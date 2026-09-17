# Local Inflow Between the Dams and Harike (roadmap item 5)

> **For agentic workers:** Executed inline by a single writer, tests first, smallest implementation that passes, then the next task. Commits as the repository's own author with no attribution trailer (the Flood repository rule). Every number in the docs comes from `outputs/` through `punjabflood report`; nothing is typed by hand.

**Goal:** The routed arrivals at the WRD control points gain the runoff of the land between the dams and the head works (the Swan and Sirsa on the Sutlej, the Chakki and the Kandi torrents on the Beas, the plains above Harike), so that the Dhilwan and Harike arrivals stop being a pure translation of the dam release. The event test then says what that term is worth on the 2023 and 2025 peaks, and the daily product carries it.

**What the record allows:** no gauge history exists for the intermediate land, so no coefficient can be fitted on it. The local term therefore transfers a dam catchment's calibrated response (coefficient, wetness dependence, lag weights) to the intermediate sub-basins with their own area and their own IMD rain, and the verification reports the term under the transferred response of Pong (the best-determined fit, r2 0.78, foothill catchment) and, as the sensitivity, under Ranjit Sagar's (the lowest coefficient). No base flow is added: the term is a lower bound on the local contribution, and the report says so.

**Spec:** `docs/roadmap.md` item 5 (2026-09-05), the scoping numbers recorded on 2026-09-05 (Dhilwan sub-basin 4080729700, Harike 4080730060, Beas local 2 sub-basins 3,506 km2, Harike local 19 sub-basins 17,369 km2), and this session's split of the 19 into three sets by the control point they drain to.

---

## The three local catchments

| name | definition (HydroBASINS level 8) | sub-basins | km2 | receives it |
|---|---|---|---|---|
| Sutlej local | upstream of the sub-basin holding Ropar Head Works and Railway Bridge Phillaur (4080735710), minus Bhakra's set | 2 | 3,968 | Ropar, Phillaur, Harike |
| Beas local | upstream of the sub-basin holding Dhilwan (4080729700), minus Pong's set | 2 | 3,506 | Dhilwan, Harike |
| Harike local | upstream of the sub-basin holding Harike Head Works (4080730060), minus Bhakra, Pong, Sutlej local and Beas local | 15 | 9,895 | Harike |

The three are disjoint and sum to the 19 sub-basins (17,369 km2) scoped on 2026-09-05. All three lie inside the IMD grid, so the observed record covers them fully. Local runoff reaches its control point on the day it runs off (no travel-time table exists for the tributaries; the sub-basins are small next to the 219 and 215 km dam reaches). Ferozepur inherits Harike's sum as before. Naushera Mirthal, just below Pong, receives no local term.

## Tasks

### Task 1: constants
**Files:** `punjabflood/constants.py`, `tests/test_constants.py`
- [x] Test: every local catchment carries a source, its outlet station is a control point, every station it feeds is a control point, every exclusion names a dam or an earlier local catchment, and the transfer dam is a dam. (All tests of this plan live in `tests/test_local_inflow.py`, one module because the term crosses six package modules.)
- [x] `LocalCatchment` dataclass and `LOCAL_CATCHMENTS` (name, river, outlet sub-basin, the station that sub-basin holds with its coordinates and their source, exclusions, stations fed, transfer dam, source, note). Coordinates: Rupnagar, Phillaur and Dhilwan from the Wikipedia article coordinates; the Harike barrage from OpenStreetMap Nominatim (31.1455 N 74.9464 E), because the town's coordinates fall in the next sub-basin downstream.

### Task 2: catchment builder
**Files:** `punjabflood/catchments.py`, `tests/test_local_inflow.py`
- [x] Tests: `build_local` on toy records removes the excluded upstream sets and keeps the rest; GeoJSON round trip keeps the role; the real archive (skipped without it) gives the sub-basin counts and areas in the table above, disjoint from the dam sets and each other, each polygon containing its station's coordinates.
- [x] `Catchment.role` ("upstream" or "local", stored in the GeoJSON); `build_local`; `build_all` builds the dams and Ghaggar points as before, then the locals in `LOCAL_CATCHMENTS` order with exclusions resolved from the sets already built.
- [x] `punjabflood build-catchments` writes the three new GeoJSONs; the five existing files changed only by the new `role` key (checked by parsing both versions).

### Task 3: the local inflow term
**Files:** `punjabflood/inflow.py`, `tests/test_local_inflow.py`
- [x] Tests: `local_inflow_cusecs` on a single rain day over a known area with unit lag weight and no wetness term equals the coefficient times the rain volume, converted to cusec-days, on that day and zero after; the antecedent term raises the coefficient exactly as `coefficient()` does; the forecast variant uses the recent days for lags and wetness and returns one value per forecast day.
- [x] `transferred_params`, `local_inflow_cusecs` (daily series in, daily cusecs out, quick response only), `local_inflow_forecast_cusecs` (recent observed days plus forecast days in, forecast-day cusecs out).

### Task 4: routing
**Files:** `punjabflood/routing.py`, `tests/test_local_inflow.py`
- [x] Tests: with no local term `arrivals` is unchanged; a local series is added on its own day at each station it feeds and nowhere else; Harike's sum includes all three and Ferozepur inherits it twelve hours later; the class is recomputed on the sum.
- [x] `arrivals(releases, local=None, how="max")`.

### Task 5: verification
**Files:** `punjabflood/verify.py`, `punjabflood/cli.py`, `tests/test_local_inflow.py`
- [x] Tests: `routed_next_day_release` passes the local term through; `local_inflow_summary` reads, per event year, the local inflow on the observed peak day, its largest value within three days of it, the routed dam release that day, and the local share of the observed peak.
- [x] `run_verify` writes `local_inflow_daily.csv` (both transfers), the routed series with the local term, `event_timing_local` and `event_timing_local_ranjit_sagar` beside the existing event rows, and `local_inflow_summary` in `results.json` (`verify.local_inflow_series` builds the series).
- [x] `build-rain --only` rebuilds the IMD series for the named catchments without touching the others (and now writes one date format: the first partial rebuild mixed Timestamps with the file's strings and broke `pull-rain-recent`); `pull-rain-recent` gives the three new catchments their 2026 ERA5 days.

### Task 6: the daily product
**Files:** `punjabflood/forecast.py`, `tests/test_local_inflow.py`
- [x] Test: `build_product` with a local catchment's QPF and area adds the local term to the reaches it feeds and records it under `local_inflow`; the Markdown names it.
- [x] `build_product(..., local_areas=None)`: per local catchment with a deterministic QPF (ECMWF IFS where present, else the first model available), the forecast-day local inflow from the transferred response, added at its stations before classification; `run` passes the IMD-covered areas and pulls the local catchments with the IMD weights.

### Task 7: report and docs
**Files:** `punjabflood/report.py`, `docs/design.md`, `docs/roadmap.md`, `docs/data-sources.md`, `README.md`
- [x] Report: the event-timing table gains the rows with the local term under both transfers; a short table of the local inflow on the observed peak days; the paragraph no longer says tributaries are not modelled.
- [x] Design: a paragraph on the land between the dams and the head works (transferred response, no base, lower bound, same-day arrival). Known limits: the local coefficient is not fitted on anything local.
- [x] Roadmap: item 5 moves to "Done in the first round" with what the event test showed; items 6 to 11 renumber.
- [x] Data sources: the HydroBASINS row notes the three local sets.

### Task 8: run, verify, commit
- [x] `build-catchments`, `build-rain --only "Sutlej local,Beas local,Harike local"`, `pull-rain-recent`, `verify`, `report`; full suite green; `ruff check` clean.
- [x] Commit in small steps with the repository's own author and no trailer; push after the daily Action's window or with `git pull --rebase` first.

## Out of scope, stated
- The as-issued hindcast keeps its dam-only form: the archived lead 1 to 7 QPF for the three new catchments is a quota-bound pull (`pull-qpf-archive`) and is queued, not run here.
- No attenuation, no travel time for the tributaries, no local base flow. Each is named in `design.md` as a limit with the data that would lift it.
