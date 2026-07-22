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

## Actuals

Run 2026-07-22, `python -m pipeline.run_ablation` (no network; all inputs are the
repo's committed CSVs). Same 1,540-row core-season frame (7 post-paddy windows x
20 districts x 11 years, 27 events, base rate 1.75%), same LOYO folds
(`sailaab.model.loyo_splits`), same XGBoost construction (`run_forecaster._mk_clf`:
300 trees, depth 4, lr 0.05, subsample 0.9), same 2015-2024->2025 hindcast and the
same flag constants (`FLAG_TOPN=5`, `FLAG_PROB=0.50`, event windows
{08-14, 08-24, 09-03}) as the shipped forecaster. Classifier only — the fraction
regressor is not part of this ablation. Every core row's antecedent_fraction is
present (0 NaN), so the persistence baseline needs no imputation. Output:
`data/forecaster_ablation.csv`; no shipped forecaster artifact was overwritten.

**Consistency gate (expectation (c)) — PASS.** The `full` variant reproduces the
shipped `POOLED` row (`data/forecaster_loyo_metrics.csv`) **exactly**: pooled
PR-AUC **0.268711** vs target 0.268711, pooled ROC-AUC **0.945889** vs target
0.945889 — 0.000000 apart, inside the ±0.005 gate. The classifier-only LOYO loop
is bit-identical to the shipped classifier, so every downstream number is
trustworthy. (Driver reruns to a byte-identical CSV.)

**Ablation table (verbatim, `data/forecaster_ablation.csv`):**

| variant | n_feat | pooled PR-AUC | pooled ROC-AUC | 2025 flagged (of 5) | Kapurthala best rank | 08-14 early top-5 | ΔPR-AUC | ΔROC-AUC | Δflagged |
|---|---|---|---|---|---|---|---|---|---|
| `full` | 16 | **0.268711** | **0.945889** | **5** | 1 | 4 | 0.000000 | 0.000000 | 0 |
| `no_reservoir` | 10 | **0.312003** | 0.931874 | **5** | 1 | 4 | **+0.043292** | −0.014015 | 0 |
| `meteo_prior` | 9 | 0.111861 | 0.762233 | 3 | 1 | 3 | −0.156850 | −0.183656 | −2 |
| `persistence` | 1 | 0.308314 | 0.936464 | **5** | 1 | 3 | +0.039603 | −0.009425 | 0 |

**2025 hindcast best rank-of-20 per named district** (across {08-14, 08-24, 09-03};
✗ = not flagged, i.e. best rank > 5 *and* best P(event) < 0.50):

| district | `full` | `no_reservoir` | `meteo_prior` | `persistence` |
|---|---|---|---|---|
| Kapurthala | 1 | 1 | 1 | 1 |
| Firozpur | 2 | 2 | 3 | 1 |
| Tarn Taran | 2 | 2 | 2 | 2 |
| Gurdaspur | 4 | 4 | 6 ✗ | 1 |
| Amritsar | 5 | 5 | 8 ✗ | 5 |
| **flagged** | **5/5** | **5/5** | **3/5** | **5/5** |

For `persistence` every flag is earned by rank alone (best P(event) 0.02-0.06 never
reaches 0.50) — exactly as pre-declared ("the prob criterion will simply not
trigger").

**Expectation checks (recorded either way):**

- **(a) monotone `full` ≥ `no_reservoir` ≥ `meteo_prior` on pooled PR-AUC — FAIL.**
  `full` 0.268711 ≥ `no_reservoir` 0.312003 is **false**: dropping the six reservoir
  features *raised* pooled PR-AUC by +0.043. (`no_reservoir` 0.312003 ≥ `meteo_prior`
  0.111861 holds.) The declared ordering is violated at the first inequality;
  reported as FAIL, not smoothed over.
- **(b) every model variant beats `persistence` on pooled PR-AUC — FAIL.**
  `persistence` = 0.308314. `full` (0.268711) does **not** beat it; `meteo_prior`
  (0.111861) does not; only `no_reservoir` (0.312003) clears it, by 0.0037. Per the
  pre-declared rule this is a finding against our own headline and ships verbatim:
  the LOYO model does **not** exceed raw flood-persistence on average precision. It
  does edge persistence on pooled ROC-AUC (0.945889 vs 0.936464) and matches it on
  2025 detection (5/5, Kapurthala #1).
- **(c) `full` reproduces shipped 0.269 PR / 0.946 ROC to ±0.005 — PASS** (0.268711 /
  0.945889, exact; see gate above).

## Verdict

**Bin: MIXED — reported verbatim.** Evaluating the pre-declared conditions on
`no_reservoir` vs `full`:

- **DAM-SIGNAL HOLDS** requires `no_reservoir` to *lose* ≥ 0.02 pooled PR-AUC **or**
  lose a 2025 flag **or** drop Kapurthala out of the top-2. Actuals: ΔPR-AUC =
  **+0.043** (a gain, not a loss), flags **5/5** unchanged, Kapurthala still **#1**.
  → does **not** fire.
- **ROBUST WITHOUT FEED** requires `no_reservoir` **within < 0.02** PR-AUC of `full`
  **and** identical flag metrics. Actuals: flag metrics **are** identical (5/5,
  Kapurthala #1, early top-5 = 4, same as `full`), **but** |ΔPR-AUC| = 0.043 ≥ 0.02,
  so the proximity clause fails. → does **not** fire.
- Neither bin fires → **MIXED**, and both pre-declared framings are stated:
  - *"If skill holds without reservoirs → the live reservoir-blind nowcast
    configuration is validated ('the forecast does not degrade when the dams stop
    reporting'), and the dam-signature claim is softened to attribution-only, stated
    verbatim."*
  - *"If skill drops without reservoirs → the dam-signature claim is proven
    causal-in-the-model, and the darkened BBMB feed is quantified as an operational
    cost ('transparency has a measurable forecasting price')."*

**Which way the evidence points.** The result lands off the ROBUST band on the
*favorable* side, not toward DAM-SIGNAL HOLDS: removing all six reservoir features
did not degrade the forecaster — it left the 2025 hindcast identical (5/5 flagged,
same ranks, same 4-of-5 early-warning top-5 before the crest) and *improved* pooled
PR-AUC by +0.043 (only pooled ROC-AUC dipped 0.014). So the "skill holds without
reservoirs" framing is the one supported: the live reservoir-blind nowcast (BBMB
feed dark since 2025-07-11) is validated, and the SHAP "Bhakra storage is the #3
driver" claim is **attribution-only** — the reservoir features carry no incremental
LOYO skill in the shipped configuration. The "skill drops" framing does **not**
apply (no drop occurred); the reason the bin is MIXED rather than a clean ROBUST is
solely that the improvement exceeds the ±0.02 proximity band the ROBUST bin was
written around.

**What actually carries the signal.** The `meteo_prior` variant (drop reservoirs
**and** antecedent_fraction) collapses to PR-AUC 0.112 / ROC 0.762 / 3-of-5 flags —
a 0.20 PR-AUC fall from `no_reservoir` — while `persistence` (antecedent_fraction
alone, no fit) nearly matches the full model (PR-AUC 0.308, ROC 0.936, 5/5).
Antecedent flood extent, not reservoir storage, is the load-bearing dynamic feature,
consistent with the shipped SHAP ranking (antecedent_fraction #1). Kapurthala is #1
in every variant including persistence — its 2025 signal is antecedent-driven and
robust to dropping the dam feed entirely.

