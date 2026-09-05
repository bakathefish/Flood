from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from punjabflood import constants as C
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


def test_qpf_bias_test_leave_one_season_out():
    # two seasons; the forecast reads half the observed rain in both, so the held-out factor
    # is 2.0 each time and the corrected forecast is exact
    frames, obs_frames = [], []
    for year in (2024, 2025):
        days = pd.date_range(f"{year}-06-01", periods=80)
        o = np.r_[np.full(70, 4.0), np.full(10, 40.0)]
        obs_frames.append(pd.DataFrame({"date": days, "catchment": "Pong", "rain_mm": o}))
        frames.append(
            pd.DataFrame(
                {
                    "target_date": days,
                    "lead_days": 2,
                    "model": "ecmwf_ifs025",
                    "rain_mm": o * 0.5,
                    "catchment": "Pong",
                }
            )
        )
    qb = verify.qpf_bias_test(pd.concat(frames), pd.concat(obs_frames))
    assert len(qb) == 1
    r = qb.iloc[0]
    assert r["n_days"] == 160 and r["n_seasons"] == 2
    assert r["factor_min"] == 2.0 and r["factor_max"] == 2.0 and r["factor_all_seasons"] == 2.0
    assert r["raw_bias_pct"] == pytest.approx(-50.0) and r["corrected_bias_pct"] == pytest.approx(
        0.0
    )
    assert r["raw_hit_rate"] == 0.0 and r["corrected_hit_rate"] == 1.0
    assert r["raw_mae_mm"] > 0 and r["corrected_mae_mm"] == pytest.approx(0.0)
    assert r["heavy_days_obs"] == 20
    # one season only: nothing to hold out, no row
    single = verify.qpf_bias_test(frames[0], obs_frames[0])
    assert single.empty
    # the factor is clipped, so a forecast reading a tenth of the rain is corrected by 2 at most
    tenth = [f.assign(rain_mm=f["rain_mm"] * 0.2) for f in frames]
    clipped = verify.qpf_bias_test(pd.concat(tenth), pd.concat(obs_frames)).iloc[0]
    assert clipped["factor_max"] == verify.QPF_FACTOR_CLIP[1]
    assert clipped["corrected_bias_pct"] == pytest.approx(-80.0)


def _event_inputs():
    days = pd.date_range("2025-08-01", "2025-08-31", freq="D")
    cap = C.PONG.live_capacity_bcm.value
    st = pd.DataFrame(
        {"date": days, "dam": "Pong", "storage_bcm": np.linspace(cap - 0.6, cap - 0.05, len(days))}
    )
    st["basis"] = "cwc"
    rain = pd.DataFrame({"date": pd.date_range("2025-07-20", "2025-09-20"), "catchment": "Pong"})
    rain["rain_mm"] = 2.0
    rain.loc[rain.date.between("2025-08-24", "2025-08-26"), "rain_mm"] = 120.0
    p = inflow.InflowParams(
        "Pong", 12560.0, c=0.6, w=(0.5, 0.3, 0.2, 0.0), rho=0.9, intercept_bcm_per_day=0.0
    )
    return st, rain, p


def _qpf_archive(rain: pd.DataFrame, model: str, shift_days: int, scale: float) -> pd.DataFrame:
    """A synthetic archive: the lead-k forecast for a target day is the observed rain of the
    target day shifted by ``shift_days`` (a forecast that places the event late) and scaled."""
    obs = rain.set_index("date")["rain_mm"]
    frames = []
    for k in range(1, 8):
        shifted = obs.shift(shift_days).fillna(2.0) * scale
        frames.append(
            pd.DataFrame(
                {
                    "target_date": shifted.index,
                    "lead_days": k,
                    "model": model,
                    "rain_mm": shifted.to_numpy(),
                    "catchment": "Pong",
                }
            )
        )
    return pd.concat(frames, ignore_index=True)


def test_as_issued_hei_and_event_summary():
    st, rain, p = _event_inputs()
    pp = verify.perfect_prog_hei(st, rain, "Pong", "Pong", p, horizon_days=5)
    # a perfect archive reproduces the perfect-prognosis run day for day
    exact = _qpf_archive(rain, "ecmwf_ifs025", 0, 1.0)
    ai = verify.as_issued_hei(st, rain, exact, "Pong", "Pong", p, "ecmwf_ifs025", carry="given")
    assert {"model", "qpf_horizon_mm", "obs_horizon_mm", "storage_bcm"} <= set(ai.columns)
    m = ai.merge(pp, on="date", suffixes=("_ai", "_pp"))
    assert len(m) == len(pp) > 0
    assert m["hei_ai"].to_numpy() == pytest.approx(m["hei_pp"].to_numpy())
    assert (m["qpf_horizon_mm"] == m["obs_horizon_mm"]).all()
    # an archive that puts the event two days late and reads half the rain flags later
    late = _qpf_archive(rain, "gfs_seamless", 2, 0.5)
    ai2 = verify.as_issued_hei(st, rain, late, "Pong", "Pong", p, "gfs_seamless", carry="given")
    both = pd.concat([ai, ai2], ignore_index=True)
    rows = verify.as_issued_event_summary(both, pp, 2025, observed_peak_date="2025-08-31")
    by = {r["model"]: r for r in rows}
    ex, gf = by["ecmwf_ifs025"], by["gfs_seamless"]
    assert ex["flagged_days"] > 0 and ex["first_flag_issue_date"] is not None
    assert ex["dam"] == gf["dam"] == "Pong"
    assert ex["pp_first_spill_date"] == gf["pp_first_spill_date"]
    # the exact archive is the perfect-prognosis run: every flag a hit, nothing false or missed
    assert ex["hit_days"] == ex["flagged_days"] and ex["false_flag_days"] == 0
    assert ex["missed_days"] == 0
    first_pp_flag = pp[pp["day_of_exhaustion"].notna()]["date"].min().date().isoformat()
    assert ex["first_flag_issue_date"] == ex["first_hit_issue_date"] == first_pp_flag
    assert ex["pp_first_flag_date"] == first_pp_flag
    # the late, dry archive flags later or not at all, and every flag is a hit or false
    assert gf["first_flag_issue_date"] is None or gf["first_flag_issue_date"] >= first_pp_flag
    assert gf["flagged_days"] <= ex["flagged_days"]
    assert gf["hit_days"] + gf["false_flag_days"] == gf["flagged_days"]
    assert gf["missed_days"] >= ex["flagged_days"] - gf["hit_days"]
    assert ex["observed_peak_date"] == "2025-08-31"
    assert (
        ex["lead_days_to_observed_peak"]
        == (pd.Timestamp("2025-08-31") - pd.Timestamp(ex["first_hit_issue_date"])).days
    )
    assert ex["lead_days_to_pp_spill"] >= 1  # the warning comes before the spill it foresees
    assert ex["first_hit_spill_day"] == ex["lead_days_to_pp_spill"]
    assert ex["max_forecast_peak_release_cusecs"] > 0 and ex["pp_peak_day1_release_cusecs"] > 0
    # a season with nothing in the archive gives no rows; a season outside the window gives
    # zero issue days
    assert verify.as_issued_event_summary(both.iloc[0:0], pp, 2025) == []
    assert verify.as_issued_event_summary(both, pp, 2019)[0]["issue_days"] == 0


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
    s, _, gaps = verify.carry_storage(
        st.set_index("date")["storage_bcm"], {}, rain.set_index("date")["rain_mm"], "Pong", p
    )
    assert s.loc["2023-08-11"] < 4.65 and s.loc["2023-08-16"] > 5.5
    # the re-anchor gap is the model's carried value for the measurement day minus the
    # measurement; the first measurement has nothing carried into it
    assert pd.Timestamp(st["date"].min()) not in gaps and pd.Timestamp("2023-08-17") in gaps
    carried_17 = min(
        s.loc["2023-08-16"]
        + inflow.predict_daily_bcm(
            p,
            [rain.set_index("date")["rain_mm"].loc["2023-08-17"]],
            C.bcm_to_cusec_days(C.cusec_days_to_bcm(C.PONG.turbine_capacity_cusecs.value)),
            rain_mm_recent=rain.set_index("date")["rain_mm"]
            .loc["2023-08-12":"2023-08-16"]
            .to_numpy(),
        )[0]
        - C.cusec_days_to_bcm(C.PONG.turbine_capacity_cusecs.value),
        C.PONG.live_capacity_bcm.value,
    )
    assert gaps[pd.Timestamp("2023-08-17")] == pytest.approx(
        carried_17 - st.set_index("date")["storage_bcm"].loc["2023-08-17"]
    )
    assert "reanchor_gap_bcm" in pp.columns
    assert pp.loc["2023-08-17", "reanchor_gap_bcm"] == pytest.approx(
        gaps[pd.Timestamp("2023-08-17")]
    )
    assert np.isnan(pp.loc["2023-08-12", "reanchor_gap_bcm"])
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


def test_live_horizon_test_scores_each_horizon_against_persistence():
    _, rain, p = _event_inputs()
    rs = rain.set_index("date")["rain_mm"]
    days = pd.date_range("2025-08-05", "2025-08-31", freq="D")
    # an inflow record that follows the model's own rain response, so the observed-rain
    # prediction beats persistence once the spell arrives
    inflow_series = []
    for d in days:
        hist = rs.reindex(pd.date_range(d - pd.Timedelta(days=5), d)).to_numpy()
        inflow_series.append(40_000.0 + C.bcm_to_cusec_days(inflow.quick_response_bcm(p, hist)))
    b = pd.DataFrame({"inflow_cusecs": inflow_series}, index=days)
    archive = _qpf_archive(rain, "ecmwf_ifs025", 0, 1.0)  # a perfect archive
    out = verify.live_horizon_test(
        b, rs, p, archive, "Pong", horizons=(1, 3), models=("ecmwf_ifs025",)
    )
    assert set(out["rain"]) == {"observed rain", "persistence", "ecmwf_ifs025"}
    assert set(out["horizon_days"]) == {1, 3}
    h1 = out[out["horizon_days"] == 1].set_index("rain")
    # the horizon-1 observed-rain leg is the plain live test on the same pairs
    assert h1.loc["observed rain", "n"] == len(days) - 1
    assert h1.loc["observed rain", "mae_cusecs"] < h1.loc["persistence", "mae_cusecs"]
    # a perfect archive reproduces the observed-rain leg
    assert h1.loc["ecmwf_ifs025", "mae_cusecs"] == pytest.approx(
        h1.loc["observed rain", "mae_cusecs"]
    )
    h3 = out[out["horizon_days"] == 3].set_index("rain")
    assert h3.loc["persistence", "n"] == len(days) - 3
    assert h3.loc["observed rain", "mae_cusecs"] < h3.loc["persistence", "mae_cusecs"]


def test_flood_scale_summary_and_variant_verdict():
    cols = verify.FLOOD_SCALE_COLS
    base_fs = pd.DataFrame(
        [
            [
                "Pong",
                "period mean",
                "2025-08-01",
                "2025-08-24",
                77000.0,
                83000.0,
                83000 / 77000,
                19,
                "s",
            ],
            [
                "Pong",
                "period mean",
                "2025-08-25",
                "2025-09-04",
                121600.0,
                137000.0,
                137000 / 121600,
                11,
                "s",
            ],
            [
                "Ranjit Sagar",
                "period mean",
                "2025-08-25",
                "2025-09-04",
                71960.0,
                80000.0,
                80000 / 71960,
                4,
                "s",
            ],
            [
                "Pong",
                "season peak",
                "2025-06-01",
                "2025-09-30",
                349522.0,
                203000.0,
                203000 / 349522,
                112,
                "s",
            ],
            [
                "Bhakra",
                "season peak",
                "2025-06-01",
                "2025-09-30",
                190603.0,
                108000.0,
                108000 / 190603,
                121,
                "s",
            ],
        ],
        columns=cols,
    )
    b = verify.flood_scale_summary(base_fs)
    # the 4-day period is not covered well enough to count
    assert b["n_period_means"] == 2
    assert b["period_mean_worst_deviation"] == pytest.approx(137000 / 121600 - 1)
    assert b["season_peak_ratio_min"] == pytest.approx(108000 / 190603)
    better = base_fs.copy()
    better.loc[better["kind"] == "season peak", "ratio"] += 0.1
    v = verify.flood_scale_summary(better)
    loso = pd.DataFrame(
        {
            "dam": ["Pong", "Bhakra", "Pong", "Bhakra"],
            "variant": ["baseline", "baseline", "excess", "excess"],
            "rmse_bcm": [0.030, 0.043, 0.029, 0.043],
        }
    )
    verdict = verify.variant_verdict(b, v, loso, "excess")
    assert verdict["adopt"] and verdict["dams"] == ["Bhakra", "Pong"]
    # a higher held-out error at one dam is enough to refuse
    loso.loc[3, "rmse_bcm"] = 0.0431
    verdict = verify.variant_verdict(b, v, loso, "excess")
    assert not verdict["loso_error_not_higher"] and not verdict["adopt"]
    assert verdict["season_peaks_higher"] and verdict["period_means_hold"]
    # period means drifting further from the reported means also refuse
    worse = better.copy()
    worse.loc[worse["kind"] == "period mean", "ratio"] += 0.2
    loso.loc[3, "rmse_bcm"] = 0.043
    verdict = verify.variant_verdict(b, verify.flood_scale_summary(worse), loso, "excess")
    assert not verdict["period_means_hold"] and not verdict["adopt"]


def test_carry_storage_runs_on_after_the_last_measurement_for_the_carry_limit():
    _, rain, p = _event_inputs()
    two = pd.Series(
        [4.0, 4.5], index=pd.to_datetime(["2025-08-01", "2025-08-10"]), name="storage_bcm"
    )
    s, basis, gaps = verify.carry_storage(two, {}, rain.set_index("date")["rain_mm"], "Pong", p)
    # the path continues for MAX_CARRY_DAYS after the last measurement and then ends
    last = pd.Timestamp("2025-08-10") + pd.Timedelta(days=verify.MAX_CARRY_DAYS)
    assert s.index.max() == last and basis[last] == "model"
    assert (last + pd.Timedelta(days=1)) not in s.index
    assert s.loc["2025-08-10"] == 4.5 and pd.Timestamp("2025-08-10") in gaps
    # nothing after the last measurement is a re-anchor
    assert max(gaps) == pd.Timestamp("2025-08-10")


def test_routed_next_day_release_places_release_on_the_following_day():
    pp = pd.DataFrame(
        {
            "date": pd.to_datetime(["2023-08-10", "2023-08-13"]),
            "dam": "Pong",
            "release_day1_cusecs": [0.0, 200_000.0],
        }
    )
    arr = verify.routed_next_day_release(pp, "Pong", passage=False)
    dh = arr[arr.station == "Dhilwan"].set_index("date")["cusecs"]
    # the run issued on Aug 13 forces a release on Aug 14; Pong to Dhilwan is about 41 h,
    # so nothing reaches Dhilwan before Aug 15 and the gap day (Aug 12) carries zero
    assert dh.loc[:"2023-08-14"].max() == 0.0
    assert dh.idxmax() == pd.Timestamp("2023-08-15")
    assert dh.max() == pytest.approx(200_000.0)
    # with the passage: spill plus turbines (45,600) less the Mukerian Hydel Channel (11,500)
    arr2 = verify.routed_next_day_release(pp, "Pong", passage=True)
    dh2 = arr2[arr2.station == "Dhilwan"].set_index("date")["cusecs"]
    assert dh2.max() == pytest.approx(200_000.0 + 45_600.0 - 11_500.0)
    assert dh2.loc[:"2023-08-14"].max() == 0.0  # no passage is added on days without spill
    # spill only: Bhakra's spill reaches Ropar whole, 18 h downstream, so the Aug 14 release
    # shows at Ropar on Aug 14 (from 18:00) and Aug 15
    ppb = pp.assign(dam="Bhakra", release_day1_cusecs=[0.0, 50_000.0])
    rop = verify.routed_next_day_release(ppb, "Bhakra", passage=False)
    rop = rop[rop.station == "Ropar Head Works"].set_index("date")["cusecs"]
    assert rop.max() == pytest.approx(50_000.0)
    assert rop.idxmax() == pd.Timestamp("2023-08-14")
    assert rop.loc["2023-08-13"] == 0.0
    assert routing.BHAKRA_CANAL_DRAW_CUSECS == pytest.approx(12_500 + 10_150)
    # Bhakra with passage: turbines minus the Nangal canals is what the Sutlej gets extra
    ropp = verify.routed_next_day_release(ppb, "Bhakra", passage=True)
    ropp = ropp[ropp.station == "Ropar Head Works"]["cusecs"].max()
    assert ropp == pytest.approx(
        50_000.0 + C.BHAKRA.turbine_capacity_cusecs.value - routing.BHAKRA_CANAL_DRAW_CUSECS
    )


def test_flood_scale_inflow_check_compares_like_days():
    days = pd.date_range("2025-08-20", "2025-09-10")
    # the run's inflow_day1 on issue date d is the inflow of d + 1
    pp = pd.DataFrame(
        {
            "date": days,
            "dam": "Pong",
            "inflow_day1_cusecs": 50_000.0 + 1000.0 * np.arange(len(days)),
        }
    )
    periods = pd.DataFrame(
        [
            {
                "dam": "Pong",
                "period_start": "2025-08-25",
                "period_end": "2025-09-04",
                "mean_inflow_cusecs": 121_600.0,
                "source": "PAC",
            }
        ]
    )
    points = pd.DataFrame(
        [{"date": "2025-08-26", "dam": "Pong", "inflow_cusecs": 233_000.0, "source": "PTI"}]
    )
    peaks = pd.DataFrame(
        [{"dam": "Pong", "year": 2025, "peak_inflow_cusecs": 349_522.0, "source": "RS"}]
    )
    rec = pd.DataFrame(
        [{"date": "2023-08-14", "dam": "Pong", "inflow_cusecs": 734_000.0, "source": "EAP"}]
    )
    fs = verify.flood_scale_inflow_check({"Pong": pp}, periods, points, peaks, rec)
    assert list(fs.columns) == verify.FLOOD_SCALE_COLS
    pm = fs[fs["kind"] == "period mean"].iloc[0]
    # inflow days 25 Aug to 4 Sep come from issue dates 24 Aug to 3 Sep: offsets 4 to 14
    expect = float(np.mean([50_000.0 + 1000.0 * k for k in range(4, 15)]))
    assert pm["model_cusecs"] == pytest.approx(expect) and pm["n_days"] == 11
    assert pm["ratio"] == pytest.approx(expect / 121_600.0)
    assert pm["start"] == "2025-08-25" and pm["end"] == "2025-09-04"
    day = fs[fs["kind"] == "day"].iloc[0]
    assert day["model_cusecs"] == pytest.approx(50_000.0 + 1000.0 * 5) and day["n_days"] == 1
    pk = fs[fs["kind"] == "season peak"].iloc[0]
    assert pk["model_cusecs"] == pytest.approx(50_000.0 + 1000.0 * (len(days) - 1))
    assert pk["start"] == "2025-06-01" and pk["n_days"] == len(days)
    rd = fs[fs["kind"] == "record day"].iloc[0]
    # no 2023 run was supplied: the figure is kept, the model value is missing
    assert rd["truth_cusecs"] == 734_000.0 and rd["n_days"] == 0
    assert rd["model_cusecs"] != rd["model_cusecs"] and rd["ratio"] != rd["ratio"]
