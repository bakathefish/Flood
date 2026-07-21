# Reservoir data — sources, endpoints, and provenance

Storage / level time series for the three dams whose releases drove the 2025
Punjab flood: **Bhakra** (Gobind Sagar, Sutlej), **Pong** (Beas), and
**Ranjit Sagar / Thein** (Ravi). Feeds the Wave-4 forecaster (storage +
Δstorage window features) and the Wave-3 causal figure.

## Files produced

| File | What | Granularity / span |
|------|------|--------------------|
| `data/reservoirs_2015_2025.csv` | CWC daily level+storage via data.gov.in | daily, 2015-2025 monsoon (Jun-Sep); these 3 dams end **2025-07-11** |
| `data/reservoirs_2025_flood_supplement.csv` | Aug-Sep 2025 flood window from BBMB/press (the gap the API cannot cover) | ~weekly, Aug 1 - Sep 6 2025 |
| `data/reservoir_windows.csv` | per (year, monsoon-window, dam) mean_storage + delta_storage | 10-day windows from `sailaab.windows` |
| `sailaab/reservoirs.py` | parse/normalize + window features (pure pandas) | — |
| `pipeline/fetch_reservoirs.py` | fetch/paginate the API into the CSV | — |

**New dependencies: none.** Fetch script uses the stdlib (`urllib`); the module
uses `pandas` (already required). data.gov.in access uses the public sample key,
no login.

## Route log (priority order, walls documented)

### 1. data.gov.in OGD API — WORKED (primary)
- Resource: **"Daily data of reservoir level of Central Water Commission
  (CWC)"**, index `1fc2148c-fc41-46f5-a364-bdc03f77053f`
  (page slug `daily-data-reservoir-level-central-water-commission-cwc`).
  ~2.17 M rows, ~200 reservoirs, from 1991; last refreshed 2026-05-15.
- Endpoint: `GET https://api.data.gov.in/resource/1fc2148c-...?api-key=<KEY>&format=json`
  with `filters[Reservoir_name]=`, `filters[Year]=`, `filters[Month]=`,
  `sort[Date]=asc`, `offset=`, `limit=`.
- Public sample key `579b464db66ec23bdd000001cdd3946e44ce4aad7209ff7b23ac571b`
  works but **hard-caps pages at 10 records** (any `limit>10` silently reverts
  to 10) and is **rate-limited (HTTP 429)** — hence month-by-month offset
  pagination with exponential backoff in the fetch script.
- Fields: `Reservoir_name, Basin, subbasin, Agency_name, Lat, Long, Date,
  Year, Month, Full_reservoir_level, Live_capacity_FRL, Storage, Level`.
- **Units: `Level` and `Full_reservoir_level` are METRES; `Storage` and
  `Live_capacity_FRL` are BCM (billion m³).** Missing readings are the literal
  string `NA`.
- Exact `Reservoir_name` keyword spellings (recovered from the resource page's
  embedded JSON):
  - Bhakra → `Gobind Sagar-Bhakra Reservoir`
  - Pong → `Pong Reservoir`
  - Ranjit Sagar/Thein → `Thein\Ranjit Sagar` (single backslash)
- FRL / live capacity per dam (from the data): Bhakra FRL **512.06 m = 1680.0 ft**
  (matches the stated 1,680 ft danger level), live cap 6.229 BCM; Pong FRL
  423.67 m = 1390 ft, live cap 6.157 BCM; Ranjit Sagar FRL 527.91 m, live cap
  2.344 BCM.
- **Coverage wall:** for all three BBMB-managed dams the series **stops on
  2025-07-11** (other reservoirs in the same resource continue to 2026-04),
  and June-July 2025 is sparse (many `NA`). This is consistent with BBMB
  ceasing to report to the central CWC feed mid-monsoon 2025. The Aug-Sep 2025
  flood window is therefore **not** available from this resource and is filled
  from route 5.
- Bulk CSV download on the resource page is captcha/modal-gated (no anonymous
  bulk file), so the paginated API is the only no-login path.

### 2. India-WRIS (indiawris.gov.in / arc.indiawris.gov.in) — UNREACHABLE here
- Swagger catalog `https://indiawris.gov.in/swagger-ui/index.html`; ArcGIS REST
  `https://arc.indiawris.gov.in/server/rest/services`. Both **time out from this
  environment** (egress appears geo-blocked to India; HTTP 000). The reservoir
  time-series API is POST-based, so not reachable via GET-only fallbacks either.
  Left as a future route from an India-egress host.

### 3. AIKosh (aikosh.indiaai.gov.in) — LOGIN-WALLED
- `daily_data_of_reservoir_level_of_central_water_commission_cwc` renders only a
  "Fetching User Profile" loader for anonymous users. Skipped. (It is the same
  CWC dataset already obtained via route 1.)

### 4. CWC weekly Reservoir Storage Bulletin PDFs — NO MONSOON 2025
- `https://cwc.gov.in/en/reservoir-level-storage-bulletin` (published Thursdays).
  PDFs are GET-able (`https://cwc.gov.in/sites/default/files/fb-DDMMYYYY.pdf`),
  but the **series' latest issue is 2025-05-08** (`fb-08052025.pdf`); no
  June-September 2025 bulletins are posted. So this route also cannot cover the
  flood window. (`cwc.gov.in/en/ffm_dashboard` returns 401.)

### 5. BBMB + press for the Aug-Sep 2025 flood window — WORKED (supplement)
Authoritative dated readings for the flood window (`level` in feet for
Bhakra/Pong as officially reported by BBMB, metres for Ranjit Sagar; `storage`
in BCM back-computed from officially-reported % full × live capacity where a %
is given, otherwise blank):
- SANDRP, "Punjab Floods 2025: Role of Bhakra, Pong and Ranjit Sagar Dams"
  (2025-09-07) — day-by-day levels, % full, and releases.
- Down To Earth, "Mismanagement of three major dams … worsened the 2025 Punjab
  floods".
- The Tribune, "Punjab floods: Bhakra water level drops; Pong dam continues high
  outflow" (2025-09-06) — exact inflow/outflow.
- Babushahi (2025-08-06) — three-dam snapshot with inflow/outflow.

## Anchor-number verification (task targets vs. obtained data)

| Anchor (task) | Obtained data | Verdict |
|---|---|---|
| Bhakra ≈ **1,668.57 ft** ~Aug 25 2025 (danger 1,680 ft) | 1,635 ft (Aug 6) → **1,666 ft (Aug 19)** → 1,676.78 ft (Sep 2) → 1,679 ft (Sep 4, season high). FRL confirmed 512.06 m = **1,680.0 ft**. | **Consistent** — Aug 25 falls between 1,666 (Aug 19) and 1,676.78 (Sep 2); interpolates to ~1,668-1,670 ft. Exact 1,668.57 not separately quoted. |
| Pong ≈ **1,393 ft** | **Crossed 1,393 ft on Aug 26** (above FRL 1,390 ft); 1,394.71 ft on Sep 5; 1,394.67 ft on Sep 6. | **Confirmed.** |
| Large releases **Aug 26-27** (~2.6 lakh cusecs Sutlej) | **Ranjit Sagar (Ravi): 77,000 cusecs Aug 26 → 173,000 cusecs Aug 27** (crossed FRL, 527.13 m). Bhakra (Sutlej) outflow peaked ~85,000 cusecs (Sep 4-5); Pong outflow >100,000 cusecs from Aug 29 (99,673 cusecs Sep 6). | **Partly confirmed.** Big Aug 26-27 release is real but its ~2.6 lakh-cusec (260k) magnitude is a *downstream cumulative* Sutlej figure, not a single-dam release; largest single-dam release in that window was Ranjit Sagar 173k cusecs (Aug 27). Bhakra's own peak was ~85k cusecs. |

Release (outflow) figures are recorded here rather than in the CSV (no flow
column): Bhakra spillway opened Aug 19-20 (first in 2 years); Ranjit Sagar
outflow 9k (Aug 24) → 24k (Aug 25) → 77k (Aug 26) → 173k (Aug 27) cusecs;
"from Aug 27, outflow > inflow for five days" (SANDRP).

## Reproduce
```
python pipeline/fetch_reservoirs.py                 # all dams, 2015-2025 -> data/reservoirs_2015_2025.csv
python -m pytest tests/test_reservoirs.py -q
```
`sailaab.reservoirs.load_frames([...])` concatenates the API CSV and the flood
supplement, then `window_features(df, years)` builds `reservoir_windows.csv`.
