# tests/test_nowcast_coverage.py
"""A district the satellite could not see must not be published with a score.

The model returns a number for every district it is asked about. For a district
with no usable imagery that number comes from priors and climatology alone, and
it is indistinguishable from a real one: same range, same rank column, same
tier. Surfacing such a district elsewhere on the page is not a fix, because the
score is still in the ranking being read.

Coverage also used to default to True when a caller did not say. That is
fail-open: an omission published a district as observed when nobody knew
whether it was.
"""

from sailaab import nowcast


def _payload(observed, p_event, extras=None):
    return nowcast.build_nowcast_json(
        generated_utc="2026-08-06T00:00:00Z",
        window={
            "window_start": "2026-08-04",
            "window_end": "2026-08-14",
            "core_season": True,
            "activates": "2026-07-25",
        },
        sources={"forecast_inputs": "gfm", "labels": "gfm"},
        districts=["Kapurthala", "Firozpur", "Amritsar"],
        observed=observed,
        p_event=p_event,
        extras=extras,
        notes="",
    )


def _by_name(payload):
    return {d["district"]: d for d in payload["districts"]}


def test_uncovered_district_gets_no_score():
    observed = {
        "Kapurthala": {"observed_fraction": 0.0, "observed_km2": 0.0, "covered": True},
        "Firozpur": {"observed_fraction": None, "observed_km2": None, "covered": False},
        "Amritsar": {"observed_fraction": 0.0, "observed_km2": 0.0, "covered": True},
    }
    # the model happily returned a number for the district nobody imaged
    p = {"Kapurthala": 0.72, "Firozpur": 0.55, "Amritsar": 0.02}
    rows = _by_name(_payload(observed, p))
    assert rows["Firozpur"]["p_event"] is None
    assert rows["Firozpur"]["covered"] is False
    assert rows["Kapurthala"]["p_event"] == 0.72
    assert rows["Amritsar"]["p_event"] == 0.02


def test_uncovered_district_gets_no_rank_or_tier():
    """Operational fields arrive via extras and must be stripped too."""
    observed = {
        "Kapurthala": {"observed_fraction": 0.0, "observed_km2": 0.0, "covered": True},
        "Firozpur": {"observed_fraction": None, "observed_km2": None, "covered": False},
        "Amritsar": {"observed_fraction": 0.0, "observed_km2": 0.0, "covered": True},
    }
    p = {"Kapurthala": 0.72, "Firozpur": 0.55, "Amritsar": 0.02}
    extras = {
        "Kapurthala": {"rank": 1, "tier": "watch", "transparent_score": 2.1},
        "Firozpur": {"rank": 2, "tier": "elevated", "transparent_score": 1.4},
        "Amritsar": {"rank": 3, "tier": "low", "transparent_score": 0.3},
    }
    rows = _by_name(_payload(observed, p, extras))
    assert rows["Firozpur"]["rank"] is None
    assert rows["Firozpur"]["tier"] is None
    assert rows["Firozpur"]["transparent_score"] is None
    assert rows["Firozpur"]["p_event"] is None
    # covered districts keep theirs
    assert rows["Kapurthala"]["tier"] == "watch"
    assert rows["Kapurthala"]["rank"] == 1


def test_coverage_defaults_to_false_not_true():
    """An observation that never says it was imaged is treated as unimaged."""
    observed = {"Kapurthala": {"observed_fraction": 0.0, "observed_km2": 0.0}}
    rows = _by_name(_payload(observed, {"Kapurthala": 0.9}))
    assert rows["Kapurthala"]["covered"] is False
    assert rows["Kapurthala"]["p_event"] is None


def test_district_absent_from_observed_is_not_scored():
    rows = _by_name(_payload({}, {"Amritsar": 0.9}))
    assert rows["Amritsar"]["covered"] is False
    assert rows["Amritsar"]["p_event"] is None


def test_every_district_covered_behaves_normally():
    observed = {
        d: {"observed_fraction": 0.01, "observed_km2": 5.0, "covered": True}
        for d in ("Kapurthala", "Firozpur", "Amritsar")
    }
    p = {"Kapurthala": 0.72, "Firozpur": 0.50, "Amritsar": 0.02}
    payload = _payload(observed, p)
    assert [d["district"] for d in payload["districts"]] == [
        "Kapurthala",
        "Firozpur",
        "Amritsar",
    ]
    assert all(d["p_event"] is not None for d in payload["districts"])
