"""Verification of the hazard tier on the dense records.

Three tests, each against a record that exists independently of this project:

1. **Annual peak class, 38 years.** The WRD's own annual maximum discharge at Harike,
   Ropar and Dhilwan (1988 to 2025) with its High/Medium/Low class, against season
   predictors built from ERA5 catchment rain (all years) and CWC storage (from 1991):
   rank correlation with the peak, area under the ROC curve for the High class, and
   leave-one-year-out logistic probabilities scored by the Brier score against the
   climatological base rate.
2. **Event timing.** The routed forced-release hydrograph against the dated Dhilwan peaks
   (2023-08-17, 2025-08-31): signed lag in days and the magnitude ratio.
3. **Live season.** The inflow model against the BBMB bulletins of 2026: bias, correlation,
   mean absolute error.

Everything is written to ``outputs/verification/`` as CSV and JSON; the Markdown report is
rendered from those files so no number is typed by hand.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

from punjabflood import constants as C
from punjabflood import hei, inflow, routing

SEASON_MONTHS = (6, 7, 8, 9)


def _season(df: pd.DataFrame, col: str = "date") -> pd.DataFrame:
    d = pd.to_datetime(df[col])
    return df[d.dt.month.isin(SEASON_MONTHS)]


def rain_predictors(rain_daily: pd.DataFrame, catchment: str, area_km2: float) -> pd.DataFrame:
    """Per year: season rain volume (BCM) and the maximum 1, 3, 5 and 10-day volumes."""
    r = rain_daily[rain_daily["catchment"] == catchment].copy()
    r["date"] = pd.to_datetime(r["date"])
    r = r.set_index("date").sort_index()
    vol = pd.Series(inflow.rain_volume_bcm(r["rain_mm"], area_km2), index=r.index)
    rows = []
    for year, g in vol.groupby(vol.index.year):
        s = g[g.index.month.isin(SEASON_MONTHS)]
        if s.notna().sum() < 100:
            continue
        rows.append(
            {
                "year": int(year),
                f"{catchment}_season_bcm": float(s.sum()),
                f"{catchment}_max1d_bcm": float(s.max()),
                f"{catchment}_max3d_bcm": float(s.rolling(3).sum().max()),
                f"{catchment}_max5d_bcm": float(s.rolling(5).sum().max()),
                f"{catchment}_max10d_bcm": float(s.rolling(10).sum().max()),
            }
        )
    return pd.DataFrame(rows).set_index("year")


def storage_predictors(state: pd.DataFrame, dam: str) -> pd.DataFrame:
    """Per year: storage fraction on 1 July, 1 August, 15 August and the season maximum."""
    s = state[(state["dam"] == dam) & state["storage_bcm"].notna()].copy()
    s["date"] = pd.to_datetime(s["date"])
    s = s.set_index("date")["storage_bcm"].sort_index()
    cap = C.DAMS[dam].live_capacity_bcm.value
    rows = []
    for year, g in s.groupby(s.index.year):
        g = g[g.index.month.isin(SEASON_MONTHS)]
        if len(g) < 30:
            continue

        def at(md):
            t = pd.Timestamp(f"{year}-{md}")
            w = g[(g.index >= t - pd.Timedelta(days=3)) & (g.index <= t + pd.Timedelta(days=3))]
            return float(w.iloc[(w.index - t).map(abs).argmin()]) / cap if len(w) else np.nan

        rows.append(
            {
                "year": int(year),
                f"{dam}_frac_jul01": at("07-01"),
                f"{dam}_frac_aug01": at("08-01"),
                f"{dam}_frac_aug15": at("08-15"),
                f"{dam}_frac_max": float(g.max()) / cap,
                f"{dam}_days_above_95pct": int((g > 0.95 * cap).sum()),
            }
        )
    return pd.DataFrame(rows).set_index("year")


MAX_CARRY_DAYS = 21  # longest gap between measurements the model is allowed to bridge


def carry_storage(
    measured: pd.Series,
    basis: dict,
    rain: pd.Series,
    dam: str,
    params: inflow.InflowParams,
    max_carry_days: int = MAX_CARRY_DAYS,
) -> tuple[pd.Series, dict]:
    """Daily storage between measurements from the model's own water balance.

    Each day without a measurement takes ``S = min(cap, S_prev + I - A)``: the one-day inflow
    the calibrated model gives for the observed rain, less the non-spill passage ``A``, which
    is exactly the storage-change relation the model was fitted on. Every measurement
    re-anchors the path; gaps longer than ``max_carry_days`` are left empty. Carried days
    get ``basis='model'``."""
    cap = C.DAMS[dam].live_capacity_bcm.value
    absorb = hei.absorption_cusecs(dam)
    a_bcm = C.cusec_days_to_bcm(absorb)
    base_bcm = max(params.intercept_bcm_per_day + a_bcm, 0.0)
    base_cusecs = C.bcm_to_cusec_days(base_bcm)
    measured = measured.sort_index()
    full = pd.date_range(measured.index.min(), measured.index.max(), freq="D")
    out = pd.Series(np.nan, index=full)
    out_basis = {}
    prev = np.nan
    since = 0
    for d in full:
        if d in measured.index:
            prev = float(measured.loc[d])
            since = 0
            out.loc[d] = prev
            out_basis[d] = basis.get(d, "")
            continue
        since += 1
        if np.isnan(prev) or since > max_carry_days:
            prev = np.nan
            continue
        hist = rain.reindex(pd.date_range(d - pd.Timedelta(days=len(params.w) - 1), d))
        if hist.isna().any():
            prev = np.nan
            continue
        inflow_bcm = float(
            inflow.predict_daily_bcm(
                params, [hist.iloc[-1]], base_cusecs, rain_mm_recent=hist.iloc[:-1].to_numpy()
            )[0]
        )
        prev = float(min(max(prev + inflow_bcm - a_bcm, 0.0), cap))
        out.loc[d] = prev
        out_basis[d] = "model"
    return out.dropna(), out_basis


def perfect_prog_hei(
    state: pd.DataFrame,
    rain_daily: pd.DataFrame,
    dam: str,
    catchment: str,
    params: inflow.InflowParams,
    horizon_days: int = 5,
    carry: str = "given",
) -> pd.DataFrame:
    """Daily headroom-exhaustion index using observed rain as a perfect forecast and the
    recorded storage as the state. Returns date, dam, hei, forced_release_bcm, the horizon
    peak and first-day forced releases, and the storage basis of each day.

    ``carry='given'`` uses the storage rows as supplied (the caller may have interpolated
    gaps, basis ``interp``). ``carry='model'`` drops interpolated rows and bridges the gaps
    between measurements with ``carry_storage`` (basis ``model``)."""
    s = state[(state["dam"] == dam) & state["storage_bcm"].notna()].copy()
    s["date"] = pd.to_datetime(s["date"])
    if carry == "model" and "basis" in s:
        s = s[s["basis"] != "interp"]
    basis = s.set_index("date")["basis"].to_dict() if "basis" in s else {}
    s = s.set_index("date")["storage_bcm"].sort_index()
    r = rain_daily[rain_daily["catchment"] == catchment].copy()
    r["date"] = pd.to_datetime(r["date"])
    rain = r.set_index("date")["rain_mm"].sort_index()
    if carry == "model" and len(s):
        s, basis = carry_storage(s, basis, rain, dam, params)
    absorb = hei.absorption_cusecs(dam)
    rows = []
    for d, storage in s.items():
        if d.month not in SEASON_MONTHS:
            continue
        fut = rain.reindex(pd.date_range(d + pd.Timedelta(days=1), periods=horizon_days))
        past = rain.reindex(pd.date_range(d - pd.Timedelta(days=3), d))
        if fut.isna().any() or past.isna().any():
            continue
        # base flow: the model's own intercept-free base is unknown historically; use the
        # rain-only quick response plus the calibration intercept as the base component
        base_bcm = max(params.intercept_bcm_per_day + C.cusec_days_to_bcm(absorb), 0.0)
        daily = inflow.predict_daily_bcm(
            params, fut.to_numpy(), C.bcm_to_cusec_days(base_bcm), rain_mm_recent=past.to_numpy()
        )
        res = hei.headroom_exhaustion(dam, float(storage), daily, absorb)
        rows.append(
            {
                "date": d,
                "dam": dam,
                "hei": res.hei,
                "forced_release_bcm": res.forced_release_bcm,
                "peak_release_cusecs": max(res.release_by_day_cusecs)
                if res.release_by_day_cusecs
                else 0.0,
                "release_day1_cusecs": res.release_by_day_cusecs[0]
                if res.release_by_day_cusecs
                else 0.0,
                "inflow_day1_cusecs": C.bcm_to_cusec_days(float(daily[0])),
                "rain_day1_mm": float(fut.iloc[0]),
                "day_of_exhaustion": res.day_of_exhaustion,
                "storage_basis": basis.get(d, ""),
            }
        )
    return pd.DataFrame(rows)


def annual_max(df: pd.DataFrame, col: str, name: str) -> pd.DataFrame:
    d = pd.to_datetime(df["date"])
    out = df.groupby(d.dt.year)[col].max().rename(name).to_frame()
    out.index.name = "year"
    return out


def peak_class_test(
    pred: pd.DataFrame,
    peaks: pd.DataFrame,
    predictor: str,
    peak_col: str = "harike_us_cusecs",
    class_col: str = "wrd_class",
) -> dict:
    """Rank correlation, High-class AUROC and leave-one-year-out Brier for one predictor."""
    df = (
        pred[[predictor]]
        .join(peaks.set_index("year")[[peak_col, class_col]], how="inner")
        .dropna(subset=[predictor, peak_col])
    )
    n = len(df)
    out = {"predictor": predictor, "n_years": int(n)}
    if n < 8:
        out["note"] = "too few years"
        return out
    rho, p = spearmanr(df[predictor], df[peak_col])
    out["spearman_rho"] = float(rho)
    out["spearman_p"] = float(p)
    y = (df[class_col].fillna("") == "H").astype(int).to_numpy()
    out["n_high"] = int(y.sum())
    if 0 < y.sum() < n:
        out["auroc_high"] = float(roc_auc_score(y, df[predictor]))
        # leave-one-year-out logistic regression on the standardised predictor
        x = df[[predictor]].to_numpy(dtype=float)
        probs = np.full(n, np.nan)
        for i in range(n):
            mask = np.arange(n) != i
            if y[mask].sum() == 0 or y[mask].sum() == mask.sum():
                probs[i] = y[mask].mean()
                continue
            mu, sd = x[mask].mean(), x[mask].std() or 1.0
            clf = LogisticRegression(C=1.0)
            clf.fit((x[mask] - mu) / sd, y[mask])
            probs[i] = clf.predict_proba((x[i : i + 1] - mu) / sd)[0, 1]
        clim = np.array([np.delete(y, i).mean() for i in range(n)])
        out["brier_loyo"] = float(np.mean((probs - y) ** 2))
        out["brier_climatology"] = float(np.mean((clim - y) ** 2))
        out["brier_skill_score"] = (
            1.0 - out["brier_loyo"] / out["brier_climatology"]
            if out["brier_climatology"] > 0
            else float("nan")
        )
        out["loyo_probabilities"] = {int(k): float(v) for k, v in zip(df.index, probs, strict=True)}
    return out


def event_timing_test(
    arrivals: pd.DataFrame,
    peaks_dhilwan: pd.DataFrame,
    years=(2023, 2025),
    station: str = "Dhilwan",
) -> pd.DataFrame:
    """Predicted versus observed Dhilwan peak per year: dates, magnitudes, signed lag."""
    a = arrivals[arrivals["station"] == station].copy()
    a["date"] = pd.to_datetime(a["date"])
    obs = peaks_dhilwan.set_index("year")
    rows = []
    for y in years:
        g = a[a["date"].dt.year == y]
        if g.empty or g["cusecs"].max() <= 0:
            rows.append({"year": y, "note": "no predicted release"})
            continue
        i = g["cusecs"].idxmax()
        pred_date = g.loc[i, "date"]
        obs_date = pd.Timestamp(obs.loc[y, "date"])
        rows.append(
            {
                "year": y,
                "predicted_peak_date": pred_date.date().isoformat(),
                "predicted_peak_cusecs": float(g.loc[i, "cusecs"]),
                "observed_peak_date": obs_date.date().isoformat(),
                "observed_peak_cusecs": float(obs.loc[y, "discharge_cusecs"]),
                "lag_days": int((pred_date - obs_date).days),
                "magnitude_ratio": float(g.loc[i, "cusecs"] / obs.loc[y, "discharge_cusecs"]),
            }
        )
    return pd.DataFrame(rows)


def live_test(predicted_cusecs: pd.Series, observed_cusecs: pd.Series) -> dict:
    df = pd.DataFrame({"pred": predicted_cusecs, "obs": observed_cusecs}).dropna()
    if len(df) < 3:
        return {"n": int(len(df)), "note": "too few days"}
    r = (
        float(np.corrcoef(df["pred"], df["obs"])[0, 1])
        if df["obs"].std() > 0 and df["pred"].std() > 0
        else float("nan")
    )
    return {
        "n": int(len(df)),
        "bias_pct": float((df["pred"].mean() - df["obs"].mean()) / df["obs"].mean() * 100),
        "pearson_r": r,
        "mae_cusecs": float((df["pred"] - df["obs"]).abs().mean()),
        "mean_obs_cusecs": float(df["obs"].mean()),
        "mean_pred_cusecs": float(df["pred"].mean()),
    }


def qpf_skill(
    qpf_leads: pd.DataFrame, rain_daily: pd.DataFrame, heavy_mm: float = 30.0
) -> pd.DataFrame:
    """As-issued catchment QPF against the observed catchment rain, per catchment, model and
    lead: bias, Pearson r, MAE, and hit rate and false-alarm ratio for heavy days
    (observed or forecast at or above ``heavy_mm``). Only the days both series have."""
    obs = rain_daily.copy()
    obs["date"] = pd.to_datetime(obs["date"])
    obs = obs.rename(columns={"date": "target_date", "rain_mm": "obs_mm"})[
        ["target_date", "catchment", "obs_mm"]
    ]
    q = qpf_leads.copy()
    q["target_date"] = pd.to_datetime(q["target_date"])
    df = q.merge(obs, on=["target_date", "catchment"], how="inner").dropna(
        subset=["rain_mm", "obs_mm"]
    )
    rows = []
    for (cat, model, lead), g in df.groupby(["catchment", "model", "lead_days"]):
        n = len(g)
        if n < 20:
            continue
        f, o = g["rain_mm"].to_numpy(), g["obs_mm"].to_numpy()
        hits = int(((f >= heavy_mm) & (o >= heavy_mm)).sum())
        misses = int(((f < heavy_mm) & (o >= heavy_mm)).sum())
        false_alarms = int(((f >= heavy_mm) & (o < heavy_mm)).sum())
        rows.append(
            {
                "catchment": cat,
                "model": model,
                "lead_days": int(lead),
                "n_days": n,
                "obs_mean_mm": float(o.mean()),
                "fc_mean_mm": float(f.mean()),
                "bias_pct": float((f.mean() - o.mean()) / o.mean() * 100)
                if o.mean() > 0
                else float("nan"),
                "pearson_r": float(np.corrcoef(f, o)[0, 1])
                if f.std() > 0 and o.std() > 0
                else float("nan"),
                "mae_mm": float(np.abs(f - o).mean()),
                "heavy_days_obs": hits + misses,
                "hit_rate": hits / (hits + misses) if hits + misses else float("nan"),
                "false_alarm_ratio": false_alarms / (hits + false_alarms)
                if hits + false_alarms
                else float("nan"),
            }
        )
    return pd.DataFrame(rows)


def routed_forced_release(pp: pd.DataFrame, dam: str) -> pd.DataFrame:
    """Route the horizon-peak forced release placed at the issue date. This is an envelope
    (the largest daily spill the next ``horizon_days`` could force, shown as early as it can
    be known), not a timing estimate; use ``routed_next_day_release`` for timing."""
    s = pp[pp["dam"] == dam].set_index("date")["peak_release_cusecs"].sort_index()
    return routing.arrivals({dam: s})


def routed_next_day_release(pp: pd.DataFrame, dam: str) -> pd.DataFrame:
    """Route the perfect-prog forced release placed on the day it happens: the release on
    day d+1 is the first-day forced spill of the run issued on day d (today's storage,
    tomorrow's observed rain).

    Only the forced spill is routed. Turbine passage also reaches the river in part
    (Bhakra: passage minus the Nangal canal draw; Pong: passage minus the Shah Nehar
    diversion, whose capacity is not in the sourced constants), so the routed series is a
    lower bound on the river release of a full reservoir, for both dams."""
    g = pp[pp["dam"] == dam].copy()
    g["date"] = pd.to_datetime(g["date"]) + pd.Timedelta(days=1)
    s = g.set_index("date")["release_day1_cusecs"].sort_index()
    full = pd.date_range(s.index.min(), s.index.max(), freq="D")
    s = s.reindex(full).fillna(0.0)
    return routing.arrivals({dam: s})


def write_json(obj, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=_json_default), encoding="utf-8")


def _json_default(o):
    if isinstance(o, np.integer | np.floating):
        return o.item()
    if isinstance(o, pd.Timestamp):
        return o.isoformat()
    return str(o)
