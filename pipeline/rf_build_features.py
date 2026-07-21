# pipeline/rf_build_features.py
"""Statewide 90 m Sentinel-1 feature stack + regenerated Tier-A mask for the RF
flood classifier (the judged AI stage).

Descending tracks, both 2025 windows (``sailaab.config``), median composites of
VV and VH. Reuses the proven, SAS-re-sign-fixed COG reader in
``pipeline.local_tier_a`` (so the central-stripe nodata hole of the pre-fix run
is filled). Writes float32 GeoTIFFs to ``data/rasters/`` (gitignored) plus a
grid sidecar the other RF pipeline scripts align to:

    rf_vv_pre.tif  rf_vv_flood.tif  rf_vh_pre.tif  rf_vh_flood.tif
    rf_dvv.tif     rf_dvh.tif                                   (float32, NaN nodata)
    local_tierA_punjab_tierA_floodmask.tif                      (uint8, regenerated)
    rf_grid.json                                                (grid metadata)

Pure array logic lives in ``sailaab.sar_local`` / ``sailaab.rf``; this is a thin
IO runner mirroring the other ``pipeline/*.py`` CLIs.

Usage:
    python -m pipeline.rf_build_features            # 90 m statewide, descending
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import rasterio

from sailaab.config import FLOOD_2025, PRE_2025
from sailaab.sar_local import flooded_hectares, sieve_mask, tier_a_mask
import pipeline.local_tier_a as lta
from pipeline.local_tier_a import (
    AOIS,
    DST_CRS,
    composite_window,
    open_client,
    search_window,
    target_grid,
)

RES = 90.0
ORBIT_STATE = (
    "descending"  # descending tracks (34 + 107 + 136), per prior statewide run
)
RASTER_DIR = Path("data/rasters")

# Keep the proven 8-way concurrency from the single-VV statewide run: more workers
# (tried 12) saturate the home link / trip anonymous throttling and stall the run.
lta.MAX_WORKERS = 8


def _by_state(items):
    out = {}
    for it in items:
        st = it.properties.get("sat:orbit_state")
        out.setdefault(st, []).append(it)
    return out


def _save_float(path, arr, transform):
    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=arr.shape[0],
        width=arr.shape[1],
        count=1,
        dtype="float32",
        crs=DST_CRS,
        transform=transform,
        nodata=float("nan"),
        compress="deflate",
        predictor=3,
    ) as dst:
        dst.write(arr.astype("float32"), 1)


def _save_uint8(path, arr, transform):
    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=arr.shape[0],
        width=arr.shape[1],
        count=1,
        dtype="uint8",
        crs=DST_CRS,
        transform=transform,
        nodata=0,
        compress="lzw",
    ) as dst:
        dst.write(arr.astype("uint8"), 1)


def build():
    t0 = time.time()
    bbox = AOIS["punjab"]
    client = open_client()

    pre_items = search_window(client, bbox, PRE_2025)
    flood_items = search_window(client, bbox, FLOOD_2025)
    pre_by = _by_state(pre_items)
    flood_by = _by_state(flood_items)
    print(f"[rf_build] pre={len(pre_items)} flood={len(flood_items)} items", flush=True)
    print(
        "  pre states :",
        {k: len(v) for k, v in pre_by.items()},
        "\n  flood states:",
        {k: len(v) for k, v in flood_by.items()},
        flush=True,
    )
    pre_sel = pre_by[ORBIT_STATE]
    flood_sel = flood_by[ORBIT_STATE]
    print(
        f"  using {ORBIT_STATE}: pre {len(pre_sel)} / flood {len(flood_sel)} scenes",
        flush=True,
    )

    transform, width, height = target_grid(bbox, RES)
    px_area = RES * RES
    print(f"  grid {width}x{height} @ {RES} m  ({DST_CRS})", flush=True)

    # Four median composites (dB). composite_window reads each asset onto the grid.
    vv_pre = composite_window(
        pre_sel, transform, width, height, asset="vv", tag="vv_pre"
    )
    print(f"  vv_pre done  (+{time.time() - t0:.0f}s)", flush=True)
    vv_flood = composite_window(
        flood_sel, transform, width, height, asset="vv", tag="vv_flood"
    )
    print(f"  vv_flood done  (+{time.time() - t0:.0f}s)", flush=True)
    vh_pre = composite_window(
        pre_sel, transform, width, height, asset="vh", tag="vh_pre"
    )
    print(f"  vh_pre done  (+{time.time() - t0:.0f}s)", flush=True)
    vh_flood = composite_window(
        flood_sel, transform, width, height, asset="vh", tag="vh_flood"
    )
    print(f"  vh_flood done  (+{time.time() - t0:.0f}s)", flush=True)

    dvv = vv_flood - vv_pre
    dvh = vh_flood - vh_pre
    mask = sieve_mask(tier_a_mask(dvv, vv_flood, vv_pre))

    valid = np.isfinite(dvv)
    flooded_ha = flooded_hectares(mask, px_area)
    valid_ha = float(valid.sum()) * px_area / 1e4

    RASTER_DIR.mkdir(parents=True, exist_ok=True)
    _save_float(RASTER_DIR / "rf_vv_pre.tif", vv_pre, transform)
    _save_float(RASTER_DIR / "rf_vv_flood.tif", vv_flood, transform)
    _save_float(RASTER_DIR / "rf_vh_pre.tif", vh_pre, transform)
    _save_float(RASTER_DIR / "rf_vh_flood.tif", vh_flood, transform)
    _save_float(RASTER_DIR / "rf_dvv.tif", dvv, transform)
    _save_float(RASTER_DIR / "rf_dvh.tif", dvh, transform)
    _save_uint8(RASTER_DIR / "local_tierA_punjab_tierA_floodmask.tif", mask, transform)

    grid = {
        "crs": DST_CRS,
        "res_m": RES,
        "width": width,
        "height": height,
        "transform": list(transform)[:6],
        "bbox_lonlat": bbox,
        "orbit_state": ORBIT_STATE,
        "scenes": {"pre": len(pre_sel), "flood": len(flood_sel)},
        "valid_fraction": round(float(valid.mean()), 4),
        "vv_pre_median_db": round(float(np.nanmedian(vv_pre)), 2),
        "vv_flood_median_db": round(float(np.nanmedian(vv_flood)), 2),
        "vh_pre_median_db": round(float(np.nanmedian(vh_pre)), 2),
        "vh_flood_median_db": round(float(np.nanmedian(vh_flood)), 2),
        "tierA_flooded_ha": round(flooded_ha, 1),
        "valid_ha": round(valid_ha, 1),
        "runtime_s": round(time.time() - t0, 1),
    }
    with open(RASTER_DIR / "rf_grid.json", "w") as fh:
        json.dump(grid, fh, indent=2)
    print("=== rf_build_features DONE ===", flush=True)
    print(json.dumps(grid, indent=2), flush=True)
    return grid


if __name__ == "__main__":
    build()
