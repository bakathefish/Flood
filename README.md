# Sailaab: Punjab Flood Intelligence

[![sailaab-monitor](https://github.com/bakathefish/Flood/actions/workflows/monitor.yml/badge.svg)](https://github.com/bakathefish/Flood/actions/workflows/monitor.yml)
**Live:** [bakathefish.github.io/Flood](https://bakathefish.github.io/Flood/) · **Synopsis:** [PDF](docs/SAILAAB-synopsis.pdf) · **District briefs:** [20 PDFs](briefs/) · MIT + CC-BY-4.0

Open SAR flood mapping, a decade hazard atlas, damage analytics, district flood forecasting, and a live trilingual monitor for Punjab, India. Every number is reproducible with zero logins.

*11 monsoons · 467 flood days · 105,183 ha mapped (2025) · 91 tehsils scored · ρ = 0.72 vs the government girdawari · 3 alert languages · 0 CWC flood-forecast stations in Punjab · 0 logins required.*

In August and September 2025 Punjab had its worst flood since 1988: all 23 districts, about 3.55 lakh people, 1.48 to 1.75 lakh hectares of crops (official range). India's flood-forecast network had zero stations in the state (CWC's own table; see `docs/notes/cwc-gap.md`), and the satellite maps that could have guided relief existed only as locked PDFs. Sailaab rebuilds that capability in the open. The code is public, the data is open, and the monitor is running this monsoon.

## What it does

| Module | Output |
|---|---|
| **2025 Flood Atlas** | Sentinel-1 SAR flood masks (physics change-detection baseline + Random Forest), per-district statistics, per-pixel submergence duration, a before/after swipe, a date-stamped timelapse |
| **Decade Hazard Atlas** | Every monsoon 2015 to 2025 mapped the same way. Punjab's first public flood-frequency map, recurrence zones, 91 tehsils scored, and a named "repeat victims" table |
| **Impact engine** | Crop-flooded hectares, the ₹351 to ₹523 crore paddy damage band (duration-weighted and at-risk, on DES district yields), population exposure (GHSL), the dam headroom counterfactual, and the rain, dams and releases causal chart |
| **Forecaster** | XGBoost district flood-risk model trained on the pipeline's own 2,420 SAR-derived labels. Leave-one-year-out validation, SHAP attributions, conformal uncertainty, and an ablation stress test |
| **Live monitor** | A 6-hourly secretless GitHub Action: new Sentinel-1 pass in, district flood km² out, written to `monitor/latest.json` with ਪੰਜਾਬੀ, हिन्दी and English alerts plus live model risk in `monitor/nowcast.json` |

The site is interactive: an every-district map with five switchable layers (2025 flood, decade frequency, hindcast risk, live observed, live model risk), per-district panels, the SAR swipe, the flood timelapse, and the live feed. Every figure loads from version-controlled CSVs in this repo.

## Headline results

- **2025 mapping.** 105,183 ha statewide SAR-flooded area (Tier-A change detection, 90 m, full coverage). The RF map adds about 52k ha in-district. The three-method envelope against Copernicus GFM is published: Tier-A 34k < RF 52k < GFM 86k in-district.
- **Forecast, held out.** Trained on 2015 to 2024 only, the model flagged all five of 2025's worst-flooded districts, with Kapurthala first at P = 0.72. Four of the five were already in the statewide top-5 by the Aug 14–24 window, roughly ten days before the Aug 26–27 dam releases. Pooled LOYO ROC-AUC 0.946, leakage-checked.
- **The ground survey agrees.** Our satellite damage ranking matched the Revenue Department's Special Girdawari table at ρ = 0.72 across all 20 districts (0.56 over the 16 named), with 5 of the top 6 identical. The divergences sit in the Ghaggar basin, outside our SAR windows, and are documented.
- **Damage.** 36,195 ha of cropland flooded in the peak snapshot. That is ₹523 crore of paddy at risk (v2, on DES district yields), refined to ₹351 crore once duration is weighted in: 51,202 ha stayed under water for 7 days or more. The official cumulative-season figure (1.48 to 1.75 lakh ha) is stated alongside, and the gap (snapshot vs season, recession bias) is explained rather than hidden.
- **Relief targeting.** 91 tehsils scored. The repeat victims have names: Khadur Sahib flooded in 6 of 11 seasons, Sultanpur Lodhi in 5 (`data/tehsil_repeat_victims.csv`). One printable brief per district lives in `briefs/`.
- **Population exposure.** 0.76 to 1.78 lakh people lived inside the mapped water (GHSL, conservation-checked), against 3.55 lakh officially "affected". The gap is low-density cropland: 146 to 206 people/km² in the flooded zone versus a state mean near 550.
- **Dam headroom (pre-declared).** At surge-eve, Pong sat 1.01 BCM above its own median operating curve and Ranjit Sagar 0.45 BCM. Bhakra's margin was 0.22 BCM, which we report as negligible. The total, about 1.68 BCM, is one to four days of peak release (`docs/notes/headroom.md`).
- **Climate context.** Pre-registered Mann-Kendall tests on 65 years of IMD grids: total monsoon loading is largely stationary, but extreme-wet-day frequency over the upstream Himalayan box is rising (p = 0.017). The 2025 Aug 20 to Sep 5 burst was +9.7σ, rank 1 of the record.
- **The gap, quantified.** Punjab has zero CWC flood-forecast stations. It is absent from the 226-station national table and from CWC's current lists, and the one historical Ravi site is defunct (`docs/notes/cwc-gap.md`).

## Validated four independent ways

| Check | Against | Result |
|---|---|---|
| Fresh-point confusion matrices | Copernicus GFM (different algorithm) | OA 0.983; F1 and the full envelope published |
| 237 optical truth points | Sentinel-2 NDWI (different sensor, different physics) | 81.7% of RF flood pixels confirmed; the pre-declared gate was 60%, and every precision/recall ordering held |
| Visual map-sheet comparison | ISRO NDEM 2025 (RISAT-1A) | The Beas-doab and Sutlej-Harike patterns correspond; registration is approximate and says so on the image |
| District damage ranking | Punjab Revenue Dept Special Girdawari (ground survey) | ρ = 0.72 across all 20 districts, 5 of the top 6 identical |

We also benchmarked an imported deep-learning U-Net (Sen1Floods11, test IoU 0.63). On Punjab it under-segments badly (recall 0.24 vs GFM). The simpler stack won, and that table ships as it came out (`docs/notes/unet.md`).

## Architecture

All decision logic lives in the pure-Python package `sailaab/`, written test-first; `tests/` mirrors it 1:1 with 408 tests. Satellite and cloud side effects stay in thin scripts: `gee/` for Code Editor JS, `pipeline/` for CLIs. Every cloud step is gated by a pre-declared numeric checkpoint in `docs/VERIFICATION-LOG.md`. The expected band is written down before the run, then the actual, then PASS or FAIL. Failures ship.

```
sailaab/    pure, tested core (masks, stats, dataset, model, alerts, monitor, validation, eos04 …)
gee/        Wave-1 interactive GEE scripts (JS)
pipeline/   batch CLIs (decade runs, forecaster, ablation, briefs, live monitor, EOS-04 comparison)
tests/      pytest, every sailaab/ module covered (408 tests)
data/       small CSVs + GeoJSON only (committed); bulk rasters stay local
atlas/      output maps and figures (incl. atlas/web/ swipe + timelapse assets)
briefs/     20 designed per-district A4 PDFs
monitor/    live state written by CI every 6 h (latest.json, nowcast.json)
docs/       site (index.html) · METHOD.md · DATA-SOURCES.md · VERIFICATION-LOG.md · SYNOPSIS.md ·
            SAILAAB-synopsis.pdf · SAILAAB-business-plan.pdf · notes/ (pre-declarations per component)
```

## Run it

```bash
pip install -r requirements.txt
python -m pytest -q          # 408 tests; Earth-Engine-marked tests excluded by default
```

Every figure and CSV regenerates from the committed inputs via the `pipeline/` CLIs. They are deterministic and need no accounts. The live monitor runs from `.github/workflows/monitor.yml` on a public runner with zero secrets.

## Data sources

Sentinel-1/2 (Copernicus, via anonymous Planetary Computer STAC), Copernicus GFM (keyless WMS), IMD gridded rainfall, CWC/BBMB reservoir records, the CWC flood-forecast station table and 70-year damage records (data.gov.in, GODL), FAO GAUL and Census-2011 boundaries, JRC Global Surface Water, Copernicus DEM GLO-30, ESA WorldCover, GHSL population, DES district paddy yields, and ISRO NDEM map sheets for validation. The full registry with URLs, licenses and access dates is in `docs/DATA-SOURCES.md`.

## Honesty rules

Training labels are bootstrapped from method agreement and labeled as such. Both spatial-CV folds are reported, including the near-separable strata artifact. Every headline number sits next to the official figure it should be compared with. The June and July "floods" that are actually rice transplanting are documented and excluded from training. We ran an ablation on ourselves: delete the dam features and the 2025 flags do not move, and a persistence baseline nearly matches pooled precision. Both results are published as they came out (`docs/notes/ablation.md`). An EOS-04 (ISRO SAR) pixel-level cross-validation is pre-declared with acceptance bands, committed before any scene was downloaded (`docs/notes/eos04.md`). Known limits (urban double-bounce, radar shadow, recession bias) are documented too.

## Documents

[Synopsis (PDF)](docs/SAILAAB-synopsis.pdf) · [Method paper](docs/METHOD.md) · [Data-source registry](docs/DATA-SOURCES.md) · [Verification log](docs/VERIFICATION-LOG.md) · [Sustainability & deployment plan (PDF)](docs/SAILAAB-business-plan.pdf) · [District briefs](briefs/)

Built by a Punjab student during the 2026 monsoon. India AI Impact Festival 2026 entry.

## License

Code: [MIT](LICENSE). Generated maps, rasters and tables: CC-BY-4.0. Use them, credit "Sailaab / Punjab Flood Intelligence". Contains modified Copernicus Sentinel and CEMS-GFM data.
