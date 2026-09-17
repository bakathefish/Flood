# The Flood Cushion Above FRL (roadmap item 7)

> **For agentic workers:** executed inline by a single writer, tests first, smallest implementation that passes. Commits as the repository's own author with no attribution trailer. Every number in the docs comes from `outputs/` through `punjabflood report`.

**Problem.** Pong went to 1398 ft in August 2023 and 1394.7 ft in September 2025, above its reduced full reservoir level of 1390 ft; that storage absorbed part of each peak. The level-storage rating is fitted on the CWC record, whose live-storage column is capped at the FRL figure, so the rating is flat above 1390 ft and every reading above FRL rates as "full". Two consequences: the state record's storage change on the flood days is zero where the reservoir was in fact gaining (which is part of why the storage-change calibration cannot see the flood days), and the forced release the product prints is the FRL bound, which fires as soon as the reservoir touches 1390 ft while BBMB in practice lets it rise.

**What the record holds.** The Pong emergency action plan publishes the design pair: FRL 1400 ft with live storage 7,290 MCM, against the reduced FRL of 1390 ft with 6,157 MCM (CWC). That fixes the storage between 1390 and 1400 ft by linear interpolation, the same way the rating interpolates between its grid points. Bhakra's bulletin header prints MWL 1690 ft and Ranjit Sagar has no MWL in hand, but no storage figure above FRL is published for either, so neither gets a cushion; the product says so.

## Design
- `constants.flood_cushion(dam)`: `(top_level_m, top_live_bcm)` from the sourced constants, None where nothing is published; `cushion_capacity_bcm(dam)` is that live storage, or the live capacity where there is no cushion.
- `reservoirs.Rating.with_cushion(dam)`: the fitted curve below FRL, then a straight line from `(FRL, storage(FRL))` to the cushion top; `fit_ratings` applies it, so the state record, the bulletin state and the reconciliation all rate readings above FRL on the line instead of clamping.
- The headroom-exhaustion functions already take `capacity_bcm`; `verify.perfect_prog_hei`, `carry_storage` and `_hei_row` gain the same parameter and pass it through.
- The product prints, beside the FRL-bound scenario it has always printed, a cushion scenario for the dams that have one: the spill probability and median peak forced release by horizon with the capacity at the cushion top. The routed arrivals stay the FRL bound (the upper bound), stated.
- Verification: the event-timing test of 2023 and 2025 is run again with Pong's capacity at the cushion top (model-carried storage, routed with passage) and printed beside the FRL-bound rows. No adoption rule: the two are a bracket, both are kept.
- The storage-change calibration is rerun on the corrected record; the report's parameter table and the leave-one-season-out errors move with it and are recorded.

## Tasks
1. [x] Constants and tests: Pong has a cushion (1400 ft, 7.290 BCM), the others None.
2. [x] Rating extension and tests: below FRL unchanged; at FRL the fitted value; at the top the published value; a dam without a cushion unchanged; a level between rates on the line.
3. [x] `perfect_prog_hei(..., capacity_bcm)` through `_event_series`, `carry_storage`, `_hei_row`, with a test that a reservoir full at FRL does not spill under the cushion capacity.
4. [x] Product: `entry["cushion"]` with the deterministic primary and the ensemble by horizon; Markdown table; tests.
5. [x] `verify` and `report`: `event_timing_cushion`, the section rows, the parameter table after recalibration.
6. [x] **Outcome 2026-09-18:** FRL bound keeps its timing; cushion bound late (2025) or absent (2023); parameters unchanged on recalibration. Recalibrate, verify, report, figures; `design.md`, roadmap (item 7 to Done), README; suite green; commit, push.
