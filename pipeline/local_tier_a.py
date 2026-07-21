# pipeline/local_tier_a.py
"""Login-free Tier-A flood mask from Microsoft Planetary Computer (anonymous STAC).

No Google Earth Engine, no accounts, no subscription key. Signs assets with
``planetary_computer.sign_inplace`` (anonymous, reduced rate). Searches
``sentinel-1-rtc`` (terrain-corrected gamma0, linear power), picks the orbit
geometry best covered in BOTH the pre and flood windows, median-composites VV on
that geometry via windowed / overview COG reads, computes ΔVV and the Tier-A mask
(see ``sailaab.sar_local``), then writes quicklook PNGs and a GeoTIFF.

Array logic lives in ``sailaab/sar_local.py`` (unit-tested); this module is the
thin IO / STAC runner, mirroring the style of the other ``pipeline/*.py`` CLIs.

Examples
--------
    python -m pipeline.local_tier_a --aoi kapurthala --res 30
    python -m pipeline.local_tier_a --aoi punjab --res 90 --orbit-mode state
"""

from __future__ import annotations

import argparse
import json
import math
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import planetary_computer as pc
import pystac_client
import rasterio
from rasterio.enums import Resampling
from rasterio.transform import from_origin
from rasterio.vrt import WarpedVRT
from rasterio.warp import transform_bounds

from sailaab.config import FLOOD_2025, PRE_2025
from sailaab.sar_local import (
    best_common_orbit,
    flooded_hectares,
    median_composite,
    sieve_mask,
    tier_a_mask,
    to_db,
)

STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"
COLLECTION = "sentinel-1-rtc"
FALLBACK_COLLECTION = "sentinel-1-grd"
NODATA_IN = -32768.0  # RTC gamma0 nodata (verified from asset metadata)
DST_CRS = "EPSG:32643"  # UTM 43N — all of Punjab sits in this zone; RTC is native here

# AOI bounding boxes in lon/lat (EPSG:4326), mirroring sailaab/config.py comments.
AOIS = {
    "kapurthala": (75.05, 31.07, 75.70, 31.66),
    "punjab": (73.85, 29.53, 76.95, 32.60),
}

# GDAL knobs for efficient remote COG reads (Azure blob + SAS token).
GDAL_ENV = dict(
    GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
    GDAL_HTTP_MULTIRANGE="YES",
    GDAL_HTTP_MERGE_CONSECUTIVE_RANGES="YES",
    VSI_CACHE="TRUE",
)

CHECKS_DIR = Path("atlas/checks")
RASTER_DIR = Path("data/rasters")

MAX_WORKERS = 8  # parallel COG reads (IO-bound; each read opens its own handle)


# --------------------------------------------------------------------------- #
# STAC search
# --------------------------------------------------------------------------- #
def open_client():
    return pystac_client.Client.open(STAC_URL, modifier=pc.sign_inplace)


def search_window(client, bbox, window, collection=COLLECTION):
    search = client.search(
        collections=[collection],
        bbox=bbox,
        datetime=f"{window[0]}/{window[1]}",
    )
    return list(search.items())


def group_by_orbit(items):
    """dict keyed by (sat:orbit_state, sat:relative_orbit) -> [items]."""
    out = {}
    for it in items:
        key = (
            it.properties.get("sat:orbit_state"),
            it.properties.get("sat:relative_orbit"),
        )
        out.setdefault(key, []).append(it)
    return out


# --------------------------------------------------------------------------- #
# Grid + COG reads
# --------------------------------------------------------------------------- #
def target_grid(bbox_ll, res, dst_crs=DST_CRS):
    left, bottom, right, top = transform_bounds("EPSG:4326", dst_crs, *bbox_ll)
    width = int(math.ceil((right - left) / res))
    height = int(math.ceil((top - bottom) / res))
    transform = from_origin(left, top, res, res)
    return transform, width, height


def read_asset(href, transform, width, height, retries=2):
    """Read one asset onto the target grid at target resolution via WarpedVRT.

    GDAL picks appropriate overviews, so only a downsampled window crosses the
    wire. nodata (and out-of-footprint) pixels come back as NaN. The GDAL config
    is applied per call so this is safe to run from a thread pool. Transient
    network errors are retried; a scene that still fails becomes an all-NaN
    layer (dropped by the NaN-median composite) rather than killing the run.
    """
    last_err = None
    for attempt in range(retries + 1):
        try:
            with rasterio.Env(**GDAL_ENV):
                with rasterio.open(href) as src:
                    with WarpedVRT(
                        src,
                        crs=DST_CRS,
                        transform=transform,
                        width=width,
                        height=height,
                        resampling=Resampling.average,
                        src_nodata=src.nodata if src.nodata is not None else NODATA_IN,
                        nodata=float("nan"),
                        dtype="float32",
                    ) as vrt:
                        arr = vrt.read(1).astype("float64")
            arr[~np.isfinite(arr)] = np.nan
            arr[arr <= 0] = np.nan  # non-positive linear power is nodata
            return arr
        except Exception as err:  # transient HTTP/GDAL errors, or expired SAS
            last_err = err
            # Anonymous SAS tokens live ~45-60 min; on long runs hrefs signed at
            # search time expire mid-composite (GDAL then reports "not recognized
            # as being in a supported file format"). Re-sign before retrying.
            try:
                href = pc.sign(href.split("?", 1)[0])
            except Exception:
                pass  # keep the old href; the plain retry may still succeed
            time.sleep(2 * (attempt + 1))
    print(f"  WARN dropping scene after {retries + 1} attempts: {last_err}")
    return np.full((height, width), np.nan)


def composite_window(items, transform, width, height, asset="vv", tag=""):
    """Median-composite an asset (linear power) over a list of items -> dB.

    COG reads run in parallel (IO-bound); each thread opens its own handle.
    """
    hrefs = [it.assets[asset].href for it in items]
    n = len(hrefs)

    def _read(ih):
        i, h = ih
        t0 = time.time()
        arr = read_asset(h, transform, width, height)
        print(
            f"    [{tag}] scene {i + 1}/{n} read in {time.time() - t0:.0f}s", flush=True
        )
        return arr

    with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, n)) as ex:
        layers = list(ex.map(_read, enumerate(hrefs)))
    return to_db(median_composite(np.stack(layers)))


# --------------------------------------------------------------------------- #
# Orbit selection (best coverage in BOTH windows)
# --------------------------------------------------------------------------- #
def coverage_scores(groups, transform, width, height, asset="vv"):
    """Valid-pixel count per orbit group at the (coarse) probe grid."""
    scores = {}
    for key, items in groups.items():
        comp = composite_window(items, transform, width, height, asset)
        scores[key] = int(np.isfinite(comp).sum())
    return scores


def pick_orbit(pre_groups, flood_groups, bbox, probe_res):
    """Choose the (orbit_state, relative_orbit) best covered in both windows,
    measured on a coarse probe grid (true covered area, not just scene count).
    Only orbits present in BOTH windows are probed — others can never win."""
    common = set(pre_groups) & set(flood_groups)
    if not common:
        raise ValueError("no orbit geometry common to both windows")
    ptransform, pw, ph = target_grid(bbox, probe_res)
    pre_scores = coverage_scores(
        {k: v for k, v in pre_groups.items() if k in common}, ptransform, pw, ph
    )
    flood_scores = coverage_scores(
        {k: v for k, v in flood_groups.items() if k in common}, ptransform, pw, ph
    )
    key = best_common_orbit(pre_scores, flood_scores)
    return key, pre_scores, flood_scores


# --------------------------------------------------------------------------- #
# Outputs
# --------------------------------------------------------------------------- #
def _save_db_png(arr_db, path, title, vmin=-25, vmax=0):
    fig, ax = plt.subplots(figsize=(7, 7))
    im = ax.imshow(arr_db, cmap="Greys_r", vmin=vmin, vmax=vmax)
    ax.set_title(title, fontsize=10)
    ax.axis("off")
    fig.colorbar(im, ax=ax, shrink=0.7, label="VV (dB)")
    fig.savefig(path, dpi=110, bbox_inches="tight")
    plt.close(fig)


def _save_overlay_png(vv_flood_db, mask, path, title):
    fig, ax = plt.subplots(figsize=(7, 7))
    ax.imshow(vv_flood_db, cmap="Greys_r", vmin=-25, vmax=0)
    overlay = np.zeros((*mask.shape, 4))
    overlay[mask] = (0.0, 0.71, 1.0, 0.85)  # cyan, opaque where flooded
    ax.imshow(overlay)
    ax.set_title(title, fontsize=10)
    ax.axis("off")
    fig.savefig(path, dpi=110, bbox_inches="tight")
    plt.close(fig)


def write_geotiff(mask, transform, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=mask.shape[0],
        width=mask.shape[1],
        count=1,
        dtype="uint8",
        crs=DST_CRS,
        transform=transform,
        nodata=0,
        compress="lzw",
    ) as dst:
        dst.write(mask.astype("uint8"), 1)


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def run(aoi_name, res, probe_res, orbit_mode, save_prefix, orbit_override=None):
    t_start = time.time()
    bbox = AOIS[aoi_name]
    client = open_client()

    pre_items = search_window(client, bbox, PRE_2025)
    flood_items = search_window(client, bbox, FLOOD_2025)
    pre_groups = group_by_orbit(pre_items)
    flood_groups = group_by_orbit(flood_items)
    print(f"[{aoi_name}] pre items={len(pre_items)} flood items={len(flood_items)}")
    print("  pre orbits :", {str(k): len(v) for k, v in pre_groups.items()})
    print("  flood orbits:", {str(k): len(v) for k, v in flood_groups.items()})

    if orbit_mode == "state":
        # Merge relative orbits within each orbit_state for statewide coverage.
        def by_state(groups):
            out = {}
            for (state, _rel), items in groups.items():
                out.setdefault((state, "all"), []).extend(items)
            return out

        pre_groups = by_state(pre_groups)
        flood_groups = by_state(flood_groups)

    if orbit_override is not None:
        orbit = orbit_override
        if orbit not in pre_groups or orbit not in flood_groups:
            raise ValueError(
                f"orbit {orbit} not present in both windows; "
                f"pre={sorted(map(str, pre_groups))} flood={sorted(map(str, flood_groups))}"
            )
    else:
        orbit, _pre_scores, _flood_scores = pick_orbit(
            pre_groups, flood_groups, bbox, probe_res
        )
    pre_sel = pre_groups[orbit]
    flood_sel = flood_groups[orbit]
    print(
        f"  chosen orbit {orbit}: pre {len(pre_sel)} scene(s), flood {len(flood_sel)} scene(s)"
    )

    transform, width, height = target_grid(bbox, res)
    px_area = res * res
    print(f"  grid {width}x{height} @ {res} m  ({DST_CRS})")

    vv_pre = composite_window(pre_sel, transform, width, height, tag="pre")
    vv_flood = composite_window(flood_sel, transform, width, height, tag="flood")

    dvv = vv_flood - vv_pre
    valid = np.isfinite(dvv)
    mask = sieve_mask(tier_a_mask(dvv, vv_flood, vv_pre))

    flooded_ha = flooded_hectares(mask, px_area)
    bbox_ha = width * height * px_area / 1e4
    valid_ha = float(valid.sum()) * px_area / 1e4
    frac_bbox = flooded_ha / bbox_ha * 100 if bbox_ha else float("nan")
    frac_valid = flooded_ha / valid_ha * 100 if valid_ha else float("nan")

    CHECKS_DIR.mkdir(parents=True, exist_ok=True)
    p_pre = CHECKS_DIR / f"{save_prefix}_pre_db.png"
    p_flood = CHECKS_DIR / f"{save_prefix}_flood_db.png"
    p_mask = CHECKS_DIR / f"{save_prefix}_mask_overlay.png"
    _save_db_png(vv_pre, p_pre, f"{aoi_name} pre-flood VV (dB) — orbit {orbit}")
    _save_db_png(vv_flood, p_flood, f"{aoi_name} flood VV (dB) — orbit {orbit}")
    _save_overlay_png(vv_flood, mask, p_mask, f"{aoi_name} Tier-A flood mask")

    tif = RASTER_DIR / f"{save_prefix}_tierA_floodmask.tif"
    write_geotiff(mask, transform, tif)

    report = {
        "aoi": aoi_name,
        "bbox": bbox,
        "resolution_m": res,
        "crs": DST_CRS,
        "collection": COLLECTION,
        "orbit": {"state": orbit[0], "relative_orbit": orbit[1]},
        "scenes": {"pre": len(pre_sel), "flood": len(flood_sel)},
        "coverage_valid_fraction": round(float(valid.mean()), 4),
        "vv_pre_median_db": round(float(np.nanmedian(vv_pre)), 2),
        "vv_flood_median_db": round(float(np.nanmedian(vv_flood)), 2),
        "flooded_ha": round(flooded_ha, 1),
        "bbox_ha": round(bbox_ha, 1),
        "flooded_pct_of_bbox": round(frac_bbox, 2),
        "flooded_pct_of_valid": round(frac_valid, 2),
        "runtime_s": round(time.time() - t_start, 1),
        "outputs": {
            "pre_png": str(p_pre),
            "flood_png": str(p_flood),
            "mask_png": str(p_mask),
            "geotiff": str(tif),
        },
    }
    print(json.dumps(report, indent=2))
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--aoi", choices=list(AOIS), default="kapurthala")
    ap.add_argument("--res", type=float, default=30.0, help="working resolution (m)")
    ap.add_argument(
        "--probe-res",
        type=float,
        default=200.0,
        help="coarse res for orbit selection (m)",
    )
    ap.add_argument(
        "--orbit-mode",
        choices=["single", "state"],
        default="single",
        help="single = one (orbit_state, rel_orbit); state = all rel orbits of one state",
    )
    ap.add_argument(
        "--orbit",
        default=None,
        help="skip the coverage probe: 'ascending:27' (single) or 'ascending' (state mode)",
    )
    ap.add_argument("--prefix", default=None, help="output filename prefix")
    args = ap.parse_args()
    prefix = args.prefix or f"local_tierA_{args.aoi}"
    orbit_override = None
    if args.orbit:
        if ":" in args.orbit:
            state, rel = args.orbit.split(":", 1)
            orbit_override = (state, int(rel))
        else:
            orbit_override = (args.orbit, "all")
    run(args.aoi, args.res, args.probe_res, args.orbit_mode, prefix, orbit_override)


if __name__ == "__main__":
    main()
