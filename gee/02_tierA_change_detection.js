// Sailaab — Script 02: Tier A flood map (change detection + Otsu) + district stats
// Depends on the same constants as 01. Output: flood mask layer + CSV export of
// flooded km^2 and flooded-cropland ha per district. This is the guaranteed baseline.

// ---------- 0. Shared setup (kept in sync with 01) ----------
var gaul2 = ee.FeatureCollection('FAO/GAUL/2015/level2');
var districts = gaul2.filter(ee.Filter.and(
  ee.Filter.eq('ADM0_NAME', 'India'), ee.Filter.eq('ADM1_NAME', 'Punjab')));
var aoi = districts.union(1).geometry();
var s1 = ee.ImageCollection('COPERNICUS/S1_GRD')
  .filterBounds(aoi)
  .filter(ee.Filter.eq('instrumentMode', 'IW'))
  .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV'))
  .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VH'))
  .select(['VV', 'VH']);
function despeckle(img) { return img.focalMedian(50, 'circle', 'meters'); }
var pre  = s1.filterDate('2025-07-01', '2025-08-10').map(despeckle).median().clip(aoi);
var post = s1.filterDate('2025-08-25', '2025-09-06').map(despeckle).min().clip(aoi);
var permWater = ee.Image('JRC/GSW1_4/GlobalSurfaceWater').select('occurrence').gte(60);
var dem = ee.ImageCollection('COPERNICUS/DEM/GLO30').select('DEM').mosaic()
  .setDefaultProjection('EPSG:4326', null, 30);
var steep = ee.Terrain.slope(dem).gt(5);

// ---------- 1. Change detection ----------
var dVV = post.select('VV').subtract(pre.select('VV')).rename('dVV');

// Fixed-threshold first guess (UN-SPIDER-style): big drop AND dark now.
var FIXED_DIFF = -3, FIXED_ABS = -15;

// Otsu refinement of the difference threshold, computed over the flood belt so the
// histogram is genuinely bimodal (state-wide it drowns in unchanged pixels).
// Rough flood-belt rectangle spanning Ravi-Beas-Sutlej lowlands — adjust after 01.
var beltRect = ee.Geometry.Rectangle([74.4, 30.8, 75.8, 32.3]);
var belt = beltRect.intersection(aoi, 100);
function otsu(histDict) {
  var counts = ee.Array(ee.Dictionary(histDict).get('histogram'));
  var means = ee.Array(ee.Dictionary(histDict).get('bucketMeans'));
  var size = means.length().get([0]);
  var total = counts.reduce(ee.Reducer.sum(), [0]).get([0]);
  var sum = means.multiply(counts).reduce(ee.Reducer.sum(), [0]).get([0]);
  var mean = ee.Number(sum).divide(total);
  var indices = ee.List.sequence(1, ee.Number(size).subtract(1));
  var bss = indices.map(function (i) {
    var aCounts = counts.slice(0, 0, i);
    var aCount = aCounts.reduce(ee.Reducer.sum(), [0]).get([0]);
    var aMeans = means.slice(0, 0, i);
    var aMean = aMeans.multiply(aCounts).reduce(ee.Reducer.sum(), [0]).get([0]);
    aMean = ee.Number(aMean).divide(aCount);
    var bCount = ee.Number(total).subtract(aCount);
    var bMean = ee.Number(sum).subtract(ee.Number(aCount).multiply(aMean)).divide(bCount);
    return ee.Number(aCount).multiply(aMean.subtract(mean).pow(2))
      .add(ee.Number(bCount).multiply(bMean.subtract(mean).pow(2)));
  });
  return means.sort(bss).get([-1]);
}
var hist = dVV.reduceRegion({
  reducer: ee.Reducer.histogram(255), geometry: belt, scale: 30,
  maxPixels: 1e10, bestEffort: true
});
var otsuThresh = ee.Number(otsu(hist.get('dVV')));
print('Otsu dVV threshold (expect roughly -2 to -5 dB):', otsuThresh);
// Use Otsu but never looser than the fixed guess:
var diffThresh = otsuThresh.min(FIXED_DIFF);

// ---------- 2. Flood mask ----------
var floodRaw = dVV.lt(diffThresh).and(post.select('VV').lt(FIXED_ABS));
var flood = floodRaw
  .updateMask(permWater.not())
  .updateMask(steep.not())
  .selfMask();
// Sieve: drop speckle blobs < ~10 connected pixels (~0.1 ha at 10 m)
flood = flood.updateMask(flood.connectedPixelCount(25).gte(10)).rename('flood');

Map.centerObject(aoi, 8);
Map.addLayer(post, {bands: 'VV', min: -25, max: 0}, 'FLOOD VV');
Map.addLayer(flood, {palette: ['00b4ff']}, 'Tier A flood mask');
Map.addLayer(permWater.selfMask(), {palette: ['00318f']}, 'Permanent water', false);

// ---------- 3. District statistics ----------
var areaHa = ee.Image.pixelArea().divide(1e4);
var cropland = ee.ImageCollection('ESA/WorldCover/v200').first().select('Map').eq(40);
var pop = ee.ImageCollection('JRC/GHSL/P2023A/GHS_POP').filterDate('2020-01-01', '2021-01-01')
  .first();

var stats = districts.map(function (d) {
  var g = d.geometry();
  var floodedHa = flood.multiply(areaHa).reduceRegion({
    reducer: ee.Reducer.sum(), geometry: g, scale: 30, maxPixels: 1e10, bestEffort: true
  }).get('flood');
  var cropFloodedHa = flood.multiply(cropland).multiply(areaHa).reduceRegion({
    reducer: ee.Reducer.sum(), geometry: g, scale: 30, maxPixels: 1e10, bestEffort: true
  }).get('flood');
  var popExposed = pop.updateMask(flood).reduceRegion({
    reducer: ee.Reducer.sum(), geometry: g, scale: 100, maxPixels: 1e10, bestEffort: true
  }).values().get(0);
  return d.select(['ADM2_NAME'])
          .set('flooded_ha', floodedHa)
          .set('crop_flooded_ha', cropFloodedHa)
          .set('pop_exposed', popExposed);
});
print('Per-district stats (first 5):', stats.limit(5));

// Exports (start from the Tasks tab):
Export.table.toDrive({
  collection: stats, description: 'sailaab_tierA_district_stats_2025',
  fileFormat: 'CSV'
});
Export.image.toDrive({
  image: flood.unmask(0).byte(), description: 'sailaab_tierA_floodmask_2025',
  region: aoi, scale: 20, maxPixels: 1e10
});

// Headline check: sum(crop_flooded_ha) should land near the official
// 1.48-1.75 lakh ha band. If wildly off, revisit thresholds + windows first.
