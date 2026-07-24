# pipeline/make_timelapse.py
"""Animated cumulative-flood timelapse for the Aug-Sep 2025 Punjab flood.

One frame per available Copernicus/GFM day in the Aug 15 -> Sep 15 2025 window.
Each frame reveals the *cumulative* flood-to-date extent (running union of every
day up to that date) rather than a single day, so the corridors grow and never
flicker away. The pixels that turned to water *on that day* are flashed brighter,
giving a visible wavefront. Permanent water and district outlines sit underneath,
in the atlas dark-cartography palette. The clip ends on three hold frames showing
the final extent with the union area (km^2 beyond permanent water) annotated.

Everything is deterministic: fixed layout, integer-safe raster decimation with
``Resampling.max`` (thin corridors survive downsampling because max-pool commutes
with the cumulative OR), and PIL text. No randomness, no timestamps baked in.

Outputs (relative to --atlas-dir, default ``atlas``)::

    atlas/web/timelapse_2025.gif    adaptive-palette GIF, target < 7 MB
    atlas/web/timelapse_2025.mp4    H.264 via ffmpeg on PATH (skipped if absent)
    atlas/timelapse_final_still.png the final hold frame

Run from the repo root::

    python pipeline/make_timelapse.py

Inputs default to ``data/gfm/2025/``, ``data/gfm/gfm_punjab_refwater.tif`` and
``data/punjab_districts.geojson``; override any of them with the CLI flags below.
The GFM tifs are git-ignored, so re-render on a tree that has them on disk.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import date

import matplotlib
import numpy as np
import rasterio
from PIL import Image, ImageDraw, ImageFont
from pyproj import Transformer

# Make ``sailaab`` importable when this file is run as a script.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
from sailaab.gfm import web_mercator_area_km2  # noqa: E402

# --- atlas dark-cartography palette (R, G, B) --------------------------------
INK = (10, 16, 20)  # #0a1014  background / no-data
BOUNDARY = (40, 57, 74)  # #28394a  district hairline
STEEL = (26, 95, 143)  # #1a5f8f  permanent water
CYAN = (79, 216, 201)  # #4fd8c9  flood-to-date (cumulative)
BRIGHT = (143, 240, 229)  # #8ff0e5  flooded on this day (fresh wavefront)
TEXT = (214, 228, 236)  # soft white for headline text
MUTED = (112, 134, 150)  # secondary labels
CREDIT = (92, 114, 130)  # bottom-left credit

# --- canvas geometry ---------------------------------------------------------
CANVAS_W, CANVAS_H = 1280, 1120
MARGIN_Y = 20  # top/bottom breathing room around the portrait map
RIGHT_X = CANVAS_W - 26  # right-aligned text column edge
LEFT_X = 26  # left-aligned text column edge

WINDOW_START = date(2025, 8, 15)
WINDOW_END = date(2025, 9, 15)

_DAY_RE = re.compile(r"gfm_punjab_(\d{4})(\d{2})(\d{2})\.tif$")
_FONT_DIR = os.path.join(
    os.path.dirname(matplotlib.__file__), "mpl-data", "fonts", "ttf"
)


def _font(size, bold=False):
    name = "DejaVuSansMono-Bold.ttf" if bold else "DejaVuSansMono.ttf"
    return ImageFont.truetype(os.path.join(_FONT_DIR, name), size)


# ---------------------------------------------------------------------------
# Pure helpers (day discovery, cumulative math, formatting, projection)
# ---------------------------------------------------------------------------
def discover_days(gfm_dir, start=WINDOW_START, end=WINDOW_END):
    """Sorted ``[(date, path), ...]`` for gfm_punjab_YYYYMMDD.tif in ``[start, end]``."""
    out = []
    for path in glob.glob(os.path.join(gfm_dir, "gfm_punjab_*.tif")):
        m = _DAY_RE.search(os.path.basename(path))
        if not m:
            continue
        d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        if start <= d <= end:
            out.append((d, path))
    out.sort(key=lambda t: t[0])
    return out


def cumulative_and_fresh(day_masks):
    """Yield ``(cum, fresh)`` boolean arrays for each day.

    ``cum`` is the running union of every day up to and including this one;
    ``fresh`` is the pixels that first became water on this day
    (``cum_i & ~cum_{i-1}``). Max-pooled decimation commutes with this OR, so
    running it on the small arrays matches running it at full resolution.
    """
    cum = None
    for m in day_masks:
        m = np.asarray(m, dtype=bool)
        if cum is None:
            fresh = m.copy()
            cum = m.copy()
        else:
            fresh = m & ~cum
            cum = cum | m
        yield cum.copy(), fresh


def fmt_km2(value):
    """``2951.2 -> '2,951 km2'`` (thousands-separated, no decimals)."""
    return f"{round(value):,} km²"


def read_mask(path, out_hw):
    """Read band 1 of ``path`` and downsample to ``out_hw`` (rows, cols) as bool.

    Downsampling is an area-box reduce (PIL ``BOX``) followed by a ``> 0``
    threshold, i.e. an *any-set* / max-pool: an output cell is True whenever any
    covered source pixel is True, so single-pixel river corridors survive the
    ~3.7x decimation (nearest-neighbour would drop them).
    """
    h, w = out_hw
    with rasterio.open(path) as ds:
        full = ds.read(1) > 0
    img = Image.fromarray((full.astype(np.uint8)) * 255)
    small = img.resize((w, h), resample=Image.BOX)
    return np.asarray(small) > 0


def _rings_4326(geojson_path):
    """All exterior+interior rings as lists of (lon, lat) from a GeoJSON file."""
    with open(geojson_path, "r", encoding="utf-8") as fh:
        gj = json.load(fh)
    rings = []
    for feat in gj["features"]:
        geom = feat["geometry"]
        polys = (
            geom["coordinates"]
            if geom["type"] == "MultiPolygon"
            else [geom["coordinates"]]
        )
        for poly in polys:
            for ring in poly:
                rings.append(ring)
    return rings


def district_polylines_px(geojson_path, bounds, map_wh, origin):
    """District rings as pixel-space point lists for the placed map.

    ``bounds`` are the raster's EPSG:3857 (minx, miny, maxx, maxy); ``map_wh`` is
    the on-canvas map size in px; ``origin`` is the map's top-left canvas pixel.
    """
    minx, miny, maxx, maxy = bounds
    map_w, map_h = map_wh
    x0, y0 = origin
    sx = map_w / (maxx - minx)
    sy = map_h / (maxy - miny)
    to_merc = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
    polylines = []
    for ring in _rings_4326(geojson_path):
        lons = [c[0] for c in ring]
        lats = [c[1] for c in ring]
        xs, ys = to_merc.transform(lons, lats)
        pts = [(x0 + (x - minx) * sx, y0 + (maxy - y) * sy) for x, y in zip(xs, ys)]
        polylines.append(pts)
    return polylines


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------
def composite_map(cum, fresh, refwater):
    """RGB uint8 array: ink, then permanent water, flood-to-date, fresh-today."""
    h, w = cum.shape
    rgb = np.empty((h, w, 3), dtype=np.uint8)
    rgb[:] = INK
    rgb[refwater] = STEEL
    rgb[cum & ~refwater] = CYAN
    rgb[fresh & ~refwater] = BRIGHT
    return rgb


def _text(draw, xy, s, font, fill, anchor="la", stroke=2):
    draw.text(
        xy,
        s,
        font=font,
        fill=fill,
        anchor=anchor,
        stroke_width=stroke,
        stroke_fill=INK,
    )


def _legend(draw, fonts, rows=None):
    """Swatch + label legend, lower-left. ``rows`` overrides the default
    (cumulative-mode) labels; the current-season daily clip passes its own."""
    if rows is None:
        rows = [
            (STEEL, "permanent water"),
            (CYAN, "flood to date"),
            (BRIGHT, "new this day"),
        ]
    f = fonts["legend"]
    y = CANVAS_H - 168
    for color, label in rows:
        draw.rectangle([LEFT_X, y, LEFT_X + 22, y + 22], fill=color)
        draw.rectangle([LEFT_X, y, LEFT_X + 22, y + 22], outline=BOUNDARY, width=1)
        _text(draw, (LEFT_X + 34, y + 11), label, f, TEXT, anchor="lm", stroke=2)
        y += 34


def _progress_bar(draw, progress):
    y = CANVAS_H - 6
    draw.rectangle([0, y, CANVAS_W, CANVAS_H], fill=BOUNDARY)
    draw.rectangle([0, y, int(CANVAS_W * progress), CANVAS_H], fill=CYAN)


def _base_frame(rgb_map, origin, polylines):
    """Ink canvas with the composited map pasted and district hairlines drawn."""
    canvas = Image.new("RGB", (CANVAS_W, CANVAS_H), INK)
    canvas.paste(Image.fromarray(rgb_map), origin)
    draw = ImageDraw.Draw(canvas)
    for pts in polylines:
        draw.line(pts, fill=BOUNDARY, width=1, joint="curve")
    return canvas, draw


def render_day(rgb_map, origin, polylines, fonts, d, area_cum, area_new, progress):
    canvas, draw = _base_frame(rgb_map, origin, polylines)
    # top-right: kicker + big ISO date
    _text(draw, (RIGHT_X, 34), "PUNJAB · MONSOON 2025", fonts["kicker"], MUTED, "ra")
    _text(draw, (RIGHT_X, 58), d.isoformat(), fonts["date"], TEXT, "ra")
    # running cumulative area + label + today's delta
    _text(draw, (RIGHT_X, 140), fmt_km2(area_cum), fonts["area"], CYAN, "ra")
    _text(draw, (RIGHT_X, 196), "cumulative flood extent", fonts["small"], MUTED, "ra")
    _text(draw, (RIGHT_X, 218), "beyond permanent water", fonts["small"], MUTED, "ra")
    if area_new >= 0.5:
        _text(
            draw,
            (RIGHT_X, 250),
            f"+{fmt_km2(area_new)} this day",
            fonts["delta"],
            BRIGHT,
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


def render_hold(rgb_map, origin, polylines, fonts, area_cum, n_days):
    canvas, draw = _base_frame(rgb_map, origin, polylines)
    _text(draw, (RIGHT_X, 34), "PUNJAB · MONSOON 2025", fonts["kicker"], MUTED, "ra")
    _text(draw, (RIGHT_X, 58), "CUMULATIVE", fonts["holdtitle"], TEXT, "ra")
    _text(draw, (RIGHT_X, 92), "FLOOD EXTENT", fonts["holdtitle"], TEXT, "ra")
    _text(draw, (RIGHT_X, 150), fmt_km2(area_cum), fonts["hero"], CYAN, "ra")
    _text(draw, (RIGHT_X, 224), "beyond permanent water", fonts["small"], MUTED, "ra")
    _text(
        draw,
        (RIGHT_X, 248),
        f"15 Aug – 15 Sep 2025 · {n_days} days",
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


def _fonts():
    return {
        "kicker": _font(19),
        "date": _font(54, bold=True),
        "area": _font(46, bold=True),
        "hero": _font(62, bold=True),
        "holdtitle": _font(30, bold=True),
        "small": _font(19),
        "delta": _font(21, bold=True),
        "legend": _font(18),
        "credit": _font(18),
    }


# ---------------------------------------------------------------------------
# Encoders
# ---------------------------------------------------------------------------
def save_gif(frames, durations_ms, path, colors=64):
    """Palette-quantised looping GIF. One shared adaptive palette keeps it small."""
    quant = [
        f.quantize(colors=colors, method=Image.MEDIANCUT, dither=Image.NONE)
        for f in frames
    ]
    quant[0].save(
        path,
        save_all=True,
        append_images=quant[1:],
        loop=0,
        duration=durations_ms,
        disposal=1,
        optimize=True,
    )


def save_mp4(frames, durations_ms, path, fps=30):
    """H.264/yuv420p via ffmpeg on PATH. Returns True on success, False if absent.

    Each rendered frame is held for ``round(duration_ms/1000*fps)`` video frames,
    so the mp4 pacing matches the gif without generating crossfade tweens.
    """
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return False
    w, h = frames[0].size
    cmd = [
        ffmpeg,
        "-y",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-s",
        f"{w}x{h}",
        "-r",
        str(fps),
        "-i",
        "pipe:0",
        "-an",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-crf",
        "20",
        "-preset",
        "medium",
        "-movflags",
        "+faststart",
        path,
    ]
    proc = subprocess.Popen(
        cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE
    )
    try:
        for frame, dur in zip(frames, durations_ms):
            reps = max(1, round(dur / 1000.0 * fps))
            raw = frame.tobytes()
            for _ in range(reps):
                proc.stdin.write(raw)
        proc.stdin.close()
        err = proc.stderr.read()
        if proc.wait() != 0:
            sys.stderr.write(err.decode("utf-8", "replace")[-2000:])
            return False
    finally:
        if proc.poll() is None:
            proc.kill()
    return True


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
def build(
    gfm_dir,
    refwater_path,
    districts_path,
    atlas_dir,
    day_ms=650,
    hold_ms=1700,
    hold_frames=3,
    gif_colors=64,
):
    days = discover_days(gfm_dir)
    if not days:
        raise SystemExit(f"no GFM day tifs found in {gfm_dir} within window")

    # Map geometry from the raster grid (portrait AOI centred in a landscape frame).
    with rasterio.open(refwater_path) as ds:
        bounds = tuple(ds.bounds)
        full_h, full_w = ds.height, ds.width
    map_h = CANVAS_H - 2 * MARGIN_Y
    map_w = round(map_h * full_w / full_h)
    origin = ((CANVAS_W - map_w) // 2, MARGIN_Y)

    refwater_small = read_mask(refwater_path, (map_h, map_w))
    day_masks = [read_mask(p, (map_h, map_w)) for _, p in days]

    polylines = district_polylines_px(districts_path, bounds, (map_w, map_h), origin)
    fonts = _fonts()

    # Per-day cumulative area (km^2 beyond permanent water) at FULL resolution,
    # via the repo's cos^2(lat)-corrected estimator, for honest annotations.
    with rasterio.open(refwater_path) as ds:
        refwater_full = ds.read(1) > 0
    cum_full = np.zeros_like(refwater_full)
    prev_area = 0.0
    areas = []  # (cum_area, new_area) per day
    for _, path in days:
        with rasterio.open(path) as ds:
            cum_full |= ds.read(1) > 0
        a = web_mercator_area_km2(cum_full & ~refwater_full, bounds)
        areas.append((a, a - prev_area))
        prev_area = a
    final_area = areas[-1][0]

    frames, durations = [], []
    n = len(days)
    for i, (cum, fresh) in enumerate(cumulative_and_fresh(day_masks)):
        rgb = composite_map(cum, fresh, refwater_small)
        d = days[i][0]
        acum, anew = areas[i]
        frames.append(
            render_day(rgb, origin, polylines, fonts, d, acum, anew, (i + 1) / n)
        )
        durations.append(day_ms)

    # Final extent hold frames (full union, no fresh flash).
    full_union = day_masks[0].copy()
    for m in day_masks[1:]:
        full_union |= m
    rgb_final = composite_map(full_union, np.zeros_like(full_union), refwater_small)
    hold = render_hold(rgb_final, origin, polylines, fonts, final_area, n)
    for _ in range(hold_frames):
        frames.append(hold)
        durations.append(hold_ms)

    web_dir = os.path.join(atlas_dir, "web")
    os.makedirs(web_dir, exist_ok=True)
    gif_path = os.path.join(web_dir, "timelapse_2025.gif")
    mp4_path = os.path.join(web_dir, "timelapse_2025.mp4")
    still_path = os.path.join(atlas_dir, "timelapse_final_still.png")

    save_gif(frames, durations, gif_path, colors=gif_colors)
    hold.save(still_path)
    mp4_ok = save_mp4(frames, durations, mp4_path)

    return {
        "days": [d.isoformat() for d, _ in days],
        "n_day_frames": n,
        "n_total_frames": len(frames),
        "final_area_km2": final_area,
        "per_day_area": [
            (d.isoformat(), round(a, 1), round(nw, 1))
            for (d, _), (a, nw) in zip(days, areas)
        ],
        "gif": gif_path,
        "mp4": mp4_path if mp4_ok else None,
        "still": still_path,
        "map_px": (map_w, map_h),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--gfm-dir", default=os.path.join("data", "gfm", "2025"))
    ap.add_argument(
        "--refwater", default=os.path.join("data", "gfm", "gfm_punjab_refwater.tif")
    )
    ap.add_argument(
        "--districts", default=os.path.join("data", "punjab_districts.geojson")
    )
    ap.add_argument("--atlas-dir", default="atlas")
    ap.add_argument("--day-ms", type=int, default=650)
    ap.add_argument("--hold-ms", type=int, default=1700)
    ap.add_argument("--hold-frames", type=int, default=3)
    ap.add_argument("--gif-colors", type=int, default=64)
    args = ap.parse_args(argv)

    info = build(
        args.gfm_dir,
        args.refwater,
        args.districts,
        args.atlas_dir,
        day_ms=args.day_ms,
        hold_ms=args.hold_ms,
        hold_frames=args.hold_frames,
        gif_colors=args.gif_colors,
    )
    print(f"days: {info['n_day_frames']}  ({info['days'][0]} -> {info['days'][-1]})")
    print(
        f"total frames: {info['n_total_frames']}  map {info['map_px'][0]}x{info['map_px'][1]}"
    )
    print(
        f"final cumulative flood beyond permanent water: {fmt_km2(info['final_area_km2'])}"
    )
    for iso, a, nw in info["per_day_area"]:
        print(f"  {iso}  cum={a:>8.1f}  +{nw:.1f}")
    for key in ("gif", "mp4", "still"):
        p = info[key]
        if p and os.path.exists(p):
            print(f"{key}: {p}  ({os.path.getsize(p) / 1e6:.2f} MB)")
        else:
            print(f"{key}: (not written)")


if __name__ == "__main__":
    main()
