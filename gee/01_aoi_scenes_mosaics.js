// Sailaab — Script 01: AOI, Sentinel-1 scene enumeration, pre/post mosaics, masks
// Paste into code.earthengine.google.com Code Editor and Run.
// Output: printed scene inventory + visual sanity check of pre/post mosaics and masks.

// ---------- 1. AOI: Punjab (India) + districts ----------
var gaul2 = ee.FeatureCollection('FAO/GAUL/2015/level2');
var districts = gaul2.filter(ee.Filter.and(
  ee.Filter.eq('ADM0_NAME', 'India'),
  ee.Filter.eq('ADM1_NAME', 'Punjab')));
var aoi = districts.union(1).geometry();
print('Districts (expect ~20-23; GAUL is 2015-vintage):',
      districts.aggregate_array('ADM2_NAME'));
Map.centerObject(aoi, 8);
Map.addLayer(ee.Image().paint(districts, 0, 1), {palette: ['555555']}, 'Districts');

// ---------- 2. Sentinel-1 collection ----------
var s1 = ee.ImageCollection('COPERNICUS/S1_GRD')
  .filterBounds(aoi)
  .filter(ee.Filter.eq('instrumentMode', 'IW'))
  .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV'))
  .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VH'))
  .select(['VV', 'VH']);

// Windows (2025 event). Pre = pre-monsoon-peak reference; Flood = peak window.
var PRE_START = '2025-07-01', PRE_END = '2025-08-10';
var FLOOD_START = '2025-08-25', FLOOD_END = '2025-09-06';

// ---------- 3. Scene inventory (run this first, read the console) ----------
function inventory(col, label) {
  var tbl = col.map(function (img) {
    return ee.Feature(null, {
      date: ee.Date(img.get('system:time_start')).format('YYYY-MM-dd'),
      orbit: img.get('relativeOrbitNumber_start'),
      pass: img.get('orbitProperties_pass')
    });
  });
  print(label + ' — scene count:', col.size());
  print(label + ' — date/orbit/pass:', tbl.aggregate_array('date').zip(
        tbl.aggregate_array('orbit')).zip(tbl.aggregate_array('pass')));
}
inventory(s1.filterDate(PRE_START, PRE_END), 'PRE window');
inventory(s1.filterDate(FLOOD_START, FLOOD_END), 'FLOOD window');

// ---------- 4. Speckle filter + mosaics ----------
// GRD is already in dB. Focal median is a pragmatic speckle filter at this scale.
function despeckle(img) {
  return img.focalMedian(50, 'circle', 'meters')
            .copyProperties(img, ['system:time_start']);
}
var pre = s1.filterDate(PRE_START, PRE_END).map(despeckle).median().clip(aoi);
var post = s1.filterDate(FLOOD_START, FLOOD_END).map(despeckle).min().clip(aoi);
// NOTE .min() for the flood mosaic: water = low backscatter; min() catches the
// wettest observation per pixel across the window (peak-flood compositing).

var visVV = {bands: 'VV', min: -25, max: 0};
Map.addLayer(pre, visVV, 'PRE VV (median)');
Map.addLayer(post, visVV, 'FLOOD VV (min)', false);

// ---------- 5. Masks ----------
// Permanent water (rivers/canals/Harike are not "flood"):
var permWater = ee.Image('JRC/GSW1_4/GlobalSurfaceWater')
  .select('occurrence').gte(60);
// Terrain: Copernicus GLO-30 is an ImageCollection; mosaic then slope.
var dem = ee.ImageCollection('COPERNICUS/DEM/GLO30').select('DEM').mosaic()
  .setDefaultProjection('EPSG:4326', null, 30);
var slope = ee.Terrain.slope(dem);
var steep = slope.gt(5); // radar shadow in Shivalik foothills

Map.addLayer(permWater.selfMask(), {palette: ['0044ff']}, 'Permanent water', false);
Map.addLayer(steep.selfMask(), {palette: ['aa5500']}, 'Slope > 5°', false);

// ---------- 6. Hand-off ----------
// Script 02 (Tier A) and 03 (RF) recompute these; keep windows/constants in sync.
// Sanity checklist before moving on:
//  [ ] FLOOD window has scenes covering the whole state (check inventory + mosaic gaps)
//  [ ] PRE mosaic looks "normal" (fields bright, rivers dark thin lines)
//  [ ] FLOOD mosaic shows large dark zones along Ravi/Beas/Sutlej belts
