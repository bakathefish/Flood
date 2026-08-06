# The daily forecaster: forecasting flood onset three days out

The window forecaster did not beat a one-line persistence baseline, and
`forecaster-v2.md` records why and publishes that null. This note records what
replaced it and what the replacement can and cannot claim.

**Headline: it forecasts, and every number here is retrospective.**
Forecasting each district each day, three days ahead, using only what is known
when the forecast is issued and training only on seasons that had already
happened, average precision exceeded both a persistence baseline and a
transparent climatology-plus-neighbour rule in each of the four seasons
containing positive outcomes; one of those seasons contained only three positive
district-days. In 2025, the season with the most positive district-days in the
evaluated record, the temporally out-of-sample average precision was 0.299
against 0.141 for the transparent rule and 0.096 for persistence.

At a fixed five-district daily alert budget the transparent rule retrospectively
detected about 55 of 91 onsets against 48 for the model, making it the
provisionally preferred alerting method under that specific objective. The model
had better overall risk-ranking performance by average precision. The uncertainty
around that seven-event difference has not been quantified. Both are published.

**All 2019 to 2025 estimates are retrospective and post-selection**, because
aggregate results from these seasons informed which feature class was used.
Walk-forward results are emphasised because they reproduce deployment
chronology; the higher leave-one-year-out figures are reported only as a less
operationally realistic supplementary analysis. The 2026 monsoon is designated
the prospective confirmatory holdout, provided the pipeline and evaluation
protocol remain frozen until its outcomes are assessed.

Drivers: `pipeline/build_daily_district_flood.py` (labels),
`pipeline/run_forecaster_daily.py` (leave-one-year-out evaluation),
`pipeline/run_forecaster_walkforward.py` (the operational simulation that
produces the headline), `pipeline/run_forecaster_daily_audit.py` and
`_audit2.py` (the checks in sections 6 and 7).
Pure helpers and tests: `sailaab/forecast_daily.py`,
`tests/test_forecast_daily.py`, `tests/test_daily_flood_data.py`.

## 1. What was actually wrong

The old model asked a question no warning system asks. It scored a ten-day
window using rainfall drawn from inside that same window, so it could not
support any lead-time claim. Worse, the aggregation left seven windows per
district-season and only ten onset transitions across three event seasons, which
is far too little to select a model on.

The fix was not a better model. The Copernicus GFM pipeline had been fetching
**one flood mask per monsoon day for a decade** and unioning them into eleven
windows before anything downstream saw them. The daily rasters were on disk the
whole time. Reading them at native resolution turns seven decisions per season
into 107, and turns the question into the one an operator actually asks.

## 2. The forecast, stated precisely

On every monsoon day from 25 July, for every district not already flooded, using
only quantities known by the end of that day, predict whether that district's
flooded fraction will cross the threshold on any of the next three days.

Every feature is a trailing quantity ending on the issue date. Nothing dated
after the issue date can enter, which is what makes the lead time real rather
than nominal. The label is strictly forward and strictly excludes the issue day,
so it can never be satisfied by water already visible when the forecast is made.

Two choices were fixed before any model was fitted, both with physical
rationale, and the full four-by-four grid is reported rather than searched.

**Threshold 0.5% of district area.** The project's committed 2% was set for the
window product, where ten days of observations are unioned before the fraction
is computed. A single-day snapshot and a ten-day union are different quantities:
2% of a Punjab district in one satellite pass is 40 to 100 square kilometres of
standing water, which is an extreme reading rather than a warning threshold.
0.5% is 10 to 25 square kilometres, still thousands of acres.

**Horizon 3 days.** Rain over the upstream Himalayan catchments reaches the
Punjab plains in roughly one to three days, and a dam release reaches the
downstream reaches inside a day or two. Horizons of 1, 2 and 5 are reported
alongside.

## 3. Features

Trailing rainfall over 1, 3, 7 and 14 days, per district. Each district's 3-day
and 7-day rainfall expressed as a **percentile of its own 1961 to 2025
climatology** for that part of the season, so the model sees "this is a
1-in-20-year fall here" rather than a millimetre count that means different
things in the foothills and the southwest. Upstream box rainfall. Observed
sub-threshold water now and its three-day maximum. District susceptibility,
rebuilt inside each fold from training years only. Day of season.

## 4. Results

Leave-one-year-out over eleven monsoons, 14,412 candidate district-days, 287
positive district-days, base rate 1.99%.

| variant | AP | ROC | recall@3 | recall@5 |
| --- | --- | --- | --- | --- |
| **prior + state + season** | **0.173** | 0.797 | 0.557 | 0.638 |
| state only | 0.167 | 0.620 | 0.286 | 0.369 |
| everything incl. timing | 0.134 | 0.746 | 0.533 | 0.652 |
| everything | 0.106 | 0.664 | 0.530 | 0.645 |
| prior only | 0.056 | 0.743 | 0.526 | 0.557 |
| observation timing only | 0.040 | 0.715 | 0.031 | 0.056 |
| persistence | 0.026 | 0.482 | 0.073 | 0.105 |
| rain + climatology | 0.020 | 0.449 | 0.157 | 0.261 |
| rain only | 0.020 | 0.446 | 0.101 | 0.220 |

**Under selection performed strictly inside each fold**, so that nothing about
the judged year influences the variant, the features or the penalty:

| | AP | ROC | recall@3 | recall@5 |
| --- | --- | --- | --- | --- |
| selected in-fold | **0.152** | 0.741 | 0.314 | 0.383 |
| persistence | 0.026 | 0.482 | 0.073 | 0.105 |

Per-year difference against persistence: 2015 +0.044, 2017 +0.097, 2019 +0.003,
2022 +0.001, 2023 +0.198, 2025 +0.066. **Positive in all six event years.**
Equal-year mean +0.068, year-block interval [+0.020, +0.126], which excludes
zero. This is the test the window forecaster failed.

Sensitivity across all sixteen threshold and horizon combinations: the
prior + state + season variant is best in eleven of sixteen, and the best learned
variant beats persistence in **all sixteen**, including at the original 2%
threshold.

## 4b. Walk-forward: the number that actually counts

Leave-one-year-out lets a fold trained on 2016 to 2025 forecast 2015, which no
operator could ever do. The system was therefore re-run the way it would have
been operated: for each season from 2019, fit on every season strictly earlier
and forecast that season cold, never showing a model its own future.

Seasons 2019 to 2025, 9,137 candidate district-days, 272 positive district-days,
base rate 2.98%, 91 distinct onset events.

| scorer | AP | lift | row R@5 | event R@3 | event R@5 |
| --- | --- | --- | --- | --- | --- |
| **model** | **0.076** | **2.6x** | 0.434 | 0.429 | 0.527 |
| climatology + neighbour | 0.039 | 1.3x | 0.474 | 0.484 | **0.604** |
| persistence | 0.036 | 1.2x | 0.110 | 0.176 | 0.231 |

Per season, average precision, model / climatology+neighbour / persistence:

| season | model | climo + nbr | persistence | positive district-days |
| --- | --- | --- | --- | --- |
| 2019 | **0.028** | 0.015 | 0.018 | 24 |
| 2022 | **0.006** | 0.002 | 0.002 | 3 |
| 2023 | **0.155** | 0.148 | 0.110 | 131 |
| 2025 | **0.299** | 0.141 | 0.096 | 114 |

2020, 2021 and 2024 contain no positives and are undefined.

**In this retrospective walk-forward analysis the model's average precision
exceeded both comparators in each of the four seasons containing positive
outcomes**, one of which held only three positive district-days. In 2025, the
season with the most positive district-days in the evaluated record, the
temporally out-of-sample average precision was 0.299, against 0.141 for the
transparent rule and 0.096 for persistence. That single-season result rests on
114 positive district-days and is retrospective, because 2025 aggregate results
informed feature-class selection.

**At a fixed alert budget the transparent rule is still better at coverage.** At
five alerts per day it retrospectively detected about 55 of 91 onsets against 48
for the model. The leave-one-year-out figure of 0.812 fell to 0.527 under
walk-forward, the shrinkage that should be expected once a model can no longer
see its own future, and the reason the walk-forward number leads this note.

The honest operational reading is that the two do different jobs under different
objectives. The transparent rule is provisionally preferred for deciding which
five districts to warn. The model has better overall risk ranking, which is what
average precision measures. The uncertainty around the seven-event difference has
not been quantified, so neither is recommended categorically, and neither is
quoted without the other.

## 5. The observation-cadence problem, and how far it goes

GFM reports flooding only where a satellite acquisition covered the ground, so a
day with no detection can mean no water or no pass. "Water observed within three
days" is therefore partly a statement about when the satellite next looks. The
median gap between statewide non-empty observation days is two days.

A null model was built from acquisition cadence alone: statewide active
indicator now, 3-day and 7-day counts, and day of season, with nothing
district-specific. It reaches AP 0.040 against a base rate of 0.020, so cadence
genuinely carries some signal. But its recall@5 is **0.056**, because with no
district information every district in a given day receives the same score and
it cannot rank within a day at all.

That is the useful decomposition. Pooled AP partly rewards knowing which *days*
are floody, and cadence supplies some of that. Recall at k rewards knowing which
*district*, and cadence supplies none of it. The district ranking, which is what
an operator acts on, is not explained by the observation schedule.

**This does not fully close the question.** The null is statewide, so it cannot
rule out district-level ascertainment: a district might be both flood-prone and
more likely to be imaged. Settling that needs per-district valid-pixel coverage
for every day, which the GFM footprint layer does not reliably provide (it
nearest-value-falls-back to about 100%). It is stated as an open limitation, not
as a solved problem.

## 6. Three checks that could have overturned this

**Event-deduplicated recall.** A three-day horizon can label up to three
district-days for one flood, so per-row recall can count a single event three
times. Recall was recomputed over the 96 distinct onset events, each counted
once if any alert fired on any day that legitimately preceded it:

| scorer | row R@3 | row R@5 | event R@3 | event R@5 |
| --- | --- | --- | --- | --- |
| **model** | 0.557 | 0.638 | **0.615** | **0.708** |
| persistence | 0.073 | 0.105 | 0.167 | 0.219 |
| district wet rate | 0.031 | 0.056 | 0.031 | 0.062 |

Event recall is higher than row recall, not lower: 68 of 96 distinct onsets
caught in the top five, against 21 of 96 for persistence.

**De novo versus escalation.** If the skill lived only where water was already
visible, the system would be forecasting escalation rather than new flooding:

| group | n | positives | model | best baseline |
| --- | --- | --- | --- | --- |
| de novo, no water at issue | 12,712 | 265 | **AP 0.183, 8.8x** | **1.0x, no skill** |
| escalation, water below alarm | 1,700 | 22 | AP 0.091, 7.0x | 7.8x, persistence wins |

**265 of 287 positives, 92%, are de novo.** In that group every transparent
baseline scores exactly its base rate, meaning no skill at all, while the model
reaches nearly nine times it. In the much smaller escalation group persistence
beats the model, so the honest operational rule is: for a district already
showing water, carry it forward; for a dry district, use the model.

**Stronger baselines, and an error in the check itself.** Distance to threshold
and the combined hazard turned out to be monotone transforms of current water,
so they are rank-equivalent to persistence and score identically. That check did
not construct a stronger baseline and is reported as a flaw in the test rather
than as a result. The one genuinely different transparent hazard, the district's
historical wet-day rate, scores 0.020 against a base rate of 0.0199, which is
nothing.

## 7. What it is, and what it is not

It forecasts **what the satellite will observe**, not physical flooding
directly. The labels are GFM detections, so a flood the satellite never imaged is
not in the record. Metrics are evaluated against recorded GFM labels and may be
biased by unverified district-level acquisition and observation coverage.

It is **not learning hydrology from rainfall.** Rainfall adds nothing and
degrades average precision when added, even though onsets are genuinely
rain-driven (3-day antecedent rainfall is 1.87 times higher before an onset,
Mann-Whitney p = 8e-9). The association is real but too noisy at district scale
to rank on. What the model learns is an empirical hazard: which districts, at
which point in the season, with what recent water history, are about to be seen
flooding. That is useful and it is honest to call it that rather than a
rainfall-runoff model.

The retrospectively identified best variant reaches event recall@5 0.708; the
in-fold-selected system, which is what an honest deployment would have run,
reaches lower row recall because two of eleven folds selected a weaker variant.
Both numbers are reported and neither is quoted without the other.

Six event years is a small sample and the interval, while excluding zero, rests
on six blocks. Nothing here is a prospective result.

## 8. What would settle the remaining questions

- Per-district valid-pixel coverage per day, which converts the ascertainment
  limitation from unresolved to measured.
- A frozen variant and threshold tested on a future monsoon, which converts
  retrospective skill into prospective skill.
- Routed upstream catchment rainfall with travel-time lags and terrain
  covariates, which is the most plausible route to making rainfall contribute.
- Event-level lead-time distribution and alert-episode counting, to state warning
  time rather than only whether a warning occurred.
