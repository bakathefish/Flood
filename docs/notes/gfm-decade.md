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
| 2019 | 46 | 2019-06-19 (911) | Sutlej-breach days present: Aug-18 215 km², Aug-23 169 km² (C3 window signal); daily sum 6,064 km² |
| 2020 | 46 | 2020-06-25 (1,868) | late-June max (paddy window); daily sum 7,207 km² |
| 2021 | 47 | 2021-06-21 (1,569) | late-June max (paddy window); daily sum 7,999 km² |
| 2022 | 47 | 2022-06-20 (1,718) | late-June max; daily sum 13,216 km² |
| 2023 | 49 | 2023-07-09 (2,795) | Jul-9 max is the REAL Jul-2023 Sutlej/Ghaggar event (coincides with paddy tail); daily sum 20,449 km² |
| 2024 | 47 | 2024-06-21 (1,304) | late-June max; daily sum 5,109 km² |
| 2025 | 53 | 2025-06-16 (2,703) | most active days of the decade; daily sum 27,281 km²; Aug-27 flood day = 2,039 km² |

Fetch COMPLETE 2026-07-21: 1,177/1,177 day-slots probed, 467 flood-active days -> 467 per-day
tifs; tif counts match active-day counts for every season.

## ACTUALS (aggregate run 2026-07-21)

Per-season **union** (any covered day, minus reference water), full season and calibrated
late-season (days >= Jul 25, past paddy transplant):

| season | active days | full-season union km² | late-season (≥Jul 25) days | late-season union km² |
|---|---|---|---|---|
| 2015 | 17 | 1,127.6 | 11 | 278.1 |
| 2016 | 25 | 2,901.9 | 18 | 1,209.4 |
| 2017 | 46 | 10,240.6 | 28 | 465.0 |
| 2018 | 43 | 6,755.8 | 25 | 225.0 |
| 2019 | 46 | 4,589.4 | 31 | 1,046.4 |
| 2020 | 46 | 5,194.0 | 28 | 267.2 |
| 2021 | 47 | 5,794.3 | 27 | 567.1 |
| 2022 | 47 | 9,182.1 | 29 | 446.3 |
| 2023 | 49 | 10,787.7 | 30 | 1,848.5 |
| 2024 | 47 | 3,651.4 | 30 | 464.3 |
| **2025** | **53** | **16,108.0 (#1)** | **33** | **3,306.3 (#1)** |

**Paddy-transplant signal, quantified** (statewide flooded-ha per window, mean across the 11
years): Jun-15 window 150,848 ha; Jun-25 172,684; Jul-05 78,774; Jul-15 38,441 — then a ~20x
collapse once transplanting ends: Jul-25 8,997; Aug-04 4,705; Aug-14 9,366; Aug-24 8,974;
Sep-03 7,589; Sep-13 3,042; Sep-23 1,820. The four Jun-15..Jul-15 windows are dominated by
agronomic inundation in every year; the seven Jul-25+ windows carry the flood climatology.
Hence the committed late-season companions (`*_late_season.*`).

## CHECKPOINT VERDICTS (against the pre-declared bands)

- **C1 — 2025 statewide max: PASS.** 2025 union = 16,108.0 km² = decade max (2nd: 2023 at
  10,787.7) and ≥ 2,500 ✓. Robust to the paddy caveat: 2025 is also #1 on the late-season
  union (3,306.3 vs 2023's 1,848.5). The pre-declared *expected band* (≈2,700–2,900 km²) was
  wrong — it was scaled from the 10-day event union and ignored the paddy component of a
  full-season union; the declared PASS criterion (max AND ≥2,500) is met.

- **C2 — 2023 Sangrur NRSC anchor: FAIL.** Covering window [2023-08-14, 2023-08-24) Sangrur
  flooded_ha = **1,551 ha** vs NRSC 7,121 ha; declared band [3,560, 10,682] -> outside (21.8 %
  of anchor). Mechanism (per-day trace): the anchor date **2023-08-18 has no GFM/S1
  acquisition** (probe = 0); the adjacent passes Aug-17/Aug-19 covered only ~50/8 km² of the
  bbox, and the window's one large acquisition (Aug-22, 619 km² statewide) was a **western
  swath over the Sutlej belt** (Firozpur/Kapurthala/Tarn Taran) that does not image Sangrur.
  The pipeline demonstrably captures the same 2023 Ghaggar disaster when S1 looks at it:
  Sangrur **33,771 ha** in [06-25,07-05), 14,971 ha in [07-15,07-25), 11,706 ha in
  [07-25,08-04); Patiala 64,374 ha in [07-05,07-15). Verdict: master-plan gate FAIL as
  declared, root-caused to S1 revisit/swath geometry on the anchor date, not to the decode or
  aggregation (which reproduce documented values exactly elsewhere).

- **C3 — 2019 Sutlej breach: PARTIAL.** Signal condition PASS: in the breach window
  [2019-08-14, 2019-08-24), Jalandhar 4,358 ha (fraction 0.0167 = **35x** its decade-median
  window fraction 0.00048) and Kapurthala 3,633 ha (0.0218 = **19x** median 0.00115) — a
  clear, correctly-located, correctly-timed detection. Rank sub-clause FAIL: 2019's season
  union ranks #8/11 on the (paddy-dominated) full-season metric and #4/11 late-season, not
  top-3 as pre-declared.

- **C4 — quiet baseline year: PARTIAL.** On raw full-season unions no year sits below the
  pre-declared 400 km² (minimum: 2015 at 1,127.6) — the threshold ignored the paddy floor ->
  FAIL as literally declared. On the calibrated late-season metric the quiet years are
  unambiguous: 2018 = 225.0, 2020 = 267.2, 2015 = 278.1 km² (all < 400, bottom-3), and the
  max/min season ratio is 14.7x (3,306.3 / 225.0). The named candidate (2016) was wrong —
  2016 is #3 late-season (1,209.4 km², a genuine Aug-2016 river signal).

- **C5 — frequency raster sanity: PASS.** Counts ∈ [0, 11], max = 11 >= 3 ✓. The RAW
  repeat-victims top-5 (Sangrur, Firozpur, Tarn Taran, Barnala, Faridkot) is
  paddy-contaminated (Barnala/Faridkot have no river). The **late-season** top-8 is entirely
  river-corridor/Ghaggar: Kapurthala (5 of 11 seasons > 1 %, 3 > 2 %), Firozpur, Tarn Taran,
  Gurdaspur, Patiala, Sangrur, Jalandhar, Amritsar — the recurrence concentrates in the
  Ravi/Beas/Sutlej/Ghaggar belts as required.

**2025 spot-check** (forecaster table): windows [08-24,09-03) + [09-03,09-13) carry
Gurdaspur 20,680 ha (5.7 %), Firozpur 12,443/15,170 ha, Kapurthala 5,424/8,554 ha (5.1 %),
Amritsar, Tarn Taran, Jalandhar — the documented Ravi/Beas/Sutlej pattern of
`docs/notes/gfm-wms.md`.

Products committed: `data/gfm_district_window_fractions_2015_2025.csv` (2,420 rows =
11 y x 11 w x 20 districts), `data/flood_frequency_districts.csv`,
`data/flood_frequency_districts_late_season.csv`, `atlas/frequency_2015_2025.png`,
`atlas/frequency_2015_2025_late_season.png`. Not committed (gitignored):
`data/rasters/flood_frequency_2015_2025{,_late_season}.tif`, 467 per-day tifs under
`data/gfm/<year>/`, `data/gfm/_decade_progress.csv` (resume state).

_remaining seasons + union km² + checkpoint verdicts pending aggregate run._
