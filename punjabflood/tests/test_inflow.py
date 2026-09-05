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
):
    """Storage and rain series generated from the model itself. ``c_wet`` is the extra
    runoff coefficient per 100 mm of rain over the previous ``inflow.API_DAYS`` days."""
    rng = np.random.default_rng(seed)
    rows_state, rows_rain = [], []
    for y in years:
        days = pd.date_range(f"{y}-05-25", f"{y}-09-30", freq="D")
        rain = rng.gamma(0.6, 12.0, size=len(days))  # mm/day, skewed like monsoon rain
        rain[rng.random(len(days)) < 0.45] = 0.0
        rv = inflow.rain_volume_bcm(rain, area_km2)
        storage = 2.0
        base = 0.05  # BCM/day
        for i, d in enumerate(days):
            api = float(rain[max(i - inflow.API_DAYS, 0) : i].sum())
            ci = min(c + c_wet * api / 100.0, inflow.C_MAX)
            quick = sum(ci * w[k] * rv[i - k] for k in range(4) if i - k >= 0)
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
    )
    assert inflow.InflowParams.from_dict(p.to_dict()) == p
    # a parameter file written before rho_raw and the wet coefficient existed still loads
    d = p.to_dict()
    del d["rho_raw"]
    del d["c_wet"]
    del d["api_days"]
    old = inflow.InflowParams.from_dict(d)
    assert np.isnan(old.rho_raw) and old.c_wet == 0.0 and old.api_days == inflow.API_DAYS
