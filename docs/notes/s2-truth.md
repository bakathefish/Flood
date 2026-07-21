# Independent optical truth set — Sentinel-2 water points vs RF / Tier-A / GFM

The one thing the validation chain lacks. The RF classifier is trained on
**Tier-A ∧ GFM agreement** labels and then reported against GFM; a skeptic calls
that circular — every number in the chain descends from the same two SAR-era
products. This note builds a truth set from a **different sensor and different
physics**: photo-interpreted standing-water points from **Sentinel-2 L2A optical
surface reflectance** (Copernicus, via anonymous Microsoft Planetary Computer
STAC). Optical NDWI has no shared failure mode with C-band SAR change detection —
if the SAR masks and the optical water points agree, the agreement is not an
artefact of one instrument.

Architecture mirrors the repo: pure array logic (NDWI, water decision rule,
stratified sampling) in `sailaab/s2.py`, unit-tested test-first in
`tests/test_s2.py`; all STAC / rasterio IO in `pipeline/fetch_s2_truth.py`.

---

## 1. PRE-DECLARED design + honest asymmetry (written BEFORE any imagery was opened)

Declared 2026-07-22, before the S2 scene search, before any NDWI or chip was
computed. Per the repo's verification discipline (see `docs/notes/rf-train.md`):
the design, the decision rule structure, and the acceptance band are committed
first; actuals and PASS/FAIL verdicts are appended afterwards and never edited to
fit.

### 1.1 The recession asymmetry — the core honesty problem

The 2025 Punjab flood peaked **26–27 Aug 2025**. The monsoon cloud deck sits
over the peak: optical Sentinel-2 sees the ground only *after* the clouds clear,
which for this event means **early September onward** — days to weeks into
**recession**. This makes the optical truth set **fundamentally asymmetric** as a
validator, and we state exactly how before looking at a single pixel:

- **S2 shows standing water at a pixel  ⟹  that pixel was flooded.** Water present
  in a post-peak optical scene is real open water; if it is still wet in
  September it was certainly wet at the late-August peak. So **S2-water points
  validate the flood masks' PRECISION / commission strongly** — a mask pixel that
  claims "flood" and lands on S2-water is confirmed by an independent sensor.

- **S2 shows dry ground at a pixel  ⟹  NOTHING about late-August flooding.** The
  water may have receded between the peak and the (later) S2 pass. A mask pixel
  that claims "flood" but lands on S2-dry is **ambiguous**: it is *either* a
  commission error *or* a true peak-flood pixel that drained before the optical
  window. We therefore **cannot** count mask-flood/S2-dry as a hard false
  positive, and we will not. **S2-dry points validate OMISSION only weakly.**

### 1.2 How both directions are reported (pre-committed)

Scoring is split so the strong and weak directions never contaminate each other.
For each mask `m ∈ {RF, Tier-A, GFM-union}`, with `pred = m says flood` and
`ref = S2 says water`, computed with `sailaab.validation.binary_metrics`:

- **On S2-water points (strong):** recall_water = TP/(TP+FN) = of independently
  confirmed standing-water points, the fraction the mask caught. A mask that
  cannot find water that is *still there in September* has a real omission
  problem, so recall on S2-water is a meaningful (not weak) omission check.
- **Precision (strong):** precision = TP/(TP+FP) = of the points the mask calls
  flood, the fraction that are S2-water. This is the commission check S2 is built
  to make.
- **On S2-dry points, mask-positive (weak / reported not penalised):** the
  **recession-explained fraction** = FP/(TP+FP) = of the mask's flood points, the
  fraction that came back S2-dry. Reported per mask, explicitly, as recession +
  commission *combined* — never hidden, never counted as pure error.

Every count of **uncertain** points dropped by the decision rule (§1.4) is
reported too.

### 1.3 Stratified sampling design (~250 points, 3 strata)

Points are drawn only inside the chosen S2 scene footprints AND inside the Punjab
district polygons AND where S2 is cloud-free (SCL, §1.4):

1. **mask-flood** — pixels where **any** of {RF, Tier-A, GFM-union} = flood.
   Oversampled so every mask's positive claim is well tested (precision needs a
   populated mask-positive set). ~40 %.
2. **mask-dry-near-flood** — pixels where **all** masks = dry but within a
   dilation buffer of the flood union (the recession/omission frontier + dry
   controls next to real water). ~30 %.
3. **random** — uniform random inside footprint ∩ Punjab (background prevalence,
   an unbiased control). ~30 %.

Deterministic RNG (seed fixed in the pipeline). Target ~250 classified points
after dropping uncertain.

### 1.4 Water decision rule (structure pre-declared; thresholds calibrated on Harike)

Primary index: **McFeeters NDWI = (B03_green − B08_nir) / (B03 + B08)** on
harmonised L2A surface reflectance (baseline-04.00+ BOA offset applied). Per
point:

1. Read the SCL (scene-classification) class. If SCL ∈ {0 no-data, 1 defective,
   3 cloud-shadow, 8 cloud-med, 9 cloud-high, 10 thin-cirrus} → **uncertain
   (drop)**. Optical cannot see ground through cloud; those points are honestly
   discarded, not guessed.
2. Otherwise classify by NDWI with a **deliberate dead-band** so only
   high-confidence points enter the truth set:
   - NDWI ≥ `t_water` → **water**
   - NDWI ≤ `t_dry`   → **dry**
   - `t_dry` < NDWI < `t_water` → **uncertain (drop)**
3. `t_water` / `t_dry` are **calibrated on Harike** (the Sutlej–Beas confluence
   wetland/reservoir, ~74.95 E 31.17 N — permanent open water) as the water
   anchor and confirmed dry cropland/urban as the dry anchor, then **documented**
   in §3 with the measured NDWI distributions. Pre-declared starting point:
   McFeeters `t_water ≈ 0`; the dead-band is widened from the Harike separation,
   not tuned to move any score.
4. The 6-chip true-colour quicklook (`atlas/checks/s2_truth_examples.png`, B04/
   B03/B02) is the **visual audit** of the rule: water and dry example points with
   markers, so the NDWI rule can be eyeballed against real chips.

### 1.5 PRE-DECLARED acceptance bands

| # | Band | Threshold declared in advance | Type | Rationale |
|---|---|---|---|---|
| **S1** | RF **precision on S2-water** (TP/(TP+FP), mask=RF) | **≥ 0.60** | PASS/FAIL gate | The mission's headline test: the judged AI stage's flood pixels, checked against an independent optical sensor, must be right on water ≥ 60 % of the time. Not 1.0 — recession guarantees some RF-flood pixels are legitimately dry by the S2 date. |
| **S2** | Precision ordering | **Tier-A ≥ RF ≥ GFM-union** | characterise | Tier-A is the strictest geometry (change-detection AND absolute-dark), so its flood pixels should most often still be water; GFM-union is the widest (any-of-6-days peak capture), so it should carry the most receded (S2-dry) pixels → lowest precision. A falsifiable structural prediction. |
| **S3** | Recall ordering on S2-water | **GFM-union ≥ RF ≥ Tier-A** | characterise | Breadth mirror of S2: the widest mask should miss the fewest confirmed-water points. |
| **S4** | Recession-explained fraction (mask-pos & S2-dry) | **substantial and largest for GFM-union**; report per mask | characterise | Direct measurement of §1.1; expected non-trivial for all masks and biggest for the peak-capturing GFM union. Reported, never penalised. |

Band **S1** is the pass/fail gate. **S2–S4** are documented characterisations of
the asymmetry, reported with physics, not tuned.

---

## 2. Scenes used (Planetary Computer `sentinel-2-l2a`, anonymous)

Search bbox = union of the three named district polygons `(73.885, 29.947,
75.911, 31.651)`. **Scene-hunt gotcha, recorded:** the R048 orbit's 43RDQ
granules on 2025-09-16/09-21 report ~0 % cloud but are **partial west-edge
slivers** (73.95-74.33 E only) that miss Harike entirely — cloud_cover is a
per-granule statistic, so partial granules mislead. The **R005** orbit gives FULL
(100 %) belt coverage; those are the scenes used, earliest first (each truth point
takes its class from the earliest date that is cloud-free AND covered at that
point, to minimise recession; later dates only backfill cloudy stragglers):

| Date | Days post-peak | Central-belt (43RDQ) cloud | Classified points assigned |
|---|---|---|---|
| **2025-09-10** | 14 | 10.8 % | 177 |
| **2025-09-18** | 22 | 5.9 % | 47 |
| **2025-09-23** | 27 (pristine, 0 %) | 0.0 % | 13 |

All granules are native **EPSG:32643** (UTM 43N) — identical CRS to the mask grid
— so each point is read by a small **2×2 window at native 10 m ≈ 20 m** in native
coordinates (no reprojection). Belt granule tiles: 43RCP/RCQ/RDP/RDQ/REP/REQ
(+43SCR/SDR/SER margins). Every candidate got a clean optical look (**0** points
with no cloud-free coverage). Total S2 transfer was a few tens of MB (windowed
point reads only) — far under the 2 GB budget.

## 3. NDWI threshold calibration on Harike + point counts

Calibrated on the **pristine 2025-09-23** scene (tiles 43REQ+43RDQ), NDWI sampled
at three anchor sets (cloud-free pixels only):

| Anchor | n | NDWI p50 | p95 | p98 |
|---|---|---|---|---|
| **dry-land** (all masks dry, >500 m from water) | 1,063,001 | −0.681 | −0.397 | −0.271 |
| **SCL water class** (Sen2Cor, independent) | 82,248 | +0.003 | +0.239 | +0.325 |
| **Harike / GFM ref-water** | 70,017 | −0.071 | +0.238 | +0.312 |

Dry cropland is confidently negative (p98 = **−0.27**); turbid Punjab flood water
and the Harike wetland straddle **0** (sediment load and aquatic vegetation
suppress NDWI — an honest, event-specific fact). Chosen rule (McFeeters,
documented in `sailaab.s2`): **t_water = 0.0, t_dry = −0.20**, dead-band
(−0.20, 0.0) dropped as uncertain. Verification on the anchors: **99.4 %** of
dry-land is ≤ t_dry and **51.8 %** of independent SCL-water is ≥ t_water, so the
thresholds sit in the observed gap and were **not** tuned to any mask score.
Permanent water (GFM ref-water) is **excluded from sampling** — the masks exclude
it by construction, and it is optically marshy/ambiguous here — so we score flood
detection, not permanent water.

**Point counts:** 285 stratified candidates → **237 classified** (93 water /
144 dry); **48 dropped uncertain** (all NDWI dead-band; 0 lacked coverage). The
dead-band fell mostly on turbid mask-flood pixels (rf_pos 55→28, gfm_pos 55→40
classified) while the SW-Firozpur Tier-A cluster stayed clean (tierA_pos 55→51).
Classified by district: Firozpur 152, Kapurthala 52, Tarn Taran 33.

## 4. ACTUALS vs pre-declared bands (runs of 2026-07-22, appended after the fact)

Confusion is `pred = mask says flood`, `ref = S2 says water`, over the 237
classified points (`sailaab.validation.binary_metrics`):

| Mask | flood pts | TP | FP | FN | TN | **precision on water** | recall on water | recession-explained frac |
|---|---|---|---|---|---|---|---|---|
| **RF** | 104 | 85 | 19 | 8 | 125 | **0.817** | 0.914 | 0.183 |
| **Tier-A** | 54 | 53 | 1 | 40 | 143 | **0.981** | 0.570 | 0.019 |
| **GFM-union** | 115 | 89 | 26 | 4 | 118 | **0.774** | 0.957 | 0.226 |

| # | Band (declared) | Actual | Verdict |
|---|---|---|---|
| **S1** | RF precision on S2-water **≥ 0.60** (GATE) | **0.817** (85 of 104 RF-flood points are S2-confirmed water) | **PASS** |
| **S2** | precision order **Tier-A ≥ RF ≥ GFM-union** | 0.981 ≥ 0.817 ≥ 0.774 | **CONFIRMED** |
| **S3** | recall-on-water order **GFM-union ≥ RF ≥ Tier-A** | 0.957 ≥ 0.914 ≥ 0.570 | **CONFIRMED** |
| **S4** | recession frac substantial, **largest for GFM-union** | GFM 0.226 > RF 0.183 > Tier-A 0.019 | **CONFIRMED** |

**Recession asymmetry, reported both ways (per §1.2):**
- *On S2-water points (strong / commission + real omission):* Tier-A catches 53
  of 93 confirmed-water points, RF 85, GFM 89 — GFM misses only 4. Precision on
  water: RF 82 %, Tier-A 98 %, GFM 77 %.
- *On S2-dry, mask-positive (weak / recession, not penalised):* 19 of 104 RF-flood
  and 26 of 115 GFM-flood points had dried by the optical pass — reported as the
  recession-explained fraction (18 % / 23 %), **not** as false positives. Tier-A's
  is 1 point (2 %).

**Verdict — the circularity is broken.** An independent optical sensor
(different physics from the SAR chain) confirms that **82 % of the RF classifier's
flood pixels are still standing water two weeks after the peak** (S1 PASS, gate
cleared with margin). All three structural predictions hold: RF sits **between**
its Tier-A and GFM-union label parents on *both* precision (0.82, between 0.98 and
0.77) and recall (0.91, between 0.57 and 0.96) — the "RF ⊂ envelope(Tier-A, GFM)"
claim of `rf-train.md`, now corroborated by a sensor outside the SAR chain. Tier-A
is near-perfectly precise (98 %) but conservative (misses 43 % of standing water);
GFM-union is the broadest (96 % recall) at the cost of the most receded pixels.
Recession is real but modest here (18-23 % for RF/GFM) because earliest-clean
sampling pulled most points to the 14-day scene; it is reported, not hidden.

**Honest limits.** (i) Optical truth is post-peak, so S2-dry never refutes
August flooding — omission is only validatable on water *still present* in
September (recall-on-water), not on the peak extent. (ii) Water anchors are
turbid, so the dead-band drops ~20 % of mask-flood points (kept out of scoring,
not misclassified). (iii) Tier-A's in-district positives are a single SW-Firozpur
cluster, so its 54-point precision rests on that locale; RF and GFM span all three
districts. (iv) GFM ref-water location is used to *place* dry/permanent-water
exclusions, a weak GFM dependency in sampling only — the NDWI verdict at every
point is fully independent.
