# CWC flood-forecast station gap — Punjab's zero

**Status: PRE-DECLARED (frame and expected values written before the repo copy
of the data was cleaned or plotted; actuals appended below in a later commit).**

## The claim being established

In the Central Water Commission's own state-wise table of existing flood
forecasting stations ("as on Jan 2018", data.gov.in OGD resource
`0ff82e77-8f0c-479c-823e-246c0b38a2c6`, Government Open Data Licence – India),
**Punjab does not appear at all** — zero level-forecast stations, zero
inflow-forecast stations — while the national network counts 226 stations
(166 level + 60 inflow) across 22 states/UTs. Neighbouring Haryana has 1,
J&K 3, Rajasthan 3.

Why it matters for Sailaab: the state hit by the worst flood since 1988 sits
outside the national flood-forecast station network. Sailaab's district
forecaster and live monitor are not an incremental improvement on an existing
public layer for Punjab — for this state, at district granularity, that layer
does not otherwise exist in public.

## Pre-declared checkpoint

| Quantity | Expected |
|---|---|
| National total stations | 226 = 166 level + 60 inflow |
| States/UTs listed | 22 |
| Punjab rows | 0 (absent from the table) |
| Haryana total | 1 |

## Vintage honesty rule (non-negotiable, goes on the figure caption)

The table is **"as on Jan 2018"** — the newest state-wise table published on
the OGD portal at sweep time (2026-07-22). CWC's network has grown since; any
claim wording MUST be anchored to the table's own vintage, and the currency
red-team below decides which of the two pre-worded claims ships:

- **(W1) if no Punjab CWC FF station is found operating today:** "Punjab has no
  CWC flood-forecasting station — absent from the last published state-wise
  table (Jan 2018) and from CWC's current public station lists."
- **(W2) if Punjab stations exist today:** "As recently as the last published
  state-wise table (Jan 2018), Punjab had zero CWC flood-forecasting stations;
  N have appeared since [cite] — none of which existed as district-level flood
  risk products during the 2025 event."

No wording stronger than the evidence. The red-team (ffs.india-water.gov.in,
CWC annual reports 2023–25, credible news) is mandatory before the synopsis
line is written.

---

(Actuals + red-team outcome appended below in a later commit.)

## Actuals

Committed 2026-07-22. Source: `data/cwc_ff_stations_2018.csv` (23 rows = 22
states/UTs + one aggregate `Total` row), cleaned verbatim from data.gov.in OGD
resource `0ff82e77-8f0c-479c-823e-246c0b38a2c6` (catalog
`534fd34f-30ed-4973-aaaa-b652e49b0d3b`), *"State-wise Existing Flood Forecasting
Stations of the Central Water Commission (CWC) As on January 2018"*, from the
Ministry of Water Resources, River Development and Ganga Rejuvenation (via Rajya
Sabha), published on OGD 2019-08-13, Government Open Data Licence – India. The
resource carries **counts only** — no station names, rivers, or coordinates.

Pure logic in `sailaab/cwc.py`; `tests/test_cwc.py` = **16 tests, all pass**
(full suite green). `load_stations` validates the schema, enforces
`level + inflow == total` on every state row, and cross-checks the table's own
`Total` row (166/60/226) against the summed state rows before dropping it — so
the national figure is the table's arithmetic, verified, not an assumption.

Every pre-declared checkpoint value was met:

| Quantity | Expected | Actual |
|---|---|---|
| National total stations | 226 = 166 level + 60 inflow | **226 = 166 + 60** ✓ |
| States/UTs listed | 22 | **22** ✓ |
| Punjab rows | 0 (absent from the table) | **0** — absent; `station_count(df,"Punjab")→0` by absence ✓ |
| Haryana total | 1 | **1** (0 level + 1 inflow) ✓ |

Neighbour anchors confirmed as pre-declared: Jammu & Kashmir 3, Rajasthan 3
(3 inflow). Ranking head: Uttar Pradesh 40, Bihar 34, Assam 29.

Figure: `atlas/cwc_station_gap.png` (driver `pipeline/make_cwc_gap.py`) —
horizontal stacked (level + inflow) ranking of the 22 listed states with **Punjab
pinned at 0** at the foot and annotated; the caption carries the *"as on Jan
2018"* vintage caveat verbatim. The driver is offline and byte-deterministic
(two consecutive runs produce an identical SHA-256).

## Red-team: current status — verdict **W1**

**Selected wording (W1):** *"Punjab has no CWC flood-forecasting station — absent
from the last published state-wise table (Jan 2018) and from CWC's current public
station lists."* W1 is chosen over the softer W2 because no operating CWC
flood-forecasting station in Punjab was found in any source; the only Punjab site
CWC is ever recorded as having added (Bamiyal, on the Ravi) is defunct.

Evidence chain (all URLs accessed 2026-07-22):

1. **The 2018 OGD table itself** — Punjab is absent from all 22 listed
   states/UTs (this component).
   `https://www.data.gov.in/resource/state-wise-existing-flood-forecasting-stations-central-water-commission-cwc-january-2018`
2. **SANDRP, *Overview of CWC Flood Forecasting Sites 2019: North India*** —
   "CWC has added one site in Punjab however the site is defunct." and, in
   summary, "CWC has no sites in Punjab (only one added this year is inactive)
   and Chandigarh." On the basins: "Even in Sutlej, Ravi and Beas basins, CWC has
   no flood forecasting sites … in Ravi Basin, CWC does not have a single
   monitoring site." (The single defunct site is Bamiyal on the Ravi.)
   `https://sandrp.in/2019/09/25/overview-of-cwc-flood-forecasting-sites-2019-north-india/`
3. **SANDRP, on the Aug-2023 Punjab floods** (the closest prior comparable
   event) — direct quote: "the Central Water Commission, India's only agency
   involved in flood forecasting, does not monitor or forecast the floods due to
   Bhakra and Pong dams", with no public CWC flood-level record for the Ghaggar,
   Sutlej, Beas or Ravi in Punjab.
   `https://sandrp.in/2023/08/21/no-dispute-about-role-of-pong-and-bhakra-dams-in-punjab-aug-2023-floods/`
4. **CWC's current network (2024)** — CWC issues flood forecasts at ~340
   stations (≈200 level + ≈140 inflow) across ~23 states/UTs and NCT of Delhi;
   the state list does **not** include Punjab or Chandigarh (CWC flood-forecasting
   pages / CWC Annual Report 2023-24; corroborated by the SANDRP North-India
   overviews above).
   `https://cwc.gov.in/en/flood-forecasting-hydrological-observation` ·
   `https://cwc.gov.in/sites/default/files/approved-annual-report-cwc-2023-24.pdf`
5. **2025 event** — no CWC district-level flood forecast for Punjab was found;
   the summary account of the 2025 Punjab floods records dam releases (Bhakra,
   Pong, Ranjit Sagar) and relief operations but makes **no mention of any CWC
   flood-forecasting station or forecast for Punjab**. Reported as absence of
   evidence, not evidence of absence.
   `https://en.wikipedia.org/wiki/2025_Punjab,_India_floods`

**Honesty caveats.** (a) The figure's own data is vintage *Jan 2018*; the
"still absent today" clause rests on CWC's current network description plus
secondary reporting (SANDRP), because CWC has not published a newer machine-
readable state-wise FF-station table on OGD. (b) The 340-station split
(≈200 level / ≈140 inflow) is CWC's current published network size gathered from
CWC/SANDRP sources via web research, not from a single downloaded table; the
hard, primary figure this component ships is the 2018 table's 226 (166 + 60). (c)
The one Punjab site ever recorded (Bamiyal, Ravi) was a *monitoring* attempt and
is defunct — so "zero flood-**forecasting** stations" is precise, and W1's "from
the last published state-wise table (Jan 2018)" is anchored to the exact vintage.
