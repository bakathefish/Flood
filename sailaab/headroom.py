# sailaab/headroom.py
"""Pure, testable math for the dam-headroom analysis (``atlas/headroom_2025.png``).

Quantifies the *management component* of the 2025 Punjab flood as **arithmetic on
storage curves** - how many BCM *less* pre-positioned empty storage (headroom)
Bhakra / Pong / Ranjit Sagar held on the eve of the flood than the **median of
their own 2015-2024 practice** would have provided on the same day-of-season. It
is deliberately *not* a hydraulic or routing simulation.

The framing discipline (never "avoidable"; rain is the primary cause; legitimate
reasons dams fill early; SANDRP prior work; the 11-Jul reporting gap) lives in
``docs/notes/headroom.md``. This module holds only the deterministic transforms:

* :func:`season_day` - Jun 1 -> Sep 30 day-of-season index (leap-safe in season).
* :func:`median_fill_curve` - the 2015-2024 per-day-of-season quantile band
  (p25/p50/p75) with an honest ``n_years`` count per day.
* :func:`interp_no_extrap` - piecewise-linear splice of the sparse 2025 points,
  ``NaN`` outside their range (never extrapolated).
* :func:`rating_level_to_storage` - hypsometric level->storage estimate from a
  dam's own (level, storage) pairs, for Ranjit Sagar's level-only flood window.
* :func:`headroom_deficit` - ``storage_2025 - median`` in BCM and % points.
* :func:`cusecs_to_bcm_per_day` / :func:`absorbable_days` - the release-surge
  buffer arithmetic.

Live-capacity / FRL constants are reused from :mod:`sailaab.causal` (sourced from
``docs/notes/reservoirs.md``) rather than re-declared here.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

import numpy as np
import pandas as pd

from sailaab.causal import FRL_FT, FRL_M, LIVE_CAPACITY_BCM  # noqa: F401 (re-export)

# --- unit conversion: cubic-feet-per-second -> BCM/day ----------------------
# 1 cusec = 0.028316846592 m^3/s; * 86400 s/day = 2446.575 m^3/day;
# * 1e-9 BCM/m^3 = 2.446575e-6 BCM/day.
CUSEC_M3_PER_S = 0.028316846592
SECONDS_PER_DAY = 86_400
CUSEC_TO_BCM_PER_DAY = CUSEC_M3_PER_S * SECONDS_PER_DAY * 1.0e-9

# --- season window (matches the Jun 1 -> Sep 30 axis of the causal figure) ---
SEASON_START_MD = "06-01"
SEASON_END_MD = "09-30"


def season_day(dates, season_start_md: str = SEASON_START_MD):
    """Day-of-season offset: 0 on ``season_start_md`` of each date's own year.

    Scalar in -> ``int`` out; array-like / ``Series`` / ``DatetimeIndex`` in ->
    ``numpy.ndarray`` out. Leap-safe *within the monsoon season*: there is no
    29 Feb between Jun 1 and Sep 30, so a calendar day maps to the same
    day-of-season in every year.
    """
    dt = pd.to_datetime(dates)
    scalar = isinstance(dt, pd.Timestamp)
    idx = pd.DatetimeIndex([dt]) if scalar else pd.DatetimeIndex(dt)
    starts = pd.to_datetime([f"{y}-{season_start_md}" for y in idx.year])
    doy = (idx.normalize() - starts).days.to_numpy()
    return int(doy[0]) if scalar else doy


def _season_len(season_start_md: str, season_end_md: str) -> int:
    ref = 2001  # any non-leap year; the season carries no 29 Feb anyway
    return int(
        (pd.Timestamp(f"{ref}-{season_end_md}") - pd.Timestamp(f"{ref}-{season_start_md}")).days
    )


def median_fill_curve(
    daily: pd.DataFrame,
    dam: str,
    prior_years: Iterable[int],
    value_col: str = "storage_value",
    season: tuple[str, str] = (SEASON_START_MD, SEASON_END_MD),
    quantiles: Sequence[float] = (0.25, 0.5, 0.75),
    date_col: str = "date",
    dam_col: str = "dam",
    as_pct_of: float | None = None,
) -> pd.DataFrame:
    """Per day-of-season quantiles of ``value_col`` across ``prior_years`` for ``dam``.

    Returns a DataFrame indexed by day-of-season (``0 .. season_len``, so 0..121
    for Jun 1 -> Sep 30) with columns ``month, day``, one column per quantile
    (``q25, q50, q75`` for the default quantiles), ``n_years`` (distinct prior
    years contributing that day) and ``n_obs`` (total readings). Days with no
    prior-year reading are still present, with ``NaN`` quantiles and
    ``n_years = 0`` - coverage is reported, never silently dropped. When
    ``as_pct_of`` (a live capacity in BCM) is given, ``<q>_pct`` columns are added.
    """
    years = {int(y) for y in prior_years}
    df = daily[[date_col, dam_col, value_col]].copy()
    df[date_col] = pd.to_datetime(df[date_col])
    df = df[(df[dam_col] == dam) & df[date_col].dt.year.isin(years)]
    df = df.dropna(subset=[value_col])
    df = df.assign(
        _doy=season_day(df[date_col], season[0]),
        _year=df[date_col].dt.year,
    )
    season_len = _season_len(season[0], season[1])
    df = df[(df["_doy"] >= 0) & (df["_doy"] <= season_len)]

    grp = df.groupby("_doy")
    out = pd.DataFrame(index=pd.RangeIndex(0, season_len + 1, name="doy"))
    qcols = []
    for q in quantiles:
        name = f"q{int(round(q * 100))}"
        out[name] = grp[value_col].quantile(q)
        qcols.append(name)
    out["n_years"] = grp["_year"].nunique()
    out["n_obs"] = grp[value_col].count()
    out["n_years"] = out["n_years"].fillna(0).astype(int)
    out["n_obs"] = out["n_obs"].fillna(0).astype(int)

    start = pd.Timestamp(f"2001-{season[0]}")
    labels = start + pd.to_timedelta(out.index.to_numpy(), unit="D")
    out.insert(0, "month", labels.month)
    out.insert(1, "day", labels.day)

    if as_pct_of is not None:
        for name in qcols:
            out[f"{name}_pct"] = out[name] / as_pct_of * 100.0
    return out


def interp_no_extrap(known_dates, known_values, target_dates) -> np.ndarray:
    """Piecewise-linear interpolation of ``known_values`` (dated) onto
    ``target_dates``; ``NaN`` for any target outside the ``[min, max]`` span of
    the known dates. Never extrapolates. Known points need not be pre-sorted.
    """
    kd = pd.DatetimeIndex(pd.to_datetime(known_dates))
    kv = np.asarray(known_values, dtype=float)
    order = np.argsort(kd.values)
    kx = kd.values[order].astype("datetime64[ns]").astype("int64").astype(float)
    kv = kv[order]
    tx = (
        pd.DatetimeIndex(pd.to_datetime(target_dates))
        .values.astype("datetime64[ns]")
        .astype("int64")
        .astype(float)
    )
    out = np.interp(tx, kx, kv)
    out[(tx < kx[0]) | (tx > kx[-1])] = np.nan
    return out


def rating_level_to_storage(
    daily: pd.DataFrame,
    dam: str,
    levels,
    prior_years: Iterable[int] | None = None,
    level_col: str = "level_m",
    storage_col: str = "storage_value",
    dam_col: str = "dam",
    date_col: str = "date",
) -> np.ndarray:
    """Hypsometric estimate: map reservoir ``levels`` to storage (BCM) via the
    dam's own ``(level, storage)`` pairs (monotone linear interpolation on sorted
    levels). Levels outside the observed range clamp to the nearest observed
    storage (``numpy.interp`` semantics) - i.e. no vertical extrapolation. Used
    for Ranjit Sagar, whose Aug-Sep 2025 flood window was reported in levels only.
    """
    df = daily[daily[dam_col] == dam].copy()
    if prior_years is not None:
        yrs = {int(y) for y in prior_years}
        df = df[pd.to_datetime(df[date_col]).dt.year.isin(yrs)]
    df = df[[level_col, storage_col]].dropna()
    x = df[level_col].to_numpy(dtype=float)
    y = df[storage_col].to_numpy(dtype=float)
    order = np.argsort(x)
    return np.interp(np.asarray(levels, dtype=float), x[order], y[order])


def headroom_deficit(storage_2025_bcm, median_bcm, live_cap_bcm: float):
    """``(deficit_bcm, deficit_pctpts)``.

    ``deficit_bcm = storage_2025 - median``: **positive => 2025 fuller than the
    decade median => less pre-positioned headroom**. ``deficit_pctpts`` expresses
    the same gap as percentage points of live capacity. Scalar or vectorized.
    """
    deficit = storage_2025_bcm - median_bcm
    return deficit, deficit / live_cap_bcm * 100.0


def cusecs_to_bcm_per_day(cusecs):
    """Convert a release/inflow in cusecs to BCM/day. Scalar in -> ``float`` out."""
    out = np.asarray(cusecs, dtype=float) * CUSEC_TO_BCM_PER_DAY
    return float(out) if out.ndim == 0 else out


def absorbable_days(deficit_bcm, surge_cusecs):
    """Days the missing headroom (``deficit_bcm``) would absorb a sustained
    ``surge_cusecs`` inflow at that dam's peak documented throughput:
    ``deficit_bcm / (surge_cusecs * CUSEC_TO_BCM_PER_DAY)``. An order-of-magnitude
    buffer, not a routing result - see the assumptions in ``docs/notes/headroom.md``.
    """
    rate = np.asarray(surge_cusecs, dtype=float) * CUSEC_TO_BCM_PER_DAY
    return deficit_bcm / rate
