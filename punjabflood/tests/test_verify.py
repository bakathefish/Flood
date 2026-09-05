from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from punjabflood import inflow, routing, verify


def _rain(years, catchment="Pong", seed=1):
    rng = np.random.default_rng(seed)
    rows = []
    for y in years:
        days = pd.date_range(f"{y}-01-01", f"{y}-12-31", freq="D")
        r = rng.gamma(0.5, 8.0, size=len(days))
        r[days.month.isin([6, 7, 8, 9]) == False] *= 0.1  # noqa: E712
        rows.append(pd.DataFrame({"date": days, "catchment": catchment, "rain_mm": r}))
    return pd.concat(rows, ignore_index=True)


def test_rain_predictors_have_one_row_per_year_and_monotone_windows():
    rain = _rain(range(2001, 2006))
    p = verify.rain_predictors(rain, "Pong", 12560.0)
    assert list(p.index) == [2001, 2002, 2003, 2004, 2005]
    assert (p["Pong_max1d_bcm"] <= p["Pong_max3d_bcm"]).all()
    assert (p["Pong_max3d_bcm"] <= p["Pong_max5d_bcm"]).all()
    assert (p["Pong_max10d_bcm"] <= p["Pong_season_bcm"]).all()


def test_storage_predictors_pick_nearest_day_and_fraction():
    days = pd.date_range("2019-06-01", "2019-09-30", freq="D")
    st = pd.DataFrame(
        {"date": days, "dam": "Bhakra", "storage_bcm": np.linspace(3.0, 6.0, len(days))}
    )
    p = verify.storage_predictors(st, "Bhakra")
    assert p.loc[2019, "Bhakra_frac_aug01"] == pytest.approx(
        st.set_index("date").loc["2019-08-01", "storage_bcm"] / 6.229
    )
    assert p.loc[2019, "Bhakra_frac_max"] == pytest.approx(6.0 / 6.229)
    assert p.loc[2019, "Bhakra_days_above_95pct"] == int((st.storage_bcm > 0.95 * 6.229).sum())


def test_peak_class_test_recovers_a_perfect_predictor():
    years = list(range(1988, 2026))
    rng = np.random.default_rng(0)
    peak = pd.Series(rng.gamma(2.0, 60_000, size=len(years)), index=years)
    cls = np.where(peak > peak.quantile(0.85), "H", np.where(peak > peak.quantile(0.5), "M", "L"))
    peaks = pd.DataFrame({"year": years, "harike_us_cusecs": peak.values, "wrd_class": cls})
    pred = pd.DataFrame(
        {"x": peak.values + rng.normal(0, 1000, len(years))}, index=pd.Index(years, name="year")
    )
    out = verify.peak_class_test(pred, peaks, "x")
    assert out["n_years"] == 38 and out["n_high"] == (cls == "H").sum()
    assert out["spearman_rho"] > 0.95
    assert out["auroc_high"] > 0.95
    assert out["brier_loyo"] < out["brier_climatology"]
    assert 0 < out["brier_skill_score"] <= 1
    noise = pd.DataFrame({"x": rng.normal(size=len(years))}, index=pd.Index(years, name="year"))
    bad = verify.peak_class_test(noise, peaks, "x")
    assert abs(bad["spearman_rho"]) < 0.5


def test_event_timing_signed_lag():
    arr = pd.DataFrame(
        {
            "station": "Dhilwan",
            "date": pd.to_datetime(["2023-08-15", "2023-08-16", "2023-08-19", "2025-08-30"]),
            "cusecs": [10_000.0, 150_000.0, 20_000.0, 0.0],
        }
    )
    peaks = pd.DataFrame(
        {
            "year": [2023, 2025],
            "date": ["2023-08-17", "2025-08-31"],
            "discharge_cusecs": [237_500, 235_494],
        }
    )
    t = verify.event_timing_test(arr, peaks).set_index("year")
    assert t.loc[2023, "lag_days"] == -1
    assert t.loc[2023, "magnitude_ratio"] == pytest.approx(150_000 / 237_500)
    assert t.loc[2025, "note"] == "no predicted release"


def test_live_test_metrics():
    idx = pd.date_range("2026-08-09", periods=5)
    pred = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0], index=idx) * 10_000
    obs = pred * 1.25
    m = verify.live_test(pred, obs)
    assert m["n"] == 5 and m["pearson_r"] == pytest.approx(1.0)
    assert m["bias_pct"] == pytest.approx(-20.0)


def test_qpf_skill_metrics():
    days = pd.date_range("2025-06-01", periods=40)
    obs = pd.DataFrame(
        {"date": days, "catchment": "Pong", "rain_mm": np.r_[np.zeros(30), np.full(10, 40.0)]}
    )
    rows = []
    for lead in (1, 3):
        fc = obs["rain_mm"].to_numpy() * (1.0 if lead == 1 else 0.5)
        rows.append(
            pd.DataFrame(
                {
                    "target_date": days,
                    "lead_days": lead,
                    "model": "gfs_seamless",
                    "rain_mm": fc,
                    "catchment": "Pong",
                }
            )
        )
    q = pd.concat(rows, ignore_index=True)
    s = verify.qpf_skill(q, obs).set_index("lead_days")
    assert s.loc[1, "hit_rate"] == 1.0 and s.loc[1, "bias_pct"] == 0.0
    assert s.loc[3, "hit_rate"] == 0.0 and s.loc[3, "bias_pct"] == pytest.approx(-50.0)
    assert s.loc[3, "heavy_days_obs"] == 10 and s.loc[1, "pearson_r"] == pytest.approx(1.0)


def test_perfect_prog_hei_runs_and_flags_exhaustion(tmp_path):
    days = pd.date_range("2023-08-01", "2023-08-31", freq="D")
    st = pd.DataFrame(
        {"date": days, "dam": "Pong", "storage_bcm": np.linspace(5.9, 6.157, len(days))}
    )
    rain = pd.DataFrame({"date": pd.date_range("2023-07-20", "2023-09-10"), "catchment": "Pong"})
    rain["rain_mm"] = 0.0
    rain.loc[rain.date.between("2023-08-12", "2023-08-14"), "rain_mm"] = 120.0
    p = inflow.InflowParams(
        "Pong", 12560.0, c=0.6, w=(0.5, 0.3, 0.2, 0.0), rho=0.9, intercept_bcm_per_day=0.0
    )
    pp = verify.perfect_prog_hei(st, rain, "Pong", "Pong", p, horizon_days=5)
    assert {
        "date",
        "dam",
        "hei",
        "forced_release_bcm",
        "peak_release_cusecs",
        "release_day1_cusecs",
        "inflow_day1_cusecs",
        "rain_day1_mm",
        "storage_basis",
    } <= set(pp.columns)
    hot = pp[pp.date.between("2023-08-09", "2023-08-14")]
    assert (hot["hei"] > 0).any() and hot["peak_release_cusecs"].max() > 100_000
    assert (pp["release_day1_cusecs"] <= pp["peak_release_cusecs"]).all()
    # the one-day inflow of the run issued on Aug 11 is for Aug 12, the first 120 mm day
    row = pp.set_index("date").loc["2023-08-11"]
    assert row["rain_day1_mm"] == 120.0
    assert row["inflow_day1_cusecs"] > row["release_day1_cusecs"] > 0
    assert (pp["storage_basis"] == "").all()  # the fixture carries no basis column
    arr = verify.routed_forced_release(pp, "Pong")
    assert (arr.station == "Dhilwan").any()


def test_model_carry_bridges_sparse_measurements_and_reanchors():
    # weekly measurements, as the public record has in August 2023: the reservoir is 1.5 BCM
    # below full on Aug 10 and (measured) full on Aug 17, with a heavy spell on Aug 13-15
    st = pd.DataFrame(
        {
            "date": pd.to_datetime(["2023-08-03", "2023-08-10", "2023-08-17", "2023-08-24"]),
            "dam": "Pong",
            "storage_bcm": [4.6, 4.65, 6.11, 5.9],
            "basis": "cwc",
        }
    )
    rain = pd.DataFrame({"date": pd.date_range("2023-07-25", "2023-09-05"), "catchment": "Pong"})
    rain["rain_mm"] = 2.0
    rain.loc[rain.date.between("2023-08-13", "2023-08-15"), "rain_mm"] = 150.0
    p = inflow.InflowParams(
        "Pong", 13637.0, c=0.5, w=(0.4, 0.3, 0.2, 0.1), rho=0.9, intercept_bcm_per_day=-0.02
    )
    given = verify.perfect_prog_hei(st, rain, "Pong", "Pong", p, horizon_days=5)
    assert set(given["date"]) == set(st["date"])  # no gap filling without carry
    pp = verify.perfect_prog_hei(st, rain, "Pong", "Pong", p, horizon_days=5, carry="model")
    pp = pp.set_index("date")
    assert (pp.loc["2023-08-11":"2023-08-16", "storage_basis"] == "model").all()
    assert pp.loc["2023-08-17", "storage_basis"] == "cwc"
    # dry days lose the passage less the intercept; the spell fills the reservoir
    s = verify.carry_storage(
        st.set_index("date")["storage_bcm"], {}, rain.set_index("date")["rain_mm"], "Pong", p
    )[0]
    assert s.loc["2023-08-11"] < 4.65 and s.loc["2023-08-16"] > 5.5
    assert s.loc["2023-08-17"] == 6.11  # the measurement re-anchors
    # the spell forces a first-day release before the next measurement, and the carried path
    # is never above live capacity
    assert (pp.loc["2023-08-13":"2023-08-16", "release_day1_cusecs"] > 0).any()
    assert s.max() <= 6.157 + 1e-9
    # a gap longer than the carry limit is left empty
    far = pd.concat(
        [
            st,
            pd.DataFrame(
                {
                    "date": [pd.Timestamp("2023-09-30")],
                    "dam": "Pong",
                    "storage_bcm": 5.0,
                    "basis": "cwc",
                }
            ),
        ]
    )
    s2 = verify.carry_storage(
        far.set_index("date")["storage_bcm"], {}, rain.set_index("date")["rain_mm"], "Pong", p
    )[0]
    assert pd.Timestamp("2023-09-20") not in s2.index and pd.Timestamp("2023-09-05") in s2.index


def test_routed_next_day_release_places_release_on_the_following_day():
    pp = pd.DataFrame(
        {
            "date": pd.to_datetime(["2023-08-10", "2023-08-13"]),
            "dam": "Pong",
            "release_day1_cusecs": [0.0, 200_000.0],
        }
    )
    arr = verify.routed_next_day_release(pp, "Pong")
    dh = arr[arr.station == "Dhilwan"].set_index("date")["cusecs"]
    # the run issued on Aug 13 forces a release on Aug 14; Pong to Dhilwan is about 41 h,
    # so nothing reaches Dhilwan before Aug 15 and the gap day (Aug 12) carries zero
    assert dh.loc[:"2023-08-14"].max() == 0.0
    assert dh.idxmax() == pd.Timestamp("2023-08-15")
    assert dh.max() == pytest.approx(200_000.0)
    # only the forced spill is routed (lower bound): Bhakra's spill reaches Ropar whole,
    # 18 h downstream, so the Aug 14 release shows at Ropar on Aug 14 (from 18:00) and Aug 15
    ppb = pp.assign(dam="Bhakra", release_day1_cusecs=[0.0, 50_000.0])
    rop = verify.routed_next_day_release(ppb, "Bhakra")
    rop = rop[rop.station == "Ropar Head Works"].set_index("date")["cusecs"]
    assert rop.max() == pytest.approx(50_000.0)
    assert rop.idxmax() == pd.Timestamp("2023-08-14")
    assert rop.loc["2023-08-13"] == 0.0
    assert routing.BHAKRA_CANAL_DRAW_CUSECS == pytest.approx(12_500 + 10_150)
