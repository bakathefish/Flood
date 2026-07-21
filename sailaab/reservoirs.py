# sailaab/reservoirs.py
"""Reservoir storage features for the flood forecaster (pure pandas, no I/O
beyond an optional CSV reader).

Feeds two consumers:
  * Wave-4 forecaster - per-monsoon-window mean storage and delta-storage per
    dam, aligned to the windows from `sailaab.windows.monsoon_windows` (the same
    grid `sailaab.dataset` joins predictors on).
  * Wave-3 causal figure - the normalized daily level/storage series.

Input schema (see data/reservoirs_2015_2025.csv and the flood supplement):
    date, dam, level_value, level_unit, storage_value, storage_unit,
    pct_capacity, source_url
Levels may be reported in metres (CWC/data.gov.in) or feet (BBMB/press during
the Aug-Sep 2025 flood); `normalize` adds a canonical `level_m` column. Storage
is BCM (billion m3) throughout. Features are storage-based, so the level unit
mix does not affect them.
"""

from pathlib import Path

import numpy as np
import pandas as pd

from sailaab.windows import monsoon_windows

FEET_TO_M = 0.3048
_NUMERIC_COLS = ("level_value", "storage_value", "pct_capacity")
FEATURE_COLUMNS = [
    "year",
    "window_start",
    "window_end",
    "dam",
    "mean_storage",
    "delta_storage",
]


def normalize(df: pd.DataFrame) -> pd.DataFrame:
    """Parse dates/numerics, add canonical `level_m`, and collapse duplicate
    (dam, date) rows preferring the one that carries a storage value.

    The literal string 'NA' (used by CWC for missing readings) and blanks
    coerce to NaN.
    """
    out = df.copy()
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    for col in _NUMERIC_COLS:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")

    unit = out["level_unit"].astype(str).str.strip().str.lower()
    out["level_m"] = np.where(
        unit.eq("ft"), out["level_value"] * FEET_TO_M, out["level_value"]
    )

    out = out.dropna(subset=["date"])
    # keep the storage-bearing row when a (dam, date) is reported twice
    out = out.assign(_has_storage=out["storage_value"].notna())
    out = (
        out.sort_values(["dam", "date", "_has_storage"])
        .drop_duplicates(["dam", "date"], keep="last")
        .drop(columns="_has_storage")
        .sort_values(["dam", "date"])
        .reset_index(drop=True)
    )
    return out


def _window_rows(group: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    lo, hi = pd.Timestamp(start), pd.Timestamp(end)
    win = group[(group["date"] >= lo) & (group["date"] < hi)]
    return win.dropna(subset=["storage_value"]).sort_values("date")


def window_features(df: pd.DataFrame, years) -> pd.DataFrame:
    """Per (year, monsoon-window, dam): mean and net change of live storage.

    ``mean_storage`` is the mean of available daily/weekly storage in the
    half-open window [window_start, window_end); ``delta_storage`` is the last
    minus the first storage reading in the window (net fill/depletion). Windows
    with no storage reading yield NaN, so every dam present in a year emits a row
    for every monsoon window (alignment with the forecaster grid).
    """
    rows = []
    for year in years:
        windows = monsoon_windows(year)
        year_df = df[df["date"].dt.year == year]
        for dam in sorted(year_df["dam"].unique()):
            group = year_df[year_df["dam"] == dam]
            for start, end in windows:
                win = _window_rows(group, start, end)
                if win.empty:
                    mean_storage = np.nan
                    delta_storage = np.nan
                else:
                    storage = win["storage_value"]
                    mean_storage = float(storage.mean())
                    delta_storage = float(storage.iloc[-1] - storage.iloc[0])
                rows.append(
                    {
                        "year": year,
                        "window_start": start,
                        "window_end": end,
                        "dam": dam,
                        "mean_storage": mean_storage,
                        "delta_storage": delta_storage,
                    }
                )
    return pd.DataFrame(rows, columns=FEATURE_COLUMNS)


def load_frames(paths) -> pd.DataFrame:
    """Read one or more reservoir CSVs and return a single normalized frame."""
    frames = [pd.read_csv(p) for p in paths]
    combined = pd.concat(frames, ignore_index=True)
    return normalize(combined)


DEFAULT_SOURCES = (
    "data/reservoirs_2015_2025.csv",
    "data/reservoirs_2025_flood_supplement.csv",
)


def build_windows(
    sources=DEFAULT_SOURCES,
    years=None,
    out="data/reservoir_windows.csv",
    round_bcm=4,
):
    """Load the committed reservoir CSV(s), build monsoon-window storage
    features for ``years`` (default ``sailaab.config.YEARS``), round, and write
    ``out``. Thin I/O convenience over ``load_frames`` + ``window_features``."""
    from sailaab import config

    paths = [Path(p) for p in sources if Path(p).exists()]
    feats = window_features(load_frames(paths), years or config.YEARS)
    for col in ("mean_storage", "delta_storage"):
        feats[col] = feats[col].round(round_bcm)
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    feats.to_csv(out, index=False)
    return feats


if __name__ == "__main__":
    result = build_windows()
    print(f"wrote {len(result)} window-rows -> data/reservoir_windows.csv")
