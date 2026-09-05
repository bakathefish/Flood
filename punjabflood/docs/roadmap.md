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
  naive forecast it has to beat.
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
   keyless). Effort: wait for archive, then small.
5. **Local inflow between the dams and Harike.** The WRD peaks at Harike and Dhilwan include
   tributaries (Swan and Sirsa on the Sutlej; Chakki and the Kandi torrents on the Beas) and
   plains rain. The HydroBASINS intermediate sub-basins are in the archive; the same runoff
   model with its own coefficient would add a local term at each control point. Effort:
   medium; improves magnitude ratios, not timing.
6. **Attenuation.** Pure translation is the department's own assumption and is right for
   timing; a linear reservoir per reach (one parameter each, fitted on nothing we have yet)
   would soften peaks. Only worth doing once daily gauge readings at the control points are
   available; the WRD publishes them during floods in its situation reports.
7. **Soil moisture as the wetness carrier.** The API is a proxy. ERA5-Land soil moisture is
   one archive pull away (the code path exists, `gamma`), and would let the coefficient
   respond to snowmelt-wetted soils the rain index cannot see. Effort: one long, quota-bound
   pull.
8. **Flood-scale error for the second probability.** The model-error term uses the
   ordinary-day RMSE. Once a daily inflow record for an event exists (item 1), the error at
   flood scale can be measured and the probability made an outer estimate instead of an
   inner one; the flood-scale check in `verification.md` already brackets it from the period
   means and season peaks the record holds. Effort: small once item 1 lands.
9. **Flood cushion above FRL.** Pong went to 1398 ft in 2023 and 1394.7 ft in 2025, above the
   1390 ft FRL; that storage absorbed part of the peak. The rating clamps at the highest
   level in the record, so the model treats FRL as the ceiling, which makes the forced
   release an early, upper bound. A published elevation-capacity table above FRL (the EAP has
   the gross figure at design FRL) would resolve it. Effort: small once the table is found.
10. **A second observed-rain record.** CHIRPS through the keyless ClimateSERV polygon API
   would give an independent 1981-onward series to cross-check the IMD grid in the mountains.
   Effort: medium; another dependency and quota.
11. **Ghaggar gauge model.** Nothing public gives Ghaggar discharge history; the state's
    situation reports during floods do. A request to the department for the Khanauri and
    Chandpur gauge records would unlock the rain-fed pathway as a real model instead of a
    percentile.

## What will not be done

No machine-learned forecaster trained on satellite labels, no blending of observed and
forecast quantities into one number, no claim of skill that the verification report does not
show. The prospective 2026 record is the test that counts, and it is being kept daily.
