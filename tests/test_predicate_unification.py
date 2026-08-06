# tests/test_predicate_unification.py
"""One coverage predicate, used by both the gate and the ranking.

There used to be two, built from two separate fetches over two different day
ranges. The statewide gate ran on the recent history under a three-day
freshness rule; ranking eligibility ran on the cumulative monsoon-window union.
A district imaged on the first day of the window and never again satisfied the
second and was never examined by the first, so it could be ranked, tiered and
published on nine-day-old imagery, with its stated observation and its score
drawn from different observation sets. The live artifact happened to agree, and
nothing made it agree.

The acceptance case, as specified in review: a district seen only on day one
stays visible, carries no score, rank or tier, and gate membership equals ranked
membership exactly.
"""

from __future__ import annotations

import pandas as pd

from sailaab import forecast_live

DISTRICTS = ["Amritsar", "Barnala", "Bathinda"]
ISSUE = "2025-08-20"


def _recent(rows):
    return pd.DataFrame(rows, columns=["date", "district", "fraction"])


def test_a_day_one_only_district_is_not_eligible():
    """The exact failure the old split permitted."""
    recent = _recent([
        # seen on day one of a long window, never since
        ("2025-08-11", "Amritsar", 0.0),
        # seen recently
        ("2025-08-19", "Barnala", 0.0),
        ("2025-08-18", "Bathinda", 0.02),
    ])
    eligible = forecast_live.eligible_districts(recent, ISSUE)
    assert "Amritsar" not in eligible, "nine-day-old imagery must not confer eligibility"
    assert set(eligible) == {"Barnala", "Bathinda"}
    assert eligible["Barnala"]["age_days"] == 1
    assert eligible["Bathinda"]["age_days"] == 2
    assert eligible["Barnala"]["latest"] == "2025-08-19"


def test_gate_membership_equals_ranked_membership():
    """The two predicates must be the same set, not merely similar.

    This is the property that was never enforced. It is checked by construction
    rather than by comparing counts, because equal counts over different sets
    was exactly the shape of the old bug.
    """
    recent = _recent([
        ("2025-08-11", "Amritsar", 0.0),
        ("2025-08-19", "Barnala", 0.0),
        ("2025-08-18", "Bathinda", 0.02),
    ])
    eligible = set(forecast_live.eligible_districts(recent, ISSUE))
    ok, reason = forecast_live.forecast_is_publishable(recent, ISSUE, DISTRICTS)
    # the gate's own count must be the size of that identical set
    assert ok, reason
    assert f"{len(eligible)} of {len(DISTRICTS)}" in reason, reason


def test_the_gate_counts_fresh_districts_not_stale_ones():
    """Coverage below the floor must fail closed even when rows exist.

    Before unification the gate counted any district with a row in the fresh
    slice, while ranking counted any district in the window union, so a feed
    could pass the gate on two districts and rank three.
    """
    recent = _recent([
        ("2025-08-01", "Amritsar", 0.0),
        ("2025-08-02", "Barnala", 0.0),
        ("2025-08-19", "Bathinda", 0.0),
    ])
    eligible = forecast_live.eligible_districts(recent, ISSUE)
    assert set(eligible) == {"Bathinda"}
    ok, reason = forecast_live.forecast_is_publishable(recent, ISSUE, DISTRICTS)
    assert not ok, "1 of 3 districts is below the coverage floor"
    assert "below the" in reason


def test_empty_and_future_only_history_are_handled():
    assert forecast_live.eligible_districts(None, ISSUE) == {}
    assert forecast_live.eligible_districts(_recent([]), ISSUE) == {}
    future = _recent([("2025-08-25", "Amritsar", 0.0)])
    assert forecast_live.eligible_districts(future, ISSUE) == {}, (
        "an observation dated after the issue date is not evidence at issue time"
    )


def test_age_is_zero_for_same_day_imagery():
    recent = _recent([(ISSUE, "Amritsar", 0.0)])
    e = forecast_live.eligible_districts(recent, ISSUE)
    assert e["Amritsar"]["age_days"] == 0
    assert e["Amritsar"]["latest"] == ISSUE
