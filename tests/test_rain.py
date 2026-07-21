# tests/test_rain.py
import numpy as np
import pandas as pd
import pytest

from sailaab.rain import window_sum, window_with_lags, window_table, anomaly_stats


def _daily(value_p=1.0, value_u=2.0, start="2020-05-01", days=180):
    """Synthetic daily box frame: constant fields so window sums == day-count * value."""
    dates = pd.date_range(start, periods=days, freq="D")
    return pd.DataFrame(
        {
            "date": dates.strftime("%Y-%m-%d"),
            "punjab_mm": np.full(days, float(value_p)),
            "upstream_mm": np.full(days, float(value_u)),
        }
    )


# --- window_sum ---------------------------------------------------------------
def test_window_sum_half_open_counts_days():
    s = window_sum(_daily(1.0, 2.0), "2020-06-15", "2020-06-25")  # 10 days
    assert s["punjab_mm"] == pytest.approx(10.0)
    assert s["upstream_mm"] == pytest.approx(20.0)


def test_window_sum_end_is_exclusive():
    # [d, d+1) sums exactly one day; adjacent windows never double-count the seam
    s = window_sum(_daily(1.0, 2.0), "2020-06-15", "2020-06-16")
    assert s["punjab_mm"] == pytest.approx(1.0)


def test_window_sum_out_of_range_is_nan():
    s = window_sum(_daily(), "1999-01-01", "1999-01-11")
    assert np.isnan(s["punjab_mm"]) and np.isnan(s["upstream_mm"])


def test_window_sum_skips_nan_days():
    df = _daily(1.0, 2.0, start="2020-05-01", days=30)
    df.loc[df["date"] == "2020-05-10", "punjab_mm"] = np.nan
    s = window_sum(df, "2020-05-01", "2020-05-31")  # 30 days, one NaN in punjab
    assert s["punjab_mm"] == pytest.approx(29.0)
    assert s["upstream_mm"] == pytest.approx(60.0)


# --- window_with_lags ---------------------------------------------------------
def test_window_with_lags_keys_and_current():
    out = window_with_lags(
        _daily(1.0, 2.0, days=120), "2020-07-01", "2020-07-11", lags=2
    )
    assert set(out) == {
        "punjab_mm",
        "upstream_mm",
        "punjab_mm_lag1",
        "upstream_mm_lag1",
        "punjab_mm_lag2",
        "upstream_mm_lag2",
    }
    assert out["punjab_mm"] == pytest.approx(10.0)
    assert out["upstream_mm"] == pytest.approx(20.0)


def test_window_with_lags_shifts_back_by_window_length():
    # constant field -> every 10-day lag window also sums to 10 / 20
    out = window_with_lags(
        _daily(1.0, 2.0, days=120), "2020-07-01", "2020-07-11", lags=2
    )
    assert out["punjab_mm_lag1"] == pytest.approx(10.0)  # [2020-06-21, 2020-07-01)
    assert out["punjab_mm_lag2"] == pytest.approx(10.0)  # [2020-06-11, 2020-06-21)
    assert out["upstream_mm_lag1"] == pytest.approx(20.0)
    assert out["upstream_mm_lag2"] == pytest.approx(20.0)


def test_window_with_lags_orders_current_gt_lag_for_ramp():
    # rising daily field -> current window sums more than its antecedents
    dates = pd.date_range("2020-01-01", periods=250, freq="D")
    df = pd.DataFrame(
        {
            "date": dates.strftime("%Y-%m-%d"),
            "punjab_mm": np.arange(1, 251, dtype=float),
            "upstream_mm": np.arange(1, 251, dtype=float),
        }
    )
    out = window_with_lags(df, "2020-07-01", "2020-07-11", lags=2)
    assert out["punjab_mm"] > out["punjab_mm_lag1"] > out["punjab_mm_lag2"]


def test_window_with_lags_lag_before_data_is_nan():
    df = _daily(1.0, 2.0, start="2020-06-01", days=60)  # data starts Jun 1
    out = window_with_lags(df, "2020-06-01", "2020-06-11", lags=2)
    assert out["punjab_mm"] == pytest.approx(10.0)
    assert np.isnan(out["punjab_mm_lag1"])  # [2020-05-22, 2020-06-01) all before data
    assert np.isnan(out["punjab_mm_lag2"])


# --- window_table -------------------------------------------------------------
def test_window_table_columns_years_and_length():
    df = _daily(1.0, 2.0, start="2019-01-01", days=800)  # season + lag room
    t = window_table(df, [2020], lags=2)
    assert list(t.columns) == [
        "year",
        "window_start",
        "window_end",
        "punjab_mm",
        "upstream_mm",
        "punjab_mm_lag1",
        "upstream_mm_lag1",
        "punjab_mm_lag2",
        "upstream_mm_lag2",
    ]
    assert len(t) == 11  # 11 monsoon windows (matches test_windows)
    assert (t["year"] == 2020).all()


def test_window_table_first_and_last_window_sums():
    df = _daily(1.0, 2.0, start="2019-01-01", days=800)
    t = window_table(df, [2020], lags=2).reset_index(drop=True)
    r0 = t.iloc[0]
    assert (r0["window_start"], r0["window_end"]) == ("2020-06-15", "2020-06-25")
    assert r0["punjab_mm"] == pytest.approx(10.0)  # full 10-day window
    rlast = t.iloc[-1]
    assert (rlast["window_start"], rlast["window_end"]) == ("2020-09-23", "2020-09-30")
    assert rlast["punjab_mm"] == pytest.approx(7.0)  # truncated 7-day window
    assert rlast["upstream_mm"] == pytest.approx(14.0)


def test_window_table_multiple_years():
    df = _daily(1.0, 2.0, start="2018-01-01", days=1200)
    t = window_table(df, [2019, 2020], lags=2)
    assert set(t["year"]) == {2019, 2020}
    assert len(t) == 22


# --- anomaly_stats ------------------------------------------------------------
def test_anomaly_stats_zscore_percentile_and_ratio():
    prior = [10.0, 12.0, 11.0, 9.0, 13.0, 8.0, 10.5, 11.5, 9.5, 12.5]
    a = anomaly_stats(prior, 30.0)  # extreme vs prior decade
    assert a["n"] == 10
    assert a["mean"] == pytest.approx(np.mean(prior))
    assert a["std"] == pytest.approx(np.std(prior, ddof=1))
    assert a["z"] == pytest.approx((30.0 - np.mean(prior)) / np.std(prior, ddof=1))
    assert a["percentile"] == pytest.approx(100.0)  # exceeds every prior year
    assert a["max_prior"] == pytest.approx(13.0)
    assert a["rank"] == 1  # largest
    assert a["ratio_to_mean"] == pytest.approx(30.0 / np.mean(prior))


def test_anomaly_stats_percentile_midrange():
    prior = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
    a = anomaly_stats(prior, 5.0)  # 6 of 10 prior <= 5
    assert a["percentile"] == pytest.approx(60.0)
    assert a["rank"] == 5  # four priors (6,7,8,9) strictly exceed it -> rank 5


def test_anomaly_stats_constant_prior_zero_std_is_nan_z():
    a = anomaly_stats([5.0, 5.0, 5.0], 9.0)
    assert np.isnan(a["z"])  # undefined spread
    assert a["percentile"] == pytest.approx(100.0)
