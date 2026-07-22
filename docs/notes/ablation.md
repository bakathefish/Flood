# Forecaster ablation — does the dam signal carry skill, or is the model robust without it?

**Status: PRE-DECLARED (this section written and committed *before* any variant
was run).** Actuals and the verdict are appended at the bottom in a later
commit, so the git history shows the hypotheses predate the result.

## Why this exists

Two claims in the synopsis rest on the reservoir features:

1. *"Bhakra reservoir storage is the #3 driver: a full dam is part of the
   signature it learned"* (SHAP ranking on the 2015–2024 fit).
2. The live nowcast (`docs/notes/nowcast.md`) currently runs with all six
   reservoir features **NaN** (the BBMB→CWC feed has been dark since
   2025-07-11), i.e. the operational model is de facto reservoir-blind.

SHAP attribution is not an ablation: a feature can rank high in attribution yet
carry little *incremental* skill (correlated rain/antecedent features can absorb
its role), and vice versa. A juror — or a reviewer — will ask. This note
pre-commits the experiment and BOTH honest framings, so neither outcome is a
retreat:

- **If skill drops without reservoirs** → the dam-signature claim is proven
  causal-in-the-model, and the darkened BBMB feed is quantified as an
  operational cost ("transparency has a measurable forecasting price").
- **If skill holds without reservoirs** → the live reservoir-blind nowcast
  configuration is validated ("the forecast does not degrade when the dams stop
  reporting"), and the dam-signature claim is softened to attribution-only,
  stated verbatim.

## Pre-declared variants (exact feature sets)

Base = the 16 features of `pipeline/run_forecaster.py::build_dataset` (6 rain +
6 reservoir + antecedent_fraction + week_of_season + 2 prior). Same model class,
same hyperparameters, same LOYO folds, same core-season frame, same
2015–2024→2025 hindcast protocol as the shipped forecaster. Nothing else moves.

| variant | features | n |
|---|---|---|
| `full` | all (reproduces shipped results; consistency check) | 16 |
| `no_reservoir` | minus the 6 `{bhakra,pong,ranjit_sagar}_{storage,delta}` | 10 |
| `meteo_prior` | minus reservoir AND minus `antecedent_fraction` (rain + week + prior only) | 9 |
| `persistence` | no model: score = `antecedent_fraction` directly | — |

## Pre-declared quantities (per variant)

1. Pooled LOYO **PR-AUC** (headline; base rate 1.75%) and ROC-AUC.
2. 2025 hindcast flag metrics under the shipped thresholds (`FLAG_TOPN=5`,
   `FLAG_PROB=0.50`, event windows 08-14/08-24/09-03): `n_flagged` of the five
   named districts, Kapurthala best rank, and the 08-14 early-window top-5 count
   (the ~10-day-lead claim).
3. Δ vs `full` for each of the above.

## Pre-declared verdict bins

- **DAM-SIGNAL HOLDS**: `no_reservoir` loses ≥ 0.02 pooled PR-AUC **or** loses
  a 2025 flag **or** Kapurthala drops out of the top-2, vs `full`.
- **ROBUST WITHOUT FEED**: `no_reservoir` within < 0.02 PR-AUC of `full` and
  identical flag metrics.
- Anything between: **MIXED — reported verbatim**, both framings partially
  apply and both are stated.

Expectations (falsifiable, recorded either way):

- (a) `full` ≥ `no_reservoir` ≥ `meteo_prior` on pooled PR-AUC (monotone
  ordering; a violation is reported as FAIL, not smoothed over).
- (b) Every model variant beats `persistence` on pooled PR-AUC. This is the
  "the model is more than persistence" defence; if `full` does NOT beat
  persistence, that is a finding against our own headline and ships verbatim.
- (c) `full` reproduces the shipped pooled ROC-AUC 0.946 / PR-AUC 0.269 to
  ±0.005 (determinism/consistency gate — if this fails the run is invalid, fix
  before reading any other number).

## Protocol notes

- Implementation reuses `build_dataset` / `loyo_oof` / `hindcast_2025` from
  `pipeline/run_forecaster.py` unchanged; the ONLY degree of freedom is the
  feature list handed to the fits (and, for `persistence`, skipping the fit).
- No hyperparameter retuning per variant — deliberately: the question is the
  marginal value of the features in the shipped configuration, not the best
  achievable reservoir-free model.
- Output: `data/forecaster_ablation.csv`; no shipped forecaster artifact is
  overwritten.

---

(Actuals appended below in a later commit.)
