#!/usr/bin/env python
"""Tehsil-level flood products from the on-disk decade GFM tifs + the 2025 RF mask.

Takes the district analysis down to **tehsil (ADM3 sub-district)** resolution,
reusing every piece of tested machinery: the tehsil polygons +
:mod:`sailaab.tehsils`, :func:`sailaab.districts.rasterize_districts` /
``district_fractions``, the decade per-row cos^2-lat area helpers in
:mod:`pipeline.fetch_gfm_decade`, :func:`sailaab.frequency.summarize_repeat_victims`,
and :func:`sailaab.stats.crop_value_at_risk`. No WMS pulls -- it only reads tifs
already on disk.

Two products, on the two canonical grids the tifs already live on:

* **decade repeat-victims** (GFM, ~100 m EPSG:3857): per-season *late-season*
  (>= Jul 25, past paddy transplant -- the calibrated convention of
  ``docs/notes/gfm-decade.md``) flood unions minus reference water, reduced to
  per-tehsil flooded fraction per season ->
  ``data/tehsil_season_fractions.csv`` + the headline
  ``data/tehsil_repeat_victims.csv`` + ``atlas/tehsil_repeat_victims.png``;
* **2025 impact** (RF, 90 m EPSG:32643): the committed ``rf_flood_2025.tif`` mask
  and ``rf_cropland.tif`` (ESA WorldCover class 40) reduced to per-tehsil flooded
  ha, crop-flooded ha, and paddy value-at-risk -> ``data/tehsil_flood_stats_2025.csv``.

Input dirs default to the repo layout but can point elsewhere (the per-day tifs
and RF rasters are gitignored, so a fresh checkout supplies them via ``--gfm-dir``
/ ``--raster-dir``).

Usage:
    python -m pipeline.tehsil_stats [--gfm-dir data/gfm] [--raster-dir data/rasters]
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_bounds
from rasterio.warp import transform_geom

from sailaab import config
from sailaab import figstyle
from sailaab.districts import district_fractions, load_districts, rasterize_districts
from sailaab.frequency import summarize_repeat_victims
from sailaab.stats import crop_value_at_risk
from sailaab.tehsils import load_tehsils
from pipeline.fetch_gfm import bbox_3857, grid_shape
from pipeline.fetch_gfm_decade import (
    LATE_SEASON_MD,
    _district_ha_from_mask,
    _read_mask,
    _row_ha,
)

SEASON_FRACTIONS_CSV = Path("data/tehsil_season_fractions.csv")
REPEAT_VICTIMS_CSV = Path("data/tehsil_repeat_victims.csv")
STATS_2025_CSV = Path("data/tehsil_flood_stats_2025.csv")
ATLAS_PNG = Path("atlas/tehsil_repeat_victims.png")


# --------------------------------------------------------------------------- #
# shared: tehsil label raster on an arbitrary grid (reprojected from 4326)
# --------------------------------------------------------------------------- #
def _tehsil_labels(transform, shape, dst_crs):
    """Rasterize the committed tehsils onto a grid. Returns (labels, names, ts)
    where ``ts`` is the sorted (tehsil, district, geom_4326) list and ``names``
    the tehsil column (label i+1 -> names[i])."""
    ts = load_tehsils()
    names = [t for t, _, _ in ts]
    geoms = [transform_geom("EPSG:4326", dst_crs, g) for _, _, g in ts]
    labels = rasterize_districts(geoms, transform, shape)
    return labels, names, ts


# --------------------------------------------------------------------------- #
# decade late-season repeat-victims (GFM 100 m EPSG:3857)
# --------------------------------------------------------------------------- #
def decade_repeat_victims(gfm_dir: Path):
    bounds = bbox_3857()
    ncols, nrows = grid_shape(bounds)
    transform = from_bounds(*bounds, ncols, nrows)

    refwater = _read_mask(gfm_dir / "gfm_punjab_refwater.tif")
    if refwater.shape != (nrows, ncols):
        raise SystemExit(f"refwater shape {refwater.shape} != grid {(nrows, ncols)}")

    labels, names, ts = _tehsil_labels(transform, (nrows, ncols), "EPSG:3857")
    tehsil_of = {t: d for t, d, _ in ts}
    n = len(names)
    row_ha = _row_ha(bounds, nrows, ncols)
    tehsil_ha = _district_ha_from_mask(np.ones((nrows, ncols), bool), labels, row_ha, n)

    per_season = {name: [] for name in names}
    season_rows = []
    for year in config.YEARS:
        cutoff = f"{year}{LATE_SEASON_MD.replace('-', '')}"  # YYYYMMDD >= Jul 25
        year_dir = gfm_dir / str(year)
        u = np.zeros((nrows, ncols), bool)
        if year_dir.exists():
            for tif in sorted(year_dir.glob("gfm_punjab_*.tif")):
                if tif.stem.split("_")[-1] >= cutoff:
                    u |= _read_mask(tif)
        u &= ~refwater
        ha = _district_ha_from_mask(u, labels, row_ha, n)
        for li, name in enumerate(names, start=1):
            d_ha = tehsil_ha[li]
            f_ha = float(ha[li])
            frac = (f_ha / d_ha) if d_ha > 0 else 0.0
            per_season[name].append({"flooded_ha": f_ha, "fraction": frac})
            season_rows.append(
                {
                    "tehsil": name,
                    "district": tehsil_of[name],
                    "year": year,
                    "flooded_ha": round(f_ha, 2),
                    "fraction": round(frac, 6),
                }
            )

    _write_csv(
        SEASON_FRACTIONS_CSV,
        ["tehsil", "district", "year", "flooded_ha", "fraction"],
        season_rows,
    )
    print(f"wrote {SEASON_FRACTIONS_CSV} ({len(season_rows)} rows)")

    summary = summarize_repeat_victims(per_season)
    rows = [
        {
            "tehsil": name,
            "district": tehsil_of[name],
            "seasons_gt1pct": summary[name]["seasons_with_fraction_gt1pct"],
            "seasons_gt2pct": summary[name]["seasons_with_fraction_gt2pct"],
            "max_season_fraction": round(summary[name]["max_season_fraction"], 6),
            "mean_annual_flooded_ha": round(summary[name]["mean_annual_flooded_ha"], 2),
        }
        for name in names
    ]
    rows.sort(
        key=lambda r: (
            -r["seasons_gt1pct"],
            -r["seasons_gt2pct"],
            -r["mean_annual_flooded_ha"],
        )
    )
    _write_csv(
        REPEAT_VICTIMS_CSV,
        [
            "tehsil",
            "district",
            "seasons_gt1pct",
            "seasons_gt2pct",
            "max_season_fraction",
            "mean_annual_flooded_ha",
        ],
        rows,
    )
    print(f"wrote {REPEAT_VICTIMS_CSV} ({len(rows)} tehsils)")
    return rows, ts, summary


# --------------------------------------------------------------------------- #
# 2025 impact (RF 90 m EPSG:32643) + crop value-at-risk
# --------------------------------------------------------------------------- #
def impact_2025(raster_dir: Path):
    flood_tif = raster_dir / "rf_flood_2025.tif"
    with rasterio.open(flood_tif) as ds:
        transform = ds.transform
        shape = ds.shape
        dst_crs = ds.crs.to_string()
        rf = ds.read(1) > 0
    px_area_ha = abs(transform.a * transform.e) / 1e4  # 90 m -> 0.81 ha

    crop_path = raster_dir / "rf_cropland.tif"
    have_crop = crop_path.exists()
    cropland = (
        (rasterio.open(crop_path).read(1) > 0) if have_crop else np.zeros(shape, bool)
    )

    labels, names, ts = _tehsil_labels(transform, shape, dst_crs)
    tehsil_of = {t: d for t, d, _ in ts}

    rf_d = district_fractions(labels, rf, px_area_ha, names=names)
    crop_d = district_fractions(labels, rf & cropland, px_area_ha, names=names)

    rows = []
    for name in names:
        crop_ha = round(crop_d[name]["flooded_ha"], 1) if have_crop else ""
        rows.append(
            {
                "tehsil": name,
                "district": tehsil_of[name],
                "rf_flooded_ha": round(rf_d[name]["flooded_ha"], 1),
                "crop_flooded_ha": crop_ha,
                "fraction": round(rf_d[name]["flooded_fraction"], 5),
                "crop_var_inr": (
                    round(crop_value_at_risk(crop_d[name]["flooded_ha"]), 1)
                    if have_crop
                    else ""
                ),
            }
        )
    rows.sort(key=lambda r: -r["rf_flooded_ha"])
    _write_csv(
        STATS_2025_CSV,
        [
            "tehsil",
            "district",
            "rf_flooded_ha",
            "crop_flooded_ha",
            "fraction",
            "crop_var_inr",
        ],
        rows,
    )
    print(
        f"wrote {STATS_2025_CSV} ({len(rows)} tehsils; "
        f"crop={'yes' if have_crop else 'MISSING -> skipped'})"
    )
    return rows, have_crop


# --------------------------------------------------------------------------- #
# atlas figure: dark ink + amber ramp, tehsils by seasons-flooded, top-10 named
# --------------------------------------------------------------------------- #
def render_atlas(repeat_rows, ts, out_path=ATLAS_PNG):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.collections import PatchCollection
    from matplotlib.colors import LinearSegmentedColormap
    from matplotlib.patches import PathPatch
    from matplotlib.path import Path as MplPath
    from shapely.geometry import shape

    figstyle.apply()
    ink = "#0a1014"
    seasons = {r["tehsil"]: r["seasons_gt1pct"] for r in repeat_rows}
    vmax = max(seasons.values()) or 1
    # amber sequential ramp; 0 (never flooded) recedes to a muted near-ink tone
    amber = LinearSegmentedColormap.from_list(
        "amber", ["#3a2a12", "#a8641b", "#e3922a", "#ffbd45", "#ffe08a"]
    )

    def patches(geom):
        out = []
        polys = geom.geoms if geom.geom_type == "MultiPolygon" else [geom]
        for poly in polys:
            verts, codes = [], []
            for ring in [poly.exterior, *poly.interiors]:
                xy = np.asarray(ring.coords)
                verts.extend(xy)
                codes.append(MplPath.MOVETO)
                codes.extend([MplPath.LINETO] * (len(xy) - 2))
                codes.append(MplPath.CLOSEPOLY)
            out.append(PathPatch(MplPath(verts, codes)))
        return out

    lats = []
    all_patches, face = [], []
    for tehsil, _, geom_dict in ts:
        geom = shape(geom_dict)
        lats.append(geom.centroid.y)
        n = seasons.get(tehsil, 0)
        color = ink if n == 0 else amber(0.15 + 0.85 * (n / vmax))
        # even never-flooded tehsils get a faint fill so the state reads as filled
        color = "#14110c" if n == 0 else color
        for p in patches(geom):
            all_patches.append(p)
            face.append(color)

    fig, ax = plt.subplots(figsize=(8.2, 9.0), dpi=150)
    fig.patch.set_facecolor(ink)
    ax.set_facecolor(ink)
    ax.add_collection(
        PatchCollection(
            all_patches, facecolors=face, edgecolors="#0a1014", linewidths=0.35
        )
    )

    # top-10 by seasons-flooded (tie-break mean annual ha) -> name labels
    top10 = repeat_rows[:10]
    top_names = {r["tehsil"] for r in top10}
    geom_of = {t: shape(g) for t, _, g in ts}
    for r in top10:
        pt = geom_of[r["tehsil"]].representative_point()
        ax.annotate(
            r["tehsil"],
            (pt.x, pt.y),
            ha="center",
            va="center",
            fontsize=6.6,
            color="#0a1014",
            fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.16", fc="#ffd166", ec="none", alpha=0.92),
        )

    mean_lat = float(np.mean(lats)) if lats else 30.9
    ax.set_aspect(1.0 / np.cos(np.radians(mean_lat)))
    ax.autoscale_view()
    ax.axis("off")
    ax.set_title(
        figstyle.clean(
            "Punjab repeat flood victims at tehsil level, 2015–2025\n"
            "late-monsoon (>= Jul 25) seasons with > 1 % of tehsil flooded; "
            "Copernicus GFM ~100 m; top-10 named"
        ),
        color="#e8eef2",
        fontsize=10.5,
        pad=12,
    )

    # discrete amber legend swatches 0..vmax
    from matplotlib.patches import Patch

    handles = [Patch(facecolor="#14110c", edgecolor="#33404a", label="0 (never)")]
    for n in range(1, vmax + 1):
        handles.append(
            Patch(facecolor=amber(0.15 + 0.85 * (n / vmax)), label=f"{n} season(s)")
        )
    leg = ax.legend(
        handles=handles,
        title="seasons > 1% flooded",
        loc="upper right",
        fontsize=7.5,
        title_fontsize=8.5,
        framealpha=0.0,
        labelcolor="#e8eef2",
    )
    leg.get_title().set_color("#e8eef2")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(
        out_path,
        facecolor=ink,
        bbox_inches="tight",
        pil_kwargs={"optimize": True},
    )
    plt.close(fig)
    kb = out_path.stat().st_size / 1024
    print(f"wrote {out_path} ({kb:.0f} KB)")
    return top_names


def _write_csv(path: Path, fieldnames, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def _report(repeat_rows, stats_rows, have_crop, ts):
    import pyproj
    from shapely.geometry import shape

    geod = pyproj.Geod(ellps="WGS84")
    area_km2 = sum(
        abs(geod.geometry_area_perimeter(shape(g))[0]) / 1e6 for _, _, g in ts
    )
    print("\n================ TEHSIL SUMMARY ================")
    print(f"tehsils: {len(ts)}   summed area {area_km2:,.0f} km2 (official 50,362)")
    print("\ntop-10 repeat victims (late-season seasons >1% / >2%):")
    for r in repeat_rows[:10]:
        print(
            f"  {r['tehsil']:20s} {r['district']:14s} "
            f">1%:{r['seasons_gt1pct']:2d} >2%:{r['seasons_gt2pct']:2d} "
            f"maxfrac {r['max_season_fraction']:.3f} "
            f"meanha {r['mean_annual_flooded_ha']:,.0f}"
        )
    print("\ntop-5 tehsils by 2025 RF-flooded ha:")
    for r in stats_rows[:5]:
        crop = f"{r['crop_flooded_ha']:,} ha" if have_crop else "n/a"
        print(
            f"  {r['tehsil']:20s} {r['district']:14s} "
            f"RF {r['rf_flooded_ha']:>8,} ha  crop {crop}  frac {r['fraction']:.4f}"
        )
    print("===============================================")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--gfm-dir", default="data/gfm")
    ap.add_argument("--raster-dir", default="data/rasters")
    args = ap.parse_args()

    repeat_rows, ts, _ = decade_repeat_victims(Path(args.gfm_dir))
    stats_rows, have_crop = impact_2025(Path(args.raster_dir))
    render_atlas(repeat_rows, ts)
    _report(repeat_rows, stats_rows, have_crop, ts)


if __name__ == "__main__":
    main()
