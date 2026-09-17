from __future__ import annotations

import pandas as pd

from punjabflood import cli


def _rows(source, days, value, cat="Pong"):
    return pd.DataFrame(
        {
            "date": pd.to_datetime(days),
            "catchment": cat,
            "rain_mm": value,
            "n_points": 3,
            "area_km2_covered": 100.0,
            "source": source,
        }
    )


def test_merge_recent_rain_keeps_the_best_source_per_day():
    d = pd.date_range("2026-09-01", periods=4)
    on_disk = pd.concat(
        [
            _rows("imd", d[:1], 1.0),  # a final day: never displaced
            _rows("era5", d[1:], 2.0),  # ERA5 for the rest
            _rows("imd_rt", d[2:3], 3.0),  # an older real-time day
        ]
    )
    on_disk["date"] = on_disk["date"].dt.strftime("%Y-%m-%d")
    fresh = [
        _rows("imd_rt", d[1:3], 4.0),  # real-time now has days 2 and 3 (day 3 refreshed)
        _rows("era5", d, 5.0),  # a fresh ERA5 pull of every day
    ]
    out = cli.merge_recent_rain(on_disk, fresh)
    assert out["date"].tolist() == [x.strftime("%Y-%m-%d") for x in d]
    assert out["source"].tolist() == ["imd", "imd_rt", "imd_rt", "era5"]
    # the final day keeps its value; real-time takes the fresh pull over the older file;
    # the last day has only ERA5 and takes the fresh one
    assert out["rain_mm"].tolist() == [1.0, 4.0, 4.0, 5.0]
    assert list(out.columns) == ["date", "catchment", "rain_mm", "n_points", "area_km2_covered", "source"]
    # nothing on disk: the fresh frames alone, one row per day
    alone = cli.merge_recent_rain(None, fresh)
    assert alone["source"].tolist() == ["era5", "imd_rt", "imd_rt", "era5"]


def test_merge_recent_rain_carries_the_soil_moisture_columns_across_sources():
    d = pd.date_range("2026-09-01", periods=3)
    on_disk = _rows("era5", d, 2.0)
    on_disk["sm_0_7"] = [0.31, 0.32, 0.33]
    on_disk["sm_7_28"] = [0.41, 0.42, 0.43]
    on_disk["date"] = on_disk["date"].dt.strftime("%Y-%m-%d")
    fresh = [_rows("imd_rt", d[:2], 4.0)]  # the real-time pull has no soil columns
    out = cli.merge_recent_rain(on_disk, fresh)
    assert out["source"].tolist() == ["imd_rt", "imd_rt", "era5"]
    assert out["sm_0_7"].tolist() == [0.31, 0.32, 0.33]
    assert out["sm_7_28"].tolist() == [0.41, 0.42, 0.43]

