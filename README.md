# Sailaab — Punjab Flood Intelligence

**Open SAR-based flood mapping, decade hazard atlas, impact analytics, and district flood forecasting for Punjab, India.**

**Live:** https://bakathefish.github.io/Flood/ — interactive district map (2025 flood / decade frequency / forecast risk layers, click for per-district stats), before/after SAR swipe, live monitor readout. Monitor auto-runs every 6 h on CI, no keys — see `monitor/latest.json`

*11 monsoons · 467 flood days · 105,183 ha mapped (2025) · 20 districts · 3 languages · 2 space agencies · 0 logins required.*

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

## Results (2025 event + decade)

- **2025 statewide SAR-flooded area:** 105,183 ha (Tier-A change detection, 90 m, full coverage); RF map with spatial cross-validation across river basins; three-method envelope vs Copernicus GFM published.
- **Crop impact:** 36,195 ha of cropland flooded in the peak-window snapshot ≈ **₹546 crore** paddy value at risk (order-of-magnitude, MSP-based; official cumulative-season figure is 1.48–1.75 lakh ha — divergence explained in the method notes).
- **Decade atlas:** Punjab's first public flood-frequency map (2015–2025); 2025 confirmed the worst season of the decade on both raw and calibrated metrics; "repeat victims" district table included. The June–July paddy-transplant contamination in SAR flood products is documented and calibrated out.
- **Forecaster:** XGBoost on the pipeline's own 2,420 SAR-derived labels; leave-one-year-out ROC-AUC 0.946 (leakage-checked). Trained on 2015–2024 only, it flagged all five of the SAR atlas's most-flooded districts (girdawari-corroborated; Kapurthala #1) with ~10 days of pre-crest lead on the dam-release peak. SHAP: antecedent flooding, flood-history prior, Bhakra storage.
- **Tehsil-level relief targeting:** 91 tehsils scored; named repeat-victims list (Khadur Sahib 6/11 seasons, Sultanpur Lodhi 5/11) — `data/tehsil_repeat_victims.csv`.
- **Population exposure:** 0.76–1.78 lakh people inside the mapped 2025 water (GHSL, conservation-checked) vs 3.55 lakh officially affected — relationship explained in the notes.
- **Ground-truth agreement:** satellite damage ranking vs the Revenue Dept's Special Girdawari table: **ρ = 0.72** (all 20 districts; 0.56 over the 16 officially named), 5 of top-6 identical. ₹ VaR v2 rebuilt on DES district paddy yields (₹523 crore). Submergence-duration atlas: 51,202 ha ≥7 days; duration-weighted damage ₹351 crore. 65-year rain-trend analysis (pre-registered Mann-Kendall): loading largely stationary; upstream extreme-wet-day frequency rising (p=0.017).
- **Live monitor + nowcast:** secretless GitHub Action, every 6 h — latest pass, district km², trilingual alerts, and (from Jul 25) live district flood-risk probabilities from the forecaster.

Festival packaging: `docs/SYNOPSIS.md`, `docs/VIDEO-SCRIPT.md`.

## License

Code: [MIT](LICENSE). Generated maps, rasters, and tables: CC-BY-4.0 — use them, credit "Sailaab / Punjab Flood Intelligence".
