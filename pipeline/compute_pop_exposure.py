# pipeline/compute_pop_exposure.py
"""Population exposure: people living inside the 2025 Punjab flood extent, per
district, for BOTH independent flood masks (GFM union and Sailaab RF).

This is the third independent validation headline, cross-checked against the
official ~3.55 lakh (355,000) "affected" figure. It answers a narrower question
than the government number: not "how many people were affected by the disaster"
(evacuations, whole villages, crop/livelihood loss) but "how many people live on
the ground the SAR says went under water".

Population raster (keyless, CC-BY):
    GHSL GHS-POP, JRC, R2023A, epoch **2025**, 1 km, World Mollweide (ESRI:54009,
    equal-area). Tiles R6_C25 + R6_C26 cover Punjab:
      https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GHSL/GHS_POP_GLOBE_R2023A/
        GHS_POP_E2025_GLOBE_R2023A_54009_1000/V1-0/tiles/
        GHS_POP_E2025_GLOBE_R2023A_54009_1000_V1_0_R6_C25.zip  (and _R6_C26.zip)
    Downloaded to data/rasters/ghsl/ (gitignored, not committed).
    Documented fallback (CC-BY): WorldPop India 1 km unconstrained 2020,
      https://data.worldpop.org/GIS/Population/Global_2000_2020_1km_UNadj/2020/IND/
        ind_ppp_2020_1km_Aggregated_UNadj.tif

Method (head-count conserving; the pure math is in sailaab.exposure, unit-tested):
    counts -> density (people/m^2, GHSL is equal-area so 1e6 m^2/px)
    -> reproject density onto each flood-mask grid (bilinear; density is intensive)
    -> density * target ground-pixel-area -> counts on the flood grid
       (EPSG:3857 uses the cos^2(lat) true-ground area; UTM 32643 uses |a*e|)
    -> rasterize districts on the same grid, sum people where mask > 0.
Conservation check: total population summed inside the district polygons must land
in ~27-32 M (Punjab's actual population), reported for every grid.

Outputs:
    data/pop_exposure_2025.csv   (district, pop_exposed_rf, pop_exposed_gfm)  [committed]

Usage:
    python pipeline/compute_pop_exposure.py
"""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
import rasterio
from rasterio.merge import merge
from rasterio.warp import Resampling, reproject, transform_geom

from sailaab import districts as D
from sailaab.config import OFFICIAL_POP_AFFECTED
from sailaab.exposure import (
    counts_to_density,
    density_to_counts,
    population_in_mask_by_district,
    total_population,
    webmerc_pixel_area_m2,
)

ROOT = Path(__file__).resolve().parents[1]
GHSL_TILES = sorted(
    (ROOT / "data" / "rasters" / "ghsl").glob("GHS_POP_E2025_*_V1_0_R6_C2*.tif")
)
GFM_TIF = ROOT / "data" / "gfm" / "gfm_punjab_20250827_0905.tif"
RF_TIF = ROOT / "data" / "rasters" / "rf_flood_2025.tif"
OUT_CSV = ROOT / "data" / "pop_exposure_2025.csv"

GHSL_PIXEL_AREA_M2 = 1_000_000.0  # Mollweide 1 km, equal-area
GHSL_NODATA = -200.0


def load_ghsl_density():
    """Mosaic the GHSL tiles and return (density people/m^2, transform, crs)."""
    srcs = [rasterio.open(f) for f in GHSL_TILES]
    try:
        mosaic, transform = merge(srcs)
        crs = srcs[0].crs
    finally:
        for s in srcs:
            s.close()
    counts = mosaic[0]
    density = counts_to_density(counts, GHSL_PIXEL_AREA_M2, nodata=GHSL_NODATA)
    return (
        density,
        transform,
        crs,
        float(total_population(np.where(counts == GHSL_NODATA, 0.0, counts))),
    )


def pop_counts_on_grid(
    density, src_transform, src_crs, dst_crs, dst_transform, dst_shape
):
    """Reproject GHSL density onto a target grid and convert back to head counts."""
    dst_density = np.zeros(dst_shape, dtype="float64")
    reproject(
        source=density,
        destination=dst_density,
        src_transform=src_transform,
        src_crs=src_crs,
        dst_transform=dst_transform,
        dst_crs=dst_crs,
        resampling=Resampling.bilinear,
    )
    if dst_crs.to_epsg() == 3857:
        area = webmerc_pixel_area_m2(dst_transform, dst_shape)  # cos^2(lat) ground area
    else:  # UTM 32643: near-conformal, pixel ground area = |a * e| (<0.1% scale error)
        area = abs(dst_transform[0] * dst_transform[4])
    return density_to_counts(dst_density, area)


def exposure_for(mask_tif, density, src_transform, src_crs, names):
    """Return (per-district dict, punjab_total_on_grid) for one flood-mask raster."""
    with rasterio.open(mask_tif) as ds:
        dst_crs, dst_transform, dst_shape = ds.crs, ds.transform, ds.shape
        mask = ds.read(1)
    counts = pop_counts_on_grid(
        density, src_transform, src_crs, dst_crs, dst_transform, dst_shape
    )
    geoms = [
        (n, transform_geom("EPSG:4326", dst_crs, g))
        for n, g in D.load_districts(canonicalize=True)
    ]
    labels = D.rasterize_districts(geoms, dst_transform, dst_shape)
    by_dist = population_in_mask_by_district(counts, labels, mask, names=names)
    return by_dist, total_population(counts, labels)


def main():
    density, moll_tf, moll_crs, ghsl_total = load_ghsl_density()
    names = [n for n, _ in D.load_districts(canonicalize=True)]

    # native-grid reference: GHSL people inside the district polygons (Mollweide)
    g_moll = [
        (n, transform_geom("EPSG:4326", moll_crs, g))
        for n, g in D.load_districts(canonicalize=True)
    ]
    lab_moll = D.rasterize_districts(g_moll, moll_tf, density.shape)
    # density was area-normalised; recover counts on the native grid for the ref sum
    ref_counts = density * GHSL_PIXEL_AREA_M2
    ref_total = total_population(ref_counts, lab_moll)

    gfm, gfm_total = exposure_for(GFM_TIF, density, moll_tf, moll_crs, names)
    rf, rf_total = exposure_for(RF_TIF, density, moll_tf, moll_crs, names)

    rows = []
    for name in names:
        rows.append(
            {
                "district": name,
                "pop_exposed_rf": round(rf[name]["pop_exposed"], 1),
                "pop_exposed_gfm": round(gfm[name]["pop_exposed"], 1),
            }
        )
    rows.sort(key=lambda r: r["pop_exposed_gfm"], reverse=True)

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(
            fh, fieldnames=["district", "pop_exposed_rf", "pop_exposed_gfm"]
        )
        w.writeheader()
        w.writerows(rows)

    tot_rf = sum(r["pop_exposed_rf"] for r in rows)
    tot_gfm = sum(r["pop_exposed_gfm"] for r in rows)
    print(f"wrote {OUT_CSV}")
    print("\n=== CONSERVATION (Punjab total population from GHSL) ===")
    print(
        f"GHSL districts native (Mollweide): {ref_total:,.0f}  ({ref_total / 1e6:.2f} M)"
    )
    print(
        f"  on GFM grid (EPSG:3857): {gfm_total:,.0f}  ({100 * gfm_total / ref_total:.2f}% of native)"
    )
    print(
        f"  on RF  grid (EPSG:32643): {rf_total:,.0f}  ({100 * rf_total / ref_total:.2f}% of native)"
    )
    print("\n=== STATEWIDE POPULATION EXPOSED IN 2025 FLOOD EXTENT ===")
    print(
        f"RF  mask (tight, lower bracket): {tot_rf:,.0f}  = {100 * tot_rf / OFFICIAL_POP_AFFECTED:.1f}% of official {OFFICIAL_POP_AFFECTED:,}"
    )
    print(
        f"GFM mask (broad, upper bracket): {tot_gfm:,.0f}  = {100 * tot_gfm / OFFICIAL_POP_AFFECTED:.1f}% of official {OFFICIAL_POP_AFFECTED:,}"
    )
    print("\n=== TOP 5 DISTRICTS (by GFM-mask exposure) ===")
    for r in rows[:5]:
        print(
            f"  {r['district']:<28} RF {r['pop_exposed_rf']:>10,.0f}   GFM {r['pop_exposed_gfm']:>10,.0f}"
        )


if __name__ == "__main__":
    main()
