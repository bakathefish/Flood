# pipeline/make_current_timelapse.py
"""Rolling CURRENT-monsoon flood timelapse for Punjab, refreshed by CI.

The live sibling of ``pipeline/make_timelapse.py`` (the fixed Aug-Sep 2025
product). For every day from 1 June of the current year up to today (India
Standard Time), it asks the keyless Copernicus GFM WMS whether a Sentinel-1 pass
imaged the Punjab bounding box that day (the S1 footprint layer) and, if so,
pulls that day's observed-flood-extent tile and decodes it to a boolean mask
(``sailaab.gfm``). Days with no S1 pass are skipped. Each frame shows THAT
DAY'S observed water (not a growing union: water that drains between passes
disappears from the next frame, and June's transplant-paddy signal does not
haunt September), in the dark-cartography style of the 2025 timelapse: cyan
water this pass day, brighter new-vs-previous-pass wavefront, permanent water
underneath, district hairlines, a per-day km^2 counter with a signed change
line, and a season-peak hold card. The driver writes:

    atlas/web/timelapse_current.gif        adaptive-palette GIF (< 7 MB)
    atlas/web/timelapse_current_still.png  the final (latest) frame
    monitor/current_timelapse.json         manifest (season_start, last_day,
                                           days_with_coverage, latest_km2,
                                           peak_km2, peak_day)

All pure logic (IST season-day enumeration, km^2 from pixel counts, the signed
change and season-peak labels) lives in ``sailaab/nowlapse.py`` and is unit-tested;
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
    STEEL,
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
def _daily_legend_rows():
    return [
        (STEEL, "permanent water"),
        (CYAN, "water this pass day"),
        (BRIGHT, "new vs previous pass"),
    ]


def _render_day(rgb, origin, polylines, fonts, iso, year, area_day, delta, progress):
    """One frame = one pass day: that day's water, its km^2, and the signed
    change against the previous covered pass (``delta`` is ``None`` on the
    first frame, which has nothing to compare against)."""
    canvas, draw = _base_frame(rgb, origin, polylines)
    _text(draw, (RIGHT_X, 34), nowlapse.kicker(year), fonts["kicker"], MUTED, "ra")
    _text(draw, (RIGHT_X, 58), iso, fonts["date"], TEXT, "ra")
    _text(draw, (RIGHT_X, 140), nowlapse.fmt_km2(area_day), fonts["area"], CYAN, "ra")
    _text(draw, (RIGHT_X, 196), "water observed this pass day", fonts["small"], MUTED, "ra")
    _text(draw, (RIGHT_X, 218), "beyond permanent water", fonts["small"], MUTED, "ra")
    if delta is not None:
        rising = delta >= 0.5
        _text(
            draw,
            (RIGHT_X, 250),
            nowlapse.change_label(delta),
            fonts["delta"],
            BRIGHT if rising else MUTED,
            "ra",
        )
    _legend(draw, fonts, rows=_daily_legend_rows())
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


def _render_hold(rgb, origin, polylines, fonts, year, peak_iso, peak_km2,
                 latest_iso, latest_km2, start_iso, n):
    """Season hold card: the PEAK single-pass extent (a real observation, not
    a cumulative union) plus the latest pass reading. ``rgb`` is the latest
    pass's map so the card matches what the monitor currently sees."""
    canvas, draw = _base_frame(rgb, origin, polylines)
    _text(draw, (RIGHT_X, 34), nowlapse.kicker(year), fonts["kicker"], MUTED, "ra")
    _text(draw, (RIGHT_X, 58), "SEASON PEAK", fonts["holdtitle"], TEXT, "ra")
    _text(draw, (RIGHT_X, 92), "SINGLE PASS", fonts["holdtitle"], TEXT, "ra")
    _text(draw, (RIGHT_X, 150), nowlapse.fmt_km2(peak_km2), fonts["hero"], CYAN, "ra")
    _text(draw, (RIGHT_X, 224),
          f"on {nowlapse.pretty_date(peak_iso)} · beyond permanent water",
          fonts["small"], MUTED, "ra")
    _text(
        draw,
        (RIGHT_X, 248),
        f"latest {nowlapse.pretty_date(latest_iso)}: {nowlapse.fmt_km2(latest_km2)}",
        fonts["small"],
        MUTED,
        "ra",
    )
    _text(
        draw,
        (RIGHT_X, 272),
        f"{nowlapse.season_range_label(start_iso, latest_iso)} · {n} days",
        fonts["small"],
        MUTED,
        "ra",
    )
    _legend(draw, fonts, rows=_daily_legend_rows())
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
def _write_manifest(generated, season_start_iso, last_day, n_cov,
                    latest_km2=None, peak_km2=None, peak_iso=None):
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    rnd = lambda v: None if v is None else round(float(v), 1)  # noqa: E731
    payload = {
        "generated_utc": generated,
        "season_start": season_start_iso,
        "last_day": last_day,
        "days_with_coverage": int(n_cov),
        "latest_km2": rnd(latest_km2),
        "peak_km2": rnd(peak_km2),
        "peak_day": peak_iso,
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
        _write_manifest(generated, season_start_iso, None, 0)
        return {
            "generated_utc": generated,
            "season_start": season_start_iso,
            "days_candidate": 0,
            "days_with_coverage": 0,
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
        _write_manifest(generated, season_start_iso, None, 0)
        return {
            "generated_utc": generated,
            "season_start": season_start_iso,
            "days_candidate": len(days),
            "days_with_coverage": 0,
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

    # One frame per covered day: THAT day's water beyond permanent water (no
    # cumulative union; drained water leaves the next frame), with a bright
    # wavefront where water is new against the previous covered pass and a
    # signed km^2 change line. Areas are pixel-fractions of the
    # cos^2-corrected box area.
    frames, durations = [], []
    day_isos, areas = [], []
    prev_mask = None
    prev_area = None
    for i, (iso, mask) in enumerate(covered_days):
        day_beyond = mask & ~refwater
        fresh_vs_prev = (
            day_beyond & ~prev_mask if prev_mask is not None
            else np.zeros_like(day_beyond)
        )
        a_day = nowlapse.mask_km2(day_beyond, bbox_area_km2)
        delta = None if prev_area is None else a_day - prev_area
        day_isos.append(iso)
        areas.append(a_day)
        rgb = composite_map(day_beyond, fresh_vs_prev, refwater)
        frames.append(
            _render_day(
                rgb, origin, polylines, fonts, iso, year, a_day, delta,
                (i + 1) / n_cov,
            )
        )
        durations.append(DAY_MS)
        prev_mask, prev_area = day_beyond, a_day

    latest_area = areas[-1]
    last_day = covered_days[-1][0]
    peak_iso, peak_km2 = nowlapse.peak_day(day_isos, areas)
    rgb_final = composite_map(prev_mask, np.zeros_like(prev_mask), refwater)
    hold = _render_hold(
        rgb_final, origin, polylines, fonts, year,
        peak_iso, peak_km2, last_day, latest_area, days[0], n_cov,
    )
    for _ in range(HOLD_FRAMES):
        frames.append(hold)
        durations.append(HOLD_MS)

    colors, gif_bytes = _save_gif_under_budget(frames, durations)
    STILL_PATH.parent.mkdir(parents=True, exist_ok=True)
    hold.save(STILL_PATH)

    _write_manifest(generated, season_start_iso, last_day, n_cov,
                    latest_area, peak_km2, peak_iso)

    return {
        "generated_utc": generated,
        "season_start": season_start_iso,
        "last_day": last_day,
        "days_candidate": len(days),
        "days_with_coverage": n_cov,
        "days_skipped_wms_error": skipped,
        "latest_km2": round(latest_area, 1),
        "peak_km2": round(peak_km2, 1),
        "peak_day": peak_iso,
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
            f"  peak_km2={info['peak_km2']} ({info['peak_day']})"
            f"  latest_km2={info['latest_km2']}"
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
