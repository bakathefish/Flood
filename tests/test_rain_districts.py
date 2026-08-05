# tests/test_rain_districts.py
import numpy as np
import pandas as pd
import pytest

from sailaab.rain_districts import (
    build_cell_weights,
    apply_weights,
    district_daily_frame,
    district_window_table,
    add_api,
)

# A 0.25 deg grid centred so that cell centres sit at 30.0, 30.25, ... and
# 75.0, 75.25, ... Each cell spans centre +/- 0.125.
LATS = np.array([30.0, 30.25, 30.5])
LONS = np.array([75.0, 75.25, 75.5])
CELL = 0.25


def _box(lon0, lat0, lon1, lat1):
    """GeoJSON-style polygon ring for an axis-aligned box."""
    return {
        "type": "Polygon",
        "coordinates": [
            [[lon0, lat0], [lon1, lat0], [lon1, lat1], [lon0, lat1], [lon0, lat0]]
        ],
    }


# --- build_cell_weights -------------------------------------------------------
def test_district_inside_one_cell_gets_all_weight():
    # A tiny box wholly inside the cell centred at (30.0, 75.0)
    polys = {"A": _box(74.95, 29.95, 75.05, 30.05)}
    w = build_cell_weights(LATS, LONS, polys, cell_deg=CELL)
    assert set(w) == {"A"}
    idx, wt = w["A"]
    assert len(idx) == 1
    assert idx[0] == (0, 0)
    assert wt[0] == pytest.approx(1.0)


def test_district_split_evenly_across_two_cells():
    # Box spanning exactly half of cell (30.0,75.0) and half of (30.0,75.25),
    # symmetric about the 75.125 cell boundary at constant latitude.
    polys = {"A": _box(75.075, 29.95, 75.175, 30.05)}
    w = build_cell_weights(LATS, LONS, polys, cell_deg=CELL)
    idx, wt = w["A"]
    assert len(idx) == 2
    assert wt == pytest.approx([0.5, 0.5], abs=1e-6)


def test_weights_sum_to_one_per_district():
    polys = {
        "A": _box(74.9, 29.9, 75.3, 30.3),
        "B": _box(75.2, 30.2, 75.7, 30.7),
    }
    w = build_cell_weights(LATS, LONS, polys, cell_deg=CELL)
    for name, (idx, wt) in w.items():
        assert wt.sum() == pytest.approx(1.0), name


def test_weights_are_area_proportional_not_cell_counts():
    # Box covering all of cell (0,0) and only a thin sliver of cell (0,1).
    polys = {"A": _box(74.875, 29.875, 75.155, 30.125)}
    idx, wt = build_cell_weights(LATS, LONS, polys, cell_deg=CELL)["A"]
    order = {tuple(i): float(x) for i, x in zip(idx, wt)}
    assert order[(0, 0)] > 0.85
    assert order[(0, 1)] < 0.15


def test_multipolygon_is_supported():
    polys = {
        "A": {
            "type": "MultiPolygon",
            "coordinates": [
                _box(74.95, 29.95, 75.05, 30.05)["coordinates"],
                _box(75.20, 29.95, 75.30, 30.05)["coordinates"],
            ],
        }
    }
    idx, wt = build_cell_weights(LATS, LONS, polys, cell_deg=CELL)["A"]
    assert len(idx) == 2
    assert wt.sum() == pytest.approx(1.0)


def test_district_outside_grid_raises():
    polys = {"A": _box(10.0, 10.0, 10.1, 10.1)}
    with pytest.raises(ValueError, match="no overlapping grid cells"):
        build_cell_weights(LATS, LONS, polys, cell_deg=CELL)


def test_higher_latitude_cells_are_area_downweighted():
    # Two cells of equal degree-extent at different latitudes contribute
    # cos(lat)-scaled area, so the lower-latitude cell carries more weight.
    lats = np.array([10.0, 60.0])
    lons = np.array([75.0])
    polys = {"A": _box(74.875, 9.875, 75.125, 60.125)}
    idx, wt = build_cell_weights(lats, lons, polys, cell_deg=CELL)["A"]
    by = {tuple(i): float(x) for i, x in zip(idx, wt)}
    assert by[(0, 0)] > by[(1, 0)]


# --- apply_weights ------------------------------------------------------------
def test_apply_weights_is_a_weighted_mean():
    grid = np.array([[10.0, 20.0, 0.0], [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]])
    idx = np.array([(0, 0), (0, 1)])
    wt = np.array([0.25, 0.75])
    assert apply_weights(grid, idx, wt) == pytest.approx(0.25 * 10 + 0.75 * 20)


def test_apply_weights_renormalises_over_valid_cells():
    # One cell is no-data; the result must be the mean over the cells that
    # remain, not a value diluted toward zero by the missing cell.
    grid = np.full((3, 3), np.nan)
    grid[0, 0] = 10.0
    idx = np.array([(0, 0), (0, 1)])
    wt = np.array([0.5, 0.5])
    assert apply_weights(grid, idx, wt) == pytest.approx(10.0)


def test_apply_weights_all_missing_is_nan():
    grid = np.full((3, 3), np.nan)
    idx = np.array([(0, 0), (0, 1)])
    wt = np.array([0.5, 0.5])
    assert np.isnan(apply_weights(grid, idx, wt))


# --- district_daily_frame -----------------------------------------------------
def test_district_daily_frame_shape_and_values():
    dates = pd.to_datetime(["2020-06-15", "2020-06-16"])
    cube = np.zeros((2, 3, 3))
    cube[0, 0, 0] = 5.0
    cube[1, 0, 0] = 7.0
    weights = {"A": (np.array([(0, 0)]), np.array([1.0]))}
    out = district_daily_frame(dates, cube, weights)
    assert list(out.columns) == ["date", "district", "rain_mm"]
    assert len(out) == 2
    assert out.loc[out["date"] == "2020-06-15", "rain_mm"].iloc[0] == pytest.approx(5.0)
    assert out.loc[out["date"] == "2020-06-16", "rain_mm"].iloc[0] == pytest.approx(7.0)


def test_district_daily_frame_rejects_length_mismatch():
    dates = pd.to_datetime(["2020-06-15"])
    cube = np.zeros((2, 3, 3))
    weights = {"A": (np.array([(0, 0)]), np.array([1.0]))}
    with pytest.raises(ValueError, match="length"):
        district_daily_frame(dates, cube, weights)


# --- district_window_table ----------------------------------------------------
def _daily_two_districts(days=60, start="2020-07-20"):
    dates = pd.date_range(start, periods=days, freq="D")
    rows = []
    for d in dates:
        rows.append({"date": d.strftime("%Y-%m-%d"), "district": "A", "rain_mm": 1.0})
        rows.append({"date": d.strftime("%Y-%m-%d"), "district": "B", "rain_mm": 3.0})
    return pd.DataFrame(rows)


def test_district_window_table_sums_per_district():
    daily = _daily_two_districts()
    out = district_window_table(daily, [("2020-07-25", "2020-08-04")], lags=0)
    a = out[out["district"] == "A"]["district_mm"].iloc[0]
    b = out[out["district"] == "B"]["district_mm"].iloc[0]
    assert a == pytest.approx(10.0)  # 10 days x 1.0
    assert b == pytest.approx(30.0)


def test_district_window_table_lags_are_previous_windows():
    daily = _daily_two_districts(days=60, start="2020-07-05")
    out = district_window_table(daily, [("2020-07-25", "2020-08-04")], lags=2)
    row = out[out["district"] == "A"].iloc[0]
    assert row["district_mm"] == pytest.approx(10.0)
    assert row["district_mm_lag1"] == pytest.approx(10.0)  # Jul 15 - Jul 25
    assert row["district_mm_lag2"] == pytest.approx(10.0)  # Jul 05 - Jul 15


def test_district_window_table_lag_before_record_is_nan():
    daily = _daily_two_districts(days=20, start="2020-07-25")
    out = district_window_table(daily, [("2020-07-25", "2020-08-04")], lags=1)
    assert np.isnan(out[out["district"] == "A"]["district_mm_lag1"].iloc[0])


def test_district_window_table_varies_across_districts():
    # The whole point of this module: within one window the value must differ
    # between districts. The two-box statewide predictor could not do this.
    daily = _daily_two_districts()
    out = district_window_table(daily, [("2020-07-25", "2020-08-04")], lags=0)
    assert out["district_mm"].nunique() == 2


# --- add_api ------------------------------------------------------------------
def test_api_decays_previous_rain():
    daily = pd.DataFrame(
        {
            "date": ["2020-07-01", "2020-07-02", "2020-07-03"],
            "district": ["A", "A", "A"],
            "rain_mm": [100.0, 0.0, 0.0],
        }
    )
    out = add_api(daily, k=0.9)
    v = out.sort_values("date")["api_mm"].tolist()
    assert v[0] == pytest.approx(100.0)
    assert v[1] == pytest.approx(90.0)
    assert v[2] == pytest.approx(81.0)


def test_api_is_computed_per_district_independently():
    daily = pd.DataFrame(
        {
            "date": ["2020-07-01", "2020-07-01", "2020-07-02", "2020-07-02"],
            "district": ["A", "B", "A", "B"],
            "rain_mm": [100.0, 0.0, 0.0, 0.0],
        }
    )
    out = add_api(daily, k=0.9)
    b = out[(out["district"] == "B") & (out["date"] == "2020-07-02")]["api_mm"].iloc[0]
    assert b == pytest.approx(0.0)


def test_api_rejects_bad_k():
    daily = pd.DataFrame({"date": ["2020-07-01"], "district": ["A"], "rain_mm": [1.0]})
    with pytest.raises(ValueError, match="k must be"):
        add_api(daily, k=1.5)
