# tests/test_dataset.py
import pandas as pd
import pytest

from sailaab.dataset import add_lags, label_events, assemble


def _frame():
    return pd.DataFrame(
        {
            "district": ["A", "A", "A", "B", "B", "B"],
            "window_start": ["2024-06-15", "2024-06-25", "2024-07-05"] * 2,
            "year": [2024] * 6,
            "flooded_fraction": [0.0, 0.01, 0.30, 0.0, 0.0, 0.05],
            "rain_mm": [10.0, 80.0, 250.0, 5.0, 40.0, 90.0],
        }
    )


def test_add_lags_shifts_within_district():
    df = add_lags(_frame(), "rain_mm", lags=2)
    a = df[df.district == "A"].sort_values("window_start")
    assert pd.isna(a["rain_mm_lag1"].iloc[0])
    assert a["rain_mm_lag1"].iloc[1] == 10.0
    assert a["rain_mm_lag1"].iloc[2] == 80.0
    assert a["rain_mm_lag2"].iloc[2] == 10.0


def test_lags_do_not_leak_across_districts():
    df = add_lags(_frame(), "rain_mm", lags=1)
    b = df[df.district == "B"].sort_values("window_start")
    assert pd.isna(b["rain_mm_lag1"].iloc[0])  # not A's last value


def test_label_events_uses_config_threshold():
    df = label_events(_frame(), threshold=0.02)
    assert df["flood_event"].tolist() == [0, 0, 1, 0, 0, 1]


def test_assemble_adds_antecedent_and_week_index():
    df = assemble(_frame())
    a = df[df.district == "A"].sort_values("window_start")
    assert a["antecedent_fraction"].iloc[2] == 0.01  # previous window's fraction
    assert a["week_of_season"].tolist() == [0, 1, 2]
