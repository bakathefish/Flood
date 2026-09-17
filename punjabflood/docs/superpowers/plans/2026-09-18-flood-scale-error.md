# Flood-Scale Error in the Spill Probability (roadmap item 6, on the record now in hand)

> **For agentic workers:** executed inline by a single writer, tests first, smallest implementation that passes. Commits as the repository's own author with no attribution trailer. Every number in the docs comes from `outputs/` through `punjabflood report`.

**Problem.** The product prints two spill probabilities: the share of ensemble members whose rain fills the reservoir, and the same with the inflow model's ordinary-day error sampled on top (additive, the calibration RMSE, its day-to-day persistence). The RMSE is measured on ordinary filling days, and the flood-scale check shows the model's flood volumes sit below the reported ones by a factor that varies from event to event, so the second probability is an inner estimate. Item 6 waited for a daily inflow record; what the record holds now is six period means of BBMB inflow over 10 to 24 days of the 2025 floods (daily quantities, the same scale as a horizon's volume) and 29 dated readings (moments, noisier than a daily mean).

## Design
- `verify.flood_scale_error(fs)`: from the flood-scale table, the log of model over reported for the period means covered on at least 10 days: their count, mean (the bias) and standard deviation (the spread); the dated readings' count and log spread beside them for the record.
- `verify` writes the period-mean spread to `data/reference/flood_scale_error.json` (committed, so the Action's runner has it) and to `results.json`; the report prints the parameters in the flood-scale section.
- `hei.ensemble_summary_with_error(..., scale_log_sd)`: on top of the ordinary-day additive error, one multiplicative factor per path drawn from a lognormal with that log standard deviation and no bias, applied to the whole path (a volume error persists through an event). Two more keys: the exhaustion probability and the peak-release quantiles under it.
- The product prints a third probability column, "QPF spread, model error and flood-scale volume error", for the FRL bound and the cushion scenario; the prospective record carries it.
- The bias is not applied. The flood-scale check says the model's flood volumes run low, but a scale factor on the inflow is the kind of correction the QPF test refused, and the product's numbers stay the model's; the spread makes the probability an outer estimate, which is what item 6 asked for.

## Tasks
1. [x] `flood_scale_error` and its test on a toy table (period means only; dated readings for the record; fewer than three periods gives no spread).
2. [x] `ensemble_summary_with_error(scale_log_sd=...)` and its test (a reservoir with headroom: the probability under the volume error is at least the one without; the keys are absent when no spread is given; seeded).
3. [x] Product: the parameter through `build_product` and `run`, the loader for the committed file, the Markdown column, the prospective-record column; tests.
4. [x] `verify` and `report`; docs (`design.md` third probability, README, roadmap item 6 to Done with its interim basis); suite green; commit, push.
