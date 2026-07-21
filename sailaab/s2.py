# sailaab/s2.py
"""Pure-array logic for the independent Sentinel-2 optical truth set.

The 2025 Punjab flood is validated by a chain that is entirely SAR-derived
(Tier-A change detection + Copernicus GFM, and an RF trained on their agreement).
This module underpins an *independent* optical cross-check: photo-interpreted
standing-water points from Sentinel-2 L2A surface reflectance (different sensor,
different physics). See ``docs/notes/s2-truth.md`` for the pre-declared design and
the recession asymmetry that governs how the numbers are read.

Everything here is deterministic numpy/scipy -- no network, no rasterio -- so it is
unit-tested against small synthetic arrays in ``tests/test_s2.py``. All STAC /
rasterio IO lives in ``pipeline/fetch_s2_truth.py``.

Provided:
    * ``harmonize_reflectance`` - L2A DN -> surface reflectance (baseline-04.00+ offset).
    * ``ndwi``                  - McFeeters NDWI = (green - nir) / (green + nir).
    * ``classify_water``        - NDWI + SCL -> water / dry / uncertain decision rule.
    * ``binary_buffer``         - dilate a boolean mask (near-flood frontier).
    * ``draw_from_mask``        - deterministic flat-index draw from a boolean mask.
    * ``precision_recall``      - precision/recall from a binary_metrics confusion.
"""

from __future__ import annotations

import numpy as np
from scipy import ndimage

# Sentinel-2 L2A processing baseline >= 04.00 (Jan 2022+) stores surface
# reflectance as DN with a radiometric offset; harmonised reflectance is
# ``(DN + BOA_ADD_OFFSET) / QUANTIFICATION_VALUE``. All 2025 scenes are baseline
# 05.xx, for which BOA_ADD_OFFSET = -1000 and QUANTIFICATION_VALUE = 10000.
BOA_ADD_OFFSET = -1000.0
QUANTIFICATION = 10000.0

# SCL (scene-classification layer) classes that make a pixel unusable for optical
# water interpretation: 0 no-data, 1 saturated/defective, 3 cloud-shadow,
# 8 cloud-medium-prob, 9 cloud-high-prob, 10 thin-cirrus. (2 dark-area, 4 veg,
# 5 bare, 6 water, 7 unclassified, 11 snow are all "ground is visible".)
CLOUD_SCL = frozenset({0, 1, 3, 8, 9, 10})
WATER_SCL = 6

# Class codes returned by ``classify_water``.
WATER = 1
DRY = 0
UNCERTAIN = -1


def harmonize_reflectance(
    dn, offset: float = BOA_ADD_OFFSET, scale: float = QUANTIFICATION, nodata=0.0
) -> np.ndarray:
    """Sentinel-2 L2A digital numbers -> surface reflectance (float64).

    ``reflectance = (DN + offset) / scale``. Pixels equal to ``nodata`` (default
    ``0``, the L2A fill) become NaN *before* the offset is applied, so fill does
    not masquerade as a small negative reflectance. Values are intentionally NOT
    clipped at 0: dark open water can be marginally negative after the offset, and
    the NDWI ratio handles that correctly.
    """
    dn = np.asarray(dn, dtype="float64")
    out = (dn + offset) / scale
    if nodata is not None:
        out = np.where(dn == nodata, np.nan, out)
    return out


def ndwi(green, nir, eps: float = 1e-6) -> np.ndarray:
    """McFeeters NDWI ``= (green - nir) / (green + nir)``.

    Water is bright in green and dark in NIR, so open water is strongly positive.
    Inputs are surface reflectance (see :func:`harmonize_reflectance`). Where the
    denominator is within ``eps`` of zero (no signal / fill) the result is NaN;
    NaN inputs propagate to NaN.
    """
    green = np.asarray(green, dtype="float64")
    nir = np.asarray(nir, dtype="float64")
    denom = green + nir
    with np.errstate(invalid="ignore", divide="ignore"):
        out = (green - nir) / denom
    out = np.where(np.abs(denom) < eps, np.nan, out)
    return out


def classify_water(
    ndwi_val,
    scl,
    *,
    t_water: float,
    t_dry: float,
    invalid_scl=CLOUD_SCL,
) -> np.ndarray:
    """NDWI + SCL -> water / dry / uncertain decision rule (int8 code array).

    Returns ``WATER`` (1), ``DRY`` (0), or ``UNCERTAIN`` (-1) per element:

    * ``UNCERTAIN`` where the SCL class is in ``invalid_scl`` (cloud / shadow /
      no-data -- the ground is not optically visible), where ``ndwi_val`` is NaN,
      or where ``t_dry < ndwi_val < t_water`` (the deliberate dead-band that keeps
      only high-confidence points in the truth set).
    * ``WATER`` where ``ndwi_val >= t_water`` and the SCL is usable.
    * ``DRY``   where ``ndwi_val <= t_dry``   and the SCL is usable.

    ``t_dry <= t_water`` is required. Inputs broadcast to a common shape.
    """
    if t_dry > t_water:
        raise ValueError(f"t_dry ({t_dry}) must be <= t_water ({t_water})")
    nd = np.asarray(ndwi_val, dtype="float64")
    sc = np.asarray(scl)
    nd, sc = np.broadcast_arrays(nd, sc)

    invalid = np.zeros(sc.shape, dtype=bool)
    for c in invalid_scl:
        invalid |= sc == c
    invalid |= ~np.isfinite(nd)

    out = np.full(nd.shape, UNCERTAIN, dtype=np.int8)
    usable = ~invalid
    out[usable & (nd >= t_water)] = WATER
    out[usable & (nd <= t_dry)] = DRY
    # dead-band (t_dry < nd < t_water) stays UNCERTAIN via the initial fill.
    return out


def binary_buffer(mask, iterations: int = 1, connectivity: int = 8) -> np.ndarray:
    """Dilate a boolean mask by ``iterations`` pixels (near-flood frontier).

    ``connectivity`` 8 (default, 3x3 structure) or 4 (plus-shaped). Used to build
    the "dry pixels adjacent to flood" sampling stratum.
    """
    mask = np.asarray(mask, dtype=bool)
    if iterations <= 0:
        return mask.copy()
    if connectivity == 8:
        structure = np.ones((3, 3), dtype=int)
    elif connectivity == 4:
        structure = None
    else:
        raise ValueError("connectivity must be 4 or 8")
    return ndimage.binary_dilation(mask, structure=structure, iterations=iterations)


def draw_from_mask(mask, n: int, rng, *, exclude=None) -> np.ndarray:
    """Deterministically draw up to ``n`` flat (row-major) indices where ``mask``.

    ``exclude`` (optional boolean mask) removes pixels from the eligible pool
    (e.g. permanent water, or already-chosen points). When fewer than ``n``
    eligible pixels exist, all of them are returned. ``rng`` is a
    :class:`numpy.random.Generator`.
    """
    mask = np.asarray(mask, dtype=bool)
    if exclude is not None:
        mask = mask & ~np.asarray(exclude, dtype=bool)
    elig = np.flatnonzero(mask.ravel())
    if len(elig) <= n:
        return elig
    return np.sort(rng.choice(elig, size=n, replace=False))


def precision_recall(metrics: dict) -> dict:
    """Precision and recall from a :func:`sailaab.validation.binary_metrics` dict.

    ``precision = TP / (TP + FP)`` (of the mask's flood claims, the fraction that
    are truly water) and ``recall = TP / (TP + FN)`` (of true-water points, the
    fraction the mask caught). Each is NaN when its denominator is zero.
    """
    tp = metrics["tp"]
    fp = metrics["fp"]
    fn = metrics["fn"]
    prec = tp / (tp + fp) if (tp + fp) else float("nan")
    rec = tp / (tp + fn) if (tp + fn) else float("nan")
    return {"precision": prec, "recall": rec}
