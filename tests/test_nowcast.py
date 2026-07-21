# tests/test_nowcast.py
"""Pure-logic tests for the live nowcast (sailaab/nowcast.py).

No network / model IO — window resolution, the exact-16 feature assembly, the
cos²(lat) mask -> per-district reduction, and the locked JSON shaping.
"""

import math

import numpy as np
import pandas as pd
import pytest

from sailaab import nowcast
from sailaab.gfm import web_mercator_area_km2

# Punjab bbox in EPSG:3857 metres (matches pipeline.fetch_gfm.bbox_3857()).
PUNJAB_BOUNDS_3857 = (
    8220944.395083253,
    3443277.6637314847,
    8566034.816542402,
    3842330.217266117,
)


# --------------------------------------------------------------------------- #
# window resolution
# --------------------------------------------------------------------------- #
def test_resolve_window_pre_core_july_2026():
    w = nowcast.resolve_window("2026-07-22")
    assert w["window_start"] == "2026-07-15"
    assert w["window_end"] == "2026-07-25"
    assert w["window_md"] == "07-15"
    assert w["week_of_season"] == 3  # 4th window of the season (0-based)
    assert w["core_season"] is False
    assert w["activates"] == "2026-07-25"
    assert w["prev_window"] == ("2026-07-05", "2026-07-15")
    assert w["prev2_window"] == ("2026-06-25", "2026-07-05")


def test_resolve_window_half_open_boundary_is_core():
    # 07-25 is the start of the first core window, NOT the tail of 07-15..07-25
    w = nowcast.resolve_window("2026-07-25")
    assert w["window_start"] == "2026-07-25"
    assert w["window_end"] == "2026-08-04"
    assert w["week_of_season"] == 4
    assert w["core_season"] is True
    assert w["prev_window"] == ("2026-07-15", "2026-07-25")


def test_resolve_window_core_season_august():
    w = nowcast.resolve_window("2026-08-05")
    assert w["window_start"] == "2026-08-04"
    assert w["core_season"] is True
    assert w["week_of_season"] == 5


def test_resolve_window_clamps_outside_season():
    before = nowcast.resolve_window("2026-05-01")
    assert before["window_index"] == 0
    assert before["clamped"] == "before_season"
    after = nowcast.resolve_window("2026-11-01")
    assert after["clamped"] == "after_season"
    assert after["window_start"] == "2026-09-23"  # last (truncated) window


def test_resolve_window_accepts_date_and_datetime():
    from datetime import date, datetime, timezone

    a = nowcast.resolve_window(date(2026, 7, 22))
    b = nowcast.resolve_window(datetime(2026, 7, 22, 6, 30, tzinfo=timezone.utc))
    assert a["window_start"] == b["window_start"] == "2026-07-15"


def test_activation_date():
    assert nowcast.activation_date(2026) == "2026-07-25"
    assert nowcast.activation_date(2019) == "2019-07-25"


# --------------------------------------------------------------------------- #
# window day enumeration
# --------------------------------------------------------------------------- #
def test_window_days_full():
    days = nowcast.window_days("2026-07-05", "2026-07-15")
    assert days[0] == "2026-07-05"
    assert days[-1] == "2026-07-14"  # half-open: end excluded
    assert len(days) == 10


def test_window_days_truncated_so_far():
    days = nowcast.window_days("2026-07-15", "2026-07-25", upto="2026-07-22")
    assert days == [
        "2026-07-15",
        "2026-07-16",
        "2026-07-17",
        "2026-07-18",
        "2026-07-19",
        "2026-07-20",
        "2026-07-21",
        "2026-07-22",
    ]


def test_window_days_upto_before_start_is_empty():
    assert nowcast.window_days("2026-07-15", "2026-07-25", upto="2026-07-10") == []


def test_window_days_upto_after_end_clamps_to_end():
    days = nowcast.window_days("2026-07-15", "2026-07-25", upto="2026-08-01")
    assert days[-1] == "2026-07-24"
    assert len(days) == 10


# --------------------------------------------------------------------------- #
# feature assembly — EXACT 16 columns in training order
# --------------------------------------------------------------------------- #
def test_feature_order_is_sixteen_and_canonical():
    assert len(nowcast.FEATURE_ORDER) == 16
    assert nowcast.FEATURE_ORDER[:6] == nowcast.RAIN_FEATURES
    assert nowcast.FEATURE_ORDER[6:12] == nowcast.RESERVOIR_FEATURES
    assert nowcast.FEATURE_ORDER[12:14] == ["antecedent_fraction", "week_of_season"]
    assert nowcast.FEATURE_ORDER[14:] == nowcast.PRIOR_FEATURES


def test_feature_order_matches_committed_model():
    """The nowcast's declared feature order must equal the committed joblib's —
    the single guarantee that a live vector lines up with the trained trees."""
    joblib = pytest.importorskip("joblib")
    from pathlib import Path

    path = (
        Path(__file__).resolve().parents[1]
        / "data"
        / "models"
        / "forecaster_2025.joblib"
    )
    bundle = joblib.load(path)
    assert list(bundle["features"]) == list(nowcast.FEATURE_ORDER)
    assert list(bundle["model"].feature_names_in_) == list(nowcast.FEATURE_ORDER)


def test_build_feature_frame_columns_and_values():
    districts = ["Kapurthala", "Firozpur"]
    rain = {
        "punjab_mm": 12.0,
        "upstream_mm": 30.0,
        "punjab_mm_lag1": 5.0,
        "upstream_mm_lag1": 8.0,
        "punjab_mm_lag2": 1.0,
        "upstream_mm_lag2": 2.0,
    }
    reservoirs = {k: float("nan") for k in nowcast.RESERVOIR_FEATURES}
    antecedent = {"Kapurthala": 0.03, "Firozpur": 0.01}
    priors = {
        "Kapurthala": {
            "prior_mean_annual_flooded_ha": 2808.25,
            "prior_seasons_with_fraction_gt2pct": 3,
        },
        "Firozpur": {
            "mean_annual_flooded_ha": 4338.24,  # bare keys also accepted
            "seasons_with_fraction_gt2pct": 2,
        },
    }
    X = nowcast.build_feature_frame(districts, rain, reservoirs, antecedent, 4, priors)

    assert list(X.columns) == list(nowcast.FEATURE_ORDER)
    assert list(X.index) == districts
    assert X.loc["Kapurthala", "punjab_mm"] == 12.0
    assert X.loc["Kapurthala", "antecedent_fraction"] == 0.03
    assert X.loc["Firozpur", "prior_mean_annual_flooded_ha"] == 4338.24
    assert X.loc["Firozpur", "prior_seasons_with_fraction_gt2pct"] == 2
    assert (X["week_of_season"] == 4).all()
    # reservoirs are NaN (XGBoost-native), not dropped
    assert X["bhakra_storage"].isna().all()


def test_build_feature_frame_missing_inputs_become_nan():
    X = nowcast.build_feature_frame(
        ["Amritsar"], rain={}, reservoirs={}, antecedent={}, week_of_season=6, priors={}
    )
    assert list(X.columns) == list(nowcast.FEATURE_ORDER)
    assert X.loc["Amritsar", "punjab_mm"] != X.loc["Amritsar", "punjab_mm"]  # NaN
    assert math.isnan(X.loc["Amritsar", "antecedent_fraction"])
    assert X.loc["Amritsar", "week_of_season"] == 6


def test_feature_frame_reproduces_committed_model_prediction():
    """End-to-end guard: assembling features the live way (statewide rain/reservoir
    scalars + per-district antecedent/prior) must feed the committed model the
    identical vector the training frame does, for a real 2025 core-season window."""
    joblib = pytest.importorskip("joblib")
    pytest.importorskip("xgboost")
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    bundle = joblib.load(root / "data" / "models" / "forecaster_2025.joblib")
    model, feats = bundle["model"], list(bundle["features"])

    df = pd.read_csv(root / "data" / "forecaster_dataset.csv")
    rows = df[(df.year == 2025) & (df.window_start == "2025-08-24")].copy()
    assert len(rows) == 20  # 20 districts in the window

    # statewide features are identical across the window's districts
    rain = {k: rows.iloc[0][k] for k in nowcast.RAIN_FEATURES}
    reservoirs = {k: rows.iloc[0][k] for k in nowcast.RESERVOIR_FEATURES}
    week = int(rows.iloc[0]["week_of_season"])
    antecedent = dict(zip(rows["district"], rows["antecedent_fraction"]))
    priors = {
        r["district"]: {
            "prior_mean_annual_flooded_ha": r["prior_mean_annual_flooded_ha"],
            "prior_seasons_with_fraction_gt2pct": r[
                "prior_seasons_with_fraction_gt2pct"
            ],
        }
        for _, r in rows.iterrows()
    }
    X = nowcast.build_feature_frame(
        list(rows["district"]), rain, reservoirs, antecedent, week, priors
    )
    expected = model.predict_proba(rows[feats])[:, 1]
    got = model.predict_proba(X[feats])[:, 1]
    assert np.allclose(got, expected, atol=1e-9)


# --------------------------------------------------------------------------- #
# GFM mask -> per-district observed fraction / km²
# --------------------------------------------------------------------------- #
def test_district_flood_stats_km2_matches_web_mercator_helper():
    # single district covering the whole grid; km² must equal the tested helper
    n = 40
    labels = np.ones((n, n), dtype=np.int32)
    rng = np.random.default_rng(0)
    mask = rng.random((n, n)) < 0.25
    stats = nowcast.district_flood_stats(mask, labels, ["D"], PUNJAB_BOUNDS_3857)
    expected_km2 = web_mercator_area_km2(mask, PUNJAB_BOUNDS_3857)
    assert stats["D"]["observed_km2"] == pytest.approx(expected_km2, rel=1e-9)
    # fraction = flooded_ha / district_ha
    assert stats["D"]["observed_fraction"] == pytest.approx(
        stats["D"]["flooded_ha"] / stats["D"]["district_ha"], rel=1e-9
    )


def test_district_flood_stats_two_districts_and_refwater():
    n = 20
    labels = np.zeros((n, n), dtype=np.int32)
    labels[:, : n // 2] = 1  # west district
    labels[:, n // 2 :] = 2  # east district
    mask = np.zeros((n, n), dtype=bool)
    mask[:, : n // 2] = True  # flood the whole west district
    refwater = np.zeros((n, n), dtype=bool)
    refwater[0, : n // 2] = True  # one permanent-water row inside west

    stats = nowcast.district_flood_stats(
        mask, labels, ["west", "east"], PUNJAB_BOUNDS_3857, refwater=refwater
    )
    # east has no flood
    assert stats["east"]["observed_fraction"] == 0.0
    assert stats["east"]["observed_km2"] == 0.0
    # west = whole district minus the one permanent-water row; fraction and km²
    # must agree with the tested cos²(lat) area helper on the same masks
    west = labels == 1
    exp_flood_km2 = web_mercator_area_km2(mask & ~refwater & west, PUNJAB_BOUNDS_3857)
    exp_frac = exp_flood_km2 / web_mercator_area_km2(west, PUNJAB_BOUNDS_3857)
    assert stats["west"]["observed_km2"] == pytest.approx(exp_flood_km2, rel=1e-9)
    assert stats["west"]["observed_fraction"] == pytest.approx(exp_frac, rel=1e-9)
    # ~19/20 of the district, and just above 0.95 (the excluded row is the
    # northernmost = smallest cos²(lat) area)
    assert 0.95 < stats["west"]["observed_fraction"] < 0.96


# --------------------------------------------------------------------------- #
# locked JSON schema
# --------------------------------------------------------------------------- #
def _window(core):
    return nowcast.resolve_window("2026-08-05" if core else "2026-07-22")


def test_build_nowcast_json_pre_core_p_event_null():
    districts = ["Kapurthala", "Firozpur", "Amritsar"]
    observed = {
        "Kapurthala": {"observed_fraction": 0.0031, "observed_km2": 8.2},
        "Firozpur": {"observed_fraction": 0.0009, "observed_km2": 2.0},
        "Amritsar": {"observed_fraction": 0.0, "observed_km2": 0.0},
    }
    payload = nowcast.build_nowcast_json(
        generated_utc="2026-07-22T00:00:00Z",
        window=_window(core=False),
        sources={"rain": "open-meteo", "reservoirs": "unavailable", "labels": "gfm"},
        districts=districts,
        observed=observed,
        p_event=None,
        notes="pre-core",
    )
    assert set(payload) == {
        "generated_utc",
        "window_start",
        "window_end",
        "core_season",
        "activates",
        "sources",
        "districts",
        "notes",
    }
    assert payload["core_season"] is False
    assert payload["activates"] == "2026-07-25"
    assert len(payload["districts"]) == 3
    assert all(d["p_event"] is None for d in payload["districts"])
    # every district carries observed_* (schema guarantee)
    assert all(
        "observed_fraction_window" in d and "observed_km2" in d
        for d in payload["districts"]
    )
    # pre-core sort is by observed_km2 desc
    assert [d["district"] for d in payload["districts"]] == [
        "Kapurthala",
        "Firozpur",
        "Amritsar",
    ]


def test_build_nowcast_json_core_season_ranks_by_p_event():
    districts = ["Kapurthala", "Firozpur", "Amritsar"]
    observed = {d: {"observed_fraction": 0.0, "observed_km2": 0.0} for d in districts}
    p_event = {"Kapurthala": 0.72, "Firozpur": 0.50, "Amritsar": 0.02}
    payload = nowcast.build_nowcast_json(
        generated_utc="2026-08-05T00:00:00Z",
        window=_window(core=True),
        sources={"rain": "open-meteo", "reservoirs": "unavailable", "labels": "gfm"},
        districts=districts,
        observed=observed,
        p_event=p_event,
        notes="core",
    )
    assert payload["core_season"] is True
    assert [d["district"] for d in payload["districts"]] == [
        "Kapurthala",
        "Firozpur",
        "Amritsar",
    ]
    assert payload["districts"][0]["p_event"] == 0.72


def test_degraded_payload_is_schema_valid_with_nulls():
    """The never-fail CI fallback must still emit the locked schema: every district
    present, p_event and observed_* null, sources unavailable, a DEGRADED note."""
    from pipeline import nowcast as pipeline_nowcast

    payload = pipeline_nowcast.degraded("2026-07-21T00:00:00Z", "2026-07-21", "boom")
    assert set(payload) == {
        "generated_utc",
        "window_start",
        "window_end",
        "core_season",
        "activates",
        "sources",
        "districts",
        "notes",
    }
    assert payload["sources"] == {
        "rain": "unavailable",
        "reservoirs": "unavailable",
        "labels": "unavailable",
    }
    assert len(payload["districts"]) == 20
    for d in payload["districts"]:
        assert d["p_event"] is None
        assert d["observed_fraction_window"] is None
        assert d["observed_km2"] is None
    assert payload["notes"].startswith("DEGRADED:")


def test_build_nowcast_json_missing_observed_defaults_present():
    payload = nowcast.build_nowcast_json(
        generated_utc="2026-07-22T00:00:00Z",
        window=_window(core=False),
        sources={"rain": "open-meteo", "reservoirs": "unavailable", "labels": "gfm"},
        districts=["Amritsar"],
        observed={},  # nothing computed
        p_event=None,
        notes="",
    )
    d = payload["districts"][0]
    assert d["district"] == "Amritsar"
    assert d["p_event"] is None
    assert d["observed_fraction_window"] is None
    assert d["observed_km2"] is None
