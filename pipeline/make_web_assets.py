# pipeline/make_web_assets.py
"""Build the web-optimized media set for the public site (docs/assets/web/).

The page previously hot-linked full-resolution atlas PNGs straight from
raw.githubusercontent.com: ~8.4 MB of images behind a 5-minute CDN cache, on
a different origin from the GitHub Pages site. This script renders every
static figure to a WebP capped at MAX_W px wide and squeezed under a hard
per-file byte budget (quality steps down, then scale, until it fits), copies
the timelapse mp4 + tiny data CSVs same-origin, writes a simplified district
GeoJSON, and seeds monitor/latest.jpg from the current latest.png (CI's
render_latest_png keeps the JPEG fresh from then on).

Outputs
  docs/assets/web/*.webp                 optimized figures (dims in manifest)
  docs/assets/web/timelapse_2025.mp4     copied as-is
  docs/assets/web/punjab_districts.json  simplified boundaries (<= ~150 KB)
  docs/assets/data/*.csv                 the four static tables the page reads
  docs/assets/web/manifest.json          {name: {w, h, bytes}} for authoring
  monitor/latest.jpg                     one-time seed (CI overwrites 6-hourly)

Idempotent; run after regenerating any atlas figure:
  python pipeline/make_web_assets.py
Budgets are pinned by tests/test_site.py.
"""

from __future__ import annotations

import io
import json
import shutil
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "docs" / "assets" / "web"
DATA_OUT = ROOT / "docs" / "assets" / "data"

MAX_W = 1600
IMG_BUDGET = 250_000  # bytes, keep in sync with tests/test_site.py

# (source, output stem) — every static image docs/index.html shows
FIGURES = [
    ("atlas/forecaster_shap.png", "forecaster_shap"),
    ("atlas/rf_flood_2025.png", "rf_flood_2025"),
    ("atlas/frequency_2015_2025_late_season.png", "frequency_2015_2025_late_season"),
    ("atlas/causal_2025.png", "causal_2025"),
    ("atlas/rf_tierA_gfm_compare_2025.png", "rf_tierA_gfm_compare_2025"),
    ("atlas/headroom_2025.png", "headroom_2025"),
    ("atlas/duration_2025.png", "duration_2025"),
    ("atlas/tehsil_repeat_victims.png", "tehsil_repeat_victims"),
    ("atlas/briefs_preview.png", "briefs_preview"),
    ("atlas/ndem_vs_sailaab.png", "ndem_vs_sailaab"),
    ("atlas/official_vs_sailaab.png", "official_vs_sailaab"),
    ("atlas/cwc_station_gap.png", "cwc_station_gap"),
    ("atlas/punjab_flood_history.png", "punjab_flood_history"),
    ("atlas/rain_trend.png", "rain_trend"),
    ("atlas/timelapse_final_still.png", "timelapse_2025_poster"),
    ("atlas/web/swipe_pre.jpg", "swipe_pre"),
    ("atlas/web/swipe_flood.jpg", "swipe_flood"),
]

CSVS = [
    "data/district_flood_stats_2025.csv",
    "data/flood_frequency_districts_late_season.csv",
    "data/forecaster_2025_hindcast.csv",
    "data/official_relief_2025.csv",
]


def encode_webp_under_budget(im: Image.Image, budget: int = IMG_BUDGET,
                             max_w: int = MAX_W) -> tuple[bytes, tuple[int, int]]:
    """WebP bytes <= budget: cap width, then walk quality down, then scale.

    Figures are dark matplotlib renders with fine text, so quality is tried
    first (80 -> 55) before any second resize; text figures fit at q80
    immediately, and only speckle-noisy SAR images (which mask compression
    artifacts) walk down the ladder. Scale steps of 0.88 are the last resort.
    """
    if im.mode not in ("RGB", "RGBA"):
        im = im.convert("RGB")
    if im.width > max_w:
        im = im.resize((max_w, round(im.height * max_w / im.width)), Image.LANCZOS)
    while True:
        for q in (80, 75, 70, 62, 55):
            buf = io.BytesIO()
            im.save(buf, "WEBP", quality=q, method=6)
            if buf.tell() <= budget:
                return buf.getvalue(), im.size
        im = im.resize((round(im.width * 0.88), round(im.height * 0.88)),
                       Image.LANCZOS)


def simplify_districts(src: Path, dst: Path, tolerance_deg: float = 0.003) -> dict:
    """Shrink the district GeoJSON for the web map: simplify + 4-dp coords."""
    from shapely.geometry import mapping, shape

    gj = json.loads(src.read_text(encoding="utf-8"))

    def rnd(x):
        if isinstance(x, (list, tuple)):
            return [rnd(v) for v in x]
        return round(x, 4)

    feats = []
    for f in gj["features"]:
        geom = shape(f["geometry"]).simplify(tolerance_deg, preserve_topology=True)
        if not geom.is_valid:
            geom = geom.buffer(0)
        g = mapping(geom)
        g["coordinates"] = rnd(g["coordinates"])
        feats.append({
            "type": "Feature",
            "properties": {"district": f["properties"]["district"]},
            "geometry": g,
        })
    out = {"type": "FeatureCollection", "features": feats}
    dst.write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
    return out


def seed_latest_jpg() -> None:
    """One-time monitor/latest.jpg from the committed PNG (CI refreshes it)."""
    png, jpg = ROOT / "monitor/latest.png", ROOT / "monitor/latest.jpg"
    if not png.exists():
        return
    if jpg.exists() and jpg.stat().st_mtime >= png.stat().st_mtime:
        return
    with Image.open(png) as im:
        im.convert("RGB").save(jpg, "JPEG", quality=82, optimize=True,
                               progressive=True)


def main() -> None:
    WEB.mkdir(parents=True, exist_ok=True)
    DATA_OUT.mkdir(parents=True, exist_ok=True)

    manifest: dict[str, dict] = {}
    for rel, stem in FIGURES:
        src = ROOT / rel
        with Image.open(src) as im:
            data, (w, h) = encode_webp_under_budget(im)
        dst = WEB / f"{stem}.webp"
        dst.write_bytes(data)
        manifest[stem] = {"w": w, "h": h, "bytes": len(data)}
        print(f"{dst.relative_to(ROOT)}  {w}x{h}  {len(data):,} B")

    mp4_src, mp4_dst = ROOT / "atlas/web/timelapse_2025.mp4", WEB / "timelapse_2025.mp4"
    # CRF-28 stillimage re-encode: the date-stamped slideshow drops ~35% with
    # no visible loss. Plain copy if ffmpeg is absent (still same-origin).
    if shutil.which("ffmpeg"):
        import subprocess

        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-i", str(mp4_src),
             "-c:v", "libx264", "-preset", "slow", "-crf", "28",
             "-tune", "stillimage", "-pix_fmt", "yuv420p",
             "-movflags", "+faststart", str(mp4_dst)],
            check=True,
        )
    else:
        shutil.copyfile(mp4_src, mp4_dst)
    print(f"{mp4_dst.relative_to(ROOT)}  {mp4_dst.stat().st_size:,} B")

    gj_dst = WEB / "punjab_districts.json"
    simplify_districts(ROOT / "data/punjab_districts.geojson", gj_dst)
    print(f"{gj_dst.relative_to(ROOT)}  {gj_dst.stat().st_size:,} B")

    for rel in CSVS:
        shutil.copyfile(ROOT / rel, DATA_OUT / Path(rel).name)

    seed_latest_jpg()
    jpg = ROOT / "monitor/latest.jpg"
    if jpg.exists():
        print(f"{jpg.relative_to(ROOT)}  {jpg.stat().st_size:,} B")

    (WEB / "manifest.json").write_text(
        json.dumps(manifest, indent=1), encoding="utf-8"
    )
    total = sum(m["bytes"] for m in manifest.values()) + mp4_dst.stat().st_size
    print(f"total static media: {total:,} B")


if __name__ == "__main__":
    main()
