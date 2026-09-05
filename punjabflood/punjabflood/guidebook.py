"""Loaders for the digitised Punjab WRD guidebook tables (``data/reference/wrd/``).

The CSVs are produced by ``scripts/digitise_guidebook.py`` from the guidebook's text layer
and checked digit by digit against the rendered pages (``VERIFICATION.md`` in the same
folder). Loaders validate shape and vocabulary so a silent corruption cannot pass.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

REF = Path(__file__).resolve().parents[1] / "data" / "reference" / "wrd"
PEAK_TABLES = {
    "harike_hussainiwala": "peaks_harike_hussainiwala.csv",
    "ropar": "peaks_ropar.csv",
    "dhilwan": "peaks_dhilwan.csv",
}
YEARS = list(range(1988, 2026))
CLASSES = {"H", "M", "L", ""}


class GuidebookDataError(ValueError):
    pass


def load_peaks(name: str, ref: Path = REF) -> pd.DataFrame:
    if name not in PEAK_TABLES:
        raise KeyError(f"unknown peak table {name!r}; choose from {sorted(PEAK_TABLES)}")
    df = pd.read_csv(ref / PEAK_TABLES[name], dtype={"wrd_class": "string"}, keep_default_na=True)
    if list(df["year"]) != YEARS:
        raise GuidebookDataError(f"{name}: years are not 1988..2025 contiguous")
    if "wrd_class" in df:
        df["wrd_class"] = df["wrd_class"].fillna("")
        bad = set(df["wrd_class"]) - CLASSES
        if bad:
            raise GuidebookDataError(f"{name}: unexpected classes {bad}")
    if "date" in df:
        parsed = pd.to_datetime(df["date"], format="%Y-%m-%d", errors="coerce")
        if parsed.isna().any() or (parsed.dt.year != df["year"]).any():
            raise GuidebookDataError(f"{name}: a date does not parse or sits in the wrong year")
    return df


def load_thresholds(ref: Path = REF) -> pd.DataFrame:
    df = pd.read_csv(ref / "thresholds.csv")
    need = {"river", "station", "low_min", "low_max", "med_min", "med_max", "high_min"}
    if not need <= set(df.columns):
        raise GuidebookDataError("thresholds.csv is missing columns")
    return df


def load_travel_times(ref: Path = REF) -> pd.DataFrame:
    return pd.read_csv(ref / "travel_times.csv")


def wrd_class_by_year(ref: Path = REF) -> pd.Series:
    """The WRD's own High/Medium/Low class per year (Harike table), '' when unclassed."""
    df = load_peaks("harike_hussainiwala", ref)
    return df.set_index("year")["wrd_class"]
