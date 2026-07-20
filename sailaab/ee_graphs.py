# sailaab/ee_graphs.py
"""All Earth Engine graph construction lives here (thin, mirrored from gee/02)."""

import ee

from sailaab import config


def punjab_districts() -> ee.FeatureCollection:
    return ee.FeatureCollection("FAO/GAUL/2015/level2").filter(
        ee.Filter.And(
            ee.Filter.eq("ADM0_NAME", "India"), ee.Filter.eq("ADM1_NAME", "Punjab")
        )
    )


def _s1(aoi):
    return (
        ee.ImageCollection("COPERNICUS/S1_GRD")
        .filterBounds(aoi)
        .filter(ee.Filter.eq("instrumentMode", "IW"))
        .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
        .select(["VV"])
    )


def _despeckle(img):
    return img.focalMedian(50, "circle", "meters")


def _masks():
    perm = ee.Image("JRC/GSW1_4/GlobalSurfaceWater").select("occurrence").gte(60)
    dem = (
        ee.ImageCollection("COPERNICUS/DEM/GLO30")
        .select("DEM")
        .mosaic()
        .setDefaultProjection("EPSG:4326", None, 30)
    )
    return perm, ee.Terrain.slope(dem).gt(5)


def flood_mask_for_window(
    aoi, window: tuple[str, str], pre: tuple[str, str]
) -> ee.Image:
    col = _s1(aoi)
    pre_img = col.filterDate(*pre).map(_despeckle).median()
    post = col.filterDate(*window).map(_despeckle).min()
    perm, steep = _masks()
    dvv = post.subtract(pre_img)
    f = (
        dvv.lt(config.DIFF_THRESHOLD_DB)
        .And(post.lt(config.ABS_VV_THRESHOLD_DB))
        .updateMask(perm.Not())
        .updateMask(steep.Not())
        .selfMask()
    )
    return f.updateMask(
        f.connectedPixelCount(25).gte(config.MIN_CONNECTED_PIXELS)
    ).rename("flood")


def district_flood_stats(
    flood: ee.Image, districts: ee.FeatureCollection, year: int, window_start: str
) -> ee.FeatureCollection:
    area_ha = ee.Image.pixelArea().divide(1e4)
    crop = ee.ImageCollection("ESA/WorldCover/v200").first().select("Map").eq(40)
    img = (
        flood.multiply(area_ha)
        .rename("flooded_ha")
        .addBands(flood.multiply(crop).multiply(area_ha).rename("crop_flooded_ha"))
    )
    stats = img.reduceRegions(
        collection=districts, reducer=ee.Reducer.sum(), scale=30, tileScale=4
    )
    return stats.map(lambda d: d.set("window_start", window_start, "year", year))
