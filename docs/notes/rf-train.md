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

## ACTUALS vs pre-declared bands (runs of 2026-07-21, appended after the fact)

| # | Band (declared) | Actual | Verdict |
|---|---|---|---|
| **a** | Tier-A statewide > 61,499 ha | **105,183.4 ha** (bbox-wide, valid fraction 0.641 → **1.000**, stripe hole filled) | **PASS** |
| **b** | per-fold OA 0.90–0.99, F1 0.80–0.99 | Fold A OA **1.000** / F1 **1.000**; Fold B OA **0.9991** / F1 **0.9993** | **FAIL — exceeded on the high side** (see analysis) |
| **c** | RF within ±40 % of Tier-A | RF 52,223 ha vs Tier-A 33,938 ha (in-district): **+53.9 %** | **FAIL** (see analysis) |
| **d** | top-6 RF districts ⊇ ≥3 of {Gurdaspur, Amritsar, Firozpur, Kapurthala} | top-6 = Firozpur, Gurdaspur, Kapurthala, Tarn Taran, Amritsar, Jalandhar → **4 of 4** | **PASS** |
| **e** | crop-flooded vs official 148k–175k ha (characterise) | **36,195 ha** ≈ 21–24 % of the official band | characterised below |

Bands are recorded as declared — the two out-of-band results are reported as
failures of the *band*, with the physics spelled out, not retro-fitted.

### Band (b) analysis — why the CV came out *too* clean

Both folds exceeded the 0.99 cap. The agreement strata turn out to be almost
perfectly separable in feature space: the positive class is definitionally
inside `dVV < −3 ∧ VV_flood < −15` (Tier-A) *and* GFM-confirmed, while
negatives are outside both, so a forest recovers a threshold-like rule that
transfers across basins essentially without error (fold A: 0 errors in 2,893
held-out points; fold B: 3 errors in 3,397). The pre-declared caveat — high
numbers expected, absolute OA/F1 are **not** evidence of real-world per-pixel
accuracy — is thus empirically confirmed in its strongest form. What the CV
*does* establish is that the learned rule is **basin-independent** (no
Ravi/Beas-specific memorisation). The honest counterweight is the independent
random-point check below (RF vs GFM on fresh, non-strata points: F1 0.394),
which shows exactly how far RF and an independent product diverge outside the
easy strata. Verdict recorded as FAIL because the band said 0.99 max; the
lesson is that the band itself was mis-calibrated for definitionally-separable
labels, and any future re-run should either add label noise / disagreement
pixels or widen the cap with this justification.

### Band (c) analysis — RF +53.9 % vs Tier-A

RF (52,223 ha in-district) sits **between** its two label parents: Tier-A
(33,938 ha, strict single-geometry change detection) and the GFM union
(86,071 ha in-district, any-of-6-days peak capture). Trained on their
agreement, the forest generalises the "flooded" concept to pixels where VH and
VV evidence resembles the agreed flood class even though the strict Tier-A
ΔVV/absolute-VV pair narrowly missed them — VH_flood carries 29 % of the
importance, so this is mostly VH-informed fill along the same corridors (see
3-panel quicklook; the RF map adds no spurious off-corridor mass). +53.9 % is
outside the declared ±40 %; recorded as FAIL. Physically the result is
consistent: RF ⊂ envelope(Tier-A, GFM), and the district ranking (band d) is
unchanged.

### Band (e) characterisation — crop-flooded vs official

RF ∧ WorldCover-cropland = **36,195 ha** statewide, 21–24 % of the official
148k–175k ha crop-damage band. Expected divergence, three stacked reasons:
(1) **snapshot vs season** — our flood window is a single 2025-08-25..09-06
composite; the official figure accumulates damage over the whole monsoon,
including waters that receded before our window and later September spills;
(2) **recession bias** — the descending flood passes cluster ~1–2 weeks after
the Aug 26–27 peak (GFM's Aug 27 single day alone maps 2,039 km² of water,
2.4× our composite's flood class), and a median composite further suppresses
transient water; (3) **standing water vs damage** — official crop loss counts
fields ruined by inundation *or* waterlogging/sand casting, not just pixels
still under open water on the pass date. The two numbers measure different
physical quantities; ours is the instantaneous open-water floor.

## Fold metrics (sailaab.validation.binary_metrics)

| Fold | Train → Test | n_train | n_test | OA | F1 | IoU | TP/FP/FN/TN |
|---|---|---|---|---|---|---|---|
| A | Ravi/Beas → Sutlej | 3,397 | 2,893 | 1.0000 | 1.0000 | 1.0000 | 1493/0/0/1400 |
| B | Sutlej → Ravi/Beas | 2,893 | 3,397 | 0.9991 | 0.9993 | 0.9986 | 2197/3/0/1197 |

Training table: 8,000 points (4,000/class), 3,397 Ravi/Beas + 2,893 Sutlej +
1,710 outside the two folds (used only in the final fit), committed as
`data/rf_training_points_2025.csv`. Final model: 200 trees, sklearn 1.8.0
defaults, features `VV_flood, VH_flood, dVV, dVH, slope`; importances
VV_flood 0.401, VH_flood 0.291, dVV 0.213, dVH 0.095, slope 0.0002 (slope is
carried but near-irrelevant on the Punjab plains at 90 m). Model saved to
`data/models/rf_2025.joblib` (55 KB — tiny because the strata are separable and
trees terminate shallow; committed, far under the 20 MB cap).

## Independent check — fresh random points, RF vs GFM union

5,000 random in-district points excluding all training indices:

| | GFM flood | GFM dry |
|---|---|---|
| **RF flood** | 28 | 27 |
| **RF dry** | 59 | 4,886 |

OA 0.983, F1 0.394, IoU 0.246. The disagreement is dominated by GFM-only flood
(59) — peak-day water our recession-biased composite never saw — plus 27
RF-only pixels (VH-informed fill). On a ~1 %-prevalence problem this is the
honest scale of divergence between two independent flood products; it is the
number that keeps band (b)'s 0.999s in perspective.

## Headline district table (top 8 of `data/district_flood_stats_2025.csv`)

| District | Tier-A ha | RF ha | crop-flooded ha | RF fraction |
|---|---|---|---|---|
| Firozpur | 10,997 | 14,096 | 11,967 | 2.71 % |
| Gurdaspur | 4,163 | 8,099 | 3,669 | 2.24 % |
| Kapurthala | 4,690 | 6,597 | 5,542 | 3.97 % |
| Tarn Taran | 4,546 | 6,355 | 4,726 | 2.66 % |
| Amritsar | 3,311 | 4,594 | 3,719 | 1.73 % |
| Jalandhar | 3,047 | 4,130 | 2,902 | 1.59 % |
| Moga | 1,860 | 2,269 | 1,725 | 0.97 % |
| Ludhiana | 712 | 1,621 | 439 | 0.45 % |

Statewide (in-district): Tier-A 33,938 ha, RF 52,223 ha, GFM 86,071 ha,
crop-flooded 36,195 ha. (Bbox-wide Tier-A is 105,183 ha — the rectangle
includes heavily-flooded Pakistani Punjab and Himachal margins outside the 20
district polygons.)

## Runtimes and transfer (2026-07-21)

| Stage | Wall time | Notes |
|---|---|---|
| GFM WMS fetch (10 days + refwater) | ~9 min | keyless GloFAS WMS, one 502 retried |
| S1 feature build (final run) | 4,819 s (80 min) | 25 scenes × VV+VH = 50 COG reads @ 90 m, 8 workers |
| two aborted S1 attempts | ~35 min | 12-worker stall; then dead-connection stall → HTTP-timeout fix |
| DEM slope + WorldCover + GFM warp | ~3.5 min | 16 GLO-30 + 4 WC tiles, overview reads |
| RF train + predict + stats + quicklooks | 29 s | 8k points; 12.7 M-pixel statewide predict |

Anti-hang fix that made the S1 run complete: GDAL's default cURL timeout is
unbounded, so dead Azure connections hung workers forever (observed 900–1,200 s
"reads", pool stalls >15 min). `pipeline/rf_build_features.py` and
`pipeline/rf_aux_layers.py` now set `GDAL_HTTP_TIMEOUT=240`,
`GDAL_HTTP_CONNECTTIMEOUT=30`, `GDAL_HTTP_LOW_SPEED_LIMIT/TIME=10240/60`,
`GDAL_HTTP_MAX_RETRY=2` on top of the SAS re-sign retry. The pre-flood window
is subsampled to ≤5 scenes per relative orbit (15 of 35; all three descending
swaths kept) — a median composite gains almost nothing from the extra 20
scenes and the read count is the binding cost under anonymous throttling.
New downloads this stage ≈ 1.1–1.3 GB, within the 3 GB budget.

## Dataset citations (accessed 2026-07-21)

| Dataset | Source | License / credit |
|---|---|---|
| ESA WorldCover 2021 v200 (class 40 = cropland) | Microsoft Planetary Computer, collection `esa-worldcover` (anonymous STAC) | **CC-BY 4.0** — © ESA WorldCover project 2021 / Contains modified Copernicus Sentinel data (2021) processed by the WorldCover consortium |
| Copernicus DEM GLO-30 | Microsoft Planetary Computer, collection `cop-dem-glo-30` (anonymous STAC) | © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA; all rights reserved |
| Sentinel-1 RTC (VV+VH features) | Planetary Computer `sentinel-1-rtc` | as recorded in `docs/notes/pc-sar.md` |
| GFM observed flood extent / reference water | keyless GloFAS WMS | as recorded in `docs/notes/gfm-wms.md` |

New Python packages: **none** beyond those already recorded in
`docs/notes/pc-sar.md` — scikit-learn 1.8.0, joblib 1.5.3, pandas were already
in the environment and in use elsewhere in the repo (`sailaab/model.py`).
