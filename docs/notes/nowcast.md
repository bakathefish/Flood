# Live nowcast — daily district flood-onset ranking from keyless inputs

The last live layer: every monitor cycle, score each district's chance of the
satellite seeing flooding within the next three days, using the committed daily
forecaster (`data/models/forecaster_daily.joblib`) and live, no-login,
no-secret inputs, then write `monitor/nowcast.json` (the locked schema the site
reads).

The earlier 10-day-window model with rainfall and reservoir predictors
(`forecaster_2025.joblib`) is superseded and no longer deployed; see
`docs/notes/forecaster.md` for why and for the numbers that were retracted with
it.

Pure logic (window resolution, the cos²(lat) mask→district reduction, coverage,
JSON shaping) lives in `sailaab/nowcast.py`, TDD'd in `tests/test_nowcast.py`. All network / model IO lives in
`pipeline/fetch_live_inputs.py` (fetchers) + `pipeline/nowcast.py` (driver) — the
same pure/IO split as `sailaab.gfm` vs `pipeline.fetch_gfm`.

Run: `python -m pipeline.nowcast` (wired into `.github/workflows/monitor.yml`
after the `live_monitor` step).

## What it computes

The deployed forecaster consumes **exactly 10 features in training order**, all
of them derived from satellite flood observations. The order is asserted against
the committed bundle at load time and by `tests/test_forecast_live.py`.

| group | features | live source |
|---|---|---|
| prior (2) | `prior_wet_days`, `prior_max_fraction` | rebuilt per fold from earlier seasons only |
| observed (2) | `frac_now`, `frac_max3d` | GFM observed extent, issue day and trailing 3 days |
| season (1) | `day_of_season` | position in the monsoon grid |
| neighbour (1) | `neighbour` | flooded fraction in adjacent districts |
| climatology (1) | `season_climo` | district-week rate from earlier seasons only |
| excitation (3) | `excite_h0`, `excite_h1`, `excite_h2` | past flood days decayed at τ = 3 d, by graph hop |

**Rainfall is not an input.** It was tested as a feature family and measurably
did not improve the forecast, so it was dropped; reservoir storage was never in
the daily model. Both are still fetched and published as page context, under the
`context_rain` and `context_reservoirs` source keys, and neither moves the score.
The earlier 16-feature rain-and-reservoir model this file used to document is
superseded; see `docs/notes/forecaster.md`.

Output per district: `p_event` (an **uncalibrated ranking score**, or **null**
pre-core and wherever the forecast could not be made), `covered` (whether the
satellite returned usable imagery for that district), `observed_fraction_window`,
`observed_km2`, `rank`, `tier`, `transparent_score`. Plus `window_start/end`,
`core_season` (**null** when the run could not determine it), `activates`,
`sources`, an optional `forecast` block carrying the horizon, threshold,
operating point and an explicit `status` when unavailable, and free-text `notes`.

Despite the field name, `p_event` is not a probability. It has never been fitted
to a reliability curve. The name is kept because the published schema is locked;
every surface that renders it must present it as a ranking score.

## Sources

- **Rain — Open-Meteo** (`archive-api.open-meteo.com` ERA5 archive +
  `api.open-meteo.com` forecast, both keyless). A 3×3 cos(lat)-weighted point grid
  per box (Punjab plains `73.85–76.95E / 29.53–32.60N`; upstream Sutlej/Beas/Ravi
  `75.5–78.6E / 30.9–33.3N` — the same boxes as `pipeline/fetch_rain.py`),
  `daily=precipitation_sum`, merged **archive-first** with the forecast API's
  `past_days` filling the recent unsettled tail. Window sums: current window
  **so far** (days elapsed) + the two complete antecedent windows (lag1, lag2).
- **Observed labels — Copernicus GFM** observed flood extent via the keyless
  GloFAS WMS (recipe in `sailaab/gfm.py` / `pipeline/fetch_gfm.py`). Daily masks
  for the current window's days-so-far and the whole previous window, unioned,
  permanent (reference) water removed, reduced to per-district flooded
  fraction/km² with the same cos²(lat) Web-Mercator physics as the decade atlas
  that made the training labels (`pipeline/fetch_gfm_decade.py`) — so a live
  `antecedent_fraction` is in-domain with the trained target. One coarse ~380 m
  WMS tile per day keeps a run to ~18–21 requests (≤10 current + ≤10 antecedent +
  1 reference water), politely paced.
- **Reservoirs — CWC** daily-reservoir resource on data.gov.in (public sample key,
  `docs/notes/reservoirs.md`). Probed for 2026 rows for the 3 BBMB dams.

## Caveats (all surfaced in the JSON `notes`)

1. **Out-of-domain before Jul 25.** The forecaster was trained ONLY on core-season
   windows (`window_start` month-day ≥ `07-25`) because the Jun 15–Jul 15 windows
   are rice-transplant inundation, not floods (the paddy decision, quantified in
   `docs/notes/forecaster.md` / `gfm-decade.md`). When the current window starts
   before Jul 25, **`p_event` is `null`** for all districts and `activates` carries
   the countdown date (`<year>-07-25`); the observed GFM fractions are still
   reported. The model is only evaluated once the window is core-season.
2. **Rain is context, not an input.** Open-Meteo rain is fetched and published
   under `sources.context_rain` so a reader can see the weather beside the
   board. It does not enter the model. Rainfall was tested as a feature family
   during the daily rebuild and measurably did not improve the forecast, so it
   was dropped; nothing about the rain feed being degraded changes a score.
3. **Reservoirs are context, and currently dark.** The three BBMB dams (Bhakra,
   Pong, Ranjit Sagar) **stopped reporting to the CWC data.gov.in feed on
   2025-07-11** (`docs/notes/reservoirs.md`) and carry no 2026 rows; the
   endpoint is also slow and geo-restricted from CI. Reservoir storage is not a
   model input either, so this costs the forecast nothing.
   `sources.context_reservoirs = "unavailable"`.
4. **Coverage comes from the acquisition footprint.** `gfm_sentinel_1_footprint`
   is the boundary of the Sentinel-1 imagery each product was built from. It is
   intersected with every district, and the share imaged decides the state:
   `observed` (at least half the district), `partial`, `not_observed`, or
   `unknown` when the layer itself could not be retrieved.

   This matters more than any other line in this file. Sentinel-1 images a
   strip, not a state, and most days there is no pass over most of Punjab. On
   2026-07-25 the acquisition covered 14% of the Punjab bounding box and **19
   of 20 districts were never imaged**; before the footprint was wired in, all
   twenty published as observed with 0.0 km2 of water. An empty flood mask over
   a district nobody photographed is not a dry district.

   A district that is not `observed` gets `covered: false`, and then `p_event`,
   `rank` and `tier` all `null`: the model would happily score it from priors
   and climatology alone, and that number is indistinguishable from a real one.
   If statewide coverage or freshness falls below the gate, no forecast is
   published at all and the payload carries `forecast.status = "unavailable"`.
   No fragile scraping is done in CI.
4. **Coarse observed grid.** The nowcast reduces GFM at ~380 m (single tile/day)
   vs the decade atlas's ~100 m, to stay within the WMS request budget — small
   absolute-area differences, same method (union − reference water, cos²(lat)
   per-district fraction). S1 revisit means only some window days carry an
   acquisition; the `notes` report S1-active day counts.

## Never-fail contract

`pipeline/nowcast.py` must never fail the monitor job: any exception is caught, a
schema-valid **nulls** payload (all `p_event`/`observed_*` null, `sources`
unavailable, a `DEGRADED:` note) is written, and the process exits 0
(`tests/test_nowcast.py::test_degraded_payload_is_schema_valid_with_nulls`, plus a
live simulated-outage check).

## First real nowcast (run 2026-07-21)

Window `2026-07-15 – 2026-07-25` — **pre-core** (`core_season=false`,
`activates=2026-07-25`), so `p_event=null` (countdown UI). Live inputs:

- Rain (Open-Meteo): Punjab **48.3 mm** so far (7/7 elapsed days), upstream
  **54.4 mm**; antecedent window (Jul 5–15) Punjab 43.2 / upstream 65.5 mm.
- Reservoirs: **no 2026 data** (CWC feed dark) → `context_reservoirs=unavailable`.
  (Historical run, made under the superseded model, which did consume six
  reservoir features. The deployed model consumes none.)
- GFM observed (permanent water removed): 3 S1-active of 7 current-window days,
  4/10 antecedent-window days, 18 WMS requests. Top current-window observed
  extent: **Patiala 15.1 km² (0.45%)**, Firozpur 6.9, Tarn Taran 4.6,
  Gurdaspur 4.1, Sangrur 3.7, Amritsar 2.1 km² — river-corridor districts, the
  expected pattern.

Runtime ≈ 2 min (dominated by the ~18 paced WMS tiles).

## Citations

| source | dataset | licence / access |
|---|---|---|
| Open-Meteo | ERA5 archive + forecast `precipitation_sum` | **CC-BY 4.0**, free for non-commercial use, keyless (`open-meteo.com`) |
| Copernicus EMS | Global Flood Monitoring (GFM) observed flood extent, GloFAS Open WMS | Copernicus EMS, free & open, keyless (`ows.globalfloods.eu`) |
| CWC / data.gov.in | Daily reservoir level of Central Water Commission | Government Open Data Licence – India (GODL), public sample key (dark for BBMB dams since 2025-07-11) |
| Model / labels / prior | this repo's committed `forecaster_daily.joblib`, GFM decade atlas, late-season frequency table | see `docs/notes/{forecaster,gfm-decade,reservoirs}.md` |
