# Punjab tehsil (sub-district) flood layer — source, reconciliation, repeat victims

Takes the district flood analysis down one administrative level, to **tehsil**
(ADM3 sub-district). The relief-tooling headline is a **named list of tehsils
that flooded repeatedly, 2015–2025** (late-monsoon, river-flood climatology) plus
each tehsil's **2025 crop-loss**. Everything reuses the tested district machinery
— `sailaab.districts.rasterize_districts` / `district_fractions`,
`sailaab.frequency.summarize_repeat_victims`, the decade per-row cos²-lat area
helpers in `pipeline/fetch_gfm_decade.py`, and `sailaab.stats.crop_value_at_risk`
— on the same two on-disk grids, so no new WMS pulls and no new area physics.

## Files produced

| File | What | Notes |
|------|------|-------|
| `data/punjab_tehsils.geojson` | 91 tehsil polygons, props `tehsil`,`district` | geoBoundaries gbOpen IND ADM3 (2018), CC-BY 4.0; clipped to Punjab; 1.25 MB |
| `sailaab/tehsils.py` | `normalize_tehsil_name` / `overlap_fraction` / `assign_district` / `load_tehsils` | pure logic; `shapely` for the two geometric primitives |
| `pipeline/fetch_tehsils.py` | build the geojson (download ADM3 → filter → assign → clip) | keyless `urllib`; reuses `sailaab.tehsils` + `sailaab.districts` |
| `pipeline/tehsil_stats.py` | the two flood products + atlas figure from on-disk tifs | no network; `--gfm-dir` / `--raster-dir` inputs |
| `data/tehsil_season_fractions.csv` | per-tehsil late-season flooded ha/fraction × 11 seasons | 1,001 rows (91 × 11) |
| `data/tehsil_repeat_victims.csv` | the headline recurrence table | sorted by `seasons_gt1pct` desc |
| `data/tehsil_flood_stats_2025.csv` | per-tehsil 2025 RF-flooded ha, crop-flooded ha, ₹ VaR | 91 rows |
| `atlas/tehsil_repeat_victims.png` | dark-ink amber choropleth, top-10 named | 223 KB (< 1.5 MB) |
| `tests/test_tehsils.py` | 15 tests (red→green), incl. a pyproj area guard | pure + committed-artifact |

## Dataset citation

- **Source:** **geoBoundaries** gbOpen — *India ADM3 (sub-district / tehsil)*,
  served raw from GitHub at pinned release commit `9469f09`:
  `https://github.com/wmgeolab/geoBoundaries/raw/9469f09/releaseData/gbOpen/IND/ADM3/geoBoundaries-IND-ADM3.geojson`
  (all-India, 6,824 features; we keep the 91 that lie majority-inside Punjab).
- **Provenance / project:** <https://www.geoboundaries.org> (William & Mary geoLab).
- **License:** **CC-BY 4.0** — © geoBoundaries; open, attribution required.
- **Vintage:** `boundaryYearRepresented` = **2018**.
- **Access date:** 2026-07-22. No login, no API key.
- **Source properties:** only `shapeName` (the tehsil), `shapeID`, `shapeGroup`,
  `shapeType`; **no parent-district field** → district assigned spatially (below).

### Why geoBoundaries (route b), not datameet (route a)
`docs/notes/districts.md` names datameet as route a and geoBoundaries as the
documented fallback. For tehsils the fallback is forced: **datameet/maps ships no
sub-district layer** (the full tree carries only Districts, States, and
assembly/parliamentary constituencies — verified 2026-07-22). geoBoundaries
gbOpen IND ADM3 is the keyless, license-clean sub-district source; its lack of a
district field is handled by spatial assignment, so no fragile name-join is
needed.

## Build method (`pipeline/fetch_tehsils.py`)

1. **Punjab union** = `unary_union` of the 20 datameet district polygons
   (`data/punjab_districts.geojson`, canonicalized to GAUL/`config` spellings).
2. **Membership** — keep an ADM3 tehsil iff `overlap_fraction(tehsil, union) ≥
   0.5` (≥ 50 % of its area inside Punjab). This defines the *named list* of
   genuine Punjab tehsils and rejects Haryana/Rajasthan/Himachal/Pakistan border
   units that only nick the state.
3. **Parent district** = `assign_district` → the district of **maximum
   intersection area** (canonical spelling; e.g. datameet *Shahid Bhagat Singh
   Nagar* → **Nawanshahr**).
4. **Clip** each kept tehsil to the Punjab union so area *and* flood stay
   within-state (a border tehsil's Pakistani/Haryana remainder — heavily flooded
   in 2025 — is excluded, not misattributed).
5. **Normalize** `shapeName` (`normalize_tehsil_name`), emit `tehsil` + `district`
   only, sorted `(district, tehsil)` for stable rasterize labels.

**Count: 91 tehsils** across all 20 districts (Sangrur 9; Gurdaspur 7; Ludhiana 7;
Firozpur 6; Patiala 6; Amritsar/Jalandhar/Rupnagar 5; Bathinda/Fatehgarh
Sahib/Hoshiarpur/Kapurthala/Moga/Tarn Taran 4; Faridkot/Mansa/Nawanshahr/SAS
Nagar 3; Barnala 2). Within the expected ~80–90 band (2018 vintage split a few
sub-tehsils out).

## Area sanity

Geodesic (WGS84, `pyproj.Geod`) sum of the 91 **clipped** tehsils:

> **Σ area = 50,280 km²** vs official Punjab **50,362 km²** → **−0.16 %** (−82
> km²). The −0.16 % is Punjab area falling in border ADM3 units dropped by the
> ≥50 % rule; the Punjab union itself is 50,427 km², so the kept+clipped tehsils
> recover **99.7 %** of the state. Full (un-clipped) tehsil area is 50,454 km².

## Name normalization (geoBoundaries `shapeName` quirks)

`normalize_tehsil_name` collapses whitespace and canonicalizes a trailing roman
numeral part-suffix to `-<UPPER>`, **without merging distinct parts**. Trailing
short words that are not roman numerals and parenthetical qualifiers are left
alone. The only quirks in the Punjab set:

| raw `shapeName` | normalized | issue fixed |
|---|---|---|
| `Amritsar -I` | `Amritsar-I` | stray space before hyphen |
| `Amritsar- Ii` | `Amritsar-II` | space after hyphen + `Ii`→`II` casing |
| `Jalandhar - I` | `Jalandhar-I` | spaced hyphen |
| `Jalandhar - Ii` | `Jalandhar-II` | spaced hyphen + casing |

Left as-is (documented, not "fixed"): `Ludhiana (East)`, `Ludhiana (West)`,
`Sas Nagar (Mohali)` (a.k.a. SAS Nagar / Mohali, parent district Sahibzada Ajit
Singh Nagar). No duplicate tehsil names occur, so the name is a safe key.

## Grids + late-season convention (reused, not re-derived)

- **Decade repeat-victims** — GFM per-day tifs, ~100 m **EPSG:3857**
  (grid `3451×3991`, `pipeline.fetch_gfm.bbox_3857`/`grid_shape`), tehsils
  rasterized after `transform_geom` 4326→3857, reference water subtracted. Only
  **late-season days (≥ Jul 25)** are unioned per season — the calibrated
  convention of `docs/notes/gfm-decade.md` that excludes the Jun–mid-Jul
  paddy-transplant inundation signal, identical to the district late-season
  product `data/flood_frequency_districts_late_season.csv`.
- **2025 impact** — the committed `rf_flood_2025.tif` + `rf_cropland.tif` (ESA
  WorldCover 2021 class 40), 90 m **EPSG:32643** (0.81 ha/pixel), via the same
  `district_fractions`. Crop VaR = `crop_value_at_risk` (paddy 6.5 t/ha × ₹23,200/t).

## Headline — top-10 repeat-victim tehsils (late-season, 2015–2025)

Sorted by seasons with > 1 % of the tehsil flooded (then > 2 %, then mean annual
ha). Every one sits on the Sutlej / Beas / Ravi / Ghaggar corridors — the tehsil
resolution pins the recurrence to specific blocks a district map blurs:

| # | tehsil | district | seasons >1% | seasons >2% | max season frac | mean annual ha |
|---|---|---|---:|---:|---:|---:|
| 1 | Khadur Sahib | Tarn Taran | 6 | 5 | 0.079 | 1,086 |
| 2 | Sultanpur Lodhi | Kapurthala | 5 | 5 | 0.155 | 1,738 |
| 3 | Moonak | Sangrur | 4 | 4 | 0.290 | 1,420 |
| 4 | Patti | Tarn Taran | 4 | 4 | 0.078 | 777 |
| 5 | Firozpur | Firozpur | 4 | 2 | 0.053 | 1,599 |
| 6 | Shahkot | Jalandhar | 3 | 3 | 0.089 | 986 |
| 7 | Dharamkot | Moga | 3 | 3 | 0.035 | 494 |
| 8 | Zira | Firozpur | 3 | 2 | 0.039 | 768 |
| 9 | Patran | Patiala | 3 | 1 | 0.139 | 816 |
| 10 | Fazilka | Firozpur | 2 | 2 | 0.068 | 1,111 |

56 of 91 tehsils flooded > 1 % in at least one late season; 34 exceeded 2 %.
Sultanpur Lodhi (Beas–Sutlej confluence), Shahkot (the 2019 Sutlej breach block),
and Moonak (Ghaggar) are the textbook chronic-flood blocks — recovered
bottom-up, purely from GFM recurrence.

## 2025 impact — top tehsils

Top-5 by RF-flooded area (of `data/tehsil_flood_stats_2025.csv`):

| tehsil | district | RF ha | crop-flooded ha | RF frac | crop ₹ VaR |
|---|---|---:|---:|---:|---:|
| Firozpur | Firozpur | 6,452 | 5,697 | 5.07 % | ₹0.86 bn |
| Sultanpur Lodhi | Kapurthala | 4,733 | 4,028 | 10.75 % | ₹0.61 bn |
| Ajnala | Amritsar | 3,810 | 3,322 | 3.65 % | ₹0.50 bn |
| Zira | Firozpur | 3,637 | 2,585 | 4.89 % | ₹0.39 bn |
| Khadur Sahib | Tarn Taran | 2,739 | 2,149 | 6.71 % | ₹0.32 bn |

(Dhar Kalan, Gurdaspur ranks high on RF ha but low on crop — it is the Shivalik
foothill/Kandi block, mostly non-cropland, physically consistent.)

## Reconciliation sanity (tehsil vs district)

Summing all 91 tehsils recovers **95 %** of the district-level statewide 2025
totals: RF 49,628 ha vs 52,223 ha (−5.0 %), crop 34,317 ha vs 36,195 ha (−5.2 %).
Interior districts match near-exactly (Kapurthala 6,590 vs 6,597 ha); the whole
gap is river-corridor flood in **border ADM3 units the state-clip/≥50 % rule
trims** (Firozpur −10 %, Gurdaspur −9 % — both Pakistan-border, where the Sutlej/
Ravi flood hugs the boundary). This is a two-vintage boundary effect, not a decode
error: the district product (datameet polygons) stays the authoritative statewide
total; the tehsil product is its within-state disaggregation, each tehsil's own
ha/fraction exact for its clipped area.

## Module API (`sailaab.tehsils`)

```python
normalize_tehsil_name(name) -> str          # tidy shapeName; -I/-II kept distinct
overlap_fraction(geom, region) -> float      # area(geom ∩ region)/area(geom), 0..1
assign_district(tehsil_geom, [(name, geom)]) -> (name, fraction)   # argmax overlap
load_tehsils(path=DEFAULT_GEOJSON, sort=True) -> list[(tehsil, district, geom_dict)]
```

## Reproduce
```
python pipeline/fetch_tehsils.py                 # -> data/punjab_tehsils.geojson (91)
python -m pipeline.tehsil_stats \
    --gfm-dir data/gfm --raster-dir data/rasters  # -> 3 CSVs + atlas PNG
python -m pytest tests/test_tehsils.py -q          # 15 tests
```
(The per-day GFM tifs and RF rasters are gitignored; point `--gfm-dir`/
`--raster-dir` at wherever they live in a fresh checkout.)
