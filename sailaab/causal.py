# sailaab/causal.py
"""Pure, testable helpers for the Wave-3 *causal* figure (``atlas/causal_2025.png``).

The figure tells the 2025 flood's causal chain: extreme upstream rain -> already
near-full reservoirs -> forced releases -> downstream inundation. This module
holds only the deterministic data transforms behind it (no plotting, no I/O):

* :func:`pct_of_live_capacity` - storage (BCM) as a percent of a dam's live
  capacity, so Bhakra / Pong / Ranjit Sagar (very different absolute capacities)
  share one 0-100 % axis and 100 % reads as "brim-full / FRL".
* :func:`same_day_climatology` - the 2015-2024 same-calendar-day quantile band
  used behind the 2025 rainfall trace ("normal" range for contrast).

Constants (live capacity, FRL / danger levels) are sourced from
``docs/notes/reservoirs.md`` (CWC via data.gov.in field ``Live_capacity_FRL`` and
the BBMB-reported danger levels), kept here so the figure's annotations reference
named values rather than magic numbers.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

import numpy as np
import pandas as pd

# Live capacity at FRL, in BCM (billion m3). Source: CWC daily reservoir feed
# (data.gov.in), field Live_capacity_FRL; see docs/notes/reservoirs.md.
LIVE_CAPACITY_BCM: dict[str, float] = {
    "Bhakra": 6.229,
    "Pong": 6.157,
    "Ranjit Sagar": 2.344,
}

# Full Reservoir Level in feet (Bhakra/Pong are reported in feet by BBMB during
# the flood window; the stated danger levels coincide with FRL).
FRL_FT: dict[str, float] = {
    "Bhakra": 1680.0,
    "Pong": 1390.0,
}

# Full Reservoir Level in metres (CWC field Full_reservoir_level).
FRL_M: dict[str, float] = {
    "Bhakra": 512.06,
    "Pong": 423.67,
    "Ranjit Sagar": 527.91,
}


def pct_of_live_capacity(storage_bcm, dam: str):
    """Return ``storage_bcm`` as a percent of ``dam``'s live capacity.

    Accepts a scalar or any array-like / ``pandas`` object (vectorized). At FRL
    (storage == live capacity) the result is 100.0. Raises ``KeyError`` for an
    unknown dam name so a typo never silently yields ``NaN``.
    """
    cap = LIVE_CAPACITY_BCM[dam]
    return storage_bcm / cap * 100.0


def same_day_climatology(
    daily: pd.DataFrame,
    value_cols: Sequence[str],
    prior_years: Iterable[int],
    target_dates,
    quantiles: Sequence[float] = (0.1, 0.5, 0.9),
    date_col: str = "date",
) -> pd.DataFrame:
    """Same-calendar-day quantiles across ``prior_years``, aligned to ``target_dates``.

    For each requested quantile ``q`` and column ``col`` the result carries a
    column ``f"{col}_p{round(q*100)}"`` giving, for every date in
    ``target_dates``, the ``q``-quantile of ``col`` over the rows of ``daily``
    whose year is in ``prior_years`` and whose (month, day) matches that target
    date. A target (month, day) absent from the priors - e.g. 29 Feb against
    non-leap priors - yields ``NaN`` for that day rather than raising.

    Parameters
    ----------
    daily : DataFrame with a datetime-coercible ``date_col`` and ``value_cols``.
    value_cols : columns to summarize (e.g. ``["upstream_mm", "punjab_mm"]``).
    prior_years : reference years (e.g. ``range(2015, 2025)``).
    target_dates : the calendar the band is aligned to (e.g. the 2025 season).
    quantiles : quantiles in [0, 1]; ``0.5`` is the median.

    Returns
    -------
    DataFrame indexed by ``pd.DatetimeIndex(target_dates)``.
    """
    df = daily.copy()
    df[date_col] = pd.to_datetime(df[date_col])
    years = list(prior_years)
    prior = df[df[date_col].dt.year.isin(years)]

    md = pd.MultiIndex.from_arrays(
        [prior[date_col].dt.month, prior[date_col].dt.day], names=["_m", "_d"]
    )
    prior = prior.set_index(md)

    target = pd.DatetimeIndex(target_dates)
    target_md = list(zip(target.month, target.day))

    out = pd.DataFrame(index=target)
    for q in quantiles:
        pct = int(round(q * 100))
        # quantile per (month, day) group, one column per value col
        qframe = prior.groupby(level=["_m", "_d"])[list(value_cols)].quantile(q)
        for col in value_cols:
            series = qframe[col]
            out[f"{col}_p{pct}"] = [series.get(key, np.nan) for key in target_md]
    return out
