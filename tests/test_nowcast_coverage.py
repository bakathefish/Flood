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
        "Kapurthala": {"observed_fraction": 0.0, "observed_km2": 0.0, "covered": True,
                        "acquisition_state": "observed",
                        "acquisition_fraction": 1.0},
        "Firozpur": {"observed_fraction": None, "observed_km2": None, "covered": False},
        "Amritsar": {"observed_fraction": 0.0, "observed_km2": 0.0, "covered": True,
                        "acquisition_state": "observed",
                        "acquisition_fraction": 1.0},
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
        "Kapurthala": {"observed_fraction": 0.0, "observed_km2": 0.0, "covered": True,
                        "acquisition_state": "observed",
                        "acquisition_fraction": 1.0},
        "Firozpur": {"observed_fraction": None, "observed_km2": None, "covered": False},
        "Amritsar": {"observed_fraction": 0.0, "observed_km2": 0.0, "covered": True,
                        "acquisition_state": "observed",
                        "acquisition_fraction": 1.0},
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
        d: {"observed_fraction": 0.01, "observed_km2": 5.0, "covered": True,
            "acquisition_state": "observed", "acquisition_fraction": 1.0}
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


# --------------------------------------------------------------------------- #
# coverage without acquisition information: the mechanism production uses
# --------------------------------------------------------------------------- #
def test_no_acquisition_covers_nothing_even_with_full_district_rasters():
    """The real false-dry shape: every district rasterized, no imagery returned.

    The earlier coverage test simulated missing imagery by deleting district
    labels from the raster. Production rasterizes every district polygon on
    every run regardless of acquisition, so that arrangement never occurs and
    the test proved nothing about the live path. This is the arrangement that
    does occur: a complete label raster, an all-zero flood mask because every
    request failed, and therefore no observation to stand behind any number.
    """
    import numpy as np

    from sailaab import nowcast as nc

    size = 8
    labels = np.zeros((size, size), dtype=int)
    labels[:, :4] = 1  # Kapurthala
    labels[:, 4:] = 2  # Firozpur
    names = ["Kapurthala", "Firozpur"]
    bounds = (8220944.0, 3443277.0, 8566034.0, 3842330.0)
    empty = np.zeros((size, size), dtype=bool)

    # Without acquisition information nothing is covered, in either direction.
    # "Some request somewhere succeeded" used to grant coverage here, which is
    # the defect the footprint work exists to remove.
    out = nc.district_flood_stats(empty, labels, names, bounds)
    for n in names:
        assert out[n]["covered"] is False
        assert out[n]["observed_km2"] is None
        assert out[n]["observed_fraction"] is None

    # With a footprint saying the whole area was imaged, an empty mask IS dry.
    full = np.ones(labels.shape, dtype=bool)
    acq = nc.district_acquisition(labels, names, full)
    imaged_and_dry = nc.district_flood_stats(
        empty, labels, names, bounds, acquisition=acq
    )
    for n in names:
        assert imaged_and_dry[n]["covered"] is True
        assert imaged_and_dry[n]["observed_km2"] == 0.0


def test_no_acquisition_information_means_no_coverage():
    """The fallback that granted coverage from a bare mask is gone."""
    import numpy as np

    from sailaab import nowcast as nc

    labels = np.ones((4, 4), dtype=int)
    mask = np.zeros((4, 4), dtype=bool)
    mask[0, 0] = True
    out = nc.district_flood_stats(mask, labels, ["A"], (0.0, 0.0, 1000.0, 1000.0))
    assert out["A"]["covered"] is False
    assert out["A"]["observed_km2"] is None


def test_imaged_but_flood_product_missing_is_unresolved_not_dry():
    """Footprint says the satellite was there; the flood request failed.

    Both reviewers ranked this the most direct remaining false zero, and they
    were right: coverage was being read from the footprint alone, so the
    district published as observed with 0.0 km2 of water when what was under
    the imagery had never been retrieved.
    """
    import numpy as np

    from sailaab import nowcast as nc

    labels, names = _strip_labels()
    bounds = (8220944.0, 3443277.0, 8566034.0, 3842330.0)
    empty = np.zeros(labels.shape, dtype=bool)
    footprint = np.ones(labels.shape, dtype=bool)
    unresolved = np.zeros(labels.shape, dtype=bool)
    unresolved[:, labels.shape[1] // 2 :] = True  # east's flood fetch failed

    acq = nc.district_acquisition(labels, names, footprint, unresolved=unresolved)
    assert acq["west"]["state"] == "observed"
    assert acq["east"]["state"] == "unresolved"

    stats = nc.district_flood_stats(
        empty, labels, names, bounds, acquisition=acq
    )
    assert stats["west"]["covered"] is True
    assert stats["east"]["covered"] is False
    assert stats["east"]["observed_km2"] is None


def test_partial_coverage_no_longer_certifies_a_district_wide_zero():
    """A district must be nearly fully imaged before it counts as observed."""
    import numpy as np

    from sailaab import nowcast as nc

    labels, names = _strip_labels(size=20)
    footprint = np.zeros(labels.shape, dtype=bool)
    footprint[:12, :] = True  # 60% of each district

    acq = nc.district_acquisition(labels, names, footprint)
    for n in names:
        assert acq[n]["state"] == "partial", "60% must not read as observed"


# --------------------------------------------------------------------------- #
# real acquisition footprints, the thing that actually answers "was it imaged"
# --------------------------------------------------------------------------- #
def _strip_labels(size=20):
    """Two districts side by side, both fully rasterized as production does."""
    import numpy as np

    labels = np.zeros((size, size), dtype=int)
    labels[:, : size // 2] = 1
    labels[:, size // 2 :] = 2
    return labels, ["west", "east"]


def test_footprint_covering_one_district_leaves_the_other_not_observed():
    """The shape a Sentinel-1 pass actually makes: a strip, not the whole state.

    Verified against the live layer on 2026-07-25, where the acquisition
    covered 14% of the Punjab bbox and 19 of 20 districts were never imaged.
    The pre-footprint code published all 20 as observed with 0.0 km2 of water.
    """
    import numpy as np

    from sailaab import nowcast as nc

    labels, names = _strip_labels()
    footprint = np.zeros(labels.shape, dtype=bool)
    footprint[:, : labels.shape[1] // 2] = True  # west only

    acq = nc.district_acquisition(labels, names, footprint)
    assert acq["west"]["state"] == "observed"
    assert acq["west"]["acquisition_fraction"] == 1.0
    assert acq["east"]["state"] == "not_observed"
    assert acq["east"]["acquisition_fraction"] == 0.0


def test_partial_acquisition_is_its_own_state_not_rounded_to_observed():
    """Half a district imaged cannot stand behind a district-wide number."""
    import numpy as np

    from sailaab import nowcast as nc

    labels, names = _strip_labels(size=20)
    footprint = np.zeros(labels.shape, dtype=bool)
    footprint[:5, :] = True  # a quarter of each district

    acq = nc.district_acquisition(labels, names, footprint)
    for n in names:
        assert acq[n]["state"] == "partial"
        assert acq[n]["acquisition_fraction"] == 0.25


def test_unavailable_footprint_is_unknown_for_everyone_not_not_observed():
    """Failing to fetch the layer is different from knowing nothing was imaged."""
    from sailaab import nowcast as nc

    labels, names = _strip_labels()
    acq = nc.district_acquisition(labels, names, None)
    for n in names:
        assert acq[n]["state"] == "unknown"
        assert acq[n]["acquisition_fraction"] is None


def test_an_unimaged_district_gets_no_flood_number_even_from_a_clean_mask():
    """The whole point: an empty mask over an unimaged district is not zero."""
    import numpy as np

    from sailaab import nowcast as nc

    labels, names = _strip_labels()
    bounds = (8220944.0, 3443277.0, 8566034.0, 3842330.0)
    empty = np.zeros(labels.shape, dtype=bool)
    footprint = np.zeros(labels.shape, dtype=bool)
    footprint[:, : labels.shape[1] // 2] = True

    acq = nc.district_acquisition(labels, names, footprint)
    stats = nc.district_flood_stats(
        empty, labels, names, bounds, acquisition=acq
    )
    assert stats["west"]["covered"] is True
    assert stats["west"]["observed_km2"] == 0.0     # imaged, and genuinely dry
    assert stats["east"]["covered"] is False
    assert stats["east"]["observed_km2"] is None    # never looked at
    assert stats["east"]["acquisition_state"] == "not_observed"
