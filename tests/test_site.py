# tests/test_site.py
"""Performance and integrity contract for the public site (docs/index.html).

Written first (red) for the 2026-07-24 performance pass. Before it, the page
shipped ~8.4 MB of full-resolution figures hot-linked from
raw.githubusercontent.com (5-minute CDN cache, no width/height, so the layout
jumped as they arrived), fetched monitor/latest.json and monitor/nowcast.json
three times each behind ?t=Date.now() cache-busters, booted two Leaflet maps
plus a remote WMS at page open, and painted a full-viewport mix-blend-mode
noise overlay on every scroll frame.

The contract these tests pin:
  * every <img>/<video> declares its intrinsic width and height (no CLS),
    and declared dimensions match the real pixels of local files;
  * static figures are served same-origin from docs/assets/web/ as capped
    WebP within a hard byte budget; only live monitor artifacts (rewritten
    by CI every 6 h) may stay on raw.githubusercontent.com;
  * each live JSON feed is fetched exactly once, with no cache-busters;
  * Leaflet and both maps initialize lazily via IntersectionObserver;
  * no full-viewport blend modes or per-image filters;
  * below-fold sections use content-visibility so first paint stays cheap.
"""

from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
INDEX = DOCS / "index.html"
WEB = DOCS / "assets" / "web"

# live artifacts CI rewrites every 6 h: these MUST stay remote (raw serves the
# fresh commit; a docs/ copy would go stale between site deploys)
LIVE_REMOTE_OK = {
    "monitor/latest.jpg",
    "atlas/web/timelapse_current.gif",
}

IMG_BUDGET_BYTES = 250_000          # per static image (WebP, <=1600 px wide)
VIDEO_BUDGET_BYTES = 1_200_000      # the 12 s timelapse mp4
TOTAL_BUDGET_BYTES = 2_600_000      # all local static media the page references
GEOJSON_BUDGET_BYTES = 150_000      # simplified district boundaries


class _Media(HTMLParser):
    """Collect <img>, <video> and <source> tags plus <script>/<link> heads."""

    def __init__(self):
        super().__init__()
        self.imgs: list[dict] = []
        self.videos: list[dict] = []
        self.scripts: list[dict] = []
        self.links: list[dict] = []

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if tag == "img":
            self.imgs.append(d)
        elif tag == "video":
            self.videos.append(d)
        elif tag == "script":
            self.scripts.append(d)
        elif tag == "link":
            self.links.append(d)


@pytest.fixture(scope="module")
def html() -> str:
    return INDEX.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def media(html) -> _Media:
    p = _Media()
    p.feed(html)
    return p


def _local_path(src: str) -> Path | None:
    """Repo path for a same-origin (relative) src, else None."""
    if re.match(r"^https?://", src):
        return None
    return DOCS / src


# --------------------------------------------------------------------------- #
# dimensions: the "messy while loading" fix
# --------------------------------------------------------------------------- #
def test_every_img_declares_dimensions(media):
    for img in media.imgs:
        src = img.get("src", "?")
        assert img.get("width", "").isdigit() and img.get("height", "").isdigit(), (
            f"<img src={src}> missing integer width/height (causes layout shift)"
        )


def test_every_video_declares_dimensions(media):
    for v in media.videos:
        assert v.get("width", "").isdigit() and v.get("height", "").isdigit(), (
            "<video> missing integer width/height (causes layout shift)"
        )


def test_declared_dimensions_match_local_files(media):
    from PIL import Image

    checked = 0
    for img in media.imgs:
        p = _local_path(img["src"])
        if p is None:
            continue
        assert p.exists(), f"referenced local image missing: {img['src']}"
        w, h = Image.open(p).size
        assert (int(img["width"]), int(img["height"])) == (w, h), (
            f"{img['src']}: declared {img['width']}x{img['height']} != file {w}x{h}"
        )
        checked += 1
    assert checked >= 15, "expected the static figure set to be local by now"


def test_imgs_are_lazy_and_async(media):
    for img in media.imgs:
        src = img.get("src", "?")
        assert img.get("loading") == "lazy", f"<img src={src}> not loading=lazy"
        assert img.get("decoding") == "async", f"<img src={src}> not decoding=async"


def test_stretched_imgs_keep_aspect_ratio(html):
    # width:100% via CSS + a height attribute distorts unless height:auto is set
    assert re.search(r"img\s*{[^}]*height\s*:\s*auto", html) or "height:auto" in html, (
        "CSS must set height:auto on sized <img> so width/height attrs only "
        "reserve aspect ratio"
    )


# --------------------------------------------------------------------------- #
# where bytes come from: same-origin optimized set, live-only remotes
# --------------------------------------------------------------------------- #
def _media_srcs(media):
    out = [i["src"] for i in media.imgs]
    for v in media.videos:
        for k in ("src", "poster"):
            if v.get(k):
                out.append(v[k])
    return out


def test_only_live_artifacts_are_remote(media):
    for src in _media_srcs(media):
        if not re.match(r"^https?://", src):
            continue
        tail = re.sub(r"^https://raw\.githubusercontent\.com/[^/]+/[^/]+/[^/]+/", "", src)
        assert tail in LIVE_REMOTE_OK, (
            f"static media must be served same-origin from docs/assets/web/, "
            f"found remote: {src}"
        )


def test_local_static_media_within_budget(media):
    total = 0
    seen = set()
    for src in _media_srcs(media):
        p = _local_path(src)
        if p is None or src in seen:
            continue
        seen.add(src)
        assert p.exists(), f"missing local asset: {src}"
        n = p.stat().st_size
        budget = VIDEO_BUDGET_BYTES if p.suffix == ".mp4" else IMG_BUDGET_BYTES
        assert n <= budget, f"{src} is {n:,} B, over its {budget:,} B budget"
        total += n
    assert total <= TOTAL_BUDGET_BYTES, (
        f"local static media totals {total:,} B > {TOTAL_BUDGET_BYTES:,} B"
    )


def test_swipe_pair_identical_dimensions():
    from PIL import Image

    pre = Image.open(WEB / "swipe_pre.webp").size
    flood = Image.open(WEB / "swipe_flood.webp").size
    assert pre == flood, "before/after swipe images must share dimensions"


def test_now_card_is_compressed_jpg(media):
    srcs = [i["src"] for i in media.imgs]
    assert any(s.endswith("monitor/latest.jpg") for s in srcs), (
        "live card must load the JPEG twin, not the ~700 KB PNG"
    )
    seed = ROOT / "monitor" / "latest.jpg"
    assert seed.exists(), "seed monitor/latest.jpg must be committed"
    assert seed.stat().st_size <= 300_000


def test_district_geojson_is_simplified_local_copy(html):
    p = WEB / "punjab_districts.json"
    assert p.exists(), "simplified district boundaries missing"
    assert p.stat().st_size <= GEOJSON_BUDGET_BYTES
    gj = json.loads(p.read_text(encoding="utf-8"))
    assert len(gj["features"]) == 20
    assert all("district" in f["properties"] for f in gj["features"])
    assert "data/punjab_districts.geojson" not in html, (
        "page must fetch the simplified same-origin copy"
    )


# --------------------------------------------------------------------------- #
# network discipline: one fetch per feed, no busters
# --------------------------------------------------------------------------- #
def test_no_cache_busters(html):
    assert "?t=" not in html, (
        "no ?t=Date.now() cache-busters: raw already caps caching at 5 min"
    )


def test_each_live_feed_fetched_once(html):
    # prose may name the files; the network may hit each exactly once
    for feed in ("monitor/latest.json", "monitor/nowcast.json",
                 "monitor/current_timelapse.json"):
        n = html.count(f"fetch(RAW + '{feed}'")
        assert n == 1, f"{feed} fetched {n}x; share one promise"


def test_explorer_day_navigation_is_clamped(html):
    # walking "day >" past the last processed GFM day makes the WMS return
    # its InvalidDimensionValue error as white tiles (the "broken table")
    assert "clampDay(" in html, "explorer must clamp typed and stepped dates"
    assert re.search(r"dateIn\.max\s*=\s*lastDay", html), (
        "date input max must be the last PROCESSED day, not today"
    )


def test_explorer_strips_gfm_tile_decorations(html):
    # the GFM group layer bakes red/green pass boxes and orange time labels
    # into its tiles and exposes no water-only layer; the server's CORS is
    # open, so the explorer must filter tiles per-pixel: keep blue-dominant
    # water (repainted warm pink), drop every decoration pixel
    assert "createTile" in html, "explorer must render filtered canvas tiles"
    assert "crossOrigin" in html
    assert "getImageData" in html
    # BOTH gfm group layers bundle the decorations (reference water included)
    assert html.count("new CleanWMS(") == 2, (
        "observed AND reference layers must go through the pixel filter"
    )


def test_explorer_passes_toggle_off_by_default(html):
    # the stripped pass swaths remain available behind an opt-in chip
    assert "gfm_sentinel_1_footprint" in html
    m = re.search(r'<button[^>]*id="ex-passes"[^>]*>', html)
    assert m, "passes chip missing"
    assert "active" not in m.group(0), "passes chip must start inactive"


def test_preconnect_to_raw(media):
    hrefs = [l.get("href", "") for l in media.links if l.get("rel") == "preconnect"]
    assert any("raw.githubusercontent.com" in h for h in hrefs)


# --------------------------------------------------------------------------- #
# maps: nothing heavy before the user scrolls near it
# --------------------------------------------------------------------------- #
def test_leaflet_not_loaded_eagerly(media):
    for s in media.scripts:
        assert "leaflet" not in s.get("src", "").lower(), (
            "Leaflet must be injected lazily, not a blocking <script src>"
        )
    for l in media.links:
        assert "leaflet" not in l.get("href", "").lower(), (
            "Leaflet CSS must be injected lazily, not a head <link>"
        )


def test_maps_init_behind_intersection_observer(html):
    assert "IntersectionObserver" in html
    # both map containers must go through the lazy-init helper
    for container in ("'exmap'", "'dmap'"):
        assert re.search(r"lazyInit\(\s*" + container, html), (
            f"map {container} must initialize via lazyInit(...)"
        )


# --------------------------------------------------------------------------- #
# paint cost: no full-viewport blends, no per-image filters, cheap first paint
# --------------------------------------------------------------------------- #
def test_no_expensive_paint_styles(html):
    assert "mix-blend-mode" not in html, (
        "full-viewport blend overlay taxes every scroll frame"
    )
    assert "saturate(" not in html, "per-image CSS filters add paint cost"


def test_below_fold_sections_are_containable(html):
    assert "content-visibility:auto" in html.replace(" ", ""), (
        "below-fold sections should use content-visibility:auto"
    )
