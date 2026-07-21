# Tier-C benchmark: U-Net on Sen1Floods11, inferred on Punjab

A **benchmark**, not a replacement. The honest deliverable is the 3-method
comparison table (threshold / RF / U-Net), whatever it shows. A small CPU U-Net
is trained on the Sen1Floods11 hand-labeled SAR chips, scored on their held-out
test split, then applied — across a deliberate domain gap — to the 90 m Punjab
2025 composites.

## What / why

* **Train data** Sen1Floods11 v1.1 `flood_events/HandLabeled` — 431 chips
  (252 train / 89 valid / 90 test), 512×512, Sentinel-1 VV+VH in dB, ~10 m.
  Labels `LabelHand`: `-1` = no-data (ignored), `0` = not-water, `1` = water.
  Public keyless GCS bucket `gs://sen1floods11` over plain HTTPS.
* **Label semantics** Sen1Floods11 labels **open water** (permanent + flood),
  not flood-change. Our RF and Tier-A masks are flood-*change* (they subtract
  permanent water). So the U-Net is expected to flag MORE water than RF/Tier-A
  by construction — rivers and canals included. This asymmetry is the point of
  the benchmark, not a bug.
* **Model** hand-rolled U-Net, 4 down / 4 up blocks, base 16 (~1.9 M params),
  in-channels VV+VH. Loss BCE+Dice, Adam 1e-3, batch 8, 256-px random crops of
  the 512 chips, early-stop on valid IoU (patience per-run below). Everything
  seeded (42). CPU-only (no GPU on this machine).
* **Normalisation** per-channel: clip dB to [-35, +5], then standardise with
  mean/std computed once over the training chips (finite pixels). The SAME
  clip+stats are stored in the checkpoint and re-applied to Punjab, so the only
  thing that changes between domains is the imagery itself.
* **Eval** IoU / F1 on the water class over the Sen1Floods11 TEST split, masking
  `-1` no-data pixels (their convention).
* **Punjab inference** tile `data/rasters/rf_vv_flood.tif` + `rf_vh_flood.tif`
  (3338×3800 @ 90 m, EPSG:32643) into overlapping 256-px tiles, run the net,
  average overlaps, threshold at 0.5, restrict to the Punjab district mask (same
  region RF reports on). Compare statewide flooded ha + per-pixel agreement
  against RF, Tier-A and GFM.

## Domain gap (declared up front)

The chips are **10 m single-scene** flood snapshots; Punjab is a **90 m
multi-scene median composite**. Nine-fold coarser resolution + median compositing
(which suppresses transient water and smooths speckle) + a different processor
(GEE GRD vs Planetary-Computer RTC γ0) is a real covariate shift. The dB
statistics differ: Punjab VV median ≈ −7.7 dB / VH ≈ −14.2 dB, brighter and
tighter than the flood-centred chips. Degradation on Punjab is plausible and, if
it happens, is itself a legitimate benchmark finding.

## Pre-declared expectations (written BEFORE training)

* **Sen1Floods11 test IoU 0.55–0.80** is the plausible band for a small,
  from-scratch CPU U-Net on 431 chips. The published Bonafilia et al. (2020)
  FCNN reaches ~0.78 IoU on hand-labeled water (fully-trained, GPU) — cited for
  context, **not** a parity requirement.
* **F1 roughly 0.70–0.89** (F1 ≥ IoU always).
* **Punjab** the U-Net should light up the major rivers/reservoirs (open water
  it was trained to find). Statewide "flooded" ha is expected to come out
  **higher** than RF/Tier-A (permanent water included) and its agreement with the
  flood-change references (RF, Tier-A) is expected to be modest. Closer to GFM
  (also inclusive) is plausible but not guaranteed. A degenerate output (all-on
  or all-off) would be reported as the finding, not hidden.

## Per-epoch log

_(appended live during training below)_

### Run 1 — initial config (pos_weight 5, no augmentation)

Model: base=16 depth=4 params=1,942,433; norm clip (-35.0, 5.0) mean=[-10.394, -17.198] std=[4.029, 4.549]; loss BCE(pos_weight=5.0)+Dice; Adam 0.001; batch 8; crop 256; seed 42.

| epoch | train_loss | valid_IoU | valid_F1 | valid_P | valid_R | sec |
|------:|-----------:|----------:|---------:|--------:|--------:|----:|
| 1 | 1.5623 | 0.5587 | 0.7169 | 0.735 | 0.700 | 68 |
| 2 | 1.4639 | 0.5068 | 0.6727 | 0.557 | 0.850 | 63 |
| 3 | 1.4092 | 0.5022 | 0.6686 | 0.540 | 0.877 | 72 |
| 4 | 1.3702 | 0.4000 | 0.5714 | 0.420 | 0.893 | 72 |

**Best epoch 1** (valid IoU 0.5587); epochs run 4; model 7.82 MB; runtime 313s.
**Sen1Floods11 TEST:** IoU **0.5911**, F1 **0.7430**, precision 0.763, recall 0.724 (micro-averaged over 90 chips, -1 masked).

Run-1 diagnosis: train loss kept falling while valid IoU fell — `pos_weight=5`
optimises a recall-heavy BCE, so precision collapsed (0.74 → 0.42) and early
stopping fired at epoch 4 with the epoch-1 weights as "best". A one-epoch model
is a weak benchmark entry, so a second run rebalances the loss (`pos_weight=2` —
Dice already handles class imbalance), adds seeded flip/rot90 augmentation, and
extends patience to 4. Both runs are reported; the better valid-IoU checkpoint
is the one carried to Punjab.

### Run 2 — rebalanced (pos_weight 2, flip/rot90 augmentation, patience 4)

Model: base=16 depth=4 params=1,942,433; norm clip (-35.0, 5.0) mean=[-10.394, -17.198] std=[4.029, 4.549]; loss BCE(pos_weight=2.0)+Dice; Adam 0.001; batch 8; crop 256; augment=True; patience 4; seed 42.

| epoch | train_loss | valid_IoU | valid_F1 | valid_P | valid_R | sec |
|------:|-----------:|----------:|---------:|--------:|--------:|----:|
| 1 | 1.4031 | 0.4576 | 0.6278 | 0.494 | 0.861 | 63 |
| 2 | 1.3141 | 0.4634 | 0.6334 | 0.503 | 0.854 | 62 |
| 3 | 1.2591 | 0.4821 | 0.6506 | 0.528 | 0.847 | 60 |
| 4 | 1.2134 | 0.5477 | 0.7077 | 0.639 | 0.793 | 69 |
| 5 | 1.1570 | 0.5567 | 0.7152 | 0.643 | 0.806 | 61 |
| 6 | 1.1166 | 0.5781 | 0.7327 | 0.707 | 0.760 | 59 |
| 7 | 1.0860 | 0.6002 | 0.7501 | 0.823 | 0.689 | 53 |
| 8 | 1.0541 | 0.5724 | 0.7281 | 0.657 | 0.816 | 53 |
| 9 | 1.0784 | 0.5975 | 0.7480 | 0.732 | 0.765 | 49 |
| 10 | 1.0503 | 0.5613 | 0.7190 | 0.859 | 0.618 | 55 |
| 11 | 1.0762 | 0.6128 | 0.7599 | 0.772 | 0.748 | 49 |
| 12 | 1.0159 | 0.4372 | 0.6084 | 0.825 | 0.482 | 49 |
| 13 | 0.9970 | 0.6050 | 0.7539 | 0.754 | 0.754 | 50 |
| 14 | 1.0286 | 0.5955 | 0.7464 | 0.780 | 0.715 | 46 |
| 15 | 0.9878 | 0.5859 | 0.7388 | 0.674 | 0.817 | 60 |

**Best epoch 11** (valid IoU 0.6128); epochs run 15; model 7.82 MB; runtime 868s.
**Sen1Floods11 TEST:** IoU **0.6346**, F1 **0.7765**, precision 0.780, recall 0.773 (micro-averaged over 90 chips, -1 masked).

Run 2 selected (valid IoU 0.6128 > run 1's 0.5587); its checkpoint is
`data/models/unet_sen1floods11.pt` (7.82 MB, seed 42, norm stats embedded).

## Actuals vs pre-declared expectations

| pre-declared | actual | verdict |
|---|---|---|
| test IoU 0.55–0.80 | **0.6346** | inside band; below the published ~0.78 FCNN (GPU, fully-trained) as anticipated for a small CPU net |
| test F1 0.70–0.89 | **0.7765** | inside band |
| Punjab: U-Net ha HIGHER than RF/Tier-A (open-water labels) | **36,063 ha — LOWER than RF's 52,223** | **wrong** — the 10 m→90 m domain gap dominated the label-semantics effect: dispersed field flooding is under-detected, so the net loses more to resolution than it gains from counting permanent water |
| Punjab output not degenerate | coherent river network (quicklook) | pass — traces the Beas/Sutlej system like the other methods; no all-on/all-off failure |

## Punjab benchmark table (in-district, 90 m grid; full CSV in `data/unet_benchmark.csv`)

| method | statewide ha | vs GFM P | vs GFM R | vs GFM IoU |
|---|---:|---:|---:|---:|
| threshold (Tier-A) | 33,938 | 0.781 | 0.308 | 0.283 |
| random forest | 52,223 | 0.616 | 0.374 | 0.303 |
| U-Net (Sen1Floods11) | 36,063 | 0.571 | 0.239 | 0.203 |
| GFM union (reference) | 86,071 | — | — | — |

Sample-point check (n=5000 fresh random in-Punjab points, seed 49):
U-Net P 0.630 / R 0.207; RF P 0.667 / R 0.415; Tier-A P 0.806 / R 0.354 —
same ordering as the full-raster numbers.

Cross-method overlap: U-Net vs RF IoU 0.419 (P 0.723) — the U-Net mostly finds
a high-confidence subset of RF's flood plus river channels; U-Net vs Tier-A IoU
0.344.

Data-integrity note: the on-disk `local_tierA_punjab_tierA_floodmask.tif` in
`data/rasters/` turned out to be a stale artifact of the earlier standalone
Tier-A run (only 3.2 kha inside districts, flood concentrated at the western
border columns). `pipeline/infer_unet.py` therefore recomputes Tier-A from the
same committed composites via the unit-tested `sailaab.sar_local` functions —
the recomputation reproduces `rf_grid.json`'s 105,183.4 ha (whole grid) and the
committed district-stats sum 33,938 ha exactly.

## Verdict (the honest benchmark result)

On the 90 m Punjab composites, the locally-trained RF stays the best AI method
(vs-GFM IoU 0.303), the zero-training threshold is a close second (0.283), and
the imported U-Net — despite being the strongest method on its native 10 m
domain (test IoU 0.63) — comes last (0.203). The domain gap, declared up front,
is the story: 9× coarser pixels plus median compositing erase the fine flood
texture the network was trained on, so it under-segments (recall 0.24 vs GFM)
while still tracing the major river system cleanly. Tier-C therefore validates
the pipeline's design choice — train on the target domain (RF) rather than
import a model across a resolution gap — and the 3-method table, not any single
winner, is the deliverable.

Wall clock: data acquisition ~7 min (862 files, 0 failures), run 1 313 s,
run 2 868 s, Punjab inference 11 s. torch 2.9.1+cpu is a user-level install
(`pip install torch --index-url https://download.pytorch.org/whl/cpu`) —
deliberately NOT added to `requirements.txt`.
