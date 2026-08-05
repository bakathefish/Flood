# Forecaster v2: district-resolved rainfall, onset versus continuation, and a negative result

The v1 district forecaster lost to a one-feature persistence baseline on PR-AUC
(0.269 against 0.308). This note records why it lost, what was rebuilt, and what
the rebuild did and did not fix.

**Headline: no improvement over persistence is demonstrated here.** An apparent
large gain on flood onset did not survive choosing the model without seeing the
year it was judged on. The data product and the evaluation fixes are real and
are kept; the skill claim is withdrawn. This is not a finding that learned
models are intrinsically worse, and the note is careful to keep that distinction
throughout: with three event seasons the sample cannot settle it either way.

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

## 2. District-level rainfall series

From the IMD 0.25 degree daily grid, Sailaab now derives district-level rainfall
series for all 20 districts in the project's Punjab boundary layer, for 1961 to
2025. These series show district-level variation within 98.7% of the defined
monsoon windows, whereas the previous two-box statewide predictors provide none. **This is a data and
monitoring contribution; it is not evidence of improved flood-forecast skill.**

To be precise about what this is and is not: it is spatial *aggregation* of an
existing 0.25 degree product to district polygons, not downscaling, and it
creates no information below the IMD grid resolution.

Method. Each district's series is the area-weighted mean of the grid cells it
overlaps. Weights are the intersection area of the cell with the district polygon,
scaled by `cos(latitude)` to correct for meridian convergence, normalised to sum
to 1 per district. Area weighting is necessary rather than decorative here,
because Punjab districts are comparable in size to a single 0.25 degree cell
(6 to 19 cells per district) and a centroid-in-cell rule would drop the smallest
districts entirely. Cells carrying the IMD no-data sentinel are excluded and the
surviving weights renormalised, so a partially masked district reports the mean
of the cells that reported rather than a value pulled toward zero; a district
whose cells are all missing reports no value rather than a zero. Windows are
half-open, matching the decade grid, so adjacent windows never double-count the
seam day. Behaviour is pinned by 19 tests in `tests/test_rain_districts.py`,
including weight normalisation, area proportionality, latitude weighting,
multipolygon handling, and the missing-data renormalisation.

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
model take credit for water already on the ground. Of the 27 observed positive
district-windows, 17 were continuation cases in which water was already present
and 10 were onset transitions from dry to flooded. The rule is explicit: rows
whose previous-window flooded fraction is at or below 2% form the onset risk set,
and a positive row in that set is an onset transition; rows above 2% form the
continuation risk set. Split by year:

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

In the three onset event-years available, fold-internal model selection did not
produce a learned variant that outperformed persistence: selected-model AP was
0.017 versus 0.058, with identical recall@3 and recall@5. Because inner selection
had at most two event-years, this evaluation does not establish that learned
models are intrinsically worse; it shows that no improvement over persistence is
demonstrated here. Persistence therefore remains the operational baseline, and
learned variants remain experimental. The previously reported district-rainfall
gain did not survive fold-safe model selection and should not be interpreted as
demonstrated out-of-sample forecasting skill.

## 5b. Continuation, and the whole task

Continuation is the majority of the positives, so leaving it unreported would
leave most of the task uncharacterised. The same in-fold selection procedure,
applied to each regime:

| regime | rows | positives | prevalence | selected AP | persistence AP | selected R@3 | persistence R@3 | selected R@5 | persistence R@5 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| onset | 1,484 | 10 | 0.0067 | 0.017 | 0.058 | 0.600 | 0.600 | 0.800 | 0.800 |
| continuation | 56 | 17 | 0.3036 | 0.260 | 0.402 | 0.824 | 0.824 | 1.000 | 1.000 |
| all rows | 1,540 | 27 | 0.0175 | 0.102 | 0.308 | 0.667 | 0.667 | 0.852 | 0.889 |

Continuation positives fall in 2023 (9) and 2025 (8); onset positives in 2019 (2),
2023 (2) and 2025 (6). Per event-year AP difference against persistence is
+0.000 in both continuation years, because in both the selector chose persistence
itself; on all rows it is +0.000 in 2019, -0.189 in 2023, +0.000 in 2025, equal-year
mean -0.063.

Variants chosen by the selector, by regime: onset picked district rain in 7 folds,
statewide rain in 2, the opening-5-day variant in 1 and persistence in 1;
continuation picked persistence in 3 and learned variants in 3; all rows picked
persistence in 9 of 11. Selection differed by regime: persistence was chosen in
1 of 11 onset folds, 3 of 6 continuation folds, and 9 of 11 all-row folds; none
of the resulting selected systems demonstrated an aggregate advantage over
persistence. Recall at the operating budgets is identical to persistence in every
regime except all-rows recall@5, where persistence is better.

Persistence is stronger on continuation than anywhere else, which is what the
physics predicts: water observed last window is usually still there.

## 6. What is kept, and what is withdrawn

Kept, because each is verifiable independently of any skill claim:

- district-resolved rainfall for 1961 to 2025, varying in 98.7% of windows and
  physically consistent with the 2025 event;
- fold-safe priors and the season-boundary reset, which respectively removed
  target leakage and unintended cross-season state carry-over from the published
  evaluation;
- the onset and continuation decomposition;
- warning-shaped metrics and year-block intervals.

Withdrawn:

- any claim that the forecaster beats persistence, on any regime;
- any lead-time, advance-warning or "10-day forecast" language. In the
  learned-model ablation, excluding rainfall observed inside the scored window
  reduced onset AP to 0.010; the reported discrimination should therefore be
  interpreted primarily as contemporaneous association, not advance warning.
  Rain falling inside a window can also postdate the inundation it is credited
  with anticipating, so even the opening-days variants are not validated
  forecasts. Any lead-time claim requires a daily rolling-origin evaluation.
  This restriction is about the learned model: persistence itself discriminates
  strongly, and the rain-denied learned variant retains AP 0.010 rather than
  nothing;
- probability language for the logistic variants. Class-balanced weighting leaves
  them badly calibrated, with Brier skill around -9.7 against climatology. They
  are rankers, not probability estimates.

## 6b. What the audit itself established

The audit is not only an absence of improvement. It established three specific
things, and they are the reason this note exists rather than a quiet revision:

- the fold-safe selected system improved neither reported recall budget in any
  regime, so the negative result holds at the operating points a user would
  actually act on, not merely on an aggregate score;
- aggregate selected average precision was below persistence in the onset,
  continuation and all-row evaluations alike, so the conclusion does not depend
  on which slice is chosen;
- the original apparent rainfall gain was traced rather than left unexplained. It
  decomposes into learner choice, the temporal availability of the rainfall used,
  and the selection procedure itself, which is why the note can say what went
  wrong instead of only that something did.

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
