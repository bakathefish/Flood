# Calibration on Measured Inflow, the 2026 Bulletin Record (roadmap item 1, the calibration mode)

> **For agentic workers:** executed inline by a single writer, tests first, smallest implementation that passes. Commits as the repository's own author with no attribution trailer. Every number in the docs comes from `outputs/` through `punjabflood report`.

**Problem.** The runoff response is fitted on day-to-day storage change, which is inflow minus a release the record does not show; on days the dam passes more than its turbines the fit reads too little inflow. The bulletin capture that began on 9 August 2026 is the first daily inflow series this project has had (BBMB prints inflow twice a day). It is a deficit season, so it says nothing about flood scale, but it lets the same response be fitted on inflow and the storage-change fit be scored against measured inflow out of sample.

## Design
- `inflow.inflow_design(inflow_daily, rain, area_km2)`: one row per bulletin day with the daily mean inflow (BCM) as the target and the lagged rain volumes and antecedent index as columns.
- `inflow.calibrate_on_inflow(inflow_daily, rain, dam, area_km2, min_days=20)`: NNLS of inflow on the lagged rain volumes, the antecedent block and a non-negative constant base, the same cap iteration as `calibrate`; returns an `InflowParams` whose intercept is that base (so the storage-change convention, base minus passage, is not used; `basis` says so).
- `inflow.score_on_inflow(p, inflow_daily, rain, area_km2, absorption_cusecs)`: the storage-fit parameters applied to the same days, with base = intercept plus passage as the verification runs do: bias, Pearson r, MAE of daily inflow, and the ratio of the inflow-fit coefficient to the storage-fit coefficient.
- `verify` runs both for Bhakra and Pong on the bulletin days that have rain; `results["inflow_calibration_2026"]`; a CSV of observed and both predictions by day; the report prints the table.
- No adoption: one deficit season, in-sample. The product keeps the storage-change parameters; the ratio of coefficients is the measure of the release bias, printed with its caveat.

## Tasks
1. [x] `inflow_design`, `calibrate_on_inflow`, `score_on_inflow`; tests on a synthetic inflow series (the coefficient and lag weights are recovered; a storage-fit with half the coefficient scores a negative bias and a ratio near two).
2. [x] `verify` and `report`; test of the section.
3. [x] Docs (`design.md` calibration paragraph, roadmap item 1 note, README), suite green, commit, push.
