from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from punjabflood import constants as C
from punjabflood import forecast, inflow

BULLETIN_TEXT = """BBMB Reservoir Data
Bhakra Dam
FRL- 1680 ft
Latest BBMB Reservoir Data
as on 04-09-2026 18:00 Hrs.
Reservoir Level
(Feet)
Bhakra  1641.20  57297  26338
Pong  1371.16  84766  22202
"""


class Rating:
    def __init__(self, slope, intercept):
        self.slope, self.intercept = slope, intercept

    def storage(self, level_m):
        return np.asarray(level_m) * self.slope + self.intercept


def test_parse_bulletin_text():
    rec = forecast.parse_bulletin_text(BULLETIN_TEXT)
    assert rec["as_on_date"] == "04-09-2026" and rec["as_on_time"] == "18:00"
    assert rec["bhakra_level_ft"] == 1641.2 and rec["pong_inflow_cusecs"] == 84766
    assert rec["pong_outflow_cusecs"] == 22202


def _inputs(storage_frac=0.99, qpf_mm=80.0):
    cap = C.PONG.live_capacity_bcm.value
    states = {
        "Pong": {
            "level_ft": 1389.0,
            "level_m": 1389 * C.FOOT_M,
            "storage_bcm": cap * storage_frac,
            "inflow_cusecs": 60_000,
            "outflow_cusecs": 20_000,
            "basis": "test",
        }
    }
    dates = pd.date_range("2026-09-05", periods=6)
    det = pd.concat(
        [
            pd.DataFrame({"target_date": dates, "model": m, "rain_mm": qpf_mm, "catchment": "Pong"})
            for m in ("gfs_seamless", "ecmwf_ifs025")
        ]
        + [
            pd.DataFrame(
                {
                    "target_date": dates,
                    "model": "best_match",
                    "rain_mm": 30.0,
                    "catchment": "Ghaggar Khanauri",
                }
            )
        ],
        ignore_index=True,
    )
    ens = pd.concat(
        [
            pd.DataFrame(
                {
                    "target_date": dates,
                    "member": k,
                    "rain_mm": qpf_mm * (0.5 + k / 10),
                    "catchment": "Pong",
                    "model": "ecmwf_ifs025",
                }
            )
            for k in range(11)
        ],
        ignore_index=True,
    )
    params = {
        "Pong": inflow.InflowParams(
            "Pong",
            12560.0,
            c=0.6,
            w=(0.5, 0.3, 0.2, 0.0),
            rho=0.9,
            intercept_bcm_per_day=0.0,
            rmse_bcm=0.03,
            resid_acf1=0.3,
        )
    }
    return states, det, ens, params


def test_build_product_full_reservoir_forces_release_and_routes_it():
    states, det, ens, params = _inputs()
    prod = forecast.build_product(
        "2026-09-04",
        states,
        det,
        ens,
        {"Pong": [0.0, 0.0, 0.0]},
        params,
        ghaggar_climatology={"Ghaggar Khanauri": np.arange(0, 200, 1.0)},
    )
    pong = prod["dams"]["Pong"]
    assert pong["ensemble"]["5"]["p_exhaustion"] == 1.0
    # the model's own error is sampled on top of the QPF spread; with 1% of headroom and
    # 80 mm days it changes nothing here, but the fields are on the record
    assert pong["ensemble"]["5"]["p_exhaustion_model_error"] == 1.0
    assert pong["ensemble"]["5"]["n_error_draws"] == 200
    assert pong["ensemble"]["5"]["error_sd_bcm_per_day"] == 0.03
    assert pong["deterministic"]["ecmwf_ifs025"]["horizons"]["1"]["day_of_exhaustion"] == 1
    assert max(pong["forced_release_median_cusecs_by_day"]) > 100_000
    stations = {r["station"]: r for r in prod["reaches"]}
    assert "Dhilwan" in stations and "Harike Head Works" in stations
    assert stations["Dhilwan"]["peak_class"] in {"medium", "high"}
    # on a spill day the river gets the spill plus the turbine passage the water balance
    # assumed, less the Mukerian Hydel Channel; Dhilwan is pure translation, so its peak is
    # that of the release
    assert stations["Dhilwan"]["peak_cusecs"] == pytest.approx(
        max(pong["forced_release_median_cusecs_by_day"]) + 45_600 - 11_500
    )
    assert stations["Harike Head Works"]["peak_date"] >= "2026-09-07"  # 72 h after the release
    assert prod["ghaggar"]["Ghaggar Khanauri"]["qpf_3day_mm"]["best_match"] == 90.0
    assert prod["ghaggar"]["Ghaggar Khanauri"]["qpf_3day_percentile"]["best_match"] == 45.0
    assert prod["disclaimer"].startswith("Hazard watch")
    json.dumps(prod, default=str)  # serialisable
    md = forecast.render_markdown(prod)
    assert "Not an official warning" in md and "Dhilwan" in md
    assert "QPF spread and model error" in md and "| 5 | 1.00 | 1.00 |" in md


def test_build_product_empty_reservoir_no_release():
    states, det, ens, params = _inputs(storage_frac=0.5, qpf_mm=5.0)
    prod = forecast.build_product("2026-09-04", states, det, ens, {}, params)
    pong = prod["dams"]["Pong"]
    assert pong["ensemble"]["5"]["p_exhaustion"] == 0.0
    assert pong["ensemble"]["5"]["p_exhaustion_model_error"] == 0.0
    # only today's outflow continues downstream, less the Mukerian Hydel Channel's 11,500
    # cusecs at the Shah Nehar barrage: 8,500 cusecs is below every WRD low band
    dh = [r for r in prod["reaches"] if r["station"] == "Dhilwan"][0]
    assert dh["peak_cusecs"] == 20_000 - 11_500 and dh["peak_class"] is None


def test_dam_state_from_bulletin_uses_rating():
    rec = forecast.parse_bulletin_text(BULLETIN_TEXT)
    ratings = {"Bhakra": Rating(0.1, -45.0), "Pong": Rating(0.2, -80.0)}
    st = forecast.dam_state_from_bulletin(rec, ratings)
    assert set(st) == {"Bhakra", "Pong"}
    assert st["Pong"]["storage_bcm"] == float(1371.16 * C.FOOT_M * 0.2 - 80.0)
    assert st["Bhakra"]["inflow_cusecs"] == 57297


def test_write_outputs(tmp_path):
    states, det, ens, params = _inputs()
    prod = forecast.build_product("2026-09-04", states, det, ens, {}, params)
    jp, mp = forecast.write_outputs(prod, tmp_path)
    assert jp.exists() and mp.exists()
    assert json.loads(jp.read_text(encoding="utf-8"))["issue_date"] == "2026-09-04"
    # a second run on the same issue date never rewrites the first record
    first = jp.read_text(encoding="utf-8")
    prod2 = dict(prod, generated_utc="2026-09-04T09:15:00+00:00", disclaimer="changed")
    jp2, mp2 = forecast.write_outputs(prod2, tmp_path)
    assert jp2 != jp and jp2.name == "2026-09-04_rerun_20260904T091500.json"
    assert jp.read_text(encoding="utf-8") == first
    jp3, _ = forecast.write_outputs(prod2, tmp_path)
    assert jp3.name == "2026-09-04_rerun_20260904T091500_2.json"
    # latest.json follows the newest run and names the dated record it copies
    latest = json.loads((tmp_path / "latest.json").read_text(encoding="utf-8"))
    assert latest["record"] == jp3.name
    assert latest["disclaimer"] == "changed"
    assert latest["issue_date"] == "2026-09-04"


def test_climatology_round_trip_and_missing_file(tmp_path):
    days = pd.date_range("2001-05-25", "2001-10-05", freq="D")
    rain = pd.DataFrame(
        {
            "date": list(days) * 2,
            "catchment": ["Ghaggar Khanauri"] * len(days) + ["Ghaggar Bhankarpur"] * len(days),
            "rain_mm": 1.0,
        }
    )
    rain.loc[rain["catchment"] == "Ghaggar Khanauri", "rain_mm"] = np.arange(len(days)) * 0.1
    clim = forecast.ghaggar_climatology(rain)
    # season days only, 3-day rolling totals, both catchments present
    n_season = int(days.month.isin([6, 7, 8, 9]).sum())
    assert set(clim) == {"Ghaggar Khanauri", "Ghaggar Bhankarpur"}
    assert len(clim["Ghaggar Khanauri"]) == n_season
    assert clim["Ghaggar Bhankarpur"] == pytest.approx(np.full(n_season, 3.0))
    p = tmp_path / "clim.json"
    forecast.save_climatology(clim, p, years="2001-2001")
    back = forecast.load_climatology(p)
    assert back["Ghaggar Khanauri"] == pytest.approx(clim["Ghaggar Khanauri"], abs=0.005)
    assert json.loads(p.read_text(encoding="utf-8"))["years"] == "2001-2001"
    assert forecast.load_climatology(tmp_path / "absent.json") is None


def test_build_product_takes_the_soil_moisture_anomaly_and_records_it():
    states, det, ens, params = _inputs(storage_frac=0.8, qpf_mm=40.0)
    wet = inflow.InflowParams(
        "Pong",
        12560.0,
        c=0.6,
        w=(0.5, 0.3, 0.2, 0.0),
        rho=0.9,
        intercept_bcm_per_day=0.0,
        rmse_bcm=0.03,
        resid_acf1=0.3,
        gamma=1.0,
        wetness="api+sm",
        sm_clim=tuple([0.3] * 366),
    )
    soil = {"Pong": {"date": "2026-09-01", "sm_0_7": 0.6}}
    dry = forecast.build_product("2026-09-04", states, det, ens, {"Pong": [0.0] * 6}, params)
    sm = forecast.build_product(
        "2026-09-04", states, det, ens, {"Pong": [0.0] * 6}, {"Pong": wet}, soil_moisture=soil
    )
    e = sm["dams"]["Pong"]
    assert e["soil_moisture"] == {
        "date": "2026-09-01",
        "sm_0_7": 0.6,
        "anomaly": 1.0,
        "age_days": 3,
        "wetness": "api+sm",
    }
    a = dry["dams"]["Pong"]["deterministic"]["ecmwf_ifs025"]["inflow_bcm_by_day"]
    b = e["deterministic"]["ecmwf_ifs025"]["inflow_bcm_by_day"]
    assert b[0] > a[0]  # the quick response doubles; the base is the bulletin's, unchanged here
    assert "soil_moisture" not in dry["dams"]["Pong"]
    md = forecast.render_markdown(sm)
    assert "soil moisture" in md.lower() and "2026-09-01" in md
    # no record for the dam: nothing recorded, anomaly zero
    none = forecast.build_product(
        "2026-09-04", states, det, ens, {}, {"Pong": wet}, soil_moisture={}
    )
    assert "soil_moisture" not in none["dams"]["Pong"]


def test_recent_rain_takes_imd_days_where_present_and_the_model_elsewhere(tmp_path):
    from punjabflood import imdrain

    class Client:
        def forecast_daily(self, lat, lon, models, days, issue_date=None, past_days=0):
            t = pd.date_range(
                pd.Timestamp(issue_date) - pd.Timedelta(days=past_days), periods=past_days + days
            )
            return {
                "time": [x.date().isoformat() for x in t],
                "precipitation_sum": [1.0] * len(t),  # one model: the bare key
            }

    # one toy catchment with IMD weights on two lattice nodes
    from shapely.geometry import box

    from punjabflood import catchments as cm

    poly = box(75.9, 30.9, 76.35, 31.35)
    pts = cm.sample_grid(poly)
    pts[imdrain.IMD_WEIGHT_COL] = pts["weight_km2"]
    cat = cm.Catchment("Toy", 1, poly, cm.geodesic_area_km2(poly), frozenset({1}), pts)
    issue = pd.Timestamp("2026-09-10")
    want = [issue - pd.Timedelta(days=k) for k in range(forecast.RECENT_DAYS, 0, -1)]
    # the real-time grid has the last three of the six days, 20 mm on every node
    grid_days = want[-3:]

    def fetch(days, rt_dir):
        for d in grid_days:
            g = np.full((imdrain.RT_LAT.size, imdrain.RT_LON.size), 20.0, dtype="<f4")
            imdrain.realtime_path(d, rt_dir).write_bytes(g.tobytes())
        return [d for d in days if d in grid_days]

    def fake_client_daily(*a, **k):  # the FakeClient above wraps a dict under "daily"
        return {"daily": Client().forecast_daily(*a, **k)}

    class C2:
        forecast_daily = staticmethod(fake_client_daily)

    recent, sources = forecast.recent_rain(
        C2(), {"Toy": cat}, issue.date().isoformat(), rt_dir=tmp_path, fetch=fetch, record="imd_rt"
    )
    assert recent["Toy"] == pytest.approx([1.0, 1.0, 1.0, 20.0, 20.0, 20.0])
    assert sources["Toy"] == ["best_match"] * 3 + ["imd_rt"] * 3
    # with the incumbent record the grid is not even consulted
    calls = []
    only_model, src_model = forecast.recent_rain(
        C2(),
        {"Toy": cat},
        issue.date().isoformat(),
        rt_dir=tmp_path,
        fetch=lambda days, rt_dir: calls.append(1),
        record="best_match",
    )
    assert only_model["Toy"] == pytest.approx([1.0] * 6) and src_model["Toy"] == ["best_match"] * 6
    assert calls == []
    # a catchment without IMD weights is served by the model only
    cat2 = cm.Catchment(
        "Plain",
        2,
        poly,
        cm.geodesic_area_km2(poly),
        frozenset({2}),
        pts.drop(columns=[imdrain.IMD_WEIGHT_COL]),
    )
    recent2, sources2 = forecast.recent_rain(
        C2(),
        {"Plain": cat2},
        issue.date().isoformat(),
        rt_dir=tmp_path,
        fetch=fetch,
        record="imd_rt",
    )
    assert sources2["Plain"] == ["best_match"] * 6


def test_markdown_names_the_source_of_each_recent_day():
    states, det, ens, params = _inputs()
    recent = {d: [0.0, 0.0, 0.0, 5.0, 12.5, 30.0] for d in states}
    prod = forecast.build_product("2026-09-04", states, det, ens, recent, params)
    prod["recent_rain_source"] = {d: ["best_match"] * 3 + ["imd_rt"] * 3 for d in states}
    md = forecast.render_markdown(prod)
    assert (
        "Observed rain of the previous 6 days: 3 from the IMD real-time grid, 3 from the "
        "best_match model's past days (0.0, 0.0, 0.0, 5.0, 12.5, 30.0 mm)." in md
    )
    # a product without the record (older files, unit fixtures) renders without the line
    assert "Observed rain of the previous" not in forecast.render_markdown(
        forecast.build_product("2026-09-04", states, det, ens, recent, params)
    )


def test_product_prints_the_cushion_scenario_beside_the_frl_bound():
    states, det, ens, params = _inputs(storage_frac=0.99, qpf_mm=80.0)
    prod = forecast.build_product("2026-09-04", states, det, ens, {}, params)
    e = prod["dams"]["Pong"]
    c = e["cushion"]
    assert c["capacity_bcm"] == pytest.approx(C.cushion_capacity_bcm("Pong"))
    assert c["top_level_ft"] == pytest.approx(1400.0)
    # the FRL bound spills at every horizon; the cushion absorbs the first days
    frl = e["ensemble"]
    for H in frl:
        assert c["ensemble"][H]["p_exhaustion"] <= frl[H]["p_exhaustion"]
        assert c["ensemble"][H]["peak_release_q50_cusecs"] <= frl[H]["peak_release_q50_cusecs"]
    assert c["ensemble"]["1"]["p_exhaustion"] == 0.0
    assert "deterministic" in c and all("hei" in v for v in c["deterministic"].values())
    md = forecast.render_markdown(prod)
    assert "flood cushion" in md and "1400" in md
    # the routed arrivals stay the FRL bound
    assert prod["reaches"] and "cushion" not in str(prod["reaches"])


def test_no_cushion_block_for_a_dam_without_a_published_top():
    states, det, ens, params = _inputs()
    st = dict(states["Pong"])
    st["storage_bcm"] = C.BHAKRA.live_capacity_bcm.value * 0.99
    states2 = {"Bhakra": st}
    det2 = det.assign(catchment="Bhakra")
    ens2 = ens.assign(catchment="Bhakra")
    prod = forecast.build_product("2026-09-04", states2, det2, ens2, {}, {"Bhakra": params["Pong"]})
    assert "cushion" not in prod["dams"]["Bhakra"]
    assert "no published storage figure above" in forecast.render_markdown(prod)


def test_product_carries_the_flood_scale_probability_and_loads_its_parameter(tmp_path):
    states, det, ens, params = _inputs(storage_frac=0.9, qpf_mm=40.0)
    prod = forecast.build_product(
        "2026-09-04", states, det, ens, {}, params, flood_scale_log_sd=0.25
    )
    e = prod["dams"]["Pong"]
    for H, s in e["ensemble"].items():
        # a symmetric spread in log volume can move the probability either way; what it
        # must do is exist, stay a probability, and carry its own peak quantiles
        assert 0.0 <= s["p_exhaustion_flood_scale"] <= 1.0
        assert s["peak_release_q90_flood_scale_cusecs"] >= s["peak_release_q50_flood_scale_cusecs"]
        assert s["flood_scale_log_sd"] == 0.25
    assert "p_exhaustion_flood_scale" in e["cushion"]["ensemble"]["5"]
    assert prod["flood_scale_log_sd"] == 0.25
    md = forecast.render_markdown(prod)
    assert "flood-scale volume error" in md
    # without the parameter the column reads n/a and the key is absent
    prod0 = forecast.build_product("2026-09-04", states, det, ens, {}, params)
    assert "p_exhaustion_flood_scale" not in prod0["dams"]["Pong"]["ensemble"]["5"]
    # the loader: the committed file, or None when there is none or no spread
    f = tmp_path / "fse.json"
    assert forecast.load_flood_scale_error(f) is None
    f.write_text(json.dumps({"log_sd": 0.13, "n_periods": 6}), encoding="utf-8")
    assert forecast.load_flood_scale_error(f) == pytest.approx(0.13)
    f.write_text(json.dumps({"log_sd": None, "n_periods": 2}), encoding="utf-8")
    assert forecast.load_flood_scale_error(f) is None


def _bhakra_rating():
    from punjabflood import reservoirs

    frl = C.BHAKRA.frl_m.value
    levels = np.linspace(frl - 40.0, frl, 200)
    cap = C.BHAKRA.live_capacity_bcm.value
    return reservoirs.Rating.fit("Bhakra", levels, cap - (frl - levels) * 0.1)


def test_product_prints_the_rule_curve_scenario_for_bhakra_only_with_a_rating():
    states, det, ens, params = _inputs(qpf_mm=5.0)
    cap = C.BHAKRA.live_capacity_bcm.value
    st = dict(states["Pong"])
    st["storage_bcm"] = cap * 0.96  # above the schedule for 10 August (1,670 ft), below FRL
    states2 = {"Bhakra": st}
    det2 = det.assign(catchment="Bhakra")
    ens2 = ens.assign(catchment="Bhakra")
    ratings = {"Bhakra": _bhakra_rating()}
    prod = forecast.build_product(
        "2026-08-10", states2, det2, ens2, {}, {"Bhakra": params["Pong"]}, ratings=ratings
    )
    e = prod["dams"]["Bhakra"]
    r = e["rule_curve"]
    assert "2019" in r["vintage"] and len(r["points"]) == 3
    assert r["level_ft_by_day"][0] == 1670.0 and len(r["level_ft_by_day"]) == len(
        r["capacity_bcm_by_day"]
    )
    assert r["headroom_day1_bcm"] < 0  # the reservoir is above its schedule
    # the schedule bound fires on day one where the FRL bound does not
    assert r["ensemble"]["1"]["p_exhaustion"] == 1.0
    assert e["ensemble"]["1"]["p_exhaustion"] == 0.0
    assert all("hei" in v for v in r["deterministic"].values())
    md = forecast.render_markdown(prod)
    assert "Against the filling schedule" in md and "1,670 ft tomorrow" in md
    # without a rating, or for a dam without a schedule, no block and no line
    prod2 = forecast.build_product(
        "2026-08-10", states2, det2, ens2, {}, {"Bhakra": params["Pong"]}
    )
    assert "rule_curve" not in prod2["dams"]["Bhakra"]
    prod3 = forecast.build_product("2026-08-10", states, det, ens, {}, params, ratings=ratings)
    assert "rule_curve" not in prod3["dams"]["Pong"]
    assert "filling schedule" not in forecast.render_markdown(prod3)


def test_product_carries_the_weather_watch_and_prints_it():
    states, det, ens, params = _inputs()
    wd = pd.DataFrame(
        {
            "target_date": pd.date_range("2026-09-05", periods=6),
            "precipitation_mm": 80.0,
            "snowfall_cm": 0.0,
            "t2m_max_c": 20.0,
            "t2m_mean_c": 15.0,
            "model": "ecmwf_aifs025_single",
            "catchment": "Pong",
        }
    )
    prod = forecast.build_product(
        "2026-09-04",
        states,
        det,
        ens,
        {"Pong": [1.0, 2.0, 3.0]},
        params,
        ghaggar_climatology={
            "Pong": np.arange(0, 400, 1.0),
            "Ghaggar Khanauri": np.arange(0, 200, 1.0),
        },
        recent_sources={"Pong": ["imd_rt", "imd_rt", "best_match"]},
        weather_daily=wd,
    )
    w = prod["weather"]
    assert set(w) == {"Pong", "Ghaggar Khanauri"}
    assert w["Pong"]["level"] == "alert"  # 80 mm a day: every member has a heavy day
    assert w["Pong"]["observed"]["sources"] == ["imd_rt", "imd_rt", "best_match"]
    assert w["Pong"]["forecast"]["three_day_percentile"]["gfs_seamless"] == 60.0
    assert w["Pong"]["temperature"]["snow_share_3day"] == 0.0
    assert w["Ghaggar Khanauri"]["forecast"]["three_day_percentile"]["best_match"] == 45.0
    md = forecast.render_markdown(prod)
    assert "## Weather watch" in md and "| Pong | alert |" in md
    json.dumps(prod, default=str)


def _melt_params():
    return inflow.InflowParams(
        "Pong",
        12560.0,
        c=0.6,
        w=(0.5, 0.3, 0.2, 0.0),
        rho=0.9,
        intercept_bcm_per_day=0.0,
        rmse_bcm=0.03,
        resid_acf1=0.3,
        c_melt=0.5,
        w_melt=(0.4, 0.3, 0.2, 0.1),
    )


def test_melt_from_series_picks_the_recent_and_horizon_days_and_converts_to_bcm():
    days = pd.date_range("2026-09-01", periods=8)  # to 09-08: the horizon's last day missing
    melt = pd.DataFrame(
        {"melt_mm": np.arange(1.0, 9.0), "pack_mm": 100.0, "source": ["archive"] * 5 + ["m"] * 3},
        index=days,
    )
    r = forecast.melt_from_series(melt, "2026-09-04", recent_days=3, horizon=5, area_km2=1000.0)
    assert r["recent_dates"] == ["2026-09-01", "2026-09-02", "2026-09-03"]
    assert r["forecast_dates"] == [f"2026-09-0{d}" for d in range(5, 10)]
    assert r["melt_mm_recent"] == [1.0, 2.0, 3.0]
    assert r["melt_mm_forecast"] == [5.0, 6.0, 7.0, 8.0, 0.0]
    # mm over km2 to BCM: 1 mm over 1000 km2 is 0.001 BCM
    assert abs(r["melt_bcm_recent"][0] - 0.001) < 1e-12
    assert r["missing_days"] == 1
    assert r["pack_mm_issue"] == 100.0
    assert r["source_recent"] == ["archive"] * 3
    assert r["source_forecast"] == ["archive", "m", "m", "m", None]


def test_build_product_applies_the_melt_inputs_where_the_parameters_carry_the_term():
    states, det, ens, _ = _inputs()
    p = {"Pong": _melt_params()}
    m = {
        "Pong": {
            "recent_dates": [],
            "melt_bcm_recent": [0.02] * 6,
            "melt_bcm_forecast": [0.02] * 5,
            "melt_mm_recent": [1.6] * 6,
            "melt_mm_forecast": [1.6] * 5,
            "forecast_dates": [],
            "missing_days": 0,
            "archive_last_day": "2026-09-02",
            "model": "m",
            "pack_mm_issue": 50.0,
        }
    }
    recent = {"Pong": [0.0] * 6}
    without = forecast.build_product("2026-09-04", states, det, ens, recent, p)
    with_melt = forecast.build_product("2026-09-04", states, det, ens, recent, p, melt=m)
    e0, e1 = without["dams"]["Pong"], with_melt["dams"]["Pong"]
    # the recent melt explains part of the observed inflow, so the base is lower
    assert e1["base_inflow_cusecs"] < e0["base_inflow_cusecs"]
    assert e1["snowmelt"]["applied"] is True and e1["snowmelt"]["melt_bcm_forecast"] == [0.02] * 5
    assert e0["snowmelt"]["applied"] is False and "contributes nothing" in e0["snowmelt"]["note"]
    d0 = e0["deterministic"]["gfs_seamless"]["inflow_bcm_by_day"]
    d1 = e1["deterministic"]["gfs_seamless"]["inflow_bcm_by_day"]
    assert d0 != d1
    md = forecast.render_markdown(with_melt)
    assert "Snowmelt (degree-day pack" in md and "pack 50 mm" in md
    assert "contributes nothing" in forecast.render_markdown(without)


def test_build_product_ignores_melt_inputs_without_the_term():
    states, det, ens, params = _inputs()
    m = {"Pong": {"melt_bcm_recent": [0.02] * 6, "melt_bcm_forecast": [0.02] * 5}}
    a = forecast.build_product("2026-09-04", states, det, ens, {"Pong": [0.0] * 6}, params)
    b = forecast.build_product("2026-09-04", states, det, ens, {"Pong": [0.0] * 6}, params, melt=m)
    assert "snowmelt" not in b["dams"]["Pong"]
    assert a["dams"]["Pong"]["base_inflow_cusecs"] == b["dams"]["Pong"]["base_inflow_cusecs"]
    assert (
        a["dams"]["Pong"]["deterministic"]["gfs_seamless"]["inflow_bcm_by_day"]
        == b["dams"]["Pong"]["deterministic"]["gfs_seamless"]["inflow_bcm_by_day"]
    )


class _MeltClient:
    """Archive spans from the cache-like fake (nulls after ``archive_have``), the model's
    past and forecast days; the tail span raises when ``tail_fails``."""

    def __init__(self, archive_have="2026-09-01", tail_fails=False):
        self.archive_have = pd.Timestamp(archive_have)
        self.tail_fails = tail_fails
        self.calls = []

    def archive_daily(self, lat, lon, start, end, daily=()):
        self.calls.append(("archive", start, end))
        if self.tail_fails and pd.Timestamp(start) > pd.Timestamp("2026-08-31"):
            from punjabflood.openmeteo import QuotaExhausted

            raise QuotaExhausted("Daily API request limit exceeded")
        days = pd.date_range(start, end)
        t = [(-5.0 if d.month < 9 else 5.0) if d <= self.archive_have else None for d in days]
        s = [7.0 if d.month == 1 else 0.0 for d in days]
        return {
            "daily": {
                "time": [d.date().isoformat() for d in days],
                "snowfall_sum": s,
                "temperature_2m_mean": t,
            }
        }

    def forecast_daily_weather(self, lat, lon, model, days, issue_date=None, daily=(), past_days=0):
        self.calls.append(("weather", model, days, past_days))
        start = pd.Timestamp(issue_date) - pd.Timedelta(days=past_days)
        t = pd.date_range(start, periods=past_days + days)
        return {
            "daily": {
                "time": [d.date().isoformat() for d in t],
                "precipitation_sum": [0.0] * len(t),
                "snowfall_sum": [0.0] * len(t),
                "temperature_2m_max": [8.0] * len(t),
                "temperature_2m_mean": [5.0] * len(t),
            }
        }


def _one_point_catchment(monkeypatch):
    from punjabflood import snow

    monkeypatch.setattr(snow, "points_with_weights", lambda cat, col: [("p1", 31.0, 77.0, 1.0)])
    monkeypatch.setattr(
        forecast.rain, "points_with_weights", lambda cat, col: [("p1", 31.0, 77.0, 1.0)]
    )
    monkeypatch.setattr(
        snow, "MELT_SPANS", [("2026-01-01", "2026-01-31"), ("2026-02-01", "2026-08-31")]
    )

    class Cat:
        name = "Pong"
        area_km2 = 1000.0

    return {"Pong": Cat()}


def test_melt_inputs_runs_the_bucket_across_the_archive_and_the_model(monkeypatch):
    cats = _one_point_catchment(monkeypatch)
    client = _MeltClient(archive_have="2026-09-01")
    out = forecast.melt_inputs(
        client, cats, {"Pong": _melt_params()}, "2026-09-05", recent_days=3, horizon=2
    )
    r = out["Pong"]
    # the tail span was asked for to two days before issue; the archive held it to 09-01
    assert ("archive", "2026-09-01", "2026-09-03") in client.calls
    assert r["archive_last_day"] == "2026-09-01" and r["model"] == "ecmwf_aifs025_single"
    assert r["recent_dates"] == ["2026-09-02", "2026-09-03", "2026-09-04"]
    assert r["source_recent"] == ["ecmwf_aifs025_single"] * 3
    assert r["source_forecast"] == ["ecmwf_aifs025_single"] * 2
    assert r["missing_days"] == 0 and r["n_points"] == 1
    # January's snow (31 days of 7 cm, 10 mm of water each) sits in the pack through August
    # and melts 20 mm a day from September; the model's days carry that on
    assert r["melt_mm_recent"] == [20.0, 20.0, 20.0] and r["melt_mm_forecast"] == [20.0, 20.0]
    assert abs(r["melt_bcm_recent"][0] - 0.02) < 1e-12
    assert "note" not in r


def test_melt_inputs_falls_back_to_the_fixed_spans_when_the_tail_cannot_be_pulled(monkeypatch):
    cats = _one_point_catchment(monkeypatch)
    client = _MeltClient(archive_have="2026-08-31", tail_fails=True)
    out = forecast.melt_inputs(
        client, cats, {"Pong": _melt_params()}, "2026-09-05", recent_days=3, horizon=2
    )
    r = out["Pong"]
    assert r["archive_last_day"] == "2026-08-31" and "archive tail not pulled" in r["note"]
    assert r["melt_mm_recent"] == [20.0, 20.0, 20.0]


def test_melt_inputs_skips_parameters_without_the_term(monkeypatch):
    cats = _one_point_catchment(monkeypatch)
    _, _, _, params = _inputs()
    assert forecast.melt_inputs(_MeltClient(), cats, params, "2026-09-05") == {}
