# sailaab/exposure.py
"""Pure logic for population exposure: warp a per-pixel population raster onto a
flood-mask grid *conserving the head-count*, then sum people inside the flood
mask per district.

The one correctness trap here is resampling. A GHS-POP / WorldPop pixel holds a
**count** (people in that cell), not an intensity. Resampling counts directly
(e.g. 1 km -> 90 m) would multiply the total by ~(1000/90)^2. The conserving move
is to carry an area-normalised **density** (people per m^2) through the reprojection
and multiply back by the *target* pixel's ground area:

    density = counts / source_pixel_area          (counts_to_density)
    <reproject density onto the target grid>       (rasterio.warp, in the pipeline)
    counts' = density' * target_pixel_area         (density_to_counts)

For an equal-area source (GHSL Mollweide, 1e6 m^2/px) the source area is a
constant; for a geographic source it varies by row. On an EPSG:3857 target the
*true ground* pixel area shrinks as cos^2(lat) (:func:`webmerc_pixel_area_m2`,
same physics as :func:`sailaab.gfm.web_mercator_area_km2`); on a UTM target it is
simply ``|a*e|``. :func:`population_in_mask_by_district` then does the mask-sum,
mirroring the flood/nodata convention of
:func:`sailaab.districts.district_fractions` (a pixel is flooded where the mask is
finite and ``> 0``; non-finite population contributes nothing).

Everything here is deterministic numpy -- no rasterio, no network -- and is
unit-tested in ``tests/test_exposure.py``. The reproject / IO orchestration lives
in ``pipeline/compute_pop_exposure.py``.
"""

from __future__ import annotations

import numpy as np

R_WEBMERC = 6378137.0  # EPSG:3857 sphere radius (matches sailaab.gfm)


def counts_to_density(counts, pixel_area_m2, nodata=None):
    """Per-pixel population **counts** -> **density** (people per m^2).

    ``pixel_area_m2`` is a scalar (equal-area source) or an array broadcastable to
    ``counts`` (per-row/​per-pixel area for a geographic source). Cells equal to
    ``nodata`` (when given) or non-finite are treated as 0 people before dividing,
    so they carry no population through the warp. Returns float64.
    """
    c = np.asarray(counts, dtype="float64")
    valid = np.isfinite(c)
    if nodata is not None:
        valid &= c != nodata
    c = np.where(valid, c, 0.0)
    area = np.asarray(pixel_area_m2, dtype="float64")
    return c / area


def density_to_counts(density, pixel_area_m2):
    """**Density** (people per m^2) -> per-pixel population **counts**.

    Inverse of :func:`counts_to_density`; ``pixel_area_m2`` is the *target* grid's
    ground pixel area (scalar or broadcastable array). Non-finite density is
    treated as 0. Returns float64.
    """
    d = np.asarray(density, dtype="float64")
    d = np.where(np.isfinite(d), d, 0.0)
    area = np.asarray(pixel_area_m2, dtype="float64")
    return d * area


def webmerc_pixel_area_m2(transform, shape):
    """True ground area (m^2) of each pixel in a north-up EPSG:3857 grid.

    Web-Mercator inflates linear scale by 1/cos(lat), so a pixel's *ground* area is
    its projected area times cos^2(lat). The correction is applied per row using
    each row's centre latitude (inverse Mercator), matching
    :func:`sailaab.gfm.web_mercator_area_km2`. ``transform`` is an
    :class:`affine.Affine` (or 6-tuple in ``a,b,c,d,e,f`` order); ``shape`` is
    ``(nrows, ncols)``. Returns an ``(nrows, ncols)`` float64 array.
    """
    nrows, ncols = int(shape[0]), int(shape[1])
    px = abs(float(transform[0]))
    py = abs(float(transform[4]))
    top = float(transform[5])
    rows = np.arange(nrows)
    y_center = top - (rows + 0.5) * py
    lat = 2.0 * np.arctan(np.exp(y_center / R_WEBMERC)) - np.pi / 2.0
    area_row = px * py * np.cos(lat) ** 2
    return np.repeat(area_row[:, None], ncols, axis=1)


def total_population(pop_counts, label_array=None):
    """Sum of population counts (conservation check).

    Non-finite cells are ignored. With ``label_array`` given, only cells whose
    label is non-zero (inside a district) are summed -- i.e. the raster's estimate
    of the total population living inside the district polygons.
    """
    pop = np.asarray(pop_counts, dtype="float64")
    pop = np.where(np.isfinite(pop), pop, 0.0)
    if label_array is not None:
        pop = np.where(np.asarray(label_array) > 0, pop, 0.0)
    return float(pop.sum())


def population_in_mask_by_district(pop_counts, label_array, mask_array, names=None):
    """Per-district population inside a flood mask, plus each district's total.

    Parameters
    ----------
    pop_counts : per-pixel population counts on the mask grid (non-finite -> 0).
    label_array : int raster from :func:`sailaab.districts.rasterize_districts`
        (``0`` = background, excluded).
    mask_array : flood mask, same shape. A pixel counts as flooded where its value
        is finite and ``> 0`` (matches
        :func:`sailaab.districts.district_fractions`); non-finite is never flood.
    names : optional sequence; results are keyed by ``names[label - 1]`` instead of
        the integer label.

    Returns
    -------
    dict
        ``key -> {"pop_exposed", "pop_total", "exposed_fraction"}`` for every
        non-zero label present. ``pop_exposed`` is the population in flooded cells,
        ``pop_total`` the district's whole-polygon population, ``exposed_fraction``
        their ratio (``0.0`` when the district holds no population).
    """
    labels = np.asarray(label_array)
    pop = np.asarray(pop_counts, dtype="float64")
    pop = np.where(np.isfinite(pop), pop, 0.0)
    mask = np.asarray(mask_array, dtype="float64")
    flooded = np.isfinite(mask) & (mask > 0)

    out = {}
    for label in np.unique(labels):
        label = int(label)
        if label == 0:
            continue
        in_district = labels == label
        pop_total = float(pop[in_district].sum())
        pop_exposed = float(pop[in_district & flooded].sum())
        fraction = (pop_exposed / pop_total) if pop_total > 0 else 0.0
        key = names[label - 1] if names is not None else label
        out[key] = {
            "pop_exposed": pop_exposed,
            "pop_total": pop_total,
            "exposed_fraction": fraction,
        }
    return out
