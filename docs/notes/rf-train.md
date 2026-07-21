# RF flood classifier — training on real 2025 Punjab SAR (honest spatial CV)

The judged AI stage. A `sklearn.RandomForestClassifier` is trained on the 2025
Punjab flood using **agreement labels** (pixels where the independent Tier-A SAR
change-detection mask and the Copernicus GFM observed-flood-extent mask *agree*),
and evaluated with **honest spatial cross-validation** across the two flood
basins (Ravi/Beas vs Sutlej), so the reported skill is never a same-place
memorisation artefact.

- Pure array logic (feature stacking, slope, agreement labels, stratified
  balanced sampling, spatial split): `sailaab/rf.py` — unit-tested test-first in
  `tests/test_rf.py` (small synthetic arrays, no network).
- IO / orchestration (all network + rasterio): `pipeline/rf_build_features.py`
  (S1 feature stack + Tier-A mask), `pipeline/rf_aux_layers.py` (Copernicus DEM
  slope, ESA WorldCover cropland, GFM warp onto the canonical grid),
  `pipeline/rf_train.py` (labels, sampling, spatial CV, statewide predict, stats,
  quicklooks, model save).
- Canonical grid: Punjab bbox `(73.85, 29.53, 76.95, 32.60)` at **90 m** on
  **EPSG:32643** (UTM 43N) — identical to `pipeline.local_tier_a.target_grid`, so
  the Tier-A mask, feature stack, DEM slope, WorldCover cropland and warped GFM
  all share one pixel grid.

## Feature stack (per 90 m pixel)

`VV_flood`, `VH_flood`, `dVV = VV_flood − VV_pre`, `dVH = VH_flood − VH_pre`
(all dB, descending tracks, median composites over the two 2025 windows in
`sailaab/config.py`), plus **slope** (degrees) from Copernicus DEM GLO-30
(`cop-dem-glo-30`, anonymous PC, mosaicked to the same 90 m grid). If the DEM
fights the run for >45 min it is dropped and the stack proceeds without slope
(noted in the actuals).

## Labels — agreement strata (the honesty core)

Per pixel, on the canonical grid:

- **positive (flood)** = Tier-A says flood **AND** GFM union says flood.
- **negative (dry)** = Tier-A says dry **AND** GFM union says dry.
- **excluded (unlabelled)** = the two disagree, **or** the pixel is permanent
  water. Permanent water = GFM reference-water mask **OR** `pre_VV < −15 dB`
  (dark-in-the-dry-season SAR proxy). Excluded pixels never enter training.

Stratified balanced sample of ~4,000 points/class, spread across districts
(`sailaab.districts.rasterize_districts` + per-district quota), written to
`data/rf_training_points_2025.csv` (`x, y, district, <features>, label`).

**Caveat, stated up front:** because the labels are *agreement strata* — pixels
where two independent masks already concur — they are, by construction, the
"easy" pixels. A classifier tested on held-out points from such strata will post
**optimistically high** OA/F1. That is expected and is *not* evidence of
real-world per-pixel accuracy; the honest signal here is (i) whether skill
**transfers across basins** under spatial CV (a model that only memorised the
Ravi/Beas basin should degrade on Sutlej), and (ii) whether the statewide RF area
and district ranking stay physically consistent with the independent Tier-A and
GFM products. The absolute OA/F1 numbers are reported with this caveat attached.

## PRE-DECLARED acceptance bands (declared BEFORE any run)

Declared 2026-07-21, before the feature build / training were executed. Adapted
from the repo's verification discipline: bands are committed first, actuals and
PASS/FAIL verdicts are appended afterwards and never edited to fit.

| # | Band | Threshold declared in advance | Rationale |
|---|---|---|---|
| **a** | Regenerated statewide Tier-A flooded area | **strictly > 61,499 ha** | 61,499 ha was an explicit *floor* from the pre-fix run whose flood composite had a central N–S nodata stripe (expired-SAS bug) swallowing most of the Beas–Sutlej belt. With the re-sign fix filling that stripe, the honest area must exceed the floor. |
| **b** | Held-out strata-point accuracy, **per spatial fold** | **OA 0.90–0.99 and F1 0.80–0.99** | Labels are agreement strata (see caveat) so high numbers are *expected*; the band asserts the model transfers across basins without collapsing (F1 not falling out the bottom) and without a suspicious perfect 1.0 (which would signal leakage / a degenerate split). |
| **c** | RF statewide flooded area vs Tier-A | **within ±40 % of the regenerated Tier-A ha** | The RF is trained toward Tier-A∧GFM agreement, so its statewide area should track Tier-A's order of magnitude; ±40 % allows the RF to reasonably fill/trim the SAR mask via VH + slope without diverging wildly. |
| **d** | Top-6 RF-flooded districts | **include ≥3 of {Gurdaspur, Amritsar, Firozpur, Kapurthala}** | These four sit on the Ravi/Beas/Sutlej corridors that both GFM and press reporting place at the centre of the 2025 flood; a credible map must rank them near the top. |
| **e** | Crop-flooded statewide vs official band | official **148,000–175,000 ha**; **record divergence + explain** | This is a *characterisation*, not a pass/fail gate: our single-window SAR snapshot (recession-biased descending passes ~2 wk after peak) measures instantaneous open-water crop inundation, whereas the official figure is cumulative crop *damage* over the whole season. Divergence is expected and explained, not tuned away. |

Bands **a–d** are PASS/FAIL gates; band **e** is a documented characterisation.

<!-- ACTUALS / VERDICTS / FOLD METRICS / DISTRICT TABLE / CITATIONS / DEPS appended below after the runs. -->
