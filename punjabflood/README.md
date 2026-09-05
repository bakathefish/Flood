# punjabflood

Physically grounded, keyless flood-hazard forecasting for the Punjab rivers.

Punjab's largest river floods (1988, 1995, 2023, 2025) are dam-release floods: multi-day
Himalayan rain fills Bhakra, Pong and Ranjit Sagar when they are already near full in late
August, the spillway gates open, and the wave reaches the Punjab plains on a clock the
state has published (Bhakra to Harike 52 hours, Pong to Harike 72 hours). This package
turns that mechanism into a daily hazard watch:

1. **State.** Reservoir level, inflow and outflow from the BBMB bulletin; storage from the
   dam's own level-storage relation fitted on the CWC record, with the record's stale and
   mistyped rows reconciled against that relation.
2. **Rain.** IMD 0.25 degree gridded daily rainfall (1961 to 2025) as the observed record,
   ERA5 through Open-Meteo for the current season, deterministic and 51-member ensemble
   quantitative precipitation forecasts (GFS, ECMWF IFS, ICON), all area-weighted over the
   real HydroBASINS catchments, all through keyless APIs.
3. **Inflow.** A calibrated runoff coefficient with lag weights, fitted on day-to-day changes
   of measured storage during filling season.
4. **Headroom-exhaustion index.** Forecast inflow volume minus headroom minus what the
   turbines can pass, per dam and horizon (1 to 5 days). Positive means the spillway must
   open: a full reservoir passes its inflow.
5. **Routing.** The forced release travels with the Water Resources Department's Annexure Z
   times to Ropar, Phillaur, Harike, Dhilwan and Ferozepur and is classed Low, Medium or
   High against the department's own thresholds.
6. **Verification.** 38 years of annual peaks with the department's High/Medium/Low class,
   the dated 2023 and 2025 Dhilwan peaks, the as-issued rain forecasts of 2024 to 2026, and
   the live 2026 bulletins. Results, with their caveats, are in `docs/verification.md`,
   rendered from `outputs/verification/` and never typed by hand.

Not an official warning. The Punjab WRD, CWC, BBMB and IMD issue those. This is a hazard
watch on physical quantities, published with its verification.

## What this is not

- No satellite-derived flood labels. Sentinel-1 revisit censoring makes them unusable as a
  forecast target for Punjab districts; the predecessor project retracted that claim.
- No district-level impact probabilities yet. That tier (document-derived onset catalogue,
  pooled hazard model) is a separate sub-project with its own pre-registration.
- No Ghaggar discharge model. There is no public gauge history for the Ghaggar; the
  package publishes the catchment rain forecast and its climatological percentile only.
- No claim to capture the extremes yet. The storage-change calibration undershoots the
  inflow of the 2023 and 2025 events (see the verification report); the daily CWC record
  from 1991 and the BBMB release chronologies are the data that fix this, and the pull is
  in progress.

## Run

This package lives in the Sailaab repository as the `punjabflood/` directory and reads the
IMD archive from the repository's `data/rasters/imd` (override with `PUNJABFLOOD_IMD_DIR`).
Run every command from this directory.

```
pip install -e .[dev]
python -m pytest                       # unit tests, offline
punjabflood pull-cwc                   # hours; resumable; the feed throttles hard
punjabflood build-catchments           # needs data/raw/hydrobasins/hybas_as_lev08_v1c.*
punjabflood build-rain                 # IMD gridded archive in data/raw/imd (imdlib layout)
punjabflood pull-rain-recent           # ERA5 for the current season, all catchments
punjabflood pull-qpf-archive           # as-issued QPF leads 1..7, 2024 to date
punjabflood digitise-guidebook         # needs the WRD guidebook PDF in data/raw/wrd/
punjabflood calibrate
punjabflood verify
punjabflood report                     # renders docs/verification.md
punjabflood forecast                   # one live cycle: outputs/forecast/<date>.{json,md}
python scripts/sync_bulletins.py       # new BBMB captures from the hourly task into data/reference
```

HydroBASINS: `https://data.hydrosheds.org/file/HydroBASINS/standard/hybas_as_lev08_v1c.zip`
(34 MB), unzip into `data/raw/hydrobasins/`. IMD gridded rain: the yearwise 0.25 degree
files as downloaded by `imdlib` (`<archive>/rain/<year>.grd`).

The daily prospective forecast runs in GitHub Actions
(`.github/workflows/hazard-forecast.yml` at the repository root) from committed data only:
the CWC seed record, the fitted parameters, the catchment files and the saved Ghaggar
climatology, plus the live BBMB bulletin and keyless Open-Meteo forecasts. Each cycle commits
`outputs/forecast/<date>.{json,md}`; earlier days are never rewritten.

## Layout

| path | what |
|---|---|
| `punjabflood/constants.py` | every constant with its source (dams, WRD thresholds, travel times) |
| `punjabflood/cwc.py`, `reservoirs.py` | CWC feed pull; state frame; level-storage rating; record reconciliation |
| `punjabflood/catchments.py`, `openmeteo.py`, `rain.py`, `imdrain.py` | catchments, keyless client, catchment-mean rain (ERA5, forecasts, IMD) |
| `punjabflood/inflow.py`, `hei.py`, `routing.py` | the model |
| `punjabflood/verify.py`, `report.py`, `forecast.py`, `cli.py` | verification, report, daily product, commands |
| `data/reference/` | committed, sourced tables: WRD digitisation (with `VERIFICATION.md`), catchment GeoJSON, BBMB bulletins captured in 2026, CWC seed files, fitted parameters |
| `docs/` | design, data sources, verification report, the implementation plan |

## Attribution

Weather data by Open-Meteo.com (CC BY 4.0). HydroBASINS: Lehner, B., Grill G. (2013),
Hydrological Processes 27(15). Gridded rainfall: Pai, D.S. et al. (2014), Mausam 65(1),
India Meteorological Department. Reservoir data: Central Water Commission via data.gov.in,
Bhakra Beas Management Board. Thresholds and travel times: Punjab Department of Water
Resources, Flood Preparedness Guidebook 2026.
