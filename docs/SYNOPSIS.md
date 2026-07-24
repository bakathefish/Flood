# Sailaab: Punjab Flood Intelligence
**Open SAR flood mapping · decade hazard atlas · impact analytics · district flood forecasting · live monitoring**
India AI Impact Festival 2026 · AI Impact Creators (student) · https://bakathefish.github.io/Flood/ · github.com/bakathefish/Flood

## 1. The problem

In August and September 2025 Punjab suffered its worst flood since 1988: all 23 districts affected, about 3.55 lakh people, 1.48 to 1.75 lakh hectares of crops destroyed, dozens of lives lost. Four failures made it worse than it had to be.

- **Nobody was forecasting.** In the Central Water Commission's own state-wise table, Punjab has **zero flood-forecasting stations**. It is absent from a 226-station national network (Haryana has 1, J&K 3), and the single site CWC ever added on the Ravi is defunct (SANDRP 2019/2023; `docs/notes/cwc-gap.md`, `atlas/cwc_station_gap.png`). Punjab's rivers sit outside India's flood-forecast network.
- **Maps existed but were locked.** ISRO's NDEM produced excellent flood maps, but as static PDFs: one snapshot at a time, not analyzable, not overlayable, not open.
- **Nobody knew the recurrence.** Punjab has no public flood-frequency atlas (NRSC published them for Assam and Bihar). Villages that flooded four times in a decade were treated as first-time surprises. Even the public damage record is sparse milestones rather than a series (`atlas/punjab_flood_history.png`).
- **Relief ran on foot.** Compensation (girdawari) required weeks of manual crop surveys while satellite data that could target it sat unused.

## 2. What Sailaab is

A five-module open pipeline that turns free satellite radar into flood intelligence a district officer can act on. I built it in Punjab during the 2026 monsoon, and it is running live today.

| Module | What it produces |
|---|---|
| **2025 Flood Atlas** | Sentinel-1 SAR flood extent (physics baseline + Random Forest), per-district statistics |
| **Decade Hazard Atlas** | Every monsoon 2015 to 2025 mapped identically, giving Punjab's first public flood-frequency map and a "repeat victims" table |
| **Impact Engine** | Crop-flooded hectares (ESA WorldCover overlay), ₹ value-at-risk, and the causal chart: rain, dams, releases |
| **Forecaster** | XGBoost district flood-risk model trained on the pipeline's own decade of SAR-derived labels, explained with SHAP |
| **Live Monitor** | Every new Sentinel-1 pass becomes district flood km² and Punjabi/Hindi/English alerts, automatically, every 6 hours |

The analysis goes below district level. **All 91 tehsils are individually scored**, which produces a named repeat-victims list: Khadur Sahib (Tarn Taran) flooded in 6 of the last 11 monsoons, Sultanpur Lodhi (Kapurthala) in 5, Moonak (Sangrur) and Patti (Tarn Taran) in 4. These are the exact administrative units where girdawari verification and pre-positioning should start. Population exposure adds the human denominator: **0.76 to 1.78 lakh people lived inside the mapped water** (GHSL 2025), consistent with the official 3.55 lakh "affected" figure once you see that flooded land is overwhelmingly low-density cropland (146 to 206 people/km² against Punjab's mean near 550).

**Everything is login-free and reproducible.** During the build we proved a fully account-free acquisition path: anonymous Planetary Computer STAC for Sentinel-1, the keyless GloFAS WMS for Copernicus Global Flood Monitoring layers, IMD gridded rainfall, and CWC reservoir records. A district collector, a journalist, or another student can re-run every number with zero accounts.

## 3. The AI, and why it is honest

**Random Forest flood classifier (Wave 1).** Features: VV/VH backscatter, pre/post change, terrain. Labels are bootstrapped from *agreement* between our physics-threshold map and Copernicus GFM. No hand digitization, and the synopsis says so. Validation is **spatial cross-validation across river basins** (train on Ravi-Beas districts, test on Sutlej districts, then swap), the anti-leakage design a technical juror looks for. We report the trap honestly: agreement-strata points are near-separable (fold F1 ≈ 1.0), so we also publish the independent fresh-point comparison against GFM (OA 0.983) and the three-method envelope (Tier-A 34k ha < RF 52k ha < GFM 86k ha across in-district areas). Statewide 2025 SAR-flooded area: **105,183 ha**; crop-flooded snapshot **36,195 ha**; paddy value at risk **₹523 crore** (v2, computed on the government's own DES district yields; the duration-weighted damage estimate is **₹351 crore**, and we publish the full band rather than the biggest number). The single-pass snapshot differs from the official *cumulative-season* 1.48 to 1.75 lakh ha for reasons we explain rather than hide.

**The self-labeling loop (Waves 2 to 4).** Nobody hands you 11 years of Punjab flood labels, so the mapping engine manufactured its own: 1,177 day-slots probed, 467 flood-active days rasterized, 2,420 district-window training rows. Doing that exposed a trap that would silently poison any naive attempt: June and July "floods" in Punjab are largely rice transplanting, because deliberately flooded paddies inflate apparent flood area about 20 times. All forecaster training excludes the transplant windows, and the calibrated late-season products ship alongside the raw ones.

**XGBoost district forecaster (Wave 4).** Unit: district × 10-day monsoon window, 2015 to 2025. Predictors: IMD rainfall (local and Himalayan upstream, with lags), CWC/BBMB reservoir storage and its rate of change, antecedent flooding, and a decade-frequency prior. Gradient boosting rather than deep learning, because it is the sample-efficient, interpretable right tool for 2.5k tabular rows. Leave-one-year-out validation: pooled ROC-AUC **0.946**, PR-AUC 15 times the base rate, leakage-checked.

**The headline result.** Trained only on 2015 to 2024 and shown 2025's predictors, the model flagged **all five districts our SAR atlas ranked most-flooded, a ranking the government's own ground girdawari later corroborated (ρ = 0.72 all districts, 0.56 named)**, with Kapurthala #1 statewide (P = 0.72 in the pre-declared flood windows; two districts clear P ≥ 0.5, and Amritsar is a rank-5 flag at low probability, stated rather than rounded up). The forecasting claim is the **pre-crest lead**: four of the five were already in the statewide top-5 during the **Aug 14–24 window, roughly 10 days before the Aug 26–27 dam-release peak**, and the flags are unchanged under fold-safe priors (leakage-checked).

**The ablation we ran on ourselves (pre-declared; both expectations failed; shipped verbatim in `docs/notes/ablation.md`).** A reviewer would ask two things, so we asked first. *Does the dam signal carry skill?* SHAP ranks Bhakra storage #3 in attribution. But delete all six reservoir features and the 2025 hindcast is **unchanged** (5/5 flagged, Kapurthala #1, the same 10-day lead) while pooled precision even improves. The dam signature is attribution rather than load-bearing skill, and the dam story lives where the evidence supports it: the headroom analysis. The operational consequence turned out to be a feature. The BBMB dams stopped reporting centrally in July 2025, so the live 2026 nowcast must run reservoir-blind, and the ablation proves that configuration loses nothing. *Does it beat naive persistence?* On pooled average precision, no. A yesterday's-flooding baseline scores 0.31 against the model's 0.27, and we publish that. The model wins exactly where forecasting lives: ROC-AUC (0.946 vs 0.936) and the pre-crest window (4/5 vs 3/5 top-5 flags on Aug 14–24). A meteorology-only variant collapses (3/5, PR-AUC 0.11). **Antecedent flooding is the load-bearing signal**, which is why the 6-hourly live monitor that measures it and the forecaster are one system rather than two modules.

**Positioning vs Google Flood Hub.** Flood Hub forecasts river stages on ungauged-basin technology; it under-models dam-*regulated* rivers and does not output district crop risk. Sailaab is impact-native (it predicts flooded fraction, crops, ₹) and regulation-aware in its analytics through the dam-headroom quantification, and by ablation its detection skill does not depend on the now-dark reservoir feed. Complementary, not competing.

## 4. Validated three independent ways, with the failures kept

Quantitatively against **Copernicus GFM** (fresh-point confusion matrices). Independently against **Sentinel-2 optical truth points**, a different sensor with different physics that breaks any SAR-chain circularity: 237 photo-interpreted NDWI points confirm **81.7% of RF flood pixels** as standing water two weeks post-peak (pre-declared gate: at least 60%), and every pre-declared precision/recall ordering held. And **visually against ISRO NDEM map sheets** (approximate-extent comparison, stated as such; no pixel agreement claimed).

**The ground survey agrees.** When Punjab's Revenue Department published its Special Girdawari district crop-damage table (13 Sep 2025), our satellite ranking matched it at **Spearman ρ = 0.72** across all 20 districts (0.56 over the 16 named), with **5 of the top 6 districts identical**. Divergences concentrate in the Ghaggar basin, outside our SAR acquisition windows, and are documented. The ₹ value-at-risk estimate was rebuilt on the government's own DES district paddy yields (v2 = ₹523 crore, within 4% of the independent v1 estimate). Submergence *duration*, computed per pixel from daily satellite observations, shows 51,202 ha under water for 7 days or more (total paddy loss territory), which refines damage to a duration-weighted **₹351 crore**.

Every satellite step is gated by a **pre-declared checkpoint**: the expected numeric band goes into the verification log *before* the run, then the actual, then PASS or FAIL. The log ships in the repo with the failures in it. The NRSC Sangrur-2023 anchor comparison **fails** on its exact date because no Sentinel-1 pass existed that day (the same event registers at full strength in adjacent windows: Sangrur 33,771 ha), and the naive fold metrics are flagged as strata artifacts. Independent confirmations: IMD data shows Aug 20 to Sep 5 2025 rainfall at **+9.7σ, rank 1 of 11 years** in both the Punjab and upstream boxes; reservoir records confirm Pong over its brim (1,393 ft, Aug 26) and Ranjit Sagar's 1.73-lakh-cusec release (Aug 27). We also documented that the three BBMB dams stopped reporting to the central CWC feed on **11 July 2025**, weeks before the flood. That is a data-transparency finding in itself.

## 5. Running right now

The public app (bakathefish.github.io/Flood) is interactive: an every-district map with three switchable layers (2025 flood extent, decade flood frequency, 2025 forecast risk), click-through per-district panels (flooded hectares, crop loss, ₹ value-at-risk, recurrence, hindcast probability), a before/after satellite swipe of the flood, and the live monitor feed. Every figure loads from version-controlled CSVs anyone can audit.

The live monitor is not a plan. It executed during this build: on a GitHub CI runner with **zero secrets and zero accounts**, it detected the most recent Sentinel-1 pass over Punjab (20 July 2026), computed district flood areas (a quiet 2.4 km² day, reported as such), and committed the state. It now does this automatically every six hours, generating alerts in ਪੰਜਾਬੀ, हिन्दी and English whenever any district crosses the alert floor. The landing page reads this feed live.

## 6. Impact, users, SDGs

- **SDMA / district EOCs:** recurrence zones plus live district km² for pre-positioning and evacuation priority.
- **Revenue Dept / girdawari:** flood-extent ∩ cropland per village-circle turns weeks of manual crop-loss survey into a verification exercise (the ₹523-crore at-risk quantification took hours, not weeks).
- **Insurers (PMFBY) and banks:** independent, reproducible loss extents.
- **Farmers and the public:** vernacular alerts, and every map open.
- **Worked example (one click in the app):** Sultanpur Lodhi tehsil, Kapurthala. Its district was flagged #1 by the model in the Aug 14–24 window; 4,733 ha flooded (4,028 ha cropland); it has flooded in 5 of the last 11 monsoons. Its girdawari verification list and a ਪੰਜਾਬੀ alert are one click away. That is the relief workflow, demonstrated on real 2025 data. Outreach to PSDMA and the worst-hit District Collectors is drafted for dispatch with this submission.
- **SDGs:** 2 (crop-loss quantification), 11 (resilient communities), 13 (climate adaptation).

## 7. Originality

(1) First open ML-ready flood mapping of Indian-Punjab 2025 (the published RF precedent covered the Pakistani side). (2) **Punjab's first public flood-frequency atlas.** (3) A self-labeling SAR-to-ML loop that manufactures its own decade of training data, with the paddy-transplant contamination discovery published. (4) A district forecaster with a demonstrated 10-day lead on the 2025 disaster, corroborated by the girdawari and **stress-tested by ablation, with both failed expectations published**. (5) An end-to-end account-free architecture: reproducibility as a design principle rather than a promise. (6) The quantified forecast gap: Punjab is absent from CWC's own flood-forecast station network, and Sailaab is the district-level layer that gap leaves open.

## 8. Roadmap

Multi-state scale-out (the pipeline is a bbox plus a district file), village-circle girdawari integration with the Revenue Dept, Bhashini voice alerts, deeper models (a U-Net benchmark on Sen1Floods11 chips) as data grows, and official partnerships. Outreach to PSDMA and the worst-hit District Collectors is prepared for dispatch with this submission. An EOS-04 (ISRO SAR) pixel-level cross-validation is pre-declared in the repo with its acceptance bands committed before any scene was downloaded.

## 9. Open source

MIT (code) + CC-BY-4.0 (maps/tables). 459 automated tests. Method paper, data-source registry (every dataset: URL, license, access date), and the full verification log: **github.com/bakathefish/Flood** · live: **bakathefish.github.io/Flood**

*11 monsoons · 467 flood days · 105,183 ha mapped · 91 tehsils scored · ρ=0.72 vs govt girdawari · 3 languages · 0 CWC forecast stations in Punjab · 0 logins required.*
