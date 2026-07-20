# pipeline/batch_decade.py
"""Wave 2 runner. Usage:
    python pipeline/batch_decade.py 2023        # one year (anchor first!)
    python pipeline/batch_decade.py             # all years
Exports land in Drive/sailaab; monitor with `earthengine task list`."""

import sys

import ee

from sailaab.decade import run_manifest
from sailaab.ee_graphs import (
    punjab_districts,
    flood_mask_for_window,
    district_flood_stats,
)

EE_PROJECT = "ee-YOURUSER"  # set after Task 1 of plan 01


def main():
    ee.Initialize(project=EE_PROJECT)
    years = [int(a) for a in sys.argv[1:]] or None
    districts = punjab_districts()
    aoi = districts.union(1).geometry()

    by_year = {}
    for row in run_manifest(years):
        f = flood_mask_for_window(aoi, row["window"], row["pre"])
        by_year.setdefault(row["year"], []).append(
            district_flood_stats(f, districts, row["year"], row["window"][0])
        )
    for year, fcs in by_year.items():
        merged = ee.FeatureCollection(fcs).flatten()
        ee.batch.Export.table.toDrive(
            collection=merged,
            description=f"sailaab_decade_{year}",
            folder="sailaab",
            fileFormat="CSV",
        ).start()
        print(f"queued {year}")


if __name__ == "__main__":
    main()
