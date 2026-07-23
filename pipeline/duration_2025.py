# pipeline/duration_2025.py
"""2025 submergence-DURATION atlas: how many days each ~100 m pixel stayed
underwater in the Aug 15 - Sep 30 2025 Punjab flood event.

Reads the per-day GFM flood masks in ``data/gfm/2025/`` (binary 0/1 uint8,
EPSG:3857 ~100 m), keeps only the event-window passes (>= Aug 15, dropping the
Jun/Jul paddy-transplant signal), subtracts reference water, and computes two
bracketing per-pixel censored-duration estimators from ``sailaab.duration``:

    days_observed_wet  (LOWER, committed raster)   span_duration (UPPER, bracket)

Products (all pure logic in ``sailaab.duration``; IO/rasterio/matplotlib here):

    data/rasters/duration_2025.tif        LOWER duration, uint8 days   (gitignored)
    data/rasters/duration_span_2025.tif   UPPER duration, uint8 days   (gitignored)
    atlas/duration_2025.png               dark cyan house-style map + legend
    data/duration_districts_2025.csv      per-district ha/class + mean duration
    data/duration_tehsils_2025.csv        per-tehsil  ha/class + mean duration
    data/duration_crop_damage_2025.csv    cropland ha/class + agronomic damage est.

Run (defaults are repo-relative; point --gfm-dir etc. at wherever the gitignored
rasters actually live):

    python -m pipeline.duration_2025 compute
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.warp import reproject, transform_geom

from sailaab.duration import (
    day_offsets,
    filter_window,
    days_observed_wet,
    span_duration,
    duration_classes,
    DURATION_CLASS_LABELS,
)
from sailaab.districts import load_districts, rasterize_districts
from sailaab.tehsils import load_tehsils
from sailaab.stats import crop_value_at_risk
from sailaab.gfm import web_mercator_area_km2
from sailaab import figstyle
from pipeline.fetch_gfm import bbox_3857, grid_shape, write_mask_tif

REPO = Path(__file__).resolve().parents[1]
EVENT_START = "2025-08-15"  # event clock: paddy Jun/Jul excluded
EVENT_END = "2025-09-30"
MAX_BRIDGE = 4  # wet-bridge cap (days) = max real observation gap in the window

# Agronomic paddy yield-loss fractions per duration class (1-2, 3-6, 7-13, 14+ d).
# Conservative bands from IRRI submergence agronomy (Setter & Laureles 1996;
# Sarkar et al. 2006; Ismail et al. 2013), labelled ESTIMATE. See duration.md.
LOSS_FRACTION = {1: 0.10, 2: 0.35, 3: 0.70, 4: 1.00}

DEFAULT_GFM_DIR = REPO / "data" / "gfm" / "2025"
DEFAULT_REFWATER = REPO / "data" / "gfm" / "gfm_punjab_refwater.tif"
DEFAULT_CROPLAND = REPO / "data" / "rasters" / "rf_cropland.tif"

RASTER_DIR = REPO / "data" / "rasters"
DURATION_TIF = RASTER_DIR / "duration_2025.tif"
SPAN_TIF = RASTER_DIR / "duration_span_2025.tif"
ATLAS_PNG = REPO / "atlas" / "duration_2025.png"
DISTRICTS_CSV = REPO / "data" / "duration_districts_2025.csv"
TEHSILS_CSV = REPO / "data" / "duration_tehsils_2025.csv"
CROP_CSV = REPO / "data" / "duration_crop_damage_2025.csv"

# site cyan single-hue ramp (docs/index.html now/flood layers), classes 1-4
RAMP = ["#155a5c", "#1f8a84", "#35b5a9", "#63e6d5"]
INK = "#0a1014"
INK2 = "#0e161d"
LINE2 = "#28394a"
PAPER = "#e9e4d6"
PAPER_DIM = "#9aa5a4"
PAPER_FAINT = "#5c6a70"


# --------------------------------------------------------------------------- #
# grid helpers (cos^2-lat pixel area, same physics as sailaab.gfm)
# --------------------------------------------------------------------------- #
def _row_ha(bounds, nrows, ncols):
    minx, miny, maxx, maxy = bounds
    px = (maxx - minx) / ncols
    py = (maxy - miny) / nrows
    r = 6378137.0
    y_center = maxy - (np.arange(nrows) + 0.5) * py
    lat = 2.0 * np.arctan(np.exp(y_center / r)) - np.pi / 2.0
    return (px * py * np.cos(lat) ** 2) / 1.0e4  # m^2 -> ha


def _rasterize_units(geom_name_pairs, bounds, nrows, ncols):
    """Reproject 4326 geoms to 3857 and burn label i+1 in list order."""
    from rasterio.transform import from_bounds

    minx, miny, maxx, maxy = bounds
    transform = from_bounds(minx, miny, maxx, maxy, ncols, nrows)
    geoms = [transform_geom("EPSG:4326", "EPSG:3857", g) for _, g in geom_name_pairs]
    labels = rasterize_districts(geoms, transform, (nrows, ncols))
    return labels


def _read_mask(path, refwater):
    with rasterio.open(path) as ds:
        return (ds.read(1) > 0) & ~refwater


# --------------------------------------------------------------------------- #
# duration compute (streamed: never holds the full 24-day stack in memory)
# --------------------------------------------------------------------------- #
def compute_duration(gfm_dir, refwater, bounds, nrows, ncols):
    tifs = sorted(Path(gfm_dir).glob("gfm_punjab_*.tif"))
    day8 = [t.stem.split("_")[-1] for t in tifs]
    isos = [f"{d[:4]}-{d[4:6]}-{d[6:8]}" for d in day8]
    keep = filter_window(isos, EVENT_START, EVENT_END)
    tifs = [tifs[i] for i in keep]
    isos = [isos[i] for i in keep]
    dn = day_offsets(isos, EVENT_START)
    if not tifs:
        raise SystemExit(f"no event-window tifs found in {gfm_dir}")
    print(f"event window {EVENT_START}..{EVENT_END}: {len(tifs)} obs days")
    print(f"  first={isos[0]} last={isos[-1]} day-numbers {dn.min()}..{dn.max()}")
    gaps = np.diff(dn)
    print(
        f"  gaps {sorted(set(gaps.tolist()))} (max {int(gaps.max())}), bridge<= {MAX_BRIDGE}"
    )

    base = np.zeros((nrows, ncols), np.uint16)  # count of wet passes
    bridge = np.zeros((nrows, ncols), np.uint16)  # bridged in-between days
    hi = int(dn.max()) + 1
    first = np.full((nrows, ncols), hi, np.int16)
    last = np.full((nrows, ncols), -1, np.int16)

    prev = None
    for i, tif in enumerate(tifs):
        cur = _read_mask(tif, refwater)
        base += cur
        d = int(dn[i])
        first = np.where(cur & (first == hi), d, first).astype(np.int16)
        last = np.where(cur, d, last).astype(np.int16)
        if prev is not None:
            g = int(dn[i] - dn[i - 1])
            if g <= MAX_BRIDGE and g > 1:
                bridge += (g - 1) * (prev & cur).astype(np.uint16)
        prev = cur

    dow = (base + bridge).astype(np.uint8)
    any_wet = last >= 0
    span = np.where(any_wet, last.astype(np.int32) - first.astype(np.int32) + 1, 0)
    span = span.astype(np.uint8)

    # sanity: closed-form pure-module math on a random pixel subset must match
    _crosscheck(tifs, refwater, dn, dow, span)
    return dow, span, isos, dn


def _crosscheck(tifs, refwater, dn, dow, span, n=6):
    """Verify the streamed rasters equal the tested pure functions on n pixels."""
    rng = np.random.default_rng(0)
    with rasterio.open(tifs[0]) as ds0:
        h, w = ds0.read(1).shape
    ys = rng.integers(0, h, n)
    xs = rng.integers(0, w, n)
    stack = np.zeros((len(tifs), n), bool)
    for i, tif in enumerate(tifs):
        with rasterio.open(tif) as ds:
            a = ds.read(1) > 0
        stack[i] = a[ys, xs] & ~refwater[ys, xs]
    exp_dow = days_observed_wet(dn, stack, MAX_BRIDGE)
    exp_span = span_duration(dn, stack)
    got_dow = dow[ys, xs].astype(np.int64)
    got_span = span[ys, xs].astype(np.int64)
    assert np.array_equal(exp_dow, got_dow), (exp_dow, got_dow)
    assert np.array_equal(exp_span, got_span), (exp_span, got_span)
    print(f"  cross-check OK: streamed rasters == sailaab.duration on {n} pixels")


# --------------------------------------------------------------------------- #
# cropland warp onto the GFM grid
# --------------------------------------------------------------------------- #
def warp_cropland(cropland_path, bounds, nrows, ncols):
    from rasterio.transform import from_bounds

    minx, miny, maxx, maxy = bounds
    dst_transform = from_bounds(minx, miny, maxx, maxy, ncols, nrows)
    dst = np.zeros((nrows, ncols), np.uint8)
    with rasterio.open(cropland_path) as src:
        reproject(
            source=src.read(1),
            destination=dst,
            src_transform=src.transform,
            src_crs=src.crs,
            dst_transform=dst_transform,
            dst_crs="EPSG:3857",
            resampling=Resampling.nearest,
            src_nodata=src.nodata,
            dst_nodata=0,
        )
    return dst > 0


# --------------------------------------------------------------------------- #
# zonal statistics
# --------------------------------------------------------------------------- #
def zonal(dow, cls, labels, row_ha, n_units, extra_mask=None):
    """Per-unit hectares in each duration class + flooded ha / mean / max duration.

    ``extra_mask`` (e.g. cropland) restricts every tally when given. Returns a
    dict label(1..n) -> {ha1,ha2,ha3,ha4, flooded_ha, mean_dur, max_dur}.
    """
    W = np.broadcast_to(row_ha[:, None], dow.shape)
    valid = labels > 0
    if extra_mask is not None:
        valid = valid & extra_mask

    ha_by_class = {}
    for c in (1, 2, 3, 4):
        sel = valid & (cls == c)
        ha_by_class[c] = np.bincount(labels[sel], weights=W[sel], minlength=n_units + 1)

    flooded = valid & (dow > 0)
    flooded_ha = np.bincount(labels[flooded], weights=W[flooded], minlength=n_units + 1)
    sum_dur = np.bincount(
        labels[flooded], weights=dow[flooded].astype(float), minlength=n_units + 1
    )
    cnt = np.bincount(labels[flooded], minlength=n_units + 1).astype(float)
    mean_dur = np.divide(sum_dur, cnt, out=np.zeros_like(sum_dur), where=cnt > 0)
    max_dur = np.zeros(n_units + 1, np.int64)
    np.maximum.at(max_dur, labels[flooded], dow[flooded].astype(np.int64))

    out = {}
    for li in range(1, n_units + 1):
        out[li] = {
            "ha1": float(ha_by_class[1][li]),
            "ha2": float(ha_by_class[2][li]),
            "ha3": float(ha_by_class[3][li]),
            "ha4": float(ha_by_class[4][li]),
            "flooded_ha": float(flooded_ha[li]),
            "mean_dur": float(mean_dur[li]),
            "max_dur": int(max_dur[li]),
        }
    return out


def _write_unit_csv(path, rows, unit_cols):
    cols = unit_cols + [
        "flooded_ha",
        "ha_1_2d",
        "ha_3_6d",
        "ha_7_13d",
        "ha_14plus_d",
        "mean_duration_days",
        "max_duration_days",
    ]
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {path} ({len(rows)} rows)")


# --------------------------------------------------------------------------- #
# dark house-style atlas PNG
# --------------------------------------------------------------------------- #
def _maxpool(a, factor):
    nr, nc = a.shape
    ph, pw = (-nr) % factor, (-nc) % factor
    if ph or pw:
        a = np.pad(a, ((0, ph), (0, pw)), constant_values=0)
    h, w = a.shape
    return a.reshape(h // factor, factor, w // factor, factor).max(axis=(1, 3))


def _rel_lum(hexc):
    r, g, b = (int(hexc[i : i + 2], 16) / 255 for i in (1, 3, 5))
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def render_png(cls, labels, bounds, max_width=1400):
    # dataviz nod: the reused single-hue ramp must be luminance-monotonic on dark
    lums = [_rel_lum(c) for c in RAMP]
    assert all(a < b for a, b in zip(lums, lums[1:])), f"ramp not monotone: {lums}"

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import BoundaryNorm, ListedColormap
    from matplotlib.patches import Patch

    figstyle.apply()

    factor = max(1, int(np.ceil(cls.shape[1] / max_width)))
    c = _maxpool(cls.astype(np.int32), factor)
    lab = _maxpool(labels.astype(np.int32), factor)
    edges = np.zeros_like(lab, bool)
    edges[:, 1:] |= lab[:, 1:] != lab[:, :-1]
    edges[1:, :] |= lab[1:, :] != lab[:-1, :]

    colors = [INK] + RAMP  # class 0 = dark surface
    cmap = ListedColormap(colors)
    norm = BoundaryNorm(range(len(colors) + 1), cmap.N)

    minx, miny, maxx, maxy = bounds
    fig, ax = plt.subplots(figsize=(9.5, 9.0), dpi=130)
    fig.patch.set_facecolor(INK)
    ax.set_facecolor(INK)
    ax.imshow(
        c,
        cmap=cmap,
        norm=norm,
        extent=(minx, maxx, miny, maxy),
        interpolation="nearest",
    )
    ys, xs = np.where(edges)
    if len(xs):
        ex = minx + (xs + 0.5) * (maxx - minx) / edges.shape[1]
        ey = maxy - (ys + 0.5) * (maxy - miny) / edges.shape[0]
        ax.scatter(ex, ey, s=0.12, c=PAPER_FAINT, marker=".", linewidths=0)

    ax.set_title(
        figstyle.clean(
            "Punjab 2025 flood: submergence duration (Aug 15–Sep 30)\n"
            "days a pixel stayed underwater: Copernicus GFM ~100 m, "
            "wet-bridge <=4 d, permanent water removed"
        ),
        fontsize=11,
        color=PAPER,
    )
    ax.set_xlabel("EPSG:3857 easting (m)", color=PAPER_DIM, fontsize=8)
    ax.set_ylabel("EPSG:3857 northing (m)", color=PAPER_DIM, fontsize=8)
    ax.tick_params(colors=PAPER_FAINT, labelsize=7, labelfontfamily=figstyle.FONT_MONO)
    for sp in ax.spines.values():
        sp.set_color(LINE2)

    leg = ax.legend(
        handles=[
            Patch(facecolor=col, edgecolor=LINE2, label=f"{lab} days")
            for col, lab in zip(RAMP, DURATION_CLASS_LABELS)
        ],
        title="days underwater",
        loc="upper right",
        fontsize=8,
        title_fontsize=9,
        framealpha=0.95,
        facecolor=INK2,
        edgecolor=LINE2,
        labelcolor=PAPER,
    )
    leg.get_title().set_color(PAPER)

    ATLAS_PNG.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(
        ATLAS_PNG,
        facecolor=INK,
        bbox_inches="tight",
        pil_kwargs={"optimize": True},
    )
    plt.close(fig)
    return ATLAS_PNG.stat().st_size


# --------------------------------------------------------------------------- #
def compute():
    bounds = bbox_3857()
    ncols, nrows = grid_shape(bounds)
    args = compute.args
    print(f"grid {ncols} x {nrows} px EPSG:3857")

    with rasterio.open(args.refwater) as ds:
        refwater = ds.read(1) > 0
    if refwater.shape != (nrows, ncols):
        raise SystemExit(f"refwater shape {refwater.shape} != {(nrows, ncols)}")

    dow, span, isos, dn = compute_duration(args.gfm_dir, refwater, bounds, nrows, ncols)
    cls = duration_classes(dow)

    RASTER_DIR.mkdir(parents=True, exist_ok=True)
    write_mask_tif(DURATION_TIF, dow, bounds)
    write_mask_tif(SPAN_TIF, span, bounds)
    print(f"wrote {DURATION_TIF} / {SPAN_TIF.name}")

    row_ha = _row_ha(bounds, nrows, ncols)

    # districts
    dpairs = load_districts(canonicalize=True)  # (name, geom) sorted
    dnames = [n for n, _ in dpairs]
    dlabels = _rasterize_units(dpairs, bounds, nrows, ncols)
    dstats = zonal(dow, cls, dlabels, row_ha, len(dnames))

    # tehsils
    tlist = load_tehsils()  # (tehsil, district, geom) sorted
    tpairs = [(f"{t}|{d}", g) for t, d, g in tlist]
    tlabels = _rasterize_units(tpairs, bounds, nrows, ncols)
    tstats = zonal(dow, cls, tlabels, row_ha, len(tlist))

    # cropland (warped onto GFM grid)
    cropland = warp_cropland(args.cropland, bounds, nrows, ncols)
    cstats = zonal(dow, cls, dlabels, row_ha, len(dnames), extra_mask=cropland)

    _write_csvs(dnames, dstats, tlist, tstats, cstats)
    size = render_png(cls, dlabels, bounds)
    print(f"wrote {ATLAS_PNG} ({size / 1024:.0f} KB)")

    _report(
        dow,
        span,
        cls,
        row_ha,
        dlabels,
        dnames,
        dstats,
        tlist,
        tstats,
        cstats,
        cropland,
        bounds,
        isos,
        dn,
    )


def _write_csvs(dnames, dstats, tlist, tstats, cstats):
    drows = []
    for li, name in enumerate(dnames, start=1):
        s = dstats[li]
        drows.append(_unit_row({"district": name}, s))
    drows.sort(key=lambda r: -r["flooded_ha"])
    _write_unit_csv(DISTRICTS_CSV, drows, ["district"])

    trows = []
    for li, (teh, dist, _) in enumerate(tlist, start=1):
        s = tstats[li]
        trows.append(_unit_row({"tehsil": teh, "district": dist}, s))
    trows.sort(key=lambda r: -r["flooded_ha"])
    _write_unit_csv(TEHSILS_CSV, trows, ["tehsil", "district"])

    _write_crop_csv(dnames, cstats)


def _unit_row(head, s):
    return {
        **head,
        "flooded_ha": round(s["flooded_ha"], 1),
        "ha_1_2d": round(s["ha1"], 1),
        "ha_3_6d": round(s["ha2"], 1),
        "ha_7_13d": round(s["ha3"], 1),
        "ha_14plus_d": round(s["ha4"], 1),
        "mean_duration_days": round(s["mean_dur"], 2),
        "max_duration_days": s["max_dur"],
    }


def _write_crop_csv(dnames, cstats):
    value_per_ha = crop_value_at_risk(1.0)  # 6.5 t/ha * Rs 23,200/t = Rs 150,800
    rows = []
    for li, name in enumerate(dnames, start=1):
        s = cstats[li]
        crop_flooded = s["ha1"] + s["ha2"] + s["ha3"] + s["ha4"]
        weighted = value_per_ha * (
            s["ha1"] * LOSS_FRACTION[1]
            + s["ha2"] * LOSS_FRACTION[2]
            + s["ha3"] * LOSS_FRACTION[3]
            + s["ha4"] * LOSS_FRACTION[4]
        )
        naive = value_per_ha * crop_flooded
        rows.append(
            {
                "district": name,
                "crop_flooded_ha": round(crop_flooded, 1),
                "crop_ha_1_2d": round(s["ha1"], 1),
                "crop_ha_3_6d": round(s["ha2"], 1),
                "crop_ha_7_13d": round(s["ha3"], 1),
                "crop_ha_14plus_d": round(s["ha4"], 1),
                "damage_weighted_inr": round(weighted),
                "naive_value_inr": round(naive),
                "damage_fraction": round(weighted / naive, 3) if naive > 0 else 0.0,
            }
        )
    rows.sort(key=lambda r: -r["crop_flooded_ha"])
    cols = [
        "district",
        "crop_flooded_ha",
        "crop_ha_1_2d",
        "crop_ha_3_6d",
        "crop_ha_7_13d",
        "crop_ha_14plus_d",
        "damage_weighted_inr",
        "naive_value_inr",
        "damage_fraction",
    ]
    with open(CROP_CSV, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {CROP_CSV} ({len(rows)} rows)")


def _report(
    dow,
    span,
    cls,
    row_ha,
    dlabels,
    dnames,
    dstats,
    tlist,
    tstats,
    cstats,
    cropland,
    bounds,
    isos,
    dn,
):
    W = np.broadcast_to(row_ha[:, None], dow.shape)
    flooded = dow > 0
    total_flooded_ha = float(W[flooded].sum())
    ge7_ha = float(W[(cls >= 3)].sum())  # classes 3,4 = >=7 days
    union_km2 = web_mercator_area_km2(flooded, bounds)
    med_core = float(np.median(dow[flooded])) if flooded.any() else 0.0
    med_span = float(np.median(span[span > 0])) if (span > 0).any() else 0.0

    print("\n================ 2025 DURATION SUMMARY ================")
    print(f"event obs days           : {len(isos)}  ({isos[0]}..{isos[-1]})")
    print(
        f"flooded footprint (>=1 d): {total_flooded_ha:,.0f} ha = {union_km2:,.1f} km2"
    )
    print(
        f"days_observed_wet (LOWER): max {int(dow.max())} d, median(flooded) {med_core:.0f} d"
    )
    print(
        f"span_duration     (UPPER): max {int(span.max())} d, median(flooded) {med_span:.0f} d"
    )
    print(f"area >= 7 days (cls 3-4) : {ge7_ha:,.0f} ha")
    frac_ge7 = ge7_ha / total_flooded_ha if total_flooded_ha else 0.0
    print(f"severe fraction >=7d/>=1d: {frac_ge7:.3f}")
    bracket_ok = bool(np.all(dow <= span))
    print(f"bracket dow<=span 100%   : {bracket_ok}")

    # top-5 tehsils by mean duration (>= 50 ha flooded to be meaningful)
    ranked = sorted(
        [
            (
                tstats[li]["mean_dur"],
                tstats[li]["flooded_ha"],
                teh,
                dist,
                tstats[li]["max_dur"],
            )
            for li, (teh, dist, _) in enumerate(tlist, start=1)
            if tstats[li]["flooded_ha"] >= 50.0
        ],
        key=lambda r: -r[0],
    )[:5]
    print("\ntop-5 tehsils by mean flooded-duration (>=50 ha flooded):")
    for mean_d, fl_ha, teh, dist, mx in ranked:
        print(
            f"  {teh:22s} {dist:14s} mean {mean_d:5.1f} d  max {mx:2d} d  flooded {fl_ha:8.0f} ha"
        )

    print("\ntop-8 districts by flooded ha:")
    for r in sorted(dstats.values(), key=lambda s: -s["flooded_ha"])[:8]:
        li = [k for k, v in dstats.items() if v is r][0]
        print(
            f"  {dnames[li - 1]:14s} flooded {r['flooded_ha']:8.0f} ha  "
            f">=7d {r['ha3'] + r['ha4']:7.0f} ha  mean {r['mean_dur']:4.1f} d  max {r['max_dur']:2d} d"
        )

    # crop damage totals
    value_per_ha = crop_value_at_risk(1.0)
    tot_crop = sum(
        cstats[li]["ha1"] + cstats[li]["ha2"] + cstats[li]["ha3"] + cstats[li]["ha4"]
        for li in range(1, len(dnames) + 1)
    )
    tot_weighted = value_per_ha * sum(
        cstats[li]["ha1"] * LOSS_FRACTION[1]
        + cstats[li]["ha2"] * LOSS_FRACTION[2]
        + cstats[li]["ha3"] * LOSS_FRACTION[3]
        + cstats[li]["ha4"] * LOSS_FRACTION[4]
        for li in range(1, len(dnames) + 1)
    )
    tot_naive = value_per_ha * tot_crop
    print(f"\ncropland flooded (>=1 d) : {tot_crop:,.0f} ha")
    print(f"naive value (all*full)   : Rs {tot_naive / 1e7:,.1f} crore")
    print(
        f"duration-weighted damage : Rs {tot_weighted / 1e7:,.1f} crore  "
        f"(fraction {tot_weighted / tot_naive:.3f})"
        if tot_naive
        else ""
    )
    print("=======================================================")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    pc = sub.add_parser("compute", help="build all 2025 duration products")
    pc.add_argument("--gfm-dir", default=str(DEFAULT_GFM_DIR))
    pc.add_argument("--refwater", default=str(DEFAULT_REFWATER))
    pc.add_argument("--cropland", default=str(DEFAULT_CROPLAND))
    args = ap.parse_args()
    if args.cmd == "compute":
        compute.args = args
        compute()


if __name__ == "__main__":
    main()
