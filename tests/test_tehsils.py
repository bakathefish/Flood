# tests/test_tehsils.py
"""Test-first spec for sailaab.tehsils (tehsil = ADM3 sub-district level).

Pure-logic tests (normalize / overlap / assign) are classic red->green. The
committed-artifact tests exercise the real ``data/punjab_tehsils.geojson`` built
by ``pipeline/fetch_tehsils.py`` and mirror the discipline of test_districts.py.
"""

import json
from pathlib import Path

import pytest
from shapely.geometry import box, shape

from sailaab.districts import load_districts
from sailaab.tehsils import (
    assign_district,
    load_tehsils,
    normalize_tehsil_name,
    overlap_fraction,
)

GEOJSON = Path(__file__).resolve().parents[1] / "data" / "punjab_tehsils.geojson"


# --------------------------------------------------------------------------- #
# name normalization (documented geoBoundaries quirks)
# --------------------------------------------------------------------------- #
def test_normalize_collapses_whitespace_and_strips():
    assert normalize_tehsil_name("  Tapa ") == "Tapa"
    assert normalize_tehsil_name("Rampura  Phul") == "Rampura Phul"
    assert normalize_tehsil_name("Batala") == "Batala"


def test_normalize_roman_numeral_suffix():
    # geoBoundaries ships "Amritsar -I", "Amritsar- Ii", "Jalandhar - Ii"
    assert normalize_tehsil_name("Amritsar -I") == "Amritsar-I"
    assert normalize_tehsil_name("Amritsar- Ii") == "Amritsar-II"
    assert normalize_tehsil_name("Jalandhar - Ii") == "Jalandhar-II"
    assert normalize_tehsil_name("Jalandhar - I") == "Jalandhar-I"


def test_normalize_keeps_distinct_parts_distinct():
    # -I and -II must not collapse onto each other
    assert normalize_tehsil_name("Amritsar -I") != normalize_tehsil_name("Amritsar- Ii")


def test_normalize_leaves_parentheticals():
    assert normalize_tehsil_name("Ludhiana (East)") == "Ludhiana (East)"
    assert normalize_tehsil_name("Ludhiana  (West)") == "Ludhiana (West)"


# --------------------------------------------------------------------------- #
# overlap_fraction — fraction of geom's area lying inside region (pure shapely)
# --------------------------------------------------------------------------- #
def test_overlap_fraction_quarter():
    geom = box(0, 0, 2, 2)  # area 4
    region = box(1, 1, 3, 3)  # overlap [1,2]x[1,2] = 1
    assert overlap_fraction(geom, region) == pytest.approx(0.25)


def test_overlap_fraction_disjoint_zero():
    assert overlap_fraction(box(0, 0, 1, 1), box(5, 5, 6, 6)) == pytest.approx(0.0)


def test_overlap_fraction_contained_one():
    assert overlap_fraction(box(0, 0, 1, 1), box(-1, -1, 4, 4)) == pytest.approx(1.0)


# --------------------------------------------------------------------------- #
# assign_district — argmax intersection area, with tehsil-fraction returned
# --------------------------------------------------------------------------- #
def test_assign_district_argmax_overlap():
    a = box(0, 0, 2, 2)
    b = box(2, 0, 4, 2)
    tehsil = box(1, 0, 4, 1)  # area 3; in A = 1, in B = 2 -> B wins
    name, frac = assign_district(tehsil, [("A", a), ("B", b)])
    assert name == "B"
    assert frac == pytest.approx(2 / 3)


def test_assign_district_single():
    a = box(0, 0, 10, 10)
    name, frac = assign_district(box(1, 1, 2, 2), [("Solo", a)])
    assert name == "Solo"
    assert frac == pytest.approx(1.0)


# --------------------------------------------------------------------------- #
# committed geojson artifact (built by pipeline/fetch_tehsils.py)
# --------------------------------------------------------------------------- #
def _canonical_districts():
    return {n for n, _ in load_districts(canonicalize=True)}


def test_geojson_exists_and_has_punjab_tehsils():
    gj = json.loads(GEOJSON.read_text(encoding="utf-8"))
    feats = gj["features"]
    assert 80 <= len(feats) <= 95  # ~91 ADM3 sub-districts majority-in-Punjab
    for f in feats:
        assert f["properties"]["tehsil"]
        assert f["properties"]["district"]
        assert f["geometry"]["type"] in ("Polygon", "MultiPolygon")


def test_tehsil_districts_are_canonical_and_complete():
    gj = json.loads(GEOJSON.read_text(encoding="utf-8"))
    canon = _canonical_districts()
    seen = {f["properties"]["district"] for f in gj["features"]}
    assert seen <= canon  # every parent district resolves to a GAUL/config name
    assert seen == canon  # all 20 districts carry at least one tehsil


def test_load_tehsils_sorted_triples():
    ts = load_tehsils(GEOJSON)
    assert 80 <= len(ts) <= 95
    keys = [(d, t) for t, d, _ in ts]
    assert keys == sorted(keys)  # stable (district, tehsil) order for labels
    for tehsil, district, geom in ts:
        assert isinstance(tehsil, str) and tehsil == tehsil.strip()
        assert isinstance(district, str)
        assert geom["type"] in ("Polygon", "MultiPolygon")


def test_tehsil_names_are_normalized():
    gj = json.loads(GEOJSON.read_text(encoding="utf-8"))
    for f in gj["features"]:
        name = f["properties"]["tehsil"]
        assert name == name.strip()
        assert "  " not in name  # no double spaces
        assert "Ii" not in name  # roman numerals upper-cased (no "Ii"/"Iii")
        assert " -" not in name and "- " not in name  # tidy hyphen separators


def test_tehsil_names_unique():
    gj = json.loads(GEOJSON.read_text(encoding="utf-8"))
    names = [f["properties"]["tehsil"] for f in gj["features"]]
    assert len(names) == len(set(names))  # no duplicate tehsil labels


def test_total_area_matches_official_within_3pct():
    pyproj = pytest.importorskip("pyproj")
    geod = pyproj.Geod(ellps="WGS84")
    total_km2 = 0.0
    for _, _, geom in load_tehsils(GEOJSON):
        area_m2, _ = geod.geometry_area_perimeter(shape(geom))
        total_km2 += abs(area_m2) / 1e6
    assert total_km2 == pytest.approx(50_362, rel=0.03)
