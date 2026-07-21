# IMD daily gridded rainfall — forecaster predictors (Wave 4)

Real daily gridded rainfall 2015–2025 for the Punjab plains and the upstream
Sutlej/Beas/Ravi Indian-Himalayan catchments, aggregated to two box daily
area-means and to the decade's monsoon windows (current + lag-1 + lag-2) for the
flood forecaster.

## Source

**Primary (used for all 11 years):** India Meteorological Department (IMD), Pune —
0.25° × 0.25° gridded **daily** rainfall (mm/day), the official Government-of-India
product. Pulled with the `imdlib` package, which POSTs yearwise `.grd` files
straight from `imdpune.gov.in` with **no login**.

`imdlib.get_data('rain', 2015, 2025, fn_format='yearwise')` → `open_data(...).get_xarray()`.

Grid: lat 6.5–38.5 °N (129 rows), lon 66.5–100.0 °E (135 cols), no-data `-999.0`.

**2025 availability:** confirmed present and complete — the 2025 file covers
2025-01-01…2025-12-31 with valid monsoon data, so the CHIRPS/ClimateSERV fallback
was **not needed**. Every year 2015–2025 in the committed CSVs is IMD 0.25°.

### Citation rows (for docs/DATA-SOURCES.md when next updated)

| Dataset | Provider | Access | License | Accessed | Used for |
|---|---|---|---|---|---|
| 0.25° daily gridded rainfall (mm) | India Meteorological Department, Pune | `imdlib` → `https://imdpune.gov.in/cmpg/Griddata/rainfall.php` (yearwise `.grd`, no login); landing: `https://imdpune.gov.in/cmpg/Griddata/Rainfall_25_NetCDF.html` | Govt. of India / IMD — free for research & academic use with attribution (commercial use needs IMD permission) | 2026-07-21 | Forecaster rainfall predictors (Punjab local + upstream Himalayan, current + lags) |

- Dataset reference: Pai D.S. et al. (2014), *Development of a new high spatial
  resolution (0.25° × 0.25°) long-period (1901–2010) daily gridded rainfall data
  set over India*, **MAUSAM** 65(1), 1–18.
- Tooling: `imdlib` (Nandi et al.), https://pypi.org/project/imdlib/ ·
  https://github.com/iamsaswata/imdlib

## New dependencies (pipeline-only — deliberately NOT in requirements.txt)

Used only by `pipeline/fetch_rain.py`. The library `sailaab/rain.py` needs
neither (pure pandas/numpy).

- `imdlib` (>=0.1.21) — downloads/reads IMD `.grd`; pulls `xarray`, `scipy`,
  `requests`, `matplotlib`.
- `xarray` (>=2024) — box `sel` + weighted area-mean during extraction.

Install: `pip install imdlib`.

## Method & deliberate approximations

- **AOI boxes** (bounding boxes, *not* true basin polygons — a deliberate
  approximation; refine with `WWF/HydroSHEDS` if needed):
  - `punjab_mm`  — lon 73.85–76.95 °E, lat 29.53–32.60 °N (Punjab plains; 12×12 cells).
  - `upstream_mm` — lon 75.5–78.6 °E, lat 30.9–33.3 °N (Sutlej/Beas/Ravi upstream; 10×13 cells).
- **Area-mean:** cos(lat)-weighted mean over grid cells whose centres fall in the
  box, skipping no-data cells. The upstream box overlaps terrain outside Indian
  territory where IMD has no data; those cells are `-999` → masked → excluded, so
  the mean reflects the Indian-monitored catchment only.
- **-999 masking done here, not by imdlib:** `imdlib.get_xarray()` tries to mask
  `-999` via `Dataset.values != -999`, which **silently no-ops on xarray ≥ 2024**
  (leaks the fill into the western Punjab/border cells and drives the mean
  negative). `fetch_rain.py` therefore masks explicitly with `rain.where(rain >= 0)`
  (rainfall is non-negative; any negative is a sentinel).
- **Windows:** half-open `[start, end)`, identical to `sailaab.windows` /
  GEE `filterDate` — adjacent windows never double-count the seam. A lag-k window
  is the current window shifted back by `k × (end−start)` days (antecedent
  precipitation), re-summed from the daily frame (so it is real even for the first
  window of a season). Logic + tests: `sailaab/rain.py`, `tests/test_rain.py`.

## Outputs

- **Committed:** `data/rain_daily_boxes_2015_2025.csv` (date, punjab_mm,
  upstream_mm; 4018 rows; ~88 KB) and `data/rain_windows_2015_2025.csv` (year,
  window_start, window_end, punjab_mm, upstream_mm, *_lag1, *_lag2; 121 rows =
  11 years × 11 monsoon windows). Re-summing the daily CSV reproduces the windows
  CSV exactly.
- **Not committed:** `data/rasters/imd/rain/*.grd` (~25 MB/yr; local-only via
  `.git/info/exclude`). Regenerate with `python pipeline/fetch_rain.py`
  (download-if-missing → extract).

## Finding — 2025 anomaly sanity check (goes to the synopsis)

Box rainfall summed over **Aug 20 – Sep 5** (the flood fortnight), 2025 vs the
2015–2024 same-window distribution:

| Box | 2025 sum | 2015–24 mean | 2015–24 max | z-score | percentile | rank | vs mean |
|---|---|---|---|---|---|---|---|
| Punjab plains | **342.2 mm** | 77.9 mm | 120.9 mm | **+9.68** | 100 | 1 / 11 | **+339 %** |
| Upstream (Sutlej/Beas/Ravi) | **306.2 mm** | 80.3 mm | 110.8 mm | **+9.79** | 100 | 1 / 11 | **+281 %** |

**2025 is the single most extreme year in the 11-year IMD record for both boxes**
(rank 1/11, ~+10σ, ≈3–4× the decade mean). This independently corroborates the
district-level anomalies cited for the event (+343 % … +887 %) and the "worst
flood since 1988" framing. Regenerate: `python pipeline/fetch_rain.py`.
