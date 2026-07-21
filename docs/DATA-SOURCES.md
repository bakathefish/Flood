# Data sources

Every dataset touched by the pipeline. Access dates are when the data was first pulled by this repo's scripts. Detailed access recipes and gotchas live in `docs/notes/`.

| Dataset | Provider | Access | License | Accessed | Used for |
|---|---|---|---|---|---|
| Sentinel-1 RTC (γ0, IW, VV+VH) | Copernicus / ESA, processed by Catalyst for Microsoft Planetary Computer | Anonymous STAC API, collection `sentinel-1-rtc` (`planetarycomputer.microsoft.com/api/stac/v1`); windowed COG reads, SAS re-sign on expiry | Copernicus Sentinel data — free & open, attribution | 2026-07-21 | 2025 flood mapping (Tier A change detection, RF features) |
| GFM observed flood extent + reference water mask | Copernicus EMS Global Flood Monitoring (Sentinel-1 derived) | Keyless GloFAS OWS WMS 1.3.0 (`ows.globalfloods.eu/glofas-ows/ows`), daily TIME 2011→present, EPSG:3857 | Copernicus free/full/open (Reg. EU 377/2014), attribution: "Contains modified Copernicus EMS — Global Flood Monitoring information, 2025" | 2026-07-21 | 2025 validation, RF label strata, decade labels + frequency atlas |
| 0.25° daily gridded rainfall | India Meteorological Department, Pune | `imdlib` → imdpune.gov.in yearwise `.grd`, no login | Govt. of India / IMD — free for research with attribution | 2026-07-21 | Forecaster rainfall predictors (Punjab + upstream boxes, lags). Ref: Pai et al. (2014), MAUSAM 65(1) |
| Daily reservoir level/storage (CWC) | Central Water Commission via data.gov.in OGD API | Resource `1fc2148c-fc41-46f5-a364-bdc03f77053f`, public sample key, month-wise pagination | Govt. Open Data License – India | 2026-07-21 | Forecaster reservoir features; causal figure (Bhakra / Pong / Ranjit Sagar, monsoons 2015–2025 to 2025-07-11) |
| Reservoir flood-window supplement (Aug–Sep 2025) | BBMB figures via SANDRP (2025-09-07), The Tribune (2025-09-06), Down To Earth, Babushahi | Cited press/official rows, hand-keyed with per-row source | Facts, cited | 2026-07-21 | The 2025 reporting gap: all three BBMB dams stop central CWC reporting on 2025-07-11 |
| District boundaries (Census 2011 vintage) | datameet/maps community digitization | GitHub raw `dists11.geojson`, filtered `ST_NM=="Punjab"` (20 districts) | ODbL v1.0 | 2026-07-21 | District stats, spatial-CV folds, rasterization. Vintage matches FAO GAUL 2015 used in `gee/` |
| Copernicus DEM GLO-30 | ESA / Airbus via Planetary Computer `cop-dem-glo-30` | Anonymous STAC | Free with attribution | 2026-07-21 | Slope feature / masking (RF stage) |
| ESA WorldCover 10 m (class 40 = cropland) | ESA via Planetary Computer `esa-worldcover` | Anonymous STAC | CC-BY 4.0 | 2026-07-21 | Crop-flooded hectares (Wave 1/3) |
| NDEM flood map products (PB 2017/2019/2023/2025) | ISRO / NRSC | `ndem.nrsc.gov.in/documents/Disaster_Document/<yr>/PB/…` PDFs (browser UA required); 4 products for 2025 incl. two cumulative sheets | Government map sheets — viewed for validation, not redistributed | 2026-07-21 | Independent validation (visual/georeferenced comparison) |
| Festival portal facts | indiaaiimpactfest.ai-for-all.in | Public pages (deadline banner, category, brackets) | — | 2026-07-21 | Deadline **Jul 26 2026** re-verified; synopsis/video spec is behind registration |

Dead ends, documented in `docs/notes/validation-recon.md`: Copernicus EMS Rapid Mapping EMSR838 vectors (login-walled as of 2026-07-21), India-WRIS API (geo-blocked/timeout), AIKosh downloads (login), CWC weekly bulletins (series stops 2025-05-08, no monsoon-2025 issues), CWC ffm_dashboard (401).
