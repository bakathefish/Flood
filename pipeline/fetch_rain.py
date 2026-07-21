# pipeline/fetch_rain.py
"""Wave 4 rainfall predictors: IMD Pune 0.25 deg daily gridded rain -> two box
daily area-means -> committed CSVs, plus the 2025 anomaly sanity check.

Source: India Meteorological Department 0.25 deg gridded rainfall, pulled with
`imdlib` straight from imdpune.gov.in (no login). See docs/notes/imd-rain.md.

This is the only xarray/imdlib-touching code in the repo; the pure aggregation
logic lives in sailaab/rain.py (tested). The .grd rasters live under
data/rasters/imd/rain/*.grd and are NOT committed (~25 MB/yr).

Usage:
    pip install imdlib                 # pipeline-only dep (not in requirements.txt)
    python pipeline/fetch_rain.py      # download-if-missing, extract, write CSVs

Outputs (committed):
    data/rain_daily_boxes_2015_2025.csv   date, punjab_mm, upstream_mm
    data/rain_windows_2015_2025.csv       year, window_start, window_end,
        punjab_mm, upstream_mm, *_lag1, *_lag2  (same windows as the decade run)
"""

from pathlib import Path

import numpy as np
import pandas as pd

from sailaab import config
from sailaab.rain import window_table, window_sum, anomaly_stats

# --- Approximate AOI boxes (deliberate bounding-box approximations, not basin
#     polygons; documented in docs/notes/imd-rain.md). lon E, lat N. ---
PUNJAB_BOX = {"lon": (73.85, 76.95), "lat": (29.53, 32.60)}  # Punjab plains
UPSTREAM_BOX = {"lon": (75.5, 78.6), "lat": (30.9, 33.3)}  # Sutlej/Beas/Ravi upstream

IMD_DIR = Path("data/rasters/imd")  # imdlib nests rain/<year>.grd under here
DATA = Path("data")
DAILY_CSV = DATA / "rain_daily_boxes_2015_2025.csv"
WINDOWS_CSV = DATA / "rain_windows_2015_2025.csv"
SANITY_WINDOW = ("08-20", "09-06")  # Aug 20 - Sep 5 inclusive (end exclusive)
_FILL = (
    -999.0
)  # IMD no-data; masked here because imdlib's own mask no-ops on xarray>=2024


def ensure_downloaded(years):
    """Download any missing yearwise .grd from imdpune.gov.in (no login)."""
    import imdlib

    for yr in years:
        if not (IMD_DIR / "rain" / f"{yr}.grd").exists():
            IMD_DIR.mkdir(parents=True, exist_ok=True)
            imdlib.get_data("rain", yr, yr, fn_format="yearwise", file_dir=str(IMD_DIR))


def _box_mean(rain, box):
    """cos(lat)-weighted area-mean over cells whose centres fall in the box,
    skipping masked (no-data) cells."""
    sub = rain.sel(lat=slice(*box["lat"]), lon=slice(*box["lon"]))
    weights = np.cos(np.deg2rad(sub.lat))
    return sub.weighted(weights).mean(dim=("lat", "lon"), skipna=True)


def daily_box_frame(years) -> pd.DataFrame:
    """Daily area-mean mm for both boxes across years -> tidy frame."""
    import imdlib

    parts = []
    for yr in years:
        rain = imdlib.open_data(
            "rain", yr, yr, "yearwise", file_dir=str(IMD_DIR)
        ).get_xarray()["rain"]
        rain = rain.where(rain >= 0.0)  # mask _FILL and any negative sentinel
        parts.append(
            pd.DataFrame(
                {
                    "date": pd.to_datetime(rain["time"].values).strftime("%Y-%m-%d"),
                    "punjab_mm": _box_mean(rain, PUNJAB_BOX).values.astype(float),
                    "upstream_mm": _box_mean(rain, UPSTREAM_BOX).values.astype(float),
                }
            )
        )
    df = pd.concat(parts, ignore_index=True)
    df["punjab_mm"] = df["punjab_mm"].round(3)
    df["upstream_mm"] = df["upstream_mm"].round(3)
    return df


def sanity_2025(df: pd.DataFrame, years) -> None:
    """Report 2025 Aug20-Sep5 box sums vs the 2015-2024 same-window distribution."""
    md0, md1 = SANITY_WINDOW
    print(f"\n=== SANITY: Aug 20 - Sep 5 box rainfall, 2025 vs 2015-2024 ===")
    for col in ("punjab_mm", "upstream_mm"):
        sums = {
            y: window_sum(df, f"{y}-{md0}", f"{y}-{md1}", cols=(col,))[col]
            for y in years
        }
        prior = [sums[y] for y in years if y != 2025]
        a = anomaly_stats(prior, sums[2025])
        print(
            f"{col:11s}: 2025={sums[2025]:.1f}mm  prior_mean={a['mean']:.1f}  "
            f"prior_max={a['max_prior']:.1f}  z={a['z']:.2f}  "
            f"pctile={a['percentile']:.0f}  rank={a['rank']}/{a['n'] + 1}  "
            f"x{a['ratio_to_mean']:.1f}_of_mean (+{(a['ratio_to_mean'] - 1) * 100:.0f}%)"
        )


def main():
    years = config.YEARS  # 2015..2025
    ensure_downloaded(years)
    df = daily_box_frame(years)
    DATA.mkdir(exist_ok=True)
    df.to_csv(DAILY_CSV, index=False)
    print(f"wrote {DAILY_CSV}  ({len(df)} rows)")

    windows = window_table(df, years, lags=2)
    num_cols = [
        c for c in windows.columns if c not in ("year", "window_start", "window_end")
    ]
    windows[num_cols] = windows[num_cols].round(3)
    windows.to_csv(WINDOWS_CSV, index=False)
    print(f"wrote {WINDOWS_CSV}  ({len(windows)} rows)")

    sanity_2025(df, years)


if __name__ == "__main__":
    main()
