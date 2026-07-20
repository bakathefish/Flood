# Punjab Flood Intelligence — Execution Plan v2 (expanded scope)
**India AI Impact Festival 2026 entry · Deadline: July 26, 2026 (submit July 25) · Plan date: July 20, 2026**

Scope v2: not one flood map — a **flood intelligence system for Punjab**, in five waves:

| Wave | Deliverable | Status if deadline hits |
|---|---|---|
| 1 | **2025 Flood Atlas** — SAR AI mapping + crop-loss + validation (the v1 core) | REQUIRED — this alone is a winnable entry |
| 2 | **Decade Hazard Atlas** — every monsoon 2015–2025, flood-frequency & recurrence zonation | High value, low marginal cost |
| 3 | **Impact engine** — village/tehsil-level damage, flood depth, exposure, compensation math | Turns maps into relief tooling |
| 4 | **Forecaster** — district flood-risk model trained on our own SAR-derived labels | The AI-depth jewel: closes the loop |
| 5 | **Live monitor** — auto-running pipeline on every new S1 pass, live this monsoon | The "it's running right now" video moment |

Each wave ships independently; the video absorbs whatever is done by Day 5 evening. Cut from the bottom, never the top.

Working name candidates: **Sailaab** / **BaadhLens** / **FloodSight Punjab** — pick Day 1, it goes in every artifact.

---

## 0. Ground rules

- **What is judged:** synopsis PDF + ≤2-min video (student "AI Impact Creators" category; SDG-aligned impact, mandatory genuine AI, originality, open-source). The system exists to make those two artifacts undeniable.
- **Two-tier engineering everywhere:** classical baseline guaranteed, AI upgrade on top. Never zero.
- **Budget:** ~60 h across 6 days (Waves 1–3 are the first ~35 h; 4–5 the next ~25 h). Fallout (10 h, due 26th) is the external constraint — Day 6 is submit + buffer only.
- **Everything open** from Day 1: public GitHub repo, MIT/CC-BY.

---

## Phase 0 — Registration + environment (Day 1 morning, ~2 h)

1. **Portal first, before any code** — indiaaiimpactfest.ai-for-all.in: re-verify the Jul 26 deadline banner (moved once from Jul 15); confirm age bracket (13–17 vs 18+) and solo/team (2025 rule: ≤3); **screenshot every submission-form field** (synopsis format/limit, video upload vs link, declarations). The form is the real deliverable spec — capture it Day 1.
2. **Google Earth Engine** account (code.earthengine.google.com, free, usually instant). GEE is the compute stack — no local SAR processing, no GPU for the primary path.
3. **Repo init:** `README.md`, `gee/` (JS), `pipeline/` (Python, earthengine-api — needed for Waves 2/5 batch runs), `notebooks/`, `data/` (small CSVs), `atlas/` (outputs), `.github/workflows/` (Wave 5).
4. **Async registrations (needed Day 2–3):** Copernicus GFM account (global-flood.emergency.copernicus.eu); enumerate NDEM Punjab 2025 products (siblings of `ndem.nrsc.gov.in/documents/Disaster_Document/2025/PB/pbflood50dsc19082025_1100hrs/`) **and** check `2023/PB/`, `2019/PB/` folders — NDEM maps for older events become extra validation for Wave 2.

---

## Wave 1 — The 2025 Flood Atlas (Days 1–2, ~12 h)

### 1.1 Data assembly in GEE (Day 1, ~4 h)
- **AOI/admin:** `FAO/GAUL/2015/level2`, `ADM1_NAME=='Punjab'` (India), 23 districts (note in README if post-GAUL districts like Malerkotla are missing).
- **Sentinel-1:** `COPERNICUS/S1_GRD`, IW, VV+VH, both orbits. First job: **print every acquisition date + relative orbit** over the AOI, Jun 2025 – Sep 2025. Peak-flood mosaic window ≈ **Aug 27 – Sep 5, 2025** (rivers rose Aug 27; matches the published IJIST window — cite it). Pre-flood reference: per-orbit median composite Jul 1 – Aug 10, 2025. Preprocess in GEE: dB, focal-median/Refined-Lee 7×7 speckle filter, border-noise masking.
- **False-positive control:** `JRC/GSW1_4/GlobalSurfaceWater` occurrence >60% (permanent water out — rivers, canals, Harike), `COPERNICUS/DEM/GLO30` slope >5° masked (Shivalik radar shadow). Urban double-bounce under-detection stated honestly in README — honesty reads as sophistication.
- **Ancillary (pull now, use later):** `ESA/WorldCover/v200` cropland (class 40); `JRC/GHSL/P2023A/GHS_POP`; `NASA/GPM_L3/IMERG_V07` + `UCSB-CHG/CHIRPS/DAILY` rainfall; IMD 0.25° gridded NetCDF from imdpune.gov.in (the "official Indian data" framing; IMERG is the fallback math); AIKosh CWC daily reservoir CSV (Bhakra/Pong/Ranjit Sagar — India-WRIS or hand-keyed bulletin values as fallback, it's 3 dams × 40 days).

### 1.2 Models (Day 2, ~6 h)
- **Tier A — change detection (2 h, guaranteed):** UN-SPIDER practice. `ΔVV = post − pre`; threshold `ΔVV < −3 dB ∧ post_VV < −15 dB`, refined by Otsu on the difference histogram; masks applied; sieve ≥10 px. Shippable product exists from Day 2 noon onward.
- **Tier B — Random Forest in native GEE (4 h, the judged AI):** `ee.Classifier.smileRandomForest` (~200 trees). Precedent: IJIST Oct 2025 mapped this same flood (Pakistan side) with RF @ 98.3% — cite, then match on the Indian side.
  - **Features:** post VV, post VH, VV−VH, ΔVV, ΔVH, slope, elevation-above-drainage proxy, JRC occurrence.
  - **Labels without digitizing:** strata where Tier-A ∧ GFM agree (flood) and both agree dry (non-flood), stratified over land cover, ~3–5k pts/class.
  - **Honest validation — spatially disjoint folds:** train Ravi–Beas belt (Gurdaspur/Amritsar/Kapurthala) → test Sutlej belt (Ferozepur/Fazilka/Rupnagar), swap; report OA/F1/IoU. Say "spatial cross-validation" explicitly in the synopsis — it's the anti-leakage move a technical juror looks for.
  - **Ensemble framing:** final map = RF; Tier-A agreement = confidence layer.
- **Tier C — U-Net benchmark (3 h hard timebox, Day 4 slot):** Sen1Floods11 S1 VV/VH hand-labeled chips → small U-Net (segmentation-models-pytorch, Colab T4) → infer on exported Punjab tiles → 3-method benchmark table (threshold vs RF vs U-Net). Note: the HF Prithvi Sen1Floods11 fine-tune is **Sentinel-2-input** — wrong sensor for monsoon clouds; skip it.

### 1.3 Validation (Day 2 evening → Day 3, ~3 h)
- **Copernicus GFM:** download S1 flood layers for the window; confusion matrix on fresh random points (excluding training strata); report agreement %.
- **ISRO NDEM:** Kapurthala/Tarn Taran map (19 Aug 2025) — QGIS georeference (1 h timebox) → 100–200 check points; fallback: same-extent side-by-side visual panel (still video-gold: "our open model vs ISRO's locked PDF — same flood").
- **Official-figures band:** flooded area, villages (~1,400–1,900), crop area vs 1.48–1.75 lakh ha.

---

## Wave 2 — Decade Hazard Atlas 2015–2025 (Day 3, ~6 h)

Same pipeline, more dates — the marginal cost is orchestration, and the payoff is the single most original artifact in the entry: **Punjab has no public flood-hazard atlas** (NRSC published them for Assam/Bihar; nothing surfaced for Punjab). We make one, open.

1. **Batch runs (Python earthengine-api, not Code Editor):** for each monsoon Jun 15 – Sep 30, years 2015–2025 (S1 archive starts ~Oct 2014), build ~10-day rolling mosaics → Tier-A + RF flood masks per window. Known event anchors to sanity-check: **Jul 2023** (Sutlej/Ghaggar — Sangrur, Patiala, Rupnagar; NRSC mapped Sangrur 18 Aug 2023, 7,121 ha — direct validation point), **Aug 2019** (Sutlej breach, Jalandhar/Kapurthala bet areas), Sep 2018.
2. **Derived products:**
   - **Flood-frequency raster:** count of seasons each pixel flooded, 2015–2025 → recurrence classes (1×, 2–3×, ≥4×).
   - **Hazard zonation:** frequency × cropland × population → per-village/tehsil hazard score.
   - **"Repeat victims" table:** villages/tehsils flooding in ≥3 of 11 seasons — nobody has published this list openly; it is the relief-policy headline.
3. **Compute honesty:** GEE export quotas can throttle ~40 mosaic runs — mitigate by computing stats server-side (reduceRegions, no raster exports except final layers) and exporting only the frequency raster + per-event district CSVs.

---

## Wave 3 — Impact engine (Day 3–4, ~7 h)

1. **Crop loss (core):** flood mask ∩ WorldCover cropland → ha per district per event; 2025 total vs official 1.48–1.75 lakh ha = headline validation stat (explain divergence: snapshot vs cumulative season). **₹ value-at-risk:** paddy ha × ~6.5 t/ha × MSP 2025 ≈ ₹23,200/t — order-of-magnitude, clearly labeled estimate, cited.
2. **Damage persistence (1 h, if cloud-free S2 exists):** Sentinel-2 NDVI, Sep–Oct 2025 vs Sep–Oct 2024 over flooded cropland → kharif-loss persistence panel.
3. **Village-level analytics:** village boundaries from datameet `indian_village_boundaries` (Punjab coverage partial — verify first) → per-village flooded fraction + hazard score; **fallback: tehsil level** (datameet census tehsil shapefiles) if village polygons are patchy. Searchable lookup in the app = the girdawari-verification / compensation-targeting story made concrete (Punjab relief ran on manual crop surveys taking weeks).
4. **Flood depth (FwDET method, ~3 h):** boundary-elevation interpolation minus interior GLO-30 DEM (Cohen et al.; GEE implementations exist on GitHub — search "FwDET GEE" before writing it yourself) → per-pixel depth → depth-weighted damage classes. Cite the NHESS 2025 EOS-04 depth paper as precedent.
5. **Exposure:** GHSL population ∩ flood extent per district vs official ~3.55 lakh.
6. **The causal figure:** Bhakra (1,668.57 ft Aug 25 vs 1,680 danger) / Pong (~1,393 ft) / Ranjit Sagar (≈527 m) level curves annotated with the Aug 26–27 releases (~2.6 lakh cusecs Sutlej, >2 lakh Ravi), IMD/IMERG anomaly strip above (Barnala +887%, Ferozepur +450%, Amritsar +343%). One chart that explains *why* — jurors remember causal charts.

---

## Wave 4 — The Forecaster (Day 4, ~8 h)

The loop-closer: **the mapping engine generates its own training labels for a prediction model.** This is the architecturally novel claim — nobody hands you flood labels for Punjab; we manufactured 11 years of them in Wave 2.

1. **Dataset construction (~3 h):** unit = district × 10-day monsoon window, 2015–2025 (≈23 × ~10 × 11 ≈ 2.5k rows).
   - **Target:** SAR-derived flooded fraction (from Wave 2), both as regression and as binary "flood event" (fraction > threshold).
   - **Predictors:** basin-aggregated rainfall current + lagged 1–2 windows (IMERG/CHIRPS; upstream Himachal catchment rain matters more than local — aggregate over Sutlej/Beas/Ravi upstream basins, `WWF/HydroSHEDS` basins for the geometry); reservoir storage level + Δstorage (WRIS/AIKosh; 2015+ available); NRSC VIC soil moisture (AIKosh, 2018+ — feature is NaN before that, GBM handles it); antecedent flooded fraction; week-of-season.
2. **Model (~2 h):** gradient boosting (XGBoost/LightGBM) — right tool for 2.5k tabular rows; NOT deep learning (say why in the synopsis: sample-efficiency, interpretability). SHAP feature attributions → "dam storage change is the #2 predictor after upstream rain" is a publishable-grade sentence.
3. **Validation (~2 h):** leave-one-year-out CV; **showcase holdout = train 2015–2024, predict 2025**: did it flag Gurdaspur/Ferozepur/Kapurthala in the Aug 22–Sep 1 windows? Given +887% rain anomalies and near-capacity reservoirs in the predictor set, it should light up — if it flags high risk by the Aug 24 window, the video line writes itself: *"three days before the peak, the model saw it coming."* If it doesn't: report honestly, show what it did flag, frame as "hindcast skill under the most extreme event in the record" — still credible.
4. **Positioning vs Google Flood Hub (in synopsis):** Flood Hub forecasts gauge levels on ungauged-basin tech; it under-models **dam-regulated** rivers and doesn't output district crop-risk. Ours is regulation-aware (reservoir features) and impact-native (predicts flooded fraction, not stage). Complementary, not competing — that's the mature framing.

Risk note: open Sutlej/Beas/Ravi hourly gauge data does not exist (peninsular-only CWC open set) — that is exactly why the target is SAR-derived fraction, not river stage. The design routes around the data gap; say so.

---

## Wave 5 — Live monitor, running this monsoon (Day 5, ~5 h)

North India is flooding **right now** (25+ dead this weekend; Punjab under IMD flash-flood watch through Jul 21; PDMA warning on the Ravi at Jassar). A monitor that is literally live during judging is the strongest possible scalability proof.

1. **GitHub Action (cron, 6-hourly):** Python earthengine-api job → query new S1 acquisitions over Punjab since last run → if new: run RF classifier, compute district flooded km² + flagged tehsils → commit `latest.json` + PNG quicklook to repo → (optional 30 min) Telegram bot push.
2. **App integration:** the GEE App / a lightweight static page reads `latest.json` → "Last satellite pass: <date> · Districts above baseline: <list>".
3. **Auth note:** GEE service-account for CI (earthengine.google.com service-account docs) — 1 h of setup friction, budgeted.
4. **Video capture:** the July 2026 pass rendering live in the app. Even if 2026 Punjab inundation is minimal, the demo point stands: *"any new pass → district damage map, automatically, in under an hour."*

---

## Wave 6 — Packaging (Day 5, ~6 h) — never cut

1. **GEE App:** layers = 2025 flood (+confidence), decade frequency, hazard zonation, crop damage choropleth, live-monitor status; district/village click → stats panel.
2. **Static atlas:** state overview + 6–8 worst-district maps + frequency map, consistent cartography → the synopsis figures.
3. **Repo:** README as full method paper (data → models → validation → results → limitations), accuracy tables, reproduction steps, data-source table **highlighting the Government-of-India sources** (IMD, CWC/AIKosh, NDEM validation).
4. **Synopsis PDF** (match portal spec; default 4–6 pp): problem (worst since 1988, 3.55 lakh affected, all 23 districts) → the gap (locked PDFs, Pakistan-side papers, weeks-long manual surveys) → system diagram (5 waves as modules) → AI section (RF + spatial CV + forecaster + SHAP; benchmark table) → results → SDGs 2/11/13 → users (SDMA/DEOC, compensation verification, insurers, farmers) → roadmap (multi-state, ML depth, official partnerships) → open-source commitment + repo.
5. **Video (≤2 min — highest-leverage artifact; script verbatim, don't improvise):**
   - 0:00–0:20 hook: flood footage + stat cards ("Worst since 1988 · 3.55 lakh affected · 1.75 lakh ha crops").
   - 0:20–0:45 gap: NDEM locked PDF vs our interactive app, side by side.
   - 0:45–1:20 system: 10 s pipeline animation → live app demo: click Gurdaspur → stats; validation slide ("matches ISRO & Copernicus, F1 = 0.9x"); decade frequency map ("these villages flooded 4 times in 11 years — now everyone can see it").
   - 1:20–1:45 forecaster: the 2025 hindcast moment + SHAP bar ("rain upstream + a full dam = the signature it learned").
   - 1:45–2:00 close: live-monitor screen with today's date + "Open source. Built on India's open data. Running this monsoon." Repo URL + name.
   - Production: OBS captures + phone VO; CapCut/DaVinci; 10 s under the limit.
6. **Day 5 evening: dry-run the full portal form**, upload everything, stop before final submit.

## Day 6 (Jul 25) — Submit (~1 h)
Proofread → submit → screenshot confirmation. Buffer day before the deadline and Fallout.

---

## Day-by-day (≈60 h ceiling; cut-lines built in)

| Day | Load | Content |
|---|---|---|
| 1 (Jul 20) | ~8 h | Phase 0 + Wave 1 data assembly + Tier A started |
| 2 (Jul 21) | ~10 h | Tier A done · RF trained + spatial CV · validation started → **shippable core exists** |
| 3 (Jul 22) | ~12 h | Wave 2 decade batch (runs mostly unattended — interleave) + Wave 3 impact engine |
| 4 (Jul 23) | ~12 h | Wave 4 forecaster + Tier-C U-Net (3 h timebox) + NDEM georef |
| 5 (Jul 24) | ~12 h | Wave 5 live monitor + Wave 6 app/repo/synopsis/video + form dry-run |
| 6 (Jul 25) | ~1 h | Submit. Rest of day → Fallout (due Jul 26) |

## Risk register (deltas from v1)

| Risk | L | Mitigation |
|---|---|---|
| Deadline/form differs from research | M | Phase 0.1 verifies Day 1; targeting Jul 25 regardless |
| GEE batch quotas throttle Wave 2 | M | Server-side stats only; export only final rasters; shrink to alternate years (2019/2021/2023/2025) if needed — frequency map survives |
| Village polygons patchy | M | Pre-verified fallback: tehsil level |
| Forecaster hindcast misses 2025 | L–M | Honest reporting + "most extreme event in record" framing; SHAP still delivers the dam-release insight |
| GEE service-account/CI friction (Wave 5) | M | 1 h budgeted; fallback = manually-triggered Action (still "live" for the video) |
| FwDET depth eats time | M | It's garnish — cut before anything else in Wave 3 |
| RF disappoints on spatial split | L | Ensemble/confidence framing; published precedent says it works |
| IB crunch collision | H | Waves ordered so Days 1–2 alone = winnable entry; Day 6 is Fallout's |
| Fair-use footage in video | L | Prefer own renders/Sentinel animations; credit on-screen |

## Cut-line ladder (bottom = cut first)
Video polish → Synopsis → Wave 1 (atlas + RF + validation) → Wave 3.1 crop loss → Wave 2 frequency map → Wave 4 forecaster → Wave 5 live monitor → Wave 3.4 depth → Tier-C U-Net → Telegram bot.

---

## Wave 7 — The Win Layer (threaded through Days 3–5, ~6 h)

The jury sees a synopsis and 120 seconds of video. Waves 1–5 make the entry *credible*; this wave makes it *win*. Past winners (Ishaara, Sporty Coach) won on human story + polish, not model depth — we bring both.

1. **The personal narrative (0 h, highest ROI).** This is a Punjab student building what the state doesn't have, for their own state, during a live monsoon. The video now OPENS with it: *"Last August, my state went underwater — the worst flood since 1988. The satellite maps that could have guided relief? Locked in PDFs."* First-person beats third-person in every judged competition; the Intel global round explicitly sells "young changemaker" stories. If any personal flood connection exists (family, village, school closure) — 5 seconds of it outweighs any animation.
2. **Punjabi vernacular alerts (~2 h) — the "AI for Bharat" checkbox made literal.** Wave 5's monitor auto-generates each district alert in **Punjabi + Hindi + English** (template-based; ਜ਼ਿਲ੍ਹਾ/district, flooded area, trend, helpline) pushed via Telegram. Last-mile inclusion for farmers is precisely the festival's theme; a jury watching an alert arrive *in Punjabi* on a phone will remember it. (Roadmap line: Bhashini API for voice alerts — name-drops the IndiaAI ecosystem correctly.)
3. **Cinematic assets (~2 h):**
   - **SAR timelapse GIF** (native GEE `getVideoThumbURL`): Aug 20 → Sep 5 mosaics — water visibly swallowing the doab. The video's most visceral 8 seconds.
   - **Before/after swipe** in the app (GEE split-panel widget, trivial) — the demo interaction juries love to see clicked.
   - **Google Earth Studio flyover** of a flooded district for the hook (free, ~1 h learning curve; cut first if time bites — the timelapse alone carries).
4. **Product identity (~1.5 h):** commit to one name (recommend **Sailaab** — one word, memorable, bilingual resonance); logo (image-gen); **GitHub Pages landing page** (one screen: tagline, live-monitor status, app link, repo link). A URL that looks like a product, not homework — it goes in the synopsis header, the video close, and the submission form.
5. **Stakeholder outreach (~30 min, Day 3 — send early so replies can land by Day 5):** short email with the district atlas PDF to Punjab SDMA, the Revenue Dept (girdawari owners), and 2–3 worst-hit District Collectors, offering the tool free. Any reply — even an acknowledgment — becomes a synopsis line: *"shared with PSDMA; feedback incorporated."* No reply costs nothing; the attempt itself is honest to state as "shared with."
6. **Numbers that stick (0 h, write them down as they emerge):** "11 monsoons · 40+ satellite mosaics · X billion pixels classified · 23 districts · 3 languages · validated against 2 space agencies." The video close card and synopsis abstract both use this string.

**Video script v2 delta:** open on the personal narrative (replaces generic hook), timelapse at 0:20, Punjabi alert arriving on a phone at 1:45, close card = numbers string + "Open source. Running this monsoon." — everything else as Wave 6.

## After the festival (parking lot, not this week)
Top-3 Creators → Intel AI Global Impact Festival (this system scales to that stage as-is). The Wave 2+4 combination (self-labeled decade dataset + regulation-aware forecaster, SHAP-attributed) is independently a science-fair/paper-grade result if written up with proper uncertainty treatment — a decision for August, not now.
