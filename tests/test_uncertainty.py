# tests/test_uncertainty.py
"""Tests for the resampling that puts intervals on the benchmark numbers."""

from __future__ import annotations

import numpy as np
import pytest

from sailaab.uncertainty import (
    BLOCK_DAYS,
    delete_one_season,
    delta_ci,
    percentile_ci,
    season_summary,
    two_stage_bootstrap,
)


def _panel(n_seasons=4, n_days=40, n_dist=20, seed=0):
    """A synthetic panel with a real signal and day-level dependence."""
    rng = np.random.default_rng(seed)
    season, day, y, good, noise = [], [], [], [], []
    for s in range(n_seasons):
        for d in range(n_days):
            wet = rng.random() < 0.15  # whole days flood together
            for _ in range(n_dist):
                season.append(2019 + s)
                day.append(d)
                label = 1.0 if (wet and rng.random() < 0.4) else 0.0
                y.append(label)
                good.append(label * 0.6 + rng.random() * 0.4)
                noise.append(rng.random())
    return (np.array(y), np.array(season), np.array(day),
            {"good": np.array(good), "noise": np.array(noise)})


def test_bootstrap_returns_one_replicate_array_per_candidate():
    y, season, day, scores = _panel()
    boot = two_stage_bootstrap(y, scores, season, day, n_boot=40, seed=1)
    assert set(boot) == {"good", "noise"}
    for v in boot.values():
        assert v.shape == (40,)


def test_a_real_signal_beats_noise_in_almost_every_replicate():
    y, season, day, scores = _panel()
    boot = two_stage_bootstrap(y, scores, season, day, n_boot=200, seed=2)
    d = delta_ci(boot, "good", "noise")
    assert d["delta"] > 0
    assert d["lo"] > 0, "a clear signal should have an interval clear of zero"
    assert d["p_a_better"] > 0.95


def test_two_identical_candidates_have_a_delta_interval_containing_zero():
    y, season, day, scores = _panel()
    same = {"a": scores["good"], "b": scores["good"].copy()}
    boot = two_stage_bootstrap(y, same, season, day, n_boot=100, seed=3)
    d = delta_ci(boot, "a", "b")
    assert d["delta"] == pytest.approx(0.0, abs=1e-12)
    assert d["lo"] <= 0 <= d["hi"]


def test_pairing_is_real_not_two_independent_draws():
    """The delta must come from the same rows, or it carries the row variance."""
    y, season, day, scores = _panel()
    boot = two_stage_bootstrap(y, scores, season, day, n_boot=150, seed=4)
    paired = np.nanstd(boot["good"] - boot["noise"])
    independent = np.sqrt(np.nanvar(boot["good"]) + np.nanvar(boot["noise"]))
    assert paired < independent, "paired spread should be tighter than independent"


def test_bootstrap_is_deterministic_for_a_seed():
    y, season, day, scores = _panel()
    a = two_stage_bootstrap(y, scores, season, day, n_boot=30, seed=7)
    b = two_stage_bootstrap(y, scores, season, day, n_boot=30, seed=7)
    for k in a:
        np.testing.assert_allclose(a[k], b[k])


def test_blocks_span_the_target_horizon():
    """Blocks shorter than the 3-day horizon would cut through the dependence."""
    assert BLOCK_DAYS > 3


def test_percentile_ci_brackets_the_values():
    lo, hi = percentile_ci(np.linspace(0.0, 1.0, 1001))
    assert 0.0 <= lo < hi <= 1.0
    assert lo == pytest.approx(0.025, abs=0.01)


def test_percentile_ci_ignores_degenerate_replicates():
    lo, hi = percentile_ci(np.array([0.2, np.nan, 0.4, np.nan]))
    assert np.isfinite(lo) and np.isfinite(hi)


def test_delete_one_season_drops_exactly_one_season_each_time():
    y, season, day, scores = _panel()
    out = delete_one_season(y, scores, season)
    assert set(out) == set(np.unique(season))
    for s, aps in out.items():
        assert set(aps) == {"good", "noise"}


def test_delete_one_season_exposes_a_single_season_carrying_the_result():
    """A candidate that only works in one season must visibly collapse."""
    y, season, day, scores = _panel()
    # a candidate that is informative in 2019 alone
    one = np.where(season == 2019, y * 0.9 + 0.05, 0.5)
    out = delete_one_season(y, {"one_season": one}, season)
    without_2019 = out[2019]["one_season"]
    with_2019 = min(out[s]["one_season"] for s in out if s != 2019)
    assert without_2019 < with_2019


def test_season_summary_reports_pooled_and_typical_separately():
    y, season, day, scores = _panel()
    per, agg = season_summary(y, scores, season)
    assert set(per) == set(np.unique(season))
    for k in ("good", "noise"):
        assert "mean" in agg[k] and "median" in agg[k]
    assert agg["good"]["mean"] > agg["noise"]["mean"]


def test_seasons_with_no_positives_are_skipped_not_scored_as_zero():
    y, season, day, scores = _panel(n_seasons=3)
    y = y.copy()
    y[season == 2021] = 0.0  # a season with no flooding at all
    per, _ = season_summary(y, scores, season)
    assert 2021 not in per, "a season with no positives has no AP to report"
