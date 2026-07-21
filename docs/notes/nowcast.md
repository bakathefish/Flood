# Live nowcast — current-window district flood risk from keyless inputs

The last live layer: every monitor cycle, predict the **current** 10-day monsoon
window's per-district flood risk with the committed forecaster
(`data/models/forecaster_2025.joblib`), from live, no-login, no-secret inputs, and
write `monitor/nowcast.json` (the locked schema the site reads).

Pure logic (window resolution, the exact-16 feature assembly, the cos²(lat)
mask→district reduction, JSON shaping) lives in `sailaab/nowcast.py`, TDD'd in
`tests/test_nowcast.py` (21 tests). All network / model IO lives in
`pipeline/fetch_live_inputs.py` (fetchers) + `pipeline/nowcast.py` (driver) — the
same pure/IO split as `sailaab.gfm` vs `pipeline.fetch_gfm`.

Run: `python -m pipeline.nowcast` (wired into `.github/workflows/monitor.yml`
after the `live_monitor` step).

## What it computes

The forecaster consumes **exactly 16 features in training order** (verified against
the committed joblib by `tests/test_nowcast.py::test_feature_order_matches_committed_model`):

| group | features | live source |
|---|---|---|
| rain (6) | `punjab_mm`, `upstream_mm`, + `_lag1`, `_lag2` for both boxes | Open-Meteo (archive + forecast) |
| reservoirs (6) | `{bhakra,pong,ranjit_sagar}_{storage,delta}` | CWC data.gov.in → **NaN** (feed dark, see below) |
| antecedent (1) | `antecedent_fraction` | GFM observed extent, previous window |
| season (1) | `week_of_season` | window index in the season grid |
| prior (2) | `prior_mean_annual_flooded_ha`, `prior_seasons_with_fraction_gt2pct` | `data/flood_frequency_districts_late_season.csv` |

Output per district: `p_event` (model probability, or **null** pre-core),
`observed_fraction_window` (current window flooded fraction so far),
`observed_km2`. Plus `window_start/end`, `core_season`, `activates`, `sources`,
free-text `notes`.

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
2. **Open-Meteo ≠ IMD calibration.** The model trained on IMD 0.25° gauge-based
   rain; Open-Meteo serves ERA5 (reanalysis) + a forecast blend. Absolute rain
   magnitudes are **not identically calibrated** — the rain features are a
   consistent proxy, not a like-for-like reproduction of the training rain. (If a
   fast IMD 2026 NRT path via `imdlib` becomes available, prefer it and record
   `"rain": "imd"`.)
3. **Reservoirs unavailable → NaN.** The three BBMB dams (Bhakra, Pong, Ranjit
   Sagar) **stopped reporting to the CWC data.gov.in feed on 2025-07-11**
   (`docs/notes/reservoirs.md`) and carry no 2026 rows; the endpoint is also
   slow/geo-restricted from CI. The 6 reservoir features are therefore set to
   `NaN`, which the XGBoost model ingests natively (it already trained with the
   2025 post-Jul-11 reservoir gap missing). `sources.reservoirs = "unavailable"`.
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
- Reservoirs: **no 2026 data** (CWC feed dark) → 6 features NaN,
  `reservoirs=unavailable`.
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
| Model / labels / prior | this repo's committed `forecaster_2025.joblib`, GFM decade atlas, late-season frequency table | see `docs/notes/{forecaster,gfm-decade,reservoirs}.md` |
