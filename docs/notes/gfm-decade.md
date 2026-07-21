# GFM decade flood atlas 2015-2025 — pre-declared checkpoints + run log

Decade batch of Copernicus **Global Flood Monitoring (GFM)** observed-flood-extent, pulled
from the keyless GloFAS WMS (recipe: `docs/notes/gfm-wms.md`). Every monsoon season
Jun 15 – Sep 30, years 2015–2025, Punjab bbox `(73.85, 29.53, 76.95, 32.60)`, ~100 m EPSG:3857.

Products:
- `data/gfm_district_window_fractions_2015_2025.csv` — forecaster target (per district × 11 windows × 11 years).
- `data/rasters/flood_frequency_2015_2025.tif` — per-pixel count of seasons flooded 0–11 (gitignored).
- `atlas/frequency_2015_2025.png` — committed quicklook of the frequency raster.
- `data/flood_frequency_districts.csv` — "repeat victims" per-district recurrence table.

Pure logic: `sailaab/frequency.py` (window assignment, season-union frequency count, repeat-victim
summary) — unit-tested. IO / WMS: `pipeline/fetch_gfm_decade.py`.

## Fetch design (why a flood-probe gate, not a footprint gate)

The `gfm_sentinel_1_footprint` layer is **unreliable for archived dates**: a footprint sweep on
2026-07-21 returned exactly `100.0%` for most 2015–2021 mid-monsoon days (a `nearestValue`
fallback to a recent full-coverage footprint) yet `0.0%` for 2023-08-18. So footprint cannot gate
the archive. The **flood layer itself has clean exact-day semantics** (verified 2026-07-21):
`2020-02-15`, `2015-01-10`, `2023-08-18`, `2025-08-29` all return **0** flood px (no
nearest-fallback), while `2025-08-27` returns flood. Therefore each day is gated by a single
1024-px flood probe over the whole bbox (~2–3 s); the full-res 4-tile fetch runs only when the
probe is non-empty. "Coverage" is reported as **flood-active days per season** (days the flood
layer carried observed flood), which is what the products actually use.

## Paddy-transplant signature (identified mid-run, 2026-07-21)

The 2017-06-30 "flood" (4,815 km²) blankets **Moga (984 km² ≈ 44 % of the district), Bathinda
(no river), Sangrur, Ludhiana** — the central paddy belt, not river corridors — while true events
(2023-08-22, 2015-07-10) hug the Sutlej/Ghaggar corridors. Punjab transplants rice into
deliberately inundated fields ~mid-June to mid-July; S1 sees those as water, and the GFM archive
carries them as observed flood in at least the early (pre-operational-era) years. Mitigation
decided mid-run: deliver the products exactly as specified (full-season unions), but (a) the
per-window forecaster table separates the Jun-15..Jul-15 windows where the artifact lives, and
(b) post-fetch the run log records a per-window cross-year comparison plus, if C1 fails on raw
unions, a parallel "core flood season" (post-Jul-15) union ranking as the calibrated comparison.
Late-August checkpoint anchors (C2, C3) are unaffected by the artifact.

## PRE-DECLARED checkpoints (written BEFORE the pull; verification discipline)

Expected bands, to be confirmed against actuals after the run. A checkpoint FAILS if the actual
lands outside its band.

- **C1 — 2025 is the statewide-max season.** The 2025 season union (flood on any covered day,
  minus reference water) must exceed every other season's union. Expected 2025 union ≈ 2,700–2,900 km²
  (2025-08-27..09-05 alone was 2,768 km², `docs/notes/gfm-wms.md`); full season Jun 15–Sep 30 ≥ that.
  PASS iff `union_km2(2025) == max over 2015–2025` **and** 2025 union ≥ 2,500 km².

- **C2 — 2023 Sangrur anchor (master-plan gate).** NRSC mapped Sangrur at **7,121 ha** for the
  Aug-2023 Ghaggar event (`config.SANGRUR_2023_NRSC_HA`). The covering window is
  **Window 6 = [2023-08-14, 2023-08-24)** (flood-active probe days 14,17,19,21,22 confirmed).
  PASS iff Sangrur `flooded_ha` in that window ∈ **[3,560, 10,682] ha** (±50 %). Patiala and
  Rupnagar should also show non-trivial flood in the Aug-2023 windows (> a few hundred ha each).

- **C3 — 2019 Sutlej breach.** The Aug-2019 Sutlej overflow flooded Jalandhar/Kapurthala/Ferozepur
  bet areas (~Aug 18–25 2019). PASS iff, in the Aug-2019 window(s), **Jalandhar and Kapurthala**
  each show flooded fraction clearly above their own decade-median window (elevated signal present),
  with the 2019 season union a clear top-3 season statewide.

- **C4 — quiet baseline year.** A non-event year (candidate 2016) must sit near baseline: season
  union small and well below 2025/2023/2019. PASS iff the identified quiet year's union < 400 km²
  and ranks in the bottom half of seasons.

- **C5 — frequency raster sanity.** Per-pixel season count ∈ [0, 11]; max ≥ 3 somewhere in the
  Ravi/Beas/Sutlej corridors; repeat-victim districts concentrate in the river belts
  (Gurdaspur, Amritsar, Ferozpur, Kapurthala, Ludhiana, Rupnagar, Sangrur/Patiala on the Ghaggar).
  PASS iff max season-count ≥ 3 and the top repeat-victim districts are river-corridor districts.

## RUN LOG (actuals appended per season during the pull)

**Resume state:** `data/gfm/_decade_progress.csv` (one row per day-slot: `day,probe_px,active,
full_px,flood_km2`). The `fetch` command skips any day already present there, so a killed run
resumes with `python -m pipeline.fetch_gfm_decade fetch` (no args = all years). Per-day full-res
masks land in `data/gfm/<YEAR>/`; reference water in `data/gfm/gfm_punjab_refwater.tif`.

**Fetch launched 2026-07-21.** Probe smoke-checks reproduced documented values exactly
(2025-08-27 = 2,039 km²; 2023-08-22 = 619 km²). Per-season actuals + checkpoint verdicts are
appended below by `aggregate` once the pull completes.

Per-season fetch checkpoints (active days = days the flood layer carried observed flood;
season-union km² comes from `aggregate` at the end):

| season | flood-active days | max single day (km²) | note |
|---|---|---|---|
| 2015 | 17 | 2015-07-10 (502) | genuine mid-July event; daily sum 1,289 km² |
| 2016 | 25 | 2016-07-09 (757) | NOT quiet — early-July signal; daily sum 3,888 km² (C4 quiet-year candidate will be re-identified from unions) |
| 2017 | 46 | 2017-06-30 (4,815) | ANOMALY FLAG: max day >2x the 2025 peak day; daily sum 14,501 km². Late-June timing suggests possible S1 paddy-transplant confusion (fields deliberately inundated) in the GFM archive — quicklook comparison scheduled post-fetch. |
| 2018 | 43 | 2018-07-02 (1,535) | early-July max again (paddy window); Sep-2018 known event should appear in late windows; daily sum 9,541 km². Fetch restarted mid-2018 as detached PID 34384 (wrapper killed); resume clean. |

_remaining seasons + union km² + checkpoint verdicts pending aggregate run._
