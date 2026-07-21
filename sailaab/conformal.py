# sailaab/conformal.py
"""Split-conformal prediction intervals for the forecaster regression head.

Pure numpy — no IO, no model fitting. Turns leave-one-year-out out-of-fold
residuals of the flooded-``fraction`` regressor into calibrated, marginally-valid
prediction intervals. The point estimates and residuals are produced upstream by
the LOYO harness (``sailaab.model`` folds); this module only does the conformal
calibration and coverage bookkeeping.

Split-conformal recap (Vovk; Lei et al. 2018): with ``n`` exchangeable calibration
nonconformity scores, the interval ``[ŷ − q, ŷ + q]`` where ``q`` is the
``⌈(n+1)(1−α)⌉``-th smallest score has marginal coverage ``≥ 1−α``. Here the score
is the absolute residual ``|y − ŷ|`` (symmetric, homoscedastic-ish intervals).

The :func:`loyo_conformal` helper makes calibration **leave-one-year-out honest**:
each year's intervals use ``q`` from the *other* years' OOF residuals, so no row is
calibrated on its own residual.
"""

from __future__ import annotations

import numpy as np


def conformal_quantile(residuals, coverage: float) -> float:
    """Finite-sample split-conformal radius for a target ``coverage`` in (0, 1).

    Returns the ``⌈(n+1)·coverage⌉``-th smallest finite residual. If that rank
    exceeds ``n`` (too few calibration points to guarantee the level), returns
    ``+inf`` — an honest "cannot certify a finite interval".
    """
    r = np.asarray(residuals, dtype=float)
    r = np.sort(r[~np.isnan(r)])
    n = r.size
    if n == 0:
        return float("nan")
    k = int(np.ceil((n + 1) * coverage))
    if k > n:
        return float("inf")
    return float(r[k - 1])  # k-th smallest, 1-indexed


def split_conformal_intervals(pred, q: float, lo_clip=None, hi_clip=None):
    """Symmetric intervals ``[pred − q, pred + q]``, optionally clamped.

    Clamping to a physical range (e.g. ``[0, 1]`` for a fraction) is
    coverage-preserving whenever the truth lies in that range.
    """
    pred = np.asarray(pred, dtype=float)
    lo = pred - q
    hi = pred + q
    if lo_clip is not None:
        lo = np.maximum(lo, lo_clip)
    if hi_clip is not None:
        hi = np.minimum(hi, hi_clip)
    return lo, hi


def empirical_coverage(y_true, lo, hi) -> float:
    """Fraction of ``y_true`` inside ``[lo, hi]`` (inclusive)."""
    y = np.asarray(y_true, dtype=float)
    lo = np.asarray(lo, dtype=float)
    hi = np.asarray(hi, dtype=float)
    if y.size == 0:
        return float("nan")
    return float(np.mean((y >= lo) & (y <= hi)))


def loyo_conformal(
    years,
    y_true,
    y_pred,
    coverage_levels=(0.80, 0.95),
    lo_clip=None,
    hi_clip=None,
) -> dict:
    """Leave-one-year-out honest split-conformal intervals.

    For each unique value in ``years`` the conformal radius is calibrated on the
    absolute OOF residuals of *all other* years, then applied to that year's own
    ``y_pred``. Returns ``{coverage: {"lo": array, "hi": array,
    "q_by_year": {year: q}}}`` with ``lo``/``hi`` aligned to the input row order.
    """
    years = np.asarray(years)
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    resid = np.abs(y_true - y_pred)

    out = {}
    for cov in coverage_levels:
        lo = np.full(years.shape, np.nan)
        hi = np.full(years.shape, np.nan)
        q_by_year = {}
        for y in np.unique(years):
            test = years == y
            cal = ~test
            q = conformal_quantile(resid[cal], cov)
            q_by_year[_as_key(y)] = q
            lo[test], hi[test] = split_conformal_intervals(
                y_pred[test], q, lo_clip=lo_clip, hi_clip=hi_clip
            )
        out[cov] = {"lo": lo, "hi": hi, "q_by_year": q_by_year}
    return out


def _as_key(y):
    """JSON/plain-key-friendly scalar (numpy int/str -> python int/str)."""
    try:
        return int(y)
    except (TypeError, ValueError):
        return str(y)
