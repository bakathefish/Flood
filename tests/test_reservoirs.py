# tests/test_reservoirs.py
import numpy as np
import pandas as pd

from sailaab.reservoirs import load_frames, normalize, window_features
from sailaab.windows import monsoon_windows


def _raw():
    """Synthetic raw frame mimicking the committed CSV schema, incl. a
    duplicate (dam, date) and a metre/feet unit mix and an 'NA' string."""
    return pd.DataFrame(
        {
            "date": [
                "2025-06-15",
                "2025-06-20",
                "2025-06-24",
                "2025-06-26",
                "2025-08-19",  # feet-reported flood row
                "2025-06-15",  # duplicate of first date, no storage
            ],
            "dam": ["Bhakra"] * 5 + ["Bhakra"],
            "level_value": [474.0, 475.0, "NA", 477.0, 1666.0, 999.0],
            "level_unit": ["m", "m", "m", "m", "ft", "m"],
            "storage_value": [1.0, 2.0, 3.0, 5.0, 4.983, "NA"],
            "storage_unit": ["BCM"] * 6,
            "pct_capacity": [20.0, 21.0, 22.0, 24.0, 80.0, ""],
            "source_url": ["http://x"] * 6,
        }
    )


def test_normalize_parses_dates_and_numbers():
    out = normalize(_raw())
    assert pd.api.types.is_datetime64_any_dtype(out["date"])
    assert pd.api.types.is_numeric_dtype(out["storage_value"])
    # the literal "NA" level became NaN
    row = out[(out["dam"] == "Bhakra") & (out["date"] == "2025-06-24")].iloc[0]
    assert np.isnan(row["level_value"])


def test_normalize_feet_to_metres_canonical_column():
    out = normalize(_raw())
    flood = out[out["date"] == "2025-08-19"].iloc[0]
    # 1666 ft -> 507.8 m
    assert abs(flood["level_m"] - 1666 * 0.3048) < 1e-6
    metric = out[(out["date"] == "2025-06-20")].iloc[0]
    assert abs(metric["level_m"] - 475.0) < 1e-9  # already metres, unchanged


def test_normalize_dedupes_preferring_storage_present():
    out = normalize(_raw())
    dup = out[(out["dam"] == "Bhakra") & (out["date"] == "2025-06-15")]
    assert len(dup) == 1
    # the surviving row is the one WITH a storage value (1.0), not the NA one
    assert dup.iloc[0]["storage_value"] == 1.0


def test_window_features_mean_and_delta():
    feats = window_features(normalize(_raw()), years=[2025])
    w0 = monsoon_windows(2025)[0]  # ("2025-06-15", "2025-06-25")
    row = feats[(feats["dam"] == "Bhakra") & (feats["window_start"] == w0[0])].iloc[0]
    # storage in [06-15, 06-25): 1.0 (15th), 2.0 (20th), 3.0 (24th)
    assert abs(row["mean_storage"] - 2.0) < 1e-9
    assert abs(row["delta_storage"] - (3.0 - 1.0)) < 1e-9  # last - first


def test_window_features_single_point_delta_zero():
    feats = window_features(normalize(_raw()), years=[2025])
    w1 = monsoon_windows(2025)[1]  # ("2025-06-25", "2025-07-05")
    row = feats[(feats["dam"] == "Bhakra") & (feats["window_start"] == w1[0])].iloc[0]
    assert abs(row["mean_storage"] - 5.0) < 1e-9  # only the 06-26 point
    assert abs(row["delta_storage"] - 0.0) < 1e-9


def test_window_features_empty_window_is_na_and_aligned():
    feats = window_features(normalize(_raw()), years=[2025])
    windows = monsoon_windows(2025)
    # output windows are exactly the monsoon_windows for the year
    got = sorted(
        set(
            zip(
                feats[feats.dam == "Bhakra"]["window_start"],
                feats[feats.dam == "Bhakra"]["window_end"],
            )
        )
    )
    assert got == sorted(windows)
    # a window with no data (e.g. the last, late-Sept) has NA features
    late = feats[(feats.dam == "Bhakra") & (feats.window_start == windows[-1][0])].iloc[
        0
    ]
    assert pd.isna(late["mean_storage"])
    assert pd.isna(late["delta_storage"])


def test_window_features_columns_exact():
    feats = window_features(normalize(_raw()), years=[2025])
    assert list(feats.columns) == [
        "year",
        "window_start",
        "window_end",
        "dam",
        "mean_storage",
        "delta_storage",
    ]


def test_load_frames_concatenates(tmp_path):
    a = tmp_path / "a.csv"
    b = tmp_path / "b.csv"
    _raw().to_csv(a, index=False)
    _raw().iloc[:2].assign(dam="Pong").to_csv(b, index=False)
    df = load_frames([a, b])
    assert set(df["dam"]) == {"Bhakra", "Pong"}
    assert pd.api.types.is_datetime64_any_dtype(df["date"])
