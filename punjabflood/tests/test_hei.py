from __future__ import annotations

import pytest

from punjabflood import constants as C
from punjabflood import hei


def test_full_reservoir_passes_inflow_above_absorption():
    cap = C.PONG.live_capacity_bcm.value
    inflow_cusecs = 150_000
    daily = [C.cusec_days_to_bcm(inflow_cusecs)] * 3
    r = hei.headroom_exhaustion("Pong", cap, daily, absorption_cusecs_value=45_600)
    assert r.day_of_exhaustion == 1
    assert r.release_by_day_cusecs == pytest.approx([inflow_cusecs - 45_600] * 3)
    assert r.hei > 0
    assert r.forced_release_bcm == pytest.approx(C.cusec_days_to_bcm((inflow_cusecs - 45_600) * 3))
    assert r.storage_by_day_bcm == pytest.approx([cap] * 3)


def test_large_headroom_absorbs_the_event():
    daily = [0.1, 0.1, 0.1]  # 0.3 BCM over 3 days
    r = hei.headroom_exhaustion("Bhakra", 4.0, daily, absorption_cusecs_value=35_000)
    assert r.day_of_exhaustion is None
    assert r.forced_release_bcm == 0.0
    assert r.hei < 0
    # water balance: storage rises by inflow minus absorption each day
    a = C.cusec_days_to_bcm(35_000)
    assert r.storage_by_day_bcm[0] == pytest.approx(4.0 + 0.1 - a)
    assert r.storage_by_day_bcm[-1] == pytest.approx(4.0 + 0.3 - 3 * a)


def test_index_is_linear_in_inflow_and_exhaustion_day_is_found():
    cap = C.BHAKRA.live_capacity_bcm.value
    a = C.cusec_days_to_bcm(35_000)
    storage = cap - 0.5  # half a BCM of headroom
    # day 1 fills 0.3, day 2 another 0.3 -> exhaustion on day 2
    daily = [0.3 + a, 0.3 + a, 0.0 + a]
    r = hei.headroom_exhaustion("Bhakra", storage, daily, absorption_cusecs_value=35_000)
    assert r.day_of_exhaustion == 2
    assert r.release_by_day_cusecs[0] == 0.0
    assert r.release_by_day_cusecs[1] == pytest.approx(C.bcm_to_cusec_days(0.1))
    assert r.hei == pytest.approx((0.6 + 3 * a - 0.5 - 3 * a) / cap)
    r2 = hei.headroom_exhaustion("Bhakra", storage, [2 * x for x in daily], 35_000)
    assert r2.inflow_volume_bcm == pytest.approx(2 * r.inflow_volume_bcm)


def test_ensemble_summary():
    cap = C.PONG.live_capacity_bcm.value
    members = [
        hei.headroom_exhaustion("Pong", cap - 0.2, [0.3, 0.3], 45_600),
        hei.headroom_exhaustion("Pong", cap - 0.2, [0.05, 0.05], 45_600),
    ]
    s = hei.ensemble_summary(members)
    assert s["n_members"] == 2 and s["p_exhaustion"] == 0.5
    # 0.2 BCM of headroom, 0.3 in and 0.1116 out per day: full on day 2
    assert s["median_day_of_exhaustion"] == 2
    assert s["hei_q90"] > s["hei_q10"]


def test_absorption_lookup():
    assert hei.absorption_cusecs("Pong") == 45_600
    assert hei.absorption_cusecs("Bhakra") == pytest.approx(C.BHAKRA.turbine_capacity_cusecs.value)
    assert 34_000 < hei.absorption_cusecs("Bhakra") < 36_000  # 3.25 lakh minus 8212 cumec
    assert 15_000 < hei.absorption_cusecs("Ranjit Sagar") < 25_000  # 600 MW at 121.9 m head
    # river-only passage: the Nangal canals take 22,650 cusecs of Bhakra's turbine water
    assert hei.absorption_cusecs("Bhakra", canal_draw_cusecs=22_650) == pytest.approx(
        C.BHAKRA.turbine_capacity_cusecs.value - 22_650
    )
    assert hei.absorption_cusecs("Pong", canal_draw_cusecs=1e6) == 0.0
