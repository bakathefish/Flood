# 2025 submergence-duration atlas — pre-declared method + checkpoints + run log

How long did each pixel stay **underwater** in the 2025 Punjab flood? Duration — not
peak extent — is what kills paddy: 3–7 days of complete submergence causes major yield
loss, >7 days is usually total (agronomy cited in §Crop-damage below). Nobody has
published a per-pixel submergence-duration map for Punjab; this is that product for the
2025 event.

Built from the same per-day Copernicus **GFM** observed-flood-extent masks as the decade
atlas (`docs/notes/gfm-decade.md`, `docs/notes/gfm-wms.md`): 2025 has 53 flood-active
days under `data/gfm/2025/gfm_punjab_<YYYYMMDD>.tif`, each a binary 0/1 uint8 mask on the
~100 m EPSG:3857 grid (3451 × 3991 px). Reference (permanent) water is
`data/gfm/gfm_punjab_refwater.tif` on the same grid.

Pure logic: `sailaab/duration.py` (censored-duration estimators, class binning) —
unit-tested in `tests/test_duration.py`. IO / raster / products:
`pipeline/duration_2025.py`.

## The event clock — Aug 15, not Jun 15 (paddy exclusion)

Punjab transplants rice into **deliberately inundated** fields ~Jun 15 – mid-Jul; S1/GFM
sees that agronomic water as flood, and the decade run quantified a ~20× collapse in
statewide flooded-ha once transplanting ends (`docs/notes/gfm-decade.md`: Jun-25 window
172,684 ha → Jul-25 8,997 ha). This is the **2025 event** product, so the clock starts at
**Aug 15** (day 0) and runs to **Sep 30** (day 46). Every observation dated before Aug 15
is dropped; a pixel wet only in the Jun/Jul paddy passes gets duration 0 by construction.

Event-window observation days actually on disk (24 of them; day-number = days since Aug 15):

```
Aug 15(0) 16(1) 18(3) 20(5) 22(7) 23(8) 27(12) 28(13) 30(15)
Sep 01(17) 03(19) 04(20) 08(24) 09(25) 11(27) 13(29) 15(31) 16(32)
    20(36) 21(37) 23(39) 25(41) 27(43) 28(44)
```

Consecutive gaps run 1–4 days; the **maximum gap is 4 days**. This sets the bridge cap
below.

## The censoring problem, stated honestly

S1 revisit means duration is **interval-censored**: we observe wet/dry only on the 24 pass
days, never continuously. Worse, a `0` in a daily mask conflates *observed-dry* with
*not-imaged*: GFM only paints pixels an S1 swath actually saw, and swath footprints cover
a fraction of the bbox on any given day (`docs/notes/gfm-wms.md`: Aug-30 footprint = 42 %
of bbox). Per-pixel S1 footprint rasters were **not retained** for the archive, so we
cannot separate the two kinds of `0`. We therefore pre-declare **two bracketing
estimators** and never pretend to a single true duration.

Let a pixel's event-window observations be sorted days `t_0 < t_1 < … < t_{k-1}` with wet
flags `b_i ∈ {0,1}` (a flag is forced 0 wherever reference water is set — permanent water
is subtracted *before* estimation, so it never contributes duration). Gaps `g_i =
t_{i+1} − t_i`.

### (a) `days_observed_wet` — LOWER bound (the committed raster)

The honest wet-bridge estimator. Count a day as underwater only when it is **either an
observed-wet pass, or sandwiched between two observed-wet passes no more than `G` days
apart** (`G = 4`, the max real gap, justified above — we never bridge farther than the
revisit that actually re-confirms wetness):

```
days_observed_wet = Σ_i b_i  +  Σ_{i : g_i ≤ G}  (b_i · b_{i+1}) · (g_i − 1)
```

Equivalently: sum, over each maximal run of consecutive wet passes (gaps ≤ G), of
`(run_last_day − run_first_day + 1)`. Each wet pass contributes 1 day; each bridgeable
wet→wet gap contributes its `g_i − 1` in-between (unobserved) days — the "implied gap
days". A **dry** pass or a gap > G **breaks** the run, so intermittent or unconfirmed
wetness is *not* credited. This is a genuine lower bound on true submergence duration and
is what we publish as `data/rasters/duration_2025.tif` (uint8 days).

### (b) `span_duration` — UPPER bound (reported bracket)

The maximal interpretation: everything between the first and last wet pass counts as
underwater, bridging across dry/unconfirmed passes too:

```
span_duration = (last wet day − first wet day + 1)   if any wet, else 0
```

By construction **0 ≤ days_observed_wet ≤ span_duration** pixelwise (every bridged day
lies inside `[first_wet, last_wet]`; span fills the interior dry-pass gaps that the lower
bound leaves empty). The gap between the two is a direct read-out of censoring /
intermittency. Both are written (`duration_2025.tif`, `duration_span_2025.tif`, both
gitignored); products and headline numbers use the lower bound unless stated.

### Duration classes (atlas legend + CSV bins)

`edges = (1, 3, 7, 14)` → class 0 = never (0 d), **1 = 1–2 d, 2 = 3–6 d, 3 = 7–13 d,
4 = 14+ d**. The 3–6 / 7–13 split is the agronomic major-vs-total paddy-loss boundary.

## Products (committed unless noted)

- `atlas/duration_2025.png` — dark house-style map (site `--ink #0a1014` surface), single-hue
  cyan sequential ramp reused from the site's `now`/`flood` layers
  (`['#155a5c','#1f8a84','#35b5a9','#63e6d5']` for classes 1–4), legend in the four
  day-classes, < 1.5 MB.
- `data/duration_districts_2025.csv`, `data/duration_tehsils_2025.csv` — per unit: hectares
  in each duration class + mean duration of the flooded area (days).
- `data/duration_crop_damage_2025.csv` — cropland (ESA WorldCover 2021 class 40,
  `data/rasters/rf_cropland.tif`, warped onto the GFM grid) ha per duration class per
  district, plus a damage-weighted paddy-loss estimate (below).
- `data/rasters/duration_2025.tif`, `duration_span_2025.tif` — lower/upper rasters (gitignored).

## Crop-damage weighting (conservative, labelled ESTIMATE)

Non-Sub1 rice — Punjab's paddy — tolerates only brief complete submergence. Established
agronomy (IRRI submergence work: Setter & Laureles 1996; Sarkar et al. 2006; Ismail et al.
2013, *Ann. Bot.*): a few days of complete submergence during vegetative growth already
cuts yield, and **>7–10 days is typically lethal**. We map the four duration classes onto
conservative fractional yield-loss bands, clearly an estimate:

```
1–2 d → 0.10    3–6 d → 0.35    7–13 d → 0.70    14+ d → 1.00
```

Damage-weighted paddy loss = Σ (cropland ha in class × loss fraction × value/ha), reusing
the repo paddy valuation `sailaab.stats.crop_value_at_risk` (6.5 t/ha × ₹23,200/t =
₹150,800/ha). Reported next to the naive "all flooded cropland × full value" figure to
show the duration weighting.

## PRE-DECLARED checkpoints (written BEFORE the compute)

A checkpoint FAILS if the actual lands outside its band.

- **D1 — flood core is severe.** Late-Aug core zones along Ravi/Beas/Sutlej stay underwater
  ≥ 7 days. PASS iff `max(days_observed_wet) ≥ 14` days **and** area with
  `days_observed_wet ≥ 7 d` is **≥ 5,000 ha** statewide.

- **D2 — event clock isolates the flood.** First ingested observation = **2025-08-15**
  (paddy Jun/Jul dropped), and the event-window flooded footprint (any day, dur ≥ 1, minus
  ref water) is a plausible river-flood union **∈ [2,000, 3,500] km²** (cross-check: decade
  late-season ≥Jul-25 union was 3,306 km²; an Aug-15-onset union should be a touch smaller).

- **D3 — bracket + bounds sane.** `0 ≤ days_observed_wet ≤ span_duration` at **100 %** of
  pixels, and `max(days_observed_wet) ≤ 45` (window is 45 obs-spanned days, Aug 15→Sep 28).

- **D4 — corridor concentration, not statewide paddy.** The severe fraction
  `ha(≥7 d)/ha(≥1 d) ∈ [0.03, 0.60]` (a minority — long submergence is river-corridor, the
  paddy interior is excluded), and the **top-5 tehsils by mean flooded-duration** all lie in
  Sutlej / Ravi / Beas / Ghaggar districts (Firozpur, Fazilka, Kapurthala, Tarn Taran,
  Gurdaspur, Amritsar, Jalandhar, Sangrur, Patiala, Muktsar, Rupnagar).

- **D5 — crop damage plausible + duration-discounted.** Duration-weighted paddy damage is
  `> 0` and **strictly less** than the naive all-flooded-cropland value, with ratio
  `weighted/naive ∈ [0.10, 0.90]`.

## ACTUALS + verdicts (compute run 2026-07-22)

24 event-window observation days (2025-08-15 … 2025-09-28), gaps ∈ {1, 2, 4}, all ≤ G = 4.
Streamed rasters cross-checked pixel-for-pixel against `sailaab.duration` (6 random pixels).

Headline (lower bound = `days_observed_wet` unless noted):

| metric | value |
|---|---|
| flooded footprint (dur ≥ 1 d, − ref water) | 298,199 ha = **2,982.0 km²** |
| max duration | **25 d** (lower) / 45 d (upper span) |
| median duration of flooded area | 2 d (lower and upper) |
| area submerged ≥ 7 d (classes 3–4) | **51,202 ha** |
| severe fraction ha(≥7 d)/ha(≥1 d) | 0.172 |
| cropland flooded (≥ 1 d) | 85,455 ha |
| duration-weighted paddy damage | **₹350.9 crore** (fraction 0.272 of naive ₹1,288.7 cr) |

The most-persistent pixel brackets to **[25 d lower, 45 d upper]** — i.e. it was confirmed
wet-bridged on 25 of the 45 spanned days, the rest being unconfirmed (dry-or-unimaged)
passes. That gap is the censoring, shown honestly rather than hidden.

Median-of-flooded = 2 d because the union is dominated by thin 1–2-day fringe (Gurdaspur's
broad upstream-Ravi sheet, mean 1.9 d); the long-duration signal is concentrated, not
statewide — exactly the paddy-excluded river-corridor result intended.

Top-5 tehsils by mean flooded-duration (≥ 50 ha flooded): **Khadur Sahib** (Tarn Taran)
10.1 d, **Fazilka** (Firozpur) 8.2 d, **Patti** (Tarn Taran) 8.0 d, **Tarn Taran**
(Tarn Taran) 7.4 d, **Baba Bakala** (Amritsar) 7.1 d — the Harike confluence + Sutlej/Beas
belt. District leaders by severe (≥ 7 d) area: Firozpur 6,689 ha, Tarn Taran 4,053 ha,
Kapurthala 3,057 ha.

### Checkpoint verdicts

- **D1 — flood core severe: PASS.** max(days_observed_wet) = 25 d ≥ 14 ✓ and ha(≥ 7 d) =
  51,202 ha ≥ 5,000 ✓.
- **D2 — event clock isolates the flood: PASS.** First ingested obs = 2025-08-15 ✓ (Jun/Jul
  paddy dropped); event union 2,982.0 km² ∈ [2,000, 3,500] ✓ — a touch under the decade
  ≥Jul-25 union (3,306 km²) exactly as predicted for an Aug-15 onset.
- **D3 — bracket + bounds sane: PASS.** `days_observed_wet ≤ span_duration` at 100 % of
  pixels ✓; max(days_observed_wet) = 25 ≤ 45 ✓.
- **D4 — corridor concentration: PASS.** severe fraction 0.172 ∈ [0.03, 0.60] ✓; all top-5
  mean-duration tehsils lie in Tarn Taran / Firozpur / Amritsar (Ravi/Beas/Sutlej/Harike) ✓.
- **D5 — crop damage plausible + discounted: PASS.** weighted ₹350.9 cr < naive ₹1,288.7 cr,
  ratio 0.272 ∈ [0.10, 0.90] ✓, > 0 ✓.

All five pre-declared checkpoints PASS. Products committed: `atlas/duration_2025.png`,
`data/duration_districts_2025.csv`, `data/duration_tehsils_2025.csv`,
`data/duration_crop_damage_2025.csv`. Not committed (gitignored):
`data/rasters/duration_2025.tif`, `data/rasters/duration_span_2025.tif`.
