"""Pull the ERA5 daily snowfall and 2 m temperature over the whole Bhakra catchment
(all 131 grid points, the half outside the IMD grid included, weighted by area) for the
snowmelt term of the inflow model. One archive call per point over the whole span; the
client sleeps through Open-Meteo's minutely and hourly limits and caches every call, so the
script is resumable. Outputs: ``data/raw/rain/snow_bhakra_daily.csv`` (the catchment means:
``date, snowfall_cm, t2m_mean_c, precip_mm, n_points, catchment, area_km2_covered``) and
``data/raw/rain/bhakra_melt_daily.csv`` (the degree-day bucket run at every point from the
same cached calls and averaged by area: ``date, snowfall_mm, melt_mm, pack_mm, t2m_mean_c,
n_points, catchment``; the pack starts empty on 2014-01-01, a spin-up year before the
first fitted season, and the table runs to the rain table's last day, ``MELT_SPANS``).

Run from ``punjabflood/``: ``python scripts/pull_snow_bhakra.py [start] [end]``.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from punjabflood import catchments as catchments_mod  # noqa: E402
from punjabflood import rain, snow  # noqa: E402
from punjabflood.openmeteo import OpenMeteo  # noqa: E402

OUT = Path("data/raw/rain/snow_bhakra_daily.csv")
MELT_OUT = Path("data/raw/rain/bhakra_melt_daily.csv")
DAILY = snow.ARCHIVE_DAILY
# The archive spans (``snow.MELT_SPANS``): a spin-up year before the first fitted season,
# the fitted seasons, and the current year to the rain table's last day.
MELT_SPANS = snow.MELT_SPANS


def main(start: str = "2015-01-01", end: str = "2025-12-31") -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    cat = catchments_mod.load_geojson()["Bhakra"]
    client = OpenMeteo()
    df = rain.era5_catchment_daily(
        client, cat, start, end, years_per_chunk=11, daily=DAILY, weight_col=rain.WEIGHT_COL
    )
    df = df.rename(
        columns={
            "snowfall_sum": "snowfall_cm",
            "temperature_2m_mean": "t2m_mean_c",
            "rain_mm": "precip_mm",
        }
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False)
    print(
        f"wrote {OUT}: {len(df)} days, {int(df['n_points'].max())} points, "
        f"{client.calls} calls, {client.cache_hits} cache hits"
    )
    melt = snow.catchment_melt(
        client, cat, MELT_SPANS[0][0], MELT_SPANS[-1][1], chunks=MELT_SPANS
    )
    melt.to_csv(MELT_OUT, index=False)
    print(
        f"wrote {MELT_OUT}: {len(melt)} days, melt {melt['melt_mm'].sum():.0f} mm over the span, "
        f"peak pack {melt['pack_mm'].max():.0f} mm"
    )


if __name__ == "__main__":
    main(*sys.argv[1:3])
