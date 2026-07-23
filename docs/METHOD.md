# Sailaab: Method

## 1. Software architecture
Decision logic lives in the pure-Python `sailaab/` package, developed test-first
(pytest, tests/ mirrors the package 1:1). Earth Engine effects are confined to
`gee/*.js` and thin `pipeline/*.py` CLIs. Constants (thresholds, windows,
spatial folds, official comparison bands) are centralized in `sailaab/config.py`.
GEE steps use pre-declared acceptance checkpoints (see VERIFICATION-LOG.md).
<!-- Sections 2+ appended by later plans: 2 Mapping, 3 Decade, 4 Validation,
     5 Forecaster, 6 Monitor -->

## 2. Data acquisition, login-free by design
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

## 3. Mapping (Wave 1)
Tier-A: per-orbit median composites (pre Jul 1-Aug 10, flood Aug 25-Sep 6 2025), dVV < -3 dB
AND VV_flood < -15 dB, permanent-water exclusion, 10-px sieve, 90 m statewide (details:
notes/pc-sar.md, notes/rf-train.md). Tier-B: RandomForest (200 trees) on VV/VH/dVV/dVH/slope;
labels = Tier-A x GFM agreement strata (stated as bootstrapped); spatial CV across the
Ravi-Beas / Sutlej basin folds; independent fresh-point check vs GFM. All bands pre-declared.

## 4. Decade + labels (Wave 2)
GFM daily observed flood extent 2015-2025 (467 flood-active days), unioned per 10-day window,
minus reference water, rasterized to districts -> 2,420 label rows + per-pixel season-frequency
raster. Discovery: June-mid-July windows carry a ~20x rice-transplant signature; calibrated
late-season companion products ship alongside raw (notes/gfm-decade.md).

## 5. Forecaster (Wave 4)
District x window unit; predictors: IMD rain (local + upstream boxes, lags), reservoir storage
and delta (CWC/BBMB), antecedent fraction, week-of-season, frequency prior. XGBoost, LOYO CV,
transplant windows excluded from fit and eval; leakage check with fold-safe priors. 2025 holdout:
5/5 flood districts flagged, ~10-day lead (notes/forecaster.md).

## 6. Live monitor (Wave 5)
Secretless GitHub Action (6-hourly): anonymous PC STAC scene watermark (sailaab/monitor.py),
coarse VV composite of new scenes vs committed 150 m pre-monsoon reference, Tier-A rule,
district km², PA/HI/EN alerts, state committed to repo (notes/monitor-rw.md).
