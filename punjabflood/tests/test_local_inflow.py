"""The local inflow term between the dams and the control points (roadmap, done in the first
round): constants, catchment sets, the transferred runoff response, routing, verification and the
daily product. Kept in one module because the term crosses six package modules."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from shapely.geometry import Point, box

from punjabflood import catchments, forecast, inflow, routing, verify
from punjabflood import constants as C
from tests.test_forecast import _inputs
from tests.test_routing import _impulse

SHP = Path(__file__).resolve().parents[1] / "data/raw/hydrobasins/hybas_as_lev08_v1c.shp"


# -- constants ---------------------------------------------------------------------------
def test_local_catchments_are_sourced_and_feed_known_stations():
    assert list(C.LOCAL_CATCHMENTS) == ["Sutlej local", "Beas local", "Harike local"]
    seen: set[str] = set()
    for name, lc in C.LOCAL_CATCHMENTS.items():
        assert lc.name == name and lc.source and lc.coord_source
        assert lc.outlet_station in C.CONTROL_POINTS
        assert lc.transfer_dam in C.DAMS
        for st in lc.stations:
            assert st in C.CONTROL_POINTS, (name, st)
        for ex in lc.exclude:
            assert ex in C.DAMS or ex in seen, (name, ex)
        assert lc.outlet_station in lc.stations
        seen.add(name)
    # Harike receives all three; Ferozepur inherits Harike's sum and is not listed
    feeders = [n for n, lc in C.LOCAL_CATCHMENTS.items() if "Harike Head Works" in lc.stations]
    assert feeders == ["Sutlej local", "Beas local", "Harike local"]
    assert C.LOCAL_CATCHMENTS["Beas local"].stations == ("Dhilwan", "Harike Head Works")


# -- catchments --------------------------------------------------------------------------
def test_build_local_removes_the_excluded_upstream_sets():
    recs = {
        1: {"NEXT_DOWN": 3},
        2: {"NEXT_DOWN": 3},
        3: {"NEXT_DOWN": 4},
        4: {"NEXT_DOWN": 0},
        5: {"NEXT_DOWN": 4},
    }
    geoms = {h: box(76.0 + 0.5 * h, 31.0, 76.5 + 0.5 * h, 31.5) for h in recs}
    lc = C.LocalCatchment(
        name="Toy local",
        river="Sutlej",
        outlet=4,
        outlet_station="Ropar Head Works",
        outlet_lat=31.25,
        outlet_lon=78.25,
        coord_source="test",
        exclude=("A",),
        stations=("Ropar Head Works",),
    )
    c = catchments.build_local(lc, recs, geoms, {"A": {1, 2, 3}})
    assert c.upstream_ids == frozenset({4, 5}) and c.role == "local"
    assert abs(c.area_km2 - catchments.geodesic_area_km2(geoms[4].union(geoms[5]))) < 0.1
    assert c.polygon.contains(Point(78.25, 31.25))
    with pytest.raises(KeyError):
        catchments.build_local(lc, recs, geoms, {})


def test_geojson_round_trip_keeps_the_role(tmp_path):
    poly = box(76.0, 31.0, 76.5, 31.5)
    c = catchments.Catchment(
        name="Toy local",
        outlet=1,
        polygon=poly,
        area_km2=catchments.geodesic_area_km2(poly),
        upstream_ids=frozenset({1}),
        points=catchments.sample_grid(poly),
        role="local",
    )
    catchments.save_geojson({"Toy local": c}, tmp_path)
    assert catchments.load_geojson(tmp_path)["Toy local"].role == "local"
    # files written before the role existed read back as upstream catchments
    path = tmp_path / "toy_local.geojson"
    fc = json.loads(path.read_text(encoding="utf-8"))
    del fc["features"][0]["properties"]["role"]
    path.write_text(json.dumps(fc), encoding="utf-8")
    assert catchments.load_geojson(tmp_path)["Toy local"].role == "upstream"


@pytest.mark.skipif(not SHP.exists(), reason="HydroBASINS archive not downloaded")
def test_real_local_catchments_between_the_dams_and_harike():
    cats = catchments.build_all(SHP.with_suffix(""))
    expect = {"Sutlej local": (2, 3968), "Beas local": (2, 3506), "Harike local": (15, 9895)}
    dam_ids = set().union(*(cats[d].upstream_ids for d in C.DAMS))
    seen: list[str] = []
    for name, (n, km2) in expect.items():
        c = cats[name]
        assert c.role == "local"
        assert len(c.upstream_ids) == n, (name, len(c.upstream_ids))
        assert abs(c.area_km2 - km2) < 5, (name, c.area_km2)
        assert not (c.upstream_ids & dam_ids)
        for other in seen:
            assert not (c.upstream_ids & cats[other].upstream_ids)
        lc = C.LOCAL_CATCHMENTS[name]
        assert c.polygon.contains(Point(lc.outlet_lon, lc.outlet_lat)), name
        assert lc.outlet in c.upstream_ids
        assert abs(c.points["weight_km2"].sum() - c.area_km2) / c.area_km2 < 0.01
        seen.append(name)
    assert sum(len(cats[n].upstream_ids) for n in expect) == 19
    for d in C.DAMS:
        assert cats[d].role == "upstream"


# -- inflow ------------------------------------------------------------------------------
def test_local_inflow_is_the_quick_response_over_the_local_area():
    p = inflow.InflowParams(
        "Pong", 12560.0, c=0.4, w=(1.0, 0.0, 0.0, 0.0), rho=0.9, intercept_bcm_per_day=0.0
    )
    days = pd.date_range("2025-08-01", periods=6, freq="D")
    rain = pd.Series([0.0, 0.0, 10.0, 0.0, 0.0, 0.0], index=days)
    q = inflow.local_inflow_cusecs(p, 1000.0, rain)
    assert list(q.index) == list(days)
    # 10 mm over 1,000 km2 is 0.01 BCM; 40 percent of it, on the day, as cusec-days
    assert q.loc["2025-08-03"] == pytest.approx(C.bcm_to_cusec_days(0.4 * 0.01))
    assert q.drop(pd.Timestamp("2025-08-03")).abs().max() == 0.0
    # the transferred parameters carry the local name and area, nothing else changes
    t = inflow.transferred_params(p, "Beas local", 1000.0)
    assert t.dam == "Beas local" and t.area_km2 == 1000.0 and t.c == p.c and t.w == p.w


def test_local_inflow_lags_and_wetness_follow_the_calibrated_response():
    p = inflow.InflowParams(
        "Pong",
        12560.0,
        c=0.2,
        w=(0.5, 0.5, 0.0, 0.0),
        rho=0.9,
        intercept_bcm_per_day=0.0,
        c_wet=0.3,
    )
    days = pd.date_range("2025-08-01", periods=8, freq="D")
    rain = pd.Series([0.0, 50.0, 0.0, 0.0, 0.0, 0.0, 0.0, 20.0], index=days)
    q = inflow.local_inflow_cusecs(p, 2000.0, rain)
    rv = inflow.rain_volume_bcm(rain.to_numpy(), 2000.0)
    # day 2: no antecedent rain, coefficient c, half the volume today
    assert q.iloc[1] == pytest.approx(C.bcm_to_cusec_days(0.2 * 0.5 * rv[1]))
    # day 3: the other half, with the coefficient raised by yesterday's 50 mm
    assert q.iloc[2] == pytest.approx(
        C.bcm_to_cusec_days(inflow.coefficient(p, 50.0) * 0.5 * rv[1])
    )
    # day 8: the 50 mm is outside the five-day antecedent window, coefficient back to c
    assert q.iloc[7] == pytest.approx(C.bcm_to_cusec_days(0.2 * 0.5 * rv[7]))
    # the day-by-day series agrees with the single-day response the product uses
    t = inflow.transferred_params(p, "x", 2000.0)
    for i in range(len(days)):
        hist = rain.to_numpy()[: i + 1]
        assert q.iloc[i] == pytest.approx(C.bcm_to_cusec_days(inflow.quick_response_bcm(t, hist)))
    # forecast form: recent observed days feed the lags and the wetness of the forecast days
    fc = inflow.local_inflow_forecast_cusecs(p, 2000.0, rain.to_numpy()[:5], rain.to_numpy()[5:])
    assert fc == pytest.approx(q.to_numpy()[5:])
    assert inflow.local_inflow_forecast_cusecs(p, 2000.0, [], []).shape == (0,)


# -- routing -----------------------------------------------------------------------------
def test_local_inflow_is_added_at_its_stations_on_the_day():
    pg = _impulse(value=200_000.0)
    idx = pg.index
    local = {
        "Beas local": pd.Series([0, 0, 0, 30_000.0, 0, 0], index=idx),
        "Sutlej local": pd.Series([0, 0, 0, 5_000.0, 0, 0], index=idx),
        "Harike local": pd.Series([0, 0, 0, 7_000.0, 0, 0], index=idx),
    }
    plain = routing.arrivals({"Pong": pg})
    arr = routing.arrivals({"Pong": pg}, local=local)
    dh = arr[arr.station == "Dhilwan"].set_index("date")["cusecs"]
    dh0 = plain[plain.station == "Dhilwan"].set_index("date")["cusecs"]
    # the local term lands on its own day (Aug 30, when the routed peak is also there)
    assert dh.loc["2025-08-30"] == dh0.loc["2025-08-30"] + 30_000
    assert dh.loc["2025-08-31"] == dh0.loc["2025-08-31"]
    # Naushera Mirthal, just below Pong, receives no local term
    nm = arr[arr.station == "Naushera Mirthal"].set_index("date")["cusecs"]
    nm0 = plain[plain.station == "Naushera Mirthal"].set_index("date")["cusecs"]
    assert nm.reindex(nm0.index).equals(nm0)
    # Harike sums the three locals; Ferozepur inherits twelve hours later
    hk = arr[arr.station == "Harike Head Works"].set_index("date")["cusecs"]
    hk0 = plain[plain.station == "Harike Head Works"].set_index("date")["cusecs"]
    assert hk.loc["2025-08-30"] == hk0.loc["2025-08-30"] + 42_000
    fz = arr[arr.station == "Ferozepur Head Works"].set_index("date")["cusecs"]
    assert fz.loc["2025-08-30"] == 42_000  # from 12:00 on Aug 30; nothing else that day
    # the Sutlej stations receive the Sutlej local term even with no Bhakra release given
    rp = arr[arr.station == "Ropar Head Works"].set_index("date")["cusecs"]
    assert rp.loc["2025-08-30"] == 5_000
    assert rp.drop(pd.Timestamp("2025-08-30")).abs().sum() == 0
    assert "Ropar Head Works" not in set(plain.station)
    assert "Railway Bridge Phillaur" in set(arr.station)
    # the class is recomputed on the sum
    row = arr[(arr.station == "Dhilwan") & (arr.date == "2025-08-30")].iloc[0]
    assert row["class"] == C.CONTROL_POINTS["Dhilwan"].classify(row["cusecs"])
    assert set(arr.columns) == set(plain.columns)


def test_arrivals_without_a_local_term_are_unchanged():
    pg = _impulse(value=200_000.0)
    assert routing.arrivals({"Pong": pg}).equals(routing.arrivals({"Pong": pg}, local=None))
    assert routing.arrivals({"Pong": pg}).equals(routing.arrivals({"Pong": pg}, local={}))


# -- verification ------------------------------------------------------------------------
def test_routed_next_day_release_passes_the_local_term_through():
    days = pd.date_range("2025-08-27", periods=6, freq="D")
    pp = pd.DataFrame(
        {"date": days, "dam": "Pong", "release_day1_cusecs": [0, 0, 100_000.0, 0, 0, 0]}
    )
    local = {"Beas local": pd.Series([0, 0, 0, 0, 25_000.0, 0], index=days)}
    plain = verify.routed_next_day_release(pp, "Pong", passage=False)
    arr = verify.routed_next_day_release(pp, "Pong", passage=False, local=local)
    dh0 = plain[plain.station == "Dhilwan"].set_index("date")["cusecs"]
    dh = arr[arr.station == "Dhilwan"].set_index("date")["cusecs"]
    both = dh0.index.union(dh.index)
    diff = dh.reindex(both).fillna(0.0) - dh0.reindex(both).fillna(0.0)
    assert diff.loc["2025-08-31"] == 25_000
    assert diff.drop(pd.Timestamp("2025-08-31")).abs().sum() == 0


def test_local_inflow_summary_reads_the_observed_peak_day():
    days = pd.date_range("2025-08-25", "2025-09-05", freq="D")
    beas = np.full(len(days), 1_000.0)
    beas[days == "2025-08-31"] = 40_000.0
    beas[days == "2025-09-02"] = 55_000.0
    local = {
        "Beas local": pd.Series(beas, index=days),
        "Harike local": pd.Series(9_000.0, index=days),
    }
    arr = pd.DataFrame(
        {"station": "Dhilwan", "date": days, "cusecs": 150_000.0, "river": "Beas", "class": "low"}
    )
    peaks = pd.DataFrame(
        {
            "year": [2025, 2023],
            "date": ["2025-08-31", "2023-08-17"],
            "discharge_cusecs": [235_494.0, 237_500.0],
        }
    )
    s = verify.local_inflow_summary(local, arr, peaks, years=(2025, 2023)).set_index("year")
    r = s.loc[2025]
    assert r["observed_peak_date"] == "2025-08-31"
    # Beas local only: Harike local does not feed Dhilwan
    assert r["local_on_peak_day_cusecs"] == 40_000
    assert r["local_max_within_3_days_cusecs"] == 55_000 and r["local_max_date"] == "2025-09-02"
    assert r["routed_dam_on_peak_day_cusecs"] == 150_000
    assert r["local_share_of_observed_peak"] == pytest.approx(40_000 / 235_494)
    assert r["dam_plus_local_ratio"] == pytest.approx(190_000 / 235_494)
    # a year the series does not cover is reported, not dropped
    assert s.loc[2023, "note"] == "no local series for the event window"


# -- the daily product -------------------------------------------------------------------
def test_build_product_adds_local_inflow_to_the_reaches_it_feeds():
    states, det, ens, params = _inputs(storage_frac=0.5, qpf_mm=5.0)
    dates = pd.date_range("2026-09-05", periods=6)
    det = pd.concat(
        [
            det,
            pd.DataFrame(
                {
                    "target_date": dates,
                    "model": "ecmwf_ifs025",
                    "rain_mm": [40.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                    "catchment": "Beas local",
                }
            ),
        ],
        ignore_index=True,
    )
    prod = forecast.build_product(
        "2026-09-04",
        states,
        det,
        ens,
        {"Beas local": [0.0, 0.0, 0.0]},
        params,
        local_areas={"Beas local": 3506.0},
    )
    li = prod["local_inflow"]["Beas local"]
    assert li["model"] == "ecmwf_ifs025" and li["transfer_dam"] == "Pong"
    assert li["stations"] == ["Dhilwan", "Harike Head Works"]
    p = params["Pong"]
    rv = inflow.rain_volume_bcm(40.0, 3506.0)
    day1 = C.bcm_to_cusec_days(p.c * p.w[0] * rv)
    day2 = C.bcm_to_cusec_days(p.c * p.w[1] * rv)
    assert li["cusecs_by_day"][0] == pytest.approx(day1)
    assert li["cusecs_by_day"][1] == pytest.approx(day2)
    dh = [r for r in prod["reaches"] if r["station"] == "Dhilwan"][0]
    by_day = {d["date"]: d["cusecs"] for d in dh["by_day"]}
    # the local term lands on Sep 5 before any routed water; from Sep 6 the dam's 8,500
    # cusecs (outflow less the Mukerian diversion, 41 h downstream) is under it
    assert by_day["2026-09-05"] == pytest.approx(day1)
    assert by_day["2026-09-06"] == pytest.approx(20_000 - 11_500 + day2)
    hk = [r for r in prod["reaches"] if r["station"] == "Harike Head Works"][0]
    assert {d["date"]: d["cusecs"] for d in hk["by_day"]}["2026-09-05"] == pytest.approx(day1)
    md = forecast.render_markdown(prod)
    assert "Local inflow" in md and "Beas local" in md
    # without the areas the term is not computed and the product is as before
    plain = forecast.build_product("2026-09-04", states, det, ens, {}, params)
    assert plain["local_inflow"] == {}
    assert "Local inflow" not in forecast.render_markdown(plain)
