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

## RESULTS (run pending — filled after training, verbatim)

_To be completed by `python -m pipeline.run_challenger` after the ERA5 intensity
table is built. Contents: side-by-side champion-vs-challenger LOYO table, the
challenger 2025 hindcast, the adoption verdict against the three pre-declared
thresholds, and the champion conformal 80/95 empirical coverage._
