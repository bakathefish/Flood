# pipeline/build_reference.py
"""Build the pre-monsoon VV reference composite the live monitor diffs against.

Run ONCE locally; the output ``monitor/reference_vv_150m.tif`` is committed and
the GitHub Action never rebuilds it (no network baseline, no secrets). It is the
dry-season / pre-monsoon statewide VV **median** in dB, quantized to int16
(dB x 100) and DEFLATE-compressed — the ``VV_pre`` term of the Tier-A rule, on
the exact 150 m UTM-43N grid the monitor reads new scenes onto.

Design choices (see docs/notes/monitor-rw.md):
- Window: 2026-04-01..2026-05-31 by default — the *same-year* pre-monsoon dry
  season, the freshest "normal, no standing water" baseline before the 2026
  monsoon (no inter-annual land-use drift). ``--window`` overrides it.
- Scenes: up to ``--per-orbit`` newest RTC scenes from EACH (orbit_state,
  relative_orbit) group, so all relative orbits are represented and the median
  covers the whole state gap-free, while total scene count (hence peak RAM) stays
  bounded. RTC gamma0 is terrain-flattened, so mixing orbits in the *baseline*
  median is sound — the canonical GEE Tier-A (``sailaab.ee_graphs``) likewise
  medians the pre window over all orbits.

Reuses the STAC/COG machinery in ``pipeline.local_tier_a`` by import (no edit)
and the quantized codec in ``sailaab.monitor_pc``.

Example
-------
    python -m pipeline.build_reference --res 150 --per-orbit 6
"""

from __future__ import annotations

import argparse
import time

import numpy as np

from pipeline.local_tier_a import (
    AOIS,
    composite_window,
    group_by_orbit,
    open_client,
    search_window,
    target_grid,
)
from sailaab.monitor_pc import save_reference

BBOX = AOIS["punjab"]
DEFAULT_WINDOW = ("2026-04-01", "2026-05-31")
REF_PATH = "monitor/reference_vv_150m.tif"
DST_CRS = "EPSG:32643"


def select_scenes(items, per_orbit: int):
    """Newest ``per_orbit`` scenes from each orbit group (full-coverage, bounded).

    Every (orbit_state, relative_orbit) present contributes its most-recent
    scenes, so the merged set spans all swaths (gap-free statewide) without
    reading every frame in the window.
    """
    groups = group_by_orbit(items)
    chosen = []
    for key in sorted(groups, key=lambda k: (str(k[0]), str(k[1]))):
        g = sorted(groups[key], key=lambda it: it.properties["datetime"], reverse=True)
        chosen.extend(g[:per_orbit])
    return chosen, groups


def build(window, res: float, per_orbit: int, out_path: str):
    t0 = time.time()
    client = open_client()
    items = search_window(client, BBOX, window)
    sel, groups = select_scenes(items, per_orbit)
    print(f"reference window {window[0]}..{window[1]}: {len(items)} items")
    print("  orbits:", {str(k): len(v) for k, v in groups.items()})
    print(f"  selected {len(sel)} scenes (<= {per_orbit}/orbit) for the median")

    transform, w, h = target_grid(BBOX, res)
    print(f"  grid {w}x{h} @ {res} m ({DST_CRS})")

    vv_db = composite_window(sel, transform, w, h, asset="vv", tag="ref")
    valid = np.isfinite(vv_db)

    save_reference(out_path, vv_db, transform, DST_CRS)

    import os

    size_mb = os.path.getsize(out_path) / 1e6
    print(
        f"  saved {out_path}  {size_mb:.2f} MB  "
        f"valid_frac={valid.mean():.3f}  "
        f"VV median={np.nanmedian(vv_db):.2f} dB"
    )
    print(f"  done in {time.time() - t0:.0f}s")
    return {
        "window": window,
        "res_m": res,
        "scenes": len(sel),
        "grid": [w, h],
        "valid_fraction": round(float(valid.mean()), 4),
        "vv_median_db": round(float(np.nanmedian(vv_db)), 2),
        "size_mb": round(size_mb, 2),
        "path": out_path,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--res", type=float, default=150.0)
    ap.add_argument("--per-orbit", type=int, default=6)
    ap.add_argument(
        "--window", nargs=2, metavar=("START", "END"), default=DEFAULT_WINDOW
    )
    ap.add_argument("--out", default=REF_PATH)
    args = ap.parse_args()
    build(tuple(args.window), args.res, args.per_orbit, args.out)


if __name__ == "__main__":
    main()
