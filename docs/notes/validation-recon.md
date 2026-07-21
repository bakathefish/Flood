# Validation data recon + festival re-verification

Recon date: 2026-07-21. Scope: independent flood-outline sources to validate the sailaab Punjab-2025
maps, plus a fresh re-check of the India AI Impact Festival submission facts. Keyless fetches only
(`curl` + browser UA; `r.jina.ai` for JS-heavy pages). Downloaded map/vector artifacts live under
`data/` and are **not** committed (government map products stay uncommitted; `data/gfm/` is gitignored).

---

## 1. NDEM / NRSC-ISRO flood products (ISRO Decision Support Centre)

**Host behaviour.** `https://ndem.nrsc.gov.in` serves plain `curl` a blanket `403`; a browser
`User-Agent` is required (root then returns `200`). Directory listing is **disabled**, which gives a
clean existence oracle on the `documents/Disaster_Document/<YEAR>/<STATE>/…` tree:

- `403` = path **exists** (listing forbidden) — e.g. `…/2025/PB/` and each product folder.
- `404` = path **absent** — confirmed with control probes (`…/2099/PB/`, fake product names).

**Punjab (`PB`) flood folders that exist (403):** `2017`, `2019`, `2023`, `2025`.
Absent (404): 2018, 2020, 2021, 2022, 2024. ("PB" = Punjab; "dsc" in the product name = NRSC
**Decision Support Centre**, Hyderabad — not orbit direction.)

**Product-folder naming.** Two generations, both under `…/<YEAR>/PB/<folder>/`:
- Per-acquisition: `pbflood50dsc<DDMMYYYY>_<HHMM>hrs`
- Cumulative: `pbflood50dsc1608_<DDMMYYYY>` ("1608" = event start 16 Aug; second date = "as-of")

**Files inside each folder** (folder itself is 403; files are directly fetchable once the name is
known): `<folder>_map.pdf` and `<folder>_report.pdf`. **All products are single-page A0/A1 PDF map
sheets + a short PDF report — no open shapefile/GeoTIFF/KML is exposed at these paths** (vector/raster
layers live only inside the NDEM web-GIS viewer, not as file downloads here). Folder listing is walled,
so filenames were recovered via search-engine index + pattern probing, not by listing.

### Inventory of NDEM Punjab flood products found

| Year | Product folder | Event / date | `_map.pdf` | `_report.pdf` |
|---|---|---|---|---|
| 2025 | `pbflood50dsc16082025_1100hrs` | acquisition 16 Aug 2025 11:00 | 200 (8.71 MB) | 200 |
| 2025 | `pbflood50dsc19082025_1100hrs` | acquisition 19 Aug 2025 11:00 (Kapurthala & Tarn Taran) | 200 (9.50 MB) | 200 |
| 2025 | `pbflood50dsc1608_05092025` | cumulative 16 Aug – 5 Sep 2025 | 200 (2.81 MB) | 200 |
| 2025 | `pbflood50dsc1608_17092025` | cumulative 16 Aug – 17 Sep 2025 | 200 (4.62 MB) | 200 |
| 2023 | `pbflood50dsc11072023_1000hrs` | 11 Jul 2023 10:00 (optical) | 200 (1.06 MB) | 200 (0.39 MB) |
| 2023 | `pbflood50dsc12072023_0600hrs` | 12 Jul 2023 06:00 | 200 (7.11 MB) | 200 (0.05 MB) |
| 2023 | `pbflood50dsc18082023_0600hrs` | 18 Aug 2023 06:00 | 200 (6.69 MB) | 200 (0.05 MB) |
| 2019 | `2019/PB/` folder exists (403) | — | not enumerable* | not enumerable* |
| 2017 | `2017/PB/` folder exists (403) | — | not enumerable* | not enumerable* |

\* 2019/2017 folders are confirmed present but no individual product name is in the search index and a
per-date/time/frame probe grid returned no `200` — listing-disabled + un-indexed. To crack them one
must open the NDEM web-GIS / `hydrological_flood.php` viewer (JS app) rather than guess file paths.

Base URL: `https://ndem.nrsc.gov.in/documents/Disaster_Document/2025/PB/<folder>/<folder>_map.pdf`

Bonus national products (open PDF): `documents/downloads/allindia_flood_techdoc.pdf` (Flood Affected
Area Atlas of India, 1998–2022) and `documents/downloads/aggregated_flood_techdoc.pdf` (NRSC/ISRO DMSG
aggregated flood inundated area).

**Downloaded to `data/ndem/` (uncommitted):** the four 2025 `_map.pdf`, plus one 2023 `_map.pdf`
(`12072023_0600hrs`) and one 2023 `_report.pdf` (`11072023_1000hrs`) as samples. All verified
`PDF-1.7`, 1 page. **Verdict:** the two 2025 cumulative sheets (`1608_05092025`, `1608_17092025`) are
the primary NRSC ground-truth for validating the sailaab 2025 extent; per-acquisition 16/19-Aug sheets
give the mid-event snapshots.

---

## 2. Copernicus EMS Rapid Mapping — 2025 Punjab / North-India

**Method.** The public list at `emergency.copernicus.eu/mapping/list-of-activations-rapid` is dead
(`404`, site migrated). Live portal: `mapping.emergency.copernicus.eu` (Django + an S3-hosted React
"datastats" app). Keyless JSON API discovered from its bundle:
`…/activations/api/activations/?countries=<CC>&limit=100` (filter param is `countries`, ISO-2 code).

**India (`IN`) — 6 activations total, NONE in 2025.** Most recent India activation is 2019:

| Code | Date | Type | Name |
|---|---|---|---|
| EMSR357 | 2019-05-02 | Storm | Tropical Cyclone Fani in Eastern India |
| EMSR104 | 2014-10-14 | Flood | Flood in Andhra Pradesh |
| EMSR049 | 2013-06-27 | Flood | Floods in Uttarakhand |
| EMSR040 / EMSR054 / EMSR057 | 2013 | Flood / Storm | Assam flood; two tropical storms |

➡ **Copernicus EMS did NOT activate for the Indian-Punjab 2025 floods.** (Consistent with India
relying on its own NRSC/NDEM service.) There is no EMSR7xx India product to fetch.

**The relevant 2025 activation is Pakistan-side: `EMSR838` — "Flood in Pakistan".** Same monsoon /
Sutlej-Ravi-Chenab system as Indian Punjab, so its western AOIs are the nearest independent outline.

| Field | Value |
|---|---|
| Code | **EMSR838** |
| Countries | Pakistan (Punjab & Khyber Pakhtunkhwa provinces) |
| Category | Flood |
| Event start | 15 Aug 2025 00:00 (monsoon flash flood, per official snippet) |
| Activation | 2025-08-29 11:45 UTC |
| Last update | 2025-09-11 12:16 UTC (status: closed, DRM phase "response") |
| Centroid | POINT(70.609 E, 28.931 N) — southern Pakistani Punjab (Sutlej–Chenab confluence) |
| **AOIs** | **11** |
| **Products** | **25** |

Detail API (open): `https://mapping.emergency.copernicus.eu/activations/api/activations/EMSR838/`
Human page: `https://mapping.emergency.copernicus.eu/activations/EMSR838/`

**⚠ WALL — vector packages are NO LONGER open on the current portal.** The task assumed "open, no
login," but the products endpoint now returns:
`{"error":"Activation not found or access denied","require_login":true,"error_code":"ACTIVATION_AUTH_REQUIRED"}`.
The per-AOI extents, product dates, layer names, and vector-package (ZIP/shapefile) downloads all sit
behind a login on the 2026 mapping portal; the legacy `list-of-components/EMSR838` download path 404s.
Only the activation-level metadata above is keyless. **No EMS vectors were downloaded** (no login was
attempted, per instructions). If EMSR838 vectors are needed, they require a free CEMS account — but see
§4: the GFM WMS gives an equivalent independent outline keyless.

---

## 3. India AI Impact Festival — fresh re-verification (2026-07-21)

Sources fetched today via `r.jina.ai`: homepage and `/faq`; the two "Resources" Google-Drive PDFs
pulled directly (`drive.google.com/uc?export=download&id=…`). Diffed against the Jul-20 cache in
`.claude-crawl/reads/`.

**Deadline banner — VERBATIM (unchanged since Jul 20):**
> Submission Deadline Extended till - July 26, 2026

**Student category — VERBATIM:** category **"AI Impact Creators"**, target audience "Students in K-12 /
higher education / equivalent ecosystems". Two sub-categories / age brackets:
> - Students in the 13-17 years age group
> - Students 18 years & above

**Team size / entry limits — VERBATIM (FAQ):**
> AI Impact Creators may submit up to two (2) projects per email ID (including participation on another
> Creator's team, which counts toward that limit). Shapers, Nurturers, and Catalysts may submit one (1)
> entry each. … Once submitted, a project cannot be edited or deleted.

No **numeric maximum team size** is stated anywhere public (teams are referenced but not sized).

**Submission mechanics (synopsis format/pages, video length, upload-vs-link):**
**NOT specified on any public surface.** Checked: homepage, `/faq`, the "Guidelines" Drive PDF (which
is actually *"Guidelines on ethical and responsible AI"* — Intel's responsible-AI principles, not a
format spec), and the "Evaluation rubrics" Drive PDF (a scoring sheet: points for "usage of emerged
AI", open-sourced link, audience fit, validation — no synopsis/video specs). The FAQ only says "submit
projects according to your category guidelines" and to prepare "your write-up, demo links, and pitch
materials." Concrete synopsis page-count and video-length/upload rules live behind the **Login /
dashboard**, which was not entered.

**Changes since Jul 20:** none material. Deadline, four categories, and age brackets are identical. The
only homepage delta: the **"Evaluation rubrics" link changed** from a Google-Drive URL
(`…id=1w3Q3ubJT4sAkO8peJrgptevpt55UEmgs`) to a dead placeholder `#` (the Drive file itself still
downloads directly). Minor carousel/nav rendering differences only.

**Flags vs the working assumption "deadline Jul 26, synopsis PDF + ≤2-min video":**
- Deadline **Jul 26 2026 — CONFIRMED** (verbatim banner, unchanged).
- "Synopsis PDF + ≤2-min video" — **UNVERIFIABLE from public pages** (neither confirmed nor
  contradicted). No public page states a synopsis format or a 2-minute video limit. Recommend
  confirming inside the registration dashboard before relying on those numbers.
- Guidelines resource: `drive.google.com/file/d/1VSeOPfRUMUBFPe41iWP2hUN7c5x3_crC/view` (ethics).
- Support: `support@digitalreadiness.org`.

---

## 4. Copernicus GFM public-access verdict (keyless probe)

**Verdict: the GFM flood layers ARE reachable keyless via WMS — the login wall is only on the
front-end, not on the map service.** The React SPA at `global-flood.emergency.copernicus.eu` returns
its 4 KB shell for every path (`/api/`, `/geoserver/…`, `/gfm/…`, `/gfm-api/…` all yield the SPA, i.e.
no usable OGC/STAC endpoint on that host), and the EODC-hosted GFM data API
(`api.flooding.eodc.eu`) does not resolve — those routes look login/registration-walled. **However**,
the sibling GloFAS OWS at `https://ows.globalfloods.eu/glofas-ows/ows` serves an open `GetCapabilities`
(HTTP 200, 147 KB, no auth) that publishes the full GFM layer set —
`gfm_observed_flood_extent_group_layer`, `gfm_observed_water_extent_group_layer`,
`gfm_affected_population`, `gfm_affected_landcover`, `gfm_reference_water_mask_group_layer`,
`gfm_uncertainty_values_group_layer`, `gfm_sentinel_1_footprint/schedule`, `gfm_advisory_flags…`,
`gfm_exclusion_mask` — each with a **daily time dimension `2011-01-01 … present / PT24H`**, so any
Aug–Sep 2025 Punjab date is addressable. `GetMap` also works **keyless** (HTTP 200 `image/png`) once
the mandatory WMS-1.3.0 `STYLES=` parameter is included and the request uses the layer's advertised
`EPSG:3857` (omitting `STYLES` triggers an OGC `ServiceException`, not an auth challenge — confirming no
login gate). This WMS is a viable independent, no-login source of GFM observed-flood extent for
validating the Punjab 2025 maps; it is a raster/image service (no open vector/WFS or bulk download —
that remains the registration-gated EODC API).

Sample saved (uncommitted, `data/gfm/`): `glofas_ows_GetCapabilities.xml` and a Punjab
`gfm_observed_flood_extent` `GetMap` PNG for 2025-09-05.

---

## Keyless reproduction recipes

```bash
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36"

# NDEM product (browser UA required; folder is 403, the _map.pdf is 200):
curl -sL -A "$UA" \
  "https://ndem.nrsc.gov.in/documents/Disaster_Document/2025/PB/pbflood50dsc1608_17092025/pbflood50dsc1608_17092025_map.pdf" -o out.pdf

# EMS activation list, filter by country (ISO-2), keyless JSON:
curl -sL -A "$UA" "https://mapping.emergency.copernicus.eu/activations/api/activations/?countries=PK&limit=100"
curl -sL -A "$UA" "https://mapping.emergency.copernicus.eu/activations/api/activations/EMSR838/"

# GFM observed flood extent via keyless GloFAS WMS (note STYLES= is REQUIRED; use EPSG:3857):
curl -sL "https://ows.globalfloods.eu/glofas-ows/ows?service=WMS&version=1.3.0&request=GetCapabilities" -o glofas_caps.xml
curl -sL "https://ows.globalfloods.eu/glofas-ows/ows?service=WMS&version=1.3.0&request=GetMap\
&layers=gfm_observed_flood_extent_group_layer&styles=&crs=EPSG:3857\
&bbox=8237000,3503000,8460000,3763000&width=512&height=512&format=image/png&transparent=true\
&time=2025-09-05T00:00Z" -o gfm_punjab.png
```
