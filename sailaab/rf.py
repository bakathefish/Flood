# sailaab/rf.py
"""Pure-array helpers for the 2025 Punjab Random-Forest flood classifier.

Everything here is deterministic numpy — no network, no sklearn, no rasterio — so
it is unit-tested against small synthetic arrays in ``tests/test_rf.py``. The IO /
STAC / training orchestration lives in ``pipeline/rf_build_features.py``,
``pipeline/rf_aux_layers.py`` and ``pipeline/rf_train.py``.

Provided:
    * ``slope_degrees``            - terrain slope from a DEM on a regular grid.
    * ``agreement_labels``         - Tier-A / GFM agreement strata (+ perm-water excl).
    * ``sample_features``          - build an (n_points, n_features) matrix at indices.
    * ``xy_from_index``            - flat pixel index -> CRS x/y pixel centres.
    * ``stratified_balanced_sample`` - class-balanced, district-spread point sample.
"""

from __future__ import annotations

import numpy as np


def slope_degrees(dem, pixel_size_m: float) -> np.ndarray:
    """Terrain slope in degrees from an elevation array on a regular grid.

    ``slope = degrees(arctan(sqrt((dz/dx)^2 + (dz/dy)^2)))`` with the horizontal
    gradient computed by :func:`numpy.gradient` at spacing ``pixel_size_m`` (metres)
    on both axes. A flat surface gives 0; a surface that rises one pixel-size per
    pixel gives 45 deg. NaN elevation propagates into NaN slope around it.
    """
    dem = np.asarray(dem, dtype="float64")
    if dem.ndim != 2:
        raise ValueError(f"expected a 2-D DEM, got shape {dem.shape}")
    gy, gx = np.gradient(dem, float(pixel_size_m))
    return np.degrees(np.arctan(np.hypot(gx, gy)))


def agreement_labels(
    tier_a,
    gfm_union,
    ref_water,
    pre_vv_db,
    *,
    abs_vv_thresh: float = -15.0,
    valid=None,
) -> np.ndarray:
    """Agreement-strata training labels (int8): ``1`` flood, ``0`` dry, ``-1`` excluded.

    * ``1`` (positive) where Tier-A **and** GFM both say flood.
    * ``0`` (negative) where Tier-A **and** GFM both say dry.
    * ``-1`` (excluded) where the two disagree, where the pixel is permanent water
      (``ref_water`` OR ``pre_vv_db < abs_vv_thresh`` dark-dry-season proxy), or
      where ``pre_vv_db`` is not finite (no SAR data). An optional ``valid`` mask
      forces ``-1`` wherever it is False.

    All inputs are broadcast to a common shape; booleans are taken as-is, NaN in
    ``pre_vv_db`` marks invalid pixels.
    """
    tier_a = np.asarray(tier_a, dtype=bool)
    gfm_union = np.asarray(gfm_union, dtype=bool)
    ref_water = np.asarray(ref_water, dtype=bool)
    pre_vv_db = np.asarray(pre_vv_db, dtype="float64")

    finite = np.isfinite(pre_vv_db)
    permanent = ref_water | (finite & (pre_vv_db < abs_vv_thresh))
    ok = finite & ~permanent
    if valid is not None:
        ok = ok & np.asarray(valid, dtype=bool)

    both_flood = tier_a & gfm_union
    both_dry = (~tier_a) & (~gfm_union)

    out = np.full(np.broadcast(tier_a, gfm_union, pre_vv_db).shape, -1, dtype=np.int8)
    out[ok & both_dry] = 0
    out[ok & both_flood] = 1
    return out


def sample_features(feature_arrays, idx_flat) -> np.ndarray:
    """Stack features at flat pixel indices into an ``(n_points, n_features)`` matrix.

    ``feature_arrays`` is a sequence of equal-shape 2-D arrays; column ``k`` of the
    result is ``feature_arrays[k]`` sampled (row-major ravel) at ``idx_flat``.
    """
    idx_flat = np.asarray(idx_flat)
    cols = [np.asarray(a).ravel()[idx_flat] for a in feature_arrays]
    if not cols:
        return np.empty((len(idx_flat), 0))
    return np.column_stack(cols).astype("float64")


def xy_from_index(idx_flat, transform, width: int):
    """Pixel-centre CRS coordinates for flat (row-major) indices.

    ``transform`` is a 6-tuple ``(a, b, c, d, e, f)`` in affine/GDAL order (as
    ``list(rasterio.Affine)[:6]``): ``x = a*col + b*row + c``, ``y = d*col + e*row
    + f``, evaluated at pixel centres (``col+0.5``, ``row+0.5``). Returns
    ``(xs, ys)`` float arrays.
    """
    idx_flat = np.asarray(idx_flat)
    a, b, c, d, e, f = transform
    row = idx_flat // int(width)
    col = idx_flat % int(width)
    cc = col + 0.5
    rr = row + 0.5
    xs = a * cc + b * rr + c
    ys = d * cc + e * rr + f
    return xs.astype("float64"), ys.astype("float64")


def _spread_pick(elig, dist, n, rng):
    """Pick ~``n`` flat indices from ``elig`` (with per-index district ``dist``),
    spread as evenly as the data allow across the distinct districts."""
    if len(elig) <= n:
        return elig.copy()
    uniq = np.unique(dist)
    per = int(np.ceil(n / len(uniq)))
    picked_parts = []
    leftover_parts = []
    for u in uniq:
        pos = np.flatnonzero(dist == u)  # positions within elig for this district
        if len(pos) <= per:
            picked_parts.append(elig[pos])
        else:
            sel = rng.choice(pos, size=per, replace=False)
            picked_parts.append(elig[sel])
            rest = np.setdiff1d(pos, sel, assume_unique=True)
            leftover_parts.append(elig[rest])
    picked = (
        np.concatenate(picked_parts) if picked_parts else np.array([], dtype=elig.dtype)
    )
    if len(picked) > n:
        picked = rng.choice(picked, size=n, replace=False)
    elif len(picked) < n and leftover_parts:
        leftover = np.concatenate(leftover_parts)
        need = n - len(picked)
        if len(leftover):
            extra = rng.choice(leftover, size=min(need, len(leftover)), replace=False)
            picked = np.concatenate([picked, extra])
    return picked


def stratified_balanced_sample(label, district, n_per_class, *, rng, classes=(0, 1)):
    """Class-balanced, district-spread sample of pixel indices.

    For each class in ``classes`` draw up to ``n_per_class`` flat (row-major)
    indices from pixels whose ``label`` equals that class **and** whose
    ``district`` label is non-zero (background/out-of-Punjab pixels are never
    sampled). Within a class the draw is spread across districts; when a class has
    fewer than ``n_per_class`` eligible pixels, all of them are returned.

    Returns a 1-D int array of flat indices (classes concatenated in order).
    ``rng`` is a :class:`numpy.random.Generator` for deterministic output.
    """
    label = np.asarray(label).ravel()
    district = np.asarray(district).ravel()
    parts = []
    for c in classes:
        elig = np.flatnonzero((label == c) & (district > 0))
        if len(elig) == 0:
            continue
        parts.append(_spread_pick(elig, district[elig], int(n_per_class), rng))
    if not parts:
        return np.array([], dtype=np.intp)
    return np.concatenate(parts)
