# pipeline/make_current_timelapse.py
"""Rolling CURRENT-monsoon flood timelapse for Punjab, refreshed by CI.

The live sibling of ``pipeline/make_timelapse.py`` (the fixed Aug-Sep 2025
product). For every day from 1 June of the current year up to today (India
Standard Time), it asks the keyless Copernicus GFM WMS whether a Sentinel-1 pass
imaged the Punjab bounding box that day (the S1 footprint layer) and, if so,
pulls that day's observed-flood-extent tile and decodes it to a boolean mask
(``sailaab.gfm``). Days with no S1 pass are skipped. The cumulative union grows
frame by frame in the exact dark-cartography style of the 2025 timelapse (cyan
flood-to-date, brighter fresh-today wavefront, permanent water underneath,
district hairlines, a running km^2 counter), and the driver writes:

    atlas/web/timelapse_current.gif        adaptive-palette GIF (< 7 MB)
    atlas/web/timelapse_current_still.png  the final (latest) frame
    monitor/current_timelapse.json         manifest (season_start, last_day,
                                           days_with_coverage, cumulative_km2)

All pure logic (IST season-day enumeration, cumulative update, km^2 from pixel
counts, dash-free labels) lives in ``sailaab/nowlapse.py`` and is unit-tested;
the WMS fetch reuses ``pipeline/fetch_gfm`` (retries + polite pacing), and the
rendering reuses ``pipeline/make_timelapse`` primitives unchanged. Decoded daily
masks are cached under ``data/gfm/current/`` (git-ignored), so a rerun only
fetches new days plus a short trailing window (recent S1 scenes are still being
processed by GFM, so the last few days are always refreshed).

Run from the repo root::

    python pipeline/make_current_timelapse.py

Deterministic given the same WMS responses. Never fails hard: on a WMS refusal
or an empty season it still writes an honest manifest and whatever frames exist.
"""

from __future__ import annotations

import io
import json
import os
import sys
import time
import traceback
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from pipeline.fetch_gfm import (  # noqa: E402  (retries + pacing + bbox reused)
    FLOOD_LAYER,
    FOOTPRINT_LAYER,
    REFWATER_LAYER,
    REQUEST_PAUSE_S,
    _get,
    _getmap_params,
    bbox_3857,
)

# Rendering primitives + palette from the 2025 product, reused UNCHANGED so the
# current-season clip is visually identical. Only the label strings differ (they
# come from sailaab.nowlapse, which is dash-free).
from pipeline.make_timelapse import (  # noqa: E402
    BRIGHT,
    CANVAS_H,
    CANVAS_W,
    CREDIT,
    CYAN,
    LEFT_X,
    MARGIN_Y,
    MUTED,
    RIGHT_X,
    TEXT,
    _base_frame,
    _fonts,
    _legend,
    _progress_bar,
    _text,
    composite_map,
    district_polylines_px,
    save_gif,
)
from sailaab import nowlapse  # noqa: E402
from sailaab.gfm import flood_mask, ref_water_mask, web_mercator_area_km2  # noqa: E402

ROOT = Path(_REPO_ROOT)
CACHE_DIR = ROOT / "data" / "gfm" / "current"
WEB_DIR = ROOT / "atlas" / "web"
GIF_PATH = WEB_DIR / "timelapse_current.gif"
STILL_PATH = WEB_DIR / "timelapse_current_still.png"
MANIFEST_PATH = ROOT / "monitor" / "current_timelapse.json"
DISTRICTS_GEOJSON = ROOT / "data" / "punjab_districts.geojson"

# Display map width in WMS pixels (single tile). Height is derived from the bbox
# aspect so ground shapes are undistorted; ~935 x 1080 for the Punjab box, the
# same on-canvas geometry as the 2025 timelapse.
MAP_TARGET_H = CANVAS_H - 2 * MARGIN_Y  # 1080
COVERAGE_PROBE_PX = 256  # cheap S1-footprint presence probe per day
REFRESH_TAIL_DAYS = 10  # always re-fetch the last N days (GFM still processing)

DAY_MS = 650
HOLD_MS = 1700
HOLD_FRAMES = 3
GIF_COLOR_LADDER = (64, 48, 32)  # try richest palette first, shrink if > 7 MB
MAX_GIF_BYTES = 7 * 1024 * 1024


# ---------------------------------------------------------------------------
# WMS helpers (single tile; retries + pacing reused from fetch_gfm)
# ---------------------------------------------------------------------------
def _wms_rgba(layer, day, bounds, width, height):
    png = _get(_getmap_params(layer, day, bounds, width, height))
    return np.array(Image.open(io.BytesIO(png)).convert("RGBA"), dtype=np.uint8)


def _footprint_covered(day, bounds, size=COVERAGE_PROBE_PX):
    """True when any Sentinel-1 acquisition footprint intersects the bbox on
    ``day`` (a coarse alpha-presence probe on the footprint layer)."""
    arr = _wms_rgba(FOOTPRINT_LAYER, day, bounds, size, size)
    return bool((arr[..., 3] > 0).any())


# ---------------------------------------------------------------------------
# per-day mask cache under data/gfm/current/ (git-ignored via data/gfm/)
# ---------------------------------------------------------------------------
def _mask_path(iso):
    return CACHE_DIR / f"{iso.replace('-', '')}.npz"


def _nocov_path(iso):
    return CACHE_DIR / f"{iso.replace('-', '')}.nocov"


def _cache_store_mask(iso, mask):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _nocov_path(iso).unlink(missing_ok=True)
    np.savez_compressed(_mask_path(iso), mask=np.asarray(mask, dtype=bool))


def _cache_store_nocov(iso):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _mask_path(iso).unlink(missing_ok=True)
    _nocov_path(iso).write_bytes(b"")


def _cache_load(iso, shape):
    """Return ``True`` mask / ``False`` (confirmed no S1) / ``None`` (uncached).

    A cached mask whose shape no longer matches ``shape`` (map size changed) is
    treated as a miss.
    """
    mp = _mask_path(iso)
    if mp.exists():
        try:
            m = np.load(mp)["mask"]
        except Exception:
            return None
        if m.shape == shape:
            return m.astype(bool)
        return None
    if _nocov_path(iso).exists():
        return False
    return None


def _day_mask(iso, bounds, width, height, force_fetch, pause):
    """Resolve one day to a boolean flood mask, ``False`` (no S1 pass), or
    ``None`` (fetch failed / skip). Uses the cache unless ``force_fetch``.

    Returns ``(result, fetched)`` where ``fetched`` is the number of WMS
    requests actually issued (0 on a cache hit).
    """
    shape = (height, width)
    if not force_fetch:
        cached = _cache_load(iso, shape)
        if cached is not None:
            return cached, 0

    requests_made = 0
    try:
        covered = _footprint_covered(iso, bounds)
        requests_made += 1
        time.sleep(pause)
    except Exception:
        return None, requests_made  # WMS refused this day; skip it (no frame)

    if not covered:
        _cache_store_nocov(iso)
        return False, requests_made

    try:
        mask = flood_mask(_wms_rgba(FLOOD_LAYER, iso, bounds, width, height))
        requests_made += 1
        time.sleep(pause)
    except Exception:
        return None, requests_made  # imaged but flood tile failed; skip frame

    _cache_store_mask(iso, mask)
    return mask, requests_made


def _load_refwater(day, bounds, width, height, pause):
    """Permanent (reference) water mask for the map, cached indefinitely (it is
    static). ``day`` supplies the WMS TIME and MUST be a day with a processed GFM
    product (the reference-water layer returns empty for a TIME with no product,
    e.g. today before the scene is processed) -- pass the last covered day.
    Returns an all-False mask if the WMS refuses; an empty result is never cached
    so a later run can retry."""
    shape = (height, width)
    cache = CACHE_DIR / f"refwater_{width}x{height}.npz"
    if cache.exists():
        try:
            m = np.load(cache)["mask"]
            if m.shape == shape and m.any():  # ignore a poisoned/empty cache
                return m.astype(bool)
        except Exception:
            pass
    try:
        m = ref_water_mask(_wms_rgba(REFWATER_LAYER, day, bounds, width, height))
        time.sleep(pause)
    except Exception:
        return np.zeros(shape, dtype=bool)
    if m.any():
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(cache, mask=m)
    return m


# ---------------------------------------------------------------------------
# frame rendering (dark-cartography style of the 2025 timelapse; dash-free text)
# ---------------------------------------------------------------------------
def _render_day(rgb, origin, polylines, fonts, iso, year, area_cum, area_new, progress):
    canvas, draw = _base_frame(rgb, origin, polylines)
    _text(draw, (RIGHT_X, 34), nowlapse.kicker(year), fonts["kicker"], MUTED, "ra")
    _text(draw, (RIGHT_X, 58), iso, fonts["date"], TEXT, "ra")
    _text(draw, (RIGHT_X, 140), nowlapse.fmt_km2(area_cum), fonts["area"], CYAN, "ra")
    _text(draw, (RIGHT_X, 196), "cumulative flood extent", fonts["small"], MUTED, "ra")
    _text(draw, (RIGHT_X, 218), "beyond permanent water", fonts["small"], MUTED, "ra")
    if area_new >= 0.5:
        _text(
            draw,
            (RIGHT_X, 250),
            nowlapse.delta_label(area_new),
            fonts["delta"],
            BRIGHT,  # fresh-today wavefront colour
            "ra",
        )
    _legend(draw, fonts)
    _text(
        draw,
        (LEFT_X, CANVAS_H - 30),
        "SAILAAB · Sentinel-1 / Copernicus GFM",
        fonts["credit"],
        CREDIT,
        "lm",
    )
    _progress_bar(draw, progress)
    return canvas


def _render_hold(rgb, origin, polylines, fonts, year, area_cum, start_iso, last_iso, n):
    canvas, draw = _base_frame(rgb, origin, polylines)
    _text(draw, (RIGHT_X, 34), nowlapse.kicker(year), fonts["kicker"], MUTED, "ra")
    _text(draw, (RIGHT_X, 58), "CURRENT SEASON", fonts["holdtitle"], TEXT, "ra")
    _text(draw, (RIGHT_X, 92), "SO FAR", fonts["holdtitle"], TEXT, "ra")
    _text(draw, (RIGHT_X, 150), nowlapse.fmt_km2(area_cum), fonts["hero"], CYAN, "ra")
    _text(draw, (RIGHT_X, 224), "beyond permanent water", fonts["small"], MUTED, "ra")
    _text(
        draw,
        (RIGHT_X, 248),
        f"{nowlapse.season_range_label(start_iso, last_iso)} · {n} days",
        fonts["small"],
        MUTED,
        "ra",
    )
    _legend(draw, fonts)
    _text(
        draw,
        (LEFT_X, CANVAS_H - 30),
        "SAILAAB · Sentinel-1 / Copernicus GFM",
        fonts["credit"],
        CREDIT,
        "lm",
    )
    _progress_bar(draw, 1.0)
    return canvas


def _save_gif_under_budget(frames, durations):
    """Save the GIF, dropping to a smaller palette until it fits the 7 MB
    budget. Returns ``(colors_used, size_bytes)``."""
    WEB_DIR.mkdir(parents=True, exist_ok=True)
    last = None
    for colors in GIF_COLOR_LADDER:
        save_gif(frames, durations, GIF_PATH, colors=colors)
        size = GIF_PATH.stat().st_size
        last = (colors, size)
        if size <= MAX_GIF_BYTES:
            return last
    return last  # smallest palette still over budget -> keep it, report honestly


# ---------------------------------------------------------------------------
# manifest
# ---------------------------------------------------------------------------
def _write_manifest(generated, season_start_iso, last_day, n_cov, cum_km2):
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_utc": generated,
        "season_start": season_start_iso,
        "last_day": last_day,
        "days_with_coverage": int(n_cov),
        "cumulative_km2": (None if cum_km2 is None else round(float(cum_km2), 1)),
    }
    MANIFEST_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    return payload


# ---------------------------------------------------------------------------
# orchestration
# ---------------------------------------------------------------------------
def build(today=None, pause=REQUEST_PAUSE_S):
    """Fetch/cache each season day, build frames, write GIF + still + manifest.

    Returns a summary dict. Never raises for per-day WMS failures (those days are
    skipped); a totally empty season still writes an honest manifest.
    """
    generated_dt = datetime.now(timezone.utc)
    generated = generated_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    today_d = nowlapse.today_ist() if today is None else nowlapse._coerce_date(today)
    year = today_d.year
    season_start_iso = nowlapse.season_start(year).isoformat()
    days = nowlapse.season_days(today_d)

    bounds = bbox_3857()
    minx, miny, maxx, maxy = bounds
    map_h = MAP_TARGET_H
    map_w = round(map_h * (maxx - minx) / (maxy - miny))
    origin = ((CANVAS_W - map_w) // 2, MARGIN_Y)
    shape = (map_h, map_w)
    # Physically correct box area (cos^2(lat) corrected); pixel fractions of this.
    bbox_area_km2 = web_mercator_area_km2(np.ones(shape, dtype=bool), bounds)

    if not days:
        _write_manifest(generated, season_start_iso, None, 0, 0.0)
        return {
            "generated_utc": generated,
            "season_start": season_start_iso,
            "days_candidate": 0,
            "days_with_coverage": 0,
            "cumulative_km2": 0.0,
            "gif": None,
            "wms_requests": 0,
            "note": "season not started (before 1 June)",
        }

    tail_start = today_d.toordinal() - (REFRESH_TAIL_DAYS - 1)

    covered_days = []  # (iso, mask) for days with an S1 pass
    total_requests = 0
    skipped = 0
    for iso in days:
        force = date.fromisoformat(iso).toordinal() >= tail_start
        result, made = _day_mask(iso, bounds, map_w, map_h, force, pause)
        total_requests += made
        if result is False:
            continue  # no S1 pass that day -> no frame
        if result is None:
            skipped += 1
            continue  # WMS refused this day -> skip, keep going
        covered_days.append((iso, result))

    n_cov = len(covered_days)
    if n_cov == 0:
        _write_manifest(generated, season_start_iso, None, 0, 0.0)
        return {
            "generated_utc": generated,
            "season_start": season_start_iso,
            "days_candidate": len(days),
            "days_with_coverage": 0,
            "cumulative_km2": 0.0,
            "gif": None,
            "wms_requests": total_requests,
            "skipped_days": skipped,
            "note": "no Sentinel-1 coverage in season so far (or WMS unavailable)",
        }

    # Reference (permanent) water, subtracted so the counter reads "beyond
    # permanent water". Fetched with the last covered day's TIME (guaranteed a
    # processed GFM product; today's date may have none yet).
    refwater = _load_refwater(covered_days[-1][0], bounds, map_w, map_h, pause)

    polylines = district_polylines_px(
        str(DISTRICTS_GEOJSON), bounds, (map_w, map_h), origin
    )
    fonts = _fonts()

    # Cumulative area beyond permanent water, per covered day (pixel-fraction of
    # the cos^2-corrected box area), for the honest on-frame + manifest counter.
    masks = [m for _, m in covered_days]
    frames, durations = [], []
    areas = []
    prev_area = 0.0
    cum_final = None
    for i, (cum, fresh) in enumerate(nowlapse.cumulative_and_fresh(masks)):
        cum_beyond = cum & ~refwater
        fresh_beyond = fresh & ~refwater
        a_cum = nowlapse.mask_km2(cum_beyond, bbox_area_km2)
        a_new = max(0.0, a_cum - prev_area)
        prev_area = a_cum
        areas.append(a_cum)
        rgb = composite_map(cum, fresh, refwater)
        frames.append(
            _render_day(
                rgb,
                origin,
                polylines,
                fonts,
                covered_days[i][0],
                year,
                a_cum,
                a_new,
                (i + 1) / n_cov,
            )
        )
        durations.append(DAY_MS)
        cum_final = cum

    final_area = areas[-1]
    last_day = covered_days[-1][0]
    rgb_final = composite_map(cum_final, np.zeros_like(cum_final), refwater)
    hold = _render_hold(
        rgb_final, origin, polylines, fonts, year, final_area, days[0], last_day, n_cov
    )
    for _ in range(HOLD_FRAMES):
        frames.append(hold)
        durations.append(HOLD_MS)

    colors, gif_bytes = _save_gif_under_budget(frames, durations)
    STILL_PATH.parent.mkdir(parents=True, exist_ok=True)
    hold.save(STILL_PATH)

    _write_manifest(generated, season_start_iso, last_day, n_cov, final_area)

    return {
        "generated_utc": generated,
        "season_start": season_start_iso,
        "last_day": last_day,
        "days_candidate": len(days),
        "days_with_coverage": n_cov,
        "days_skipped_wms_error": skipped,
        "cumulative_km2": round(final_area, 1),
        "map_px": (map_w, map_h),
        "gif": str(GIF_PATH),
        "gif_bytes": gif_bytes,
        "gif_colors": colors,
        "still": str(STILL_PATH),
        "manifest": str(MANIFEST_PATH),
        "wms_requests": total_requests,
    }


def main():
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        info = build()
    except Exception as exc:  # honest manifest even on an unexpected failure
        traceback.print_exc()
        try:
            year = nowlapse.today_ist().year
            _write_manifest(
                generated, nowlapse.season_start(year).isoformat(), None, 0, None
            )
        except Exception:
            traceback.print_exc()
        print(f"CURRENT_TIMELAPSE DEGRADED: {type(exc).__name__}: {exc}")
        return 0

    print("CURRENT_TIMELAPSE_SUMMARY_JSON_START")
    print(json.dumps(info, indent=2, default=str))
    print("CURRENT_TIMELAPSE_SUMMARY_JSON_END")
    if info.get("gif"):
        print(
            f"gif: {info['gif']}  ({info['gif_bytes'] / 1e6:.2f} MB, "
            f"{info['gif_colors']} colors)  days_with_coverage={info['days_with_coverage']}"
            f"  cumulative_km2={info['cumulative_km2']}"
        )
    else:
        print(f"no frames produced: {info.get('note')}")
    print(f"manifest: {MANIFEST_PATH}")
    return 0


if __name__ == "__main__":
    try:
        code = main()
    except Exception:  # pragma: no cover - last-resort guard
        traceback.print_exc()
        code = 0
    raise SystemExit(code)
