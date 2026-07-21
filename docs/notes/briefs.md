# District flood briefs — the print-ready "pin it to the wall" artifact

One A4 portrait PDF per Punjab district (20 total): the single sheet a District
Collector's office would actually print and pin up. Light paper ground, ink
text, cyan (water) and amber (risk) accents. Every number on the page is read
straight from the committed CSVs, and the whole set regenerates deterministically
from the repo with `matplotlib` alone.

## Files produced

| File | What |
|------|------|
| `pipeline/make_district_briefs.py` | the generator (pure `matplotlib` + `numpy`; reuses `sailaab.districts.canonical_name`) |
| `briefs/<District>.pdf` × 20 | one print-ready A4 brief per district |
| `atlas/briefs_preview.png` | 3 exemplars (Firozpur, Kapurthala, Gurdaspur) side-by-side, for the synopsis/video |

Sizes: every PDF is 77–141 KB (budget < 400 KB each), 2.03 MB for the set
(budget < 6 MB); the preview is ~250 KB (budget < 1.2 MB). All 20 PDFs are
committed.

## Inputs (all committed, repo-relative)

- `data/district_flood_stats_2025.csv` — Tier-A / RF / cropland flooded ha, fraction, crop value ₹
- `data/flood_frequency_districts_late_season.csv` — decade seasons >1% / >2%, worst season, mean annual ha
- `data/forecaster_2025_hindcast.csv` — per-window `p_event`; the brief shows the district's **peak** P and its statewide rank
- `data/pop_exposure_2025.csv` — population exposed, RF and GFM brackets
- `data/tehsil_flood_stats_2025.csv` + `data/tehsil_repeat_victims.csv` — the per-district tehsils table (2025 ha + decade ≥1% seasons), joined on `(district, tehsil)` and sorted worst-first
- `data/punjab_districts.geojson` + `data/punjab_tehsils.geojson` — mini-map polygons

## Layout (A4 portrait, 210 × 297 mm)

- **Header** — `SAILAAB` wordmark + "District Flood Brief", the tagline, the
  project URL (`bakathefish.github.io/Flood`; no QR library is available so the
  URL is printed), the district name in English, and the same name echoed in
  Gurmukhi. Both names auto-shrink to their half of the header so the longest
  ("Sahibzada Ajit Singh Nagar") never collides with its Gurmukhi.
- **Left column** — a mini-map: the district's tehsils shaded by their 2025
  RF-derived flooded fraction (white → cyan), the district outline in ink, and
  neighbouring districts greyed for context; the two worst-flooded tehsils are
  labelled. A slim legend gives the flood-fraction ramp.
- **Right column** — the stat block: 2025 RF + Tier-A flooded ha, cropland
  flooded ha, ₹ value-at-risk (crore), population exposed (RF & GFM); decade
  seasons >1% / >2%, worst-season share, mean annual ha, forecaster peak P +
  statewide rank; then the tehsils table (2025 ha, decade ≥1%-season badges).
- **Footer** — one-line method, "Open data: github.com/bakathefish/Flood ·
  validated vs Copernicus GFM & ISRO NDEM", and the generation date (2026-07-22).

## Design decisions

- **Why a per-tehsil choropleth, not a raster inset.** The plan named a raster
  inset (`data/rasters/rf_flood_2025.tif`), but that statewide RF mask is
  gitignored and stays local (see `.gitignore`, README "small CSVs only"). The
  brief instead renders the flood signal as a **vector choropleth of the
  committed per-tehsil RF flooded fraction** — fully reproducible from the repo,
  lighter (no raster to downsample), and per-tehsil rather than per-pixel. The
  cyan ramp uses a fixed statewide scale (`PowerNorm(γ=0.55, vmax=0.11`, just
  above the statewide max tehsil fraction of 0.107 at Sultanpur Lodhi) so colour
  intensity is directly comparable across all 20 briefs.
- **Name reconciliation.** The district geojson spells one district "Shahid
  Bhagat Singh Nagar" while every CSV uses "Nawanshahr"; the tehsil geojson and
  CSVs agree elsewhere. We route every name through the existing
  `sailaab.districts.canonical_name` crosswalk, so all five CSVs, both geojsons,
  and the filenames line up on 20 canonical names. A couple of districts also
  carry a well-known alternate name (Mohali, Sri Muktsar Sahib) shown as a small
  sub-label.
- **Season badges.** Decade ≥1%-season counts render as filled dots (● ×N,
  capped at 6), amber for ≥3 seasons, cyan for 1–2, an em-dash for 0 — a
  glanceable "repeat victim" signal in the tehsils table.
- **Palette.** Paper `#FBFAF7`, ink `#1B1E24`, water/flood cyan `#0E7C9B`, risk
  amber `#B26B12` — the print-oriented, light-background counterpart to the dark
  "living map" house style used by `pipeline/make_ndem_panel.py`.

## Gurmukhi (ਪੰਜਾਬੀ) rendering

matplotlib has **no complex-text-layout engine** (no HarfBuzz/libraqm in this
environment — checked: `PIL.features.check("raqm")` is `False`, no `uharfbuzz`),
so Indic scripts are laid out in logical, not visual, order. For these 20 names
the one systematic breaker is the pre-base short-i matra **ਿ (U+0A3F)**, which
must display *before* its consonant; left as-is it would draw on the wrong side
(e.g. Firozpur would be mis-ordered). `_shape_gurmukhi` reorders each ਿ before
its base consonant (stepping over an optional nukta **਼ U+0A3C**), which is
deterministic and makes **all 20 names read correctly**. Rendering uses the
Windows **Nirmala UI** font (`C:\Windows\Fonts\Nirmala.ttc`); the matplotlib PDF
backend embeds each glyph as a **Type-3 vector outline**, so the PDFs are
self-contained and print identically on machines without the font installed
(verified by rendering the output PDF back with `pypdfium2`).

**Known cosmetic limitation.** Two names carry a halant subjoined conjunct
(**੍ U+0A4D**): ਅੰਮ੍ਰਿਤਸਰ (Amritsar, ਮ੍ਰ) and ਫ਼ਤਹਿਗੜ੍ਹ (Fatehgarh Sahib, ੜ੍ਹ).
Without shaping these render **inline instead of stacked** — the halant is
visible and the word is still readable, but the subjoined form is not composed.
This affects 2 of 20 names and is cosmetic only. If Nirmala UI is ever
unavailable, the generator falls back to English-only and prints a note in the
header instead of mis-rendered Gurmukhi.

## Determinism

Same inputs → byte-identical PDFs (verified: two runs, matching SHA-256 for all
20). No network, no randomness; the PDF `CreationDate`/`ModDate` are pinned to a
fixed timestamp via `savefig(metadata=…)` so no run-time clock leaks into the
bytes. The auto-fit name sizing is pure text measurement, also deterministic.

## Regenerate

```bash
python pipeline/make_district_briefs.py                 # all 20 PDFs + the preview
python pipeline/make_district_briefs.py Firozpur Moga    # a subset (no preview)
```

Dependencies are already in `requirements.txt` (`matplotlib`, `numpy`; `pyproj`
is a transitive `rasterio` dep, used only for the geographic aspect of the
mini-map). The Nirmala UI font is optional — English-only fallback otherwise.

## Known limitations / honesty notes

- The flood layer is the **per-tehsil** RF fraction, not the per-pixel mask, so
  the map reads intensity by tehsil, not shoreline. The district outline and
  tehsil borders are the exact committed polygons (interior holes are honoured).
- Crop ₹ value-at-risk is an **order-of-magnitude** paddy-MSP figure (stated on
  every page), consistent with the whole project's honesty rules.
- Low/zero-flood districts (e.g. Fatehgarh Sahib) render an almost-white map and
  near-zero stats — that is the honest result, not a rendering fault.
