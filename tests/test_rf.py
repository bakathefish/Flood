# tests/test_rf.py
"""Pure-array RF helper logic, developed test-first with small synthetic arrays.
No network, no sklearn — just the deterministic feature/label/sample machinery in
sailaab/rf.py that the RF training pipeline is built on."""

import numpy as np
import pytest

from sailaab.rf import (
    slope_degrees,
    agreement_labels,
    sample_features,
    xy_from_index,
    stratified_balanced_sample,
)


# --- slope_degrees ---------------------------------------------------------
def test_slope_flat_is_zero():
    dem = np.full((5, 5), 173.0)
    slope = slope_degrees(dem, 90.0)
    np.testing.assert_allclose(slope, 0.0, atol=1e-9)


def test_slope_unit_ramp_is_45_degrees():
    # elevation rises one pixel-size per column -> dz/dx = 1 -> 45 deg everywhere
    p = 90.0
    cols = np.arange(6) * p
    dem = np.tile(cols, (6, 1)).astype(float)
    slope = slope_degrees(dem, p)
    np.testing.assert_allclose(slope, 45.0, atol=1e-6)


def test_slope_diagonal_ramp():
    # dz/dx = dz/dy = 1 -> magnitude sqrt(2) -> arctan(sqrt(2)) deg
    p = 30.0
    i = np.arange(7)
    dem = (i[:, None] + i[None, :]) * p
    slope = slope_degrees(dem, p)
    expect = np.degrees(np.arctan(np.sqrt(2.0)))
    np.testing.assert_allclose(slope, expect, atol=1e-6)


def test_slope_nan_propagates():
    dem = np.zeros((4, 4))
    dem[1, 1] = np.nan
    slope = slope_degrees(dem, 90.0)
    assert np.isnan(slope).any()


# --- agreement_labels ------------------------------------------------------
def _lab_inputs():
    # 6 pixels in a row, one scenario each
    tier = np.array([[True, False, True, True, False, True]])
    gfm = np.array([[True, False, False, True, False, True]])
    refw = np.array([[False, False, False, True, False, False]])
    prevv = np.array([[-8.0, -8.0, -8.0, -8.0, -20.0, np.nan]])
    return tier, gfm, refw, prevv


def test_agreement_labels_all_cases():
    tier, gfm, refw, prevv = _lab_inputs()
    lab = agreement_labels(tier, gfm, refw, prevv, abs_vv_thresh=-15.0)
    # px0 both flood, clean          -> 1
    # px1 both dry, clean            -> 0
    # px2 disagree                   -> -1
    # px3 both flood but refwater    -> -1
    # px4 both dry but pre_vv<-15    -> -1 (permanent-water proxy)
    # px5 both flood but pre_vv NaN  -> -1 (invalid)
    np.testing.assert_array_equal(lab, np.array([[1, 0, -1, -1, -1, -1]]))


def test_agreement_labels_dtype_and_counts():
    tier, gfm, refw, prevv = _lab_inputs()
    lab = agreement_labels(tier, gfm, refw, prevv)
    assert lab.dtype == np.int8
    assert int((lab == 1).sum()) == 1
    assert int((lab == 0).sum()) == 1
    assert int((lab == -1).sum()) == 4


def test_agreement_labels_extra_valid_mask():
    tier, gfm, refw, prevv = _lab_inputs()
    valid = np.array([[False, True, True, True, True, True]])  # kill px0
    lab = agreement_labels(tier, gfm, refw, prevv, valid=valid)
    assert lab[0, 0] == -1  # forced excluded even though it was a clean positive


# --- sample_features -------------------------------------------------------
def test_sample_features_extracts_columns():
    a = np.array([[1.0, 2.0], [3.0, 4.0]])
    b = np.array([[10.0, 20.0], [30.0, 40.0]])
    idx = np.array([0, 3])  # corners: (0,0) and (1,1)
    X = sample_features([a, b], idx)
    np.testing.assert_array_equal(X, np.array([[1.0, 10.0], [4.0, 40.0]]))
    assert X.shape == (2, 2)


# --- xy_from_index ---------------------------------------------------------
def test_xy_from_index_pixel_centres():
    # north-up transform: a=90, e=-90, origin (1000, 5000), width=4
    transform = (90.0, 0.0, 1000.0, 0.0, -90.0, 5000.0)
    xs, ys = xy_from_index(np.array([0, 5]), transform, width=4)
    # idx0 -> row0,col0 ; idx5 -> row1,col1
    np.testing.assert_allclose(xs, [1045.0, 1135.0])
    np.testing.assert_allclose(ys, [4955.0, 4865.0])


# --- stratified_balanced_sample --------------------------------------------
def _sample_scene():
    # 6x6 grid. Left half class 1, right half class 0. Three districts in bands.
    label = np.full((6, 6), -1, dtype=np.int8)
    label[:, :3] = 1
    label[:, 3:] = 0
    district = np.zeros((6, 6), dtype=np.int32)
    district[0:2, :] = 1
    district[2:4, :] = 2
    district[4:6, :] = 3
    return label, district


def test_stratified_balanced_sample_counts_and_districts():
    label, district = _sample_scene()
    rng = np.random.default_rng(0)
    idx = stratified_balanced_sample(label, district, n_per_class=6, rng=rng)
    lab_flat = label.ravel()[idx]
    dist_flat = district.ravel()[idx]
    assert int((lab_flat == 1).sum()) == 6
    assert int((lab_flat == 0).sum()) == 6
    assert set(np.unique(dist_flat)) == {1, 2, 3}  # spread across all districts
    assert (dist_flat > 0).all()  # never samples background


def test_stratified_balanced_sample_deterministic():
    label, district = _sample_scene()
    a = stratified_balanced_sample(label, district, 6, rng=np.random.default_rng(7))
    b = stratified_balanced_sample(label, district, 6, rng=np.random.default_rng(7))
    np.testing.assert_array_equal(a, b)


def test_stratified_balanced_sample_scarcity_takes_all():
    # only 3 class-1 pixels exist; asking for 10 yields the 3 available
    label = np.full((4, 4), 0, dtype=np.int8)
    label.ravel()[[0, 1, 2]] = 1
    district = np.ones((4, 4), dtype=np.int32)
    rng = np.random.default_rng(1)
    idx = stratified_balanced_sample(label, district, n_per_class=10, rng=rng)
    lab_flat = label.ravel()[idx]
    assert int((lab_flat == 1).sum()) == 3
    assert int((lab_flat == 0).sum()) == 10


def test_stratified_balanced_sample_no_background_only():
    # a class present only under background district contributes nothing
    label = np.full((3, 3), 1, dtype=np.int8)
    district = np.zeros((3, 3), dtype=np.int32)
    district[0, 0] = 1  # single valid pixel
    rng = np.random.default_rng(2)
    idx = stratified_balanced_sample(
        label, district, n_per_class=5, rng=rng, classes=(1,)
    )
    assert len(idx) == 1
    assert district.ravel()[idx][0] == 1
