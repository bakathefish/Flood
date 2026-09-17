"""IMD 0.25 degree daily gridded rainfall (Pai et al. 2014, MAUSAM 65) as catchment means.

The India Meteorological Department's gridded product is the official rain record for
the Indian Himalayan catchments of the Sutlej, Beas and Ravi and for the Ghaggar. It
covers India only (no-data -999 elsewhere), so for Bhakra the catchment mean is the mean
over the Indian part of the Sutlej catchment (about 20,000 of 56,875 km2); the Tibetan
part is arid and snow-fed and enters the inflow model through the base component. The
same coverage mask is applied to the forecast rain so calibration and forecast use one
index, and the covered area is what turns millimetres into volume.

Files: yearwise ``rain/<year>.grd`` from imdpune.gov.in, read with ``imdlib``. The archive
used here was downloaded by the Sailaab project (1961 to 2025) and lives in that repo at
``data/rasters/imd``; this package sits inside the same repo, so the default location is
one directory up. ``resolve_imd_dir`` looks, in order, at the ``PUNJABFLOOD_IMD_DIR``
environment variable, ``data/raw/imd`` and ``../data/rasters/imd``.
"""

from __future__ import annotations

import os
from collections.abc import Iterable
from pathlib import Path

import numpy as np
import pandas as pd

from punjabflood.catchments import Catchment
from punjabflood.rain import weighted_mean

IMD_DIR_ENV = "PUNJABFLOOD_IMD_DIR"
IMD_DIR_CANDIDATES = (Path("data/raw/imd"), Path("../data/rasters/imd"))
NODATA = -999.0
IMD_WEIGHT_COL = "weight_imd_km2"
SOURCE = (
    "IMD 0.25 degree daily gridded rainfall (Pai et al. 2014), yearwise .grd via imdlib "
    "from imdpune.gov.in"
)


def resolve_imd_dir(env: dict | None = None, candidates=IMD_DIR_CANDIDATES) -> Path:
    """Where the IMD archive is: the environment variable if set, else the first candidate
    directory that holds a ``rain`` folder, else the first candidate (so the error names it)."""
    env = os.environ if env is None else env
    if env.get(IMD_DIR_ENV):
        return Path(env[IMD_DIR_ENV])
    for c in candidates:
        if (c / "rain").is_dir():
            return c
    return Path(candidates[0])


def open_year(year: int, imd_dir: Path | None = None):
    """The year's rainfall as an xarray DataArray (time, lat, lon) in mm/day, no-data as NaN."""
    import imdlib

    imd_dir = resolve_imd_dir() if imd_dir is None else imd_dir
    ds = imdlib.open_data("rain", year, year, "yearwise", file_dir=str(imd_dir))
    rain = ds.get_xarray()["rain"]
    return rain.where(rain >= 0)


def coverage_mask(rain) -> pd.DataFrame:
    """Grid points with at least one valid value: DataFrame(lat, lon) of covered nodes."""
    valid = rain.notnull().any("time")
    lat, lon = np.meshgrid(valid["lat"].values, valid["lon"].values, indexing="ij")
    m = valid.values
    return pd.DataFrame({"lat": np.round(lat[m], 4), "lon": np.round(lon[m], 4)})


def mark_coverage(catchments: dict[str, Catchment], covered: pd.DataFrame) -> None:
    """Add ``weight_imd_km2`` to every catchment's points: the cell weight where the IMD grid
    has data at that node, zero elsewhere. Mutates the Catchment objects."""
    key = set(zip(covered["lat"].round(4), covered["lon"].round(4), strict=True))
    for c in catchments.values():
        pts = c.points
        inside = [
            (round(a, 4), round(b, 4)) in key for a, b in zip(pts["lat"], pts["lon"], strict=True)
        ]
        pts[IMD_WEIGHT_COL] = np.where(inside, pts["weight_km2"], 0.0)


def point_series(rain, points: pd.DataFrame, weight_col: str = IMD_WEIGHT_COL) -> pd.DataFrame:
    """Daily values at the catchment's covered grid nodes: index = date, columns = point id."""
    cols = {}
    for row in points.itertuples(index=False):
        w = getattr(row, weight_col, None)
        if w is None or w <= 0:
            continue
        try:
            s = rain.sel(lat=row.lat, lon=row.lon, method="nearest", tolerance=0.01)
        except KeyError:
            continue
        cols[f"{row.lat:.4f},{row.lon:.4f}"] = pd.Series(
            s.values.astype(float), index=pd.to_datetime(rain["time"].values)
        )
    return pd.DataFrame(cols)


def catchment_daily(
    years: Iterable[int],
    catchments: dict[str, Catchment],
    imd_dir: Path | None = None,
    weight_col: str = IMD_WEIGHT_COL,
) -> pd.DataFrame:
    """Catchment-mean daily rain for the given years: columns date, catchment, rain_mm,
    n_points, area_km2_covered, source."""
    imd_dir = resolve_imd_dir() if imd_dir is None else imd_dir
    out = []
    for year in years:
        rain = open_year(year, imd_dir)
        for name, c in catchments.items():
            pts = c.points[c.points[weight_col] > 0] if weight_col in c.points else c.points
            if pts.empty:
                continue
            values = point_series(rain, pts, weight_col)
            if values.empty:
                continue
            w = pd.Series(
                {
                    f"{r.lat:.4f},{r.lon:.4f}": getattr(r, weight_col)
                    for r in pts.itertuples(index=False)
                }
            )
            mean = weighted_mean(values, w)
            out.append(
                pd.DataFrame(
                    {
                        "date": mean.index,
                        "catchment": name,
                        "rain_mm": mean.to_numpy(),
                        "n_points": values.notna().sum(axis=1).to_numpy(),
                        "area_km2_covered": float(w.reindex(values.columns).sum()),
                        "source": "imd",
                    }
                )
            )
    if not out:
        return pd.DataFrame(
            columns=["date", "catchment", "rain_mm", "n_points", "area_km2_covered", "source"]
        )
    return (
        pd.concat(out, ignore_index=True).sort_values(["catchment", "date"]).reset_index(drop=True)
    )


def covered_area_km2(c: Catchment, weight_col: str = IMD_WEIGHT_COL) -> float:
    return (
        float(c.points[weight_col].sum())
        if weight_col in c.points
        else float(c.points["weight_km2"].sum())
    )


# --- the real-time grid ------------------------------------------------------------------
#
# IMD Pune serves a preliminary daily analysis on the same 0.25 degree lattice for recent
# days (fewer stations than the final yearwise file): one 129 x 135 float32 grid per day,
# latitude rows from 6.5 to 38.5 N, longitude columns from 66.5 to 100 E, -999 no-data,
# returned by a POST to ``rain.php`` with ``rain=DDMMYYYY`` (the endpoint imdlib uses). It
# is the observed rain the product carries for the days before the issue date, in place of
# a model's past days, wherever the service has the day.

RT_URL = "https://imdpune.gov.in/cmpg/Realtimedata/Rainfall/rain.php"
RT_LAT = np.linspace(6.5, 38.5, 129)
RT_LON = np.linspace(66.5, 100.0, 135)
RT_GRID_BYTES = RT_LAT.size * RT_LON.size * 4
RT_SUBDIR = "realtime"
RT_SOURCE = "imd_rt"


def realtime_dir(imd_dir: Path | None = None) -> Path:
    """Where the real-time files live: ``<imd_dir>/realtime``."""
    return (resolve_imd_dir() if imd_dir is None else imd_dir) / RT_SUBDIR


def realtime_path(day, rt_dir: Path) -> Path:
    day = pd.Timestamp(day)
    return Path(rt_dir) / f"rain_ind0.25_{day:%y_%m_%d}.grd"  # imdlib's own naming


def _post_realtime(day, timeout: float = 90.0) -> bytes:
    import requests

    r = requests.post(RT_URL, data={"rain": pd.Timestamp(day).strftime("%d%m%Y")}, timeout=timeout)
    r.raise_for_status()
    return r.content


def fetch_realtime(days: Iterable, rt_dir: Path, post=_post_realtime) -> list[pd.Timestamp]:
    """Download the days not yet on disk (a body that is not exactly one grid is discarded;
    a failed request is a missing day). Returns the days present afterwards, in order."""
    rt_dir = Path(rt_dir)
    rt_dir.mkdir(parents=True, exist_ok=True)
    present = []
    for day in days:
        day = pd.Timestamp(day)
        f = realtime_path(day, rt_dir)
        if f.exists() and f.stat().st_size == RT_GRID_BYTES:
            present.append(day)
            continue
        try:
            body = post(day)
        except Exception:  # noqa: BLE001 - any failure is a missing day
            continue
        if body is not None and len(body) == RT_GRID_BYTES:
            f.write_bytes(body)
            present.append(day)
    return present


def open_real_days(days: Iterable, rt_dir: Path):
    """The real-time files on disk among ``days`` as one DataArray (time, lat, lon) in
    mm/day on the archive lattice, negative (no-data) as NaN; None when none is on disk."""
    import xarray as xr

    stack, times = [], []
    for day in days:
        day = pd.Timestamp(day)
        f = realtime_path(day, rt_dir)
        if not f.exists() or f.stat().st_size != RT_GRID_BYTES:
            continue
        grid = np.frombuffer(f.read_bytes(), dtype="<f4").reshape(RT_LAT.size, RT_LON.size)
        stack.append(grid.astype(float))
        times.append(day)
    if not stack:
        return None
    da = xr.DataArray(
        np.stack(stack),
        coords={"time": pd.DatetimeIndex(times), "lat": RT_LAT, "lon": RT_LON},
        dims=("time", "lat", "lon"),
    )
    return da.where(da >= 0)


def catchment_daily_realtime(
    days: Iterable,
    catchments: dict[str, Catchment],
    rt_dir: Path,
    weight_col: str = IMD_WEIGHT_COL,
) -> pd.DataFrame:
    """Catchment-mean daily rain from the real-time files on disk, source ``imd_rt``, the
    archive's columns; empty when no day is on disk."""
    cols = ["date", "catchment", "rain_mm", "n_points", "area_km2_covered", "source"]
    rain = open_real_days(days, rt_dir)
    if rain is None:
        return pd.DataFrame(columns=cols)
    out = []
    for name, c in catchments.items():
        pts = c.points[c.points[weight_col] > 0] if weight_col in c.points else c.points
        if pts.empty:
            continue
        values = point_series(rain, pts, weight_col)
        if values.empty:
            continue
        w = pd.Series(
            {
                f"{r.lat:.4f},{r.lon:.4f}": getattr(r, weight_col)
                for r in pts.itertuples(index=False)
            }
        )
        mean = weighted_mean(values, w)
        out.append(
            pd.DataFrame(
                {
                    "date": mean.index,
                    "catchment": name,
                    "rain_mm": mean.to_numpy(),
                    "n_points": values.notna().sum(axis=1).to_numpy(),
                    "area_km2_covered": float(w.reindex(values.columns).sum()),
                    "source": RT_SOURCE,
                }
            )
        )
    if not out:
        return pd.DataFrame(columns=cols)
    return (
        pd.concat(out, ignore_index=True).sort_values(["catchment", "date"]).reset_index(drop=True)
    )
