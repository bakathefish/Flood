# sailaab/rain_districts.py
"""District-resolved rainfall from the IMD 0.25 degree daily grid.

Why this module exists
----------------------
The forecaster's original rain predictors were area-means over two fixed
bounding boxes (``punjab_mm``, ``upstream_mm``), so every district in a given
window received the *same* rainfall number. Combined with statewide reservoir
columns and a time-constant district prior, that left ``antecedent_fraction``
as the only predictor varying across both district and window, which is exactly
the persistence baseline the model was measured against. This module gives each
district its own rainfall series so the model has district-specific weather to
learn from.

Scope: pure numpy/pandas/shapely transforms, no IO and no netCDF reader. The
``.grd`` reading lives in ``pipeline/fetch_rain_districts.py``, mirroring the
split between ``sailaab.rain`` and ``pipeline/fetch_rain.py``.

Conventions
-----------
* Grid cells are centred on the supplied ``lats``/``lons`` and span
  ``cell_deg`` degrees, i.e. centre +/- ``cell_deg / 2``.
* A district's value is the area-weighted mean of the cells it overlaps.
  Weights are intersection area in degrees scaled by ``cos(latitude)``, which
  corrects for meridian convergence, then normalised to sum to 1 per district.
  Area weighting matters here because Punjab districts are comparable in size
  to a single 0.25 degree cell, so several districts contain no cell centre at
  all and a centroid-in-cell rule would drop them.
* Windows are half-open ``[start, end)``, identical to ``sailaab.rain`` and
  ``sailaab.windows``, so adjacent windows never double-count the seam day.
* Missing cells (IMD no-data) are skipped and the remaining weights are
  renormalised; a district whose cells are all missing yields NaN rather than a
  value biased toward zero.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from shapely.geometry import box, shape


def build_cell_weights(
    lats,
    lons,
    polygons: dict,
    cell_deg: float = 0.25,
) -> dict:
    """Area-overlap weights mapping grid cells to districts.

    Parameters
    ----------
    lats, lons:
        1-D arrays of grid-cell centre coordinates, in degrees.
    polygons:
        ``{district_name: geojson_geometry}``; Polygon and MultiPolygon both
        supported.
    cell_deg:
        Grid spacing in degrees; each cell spans its centre +/- ``cell_deg/2``.

    Returns
    -------
    ``{district_name: (idx, weights)}`` where ``idx`` is a list of
    ``(lat_index, lon_index)`` tuples and ``weights`` is a float array summing
    to 1.

    Raises
    ------
    ValueError
        If a district overlaps no grid cell at all. That is a coordinate-system
        or extent mistake, and silently returning NaN would hide it.
    """
    lats = np.asarray(lats, dtype=float)
    lons = np.asarray(lons, dtype=float)
    half = float(cell_deg) / 2.0

    out = {}
    for name, geom in polygons.items():
        poly = shape(geom)
        # Only test cells whose centres lie within one cell of the polygon
        # bounds; the full product is cheap for Punjab but this keeps the
        # helper usable on larger grids.
        minx, miny, maxx, maxy = poly.bounds
        lat_sel = np.where((lats >= miny - cell_deg) & (lats <= maxy + cell_deg))[0]
        lon_sel = np.where((lons >= minx - cell_deg) & (lons <= maxx + cell_deg))[0]

        idx, wts = [], []
        for i in lat_sel:
            coslat = float(np.cos(np.deg2rad(lats[i])))
            for j in lon_sel:
                cell = box(
                    lons[j] - half, lats[i] - half, lons[j] + half, lats[i] + half
                )
                inter = poly.intersection(cell).area
                if inter <= 0.0:
                    continue
                idx.append((int(i), int(j)))
                wts.append(inter * coslat)

        if not idx:
            raise ValueError(f"district {name!r} has no overlapping grid cells")

        w = np.asarray(wts, dtype=float)
        out[name] = (idx, w / w.sum())
    return out


def apply_weights(grid: np.ndarray, idx, weights) -> float:
    """Weighted mean of ``grid`` over the given cells.

    Cells holding NaN are dropped and the surviving weights are renormalised,
    so a partially masked district reports the mean of the cells that reported
    rather than a value pulled toward zero. All-missing yields NaN.
    """
    ii = np.asarray(idx).reshape(-1, 2)
    w = np.asarray(weights, dtype=float)
    vals = grid[ii[:, 0], ii[:, 1]].astype(float)
    ok = ~np.isnan(vals)
    if not ok.any():
        return float("nan")
    w_ok = w[ok]
    total = w_ok.sum()
    if total <= 0:
        return float("nan")
    return float(np.dot(vals[ok], w_ok) / total)


def district_daily_frame(dates, cube: np.ndarray, weights: dict) -> pd.DataFrame:
    """Tidy ``date, district, rain_mm`` frame from a ``(time, lat, lon)`` cube."""
    cube = np.asarray(cube, dtype=float)
    dates = pd.to_datetime(pd.Index(dates))
    if len(dates) != cube.shape[0]:
        raise ValueError(
            f"length mismatch: {len(dates)} dates vs {cube.shape[0]} time steps"
        )

    stamps = dates.strftime("%Y-%m-%d")
    rows = []
    for name, (idx, w) in weights.items():
        for t, day in enumerate(stamps):
            rows.append(
                {
                    "date": day,
                    "district": name,
                    "rain_mm": apply_weights(cube[t], idx, w),
                }
            )
    return pd.DataFrame(rows, columns=["date", "district", "rain_mm"])


def district_window_table(
    daily: pd.DataFrame,
    windows,
    lags: int = 2,
    value_col: str = "rain_mm",
    out_col: str = "district_mm",
) -> pd.DataFrame:
    """Per-district window sums plus ``lags`` antecedent-window sums.

    ``windows`` is an iterable of ``(start, end)`` half-open date pairs. Each
    lag-k column re-sums the daily frame over the window shifted back by
    ``k * (end - start)`` days, so a lag is a real accumulation rather than a
    table row-shift and is well defined for the first window of a season.
    Windows with no rows yield NaN.
    """
    d = daily.copy()
    d["_date"] = pd.to_datetime(d["date"])
    rows = []
    for start, end in windows:
        s, e = pd.Timestamp(start), pd.Timestamp(end)
        span = e - s
        for name, grp in d.groupby("district", sort=True):
            rec = {
                "district": name,
                "year": int(s.year),
                "window_start": s.strftime("%Y-%m-%d"),
                "window_end": e.strftime("%Y-%m-%d"),
            }
            for k in range(0, lags + 1):
                ks, ke = s - k * span, e - k * span
                sub = grp.loc[(grp["_date"] >= ks) & (grp["_date"] < ke), value_col]
                col = out_col if k == 0 else f"{out_col}_lag{k}"
                rec[col] = float(sub.sum(min_count=1))
            rows.append(rec)
    cols = ["district", "year", "window_start", "window_end", out_col] + [
        f"{out_col}_lag{k}" for k in range(1, lags + 1)
    ]
    return pd.DataFrame(rows, columns=cols)


def add_api(daily: pd.DataFrame, k: float = 0.9) -> pd.DataFrame:
    """Antecedent Precipitation Index per district.

    ``API_t = rain_t + k * API_{t-1}``, the standard recursive wetness proxy.
    It carries how saturated the ground already was into the next storm, which
    a fixed 10-day window sum cannot express: 100 mm falling on dry ground and
    100 mm falling on ground that was soaked last week are the same window sum
    but very different flood risk.

    ``k`` is the daily retention coefficient and must lie in ``(0, 1)``.
    """
    if not (0.0 < float(k) < 1.0):
        raise ValueError(f"k must be in (0, 1), got {k}")
    d = daily.copy()
    d["_date"] = pd.to_datetime(d["date"])
    d = d.sort_values(["district", "_date"])

    api = np.empty(len(d), dtype=float)
    pos = 0
    for _, grp in d.groupby("district", sort=False):
        acc = 0.0
        for r in grp["rain_mm"].to_numpy(dtype=float):
            acc = (0.0 if np.isnan(r) else r) + float(k) * acc
            api[pos] = acc
            pos += 1
    d["api_mm"] = api
    return d.drop(columns="_date").reset_index(drop=True)
