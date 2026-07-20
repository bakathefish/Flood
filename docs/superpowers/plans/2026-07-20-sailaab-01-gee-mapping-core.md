# Sailaab 01 — GEE Mapping Core (Wave 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. NOTE: Tasks 2–7 run inside the GEE Code Editor and require the human's authenticated browser session — execute them WITH the user, not in a headless subagent.

**Goal:** Produce the validated 2025 Punjab flood masks (Tier A change-detection + Tier B Random Forest), per-district statistics, and exported rasters — every step gated by a pre-declared checkpoint.

**Architecture:** Three thin JS scripts (already drafted in `gee/`) run interactively in the Code Editor. "TDD adapted": for each run, the expected numeric band is appended to `docs/VERIFICATION-LOG.md` **before** clicking Run (red), then the observed value and verdict (green). Constants mirror `sailaab/config.py`; Task 5 reconciles district spellings both ways.

**Tech Stack:** GEE Code Editor (JS), datasets: COPERNICUS/S1_GRD, FAO/GAUL/2015/level2, JRC/GSW1_4, COPERNICUS/DEM/GLO30, ESA/WorldCover/v200, JRC/GHSL/P2023A/GHS_POP.

---

### Task 1: Accounts + project prerequisites (human-only, do first)

**Files:** none (external)

- [ ] **Step 1:** Register on indiaaiimpactfest.ai-for-all.in — verify the Jul 26 deadline banner, note your category bracket, **screenshot every submission-form field** into `docs/festival-form/` (create the folder, drop the PNGs).
- [ ] **Step 2:** Create the GEE account at code.earthengine.google.com (choose "Unpaid usage → Academia/non-profit or personal"). Note the cloud project id (format `ee-<username>`).
- [ ] **Step 3:** Register on global-flood.emergency.copernicus.eu (GFM — needed by plan 04). Request nothing yet; just have the login.
- [ ] **Step 4:** Commit the form screenshots:

```bash
git add docs/festival-form/
git commit -m "docs: festival submission form field screenshots (the real spec)"
```

---

### Task 2: Scene inventory checkpoint (script 01)

**Files:**
- Use: `gee/01_aoi_scenes_mosaics.js` (exists)
- Modify: `docs/VERIFICATION-LOG.md`

- [ ] **Step 1: Pre-declare the checkpoint (red).** Append to the log table:

```markdown
| 2026-07-2X | gee/01 scene inventory | FLOOD window (Aug 25–Sep 6 2025) has ≥6 scenes across ≥2 relative orbits; PRE window ≥12 scenes; district list ~20–23 names | | |
```

- [ ] **Step 2: Run.** Paste `gee/01_aoi_scenes_mosaics.js` into the Code Editor, Run, read the console.

- [ ] **Step 3: Record (green/red).** Fill Actual + Verdict. If FAIL (missing coverage): widen FLOOD window to `2025-08-22..2025-09-10` in BOTH `gee/01` and `sailaab/config.py` (`FLOOD_2025`), re-declare, re-run.

- [ ] **Step 4: Visual sanity.** Toggle layers: PRE mosaic "normal" (bright fields, thin dark rivers), FLOOD mosaic shows large dark zones along the Ravi/Beas/Sutlej belts, permanent-water mask hugs the rivers. Screenshot both mosaics into `atlas/checks/`.

- [ ] **Step 5: Commit.**

```bash
git add docs/VERIFICATION-LOG.md atlas/checks/
git commit -m "docs: scene inventory checkpoint for 2025 event windows"
```

---

### Task 3: Tier A flood mask + district stats (script 02)

**Files:**
- Use: `gee/02_tierA_change_detection.js` (exists)
- Modify: `docs/VERIFICATION-LOG.md`

- [ ] **Step 1: Pre-declare (red).** Append:

```markdown
| 2026-07-2X | gee/02 Otsu threshold | Otsu dVV in [-5.5, -2.0] dB | | |
| 2026-07-2X | gee/02 statewide crop_flooded sum | 120,000–220,000 ha (official band 148–175k) | | |
| 2026-07-2X | gee/02 worst districts | Gurdaspur/Amritsar/Ferozepur/Kapurthala in top 6 by flooded_ha | | |
```

- [ ] **Step 2: Run script 02.** Check the Otsu print first; then print full stats by changing the limit line to `print('ALL', stats)` if needed.

- [ ] **Step 3: Record verdicts.** If crop sum is far outside band: first suspect the flood window (compare with Task 2 scenes), then thresholds (tighten `FIXED_ABS` to −16), then the belt rectangle for Otsu. One change at a time, re-declare each re-run.

- [ ] **Step 4: Start both exports** (Tasks tab): `sailaab_tierA_district_stats_2025` (CSV → Drive) and `sailaab_tierA_floodmask_2025` (GeoTIFF → Drive). Download CSV into `data/` when done.

- [ ] **Step 5: Commit.**

```bash
git add docs/VERIFICATION-LOG.md data/sailaab_tierA_district_stats_2025.csv
git commit -m "feat: Tier A 2025 flood mask stats, checkpoints passed"
```

---

### Task 4: Tier B Random Forest + spatial CV (script 03)

**Files:**
- Use: `gee/03_tierB_random_forest.js` (exists)
- Modify: `docs/VERIFICATION-LOG.md`

- [ ] **Step 1: Pre-declare (red).**

```markdown
| 2026-07-2X | gee/03 fold A→B accuracy | OA ≥ 0.90, F1(flood) ≥ 0.80 | | |
| 2026-07-2X | gee/03 fold B→A accuracy | OA ≥ 0.90, F1(flood) ≥ 0.80 | | |
| 2026-07-2X | gee/03 variable importance | dVV or postVV among top 2 | | |
```

- [ ] **Step 2: Run script 03.** Record both confusion matrices VERBATIM into the log (both folds — honesty rule).

- [ ] **Step 3: If a fold fails:** inspect where RF and Tier A disagree on the map (add `Map.addLayer(rfFlood.unmask(0).neq(tierA.unmask(0)))` after recomputing tierA); usual culprits are label-strata leakage into urban shadows → tighten dry stratum (`post VV > -12`), or fold lists misspelled (Task 5 fixes).

- [ ] **Step 4: Export** `sailaab_RF_floodmask_2025` and re-run the district stats block with `rfFlood` → export `sailaab_RF_district_stats_2025.csv` → `data/`.

- [ ] **Step 5: Commit.**

```bash
git add docs/VERIFICATION-LOG.md data/sailaab_RF_district_stats_2025.csv
git commit -m "feat: RF flood map with two-fold spatial CV logged"
```

---

### Task 5: District spelling sync (JS ↔ config.py)

**Files:**
- Modify: `sailaab/config.py` (FOLD_RAVI_BEAS / FOLD_SUTLEJ), `gee/03_tierB_random_forest.js` (RAVI_BEAS / SUTLEJ arrays)
- Test: `tests/test_config.py` (exists; extend)

- [ ] **Step 1: Get truth.** From the Task 2 console output, copy the exact `ADM2_NAME` list into `docs/VERIFICATION-LOG.md` as a note row.

- [ ] **Step 2: Write the failing test** (extend `tests/test_config.py`):

```python
def test_fold_districts_use_gaul_spellings():
    # paste the exact GAUL list from the gee/01 console here:
    gaul = {"Amritsar", "Bathinda", "Faridkot", "Fatehgarh Sahib", "Firozpur",
            "Gurdaspur", "Hoshiarpur", "Jalandhar", "Kapurthala", "Ludhiana",
            "Mansa", "Moga", "Muktsar", "Nawanshahr", "Patiala", "Rupnagar",
            "Sangrur", "Tarn Taran"}  # REPLACE with actual console output
    from sailaab import config
    assert set(config.FOLD_RAVI_BEAS) <= gaul
    assert set(config.FOLD_SUTLEJ) <= gaul
```

- [ ] **Step 3: Run → fix spellings in `config.py` until green.** `python -m pytest tests/test_config.py -v`

- [ ] **Step 4: Mirror the corrected lists into `gee/03`** (RAVI_BEAS/SUTLEJ arrays, remove the duplicate-spelling guesses), re-run script 03 if lists changed materially (re-declare checkpoints).

- [ ] **Step 5: Commit.**

```bash
git add sailaab/config.py tests/test_config.py gee/03_tierB_random_forest.js
git commit -m "fix: reconcile district spellings with GAUL, test-pinned"
```

---

### Task 6: METHOD.md §2 — mapping method

**Files:**
- Modify: `docs/METHOD.md`, `docs/DATA-SOURCES.md`

- [ ] **Step 1: Append §2 to METHOD.md** — cover: windows chosen and why (Aug 27 river rise; IJIST precedent), speckle filter, min-composite rationale, masks (JRC ≥60%, slope >5°, urban double-bounce limitation), Otsu-refined thresholds, RF features/labels (bootstrapped strata — stated plainly), two-fold spatial CV with BOTH accuracies, and the crop-sum vs official-band comparison. Write it from the VERIFICATION-LOG numbers — every claim in this section must have a log row.

- [ ] **Step 2: Append DATA-SOURCES.md rows** for S1_GRD, GAUL, JRC GSW, GLO-30, WorldCover, GHSL (provider, URL, license, access date).

- [ ] **Step 3: Commit.**

```bash
git add docs/METHOD.md docs/DATA-SOURCES.md
git commit -m "docs: mapping method section with logged evidence"
```
