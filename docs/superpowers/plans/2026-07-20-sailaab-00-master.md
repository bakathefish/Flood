# Sailaab Flood Intelligence — Master Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the Sailaab flood-intelligence system (2025 Punjab flood atlas → decade hazard atlas → impact analytics → forecaster → live monitor → festival submission) with TDD rigor and full documentation, submitting to the India AI Impact Festival by July 25, 2026.

**Architecture:** All decision logic (window generation, stats tidying, dataset assembly, CV splitting, alert rendering, monitor state) lives in a pure-Python package `sailaab/` developed strictly test-first with pytest. Google Earth Engine work is split into thin JS Code Editor scripts (Wave 1 interactive) and thin Python CLIs in `pipeline/` that call the tested library; every GEE step carries a **pre-declared acceptance checkpoint** (expected numeric band written into `docs/VERIFICATION-LOG.md` *before* the run — red/green adapted to a cloud platform you can't unit-test). Content deliverables (app, synopsis, video) are driven by acceptance checklists.

**Tech Stack:** Google Earth Engine (JS + `earthengine-api`), Python 3.11+, pytest, pandas, xgboost, shap, GitHub Actions; QGIS for NDEM georeferencing; OBS/CapCut for the video.

---

## Sub-plans (execution order)

| # | Plan file | Wave | Produces |
|---|---|---|---|
| 01 | `2026-07-20-sailaab-01-gee-mapping-core.md` | 1 | 2025 flood masks (Tier A + RF), district stats CSV, checkpoints passed |
| 02 | `2026-07-20-sailaab-02-python-core-lib.md` | lib | `sailaab/` package: config, windows, stats — tested |
| 03 | `2026-07-20-sailaab-03-decade-batch.md` | 2 | 11-season flood CSVs + frequency raster, anchors verified |
| 04 | `2026-07-20-sailaab-04-validation-analytics.md` | 1/3 | GFM/NDEM validation numbers, crop-loss/exposure/depth tables, causal figure |
| 05 | `2026-07-20-sailaab-05-forecaster.md` | 4 | LOYO-validated XGBoost + 2025 hindcast + SHAP figure |
| 06 | `2026-07-20-sailaab-06-live-monitor.md` | 5 | 6-hourly GitHub Action, `latest.json`, PA/HI/EN alerts |
| 07 | `2026-07-20-sailaab-07-packaging-submission.md` | 6/7 | GEE App, repo docs, landing page, synopsis, video, submission |

Dependencies: 02 blocks 03/05/06 (they import the lib). 01 is independent of 02 (JS). 03 blocks 05 (labels). 04 needs 01 exports. 07 consumes everything and is scheduled last but its Phase-0 items (portal registration, form screenshot) run FIRST — they gate the whole endeavor.

## Repository file map (final state)

```
d/
├── gee/                      # thin JS Code Editor scripts (Wave 1)
│   ├── 01_aoi_scenes_mosaics.js
│   ├── 02_tierA_change_detection.js
│   └── 03_tierB_random_forest.js
├── sailaab/                  # pure-Python core — 100% TDD
│   ├── __init__.py
│   ├── config.py             # windows, thresholds, district folds, paths
│   ├── windows.py            # monsoon window generation
│   ├── stats.py              # GEE export CSV → tidy frames, area math
│   ├── dataset.py            # forecaster dataset assembly (joins, lags, targets)
│   ├── model.py              # LOYO splits, fit/predict, metrics
│   ├── alerts.py             # PA/HI/EN alert rendering
│   ├── monitor.py            # new-scene detection, state file
│   └── validation.py         # confusion matrix, OA/F1/IoU, area sums
├── pipeline/                 # thin CLIs (EE side-effects live here only)
│   ├── batch_decade.py       # Wave 2 runner (rewrite of draft — see plan 03)
│   ├── run_forecaster.py     # Wave 4 runner
│   └── live_monitor.py       # Wave 5 runner (called by Action)
├── tests/                    # pytest; mirrors sailaab/ 1:1
├── data/                     # small CSVs only (reservoirs, exports); no rasters
├── atlas/                    # output figures/maps for synopsis+video
├── docs/
│   ├── METHOD.md             # the method paper (grows with each plan)
│   ├── DATA-SOURCES.md       # every dataset: URL, license, access date
│   ├── VERIFICATION-LOG.md   # pre-declared checkpoints + actual results
│   └── superpowers/plans/    # these plans
├── .github/workflows/monitor.yml
├── requirements.txt
├── README.md
└── punjab-flood-atlas-PLAN.md  # strategy doc (v2, stays as vision reference)
```

Existing draft files `pipeline/batch_decade.py` and `pipeline/forecaster.py` are **drafts written before this plan** — plans 03/05 replace them task-by-task through TDD; do not treat them as done. `gee/01–03.js` are the Wave-1 starting points and are refined by plan 01.

## Conventions (all sub-plans inherit these)

- **TDD:** test first, watch it fail, minimal implementation, watch it pass, commit. Test command: `python -m pytest tests/ -v` (Windows PowerShell).
- **GEE checkpoint discipline:** before running any GEE script/export, append to `docs/VERIFICATION-LOG.md`: date, what runs, **expected band**, then the actual result and PASS/FAIL. A FAIL stops the wave until explained.
- **Commits:** conventional messages (`feat:`, `test:`, `docs:`, `fix:`), one logical change each. This repo will be public and festival-judged: **no AI-attribution trailers** (matches your standing public-repo preference — flag if you want it otherwise).
- **Docs are tasks, not afterthoughts:** each sub-plan ends with a METHOD.md section task + DATA-SOURCES.md rows. A wave is not done until its docs task is checked.
- **Honesty rules:** report both spatial-CV folds; label bootstrapped training labels as such; every headline number carries its comparison band (official figures) in METHOD.md.

## Definition of done per wave (gates)

1. **Wave 1:** both fold accuracies printed and logged; statewide crop-flooded sum within 1.2–2.2 lakh ha of the official band or divergence explained in METHOD.md; masks exported.
2. **Wave 2:** 2023 Sangrur anchor within ±50% of NRSC's 7,121 ha; ≥8 of 11 seasons processed; frequency raster exported.
3. **Wave 3/validation:** GFM agreement computed on fresh points; NDEM comparison (georef or visual panel) in atlas/; causal figure done.
4. **Wave 4:** LOYO metrics table; 2025 hindcast result stated verbatim (whatever it shows); SHAP figure.
5. **Wave 5:** Action runs green on schedule twice consecutively; `latest.json` updating; PA/HI/EN alerts rendering (native-speaker read-through = you).
6. **Wave 7:** portal form dry-run complete by Jul 24 evening; submitted + confirmation screenshot by Jul 25.

## Schedule mapping (from strategy doc v2)

Day 1–2 → plans 01+02 · Day 3 → 03+04 · Day 4 → 05 (+U-Net timebox) · Day 5 → 06+07 · Day 6 (Jul 25) → submit. Cut-line ladder in the strategy doc governs what drops if the week compresses.
