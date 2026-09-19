# Roadmap: what would make the prediction better, and what each step needs

Written 2026-09-05 after the first verification round. Items are ordered by expected effect
on the thing that matters, the flood-scale forecast, and each names the data it needs. The
numbers that motivate them are in `verification.md`, never repeated here.

## Done in the first round

- **Wetness-dependent runoff coefficient.** The storage record itself showed the response
  rising with antecedent rain for Pong and Ranjit Sagar (the fraction of a three-day rain
  volume that showed up as storage change roughly tripled from dry to saturated antecedents).
  The coefficient is now `c + c_wet * API / 100 mm`, API the previous five days' catchment
  rain, capped at 0.95, fitted jointly with the lag weights by non-negative least squares.
  It moved the 2023 event from missed to matched on the day, and lifted both event
  magnitudes; it cost a little on ordinary 2026 days. Bhakra shows no wetness dependence in
  the record (half its catchment is outside the IMD grid and its base is snowmelt).
- **Passage in the routed release.** On a spill day a full reservoir passes its inflow, so the
  turbines run; the river gets spill plus passage less the diversion capacity (Nangal canals
  for Bhakra, the Mukerian Hydel Channel for Pong, both sourced). The product and the event
  test now route that, with the spill-only figure kept as the inner bound.
- **Persistence baseline** in the live test, so the rain response is judged against the
  naive forecast it has to beat, and the live test carried out to five days ahead with
  observed rain, with each model's as-issued rain and by persistence, so the report says from
  which day the rain response beats persistence at each dam.
- **Record repair** (stale CWC rows, level slips) and **model-carried storage** between the
  sparse event-week measurements, both described in `design.md`.
- **Model error inside the spill probability.** P(spillway forced) is now printed twice: from
  the 51-member QPF spread with the inflow model taken as exact, and with the model's own
  error sampled on top (additive on each day's inflow volume, the calibration RMSE as its
  spread and the residual lag-1 autocorrelation as its persistence, 200 seeded paths per
  member). The calibration RMSE is an ordinary-day error, so the second probability is still
  an inner estimate; it is labelled as such.
- **Scale bias correction of the QPF, tested and not adopted.** One factor per catchment,
  model and lead, fitted leave-one-season-out on the 2024 to 2026 archive. On the held-out
  seasons it removes the mean bias and little else: the MAE rises on nearly every
  dam-catchment row, the heavy-day hit rate moves in a handful of rows and in both
  directions, the false-alarm ratio worsens in half of them (`verification.md`). The under-forecast is concentrated on the heavy days, so scaling
  every day up mostly inflates the ordinary ones. The product applies no correction, and the
  rule that would let one in is written down in `design.md`.
- **Flood-scale inflow truth, what the record holds.** A hunt for daily inflow at the event
  scale found no day-wise series: BBMB keeps no archive, and the Internet Archive holds two
  of its daily sheets from September 2025 and none from August 2023 or August 2025. What
  the record does hold is now in the reference tables and set against the model in
  `verification.md`: the Public Action Committee's period means of BBMB inflow and outflow
  for 1 to 24 August and 25 August to 4 September 2025 at all three dams (as reported by
  The Wire), the season's largest inflows at Pong and Bhakra as stated to the Rajya Sabha,
  two dated press figures credited to the dam offices, and the two archived sheets, which
  also join the storage record as measured state.
- **As-issued hindcast of the 2025 event.** The archived lead 1 to 5 forecasts of ECMWF and
  GFS, issue date by issue date, through the product's water balance with the recorded or
  carried storage of each of the three dams: the first flagged issue date, how many days were flagged, and the
  lead to the model's own first spill under observed rain and to the dated Dhilwan peak, for
  2024 (no event), 2025 (the event) and 2026 to date. At Bhakra the model flagged in the last
  days of August 2025 and never spilled within the window; the early-September measurement
  re-anchored its carried path downward, the same reading as Pong's mid-August gap (the dam
  releasing more than its turbines, the inflow over-predicted, or both). The numbers are in
  `verification.md`.
- **Prospective record summary** at the end of the verification report, one row per issue
  date, growing daily from the Action.
- **Threshold-excess response, tested and not adopted.** Rain above the heavy-day threshold
  was given its own coefficient and lag weights, fitted jointly on the same storage record and
  scored leave-one-season-out beside the response in use, with the adoption rule written
  before the fit (`verification.md`). In every fit the excess runs off with a far larger
  coefficient than the ordinary rain, which is the physics one expects, but out of sample it
  buys nothing: the held-out error rises at Bhakra, whose record holds two heavy days, and
  does not fall at Pong or Ranjit Sagar; the season peaks of the flood-scale check do not
  rise, because the fit hands the excess mostly to the day after; and the heavy-day
  residuals say the storage change on those days is already over-predicted, which is the dam
  releasing while it rains. The
  storage-change target cannot carry a sharper heavy-day response; a day-wise inflow record
  could (item 1).

- **Local inflow between the dams and the head works.** The Swan, Sirsa and Kandi torrents
  above Ropar, the Chakki and Kandi torrents above Dhilwan, and the plains draining to Harike
  are now three HydroBASINS local catchments (the sub-basins draining to the ones holding
  Ropar and Phillaur, Dhilwan, and the Harike barrage, with the dam sets removed), each
  carrying its own IMD rain through a dam's calibrated response transferred to its area,
  Pong's as the primary and Ranjit Sagar's as the sensitivity, no base flow, same-day
  arrival. The daily product adds the term at Ropar, Phillaur, Dhilwan and Harike before
  classification; the event test reports the Dhilwan peaks with and without it. What it
  showed (`verification.md`): the local term is a small share of the observed peak day in
  both event years, larger in 2025 than in 2023, and it raises the routed magnitude ratio
  by a few hundredths in 2023 and by about a tenth in 2025 while the timing is unchanged;
  the gap that remains at the peaks is the dams' own peak-day response (item 2), not the
  tributaries. The coefficient is fitted on nothing local (`design.md`, known limits); daily
  gauge readings at the control points during a flood would let it be fitted on the river.

- **The machine-learned rain forecast as a source.** ECMWF's AIFS (the single, deterministic
  run; Open-Meteo serves no AIFS ensemble) joins IFS and GFS everywhere a rain forecast is
  read: the daily product, the as-issued hindcast, the live test by horizon and the QPF skill
  tables. Its as-issued archive begins in March 2025, so it is scored against IFS on exactly
  the dam-catchment rows both have at the product's short leads, under a rule written before
  the pull: it becomes the product's primary deterministic model only if its heavy-day hit
  rate is higher and its false-alarm ratio is not higher on those rows. It passed both, with
  a lower mean error and next to no mean bias where IFS under-forecasts (`verification.md`),
  so the primary deterministic model, which drives the local term and the deterministic
  fallback, is now AIFS; the spill probability keeps the IFS ensemble. In the 2025 hindcast
  its first flag at Pong came two days after IFS's; on the live 2026 days it beats
  persistence at Pong at every lead. Item 4 below stays open for what it asked for, a
  correction conditional on the forecast amount, which needs more archive than exists.

- **Soil moisture as the wetness carrier, tested and not adopted.** ERA5-Land soil
  moisture (0 to 7 cm, daily catchment means over the same IMD-covered points, 2015 to 2025)
  was pulled for the three dam catchments and carried as a fractional anomaly against a
  31-day day-of-year climatology, multiplying the coefficient through a sensitivity fitted
  on the residual of the rain fit. Two carriers were scored leave-one-season-out beside the
  rain index in use, each fold's climatology leaving the held-out season out, under the rule
  the threshold-excess test was held to: soil moisture beside the index, and soil moisture in
  its place. Neither passes (`verification.md`): the held-out error is unchanged to the
  third decimal at every dam, the season peaks of the flood-scale check fall rather than
  rise, and at Pong the fitted sensitivity is negative, wetter soil giving less storage
  change, which is the anomaly reading the dam's releases on the wet days, the same thing
  that stopped the threshold-excess term. The five-day rain index stays the carrier; the
  code path, the pull and the climatology remain, so a day-wise inflow record (item 1)
  can re-run the test on inflow rather than storage change.
- **The in-season observed rain from IMD's own real-time grid.** The runoff model is
  calibrated on the final IMD grid, which arrives after the season; in season the product
  carried the previous six days from the best-match model's past days and the record on
  disk was ERA5, both of which saw well under half of the IMD rain over the 2023 event.
  IMD Pune serves a preliminary daily analysis on the same lattice, keyless, for recent days
  (the endpoint `imdlib` uses). It was pulled for the 2025 and 2026 seasons and scored
  beside ERA5 against the final 2025 grid on the dam catchments under a rule written first
  (MAE lower than ERA5's at every dam, heavy-day hit rate not lower at any). It passed by a
  wide margin (`verification.md`, the in-season observed rain section), so the product's
  observed record is the real-time grid where the service has the day, with the model's
  past days standing in otherwise and every day's source recorded on the product; the
  current-season rows of the rain table are the real-time grid too, ERA5 for the days it
  lacks, and the final grid replaces both when the year arrives. The switch is
  `forecast.OBSERVED_RECORD`. This settles the in-season half of item 4; the forecast
  half (the models' heavy-day totals) stays open below.
- **The flood cushion above FRL at Pong.** The CWC record's live-storage column is capped at
  the FRL figure, so the fitted rating was flat above 1390 ft and every reading of the 2023
  and 2025 floods (1398 ft, 1394.7 ft) rated as "full": zero storage change on the flood
  days, and a forced release that fires the moment the reservoir touches FRL. The Pong
  emergency action plan publishes the design pair, 1400 ft with 7,290 MCM live, and the
  rating now runs on a straight line from its fitted value at FRL to that point
  (`reservoirs.Rating.with_cushion`), which every consumer of a level above FRL uses. The
  headroom functions take the capacity as a parameter; the product prints a cushion scenario
  beside the FRL bound (spill probability and peak release by horizon with the spillway
  opening at 1400 ft), and the event-timing test runs both settings, which bracket what BBMB
  did in each event. Outcome (`verification.md`, event timing): the FRL bound keeps the
  timing it had, and the cushion bound fires late in 2025 and not at all in 2023, so BBMB
  opened the spillway before the cushion was used up in both floods; the FRL bound stays
  the product's routed scenario and the cushion scenario is printed as the other end of
  the bracket. The storage-change calibration was rerun on the corrected record and the
  fitted parameters did not move to the third decimal (the fit uses filling days below
  FRL). Bhakra and Ranjit Sagar have no published figure above FRL; that remains item 7.
- **Flood-scale error in the spill probability.** The product prints a third spill
  probability: the ensemble spread, the inflow model's ordinary-day error, and on top a
  multiplicative volume error per path drawn from the spread the flood-scale check measures
  (the sample standard deviation of log model-over-reported across the Public Action
  Committee's 2025 period means of at least 10 days, written by `verify` to
  `data/reference/flood_scale_error.json` so the daily runner has it). The bias is reported,
  not applied. The prospective record carries the third column.

- **The operator's schedule at Bhakra (roadmap item 3, first form).** The forced release
  is the spillway's bound; BBMB opens the gates under a filling schedule. The 2026-09-18
  sweep found the Bhakra schedule as three dated points (2019 chart on page 44 of the CBIP
  decision-support presentation, and the thesis statement that FRL is not to be reached
  before 31 August): 1,650 ft up to 31 July, 1,670 ft up to 15 August, 1,680 ft by
  31 August. `constants.rule_curve_level_ft` gives the maximum permissible level on a date
  (a level holds up to its date, a straight line from 15 to 31 August), the dam's rating
  turns it into a per-day storage ceiling, and `hei.headroom_exhaustion` takes a per-day
  ceiling with the start unclamped, so a reservoir already above the schedule owes its
  drawdown on day one. The product prints a second Bhakra line: P(release forced) against
  the schedule by horizon, with the day-one headroom to it. The timing test in the report
  (`rule_curve_timing.csv`) sets the first forced day of each season under each bound
  against the three dated gate openings the sweep found (10 August 2015 at 1,661.1 ft,
  13 August 2023 at 1,672 ft, 19 August 2025 at 1,665.06 ft): the FRL bound fires in none
  of those seasons, the 2019 schedule fires in all three but not on the day, and the 2025
  guideline of 1,662 ft says the schedule has been lowered since. The scenario is labelled
  with its vintage.
- **The routed release on the days the press quoted the gauges.** The sweep found 27 dated
  press readings of the Dhilwan, Harike and Ferozepur (Hussainiwala) gauges in 2023 and
  2025 (`data/reference/wrd/gauge_readings_press.csv`); no station has a run of consecutive
  days, so no attenuation fit, but `verify.routed_vs_gauge_readings` sets the routed Pong
  release on each dated day against the reading as a ratio (report section). The ratios
  are below one and fall to zero on the days after the spill stops, which is the local
  catchment and the Sutlej arm the routed Pong release does not carry.
- **The press readings database.** Four sweeps of the press and the CWC bulletins
  (The Tribune, the English press, the Hindi and Punjabi press, the CWC weekly storage bulletins
  2015 to 2026) under `data/raw/bbmb/readings_*.csv`, merged by `scripts/ingest_readings.py`
  into `data/reference/bbmb/press_readings.csv` (829 dated rows, 200 with inflow, 761 with
  level). Every dated inflow reading before the current season now enters the flood-scale
  check (147 dated days), and the press-inflow response variant is fitted on them and
  scored on the storage record, where its held-out error is higher than the baseline's
  and it is not adopted (report, response variants).

## Tested and refused in the 2026-09-19 sprint

- **Combining the deterministic rain models.** The equal-weight mean, an inverse-MAE
  weighted mean (weights fitted leave-one-season-out) and the maximum of AIFS, IFS and GFS
  were scored against AIFS on the common rows over the dam catchments at leads 1 to 3
  (`verify.qpf_blend_test`). The means lower the MAE and raise the correlation but catch
  fewer of the heavy days; the maximum catches more at a higher false-alarm ratio. None
  passes the switching rule; AIFS stays. The numbers are in `verification.md`.

## Measured in the 2026-09-19 sprint

- **The weather watch run over the as-issued archive.** The watch's levels were fixed
  before any day was scored, and the score was written before the run (the plan file
  `docs/superpowers/plans/2026-09-19-snowmelt-and-watch-hindcast.md`): the deterministic
  branch of `weather.level` on every monsoon issue date of 2024 to 2026 the archive holds
  all its models at leads 1 to 3, the truth the dated 2025 gate opening at Bhakra and the
  largest dated inflow reading of 2025 at Pong and Ranjit Sagar, false alarms counted
  outside a window of 14 days before to 7 after an event. What it showed
  (`verification.md`, the weather watch section, 1,029 issue days): before the Bhakra
  opening of 19 August 2025 the first watch was issued on 9 August and the first alert on
  10 August, the level stood at alert on 10, 11 and 13 August and at watch on the 12th,
  the watch was quiet from 16 to 20 August (the 14th quiet, the 15th a watch), and alerts
  returned on 22 and 23 August; at Pong and Ranjit Sagar the window opened already at alert
  (at alert from 11 August, watch from the 10th), so their leads are bounded by the window at 14 days, not
  measured. In the two seasons without a dam event between a tenth and a fifth of the
  issue days stood at watch or above (23, 19 and 14 days of 119 in 2024; 20, 13 and 10 of
  105 in 2026 at Bhakra, Pong and Ranjit Sagar) and between 3 and 8 days a season at alert
  (8, 7, 3 in 2024 and 5, 4, 4 in 2026). No level is changed on this: the ensemble half of the rule cannot be
  scored (no ensemble is archived), and a change would be a new plan with its own rule.

- **The snowmelt term at Bhakra, fitted, adopted and in the product.** Under the rule written
  before the fit (the same plan file), a degree-day snowpack at all 131 archive points of
  the Bhakra catchment (ERA5 snowfall and 2 m temperature from a 2014 spin-up year) gave
  a melt term fitted jointly with the rain response: `c_melt` 0.067, lag weights
  0.00, 0.15, 0.00, 0.85. Leave-one-season-out over 11 seasons and 1,009 days the
  held-out error is 0.043809 BCM/day against the no-melt refit's 0.043905, the
  season-peak ratio 0.58 against 0.57 and the worst period-mean deviation 0.10 against
  0.11; all three conditions pass and the verdict is recorded in
  `outputs/verification/results.json` (`snowmelt_verdict`). The term is in the
  parameters the product runs (`calibrate --melt`, plan
  `docs/superpowers/plans/2026-09-19-snowmelt-in-the-product.md`): the daily product
  runs the same bucket from the archive through the primary model's past and forecast
  days at the same points, and every score that uses the file's parameters carries it
  with the archive's melt over the horizon (perfect prognosis for melt; the previous-runs
  archive holds no temperature). Over the 2025 monsoon (122 issue days) the melt
  response over five days is 0.025 BCM on average and 0.069 BCM at most, the rain
  response 0.180 and 0.749 BCM. What moved in the scores that run on the file's
  parameters: the as-issued 2025 Bhakra run's false flags went from 1 to 0 under the two
  ECMWF models and from 3 to 2 under GFS (hits unchanged at 3, 3 and 1; the earliest
  possible flag under observed rain moved from 29 to 30 August), the 2026 fit against
  measured inflow has bias +18% and MAE 8,119 cusecs (were +24% and 9,868), the live
  one-day test MAE 4,040 cusecs at r +0.58 (were 4,006 and +0.57), and the five-day
  horizon test under observed rain MAE 5,677 cusecs (was 5,792). The remaining step is
  data-bound: a hindcast on forecast melt needs archived temperature and snowfall
  forecasts, which the previous-runs archive does not hold.

## Next, in order

1. **Flood-scale inflow truth.** The one thing that would settle the runoff response at the
   extremes. BBMB publishes daily inflow and outflow in its bulletin and keeps no archive;
   the season-long capture that started in August 2026 is the first daily inflow record this
   project has. For 2023 and 2025 the public record holds scattered figures (a record inflow
   on 14 August 2023 in the Pong EAP; period averages for Ranjit Sagar in press coverage of
   the state's release data; season totals stated by BBMB). The Public Action Committee, a
   Ludhiana group, released a month of BBMB discharge data for the three dams on
   8 September 2025; the press carried its period means (1 to 24 August and 25 August to
   4 September, inflow and outflow, all three dams), which are kept in
   `data/reference/bbmb/pac_period_means_2025.csv` and checked against the model in
   `verification.md`; the day-wise table itself was not published. The Internet Archive holds
   two of BBMB's daily sheets from September 2025 (15 and 24 September) and none from
   August 2023 or August 2025. With any daily inflow series for an event, the coefficient can
   be fitted on inflow rather than on storage change, and the release-during-event bias
   disappears. The calibration mode exists (2026-09-18, `inflow.calibrate_on_inflow`) and
   runs on the 2026 bulletins in `verification.md`, one deficit season, in-sample; what it
   waits for is an event's daily inflow. Effort: data hunt.
   *Hunt of 2026-09-17:* a sweep of the English and Hindi press (The Tribune, Hindustan
   Times, Indian Express, Times of India, Babushahi, Diary Times, Rozana Spokesman, Himachal
   Tonite, SANDRP, Down To Earth, The Wire) for 10 to 25 August 2023 and 15 August to
   10 September 2025 found no day-wise table for either event and confirmed that BBMB's
   `res_data.pdf` has two Internet Archive captures in all. It did yield 24 more dated
   readings credited to BBMB or the dam offices (level, inflow, outflow at a stated time of
   day) on 5 days of the 2023 event and 11 days of the 2025 event, each re-read from its
   source page; they are in `data/reference/bbmb/inflow_points.csv` and the flood-scale
   check of `verification.md` now prints the model against each of them with a per-year
   summary. They are moment readings, not daily means, so they bound the model from below;
   the calibration mode on inflow still waits for a daily series, which only the 2026
   capture provides so far. The day-wise BBMB data the Public Action Committee released on
   8 September 2025 remains the one known table; asking the committee for it is an owner
   action.
   *Probe of 2026-09-19:* the two official daily-storage sources that could stand in for
   inflow were tried again from this machine (`scripts` scratch probe, statuses as
   returned): the data.gov.in CWC reservoir feed answered 429 (rate limit exceeded) to a
   three-row query on the sample key, and every form of the India-WRIS reservoir dataset
   endpoint, and its home page, timed out at the connection after 21 s. Neither is a
   day-wise inflow record in any case (both carry storage), so the item stays a data hunt
   for the committee's table or a BBMB archive.
2. **Peak-day concentration.** The flood-scale check says the model's volumes over the 2025
   flood periods are close to the means BBMB reported while its largest days fall well short
   of the stated season peaks, and in both 2023 and 2025 the routed Dhilwan peak fell below
   the Medium band the observed peak sat in (`verification.md`, event timing). The stated
   peaks are readings at a moment and the model's day is a daily volume, so part of the gap
   is that, not the model. The one sharper response the storage record could support, a
   threshold-excess term, was tested under a rule written in advance and refused (above): on
   heavy days the storage change carries the dam's releases, so it cannot teach the model
   what the river did. What would settle it is the day-wise inflow record of item 1, on
   which a heavy-day response could be fitted directly, and a sub-daily reading of the peaks
   to say how much of the gap is the daily mean. Effort: blocked on item 1.
3. **The operator, the current schedule.** The 2019 rule is built (above). The press quotes
   a guideline of 1,662 ft for 19 August 2025, below the 2019 line, and the timing test
   shows it: the 2019 rule reproduces none of the three dated gate openings to the day
   (the 2015 and 2025 openings came a week and thirteen days before it would have forced a
   release, the 2023 one nineteen days after). The current schedule as dated points, with
   the date the reservoir may reach FRL, is what would make the scenario a prediction of
   BBMB rather than a scenario; nothing is in hand for Pong beyond the EAP's alert levels
   (1,380 ft by 15 August, 1,390 by 20 August, 1,410 by 31 August), which are warnings,
   not a filling schedule. Effort: locate the current schedule (BBMB Technical Committee
   minutes or a right-to-information reply), then a constants change.
4. **Rain input for the extremes.** ERA5 saw well under half of the IMD catchment rain over
   Pong in the August 2023 event (`data/reference/rain/era5_vs_imd_event_windows.csv`,
   rendered in `verification.md`). The forecast models share ERA5's physics and resolution,
   so their heavy-day totals over these mountain catchments are low, and the as-issued skill
   table shows heavy-day hit rates of one in four or worse. A uniform scale factor does not
   fix this (tested above). What would: a correction conditional on the forecast amount, or
   quantile mapping, both of which need more than the three seasons of archive that exist;
   or a higher-resolution model (ICON-D2 does not cover India; the IMD's own NWP is not
   keyless). The observed-rain half of this item is done (above): in season the product
   now reads IMD's real-time grid rather than a model's past days. Effort for the forecast
   half: wait for archive, then small.
5. **Attenuation.** Pure translation is the department's own assumption and is right for
   timing; a linear reservoir per reach (one parameter each, fitted on nothing we have yet)
   would soften peaks. Only worth doing once daily gauge readings at the control points are
   available; the WRD publishes them during floods in its situation reports.
6. **Flood-scale error on a daily record.** Done on the record in hand (above): the third
   spill probability samples the spread of the model's log ratio to the six 2025 period
   means. Six means of one season are a thin basis; a daily inflow record for an event
   (item 1) would give the spread by day and let the bias be tested as a correction rather
   than only reported. Effort: small once item 1 lands.
7. **Flood cushion above FRL, Bhakra and Ranjit Sagar.** Pong's is done (above). Bhakra's
   bulletin header prints an MWL of 1690 ft and Ranjit Sagar has none in hand, and no
   storage figure above FRL is published for either, so their ratings clamp at FRL and
   their forced release stays the FRL bound. An elevation-capacity table above FRL for
   either dam (BBMB, the CWC dam register, a right-to-information reply) is what a cushion
   scenario there needs. Effort: small once a table is found.
8. **A second observed-rain record.** CHIRPS through the keyless ClimateSERV polygon API
   would give an independent 1981-onward series to cross-check the IMD grid in the mountains.
   Effort: medium; another dependency and quota.
9. **Ghaggar gauge model.** Nothing public gives Ghaggar discharge history; the state's
    situation reports during floods do. A request to the department for the Khanauri and
    Chandpur gauge records would unlock the rain-fed pathway as a real model instead of a
    percentile.

## What will not be done

No machine-learned forecaster trained on satellite labels, no blending of observed and
forecast quantities into one number, no claim of skill that the verification report does not
show. The prospective 2026 record is the test that counts, and it is being kept daily.
