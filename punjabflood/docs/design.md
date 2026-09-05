# Design: the hazard tier

## The mechanism the system encodes

Water moves in this order, and so does the code.

**Weather to catchment.** Numerical weather prediction gives a quantitative precipitation
forecast. The catchments above Bhakra (Sutlej), Pong (Beas) and Ranjit Sagar (Ravi) are
taken from HydroBASINS level 8 as the upstream set of the sub-basin containing the dam;
the 0.25 degree grid points inside each polygon are weighted by the geodesic area of their
cell inside it. Level 8 is coarse: the Bhakra set is 52,765 km2 against BBMB's 56,875 km2,
the Pong set 13,637 km2 against 12,560 km2, the Ranjit Sagar set 6,953 km2 against
6,086 km2. The observed rain record is the IMD gridded daily analysis (1961 to 2025); its
grid stops at the Indian border, so the Tibetan Sutlej above Bhakra (about half of that
catchment) is outside it and enters the model through the base flow. Coverage weights are
carried per grid point and the runoff coefficient is calibrated with the same weighted
polygons, so the area bias is absorbed into the coefficient rather than into the volume.
ERA5 through Open-Meteo covers the current season only, where the IMD archive has not yet
been published.

**Catchment to reservoir.** Inflow is a base component plus a quick response to the last
four days of catchment rain. The quick response is calibrated on what the public record
holds, the CWC storage series: during filling season the day-to-day storage change is
inflow minus a slowly varying outflow, so regressing it on lagged rain volumes (non-negative
least squares, days at or above 97 percent of capacity excluded) recovers the runoff
coefficient and the lag weights. Only measured storage enters the fit (the CWC table, or
the CWC level through the dam's own rating); storage read off the rating from a bulletin
level has flat-step artefacts in its daily differences. The base component today is the
observed BBMB inflow minus the quick response the recent rain explains, decaying at a
fitted daily recession. The recession is estimated from the residuals as the lag-2 to lag-1
autocovariance ratio, which is unbiased under white measurement noise; where the residual
drifts through the season instead of recessing the ratio exceeds one and the estimate sits
at its 0.99 clip, and the parameter file keeps the raw ratio so the report can say so.

**The record itself.** The CWC feed prints the level as read and the storage as a table
lookup, and occasionally fails to update the lookup (the previous row's storage repeated
against a new level) or slips a digit in the level (a 405 m reading in a 500 m record). The
rating is fitted with worst-first removal of pairs more than 0.3 BCM from the monotone
curve, and every row is then reconciled: a storage inconsistent with its level takes the
rating's value, a level outside 100 m below to 10 m above full reservoir level is blanked,
and a row with both faults is dropped. Without this step the record shows Pong 1.5 BCM
below full on the day in August 2023 when its level was 6 ft above the full reservoir
level, and the stale pair drags the top of the rating down by a quarter of a BCM.

**Reservoir to release.** The headroom-exhaustion index over horizon H is forecast inflow
volume minus headroom minus H days of turbine passage, divided by live capacity. The
day-by-day water balance gives the day of exhaustion and the forced release hydrograph:
above full reservoir level, whatever exceeds the turbines goes over the spillway. Turbine
capacities: Pong 45,600 cusecs (six penstocks at 7,600 cusecs, BBMB EAP), Bhakra about
35,000 cusecs (BBMB's total passage of 3.25 lakh cusecs minus the 8,212 cumec spillway and
outlet design), Ranjit Sagar about 20,000 cusecs (an estimate from 600 MW at 121.9 m head;
no published figure). This is a bound on the operator, not a prediction of the operator:
BBMB can release earlier and lower, and did in 2025; the verification scores both.

**Release to control point.** Pure translation with the WRD's Annexure Z travel times, no
attenuation, no tributaries; Harike sums the Sutlej and Beas arrivals; Ferozepur is Harike
plus twelve hours; Dhilwan is placed on the Tanda to Harike reach by distance. Bhakra's river
release is its outflow minus the Nangal canal off-takes (12,500 plus 10,150 cusecs), which do
not return above Ropar. Arrivals are classed Low, Medium, High with the WRD section 3.2
limits, printed inconsistencies kept as printed.

**Rain-fed pathway.** For the Ghaggar there is no public gauge history, so the product
publishes the catchment QPF above Bhankarpur and Khanauri, the recent rain, and the
percentile of the forecast three-day total against the 1988 to 2025 season record.

## Verification, tiered by the density of the record

1. Annual peak class, 38 years. The WRD table of annual maximum discharge at Harike,
   Ropar and Dhilwan carries the department's own High, Medium, Low class. Predictors from
   IMD rain (season rain volume, maximum 1 to 10-day volumes, all years) and from storage
   (fraction on 1 July, 1 August, 15 August; days above 95 percent; for the years the
   storage record covers) and the perfect-prognosis maximum of the index are each scored
   by Spearman rank correlation with the peak, area under the ROC curve for the High class,
   and a leave-one-year-out logistic Brier score against climatology. With five High years
   in 38 the AUROC has wide sampling error and the Brier skill is the more demanding number.
2. Event timing. The one-day-ahead forced release of each day's perfect-prognosis run,
   placed on the day it happens and routed, against the dated Dhilwan peaks of 17 August
   2023 and 31 August 2025: signed lag in days and magnitude ratio. Only the spill is
   routed, so the magnitude is a lower bound. The public storage record is weekly in
   August 2023 and a few press points in August 2025; between measurements the reservoir
   is carried by the model's own water balance under the observed rain and re-anchored at
   every measurement. The same section reports the model's one-day inflow on the wettest
   day against the largest inflow BBMB has recorded at Pong, because that gap, not the
   routing, is what limits the event test: on days when the dam releases heavily the
   storage change understates the inflow, and the largest daily changes are excluded from
   the fit as implausible, so the coefficient is an ordinary-day coefficient.
3. Live season. The one-day inflow prediction against every 2026 BBMB bulletin: bias,
   correlation, mean absolute error. 2026 is a deficit season, so this leg supplies
   false-alarm and calibration evidence only.

As-issued skill (forecast rather than observed rain) is measured on the 2024 to 2026
seasons, the period for which Open-Meteo archives the lead 1 to 7 forecasts of GFS and
ECMWF IFS 0.25, as bias, correlation, and hit rate and false-alarm ratio for catchment days
of 30 mm or more.

## Known limits and the data that lift them

- Extreme-event inflow is underestimated by the storage-change calibration (see the event
  section of `docs/verification.md`). The daily CWC record from 1991 (pull in progress) adds
  the large filling days of 1988 to 2014, and BBMB's 2023 and 2025 release chronologies
  would let the coefficient be fitted on inflow rather than on storage change.
- The storage record is sparse exactly in the event weeks; the model carry is a bridge, not
  a measurement. BBMB keeps no bulletin archive, so 2026 is the first season with daily
  measured state in this project.
- Soil-moisture modulation of the coefficient is implemented but inactive (gamma 0):
  the ERA5-Land soil-moisture pull was not made because the IMD archive replaced ERA5 as
  the observed rain record. It is one archive pull away.
- The ratings clamp at the highest level each dam has printed; above that the flood cushion
  above full reservoir level is not resolved, and headroom is simply zero.

## What was measured before this design was fixed

GloFAS, the global system, reads about a third of the BBMB-reported inflow at Bhakra and
Pong (27 days of 2026 bulletins, negative correlation), and underestimates the 2023 and
2025 Dhilwan peaks four to eight times while peaking six to ten days late. Its reservoir
module is rule-based on relative filling and cannot represent gate operations. It is not
used as a driver here.

## Boundaries

No satellite-derived labels. No district impact probabilities in this tier. No LSTM or
transformer. No blending of observed and forecast quantities into one number. Every
constant in `punjabflood/constants.py` carries its source and the digitised WRD tables carry
a page-by-page verification record.
