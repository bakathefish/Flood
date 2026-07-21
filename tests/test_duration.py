# tests/test_duration.py
import numpy as np
import pytest

from sailaab.duration import (
    day_offsets,
    filter_window,
    days_observed_wet,
    span_duration,
    duration_classes,
    DURATION_CLASS_EDGES,
    DURATION_CLASS_LABELS,
)


# --- day_offsets: ISO day -> integer day number from an origin --------------


def test_day_offsets_basic():
    days = ["2025-08-15", "2025-08-16", "2025-08-18", "2025-09-28"]
    off = day_offsets(days, "2025-08-15")
    assert off.tolist() == [0, 1, 3, 44]
    assert np.issubdtype(off.dtype, np.integer)


def test_day_offsets_origin_after_gives_negative():
    assert day_offsets(["2025-08-14"], "2025-08-15").tolist() == [-1]


# --- filter_window: indices of ISO days inside [start, end] inclusive -------


def test_filter_window_inclusive_bounds():
    days = ["2025-06-16", "2025-08-15", "2025-09-30", "2025-10-01"]
    idx = filter_window(days, "2025-08-15", "2025-09-30")
    assert idx == [1, 2]  # 06-16 dropped (paddy), 10-01 dropped (after)


def test_filter_window_empty():
    assert filter_window(["2025-07-01"], "2025-08-15", "2025-09-30") == []


# --- days_observed_wet: LOWER-bound wet-bridge estimator ---------------------


def test_dow_all_wet_consecutive_equals_span():
    # every pass wet, all gaps <= bridge -> fully bridged = span
    dn = np.array([0, 1, 3])
    wet = np.array([True, True, True])
    # base 3 + pair(1->3) interior 1 = 4 ; span 3-0+1 = 4
    assert int(days_observed_wet(dn, wet)) == 4
    assert int(span_duration(dn, wet)) == 4


def test_dow_dry_pass_breaks_bridge():
    dn = np.array([0, 1, 3])
    wet = np.array([True, False, True])
    # base 2, no both-wet consecutive pair -> 2 ; span still 0..3 = 4
    assert int(days_observed_wet(dn, wet)) == 2
    assert int(span_duration(dn, wet)) == 4


def test_dow_gap_beyond_cap_not_bridged():
    dn = np.array([0, 10])
    wet = np.array([True, True])
    # gap 10 > 4 -> no bridge, base 2
    assert int(days_observed_wet(dn, wet, max_bridge=4)) == 2
    # a wider cap would bridge it
    assert int(days_observed_wet(dn, wet, max_bridge=10)) == 11
    assert int(span_duration(dn, wet)) == 11


def test_dow_isolated_single_wet():
    dn = np.array([0, 1, 3])
    wet = np.array([False, True, False])
    assert int(days_observed_wet(dn, wet)) == 1
    assert int(span_duration(dn, wet)) == 1


def test_dow_none_wet_is_zero():
    dn = np.array([0, 2, 4])
    wet = np.array([False, False, False])
    assert int(days_observed_wet(dn, wet)) == 0
    assert int(span_duration(dn, wet)) == 0


def test_dow_two_runs_split_by_dry():
    #  wet wet DRY wet wet  at days 0,1,2,3,4 (all gaps 1)
    dn = np.array([0, 1, 2, 3, 4])
    wet = np.array([True, True, False, True, True])
    # run1 days0-1 =2, run2 days3-4 =2 -> 4 ; span 0..4 = 5
    assert int(days_observed_wet(dn, wet)) == 4
    assert int(span_duration(dn, wet)) == 5


def test_dow_single_observation():
    assert int(days_observed_wet(np.array([0]), np.array([True]))) == 1
    assert int(days_observed_wet(np.array([0]), np.array([False]))) == 0


def test_dow_and_span_vectorized_over_stack():
    # shape (k, 2, 2); prove per-pixel independence
    dn = np.array([0, 1, 3])
    wet = np.array(
        [
            [[True, True], [False, True]],
            [[True, False], [False, True]],
            [[True, True], [True, True]],
        ]
    )
    dow = days_observed_wet(dn, wet)
    span = span_duration(dn, wet)
    # pixel (0,0): all wet -> 4 ; (0,1): T,F,T -> 2 ; (1,0): F,F,T -> 1 ; (1,1): all wet -> 4
    assert dow.tolist() == [[4, 2], [1, 4]]
    # span: (0,0) 0..3=4 ; (0,1) 0..3=4 ; (1,0) 3..3=1 ; (1,1) 0..3=4
    assert span.tolist() == [[4, 4], [1, 4]]
    assert np.all(dow <= span)


def test_dow_bracket_holds_random():
    rng = np.random.default_rng(0)
    dn = np.array([0, 1, 3, 5, 7, 8, 12, 13, 15])
    wet = rng.random((len(dn), 40, 40)) < 0.5
    dow = days_observed_wet(dn, wet)
    span = span_duration(dn, wet)
    assert np.all(dow >= 0)
    assert np.all(dow <= span)


# --- validation --------------------------------------------------------------


def test_dow_rejects_unsorted_days():
    with pytest.raises(ValueError):
        days_observed_wet(np.array([0, 3, 1]), np.array([True, True, True]))


def test_dow_rejects_shape_mismatch():
    with pytest.raises(ValueError):
        days_observed_wet(np.array([0, 1, 2]), np.array([True, True]))


def test_dow_rejects_empty():
    with pytest.raises(ValueError):
        days_observed_wet(np.array([], int), np.array([], bool))


# --- duration_classes --------------------------------------------------------


def test_duration_classes_boundaries():
    dur = np.array([0, 1, 2, 3, 6, 7, 13, 14, 45])
    cls = duration_classes(dur)
    #        0  1  2  3  6  7  13 14 45
    assert cls.tolist() == [0, 1, 1, 2, 2, 3, 3, 4, 4]


def test_duration_classes_edges_and_labels_consistent():
    assert DURATION_CLASS_EDGES == (1, 3, 7, 14)
    assert len(DURATION_CLASS_LABELS) == 4  # one label per non-zero class


def test_duration_classes_2d():
    dur = np.array([[0, 3], [7, 14]])
    assert duration_classes(dur).tolist() == [[0, 2], [3, 4]]
