# pipeline/fetch_gfm.py
"""Pull Copernicus GFM observed-flood-extent masks for the 2025 Punjab flood
from the KEYLESS GloFAS WMS and build the validation raster the repo expects.

Source: Global Flood Monitoring (GFM), Copernicus Emergency Management Service,
served by the GloFAS Open Web Service at ``https://ows.globalfloods.eu/glofas-ows/ows``.
No login / API key -- WMS 1.3.0 GetMap with an empty ``STYLES=`` and ``EPSG:3857``.
The service publishes styled RGBA PNGs (not class values); the colour decode rule
lives in ``sailaab.gfm`` and is documented in ``docs/notes/gfm-wms.md``.

This is the only WMS/rasterio-touching code for the GFM validation layer; all the
pure array logic (PNG->binary decode, tiling, stitching, union, cos-lat area) is in
``sailaab/gfm.py`` and is unit-tested. Rasters land under ``data/gfm/`` and are NOT
committed (gitignored).

Usage:
    python pipeline/fetch_gfm.py         # fetch, stitch, write tifs + quicklook

Outputs:
    data/gfm/gfm_punjab_<YYYYMMDD>.tif       per-day binary flood mask (uint8 0/1)
    data/gfm/gfm_punjab_refwater.tif         reference (permanent) water mask
    data/gfm/gfm_punjab_20250827_0905.tif    UNION flood (any day) minus ref water
    atlas/checks/gfm_union_20250827_0905.png quicklook of the union mask (committed)
"""

import io
import time
from pathlib import Path

import numpy as np
import rasterio
import requests
from PIL import Image
from pyproj import Transformer
from rasterio.transform import from_bounds

from sailaab.gfm import (
    flood_mask,
    ref_water_mask,
    paste_tile,
    tile_offsets,
    tile_bounds,
    union_masks,
    subtract_mask,
    web_mercator_area_km2,
)

OWS = "https://ows.globalfloods.eu/glofas-ows/ows"
UA = {"User-Agent": "sailaab-flood-validation/1.0 (Punjab 2025; keyless GFM WMS)"}

FLOOD_LAYER = "gfm_observed_flood_extent_group_layer"
REFWATER_LAYER = "gfm_reference_water_mask_group_layer"
FOOTPRINT_LAYER = "gfm_sentinel_1_footprint"

# Punjab bounding box, lon/lat (matches PUNJAB_BOX in pipeline/fetch_rain.py).
BBOX_LONLAT = (73.85, 29.53, 76.95, 32.60)  # minlon, minlat, maxlon, maxlat

# Compare window: daily observed flood extent, 2025-08-27 .. 2025-09-05 inclusive.
DAYS = [f"2025-08-{d:02d}" for d in range(27, 32)] + [
    f"2025-09-{d:02d}" for d in range(1, 6)
]

TARGET_PX_M = 100.0  # ~100 m effective resolution in EPSG:3857 metres
MAX_TILE = 2048  # server-safe tile size per side
REQUEST_PAUSE_S = 1.0  # polite pacing between WMS calls

GFM_DIR = Path("data/gfm")
UNION_TIF = GFM_DIR / "gfm_punjab_20250827_0905.tif"
REFWATER_TIF = GFM_DIR / "gfm_punjab_refwater.tif"
QUICKLOOK = Path("atlas/checks/gfm_union_20250827_0905.png")

_TF = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)


def bbox_3857():
    minlon, minlat, maxlon, maxlat = BBOX_LONLAT
    minx, miny = _TF.transform(minlon, minlat)
    maxx, maxy = _TF.transform(maxlon, maxlat)
    return (minx, miny, maxx, maxy)


def grid_shape(bounds):
    minx, miny, maxx, maxy = bounds
    ncols = int(round((maxx - minx) / TARGET_PX_M))
    nrows = int(round((maxy - miny) / TARGET_PX_M))
    return ncols, nrows


def _get(params, retries=4):
    """GET with polite pacing and exponential backoff on 5xx / network errors."""
    delay = 2.0
    for attempt in range(retries):
        try:
            r = requests.get(OWS, params=params, headers=UA, timeout=120)
            if r.status_code == 200 and (r.headers.get("content-type", "")).startswith(
                "image"
            ):
                return r.content
            if r.status_code < 500:
                raise RuntimeError(
                    f"WMS {r.status_code} {r.headers.get('content-type')}: "
                    f"{r.text[:200]}"
                )
        except requests.RequestException as exc:  # network hiccup
            if attempt == retries - 1:
                raise
            print(f"    net error ({exc}); backoff {delay:.0f}s")
        else:
            print(f"    server {r.status_code}; backoff {delay:.0f}s")
        time.sleep(delay)
        delay *= 2
    raise RuntimeError("WMS request failed after retries")


def _getmap_params(layer, time_iso, bounds, width, height):
    minx, miny, maxx, maxy = bounds
    return {
        "service": "WMS",
        "version": "1.3.0",
        "request": "GetMap",
        "layers": layer,
        "styles": "",  # MANDATORY empty style (omitting it triggers ServiceException)
        "crs": "EPSG:3857",
        "bbox": f"{minx},{miny},{maxx},{maxy}",
        "width": width,
        "height": height,
        "format": "image/png",
        "transparent": "true",
        "time": f"{time_iso}T00:00Z",
    }


def fetch_rgba_grid(layer, time_iso, bounds, ncols, nrows):
    """Tiled GetMap over the full grid, stitched into one (nrows, ncols, 4) array."""
    canvas = np.zeros((nrows, ncols, 4), dtype=np.uint8)
    for col_off, row_off, tw, th in tile_offsets(ncols, nrows, MAX_TILE):
        tb = tile_bounds(bounds, ncols, nrows, col_off, row_off, tw, th)
        png = _get(_getmap_params(layer, time_iso, tb, tw, th))
        tile = np.array(Image.open(io.BytesIO(png)).convert("RGBA"), dtype=np.uint8)
        paste_tile(canvas, tile, col_off, row_off)
        time.sleep(REQUEST_PAUSE_S)
    return canvas


def footprint_coverage(time_iso, bounds, size=1024):
    """Fraction of the bbox with an S1 acquisition footprint on this day (0..1)."""
    png = _get(_getmap_params(FOOTPRINT_LAYER, time_iso, bounds, size, size))
    time.sleep(REQUEST_PAUSE_S)
    arr = np.array(Image.open(io.BytesIO(png)).convert("RGBA"))
    return float((arr[..., 3] > 0).mean())


def write_mask_tif(path, mask, bounds):
    minx, miny, maxx, maxy = bounds
    nrows, ncols = mask.shape
    transform = from_bounds(minx, miny, maxx, maxy, ncols, nrows)
    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=nrows,
        width=ncols,
        count=1,
        dtype="uint8",
        crs="EPSG:3857",
        transform=transform,
        compress="deflate",
        nodata=0,
    ) as ds:
        ds.write(mask.astype("uint8"), 1)


def _downsample_any(mask, factor):
    """OR-pool a boolean mask by an integer factor so thin flood survives."""
    nrows, ncols = mask.shape
    ph = (-nrows) % factor
    pw = (-ncols) % factor
    if ph or pw:
        mask = np.pad(mask, ((0, ph), (0, pw)), constant_values=False)
    h, w = mask.shape
    return mask.reshape(h // factor, factor, w // factor, factor).any(axis=(1, 3))


def write_quicklook(path, flood, refwater, max_width=1500):
    """Quicklook PNG: union flood (pink) over permanent water (light blue) on white."""
    factor = max(1, int(np.ceil(flood.shape[1] / max_width)))
    f = _downsample_any(flood, factor)
    w = _downsample_any(refwater, factor)
    h, wd = f.shape
    rgb = np.full((h, wd, 3), 255, np.uint8)
    rgb[w] = (200, 224, 240)  # permanent water context
    rgb[f] = (232, 76, 120)  # union flood
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(rgb).save(path, optimize=True)
    return path.stat().st_size


def main():
    bounds = bbox_3857()
    ncols, nrows = grid_shape(bounds)
    total_km2 = web_mercator_area_km2(np.ones((nrows, ncols), bool), bounds)
    print(
        f"grid {ncols} x {nrows} px @ ~{TARGET_PX_M:.0f} m (EPSG:3857); "
        f"bbox area {total_km2:,.0f} km^2"
    )
    print(f"tiles/day: {len(tile_offsets(ncols, nrows, MAX_TILE))}")

    daily = {}
    covered, empty = [], []
    print("\nday          cover%   flood_px    flood_km2")
    for day in DAYS:
        cov = footprint_coverage(day, bounds)
        rgba = fetch_rgba_grid(FLOOD_LAYER, day, bounds, ncols, nrows)
        mask = flood_mask(rgba)
        daily[day] = mask
        km2 = web_mercator_area_km2(mask, bounds)
        write_mask_tif(GFM_DIR / f"gfm_punjab_{day.replace('-', '')}.tif", mask, bounds)
        (covered if cov > 0 else empty).append(day)
        flag = "" if cov > 0 else "  (no S1 pass)"
        print(f"{day}   {cov * 100:6.1f}   {int(mask.sum()):9d}   {km2:9.1f}{flag}")

    print("\nreference water mask ...")
    ref_rgba = fetch_rgba_grid(REFWATER_LAYER, DAYS[0], bounds, ncols, nrows)
    refwater = ref_water_mask(ref_rgba)
    write_mask_tif(REFWATER_TIF, refwater, bounds)

    union = union_masks(daily.values())
    union_minus = subtract_mask(union, refwater)
    write_mask_tif(UNION_TIF, union_minus, bounds)

    union_km2 = web_mercator_area_km2(union, bounds)
    final_km2 = web_mercator_area_km2(union_minus, bounds)
    ref_removed = int(union.sum() - union_minus.sum())
    size = write_quicklook(QUICKLOOK, union_minus, refwater)

    print(f"\nwrote {UNION_TIF}")
    print(f"wrote {REFWATER_TIF}")
    print(f"wrote {QUICKLOOK} ({size / 1024:.0f} KB)")
    print("\n=== UNION 2025-08-27 .. 2025-09-05 ===")
    print(f"days with S1 coverage : {len(covered)}  {covered}")
    print(f"days empty (no pass)  : {len(empty)}  {empty}")
    print(f"union flood (raw)     : {int(union.sum()):,} px  = {union_km2:,.0f} km^2")
    print(f"reference water rm    : {ref_removed:,} px")
    print(
        f"union flood - refwater: {int(union_minus.sum()):,} px  = {final_km2:,.0f} km^2"
    )
    print(f"share of bbox         : {100 * final_km2 / total_km2:.2f} %")


if __name__ == "__main__":
    main()
