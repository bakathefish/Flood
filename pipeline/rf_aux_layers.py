# pipeline/rf_aux_layers.py
"""Auxiliary RF layers on the canonical 90 m Punjab grid (EPSG:32643):

    * slope (deg) from Copernicus DEM GLO-30  (PC `cop-dem-glo-30`, anonymous)
    * cropland (0/1) from ESA WorldCover 2021 class 40 (PC `esa-worldcover`)
    * GFM union flood + reference water, warped from the EPSG:3857 GFM tifs

All reads are anonymous Planetary Computer / local GFM tifs; the grid is the exact
`pipeline.local_tier_a.target_grid(punjab, 90)` used by the SAR feature stack, so
every layer is pixel-aligned. Outputs (gitignored) -> data/rasters/:

    rf_dem.tif  rf_slope.tif  rf_cropland.tif  rf_gfm_union.tif  rf_gfm_refwater.tif

DEM is time-boxed: if the mosaic loop runs past ~45 min it aborts and writes no
slope (the RF stack then proceeds without it), per the mission's degrade rule.
"""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import planetary_computer as pc
import pystac_client
import rasterio
from rasterio.enums import Resampling
from rasterio.vrt import WarpedVRT
from rasterio.warp import reproject

import pipeline.local_tier_a as lta
from pipeline.local_tier_a import AOIS, DST_CRS, target_grid
from sailaab.rf import slope_degrees

STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"
RASTER_DIR = Path("data/rasters")
GFM_DIR = Path("data/gfm")
DEM_TIME_BUDGET_S = 45 * 60
RES = 90.0


def _client():
    return pystac_client.Client.open(STAC_URL, modifier=pc.sign_inplace)


def read_onto_grid(href, transform, width, height, resampling, retries=2):
    """WarpedVRT-read one COG asset onto the canonical grid; NaN outside footprint."""
    last = None
    for attempt in range(retries + 1):
        try:
            with rasterio.Env(**lta.GDAL_ENV):
                with rasterio.open(href) as src:
                    with WarpedVRT(
                        src,
                        crs=DST_CRS,
                        transform=transform,
                        width=width,
                        height=height,
                        resampling=resampling,
                        src_nodata=src.nodata,
                        nodata=float("nan"),
                        dtype="float32",
                    ) as vrt:
                        arr = vrt.read(1).astype("float64")
            arr[~np.isfinite(arr)] = np.nan
            return arr
        except Exception as err:  # transient HTTP/GDAL or expired SAS
            last = err
            try:
                href = pc.sign(href.split("?", 1)[0])
            except Exception:
                pass
            time.sleep(2 * (attempt + 1))
    print(f"    WARN dropping tile after {retries + 1} tries: {last}", flush=True)
    return np.full((height, width), np.nan)


def _coalesce(mosaic, tile):
    """First-valid-wins mosaic (fill NaN holes in `mosaic` from `tile`)."""
    if mosaic is None:
        return tile.copy()
    fill = np.isnan(mosaic) & np.isfinite(tile)
    mosaic[fill] = tile[fill]
    return mosaic


def _save(path, arr, dtype, nodata, transform, predictor=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    kwargs = dict(
        driver="GTiff",
        height=arr.shape[0],
        width=arr.shape[1],
        count=1,
        dtype=dtype,
        crs=DST_CRS,
        transform=transform,
        nodata=nodata,
        compress="deflate",
    )
    if predictor:
        kwargs["predictor"] = predictor
    with rasterio.open(path, "w", **kwargs) as dst:
        dst.write(arr.astype(dtype), 1)


def build_dem_slope(client, transform, width, height):
    bbox = AOIS["punjab"]
    items = list(client.search(collections=["cop-dem-glo-30"], bbox=bbox).items())
    print(f"[dem] {len(items)} GLO-30 tiles", flush=True)
    t0 = time.time()
    mosaic = None
    for i, it in enumerate(items):
        if time.time() - t0 > DEM_TIME_BUDGET_S:
            print("[dem] TIME BUDGET EXCEEDED — aborting slope", flush=True)
            return None
        arr = read_onto_grid(
            it.assets["data"].href, transform, width, height, Resampling.bilinear
        )
        mosaic = _coalesce(mosaic, arr)
        print(
            f"  [dem] tile {i + 1}/{len(items)} "
            f"valid={np.isfinite(mosaic).mean() * 100:.1f}%  (+{time.time() - t0:.0f}s)",
            flush=True,
        )
    if mosaic is None:
        return None
    slope = slope_degrees(mosaic, RES)
    _save(
        RASTER_DIR / "rf_dem.tif",
        mosaic,
        "float32",
        float("nan"),
        transform,
        predictor=3,
    )
    _save(
        RASTER_DIR / "rf_slope.tif",
        slope,
        "float32",
        float("nan"),
        transform,
        predictor=3,
    )
    print(
        f"[dem] slope done: median={np.nanmedian(slope):.2f} deg "
        f"p95={np.nanpercentile(slope, 95):.2f} deg",
        flush=True,
    )
    return slope


def build_cropland(client, transform, width, height):
    bbox = AOIS["punjab"]
    items = [
        it
        for it in client.search(collections=["esa-worldcover"], bbox=bbox).items()
        if "/2021/" in it.assets["map"].href or "/v200/" in it.assets["map"].href
    ]
    print(f"[wc] {len(items)} WorldCover-2021 tiles", flush=True)
    mosaic = None
    for i, it in enumerate(items):
        arr = read_onto_grid(
            it.assets["map"].href, transform, width, height, Resampling.nearest
        )
        mosaic = _coalesce(mosaic, arr)
        print(f"  [wc] tile {i + 1}/{len(items)}", flush=True)
    cls = np.rint(np.where(np.isfinite(mosaic), mosaic, 0)).astype("int16")
    cropland = (cls == 40).astype("uint8")  # WorldCover class 40 = cropland
    _save(RASTER_DIR / "rf_cropland.tif", cropland, "uint8", 0, transform)
    print(
        f"[wc] cropland pixels = {int(cropland.sum()):,} "
        f"({cropland.mean() * 100:.1f}% of grid)",
        flush=True,
    )
    return cropland


def warp_gfm(transform, width, height):
    out = {}
    for name, src_path in [
        ("rf_gfm_union", GFM_DIR / "gfm_punjab_20250827_0905.tif"),
        ("rf_gfm_refwater", GFM_DIR / "gfm_punjab_refwater.tif"),
    ]:
        if not src_path.exists():
            print(f"[gfm] MISSING {src_path} — skipping", flush=True)
            continue
        with rasterio.open(src_path) as src:
            src_arr = src.read(1)
            dst = np.zeros((height, width), dtype="uint8")
            reproject(
                source=src_arr,
                destination=dst,
                src_transform=src.transform,
                src_crs=src.crs,
                dst_transform=transform,
                dst_crs=DST_CRS,
                resampling=Resampling.nearest,
                src_nodata=src.nodata,
                dst_nodata=0,
            )
        _save(RASTER_DIR / f"{name}.tif", dst, "uint8", 0, transform)
        out[name] = dst
        print(f"[gfm] {name}: {int(dst.sum()):,} px on canonical grid", flush=True)
    return out


def main():
    transform, width, height = target_grid(AOIS["punjab"], RES)
    print(f"[aux] canonical grid {width}x{height} @ {RES} m ({DST_CRS})", flush=True)
    client = _client()
    warp_gfm(transform, width, height)
    build_cropland(client, transform, width, height)
    build_dem_slope(client, transform, width, height)
    print("=== rf_aux_layers DONE ===", flush=True)


if __name__ == "__main__":
    main()
