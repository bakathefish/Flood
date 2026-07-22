# EOS-04 (RISAT-1A) cross-validation — ISRO SAR vs our Sentinel-1 products

**Status: PRE-DECLARED (protocol, modes, and acceptance bands written and
committed BEFORE any EOS-04 scene is downloaded or compared). Actuals appended
in a later commit once data is in hand.**

## Why

Every SAR product in Sailaab descends from Sentinel-1. EOS-04 is ISRO's C-band
(5.4 GHz) radar — a genuinely independent *sensor and agency* with compatible
physics: our water-detection thresholds transfer. NRSC's own NDEM 2025 Punjab
flood sheets were produced from RISAT-1A MRS acquisitions spanning
**16 Aug – 17 Sep 2025** (see `docs/notes/gov-data.md` §3, validation-recon §1),
which brackets our flood window — so coverage exists. A pixel-level comparison
against L2B terrain-normalised ARD that *we* process ourselves upgrades the
existing visual NDEM cross-check to a quantitative, reproducible one — and
de-risks single-constellation reliance (roadmap item, now executed).

## Access (documented, not yet exercised)

Bhoonidhi (bhoonidhi.nrsc.gov.in): free self-service registration (email +
mobile OTP, user type "Academic"). EOS-04 **L2B Terrain-Normalized ARD**
(CEOS-ARD/RTC GeoTIFF) for **MRS (~18–25 m)** and **CRS (~50 m)** is
`OpenData_DirectDownload` — free, immediate. NDEM's 2025 products used
**descending** passes (`…dsc…` naming); prefer descending L2B scenes to match.
Scene enumeration requires login; the bulk STAC API additionally requires IP
whitelisting by mail — the portal cart path needs neither.

Scenes land in `data/eos04/` (gitignored; `data/eos04/README.md` carries the
recipe). Nothing here goes in the repo except derived CSVs/figures.

## Pre-declared protocol

1. **Grid**: reproject/resample EOS-04 L2B gamma0 to our 90 m statewide grid
   (nearest for masks, average for backscatter), Punjab bbox
   73.85–76.95 E / 29.53–32.60 N.
2. **Water detection — two modes, declared up front**:
   - *change mode* (preferred, needs a pre-monsoon EOS-04 scene of the same
     orbit/mode): dVV < −3 dB AND VV_flood < −15 dB — the exact Tier-A rule.
   - *single-date mode* (fallback when no usable EOS-04 pre-scene exists):
     VV_flood < −15 dB with permanent/reference water removed. The mode used is
     stated on every output row; single-date is expected to over-detect
     permanent-dark surfaces and is compared accordingly.
3. **Comparison targets**: our committed Tier-A 2025 flood mask and the RF map
   (local rasters), over co-valid pixels only (both sensors observing).
4. **Aggregation**: statewide + per-district (Census-2011 polygons)
   TP/FP/FN/TN → OA, precision, recall, F1, IoU. Per-scene rows AND a
   flood-window union row.
5. **Date honesty**: EOS-04 acquisition dates will not equal S1 pass dates.
   Every row carries both dates and the day offset; recession bias
   (S2-truth-style) is expected for late scenes and stated, not hidden.

## Pre-declared acceptance bands

| Quantity | Band | Rationale |
|---|---|---|
| Overall accuracy (co-valid, statewide) | ≥ 0.90 | water is rare; OA is dominated by dry land |
| Flood-class F1, EOS-04 vs Tier-A, union | 0.30 – 0.75 | cross-sensor, cross-date; RF-vs-GFM fresh-point F1 was 0.394 |
| Direction check | EOS-04 flood fraction correlates positively with our district ranking (Spearman ρ > 0.4) | the flood is real; any sensor should rank Firozpur/Gurdaspur high |
| Coverage | ≥ 5 districts with co-valid flood pixels | else the comparison is anecdote, recorded as such |

Below-band or failed checks ship verbatim (house rule). If **no** flood-window
EOS-04 scene is downloadable, that outcome is recorded and the roadmap claim
reverts to "documented access path" — no synthetic substitute.

## Implementation (built ahead of data — TDD on synthetic rasters)

Pure logic in `sailaab/eos04.py` (numpy only: dB conversion with floor, both
water-mask modes, confusion/agreement metrics, per-district aggregation over a
label raster), tests in `tests/test_eos04.py` with exact-count synthetic cases.
Driver `pipeline/compare_eos04.py`: reads `data/eos04/*.tif` + local Tier-A/RF
rasters, writes `data/eos04_agreement.csv` + `atlas/eos04_compare.png`;
deterministic, no network; a missing-inputs run exits with the download recipe
instead of a traceback.

---

(Actuals appended below in a later commit, once scenes are downloaded.)
