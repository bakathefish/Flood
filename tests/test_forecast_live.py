# tests/test_forecast_live.py
import numpy as np
import pandas as pd
import pytest

from sailaab.forecast_live import (
    FEATURE_ORDER,
    build_live_features,
    rank_and_tier,
    season_day_index,
    transparent_score,
)

DISTRICTS = ["A", "B", "C", "D", "E", "F"]
ADJ = {"A": ["B"], "B": ["A", "C"], "C": ["B"], "D": ["E"], "E": ["D"], "F": []}
PRIORS = {
    d: {"prior_wet_days": float(i), "prior_max_fraction": 0.01 * i}
    for i, d in enumerate(DISTRICTS)
}
CLIMO = {(d, w): 0.01 * (i + 1) for i, d in enumerate(DISTRICTS) for w in range(16)}


def _recent(rows):
    """rows: {(day, district): fraction}"""
    return pd.DataFrame(
        [{"date": k[0], "district": k[1], "fraction": v} for k, v in rows.items()]
    )


# --- season_day_index ---------------------------------------------------------
def test_season_day_index_is_zero_on_the_first_day():
    assert season_day_index("2026-06-15") == 0


def test_season_day_index_counts_days_since_season_start():
    assert season_day_index("2026-06-25") == 10
    assert season_day_index("2026-08-14") == 60


def test_season_day_index_is_negative_before_the_season():
    assert season_day_index("2026-06-01") < 0


# --- build_live_features ------------------------------------------------------
def test_features_are_in_the_declared_order_and_cover_every_district():
    recent = _recent({("2026-08-14", d): 0.0 for d in DISTRICTS})
    X = build_live_features(recent, "2026-08-14", DISTRICTS, PRIORS, CLIMO, ADJ)
    assert list(X.columns) == list(FEATURE_ORDER)
    assert list(X.index) == DISTRICTS


def test_frac_now_is_todays_value_not_an_older_one():
    recent = _recent(
        {("2026-08-13", "A"): 0.9, ("2026-08-14", "A"): 0.1}
        | {("2026-08-14", d): 0.0 for d in DISTRICTS if d != "A"}
    )
    X = build_live_features(recent, "2026-08-14", DISTRICTS, PRIORS, CLIMO, ADJ)
    assert X.loc["A", "frac_now"] == pytest.approx(0.1)
    assert X.loc["A", "frac_max3d"] == pytest.approx(0.9)


def test_neighbour_sees_adjacent_water_and_never_the_district_itself():
    recent = _recent(
        {("2026-08-14", "A"): 0.5} | {("2026-08-14", d): 0.0 for d in DISTRICTS[1:]}
    )
    X = build_live_features(recent, "2026-08-14", DISTRICTS, PRIORS, CLIMO, ADJ)
    assert X.loc["B", "neighbour"] == pytest.approx(0.5)  # B touches A
    assert X.loc["A", "neighbour"] == pytest.approx(0.0)  # A must not see itself
    assert X.loc["D", "neighbour"] == pytest.approx(0.0)  # D is not adjacent to A


def test_neighbour_looks_back_three_days():
    recent = _recent(
        {("2026-08-12", "A"): 0.7}
        | {("2026-08-14", d): 0.0 for d in DISTRICTS}
    )
    X = build_live_features(recent, "2026-08-14", DISTRICTS, PRIORS, CLIMO, ADJ)
    assert X.loc["B", "neighbour"] == pytest.approx(0.7)


def test_future_days_are_ignored():
    """A forecast issued today must not be able to see tomorrow, even if a
    later observation somehow reached the frame."""
    recent = _recent(
        {("2026-08-14", "A"): 0.0, ("2026-08-15", "A"): 0.99}
        | {("2026-08-14", d): 0.0 for d in DISTRICTS if d != "A"}
    )
    X = build_live_features(recent, "2026-08-14", DISTRICTS, PRIORS, CLIMO, ADJ)
    assert X.loc["A", "frac_now"] == pytest.approx(0.0)
    assert X.loc["A", "frac_max3d"] == pytest.approx(0.0)
    assert X.loc["B", "neighbour"] == pytest.approx(0.0)


def test_missing_district_observation_is_nan_not_zero():
    """An unimaged district must not look dry to the model."""
    recent = _recent({("2026-08-14", d): 0.0 for d in DISTRICTS if d != "C"})
    X = build_live_features(recent, "2026-08-14", DISTRICTS, PRIORS, CLIMO, ADJ)
    assert np.isnan(X.loc["C", "frac_now"])


def test_unknown_district_prior_is_nan_not_fabricated():
    recent = _recent({("2026-08-14", d): 0.0 for d in DISTRICTS})
    X = build_live_features(recent, "2026-08-14", DISTRICTS, {}, CLIMO, ADJ)
    assert X["prior_wet_days"].isna().all()


def test_day_of_season_matches_the_issue_date():
    recent = _recent({("2026-08-14", d): 0.0 for d in DISTRICTS})
    X = build_live_features(recent, "2026-08-14", DISTRICTS, PRIORS, CLIMO, ADJ)
    assert (X["day_of_season"] == season_day_index("2026-08-14")).all()


# --- transparent_score --------------------------------------------------------
def test_transparent_score_rewards_water_climatology_and_neighbours():
    X = pd.DataFrame(
        {
            "frac_now": [0.0, 0.004, 0.0],
            "neighbour": [0.0, 0.0, 0.5],
            "season_climo": [0.9, 0.0, 0.0],
        },
        index=["climo_high", "wet", "neighbour_wet"],
    )
    s = transparent_score(X)
    assert s.notna().all()
    # each district leads on exactly one component, so all three outrank a
    # district that leads on none
    X2 = pd.concat([X, pd.DataFrame({"frac_now": [0.0], "neighbour": [0.0],
                                     "season_climo": [0.0]}, index=["nothing"])])
    s2 = transparent_score(X2)
    assert s2["nothing"] == s2.min()


def test_transparent_score_handles_all_missing_without_raising():
    X = pd.DataFrame(
        {"frac_now": [np.nan, np.nan], "neighbour": [np.nan, np.nan],
         "season_climo": [np.nan, np.nan]},
        index=["A", "B"],
    )
    s = transparent_score(X)
    assert len(s) == 2


# --- rank_and_tier ------------------------------------------------------------
def test_top_k_of_the_transparent_rule_becomes_the_watch_set():
    model = pd.Series([0.1, 0.2, 0.3, 0.4, 0.5, 0.6], index=DISTRICTS)
    trans = pd.Series([6.0, 5.0, 4.0, 3.0, 2.0, 1.0], index=DISTRICTS)
    out = rank_and_tier(model, trans, k=2)
    watch = {r["district"] for r in out if r["tier"] == "watch"}
    assert watch == {"A", "B"}  # top 2 of the transparent rule


def test_model_top_k_outside_the_watch_set_is_elevated():
    model = pd.Series([0.1, 0.2, 0.3, 0.4, 0.5, 0.6], index=DISTRICTS)
    trans = pd.Series([6.0, 5.0, 4.0, 3.0, 2.0, 1.0], index=DISTRICTS)
    out = rank_and_tier(model, trans, k=2)
    tiers = {r["district"]: r["tier"] for r in out}
    assert tiers["F"] == "elevated"  # model's top pick, not the rule's
    assert tiers["E"] == "elevated"
    assert tiers["C"] == "low"


def test_rank_is_by_model_score_descending():
    model = pd.Series([0.1, 0.9, 0.5, 0.0, 0.2, 0.3], index=DISTRICTS)
    trans = pd.Series(range(6), index=DISTRICTS, dtype=float)
    out = rank_and_tier(model, trans, k=2)
    assert out[0]["district"] == "B"
    assert out[0]["rank"] == 1
    assert [r["rank"] for r in out] == sorted(r["rank"] for r in out)


def test_all_nan_model_scores_still_produce_rows_and_no_watch_from_the_model():
    model = pd.Series([np.nan] * 6, index=DISTRICTS)
    trans = pd.Series([6.0, 5.0, 4.0, 3.0, 2.0, 1.0], index=DISTRICTS)
    out = rank_and_tier(model, trans, k=2)
    assert len(out) == 6
    assert all(r["p_event"] is None for r in out)
    # the transparent rule still works when the model is unavailable
    assert {r["district"] for r in out if r["tier"] == "watch"} == {"A", "B"}


# --- excitation and the threshold operating point ------------------------------
def test_excitation_features_are_present_when_a_threshold_is_given():
    recent = _recent(
        {("2026-08-10", "A"): 0.9}
        | {("2026-08-14", d): 0.0 for d in DISTRICTS}
    )
    X = build_live_features(
        recent, "2026-08-14", DISTRICTS, PRIORS, CLIMO, ADJ, threshold=0.005
    )
    assert X.loc["A", "excite_h0"] > 0  # A flooded four days ago
    assert X.loc["B", "excite_h1"] > 0  # B touches A
    assert X.loc["C", "excite_h2"] > 0  # C is two hops away
    assert X.loc["F", "excite_h1"] == pytest.approx(0.0)  # F is isolated


def test_excitation_cannot_see_past_the_issue_date():
    recent = _recent(
        {("2026-08-14", d): 0.0 for d in DISTRICTS} | {("2026-08-15", "A"): 0.9}
    )
    X = build_live_features(
        recent, "2026-08-14", DISTRICTS, PRIORS, CLIMO, ADJ, threshold=0.005
    )
    assert X.loc["A", "excite_h0"] == pytest.approx(0.0)
    assert X.loc["B", "excite_h1"] == pytest.approx(0.0)


def test_threshold_operating_point_drives_the_watch_set():
    model = pd.Series([0.9, 0.8, 0.1, 0.05, 0.02, 0.01], index=DISTRICTS)
    trans = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0, 6.0], index=DISTRICTS)
    out = rank_and_tier(model, trans, k=5, alert_threshold=0.5)
    tiers = {r["district"]: r["tier"] for r in out}
    # only the two districts over the threshold are warned, regardless of how
    # the transparent rule happens to order the rest
    assert {d for d, t in tiers.items() if t == "watch"} == {"A", "B"}


def test_a_quiet_day_produces_no_watch_at_all():
    """The whole point of a threshold: on a calm day nobody is warned."""
    model = pd.Series([0.001] * 6, index=DISTRICTS)
    trans = pd.Series(range(6), index=DISTRICTS, dtype=float)
    out = rank_and_tier(model, trans, k=5, alert_threshold=0.5)
    assert all(r["tier"] != "watch" for r in out)


# --- the safety gate ----------------------------------------------------------
def test_no_imagery_means_unknown_not_all_clear():
    """The defect this guards is the worst one a warning system can have: a
    failed or empty satellite fetch scoring priors and climatology alone, then
    publishing that nothing is above the alert threshold. Absence of imagery is
    absence of knowledge, never an all-clear."""
    from sailaab.forecast_live import forecast_is_publishable

    empty = pd.DataFrame(columns=["date", "district", "fraction"])
    ok, reason = forecast_is_publishable(empty, "2026-08-14", DISTRICTS)
    assert ok is False
    assert "no" in reason.lower()


def test_partial_imagery_below_the_floor_is_not_publishable():
    # one district out of six seen today is not a basis for a statewide board
    recent = _recent({("2026-08-14", "A"): 0.0})
    ok, _ = forecast_is_publishable_helper(recent, "2026-08-14", DISTRICTS)
    assert ok is False


def test_full_imagery_is_publishable():
    recent = _recent({("2026-08-14", d): 0.0 for d in DISTRICTS})
    ok, _ = forecast_is_publishable_helper(recent, "2026-08-14", DISTRICTS)
    assert ok is True


def forecast_is_publishable_helper(recent, issue, districts):
    from sailaab.forecast_live import forecast_is_publishable

    return forecast_is_publishable(recent, issue, districts)


def test_stale_imagery_is_not_publishable():
    """Imagery that stops days before the issue date cannot support a forecast
    made today, however complete it was when it arrived."""
    from sailaab.forecast_live import forecast_is_publishable

    recent = _recent({("2026-08-01", d): 0.0 for d in DISTRICTS})
    ok, reason = forecast_is_publishable(recent, "2026-08-14", DISTRICTS)
    assert ok is False
    assert "stale" in reason.lower()
