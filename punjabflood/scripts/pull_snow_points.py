"""Pull the ERA5 snow and temperature archive for a subset of the Bhakra catchment's grid
points into the Open-Meteo disk cache, so the pull can be spread over machines when one
IP's daily quota is spent (Open-Meteo's free tier limits calls per IP per day). The
points are the same ordered list ``pull_snow_bhakra.py`` walks, the request is identical,
so the cached files drop straight into ``data/cache/openmeteo/archive/`` on the machine
that runs the full script (every call is then a cache hit).

Run from ``punjabflood/``:
  python scripts/pull_snow_points.py --list-missing
  python scripts/pull_snow_points.py --points 112,113,114 [--span 2014|main|2026]
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from punjabflood import catchments as catchments_mod  # noqa: E402
from punjabflood import rain, snow  # noqa: E402
from punjabflood.openmeteo import OpenMeteo  # noqa: E402

SPANS = {
    "2014": ("2014-01-01", "2014-12-31"),
    "main": ("2015-01-01", "2025-12-31"),
    "2026": ("2026-01-01", "2026-09-15"),
}


def _params(lat: float, lon: float, span: tuple[str, str]) -> dict:
    return {
        "latitude": lat,
        "longitude": lon,
        "start_date": span[0],
        "end_date": span[1],
        "daily": list(snow.ARCHIVE_DAILY),
        "timezone": "UTC",
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--points", default="", help="comma-separated point indices to pull")
    ap.add_argument("--span", default="main", choices=sorted(SPANS), help="archive span")
    ap.add_argument("--list-missing", action="store_true", help="print indices not cached")
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    cat = catchments_mod.load_geojson()["Bhakra"]
    client = OpenMeteo()
    pts = list(rain.points_with_weights(cat, rain.WEIGHT_COL))
    span = SPANS[a.span]
    if a.list_missing:
        missing = [
            i
            for i, (_pid, lat, lon, _w) in enumerate(pts)
            if not client._cache_path("archive", _params(lat, lon, span)).exists()
        ]
        print(",".join(map(str, missing)))
        return
    idx = [int(x) for x in a.points.split(",") if x.strip()]
    for i in idx:
        _pid, lat, lon, _w = pts[i]
        j = client.archive_daily(lat, lon, span[0], span[1], daily=snow.ARCHIVE_DAILY)
        n = len(j.get("daily", {}).get("time", []))
        logging.info("point %d (%.3f, %.3f): %d days", i, lat, lon, n)
    print(f"{len(idx)} points, {client.calls} calls, {client.cache_hits} cache hits")


if __name__ == "__main__":
    main()
