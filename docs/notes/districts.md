# Punjab district polygons — source, reconciliation, and the rasterize/lookup core

District boundaries for Punjab (India) plus the tested module every downstream
district statistic depends on: flood fractions per district, the spatial-CV
folds, and the per-district tables. Polygons feed `sailaab.districts`
(load → rasterize → reduce a SAR flood mask to per-district ha/fraction) and the
name crosswalk that reconciles our polygon spellings with the GAUL-2015
`ADM2_NAME` spellings the GEE side and `sailaab.config` use.

## Files produced

| File | What | Notes |
|------|------|-------|
| `data/punjab_districts.geojson` | 20 Punjab district polygons | datameet Census-2011, ODbL; one `district` property; 388 KB |
| `sailaab/districts.py` | load / rasterize / district_fractions / fold_of + `NAME_ALIASES` | pure numpy + `rasterio.features`; no I/O beyond reading the geojson |
| `pipeline/fetch_districts.py` | fetch + filter the datameet all-India file → the geojson | stdlib `urllib`, keyless |
| `tests/test_districts.py` | 19 tests (red→green) | includes a pyproj area-sanity guard |

**New dependency: `shapely` (>=2.0).** Used for geometry handling by callers and
by the area-sanity test (`shapely.geometry.shape`). `rasterio` (already required)
supplies `rasterio.features.rasterize`; `numpy` is already required. `pyproj`
(a rasterio transitive dep, so already present) is used only for the geodesic
area check in the notes/tests — the test `importorskip`s it, so it is not a hard
requirement.

## Dataset citation

- **Source:** datameet/maps — *Census 2011 district boundaries of India*
  (`Districts/Census_2011`), served raw from GitHub:
  `https://raw.githubusercontent.com/datameet/maps/master/docs/data/geojson/dists11.geojson`
  (all-India FeatureCollection, 641 features; we keep `ST_NM=="Punjab"` → 20).
- **Repo / provenance:** <https://github.com/datameet/maps>
- **License:** Open Database License (**ODbL** v1.0) — attribution + share-alike.
- **Access date:** 2026-07-21. No login, no API key.
- **Properties in the source:** `DISTRICT`, `ST_NM`, `ST_CEN_CD`, `DT_CEN_CD`,
  `censuscode`. We re-emit only `district` (= `DISTRICT`) + `state`.

### Why datameet (route a), not geoBoundaries (route b)
datameet worked on the first try and its **Census-2011 vintage matches the
`FAO/GAUL/2015/level2` vintage already used** across `gee/*.js` and the
`config.FOLD_*` lists (20 districts; 12 of the 13 fold districts match GAUL
`ADM2_NAME` **verbatim**). geoBoundaries gbOpen ADM2 is the modern 23-district
layout (Pathankot, Fazilka, Malerkotla split out) and carries no state field, so
it would have needed name-matching *and* a vintage back-merge. datameet is the
faithful, lower-risk choice; geoBoundaries (CC-BY 4.0) remains the documented
fallback if a modern 23-district layer is ever needed.

## Geometry fidelity — no simplification

The Punjab subset is only ~0.4 MB, far under the 5 MB budget, so the polygons are
kept at **full source resolution** (259–1283 vertices/district; Kapurthala and
Patiala are MultiPolygons). **Area sanity check** (geodesic, WGS84 ellipsoid via
`pyproj.Geod`):

> **Σ area = 50,426.7 km²** vs official Punjab **50,362 km²** → **+0.13%**
> (+64.7 km²). Well within cartographic tolerance — confirms the polygons are
> faithful and complete.

## Name reconciliation (datameet → GAUL-2015 `ADM2_NAME`)

The geojson stores the **datameet** spelling in `district`. `sailaab.districts`
owns the crosswalk: `NAME_ALIASES` + `canonical_name()` map datameet (and common
GEE/press) spellings onto the GAUL/`config` spellings, and `fold_of()` uses it.
Call `load_districts(canonicalize=True)` to get GAUL-spelled names directly.

**Only one district actually diverges** between the datameet and GAUL vintages:

| # | datameet `DISTRICT` | GAUL-2015 `ADM2_NAME` (config) | fold | area km² | note |
|---|---|---|---|---:|---|
| 1 | Amritsar | Amritsar | ravi_beas | 2659.9 | exact |
| 2 | Barnala | Barnala | — | 1485.3 | outside flood basins |
| 3 | Bathinda | Bathinda | — | 3369.5 | outside flood basins |
| 4 | Faridkot | Faridkot | sutlej | 1450.8 | exact |
| 5 | Fatehgarh Sahib | Fatehgarh Sahib | sutlej | 1142.9 | exact |
| 6 | Firozpur | Firozpur | sutlej | 5204.2 | exact (not "Ferozepur") |
| 7 | Gurdaspur | Gurdaspur | ravi_beas | 3619.2 | exact |
| 8 | Hoshiarpur | Hoshiarpur | ravi_beas | 3366.7 | exact |
| 9 | Jalandhar | Jalandhar | ravi_beas | 2605.7 | exact |
| 10 | Kapurthala | Kapurthala | ravi_beas | 1661.3 | exact |
| 11 | Ludhiana | Ludhiana | sutlej | 3584.8 | exact |
| 12 | Mansa | Mansa | — | 2211.1 | outside flood basins |
| 13 | Moga | Moga | sutlej | 2346.6 | exact |
| 14 | Muktsar | Muktsar | — | 2604.5 | modern "Sri Muktsar Sahib"; aliased |
| 15 | Patiala | Patiala | — | 3329.4 | outside flood basins |
| 16 | Rupnagar | Rupnagar | sutlej | 1383.8 | exact (a.k.a. Ropar; aliased) |
| 17 | Sahibzada Ajit Singh Nagar | Sahibzada Ajit Singh Nagar | — | 1107.6 | a.k.a. Mohali / S.A.S. Nagar; aliased |
| 18 | Sangrur | Sangrur | — | 3599.1 | contains Malerkotla — see below |
| 19 | **Shahid Bhagat Singh Nagar** | **Nawanshahr** | **sutlej** | 1300.9 | **the one real mismatch → aliased** |
| 20 | Tarn Taran | Tarn Taran | ravi_beas | 2393.1 | exact |

**Mismatch found (1):** `Shahid Bhagat Singh Nagar` (datameet Census-2011, the
district's post-2008 official name / "SBS Nagar") = **`Nawanshahr`** (the GAUL
`ADM2_NAME` in `config.FOLD_SUTLEJ`). Handled by
`NAME_ALIASES["Shahid Bhagat Singh Nagar"] = "Nawanshahr"`; `fold_of()` therefore
returns `"sutlej"` for either spelling.

**Fold coverage:** all **13** `config` fold districts (6 Ravi-Beas + 7 Sutlej)
resolve from the geojson; the other **7** (Barnala, Bathinda, Mansa, Muktsar,
Patiala, Sahibzada Ajit Singh Nagar, Sangrur) are outside the Ravi-Beas & Sutlej
flood basins and correctly return `fold_of() → None`. No config fold district is
missing from the polygons.

### Districts NOT in this file (vintage gaps — by design)
datameet Census-2011 = GAUL-2015 vintage, so three **post-2011 districts do not
exist as separate polygons** and are folded into their parent:

| modern district | created | folded into (this file) |
|---|---|---|
| **Malerkotla** | 2021, from Sangrur | **Sangrur** |
| **Pathankot** | 2011, from Gurdaspur | **Gurdaspur** |
| **Fazilka** | 2011, from Firozpur | **Firozpur** |

This is consistent with the GEE side (also GAUL-2015). If a source ever supplies
Malerkotla/Pathankot/Fazilka separately (e.g. geoBoundaries), map them back to
Sangrur/Gurdaspur/Firozpur respectively before joining to `config`. `NAME_ALIASES`
is the place to add such mappings; no change to `config.py` is needed.

## Module API (`sailaab.districts`)

```python
load_districts(path=DEFAULT_GEOJSON, canonicalize=False)
    -> list[(name, geometry_dict)]           # sorted by name (stable labels)
NAME_ALIASES: dict                            # datameet/variant -> GAUL spelling
canonical_name(name) -> str                   # apply aliases (+ whitespace collapse)
rasterize_districts(geoms, transform, shape, *, all_touched=False)
    -> int32 label array                      # label i+1 per district, 0 = nodata
district_fractions(label_array, mask_array, pixel_area_ha, names=None)
    -> {key: {flooded_ha, district_ha, flooded_fraction}}   # pure numpy
fold_of(name) -> 'ravi_beas' | 'sutlej' | None
```

`district_fractions` counts a pixel as flooded where the mask is **finite and
`> 0`**; `NaN`/non-finite = nodata (never flood), and background label `0` is
always excluded. Labels from `rasterize_districts` line up with the order of
`load_districts`, so pass `names=[n for n, _ in load_districts()]` to key the
result by district name (or `canonicalize=True` for GAUL-spelled keys that join
to the GEE `reduceRegions` exports and `sailaab.stats`).

## Reproduce
```
python pipeline/fetch_districts.py          # -> data/punjab_districts.geojson (20 districts)
python -m pytest tests/test_districts.py -q  # 19 tests
```
