from __future__ import annotations

import numpy as np
import pandas as pd

from punjabflood import snow


def test_no_snow_gives_no_melt_and_no_pack():
    pack, melt = snow.degree_day_melt(np.zeros(5), np.full(5, 10.0))
    assert np.all(pack == 0) and np.all(melt == 0)


def test_a_fall_at_five_degrees_melts_fully_the_same_day():
    # 10 mm falls on day 0 at +5 C: capacity 4 * 5 = 20 mm, the whole 10 mm melts
    pack, melt = snow.degree_day_melt(np.array([10.0, 0.0]), np.array([5.0, 5.0]))
    assert melt.tolist() == [10.0, 0.0]
    assert pack.tolist() == [0.0, 0.0]


def test_a_fall_at_one_degree_melts_four_mm_a_day_and_the_pack_never_goes_negative():
    t = np.full(4, 1.0)
    pack, melt = snow.degree_day_melt(np.array([10.0, 0.0, 0.0, 0.0]), t)
    assert melt.tolist() == [4.0, 4.0, 2.0, 0.0]
    assert pack.tolist() == [6.0, 2.0, 0.0, 0.0]


def test_below_freezing_nothing_melts_and_the_pack_accumulates():
    pack, melt = snow.degree_day_melt(np.array([3.0, 4.0]), np.array([-2.0, -10.0]))
    assert melt.tolist() == [0.0, 0.0]
    assert pack.tolist() == [3.0, 7.0]


def test_missing_temperature_is_treated_as_no_melt():
    pack, melt = snow.degree_day_melt(np.array([5.0, 0.0]), np.array([np.nan, 5.0]))
    assert melt.tolist() == [0.0, 5.0]


def test_catchment_melt_weights_points_by_area():
    days = pd.date_range("2020-01-01", periods=3)
    per_point = {
        "a": pd.DataFrame(
            {"snowfall_cm": [7.0, 0.0, 0.0], "t2m_mean_c": [5.0, 5.0, 5.0]}, index=days
        ),
        "b": pd.DataFrame(
            {"snowfall_cm": [0.0, 0.0, 0.0], "t2m_mean_c": [5.0, 5.0, 5.0]}, index=days
        ),
    }
    weights = pd.Series({"a": 1.0, "b": 3.0})
    out = snow.catchment_melt_from_points(per_point, weights)
    # 7 cm of snow is 10 mm of water at point a; a carries a quarter of the area
    assert out.loc[days[0], "snowfall_mm"] == 10.0 * 0.25
    assert out.loc[days[0], "melt_mm"] == 10.0 * 0.25
    assert out.loc[days[1], "melt_mm"] == 0.0
    assert out.loc[days[0], "pack_mm"] == 0.0
    assert out.loc[days[0], "t2m_mean_c"] == 5.0
    assert list(out.columns) == ["snowfall_mm", "melt_mm", "pack_mm", "t2m_mean_c", "n_points"]
    assert out["n_points"].tolist() == [2, 2, 2]
