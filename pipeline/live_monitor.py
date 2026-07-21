# pipeline/live_monitor.py
"""6-hourly live flood monitor — ZERO secrets, Microsoft Planetary Computer.

Queries the anonymous MPC STAC for Sentinel-1 RTC scenes over Punjab in the last
``LOOKBACK_DAYS`` days, advances the ``monitor/state.json`` watermark
(:mod:`sailaab.monitor`), and for each genuinely new acquisition date builds a
coarse (150 m) VV composite of just that pass, diffs it against the committed
pre-monsoon reference composite (``monitor/reference_vv_150m.tif``), applies the
Tier-A rule (:mod:`sailaab.sar_local`), reduces the mask to per-district flooded
km² (:mod:`sailaab.districts`), and writes ``monitor/latest.json`` +
``monitor/latest.png``. No new scenes -> print and exit 0.

No Earth Engine, no service account, no subscription key: MPC asset signing is
anonymous. The legacy EE path is preserved verbatim in
``pipeline/legacy_ee_monitor.py``. Heavy STAC/COG IO is reused by import from
``pipeline.local_tier_a`` (unchanged); pure grouping/shaping/codec logic is in
``sailaab.monitor_pc`` (unit-tested).

Runtime is kept under the runner budget by: coarse 150 m grid, reading only the
new pass's scenes (a swath, not the whole archive), and processing the latest
date only when a backlog of >``MAX_NEW_SCENES`` scenes arrives at once.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

from pipeline.local_tier_a import (
    _save_overlay_png,
    composite_window,
    open_client,
    search_window,
)
from sailaab.districts import district_fractions, load_districts, rasterize_districts
from sailaab.monitor import load_state, new_scenes, save_state
from sailaab.monitor_pc import (
    build_alerts,
    district_km2_rows,
    group_by_date,
    load_reference,
    plan_passes,
    reproject_geoms,
)
from sailaab.sar_local import sieve_mask, tier_a_mask

PUNJAB_BBOX = (73.85, 29.53, 76.95, 32.60)
COLLECTION = "sentinel-1-rtc"
REF_PATH = Path("monitor/reference_vv_150m.tif")
STATE = Path("monitor/state.json")
LATEST = Path("monitor/latest.json")
LATEST_PNG = Path("monitor/latest.png")

LOOKBACK_DAYS = 12  # one S1 revisit cycle
ALERT_KM2 = 25.0  # district alert floor
MAX_NEW_SCENES = 8  # above this, composite the latest date only (backlog guard)

SOURCE = "Sentinel-1 RTC via Microsoft Planetary Computer (anonymous STAC)"
REFERENCE_DESC = "pre-monsoon VV dry-season median, 150 m (see monitor/reference)"


def _pixel_area_ha(transform) -> float:
    return abs(transform.a) * abs(transform.e) / 1e4


def _district_labels(transform, width, height, crs):
    """Rasterize the 20 Punjab districts onto the SAR UTM grid.

    Polygons ship in lon/lat; they are reprojected to the reference CRS and burnt
    with :func:`sailaab.districts.rasterize_districts` (label i+1 for the i-th
    district, background 0). Returns ``(labels, names)`` with GAUL spellings.
    """
    districts = load_districts(canonicalize=True)  # [(gaul_name, lonlat_geom)]
    names = [n for n, _ in districts]
    epsg = crs.to_epsg()
    utm_pairs = reproject_geoms(districts, "EPSG:4326", f"EPSG:{epsg}")
    labels = rasterize_districts(utm_pairs, transform, (height, width))
    return labels, names


def process_pass(items, ref_db, transform, width, height, labels, names, px_area_ha):
    """Composite one acquisition date's scenes and reduce to per-district km².

    ΔVV = VV_pass - VV_reference on the shared grid; Tier-A mask + speckle sieve;
    then :func:`sailaab.districts.district_fractions`. Returns the VV dB field,
    the mask, sorted district rows, flagged rows, statewide total km², and the
    fraction of Punjab this pass actually imaged.
    """
    vv_flood = composite_window(items, transform, width, height, asset="vv", tag="pass")
    dvv = vv_flood - ref_db
    valid = np.isfinite(dvv)
    mask = sieve_mask(tier_a_mask(dvv, vv_flood, ref_db))

    fractions = district_fractions(labels, mask, px_area_ha, names=names)
    rows, flagged = district_km2_rows(fractions, ALERT_KM2)
    total_km2 = round(sum(r["flooded_km2"] for r in rows), 1)

    state = labels > 0
    coverage = float((valid & state).sum()) / float(state.sum()) if state.any() else 0.0
    return {
        "vv_flood": vv_flood,
        "mask": mask,
        "rows": rows,
        "flagged": flagged,
        "total_km2": total_km2,
        "coverage": round(coverage, 3),
        "scenes": len(items),
    }


def main():
    # Bound each remote COG HTTP request so a stalled socket under MPC's
    # anonymous throttling aborts and is retried (read_asset re-signs + retries)
    # instead of hanging the whole job. Per-request, not per-scene, so
    # slow-but-progressing reads still complete; a genuinely stuck request can't
    # burn the 25-minute runner budget. Overridable from the environment.
    os.environ.setdefault("GDAL_HTTP_TIMEOUT", "120")
    os.environ.setdefault("GDAL_HTTP_MAX_RETRY", "3")
    os.environ.setdefault("GDAL_HTTP_RETRY_DELAY", "3")

    if not REF_PATH.exists():
        raise SystemExit(
            f"missing reference composite {REF_PATH}; build it once with "
            f"`python -m pipeline.build_reference` and commit it."
        )
    ref_db, transform, crs, width, height = load_reference(REF_PATH)
    px_area_ha = _pixel_area_ha(transform)

    now = datetime.now(timezone.utc)
    start = (now - timedelta(days=LOOKBACK_DAYS)).strftime("%Y-%m-%d")
    client = open_client()
    items = search_window(
        client, PUNJAB_BBOX, (start, now.strftime("%Y-%m-%d")), COLLECTION
    )
    iso = sorted(it.properties["datetime"] for it in items)

    fresh = new_scenes(iso, load_state(STATE))
    if not fresh:
        print("no new scenes")
        return

    dates_to_process, backlog = plan_passes(fresh, MAX_NEW_SCENES)
    fresh_by_date = group_by_date(fresh)
    items_by_date: dict[str, list] = {}
    for it in items:
        items_by_date.setdefault(it.properties["datetime"][:10], []).append(it)

    skipped_dates = [d for d in sorted(fresh_by_date) if d not in dates_to_process]
    print(
        f"{len(fresh)} new scene(s) across {len(fresh_by_date)} date(s); "
        f"processing {dates_to_process}"
        + (f" (backlog: skipped {skipped_dates})" if backlog else "")
    )

    labels, names = _district_labels(transform, width, height, crs)

    passes = []
    latest_result = None
    latest_date = dates_to_process[-1]
    for date in dates_to_process:
        res = process_pass(
            items_by_date[date],
            ref_db,
            transform,
            width,
            height,
            labels,
            names,
            px_area_ha,
        )
        passes.append(
            {
                "date": date,
                "scenes": res["scenes"],
                "total_flooded_km2": res["total_km2"],
                "flagged": len(res["flagged"]),
                "coverage_fraction": res["coverage"],
            }
        )
        print(
            f"  {date}: {res['scenes']} scene(s), {res['total_km2']} km² flooded, "
            f"{len(res['flagged'])} district(s) flagged, coverage {res['coverage']:.0%}"
        )
        if date == latest_date:
            latest_result = res

    alerts = build_alerts(latest_result["flagged"], trend="stable")

    LATEST.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": SOURCE,
        "reference": REFERENCE_DESC,
        "lookback_days": LOOKBACK_DAYS,
        "alert_floor_km2": ALERT_KM2,
        "latest_pass": latest_date,
        "latest_pass_utc": fresh[-1],
        "new_scenes": len(fresh),
        "backlog_skipped": backlog,
        "skipped_dates": skipped_dates,
        "coverage_fraction": latest_result["coverage"],
        "total_flooded_km2": latest_result["total_km2"],
        "passes": passes,
        "districts": latest_result["rows"],
        "flagged": latest_result["flagged"],
        "alerts": alerts,
    }
    LATEST.write_text(
        json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8"
    )

    _save_overlay_png(
        latest_result["vv_flood"],
        latest_result["mask"],
        LATEST_PNG,
        f"Punjab flood monitor — pass {latest_date} "
        f"({latest_result['total_km2']:.0f} km², coverage {latest_result['coverage']:.0%})",
    )

    save_state(STATE, fresh[-1])
    print(
        f"updated: latest pass {latest_date}, {latest_result['total_km2']} km² flooded, "
        f"{len(latest_result['flagged'])} district(s) >= {ALERT_KM2} km²"
    )


if __name__ == "__main__":
    main()
