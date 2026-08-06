# tests/test_nowcast_notes.py
"""The published note must describe the model that is actually deployed.

The forecaster reads satellite flood history only. An earlier version of the
note said reservoir features were NaN and that rain features went missing when
Open-Meteo was unreachable, which told every reader that rain and dam storage
were model inputs. They are not: rainfall was tested as a feature family and
measurably did not help, so it was dropped, and reservoir storage was never in
the daily model at all. Both are still fetched and shown as page context.

Describing inputs the model does not have is the same class of error as
overstating skill, so it is guarded here rather than left to review.
"""

import pipeline.nowcast as pn
from sailaab import forecast_live


def _notes(rain_source="open-meteo", res_source="unavailable"):
    return pn._build_notes(
        window={"core_season": True},
        rain_source=rain_source,
        rain_meta={"current_days_counted": 3, "current_days_total": 5},
        res_source=res_source,
        gfm_meta={
            "current_days_active": 2,
            "current_days": 3,
            "prev_days_active": 1,
            "prev_days": 3,
            "grid_px": 512,
        },
        model_note="",
    )


def test_note_states_the_forecast_reads_satellite_history_only():
    note = _notes()
    assert "satellite flood history only" in note


def test_note_says_rainfall_was_tested_and_is_not_an_input():
    note = _notes()
    assert "did not improve the forecast" in note
    assert "not an " in note or "not an input" in note


def test_note_never_calls_rain_or_reservoirs_model_features():
    """No phrasing that implies the model ingests rain or dam storage."""
    for rain in ("open-meteo", "unavailable"):
        for res in ("cwc", "unavailable"):
            note = _notes(rain_source=rain, res_source=res)
            lowered = note.lower()
            for banned in (
                "rain features",
                "reservoir storage/delta features",
                "ingests the missing values",
            ):
                assert banned not in lowered, f"{banned!r} in note ({rain}, {res})"


def test_note_marks_rain_and_reservoirs_as_context():
    assert "context only" in _notes()
    assert "Rain context" in _notes(rain_source="open-meteo")
    assert "Rain context unavailable" in _notes(rain_source="degraded")
    assert "Reservoir context is unavailable" in _notes(res_source="unavailable")


def test_declared_inputs_match_the_deployed_feature_order():
    """The note's plain-English input list must cover every shipped feature.

    Each feature in the bundle's locked order maps to one phrase in the note.
    If a feature is added and the note is not updated, this fails.
    """
    note = _notes().lower()
    described = {
        "prior_wet_days": "district priors",
        "prior_max_fraction": "district priors",
        "frac_now": "observed extent now",
        "frac_max3d": "over three days",
        "day_of_season": "position in the season",
        "neighbour": "neighbouring districts",
        "season_climo": "district-week climatology",
        "excite_h0": "decaying across the district graph",
        "excite_h1": "decaying across the district graph",
        "excite_h2": "decaying across the district graph",
    }
    assert set(described) == set(forecast_live.FEATURE_ORDER), (
        "feature order changed; update the published note and this map"
    )
    for feature, phrase in described.items():
        assert phrase in note, f"{feature} not described in the published note"
