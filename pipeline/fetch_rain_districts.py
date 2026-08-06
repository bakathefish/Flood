# pipeline/fetch_rain_districts.py
"""District-resolved IMD rainfall for the forecaster.

The original rain predictors (pipeline/fetch_rain.py) collapse the IMD 0.25 deg
grid to two bounding-box area means, so every district in a window sees the same
rainfall. This script keeps the grid and reduces it per district polygon
instead, which is what gives the forecaster district-specific weather.

Source: the same IMD Pune 0.25 deg daily gridded rasters already on disk under
data/rasters/imd/rain/*.grd (downloaded by fetch_rain.py, no login). This script
adds no new download requirement for years already fetched.

The pure aggregation logic lives in sailaab/rain_districts.py (tested); this
file only reads rasters and writes CSVs, mirroring the fetch_rain.py split.

Usage:
    pip install imdlib xarray          # pipeline-only deps, as for fetch_rain.py
    python -m pipeline.fetch_rain_districts

Outputs (committed):
    data/rain_district_daily_2015_2025.csv    date, district, rain_mm, api_mm
    data/rain_district_windows_2015_2025.csv  district x window predictors
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from sailaab import config
from sailaab.rain_districts import (
    add_api,
    apply_weights,
    build_cell_weights,
    district_daily_frame,
)
from sailaab.windows import monsoon_windows

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
IMD_DIR = DATA / "rasters" / "imd"
DISTRICTS = DATA / "punjab_districts.geojson"

DAILY_CSV = DATA / "rain_district_daily_2015_2025.csv"
# Full IMD record. The long series exists only to give each district its own
# rainfall climatology, so "200 mm in three days" can be expressed as a
# percentile of what that district actually sees at that point in the season.
CLIMO_CSV = DATA / "rain_district_daily_1961_2025.csv"
CLIMO_YEARS = range(1961, 2026)
WINDOWS_CSV = DATA / "rain_district_windows_2015_2025.csv"

API_K = 0.90  # daily retention; mid of the 0.85/0.90/0.95 range in the notes
CELL_DEG = 0.25


def load_polygons(path: Path = DISTRICTS) -> dict:
    gj = json.loads(path.read_text(encoding="utf-8"))
    return {f["properties"]["district"]: f["geometry"] for f in gj["features"]}


def read_year(year: int):
    """(dates, cube, lats, lons) for one IMD year file, no-data masked to NaN."""
    import imdlib

    ds = imdlib.open_data("rain", year, year, "yearwise", file_dir=str(IMD_DIR))
    da = ds.get_xarray()["rain"]
    da = da.where(da >= 0.0)  # IMD uses -999 for no-data
    return (
        pd.to_datetime(da["time"].values),
        da.values.astype(float),
        da["lat"].values.astype(float),
        da["lon"].values.astype(float),
    )


def _window_extremes(daily: pd.DataFrame, windows) -> pd.DataFrame:
    """Per district x window rainfall extremes and antecedent wetness.

    Window means hide the storms that actually break embankments, so alongside
    the window total we carry the wettest single day, the wettest 3-day run and
    the 90th percentile of daily rain inside the window. ``api_start`` is the
    antecedent precipitation index on the day BEFORE the window opens, so it
    describes how saturated the ground already was at issuance and uses no
    information from inside the window itself.
    """
    d = daily.copy()
    d["_date"] = pd.to_datetime(d["date"])
    d = d.sort_values(["district", "_date"])

    rows = []
    for start, end in windows:
        s, e = pd.Timestamp(start), pd.Timestamp(end)
        for name, grp in d.groupby("district", sort=True):
            inside = grp.loc[(grp["_date"] >= s) & (grp["_date"] < e)]
            rain = inside["rain_mm"].to_numpy(dtype=float)
            roll3 = (
                inside["rain_mm"].rolling(3, min_periods=1).sum().to_numpy(dtype=float)
            )
            before = grp.loc[grp["_date"] < s, "api_mm"]
            # Lead-time predictors: rain observed in the opening days of the
            # window, used to rank flooding over the whole window. These are the
            # only rainfall features that support a genuine warning-time claim,
            # since everything else inside the window arrives too late to warn.
            first3 = grp.loc[
                (grp["_date"] >= s) & (grp["_date"] < s + pd.Timedelta(days=3)),
                "rain_mm",
            ]
            first5 = grp.loc[
                (grp["_date"] >= s) & (grp["_date"] < s + pd.Timedelta(days=5)),
                "rain_mm",
            ]
            rows.append(
                {
                    "district": name,
                    "year": int(s.year),
                    "window_start": s.strftime("%Y-%m-%d"),
                    "district_first3d": float(first3.sum(min_count=1)),
                    "district_first5d": float(first5.sum(min_count=1)),
                    "district_max1d": float(np.nanmax(rain)) if rain.size else np.nan,
                    "district_max3d": float(np.nanmax(roll3)) if roll3.size else np.nan,
                    "district_p90": (
                        float(np.nanpercentile(rain, 90)) if rain.size else np.nan
                    ),
                    "api_start": float(before.iloc[-1]) if len(before) else np.nan,
                }
            )
    return pd.DataFrame(rows)


def main(years=None, out_daily=None, windows_too=True) -> None:
    years = list(years or config.YEARS)
    polys = load_polygons()
    print(f"districts: {len(polys)}")

    weights = None
    frames = []
    for yr in years:
        dates, cube, lats, lons = read_year(yr)
        if weights is None:
            weights = build_cell_weights(lats, lons, polys, cell_deg=CELL_DEG)
            ncells = {k: len(v[0]) for k, v in weights.items()}
            print(
                f"grid {len(lats)}x{len(lons)}; cells per district "
                f"min={min(ncells.values())} max={max(ncells.values())}"
            )
        frames.append(district_daily_frame(dates, cube, weights))
        print(f"  {yr}: {len(dates)} days")

    daily = pd.concat(frames, ignore_index=True)
    daily = add_api(daily, k=API_K)
    daily["rain_mm"] = daily["rain_mm"].round(3)
    daily["api_mm"] = daily["api_mm"].round(3)
    target = out_daily or DAILY_CSV
    daily.sort_values(["district", "date"]).to_csv(target, index=False)
    print(f"wrote {target} ({len(daily)} rows)")
    if not windows_too:
        return

    # Same windows as the decade grid, so this table joins 1:1 on
    # (year, window_start, district).
    windows = []
    for yr in years:
        windows += [(a, b) for a, b in monsoon_windows(yr)]

    from sailaab.rain_districts import district_window_table

    wt = district_window_table(daily, windows, lags=2)
    ext = _window_extremes(daily, windows)
    out = wt.merge(ext, on=["district", "year", "window_start"], how="left")
    for c in out.columns:
        if out[c].dtype.kind == "f":
            out[c] = out[c].round(3)
    out.to_csv(WINDOWS_CSV, index=False)
    print(f"wrote {WINDOWS_CSV} ({len(out)} rows)")

    # Sanity: the whole point is across-district variation inside a window.
    g = out.groupby(["year", "window_start"])["district_mm"].nunique()
    print(f"windows where district rainfall varies: {(g > 1).mean() * 100:.1f}%")
    peak = out[(out["year"] == 2025) & (out["window_start"] == "2025-08-24")]
    if len(peak):
        top = peak.nlargest(5, "district_mm")[["district", "district_mm", "api_start"]]
        print("\n2025-08-24 window, wettest districts:")
        print(top.to_string(index=False))


if __name__ == "__main__":
    import sys

    if "--climatology" in sys.argv:
        # 65-year district series; no window products, they are only
        # defined on the decade grid.
        main(years=CLIMO_YEARS, out_daily=CLIMO_CSV, windows_too=False)
    else:
        main()
