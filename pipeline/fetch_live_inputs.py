# pipeline/fetch_live_inputs.py
"""Keyless live inputs for the district flood-risk nowcast.

Three fetchers, all no-login / no-secret, each returning plain dicts the pure
``sailaab.nowcast`` layer turns into the 16-feature vector:

* :func:`fetch_rain` — Open-Meteo ERA5 **archive** + **forecast** APIs
  (``archive-api.open-meteo.com`` / ``api.open-meteo.com``, keyless): a 3x3
  cos(lat)-weighted point grid per box (Punjab plains + Sutlej/Beas/Ravi
  upstream, the same boxes as ``pipeline/fetch_rain.py``), merged archive-first,
  reduced to the current window's rain-so-far and the two antecedent windows.
* :func:`fetch_reservoirs` — the data.gov.in CWC daily-reservoir resource for
  the 3 BBMB dams. The feed went dark for these dams in Jul 2025
  (``docs/notes/reservoirs.md``); when 2026 rows are absent (the expected case)
  the 6 storage/delta features stay ``NaN`` (XGBoost-native).
* :func:`fetch_gfm_observed` — Copernicus GFM observed flood extent from the
  keyless GloFAS WMS (recipe in ``sailaab.gfm`` / ``pipeline.fetch_gfm``): daily
  masks for the current window's days-so-far and the whole antecedent window,
  unioned, permanent water removed, reduced to per-district observed fraction/km²
  and the antecedent fraction. Kept to a single coarse WMS tile per day so a run
  stays well under ~25 requests.

All array logic (colour decode, cos²lat area, per-district reduction) lives in
``sailaab.gfm`` / ``sailaab.nowcast`` and is unit-tested; this module is IO only.
"""

from __future__ import annotations

import io
import time

import numpy as np
import requests
from PIL import Image
from rasterio.transform import from_bounds
from rasterio.warp import transform_geom

from pipeline.fetch_gfm import (
    FLOOD_LAYER,
    REFWATER_LAYER,
    REQUEST_PAUSE_S,
    _get,
    _getmap_params,
    bbox_3857,
)
from sailaab import nowcast
from sailaab.districts import load_districts, rasterize_districts
from sailaab.gfm import flood_mask, ref_water_mask

UA = {"User-Agent": "sailaab-nowcast/1.0 (Punjab flood nowcast; keyless)"}

# --------------------------------------------------------------------------- #
# RAIN — Open-Meteo (archive + forecast), keyless
# --------------------------------------------------------------------------- #
PUNJAB_BOX = {"lon": (73.85, 76.95), "lat": (29.53, 32.60)}  # Punjab plains
UPSTREAM_BOX = {"lon": (75.5, 78.6), "lat": (30.9, 33.3)}  # Sutlej/Beas/Ravi upstream
OM_FORECAST = "https://api.open-meteo.com/v1/forecast"
OM_ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"


def _grid_points(box, n: int = 3):
    """``n`` x ``n`` (lat, lon) point grid spanning the box edges."""
    lons = np.linspace(box["lon"][0], box["lon"][1], n)
    lats = np.linspace(box["lat"][0], box["lat"][1], n)
    return [(float(la), float(lo)) for la in lats for lo in lons]


def _om_locations(url, points, extra, timeout: int = 60):
    """One multi-location Open-Meteo call -> list of ``{date: precip_mm}`` per point."""
    params = {
        "latitude": ",".join(f"{la:.4f}" for la, _ in points),
        "longitude": ",".join(f"{lo:.4f}" for _, lo in points),
        "daily": "precipitation_sum",
        "timezone": "UTC",
        **extra,
    }
    r = requests.get(url, params=params, headers=UA, timeout=timeout)
    r.raise_for_status()
    j = r.json()
    if isinstance(j, dict):  # single location -> wrap
        j = [j]
    out = []
    for loc in j:
        d = loc.get("daily", {}) or {}
        out.append(
            dict(zip(d.get("time", []) or [], d.get("precipitation_sum", []) or []))
        )
    return out


def _area_mean_by_date(loc_series, weights):
    """cos(lat)-weighted area-mean per date across the point series (skip missing)."""
    dates: set[str] = set()
    for s in loc_series:
        dates |= set(s)
    out = {}
    for dt in dates:
        vals, ws = [], []
        for s, w in zip(loc_series, weights):
            v = s.get(dt)
            if v is not None and not (isinstance(v, float) and np.isnan(v)):
                vals.append(float(v))
                ws.append(w)
        out[dt] = float(np.average(vals, weights=ws)) if vals else float("nan")
    return out


def _box_daily_series(box, start_iso, today_iso):
    """Merged daily area-mean rain series for a box, archive-first with the
    forecast API's ``past_days`` filling the recent (unsettled) tail."""
    points = _grid_points(box)
    weights = [np.cos(np.deg2rad(la)) for la, _ in points]
    try:
        arch = _area_mean_by_date(
            _om_locations(
                OM_ARCHIVE, points, {"start_date": start_iso, "end_date": today_iso}
            ),
            weights,
        )
    except Exception:
        arch = {}
    try:
        fc = _area_mean_by_date(
            _om_locations(OM_FORECAST, points, {"past_days": 92, "forecast_days": 1}),
            weights,
        )
    except Exception:
        fc = {}
    merged = {}
    for dt in set(arch) | set(fc):
        a = arch.get(dt)
        merged[dt] = (
            a
            if (a is not None and not (isinstance(a, float) and np.isnan(a)))
            else fc.get(dt)
        )
    return merged


def _sum_window(series, w0, w1, upto=None):
    """Summed mm over the window's days (``upto`` truncates the current window to
    days elapsed). Returns ``(sum, n_days_with_data, n_days)``; sum is NaN if none."""
    days = nowcast.window_days(w0, w1, upto)
    good = [
        float(series.get(d))
        for d in days
        if series.get(d) is not None
        and not (isinstance(series.get(d), float) and np.isnan(series.get(d)))
    ]
    return (float(sum(good)) if good else float("nan")), len(good), len(days)


def fetch_rain(window, today_iso):
    """Rain features for the current + two antecedent windows. Returns
    ``(features, source, meta)`` with the 6 :data:`sailaab.nowcast.RAIN_FEATURES`."""
    prev = window["prev_window"]
    prev2 = window["prev2_window"]
    start = (prev2 or prev or (window["window_start"], None))[0]
    out = {k: float("nan") for k in nowcast.RAIN_FEATURES}
    try:
        pj = _box_daily_series(PUNJAB_BOX, start, today_iso)
        up = _box_daily_series(UPSTREAM_BOX, start, today_iso)
        if not pj and not up:
            return out, "unavailable", {"error": "no Open-Meteo data"}
        cj, cj_n, cj_d = _sum_window(
            pj, window["window_start"], window["window_end"], upto=today_iso
        )
        cu, _, _ = _sum_window(
            up, window["window_start"], window["window_end"], upto=today_iso
        )
        out["punjab_mm"], out["upstream_mm"] = cj, cu
        if prev:
            out["punjab_mm_lag1"] = _sum_window(pj, prev[0], prev[1])[0]
            out["upstream_mm_lag1"] = _sum_window(up, prev[0], prev[1])[0]
        if prev2:
            out["punjab_mm_lag2"] = _sum_window(pj, prev2[0], prev2[1])[0]
            out["upstream_mm_lag2"] = _sum_window(up, prev2[0], prev2[1])[0]
        return (
            out,
            "open-meteo",
            {"current_days_counted": cj_n, "current_days_total": cj_d},
        )
    except Exception as exc:  # pragma: no cover - network guard
        return out, "unavailable", {"error": repr(exc)}


# --------------------------------------------------------------------------- #
# RESERVOIRS — data.gov.in CWC (expected dark for the 3 BBMB dams in 2026)
# --------------------------------------------------------------------------- #
CWC_RESOURCE = "https://api.data.gov.in/resource/1fc2148c-fc41-46f5-a364-bdc03f77053f"
CWC_KEY = (
    "579b464db66ec23bdd000001cdd3946e44ce4aad7209ff7b23ac571b"  # public sample key
)
CWC_DAMS = [
    ("bhakra", "Gobind Sagar-Bhakra Reservoir"),
    ("pong", "Pong Reservoir"),
    ("ranjit_sagar", "Thein\\Ranjit Sagar"),
]


def _cwc_rows(keyword, year, timeout: int = 12):
    params = {
        "api-key": CWC_KEY,
        "format": "json",
        "filters[Reservoir_name]": keyword,
        "filters[Year]": str(year),
        "sort[Date]": "asc",
        "limit": 100,
    }
    r = requests.get(CWC_RESOURCE, params=params, headers=UA, timeout=timeout)
    r.raise_for_status()
    return (r.json() or {}).get("records", []) or []


def _storage_window(records, w0, w1, upto=None):
    """(mean_storage, delta_storage) in BCM over the window from CWC records."""
    days = set(nowcast.window_days(w0, w1, upto))
    pts = []
    for rec in records:
        d = str(rec.get("Date", ""))[:10]
        if d in days:
            v = nowcast._num(rec.get("Storage"))
            if not np.isnan(v):
                pts.append((d, v))
    if not pts:
        return float("nan"), float("nan")
    pts.sort()
    vals = [v for _, v in pts]
    return float(np.mean(vals)), float(vals[-1] - vals[0])


def fetch_reservoirs(window, today_iso, timeout: int = 12):
    """CWC storage/delta for the 3 BBMB dams; NaN + ``unavailable`` when the feed
    carries no 2026 rows (the documented post-Jul-2025 dark state). Returns
    ``(features, source, note)``."""
    feats = {k: float("nan") for k in nowcast.RESERVOIR_FEATURES}
    year, w0, w1 = window["year"], window["window_start"], window["window_end"]
    got_any = False
    note = ""
    for slug, kw in CWC_DAMS:
        try:
            recs = _cwc_rows(kw, year, timeout=timeout)
        except Exception as exc:
            note = repr(exc)
            recs = []
        if recs:
            got_any = True
            mean_s, delta_s = _storage_window(recs, w0, w1, upto=today_iso)
            feats[f"{slug}_storage"] = mean_s
            feats[f"{slug}_delta"] = delta_s
        elif slug == "bhakra":
            # Bhakra empty/unreachable -> the whole BBMB feed is dark; stop probing.
            break
    return feats, ("cwc" if got_any else "unavailable"), note


# --------------------------------------------------------------------------- #
# OBSERVED / ANTECEDENT — Copernicus GFM observed flood extent (keyless WMS)
# --------------------------------------------------------------------------- #
GFM_SIZE = 900  # single ~380 m EPSG:3857 tile over the Punjab bbox (1 request/day)


def _wms_rgba(layer, day, bounds, size, timeout: int = 90):
    png = _get(_getmap_params(layer, day, bounds, size, size))
    return np.array(Image.open(io.BytesIO(png)).convert("RGBA"), dtype="uint8")


def _district_labels(bounds, size):
    transform = from_bounds(bounds[0], bounds[1], bounds[2], bounds[3], size, size)
    ds = load_districts(canonicalize=True)  # sorted (GAUL name, lonlat geom)
    names = [n for n, _ in ds]
    geoms = [transform_geom("EPSG:4326", "EPSG:3857", g) for _, g in ds]
    labels = rasterize_districts(geoms, transform, (size, size))
    return labels, names


def _union_over_days(days, bounds, size, pause):
    """OR of the daily GFM flood masks over ``days``. A day with no S1 pass yields
    an empty mask; a failed request is skipped. Returns ``(union, fetched, active)``."""
    union = np.zeros((size, size), dtype=bool)
    fetched = active = 0
    for d in days:
        try:
            m = flood_mask(_wms_rgba(FLOOD_LAYER, d, bounds, size))
        except Exception:
            continue
        fetched += 1
        if m.any():
            active += 1
        union |= m
        time.sleep(pause)
    return union, fetched, active


def fetch_gfm_observed(
    window, today_iso, size: int = GFM_SIZE, pause: float = REQUEST_PAUSE_S
):
    """Per-district observed flood fraction/km² for the current window-so-far and
    the antecedent fraction for the previous window. Returns
    ``(observed, antecedent, meta)``; ``meta['names']`` is the canonical 20-district
    order to key everything else on."""
    bounds = bbox_3857()
    labels, names = _district_labels(bounds, size)

    cur_days = nowcast.window_days(
        window["window_start"], window["window_end"], upto=today_iso
    )
    prev = window["prev_window"]
    prev_days = nowcast.window_days(prev[0], prev[1]) if prev else []

    try:
        ref_day = cur_days[-1] if cur_days else today_iso
        refwater = ref_water_mask(_wms_rgba(REFWATER_LAYER, ref_day, bounds, size))
        time.sleep(pause)
        ref_ok = True
    except Exception:
        refwater = np.zeros((size, size), dtype=bool)
        ref_ok = False

    cur_union, cur_fetched, cur_active = _union_over_days(cur_days, bounds, size, pause)
    prev_union, prev_fetched, prev_active = _union_over_days(
        prev_days, bounds, size, pause
    )

    cur_stats = nowcast.district_flood_stats(
        cur_union, labels, names, bounds, refwater=refwater
    )
    prev_stats = nowcast.district_flood_stats(
        prev_union, labels, names, bounds, refwater=refwater
    )

    observed = {
        n: {
            "observed_fraction": cur_stats[n]["observed_fraction"],
            "observed_km2": cur_stats[n]["observed_km2"],
        }
        for n in names
    }
    antecedent = {n: prev_stats[n]["observed_fraction"] for n in names}
    meta = {
        "names": names,
        "grid_px": size,
        "current_days": len(cur_days),
        "current_days_active": cur_active,
        "prev_days": len(prev_days),
        "prev_days_active": prev_active,
        "refwater_ok": ref_ok,
        "wms_requests": cur_fetched + prev_fetched + (1 if ref_ok else 0),
    }
    return observed, antecedent, meta
