"""Route dam releases to the WRD control points with the published travel times and
classify the arrivals against the WRD flood-intensity limits.

Pure time shift, no attenuation, no tributary inflow: the guidebook's Annexure Z gives
travel times only, so this is what the state's own tables support. Arrivals are therefore
lower bounds where tributaries add (the Swan and Sirsa on the Sutlej, the Chakki on the
Beas) and upper bounds where the flood wave spreads. Harike receives the Sutlej and the
Beas; Hussainiwala (Ferozepur head works) is Harike plus twelve hours.

Bhakra's river release is its outflow minus the canal off-takes at Nangal (Nangal Hydel
Channel and Anandpur Sahib Hydel Channel), which do not return to the Sutlej above Ropar.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from punjabflood import constants as C


@dataclass(frozen=True)
class Station:
    name: str  # control point name as in constants.CONTROL_POINTS (or an Annexure Z node)
    river: str
    source_dam: str  # "Bhakra", "Pong", "Ranjit Sagar" or "Ghaggar" (index point Bhankarpur)
    hours: float
    note: str = ""


def _dhilwan_hours() -> float:
    tanda = C.travel_hours("Beas", "Pong Dam", "Tanda Bridge")
    reach = C.travel_hours("Beas", "Tanda Bridge", "Harike Head Works")
    return tanda + C.DHILWAN_FRACTION_OF_TANDA_HARIKE * reach


STATIONS: tuple[Station, ...] = (
    Station(
        "Ropar Head Works",
        "Sutlej",
        "Bhakra",
        C.travel_hours("Sutlej", "Bhakra Dam", "Ropar Head Works"),
    ),
    Station(
        "Railway Bridge Phillaur",
        "Sutlej",
        "Bhakra",
        C.travel_hours("Sutlej", "Bhakra Dam", "Railway Bridge Phillaur"),
    ),
    Station(
        "Harike Head Works",
        "Sutlej",
        "Bhakra",
        C.travel_hours("Sutlej", "Bhakra Dam", "Harike Head Works"),
    ),
    Station(
        "Naushera Mirthal", "Beas", "Pong", C.travel_hours("Beas", "Pong Dam", "Naushera Mirthal")
    ),
    Station(
        "Dhilwan",
        "Beas",
        "Pong",
        _dhilwan_hours(),
        "interpolated on the Tanda-Harike reach; not an Annexure Z node",
    ),
    Station(
        "Harike Head Works", "Beas", "Pong", C.travel_hours("Beas", "Pong Dam", "Harike Head Works")
    ),
    Station(
        "Madhopur Head Works",
        "Ravi",
        "Ranjit Sagar",
        0.0,
        "Madhopur is a few km below the dam; no Annexure Z time, lag taken as zero",
    ),
    Station(
        "Crossing with Narwana Branch",
        "Ghaggar",
        "Ghaggar",
        C.travel_hours("Ghaggar", "Bhankarpur", "Crossing with Narwana Branch"),
    ),
    Station(
        "Khanauri",
        "Ghaggar",
        "Ghaggar",
        C.travel_hours("Ghaggar", "Bhankarpur", "Khanauri"),
        "AWLR site; no WRD threshold printed",
    ),
    Station(
        "Sardulgarh",
        "Ghaggar",
        "Ghaggar",
        C.travel_hours("Ghaggar", "Bhankarpur", "Sardulgarh"),
        "no WRD threshold printed",
    ),
)
HUSSAINIWALA_LAG_H = C.travel_hours("Sutlej", "Harike Head Works", "Hussainiwala Head Works")

BHAKRA_CANAL_DRAW_CUSECS = (
    C.BHAKRA.extra["nangal_hydel_channel_cusecs"].value
    + C.BHAKRA.extra["anandpur_sahib_hydel_channel_cusecs"].value
)


# The most that can leave each river between the dam and the first control point: Bhakra's
# turbine water feeds the Nangal canals; the Beas is diverted at the Shah Nehar barrage into
# the Mukerian Hydel Channel. Ranjit Sagar's turbine water reaches Madhopur, where the UBDC
# and the Kashmir canal take off; that draw is not in the sourced constants, so none is
# subtracted (its routed release is an upper side by that amount).
DIVERSION_CUSECS = {
    "Bhakra": BHAKRA_CANAL_DRAW_CUSECS,
    "Pong": C.PONG.extra["mukerian_hydel_channel_cusecs"].value,
    "Ranjit Sagar": 0.0,
}


def river_release(dam: str, outflow_cusecs, canal_draw_cusecs: float | None = None):
    """What reaches the river below the dam from a total outflow: the diversion capacity
    (``DIVERSION_CUSECS``) is taken off first."""
    q = np.asarray(outflow_cusecs, dtype=float)
    draw = DIVERSION_CUSECS.get(dam, 0.0) if canal_draw_cusecs is None else canal_draw_cusecs
    return np.maximum(q - draw, 0.0)


def river_release_when_spilling(dam: str, spill_cusecs) -> np.ndarray:
    """Lower bound on the river release on days the spillway is forced: the spill plus the
    turbine passage (a full reservoir passes its inflow, so the turbines are running) less the
    diversion capacity. Zero on days without spill, when the dam may hold water back."""
    spill = np.asarray(spill_cusecs, dtype=float)
    passage = C.DAMS[dam].turbine_capacity_cusecs
    passage_cusecs = passage.value if passage is not None else 0.0
    river = spill + np.maximum(passage_cusecs - DIVERSION_CUSECS.get(dam, 0.0), 0.0)
    return np.where(spill > 0, river, 0.0)


def daily_to_hourly(daily: pd.Series) -> pd.Series:
    """A daily-mean series (index = dates) as a constant-within-day hourly series."""
    idx = pd.to_datetime(daily.index)
    start = idx.min()
    end = idx.max() + pd.Timedelta(hours=23)
    hours = pd.date_range(start, end, freq="h")
    return daily.set_axis(idx).reindex(hours, method="ffill")


def shift_hours(hourly: pd.Series, hours: float) -> pd.Series:
    """Shift a series later by ``hours`` (fractional hours round to the nearest hour)."""
    h = int(round(hours))
    return hourly.set_axis(hourly.index + pd.Timedelta(hours=h))


def route_daily(daily_release: pd.Series, hours: float, how: str = "max") -> pd.Series:
    """Daily arrivals at a point ``hours`` downstream of a daily-mean release series.
    ``how`` = 'max' (daily maximum of the shifted hourly series; what a threshold sees) or
    'mean'."""
    hourly = shift_hours(daily_to_hourly(daily_release), hours)
    daily = hourly.resample("1D").max() if how == "max" else hourly.resample("1D").mean()
    daily.index.name = "date"
    return daily


def arrivals(releases: dict[str, pd.Series], how: str = "max") -> pd.DataFrame:
    """``releases``: dam or index point -> daily series of river release (cusecs).
    Returns one row per (station, date) with the summed arrivals (Harike sums Sutlej and
    Beas; Hussainiwala is Harike shifted 12 h)."""
    rows = []
    harike_parts = []
    for st in STATIONS:
        if st.source_dam not in releases:
            continue
        s = route_daily(releases[st.source_dam], st.hours, how)
        if st.name == "Harike Head Works":
            harike_parts.append(s)
            continue
        rows.append(
            pd.DataFrame(
                {"station": st.name, "date": s.index, "cusecs": s.to_numpy(), "river": st.river}
            )
        )
    if harike_parts:
        h = pd.concat(harike_parts, axis=1).fillna(0.0).sum(axis=1)
        rows.append(
            pd.DataFrame(
                {
                    "station": "Harike Head Works",
                    "date": h.index,
                    "cusecs": h.to_numpy(),
                    "river": "Sutlej+Beas",
                }
            )
        )
        hz = shift_hours(daily_to_hourly(h), HUSSAINIWALA_LAG_H).resample("1D").max()
        rows.append(
            pd.DataFrame(
                {
                    "station": "Ferozepur Head Works",
                    "date": hz.index,
                    "cusecs": hz.to_numpy(),
                    "river": "Sutlej",
                }
            )
        )
    if not rows:
        return pd.DataFrame(columns=["station", "date", "cusecs", "river", "class"])
    out = pd.concat(rows, ignore_index=True)
    out["class"] = [classify(st, q) for st, q in zip(out["station"], out["cusecs"], strict=True)]
    return out.sort_values(["station", "date"]).reset_index(drop=True)


def classify(station: str, cusecs: float) -> str | None:
    cp = C.CONTROL_POINTS.get(station)
    if cp is None:
        return None
    return cp.classify(cusecs)


def station_hours() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "station": s.name,
                "river": s.river,
                "source": s.source_dam,
                "hours": s.hours,
                "note": s.note,
            }
            for s in STATIONS
        ]
    )
