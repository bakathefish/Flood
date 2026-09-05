"""Catchment-mean rainfall and soil moisture: observed (ERA5 via Open-Meteo) and forecast
(deterministic, ensemble and archived as-issued leads).

Every series is an area-weighted mean over the catchment's grid points, the weights being
a column of ``catchments.Catchment.points``: ``weight_km2`` (the whole polygon) or
``weight_imd_km2`` (the part the IMD gridded record covers, so that forecasts and the
calibration record share one index). Points with zero weight are not requested. A point
with no value on a day drops out of that day's weights instead of counting as zero.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable

import numpy as np
import pandas as pd

from punjabflood.catchments import Catchment
from punjabflood.openmeteo import OpenMeteo

log = logging.getLogger(__name__)

DEFAULT_LEADS = (1, 2, 3, 4, 5, 6, 7)
WEIGHT_COL = "weight_km2"


def weighted_mean(values: pd.DataFrame, weights: pd.Series) -> pd.Series:
    """Row-wise weighted mean of ``values`` (index = time, columns = point ids) with
    ``weights`` indexed by point id. Missing values are excluded and the weights are
    renormalised over the points present that row; an all-missing row is NaN."""
    w = weights.reindex(values.columns).to_numpy(dtype=float)
    v = values.to_numpy(dtype=float)
    mask = ~np.isnan(v)
    ww = np.where(mask, w[None, :], 0.0)
    denom = ww.sum(axis=1)
    num = np.nansum(v * ww, axis=1)
    out = np.where(denom > 0, num / np.where(denom > 0, denom, 1.0), np.nan)
    return pd.Series(out, index=values.index, name="value")


def _point_id(lat: float, lon: float) -> str:
    return f"{lat:.4f},{lon:.4f}"


def points_with_weights(catchment: Catchment, weight_col: str = WEIGHT_COL):
    """Yield ``(point_id, lat, lon, weight)`` for points with positive weight."""
    col = weight_col if weight_col in catchment.points.columns else WEIGHT_COL
    for row in catchment.points.itertuples(index=False):
        w = float(getattr(row, col))
        if w > 0:
            yield _point_id(row.lat, row.lon), float(row.lat), float(row.lon), w


def _year_chunks(start: str, end: str, years_per_chunk: int) -> list[tuple[str, str]]:
    s = pd.Timestamp(start)
    e = pd.Timestamp(end)
    out = []
    cur = s
    while cur <= e:
        nxt = min(
            pd.Timestamp(year=cur.year + years_per_chunk, month=1, day=1) - pd.Timedelta(days=1), e
        )
        out.append((cur.date().isoformat(), nxt.date().isoformat()))
        cur = nxt + pd.Timedelta(days=1)
    return out


def era5_catchment_daily(
    client: OpenMeteo,
    catchment: Catchment,
    start: str,
    end: str,
    years_per_chunk: int = 10,
    daily: Iterable[str] = ("precipitation_sum",),
    weight_col: str = WEIGHT_COL,
) -> pd.DataFrame:
    """Daily catchment means of the requested archive variables (``precipitation_sum`` ->
    ``rain_mm``, ``soil_moisture_0_to_7cm_mean`` -> ``sm_0_7``, ``soil_moisture_7_to_28cm_mean``
    -> ``sm_7_28``), with ``n_points`` contributing. Open-Meteo weights archive calls by data
    volume, so request only the variables and years you need."""
    daily = list(daily)
    names = {
        "precipitation_sum": "rain_mm",
        "soil_moisture_0_to_7cm_mean": "sm_0_7",
        "soil_moisture_7_to_28cm_mean": "sm_7_28",
    }
    frames: dict[str, dict[str, pd.Series]] = {k: {} for k in daily}
    weights = {}
    for pid, lat, lon, w in points_with_weights(catchment, weight_col):
        weights[pid] = w
        parts = {k: [] for k in daily}
        for s, e in _year_chunks(start, end, years_per_chunk):
            j = client.archive_daily(lat, lon, s, e, daily=daily)
            d = j.get("daily", {})
            idx = pd.to_datetime(d.get("time", []))
            for k in daily:
                parts[k].append(pd.Series(d.get(k, [None] * len(idx)), index=idx, dtype=float))
        for k in daily:
            frames[k][pid] = pd.concat(parts[k]) if parts[k] else pd.Series(dtype=float)
    wser = pd.Series(weights)
    out = pd.DataFrame(index=pd.DatetimeIndex([], name="date"))
    for k in daily:
        df = pd.DataFrame(frames[k])
        df.index.name = "date"
        col = names.get(k, k)
        out = out.join(weighted_mean(df, wser).rename(col), how="outer")
        if k == daily[0]:
            out["n_points"] = df.notna().sum(axis=1).reindex(out.index)
    out.index.name = "date"
    out["catchment"] = catchment.name
    out["area_km2_covered"] = float(wser.sum())
    out["source"] = "era5"
    return out.reset_index()


def forecast_catchment(
    client: OpenMeteo,
    catchment: Catchment,
    models: Iterable[str] = ("gfs_seamless", "ecmwf_ifs025", "icon_seamless", "best_match"),
    days: int = 10,
    issue_date: str | None = None,
    past_days: int = 0,
    weight_col: str = WEIGHT_COL,
) -> pd.DataFrame:
    """Deterministic daily QPF (mm) per model as catchment means:
    columns ``target_date, model, rain_mm, catchment``. ``past_days`` prepends the model's
    analysis of the days already gone (the recent-rain term of the inflow model)."""
    models = list(models)
    per_model: dict[str, dict[str, pd.Series]] = {m: {} for m in models}
    weights = {}
    for pid, lat, lon, w in points_with_weights(catchment, weight_col):
        weights[pid] = w
        j = client.forecast_daily(
            lat, lon, models=models, days=days, issue_date=issue_date, past_days=past_days
        )
        d = j.get("daily", {})
        idx = pd.to_datetime(d.get("time", []))
        for m in models:
            key = f"precipitation_sum_{m}" if len(models) > 1 else "precipitation_sum"
            per_model[m][pid] = pd.Series(d.get(key, [None] * len(idx)), index=idx, dtype=float)
    wser = pd.Series(weights)
    out = []
    for m in models:
        s = weighted_mean(pd.DataFrame(per_model[m]), wser)
        out.append(pd.DataFrame({"target_date": s.index, "model": m, "rain_mm": s.to_numpy()}))
    res = (
        pd.concat(out, ignore_index=True)
        if out
        else pd.DataFrame(columns=["target_date", "model", "rain_mm"])
    )
    res["catchment"] = catchment.name
    return res


def ensemble_catchment(
    client: OpenMeteo,
    catchment: Catchment,
    model: str = "ecmwf_ifs025",
    days: int = 7,
    issue_date: str | None = None,
    weight_col: str = WEIGHT_COL,
) -> pd.DataFrame:
    """Ensemble daily QPF as catchment means: columns ``target_date, member, rain_mm``.
    Member 0 is the control (``precipitation_sum``), members 1..N the perturbed runs."""
    series: dict[int, dict[str, pd.Series]] = {}
    weights = {}
    for pid, lat, lon, w in points_with_weights(catchment, weight_col):
        weights[pid] = w
        j = client.ensemble_daily(lat, lon, model=model, days=days, issue_date=issue_date)
        d = j.get("daily", {})
        idx = pd.to_datetime(d.get("time", []))
        for key, vals in d.items():
            if not key.startswith("precipitation_sum"):
                continue
            member = 0 if key == "precipitation_sum" else int(key.rsplit("member", 1)[1])
            series.setdefault(member, {})[pid] = pd.Series(vals, index=idx, dtype=float)
    wser = pd.Series(weights)
    out = []
    for member in sorted(series):
        s = weighted_mean(pd.DataFrame(series[member]), wser)
        out.append(
            pd.DataFrame({"target_date": s.index, "member": member, "rain_mm": s.to_numpy()})
        )
    res = (
        pd.concat(out, ignore_index=True)
        if out
        else pd.DataFrame(columns=["target_date", "member", "rain_mm"])
    )
    res["catchment"] = catchment.name
    res["model"] = model
    return res


def ensemble_quantiles(ens: pd.DataFrame, qs=(0.1, 0.5, 0.9)) -> pd.DataFrame:
    g = ens.groupby("target_date")["rain_mm"]
    out = pd.DataFrame({f"q{int(q * 100):02d}": g.quantile(q) for q in qs})
    out["mean"] = g.mean()
    out["n_members"] = g.count()
    return out.reset_index()


def archived_leads_catchment(
    client: OpenMeteo,
    catchment: Catchment,
    model: str,
    start: str,
    end: str,
    leads: Iterable[int] = DEFAULT_LEADS,
    weight_col: str = WEIGHT_COL,
) -> pd.DataFrame:
    """As-issued daily QPF by lead from the previous-run archive: for each target day the
    daily sum of the hourly forecast issued ``lead_days`` earlier (lead 0 is the stitched
    shortest-lead series). Columns ``target_date, lead_days, model, rain_mm, catchment``."""
    leads = list(leads)
    per_lead: dict[int, dict[str, pd.Series]] = {0: {}, **{n: {} for n in leads}}
    weights = {}
    for pid, lat, lon, w in points_with_weights(catchment, weight_col):
        weights[pid] = w
        j = client.previous_runs_hourly(lat, lon, model, start, end, leads=leads)
        h = j.get("hourly", {})
        idx = pd.to_datetime(h.get("time", []))
        for n in per_lead:
            key = "precipitation" if n == 0 else f"precipitation_previous_day{n}"
            s = pd.Series(h.get(key, [None] * len(idx)), index=idx, dtype=float)
            # a day counts only if all 24 hours are present
            daily = s.resample("1D").agg(lambda x: x.sum() if x.notna().sum() == 24 else np.nan)
            per_lead[n][pid] = daily
    wser = pd.Series(weights)
    out = []
    for n in per_lead:
        s = weighted_mean(pd.DataFrame(per_lead[n]), wser)
        out.append(
            pd.DataFrame(
                {"target_date": s.index, "lead_days": n, "model": model, "rain_mm": s.to_numpy()}
            )
        )
    res = pd.concat(out, ignore_index=True)
    res["catchment"] = catchment.name
    return res
