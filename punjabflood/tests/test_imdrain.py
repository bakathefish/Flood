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
