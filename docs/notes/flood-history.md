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

(Actuals + red-team outcome appended below in a later commit.)
