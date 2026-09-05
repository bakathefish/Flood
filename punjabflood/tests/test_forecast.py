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
