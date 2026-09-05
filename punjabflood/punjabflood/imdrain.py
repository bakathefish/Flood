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
