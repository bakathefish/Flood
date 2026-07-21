# District flood-risk forecaster — pre-declared bands, paddy decision, actuals

The last AI piece of the pipeline. A district x window flood-risk forecaster whose
**training labels the pipeline manufactured itself** (the GFM decade atlas,
`data/gfm_district_window_fractions_2015_2025.csv`). Assembly reuses
`sailaab.dataset` (antecedent + week-of-season + event labels), modelling reuses
`sailaab.model` (LOYO splits + XGBoost); new pure helpers live in
`sailaab.forecast_features` (reservoir pivot, core-season mask, district prior,
metric wrappers), TDD'd in `tests/test_forecast_features.py`. Driver:
`pipeline/run_forecaster.py`.

## Inputs (all committed CSVs, no network)

- **Target** `gfm_district_window_fractions_2015_2025.csv` — 2,420 rows =
  11 years x 11 monsoon windows x 20 districts; `fraction` (regression target) and
  `flooded_ha`. `fraction > config.FLOOD_EVENT_FRACTION (0.02)` = event label.
- **Rain** `rain_windows_2015_2025.csv` — statewide two-box IMD 0.25 deg means:
  `punjab_mm`, `upstream_mm`, each with `_lag1`, `_lag2` (already window-lagged).
  Joined on (year, window_start); identical across the 20 districts of a window.
- **Reservoirs** `reservoir_windows.csv` — per-dam (Bhakra, Pong, Ranjit Sagar)
  `mean_storage` + `delta_storage`; pivoted wide to 6 features per window.
- **District prior** `flood_frequency_districts_late_season.csv` — the calibrated
  (post-paddy) repeat-victim table; `mean_annual_flooded_ha` +
  `seasons_with_fraction_gt2pct` merged per district as `prior_*`.

Feature vector (~15): 6 rain (current + 2 lags, both boxes) + 6 reservoir
(3 dams x storage/delta) + `antecedent_fraction` (lag-1 of the target) +
`week_of_season` + 2 district-prior columns.

## PADDY DECISION (never silently train on contaminated labels)

`docs/notes/gfm-decade.md` quantified it: statewide mean flooded-ha per window is
Jun-15 150,848 / Jun-25 172,684 / Jul-05 78,774 / Jul-15 38,441 ha, then a ~20x
**collapse** once rice transplanting ends — Jul-25 8,997 / Aug-04 4,705 /
Aug-14 9,366 / Aug-24 8,974 / Sep-03 7,589 / Sep-13 3,042 / Sep-23 1,820 ha. The
four windows starting Jun-15..Jul-15 are agronomic inundation (fields deliberately
flooded for paddy), not floods; on those windows the event base rate is a
manufactured **30%**, versus **1.75%** on the seven Jul-25+ windows that carry the
real flood climatology.

**Decision:** train *and* evaluate the event classifier **and** the fraction
regressor only on **core-season windows** (`window_start` month-day >= `07-25`, i.e.
the 7 post-transplant windows). `week_of_season` is computed over the full 11-window
season *before* the core filter (so it carries absolute seasonal position 4..10, and
`antecedent_fraction` of the first core window is the real Jul-15 antecedent), then
the paddy windows are dropped from the modelling frame. No paddy-manufactured
positive ever enters a fit. The 2025 event (Aug 22 – Sep 6) lies entirely inside the
core season, so nothing of interest is lost.

**Alternatives considered & rejected:**
- *Train on all windows, evaluate only on core* (the lighter mission option): still
  fits the positive class to agronomic water and lets June "floods" shape the tree
  splits — rejected as still training on contaminated labels.
- *Substitute a calibrated late-season target for the early windows*: gfm-decade.md's
  calibration exists only at the **season-union** level, not per district x early
  window, so per-cell early-window "flood" fractions would be fabricated — rejected.

`week_of_season` is retained as a feature (mission requirement and a genuine
within-core-season signal: late-Jul vs Sep base rates differ).

**Leakage note (district prior).** The `prior_*` columns come from the all-years
late-season frequency table, so a held-out year contributes <= 1/11 to its own
district's prior. Because the prior is a single per-district constant (identical
across every window and year of a district) it cannot discriminate *within* a
held-out year — it only shifts a district's baseline — so the residual leakage
cannot inflate the within-year window ranking that PR-AUC and the 2025 rank-flag
measure. Reported honestly; SHAP is checked to confirm the prior is not the
dominant feature.

## PRE-DECLARED bands (written BEFORE any model was fit)

Base rate is a property of the target, not a model output: core-season
(`window_start >= 07-25`) event prevalence = **27 / 1540 = 1.75%**.

**(a) LOYO event-classification usable signal.** Headline = pooled out-of-fold
**PR-AUC** (average precision; threshold-free, robust to the 1.75% imbalance).
Secondary = pooled OOF ROC-AUC and F1/precision/recall at a **declared threshold of
0.50**. Per-year metrics reported where the test year has >= 1 core-season event
(0-event years -> AUC undefined = NaN, exactly as `sailaab.model` handles it).
Bands:
- **USABLE** iff pooled PR-AUC >= **0.10** (> 5x the 0.018 base rate) **and** pooled
  ROC-AUC >= **0.75**.
- **STRONG** iff pooled PR-AUC >= **0.30** **and** pooled ROC-AUC >= **0.85**.
- Regression (fraction): **USABLE** iff pooled Spearman >= **0.30**; MAE reported
  (no hard band — fractions are small so absolute MAE will be tiny).

**(b) 2025 holdout — train 2015-2024, predict every 2025 window.** Target windows =
`window_start` month-day in **{08-14, 08-24, 09-03}** (the three 10-day windows
spanning the Aug 22 – Sep 6 event). Named flood set (the RF/GFM 2025 top districts) =
**{Firozpur, Gurdaspur, Kapurthala, Tarn Taran, Amritsar}**. A district is
**FLAGGED** iff, in >= 1 target window, its predicted P(event) ranks in the **top-5
of 20** districts for that window **OR** P(event) >= **0.50**.
- **PASS** iff **>= 3 of 5** named districts flagged; **STRONG** iff **>= 4 of 5**.
- A miss (< 3 flagged) is reported openly as *hindcast skill under the most extreme
  event in the record* — 2025 is the +10-sigma year the model never trained on, and
  its reservoir readings are largely missing (BBMB stopped reporting to CWC on
  2025-07-11), so rain must carry the 2025 signal.
- **Early-warning readout:** in the first target window `[08-14, 08-24)` (Aug 14-24,
  *before* the Aug 26-27 dam-release peak), report the model's risk **rank**
  (1 = highest of 20) for each named district.

**(c) SHAP.** Expectation (declared): the top-3 mean-|SHAP| features include >= 1
upstream-rain feature (`upstream_mm` / `_lag1` / `_lag2`) **and** >= 1 reservoir
feature (`*_storage` / `*_delta`). The **actual** top-3 is reported verbatim below
regardless of whether the expectation holds.

## ACTUALS (run 2026-07-21, `python -m pipeline.run_forecaster`)

Core-season modelling frame: 1,540 rows (7 windows x 20 districts x 11 years),
27 events, base rate **1.75%**. XGBoost mirrors `sailaab.model._make_model`
(300 trees, depth 4, lr 0.05, subsample 0.9); classifier + regressor share the
same LOYO folds from `sailaab.model.loyo_splits`. Only 3 of 11 seasons carry any
core-season event (2019, 2023, 2025) — the real Punjab flood years — so per-year
classification AUCs exist only for those; the **pooled OOF** metric is the honest
aggregate.

**LOYO (leave-one-year-out) — `data/forecaster_loyo_metrics.csv`:**

| year | events | PR-AUC | ROC-AUC | Spearman | MAE |
|---|---|---|---|---|---|
| 2019 | 2 | 0.052 | 0.781 | 0.442 | 0.0022 |
| 2023 | 11 | 0.592 | 0.930 | 0.862 | 0.0040 |
| 2025 | 14 | 0.512 | 0.897 | 0.256 | 0.0072 |
| *(8 zero-event yrs)* | 0 | n/a | n/a | 0.21–0.62 | <0.0017 |
| **POOLED** | **27** | **0.269** | **0.946** | **0.522** | **0.0017** |

Pooled F1@0.50 = 0.235 (precision 0.571, recall 0.148) — precise but low recall at
the conservative 0.5 cut, as expected at a 1.75% base rate; PR-AUC/ROC/rank are the
threshold-free headline. **Cross-check:** `sailaab.model.fit_eval` per-year ROC-AUC
= 2019 **0.781**, 2023 **0.930**, 2025 **0.897** — identical to the OOF loop above,
confirming the loop reproduces the module's LOYO exactly (0-event years are the
single-class years `fit_eval` skips).

**Prior-leakage robustness (test-before-ship).** Re-running LOYO **and** the 2025
hindcast with the district prior recomputed **fold-safe** (per-district mean
core-season fraction + count of >2% seasons, from *training years only*, excluding
the held-out/2025 year) gives pooled PR-AUC **0.215**, ROC **0.923**, Spearman
**0.525**, and the **same 5/5** 2025 flags at the **same ranks** (Kapurthala 1,
Firozpur 2, Tarn Taran 2, Gurdaspur 4, Amritsar 5). The <=1/11 prior self-leak
therefore does **not** drive any verdict — the prior encodes stable river-corridor
geography, not the 2025 outcome. Headline numbers below use the committed
all-years late-season prior table as specified; the fold-safe run is the honesty
check.

**2025 showcase hindcast (train 2015-2024 core season, predict every 2025 window).**
2025 per-year classification: ROC-AUC **0.897**, PR-AUC **0.512**. Verbatim flag
readout on the target windows {08-14, 08-24, 09-03}:

| district | best rank (of 20) | best P(event) | flagged |
|---|---|---|---|
| Kapurthala | **1** | 0.721 | yes |
| Firozpur | **2** | 0.502 | yes |
| Tarn Taran | **2** | 0.434 | yes |
| Gurdaspur | **4** | 0.131 | yes |
| Amritsar | **5** | 0.019 | yes |

**5 of 5 named districts flagged.** Every one lands in the top-5 of its worst
window; Kapurthala and Firozpur also clear P>=0.50. (Ground truth confirms all five
are genuine 2025 core-season events, `fraction` 0.022-0.057; the only non-named
top-6 district by actual fraction is Jalandhar.)

**Early-warning readout** — window `[08-14, 08-24)` (Aug 14-24, ~10 days *before*
the Aug 26-27 dam-release peak): risk ranks Kapurthala **#1**, Firozpur **#2**,
Tarn Taran **#3**, Gurdaspur **#5**, Amritsar #9. As of that window **4 of the 5
eventual flood districts were already in the model's top-5 risk ranks** — a real
lead-time signal built only from data available before the crest.

**SHAP (mean-|value| on the 2015-2024 fit) — `atlas/forecaster_shap.png`,
verbatim top features:**
1. **antecedent_fraction** — 1.232 (flood persistence: last window's observed extent)
2. **prior_seasons_with_fraction_gt2pct** — 1.082 (district repeat-victim propensity)
3. **bhakra_storage** — 0.837 (Gobind Sagar / Sutlej live storage)
4. punjab_mm_lag2 — 0.821 · 5. ranjit_sagar_storage — 0.359 · 6. pong_delta — 0.346
· 7. upstream_mm_lag1 — 0.29 · 8. upstream_mm — 0.28

## VERDICTS (actual vs pre-declared band)

- **(a) LOYO usable signal — PASS (usable; verges on strong).** Pooled ROC-AUC
  **0.946** clears the STRONG bar (>=0.85); pooled PR-AUC **0.269** is ~15x the 1.75%
  base rate and clears USABLE (>=0.10) but sits just under the STRONG line (0.30);
  regression Spearman **0.522** clears USABLE (>=0.30). Fold-safe prior confirms
  (PR-AUC 0.215, ROC 0.923). Verdict: **usable flood signal confirmed decisively**,
  a hair short of the (arbitrary) STRONG PR-AUC cut.

- **(b) 2025 holdout — STRONG PASS.** 5 of 5 named districts flagged (band: PASS >=3,
  STRONG >=4), all in the top-5 of their worst window; identical under the fold-safe
  prior. This is **hindcast skill under the most extreme event in the 11-year
  record** — 2025 was held out entirely, is the +10-sigma rain year the model never
  trained on, and its reservoir readings are largely missing post-2025-07-11, so
  rain + antecedent + susceptibility carried a clean 5/5 detection with a genuine
  ~10-day early-warning lead (4/5 in top-5 before the crest).

- **(c) SHAP — expectation PARTIALLY met, reported verbatim.** Reservoir storage in
  the top-3 as expected (**bhakra_storage #3**); the *upstream-rain* half was **not**
  met — the top rain feature is **punjab_mm_lag2 at #4** (local box, 2-window lag),
  with upstream rain at #7-#8. The two strongest features are flood persistence
  (antecedent fraction) and district repeat-victim propensity (the prior). Physically
  coherent: within the clean flood season, *where it flooded last window* and *which
  districts chronically flood* dominate, with Bhakra/Sutlej storage and antecedent
  Punjab-plains rain as the top dynamic drivers.

**Bottom line.** On the pipeline's own manufactured GFM labels, once the
rice-transplant windows are removed, the forecaster shows a genuine, leakage-checked
flood signal (ROC-AUC 0.95 pooled) and cleanly hindcasts the 2025 disaster it never
saw — flagging all five real flood districts, four of them with ~10 days of lead.

Citations: n/a (all inputs are this repo's committed CSVs; sources documented in
`docs/notes/{gfm-decade,imd-rain,reservoirs}.md`).

