# Sailaab — Punjab Flood Intelligence
**Open SAR flood mapping · decade hazard atlas · impact analytics · district flood forecasting · live monitoring**
India AI Impact Festival 2026 · AI Impact Creators (student) · https://bakathefish.github.io/Flood/ · github.com/bakathefish/Flood

> *Format note: the portal's synopsis specification is visible only after registration; this document follows the default 4–6 page structure and will be reflowed to the exact spec on submission.*

## 1. The problem

In August–September 2025, Punjab suffered its worst flood since 1988: all 23 districts affected, ~3.55 lakh people, 1.48–1.75 lakh hectares of crops destroyed, dozens of lives lost. Three failures made it worse than it had to be:

- **Maps existed but were locked.** ISRO's NDEM produced excellent flood maps — as static PDFs, one snapshot at a time, not analyzable, not overlayable, not open.
- **Nobody knew the recurrence.** Punjab has no public flood-frequency atlas (NRSC published them for Assam and Bihar). Villages that flooded four times in a decade were treated as first-time surprises.
- **Relief ran on foot.** Compensation (girdawari) required weeks of manual crop surveys while satellite data that could target it sat unused.

## 2. What Sailaab is

A five-module open pipeline that turns free satellite radar into decision-grade flood intelligence for Punjab — built by a Punjab student during the 2026 monsoon, running live today.

| Module | What it produces |
|---|---|
| **2025 Flood Atlas** | Sentinel-1 SAR flood extent (physics baseline + Random Forest), per-district statistics |
| **Decade Hazard Atlas** | Every monsoon 2015–2025 mapped identically → Punjab's first public flood-frequency map + "repeat victims" table |
| **Impact Engine** | Crop-flooded hectares (ESA WorldCover overlay), ₹ value-at-risk, and the causal chart: rain × dams × releases |
| **Forecaster** | XGBoost district flood-risk model trained on the pipeline's own decade of SAR-derived labels — SHAP-explained |
| **Live Monitor** | Every new Sentinel-1 pass → district flood km² → Punjabi/Hindi/English alerts, automatically, every 6 hours |

**Everything is login-free and reproducible.** During the build we proved a fully account-free acquisition path: anonymous Planetary Computer STAC for Sentinel-1, the keyless GloFAS WMS for Copernicus Global Flood Monitoring layers, IMD gridded rainfall, and CWC reservoir records. Anyone — a district collector, a journalist, a student — can re-run every number with zero accounts.

## 3. The AI (and why it is honest)

**Random Forest flood classifier (Wave 1).** Features: VV/VH backscatter, pre/post change, terrain. Labels: bootstrapped from *agreement* between our physics-threshold map and Copernicus GFM — no hand digitization, and stated as such. Validation is **spatial cross-validation across river basins** (train Ravi–Beas districts → test Sutlej districts, and swap), the anti-leakage design a technical juror looks for. We report the trap honestly: agreement-strata points are near-separable (fold F1 ≈ 1.0), so we also publish the independent fresh-point comparison against GFM (OA 0.983) and the three-method envelope (Tier-A 34k ha < RF 52k ha < GFM 86k ha across in-district areas). Statewide 2025 SAR-flooded area: **105,183 ha**; crop-flooded snapshot **36,195 ha ≈ ₹546 crore** paddy value at risk (single-pass snapshot vs the official *cumulative-season* 1.48–1.75 lakh ha — divergence explained, not hidden).

**The self-labeling loop (Wave 2 → 4).** Nobody hands you 11 years of Punjab flood labels — so the mapping engine manufactured its own: 1,177 day-slots probed, 467 flood-active days rasterized, 2,420 district-window training rows. In doing so we caught and published a trap that would silently poison any naive attempt: **June–July "floods" in Punjab are largely rice transplanting** — deliberately flooded paddies inflate apparent flood area ~20×. All forecaster training excludes the transplant windows; the calibrated late-season products ship alongside the raw ones.

**XGBoost district forecaster (Wave 4).** Unit: district × 10-day monsoon window, 2015–2025. Predictors: IMD rainfall (local + Himalayan upstream, with lags), CWC/BBMB reservoir storage and its rate of change, antecedent flooding, decade-frequency prior. Gradient boosting, not deep learning — the sample-efficient, interpretable right tool for 2.5k tabular rows. Leave-one-year-out validation: pooled ROC-AUC **0.946**, PR-AUC 15× base rate, leakage-checked.

**The headline result.** Trained only on 2015–2024 and shown 2025's predictors, the model **flagged all five districts that actually flooded — Kapurthala ranked #1 statewide (P = 0.72)** — and four of the five were already in its top-5 during the **Aug 14–24 window, ~10 days before the Aug 26–27 dam-release peak**. SHAP attribution says why: antecedent flooding, flood-history prior, and **Bhakra reservoir storage** are the top drivers. A full dam is part of the signature it learned — which is precisely the mechanism the 2025 disaster followed.

**Positioning vs Google Flood Hub:** Flood Hub forecasts river stages on ungauged-basin technology; it under-models dam-*regulated* rivers and does not output district crop risk. Sailaab is regulation-aware (reservoir features) and impact-native (predicts flooded fraction). Complementary, not competing.

## 4. Verified against two space agencies — with the failures kept

Every satellite step is gated by a **pre-declared checkpoint**: the expected numeric band is written into the verification log *before* the run, then the actual, then PASS/FAIL. The log ships in the repo, failures included — e.g., the NRSC Sangrur-2023 anchor comparison **fails** on its exact date because no Sentinel-1 pass existed that day (the same event registers at full strength in adjacent windows: Sangrur 33,771 ha), and the naive fold metrics are flagged as strata artifacts. Validation sources: Copernicus GFM (fresh-point confusion matrices) and ISRO NDEM 2025 map sheets (4 products located and compared). Independent confirmations: IMD data shows Aug 20–Sep 5 2025 rainfall at **+9.7σ, rank 1 of 11 years** in both the Punjab and upstream boxes; reservoir records confirm Pong over its brim (1,393 ft, Aug 26) and Ranjit Sagar's 1.73-lakh-cusec release (Aug 27). We also documented that the three BBMB dams stopped reporting to the central CWC feed on **11 July 2025** — weeks before the flood — a data-transparency finding in itself.

## 5. Running right now

The live monitor is not a plan — it executed during this build. On a GitHub CI runner with **zero secrets and zero accounts**, it detected the most recent Sentinel-1 pass over Punjab (20 July 2026), computed district flood areas (a quiet 2.4 km² day, honestly reported as such), and committed the state — as it now does automatically every six hours, generating alerts in ਪੰਜਾਬੀ, हिन्दी and English whenever any district crosses the alert floor. The landing page reads this feed live.

## 6. Impact, users, SDGs

- **SDMA / district EOCs:** recurrence zones + live district km² for pre-positioning and evacuation priority.
- **Revenue Dept / girdawari:** flood-extent ∩ cropland per village-circle turns weeks of manual crop-loss survey into a verification exercise (₹546 crore at risk quantified in hours, not weeks).
- **Insurers (PMFBY) and banks:** independent, reproducible loss extents.
- **Farmers and the public:** vernacular alerts; every map open.
- **SDGs:** 2 (crop-loss quantification), 11 (resilient communities), 13 (climate adaptation).

## 7. Originality

(1) First open ML-ready flood mapping of Indian-Punjab 2025 (the published RF precedent covered the Pakistani side); (2) **Punjab's first public flood-frequency atlas**; (3) a self-labeling SAR→ML loop that manufactures its own decade of training data, with the paddy-transplant contamination discovery published; (4) a dam-regulation-aware district forecaster with ~10-day demonstrated lead on the 2025 disaster; (5) an end-to-end account-free architecture — reproducibility as a design principle, not a promise.

## 8. Roadmap

Multi-state scale-out (the pipeline is a bbox + district file), village-circle girdawari integration with Revenue Dept, Bhashini voice alerts, deeper models (U-Net benchmark on Sen1Floods11 chips) as data grows, and official partnerships — outreach to PSDMA and the worst-hit District Collectors is prepared for dispatch with this submission.

## 9. Open source

MIT (code) + CC-BY-4.0 (maps/tables). 168 automated tests. Method paper, data-source registry (every dataset: URL, license, access date), and the full verification log: **github.com/bakathefish/Flood** · live: **bakathefish.github.io/Flood**

*11 monsoons · 467 flood days · 105,183 ha mapped · 20 districts · 3 languages · 2 space agencies · 0 logins required.*
