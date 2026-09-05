# Verification report

Rendered from `outputs/verification/` (results.json, peak_tests.csv). Regenerate with `punjabflood verify` then `punjabflood report`.

## Inflow model parameters

Fitted by non-negative least squares on day-to-day changes of measured storage (CWC table, or the CWC level through the dam's own rating) against lagged catchment rain volumes; spilling days and implausible jumps excluded. The recession is the lag-2 to lag-1 autocovariance ratio of the residuals, clipped to [0.50, 0.99]; a raw ratio above the clip means the residual drifts through the season (base flow and outflow both move slowly) rather than recessing, so the base is carried as nearly constant over the horizon.

| dam | area used (km2) | runoff coefficient c (dry) | c_wet per 100 mm antecedent | lag weights w0..w3 | recession (raw ratio) | gamma | R2 | RMSE (BCM/day) | days |
|---|---|---|---|---|---|---|---|---|---|
| Bhakra | 25,762 | 0.170 | 0.250 | 0.54, 0.27, 0.10, 0.09 | 0.990 (1.856) | 0.00 | 0.212 | 0.0434 | 1009 |
| Pong | 13,637 | 0.203 | 0.328 | 0.35, 0.48, 0.09, 0.08 | 0.990 (1.051) | 0.00 | 0.777 | 0.0296 | 733 |
| Ranjit Sagar | 6,953 | 0.131 | 0.263 | 0.62, 0.24, 0.08, 0.05 | 0.990 (2.219) | 0.00 | 0.398 | 0.0224 | 1184 |
The coefficient in force on a day is c plus c_wet times the previous five days' catchment rain over 100 mm, capped at 0.95.

## Annual peak class, 38 years (1988 to 2025)

For each WRD peak table, the predictors ranked by area under the ROC curve for the department's High class. Spearman rho is against the peak discharge itself; the Brier skill score compares leave-one-year-out logistic probabilities with the climatological base rate (positive is skill).

### dhilwan

| predictor | years | High years | Spearman rho | AUROC (High) | Brier skill |
|---|---|---|---|---|---|
| Pong_days_above_95pct | 11 | 2 | +0.62 | 1.00 | +0.54 |
| Ranjit Sagar_frac_aug01 | 10 | 1 | +0.71 | 1.00 | -0.04 |
| Pong_hei_pp_max | 11 | 2 | +0.75 | 1.00 | +0.45 |
| Pong_release_pp_max | 11 | 2 | +0.62 | 1.00 | +0.84 |
| Pong_frac_aug01 | 10 | 1 | +0.48 | 1.00 | -0.04 |
| Ranjit Sagar_max10d_bcm | 38 | 5 | +0.36 | 0.99 | +0.62 |
| Ranjit Sagar_max5d_bcm | 38 | 5 | +0.33 | 0.98 | +0.49 |
| Ranjit Sagar_max3d_bcm | 38 | 5 | +0.34 | 0.96 | +0.45 |
| Pong_season_bcm | 38 | 5 | +0.68 | 0.95 | +0.44 |
| Pong_frac_max | 11 | 2 | +0.72 | 0.94 | +0.11 |

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
| Pong_days_above_95pct | 11 | 2 | +0.68 | 1.00 | +0.54 |
| Ranjit Sagar_frac_aug01 | 10 | 1 | +0.73 | 1.00 | -0.04 |
| Pong_hei_pp_max | 11 | 2 | +0.88 | 1.00 | +0.45 |
| Pong_release_pp_max | 11 | 2 | +0.68 | 1.00 | +0.84 |
| Pong_frac_aug01 | 10 | 1 | +0.49 | 1.00 | -0.04 |
| Ranjit Sagar_max10d_bcm | 38 | 5 | +0.62 | 0.99 | +0.62 |
| Ranjit Sagar_max5d_bcm | 38 | 5 | +0.56 | 0.98 | +0.49 |
| Ranjit Sagar_max3d_bcm | 38 | 5 | +0.57 | 0.96 | +0.45 |
| Pong_season_bcm | 38 | 5 | +0.75 | 0.95 | +0.44 |
| Pong_frac_max | 11 | 2 | +0.85 | 0.94 | +0.11 |

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
| Pong_days_above_95pct | 11 | 2 | +0.57 | 1.00 | +0.54 |
| Ranjit Sagar_frac_aug01 | 10 | 1 | +0.56 | 1.00 | -0.04 |
| Pong_hei_pp_max | 11 | 2 | +0.69 | 1.00 | +0.45 |
| Pong_release_pp_max | 11 | 2 | +0.57 | 1.00 | +0.84 |
| Pong_frac_aug01 | 10 | 1 | +0.56 | 1.00 | -0.04 |
| Ranjit Sagar_max10d_bcm | 38 | 5 | +0.52 | 0.99 | +0.62 |
| Ranjit Sagar_max5d_bcm | 38 | 5 | +0.49 | 0.98 | +0.49 |
| Ranjit Sagar_max3d_bcm | 38 | 5 | +0.49 | 0.96 | +0.45 |
| Pong_season_bcm | 38 | 5 | +0.52 | 0.95 | +0.44 |
| Pong_frac_max | 11 | 2 | +0.65 | 0.94 | +0.11 |

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

The forced release of a full Pong reservoir under the observed rain (one-day-ahead spill of each day's run, placed on the day it happens) is routed to Dhilwan with the Annexure Z travel times and compared with the department's dated peak. The river release on a spill day is the spill plus the turbine passage less the Mukerian Hydel Channel's capacity (a full reservoir passes its inflow, so the turbines run); this is the lower bound on what the dam sends down the Beas, and the spill-only row below it is the lower bound of that. Tributaries between Pong and Dhilwan are not modelled. The storage that drives the index comes from the public record, which is weekly in August 2023 and a handful of press points in August 2025; between measurements the reservoir is carried by the model's own water balance under the observed rain (one-day inflow less the non-spill passage), and every measurement re-anchors it.

| year | release routed | predicted peak date | predicted peak (cusecs) | observed peak date | observed peak (cusecs) | lag (days) | magnitude ratio |
|---|---|---|---|---|---|---|---|
| 2023 | spill + passage | 2023-08-17 | 181,686 | 2023-08-17 | 237,500 | +0 | 0.76 |
| 2025 | spill + passage | 2025-08-28 | 173,501 | 2025-08-31 | 235,494 | -3 | 0.74 |
| 2023 | spill only | 2023-08-17 | 147,586 | 2023-08-17 | 237,500 | +0 | 0.62 |
| 2025 | spill only | 2025-08-28 | 139,401 | 2025-08-31 | 235,494 | -3 | 0.59 |

Storage basis of the Pong path in August of each event year (days):

| year | measured (CWC) | CWC level through the rating | press report | carried by the model | interpolated |
|---|---|---|---|---|---|
| 2023 | 4 | 1 | 0 | 26 | 0 |
| 2025 | 0 | 0 | 4 | 22 | 0 |

### Flood-scale inflow: the model against the figures the record holds

The runoff coefficient is fitted on ordinary filling days (the storage-change relation), so what the model does at flood scale has to be checked against whatever flood-scale inflow the public record holds: BBMB's daily sheets where the Internet Archive kept them, dated press figures credited to the dam offices, the period means of BBMB inflow that the Public Action Committee compiled for August to early September 2025, the season's largest inflows as stated to the Rajya Sabha, and the record inflow in the Pong emergency action plan. Each is set against the model's one-day inflow under observed rain (the perfect-prognosis run with its base-flow stand-in) on the same day or days: a period mean against the model's mean over the same days, a season peak against the model's largest day of the same June to September. A period mean is a daily quantity like the model's; the season peaks, the evening press figure and the sheets' figures are readings at a time of day, so against a daily volume those ratios are lower bounds on the model's share of the day's mean. The full citations are in `data-sources.md` and the reference tables.

| dam | figure | model days | reported (cusecs) | model (cusecs) | model / reported | source |
|---|---|---|---|---|---|---|
| Bhakra | mean, 2025-08-01 to 2025-08-24 | 24 | 57,430 | 55,913 | 0.97 | PAC data via The Wire, 8 Sep 2025 |
| Bhakra | mean, 2025-08-25 to 2025-09-04 | 11 | 73,400 | 81,542 | 1.11 | PAC data via The Wire, 8 Sep 2025 |
| Pong | mean, 2025-08-01 to 2025-08-24 | 19 | 77,000 | 83,012 | 1.08 | PAC data via The Wire, 8 Sep 2025 |
| Pong | mean, 2025-08-25 to 2025-09-04 | 11 | 121,600 | 137,283 | 1.13 | PAC data via The Wire, 8 Sep 2025 |
| Ranjit Sagar | mean, 2025-08-01 to 2025-08-24 | 20 | 38,700 | 30,075 | 0.78 | PAC data via The Wire, 8 Sep 2025 |
| Ranjit Sagar | mean, 2025-08-25 to 2025-09-04 | 11 | 71,960 | 69,098 | 0.96 | PAC data via The Wire, 8 Sep 2025 |
| Pong | day, 2025-08-26 | 1 | 233,000 | 175,210 | 0.75 | PTI via The Week, 26 Aug 2025 (about) |
| Bhakra | day, 2025-09-05 | 1 | 76,318 | 67,120 | 0.88 | SDO Nangal via Babushahi, 5 Sep 2025 |
| Bhakra | day, 2025-09-15 | 1 | 54,667 | 44,853 | 0.82 | BBMB daily sheet, Internet Archive |
| Bhakra | day, 2025-09-24 | 1 | 35,666 | 35,817 | 1.00 | BBMB daily sheet, Internet Archive |
| Pong | day, 2025-09-15 | 1 | 76,498 | 83,124 | 1.09 | BBMB daily sheet, Internet Archive |
| Pong | day, 2025-09-24 | 1 | 17,291 | 40,090 | 2.32 | BBMB daily sheet, Internet Archive |
| Pong | record day, 2023-08-14 | 1 | 734,000 | 233,281 | 0.32 | BBMB Pong EAP, largest inflow recorded |
| Pong | largest day of 2025 | 112 | 349,522 | 203,537 | 0.58 | Rajya Sabha reply via PTI, 2 Dec 2025 |
| Bhakra | largest day of 2025 | 121 | 190,603 | 108,620 | 0.57 | Rajya Sabha reply via PTI, 2 Dec 2025 |

Where the run covers at least 10 of a period's days, the model's mean is 0.78 to 1.13 of the reported mean; its largest day of the season is 0.57 to 0.58 of the stated peak. The flood's volume is close to right and its peak day is not: the model spreads the volume over more days than the river does, which is consistent with lag weights fitted on ordinary days.

### A sharper response to heavy rain, tested out of sample

Rain above the heavy-day threshold in a catchment day gets its own coefficient and lag weights (the threshold-excess variant), fitted jointly with the ordinary response on the same storage record. The rule before it can replace the response the product uses: the leave-one-season-out error (each season scored by a fit on the others) may not rise at any dam, the season-peak ratios of the flood-scale table must rise, and the period means may not move further from the reported means than the baseline's worst one does. Heavy-day bias is observed minus predicted storage change, positive when heavy days are under-predicted.

| dam | variant | seasons | days | held-out RMSE (BCM/day) | heavy days | heavy-day RMSE (BCM/day) | heavy-day bias (BCM/day) | c | c_wet | w | c_excess | w_excess |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Bhakra | baseline | 11 | 1009 | 0.0439 | 2 | 0.1013 | -0.0908 | 0.170 | 0.250 | 0.54 0.27 0.10 0.09 | 0.000 | none |
| Bhakra | excess above 30 mm | 11 | 1009 | 0.0668 | 2 | 0.0923 | -0.0773 | 0.194 | 0.207 | 0.55 0.21 0.12 0.12 | 0.303 | 0.00 1.00 0.00 0.00 |
| Pong | baseline | 8 | 733 | 0.0302 | 28 | 0.0782 | -0.0158 | 0.203 | 0.328 | 0.35 0.48 0.09 0.08 | 0.000 | none |
| Pong | excess above 30 mm | 8 | 733 | 0.0304 | 28 | 0.0773 | -0.0129 | 0.200 | 0.332 | 0.40 0.39 0.11 0.10 | 0.523 | 0.20 0.65 0.09 0.06 |
| Ranjit Sagar | baseline | 11 | 1184 | 0.0229 | 29 | 0.0442 | -0.0113 | 0.131 | 0.263 | 0.62 0.24 0.08 0.05 | 0.000 | none |
| Ranjit Sagar | excess above 30 mm | 11 | 1184 | 0.0229 | 29 | 0.0469 | -0.0074 | 0.156 | 0.166 | 0.47 0.27 0.15 0.11 | 0.469 | 0.46 0.48 0.00 0.07 |

| variant | period means covered | worst deviation of a period mean from 1 | season-peak ratio, smallest | season-peak ratio, largest |
|---|---|---|---|---|
| baseline | 6 | 0.22 | 0.57 | 0.58 |
| excess above 30 mm | 6 | 0.26 | 0.55 | 0.58 |

Verdict on 'excess above 30 mm', not adopted. Conditions: the held-out error does not rise at any dam (fails); the season peaks rise (fails); the period means hold (fails).

## As-issued hindcast: what the product would have said, each dam, 2024 to 2026

For each issue date the recorded or model-carried storage and the rain forecast actually issued that day (archived lead 1 to 5 QPF, deterministic) go through the same water balance as the live product. A flagged day is an issue date whose forecast forces the spillway within five days. BBMB's gate log is not public, so the model's own run under observed rain (perfect prognosis) is the reference: a flag is a hit when that run also forces the spillway within five days of the same issue date, a false flag otherwise, and a perfect-prognosis flag without an as-issued flag is a miss. The first hit is the warning; the lead is counted from it to the model's first spill under observed rain and to the dated Dhilwan peak. The window is 1 August to 15 September.

| year | dam | model | issue days | flagged (hits, false) | missed | first flag of any kind | first hit (issue date, spill on day) | earliest possible flag (observed rain) | first spill under observed rain | lead (days) | observed Dhilwan peak (Pong only) | lead (days) | largest forecast peak release (cusecs) | perfect-prognosis peak release (cusecs) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2024 | Pong | ecmwf_ifs025 | 46 | 0 (0 hits, 0 false) | 0 | none | none | none | none | n/a | 2024-08-12 | n/a | 0 | 0 |
| 2024 | Pong | gfs_seamless | 46 | 0 (0 hits, 0 false) | 0 | none | none | none | none | n/a | 2024-08-12 | n/a | 0 | 0 |
| 2025 | Pong | ecmwf_ifs025 | 41 | 25 (25 hits, 0 false) | 4 | 2025-08-15 | 2025-08-15, day 5 | 2025-08-14 | 2025-08-27 | +12 | 2025-08-31 | +16 | 173,377 | 139,401 |
| 2025 | Pong | gfs_seamless | 41 | 23 (23 hits, 0 false) | 6 | 2025-08-17 | 2025-08-17, day 4 | 2025-08-14 | 2025-08-27 | +10 | 2025-08-31 | +14 | 120,955 | 139,401 |
| 2026 | Pong | ecmwf_ifs025 | 30 | 0 (0 hits, 0 false) | 0 | none | none | none | none | n/a | none | n/a | 0 | 0 |
| 2026 | Pong | gfs_seamless | 30 | 0 (0 hits, 0 false) | 0 | none | none | none | none | n/a | none | n/a | 0 | 0 |
| 2024 | Bhakra | ecmwf_ifs025 | 46 | 0 (0 hits, 0 false) | 0 | none | none | none | none | n/a | none | n/a | 0 | 0 |
| 2024 | Bhakra | gfs_seamless | 46 | 0 (0 hits, 0 false) | 0 | none | none | none | none | n/a | none | n/a | 0 | 0 |
| 2025 | Bhakra | ecmwf_ifs025 | 46 | 3 (3 hits, 0 false) | 1 | 2025-08-30 | 2025-08-30, day 4 | 2025-08-29 | none | n/a | none | n/a | 35,473 | 0 |
| 2025 | Bhakra | gfs_seamless | 46 | 1 (1 hits, 0 false) | 3 | 2025-09-01 | 2025-09-01, day 2 | 2025-08-29 | none | n/a | none | n/a | 48,966 | 0 |
| 2026 | Bhakra | ecmwf_ifs025 | 30 | 0 (0 hits, 0 false) | 0 | none | none | none | none | n/a | none | n/a | 0 | 0 |
| 2026 | Bhakra | gfs_seamless | 30 | 0 (0 hits, 0 false) | 0 | none | none | none | none | n/a | none | n/a | 0 | 0 |
| 2024 | Ranjit Sagar | ecmwf_ifs025 | 46 | 0 (0 hits, 0 false) | 0 | none | none | none | none | n/a | none | n/a | 0 | 0 |
| 2024 | Ranjit Sagar | gfs_seamless | 46 | 0 (0 hits, 0 false) | 0 | none | none | none | none | n/a | none | n/a | 0 | 0 |
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
| Bhakra | ecmwf_ifs025 | 0 | 339 | 4.4 | -16% | 0.70 | 1.9 | 0 | n/a | 1.00 |
| Bhakra | ecmwf_ifs025 | 1 | 339 | 4.4 | -16% | 0.64 | 2.1 | 0 | n/a | n/a |
| Bhakra | ecmwf_ifs025 | 2 | 339 | 4.4 | -12% | 0.66 | 2.2 | 0 | n/a | 1.00 |
| Bhakra | ecmwf_ifs025 | 3 | 339 | 4.4 | -11% | 0.56 | 2.4 | 0 | n/a | n/a |
| Bhakra | ecmwf_ifs025 | 4 | 339 | 4.4 | -10% | 0.52 | 2.6 | 0 | n/a | 1.00 |
| Bhakra | ecmwf_ifs025 | 5 | 339 | 4.4 | -8% | 0.50 | 2.6 | 0 | n/a | n/a |
| Bhakra | ecmwf_ifs025 | 6 | 339 | 4.4 | -8% | 0.52 | 2.7 | 0 | n/a | n/a |
| Bhakra | ecmwf_ifs025 | 7 | 339 | 4.4 | +1% | 0.51 | 2.8 | 0 | n/a | 1.00 |
| Bhakra | gfs_seamless | 0 | 339 | 4.4 | +3% | 0.66 | 2.4 | 0 | n/a | 1.00 |
| Bhakra | gfs_seamless | 1 | 339 | 4.4 | -6% | 0.61 | 2.5 | 0 | n/a | 1.00 |
| Bhakra | gfs_seamless | 2 | 339 | 4.4 | -4% | 0.48 | 2.8 | 0 | n/a | n/a |
| Bhakra | gfs_seamless | 3 | 339 | 4.4 | +3% | 0.43 | 3.1 | 0 | n/a | n/a |
| Bhakra | gfs_seamless | 4 | 339 | 4.4 | +13% | 0.50 | 3.0 | 0 | n/a | 1.00 |
| Bhakra | gfs_seamless | 5 | 339 | 4.4 | -41% | 0.31 | 3.1 | 0 | n/a | n/a |
| Bhakra | gfs_seamless | 6 | 339 | 4.4 | -51% | 0.22 | 3.4 | 0 | n/a | n/a |
| Bhakra | gfs_seamless | 7 | 339 | 4.4 | -52% | 0.19 | 3.4 | 0 | n/a | n/a |
| Ghaggar Bhankarpur | ecmwf_ifs025 | 0 | 339 | 6.1 | -19% | 0.51 | 4.4 | 12 | 0.25 | 0.25 |
| Ghaggar Bhankarpur | ecmwf_ifs025 | 1 | 339 | 6.1 | +1% | 0.59 | 5.2 | 12 | 0.42 | 0.17 |
| Ghaggar Bhankarpur | ecmwf_ifs025 | 2 | 339 | 6.1 | +9% | 0.53 | 5.6 | 12 | 0.33 | 0.33 |
| Ghaggar Bhankarpur | ecmwf_ifs025 | 3 | 339 | 6.1 | +16% | 0.43 | 6.0 | 12 | 0.33 | 0.56 |
| Ghaggar Bhankarpur | ecmwf_ifs025 | 4 | 339 | 6.1 | +23% | 0.34 | 6.4 | 12 | 0.17 | 0.82 |
| Ghaggar Bhankarpur | ecmwf_ifs025 | 5 | 339 | 6.1 | +22% | 0.31 | 6.7 | 12 | 0.17 | 0.82 |
| Ghaggar Bhankarpur | ecmwf_ifs025 | 6 | 339 | 6.1 | +29% | 0.41 | 6.7 | 12 | 0.17 | 0.78 |
| Ghaggar Bhankarpur | ecmwf_ifs025 | 7 | 339 | 6.1 | +34% | 0.32 | 7.2 | 12 | 0.08 | 0.92 |
| Ghaggar Bhankarpur | gfs_seamless | 0 | 339 | 6.1 | -14% | 0.49 | 5.2 | 12 | 0.33 | 0.33 |
| Ghaggar Bhankarpur | gfs_seamless | 1 | 339 | 6.1 | -9% | 0.47 | 5.3 | 12 | 0.17 | 0.71 |
| Ghaggar Bhankarpur | gfs_seamless | 2 | 339 | 6.1 | +8% | 0.31 | 6.3 | 12 | 0.17 | 0.75 |
| Ghaggar Bhankarpur | gfs_seamless | 3 | 339 | 6.1 | +33% | 0.24 | 7.8 | 12 | 0.17 | 0.87 |
| Ghaggar Bhankarpur | gfs_seamless | 4 | 339 | 6.1 | +33% | 0.20 | 8.0 | 12 | 0.08 | 0.95 |
| Ghaggar Bhankarpur | gfs_seamless | 5 | 339 | 6.1 | -31% | 0.18 | 5.7 | 12 | 0.00 | 1.00 |
| Ghaggar Bhankarpur | gfs_seamless | 6 | 339 | 6.1 | -46% | 0.19 | 5.5 | 12 | 0.00 | 1.00 |
| Ghaggar Bhankarpur | gfs_seamless | 7 | 339 | 6.1 | -47% | 0.10 | 5.8 | 12 | 0.00 | 1.00 |
| Ghaggar Khanauri | ecmwf_ifs025 | 0 | 339 | 5.8 | -15% | 0.56 | 3.9 | 11 | 0.27 | 0.25 |
| Ghaggar Khanauri | ecmwf_ifs025 | 1 | 339 | 5.8 | +4% | 0.62 | 4.8 | 11 | 0.36 | 0.33 |
| Ghaggar Khanauri | ecmwf_ifs025 | 2 | 339 | 5.8 | +11% | 0.55 | 5.1 | 11 | 0.36 | 0.43 |
| Ghaggar Khanauri | ecmwf_ifs025 | 3 | 339 | 5.8 | +20% | 0.45 | 5.6 | 11 | 0.27 | 0.67 |
| Ghaggar Khanauri | ecmwf_ifs025 | 4 | 339 | 5.8 | +23% | 0.38 | 5.8 | 11 | 0.18 | 0.85 |
| Ghaggar Khanauri | ecmwf_ifs025 | 5 | 339 | 5.8 | +25% | 0.32 | 6.1 | 11 | 0.00 | 1.00 |
| Ghaggar Khanauri | ecmwf_ifs025 | 6 | 339 | 5.8 | +33% | 0.45 | 6.1 | 11 | 0.18 | 0.78 |
| Ghaggar Khanauri | ecmwf_ifs025 | 7 | 339 | 5.8 | +34% | 0.36 | 6.5 | 11 | 0.09 | 0.90 |
| Ghaggar Khanauri | gfs_seamless | 0 | 339 | 5.8 | -18% | 0.47 | 4.7 | 11 | 0.18 | 0.60 |
| Ghaggar Khanauri | gfs_seamless | 1 | 339 | 5.8 | -10% | 0.44 | 4.9 | 11 | 0.18 | 0.67 |
| Ghaggar Khanauri | gfs_seamless | 2 | 339 | 5.8 | +5% | 0.36 | 5.5 | 11 | 0.18 | 0.75 |
| Ghaggar Khanauri | gfs_seamless | 3 | 339 | 5.8 | +28% | 0.26 | 7.0 | 11 | 0.18 | 0.86 |
| Ghaggar Khanauri | gfs_seamless | 4 | 339 | 5.8 | +34% | 0.21 | 7.5 | 11 | 0.09 | 0.94 |
| Ghaggar Khanauri | gfs_seamless | 5 | 339 | 5.8 | -33% | 0.23 | 5.1 | 11 | 0.09 | 0.67 |
| Ghaggar Khanauri | gfs_seamless | 6 | 339 | 5.8 | -48% | 0.21 | 5.0 | 11 | 0.00 | 1.00 |
| Ghaggar Khanauri | gfs_seamless | 7 | 339 | 5.8 | -49% | 0.14 | 5.3 | 11 | 0.00 | n/a |
| Pong | ecmwf_ifs025 | 0 | 339 | 8.9 | -16% | 0.61 | 4.7 | 17 | 0.29 | 0.58 |
| Pong | ecmwf_ifs025 | 1 | 339 | 8.9 | -22% | 0.61 | 4.9 | 17 | 0.24 | 0.56 |
| Pong | ecmwf_ifs025 | 2 | 339 | 8.9 | -11% | 0.60 | 5.3 | 17 | 0.29 | 0.58 |
| Pong | ecmwf_ifs025 | 3 | 339 | 8.9 | -11% | 0.49 | 5.8 | 17 | 0.12 | 0.78 |
| Pong | ecmwf_ifs025 | 4 | 339 | 8.9 | -11% | 0.57 | 5.5 | 17 | 0.18 | 0.57 |
| Pong | ecmwf_ifs025 | 5 | 339 | 8.9 | -9% | 0.53 | 5.8 | 17 | 0.18 | 0.70 |
| Pong | ecmwf_ifs025 | 6 | 339 | 8.9 | -7% | 0.52 | 6.0 | 17 | 0.24 | 0.56 |
| Pong | ecmwf_ifs025 | 7 | 339 | 8.9 | -1% | 0.57 | 5.8 | 17 | 0.18 | 0.77 |
| Pong | gfs_seamless | 0 | 339 | 8.9 | -6% | 0.59 | 5.5 | 17 | 0.29 | 0.55 |
| Pong | gfs_seamless | 1 | 339 | 8.9 | -18% | 0.50 | 5.7 | 17 | 0.12 | 0.75 |
| Pong | gfs_seamless | 2 | 339 | 8.9 | -19% | 0.51 | 5.9 | 17 | 0.06 | 0.80 |
| Pong | gfs_seamless | 3 | 339 | 8.9 | -8% | 0.47 | 6.3 | 17 | 0.12 | 0.75 |
| Pong | gfs_seamless | 4 | 339 | 8.9 | +4% | 0.39 | 6.8 | 17 | 0.06 | 0.92 |
| Pong | gfs_seamless | 5 | 339 | 8.9 | -46% | 0.31 | 6.8 | 17 | 0.00 | 1.00 |
| Pong | gfs_seamless | 6 | 339 | 8.9 | -56% | 0.27 | 7.1 | 17 | 0.00 | 1.00 |
| Pong | gfs_seamless | 7 | 339 | 8.9 | -55% | 0.18 | 7.2 | 17 | 0.00 | 1.00 |
| Ranjit Sagar | ecmwf_ifs025 | 0 | 339 | 7.9 | -5% | 0.74 | 4.2 | 16 | 0.38 | 0.33 |
| Ranjit Sagar | ecmwf_ifs025 | 1 | 339 | 7.9 | -26% | 0.72 | 4.6 | 16 | 0.25 | 0.20 |
| Ranjit Sagar | ecmwf_ifs025 | 2 | 339 | 7.9 | -14% | 0.63 | 5.1 | 16 | 0.19 | 0.62 |
| Ranjit Sagar | ecmwf_ifs025 | 3 | 339 | 7.9 | -17% | 0.60 | 5.2 | 16 | 0.25 | 0.50 |
| Ranjit Sagar | ecmwf_ifs025 | 4 | 339 | 7.9 | -16% | 0.66 | 4.9 | 16 | 0.12 | 0.60 |
| Ranjit Sagar | ecmwf_ifs025 | 5 | 339 | 7.9 | -13% | 0.54 | 5.3 | 16 | 0.12 | 0.75 |
| Ranjit Sagar | ecmwf_ifs025 | 6 | 339 | 7.9 | -18% | 0.59 | 5.3 | 16 | 0.12 | 0.60 |
| Ranjit Sagar | ecmwf_ifs025 | 7 | 339 | 7.9 | -14% | 0.61 | 5.3 | 16 | 0.12 | 0.60 |
| Ranjit Sagar | gfs_seamless | 0 | 339 | 7.9 | +0% | 0.67 | 5.3 | 16 | 0.25 | 0.56 |
| Ranjit Sagar | gfs_seamless | 1 | 339 | 7.9 | -13% | 0.62 | 5.1 | 16 | 0.19 | 0.50 |
| Ranjit Sagar | gfs_seamless | 2 | 339 | 7.9 | -17% | 0.53 | 5.5 | 16 | 0.06 | 0.67 |
| Ranjit Sagar | gfs_seamless | 3 | 339 | 7.9 | -12% | 0.45 | 5.7 | 16 | 0.06 | 0.67 |
| Ranjit Sagar | gfs_seamless | 4 | 339 | 7.9 | +2% | 0.35 | 6.5 | 16 | 0.12 | 0.80 |
| Ranjit Sagar | gfs_seamless | 5 | 339 | 7.9 | -43% | 0.40 | 5.8 | 16 | 0.06 | 0.67 |
| Ranjit Sagar | gfs_seamless | 6 | 339 | 7.9 | -56% | 0.33 | 6.1 | 16 | 0.00 | 1.00 |
| Ranjit Sagar | gfs_seamless | 7 | 339 | 7.9 | -57% | 0.27 | 6.2 | 16 | 0.00 | n/a |

### Multiplicative bias correction, tested out of sample

One factor per catchment, model and lead (observed season rain over forecast season rain, clipped to 0.5 to 2), fitted on every season but one and applied to the held-out season; the held-out days of all seasons are scored together. Pearson r does not move under a scale factor, so the columns that can move are shown raw and corrected. Leads 1 to 5 are the product's horizons.

| catchment | model | lead (days) | days | held-out factors | bias raw / corrected | MAE (mm) raw / corrected | hit rate raw / corrected | false-alarm ratio raw / corrected |
|---|---|---|---|---|---|---|---|---|
| Bhakra | ecmwf_ifs025 | 1 | 339 | 1.08 to 1.25 | -16% / -1% | 2.1 / 2.3 | n/a / n/a | n/a / n/a |
| Bhakra | ecmwf_ifs025 | 2 | 339 | 1.07 to 1.20 | -12% / -1% | 2.2 / 2.3 | n/a / n/a | 1.00 / 1.00 |
| Bhakra | ecmwf_ifs025 | 3 | 339 | 1.04 to 1.22 | -11% / -1% | 2.4 / 2.6 | n/a / n/a | n/a / 1.00 |
| Bhakra | ecmwf_ifs025 | 4 | 339 | 1.02 to 1.19 | -10% / -1% | 2.6 / 2.8 | n/a / n/a | 1.00 / 1.00 |
| Bhakra | ecmwf_ifs025 | 5 | 339 | 0.99 to 1.18 | -8% / -2% | 2.6 / 2.8 | n/a / n/a | n/a / n/a |
| Bhakra | gfs_seamless | 1 | 339 | 1.02 to 1.10 | -6% / -1% | 2.5 / 2.6 | n/a / n/a | 1.00 / 1.00 |
| Bhakra | gfs_seamless | 2 | 339 | 0.93 to 1.11 | -4% / -1% | 2.8 / 2.9 | n/a / n/a | n/a / n/a |
| Bhakra | gfs_seamless | 3 | 339 | 0.85 to 1.04 | +3% / -1% | 3.1 / 3.1 | n/a / n/a | n/a / n/a |
| Bhakra | gfs_seamless | 4 | 339 | 0.77 to 0.94 | +13% / -1% | 3.0 / 2.9 | n/a / n/a | 1.00 / n/a |
| Bhakra | gfs_seamless | 5 | 339 | 1.35 to 2.00 | -41% / -1% | 3.1 / 3.8 | n/a / n/a | n/a / 1.00 |
| Ghaggar Bhankarpur | ecmwf_ifs025 | 1 | 339 | 0.96 to 1.04 | +1% / -1% | 5.2 / 5.1 | 0.42 / 0.33 | 0.17 / 0.20 |
| Ghaggar Bhankarpur | ecmwf_ifs025 | 2 | 339 | 0.84 to 0.98 | +9% / +1% | 5.6 / 5.5 | 0.33 / 0.33 | 0.33 / 0.33 |
| Ghaggar Bhankarpur | ecmwf_ifs025 | 3 | 339 | 0.83 to 0.91 | +16% / -1% | 6.0 / 5.6 | 0.33 / 0.33 | 0.56 / 0.50 |
| Ghaggar Bhankarpur | ecmwf_ifs025 | 4 | 339 | 0.77 to 0.86 | +23% / -1% | 6.4 / 5.8 | 0.17 / 0.08 | 0.82 / 0.86 |
| Ghaggar Bhankarpur | ecmwf_ifs025 | 5 | 339 | 0.78 to 0.86 | +22% / -1% | 6.7 / 6.0 | 0.17 / 0.00 | 0.82 / 1.00 |
| Ghaggar Bhankarpur | gfs_seamless | 1 | 339 | 1.00 to 1.15 | -9% / +2% | 5.3 / 5.6 | 0.17 / 0.17 | 0.71 / 0.78 |
| Ghaggar Bhankarpur | gfs_seamless | 2 | 339 | 0.81 to 1.01 | +8% / -1% | 6.3 / 6.0 | 0.17 / 0.17 | 0.75 / 0.71 |
| Ghaggar Bhankarpur | gfs_seamless | 3 | 339 | 0.64 to 0.84 | +33% / -1% | 7.8 / 6.6 | 0.17 / 0.17 | 0.87 / 0.83 |
| Ghaggar Bhankarpur | gfs_seamless | 4 | 339 | 0.63 to 0.85 | +33% / -0% | 8.0 / 6.8 | 0.08 / 0.08 | 0.95 / 0.86 |
| Ghaggar Bhankarpur | gfs_seamless | 5 | 339 | 1.15 to 1.86 | -31% / +2% | 5.7 / 7.0 | 0.00 / 0.00 | 1.00 / 1.00 |
| Ghaggar Khanauri | ecmwf_ifs025 | 1 | 339 | 0.91 to 1.00 | +4% / +0% | 4.8 / 4.7 | 0.36 / 0.36 | 0.33 / 0.33 |
| Ghaggar Khanauri | ecmwf_ifs025 | 2 | 339 | 0.80 to 0.98 | +11% / +3% | 5.1 / 4.9 | 0.36 / 0.27 | 0.43 / 0.50 |
| Ghaggar Khanauri | ecmwf_ifs025 | 3 | 339 | 0.79 to 0.86 | +20% / +1% | 5.6 / 5.1 | 0.27 / 0.27 | 0.67 / 0.67 |
| Ghaggar Khanauri | ecmwf_ifs025 | 4 | 339 | 0.76 to 0.85 | +23% / +1% | 5.8 / 5.3 | 0.18 / 0.18 | 0.85 / 0.67 |
| Ghaggar Khanauri | ecmwf_ifs025 | 5 | 339 | 0.76 to 0.82 | +25% / +0% | 6.1 / 5.5 | 0.00 / 0.00 | 1.00 / 1.00 |
| Ghaggar Khanauri | gfs_seamless | 1 | 339 | 0.98 to 1.27 | -10% / +5% | 4.9 / 5.4 | 0.18 / 0.18 | 0.67 / 0.83 |
| Ghaggar Khanauri | gfs_seamless | 2 | 339 | 0.88 to 1.01 | +5% / -1% | 5.5 / 5.4 | 0.18 / 0.18 | 0.75 / 0.67 |
| Ghaggar Khanauri | gfs_seamless | 3 | 339 | 0.70 to 0.86 | +28% / -0% | 7.0 / 6.1 | 0.18 / 0.18 | 0.86 / 0.82 |
| Ghaggar Khanauri | gfs_seamless | 4 | 339 | 0.67 to 0.82 | +34% / -0% | 7.5 / 6.3 | 0.09 / 0.09 | 0.94 / 0.86 |
| Ghaggar Khanauri | gfs_seamless | 5 | 339 | 1.22 to 1.86 | -33% / +1% | 5.1 / 6.3 | 0.09 / 0.09 | 0.67 / 0.89 |
| Pong | ecmwf_ifs025 | 1 | 339 | 1.15 to 1.37 | -22% / -2% | 4.9 / 5.3 | 0.24 / 0.24 | 0.56 / 0.64 |
| Pong | ecmwf_ifs025 | 2 | 339 | 1.01 to 1.22 | -11% / -2% | 5.3 / 5.6 | 0.29 / 0.29 | 0.58 / 0.62 |
| Pong | ecmwf_ifs025 | 3 | 339 | 0.99 to 1.25 | -11% / -2% | 5.8 / 6.2 | 0.12 / 0.12 | 0.78 / 0.78 |
| Pong | ecmwf_ifs025 | 4 | 339 | 0.99 to 1.22 | -11% / -2% | 5.5 / 5.8 | 0.18 / 0.18 | 0.57 / 0.75 |
| Pong | ecmwf_ifs025 | 5 | 339 | 0.93 to 1.21 | -9% / -2% | 5.8 / 6.3 | 0.18 / 0.18 | 0.70 / 0.77 |
| Pong | gfs_seamless | 1 | 339 | 1.11 to 1.29 | -18% / -2% | 5.7 / 6.1 | 0.12 / 0.12 | 0.75 / 0.78 |
| Pong | gfs_seamless | 2 | 339 | 1.01 to 1.35 | -19% / -2% | 5.9 / 6.5 | 0.06 / 0.06 | 0.80 / 0.86 |
| Pong | gfs_seamless | 3 | 339 | 0.87 to 1.25 | -8% / -0% | 6.3 / 6.9 | 0.12 / 0.06 | 0.75 / 0.86 |
| Pong | gfs_seamless | 4 | 339 | 0.76 to 1.08 | +4% / -1% | 6.8 / 7.0 | 0.06 / 0.06 | 0.92 / 0.92 |
| Pong | gfs_seamless | 5 | 339 | 1.38 to 2.00 | -46% / -6% | 6.8 / 8.1 | 0.00 / 0.00 | 1.00 / 1.00 |
| Ranjit Sagar | ecmwf_ifs025 | 1 | 339 | 1.29 to 1.37 | -26% / -1% | 4.6 / 4.7 | 0.25 / 0.31 | 0.20 / 0.44 |
| Ranjit Sagar | ecmwf_ifs025 | 2 | 339 | 1.11 to 1.20 | -14% / -1% | 5.1 / 5.4 | 0.19 / 0.31 | 0.62 / 0.67 |
| Ranjit Sagar | ecmwf_ifs025 | 3 | 339 | 1.16 to 1.23 | -17% / -1% | 5.2 / 5.4 | 0.25 / 0.25 | 0.50 / 0.56 |
| Ranjit Sagar | ecmwf_ifs025 | 4 | 339 | 1.11 to 1.24 | -16% / -1% | 4.9 / 5.2 | 0.12 / 0.25 | 0.60 / 0.64 |
| Ranjit Sagar | ecmwf_ifs025 | 5 | 339 | 1.05 to 1.19 | -13% / -1% | 5.3 / 5.6 | 0.12 / 0.12 | 0.75 / 0.78 |
| Ranjit Sagar | gfs_seamless | 1 | 339 | 1.07 to 1.20 | -13% / -1% | 5.1 / 5.3 | 0.19 / 0.19 | 0.50 / 0.50 |
| Ranjit Sagar | gfs_seamless | 2 | 339 | 1.02 to 1.32 | -17% / -1% | 5.5 / 5.9 | 0.06 / 0.12 | 0.67 / 0.67 |
| Ranjit Sagar | gfs_seamless | 3 | 339 | 0.91 to 1.34 | -12% / +1% | 5.7 / 6.4 | 0.06 / 0.06 | 0.67 / 0.83 |
| Ranjit Sagar | gfs_seamless | 4 | 339 | 0.81 to 1.15 | +2% / +1% | 6.5 / 6.6 | 0.12 / 0.06 | 0.80 / 0.88 |
| Ranjit Sagar | gfs_seamless | 5 | 339 | 1.36 to 2.00 | -43% / -1% | 5.8 / 7.1 | 0.06 / 0.12 | 0.67 / 0.88 |

Held-out days, dam catchments, leads 1 to 5: MAE lower after correction in 1 of 30 rows, heavy-day hit rate higher in 5, false-alarm ratio higher in 16. The product applies a correction only when MAE and hit rate both improve on the held-out seasons for a dam catchment; the rule is in `design.md`.

## Live 2026: one-day inflow prediction against the BBMB bulletins

Persistence (tomorrow's inflow equals today's) is the baseline any one-day prediction has to beat; the model's base component is that persistence with the rain response added, so the difference between the two rows is what the rain brings.

| dam | days | mean observed (cusecs) | mean predicted (cusecs) | bias | Pearson r | MAE (cusecs) | persistence bias | persistence r | persistence MAE |
|---|---|---|---|---|---|---|---|---|---|
| Bhakra | 26 | 42,141 | 41,447 | -2% | +0.46 | 4,567 | -0% | +0.56 | 4,463 |
| Pong | 26 | 37,862 | 36,970 | -2% | +0.38 | 11,594 | -0% | +0.33 | 12,557 |

## Prospective record, 2026 season

Issued daily from the committed inputs and the live BBMB bulletin; a record is never rewritten (`outputs/forecast/`). P(spillway forced) is at the five-day horizon.

1 issue date from 2026-09-05 to 2026-09-05. Bhakra: P(spillway forced) above zero on 0 of 1 days. Pong: P(spillway forced) above zero on 0 of 1 days. Days with any control point at or above the WRD low band: 0.

No day so far has put a forced spill or a classed arrival on the record.
