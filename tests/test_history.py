# tests/test_history.py
"""Tests for the pure logic behind the 70-year flood-context milestone figure
(``sailaab.history``): unit normalisation (lakh_ha / Mha / ha -> ha, crore-INR
and count passthrough), disjoint metric-class tagging (flooded area vs crop-damage
area vs lives vs houses -- never conflated), period->x mapping, and schema +
anchor-value validation of the consolidated ``data/punjab_flood_damage_history.csv``.

Rendering (``pipeline/make_flood_history.py``) is not tested here -- only the
deterministic transforms and the committed consolidated record it depends on.
"""

from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from sailaab.history import (
    AREA_CLASSES,
    AREA_UNIT_TO_HA,
    HISTORY_COLUMNS,
    KNOWN_UNITS,
    METRIC_CLASS,
    load_history,
    metric_class,
    milestones,
    normalize_value,
    period_to_year,
    to_ha,
)

ROOT = Path(__file__).resolve().parents[1]
HISTORY_CSV = ROOT / "data" / "punjab_flood_damage_history.csv"


# --------------------------------------------------------------------------- #
# unit conversion  (lakh_ha / Mha / ha -> ha, crore + count passthrough)
# --------------------------------------------------------------------------- #
def test_to_ha_exact_area_conversions():
    assert to_ha(1.0, "ha") == pytest.approx(1.0)
    assert to_ha(2.79, "Mha") == pytest.approx(2_790_000.0)  # the 1953-2010 anchor
    assert to_ha(0.52, "lakh_ha") == pytest.approx(52_000.0)  # 2018-19 crops
    assert to_ha(1.985, "lakh_ha") == pytest.approx(198_500.0)


def test_to_ha_rejects_non_area_unit():
    with pytest.raises(ValueError):
        to_ha(10.0, "crore_inr")
    with pytest.raises(ValueError):
        to_ha(10.0, "count")


def test_normalize_value_area_goes_to_ha():
    assert normalize_value(0.001, "Mha") == pytest.approx((1_000.0, "ha"))
    assert normalize_value(0.023, "Mha") == pytest.approx((23_000.0, "ha"))
    assert normalize_value(105183.0, "ha") == pytest.approx((105_183.0, "ha"))


def test_normalize_value_crore_and_count_passthrough():
    v, u = normalize_value(18.23, "crore_inr")
    assert (v, u) == pytest.approx((18.23, "crore_inr"))
    v, u = normalize_value(35, "count")  # lives lost
    assert (v, u) == pytest.approx((35.0, "count"))


def test_normalize_value_rejects_unknown_unit():
    with pytest.raises(ValueError):
        normalize_value(1.0, "acres")


def test_normalize_value_rejects_negative():
    with pytest.raises(ValueError):
        normalize_value(-1.0, "ha")
    with pytest.raises(ValueError):
        normalize_value(-5, "count")


def test_known_units_set():
    assert KNOWN_UNITS == {"ha", "lakh_ha", "Mha", "crore_inr", "count"}
    assert set(AREA_UNIT_TO_HA) == {"ha", "lakh_ha", "Mha"}


# --------------------------------------------------------------------------- #
# metric-class tagging  (the four load-bearing classes never conflated)
# --------------------------------------------------------------------------- #
def test_metric_class_assignments():
    assert metric_class("max_area_affected") == "flooded_area"
    assert metric_class("area_affected") == "flooded_area"
    assert metric_class("crop_damage_area") == "crop_damage_area"
    assert metric_class("crop_damage_value") == "crop_damage_value"
    assert metric_class("lives_lost") == "lives"
    assert metric_class("houses_damaged") == "houses"


def test_metric_class_rejects_unknown_metric():
    with pytest.raises(ValueError):
        metric_class("area_affected_or_something")


def test_metric_classes_are_disjoint():
    members = defaultdict(set)
    for m, cls in METRIC_CLASS.items():
        members[cls].add(m)
    # the load-bearing classes are all present and non-empty
    for cls in ("flooded_area", "crop_damage_area", "lives", "houses"):
        assert members[cls], f"no metric maps to {cls}"
    # no metric belongs to two classes; classes share no members
    classes = list(members)
    for i in range(len(classes)):
        for j in range(i + 1, len(classes)):
            assert members[classes[i]].isdisjoint(members[classes[j]])
    # flooded area is never crop-damage area (the never-merge rule)
    assert metric_class("area_affected") != metric_class("crop_damage_area")


def test_flooded_and_crop_are_the_two_area_classes():
    assert AREA_CLASSES == {"flooded_area", "crop_damage_area"}


# --------------------------------------------------------------------------- #
# period -> plotting x
# --------------------------------------------------------------------------- #
def test_period_to_year_single_calendar_year():
    assert period_to_year("2016") == pytest.approx(2016.0)
    assert period_to_year("2025") == pytest.approx(2025.0)


def test_period_to_year_financial_year_uses_start():
    assert period_to_year("2018-19") == pytest.approx(2018.0)
    assert period_to_year("2021-22") == pytest.approx(2021.0)


def test_period_to_year_undated_span_is_nan():
    # the 1953-2010 "worst year" carries no published year -> not placed on the axis
    assert np.isnan(period_to_year("1953-2010"))


# --------------------------------------------------------------------------- #
# consolidated CSV: schema + anchor values load correctly
# --------------------------------------------------------------------------- #
def test_history_csv_schema():
    df = load_history(HISTORY_CSV)
    for col in HISTORY_COLUMNS:
        assert col in df.columns
    # derived columns added by the loader
    for col in ("metric_class", "value_norm", "unit_norm", "value_ha"):
        assert col in df.columns
    # every unit and metric in the committed file is known
    assert set(df["unit"]).issubset(KNOWN_UNITS)
    assert df["value"].min() >= 0


def _one(df, period, metric):
    hit = df[(df["period"] == period) & (df["metric"] == metric)]
    assert len(hit) == 1, f"expected exactly one row for {period}/{metric}, got {len(hit)}"
    return hit.iloc[0]


def test_history_anchor_2p79_Mha_loads():
    df = load_history(HISTORY_CSV)
    row = _one(df, "1953-2010", "max_area_affected")
    assert row["value"] == pytest.approx(2.79)
    assert row["unit"] == "Mha"
    assert row["metric_class"] == "flooded_area"
    assert row["value_ha"] == pytest.approx(2_790_000.0)


def test_history_anchor_2016_2018_area_series():
    df = load_history(HISTORY_CSV)
    assert _one(df, "2016", "area_affected")["value"] == pytest.approx(0.001)
    assert _one(df, "2017", "area_affected")["value"] == pytest.approx(0.006)
    assert _one(df, "2018", "area_affected")["value"] == pytest.approx(0.023)
    # quiet baseline: every 2016-18 flooded area is <= 0.023 Mha
    area = df[(df["metric"] == "area_affected") & df["period"].isin(["2016", "2017", "2018"])]
    assert area["value"].max() == pytest.approx(0.023)
    # crop-damage VALUE (crore) stays crore, never conflated with area
    assert _one(df, "2017", "crop_damage_value")["value"] == pytest.approx(18.23)
    assert _one(df, "2017", "crop_damage_value")["unit_norm"] == "crore_inr"


def test_history_anchor_lives_series():
    df = load_history(HISTORY_CSV)
    lives = df[df["metric"] == "lives_lost"].set_index("period")["value"]
    assert lives.loc["2018-19"] == pytest.approx(35)
    assert lives.loc["2019-20"] == pytest.approx(20)
    assert lives.loc["2020-21"] == pytest.approx(16)
    assert lives.loc["2021-22"] == pytest.approx(9)
    assert (df[df["metric"] == "lives_lost"]["metric_class"] == "lives").all()


def test_history_2025_enters_as_two_distinct_area_points():
    df = load_history(HISTORY_CSV)
    sar = _one(df, "2025", "area_affected")  # SAR single-pass mapped extent
    gird = _one(df, "2025", "crop_damage_area")  # girdawari cumulative crop damage
    assert sar["value_ha"] == pytest.approx(105_183.0)
    assert gird["value_ha"] == pytest.approx(198_524.0)
    # the two 2025 points are different metric classes -> never merged
    assert sar["metric_class"] == "flooded_area"
    assert gird["metric_class"] == "crop_damage_area"
    assert sar["metric_class"] != gird["metric_class"]


def test_history_all_area_rows_normalise_to_ha():
    df = load_history(HISTORY_CSV)
    area = df[df["metric_class"].isin(AREA_CLASSES)]
    assert (area["unit_norm"] == "ha").all()
    assert area["value_ha"].notna().all()
    # non-area rows carry NaN in value_ha (no silent unit mixing)
    non_area = df[~df["metric_class"].isin(AREA_CLASSES)]
    assert non_area["value_ha"].isna().all()


def test_milestones_filters_by_class():
    df = load_history(HISTORY_CSV)
    flooded = milestones(df, "flooded_area")
    assert (flooded["metric_class"] == "flooded_area").all()
    # contains both the 1953-2010 anchor and the 2025 SAR point
    assert "1953-2010" in set(flooded["period"])
    assert "2025" in set(flooded["period"])


# --------------------------------------------------------------------------- #
# loader validation on malformed input
# --------------------------------------------------------------------------- #
def test_load_history_rejects_unknown_unit(tmp_path):
    p = tmp_path / "bad_unit.csv"
    p.write_text(
        "period,metric,value,unit,source_uuid\n"
        "2016,area_affected,0.001,acres,uuid-x\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        load_history(p)


def test_load_history_rejects_negative_value(tmp_path):
    p = tmp_path / "bad_value.csv"
    p.write_text(
        "period,metric,value,unit,source_uuid\n"
        "2016,area_affected,-0.001,Mha,uuid-x\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        load_history(p)


def test_load_history_rejects_unknown_metric(tmp_path):
    p = tmp_path / "bad_metric.csv"
    p.write_text(
        "period,metric,value,unit,source_uuid\n"
        "2016,rainfall_mm,300,ha,uuid-x\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        load_history(p)


def test_load_history_rejects_missing_column(tmp_path):
    p = tmp_path / "bad_schema.csv"
    p.write_text("period,metric,value,unit\n2016,area_affected,0.001,Mha\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_history(p)
