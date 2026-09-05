"""Digitise the WRD Flood Preparedness Guidebook 2026 tables into reference CSVs.

Input: the text layer extracted from the guidebook PDF (``data/raw/wrd/wrd_guidebook_2026.txt``)
and the PDF itself for page renders. The PDF carries personal phone numbers of officials and
is therefore never committed; only the tables below are.

Outputs (``data/reference/wrd/``):
    thresholds.csv                   section 3.2, flood-intensity limits per control station
    peaks_harike_hussainiwala.csv    section 3.3 (I), annual maxima 1988-2025 with WRD class
    peaks_ropar.csv                  section 3.3 (II)
    peaks_dhilwan.csv                section 3.3 (III), dated annual maxima
    travel_times.csv                 Annexure Z
    pages/*.png                      renders of the source pages for visual verification

Run: python scripts/digitise_guidebook.py
"""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

import pypdfium2 as pdfium

ROOT = Path(__file__).resolve().parents[1]
TXT = ROOT / "data/raw/wrd/wrd_guidebook_2026.txt"
PDF = ROOT / "data/raw/wrd/wrd_guidebook_2026.pdf"
OUT = ROOT / "data/reference/wrd"
PAGES = OUT.parent.parent / "raw/wrd/pages"


def _section(text: str, start_marker: str, end_marker: str) -> str:
    i = text.index(start_marker)
    j = text.index(end_marker, i)
    return text[i:j]


def _int(s: str) -> int:
    return int(s.replace(",", ""))


def parse_thresholds(text: str) -> list[dict]:
    sec = _section(text, "3.2 CLASSIFICATION OF FLOOD DISCHARGE", "3.3 HISTORICAL DATA")
    lines = [ln.strip() for ln in sec.splitlines() if ln.strip()]
    rivers = {"SUTLEJ", "BEAS", "RAVI", "GHAGGAR"}
    rows, river, station, bands = [], None, None, {}
    station_river = None  # the river current when the station line was read
    band_re = re.compile(
        r"^(?:(?P<station>.+?)\s+)?(?P<cls>Low|Med|High)\s+(?P<a>[\d,]+)(?:-(?P<b>[\d,]+))?(?:\s+and above)?$"
    )
    for ln in lines:
        if ln in rivers:
            river = ln.capitalize()
            continue
        m = band_re.match(ln)
        if not m:
            continue
        if m.group("station"):
            if station and bands:
                rows.append(_threshold_row(station_river, station, bands))
            station, bands = m.group("station").strip(), {}
            # the RAVI row prints the river name and the station on one line
            first, _, rest = station.partition(" ")
            if first in rivers and rest:
                river, station = first.capitalize(), rest.strip()
            station_river = river
        cls = m.group("cls")
        a = _int(m.group("a"))
        b = _int(m.group("b")) if m.group("b") else None
        bands[cls] = (a, b)
    if station and bands:
        rows.append(_threshold_row(station_river, station, bands))
    return rows


def _threshold_row(river, station, bands):
    low, med, high = bands.get("Low"), bands.get("Med"), bands.get("High")
    return {
        "river": river,
        "station": station,
        "low_min": low[0] if low else "",
        "low_max": low[1] if low else "",
        "med_min": med[0] if med else "",
        "med_max": med[1] if med else "",
        "high_min": high[0] if high else "",
        "source_page": 11,
    }


def parse_harike(text: str) -> list[dict]:
    sec = _section(text, "I) MAXIMUM DISCHARGE AT HARIKE", "II) MAXIMUM DISCHARGE AT ROPAR")
    row_re = re.compile(r"^(\d{1,2})\s+(\d{4})\s+(\d+)\s+(\d+)\s+(\d+|-)\s+(\d+|-)\s+(H|M|L|-)\s*$")
    rows = []
    for ln in sec.splitlines():
        m = row_re.match(ln.strip())
        if not m:
            continue
        sr, yr, hu, hd, wu, wd, cls = m.groups()
        rows.append(
            {
                "sr_no": int(sr),
                "year": int(yr),
                "harike_us_cusecs": int(hu),
                "harike_ds_cusecs": int(hd),
                "hussainiwala_us_cusecs": "" if wu == "-" else int(wu),
                "hussainiwala_ds_cusecs": "" if wd == "-" else int(wd),
                "wrd_class": "" if cls == "-" else cls,
                "source_page": 12,
            }
        )
    return rows


def parse_ropar(text: str) -> list[dict]:
    sec = _section(text, "II) MAXIMUM DISCHARGE AT ROPAR", "III) MAXIMUM DISCHARGE OF LAST")
    row_re = re.compile(r"^(\d{1,2})\s+(\d{4})\s+(\d+)\s+(\d+)\s*$")
    rows = []
    for ln in sec.splitlines():
        m = row_re.match(ln.strip())
        if m:
            sr, yr, us, ds = m.groups()
            rows.append(
                {
                    "sr_no": int(sr),
                    "year": int(yr),
                    "us_cusecs": int(us),
                    "ds_cusecs": int(ds),
                    "source_page": 13,
                }
            )
    return rows


def parse_dhilwan(text: str) -> list[dict]:
    sec = _section(text, "III) MAXIMUM DISCHARGE OF LAST", "IV) MONTHLY RAINFALL")
    row_re = re.compile(r"^(\d{4})\s+(\d{2})-(\d{2})-(\d{4})\s+([\d.]+)\s+(\d+)\s*$")
    rows = []
    for ln in sec.splitlines():
        m = row_re.match(ln.strip())
        if m:
            yr, dd, mm, yyyy, gauge, q = m.groups()
            rows.append(
                {
                    "year": int(yr),
                    "date": f"{yyyy}-{mm}-{dd}",
                    "gauge_ft": float(gauge),
                    "discharge_cusecs": int(q),
                    "source_page": 14,
                }
            )
    return rows


def parse_travel_times(text: str) -> list[dict]:
    sec = _section(text, "TRAVELLING TIME OF WATER RELATED TO VARIOUS RIVERS", "D) Ravi")
    rows = []
    river = None
    for ln in sec.splitlines():
        s = ln.strip()
        if s.startswith("A) Sutlej"):
            river = "Sutlej"
        elif s.startswith("B) Ghaggar"):
            river = "Ghaggar"
        elif s.startswith("C) Beas"):
            river = "Beas"
        m = re.match(r"^(\d)\.?\s+(?:From\s+)?(.+?)\s+([\d.]+)\s+([\d.]+)\s*$", s)
        if m and river:
            n, desc, km, hrs = m.groups()
            if desc.startswith("Total distance"):
                continue
            rows.append(
                {
                    "river": river,
                    "sr_no": int(n),
                    "reach": desc.strip(),
                    "km": float(km),
                    "hours": float(hrs),
                    "source_page": 118,
                }
            )
    return rows


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def render_pages(markers: dict[str, str], scale: float = 1.6) -> dict[str, int]:
    """Render the PDF page that contains each marker string; return marker -> 1-based page."""
    PAGES.mkdir(parents=True, exist_ok=True)
    doc = pdfium.PdfDocument(str(PDF))
    found = {}
    for k in range(len(doc)):
        page = doc[k]
        tp = page.get_textpage()
        t = tp.get_text_range()
        tp.close()
        for name, marker in markers.items():
            if name not in found and marker in t:
                found[name] = k + 1
                img = page.render(scale=scale).to_pil()
                img.save(PAGES / f"{name}_p{k + 1}.png")
        page.close()
    doc.close()
    return found


def main() -> None:
    text = TXT.read_text(encoding="utf-8")
    tables = {
        "thresholds.csv": parse_thresholds(text),
        "peaks_harike_hussainiwala.csv": parse_harike(text),
        "peaks_ropar.csv": parse_ropar(text),
        "peaks_dhilwan.csv": parse_dhilwan(text),
        "travel_times.csv": parse_travel_times(text),
    }
    for name, rows in tables.items():
        write_csv(OUT / name, rows)
        print(f"{name}: {len(rows)} rows")
    pages = render_pages(
        {
            "thresholds": "3.2 CLASSIFICATION OF FLOOD DISCHARGE",
            "peaks_harike": "I) MAXIMUM DISCHARGE AT HARIKE",
            "peaks_ropar": "II) MAXIMUM DISCHARGE AT ROPAR",
            "peaks_dhilwan": "III) MAXIMUM DISCHARGE OF LAST",
            "travel_times": "TRAVELLING TIME OF WATER",
        }
    )
    print("rendered pages:", pages)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
