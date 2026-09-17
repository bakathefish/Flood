"""Inflow from catchment rain: a transparent, calibrated linear-reservoir model.

Daily reservoir inflow is decomposed into a slowly varying base (snowmelt, groundwater,
the Beas-Sutlej link at Bhakra) and a quick response to the last few days of catchment
rain:

    I_t = base_t + c * sum_k w_k * R_{t-k},     R = rain volume over the catchment (BCM)

with runoff coefficient ``c`` (dimensionless) and lag weights ``w_k`` (k = 0..3 days) that
sum to one. The base decays with a daily recession factor ``rho`` when no rain falls.

Calibration uses what the public record has: the CWC daily storage series. During filling
season the daily storage change is inflow minus a slowly varying outflow (turbines and
canals), so regressing the storage change on lagged rain volumes recovers ``c * w_k``;
the intercept absorbs base minus outflow. Days at or above 97 percent of live capacity are
excluded (the reservoir is spilling and storage no longer tracks inflow), as are days
whose storage change is physically implausible. Coefficients are constrained
non-negative (rain cannot remove water) by non-negative least squares.

Soil moisture modulates the coefficient as ``c_t = c * (1 + gamma * sm_anom_t)`` where
``sm_anom`` is the fractional anomaly of ERA5-Land 0-7 cm soil moisture against its
day-of-year climatology (a 31-day centred window over the pulled years, carried in the
parameters as ``sm_clim``); ``gamma`` is fitted in a second stage on the residual of the
rain fit. The wetness carrier is chosen by ``calibrate(..., wetness=...)``: ``"api"`` (the
antecedent rain index alone, gamma zero), ``"api+sm"`` (both) or ``"sm"`` (soil moisture
alone, ``c_wet`` zero). The verification fits and scores all three; the product uses the
one in the parameter file.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd
from scipy.optimize import nnls

from punjabflood import constants as C

LAGS = (0, 1, 2, 3)
SPILL_FRACTION = 0.97
# A one-day storage change above this is treated as a data error rather than an event. It is
# set above the largest genuine consecutive-day rises in the record (Pong 0.54 BCM on
# 2018-08-14 after 99 mm the day before) so that event days stay in the fit; stale rows and
# level slips are removed earlier by the reconciliation in ``reservoirs``.
MAX_ABS_DS_BCM = 1.0
# Wetness dependence of the runoff coefficient: c_t = c + c_wet * API_t / API_REF_MM, where
# API_t is the catchment rain over the previous API_DAYS days (today excluded), capped at
# C_MAX (a saturated catchment passes nearly all of its rain).
API_DAYS = 5
API_REF_MM = 100.0
C_MAX = 0.95
# storage bases that are measurements (the CWC table, or the CWC level through the dam's own
# rating); storage read off the rating from a bulletin level has flat-step artefacts that
# make the day-to-day changes unusable for calibration
MEASURED_BASES = ("cwc", "cwc_level")
# The threshold-excess variant of the response: catchment rain above this many millimetres in
# a day gets its own coefficient and lag weights (a flood's rain may run off faster and more
# completely than the ordinary day's). It is the heavy-day definition of the QPF skill tables.
# The variant is fitted and scored out of sample by the verification; the product uses it
# only if the parameter file carries it.
EXCESS_THRESHOLD_MM = 30.0
MIN_CALIBRATION_DAYS = 60


@dataclass
class InflowParams:
    dam: str
    area_km2: float
    c: float  # runoff coefficient
    w: tuple[float, ...]  # lag weights, sum 1
    rho: float  # daily recession of the base component (clipped estimate)
    intercept_bcm_per_day: float  # base minus outflow during the calibration window
    gamma: float = 0.0  # soil-moisture sensitivity
    n_days: int = 0
    r2: float = float("nan")
    rmse_bcm: float = float("nan")
    rho_raw: float = float("nan")  # the unclipped autocovariance ratio; nan when defaulted
    c_wet: float = 0.0  # extra runoff coefficient per API_REF_MM of antecedent rain
    api_days: int = API_DAYS
    # lag-1 autocorrelation of the calibration residuals: how the model's error persists from
    # one day to the next, used to propagate that error over a forecast horizon
    resid_acf1: float = float("nan")
    # threshold-excess response: rain above ``excess_threshold_mm`` in a day responds with
    # coefficient ``c_excess`` and lag weights ``w_excess`` (empty: no such term, and the whole
    # rain goes through ``c`` and ``w``)
    c_excess: float = 0.0
    w_excess: tuple[float, ...] = ()
    excess_threshold_mm: float = float("nan")
    # the wetness carrier ("api", "api+sm" or "sm") and the day-of-year climatology of the
    # 0-7 cm soil moisture (366 values) the anomaly is measured against; empty without one
    wetness: str = "api"
    sm_clim: tuple[float, ...] = ()
    # what the fit was made on: "storage" (day-to-day storage change, the intercept is base
    # minus passage) or "inflow" (measured daily inflow, the intercept is the base itself)
    basis: str = "storage"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["w"] = list(self.w)
        d["w_excess"] = list(self.w_excess)
        d["sm_clim"] = [round(float(x), 6) for x in self.sm_clim]
        return d

    @classmethod
    def from_dict(cls, d: dict) -> InflowParams:
        d = dict(d)
        d["w"] = tuple(d["w"])
        if "w_excess" in d:
            d["w_excess"] = tuple(d["w_excess"])
        if "sm_clim" in d:
            d["sm_clim"] = tuple(float(x) for x in d["sm_clim"])
        return cls(**d)

    @property
    def uses_sm(self) -> bool:
        return self.gamma != 0.0 and len(self.sm_clim) == 366

    @property
    def has_excess(self) -> bool:
        return bool(self.w_excess) and self.excess_threshold_mm == self.excess_threshold_mm


def rain_volume_bcm(rain_mm, area_km2: float) -> np.ndarray:
    """mm over km2 to BCM: mm * 1e-3 m * km2 * 1e6 m2 / 1e9."""
    return np.asarray(rain_mm, dtype=float) * area_km2 * 1e-6


def lagged_matrix(series: pd.Series, lags=LAGS) -> pd.DataFrame:
    return pd.DataFrame({f"lag{k}": series.shift(k) for k in lags}, index=series.index)


def antecedent_mm(rain_mm: pd.Series, days: int = API_DAYS) -> pd.Series:
    """Rain over the previous ``days`` days, today excluded (the antecedent precipitation
    index that carries catchment wetness)."""
    return rain_mm.shift(1).rolling(days, min_periods=1).sum()


def coefficient(p: InflowParams, api_mm: float) -> float:
    """The runoff coefficient in force today given the antecedent rain."""
    return float(min(p.c + p.c_wet * api_mm / API_REF_MM, C_MAX))


# --------------------------------------------------------------------------- #
# soil moisture: climatology and anomaly
# --------------------------------------------------------------------------- #
SM_CLIM_WINDOW_DAYS = 31
SM_ANOM_CLIP = (-0.9, 3.0)
WETNESS_CARRIERS = ("api", "api+sm", "sm")


def sm_climatology(sm: pd.Series, window: int = SM_CLIM_WINDOW_DAYS) -> np.ndarray:
    """Day-of-year climatology of a daily soil-moisture series: the mean by day of year over
    the years given, smoothed with a centred circular window (366 values; 29 February takes
    the smoothed value of its neighbours)."""
    s = sm.dropna()
    by_doy = s.groupby(s.index.dayofyear).mean().reindex(range(1, 367))
    v = by_doy.to_numpy(dtype=float)
    if np.isnan(v[365]):  # no leap day in the record
        v[365] = np.nanmean(v[[364, 0]])
    half = window // 2
    ext = np.concatenate([v[-half:], v, v[:half]])
    out = np.array([np.nanmean(ext[i : i + 2 * half + 1]) for i in range(366)], dtype=float)
    return out


def sm_anomaly_series(sm: pd.Series, clim) -> pd.Series:
    """Fractional anomaly ``(sm - clim) / clim`` by date, clipped to ``SM_ANOM_CLIP``; NaN
    where the series is."""
    c = np.asarray(clim, dtype=float)[sm.index.dayofyear.to_numpy() - 1]
    a = (sm.to_numpy(dtype=float) - c) / c
    return pd.Series(np.clip(a, *SM_ANOM_CLIP), index=sm.index)


def sm_anomaly(p: InflowParams, value: float, date) -> float:
    """Today's anomaly for the product: zero when the parameters carry no climatology or the
    value is missing."""
    if len(p.sm_clim) != 366 or value is None or value != value:
        return 0.0
    c = p.sm_clim[pd.Timestamp(date).dayofyear - 1]
    return float(np.clip((float(value) - c) / c, *SM_ANOM_CLIP))


def split_excess(rain_mm, threshold_mm: float | None) -> tuple[np.ndarray, np.ndarray]:
    """A day's rain as the part up to the threshold and the part above it (all of it and
    zeros when there is no threshold)."""
    r = np.asarray(rain_mm, dtype=float)
    if threshold_mm is None or threshold_mm != threshold_mm:
        return r, np.zeros_like(r)
    return np.minimum(r, threshold_mm), np.maximum(r - threshold_mm, 0.0)


def design_matrix(
    state: pd.DataFrame,
    rain: pd.DataFrame,
    dam: str,
    area_km2: float,
    season=(6, 9),
    lags=LAGS,
    spill_fraction: float = SPILL_FRACTION,
    excess_threshold_mm: float | None = None,
    sm_clim=None,
) -> pd.DataFrame:
    """The calibration table, one row per usable consecutive-day pair: the storage change
    ``ds`` (BCM), the lagged rain volumes ``lag{k}`` (of the rain up to the threshold when
    one is given), the lagged excess volumes ``ex{k}`` (rain above the threshold; zeros
    without one), the antecedent index ``api_mm``, the day's rain ``rain_mm`` and, when
    ``sm_clim`` is given and ``rain`` carries ``sm_0_7``, the soil-moisture anomaly
    ``sm_anom`` (zero otherwise, and on days the soil-moisture record lacks).

    ``state``: columns date, dam, storage_bcm and, if present, basis (only rows whose basis
    is in ``MEASURED_BASES`` are used). ``rain``: columns date, rain_mm for this dam's
    catchment. Rows keep consecutive days in the ``season`` months, both days below the spill
    fraction of live capacity, and a storage change below ``MAX_ABS_DS_BCM``."""
    s = state[(state["dam"] == dam) & state["storage_bcm"].notna()].copy()
    if "basis" in s.columns:
        s = s[s["basis"].isin(MEASURED_BASES)]
    s["date"] = pd.to_datetime(s["date"])
    s = s.set_index("date")["storage_bcm"].sort_index()
    r = rain.copy()
    r["date"] = pd.to_datetime(r["date"])
    r = r.set_index("date").sort_index()
    base_mm, ex_mm = split_excess(r["rain_mm"], excess_threshold_mm)
    X = lagged_matrix(pd.Series(rain_volume_bcm(base_mm, area_km2), index=r.index), lags)
    ex = lagged_matrix(pd.Series(rain_volume_bcm(ex_mm, area_km2), index=r.index), lags)
    ex.columns = [f"ex{k}" for k in lags]
    X = X.join(ex)
    X["api_mm"] = antecedent_mm(r["rain_mm"])
    X["rain_mm"] = r["rain_mm"]
    if sm_clim is not None and "sm_0_7" in r.columns:
        X["sm_anom"] = sm_anomaly_series(r["sm_0_7"].astype(float), sm_clim).fillna(0.0)
    else:
        X["sm_anom"] = 0.0

    ds = s.diff()
    gap = s.index.to_series().diff().dt.days
    ok = (gap == 1) & ds.notna()
    cap = C.DAMS[dam].live_capacity_bcm.value
    ok &= s < spill_fraction * cap
    ok &= s.shift(1) < spill_fraction * cap
    ok &= ds.abs() < MAX_ABS_DS_BCM
    ok &= s.index.month.isin(range(season[0], season[1] + 1))
    return pd.DataFrame({"ds": ds[ok]}).join(X, how="inner").dropna()


def calibrate(
    state: pd.DataFrame,
    rain: pd.DataFrame,
    dam: str,
    area_km2: float,
    season=(6, 9),
    lags=LAGS,
    spill_fraction: float = SPILL_FRACTION,
    excess_threshold_mm: float | None = None,
    wetness: str = "api",
    clim_exclude_year: int | None = None,
) -> InflowParams:
    """Fit ``c``, ``w`` and the intercept on daily storage changes (``design_matrix``).

    With ``excess_threshold_mm`` the rain above the threshold gets its own coefficient and
    lag weights (``c_excess``, ``w_excess``), fitted jointly; without it the whole rain goes
    through ``c`` and ``w`` as before. ``wetness`` picks the carrier of catchment wetness
    (``WETNESS_CARRIERS``); with soil moisture in it the climatology is built from the
    ``sm_0_7`` column of ``rain`` (``clim_exclude_year`` keeps a held-out season out of it)
    and ``gamma`` is fitted on the residual of the rain fit.
    """
    if wetness not in WETNESS_CARRIERS:
        raise ValueError(f"wetness must be one of {WETNESS_CARRIERS}, not {wetness!r}")
    use_sm = wetness != "api"
    sm_clim = None
    if use_sm:
        r_sm = rain.copy()
        r_sm["date"] = pd.to_datetime(r_sm["date"])
        r_sm = r_sm.set_index("date").sort_index()
        if "sm_0_7" not in r_sm.columns or r_sm["sm_0_7"].notna().sum() < MIN_CALIBRATION_DAYS:
            raise ValueError(f"{dam}: no soil-moisture record to fit the {wetness!r} carrier")
        s_sm = r_sm["sm_0_7"].astype(float)
        if clim_exclude_year is not None:
            s_sm = s_sm[s_sm.index.year != clim_exclude_year]
        sm_clim = sm_climatology(s_sm)
    df = design_matrix(
        state, rain, dam, area_km2, season, lags, spill_fraction, excess_threshold_mm, sm_clim
    )
    if len(df) < MIN_CALIBRATION_DAYS:
        raise ValueError(f"{dam}: only {len(df)} usable days for calibration")
    with_excess = excess_threshold_mm is not None and excess_threshold_mm == excess_threshold_mm

    # Joint NNLS: ds = sum_k (beta_k + delta_k * api / API_REF_MM) * rv_{t-k}
    #                  [+ sum_k eps_k * ex_{t-k}] + intercept,
    # with beta_k = c * w_k and delta_k = c_wet * w_k (the wetness factor multiplies the whole
    # lagged response) and eps_k = c_excess * w_excess_k. The intercept is free through its
    # positive and negative parts. Days whose coefficient the cap C_MAX would bind are left
    # out and the fit repeated until that set is stable, so the linear fit is never asked to
    # explain a capped day.
    nl = len(lags)
    L = df[[f"lag{k}" for k in lags]].to_numpy()
    E = df[[f"ex{k}" for k in lags]].to_numpy()
    api = df["api_mm"].to_numpy()
    y = df["ds"].to_numpy()
    ones = np.ones(len(df))
    # the "sm" carrier drops the antecedent-rain block: its columns are zeroed, so NNLS
    # returns zero for them and the rest of the bookkeeping is unchanged
    api_block = L * (api / API_REF_MM)[:, None] if wetness != "sm" else np.zeros_like(L)
    blocks = [L, api_block] + ([E] if with_excess else [])
    A = np.column_stack([*blocks, ones, -ones])
    use = np.ones(len(df), dtype=bool)
    for _ in range(6):
        coef, _ = nnls(A[use], y[use])
        beta, delta = coef[:nl], coef[nl : 2 * nl]
        c, c_wet = float(beta.sum()), float(delta.sum())
        new_use = c + c_wet * api / API_REF_MM <= C_MAX
        if new_use.sum() < MIN_CALIBRATION_DAYS or np.array_equal(new_use, use):
            break
        use = new_use
    pos = 2 * nl
    if with_excess:
        eps = coef[pos : pos + nl]
        pos += nl
        c_ex = float(eps.sum())
        w_ex = tuple(float(x / c_ex) for x in eps) if c_ex > 0 else tuple(0.0 for _ in lags)
    else:
        c_ex, w_ex = 0.0, ()
    intercept = coef[pos] - coef[pos + 1]
    total = beta + delta
    w = (
        tuple(float(x / total.sum()) for x in total)
        if total.sum() > 0
        else tuple(1.0 / len(lags) for _ in lags)
    )
    params = InflowParams(
        dam=dam,
        area_km2=area_km2,
        c=c,
        w=w,
        rho=DEFAULT_RHO,
        intercept_bcm_per_day=float(intercept),
        n_days=int(len(df)),
        c_wet=c_wet,
        api_days=API_DAYS,
        c_excess=c_ex,
        w_excess=w_ex,
        excess_threshold_mm=float(excess_threshold_mm) if with_excess else float("nan"),
        wetness=wetness,
        sm_clim=tuple(float(x) for x in sm_clim) if sm_clim is not None else (),
    )
    if use_sm:
        # second stage: the residual of the rain fit against the response times the anomaly
        params.gamma = _fit_gamma(df, params)
    resid = y - predict_storage_change(params, df)
    ss_tot = float(((df["ds"] - df["ds"].mean()) ** 2).sum())
    params.r2 = 1.0 - float((resid**2).sum()) / ss_tot if ss_tot > 0 else float("nan")
    params.rmse_bcm = float(np.sqrt((resid**2).mean()))
    res = pd.Series(resid, index=df.index)
    params.rho = estimate_recession(res)
    params.rho_raw = recession_ratio(res)
    params.resid_acf1 = residual_acf1(res)
    return params


def _quick_from_design(p: InflowParams, df: pd.DataFrame) -> np.ndarray:
    """The rain response on the rows of a design matrix, before the soil-moisture factor:
    the wetness-dependent coefficient times the lagged response."""
    lags = range(len(p.w))
    L = df[[f"lag{k}" for k in lags]].to_numpy()
    api = df["api_mm"].to_numpy()
    c_used = np.minimum(p.c + p.c_wet * api / API_REF_MM, C_MAX)
    return c_used * (L @ np.asarray(p.w))


def predict_storage_change(p: InflowParams, df: pd.DataFrame) -> np.ndarray:
    """The fitted storage-change relation on the rows of a ``design_matrix`` built with the
    same threshold and climatology as ``p``: the wetness-dependent coefficient times the
    lagged response, times the soil-moisture factor where ``gamma`` is non-zero, plus the
    excess response where the parameters carry one, plus the intercept."""
    lags = range(len(p.w))
    quick = _quick_from_design(p, df)
    if p.gamma != 0.0 and "sm_anom" in df.columns:
        quick = quick * (1.0 + p.gamma * df["sm_anom"].to_numpy(dtype=float))
    pred = quick + p.intercept_bcm_per_day
    if p.has_excess:
        E = df[[f"ex{k}" for k in lags]].to_numpy()
        pred = pred + p.c_excess * (E @ np.asarray(p.w_excess))
    return pred


def loso_score(
    state: pd.DataFrame,
    rain: pd.DataFrame,
    dam: str,
    area_km2: float,
    excess_threshold_mm: float | None = None,
    heavy_mm: float = EXCESS_THRESHOLD_MM,
    wetness: str = "api",
) -> dict:
    """Leave-one-season-out score of the calibration: for every season in the record the
    model is fitted on the other seasons and its storage-change prediction scored on the
    held-out one. Returns the days scored, the root-mean-square error (BCM per day), and the
    same on the heavy days (the day's catchment rain at or above ``heavy_mm``) with their
    mean residual (observed minus predicted: positive when heavy days are under-predicted).
    Seasons whose training set is too short for a fit are skipped. With a soil-moisture
    carrier each fold's climatology leaves the held-out season out, and the held-out rows
    take their anomaly from that fold's climatology."""
    df = design_matrix(state, rain, dam, area_km2, excess_threshold_mm=excess_threshold_mm)
    st = state.copy()
    st["date"] = pd.to_datetime(st["date"])
    resid, heavy = [], []
    for y in sorted(set(df.index.year)):
        try:
            p = calibrate(
                st[st["date"].dt.year != y],
                rain,
                dam,
                area_km2,
                excess_threshold_mm=excess_threshold_mm,
                wetness=wetness,
                clim_exclude_year=y if wetness != "api" else None,
            )
        except ValueError:
            continue
        if p.sm_clim:
            fold = design_matrix(
                state,
                rain,
                dam,
                area_km2,
                excess_threshold_mm=excess_threshold_mm,
                sm_clim=p.sm_clim,
            )
            held = fold[fold.index.year == y]
        else:
            held = df[df.index.year == y]
        resid.append(held["ds"].to_numpy() - predict_storage_change(p, held))
        heavy.append(held["rain_mm"].to_numpy() >= heavy_mm)
    if not resid:
        return {"n_seasons": 0, "n_days": 0, "rmse_bcm": float("nan"), "n_heavy_days": 0}
    r = np.concatenate(resid)
    h = np.concatenate(heavy)
    return {
        "n_seasons": len(resid),
        "n_days": int(len(r)),
        "rmse_bcm": float(np.sqrt(np.mean(r**2))),
        "n_heavy_days": int(h.sum()),
        "heavy_rmse_bcm": float(np.sqrt(np.mean(r[h] ** 2))) if h.any() else float("nan"),
        "heavy_bias_bcm": float(np.mean(r[h])) if h.any() else float("nan"),
    }


DEFAULT_RHO = 0.9
RHO_CLIP = (0.5, 0.99)


def recession_ratio(res: pd.Series) -> float:
    """The unclipped lag-2 to lag-1 autocovariance ratio of the residuals on consecutive
    days, or nan when the series is too short or the autocovariances too small to trust."""
    res = res.dropna()
    if len(res) < 40:
        return float("nan")
    day = res.index.to_series().diff().dt.days
    r0 = res - res.mean()
    r1 = r0.shift(1)
    r2 = r0.shift(2)
    ok1 = r1.notna() & (day == 1)
    ok2 = r2.notna() & (day == 1) & (day.shift(1) == 1)
    if ok1.sum() < 30 or ok2.sum() < 30:
        return float("nan")
    c1 = float((r0[ok1] * r1[ok1]).mean())
    c2 = float((r0[ok2] * r2[ok2]).mean())
    var = float((r0**2).mean())
    if var <= 0 or c1 <= 0.05 * var or c2 <= 0:
        return float("nan")
    return c2 / c1


def residual_acf1(res: pd.Series) -> float:
    """Lag-1 autocorrelation of the residuals over consecutive days: the day-to-day
    persistence of the model's own error, which decides how that error accumulates over a
    forecast horizon (independent errors partly cancel in the volume, persistent ones do
    not). Nan when the series is too short."""
    res = res.dropna()
    if len(res) < 40:
        return float("nan")
    day = res.index.to_series().diff().dt.days
    r0 = res - res.mean()
    r1 = r0.shift(1)
    ok = r1.notna() & (day == 1)
    var = float((r0**2).mean())
    if ok.sum() < 30 or var <= 0:
        return float("nan")
    return float((r0[ok] * r1[ok]).mean() / var)


def estimate_recession(res: pd.Series, default: float = DEFAULT_RHO) -> float:
    """Daily persistence of the slow (base minus outflow) component from the calibration
    residuals, robust to day-to-day measurement noise in the storage series.

    The residual is a slowly varying signal plus independent noise. For an AR(1) signal
    with white noise on top, the lag-1 autocorrelation is biased towards zero while the
    ratio of the lag-2 to the lag-1 autocovariance equals the signal's own persistence, so
    that ratio is used (``recession_ratio``). Clipped to ``RHO_CLIP``; ``default`` when the
    ratio cannot be trusted. A ratio at the upper clip means the residual drifts over the
    season (base and outflow both move slowly) rather than recessing; the parameter file
    keeps the raw ratio so the report can say so.
    """
    ratio = recession_ratio(res)
    if ratio != ratio:  # nan
        return default
    return float(min(max(ratio, RHO_CLIP[0]), RHO_CLIP[1]))


def _fit_gamma(df: pd.DataFrame, p: InflowParams) -> float:
    """Second stage: does the residual of the rain fit scale with the rain response times
    the soil-moisture anomaly (the ``sm_anom`` column of the design matrix)? ``gamma`` is
    the least-squares slope through the origin, clipped to ``SM_ANOM_CLIP``'s range."""
    quick = _quick_from_design(p, df)
    if p.has_excess:
        lags = range(len(p.w))
        E = df[[f"ex{k}" for k in lags]].to_numpy()
        quick = quick + p.c_excess * (E @ np.asarray(p.w_excess))
    x = quick * df["sm_anom"].to_numpy(dtype=float)
    resid = df["ds"].to_numpy() - (quick + p.intercept_bcm_per_day)
    ok = ~(np.isnan(x) | np.isnan(resid))
    if ok.sum() < MIN_CALIBRATION_DAYS or float((x[ok] ** 2).sum()) == 0:
        return 0.0
    g = float((x[ok] * resid[ok]).sum() / (x[ok] ** 2).sum())
    return float(np.clip(g, *SM_ANOM_CLIP))


def history_days(p: InflowParams) -> int:
    """How many days of rain (today included) the quick response needs: the lag window or
    the antecedent window plus today, whichever is longer."""
    return max(len(p.w), p.api_days + 1)


def quick_response_bcm(p: InflowParams, rain_mm_history: np.ndarray, sm_anom: float = 0.0) -> float:
    """Quick-flow volume today from the recent rain (index -1 = today). The coefficient in
    force is ``coefficient(p, api)`` with the antecedent index summed over the days before
    today that the history holds (up to ``p.api_days``)."""
    hist = np.asarray(rain_mm_history, dtype=float)
    base_mm, ex_mm = split_excess(hist, p.excess_threshold_mm if p.has_excess else None)
    rv = rain_volume_bcm(base_mm, p.area_km2)
    q = 0.0
    for k, wk in enumerate(p.w):
        if k < len(rv):
            q += wk * rv[-1 - k]
    api = (
        float(hist[max(len(hist) - 1 - p.api_days, 0) : len(hist) - 1].sum())
        if len(hist) > 1
        else 0.0
    )
    quick = coefficient(p, api) * (1.0 + p.gamma * sm_anom) * q
    if p.has_excess:
        ev = rain_volume_bcm(ex_mm, p.area_km2)
        quick += p.c_excess * sum(wk * ev[-1 - k] for k, wk in enumerate(p.w_excess) if k < len(ev))
    return float(quick)


def predict_daily_bcm(
    p: InflowParams,
    rain_mm_forecast,
    base_cusecs: float,
    rain_mm_recent=(),
    sm_anom: float = 0.0,
) -> np.ndarray:
    """Daily inflow volumes (BCM) for the forecast days.

    ``base_cusecs`` is today's base flow (observed inflow minus today's quick response);
    it decays by ``rho`` per day. ``rain_mm_recent`` are the last days of observed rain
    (oldest first) that still contribute through the lag weights.
    """
    hist = list(rain_mm_recent)
    base = C.cusec_days_to_bcm(base_cusecs)
    out = []
    n = history_days(p)
    for d, rmm in enumerate(rain_mm_forecast, start=1):
        hist.append(float(rmm))
        q = quick_response_bcm(p, np.asarray(hist[-n:]), sm_anom)
        out.append(base * (p.rho**d) + q)
    return np.asarray(out)


def transferred_params(p: InflowParams, name: str, area_km2: float) -> InflowParams:
    """A dam's calibrated response carried to another catchment: the same coefficient,
    wetness dependence and lag weights over the other catchment's area."""
    from dataclasses import replace

    return replace(p, dam=name, area_km2=float(area_km2))


def local_inflow_cusecs(p: InflowParams, area_km2: float, rain_mm: pd.Series) -> pd.Series:
    """Runoff of an intermediate catchment (between a dam and a control point) from its own
    daily rain, in cusecs per day, with ``p`` transferred to its area: the quick response
    only, no base component, so a lower bound on what the tributaries add. ``rain_mm`` is
    indexed by date; the antecedent index and the lags read the days before each one."""
    t = transferred_params(p, p.dam, area_km2)
    s = pd.Series(np.asarray(rain_mm, dtype=float), index=rain_mm.index).sort_index()
    hist = s.to_numpy()
    n_hist = history_days(t)
    out = np.zeros(len(hist))
    for i in range(len(hist)):
        lo = max(i - n_hist + 1, 0)
        out[i] = C.bcm_to_cusec_days(quick_response_bcm(t, hist[lo : i + 1]))
    return pd.Series(out, index=s.index)


def local_inflow_forecast_cusecs(
    p: InflowParams, area_km2: float, rain_mm_recent, rain_mm_forecast
) -> np.ndarray:
    """The same term on the forecast days: the recent observed days feed the lags and the
    antecedent index of the first forecast days. One value per forecast day."""
    recent = np.asarray(list(rain_mm_recent), dtype=float)
    fut = np.asarray(list(rain_mm_forecast), dtype=float)
    if len(fut) == 0:
        return np.zeros(0)
    both = np.concatenate([recent, fut])
    s = local_inflow_cusecs(p, area_km2, pd.Series(both, index=pd.RangeIndex(len(both))))
    return s.to_numpy()[len(recent) :]


def base_from_observed(
    p: InflowParams, observed_inflow_cusecs: float, rain_mm_recent, sm_anom=0.0
) -> float:
    """Today's base flow in cusecs: observed inflow minus the quick response the recent rain
    explains, floored at zero."""
    q_bcm = quick_response_bcm(p, np.asarray(list(rain_mm_recent)), sm_anom)
    return max(observed_inflow_cusecs - C.bcm_to_cusec_days(q_bcm), 0.0)


def volume_bcm(
    p: InflowParams,
    rain_mm_forecast,
    base_cusecs: float,
    horizon_days: int,
    rain_mm_recent=(),
    sm_anom: float = 0.0,
) -> float:
    daily = predict_daily_bcm(
        p, list(rain_mm_forecast)[:horizon_days], base_cusecs, rain_mm_recent, sm_anom
    )
    return float(daily.sum())


# --- calibration on measured inflow ------------------------------------------------------


def inflow_design(inflow_daily: pd.Series, rain: pd.DataFrame, area_km2: float, lags=LAGS):
    """One row per day with a measured inflow and a full rain history: the daily inflow
    volume ``y`` (BCM), the lagged rain volumes ``lag{k}``, the antecedent index ``api_mm``
    and the day's rain. ``inflow_daily``: cusecs indexed by date (one value per day)."""
    r = rain.copy()
    r["date"] = pd.to_datetime(r["date"])
    r = r.set_index("date").sort_index()
    X = lagged_matrix(pd.Series(rain_volume_bcm(r["rain_mm"], area_km2), index=r.index), lags)
    X["api_mm"] = antecedent_mm(r["rain_mm"])
    X["rain_mm"] = r["rain_mm"]
    y = pd.Series(inflow_daily, dtype=float)
    y.index = pd.to_datetime(y.index)
    y = C.cusec_days_to_bcm(y.sort_index())
    df = X.join(y.rename("y"), how="inner").dropna()
    return df


def calibrate_on_inflow(
    inflow_daily: pd.Series,
    rain: pd.DataFrame,
    dam: str,
    area_km2: float,
    lags=LAGS,
    min_days: int = 20,
) -> InflowParams:
    """Fit ``c``, ``c_wet``, ``w`` and a constant base on measured daily inflow: the same
    non-negative least squares as ``calibrate`` with the inflow volume as the target and the
    base as a non-negative constant (``basis='inflow'``). One season of bulletins is enough
    for the fit and for nothing more; the caller says what it is used for."""
    df = inflow_design(inflow_daily, rain, area_km2, lags)
    if len(df) < min_days:
        raise ValueError(f"{dam}: only {len(df)} inflow days with a rain history")
    nl = len(lags)
    L = df[[f"lag{k}" for k in lags]].to_numpy()
    api = df["api_mm"].to_numpy()
    y = df["y"].to_numpy()
    A = np.column_stack([L, L * (api / API_REF_MM)[:, None], np.ones(len(df))])
    use = np.ones(len(df), dtype=bool)
    for _ in range(6):
        coef, _ = nnls(A[use], y[use])
        beta, delta = coef[:nl], coef[nl : 2 * nl]
        c, c_wet = float(beta.sum()), float(delta.sum())
        new_use = c + c_wet * api / API_REF_MM <= C_MAX
        if new_use.sum() < min_days or np.array_equal(new_use, use):
            break
        use = new_use
    total = beta + delta
    w = (
        tuple(float(x / total.sum()) for x in total)
        if total.sum() > 0
        else tuple(1.0 / nl for _ in lags)
    )
    p = InflowParams(
        dam=dam,
        area_km2=area_km2,
        c=c,
        w=w,
        rho=DEFAULT_RHO,
        intercept_bcm_per_day=float(coef[2 * nl]),
        n_days=int(len(df)),
        c_wet=c_wet,
        api_days=API_DAYS,
        basis="inflow",
    )
    pred = _quick_from_design(p, df) + p.intercept_bcm_per_day
    resid = y - pred
    ss_tot = float(((y - y.mean()) ** 2).sum())
    p.r2 = 1.0 - float((resid**2).sum()) / ss_tot if ss_tot > 0 else float("nan")
    p.rmse_bcm = float(np.sqrt((resid**2).mean()))
    p.resid_acf1 = residual_acf1(pd.Series(resid, index=df.index))
    return p


def score_on_inflow(
    p: InflowParams,
    inflow_daily: pd.Series,
    rain: pd.DataFrame,
    area_km2: float,
    absorption_cusecs: float,
    base_from_intercept: bool = False,
    fitted_base: bool = False,
) -> dict:
    """A parameter set against measured daily inflow: base plus quick response on every
    day with a rain history. The base is the intercept plus the non-spill passage for a
    storage-change fit (its intercept is base minus passage, the convention of the
    verification runs), the intercept itself with ``base_from_intercept`` (an inflow fit),
    or with ``fitted_base`` the constant that makes the set unbiased on these days (the
    response judged on its own, the base convention set aside). Returns days, bias,
    Pearson r, MAE (cusecs), the mean observed and predicted inflow, and
    ``coefficient_ratio``: the coefficient an inflow fit on the same days gives over this
    set's, the measure of what the storage-change fit cannot see."""
    df = inflow_design(inflow_daily, rain, area_km2, range(len(p.w)))
    if df.empty:
        return {"n_days": 0, "note": "no days"}
    base = (
        max(p.intercept_bcm_per_day, 0.0)
        if base_from_intercept
        else max(p.intercept_bcm_per_day + C.cusec_days_to_bcm(absorption_cusecs), 0.0)
    )
    quick = _quick_from_design(p, df)
    if fitted_base:
        base = float(max((df["y"].to_numpy() - quick).mean(), 0.0))
    pred = C.bcm_to_cusec_days(quick + base)
    obs = C.bcm_to_cusec_days(df["y"].to_numpy())
    out = {
        "n_days": int(len(df)),
        "bias_pct": float((pred.mean() - obs.mean()) / obs.mean() * 100) if obs.mean() > 0 else float("nan"),
        "pearson_r": float(np.corrcoef(pred, obs)[0, 1]) if pred.std() > 0 and obs.std() > 0 else float("nan"),
        "mae_cusecs": float(np.abs(pred - obs).mean()),
        "mean_obs_cusecs": float(obs.mean()),
        "mean_pred_cusecs": float(pred.mean()),
        "base_cusecs": float(C.bcm_to_cusec_days(base)),
    }
    try:
        fit = calibrate_on_inflow(inflow_daily, rain, p.dam, area_km2, lags=range(len(p.w)))
        out["coefficient_ratio"] = float(fit.c / p.c) if p.c > 0 else float("nan")
        out["wet_coefficient_ratio"] = float(fit.c_wet / p.c_wet) if p.c_wet > 0 else float("nan")
    except ValueError:
        out["coefficient_ratio"] = float("nan")
    return out


def as_storage_basis(p: InflowParams, absorption_cusecs: float) -> InflowParams:
    """An inflow-basis parameter set expressed in the storage-change convention (intercept =
    base minus the non-spill passage), so the verification runs and the product, which add
    the passage back, read the same base. A storage-basis set is returned unchanged."""
    if p.basis != "inflow":
        return p
    q = InflowParams.from_dict(p.to_dict())
    q.intercept_bcm_per_day = p.intercept_bcm_per_day - C.cusec_days_to_bcm(absorption_cusecs)
    q.basis = "storage"
    return q


def storage_change_score(
    p: InflowParams,
    state: pd.DataFrame,
    rain: pd.DataFrame,
    dam: str,
    area_km2: float,
    heavy_mm: float = EXCESS_THRESHOLD_MM,
) -> dict:
    """A fixed parameter set scored on the storage-change record, the same keys as
    ``loso_score``. For a set not fitted on that record (an inflow fit) every season is out
    of sample, so no leave-one-out is needed; ``n_seasons`` counts the seasons scored."""
    df = design_matrix(state, rain, dam, area_km2)
    if df.empty:
        return {"n_seasons": 0, "n_days": 0, "rmse_bcm": float("nan"), "n_heavy_days": 0}
    r = df["ds"].to_numpy() - predict_storage_change(p, df)
    h = df["rain_mm"].to_numpy() >= heavy_mm
    return {
        "n_seasons": int(len(set(df.index.year))),
        "n_days": int(len(r)),
        "rmse_bcm": float(np.sqrt(np.mean(r**2))),
        "n_heavy_days": int(h.sum()),
        "heavy_rmse_bcm": float(np.sqrt(np.mean(r[h] ** 2))) if h.any() else float("nan"),
        "heavy_bias_bcm": float(np.mean(r[h])) if h.any() else float("nan"),
    }

