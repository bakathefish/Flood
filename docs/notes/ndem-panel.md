# The founding-argument panel — `atlas/ndem_vs_sailaab.png`

One image that states the premise: **ISRO's locked, static PDF flood sheet vs the
SAILAAB open, interactive flood map — the same Punjab-2025 flood.** Regenerated
deterministically by `pipeline/make_ndem_panel.py` (same inputs → byte-stable
PNG; no network, no randomness).

```
python -m pip install pypdfium2          # pure wheel, no poppler
python pipeline/make_ndem_panel.py       # -> atlas/ndem_vs_sailaab.png (2200x1127, ~1.0 MB)
```

- **LEFT** — the NDEM rapid-mapping sheet (a locked A0 PDF, "For Official Use"),
  cropped to the framed map body, labeled `ISRO NDEM · 19 Aug 2025 · static PDF`.
- **RIGHT** — the SAILAAB `rf_flood_2025.tif` mask over the *same approximate
  extent*, dark cartography (ink ground, cyan inundation, hairline district
  borders + labels), labeled `SAILAAB · same flood · open, interactive,
  reproducible`.
- **Footer** — `Same event, two access models. NDEM sheets validated our extent
  visually; full georeferenced comparison on the roadmap.`

## Honesty framing (read this first)

This is a **visual-comparison panel, not a georeferenced overlay** — the sanctioned
fallback in `punjab-flood-atlas-PLAN.md` §1.3 ("fallback: same-extent side-by-side
visual panel"). The NDEM product is a raster PDF with **no machine-readable
projection**, so the two halves are aligned **by district shape, not by
coordinates**. We make **no claim of pixel agreement**; the caption on the image
says "approximate extent match" explicitly. What the panel *does* show honestly:
both ISRO and SAILAAB independently map the **same Beas-doab + Sutlej inundation
signature** across Kapurthala / Tarn Taran in August 2025.

Visual-match verdict: **good-to-loose.** The Beas-doab flood blob and the
Sutlej/Harike stretch land at matching positions and the Tarn Taran / Kapurthala /
Jalandhar district shapes correspond; absolute registration is approximate
(estimated ~a few km, un-georeferenced), hence the honest caption rather than an
accuracy number.

## Source credit (government map product)

The left panel is a **Government-of-India map product** reproduced **downscaled,
for comparison / criticism, with full credit**. The credit is printed on the image
and repeated here:

> **Map excerpt: NDEM / NRSC / ISRO, ndem.nrsc.gov.in**
> Citation on the sheet: "NRSC (2025) — Flood Inundated areas in Part of Punjab
> State (as on 19-08-2025), based on the analysis of Resourcesat-2A AWiFS Satellite
> Image of 19-08-2025 (11:00 Hrs. IST). Map no: 2025/FL/PB/2/19082025, NRSC/ISRO."

## Which sheet, and why

Six NDEM PDFs were downloaded to `data/ndem/` (uncommitted; see
`docs/notes/validation-recon.md`). All six map sheets were rendered and inspected:

| Product | Date / kind | Extent | Verdict for the panel |
|---|---|---|---|
| `pbflood50dsc16082025_1100hrs_map` | 16 Aug, Landsat-8 | Beas strip, Gurdaspur→Kapurthala | narrow Beas strip; less doab drama |
| **`pbflood50dsc19082025_1100hrs_map` (p0)** | **19 Aug, Resourcesat-2A** | **Kapurthala & Tarn Taran** | **CHOSEN** — the canonical Kapurthala-doab sheet; matches where our mask is strongest |
| `…19082025…` (p1) | 19 Aug | + Hoshiarpur, Beas ribbon | good, but p0 matches the plan's "Kapurthala/Tarn Taran" verbatim |
| `pbflood50dsc1608_05092025_map` | cumulative 16 Aug–5 Sep | statewide | strong too, but statewide (less focused on our strong belt) |
| `pbflood50dsc1608_17092025_map` | cumulative 16 Aug–17 Sep | statewide | statewide, densest flood |
| `pbflood50dsc12072023_0600hrs_map` | 12 Jul **2023** | Sutlej/Ghaggar | wrong event (2023) |

**Chosen: `pbflood50dsc19082025_1100hrs_map.pdf`, page 0** — titled *"Flood
Inundation Areas in Parts of Kapurthala and Tarn Taran Districts, Punjab State"*.
It is the single-acquisition (19 Aug 2025) sheet over exactly the Kapurthala /
Beas–Sutlej belt where the SAILAAB masks (`rf_flood_2025.tif` and the 60 m
`local_tierA_kapurthala_tierA_floodmask.tif`) carry the strongest signal, and it
matches the video plan's "19 Aug 2025 · Kapurthala/Tarn Taran" beat verbatim. The
two cumulative statewide sheets are the better *quantitative* ground-truth (they
are the primary validation reference in `validation-recon.md`); this sheet is the
better *rhetorical* one — a tight, dramatic, single-date locked PDF.

## Method + exact crop coordinates

1. **Render** page 0 of the chosen PDF at **150 dpi** with `pypdfium2`
   (`scale = 150/72`). Page renders to **7022 × 4967 px**.
2. **Crop to the map body.** The framed map is bounded by a black neat-line found
   by a dark-run scan of the page (columns/rows that are >40 % dark): verticals at
   x ≈ 314 / 5772 px, horizontals at y ≈ 561 / 4229 px. The crop is taken **just
   inside** those lines, stored as page fractions so it survives a re-render:

   ```
   NDEM_CROP_FRAC = (left, top, right, bottom)
                  = (0.0456, 0.1141, 0.8213, 0.8504)
   → crop box @ 150 dpi = (320, 567, 5767, 4224) px   (5447 × 3657, aspect 1.489)
   ```

   This trims the title bar (top), the right-hand legend + "MAP ID / About the
   Event" text column, and the scale bar + India/Punjab locator insets (bottom).
3. **Right panel.** Read `rf_flood_2025.tif` (EPSG:32643) over the lon/lat window
   **lon [74.40, 75.64] × lat [30.78, 31.50]** (the Beas–Sutlej doab), expanded to
   the NDEM crop's 1.489 aspect so the halves match; overlay Punjab district
   polygons (`data/punjab_districts.geojson`, datameet/ODbL) reprojected to UTM 43N
   as hairlines + a few district labels. Ink ground `#0b0f14`, cyan flood.
4. **Compose** at 2200 px wide (matplotlib, dpi 100): title block, two panels with
   a centre divider, per-panel labels, the source credit, and the honest footer.

## Inputs (how to fetch)

All inputs are repo-relative; the two large ones are **gitignored** (government map
products and rasters stay uncommitted):

- `data/ndem/pbflood50dsc19082025_1100hrs_map.pdf` — from
  `https://ndem.nrsc.gov.in/documents/Disaster_Document/2025/PB/pbflood50dsc19082025_1100hrs/pbflood50dsc19082025_1100hrs_map.pdf`
  (needs a browser `User-Agent`; see `validation-recon.md` for the recipe).
- `data/rasters/rf_flood_2025.tif` — the statewide RF flood mask (built by the RF
  pipeline; see `docs/notes/rf-train.md`).
- `data/punjab_districts.geojson` — committed.

Only `atlas/ndem_vs_sailaab.png`, `pipeline/make_ndem_panel.py` and this note are
committed.
