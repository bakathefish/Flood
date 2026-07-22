# Punjab floods in 70-year context — sparse-milestone record

**Status: PRE-DECLARED (frame and expected values written before the repo copy
of the data was cleaned or plotted; actuals appended below in a later commit).**

## What this is — and what it is not

A historical-context figure placing 2025 against the public record of Punjab
flood damage. **No continuous public annual series exists** on the OGD portal —
the record is a set of milestones from three resources of different vintages
and different metrics. The figure is therefore a sparse milestone timeline and
must look like one: no interpolation, no dense line, metric classes never
conflated (flooded area ≠ crop-damage area ≠ lives ≠ houses — distinct markers,
stated units).

## Sources (all keyless via OGD sample-key API, GODL licence; raw pulls in scratchpad)

| Resource | uuid | Punjab content |
|---|---|---|
| Max area affected by floods 1953–2010 | `c00fd02a-c30e-4953-bddb-a4cbacb78036` | worst single-year flooded area 2.79 Mha |
| Flood damage 2016–2018 (MoEFCC) | `f03e92a4-3e5d-4f0f-a30e-975593acb658` | 2016: 0.001 Mha / ₹1.14 cr; 2017: 0.006 Mha / ₹18.23 cr; 2018: 0.023 Mha |
| Hydromet damages 2018-19→2021-22 | `082dd5e0-75c2-4601-b82c-71d653318bf6` | lives 35/20/16/9; houses 229/2,618/837/8; crops (lakh ha) 0.52/1.51/1.23/– |

2025 enters as TWO clearly-labelled points, never merged: **105,183 ha** (our
SAR single-pass mapped extent) and **1.985 lakh ha** (official Special
Girdawari cumulative crop damage, as of 2025-09-13, `official_relief_2025.csv`).

## Pre-declared checkpoint

| Quantity | Expected |
|---|---|
| 1953–2010 Punjab max flooded area | 2.79 Mha |
| 2016–18 Punjab flooded area | ≤ 0.023 Mha every year (quiet baseline) |
| 2018-19→2021-22 lives lost | 35/20/16/9 |
| Consolidated CSV | one row per (period, metric, value, unit, source_uuid); units normalised to ha / INR-crore / count |

## Red-team rule (mandatory)

The 2.79 Mha figure: establish the year it refers to if the resource or
literature allows (1988 is the prior suspect, NOT an assumption). If it cannot
be dated from a citable source, the figure labels it *"worst year, 1953–2010
(year not published in source)"*. No invented year, no silent attribution.

## Framing rule

The contrast that matters: a placid 2016–21 baseline (≤0.15 lakh ha crops,
single-digit-to-low-double-digit lives) → 2025 at ~2 lakh ha girdawari damage
and 55 deaths. 2025 is the outlier the recurrence atlas said to prepare for —
the figure supports §1 of the synopsis, it does not replace the official
record.

---

## Actuals

Committed record: `data/punjab_flood_damage_history.csv` — 21 rows, one per
`(period, metric, value, unit, source_uuid)`. Units kept in their source form and
normalised in code (`sailaab.history`): `Mha`/`lakh_ha`/`ha` → ha, `crore_inr`
and `count` passthrough. Figure: `atlas/punjab_flood_history.png` (log-ha area
panel + linear lives panel); byte-stable across two driver runs
(md5 `de39867e439ea21eeab7ac9d2db2a333`). Unit/schema tests: 25/25 pass.

Checkpoint (pre-declared → actual):

| Quantity | Expected | Actual | Verdict |
|---|---|---|---|
| 1953–2010 Punjab max flooded area | 2.79 Mha | 2.79 Mha = 2,790,000 ha (loads, class `flooded_area`) | PASS |
| 2016–18 flooded area | ≤ 0.023 Mha every year | 0.001 / 0.006 / 0.023 Mha (max 0.023) | PASS |
| 2018-19→2021-22 lives lost | 35/20/16/9 | 35/20/16/9 (class `lives`) | PASS |
| Consolidated CSV | one row per (period, metric, value, unit, source_uuid); ha / crore-INR / count | schema holds; all units in `{ha, lakh_ha, Mha, crore_inr, count}`; no negatives | PASS |

2025 enters as **two separate points, never merged** — they are different metric
classes: SAR single-pass **105,183 ha** (`area_affected`, class `flooded_area`;
statewide Tier-A, `docs/VERIFICATION-LOG.md` 2026-07-21) and Special Girdawari
cumulative **198,524 ha** (`crop_damage_area`; sum of the 18 district rows in
`data/official_relief_2025.csv`, which round to the STATEWIDE reported 198,525 —
the 1-ha gap is rounding; both = 1.985 lakh ha). Lives 2025 = **55** (STATEWIDE
deaths, same file), the anchor for the lives contrast.

Metric classes are disjoint and never conflated: `flooded_area`,
`crop_damage_area`, `crop_damage_value` (crore INR), `lives`, `houses`.

Deviations from the frame, and why:
- **2021-22 crops = `NA`** in the source (resource 2c) → row omitted, no value
  invented. So `crop_damage_area` has 2018-19/2019-20/2020-21 + the 2025 anchor.
- **Houses** (229 / 2,618 / 837 / 8) are kept in the CSV for completeness but
  **not plotted**: the repo has no 2025 houses figure to anchor the contrast, and
  §1 rests on the area + lives story. Keeping them off-figure preserves the sparse
  look; the numbers remain in the record.
- The 2.79 Mha worst-year maximum is drawn as an **undated horizontal reference
  band**, above 2025 — not a dated point (see red-team below).

## Red-team: dating the 2.79 Mha

**Outcome: undatable from a citable source → labelled "year not published in
source". No year invented.**

- **Source has no year.** The OGD resource "State/UTs-wise Maximum Area Affected
  by Floods in any Year during 1953-2010" (uuid `c00fd02a-c30e-4953-bddb-a4cbacb78036`,
  Rajya Sabha, published 2022-12-25) carries only three fields — `sl__no_`,
  `state_ut`, `max__area_affected__million_ha_`. There is **no year column**; the
  table reports the maximum over the window without saying which year produced it
  (raw pull: scratchpad `datagovin/maxarea_punjab.json`). Accessed 2026-07-22.
- **1988 (prior suspect) cannot be pinned to 2.79 Mha.** 1988 is widely cited as
  Punjab's worst pre-2025 flood ("worst deluge since 1988"; *The Tribune*, "redux
  of 1988/1993"), but the 1988 Punjab floods record gives **no area-affected
  figure in hectares** — only 9,000 of 12,989 villages flooded, ~34 lakh people
  affected, 634 mm Bhakra-area rain. The inundation figure sometimes cited for
  1988 (~9,221 km² ≈ 0.92 Mha) is **far below** 2.79 Mha, which suggests the OGD
  "area affected" is a broader administrative measure than satellite inundation.
  No citable source ties the specific 2.79 Mha value to any year.
- **Decision (per pre-declared rule):** the figure labels the row *"Punjab worst
  flood year, 1953–2010: 2.79 Mha — year not published in source"* and places it
  as an undated reference, off the time axis.

Sources (accessed 2026-07-22):
- data.gov.in resource `c00fd02a-c30e-4953-bddb-a4cbacb78036` (raw JSON — no year field)
- https://en.wikipedia.org/wiki/1988_Punjab_floods (no area-affected figure)
- https://en.wikipedia.org/wiki/2025_Punjab,_India_floods ("worst since 1988")
- https://india.mongabay.com/2025/09/lives-homes-and-crops-lost-as-punjab-faces-the-worst-flood-in-decades/
- https://www.indiastat.com/punjab-state/data/meteorological-data/floods-cyclonic-storms-and-landslides (year-wise series behind paywall; no public year-wise max surfaced)
