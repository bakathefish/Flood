# sailaab/districts.py
"""Punjab district polygons: load, rasterize, and reduce a SAR flood mask to
per-district flooded area / fraction, plus the name crosswalk and spatial-CV
fold lookup that every downstream district statistic depends on.

Polygons live in ``data/punjab_districts.geojson`` (datameet Census-2011, ODbL;
20 districts, the same vintage as the ``FAO/GAUL/2015/level2`` collection used by
``gee/*.js``). The geojson ``district`` property carries the **datameet**
spelling. ``NAME_ALIASES`` / :func:`canonical_name` map that (plus common
GEE/press variants) onto the **GAUL-2015 ADM2_NAME** spellings used by
``sailaab.config`` and the GEE ``reduceRegions`` exports, so :func:`fold_of` and
any geojson<->export join reconcile cleanly. Pass ``canonicalize=True`` to
:func:`load_districts` to get GAUL-spelled names directly.

Only one district actually diverges between the two vintages:
``"Shahid Bhagat Singh Nagar"`` (datameet) == ``"Nawanshahr"`` (GAUL/config).
The remaining spelling entries below are defensive: variants that a GEE export
or press table might carry for districts we care about.

New dependency: ``shapely`` (geometry handling in callers/tests). ``rasterio``
is already required; ``numpy`` too.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from rasterio.features import rasterize as _rio_rasterize

from sailaab import config

# datameet Census-2011 / GEE / press spellings -> GAUL-2015 ADM2_NAME (config).
# Keys are matched after whitespace collapse; unknown names pass through.
NAME_ALIASES = {
    # the one real datameet<->GAUL divergence in Punjab
    "Shahid Bhagat Singh Nagar": "Nawanshahr",
    "Shaheed Bhagat Singh Nagar": "Nawanshahr",
    "SBS Nagar": "Nawanshahr",
    "S.B.S. Nagar": "Nawanshahr",
    "Nawan Shahr": "Nawanshahr",
    "Nawanshahr": "Nawanshahr",
    # defensive variants for fold districts (GEE / press / transliteration)
    "Ferozepur": "Firozpur",
    "Ferozepore": "Firozpur",
    "Firozepur": "Firozpur",
    "Ropar": "Rupnagar",
    "Roopnagar": "Rupnagar",
    "Tarn Taran Sahib": "Tarn Taran",
    "Taran Taran": "Tarn Taran",
    # non-fold districts whose modern/GAUL spelling differs from datameet
    "Sri Muktsar Sahib": "Muktsar",
    "S.A.S. Nagar": "Sahibzada Ajit Singh Nagar",
    "SAS Nagar": "Sahibzada Ajit Singh Nagar",
    "Mohali": "Sahibzada Ajit Singh Nagar",
}

DEFAULT_GEOJSON = (
    Path(__file__).resolve().parents[1] / "data" / "punjab_districts.geojson"
)


def canonical_name(name: str) -> str:
    """Map a district name (datameet / GEE / press variant) to the GAUL-2015
    ADM2_NAME spelling used by ``sailaab.config``. Whitespace is collapsed;
    unknown names are returned unchanged (after that normalization)."""
    if name is None:
        return name
    key = " ".join(str(name).split()).strip()
    return NAME_ALIASES.get(key, key)


def load_districts(path=DEFAULT_GEOJSON, canonicalize: bool = False):
    """Load district polygons from a GeoJSON FeatureCollection.

    Returns a list of ``(name, geometry_dict)`` sorted by name so that
    :func:`rasterize_districts` assigns stable labels across runs. ``name`` comes
    from the ``district`` property (falling back to ``DISTRICT`` / ``NAME``); with
    ``canonicalize=True`` it is passed through :func:`canonical_name` (GAUL
    spelling). ``geometry_dict`` is the raw GeoJSON geometry mapping, ready for
    :func:`rasterize_districts` or ``shapely.geometry.shape``.
    """
    with open(path, encoding="utf-8") as fh:
        gj = json.load(fh)
    feats = gj["features"] if isinstance(gj, dict) else gj
    out = []
    for feat in feats:
        props = feat.get("properties", {})
        name = props.get("district") or props.get("DISTRICT") or props.get("NAME")
        if canonicalize:
            name = canonical_name(name)
        out.append((name, feat["geometry"]))
    out.sort(key=lambda t: t[0] or "")
    return out


def rasterize_districts(geoms, transform, shape, *, all_touched: bool = False):
    """Burn district polygons into an ``int32`` label raster.

    ``geoms`` is an iterable of GeoJSON geometry dicts **or** ``(name, geom)``
    pairs (as returned by :func:`load_districts`). Label ``i + 1`` is assigned to
    the i-th geometry in order; background stays ``0`` (nodata). ``transform`` is
    an :class:`affine.Affine`, ``shape`` is ``(rows, cols)``. ``all_touched``
    forwards to :func:`rasterio.features.rasterize` (default False = pixel-centre
    rule).
    """
    shapes = []
    for i, item in enumerate(geoms, start=1):
        geom = item[1] if isinstance(item, tuple) else item
        shapes.append((geom, i))
    return _rio_rasterize(
        shapes,
        out_shape=shape,
        transform=transform,
        fill=0,
        dtype="int32",
        all_touched=all_touched,
    )


def district_fractions(label_array, mask_array, pixel_area_ha, names=None):
    """Per-district flooded hectares and flooded fraction (pure numpy).

    Parameters
    ----------
    label_array : int raster from :func:`rasterize_districts` (``0`` = background,
        excluded from the result).
    mask_array : flood mask, same shape. A pixel counts as flooded where its
        value is finite and ``> 0``; ``NaN`` (or any non-finite value) is treated
        as nodata and never counts as flood.
    pixel_area_ha : area of a single pixel in hectares.
    names : optional sequence; when given, results are keyed by ``names[label-1]``
        instead of the integer label (label ``i+1`` -> ``names[i]``).

    Returns
    -------
    dict
        ``key -> {"flooded_ha", "district_ha", "flooded_fraction"}`` for every
        non-zero label present in ``label_array``. ``district_ha`` is the label's
        total pixel count times ``pixel_area_ha``; ``flooded_fraction`` is
        ``flooded_ha / district_ha`` (``0.0`` when the district has no pixels).
    """
    labels = np.asarray(label_array)
    mask = np.asarray(mask_array, dtype="float64")
    flooded = np.isfinite(mask) & (mask > 0)

    out = {}
    for label in np.unique(labels):
        label = int(label)
        if label == 0:
            continue
        in_district = labels == label
        district_pixels = int(in_district.sum())
        flooded_pixels = int(np.logical_and(in_district, flooded).sum())
        district_ha = district_pixels * pixel_area_ha
        flooded_ha = flooded_pixels * pixel_area_ha
        fraction = (flooded_ha / district_ha) if district_ha > 0 else 0.0
        key = names[label - 1] if names is not None else label
        out[key] = {
            "flooded_ha": flooded_ha,
            "district_ha": district_ha,
            "flooded_fraction": fraction,
        }
    return out


def fold_of(name):
    """Return the spatial-CV fold for a district name: ``'ravi_beas'``,
    ``'sutlej'``, or ``None``.

    The name is canonicalized (:func:`canonical_name`) before checking
    ``config.FOLD_RAVI_BEAS`` / ``config.FOLD_SUTLEJ``, so datameet, GEE, and
    press spellings all resolve. Districts outside the two flood basins (e.g.
    Bathinda, Patiala, Sangrur) return ``None`` by design.
    """
    canon = canonical_name(name)
    if canon in config.FOLD_RAVI_BEAS:
        return "ravi_beas"
    if canon in config.FOLD_SUTLEJ:
        return "sutlej"
    return None
