# tests/test_era5_intensity.py
"""Pure-logic tests for the ERA5 sub-daily intensity helpers (no network)."""

import numpy as np

from pipeline.fetch_era5_intensity import (
    area_mean_hourly,
    rolling_max_sum,
    window_intensity,
)


def test_rolling_max_sum_picks_the_peak_run():
    # peak 3-run is 4+5+6 = 15
    assert rolling_max_sum([1, 2, 3, 4, 5, 6, 0], 3) == 15.0


def test_rolling_max_sum_nan_treated_as_zero():
    assert rolling_max_sum([np.nan, 2.0, np.nan], 2) == 2.0


def test_rolling_max_sum_short_series_sums_all():
    assert rolling_max_sum([2.0, 3.0], 24) == 5.0


def test_rolling_max_sum_empty_is_nan():
    assert np.isnan(rolling_max_sum([], 3))


def test_area_mean_hourly_cos_lat_weighted():
    # two points, equal weights -> plain mean; missing hour skipped
    s1 = {"2020-08-01T00:00": 2.0, "2020-08-01T01:00": 4.0}
    s2 = {"2020-08-01T00:00": 4.0}
    out = area_mean_hourly([s1, s2], [1.0, 1.0])
    assert out["2020-08-01T00:00"] == 3.0  # (2+4)/2
    assert out["2020-08-01T01:00"] == 4.0  # only s1 present


def test_window_intensity_within_window_only():
    # 26 hours on 08-24, then spill into 08-25 which must be excluded by [w0,w1)
    hourly = {}
    for hh in range(24):
        hourly[f"2020-08-24T{hh:02d}:00"] = 1.0  # 1 mm every hour on 08-24
    # a burst on 08-24: three consecutive 10 mm hours -> max_3h = 30, but replace
    hourly["2020-08-24T05:00"] = 10.0
    hourly["2020-08-24T06:00"] = 10.0
    hourly["2020-08-24T07:00"] = 10.0
    # next-day hours that must NOT count
    hourly["2020-08-25T00:00"] = 99.0
    m = window_intensity(hourly, "2020-08-24", "2020-08-25")
    assert m["max_3h_mm"] == 30.0  # 10+10+10, the 99 on 08-25 is excluded
    assert m["hours_ge5mm"] == 3  # only the three 10 mm hours clear 5 mm
    # 24h sum = 21 normal hours * 1 + 3 burst hours * 10 = 21 + 30 = 51
    assert m["max_24h_mm"] == 51.0


def test_window_intensity_counts_threshold_boundary():
    hourly = {
        "2021-09-03T00:00": 5.0,  # exactly 5 -> counts (>=)
        "2021-09-03T01:00": 4.999,  # just under -> not
        "2021-09-03T02:00": 12.0,
    }
    m = window_intensity(hourly, "2021-09-03", "2021-09-13")
    assert m["hours_ge5mm"] == 2
