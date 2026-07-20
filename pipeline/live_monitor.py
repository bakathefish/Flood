# pipeline/live_monitor.py
"""6-hourly monitor: new S1 pass over Punjab -> flood stats -> monitor/latest.json.
Auth: EE service account via GOOGLE_APPLICATION_CREDENTIALS or EE_SA_KEY env
(JSON key contents; written to a temp file in CI)."""

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import ee

from sailaab.alerts import render_alert
from sailaab.ee_graphs import (
    punjab_districts,
    flood_mask_for_window,
    district_flood_stats,
)
from sailaab.monitor import load_state, new_scenes, save_state

STATE = Path("monitor/state.json")
LATEST = Path("monitor/latest.json")
LOOKBACK_DAYS = 12  # one S1 revisit
ALERT_KM2 = 25.0  # district alert floor


def _init_ee():
    key = os.environ.get("EE_SA_KEY")
    if key:
        kf = Path("ee-key.json")
        kf.write_text(key)
        creds = ee.ServiceAccountCredentials(None, str(kf))
        ee.Initialize(creds)
    else:
        ee.Initialize()


def main():
    _init_ee()
    districts = punjab_districts()
    aoi = districts.union(1).geometry()
    now = datetime.now(timezone.utc)
    start = (now - timedelta(days=LOOKBACK_DAYS)).strftime("%Y-%m-%d")

    col = (
        ee.ImageCollection("COPERNICUS/S1_GRD")
        .filterBounds(aoi)
        .filter(ee.Filter.eq("instrumentMode", "IW"))
        .filterDate(start, now.strftime("%Y-%m-%d"))
    )
    dates = col.aggregate_array("system:time_start").getInfo() or []
    iso = [
        datetime.fromtimestamp(t / 1000, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
        for t in sorted(dates)
    ]

    fresh = new_scenes(iso, load_state(STATE))
    if not fresh:
        print("no new scenes")
        return

    window = (fresh[0][:10], now.strftime("%Y-%m-%d"))
    year = now.year
    pre = (f"{year}-04-01", f"{year}-05-31")
    flood = flood_mask_for_window(aoi, window, pre)
    stats = district_flood_stats(flood, districts, year, window[0]).getInfo()[
        "features"
    ]

    rows = []
    for f in stats:
        p = f["properties"]
        km2 = float(p.get("flooded_ha") or 0) / 100.0
        rows.append({"district": p["ADM2_NAME"], "flooded_km2": round(km2, 1)})
    rows.sort(key=lambda r: -r["flooded_km2"])
    flagged = [r for r in rows if r["flooded_km2"] >= ALERT_KM2]
    alerts = {
        lang: [
            render_alert(r["district"], r["flooded_km2"], "stable", lang)
            for r in flagged
        ]
        for lang in ("pa", "hi", "en")
    }

    LATEST.parent.mkdir(exist_ok=True)
    LATEST.write_text(
        json.dumps(
            {
                "generated_utc": now.strftime("%Y-%m-%dT%H:%M:%S"),
                "latest_pass": fresh[-1],
                "window": window,
                "districts": rows,
                "flagged": flagged,
                "alerts": alerts,
            },
            ensure_ascii=False,
            indent=1,
        )
    )
    save_state(STATE, fresh[-1])
    print(f"updated: {len(fresh)} new scene(s), {len(flagged)} flagged")


if __name__ == "__main__":
    main()
