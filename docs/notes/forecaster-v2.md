# Forecaster v2: district-resolved rainfall, onset versus continuation, and a negative result

The v1 district forecaster lost to a one-feature persistence baseline on PR-AUC
(0.269 against 0.308). This note records why it lost, what was rebuilt, and what
the rebuild did and did not fix.

**Headline: the rebuild did not produce a forecaster that beats persistence.**
An apparent large gain on flood onset disappeared once the model was chosen
without seeing the year it was judged on. The data products and the evaluation
fixes are real and are kept; the skill claim is withdrawn.

Driver: `pipeline/run_forecaster_v2.py` (variant comparison),
`pipeline/run_forecaster_selection.py` (honest in-fold selection). Pure helpers
and their tests: `sailaab/rain_districts.py`, `sailaab/forecast_v2.py`.

## 1. Why v1 could not beat persistence

v1 had 16 features. Counting how many actually vary *across districts* inside a
single window:

| feature group | varies across districts within a window |
| --- | --- |
| 6 rain columns (`punjab_mm`, `upstream_mm`, lags) | 0% of windows |
| 6 reservoir columns (3 dams, storage and delta) | 0% of windows |
| `week_of_season` | 0% of windows |
| 2 district priors | 100%, but constant across years |
| `antecedent_fraction` | 96% of windows |

The rain predictors were area means over two fixed bounding boxes, so every
district in a window received the same rainfall number, and the reservoir
columns were statewide by construction. The only predictor varying across both
district and window was the lagged target. A gradient-boosted model can still
form district-specific predictions by interacting the static prior with the
statewide series, so it is not literally reduced to persistence, but it has
almost no district-specific weather to learn from.

## 2. District-resolved rainfall

The IMD 0.25 degree daily grid was already on disk for 1961 to 2025 and was
being collapsed to two box means. It is now reduced per district polygon by
area-overlap weights: the intersection area of each grid cell with each district,
scaled by `cos(latitude)` and normalised to sum to 1 per district. Area weighting
is necessary rather than decorative, because Punjab districts are comparable in
size to a single 0.25 degree cell (6 to 19 cells per district) and a
centroid-in-cell rule would drop the smallest districts entirely.

District rainfall now varies within 98.7% of windows, against 0% before.

Sanity check on the peak window of the 2025 event (2025-08-24), using nothing
that went into building the weights:

| district | window rainfall (mm) | API at window open (mm) |
| --- | --- | --- |
| Kapurthala | 355.3 | 87.3 |
| Shahid Bhagat Singh Nagar | 343.4 | 123.0 |
| Rupnagar | 343.1 | 165.5 |
| Gurdaspur | 330.7 | 118.7 |
| Hoshiarpur | 325.4 | 160.5 |

The wettest district is Kapurthala, which was the worst affected, and the highest
antecedent wetness sits in the foothill districts.

Predictors added: window total, wettest single day, wettest 3-day run, 90th
percentile of daily rain, two lagged window totals, rain in the opening 3 and 5
days of the window, and an antecedent precipitation index
`API_t = P_t + 0.9 * API_{t-1}` sampled on the day before the window opens.

## 3. Two evaluation defects fixed

The district prior was computed once over 2015 to 2025 and joined before the
leave-one-year-out split, so every held-out year contributed to its own features.
It is now rebuilt inside each fold from that fold's training years only, and a
test asserts that mutating the held-out year's labels leaves the fold's prior
byte-identical.

Antecedent flooding and week-of-season were shifting across the year boundary, so
the first window of a season inherited the previous September. Both now reset at
the season boundary.

Reported metrics changed too. Pooled ROC-AUC flatters this problem badly: about
three quarters of the negatives come from the eight seasons with no flood at all,
so most comparisons only ask whether a year was quiet. Reported instead:
within-window top-k recall, the false-alert burden in quiet windows, Brier skill
against fold-training climatology, and bootstrap intervals that resample whole
seasons rather than rows.

## 4. Onset versus continuation

Flood water persists for longer than a 10-day window, so scoring every row lets a
model take credit for water already on the ground. Splitting the 27 positives by
whether the district was already above the event threshold when the window
opened:

| year | onset (district was dry) | continuation (already wet) |
| --- | --- | --- |
| 2019 | 2 | 0 |
| 2023 | 2 | 9 |
| 2025 | 6 | 8 |
| total | **10** | **17** |

Seventeen of the twenty-seven positives are continuation. An early-warning system
exists to answer the onset question: which dry district is about to flood. The
decomposition is a genuine and useful distinction and is kept.

Persistence remains informative even inside the onset subset: against a base rate
of 10/1484 = 0.0067 it reaches AP 0.058, roughly 8.5 times prevalence, with
ROC-AUC 0.871 and top-5 recall 0.800. An earlier draft of this note described it
as carrying almost no onset information. That was wrong and is corrected here.

## 5. The negative result

Comparing many variants on the same folds, the best onset scorer was penalised
logistic regression on district rainfall, at AP 0.310 against persistence 0.058.
Three checks dismantled that number.

**Matched ablation.** The winner was a different learner from its comparators, so
the gain was not attributable to rainfall. Holding the learner fixed:

| onset variant, identical nested-logistic learner | AP |
| --- | --- |
| antecedent and prior only, no rain | 0.041 |
| plus statewide rain, no district rain | 0.206 |
| plus district rain | 0.310 |

So of the apparent +0.252 over persistence, about +0.148 came from changing the
learner and using statewide rain, and about +0.104 from district-resolved
rainfall specifically.

**Per-year decomposition.** The pooled figure hides that the model loses in one of
the three event years: AP difference against persistence is +0.044 in 2019,
**-0.155 in 2023**, +0.408 in 2025. The equal-year mean is +0.099, not +0.252,
with a year-block interval of [-0.155, +0.408] that includes zero.

**Honest selection.** The decisive test. For each held-out year the variant was
chosen by an inner leave-one-year-out sweep over the training years only, then
refitted and applied once to the held-out year, so nothing about the judged year
influenced the choice of model, features or penalty:

| onset, selection made inside the fold | AP | ROC-AUC | recall@3 | recall@5 |
| --- | --- | --- | --- | --- |
| variant selected in-fold | 0.017 | 0.412 | 0.600 | 0.800 |
| persistence | 0.058 | 0.871 | 0.600 | 0.800 |

Per-year AP difference: +0.032 in 2019, -0.131 in 2023, +0.000 in 2025 (in 2025
the selector chose persistence itself). Equal-year mean **-0.033**, interval
[-0.131, +0.032].

**The learned model does not beat persistence when it is chosen honestly.** With
three event seasons and ten onset transitions, the inner selection has at most
two event years to learn from and is too noisy to identify a better model. The
apparent gain was selection, not skill.

## 6. What is kept, and what is withdrawn

Kept, because each is verifiable independently of any skill claim:

- district-resolved rainfall for 1961 to 2025, varying in 98.7% of windows and
  physically consistent with the 2025 event;
- fold-safe priors and the season-boundary reset, both of which removed real
  leakage from the published evaluation;
- the onset and continuation decomposition;
- warning-shaped metrics and year-block intervals.

Withdrawn:

- any claim that the forecaster beats persistence, on any regime;
- any lead-time, advance-warning or "10-day forecast" language. The variant
  denied rain from inside the target window scores AP 0.010 on onset, so
  essentially all measured discrimination comes from rain observed during the
  window being scored. Rain falling inside a window can also postdate the
  inundation it is credited with anticipating, so even the opening-days variants
  are not validated forecasts without a daily rolling-origin test;
- probability language for the logistic variants. Class-balanced weighting leaves
  them badly calibrated, with Brier skill around -9.7 against climatology. They
  are rankers, not probability estimates.

## 7. Operational recommendation

Persistence is the operational baseline for district ranking, and the learned
model is experimental. This is not a failure of the pipeline; it is what the
available evidence supports. Ten onset transitions in three seasons is a small
sample, and reporting a selection artifact as skill would be worse than reporting
none.

## 8. What would settle it

- Daily rolling-origin evaluation predicting the first threshold crossing, using
  only rainfall through each issue date. Daily IMD and daily GFM rasters are both
  already available, so this is buildable without new sources.
- Onset robustness under hysteresis (previous fraction below 1%, subsequent above
  3%), across thresholds of 1, 2, 3 and 5%, and requiring two consecutive dry
  windows.
- Independent onset labels from Sentinel-1 or official 2025 records, since the
  current labels and the onset condition come from the same GFM product.
- Routed upstream catchment rainfall with travel-time lags of 0 to 4 days, and
  terrain covariates (height above nearest drainage, river proximity) from
  HydroSHEDS, which is keyless.
- More event seasons. This is the binding constraint and no method substitutes
  for it.
