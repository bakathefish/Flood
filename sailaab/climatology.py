# sailaab/climatology.py
"""Extreme monsoon-rain indices and long-record trend statistics (pure numpy /
pandas, stdlib ``math.erfc`` for the normal tail — no scipy/pymannkendall dep).

Consumes a *daily area-mean* frame (``date`` + one box column, e.g.
``punjab_mm``), the same shape produced by ``pipeline/fetch_rain.py``. Everything
here is unit-tested on synthetic series of known trend
(``tests/test_climatology.py``); the pre-registration of indices/tests lives in
``docs/notes/rain-trend.md``.

Two layers:

* **Indices** — per box, per monsoon (1 Jun - 30 Sep):
  :func:`total_monsoon` (PRCPTOT), :func:`rx5day` (max 5-day accumulation), and
  :func:`r95_count` against a fixed :func:`wet_day_threshold` (95th percentile of
  wet-day rain over a base period). :func:`annual_indices` tabulates all three.
* **Trend statistics** — :func:`mann_kendall` (tie-corrected, continuity-
  corrected normal approximation), :func:`lag1_autocorr` / :func:`prewhiten` /
  :func:`mann_kendall_prewhitened` (von Storch 1995 lag-1 pre-whitening),
  :func:`sens_slope` (Theil-Sen), and :func:`empirical_return_period` (Weibull
  plotting position, no fitted tail).
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

MONSOON = ("06-01", "09-30")  # JJAS, inclusive


# --------------------------------------------------------------------------- #
# season slicing
# --------------------------------------------------------------------------- #
def _season_mask(dates: pd.Series, season: tuple[str, str]) -> pd.Series:
    """Boolean mask for calendar days whose (month, day) lies in the inclusive
    ``[start, end]`` window, independent of year."""
    (s, e) = season
    s_mo, s_dy = int(s[:2]), int(s[3:5])
    e_mo, e_dy = int(e[:2]), int(e[3:5])
    mo, dy = dates.dt.month, dates.dt.day
    after = (mo > s_mo) | ((mo == s_mo) & (dy >= s_dy))
    before = (mo < e_mo) | ((mo == e_mo) & (dy <= e_dy))
    return after & before


def _year_season(daily: pd.DataFrame, col: str, year: int, season) -> pd.DataFrame:
    d = daily[["date", col]].copy()
    d["date"] = pd.to_datetime(d["date"])
    m = (d["date"].dt.year == year) & _season_mask(d["date"], season)
    return d.loc[m].sort_values("date")


# --------------------------------------------------------------------------- #
# indices
# --------------------------------------------------------------------------- #
def total_monsoon(daily, col, year, season=MONSOON) -> float:
    """PRCPTOT — total box-mean rainfall (mm) over the monsoon window."""
    s = _year_season(daily, col, year, season)
    return float(s[col].sum(min_count=1))


def wet_day_threshold(
    daily, col, base_years, pct=95.0, wet_mm=1.0, season=MONSOON
) -> float:
    """``pct``-th percentile (linear) of wet-day (>= ``wet_mm``) box-mean rain
    over the monsoon days of ``base_years`` — the fixed R95 threshold."""
    d = daily[["date", col]].copy()
    d["date"] = pd.to_datetime(d["date"])
    m = d["date"].dt.year.isin(list(base_years)) & _season_mask(d["date"], season)
    vals = d.loc[m, col].to_numpy(dtype=float)
    wet = vals[vals >= wet_mm]
    return float(np.percentile(wet, pct)) if wet.size else float("nan")


def r95_count(daily, col, year, threshold, season=MONSOON) -> int:
    """Number of monsoon days with box-mean rain >= ``threshold``.

    (Comparisons against a NaN threshold are all False -> 0, so an empty base
    period degrades gracefully.)"""
    s = _year_season(daily, col, year, season)
    v = s[col].to_numpy(dtype=float)
    return int(np.count_nonzero(v >= threshold))


def rx5day(daily, col, year, season=MONSOON, window=5) -> float:
    """Maximum ``window``-day running accumulation (mm) within the monsoon.

    Only full ``window``-day sums count; a season shorter than ``window`` days
    yields NaN."""
    s = _year_season(daily, col, year, season)
    v = s[col].astype(float)
    if len(v) < window:
        return float("nan")
    return float(v.rolling(window, min_periods=window).sum().max())


def annual_indices(
    daily, col, years, base_years, pct=95.0, wet_mm=1.0, season=MONSOON
) -> pd.DataFrame:
    """Per-year table ``year, r95cnt, rx5day, prcptot`` for one box column.

    The R95 threshold is computed once from ``base_years`` and applied to every
    year (so R95cnt is comparable across the record)."""
    thr = wet_day_threshold(daily, col, base_years, pct, wet_mm, season)
    rows = [
        {
            "year": int(y),
            "r95cnt": r95_count(daily, col, y, thr, season),
            "rx5day": rx5day(daily, col, y, season),
            "prcptot": total_monsoon(daily, col, y, season),
        }
        for y in years
    ]
    return pd.DataFrame(rows, columns=["year", "r95cnt", "rx5day", "prcptot"])


# --------------------------------------------------------------------------- #
# trend statistics
# --------------------------------------------------------------------------- #
def _norm_sf(z: float) -> float:
    """Upper-tail standard-normal survival function via stdlib erfc."""
    return 0.5 * math.erfc(z / math.sqrt(2.0))


def mann_kendall(x) -> dict:
    """Mann-Kendall trend test, two-sided.

    Returns ``s`` (statistic), ``var_s`` (tie-corrected), ``z`` (continuity-
    corrected), ``p`` (2-sided normal-approx), ``tau`` (tau-b), ``n``.
    """
    x = np.asarray(list(x), dtype=float)
    x = x[~np.isnan(x)]
    n = int(x.size)
    s = 0
    for i in range(n - 1):
        s += int(np.sum(np.sign(x[i + 1 :] - x[i])))

    _, counts = np.unique(x, return_counts=True)
    tie = float(np.sum(counts * (counts - 1) * (2 * counts + 5)))
    var_s = (n * (n - 1) * (2 * n + 5) - tie) / 18.0

    if var_s <= 0 or s == 0:
        z = 0.0
    elif s > 0:
        z = (s - 1) / math.sqrt(var_s)
    else:
        z = (s + 1) / math.sqrt(var_s)
    p = 2.0 * _norm_sf(abs(z))

    n0 = n * (n - 1) / 2.0
    n_ties = float(np.sum(counts * (counts - 1) / 2.0))
    denom = math.sqrt((n0 - n_ties) * n0) if n0 > 0 else 0.0
    tau = s / denom if denom > 0 else float("nan")

    return {
        "s": int(s),
        "var_s": float(var_s),
        "z": float(z),
        "p": float(min(p, 1.0)),
        "tau": float(tau),
        "n": n,
    }


def lag1_autocorr(x) -> float:
    """Lag-1 autocorrelation (Pearson, biased/full-variance estimator)."""
    x = np.asarray(list(x), dtype=float)
    dev = x - x.mean()
    denom = float(np.sum(dev * dev))
    if denom == 0.0:
        return 0.0
    return float(np.sum(dev[:-1] * dev[1:]) / denom)


def prewhiten(x, r1: float | None = None) -> np.ndarray:
    """von Storch (1995) lag-1 pre-whitening: ``x'_t = x_t - r1 * x_{t-1}``.

    Returns a length ``n-1`` series. ``r1`` is estimated by
    :func:`lag1_autocorr` when not supplied."""
    x = np.asarray(list(x), dtype=float)
    if r1 is None:
        r1 = lag1_autocorr(x)
    return x[1:] - r1 * x[:-1]


def mann_kendall_prewhitened(x, sig=1.96) -> dict:
    """MK with deterministic lag-1 pre-whitening.

    If ``|r1| > sig/sqrt(n)`` (i.e. the lag-1 autocorrelation is significant at
    ~5%), the series is pre-whitened before the MK test; otherwise the raw MK
    result is reported. Both the raw and the reported p-values plus ``r1`` are
    returned so the autocorrelation and its effect are transparent.
    """
    x = np.asarray(list(x), dtype=float)
    x = x[~np.isnan(x)]
    n = int(x.size)
    r1 = lag1_autocorr(x)
    crit = sig / math.sqrt(n) if n > 0 else float("inf")
    raw = mann_kendall(x)
    if abs(r1) > crit:
        rep = mann_kendall(prewhiten(x, r1))
        applied = True
    else:
        rep = raw
        applied = False
    return {
        "r1": float(r1),
        "prewhitened": bool(applied),
        "p": float(rep["p"]),
        "p_raw": float(raw["p"]),
        "z": float(rep["z"]),
        "s": int(rep["s"]),
        "tau": float(raw["tau"]),
        "n": n,
    }


def sens_slope(x, t=None) -> float:
    """Theil-Sen slope: median of all pairwise slopes ``(x_j-x_i)/(t_j-t_i)``.

    ``t`` defaults to ``0..n-1`` (slope per step); pass calendar years for a
    per-year slope."""
    x = np.asarray(list(x), dtype=float)
    n = x.size
    t = np.arange(n, dtype=float) if t is None else np.asarray(list(t), dtype=float)
    slopes = []
    for i in range(n - 1):
        dt = t[i + 1 :] - t[i]
        dx = x[i + 1 :] - x[i]
        ok = dt != 0
        slopes.append(dx[ok] / dt[ok])
    if not slopes:
        return float("nan")
    all_s = np.concatenate(slopes)
    all_s = all_s[~np.isnan(all_s)]
    return float(np.median(all_s)) if all_s.size else float("nan")


def empirical_return_period(values, target) -> dict:
    """Locate ``target`` in ``values`` (the full record, including ``target``)
    and report the empirical rank and Weibull return period.

    ``rank`` = 1 + (# strictly greater) so the record max is rank 1;
    ``return_period`` = ``(n+1)/rank`` years; ``exceedance_prob`` = ``1/T``.
    No parametric tail is fitted.
    """
    v = np.asarray(list(values), dtype=float)
    v = v[~np.isnan(v)]
    n = int(v.size)
    rank = int(1 + np.count_nonzero(v > target))
    T = (n + 1) / rank
    return {
        "rank": rank,
        "n": n,
        "return_period": float(T),
        "exceedance_prob": float(rank / (n + 1)),
    }
