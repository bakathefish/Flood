"""Sailaab — Wave 2: decade batch runner (2015–2025 monsoon flood masks).

Runs the Tier-A change-detection logic over every ~10-day monsoon window for each
year, computes per-district flooded area server-side (no raster exports except the
final frequency layer), and writes one CSV per year + a state flood-frequency image.

Setup (once):
    pip install earthengine-api pandas
    earthengine authenticate
    # then set EE_PROJECT below to your GEE cloud project id

Run:
    python pipeline/batch_decade.py            # all years
    python pipeline/batch_decade.py 2023       # single year (sanity: Sangrur, Jul 2023)

Outputs land in Google Drive folder 'sailaab' as CSV export tasks; poll the GEE
Tasks tab or `earthengine task list`.
"""

import sys
import ee

EE_PROJECT = "YOUR-GEE-PROJECT-ID"  # TODO after GEE signup

YEARS = list(range(2015, 2026))
SEASON_START = "-06-15"
SEASON_END = "-09-30"
WINDOW_DAYS = 10
PRE_MONTHS = ("-04-01", "-05-31")  # dry-season reference per year (pre-monsoon)

DIFF_T = -3.0  # dVV threshold (dB) — keep in sync with gee/02
ABS_T = -15.0  # post VV threshold (dB)


def init():
    ee.Initialize(project=EE_PROJECT)


def punjab():
    g = ee.FeatureCollection("FAO/GAUL/2015/level2").filter(
        ee.Filter.And(
            ee.Filter.eq("ADM0_NAME", "India"), ee.Filter.eq("ADM1_NAME", "Punjab")
        )
    )
    return g, g.union(1).geometry()


def s1(aoi):
    return (
        ee.ImageCollection("COPERNICUS/S1_GRD")
        .filterBounds(aoi)
        .filter(ee.Filter.eq("instrumentMode", "IW"))
        .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
        .select(["VV"])
    )


def masks():
    perm = ee.Image("JRC/GSW1_4/GlobalSurfaceWater").select("occurrence").gte(60)
    dem = (
        ee.ImageCollection("COPERNICUS/DEM/GLO30")
        .select("DEM")
        .mosaic()
        .setDefaultProjection("EPSG:4326", None, 30)
    )
    steep = ee.Terrain.slope(dem).gt(5)
    return perm, steep


def flood_mask(col, pre_img, perm, steep):
    post = col.map(lambda i: i.focalMedian(50, "circle", "meters")).min()
    dvv = post.subtract(pre_img)
    f = (
        dvv.lt(DIFF_T)
        .And(post.lt(ABS_T))
        .updateMask(perm.Not())
        .updateMask(steep.Not())
        .selfMask()
    )
    return f.updateMask(f.connectedPixelCount(25).gte(10)).rename("flood")


def year_windows(year):
    start = ee.Date(f"{year}{SEASON_START}")
    end = ee.Date(f"{year}{SEASON_END}")
    n = end.difference(start, "day").divide(WINDOW_DAYS).floor().getInfo()
    return [
        (
            start.advance(i * WINDOW_DAYS, "day"),
            start.advance((i + 1) * WINDOW_DAYS, "day"),
        )
        for i in range(int(n))
    ]


def run_year(year, districts, aoi, perm, steep):
    col = s1(aoi)
    pre_img = (
        col.filterDate(f"{year}{PRE_MONTHS[0]}", f"{year}{PRE_MONTHS[1]}")
        .map(lambda i: i.focalMedian(50, "circle", "meters"))
        .median()
    )
    area_ha = ee.Image.pixelArea().divide(1e4)
    crop = ee.ImageCollection("ESA/WorldCover/v200").first().select("Map").eq(40)

    feats, season_max = [], ee.Image(0)
    for w0, w1 in year_windows(year):
        wcol = col.filterDate(w0, w1)
        # skip empty windows client-side to avoid null mosaics
        if wcol.size().getInfo() == 0:
            continue
        f = flood_mask(wcol, pre_img, perm, steep)
        season_max = season_max.Or(f.unmask(0))
        stats = (
            f.multiply(area_ha)
            .addBands(f.multiply(crop).multiply(area_ha))
            .reduceRegions(
                collection=districts, reducer=ee.Reducer.sum(), scale=30, tileScale=4
            )
        )
        date0 = w0.format("YYYY-MM-dd").getInfo()
        stats = stats.map(lambda d: d.set("window_start", date0, "year", year))
        feats.append(stats)

    merged = ee.FeatureCollection(feats).flatten()
    ee.batch.Export.table.toDrive(
        collection=merged,
        description=f"sailaab_decade_{year}",
        folder="sailaab",
        fileFormat="CSV",
    ).start()
    return season_max.rename(f"y{year}")


def main():
    init()
    districts, aoi = punjab()
    perm, steep = masks()
    years = [int(sys.argv[1])] if len(sys.argv) > 1 else YEARS

    season_layers = []
    for y in years:
        print(f"queueing {y} ...")
        season_layers.append(run_year(y, districts, aoi, perm, steep))

    if len(season_layers) == len(YEARS):  # full run -> frequency raster
        freq = (
            ee.ImageCollection([img for img in season_layers])
            .toBands()
            .reduce(ee.Reducer.sum())
            .rename("flood_frequency")
        )
        ee.batch.Export.image.toDrive(
            image=freq.byte(),
            description="sailaab_flood_frequency_2015_2025",
            folder="sailaab",
            region=aoi,
            scale=30,
            maxPixels=1e10,
        ).start()
    print("All export tasks queued. Monitor: earthengine task list")


if __name__ == "__main__":
    main()

# Sanity anchors while tuning:
#   2023: Sangrur ~7,121 ha (NRSC, 18 Aug 2023) and Jul-2023 Sutlej/Ghaggar belt
#   2019: Aug Sutlej breach — Jalandhar/Kapurthala bet areas
#   2025: crop_flooded sum near 1.48-1.75 lakh ha statewide
# Quota notes: if exports throttle, run alternate years first (2019/2021/2023/2025);
# the frequency map remains meaningful and the plan's cut-line covers it.
