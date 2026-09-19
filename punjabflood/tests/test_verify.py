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
    assert b["n_dated_days"] == 0 and b["dated_day_ratio_median"] != b["dated_day_ratio_median"]
    with_days = pd.concat(
        [
            base_fs,
            pd.DataFrame(
                [
                    ["Pong", "day", "2025-08-31", "2025-08-31", 160276.0, 121294.0, 0.757, 1, "s"],
                    ["Bhakra", "day", "2023-08-23", "2023-08-23", 128406.0, 60147.0, 0.468, 1, "s"],
                    [
                        "Pong",
                        "record day",
                        "2023-08-14",
                        "2023-08-14",
                        734000.0,
                        np.nan,
                        np.nan,
                        0,
                        "s",
                    ],
                ],
                columns=cols,
            ),
        ],
        ignore_index=True,
    )
    d = verify.flood_scale_summary(with_days)
    assert d["n_dated_days"] == 2 and d["dated_day_ratio_median"] == pytest.approx(
        (0.757 + 0.468) / 2
    )
    assert d["n_period_means"] == b["n_period_means"]
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


# --- the soil-moisture anomaly reaches every predictor path -------------------------
def _sm_inputs():
    st, rain, p = _event_inputs()
    rain = rain.copy()
    rain["sm_0_7"] = 0.6  # twice a flat climatology of 0.3: anomaly +1 every day
    wet = inflow.InflowParams(
        "Pong",
        12560.0,
        c=0.6,
        w=(0.5, 0.3, 0.2, 0.0),
        rho=0.9,
        intercept_bcm_per_day=0.0,
        gamma=1.0,
        wetness="api+sm",
        sm_clim=tuple([0.3] * 366),
    )
    return st, rain, p, wet


def test_perfect_prog_and_as_issued_double_the_quick_response_under_a_unit_anomaly():
    st, rain, p, wet = _sm_inputs()
    dry = verify.perfect_prog_hei(st, rain, "Pong", "Pong", p, horizon_days=5)
    sm = verify.perfect_prog_hei(st, rain, "Pong", "Pong", wet, horizon_days=5)
    m = dry.merge(sm, on="date", suffixes=("_dry", "_sm"))
    absorb = verify.hei.absorption_cusecs("Pong")
    base = C.bcm_to_cusec_days(p.intercept_bcm_per_day + C.cusec_days_to_bcm(absorb))
    quick_dry = m["inflow_day1_cusecs_dry"] - base
    quick_sm = m["inflow_day1_cusecs_sm"] - base
    spell = m[m["rain_day1_mm_dry"] > 100]
    assert (quick_sm[spell.index] > 1.9 * quick_dry[spell.index]).all()
    # a params object without a climatology ignores the column entirely
    plain = verify.perfect_prog_hei(st, rain.drop(columns="sm_0_7"), "Pong", "Pong", p, 5)
    assert m["inflow_day1_cusecs_dry"].to_numpy() == pytest.approx(
        plain["inflow_day1_cusecs"].to_numpy()
    )
    exact = _qpf_archive(rain, "ecmwf_ifs025", 0, 1.0)
    ai = verify.as_issued_hei(st, rain, exact, "Pong", "Pong", wet, "ecmwf_ifs025", carry="given")
    m2 = ai.merge(sm, on="date", suffixes=("_ai", "_pp"))
    assert m2["hei_ai"].to_numpy() == pytest.approx(m2["hei_pp"].to_numpy())


def test_carry_storage_and_live_horizons_take_the_anomaly():
    st, rain, p, wet = _sm_inputs()
    rs = rain.set_index("date")["rain_mm"]
    sm = verify.sm_anomaly_series_for(rain, "Pong", wet)
    assert sm is not None and (sm == 1.0).all()
    assert verify.sm_anomaly_series_for(rain, "Pong", p) is None
    two = pd.Series([3.0, 3.5], index=pd.to_datetime(["2025-08-10", "2025-08-28"]))
    s_dry, _, _ = verify.carry_storage(two, {}, rs, "Pong", p)
    s_wet, _, _ = verify.carry_storage(two, {}, rs, "Pong", wet, sm=sm)
    assert s_wet.loc["2025-08-27"] > s_dry.loc["2025-08-27"]  # more of the spell reaches the lake
    days = pd.date_range("2025-08-05", "2025-08-31", freq="D")
    b = pd.DataFrame({"inflow_cusecs": [50_000.0] * len(days)}, index=days)
    out_dry = verify.live_horizon_test(b, rs, wet, None, None, horizons=(1,), models=())
    out_wet = verify.live_horizon_test(b, rs, wet, None, None, horizons=(1,), models=(), sm=sm)
    d = out_dry.set_index("rain").loc["observed rain", "mean_pred_cusecs"]
    w = out_wet.set_index("rain").loc["observed rain", "mean_pred_cusecs"]
    assert w != d  # the anomaly changed both the base removal and the response


# --- two rain sources compared on the days both have ---------------------------------
def test_qpf_model_comparison_pools_common_days_and_applies_the_switch_rule():
    days = pd.date_range("2025-07-01", "2025-08-31")
    obs = pd.DataFrame({"date": days, "catchment": "Pong", "rain_mm": 0.0})
    obs.loc[obs.index % 7 == 0, "rain_mm"] = 50.0  # nine heavy days
    rows = []
    for k in (1, 2, 3):
        for m, hit_every in (("ecmwf_ifs025", 3), ("ecmwf_aifs025_single", 1)):
            f = obs["rain_mm"].to_numpy().copy()
            heavy = np.where(f >= 30)[0]
            f[heavy[::hit_every]] = 40.0  # the hit days
            f[heavy[np.arange(len(heavy)) % hit_every != 0]] = 5.0  # the missed ones
            rows.append(
                pd.DataFrame(
                    {
                        "target_date": days,
                        "lead_days": k,
                        "model": m,
                        "rain_mm": f,
                        "catchment": "Pong",
                    }
                )
            )
    # AIFS also has a season the other model lacks: it must not count
    extra = rows[-1].copy()
    extra["target_date"] = extra["target_date"] + pd.DateOffset(years=1)
    extra["rain_mm"] = 40.0
    obs2 = obs.copy()
    obs2["date"] = obs2["date"] + pd.DateOffset(years=1)
    archive = pd.concat(rows + [extra], ignore_index=True)
    ifs, aifs = "ecmwf_ifs025", "ecmwf_aifs025_single"
    cmp = verify.qpf_model_comparison(
        archive, pd.concat([obs, obs2]), ifs, aifs, catchments=("Pong",)
    )
    assert cmp["n_common_days"] == 3 * len(days)
    assert cmp["challenger"]["hit_rate"] == pytest.approx(1.0)
    assert 0.3 < cmp["incumbent"]["hit_rate"] < 0.5
    assert cmp["switch"] is True
    # a challenger with more false alarms does not switch even with the higher hit rate
    noisy = archive.copy()
    noisy.loc[(noisy["model"] == aifs) & (noisy["rain_mm"] == 0.0), "rain_mm"] = 45.0
    cmp2 = verify.qpf_model_comparison(noisy, obs, ifs, aifs, catchments=("Pong",))
    assert cmp2["challenger"]["false_alarm_ratio"] > cmp2["incumbent"]["false_alarm_ratio"]
    assert cmp2["switch"] is False
    # nothing in common: no verdict
    none = verify.qpf_model_comparison(archive, obs, ifs, "no_such_model", catchments=("Pong",))
    assert none["n_common_days"] == 0 and none["switch"] is False


def test_realtime_vs_final_scores_both_records_and_applies_the_switch_rule():
    days = pd.date_range("2025-06-01", periods=40)
    final = np.r_[np.full(30, 5.0), np.full(10, 40.0)]  # ten heavy days at the end
    frames = []
    for cat in ("Pong", "Bhakra"):
        frames.append(
            pd.DataFrame({"date": days, "catchment": cat, "rain_mm": final, "source": "imd"})
        )
    final_df = pd.concat(frames, ignore_index=True)
    # real-time: close to final, catches every heavy day; ERA5: half of everything
    rt = final_df.copy()
    rt["rain_mm"] = rt["rain_mm"] * 0.9
    rt["source"] = "imd_rt"
    era5 = final_df.copy()
    era5["rain_mm"] = era5["rain_mm"] * 0.5
    era5["source"] = "era5"
    cmp = verify.realtime_vs_final(final_df, rt, era5, catchments=("Pong", "Bhakra"))
    rows = cmp["rows"]
    assert {(r["catchment"], r["record"]) for r in rows} == {
        ("Pong", "imd_rt"),
        ("Pong", "era5"),
        ("Bhakra", "imd_rt"),
        ("Bhakra", "era5"),
    }
    pong_rt = next(r for r in rows if r["catchment"] == "Pong" and r["record"] == "imd_rt")
    pong_era5 = next(r for r in rows if r["catchment"] == "Pong" and r["record"] == "era5")
    assert pong_rt["n_days"] == 40 and pong_rt["hit_rate"] == 1.0 and pong_era5["hit_rate"] == 0.0
    assert pong_rt["mae_mm"] < pong_era5["mae_mm"]
    assert cmp["mae_lower_everywhere"] and cmp["hit_rate_not_lower"] and cmp["switch"]
    # the rule fails when one dam's real-time misses heavy days that ERA5 catches, even
    # with the lower MAE (real-time 29 mm against 40: hit rate 0; ERA5 there at 30: hits)
    bad = rt.copy()
    bad.loc[(bad["catchment"] == "Bhakra") & (bad["rain_mm"] > 30), "rain_mm"] = 29.0
    era5b = era5.copy()
    era5b.loc[(era5b["catchment"] == "Bhakra") & (final_df["rain_mm"] > 30), "rain_mm"] = 30.0
    cmp2 = verify.realtime_vs_final(final_df, bad, era5b, catchments=("Pong", "Bhakra"))
    assert cmp2["mae_lower_everywhere"] and not cmp2["hit_rate_not_lower"] and not cmp2["switch"]
    # a dam with no real-time rows cannot pass
    cmp3 = verify.realtime_vs_final(
        final_df, rt[rt["catchment"] == "Pong"], era5, catchments=("Pong", "Bhakra")
    )
    assert not cmp3["switch"] and cmp3["dams_missing"] == ["Bhakra"]


def test_perfect_prog_hei_takes_a_capacity_and_a_full_reservoir_keeps_filling_into_it():
    cap = C.PONG.live_capacity_bcm.value
    days = pd.date_range("2025-08-20", periods=12)
    state = pd.DataFrame({"date": days, "dam": "Pong", "storage_bcm": cap, "basis": "cwc"})
    rain_days = pd.date_range(days[0] - pd.Timedelta(days=10), days[-1])
    rain = pd.DataFrame({"date": rain_days, "catchment": "Pong", "rain_mm": 25.0})
    p = inflow.InflowParams(
        "Pong", 12560.0, c=0.6, w=(0.5, 0.3, 0.2, 0.0), rho=0.9, intercept_bcm_per_day=0.0
    )
    at_frl = verify.perfect_prog_hei(state, rain, "Pong", "Pong", p, 3)
    with_cushion = verify.perfect_prog_hei(
        state, rain, "Pong", "Pong", p, 3, capacity_bcm=C.cushion_capacity_bcm("Pong")
    )
    assert (at_frl["forced_release_bcm"] > 0).all()
    # the same days, the same inflow, no spill while the cushion holds the volume
    assert (with_cushion["forced_release_bcm"] == 0).all()
    assert with_cushion["inflow_day1_cusecs"].tolist() == pytest.approx(
        at_frl["inflow_day1_cusecs"].tolist()
    )
    # the model carry clamps at the capacity it is given
    s, basis, gaps = verify.carry_storage(
        pd.Series([cap], index=[days[0]]),
        {days[0]: "cwc"},
        rain.set_index("date")["rain_mm"],
        "Pong",
        p,
        capacity_bcm=C.cushion_capacity_bcm("Pong"),
    )
    assert s.max() > cap and s.max() <= C.cushion_capacity_bcm("Pong") + 1e-9


def test_flood_scale_error_from_the_period_means():
    cols = verify.FLOOD_SCALE_COLS
    rows = []
    for i, ratio in enumerate((0.8, 1.0, 1.25, 1.1)):
        rows.append(
            [
                "Pong",
                "period mean",
                "2025-08-01",
                "2025-08-24",
                100.0,
                100.0 * ratio,
                ratio,
                20,
                "s",
            ]
        )
    rows.append(
        ["Pong", "period mean", "2025-09-01", "2025-09-04", 100.0, 300.0, 3.0, 4, "s"]
    )  # too short
    rows.append(["Pong", "day", "2025-08-31", "2025-08-31", 100.0, 50.0, 0.5, 1, "s"])
    rows.append(["Pong", "day", "2025-09-04", "2025-09-04", 100.0, 200.0, 2.0, 1, "s"])
    rows.append(["Pong", "day", "2025-09-05", "2025-09-05", 100.0, 100.0, 1.0, 1, "s"])
    rows.append(["Pong", "record day", "2023-08-14", "2023-08-14", 100.0, np.nan, np.nan, 0, "s"])
    fs = pd.DataFrame(rows, columns=cols)
    e = verify.flood_scale_error(fs)
    logs = np.log([0.8, 1.0, 1.25, 1.1])
    assert e["n_periods"] == 4
    assert e["log_bias"] == pytest.approx(logs.mean())
    assert e["log_sd"] == pytest.approx(logs.std(ddof=1))
    assert e["n_dated_days"] == 3
    assert e["dated_log_sd"] == pytest.approx(np.log([0.5, 2.0, 1.0]).std(ddof=1))
    # fewer than three usable periods: no spread
    e2 = verify.flood_scale_error(fs.iloc[:2])
    assert e2["n_periods"] == 2 and e2["log_sd"] != e2["log_sd"]


def test_rule_curve_run_fires_before_the_frl_bound_and_the_timing_test_reads_the_opening():
    from punjabflood import reservoirs

    frl = C.BHAKRA.frl_m.value
    cap = C.BHAKRA.live_capacity_bcm.value
    levels = np.linspace(frl - 40.0, frl, 200)
    rating = reservoirs.Rating.fit("Bhakra", levels, cap - (frl - levels) * 0.1)
    # a reservoir sitting a little below FRL through August, rain that keeps it there
    days = pd.date_range("2023-08-05", periods=20)
    s_at = float(rating.storage((1672.0) * C.FOOT_M))
    state = pd.DataFrame({"date": days, "dam": "Bhakra", "storage_bcm": s_at, "basis": "cwc"})
    rain_days = pd.date_range(days[0] - pd.Timedelta(days=10), days[-1] + pd.Timedelta(days=6))
    rain = pd.DataFrame({"date": rain_days, "catchment": "Bhakra", "rain_mm": 1.5})
    p = inflow.InflowParams(
        "Bhakra", 56000.0, c=0.5, w=(0.5, 0.3, 0.2, 0.0), rho=0.9, intercept_bcm_per_day=0.0
    )
    pp_frl = verify.perfect_prog_hei(state, rain, "Bhakra", "Bhakra", p, 3)
    pp_rule = verify.perfect_prog_hei(
        state, rain, "Bhakra", "Bhakra", p, 3, rule_curve_rating=rating
    )
    assert (pp_frl["forced_release_bcm"] == 0).all()
    # 1,672 ft is above the schedule (1,670 up to 15 August): the drawdown is owed at once,
    # and stops being owed once the line to FRL passes the reservoir in the third week
    before = pd.to_datetime(pp_rule["date"]) <= "2023-08-15"
    assert (pp_rule.loc[before, "release_day1_cusecs"] > 0).all()
    assert (pp_rule.loc[~before, "release_day1_cusecs"] == 0).any()
    assert pp_rule["inflow_day1_cusecs"].tolist() == pytest.approx(
        pp_frl["inflow_day1_cusecs"].tolist()
    )
    openings = pd.DataFrame({"dam": ["Bhakra"], "date": ["2023-08-13"], "level_ft": [1672.0]})
    t = verify.rule_curve_timing_test(pp_frl, pp_rule, openings, "Bhakra")
    r = t.iloc[0]
    assert r["year"] == 2023 and r["schedule_level_ft"] == 1670.0 and r["frl_ft"] == 1680.0
    assert r["first_forced_frl"] is None and r["lag_frl_days"] is None
    # the first run is issued on 5 August, its release lands on the 6th: seven days early
    assert r["first_forced_rule"] == "2023-08-06" and r["lag_rule_days"] == -7
    # an opening with no run in its year gets no forced day either way
    t2 = verify.rule_curve_timing_test(
        pp_frl,
        pp_rule,
        pd.DataFrame({"dam": ["Bhakra"], "date": ["2015-08-10"], "level_ft": [1661.1]}),
        "Bhakra",
    )
    assert t2.iloc[0]["n_days_rule"] == 0 and t2.iloc[0]["first_forced_rule"] is None


def test_routed_vs_gauge_readings_pairs_by_station_and_day():
    arr = pd.DataFrame(
        {
            "station": ["Dhilwan", "Dhilwan", "Harike Head Works"],
            "date": pd.to_datetime(["2023-08-17", "2023-08-18", "2023-08-18"]),
            "cusecs": [120_000.0, 110_000.0, 140_000.0],
        }
    )
    readings = pd.DataFrame(
        {
            "date": ["2023-08-17", "2023-08-18", "2023-08-18", "2023-08-19"],
            "station": ["Dhilwan", "Dhilwan", "Harike Head Works", "Dhilwan"],
            "discharge_cusecs": [234_000, 220_000, 284_987, 200_000],
            "ambiguous": [False, True, False, False],
            "as_of_time": ["", "evening", "", ""],
        }
    )
    t = verify.routed_vs_gauge_readings(arr, readings, stations=("Dhilwan", "Harike Head Works"))
    assert len(t) == 3  # the ambiguous row is left out
    d = t[t["station"] == "Dhilwan"].set_index("date")
    assert d.loc["2023-08-17", "ratio"] == pytest.approx(120_000 / 234_000)
    assert np.isnan(d.loc["2023-08-19", "routed_cusecs"]) and np.isnan(d.loc["2023-08-19", "ratio"])
    assert t[t["station"] == "Harike Head Works"]["ratio"].iloc[0] == pytest.approx(
        140_000 / 284_987
    )


def test_qpf_blend_test_scores_the_blends_on_common_rows_and_applies_the_rule():
    days = pd.date_range("2025-07-01", "2025-08-31")
    obs = np.zeros(len(days))
    obs[::7] = 50.0  # nine heavy days
    obs_df = pd.DataFrame({"date": days, "catchment": "Pong", "rain_mm": obs})
    rows = []
    for k in (1, 2, 3):
        # AIFS hits every heavy day at 40; IFS and GFS miss them all at 5, and are dry
        # otherwise: the mean of the three is 16.7 on a heavy day, below the threshold
        for m, val in (
            ("ecmwf_aifs025_single", 40.0),
            ("ecmwf_ifs025", 5.0),
            ("gfs_seamless", 5.0),
        ):
            f = np.where(obs >= 30, val, 0.0)
            rows.append(
                pd.DataFrame(
                    {
                        "target_date": days,
                        "lead_days": k,
                        "model": m,
                        "rain_mm": f,
                        "catchment": "Pong",
                    }
                )
            )
    # a second season so the leave-one-season-out weights exist
    second = [r.assign(target_date=r["target_date"] + pd.DateOffset(years=1)) for r in rows]
    obs2 = obs_df.assign(date=obs_df["date"] + pd.DateOffset(years=1))
    q = pd.concat(rows + second, ignore_index=True)
    res = verify.qpf_blend_test(q, pd.concat([obs_df, obs2]), incumbent="ecmwf_aifs025_single")
    assert res["n_common_days"] == 2 * 3 * len(days)
    s = res["scores"]
    assert s["ecmwf_aifs025_single"]["hit_rate"] == 1.0
    assert s["equal_mean"]["hit_rate"] == 0.0 and s["equal_mean"]["passes_rule"] is False
    assert s["max_of_models"]["hit_rate"] == 1.0 and s["max_of_models"]["passes_rule"] is False
    assert "inverse_mae_weighted_loso" in s
    assert s["inverse_mae_weighted_loso"]["passes_rule"] is False
    assert res["adopt"] is None
    assert abs(sum(res["weights_all_seasons"].values()) - 1.0) < 1e-9


def test_qpf_blend_test_with_no_common_rows_is_empty():
    days = pd.date_range("2025-07-01", "2025-07-31")
    q = pd.DataFrame(
        {
            "target_date": days,
            "lead_days": 1,
            "model": "ecmwf_aifs025_single",
            "rain_mm": 1.0,
            "catchment": "Pong",
        }
    )
    obs = pd.DataFrame({"date": days, "catchment": "Pong", "rain_mm": 0.0})
    res = verify.qpf_blend_test(q, obs)
    assert res["n_common_days"] == 0 and res["adopt"] is None and res["scores"] == {}


def _toy_archive(days, model_vals, catchment="Pong"):
    rows = []
    for k in (1, 2, 3):
        for m, series in model_vals.items():
            rows.append(
                pd.DataFrame(
                    {
                        "target_date": days,
                        "lead_days": k,
                        "model": m,
                        "rain_mm": series,
                        "catchment": catchment,
                    }
                )
            )
    return pd.concat(rows, ignore_index=True)


def test_weather_watch_hindcast_quiet_season_has_no_watch_days():
    days = pd.date_range("2024-06-01", "2024-09-30")
    q = _toy_archive(
        days, {"ecmwf_ifs025": np.full(len(days), 1.0), "gfs_seamless": np.full(len(days), 1.0)}
    )
    clim = {"Pong": np.linspace(0, 100, 1001)}
    res = verify.weather_watch_hindcast(q, clim, events={}, models=("ecmwf_ifs025", "gfs_seamless"))
    rows = res["rows"]
    assert len(rows) > 0
    assert set(rows["level"]) == {"quiet"}
    s = res["seasons"]
    assert s[0]["catchment"] == "Pong" and s[0]["year"] == 2024
    assert s[0]["watch_share"] == 0.0 and s[0]["alert_share"] == 0.0
    assert res["events"] == []


def test_weather_watch_hindcast_heavy_day_in_one_model_is_a_watch_and_alert_has_a_lead():
    days = pd.date_range("2025-06-01", "2025-09-30")
    ifs = np.full(len(days), 1.0)
    gfs = np.full(len(days), 1.0)
    # one model sees 40 mm on 10 July: a watch on the issue dates whose leads 1-3 cover it
    gfs[days.get_loc("2025-07-10")] = 40.0
    # the primary sees 70, 70, 70 on 20-22 August: a three-day total of 210 above the 90th pct
    for d in ("2025-08-20", "2025-08-21", "2025-08-22"):
        ifs[days.get_loc(d)] = 70.0
    q = _toy_archive(days, {"ecmwf_ifs025": ifs, "gfs_seamless": gfs})
    clim = {"Pong": np.linspace(0, 100, 1001)}  # 90th pct is 90 mm
    events = {"Pong": "2025-08-24"}
    res = verify.weather_watch_hindcast(
        q, clim, events=events, models=("ecmwf_ifs025", "gfs_seamless"), primary="ecmwf_ifs025"
    )
    rows = res["rows"].set_index("issue_date")
    assert rows.loc["2025-07-09", "level"] == "watch"  # lead 1 covers the 10th
    assert rows.loc["2025-07-07", "level"] == "watch"  # lead 3 covers the 10th
    assert rows.loc["2025-07-06", "level"] == "quiet"
    assert rows.loc["2025-08-19", "level"] == "alert"  # leads 1-3 are 20, 21, 22
    ev = res["events"][0]
    assert ev["catchment"] == "Pong" and ev["event_date"] == "2025-08-24"
    # issued on the 18th the leads cover 19, 20, 21: a total of 141 mm, above the 90th pct
    assert ev["first_alert_issue_date"] == "2025-08-18" and ev["alert_lead_days"] == 6
    # issued on the 17th the leads cover 18, 19, 20: one heavy day, a watch
    assert ev["first_watch_issue_date"] == "2025-08-17" and ev["watch_lead_days"] == 7
    s = res["seasons"][0]
    # the July watch days lie outside the event window, so they count as false alarms
    assert s["false_alarm_days"] == 3 and s["n_issue_days"] > 100
    # the watch rose inside the window, so the lead is a measurement, not a bound
    assert ev["watch_raised_before_window"] is False
    assert ev["alert_raised_before_window"] is False
    # issue dates 17 to 21 August are raised (the 22nd covers 23 to 25, one heavy day and
    # a low total, the 23rd nothing); 18 to 20 are alerts
    assert ev["days_at_watch_before"] == 5 and ev["days_at_alert_before"] == 3


def test_weather_watch_hindcast_marks_a_lead_bounded_by_the_window():
    days = pd.date_range("2025-06-01", "2025-09-30")
    ifs = np.full(len(days), 1.0)
    # the primary sees 70 mm a day from 1 August to 23 August: an alert on every issue
    # date from 29 July onward, so the window of 14 days before the 24th opens already raised
    for d in pd.date_range("2025-08-01", "2025-08-23"):
        ifs[days.get_loc(d)] = 70.0
    q = _toy_archive(days, {"ecmwf_ifs025": ifs, "gfs_seamless": np.full(len(days), 1.0)})
    clim = {"Pong": np.linspace(0, 100, 1001)}
    res = verify.weather_watch_hindcast(
        q,
        clim,
        events={"Pong": "2025-08-24"},
        models=("ecmwf_ifs025", "gfs_seamless"),
        primary="ecmwf_ifs025",
    )
    ev = res["events"][0]
    assert ev["first_alert_issue_date"] == "2025-08-10" and ev["alert_lead_days"] == 14
    assert ev["alert_raised_before_window"] is True
    assert ev["watch_raised_before_window"] is True
    # issued on the 22nd the leads cover 23 to 25: one heavy day, a watch; the 23rd is quiet
    assert ev["days_at_alert_before"] == 12 and ev["days_at_watch_before"] == 13


# --- the snowmelt term through the verification runs --------------------------------
def _melt_inputs():
    st, rain, p = _event_inputs()
    rain = rain.copy()
    rain["melt_bcm"] = 0.01  # a flat melt volume every day
    withm = inflow.InflowParams(
        "Pong",
        12560.0,
        c=p.c,
        w=p.w,
        rho=p.rho,
        intercept_bcm_per_day=p.intercept_bcm_per_day,
        c_melt=0.5,
        w_melt=(0.6, 0.4, 0.0, 0.0),
    )
    return st, rain, p, withm


def test_perfect_prog_and_carry_add_the_melt_term_where_the_parameters_carry_one():
    st, rain, p, withm = _melt_inputs()
    plain = verify.perfect_prog_hei(st, rain, "Pong", "Pong", p, horizon_days=5)
    melt = verify.perfect_prog_hei(st, rain, "Pong", "Pong", withm, horizon_days=5)
    m = plain.merge(melt, on="date", suffixes=("_plain", "_melt"))
    # a flat 0.01 BCM melt through 0.5 * (0.6 + 0.4) adds 0.005 BCM a day
    extra = m["inflow_day1_cusecs_melt"] - m["inflow_day1_cusecs_plain"]
    assert extra.to_numpy() == pytest.approx(C.bcm_to_cusec_days(0.005), rel=1e-6)
    # a parameter set without the term ignores the column, and the term without a column
    # melts nothing
    assert verify.melt_series_for(rain, "Pong", p) is None
    assert verify.melt_series_for(rain.drop(columns="melt_bcm"), "Pong", withm) is None
    none = verify.perfect_prog_hei(st, rain.drop(columns="melt_bcm"), "Pong", "Pong", withm, 5)
    assert none["inflow_day1_cusecs"].to_numpy() == pytest.approx(
        plain["inflow_day1_cusecs"].to_numpy()
    )
    # the model carry between measurements gains the same volume each day
    rs = rain.set_index("date")["rain_mm"]
    ms = verify.melt_series_for(rain, "Pong", withm)
    two = pd.Series([3.0, 3.5], index=pd.to_datetime(["2025-08-10", "2025-08-28"]))
    s0, _, _ = verify.carry_storage(two, {}, rs, "Pong", p)
    s1, _, _ = verify.carry_storage(two, {}, rs, "Pong", withm, melt=ms)
    assert s1.loc["2025-08-15"] - s0.loc["2025-08-15"] == pytest.approx(5 * 0.005, abs=1e-9)


def test_variant_verdict_can_be_restricted_to_the_dams_a_variant_touches():
    loso = pd.DataFrame(
        {
            "dam": ["Pong", "Bhakra", "Bhakra"],
            "variant": ["baseline", "baseline", "snowmelt"],
            "rmse_bcm": [0.030, 0.043, 0.042],
        }
    )
    b = {"season_peak_ratio_min": 0.5, "period_mean_worst_deviation": 0.3}
    v = {"season_peak_ratio_min": 0.6, "period_mean_worst_deviation": 0.3}
    verdict = verify.variant_verdict(b, v, loso, "snowmelt", dams=("Bhakra",))
    assert verdict["dams"] == ["Bhakra"] and verdict["adopt"]
    # without the filter the same table gives the same dams (the variant has only Bhakra)
    assert verify.variant_verdict(b, v, loso, "snowmelt")["dams"] == ["Bhakra"]
    # a dam the variant has no row for is not scored
    assert verify.variant_verdict(b, v, loso, "snowmelt", dams=("Pong",))["adopt"] is False


def test_melt_window_warns_once_per_gap(caplog):
    melt = pd.Series(1.0, index=pd.date_range("2015-01-01", "2015-12-31"))
    verify._MELT_GAPS_LOGGED.clear()
    with caplog.at_level("WARNING", logger="punjabflood.verify"):
        a = verify._melt_window(melt, pd.date_range("2015-12-28", "2016-01-03"))
        b = verify._melt_window(melt, pd.date_range("2015-12-29", "2016-01-04"))
        c = verify._melt_window(melt, pd.date_range("2016-06-01", "2016-06-04"))
    assert a.tolist() == [1.0, 1.0, 1.0, 1.0, 0.0, 0.0, 0.0]
    assert b[-1] == 0.0 and c.tolist() == [0.0] * 4
    msgs = [r.getMessage() for r in caplog.records if "melt series" in r.getMessage()]
    assert len(msgs) == 1, msgs
    assert "2016-01-01" in msgs[0]
