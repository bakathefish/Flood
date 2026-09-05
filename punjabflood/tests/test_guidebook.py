from __future__ import annotations

import pytest

from punjabflood import constants as C
from punjabflood import guidebook


def test_peak_tables_have_38_contiguous_years():
    for name in guidebook.PEAK_TABLES:
        df = guidebook.load_peaks(name)
        assert list(df["year"]) == list(range(1988, 2026)), name


def test_known_cells_match_the_printed_pages():
    hk = guidebook.load_peaks("harike_hussainiwala").set_index("year")
    assert hk.loc[2023, "harike_us_cusecs"] == 301061 and hk.loc[2023, "wrd_class"] == "H"
    assert hk.loc[2025, "harike_us_cusecs"] == 347548 and hk.loc[2025, "wrd_class"] == "H"
    assert hk.loc[1988, "harike_us_cusecs"] == 600000 and hk.loc[1988, "wrd_class"] == "H"
    assert hk.loc[2019, "wrd_class"] == "L" and hk.loc[2019, "harike_us_cusecs"] == 119250
    assert (
        hk.loc[2002, "wrd_class"] == ""
        and hk.loc[2002, "hussainiwala_ds_cusecs"] != hk.loc[2002, "hussainiwala_ds_cusecs"]
    )
    assert (hk["wrd_class"] == "H").sum() == 5  # 1988, 1994, 1995, 2023, 2025
    dh = guidebook.load_peaks("dhilwan").set_index("year")
    assert dh.loc[2023, "date"] == "2023-08-17" and dh.loc[2023, "discharge_cusecs"] == 237500
    assert dh.loc[2025, "date"] == "2025-08-31" and dh.loc[2025, "discharge_cusecs"] == 235494
    assert dh.loc[1988, "gauge_ft"] == 740.5
    rp = guidebook.load_peaks("ropar").set_index("year")
    assert rp.loc[2023, "us_cusecs"] == 125722 and rp.loc[2025, "us_cusecs"] == 117282
    assert rp.loc[1988, "us_cusecs"] == 369736


def test_thresholds_csv_agrees_with_constants():
    df = guidebook.load_thresholds().set_index("station")
    assert len(df) == len(C.CONTROL_POINTS)
    for st, cp in C.CONTROL_POINTS.items():
        assert df.loc[st, "high_min"] == cp.high_min, st
        assert df.loc[st, "low_min"] == cp.low_min, st
        assert df.loc[st, "med_min"] == cp.med_min, st


def test_travel_times_csv_agrees_with_constants():
    df = guidebook.load_travel_times()
    assert len(df) == len(C.REACHES)
    by_river = df.groupby("river")["hours"].sum()
    assert by_river["Sutlej"] == 52 + 12  # incl. Harike to Hussainiwala
    assert by_river["Beas"] == 72
    assert by_river["Ghaggar"] == 72
    assert df.groupby("river")["km"].sum()["Beas"] == pytest.approx(215.3)


def test_class_by_year_vocabulary():
    s = guidebook.wrd_class_by_year()
    assert set(s.unique()) <= {"H", "M", "L", ""}
    assert s.loc[1995] == "H" and s.loc[1993] == "M"
