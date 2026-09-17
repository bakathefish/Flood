"""Merge the press and archive sweeps of dated BBMB reservoir readings into one reference
table, ``data/reference/bbmb/press_readings.csv``.

Inputs: every ``data/raw/bbmb/readings_*.csv`` and ``data/reference/bbmb/inflow_points.csv``
(the hand-checked rows). The sweep files are written by research agents and are lenient
CSV (unquoted commas in titles); each row is re-parsed by position with the last two
fields as URL and quote where the field count overflows. Rows are kept when the date
parses, the dam is one of the three, and at least one of level, inflow, outflow is a
number inside a plausibility gate (level within 100 ft of the dam's FRL or below it by up
to 250 ft; flows below 2,000,000 cusecs). Duplicates by (date, dam, url) collapse to one
row. Rows flagged ambiguous in their time column keep the flag.

Run from ``punjabflood/``: ``python scripts/ingest_readings.py``.
"""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from punjabflood import constants as C  # noqa: E402

RAW = Path("data/raw/bbmb")
REF = Path("data/reference/bbmb")
OUT = REF / "press_readings.csv"
COLS = [
    "date",
    "dam",
    "level_ft",
    "inflow_cusecs",
    "outflow_cusecs",
    "as_of_time",
    "ambiguous",
    "source_title",
    "source_url",
    "published",
    "quote",
]
DAM_ALIASES = {
    "bhakra": "Bhakra",
    "gobind sagar": "Bhakra",
    "pong": "Pong",
    "maharana pratap sagar": "Pong",
    "ranjit sagar": "Ranjit Sagar",
    "thein": "Ranjit Sagar",
}


def _dam(s: str) -> str | None:
    s = (s or "").strip().lower()
    for k, v in DAM_ALIASES.items():
        if k in s:
            return v
    return None


def _num(s) -> float:
    if s is None:
        return float("nan")
    s = str(s).strip().replace(",", "")
    if not s or s.lower() in ("nan", "none", "n/a", "-"):
        return float("nan")
    m = re.match(r"^-?\d+(\.\d+)?$", s)
    if m:
        return float(s)
    m = re.match(r"^(\d+(\.\d+)?)\s*lakh$", s.lower())
    if m:
        return float(m.group(1)) * 100_000
    return float("nan")


def _rows(path: Path) -> list[dict]:
    """Lenient parse: header defines the column count; overflowing rows keep the last two
    fields as url and quote and join the middle into the title."""
    out = []
    with open(path, encoding="utf-8", errors="replace", newline="") as f:
        reader = csv.reader(f)
        try:
            header = [h.strip() for h in next(reader)]
        except StopIteration:
            return out
        n = len(header)
        for r in reader:
            if not r or all(not x.strip() for x in r):
                continue
            if len(r) > n:
                fixed = r[: n - 3] + [",".join(r[n - 3 : len(r) - 2]), r[-2], r[-1]]
                r = fixed
            if len(r) < n:
                r = r + [""] * (n - len(r))
            out.append(dict(zip(header, r, strict=False)))
    return out


def _gate(dam: str, level_ft: float, inflow: float, outflow: float) -> bool:
    frl = C.DAMS[dam].frl_ft.value
    ok_level = level_ft != level_ft or (frl - 250.0 <= level_ft <= frl + 100.0)
    ok_in = inflow != inflow or 0 <= inflow <= 2_000_000
    ok_out = outflow != outflow or 0 <= outflow <= 2_000_000
    return ok_level and ok_in and ok_out


def ingest(paths: list[Path]) -> pd.DataFrame:
    rows = []
    for p in paths:
        for r in _rows(p):
            dam = _dam(r.get("dam", ""))
            date = pd.to_datetime(r.get("date", ""), errors="coerce")
            if dam is None or date is pd.NaT or date != date:
                continue
            lv, fi, fo = (
                _num(r.get("level_ft")),
                _num(r.get("inflow_cusecs")),
                _num(r.get("outflow_cusecs")),
            )
            if lv != lv and fi != fi and fo != fo:
                continue
            if not _gate(dam, lv, fi, fo):
                continue
            t = (r.get("as_of_time") or r.get("as_on") or "").strip()
            amb = "ambiguous" in t.lower() or str(r.get("approximate", "")).lower() == "yes"
            rows.append(
                {
                    "date": date.date().isoformat(),
                    "dam": dam,
                    "level_ft": lv,
                    "inflow_cusecs": fi,
                    "outflow_cusecs": fo,
                    "as_of_time": t,
                    "ambiguous": amb,
                    "source_title": (r.get("source_title") or r.get("source_short") or "").strip(),
                    "source_url": (r.get("source_url") or r.get("source") or "").strip(),
                    "published": (r.get("published") or "").strip(),
                    "quote": (r.get("quote") or "").strip(),
                    "file": p.name,
                }
            )
    df = pd.DataFrame(rows, columns=[*COLS, "file"])
    if df.empty:
        return df[COLS]
    df = df.sort_values(["date", "dam", "source_url"]).drop_duplicates(
        ["date", "dam", "source_url"], keep="first"
    )
    return df[COLS].reset_index(drop=True)


def main() -> None:
    paths = sorted(RAW.glob("readings_*.csv")) + [REF / "inflow_points.csv"]
    paths = [p for p in paths if p.exists()]
    df = ingest(paths)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False)
    by_year = df.groupby([df["date"].str[:4], "dam"]).size()
    print(f"wrote {OUT}: {len(df)} rows from {len(paths)} files")
    print(by_year.to_string())
    print(
        "with inflow:",
        int(df["inflow_cusecs"].notna().sum()),
        "with level:",
        int(df["level_ft"].notna().sum()),
    )


if __name__ == "__main__":
    main()
