# sailaab/stats.py
"""Tidy GEE reduceRegions exports into analysis frames."""

import pandas as pd

_REQUIRED = ["ADM2_NAME", "flooded_ha", "crop_flooded_ha", "window_start", "year"]


def tidy_district_export(raw: pd.DataFrame) -> pd.DataFrame:
    missing = [c for c in _REQUIRED if c not in raw.columns]
    if missing:
        raise ValueError(f"export missing columns: {missing}")
    df = raw[_REQUIRED].rename(columns={"ADM2_NAME": "district"}).copy()
    df["flooded_ha"] = df["flooded_ha"].astype(float)
    df["crop_flooded_ha"] = df["crop_flooded_ha"].astype(float)
    return df[["district", "window_start", "year", "flooded_ha", "crop_flooded_ha"]]


def flooded_fraction(df: pd.DataFrame, district_areas: pd.DataFrame) -> pd.DataFrame:
    unknown = set(df["district"]) - set(district_areas["district"])
    if unknown:
        raise ValueError(f"no area for districts: {sorted(unknown)}")
    out = df.merge(district_areas, on="district", how="left")
    out["flooded_fraction"] = out["flooded_ha"] / out["area_ha"]
    return out
