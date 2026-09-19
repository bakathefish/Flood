from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from punjabflood import constants as C
from punjabflood import inflow


def _synthetic(
    dam="Pong",
    area_km2=12560.0,
    c=0.55,
    w=(0.5, 0.3, 0.15, 0.05),
    rho=0.9,
    outflow_bcm=0.03,
    seed=0,
    years=(2001, 2002, 2003, 2004, 2005),
    c_wet=0.0,
    c_excess=0.0,
    w_excess=(0.7, 0.3, 0.0, 0.0),
    threshold_mm=inflow.EXCESS_THRESHOLD_MM,
    rain_scale=12.0,
):
    """Storage and rain series generated from the model itself. ``c_wet`` is the extra
    runoff coefficient per 100 mm of rain over the previous ``inflow.API_DAYS`` days. With
    ``c_excess`` the rain above ``threshold_mm`` responds through ``c_excess`` and
    ``w_excess`` and only the rest through ``c`` and ``w``."""
    rng = np.random.default_rng(seed)
    rows_state, rows_rain = [], []
    for y in years:
        days = pd.date_range(f"{y}-05-25", f"{y}-09-30", freq="D")
        rain = rng.gamma(0.6, rain_scale, size=len(days))  # mm/day, skewed like monsoon rain
        rain[rng.random(len(days)) < 0.45] = 0.0
        base_mm, ex_mm = inflow.split_excess(rain, threshold_mm if c_excess > 0 else None)
        rv = inflow.rain_volume_bcm(base_mm, area_km2)
        ev = inflow.rain_volume_bcm(ex_mm, area_km2)
        storage = 2.0
        base = 0.05  # BCM/day
        for i, d in enumerate(days):
            api = float(rain[max(i - inflow.API_DAYS, 0) : i].sum())
            ci = min(c + c_wet * api / 100.0, inflow.C_MAX)
            quick = sum(ci * w[k] * rv[i - k] for k in range(4) if i - k >= 0)
            quick += sum(c_excess * w_excess[k] * ev[i - k] for k in range(4) if i - k >= 0)
            base = base * rho + 0.05 * (1 - rho)  # relaxes towards a mean base
            infl = base + quick
            storage = storage + infl - outflow_bcm
            rows_state.append({"date": d, "dam": dam, "storage_bcm": storage, "basis": "cwc"})
            rows_rain.append({"date": d, "rain_mm": rain[i], "sm_0_7": 0.3 + 0.002 * rain[i]})
    return pd.DataFrame(rows_state), pd.DataFrame(rows_rain)


def test_calibration_recovers_runoff_coefficient_and_lags():
    state, rain = _synthetic()
    p = inflow.calibrate(state, rain, "Pong", 12560.0)
    assert abs(p.c - 0.55) / 0.55 < 0.10, p
    assert abs(p.w[0] - 0.5) < 0.08 and abs(p.w[1] - 0.3) < 0.08
    assert abs(sum(p.w) - 1.0) < 1e-9
    assert p.r2 > 0.9
    assert p.n_days > 300
    assert 0.5 < p.rho < 0.99
    # no wetness dependence was generated, so none should be found
    assert p.c_wet < 0.05


def test_calibration_recovers_wetness_dependence():
    state, rain = _synthetic(c=0.35, c_wet=0.5, seed=4)
    p = inflow.calibrate(state, rain, "Pong", 12560.0)
    assert abs(p.c - 0.35) < 0.06, p
    assert abs(p.c_wet - 0.5) < 0.12, p
    assert p.api_days == inflow.API_DAYS
    # the coefficient in use rises with antecedent rain and is capped at C_MAX
    assert inflow.coefficient(p, api_mm=0.0) == pytest.approx(p.c)
    assert inflow.coefficient(p, api_mm=100.0) == pytest.approx(min(p.c + p.c_wet, inflow.C_MAX))
    assert inflow.coefficient(p, api_mm=1e6) == inflow.C_MAX


def test_calibration_recovers_the_excess_response():
    state, rain = _synthetic(c=0.4, c_excess=0.8, seed=11, years=range(2001, 2013), rain_scale=20.0)
    p = inflow.calibrate(state, rain, "Pong", 12560.0, excess_threshold_mm=30.0)
    assert p.has_excess and p.excess_threshold_mm == 30.0
    assert abs(p.c - 0.4) < 0.08, p
    assert abs(p.c_excess - 0.8) < 0.2, p
    assert abs(p.w_excess[0] - 0.7) < 0.15 and abs(sum(p.w_excess) - 1.0) < 1e-9, p
    # the plain response cannot follow the heavy days as well
    p0 = inflow.calibrate(state, rain, "Pong", 12560.0)
    assert not p0.has_excess and p0.w_excess == ()
    assert p0.rmse_bcm > p.rmse_bcm
    # the fitted relation reproduces its own calibration residuals
    df = inflow.design_matrix(state, rain, "Pong", 12560.0, excess_threshold_mm=30.0)
    resid = df["ds"].to_numpy() - inflow.predict_storage_change(p, df)
    assert float(np.sqrt(np.mean(resid**2))) == pytest.approx(p.rmse_bcm)


def test_excess_fit_on_linear_data_matches_the_plain_coefficient():
    # no excess mechanism was generated, so the rain above the threshold responds with the
    # same coefficient as the rest, and the held-out error is the same either way
    state, rain = _synthetic(seed=0, years=range(2001, 2011), rain_scale=20.0)
    p = inflow.calibrate(state, rain, "Pong", 12560.0, excess_threshold_mm=30.0)
    assert abs(p.c - 0.55) < 0.1 and abs(p.c_excess - 0.55) < 0.2, p
    a = inflow.loso_score(state, rain, "Pong", 12560.0)
    b = inflow.loso_score(state, rain, "Pong", 12560.0, excess_threshold_mm=30.0)
    assert a["n_seasons"] == 10 and a["n_days"] == len(
        inflow.design_matrix(state, rain, "Pong", 12560.0)
    )
    assert a["n_heavy_days"] > 20 and a["n_heavy_days"] == b["n_heavy_days"]
    assert abs(a["rmse_bcm"] - b["rmse_bcm"]) / a["rmse_bcm"] < 0.1
    assert a["heavy_rmse_bcm"] > 0 and abs(a["heavy_bias_bcm"]) < a["heavy_rmse_bcm"]


def test_quick_response_with_excess_splits_the_day():
    common = dict(c=0.4, w=(1.0, 0.0, 0.0, 0.0), rho=0.9, intercept_bcm_per_day=0.0)
    plain = inflow.InflowParams("Pong", 12560.0, **common)
    ex = inflow.InflowParams(
        "Pong",
        12560.0,
        **common,
        c_excess=0.8,
        w_excess=(1.0, 0.0, 0.0, 0.0),
        excess_threshold_mm=30.0,
    )
    hist = np.array([0.0, 0.0, 0.0, 0.0, 0.0, 50.0])
    vol = lambda mm: inflow.rain_volume_bcm(mm, 12560.0)  # noqa: E731
    assert inflow.quick_response_bcm(plain, hist) == pytest.approx(0.4 * vol(50.0))
    assert inflow.quick_response_bcm(ex, hist) == pytest.approx(0.4 * vol(30.0) + 0.8 * vol(20.0))
    # below the threshold the two agree
    light = np.array([0.0, 0.0, 0.0, 0.0, 0.0, 20.0])
    assert inflow.quick_response_bcm(ex, light) == pytest.approx(
        inflow.quick_response_bcm(plain, light)
    )


def test_quick_response_uses_antecedent_rain():
    p = inflow.InflowParams(
        "Pong",
        12560.0,
        c=0.4,
        w=(1.0, 0.0, 0.0, 0.0),
        rho=0.9,
        intercept_bcm_per_day=0.0,
        c_wet=0.4,
    )
    dry = inflow.quick_response_bcm(p, np.array([0, 0, 0, 0, 0, 50.0]))
    wet = inflow.quick_response_bcm(p, np.array([20, 20, 20, 20, 20, 50.0]))
    assert dry == pytest.approx(0.4 * inflow.rain_volume_bcm(50.0, 12560.0))
    # five antecedent days of 20 mm = 100 mm -> coefficient 0.4 + 0.4
    assert wet == pytest.approx(0.8 * inflow.rain_volume_bcm(50.0, 12560.0))
    # a short history uses what it has
    assert inflow.quick_response_bcm(p, np.array([50.0])) == pytest.approx(dry)


def test_calibration_excludes_spilling_days():
    state, rain = _synthetic()
    cap = C.PONG.live_capacity_bcm.value
    # push a block of days to full: those days carry no rain signal and must be dropped
    full = state.index[100:140]
    state.loc[full, "storage_bcm"] = cap
    p = inflow.calibrate(state, rain, "Pong", 12560.0)
    assert abs(p.c - 0.55) / 0.55 < 0.12


def test_calibration_uses_measured_storage_rows_only():
    state, rain = _synthetic()
    # rating-derived rows (bulletin levels through the rating) carry flat-step artefacts;
    # here they are pure garbage and must not touch the fit
    rng = np.random.default_rng(5)
    junk = state.iloc[-120:].copy()
    junk["date"] = junk["date"] + pd.Timedelta(days=400)
    junk["storage_bcm"] = rng.uniform(1.0, 6.0, len(junk))
    junk["basis"] = "bbmb"
    p_clean = inflow.calibrate(state, rain, "Pong", 12560.0)
    p_junk = inflow.calibrate(pd.concat([state, junk], ignore_index=True), rain, "Pong", 12560.0)
    assert p_junk.n_days == p_clean.n_days
    assert p_junk.c == pytest.approx(p_clean.c)
    assert p_junk.rho == pytest.approx(p_clean.rho)
    # without a basis column every row is used
    p_nobasis = inflow.calibrate(state.drop(columns="basis"), rain, "Pong", 12560.0)
    assert p_nobasis.n_days == p_clean.n_days


def test_recession_ratio_is_kept_unclipped_in_the_parameters():
    state, rain = _synthetic()
    p = inflow.calibrate(state, rain, "Pong", 12560.0)
    assert p.rho_raw == p.rho_raw  # a number, not nan, on this long clean series
    assert p.rho == pytest.approx(min(max(p.rho_raw, *inflow.RHO_CLIP[:1]), inflow.RHO_CLIP[1]))
    idx = pd.date_range("2000-06-01", periods=500, freq="D")
    walk = pd.Series(np.cumsum(np.random.default_rng(2).normal(size=500)), index=idx)
    assert inflow.recession_ratio(walk) > 0.99  # a random walk drifts; the ratio exceeds the clip
    assert inflow.estimate_recession(walk) == inflow.RHO_CLIP[1]
    assert np.isnan(inflow.recession_ratio(walk.iloc[:20]))


def test_prediction_volume_is_sum_of_daily_and_base_decays():
    p = inflow.InflowParams(
        "Pong", 12560.0, c=0.5, w=(1.0, 0.0, 0.0, 0.0), rho=0.8, intercept_bcm_per_day=0.0
    )
    daily = inflow.predict_daily_bcm(p, [0.0, 0.0, 0.0], base_cusecs=100_000)
    b = C.cusec_days_to_bcm(100_000)
    assert np.allclose(daily, [b * 0.8, b * 0.64, b * 0.512])
    v = inflow.volume_bcm(p, [0.0, 0.0, 0.0], 100_000, horizon_days=2)
    assert v == pytest.approx(b * (0.8 + 0.64))
    # 100 mm over the whole catchment at c = 0.5 adds 0.5 * 100 * 12560 * 1e-6 BCM today
    daily2 = inflow.predict_daily_bcm(p, [100.0], base_cusecs=0.0)
    assert daily2[0] == pytest.approx(0.5 * 100 * 12560 * 1e-6)
    # with a wet coefficient the forecast days feed the antecedent index of later days
    pw = inflow.InflowParams(
        "Pong",
        12560.0,
        c=0.5,
        w=(1.0, 0.0, 0.0, 0.0),
        rho=0.8,
        intercept_bcm_per_day=0.0,
        c_wet=0.5,
    )
    d3 = inflow.predict_daily_bcm(pw, [100.0, 100.0], base_cusecs=0.0)
    assert d3[0] == pytest.approx(0.5 * 100 * 12560 * 1e-6)  # no antecedent rain yet
    assert d3[1] == pytest.approx(min(0.5 + 0.5 * 100 / 100, inflow.C_MAX) * 100 * 12560 * 1e-6)


def test_base_from_observed_removes_recent_quick_flow():
    p = inflow.InflowParams(
        "Pong", 12560.0, c=0.5, w=(0.5, 0.5, 0.0, 0.0), rho=0.9, intercept_bcm_per_day=0.0
    )
    # yesterday 20 mm, today 0 mm -> quick today = 0.5 * 0.5 * 20 mm volume
    q_bcm = 0.5 * 0.5 * inflow.rain_volume_bcm(20.0, 12560.0)
    obs = 60_000.0
    base = inflow.base_from_observed(p, obs, rain_mm_recent=[20.0, 0.0])
    assert base == pytest.approx(obs - C.bcm_to_cusec_days(q_bcm))
    assert inflow.base_from_observed(p, 1.0, rain_mm_recent=[200.0, 200.0]) == 0.0


def test_recession_estimator_is_robust_to_measurement_noise():
    rng = np.random.default_rng(3)
    n = 6000  # the ratio estimator's sampling error is about 0.035 at this length
    phi = 0.9
    sig = np.zeros(n)
    for i in range(1, n):
        sig[i] = phi * sig[i - 1] + rng.normal(0, 1.0)
    noise = rng.normal(0, 2.0, n)  # noise variance four times the innovation variance
    idx = pd.date_range("2000-06-01", periods=n, freq="D")
    res = pd.Series(sig + noise, index=idx)
    est = inflow.estimate_recession(res)
    assert abs(est - phi) < 0.08, est
    # the naive lag-1 autocorrelation is badly biased low on the same series
    naive = float(res.autocorr(1))
    assert naive < 0.75
    # too short or structureless -> default
    assert inflow.estimate_recession(res.iloc[:20]) == inflow.DEFAULT_RHO
    white = pd.Series(rng.normal(size=500), index=pd.date_range("2000-01-01", periods=500))
    assert inflow.estimate_recession(white) == inflow.DEFAULT_RHO


def test_params_round_trip():
    p = inflow.InflowParams(
        "Bhakra",
        52765.0,
        0.4,
        (0.6, 0.3, 0.1, 0.0),
        0.93,
        -0.01,
        gamma=0.2,
        n_days=500,
        r2=0.8,
        rmse_bcm=0.01,
        rho_raw=0.93,
        c_wet=0.2,
        resid_acf1=0.3,
        c_excess=0.7,
        w_excess=(0.8, 0.2, 0.0, 0.0),
        excess_threshold_mm=30.0,
    )
    assert inflow.InflowParams.from_dict(p.to_dict()) == p
    assert p.to_dict()["w_excess"] == [0.8, 0.2, 0.0, 0.0]
    # a parameter file written before rho_raw, the wet coefficient, the residual
    # persistence and the excess response existed still loads
    d = p.to_dict()
    for k in (
        "rho_raw",
        "c_wet",
        "api_days",
        "resid_acf1",
        "c_excess",
        "w_excess",
        "excess_threshold_mm",
    ):
        del d[k]
    old = inflow.InflowParams.from_dict(d)
    assert np.isnan(old.rho_raw) and old.c_wet == 0.0 and old.api_days == inflow.API_DAYS
    assert np.isnan(old.resid_acf1)
    assert old.w_excess == () and not old.has_excess


def test_residual_acf1_recovers_ar1_persistence():
    rng = np.random.default_rng(7)
    n = 3000
    e = np.empty(n)
    e[0] = rng.normal()
    for t in range(1, n):
        e[t] = 0.7 * e[t - 1] + np.sqrt(1 - 0.7**2) * rng.normal()
    res = pd.Series(e, index=pd.date_range("2000-01-01", periods=n))
    assert inflow.residual_acf1(res) == pytest.approx(0.7, abs=0.05)
    white = pd.Series(rng.normal(size=n), index=pd.date_range("2000-01-01", periods=n))
    assert abs(inflow.residual_acf1(white)) < 0.05
    assert np.isnan(inflow.residual_acf1(res.iloc[:20]))
    # only consecutive days count: a series sampled every other day has no lag-1 pairs
    sparse = pd.Series(e[:200], index=pd.date_range("2000-01-01", periods=200, freq="2D"))
    assert np.isnan(inflow.residual_acf1(sparse))


# --- soil moisture as the wetness carrier ------------------------------------------
def _params(**kw):
    base = dict(
        dam="Pong",
        area_km2=12560.0,
        c=0.5,
        w=(1.0, 0.0, 0.0, 0.0),
        rho=0.9,
        intercept_bcm_per_day=0.0,
    )
    base.update(kw)
    return inflow.InflowParams(**base)


def test_sm_climatology_and_anomaly():
    idx = pd.date_range("2015-01-01", "2017-12-31")
    flat = pd.Series(0.3, index=idx)
    clim = inflow.sm_climatology(flat)
    assert clim.shape == (366,) and np.allclose(clim, 0.3)
    assert np.allclose(inflow.sm_anomaly_series(flat, clim), 0.0)
    s = flat.copy()
    s.loc["2016-07-15"] = 0.6
    clim2 = inflow.sm_climatology(s)
    doy = pd.Timestamp("2016-07-15").dayofyear - 1
    assert 0.3 < clim2[doy] < 0.31  # a 31-day window over three years barely moves it
    a = inflow.sm_anomaly_series(s, clim2)
    assert 0.9 < a.loc["2016-07-15"] < 1.0 and abs(a.loc["2016-07-14"]) < 0.02
    # the anomaly is clipped to [-0.9, 3] and missing values give no anomaly
    big = pd.Series([10.0, np.nan], index=pd.to_datetime(["2016-01-01", "2016-01-02"]))
    assert inflow.sm_anomaly_series(big, clim).iloc[0] == 3.0
    assert np.isnan(inflow.sm_anomaly_series(big, clim).iloc[1])
    p = _params(sm_clim=tuple(clim))
    assert inflow.sm_anomaly(p, 0.6, pd.Timestamp("2016-07-15")) == pytest.approx(1.0)
    assert inflow.sm_anomaly(p, float("nan"), pd.Timestamp("2016-07-15")) == 0.0
    assert inflow.sm_anomaly(_params(), 0.6, pd.Timestamp("2016-07-15")) == 0.0  # no climatology


def _synthetic_sm(gamma=1.0, c=0.45, seed=7, years=range(2001, 2011), c_wet=0.0):
    """Like ``_synthetic`` with a seasonal soil-moisture series whose fractional anomaly
    multiplies the coefficient by ``1 + gamma * anomaly``: wet years run wetter all season."""
    rng = np.random.default_rng(seed)
    area = 12560.0
    w = (0.5, 0.3, 0.15, 0.05)
    days_all = pd.date_range(f"{min(years)}-01-01", f"{max(years)}-12-31")
    season_curve = 0.25 + 0.08 * np.sin(2 * np.pi * (days_all.dayofyear - 120) / 365.25)
    year_offset = {y: rng.uniform(-0.35, 0.35) for y in years}
    scale = np.array([1 + year_offset[d.year] for d in days_all])
    sm = pd.Series(season_curve * scale, index=days_all)
    sm = sm * (1 + 0.03 * rng.standard_normal(len(sm)))
    clim = inflow.sm_climatology(sm)
    anom = inflow.sm_anomaly_series(sm, clim)
    rows_state, rows_rain = [], []
    for y in years:
        days = pd.date_range(f"{y}-05-25", f"{y}-09-30", freq="D")
        rain = rng.gamma(0.6, 12.0, size=len(days))
        rain[rng.random(len(days)) < 0.45] = 0.0
        rv = inflow.rain_volume_bcm(rain, area)
        storage, base = 2.0, 0.05
        for i, d in enumerate(days):
            api = float(rain[max(i - inflow.API_DAYS, 0) : i].sum())
            ci = min(c + c_wet * api / 100.0, inflow.C_MAX) * (1 + gamma * float(anom.loc[d]))
            quick = sum(ci * w[k] * rv[i - k] for k in range(4) if i - k >= 0)
            base = base * 0.9 + 0.05 * 0.1
            storage = storage + base + quick - 0.03
            rows_state.append({"date": d, "dam": "Pong", "storage_bcm": storage, "basis": "cwc"})
        for d in pd.date_range(f"{y}-01-01", f"{y}-12-31"):
            r = rain[(days == d).argmax()] if d in days else 0.0
            rows_rain.append({"date": d, "rain_mm": r, "sm_0_7": sm.loc[d]})
    return pd.DataFrame(rows_state), pd.DataFrame(rows_rain)


def test_calibration_recovers_soil_moisture_sensitivity_under_each_wetness_carrier():
    state, rain = _synthetic_sm(gamma=1.0)
    p_api = inflow.calibrate(state, rain, "Pong", 12560.0)
    assert p_api.wetness == "api" and p_api.gamma == 0.0 and p_api.sm_clim == ()
    p_both = inflow.calibrate(state, rain, "Pong", 12560.0, wetness="api+sm")
    assert p_both.wetness == "api+sm" and len(p_both.sm_clim) == 366
    assert abs(p_both.gamma - 1.0) < 0.3, p_both.gamma
    assert abs(p_both.c - 0.45) < 0.08
    p_sm = inflow.calibrate(state, rain, "Pong", 12560.0, wetness="sm")
    assert p_sm.wetness == "sm" and p_sm.c_wet == 0.0 and abs(p_sm.gamma - 1.0) < 0.3
    # the soil-moisture carrier explains what the rain index cannot: lower in-sample error
    assert p_both.rmse_bcm < p_api.rmse_bcm
    # round trip keeps the climatology and the carrier
    back = inflow.InflowParams.from_dict(p_both.to_dict())
    assert back.wetness == "api+sm" and np.allclose(back.sm_clim, p_both.sm_clim)


def test_predict_storage_change_and_quick_response_apply_gamma():
    p = _params(gamma=1.0, sm_clim=tuple([0.3] * 366))
    df = pd.DataFrame({"lag0": [0.1], "lag1": [0.0], "lag2": [0.0], "lag3": [0.0], "api_mm": [0.0]})
    df["sm_anom"] = 0.5
    assert inflow.predict_storage_change(p, df)[0] == pytest.approx(0.5 * 0.1 * 1.5)
    df["sm_anom"] = 0.0
    assert inflow.predict_storage_change(p, df)[0] == pytest.approx(0.05)
    assert inflow.predict_storage_change(p, df.drop(columns="sm_anom"))[0] == pytest.approx(0.05)
    q0 = inflow.quick_response_bcm(p, np.array([0.0, 0.0, 0.0, 10.0]))
    q1 = inflow.quick_response_bcm(p, np.array([0.0, 0.0, 0.0, 10.0]), sm_anom=1.0)
    assert q1 == pytest.approx(2 * q0)


def test_loso_score_takes_the_wetness_carrier_and_scores_each_fold_with_its_own_climatology():
    state, rain = _synthetic_sm(gamma=1.0, years=range(2001, 2007))
    base = inflow.loso_score(state, rain, "Pong", 12560.0)
    both = inflow.loso_score(state, rain, "Pong", 12560.0, wetness="api+sm")
    assert base["n_seasons"] == both["n_seasons"] >= 5
    assert both["rmse_bcm"] < base["rmse_bcm"]


def _synthetic_inflow(c=0.4, w=(0.5, 0.3, 0.15, 0.05), c_wet=0.2, base_bcm=0.06, seed=3, n=60):
    """A daily inflow series generated by the model itself over one season: base plus the
    wetness-dependent quick response, in cusecs, with the rain that made it."""
    rng = np.random.default_rng(seed)
    area = 12560.0
    days = pd.date_range("2026-07-15", periods=n + 10)
    rain = rng.gamma(0.6, 12.0, size=len(days))
    rain[rng.random(len(days)) < 0.45] = 0.0
    rv = inflow.rain_volume_bcm(rain, area)
    infl = []
    for i in range(len(days)):
        api = float(rain[max(i - inflow.API_DAYS, 0) : i].sum())
        ci = min(c + c_wet * api / 100.0, inflow.C_MAX)
        quick = sum(ci * w[k] * rv[i - k] for k in range(4) if i - k >= 0)
        infl.append(base_bcm + quick)
    obs = pd.Series(C.bcm_to_cusec_days(np.array(infl[10:])), index=days[10:])
    rain_df = pd.DataFrame({"date": days, "rain_mm": rain})
    return obs, rain_df, area


def test_calibrate_on_inflow_recovers_the_response_and_scores_the_storage_fit():
    obs, rain, area = _synthetic_inflow()
    p = inflow.calibrate_on_inflow(obs, rain, "Pong", area)
    assert p.n_days == 60 and p.basis == "inflow"
    assert abs(p.c - 0.4) < 0.05 and abs(p.c_wet - 0.2) < 0.06, (p.c, p.c_wet)
    assert abs(p.w[0] - 0.5) < 0.08 and abs(p.w[1] - 0.3) < 0.08
    assert abs(p.intercept_bcm_per_day - 0.06) < 0.01
    assert p.r2 > 0.95
    # the storage-change convention: a fit with half the coefficient and base minus passage
    absorb = 45_600.0
    half = inflow.InflowParams(
        "Pong",
        area,
        c=0.2,
        w=(0.5, 0.3, 0.15, 0.05),
        rho=0.9,
        intercept_bcm_per_day=0.06 - C.cusec_days_to_bcm(absorb),
        c_wet=0.1,
    )
    s = inflow.score_on_inflow(half, obs, rain, area, absorb)
    assert s["n_days"] == 60 and s["bias_pct"] < -5 and s["pearson_r"] > 0.9
    assert s["mae_cusecs"] > 0
    assert s["coefficient_ratio"] == pytest.approx(p.c / 0.2, rel=0.15)
    # with the base fitted on these days the half-coefficient set is unbiased but flatter
    s3 = inflow.score_on_inflow(half, obs, rain, area, absorb, fitted_base=True)
    assert abs(s3["bias_pct"]) < 1e-6 and s3["mae_cusecs"] < s["mae_cusecs"]
    assert s3["mae_cusecs"] > 0
    # the inflow fit itself scores without bias on its own days
    s2 = inflow.score_on_inflow(p, obs, rain, area, absorb, base_from_intercept=True)
    assert abs(s2["bias_pct"]) < 2
    # too few days is an error, not a fit
    with pytest.raises(ValueError):
        inflow.calibrate_on_inflow(obs.iloc[:10], rain, "Pong", area)


def test_inflow_fit_in_storage_convention_scores_the_storage_record_out_of_sample():
    state, rain = _synthetic(c=0.55, outflow_bcm=0.03)
    absorb = C.bcm_to_cusec_days(0.03)
    p_store = inflow.calibrate(state, rain, "Pong", 12560.0)
    # an inflow-basis set with the true response and the true base
    p_in = inflow.InflowParams(
        "Pong",
        12560.0,
        c=0.55,
        w=(0.5, 0.3, 0.15, 0.05),
        rho=0.9,
        intercept_bcm_per_day=0.05,
        basis="inflow",
    )
    q = inflow.as_storage_basis(p_in, absorb)
    assert q.basis == "storage" and q.intercept_bcm_per_day == pytest.approx(0.05 - 0.03)
    assert inflow.as_storage_basis(p_store, absorb) is p_store
    s_true = inflow.storage_change_score(q, state, rain, "Pong", 12560.0)
    s_fit = inflow.storage_change_score(p_store, state, rain, "Pong", 12560.0)
    assert s_true["n_seasons"] == 5 and s_true["n_days"] > 300
    # the true response scores about as well as the fit on its own record
    assert s_true["rmse_bcm"] < s_fit["rmse_bcm"] * 1.2
    # a wrong response scores worse
    bad = inflow.InflowParams(
        "Pong", 12560.0, c=0.2, w=(0.25,) * 4, rho=0.9, intercept_bcm_per_day=0.02
    )
    assert (
        inflow.storage_change_score(bad, state, rain, "Pong", 12560.0)["rmse_bcm"]
        > s_true["rmse_bcm"] * 1.5
    )


def test_sm_climatology_fills_the_leap_day_when_the_record_has_none():
    # pandas 3 returns a read-only view from to_numpy; the leap-day fill must write to a copy
    idx = pd.date_range("2001-01-01", "2003-12-31", freq="D")
    sm = pd.Series(np.linspace(0.2, 0.3, len(idx)), index=idx)
    clim = inflow.sm_climatology(sm)
    assert clim.shape == (366,)
    assert np.isfinite(clim).all()


# --- the snowmelt term ------------------------------------------------------------------


def _synthetic_melt(c_melt=0.6, w_melt=(0.5, 0.3, 0.2, 0.0), seed=21, years=range(2001, 2011)):
    """The plain synthetic record with a daily melt volume on the rain frame and, when
    ``c_melt`` is above zero, its lagged response added to the storage change. The melt is a
    smooth seasonal hump with noise, so it is not collinear with the rain."""
    state, rain = _synthetic(seed=seed, years=years)
    rng = np.random.default_rng(seed + 1)
    d = pd.to_datetime(rain["date"])
    doy = d.dt.dayofyear.to_numpy()
    melt_bcm = 0.02 * np.exp(-(((doy - 190) / 40.0) ** 2)) * (1 + 0.5 * rng.random(len(doy)))
    rain = rain.copy()
    rain["melt_bcm"] = melt_bcm
    if c_melt > 0:
        s = state.set_index("date")
        add = pd.Series(0.0, index=s.index)
        m = pd.Series(melt_bcm, index=d)
        for k, wk in enumerate(w_melt):
            add = add + c_melt * wk * m.shift(k).fillna(0.0).reindex(s.index).fillna(0.0)
        # the storage is a running sum of inflow, so the response accumulates within a season
        for y in years:
            sel = s.index.year == y
            s.loc[sel, "storage_bcm"] += add[sel].cumsum().to_numpy()
        state = s.reset_index()
    return state, rain


def test_design_matrix_carries_zero_melt_columns_without_a_melt_series():
    state, rain = _synthetic()
    df = inflow.design_matrix(state, rain, "Pong", 12560.0)
    assert [f"melt{k}" for k in inflow.LAGS] == [c for c in df.columns if c.startswith("melt")]
    assert (df[[f"melt{k}" for k in inflow.LAGS]] == 0).all().all()


def test_melt_fit_without_a_melt_mechanism_leaves_the_response_alone():
    state, rain = _synthetic_melt(c_melt=0.0)
    p0 = inflow.calibrate(state, rain, "Pong", 12560.0)
    p1 = inflow.calibrate(state, rain, "Pong", 12560.0, melt=True)
    assert not p0.has_melt and p0.w_melt == () and p0.c_melt == 0.0
    assert p1.has_melt and len(p1.w_melt) == len(inflow.LAGS)
    assert abs(p1.c - p0.c) < 0.05, (p0.c, p1.c)
    # nothing to explain, so the term stays near zero
    assert p1.c_melt < 0.15, p1.c_melt


def test_melt_fit_recovers_a_planted_coefficient():
    state, rain = _synthetic_melt(c_melt=0.6, w_melt=(0.5, 0.3, 0.2, 0.0))
    p = inflow.calibrate(state, rain, "Pong", 12560.0, melt=True)
    assert abs(p.c_melt - 0.6) < 0.15, p.c_melt
    assert abs(sum(p.w_melt) - 1.0) < 1e-9
    assert abs(p.c - 0.55) < 0.08, p.c
    # the fitted relation reproduces its own calibration residuals
    df = inflow.design_matrix(state, rain, "Pong", 12560.0)
    resid = df["ds"].to_numpy() - inflow.predict_storage_change(p, df)
    assert float(np.sqrt(np.mean(resid**2))) == pytest.approx(p.rmse_bcm)
    # without the term the fit is worse, in sample and held out
    p0 = inflow.calibrate(state, rain, "Pong", 12560.0)
    assert p0.rmse_bcm > p.rmse_bcm
    a = inflow.loso_score(state, rain, "Pong", 12560.0)
    b = inflow.loso_score(state, rain, "Pong", 12560.0, melt=True)
    assert a["n_days"] == b["n_days"] and b["rmse_bcm"] < a["rmse_bcm"]


def test_quick_response_adds_the_melt_history():
    common = dict(c=0.4, w=(1.0, 0.0, 0.0, 0.0), rho=0.9, intercept_bcm_per_day=0.0)
    plain = inflow.InflowParams("Bhakra", 56980.0, **common)
    withm = inflow.InflowParams(
        "Bhakra", 56980.0, **common, c_melt=0.5, w_melt=(0.6, 0.4, 0.0, 0.0)
    )
    hist = np.array([0.0, 0.0, 0.0, 0.0, 0.0, 10.0])
    melt = np.array([0.01, 0.02])  # BCM, oldest first, index -1 = today
    base = inflow.quick_response_bcm(plain, hist)
    assert inflow.quick_response_bcm(plain, hist, melt_bcm_history=melt) == pytest.approx(base)
    assert inflow.quick_response_bcm(withm, hist, melt_bcm_history=melt) == pytest.approx(
        base + 0.5 * (0.6 * 0.02 + 0.4 * 0.01)
    )
    assert inflow.quick_response_bcm(withm, hist) == pytest.approx(base)


def test_melt_params_round_trip_and_old_files_load():
    p = inflow.InflowParams(
        "Bhakra",
        56980.0,
        0.4,
        (0.6, 0.3, 0.1, 0.0),
        0.9,
        0.0,
        r2=0.5,
        rmse_bcm=0.01,
        rho_raw=0.9,
        resid_acf1=0.2,
        excess_threshold_mm=30.0,
        c_melt=0.3,
        w_melt=(0.5, 0.5, 0.0, 0.0),
    )
    assert inflow.InflowParams.from_dict(p.to_dict()) == p and p.has_melt
    d = p.to_dict()
    del d["c_melt"]
    del d["w_melt"]
    old = inflow.InflowParams.from_dict(d)
    assert old.c_melt == 0.0 and old.w_melt == () and not old.has_melt


def test_baseline_is_unchanged_by_a_melt_column_it_does_not_use():
    state, rain = _synthetic_melt(c_melt=0.6)
    with_col = inflow.calibrate(state, rain, "Pong", 12560.0)
    without = inflow.calibrate(state, rain.drop(columns="melt_bcm"), "Pong", 12560.0)
    assert not with_col.has_melt and not without.has_melt
    assert with_col.c == without.c and with_col.w == without.w
    assert with_col.intercept_bcm_per_day == without.intercept_bcm_per_day
    d1 = inflow.design_matrix(state, rain, "Pong", 12560.0)
    d2 = inflow.design_matrix(state, rain.drop(columns="melt_bcm"), "Pong", 12560.0)
    pd.testing.assert_frame_equal(d1.drop(columns=[c for c in d1 if c.startswith("melt")]),
                                  d2.drop(columns=[c for c in d2 if c.startswith("melt")]))


def test_base_from_observed_subtracts_the_melt_response_when_the_term_is_carried():
    state, rain = _synthetic_melt(c_melt=0.6)
    p = inflow.calibrate(state, rain, "Pong", 12560.0, melt=True)
    assert p.c_melt > 0
    recent = np.zeros(8)
    without = inflow.base_from_observed(p, 20000.0, recent)
    with_melt = inflow.base_from_observed(p, 20000.0, recent, melt_bcm_recent=[0.02] * 8)
    assert with_melt < without
