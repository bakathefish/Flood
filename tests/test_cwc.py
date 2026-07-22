# tests/test_cwc.py
"""Tests for the pure logic behind the CWC flood-forecast station-gap analysis
(``sailaab.cwc``): schema validation of the "as on Jan 2018" state-wise table,
national totals (226 = 166 level + 60 inflow), the aggregate ``Total`` row
excluded from per-state rows, per-row ``level + inflow == total`` consistency,
stable-descending ranking by total stations, and the absent-state -> 0 semantics
that is the whole point for Punjab.

Rendering (``pipeline/make_cwc_gap.py``) is not tested here - only the
deterministic transforms it depends on."""

from pathlib import Path

import pandas as pd
import pytest

from sailaab.cwc import (
    REQUIRED_COLUMNS,
    load_stations,
    national_totals,
    state_totals,
    station_count,
)

ROOT = Path(__file__).resolve().parents[1]
CSV = ROOT / "data" / "cwc_ff_stations_2018.csv"


# --------------------------------------------------------------------------- #
# schema
# --------------------------------------------------------------------------- #
def test_load_stations_schema_columns():
    df = load_stations(CSV)
    for col in REQUIRED_COLUMNS:
        assert col in df.columns


def test_load_stations_excludes_total_row_and_lists_22_states():
    df = load_stations(CSV)
    # the aggregate "Total" row is validated then dropped -> 22 states/UTs
    assert len(df) == 22
    labels = {s.strip().casefold() for s in df["state_ut"]}
    assert "total" not in labels
    assert "punjab" not in labels  # Punjab is genuinely absent from the table


def test_load_stations_rejects_missing_column(tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text("state_ut,level_stations,total_stations\nA,1,1\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_stations(bad)


def test_load_stations_rejects_row_where_level_plus_inflow_ne_total(tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text(
        "state_ut,level_stations,inflow_stations,total_stations\n"
        "Andhra Pradesh,7,7,14\n"
        "Wrongland,2,2,5\n",  # 2 + 2 != 5
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        load_stations(bad)


def test_load_stations_rejects_total_row_that_disagrees_with_state_sums(tmp_path):
    # Total row is internally consistent (99 + 99 == 198) but disagrees with the
    # state-row sums (7 + 0 = 7 level, 7 + 1 = 8 inflow) -> load must reject it.
    bad = tmp_path / "bad.csv"
    bad.write_text(
        "state_ut,level_stations,inflow_stations,total_stations\n"
        "Andhra Pradesh,7,7,14\n"
        "Haryana,0,1,1\n"
        "Total,99,99,198\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        load_stations(bad)


# --------------------------------------------------------------------------- #
# per-row consistency: level + inflow == total
# --------------------------------------------------------------------------- #
def test_every_state_row_is_internally_consistent():
    df = load_stations(CSV)
    assert (df["level_stations"] + df["inflow_stations"] == df["total_stations"]).all()


# --------------------------------------------------------------------------- #
# national totals
# --------------------------------------------------------------------------- #
def test_national_totals_226_equals_166_level_plus_60_inflow():
    df = load_stations(CSV)
    tot = national_totals(df)
    assert tot["level"] == 166
    assert tot["inflow"] == 60
    assert tot["total"] == 226
    assert tot["level"] + tot["inflow"] == tot["total"]


def test_national_totals_match_the_declared_total_row():
    # the summed state rows must reproduce the table's own "Total" row (226)
    raw = pd.read_csv(CSV)
    total_row = raw[raw["state_ut"].str.strip().str.casefold() == "total"].iloc[0]
    df = load_stations(CSV)
    tot = national_totals(df)
    assert tot["level"] == int(total_row["level_stations"])
    assert tot["inflow"] == int(total_row["inflow_stations"])
    assert tot["total"] == int(total_row["total_stations"])


# --------------------------------------------------------------------------- #
# absent-state -> 0 semantics (the Punjab claim) + Haryana anchor
# --------------------------------------------------------------------------- #
def test_station_count_punjab_is_zero_by_absence():
    df = load_stations(CSV)
    assert station_count(df, "Punjab") == 0
    assert station_count(df, "Punjab", kind="level") == 0
    assert station_count(df, "Punjab", kind="inflow") == 0


def test_station_count_haryana_is_one_inflow():
    df = load_stations(CSV)
    assert station_count(df, "Haryana") == 1
    assert station_count(df, "Haryana", kind="level") == 0
    assert station_count(df, "Haryana", kind="inflow") == 1


def test_station_count_is_case_and_whitespace_insensitive():
    df = load_stations(CSV)
    assert station_count(df, "  haryana ") == 1
    assert station_count(df, "PUNJAB") == 0


def test_station_count_neighbours_anchor():
    df = load_stations(CSV)
    assert station_count(df, "Jammu and Kashmir") == 3
    assert station_count(df, "Rajasthan") == 3
    assert station_count(df, "Rajasthan", kind="inflow") == 3


# --------------------------------------------------------------------------- #
# ranking: stable, descending by total
# --------------------------------------------------------------------------- #
def test_state_totals_ranked_descending():
    df = load_stations(CSV)
    ranked = state_totals(df)
    totals = ranked["total_stations"].tolist()
    assert totals == sorted(totals, reverse=True)
    assert ranked.iloc[0]["state_ut"] == "Uttar Pradesh"  # 40, the max
    assert ranked.iloc[0]["total_stations"] == 40


def test_state_totals_is_stable_within_ties():
    # four states all have total 10; input order is Karnataka, Maharashtra,
    # Tamil Nadu, Telangana -> a stable descending sort must preserve that order.
    df = load_stations(CSV)
    ranked = state_totals(df)
    tens = [s for s in ranked["state_ut"] if station_count(df, s) == 10]
    assert tens == ["Karnataka", "Maharashtra", "Tamil Nadu", "Telangana"]


def test_state_totals_stable_on_synthetic_ties():
    df = pd.DataFrame(
        {
            "state_ut": ["A", "B", "C", "D"],
            "level_stations": [5, 3, 3, 1],
            "inflow_stations": [0, 0, 0, 0],
            "total_stations": [5, 3, 3, 1],
        }
    )
    ranked = state_totals(df)
    assert ranked["state_ut"].tolist() == ["A", "B", "C", "D"]  # B before C (tie kept)


def test_state_totals_does_not_mutate_input():
    df = load_stations(CSV)
    before = df.copy()
    _ = state_totals(df)
    pd.testing.assert_frame_equal(df, before)
