#!/usr/bin/env python
# pipeline/fetch_rain_longrecord.py
"""Long-record extension of the IMD box rainfall series: 1961-2025.

The climate-trend panel asks whether the rain loading that produced the 2025
flood is becoming more frequent. Answering that needs a multi-decade record, so
this script extends the committed 2015-2025 daily box means back to 1961 using
the SAME IMD 0.25 deg product, the SAME two AOI boxes, and the SAME cos(lat)
area-mean + ``rain.where(rain >= 0)`` no-data mask as ``pipeline/fetch_rain.py``
(imported, not re-implemented, so the 1961-2014 numbers are byte-for-byte
consistent with the existing 2015-2025 numbers).

Downloads are yearwise ``.grd`` from imdpune.gov.in (no login), ~25 MB/yr. They
are **resumable** (skip any year already on disk), **paced** (a short sleep
between fetches so shared bandwidth is not hogged), and **retried** a few times
per year. Rasters live under ``data/rasters/imd/rain/*.grd`` and are NOT
committed (gitignored). If the archive throttles and some early years never
arrive, the daily CSV is still written from the earliest fully-available
contiguous start year (>= 1975 preferred) and the gap is reported.

Outputs (committed):
    data/rain_daily_boxes_1961_2025.csv   date, punjab_mm, upstream_mm

Run:  python pipeline/fetch_rain_longrecord.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (str(ROOT), str(ROOT / "pipeline")):
    if p not in sys.path:
        sys.path.insert(0, p)

import pandas as pd  # noqa: E402

import fetch_rain  # noqa: E402  (reuse boxes, _box_mean, masking, daily_box_frame)

DATA = ROOT / "data"
IMD_DIR = ROOT / "data" / "rasters" / "imd"
EXISTING_CSV = DATA / "rain_daily_boxes_2015_2025.csv"  # committed 2015-2025 means
OUT_CSV = DATA / "rain_daily_boxes_1961_2025.csv"

HIST_YEARS = list(range(1961, 2015))  # the years missing from the committed CSV
PACE_SECONDS = 2.0  # be polite to shared bandwidth
MAX_RETRIES = 3
FALLBACK_START = 1975  # if the deep archive throttles


def _grd(year: int) -> Path:
    return IMD_DIR / "rain" / f"{year}.grd"


def ensure_downloaded(years) -> list[int]:
    """Download any missing yearwise .grd; return the years present on disk."""
    import imdlib

    (IMD_DIR / "rain").mkdir(parents=True, exist_ok=True)
    present: list[int] = []
    for yr in years:
        if _grd(yr).exists() and _grd(yr).stat().st_size > 0:
            present.append(yr)
            continue
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                imdlib.get_data(
                    "rain", yr, yr, fn_format="yearwise", file_dir=str(IMD_DIR)
                )
                if _grd(yr).exists() and _grd(yr).stat().st_size > 0:
                    present.append(yr)
                    print(
                        f"  {yr}: downloaded ({_grd(yr).stat().st_size / 1e6:.1f} MB)"
                    )
                    break
            except Exception as e:  # noqa: BLE001 - report and retry/skip
                print(
                    f"  {yr}: attempt {attempt}/{MAX_RETRIES} failed: "
                    f"{type(e).__name__}: {str(e)[:120]}"
                )
                time.sleep(PACE_SECONDS * attempt)
        else:
            print(f"  {yr}: GAVE UP after {MAX_RETRIES} attempts")
        time.sleep(PACE_SECONDS)
    return present


def _contiguous_start(present: list[int]) -> int:
    """Earliest year such that every year from it through 2014 is present.

    Guarantees a gap-free historical block; prefers <= FALLBACK_START but will
    accept a later start if the deep archive dropped early years.
    """
    have = set(present)
    start = 1961
    # walk forward while there is any hole between `start` and 2014
    for y in range(1961, 2015):
        if all(k in have for k in range(y, 2015)):
            start = y
            break
    else:
        start = 2015  # no contiguous historical block at all
    return start


def build_daily_csv() -> None:
    present = ensure_downloaded(HIST_YEARS)
    missing = [y for y in HIST_YEARS if y not in present]
    start = _contiguous_start(present)
    use_years = [y for y in HIST_YEARS if y >= start]

    if missing:
        print(f"\nWARNING: {len(missing)} historical year(s) missing: {missing}")
    print(
        f"Using contiguous historical block {start}-2014 "
        f"({len(use_years)} years) + committed 2015-2025."
    )
    if start > FALLBACK_START:
        print(
            f"NOTE: start {start} is later than the {FALLBACK_START} fallback "
            f"floor because the archive did not serve every earlier year."
        )

    hist = (
        fetch_rain.daily_box_frame(use_years)
        if use_years
        else pd.DataFrame(columns=["date", "punjab_mm", "upstream_mm"])
    )
    recent = pd.read_csv(EXISTING_CSV)
    df = pd.concat([hist, recent], ignore_index=True)
    df["date"] = pd.to_datetime(df["date"])
    df = df.drop_duplicates(subset="date").sort_values("date").reset_index(drop=True)
    df["date"] = df["date"].dt.strftime("%Y-%m-%d")
    df["punjab_mm"] = df["punjab_mm"].round(3)
    df["upstream_mm"] = df["upstream_mm"].round(3)

    DATA.mkdir(exist_ok=True)
    df.to_csv(OUT_CSV, index=False)
    yr0, yr1 = df["date"].iloc[0][:4], df["date"].iloc[-1][:4]
    print(f"\nwrote {OUT_CSV.relative_to(ROOT)}  ({len(df)} rows, {yr0}-{yr1})")


if __name__ == "__main__":
    build_daily_csv()
