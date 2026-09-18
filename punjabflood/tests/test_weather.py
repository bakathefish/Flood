from __future__ import annotations

import numpy as np
import pandas as pd

from punjabflood import weather as wx


def _det(cat, models, days, mm):
    dates = pd.date_range("2026-09-20", periods=days)
    return pd.concat(
        [
            pd.DataFrame({"target_date": dates, "model": m, "rain_mm": mm[m], "catchment": cat})
            for m in models
        ],
        ignore_index=True,
    )


def _ens(cat, days, scale, n=10):
    dates = pd.date_range("2026-09-20", periods=days)
    return pd.concat(
        [
            pd.DataFrame(
                {
                    "target_date": dates,
                    "member": k,
                    "rain_mm": scale * (0.5 + k / 10),
                    "catchment": cat,
                    "model": "ecmwf_ifs025",
                }
            )
            for k in range(n)
        ],
        ignore_index=True,
    )


def test_season_climatology_keeps_only_monsoon_three_day_totals_for_every_catchment():
    idx = pd.date_range("2020-01-01", "2020-12-31")
    rows = []
    for cat in ("Bhakra", "Pong"):
        rows.append(pd.DataFrame({"date": idx, "catchment": cat, "rain_mm": 1.0}))
    clim = wx.season_3day_climatology(pd.concat(rows))
    assert set(clim) == {"Bhakra", "Pong"}
    # Jun-Sep has 122 days; the rolling sum is defined on all of them here
    assert clim["Bhakra"].shape == (122,)
    assert np.allclose(clim["Bhakra"], 3.0)


def test_percentile_and_snow_share_edge_cases():
    clim = np.arange(0, 100, 1.0)
    assert wx.percentile_of(clim, 50.0) == 50.0
    assert wx.percentile_of(None, 50.0) is None
    assert wx.percentile_of(clim, float("nan")) is None
    share = wx.snow_share(np.array([0.0, 10.0, 7.0]), np.array([0.0, 3.5, 10.0]))
    assert share[0] == 0.0  # dry day
    assert share[1] == 0.5  # 3.5 cm snow is 5 mm water of 10 mm
    assert share[2] == 1.0  # capped


def test_levels_follow_the_written_rules():
    # ensemble present: percentile of the median drives it, members with a heavy day too
    assert wx.level(95.0, 0.0, 0.0, True) == "alert"
    assert wx.level(10.0, 0.6, 0.0, True) == "alert"
    assert wx.level(80.0, 0.0, 0.0, True) == "watch"
    assert wx.level(10.0, 0.3, 0.0, True) == "watch"
    assert wx.level(10.0, 0.0, 0.25, True) == "watch"
    assert wx.level(10.0, 0.0, 0.0, True) == "quiet"
    assert wx.level(None, None, None, True) == "quiet"
    # no ensemble: the primary model's percentile and the models' agreement
    assert wx.level(95.0, None, 0.0, False) == "alert"
    assert wx.level(10.0, None, 0.75, False) == "alert"
    assert wx.level(10.0, None, 0.25, False) == "watch"
    assert wx.level(10.0, None, 0.0, False) == "quiet"


def test_weather_watch_builds_one_entry_per_catchment_with_the_record_and_the_snow():
    det = pd.concat(
        [
            _det(
                "Pong",
                ("gfs_seamless", "ecmwf_aifs025_single"),
                5,
                {"gfs_seamless": 5.0, "ecmwf_aifs025_single": 40.0},
            ),
            _det("Ghaggar Khanauri", ("best_match",), 5, {"best_match": 2.0}),
        ],
        ignore_index=True,
    )
    ens = _ens("Pong", 5, 40.0)
    clim = {"Pong": np.arange(0, 200, 1.0), "Ghaggar Khanauri": np.arange(0, 200, 1.0)}
    wd = pd.DataFrame(
        {
            "target_date": pd.date_range("2026-09-19", periods=6),
            "precipitation_mm": 10.0,
            "snowfall_cm": [0.0, 0.0, 3.5, 0.0, 0.0, 0.0],
            "t2m_max_c": 12.0,
            "t2m_mean_c": 8.0,
            "model": "ecmwf_aifs025_single",
            "catchment": "Pong",
        }
    )
    watch = wx.weather_watch(
        "2026-09-19",
        det,
        ens,
        {"Pong": [1.0, 2.0, 3.0], "Ghaggar Khanauri": []},
        {"Pong": ["imd_rt", "imd_rt", "best_match"]},
        clim,
        "ecmwf_aifs025_single",
        weather_daily=wd,
    )
    p = watch["Pong"]
    assert p["observed"]["total_mm"] == 6.0
    assert p["observed"]["days"] == ["2026-09-16", "2026-09-17", "2026-09-18"]
    assert p["forecast"]["three_day_mm"]["ecmwf_aifs025_single"] == 120.0
    assert p["forecast"]["three_day_percentile"]["ecmwf_aifs025_single"] == 60.0
    assert p["forecast"]["heavy_day_by_model"] == {
        "gfs_seamless": False,
        "ecmwf_aifs025_single": True,
    }
    assert p["forecast"]["models_with_heavy_day"] == 0.5
    e = p["ensemble"]
    assert e["n_members"] == 10
    # members scale 0.5..1.4 of 40 mm a day: three-day totals 60..168, 20 mm a day and up is
    # a heavy day for every member from k=2 on (0.7 * 40 = 28 < 30: k>=3), so 7 of 10
    assert e["p_heavy_day"] == 0.7
    assert e["three_day_q10_mm"] < e["three_day_q50_mm"] < e["three_day_q90_mm"]
    assert p["level"] == "alert"
    assert p["temperature"]["snow_share"][1] == 0.5  # the 2026-09-21 row: 5 mm water of 10
    assert p["temperature"]["snow_share_3day"] == 5.0 / 30.0
    g = watch["Ghaggar Khanauri"]
    assert "ensemble" not in g and "temperature" not in g
    assert g["forecast"]["three_day_percentile"]["best_match"] == 3.0  # 6 of 200 totals below 6 mm
    assert g["level"] == "quiet"
    rows = wx.summary_rows(watch)
    assert {r["catchment"] for r in rows} == {"Pong", "Ghaggar Khanauri"}
    assert rows[0]["level"] in {"alert", "quiet"}


def test_weather_watch_without_a_record_still_levels_on_heavy_days():
    det = _det("Bhakra", ("ecmwf_aifs025_single",), 5, {"ecmwf_aifs025_single": 35.0})
    watch = wx.weather_watch(
        "2026-09-19", det, pd.DataFrame(), {}, None, None, "ecmwf_aifs025_single"
    )
    b = watch["Bhakra"]
    assert b["record_n_days"] == 0
    assert b["forecast"]["three_day_percentile"]["ecmwf_aifs025_single"] is None
    assert b["level"] == "alert"  # the only model has a heavy day: share 1.0 > 0.5
