# Dam headroom — how much less pre-positioned storage than the decade-median practice

**Status: PRE-DECLARED (this section written and committed *before* the numbers
were computed).** Actuals and the verdict are appended in the two sections at the
bottom, in a later commit, so the git history shows the hypotheses predate the
result.

## What this is — and what it is *not*

A careful quantification of the **management component** of the 2025 Punjab flood,
using only data already committed in this repo. It is **arithmetic on storage
curves**, not a hydraulic or routing simulation. The number we are after is one
disciplined quantity:

> **How many BCM *less* empty storage (headroom) did Bhakra / Pong / Ranjit Sagar
> hold on the eve of the flood than the *median of their own 2015–2024 practice*
> would have provided on the same day-of-season?**

We do **not** claim the flood was avoidable. The primary cause is the rain — a
late-August pulse over the Sutlej–Beas–Ravi catchments at roughly **+10σ / ≈10×
the 2015–24 same-day median** (see `atlas/rain_trend.png`, `atlas/causal_2025.png`).
Reservoir headroom is a *secondary, contributory* factor and is framed as such.

This is the quantitative companion to SANDRP's qualitative argument (SANDRP,
"Punjab Floods 2025: Role of Bhakra, Pong and Ranjit Sagar Dams", 2025-09-07),
which said the dams *could* have kept more room but did not put a decade-baselined
BCM figure on it. Prior-work credit is theirs; this note supplies the number.

## Framing rules (non-negotiable — copied onto the figure caption)

- **(a) Never "avoidable".** The claim is only: *"N BCM less pre-positioned
  storage than the decade-median practice would have provided,"* never "the flood
  could have been prevented."
- **(b) Legitimate reasons dams fill early exist** and are acknowledged:
  irrigation and hydropower delivery commitments, the rule-curve filling schedule,
  and genuine forecast uncertainty (holding room you may not get to refill is a
  real economic risk). Running fuller is a *defensible* operating choice, not
  presumptive misconduct.
- **(c) Presented alongside the +10σ rain**, which remains the primary cause and
  is shown in the same figure/caption.
- **(d) SANDRP's qualitative version is cited as prior work** (above).
- **(e) The BBMB→CWC central-reporting gap (series ends 2025-07-11)** limits
  post-11-Jul precision to the cited BBMB/press supplement points. Every 2025
  August value is tagged with its basis; nothing post-11-Jul is presented as a
  dense daily measurement.

## Pre-declared quantities (exactly what will be computed)

1. **Decade-median filling curve**, per dam, on a Jun 1 → Sep 30 day-of-season
   axis (day 0 = Jun 1 … day 121 = Sep 30):
   - median (p50), and the **p25–p75 IQR band**, of live storage (BCM) across
     prior years **2015–2024**, per day-of-season;
   - also expressed as **% of live capacity** (storage ÷ live capacity × 100);
   - **`n_years` reported per day-of-season** (how many prior years contribute),
     because coverage is uneven — especially Pong, whose 2021–24 monsoons are
     sparse in the central feed.
2. **2025 filling curve**, per dam: the CWC daily API to 11 Jul (dense, measured)
   spliced to the cited BBMB/press supplement points after 11 Jul. For Ranjit
   Sagar, which BBMB reported in **levels only** through the flood window, August
   storage is a **hypsometric estimate** — the dam's own 2015–24 level↔storage
   rating applied to the reported level — and is flagged as such.
3. **Headroom deficit**, per dam, for **each date 2025-08-01 → 2025-08-25**:
   `deficit_bcm = storage_2025 − median_curve_storage` (positive = 2025 *fuller*
   than the decade median = *less* headroom) and
   `deficit_pctpts = deficit_bcm ÷ live_capacity × 100`.
   The 2025 storage on each date is a **no-extrapolation** piecewise-linear
   interpolation between cited points; each row carries a **`basis`** tag
   (`api`, `press_storage`, `press_pct`, `frl_crossing`, `hypsometric`,
   `interp`) and rows requiring extrapolation beyond the cited points are left
   blank rather than invented.
4. **Buffer arithmetic** for the documented **Aug 26–27** release surge:
   - mass balance `inflow ≈ Δstorage + outflow`; at/near FRL the dam is spilling
     so `Δstorage ≈ 0` and the documented **peak release** is used as the surge
     inflow proxy;
   - unit conversion `1 cusec = 0.028316846592 m³/s × 86 400 s = 2 446.575 m³/day
     = 2.446575 × 10⁻⁶ BCM/day`;
   - **`absorbable_days = deficit_bcm ÷ (peak_release_cusecs × 2.446575e-6)`** per
     dam — *"how long the missing headroom would have lasted at that dam's peak
     documented throughput, had 2025 tracked the decade median."*
   - Documented peak releases used (from `docs/notes/reservoirs.md`): Ranjit
     Sagar **173,000 cusecs** (Aug 27), Bhakra **~85,000 cusecs** (Sep 4–5), Pong
     **~100,000 cusecs** (from Aug 29). Basin-scale Sutlej cumulative ≈ 2.6 lakh
     (260,000) cusecs is reported for context only.

Constants (live capacity, FRL) are **reused** from `sailaab/causal.py`
(`LIVE_CAPACITY_BCM`, `FRL_FT`, `FRL_M`), themselves sourced from
`docs/notes/reservoirs.md`: Bhakra 6.229 BCM / 1 680 ft, Pong 6.157 BCM /
1 390 ft, Ranjit Sagar 2.344 BCM / 527.91 m.

## Pre-declared falsification criteria (committed before seeing the result)

Primary metric: the **2025-08-25 headroom deficit** per dam (BCM and percentage
points of live capacity). We commit *now* to reporting each dam into one of these
bins, whichever way it lands:

- **HOLDS** — deficit **≥ +0.3 BCM and ≥ +5 pts**: 2025 was materially fuller than
  the decade median → a real, quantifiable management component for that dam.
- **NEGLIGIBLE** — `0 ≤ deficit < 0.3 BCM` or `< 5 pts`: 2025 tracked the decade
  median within noise → the headroom argument does **not** hold for that dam and
  we will say so plainly.
- **FALSIFIED** — deficit **< 0**: 2025 was *emptier* than the decade median → the
  dam actually held **more** room than usual; the management narrative is
  *reversed* for that dam and we will report that reversal.

Thresholds are pre-registered, not tuned: 0.3 BCM ≈ 5 % of Bhakra/Pong live
capacity (≈ 13 % of Ranjit Sagar's); 5 pts is a modest, plainly visible fraction
of the 0–100 % axis. Every median point is reported with its `n_years`; where
`n_years` is thin (Pong) the deficit is labelled low-confidence regardless of bin.

The narrative would also be **weakened** if the 2025 curve sat *inside* the
2015–24 IQR band (i.e. 2025 is an ordinary year, not an outlier fill); we commit
to reporting the band-relative position, not only the median difference.

## Method / reproduce

Pure math in `sailaab/headroom.py` (median-curve builder, day-of-season index,
no-extrapolation interpolation, deficit calc, cusec→BCM/day, absorbable-days),
TDD-tested in `tests/test_headroom.py` on synthetic data. Figure + CSV built by:

```
python pipeline/make_headroom.py            # -> data/headroom_2025.csv, atlas/headroom_2025.png
python -m pytest tests/test_headroom.py -q
```

<!-- ============================================================ -->
<!-- ACTUALS and VERDICT are appended below in a later commit,    -->
<!-- after the code above computes them. Nothing below this line  -->
<!-- was written before the numbers existed.                      -->
<!-- ============================================================ -->

## Actuals (computed by `pipeline/make_headroom.py`)

### Coverage behind the decade-median curve (2015–2024, storage-days per day-of-season)

| Dam | `n_years` per day (min–max, median) | On 2025-08-25 | Note |
|---|---|---|---|
| Bhakra | 6–10 (median 9) | 8 | good |
| Pong | **4–9 (median 7)** | **6** | 2021–24 monsoons sparse — deficits low-confidence |
| Ranjit Sagar | 8–10 (median 10) | 9 | best coverage; but Aug 2025 is a **hypsometric** estimate |

### Headroom deficit on 2025-08-25 (eve of the Aug 26–27 surge)

`deficit = 2025 storage − 2015–24 raw daily median`; positive = **less** headroom
than the decade-median practice. Full daily Aug 1–25 series in
`data/headroom_2025.csv` (with per-row `basis`).

| Dam | 2025 storage | Decade median | **Deficit (BCM)** | **Deficit (pts)** | vs IQR | Aug 1–25 mean | `basis` @ 25 Aug |
|---|---|---|---|---|---|---|---|
| **Pong** | 6.04 BCM (98%) | 5.03 BCM (82%) | **+1.01** | **+16.4** | **above p75** | +1.57 BCM / +25 pts | `interp_frl` |
| **Ranjit Sagar** | 2.21 BCM (94%) | 1.76 BCM (75%) | **+0.45** | **+19.1** | **above p75** | +0.25 BCM / +11 pts | `interp_hyps` |
| **Bhakra** | 5.20 BCM (83%) | 4.98 BCM (80%) | **+0.22** | **+3.5** | within IQR | +0.39 BCM / +6 pts | `interp` |

Bhakra ran a real lead in **early/mid-August** (peak **+0.76 BCM / +12 pts** on
Aug 12) but its decade-median fills steeply through late August and had caught up
by the 25th — hence the small surge-eve deficit.

### Buffer arithmetic (Aug 26–27 release surge)

`inflow ≈ Δstorage + outflow`; at/near FRL the dam spills so `Δstorage ≈ 0` and
the documented **peak release** is used as the surge proxy.
`absorbable_days = deficit_bcm ÷ (peak_cusecs × 2.446575e-6 BCM/day)`.

| Dam | Deficit (BCM) | Peak release | = BCM/day | **Buffer (days)** |
|---|---|---|---|---|
| Pong | +1.01 | ~100,000 cusecs | 0.245 | **~4.1 d** |
| Ranjit Sagar | +0.45 | 173,000 cusecs (27 Aug) | 0.423 | **~1.1 d** |
| Bhakra | +0.22 | ~85,000 cusecs | 0.208 | **~1.0 d** |

Total surge-eve pre-positioning deficit across the three dams ≈ **+1.68 BCM**.
Basin-scale Sutlej cumulative release ≈ 2.6 lakh (260,000) cusecs is context only.

## Verdict (against the pre-declared bins)

- **Pong — HOLDS (strong).** +1.01 BCM / +16 pts, **outside its normal IQR** all
  August. The clearest management component of the three. *Caveat: thin priors
  (`n_years` 4–9); the magnitude, not the sign, is uncertain.*
- **Ranjit Sagar — HOLDS.** +0.45 BCM / +19 pts, **outside its IQR**. Small dam,
  so the percentage-point gap is large while the BCM is modest. *Caveat: 2025
  August storage is a hypsometric estimate from the dam's own level↔storage
  rating (BBMB reported levels only); by Aug 27 its level (527.13 m) sat at the
  top of the 2015–24 observed range.*
- **Bhakra — NEGLIGIBLE at the surge date.** +0.22 BCM / +3.5 pts, **within its
  IQR** — 2025 tracked the decade median by Aug 25. This is exactly the
  pre-declared "weakens" outcome, reported as such. (A real early/mid-August lead
  existed but had closed by the surge.)

**Net: the headroom argument is supported for Pong and Ranjit Sagar and does not
hold for Bhakra on the surge date — a partial, honestly-mixed result, not a clean
three-for-three.** No dam was *emptier* than its decade median (no full
reversal). The pre-positioning deficit is **real but second-order**: even the
largest (Pong) equals only ~4 days of peak release, against a multi-week +10σ
rain pulse that remains the primary cause.

### One-sentence honest headline (for the synopsis)

> Two of the three BBMB dams — **Pong (+1.0 BCM, +16 pts) and Ranjit Sagar
> (+0.45 BCM, +19 pts)** — met the Aug 26–27 surge holding **more water than their
> own decade-median practice** and thus that much *less* pre-positioned flood
> headroom (Bhakra was near its median), a gap equal to only ~1–4 days of each
> dam's peak release — **real but second-order to the record +10σ rain that caused
> the flood.**

### Robustness

Deficits are computed against the **raw** per-day median (as pre-declared). A
7-day centred smoothing of the climatological median (to damp sparse-year
sampling noise) shifts the Aug-25 deficits by ≤0.04 BCM for Bhakra/Ranjit Sagar
and +0.31 BCM for Pong — **changing no verdict bin**. The figure draws the
smoothed median (bold) over the raw IQR band; the CSV holds raw daily values.

### Honesty ledger / limits

- **Pong Aug 1–7** rows are interpolated across the 29-day Jul-11→Aug-8 reporting
  gap (`basis = interp_wide`) and are the least reliable; the Aug-25 headline sits
  on the tight Aug-18→26 bracket and does not depend on them.
- **Ranjit Sagar** August storage is hypsometric, not directly reported
  (`basis = interp_hyps` / `hypsometric`).
- Precision post-11-Jul is capped by the cited supplement points (framing rule e).
- This is arithmetic on storage curves, **not** a routing/hydraulic model; the
  buffer-days figure answers "how long would the extra empty space have lasted at
  peak throughput," never "the flood would have been prevented" (framing rule a).
