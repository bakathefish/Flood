# sailaab/gfm.py
"""Pure logic for turning Copernicus GFM WMS PNG tiles into a binary flood mask.

The GloFAS keyless WMS (``https://ows.globalfloods.eu/glofas-ows/ows``) serves the
GFM ``gfm_observed_flood_extent_group_layer`` as a *styled* RGBA PNG, not raw class
values. The group layer paints several things on top of each other, so the decode
rule is colour-based, not "any non-transparent pixel":

    * observed flood extent fill  -> pink   (232, 76, 120)   <- the signal
    * S1 swath / granule outline  -> red    (192, 0, 0)      <- reject (thin lines)
    * acquisition-time label      -> orange (255, 118, 13)   <- reject (burnt-in text)
    * minor overlay class         -> green  (112, 173, 71)   <- reject
    * reference (permanent) water -> blue   (0, 75, 114)     <- reject / subtract

Palette sampled 2026-07-21; see ``docs/notes/gfm-wms.md``. All functions here are
numpy-only and side-effect free; the WMS fetch and rasterio writes live in
``pipeline/fetch_gfm.py``.
"""

import numpy as np

# GFM WMS rendered palette (R, G, B), sampled 2026-07-21.
FLOOD_RGB = (232, 76, 120)  # observed flood extent fill
REF_WATER_RGB = (0, 75, 114)  # reference water mask fill


def color_mask(rgba, target_rgb, tol=48, alpha_min=96):
    """Boolean mask where an RGBA image matches ``target_rgb``.

    A pixel matches when each of R, G, B is within ``tol`` of the target and the
    alpha channel is at least ``alpha_min`` (drops faint anti-aliased halos).

    Parameters
    ----------
    rgba : array_like, shape (..., 4)
        RGBA image (uint8 range values).
    target_rgb : tuple(int, int, int)
    tol : int
        Per-channel absolute tolerance.
    alpha_min : int
        Minimum alpha to accept.
    """
    a = np.asarray(rgba)
    if a.ndim < 1 or a.shape[-1] != 4:
        raise ValueError(f"expected RGBA with last dim 4, got shape {a.shape}")
    r = a[..., 0].astype(np.int16)
    g = a[..., 1].astype(np.int16)
    b = a[..., 2].astype(np.int16)
    alpha = a[..., 3].astype(np.int16)
    tr, tg, tb = target_rgb
    return (
        (alpha >= alpha_min)
        & (np.abs(r - tr) <= tol)
        & (np.abs(g - tg) <= tol)
        & (np.abs(b - tb) <= tol)
    )


def flood_mask(rgba, tol=48, alpha_min=96):
    """Boolean observed-flood-extent mask from a GFM WMS RGBA tile."""
    return color_mask(rgba, FLOOD_RGB, tol=tol, alpha_min=alpha_min)


def ref_water_mask(rgba, tol=48, alpha_min=96):
    """Boolean reference (permanent) water mask from a GFM WMS RGBA tile."""
    return color_mask(rgba, REF_WATER_RGB, tol=tol, alpha_min=alpha_min)


def union_masks(masks):
    """Logical OR over an iterable of equal-shape boolean arrays."""
    out = None
    for m in masks:
        m = np.asarray(m, dtype=bool)
        if out is None:
            out = m.copy()
        elif m.shape != out.shape:
            raise ValueError(f"shape mismatch in union: {m.shape} vs {out.shape}")
        else:
            out |= m
    if out is None:
        raise ValueError("union_masks: empty iterable")
    return out


def subtract_mask(mask, remove):
    """``mask`` with ``remove`` pixels cleared (mask AND NOT remove)."""
    mask = np.asarray(mask, dtype=bool)
    remove = np.asarray(remove, dtype=bool)
    if mask.shape != remove.shape:
        raise ValueError(f"shape mismatch: {mask.shape} vs {remove.shape}")
    return mask & ~remove


def tile_offsets(width, height, max_tile=2048):
    """Split a ``width`` x ``height`` pixel grid into tiles no larger than
    ``max_tile`` per side.

    Returns a row-major list of ``(col_off, row_off, tile_w, tile_h)`` that covers
    the grid exactly, with no overlap.
    """
    if width <= 0 or height <= 0:
        raise ValueError("width and height must be positive")
    if max_tile <= 0:
        raise ValueError("max_tile must be positive")

    def spans(n):
        out = []
        off = 0
        while off < n:
            out.append((off, min(max_tile, n - off)))
            off += max_tile
        return out

    tiles = []
    for row_off, th in spans(height):
        for col_off, tw in spans(width):
            tiles.append((col_off, row_off, tw, th))
    return tiles


def tile_bounds(full_bounds, full_w, full_h, col_off, row_off, tile_w, tile_h):
    """World bounds ``(minx, miny, maxx, maxy)`` of a pixel tile inside a
    north-up grid whose full pixel extent maps to ``full_bounds``.

    Row 0 is the north (max-y) edge, matching image / raster convention.
    """
    minx, miny, maxx, maxy = full_bounds
    px = (maxx - minx) / full_w
    py = (maxy - miny) / full_h
    tminx = minx + col_off * px
    tmaxx = minx + (col_off + tile_w) * px
    tmaxy = maxy - row_off * py
    tminy = maxy - (row_off + tile_h) * py
    return (tminx, tminy, tmaxx, tmaxy)


def paste_tile(canvas, tile, col_off, row_off):
    """Paste ``tile`` into ``canvas`` at the given pixel offset (mutates canvas)."""
    th = tile.shape[0]
    tw = tile.shape[1]
    canvas[row_off : row_off + th, col_off : col_off + tw, ...] = tile
    return canvas


def web_mercator_area_km2(mask, bounds):
    """Ground area (km^2) of True pixels in a north-up EPSG:3857 grid.

    Web-Mercator inflates linear scale by 1 / cos(lat), so the true ground area of
    a pixel is its projected area times cos^2(lat). The correction is applied per
    pixel row using each row's centre latitude (inverse Mercator), which matters
    across the ~3 deg latitude span of the Punjab bounding box.
    """
    mask = np.asarray(mask, dtype=bool)
    nrows, ncols = mask.shape
    minx, miny, maxx, maxy = bounds
    px = (maxx - minx) / ncols
    py = (maxy - miny) / nrows
    r_earth = 6378137.0  # EPSG:3857 sphere radius
    rows = np.arange(nrows)
    y_center = maxy - (rows + 0.5) * py
    lat = 2.0 * np.arctan(np.exp(y_center / r_earth)) - np.pi / 2.0
    cos2 = np.cos(lat) ** 2
    per_row = mask.sum(axis=1).astype(float)
    area_m2 = float(np.sum(per_row * px * py * cos2))
    return area_m2 / 1.0e6
