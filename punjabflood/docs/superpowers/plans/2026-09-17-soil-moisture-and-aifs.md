# Soil Moisture as the Wetness Carrier, and AIFS as a Rain Source (roadmap items 6 and 4)

> **For agentic workers:** Executed inline by a single writer, tests first, smallest implementation that passes, then the next task. Commits as the repository's own author with no attribution trailer. Every number in the docs comes from `outputs/` through `punjabflood report`; nothing is typed by hand. Adoption rules are written here before any fit is run.

**Goal:** take in the best input the keyless record offers on both sides of the inflow model. On the runoff side, the ground's wetness enters as ERA5-Land soil moisture instead of, or beside, the five-day rain index that stands in for it. On the rain side, ECMWF's machine-learned model (AIFS single, `ecmwf_aifs025_single` on Open-Meteo) joins IFS and GFS as a forecast source and is scored the same way. Neither is adopted on taste: each has a rule below, and the verification report says which way it went.

**What was probed on 2026-09-17:** the Open-Meteo archive returns ERA5-Land soil moisture (0 to 7 cm and 7 to 28 cm, daily means) for 2015 to 2025 with no gaps at a Pong catchment point; AIFS single is served by the forecast endpoint and by the historical-forecast endpoint with the `_previous_dayN` variables from March 2025 (nothing before), so its as-issued archive covers the 2025 and 2026 seasons. The dam catchments hold 71, 38 and 22 IMD-covered points (Bhakra, Pong, Ranjit Sagar); the soil-moisture pull is one archive call per point.

---

## Part A: soil moisture

### The term
The coefficient in force today is `c_t = coefficient(api) * (1 + gamma * sm_anom_t)`, the form already in `inflow.py` (gamma fitted in a second stage, never used because no soil-moisture record was ever pulled). `sm_anom_t` is the fractional anomaly of the 0 to 7 cm ERA5-Land soil moisture against its day-of-year climatology (a 31-day centred window over the pulled years), clipped to [-0.9, 3]. Three wetness carriers are fitted and scored:

| variant | API term | soil-moisture term |
|---|---|---|
| `baseline` | fitted (`c_wet`) | none (gamma 0) |
| `api+sm` | fitted | gamma fitted on the residual |
| `sm` | none (`c_wet` 0) | gamma fitted |

### Adoption rule (written before the fit)
The repository's existing rule, `verify.variant_verdict`, the one the threshold-excess test was held to: leave-one-season-out on the same storage record the held-out RMSE may not rise at any dam; the season-peak ratios of the flood-scale check must rise; and the period means may not move further from the reported means than the baseline's worst one does. Otherwise the product keeps the baseline and the report records the refusal with the numbers.

### Tasks
1. [x] **Pull.** `punjabflood pull-soil-moisture --start 2015-01-01 --end 2025-12-31`: ERA5-Land soil moisture as catchment means over the IMD-covered points of the dam catchments, merged into `data/raw/rain/catchment_daily.csv` by (catchment, date) as `sm_0_7`, `sm_7_28` (the 2026 rows from `pull-rain-recent` already carry them). Test: the merge keeps every rain row and fills the two columns where the pull has a day.
2. [x] **Climatology and anomaly.** `inflow.sm_climatology(series)` (366 values, 31-day window) and `inflow.sm_anomaly(p, value, date)`; `InflowParams` carries `sm_clim` and `wetness` ("api", "api+sm", "sm"). Tests: a flat series gives zero anomaly; a doubled day gives +1; the window smooths a single spike.
3. [x] **Consistent use.** `design_matrix` gains `sm_anom`; `predict_storage_change` applies gamma; `calibrate(..., wetness=...)`; `loso_score` passes the wetness through. Tests: with gamma 0 nothing changes; with gamma 1 and anomaly 0.5 the prediction is 1.5 times the quick response.
4. [x] **Every predictor path passes the day's anomaly.** `carry_storage`, `perfect_prog_hei`, `as_issued_hei`, `live_horizon_test`, the live 2026 loop in `cli.verify`, and `forecast.build_product` (the product pulls the latest ERA5-Land day available, records its date and the anomaly, and says how stale it is). Tests: the anomaly reaches `predict_daily_bcm` (a fake params with gamma 1 doubles the quick response under anomaly 1).
5. [ ] **Verification and report.** The three variants in `inflow_variants.csv`, the verdict in `results.json`, a paragraph and the table in `verification.md`; `design.md` documents the carrier and the rule; the roadmap moves item 6 to Done with the outcome.

## Part B: AIFS

### Tasks
6. [x] **Archive pull that merges.** `pull-qpf-archive` keeps the rows of models and seasons it did not pull (it used to overwrite the file); `rain.merge_qpf_leads`, tested on a toy file.
7. [x] **AIFS everywhere a model is listed:** `forecast.DETERMINISTIC_MODELS`, `verify.AS_ISSUED_MODELS`, the live horizon test, the QPF skill and bias tables, the as-issued 2025 hindcast, the horizon figure. `ecmwf_aifs025_single` pulled for the 2025 and 2026 seasons; IFS and GFS 2026 brought up to date.
8. [x] **Rule for the product's primary deterministic model** (drives the local term and the deterministic fallback; the spill probability comes from the IFS ensemble either way): stays `ecmwf_ifs025` unless AIFS's heavy-day hit rate over the three dam catchments at leads 1 to 3, on exactly the rows both have, is higher and its false-alarm ratio is not higher (`verify.qpf_model_comparison`). **Outcome 2026-09-17: both conditions passed on 2,034 common rows; `forecast.PRIMARY_DETERMINISTIC` switched to AIFS, the incumbent kept as the comparison's reference.** The report prints the comparison and the product's primary.

## Out of scope, stated
- No AIFS ensemble (Open-Meteo serves none); the spill probability keeps the IFS ensemble.
- Soil moisture for the local catchments: their response is transferred, not fitted; the anomaly there stays zero, said in `design.md`.
- ERA5-Land soil moisture is a reanalysis, not a measurement; its climatology is its own. The product's anomaly is at most about six days old (ERA5T lag) and is labelled with its date.
