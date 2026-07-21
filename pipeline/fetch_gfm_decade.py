# pipeline/fetch_gfm_decade.py
"""Decade batch (2015-2025) of Copernicus GFM observed flood extent from the
keyless GloFAS WMS, and the two forecaster/atlas products built from it.

Two phases (all WMS/rasterio IO lives here; pure logic is in ``sailaab.gfm`` and
``sailaab.frequency``):

    python -m pipeline.fetch_gfm_decade fetch [YEAR ...]   # Phase A: pull per-day tifs
    python -m pipeline.fetch_gfm_decade aggregate          # Phase B: build products

Phase A pulls, for every monsoon day (Jun 15 - Sep 30) of each year, a single
low-res *flood probe* (1024 px over the whole bbox, ~2-3 s). Only when the probe
is non-empty does it fetch the full ~100 m 4-tile grid and write a per-day mask to
``data/gfm/<YEAR>/gfm_punjab_<YYYYMMDD>.tif`` (gitignored). The footprint layer is
NOT used to gate the archive -- it nearest-value-falls-back to ~100% on old dates
(see ``docs/notes/gfm-decade.md``); the flood layer has clean exact-day semantics.
Progress is appended to ``data/gfm/_decade_progress.csv`` so the run is resumable.

Phase B reads the per-day tifs, unions them into the 11 monsoon windows and the
season, subtracts reference water, rasterizes the 20 Punjab districts on the same
100 m EPSG:3857 grid, and writes:

    data/gfm_district_window_fractions_2015_2025.csv  (forecaster target, committed)
    data/rasters/flood_frequency_2015_2025.tif        (season-count raster, gitignored)
    atlas/frequency_2015_2025.png                     (committed quicklook + legend)
    data/flood_frequency_districts.csv                (repeat-victims table, committed)

Reference water is pulled once into ``data/gfm/gfm_punjab_refwater.tif``.
"""

from __future__ import annotations

import argparse
import csv
import io
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image
from rasterio.warp import transform_geom

from sailaab import config
from sailaab.windows import monsoon_windows
from sailaab.districts import load_districts, rasterize_districts
from sailaab.frequency import (
    window_index,
    frequency_count,
    classify_frequency,
    summarize_repeat_victims,
)
from sailaab.gfm import flood_mask, ref_water_mask, web_mercator_area_km2
from pipeline.fetch_gfm import (
    bbox_3857,
    grid_shape,
    fetch_rgba_grid,
    write_mask_tif,
    _get,
    _getmap_params,
    FLOOD_LAYER,
    REFWATER_LAYER,
    REQUEST_PAUSE_S,
)

GFM_DIR = Path("data/gfm")
RASTER_DIR = Path("data/rasters")
PROGRESS_CSV = GFM_DIR / "_decade_progress.csv"
REFWATER_TIF = GFM_DIR / "gfm_punjab_refwater.tif"

WINDOW_FRACTIONS_CSV = Path("data/gfm_district_window_fractions_2015_2025.csv")
FREQUENCY_TIF = RASTER_DIR / "flood_frequency_2015_2025.tif"
FREQUENCY_PNG = Path("atlas/frequency_2015_2025.png")
REPEAT_VICTIMS_CSV = Path("data/flood_frequency_districts.csv")

PROBE_SIZE = 1024  # single-tile flood-probe resolution over the whole bbox


# ---------------------------------------------------------------------------
# Phase A: fetch
# ---------------------------------------------------------------------------


def season_days(year: int):
    """ISO days of the monsoon season, aligned to the half-open window manifest
    ``[06-15, 09-30)`` (Jun 15 .. Sep 29 inclusive)."""
    cur = date(year, 6, 15)
    end = date.fromisoformat(f"{year}-{config.SEASON_END_MD}")
    while cur < end:
        yield cur.isoformat()
        cur += timedelta(days=1)


def flood_probe(day: str, bounds, size: int = PROBE_SIZE) -> int:
    """Flood-pixel count from a single low-res GetMap over the whole bbox.

    Cheap gate: the full ~100 m grid is only pulled when this is > 0.
    """
    png = _get(_getmap_params(FLOOD_LAYER, day, bounds, size, size))
    arr = np.array(Image.open(io.BytesIO(png)).convert("RGBA"), dtype=np.uint8)
    return int(flood_mask(arr).sum())


def _load_progress() -> set[str]:
    done = set()
    if PROGRESS_CSV.exists():
        with open(PROGRESS_CSV, newline="") as fh:
            for row in csv.DictReader(fh):
                done.add(row["day"])
    return done


def _append_progress(day, probe_px, active, full_px, flood_km2):
    new = not PROGRESS_CSV.exists()
    PROGRESS_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(PROGRESS_CSV, "a", newline="") as fh:
        w = csv.writer(fh)
        if new:
            w.writerow(["day", "probe_px", "active", "full_px", "flood_km2"])
        w.writerow([day, probe_px, int(active), full_px, f"{flood_km2:.3f}"])


def fetch_refwater(bounds, ncols, nrows):
    if REFWATER_TIF.exists():
        print(f"reference water already present: {REFWATER_TIF}")
        return
    print("fetching reference water mask (once) ...")
    rgba = fetch_rgba_grid(REFWATER_LAYER, config.FLOOD_2025[0], bounds, ncols, nrows)
    refwater = ref_water_mask(rgba)
    write_mask_tif(REFWATER_TIF, refwater, bounds)
    print(f"  wrote {REFWATER_TIF} ({int(refwater.sum()):,} px)")


def fetch(years):
    bounds = bbox_3857()
    ncols, nrows = grid_shape(bounds)
    print(
        f"grid {ncols} x {nrows} px @ ~{config.__dict__.get('TARGET_PX_M', 100)} m "
        f"EPSG:3857; years {years}"
    )
    fetch_refwater(bounds, ncols, nrows)

    done = _load_progress()
    print(f"resume: {len(done)} day-slots already processed\n")

    for year in years:
        t_year = time.time()
        active = 0
        probed = 0
        year_dir = GFM_DIR / str(year)
        for day in season_days(year):
            if day in done:
                # count already-active days for the per-season summary
                continue
            probed += 1
            try:
                px = flood_probe(day, bounds)
            except Exception as exc:
                print(f"  {day}: probe failed ({exc}); recording empty, continuing")
                _append_progress(day, -1, False, 0, 0.0)
                time.sleep(REQUEST_PAUSE_S)
                continue
            time.sleep(REQUEST_PAUSE_S)
            if px <= 0:
                _append_progress(day, px, False, 0, 0.0)
                continue
            # flood present -> pull the full-res grid
            rgba = fetch_rgba_grid(FLOOD_LAYER, day, bounds, ncols, nrows)
            mask = flood_mask(rgba)
            full_px = int(mask.sum())
            km2 = web_mercator_area_km2(mask, bounds)
            write_mask_tif(
                year_dir / f"gfm_punjab_{day.replace('-', '')}.tif", mask, bounds
            )
            _append_progress(day, px, True, full_px, km2)
            active += 1
            print(f"  {day}: probe {px:5d} -> full {full_px:7d} px = {km2:8.1f} km2")
        # per-season summary (recount from progress for resumed years)
        yr_active = _year_active_days(year)
        print(
            f"[{year}] done: {probed} newly probed this run, "
            f"{yr_active} flood-active days total  ({time.time() - t_year:.0f}s)\n"
        )
    print("FETCH COMPLETE")


def _year_active_days(year: int) -> int:
    n = 0
    if PROGRESS_CSV.exists():
        prefix = f"{year}-"
        with open(PROGRESS_CSV, newline="") as fh:
            for row in csv.DictReader(fh):
                if row["day"].startswith(prefix) and row["active"] == "1":
                    n += 1
    return n


# ---------------------------------------------------------------------------
# Phase B: aggregate
# ---------------------------------------------------------------------------


def _read_mask(path) -> np.ndarray:
    with rasterio.open(path) as ds:
        return ds.read(1) > 0


def _district_labels(bounds, nrows, ncols):
    """Rasterize the 20 Punjab districts (canonical GAUL names) on the 100 m
    EPSG:3857 grid. Returns (labels int32, names list). Geometries are reprojected
    from the geojson's EPSG:4326 to EPSG:3857 to match the flood grid."""
    from rasterio.transform import from_bounds

    minx, miny, maxx, maxy = bounds
    transform = from_bounds(minx, miny, maxx, maxy, ncols, nrows)
    ds = load_districts(canonicalize=True)  # sorted (name, geom_4326)
    names = [n for n, _ in ds]
    geoms_3857 = [transform_geom("EPSG:4326", "EPSG:3857", g) for _, g in ds]
    labels = rasterize_districts(geoms_3857, transform, (nrows, ncols))
    return labels, names


def _row_ha(bounds, nrows, ncols) -> np.ndarray:
    """Per-row ground area of one pixel, in hectares, with the Web-Mercator
    cos^2(lat) correction (same physics as ``sailaab.gfm.web_mercator_area_km2``)."""
    minx, miny, maxx, maxy = bounds
    px = (maxx - minx) / ncols
    py = (maxy - miny) / nrows
    r_earth = 6378137.0
    rows = np.arange(nrows)
    y_center = maxy - (rows + 0.5) * py
    lat = 2.0 * np.arctan(np.exp(y_center / r_earth)) - np.pi / 2.0
    cos2 = np.cos(lat) ** 2
    return (px * py * cos2) / 1.0e4  # m^2 -> ha


def _district_ha_from_mask(mask, labels, row_ha, n_labels):
    """Vectorised per-district hectares of True pixels in ``mask``.

    Returns an array indexed 1..n_labels (index 0 = background, ignored)."""
    weight = np.broadcast_to(row_ha[:, None], mask.shape)
    sel = mask & (labels > 0)
    return np.bincount(
        labels[sel].ravel(),
        weights=weight[sel].ravel(),
        minlength=n_labels + 1,
    )


def aggregate():
    bounds = bbox_3857()
    ncols, nrows = grid_shape(bounds)

    if not REFWATER_TIF.exists():
        sys.exit(f"missing {REFWATER_TIF}; run `fetch` first")
    refwater = _read_mask(REFWATER_TIF)
    if refwater.shape != (nrows, ncols):
        sys.exit(f"refwater shape {refwater.shape} != grid {(nrows, ncols)}")

    labels, names = _district_labels(bounds, nrows, ncols)
    n_labels = len(names)
    row_ha = _row_ha(bounds, nrows, ncols)
    district_ha = _district_ha_from_mask(
        np.ones((nrows, ncols), bool), labels, row_ha, n_labels
    )

    # cross-check the vectorised area against the tested reference on a full mask
    ref_full = web_mercator_area_km2(labels > 0, bounds) * 100.0
    assert abs(district_ha[1:].sum() - ref_full) / ref_full < 1e-6, "area mismatch"

    years = config.YEARS
    window_rows = []  # forecaster target CSV
    per_season = {name: [] for name in names}  # repeat-victims input
    season_masks = []  # frequency stack (year order)
    season_union_km2 = {}

    for year in years:
        windows = monsoon_windows(year)
        n_win = len(windows)
        win_masks = [np.zeros((nrows, ncols), bool) for _ in range(n_win)]
        season_union = np.zeros((nrows, ncols), bool)

        year_dir = GFM_DIR / str(year)
        tifs = sorted(year_dir.glob("gfm_punjab_*.tif")) if year_dir.exists() else []
        for tif in tifs:
            day8 = tif.stem.split("_")[-1]  # YYYYMMDD
            day = f"{day8[:4]}-{day8[4:6]}-{day8[6:8]}"
            m = _read_mask(tif)
            season_union |= m
            idx = window_index(day, windows)
            if idx is not None:
                win_masks[idx] |= m

        # per-window district fractions (forecaster target)
        for idx, (w0, w1) in enumerate(windows):
            wm = win_masks[idx] & ~refwater
            fl_ha = _district_ha_from_mask(wm, labels, row_ha, n_labels)
            for li, name in enumerate(names, start=1):
                d_ha = district_ha[li]
                f_ha = float(fl_ha[li])
                frac = (f_ha / d_ha) if d_ha > 0 else 0.0
                window_rows.append(
                    {
                        "year": year,
                        "window_start": w0,
                        "window_end": w1,
                        "district": name,
                        "flooded_ha": round(f_ha, 2),
                        "fraction": round(frac, 6),
                    }
                )

        # per-season district fractions (repeat-victims) + frequency stack
        season_minus = season_union & ~refwater
        season_masks.append(season_minus)
        season_union_km2[year] = web_mercator_area_km2(season_minus, bounds)
        s_ha = _district_ha_from_mask(season_minus, labels, row_ha, n_labels)
        for li, name in enumerate(names, start=1):
            d_ha = district_ha[li]
            f_ha = float(s_ha[li])
            per_season[name].append(
                {"flooded_ha": f_ha, "fraction": (f_ha / d_ha) if d_ha > 0 else 0.0}
            )
        print(
            f"[{year}] active tifs {len(tifs):3d}  season union "
            f"{season_union_km2[year]:8.1f} km2"
        )

    # --- write forecaster target CSV ---
    WINDOW_FRACTIONS_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(WINDOW_FRACTIONS_CSV, "w", newline="") as fh:
        w = csv.DictWriter(
            fh,
            fieldnames=[
                "year",
                "window_start",
                "window_end",
                "district",
                "flooded_ha",
                "fraction",
            ],
        )
        w.writeheader()
        w.writerows(window_rows)
    print(f"wrote {WINDOW_FRACTIONS_CSV} ({len(window_rows)} rows)")

    # --- frequency raster (per-pixel count of seasons flooded 0..11) ---
    freq = frequency_count(season_masks).astype(np.uint8)
    RASTER_DIR.mkdir(parents=True, exist_ok=True)
    write_mask_tif(FREQUENCY_TIF, freq, bounds)  # uint8 count raster
    print(f"wrote {FREQUENCY_TIF} (max count {int(freq.max())})")

    # --- repeat-victims table ---
    summary = summarize_repeat_victims(per_season)
    with open(REPEAT_VICTIMS_CSV, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(
            [
                "district",
                "seasons_with_fraction_gt1pct",
                "seasons_with_fraction_gt2pct",
                "max_season_fraction",
                "mean_annual_flooded_ha",
            ]
        )
        for name in sorted(
            names,
            key=lambda n: (
                -summary[n]["seasons_with_fraction_gt2pct"],
                -summary[n]["mean_annual_flooded_ha"],
            ),
        ):
            s = summary[name]
            w.writerow(
                [
                    name,
                    s["seasons_with_fraction_gt1pct"],
                    s["seasons_with_fraction_gt2pct"],
                    round(s["max_season_fraction"], 6),
                    round(s["mean_annual_flooded_ha"], 2),
                ]
            )
    print(f"wrote {REPEAT_VICTIMS_CSV}")

    # --- atlas quicklook PNG ---
    size = _render_frequency_png(freq, labels, bounds, len(years))
    print(f"wrote {FREQUENCY_PNG} ({size / 1024:.0f} KB)")

    _report(season_union_km2, window_rows, summary, names)


def _maxpool(a, factor):
    nr, nc = a.shape
    ph = (-nr) % factor
    pw = (-nc) % factor
    if ph or pw:
        a = np.pad(a, ((0, ph), (0, pw)), constant_values=0)
    h, w = a.shape
    return a.reshape(h // factor, factor, w // factor, factor).max(axis=(1, 3))


def _render_frequency_png(freq, labels, bounds, n_years, max_width=1600):
    """Discrete recurrence choropleth with legend and district outlines."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import BoundaryNorm, ListedColormap
    from matplotlib.patches import Patch

    factor = max(1, int(np.ceil(freq.shape[1] / max_width)))
    f = _maxpool(freq, factor)
    # district boundary edges on the same reduced grid
    lab = _maxpool(labels.astype(np.int32), factor)
    edges = np.zeros_like(lab, bool)
    edges[:, 1:] |= lab[:, 1:] != lab[:, :-1]
    edges[1:, :] |= lab[1:, :] != lab[:-1, :]

    # classes: 0 none, 1 (1x), 2 (2-3x), 3 (4-6x), 4 (>=7x)
    edges_cls = (1, 2, 4, 7)
    cls = classify_frequency(f, edges=edges_cls)
    colors = ["#f2f2f2", "#c6dbef", "#6baed6", "#fb6a4a", "#a50f15"]
    labels_txt = ["0 (never)", "1x", "2-3x", "4-6x", ">=7x"]
    cmap = ListedColormap(colors)
    norm = BoundaryNorm(range(len(colors) + 1), cmap.N)

    minx, miny, maxx, maxy = bounds
    fig, ax = plt.subplots(figsize=(9.5, 9.0), dpi=130)
    ax.imshow(
        cls,
        cmap=cmap,
        norm=norm,
        extent=(minx, maxx, miny, maxy),
        interpolation="nearest",
    )
    # overlay district boundaries (dark grey)
    ys, xs = np.where(edges)
    if len(xs):
        ex = minx + (xs + 0.5) * (maxx - minx) / edges.shape[1]
        ey = maxy - (ys + 0.5) * (maxy - miny) / edges.shape[0]
        ax.scatter(ex, ey, s=0.15, c="#333333", marker=".", linewidths=0)
    ax.set_title(
        f"Punjab monsoon flood recurrence 2015-2025 ({n_years} seasons)\n"
        "Copernicus GFM observed flood extent, ~100 m",
        fontsize=11,
    )
    ax.set_xlabel("EPSG:3857 easting (m)")
    ax.set_ylabel("EPSG:3857 northing (m)")
    ax.legend(
        handles=[
            Patch(facecolor=c, edgecolor="#888", label=t)
            for c, t in zip(colors, labels_txt)
        ],
        title="seasons flooded",
        loc="upper right",
        fontsize=8,
        title_fontsize=9,
        framealpha=0.9,
    )
    FREQUENCY_PNG.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(FREQUENCY_PNG, bbox_inches="tight", pil_kwargs={"optimize": True})
    plt.close(fig)
    return FREQUENCY_PNG.stat().st_size


def _report(season_union_km2, window_rows, summary, names):
    print("\n================ DECADE SUMMARY ================")
    print("per-season union (minus ref water):")
    ranked = sorted(season_union_km2.items(), key=lambda kv: -kv[1])
    for rank, (yr, km2) in enumerate(ranked, 1):
        tag = "  <== MAX" if rank == 1 else ""
        print(f"  {yr}: {km2:8.1f} km2{tag}")

    # 2023 Sangrur anchor, window [08-14, 08-24)
    anchor = [
        r
        for r in window_rows
        if r["year"] == 2023
        and r["window_start"] == "2023-08-14"
        and r["district"] == "Sangrur"
    ]
    if anchor:
        ha = anchor[0]["flooded_ha"]
        lo, hi = config.SANGRUR_2023_NRSC_HA * 0.5, config.SANGRUR_2023_NRSC_HA * 1.5
        verdict = "PASS" if lo <= ha <= hi else "FAIL"
        print(
            f"\nC2 Sangrur 2023 window [08-14,08-24): {ha:,.0f} ha "
            f"(NRSC 7,121; band [{lo:,.0f},{hi:,.0f}]) -> {verdict}"
        )

    # 2019 Jalandhar / Kapurthala signal
    print("\nC3 2019 Aug windows, Jalandhar & Kapurthala flooded_ha:")
    for r in window_rows:
        if (
            r["year"] == 2019
            and r["window_start"] >= "2019-08-04"
            and r["window_start"] <= "2019-08-24"
            and r["district"] in ("Jalandhar", "Kapurthala")
        ):
            print(
                f"  {r['window_start']} {r['district']:12s} {r['flooded_ha']:8.0f} ha  frac {r['fraction']:.4f}"
            )

    print("\ntop-5 repeat-victim districts (by seasons >2% then mean annual ha):")
    top = sorted(
        names,
        key=lambda n: (
            -summary[n]["seasons_with_fraction_gt2pct"],
            -summary[n]["mean_annual_flooded_ha"],
        ),
    )[:5]
    for n in top:
        s = summary[n]
        print(
            f"  {n:12s}  >1%:{s['seasons_with_fraction_gt1pct']:2d}  "
            f">2%:{s['seasons_with_fraction_gt2pct']:2d}  "
            f"maxfrac {s['max_season_fraction']:.3f}  meanha {s['mean_annual_flooded_ha']:,.0f}"
        )
    print("===============================================")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    pf = sub.add_parser("fetch", help="Phase A: pull per-day flood tifs")
    pf.add_argument("years", nargs="*", type=int, help="years (default all 2015-2025)")
    sub.add_parser("aggregate", help="Phase B: build products from tifs")
    args = ap.parse_args()

    if args.cmd == "fetch":
        years = args.years or config.YEARS
        fetch(years)
    elif args.cmd == "aggregate":
        aggregate()


if __name__ == "__main__":
    main()
