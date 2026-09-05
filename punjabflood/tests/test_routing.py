from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from punjabflood import constants as C
from punjabflood import routing


def _impulse(dam_day="2025-08-29", value=100_000.0, ndays=6):
    idx = pd.date_range("2025-08-27", periods=ndays, freq="D")
    s = pd.Series(0.0, index=idx)
    s.loc[pd.Timestamp(dam_day)] = value
    return s


def test_daily_to_hourly_and_shift():
    s = pd.Series([1.0, 2.0], index=pd.to_datetime(["2025-08-29", "2025-08-30"]))
    h = routing.daily_to_hourly(s)
    assert len(h) == 48 and h.iloc[0] == 1.0 and h.iloc[24] == 2.0
    sh = routing.shift_hours(h, 18)
    assert sh.index[0] == pd.Timestamp("2025-08-29 18:00")


def test_bhakra_impulse_reaches_ropar_and_harike_on_the_annexure_z_clock():
    rel = _impulse()
    arr = routing.arrivals({"Bhakra": rel})
    ropar = arr[arr.station == "Ropar Head Works"].set_index("date")["cusecs"]
    # 18 h shift: the release day still shows the peak (from 18:00) and so does the next day
    assert ropar.loc["2025-08-29"] == 100_000 and ropar.loc["2025-08-30"] == 100_000
    assert ropar.loc["2025-08-31"] == 0.0
    harike = arr[arr.station == "Harike Head Works"].set_index("date")["cusecs"]
    # 52 h: arrives 2 days + 4 h later -> peak visible on Aug 31 (from 04:00) and Sep 1 (to 04:00)
    assert harike.loc["2025-08-30"] == 0.0
    assert harike.loc["2025-08-31"] == 100_000 and harike.loc["2025-09-01"] == 100_000
    fz = arr[arr.station == "Ferozepur Head Works"].set_index("date")["cusecs"]
    assert fz.loc["2025-08-31"] == 100_000  # +12 h: from 16:00 on Aug 31


def test_harike_sums_sutlej_and_beas_and_classifies():
    bh = _impulse(value=150_000.0)
    pg = _impulse(value=200_000.0)
    arr = routing.arrivals({"Bhakra": bh, "Pong": pg})
    harike = arr[arr.station == "Harike Head Works"].set_index("date")
    # Pong impulse (72 h = 3 days exactly) lands Sep 1; Bhakra's (52 h) spans Aug 31 to Sep 1
    assert harike.loc["2025-09-01", "cusecs"] == 350_000
    assert harike.loc["2025-09-01", "class"] == "high"
    assert harike.loc["2025-08-31", "cusecs"] == 150_000
    assert harike.loc["2025-08-31", "class"] == "low"
    dh = arr[arr.station == "Dhilwan"].set_index("date")
    # Dhilwan lag 26 + 0.32 * 46 = 40.7 -> 41 h: Aug 30 17:00 onwards and Aug 31
    assert dh.loc["2025-08-30", "cusecs"] == 200_000 and dh.loc["2025-08-31", "cusecs"] == 200_000
    assert dh.loc["2025-08-30", "class"] == "medium"


def test_river_release_removes_each_dams_diversion():
    q = np.array([20_000.0, 60_000.0])
    out = routing.river_release("Bhakra", q)
    assert out[0] == 0.0 and out[1] == pytest.approx(60_000 - 22_650)
    # the Beas loses up to the Mukerian Hydel Channel's capacity at the Shah Nehar barrage
    assert np.array_equal(routing.river_release("Pong", q), q - 11_500)
    # no sourced diversion for the Ravi below Ranjit Sagar: nothing is taken off
    assert np.array_equal(routing.river_release("Ranjit Sagar", q), q)
    assert routing.BHAKRA_CANAL_DRAW_CUSECS == pytest.approx(
        C.BHAKRA.extra["nangal_hydel_channel_cusecs"].value
        + C.BHAKRA.extra["anandpur_sahib_hydel_channel_cusecs"].value
    )
    assert routing.DIVERSION_CUSECS["Pong"] == C.PONG.extra["mukerian_hydel_channel_cusecs"].value


def test_river_release_when_spilling_adds_passage_only_on_spill_days():
    spill = np.array([0.0, 100_000.0])
    pong = routing.river_release_when_spilling("Pong", spill)
    assert pong[0] == 0.0
    assert pong[1] == pytest.approx(100_000 + C.PONG.turbine_capacity_cusecs.value - 11_500)
    bhakra = routing.river_release_when_spilling("Bhakra", spill)
    assert bhakra[1] == pytest.approx(
        100_000 + C.BHAKRA.turbine_capacity_cusecs.value - routing.BHAKRA_CANAL_DRAW_CUSECS
    )


def test_station_table_has_every_control_point_with_a_route():
    st = routing.station_hours()
    assert {
        "Ropar Head Works",
        "Railway Bridge Phillaur",
        "Harike Head Works",
        "Dhilwan",
        "Naushera Mirthal",
        "Madhopur Head Works",
    } <= set(st["station"])
    assert st.loc[st.station == "Dhilwan", "hours"].iloc[0] == pytest.approx(26 + 0.32 * 46)
