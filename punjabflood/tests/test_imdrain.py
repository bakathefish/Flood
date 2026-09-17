from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import xarray as xr
from shapely.geometry import box

from punjabflood import catchments, imdrain

IMD = imdrain.resolve_imd_dir() / "rain" / "2023.grd"


def test_resolve_imd_dir_prefers_env_then_first_existing_archive(tmp_path):
    a = tmp_path / "a"
    b = tmp_path / "b"
    (b / "rain").mkdir(parents=True)
    # the environment variable wins even when it does not exist yet
    assert imdrain.resolve_imd_dir({"PUNJABFLOOD_IMD_DIR": str(tmp_path / "x")}) == tmp_path / "x"
    # otherwise the first candidate that holds a rain folder
    assert imdrain.resolve_imd_dir({}, candidates=(a, b)) == b
    # nothing found: the first candidate, so the error that follows names a path
    assert imdrain.resolve_imd_dir({}, candidates=(a, tmp_path / "c")) == a
    # the package default looks in data/raw/imd first, then the Sailaab archive one level up
    assert [str(c).replace("\\", "/") for c in imdrain.IMD_DIR_CANDIDATES] == [
        "data/raw/imd",
        "../data/rasters/imd",
    ]


def _toy_rain():
    lat = np.arange(30.5, 32.01, 0.25)
    lon = np.arange(75.5, 77.01, 0.25)
    time = pd.date_range("2023-08-10", periods=3)
    data = np.zeros((len(time), len(lat), len(lon)))
    data[:, :, :] = 10.0
    data[:, lat >= 31.5, :] = np.nan  # "outside India" rows
    data[1, :, :] += 5.0
    return xr.DataArray(
        data, coords={"time": time, "lat": lat, "lon": lon}, dims=("time", "lat", "lon")
    )


def _toy_catchment():
    poly = box(75.6, 30.6, 76.9, 31.9)
    pts = catchments.sample_grid(poly)
    return {
        "Toy": catchments.Catchment(
            "Toy", 1, poly, catchments.geodesic_area_km2(poly), frozenset({1}), pts
        )
    }


def test_coverage_mask_and_marking():
    rain = _toy_rain()
    cov = imdrain.coverage_mask(rain)
    assert set(cov["lat"].unique()) == {30.5, 30.75, 31.0, 31.25}
    cats = _toy_catchment()
    imdrain.mark_coverage(cats, cov)
    pts = cats["Toy"].points
    assert imdrain.IMD_WEIGHT_COL in pts.columns
    assert (pts.loc[pts.lat >= 31.5, imdrain.IMD_WEIGHT_COL] == 0).all()
    assert (
        pts.loc[pts.lat < 31.5, imdrain.IMD_WEIGHT_COL] == pts.loc[pts.lat < 31.5, "weight_km2"]
    ).all()
    assert 0 < imdrain.covered_area_km2(cats["Toy"]) < cats["Toy"].area_km2


def test_catchment_daily_from_synthetic_field(monkeypatch):
    rain = _toy_rain()
    cats = _toy_catchment()
    imdrain.mark_coverage(cats, imdrain.coverage_mask(rain))
    monkeypatch.setattr(imdrain, "open_year", lambda year, imd_dir=None: rain)
    df = imdrain.catchment_daily([2023], cats)
    assert list(df.columns) == [
        "date",
        "catchment",
        "rain_mm",
        "n_points",
        "area_km2_covered",
        "source",
    ]
    assert len(df) == 3
    assert df["rain_mm"].tolist() == pytest.approx([10.0, 15.0, 10.0])
    assert df["area_km2_covered"].iloc[0] == pytest.approx(imdrain.covered_area_km2(cats["Toy"]))
    assert (df["n_points"] == (cats["Toy"].points[imdrain.IMD_WEIGHT_COL] > 0).sum()).all()


@pytest.mark.skipif(not IMD.exists(), reason="IMD archive not linked")
def test_real_2023_august_pong_catchment_rain_is_large():
    cats = catchments.load_geojson()
    rain = imdrain.open_year(2023)
    imdrain.mark_coverage(cats, imdrain.coverage_mask(rain))
    df = imdrain.catchment_daily([2023], {"Pong": cats["Pong"]})
    aug = df[(df.date >= "2023-08-12") & (df.date <= "2023-08-15")]
    # the 13 to 14 August 2023 event produced Pong's record inflow (BBMB EAP)
    assert aug["rain_mm"].max() > 50
    assert (df["n_points"] > 20).all()


# --- the real-time grid ------------------------------------------------------------------


def _write_realtime_grid(rt_dir: Path, day: pd.Timestamp, value_at: dict | None = None):
    """One real-time file on the archive lattice: -999 everywhere except the given
    (lat, lon) -> mm entries, written in the service's layout (lat rows, lon columns)."""
    grid = np.full((imdrain.RT_LAT.size, imdrain.RT_LON.size), -999.0, dtype="<f4")
    for (lat, lon), v in (value_at or {}).items():
        grid[np.argmin(np.abs(imdrain.RT_LAT - lat)), np.argmin(np.abs(imdrain.RT_LON - lon))] = v
    rt_dir.mkdir(parents=True, exist_ok=True)
    imdrain.realtime_path(day, rt_dir).write_bytes(grid.tobytes(order="C"))


def test_open_real_days_matches_imdlib_layout_and_skips_missing(tmp_path):
    imdlib = pytest.importorskip("imdlib")
    d1, d2, d3 = pd.date_range("2026-09-10", periods=3)
    _write_realtime_grid(tmp_path, d1, {(31.0, 76.0): 12.5, (32.25, 77.5): 3.0})
    _write_realtime_grid(tmp_path, d3, {(31.0, 76.0): 40.0})
    da = imdrain.open_real_days([d1, d2, d3], tmp_path)
    # the day without a file is not in the array; the others are, in order
    assert list(pd.to_datetime(da["time"].values)) == [d1, d3]
    assert float(da.sel(time=d1, lat=31.0, lon=76.0)) == pytest.approx(12.5)
    assert float(da.sel(time=d1, lat=32.25, lon=77.5)) == pytest.approx(3.0)
    assert float(da.sel(time=d3, lat=31.0, lon=76.0)) == pytest.approx(40.0)
    assert np.isnan(float(da.sel(time=d1, lat=20.0, lon=80.0)))  # no-data is NaN
    # the same file read by imdlib's own reader lands on the same node
    ref = imdlib.open_real_data("rain", d1.date().isoformat(), d1.date().isoformat(), str(tmp_path))
    x = ref.get_xarray()["rain"]
    assert float(x.sel(lat=31.0, lon=76.0, method="nearest").values[0]) == pytest.approx(12.5)
    assert float(x.sel(lat=32.25, lon=77.5, method="nearest").values[0]) == pytest.approx(3.0)
    # nothing on disk: None
    assert imdrain.open_real_days([d2], tmp_path) is None


def test_fetch_realtime_keeps_only_whole_grids_and_skips_files_on_disk(tmp_path):
    d1, d2, d3 = pd.date_range("2026-09-10", periods=3)
    _write_realtime_grid(tmp_path, d1)
    calls = []

    def post(day):
        calls.append(day)
        if day == d2:
            return b"<html>error</html>"
        return np.zeros((imdrain.RT_LAT.size, imdrain.RT_LON.size), dtype="<f4").tobytes()

    present = imdrain.fetch_realtime([d1, d2, d3], tmp_path, post=post)
    assert calls == [d2, d3]  # d1 was on disk
    assert present == [d1, d3]
    assert not imdrain.realtime_path(d2, tmp_path).exists()
    # a fetcher that raises is a missing day, not a crash
    def boom(day):
        raise OSError("no route")

    assert imdrain.fetch_realtime([d2], tmp_path, post=boom) == []


def test_catchment_daily_realtime_equals_the_archive_path_on_the_same_field(tmp_path):
    rain = _toy_rain()
    cats = _toy_catchment()
    imdrain.mark_coverage(cats, imdrain.coverage_mask(rain))
    # write the toy field's three days as real-time files on the full lattice
    for t in rain["time"].values:
        day = pd.Timestamp(t)
        vals = {}
        for la in rain["lat"].values:
            for lo in rain["lon"].values:
                v = float(rain.sel(time=day, lat=la, lon=lo))
                if not np.isnan(v):
                    vals[(float(la), float(lo))] = v
        _write_realtime_grid(tmp_path, day, vals)
    days = pd.to_datetime(rain["time"].values)
    df = imdrain.catchment_daily_realtime(days, cats, tmp_path)
    assert df["source"].unique().tolist() == ["imd_rt"]
    assert df["rain_mm"].tolist() == pytest.approx([10.0, 15.0, 10.0])
    assert (df["n_points"] == (cats["Toy"].points[imdrain.IMD_WEIGHT_COL] > 0).sum()).all()
    # no files: an empty frame with the archive's columns
    empty = imdrain.catchment_daily_realtime(pd.date_range("2030-01-01", periods=2), cats, tmp_path)
    assert list(empty.columns) == list(df.columns) and empty.empty
