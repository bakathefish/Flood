# pipeline/fetch_era5_intensity.py
"""Sub-daily rainfall-intensity features for the forecaster challenger.

Pulls **hourly** precipitation from the Open-Meteo **ERA5 archive** (keyless,
``archive-api.open-meteo.com``) for the same two boxes and 3x3 cos(lat)-weighted
point grids as ``pipeline/fetch_live_inputs.py``, 2015-2025, then reduces each
box to one area-mean hourly series and derives three intensity metrics per 10-day
monsoon window (same window grid as the decade run, ``sailaab.windows``):

* ``*_max_3h_mm``   — max rolling 3-hour area-mean rainfall sum in the window
* ``*_max_24h_mm``  — max rolling 24-hour area-mean rainfall sum in the window
* ``*_hours_ge5mm`` — count of hours in the window with area-mean rain >= 5 mm

= 6 columns (3 metrics x 2 boxes). The raw hourly API responses are cached under
``data/rasters/era5/`` (gitignored, ~one JSON per box-year); the derived per-window
table is committed as ``data/rain_intensity_windows.csv`` and merged on
``(year, window_start)`` by ``pipeline/run_challenger.py``.

Pure helpers (``area_mean_hourly``, ``rolling_max_sum``, ``window_intensity``) carry
no IO and are unit-tested in ``tests/test_era5_intensity.py``.

Usage:
    python -m pipeline.fetch_era5_intensity     # download-if-missing, write CSV
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from sailaab import config
from sailaab.windows import monsoon_windows

# Same boxes as pipeline/fetch_live_inputs.py (and pipeline/fetch_rain.py).
PUNJAB_BOX = {"lon": (73.85, 76.95), "lat": (29.53, 32.60)}  # Punjab plains
UPSTREAM_BOX = {"lon": (75.5, 78.6), "lat": (30.9, 33.3)}  # Sutlej/Beas/Ravi upstream
BOXES = {"punjab": PUNJAB_BOX, "upstream": UPSTREAM_BOX}

OM_ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"
UA = {"User-Agent": "sailaab-forecaster/1.0 (Punjab flood forecaster; keyless)"}

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
ERA5_DIR = DATA / "rasters" / "era5"
OUT_CSV = DATA / "rain_intensity_windows.csv"

INTENSITY_THRESHOLD_MM = 5.0  # hour counts as "intense" at >= this area-mean mm
METRICS = ["max_3h_mm", "max_24h_mm", "hours_ge5mm"]


# --------------------------------------------------------------------------- #
# pure helpers (no IO)
# --------------------------------------------------------------------------- #
def _grid_points(box, n: int = 3):
    """``n`` x ``n`` (lat, lon) point grid spanning the box edges (matches
    ``pipeline/fetch_live_inputs.py._grid_points``)."""
    lons = np.linspace(box["lon"][0], box["lon"][1], n)
    lats = np.linspace(box["lat"][0], box["lat"][1], n)
    return [(float(la), float(lo)) for la in lats for lo in lons]


def area_mean_hourly(loc_series, weights) -> dict:
    """cos(lat)-weighted area-mean per hour across a list of ``{time: mm}`` point
    series (missing points skipped). Returns ``{iso_hour: mm}``."""
    hours: set[str] = set()
    for s in loc_series:
        hours |= set(s)
    out = {}
    for h in hours:
        vals, ws = [], []
        for s, w in zip(loc_series, weights):
            v = s.get(h)
            if v is not None and not (isinstance(v, float) and np.isnan(v)):
                vals.append(float(v))
                ws.append(w)
        out[h] = float(np.average(vals, weights=ws)) if vals else float("nan")
    return out


def rolling_max_sum(vals, k: int) -> float:
    """Max sum of ``k`` contiguous values (NaN treated as 0.0). For fewer than
    ``k`` values the sum of all is returned; empty -> NaN."""
    v = np.asarray(vals, dtype=float)
    v = np.where(np.isnan(v), 0.0, v)
    n = len(v)
    if n == 0:
        return float("nan")
    if n < k:
        return float(v.sum())
    c = np.concatenate(([0.0], np.cumsum(v)))
    sums = c[k:] - c[:-k]
    return float(sums.max())


def window_intensity(hourly: dict, w0: str, w1: str) -> dict:
    """Three intensity metrics for the half-open window ``[w0, w1)`` from an
    ``{iso_hour: mm}`` area-mean series. Only hours whose calendar date lies in
    ``[w0, w1)`` are used, so there is no cross-window leakage."""
    d0, d1 = w0[:10], w1[:10]
    times = sorted(t for t in hourly if d0 <= t[:10] < d1)
    vals = [hourly[t] for t in times]
    arr = np.asarray(vals, dtype=float)
    finite = arr[~np.isnan(arr)]
    return {
        "max_3h_mm": round(rolling_max_sum(vals, 3), 3),
        "max_24h_mm": round(rolling_max_sum(vals, 24), 3),
        "hours_ge5mm": int(np.sum(finite >= INTENSITY_THRESHOLD_MM)),
    }


# --------------------------------------------------------------------------- #
# IO — fetch + cache
# --------------------------------------------------------------------------- #
def _fetch_box_year(box, year: int, timeout: int = 180, retries: int = 3):
    """One multi-location ERA5-archive call for a box's 9 points over the monsoon
    season -> list of ``{time: [...], precipitation: [...]}`` (one per point)."""
    points = _grid_points(box)
    params = {
        "latitude": ",".join(f"{la:.4f}" for la, _ in points),
        "longitude": ",".join(f"{lo:.4f}" for _, lo in points),
        "hourly": "precipitation",
        "start_date": f"{year}-{config.SEASON_START_MD}",
        "end_date": f"{year}-{config.SEASON_END_MD}",
        "timezone": "UTC",
    }
    last = None
    for attempt in range(retries):
        try:
            r = requests.get(OM_ARCHIVE, params=params, headers=UA, timeout=timeout)
            r.raise_for_status()
            j = r.json()
            if isinstance(j, dict):  # single location -> wrap
                j = [j]
            return [loc.get("hourly", {}) or {} for loc in j]
        except Exception as exc:  # pragma: no cover - network guard
            last = exc
            time.sleep(2.0 * (attempt + 1))
    raise RuntimeError(f"ERA5 fetch failed for {year}: {last!r}")


def _cached_box_year(box_name: str, box, year: int) -> list[dict]:
    """Raw per-point hourly series for a box-year, cached to
    ``data/rasters/era5/<box>_<year>.json``."""
    ERA5_DIR.mkdir(parents=True, exist_ok=True)
    path = ERA5_DIR / f"{box_name}_{year}.json"
    if path.exists():
        return json.loads(path.read_text())
    hourly_per_point = _fetch_box_year(box, year)
    path.write_text(json.dumps(hourly_per_point))
    time.sleep(1.0)  # be polite between live calls
    return hourly_per_point


def _box_hourly_mean(box_name: str, box, year: int) -> dict:
    """Area-mean ``{iso_hour: mm}`` series for a box-year."""
    per_point = _cached_box_year(box_name, box, year)
    loc_series = [
        dict(zip(h.get("time", []) or [], h.get("precipitation", []) or []))
        for h in per_point
    ]
    weights = [np.cos(np.deg2rad(la)) for la, _ in _grid_points(box)]
    return area_mean_hourly(loc_series, weights)


# --------------------------------------------------------------------------- #
# driver
# --------------------------------------------------------------------------- #
def build_intensity_table(years) -> pd.DataFrame:
    """Per-window intensity for both boxes across ``years`` -> tidy frame keyed on
    ``(year, window_start, window_end)`` with the 6 intensity columns."""
    rows = []
    for year in years:
        box_hourly = {
            name: _box_hourly_mean(name, box, year) for name, box in BOXES.items()
        }
        for w0, w1 in monsoon_windows(year):
            row = {"year": year, "window_start": w0, "window_end": w1}
            for name in BOXES:
                metrics = window_intensity(box_hourly[name], w0, w1)
                for m in METRICS:
                    row[f"{name}_{m}"] = metrics[m]
            rows.append(row)
    cols = ["year", "window_start", "window_end"] + [
        f"{name}_{m}" for name in BOXES for m in METRICS
    ]
    return pd.DataFrame(rows, columns=cols)


def main():
    years = config.YEARS  # 2015..2025
    df = build_intensity_table(years)
    DATA.mkdir(exist_ok=True)
    df.to_csv(OUT_CSV, index=False)
    print(f"wrote {OUT_CSV}  ({len(df)} rows, {len(df.columns)} cols)")
    print(df.describe(include="all").T.to_string())
    # quick 2025 core-season peek (the event windows)
    ev = df[(df.year == 2025) & (df.window_start.str.slice(5) >= "08-14")]
    print("\n2025 event-window intensity:")
    print(ev.to_string(index=False))


if __name__ == "__main__":
    main()
