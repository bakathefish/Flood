# pipeline/fetch_reservoirs.py
"""Fetch daily reservoir level/storage for the three BBMB flood dams
(Bhakra/Gobind Sagar on the Sutlej, Pong on the Beas, Ranjit Sagar/Thein on
the Ravi) from the data.gov.in CWC daily-reservoir resource, monsoon months
(Jun-Sep), 2015-2025.

Usage:
    python pipeline/fetch_reservoirs.py                 # all dams, 2015-2025
    python pipeline/fetch_reservoirs.py --years 2024 2025

Source: OGD India resource "Daily data of reservoir level of Central Water
Commission (CWC)" (index 1fc2148c-...). The public sample key caps pages at
10 records, so we offset-paginate month-by-month with polite spacing and
exponential backoff on HTTP 429. Level/Full_reservoir_level are metres;
Storage/Live_capacity_FRL are BCM (billion m3).

Output: data/reservoirs_2015_2025.csv with columns
    date, dam, level_value, level_unit, storage_value, storage_unit,
    pct_capacity, source_url

NOTE: for these three dams the resource currently ends 2025-07-11 and 2025
values are sparse; the Aug-Sep 2025 flood window is filled from CWC weekly
bulletins (see docs/notes/reservoirs.md and data/reservoirs_2025_flood_supplement.csv).
"""

import argparse
import csv
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

RESOURCE = "1fc2148c-fc41-46f5-a364-bdc03f77053f"
API = f"https://api.data.gov.in/resource/{RESOURCE}"
# data.gov.in's openly published sample key (not a secret); override via env.
API_KEY = os.environ.get(
    "DATA_GOV_IN_KEY", "579b464db66ec23bdd000001cdd3946e44ce4aad7209ff7b23ac571b"
)
RESOURCE_PAGE = (
    "https://www.data.gov.in/resource/"
    "daily-data-reservoir-level-central-water-commission-cwc"
)

# exact Reservoir_name keyword (as stored in the resource) -> canonical label
DAMS = {
    "Gobind Sagar-Bhakra Reservoir": "Bhakra",
    "Pong Reservoir": "Pong",
    "Thein\\Ranjit Sagar": "Ranjit Sagar",
}
MONSOON_MONTHS = ["06", "07", "08", "09"]
PAGE = 10  # public-key hard cap on records per call
FIELDS = [
    "date",
    "dam",
    "level_value",
    "level_unit",
    "storage_value",
    "storage_unit",
    "pct_capacity",
    "source_url",
]


def _get(params, tries=8, base_delay=1.0):
    """GET the API with exponential backoff on 429/transient errors."""
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "sailaab-reservoirs/1.0"})
    delay = 5.0
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=45) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < tries - 1:
                time.sleep(delay)
                delay = min(delay * 2, 60)
                continue
            raise
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            if attempt < tries - 1:
                time.sleep(delay)
                delay = min(delay * 2, 60)
                continue
            raise
    return {}


def _num(v):
    """CWC uses the literal 'NA' for missing values; map to ''."""
    if v is None:
        return ""
    s = str(v).strip()
    if s == "" or s.upper() == "NA":
        return ""
    try:
        return float(s)
    except ValueError:
        return ""


def fetch_dam_month(res_name, year, month):
    """All daily records for one dam / year / month, following pagination."""
    rows, offset = [], 0
    while True:
        d = _get(
            {
                "api-key": API_KEY,
                "format": "json",
                "limit": PAGE,
                "offset": offset,
                "filters[Reservoir_name]": res_name,
                "filters[Year]": year,
                "filters[Month]": month,
                "sort[Date]": "asc",
            }
        )
        recs = d.get("records", [])
        rows.extend(recs)
        total = int(d.get("total", 0) or 0)
        offset += PAGE
        if not recs or offset >= total:
            break
        time.sleep(1.0)
    return rows


def _row_from_record(rec, label):
    lvl = _num(rec.get("Level"))
    sto = _num(rec.get("Storage"))
    cap = _num(rec.get("Live_capacity_FRL"))
    pct = round(sto / cap * 100, 2) if (sto != "" and cap not in ("", 0)) else ""
    return {
        "date": rec.get("Date"),
        "dam": label,
        "level_value": lvl,
        "level_unit": "m",
        "storage_value": sto,
        "storage_unit": "BCM",
        "pct_capacity": pct,
        "source_url": RESOURCE_PAGE,
    }


def _write(out, seen):
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for row in sorted(seen.values(), key=lambda r: (r["dam"], r["date"] or "")):
            w.writerow(row)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--years", type=int, nargs="*", default=list(range(2015, 2026)))
    ap.add_argument("--out", default="data/reservoirs_2015_2025.csv")
    args = ap.parse_args()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    seen = {}
    for res_name, label in DAMS.items():
        for year in args.years:
            for month in MONSOON_MONTHS:
                for rec in fetch_dam_month(res_name, year, month):
                    if not rec.get("Date"):
                        continue
                    seen[(rec["Date"], label)] = _row_from_record(rec, label)
                print(
                    f"{label} {year}-{month}: cumulative {len(seen)} rows", flush=True
                )
                time.sleep(1.0)
            _write(out, seen)  # checkpoint after each dam-year
    _write(out, seen)
    print(f"wrote {len(seen)} rows -> {out}", flush=True)


if __name__ == "__main__":
    main()
