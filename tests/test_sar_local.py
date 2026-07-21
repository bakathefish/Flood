# tests/test_sar_local.py
"""Pure-array SAR flood logic, developed test-first with small synthetic arrays.
No network, no Earth Engine — mirrors the Tier-A convention in gee/02."""

import numpy as np
import pytest

from sailaab.sar_local import (
    to_db,
    median_composite,
    tier_a_mask,
    sieve_mask,
    flooded_hectares,
    best_common_orbit,
)


# --- to_db -----------------------------------------------------------------
def test_to_db_known_values():
    x = np.array([1.0, 0.1, 0.01])
    np.testing.assert_allclose(to_db(x), [0.0, -10.0, -20.0])


def test_to_db_floor_clips_zero_not_minus_inf():
    # 0 linear power would be -inf; the 1e-6 floor caps it at -60 dB
    assert to_db(np.array([0.0]))[0] == pytest.approx(-60.0)
    assert np.isfinite(to_db(np.array([0.0]))[0])


def test_to_db_preserves_nan():
    out = to_db(np.array([np.nan, 1.0]))
    assert np.isnan(out[0]) and out[1] == pytest.approx(0.0)


# --- median_composite ------------------------------------------------------
def test_median_composite_ignores_nan():
    stack = np.array(
        [
            [[1.0, np.nan]],
            [[3.0, 4.0]],
            [[5.0, 6.0]],
        ]
    )  # shape (3,1,2)
    out = median_composite(stack)
    np.testing.assert_allclose(
        out, [[3.0, 5.0]]
    )  # col1 median(1,3,5)=3; col2 median(4,6)=5


def test_median_composite_all_nan_column_is_nan():
    stack = np.array([[[np.nan]], [[np.nan]]])
    out = median_composite(stack)
    assert np.isnan(out[0, 0])


def test_median_composite_rejects_non_3d():
    with pytest.raises(ValueError, match="scene"):
        median_composite(np.zeros((2, 2)))


# --- tier_a_mask -----------------------------------------------------------
def test_tier_a_mask_all_conditions():
    # pixel A: drop -5, flood -18, pre -8  -> flood (drop & dark & not-perm)
    # pixel B: drop -1 (too small)         -> no
    # pixel C: flood -12 (not dark enough) -> no
    # pixel D: pre -20 (permanent water)   -> excluded
    dvv = np.array([-5.0, -1.0, -5.0, -5.0])
    vf = np.array([-18.0, -18.0, -12.0, -18.0])
    vp = np.array([-8.0, -8.0, -8.0, -20.0])
    m = tier_a_mask(dvv, vf, vp)
    np.testing.assert_array_equal(m, [True, False, False, False])


def test_tier_a_mask_nan_is_not_flood():
    dvv = np.array([np.nan, -5.0])
    vf = np.array([-18.0, np.nan])
    vp = np.array([-8.0, -8.0])
    m = tier_a_mask(dvv, vf, vp)
    np.testing.assert_array_equal(m, [False, False])


def test_tier_a_mask_custom_thresholds():
    dvv = np.array([-2.5])
    vf = np.array([-16.0])
    vp = np.array([-8.0])
    assert tier_a_mask(dvv, vf, vp, diff_thresh=-2.0, abs_thresh=-15.0)[0]
    assert not tier_a_mask(dvv, vf, vp, diff_thresh=-3.0, abs_thresh=-15.0)[0]


# --- sieve_mask ------------------------------------------------------------
def test_sieve_removes_small_blob_keeps_large():
    m = np.zeros((10, 10), dtype=bool)
    m[0, 0] = True  # 1-px blob -> removed
    m[5:9, 5:9] = True  # 16-px blob -> kept
    out = sieve_mask(m, min_size=10)
    assert not out[0, 0]
    assert out[5:9, 5:9].all()
    assert out.sum() == 16


def test_sieve_boundary_size_kept():
    m = np.zeros((5, 20), dtype=bool)
    m[0, 0:10] = True  # exactly 10 px in a row
    out = sieve_mask(m, min_size=10)
    assert out.sum() == 10


def test_sieve_connectivity_8_vs_4():
    # a diagonal chain of 3 pixels: 8-connected = one blob of 3; 4-connected = three blobs of 1
    m = np.zeros((5, 5), dtype=bool)
    m[1, 1] = m[2, 2] = m[3, 3] = True
    assert sieve_mask(m, min_size=3, connectivity=8).sum() == 3
    assert sieve_mask(m, min_size=3, connectivity=4).sum() == 0


def test_sieve_rejects_bad_connectivity():
    with pytest.raises(ValueError):
        sieve_mask(np.zeros((3, 3), dtype=bool), connectivity=6)


# --- flooded_hectares ------------------------------------------------------
def test_flooded_hectares():
    m = np.zeros((10, 10), dtype=bool)
    m[:5, :4] = True  # 20 px
    # 20 px * 900 m^2 / 1e4 = 1.8 ha
    assert flooded_hectares(m, pixel_area_m2=900.0) == pytest.approx(1.8)


# --- best_common_orbit -----------------------------------------------------
def test_best_common_orbit_picks_best_min_then_total():
    pre = {("ascending", 27): 9, ("descending", 34): 7, ("descending", 136): 4}
    flood = {("ascending", 27): 2, ("descending", 34): 2, ("ascending", 100): 1}
    # common = {asc/27, desc/34}; both min=2, tie broken by total (11 vs 9)
    assert best_common_orbit(pre, flood) == ("ascending", 27)


def test_best_common_orbit_raises_when_no_overlap():
    with pytest.raises(ValueError, match="common"):
        best_common_orbit({("ascending", 27): 9}, {("descending", 136): 4})
