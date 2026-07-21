# Long-record monsoon rain-loading trend — pre-registration

**Question.** Is the extreme monsoon rain loading over the flood-driving
catchments that produced the 2025 Punjab flood becoming *more frequent*? A single
extreme year proves nothing about a trend; this panel tests the long record.

**This file is a pre-registration.** Everything below — indices, boxes, base
period, test, significance level, record length, and the 2025-in-context method —
is fixed *before* any statistic is computed, so the result cannot be p-hacked.
The pre-declared indices are the **only** ones reported, significant or not. A
null result ("no significant long-term trend; 2025 is a rank-1 outlier in an
otherwise stationary record") is reported as faithfully as a positive one.

Written before computing. Implementation: pure index/stat math in
`sailaab/climatology.py` (TDD, synthetic-series tests first); orchestration in
`pipeline/make_rain_trend.py`; long-record daily extraction in
`pipeline/fetch_rain_longrecord.py`.

## Data

- **Product:** India Meteorological Department (IMD), Pune 0.25 deg x 0.25 deg
  **daily** gridded rainfall (mm/day) — the same official product used for the
  2015-2025 forecaster predictors (`docs/notes/imd-rain.md`). Pulled with
  `imdlib` (yearwise `.grd`, no login).
- **Record:** **1961-2025** (65 monsoons). Rasters ~25 MB/yr, downloaded
  resumably and NOT committed (gitignored). The committed 2015-2025 daily box
  means are reused verbatim; only 1961-2014 is newly fetched.
- **Fallback:** if the deep archive throttles and early years are unavailable,
  the record starts at the earliest gap-free year (>= **1975**) and the actual
  start is reported. (Outcome recorded in the Results section once run.)
- **Boxes** (identical to `docs/notes/imd-rain.md`, so the long record is
  methodologically continuous with the forecaster series):
  - `punjab`   — Punjab plains: lon 73.85-76.95 E, lat 29.53-32.60 N.
  - `upstream` — Sutlej/Beas/Ravi upstream Himalayan catchments:
    lon 75.5-78.6 E, lat 30.9-33.3 N.
- **Spatial reduction:** cos(lat)-weighted area-mean over in-box grid cells,
  no-data (`-999`) masked with `rain.where(rain >= 0)` — the exact
  `pipeline/fetch_rain.py` routine, imported (not re-implemented). Every index is
  therefore a **catchment-integrated (box-mean) loading**, which is the physically
  relevant quantity for basin flooding — not a point-gauge extreme.

## Season

**Monsoon = 1 June - 30 September (JJAS), inclusive**, per calendar year. All
three indices are computed within this window only.

## Indices (per box, per year) — the three, fixed

1. **R95cnt** — count of monsoon days whose box-mean rainfall is
   **>= the R95 threshold**, where the R95 threshold is the **95th percentile of
   wet-day box-mean rainfall over the 1961-1990 base period** (monsoon days only).
   - *Wet day* = box-mean rain **>= 1.0 mm**.
   - One threshold per box, from the fixed **1961-1990** base period (the WMO
     standard normal). Computed once, applied to every year 1961-2025.
2. **RX5day** — the **maximum 5-day running accumulation** (mm) of box-mean
   rainfall within the monsoon window (5-day sums, take the annual max).
3. **PRCPTOT** — **total monsoon rainfall** (mm): sum of box-mean daily rain over
   1 June - 30 September.

That is **3 indices x 2 boxes = 6 trend tests**. No others will be reported.

## Trend test — fixed

- **Mann-Kendall** rank test (two-sided), normal approximation of S with the
  standard tie correction:
  `Var(S) = [n(n-1)(2n+5) - sum_g t_g(t_g-1)(2t_g+5)] / 18`,
  continuity-corrected `Z = (S -/+ 1)/sqrt(Var(S))`, `p = 2(1 - Phi(|Z|))`.
- **Lag-1 autocorrelation handling — von Storch (1995) pre-whitening.**
  Estimate the lag-1 autocorrelation `r1` of the index series. If it is
  significant at 5% (`|r1| > 1.96/sqrt(n)`), remove it before the MK test
  (`x'_t = x_t - r1 * x_{t-1}`) and run MK on the pre-whitened series; otherwise
  run MK on the raw series. **`r1`, the raw-MK p, and the reported (pre-whitened
  where applicable) p are all published** so the autocorrelation and its effect
  are visible. Monsoon-total indices typically carry little year-to-year memory,
  so pre-whitening is expected to change little — but the rule is deterministic
  and fixed here regardless of outcome.
- **Sen's (Theil-Sen) slope** = median of all pairwise slopes
  `(x_j - x_i)/(j - i)`, computed on the **original** series (pre-whitening is for
  the significance test only). Reported **per decade** (slope x 10).
- **Significance level: alpha = 0.05**, two-sided. A trend is called
  "significant" iff the reported MK p < 0.05. With 6 tests we do **not** apply a
  multiplicity correction to the headline verdicts (each index is a distinct
  physical hypothesis); instead we report every p honestly and let the reader
  judge. No index is added, dropped, or reselected after seeing any p-value.

## 2025 in context — fixed, empirical only

The 2025 RX5day for each box is located in the **full 1961-2025 record** by:

- **Empirical rank** m (m = 1 is the largest year on record).
- **Empirical return period** by the Weibull plotting position,
  `T = (n + 1) / m` years (n = record length).

No GEV or other parametric tail is fitted — a fitted return period from a
65-value sample would over-claim. The rank + Weibull statement is the honest
one, and its ceiling (`T ~ n+1` for the record max) is acknowledged as a lower
bound on a rare event's true return period. RX5day is the headline (it is the
flood-relevant burst); rank/return for PRCPTOT and R95cnt are reported alongside
for completeness.

## Outputs

- `data/rain_daily_boxes_1961_2025.csv` — daily box means, full record (committed).
- `data/rain_indices_1961_2025.csv` — year x box x {R95cnt, RX5day, PRCPTOT}.
- `data/rain_trend_results.csv` — per (index, box): n, r1, Sen slope/decade,
  raw-MK p, reported MK p, verdict.
- `atlas/rain_trend.png` — house-style panel, one small-multiple per index, each
  box as a single-hue series with its Sen slope line, significance verdict, and
  the 2025 point highlighted.

## Results

**Record fetched.** 1961-2014 newly downloaded (54 yearwise `.grd`, ~25 MB/yr,
resumable) + the committed 2015-2025 box means reused verbatim = **1961-2025, 65
monsoons, gap-free**. The **1961-1990** R95 base period was fully available (no
fallback needed). Regenerate: `python pipeline/fetch_rain_longrecord.py` then
`python pipeline/make_rain_trend.py`.

**Trend verdicts** (Mann-Kendall + Theil-Sen, alpha=0.05; `data/rain_trend_results.csv`):

| Index | Box | Sen slope /decade | MK p | Verdict |
|---|---|---|---|---|
| R95cnt | upstream | **+0.56 days** | **0.017** | **significant increasing** |
| R95cnt | punjab | ±0.00 days | 0.796 | no significant trend |
| RX5day | upstream | -0.77 mm | 0.696 | no significant trend |
| RX5day | punjab | -2.98 mm | 0.165 | no significant trend |
| PRCPTOT | upstream | +1.84 mm | 0.843 | no significant trend |
| PRCPTOT | punjab | -8.29 mm | 0.316 | no significant trend |

**Lag-1 pre-whitening triggered for none** of the six series: every lag-1
autocorrelation `r1` (range -0.12 to +0.22) was below the `1.96/sqrt(65)=0.243`
threshold, so raw MK is reported throughout (monsoon indices carry little
year-to-year memory, as anticipated). Reported p == raw p for all six.

**Headline (honest).** Over 65 years the catchment rain *loading* is essentially
**stationary**: five of six indices — including **every** RX5day (the flood-
relevant 5-day burst) and **every** seasonal total — show **no significant
long-term trend**. The single detectable signal is a rising **frequency of
extreme-threshold wet days over the upstream Sutlej-Beas-Ravi catchments**
(R95cnt +0.56 days/decade, p=0.017 -> ~+3.6 such days across the record); the
Punjab-plains box shows no trend in any index.

**2025 in context (empirical rank / Weibull return in the 65-year record):**

| Index | Box | 2025 value | Rank | Return |
|---|---|---|---|---|
| RX5day | upstream | 129.2 mm | **11 / 65** | ~6 yr |
| RX5day | punjab | 154.4 mm | **6 / 65** | ~11 yr |
| PRCPTOT | upstream | 884.2 mm | 5 / 65 | ~13 yr |
| PRCPTOT | punjab | 907.3 mm | 3 / 65 | ~22 yr |
| R95cnt | upstream | 13 days | 3 / 65 | ~22 yr |
| R95cnt | punjab | 8 days | 4 / 65 | ~16 yr |

So at the **catchment-integrated (box-mean) full-monsoon** scale, 2025's rainfall
was **extreme but not unprecedented** — its 5-day burst ranks only 6th (Punjab)
and 11th (upstream) in 65 years, and its seasonal totals 3rd-5th. This is
consistent with, not contradictory to, the `docs/notes/imd-rain.md` finding that
2025 was rank-1/11 for the *specific Aug 20 - Sep 5 flood fortnight* against a
short 2015-2024 baseline: the disaster was driven by the **late-August timing and
antecedent near-full reservoirs** (see `atlas/causal_2025.png`), not by an all-
time-record seasonal accumulation. The long record does **not** support a claim
that this magnitude of monsoon loading is becoming more frequent — except for the
rising count of extreme-threshold days upstream, which it does support.
