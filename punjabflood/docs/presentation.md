# The river watch, in ten minutes

A daily forecast of whether the Bhakra and Pong spillways will be forced open in the
next five days, what that release does at five points on the Punjab rivers, and how
much rain is coming over each catchment. Everything below is drawn from
[`verification.md`](verification.md), which the package renders from its outputs; the
figures come from `scripts/make_brief_figures.py` on the same files.

## The question

Punjab's largest river floods are dam-release floods. In late August 2025 the Beas rose
into Pong while the reservoir was already near its flood cushion, the gates opened on
27 August, and the wave peaked at Dhilwan on 31 August. Anyone standing on the
Dhilwan bridge that morning had four days' notice from the gate opening. The watch asks
a different question: how many days before the gates open can the rain forecasts, run
through a water balance of the reservoir, say they will have to?

## What it reads

- The BBMB daily bulletin: level, inflow and outflow at Bhakra and Pong, fetched every
  morning. Storage comes from each dam's own level-storage relation fitted on the CWC
  record.
- Rain over eight catchments (the three dams, three local catchments between the dams
  and the head works, the Ghaggar and Sutlej reaches), area-weighted over HydroBASINS
  polygons. The observed record is IMD's real-time 0.25 degree grid; the forecasts come
  from four weather models (ECMWF AIFS as the primary, ECMWF IFS, GFS, ICON) and the
  51-member ECMWF ensemble, all keyless.
- Snow at Bhakra: ERA5 snowfall stacked into a pack at each archive point of the
  catchment and released by degree-days, for the half of the catchment the rain grid
  does not cover.

![What fell and what is forecast over each dam catchment, with the level](../outputs/figures/brief_weather_watch.png)

## What it says each day

For each dam and each of the next five days: forecast inflow, headroom, what the
turbines can pass, and the surplus a full reservoir cannot hold. The chance that the
spillway is forced is printed three times, from the rain ensemble alone, with the inflow
model's ordinary-day error added, and with its flood-scale volume error added on top;
the site shows the widest. The forced release is routed downstream on the Water
Resources Department's published travel times and classed Low, Medium or High against
the department's thresholds at Ropar, Phillaur, Harike, Dhilwan and Ferozepur.

The weather watch sits beside it with a level per catchment (quiet, watch, alert) from
rules written before any season was scored: the primary model's next three days placed
in the 1961 to 2025 record of monsoon three-day totals, and the share of models with a
30 mm day.

## How it did on the 2025 flood

Run day by day over the forecasts that were issued at the time, the watch would have
said this before the event:

| dam | first flagged forced spill | gates opened | lead | Dhilwan peak | lead | flagged days | false |
|---|---|---|---|---|---|---|---|
| Pong (AIFS) | 17 Aug 2025 | 27 Aug 2025 | 10 days | 31 Aug 2025 | 14 days | 23 | 0 |
| Pong (IFS) | 15 Aug 2025 | 27 Aug 2025 | 12 days | 31 Aug 2025 | 16 days | 25 | 0 |
| Bhakra (AIFS and IFS) | 30 Aug 2025 | 19 Aug 2025 | after the fact | n/a | n/a | 3 | 0 |

At Bhakra BBMB opened the gates on 19 August at 1,665 ft, below the 1,672.5 ft its
filling schedule allowed that day, so the watch, which forecasts the schedule's bound,
first flagged on 30 August, eleven days late; its three flagged days were each followed
by gate operation, none false. In 2024 and 2026, seasons with no forced spill, the
watch flagged no day at either dam.
The weather watch reached watch level over the Bhakra catchment on 9 August 2025, ten
days before the 19 August gate opening, and alert on 10 August; over Pong and Ranjit
Sagar it was raised at least fourteen days before the largest inflow day. Its false
alarms are counted over 1,029 issue days: 23 of the 119 issue days of 2024 and 20 of
the 105 of 2026 sat at watch or above over Bhakra with no dam event that year.

![The 2025 event at Dhilwan: routed release against the dated peak](../outputs/figures/event_2025_dhilwan.png)

## How it is doing this season

Against the 2026 BBMB bulletins, one day ahead. The baseline is carrying today's inflow
forward; the difference is what the rain forecast brings.

| dam | days | model MAE (cusecs) | model r | persistence MAE (cusecs) | persistence r |
|---|---|---|---|---|---|
| Bhakra | 30 | 4,040 | 0.58 | 4,148 | 0.56 |
| Pong | 30 | 5,904 | 0.86 | 12,135 | 0.37 |

![Live 2026 one-day inflow error against persistence](../outputs/figures/brief_live_2026.png)

The observed rain the product carries in season is IMD's real-time grid. Scored against
the final grid over 2025 it lands within 11% of the mean at each dam catchment with r
of 0.98 or better; the ERA5 record it replaced ran 12 to 27% low.

![IMD real-time grid and ERA5 against the final IMD grid](../outputs/figures/brief_realtime_rain.png)

## The snowmelt term

Bhakra's base flow is snowmelt from outside the rain grid. The degree-day term enters
the inflow fit as a lagged variable with its own coefficient (0.067) and lag weights;
it was adopted because the held-out error at Bhakra did not rise and the season peak
rose, from 0.5699 to 0.5775 of the stated peak. Over the 2025 monsoon the melt response
averaged 0.025 BCM over five days, about 2,000 cusecs a day, a seasonal modulation of
the base flow rather than the flood signal.

![Degree-day melt at Bhakra beside the held-out error of every inflow variant](../outputs/figures/brief_snowmelt.png)

## What it does not do

- It undershoots flood peaks. Over the 2025 flood periods the model's volumes came to
  0.78 to 1.13 of what BBMB reported, but its largest day was 0.58 of the stated peak.
  Lag weights fitted on ordinary days spread a flood over more days than the river does.
  A day-wise inflow record for 2023 and 2025 is the data that fixes this; `roadmap.md`
  lists the rest.
- Ranjit Sagar has no public daily bulletin, so it has a weather watch and no dam row.
- The Ghaggar has no public gauge history, so it gets the rain forecast and its
  percentile only.
- It is not an official warning. The Punjab WRD, CWC, BBMB and IMD issue those.

## Where it lives

- Live: the river watch section of [bakathefish.github.io/Flood](https://bakathefish.github.io/Flood/#rivers),
  reading `outputs/forecast/latest.json`, which a daily GitHub Action rewrites; the dated
  records beside it are never rewritten.
- Code, tests and data: [`punjabflood/`](../) in the Sailaab repository, MIT.
- The full record: [`verification.md`](verification.md), [`design.md`](design.md),
  [`data-sources.md`](data-sources.md), [`roadmap.md`](roadmap.md).
