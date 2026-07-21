# tests/test_causal.py
"""Tests for the pure helpers behind the Wave-3 causal figure
(``sailaab.causal``): %-of-live-capacity math and the same-calendar-day
climatology band. Rendering (``pipeline/make_causal_figure.py``) is not tested
here - only the deterministic data transforms it depends on."""

import numpy as np
import pandas as pd
import pytest

from sailaab.causal import (
    FRL_FT,
    LIVE_CAPACITY_BCM,
    pct_of_live_capacity,
    same_day_climatology,
)


def test_pct_of_live_capacity_scalar():
    # storage == live capacity -> exactly 100 % (FRL / brim-full)
    assert pct_of_live_capacity(LIVE_CAPACITY_BCM["Bhakra"], "Bhakra") == pytest.approx(
        100.0
    )
    assert pct_of_live_capacity(
        LIVE_CAPACITY_BCM["Bhakra"] / 2, "Bhakra"
    ) == pytest.approx(50.0)


def test_pct_of_live_capacity_series_is_vectorized():
    cap = LIVE_CAPACITY_BCM["Pong"]
    s = pd.Series([cap, cap / 2, 0.0])
    out = pct_of_live_capacity(s, "Pong")
    assert isinstance(out, pd.Series)
    assert out.tolist() == pytest.approx([100.0, 50.0, 0.0])


def test_pct_of_live_capacity_matches_reported_pct():
    # Bhakra 2025-09-03 supplement row: storage 5.793 BCM was reported at 93 %.
    assert pct_of_live_capacity(5.793, "Bhakra") == pytest.approx(93.0, abs=0.1)


def test_pct_of_live_capacity_unknown_dam_raises():
    with pytest.raises(KeyError):
        pct_of_live_capacity(1.0, "Nonesuch")


def test_frl_constants_present():
    # danger levels used in annotations are sourced constants, not magic numbers.
    assert FRL_FT["Bhakra"] == 1680.0
    assert FRL_FT["Pong"] == 1390.0


def test_same_day_climatology_median_per_calendar_day():
    dates = pd.to_datetime(
        [
            "2015-06-01",
            "2016-06-01",
            "2025-06-01",
            "2015-06-02",
            "2016-06-02",
            "2025-06-02",
        ]
    )
    daily = pd.DataFrame({"date": dates, "x_mm": [10.0, 20.0, 999.0, 0.0, 4.0, 999.0]})
    target = pd.to_datetime(["2025-06-01", "2025-06-02"])
    clim = same_day_climatology(daily, ["x_mm"], [2015, 2016], target, quantiles=(0.5,))
    # median of {10,20} = 15 on 06-01; median of {0,4} = 2 on 06-02
    assert clim.loc[pd.Timestamp("2025-06-01"), "x_mm_p50"] == pytest.approx(15.0)
    assert clim.loc[pd.Timestamp("2025-06-02"), "x_mm_p50"] == pytest.approx(2.0)
    # target year's own values must not leak into the prior-year climatology
    assert clim["x_mm_p50"].max() < 999.0


def test_same_day_climatology_orders_percentiles():
    dates = pd.to_datetime(["2015-07-10", "2016-07-10", "2017-07-10"])
    daily = pd.DataFrame({"date": dates, "u": [1.0, 5.0, 9.0]})
    target = pd.to_datetime(["2025-07-10"])
    clim = same_day_climatology(
        daily, ["u"], [2015, 2016, 2017], target, quantiles=(0.1, 0.5, 0.9)
    )
    p10 = clim.loc[pd.Timestamp("2025-07-10"), "u_p10"]
    p50 = clim.loc[pd.Timestamp("2025-07-10"), "u_p50"]
    p90 = clim.loc[pd.Timestamp("2025-07-10"), "u_p90"]
    assert p10 <= p50 <= p90


def test_same_day_climatology_missing_target_day_is_nan():
    # A target (month, day) absent from the priors -> NaN, no crash.
    dates = pd.to_datetime(["2015-07-10", "2016-07-10"])
    daily = pd.DataFrame({"date": dates, "u": [2.0, 6.0]})
    target = pd.to_datetime(["2025-07-11", "2025-07-10"])  # 07-11 not in priors
    clim = same_day_climatology(daily, ["u"], [2015, 2016], target, quantiles=(0.5,))
    assert np.isnan(clim.loc[pd.Timestamp("2025-07-11"), "u_p50"])
    assert clim.loc[pd.Timestamp("2025-07-10"), "u_p50"] == pytest.approx(4.0)


def test_same_day_climatology_multiple_columns():
    dates = pd.to_datetime(["2015-08-01", "2016-08-01"])
    daily = pd.DataFrame({"date": dates, "up": [10.0, 30.0], "pun": [4.0, 8.0]})
    target = pd.to_datetime(["2025-08-01"])
    clim = same_day_climatology(
        daily, ["up", "pun"], [2015, 2016], target, quantiles=(0.5,)
    )
    assert clim.loc[pd.Timestamp("2025-08-01"), "up_p50"] == pytest.approx(20.0)
    assert clim.loc[pd.Timestamp("2025-08-01"), "pun_p50"] == pytest.approx(6.0)
