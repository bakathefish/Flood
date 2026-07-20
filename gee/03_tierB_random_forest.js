// Sailaab — Script 03: Tier B Random Forest segmentation + spatial cross-validation
// The judged "AI component". Precedent: IJIST Oct-2025 RF on this same flood
// (Pakistan side) @ 98.3% OA. Labels are auto-sampled from high-confidence strata;
// validation uses spatially disjoint district folds (anti-leakage).
//
// v0 labels = Tier-A-strict (flood) vs strict-dry. UPGRADE PATH: after downloading
// Copernicus GFM layers (global-flood.emergency.copernicus.eu), upload as an asset
// and switch `floodLabelZone` to TierA AND GFM agreement.

// ---------- 0. Shared setup (in sync with 01/02) ----------
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
var gsw = ee.Image('JRC/GSW1_4/GlobalSurfaceWater').select('occurrence').unmask(0);
var permWater = gsw.gte(60);
var dem = ee.ImageCollection('COPERNICUS/DEM/GLO30').select('DEM').mosaic()
  .setDefaultProjection('EPSG:4326', null, 30);
var slope = ee.Terrain.slope(dem);

// ---------- 1. Feature stack ----------
var dVV = post.select('VV').subtract(pre.select('VV')).rename('dVV');
var dVH = post.select('VH').subtract(pre.select('VH')).rename('dVH');
var stack = ee.Image.cat([
  post.select('VV').rename('postVV'),
  post.select('VH').rename('postVH'),
  post.select('VV').subtract(post.select('VH')).rename('VVminusVH'),
  dVV, dVH,
  slope.rename('slope'),
  dem.rename('elev'),
  gsw.rename('occurrence')
]).clip(aoi);
var BANDS = ['postVV', 'postVH', 'VVminusVH', 'dVV', 'dVH', 'slope', 'elev', 'occurrence'];

// ---------- 2. Auto-labels from high-confidence strata ----------
// STRICT flood: very large drop, very dark now, flat, not permanent water.
var floodLabelZone = dVV.lt(-5).and(post.select('VV').lt(-16))
  .and(slope.lt(2)).and(permWater.not());
// STRICT dry: barely changed, bright, never water historically.
var dryLabelZone = dVV.gt(-1).and(post.select('VV').gt(-13)).and(gsw.eq(0));

var labelImg = ee.Image(0).where(floodLabelZone, 1).rename('label')
  .updateMask(floodLabelZone.or(dryLabelZone));

// ---------- 3. Spatial folds (anti-leakage) ----------
var RAVI_BEAS = ['Gurdaspur', 'Amritsar', 'Kapurthala', 'Taran Taran', 'Tarn Taran',
                 'Hoshiarpur', 'Jalandhar'];
var SUTLEJ = ['Firozpur', 'Ferozepur', 'Faridkot', 'Ludhiana', 'Moga', 'Rupnagar',
              'Nawanshahr', 'Fatehgarh Sahib'];
// NOTE: print district names from 01 and fix spellings above to match GAUL exactly.
var foldA = districts.filter(ee.Filter.inList('ADM2_NAME', RAVI_BEAS)).geometry();
var foldB = districts.filter(ee.Filter.inList('ADM2_NAME', SUTLEJ)).geometry();

function samplePts(region, n) {
  return stack.addBands(labelImg).stratifiedSample({
    numPoints: n, classBand: 'label', region: region, scale: 30,
    seed: 42, geometries: false, tileScale: 4
  });
}
var trainA = samplePts(foldA, 4000), testB = samplePts(foldB, 2000);
var trainB = samplePts(foldB, 4000), testA = samplePts(foldA, 2000);

// ---------- 4. Train + evaluate (fold A->B, then B->A) ----------
function runFold(train, test, tag) {
  var rf = ee.Classifier.smileRandomForest(200)
    .train({features: train, classProperty: 'label', inputProperties: BANDS});
  var cm = test.classify(rf).errorMatrix('label', 'classification');
  print(tag + ' confusion matrix:', cm);
  print(tag + ' OA:', cm.accuracy(), 'F1(flood):', cm.fscore().get([1]));
  return rf;
}
var rfAB = runFold(trainA, testB, 'Train Ravi-Beas -> Test Sutlej');
var rfBA = runFold(trainB, testA, 'Train Sutlej -> Test Ravi-Beas');

// ---------- 5. Final model (all labels) + map ----------
var rfFinal = ee.Classifier.smileRandomForest(200)
  .train({features: trainA.merge(trainB), classProperty: 'label', inputProperties: BANDS});
var rfFlood = stack.classify(rfFinal).eq(1)
  .updateMask(permWater.not()).updateMask(slope.lt(5).or(slope.mask().not()))
  .selfMask().rename('flood');
rfFlood = rfFlood.updateMask(rfFlood.connectedPixelCount(25).gte(10));

print('RF variable importance:', rfFinal.explain().get('importance'));

Map.centerObject(aoi, 8);
Map.addLayer(post, {bands: 'VV', min: -25, max: 0}, 'FLOOD VV');
Map.addLayer(rfFlood, {palette: ['ff5500']}, 'RF flood');
// Confidence layer = RF AND Tier-A agreement (recompute TierA or load its asset):
// Map.addLayer(rfFlood.and(tierA), {palette:['ffffff']}, 'High confidence');

Export.image.toDrive({
  image: rfFlood.unmask(0).byte(), description: 'sailaab_RF_floodmask_2025',
  region: aoi, scale: 20, maxPixels: 1e10
});
// Re-run the district-stats block from 02 with `rfFlood` for the headline table.
//
// HONESTY NOTES for the synopsis:
//  - Labels are model-bootstrapped (strict-strata), not hand-digitized ground truth;
//    the independent checks are GFM + NDEM + the official crop-area band.
//  - Report BOTH fold accuracies, not just the better one.
