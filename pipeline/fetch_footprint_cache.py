# pipeline/fetch_footprint_cache.py
"""Cache the Sentinel-1 acquisition footprint for every day in the record.

Why this exists. The daily district table was built on a rule that reads
"the flood service answered and returned no flood pixels" as "observed, and
dry, for all twenty districts". That is wrong in the reassuring direction. A
Sentinel-1 pass images a strip roughly 250 km wide, not a state, and on most
days there is no pass over most of Punjab at all. Sampling the footprint layer
against days the table records as entirely dry, seventeen of eighteen from
2022 onward had no acquisition anywhere over the bounding box.

So those district-days are not dry. Nobody looked at them. They are currently
teaching the model that floods do not happen on days it cannot see, and they
are counted as correct negatives when it agrees.

This script fetches ``gfm_sentinel_1_footprint`` once per day and caches the
per-district covered fraction, so the table can be rebuilt with unobserved
district-days as NaN rather than zero. One row per district per day.

Resumable: every day already in the cache is skipped, so an interrupted run
picks up where it stopped. The service is rate-limited and occasionally throws
502s, so this takes a while and is meant to run unattended.

A caveat that cannot be fixed by running longer: for 2015 to 2021 the layer
returns full coverage for every day probed, wet and dry alike, which is not a
plausible per-day acquisition pattern. The layer is not usable as evidence for
that era, and those years are marked ``era_unreliable`` rather than silently
trusted. From 2022 the footprints are genuinely partial and vary day to day.

Run: python -m pipeline.fetch_footprint_cache [--limit N]
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from pipeline.fetch_gfm import FOOTPRINT_LAYER, bbox_3857
from pipeline.fetch_live_inputs import _district_labels, _wms_rgba

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DAILY = DATA / "gfm_district_daily_2015_2025.csv"
OUT = DATA / "gfm_footprint_daily.csv"

GRID = 512
PAUSE = 0.4
# Before 2022 the layer answers "everything, every day", which is not an
# acquisition pattern. Recorded, not trusted.
RELIABLE_FROM = "2022-01-01"


def _load_done() -> set[str]:
    if not OUT.exists():
        return set()
    try:
        return set(pd.read_csv(OUT, usecols=["date"])["date"].astype(str))
    except Exception:
        return set()


def _alive(lock: Path) -> bool:
    """Is the process named in the lock file still running?"""
    try:
        pid = int(lock.read_text().strip())
    except (OSError, ValueError):
        return False
    if pid == os.getpid():
        return False
    try:
        # signal 0 checks existence without touching the process
        os.kill(pid, 0)
    except (OSError, PermissionError):
        return False
    return True


def _order(days: list[str]) -> list[str]:
    """Reliable era first.

    Before 2022 the layer answers "everything, every day", so those fetches
    cannot change any conclusion. Fetching them first, in date order, spends
    hours of rate limit before reaching the only days that carry information.
    """
    return [d for d in days if d >= RELIABLE_FROM] + [
        d for d in days if d < RELIABLE_FROM
    ]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="stop after N new days")
    args = ap.parse_args()

    # Two copies appending to the same CSV duplicate every fetch and race on
    # the write. That already happened once and cost an hour of rate limit.
    # A crashed run leaves the lock behind, so a lock naming a dead process is
    # taken over rather than requiring someone to remember to delete it.
    lock = OUT.with_suffix(".lock")
    if lock.exists() and not _alive(lock):
        print(f"clearing stale {lock.name}")
        lock.unlink(missing_ok=True)
    try:
        fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        print(f"another run holds {lock.name}")
        return 1
    os.write(fd, str(os.getpid()).encode())
    os.close(fd)
    try:
        return _run(args)
    finally:
        lock.unlink(missing_ok=True)


def _run(args) -> int:

    days = sorted(pd.read_csv(DAILY, usecols=["date"])["date"].astype(str).unique())
    done = _load_done()
    todo = _order([d for d in days if d not in done])
    if args.limit:
        todo = todo[: args.limit]

    print(f"{len(days)} days in the record, {len(done)} cached, {len(todo)} to fetch")
    if not todo:
        print("nothing to do")
        return 0

    bounds = bbox_3857()
    labels, names = _district_labels(bounds, GRID)
    totals = {i: int((labels == i).sum()) for i in range(1, len(names) + 1)}

    new = not OUT.exists()
    with OUT.open("a", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        if new:
            w.writerow(["date", "district", "acq_fraction", "bbox_fraction", "era"])

        ok = fail = 0
        for k, day in enumerate(todo, start=1):
            try:
                arr = _wms_rgba(FOOTPRINT_LAYER, day, bounds, GRID)
            except Exception as exc:
                fail += 1
                print(f"  {day}  FAIL {type(exc).__name__}", flush=True)
                time.sleep(PAUSE * 3)
                continue
            fp = arr[..., 3] > 0
            era = "reliable" if day >= RELIABLE_FROM else "era_unreliable"
            bbox_frac = float(fp.mean())
            for i, name in enumerate(names, start=1):
                tot = totals[i]
                frac = (
                    float((fp & (labels == i)).sum()) / tot if tot else float("nan")
                )
                w.writerow([day, name, round(frac, 5), round(bbox_frac, 5), era])
            ok += 1
            if k % 25 == 0:
                fh.flush()
                print(f"  {k}/{len(todo)}  last {day} bbox={bbox_frac:.3f}", flush=True)
            time.sleep(PAUSE)

    print(f"done: {ok} days cached, {fail} failed -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
