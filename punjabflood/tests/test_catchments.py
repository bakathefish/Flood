from __future__ import annotations

from pathlib import Path

import pytest
from shapely.geometry import Point, box

from punjabflood import catchments
from punjabflood import constants as C

SHP = Path(__file__).resolve().parents[1] / "data/raw/hydrobasins/hybas_as_lev08_v1c.shp"


def test_upstream_set_follows_next_down_links():
    recs = {
        1: {"NEXT_DOWN": 3},
        2: {"NEXT_DOWN": 3},
        3: {"NEXT_DOWN": 4},
        4: {"NEXT_DOWN": 0},
        5: {"NEXT_DOWN": 4},
        6: {"NEXT_DOWN": 7},  # unrelated branch
        7: {"NEXT_DOWN": 0},
    }
    assert catchments.upstream_set(3, recs) == {1, 2, 3}
    assert catchments.upstream_set(4, recs) == {1, 2, 3, 4, 5}
    assert catchments.upstream_set(7, recs) == {6, 7}


def test_grid_weights_sum_to_polygon_area_and_points_sit_on_the_era5_grid():
    poly = box(76.07, 31.02, 76.61, 31.48)
    pts = catchments.sample_grid(poly, step_deg=0.25)
    assert abs(pts["weight_km2"].sum() - catchments.geodesic_area_km2(poly)) < 0.5
    assert ((pts["lat"] * 4).round() == pts["lat"] * 4).all()
    assert ((pts["lon"] * 4).round() == pts["lon"] * 4).all()
    # an interior cell carries the full 0.25-degree cell area (about 640 km2 at 31 N)
    full = pts[(pts.lat == 31.25) & (pts.lon == 76.25)]["weight_km2"].iloc[0]
    assert 600 < full < 700


def test_geodesic_area_of_one_degree_cell_near_the_equator():
    area = catchments.geodesic_area_km2(box(0, 0, 1, 1))
    assert 12300 < area < 12400  # 111.3 km x 110.6 km


@pytest.mark.skipif(not SHP.exists(), reason="HydroBASINS archive not downloaded")
def test_real_catchments_match_published_areas_and_contain_the_dams():
    cats = catchments.build_all(SHP.with_suffix(""))
    tol = {"Bhakra": 0.10, "Pong": 0.10, "Ranjit Sagar": 0.15}
    for dam in C.DAMS.values():
        c = cats[dam.name]
        assert c.polygon.contains(Point(dam.lon, dam.lat)), dam.name
        if dam.catchment_km2_published is not None:
            pub = dam.catchment_km2_published.value
            assert abs(c.area_km2 - pub) / pub < tol[dam.name], (dam.name, c.area_km2, pub)
        assert abs(c.points["weight_km2"].sum() - c.area_km2) / c.area_km2 < 0.01
    assert cats["Ghaggar Khanauri"].area_km2 > cats["Ghaggar Bhankarpur"].area_km2
    assert cats["Ghaggar Bhankarpur"].upstream_ids <= cats["Ghaggar Khanauri"].upstream_ids


def test_geojson_round_trip(tmp_path):
    poly = box(76.0, 31.0, 76.5, 31.5)
    c = catchments.Catchment(
        name="Toy",
        outlet=1,
        polygon=poly,
        area_km2=catchments.geodesic_area_km2(poly),
        upstream_ids=frozenset({1}),
        points=catchments.sample_grid(poly),
    )
    catchments.save_geojson({"Toy": c}, tmp_path)
    back = catchments.load_geojson(tmp_path)["Toy"]
    assert back.outlet == 1
    assert abs(back.area_km2 - c.area_km2) < 0.1
    assert len(back.points) == len(c.points)
    assert back.polygon.equals_exact(poly, 1e-9)
