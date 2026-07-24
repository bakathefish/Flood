# tests/test_nowlapse.py
"""Pure-logic tests for the current-season timelapse (sailaab/nowlapse.py).

No network / IO: IST season-day enumeration, the cumulative-mask update, km^2
from pixel counts, and dash-free frame labels -- all against synthetic arrays
with exact expected counts.
"""

from datetime import date, datetime, timezone

import numpy as np
import pytest

from sailaab import nowlapse


# --------------------------------------------------------------------------- #
# IST "today" and season-day enumeration
# --------------------------------------------------------------------------- #
def test_today_ist_rolls_after_1830_utc():
    # 18:15 UTC is 23:45 IST -> same Indian day; 18:45 UTC is 00:15 IST -> next.
    before = datetime(2026, 6, 1, 18, 15, tzinfo=timezone.utc)
    after = datetime(2026, 6, 1, 18, 45, tzinfo=timezone.utc)
    assert nowlapse.today_ist(before) == date(2026, 6, 1)
    assert nowlapse.today_ist(after) == date(2026, 6, 2)


def test_today_ist_treats_naive_as_utc():
    naive = datetime(2026, 6, 1, 20, 0)  # no tzinfo -> assumed UTC -> 01:30 IST +1d
    assert nowlapse.today_ist(naive) == date(2026, 6, 2)


def test_season_days_spans_june1_to_today_inclusive():
    days = nowlapse.season_days("2026-07-23")
    assert days[0] == "2026-06-01"
    assert days[-1] == "2026-07-23"
    # June (30) + July 1..23 (23) = 53 candidate days
    assert len(days) == 53


def test_season_days_single_day_on_june_first():
    assert nowlapse.season_days("2026-06-01") == ["2026-06-01"]


def test_season_days_empty_before_season():
    assert nowlapse.season_days("2026-05-31") == []


def test_season_days_accepts_date_and_datetime():
    a = nowlapse.season_days(date(2026, 6, 3))
    b = nowlapse.season_days(datetime(2026, 6, 3, 9, 0, tzinfo=timezone.utc))
    assert a == b == ["2026-06-01", "2026-06-02", "2026-06-03"]


def test_season_days_year_override():
    days = nowlapse.season_days("2024-06-10", year=2024)
    assert days[0] == "2024-06-01" and days[-1] == "2024-06-10"
    assert len(days) == 10


# --------------------------------------------------------------------------- #
# cumulative-mask update
# --------------------------------------------------------------------------- #
def test_update_cumulative_first_day_is_all_fresh():
    day = np.array([[1, 0], [0, 1]], bool)
    cum, fresh = nowlapse.update_cumulative(None, day)
    assert cum.tolist() == day.tolist()
    assert fresh.tolist() == day.tolist()


def test_update_cumulative_only_new_pixels_are_fresh():
    cum0 = np.array([[1, 0], [0, 0]], bool)
    day = np.array([[1, 1], [0, 0]], bool)  # (0,0) already wet, (0,1) is new
    cum, fresh = nowlapse.update_cumulative(cum0, day)
    assert cum.tolist() == [[True, True], [False, False]]
    assert fresh.tolist() == [[False, True], [False, False]]
    assert int(fresh.sum()) == 1


def test_update_cumulative_does_not_mutate_input():
    cum0 = np.zeros((2, 2), bool)
    day = np.ones((2, 2), bool)
    nowlapse.update_cumulative(cum0, day)
    assert cum0.sum() == 0  # untouched


def test_update_cumulative_shape_mismatch_raises():
    with pytest.raises(ValueError):
        nowlapse.update_cumulative(np.zeros((2, 2), bool), np.zeros((2, 3), bool))


def test_cumulative_and_fresh_sequence_is_monotone_and_disjoint():
    d1 = np.array([[1, 0, 0]], bool)
    d2 = np.array([[1, 1, 0]], bool)
    d3 = np.array([[0, 0, 1]], bool)
    out = list(nowlapse.cumulative_and_fresh([d1, d2, d3]))
    cum_counts = [int(c.sum()) for c, _ in out]
    fresh_counts = [int(f.sum()) for _, f in out]
    assert cum_counts == [1, 2, 3]  # union only grows
    assert fresh_counts == [1, 1, 1]  # each day adds exactly one new pixel
    # final cumulative is the full union
    assert out[-1][0].tolist() == [[True, True, True]]


# --------------------------------------------------------------------------- #
# km^2 from pixel counts
# --------------------------------------------------------------------------- #
def test_km2_from_pixels_exact_fraction():
    # 25 of 100 pixels over a 1000 km^2 box -> 250 km^2
    assert nowlapse.km2_from_pixels(25, 100, 1000.0) == pytest.approx(250.0)


def test_km2_from_pixels_zero_flood_is_zero():
    assert nowlapse.km2_from_pixels(0, 100, 1000.0) == 0.0


def test_km2_from_pixels_total_must_be_positive():
    with pytest.raises(ValueError):
        nowlapse.km2_from_pixels(1, 0, 1000.0)


def test_mask_km2_counts_true_pixels():
    mask = np.zeros((10, 10), bool)
    mask[:2, :] = True  # 20 of 100 pixels
    assert nowlapse.mask_km2(mask, 500.0) == pytest.approx(100.0)


# --------------------------------------------------------------------------- #
# daily mode: signed change vs previous pass + season peak
# --------------------------------------------------------------------------- #
def test_change_label_signed_and_worded():
    # daily frames show the change against the PREVIOUS covered pass; water
    # that drained away must read as a fall, not vanish silently
    assert nowlapse.change_label(12.4) == "up 12 km² vs previous pass"
    assert nowlapse.change_label(-8.6) == "down 9 km² vs previous pass"
    assert nowlapse.change_label(0.2) == "level with previous pass"
    assert nowlapse.change_label(-0.4) == "level with previous pass"


def test_peak_day_first_maximum_wins():
    days = ["2026-06-01", "2026-06-13", "2026-07-02"]
    areas = [10.0, 42.5, 42.5]
    assert nowlapse.peak_day(days, areas) == ("2026-06-13", 42.5)


def test_peak_day_validates_input():
    with pytest.raises(ValueError):
        nowlapse.peak_day([], [])
    with pytest.raises(ValueError):
        nowlapse.peak_day(["2026-06-01"], [1.0, 2.0])


# --------------------------------------------------------------------------- #
# frame labels -- must never contain an em dash or en dash
# --------------------------------------------------------------------------- #
def _all_labels():
    return [
        nowlapse.fmt_km2(2951.2),
        nowlapse.pretty_date("2026-06-01"),
        nowlapse.season_range_label("2026-06-01", "2026-07-23"),
        nowlapse.kicker(2026),
        nowlapse.delta_label(12.0),
        nowlapse.change_label(12.0),
        nowlapse.change_label(-12.0),
        nowlapse.change_label(0.0),
        nowlapse.coverage_caption(3),
        nowlapse.coverage_caption(1),
    ]


def test_labels_have_no_em_or_en_dash():
    for s in _all_labels():
        assert "—" not in s, f"em dash in {s!r}"  # em dash
        assert "–" not in s, f"en dash in {s!r}"  # en dash


def test_label_formats():
    assert nowlapse.fmt_km2(2951.2) == "2,951 km²"
    assert nowlapse.pretty_date("2026-06-01") == "01 Jun 2026"
    assert nowlapse.season_range_label("2026-06-01", "2026-07-23") == (
        "01 Jun · 23 Jul 2026"
    )
    assert nowlapse.kicker(2026) == "PUNJAB · MONSOON 2026"
    assert nowlapse.delta_label(12.0) == "+12 km² this day"
    assert nowlapse.coverage_caption(1) == "1 day with a Sentinel-1 pass"
    assert nowlapse.coverage_caption(3) == "3 days with a Sentinel-1 pass"
