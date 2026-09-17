# Verification report

Rendered from `outputs/verification/` (results.json, peak_tests.csv). Regenerate with `punjabflood verify` then `punjabflood report`.

## Inflow model parameters

Fitted by non-negative least squares on day-to-day changes of measured storage (CWC table, or the CWC level through the dam's own rating) against lagged catchment rain volumes; spilling days and implausible jumps excluded. The recession is the lag-2 to lag-1 autocovariance ratio of the residuals, clipped to [0.50, 0.99]; a raw ratio above the clip means the residual drifts through the season (base flow and outflow both move slowly) rather than recessing, so the base is carried as nearly constant over the horizon.

| dam | area used (km2) | runoff coefficient c (dry) | c_wet per 100 mm antecedent | lag weights w0..w3 | recession (raw ratio) | gamma | R2 | RMSE (BCM/day) | days | wetness carrier |
|---|---|---|---|---|---|---|---|---|---|---|
| Bhakra | 25,762 | 0.170 | 0.250 | 0.54, 0.27, 0.10, 0.09 | 0.990 (1.856) | 0.00 | 0.212 | 0.0434 | 1009 | api |
| Pong | 13,637 | 0.203 | 0.328 | 0.35, 0.48, 0.09, 0.08 | 0.990 (1.051) | 0.00 | 0.777 | 0.0296 | 733 | api |
| Ranjit Sagar | 6,953 | 0.131 | 0.263 | 0.62, 0.24, 0.08, 0.05 | 0.990 (2.219) | 0.00 | 0.398 | 0.0224 | 1184 | api |
The coefficient in force on a day is c plus c_wet times the previous five days' catchment rain over 100 mm, capped at 0.95, times one plus gamma times the ERA5-Land 0-7 cm soil-moisture anomaly (fractional, against a 31-day day-of-year climatology) where the wetness carrier includes soil moisture (`api+sm` or `sm`; gamma is zero under `api`).

## Annual peak class, 38 years (1988 to 2025)

For each WRD peak table, the predictors ranked by area under the ROC curve for the department's High class. Spearman rho is against the peak discharge itself; the Brier skill score compares leave-one-year-out logistic probabilities with the climatological base rate (positive is skill).

### dhilwan

| predictor | years | High years | Spearman rho | AUROC (High) | Brier skill |
|---|---|---|---|---|---|
| Ranjit Sagar_frac_aug01 | 10 | 1 | +0.71 | 1.00 | -0.04 |
| Pong_hei_pp_max | 11 | 2 | +0.75 | 1.00 | +0.45 |
| Pong_release_pp_max | 11 | 2 | +0.62 | 1.00 | +0.84 |
| Pong_days_above_95pct | 11 | 2 | +0.62 | 1.00 | +0.54 |
| Pong_frac_aug01 | 10 | 1 | +0.48 | 1.00 | -0.04 |
| Ranjit Sagar_max10d_bcm | 38 | 5 | +0.36 | 0.99 | +0.62 |
| Ranjit Sagar_max5d_bcm | 38 | 5 | +0.33 | 0.98 | +0.49 |
| Beas local_season_bcm | 38 | 5 | +0.51 | 0.98 | +0.36 |
| Ranjit Sagar_max3d_bcm | 38 | 5 | +0.34 | 0.96 | +0.45 |
| Sutlej local_season_bcm | 38 | 5 | +0.62 | 0.96 | +0.42 |

Other pre-named predictors:

| predictor | years | High years | Spearman rho | AUROC (High) | Brier skill |
|---|---|---|---|---|---|
| Pong_frac_aug15 | 11 | 2 | +0.93 | 0.94 | +0.18 |
| Bhakra_hei_pp_max | 11 | 2 | +0.69 | 0.89 | +0.05 |
| Pong_max3d_bcm | 38 | 5 | +0.40 | 0.87 | +0.26 |
| Pong_max5d_bcm | 38 | 5 | +0.44 | 0.87 | +0.22 |
| sutlej_beas_max5d_bcm | 38 | 5 | +0.48 | 0.86 | +0.10 |
| Bhakra_frac_aug15 | 11 | 2 | +0.64 | 0.83 | +0.01 |
| Bhakra_max5d_bcm | 38 | 5 | +0.37 | 0.83 | -0.10 |
| sutlej_beas_max3d_bcm | 38 | 5 | +0.42 | 0.82 | +0.06 |

### harike_hussainiwala

| predictor | years | High years | Spearman rho | AUROC (High) | Brier skill |
|---|---|---|---|---|---|
| Ranjit Sagar_frac_aug01 | 10 | 1 | +0.73 | 1.00 | -0.04 |
| Pong_hei_pp_max | 11 | 2 | +0.88 | 1.00 | +0.45 |
| Pong_release_pp_max | 11 | 2 | +0.68 | 1.00 | +0.84 |
| Pong_days_above_95pct | 11 | 2 | +0.68 | 1.00 | +0.54 |
| Pong_frac_aug01 | 10 | 1 | +0.49 | 1.00 | -0.04 |
| Ranjit Sagar_max10d_bcm | 38 | 5 | +0.62 | 0.99 | +0.62 |
| Ranjit Sagar_max5d_bcm | 38 | 5 | +0.56 | 0.98 | +0.49 |
| Beas local_season_bcm | 38 | 5 | +0.67 | 0.98 | +0.36 |
| Ranjit Sagar_max3d_bcm | 38 | 5 | +0.57 | 0.96 | +0.45 |
| Sutlej local_season_bcm | 38 | 5 | +0.83 | 0.96 | +0.42 |

Other pre-named predictors:

| predictor | years | High years | Spearman rho | AUROC (High) | Brier skill |
|---|---|---|---|---|---|
| Pong_frac_aug15 | 11 | 2 | +0.75 | 0.94 | +0.18 |
| Bhakra_hei_pp_max | 11 | 2 | +0.84 | 0.89 | +0.05 |
| Pong_max3d_bcm | 38 | 5 | +0.47 | 0.87 | +0.26 |
| Pong_max5d_bcm | 38 | 5 | +0.57 | 0.87 | +0.22 |
| sutlej_beas_max5d_bcm | 38 | 5 | +0.64 | 0.86 | +0.10 |
| Bhakra_frac_aug15 | 11 | 2 | +0.67 | 0.83 | +0.01 |
| Bhakra_max5d_bcm | 38 | 5 | +0.53 | 0.83 | -0.10 |
| sutlej_beas_max3d_bcm | 38 | 5 | +0.60 | 0.82 | +0.06 |

### ropar

| predictor | years | High years | Spearman rho | AUROC (High) | Brier skill |
|---|---|---|---|---|---|
| Ranjit Sagar_frac_aug01 | 10 | 1 | +0.56 | 1.00 | -0.04 |
| Pong_hei_pp_max | 11 | 2 | +0.69 | 1.00 | +0.45 |
| Pong_release_pp_max | 11 | 2 | +0.57 | 1.00 | +0.84 |
| Pong_days_above_95pct | 11 | 2 | +0.57 | 1.00 | +0.54 |
| Pong_frac_aug01 | 10 | 1 | +0.56 | 1.00 | -0.04 |
| Ranjit Sagar_max10d_bcm | 38 | 5 | +0.52 | 0.99 | +0.62 |
| Ranjit Sagar_max5d_bcm | 38 | 5 | +0.49 | 0.98 | +0.49 |
| Beas local_season_bcm | 38 | 5 | +0.62 | 0.98 | +0.36 |
| Ranjit Sagar_max3d_bcm | 38 | 5 | +0.49 | 0.96 | +0.45 |
| Sutlej local_season_bcm | 38 | 5 | +0.67 | 0.96 | +0.42 |

Other pre-named predictors:

| predictor | years | High years | Spearman rho | AUROC (High) | Brier skill |
|---|---|---|---|---|---|
| Pong_frac_aug15 | 11 | 2 | +0.59 | 0.94 | +0.18 |
| Bhakra_hei_pp_max | 11 | 2 | +0.68 | 0.89 | +0.05 |
| Pong_max3d_bcm | 38 | 5 | +0.31 | 0.87 | +0.26 |
| Pong_max5d_bcm | 38 | 5 | +0.40 | 0.87 | +0.22 |
| sutlej_beas_max5d_bcm | 38 | 5 | +0.52 | 0.86 | +0.10 |
| Bhakra_frac_aug15 | 11 | 2 | +0.65 | 0.83 | +0.01 |
| Bhakra_max5d_bcm | 38 | 5 | +0.49 | 0.83 | -0.10 |
| sutlej_beas_max3d_bcm | 38 | 5 | +0.48 | 0.82 | +0.06 |

## Event timing: routed perfect-prognosis release versus the dated Dhilwan peaks

The forced release of a full Pong reservoir under the observed rain (one-day-ahead spill of each day's run, placed on the day it happens) is routed to Dhilwan with the Annexure Z travel times and compared with the department's dated peak. The river release on a spill day is the spill plus the turbine passage less the Mukerian Hydel Channel's capacity (a full reservoir passes its inflow, so the turbines run); this is the lower bound on what the dam sends down the Beas, and the spill-only row below it is the lower bound of that. The rows with the local term add the runoff of the land between Pong and Dhilwan (the Beas local catchment, the HydroBASINS sub-basins that drain to Dhilwan below the dam) from its own IMD rain, with a dam's calibrated response transferred because no gauge exists to fit one on: Pong's response as the primary, Ranjit Sagar's (the lowest fitted coefficient) as the sensitivity; no base flow, so the term is a lower bound, and it arrives on the day it runs off. The storage that drives the index comes from the public record, which is weekly in August 2023 and a handful of press points in August 2025; between measurements the reservoir is carried by the model's own water balance under the observed rain (one-day inflow less the non-spill passage), and every measurement re-anchors it.

| year | release routed | predicted peak date | predicted peak (cusecs) | observed peak date | observed peak (cusecs) | lag (days) | magnitude ratio |
|---|---|---|---|---|---|---|---|
| 2023 | spill + passage | 2023-08-17 | 181,686 | 2023-08-17 | 237,500 | +0 | 0.76 |
| 2025 | spill + passage | 2025-08-28 | 173,501 | 2025-08-31 | 235,494 | -3 | 0.74 |
| 2023 | spill only | 2023-08-17 | 147,586 | 2023-08-17 | 237,500 | +0 | 0.62 |
| 2025 | spill only | 2025-08-28 | 139,401 | 2025-08-31 | 235,494 | -3 | 0.59 |
| 2023 | spill + passage + local inflow, Pong response | 2023-08-17 | 186,401 | 2023-08-17 | 237,500 | +0 | 0.78 |
| 2025 | spill + passage + local inflow, Pong response | 2025-08-28 | 200,816 | 2025-08-31 | 235,494 | -3 | 0.85 |
| 2023 | spill + passage + local inflow, Ranjit Sagar response | 2023-08-17 | 184,154 | 2023-08-17 | 237,500 | +0 | 0.78 |
| 2025 | spill + passage + local inflow, Ranjit Sagar response | 2025-08-28 | 189,045 | 2025-08-31 | 235,494 | -3 | 0.80 |

Local inflow at Dhilwan on the department's peak days (Pong response transferred; the routed dam release is the spill-plus-passage row above):

| year | observed peak date | local inflow that day (cusecs) | share of the observed peak | largest within 3 days (cusecs, date) | routed dam release that day (cusecs) | dam plus local, ratio to observed |
|---|---|---|---|---|---|---|
| 2023 | 2023-08-17 | 4,715 | 0.02 | 20,266 (2023-08-15) | 181,686 | 0.78 |
| 2025 | 2025-08-31 | 16,813 | 0.07 | 33,891 (2025-09-03) | 114,036 | 0.56 |

Storage basis of the Pong path in August of each event year (days):

| year | measured (CWC) | CWC level through the rating | press report | carried by the model | interpolated |
|---|---|---|---|---|---|
| 2023 | 4 | 1 | 0 | 26 | 0 |
| 2025 | 0 | 0 | 4 | 22 | 0 |

### Flood-scale inflow: the model against the figures the record holds

The runoff coefficient is fitted on ordinary filling days (the storage-change relation), so what the model does at flood scale has to be checked against whatever flood-scale inflow the public record holds: BBMB's daily sheets where the Internet Archive kept them, dated press figures credited to the dam offices, the period means of BBMB inflow that the Public Action Committee compiled for August to early September 2025, the season's largest inflows as stated to the Rajya Sabha, and the record inflow in the Pong emergency action plan. Each is set against the model's one-day inflow under observed rain (the perfect-prognosis run with its base-flow stand-in) on the same day or days: a period mean against the model's mean over the same days, a season peak against the model's largest day of the same June to September. A period mean is a daily quantity like the model's; the season peaks, the dated press figures and the sheets' figures are readings at a time of day, so against a daily volume those ratios are lower bounds on the model's share of the day's mean. The full citations are in `data-sources.md` and the reference tables.

| dam | figure | model days | reported (cusecs) | model (cusecs) | model / reported | source |
|---|---|---|---|---|---|---|
| Bhakra | mean, 2025-08-01 to 2025-08-24 | 24 | 57,430 | 55,913 | 0.97 | PAC data via The Wire, 8 Sep 2025 |
| Bhakra | mean, 2025-08-25 to 2025-09-04 | 11 | 73,400 | 81,542 | 1.11 | PAC data via The Wire, 8 Sep 2025 |
| Pong | mean, 2025-08-01 to 2025-08-24 | 19 | 77,000 | 83,012 | 1.08 | PAC data via The Wire, 8 Sep 2025 |
| Pong | mean, 2025-08-25 to 2025-09-04 | 11 | 121,600 | 137,283 | 1.13 | PAC data via The Wire, 8 Sep 2025 |
| Ranjit Sagar | mean, 2025-08-01 to 2025-08-24 | 20 | 38,700 | 30,075 | 0.78 | PAC data via The Wire, 8 Sep 2025 |
| Ranjit Sagar | mean, 2025-08-25 to 2025-09-04 | 11 | 71,960 | 69,098 | 0.96 | PAC data via The Wire, 8 Sep 2025 |
| Bhakra | day, 2023-08-14 | 1 | 193,324 | 91,025 | 0.47 | BBMB via Himachal Tonite, Aug 2023 |
| Bhakra | day, 2023-08-15 | 1 | 85,899 | 86,995 | 1.01 | The Tribune, 15 Aug 2023 |
| Bhakra | day, 2023-08-22 | 1 | 105,000 | 39,112 | 0.37 | The Tribune, 23 Aug 2023 (Tuesday) |
| Bhakra | day, 2023-08-22 | 1 | 72,835 | 39,112 | 0.54 | The Tribune, 24 Aug 2023 (yesterday) |
| Pong | day, 2023-08-22 | 1 | 58,702 | 46,948 | 0.80 | The Tribune, 24 Aug 2023 (yesterday) |
| Bhakra | day, 2023-08-23 | 1 | 128,000 | 60,147 | 0.47 | The Tribune, 23 Aug 2023 (Wednesday) |
| Bhakra | day, 2023-08-23 | 1 | 128,406 | 60,147 | 0.47 | The Tribune, 24 Aug 2023 |
| Pong | day, 2023-08-23 | 1 | 158,000 | 68,465 | 0.43 | The Tribune, 23 Aug 2023 (Wednesday) |
| Pong | day, 2023-08-23 | 1 | 138,674 | 68,465 | 0.49 | The Tribune, 24 Aug 2023 |
| Bhakra | day, 2023-08-25 | 1 | 52,810 | 57,026 | 1.08 | Rozana Spokesman, 25 Aug 2023 |
| Pong | day, 2025-08-02 | 0 | 87,586 | n/a | n/a | The Tribune, 2 Aug 2025 |
| Bhakra | day, 2025-08-06 | 1 | 59,200 | 82,043 | 1.39 | Babushahi, 6 Aug 2025 |
| Pong | day, 2025-08-06 | 0 | 93,650 | n/a | n/a | Babushahi, 6 Aug 2025 |
| Pong | day, 2025-08-17 | 1 | 109,789 | 116,417 | 1.06 | The Tribune, 17 Aug 2025 |
| Bhakra | day, 2025-08-19 | 1 | 65,617 | 50,860 | 0.78 | Babushahi, 19 Aug 2025 |
| Pong | day, 2025-08-25 | 1 | 146,174 | 104,157 | 0.71 | Diary Times, 25 Aug 2025 |
| Pong | day, 2025-08-26 | 1 | 233,000 | 175,210 | 0.75 | PTI via The Week, 26 Aug 2025 (about) |
| Bhakra | day, 2025-08-27 | 1 | 58,997 | 62,325 | 1.06 | The Tribune, 28 Aug 2026 (same date last year) |
| Pong | day, 2025-08-27 | 1 | 228,091 | 203,537 | 0.89 | The Tribune, 28 Aug 2026 (same date last year) |
| Ranjit Sagar | day, 2025-08-27 | 1 | 163,037 | 109,546 | 0.67 | The Tribune, 28 Aug 2026 (same date last year) |
| Pong | day, 2025-08-31 | 1 | 160,276 | 121,294 | 0.76 | The Tribune, 31 Aug 2025 |
| Pong | day, 2025-09-04 | 1 | 107,301 | 147,004 | 1.37 | The Tribune, 4 Sep 2025 (actual inflow) |
| Bhakra | day, 2025-09-05 | 1 | 76,318 | 67,120 | 0.88 | SDO Nangal via Babushahi, 5 Sep 2025 |
| Pong | day, 2025-09-05 | 1 | 105,950 | 113,008 | 1.07 | The Tribune, 6 Sep 2025 (yesterday) |
| Bhakra | day, 2025-09-06 | 1 | 62,481 | 56,139 | 0.90 | The Tribune, 6 Sep 2025 |
| Pong | day, 2025-09-06 | 1 | 98,418 | 75,537 | 0.77 | The Tribune, 6 Sep 2025 |
| Bhakra | day, 2025-09-15 | 1 | 54,667 | 44,853 | 0.82 | BBMB daily sheet, Internet Archive |
| Bhakra | day, 2025-09-24 | 1 | 35,666 | 35,817 | 1.00 | BBMB daily sheet, Internet Archive |
| Pong | day, 2025-09-15 | 1 | 76,498 | 83,124 | 1.09 | BBMB daily sheet, Internet Archive |
| Pong | day, 2025-09-24 | 1 | 17,291 | 40,090 | 2.32 | BBMB daily sheet, Internet Archive |
| Pong | record day, 2023-08-14 | 1 | 734,000 | 233,281 | 0.32 | BBMB Pong EAP, largest inflow recorded |
| Pong | largest day of 2025 | 112 | 349,522 | 203,537 | 0.58 | Rajya Sabha reply via PTI, 2 Dec 2025 |
| Bhakra | largest day of 2025 | 121 | 190,603 | 108,620 | 0.57 | Rajya Sabha reply via PTI, 2 Dec 2025 |

Dated figures by year (readings at a time of day against the model's daily volume; 2023: 11 dated figures, the model at 0.32 to 1.08 of the reading, median 0.47; 2025: 18 dated figures, the model at 0.67 to 2.32 of the reading, median 0.90).

Where the run covers at least 10 of a period's days, the model's mean is 0.78 to 1.13 of the reported mean; its largest day of the season is 0.57 to 0.58 of the stated peak. The flood's volume is close to right and its peak day is not: the model spreads the volume over more days than the river does, which is consistent with lag weights fitted on ordinary days.

### Response variants, tested out of sample

Each variant is fitted on the same storage record beside the response in use and scored leave-one-season-out (each season by a fit on the others). Rain above the heavy-day threshold in a catchment day gets its own coefficient and lag weights (the threshold-excess variant). The soil-moisture variants change the carrier of catchment wetness: `api+sm` keeps the five-day rain index and adds the ERA5-Land 0-7 cm soil-moisture anomaly through gamma; `sm` drops the rain index and keeps the anomaly alone (each fold's climatology leaves the held-out season out). The rule before any variant can replace the response the product uses: the held-out error may not rise at any dam, the season-peak ratios of the flood-scale table must rise, and the period means may not move further from the reported means than the baseline's worst one does. Heavy-day bias is observed minus predicted storage change, positive when heavy days are under-predicted.

| dam | variant | seasons | days | held-out RMSE (BCM/day) | heavy days | heavy-day RMSE (BCM/day) | heavy-day bias (BCM/day) | c | c_wet | w | c_excess | w_excess | wetness | gamma |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Bhakra | baseline | 11 | 1009 | 0.0439 | 2 | 0.1013 | -0.0908 | 0.170 | 0.250 | 0.54 0.27 0.10 0.09 | 0.000 | none | api | 0.00 |
| Bhakra | excess above 30 mm | 11 | 1009 | 0.0668 | 2 | 0.0923 | -0.0773 | 0.194 | 0.207 | 0.55 0.21 0.12 0.12 | 0.303 | 0.00 1.00 0.00 0.00 | api | 0.00 |
| Bhakra | api+sm | 11 | 1009 | 0.0440 | 2 | 0.0961 | -0.0866 | 0.170 | 0.250 | 0.54 0.27 0.10 0.09 | 0.000 | none | api+sm | -0.14 |
| Bhakra | sm | 11 | 1009 | 0.0436 | 2 | 0.0691 | -0.0530 | 0.278 | 0.000 | 0.27 0.36 0.18 0.19 | 0.000 | none | sm | 0.15 |
| Pong | baseline | 8 | 733 | 0.0302 | 28 | 0.0782 | -0.0158 | 0.203 | 0.328 | 0.35 0.48 0.09 0.08 | 0.000 | none | api | 0.00 |
| Pong | excess above 30 mm | 8 | 733 | 0.0304 | 28 | 0.0773 | -0.0129 | 0.200 | 0.332 | 0.40 0.39 0.11 0.10 | 0.523 | 0.20 0.65 0.09 0.06 | api | 0.00 |
| Pong | api+sm | 8 | 733 | 0.0300 | 28 | 0.0772 | -0.0059 | 0.203 | 0.328 | 0.35 0.48 0.09 0.08 | 0.000 | none | api+sm | -0.36 |
| Pong | sm | 8 | 733 | 0.0334 | 28 | 0.0860 | +0.0101 | 0.509 | 0.000 | 0.21 0.52 0.15 0.13 | 0.000 | none | sm | -0.25 |
| Ranjit Sagar | baseline | 11 | 1184 | 0.0229 | 29 | 0.0442 | -0.0113 | 0.131 | 0.263 | 0.62 0.24 0.08 0.05 | 0.000 | none | api | 0.00 |
| Ranjit Sagar | excess above 30 mm | 11 | 1184 | 0.0229 | 29 | 0.0469 | -0.0074 | 0.156 | 0.166 | 0.47 0.27 0.15 0.11 | 0.469 | 0.46 0.48 0.00 0.07 | api | 0.00 |
| Ranjit Sagar | api+sm | 11 | 1184 | 0.0230 | 29 | 0.0384 | -0.0168 | 0.131 | 0.263 | 0.62 0.24 0.08 0.05 | 0.000 | none | api+sm | 0.26 |
| Ranjit Sagar | sm | 11 | 1184 | 0.0230 | 29 | 0.0471 | -0.0101 | 0.341 | 0.000 | 0.34 0.45 0.11 0.10 | 0.000 | none | sm | 1.30 |

| variant | period means covered | worst deviation of a period mean from 1 | season-peak ratio, smallest | season-peak ratio, largest |
|---|---|---|---|---|
| baseline | 6 | 0.22 | 0.57 | 0.58 |
| excess above 30 mm | 6 | 0.26 | 0.55 | 0.58 |
| api+sm | 6 | 0.22 | 0.54 | 0.57 |
| sm | 6 | 0.26 | 0.46 | 0.50 |

Verdict on 'excess above 30 mm', not adopted. Conditions: the held-out error does not rise at any dam (fails); the season peaks rise (fails); the period means hold (fails).

Verdict on 'api+sm', not adopted. Conditions: the held-out error does not rise at any dam (fails); the season peaks rise (fails); the period means hold (passes).

Verdict on 'sm', not adopted. Conditions: the held-out error does not rise at any dam (fails); the season peaks rise (fails); the period means hold (fails).

## As-issued hindcast: what the product would have said, each dam, 2024 to 2026

For each issue date the recorded or model-carried storage and the rain forecast actually issued that day (archived lead 1 to 5 QPF, deterministic) go through the same water balance as the live product. A flagged day is an issue date whose forecast forces the spillway within five days. BBMB's gate log is not public, so the model's own run under observed rain (perfect prognosis) is the reference: a flag is a hit when that run also forces the spillway within five days of the same issue date, a false flag otherwise, and a perfect-prognosis flag without an as-issued flag is a miss. The first hit is the warning; the lead is counted from it to the model's first spill under observed rain and to the dated Dhilwan peak. The window is 1 August to 15 September.

| year | dam | model | issue days | flagged (hits, false) | missed | first flag of any kind | first hit (issue date, spill on day) | earliest possible flag (observed rain) | first spill under observed rain | lead (days) | observed Dhilwan peak (Pong only) | lead (days) | largest forecast peak release (cusecs) | perfect-prognosis peak release (cusecs) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2024 | Pong | ecmwf_aifs025_single | 0 | 0 (0 hits, 0 false) | 0 | none | none | none | none | n/a | 2024-08-12 | n/a | nan | 0 |
| 2024 | Pong | ecmwf_ifs025 | 46 | 0 (0 hits, 0 false) | 0 | none | none | none | none | n/a | 2024-08-12 | n/a | 0 | 0 |
| 2024 | Pong | gfs_seamless | 46 | 0 (0 hits, 0 false) | 0 | none | none | none | none | n/a | 2024-08-12 | n/a | 0 | 0 |
| 2025 | Pong | ecmwf_aifs025_single | 41 | 23 (23 hits, 0 false) | 6 | 2025-08-17 | 2025-08-17, day 3 | 2025-08-14 | 2025-08-27 | +10 | 2025-08-31 | +14 | 133,607 | 139,401 |
| 2025 | Pong | ecmwf_ifs025 | 41 | 25 (25 hits, 0 false) | 4 | 2025-08-15 | 2025-08-15, day 5 | 2025-08-14 | 2025-08-27 | +12 | 2025-08-31 | +16 | 173,377 | 139,401 |
| 2025 | Pong | gfs_seamless | 41 | 23 (23 hits, 0 false) | 6 | 2025-08-17 | 2025-08-17, day 4 | 2025-08-14 | 2025-08-27 | +10 | 2025-08-31 | +14 | 120,955 | 139,401 |
| 2026 | Pong | ecmwf_aifs025_single | 42 | 0 (0 hits, 0 false) | 0 | none | none | none | none | n/a | none | n/a | 0 | 0 |
| 2026 | Pong | ecmwf_ifs025 | 42 | 0 (0 hits, 0 false) | 0 | none | none | none | none | n/a | none | n/a | 0 | 0 |
| 2026 | Pong | gfs_seamless | 42 | 0 (0 hits, 0 false) | 0 | none | none | none | none | n/a | none | n/a | 0 | 0 |
| 2024 | Pong | ecmwf_aifs025_single | 0 | 0 (0 hits, 0 false) | 0 | none | none | none | none | n/a | none | n/a | nan | 0 |
| 2024 | Bhakra | ecmwf_ifs025 | 46 | 0 (0 hits, 0 false) | 0 | none | none | none | none | n/a | none | n/a | 0 | 0 |
| 2024 | Bhakra | gfs_seamless | 46 | 0 (0 hits, 0 false) | 0 | none | none | none | none | n/a | none | n/a | 0 | 0 |
| 2025 | Bhakra | ecmwf_aifs025_single | 46 | 3 (3 hits, 0 false) | 1 | 2025-08-30 | 2025-08-30, day 4 | 2025-08-29 | none | n/a | none | n/a | 67,585 | 0 |
| 2025 | Bhakra | ecmwf_ifs025 | 46 | 3 (3 hits, 0 false) | 1 | 2025-08-30 | 2025-08-30, day 4 | 2025-08-29 | none | n/a | none | n/a | 35,473 | 0 |
| 2025 | Bhakra | gfs_seamless | 46 | 1 (1 hits, 0 false) | 3 | 2025-09-01 | 2025-09-01, day 2 | 2025-08-29 | none | n/a | none | n/a | 48,966 | 0 |
| 2026 | Bhakra | ecmwf_aifs025_single | 42 | 0 (0 hits, 0 false) | 0 | none | none | none | none | n/a | none | n/a | 0 | 0 |
| 2026 | Bhakra | ecmwf_ifs025 | 42 | 0 (0 hits, 0 false) | 0 | none | none | none | none | n/a | none | n/a | 0 | 0 |
| 2026 | Bhakra | gfs_seamless | 42 | 0 (0 hits, 0 false) | 0 | none | none | none | none | n/a | none | n/a | 0 | 0 |
| 2024 | Pong | ecmwf_aifs025_single | 0 | 0 (0 hits, 0 false) | 0 | none | none | none | none | n/a | none | n/a | nan | 0 |
| 2024 | Ranjit Sagar | ecmwf_ifs025 | 46 | 0 (0 hits, 0 false) | 0 | none | none | none | none | n/a | none | n/a | 0 | 0 |
| 2024 | Ranjit Sagar | gfs_seamless | 46 | 0 (0 hits, 0 false) | 0 | none | none | none | none | n/a | none | n/a | 0 | 0 |
| 2025 | Ranjit Sagar | ecmwf_aifs025_single | 42 | 13 (12 hits, 1 false) | 3 | 2025-08-26 | 2025-08-26, day 3 | 2025-08-23 | 2025-08-28 | +2 | none | n/a | 63,711 | 71,845 |
| 2025 | Ranjit Sagar | ecmwf_ifs025 | 42 | 13 (12 hits, 1 false) | 3 | 2025-08-26 | 2025-08-26, day 4 | 2025-08-23 | 2025-08-28 | +2 | none | n/a | 67,036 | 71,845 |
| 2025 | Ranjit Sagar | gfs_seamless | 42 | 13 (12 hits, 1 false) | 3 | 2025-08-26 | 2025-08-26, day 4 | 2025-08-23 | 2025-08-28 | +2 | none | n/a | 48,721 | 71,845 |

In 2025 the Pong run under observed rain flagged from 2025-08-14 while its spill came on 2025-08-27. Between the two, the measured storage of 2025-08-18 re-anchored the model's carried path downward by 0.82 BCM: the reservoir gained less than the water balance says, which is the dam passing more than its turbines, the inflow over-predicted, or both; the public record cannot separate them. The flags before that date were therefore calls of a spill unless water was released, which is what the index means, and the as-issued hits scored against them carry the same reading.

In 2025 the Bhakra run under observed rain flagged from 2025-08-29 and did not force the spillway within the window (to 2025-09-15). After the first flag, the measured storage of 2025-09-02 re-anchored the model's carried path downward by 0.61 BCM: the reservoir gained less than the water balance says, which is the dam passing more than its turbines, the inflow over-predicted, or both; the public record cannot separate them. The flags were therefore calls of a spill unless water was released, which is what the index means; the as-issued hits scored against them carry the same reading, and after the re-anchor the observed rain did not fill the reservoir before the window closed.

In 2025 the Ranjit Sagar run under observed rain flagged from 2025-08-23 while its spill came on 2025-08-28. Between the two, the measured storage of 2025-08-27 re-anchored the model's carried path downward by 0.06 BCM: the reservoir gained less than the water balance says, which is the dam passing more than its turbines, the inflow over-predicted, or both; the public record cannot separate them. The flags before that date were therefore calls of a spill unless water was released, which is what the index means, and the as-issued hits scored against them carry the same reading.

## Rain input check: ERA5 against the IMD grid over the event windows

ERA5 (0.25 degree reanalysis, through Open-Meteo) is the rain record the product uses for the current season, and the forecast models it ingests share its resolution and physics over these mountain catchments. The IMD gridded analysis is the observed record the model is calibrated on. A reanalysis that misses the rain of an event says the forecasts will too; the ratio column is the size of that miss over each event window.

| catchment | event | window | days | IMD total (mm) | ERA5 total (mm) | ERA5 / IMD | IMD wettest day (mm) | ERA5 that day (mm) |
|---|---|---|---|---|---|---|---|---|
| Bhakra | 2023 | 2023-08-06 to 2023-08-20 | 15 | 106 | 39 | 0.37 | 28 | 8 |
| Bhakra | 2025 | 2025-08-18 to 2025-09-06 | 20 | 197 | 167 | 0.85 | 28 | 32 |
| Pong | 2023 | 2023-08-06 to 2023-08-20 | 15 | 286 | 109 | 0.38 | 99 | 33 |
| Pong | 2025 | 2025-08-18 to 2025-09-06 | 20 | 425 | 359 | 0.85 | 64 | 31 |
| Ranjit Sagar | 2023 | 2023-08-06 to 2023-08-20 | 15 | 137 | 81 | 0.59 | 50 | 26 |
| Ranjit Sagar | 2025 | 2025-08-18 to 2025-09-06 | 20 | 473 | 446 | 0.94 | 85 | 76 |

## As-issued catchment QPF against observed catchment rain (2024 to 2026 seasons)

Heavy day: 30 mm or more over the catchment in a day. Lead 0 is the archive's stitched shortest-lead series.

| catchment | model | lead (days) | days | obs mean (mm) | bias | r | MAE (mm) | heavy days | hit rate | false-alarm ratio |
|---|---|---|---|---|---|---|---|---|---|---|
| Beas local | ecmwf_aifs025_single | 0 | 226 | 6.9 | +3% | 0.82 | 3.5 | 8 | 0.75 | 0.25 |
| Beas local | ecmwf_aifs025_single | 1 | 226 | 6.9 | +7% | 0.78 | 4.0 | 8 | 0.75 | 0.33 |
| Beas local | ecmwf_aifs025_single | 2 | 226 | 6.9 | +18% | 0.76 | 4.3 | 8 | 0.75 | 0.25 |
| Beas local | ecmwf_aifs025_single | 3 | 226 | 6.9 | +12% | 0.55 | 4.6 | 8 | 0.50 | 0.43 |
| Beas local | ecmwf_aifs025_single | 4 | 226 | 6.9 | +8% | 0.38 | 5.1 | 8 | 0.25 | 0.60 |
| Beas local | ecmwf_aifs025_single | 5 | 226 | 6.9 | +12% | 0.29 | 5.7 | 8 | 0.00 | 1.00 |
| Beas local | ecmwf_aifs025_single | 6 | 226 | 6.9 | +13% | 0.29 | 5.9 | 8 | 0.00 | 1.00 |
| Beas local | ecmwf_aifs025_single | 7 | 226 | 6.9 | +18% | 0.23 | 6.3 | 8 | 0.00 | 1.00 |
| Beas local | ecmwf_ifs025 | 0 | 104 | 4.6 | -2% | 0.99 | 0.5 | 1 | 1.00 | 0.00 |
| Beas local | ecmwf_ifs025 | 1 | 104 | 4.6 | +1% | 0.68 | 2.6 | 1 | 0.00 | n/a |
| Beas local | ecmwf_ifs025 | 2 | 104 | 4.6 | +22% | 0.70 | 3.1 | 1 | 1.00 | 0.50 |
| Beas local | ecmwf_ifs025 | 3 | 104 | 4.6 | +24% | 0.72 | 3.3 | 1 | 1.00 | 0.50 |
| Beas local | ecmwf_ifs025 | 4 | 104 | 4.6 | +27% | 0.69 | 3.2 | 1 | 1.00 | 0.50 |
| Beas local | ecmwf_ifs025 | 5 | 104 | 4.6 | +37% | 0.71 | 3.6 | 1 | 1.00 | 0.50 |
| Beas local | ecmwf_ifs025 | 6 | 104 | 4.6 | +49% | 0.79 | 3.8 | 1 | 1.00 | 0.50 |
| Beas local | ecmwf_ifs025 | 7 | 104 | 4.6 | +36% | 0.69 | 3.8 | 1 | 1.00 | 0.00 |
| Beas local | gfs_seamless | 0 | 104 | 4.6 | -33% | 0.74 | 2.6 | 1 | 1.00 | 0.00 |
| Beas local | gfs_seamless | 1 | 104 | 4.6 | -11% | 0.73 | 3.2 | 1 | 1.00 | 0.50 |
| Beas local | gfs_seamless | 2 | 104 | 4.6 | -3% | 0.72 | 2.9 | 1 | 1.00 | 0.00 |
| Beas local | gfs_seamless | 3 | 104 | 4.6 | +6% | 0.66 | 3.2 | 1 | 0.00 | n/a |
| Beas local | gfs_seamless | 4 | 104 | 4.6 | +27% | 0.42 | 4.7 | 1 | 0.00 | 1.00 |
| Beas local | gfs_seamless | 5 | 104 | 4.6 | +29% | 0.61 | 4.7 | 1 | 1.00 | 0.75 |
| Beas local | gfs_seamless | 6 | 104 | 4.6 | +1% | 0.64 | 3.4 | 1 | 1.00 | 0.50 |
| Beas local | gfs_seamless | 7 | 104 | 4.6 | -4% | 0.26 | 4.2 | 1 | 0.00 | n/a |
| Bhakra | ecmwf_aifs025_single | 0 | 226 | 4.5 | -13% | 0.78 | 1.7 | 0 | n/a | 1.00 |
| Bhakra | ecmwf_aifs025_single | 1 | 226 | 4.5 | -4% | 0.74 | 1.9 | 0 | n/a | 1.00 |
| Bhakra | ecmwf_aifs025_single | 2 | 226 | 4.5 | +4% | 0.65 | 2.1 | 0 | n/a | 1.00 |
| Bhakra | ecmwf_aifs025_single | 3 | 226 | 4.5 | +3% | 0.48 | 2.2 | 0 | n/a | 1.00 |
| Bhakra | ecmwf_aifs025_single | 4 | 226 | 4.5 | +2% | 0.43 | 2.4 | 0 | n/a | 1.00 |
| Bhakra | ecmwf_aifs025_single | 5 | 226 | 4.5 | +6% | 0.37 | 2.7 | 0 | n/a | 1.00 |
| Bhakra | ecmwf_aifs025_single | 6 | 226 | 4.5 | +8% | 0.47 | 2.7 | 0 | n/a | 1.00 |
| Bhakra | ecmwf_aifs025_single | 7 | 226 | 4.5 | +10% | 0.23 | 2.9 | 0 | n/a | 1.00 |
| Bhakra | ecmwf_ifs025 | 0 | 348 | 4.3 | -16% | 0.71 | 1.9 | 0 | n/a | 1.00 |
| Bhakra | ecmwf_ifs025 | 1 | 348 | 4.3 | -16% | 0.65 | 2.1 | 0 | n/a | n/a |
| Bhakra | ecmwf_ifs025 | 2 | 348 | 4.3 | -12% | 0.66 | 2.2 | 0 | n/a | 1.00 |
| Bhakra | ecmwf_ifs025 | 3 | 348 | 4.3 | -11% | 0.57 | 2.4 | 0 | n/a | n/a |
| Bhakra | ecmwf_ifs025 | 4 | 348 | 4.3 | -10% | 0.52 | 2.6 | 0 | n/a | 1.00 |
| Bhakra | ecmwf_ifs025 | 5 | 348 | 4.3 | -8% | 0.50 | 2.6 | 0 | n/a | n/a |
| Bhakra | ecmwf_ifs025 | 6 | 348 | 4.3 | -8% | 0.52 | 2.6 | 0 | n/a | n/a |
| Bhakra | ecmwf_ifs025 | 7 | 348 | 4.3 | +1% | 0.51 | 2.7 | 0 | n/a | 1.00 |
| Bhakra | gfs_seamless | 0 | 348 | 4.3 | +3% | 0.67 | 2.4 | 0 | n/a | 1.00 |
| Bhakra | gfs_seamless | 1 | 348 | 4.3 | -6% | 0.61 | 2.5 | 0 | n/a | 1.00 |
| Bhakra | gfs_seamless | 2 | 348 | 4.3 | -4% | 0.48 | 2.8 | 0 | n/a | n/a |
| Bhakra | gfs_seamless | 3 | 348 | 4.3 | +2% | 0.44 | 3.0 | 0 | n/a | n/a |
| Bhakra | gfs_seamless | 4 | 348 | 4.3 | +13% | 0.50 | 3.0 | 0 | n/a | 1.00 |
| Bhakra | gfs_seamless | 5 | 348 | 4.3 | -41% | 0.31 | 3.1 | 0 | n/a | n/a |
| Bhakra | gfs_seamless | 6 | 348 | 4.3 | -51% | 0.23 | 3.4 | 0 | n/a | n/a |
| Bhakra | gfs_seamless | 7 | 348 | 4.3 | -52% | 0.20 | 3.3 | 0 | n/a | n/a |
| Ghaggar Bhankarpur | ecmwf_aifs025_single | 0 | 226 | 6.2 | -6% | 0.65 | 4.1 | 9 | 0.33 | 0.25 |
| Ghaggar Bhankarpur | ecmwf_aifs025_single | 1 | 226 | 6.2 | +11% | 0.70 | 4.3 | 9 | 0.44 | 0.43 |
| Ghaggar Bhankarpur | ecmwf_aifs025_single | 2 | 226 | 6.2 | +28% | 0.62 | 5.1 | 9 | 0.44 | 0.33 |
| Ghaggar Bhankarpur | ecmwf_aifs025_single | 3 | 226 | 6.2 | +33% | 0.48 | 5.7 | 9 | 0.44 | 0.43 |
| Ghaggar Bhankarpur | ecmwf_aifs025_single | 4 | 226 | 6.2 | +34% | 0.34 | 6.2 | 9 | 0.33 | 0.57 |
| Ghaggar Bhankarpur | ecmwf_aifs025_single | 5 | 226 | 6.2 | +40% | 0.28 | 6.9 | 9 | 0.11 | 0.80 |
| Ghaggar Bhankarpur | ecmwf_aifs025_single | 6 | 226 | 6.2 | +43% | 0.35 | 6.9 | 9 | 0.22 | 0.71 |
| Ghaggar Bhankarpur | ecmwf_aifs025_single | 7 | 226 | 6.2 | +46% | 0.29 | 7.1 | 9 | 0.22 | 0.67 |
| Ghaggar Bhankarpur | ecmwf_ifs025 | 0 | 348 | 5.9 | -18% | 0.52 | 4.3 | 12 | 0.25 | 0.25 |
| Ghaggar Bhankarpur | ecmwf_ifs025 | 1 | 348 | 5.9 | +2% | 0.59 | 5.1 | 12 | 0.42 | 0.17 |
| Ghaggar Bhankarpur | ecmwf_ifs025 | 2 | 348 | 5.9 | +10% | 0.53 | 5.6 | 12 | 0.33 | 0.33 |
| Ghaggar Bhankarpur | ecmwf_ifs025 | 3 | 348 | 5.9 | +16% | 0.43 | 5.9 | 12 | 0.33 | 0.56 |
| Ghaggar Bhankarpur | ecmwf_ifs025 | 4 | 348 | 5.9 | +24% | 0.34 | 6.3 | 12 | 0.17 | 0.82 |
| Ghaggar Bhankarpur | ecmwf_ifs025 | 5 | 348 | 5.9 | +24% | 0.31 | 6.6 | 12 | 0.17 | 0.82 |
| Ghaggar Bhankarpur | ecmwf_ifs025 | 6 | 348 | 5.9 | +30% | 0.42 | 6.6 | 12 | 0.17 | 0.78 |
| Ghaggar Bhankarpur | ecmwf_ifs025 | 7 | 348 | 5.9 | +34% | 0.32 | 7.1 | 12 | 0.08 | 0.92 |
| Ghaggar Bhankarpur | gfs_seamless | 0 | 348 | 5.9 | -14% | 0.49 | 5.1 | 12 | 0.33 | 0.33 |
| Ghaggar Bhankarpur | gfs_seamless | 1 | 348 | 5.9 | -8% | 0.47 | 5.2 | 12 | 0.17 | 0.71 |
| Ghaggar Bhankarpur | gfs_seamless | 2 | 348 | 5.9 | +8% | 0.32 | 6.2 | 12 | 0.17 | 0.75 |
| Ghaggar Bhankarpur | gfs_seamless | 3 | 348 | 5.9 | +33% | 0.24 | 7.7 | 12 | 0.17 | 0.87 |
| Ghaggar Bhankarpur | gfs_seamless | 4 | 348 | 5.9 | +34% | 0.21 | 7.9 | 12 | 0.08 | 0.95 |
| Ghaggar Bhankarpur | gfs_seamless | 5 | 348 | 5.9 | -31% | 0.19 | 5.5 | 12 | 0.00 | 1.00 |
| Ghaggar Bhankarpur | gfs_seamless | 6 | 348 | 5.9 | -45% | 0.20 | 5.4 | 12 | 0.00 | 1.00 |
| Ghaggar Bhankarpur | gfs_seamless | 7 | 348 | 5.9 | -47% | 0.10 | 5.7 | 12 | 0.00 | 1.00 |
| Ghaggar Khanauri | ecmwf_aifs025_single | 0 | 226 | 5.8 | -3% | 0.72 | 3.3 | 6 | 0.33 | 0.33 |
| Ghaggar Khanauri | ecmwf_aifs025_single | 1 | 226 | 5.8 | +15% | 0.74 | 3.8 | 6 | 0.50 | 0.57 |
| Ghaggar Khanauri | ecmwf_aifs025_single | 2 | 226 | 5.8 | +33% | 0.67 | 4.5 | 6 | 0.50 | 0.57 |
| Ghaggar Khanauri | ecmwf_aifs025_single | 3 | 226 | 5.8 | +37% | 0.52 | 5.0 | 6 | 0.50 | 0.57 |
| Ghaggar Khanauri | ecmwf_aifs025_single | 4 | 226 | 5.8 | +39% | 0.38 | 5.6 | 6 | 0.50 | 0.57 |
| Ghaggar Khanauri | ecmwf_aifs025_single | 5 | 226 | 5.8 | +44% | 0.32 | 6.1 | 6 | 0.17 | 0.80 |
| Ghaggar Khanauri | ecmwf_aifs025_single | 6 | 226 | 5.8 | +48% | 0.33 | 6.3 | 6 | 0.33 | 0.71 |
| Ghaggar Khanauri | ecmwf_aifs025_single | 7 | 226 | 5.8 | +50% | 0.27 | 6.4 | 6 | 0.33 | 0.71 |
| Ghaggar Khanauri | ecmwf_ifs025 | 0 | 348 | 5.7 | -15% | 0.57 | 3.8 | 11 | 0.27 | 0.25 |
| Ghaggar Khanauri | ecmwf_ifs025 | 1 | 348 | 5.7 | +5% | 0.61 | 4.7 | 11 | 0.36 | 0.33 |
| Ghaggar Khanauri | ecmwf_ifs025 | 2 | 348 | 5.7 | +12% | 0.55 | 5.0 | 11 | 0.36 | 0.43 |
| Ghaggar Khanauri | ecmwf_ifs025 | 3 | 348 | 5.7 | +21% | 0.45 | 5.5 | 11 | 0.27 | 0.67 |
| Ghaggar Khanauri | ecmwf_ifs025 | 4 | 348 | 5.7 | +23% | 0.38 | 5.7 | 11 | 0.18 | 0.85 |
| Ghaggar Khanauri | ecmwf_ifs025 | 5 | 348 | 5.7 | +26% | 0.32 | 6.1 | 11 | 0.00 | 1.00 |
| Ghaggar Khanauri | ecmwf_ifs025 | 6 | 348 | 5.7 | +34% | 0.45 | 6.0 | 11 | 0.18 | 0.78 |
| Ghaggar Khanauri | ecmwf_ifs025 | 7 | 348 | 5.7 | +35% | 0.36 | 6.4 | 11 | 0.09 | 0.90 |
| Ghaggar Khanauri | gfs_seamless | 0 | 348 | 5.7 | -17% | 0.48 | 4.6 | 11 | 0.18 | 0.60 |
| Ghaggar Khanauri | gfs_seamless | 1 | 348 | 5.7 | -10% | 0.44 | 4.8 | 11 | 0.18 | 0.67 |
| Ghaggar Khanauri | gfs_seamless | 2 | 348 | 5.7 | +5% | 0.36 | 5.4 | 11 | 0.18 | 0.75 |
| Ghaggar Khanauri | gfs_seamless | 3 | 348 | 5.7 | +28% | 0.27 | 6.9 | 11 | 0.18 | 0.86 |
| Ghaggar Khanauri | gfs_seamless | 4 | 348 | 5.7 | +34% | 0.22 | 7.4 | 11 | 0.09 | 0.94 |
| Ghaggar Khanauri | gfs_seamless | 5 | 348 | 5.7 | -33% | 0.24 | 5.0 | 11 | 0.09 | 0.67 |
| Ghaggar Khanauri | gfs_seamless | 6 | 348 | 5.7 | -47% | 0.21 | 5.0 | 11 | 0.00 | 1.00 |
| Ghaggar Khanauri | gfs_seamless | 7 | 348 | 5.7 | -49% | 0.14 | 5.2 | 11 | 0.00 | n/a |
| Harike local | ecmwf_aifs025_single | 0 | 226 | 6.0 | -11% | 0.82 | 3.0 | 8 | 0.38 | 0.40 |
| Harike local | ecmwf_aifs025_single | 1 | 226 | 6.0 | +2% | 0.81 | 3.3 | 8 | 0.50 | 0.33 |
| Harike local | ecmwf_aifs025_single | 2 | 226 | 6.0 | +15% | 0.80 | 3.7 | 8 | 0.50 | 0.00 |
| Harike local | ecmwf_aifs025_single | 3 | 226 | 6.0 | +13% | 0.55 | 4.2 | 8 | 0.38 | 0.25 |
| Harike local | ecmwf_aifs025_single | 4 | 226 | 6.0 | +10% | 0.34 | 4.9 | 8 | 0.12 | 0.50 |
| Harike local | ecmwf_aifs025_single | 5 | 226 | 6.0 | +15% | 0.26 | 5.5 | 8 | 0.00 | 1.00 |
| Harike local | ecmwf_aifs025_single | 6 | 226 | 6.0 | +17% | 0.27 | 5.8 | 8 | 0.00 | 1.00 |
| Harike local | ecmwf_aifs025_single | 7 | 226 | 6.0 | +20% | 0.26 | 6.0 | 8 | 0.00 | 1.00 |
| Harike local | ecmwf_ifs025 | 0 | 104 | 3.6 | -0% | 0.99 | 0.3 | 0 | n/a | n/a |
| Harike local | ecmwf_ifs025 | 1 | 104 | 3.6 | +14% | 0.58 | 2.6 | 0 | n/a | n/a |
| Harike local | ecmwf_ifs025 | 2 | 104 | 3.6 | +32% | 0.59 | 2.9 | 0 | n/a | n/a |
| Harike local | ecmwf_ifs025 | 3 | 104 | 3.6 | +37% | 0.67 | 2.8 | 0 | n/a | n/a |
| Harike local | ecmwf_ifs025 | 4 | 104 | 3.6 | +43% | 0.61 | 3.2 | 0 | n/a | 1.00 |
| Harike local | ecmwf_ifs025 | 5 | 104 | 3.6 | +52% | 0.59 | 3.5 | 0 | n/a | n/a |
| Harike local | ecmwf_ifs025 | 6 | 104 | 3.6 | +59% | 0.62 | 3.7 | 0 | n/a | 1.00 |
| Harike local | ecmwf_ifs025 | 7 | 104 | 3.6 | +59% | 0.60 | 3.5 | 0 | n/a | 1.00 |
| Harike local | gfs_seamless | 0 | 104 | 3.6 | -42% | 0.56 | 2.4 | 0 | n/a | n/a |
| Harike local | gfs_seamless | 1 | 104 | 3.6 | -26% | 0.60 | 2.4 | 0 | n/a | n/a |
| Harike local | gfs_seamless | 2 | 104 | 3.6 | -0% | 0.66 | 2.7 | 0 | n/a | 1.00 |
| Harike local | gfs_seamless | 3 | 104 | 3.6 | +16% | 0.54 | 3.4 | 0 | n/a | 1.00 |
| Harike local | gfs_seamless | 4 | 104 | 3.6 | +34% | 0.54 | 3.6 | 0 | n/a | 1.00 |
| Harike local | gfs_seamless | 5 | 104 | 3.6 | +26% | 0.48 | 3.8 | 0 | n/a | 1.00 |
| Harike local | gfs_seamless | 6 | 104 | 3.6 | +7% | 0.43 | 3.3 | 0 | n/a | 1.00 |
| Harike local | gfs_seamless | 7 | 104 | 3.6 | +12% | 0.23 | 3.7 | 0 | n/a | n/a |
| Pong | ecmwf_aifs025_single | 0 | 226 | 9.5 | -12% | 0.72 | 4.1 | 15 | 0.40 | 0.45 |
| Pong | ecmwf_aifs025_single | 1 | 226 | 9.5 | -5% | 0.67 | 4.5 | 15 | 0.27 | 0.50 |
| Pong | ecmwf_aifs025_single | 2 | 226 | 9.5 | +3% | 0.63 | 4.7 | 15 | 0.47 | 0.30 |
| Pong | ecmwf_aifs025_single | 3 | 226 | 9.5 | +1% | 0.39 | 5.2 | 15 | 0.27 | 0.43 |
| Pong | ecmwf_aifs025_single | 4 | 226 | 9.5 | -2% | 0.31 | 5.6 | 15 | 0.00 | 1.00 |
| Pong | ecmwf_aifs025_single | 5 | 226 | 9.5 | +2% | 0.31 | 6.1 | 15 | 0.07 | 0.80 |
| Pong | ecmwf_aifs025_single | 6 | 226 | 9.5 | +4% | 0.34 | 6.4 | 15 | 0.07 | 0.67 |
| Pong | ecmwf_aifs025_single | 7 | 226 | 9.5 | +7% | 0.19 | 6.6 | 15 | 0.07 | 0.80 |
| Pong | ecmwf_ifs025 | 0 | 348 | 8.7 | -16% | 0.62 | 4.6 | 17 | 0.29 | 0.58 |
| Pong | ecmwf_ifs025 | 1 | 348 | 8.7 | -21% | 0.61 | 4.8 | 17 | 0.24 | 0.56 |
| Pong | ecmwf_ifs025 | 2 | 348 | 8.7 | -10% | 0.60 | 5.2 | 17 | 0.29 | 0.58 |
| Pong | ecmwf_ifs025 | 3 | 348 | 8.7 | -11% | 0.50 | 5.7 | 17 | 0.12 | 0.78 |
| Pong | ecmwf_ifs025 | 4 | 348 | 8.7 | -11% | 0.58 | 5.4 | 17 | 0.18 | 0.57 |
| Pong | ecmwf_ifs025 | 5 | 348 | 8.7 | -8% | 0.54 | 5.7 | 17 | 0.18 | 0.70 |
| Pong | ecmwf_ifs025 | 6 | 348 | 8.7 | -7% | 0.53 | 5.9 | 17 | 0.24 | 0.56 |
| Pong | ecmwf_ifs025 | 7 | 348 | 8.7 | -2% | 0.57 | 5.7 | 17 | 0.18 | 0.77 |
| Pong | gfs_seamless | 0 | 348 | 8.7 | -6% | 0.59 | 5.4 | 17 | 0.29 | 0.55 |
| Pong | gfs_seamless | 1 | 348 | 8.7 | -19% | 0.50 | 5.6 | 17 | 0.12 | 0.75 |
| Pong | gfs_seamless | 2 | 348 | 8.7 | -19% | 0.51 | 5.8 | 17 | 0.06 | 0.80 |
| Pong | gfs_seamless | 3 | 348 | 8.7 | -8% | 0.47 | 6.2 | 17 | 0.12 | 0.75 |
| Pong | gfs_seamless | 4 | 348 | 8.7 | +4% | 0.40 | 6.6 | 17 | 0.06 | 0.92 |
| Pong | gfs_seamless | 5 | 348 | 8.7 | -46% | 0.31 | 6.7 | 17 | 0.00 | 1.00 |
| Pong | gfs_seamless | 6 | 348 | 8.7 | -56% | 0.27 | 6.9 | 17 | 0.00 | 1.00 |
| Pong | gfs_seamless | 7 | 348 | 8.7 | -55% | 0.19 | 7.0 | 17 | 0.00 | 1.00 |
| Ranjit Sagar | ecmwf_aifs025_single | 0 | 226 | 8.9 | +1% | 0.80 | 4.0 | 13 | 0.46 | 0.25 |
| Ranjit Sagar | ecmwf_aifs025_single | 1 | 226 | 8.9 | -1% | 0.75 | 4.3 | 13 | 0.31 | 0.56 |
| Ranjit Sagar | ecmwf_aifs025_single | 2 | 226 | 8.9 | +5% | 0.67 | 4.9 | 13 | 0.46 | 0.40 |
| Ranjit Sagar | ecmwf_aifs025_single | 3 | 226 | 8.9 | -0% | 0.42 | 5.4 | 13 | 0.23 | 0.50 |
| Ranjit Sagar | ecmwf_aifs025_single | 4 | 226 | 8.9 | -4% | 0.31 | 5.6 | 13 | 0.15 | 0.50 |
| Ranjit Sagar | ecmwf_aifs025_single | 5 | 226 | 8.9 | -2% | 0.24 | 6.0 | 13 | 0.00 | 1.00 |
| Ranjit Sagar | ecmwf_aifs025_single | 6 | 226 | 8.9 | -2% | 0.25 | 6.2 | 13 | 0.00 | 1.00 |
| Ranjit Sagar | ecmwf_aifs025_single | 7 | 226 | 8.9 | +0% | 0.17 | 6.4 | 13 | 0.00 | 1.00 |
| Ranjit Sagar | ecmwf_ifs025 | 0 | 348 | 7.8 | -5% | 0.74 | 4.1 | 16 | 0.38 | 0.33 |
| Ranjit Sagar | ecmwf_ifs025 | 1 | 348 | 7.8 | -25% | 0.72 | 4.5 | 16 | 0.25 | 0.20 |
| Ranjit Sagar | ecmwf_ifs025 | 2 | 348 | 7.8 | -14% | 0.63 | 5.0 | 16 | 0.19 | 0.62 |
| Ranjit Sagar | ecmwf_ifs025 | 3 | 348 | 7.8 | -17% | 0.60 | 5.1 | 16 | 0.25 | 0.50 |
| Ranjit Sagar | ecmwf_ifs025 | 4 | 348 | 7.8 | -16% | 0.66 | 4.8 | 16 | 0.12 | 0.60 |
| Ranjit Sagar | ecmwf_ifs025 | 5 | 348 | 7.8 | -12% | 0.54 | 5.2 | 16 | 0.12 | 0.75 |
| Ranjit Sagar | ecmwf_ifs025 | 6 | 348 | 7.8 | -18% | 0.59 | 5.2 | 16 | 0.12 | 0.60 |
| Ranjit Sagar | ecmwf_ifs025 | 7 | 348 | 7.8 | -14% | 0.61 | 5.2 | 16 | 0.12 | 0.60 |
| Ranjit Sagar | gfs_seamless | 0 | 348 | 7.8 | +0% | 0.67 | 5.1 | 16 | 0.25 | 0.56 |
| Ranjit Sagar | gfs_seamless | 1 | 348 | 7.8 | -13% | 0.62 | 4.9 | 16 | 0.19 | 0.50 |
| Ranjit Sagar | gfs_seamless | 2 | 348 | 7.8 | -17% | 0.54 | 5.4 | 16 | 0.06 | 0.67 |
| Ranjit Sagar | gfs_seamless | 3 | 348 | 7.8 | -11% | 0.45 | 5.6 | 16 | 0.06 | 0.67 |
| Ranjit Sagar | gfs_seamless | 4 | 348 | 7.8 | +2% | 0.35 | 6.4 | 16 | 0.12 | 0.80 |
| Ranjit Sagar | gfs_seamless | 5 | 348 | 7.8 | -43% | 0.40 | 5.6 | 16 | 0.06 | 0.67 |
| Ranjit Sagar | gfs_seamless | 6 | 348 | 7.8 | -55% | 0.34 | 5.9 | 16 | 0.00 | 1.00 |
| Ranjit Sagar | gfs_seamless | 7 | 348 | 7.8 | -56% | 0.27 | 6.0 | 16 | 0.00 | n/a |
| Sutlej local | ecmwf_aifs025_single | 0 | 226 | 7.8 | -26% | 0.74 | 4.4 | 12 | 0.25 | 0.25 |
| Sutlej local | ecmwf_aifs025_single | 1 | 226 | 7.8 | -16% | 0.76 | 4.4 | 12 | 0.25 | 0.50 |
| Sutlej local | ecmwf_aifs025_single | 2 | 226 | 7.8 | -3% | 0.76 | 4.6 | 12 | 0.33 | 0.20 |
| Sutlej local | ecmwf_aifs025_single | 3 | 226 | 7.8 | -3% | 0.52 | 5.5 | 12 | 0.17 | 0.60 |
| Sutlej local | ecmwf_aifs025_single | 4 | 226 | 7.8 | -4% | 0.30 | 6.3 | 12 | 0.08 | 0.75 |
| Sutlej local | ecmwf_aifs025_single | 5 | 226 | 7.8 | +1% | 0.27 | 6.9 | 12 | 0.00 | 1.00 |
| Sutlej local | ecmwf_aifs025_single | 6 | 226 | 7.8 | +3% | 0.33 | 7.0 | 12 | 0.08 | 0.80 |
| Sutlej local | ecmwf_aifs025_single | 7 | 226 | 7.8 | +7% | 0.31 | 7.1 | 12 | 0.08 | 0.80 |
| Sutlej local | ecmwf_ifs025 | 0 | 104 | 4.0 | +0% | 0.99 | 0.3 | 0 | n/a | n/a |
| Sutlej local | ecmwf_ifs025 | 1 | 104 | 4.0 | +23% | 0.69 | 2.5 | 0 | n/a | n/a |
| Sutlej local | ecmwf_ifs025 | 2 | 104 | 4.0 | +43% | 0.64 | 3.2 | 0 | n/a | n/a |
| Sutlej local | ecmwf_ifs025 | 3 | 104 | 4.0 | +55% | 0.66 | 3.5 | 0 | n/a | 1.00 |
| Sutlej local | ecmwf_ifs025 | 4 | 104 | 4.0 | +61% | 0.64 | 3.9 | 0 | n/a | 1.00 |
| Sutlej local | ecmwf_ifs025 | 5 | 104 | 4.0 | +65% | 0.62 | 4.2 | 0 | n/a | 1.00 |
| Sutlej local | ecmwf_ifs025 | 6 | 104 | 4.0 | +63% | 0.62 | 3.9 | 0 | n/a | n/a |
| Sutlej local | ecmwf_ifs025 | 7 | 104 | 4.0 | +73% | 0.57 | 4.5 | 0 | n/a | 1.00 |
| Sutlej local | gfs_seamless | 0 | 104 | 4.0 | -25% | 0.56 | 2.9 | 0 | n/a | n/a |
| Sutlej local | gfs_seamless | 1 | 104 | 4.0 | +6% | 0.54 | 3.4 | 0 | n/a | 1.00 |
| Sutlej local | gfs_seamless | 2 | 104 | 4.0 | +27% | 0.51 | 3.8 | 0 | n/a | 1.00 |
| Sutlej local | gfs_seamless | 3 | 104 | 4.0 | +52% | 0.46 | 4.8 | 0 | n/a | 1.00 |
| Sutlej local | gfs_seamless | 4 | 104 | 4.0 | +73% | 0.47 | 5.5 | 0 | n/a | 1.00 |
| Sutlej local | gfs_seamless | 5 | 104 | 4.0 | +77% | 0.49 | 6.1 | 0 | n/a | 1.00 |
| Sutlej local | gfs_seamless | 6 | 104 | 4.0 | +42% | 0.37 | 5.0 | 0 | n/a | 1.00 |
| Sutlej local | gfs_seamless | 7 | 104 | 4.0 | +47% | 0.22 | 5.2 | 0 | n/a | 1.00 |

### Multiplicative bias correction, tested out of sample

One factor per catchment, model and lead (observed season rain over forecast season rain, clipped to 0.5 to 2), fitted on every season but one and applied to the held-out season; the held-out days of all seasons are scored together. Pearson r does not move under a scale factor, so the columns that can move are shown raw and corrected. Leads 1 to 5 are the product's horizons.

| catchment | model | lead (days) | days | held-out factors | bias raw / corrected | MAE (mm) raw / corrected | hit rate raw / corrected | false-alarm ratio raw / corrected |
|---|---|---|---|---|---|---|---|---|
| Beas local | ecmwf_aifs025_single | 1 | 226 | 0.83 to 0.99 | +7% / -5% | 4.0 / 3.9 | 0.75 / 0.50 | 0.33 / 0.33 |
| Beas local | ecmwf_aifs025_single | 2 | 226 | 0.82 to 0.86 | +18% / -2% | 4.3 / 3.9 | 0.75 / 0.62 | 0.25 / 0.17 |
| Beas local | ecmwf_aifs025_single | 3 | 226 | 0.80 to 0.94 | +12% / -5% | 4.6 / 4.4 | 0.50 / 0.38 | 0.43 / 0.40 |
| Beas local | ecmwf_aifs025_single | 4 | 226 | 0.75 to 1.05 | +8% / -7% | 5.1 / 5.0 | 0.25 / 0.00 | 0.60 / 1.00 |
| Beas local | ecmwf_aifs025_single | 5 | 226 | 0.71 to 1.01 | +12% / -7% | 5.7 / 5.4 | 0.00 / 0.00 | 1.00 / 1.00 |
| Bhakra | ecmwf_aifs025_single | 1 | 226 | 0.90 to 1.15 | -4% / -5% | 1.9 / 2.0 | n/a / n/a | 1.00 / n/a |
| Bhakra | ecmwf_aifs025_single | 2 | 226 | 0.85 to 1.03 | +4% / -4% | 2.1 / 2.1 | n/a / n/a | 1.00 / 1.00 |
| Bhakra | ecmwf_aifs025_single | 3 | 226 | 0.82 to 1.07 | +3% / -5% | 2.2 / 2.3 | n/a / n/a | 1.00 / 1.00 |
| Bhakra | ecmwf_aifs025_single | 4 | 226 | 0.81 to 1.11 | +2% / -5% | 2.4 / 2.6 | n/a / n/a | 1.00 / 1.00 |
| Bhakra | ecmwf_aifs025_single | 5 | 226 | 0.78 to 1.07 | +6% / -5% | 2.7 / 2.8 | n/a / n/a | 1.00 / 1.00 |
| Bhakra | ecmwf_ifs025 | 1 | 348 | 1.08 to 1.25 | -16% / -1% | 2.1 / 2.2 | n/a / n/a | n/a / n/a |
| Bhakra | ecmwf_ifs025 | 2 | 348 | 1.07 to 1.20 | -12% / -1% | 2.2 / 2.3 | n/a / n/a | 1.00 / 1.00 |
| Bhakra | ecmwf_ifs025 | 3 | 348 | 1.05 to 1.22 | -11% / -1% | 2.4 / 2.5 | n/a / n/a | n/a / 1.00 |
| Bhakra | ecmwf_ifs025 | 4 | 348 | 1.03 to 1.19 | -10% / -1% | 2.6 / 2.7 | n/a / n/a | 1.00 / 1.00 |
| Bhakra | ecmwf_ifs025 | 5 | 348 | 0.98 to 1.18 | -8% / -1% | 2.6 / 2.8 | n/a / n/a | n/a / n/a |
| Bhakra | gfs_seamless | 1 | 348 | 1.02 to 1.10 | -6% / -1% | 2.5 / 2.5 | n/a / n/a | 1.00 / 1.00 |
| Bhakra | gfs_seamless | 2 | 348 | 0.93 to 1.11 | -4% / -1% | 2.8 / 2.9 | n/a / n/a | n/a / n/a |
| Bhakra | gfs_seamless | 3 | 348 | 0.86 to 1.04 | +2% / -1% | 3.0 / 3.1 | n/a / n/a | n/a / n/a |
| Bhakra | gfs_seamless | 4 | 348 | 0.78 to 0.94 | +13% / -1% | 3.0 / 2.8 | n/a / n/a | 1.00 / n/a |
| Bhakra | gfs_seamless | 5 | 348 | 1.35 to 2.00 | -41% / -0% | 3.1 / 3.7 | n/a / n/a | n/a / 1.00 |
| Ghaggar Bhankarpur | ecmwf_aifs025_single | 1 | 226 | 0.73 to 1.00 | +11% / -8% | 4.3 / 4.2 | 0.44 / 0.44 | 0.43 / 0.00 |
| Ghaggar Bhankarpur | ecmwf_aifs025_single | 2 | 226 | 0.62 to 0.87 | +28% / -8% | 5.1 / 4.5 | 0.44 / 0.33 | 0.33 / 0.25 |
| Ghaggar Bhankarpur | ecmwf_aifs025_single | 3 | 226 | 0.56 to 0.89 | +33% / -9% | 5.7 / 5.0 | 0.44 / 0.22 | 0.43 / 0.50 |
| Ghaggar Bhankarpur | ecmwf_aifs025_single | 4 | 226 | 0.52 to 0.91 | +34% / -8% | 6.2 / 5.5 | 0.33 / 0.11 | 0.57 / 0.75 |
| Ghaggar Bhankarpur | ecmwf_aifs025_single | 5 | 226 | 0.50 to 0.87 | +40% / -8% | 6.9 / 5.8 | 0.11 / 0.11 | 0.80 / 0.75 |
| Ghaggar Bhankarpur | ecmwf_ifs025 | 1 | 348 | 0.94 to 1.04 | +2% / -1% | 5.1 / 5.1 | 0.42 / 0.33 | 0.17 / 0.20 |
| Ghaggar Bhankarpur | ecmwf_ifs025 | 2 | 348 | 0.82 to 0.98 | +10% / +1% | 5.6 / 5.4 | 0.33 / 0.33 | 0.33 / 0.33 |
| Ghaggar Bhankarpur | ecmwf_ifs025 | 3 | 348 | 0.82 to 0.91 | +16% / -1% | 5.9 / 5.5 | 0.33 / 0.33 | 0.56 / 0.50 |
| Ghaggar Bhankarpur | ecmwf_ifs025 | 4 | 348 | 0.77 to 0.86 | +24% / -1% | 6.3 / 5.7 | 0.17 / 0.08 | 0.82 / 0.86 |
| Ghaggar Bhankarpur | ecmwf_ifs025 | 5 | 348 | 0.77 to 0.86 | +24% / -2% | 6.6 / 5.9 | 0.17 / 0.00 | 0.82 / 1.00 |
| Ghaggar Bhankarpur | gfs_seamless | 1 | 348 | 0.99 to 1.15 | -8% / +1% | 5.2 / 5.5 | 0.17 / 0.17 | 0.71 / 0.75 |
| Ghaggar Bhankarpur | gfs_seamless | 2 | 348 | 0.81 to 1.01 | +8% / -1% | 6.2 / 5.9 | 0.17 / 0.17 | 0.75 / 0.71 |
| Ghaggar Bhankarpur | gfs_seamless | 3 | 348 | 0.64 to 0.84 | +33% / -1% | 7.7 / 6.5 | 0.17 / 0.17 | 0.87 / 0.83 |
| Ghaggar Bhankarpur | gfs_seamless | 4 | 348 | 0.63 to 0.84 | +34% / -0% | 7.9 / 6.7 | 0.08 / 0.08 | 0.95 / 0.86 |
| Ghaggar Bhankarpur | gfs_seamless | 5 | 348 | 1.14 to 1.86 | -31% / +2% | 5.5 / 6.9 | 0.00 / 0.00 | 1.00 / 1.00 |
| Ghaggar Khanauri | ecmwf_aifs025_single | 1 | 226 | 0.74 to 0.94 | +15% / -6% | 3.8 / 3.5 | 0.50 / 0.50 | 0.57 / 0.40 |
| Ghaggar Khanauri | ecmwf_aifs025_single | 2 | 226 | 0.64 to 0.82 | +33% / -6% | 4.5 / 3.8 | 0.50 / 0.50 | 0.57 / 0.25 |
| Ghaggar Khanauri | ecmwf_aifs025_single | 3 | 226 | 0.57 to 0.84 | +37% / -7% | 5.0 / 4.4 | 0.50 / 0.33 | 0.57 / 0.33 |
| Ghaggar Khanauri | ecmwf_aifs025_single | 4 | 226 | 0.53 to 0.86 | +39% / -7% | 5.6 / 4.8 | 0.50 / 0.17 | 0.57 / 0.50 |
| Ghaggar Khanauri | ecmwf_aifs025_single | 5 | 226 | 0.51 to 0.83 | +44% / -7% | 6.1 / 5.1 | 0.17 / 0.17 | 0.80 / 0.67 |
| Ghaggar Khanauri | ecmwf_ifs025 | 1 | 348 | 0.90 to 1.00 | +5% / -0% | 4.7 / 4.6 | 0.36 / 0.36 | 0.33 / 0.33 |
| Ghaggar Khanauri | ecmwf_ifs025 | 2 | 348 | 0.79 to 0.96 | +12% / +3% | 5.0 / 4.8 | 0.36 / 0.27 | 0.43 / 0.50 |
| Ghaggar Khanauri | ecmwf_ifs025 | 3 | 348 | 0.78 to 0.85 | +21% / +0% | 5.5 / 5.0 | 0.27 / 0.18 | 0.67 / 0.75 |
| Ghaggar Khanauri | ecmwf_ifs025 | 4 | 348 | 0.75 to 0.84 | +23% / +1% | 5.7 / 5.2 | 0.18 / 0.18 | 0.85 / 0.67 |
| Ghaggar Khanauri | ecmwf_ifs025 | 5 | 348 | 0.75 to 0.82 | +26% / -0% | 6.1 / 5.4 | 0.00 / 0.00 | 1.00 / 1.00 |
| Ghaggar Khanauri | gfs_seamless | 1 | 348 | 0.97 to 1.25 | -10% / +4% | 4.8 / 5.3 | 0.18 / 0.18 | 0.67 / 0.82 |
| Ghaggar Khanauri | gfs_seamless | 2 | 348 | 0.88 to 1.01 | +5% / -1% | 5.4 / 5.3 | 0.18 / 0.18 | 0.75 / 0.67 |
| Ghaggar Khanauri | gfs_seamless | 3 | 348 | 0.69 to 0.86 | +28% / -0% | 6.9 / 6.0 | 0.18 / 0.18 | 0.86 / 0.80 |
| Ghaggar Khanauri | gfs_seamless | 4 | 348 | 0.67 to 0.81 | +34% / -0% | 7.4 / 6.2 | 0.09 / 0.09 | 0.94 / 0.86 |
| Ghaggar Khanauri | gfs_seamless | 5 | 348 | 1.21 to 1.86 | -33% / +2% | 5.0 / 6.2 | 0.09 / 0.09 | 0.67 / 0.89 |
| Harike local | ecmwf_aifs025_single | 1 | 226 | 0.81 to 1.07 | +2% / -9% | 3.3 / 3.4 | 0.50 / 0.38 | 0.33 / 0.40 |
| Harike local | ecmwf_aifs025_single | 2 | 226 | 0.76 to 0.92 | +15% / -7% | 3.7 / 3.4 | 0.50 / 0.50 | 0.00 / 0.00 |
| Harike local | ecmwf_aifs025_single | 3 | 226 | 0.70 to 0.99 | +13% / -10% | 4.2 / 4.3 | 0.38 / 0.38 | 0.25 / 0.25 |
| Harike local | ecmwf_aifs025_single | 4 | 226 | 0.63 to 1.09 | +10% / -10% | 4.9 / 5.0 | 0.12 / 0.00 | 0.50 / 1.00 |
| Harike local | ecmwf_aifs025_single | 5 | 226 | 0.60 to 1.04 | +15% / -10% | 5.5 / 5.3 | 0.00 / 0.00 | 1.00 / 1.00 |
| Pong | ecmwf_aifs025_single | 1 | 226 | 0.97 to 1.10 | -5% / -4% | 4.5 / 4.6 | 0.27 / 0.27 | 0.50 / 0.43 |
| Pong | ecmwf_aifs025_single | 2 | 226 | 0.95 to 0.97 | +3% / -1% | 4.7 / 4.6 | 0.47 / 0.40 | 0.30 / 0.33 |
| Pong | ecmwf_aifs025_single | 3 | 226 | 0.92 to 1.03 | +1% / -4% | 5.2 / 5.2 | 0.27 / 0.07 | 0.43 / 0.75 |
| Pong | ecmwf_aifs025_single | 4 | 226 | 0.90 to 1.08 | -2% / -5% | 5.6 / 5.7 | 0.00 / 0.00 | 1.00 / 1.00 |
| Pong | ecmwf_aifs025_single | 5 | 226 | 0.90 to 1.02 | +2% / -4% | 6.1 / 6.0 | 0.07 / 0.00 | 0.80 / 1.00 |
| Pong | ecmwf_ifs025 | 1 | 348 | 1.15 to 1.37 | -21% / -2% | 4.8 / 5.2 | 0.24 / 0.24 | 0.56 / 0.64 |
| Pong | ecmwf_ifs025 | 2 | 348 | 1.01 to 1.22 | -10% / -2% | 5.2 / 5.5 | 0.29 / 0.29 | 0.58 / 0.62 |
| Pong | ecmwf_ifs025 | 3 | 348 | 0.99 to 1.25 | -11% / -2% | 5.7 / 6.1 | 0.12 / 0.12 | 0.78 / 0.78 |
| Pong | ecmwf_ifs025 | 4 | 348 | 0.99 to 1.22 | -11% / -2% | 5.4 / 5.7 | 0.18 / 0.18 | 0.57 / 0.75 |
| Pong | ecmwf_ifs025 | 5 | 348 | 0.93 to 1.21 | -8% / -2% | 5.7 / 6.2 | 0.18 / 0.18 | 0.70 / 0.77 |
| Pong | gfs_seamless | 1 | 348 | 1.12 to 1.29 | -19% / -2% | 5.6 / 6.0 | 0.12 / 0.12 | 0.75 / 0.78 |
| Pong | gfs_seamless | 2 | 348 | 1.01 to 1.35 | -19% / -1% | 5.8 / 6.4 | 0.06 / 0.06 | 0.80 / 0.86 |
| Pong | gfs_seamless | 3 | 348 | 0.87 to 1.25 | -8% / -0% | 6.2 / 6.8 | 0.12 / 0.06 | 0.75 / 0.86 |
| Pong | gfs_seamless | 4 | 348 | 0.77 to 1.09 | +4% / -1% | 6.6 / 6.9 | 0.06 / 0.06 | 0.92 / 0.92 |
| Pong | gfs_seamless | 5 | 348 | 1.38 to 2.00 | -46% / -6% | 6.7 / 8.0 | 0.00 / 0.00 | 1.00 / 1.00 |
| Ranjit Sagar | ecmwf_aifs025_single | 1 | 226 | 0.98 to 1.08 | -1% / +3% | 4.3 / 4.5 | 0.31 / 0.31 | 0.56 / 0.56 |
| Ranjit Sagar | ecmwf_aifs025_single | 2 | 226 | 0.88 to 1.09 | +5% / +8% | 4.9 / 5.1 | 0.46 / 0.46 | 0.40 / 0.40 |
| Ranjit Sagar | ecmwf_aifs025_single | 3 | 226 | 0.95 to 1.11 | -0% / +5% | 5.4 / 5.6 | 0.23 / 0.23 | 0.50 / 0.50 |
| Ranjit Sagar | ecmwf_aifs025_single | 4 | 226 | 1.02 to 1.09 | -4% / +2% | 5.6 / 5.7 | 0.15 / 0.15 | 0.50 / 0.50 |
| Ranjit Sagar | ecmwf_aifs025_single | 5 | 226 | 1.00 to 1.07 | -2% / +2% | 6.0 / 6.1 | 0.00 / 0.00 | 1.00 / 1.00 |
| Ranjit Sagar | ecmwf_ifs025 | 1 | 348 | 1.28 to 1.37 | -25% / -1% | 4.5 / 4.6 | 0.25 / 0.31 | 0.20 / 0.44 |
| Ranjit Sagar | ecmwf_ifs025 | 2 | 348 | 1.11 to 1.20 | -14% / -1% | 5.0 / 5.2 | 0.19 / 0.31 | 0.62 / 0.67 |
| Ranjit Sagar | ecmwf_ifs025 | 3 | 348 | 1.16 to 1.23 | -17% / -1% | 5.1 / 5.3 | 0.25 / 0.25 | 0.50 / 0.56 |
| Ranjit Sagar | ecmwf_ifs025 | 4 | 348 | 1.11 to 1.23 | -16% / -1% | 4.8 / 5.0 | 0.12 / 0.25 | 0.60 / 0.64 |
| Ranjit Sagar | ecmwf_ifs025 | 5 | 348 | 1.05 to 1.19 | -12% / -1% | 5.2 / 5.4 | 0.12 / 0.12 | 0.75 / 0.78 |
| Ranjit Sagar | gfs_seamless | 1 | 348 | 1.07 to 1.20 | -13% / -1% | 4.9 / 5.1 | 0.19 / 0.19 | 0.50 / 0.50 |
| Ranjit Sagar | gfs_seamless | 2 | 348 | 1.02 to 1.31 | -17% / -1% | 5.4 / 5.8 | 0.06 / 0.12 | 0.67 / 0.67 |
| Ranjit Sagar | gfs_seamless | 3 | 348 | 0.91 to 1.33 | -11% / +1% | 5.6 / 6.2 | 0.06 / 0.06 | 0.67 / 0.80 |
| Ranjit Sagar | gfs_seamless | 4 | 348 | 0.81 to 1.15 | +2% / +1% | 6.4 / 6.5 | 0.12 / 0.06 | 0.80 / 0.88 |
| Ranjit Sagar | gfs_seamless | 5 | 348 | 1.34 to 2.00 | -43% / -1% | 5.6 / 7.0 | 0.06 / 0.12 | 0.67 / 0.87 |
| Sutlej local | ecmwf_aifs025_single | 1 | 226 | 0.80 to 1.40 | -16% / -15% | 4.4 / 5.3 | 0.25 / 0.17 | 0.50 / 0.50 |
| Sutlej local | ecmwf_aifs025_single | 2 | 226 | 0.73 to 1.18 | -3% / -14% | 4.6 / 5.1 | 0.33 / 0.33 | 0.20 / 0.20 |
| Sutlej local | ecmwf_aifs025_single | 3 | 226 | 0.66 to 1.25 | -3% / -15% | 5.5 / 6.2 | 0.17 / 0.17 | 0.60 / 0.60 |
| Sutlej local | ecmwf_aifs025_single | 4 | 226 | 0.61 to 1.33 | -4% / -13% | 6.3 / 7.1 | 0.08 / 0.00 | 0.75 / 1.00 |
| Sutlej local | ecmwf_aifs025_single | 5 | 226 | 0.59 to 1.25 | +1% / -14% | 6.9 / 7.3 | 0.00 / 0.00 | 1.00 / 1.00 |

Held-out days, dam catchments, leads 1 to 5: MAE lower after correction in 4 of 45 rows, heavy-day hit rate higher in 5, false-alarm ratio higher in 19. The product applies a correction only when MAE and hit rate both improve on the held-out seasons for a dam catchment; the rule is in `design.md`.

### The machine-learned model against the primary deterministic model

`ecmwf_aifs025_single` (ECMWF AIFS, the machine-learned forecast) and `ecmwf_ifs025` scored on exactly the same rows: the dam catchments, leads 1, 2, 3, every target day both have in the archive (2,034 rows). The rule, written before the pull: the challenger replaces the incumbent as the product's primary deterministic model only if its heavy-day hit rate is higher and its false-alarm ratio is not higher on those rows. The spill probability comes from the IFS ensemble either way; the primary deterministic model drives the local term and the deterministic fallback.

| model | obs mean (mm) | bias | r | MAE (mm) | heavy days | hit rate | false-alarm ratio |
|---|---|---|---|---|---|---|---|
| ecmwf_ifs025 | 7.6 | -16% | 0.65 | 4.1 | 84 | 0.24 | 0.53 |
| ecmwf_aifs025_single | 7.6 | +1% | 0.60 | 3.9 | 84 | 0.33 | 0.49 |

Hit rate higher: yes; false-alarm ratio not higher: yes. Verdict: the primary deterministic model switches to ecmwf_aifs025_single. The product's primary is `ecmwf_aifs025_single`.

## Live 2026: one-day inflow prediction against the BBMB bulletins

Persistence (tomorrow's inflow equals today's) is the baseline any one-day prediction has to beat; the model's base component is that persistence with the rain response added, so the difference between the two rows is what the rain brings.

| dam | days | mean observed (cusecs) | mean predicted (cusecs) | bias | Pearson r | MAE (cusecs) | persistence bias | persistence r | persistence MAE |
|---|---|---|---|---|---|---|---|---|---|
| Bhakra | 30 | 41,926 | 41,551 | -1% | +0.46 | 4,185 | +0% | +0.56 | 4,148 |
| Pong | 30 | 35,571 | 35,601 | +0% | +0.42 | 11,232 | +3% | +0.37 | 12,135 |

### By horizon, with observed and with forecast rain

From each bulletin day, the inflow one to five days ahead: predicted with the observed catchment rain of the days in between (what the hydrology alone can do), with the rain forecast issued that day (what the product does, per model), and by persistence (the inflow stays at the day's value). Scored on the days a bulletin exists for the target day.

| dam | horizon (days) | rain | days | bias | Pearson r | MAE (cusecs) |
|---|---|---|---|---|---|---|
| Bhakra | 1 | observed rain | 30 | -1% | +0.46 | 4,185 |
| Bhakra | 1 | persistence | 30 | +0% | +0.56 | 4,148 |
| Bhakra | 1 | ecmwf_ifs025 | 30 | -1% | +0.49 | 4,187 |
| Bhakra | 1 | gfs_seamless | 30 | +0% | +0.48 | 5,049 |
| Bhakra | 1 | ecmwf_aifs025_single | 30 | +1% | +0.45 | 4,804 |
| Bhakra | 2 | observed rain | 29 | -2% | +0.21 | 6,107 |
| Bhakra | 2 | persistence | 29 | +0% | +0.32 | 5,796 |
| Bhakra | 2 | ecmwf_ifs025 | 29 | +0% | +0.27 | 6,121 |
| Bhakra | 2 | gfs_seamless | 29 | +1% | +0.24 | 7,049 |
| Bhakra | 2 | ecmwf_aifs025_single | 29 | +3% | +0.20 | 7,065 |
| Bhakra | 3 | observed rain | 28 | -3% | +0.18 | 6,894 |
| Bhakra | 3 | persistence | 28 | +0% | +0.19 | 6,762 |
| Bhakra | 3 | ecmwf_ifs025 | 28 | +1% | +0.33 | 6,313 |
| Bhakra | 3 | gfs_seamless | 28 | +1% | +0.25 | 7,414 |
| Bhakra | 3 | ecmwf_aifs025_single | 28 | +4% | +0.17 | 7,695 |
| Bhakra | 4 | observed rain | 27 | -6% | +0.19 | 6,829 |
| Bhakra | 4 | persistence | 27 | +0% | +0.10 | 7,551 |
| Bhakra | 4 | ecmwf_ifs025 | 27 | +0% | +0.31 | 5,974 |
| Bhakra | 4 | gfs_seamless | 27 | +2% | +0.33 | 6,728 |
| Bhakra | 4 | ecmwf_aifs025_single | 27 | +3% | +0.14 | 6,886 |
| Bhakra | 5 | observed rain | 26 | -8% | +0.08 | 7,488 |
| Bhakra | 5 | persistence | 26 | +1% | -0.05 | 7,691 |
| Bhakra | 5 | ecmwf_ifs025 | 26 | +0% | +0.29 | 6,748 |
| Bhakra | 5 | gfs_seamless | 26 | +2% | +0.34 | 7,301 |
| Bhakra | 5 | ecmwf_aifs025_single | 26 | +3% | +0.01 | 7,646 |
| Pong | 1 | observed rain | 30 | +0% | +0.42 | 11,232 |
| Pong | 1 | persistence | 30 | +3% | +0.37 | 12,135 |
| Pong | 1 | ecmwf_ifs025 | 30 | -0% | +0.42 | 11,031 |
| Pong | 1 | gfs_seamless | 30 | -1% | +0.40 | 11,662 |
| Pong | 1 | ecmwf_aifs025_single | 30 | +2% | +0.39 | 11,449 |
| Pong | 2 | observed rain | 29 | +0% | +0.06 | 14,649 |
| Pong | 2 | persistence | 29 | +4% | -0.20 | 17,175 |
| Pong | 2 | ecmwf_ifs025 | 29 | +4% | +0.01 | 15,541 |
| Pong | 2 | gfs_seamless | 29 | +1% | +0.00 | 16,189 |
| Pong | 2 | ecmwf_aifs025_single | 29 | +5% | -0.04 | 15,559 |
| Pong | 3 | observed rain | 28 | -1% | +0.36 | 12,085 |
| Pong | 3 | persistence | 28 | +4% | +0.03 | 16,235 |
| Pong | 3 | ecmwf_ifs025 | 28 | +10% | +0.39 | 14,082 |
| Pong | 3 | gfs_seamless | 28 | +5% | +0.28 | 15,032 |
| Pong | 3 | ecmwf_aifs025_single | 28 | +5% | +0.26 | 13,353 |
| Pong | 4 | observed rain | 27 | -1% | +0.53 | 10,358 |
| Pong | 4 | persistence | 27 | +7% | +0.31 | 14,265 |
| Pong | 4 | ecmwf_ifs025 | 27 | +10% | +0.56 | 9,676 |
| Pong | 4 | gfs_seamless | 27 | +12% | +0.53 | 12,058 |
| Pong | 4 | ecmwf_aifs025_single | 27 | +6% | +0.44 | 10,421 |
| Pong | 5 | observed rain | 26 | -3% | +0.12 | 13,870 |
| Pong | 5 | persistence | 26 | +9% | +0.03 | 16,071 |
| Pong | 5 | ecmwf_ifs025 | 26 | +12% | +0.17 | 14,245 |
| Pong | 5 | gfs_seamless | 26 | +18% | +0.33 | 14,171 |
| Pong | 5 | ecmwf_aifs025_single | 26 | +7% | +0.04 | 14,444 |

## Prospective record, 2026 season

Issued daily from the committed inputs and the live BBMB bulletin; a record is never rewritten (`outputs/forecast/`). P(spillway forced) is at the five-day horizon.

13 issue dates from 2026-09-05 to 2026-09-17. Bhakra: P(spillway forced) above zero on 0 of 13 days. Pong: P(spillway forced) above zero on 0 of 13 days. Days with any control point at or above the WRD low band: 0.

No day so far has put a forced spill or a classed arrival on the record.
