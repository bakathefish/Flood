# Login-free Sentinel-1 via Microsoft Planetary Computer (anonymous STAC)

Goal: a Tier-A flood change-detection mask for the 2025 Punjab flood **without
Google Earth Engine and without any account** — proving (or disproving) that
Microsoft Planetary Computer's (MPC) STAC API is usable anonymously.

## Verdict: WORKS anonymously

`pystac_client.Client.open(STAC, modifier=planetary_computer.sign_inplace)` with
**no subscription key** signs asset hrefs (Azure blob SAS token) and both
searching and COG reads succeed. No 401/403 anywhere on the search or the signed
GET. Signing endpoint used: `https://planetarycomputer.microsoft.com/api/sas/v1/sign`.

- STAC root: `https://planetarycomputer.microsoft.com/api/stac/v1`
- Collection: `sentinel-1-rtc` (terrain-corrected gamma0, **linear power**;
  convert to dB with `10*log10(clip(x, 1e-6, None))`). Assets: `vv`, `vh`,
  `tilejson`, `rendered_preview`.
- Fallback collection available: `sentinel-1-grd`.

### Asset / read facts (verified from live metadata)
- Native CRS of RTC assets over Punjab: **EPSG:32643 (UTM 43N)** — the whole
  Punjab bbox lies in this single UTM zone, so no cross-zone mosaicking. Read/warp
  target grid is UTM 43N; pixel area is constant (`res*res` m²).
- dtype `float32`, **nodata `-32768`** (NOT NaN). The runner maps nodata and any
  non-positive linear power to NaN before compositing.
- COGs carry overviews `[2, 4, 8, 16, 32, 64]`; `rasterio.WarpedVRT` at the target
  resolution pulls only a downsampled window over the wire (bandwidth stays small).
- GDAL gotcha: do **not** set `CPL_VSIL_CURL_ALLOWED_EXTENSIONS=.tif` — RTC assets
  end in `.tiff` and the filter silently rejects them ("does not exist in the file
  system"). Effective env: `GDAL_DISABLE_READDIR_ON_OPEN=EMPTY_DIR`,
  `GDAL_HTTP_MULTIRANGE=YES`, `GDAL_HTTP_MERGE_CONSECUTIVE_RANGES=YES`, `VSI_CACHE=TRUE`.

## Scene inventory — Kapurthala bbox (75.05, 31.07, 75.70, 31.66)
Windows mirror `sailaab/config.py`: PRE = 2025-07-01..08-10, FLOOD = 2025-08-25..09-06.

| Window | Total items | by (orbit_state, relative_orbit) |
|---|---|---|
| PRE   | 23 | ascending/27: 9, descending/34: 7, descending/136: 4, ascending/100: 3 |
| FLOOD | 5  | descending/34: 2, ascending/27: 2, ascending/100: 1 |

Orbits present in BOTH windows: ascending/27, descending/34, ascending/100
(descending/136 has no flood-window scene). Runner picks the orbit with the best
**covered area** in both windows (coarse probe), not merely scene count.

## Architecture (repo convention)
- Pure array logic: `sailaab/sar_local.py` — `to_db`, `median_composite`,
  `tier_a_mask`, `sieve_mask`, `flooded_hectares`, `best_common_orbit`.
  Test-first in `tests/test_sar_local.py` (16 synthetic-array tests).
- IO / STAC runner: `pipeline/local_tier_a.py` (thin CLI, mirrors other
  `pipeline/*.py`). `--aoi kapurthala|punjab --res 30 --orbit-mode single|state`.
- Tier-A rule (from `sailaab/config.py`, identical to `gee/02`):
  `flood = (ΔVV < -3 dB) & (VV_flood < -15 dB) & (VV_pre >= -15 dB)`, then sieve
  connected components < 10 px (8-connectivity). ΔVV = flood − pre, median composites.

## New dependencies (user-level `pip install --user`)
| Package | Version |
|---|---|
| pystac-client | 0.9.0 |
| planetary-computer | 1.0.0 |
| rioxarray | 0.22.0 |
| pystac | 1.15.1 |
| pyproj | 3.7.2 |
(rasterio 1.5.0, scipy 1.17.0, numpy 2.4.1, xarray 2026.2.0, matplotlib already present.)

Not added to `requirements.txt` per task constraint — recorded here only.

## Dataset citation
Microsoft Planetary Computer, **Sentinel-1 Radiometrically Terrain Corrected
(RTC)** collection (`sentinel-1-rtc`), derived from Copernicus Sentinel-1 GRD.
Contains modified Copernicus Sentinel data 2025, processed by ESA and by Catalyst /
Microsoft for the Planetary Computer. Accessed 2026-07-21 via the anonymous STAC
API. License: Copernicus Sentinel data — free and open (CC-BY-like attribution).

## Performance notes (anonymous tier, home bandwidth, IN region -> Azure West Europe)
- Windowed WarpedVRT reads of the Kapurthala bbox at 60 m: 16-80 s per scene,
  8-way threaded (ThreadPoolExecutor; one dataset handle per thread).
- A full run at 30 m plus a per-orbit coverage probe was too slow on this link;
  the practical recipe is: pick the orbit from scene counts (or a coarse probe),
  pass `--orbit ascending:27` to skip probing, and work at 60 m (Kapurthala) /
  ~90 m (statewide). Working res only mildly affects Tier-A area statistics
  because the mask thresholds operate on composited dB values.
- Anonymous throttling shows up as variable per-scene read time (16 s -> 80 s),
  not as 401/403 errors. No request was ever rejected outright.

## Results

### Kapurthala bbox (75.05, 31.07, 75.70, 31.66) — verification AOI
Command: `python -m pipeline.local_tier_a --aoi kapurthala --res 60 --orbit ascending:27`

| Quantity | Value |
|---|---|
| Scenes (PRE / FLOOD) | 23 / 5 total; used ascending/27: 9 / 2 |
| Working grid | 1034 x 1094 @ 60 m, EPSG:32643 |
| Valid coverage (both windows) | 89.3 % |
| VV median (pre / flood) | -9.39 / -8.50 dB |
| **Flooded area (Tier-A)** | **6,162.8 ha** |
| % of bbox (407,231 ha) | 1.51 % (1.70 % of valid pixels) |
| Runtime | 393 s |

Quicklooks: `atlas/checks/local_tierA_kapurthala_{pre_db,flood_db,mask_overlay}.png`;
mask GeoTIFF: `data/rasters/local_tierA_kapurthala_tierA_floodmask.tif` (not committed).

Visual check: the mask concentrates along the Beas corridor (NW) and the
Sutlej / Harike belt (S) — spatially coherent, matching NDEM's Aug 19 2025
flood mapping for Kapurthala. The 1.5 % figure sits at the low end of the
plausible 2-20 % band because (a) the only ascending/27 flood pass is
2025-09-03, ~2 weeks after peak, well into recession, and (b) this route uses a
median flood composite (the GEE Tier-A script uses `.min()`, which is darker /
more inclusive). Both choices are conservative, not degenerate.

### Punjab statewide bbox (73.85, 29.53, 76.95, 32.60)
Command: `python -m pipeline.local_tier_a --aoi punjab --res 90 --orbit-mode state --orbit descending`

| Quantity | Value |
|---|---|
| Scenes (PRE / FLOOD) | 65 / 18 total; used descending all-tracks (34+107+136): 35 / 10 |
| Working grid | 3338 x 3800 @ 90 m, EPSG:32643 |
| Valid coverage (both windows) | 64.1 % of the rectangle (see hole note) |
| VV median (pre / flood) | -8.08 / -7.69 dB |
| **Flooded area (Tier-A, raw, covered area only)** | **61,499 ha** (lower bound) |
| % of bbox (10.27 M ha) | 0.60 % (0.93 % of valid pixels) |
| Runtime | 2,734 s (45.6 min) |

Quicklooks: `atlas/checks/local_tierA_punjab_{pre_db,flood_db,mask_overlay}.png`;
GeoTIFF: `data/rasters/local_tierA_punjab_tierA_floodmask.tif` (not committed).
No crop mask is available locally, so this is raw flooded area over all land
cover — not comparable 1:1 with the official 148k-175k ha *crop* figure.

**Known gap (documented, fix committed):** the two 2025-09-04 descending/34
frames covering central Punjab were dropped mid-run because the anonymous SAS
token signed at search time expired after ~45 min (GDAL surfaces the 403 as
"not recognized as being in a supported file format"). The flood composite
therefore has a central N-S stripe of nodata that includes most of the
Beas-Sutlej flood belt — the 61,499 ha is a **floor**, and it excludes e.g. the
~6,163 ha independently mapped in the Kapurthala bbox. `read_asset` now
re-signs hrefs on retry; a statewide rerun with the fix is one command.

## Verdict details / gotchas recap
1. Anonymous signing works end-to-end (search + SAS + blob GET). No key, no
   login, no 401/403 for compliant requests.
2. Anonymous SAS tokens expire ~45-60 min after signing — re-sign per read on
   long runs (fixed in `pipeline/local_tier_a.py`).
3. RTC assets are `.tiff` — do not set `CPL_VSIL_CURL_ALLOWED_EXTENSIONS=.tif`.
4. RTC nodata is -32768.0 (not NaN) and data is linear power — floor at 1e-6
   before `10*log10`.
5. Throttling is time-variable: reads of the same window size ranged 8 s to
   1,678 s within one run. Budget wall-clock generously; bytes stay modest
   (both runs together ≈ 1 GB estimated, well under a 3 GB budget).

## Approx download totals
- Kapurthala 60 m run: 11 windowed scene reads ≈ 70-120 MB.
- Statewide 90 m run: 45 windowed scene reads ≈ 700-900 MB.
- Probes/aborted 30 m attempt: ≈ 100 MB.
- Total ≈ 0.9-1.1 GB (estimates from window/overview sizes; GDAL does not
  report exact transfer counts).
