# Hazard Tier Implementation Plan (punjabflood 0.1)

> **For agentic workers:** This plan is executed inline by the author (single writer, per the owner's standing preference for cohesion-heavy builds). Steps use checkbox (`- [ ]`) syntax for tracking. Tests first, then the smallest implementation that passes, then the next task. No commits are made by the agent; the owner commits as themselves.

**Goal:** A clean, keyless system that pulls reservoir state, catchment rainfall (observed and forecast) and the state's published routing constants, computes a headroom-exhaustion index per dam, routes forced releases to the WRD control points, and is verified on 38 years of annual peaks, the 2023 and 2025 event chronologies and the 2026 live bulletins.

**Architecture:** One Python package `punjabflood` with pure, testable modules per responsibility (constants, guidebook tables, catchments, Open-Meteo client, rain series, CWC feed, reservoir state and rating, inflow model, headroom index, routing, verification, forecast product, CLI). Data lives under `data/reference/` (committed, sourced tables) and `data/raw/` and `data/cache/` (rebuilt by the CLI, gitignored). Every constant carries its source. The impact tier (district onset probabilities against the document catalogue) is a separate sub-project and is not in this plan.

**Tech Stack:** Python 3.11+, numpy, pandas, requests, shapely, pyproj, pyshp, pypdfium2, scikit-learn, typer, pytest. No API keys anywhere.

**Spec:** `private/rebuild/ISEF-PLAN-v2_2026-09-05.md` in the Sailaab repo (sections 1, 2 and 4), and the probe results recorded in this session (Open-Meteo archive coverage, HydroBASINS sub-basin ids, CWC feed behaviour, BBMB salient-feature documents).

---

## File structure

| path | responsibility |
|---|---|
| `punjabflood/constants.py` | single authority for units, dam register, WRD thresholds, Annexure Z reaches (done) |
| `punjabflood/cwc.py` | CWC daily storage feed puller, resumable, throttled (done) |
| `punjabflood/guidebook.py` | loaders and validators for the digitised WRD tables in `data/reference/wrd/` |
| `scripts/digitise_guidebook.py` | one-off: extraction text to CSV tables, plus page renders for visual verification |
| `punjabflood/catchments.py` | HydroBASINS upstream sets, catchment polygons, area checks, weighted sample grids |
| `punjabflood/openmeteo.py` | cached, quota-aware client for the archive, forecast, ensemble and previous-run endpoints |
| `punjabflood/rain.py` | catchment-mean daily rain and soil moisture (observed) and QPF by lead (forecast) |
| `punjabflood/reservoirs.py` | CWC and BBMB records into one daily state frame; level to storage rating; headroom |
| `punjabflood/inflow.py` | storage-change based runoff calibration and inflow-volume prediction |
| `punjabflood/hei.py` | headroom-exhaustion index and forced-release bound |
| `punjabflood/routing.py` | Annexure Z lags, arrival hydrographs at control points, WRD classification |
| `punjabflood/verify.py` | 38-year peak test, event timing test, 2026 live test; writes `outputs/verification/` |
| `punjabflood/forecast.py` | daily product: pulls, index, routing, JSON and Markdown outputs |
| `punjabflood/cli.py` | typer commands wiring the above |
| `tests/test_*.py` | one test module per package module; network tests marked `network` |
| `docs/design.md`, `docs/data-sources.md`, `docs/verification.md`, `README.md` | public-safe documentation |

---

### Task 1: Constants and unit conversions (done)

**Files:** `punjabflood/constants.py`, `tests/test_constants.py`

- [x] Tests: exact conversions, reach tables sum to the Annexure Z totals, thresholds ordered and boundary classification, every dam constant sourced.
- [x] Implementation written with sources from the WRD guidebook, the BBMB bulletin header, the BBMB Pong EAP, BBMB at a Glance, the CWC feed, the ESDD/DRIP documents and the Punjab WRD dams page.
- [x] Run: `python -m pytest tests/test_constants.py -q` → all pass.

### Task 2: CWC storage feed (done, pull running)

**Files:** `punjabflood/cwc.py`, `tests/test_cwc.py`

- [x] Tests: record normalisation and NA handling, date parsing, pagination, resumable pull with manifest, 429 backoff, 5xx outage budget.
- [x] Implementation; background pull started into `data/raw/cwc/cwc_daily.csv` (1991 to 2026, months 5 to 10). The feed answered 502 for the whole afternoon of 2026-09-05; the puller waits within a six-hour budget.
- [x] Run: `python -m pytest tests/test_cwc.py -q` → all pass.

### Task 2b: IMD gridded rain as the observed record (added during the build)

The ERA5 pull through Open-Meteo was stopped after one hour: archive calls are weighted by data volume and the 222-point, 38-year request would have taken days of quota. The predecessor project holds the IMD 0.25 degree yearwise archive 1961 to 2025 (1.6 GB), linked into `data/raw/imd`. `punjabflood/imdrain.py` computes coverage-weighted catchment means (`weight_imd_km2`; the Tibetan Sutlej is outside the IMD grid and enters through the base flow). ERA5 is used only for the current year (`pull-rain-recent`). Tests in `tests/test_imdrain.py`.

- [x] Coverage weights in the catchment GeoJSON; Bhakra covered 25,762 of 52,765 km2, the others fully.
- [x] `build-rain` 1961 to 2025 running; `pull-rain-recent` for 2026 follows.

### Task 3: Guidebook tables digitised and verified

**Files:** `scripts/digitise_guidebook.py`, `punjabflood/guidebook.py`, `tests/test_guidebook.py`, `data/reference/wrd/{thresholds.csv,peaks_harike_hussainiwala.csv,peaks_ropar.csv,peaks_dhilwan.csv,travel_times.csv,VERIFICATION.md}`

- [x] **Step 1: failing tests**

```python
def test_peak_tables_have_38_contiguous_years():
    for name in ("harike_hussainiwala", "ropar", "dhilwan"):
        df = guidebook.load_peaks(name)
        assert list(df["year"]) == list(range(1988, 2026))

def test_known_cells_match_the_printed_page():
    hk = guidebook.load_peaks("harike_hussainiwala").set_index("year")
    assert hk.loc[2023, "harike_us_cusecs"] == 301061 and hk.loc[2023, "wrd_class"] == "H"
    assert hk.loc[1988, "harike_us_cusecs"] == 600000
    dh = guidebook.load_peaks("dhilwan").set_index("year")
    assert dh.loc[2023, "date"] == "2023-08-17" and dh.loc[2023, "discharge_cusecs"] == 237500
    assert dh.loc[2025, "date"] == "2025-08-31" and dh.loc[2025, "discharge_cusecs"] == 235494
    rp = guidebook.load_peaks("ropar").set_index("year")
    assert rp.loc[2023, "us_cusecs"] == 125722

def test_thresholds_csv_agrees_with_constants():
    df = guidebook.load_thresholds().set_index("station")
    for st, cp in constants.CONTROL_POINTS.items():
        assert df.loc[st, "high_min"] == cp.high_min
```

- [x] **Step 2: run, expect ImportError**
- [x] **Step 3: implement the digitiser** (regex over the extraction text lines 355 to 540 and 5200 to 5230; writes CSVs with a `source_page` column; renders pages 11 to 14 and 118 to PNG under `data/raw/wrd/pages/`)
- [x] **Step 4: verify visually** each rendered page against the CSV (the author reads the PNGs) and record the result per table in `VERIFICATION.md` with the page number and any printed inconsistency (Dhilwan band gap; Annexure Z "3.90 lacs" 1988 note versus 166,000 in the table).
- [x] **Step 5: implement loaders** with schema validation (`year` int, classes in {H, M, L, ""}).
- [x] **Step 6: run tests, pass.**

### Task 4: Catchments from HydroBASINS

**Files:** `punjabflood/catchments.py`, `tests/test_catchments.py`, `data/reference/catchments/*.geojson`

- [x] **Step 1: failing tests (synthetic graph + real data)**

```python
def test_upstream_set_follows_next_down_links():
    recs = {1: {"NEXT_DOWN": 3}, 2: {"NEXT_DOWN": 3}, 3: {"NEXT_DOWN": 4}, 4: {"NEXT_DOWN": 0}, 5: {"NEXT_DOWN": 4}}
    assert catchments.upstream_set(3, recs) == {1, 2, 3}
    assert catchments.upstream_set(4, recs) == {1, 2, 3, 4, 5}

def test_grid_weights_sum_to_polygon_area():
    poly = box(76.0, 31.0, 76.6, 31.5)
    pts = catchments.sample_grid(poly, step_deg=0.25)
    assert abs(pts["weight_km2"].sum() - catchments.geodesic_area_km2(poly)) < 1.0

@pytest.mark.slow
def test_real_catchments_match_published_areas(hydrobasins_available):
    cats = catchments.build_all()
    assert abs(cats["Bhakra"].area_km2 - 56875) / 56875 < 0.10
    assert abs(cats["Pong"].area_km2 - 12560) / 12560 < 0.10
    assert abs(cats["Ranjit Sagar"].area_km2 - 6086) / 6086 < 0.15
    for dam in ("Bhakra", "Pong", "Ranjit Sagar"):
        assert cats[dam].polygon.contains(Point(constants.DAMS[dam].lon, constants.DAMS[dam].lat))
```

- [x] **Step 2: implement** `load_hydrobasins(window)`, `upstream_set`, `Catchment` dataclass (name, outlet id, polygon, area_km2, points DataFrame), `sample_grid` (0.25 degree centres, weight = geodesic area of cell ∩ polygon), `build_all()` for the three dams and the two Ghaggar points, `save_geojson`.
- [x] **Step 3: run tests; write the GeoJSON files.**

### Task 5: Open-Meteo client

**Files:** `punjabflood/openmeteo.py`, `tests/test_openmeteo.py`

- [x] **Step 1: failing tests** using a fake transport: cache hit avoids a second call; 429 with a "minute" reason sleeps and retries; 429 with a "daily" reason raises `QuotaExhausted`; parameter normalisation makes the cache key order-independent.
- [x] **Step 2: implement** `OpenMeteo(cache_dir, sleep=time.sleep)` with `.get(host, path, params)`, JSON disk cache keyed by sha1 of the canonical query, endpoints `archive_daily`, `forecast_daily`, `ensemble_daily`, `previous_runs_hourly`; convenience `points_daily(points, ...)` looping with polite spacing.
- [x] **Step 3: run tests, pass.**

### Task 6: Catchment rain series

**Files:** `punjabflood/rain.py`, `tests/test_rain.py`

- [x] **Step 1: failing tests** on synthetic point tables: weighted mean equals hand computation; missing point on a day is dropped from the weights that day (not treated as zero); QPF frame by lead has one row per (issue_date, target_date, model, lead_days).
- [x] **Step 2: implement** `weighted_mean(frames, weights)`, `era5_catchment_daily(client, catchment, start, end)` (ERA5 precipitation with ERA5-Land soil moisture, default Open-Meteo archive model), `qpf_catchment(client, catchment, model, start, end, leads)` from the previous-run hourly archive, `ensemble_qpf_catchment(client, catchment, days)`.
- [x] **Step 3: run tests; pull ERA5 1988 to date for all catchments into `data/cache/` and write `data/raw/rain/catchment_daily.csv`.**

### Task 7: Reservoir state and rating

**Files:** `punjabflood/reservoirs.py`, `tests/test_reservoirs.py`

- [x] **Step 1: failing tests**: rating is monotone; Bhakra 1666 ft maps within 0.2 BCM of 4.983 and 1676.78 ft within 0.2 BCM of 5.482 (the 2025 press supplement points); bulletin rows load with storage; `headroom_bcm` = capacity − storage, floored at zero.
- [x] **Step 2: implement** `load_cwc(path)`, `load_bulletins(path)`, `Rating.fit(level_m, storage_bcm)` (isotonic on sorted unique levels), `state_frame(dam)` merging CWC daily (to 2025-07-11) and bulletins (2026) with `basis` column, `headroom_bcm`.
- [x] **Step 3: run tests, pass.**

### Task 8: Inflow model

**Files:** `punjabflood/inflow.py`, `tests/test_inflow.py`

Model: `Q_in(t) = b(t) + Σ_k c · w_k · P(t−k) · A` where `b` is a slowly varying base (rolling 15-day median of the storage-change series plus a fixed outflow allowance), `c` the runoff coefficient, `w_k` lag weights over 0 to 3 days summing to one, `A` catchment area. Calibration regresses the detrended daily storage change (BCM/day) on lagged catchment rain volumes (BCM) during filling season, days with no reported spill. Soil-moisture modulation `c = c0 + c1 · (sm − sm_clim)` fitted as a second stage.

- [x] **Step 1: failing tests** on synthetic data generated from the model with known `c`, `w`: recovered `c` within 10 percent; predicted H-day volume equals the sum of daily predictions; zero rain gives base only.
- [x] **Step 2: implement** `calibrate(state_frame, rain_frame, dam) -> InflowParams`, `predict_daily(params, rain_by_day, base_cusecs)`, `volume_bcm(params, rain_forecast, base_cusecs, horizon_days)`.
- [x] **Step 3: run tests; calibrate on CWC 1991 to 2025 (as pulled) and report the fit against the 2026 BBMB inflows in `docs/verification.md`.**

### Task 9: Headroom-exhaustion index

**Files:** `punjabflood/hei.py`, `tests/test_hei.py`

`HEI_H = (V_in,H − headroom − absorption · H) / capacity`, with `absorption` the dam's turbine passing capacity in BCM/day; `forced_release_H = max(0, V_in,H − headroom − absorption · H)` in BCM, converted to a mean cusecs over the days after the reservoir reaches FRL.

- [x] **Step 1: failing tests**: at FRL with inflow above absorption, HEI > 0 and forced release equals inflow minus absorption; with headroom larger than the inflow volume, HEI < 0 and release 0; index is linear in inflow volume.
- [x] **Step 2: implement** `headroom_exhaustion(storage_bcm, capacity_bcm, inflow_volume_bcm, absorption_cusecs, horizon_days) -> HEIResult(hei, forced_release_bcm, day_of_exhaustion)`.
- [x] **Step 3: run tests, pass.**

### Task 10: Routing and classification

**Files:** `punjabflood/routing.py`, `tests/test_routing.py`

- [x] **Step 1: failing tests**: an impulse release at Bhakra on day 0 hour 0 arrives at Ropar at +18 h and at Harike at +52 h; daily max at Harike of Sutlej plus Beas contributions; classification uses `constants.CONTROL_POINTS`; Dhilwan lag is the interpolated Tanda–Harike fraction.
- [x] **Step 2: implement** `route_series(hourly_cusecs, river, frm, to)` (pure shift by `travel_hours`), `arrivals(release_by_dam_daily) -> DataFrame[station, date, cusecs]`, `classify_arrivals`.
- [x] **Step 3: run tests, pass.**

### Task 11: Verification

**Files:** `punjabflood/verify.py`, `tests/test_verify.py`, `outputs/verification/`

- [x] **Step 1: failing tests** on synthetic inputs: ordinal metrics (Spearman, AUROC high-vs-rest) computed correctly; leave-one-year-out returns one prediction per year; lag error is signed days.
- [x] **Step 2: implement** `annual_predictors(rain_daily, state_frame)` (season rain volume, maximum 3-day and 5-day rain volume, storage fraction on 1 Aug and 15 Aug, maximum perfect-prog HEI), `peak_class_test(predictors, peaks)` (Spearman against peak discharge, AUROC for the WRD High class, leave-one-year-out logistic), `event_timing_test(routed, peaks_dhilwan)` for 2023 and 2025, `live_2026_test(predicted_inflow, bulletins)`.
- [x] **Step 3: run tests; run the verification; write `docs/verification.md` from the outputs (numbers come from the CSVs, never typed).**

### Task 12: Forecast product

**Files:** `punjabflood/forecast.py`, `tests/test_forecast.py`

- [x] **Step 1: failing tests** with fakes: given a state, a QPF table and parameters, `build_product` returns per dam per horizon HEI with ensemble quantiles, per station arrival class, and a disclaimer string; output JSON validates against the documented keys.
- [x] **Step 2: implement** `fetch_bulletin()` (BBMB res_data.pdf via pypdfium2, reusing the parse regex), `build_product(date, state, qpf, ensemble, params)`, `write_outputs(product, outputs_dir)` (JSON and Markdown).
- [x] **Step 3: run tests; run one live cycle and keep its output as the first prospective record.**

### Task 13: CLI and docs

**Files:** `punjabflood/cli.py`, `README.md`, `docs/design.md`, `docs/data-sources.md`

- [x] Commands: `pull-cwc`, `build-catchments`, `pull-rain`, `pull-qpf-archive`, `digitise-guidebook`, `calibrate`, `verify`, `forecast`. Each command is a thin wrapper; tests call the functions, not the CLI.
- [x] README states what the system is, what it is not (no official warning, no satellite labels, impact tier pending), and how to run the full chain.

---

## Deviations recorded at completion (2026-09-05 evening)

All tasks are ticked; where the executed step differs from the step as written, this is the
record.

- Task 6, step 3: the ERA5 archive pull for 1988 to date was stopped (Open-Meteo weighted
  hourly limit) and replaced by the IMD gridded archive (Task 2b). ERA5 covers 2026 only. The
  soil-moisture stage exists in code with gamma fixed at 0 because ERA5-Land soil moisture
  was not pulled.
- Task 7: two steps were added after the first verification run exposed them: a worst-first
  robust rating fit and a level-versus-storage reconciliation of the CWC rows (`reconcile_cwc`),
  because the record repeats stale storage against new levels (Pong 2023-08-17) and carries
  100 m level slips (Ranjit Sagar). Levels are gated to 100 m below and 10 m above FRL.
- Task 8, step 3: the 1991 to 2025 daily pull had not landed (the data.gov.in feed answered
  502 all afternoon and evening; the puller was killed by the operating system for low memory
  at about 19:20 with 0 rows after 63 minutes of continuous 502s, and is resumable with
  `punjabflood pull-cwc`), so the model is calibrated on the 2015 to 2025 seed record,
  measured storage rows only. The recession
  estimate keeps its raw ratio in the parameter file; Bhakra and Ranjit Sagar sit at the
  0.99 clip.
- Task 11: the event-timing test routes the one-day-ahead forced release placed on the day
  it happens (the first version placed the horizon peak at the issue date, which is an
  envelope, not a timing). Between the sparse storage measurements of the event weeks the
  reservoir is carried by the model's own water balance (`carry_storage`). The report adds
  the model's one-day inflow on the wettest day against BBMB's recorded maximum, because
  that gap is what limits the test.
- Task 12, step 3: the first prospective record is `outputs/forecast/2026-09-05.{json,md}`.
  Outputs are committed (the owner's decision the same evening); the daily GitHub Action
  adds one record per day and a record is never rewritten.
- Task 13: `report` was added as a command; `pull-rain` became `build-rain` (IMD) and
  `pull-rain-recent` (ERA5, current season).
- Commits: the owner authorised the agent to commit into the Sailaab repository on top of
  the existing history (no rewrite), which is where this sub-project now lives.

## Second round (2026-09-05, late evening), beyond the plan

- Inflow: the runoff coefficient became wetness-dependent (`c + c_wet * API / 100 mm`,
  capped at 0.95, joint NNLS with the lag weights) after the storage record showed the
  response rising with antecedent rain for Pong and Ranjit Sagar. Calibration uses measured
  storage rows only; the implausible-jump filter was raised to 1.0 BCM so event days stay in.
- Routing: diversions per river (Nangal canals, Mukerian Hydel Channel) and the spill-day
  river release as spill plus turbine passage less diversion; the event test reports both
  that and spill only.
- Verification: persistence baseline in the live test; ERA5 against IMD over the event
  windows; a leave-one-season-out test of a multiplicative QPF bias correction, which the
  product does not adopt because the correction fails the rule in `design.md`.
- Product: P(spillway forced) printed with and without the inflow model's own error
  (`hei.ensemble_summary_with_error`; the residual lag-1 autocorrelation joined the
  parameter file for it). On a forced-spill day the product routes spill plus turbine
  passage less the diversion, the same rule as the event test.
- Verification, continued: an as-issued hindcast (`verify.as_issued_hei`, the archived lead
  1 to 5 QPF of ECMWF and GFS through the product's water balance for every issue date of
  2024 to 2026, Pong and Bhakra, scored as hits, false flags and misses against the
  perfect-prognosis run, with a re-anchor note per dam that also covers flags without a
  spill inside the window) and a prospective-record summary rendered from
  `outputs/forecast/`.
- Constants: two points of the 2019 Bhakra rule curve from the CBIP presentation chart,
  with the vintage caveat; no operator scenario yet.
- `docs/roadmap.md` lists what comes next and the data each step needs.

## Self-review

- Spec coverage: pathway 1 (Tasks 4 to 12), pathway 2 Ghaggar index (Tasks 4, 6, 10 include the Ghaggar catchments and reaches; verification is thin by design and says so), two-tier verification data (Task 11), publication surface (Task 12 outputs only; the web driver panel is out of scope here).
- Placeholders: none; the impact tier is explicitly excluded, not deferred with a TODO.
- Type consistency: `Catchment.points` has columns `lat, lon, weight_km2`; `rain` functions consume that frame; `state_frame` columns `date, dam, storage_bcm, level_m, basis`; `InflowParams` is consumed by `hei` through `volume_bcm`.
