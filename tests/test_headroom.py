# tests/test_headroom.py
"""Tests for the pure math behind the dam-headroom analysis
(``sailaab.headroom``): day-of-season indexing, the 2015-2024 median filling
curve (with honest per-day ``n_years`` reporting and an IQR band), the
no-extrapolation 2025-curve interpolation, the headroom-deficit arithmetic, the
level->storage hypsometric rating (Ranjit Sagar), and the cusec->BCM/day surge
conversion + absorbable-days buffer math.

Rendering (``pipeline/make_headroom.py``) is not tested here - only the
deterministic transforms it depends on."""

import numpy as np
import pandas as pd
import pytest

from sailaab.headroom import (
    CUSEC_TO_BCM_PER_DAY,
    absorbable_days,
    cusecs_to_bcm_per_day,
    headroom_deficit,
    interp_no_extrap,
    median_fill_curve,
    rating_level_to_storage,
    season_day,
)


# --------------------------------------------------------------------------- #
# day-of-season index
# --------------------------------------------------------------------------- #
def test_season_day_scalar_anchors():
    assert season_day("2025-06-01") == 0
    assert season_day("2025-07-01") == 30  # June has 30 days
    assert season_day("2025-08-01") == 61
    assert season_day("2025-08-25") == 85  # the headline date
    assert season_day("2025-09-30") == 121  # last day of season


def test_season_day_is_leap_safe_across_years():
    # No 29 Feb inside Jun-Sep, so the same calendar day maps to the same
    # day-of-season in every year (leap or not).
    assert season_day("2020-08-25") == season_day("2021-08-25") == 85


def test_season_day_vectorized():
    out = season_day(pd.to_datetime(["2025-06-01", "2025-08-25", "2025-09-30"]))
    assert isinstance(out, np.ndarray)
    assert out.tolist() == [0, 85, 121]


# --------------------------------------------------------------------------- #
# median filling curve
# --------------------------------------------------------------------------- #
def _synthetic_daily():
    """Two prior years + a target year, one dam, hand-computable quantiles."""
    rows = []
    # 06-01: 2015->2.0, 2016->4.0, 2017->6.0  => q25=3, q50=4, q75=5 (3 years)
    for y, s in [(2015, 2.0), (2016, 4.0), (2017, 6.0)]:
        rows.append((f"{y}-06-01", "Bhakra", s))
    # 06-02: only 2015 present => n_years=1, median=10
    rows.append(("2015-06-02", "Bhakra", 10.0))
    # 06-03: absent from all priors (only the target year 2025 has it)
    rows.append(("2025-06-03", "Bhakra", 999.0))
    df = pd.DataFrame(rows, columns=["date", "dam", "storage_value"])
    df["date"] = pd.to_datetime(df["date"])
    return df


def test_median_fill_curve_quantiles_and_n_years():
    df = _synthetic_daily()
    curve = median_fill_curve(df, "Bhakra", [2015, 2016, 2017])
    row0 = curve.loc[0]
    assert row0["q50"] == pytest.approx(4.0)
    assert row0["q25"] == pytest.approx(3.0)
    assert row0["q75"] == pytest.approx(5.0)
    assert row0["n_years"] == 3
    assert row0["n_obs"] == 3
    # ordering of the band
    assert row0["q25"] <= row0["q50"] <= row0["q75"]


def test_median_fill_curve_reports_sparse_days_honestly():
    df = _synthetic_daily()
    curve = median_fill_curve(df, "Bhakra", [2015, 2016, 2017])
    # 06-02 (doy 1): only 2015 contributed
    assert curve.loc[1, "n_years"] == 1
    assert curve.loc[1, "q50"] == pytest.approx(10.0)
    # 06-03 (doy 2): no prior year -> NaN quantile, n_years 0, but row still exists
    assert curve.loc[2, "n_years"] == 0
    assert np.isnan(curve.loc[2, "q50"])


def test_median_fill_curve_excludes_target_year():
    df = _synthetic_daily()
    curve = median_fill_curve(df, "Bhakra", [2015, 2016, 2017])
    # the 2025 value of 999 on 06-03 must never leak into the prior-year curve
    assert curve["q50"].max(skipna=True) < 999.0


def test_median_fill_curve_covers_full_season_index():
    df = _synthetic_daily()
    curve = median_fill_curve(df, "Bhakra", [2015, 2016, 2017])
    # day-of-season 0..121 all present (Jun 1 -> Sep 30)
    assert list(curve.index) == list(range(122))
    assert curve.loc[121].name == 121  # Sep 30 present


def test_median_fill_curve_pct_column_when_requested():
    df = _synthetic_daily()
    curve = median_fill_curve(df, "Bhakra", [2015, 2016, 2017], as_pct_of=6.229)
    # q50 storage 4.0 BCM -> 4.0/6.229*100 pct
    assert curve.loc[0, "q50_pct"] == pytest.approx(4.0 / 6.229 * 100.0)


# --------------------------------------------------------------------------- #
# deficit arithmetic
# --------------------------------------------------------------------------- #
def test_headroom_deficit_positive_when_fuller_than_median():
    # 2025 fuller than the decade median => positive deficit (less headroom)
    dbcm, dpct = headroom_deficit(5.0, 4.0, live_cap_bcm=6.229)
    assert dbcm == pytest.approx(1.0)
    assert dpct == pytest.approx(1.0 / 6.229 * 100.0)


def test_headroom_deficit_negative_when_emptier_than_median():
    dbcm, dpct = headroom_deficit(3.0, 4.0, live_cap_bcm=6.229)
    assert dbcm == pytest.approx(-1.0)
    assert dpct < 0


def test_headroom_deficit_vectorized():
    s = pd.Series([5.0, 4.0, 3.0])
    m = pd.Series([4.0, 4.0, 4.0])
    dbcm, dpct = headroom_deficit(s, m, live_cap_bcm=6.157)
    assert list(dbcm) == pytest.approx([1.0, 0.0, -1.0])


# --------------------------------------------------------------------------- #
# no-extrapolation interpolation of the sparse 2025 curve
# --------------------------------------------------------------------------- #
def test_interp_no_extrap_interior():
    kd = pd.to_datetime(["2025-08-01", "2025-08-19"])
    kv = [3.301, 4.983]
    tgt = pd.to_datetime(["2025-08-10"])
    got = interp_no_extrap(kd, kv, tgt)
    # linear between the two points at day 9 of an 18-day span
    frac = 9 / 18
    assert got[0] == pytest.approx(3.301 + frac * (4.983 - 3.301))


def test_interp_no_extrap_returns_nan_outside_range():
    kd = pd.to_datetime(["2025-08-08", "2025-08-18"])
    kv = [5.110, 5.233]
    tgt = pd.to_datetime(["2025-08-01", "2025-08-12", "2025-08-25"])
    got = interp_no_extrap(kd, kv, tgt)
    assert np.isnan(got[0])  # before first known -> no extrapolation
    assert not np.isnan(got[1])  # interior -> interpolated
    assert np.isnan(got[2])  # after last known -> no extrapolation


def test_interp_no_extrap_hits_known_points_exactly():
    kd = pd.to_datetime(["2025-08-01", "2025-08-19"])
    kv = [3.301, 4.983]
    got = interp_no_extrap(kd, kv, kd)
    assert got == pytest.approx(kv)


def test_interp_no_extrap_unsorted_input():
    kd = pd.to_datetime(["2025-08-19", "2025-08-01"])  # reversed
    kv = [4.983, 3.301]
    tgt = pd.to_datetime(["2025-08-01", "2025-08-19"])
    got = interp_no_extrap(kd, kv, tgt)
    assert got == pytest.approx([3.301, 4.983])


# --------------------------------------------------------------------------- #
# hypsometric level -> storage rating (Ranjit Sagar)
# --------------------------------------------------------------------------- #
def test_rating_level_to_storage_monotone_interp():
    # synthetic monotone rating: storage rises with level
    daily = pd.DataFrame(
        {
            "dam": ["RS"] * 4,
            "level_m": [500.0, 510.0, 520.0, 527.0],
            "storage_value": [0.5, 1.2, 2.0, 2.3],
        }
    )
    got = rating_level_to_storage(daily, "RS", [515.0])
    # halfway between (510,1.2) and (520,2.0) -> 1.6
    assert got[0] == pytest.approx(1.6, abs=1e-6)


def test_rating_level_to_storage_clamps_above_observed():
    daily = pd.DataFrame(
        {
            "dam": ["RS"] * 3,
            "level_m": [500.0, 510.0, 520.0],
            "storage_value": [0.5, 1.2, 2.0],
        }
    )
    # a level above the observed max clamps to the top storage (no extrapolation up)
    got = rating_level_to_storage(daily, "RS", [525.0])
    assert got[0] == pytest.approx(2.0)


# --------------------------------------------------------------------------- #
# surge conversion + absorbable-days buffer math
# --------------------------------------------------------------------------- #
def test_cusec_conversion_constant():
    # 1 cusec = 0.028316846592 m^3/s * 86400 s * 1e-9 BCM/m^3
    assert CUSEC_TO_BCM_PER_DAY == pytest.approx(2.446575e-6, rel=1e-4)


def test_cusecs_to_bcm_per_day_scalar_and_vector():
    assert cusecs_to_bcm_per_day(173_000) == pytest.approx(0.4233, abs=1e-3)
    out = cusecs_to_bcm_per_day(np.array([85_000, 100_000]))
    assert out.tolist() == pytest.approx([0.2080, 0.2447], abs=1e-3)


def test_absorbable_days_is_deficit_over_rate():
    # ~0.4233 BCM of headroom at 173k cusecs peak throughput ~= 1.0 day
    days = absorbable_days(0.4233, 173_000)
    assert days == pytest.approx(1.0, abs=0.02)


def test_absorbable_days_zero_headroom_is_zero_days():
    assert absorbable_days(0.0, 173_000) == pytest.approx(0.0)
