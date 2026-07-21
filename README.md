# Sailaab — Punjab Flood Intelligence

**Open SAR-based flood mapping, decade hazard atlas, impact analytics, and district flood forecasting for Punjab, India.**

In August–September 2025 Punjab suffered its worst flood since 1988 — all 23 districts affected, ~3.55 lakh people, 1.48–1.75 lakh ha of crops. The satellite maps that could have guided relief existed, but locked in PDFs. Sailaab rebuilds that capability in the open: reproducible code, open data, public outputs.

## What it does

| Module | Output |
|---|---|
| **2025 Flood Atlas** | Sentinel-1 SAR flood masks (change-detection baseline + Random Forest), per-district statistics, validated against Copernicus GFM and ISRO NDEM products |
| **Decade Hazard Atlas** | Every monsoon 2015–2025 mapped with the same pipeline → flood-frequency raster, recurrence zonation, "repeat victims" village/tehsil table |
| **Impact engine** | Crop-loss hectares and ₹ value-at-risk, population exposure, flood depth (FwDET), the dam-release causal chart |
| **Forecaster** | XGBoost district flood-risk model trained on our own SAR-derived labels; leave-one-year-out validation; SHAP attributions |
| **Live monitor** | 6-hourly GitHub Action: new Sentinel-1 pass → flood stats → `monitor/latest.json` + Punjabi/Hindi/English alerts |

## Architecture

All decision logic lives in the pure-Python package `sailaab/`, developed strictly test-first (`tests/` mirrors it 1:1). Earth Engine / satellite side-effects are confined to thin scripts in `gee/` (Code Editor JS) and `pipeline/` (CLIs). Every cloud step is gated by a pre-declared numeric checkpoint in `docs/VERIFICATION-LOG.md` — the expected band is written down *before* the run.

```
sailaab/    pure, tested core (windows, stats, dataset, model, alerts, monitor, validation)
gee/        Wave-1 interactive GEE scripts (JS)
pipeline/   batch CLIs (decade runs, forecaster, live monitor)
tests/      pytest — every sailaab/ module covered
data/       small CSVs only (committed); bulk rasters stay local
atlas/      output maps and figures
docs/       METHOD.md (method paper), DATA-SOURCES.md, VERIFICATION-LOG.md
```

## Run the tests

```bash
pip install -r requirements.txt
python -m pytest -q
```

Earth-Engine-dependent tests are marked `ee` and excluded by default.

## Data sources

Sentinel-1 (Copernicus), FAO GAUL, JRC Global Surface Water, Copernicus DEM GLO-30, ESA WorldCover, GHSL population, IMD gridded rainfall, CWC reservoir data, Copernicus GFM and ISRO NDEM for validation. Full table with access dates and licenses: `docs/DATA-SOURCES.md`.

## Honesty rules

Training labels are bootstrapped from method agreement and labeled as such. Both spatial-CV folds are reported. Every headline number is stated next to the official figure it should be compared with. Known limitations (urban double-bounce under-detection, radar shadow in the Shivaliks) are documented, not hidden.

## Status

Active build for the India AI Impact Festival 2026 (student category). Core library and pipelines are complete and tested; satellite runs and validation are in progress this week.

## License

Code: [MIT](LICENSE). Generated maps, rasters, and tables: CC-BY-4.0 — use them, credit "Sailaab / Punjab Flood Intelligence".
