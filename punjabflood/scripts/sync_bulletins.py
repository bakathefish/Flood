"""Bring the committed BBMB bulletin file up to date from the hourly capture.

The Sailaab repo's Windows scheduled task (``sailaab-bbmb-poll``) fetches BBMB's
``res_data.pdf`` every hour and appends one parsed record per new bulletin to a private,
uncommitted file. BBMB keeps no archive, so that capture is the only history of the 2026
season. This script copies every record whose (as_on_date, as_on_time) key the committed
file does not have yet into ``data/reference/bbmb/bulletins_2026.jsonl``, in capture
order, without rewriting what is already there. Records are identical in schema; the
``raw_text`` field is kept so the parse can be re-checked later.

Run from the ``punjabflood`` directory:

    python scripts/sync_bulletins.py [source.jsonl]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

DEFAULT_SOURCE = Path("../private/rebuild/probes/bbmb/parsed.jsonl")
TARGET = Path("data/reference/bbmb/bulletins_2026.jsonl")


def _records(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def _key(rec: dict) -> tuple:
    return (rec.get("as_on_date"), rec.get("as_on_time"))


def sync(source: Path = DEFAULT_SOURCE, target: Path = TARGET) -> int:
    """Append new records from ``source`` to ``target``; returns how many were added."""
    have = {_key(r) for r in _records(target)}
    new = [r for r in _records(source) if _key(r) not in have and r.get("as_on_date")]
    if not new:
        return 0
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as fh:
        for r in new:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    return len(new)


if __name__ == "__main__":
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SOURCE
    n = sync(src)
    print(f"{n} new bulletin record(s) appended to {TARGET} from {src}")
