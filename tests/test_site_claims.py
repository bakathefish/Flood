# tests/test_site_claims.py
"""Every shipped chunk must carry the current model's claims, not a past one's.

The app is code-split: the forecast board and the proof section land in
different JS chunks. A review pass that checked only the main `index-*.js`
bundle passed while the proof chunk still described a superseded model, called
the ranking score a predicted probability, drew it on a percentage axis, and
labelled it "flood risk". The copy was corrected in one chunk and shipped
stale in another.

So the gate scans *every* JS chunk under docs/assets, not the entry bundle. If
a claim is retired anywhere it has to be retired everywhere, and adding a new
chunk cannot quietly reintroduce an old number.
"""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "docs" / "assets"


def _chunks():
    files = sorted(ASSETS.glob("*.js"))
    assert files, "no built JS chunks in docs/assets"
    return [(f.name, f.read_text(encoding="utf-8", errors="ignore")) for f in files]


# Claims that were true of an earlier model or an earlier evaluation and must
# never reappear on any public surface. Each is paired with what replaced it.
RETIRED = [
    ("0.549", "superseded 2025 AP; the fold-safe walk-forward value is 0.536"),
    ("96%", "retracted alert precision; the out-of-fold value is about a third"),
    ("28 alerts", "pre-rerun alert volume; the fold-safe value is about 24"),
    ("predicted probability", "the score is an uncalibrated ranking score"),
    ("flood risk'", "column and tooltip label; use a score label instead"),
    ("held out to 2025", "the forecaster is walk-forward, not a single hold-out"),
    ("trained only on 2015 to 2024", "walk-forward: every season uses earlier ones"),
    ("without the history features", "the ablation removed excitation features only"),
]


@pytest.mark.parametrize("needle,why", RETIRED, ids=[r[0] for r in RETIRED])
def test_retired_claim_absent_from_every_chunk(needle, why):
    offenders = [name for name, body in _chunks() if needle in body]
    assert not offenders, f"{needle!r} still shipped in {offenders}: {why}"


def test_current_headline_numbers_present_in_all_three_languages():
    """The corrected figures ship once per language, not just in English."""
    joined = "\n".join(body for _, body in _chunks())
    for value, expect in (("0.249", 3), ("0.176", 3), ("0.083", 3)):
        got = joined.count(value)
        assert got >= expect, f"{value} appears {got} times, expected >= {expect}"


def test_uncalibrated_wording_ships():
    joined = "\n".join(body for _, body in _chunks())
    assert "not a probability" in joined or "not a calibrated" in joined
    assert "ranking score" in joined


def test_walkforward_season_feed_is_published_and_wired():
    """The proof chart's data file must exist and match the benchmark export."""
    published = ASSETS / "forecaster_2025_walkforward.csv"
    assert published.exists(), "proof chart data feed missing from docs/assets"
    header = published.read_text(encoding="utf-8").splitlines()[0]
    assert header.split(",") == ["district", "date", "score", "flooded_within_3d"]

    source = ROOT / "data" / "forecaster_2025_walkforward.csv"
    assert source.exists(), "benchmark did not write the season export"
    assert published.read_bytes() == source.read_bytes(), (
        "published copy has drifted from the benchmark output; re-copy it"
    )

    joined = "\n".join(body for _, body in _chunks())
    assert "forecaster_2025_walkforward.csv" in joined, "chart not wired to the feed"
    assert "forecaster_2025_hindcast.csv" not in joined, (
        "a chunk still loads the superseded hindcast feed"
    )


def test_no_null_score_coerced_to_zero_in_any_chunk():
    """`+d.p_event || 0` turns "we do not know" into "calm". Ban the pattern."""
    for name, body in _chunks():
        for pattern in ("p_event||0", "p_event || 0", "score||0", "score || 0"):
            assert pattern not in body, f"null-as-zero coercion {pattern!r} in {name}"
