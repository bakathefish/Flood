# tests/test_districts.py
import json
from pathlib import Path

import numpy as np
import pytest
from rasterio.transform import from_bounds

from sailaab import config
from sailaab.districts import (
    NAME_ALIASES,
    canonical_name,
    district_fractions,
    fold_of,
    load_districts,
    rasterize_districts,
)

GEOJSON = Path(__file__).resolve().parents[1] / "data" / "punjab_districts.geojson"


# --------------------------------------------------------------------------- #
# committed geojson artifact
# --------------------------------------------------------------------------- #
def test_geojson_exists_and_has_20_punjab_districts():
    gj = json.loads(GEOJSON.read_text(encoding="utf-8"))
    feats = gj["features"]
    assert len(feats) == 20
    for f in feats:
        assert f["properties"]["district"]  # canonical name property present
        assert f["geometry"]["type"] in ("Polygon", "MultiPolygon")


def test_load_districts_returns_sorted_name_geometry_pairs():
    ds = load_districts(GEOJSON)
    assert len(ds) == 20
    names = [n for n, _ in ds]
    assert names == sorted(names)  # deterministic order for stable labels
    for name, geom in ds:
        assert isinstance(name, str)
        assert isinstance(geom, dict)
        assert geom["type"] in ("Polygon", "MultiPolygon")


def test_load_districts_canonicalize_maps_to_gaul():
    raw = {n for n, _ in load_districts(GEOJSON)}
    canon = {n for n, _ in load_districts(GEOJSON, canonicalize=True)}
    # datameet ships "Shahid Bhagat Singh Nagar"; GAUL/config spelling is Nawanshahr
    assert "Shahid Bhagat Singh Nagar" in raw
    assert "Shahid Bhagat Singh Nagar" not in canon
    assert "Nawanshahr" in canon


# --------------------------------------------------------------------------- #
# name reconciliation
# --------------------------------------------------------------------------- #
def test_canonical_name_aliases_sbs_nagar():
    assert canonical_name("Shahid Bhagat Singh Nagar") == "Nawanshahr"
    assert NAME_ALIASES["Shahid Bhagat Singh Nagar"] == "Nawanshahr"


def test_canonical_name_passthrough_and_whitespace():
    assert canonical_name("Gurdaspur") == "Gurdaspur"
    assert canonical_name("  Tarn   Taran ") == "Tarn Taran"
    assert canonical_name("Bathinda") == "Bathinda"  # unknown -> unchanged


def test_canonical_name_handles_common_variants():
    assert canonical_name("Ferozepur") == "Firozpur"
    assert canonical_name("SBS Nagar") == "Nawanshahr"
    assert canonical_name("Ropar") == "Rupnagar"


# --------------------------------------------------------------------------- #
# fold lookup
# --------------------------------------------------------------------------- #
def test_fold_of_ravi_beas():
    for d in config.FOLD_RAVI_BEAS:
        assert fold_of(d) == "ravi_beas"


def test_fold_of_sutlej():
    for d in config.FOLD_SUTLEJ:
        assert fold_of(d) == "sutlej"


def test_fold_of_via_alias():
    # datameet spelling reconciles into the Sutlej fold
    assert fold_of("Shahid Bhagat Singh Nagar") == "sutlej"
    assert fold_of("SBS Nagar") == "sutlej"


def test_fold_of_unassigned_is_none():
    for d in ("Bathinda", "Patiala", "Sangrur", "Mansa", "Barnala"):
        assert fold_of(d) is None


def test_every_geojson_district_reconciles():
    ds = load_districts(GEOJSON)
    folded = {n: fold_of(n) for n, _ in ds}
    # exactly the 13 config fold districts get a fold; the other 7 are None
    assigned = [n for n, f in folded.items() if f is not None]
    assert len(assigned) == len(config.FOLD_RAVI_BEAS) + len(config.FOLD_SUTLEJ)
    assert sum(f == "ravi_beas" for f in folded.values()) == len(config.FOLD_RAVI_BEAS)
    assert sum(f == "sutlej" for f in folded.values()) == len(config.FOLD_SUTLEJ)


# --------------------------------------------------------------------------- #
# rasterization
# --------------------------------------------------------------------------- #
def _two_squares():
    # district A = unit square [0,1]x[0,1]; district B = [1,2]x[0,1]
    a = {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]}
    b = {"type": "Polygon", "coordinates": [[[1, 0], [2, 0], [2, 1], [1, 1], [1, 0]]]}
    return a, b


def test_rasterize_districts_labels_by_order():
    a, b = _two_squares()
    transform = from_bounds(0, 0, 2, 1, width=2, height=1)
    labels = rasterize_districts([a, b], transform, (1, 2))
    assert labels.tolist() == [[1, 2]]  # 0=background, i+1 per district
    assert labels.dtype == np.int32


def test_rasterize_accepts_name_geometry_pairs():
    a, b = _two_squares()
    transform = from_bounds(0, 0, 2, 1, width=2, height=1)
    from_pairs = rasterize_districts([("A", a), ("B", b)], transform, (1, 2))
    from_geoms = rasterize_districts([a, b], transform, (1, 2))
    assert np.array_equal(from_pairs, from_geoms)


def test_rasterize_leaves_background_zero():
    a, _ = _two_squares()
    transform = from_bounds(0, 0, 2, 1, width=2, height=1)
    labels = rasterize_districts([a], transform, (1, 2))
    assert labels.tolist() == [[1, 0]]  # right pixel uncovered -> 0


# --------------------------------------------------------------------------- #
# per-district flooded area / fraction
# --------------------------------------------------------------------------- #
def _labels_and_mask():
    labels = np.array([[0, 1, 1, 2], [0, 1, 2, 2]], dtype="int32")
    # flood mask: 1=water, 0=dry, NaN=nodata
    mask = np.array([[1.0, 1.0, 0.0, 1.0], [1.0, 0.0, 1.0, 0.0]])
    return labels, mask


def test_district_fractions_basic():
    labels, mask = _labels_and_mask()
    out = district_fractions(labels, mask, pixel_area_ha=100.0)
    # label 0 (background) excluded even though its pixels are "flooded"
    assert set(out) == {1, 2}
    # label 1: 3 pixels, 1 flooded; label 2: 3 pixels, 2 flooded
    assert out[1]["district_ha"] == pytest.approx(300.0)
    assert out[1]["flooded_ha"] == pytest.approx(100.0)
    assert out[1]["flooded_fraction"] == pytest.approx(1 / 3)
    assert out[2]["flooded_ha"] == pytest.approx(200.0)
    assert out[2]["flooded_fraction"] == pytest.approx(2 / 3)


def test_district_fractions_handles_nan_nodata():
    labels, mask = _labels_and_mask()
    mask = mask.copy()
    mask[0, 1] = np.nan  # was a flooded pixel of label 1 -> now nodata
    out = district_fractions(labels, mask, pixel_area_ha=100.0)
    assert out[1]["flooded_ha"] == pytest.approx(0.0)  # its only flood cell is nodata
    assert out[1]["flooded_fraction"] == pytest.approx(0.0)


def test_district_fractions_names_keys():
    labels, mask = _labels_and_mask()
    out = district_fractions(labels, mask, pixel_area_ha=1.0, names=["Aland", "Bland"])
    assert set(out) == {"Aland", "Bland"}
    assert out["Aland"]["flooded_ha"] == pytest.approx(1.0)


def test_district_fractions_zero_area_district_is_safe():
    labels = np.array([[1, 1]], dtype="int32")  # label 2 absent
    mask = np.array([[1.0, 0.0]])
    out = district_fractions(labels, mask, pixel_area_ha=5.0)
    assert set(out) == {1}  # absent labels simply not reported, no div-by-zero


# --------------------------------------------------------------------------- #
# area sanity (skips if pyproj unavailable)
# --------------------------------------------------------------------------- #
def test_total_area_matches_official_within_2pct():
    pyproj = pytest.importorskip("pyproj")
    pytest.importorskip("shapely")
    from shapely.geometry import shape

    geod = pyproj.Geod(ellps="WGS84")
    total_km2 = 0.0
    for _, geom in load_districts(GEOJSON):
        area_m2, _ = geod.geometry_area_perimeter(shape(geom))
        total_km2 += abs(area_m2) / 1e6
    assert total_km2 == pytest.approx(50_362, rel=0.02)
