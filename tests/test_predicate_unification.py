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

    The real guarantee is structural and lives in the code: the gate calls
    eligible_districts() rather than walking the frame a second time, so the
    two cannot diverge. This test can only observe the count the gate reports,
    which is weaker than the guarantee; it is here to catch a regression that
    reintroduces a parallel walk, not to establish set equality by itself.
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


def test_a_temporal_mosaic_cannot_certify_a_district_wide_reading():
    """Union coverage is not the same observation the 95% rule requires.

    Two passes each imaging half a district, on opposite halves and different
    days, union to "100% covered". That row then published covered=True with a
    0.0 flood fraction and no observation date at all, and the map drew the
    zero. MIN_OBSERVED_FRACTION exists precisely to stop a district-wide
    certification from a partial pass; the union path re-admitted it through
    the back door.
    """
    from sailaab import nowcast as nc

    payload = nc.build_nowcast_json(
        generated_utc="2026-08-06T00:00:00Z",
        window={"core_season": True, "window_start": "2026-08-01",
                "window_end": "2026-08-10", "activates": "2026-07-01"},
        sources={},
        districts=["west", "east"],
        # what the window union reports: both fully covered, both dry
        observed={
            "west": {"covered": True, "observed_fraction": 0.0, "observed_km2": 0.0,
                     "acquisition_state": "observed", "acquisition_fraction": 1.0},
            "east": {"covered": True, "observed_fraction": 0.0, "observed_km2": 0.0,
                     "acquisition_state": "observed", "acquisition_fraction": 1.0},
        },
        # ...but the recent history has no qualifying observation for either
        last_seen={},
    )
    for row in payload["districts"]:
        assert row["covered"] is False, (
            f"{row['district']} certified as covered with nothing to point at"
        )
        assert row["observed_fraction_window"] is None, (
            f"{row['district']} published a district-wide fraction from a mosaic"
        )
        assert row["observed_km2"] is None


def test_a_district_with_a_recent_observation_keeps_its_coverage():
    """The rule above must not blank districts that genuinely were imaged."""
    from sailaab import nowcast as nc

    payload = nc.build_nowcast_json(
        generated_utc="2026-08-06T00:00:00Z",
        window={"core_season": True, "window_start": "2026-08-01",
                "window_end": "2026-08-10", "activates": "2026-07-01"},
        sources={},
        districts=["west"],
        observed={
            "west": {"covered": True, "observed_fraction": 0.02, "observed_km2": 5.0,
                     "acquisition_state": "observed", "acquisition_fraction": 1.0},
        },
        last_seen={"west": {"latest": "2026-08-05", "age_days": 1}},
    )
    row = payload["districts"][0]
    assert row["covered"] is True
    assert row["observed_fraction_window"] == 0.02
    assert row["latest_input"] == "2026-08-05"
