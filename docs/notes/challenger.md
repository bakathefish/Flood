# Forecaster champion/challenger — pre-declared rule, sub-daily intensity, conformal

A disciplined champion/challenger experiment on the district flood-risk forecaster
(`docs/notes/forecaster.md`). The committed model
(`data/models/forecaster_2025.joblib`) is the **CHAMPION** and stays frozen. A
**CHALLENGER** adds six sub-daily rainfall-intensity features and is adopted **only**
if it clears pre-declared thresholds. Everything above the `---` line was written
and committed **before any challenger model was fit**; the `RESULTS` section below
the line is filled in afterwards, verbatim, whether or not the challenger wins.

## Champion baseline (frozen, committed)

Reproduced this run from the committed pipeline (identical to
`data/forecaster_loyo_metrics.csv`, confirming the harness is deterministic):

| metric (pooled LOYO, 1540 core rows, 27 events) | champion |
|---|---|
| ROC-AUC | **0.94589** |
| PR-AUC (average precision) | **0.26871** |
| Spearman (fraction) | 0.52229 |
| MAE (fraction) | 0.001736 |
| 2025 hindcast named-district flags | **5 / 5** |

Champion feature vector = 16 columns: 6 rain (`punjab_mm`, `upstream_mm`, each
+`_lag1`/`_lag2`) + 6 reservoir (`{bhakra,pong,ranjit_sagar}_{storage,delta}`) +
`antecedent_fraction` + `week_of_season` + 2 district-prior (`prior_*`).

## PRE-DECLARED ADOPTION RULE (written before any training)

Both the classification improvement **and** the regression/robustness floor must
hold. The challenger REPLACES the champion **iff ALL THREE** of the following are
true, measured on the **identical** core-season LOYO harness (`sailaab.model`
folds, same XGBoost config, same 1540-row core-season frame):

1. **ROC-AUC gain** — pooled LOYO ROC-AUC improves by **≥ +0.005** over the
   champion: challenger pooled ROC-AUC **≥ 0.95089** (0.94589 + 0.005).
2. **PR-AUC gain** — pooled LOYO PR-AUC improves by **≥ +0.02** over the champion:
   challenger pooled PR-AUC **≥ 0.28871** (0.26871 + 0.02).
3. **Hindcast preserved** — the 2025 hold-out hindcast (train 2015–2024 core
   season, score every 2025 core window) still flags **≥ 5 / 5** of the named 2025
   flood districts {Firozpur, Gurdaspur, Kapurthala, Tarn Taran, Amritsar} under
   the same flag rule as the champion (top-5 of 20 in ≥1 target window **OR**
   P(event) ≥ 0.50, target windows {08-14, 08-24, 09-03}).

Any one of the three failing ⇒ **champion retained**. A retained champion with a
documented negative result is an accepted, valuable outcome — the point is a
truthful test, not a forced win. No re-declaration of thresholds after seeing
challenger numbers.

## THE SIX NEW FEATURES (exact)

Sub-daily rainfall **intensity**, from the Open-Meteo **ERA5 archive** (keyless,
`archive-api.open-meteo.com`, hourly variable `precipitation`), 2015–2025. For
**both** boxes — the same `PUNJAB_BOX` (Punjab plains) and `UPSTREAM_BOX`
(Sutlej/Beas/Ravi upstream) 3×3 cos(lat)-weighted point grids used by
`pipeline/fetch_live_inputs.py` — the hourly precipitation of the 9 grid points is
reduced to one cos(lat)-weighted **area-mean hourly series** per box, then per
10-day monsoon window `[window_start, window_end)` (same window grid as the decade
run) three metrics are computed **within-window only** (no cross-window leakage):

| column | definition (per box, per window) |
|---|---|
| `punjab_max_3h_mm` / `upstream_max_3h_mm` | max over the window of the rolling **3-hour** area-mean rainfall sum (mm) |
| `punjab_max_24h_mm` / `upstream_max_24h_mm` | max over the window of the rolling **24-hour** area-mean rainfall sum (mm) |
| `punjab_hours_ge5mm` / `upstream_hours_ge5mm` | count of hours in the window whose area-mean rainfall is **≥ 5 mm** |

= **6 new columns**. Raw hourly responses cached to `data/rasters/era5/`
(gitignored); the derived per-window table is committed as
`data/rain_intensity_windows.csv` and merged on `(year, window_start)`, so — like
the existing rain features — the six values are identical across the 20 districts
of a window. Challenger feature vector = champion's 16 + these 6 = **22**. Same
core-season scoping (`window_start` month-day ≥ `07-25`), same folds, same config.

## CONFORMAL METHOD (both outcomes — applied to the frozen champion)

Split-conformal prediction intervals for the **regression head** (flooded
`fraction`), calibrated on **leave-one-year-out out-of-fold residuals** so the
intervals inherit the same honesty as the LOYO point estimates. Implemented in a
new TDD'd `sailaab/conformal.py` (synthetic coverage test written first).

- **Nonconformity score:** absolute OOF residual `|y − ŷ|` from the LOYO
  regression head (`XGBRegressor` on `flooded_fraction`, the champion 16 features).
- **Finite-sample quantile:** for nominal coverage `1−α`, the conformal radius `q`
  is the `⌈(n+1)(1−α)⌉`-th smallest absolute residual of the calibration set
  (standard split-conformal correction; `q = +∞` if `⌈(n+1)(1−α)⌉ > n`).
- **LOYO-honest calibration:** each held-out year's intervals use `q` computed
  from the OOF residuals of the **other** years only — no row calibrates on its own
  residual. Point prediction for a row is its own LOYO OOF `ŷ`.
- **Intervals:** symmetric `[ŷ − q, ŷ + q]`, clamped to `[0, 1]` (physical bounds
  of a fraction; clamping is coverage-preserving because `y ∈ [0, 1]`).
- **Report:** empirical LOYO coverage of the **80%** and **95%** intervals, pooled
  over all 1540 core rows (target ≈ nominal; actual reported verbatim).
- **Committed artefact:** `data/forecaster_conformal.csv` with
  `year, window, district, pred, lo80, hi80, lo95, hi95` for every champion core row.

Deliverables: `data/rain_intensity_windows.csv`, `data/forecaster_conformal.csv`,
`sailaab/conformal.py` + `tests/test_conformal.py`, `pipeline/fetch_era5_intensity.py`,
`pipeline/run_challenger.py`, and the RESULTS section below.

---

## RESULTS (run `python -m pipeline.run_challenger`, 2026-07-22)

ERA5 intensity table: `data/rain_intensity_windows.csv` (121 rows = 11 years x 11
windows, 6 intensity columns). The `*_max_24h_mm` features peak in the 2025 event
window `[08-24, 09-03)` (punjab **53.9 mm**, upstream **40.7 mm**) — physically
coherent. The `*_hours_ge5mm` counts are sparse on the box **area-mean** series
(≥5 mm/h averaged over a ~300 km box is extreme): mostly 0, max 4 — a near-constant
column, kept as pre-declared. Both feature sets run on the **identical** 1540-row
core-season frame (27 events, base rate 1.75%); the recomputed champion equals the
committed `forecaster_loyo_metrics.csv` to all digits, confirming a fair harness.

### Side-by-side LOYO — champion (16 feat) vs challenger (16 + 6 = 22 feat)

Classification metrics exist only for the 3 event-bearing years (2019/2023/2025);
the other 8 are single-class (AUC undefined). Regression spans all 11.

| year | events | champ PR-AUC | chal PR-AUC | champ ROC-AUC | chal ROC-AUC | champ Spearman | chal Spearman |
|---|---|---|---|---|---|---|---|
| 2019 | 2 | 0.0519 | 0.0505 | 0.7808 | 0.7844 | 0.442 | 0.425 |
| 2023 | 11 | 0.5922 | 0.5670 | 0.9295 | 0.9281 | 0.862 | 0.866 |
| 2025 | 14 | 0.5122 | 0.4714 | 0.8974 | 0.8804 | 0.256 | 0.248 |
| *(8 zero-event yrs)* | 0 | n/a | n/a | n/a | n/a | 0.21–0.62 | 0.22–0.67 |
| **POOLED** | **27** | **0.26871** | **0.24455** | **0.94589** | **0.94452** | **0.52229** | **0.51749** |
| **Δ (chal − champ)** | | | **−0.02416** | | **−0.00137** | | **−0.00480** |

Pooled MAE (fraction): champion **0.001736**, challenger **0.001565** (the one place
the intensity features help — ~10% lower absolute regression error, driven by 2025:
MAE 0.00718 → 0.00517). Full table committed to `data/forecaster_challenger_loyo.csv`.

### Challenger 2025 hindcast (train 2015–2024 core, score every 2025 core window)

| district | best rank (of 20) | best P(event) | flagged |
|---|---|---|---|
| Kapurthala | **1** | 0.714 | yes |
| Firozpur | **2** | 0.417 | yes |
| Tarn Taran | **2** | 0.340 | yes |
| Gurdaspur | **4** | 0.087 | yes |
| Amritsar | **5** | 0.011 | yes |

**5 / 5 named districts flagged** — same as the champion, though at slightly lower
probabilities (champion Firozpur 0.502 / Tarn Taran 0.434 vs challenger 0.417 / 0.340).

### VERDICT — CHALLENGER NOT ADOPTED (champion retained)

Applying the three pre-declared thresholds verbatim:

| condition | required | actual | pass? |
|---|---|---|---|
| ROC-AUC gain | ≥ +0.005 (chal ≥ 0.95089) | **−0.00137** (0.94452) | **NO** |
| PR-AUC gain | ≥ +0.02 (chal ≥ 0.28871) | **−0.02416** (0.24455) | **NO** |
| 2025 hindcast flags | ≥ 5 / 5 | 5 / 5 | yes |

Two of the three fail — and not marginally: the challenger is **worse** on both
classification headlines. **The champion is retained.** The six statewide
intensity columns are collinear with the daily rain features the champion already
carries (`punjab_mm`/`upstream_mm` + lags), so they add variance, not signal, to a
27-positive problem; the two `*_hours_ge5mm` columns are near-constant. The only
gain is a modest drop in regression MAE, which the rule (rightly) does not reward.

**A documented negative result.** The frozen champion
`data/models/forecaster_2025.joblib` stands; `data/models/forecaster_2025_v2.joblib`
was **not** written. `pipeline/nowcast.py` is **untouched and needs no change** —
its locked 16-feature contract (`FEATURE_ORDER`) remains correct. (Had the
challenger been adopted, nowcast.py would have needed the 6 intensity features
added to its live feature assembly, plus a live hourly-ERA5 fetch in
`fetch_live_inputs.py` — flagged here for the record; not required.)

### Champion conformal — split-conformal intervals for flooded `fraction`

LOYO-honest split-conformal (`sailaab.conformal`, TDD'd in `tests/test_conformal.py`),
absolute OOF residuals, symmetric intervals clamped to `[0, 1]`. Committed per-row
to `data/forecaster_conformal.csv` (1540 rows: year, window, district, pred, lo80,
hi80, lo95, hi95). Median interval half-widths are tiny because fractions are tiny:
80% width ≈ 0.0022, 95% width ≈ 0.0094 (i.e. ±0.11 / ±0.47 percentage points).

**Empirical coverage (pooled, n=1540): 80% → 0.798, 95% → 0.929.** Both ≈ nominal.
But the per-year breakdown is the honest headline:

| year | cov80 | cov95 | | year | cov80 | cov95 |
|---|---|---|---|---|---|---|
| 2015 | 0.886 | 0.986 | | 2021 | 0.921 | 0.993 |
| 2016 | 0.864 | 0.957 | | 2022 | 0.950 | 1.000 |
| 2017 | 0.964 | 0.993 | | 2023 | 0.700 | 0.850 |
| 2018 | 0.743 | 0.943 | | 2024 | 0.993 | 1.000 |
| 2019 | 0.743 | 0.936 | | **2025** | **0.036** | **0.557** |
| 2020 | 0.979 | 1.000 | | | | |

Every normal year sits at/above nominal; **2025 collapses (cov80 0.036, cov95 0.557)**.
This is the textbook conformal failure mode under **non-exchangeability**:
LOYO-honest calibration leaves 2025 out, so the radius is set by 2015–2024 residuals
(all tiny), yet 2025's flooded fractions are an order of magnitude larger (+10σ
event) — the intervals are far too narrow for the one year that most matters. The
marginal (pooled) guarantee holds; the conditional (per-year) guarantee cannot, and
conformal makes that limitation *visible and quantified* rather than hidden. Reported
verbatim, not smoothed.

### Bottom line

The sub-daily ERA5 intensity features do **not** beat the frozen champion on the
pre-declared bar — a clean, disciplined negative result; the champion stays. Split-
conformal gives calibrated (~nominal) marginal prediction intervals for the flooded-
fraction head across normal years, and honestly exposes its own under-coverage in
the extreme 2025 outlier. Citations: n/a (ERA5 hourly via keyless Open-Meteo archive;
all other inputs are this repo's committed CSVs).
