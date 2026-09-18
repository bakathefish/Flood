# The Operator's Schedule: Release Forced by the Rule Curve (roadmap item 3)

> **For agentic workers:** executed inline by a single writer, tests first, smallest implementation that passes. Commits as the repository's own author with no attribution trailer. Every number in the docs comes from `outputs/` through `punjabflood report`.

**Problem.** The forced release is a bound on BBMB (the spillway must open when the reservoir is full), not a prediction of BBMB, which opens the gates days earlier under a filling schedule. The 2026-09-18 sweep found the Bhakra schedule as dated points and three dated gate openings, all below FRL:

| what | date | level (ft) | source |
|---|---|---|---|
| maximum permissible up to 31 July | 31 Jul | 1,650 | CBIP RTDSS presentation, page 44 (2019 chart); BBMB decision quoted in The Tribune letters, 24 Jul 2013 |
| maximum permissible up to 15 August | 15 Aug | 1,670 | CBIP RTDSS presentation, page 44 (2019 chart) |
| FRL not to be reached before | 31 Aug | 1,680 | Singh, PhD thesis, Jamia Millia Islamia, 2020, p. 112 |
| regulatory guideline for the date (revised schedule) | 19 Aug 2025 | 1,662 | The Tribune explainer, 20 Aug 2025 |
| floodgates opened | 10 Aug 2015 | 1,661.1 (9 Aug, 2 pm) | The Tribune, 10 Aug 2015 |
| floodgates opened | 13 Aug 2023 | 1,672 | PTI via Newsdrum, 19 Aug 2025 |
| floodgates opened | 19 Aug 2025 | 1,665.06 | Babushahi, 19 Aug 2025; The Tribune explainer |

Nothing of the kind exists for Pong (only the 1,390 ft ceiling and the EAP's 1,380 ft alert level) or Ranjit Sagar.

## Design
- `constants.rule_curve(dam)`: the dated points of the schedule in force (2019 chart: 31 Jul 1,650; 15 Aug 1,670; 31 Aug 1,680), None for the other dams. `constants.rule_curve_level_ft(dam, date)`: the maximum permissible level on a date, the level of a point holding up to its date (the chart draws horizontal lines), a straight line from 15 August to 31 August where the schedule only says FRL is not reached earlier, FRL after. The 2025 guideline point is recorded beside it as evidence that the schedule has been lowered since.
- `reservoirs.rule_curve_capacity_bcm(rating, dam, dates)`: the storage at the schedule level on each date through the dam's own rating.
- `hei.headroom_exhaustion` and `_balance_matrix` take a per-day capacity as well as a scalar, with `clamp_start=False` so a reservoir already above the schedule owes its drawdown on day one (the scalar bounds are unchanged).
- Product: for a dam with a schedule, `entry["rule_curve"]` with the schedule level and capacity by day of the horizon, the day-one headroom against it (negative when the reservoir is above the schedule), the deterministic and ensemble runs against it; a Markdown line. The routed arrivals stay the FRL bound.
- Verification: `perfect_prog_hei(..., rule_curve_rating=rating)` runs the event series against the schedule, and `rule_curve_timing_test` gives, for each dated gate opening, the first day of that season on which each bound forces a release and its lag from the opening; `results["rule_curve_timing"]`; report section.
- Also from the sweep: `data/reference/wrd/gauge_readings_press.csv`, the dated press readings of the river gauges (Dhilwan, Harike, Hussainiwala; 2023 and 2025), and `verify.routed_vs_gauge_readings`: the routed release on each dated reading day against the reading, as a ratio; report table. No attenuation fit: no station has a run of consecutive days.

## Tasks
1. [x] Constants, rating capacity, the per-day bound in `hei`; tests.
2. [x] Product block and Markdown line; tests.
3. [x] Verification runs, timing test, gauge readings check; report sections; tests.
4. [x] Docs (`design.md`, `roadmap.md` item 3, `data-sources.md`, README), suite green, commit, push.
