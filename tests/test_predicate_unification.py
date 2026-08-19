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


# --- the window boundary: the two predicates disagreeing completely -----------
#
# 14 Aug 2026 was the first day of a new monsoon window. Every district held an
# observation from 13 Aug, one day old and comfortably inside the freshness
# rule, so the publication gate passed on the rolling history and reported "20
# of 20 districts observed within 1 day(s)". The current window's Sentinel-1
# footprint had recorded no pass at all, so every row was built not_observed.
# The feed went out asserting both. Every scheduled monitor run from that cycle
# to the next fix failed on it, and the live site published nothing for five
# days.


def _window_boundary_payload(**over):
    """A feed shaped exactly like the 14 Aug one: fresh history, empty window."""
    from sailaab import nowcast as nc

    kwargs = dict(
        generated_utc="2026-08-14T07:22:11Z",
        window={"core_season": True, "window_start": "2026-08-14",
                "window_end": "2026-08-24", "activates": "2026-07-25"},
        sources={},
        districts=["Amritsar", "Barnala"],
        # the new window's footprint has seen nobody yet
        observed={
            n: {"covered": False, "observed_fraction": None, "observed_km2": None,
                "acquisition_state": "not_observed", "acquisition_fraction": 0.0}
            for n in ("Amritsar", "Barnala")
        },
        # ...while yesterday's observation, from the window that just ended, is
        # one day old for both
        last_seen={
            "Amritsar": {"latest": "2026-08-13", "age_days": 1},
            "Barnala": {"latest": "2026-08-13", "age_days": 1},
        },
    )
    kwargs.update(over)
    return nc.build_nowcast_json(**kwargs)


def test_an_uncovered_row_keeps_no_observation_date_from_extras():
    """The leak that made the published feed invalid for five days.

    The uncovered cleanup listed rank, tier and transparent_score, which were
    the fields that had gone wrong the previous time. latest_input and
    input_age_days were added to the payload afterwards, were not added to the
    list, and so were re-attached by the extras merge to rows the footprint had
    just declared never imaged. The consumer's rule is that an uncovered row
    states no observation at all, so the whole feed failed validation and the
    board fell closed with no disclosure behind it.
    """
    payload = _window_boundary_payload(
        p_event={"Amritsar": 0.31, "Barnala": 0.12},
        extras={
            "Amritsar": {"rank": 1, "tier": "elevated", "transparent_score": 1.5,
                         "latest_input": "2026-08-13", "input_age_days": 1},
            "Barnala": {"rank": 2, "tier": "low", "transparent_score": 0.4,
                        "latest_input": "2026-08-13", "input_age_days": 1},
        },
    )
    for row in payload["districts"]:
        assert row["covered"] is False
        for field in ("p_event", "rank", "tier", "transparent_score",
                      "latest_input", "input_age_days",
                      "observed_fraction_window", "observed_km2"):
            assert row[field] is None, (
                f"{row['district']} published {field} with no acquisition behind it"
            )


def test_the_uncovered_rule_covers_every_field_a_row_can_carry():
    """Stating the rule is only worth doing if the statement is complete.

    Pinning the constant against the row itself means a field added to the
    payload and forgotten here shows up as a failure now, rather than as an
    invalid feed on the first cycle that publishes it.
    """
    from sailaab import nowcast as nc

    row = _window_boundary_payload()["districts"][0]
    structural = {"district", "covered", "acquisition_state", "acquisition_fraction"}
    assert set(nc.UNCOVERED_NULL_FIELDS) == set(row) - structural, (
        "every non-structural field must be on the uncovered-null list"
    )


def test_publishable_districts_is_the_intersection_not_either_side():
    from sailaab import nowcast as nc

    observed = {
        "fresh_and_imaged": {"covered": True},
        "fresh_not_imaged": {"covered": False},
        "imaged_not_fresh": {"covered": True},
    }
    eligible = {"fresh_and_imaged": {}, "fresh_not_imaged": {}}
    order = ["fresh_and_imaged", "fresh_not_imaged", "imaged_not_fresh"]
    assert nc.publishable_districts(order, eligible, observed) == ["fresh_and_imaged"]


def test_the_window_boundary_leaves_nobody_publishable():
    """The precondition for withholding the forecast block entirely."""
    from sailaab import nowcast as nc

    order = ["Amritsar", "Barnala"]
    observed = {n: {"covered": False} for n in order}
    eligible = {n: {"latest": "2026-08-13", "age_days": 1} for n in order}
    assert nc.publishable_districts(order, eligible, observed) == [], (
        "a district the current window never imaged cannot carry a score, "
        "however fresh its last observation from the previous window was"
    )
