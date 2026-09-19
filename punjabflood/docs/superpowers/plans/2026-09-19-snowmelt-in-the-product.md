# The Snowmelt Term in the Daily Product

> **For agentic workers:** Executed by one writer for the product path and one for the verification path in the same tree, tests first, smallest implementation that passes. Commits as the repository's own author with no attribution trailer.

**Why this plan exists.** `docs/superpowers/plans/2026-09-19-snowmelt-and-watch-hindcast.md` fitted a degree-day snowmelt term at Bhakra as a variant and said that a term passing its adoption rule would need its own plan to enter the product. The rule passed (`outputs/verification/results.json["snowmelt_verdict"]["adopt"]` is true; the numbers are in `docs/verification.md`). This plan carries the term into the parameters the product runs, into the live cycle, and into every score that uses those parameters.

**Written before the code (2026-09-19).**

## What the product does with the term

- **Parameters.** `python -m punjabflood.cli calibrate --melt` fits Bhakra with the melt block (the other dams unchanged) and writes `c_melt`, `w_melt` into `data/reference/inflow_params.json`. Without `--melt` the file carries no term, as before.
- **Recent melt.** The archive's melt at every Bhakra point, the pack carried from the 2014 spin-up through the fixed spans (`snow.MELT_SPANS`) and a tail span to the archive's latest day, one call per point per issue day (the tail's end date is part of the cache key). The last archive day is the last day every point has a temperature; later days in the response are dropped, not melted.
- **The gap and the horizon.** The primary model (`forecast.PRIMARY_DETERMINISTIC`) at the same points, its past days covering the days between the archive's last day and the issue date, its forecast days covering the horizon; the bucket continues from the archive's pack through those days. The catchment melt is the area-weighted mean over all the points and its volume over the whole catchment area of the catchment file, as in the fit.
- **In the model.** The recent melt over the same days as the recent rain enters `base_from_observed`, so the observed inflow is split between base, rain response and melt response; the horizon melt enters `predict_daily_bcm` for every deterministic model and every ensemble member. The product records the days, the melt, the pack at the issue date, the archive's last day and the source of every day (`archive` or the model's name).
- **Degrade.** If the melt inputs cannot be built (a pull fails), the product runs with the term contributing nothing that cycle and says so in the product; the cycle never fails on the melt.

## What is scored

- The flood-scale check, the as-issued hindcast, the live one-day test and the live horizon test all run on the parameters in the file, so with `--melt` they carry the term. In the hindcasts the melt over the horizon is the archive's (perfect prognosis for melt): the previous-runs archive holds no temperature or snowfall, so a forecast-melt hindcast is not possible from the record on disk. The size of that assumption is bounded in the verification by the term's horizon contribution (the melt response over five days at the term's fitted coefficient), reported beside the rain response.
- The adoption verdict compares the snowmelt variant against a no-melt refit of the baseline (the `baseline` row of the variant table), never against the parameters in use, so it reads the same whether or not the file carries the term.
- No level or threshold changes on the result.

## Tasks

1. [x] **Client and points.** `OpenMeteo.forecast_daily_weather(..., past_days)`; `rain.weather_points` returns the per-point frames the catchment means are made from, `rain.weather_catchment` uses it. Tests: the past days sit in the request; the catchment mean is the weighted mean of the points.
2. [x] **Bucket continuation.** `snow.MELT_SPANS`, `snow.live_spans(archive_end)`, `snow.last_complete_day(frames)`, `snow.extend_points(archive_frames, model_frames)` (archive rows to the last complete day, then the model's rows, a `source` column). Tests: a trailing day one point lacks is dropped; the model's rows start the day after; the pack carries across the join.
3. [x] **Melt inputs.** `forecast.melt_from_series(melt_df, issue_date, recent_days, horizon, area_km2)` selects the recent days and the horizon days and converts to BCM; `forecast.melt_inputs(client, catchments, params, issue_date)` builds them for every dam whose parameters carry the term. `build_product(..., melt=...)` applies them; `run` pulls them. Tests: a product built with a melt input has a lower base and a higher horizon inflow than without, for a parameter set with the term, and records the inputs; without the term the product is unchanged.
4. [x] **Calibrate and verify.** `calibrate --melt`; the verdict's baseline from the refit; the live one-day and horizon tests take the melt series; the horizon contribution reported. Tests: the CLI writes the term for Bhakra only; the verdict is unchanged by the file's parameters; the live horizon test with a melt series differs from without.
5. [x] **Run and record.** `calibrate --melt`, `verify`, `report`; `design.md` states what the product does with the term; the roadmap records the outcome with the numbers from `outputs/verification`; `data-sources.md` notes the daily archive tail and the model's past days.
