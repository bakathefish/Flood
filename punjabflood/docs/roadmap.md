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
   disappears. Effort: data hunt plus one calibration mode.
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
3. **The operator.** The forced release is a bound on BBMB, not a prediction of BBMB. The
   board runs a filling schedule (rule curve). Two points of the Bhakra schedule are now in
   hand from the chart on page 44 of the CBIP decision-support presentation (2019 season,
   read off the image, the lines sit on the gridlines): a maximum permissible level of
   1,650 ft up to 31 July and 1,670 ft up to 15 August, against a full reservoir level of
   1,680 ft; they are recorded in `constants.py` with the vintage. Press coverage of
   19 August 2025 quotes a guideline of 1,662 ft for that date, below the 2019 line, so the
   schedule has been revised since and the current one, with the date the reservoir may
   reach FRL, is what a rule-curve scenario needs; nothing is in hand for Pong. With the
   current schedule as dated (date, level) points, a second scenario follows: release forced
   by the rule curve, which fires days before the FRL bound and would speak to the 2025
   pre-emptive releases. Effort: locate the current schedule (BBMB Technical Committee
   minutes or a right-to-information reply), then a small module.
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
6. **Flood-scale error for the second probability.** The model-error term uses the
   ordinary-day RMSE. Once a daily inflow record for an event exists (item 1), the error at
   flood scale can be measured and the probability made an outer estimate instead of an
   inner one; the flood-scale check in `verification.md` already brackets it from the period
   means and season peaks the record holds. Effort: small once item 1 lands.
7. **Flood cushion above FRL.** Pong went to 1398 ft in 2023 and 1394.7 ft in 2025, above the
   1390 ft FRL; that storage absorbed part of the peak. The rating clamps at the highest
   level in the record, so the model treats FRL as the ceiling, which makes the forced
   release an early, upper bound. A published elevation-capacity table above FRL (the EAP has
   the gross figure at design FRL) would resolve it. Effort: small once the table is found.
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
