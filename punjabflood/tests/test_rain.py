from __future__ import annotations

import numpy as np
import pandas as pd
from shapely.geometry import box

from punjabflood import catchments, rain


def test_weighted_mean_handles_missing_points_by_renormalising():
    idx = pd.to_datetime(["2023-08-10", "2023-08-11", "2023-08-12"])
    values = pd.DataFrame({"a": [10.0, 10.0, np.nan], "b": [20.0, np.nan, np.nan]}, index=idx)
    weights = pd.Series({"a": 1.0, "b": 3.0})
    out = rain.weighted_mean(values, weights)
    assert out.iloc[0] == 17.5  # (10*1 + 20*3) / 4
    assert out.iloc[1] == 10.0  # b missing: renormalised to a alone, not zero-filled
    assert np.isnan(out.iloc[2])


def _toy_catchment():
    poly = box(76.0, 31.0, 76.5, 31.25)
    pts = catchments.sample_grid(poly)
    return catchments.Catchment(
        "Toy", 1, poly, catchments.geodesic_area_km2(poly), frozenset({1}), pts
    )


class FakeClient:
    """Serves deterministic per-point data so the weighted means can be checked by hand."""

    def __init__(self):
        self.calls = []

    def archive_daily(self, lat, lon, start, end, daily=("precipitation_sum",)):
        self.calls.append(("archive", lat, lon, start, end, tuple(daily)))
        days = pd.date_range(start, end, freq="D")
        d = {"time": [x.date().isoformat() for x in days]}
        for k in daily:
            if k == "precipitation_sum":
                d[k] = [float(lat) for _ in days]
            elif k == "soil_moisture_0_to_7cm_mean":
                d[k] = [0.3 for _ in days]
            else:
                d[k] = [0.35 for _ in days]
        return {"daily": d}

    def forecast_daily(self, lat, lon, models, days, issue_date=None, past_days=0):
        t = pd.date_range("2026-09-06", periods=days, freq="D")
        d = {"time": [x.date().isoformat() for x in t]}
        for m in models:
            d[f"precipitation_sum_{m}"] = [float(lon) if m == "gfs_seamless" else 1.0 for _ in t]
        return {"daily": d}

    def ensemble_daily(self, lat, lon, model, days, issue_date=None):
        t = pd.date_range("2026-09-06", periods=days, freq="D")
        d = {"time": [x.date().isoformat() for x in t], "precipitation_sum": [1.0] * days}
        for k in range(1, 4):
            d[f"precipitation_sum_member{k:02d}"] = [float(k)] * days
        return {"daily": d}

    def previous_runs_hourly(self, lat, lon, model, start, end, leads):
        hours = pd.date_range(start, pd.Timestamp(end) + pd.Timedelta(hours=23), freq="h")
        h = {"time": [x.isoformat() for x in hours], "precipitation": [0.5] * len(hours)}
        for n in leads:
            vals = [float(n)] * len(hours)
            if n == 3:
                vals[5] = None  # one missing hour on the first day breaks that day's sum
            h[f"precipitation_previous_day{n}"] = vals
        return {"hourly": h}


def test_era5_catchment_daily_is_the_area_weighted_mean_and_chunks_years():
    cat = _toy_catchment()
    cli = FakeClient()
    df = rain.era5_catchment_daily(
        cli,
        cat,
        "1999-12-30",
        "2000-01-02",
        years_per_chunk=1,
        daily=("precipitation_sum", "soil_moisture_0_to_7cm_mean", "soil_moisture_7_to_28cm_mean"),
    )
    assert list(df.columns) == [
        "date",
        "rain_mm",
        "n_points",
        "sm_0_7",
        "sm_7_28",
        "catchment",
        "area_km2_covered",
        "source",
    ]
    assert len(df) == 4
    expected = (cat.points.lat * cat.points.weight_km2).sum() / cat.points.weight_km2.sum()
    assert abs(df["rain_mm"].iloc[0] - expected) < 1e-9
    assert (df["n_points"] == len(cat.points)).all()
    assert df["area_km2_covered"].iloc[0] == cat.points.weight_km2.sum()
    # two chunks per point: 1999 and 2000
    assert len(cli.calls) == 2 * len(cat.points)


def test_zero_weight_points_are_not_requested():
    cat = _toy_catchment()
    cat.points["weight_imd_km2"] = cat.points["weight_km2"]
    cat.points.loc[cat.points.index[0], "weight_imd_km2"] = 0.0
    cli = FakeClient()
    df = rain.era5_catchment_daily(
        cli, cat, "2000-01-01", "2000-01-02", weight_col="weight_imd_km2"
    )
    assert len(cli.calls) == len(cat.points) - 1
    assert (df["n_points"] == len(cat.points) - 1).all()
    assert df["area_km2_covered"].iloc[0] == cat.points["weight_imd_km2"].sum()


def test_forecast_and_ensemble_catchment_shapes():
    cat = _toy_catchment()
    cli = FakeClient()
    det = rain.forecast_catchment(cli, cat, models=("gfs_seamless", "ecmwf_ifs025"), days=3)
    assert set(det["model"]) == {"gfs_seamless", "ecmwf_ifs025"}
    assert len(det) == 6
    gfs = det[det.model == "gfs_seamless"]["rain_mm"].iloc[0]
    expected = (cat.points.lon * cat.points.weight_km2).sum() / cat.points.weight_km2.sum()
    assert abs(gfs - expected) < 1e-9
    ens = rain.ensemble_catchment(cli, cat, days=2)
    assert sorted(ens["member"].unique()) == [0, 1, 2, 3]
    q = rain.ensemble_quantiles(ens)
    assert list(q.columns) == ["target_date", "q10", "q50", "q90", "mean", "n_members"]
    assert (q["n_members"] == 4).all()


def test_archived_leads_daily_sums_and_incomplete_days():
    cat = _toy_catchment()
    cli = FakeClient()
    df = rain.archived_leads_catchment(
        cli, cat, "gfs_seamless", "2025-08-25", "2025-08-26", leads=(1, 3)
    )
    assert sorted(df["lead_days"].unique()) == [0, 1, 3]
    lead1 = df[(df.lead_days == 1)].sort_values("target_date")
    assert np.allclose(lead1["rain_mm"], 24.0)  # 24 hours x 1.0 mm
    lead3 = df[(df.lead_days == 3)].sort_values("target_date")
    assert np.isnan(lead3["rain_mm"].iloc[0])  # a missing hour voids the day
    assert lead3["rain_mm"].iloc[1] == 72.0
