# tests/test_forecast_v2.py
import numpy as np
import pandas as pd
import pytest

from sailaab.forecast_v2 import (
    block_bootstrap_ci,
    brier_skill,
    fold_safe_prior,
    group_topk,
    quiet_window_alert_rate,
    recall_at_k,
)


# --- fold_safe_prior ----------------------------------------------------------
def _frame():
    rows = []
    for year in (2020, 2021, 2022):
        for d in ("A", "B"):
            frac = 0.05 if (d == "A" or year == 2022) else 0.001
            rows.append(
                {
                    "year": year,
                    "district": d,
                    "window_start": f"{year}-08-14",
                    "flooded_fraction": frac,
                    "flooded_ha": frac * 1000,
                }
            )
    return pd.DataFrame(rows)


def test_prior_uses_only_training_years():
    df = _frame()
    p = fold_safe_prior(df, train_years=[2020, 2021])
    # B floods only in 2022, which is excluded, so its event count must be 0
    b = p[p["district"] == "B"].iloc[0]
    assert b["prior_seasons_with_fraction_gt2pct"] == 0


def test_prior_changes_when_holdout_year_changes():
    df = _frame()
    a = fold_safe_prior(df, train_years=[2020, 2021])
    b = fold_safe_prior(df, train_years=[2020, 2022])
    va = a[a["district"] == "B"]["prior_seasons_with_fraction_gt2pct"].iloc[0]
    vb = b[b["district"] == "B"]["prior_seasons_with_fraction_gt2pct"].iloc[0]
    assert va != vb


def test_holdout_year_label_cannot_move_the_prior():
    # The leak test: mutate ONLY the held-out year's labels and assert the
    # fold's prior is byte-identical. This is the property the shipped
    # pipeline violated.
    df = _frame()
    base = fold_safe_prior(df, train_years=[2020, 2021])
    tampered = df.copy()
    m = tampered["year"] == 2022
    tampered.loc[m, "flooded_fraction"] = 0.99
    tampered.loc[m, "flooded_ha"] = 990.0
    after = fold_safe_prior(tampered, train_years=[2020, 2021])
    pd.testing.assert_frame_equal(base, after)


def test_prior_covers_every_district_even_if_never_flooded():
    df = _frame()
    df.loc[df["district"] == "B", "flooded_fraction"] = 0.0
    p = fold_safe_prior(df, train_years=[2020, 2021])
    assert set(p["district"]) == {"A", "B"}
    assert (p["prior_seasons_with_fraction_gt2pct"] >= 0).all()


def test_prior_rejects_empty_training_set():
    with pytest.raises(ValueError, match="no training years"):
        fold_safe_prior(_frame(), train_years=[])


# --- group_topk / recall_at_k -------------------------------------------------
def _scored():
    # one window, 4 districts, 1 positive ranked 2nd
    return (
        np.array([0, 1, 0, 0]),
        np.array([0.9, 0.8, 0.2, 0.1]),
        np.array(["w1"] * 4),
    )


def test_group_topk_counts_hits_within_group():
    y, p, g = _scored()
    out = group_topk(y, p, g, k=2)
    row = out.iloc[0]
    assert row["n_pos"] == 1
    assert row["hits"] == 1
    assert row["precision_at_k"] == pytest.approx(0.5)
    assert row["recall_at_k"] == pytest.approx(1.0)


def test_group_topk_misses_when_positive_ranked_below_k():
    y = np.array([0, 0, 1, 0])
    p = np.array([0.9, 0.8, 0.2, 0.1])
    g = np.array(["w1"] * 4)
    out = group_topk(y, p, g, k=2)
    assert out.iloc[0]["hits"] == 0
    assert out.iloc[0]["recall_at_k"] == pytest.approx(0.0)


def test_recall_at_k_ignores_windows_with_no_positive():
    # A quiet window has undefined recall; including it as 0 would understate
    # skill, including it as 1 would overstate it. It must be excluded.
    y = np.array([0, 1, 0, 0, 0, 0])
    p = np.array([0.1, 0.9, 0.2, 0.5, 0.4, 0.3])
    g = np.array(["w1", "w1", "w1", "w2", "w2", "w2"])
    assert recall_at_k(y, p, g, k=1) == pytest.approx(1.0)


def test_recall_at_k_is_nan_without_any_positive():
    y = np.zeros(4)
    p = np.array([0.4, 0.3, 0.2, 0.1])
    g = np.array(["w1"] * 4)
    assert np.isnan(recall_at_k(y, p, g, k=2))


def test_group_topk_k_larger_than_group_is_clamped():
    y, p, g = _scored()
    out = group_topk(y, p, g, k=99)
    assert out.iloc[0]["hits"] == 1
    assert out.iloc[0]["k_used"] == 4


def test_group_topk_breaks_ties_without_favouring_positives():
    # All-equal scores must not let the positive float to the top; a model
    # that separates nothing must score like a random pick, not perfectly.
    y = np.array([0, 0, 0, 1])
    p = np.array([0.5, 0.5, 0.5, 0.5])
    g = np.array(["w1"] * 4)
    assert group_topk(y, p, g, k=1).iloc[0]["hits"] == 0


# --- quiet_window_alert_rate --------------------------------------------------
def test_quiet_window_alert_rate_counts_false_alerts():
    y = np.array([0, 0, 1, 0])
    p = np.array([0.9, 0.1, 0.9, 0.1])
    g = np.array(["quiet", "quiet", "event", "event"])
    # only the quiet window counts; 1 of its 2 districts is over threshold
    assert quiet_window_alert_rate(y, p, g, threshold=0.5) == pytest.approx(0.5)


def test_quiet_window_alert_rate_is_nan_without_quiet_windows():
    y = np.array([1, 0])
    p = np.array([0.9, 0.1])
    g = np.array(["event", "event"])
    assert np.isnan(quiet_window_alert_rate(y, p, g, threshold=0.5))


# --- brier_skill --------------------------------------------------------------
def test_brier_skill_positive_when_better_than_reference():
    y = np.array([1, 0, 1, 0])
    good = np.array([0.9, 0.1, 0.9, 0.1])
    ref = np.array([0.5, 0.5, 0.5, 0.5])
    assert brier_skill(y, good, ref) > 0


def test_brier_skill_zero_against_itself():
    y = np.array([1, 0, 1, 0])
    p = np.array([0.7, 0.2, 0.6, 0.3])
    assert brier_skill(y, p, p) == pytest.approx(0.0)


def test_brier_skill_negative_when_worse():
    y = np.array([1, 0])
    bad = np.array([0.0, 1.0])
    ref = np.array([0.5, 0.5])
    assert brier_skill(y, bad, ref) < 0


# --- block_bootstrap_ci -------------------------------------------------------
def test_block_bootstrap_resamples_whole_years():
    by_year = {2019: [0.0], 2023: [1.0], 2025: [1.0]}
    lo, hi = block_bootstrap_ci(by_year, n=400, seed=1)
    assert lo <= hi
    assert 0.0 <= lo and hi <= 1.0


def test_block_bootstrap_is_deterministic_under_seed():
    by_year = {2019: [0.1, 0.2], 2023: [0.8], 2025: [0.6, 0.7]}
    a = block_bootstrap_ci(by_year, n=200, seed=7)
    b = block_bootstrap_ci(by_year, n=200, seed=7)
    assert a == b


def test_block_bootstrap_rejects_too_few_blocks():
    with pytest.raises(ValueError, match="at least 2"):
        block_bootstrap_ci({2025: [1.0]}, n=100, seed=1)
