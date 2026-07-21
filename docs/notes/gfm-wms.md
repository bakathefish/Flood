# GFM observed flood extent via the keyless GloFAS WMS

How the Copernicus **Global Flood Monitoring (GFM)** observed-flood-extent masks for the
2025 Punjab flood are pulled for validation, and the exact decode rule. Companion to
`docs/notes/validation-recon.md` §4 (which established that the layers are reachable
without a login). Fetched 2026-07-21.

- **Endpoint:** `https://ows.globalfloods.eu/glofas-ows/ows` (WMS 1.3.0, no key, no login).
- **Pure logic:** `sailaab/gfm.py` (PNG→binary decode, tiling, stitch, union, area) — unit-tested in `tests/test_gfm.py`.
- **IO / fetch:** `pipeline/fetch_gfm.py` (`requests` + `rasterio`). Run: `python -m pipeline.fetch_gfm`.
- **Rasters:** `data/gfm/` (gitignored, not committed). Quicklook: `atlas/checks/gfm_union_20250827_0905.png` (committed).

## Request recipe

`GetMap` **requires** an empty `STYLES=` (omitting it returns an OGC `ServiceException`, not
an auth error — proving there is no login gate) and the layer's advertised `EPSG:3857`:

```
service=WMS  version=1.3.0  request=GetMap
layers=gfm_observed_flood_extent_group_layer  styles=            (empty, mandatory)
crs=EPSG:3857  bbox=<minx,miny,maxx,maxy>  width=..  height=..
format=image/png  transparent=true  time=2025-08-27T00:00Z
```

WMS 1.3.0 + `EPSG:3857` uses **x,y (easting,northing)** axis order, so `bbox = minx,miny,maxx,maxy`.

## Layers (exact names, from GetCapabilities)

| Layer | Use |
|---|---|
| `gfm_observed_flood_extent_group_layer` | observed flood extent (the signal) |
| `gfm_reference_water_mask_group_layer` | reference (permanent) water — subtracted from the union |
| `gfm_sentinel_1_footprint` | per-day S1 acquisition footprint (coverage indicator) |

Other published GFM layers (unused here): `gfm_observed_water_extent_group_layer`,
`gfm_affected_population`, `gfm_affected_landcover`, `gfm_uncertainty_values_group_layer`,
`gfm_advisory_flags_group_layer`, `gfm_exclusion_mask`, `gfm_sentinel_1_schedule`.

**TIME dimension:** `units=ISO8601`, extent `2011-01-01T00:00Z/<today>/PT24H` (daily),
`nearestValue=0` → you must hit an exact daily timestamp (`YYYY-MM-DDT00:00Z`). Layers are
`queryable=0`, so there is **no GetFeatureInfo** and **GetLegendGraphic is a 400** on these
cascaded group layers — the palette below was sampled directly from rendered GetMap PNGs.

## Palette decode rule (the important part)

The `..._group_layer` returns a **styled RGBA PNG**, not class values, and paints several
things on top of each other. "Any non-transparent pixel = flood" is **wrong** — it captures
swath outlines and burnt-in text. Sampled palette (2026-07-21):

| Rendered colour (R,G,B) | Meaning | Decode |
|---|---|---|
| **pink `(232, 76, 120)`** | observed flood extent fill | **FLOOD ✓** |
| red `(192, 0, 0)` | S1 swath / granule outline (thin lines) | reject |
| orange `(255, 118, 13)` | burnt-in acquisition-time label (text) | reject |
| green `(112, 173, 71)` | minor overlay class | reject |
| blue `(0, 75, 114)` | reference water fill | reject / subtract |

**Rule:** a pixel is flood iff its colour is within ±48 per channel of the flood pink **and**
alpha ≥ 96. The pink is cleanly separable — red/orange have `B ≤ 13` (pink `B=120`), green
has `R=112` (pink `R≥180`), blue has `R=0`. Reference water uses the same rule on `(0,75,114)`.
See `sailaab.gfm.color_mask` / `flood_mask` / `ref_water_mask`. Flood polygons render as solid
pink (`alpha=255`) even at ~100 m; only thin anti-aliased edges are partial-alpha, so the
result is insensitive to the exact `alpha_min`.

## Grid, tiling, area

Punjab bbox `(73.85, 29.53, 76.95, 32.60)` (lon/lat; matches `PUNJAB_BOX` in
`pipeline/fetch_rain.py`) → EPSG:3857 `(8220944, 3443278, 8566035, 3842330)`. Rendered at
**~100 m** (3451 × 3991 px), tiled at ≤2048² (4 tiles/day) and stitched. Area uses the
Web-Mercator **cos²(lat)** correction applied per pixel row (3857 inflates linear scale by
1/cos(lat); true pixel area = projected area × cos²(lat)), so ~100 m in 3857 is ~86 m ground
at 31 °N. bbox ground area = 101,009 km².

## Coverage (daily, 2025-08-27 … 2025-09-05)

S1 revisit means not every day has a pass. Coverage from `gfm_sentinel_1_footprint`:

| Day | S1 footprint % of bbox | Flood km² |
|---|---|---|
| 2025-08-27 | 65.0 | 2039 |
| 2025-08-28 | 14.2 | 643 |
| 2025-08-29 | 0.0 | — (no S1 pass) |
| 2025-08-30 | 42.3 | 32 (large swath, little flood) |
| 2025-08-31 | 0.0 | — (no S1 pass) |
| 2025-09-01 | 1.8 | 51 |
| 2025-09-02 | 0.0 | — (no S1 pass) |
| 2025-09-03 | 57.2 | 360 |
| 2025-09-04 | 80.2 | 1387 |
| 2025-09-05 | 0.0 | — (no S1 pass) |

**6 days with coverage** (27, 28, 30 Aug; 1, 3, 4 Sep); **4 empty** (29, 31 Aug; 2, 5 Sep).

## Result

Union flood (flood on any covered day) = 2,795 km²; minus reference water (27 km² removed) =
**2,768 km² = 382,488 px @ 100 m = 2.74 % of the bbox**. Reference-water subtraction is small
because GFM "observed flood extent" already excludes permanent water — it is a belt-and-braces
step. The spatial pattern hugs the **Ravi** (NW, Gurdaspur/Amritsar), **Beas** (Pong→Harike),
and **Sutlej** (Harike→Ferozepur/Fazilka SW, and upstream toward Rupnagar/Ludhiana) belts,
converging at the Harike confluence, with the dry interior plains essentially flood-free —
consistent with a river-corridor flood.

## Citation

GFM observed flood extent / reference water mask — **Global Flood Monitoring (GFM), Copernicus
Emergency Management Service (CEMS)**, served by the **GloFAS Open Web Service**
(`https://ows.globalfloods.eu/glofas-ows/ows`), keyless WMS 1.3.0, accessed **2026-07-21**.
GFM is produced from Copernicus Sentinel-1 data. The WMS `GetCapabilities` advertises **no Fees
and no AccessConstraints** element; CEMS/Copernicus data is provided under the **free, full and
open Copernicus data policy** (Regulation (EU) No 377/2014; attribution required, CC-BY-4.0
equivalent). Suggested credit: *"Contains modified Copernicus Emergency Management Service —
Global Flood Monitoring information, 2025."*
