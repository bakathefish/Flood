# tests/test_conformal.py
"""TDD for sailaab/conformal.py — split-conformal intervals with LOYO-honest
calibration. The headline is the synthetic coverage check: intervals built from a
calibration sample must cover a fresh sample at (approximately) the nominal rate.
"""

import numpy as np

from sailaab.conformal import (
    conformal_quantile,
    empirical_coverage,
    loyo_conformal,
    split_conformal_intervals,
)


# --------------------------------------------------------------------------- #
# finite-sample quantile
# --------------------------------------------------------------------------- #
def test_conformal_quantile_finite_sample_correction():
    # residuals 1..100; 80% -> k = ceil(101*0.8) = 81 -> 81st smallest = 81
    r = np.arange(1, 101)
    assert conformal_quantile(r, 0.80) == 81
    # 95% -> k = ceil(101*0.95) = 96 -> 96th smallest = 96
    assert conformal_quantile(r, 0.95) == 96


def test_conformal_quantile_ignores_nan():
    r = np.array([1.0, 2.0, 3.0, np.nan, 4.0, 5.0])  # 5 finite: 1..5
    # 80% -> k = ceil(6*0.8) = 5 -> 5th smallest = 5
    assert conformal_quantile(r, 0.80) == 5.0


def test_conformal_quantile_insufficient_data_is_inf():
    # n=4, 95% -> k = ceil(5*0.95) = 5 > 4 -> infinite (cannot guarantee)
    assert conformal_quantile(np.arange(1, 5), 0.95) == float("inf")


# --------------------------------------------------------------------------- #
# intervals + coverage
# --------------------------------------------------------------------------- #
def test_split_conformal_intervals_symmetric():
    lo, hi = split_conformal_intervals(np.array([1.0, 2.0]), 0.5)
    assert np.allclose(lo, [0.5, 1.5])
    assert np.allclose(hi, [1.5, 2.5])


def test_split_conformal_intervals_clamped():
    lo, hi = split_conformal_intervals(
        np.array([0.1, 0.9]), 0.5, lo_clip=0.0, hi_clip=1.0
    )
    assert np.allclose(lo, [0.0, 0.4])  # 0.1-0.5 clamped up to 0
    assert np.allclose(hi, [0.6, 1.0])  # 0.9+0.5 clamped down to 1


def test_empirical_coverage_inclusive_bounds():
    y = np.array([0.0, 1.0, 2.0, 3.0])
    lo = np.array([0.0, 0.5, 3.0, 0.0])
    hi = np.array([0.5, 1.5, 4.0, 2.9])
    # covered: 0.0 (==lo), 1.0 (in), 2.0? no (lo 3.0), 3.0? no (hi 2.9) -> 2/4
    assert empirical_coverage(y, lo, hi) == 0.5


# --------------------------------------------------------------------------- #
# THE synthetic coverage check — split-conformal is (marginally) valid
# --------------------------------------------------------------------------- #
def test_split_conformal_synthetic_coverage_near_nominal():
    rng = np.random.default_rng(7)
    n = 40000
    cal = np.abs(rng.normal(size=n))  # calibration |residuals|
    fresh = np.abs(rng.normal(size=n))  # fresh |residuals| from same law
    for cov in (0.80, 0.95):
        q = conformal_quantile(cal, cov)
        empirical = float(np.mean(fresh <= q))
        assert abs(empirical - cov) < 0.01, (cov, empirical)


def test_loyo_conformal_coverage_near_nominal():
    rng = np.random.default_rng(11)
    years = np.repeat(np.arange(2015, 2026), 300)  # 11 years x 300 rows
    resid = rng.normal(size=years.size)  # true - pred ~ N(0,1)
    y_pred = rng.normal(size=years.size)  # arbitrary point predictions
    y_true = y_pred + resid
    out = loyo_conformal(years, y_true, y_pred, coverage_levels=(0.80, 0.95))
    for cov in (0.80, 0.95):
        c = empirical_coverage(y_true, out[cov]["lo"], out[cov]["hi"])
        assert abs(c - cov) < 0.02, (cov, c)


def test_loyo_conformal_clamps_to_unit_interval():
    years = np.array([2019, 2019, 2020, 2020, 2021, 2021])
    y_true = np.array([0.0, 0.02, 0.01, 0.0, 0.03, 0.0])
    y_pred = np.array([0.01, 0.01, 0.02, 0.0, 0.02, 0.01])
    out = loyo_conformal(
        years, y_true, y_pred, coverage_levels=(0.80,), lo_clip=0.0, hi_clip=1.0
    )
    assert np.all(out[0.80]["lo"] >= 0.0)
    assert np.all(out[0.80]["hi"] <= 1.0)
