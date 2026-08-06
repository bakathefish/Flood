# sailaab/uncertainty.py
"""How much of the forecaster's measured skill could be luck.

Average precision is a single number over 8,863 correlated district-days: the
target asks about a three-day horizon, so consecutive days share outcomes, and
neighbouring districts flood together. Treating those rows as independent makes
any interval far too tight. Worse, the pooled figure is dominated by whichever
seasons carry the most positives — 2025 alone can carry it.

So resampling happens at two levels: whole seasons, then blocks of whole days
inside each sampled season. A day block moves every district for that day
together, which is the dependence that actually exists.

The paired delta matters more than either model's interval. Asking "is
excitation worth anything" means comparing two models on the *same* resampled
rows, because most of the variance is which rows you drew, and that cancels.

With four seasons that contain flooding, none of this produces a tight answer,
and it is not supposed to. It produces an honest one.
"""

from __future__ import annotations

import numpy as np
from sklearn.metrics import average_precision_score

# Longer than the 3-day target horizon, so a block spans the dependence rather
# than slicing through the middle of it.
BLOCK_DAYS = 7


def _circular_block_days(days, block, rng):
    """Resample a season's days in circular blocks, preserving the day count."""
    n = len(days)
    picked = []
    while len(picked) < n:
        start = int(rng.integers(n))
        picked.extend(days[(start + np.arange(block)) % n])
    return picked[:n]


def two_stage_bootstrap(
    y, scores, season, day, n_boot=2000, block=BLOCK_DAYS, seed=0
):
    """Two-stage block bootstrap of average precision.

    ``scores`` maps a candidate name to its score array, so every candidate is
    evaluated on the *same* resampled rows and the deltas between them are
    paired.

    Stage one samples seasons with replacement; stage two resamples circular
    blocks of whole days inside each. Returns ``name -> array of AP replicates``
    in draw order, so ``a - b`` is a valid paired delta.
    """
    y = np.asarray(y, dtype=float)
    season = np.asarray(season)
    day = np.asarray(day)
    rng = np.random.default_rng(seed)

    seasons = np.unique(season)
    # index rows once per (season, day) so a replicate is a concatenation
    by_season = {}
    for s in seasons:
        m = season == s
        days = np.unique(day[m])
        by_season[s] = (days, {d: np.flatnonzero(m & (day == d)) for d in days})

    out = {k: np.empty(n_boot, dtype=float) for k in scores}
    for b in range(n_boot):
        drawn = rng.choice(seasons, size=len(seasons), replace=True)
        idx = []
        for s in drawn:
            days, index = by_season[s]
            for d in _circular_block_days(days, block, rng):
                idx.append(index[d])
        idx = np.concatenate(idx)
        yb = y[idx]
        # a replicate with one class carries no ranking information
        if yb.min() == yb.max():
            for k in out:
                out[k][b] = np.nan
            continue
        for k, v in scores.items():
            out[k][b] = average_precision_score(yb, np.asarray(v, dtype=float)[idx])
    return out


def percentile_ci(values, lo=2.5, hi=97.5):
    """Percentile interval, ignoring degenerate replicates."""
    v = np.asarray(values, dtype=float)
    v = v[np.isfinite(v)]
    if v.size == 0:
        return (float("nan"), float("nan"))
    return (float(np.percentile(v, lo)), float(np.percentile(v, hi)))


def delta_ci(boot, a, b, lo=2.5, hi=97.5):
    """Paired interval on AP(a) - AP(b), and the share of draws where a wins."""
    d = np.asarray(boot[a], dtype=float) - np.asarray(boot[b], dtype=float)
    d = d[np.isfinite(d)]
    if d.size == 0:
        return {"delta": float("nan"), "lo": float("nan"), "hi": float("nan"),
                "p_a_better": float("nan"), "n": 0}
    return {
        "delta": float(d.mean()),
        "lo": float(np.percentile(d, lo)),
        "hi": float(np.percentile(d, hi)),
        "p_a_better": float((d > 0).mean()),
        "n": int(d.size),
    }


def delete_one_season(y, scores, season):
    """Recompute AP with each season removed in turn.

    A bootstrap over four positive seasons can still be carried by one of them.
    This says so directly: if dropping a single season collapses a candidate's
    number, that candidate's skill is a claim about that season.
    """
    y = np.asarray(y, dtype=float)
    season = np.asarray(season)
    out = {}
    for s in np.unique(season):
        keep = season != s
        if y[keep].min() == y[keep].max():
            continue
        out[s] = {
            k: float(average_precision_score(y[keep], np.asarray(v, dtype=float)[keep]))
            for k, v in scores.items()
        }
    return out


def season_summary(y, scores, season):
    """Per-season AP, plus the mean and median across seasons that had floods.

    The pooled figure and the seasonal median answer different questions. A
    model can win pooled while losing the typical season, which is exactly the
    case here, so both get reported.
    """
    y = np.asarray(y, dtype=float)
    season = np.asarray(season)
    per = {}
    for s in np.unique(season):
        m = season == s
        if y[m].min() == y[m].max():
            continue
        per[s] = {
            k: float(average_precision_score(y[m], np.asarray(v, dtype=float)[m]))
            for k, v in scores.items()
        }
    agg = {}
    for k in scores:
        vals = np.array([per[s][k] for s in per], dtype=float)
        agg[k] = {"mean": float(vals.mean()), "median": float(np.median(vals))}
    return per, agg
