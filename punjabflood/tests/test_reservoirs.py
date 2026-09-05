from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from punjabflood import constants as C
from punjabflood import reservoirs


@pytest.fixture(scope="module")
def legacy_cwc():
    return reservoirs.load_cwc(reservoirs.CWC_LEGACY)


def test_legacy_loader_normalises_units_and_dedups(legacy_cwc):
    assert set(legacy_cwc["dam"]) == {"Bhakra", "Pong", "Ranjit Sagar"}
    b = legacy_cwc[legacy_cwc.dam == "Bhakra"]
    assert b["level_m"].between(440, 520).all()
    assert not b.duplicated(["date"]).any()
    assert b["date"].min().year == 2015


def test_rating_is_monotone_and_matches_the_2025_press_points(legacy_cwc):
    ratings = reservoirs.fit_ratings(legacy_cwc)
    r = ratings["Bhakra"]
    assert np.all(np.diff(r.storage_bcm) >= 0)
    # SANDRP / BBMB reported levels with a rounded percent-full for the 2025 flood. The CWC
    # storage table and BBMB's percent-full disagree by up to about 0.2 BCM (3 percent of
    # live capacity) near full reservoir level; the tolerance records that, it does not hide it.
    for level_ft, storage in ((1666.0, 4.983), (1676.78, 5.482)):
        est = float(r.storage(level_ft * C.FOOT_M))
        assert abs(est - storage) < 0.25, (level_ft, est, storage)
    # round trip; the isotonic fit has flat steps where the feed repeats a storage value,
    # so the inverse is exact only to the width of such a step (well under a metre)
    assert abs(float(r.level(r.storage(505.0))) - 505.0) < 1.0


def test_rating_ignores_a_stale_pair_at_a_record_level():
    levels = np.linspace(400.0, 424.0, 200)
    storage = 0.5 + (levels - 400.0) ** 1.5 / 20.0  # smooth, increasing
    r_clean = reservoirs.Rating.fit("Pong", levels, storage)
    # a stale row: the highest level ever printed against a storage from 7 m lower
    lv = np.r_[levels, 425.6]
    st = np.r_[storage, float(np.interp(418.3, levels, storage))]
    r = reservoirs.Rating.fit("Pong", lv, st)
    assert float(r.storage(424.0)) == pytest.approx(float(r_clean.storage(424.0)), abs=1e-6)
    assert float(r.storage(425.6)) == pytest.approx(float(r_clean.storage(424.0)), abs=1e-6)
    naive = reservoirs.Rating.fit("Pong", lv, st, max_resid_bcm=np.inf)
    assert float(naive.storage(424.0)) < float(r_clean.storage(424.0)) - 0.2
    # a 100 m digit slip is outside the dam's level gate and never enters the fit
    lo, hi = reservoirs.level_gate_m("Pong")
    assert lo < 400.0 < 425.6 < hi and 305.0 < lo
    r2 = reservoirs.Rating.fit("Pong", np.r_[levels, 305.0], np.r_[storage, 6.0])
    assert r2.level_range_m[0] == pytest.approx(400.0)
    assert float(r2.storage(424.0)) == pytest.approx(float(r_clean.storage(424.0)), abs=1e-6)


def test_reconcile_cwc_repairs_stale_rows_and_drops_mistyped_levels():
    levels = np.linspace(400.0, 424.0, 200)
    storage = 0.5 + (levels - 400.0) ** 1.5 / 20.0
    rating = reservoirs.Rating.fit("Pong", levels, storage)
    days = pd.date_range("2023-08-01", periods=6)
    cwc = pd.DataFrame(
        {
            "date": days,
            "dam": "Pong",
            "level_m": [418.0, 418.3, 425.586, 424.2, 305.0, 419.0],
            "storage_bcm": [
                float(rating.storage(418.0)),
                float(rating.storage(418.3)),
                float(rating.storage(418.3)),  # stale: level jumped 7 m, storage repeated
                float(rating.storage(424.2)),
                float(rating.storage(424.2)),  # stale and the level is a 100 m typo
                float(rating.storage(419.0)) + 0.6,  # inconsistent with its own level
            ],
            "basis": "cwc",
        }
    )
    out = reservoirs.reconcile_cwc(cwc, {"Pong": rating}).set_index("date")
    assert len(out) == 5 and pd.Timestamp("2023-08-05") not in out.index
    assert out.loc["2023-08-03", "basis"] == "cwc_level"
    # a little above the fitted range (a record season) the rating clamps to its top value
    assert out.loc["2023-08-03", "storage_bcm"] == pytest.approx(float(rating.storage(424.0)))
    # a mistyped level with a sound storage: the level is blanked, the storage kept
    cwc2 = cwc.copy()
    cwc2.loc[4, "storage_bcm"] = float(rating.storage(419.5))
    out2 = reservoirs.reconcile_cwc(cwc2, {"Pong": rating}).set_index("date")
    assert len(out2) == 6 and np.isnan(out2.loc["2023-08-05", "level_m"])
    assert out2.loc["2023-08-05", "storage_bcm"] == pytest.approx(float(rating.storage(419.5)))
    assert out2.loc["2023-08-05", "basis"] == "cwc"
    assert out.loc["2023-08-06", "basis"] == "cwc_level"
    assert out.loc["2023-08-06", "storage_bcm"] == pytest.approx(float(rating.storage(419.0)))
    assert (out.loc[["2023-08-01", "2023-08-02", "2023-08-04"], "basis"] == "cwc").all()
    # a dam without a rating passes through untouched
    other = cwc.assign(dam="Elsewhere")
    assert reservoirs.reconcile_cwc(other, {"Pong": rating}).equals(
        other.sort_values(["dam", "date"]).reset_index(drop=True)
    )


def test_reconcile_real_record_fixes_the_2023_pong_peak(legacy_cwc):
    ratings = reservoirs.fit_ratings(legacy_cwc)
    fixed = reservoirs.reconcile_cwc(legacy_cwc, ratings)
    row = fixed[(fixed.dam == "Pong") & (fixed.date == "2023-08-17")].iloc[0]
    assert row["basis"] == "cwc_level"
    # 425.586 m is 1396.3 ft, above the 1390 ft FRL: the reservoir was full
    assert row["storage_bcm"] > 0.97 * C.PONG.live_capacity_bcm.value
    # no row keeps a storage more than the tolerance away from its level's rating
    for dam, g in fixed.groupby("dam"):
        g = g[g.level_m.notna() & g.storage_bcm.notna()]
        resid = np.abs(g["storage_bcm"].to_numpy() - ratings[dam].storage(g["level_m"]))
        assert resid.max() <= reservoirs.MAX_RATING_RESID_BCM + 1e-9, dam


def test_bulletins_load_with_both_dams_and_latest_per_day():
    b = reservoirs.load_bulletins()
    assert set(b["dam"]) == {"Bhakra", "Pong"}
    assert b["inflow_cusecs"].gt(0).all()
    latest = b.sort_values("as_on").groupby(["dam", "date"]).tail(1)
    assert len(latest) < len(b)  # two bulletins a day collapse to one


def test_daily_state_prefers_measured_storage_and_fills_from_rating(legacy_cwc):
    ratings = reservoirs.fit_ratings(legacy_cwc)
    bulletins = reservoirs.load_bulletins()
    sup = reservoirs.load_supplement()
    state = reservoirs.daily_state(legacy_cwc, bulletins, ratings, supplement=sup)
    assert list(state.columns) == reservoirs.STATE_COLUMNS
    assert not state.duplicated(["dam", "date"]).any()
    b26 = state[(state.dam == "Bhakra") & (state.date >= "2026-08-01")]
    assert (b26["basis"] == "bbmb").all()
    assert b26["storage_bcm"].notna().all() and b26["inflow_cusecs"].notna().all()
    assert b26["storage_bcm"].between(2.0, 5.0).all()  # a deficit season, 1612 to 1641 ft
    press = state[(state.dam == "Bhakra") & (state.date == "2025-09-02")]
    assert press["basis"].iloc[0] == "press" and abs(press["storage_bcm"].iloc[0] - 5.482) < 1e-9
    hr = reservoirs.headroom_bcm(state.loc[state.dam == "Bhakra", "storage_bcm"], "Bhakra")
    assert (hr >= 0).all() and hr.max() <= C.BHAKRA.live_capacity_bcm.value


def test_fill_gaps_interpolates_short_gaps_only():
    state = pd.DataFrame(
        {
            "date": pd.to_datetime(["2025-08-01", "2025-08-06", "2025-08-19", "2025-09-10"]),
            "dam": "Bhakra",
            "level_m": [np.nan] * 4,
            "storage_bcm": [3.301, 3.5, 4.983, 5.6],
            "inflow_cusecs": [np.nan] * 4,
            "outflow_cusecs": [np.nan] * 4,
            "basis": "press",
        }
    )
    filled = reservoirs.fill_gaps(state, max_gap_days=14)
    f = filled.set_index("date")
    assert f.loc["2025-08-03", "basis"] == "interp"
    assert f.loc["2025-08-03", "storage_bcm"] == pytest.approx(3.301 + (3.5 - 3.301) * 2 / 5)
    assert f.loc["2025-08-12", "basis"] == "interp"  # 13-day gap is filled
    assert "2025-08-25" not in f.index  # the 22-day gap is not
    assert (f.loc[f.basis == "press", "storage_bcm"] == [3.301, 3.5, 4.983, 5.6]).all()


def test_headroom_floors_at_zero():
    assert reservoirs.headroom_bcm([7.0], "Bhakra")[0] == 0.0
    assert reservoirs.headroom_bcm([6.0], "Bhakra")[0] == pytest.approx(0.229)
    assert reservoirs.storage_fraction([3.1145], "Bhakra")[0] == pytest.approx(0.5)
