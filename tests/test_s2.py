# tests/test_s2.py
"""Pure-array Sentinel-2 truth-set logic, developed test-first with small
synthetic arrays. No network, no rasterio -- just the deterministic NDWI /
harmonisation / water-decision / sampling machinery in ``sailaab/s2.py`` that the
optical cross-check pipeline is built on. See ``docs/notes/s2-truth.md``."""

import numpy as np
import pytest

from sailaab.s2 import (
    BOA_ADD_OFFSET,
    DRY,
    UNCERTAIN,
    WATER,
    binary_buffer,
    classify_water,
    draw_from_mask,
    harmonize_reflectance,
    ndwi,
    precision_recall,
)
from sailaab.validation import binary_metrics


# --- harmonize_reflectance -------------------------------------------------
def test_harmonize_applies_offset_and_scale():
    # DN 3000 -> (3000 - 1000) / 10000 = 0.20 reflectance
    dn = np.array([[3000.0]])
    r = harmonize_reflectance(dn)
    np.testing.assert_allclose(r, 0.20)


def test_harmonize_nodata_becomes_nan():
    dn = np.array([0.0, 1000.0, 2000.0])
    r = harmonize_reflectance(dn, nodata=0.0)
    assert np.isnan(r[0])
    np.testing.assert_allclose(r[1:], [0.0, 0.1])


def test_harmonize_dark_water_may_go_slightly_negative():
    # DN below the offset -> small negative reflectance, intentionally not clipped
    r = harmonize_reflectance(np.array([800.0]))
    assert r[0] < 0
    assert r[0] == pytest.approx((800 + BOA_ADD_OFFSET) / 10000.0)


# --- ndwi ------------------------------------------------------------------
def test_ndwi_open_water_positive():
    # green >> nir  -> strongly positive
    val = ndwi(np.array([0.12]), np.array([0.02]))
    assert val[0] == pytest.approx((0.12 - 0.02) / (0.12 + 0.02))
    assert val[0] > 0.5


def test_ndwi_dry_vegetation_negative():
    # nir >> green (healthy crops) -> negative NDWI
    val = ndwi(np.array([0.08]), np.array([0.35]))
    assert val[0] < 0


def test_ndwi_zero_denominator_is_nan():
    val = ndwi(np.array([0.0]), np.array([0.0]))
    assert np.isnan(val[0])


def test_ndwi_nan_propagates():
    val = ndwi(np.array([np.nan, 0.1]), np.array([0.02, 0.02]))
    assert np.isnan(val[0])
    assert np.isfinite(val[1])


# --- classify_water --------------------------------------------------------
def test_classify_water_dry_deadband():
    # ndwi: clear water, clear dry, dead-band -> WATER, DRY, UNCERTAIN
    nd = np.array([0.30, -0.30, 0.02])
    scl = np.array([6, 5, 5])  # all optically usable
    out = classify_water(nd, scl, t_water=0.10, t_dry=-0.05)
    assert list(out) == [WATER, DRY, UNCERTAIN]


def test_classify_cloud_is_uncertain_even_if_ndwi_wet():
    # a cloud pixel with high NDWI must NOT be called water
    nd = np.array([0.4, 0.4, 0.4, 0.4])
    scl = np.array([8, 9, 3, 0])  # cloud-med, cloud-high, shadow, nodata
    out = classify_water(nd, scl, t_water=0.1, t_dry=-0.05)
    assert (out == UNCERTAIN).all()


def test_classify_nan_ndwi_is_uncertain():
    out = classify_water(np.array([np.nan]), np.array([5]), t_water=0.1, t_dry=-0.05)
    assert out[0] == UNCERTAIN


def test_classify_requires_ordered_thresholds():
    with pytest.raises(ValueError):
        classify_water(np.array([0.0]), np.array([5]), t_water=-0.1, t_dry=0.1)


def test_classify_boundary_inclusive():
    # exactly at the thresholds -> water / dry (inclusive), not dead-band
    nd = np.array([0.10, -0.05])
    scl = np.array([5, 5])
    out = classify_water(nd, scl, t_water=0.10, t_dry=-0.05)
    assert list(out) == [WATER, DRY]


# --- binary_buffer ---------------------------------------------------------
def test_binary_buffer_grows_by_one_ring():
    m = np.zeros((5, 5), dtype=bool)
    m[2, 2] = True
    buf = binary_buffer(m, iterations=1, connectivity=8)
    # a single point dilated by 1 (8-conn) -> 3x3 block of 9 True
    assert buf.sum() == 9
    assert buf[1:4, 1:4].all()


def test_binary_buffer_zero_iterations_is_identity():
    m = np.array([[True, False], [False, True]])
    np.testing.assert_array_equal(binary_buffer(m, iterations=0), m)


def test_near_flood_frontier_excludes_flood_itself():
    flood = np.zeros((5, 5), dtype=bool)
    flood[2, 2] = True
    ring = binary_buffer(flood, 1) & ~flood
    assert ring.sum() == 8
    assert not ring[2, 2]


# --- draw_from_mask --------------------------------------------------------
def test_draw_from_mask_deterministic_and_bounded():
    rng1 = np.random.default_rng(0)
    rng2 = np.random.default_rng(0)
    mask = np.zeros((10, 10), dtype=bool)
    mask.ravel()[np.arange(0, 100, 3)] = True
    a = draw_from_mask(mask, 5, rng1)
    b = draw_from_mask(mask, 5, rng2)
    np.testing.assert_array_equal(a, b)
    assert len(a) == 5
    assert mask.ravel()[a].all()  # every drawn index is inside the mask


def test_draw_from_mask_returns_all_when_scarce():
    mask = np.zeros(20, dtype=bool)
    mask[[3, 7, 11]] = True
    idx = draw_from_mask(mask.reshape(4, 5), 10, np.random.default_rng(1))
    assert sorted(idx) == [3, 7, 11]


def test_draw_from_mask_exclude():
    mask = np.ones(10, dtype=bool)
    exclude = np.zeros(10, dtype=bool)
    exclude[:8] = True
    idx = draw_from_mask(mask, 10, np.random.default_rng(2), exclude=exclude)
    assert sorted(idx) == [8, 9]


# --- precision_recall ------------------------------------------------------
def test_precision_recall_matches_definition():
    # pred (mask flood) vs ref (S2 water): TP=2 FP=1 FN=1 TN=2
    pred = np.array([1, 1, 1, 0, 0, 0], dtype=bool)
    ref = np.array([1, 0, 1, 0, 1, 0], dtype=bool)
    m = binary_metrics(pred, ref)
    pr = precision_recall(m)
    assert pr["precision"] == pytest.approx(2 / 3)  # TP/(TP+FP)
    assert pr["recall"] == pytest.approx(2 / 3)  # TP/(TP+FN)


def test_precision_recall_nan_when_no_positive_prediction():
    pred = np.zeros(4, dtype=bool)
    ref = np.array([1, 0, 1, 0], dtype=bool)
    pr = precision_recall(binary_metrics(pred, ref))
    assert np.isnan(pr["precision"])  # no flood predictions -> precision undefined
    assert pr["recall"] == 0.0  # caught 0 of 2 water points
