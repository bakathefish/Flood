# pipeline/build_daily_district_flood.py
"""Per-day, per-district flooded fraction from the cached GFM day masks.

The decade pipeline fetches one Copernicus GFM observed-flood mask per monsoon
day and then unions them into eleven 10-day windows before anything downstream
sees them. That aggregation is what starves the forecaster: it leaves seven
usable windows per district-season, it smears a signal whose real routing time
is one to three days across a ten-day box, and it collapses the flood onsets
that an early-warning system is supposed to catch into a handful of examples.

The per-day masks are already on disk. This script reads them at their native
daily resolution and writes the district series the forecaster should have been
trained on. It reuses the decade pipeline's own grid, reference-water mask,
district rasterisation and area helpers, so the daily rows aggregate back to the
committed window table rather than forming a parallel truth.

A monsoon day with no mask file on disk is an observed dry day, not a gap: the
fetcher probes every day and only writes a full raster when the probe is
non-empty (`data/gfm/_decade_progress.csv` records every probe). Days absent
from the progress log are genuinely unobserved and are emitted as NaN so they
can never be mistaken for zeros.

Run: python -m pipeline.build_daily_district_flood

Output (committed):
    data/gfm_district_daily_2015_2025.csv   date, district, flooded_ha, fraction
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from sailaab import config
from sailaab.gfm import web_mercator_area_km2
from pipeline.fetch_gfm import bbox_3857, grid_shape
from pipeline.fetch_gfm_decade import (
    GFM_DIR,
    PROGRESS_CSV,
    REFWATER_TIF,
    _district_ha_from_mask,
    _district_labels,
    _read_mask,
    _row_ha,
    season_days,
)

OUT_CSV = Path("data/gfm_district_daily_2015_2025.csv")


def _observed_days() -> set[str]:
    """Monsoon days the fetcher actually probed, from the progress log."""
    if not PROGRESS_CSV.exists():
        return set()
    with PROGRESS_CSV.open(newline="", encoding="utf-8") as fh:
        return {row["day"] for row in csv.DictReader(fh) if row.get("day")}


def main() -> None:
    bounds = bbox_3857()
    ncols, nrows = grid_shape(bounds)

    if not REFWATER_TIF.exists():
        sys.exit(f"missing {REFWATER_TIF}; run `fetch_gfm_decade fetch` first")
    refwater = _read_mask(REFWATER_TIF)
    if refwater.shape != (nrows, ncols):
        sys.exit(f"refwater shape {refwater.shape} != grid {(nrows, ncols)}")

    labels, names = _district_labels(bounds, nrows, ncols)
    n_labels = len(names)
    row_ha = _row_ha(bounds, nrows, ncols)
    district_ha = _district_ha_from_mask(
        np.ones((nrows, ncols), bool), labels, row_ha, n_labels
    )
    ref_full = web_mercator_area_km2(labels > 0, bounds) * 100.0
    assert abs(district_ha[1:].sum() - ref_full) / ref_full < 1e-6, "area mismatch"

    observed = _observed_days()
    rows = []
    n_wet = n_dry = n_missing = 0

    for year in config.YEARS:
        year_dir = GFM_DIR / str(year)
        by_day = {}
        if year_dir.exists():
            for tif in sorted(year_dir.glob("gfm_punjab_*.tif")):
                d8 = tif.stem.split("_")[-1]
                by_day[f"{d8[:4]}-{d8[4:6]}-{d8[6:8]}"] = tif

        for day in season_days(year):
            day = str(day)
            tif = by_day.get(day)
            if tif is not None:
                mask = _read_mask(tif) & ~refwater
                fl = _district_ha_from_mask(mask, labels, row_ha, n_labels)
                n_wet += 1
            elif day in observed:
                fl = np.zeros(n_labels + 1, dtype=float)  # probed, no flood
                n_dry += 1
            else:
                fl = None  # never probed: unknown, not dry
                n_missing += 1

            for li, name in enumerate(names, start=1):
                d_ha = float(district_ha[li])
                if fl is None or d_ha <= 0:
                    ha = frac = float("nan")
                else:
                    ha = float(fl[li])
                    frac = ha / d_ha
                rows.append(
                    {
                        "date": day,
                        "district": name,
                        "flooded_ha": ha,
                        "fraction": frac,
                    }
                )

    df = pd.DataFrame(rows)
    df["flooded_ha"] = df["flooded_ha"].round(2)
    df["fraction"] = df["fraction"].round(6)
    df.to_csv(OUT_CSV, index=False)

    print(f"days: {n_wet} with flood raster, {n_dry} probed dry, {n_missing} unobserved")
    print(f"wrote {OUT_CSV} ({len(df)} rows, {df['district'].nunique()} districts)")

    # Reconciliation against the committed window table: the daily maximum
    # inside a window must not exceed the window union fraction, since the
    # window product unions the same days.
    win = pd.read_csv("data/gfm_district_window_fractions_2015_2025.csv")
    d = df.dropna(subset=["fraction"]).copy()
    d["date"] = pd.to_datetime(d["date"])
    bad = 0
    for _, w in win.iterrows():
        m = (
            (d["district"] == w["district"])
            & (d["date"] >= pd.Timestamp(w["window_start"]))
            & (d["date"] < pd.Timestamp(w["window_end"]))
        )
        sub = d.loc[m, "fraction"]
        if len(sub) and sub.max() > w["fraction"] + 1e-6:
            bad += 1
    print(f"window reconciliation: {bad} of {len(win)} rows where a daily value "
          f"exceeds its window union (expected 0)")

    thr = config.FLOOD_EVENT_FRACTION
    wet = d[d["fraction"] > thr]
    print(f"\ndistrict-days above the {thr:.0%} event threshold: {len(wet)}")
    print(wet.groupby(d["date"].dt.year).size().to_string())


if __name__ == "__main__":
    main()
