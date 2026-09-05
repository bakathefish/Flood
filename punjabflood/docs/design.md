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
level has flat-step artefacts in its daily differences. The coefficient depends on how wet
the catchment already is: `c + c_wet * API / 100 mm`, API the previous five days' catchment
rain, capped at 0.95. The record itself asked for this (the share of a rain volume that
showed up as storage change rose steadily with antecedent rain for Pong and Ranjit Sagar),
and it is fitted jointly with the lag weights by non-negative least squares, leaving out
days the cap would bind. The base component today is the observed BBMB inflow minus the
quick response the recent rain explains, decaying at a fitted daily recession. The recession is estimated from the residuals as the lag-2 to lag-1
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

**Two probabilities.** The product prints P(spillway forced) twice. The first is the share
of the 51 ECMWF ensemble members whose rain would fill the reservoir: the weather
uncertainty alone, with the inflow model taken as exact. The second samples the inflow
model's own error on top of every member: additive Gaussian error on each day's inflow
volume with the calibration RMSE as its standard deviation and the calibration residuals'
lag-1 autocorrelation as its day-to-day persistence (`hei.ensemble_summary_with_error`,
200 seeded paths per member, perturbed inflows floored at zero). The RMSE is measured on
the ordinary filling days the model was fitted on, so this is the model's ordinary-day
error; at flood scale the error is larger (the event section of the verification report
says by how much), and the second probability is therefore still an inner estimate of the
uncertainty, not an outer one.

**Release to control point.** Pure translation with the WRD's Annexure Z travel times, no
attenuation, no tributaries; Harike sums the Sutlej and Beas arrivals; Ferozepur is Harike
plus twelve hours; Dhilwan is placed on the Tanda to Harike reach by distance. Each river
loses its diversion first: Bhakra's outflow minus the Nangal canal off-takes (12,500 plus
10,150 cusecs), which do not return above Ropar; Pong's outflow minus the Mukerian Hydel
Channel's 11,500 cusecs taken at the Shah Nehar barrage (PSPCL). On a day the spillway is
forced, a full reservoir passes its inflow, so the river gets the spill plus the turbine
passage less that diversion; this is the lower bound on the river release and is what the
product and the event test route. Arrivals are classed Low, Medium, High with the WRD
section 3.2 limits, printed inconsistencies kept as printed.

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
   correlation, mean absolute error, beside the same numbers for persistence (tomorrow
   equals today), which any one-day prediction has to beat. 2026 is a deficit season, so
   this leg supplies false-alarm and calibration evidence only.
4. Rain input check. ERA5 catchment rain against the IMD grid over the 2023 and 2025 event
   windows, because the forecast models share ERA5's physics and resolution; a reanalysis
   that misses the mountain rain of an event says the forecasts will too.
5. QPF bias correction, out of sample. One multiplicative factor per catchment, model and
   lead (observed over forecast season rain), fitted on every season but one and applied to
   the held-out one, scored against the raw forecast on the held-out days. The rule for the
   product: a correction is applied only if it lowers the held-out MAE and raises the
   held-out heavy-day hit rate for the dam catchments. On the 2024 to 2026 archive it does
   neither: the mean bias goes by construction, the MAE rises on nearly every row, the
   heavy-day hit rate moves in a handful of rows and in both directions, and the false-alarm
   ratio rises in half of them, so the product applies no correction. The models' shortfall is
   on the heavy days themselves, not a uniform scale error, which is what the ERA5
   comparison says too. A correction conditional on the forecast amount, or quantile
   mapping, needs more seasons of archive than exist.
6. As-issued hindcast. For every issue date of the 2024 to 2026 seasons, the recorded or
   model-carried Pong storage and the rain forecast that was actually issued that day
   (archived lead 1 to 5 QPF, ECMWF and GFS, deterministic) go through the same water
   balance as the live product: what the product would have said, day by day, before the
   2025 event and through the two seasons without one. Scored as flagged issue dates (a
   forecast that forces the spillway within five days), the first of them, and the lead from
   it to the model's own first spill under observed rain and to the dated Dhilwan peak.
   BBMB's gate log is not public, so the perfect-prognosis run stands in for the spill date.
   The model carry records its re-anchor gaps (the carried storage on a measurement day
   minus the measurement), and the report prints the largest one between the first
   perfect-prognosis flag and the spill, because that gap is why the model's own flags can
   run ahead of its spill: a positive gap is the dam passing more than its turbines, the
   inflow over-predicted, or both, and the public record cannot separate them. In 2025 both
   models flagged from mid-August and every flag was a hit against the perfect-prognosis
   run, with a few misses; the 2024 and 2026 seasons had no flags and no spill. The
   prospective 2026 record continues this test forward with the live ensemble.

As-issued skill (forecast rather than observed rain) is measured on the 2024 to 2026
seasons, the period for which Open-Meteo archives the lead 1 to 7 forecasts of GFS and
ECMWF IFS 0.25, as bias, correlation, and hit rate and false-alarm ratio for catchment days
of 30 mm or more.

## Known limits and the data that lift them

The full list, ordered by expected effect, is `roadmap.md`.

- Extreme-event inflow is still underestimated by the storage-change calibration even with
  the wetness term (see the event section of `docs/verification.md`): on days the dam
  releases heavily the storage change understates the inflow. The daily CWC record from
  1991 (pull in progress) adds the large filling days of 1988 to 2014, and any daily inflow
  series for 2023 or 2025 would let the coefficient be fitted on inflow itself.
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
