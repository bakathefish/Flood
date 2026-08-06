# tests/test_daily_flood_data.py
"""Contract for the per-day district flood series.

The daily series is the forecaster's label source, so a silent corruption here
would quietly invalidate every downstream number. These checks pin the shape,
the reconciliation against the committed window product, and the one property
that matters most for a warning system: a day the satellite never observed must
never be readable as a dry day.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DAILY = DATA / "gfm_district_daily_2015_2025.csv"
WINDOWS = DATA / "gfm_district_window_fractions_2015_2025.csv"


@pytest.fixture(scope="module")
def daily():
    return pd.read_csv(DAILY, parse_dates=["date"])


def test_daily_series_exists_and_covers_every_district(daily):
    assert len(daily) > 20000
    assert daily["district"].nunique() == 20
    assert set(daily.columns) == {"date", "district", "flooded_ha", "fraction"}


def test_every_monsoon_day_of_every_year_is_present(daily):
    years = daily["date"].dt.year.unique()
    assert sorted(years) == list(range(2015, 2026))
    per_year_days = daily.groupby(daily["date"].dt.year)["date"].nunique()
    # The season is half-open [Jun 15, Sep 30), matching every other window in
    # the project, which is 107 days. Leap years do not change it: Feb is
    # outside the monsoon.
    assert (per_year_days == 107).all(), per_year_days.to_dict()


def test_fractions_are_bounded(daily):
    f = daily["fraction"].dropna()
    assert (f >= 0).all()
    assert (f <= 1).all()


def test_daily_values_never_exceed_their_window_union(daily):
    """The window product unions the same days, so a daily fraction above its
    own window's fraction would mean the two products disagree about reality."""
    win = pd.read_csv(WINDOWS)
    d = daily.dropna(subset=["fraction"]).copy()
    violations = 0
    for _, w in win.iterrows():
        m = (
            (d["district"] == w["district"])
            & (d["date"] >= pd.Timestamp(w["window_start"]))
            & (d["date"] < pd.Timestamp(w["window_end"]))
        )
        sub = d.loc[m, "fraction"]
        if len(sub) and sub.max() > w["fraction"] + 1e-6:
            violations += 1
    assert violations == 0, f"{violations} window rows contradicted by daily values"


def test_the_2025_event_is_present_and_peaks_in_the_right_place(daily):
    ev = daily[
        (daily["date"] >= "2025-08-22") & (daily["date"] <= "2025-09-06")
    ]
    peak = ev.loc[ev["fraction"].idxmax()]
    assert peak["fraction"] > 0.02
    # the worst-hit districts of the real event
    assert peak["district"] in {
        "Kapurthala",
        "Firozpur",
        "Gurdaspur",
        "Tarn Taran",
        "Amritsar",
        "Jalandhar",
    }


def test_unobserved_days_are_null_rather_than_zero():
    """Regression guard on the distinction that keeps a false all-clear out of
    the label set. A day the fetcher never probed must be NaN, not 0.0."""
    import csv

    progress = DATA / "gfm" / "_decade_progress.csv"
    if not progress.exists():  # raster cache is gitignored; skip when absent
        pytest.skip("GFM progress log not present in this checkout")
    with progress.open(newline="", encoding="utf-8") as fh:
        probed = {r["day"] for r in csv.DictReader(fh) if r.get("day")}
    d = pd.read_csv(DAILY, parse_dates=["date"])
    d["day"] = d["date"].dt.strftime("%Y-%m-%d")
    unprobed = d[~d["day"].isin(probed)]
    if unprobed.empty:
        pytest.skip("every monsoon day was probed in this cache")
    assert unprobed["fraction"].isna().all()
