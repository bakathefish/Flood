# tests/test_briefs_data.py
"""District briefs must carry the v2 (DES district-yield) value-at-risk.

Guards the consistency contract between the briefs and the synopsis: the
synopsis headline is VaR v2 (₹523.2 cr statewide, district DES yields); the
briefs read the same v2 numbers, not the flat-yield v1 in
district_flood_stats_2025.csv.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


@pytest.fixture(scope="module")
def tables():
    from pipeline.make_district_briefs import load_tables

    return load_tables()


def _v2_by_district():
    with open(DATA / "district_var_v2.csv", newline="", encoding="utf-8") as f:
        return {r["district"]: float(r["crop_var_inr_v2"]) for r in csv.DictReader(f)}


def test_briefs_var_is_v2_not_v1(tables):
    v2 = _v2_by_district()
    dist = tables["dist"]
    for name, want in v2.items():
        got = float(dist[name]["crop_var_inr"])
        assert got == pytest.approx(want, rel=1e-6), name


def test_briefs_var_statewide_matches_synopsis_523cr(tables):
    dist = tables["dist"]
    total_cr = sum(float(r["crop_var_inr"]) for r in dist.values()) / 1e7
    assert total_cr == pytest.approx(523.2, abs=0.5)
