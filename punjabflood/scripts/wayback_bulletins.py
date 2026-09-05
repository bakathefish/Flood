"""Parse the BBMB daily reservoir sheets held by the Internet Archive into bulletin records.

BBMB publishes one sheet a day (``res_data.pdf``: level in feet, inflow and outflow in
cusecs, Bhakra and Pong, as on a date and time) and keeps no archive. The Wayback Machine
captured a handful of them: two in September 2025 and four in the 2026 season before the
hourly capture began. This script reads the saved captures from
``data/raw/bbmb_docs/wayback/res_data_<timestamp>.pdf`` (downloaded from
``web.archive.org/web/<timestamp>id_/<original url>``) and writes one record per sheet, in
the schema of the hourly capture, to ``data/reference/bbmb/bulletins_wayback.jsonl`` so the
reservoir loader can read both files alike. Records already present (same as-on key) are
kept as they are.

Run from the ``punjabflood`` directory:

    python scripts/wayback_bulletins.py
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from pypdf import PdfReader

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from punjabflood.reservoirs import BULLETINS_WAYBACK, parse_sheet_text  # noqa: E402

RAW = Path("data/raw/bbmb_docs/wayback")
ORIGINAL = "https://bbmb.gov.in/writereaddata/Portal/images/pdf/res_data.pdf"


def record(pdf: Path) -> dict:
    ts = pdf.stem.split("_")[-1]
    data = pdf.read_bytes()
    text = "\n".join((page.extract_text() or "") for page in PdfReader(pdf).pages)
    rec = {
        "captured_utc": f"{ts[:8]}T{ts[8:]}Z",
        "source_url": f"https://web.archive.org/web/{ts}/{ORIGINAL}",
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "http_status": 200,
        "is_pdf": True,
        "capture_source": "wayback",
        "raw_text": text,
    }
    rec.update(parse_sheet_text(text))
    return rec


def main(raw: Path = RAW, target: Path = BULLETINS_WAYBACK) -> int:
    have = set()
    if target.exists():
        for line in target.read_text(encoding="utf-8").splitlines():
            if line.strip():
                have.add(json.loads(line).get("as_on_key"))
    new = []
    for pdf in sorted(raw.glob("res_data_*.pdf")):
        rec = record(pdf)
        if rec["as_on_key"] not in have:
            new.append(rec)
            have.add(rec["as_on_key"])
    if new:
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as fh:
            for r in new:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"{len(new)} new record(s) appended to {target}")
    return len(new)


if __name__ == "__main__":
    main()
