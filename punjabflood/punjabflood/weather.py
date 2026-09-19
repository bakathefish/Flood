"""Weather watch: the rain that is falling and the rain that is forecast, per catchment,
placed against the observed record, with the level the watch stands at.

The hazard index answers "must the spillway open". This module answers the question that
comes before it: is the weather over the catchments ordinary, worth watching, or the kind
that has filled the dams before? It reads only what the product already pulls (the observed
days, the deterministic models, the IFS ensemble) plus one more daily call per point for
the primary model's temperature and snowfall, and it never touches the inflow model.

Levels, written down before any season was scored:

* ``alert``: the ensemble median of the next three days' rain sits at or above the 90th
  percentile of the record's monsoon three-day totals, or at least half the members put a
  heavy day (``HEAVY_MM`` or more) inside the next three days. Without an ensemble, the
  primary model's three-day total at or above the 90th percentile, or a majority of the
  deterministic models with a heavy day.
* ``watch``: the median (or primary model) at or above the 75th percentile, or a quarter of
  the members with a heavy day, or any deterministic model with a heavy day.
* ``quiet``: everything else.

The record is the Jun-Sep three-day totals of the IMD grid over the same catchment
(``season_3day_climatology``), the same distribution the Ghaggar index has used since the
first release, now kept for every catchment.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

HEAVY_MM = 30.0
WATCH_DAYS = 3
ALERT_PCT = 90.0
WATCH_PCT = 75.0
ALERT_MEMBER_SHARE = 0.5
WATCH_MEMBER_SHARE = 0.25
SEASON_MONTHS = (6, 7, 8, 9)
SNOW_CM_TO_MM_WATER = 10.0 / 7.0  # Open-Meteo's snowfall is cm of snow, 7 cm of snow per 10 mm of water


def season_3day_climatology(
    rain_daily: pd.DataFrame, catchments=None, months=SEASON_MONTHS
) -> dict[str, np.ndarray]:
    """Monsoon three-day rain totals per catchment from the observed record (every catchment
    in ``rain_daily`` unless ``catchments`` names some)."""
    out = {}
    names = list(catchments) if catchments is not None else sorted(rain_daily["catchment"].unique())
    for cat in names:
        g = rain_daily[rain_daily["catchment"] == cat].copy()
        if g.empty:
            continue
        g["date"] = pd.to_datetime(g["date"])
        s = g.set_index("date")["rain_mm"].astype(float).sort_index().rolling(3).sum()
        out[cat] = s[s.index.month.isin(list(months))].dropna().to_numpy()
    return out


def percentile_of(clim: np.ndarray | None, value: float) -> float | None:
    """Where ``value`` falls in the record: the share of recorded totals below it, in
    percent. None without a record."""
    if clim is None or len(clim) == 0 or value != value:
        return None
    return float((np.asarray(clim, dtype=float) < value).mean() * 100)


def snow_share(precipitation_mm: np.ndarray, snowfall_cm: np.ndarray) -> np.ndarray:
    """The share of each day's precipitation that falls as snow (water equivalent of the
    snowfall over the precipitation), 0 on a dry day, capped at 1."""
    p = np.asarray(precipitation_mm, dtype=float)
    s = np.asarray(snowfall_cm, dtype=float) * SNOW_CM_TO_MM_WATER
    with np.errstate(divide="ignore", invalid="ignore"):
        share = np.where(p > 0, s / p, 0.0)
    return np.clip(np.nan_to_num(share), 0.0, 1.0)


def level(
    pct_median: float | None,
    member_heavy_share: float | None,
    det_heavy_share: float | None,
    has_ensemble: bool,
) -> str:
    """The watch level from the rules in the module docstring."""
    pct = -1.0 if pct_median is None else pct_median
    if has_ensemble:
        mh = member_heavy_share or 0.0
        if pct >= ALERT_PCT or mh >= ALERT_MEMBER_SHARE:
            return "alert"
        if pct >= WATCH_PCT or mh >= WATCH_MEMBER_SHARE or (det_heavy_share or 0.0) > 0:
            return "watch"
        return "quiet"
    dh = det_heavy_share or 0.0
    if pct >= ALERT_PCT or dh > 0.5:
        return "alert"
    if pct >= WATCH_PCT or dh > 0:
        return "watch"
    return "quiet"


def _det_by_model(qpf_det: pd.DataFrame, cat: str, days: int) -> dict[str, np.ndarray]:
    g = qpf_det[qpf_det["catchment"] == cat]
    out = {}
    for m, gm in g.groupby("model"):
        v = gm.sort_values("target_date")["rain_mm"].to_numpy(dtype=float)[:days]
        if len(v):
            out[str(m)] = v
    return out


def _members(qpf_ens: pd.DataFrame, cat: str, days: int) -> dict[int, np.ndarray]:
    g = qpf_ens[qpf_ens["catchment"] == cat] if len(qpf_ens) else qpf_ens
    out = {}
    for m, gm in g.groupby("member"):
        v = gm.sort_values("target_date")["rain_mm"].to_numpy(dtype=float)[:days]
        if len(v):
            out[int(m)] = v
    return out


def weather_watch(
    issue_date: str,
    qpf_det: pd.DataFrame,
    qpf_ens: pd.DataFrame,
    recent_rain: dict[str, list[float]],
    recent_sources: dict[str, list[str]] | None,
    climatology: dict[str, np.ndarray] | None,
    primary_model: str,
    weather_daily: pd.DataFrame | None = None,
    horizon_days: int = 5,
    watch_days: int = WATCH_DAYS,
    heavy_mm: float = HEAVY_MM,
) -> dict[str, dict]:
    """One entry per catchment that has a deterministic forecast: what fell, what every
    model says, what the ensemble spreads over, where the next ``watch_days`` sit in the
    record, and the level. ``weather_daily`` (columns ``catchment, target_date,
    precipitation_mm, snowfall_cm, t2m_max_c, t2m_mean_c``) adds the primary model's
    temperature and the share of the precipitation falling as snow, where it has them."""
    clim = climatology or {}
    issue = pd.Timestamp(issue_date)
    out: dict[str, dict] = {}
    for cat in sorted(qpf_det["catchment"].unique()):
        det = _det_by_model(qpf_det, cat, horizon_days)
        if not det:
            continue
        model = primary_model if primary_model in det else next(iter(det))
        three = {m: float(v[:watch_days].sum()) for m, v in det.items()}
        c = clim.get(cat)
        pct = {m: percentile_of(c, v) for m, v in three.items()}
        det_heavy = {m: bool((v[:watch_days] >= heavy_mm).any()) for m, v in det.items()}
        det_heavy_share = sum(det_heavy.values()) / len(det_heavy)
        recent = [float(x) for x in recent_rain.get(cat, [])]
        srcs = list((recent_sources or {}).get(cat, []))
        entry = {
            "level": "quiet",
            "watch_days": int(watch_days),
            "heavy_mm": float(heavy_mm),
            "primary_model": model,
            "observed": {
                "days": [
                    (issue - pd.Timedelta(days=k)).date().isoformat()
                    for k in range(len(recent), 0, -1)
                ],
                "rain_mm": recent,
                "sources": srcs,
                "total_mm": float(sum(recent)),
            },
            "forecast": {
                "dates": [
                    (issue + pd.Timedelta(days=k)).date().isoformat()
                    for k in range(1, horizon_days + 1)
                ],
                "by_model_mm": {m: [float(x) for x in v] for m, v in det.items()},
                "three_day_mm": three,
                "three_day_percentile": pct,
                "heavy_day_by_model": det_heavy,
                "models_with_heavy_day": float(det_heavy_share),
            },
            "record_n_days": int(len(c)) if c is not None else 0,
        }
        members = _members(qpf_ens, cat, horizon_days) if len(qpf_ens) else {}
        pct_median = pct.get(model)
        member_heavy_share = None
        if members:
            arr = np.array([v for v in members.values() if len(v) >= watch_days])
            if len(arr):
                totals = arr[:, :watch_days].sum(axis=1)
                member_heavy_share = float((arr[:, :watch_days] >= heavy_mm).any(axis=1).mean())
                q10, q50, q90 = (float(np.quantile(totals, q)) for q in (0.1, 0.5, 0.9))
                pct_median = percentile_of(c, q50)
                entry["ensemble"] = {
                    "n_members": int(len(arr)),
                    "three_day_q10_mm": q10,
                    "three_day_q50_mm": q50,
                    "three_day_q90_mm": q90,
                    "three_day_q50_percentile": pct_median,
                    "p_heavy_day": member_heavy_share,
                    "daily_q50_mm": [float(x) for x in np.quantile(arr, 0.5, axis=0)],
                    "daily_q90_mm": [float(x) for x in np.quantile(arr, 0.9, axis=0)],
                }
        entry["level"] = level(pct_median, member_heavy_share, det_heavy_share, bool(members))
        entry["level_basis"] = {
            "three_day_percentile": pct_median,
            "member_share_with_heavy_day": member_heavy_share,
            "models_with_heavy_day": float(det_heavy_share),
        }
        if weather_daily is not None and len(weather_daily):
            w = weather_daily[weather_daily["catchment"] == cat].sort_values("target_date")
            w = w[pd.to_datetime(w["target_date"]) > issue].head(horizon_days)
            if len(w):
                share = snow_share(w["precipitation_mm"].to_numpy(), w["snowfall_cm"].to_numpy())
                entry["temperature"] = {
                    "model": str(w["model"].iloc[0]) if "model" in w else model,
                    "t2m_max_c": [float(x) for x in w["t2m_max_c"]],
                    "t2m_mean_c": [float(x) for x in w["t2m_mean_c"]],
                    "snowfall_cm": [float(x) for x in w["snowfall_cm"]],
                    "snow_share": [float(x) for x in share],
                    "snow_share_3day": float(
                        snow_share(
                            np.array([w["precipitation_mm"].head(watch_days).sum()]),
                            np.array([w["snowfall_cm"].head(watch_days).sum()]),
                        )[0]
                    ),
                }
        out[cat] = entry
    return out


def summary_rows(watch: dict[str, dict]) -> list[dict]:
    """Flat rows for a table or a figure: one per catchment."""
    rows = []
    for cat, e in watch.items():
        ens = e.get("ensemble") or {}
        m = e["primary_model"]
        rows.append(
            {
                "catchment": cat,
                "level": e["level"],
                "observed_total_mm": e["observed"]["total_mm"],
                "primary_3day_mm": e["forecast"]["three_day_mm"].get(m),
                "primary_3day_percentile": e["forecast"]["three_day_percentile"].get(m),
                "ens_3day_q10_mm": ens.get("three_day_q10_mm"),
                "ens_3day_q50_mm": ens.get("three_day_q50_mm"),
                "ens_3day_q90_mm": ens.get("three_day_q90_mm"),
                "p_heavy_day": ens.get("p_heavy_day"),
                "models_with_heavy_day": e["forecast"]["models_with_heavy_day"],
                "snow_share_3day": (e.get("temperature") or {}).get("snow_share_3day"),
            }
        )
    return rows
