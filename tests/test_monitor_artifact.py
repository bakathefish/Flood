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
