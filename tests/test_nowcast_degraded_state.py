# tests/test_nowcast_degraded_state.py
"""A failed run must never be publishable as a benign off-season state.

`degraded()` is the catch-all for any exception in the live pipeline. It used
to emit `core_season: false` whenever it could not resolve the window, and to
omit the forecast block entirely. Both are readable as good news: a consumer
turns the first into "the forecaster is resting until the monsoon" and the
second into "nothing to report". On the day the pipeline breaks mid-monsoon,
either one is an all-clear.

So: unknown stays null, and the failure is stated explicitly rather than
inferred from an omission.
"""

import pipeline.nowcast as pn
from sailaab import nowcast


def _degraded(today="2026-08-06", reason="RuntimeError: upstream down"):
    return pn.degraded("2026-08-06T00:00:00Z", today, reason)


def test_degraded_carries_an_explicit_unavailable_forecast():
    payload = _degraded()
    assert payload["forecast"]["status"] == "unavailable"
    assert "not an all-clear" in payload["forecast"]["note"].lower()
    assert payload["forecast"]["reason"] == "RuntimeError: upstream down"


def test_degraded_mid_monsoon_is_not_labelled_off_season():
    """6 Aug is core season. A failure there must not read as pre-season."""
    payload = _degraded(today="2026-08-06")
    assert payload["core_season"] is True
    assert payload["forecast"]["status"] == "unavailable"


def test_unresolvable_date_reports_unknown_season_not_false():
    """When the window cannot be resolved, the season is unknown, not absent."""
    payload = _degraded(today="not-a-date")
    assert payload["core_season"] is None, (
        "an unresolvable date must not assert that we are out of season"
    )


def test_degraded_scores_are_all_null():
    payload = _degraded()
    assert payload["districts"]
    for d in payload["districts"]:
        assert d["p_event"] is None
        assert d["observed_km2"] is None


def test_build_nowcast_json_preserves_unknown_season():
    payload = nowcast.build_nowcast_json(
        generated_utc="2026-08-06T00:00:00Z",
        window={
            "window_start": None,
            "window_end": None,
            "core_season": None,
            "activates": None,
        },
        sources={"labels": "unavailable"},
        districts=["Amritsar"],
        observed={},
        p_event=None,
        notes="DEGRADED: test",
    )
    assert payload["core_season"] is None


def test_build_nowcast_json_still_coerces_real_flags():
    for raw, want in ((1, True), (0, False), (True, True), (False, False)):
        payload = nowcast.build_nowcast_json(
            generated_utc="2026-08-06T00:00:00Z",
            window={
                "window_start": "2026-08-04",
                "window_end": "2026-08-14",
                "core_season": raw,
                "activates": "2026-07-25",
            },
            sources={"labels": "gfm"},
            districts=["Amritsar"],
            observed={},
            p_event=None,
            notes="",
        )
        assert payload["core_season"] is want
