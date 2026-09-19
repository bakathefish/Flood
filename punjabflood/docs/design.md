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
The final IMD grid arrives after the season, so the current season needs another observed
record. Two are kept: IMD Pune's real-time analysis, a preliminary daily grid on the same
lattice served keyless for recent days (source `imd_rt`), and ERA5 through Open-Meteo
(source `era5`); the rain table holds one row per catchment and day with the best source
present, final over real-time over ERA5. Live, the product carries the previous six days'
rain per catchment from the IMD real-time grid where the service has the day and from the
best-match model's past day otherwise, and records the source of every day; the rule that
put the real-time grid in front of the model's past days is in the verification section
below (item 4) and the switch is `forecast.OBSERVED_RECORD`.

**The flood cushion.** BBMB lets Pong rise above its reduced FRL in a flood (1398 ft in
August 2023, 1394.7 ft in September 2025), and the CWC record's live-storage column is
capped at the FRL figure, so a rating fitted on that record is flat above 1390 ft. The
emergency action plan publishes the design pair, 1400 ft with 7,290 MCM live, which fixes
the storage above FRL: the rating keeps its fitted curve below FRL and runs on a straight
line from the fitted value at FRL to that point (`reservoirs.Rating.with_cushion`). Every
consumer of a level above FRL, the state record, the bulletin state and the reconciliation
of the feed's capped rows, rates on the line. The headroom-exhaustion functions take the
capacity as a parameter, so the product prints two scenarios for Pong: the FRL bound (the
spillway opens at 1390 ft; the routed arrivals use this, the early upper bound) and the
cushion scenario (the spillway opens at 1400 ft), and the event-timing test runs both. No
figure above FRL is published for Bhakra or Ranjit Sagar, so they have the FRL bound only.

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
days the cap would bind. A threshold-excess response (rain above the heavy-day threshold
with its own coefficient and lag weights) was fitted on the same record and scored
leave-one-season-out beside this one; it did not lower the held-out error and is not used
(`verification.md`; the rule is in `roadmap.md`). Since August 2026 the bulletin capture
gives a daily inflow series, and the same response is fitted on it beside the storage-change
fit (`inflow.calibrate_on_inflow`; the base is then a fitted constant rather than the
intercept plus passage), with the storage-change fit scored against the measured inflow
out of sample; the ratio of the two coefficients measures what the storage record cannot
see. One deficit season and in-sample, so the product keeps the storage-change parameters
(the section in `verification.md`). The rain index is a proxy for the
ground's wetness; the direct quantity, ERA5-Land soil moisture (0 to 7 cm, daily catchment
mean over the same IMD-covered points, 2015 onward from the keyless Open-Meteo archive), is
carried as a fractional anomaly against a 31-day day-of-year climatology and multiplies the
coefficient by `1 + gamma * anomaly`, gamma fitted in a second stage on the residual of the
rain fit. Three wetness carriers are fitted and scored out of sample beside each other
(`api`, the index alone; `api+sm`, both; `sm`, the anomaly alone, each fold's climatology
leaving the held-out season out) under the rule the threshold-excess test used; neither
passed (the held-out error did not fall, the season peaks fell, and Pong's fitted
sensitivity came out negative), so the product's carrier is the rain index and the report
records the refusal with the numbers. Should a carrier
ever pass (on a day-wise inflow record, say), the daily product already takes the anomaly
from the latest ERA5-Land day on record, up to about six days before the issue date,
labelled with its date, and holds it over the horizon. Bhakra's base is snowmelt, and
the record shows no wetness dependence there, so the one term the storage record could
still carry at Bhakra is the melt itself: a degree-day snowpack (`snow.py`) run at every
one of the catchment's 131 archive points, the IMD-uncovered half included, on ERA5's daily
snowfall (cm of snow at 10 mm of water per 7 cm, the constant of the watch) and 2 m mean
temperature, with the pack draining at 4 mm per degree-day above 0 C (the middle of the
Himalayan range in Hock 2003, *J. Hydrol.* 282, 104; the factor sets how fast a pack
drains, the fitted coefficient absorbs the scale) and never below empty, carried from an
empty pack on 1 January 2014 (a spin-up year before the first fitted season) through
every day to the rain table's last day. At the points above the snowline the pack never
empties and grows across the years (the bucket has no glacier flow), so the pack there is
not a physical depth; the melt, the only quantity the fit sees, is bounded at such points
by the degree-days alone. The catchment melt is the
area-weighted mean over all the points, its volume over the whole catchment area of the
catchment file, and it enters the storage-change relation as its own lagged block
(`c_melt`, `w_melt`, lags 0 to 3) fitted jointly with the rain response by the same
non-negative least squares, the intercept still free so the term wins only what a
season-varying melt explains beyond a constant base. It is a variant, scored
leave-one-season-out beside the baseline at Bhakra alone under a rule written before the
fit (`docs/superpowers/plans/2026-09-19-snowmelt-and-watch-hindcast.md`): the held-out
error may not rise, Bhakra's season-peak ratio in the flood-scale check must rise, and its
period means may not move further from the reported means than the baseline's worst one.
The outcome and the numbers are in `verification.md` (the snowmelt section). The rule
passed, and the term is in the parameters the product runs
(`calibrate --melt`, the second plan
`docs/superpowers/plans/2026-09-19-snowmelt-in-the-product.md`): Bhakra's parameter
set carries `c_melt` and `w_melt`, the other dams' do not. In the daily product the
recent melt comes from the archive at the same 131 points (the fixed spans plus a tail
to the archive's latest day, two days behind the issue date; when the tail cannot be
pulled, the fixed spans stand) and the primary model's past days and forecast days at
the same points carry the bucket across the gap and over the horizon, one pack across
the join. The recent melt over the same days as the recent rain enters the base
removal, so the observed inflow is split between base, rain response and melt
response; the horizon melt enters every deterministic model and every ensemble member.
The product records the days, the melt, the pack at the issue date, the archive's last
day and the source of every day; if the melt inputs cannot be built the cycle runs with
the term contributing nothing and says so. In every score that runs on the parameters
in use (the flood-scale check, the as-issued hindcast, the live one-day and horizon
tests) the melt over the horizon is the archive's melt, perfect prognosis for melt: the
previous-runs archive holds no temperature or snowfall, so a hindcast on forecast melt
is not possible from the record on disk. The size of that assumption is bounded in
`verification.md` by the term's horizon contribution (the melt response over five days
at the fitted coefficient beside the rain response). The adoption verdict compares the
snowmelt variant against a no-melt refit of the baseline, never against the parameters
in use, so it reads the same whether or not the file carries the term. The base component today is the observed BBMB inflow minus the
quick response the recent rain (and, at Bhakra, the recent melt) explains, decaying at a fitted daily recession. The recession is estimated from the residuals as the lag-2 to lag-1
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
uncertainty. The third samples the flood-scale volume error on top: one multiplicative
factor per path, lognormal with the spread that the flood-scale check measures (the sample
standard deviation of log model-over-reported across the Public Action Committee's period
means of at least 10 days, committed by `verify` in `data/reference/flood_scale_error.json`),
no bias, applied to the whole path because a volume error persists through an event. The
bias the same check measures is not applied: the product's numbers stay the model's, and
the report says how far below the reported volumes they sit. Six period means of one
season are a thin basis for a spread; a daily inflow record for an event (roadmap item 1)
would replace it.

**Release to control point.** Pure translation with the WRD's Annexure Z travel times, no
attenuation; the tributaries enter as the local term of the next paragraph; Harike sums the
Sutlej and Beas arrivals; Ferozepur is Harike plus twelve hours; Dhilwan is placed on the
Tanda to Harike reach by distance. Each river
loses its diversion first: Bhakra's outflow minus the Nangal canal off-takes (12,500 plus
10,150 cusecs), which do not return above Ropar; Pong's outflow minus the Mukerian Hydel
Channel's 11,500 cusecs taken at the Shah Nehar barrage (PSPCL). On a day the spillway is
forced, a full reservoir passes its inflow, so the river gets the spill plus the turbine
passage less that diversion; this is the lower bound on the river release and is what the
product and the event test route. Arrivals are classed Low, Medium, High with the WRD
section 3.2 limits, printed inconsistencies kept as printed.

**The land between the dams and the head works.** The Swan, the Sirsa and the Kandi
torrents join the Sutlej above Ropar; the Chakki and more Kandi torrents join the Beas above
Dhilwan; the plains drain to Harike. Three local catchments carry that water: the HydroBASINS
sub-basins draining to the sub-basin that holds Ropar and Phillaur, to the one that holds
Dhilwan, and to the one at the Harike barrage, each with the dam sets (and the local sets
built before it) removed, so the three are disjoint and together are the nineteen sub-basins
below Bhakra and Pong. All three lie inside the IMD grid. No gauge history exists for any of
them, so no coefficient can be fitted on them; the runoff is their own daily rain through a
dam's calibrated response (coefficient, wetness dependence and lag weights, `inflow.py`)
transferred to their area, Pong's response as the primary and Ranjit Sagar's (the lowest
fitted coefficient) as the sensitivity in the verification. No base flow is added, so the term
is a lower bound on what the tributaries contribute; it arrives at its control point on the day
it runs off, with no travel-time table for the tributaries and no attenuation, the same
assumption the dam reaches carry. The daily product computes it from the deterministic QPF
(ECMWF IFS where present) with the recent observed days feeding the lags and the antecedent
index, and adds it at Ropar, Phillaur, Dhilwan and Harike before classification; the event
test adds it from the IMD record and reports the Dhilwan peaks with and without it.

**Rain-fed pathway.** For the Ghaggar there is no public gauge history, so the product
publishes the catchment QPF above Bhankarpur and Khanauri, the recent rain, and the
percentile of the forecast three-day total against the 1988 to 2025 season record.

**Weather watch.** Before the index asks whether the spillway must open, the product
places the weather itself: for every catchment, the observed days (IMD real-time grid
where served), the next days from every deterministic model and the IFS ensemble, the
percentile of the next three days against the monsoon three-day totals of the 1961-2025
IMD record over the same catchment, and, for the dam catchments, the primary model's
2 m temperature and the share of its precipitation falling as snow (Open-Meteo's snowfall
at 10 mm of water per 7 cm of snow). The level is a fixed rule (`weather.py`): alert at the 90th
percentile of the ensemble median or half the members with a 30 mm day; watch at the
75th, a quarter of the members, or any model with a 30 mm day; quiet otherwise. It is a
reading aid over the same inputs, never an input to the inflow model.

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
   2023 and 31 August 2025: signed lag in days and magnitude ratio. The spill plus the
   turbine passage less the diversion is routed, with spill alone as the inner bound, so
   the magnitude is a lower bound either way. The public storage record is weekly in
   August 2023 and a few press points in August 2025, plus the two BBMB daily sheets of
   September 2025 that the Internet Archive kept; between measurements the reservoir is
   carried by the model's own water balance under the observed rain, re-anchored at every
   measurement, and run on for three weeks past the last one where a season's record stops
   early (Ranjit Sagar's does in 2025). The same section sets the model's one-day inflow under observed rain
   against every flood-scale inflow figure the public record holds (the archived BBMB
   sheets, dated press figures credited to the dam offices, the Public Action Committee's
   period means of BBMB inflow for August to early September 2025 at all three dams, the
   season peaks stated to the Rajya Sabha, the record inflow in the Pong emergency action
   plan), because that gap, not the routing, is what limits the event test: the
   coefficient is fitted on ordinary filling days, and on days when the dam releases
   heavily the storage change understates the inflow. The period means compare like with
   like; the stated peaks are readings at a moment against the model's daily volume, so
   those ratios are lower bounds.
3. Live season. The one-day inflow prediction against every 2026 BBMB bulletin: bias,
   correlation, mean absolute error, beside the same numbers for persistence (tomorrow
   equals today), which any one-day prediction has to beat; then the same one to five days
   ahead, with the observed rain of the days in between (the hydrology alone), with the
   rain forecast issued that day per model (what the product does), and by persistence,
   scored on the days a bulletin exists for the target day. Persistence is hard to beat a
   day ahead in a deficit season and easy to beat further out; the table says from which
   day the rain response earns its place at each dam. 2026 is a deficit season, so this leg
   supplies false-alarm and calibration evidence only.
4. Rain input check. ERA5 catchment rain against the IMD grid over the 2023 and 2025 event
   windows, because the forecast models share ERA5's physics and resolution; a reanalysis
   that misses the mountain rain of an event says the forecasts will too. The in-season
   half of the same question: the IMD real-time grid and ERA5 each against the final grid
   over the latest season that has all three, on the dam catchments (bias, r, MAE,
   heavy-day hit rate and false-alarm ratio, the QPF skill scores). The rule, written
   before the pull: the real-time grid replaces the model's past days as the product's
   observed record only if its MAE is lower than ERA5's at every dam and its heavy-day hit
   rate is not lower at any. The report prints both records and the verdict.
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
   model-carried storage of each dam and the rain forecast that was actually issued that day
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
   inflow over-predicted, or both, and the public record cannot separate them. For Pong in
   2025 both models flagged from mid-August and every flag was a hit against the
   perfect-prognosis run, with a few misses; the 2024 and 2026 seasons had no flags and no
   spill at either dam. For Bhakra in 2025 the run under observed rain flagged in the last
   days of August and never forced the spillway within the window: the measurement that
   followed re-anchored the carried path downward, and the reservoir the record then shows
   stayed below the ceiling, so the as-issued hits there were calls of a spill unless water
   was released, and the record says that water was released, the inflow over-predicted, or
   both. Where the model never spills, the re-anchor note runs from the first flag to the end
   of the window instead of to the spill. The Dhilwan peak is dated in the WRD table and the
   Ropar peak is not, so the observed-peak lead is Pong's alone. The prospective 2026 record
   continues this test forward with the live ensemble.

As-issued skill (forecast rather than observed rain) is measured on the 2024 to 2026
seasons, the period for which Open-Meteo archives the lead 1 to 7 forecasts of GFS and
ECMWF IFS 0.25, as bias, correlation, and hit rate and false-alarm ratio for catchment days
of 30 mm or more.

## Known limits and the data that lift them

The full list, ordered by expected effect, is `roadmap.md`.

- The forced release is a bound on the operator, not a prediction of it. For Bhakra the
  product prints a second scenario against the 2019 filling schedule (the level not to be
  exceeded on the date, through the rating, with a reservoir above the schedule owing its
  drawdown at once); the timing test in `docs/verification.md` shows that schedule fires
  in every season with a dated gate opening but not on the day, and the guideline the
  press quotes for 19 August 2025 (1,662 ft) is below the 2019 line. The current
  schedule would replace the constants; nothing exists for Pong beyond alert levels.
- Peak-day inflow is still underestimated. The flood-scale check (event section of
  `docs/verification.md`) puts the model's volumes over the 2025 flood periods close to the
  means BBMB reported and its largest days well below the stated season peaks: the lag
  weights, fitted on ordinary filling days, spread a flood over more days than the river
  does, and on days the dam releases heavily the storage change understates the inflow. A
  sharper heavy-day response fitted on the storage record was tested and refused for that
  reason: the record's heavy days carry the dam's releases. The daily CWC record from 1991
  (pull in progress) adds the large filling days of 1988 to 2014, and any day-wise inflow
  series for 2023 or 2025 would let the response be fitted on inflow itself.
- The storage record is sparse exactly in the event weeks; the model carry is a bridge, not
  a measurement. BBMB keeps no bulletin archive, so 2026 is the first season with daily
  measured state in this project.
- Soil moisture is a reanalysis (ERA5-Land), not a measurement, and its climatology is its
  own; the anomaly in the product is up to about six days old (the archive's lag) and is
  held constant over the horizon. The local catchments carry a transferred response with no
  anomaly of their own.
- The rain forecast sources are the ones Open-Meteo serves keyless: IFS, GFS, ICON, the
  best-match blend and, from March 2025 in the as-issued archive, ECMWF's machine-learned
  AIFS (single, no ensemble). AIFS is scored beside IFS on exactly the days both have; the
  product's primary deterministic model changes only under the rule in `verify.py`, and the
  spill probability keeps the IFS ensemble because AIFS has none there.
- Above full reservoir level only Pong is resolved: its rating runs on a straight line from
  the fitted value at 1390 ft to the emergency action plan's design pair (1400 ft, 7,290 MCM
  live), and the product prints a flood-cushion scenario beside the FRL bound. Bhakra's
  bulletin prints an MWL of 1690 ft and Ranjit Sagar none, with no storage figure above FRL
  for either, so their ratings clamp at FRL and their forced release is the FRL bound only.
- The local inflow term is not fitted on anything local: the intermediate catchments carry a
  dam's runoff response, and the plains and the Shivalik torrents need not respond like a
  Himalayan catchment. Daily gauge readings at Ropar, Dhilwan or Harike during a flood (the
  WRD publishes them in its situation reports) would let the local coefficient be fitted, and
  the routed dam release checked, on the river itself.

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
