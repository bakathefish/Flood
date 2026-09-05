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
day-of-season climatology; ``gamma`` is fitted in a second stage and may be zero.
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

    def to_dict(self) -> dict:
        d = asdict(self)
        d["w"] = list(self.w)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> InflowParams:
        d = dict(d)
        d["w"] = tuple(d["w"])
        return cls(**d)


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


def calibrate(
    state: pd.DataFrame,
    rain: pd.DataFrame,
    dam: str,
    area_km2: float,
    season=(6, 9),
    lags=LAGS,
    spill_fraction: float = SPILL_FRACTION,
) -> InflowParams:
    """Fit ``c``, ``w`` and the intercept on daily storage changes.

    ``state``: columns date, dam, storage_bcm and, if present, basis (only rows whose basis
    is in ``MEASURED_BASES`` are used). ``rain``: columns date, rain_mm, sm_0_7 (optional)
    for this dam's catchment. Months in ``season`` are used (inclusive). Consecutive-day
    pairs only.
    """
    s = state[(state["dam"] == dam) & state["storage_bcm"].notna()].copy()
    if "basis" in s.columns:
        s = s[s["basis"].isin(MEASURED_BASES)]
    s["date"] = pd.to_datetime(s["date"])
    s = s.set_index("date")["storage_bcm"].sort_index()
    r = rain.copy()
    r["date"] = pd.to_datetime(r["date"])
    r = r.set_index("date").sort_index()
    rv = pd.Series(rain_volume_bcm(r["rain_mm"], area_km2), index=r.index)
    X = lagged_matrix(rv, lags)
    X["api_mm"] = antecedent_mm(r["rain_mm"])

    ds = s.diff()
    gap = s.index.to_series().diff().dt.days
    ok = (gap == 1) & ds.notna()
    cap = C.DAMS[dam].live_capacity_bcm.value
    ok &= s < spill_fraction * cap
    ok &= s.shift(1) < spill_fraction * cap
    ok &= ds.abs() < MAX_ABS_DS_BCM
    ok &= s.index.month.isin(range(season[0], season[1] + 1))
    df = pd.DataFrame({"ds": ds[ok]}).join(X, how="inner").dropna()
    if len(df) < 60:
        raise ValueError(f"{dam}: only {len(df)} usable days for calibration")

    # Joint NNLS: ds = sum_k (beta_k + delta_k * api / API_REF_MM) * rv_{t-k} + intercept,
    # with beta_k = c * w_k and delta_k = c_wet * w_k (the wetness factor multiplies the whole
    # lagged response). The intercept is free through its positive and negative parts. Days
    # whose coefficient the cap C_MAX would bind are left out and the fit repeated until that
    # set is stable, so the linear fit is never asked to explain a capped day.
    L = df[[f"lag{k}" for k in lags]].to_numpy()
    api = df["api_mm"].to_numpy()
    y = df["ds"].to_numpy()
    ones = np.ones(len(df))
    A = np.column_stack([L, L * (api / API_REF_MM)[:, None], ones, -ones])
    use = np.ones(len(df), dtype=bool)
    for _ in range(6):
        coef, _ = nnls(A[use], y[use])
        beta, delta = coef[: len(lags)], coef[len(lags) : 2 * len(lags)]
        c, c_wet = float(beta.sum()), float(delta.sum())
        new_use = c + c_wet * api / API_REF_MM <= C_MAX
        if new_use.sum() < 60 or np.array_equal(new_use, use):
            break
        use = new_use
    intercept = coef[2 * len(lags)] - coef[2 * len(lags) + 1]
    total = beta + delta
    w = (
        tuple(float(x / total.sum()) for x in total)
        if total.sum() > 0
        else tuple(1.0 / len(lags) for _ in lags)
    )
    q = L @ np.asarray(w)
    c_used = np.minimum(c + c_wet * api / API_REF_MM, C_MAX)
    pred = c_used * q + intercept
    resid = y - pred
    ss_tot = float(((df["ds"] - df["ds"].mean()) ** 2).sum())
    r2 = 1.0 - float((resid**2).sum()) / ss_tot if ss_tot > 0 else float("nan")
    rmse = float(np.sqrt((resid**2).mean()))

    res = pd.Series(resid, index=df.index)
    rho = estimate_recession(res)

    params = InflowParams(
        dam=dam,
        area_km2=area_km2,
        c=c,
        w=w,
        rho=rho,
        intercept_bcm_per_day=float(intercept),
        n_days=int(len(df)),
        r2=r2,
        rmse_bcm=rmse,
        rho_raw=recession_ratio(res),
        c_wet=c_wet,
        api_days=API_DAYS,
    )
    if "sm_0_7" in r.columns and r["sm_0_7"].notna().sum() > 60:
        params.gamma = _fit_gamma(df, r, rv, params, lags)
    return params


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


def _fit_gamma(df: pd.DataFrame, r: pd.DataFrame, rv: pd.Series, p: InflowParams, lags) -> float:
    """Second stage: does the residual scale with the rain response times the soil-moisture
    anomaly? ``gamma`` is the least-squares slope, clipped to [-0.9, 3]."""
    sm = r["sm_0_7"]
    clim = sm.groupby(sm.index.dayofyear).transform("mean")
    anom = ((sm - clim) / clim).reindex(df.index)
    quick = sum(p.c * p.w[i] * df[f"lag{k}"] for i, k in enumerate(lags))
    x = (quick * anom).to_numpy()
    resid = df["ds"].to_numpy() - (quick.to_numpy() + p.intercept_bcm_per_day)
    ok = ~(np.isnan(x) | np.isnan(resid))
    if ok.sum() < 60 or float((x[ok] ** 2).sum()) == 0:
        return 0.0
    g = float((x[ok] * resid[ok]).sum() / (x[ok] ** 2).sum())
    return float(min(max(g, -0.9), 3.0))


def history_days(p: InflowParams) -> int:
    """How many days of rain (today included) the quick response needs: the lag window or
    the antecedent window plus today, whichever is longer."""
    return max(len(p.w), p.api_days + 1)


def quick_response_bcm(p: InflowParams, rain_mm_history: np.ndarray, sm_anom: float = 0.0) -> float:
    """Quick-flow volume today from the recent rain (index -1 = today). The coefficient in
    force is ``coefficient(p, api)`` with the antecedent index summed over the days before
    today that the history holds (up to ``p.api_days``)."""
    hist = np.asarray(rain_mm_history, dtype=float)
    rv = rain_volume_bcm(hist, p.area_km2)
    q = 0.0
    for k, wk in enumerate(p.w):
        if k < len(rv):
            q += wk * rv[-1 - k]
    api = (
        float(hist[max(len(hist) - 1 - p.api_days, 0) : len(hist) - 1].sum())
        if len(hist) > 1
        else 0.0
    )
    return float(coefficient(p, api) * (1.0 + p.gamma * sm_anom) * q)


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
