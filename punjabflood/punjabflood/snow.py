"""A temperature-index snowpack per archive point, and the catchment melt it yields.

The Bhakra catchment's base flow is snowmelt from Kinnaur, Spiti and the Tibetan plateau,
outside the IMD grid the rain response is calibrated on. The inflow model carries that base
as a constant intercept; this module gives it a day: for every archive point the daily
snowfall (ERA5 through the Open-Meteo archive, 10 mm of water per 7 cm of snow, the
constant of ``weather.py``) is stacked into a pack and released by a degree-day rule,
``melt = min(pack + snow, DDF * max(T - T0, 0))``, ``DDF`` fixed at 4.0 mm per degree-day
(the middle of the Himalayan range in Hock 2003, J. Hydrol. 282, 104). The factor is not
fitted: the inflow model's coefficient on the melt volume absorbs the scale, the factor
only sets how fast a pack drains. The catchment melt is the area-weighted mean over every
point of the catchment (all 131 at Bhakra, not the 71 the IMD grid covers).

The adoption rule for the term is in
``docs/superpowers/plans/2026-09-19-snowmelt-and-watch-hindcast.md``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from punjabflood.catchments import Catchment
from punjabflood.openmeteo import OpenMeteo
from punjabflood.rain import WEIGHT_COL, _year_chunks, points_with_weights, weighted_mean
from punjabflood.weather import SNOW_CM_TO_MM_WATER

DDF_MM_PER_DEGREE_DAY = 4.0
T0_C = 0.0
ARCHIVE_DAILY = ("snowfall_sum", "temperature_2m_mean", "precipitation_sum")
COLUMNS = ["snowfall_mm", "melt_mm", "pack_mm", "t2m_mean_c", "n_points"]


def degree_day_melt(
    snow_mm: np.ndarray,
    t_c: np.ndarray,
    ddf: float = DDF_MM_PER_DEGREE_DAY,
    t0: float = T0_C,
    pack0: float = 0.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Pack (end of day) and melt (during the day), mm of water, day by day. A missing
    temperature melts nothing that day; a missing snowfall adds nothing."""
    snow = np.nan_to_num(np.asarray(snow_mm, dtype=float), nan=0.0)
    t = np.asarray(t_c, dtype=float)
    cap = np.where(np.isnan(t), 0.0, ddf * np.maximum(t - t0, 0.0))
    pack = np.empty(len(snow))
    melt = np.empty(len(snow))
    p = float(pack0)
    for i in range(len(snow)):
        avail = p + snow[i]
        m = min(avail, cap[i])
        p = avail - m
        pack[i] = p
        melt[i] = m
    return pack, melt


def catchment_melt_from_points(
    per_point: dict[str, pd.DataFrame], weights: pd.Series, ddf: float = DDF_MM_PER_DEGREE_DAY
) -> pd.DataFrame:
    """Run the bucket at every point (frames indexed by day with ``snowfall_cm`` and
    ``t2m_mean_c``) and average by area: columns ``COLUMNS``, indexed by day."""
    snow_f, melt_f, pack_f, t_f = {}, {}, {}, {}
    for pid, df in per_point.items():
        snow_mm = df["snowfall_cm"].to_numpy(dtype=float) * SNOW_CM_TO_MM_WATER
        pack, melt = degree_day_melt(snow_mm, df["t2m_mean_c"].to_numpy(dtype=float), ddf)
        snow_f[pid] = pd.Series(snow_mm, index=df.index)
        melt_f[pid] = pd.Series(melt, index=df.index)
        pack_f[pid] = pd.Series(pack, index=df.index)
        t_f[pid] = df["t2m_mean_c"].astype(float)
    out = pd.DataFrame(
        {
            "snowfall_mm": weighted_mean(pd.DataFrame(snow_f), weights),
            "melt_mm": weighted_mean(pd.DataFrame(melt_f), weights),
            "pack_mm": weighted_mean(pd.DataFrame(pack_f), weights),
            "t2m_mean_c": weighted_mean(pd.DataFrame(t_f), weights),
        }
    )
    out["n_points"] = pd.DataFrame(t_f).notna().sum(axis=1).reindex(out.index)
    out.index.name = "date"
    return out[COLUMNS]


def point_series(
    client: OpenMeteo,
    catchment: Catchment,
    start: str,
    end: str,
    years_per_chunk: int = 11,
    weight_col: str = WEIGHT_COL,
) -> tuple[dict[str, pd.DataFrame], pd.Series]:
    """The per-point daily snowfall and temperature from the archive (cache hits when
    ``scripts/pull_snow_bhakra.py`` has run with the same span and chunking), and the
    area weights."""
    frames: dict[str, pd.DataFrame] = {}
    weights = {}
    for pid, lat, lon, w in points_with_weights(catchment, weight_col):
        weights[pid] = w
        parts = []
        for s, e in _year_chunks(start, end, years_per_chunk):
            d = client.archive_daily(lat, lon, s, e, daily=ARCHIVE_DAILY).get("daily", {})
            idx = pd.to_datetime(d.get("time", []))
            parts.append(
                pd.DataFrame(
                    {
                        "snowfall_cm": pd.Series(d.get("snowfall_sum"), index=idx, dtype=float),
                        "t2m_mean_c": pd.Series(
                            d.get("temperature_2m_mean"), index=idx, dtype=float
                        ),
                    }
                )
            )
        frames[pid] = pd.concat(parts).sort_index()
    return frames, pd.Series(weights)


def catchment_melt(
    client: OpenMeteo, catchment: Catchment, start: str, end: str, years_per_chunk: int = 11
) -> pd.DataFrame:
    """The catchment's daily snowfall, melt, pack and temperature over ``start`` to ``end``
    (the pack starts empty on ``start``), as ``catchment_melt_from_points`` returns it, with
    ``catchment`` and ``date`` columns."""
    frames, weights = point_series(client, catchment, start, end, years_per_chunk)
    out = catchment_melt_from_points(frames, weights)
    out["catchment"] = catchment.name
    return out.reset_index()
