# Verification report

Rendered from `outputs/verification/` (results.json, peak_tests.csv). Regenerate with `punjabflood verify` then `punjabflood report`.

## Inflow model parameters

Fitted by non-negative least squares on day-to-day changes of measured storage (CWC table, or the CWC level through the dam's own rating) against lagged catchment rain volumes; spilling days and implausible jumps excluded. The recession is the lag-2 to lag-1 autocovariance ratio of the residuals, clipped to [0.50, 0.99]; a raw ratio above the clip means the residual drifts through the season (base flow and outflow both move slowly) rather than recessing, so the base is carried as nearly constant over the horizon.

| dam | area used (km2) | runoff coefficient c (dry) | c_wet per 100 mm antecedent | lag weights w0..w3 | recession (raw ratio) | gamma | R2 | RMSE (BCM/day) | days | wetness carrier |
|---|---|---|---|---|---|---|---|---|---|---|
| Bhakra | 25,762 | 0.145 | 0.282 | 0.54, 0.28, 0.08, 0.09 | 0.990 (1.888) | 0.00 | 0.221 | 0.0431 | 1009 | api |
| Pong | 13,637 | 0.203 | 0.328 | 0.35, 0.48, 0.09, 0.08 | 0.990 (1.051) | 0.00 | 0.777 | 0.0296 | 733 | api |
| Ranjit Sagar | 6,953 | 0.131 | 0.263 | 0.62, 0.24, 0.08, 0.05 | 0.990 (2.219) | 0.00 | 0.398 | 0.0224 | 1184 | api |
The coefficient in force on a day is c plus c_wet times the previous five days' catchment rain over 100 mm, capped at 0.95, times one plus gamma times the ERA5-Land 0-7 cm soil-moisture anomaly (fractional, against a 31-day day-of-year climatology) where the wetness carrier includes soil moisture (`api+sm` or `sm`; gamma is zero under `api`).

## Annual peak class, 38 years (1988 to 2025)

For each WRD peak table, the predictors ranked by area under the ROC curve for the department's High class. Spearman rho is against the peak discharge itself; the Brier skill score compares leave-one-year-out logistic probabilities with the climatological base rate (positive is skill).

### dhilwan

| predictor | years | High years | Spearman rho | AUROC (High) | Brier skill |
|---|---|---|---|---|---|
| Pong_days_above_95pct | 11 | 2 | +0.62 | 1.00 | +0.55 |
| Pong_frac_max | 11 | 2 | +0.76 | 1.00 | +0.30 |
| Pong_release_pp_max | 11 | 2 | +0.63 | 1.00 | +0.72 |
| Pong_hei_pp_max | 11 | 2 | +0.75 | 1.00 | +0.51 |
| Pong_frac_aug01 | 10 | 1 | +0.48 | 1.00 | -0.04 |
| Ranjit Sagar_frac_aug01 | 10 | 1 | +0.71 | 1.00 | -0.04 |
| Ranjit Sagar_max10d_bcm | 38 | 5 | +0.36 | 0.99 | +0.62 |
| Ranjit Sagar_max5d_bcm | 38 | 5 | +0.33 | 0.98 | +0.49 |
| Beas local_season_bcm | 38 | 5 | +0.51 | 0.98 | +0.36 |
| Ranjit Sagar_max3d_bcm | 38 | 5 | +0.34 | 0.96 | +0.45 |

Other pre-named predictors:

| predictor | years | High years | Spearman rho | AUROC (High) | Brier skill |
|---|---|---|---|---|---|
| Pong_frac_aug15 | 11 | 2 | +0.93 | 0.94 | +0.25 |
| Bhakra_hei_pp_max | 11 | 2 | +0.69 | 0.89 | +0.06 |
| Pong_max3d_bcm | 38 | 5 | +0.40 | 0.87 | +0.26 |
| Pong_max5d_bcm | 38 | 5 | +0.44 | 0.87 | +0.22 |
| sutlej_beas_max5d_bcm | 38 | 5 | +0.48 | 0.86 | +0.10 |
| Bhakra_frac_aug15 | 11 | 2 | +0.64 | 0.83 | +0.01 |
| Bhakra_max5d_bcm | 38 | 5 | +0.37 | 0.83 | -0.10 |
| sutlej_beas_max3d_bcm | 38 | 5 | +0.42 | 0.82 | +0.06 |

### harike_hussainiwala

| predictor | years | High years | Spearman rho | AUROC (High) | Brier skill |
|---|---|---|---|---|---|
| Pong_days_above_95pct | 11 | 2 | +0.68 | 1.00 | +0.55 |
| Pong_frac_max | 11 | 2 | +0.87 | 1.00 | +0.30 |
| Pong_release_pp_max | 11 | 2 | +0.67 | 1.00 | +0.72 |
| Pong_hei_pp_max | 11 | 2 | +0.88 | 1.00 | +0.51 |
| Pong_frac_aug01 | 10 | 1 | +0.49 | 1.00 | -0.04 |
| Ranjit Sagar_frac_aug01 | 10 | 1 | +0.73 | 1.00 | -0.04 |
| Ranjit Sagar_max10d_bcm | 38 | 5 | +0.62 | 0.99 | +0.62 |
| Ranjit Sagar_max5d_bcm | 38 | 5 | +0.56 | 0.98 | +0.49 |
| Beas local_season_bcm | 38 | 5 | +0.67 | 0.98 | +0.36 |
| Ranjit Sagar_max3d_bcm | 38 | 5 | +0.57 | 0.96 | +0.45 |

Other pre-named predictors:

| predictor | years | High years | Spearman rho | AUROC (High) | Brier skill |
|---|---|---|---|---|---|
| Pong_frac_aug15 | 11 | 2 | +0.75 | 0.94 | +0.25 |
| Bhakra_hei_pp_max | 11 | 2 | +0.84 | 0.89 | +0.06 |
| Pong_max3d_bcm | 38 | 5 | +0.47 | 0.87 | +0.26 |
| Pong_max5d_bcm | 38 | 5 | +0.57 | 0.87 | +0.22 |
| sutlej_beas_max5d_bcm | 38 | 5 | +0.64 | 0.86 | +0.10 |
| Bhakra_frac_aug15 | 11 | 2 | +0.67 | 0.83 | +0.01 |
| Bhakra_max5d_bcm | 38 | 5 | +0.53 | 0.83 | -0.10 |
| sutlej_beas_max3d_bcm | 38 | 5 | +0.60 | 0.82 | +0.06 |

### ropar

| predictor | years | High years | Spearman rho | AUROC (High) | Brier skill |
|---|---|---|---|---|---|
| Pong_days_above_95pct | 11 | 2 | +0.57 | 1.00 | +0.55 |
| Pong_frac_max | 11 | 2 | +0.70 | 1.00 | +0.30 |
| Pong_release_pp_max | 11 | 2 | +0.58 | 1.00 | +0.72 |
| Pong_hei_pp_max | 11 | 2 | +0.69 | 1.00 | +0.51 |
| Pong_frac_aug01 | 10 | 1 | +0.56 | 1.00 | -0.04 |
| Ranjit Sagar_frac_aug01 | 10 | 1 | +0.56 | 1.00 | -0.04 |
| Ranjit Sagar_max10d_bcm | 38 | 5 | +0.52 | 0.99 | +0.62 |
| Ranjit Sagar_max5d_bcm | 38 | 5 | +0.49 | 0.98 | +0.49 |
| Beas local_season_bcm | 38 | 5 | +0.62 | 0.98 | +0.36 |
| Ranjit Sagar_max3d_bcm | 38 | 5 | +0.49 | 0.96 | +0.45 |

Other pre-named predictors:

| predictor | years | High years | Spearman rho | AUROC (High) | Brier skill |
|---|---|---|---|---|---|
| Pong_frac_aug15 | 11 | 2 | +0.59 | 0.94 | +0.25 |
| Bhakra_hei_pp_max | 11 | 2 | +0.68 | 0.89 | +0.06 |
| Pong_max3d_bcm | 38 | 5 | +0.31 | 0.87 | +0.26 |
| Pong_max5d_bcm | 38 | 5 | +0.40 | 0.87 | +0.22 |
| sutlej_beas_max5d_bcm | 38 | 5 | +0.52 | 0.86 | +0.10 |
| Bhakra_frac_aug15 | 11 | 2 | +0.65 | 0.83 | +0.01 |
| Bhakra_max5d_bcm | 38 | 5 | +0.49 | 0.83 | -0.10 |
| sutlej_beas_max3d_bcm | 38 | 5 | +0.48 | 0.82 | +0.06 |

## Event timing: routed perfect-prognosis release versus the dated Dhilwan peaks

The forced release of a full Pong reservoir under the observed rain (one-day-ahead spill of each day's run, placed on the day it happens) is routed to Dhilwan with the Annexure Z travel times and compared with the department's dated peak. The river release on a spill day is the spill plus the turbine passage less the Mukerian Hydel Channel's capacity (a full reservoir passes its inflow, so the turbines run); this is the lower bound on what the dam sends down the Beas, and the spill-only row below it is the lower bound of that. The rows with the local term add the runoff of the land between Pong and Dhilwan (the Beas local catchment, the HydroBASINS sub-basins that drain to Dhilwan below the dam) from its own IMD rain, with a dam's calibrated response transferred because no gauge exists to fit one on: Pong's response as the primary, Ranjit Sagar's (the lowest fitted coefficient) as the sensitivity; no base flow, so the term is a lower bound, and it arrives on the day it runs off. The storage that drives the index comes from the public record, which is weekly in August 2023 and a handful of press points in August 2025; between measurements the reservoir is carried by the model's own water balance under the observed rain (one-day inflow less the non-spill passage), and every measurement re-anchors it.

The rows marked flood cushion let Pong rise to 1400 ft (7.290 BCM live, the design pair in the emergency action plan) before the spillway must open, against 6.157 BCM at the reduced FRL in the other rows; the storage above FRL is rated on the straight line between the two published points. The dam did rise into the cushion in both events, so the two settings bracket what BBMB did: the FRL bound fires early and high, the cushion bound late and low.

### The operator's schedule at Bhakra

The forced release above is the spillway's bound. BBMB opens the gates earlier, under a filling schedule; the one in hand for Bhakra (2019 chart (CBIP RTDSS presentation, page 44)) reads 1,650 ft up to 31 July; 1,670 ft up to 15 August; 1,680 ft up to 31 August, a level holding up to its date and a straight line from the last point below FRL to the date FRL may be reached. The press quotes a guideline of 1,662 ft for 19 August 2025, below that line, so the schedule has been lowered since and this scenario is the 2019 rule. For each dated gate opening, the first day of the season on which each bound forces a release (the schedule bound counting a release above a tenth of the turbine passage), and its lag from the opening; the storage between measurements is the model's carry.

| year | gates opened | level then (ft) | schedule level that day (ft) | first forced, FRL bound | lag (days) | first forced, schedule bound | lag (days) |
|---|---|---|---|---|---|---|---|
| 2015 | 2015-08-10 | 1,661.10 | 1,670.0 | none in the season | n/a | 2015-08-17 | +7 |
| 2023 | 2023-08-13 | 1,672.00 | 1,670.0 | none in the season | n/a | 2023-07-25 | -19 |
| 2025 | 2025-08-19 | 1,665.06 | 1,672.5 | none in the season | n/a | 2025-09-01 | +13 |

### The routed release on the days the press quoted the gauges

The dated press readings of the river gauges (moment readings, ambiguous rows left out) against the routed Pong release (spill plus passage, no local term) on the same day, as a ratio; a check of the hydrograph's level on dated days, not a fit.

| station | date | quoted (cusecs) | routed (cusecs) | ratio |
|---|---|---|---|---|
| Dhilwan | 2023-08-17 | 234,000 | 181,686 | 0.78 |
| Dhilwan | 2023-08-18 | 220,000 | 181,686 | 0.83 |
| Dhilwan | 2023-08-20 | 155,500 | 52,268 | 0.34 |
| Dhilwan | 2023-08-21 | 139,000 | 38,388 | 0.28 |
| Dhilwan | 2023-08-23 | 136,000 | 0 | 0.00 |
| Dhilwan | 2025-08-24 | 130,000 | 0 | 0.00 |
| Dhilwan | 2025-08-25 | 140,000 | 0 | 0.00 |
| Ferozepur Head Works | 2023-08-18 | 258,910 | 103,483 | 0.40 |
| Ferozepur Head Works | 2023-08-20 | 225,000 | 181,686 | 0.81 |
| Ferozepur Head Works | 2023-08-21 | 156,000 | 92,820 | 0.59 |
| Ferozepur Head Works | 2023-08-23 | 133,224 | 38,388 | 0.29 |
| Ferozepur Head Works | 2025-08-21 | 82,725 | 0 | 0.00 |
| Ferozepur Head Works | 2025-09-03 | 324,000 | 114,036 | 0.35 |
| Ferozepur Head Works | 2025-09-03 | 302,508 | 114,036 | 0.38 |
| Ferozepur Head Works | 2025-09-03 | 301,918 | 114,036 | 0.38 |
| Harike Head Works | 2023-08-17 | 235,000 | 0 | 0.00 |
| Harike Head Works | 2023-08-17 | 215,000 | 0 | 0.00 |
| Harike Head Works | 2023-08-18 | 284,987 | 103,483 | 0.36 |
| Harike Head Works | 2023-08-20 | 169,000 | 92,820 | 0.55 |
| Harike Head Works | 2023-08-21 | 160,000 | 52,268 | 0.33 |
| Harike Head Works | 2023-08-23 | 142,766 | 0 | 0.00 |
| Harike Head Works | 2025-08-21 | 94,929 | 0 | 0.00 |
| Harike Head Works | 2025-09-03 | 330,000 | 109,794 | 0.33 |
| Harike Head Works | 2025-09-03 | 335,030 | 109,794 | 0.33 |
| Harike Head Works | 2025-09-03 | 318,159 | 109,794 | 0.35 |

| year | release routed | predicted peak date | predicted peak (cusecs) | observed peak date | observed peak (cusecs) | lag (days) | magnitude ratio |
|---|---|---|---|---|---|---|---|
| 2023 | spill + passage | 2023-08-17 | 181,686 | 2023-08-17 | 237,500 | +0 | 0.76 |
| 2025 | spill + passage | 2025-08-28 | 192,037 | 2025-08-31 | 235,494 | -3 | 0.82 |
| 2023 | spill + passage, flood cushion | no predicted release | | | | | |
| 2025 | spill + passage, flood cushion | 2025-09-04 | 140,329 | 2025-08-31 | 235,494 | +4 | 0.60 |
| 2023 | spill only | 2023-08-17 | 147,586 | 2023-08-17 | 237,500 | +0 | 0.62 |
| 2025 | spill only | 2025-08-28 | 157,937 | 2025-08-31 | 235,494 | -3 | 0.67 |
| 2023 | spill + passage + local inflow, Pong response | 2023-08-17 | 186,401 | 2023-08-17 | 237,500 | +0 | 0.78 |
| 2025 | spill + passage + local inflow, Pong response | 2025-08-28 | 219,352 | 2025-08-31 | 235,494 | -3 | 0.93 |
| 2023 | spill + passage + local inflow, Ranjit Sagar response | 2023-08-17 | 184,154 | 2023-08-17 | 237,500 | +0 | 0.78 |
| 2025 | spill + passage + local inflow, Ranjit Sagar response | 2025-08-28 | 207,581 | 2025-08-31 | 235,494 | -3 | 0.88 |

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
| Bhakra | mean, 2025-08-01 to 2025-08-24 | 24 | 57,430 | 54,832 | 0.95 | PAC data via The Wire, 8 Sep 2025 |
| Bhakra | mean, 2025-08-25 to 2025-09-04 | 11 | 73,400 | 80,653 | 1.10 | PAC data via The Wire, 8 Sep 2025 |
| Pong | mean, 2025-08-01 to 2025-08-24 | 19 | 77,000 | 83,012 | 1.08 | PAC data via The Wire, 8 Sep 2025 |
| Pong | mean, 2025-08-25 to 2025-09-04 | 11 | 121,600 | 137,283 | 1.13 | PAC data via The Wire, 8 Sep 2025 |
| Ranjit Sagar | mean, 2025-08-01 to 2025-08-24 | 20 | 38,700 | 30,075 | 0.78 | PAC data via The Wire, 8 Sep 2025 |
| Ranjit Sagar | mean, 2025-08-25 to 2025-09-04 | 11 | 71,960 | 69,098 | 0.96 | PAC data via The Wire, 8 Sep 2025 |
| Bhakra | day, 2015-05-27 | 0 | 27,137 | n/a | n/a | dry spell leads to drop in water level in 3 dams |
| Pong | day, 2015-05-27 | 0 | 5,278 | n/a | n/a | dry spell leads to drop in water level in 3 dams |
| Bhakra | day, 2016-03-31 | 0 | 6,750 | n/a | n/a | bhakra water level plummets |
| Bhakra | day, 2016-05-27 | 0 | 18,560 | n/a | n/a | dry spell leads to drop in water level in 3 dams |
| Pong | day, 2016-05-27 | 0 | 2,965 | n/a | n/a | dry spell leads to drop in water level in 3 dams |
| Ranjit Sagar | day, 2016-05-27 | 0 | 8,888 | n/a | n/a | dry spell leads to drop in water level in 3 dams |
| Bhakra | day, 2016-07-02 | 1 | 35,627 | 61,843 | 1.74 | bhakra pong dams filling up quickly |
| Bhakra | day, 2017-03-31 | 0 | 8,800 | n/a | n/a | bhakra water level plummets |
| Bhakra | day, 2017-07-02 | 1 | 34,802 | 53,298 | 1.53 | bhakra pong dams filling up quickly |
| Bhakra | day, 2020-05-13 | 0 | 19,548 | n/a | n/a | water storage down to 10 bhakra can meet only 30 demand for irrigation |
| Pong | day, 2020-05-13 | 0 | 5,266 | n/a | n/a | water storage down to 10 bhakra can meet only 30 demand for irrigation |
| Pong | day, 2020-09-01 | 1 | 74,960 | 59,435 | 0.79 | Water level in Pong Dam rises over 5 feet above danger mark as rains l |
| Bhakra | day, 2021-05-13 | 0 | 15,661 | n/a | n/a | water storage down to 10 bhakra can meet only 30 demand for irrigation |
| Pong | day, 2021-05-13 | 0 | 3,565 | n/a | n/a | water storage down to 10 bhakra can meet only 30 demand for irrigation |
| Bhakra | day, 2021-08-19 | 1 | 90,000 | 35,959 | 0.40 | Bhakra water level flood update |
| Pong | day, 2022-08-11 | 1 | 86,897 | 76,788 | 0.88 | Himachal: भारी बारिश से पौंग बांध का जलस्तर 1351.20 फीट तक पहुंचा, पंड |
| Pong | day, 2022-08-22 | 1 | 50,592 | 89,472 | 1.77 | Water Level Rise: खतरे के निशान के नजदीक पहुंचा पौंग बांध का जलस्तर, झ |
| Ranjit Sagar | day, 2023-07-06 | 1 | 18,000 | 26,024 | 1.45 | Jalandhar News: एक दिन की बारिश से रणजीत सागर डैम में 36 सेंटीमीटर बढ़ |
| Ranjit Sagar | day, 2023-07-18 | 1 | 25,660 | 37,517 | 1.46 | rain a boon for pspcl generates 144 lakh units daily at ranjit sagar d |
| Bhakra | day, 2023-08-14 | 1 | 193,324 | 90,538 | 0.47 | BBMB via Himachal Tonite, Aug 2023 |
| Bhakra | day, 2023-08-14 | 1 | 109,834 | 90,538 | 0.82 | हिमाचल में भारी बारिश का असर: भाखड़ा बांध का जलस्तर 1675 फीट पहुंचा, ख |
| Pong | day, 2023-08-14 | 1 | 700,000 | 233,281 | 0.33 | Punjab: पौंग डैम में सात लाख क्यूसेक पानी पहुंचा, पंजाब के पांच जिलों  |
| Pong | day, 2023-08-14 | 1 | 381,330 | 233,281 | 0.61 | Kangra News: पौंग बांध का पानी खतरे के निशान से सात फीट ऊपर, निचले क्ष |
| Pong | day, 2023-08-14 | 1 | 513,000 | 233,281 | 0.45 | Pong Dam Kangra: खतरे के निशान से ऊपर पौंग बांध का जलस्तर, आज शाम 4 बज |
| Bhakra | day, 2023-08-15 | 1 | 85,899 | 89,048 | 1.04 | The Tribune, 15 Aug 2023 |
| Pong | day, 2023-08-15 | 1 | 142,000 | 374,723 | 2.64 | Several villages in Punjab's Hoshiarpur, Rupnagar inundated after wate |
| Bhakra | day, 2023-08-22 | 1 | 72,835 | 39,276 | 0.54 | The Tribune, 24 Aug 2023 (yesterday) |
| Pong | day, 2023-08-22 | 1 | 58,702 | 46,948 | 0.80 | The Tribune, 24 Aug 2023 (yesterday) |
| Bhakra | day, 2023-08-23 | 1 | 128,406 | 58,857 | 0.46 | The Tribune, 24 Aug 2023 |
| Pong | day, 2023-08-23 | 1 | 138,674 | 68,465 | 0.49 | The Tribune, 24 Aug 2023 |
| Bhakra | day, 2023-08-25 | 1 | 52,810 | 57,106 | 1.08 | Rozana Spokesman, 25 Aug 2023 |
| Bhakra | day, 2023-08-25 | 1 | 52,810 | 57,106 | 1.08 | Mounting Rainfall Elevates Flood Concerns: Bhakra Dam Water Level Reac |
| Bhakra | day, 2024-06-21 | 1 | 34,525 | 40,012 | 1.16 | Heavy rainfall in HP but water level low in Bhakra, Pong dams |
| Pong | day, 2024-06-21 | 1 | 5,389 | 44,524 | 8.26 | Heavy rainfall in HP but water level low in Bhakra, Pong dams |
| Bhakra | day, 2024-06-30 | 1 | 34,162 | 46,609 | 1.36 | ਭਾਖੜਾ ਡੈਮ 'ਚ ਪਾਣੀ ਦਾ ਪੱਧਰ 1585.83 ਫੁੱਟ 'ਤੇ ਪੁੱਜਾ |
| Bhakra | day, 2024-08-02 | 1 | 56,073 | 52,685 | 0.94 | 1610.41 ਫੁੱਟ ਤੇ ਪਹੁੰਚਿਆਂ ਭਾਖੜਾ ਡੈਮ 'ਚ ਪਾਣੀ ਦਾ ਪੱਧਰ, ਬੀਤੇ ਵਰ੍ਹੇ ਦੇ ਮੁਕਾ |
| Pong | day, 2024-08-12 | 1 | 59,830 | 100,436 | 1.68 | Kangra News: 1,346 फीट तक पहुंचा पौंग का जलस्तर, खतरे के निशान के महज  |
| Bhakra | day, 2024-11-20 | 0 | 6,000 | n/a | n/a | water level low in dams bbmb cautions member states |
| Bhakra | day, 2025-01-03 | 0 | 4,700 | n/a | n/a | water level low in dams bbmb sounds warning |
| Pong | day, 2025-01-03 | 0 | 2,600 | n/a | n/a | water level low in dams bbmb sounds warning |
| Bhakra | day, 2025-06-09 | 1 | 21,792 | 37,167 | 1.71 | Dam level up, BBMB tells Punjab, Haryana to draw more water |
| Bhakra | day, 2025-06-12 | 1 | 28,015 | 43,053 | 1.54 | Una News: भाखड़ा डैम का जलस्तर पहुंचा 1,576 फीट के पार |
| Bhakra | day, 2025-06-21 | 1 | 32,699 | 42,197 | 1.29 | Heavy rainfall in HP but water level low in Bhakra, Pong dams |
| Pong | day, 2025-06-21 | 1 | 16,602 | 51,988 | 3.13 | Heavy rainfall in HP but water level low in Bhakra, Pong dams |
| Bhakra | day, 2025-06-29 | 1 | 46,103 | 70,804 | 1.54 | Una News: बीते वर्ष के मुकाबले भाखड़ा बांध के जलस्तर में आई 16 फीट की  |
| Bhakra | day, 2025-07-05 | 1 | 44,295 | 48,735 | 1.10 | Bhakra Dam Water level increased, level reached 1584.21 feet |
| Pong | day, 2025-07-20 | 1 | 22,345 | 43,202 | 1.93 | पौंग बांध में पिछले नौ दिन में चार फीट तक बढ़ा जलस्तर |
| Bhakra | day, 2025-07-21 | 1 | 43,671 | 57,479 | 1.32 | Una News: भाखड़ा बांध का जलस्तर 1600 फीट के ऊपर पहुंचा |
| Bhakra | day, 2025-07-22 | 1 | 77,741 | 61,831 | 0.80 | Bhakra Dam Water Level: ਭਾਖੜਾ, ਪੌਂਗ ਅਤੇ ਪੰਡੋਹ ਡੈਮਾਂ ਵਿੱਚ ਪਾਣੀ ਦੀ ਆਮਦ ਘ |
| Bhakra | day, 2025-07-28 | 1 | 45,857 | 42,074 | 0.92 | Una News: भाखड़ा बांध का जलस्तर बढ़ा, खतरे के निशान के करीब |
| Bhakra | day, 2025-08-01 | 1 | 190,000 | 54,183 | 0.29 | Centre rejects Punjab's claim that lapses at Bhakra, Pong dams exacerb |
| Pong | day, 2025-08-01 | 1 | 350,000 | 99,437 | 0.28 | Centre rejects Punjab's claim that lapses at Bhakra, Pong dams exacerb |
| Pong | day, 2025-08-02 | 0 | 87,586 | n/a | n/a | The Tribune, 2 Aug 2025 |
| Pong | day, 2025-08-02 | 0 | 87,586 | n/a | n/a | Water level in Pong dam rises sharply due to heavy rainfall; BBMB warn |
| Pong | day, 2025-08-03 | 0 | 87,586 | n/a | n/a | पोंग बांध में जलस्तर खतरे के निशान के करीब, BBMB 18,995 क्यूसेक पानी छ |
| Pong | day, 2025-08-03 | 0 | 87,586 | n/a | n/a | Himachal: Water level near danger mark at Pong dam |
| Pong | day, 2025-08-03 | 0 | 87,586 | n/a | n/a | water level in pong dam nears danger mark bbmb to release 18995 cusecs |
| Pong | day, 2025-08-05 | 0 | 74,370 | n/a | n/a | Kangra News: पौंग बांध का जलस्तर खतरे के निशान से 21 फीट दूर |
| Bhakra | day, 2025-08-06 | 1 | 59,200 | 79,845 | 1.35 | Babushahi, 6 Aug 2025 |
| Bhakra | day, 2025-08-06 | 1 | 59,200 | 79,845 | 1.35 | Water levels surge at Bhakra, Pong, and Ranjit Sagar dams after heavy  |
| Pong | day, 2025-08-06 | 0 | 93,650 | n/a | n/a | Babushahi, 6 Aug 2025 |
| Pong | day, 2025-08-06 | 0 | 93,650 | n/a | n/a | Water levels surge at Bhakra, Pong, and Ranjit Sagar dams after heavy  |
| Ranjit Sagar | day, 2025-08-06 | 0 | 24,000 | n/a | n/a | Water levels surge at Bhakra, Pong, and Ranjit Sagar dams after heavy  |
| Bhakra | day, 2025-08-07 | 1 | 70,352 | 68,774 | 0.98 | Una News: भाखड़ा बांध का जलस्तर पहुंचा 1638 फीट के पार |
| Pong | day, 2025-08-07 | 1 | 190,000 | 121,176 | 0.64 | Punjab: 23,000 cusecs of water released from Pong dam |
| Pong | day, 2025-08-09 | 1 | 52,518 | 61,410 | 1.17 | पंजाब में आज भारी बारिश का अलर्ट: पौंग बांध से फिर छोड़ा जाएगा पानी, ज |
| Bhakra | day, 2025-08-16 | 1 | 89,361 | 65,342 | 0.73 | Una News: भाखड़ा बांध का जलस्तर पहुंचा 1658 फीट के पार |
| Pong | day, 2025-08-17 | 1 | 109,789 | 116,417 | 1.06 | The Tribune, 17 Aug 2025 |
| Pong | day, 2025-08-17 | 1 | 109,789 | 116,417 | 1.06 | Water level in Pong Dam touches 1,379.98 feet, BBMB orders release of  |
| Bhakra | day, 2025-08-19 | 1 | 65,617 | 50,105 | 0.76 | Babushahi, 19 Aug 2025 |
| Bhakra | day, 2025-08-19 | 1 | 65,617 | 50,105 | 0.76 | Breaking: All four floodgates of Bhakra dam opened |
| Bhakra | day, 2025-08-19 | 1 | 70,500 | 50,105 | 0.71 | BBMB Releases Water From Pong & Bhakra Dams, Flood Alert Issued in Sev |
| Pong | day, 2025-08-19 | 1 | 84,000 | 101,775 | 1.21 | BBMB Releases Water From Pong & Bhakra Dams, Flood Alert Issued in Sev |
| Bhakra | day, 2025-08-25 | 1 | 48,000 | 62,116 | 1.29 | Amid heavy rainfall in Himachal: BBMB keeps close watch, says Bhakra w |
| Pong | day, 2025-08-25 | 1 | 146,174 | 104,157 | 0.71 | Diary Times, 25 Aug 2025 |
| Pong | day, 2025-08-25 | 1 | 151,000 | 104,157 | 0.69 | Kangra News: पौंग बांध का जलस्तर बढ़ा, घराट जलमग्न |
| Pong | day, 2025-08-26 | 1 | 233,000 | 175,210 | 0.75 | Water level in Pong dam reaches 1,390 feet |
| Bhakra | day, 2025-08-27 | 1 | 58,997 | 60,633 | 1.03 | The Tribune, 28 Aug 2026 (same date last year) |
| Bhakra | day, 2025-08-27 | 1 | 58,997 | 60,633 | 1.03 | Bilaspur News: भाखड़ा बांध में पिछले साल से 37 फीट कम पानी |
| Bhakra | day, 2025-08-27 | 1 | 59,364 | 60,633 | 1.02 | Punjab's power demand stays above 16,000 MW, but why is Bhakra inflow  |
| Pong | day, 2025-08-27 | 1 | 228,091 | 203,537 | 0.89 | The Tribune, 28 Aug 2026 (same date last year) |
| Ranjit Sagar | day, 2025-08-27 | 1 | 163,037 | 109,546 | 0.67 | The Tribune, 28 Aug 2026 (same date last year) |
| Ranjit Sagar | day, 2025-08-27 | 1 | 7,073 | 109,546 | 15.49 | Punjab faces 34% monsoon deficit as key reservoirs record sharp drop i |
| Bhakra | day, 2025-08-28 | 1 | 53,856 | 55,806 | 1.04 | Water level drops in Punjab's Ranjit Sagar Dam |
| Bhakra | day, 2025-08-28 | 1 | 54,213 | 55,806 | 1.03 | water levels recede in punjab dams bringing relief to flood affected a |
| Pong | day, 2025-08-28 | 1 | 110,000 | 126,933 | 1.15 | Water level drops in Punjab's Ranjit Sagar Dam |
| Pong | day, 2025-08-28 | 1 | 79,780 | 126,933 | 1.59 | pong dam water level remains above danger mark high discharge continue |
| Pong | day, 2025-08-28 | 1 | 144,741 | 126,933 | 0.88 | water levels recede in punjab dams bringing relief to flood affected a |
| Bhakra | day, 2025-08-29 | 1 | 49,137 | 70,410 | 1.43 | Punjab Dams' Water Level Recede, Bring Relief To Flood-Hit Areas |
| Bhakra | day, 2025-08-29 | 1 | 49,137 | 70,410 | 1.43 | water levels recede in punjab dams bringing relief to flood affected a |
| Pong | day, 2025-08-29 | 1 | 61,371 | 116,119 | 1.89 | Punjab Dams' Water Level Recede, Bring Relief To Flood-Hit Areas |
| Pong | day, 2025-08-29 | 1 | 61,371 | 116,119 | 1.89 | water levels recede in punjab dams bringing relief to flood affected a |
| Ranjit Sagar | day, 2025-08-29 | 1 | 54,623 | 52,900 | 0.97 | Punjab Dams' Water Level Recede, Bring Relief To Flood-Hit Areas |
| Pong | day, 2025-08-31 | 1 | 160,276 | 121,294 | 0.76 | The Tribune, 31 Aug 2025 |
| Pong | day, 2025-08-31 | 1 | 160,276 | 121,294 | 0.76 | pong dam level remains above danger mark 84952 cusecs water discharged |
| Bhakra | day, 2025-09-01 | 1 | 107,565 | 102,896 | 0.96 | Una News: खतरे के निशान से मात्र तीन फीट की दूरी पर भाखड़ा डैम का जलस् |
| Bhakra | day, 2025-09-01 | 1 | 107,000 | 102,896 | 0.96 | Amid Heavy Rain, Bhakra Dam Level Rises 3 ft In 24 Hours, Authorities  |
| Bhakra | day, 2025-09-02 | 1 | 107,000 | 110,069 | 1.03 | Bhakra Dam level rises 3 ft in 24 hours, triggers flood alarm downstre |
| Pong | day, 2025-09-02 | 1 | 96,777 | 134,700 | 1.39 | Bhakra Dam level rises 3 ft in 24 hours, triggers flood alarm downstre |
| Pong | day, 2025-09-02 | 1 | 96,777 | 134,700 | 1.39 | Amid Heavy Rain, Bhakra Dam Level Rises 3 ft In 24 Hours, Authorities  |
| Bhakra | day, 2025-09-03 | 1 | 110,000 | 101,982 | 0.93 | Una News: भाखड़ा बांध का जलस्तर 1678 फीट पार, दो फीट रह गया खतरे का नि |
| Bhakra | day, 2025-09-03 | 1 | 86,822 | 101,982 | 1.17 | record rain red alert in punjab himachal j&k chandigarh's sukhna gates |
| Pong | day, 2025-09-03 | 1 | 155,261 | 151,829 | 0.98 | heavy rainfall swells pong dam water level above danger mark for 4th d |
| Bhakra | day, 2025-09-04 | 1 | 95,435 | 93,866 | 0.98 | BBMB Reservoir Data (data-reservoir.htm archived capture) |
| Bhakra | day, 2025-09-04 | 1 | 95,435 | 93,866 | 0.98 | bhakra to release more water into punjab as pong dam hits full capacit |
| Pong | day, 2025-09-04 | 1 | 107,301 | 147,004 | 1.37 | The Tribune, 4 Sep 2025 (actual inflow) |
| Pong | day, 2025-09-04 | 1 | 132,595 | 147,004 | 1.11 | BBMB Reservoir Data (data-reservoir.htm archived capture) |
| Pong | day, 2025-09-04 | 1 | 132,595 | 147,004 | 1.11 | bhakra to release more water into punjab as pong dam hits full capacit |
| Bhakra | day, 2025-09-05 | 1 | 76,318 | 66,699 | 0.87 | SDO Nangal via Babushahi, 5 Sep 2025 |
| Bhakra | day, 2025-09-05 | 1 | 76,318 | 66,699 | 0.87 | Bhakra reservoir water level data (SDO Nangal Dam office) |
| Pong | day, 2025-09-05 | 1 | 105,950 | 113,008 | 1.07 | The Tribune, 6 Sep 2025 (yesterday) |
| Pong | day, 2025-09-05 | 1 | 99,673 | 113,008 | 1.13 | Kangra News: पौंग बांध का जलस्तर 1394.80 फीट पर स्थिर, खतरे से 4.80 फी |
| Pong | day, 2025-09-05 | 1 | 105,950 | 113,008 | 1.07 | Punjab floods: Bhakra water level drops; Pong dam continues high outfl |
| Bhakra | day, 2025-09-06 | 1 | 62,481 | 55,270 | 0.88 | The Tribune, 6 Sep 2025 |
| Bhakra | day, 2025-09-06 | 1 | 51,332 | 55,270 | 1.08 | Punjab: Pong releases 99,889 cusecs as water level exceeds limit |
| Bhakra | day, 2025-09-06 | 1 | 62,481 | 55,270 | 0.88 | Water level in Bhakra, Pong & Ranjit Sagar dams recedes |
| Bhakra | day, 2025-09-06 | 1 | 62,481 | 55,270 | 0.88 | Punjab floods: Bhakra water level drops; Pong dam continues high outfl |
| Pong | day, 2025-09-06 | 1 | 98,418 | 75,537 | 0.77 | The Tribune, 6 Sep 2025 |
| Pong | day, 2025-09-06 | 1 | 47,162 | 75,537 | 1.60 | Punjab: Pong releases 99,889 cusecs as water level exceeds limit |
| Pong | day, 2025-09-06 | 1 | 47,162 | 75,537 | 1.60 | Punjab: Water level in Pong dam dips by 2 feet but outflow still high |
| Pong | day, 2025-09-06 | 1 | 98,418 | 75,537 | 0.77 | Punjab floods: Bhakra water level drops; Pong dam continues high outfl |
| Ranjit Sagar | day, 2025-09-06 | 1 | 24,947 | 22,582 | 0.91 | Punjab: Pong releases 99,889 cusecs as water level exceeds limit |
| Bhakra | day, 2025-09-07 | 1 | 66,900 | 46,889 | 0.70 | Punjab: Water level in Pong dam dips by 2 feet but outflow still high |
| Pong | day, 2025-09-07 | 1 | 36,968 | 58,398 | 1.58 | Punjab: Water level in Pong dam dips by 2 feet but outflow still high |
| Bhakra | day, 2025-09-08 | 1 | 55,338 | 43,358 | 0.78 | Water level in Bhakra, Pong & Ranjit Sagar dams recedes |
| Pong | day, 2025-09-08 | 1 | 46,500 | 54,954 | 1.18 | Punjab: Water level in Pong dam dips by 2 feet but outflow still high |
| Pong | day, 2025-09-08 | 1 | 35,439 | 54,954 | 1.55 | Water level in Bhakra, Pong & Ranjit Sagar dams recedes |
| Ranjit Sagar | day, 2025-09-08 | 1 | 30,500 | 19,141 | 0.63 | Punjab: Water level in Pong dam dips by 2 feet but outflow still high |
| Ranjit Sagar | day, 2025-09-08 | 1 | 19,782 | 19,141 | 0.97 | Water level in Bhakra, Pong & Ranjit Sagar dams recedes |
| Bhakra | day, 2025-09-14 | 1 | 46,708 | 46,070 | 0.99 | पंजाब में बढ़ी बिजली की मांग: 2173 मेगावाट उत्पादन ठप, मानसून की बेरुख |
| Pong | day, 2025-09-14 | 1 | 34,737 | 70,784 | 2.04 | पंजाब में बढ़ी बिजली की मांग: 2173 मेगावाट उत्पादन ठप, मानसून की बेरुख |
| Bhakra | day, 2025-09-15 | 1 | 54,667 | 44,977 | 0.82 | BBMB Reservoir Data res_data.pdf (archived capture) |
| Bhakra | day, 2025-09-15 | 1 | 40,999 | 44,977 | 1.10 | water level at pong dam rises amid surplus rain in parts of himachal p |
| Pong | day, 2025-09-15 | 1 | 76,498 | 83,124 | 1.09 | BBMB Reservoir Data res_data.pdf (archived capture) |
| Pong | day, 2025-09-15 | 1 | 80,000 | 83,124 | 1.04 | पौंग डैम का जलस्तर घटा, निचले इलाकों के लिए राहत, जल्द पटरी पर लौटेगी  |
| Pong | day, 2025-09-15 | 1 | 64,964 | 83,124 | 1.28 | water level at pong dam rises amid surplus rain in parts of himachal p |
| Pong | day, 2025-09-16 | 1 | 160,369 | 74,345 | 0.46 | Kangra News: पौंग बांध का जलस्तर खतरे के निशान से पांच फीट ऊपर |
| Pong | day, 2025-09-20 | 1 | 38,773 | 49,898 | 1.29 | Pong Dam water level sees decline |
| Pong | day, 2025-09-21 | 1 | 31,540 | 45,578 | 1.45 | Pong Dam water level sees decline |
| Bhakra | day, 2025-09-24 | 1 | 35,666 | 34,673 | 0.97 | BBMB Reservoir Data res_data.pdf (archived capture) |
| Pong | day, 2025-09-24 | 1 | 17,291 | 40,090 | 2.32 | BBMB Reservoir Data res_data.pdf (archived capture) |
| Pong | day, 2025-10-05 | 0 | 10,084 | n/a | n/a | 50000 cusecs of water released from pong dam |
| Bhakra | day, 2025-11-20 | 0 | 7,811 | n/a | n/a | Himachal: पंजाब में नहरों की मरम्मत से और बढ़ेगा भाखड़ा डैम में पानी |
| Bhakra | day, 2026-05-14 | 0 | 13,102 | n/a | n/a | BBMB Reservoir Data rdata.html (archived capture) |
| Pong | day, 2026-05-14 | 0 | 2,705 | n/a | n/a | BBMB Reservoir Data rdata.html (archived capture) |
| Bhakra | day, 2026-06-04 | 0 | 10,641 | n/a | n/a | BBMB Reservoir Data rdata.html (archived capture) |
| Pong | day, 2026-06-04 | 0 | 2,088 | n/a | n/a | BBMB Reservoir Data rdata.html (archived capture) |
| Bhakra | day, 2026-06-09 | 0 | 13,748 | n/a | n/a | Dam level up, BBMB tells Punjab, Haryana to draw more water |
| Bhakra | day, 2026-06-10 | 0 | 13,748 | n/a | n/a | Draw more water from dams, BBMB tells partner states ahead of monsoon |
| Pong | day, 2026-06-10 | 0 | 1,986 | n/a | n/a | Draw more water from dams, BBMB tells partner states ahead of monsoon |
| Bhakra | day, 2026-06-11 | 0 | 16,527 | n/a | n/a | Una News: भाखड़ा डैम का जलस्तर पहुंचा 1,576 फीट के पार |
| Bhakra | day, 2026-06-11 | 0 | 16,527 | n/a | n/a | Bhakra inflows down 50% as low snowfall, delayed snowmelt hit Sutlej c |
| Pong | day, 2026-06-11 | 0 | 2,129 | n/a | n/a | Bhakra inflows down 50% as low snowfall, delayed snowmelt hit Sutlej c |
| Ranjit Sagar | day, 2026-06-11 | 0 | 4,854 | n/a | n/a | Bhakra inflows down 50% as low snowfall, delayed snowmelt hit Sutlej c |
| Bhakra | day, 2026-06-13 | 0 | 19,074 | n/a | n/a | Bhakra Dam Water Level: ਭਾਖੜਾ ਡੈਮ ਵਿੱਚ ਪਾਣੀ ਦਾ ਪੱਧਰ 1576.22 ਫੁੱਟ ਤੱਕ ਪ |
| Bhakra | day, 2026-06-14 | 0 | 22,581 | n/a | n/a | ਭਾਖੜਾ ਡੈਮ ਅਪਡੇਟ: ਮੰਗ ਵਧਣ ਕਾਰਨ 3 ਦਿਨਾਂ 'ਚ 0.81 ਫੁੱਟ ਘਟਿਆ ਪਾਣੀ ਦਾ ਪੱਧਰ |
| Bhakra | day, 2026-06-24 | 0 | 18,715 | n/a | n/a | BBMB Reservoir Data res_data.pdf (archived capture) |
| Pong | day, 2026-06-24 | 0 | 3,527 | n/a | n/a | BBMB Reservoir Data res_data.pdf (archived capture) |
| Bhakra | day, 2026-06-28 | 1 | 22,137 | 37,344 | 1.69 | Below-normal monsoon may impact water-levels at Bhakra, Ranjit Sagar r |
| Pong | day, 2026-06-28 | 1 | 5,723 | 42,118 | 7.36 | Below-normal monsoon may impact water-levels at Bhakra, Ranjit Sagar r |
| Ranjit Sagar | day, 2026-06-28 | 0 | 2,006 | n/a | n/a | Below-normal monsoon may impact water-levels at Bhakra, Ranjit Sagar r |
| Bhakra | day, 2026-06-29 | 1 | 22,734 | 42,518 | 1.87 | Una News: बीते वर्ष के मुकाबले भाखड़ा बांध के जलस्तर में आई 16 फीट की  |
| Bhakra | day, 2026-07-15 | 1 | 40,426 | 39,763 | 0.98 | 22 फीट बढ़ा भाखड़ा का जलस्तर: पिछले साल से फिर भी नीचे... |
| Ranjit Sagar | day, 2026-07-21 | 0 | 43,898 | n/a | n/a | Water levels at Bhakra, Pong and Pandoh dams substantially lower due t |
| Bhakra | day, 2026-07-22 | 0 | 36,866 | n/a | n/a | Water levels at Bhakra, Pong and Pandoh dams substantially lower due t |
| Bhakra | day, 2026-07-22 | 0 | 36,866 | n/a | n/a | Bhakra Dam Water Level: ਭਾਖੜਾ, ਪੌਂਗ ਅਤੇ ਪੰਡੋਹ ਡੈਮਾਂ ਵਿੱਚ ਪਾਣੀ ਦੀ ਆਮਦ ਘ |
| Pong | day, 2026-07-22 | 0 | 22,546 | n/a | n/a | Water levels at Bhakra, Pong and Pandoh dams substantially lower due t |
| Ranjit Sagar | day, 2026-07-24 | 0 | 96,674 | n/a | n/a | ਰਣਜੀਤ ਸਾਗਰ ਡੈਮ 'ਚ ਵਧਿਆ ਪਾਣੀ ਦਾ ਪੱਧਰ, ਡੈਮ ਪ੍ਰਬੰਧਕਾਂ ਨੇ ਭੇਜਿਆ ਚੇਤਾਵਨੀ ਸੰ |
| Bhakra | day, 2026-07-26 | 0 | 40,363 | n/a | n/a | BBMB Reservoir Data res_data.pdf (archived capture) |
| Pong | day, 2026-07-26 | 0 | 37,172 | n/a | n/a | BBMB Reservoir Data res_data.pdf (archived capture) |
| Pong | day, 2026-07-29 | 1 | 61,210 | 107,558 | 1.76 | Kangra News: पौंग बांध का जलस्तर 11 दिन में 12 फीट बढ़ा |
| Bhakra | day, 2026-08-08 | 1 | 41,501 | 57,592 | 1.39 | BBMB Reservoir Data res_data.pdf (archived capture) |
| Pong | day, 2026-08-08 | 1 | 48,054 | 94,699 | 1.97 | BBMB Reservoir Data res_data.pdf (archived capture) |
| Bhakra | day, 2026-08-09 | 1 | 40,137 | 52,848 | 1.32 | BBMB Reservoir Data res_data.pdf (archived capture) |
| Pong | day, 2026-08-09 | 1 | 34,263 | 70,121 | 2.05 | BBMB Reservoir Data res_data.pdf (archived capture) |
| Bhakra | day, 2026-08-10 | 1 | 41,000 | 55,778 | 1.36 | Himachal rain takes Bhakra Dam level to 1,612 feet, still far from 1,6 |
| Pong | day, 2026-08-10 | 1 | 48,000 | 61,781 | 1.29 | Himachal rain takes Bhakra Dam level to 1,612 feet, still far from 1,6 |
| Ranjit Sagar | day, 2026-08-12 | 0 | 11,645 | n/a | n/a | Jalandhar News: रंजीत सागर बांध का जलस्तर 513.01 मीटर पहुंचा |
| Bhakra | day, 2026-08-21 | 1 | 48,309 | 44,884 | 0.93 | Punjab, Haryana brace for rain on August 22; dam levels below normal a |
| Pong | day, 2026-08-21 | 1 | 39,639 | 62,136 | 1.57 | Punjab, Haryana brace for rain on August 22; dam levels below normal a |
| Bhakra | day, 2026-08-26 | 1 | 42,000 | 40,840 | 0.97 | Punjab: Tighten taps, BBMB cautions partner states as weak monsoon str |
| Bhakra | day, 2026-08-27 | 1 | 30,452 | 39,686 | 1.30 | Bilaspur News: भाखड़ा बांध में पिछले साल से 37 फीट कम पानी |
| Bhakra | day, 2026-08-27 | 1 | 30,452 | 39,686 | 1.30 | Punjab faces 34% monsoon deficit as key reservoirs record sharp drop i |
| Bhakra | day, 2026-08-27 | 1 | 30,452 | 39,686 | 1.30 | Bhakra, Pong, Ranjit Sagar Dams see lower water levels this monsoon |
| Bhakra | day, 2026-08-27 | 1 | 6,163 | 39,686 | 6.44 | Punjab's power demand stays above 16,000 MW, but why is Bhakra inflow  |
| Pong | day, 2026-08-27 | 1 | 22,202 | 51,504 | 2.32 | Punjab faces 34% monsoon deficit as key reservoirs record sharp drop i |
| Pong | day, 2026-08-27 | 1 | 22,202 | 51,504 | 2.32 | Bhakra, Pong, Ranjit Sagar Dams see lower water levels this monsoon |
| Ranjit Sagar | day, 2026-08-27 | 0 | 7,073 | n/a | n/a | Bhakra, Pong, Ranjit Sagar Dams see lower water levels this monsoon |
| Bhakra | day, 2026-09-04 | 1 | 42,701 | 49,079 | 1.15 | BBMB Reservoir Data res_data.pdf (direct capture) |
| Pong | day, 2026-09-04 | 1 | 20,102 | 64,224 | 3.19 | BBMB Reservoir Data res_data.pdf (direct capture) |
| Bhakra | day, 2026-09-05 | 1 | 41,628 | 54,222 | 1.30 | BBMB Reservoir Data res_data.pdf (direct capture) |
| Pong | day, 2026-09-05 | 1 | 22,870 | 61,254 | 2.68 | BBMB Reservoir Data res_data.pdf (direct capture) |
| Bhakra | day, 2026-09-14 | 0 | 30,199 | n/a | n/a | पंजाब में बढ़ी बिजली की मांग: 2173 मेगावाट उत्पादन ठप, मानसून की बेरुख |
| Pong | day, 2026-09-14 | 0 | 10,751 | n/a | n/a | पंजाब में बढ़ी बिजली की मांग: 2173 मेगावाट उत्पादन ठप, मानसून की बेरुख |
| Bhakra | day, 2026-09-17 | 0 | 28,368 | n/a | n/a | BBMB Reservoir Data res_data.pdf (direct capture) |
| Pong | day, 2026-09-17 | 0 | 11,509 | n/a | n/a | BBMB Reservoir Data res_data.pdf (direct capture) |
| Bhakra | day, 2025-09-15 | 1 | 54,667 | 44,977 | 0.82 | BBMB daily sheet, Internet Archive |
| Bhakra | day, 2025-09-24 | 1 | 35,666 | 34,673 | 0.97 | BBMB daily sheet, Internet Archive |
| Pong | day, 2025-09-15 | 1 | 76,498 | 83,124 | 1.09 | BBMB daily sheet, Internet Archive |
| Pong | day, 2025-09-24 | 1 | 17,291 | 40,090 | 2.32 | BBMB daily sheet, Internet Archive |
| Pong | record day, 2023-08-14 | 1 | 734,000 | 233,281 | 0.32 | BBMB Pong EAP, largest inflow recorded |
| Pong | largest day of 2025 | 112 | 349,522 | 203,537 | 0.58 | Rajya Sabha reply via PTI, 2 Dec 2025 |
| Bhakra | largest day of 2025 | 121 | 190,603 | 110,069 | 0.58 | Rajya Sabha reply via PTI, 2 Dec 2025 |

Dated figures by year (readings at a time of day against the model's daily volume; 2016: 1 dated figures, the model at 1.74 of the reading, median 1.74; 2017: 1 dated figures, the model at 1.53 of the reading, median 1.53; 2020: 1 dated figures, the model at 0.79 of the reading, median 0.79; 2021: 1 dated figures, the model at 0.40 of the reading, median 0.40; 2022: 2 dated figures, the model at 0.88 to 1.77 of the reading, median 1.33; 2023: 16 dated figures, the model at 0.32 to 2.64 of the reading, median 0.71; 2024: 5 dated figures, the model at 0.94 to 8.26 of the reading, median 1.36; 2025: 96 dated figures, the model at 0.28 to 15.49 of the reading, median 1.03; 2026: 24 dated figures, the model at 0.93 to 7.36 of the reading, median 1.48).

The spread of the model's log ratio to the 6 period means (sample standard deviation) is 0.14, with a mean log ratio of -0.01; the dated readings (147) spread 0.56, wider because they are moments, not daily means. The product samples the period-mean spread as a multiplicative volume error on every inflow path for its third spill probability (an outer estimate), and does not apply the bias.

Where the run covers at least 10 of a period's days, the model's mean is 0.78 to 1.13 of the reported mean; its largest day of the season is 0.58 of the stated peak. The flood's volume is close to right and its peak day is not: the model spreads the volume over more days than the river does, which is consistent with lag weights fitted on ordinary days.

### Response variants, tested out of sample

Each variant is fitted on the same storage record beside the response in use and scored leave-one-season-out (each season by a fit on the others). Rain above the heavy-day threshold in a catchment day gets its own coefficient and lag weights (the threshold-excess variant). The soil-moisture variants change the carrier of catchment wetness: `api+sm` keeps the five-day rain index and adds the ERA5-Land 0-7 cm soil-moisture anomaly through gamma; `sm` drops the rain index and keeps the anomaly alone (each fold's climatology leaves the held-out season out). The press inflow fit is the same response fitted on every dated press reading of inflow the sweeps found (moment readings, all seasons before the current one), expressed in the storage-change convention and scored on the storage record, where every season is out of sample for it (`seasons` counts them). The rule before any variant can replace the response the product uses: the held-out error may not rise at any dam, the season-peak ratios of the flood-scale table must rise, and the period means may not move further from the reported means than the baseline's worst one does. Heavy-day bias is observed minus predicted storage change, positive when heavy days are under-predicted.

| dam | variant | seasons | days | held-out RMSE (BCM/day) | heavy days | heavy-day RMSE (BCM/day) | heavy-day bias (BCM/day) | c | c_wet | w | c_excess | w_excess | wetness | gamma | c_melt |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Bhakra | baseline | 11 | 1009 | 0.0439 | 2 | 0.1013 | -0.0908 | 0.170 | 0.250 | 0.54 0.27 0.10 0.09 | 0.000 | none | api | 0.00 | 0.000 |
| Bhakra | excess above 30 mm | 11 | 1009 | 0.0668 | 2 | 0.0923 | -0.0773 | 0.194 | 0.207 | 0.55 0.21 0.12 0.12 | 0.303 | 0.00 1.00 0.00 0.00 | api | 0.00 | 0.000 |
| Bhakra | api+sm | 11 | 1009 | 0.0440 | 2 | 0.0961 | -0.0866 | 0.170 | 0.250 | 0.54 0.27 0.10 0.09 | 0.000 | none | api+sm | -0.14 | 0.000 |
| Bhakra | sm | 11 | 1009 | 0.0436 | 2 | 0.0691 | -0.0530 | 0.278 | 0.000 | 0.27 0.36 0.18 0.19 | 0.000 | none | sm | 0.15 | 0.000 |
| Bhakra | snowmelt | 11 | 1009 | 0.0438 | 2 | 0.0948 | -0.0846 | 0.145 | 0.282 | 0.54 0.28 0.08 0.09 | 0.000 | none | api | 0.00 | 0.067 |
| Pong | baseline | 8 | 733 | 0.0302 | 28 | 0.0782 | -0.0158 | 0.203 | 0.328 | 0.35 0.48 0.09 0.08 | 0.000 | none | api | 0.00 | 0.000 |
| Pong | excess above 30 mm | 8 | 733 | 0.0304 | 28 | 0.0773 | -0.0129 | 0.200 | 0.332 | 0.40 0.39 0.11 0.10 | 0.523 | 0.20 0.65 0.09 0.06 | api | 0.00 | 0.000 |
| Pong | api+sm | 8 | 733 | 0.0300 | 28 | 0.0772 | -0.0059 | 0.203 | 0.328 | 0.35 0.48 0.09 0.08 | 0.000 | none | api+sm | -0.36 | 0.000 |
| Pong | sm | 8 | 733 | 0.0334 | 28 | 0.0860 | +0.0101 | 0.509 | 0.000 | 0.21 0.52 0.15 0.13 | 0.000 | none | sm | -0.25 | 0.000 |
| Ranjit Sagar | baseline | 11 | 1184 | 0.0229 | 29 | 0.0442 | -0.0113 | 0.131 | 0.263 | 0.62 0.24 0.08 0.05 | 0.000 | none | api | 0.00 | 0.000 |
| Ranjit Sagar | excess above 30 mm | 11 | 1184 | 0.0229 | 29 | 0.0469 | -0.0074 | 0.156 | 0.166 | 0.47 0.27 0.15 0.11 | 0.469 | 0.46 0.48 0.00 0.07 | api | 0.00 | 0.000 |
| Ranjit Sagar | api+sm | 11 | 1184 | 0.0230 | 29 | 0.0384 | -0.0168 | 0.131 | 0.263 | 0.62 0.24 0.08 0.05 | 0.000 | none | api+sm | 0.26 | 0.000 |
| Ranjit Sagar | sm | 11 | 1184 | 0.0230 | 29 | 0.0471 | -0.0101 | 0.341 | 0.000 | 0.34 0.45 0.11 0.10 | 0.000 | none | sm | 1.30 | 0.000 |
| Bhakra | press inflow fit | 11 | 1009 | 0.0460 | 2 | 0.1520 | -0.1497 | 0.433 | 0.000 | 0.47 0.21 0.11 0.21 | 0.000 | none | api | 0.00 | 0.000 |
| Pong | press inflow fit | 8 | 733 | 0.0714 | 28 | 0.1157 | -0.0589 | 0.710 | 0.278 | 0.35 0.15 0.22 0.28 | 0.000 | none | api | 0.00 | 0.000 |

| variant | period means covered | worst deviation of a period mean from 1 | season-peak ratio, smallest | season-peak ratio, largest |
|---|---|---|---|---|
| baseline | 6 | 0.22 | 0.57 | 0.58 |
| excess above 30 mm | 6 | 0.26 | 0.55 | 0.58 |
| api+sm | 6 | 0.22 | 0.54 | 0.57 |
| sm | 6 | 0.26 | 0.46 | 0.50 |
| press inflow fit | 4 | 0.22 | 0.58 | 0.62 |

Verdict on 'excess above 30 mm', not adopted. Conditions: the held-out error does not rise at any dam (fails); the season peaks rise (fails); the period means hold (fails).

Verdict on 'api+sm', not adopted. Conditions: the held-out error does not rise at any dam (fails); the season peaks rise (fails); the period means hold (passes).

Verdict on 'sm', not adopted. Conditions: the held-out error does not rise at any dam (fails); the season peaks rise (fails); the period means hold (fails).

Verdict on 'press inflow fit', not adopted. Conditions: the held-out error does not rise at any dam (fails); the season peaks rise (passes); the period means hold (passes).

### The snowmelt term at Bhakra

Bhakra's base flow is snowmelt from the half of the catchment outside the IMD grid, which the response carries as a constant intercept. The variant runs a temperature-index snowpack at every archive point of the catchment (ERA5 snowfall stacked into a pack, released at 4 mm per degree-day above 0 C, the factor fixed, not fitted) and adds the area-weighted melt, as a volume over the whole catchment, as a lagged term with its own non-negative coefficient and lag weights in the same fit; the intercept stays free, so the term wins only what a season-varying melt explains beyond a constant base. It touches Bhakra alone, so the rule is read at Bhakra alone: the held-out error there may not rise, Bhakra's season-peak ratio must rise, and Bhakra's period means may not move further from the reported means than the baseline's worst one does. The rule was written before the fit.

| dam | c | c_wet | c_melt | w_melt | intercept (BCM/day) | in-sample RMSE (BCM/day) | R2 |
|---|---|---|---|---|---|---|---|
| Bhakra | 0.145 | 0.282 | 0.067 | 0.00 0.15 0.00 0.85 | -0.0014 | 0.0431 | 0.221 |

| run | period means covered | worst deviation of a period mean from 1 | season-peak ratio, smallest | season-peak ratio, largest |
|---|---|---|---|---|
| baseline, Bhakra | 2 | 0.11 | 0.57 | 0.57 |
| snowmelt, Bhakra | 2 | 0.10 | 0.58 | 0.58 |

Verdict on 'snowmelt', adopted. Conditions: the held-out error does not rise at Bhakra (passes); Bhakra's season peak rises (passes); Bhakra's period means hold (passes). The held-out row is in the variants table above.

Over the 2025 monsoon (122 issue days) the melt response over five days came to 0.025 BCM on average, 0.069 BCM at most; the rain response 0.180 BCM and 0.749 BCM (each response alone, no base flow, the archive's melt over the horizon).

The parameters in use carry the term at: Bhakra.

## As-issued hindcast: what the product would have said, each dam, 2024 to 2026

For each issue date the recorded or model-carried storage and the rain forecast actually issued that day (archived lead 1 to 5 QPF, deterministic) go through the same water balance as the live product. A flagged day is an issue date whose forecast forces the spillway within five days. BBMB's gate log is not public, so the model's own run under observed rain (perfect prognosis) is the reference: a flag is a hit when that run also forces the spillway within five days of the same issue date, a false flag otherwise, and a perfect-prognosis flag without an as-issued flag is a miss. The first hit is the warning; the lead is counted from it to the model's first spill under observed rain and to the dated Dhilwan peak. The window is 1 August to 15 September.

| year | dam | model | issue days | flagged (hits, false) | missed | first flag of any kind | first hit (issue date, spill on day) | earliest possible flag (observed rain) | first spill under observed rain | lead (days) | observed Dhilwan peak (Pong only) | lead (days) | largest forecast peak release (cusecs) | perfect-prognosis peak release (cusecs) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2024 | Pong | ecmwf_aifs025_single | 0 | 0 (0 hits, 0 false) | 0 | none | none | none | none | n/a | 2024-08-12 | n/a | nan | 0 |
| 2024 | Pong | ecmwf_ifs025 | 46 | 0 (0 hits, 0 false) | 0 | none | none | none | none | n/a | 2024-08-12 | n/a | 0 | 0 |
| 2024 | Pong | gfs_seamless | 46 | 0 (0 hits, 0 false) | 0 | none | none | none | none | n/a | 2024-08-12 | n/a | 0 | 0 |
| 2025 | Pong | ecmwf_aifs025_single | 41 | 23 (23 hits, 0 false) | 6 | 2025-08-17 | 2025-08-17, day 3 | 2025-08-14 | 2025-08-27 | +10 | 2025-08-31 | +14 | 142,449 | 157,937 |
| 2025 | Pong | ecmwf_ifs025 | 41 | 25 (25 hits, 0 false) | 4 | 2025-08-15 | 2025-08-15, day 5 | 2025-08-14 | 2025-08-27 | +12 | 2025-08-31 | +16 | 173,377 | 157,937 |
| 2025 | Pong | gfs_seamless | 41 | 23 (23 hits, 0 false) | 6 | 2025-08-17 | 2025-08-17, day 4 | 2025-08-14 | 2025-08-27 | +10 | 2025-08-31 | +14 | 139,491 | 157,937 |
| 2026 | Pong | ecmwf_aifs025_single | 42 | 0 (0 hits, 0 false) | 0 | none | none | none | none | n/a | none | n/a | 0 | 0 |
| 2026 | Pong | ecmwf_ifs025 | 42 | 0 (0 hits, 0 false) | 0 | none | none | none | none | n/a | none | n/a | 0 | 0 |
| 2026 | Pong | gfs_seamless | 42 | 0 (0 hits, 0 false) | 0 | none | none | none | none | n/a | none | n/a | 0 | 0 |
| 2024 | Pong | ecmwf_aifs025_single | 0 | 0 (0 hits, 0 false) | 0 | none | none | none | none | n/a | none | n/a | nan | 0 |
| 2024 | Bhakra | ecmwf_ifs025 | 46 | 0 (0 hits, 0 false) | 0 | none | none | none | none | n/a | none | n/a | 0 | 0 |
| 2024 | Bhakra | gfs_seamless | 46 | 0 (0 hits, 0 false) | 0 | none | none | none | none | n/a | none | n/a | 0 | 0 |
| 2025 | Bhakra | ecmwf_aifs025_single | 46 | 3 (3 hits, 0 false) | 0 | 2025-08-30 | 2025-08-30, day 4 | 2025-08-30 | none | n/a | none | n/a | 68,679 | 0 |
| 2025 | Bhakra | ecmwf_ifs025 | 46 | 3 (3 hits, 0 false) | 0 | 2025-08-30 | 2025-08-30, day 4 | 2025-08-30 | none | n/a | none | n/a | 34,661 | 0 |
| 2025 | Bhakra | gfs_seamless | 46 | 1 (1 hits, 0 false) | 2 | 2025-09-01 | 2025-09-01, day 3 | 2025-08-30 | none | n/a | none | n/a | 47,619 | 0 |
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

In 2025 the Bhakra run under observed rain flagged from 2025-08-30 and did not force the spillway within the window (to 2025-09-15). After the first flag, the measured storage of 2025-09-02 re-anchored the model's carried path downward by 0.57 BCM: the reservoir gained less than the water balance says, which is the dam passing more than its turbines, the inflow over-predicted, or both; the public record cannot separate them. The flags were therefore calls of a spill unless water was released, which is what the index means; the as-issued hits scored against them carry the same reading, and after the re-anchor the observed rain did not fill the reservoir before the window closed.

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
| Beas local | ecmwf_aifs025_single | 0 | 229 | 7.7 | -8% | 0.75 | 4.7 | 10 | 0.60 | 0.25 |
| Beas local | ecmwf_aifs025_single | 1 | 229 | 7.7 | -5% | 0.71 | 4.9 | 10 | 0.60 | 0.33 |
| Beas local | ecmwf_aifs025_single | 2 | 229 | 7.7 | +5% | 0.69 | 5.1 | 10 | 0.60 | 0.25 |
| Beas local | ecmwf_aifs025_single | 3 | 229 | 7.7 | -0% | 0.51 | 5.3 | 10 | 0.40 | 0.43 |
| Beas local | ecmwf_aifs025_single | 4 | 229 | 7.7 | -4% | 0.35 | 5.7 | 10 | 0.20 | 0.60 |
| Beas local | ecmwf_aifs025_single | 5 | 229 | 7.7 | -1% | 0.27 | 6.3 | 10 | 0.00 | 1.00 |
| Beas local | ecmwf_aifs025_single | 6 | 229 | 7.7 | +0% | 0.27 | 6.5 | 10 | 0.00 | 1.00 |
| Beas local | ecmwf_aifs025_single | 7 | 229 | 7.7 | +5% | 0.21 | 6.9 | 10 | 0.00 | 1.00 |
| Beas local | ecmwf_ifs025 | 0 | 107 | 6.4 | -31% | 0.56 | 4.1 | 3 | 0.33 | 0.00 |
| Beas local | ecmwf_ifs025 | 1 | 107 | 6.4 | -29% | 0.49 | 4.4 | 3 | 0.00 | n/a |
| Beas local | ecmwf_ifs025 | 2 | 107 | 6.4 | -14% | 0.47 | 4.5 | 3 | 0.33 | 0.50 |
| Beas local | ecmwf_ifs025 | 3 | 107 | 6.4 | -13% | 0.49 | 4.5 | 3 | 0.33 | 0.50 |
| Beas local | ecmwf_ifs025 | 4 | 107 | 6.4 | -10% | 0.52 | 4.4 | 3 | 0.33 | 0.50 |
| Beas local | ecmwf_ifs025 | 5 | 107 | 6.4 | -3% | 0.56 | 4.8 | 3 | 0.33 | 0.50 |
| Beas local | ecmwf_ifs025 | 6 | 107 | 6.4 | +6% | 0.52 | 4.9 | 3 | 0.33 | 0.50 |
| Beas local | ecmwf_ifs025 | 7 | 107 | 6.4 | -3% | 0.44 | 5.2 | 3 | 0.33 | 0.00 |
| Beas local | gfs_seamless | 0 | 107 | 6.4 | -53% | 0.48 | 4.7 | 3 | 0.33 | 0.00 |
| Beas local | gfs_seamless | 1 | 107 | 6.4 | -37% | 0.45 | 5.0 | 3 | 0.33 | 0.50 |
| Beas local | gfs_seamless | 2 | 107 | 6.4 | -30% | 0.53 | 4.5 | 3 | 0.33 | 0.00 |
| Beas local | gfs_seamless | 3 | 107 | 6.4 | -20% | 0.48 | 4.7 | 3 | 0.00 | n/a |
| Beas local | gfs_seamless | 4 | 107 | 6.4 | -7% | 0.55 | 5.1 | 3 | 0.33 | 0.50 |
| Beas local | gfs_seamless | 5 | 107 | 6.4 | -7% | 0.30 | 6.4 | 3 | 0.33 | 0.75 |
| Beas local | gfs_seamless | 6 | 107 | 6.4 | -28% | 0.53 | 4.6 | 3 | 0.33 | 0.50 |
| Beas local | gfs_seamless | 7 | 107 | 6.4 | -32% | 0.40 | 5.3 | 3 | 0.00 | n/a |
| Bhakra | ecmwf_aifs025_single | 0 | 229 | 5.4 | -27% | 0.68 | 2.7 | 0 | n/a | 1.00 |
| Bhakra | ecmwf_aifs025_single | 1 | 229 | 5.4 | -20% | 0.66 | 2.5 | 0 | n/a | 1.00 |
| Bhakra | ecmwf_aifs025_single | 2 | 229 | 5.4 | -13% | 0.59 | 2.6 | 0 | n/a | 1.00 |
| Bhakra | ecmwf_aifs025_single | 3 | 229 | 5.4 | -14% | 0.44 | 2.7 | 0 | n/a | 1.00 |
| Bhakra | ecmwf_aifs025_single | 4 | 229 | 5.4 | -15% | 0.40 | 2.8 | 0 | n/a | 1.00 |
| Bhakra | ecmwf_aifs025_single | 5 | 229 | 5.4 | -11% | 0.33 | 3.1 | 0 | n/a | 1.00 |
| Bhakra | ecmwf_aifs025_single | 6 | 229 | 5.4 | -9% | 0.44 | 3.1 | 0 | n/a | 1.00 |
| Bhakra | ecmwf_aifs025_single | 7 | 229 | 5.4 | -8% | 0.22 | 3.3 | 0 | n/a | 1.00 |
| Bhakra | ecmwf_ifs025 | 0 | 351 | 4.9 | -25% | 0.63 | 2.6 | 0 | n/a | 1.00 |
| Bhakra | ecmwf_ifs025 | 1 | 351 | 4.9 | -26% | 0.61 | 2.6 | 0 | n/a | n/a |
| Bhakra | ecmwf_ifs025 | 2 | 351 | 4.9 | -22% | 0.64 | 2.5 | 0 | n/a | 1.00 |
| Bhakra | ecmwf_ifs025 | 3 | 351 | 4.9 | -21% | 0.57 | 2.6 | 0 | n/a | n/a |
| Bhakra | ecmwf_ifs025 | 4 | 351 | 4.9 | -21% | 0.52 | 2.8 | 0 | n/a | 1.00 |
| Bhakra | ecmwf_ifs025 | 5 | 351 | 4.9 | -19% | 0.52 | 2.7 | 0 | n/a | n/a |
| Bhakra | ecmwf_ifs025 | 6 | 351 | 4.9 | -19% | 0.55 | 2.7 | 0 | n/a | n/a |
| Bhakra | ecmwf_ifs025 | 7 | 351 | 4.9 | -11% | 0.54 | 2.8 | 0 | n/a | 1.00 |
| Bhakra | gfs_seamless | 0 | 351 | 4.9 | -9% | 0.59 | 2.9 | 0 | n/a | 1.00 |
| Bhakra | gfs_seamless | 1 | 351 | 4.9 | -17% | 0.56 | 2.8 | 0 | n/a | 1.00 |
| Bhakra | gfs_seamless | 2 | 351 | 4.9 | -15% | 0.46 | 3.1 | 0 | n/a | n/a |
| Bhakra | gfs_seamless | 3 | 351 | 4.9 | -10% | 0.44 | 3.2 | 0 | n/a | n/a |
| Bhakra | gfs_seamless | 4 | 351 | 4.9 | -1% | 0.51 | 3.1 | 0 | n/a | 1.00 |
| Bhakra | gfs_seamless | 5 | 351 | 4.9 | -48% | 0.43 | 3.2 | 0 | n/a | n/a |
| Bhakra | gfs_seamless | 6 | 351 | 4.9 | -57% | 0.40 | 3.5 | 0 | n/a | n/a |
| Bhakra | gfs_seamless | 7 | 351 | 4.9 | -57% | 0.38 | 3.4 | 0 | n/a | n/a |
| Ghaggar Bhankarpur | ecmwf_aifs025_single | 0 | 229 | 6.9 | -15% | 0.50 | 5.9 | 9 | 0.22 | 0.50 |
| Ghaggar Bhankarpur | ecmwf_aifs025_single | 1 | 229 | 6.9 | +0% | 0.52 | 6.0 | 9 | 0.33 | 0.57 |
| Ghaggar Bhankarpur | ecmwf_aifs025_single | 2 | 229 | 6.9 | +16% | 0.47 | 6.5 | 9 | 0.33 | 0.50 |
| Ghaggar Bhankarpur | ecmwf_aifs025_single | 3 | 229 | 6.9 | +20% | 0.36 | 7.0 | 9 | 0.33 | 0.57 |
| Ghaggar Bhankarpur | ecmwf_aifs025_single | 4 | 229 | 6.9 | +21% | 0.26 | 7.5 | 9 | 0.22 | 0.71 |
| Ghaggar Bhankarpur | ecmwf_aifs025_single | 5 | 229 | 6.9 | +26% | 0.18 | 8.0 | 9 | 0.00 | 1.00 |
| Ghaggar Bhankarpur | ecmwf_aifs025_single | 6 | 229 | 6.9 | +29% | 0.27 | 8.1 | 9 | 0.22 | 0.71 |
| Ghaggar Bhankarpur | ecmwf_aifs025_single | 7 | 229 | 6.9 | +32% | 0.22 | 8.2 | 9 | 0.11 | 0.83 |
| Ghaggar Bhankarpur | ecmwf_ifs025 | 0 | 351 | 6.4 | -24% | 0.42 | 5.7 | 12 | 0.17 | 0.50 |
| Ghaggar Bhankarpur | ecmwf_ifs025 | 1 | 351 | 6.4 | -5% | 0.45 | 6.0 | 12 | 0.33 | 0.33 |
| Ghaggar Bhankarpur | ecmwf_ifs025 | 2 | 351 | 6.4 | +2% | 0.47 | 6.0 | 12 | 0.33 | 0.33 |
| Ghaggar Bhankarpur | ecmwf_ifs025 | 3 | 351 | 6.4 | +8% | 0.39 | 6.4 | 12 | 0.33 | 0.56 |
| Ghaggar Bhankarpur | ecmwf_ifs025 | 4 | 351 | 6.4 | +15% | 0.31 | 6.8 | 12 | 0.17 | 0.82 |
| Ghaggar Bhankarpur | ecmwf_ifs025 | 5 | 351 | 6.4 | +15% | 0.25 | 7.2 | 12 | 0.17 | 0.82 |
| Ghaggar Bhankarpur | ecmwf_ifs025 | 6 | 351 | 6.4 | +21% | 0.35 | 7.2 | 12 | 0.17 | 0.78 |
| Ghaggar Bhankarpur | ecmwf_ifs025 | 7 | 351 | 6.4 | +25% | 0.26 | 7.6 | 12 | 0.08 | 0.92 |
| Ghaggar Bhankarpur | gfs_seamless | 0 | 351 | 6.4 | -20% | 0.43 | 5.7 | 12 | 0.33 | 0.33 |
| Ghaggar Bhankarpur | gfs_seamless | 1 | 351 | 6.4 | -14% | 0.36 | 6.0 | 12 | 0.08 | 0.86 |
| Ghaggar Bhankarpur | gfs_seamless | 2 | 351 | 6.4 | +1% | 0.28 | 6.6 | 12 | 0.17 | 0.75 |
| Ghaggar Bhankarpur | gfs_seamless | 3 | 351 | 6.4 | +24% | 0.23 | 8.1 | 12 | 0.17 | 0.87 |
| Ghaggar Bhankarpur | gfs_seamless | 4 | 351 | 6.4 | +24% | 0.19 | 8.3 | 12 | 0.08 | 0.95 |
| Ghaggar Bhankarpur | gfs_seamless | 5 | 351 | 6.4 | -36% | 0.15 | 6.1 | 12 | 0.00 | 1.00 |
| Ghaggar Bhankarpur | gfs_seamless | 6 | 351 | 6.4 | -49% | 0.16 | 5.9 | 12 | 0.00 | 1.00 |
| Ghaggar Bhankarpur | gfs_seamless | 7 | 351 | 6.4 | -50% | 0.11 | 6.1 | 12 | 0.00 | 1.00 |
| Ghaggar Khanauri | ecmwf_aifs025_single | 0 | 229 | 6.4 | -13% | 0.52 | 5.0 | 7 | 0.29 | 0.33 |
| Ghaggar Khanauri | ecmwf_aifs025_single | 1 | 229 | 6.4 | +4% | 0.55 | 5.3 | 7 | 0.29 | 0.71 |
| Ghaggar Khanauri | ecmwf_aifs025_single | 2 | 229 | 6.4 | +19% | 0.51 | 5.7 | 7 | 0.29 | 0.71 |
| Ghaggar Khanauri | ecmwf_aifs025_single | 3 | 229 | 6.4 | +23% | 0.39 | 6.1 | 7 | 0.29 | 0.71 |
| Ghaggar Khanauri | ecmwf_aifs025_single | 4 | 229 | 6.4 | +25% | 0.29 | 6.6 | 7 | 0.29 | 0.71 |
| Ghaggar Khanauri | ecmwf_aifs025_single | 5 | 229 | 6.4 | +30% | 0.22 | 7.1 | 7 | 0.00 | 1.00 |
| Ghaggar Khanauri | ecmwf_aifs025_single | 6 | 229 | 6.4 | +33% | 0.25 | 7.1 | 7 | 0.14 | 0.86 |
| Ghaggar Khanauri | ecmwf_aifs025_single | 7 | 229 | 6.4 | +35% | 0.20 | 7.2 | 7 | 0.14 | 0.86 |
| Ghaggar Khanauri | ecmwf_ifs025 | 0 | 351 | 6.1 | -21% | 0.46 | 5.2 | 12 | 0.17 | 0.50 |
| Ghaggar Khanauri | ecmwf_ifs025 | 1 | 351 | 6.1 | -2% | 0.49 | 5.5 | 12 | 0.25 | 0.50 |
| Ghaggar Khanauri | ecmwf_ifs025 | 2 | 351 | 6.1 | +4% | 0.50 | 5.3 | 12 | 0.33 | 0.43 |
| Ghaggar Khanauri | ecmwf_ifs025 | 3 | 351 | 6.1 | +13% | 0.41 | 5.9 | 12 | 0.25 | 0.67 |
| Ghaggar Khanauri | ecmwf_ifs025 | 4 | 351 | 6.1 | +15% | 0.35 | 6.1 | 12 | 0.17 | 0.85 |
| Ghaggar Khanauri | ecmwf_ifs025 | 5 | 351 | 6.1 | +18% | 0.27 | 6.5 | 12 | 0.00 | 1.00 |
| Ghaggar Khanauri | ecmwf_ifs025 | 6 | 351 | 6.1 | +25% | 0.39 | 6.5 | 12 | 0.17 | 0.78 |
| Ghaggar Khanauri | ecmwf_ifs025 | 7 | 351 | 6.1 | +26% | 0.31 | 6.8 | 12 | 0.08 | 0.90 |
| Ghaggar Khanauri | gfs_seamless | 0 | 351 | 6.1 | -23% | 0.43 | 5.1 | 12 | 0.17 | 0.60 |
| Ghaggar Khanauri | gfs_seamless | 1 | 351 | 6.1 | -16% | 0.36 | 5.4 | 12 | 0.08 | 0.83 |
| Ghaggar Khanauri | gfs_seamless | 2 | 351 | 6.1 | -2% | 0.33 | 5.8 | 12 | 0.17 | 0.75 |
| Ghaggar Khanauri | gfs_seamless | 3 | 351 | 6.1 | +20% | 0.26 | 7.2 | 12 | 0.17 | 0.86 |
| Ghaggar Khanauri | gfs_seamless | 4 | 351 | 6.1 | +25% | 0.22 | 7.6 | 12 | 0.08 | 0.94 |
| Ghaggar Khanauri | gfs_seamless | 5 | 351 | 6.1 | -37% | 0.20 | 5.5 | 12 | 0.08 | 0.67 |
| Ghaggar Khanauri | gfs_seamless | 6 | 351 | 6.1 | -51% | 0.20 | 5.4 | 12 | 0.00 | 1.00 |
| Ghaggar Khanauri | gfs_seamless | 7 | 351 | 6.1 | -52% | 0.18 | 5.5 | 12 | 0.00 | n/a |
| Harike local | ecmwf_aifs025_single | 0 | 229 | 6.0 | -12% | 0.76 | 3.8 | 8 | 0.38 | 0.40 |
| Harike local | ecmwf_aifs025_single | 1 | 229 | 6.0 | +1% | 0.78 | 3.8 | 8 | 0.50 | 0.33 |
| Harike local | ecmwf_aifs025_single | 2 | 229 | 6.0 | +13% | 0.77 | 4.2 | 8 | 0.50 | 0.00 |
| Harike local | ecmwf_aifs025_single | 3 | 229 | 6.0 | +12% | 0.52 | 4.7 | 8 | 0.38 | 0.25 |
| Harike local | ecmwf_aifs025_single | 4 | 229 | 6.0 | +9% | 0.32 | 5.3 | 8 | 0.12 | 0.50 |
| Harike local | ecmwf_aifs025_single | 5 | 229 | 6.0 | +14% | 0.23 | 6.0 | 8 | 0.00 | 1.00 |
| Harike local | ecmwf_aifs025_single | 6 | 229 | 6.0 | +16% | 0.25 | 6.1 | 8 | 0.00 | 1.00 |
| Harike local | ecmwf_aifs025_single | 7 | 229 | 6.0 | +19% | 0.24 | 6.4 | 8 | 0.00 | 1.00 |
| Harike local | ecmwf_ifs025 | 0 | 107 | 3.7 | -5% | 0.36 | 3.2 | 0 | n/a | n/a |
| Harike local | ecmwf_ifs025 | 1 | 107 | 3.7 | +9% | 0.36 | 3.5 | 0 | n/a | n/a |
| Harike local | ecmwf_ifs025 | 2 | 107 | 3.7 | +26% | 0.48 | 3.4 | 0 | n/a | n/a |
| Harike local | ecmwf_ifs025 | 3 | 107 | 3.7 | +30% | 0.48 | 3.6 | 0 | n/a | n/a |
| Harike local | ecmwf_ifs025 | 4 | 107 | 3.7 | +35% | 0.41 | 3.7 | 0 | n/a | 1.00 |
| Harike local | ecmwf_ifs025 | 5 | 107 | 3.7 | +45% | 0.38 | 4.2 | 0 | n/a | n/a |
| Harike local | ecmwf_ifs025 | 6 | 107 | 3.7 | +52% | 0.37 | 4.3 | 0 | n/a | 1.00 |
| Harike local | ecmwf_ifs025 | 7 | 107 | 3.7 | +53% | 0.34 | 4.5 | 0 | n/a | 1.00 |
| Harike local | gfs_seamless | 0 | 107 | 3.7 | -45% | 0.26 | 3.3 | 0 | n/a | n/a |
| Harike local | gfs_seamless | 1 | 107 | 3.7 | -29% | 0.36 | 3.0 | 0 | n/a | n/a |
| Harike local | gfs_seamless | 2 | 107 | 3.7 | -3% | 0.40 | 3.5 | 0 | n/a | 1.00 |
| Harike local | gfs_seamless | 3 | 107 | 3.7 | +14% | 0.35 | 3.8 | 0 | n/a | 1.00 |
| Harike local | gfs_seamless | 4 | 107 | 3.7 | +33% | 0.38 | 4.3 | 0 | n/a | 1.00 |
| Harike local | gfs_seamless | 5 | 107 | 3.7 | +23% | 0.22 | 4.7 | 0 | n/a | 1.00 |
| Harike local | gfs_seamless | 6 | 107 | 3.7 | +3% | 0.21 | 4.3 | 0 | n/a | 1.00 |
| Harike local | gfs_seamless | 7 | 107 | 3.7 | +6% | 0.24 | 3.9 | 0 | n/a | n/a |
| Pong | ecmwf_aifs025_single | 0 | 229 | 10.7 | -23% | 0.65 | 5.8 | 17 | 0.35 | 0.45 |
| Pong | ecmwf_aifs025_single | 1 | 229 | 10.7 | -17% | 0.60 | 5.8 | 17 | 0.24 | 0.50 |
| Pong | ecmwf_aifs025_single | 2 | 229 | 10.7 | -9% | 0.56 | 5.9 | 17 | 0.41 | 0.30 |
| Pong | ecmwf_aifs025_single | 3 | 229 | 10.7 | -12% | 0.35 | 6.4 | 17 | 0.24 | 0.43 |
| Pong | ecmwf_aifs025_single | 4 | 229 | 10.7 | -14% | 0.28 | 6.6 | 17 | 0.00 | 1.00 |
| Pong | ecmwf_aifs025_single | 5 | 229 | 10.7 | -10% | 0.27 | 7.1 | 17 | 0.06 | 0.80 |
| Pong | ecmwf_aifs025_single | 6 | 229 | 10.7 | -9% | 0.31 | 7.3 | 17 | 0.06 | 0.67 |
| Pong | ecmwf_aifs025_single | 7 | 229 | 10.7 | -6% | 0.17 | 7.6 | 17 | 0.06 | 0.80 |
| Pong | ecmwf_ifs025 | 0 | 351 | 9.5 | -24% | 0.57 | 5.9 | 19 | 0.26 | 0.58 |
| Pong | ecmwf_ifs025 | 1 | 351 | 9.5 | -29% | 0.58 | 5.7 | 19 | 0.21 | 0.56 |
| Pong | ecmwf_ifs025 | 2 | 351 | 9.5 | -18% | 0.56 | 5.9 | 19 | 0.26 | 0.58 |
| Pong | ecmwf_ifs025 | 3 | 351 | 9.5 | -19% | 0.47 | 6.3 | 19 | 0.11 | 0.78 |
| Pong | ecmwf_ifs025 | 4 | 351 | 9.5 | -19% | 0.55 | 6.0 | 19 | 0.16 | 0.57 |
| Pong | ecmwf_ifs025 | 5 | 351 | 9.5 | -17% | 0.53 | 6.2 | 19 | 0.16 | 0.70 |
| Pong | ecmwf_ifs025 | 6 | 351 | 9.5 | -15% | 0.52 | 6.3 | 19 | 0.21 | 0.56 |
| Pong | ecmwf_ifs025 | 7 | 351 | 9.5 | -10% | 0.58 | 6.0 | 19 | 0.21 | 0.69 |
| Pong | gfs_seamless | 0 | 351 | 9.5 | -15% | 0.54 | 6.2 | 19 | 0.26 | 0.55 |
| Pong | gfs_seamless | 1 | 351 | 9.5 | -26% | 0.47 | 6.4 | 19 | 0.11 | 0.75 |
| Pong | gfs_seamless | 2 | 351 | 9.5 | -26% | 0.50 | 6.4 | 19 | 0.05 | 0.80 |
| Pong | gfs_seamless | 3 | 351 | 9.5 | -16% | 0.48 | 6.7 | 19 | 0.11 | 0.75 |
| Pong | gfs_seamless | 4 | 351 | 9.5 | -5% | 0.41 | 7.0 | 19 | 0.05 | 0.92 |
| Pong | gfs_seamless | 5 | 351 | 9.5 | -50% | 0.37 | 7.1 | 19 | 0.00 | 1.00 |
| Pong | gfs_seamless | 6 | 351 | 9.5 | -59% | 0.38 | 7.2 | 19 | 0.00 | 1.00 |
| Pong | gfs_seamless | 7 | 351 | 9.5 | -59% | 0.32 | 7.2 | 19 | 0.00 | 1.00 |
| Ranjit Sagar | ecmwf_aifs025_single | 0 | 229 | 9.5 | -6% | 0.71 | 5.8 | 18 | 0.33 | 0.25 |
| Ranjit Sagar | ecmwf_aifs025_single | 1 | 229 | 9.5 | -8% | 0.68 | 5.8 | 18 | 0.22 | 0.56 |
| Ranjit Sagar | ecmwf_aifs025_single | 2 | 229 | 9.5 | -2% | 0.61 | 6.2 | 18 | 0.39 | 0.30 |
| Ranjit Sagar | ecmwf_aifs025_single | 3 | 229 | 9.5 | -7% | 0.37 | 6.7 | 18 | 0.17 | 0.50 |
| Ranjit Sagar | ecmwf_aifs025_single | 4 | 229 | 9.5 | -11% | 0.28 | 6.9 | 18 | 0.11 | 0.50 |
| Ranjit Sagar | ecmwf_aifs025_single | 5 | 229 | 9.5 | -9% | 0.21 | 7.4 | 18 | 0.00 | 1.00 |
| Ranjit Sagar | ecmwf_aifs025_single | 6 | 229 | 9.5 | -9% | 0.22 | 7.6 | 18 | 0.00 | 1.00 |
| Ranjit Sagar | ecmwf_aifs025_single | 7 | 229 | 9.5 | -7% | 0.15 | 7.6 | 18 | 0.00 | 1.00 |
| Ranjit Sagar | ecmwf_ifs025 | 0 | 351 | 8.2 | -10% | 0.67 | 5.5 | 21 | 0.24 | 0.44 |
| Ranjit Sagar | ecmwf_ifs025 | 1 | 351 | 8.2 | -29% | 0.66 | 5.3 | 21 | 0.19 | 0.20 |
| Ranjit Sagar | ecmwf_ifs025 | 2 | 351 | 8.2 | -19% | 0.56 | 5.9 | 21 | 0.14 | 0.62 |
| Ranjit Sagar | ecmwf_ifs025 | 3 | 351 | 8.2 | -21% | 0.55 | 5.9 | 21 | 0.24 | 0.38 |
| Ranjit Sagar | ecmwf_ifs025 | 4 | 351 | 8.2 | -21% | 0.62 | 5.5 | 21 | 0.10 | 0.60 |
| Ranjit Sagar | ecmwf_ifs025 | 5 | 351 | 8.2 | -17% | 0.51 | 5.9 | 21 | 0.10 | 0.75 |
| Ranjit Sagar | ecmwf_ifs025 | 6 | 351 | 8.2 | -23% | 0.57 | 5.8 | 21 | 0.10 | 0.60 |
| Ranjit Sagar | ecmwf_ifs025 | 7 | 351 | 8.2 | -19% | 0.58 | 5.7 | 21 | 0.14 | 0.40 |
| Ranjit Sagar | gfs_seamless | 0 | 351 | 8.2 | -5% | 0.61 | 6.0 | 21 | 0.19 | 0.56 |
| Ranjit Sagar | gfs_seamless | 1 | 351 | 8.2 | -18% | 0.55 | 5.8 | 21 | 0.14 | 0.50 |
| Ranjit Sagar | gfs_seamless | 2 | 351 | 8.2 | -21% | 0.50 | 6.1 | 21 | 0.05 | 0.67 |
| Ranjit Sagar | gfs_seamless | 3 | 351 | 8.2 | -16% | 0.45 | 6.1 | 21 | 0.05 | 0.67 |
| Ranjit Sagar | gfs_seamless | 4 | 351 | 8.2 | -3% | 0.33 | 7.0 | 21 | 0.10 | 0.80 |
| Ranjit Sagar | gfs_seamless | 5 | 351 | 8.2 | -46% | 0.39 | 6.3 | 21 | 0.10 | 0.33 |
| Ranjit Sagar | gfs_seamless | 6 | 351 | 8.2 | -58% | 0.42 | 6.2 | 21 | 0.00 | 1.00 |
| Ranjit Sagar | gfs_seamless | 7 | 351 | 8.2 | -58% | 0.35 | 6.4 | 21 | 0.00 | n/a |
| Sutlej local | ecmwf_aifs025_single | 0 | 229 | 8.6 | -33% | 0.67 | 5.8 | 14 | 0.21 | 0.25 |
| Sutlej local | ecmwf_aifs025_single | 1 | 229 | 8.6 | -25% | 0.70 | 5.4 | 14 | 0.21 | 0.50 |
| Sutlej local | ecmwf_aifs025_single | 2 | 229 | 8.6 | -13% | 0.70 | 5.7 | 14 | 0.29 | 0.20 |
| Sutlej local | ecmwf_aifs025_single | 3 | 229 | 8.6 | -13% | 0.46 | 6.4 | 14 | 0.14 | 0.60 |
| Sutlej local | ecmwf_aifs025_single | 4 | 229 | 8.6 | -14% | 0.28 | 7.1 | 14 | 0.07 | 0.75 |
| Sutlej local | ecmwf_aifs025_single | 5 | 229 | 8.6 | -9% | 0.23 | 7.7 | 14 | 0.00 | 1.00 |
| Sutlej local | ecmwf_aifs025_single | 6 | 229 | 8.6 | -7% | 0.30 | 7.7 | 14 | 0.07 | 0.80 |
| Sutlej local | ecmwf_aifs025_single | 7 | 229 | 8.6 | -3% | 0.29 | 7.8 | 14 | 0.07 | 0.80 |
| Sutlej local | ecmwf_ifs025 | 0 | 107 | 5.9 | -33% | 0.34 | 4.5 | 2 | 0.00 | n/a |
| Sutlej local | ecmwf_ifs025 | 1 | 107 | 5.9 | -17% | 0.38 | 4.5 | 2 | 0.00 | n/a |
| Sutlej local | ecmwf_ifs025 | 2 | 107 | 5.9 | -4% | 0.39 | 4.7 | 2 | 0.00 | n/a |
| Sutlej local | ecmwf_ifs025 | 3 | 107 | 5.9 | +4% | 0.38 | 4.8 | 2 | 0.00 | 1.00 |
| Sutlej local | ecmwf_ifs025 | 4 | 107 | 5.9 | +7% | 0.32 | 5.3 | 2 | 0.00 | 1.00 |
| Sutlej local | ecmwf_ifs025 | 5 | 107 | 5.9 | +11% | 0.38 | 5.3 | 2 | 0.00 | 1.00 |
| Sutlej local | ecmwf_ifs025 | 6 | 107 | 5.9 | +10% | 0.35 | 5.3 | 2 | 0.00 | n/a |
| Sutlej local | ecmwf_ifs025 | 7 | 107 | 5.9 | +18% | 0.33 | 6.0 | 2 | 0.00 | 1.00 |
| Sutlej local | gfs_seamless | 0 | 107 | 5.9 | -50% | 0.29 | 4.8 | 2 | 0.00 | n/a |
| Sutlej local | gfs_seamless | 1 | 107 | 5.9 | -28% | 0.35 | 4.7 | 2 | 0.00 | 1.00 |
| Sutlej local | gfs_seamless | 2 | 107 | 5.9 | -14% | 0.42 | 4.8 | 2 | 0.00 | 1.00 |
| Sutlej local | gfs_seamless | 3 | 107 | 5.9 | +3% | 0.29 | 5.9 | 2 | 0.00 | 1.00 |
| Sutlej local | gfs_seamless | 4 | 107 | 5.9 | +17% | 0.32 | 6.3 | 2 | 0.00 | 1.00 |
| Sutlej local | gfs_seamless | 5 | 107 | 5.9 | +20% | 0.21 | 7.4 | 2 | 0.00 | 1.00 |
| Sutlej local | gfs_seamless | 6 | 107 | 5.9 | -4% | 0.24 | 6.0 | 2 | 0.00 | 1.00 |
| Sutlej local | gfs_seamless | 7 | 107 | 5.9 | -1% | 0.31 | 5.7 | 2 | 0.00 | 1.00 |

### Multiplicative bias correction, tested out of sample

One factor per catchment, model and lead (observed season rain over forecast season rain, clipped to 0.5 to 2), fitted on every season but one and applied to the held-out season; the held-out days of all seasons are scored together. Pearson r does not move under a scale factor, so the columns that can move are shown raw and corrected. Leads 1 to 5 are the product's horizons.

| catchment | model | lead (days) | days | held-out factors | bias raw / corrected | MAE (mm) raw / corrected | hit rate raw / corrected | false-alarm ratio raw / corrected |
|---|---|---|---|---|---|---|---|---|
| Beas local | ecmwf_aifs025_single | 1 | 229 | 0.99 to 1.17 | -5% / +5% | 4.9 / 5.1 | 0.60 / 0.60 | 0.33 / 0.40 |
| Beas local | ecmwf_aifs025_single | 2 | 229 | 0.86 to 1.15 | +5% / +10% | 5.1 / 5.5 | 0.60 / 0.60 | 0.25 / 0.33 |
| Beas local | ecmwf_aifs025_single | 3 | 229 | 0.94 to 1.12 | -0% / +5% | 5.3 / 5.4 | 0.40 / 0.50 | 0.43 / 0.44 |
| Beas local | ecmwf_aifs025_single | 4 | 229 | 1.05 to 1.05 | -4% / +0% | 5.7 / 5.8 | 0.20 / 0.20 | 0.60 / 0.60 |
| Beas local | ecmwf_aifs025_single | 5 | 229 | 1.00 to 1.01 | -1% / -0% | 6.3 / 6.3 | 0.00 / 0.00 | 1.00 / 1.00 |
| Bhakra | ecmwf_aifs025_single | 1 | 229 | 1.15 to 1.39 | -20% / +4% | 2.5 / 2.8 | n/a / n/a | 1.00 / 1.00 |
| Bhakra | ecmwf_aifs025_single | 2 | 229 | 1.03 to 1.32 | -13% / +5% | 2.6 / 3.0 | n/a / n/a | 1.00 / 1.00 |
| Bhakra | ecmwf_aifs025_single | 3 | 229 | 1.07 to 1.28 | -14% / +3% | 2.7 / 2.9 | n/a / n/a | 1.00 / 1.00 |
| Bhakra | ecmwf_aifs025_single | 4 | 229 | 1.11 to 1.25 | -15% / +2% | 2.8 / 2.9 | n/a / n/a | 1.00 / 1.00 |
| Bhakra | ecmwf_aifs025_single | 5 | 229 | 1.07 to 1.21 | -11% / +2% | 3.1 / 3.2 | n/a / n/a | 1.00 / 1.00 |
| Bhakra | ecmwf_ifs025 | 1 | 351 | 1.25 to 1.44 | -26% / +1% | 2.6 / 2.8 | n/a / n/a | n/a / 1.00 |
| Bhakra | ecmwf_ifs025 | 2 | 351 | 1.20 to 1.33 | -22% / +1% | 2.5 / 2.7 | n/a / n/a | 1.00 / 1.00 |
| Bhakra | ecmwf_ifs025 | 3 | 351 | 1.22 to 1.30 | -21% / +0% | 2.6 / 2.8 | n/a / n/a | n/a / 1.00 |
| Bhakra | ecmwf_ifs025 | 4 | 351 | 1.19 to 1.32 | -21% / +0% | 2.8 / 3.0 | n/a / n/a | 1.00 / 1.00 |
| Bhakra | ecmwf_ifs025 | 5 | 351 | 1.18 to 1.29 | -19% / -0% | 2.7 / 3.0 | n/a / n/a | n/a / 1.00 |
| Bhakra | gfs_seamless | 1 | 351 | 1.10 to 1.26 | -17% / +1% | 2.8 / 3.0 | n/a / n/a | 1.00 / 1.00 |
| Bhakra | gfs_seamless | 2 | 351 | 1.11 to 1.28 | -15% / +0% | 3.1 / 3.3 | n/a / n/a | n/a / 1.00 |
| Bhakra | gfs_seamless | 3 | 351 | 1.02 to 1.25 | -10% / +1% | 3.2 / 3.4 | n/a / n/a | n/a / 1.00 |
| Bhakra | gfs_seamless | 4 | 351 | 0.94 to 1.11 | -1% / +0% | 3.1 / 3.2 | n/a / n/a | 1.00 / 1.00 |
| Bhakra | gfs_seamless | 5 | 351 | 1.68 to 2.00 | -48% / -3% | 3.2 / 3.5 | n/a / n/a | n/a / 1.00 |
| Ghaggar Bhankarpur | ecmwf_aifs025_single | 1 | 229 | 0.99 to 1.00 | +0% / -0% | 6.0 / 5.9 | 0.33 / 0.33 | 0.57 / 0.57 |
| Ghaggar Bhankarpur | ecmwf_aifs025_single | 2 | 229 | 0.85 to 0.87 | +16% / -1% | 6.5 / 6.1 | 0.33 / 0.22 | 0.50 / 0.50 |
| Ghaggar Bhankarpur | ecmwf_aifs025_single | 3 | 229 | 0.76 to 0.89 | +20% / -3% | 7.0 / 6.5 | 0.33 / 0.22 | 0.57 / 0.60 |
| Ghaggar Bhankarpur | ecmwf_aifs025_single | 4 | 229 | 0.71 to 0.91 | +21% / -4% | 7.5 / 6.9 | 0.22 / 0.00 | 0.71 / 1.00 |
| Ghaggar Bhankarpur | ecmwf_aifs025_single | 5 | 229 | 0.68 to 0.87 | +26% / -4% | 8.0 / 7.2 | 0.00 / 0.00 | 1.00 / 1.00 |
| Ghaggar Bhankarpur | ecmwf_ifs025 | 1 | 351 | 1.04 to 1.07 | -5% / +0% | 6.0 / 6.2 | 0.33 / 0.33 | 0.33 / 0.33 |
| Ghaggar Bhankarpur | ecmwf_ifs025 | 2 | 351 | 0.92 to 1.07 | +2% / +3% | 6.0 / 6.1 | 0.33 / 0.33 | 0.33 / 0.33 |
| Ghaggar Bhankarpur | ecmwf_ifs025 | 3 | 351 | 0.91 to 0.96 | +8% / +1% | 6.4 / 6.2 | 0.33 / 0.33 | 0.56 / 0.56 |
| Ghaggar Bhankarpur | ecmwf_ifs025 | 4 | 351 | 0.85 to 0.91 | +15% / +1% | 6.8 / 6.4 | 0.17 / 0.17 | 0.82 / 0.75 |
| Ghaggar Bhankarpur | ecmwf_ifs025 | 5 | 351 | 0.86 to 0.88 | +15% / +0% | 7.2 / 6.7 | 0.17 / 0.00 | 0.82 / 1.00 |
| Ghaggar Bhankarpur | gfs_seamless | 1 | 351 | 1.10 to 1.29 | -14% / +4% | 6.0 / 6.5 | 0.08 / 0.25 | 0.86 / 0.80 |
| Ghaggar Bhankarpur | gfs_seamless | 2 | 351 | 0.93 to 1.12 | +1% / +1% | 6.6 / 6.6 | 0.17 / 0.17 | 0.75 / 0.75 |
| Ghaggar Bhankarpur | gfs_seamless | 3 | 351 | 0.73 to 0.93 | +24% / +1% | 8.1 / 7.3 | 0.17 / 0.17 | 0.87 / 0.85 |
| Ghaggar Bhankarpur | gfs_seamless | 4 | 351 | 0.72 to 0.93 | +24% / +1% | 8.3 / 7.4 | 0.08 / 0.08 | 0.95 / 0.88 |
| Ghaggar Bhankarpur | gfs_seamless | 5 | 351 | 1.30 to 1.86 | -36% / +2% | 6.1 / 7.4 | 0.00 / 0.00 | 1.00 / 1.00 |
| Ghaggar Khanauri | ecmwf_aifs025_single | 1 | 229 | 0.94 to 1.00 | +4% / +2% | 5.3 / 5.2 | 0.29 / 0.29 | 0.71 / 0.71 |
| Ghaggar Khanauri | ecmwf_aifs025_single | 2 | 229 | 0.82 to 0.86 | +19% / +1% | 5.7 / 5.2 | 0.29 / 0.29 | 0.71 / 0.50 |
| Ghaggar Khanauri | ecmwf_aifs025_single | 3 | 229 | 0.77 to 0.84 | +23% / -2% | 6.1 / 5.6 | 0.29 / 0.29 | 0.71 / 0.50 |
| Ghaggar Khanauri | ecmwf_aifs025_single | 4 | 229 | 0.72 to 0.86 | +25% / -3% | 6.6 / 6.0 | 0.29 / 0.00 | 0.71 / 1.00 |
| Ghaggar Khanauri | ecmwf_aifs025_single | 5 | 229 | 0.69 to 0.83 | +30% / -3% | 7.1 / 6.3 | 0.00 / 0.00 | 1.00 / 1.00 |
| Ghaggar Khanauri | ecmwf_ifs025 | 1 | 351 | 1.00 to 1.10 | -2% / +2% | 5.5 / 5.7 | 0.25 / 0.25 | 0.50 / 0.50 |
| Ghaggar Khanauri | ecmwf_ifs025 | 2 | 351 | 0.88 to 1.09 | +4% / +5% | 5.3 / 5.4 | 0.33 / 0.33 | 0.43 / 0.43 |
| Ghaggar Khanauri | ecmwf_ifs025 | 3 | 351 | 0.85 to 0.96 | +13% / +2% | 5.9 / 5.6 | 0.25 / 0.25 | 0.67 / 0.67 |
| Ghaggar Khanauri | ecmwf_ifs025 | 4 | 351 | 0.84 to 0.96 | +15% / +3% | 6.1 / 5.8 | 0.17 / 0.17 | 0.85 / 0.82 |
| Ghaggar Khanauri | ecmwf_ifs025 | 5 | 351 | 0.82 to 0.91 | +18% / +2% | 6.5 / 6.1 | 0.00 / 0.00 | 1.00 / 1.00 |
| Ghaggar Khanauri | gfs_seamless | 1 | 351 | 1.08 to 1.41 | -16% / +7% | 5.4 / 6.2 | 0.08 / 0.17 | 0.83 / 0.87 |
| Ghaggar Khanauri | gfs_seamless | 2 | 351 | 0.96 to 1.12 | -2% / +1% | 5.8 / 6.0 | 0.17 / 0.17 | 0.75 / 0.71 |
| Ghaggar Khanauri | gfs_seamless | 3 | 351 | 0.79 to 0.95 | +20% / +2% | 7.2 / 6.6 | 0.17 / 0.17 | 0.86 / 0.83 |
| Ghaggar Khanauri | gfs_seamless | 4 | 351 | 0.76 to 0.90 | +25% / +2% | 7.6 / 6.7 | 0.08 / 0.08 | 0.94 / 0.88 |
| Ghaggar Khanauri | gfs_seamless | 5 | 351 | 1.37 to 1.86 | -37% / +1% | 5.5 / 6.6 | 0.08 / 0.08 | 0.67 / 0.91 |
| Harike local | ecmwf_aifs025_single | 1 | 229 | 0.84 to 1.07 | +1% / -7% | 3.8 / 3.9 | 0.50 / 0.38 | 0.33 / 0.40 |
| Harike local | ecmwf_aifs025_single | 2 | 229 | 0.80 to 0.92 | +13% / -5% | 4.2 / 3.9 | 0.50 / 0.50 | 0.00 / 0.00 |
| Harike local | ecmwf_aifs025_single | 3 | 229 | 0.73 to 0.99 | +12% / -9% | 4.7 / 4.7 | 0.38 / 0.38 | 0.25 / 0.25 |
| Harike local | ecmwf_aifs025_single | 4 | 229 | 0.65 to 1.09 | +9% / -9% | 5.3 / 5.4 | 0.12 / 0.00 | 0.50 / 1.00 |
| Harike local | ecmwf_aifs025_single | 5 | 229 | 0.63 to 1.04 | +14% / -9% | 6.0 / 5.7 | 0.00 / 0.00 | 1.00 / 1.00 |
| Pong | ecmwf_aifs025_single | 1 | 229 | 1.10 to 1.40 | -17% / +8% | 5.8 / 6.3 | 0.24 / 0.41 | 0.50 / 0.50 |
| Pong | ecmwf_aifs025_single | 2 | 229 | 0.97 to 1.38 | -9% / +13% | 5.9 / 7.1 | 0.41 / 0.47 | 0.30 / 0.60 |
| Pong | ecmwf_aifs025_single | 3 | 229 | 1.03 to 1.34 | -12% / +9% | 6.4 / 7.0 | 0.24 / 0.29 | 0.43 / 0.50 |
| Pong | ecmwf_aifs025_single | 4 | 229 | 1.08 to 1.30 | -14% / +5% | 6.6 / 7.0 | 0.00 / 0.18 | 1.00 / 0.57 |
| Pong | ecmwf_aifs025_single | 5 | 229 | 1.02 to 1.30 | -10% / +8% | 7.1 / 7.7 | 0.06 / 0.12 | 0.80 / 0.75 |
| Pong | ecmwf_ifs025 | 1 | 351 | 1.37 to 1.46 | -29% / -0% | 5.7 / 6.0 | 0.21 / 0.26 | 0.56 / 0.62 |
| Pong | ecmwf_ifs025 | 2 | 351 | 1.20 to 1.25 | -18% / -0% | 5.9 / 6.1 | 0.26 / 0.37 | 0.58 / 0.56 |
| Pong | ecmwf_ifs025 | 3 | 351 | 1.18 to 1.27 | -19% / -1% | 6.3 / 6.6 | 0.11 / 0.11 | 0.78 / 0.80 |
| Pong | ecmwf_ifs025 | 4 | 351 | 1.18 to 1.30 | -19% / -1% | 6.0 / 6.4 | 0.16 / 0.21 | 0.57 / 0.71 |
| Pong | ecmwf_ifs025 | 5 | 351 | 1.10 to 1.27 | -17% / -1% | 6.2 / 6.5 | 0.16 / 0.21 | 0.70 / 0.73 |
| Pong | gfs_seamless | 1 | 351 | 1.29 to 1.44 | -26% / +0% | 6.4 / 6.8 | 0.11 / 0.11 | 0.75 / 0.83 |
| Pong | gfs_seamless | 2 | 351 | 1.21 to 1.54 | -26% / +0% | 6.4 / 6.9 | 0.05 / 0.05 | 0.80 / 0.93 |
| Pong | gfs_seamless | 3 | 351 | 1.04 to 1.43 | -16% / +2% | 6.7 / 7.4 | 0.11 / 0.11 | 0.75 / 0.83 |
| Pong | gfs_seamless | 4 | 351 | 0.92 to 1.24 | -5% / +1% | 7.0 / 7.5 | 0.05 / 0.16 | 0.92 / 0.84 |
| Pong | gfs_seamless | 5 | 351 | 1.64 to 2.00 | -50% / -7% | 7.1 / 7.7 | 0.00 / 0.05 | 1.00 / 0.94 |
| Ranjit Sagar | ecmwf_aifs025_single | 1 | 229 | 0.98 to 1.29 | -8% / +8% | 5.8 / 6.3 | 0.22 / 0.28 | 0.56 / 0.50 |
| Ranjit Sagar | ecmwf_aifs025_single | 2 | 229 | 0.88 to 1.30 | -2% / +14% | 6.2 / 7.2 | 0.39 / 0.33 | 0.30 / 0.50 |
| Ranjit Sagar | ecmwf_aifs025_single | 3 | 229 | 0.95 to 1.32 | -7% / +10% | 6.7 / 7.3 | 0.17 / 0.17 | 0.50 / 0.67 |
| Ranjit Sagar | ecmwf_aifs025_single | 4 | 229 | 1.02 to 1.29 | -11% / +6% | 6.9 / 7.3 | 0.11 / 0.17 | 0.50 / 0.57 |
| Ranjit Sagar | ecmwf_aifs025_single | 5 | 229 | 1.00 to 1.28 | -9% / +7% | 7.4 / 8.0 | 0.00 / 0.00 | 1.00 / 1.00 |
| Ranjit Sagar | ecmwf_ifs025 | 1 | 351 | 1.36 to 1.47 | -29% / -0% | 5.3 / 5.5 | 0.19 / 0.29 | 0.20 / 0.50 |
| Ranjit Sagar | ecmwf_ifs025 | 2 | 351 | 1.20 to 1.28 | -19% / -0% | 5.9 / 6.2 | 0.14 / 0.38 | 0.62 / 0.53 |
| Ranjit Sagar | ecmwf_ifs025 | 3 | 351 | 1.23 to 1.31 | -21% / -0% | 5.9 / 6.2 | 0.24 / 0.24 | 0.38 / 0.44 |
| Ranjit Sagar | ecmwf_ifs025 | 4 | 351 | 1.22 to 1.33 | -21% / -1% | 5.5 / 5.8 | 0.10 / 0.29 | 0.60 / 0.57 |
| Ranjit Sagar | ecmwf_ifs025 | 5 | 351 | 1.16 to 1.28 | -17% / -1% | 5.9 / 6.3 | 0.10 / 0.14 | 0.75 / 0.75 |
| Ranjit Sagar | gfs_seamless | 1 | 351 | 1.16 to 1.29 | -18% / -0% | 5.8 / 6.1 | 0.14 / 0.19 | 0.50 / 0.50 |
| Ranjit Sagar | gfs_seamless | 2 | 351 | 1.13 to 1.41 | -21% / -1% | 6.1 / 6.5 | 0.05 / 0.14 | 0.67 / 0.57 |
| Ranjit Sagar | gfs_seamless | 3 | 351 | 1.00 to 1.42 | -16% / +1% | 6.1 / 6.8 | 0.05 / 0.05 | 0.67 / 0.83 |
| Ranjit Sagar | gfs_seamless | 4 | 351 | 0.89 to 1.23 | -3% / +1% | 7.0 / 7.3 | 0.10 / 0.05 | 0.80 / 0.90 |
| Ranjit Sagar | gfs_seamless | 5 | 351 | 1.48 to 2.00 | -46% / -2% | 6.3 / 7.2 | 0.10 / 0.24 | 0.33 / 0.69 |
| Sutlej local | ecmwf_aifs025_single | 1 | 229 | 1.18 to 1.40 | -25% / -5% | 5.4 / 5.8 | 0.21 / 0.36 | 0.50 / 0.44 |
| Sutlej local | ecmwf_aifs025_single | 2 | 229 | 1.09 to 1.18 | -13% / -3% | 5.7 / 5.8 | 0.29 / 0.43 | 0.20 / 0.25 |
| Sutlej local | ecmwf_aifs025_single | 3 | 229 | 0.98 to 1.25 | -13% / -6% | 6.4 / 6.7 | 0.14 / 0.14 | 0.60 / 0.60 |
| Sutlej local | ecmwf_aifs025_single | 4 | 229 | 0.90 to 1.33 | -14% / -7% | 7.1 / 7.5 | 0.07 / 0.00 | 0.75 / 1.00 |
| Sutlej local | ecmwf_aifs025_single | 5 | 229 | 0.88 to 1.25 | -9% / -7% | 7.7 / 8.0 | 0.00 / 0.00 | 1.00 / 1.00 |

Held-out days, dam catchments, leads 1 to 5: MAE lower after correction in 0 of 45 rows, heavy-day hit rate higher in 20, false-alarm ratio higher in 17. The product applies a correction only when MAE and hit rate both improve on the held-out seasons for a dam catchment; the rule is in `design.md`.

### The machine-learned model against the primary deterministic model

`ecmwf_aifs025_single` (ECMWF AIFS, the machine-learned forecast) and `ecmwf_ifs025` scored on exactly the same rows: the dam catchments, leads 1, 2, 3, every target day both have in the archive (2,061 rows). The rule, written before the pull: the challenger replaces the incumbent as the product's primary deterministic model only if its heavy-day hit rate is higher and its false-alarm ratio is not higher on those rows. The spill probability comes from the IFS ensemble either way; the primary deterministic model drives the local term and the deterministic fallback.

| model | obs mean (mm) | bias | r | MAE (mm) | heavy days | hit rate | false-alarm ratio |
|---|---|---|---|---|---|---|---|
| ecmwf_ifs025 | 8.5 | -25% | 0.58 | 5.1 | 105 | 0.20 | 0.51 |
| ecmwf_aifs025_single | 8.5 | -11% | 0.54 | 5.0 | 105 | 0.28 | 0.47 |

Hit rate higher: yes; false-alarm ratio not higher: yes. Verdict: the primary deterministic model switches to ecmwf_aifs025_single. The product's primary is `ecmwf_aifs025_single`.

### The deterministic models combined against the primary one

Three ways of combining `ecmwf_aifs025_single`, `ecmwf_ifs025`, `gfs_seamless` scored on the 2,061 (catchment, day, lead) rows all of them have over the dam catchments at leads 1, 2, 3: the equal-weight mean, an inverse-MAE weighted mean with the weights fitted on every season but the one scored, and the largest of the three (the hazard-minded blend). Same rule as the model switch: a blend replaces the primary only if its heavy-day hit rate is higher and its false-alarm ratio is not higher on the same rows.

| rain source | bias | r | MAE (mm) | heavy days | hit rate | false-alarm ratio | passes the rule |
|---|---|---|---|---|---|---|---|
| ecmwf_aifs025_single | -11% | 0.54 | 4.96 | 105 | 0.28 | 0.47 |  |
| ecmwf_ifs025 | -25% | 0.58 | 5.14 | 105 | 0.20 | 0.51 |  |
| gfs_seamless | -28% | 0.50 | 5.54 | 105 | 0.07 | 0.67 |  |
| equal_mean | -21% | 0.64 | 4.78 | 105 | 0.18 | 0.46 | no |
| inverse_mae_weighted_loso | -21% | 0.64 | 4.77 | 105 | 0.19 | 0.43 | no |
| max_of_models | +9% | 0.55 | 5.41 | 105 | 0.35 | 0.55 | no |

Weights fitted on every season: ecmwf_aifs025_single 0.35, ecmwf_ifs025 0.34, gfs_seamless 0.31. Verdict: no blend passes; the primary stays `ecmwf_aifs025_single`. The means lower the MAE and raise the correlation but miss more of the heavy days (the models disagree on their timing, so averaging smears them); the maximum catches more heavy days at a higher false-alarm ratio.

### The weather watch run over the archive

The watch's levels were fixed before any day was scored (`weather.py`). Here they are run day by day over the as-issued archive for every monsoon issue date the archive holds every model at leads 1 to 3, deterministic branch only (no ensemble is archived): the primary model's next-three-day total placed in the monsoon three-day totals of every year of the rain table (1961 to the latest day on disk, the scored seasons included) and the share of models with a 30 mm day. Truth, fixed in advance: at Bhakra the dated floodgate opening of 2025, at Pong and Ranjit Sagar the day of the largest dated inflow reading of 2025. A watch or alert day outside the window from 14 days before an event to 7 after it counts as a false alarm; 2024 and 2026 had no dam event, so every raised day there counts. 1,029 issue days scored.

| catchment | event | issue days before | first watch | lead (d) | first alert | lead (d) | days at watch or above | days at alert | highest percentile before |
|---|---|---|---|---|---|---|---|---|---|
| Bhakra | 2025-08-19 | 14 | 2025-08-09 | 10 | 2025-08-10 | 9 | 6 | 3 | 94 |
| Pong | 2025-08-26 | 14 | 2025-08-12 | 14 or more (raised before the window) | 2025-08-12 | 14 or more (raised before the window) | 10 | 5 | 98 |
| Ranjit Sagar | 2025-08-27 | 14 | 2025-08-13 | 14 or more (raised before the window) | 2025-08-13 | 14 or more (raised before the window) | 9 | 5 | 100 |

| catchment | season | issue days | watch share | alert share | days outside event windows | false alarms (watch or above) | false alerts |
|---|---|---|---|---|---|---|---|
| Bhakra | 2024 | 119 | 0.13 | 0.07 | 119 | 23 | 8 |
| Bhakra | 2025 | 119 | 0.24 | 0.09 | 97 | 29 | 6 |
| Bhakra | 2026 | 105 | 0.14 | 0.05 | 105 | 20 | 5 |
| Pong | 2024 | 119 | 0.10 | 0.06 | 119 | 19 | 7 |
| Pong | 2025 | 119 | 0.29 | 0.15 | 97 | 36 | 9 |
| Pong | 2026 | 105 | 0.09 | 0.04 | 105 | 13 | 4 |
| Ranjit Sagar | 2024 | 119 | 0.09 | 0.03 | 119 | 14 | 3 |
| Ranjit Sagar | 2025 | 119 | 0.19 | 0.12 | 97 | 22 | 6 |
| Ranjit Sagar | 2026 | 105 | 0.06 | 0.04 | 105 | 10 | 4 |

No level is changed on this result; a change would be a new plan with its own rule.

### The in-season observed rain: IMD real-time grid and ERA5 against the final grid

The runoff model is calibrated on the final IMD grid, which arrives after the season. In season the product has to carry the previous days' rain from something else: until now the best-match model's past days (ERA5 physics), and the record on disk was ERA5. IMD Pune serves a preliminary real-time analysis on the same lattice. Both are scored here against the final grid over the 2025 season on the dam catchments, on the days each has (heavy day: 30 mm or more). The rule, written before the pull: the real-time grid replaces the model's past days as the product's observed record only if its MAE is lower than ERA5's at every dam and its heavy-day hit rate is not lower at any.

| catchment | record | days | final mean (mm) | bias | r | MAE (mm) | heavy days | hit rate | false-alarm ratio |
|---|---|---|---|---|---|---|---|---|---|
| Bhakra | imd_rt | 121 | 5.5 | +9% | 0.98 | 0.6 | 0 | n/a | n/a |
| Bhakra | era5 | 122 | 5.5 | -22% | 0.72 | 2.7 | 0 | n/a | 1.00 |
| Pong | imd_rt | 121 | 12.1 | +6% | 1.00 | 0.9 | 14 | 0.93 | 0.07 |
| Pong | era5 | 122 | 12.1 | -27% | 0.60 | 7.1 | 14 | 0.29 | 0.50 |
| Ranjit Sagar | imd_rt | 121 | 10.2 | +11% | 0.99 | 1.5 | 11 | 1.00 | 0.21 |
| Ranjit Sagar | era5 | 122 | 10.1 | -12% | 0.76 | 5.7 | 11 | 0.36 | 0.43 |

MAE lower at every dam: yes; hit rate not lower at any: yes. Verdict: the product's observed record switches to the IMD real-time grid, the model's past days standing in for any day the service does not have. The product's observed record is `imd_rt`.

## Live 2026: one-day inflow prediction against the BBMB bulletins

Persistence (tomorrow's inflow equals today's) is the baseline any one-day prediction has to beat; the model's base component is that persistence with the rain response added, so the difference between the two rows is what the rain brings.

| dam | days | mean observed (cusecs) | mean predicted (cusecs) | bias | Pearson r | MAE (cusecs) | persistence bias | persistence r | persistence MAE |
|---|---|---|---|---|---|---|---|---|---|
| Bhakra | 30 | 41,926 | 41,437 | -1% | +0.58 | 4,040 | +0% | +0.56 | 4,148 |
| Pong | 30 | 35,571 | 35,608 | +0% | +0.86 | 5,904 | +3% | +0.37 | 12,135 |

### The response fitted on measured inflow, 2026 bulletins

The runoff response in force is fitted on day-to-day storage change, which is inflow minus a release the record does not show. The bulletin capture that began in August 2026 is the first daily inflow record this project has had, so the same response (coefficient, wetness term, lag weights, a constant base) is fitted on the daily mean of the bulletins' inflow and the storage-change fit is scored against that inflow out of sample (its base is the intercept plus the non-spill passage, as in every verification run, and again with the base fitted on these days so the response is judged on its own). One deficit season, in-sample for the inflow fit: the product keeps the storage-change parameters, and the live product takes its base from the bulletin, not from the intercept; the ratio of the two coefficients is the measure of what the storage record cannot see.

| dam | bulletin days | fit | c (dry) | c_wet | lag weights | base (cusecs) | R2 | bias against measured inflow | r | MAE (cusecs) | c ratio, inflow fit over storage fit |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Bhakra | 37 | storage change, 2015 to 2025 | 0.145 | 0.282 | 0.54, 0.28, 0.08, 0.09 | 34,430 | 0.221 | +18% | 0.62 | 8,119 | 1.55 |
| Bhakra | 35 | storage change, base fitted on 2026 | 0.145 | 0.282 | 0.54, 0.28, 0.08, 0.09 | 27,165 | | -0% | 0.62 | 5,115 | |
| Bhakra | 35 | measured inflow, 2026 (in sample) | 0.224 | 0.000 | 0.35, 0.23, 0.24, 0.18 | 27,525 | 0.474 | -0% | 0.69 | 4,643 | |
| Pong | 37 | storage change, 2015 to 2025 | 0.203 | 0.328 | 0.35, 0.48, 0.09, 0.08 | 40,229 | 0.777 | +95% | 0.87 | 32,658 | 1.21 |
| Pong | 35 | storage change, base fitted on 2026 | 0.203 | 0.328 | 0.35, 0.48, 0.09, 0.08 | 7,572 | | +0% | 0.87 | 6,773 | |
| Pong | 35 | measured inflow, 2026 (in sample) | 0.246 | 0.160 | 0.27, 0.54, 0.19, 0.00 | 11,768 | 0.807 | -0% | 0.90 | 5,496 | |

### By horizon, with observed and with forecast rain

From each bulletin day, the inflow one to five days ahead: predicted with the observed catchment rain of the days in between (what the hydrology alone can do), with the rain forecast issued that day (what the product does, per model), and by persistence (the inflow stays at the day's value). Scored on the days a bulletin exists for the target day.

| dam | horizon (days) | rain | days | bias | Pearson r | MAE (cusecs) |
|---|---|---|---|---|---|---|
| Bhakra | 1 | observed rain | 30 | -1% | +0.58 | 4,040 |
| Bhakra | 1 | persistence | 31 | +0% | +0.61 | 4,082 |
| Bhakra | 1 | ecmwf_ifs025 | 31 | -8% | +0.51 | 4,533 |
| Bhakra | 1 | gfs_seamless | 31 | -7% | +0.51 | 4,810 |
| Bhakra | 1 | ecmwf_aifs025_single | 31 | -6% | +0.48 | 4,554 |
| Bhakra | 2 | observed rain | 30 | -2% | +0.46 | 5,444 |
| Bhakra | 2 | persistence | 31 | -0% | +0.45 | 5,594 |
| Bhakra | 2 | ecmwf_ifs025 | 30 | -12% | +0.33 | 6,176 |
| Bhakra | 2 | gfs_seamless | 30 | -11% | +0.31 | 6,653 |
| Bhakra | 2 | ecmwf_aifs025_single | 30 | -8% | +0.28 | 5,849 |
| Bhakra | 3 | observed rain | 28 | -3% | +0.36 | 6,135 |
| Bhakra | 3 | persistence | 29 | +0% | +0.31 | 6,582 |
| Bhakra | 3 | ecmwf_ifs025 | 29 | -12% | +0.39 | 6,250 |
| Bhakra | 3 | gfs_seamless | 29 | -12% | +0.31 | 7,765 |
| Bhakra | 3 | ecmwf_aifs025_single | 29 | -9% | +0.22 | 6,941 |
| Bhakra | 4 | observed rain | 27 | -5% | +0.33 | 5,851 |
| Bhakra | 4 | persistence | 28 | -0% | +0.21 | 7,471 |
| Bhakra | 4 | ecmwf_ifs025 | 27 | -14% | +0.12 | 7,654 |
| Bhakra | 4 | gfs_seamless | 27 | -12% | +0.20 | 8,087 |
| Bhakra | 4 | ecmwf_aifs025_single | 27 | -12% | -0.08 | 7,926 |
| Bhakra | 5 | observed rain | 26 | -6% | +0.38 | 5,677 |
| Bhakra | 5 | persistence | 26 | +1% | -0.05 | 7,691 |
| Bhakra | 5 | ecmwf_ifs025 | 26 | -14% | +0.22 | 7,596 |
| Bhakra | 5 | gfs_seamless | 26 | -12% | +0.31 | 7,874 |
| Bhakra | 5 | ecmwf_aifs025_single | 26 | -12% | -0.08 | 8,090 |
| Pong | 1 | observed rain | 30 | +0% | +0.86 | 5,904 |
| Pong | 1 | persistence | 31 | +3% | +0.42 | 11,842 |
| Pong | 1 | ecmwf_ifs025 | 31 | -12% | +0.81 | 7,602 |
| Pong | 1 | gfs_seamless | 31 | -12% | +0.78 | 8,063 |
| Pong | 1 | ecmwf_aifs025_single | 31 | -9% | +0.79 | 7,245 |
| Pong | 2 | observed rain | 30 | -0% | +0.82 | 7,594 |
| Pong | 2 | persistence | 31 | +5% | -0.05 | 16,265 |
| Pong | 2 | ecmwf_ifs025 | 30 | -29% | +0.38 | 13,811 |
| Pong | 2 | gfs_seamless | 30 | -32% | +0.37 | 14,680 |
| Pong | 2 | ecmwf_aifs025_single | 30 | -27% | +0.33 | 13,026 |
| Pong | 3 | observed rain | 28 | -0% | +0.79 | 8,770 |
| Pong | 3 | persistence | 29 | +5% | +0.10 | 15,922 |
| Pong | 3 | ecmwf_ifs025 | 29 | -26% | +0.47 | 13,576 |
| Pong | 3 | gfs_seamless | 29 | -32% | +0.40 | 14,510 |
| Pong | 3 | ecmwf_aifs025_single | 29 | -32% | +0.37 | 13,289 |
| Pong | 4 | observed rain | 27 | -0% | +0.77 | 8,438 |
| Pong | 4 | persistence | 28 | +7% | +0.36 | 13,975 |
| Pong | 4 | ecmwf_ifs025 | 27 | -32% | +0.37 | 13,994 |
| Pong | 4 | gfs_seamless | 27 | -30% | +0.40 | 14,960 |
| Pong | 4 | ecmwf_aifs025_single | 27 | -36% | +0.13 | 14,937 |
| Pong | 5 | observed rain | 26 | -1% | +0.80 | 7,828 |
| Pong | 5 | persistence | 26 | +9% | +0.03 | 16,071 |
| Pong | 5 | ecmwf_ifs025 | 26 | -32% | +0.38 | 14,045 |
| Pong | 5 | gfs_seamless | 26 | -26% | +0.51 | 13,907 |
| Pong | 5 | ecmwf_aifs025_single | 26 | -37% | +0.24 | 14,946 |

## Prospective record, 2026 season

Issued daily from the committed inputs and the live BBMB bulletin; a record is never rewritten (`outputs/forecast/`; `latest.json` there is the one file rewritten every run, a copy of the newest product naming its dated record). P(spillway forced) is at the five-day horizon.

15 issue dates from 2026-09-05 to 2026-09-19. Bhakra: P(spillway forced) above zero on 0 of 15 days. Pong: P(spillway forced) above zero on 0 of 15 days. Days with any control point at or above the WRD low band: 0.

No day so far has put a forced spill or a classed arrival on the record.
