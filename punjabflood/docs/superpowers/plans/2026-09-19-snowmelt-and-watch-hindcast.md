# A Snowmelt Term at Bhakra, and the Weather Watch Scored on the Archive

> **For agentic workers:** Executed inline by a single writer, tests first, smallest implementation that passes, then the next task. Commits as the repository's own author with no attribution trailer. Every number in the docs comes from `outputs/` through `punjabflood report`; nothing is typed by hand. Adoption rules are written here before any fit is run.

**Goal:** the two accuracy steps the keyless record still allows after the 2026-09-19 sprint. Bhakra is the dam where the rain response barely beats persistence, and its base is snowmelt that the model carries as a constant intercept; a melt term is the one physical input not yet tried there. The weather watch has pre-registered levels but no score; the as-issued archive lets it be run day by day over three seasons, one with the 2025 event.

**Probed on 2026-09-19 (before any of this):** the CWC feed on data.gov.in answers 429 at once and stopped carrying the three dams in mid-2025; India-WRIS times out on connect from this egress (as on 2026-09-05); so no daily storage record beyond the one in hand exists for calibration, and roadmap item 1 stays an owner action. The Open-Meteo archive serves daily `snowfall_sum` (cm), `temperature_2m_mean` and `precipitation_sum` for any point 2015 to 2025; a daily snow water equivalent is not served. The Bhakra catchment holds 131 archive points (71 inside the IMD grid, 60 outside, in Kinnaur, Spiti and Tibet, where the snow is).

**Checked on 2026-09-19, no code needed:** the live product reads the reservoir level from the BBMB bulletin on every cycle (`forecast.dam_state_from_bulletin`) and rates it to storage, so the 2026 loop is anchored on the measured state daily; nothing is carried from the model between cycles.

---

## Part A: snowmelt at Bhakra

### The term
Per archive point, a temperature-index snowpack: `pack_t = pack_{t-1} + snow_t - melt_t`, `snow_t` the day's snowfall as water (cm of snow at 10 mm of water per 7 cm, the constant already in `weather.py`), `melt_t = min(pack_{t-1} + snow_t, DDF * max(T_t - 0 C, 0))` with `DDF` fixed at 4.0 mm per degree-day (the middle of the Himalayan range in Hock 2003, *J. Hydrol.* 282, 104; the coefficient below absorbs the scale, the factor only sets how fast a pack drains). The pack starts empty on 2014-01-01, a spin-up year before the first fitted season, and is carried through every day of the year to the rain table's last day, so a June value has the winter behind it and the 2026 horizon days have melt. The catchment melt `melt_mm_t` is the area-weighted mean over all 131 points, and its volume over the whole catchment area of the catchment file (52,765 km2 at Bhakra, the sum of the 131 point weights, not the IMD-covered half) enters the storage-change relation as a lagged block with its own non-negative coefficient and lag weights, fitted jointly with the rain response by the same NNLS:

`ds_t = coefficient(api) * sum_k w_k rv_{t-k} + c_melt * sum_k w_melt_k mv_{t-k} + intercept`

The intercept stays free, so the term only wins what a season-varying melt explains beyond a constant base.

### Adoption rule (written before the fit)
`verify.variant_verdict` restricted to the one dam the term touches: at Bhakra the leave-one-season-out RMSE may not rise, Bhakra's season-peak ratio in the flood-scale check must rise, and Bhakra's period means may not move further from the reported means than the baseline's worst Bhakra one does. Pong and Ranjit Sagar are unchanged by construction. Otherwise the product keeps the baseline and the report records the refusal with the numbers. If adopted, the product needs the recent melt from the archive (five days behind) and the primary model's temperature and snowfall for the horizon, which are already pulled for the watch; that integration is a second plan.

### Tasks
1. [ ] **Pull.** `scripts/pull_snow_bhakra.py`: one archive call per point and span (2014 spin-up, 2015 to 2025, 2026 to the rain table's last day), cached; the per-IP daily quota is spread over GitHub Actions runners with `scripts/pull_snow_points.py` and `.github/workflows/snow-pull.yml`; the catchment means to `data/raw/rain/snow_bhakra_daily.csv` (gitignored with the rest of `data/raw/rain`).
2. [x] **Bucket.** `snow.degree_day_melt(snow_mm, t_c, ddf, t0)` returns pack and melt; `snow.catchment_melt(client, catchment, start, end)` rebuilds the per-point series from the cache and returns the daily area-weighted `melt_mm`, `pack_mm`, `snowfall_mm`, `t2m_mean_c`. Tests: no snow gives no melt; a 10 mm fall at +5 C melts fully at 20 mm per degree-day capacity, and at 1 C melts 4 mm a day; the pack never goes negative; the catchment mean weights by area.
3. [x] **Term.** `InflowParams` gains `c_melt`, `w_melt`; `design_matrix` builds `melt{k}` (zeros without a `melt_bcm` column); `calibrate(..., melt=True)` fits the block; `predict_storage_change` and `quick_response_bcm` add it; `loso_score(..., melt=True)`. Tests: with `c_melt` 0 nothing changes; with a unit melt column the fitted term recovers a planted coefficient.
4. [ ] **Verification.** `snowmelt` joins the variant table for Bhakra only; `verify.variant_verdict(..., dams=("Bhakra",))`; `results.json["snowmelt_verdict"]`; a paragraph and the row in `verification.md`; `design.md` states the term and the rule; the roadmap records the outcome.

## Part B: the weather watch on the as-issued archive

### The score (written before the run)
For every issue date of the 2024, 2025 and 2026 monsoon seasons (June to September, the days the archive has all three of AIFS, IFS and GFS at leads 1 to 3; AIFS begins March 2025, so 2024 runs on IFS and GFS) and every dam catchment, the deterministic-only branch of `weather.level` as it stands: the primary model's next-three-day total placed in the monsoon three-day totals of every year of the rain table (1961 to the latest day on disk, the scored seasons included), and the share of models with a 30 mm day. No ensemble is archived, so the ensemble conditions cannot be scored; the branch scored is the one the product would run without an ensemble.

Truth, fixed now from the reference tables: at Bhakra the dated floodgate opening of 2025-08-19 (`gate_openings.csv`); at Pong and Ranjit Sagar the day of the largest dated inflow reading of 2025 in `inflow_points.csv` (2025-08-26 and 2025-08-27). For each event: the first issue date at watch and at alert within the 14 days before it, and the lead in days (none if the level never rose). For every season: the share of issue days at each level, with the 14 days before an event and 7 after it excluded from the false-alarm count. 2024 and 2026 are seasons without a dam event, so every watch or alert day there counts against the rules.

No level is changed on the result; the score is reported, and a change would be a new plan with its own rule.

### Tasks
5. [x] **Hindcast.** `verify.weather_watch_hindcast(qpf_leads, climatology, events, models, primary)` returns one row per issue date and catchment (`level`, the primary three-day total and percentile, the models with a heavy day) plus the event summary; `outputs/verification/weather_watch_hindcast.csv`, `results.json["weather_watch_hindcast"]`. Tests on a toy archive: a quiet season gives no watch days; a 40 mm day in one model gives a watch; a total above the 90th percentile gives an alert and a lead of the right length.
6. [x] **Report.** The table and a paragraph in `verification.md`; the roadmap notes what the watch did.

## Out of scope, stated
- No fitted degree-day factor; no per-band elevation model; no ensemble hindcast (none is archived).
- No post-processing of the live product against the poller yet: the 2026 season is one deficit season of about five weeks of readings, and a correction fitted on it could not be held out. It waits for a second season.
