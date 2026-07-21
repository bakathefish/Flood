# sailaab/rain.py
"""Rainfall window aggregation for the forecaster (Wave 4), pure pandas/numpy.

Consumes a *daily area-mean* frame (one row per calendar day) with box columns
``punjab_mm`` (local Punjab plains) and ``upstream_mm`` (Sutlej/Beas/Ravi Indian
Himalayan catchments), and reduces it to window sums and lagged window sums that
become forecaster predictors.

No xarray / rasterio here — the grid->box extraction lives in
``pipeline/fetch_rain.py``. This module only sees the daily table, so it stays
fast and unit-testable on synthetic frames.

Conventions
-----------
* Windows are **half-open** ``[start, end)`` — identical to
  :func:`sailaab.windows.monsoon_windows` and GEE ``filterDate``, so adjacent
  windows never double-count the seam day and box sums line up 1:1 with the
  decade grid.
* A "lag-k window" is the current window shifted back in calendar time by
  ``k * (end - start)`` days — i.e. antecedent precipitation over the preceding
  window(s). For the contiguous equal-length monsoon windows this is exactly the
  previous grid window; it is computed by re-summing the daily frame, so it is a
  real physical quantity (not a table row-shift) and is well defined even for the
  first window of a season.
* Sums use ``min_count=1``: a window with no rows (e.g. a lag reaching before the
  data starts) or only missing days is ``NaN`` — a gradient-boosted forecaster
  ingests that directly.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from sailaab.windows import monsoon_windows

DEFAULT_BOX_COLS = ("punjab_mm", "upstream_mm")


def window_sum(
    daily: pd.DataFrame,
    start,
    end,
    cols: tuple[str, ...] = DEFAULT_BOX_COLS,
    date_col: str = "date",
) -> dict[str, float]:
    """Summed mm per box over the half-open window ``[start, end)``.

    ``start``/``end`` may be ISO strings or anything ``pd.Timestamp`` accepts.
    Empty / all-missing windows yield ``NaN`` for that box.
    """
    start_ts, end_ts = pd.Timestamp(start), pd.Timestamp(end)
    dates = pd.to_datetime(daily[date_col])
    mask = (dates >= start_ts) & (dates < end_ts)
    sub = daily.loc[mask]
    return {c: float(sub[c].sum(min_count=1)) for c in cols}


def window_with_lags(
    daily: pd.DataFrame,
    start,
    end,
    lags: int = 2,
    cols: tuple[str, ...] = DEFAULT_BOX_COLS,
    date_col: str = "date",
) -> dict[str, float]:
    """Current window sum per box plus ``lags`` antecedent-window sums.

    Returns a flat dict ``{col, ..., col_lag1, ..., col_lag2, ...}`` where each
    ``col_lagk`` sums the daily frame over ``[start - k*L, end - k*L)`` with
    ``L = (end - start)`` days.
    """
    start_ts, end_ts = pd.Timestamp(start), pd.Timestamp(end)
    length = pd.Timedelta(days=(end_ts - start_ts).days)
    out = dict(window_sum(daily, start_ts, end_ts, cols, date_col))
    for k in range(1, lags + 1):
        shift = length * k
        lag = window_sum(daily, start_ts - shift, end_ts - shift, cols, date_col)
        for c in cols:
            out[f"{c}_lag{k}"] = lag[c]
    return out


def window_table(
    daily: pd.DataFrame,
    years: list[int],
    lags: int = 2,
    cols: tuple[str, ...] = DEFAULT_BOX_COLS,
    date_col: str = "date",
) -> pd.DataFrame:
    """Per-monsoon-window box sums + lags for ``years``, using the SAME windows
    as :func:`sailaab.windows.monsoon_windows` (the decade grid).

    Columns: ``year, window_start, window_end, <cols>, <cols>_lag1, ..._lagN``.
    """
    rows = []
    for y in years:
        for w0, w1 in monsoon_windows(y):
            feats = window_with_lags(daily, w0, w1, lags, cols, date_col)
            rows.append({"year": y, "window_start": w0, "window_end": w1, **feats})
    lag_cols = [f"{c}_lag{k}" for k in range(1, lags + 1) for c in cols]
    ordered = ["year", "window_start", "window_end", *cols, *lag_cols]
    return pd.DataFrame(rows, columns=ordered)


def anomaly_stats(prior_values, target: float) -> dict[str, float]:
    """Locate ``target`` (e.g. the 2025 window sum) within the distribution of
    ``prior_values`` (the 2015-2024 same-window sums).

    Returns ``n, mean, std, z, percentile, rank, max_prior, ratio_to_mean``:
    * ``z``          = (target - mean) / sample std (ddof=1); ``NaN`` if <2 priors
                       or zero spread.
    * ``percentile`` = 100 * fraction of priors <= target (100 => beats every
                       prior year).
    * ``rank``       = 1 for the largest (1 + count of priors strictly above).
    * ``ratio_to_mean`` = target / mean (``(ratio-1)*100`` is the % anomaly).
    """
    arr = np.asarray(list(prior_values), dtype=float)
    arr = arr[~np.isnan(arr)]
    n = int(arr.size)
    if n == 0:
        raise ValueError("anomaly_stats needs at least one non-NaN prior value")
    mean = float(np.mean(arr))
    std = float(np.std(arr, ddof=1)) if n > 1 else float("nan")
    z = float((target - mean) / std) if std and not np.isnan(std) else float("nan")
    percentile = float(100.0 * np.count_nonzero(arr <= target) / n)
    rank = int(1 + np.count_nonzero(arr > target))
    max_prior = float(np.max(arr))
    ratio_to_mean = float(target / mean) if mean != 0 else float("nan")
    return {
        "n": n,
        "mean": mean,
        "std": std,
        "z": z,
        "percentile": percentile,
        "rank": rank,
        "max_prior": max_prior,
        "ratio_to_mean": ratio_to_mean,
    }
