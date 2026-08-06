# The Sailaab flood forecaster

For every district in Punjab, on every day of the monsoon, using only what is
known when the forecast is issued: will Copernicus GFM observe flooding above
0.5% of that district's area within the next three days?

In retrospective, post-selection 2019 to 2025 walk-forward tests, the selected
gradient-boosting model had the best **pooled** ranking among the reported
candidates: average precision 0.249 against a 3.07% base rate. Read on before
quoting that number, because resampling takes most of it away.

**The pooled figure is very largely a 2025 result.** Remove that one season and
it falls from 0.249 to **0.042**. Every candidate falls too, so the model still
leads its baselines without 2025, but the headline is a statement about one
monsoon rather than about seven.

**The interval is enormous.** A two-stage block bootstrap, resampling seasons
and then seven-day blocks of whole days inside them, puts a 95% interval of
**[0.004, 0.521]** around it. Four seasons contained flooding; nothing measured
on four seasons is precise.

**By typical season the simpler model is better.** Averaged across the flood
seasons, the deployed model's mean AP is 0.176 and its median is **0.083**. The
same model with the excitation features removed has mean 0.159 and median
**0.133**. Pooled, excitation wins; in the median season, it loses.

**The excitation gain is probable, not established.** Compared on the same
resampled rows, the deployed model beats the no-excitation variant by +0.093,
interval **[-0.002, +0.268]**, ahead in 90% of draws. That is suggestive and it
is not significance. Against persistence the gap is +0.211, [-0.000, +0.484],
ahead in 97% of draws.

(An earlier version of this note quoted the excitation gain as +0.093 and the
persistence gap as +0.191. Those were the *means of the bootstrap draws*, not
the observed differences, which are +0.111 and +0.211. The resampling is there
to produce the interval; letting it silently restate the point estimate as well
was a mistake, and the code now reports the observed value with the bootstrap
interval around it.)

At the deployed alert setting it raised about 24 alerts a season, about a third
of which were followed by flooding within three days, while catching about one
recorded onset in four.

### What we are doing about the excitation question

The honest reading is that the deployed model is selected on pooled average
precision, and that a criterion built on the typical season would have chosen
the simpler variant instead. We are not swapping the model mid-season: the 2026
run is frozen, and changing the thing being tested while the test is running
would destroy the only prospective evidence this project will get. The
selection rule for the next cycle is written down now, before seeing 2026:
**maximise median AP across the seasons that contain flooding, with pooled AP
only as a tie-break.** On current evidence that rule selects the no-excitation
model, 0.133 against 0.083.

An earlier version of this paragraph added a guardrail, that the winner may not
lose more than 20% of AP to any candidate in any flood season, and claimed the
rule still selected the no-excitation model. **That was arithmetically false and
is withdrawn.** No-excitation loses 31.5% to the deployed model in 2025
(0.367 against 0.536), and the deployed model loses 40.3% to it in 2023
(0.145 against 0.243). A 20% relative guardrail rejects both candidates, so the
rule as written selected nothing at all. A guardrail may return once it is
calibrated against the season-to-season spread these four seasons actually
show, rather than picked because 20% sounded strict.

### A limit that no amount of resampling fixes

The target is defined by the same Copernicus GFM product the features are built
from. Predicting whether GFM will observe flooding, using GFM's own history, is
same-sensor autoregression rather than forecasting against independent
hydrological truth. There is no label leakage, since the future is never used
to build a feature, but the skill measured here is partly skill at predicting a
sensor. Performance against ground observations of flooding could be lower, and
this project has no independent daily ground truth to check that with.

**The ranking is the solid result. The alerting is modest and is reported as
such.** Episode-clean verification and prospective validation both remain
outstanding, and every estimate below is retrospective and post-selection. The
2026 monsoon, now in progress, is the prospective test and the protocol is
frozen.

An earlier draft of this note claimed 96% alert precision at four alerts a
season. That was an artifact of taking the alert threshold from the model's own
training predictions, which it had already fitted and therefore scores too
highly. Recomputed from out-of-fold scores the figure is about a third, and the
lower number is the one that stands.

Code: `sailaab/hazard.py`, `sailaab/forecast_daily.py`, `sailaab/forecast_live.py`.
Evaluation: `pipeline/run_forecaster_benchmark.py` (the architecture bake-off),
`pipeline/run_forecaster_walkforward.py`, `pipeline/run_forecaster_daily_audit*.py`.
Training: `pipeline/train_daily_forecaster.py`. Live: `pipeline/nowcast.py`.

## 1. What the design is, and where each piece comes from

The architecture was chosen after reading what operational flood forecasting
actually uses, not by trying models until one worked.

**Local LSTM training is unsupported at this sample size.** Google's operational
model is an encoder-decoder LSTM trained on about 5,680 gauges in the 2024 Nature
work and closer to 16,000 in the later operational update. This problem has 96
distinct flood onsets. That is not a claim that LSTMs cannot forecast floods,
which they plainly can; it is that nothing of that class can be trained here.

**Hawkes-like history features.** The recent flood literature routes water over a
river graph with a graph neural network, which is the right idea for Punjab,
where floods travel district to district along the Sutlej, Beas and Ravi. What is
implemented here is much weaker and should be described precisely: features
inspired by the self-exciting point-process family, not a fitted Hawkes process,
not a substitute for a GNN, and not a causal routing model. The graph is
undirected polygon adjacency rather than a directed river network, and most of
the weight sits on a district's own history rather than on propagation from its
neighbours. Past flood days are summed with exponential decay in time and by ring
in graph distance:

    excite_h<k>(district, day) = sum over districts exactly k hops away,
                                 and over earlier days t',
                                 of exp(-(day - t') / tau)

with `tau = 3` days, matched to the routing time from upstream catchment rain and
dam release to the plains, and rings 0, 1 and 2. Two interpretable constants
instead of a learned branching structure.

**Rare-event corrections, kept as tested diagnostics.** Firth's penalised
likelihood and the King and Zeng prior correction are implemented in
`sailaab/hazard.py` with tests, including the classic check that Firth stays
finite under perfect separation. Firth improved the linear model, both still lost
to boosting, so neither is in production and neither is claimed to make the
scores quotable as probabilities. That would require a calibration assessment
which has not been done. The deployed number is a ranking score.

**The metrics an operational service actually uses.** Average precision is a
machine-learning score. Flood warning is verified with probability of detection,
false alarm ratio and critical success index from a contingency table. Those are
now what the headline reports.

## 2. The forecast, stated precisely

On every monsoon day from 25 July, for every district not already flooded, using
only quantities known by the end of that day, predict whether that district's
observed flooded fraction crosses the threshold on any of the next three days.

Every feature is a trailing quantity ending on the issue date, and the label is
strictly forward and strictly excludes the issue day, so it can never be
satisfied by water already visible when the forecast is made. Tests pin both
properties, including one that adds a flood on the day *after* issue and asserts
no feature moves.

Two constants, both fixed before fitting, with the full four-by-four grid
reported rather than searched:

**Threshold 0.5% of district area.** The project's earlier 2% threshold was set
for a product that unions ten days of observations before computing a fraction.
For a single-day snapshot, 2% demands 40 to 100 square kilometres of standing
water in one satellite pass, which is an extreme reading rather than a warning
level. 0.5% is 10 to 25 square kilometres, still thousands of acres.

**Horizon 3 days**, matching the routing time.

## 3. Features

District susceptibility rebuilt inside each fold from training seasons only;
observed water now and its three-day maximum; day of season; water in adjacent
districts; the seasonal onset climatology for that district and week; and the
three self-excitation rings.

**No rainfall.** Rain added no measurable incremental skill under this model and
protocol, and degraded average precision when included, even though onsets are
genuinely rain-driven (three-day antecedent rainfall is 1.87 times higher before
an onset, Mann-Whitney p = 8e-9). The association is real but too noisy at
district scale to rank on. A useful side effect is that the live path depends on
no rain feed at all, so one fewer external service can fail.

## 4. The architecture bake-off

Walk-forward, seasons 2019 to 2025, 8,863 candidate district-days, 272 positive
district-days, base rate 3.07%. Rows whose three-day horizon was only partly
observed are censored out rather than counted as quiet, so a flood on a day the
satellite missed can never be scored as a correct negative.

| candidate | AP | lift | POD | FAR | CSI | Brier skill |
| --- | --- | --- | --- | --- | --- | --- |
| **gradient boosting + excitation** | **0.249** | **8.1x** | 0.460 | 0.944 | 0.052 | **+0.110** |
| gradient boosting, no excitation | 0.138 | 4.5x | 0.673 | 0.918 | 0.079 | +0.032 |
| Firth logistic + excitation | 0.092 | 3.0x | 0.426 | 0.948 | 0.048 | -0.042 |
| balanced logistic, King-Zeng corrected | 0.084 | 2.7x | 0.327 | 0.960 | 0.037 | -0.125 |
| balanced logistic | 0.075 | 2.4x | 0.426 | 0.948 | 0.048 | - |
| transparent rule | 0.040 | 1.3x | 0.474 | 0.942 | 0.054 | - |
| persistence | 0.037 | 1.2x | 0.114 | 0.986 | 0.012 | - |

The POD and FAR columns above are at a five-alerts-every-day operating point,
which is why they look so poor for every method: warning five districts daily,
straight through quiet weeks, sends almost every alert into an empty sky.
Section 5 replaces it with a threshold.

Per season, average precision:

| season | boosting | boosting, no excite | logistic | transparent | persistence | positives |
| --- | --- | --- | --- | --- | --- | --- |
| 2019 | 0.020 | **0.023** | 0.022 | 0.015 | 0.019 | 24 |
| 2022 | 0.003 | 0.002 | **0.006** | 0.002 | 0.002 | 3 |
| 2023 | 0.145 | **0.243** | 0.150 | 0.151 | 0.113 | 131 |
| 2025 | **0.536** | 0.367 | 0.298 | 0.145 | 0.100 | 114 |

Read that table honestly. The deployed model leads only in 2025. 2023 actually
carries more positive district-days (131 against 114), so 2025 is not the
biggest season by volume; it is the one where the learned score separates best,
and its scores are high enough to dominate a micro-pooled average. In 2023 the
same model without the excitation features scores 0.243 against its 0.145, so
the excitation is not uniformly helpful; in 2019 and 2022, where positives are
few, several candidates are within noise of each other and boosting is not the
best. Quote the pooled figure as a pooled figure, next to the seasonal mean of
0.176 and median of 0.083. A claim that it beats everything everywhere would be
false, and a claim that pooled 0.249 is the model's typical seasonal behaviour
would be misleading.

**Matched ablation**, identical learner, excitation removed: 0.249 falls to
0.138. This is a model-feature interaction rather than a universal result, since
the same features do nothing for the balanced logistic model (0.074 to 0.072),
and boosting without any excitation already beats logistic, so the learner
reversal is not purely an excitation artifact. XGBoost split-gain importance puts
excite_h0 at 0.42 and the three rings together above half the total, but split
gain is not a share of predictive skill and is not quoted as one.

**A correction to an earlier finding.** An earlier note in this project reported
that logistic regression beat gradient boosting. That was an artifact of working
at ten-day window resolution, where there were only 27 positives. At daily
resolution with 272 positives the usual result from the flood-susceptibility
literature holds and boosting wins clearly. The earlier claim was wrong and is
withdrawn here.

## 5. The operating point, which is where the system becomes usable

Warning five districts every single day, the operating point this project used
before, produces a false alarm ratio near 0.94 for every method, because it warns
straight through quiet weeks. The fix is to alert on a score threshold so that a
calm day produces no alert at all.

Threshold taken from **training scores only**, never from the season being
judged:

The threshold comes from an inner walk-forward inside the training seasons, so it
is taken from scores each inner model never saw. Because the later seasons flood
more than the seasons the threshold was derived from, the REALIZED alert volume
runs well above the nominal quantile, and only the realized number describes what
an operator would live with:

Every target-derived feature, the district priors and the seasonal climatology,
is rebuilt inside each inner fold, so an inner validation season cannot shape its
own features and later seasons cannot reach back into earlier folds.

| nominal | realized alerts/season | onsets warned | alert precision | FAR |
| --- | --- | --- | --- | --- |
| 0.02% | 20.6 | 22 of 91 (24.2%) | **0.375** | 0.625 |
| 0.05% | 23.0 | 22 of 91 (24.2%) | 0.342 | 0.658 |
| **0.1%** | **24.1** | 23 of 91 (25.3%) | **0.331** | 0.669 |
| 0.2% | 29.3 | 25 of 91 (27.5%) | 0.293 | 0.707 |
| 0.5% | 41.4 | 25 of 91 (27.5%) | 0.248 | 0.752 |
| 2.0% | 67.7 | 30 of 91 (33.0%) | 0.173 | 0.827 |

At the deployed setting the system raises roughly 24 alerts a season, about three
a week through the monsoon, and roughly one alert in three is followed by
flooding within three days while about one onset in four is caught.

That is a modest operational product and it is stated as one. **This is a
selective trigger for recorded GFM threshold crossings, not a comprehensive
flood-warning system.**

## 6. What it is not

It forecasts **what the satellite will observe**, not physical flooding directly.
A flood GFM never imaged is not in the record. Metrics are evaluated against
recorded GFM labels and may be biased by unverified district-level acquisition
coverage; the observation-cadence null in `forecaster-daily.md` bounds how much of
the signal the satellite schedule can explain but does not eliminate the question.

It is **not a rainfall-runoff model** and does not claim to have learned
hydrology. It learns an empirical hazard: which districts, at which point in the
season, with what recent flooding nearby, are about to be seen flooding.

**All numbers are retrospective and post-selection**, because aggregate results
on these seasons informed the choice of feature family. Four seasons contain
floods and one of those contains three positive district-days. The 2026 monsoon
is the prospective test.

## 7. Live

The 6-hourly monitor fetches 21 days of GFM district observations, builds the
issue-time features, scores every district, and publishes a self-describing
payload to `monitor/nowcast.json` carrying the horizon, the threshold, the alert
level and the definition of the number, so the feed cannot be misread as a
calibrated percentage chance.

Districts absent from a satellite pass are published as `covered: false` with a
null fraction. Not imaged and imaged-and-dry are different facts, and a warning
system must never render the first as the second.
