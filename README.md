# Sailaab — Punjab Flood Intelligence

[![sailaab-monitor](https://github.com/bakathefish/Flood/actions/workflows/monitor.yml/badge.svg)](https://github.com/bakathefish/Flood/actions/workflows/monitor.yml)
**Live:** [bakathefish.github.io/Flood](https://bakathefish.github.io/Flood/) · **Synopsis:** [PDF](docs/SAILAAB-synopsis.pdf) · **District briefs:** [20 PDFs](briefs/) · License: MIT + CC-BY-4.0

**Open SAR flood mapping, a decade hazard atlas, damage analytics, district flood forecasting, and a live trilingual monitor for Punjab, India — every number reproducible with zero logins.**

*11 monsoons · 467 flood days · 105,183 ha mapped (2025) · 91 tehsils scored · ρ = 0.72 vs the government girdawari · 3 alert languages · 0 CWC flood-forecast stations in Punjab · 0 logins required.*

In August–September 2025 Punjab suffered its worst flood since 1988 — all 23 districts, ~3.55 lakh people, 1.48–1.75 lakh ha of crops (official range). India's flood-forecast network had **zero stations in the state** (CWC's own table; `docs/notes/cwc-gap.md`), and the satellite maps that could have guided relief existed only as locked PDFs. Sailaab rebuilds that capability in the open: reproducible code, open data, public outputs, running live this monsoon.

## What it does

| Module | Output |
|---|---|
| **2025 Flood Atlas** | Sentinel-1 SAR flood masks (physics change-detection baseline + Random Forest), per-district statistics, per-pixel **submergence duration**, before/after swipe, date-stamped timelapse |
| **Decade Hazard Atlas** | Every monsoon 2015–2025 mapped identically → Punjab's first public flood-frequency map, recurrence zonation, **91 tehsils scored**, the named "repeat victims" table |
| **Impact engine** | Crop-flooded hectares, the **₹351–523 crore** paddy damage band (duration-weighted → at-risk, on DES district yields), population exposure (GHSL), **dam headroom** counterfactual, the rain × dams × releases causal chart |
| **Forecaster** | XGBoost district flood-risk model trained on the pipeline's own 2,420 SAR-derived labels; leave-one-year-out validation; SHAP attributions; conformal uncertainty; **ablation-stress-tested** |
| **Live monitor** | 6-hourly secretless GitHub Action: new Sentinel-1 pass → district flood km² → `monitor/latest.json` + ਪੰਜਾਬੀ/हिन्दी/English alerts + live model risk (`monitor/nowcast.json`) |

The live site ([bakathefish.github.io/Flood](https://bakathefish.github.io/Flood/)) is interactive: an every-district map with five switchable layers (2025 flood, decade frequency, hindcast risk, live observed, live model risk), click-through per-district panels, the SAR swipe, the flood timelapse, and the live monitor feed — every figure loading from version-controlled CSVs in this repo.

## Headline results

- **2025 mapping:** 105,183 ha statewide SAR-flooded (Tier-A change detection, 90 m, full coverage); RF map ~52k ha in-district; three-method envelope vs Copernicus GFM published (Tier-A 34k < RF 52k < GFM 86k in-district).
- **Forecast, held out:** trained on 2015–2024 only, the model flagged **all five** of 2025's worst-flooded districts (Kapurthala #1, P = 0.72), with **~10 days of pre-crest lead** — 4 of 5 already in the statewide top-5 by the Aug 14–24 window, before the Aug 26–27 dam releases. Pooled LOYO ROC-AUC 0.946, leakage-checked.
- **Ground survey agreement:** satellite damage ranking vs the Revenue Department's Special Girdawari table: **ρ = 0.72** (all 20 districts; 0.56 over the 16 named), 5 of the top-6 identical; divergences concentrate in the Ghaggar basin (outside our SAR windows) and are documented.
- **Damage:** 36,195 ha cropland flooded (snapshot) → **₹523 crore** paddy value at risk (v2, DES district yields) → **₹351 crore** duration-weighted (51,202 ha under water ≥7 days). Official cumulative-season figure (1.48–1.75 lakh ha) is stated alongside; the divergence (snapshot vs season, recession bias) is explained, not hidden.
- **Relief targeting:** 91 tehsils scored; named repeat victims — Khadur Sahib 6 of 11 seasons, Sultanpur Lodhi 5 (`data/tehsil_repeat_victims.csv`); one printable brief per district in `briefs/`.
- **Population exposure:** 0.76–1.78 lakh people inside the mapped water (GHSL, conservation-checked) vs 3.55 lakh officially "affected" — the gap is low-density cropland (146–206 /km² vs ~550 mean), quantified.
- **Dam headroom (pre-declared):** at surge-eve, Pong sat +1.01 BCM above its own median operating curve, Ranjit Sagar +0.45, Bhakra +0.22 (negligible — reported as such); total ≈ 1.68 BCM ≈ 1–4 days of peak release (`docs/notes/headroom.md`).
- **Climate context:** pre-registered Mann-Kendall on 65 years of IMD grids — monsoon loading largely stationary, but upstream extreme-wet-day frequency rising (p = 0.017); 2025's Aug 20–Sep 5 burst: +9.7σ, rank 1 of the record.
- **The gap, quantified:** Punjab has **zero** CWC flood-forecast stations — absent from the 226-station national table and from CWC's current lists; the sole historical Ravi site is defunct (`docs/notes/cwc-gap.md`).

## Validated four independent ways

| Check | Against | Result |
|---|---|---|
| Fresh-point confusion matrices | Copernicus GFM (different algorithm) | OA 0.983; F1 and envelope published |
| 237 optical truth points | Sentinel-2 NDWI (different sensor, different physics) | 81.7 % of RF flood pixels confirmed (pre-declared gate ≥60 %); all precision/recall orderings confirmed |
| Visual map-sheet comparison | ISRO NDEM 2025 (RISAT-1A) | Beas-doab and Sutlej–Harike patterns correspond; registration approximate, stated on the image |
| District damage ranking | Punjab Revenue Dept Special Girdawari (ground survey) | ρ = 0.72 (all 20), 5 of top-6 identical |

We also benchmarked an imported deep-learning U-Net (Sen1Floods11: test IoU 0.63) — it under-segments Punjab badly (recall 0.24 vs GFM). The simpler stack won, and that table ships verbatim (`docs/notes/unet.md`).

## Architecture

All decision logic lives in the pure-Python package `sailaab/`, developed strictly test-first (`tests/` mirrors it 1:1 — **408 tests**). Satellite/cloud side-effects are confined to thin scripts in `gee/` (Code Editor JS) and `pipeline/` (CLIs). Every cloud step is gated by a pre-declared numeric checkpoint in `docs/VERIFICATION-LOG.md` — the expected band is written down *before* the run, then the actual, then PASS/FAIL. Failures ship.

```
sailaab/    pure, tested core (masks, stats, dataset, model, alerts, monitor, validation, eos04 …)
gee/        Wave-1 interactive GEE scripts (JS)
pipeline/   batch CLIs (decade runs, forecaster, ablation, briefs, live monitor, EOS-04 comparison)
tests/      pytest — every sailaab/ module covered (408 tests)
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

Every figure and CSV regenerates from the committed inputs via the `pipeline/` CLIs (deterministic, no accounts). The live monitor runs from `.github/workflows/monitor.yml` on a public runner with zero secrets.

## Data sources

Sentinel-1/2 (Copernicus, via anonymous Planetary Computer STAC), Copernicus GFM (keyless WMS), IMD gridded rainfall, CWC/BBMB reservoir records, CWC flood-forecast station table + 70-year damage records (data.gov.in, GODL), FAO GAUL / Census-2011 boundaries, JRC Global Surface Water, Copernicus DEM GLO-30, ESA WorldCover, GHSL population, DES district paddy yields; ISRO NDEM map sheets for validation. Full registry with URLs, licenses and access dates: `docs/DATA-SOURCES.md`.

## Honesty rules

Training labels are bootstrapped from method agreement and labeled as such. Both spatial-CV folds are reported (including the near-separable strata artifact). Every headline number is stated next to the official figure it should be compared with. The June–July "floods" that are actually rice transplanting are documented and excluded from training. The ablation we ran on ourselves — delete the dam features, the 2025 flags don't move; a persistence baseline nearly matches pooled precision — is published verbatim (`docs/notes/ablation.md`). An EOS-04 (ISRO SAR) pixel-level cross-validation is pre-declared with acceptance bands before any scene was downloaded (`docs/notes/eos04.md`). Known limitations (urban double-bounce, radar shadow, recession bias) are documented, not hidden.

## Documents

[Synopsis (PDF)](docs/SAILAAB-synopsis.pdf) · [Method paper](docs/METHOD.md) · [Data-source registry](docs/DATA-SOURCES.md) · [Verification log](docs/VERIFICATION-LOG.md) · [Sustainability & deployment plan (PDF)](docs/SAILAAB-business-plan.pdf) · [District briefs](briefs/) · [Video script](docs/VIDEO-SCRIPT.md)

Built by a Punjab student during the 2026 monsoon · India AI Impact Festival 2026 entry.

## License

Code: [MIT](LICENSE). Generated maps, rasters, and tables: CC-BY-4.0 — use them, credit "Sailaab / Punjab Flood Intelligence". Contains modified Copernicus Sentinel and CEMS-GFM data.
