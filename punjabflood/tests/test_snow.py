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


class _Recorder:
    """A stand-in client that records the archive spans asked for."""

    def __init__(self):
        self.spans = []

    def archive_daily(self, lat, lon, start, end, daily=()):
        self.spans.append((start, end))
        days = pd.date_range(start, end)
        return {
            "daily": {
                "time": [d.strftime("%Y-%m-%d") for d in days],
                "snowfall_sum": [0.0] * len(days),
                "temperature_2m_mean": [1.0] * len(days),
            }
        }


class _OnePoint:
    name = "X"


def test_point_series_uses_the_given_chunks(monkeypatch):
    chunks = [("2014-01-01", "2014-12-31"), ("2015-01-01", "2015-01-31")]
    monkeypatch.setattr(snow, "points_with_weights", lambda cat, col: [("p1", 31.0, 77.0, 2.0)])
    client = _Recorder()
    frames, weights = snow.point_series(
        client, _OnePoint(), "2014-01-01", "2015-01-31", chunks=chunks
    )
    assert client.spans == chunks
    assert len(frames["p1"]) == 365 + 31
    assert frames["p1"].index.is_monotonic_increasing
    assert weights["p1"] == 2.0


def test_live_spans_adds_a_tail_only_after_the_last_fixed_span():
    spans = [("2014-01-01", "2014-12-31"), ("2015-01-01", "2015-06-30")]
    assert snow.live_spans("2015-06-30", spans) == spans
    assert snow.live_spans("2015-03-01", spans) == spans
    assert snow.live_spans("2015-07-04", spans) == spans + [("2015-07-01", "2015-07-04")]


def _frame(days, snow_cm, t):
    return pd.DataFrame({"snowfall_cm": snow_cm, "t2m_mean_c": t}, index=days)


def test_last_complete_day_is_the_last_day_every_point_has_a_temperature():
    days = pd.date_range("2026-09-10", periods=4)
    a = _frame(days, [0.0] * 4, [1.0, 1.0, 1.0, np.nan])
    b = _frame(days, [0.0] * 4, [1.0, 1.0, np.nan, np.nan])
    assert snow.last_complete_day({"a": a, "b": b}) == pd.Timestamp("2026-09-11")
    assert snow.last_complete_day({"a": _frame(days, [0.0] * 4, [np.nan] * 4)}) is None


def test_extend_points_joins_the_model_after_the_archive_and_the_pack_carries_across():
    arch_days = pd.date_range("2026-09-10", periods=3)
    # 7 cm of snow (10 mm of water) falls at -5 C on the first day and stays; the archive's
    # last day has no temperature yet
    archive = {"p": _frame(arch_days, [7.0, 0.0, 0.0], [-5.0, -5.0, np.nan])}
    model_days = pd.date_range("2026-09-08", periods=7)  # past days overlap the archive
    model = {"p": _frame(model_days, [0.0] * 7, [-5.0, -5.0, -5.0, -5.0, 5.0, 5.0, 5.0])}
    joined, end = snow.extend_points(archive, model, "m")
    assert end == pd.Timestamp("2026-09-11")
    f = joined["p"]
    assert f.index[0] == arch_days[0] and f.index[-1] == model_days[-1]
    assert f["source"].tolist() == ["archive", "archive", "m", "m", "m"]
    assert f.index.is_monotonic_increasing and f.index.is_unique
    out = snow.catchment_melt_from_points(joined, pd.Series({"p": 1.0}))
    # the pack built in the archive melts on the model's first warm day (capacity 20 mm)
    assert out["pack_mm"].tolist()[:2] == [10.0, 10.0]
    assert out.loc[pd.Timestamp("2026-09-12"), "melt_mm"] == 10.0
    assert out.loc[pd.Timestamp("2026-09-12"), "pack_mm"] == 0.0


def test_extend_points_keeps_the_archive_alone_for_a_point_the_model_lacks():
    days = pd.date_range("2026-09-10", periods=2)
    joined, end = snow.extend_points({"p": _frame(days, [0.0, 0.0], [1.0, 1.0])}, {}, "m")
    assert end == days[-1] and joined["p"]["source"].tolist() == ["archive", "archive"]
