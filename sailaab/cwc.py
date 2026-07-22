# sailaab/cwc.py
"""Pure, testable logic for the CWC flood-forecast station-gap analysis
(``atlas/cwc_station_gap.png``).

The single fact this module exists to establish: in the Central Water
Commission's own state-wise table of *existing flood forecasting stations*
("as on Jan 2018", data.gov.in OGD resource
``0ff82e77-8f0c-479c-823e-246c0b38a2c6``, Government Open Data Licence - India),
**Punjab does not appear at all** - zero level-forecast stations, zero
inflow-forecast stations - while the national network counts 226 (166 level +
60 inflow) across 22 states/UTs. That absence is not a null we impute; it is the
table's own silence, and :func:`station_count` renders it as the honest 0.

This module holds only deterministic transforms; all IO/plotting/paths live in
``pipeline/make_cwc_gap.py``:

* :func:`load_stations` - schema-validate the CSV, verify per-row
  ``level + inflow == total``, cross-check the aggregate ``Total`` row against
  the state-row sums, then return the 22 per-state rows (``Total`` dropped).
* :func:`national_totals` - the summed network (166 / 60 / 226).
* :func:`state_totals` - per-state rows ranked stable-descending by total.
* :func:`station_count` - stations for a named state; **absent state -> 0**
  (the Punjab semantics), case/whitespace-insensitive.

The vintage caveat ("as on Jan 2018") and the currency red-team (whether Punjab
has any CWC FF station *today*) live in ``docs/notes/cwc-gap.md`` - not encoded
here, because this module only reads what the 2018 table says.
"""

from __future__ import annotations

import pandas as pd

REQUIRED_COLUMNS = [
    "state_ut",
    "level_stations",
    "inflow_stations",
    "total_stations",
]
_COUNT_COLUMNS = ["level_stations", "inflow_stations", "total_stations"]
_KIND_COLUMN = {
    "total": "total_stations",
    "level": "level_stations",
    "inflow": "inflow_stations",
}
TOTAL_ROW_LABEL = "Total"


def _norm(series_or_str):
    """Case- and whitespace-insensitive key for matching state names."""
    if isinstance(series_or_str, str):
        return series_or_str.strip().casefold()
    return series_or_str.astype(str).str.strip().str.casefold()


def load_stations(path) -> pd.DataFrame:
    """Load and validate the CWC state-wise FF-station table.

    Returns the **per-state rows only** (22 for the shipped 2018 table): the
    aggregate ``Total`` row is validated against the state-row sums and then
    dropped, so callers never double-count it. Counts are coerced to ``int``.

    Raises ``ValueError`` if a required column is missing, if any per-state row
    violates ``level + inflow == total``, or if a present ``Total`` row disagrees
    with the summed state rows. Punjab is genuinely absent from this table; that
    is the finding, not an error - see :func:`station_count`.
    """
    df = pd.read_csv(path)

    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"CWC station table missing columns: {missing}")

    df = df[REQUIRED_COLUMNS].copy()
    for col in _COUNT_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="raise").astype(int)

    is_total = _norm(df["state_ut"]) == TOTAL_ROW_LABEL.casefold()
    states = df[~is_total].reset_index(drop=True)
    totals = df[is_total]

    bad = states[
        states["level_stations"] + states["inflow_stations"] != states["total_stations"]
    ]
    if len(bad):
        names = ", ".join(bad["state_ut"].astype(str))
        raise ValueError(f"level + inflow != total for: {names}")

    sums = {c: int(states[c].sum()) for c in _COUNT_COLUMNS}
    if len(totals):
        row = totals.iloc[0]
        for c in _COUNT_COLUMNS:
            if int(row[c]) != sums[c]:
                raise ValueError(
                    f"Total row {c}={int(row[c])} disagrees with state sum {sums[c]}"
                )

    return states


def national_totals(df: pd.DataFrame) -> dict[str, int]:
    """Summed network across the per-state rows: ``{"level", "inflow", "total"}``.

    For the shipped 2018 table this is ``166 / 60 / 226``. Expects the
    per-state DataFrame from :func:`load_stations` (no ``Total`` row).
    """
    return {
        "level": int(df["level_stations"].sum()),
        "inflow": int(df["inflow_stations"].sum()),
        "total": int(df["total_stations"].sum()),
    }


def state_totals(df: pd.DataFrame) -> pd.DataFrame:
    """Per-state rows ranked by ``total_stations`` **descending, stably** - ties
    keep their input (roughly alphabetical, as published) order.

    A fresh, index-reset copy is returned; the input is never mutated. Stability
    is guaranteed by an explicit secondary key on the original row order rather
    than relying on the sort kind's tie behaviour under a descending sort.
    """
    out = df.reset_index(drop=True).copy()
    out["_ord"] = range(len(out))
    out = out.sort_values(
        ["total_stations", "_ord"], ascending=[False, True], kind="mergesort"
    )
    return out.drop(columns="_ord").reset_index(drop=True)


def station_count(df: pd.DataFrame, state: str, kind: str = "total") -> int:
    """Number of CWC FF stations for ``state`` (``kind`` in level/inflow/total).

    **A state absent from the table returns 0** - this is the Punjab semantics:
    the 2018 table simply does not list Punjab, so its count is an honest zero,
    not a missing value. Matching is case- and whitespace-insensitive.
    """
    if kind not in _KIND_COLUMN:
        raise ValueError(f"kind must be one of {list(_KIND_COLUMN)}; got {kind!r}")
    col = _KIND_COLUMN[kind]
    hit = df[_norm(df["state_ut"]) == _norm(state)]
    if len(hit) == 0:
        return 0
    return int(hit[col].sum())
