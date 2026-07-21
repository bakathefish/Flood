# Indian government data sweep — findings, recipes, walls

Sweep date: 2026-07-22. Scope: four sub-missions — (1) district paddy actuals for the ₹ VaR,
(2) official 2025 relief/damage validation, (3) ISRO Bhuvan keyless probe, (4) AIKosh /
IndiaAI Compute / Bhoonidhi dossiers. Keyless fetches only (`curl` + browser UA;
`r.jina.ai` for JS pages; data.gov.in public sample key). No logins anywhere; every wall
below is documented with its HTTP behaviour.

---

## 1. District paddy actuals → VaR v2 (`data/punjab_paddy_apy.csv`, `data/district_var_v2.csv`)

### What was obtained — DES 2022-23 district Rice APY, keyless

The authoritative source worked: **DES (Directorate of Economics & Statistics, Ministry of
Agriculture) APY report portal** `https://data.desagri.gov.in/website/crops-apy-report-web` —
**Punjab × Rice × Kharif × 2022-23, all 23 districts** (Area ha, Production t, Yield t/ha).
No login: it is a public report form; it just cannot be fetched statelessly (the report body
is built from server-side session state seeded by the dropdown AJAX flow — a plain GET of
the report URL returns HTTP 200 `Content-Length: 0`). Driving the real form in a browser
(select Punjab → All Districts → Rice → Kharif → 2022-23 → View Report) renders the full
table. Form internals for replay: base `POST /postReq` (Laravel CSRF `_token` +
`laravel_session`), params `fltrstates[]=3` (Punjab), `fltrdistricts[]`, `fltrcrops[]=1`
(Rice), `fltrseason[]=K`, `fltrstartyear`/`fltrendyear` (1997→2022), `fltrrptformat`
(scrview/exl/pdf), `reportformat=horizontal_crop_vertical_year`.

### Basis verification (the number that decides the valuation)

The DES table is **MILLED RICE**, not paddy: statewide 13,751,000 t / 3,167,800 ha =
**4.341 t/ha**, squarely on the milled-rice anchor (~4.2–4.4 recent Punjab) and 1.5× below
the paddy anchor. Area cross-check: 31.68 lakh ha matches Punjab's known 2022-23 rice area.
Paddy-equivalent = rice ÷ (2/3) (standard DES paddy→rice milling convention) → statewide
**6.511 t/ha paddy — within 0.2 % of the v1 flat 6.5**, independently validating both the
sourced table and the conversion. `data/punjab_paddy_apy.csv` carries both
`rice_yield_t_ha` (as published) and `yield_t_ha` (paddy-equivalent, used downstream).

Cross-validation of the same lineage: data.gov.in resource **"District-wise, season-wise
crop production statistics from 1997"**, index id `35be999b-0208-4354-b557-f6ca9a5355de`
(note: the widely-circulated id ending `…f6ca9a5ab07c` is wrong — returns "Meta not found").
It is keyless via the sample-key API (10 records/page, 429 rate-limits) but its Punjab rice
series **ends at crop year 2014**; the 2014 table (22 districts, 2.894 Mha, 3.84 t/ha milled
= official 2014-15 figure exactly) was pulled as a fallback and is superseded by the DES
2022-23 table above.

### VaR v2 (`data/district_var_v2.csv`)

Formula: `crop_var_inr_v2 = crop_flooded_ha × paddy_share × district_paddy_yield_t_ha ×
MSP`, with **MSP ₹23,200/t** (grade-A ₹2,320/quintal, unchanged from v1),
**paddy_share = 1.0** (documented assumption, same as v1 implicitly: monsoon-season
WorldCover cropland in the flood belt is treated as paddy), and district paddy-equivalent
yields from the 2022-23 DES table. Post-2011 districts are merged back to our Census-2011
polygons area-weightedly (**Fazilka→Firozpur, Pathankot→Gurdaspur, Malerkotla→Sangrur**).
`district_flood_stats_2025.csv` is untouched; v2 lives in the new file.

| | v1 (flat 6.5 t/ha) | v2 (district DES yields) |
|---|---|---|
| Statewide total | **₹545.8 crore** | **₹523.2 crore** (−4.1 %) |

The level barely moves (statewide yields agree) — **the correction is distributional**:
Amritsar ₹56.1→46.0 cr and Gurdaspur ₹55.3→44.8 cr (−18 %; yields 5.34/5.26 t/ha — the
**basmati belt** has genuinely lower per-ha mass), while Moga rises ₹26.0→30.4 cr
(7.59 t/ha) and Firozpur is nearly flat (6.48 t/ha ≈ 6.5). Honesty caveat for any display:
border-district rice includes basmati, which yields less but sells **above** MSP — pricing
everything at common-paddy MSP makes the v2 basmati-district figures conservative.

Reproduce v2 from the two CSVs (pure pandas):
```python
import pandas as pd
from sailaab.districts import canonical_name
V = {"Fazilka":"Firozpur","Pathankot":"Gurdaspur","Malerkotla":"Sangrur"}
apy = pd.read_csv("data/punjab_paddy_apy.csv")
apy["d"] = apy.district.map(canonical_name).map(lambda x: V.get(x,x))
m = apy.groupby("d").agg(a=("area_ha","sum"), p=("production_t","sum"))
m["paddy_yield"] = m.p/m.a/(2/3)
fl = pd.read_csv("data/district_flood_stats_2025.csv")
v2 = fl.crop_flooded_ha * fl.district.map(canonical_name).map(m.paddy_yield) * 23_200
```

### Walls (sub-mission 1)
- data.gov.in Punjab-specific resources — `"District-wise Yield under Rice Cultivation in
  Punjab 1968-2022"` (uuid `c41db276-9969-4988-8aca-da0c1dc863b3`) and the food-grains APY
  catalog: **not API-exposed** ("Meta not found"); their download buttons are
  Janparichay-login-gated (`icon-lock`).
- `esopb.gov.in` (Punjab Statistical Abstract) — connection timeouts (HTTP 000) from this
  egress.
- `aps.dac.gov.in` (legacy APY portal) — timeout (HTTP 000).
- `upag.gov.in` — reachable (HTTP 200 shell) but its data flows sit behind portal APIs that
  were not needed once DES delivered.

---

## 2. Official 2025 relief/damage validation (`data/official_relief_2025.csv`)

### What was obtained

**District-wise crop damage (girdawari).** The Punjab Revenue, Rehabilitation & Disaster
Management Minister (Hardeep Singh Mundian) released a Special Girdawari progress report on
**2025-09-13** with a district-wise crop-damage table in hectares — 18 districts, summing to
198,524 ha ≈ the stated statewide **1,98,525 ha** (internally consistent). Carried by
Babushahi (news-quoting-official, full table) and corroborated by ANI's report of the same
briefing. This is the single best public district-resolved official damage dataset for the
2025 event; no genuine 2025 *per-district rupee disbursement* table was public at sweep time
(girdawari finalised after Oct 7; payouts from Oct 15 2025).

Also captured in the CSV: per-district `people_affected` / `villages_affected` for the worst
districts (Sphere India SitRep-03, 2025-09-08, media/Red Cross-sourced; Gurdaspur figures
corroborated by the govt broadcaster newsonair.gov.in), the per-district girdawari
`patwaris_deployed` (2,167 total — an official effort proxy that covers the three ranked
districts missing a crop-ha line), and statewide totals: 55 deaths (Sep 12), 2,050 villages,
~3.5 lakh people affected, 3,87,898 displaced, **₹71 crore immediate state relief**
(₹35.50 cr equally to all districts + ₹35.50 cr to the 12 worst-hit), **₹1,600 crore central
assistance** (PM, Sep 9; PIB PRID 2164996), ₹14,000 crore interim state loss estimate, and
the compensation regime (₹20,000/acre for 75–100 % loss = ₹6,800 Centre + ₹13,200 state).

**Trap rejected:** a Tribune district-wise ₹186-crore relief table (Patiala ₹59.50 cr …)
looks perfect but its `datePublished` is **2023-08-23** — it is the 2023 flood, not 2025.
Excluded.

### Rank correlation vs our satellite map — the validation number

Our polygons are Census-2011 vintage (20 districts), so post-2011 districts merge back for
the comparison: **Fazilka→Firozpur, Pathankot→Gurdaspur, Malerkotla→Sangrur**. Correlating
official girdawari `crop_damage_ha` against our `rf_flooded_ha`
(`data/district_flood_stats_2025.csv`), Spearman, pure pandas:

| Variant | ρ |
|---|---|
| 16 districts named in the girdawari table | **0.556** |
| All 20 (districts absent from every official damage list ≔ 0) | **0.720** |
| Tier-A flooded ha vs girdawari (16) | 0.621 |

**5 of our satellite top-6 are in the official top-6** (Gurdaspur, Firozpur, Amritsar,
Kapurthala, Tarn Taran — official #4 Patiala is the exception). The divergences are
coherent, not random: **Patiala (official #4, ours #12), Mansa (#7 vs #14), Sangrur (#9 vs
#15) are all Ghaggar-basin districts** — rain-fed southern flooding where girdawari counts
cumulative crop loss (incl. waterlogging) while our Aug 25–Sep 6 SAR window captures
standing water on acquisition dates. Conversely Muktsar/Faridkot/Barnala/Fatehgarh Sahib
(our ranks 13/18/19/20, all small) have no official crop-damage line at all — consistent
with negligible true damage. Framing: *"our satellite ranking correlates ρ≈0.56 (0.72 with
the full district set) with where the official girdawari found crop damage, and agrees on
5 of the top 6 districts; the gap is concentrated in the Ghaggar basin, outside our
Ravi–Beas–Sutlej SAR windows."*

Reproduce (pure pandas):
```python
import pandas as pd
rel = pd.read_csv("data/official_relief_2025.csv")
crop = rel[(rel.metric=="crop_damage_ha") & (rel.district!="STATEWIDE")].copy()
V = {"Fazilka":"Firozpur","Pathankot":"Gurdaspur","Malerkotla":"Sangrur"}
off = crop.assign(d=crop.district.map(lambda x: V.get(x,x))).groupby("d")["value"].sum()
sat = pd.read_csv("data/district_flood_stats_2025.csv").set_index("district")
both = sat.join(off.rename("official_ha"), how="inner")
rho = both.rf_flooded_ha.corr(both.official_ha, method="spearman")   # 0.556
```

**Note on the config honesty band:** `OFFICIAL_CROP_FLOODED_HA_BAND = (148k, 175k)` matches
the Sep 3 / Sep 8 official figures; the girdawari as-of Sep 13 reached ~198.5k ha (the
number kept rising as surveys progressed). Not changed here — recorded for context.

### Walls (sub-mission 2)
- `pib.gov.in` PressReleasePage — **403** to non-browser fetch; content recovered via DD
  News (both carry the same PM announcement).
- `indianexpress.com`, `timesofindia.indiatimes.com` — fetch-blocked; figures recovered via
  alternative carriers of the same official statements.
- Sphere India SitRep is a binary PDF — needs `pdftotext`, not a plain fetch.

---

## 3. ISRO Bhuvan keyless probe — VERDICT: two keyless NRSC OGC services work

**Both a Bhuvan LULC-50k WMS and an NRSC flood WMS are open — no key, no login, plain
`curl`.** This adds ISRO-served layers to the stack keylessly.

### 3a. Bhuvan GeoServer WMS (vector/thematic incl. LULC 1:50k) — OPEN
- Endpoint: `https://bhuvan-vec1.nrsc.gov.in/bhuvan/wms`
- `GetCapabilities` → **HTTP 200**, `application/vnd.ogc.wms_xml`, ~1.06 MB, **777 layers**
  (GeoServer). WFS exists too but rejects anonymous feature access (ExceptionReport), so
  Bhuvan vectors are effectively raster-only via WMS.
- Punjab-relevant layers found: `sisdp:Amritsar_lulc` (SIS-DP LULC 1:50k, EPSG:4326, bbox
  74.487–75.405 E, 31.482–32.055 N; renders agriculture-dominant LULC with built-up),
  `sdv:pb_slope`, `nuis:pb_lu_mg` (urban land-use), `pb_railgrp`, plus many other states'
  `sisdpv2:*_lulc_v2` district sheets. Coverage is per-district and patchy — Amritsar is the
  only Punjab `sisdp` LULC sheet on vec1; this is a *sample/branding* layer, not a
  statewide substitute for WorldCover.
- Verified sample (HTTP 200, valid 800×500 PNG):
```bash
curl -sL -A "$UA" "https://bhuvan-vec1.nrsc.gov.in/bhuvan/wms?service=WMS&version=1.1.1\
&request=GetMap&layers=sisdp:Amritsar_lulc&styles=&srs=EPSG:4326\
&bbox=74.48697658200007,31.482027059000075,75.40457918300005,32.05546570600003\
&width=800&height=500&format=image/png" -o amritsar_lulc.png
```

### 3b. NRSC Disaster-Services flood WMS (MapServer) — OPEN, but archive-era
- Endpoint: `https://bhuvan-ras2.nrsc.gov.in/cgi-bin/flood.exe` (MapServer 7.0.7 / MS4W),
  discovered inside `bhuvan-app1.nrsc.gov.in/disaster/disaster.php` (page itself HTTP 200).
- `GetCapabilities` → **HTTP 200**, 103 KB, **157 layers**: per-event flood-inundation
  layers named `<state>_<DDMMYY>_flood` (as=Assam 51, or=Odisha 28, br=Bihar 14, mh=9, wb=8,
  ap=8 …) — **the dated layers span ~2011–2013**, i.e. this is the legacy flood archive.
- **`punjab_flood`** is the only Punjab layer (undated composite; bbox 74.65–77.22 E,
  28.99–30.80 N = **south-east Punjab / Ghaggar basin**, so a legacy Ghaggar-flood product,
  NOT the 2025 Ravi–Beas–Sutlej event). `GetLegendGraphic` also works (HTTP 200).
- Verified sample (HTTP 200, valid PNG; flood polygons render in cyan, ~2 % of frame):
```bash
curl -sL -A "$UA" "https://bhuvan-ras2.nrsc.gov.in/cgi-bin/flood.exe?SERVICE=WMS\
&VERSION=1.1.1&REQUEST=GetMap&LAYERS=punjab_flood&STYLES=&SRS=EPSG:4326\
&BBOX=74.6495,28.9896,77.2159,30.7983&WIDTH=800&HEIGHT=564&FORMAT=image/png\
&TRANSPARENT=TRUE" -o punjab_flood.png
```
- **2025 flood layers are NOT on this WMS.** The 2025 Punjab products exist only as NDEM PDF
  map sheets (see `docs/notes/validation-recon.md` §1) and inside the login/JS NDEM web-GIS.

### 3c. Dead endpoints (documented so nobody re-probes)
| Endpoint | Result |
|---|---|
| `bhuvan-vec2` / `bhuvan5` (any path) | timeout (HTTP 000) from this egress |
| `bhuvan-ras1|ras2 /bhuvan/wms`, `/geoserver/wms`, `/bhuvan/gwc/service/wms` | 404 |
| `bhuvan-app1 /bhuvan/wms`, `/geoserver/wms`, `/disaster/wms` | 404 |
| `bhuvan-vec1 /bhuvan/wfs` GetFeature (anonymous) | OGC ExceptionReport (no anon WFS) |

`UA` = a browser User-Agent string — NRSC hosts serve plain curl a 403 without one.

---

## 4. AIKosh, IndiaAI Compute, Bhoonidhi

### 4a. AIKosh (aikosh.indiaai.gov.in) — fully login-walled; adds nothing keyless

Every catalog/detail URL (and the `aikosh/api/v1/dataset/search` path) returns the SPA
shell that blocks on a **"Fetching User Profile"** loader before rendering anything —
confirmed three ways (Jul-20 cache, live curl HTTP 200 shell, live `r.jina.ai` JS render).
Anonymous users cannot even list the catalog. Datasets confirmed present (slugs from cached
detail URLs) and where to get the same data OPEN instead:

| AIKosh dataset (slug) | Theme | AIKosh access | Open equivalent |
|---|---|---|---|
| `daily_data_of_soil_moisture` | NRSC VIC-model daily soil moisture | LOGIN-walled | No clean open mirror found — the one AIKosh-unique item of interest (NRSC VIC hydrology; the companion VIC *rainfall* is open, see below) |
| `daily_rainfall_data_from_india_meteorological_department_imd_grid_model_agency_during_july_2022` | IMD 0.25° gridded rain (Jul 2022 slice) | LOGIN-walled | OPEN: IMD Pune `.grd` via `imdlib` (already our forecaster source); also NRSC-VIC district rainfall via data.gov.in resource `6c05cd1b-ed59-40c2-bc31-e314f39c6971` |
| `daily_data_of_reservoir_level_of_central_water_commission_cwc` | CWC reservoir levels | LOGIN-walled | OPEN: data.gov.in resource `1fc2148c-fc41-46f5-a364-bdc03f77053f` (already our reservoir source) |

Flood/crop/LULC AIKosh slugs could not be enumerated anonymously. Open alternates:
data.gov.in `search?title=flood` (~113 open *tabular* resources — e.g. State/UT flood damage
1953–2010 & 2016–2018, FMP/FMBAP central assistance, CWC FF stations) and Bhuvan/Bhoonidhi
for rasters (§3, §4c). **Bottom line: register on AIKosh only for the VIC soil-moisture
product; everything else it holds is open at the origin.**

### 4b. IndiaAI Compute — student GPU dossier (10-minute read)

Portal `https://compute.indiaai.gov.in/` (302 → `/login`). Rulebook: **"End-User Policy for
AI Services on the Cloud"**
(`indiaai.s3.ap-south-1.amazonaws.com/docs/end-user-policy-for-indiaai-compute-portal.pdf`).
38,000+ empanelled GPUs (H100/H200/A100, MI300X, Gaudi 2, Trainium) via 19 providers;
reported floor rate **~₹65–67/GPU-hr**, plus **up to 40 % IndiaAI subsidy** for approved
users. There is **no blanket free student tier**.

1. **Eligibility** — students are an explicit category (End-User Policy §3.3, "students in
   K-12/UG/PG courses with projects in AI/ML"). BUT approval is **institution-gated**: a
   faculty verifier-and-endorser from your institute must endorse on the portal (their own
   onboarding needs an HOD/Director/Dean/Registrar letter, §5.3c).
2. **Steps** — (a) register on `compute.indiaai.gov.in` with institute email + mobile (OTP,
   §4.1); (b) submit **APAAR ID** (mandatory for students, verified electronically, §4.2);
   (c) submit project proposal in Annexure-I format with a GPU×hours BOQ (§4.3); (d) route:
   **fast lane** (§4.5: ≤5,000 GPU-hrs, ≤50 GPUs, no subsidy → just faculty endorsement +
   availability) or **committee lane** (§4.6: bigger/subsidised → monthly PMEC batch,
   collated the 1st–25th, subsidy quantum decided there).
3. **Documents** — APAAR ID; student profile (subjects, publications/projects); faculty
   endorsement.
4. **Turnaround** — fast lane: as fast as the faculty endorses; subsidy lane: monthly PMEC
   cycle, budget **2–6 weeks**.
5. **Honest verdict for a solo student** — reachable only with one cooperating professor
   (fast lane is then genuinely cheap). Without that: **Kaggle (free T4×2/P100,
   ~30 GPU-hrs/wk)** or Colab free T4 are the realistic defaults for Sailaab-scale
   workloads; C-DAC AIRAWAT/PARAM (NSM) is the same institution-gate.

### 4c. NRSC Bhoonidhi — free EO downloads + EOS-04 SAR cross-validation

Portal `https://bhoonidhi.nrsc.gov.in/` (302 → `/bhoonidhi/home.html`, HTTP 200; help path
is `…/bhoonidhi/help/` — `help.html` 404s). Archive of 47 satellites since 1986 incl.
regional Sentinel-1/2 and Landsat-8/9 distribution.

1. **Register (free, self-service, no documents)** —
   `https://bhoonidhi.nrsc.gov.in/bhoonidhi/registration.html`: name, login, email+mobile
   (OTP), user type **"Academic"**, organisation, address, captcha, T&C. That is the entire
   gate for Open Data downloads.
2. **Search & download** — Browse & Order at `…/bhoonidhi/index.html` (AOI + date + sensor
   → View → *Download* for Open Data); STAC **Open Data Access API** at `…/bhoonidhi-api/`
   (access by mail to `bhoonidhi@nrsc.gov.in`); fresh EOS-04 acquisitions can be requested
   via `bhoonidhi-planner.nrsc.gov.in`. Since 2024-02-01, **Level-2B products are in the
   OpenData_DirectDownload category**.
3. **EOS-04 facts** (naming: EOS-04 = RISAT-1A follow-on, launched 2022-02-14 PSLV-C52,
   C-band 5.4 GHz — *not* "RISAT-1B", which is EOS-09, lost in the May-2025 PSLV-C61
   failure): modes HRS <2 m/10 km, FRS-1 ~few m/25 km, FRS-2 12 m/30 km quad-pol,
   **MRS 25 m/120 km**, **CRS 50 m/240 km**; products L0/L1(SLC)/L2A/**L2B
   terrain-normalised ARD (CEOS-ARD/RTC, GeoTIFF)**/L3A.
4. **What Sailaab would do with it** — pull EOS-04 **L2B ARD ScanSAR (MRS 25 m)** over
   Punjab for flood-window + dry-baseline dates, run the existing C-band water-detection
   thresholds (both sensors are C-band ~5.4 GHz, thresholds transfer), and report per-
   district IoU/F1 vs the Sentinel-1 maps: an ISRO-sourced, agency-independent SAR
   confirmation that de-risks single-sensor reliance. Requires the free registration above
   (kept as a documented login-gated opportunity; not exercised in this keyless sweep).

---

## Cross-cutting walls table (this sweep)

| Source | Status |
|---|---|
| Bhuvan vec1 WMS + flood.exe WMS | **OPEN** (recipes above, samples verified) |
| AIKosh (all of it) | LOGIN (SPA profile-gate; no anon API) |
| IndiaAI Compute portal | LOGIN (302 → /login); policy PDF open |
| Bhoonidhi downloads | free-registration gate (browse open) |
| PIB press pages | 403 to non-browser fetch (mirrors open) |
| punjab.data.gov.in state portal | listing open; CSV download is JS/captcha-gated |
| data.gov.in API (sample key) | OPEN but 10-records/page + 429 rate-limit |
