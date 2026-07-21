# sailaab/sar_local.py
"""Pure-array SAR flood logic for the login-free Planetary Computer route.

Mirrors the Tier-A convention in ``gee/02_tierA_change_detection.js`` and the
thresholds in ``sailaab/config.py``, but operates on in-memory numpy arrays read
from Microsoft Planetary Computer COGs — no Earth Engine, no accounts. All IO /
STAC lives in ``pipeline/local_tier_a.py``; everything here is deterministic and
unit-tested against small synthetic arrays."""

from __future__ import annotations

import warnings

import numpy as np
from scipy import ndimage

from sailaab.config import (
    ABS_VV_THRESHOLD_DB,
    DIFF_THRESHOLD_DB,
    MIN_CONNECTED_PIXELS,
)

# Floor applied before log10 so that zero / near-zero linear power maps to a
# finite, very-dark dB value instead of -inf.
DB_FLOOR = 1e-6


def to_db(power, floor: float = DB_FLOOR) -> np.ndarray:
    """Linear power (gamma0, RTC) -> decibels.

    ``10 * log10(clip(power, floor, None))``. NaN nodata propagates as NaN
    (``clip`` and ``log10`` both pass NaN through untouched).
    """
    power = np.asarray(power, dtype="float64")
    return 10.0 * np.log10(np.clip(power, floor, None))


def median_composite(stack) -> np.ndarray:
    """NaN-ignoring median over the leading (scene) axis of a 3-D stack.

    ``stack`` has shape ``(n_scenes, ny, nx)``. Pixels that are NaN in every
    scene stay NaN (with the numpy all-NaN warning suppressed).
    """
    stack = np.asarray(stack, dtype="float64")
    if stack.ndim != 3:
        raise ValueError(f"expected (scene, y, x) stack, got shape {stack.shape}")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)
        return np.nanmedian(stack, axis=0)


def tier_a_mask(
    dvv_db,
    vv_flood_db,
    vv_pre_db,
    diff_thresh: float = DIFF_THRESHOLD_DB,
    abs_thresh: float = ABS_VV_THRESHOLD_DB,
) -> np.ndarray:
    """Boolean Tier-A flood mask.

    ``flood = (ΔVV < diff_thresh) & (VV_flood < abs_thresh) & (VV_pre >= abs_thresh)``

    The first two terms are the UN-SPIDER-style "big backscatter drop AND dark
    now" test; the third excludes the permanent-water proxy (pixels that were
    already dark before the flood). Any NaN input makes the comparison False, so
    nodata pixels are never flagged as flood.
    """
    dvv = np.asarray(dvv_db, dtype="float64")
    vf = np.asarray(vv_flood_db, dtype="float64")
    vp = np.asarray(vv_pre_db, dtype="float64")
    drop = dvv < diff_thresh
    dark_now = vf < abs_thresh
    not_permanent_water = vp >= abs_thresh
    return drop & dark_now & not_permanent_water


def sieve_mask(
    mask, min_size: int = MIN_CONNECTED_PIXELS, connectivity: int = 8
) -> np.ndarray:
    """Drop connected components smaller than ``min_size`` pixels (speckle sieve).

    ``connectivity`` is 8 (default, matches GEE ``connectedPixelCount``) or 4.
    """
    mask = np.asarray(mask, dtype=bool)
    if connectivity == 8:
        structure = np.ones((3, 3), dtype=int)
    elif connectivity == 4:
        structure = None  # scipy default: 4-connectivity cross
    else:
        raise ValueError("connectivity must be 4 or 8")
    labels, n = ndimage.label(mask, structure=structure)
    if n == 0:
        return mask
    sizes = np.bincount(labels.ravel())
    sizes[0] = 0  # background label never counts
    keep = sizes >= min_size
    return keep[labels]


def flooded_hectares(mask, pixel_area_m2: float) -> float:
    """Total area of the boolean ``mask`` in hectares, given per-pixel m²."""
    return float(np.count_nonzero(mask)) * float(pixel_area_m2) / 1e4


def best_common_orbit(pre_scores: dict, flood_scores: dict):
    """Pick the ``(orbit_state, relative_orbit)`` present in BOTH windows.

    ``*_scores`` map an orbit key to a coverage score (scene count or covered
    area). The winner maximizes the weaker of the two window scores, tie-broken
    by the total — i.e. the geometry that is well-covered in *both* pre and
    flood, so ΔVV is computed on a consistent viewing geometry.
    """
    common = set(pre_scores) & set(flood_scores)
    if not common:
        raise ValueError("no orbit geometry common to both windows")

    def _key(k):
        return (min(pre_scores[k], flood_scores[k]), pre_scores[k] + flood_scores[k])

    return max(common, key=_key)
