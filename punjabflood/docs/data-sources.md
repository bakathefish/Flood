# Data sources

All keyless. Access verified 2026-09-05 unless stated.

| source | what | access | span | notes |
|---|---|---|---|---|
| BBMB reservoir bulletin | Bhakra and Pong level (ft), inflow and outflow (cusecs), twice daily | `bbmb.gov.in/writereaddata/Portal/images/pdf/res_data.pdf` (PDF, incomplete TLS chain) | live only; BBMB keeps no archive | 45 bulletins captured 2026-08-09 to 2026-09-04 are committed in `data/reference/bbmb/` |
| CWC daily reservoir data | level (m), live storage (BCM), FRL, live capacity per reservoir | data.gov.in resource `1fc2148c-fc41-46f5-a364-bdc03f77053f`, sample key, 10 rows per call, throttled, intermittent 502 | 1991 to 2025-07-11 for the three BBMB dams | pulled by `punjabflood pull-cwc`; the feed stopped carrying these dams mid-2025; the feed answered 502 for the whole afternoon and evening of 2026-09-05, so the build ran on the seed file below |
| CWC seed file (predecessor project) | the same fields, monsoon months 2015 to 2025, daily in most seasons and weekly in 2023 | `data/reference/cwc/reservoirs_monsoon_2015_2025_legacy.csv` | 2015 to 2025 | has stale rows (storage repeated while the level moved) and a few 100 m level slips; reconciled in `reservoirs.py`, see `docs/design.md` |
| IMD gridded daily rainfall 0.25 degree | daily rain on the IMD grid over India (Pai et al. 2014) | yearwise files as downloaded by `imdlib`; the Sailaab archive at `../data/rasters/imd` (1.6 GB, not committed; override with `PUNJABFLOOD_IMD_DIR`) | 1961 to 2025 | the observed rain record; the grid stops at the border, so about half of the Bhakra catchment is uncovered and carried as coverage weights |
| BBMB hourly capture (Sailaab scheduled task) | the same bulletin records, one per new bulletin, private and uncommitted | `scripts/sync_bulletins.py` copies new records into `data/reference/bbmb/bulletins_2026.jsonl` | 2026 season | BBMB keeps no archive; this capture is the season's only history |
| Press supplement Aug to Sep 2025 | dated levels and percent full during the 2025 flood | SANDRP, The Tribune, Babushahi (see file) | 2025-08-01 to 2025-09-06 | `data/reference/cwc/reservoirs_2025_flood_supplement.csv` |
| Punjab WRD Flood Preparedness Guidebook 2026 | flood-intensity thresholds, 38-year annual peaks at Harike, Hussainiwala, Ropar, Dhilwan, travel times | PDF captured 2026-08-10 (not committed: personal phone numbers) | 1988 to 2025 | digitised to `data/reference/wrd/` and verified page by page |
| BBMB Pong Dam EAP, Bhakra ESDD report, DRIP screening template, BBMB at a Glance, RTDSS presentation | salient features: catchments, capacities, spillway and turbine passage | bbmb.gov.in, cbip.org | | quoted in `constants.py` with document and page |
| Punjab WRD dams page | Ranjit Sagar salient features | `wrd.punjab.gov.in/en/page/damsadministration` | | catchment 6,086 km2, spillway 24,637 cumecs |
| PSPCL Mukerian Hydel Project page | Mukerian Hydel Channel carrying capacity (the Beas diversion at the Shah Nehar barrage) | `pspcl.in/Otherlinks/mukerian-hydel-project-stage-i.aspx` (page dated 04-09-2026, fetched 2026-09-05) | | 11,500 cusecs; used as the most the river can lose below Pong |
| ERA5 event windows | ERA5 catchment rain for 6-20 Aug 2023 and 18 Aug-6 Sep 2025 beside the IMD values | `data/reference/rain/era5_vs_imd_event_windows.csv` (from the Open-Meteo archive API, 2026-09-05) | two windows | the rain-input check in `verification.md` |
| HydroBASINS v1c Asia level 8 | sub-basin polygons with downstream links | `data.hydrosheds.org` (34 MB zip) | | attribution required (Lehner & Grill 2013) |
| Open-Meteo archive API | ERA5 precipitation (0.25 degree), ERA5-Land soil moisture 0-7 and 7-28 cm, daily | `archive-api.open-meteo.com` | 1950 to about five days ago | weighted calls; the client sleeps through minutely and hourly limits. Used for the current season only: a 38-year pull for 222 grid points hit the hourly weighted limit after 66 calls and was replaced by the IMD archive |
| Open-Meteo forecast API | daily precipitation from GFS, ECMWF IFS 0.25, ICON, best match; `past_days` for recent analysis | `api.open-meteo.com` | 16 days ahead | one pull per day per point is cached |
| Open-Meteo ensemble API | ECMWF IFS 0.25 ensemble, 51 members, daily precipitation | `ensemble-api.open-meteo.com` | 7 to 15 days | |
| Open-Meteo historical forecast API | archived forecasts; `precipitation_previous_dayN` hourly gives the as-issued lead-N forecast | `historical-forecast-api.open-meteo.com` | previous-day variables from 2024-02 (GFS, ECMWF IFS 0.25, ICON, GEM, best match); stitched short-lead series from 2021 (GFS) | measured in this project, see `openmeteo.py` |

Dead ends, measured: India-WRIS returns no data for the reservoir dataset from any
egress tried; BBMB has no historical bulletin archive; GloFAS via the Open-Meteo flood
API misses the release floods by a factor of four to eight and is not used as a driver.
