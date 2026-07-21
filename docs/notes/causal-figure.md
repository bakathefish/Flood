# The causal figure — `atlas/causal_2025.png`

The single "why the flood happened" chart. Regenerated deterministically from
committed CSVs by `pipeline/make_causal_figure.py` (pure matplotlib; same input →
byte-identical PNG). Testable data transforms live in `sailaab/causal.py`
(`tests/test_causal.py`, 9 tests).

```
python pipeline/make_causal_figure.py      # -> atlas/causal_2025.png (2000x1400, ~380 KB)
python -m pytest tests/test_causal.py -q
```

## What it argues

One causal chain, stacked on a **shared Jun 1 → Sep 30 2025 time axis** so cause
sits directly above effect:

> extreme upstream rain → already-near-full reservoirs → forced releases → downstream inundation

- **Panel A (thin, top)** — daily area-mean rainfall for the upstream
  (Sutlej/Beas/Ravi) and Punjab-plains boxes in 2025, over the 2015–2024
  same-calendar-day **median** silhouette. The 26 Aug spike (≈10× normal) is the
  visual scream.
- **Panel B (main, bottom)** — the three BBMB dams as **percent of live capacity**
  (one axis for three very different capacities; 100 % = FRL = "brim-full /
  danger"). **Solid** = CWC daily API (to 11 Jul); **dashed + dots** =
  BBMB/press for the Aug–Sep window the API never reported. The reporting gap and
  the 26 Aug–6 Sep flood window are shaded across both panels.

## Design decisions

- **% of live capacity, not BCM or ft.** Bhakra 6.229 / Pong 6.157 / Ranjit Sagar
  2.344 BCM live capacity are not comparable in absolute units; normalizing puts
  all three on one 0–100 % axis where **100 % reads as FRL / brim-full**, and Pong
  poking above it reads as "over the top." Honours the dataviz "one axis" rule
  (no dual-axis). The daily API's own `pct_capacity` and the press %-full figures
  are the *same* quantity (verified: `storage / live_capacity × 100`; see
  `test_pct_of_live_capacity_matches_reported_pct`), so solid and dashed segments
  are directly comparable.
- **Solid vs dashed provenance.** The two CSVs are loaded and normalized
  separately so provenance is never guessed; solid stops at the 11 Jul coverage
  wall, dashed carries the press points, and the ~3-week gap is left unbridged and
  labelled ("reporting gap — BBMB ↛ CWC, 11 Jul") rather than interpolated.
- **Level-only flood points are annotated, not plotted.** Ranjit Sagar's two
  flood-window press rows are levels in metres with no storage, so it has no
  defensible % point after 11 Jul — its release is called out in text instead of
  inventing a %. Pong's post-18 Aug rows are levels showing it crossed FRL; rather
  than fabricate a precise %, a thin dashed arrow carries it "over the 1,390 ft
  brim" to just above the 100 % line.
- **Colour (validated, not eyeballed).** Ran the dataviz `validate_palette.js` on
  the white surface. Rain pair blue `#2a78d6` / orange `#eb6834` — worst CVD ΔE
  96.7. Dam trio Bhakra violet `#4a3aa7` / Pong red `#e34948` / Ranjit Sagar green
  `#008300` — worst all-pairs ΔE **13.3** (clears the ≥12 target), all ≥ 3:1 on
  white. The red/green pair is the tightest, so both carry **secondary encoding**
  (direct labels + solid/dashed) per the CVD-floor rule. Text wears ink tokens,
  never a series colour.
- **Sparse annotation.** Two consolidated callouts (reservoir state; forced
  releases), one peak callout, a handful of direct labels — never a number on
  every point.
- **Bilingual.** English title + Gurmukhi subtitle "ਸੈਲਾਬ 2025 — ਹੜ੍ਹ ਕਿਉਂ ਆਇਆ",
  rendered with **Nirmala UI** (verified rendering — real glyphs, not tofu). If
  that face is absent the script falls back to a transliterated English subtitle
  automatically.

## Every annotated number → its source

| On the figure | Value | Source row / reference |
|---|---|---|
| 26 Aug rainfall | 46 mm upstream · 58 mm Punjab | `rain_daily_boxes_2015_2025.csv` 2025-08-26 (`upstream_mm` 45.623, `punjab_mm` 58.252) |
| "≈10× the same-day median" | 45.6 / 4.5 ≈ 10.1× | computed by `same_day_climatology` over 2015–2024, 08-26 |
| Bhakra "93 %, 1,678 ft" | 93 % · 1,678.45 ft · 5.793 BCM | `reservoirs_2025_flood_supplement.csv` 2025-09-03 Bhakra (SANDRP) |
| Bhakra danger 1,680 ft | FRL 512.06 m = 1,680.0 ft | `docs/notes/reservoirs.md` (CWC `Full_reservoir_level`) |
| Pong "over its 1,390 ft brim, 1,393 ft (26 Aug)" | 1,393 ft > FRL 1,390 ft | `reservoirs_2025_flood_supplement.csv` 2025-08-26 Pong (SANDRP) |
| Ranjit Sagar release "1.73 lakh cusecs (27 Aug)" | 173,000 cusecs | `docs/notes/reservoirs.md` anchor table / route 5 (SANDRP) — outflow, no CSV flow column |
| Bhakra release "~85,000 cusecs (4 Sep)" | ~85,000 cusecs peak | `docs/notes/reservoirs.md` anchor table (SANDRP, 4–5 Sep) |
| Live capacities (for %) | 6.229 / 6.157 / 2.344 BCM | `docs/notes/reservoirs.md` (CWC `Live_capacity_FRL`) → `sailaab/causal.LIVE_CAPACITY_BCM` |
| "worst since 1988" | — | press (SANDRP / Down To Earth); stated as press-reported in the caption |

### Note on the Bhakra ~1,668.6 ft / 25 Aug target

The brief's "Bhakra ≈1,668.6 ft, 25 Aug" is **interpolated**, not a separately
quoted reading (`docs/notes/reservoirs.md` anchor table: 25 Aug falls between the
reported 1,666 ft on 19 Aug and 1,676.78 ft on 2 Sep). To keep every annotated
number tied to a real data row, the figure instead marks the **reported** season
approach-to-danger — **1,678 ft / 93 % on 3 Sep, ~1.5 ft below the 1,680 ft danger
level** — which is both directly sourced and a stronger "how close to the brim"
statement. Bhakra's own reported season high is 1,679 ft on 4 Sep (no % reported).

## Data-source line (as printed on the figure)

Rainfall: IMD 0.25° gridded, area-mean over the upstream & Punjab boxes.
Reservoirs: CWC via data.gov.in (daily, to 11 Jul 2025); Aug–Sep flood window BBMB
via press (SANDRP, The Tribune, Down To Earth, Babushahi). Solid = API · dashed =
BBMB/press-reported.
