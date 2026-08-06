# sailaab/forecast_daily.py
"""Daily-issue flood forecasting: accumulations, climatology and forward labels.

The window forecaster asked a question no early-warning system asks: it scored a
ten-day box using rainfall drawn from inside that same box. This module supports
the question that matters instead. On each day of the monsoon, for each district
that is currently dry, using only what is known by the end of that day, will this
district be flooded within the next few days?

Three pieces live here, all pure transforms over tidy frames:

*Trailing accumulations.* Rain summed over the days up to and including the issue
date. Nothing after the issue date can enter a feature, which is what makes a
lead-time claim possible at all.

*Climatology percentiles.* 200 mm in three days means something different in
Gurdaspur in August than in Bathinda in September. Each accumulation is expressed
as its percentile within the same district's own 1961 to 2025 distribution for
the same part of the calendar, so the model sees "this is a 1-in-20-year three-day
fall here" rather than a raw millimetre count.

*Forward labels.* Whether the district crosses the flood threshold on any day in
the forecast horizon after the issue date.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def trailing_sums(
    daily: pd.DataFrame,
    windows=(1, 3, 7, 14),
    value_col: str = "rain_mm",
    key: str = "district",
    date_col: str = "date",
    prefix: str = "rain",
) -> pd.DataFrame:
    """Per-key trailing sums ending on each row's own date, inclusive.

    ``rain_3d`` on day t sums days t-2, t-1 and t. The sums are causal by
    construction: no value after t contributes.
    """
    d = daily.copy()
    d[date_col] = pd.to_datetime(d[date_col])
    d = d.sort_values([key, date_col]).reset_index(drop=True)
    g = d.groupby(key, sort=False)[value_col]
    for w in windows:
        d[f"{prefix}_{w}d"] = g.transform(
            lambda s, w=w: s.rolling(w, min_periods=1).sum()
        )
    return d


def _doy(dates: pd.Series) -> np.ndarray:
    """Day of year with Feb 29 folded onto Feb 28, so leap years line up."""
    dt = pd.to_datetime(dates)
    doy = dt.dt.dayofyear.to_numpy()
    leap = dt.dt.is_leap_year.to_numpy()
    return np.where(leap & (doy > 59), doy - 1, doy)


def build_climatology(
    climo_daily: pd.DataFrame,
    windows=(3, 7),
    halfwidth: int = 10,
    value_col: str = "rain_mm",
    key: str = "district",
    date_col: str = "date",
) -> dict:
    """Sorted historical accumulations per (key, day-of-year, window).

    For each calendar day the reference sample pools every year's values within
    ``halfwidth`` days either side, so a percentile is taken against the same
    part of the season rather than against the whole year.

    Returns ``{(key, window): (doy_index_array, list_of_sorted_arrays)}`` where
    entry ``i`` of the list is the sorted sample for day-of-year ``i + 1``.
    """
    d = trailing_sums(
        climo_daily, windows=windows, value_col=value_col, key=key, date_col=date_col
    )
    d["_doy"] = _doy(d[date_col])

    out = {}
    for name, grp in d.groupby(key, sort=True):
        doy = grp["_doy"].to_numpy()
        for w in windows:
            vals = grp[f"rain_{w}d"].to_numpy(dtype=float)
            samples = []
            for target in range(1, 367):
                lo, hi = target - halfwidth, target + halfwidth
                if lo < 1 or hi > 366:  # wrap across the year boundary
                    m = ((doy >= lo % 366) | (doy <= hi % 366)) if lo < 1 else (
                        (doy >= lo) | (doy <= hi % 366)
                    )
                else:
                    m = (doy >= lo) & (doy <= hi)
                s = vals[m]
                s = s[~np.isnan(s)]
                samples.append(np.sort(s))
            out[(name, w)] = samples
    return out


def climatology_percentile(
    frame: pd.DataFrame,
    climo: dict,
    windows=(3, 7),
    key: str = "district",
    date_col: str = "date",
) -> pd.DataFrame:
    """Add ``rain_<w>d_pctl``: where each accumulation sits in its own district's
    historical distribution for that point in the season, in [0, 1].

    A value at or above every historical observation scores 1.0. Districts or
    windows absent from the climatology yield NaN rather than a fabricated rank.
    """
    d = frame.copy()
    doy = _doy(d[date_col])
    for w in windows:
        col = f"rain_{w}d"
        out = np.full(len(d), np.nan)
        vals = d[col].to_numpy(dtype=float)
        names = d[key].to_numpy()
        for i in range(len(d)):
            samples = climo.get((names[i], w))
            if samples is None or np.isnan(vals[i]):
                continue
            s = samples[doy[i] - 1]
            if s.size == 0:
                continue
            out[i] = float(np.searchsorted(s, vals[i], side="right") / s.size)
        d[f"{col}_pctl"] = out
    return d


def forward_event(
    daily: pd.DataFrame,
    threshold: float,
    horizon: int = 3,
    value_col: str = "fraction",
    key: str = "district",
    date_col: str = "date",
    season_col: str | None = "year",
) -> pd.Series:
    """1 if ``value_col`` exceeds ``threshold`` on any day in ``[t+1, t+horizon]``.

    Strictly forward looking and strictly exclusive of the issue date, so the
    label can never be satisfied by water already visible when the forecast is
    made. Grouped within a season when ``season_col`` is given, so the end of one
    monsoon cannot borrow the start of the next. Rows whose horizon runs past the
    end of the available record yield NaN rather than a spurious 0.
    """
    d = daily.copy()
    d[date_col] = pd.to_datetime(d[date_col])
    keys = [key] + ([season_col] if season_col else [])
    d = d.sort_values(keys + [date_col])

    wet = (d[value_col] > threshold).astype(float)
    wet[d[value_col].isna()] = np.nan

    g = wet.groupby([d[k] for k in keys])
    shifted = [g.shift(-h) for h in range(1, horizon + 1)]
    stack = pd.concat(shifted, axis=1)
    any_wet = stack.max(axis=1, skipna=True)
    # a row is unusable only if the whole horizon is unavailable
    all_missing = stack.isna().all(axis=1)
    any_wet[all_missing] = np.nan
    return any_wet.reindex(daily.index if len(daily) == len(any_wet) else any_wet.index)


def dry_at_issue(
    frame: pd.DataFrame, threshold: float, value_col: str = "fraction"
) -> pd.Series:
    """Rows where the district is not already flooded when the forecast is made.

    Restricting to these is what separates forecasting an onset from noticing
    water that is already on the ground.
    """
    v = frame[value_col]
    return (v <= threshold) | v.isna()


def build_adjacency(geojson: dict, key: str = "district") -> dict:
    """District -> the districts whose polygons touch it.

    Flooding propagates between neighbouring districts along the rivers, so
    water already visible next door is genuine information about a district that
    is still dry. Adjacency is derived from the boundary layer itself rather
    than hand-listed, so it cannot drift out of step with the polygons.
    """
    from shapely.geometry import shape

    geoms = {f["properties"][key]: shape(f["geometry"]) for f in geojson["features"]}
    return {
        a: [b for b, gb in geoms.items() if b != a and ga.buffer(1e-9).intersects(gb)]
        for a, ga in geoms.items()
    }


def neighbour_water(
    daily,
    adjacency: dict,
    days: int = 3,
    value_col: str = "fraction",
    key: str = "district",
    date_col: str = "date",
) -> "pd.Series":
    """Max ``value_col`` over the last ``days`` in ADJACENT districts.

    The target district is strictly excluded, so any skill this carries is skill
    from the flood being visible somewhere else already, not a restatement of
    the district's own state.
    """
    d = daily.copy()
    d[date_col] = pd.to_datetime(d[date_col])
    d["_roll"] = (
        d.sort_values([key, date_col])
        .groupby(key, sort=False)[value_col]
        .transform(lambda s: s.rolling(days, min_periods=1).max())
    )
    wide = d.pivot_table(index=date_col, columns=key, values="_roll")
    out = pd.DataFrame(index=wide.index)
    for dist, nbrs in adjacency.items():
        cols = [n for n in nbrs if n in wide.columns]
        out[dist] = wide[cols].max(axis=1) if cols else np.nan
    long = out.stack().rename("neighbour_water").reset_index()
    long.columns = [date_col, key, "neighbour_water"]
    merged = d.merge(long, on=[date_col, key], how="left")
    return merged["neighbour_water"]


def seasonal_onset_rate(
    train, label_col: str = "y", key: str = "district", season_col: str = "day_of_season"
):
    """Onset rate per district per week of season, from training rows only.

    This is the transparent hazard a learned model has to beat: it encodes which
    districts flood and when in the season, and nothing else.
    """
    t = train.copy()
    t["week"] = (t[season_col] // 7).astype(int)
    return (
        t.groupby([key, "week"])[label_col].mean().rename("season_climo").reset_index()
    )
