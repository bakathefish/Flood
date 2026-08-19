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

from pathlib import Path

import pandas as pd
import pytest

from sailaab import forecast_live

ROOT = Path(__file__).resolve().parents[1]

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
        # The state is half of the same claim. This test used to stop one line
        # above and so blessed a row the consumer refuses outright: `covered` is
        # defined to it as exactly `acquisition_state == "observed"`, and a row
        # withdrawing one while still asserting the other fails validation and
        # takes the whole feed down with it.
        assert row["acquisition_state"] != "observed", (
            f"{row['district']} withdrew coverage but still says it was observed"
        )
        assert row["acquisition_state"] == "unresolved"
        assert row["acquisition_fraction"] == 1.0, (
            "the footprint reading itself is evidence and is not discarded"
        )


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



def _producer_extras(names) -> dict:
    """Extras built by the producer's own code path, for the given districts.

    pipeline/nowcast.py calls exactly these two functions, so a field added to
    either reaches this fixture without anybody remembering to add it. The
    previous version listed the two freshness fields by hand, which is the
    failure being tested for, one layer out.
    """
    from sailaab import nowcast as nc

    ranked = forecast_live.rank_and_tier(
        pd.Series([0.5 - 0.1 * i for i in range(len(names))], index=list(names)),
        pd.Series([1.0] * len(names), index=list(names)),
        alert_threshold=0.9,
    )
    return nc.build_extras(
        ranked, {n: {"latest": "2026-08-13", "age_days": 1} for n in names}
    )


def test_the_uncovered_rule_covers_every_field_a_row_can_carry():
    """Stating the rule is only worth doing if the statement is complete.

    Pinning the constant against the row itself means a field added to the
    payload and forgotten here shows up as a failure now, rather than as an
    invalid feed on the first cycle that publishes it.
    """
    from sailaab import nowcast as nc

    # Built through the EXTRAS path, because that path can put fields on a row
    # that the base dict never mentions, and those are exactly the ones the
    # rule missed last time. The shape is DERIVED from rank_and_tier rather
    # than hand-copied, so a field added to the producer's ranked rows reaches
    # this pin by itself; a hand-written dict only ever pins what its author
    # already remembered, which is the failure mode being tested for.
    extras = _producer_extras(("Amritsar", "Barnala"))
    assert set(nc.EXTRAS_FIELDS) == set(next(iter(extras.values()))), (
        "EXTRAS_FIELDS and build_extras() disagree about the extras contract"
    )
    row = _window_boundary_payload(
        p_event={"Amritsar": 0.31, "Barnala": 0.12},
        extras=extras,
    )["districts"][0]
    structural = {"district", "covered", "acquisition_state", "acquisition_fraction"}
    assert set(nc.UNCOVERED_NULL_FIELDS) == set(row) - structural, (
        "every non-structural field must be on the uncovered-null list"
    )


def test_publishable_districts_is_the_intersection_not_either_side():
    from sailaab import nowcast as nc

    covered = {"covered": True, "acquisition_state": "observed",
               "acquisition_fraction": 1.0}
    observed = {
        "fresh_and_imaged": dict(covered),
        "fresh_not_imaged": {"covered": False, "acquisition_state": "not_observed",
                             "acquisition_fraction": 0.0},
        "imaged_not_fresh": dict(covered),
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


# --- producer output judged by the consumer that actually reads it -----------
def _districts_are_valid(payload) -> bool:
    """Run a payload through the REAL validator the site ships.

    Every check in this file up to here is producer-side, and producer-side
    asserts are exactly how the mosaic guard shipped a row the consumer
    refuses: the test enumerated the fields it remembered and the one it did
    not remember was the one that broke the feed. Asking the shipped validator
    removes the enumeration from the test entirely.
    """
    import json
    import shutil
    import subprocess

    if shutil.which("node") is None:
        pytest.skip("node not available")
    script = (
        "import {districtsAreValid} from './webapp/src/forecastSchema.js';"
        "let raw='';"
        "process.stdin.on('data', c => raw += c);"
        "process.stdin.on('end', () => {"
        "  const nc = JSON.parse(raw);"
        "  process.stdout.write(String("
        "    districtsAreValid(nc.districts, {issued: nc.generated_utc})));"
        "});"
    )
    proc = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=ROOT, input=json.dumps(payload), capture_output=True,
        text=True, timeout=120,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    return proc.stdout.strip() == "true"


def test_the_withdrawn_mosaic_row_is_accepted_by_the_shipped_validator():
    """The guard's output must survive the consumer, not merely satisfy us.

    It did not. `covered` was withdrawn and `acquisition_state` was left saying
    "observed", and forecastSchema.js rejects that pair outright, so a single
    district hitting this guard invalidated the entire published feed and the
    board fell closed with no disclosure behind it. That is the same five-day
    outage this file already documents, reachable by a second route.
    """
    from sailaab import nowcast as nc

    payload = nc.build_nowcast_json(
        generated_utc="2026-08-19T00:00:00Z",
        window={"core_season": True, "window_start": "2026-08-14",
                "window_end": "2026-08-24", "activates": "2026-07-25"},
        sources={},
        districts=["west", "east"],
        observed={
            "west": {"covered": True, "observed_fraction": 0.0,
                     "observed_km2": 0.0, "acquisition_state": "observed",
                     "acquisition_fraction": 1.0},
            "east": {"covered": True, "observed_fraction": 0.01,
                     "observed_km2": 3.0, "acquisition_state": "observed",
                     "acquisition_fraction": 0.98},
        },
        # the recent history holds only `east`, so `west` loses its claim
        last_seen={"east": {"latest": "2026-08-18", "age_days": 1}},
    )
    west = next(r for r in payload["districts"] if r["district"] == "west")
    assert west["covered"] is False and west["acquisition_state"] == "unresolved"
    assert _districts_are_valid(payload), (
        "the producer emitted a feed its own consumer refuses"
    )


def test_a_tier_decided_on_the_raw_score_cannot_contradict_the_published_one():
    """The feed's two statements about the same district must agree.

    p_event ships rounded to four places and the consumer re-derives the
    threshold comparison from that rounded value, so a raw score inside the
    rounding window published a tier its own score contradicted and the board
    was rejected. Picked to sit just below the threshold raw and just above it
    once rounded, which is the only interval where the two disagree.
    """
    import pandas as pd

    from sailaab import forecast_live

    threshold = 0.7916666865348816
    raw = 0.79166          # below the threshold; rounds to 0.7917, above it
    assert raw < threshold < round(raw, 4), "fixture must sit in the window"

    idx = ["a", "b"]
    ranked = forecast_live.rank_and_tier(
        pd.Series([raw, 0.1], index=idx),
        pd.Series([1.0, 0.5], index=idx),
        alert_threshold=threshold,
    )
    row = next(r for r in ranked if r["district"] == "a")
    published = round(row["p_event"], 4)
    assert (row["tier"] == "watch") == (published >= threshold), (
        f"tier {row['tier']!r} contradicts published score {published}"
    )


# --- the window the claim is about, not merely some recent window ------------
def test_a_previous_window_observation_cannot_certify_this_window():
    """The mosaic guard checked membership and not the date.

    In the first days of a window the rolling history still reaches back into
    the window that just ended, so a district can satisfy the three-day
    freshness rule on an observation taken BEFORE this window opened. If the
    current window covered it only as a mosaic of partial passes, the row then
    published a district-wide window fraction earned by exactly the temporal
    mosaic MIN_OBSERVED_FRACTION forbids, with its stated evidence dated
    outside the window it was certifying. Membership in `last_seen` was true
    the whole time, so the guard let it through.
    """
    from sailaab import nowcast as nc

    window = {"core_season": True, "window_start": "2026-08-14",
              "window_end": "2026-08-24", "activates": "2026-07-25"}
    observed = {
        # the footprint union over the window's days reaches 95%, by mosaic
        "west": {"covered": True, "observed_fraction": 0.0, "observed_km2": 0.0,
                 "acquisition_state": "observed", "acquisition_fraction": 0.99},
        "east": {"covered": True, "observed_fraction": 0.02, "observed_km2": 4.0,
                 "acquisition_state": "observed", "acquisition_fraction": 1.0},
    }
    last_seen = {
        # one day old and inside the freshness rule, but the PREVIOUS window
        "west": {"latest": "2026-08-13", "age_days": 1},
        "east": {"latest": "2026-08-15", "age_days": 1},
    }
    eligible = {"west": {}, "east": {}}

    assert nc.publishable_districts(
        ["west", "east"], eligible, observed,
        last_seen=last_seen, window_start=window["window_start"],
    ) == ["east"], "a pre-window observation cannot make a district scorable"

    payload = nc.build_nowcast_json(
        generated_utc="2026-08-15T00:00:00Z",
        window=window, sources={}, districts=["west", "east"],
        observed=observed, last_seen=last_seen,
        p_event={"west": 0.4, "east": 0.2},
        extras={"east": {"rank": 1, "tier": "elevated", "transparent_score": 1.0,
                         "latest_input": "2026-08-15", "input_age_days": 0}},
    )
    rows = {r["district"]: r for r in payload["districts"]}
    assert rows["west"]["p_event"] is None, "scored on a pre-window observation"
    assert rows["west"]["covered"] is False
    assert rows["west"]["observed_fraction_window"] is None
    assert rows["east"]["p_event"] == 0.2, "the in-window district still scores"
    assert _districts_are_valid(payload)


def test_covered_and_its_state_cannot_be_set_independently():
    """A caller that sets one and not the other must not publish a score.

    `covered: True` with no acquisition_state emitted state "unknown" beside a
    score, which the validator rejects outright, so a single such row took the
    whole feed down. The producer does not repair the contradiction by
    upgrading the state to match the flag, because that would invent an
    observation; it withdraws the claim.
    """
    from sailaab import nowcast as nc

    payload = nc.build_nowcast_json(
        generated_utc="2026-08-19T00:00:00Z",
        window={"core_season": True, "window_start": "2026-08-14",
                "window_end": "2026-08-24", "activates": "2026-07-25"},
        sources={},
        districts=["ghost"],
        # the shape a fixture reaches for: the flag alone
        observed={"ghost": {"covered": True, "observed_fraction": 0.0,
                            "observed_km2": 0.0}},
        p_event={"ghost": 0.9},
    )
    row = payload["districts"][0]
    assert row["covered"] is False, "a coverage flag with no acquisition behind it"
    assert row["p_event"] is None
    assert _districts_are_valid(payload), (
        "the producer emitted a feed its own consumer refuses"
    )


def test_extras_cannot_overwrite_a_field_they_do_not_own():
    """The merge ran after the coverage decision and before a guard that only
    fires on uncovered rows, so on a COVERED row extras could overwrite the
    acquisition_state that coverage_is_earned() had just settled, and the
    payload would go out contradicting itself with nothing to catch it."""
    from sailaab import nowcast as nc

    payload = nc.build_nowcast_json(
        generated_utc="2026-08-19T00:00:00Z",
        window={"core_season": True, "window_start": "2026-08-14",
                "window_end": "2026-08-24", "activates": "2026-07-25"},
        sources={},
        districts=["west"],
        observed={"west": {"covered": True, "observed_fraction": 0.01,
                           "observed_km2": 2.0, "acquisition_state": "observed",
                           "acquisition_fraction": 1.0}},
        last_seen={"west": {"latest": "2026-08-18", "age_days": 1}},
        p_event={"west": 0.3},
        extras={"west": {
            "rank": 1, "tier": "elevated", "transparent_score": 1.0,
            "latest_input": "2026-08-18", "input_age_days": 1,
            # fields extras has no business setting
            "acquisition_state": "not_observed",
            "acquisition_fraction": 0.0,
            "covered": False,
            "district": "somewhere else",
        }},
    )
    row = payload["districts"][0]
    assert row["district"] == "west"
    assert row["covered"] is True
    assert row["acquisition_state"] == "observed", (
        "extras overwrote the state the coverage decision had settled"
    )
    assert row["acquisition_fraction"] == 1.0
    assert row["rank"] == 1 and row["tier"] == "elevated", "owned fields still land"
    assert _districts_are_valid(payload)


def test_coverage_cannot_be_granted_without_saying_which_window():
    """window_start used to be optional, and optional meant the date test was
    skipped, which grants coverage with no window proof at all. A caller that
    has a history to check against must say what it is checking against."""
    from sailaab import nowcast as nc

    observed = {"west": {"covered": True, "acquisition_state": "observed",
                         "acquisition_fraction": 1.0}}
    last_seen = {"west": {"latest": "2026-08-18", "age_days": 1}}
    with pytest.raises(ValueError, match="window_start is required"):
        nc.coverage_is_earned("west", observed, last_seen, None)

    # ...and it still answers normally once told.
    assert nc.coverage_is_earned("west", observed, last_seen, "2026-08-14") is True
    assert nc.coverage_is_earned("west", observed, last_seen, "2026-08-19") is False
