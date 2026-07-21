# Sailaab — Method

## 1. Software architecture
Decision logic lives in the pure-Python `sailaab/` package, developed test-first
(pytest, tests/ mirrors the package 1:1). Earth Engine effects are confined to
`gee/*.js` and thin `pipeline/*.py` CLIs. Constants (thresholds, windows,
spatial folds, official comparison bands) are centralized in `sailaab/config.py`.
GEE steps use pre-declared acceptance checkpoints (see VERIFICATION-LOG.md).
<!-- Sections 2+ appended by later plans: 2 Mapping, 3 Decade, 4 Validation,
     5 Forecaster, 6 Monitor -->

## 2. Data acquisition — login-free by design
The original design used Google Earth Engine as the compute stack. During the build we
proved a fully account-free acquisition path and adopted it as primary, keeping GEE as
an optional mirror: Sentinel-1 RTC via Microsoft Planetary Computer's anonymous STAC
(windowed COG reads at 60–90 m working resolution; SAS tokens re-signed on expiry),
Copernicus GFM flood/reference-water layers via the keyless GloFAS WMS (daily,
2011-present, decoded from styled tiles by exact palette match), IMD 0.25-degree daily
rainfall via imdpune yearwise files, CWC reservoir series via the data.gov.in OGD API
(with a cited BBMB/press supplement for the Aug-Sep 2025 window, during which the three
BBMB dams stop reporting to the central feed on 2025-07-11), and Census-2011 district
polygons (datameet) whose vintage matches the GAUL-2015 lists used for spatial folds.
Every step above carries a pre-declared checkpoint in VERIFICATION-LOG.md; full recipes
and dead ends (EMS vector login wall, WRIS geo-block, AIKosh login) in docs/notes/.
