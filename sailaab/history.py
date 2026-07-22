# sailaab/history.py
"""Pure, testable logic for the *70-year flood-context* milestone figure
(``atlas/punjab_flood_history.png``).

Places the 2025 Punjab flood against the **public damage record**. There is **no
continuous public annual series** on the OGD portal (data.gov.in) -- the record
is a set of milestones from three resources of different vintages and different
*metrics*. This module normalises those milestones onto common units and tags
each with a **metric class**, so the figure can keep classes strictly separate:

    flooded_area        (mapped / "area affected" flood extent)      -> ha
    crop_damage_area    (crop area reported damaged / girdawari)     -> ha
    crop_damage_value   (crop damage value)                          -> crore INR
    lives               (human lives lost)                           -> count
    houses              (houses / huts damaged)                      -> count

flooded area, crop-damage area, lives and houses are **never conflated** -- they
are different quantities in different units. 2025 therefore enters as *two*
separate area points (SAR single-pass mapped extent in ``flooded_area``, official
Special Girdawari cumulative crop damage in ``crop_damage_area``), never merged.

Unit rules (the pre-declaration in ``docs/notes/flood-history.md``):
* area units ``ha`` / ``lakh_ha`` (x1e5) / ``Mha`` (x1e6) all normalise to ha;
* ``crore_inr`` and ``count`` pass through unchanged;
* negative values and unknown units are rejected -- no silent coercion.

Rendering / IO lives in ``pipeline/make_flood_history.py``; this module holds only
the deterministic transforms and the schema/validation for the committed
consolidated record ``data/punjab_flood_damage_history.csv``.
"""

from __future__ import annotations

import re

import pandas as pd

# --- unit normalisation ------------------------------------------------------
# area units -> hectares (the common area unit for the figure)
AREA_UNIT_TO_HA: dict[str, float] = {
    "ha": 1.0,
    "lakh_ha": 1.0e5,  # 1 lakh = 100,000
    "Mha": 1.0e6,  # 1 million hectares
}
# units that carry through unchanged (not areas)
PASSTHROUGH_UNITS: frozenset[str] = frozenset({"crore_inr", "count"})
KNOWN_UNITS: frozenset[str] = frozenset(AREA_UNIT_TO_HA) | PASSTHROUGH_UNITS

# --- metric -> class ---------------------------------------------------------
# Every metric that may appear in the consolidated record maps to exactly one
# class. Classes are the never-conflated buckets the figure draws with distinct
# markers and stated units.
METRIC_CLASS: dict[str, str] = {
    "max_area_affected": "flooded_area",  # 1953-2010 worst single-year extent
    "area_affected": "flooded_area",  # MoEFCC / SAR mapped flood extent
    "crop_damage_area": "crop_damage_area",  # hydromet crops / girdawari
    "crop_damage_value": "crop_damage_value",  # crop damage value (crore INR)
    "lives_lost": "lives",  # human lives lost
    "houses_damaged": "houses",  # houses / huts damaged
}

# classes whose normalised unit is hectares (the two area classes)
AREA_CLASSES: frozenset[str] = frozenset({"flooded_area", "crop_damage_area"})

# normalised unit carried by each class (for axis / legend labels)
CLASS_UNIT: dict[str, str] = {
    "flooded_area": "ha",
    "crop_damage_area": "ha",
    "crop_damage_value": "crore_inr",
    "lives": "count",
    "houses": "count",
}

# consolidated-record schema (one row per period x metric)
HISTORY_COLUMNS: list[str] = ["period", "metric", "value", "unit", "source_uuid"]

_YEAR = re.compile(r"^\d{4}$")
_FIN_YEAR = re.compile(r"^(\d{4})-\d{2}$")  # financial year e.g. 2018-19
_SPAN = re.compile(r"^\d{4}-\d{4}$")  # multi-year span e.g. 1953-2010


# --------------------------------------------------------------------------- #
# unit conversion
# --------------------------------------------------------------------------- #
def to_ha(value: float, unit: str) -> float:
    """Convert an **area** ``value`` in ``unit`` to hectares.

    ``unit`` must be one of :data:`AREA_UNIT_TO_HA` (``ha`` / ``lakh_ha`` /
    ``Mha``). Non-area units raise ``ValueError`` -- use :func:`normalize_value`
    for the general (area or passthrough) case.
    """
    if unit not in AREA_UNIT_TO_HA:
        raise ValueError(
            f"to_ha: {unit!r} is not an area unit; expected one of "
            f"{sorted(AREA_UNIT_TO_HA)}"
        )
    return float(value) * AREA_UNIT_TO_HA[unit]


def normalize_value(value: float, unit: str) -> tuple[float, str]:
    """Normalise ``(value, unit)`` -> ``(value_norm, unit_norm)``.

    Area units collapse to hectares; ``crore_inr`` and ``count`` pass through
    unchanged. Negative values and unknown units raise ``ValueError`` (no silent
    coercion or unit invention).
    """
    v = float(value)
    if v < 0:
        raise ValueError(f"normalize_value: negative value {v!r} not allowed")
    if unit in AREA_UNIT_TO_HA:
        return v * AREA_UNIT_TO_HA[unit], "ha"
    if unit in PASSTHROUGH_UNITS:
        return v, unit
    raise ValueError(
        f"normalize_value: unknown unit {unit!r}; known units are "
        f"{sorted(KNOWN_UNITS)}"
    )


# --------------------------------------------------------------------------- #
# metric-class tagging
# --------------------------------------------------------------------------- #
def metric_class(metric: str) -> str:
    """Class for ``metric`` (see :data:`METRIC_CLASS`). Unknown metric raises."""
    try:
        return METRIC_CLASS[metric]
    except KeyError:
        raise ValueError(
            f"metric_class: unknown metric {metric!r}; known metrics are "
            f"{sorted(METRIC_CLASS)}"
        ) from None


# --------------------------------------------------------------------------- #
# period -> plotting x
# --------------------------------------------------------------------------- #
def period_to_year(period: str) -> float:
    """Representative axis year for a ``period`` label.

    * ``"2016"`` (calendar year) -> ``2016.0``
    * ``"2018-19"`` (financial year) -> ``2018.0`` (the FY start, i.e. that
      monsoon's calendar year)
    * ``"1953-2010"`` (multi-year span) -> ``nan`` -- the "worst year" has no
      published year, so it is drawn as an undated reference, not placed on the
      time axis.
    """
    period = str(period).strip()
    if _YEAR.match(period):
        return float(period)
    m = _FIN_YEAR.match(period)
    if m:
        return float(m.group(1))
    if _SPAN.match(period):
        return float("nan")
    raise ValueError(f"period_to_year: unrecognised period {period!r}")


# --------------------------------------------------------------------------- #
# consolidated record: load + validate + derive
# --------------------------------------------------------------------------- #
def validate_history(df: pd.DataFrame) -> None:
    """Raise ``ValueError`` if ``df`` violates the consolidated-record contract:
    required columns present, known metrics, known units, non-negative values."""
    missing = [c for c in HISTORY_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"history record missing columns: {missing}")
    unknown_metrics = sorted(set(df["metric"]) - set(METRIC_CLASS))
    if unknown_metrics:
        raise ValueError(f"history record has unknown metrics: {unknown_metrics}")
    unknown_units = sorted(set(df["unit"]) - set(KNOWN_UNITS))
    if unknown_units:
        raise ValueError(f"history record has unknown units: {unknown_units}")
    if not pd.to_numeric(df["value"], errors="coerce").notna().all():
        raise ValueError("history record has non-numeric / missing values")
    if (pd.to_numeric(df["value"]) < 0).any():
        raise ValueError("history record has negative values")


def load_history(path) -> pd.DataFrame:
    """Load and validate the consolidated milestone record, returning a
    DataFrame with the source columns plus derived ``metric_class``,
    ``value_norm``, ``unit_norm`` and ``value_ha`` (NaN for non-area rows).
    """
    df = pd.read_csv(path)
    validate_history(df)
    df = df.copy()
    df["metric_class"] = df["metric"].map(metric_class)
    norm = [normalize_value(v, u) for v, u in zip(df["value"], df["unit"])]
    df["value_norm"] = [v for v, _ in norm]
    df["unit_norm"] = [u for _, u in norm]
    df["value_ha"] = [
        vn if cls in AREA_CLASSES else float("nan")
        for vn, cls in zip(df["value_norm"], df["metric_class"])
    ]
    return df


def milestones(df: pd.DataFrame, metric_class_name: str) -> pd.DataFrame:
    """Rows of ``df`` belonging to ``metric_class_name`` (index reset)."""
    return df[df["metric_class"] == metric_class_name].reset_index(drop=True)
