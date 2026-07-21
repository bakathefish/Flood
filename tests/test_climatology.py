# tests/test_climatology.py
"""TDD spec for sailaab.climatology — extreme-rain indices + trend statistics.

Every assertion is a hand-computed anchor on a synthetic series so the math is
pinned independently of the IMD data (which is not committed as rasters).
"""

import numpy as np
import pandas as pd
import pytest

from sailaab.climatology import (
    annual_indices,
    empirical_return_period,
    lag1_autocorr,
    mann_kendall,
    mann_kendall_prewhitened,
    prewhiten,
    r95_count,
    rx5day,
    sens_slope,
    total_monsoon,
    wet_day_threshold,
)


def _year_daily(year, monsoon_values, col="punjab_mm"):
    """A one-year daily frame whose Jun1-Sep30 days take `monsoon_values`
    (padded/truncated to the 122 JJAS days) and 0.0 elsewhere."""
    dates = pd.date_range(f"{year}-01-01", f"{year}-12-31", freq="D")
    vals = np.zeros(len(dates))
    monsoon = (dates >= f"{year}-06-01") & (dates <= f"{year}-09-30")
    idx = np.where(monsoon)[0]
    mv = np.asarray(monsoon_values, dtype=float)
    n = min(len(idx), len(mv))
    vals[idx[:n]] = mv[:n]
    return pd.DataFrame({"date": dates.strftime("%Y-%m-%d"), col: vals})


# --- season slicing / total -------------------------------------------------
def test_jjas_is_exactly_122_days_and_total_sums_only_monsoon():
    # put 1.0 on every JJAS day and 5.0 on Jan 1 (must be ignored)
    df = _year_daily(2000, np.ones(122))
    df.loc[0, "punjab_mm"] = 5.0  # Jan 1 spike outside monsoon
    assert total_monsoon(df, "punjab_mm", 2000) == pytest.approx(122.0)


def test_total_monsoon_leap_year_still_122_jjas_days():
    df = _year_daily(2000, np.ones(200))  # leap year; JJAS still 122 days
    assert total_monsoon(df, "punjab_mm", 2000) == pytest.approx(122.0)


# --- wet-day threshold (R95) ------------------------------------------------
def test_wet_day_threshold_linear_percentile_known_value():
    # base period 1990: monsoon wet days = [10,20,...,100]; dry days (<1mm) ignored
    wet = list(range(10, 101, 10))  # 10 values
    monsoon = wet + [0.0] * (122 - len(wet))  # pad with dry days
    df = _year_daily(1990, monsoon)
    thr = wet_day_threshold(df, "punjab_mm", [1990], pct=95.0, wet_mm=1.0)
    # np.percentile([10..100],95, linear) = arr[8] + 0.55*(arr[9]-arr[8]) = 95.5
    assert thr == pytest.approx(95.5)


def test_wet_day_threshold_excludes_sub_1mm_days():
    # drizzle (0.4mm) days must not enter the wet-day distribution
    monsoon = [0.4] * 60 + [50.0, 100.0] + [0.0] * 60
    df = _year_daily(1985, monsoon)
    thr = wet_day_threshold(df, "punjab_mm", [1985], pct=95.0, wet_mm=1.0)
    # only wet days are {50,100}; 95th pct linear = 50 + 0.95*50 = 97.5
    assert thr == pytest.approx(97.5)


def test_r95_count_counts_days_at_or_above_threshold():
    df = _year_daily(2010, [96.0, 40.0, 100.0, 95.5, 20.0])
    # threshold 95.5 -> days {96, 100, 95.5} qualify (>=), 40 and 20 do not
    assert r95_count(df, "punjab_mm", 2010, threshold=95.5) == 3


# --- RX5day -----------------------------------------------------------------
def test_rx5day_picks_max_5day_running_sum():
    # a single 5-day burst 3,10,20,10,3 (=46) dominates; rest are 1.0
    burst = [1.0] * 20 + [3.0, 10.0, 20.0, 10.0, 3.0] + [1.0] * 20
    df = _year_daily(2011, burst)
    assert rx5day(df, "punjab_mm", 2011) == pytest.approx(46.0)


def test_rx5day_requires_full_5day_window():
    # only 3 monsoon days with rain -> no full 5-day window from them alone,
    # but zeros fill the rest so the max 5-day sum is just the burst total
    df = _year_daily(2012, [7.0, 8.0, 9.0])  # rest of JJAS is 0.0
    assert rx5day(df, "punjab_mm", 2012) == pytest.approx(24.0)  # 7+8+9+0+0


# --- Mann-Kendall -----------------------------------------------------------
def test_mann_kendall_strictly_increasing_S_and_tau():
    r = mann_kendall([1, 2, 3, 4, 5])
    assert r["n"] == 5
    assert r["s"] == 10  # all 10 pairs concordant
    assert r["tau"] == pytest.approx(1.0)
    assert r["p"] == pytest.approx(0.0275, abs=1e-3)  # 2*sf(2.2045)


def test_mann_kendall_strictly_decreasing_is_negative_S():
    r = mann_kendall([5, 4, 3, 2, 1])
    assert r["s"] == -10
    assert r["tau"] == pytest.approx(-1.0)
    assert r["p"] == pytest.approx(0.0275, abs=1e-3)


def test_mann_kendall_flat_symmetric_series_has_zero_S_and_p_one():
    r = mann_kendall([3, 1, 4, 1, 4, 1, 3])  # constructed so S == 0
    assert r["s"] == 0
    assert r["z"] == pytest.approx(0.0)
    assert r["p"] == pytest.approx(1.0)


def test_mann_kendall_tie_correction_S_exact():
    r = mann_kendall([1, 1, 2, 2, 3, 3])
    assert r["s"] == 12
    assert r["n"] == 6


def test_mann_kendall_matches_scipy_kendalltau_on_noisy_series():
    # tau/S are method-independent; cross-check against scipy. p is validated to
    # 1e-3 by the deterministic 1..5 anchor above, so here we only require the
    # normal-approx p to agree on significance (both well below 0.05).
    rng = np.random.default_rng(0)
    x = np.arange(30) * 0.3 + rng.normal(size=30)
    r = mann_kendall(x)
    from scipy.stats import kendalltau

    tau_ref, p_ref = kendalltau(np.arange(30), x)
    assert r["tau"] == pytest.approx(tau_ref, abs=1e-9)
    assert r["p"] < 0.05 and p_ref < 0.05


# --- lag-1 autocorrelation + pre-whitening ----------------------------------
def test_lag1_autocorr_known_value():
    assert lag1_autocorr([1, 2, 3, 4]) == pytest.approx(0.25)


def test_prewhiten_removes_lag1_component():
    out = prewhiten([1, 2, 3, 4], r1=0.25)
    assert list(np.round(out, 4)) == [1.75, 2.5, 3.25]  # x[t]-0.25*x[t-1]


def test_prewhiten_estimates_r1_when_not_given():
    out = prewhiten([1, 2, 3, 4])  # uses r1=0.25 internally
    assert out == pytest.approx([1.75, 2.5, 3.25])


def test_mann_kendall_prewhitened_flags_low_autocorr_as_not_applied():
    # low lag-1 autocorr (r1 = 0.125, below 1.96/sqrt(8)=0.69) -> raw MK reported
    x = [1, 3, 2, 4, 3, 5, 4, 6]
    r = mann_kendall_prewhitened(x)
    assert r["prewhitened"] is False
    assert r["p"] == pytest.approx(r["p_raw"])
    assert abs(r["r1"]) <= 1.96 / np.sqrt(len(x))


def test_mann_kendall_prewhitened_applies_when_autocorr_strong():
    # strong AR(1)+trend: lag-1 autocorr is significant -> pre-whitening applied
    rng = np.random.default_rng(1)
    n = 60
    e = rng.normal(size=n)
    x = np.zeros(n)
    for t in range(1, n):
        x[t] = 0.7 * x[t - 1] + e[t]
    x = x + 0.05 * np.arange(n)  # mild trend
    r = mann_kendall_prewhitened(x)
    assert r["prewhitened"] is True
    assert r["r1"] > 1.96 / np.sqrt(n)
    assert "p" in r and "p_raw" in r


# --- Sen's slope ------------------------------------------------------------
def test_sens_slope_exact_on_linear_series():
    t = np.arange(10)
    x = 3.0 + 2.0 * t
    assert sens_slope(x) == pytest.approx(2.0)


def test_sens_slope_is_robust_to_a_single_outlier():
    t = np.arange(11)
    x = (1.0 * t).astype(float)
    x[5] = 100.0  # gross outlier
    assert sens_slope(x) == pytest.approx(1.0)  # median pairwise slope unmoved


def test_sens_slope_with_explicit_time_vector():
    t = np.array([2000, 2002, 2004, 2006])
    x = 10 + 0.5 * (t - 2000)
    assert sens_slope(x, t) == pytest.approx(0.5)


# --- empirical return period ------------------------------------------------
def test_empirical_return_period_record_max():
    vals = [5, 3, 9, 1, 7]
    r = empirical_return_period(vals, 9)  # the maximum
    assert r["rank"] == 1
    assert r["n"] == 5
    assert r["return_period"] == pytest.approx(6.0)  # (n+1)/1
    assert r["exceedance_prob"] == pytest.approx(1 / 6)


def test_empirical_return_period_midrank():
    vals = [5, 3, 9, 1, 7]
    r = empirical_return_period(vals, 7)  # one value (9) strictly greater
    assert r["rank"] == 2
    assert r["return_period"] == pytest.approx(3.0)  # 6/2


# --- integration: annual_indices table --------------------------------------
def test_annual_indices_table_shape_and_columns():
    frames = []
    for y in (1961, 1962, 1963):
        frames.append(_year_daily(y, [50.0, 20.0, 10.0] + [2.0] * 40))
    daily = pd.concat(frames, ignore_index=True)
    tbl = annual_indices(
        daily, "punjab_mm", years=[1961, 1962, 1963], base_years=[1961, 1962]
    )
    assert list(tbl.columns) == ["year", "r95cnt", "rx5day", "prcptot"]
    assert list(tbl["year"]) == [1961, 1962, 1963]
    # constant fields across years -> identical index values each year
    assert tbl["prcptot"].nunique() == 1
