# sailaab/forecast_v2.py
"""Fold-safe priors and warning-shaped metrics for the district forecaster.

Two problems with the first forecaster evaluation motivated this module.

*Leakage.* The district prior (mean annual flooded hectares, seasons above the
2% fraction) was computed once over 2015-2025 and joined before the
leave-one-year-out split, so every held-out year contributed to its own
features. :func:`fold_safe_prior` rebuilds the prior from the training years of
each fold, and the test suite pins the property that mutating a held-out year's
labels cannot move that fold's prior.

*Metric shape.* Pooled ROC-AUC flatters this problem badly: about three quarters
of the negatives come from years with no flood at all, so most positive-negative
comparisons only ask "was this a quiet year", not "which district flooded". The
operational question is a ranking one, since an agency can act on a handful of
districts per window. The helpers here score that directly: within-window
top-k recall, the false-alert burden carried in quiet windows, and Brier skill
against an explicit reference forecast. Year-block bootstrap intervals are
provided because the sample contains only three event years, and resampling
rows rather than years would badly understate the uncertainty.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from sailaab import config


def fold_safe_prior(
    df: pd.DataFrame,
    train_years,
    threshold: float = config.FLOOD_EVENT_FRACTION,
) -> pd.DataFrame:
    """District prior computed from ``train_years`` only.

    Returns one row per district present anywhere in ``df`` (so a fold never
    drops a district merely because it stayed dry during training), with
    ``prior_mean_annual_flooded_ha`` and ``prior_seasons_with_fraction_gt2pct``.
    """
    train_years = list(train_years)
    if not train_years:
        raise ValueError("no training years supplied; the prior would be empty")

    districts = pd.Index(sorted(df["district"].unique()), name="district")
    tr = df[df["year"].isin(train_years)]

    per_year = tr.groupby(["district", "year"], sort=True).agg(
        season_ha=("flooded_ha", "sum"),
        season_max_fraction=("flooded_fraction", "max"),
    )
    mean_ha = per_year.groupby("district")["season_ha"].mean()
    seasons = (
        (per_year["season_max_fraction"] > threshold).groupby("district").sum()
    )

    out = pd.DataFrame(index=districts)
    out["prior_mean_annual_flooded_ha"] = mean_ha.reindex(districts).fillna(0.0)
    out["prior_seasons_with_fraction_gt2pct"] = (
        seasons.reindex(districts).fillna(0).astype(int)
    )
    return out.reset_index()


def group_topk(y_true, prob, groups, k: int = 5) -> pd.DataFrame:
    """Per-group top-k hit table.

    One row per group (a group is normally one year x window, i.e. the set of
    districts competing for the same alert budget) with the number of positives,
    how many of them fall in the top ``k`` by score, and the resulting
    precision and recall. ``k_used`` records the clamp when a group holds fewer
    than ``k`` members.

    Ties are broken by ascending index rather than by label, so a model that
    separates nothing cannot score as if it ranked perfectly.
    """
    y = np.asarray(y_true, dtype=float)
    p = np.asarray(prob, dtype=float)
    g = np.asarray(groups)
    if not (len(y) == len(p) == len(g)):
        raise ValueError("y_true, prob and groups must be the same length")

    rows = []
    for name in pd.unique(g):
        m = g == name
        yy, pp = y[m], p[m]
        n = len(yy)
        kk = int(min(k, n))
        # stable sort on -score keeps original order within ties
        order = np.argsort(-np.nan_to_num(pp, nan=-np.inf), kind="stable")
        top = order[:kk]
        n_pos = int(np.nansum(yy))
        hits = int(np.nansum(yy[top]))
        rows.append(
            {
                "group": name,
                "n": n,
                "k_used": kk,
                "n_pos": n_pos,
                "hits": hits,
                "precision_at_k": hits / kk if kk else np.nan,
                "recall_at_k": hits / n_pos if n_pos else np.nan,
            }
        )
    return pd.DataFrame(rows)


def recall_at_k(y_true, prob, groups, k: int = 5) -> float:
    """Share of positives captured by a top-k alert budget, over groups that
    actually contained a positive. Groups with no positive have undefined
    recall and are excluded rather than scored as 0 or 1."""
    t = group_topk(y_true, prob, groups, k=k)
    ev = t[t["n_pos"] > 0]
    if ev.empty:
        return float("nan")
    return float(ev["hits"].sum() / ev["n_pos"].sum())


def quiet_window_alert_rate(y_true, prob, groups, threshold: float = 0.5) -> float:
    """Fraction of district-windows alerted inside groups that had no flood.

    This is the cost side of any recall gain: how much crying wolf the operating
    point buys. NaN when every group contained a positive.
    """
    y = np.asarray(y_true, dtype=float)
    p = np.asarray(prob, dtype=float)
    g = np.asarray(groups)
    quiet = np.zeros(len(y), dtype=bool)
    for name in pd.unique(g):
        m = g == name
        if np.nansum(y[m]) == 0:
            quiet |= m
    if not quiet.any():
        return float("nan")
    pq = p[quiet]
    valid = ~np.isnan(pq)
    if not valid.any():
        return float("nan")
    return float(np.mean(pq[valid] >= threshold))


def brier_skill(y_true, prob, reference) -> float:
    """Brier skill score against an explicit reference forecast.

    Positive means better than the reference, 0 means identical, negative means
    worse. Reporting skill against fold-training climatology and against
    persistence is more informative than a bare Brier score, which is dominated
    by the 1.75% base rate.
    """
    y = np.asarray(y_true, dtype=float)
    p = np.asarray(prob, dtype=float)
    r = np.asarray(reference, dtype=float)
    ok = ~(np.isnan(y) | np.isnan(p) | np.isnan(r))
    if not ok.any():
        return float("nan")
    bs = np.mean((p[ok] - y[ok]) ** 2)
    ref = np.mean((r[ok] - y[ok]) ** 2)
    if ref == 0:
        return float("nan")
    return float(1.0 - bs / ref)


def block_bootstrap_ci(
    values_by_year: dict,
    n: int = 2000,
    seed: int = 0,
    alpha: float = 0.05,
) -> tuple[float, float]:
    """Percentile interval from resampling whole YEARS with replacement.

    The rows within a season are not independent: one storm drives many
    district-windows at once. Resampling rows would therefore produce an
    interval far too narrow. Resampling years respects that block structure.
    With only a handful of event years the interval is descriptive, not a
    calibrated confidence statement, and should be reported as such.
    """
    years = sorted(values_by_year)
    if len(years) < 2:
        raise ValueError("need at least 2 year blocks to bootstrap")
    blocks = [np.asarray(values_by_year[y], dtype=float) for y in years]
    rng = np.random.default_rng(seed)
    stats = np.empty(n, dtype=float)
    for i in range(n):
        pick = rng.integers(0, len(blocks), size=len(blocks))
        pooled = np.concatenate([blocks[j] for j in pick])
        pooled = pooled[~np.isnan(pooled)]
        stats[i] = np.mean(pooled) if pooled.size else np.nan
    lo = float(np.nanpercentile(stats, 100 * alpha / 2))
    hi = float(np.nanpercentile(stats, 100 * (1 - alpha / 2)))
    return lo, hi
