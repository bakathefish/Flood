# tests/test_monitor_pc.py
"""Pure logic + reference-raster codec for the secretless Planetary Computer
monitor, developed test-first. No network, no Earth Engine — the STAC/COG IO
lives in pipeline/live_monitor.py and is exercised by the end-to-end run."""

import numpy as np
import pytest

from sailaab.monitor_pc import (
    QUANT_NODATA,
    build_alerts,
    dequantize_db,
    district_km2_rows,
    group_by_date,
    load_reference,
    plan_passes,
    quantize_db,
    reproject_geoms,
    save_reference,
    scene_date,
)


# --- scene_date / group_by_date -------------------------------------------
def test_scene_date_strips_time_and_zone():
    assert scene_date("2026-07-20T00:59:03.430430Z") == "2026-07-20"
    assert scene_date("2026-07-19T12:54:51Z") == "2026-07-19"


def test_group_by_date_buckets_and_sorts():
    dts = [
        "2026-07-20T00:59:53Z",
        "2026-07-19T12:54:51Z",
        "2026-07-20T00:59:03Z",
        "2026-07-19T12:56:09Z",
    ]
    out = group_by_date(dts)
    assert set(out) == {"2026-07-19", "2026-07-20"}
    assert out["2026-07-20"] == ["2026-07-20T00:59:03Z", "2026-07-20T00:59:53Z"]
    assert out["2026-07-19"] == ["2026-07-19T12:54:51Z", "2026-07-19T12:56:09Z"]


# --- plan_passes ----------------------------------------------------------
def test_plan_passes_processes_all_dates_when_small():
    dts = ["2026-07-19T12:54:51Z", "2026-07-20T00:59:03Z", "2026-07-20T00:59:53Z"]
    dates, skipped = plan_passes(dts, max_scenes=8)
    assert dates == ["2026-07-19", "2026-07-20"]
    assert skipped is False


def test_plan_passes_latest_only_on_backlog():
    # 9 scenes across 3 dates exceeds max_scenes=8 -> latest date only
    dts = (
        ["2026-07-10T01:00:00Z"] * 3
        + ["2026-07-15T01:00:00Z"] * 3
        + ["2026-07-20T01:00:00Z"] * 3
    )
    dates, skipped = plan_passes(dts, max_scenes=8)
    assert dates == ["2026-07-20"]
    assert skipped is True


def test_plan_passes_empty():
    assert plan_passes([]) == ([], False)


# --- district_km2_rows ----------------------------------------------------
def test_district_km2_rows_sorts_and_flags():
    fractions = {
        "Amritsar": {
            "flooded_ha": 6000.0,
            "district_ha": 200000.0,
            "flooded_fraction": 0.03,
        },
        "Ludhiana": {
            "flooded_ha": 1000.0,
            "district_ha": 300000.0,
            "flooded_fraction": 0.0033,
        },
        "Moga": {"flooded_ha": 0.0, "district_ha": 100000.0, "flooded_fraction": 0.0},
    }
    rows, flagged = district_km2_rows(fractions, alert_km2=25.0)
    # 6000 ha = 60 km², 1000 ha = 10 km², 0 ha = 0
    assert [r["district"] for r in rows] == ["Amritsar", "Ludhiana", "Moga"]
    assert rows[0]["flooded_km2"] == pytest.approx(60.0)
    assert rows[1]["flooded_km2"] == pytest.approx(10.0)
    # only Amritsar clears the 25 km² floor
    assert [r["district"] for r in flagged] == ["Amritsar"]


def test_district_km2_rows_ties_break_by_name():
    fractions = {
        "Zira": {"flooded_ha": 500.0, "district_ha": 1.0, "flooded_fraction": 0.1},
        "Abohar": {"flooded_ha": 500.0, "district_ha": 1.0, "flooded_fraction": 0.1},
    }
    rows, _ = district_km2_rows(fractions, alert_km2=25.0)
    assert [r["district"] for r in rows] == ["Abohar", "Zira"]


# --- build_alerts ---------------------------------------------------------
def test_build_alerts_trilingual():
    flagged = [{"district": "Amritsar", "flooded_km2": 60.0}]
    alerts = build_alerts(flagged, trend="stable")
    assert set(alerts) == {"pa", "hi", "en"}
    assert len(alerts["en"]) == 1
    assert "Amritsar" in alerts["en"][0]
    assert "1070" in alerts["en"][0]
    # Punjabi copy renders (non-empty, contains the helpline)
    assert "1070" in alerts["pa"][0]


def test_build_alerts_empty_when_nothing_flagged():
    alerts = build_alerts([])
    assert alerts == {"pa": [], "hi": [], "en": []}


# --- quantize / dequantize round-trip -------------------------------------
def test_quantize_dequantize_roundtrip():
    db = np.array([[-8.34, -15.0, 0.0], [-22.51, 3.2, np.nan]])
    q = quantize_db(db)
    assert q.dtype == np.int16
    back = dequantize_db(q)
    # finite values recovered to 0.01 dB; NaN preserved
    np.testing.assert_allclose(back[np.isfinite(db)], db[np.isfinite(db)], atol=0.005)
    assert np.isnan(back[1, 2])


def test_quantize_marks_nan_with_sentinel():
    q = quantize_db(np.array([np.nan, -10.0]))
    assert q[0] == QUANT_NODATA
    assert q[1] == -1000


# --- reference GeoTIFF round-trip -----------------------------------------
def test_save_load_reference_roundtrip(tmp_path):
    from rasterio.transform import from_origin

    db = np.array([[-8.0, -15.5], [-20.0, np.nan]], dtype="float64")
    transform = from_origin(388562.37, 3608622.45, 150.0, 150.0)
    path = tmp_path / "ref.tif"
    save_reference(path, db, transform, "EPSG:32643")
    arr, tr, crs, w, h = load_reference(path)
    assert (w, h) == (2, 2)
    assert crs.to_epsg() == 32643
    np.testing.assert_allclose(arr[np.isfinite(db)], db[np.isfinite(db)], atol=0.005)
    assert np.isnan(arr[1, 1])
    # transform preserved (same grid the monitor will read new scenes onto)
    assert tr.a == pytest.approx(150.0)
    assert tr.e == pytest.approx(-150.0)


def test_reference_file_is_compact(tmp_path):
    # a smooth statewide dB field compresses far below the 40 MB commit ceiling
    from rasterio.transform import from_origin

    rng = np.random.default_rng(0)
    db = (-9.0 + rng.normal(0, 1.5, size=(2003, 2280))).astype("float64")
    path = tmp_path / "ref.tif"
    save_reference(path, db, from_origin(0, 0, 150, 150), "EPSG:32643")
    assert path.stat().st_size < 40 * 1024 * 1024


# --- reproject_geoms ------------------------------------------------------
def test_reproject_geoms_to_utm_and_back():
    # a small square near Amritsar (lon ~75, lat ~31.7)
    square = {
        "type": "Polygon",
        "coordinates": [
            [[74.9, 31.6], [75.0, 31.6], [75.0, 31.7], [74.9, 31.7], [74.9, 31.6]]
        ],
    }
    ((name, utm),) = reproject_geoms([("Amritsar", square)], "EPSG:4326", "EPSG:32643")
    assert name == "Amritsar"
    xs = [c[0] for c in utm["coordinates"][0]]
    ys = [c[1] for c in utm["coordinates"][0]]
    # Punjab eastings ~300-600 km, northings ~3.2-3.6 Mm in UTM 43N
    assert all(3.0e5 < x < 6.0e5 for x in xs)
    assert all(3.2e6 < y < 3.6e6 for y in ys)
    # round-trip back to lon/lat recovers the original corners
    ((_, back),) = reproject_geoms([("Amritsar", utm)], "EPSG:32643", "EPSG:4326")
    np.testing.assert_allclose(
        back["coordinates"][0], square["coordinates"][0], atol=1e-6
    )
