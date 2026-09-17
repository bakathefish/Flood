# IMD Real-Time Rain as the Product's Observed Record (roadmap item 4, the in-season half)

> **For agentic workers:** executed inline by a single writer, tests first, smallest implementation that passes. Commits as the repository's own author with no attribution trailer. Every number in the docs comes from `outputs/` through `punjabflood report`. The adoption rule is written here before the comparison is run.

**Problem.** The runoff model is calibrated on the IMD 0.25 degree gridded analysis. Live, the product carries the previous six days of observed rain from Open-Meteo's best-match model, and the in-season record on disk is ERA5. Both share ERA5's physics and resolution over these mountain catchments, and the rain input check in `verification.md` shows ERA5 saw 0.37 (Bhakra), 0.38 (Pong) and 0.59 (Ranjit Sagar) of the IMD rain over the August 2023 event. The wetness index and the lagged runoff of the live product therefore start from an observed record that can be half of what the model was fitted on.

**What was probed on 2026-09-17.** IMD Pune's real-time service (`https://imdpune.gov.in/cmpg/Realtimedata/Rainfall/rain.php`, a POST with `rain=DDMMYYYY`, the endpoint `imdlib` uses) returns one 129 x 135 float32 grid (69,660 bytes, the same 0.25 degree lattice as the archive) for days of the 2025 and 2026 seasons, including the day before the request, with no key. A 2023 day returned nothing. This is a preliminary analysis with fewer stations than the final yearwise file; how much closer it sits to the final grid than ERA5 does is the question the comparison answers.

## Design
- `imdrain.fetch_realtime(dates, rt_dir)`: downloads the days not yet on disk into `<imd_dir>/realtime/rain_ind0.25_YY_MM_DD.grd` (imdlib's naming); a body that is not exactly one grid is discarded; returns the dates present.
- `imdrain.open_real_days(dates, rt_dir)`: the days on disk as one DataArray (time, lat, lon) on the archive lattice, negative values as NaN, so `point_series` and `catchment_daily` work unchanged.
- `imdrain.catchment_daily_realtime(dates, catchments, rt_dir)`: catchment means, source `imd_rt`.
- `cli pull-rain-recent --source imd|era5` (default `imd`): the current season from the real-time grid where it has the day, ERA5 for the rest; `imd_rt` rows replace `era5` rows for the same day and are themselves replaced by `imd` when `build-rain` rebuilds the year.
- `forecast.recent_rain(...)`: for the catchments with IMD weights, each of the previous `RECENT_DAYS` days from the real-time grid when it is on disk or can be fetched, else from the best-match past day as now; the product records the source of every day (`recent_rain_source`) and the Markdown says how many of the six came from IMD.
- `verify.realtime_vs_final(final, realtime, era5, catchments, heavy_mm=30)`: per dam catchment over the 2025 season, real-time and ERA5 each against the final IMD grid: days, bias, r, MAE, heavy-day hit rate and false-alarm ratio; `switch` per the rule below.

## Adoption rule (written before the comparison)
The product's observed record switches from the best-match past days to the IMD real-time grid only if, over the 2025 season on the three dam catchments, the real-time grid's MAE against the final IMD grid is lower than ERA5's at every dam and its heavy-day hit rate is not lower at any. Otherwise the product keeps the best-match past days and the report records the refusal with the numbers.

## Tasks
1. [x] Reader and fetcher, with tests on a toy grid written to a temp dir (layout check against `imdlib.open_real_data` on the same file; a short body is rejected; missing days are skipped).
2. [x] `catchment_daily_realtime` test: the toy grid's catchment mean equals the archive path's on the same values.
3. [x] `verify.realtime_vs_final` test on toy frames: the rule fires only when both conditions hold at every dam.
4. [x] `forecast.recent_rain` test: a fake fetcher supplies IMD days for some of the six, the rest come from the fake client, and the sources are recorded in order.
5. [x] `pull-rain-recent --source imd`: replaces ERA5 rows; `build-rain` drops `imd_rt` for rebuilt years. Test on a toy CSV.
6. [x] **Outcome 2026-09-18: switch adopted** (the section in `verification.md` has the numbers; both conditions passed at every dam). Pull the 2025 season and the 2026 season to date; run the comparison in `verify`; render the section in the report; decide by the rule; `design.md`, `data-sources.md`, `README.md`, roadmap.
7. [x] Suite green, commit, push. The next hazard-forecast Action cycle proves the live path (the runner must reach imdpune.gov.in; the fallback covers it if not, and the product says which happened).

## Out of scope, stated
- The pre-2024 record stays the final IMD grid; the real-time grid exists only for the current and recent seasons.
- No blending of real-time and ERA5 on the same day: one source per day, named.
