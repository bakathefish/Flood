# tests/test_frequency.py
import numpy as np
import pytest

from sailaab.frequency import (
    window_index,
    frequency_count,
    classify_frequency,
    summarize_repeat_victims,
)


# --- window_index: which half-open [start, end) window a day falls in ---------

WINDOWS = [
    ("2023-06-15", "2023-06-25"),
    ("2023-06-25", "2023-07-05"),
    ("2023-08-14", "2023-08-24"),  # (non-contiguous on purpose for the test)
]


def test_window_index_inside():
    assert window_index("2023-06-20", WINDOWS) == 0
    assert window_index("2023-08-18", WINDOWS) == 2


def test_window_index_start_inclusive():
    assert window_index("2023-06-15", WINDOWS) == 0
    assert window_index("2023-08-14", WINDOWS) == 2


def test_window_index_end_exclusive():
    # 06-25 is the end of window 0 and the start of window 1 -> belongs to 1.
    assert window_index("2023-06-25", WINDOWS) == 1
    # 08-24 is the (exclusive) end of the last window -> outside.
    assert window_index("2023-08-24", WINDOWS) is None


def test_window_index_outside_returns_none():
    assert window_index("2023-06-14", WINDOWS) is None
    assert window_index("2023-07-10", WINDOWS) is None  # gap between windows
    assert window_index("2023-12-01", WINDOWS) is None


# --- frequency_count: per-pixel count of True across a season-mask stack ------


def test_frequency_count_sums_stack():
    a = np.array([[1, 0], [1, 0]], bool)
    b = np.array([[1, 1], [0, 0]], bool)
    c = np.array([[0, 1], [1, 0]], bool)
    out = frequency_count([a, b, c])
    assert out.tolist() == [[2, 2], [2, 0]]
    assert out.dtype == np.dtype("int32") or np.issubdtype(out.dtype, np.integer)


def test_frequency_count_single_mask():
    a = np.array([[1, 0]], bool)
    assert frequency_count([a]).tolist() == [[1, 0]]


def test_frequency_count_empty_raises():
    with pytest.raises(ValueError):
        frequency_count([])


def test_frequency_count_shape_mismatch_raises():
    with pytest.raises(ValueError):
        frequency_count([np.zeros((2, 2), bool), np.zeros((2, 3), bool)])


# --- classify_frequency: recurrence classes for the legend --------------------


def test_classify_frequency_default_edges():
    # edges (1,2,4): 0->0 (none), 1->1 (1x), 2..3->2 (2-3x), >=4->3 (>=4x)
    freq = np.array([[0, 1, 2], [3, 4, 11]])
    out = classify_frequency(freq)
    assert out.tolist() == [[0, 1, 2], [2, 3, 3]]


def test_classify_frequency_custom_edges():
    freq = np.array([0, 1, 2, 3, 5])
    out = classify_frequency(freq, edges=(1, 3))
    # count>=1 ->1, count>=3 -> 2
    assert out.tolist() == [0, 1, 1, 2, 2]


# --- summarize_repeat_victims: per-district recurrence table ------------------


def test_summarize_repeat_victims_counts_and_stats():
    per_season = {
        "Sangrur": [
            {"fraction": 0.0, "flooded_ha": 0.0},
            {"fraction": 0.005, "flooded_ha": 50.0},
            {"fraction": 0.015, "flooded_ha": 150.0},
            {"fraction": 0.03, "flooded_ha": 300.0},
        ],
        "Dry": [
            {"fraction": 0.0, "flooded_ha": 0.0},
            {"fraction": 0.001, "flooded_ha": 10.0},
        ],
    }
    out = summarize_repeat_victims(per_season)
    s = out["Sangrur"]
    assert s["seasons_with_fraction_gt1pct"] == 2  # 0.015, 0.03
    assert s["seasons_with_fraction_gt2pct"] == 1  # 0.03
    assert s["max_season_fraction"] == pytest.approx(0.03)
    assert s["mean_annual_flooded_ha"] == pytest.approx(125.0)  # (0+50+150+300)/4
    assert s["n_seasons"] == 4
    d = out["Dry"]
    assert d["seasons_with_fraction_gt1pct"] == 0
    assert d["seasons_with_fraction_gt2pct"] == 0
    assert d["max_season_fraction"] == pytest.approx(0.001)
    assert d["mean_annual_flooded_ha"] == pytest.approx(5.0)


def test_summarize_repeat_victims_custom_thresholds():
    per_season = {"X": [{"fraction": 0.04, "flooded_ha": 400.0}]}
    out = summarize_repeat_victims(per_season, thresholds=(0.03, 0.05))
    assert out["X"]["seasons_with_fraction_gt1pct"] == 1  # >0.03
    assert out["X"]["seasons_with_fraction_gt2pct"] == 0  # not >0.05


def test_summarize_repeat_victims_empty_seasons():
    out = summarize_repeat_victims({"Z": []})
    z = out["Z"]
    assert z["n_seasons"] == 0
    assert z["max_season_fraction"] == 0.0
    assert z["mean_annual_flooded_ha"] == 0.0
    assert z["seasons_with_fraction_gt1pct"] == 0
