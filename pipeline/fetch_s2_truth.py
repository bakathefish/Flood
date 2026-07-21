# pipeline/fetch_s2_truth.py
"""Independent Sentinel-2 optical truth set for the 2025 Punjab flood masks.

The whole validation chain is SAR-derived: Tier-A change detection, Copernicus
GFM, and an RF trained on their *agreement* and reported against GFM. A skeptic
calls that circular. This runner builds an **independent** cross-check from a
different sensor and different physics -- photo-interpreted standing-water points
from Sentinel-2 L2A surface reflectance (anonymous Microsoft Planetary Computer
STAC, login-free, ``sign_inplace``) -- and scores RF / Tier-A / GFM-union against
it. See ``docs/notes/s2-truth.md`` for the pre-declared design and the recession
asymmetry that governs how the numbers are read.

Because monsoon cloud hides the 26-27 Aug flood peak, the usable optical scenes
are post-peak (Sep onward, into recession). S2-water therefore **confirms** flood
(validates precision/commission strongly), while S2-dry does **not** refute Aug
flooding (recession) -- so mask-positive/S2-dry points are reported as a
recession-explained fraction, never counted as hard errors.

S2 granules over the flood belt are native EPSG:32643 (UTM 43N) -- identical CRS
to the 90 m mask grid -- so each truth point is sampled by a small **windowed COG
read** in native coordinates (a 2x2 10 m block -> 20 m, no reprojection), which
keeps bandwidth tiny and transparently skips no-data / partial-granule pixels.

Pure array logic (NDWI, harmonisation, water decision rule, sampling) lives in
``sailaab/s2.py`` (unit-tested test-first); this is the thin IO / STAC runner,
mirroring ``pipeline/local_tier_a.py`` and ``pipeline/rf_aux_layers.py``.

Run:  ``python -m pipeline.fetch_s2_truth``
Outputs (committed): ``data/s2_truth_points_2025.csv``,
``atlas/checks/s2_truth_examples.png``.
"""

from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import planetary_computer as pc
import pystac_client
import rasterio
from pyproj import Transformer
from rasterio.enums import Resampling
from rasterio.transform import from_origin
from rasterio.vrt import WarpedVRT
from rasterio.windows import Window
from rasterio.warp import transform_bounds, transform_geom
from shapely.geometry import Point, shape

from pipeline.local_tier_a import AOIS, DST_CRS, target_grid
from sailaab.districts import canonical_name, load_districts, rasterize_districts
from sailaab.s2 import (
    CLOUD_SCL,
    DRY,
    WATER,
    binary_buffer,
    classify_water,
    draw_from_mask,
    harmonize_reflectance,
    ndwi,
    precision_recall,
)
from sailaab.validation import binary_metrics

STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"
COLLECTION = "sentinel-2-l2a"
RES = 20.0  # effective NDWI sampling resolution (2x2 of native 10 m), per mission

# Sampling region: the three named flood-belt districts (their union bbox is used
# only to search granules; points are constrained to the district polygons).
NAMED_DISTRICTS = ("Firozpur", "Kapurthala", "Tarn Taran")
SEARCH_BBOX_LL = (73.885, 29.947, 75.911, 31.651)  # 3-district union, lon/lat

# Earliest-first post-peak dates (all FULL-coverage R005-orbit granules over the
# belt). Each truth point takes its class from the EARLIEST date that is
# cloud-free AND covered at that point (least recession); later dates only
# backfill cloudy stragglers.
#   09-10 = 14 d post-peak (earliest; central belt ~11 % cloud)
#   09-18 = 22 d (clean central belt, 5.9 %)
#   09-23 = 27 d (pristine full belt, 0 %) -- backstop
DATES = ["2025-09-10", "2025-09-18", "2025-09-23"]
CALIB_DATE = "2025-09-23"  # pristine scene used to calibrate/verify thresholds

# NDWI water/dry thresholds, CALIBRATED on Harike (permanent water) vs dry
# cropland on the pristine 2025-09-23 scene (see docs/notes/s2-truth.md sec 3):
# dry-land NDWI p98 = -0.27 (confidently negative); turbid Punjab flood water and
# the Harike wetland straddle 0. McFeeters open-water threshold 0.0; a dead-band
# down to -0.20 drops ambiguous turbid/moist pixels; <= -0.20 is confident dry.
T_WATER = 0.0
T_DRY = -0.20

# Harike wetland (Beas-Sutlej confluence) calibration window, lon/lat.
HARIKE_LL = (74.83, 31.05, 75.12, 31.27)

RASTER_DIR = Path("data/rasters")
CHECKS_DIR = Path("atlas/checks")
OUT_CSV = Path("data/s2_truth_points_2025.csv")

# Stratified sampling: sub-sample each mask's positives so every mask's precision
# is well estimated; plus a near-flood dry frontier and a random background.
N_MASK_POS = 55  # per mask (RF / Tier-A / GFM)
N_NEAR = 60  # dry pixels adjacent to the flood union (recession/omission frontier)
N_RANDOM = 60  # uniform background inside the 3 districts
NEAR_BUFFER_PX = 3  # ~270 m dilation at 90 m
SEED = 42

GDAL_ENV = dict(
    GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
    GDAL_HTTP_MULTIRANGE="YES",
    GDAL_HTTP_MERGE_CONSECUTIVE_RANGES="YES",
    VSI_CACHE="TRUE",
    GDAL_HTTP_TIMEOUT="240",
    GDAL_HTTP_CONNECTTIMEOUT="30",
    GDAL_HTTP_LOW_SPEED_LIMIT="10240",
    GDAL_HTTP_LOW_SPEED_TIME="60",
    GDAL_HTTP_MAX_RETRY="2",
    GDAL_HTTP_RETRY_DELAY="3",
)

_TO_LL = Transformer.from_crs(DST_CRS, "EPSG:4326", always_xy=True)


# --------------------------------------------------------------------------- #
# STAC helpers
# --------------------------------------------------------------------------- #
def open_client():
    return pystac_client.Client.open(STAC_URL, modifier=pc.sign_inplace)


def search_date(client, bbox_ll, date):
    return list(
        client.search(
            collections=[COLLECTION], bbox=bbox_ll, datetime=f"{date}/{date}"
        ).items()
    )


def sub_grid(bbox_ll, res=RES):
    left, bottom, right, top = transform_bounds("EPSG:4326", DST_CRS, *bbox_ll)
    w = int(math.ceil((right - left) / res))
    h = int(math.ceil((top - bottom) / res))
    return from_origin(left, top, res, res), w, h


def read_asset(href, transform, width, height, resampling, retries=2):
    """WarpedVRT-read one COG asset onto a target grid; nodata -> NaN (re-signs
    the SAS token on retry, as in pipeline/local_tier_a.read_asset). Used only for
    the small calibration window and the quicklook chips."""
    last = None
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
                        resampling=resampling,
                        src_nodata=src.nodata if src.nodata is not None else 0,
                        nodata=float("nan"),
                        dtype="float32",
                    ) as vrt:
                        return vrt.read(1)
        except Exception as err:
            last = err
            try:
                href = pc.sign(href.split("?", 1)[0])
            except Exception:
                pass
            time.sleep(2 * (attempt + 1))
    print(f"    WARN dropping asset after {retries + 1} tries: {last}", flush=True)
    return np.full((height, width), np.nan, dtype="float32")


def _coalesce(mosaic, tile):
    if mosaic is None:
        return tile.copy()
    fill = ~np.isfinite(mosaic) & np.isfinite(tile)
    mosaic[fill] = tile[fill]
    return mosaic


def read_points_native(href, xs, ys, size, retries=2):
    """Windowed reads of a COG at native resolution/CRS (EPSG:32643) for points.

    For each (x, y) reads a ``size`` x ``size`` pixel block centred on the pixel
    containing the point and returns the mean of its non-nodata values (NaN if the
    block is all nodata / out of footprint). ``size=2`` on a 10 m band ~ a 20 m
    sample; ``size=1`` reads the single covering pixel (SCL). Re-signs SAS on
    retry. Assumes the asset CRS is EPSG:32643 (true for Punjab S2 tiles)."""
    n = len(xs)
    out = np.full(n, np.nan)
    for attempt in range(retries + 1):
        try:
            with rasterio.Env(**GDAL_ENV):
                with rasterio.open(href) as ds:
                    T = ds.transform
                    nod = ds.nodata if ds.nodata is not None else 0
                    # S2 Punjab tiles are native EPSG:32643 (== DST_CRS); reproject
                    # the query points only if some other tile CRS turns up.
                    px, py = xs, ys
                    if ds.crs is not None and ds.crs.to_epsg() != 32643:
                        tf = Transformer.from_crs(DST_CRS, ds.crs, always_xy=True)
                        px, py = tf.transform(xs, ys)
                    for k in range(n):
                        col = (px[k] - T.c) / T.a
                        row = (py[k] - T.f) / T.e
                        ci = int(math.floor(col - size / 2.0 + 0.5))
                        ri = int(math.floor(row - size / 2.0 + 0.5))
                        a = ds.read(
                            1,
                            window=Window(ci, ri, size, size),
                            boundless=True,
                            fill_value=nod,
                        ).astype("float64")
                        valid = a[a != nod]
                        if valid.size:
                            out[k] = valid.mean()
            return out
        except Exception as err:
            last = err
            try:
                href = pc.sign(href.split("?", 1)[0])
            except Exception:
                pass
            time.sleep(2 * (attempt + 1))
    print(f"    WARN point-read failed after {retries + 1} tries: {last}", flush=True)
    return out


# --------------------------------------------------------------------------- #
# Masks + strata on the 90 m canonical grid
# --------------------------------------------------------------------------- #
def _read_mask(path):
    with rasterio.open(path) as ds:
        return ds.read(1) > 0


def load_masks_and_grid():
    transform, width, height = target_grid(AOIS["punjab"], 90.0)
    shape_hw = (height, width)
    pairs = load_districts(canonicalize=True)
    dnames = [n for n, _ in pairs]
    geoms = [transform_geom("EPSG:4326", DST_CRS, g) for _, g in pairs]
    districts = rasterize_districts(geoms, transform, shape_hw)
    named_labels = {i + 1 for i, n in enumerate(dnames) if n in NAMED_DISTRICTS}
    in_named = np.isin(districts, list(named_labels))
    return {
        "transform": transform,
        "width": width,
        "height": height,
        "shape": shape_hw,
        "rf": _read_mask(RASTER_DIR / "rf_flood_2025.tif"),
        "tierA": _read_mask(RASTER_DIR / "local_tierA_punjab_tierA_floodmask.tif"),
        "gfm": _read_mask(RASTER_DIR / "rf_gfm_union.tif"),
        "refw": _read_mask(RASTER_DIR / "rf_gfm_refwater.tif"),
        "districts": districts,
        "dnames": dnames,
        "in_named": in_named,
    }


def build_candidates(M, rng):
    """Stratified candidate flat indices on the 90 m grid + a stratum label each.

    Strata (all restricted to the 3 named districts, permanent water excluded):
      rf / tierA / gfm : each mask's flood positives (sub-sampled for precision)
      near             : dry pixels within a dilation of the flood union
      random           : uniform background
    """
    base = M["in_named"] & ~M["refw"]  # never sample permanent water
    union = M["rf"] | M["tierA"] | M["gfm"]
    near = binary_buffer(union, NEAR_BUFFER_PX) & ~union

    chosen = np.zeros(M["shape"], dtype=bool)
    idx_list, strat_list = [], []

    def take(mask, n, tag):
        idx = draw_from_mask(mask & base, n, rng, exclude=chosen)
        chosen.ravel()[idx] = True
        idx_list.append(idx)
        strat_list.append(np.full(len(idx), tag))
        return len(idx)

    for tag, mask in [("rf_pos", M["rf"]), ("tierA_pos", M["tierA"]),
                      ("gfm_pos", M["gfm"])]:
        take(mask, N_MASK_POS, tag)
    take(near, N_NEAR, "near_dry")
    take(base, N_RANDOM, "random")

    return np.concatenate(idx_list), np.concatenate(strat_list)


def xy_of(idx, transform, width):
    a, _, c, _, e, f = list(transform)[:6]
    row = idx // width
    col = idx % width
    return c + (col + 0.5) * a, f + (row + 0.5) * e


# --------------------------------------------------------------------------- #
# Sample S2 at points: earliest cloud-free covered look (windowed native reads)
# --------------------------------------------------------------------------- #
def sample_points_s2(client, xs, ys):
    n = len(xs)
    lon, lat = _TO_LL.transform(xs, ys)
    out_ndwi = np.full(n, np.nan)
    out_scl = np.full(n, np.nan)
    out_date = np.array([""] * n, dtype=object)
    provenance = {}
    cloud = np.array(sorted(CLOUD_SCL))

    for date in DATES:
        need = out_date == ""
        if not need.any():
            break
        items = search_date(client, SEARCH_BBOX_LL, date)
        provenance[date] = {
            "items": [it.id for it in items],
            "cloud_cover": [round(it.properties.get("eo:cloud_cover", -1), 1) for it in items],
        }
        g = np.full(n, np.nan)
        nr = np.full(n, np.nan)
        sc = np.full(n, np.nan)
        t0 = time.time()
        for it in items:
            geom = shape(it.geometry)
            inside = need & np.isnan(g)
            sel = np.array(
                [
                    inside[k] and geom.contains(Point(lon[k], lat[k]))
                    for k in range(n)
                ]
            )
            if not sel.any():
                continue
            idxs = np.flatnonzero(sel)
            gg = read_points_native(it.assets["B03"].href, xs[idxs], ys[idxs], 2)
            nn = read_points_native(it.assets["B08"].href, xs[idxs], ys[idxs], 2)
            ss = read_points_native(it.assets["SCL"].href, xs[idxs], ys[idxs], 1)
            got = np.isfinite(gg) & np.isfinite(nn)
            g[idxs[got]] = gg[got]
            nr[idxs[got]] = nn[got]
            sc[idxs[got]] = ss[got]
        gr = harmonize_reflectance(g, nodata=None)
        ni = harmonize_reflectance(nr, nodata=None)
        nd = ndwi(gr, ni)
        clean = need & np.isfinite(nd) & np.isfinite(sc) & ~np.isin(sc, cloud)
        out_ndwi[clean] = nd[clean]
        out_scl[clean] = sc[clean]
        out_date[clean] = date
        print(
            f"[s2] {date}: {len(items)} granules; assigned {int(clean.sum())} "
            f"(cumulative {int((out_date != '').sum())}/{n}) in {time.time() - t0:.0f}s",
            flush=True,
        )
    return out_ndwi, out_scl, out_date, provenance


# --------------------------------------------------------------------------- #
# Threshold calibration record (Harike water vs dry land)
# --------------------------------------------------------------------------- #
def calibration_record(client):
    tr, w, h = sub_grid(HARIKE_LL, RES)
    items = search_date(client, HARIKE_LL, CALIB_DATE)
    if not items:
        return {"note": "calibration scene unavailable"}
    green = nir = scl = None
    for it in items:
        green = _coalesce(green, read_asset(it.assets["B03"].href, tr, w, h, Resampling.average))
        nir = _coalesce(nir, read_asset(it.assets["B08"].href, tr, w, h, Resampling.average))
        scl = _coalesce(scl, read_asset(it.assets["SCL"].href, tr, w, h, Resampling.nearest))
    nd = ndwi(harmonize_reflectance(green.astype("float64"), nodata=None),
              harmonize_reflectance(nir.astype("float64"), nodata=None))
    scl = np.where(np.isfinite(scl), scl, 0)
    clear = ~np.isin(scl, np.array(sorted(CLOUD_SCL))) & np.isfinite(nd)

    refw = read_asset(str(RASTER_DIR / "rf_gfm_refwater.tif"), tr, w, h, Resampling.nearest) > 0
    rf = read_asset(str(RASTER_DIR / "rf_flood_2025.tif"), tr, w, h, Resampling.nearest) > 0
    ta = read_asset(str(RASTER_DIR / "local_tierA_punjab_tierA_floodmask.tif"), tr, w, h, Resampling.nearest) > 0
    gf = read_asset(str(RASTER_DIR / "rf_gfm_union.tif"), tr, w, h, Resampling.nearest) > 0
    from scipy import ndimage

    far = ~ndimage.binary_dilation(refw | gf, iterations=25)
    water_anchor = nd[clear & refw]
    scl6 = nd[clear & (scl == 6)]
    dry_anchor = nd[clear & (~rf) & (~ta) & (~gf) & (~refw) & far]

    def pcts(arr):
        if not len(arr):
            return None
        return {q: round(float(np.percentile(arr, q)), 3)
                for q in (2, 5, 25, 50, 75, 95, 98)}

    rec = {
        "calib_date": CALIB_DATE,
        "scene_ids": [it.id for it in items],
        "t_water": T_WATER,
        "t_dry": T_DRY,
        "harike_refwater_ndwi": {"n": int(len(water_anchor)), "pctl": pcts(water_anchor)},
        "scl_water_ndwi": {"n": int(len(scl6)), "pctl": pcts(scl6)},
        "dry_land_ndwi": {"n": int(len(dry_anchor)), "pctl": pcts(dry_anchor)},
    }
    if len(dry_anchor):
        rec["dry_at_or_below_t_dry_frac"] = round(float(np.mean(dry_anchor <= T_DRY)), 3)
    if len(scl6):
        rec["sclwater_at_or_above_t_water_frac"] = round(float(np.mean(scl6 >= T_WATER)), 3)
    return rec


# --------------------------------------------------------------------------- #
# Scoring (recession asymmetry separated)
# --------------------------------------------------------------------------- #
def score_masks(df):
    ref = (df["s2_class"] == "water").to_numpy()
    results = {
        "n_classified": int(len(df)),
        "n_s2_water": int(ref.sum()),
        "n_s2_dry": int((~ref).sum()),
    }
    per_mask = {}
    for col in ["rf", "tierA", "gfm"]:
        pred = df[col].to_numpy().astype(bool)
        m = binary_metrics(pred, ref)
        pr = precision_recall(m)
        n_pos = int(pred.sum())
        recession = m["fp"] / n_pos if n_pos else float("nan")
        per_mask[col] = {
            "n_flood_points": n_pos,
            "tp": m["tp"], "fp": m["fp"], "fn": m["fn"], "tn": m["tn"],
            "precision_on_water": round(pr["precision"], 3) if np.isfinite(pr["precision"]) else None,
            "recall_on_water": round(pr["recall"], 3) if np.isfinite(pr["recall"]) else None,
            "recession_explained_frac": round(recession, 3) if np.isfinite(recession) else None,
            "on_s2_water": {"caught_tp": m["tp"], "missed_fn": m["fn"]},
            "on_s2_dry": {"flagged_fp": m["fp"], "correct_tn": m["tn"]},
            "f1": round(m["f1"], 3), "iou": round(m["iou"], 3),
        }
    results["per_mask"] = per_mask
    return results


# --------------------------------------------------------------------------- #
# Quicklook: 6 true-colour chips with point markers (water + dry examples)
# --------------------------------------------------------------------------- #
def _chip_bbox_ll(x, y, half_m):
    return transform_bounds(
        DST_CRS, "EPSG:4326", x - half_m - 100, y - half_m - 100,
        x + half_m + 100, y + half_m + 100,
    )


def _read_rgb_chip(client, x, y, date, half_m=700):
    tr = from_origin(x - half_m, y + half_m, RES, RES)
    w = h = int(2 * half_m / RES)
    items = search_date(client, _chip_bbox_ll(x, y, half_m), date)
    r = g = b = None
    for it in items:
        r = _coalesce(r, read_asset(it.assets["B04"].href, tr, w, h, Resampling.average))
        g = _coalesce(g, read_asset(it.assets["B03"].href, tr, w, h, Resampling.average))
        b = _coalesce(b, read_asset(it.assets["B02"].href, tr, w, h, Resampling.average))
    if r is None:
        return None
    rgb = np.dstack([
        harmonize_reflectance(c.astype("float64"), nodata=None) for c in (r, g, b)
    ])
    return np.nan_to_num(np.clip(rgb / 0.30, 0, 1))  # 0..0.30 reflectance -> 0..1


def make_quicklook(client, df, path):
    water = df[df["s2_class"] == "water"]
    dry = df[df["s2_class"] == "dry"]
    n_each = 3
    pick_w = water.sample(min(n_each, len(water)), random_state=SEED)
    pick_d = dry.sample(min(n_each, len(dry)), random_state=SEED)
    picks = pd.concat([pick_w, pick_d]).reset_index(drop=True)
    if picks.empty:
        print("[s2] no classified points for quicklook", flush=True)
        return
    fig, axes = plt.subplots(2, n_each, figsize=(11, 7.8))
    for ax in axes.ravel():
        ax.axis("off")
    for k, r in picks.iterrows():
        ax = axes[k // n_each, k % n_each]
        chip = _read_rgb_chip(client, r["x"], r["y"], r["date_s2"])
        if chip is None:
            continue
        ax.imshow(chip, origin="upper")
        cen = chip.shape[0] // 2
        col = "#00e5ff" if r["s2_class"] == "water" else "#ffd21f"
        ax.plot(cen, cen, marker="o", mfc="none", mec=col, mew=2.4, ms=17)
        flags = "".join(t for t, on in
                        [("R", r["rf"]), ("T", r["tierA"]), ("G", r["gfm"])] if on) or "-"
        ax.set_title(
            f"{r['s2_class'].upper()}  NDWI={r['ndwi']:+.2f}\n"
            f"{r['date_s2']}  {r['district']}  masks:{flags}",
            fontsize=8.5,
        )
        ax.axis("on")
        ax.set_xticks([])
        ax.set_yticks([])
    fig.suptitle(
        "Sentinel-2 truth points (true colour): water (cyan) & dry (yellow) "
        "examples\nmask flags  R=RF  T=Tier-A  G=GFM-union",
        fontsize=10,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=125, bbox_inches="tight")
    plt.close(fig)
    print(f"[s2] wrote {path} ({path.stat().st_size / 1024:.0f} KB)", flush=True)


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def run():
    t0 = time.time()
    rng = np.random.default_rng(SEED)
    client = open_client()

    print("[s2] calibrating NDWI thresholds on Harike ...", flush=True)
    calib = calibration_record(client)
    print(json.dumps(calib, indent=2), flush=True)

    M = load_masks_and_grid()
    idx, strat = build_candidates(M, rng)
    xs, ys = xy_of(idx, M["transform"], M["width"])
    import collections

    print(f"[s2] {len(idx)} candidates; strata "
          f"{dict(collections.Counter(strat.tolist()))}", flush=True)

    out_ndwi, out_scl, out_date, provenance = sample_points_s2(client, xs, ys)

    s2code = classify_water(
        out_ndwi, np.where(np.isfinite(out_scl), out_scl, 0),
        t_water=T_WATER, t_dry=T_DRY,
    )
    class_name = np.where(s2code == WATER, "water",
                          np.where(s2code == DRY, "dry", "uncertain"))

    dvals = M["districts"].ravel()[idx]
    districts = np.array([M["dnames"][d - 1] if d > 0 else "" for d in dvals])

    df_all = pd.DataFrame({
        "x": np.round(xs, 1),
        "y": np.round(ys, 1),
        "date_s2": out_date,
        "ndwi": np.round(out_ndwi, 4),
        "s2_class": class_name,
        "rf": M["rf"].ravel()[idx].astype(int),
        "tierA": M["tierA"].ravel()[idx].astype(int),
        "gfm": M["gfm"].ravel()[idx].astype(int),
        "stratum": strat,
        "district": districts,
    })
    n_uncertain = int((df_all["s2_class"] == "uncertain").sum())
    n_nocover = int((df_all["date_s2"] == "").sum())
    df = df_all[df_all["s2_class"] != "uncertain"].reset_index(drop=True)

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    df[["x", "y", "date_s2", "ndwi", "s2_class", "rf", "tierA", "gfm",
        "stratum", "district"]].to_csv(OUT_CSV, index=False)
    print(f"[s2] wrote {OUT_CSV}: {len(df)} classified "
          f"({int((df.s2_class == 'water').sum())} water / "
          f"{int((df.s2_class == 'dry').sum())} dry); dropped {n_uncertain} "
          f"uncertain ({n_nocover} no clean optical)", flush=True)

    scores = score_masks(df)
    make_quicklook(client, df, CHECKS_DIR / "s2_truth_examples.png")

    results = {
        "search_bbox_ll": SEARCH_BBOX_LL,
        "named_districts": list(NAMED_DISTRICTS),
        "res_m": RES,
        "dates": DATES,
        "scene_provenance": provenance,
        "calibration": calib,
        "n_candidates": int(len(idx)),
        "points_by_date": {d: int((df["date_s2"] == d).sum()) for d in DATES},
        "n_uncertain_dropped": n_uncertain,
        "n_no_clean_optical": n_nocover,
        "class_counts": {
            "water": int((df.s2_class == "water").sum()),
            "dry": int((df.s2_class == "dry").sum()),
        },
        "stratum_counts": {t: int((df.stratum == t).sum()) for t in sorted(set(strat))},
        "district_counts": dict(collections.Counter(df["district"].tolist())),
        "scores": scores,
        "runtime_s": round(time.time() - t0, 1),
    }
    print("=== s2_truth RESULTS ===", flush=True)
    print(json.dumps(results, indent=2, default=str), flush=True)
    scratch = Path(
        "C:/Users/rudra/AppData/Local/Temp/claude/"
        "C--Users-rudra-OneDrive-Desktop-d/720623cf-3d92-4140-9645-d2526c85c313/scratchpad"
    )
    scratch.mkdir(parents=True, exist_ok=True)
    with open(scratch / "s2_results.json", "w") as fh:
        json.dump(results, fh, indent=2, default=str)
    return results


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.parse_args()
    run()


if __name__ == "__main__":
    main()
