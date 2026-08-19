# tests/test_monitor_artifact.py
"""The committed monitor/nowcast.json is a published artifact; gate it.

Nothing was reading it. The pipeline that writes it was tested, the page that
renders it was tested, and the file itself — the thing actually served to every
reader between one CI run and the next — was checked by eye. That is how it
came to sit in the repository still describing rain and reservoirs as model
features after they had been removed from the model.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from sailaab import forecast_live

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "monitor" / "nowcast.json"
TIERS = {"watch", "elevated", "low"}


@pytest.fixture(scope="module")
def payload():
    assert ARTIFACT.exists(), "monitor/nowcast.json is not committed"
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))


def test_top_level_schema(payload):
    for key in ("generated_utc", "window_start", "window_end", "core_season",
                "activates", "sources", "districts", "notes"):
        assert key in payload, f"missing {key}"
    assert payload["core_season"] is None or isinstance(payload["core_season"], bool)
    assert isinstance(payload["districts"], list) and payload["districts"]


def test_sources_use_the_migrated_keys(payload):
    """`rain` and `reservoirs` sat beside the forecast and read as its inputs."""
    src = payload["sources"]
    assert "forecast_inputs" in src
    assert "rain" not in src, "legacy source key still published"
    assert "reservoirs" not in src, "legacy source key still published"


def test_notes_do_not_claim_rain_or_reservoirs_are_model_features(payload):
    n = payload["notes"].lower()
    for banned in ("rain features", "reservoir storage/delta features",
                   "ingests the missing values", "trained on imd"):
        assert banned not in n, f"{banned!r} still published in notes"


ACQ_STATES = {"observed", "partial", "not_observed", "unresolved", "unknown"}


def test_every_district_row_is_internally_consistent(payload):
    for d in payload["districts"]:
        assert isinstance(d.get("district"), str) and d["district"]
        assert isinstance(d.get("covered"), bool), d["district"]
        if not d["covered"]:
            # A district nobody imaged must carry no operational output at all.
            # observed_fraction_window and transparent_score belong on this list
            # and were left off it: an unimaged district could publish a flood
            # fraction, which is a measurement of imagery that does not exist.
            for field in ("p_event", "rank", "tier", "observed_km2",
                          "observed_fraction_window", "transparent_score"):
                assert d.get(field) is None, f"{d['district']} has {field} uncovered"
        else:
            p = d.get("p_event")
            if p is not None:
                assert isinstance(p, (int, float)) and 0.0 <= p <= 1.0, d["district"]
                assert d.get("tier") in TIERS, d["district"]
                r = d.get("rank")
                assert isinstance(r, int) and r >= 1, d["district"]


def test_every_row_states_its_acquisition_and_agrees_with_covered(payload):
    """`covered` is defined as "the footprint covered this district", so the two
    fields describe one fact and must not disagree. They arrived after this file
    was written and went unchecked, which let a row claim coverage it did not
    have."""
    for d in payload["districts"]:
        state = d.get("acquisition_state")
        assert state in ACQ_STATES, f"{d['district']} has acquisition_state {state!r}"
        frac = d.get("acquisition_fraction")
        assert frac is None or (isinstance(frac, (int, float)) and 0.0 <= frac <= 1.0), (
            f"{d['district']} has acquisition_fraction {frac!r}"
        )
        assert d["covered"] == (state == "observed"), (
            f"{d['district']} says covered={d['covered']} beside state={state!r}"
        )


def test_ranks_are_unique_and_agree_with_the_scores(payload):
    scored = [d for d in payload["districts"] if d.get("p_event") is not None]
    if not scored:
        pytest.skip("no scored districts in the committed artifact")
    ranks = [d["rank"] for d in scored]
    assert len(set(ranks)) == len(ranks), "duplicate ranks published"
    by_rank = sorted(scored, key=lambda d: d["rank"])
    for a, b in zip(by_rank, by_rank[1:]):
        assert a["p_event"] >= b["p_event"], (
            f"rank order contradicts scores at {a['district']} / {b['district']}"
        )


def test_forecast_block_is_honest_when_present(payload):
    fc = payload.get("forecast")
    if not fc:
        return
    if fc.get("status") == "unavailable":
        assert "all-clear" in fc.get("note", "").lower()
        return
    assert fc["horizon_days"] == forecast_live.STATE_DAYS
    t = fc["alert_threshold"]
    assert isinstance(t, (int, float)) and 0.0 <= t <= 1.0
    assert "not a calibrated probability" in fc["calibration"]
    # the retracted figures must never reappear in the published feed
    blob = json.dumps(fc)
    for banned in ("96%", "four alerts", "0.549"):
        assert banned not in blob, f"{banned!r} back in the published feed"


def test_the_coverage_line_counts_the_rows_beside_it(payload):
    """The block's coverage sentence must describe the published rows.

    It used to carry the publication gate's count, which is a different and
    larger set: the gate counts districts holding a recent observation anywhere
    in the rolling history, while a row is scored only if that observation also
    falls inside this window and the footprint covered the district. The feed
    could therefore state "20 of 20 districts observed" directly above five
    scored rows, and both sentences were true of different questions.
    """
    fc = payload.get("forecast") or {}
    coverage = fc.get("coverage")
    if fc.get("status") == "unavailable" or not coverage:
        pytest.skip("no forecast published this cycle")
    m = re.match(r"(\d+) of (\d+)", coverage)
    assert m, f"coverage line does not open with a count: {coverage!r}"
    stated, total = int(m.group(1)), int(m.group(2))
    scored = [d for d in payload["districts"] if d.get("p_event") is not None]
    assert total == len(payload["districts"]), (
        f"coverage line totals {total} districts, feed carries "
        f"{len(payload['districts'])}"
    )
    assert stated == len(scored), (
        f"coverage line claims {stated} scored, feed carries {len(scored)}"
    )


def _coverage_counts(coverage: str, districts: list) -> tuple[int, int, int]:
    m = re.match(r"(\d+) of (\d+)", coverage)
    assert m, f"coverage line does not open with a count: {coverage!r}"
    scored = [d for d in districts if d.get("p_event") is not None]
    return int(m.group(1)), int(m.group(2)), len(scored)


def test_the_coverage_rule_runs_on_a_board_shaped_payload():
    """The artifact test above skips whenever no forecast was published, which
    on a quiet cycle is every run, so the rule would go unexercised for days at
    a time and its own imports would not even be reached. This runs it against
    a payload that always carries a board."""
    from sailaab import nowcast as nc

    districts = [
        {"district": "a", "p_event": 0.4},
        {"district": "b", "p_event": 0.1},
        {"district": "c", "p_event": None},
    ]
    n_scored = len([d for d in districts if d["p_event"] is not None])

    # The sentence is DERIVED from the rows through the producer's own
    # formatter, not copied. Hard-coding both sides made the test agree with
    # itself: it would have kept passing after the producer's wording changed,
    # and it could not have caught a producer that miscounted.
    stated, total, scored = _coverage_counts(
        nc.coverage_sentence(n_scored, len(districts)), districts
    )
    assert (stated, total, scored) == (2, 3, 2)

    # ...and it must be able to fail. An inflated count from the same formatter
    # is caught, which is the regression this rule exists for.
    bad, total, scored = _coverage_counts(
        nc.coverage_sentence(len(districts), len(districts)), districts
    )
    assert bad != scored, "the rule must be able to catch an inflated count"
