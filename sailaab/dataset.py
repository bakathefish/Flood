# sailaab/dataset.py
"""Forecaster dataset assembly — pure pandas, no EE."""

import pandas as pd

from sailaab import config


def add_lags(df: pd.DataFrame, col: str, lags: int) -> pd.DataFrame:
    out = df.sort_values(["district", "window_start"]).copy()
    for k in range(1, lags + 1):
        out[f"{col}_lag{k}"] = out.groupby("district")[col].shift(k)
    return out


def label_events(
    df: pd.DataFrame, threshold: float = config.FLOOD_EVENT_FRACTION
) -> pd.DataFrame:
    out = df.copy()
    out["flood_event"] = (out["flooded_fraction"] > threshold).astype(int)
    return out


def assemble(df: pd.DataFrame) -> pd.DataFrame:
    out = df.sort_values(["district", "window_start"]).copy()
    out["antecedent_fraction"] = out.groupby("district")["flooded_fraction"].shift(1)
    out["week_of_season"] = out.groupby(["district", "year"]).cumcount()
    return out
