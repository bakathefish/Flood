#!/usr/bin/env python
# pipeline/make_ndem_panel.py
"""Render ``atlas/ndem_vs_sailaab.png`` - the founding-argument side-by-side.

The single image that states the project's premise in one glance:

    LEFT   ISRO's rapid-mapping flood sheet for the 19 Aug 2025 Beas flood in
           Kapurthala / Tarn Taran - a locked, static A0 PDF ("For Official Use").
    RIGHT  the SAILAAB open flood mask over the *same approximate extent*, dark
           cartography (ink ground, cyan inundation, hairline district borders):
           the same flood, but open, interactive and reproducible.

Honesty first. The two halves are aligned **by district shape, not georeferenced**
- the NDEM sheet is a raster PDF with no machine-readable projection, so this is a
visual-comparison panel (the sanctioned fallback in punjab-flood-atlas-PLAN.md
Wave 1.3), NOT a pixel-accurate overlay. The caption says so, and credits the
government source. Left crop = documented map-body box; right window = a fixed
lon/lat box over the Beas-Sutlej doab where our mask is strong.

Left source is a Government-of-India map product, reproduced downscaled for
comparison / criticism with full credit ("Map excerpt: NDEM/NRSC/ISRO,
ndem.nrsc.gov.in"). See docs/notes/ndem-panel.md for method + crop coordinates.

Inputs (all repo-relative; the NDEM PDF and the RF raster are gitignored - see
docs/notes/ndem-panel.md for how to fetch them):
    data/ndem/pbflood50dsc19082025_1100hrs_map.pdf   (page 0)
    data/rasters/rf_flood_2025.tif                   (statewide RF mask)
    data/punjab_districts.geojson

Deterministic: same inputs in -> byte-stable PNG out. No network, no randomness.

Run:  python pipeline/make_ndem_panel.py
Deps: pypdfium2 (pure wheel, no poppler), plus rasterio / pyproj / shapely /
matplotlib / numpy (already in requirements.txt).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pypdfium2 as pdfium  # noqa: E402
import rasterio  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patheffects import withStroke  # noqa: E402
from pyproj import Transformer  # noqa: E402
from rasterio.windows import from_bounds  # noqa: E402
from shapely.geometry import shape  # noqa: E402
from shapely.ops import transform as shp_transform  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DATA = ROOT / "data"
OUT = ROOT / "atlas" / "ndem_vs_sailaab.png"

# --- inputs ----------------------------------------------------------------- #
NDEM_PDF = DATA / "ndem" / "pbflood50dsc19082025_1100hrs_map.pdf"
NDEM_PAGE = 0  # page 0 = "Parts of Kapurthala and Tarn Taran Districts"
NDEM_DPI = 150  # render dpi for the source page

# Map-body crop as fractions of the rendered page (left, top, right, bottom),
# taken just inside the black neat-line detected by a dark-run scan of the page
# (see docs/notes/ndem-panel.md). Trims title, the right-hand legend/text column,
# the scale bar and the locator insets - leaving only the framed map.
NDEM_CROP_FRAC = (0.0456, 0.1141, 0.8213, 0.8504)

RF_TIF = DATA / "rasters" / "rf_flood_2025.tif"
DISTRICTS = DATA / "punjab_districts.geojson"

# SAILAAB (right) window in lon/lat (EPSG:4326): the Beas-Sutlej doab across
# Tarn Taran / Kapurthala / N-Firozpur / W-Jalandhar - the approximate footprint
# of the NDEM sheet and where the RF mask carries strong signal. The box is
# expanded to the NDEM crop's aspect at render time so the two halves match.
RIGHT_WINDOW = (74.40, 30.78, 75.64, 31.50)  # lon0, lat0, lon1, lat1
UTM = "EPSG:32643"  # UTM 43N - native CRS of every SAILAAB raster

# District name labels to echo on the right panel (mirrors the NDEM sheet).
RIGHT_LABELS = ("Tarn Taran", "Kapurthala", "Jalandhar", "Firozpur", "Amritsar")

# --- palette: dark "living map" ground vs the white "locked PDF" ------------- #
BG = "#0b0f14"  # ink ground (whole canvas + right panel)
CYAN = (0.20, 0.86, 1.0)  # flood inundation (echoes the Tier-A quicklook cyan)
HAIR = "#5c6b82"  # hairline district boundaries
TITLE = "#f2f4f7"
MUTED = "#9aa4b2"
FAINT = "#6b7480"
AMBER = "#f5b642"  # "static / locked" accent (left)
CYAN_TXT = "#43daffff"[:7]  # "#43daff" live accent (right)
DIVIDER = "#243040"

_HALO = [withStroke(linewidth=2.2, foreground=BG)]


# --------------------------------------------------------------------------- #
# left: NDEM map-body crop
# --------------------------------------------------------------------------- #
def render_ndem_crop():
    """Render the chosen NDEM page at NDEM_DPI and crop to the map body.

    Returns ``(rgb_array, crop_box_px, page_size_px)`` where ``rgb_array`` is a
    uint8 ``(H, W, 3)`` image of just the framed map.
    """
    doc = pdfium.PdfDocument(str(NDEM_PDF))
    try:
        page = doc[NDEM_PAGE]
        pil = page.render(scale=NDEM_DPI / 72).to_pil().convert("RGB")
    finally:
        doc.close()
    w, h = pil.size
    left, top, right, bottom = NDEM_CROP_FRAC
    box = (round(left * w), round(top * h), round(right * w), round(bottom * h))
    return np.asarray(pil.crop(box)), box, (w, h)


# --------------------------------------------------------------------------- #
# right: SAILAAB dark mask panel
# --------------------------------------------------------------------------- #
def _to_utm_transformer():
    return Transformer.from_crs("EPSG:4326", UTM, always_xy=True)


def _window_utm_bbox(window_lonlat, target_aspect):
    """lon/lat window -> UTM (L, B, R, T) expanded to ``target_aspect`` (w/h)."""
    tf = _to_utm_transformer()
    lon0, lat0, lon1, lat1 = window_lonlat
    xs, ys = [], []
    for lo in (lon0, lon1):
        for la in (lat0, lat1):
            x, y = tf.transform(lo, la)
            xs.append(x)
            ys.append(y)
    left, right, bottom, top = min(xs), max(xs), min(ys), max(ys)
    w, h = right - left, top - bottom
    if w / h < target_aspect:  # too tall -> widen
        nw = target_aspect * h
        cx = (left + right) / 2
        left, right = cx - nw / 2, cx + nw / 2
    else:  # too wide -> heighten
        nh = w / target_aspect
        cy = (bottom + top) / 2
        bottom, top = cy - nh / 2, cy + nh / 2
    return left, bottom, right, top


def _load_districts_utm():
    tf = _to_utm_transformer()
    gj = json.loads(DISTRICTS.read_text(encoding="utf-8"))

    def to_utm(geom):
        return shp_transform(lambda x, y, z=None: tf.transform(x, y), shape(geom))

    return [
        (f["properties"].get("district"), to_utm(f["geometry"])) for f in gj["features"]
    ]


def build_right_panel(ax, target_aspect):
    """Draw the SAILAAB flood mask + district hairlines on ``ax`` (UTM 43N)."""
    left, bottom, right, top = _window_utm_bbox(RIGHT_WINDOW, target_aspect)
    with rasterio.open(RF_TIF) as ds:
        win = from_bounds(left, bottom, right, top, ds.transform)
        arr = ds.read(1, window=win)
        wt = ds.window_transform(win)
    h, w = arr.shape
    extent = [wt.c, wt.c + w * wt.a, wt.f + h * wt.e, wt.f]  # L, R, B, T

    ax.set_facecolor(BG)
    rgba = np.zeros((h, w, 4), dtype=float)
    rgba[arr == 1] = (*CYAN, 1.0)
    ax.imshow(rgba, extent=extent, interpolation="nearest", zorder=3)

    labels = _load_districts_utm()
    label_pts = dict(RIGHT_LABELS and _label_points(labels))
    for name, poly in labels:
        parts = [poly] if poly.geom_type == "Polygon" else list(poly.geoms)
        for g in parts:
            ax.plot(*g.exterior.xy, color=HAIR, lw=0.6, zorder=2)
    for name in RIGHT_LABELS:
        if name in label_pts:
            x, y = label_pts[name]
            if left <= x <= right and bottom <= y <= top:
                ax.text(
                    x,
                    y,
                    name.upper(),
                    color=MUTED,
                    fontsize=6.6,
                    ha="center",
                    va="center",
                    zorder=4,
                    path_effects=_HALO,
                )

    ax.set_xlim(left, right)
    ax.set_ylim(bottom, top)
    ax.set_aspect("auto")
    ax.axis("off")
    flooded_px = int((arr == 1).sum())
    return flooded_px, (left, bottom, right, top)


def _label_points(labels):
    pts = {}
    for name, poly in labels:
        p = poly.representative_point()
        pts[name] = (p.x, p.y)
    return pts


# --------------------------------------------------------------------------- #
# compose
# --------------------------------------------------------------------------- #
def compose(ndem_rgb):
    crop_aspect = ndem_rgb.shape[1] / ndem_rgb.shape[0]  # w / h

    # pixel layout ----------------------------------------------------------- #
    W = 2200
    m = 26  # side margin
    gap = 30  # gap between panels (holds the divider)
    panel_w = (W - 2 * m - gap) / 2
    panel_h = panel_w / crop_aspect
    top_band = 156  # title + subtitle
    label_row = 62  # per-panel labels
    credit_row = 40  # source credit under the panels
    footer = 128  # honest-framing footer
    bot_m = 30
    panel_top = top_band + label_row
    H = int(round(panel_top + panel_h + credit_row + footer + bot_m))

    dpi = 100
    fig = plt.figure(figsize=(W / dpi, H / dpi), dpi=dpi)
    fig.patch.set_facecolor(BG)

    def rect(x, y, w, h):  # px (top-left origin) -> figure fraction
        return [x / W, 1 - (y + h) / H, w / W, h / H]

    lx, rx = m, m + panel_w + gap
    ax_l = fig.add_axes(rect(lx, panel_top, panel_w, panel_h))
    ax_r = fig.add_axes(rect(rx, panel_top, panel_w, panel_h))

    ax_l.imshow(ndem_rgb, aspect="auto", interpolation="lanczos")
    ax_l.axis("off")
    for s in ax_l.spines.values():
        s.set_visible(False)
    flooded_px, _ = build_right_panel(ax_r, crop_aspect)

    # thin frames around each panel ----------------------------------------- #
    for ax, col in ((ax_l, "#c9ccd1"), (ax_r, DIVIDER)):
        ax.patch.set_edgecolor(col)
    for x0, x1 in ((lx, lx + panel_w), (rx, rx + panel_w)):
        fig.add_artist(
            plt.Rectangle(
                (x0 / W, 1 - (panel_top + panel_h) / H),
                panel_w / W,
                panel_h / H,
                transform=fig.transFigure,
                fill=False,
                edgecolor="#2a3543",
                lw=1.0,
                zorder=5,
            )
        )

    # centre divider --------------------------------------------------------- #
    xdiv = (lx + panel_w + rx) / 2 / W
    fig.add_artist(
        Line2D(
            [xdiv, xdiv],
            [1 - (panel_top + panel_h) / H, 1 - panel_top / H],
            color=DIVIDER,
            lw=1.4,
            transform=fig.transFigure,
        )
    )

    def ftext(x_px, y_px, s, **kw):
        fig.text(x_px / W, 1 - y_px / H, s, **kw)

    # title block ------------------------------------------------------------ #
    ftext(
        m,
        40,
        "The same flood, two access models",
        fontsize=25,
        weight="bold",
        color=TITLE,
        ha="left",
        va="center",
    )
    ftext(
        m,
        84,
        "Punjab, August 2025 - the Beas breaks its banks across the Kapurthala "
        "doab. ISRO mapped it; so did we.",
        fontsize=12.5,
        color=MUTED,
        ha="left",
        va="center",
    )
    ftext(
        W - m,
        40,
        "SAILAAB",
        fontsize=15,
        weight="bold",
        color=CYAN_TXT,
        ha="right",
        va="center",
    )
    ftext(
        W - m,
        66,
        "Punjab flood intelligence",
        fontsize=10.5,
        color=FAINT,
        ha="right",
        va="center",
    )

    # per-panel labels ------------------------------------------------------- #
    ly = panel_top - label_row / 2 - 4
    ftext(
        lx,
        ly,
        "ISRO NDEM  ·  19 Aug 2025  ·  static PDF",
        fontsize=13.5,
        weight="bold",
        color=AMBER,
        ha="left",
        va="center",
    )
    ftext(
        lx,
        ly + 22,
        "locked A0 sheet — “For Official Use”",
        fontsize=9.5,
        color=FAINT,
        ha="left",
        va="center",
    )
    ftext(
        rx,
        ly,
        "SAILAAB  ·  same flood  ·  open, interactive, reproducible",
        fontsize=13.5,
        weight="bold",
        color=CYAN_TXT,
        ha="left",
        va="center",
    )
    ftext(
        rx,
        ly + 22,
        "Sentinel-1 SAR → random-forest mask · EPSG:32643 · MIT + open data",
        fontsize=9.5,
        color=FAINT,
        ha="left",
        va="center",
    )

    # source credit (on image, under the left panel) ------------------------- #
    ftext(
        lx,
        panel_top + panel_h + 22,
        "Map excerpt: NDEM / NRSC / ISRO, ndem.nrsc.gov.in — Govt. of India "
        "map product, downscaled for comparison/criticism with credit.",
        fontsize=8.6,
        color=FAINT,
        ha="left",
        va="center",
    )
    ftext(
        rx,
        panel_top + panel_h + 22,
        "SAILAAB RF flood mask (rf_flood_2025.tif) over Punjab district polygons "
        "(datameet, ODbL). Cyan = inundation.",
        fontsize=8.6,
        color=FAINT,
        ha="left",
        va="center",
    )

    # footer strip ----------------------------------------------------------- #
    fy = H - footer - bot_m
    fig.add_artist(
        Line2D(
            [m / W, (W - m) / W],
            [1 - fy / H, 1 - fy / H],
            color=DIVIDER,
            lw=1.0,
            transform=fig.transFigure,
        )
    )
    ftext(
        m,
        fy + 34,
        "Same event, two access models. NDEM sheets validated our extent visually; "
        "full georeferenced comparison on the roadmap.",
        fontsize=13,
        color=TITLE,
        ha="left",
        va="center",
        weight="medium",
    )
    ftext(
        m,
        fy + 70,
        "Approximate extent match — the two halves are aligned by district "
        "shape, not georeferenced (the NDEM sheet is a projection-less raster PDF). "
        "Left: Resourcesat-2A AWiFS, 19-08-2025, Kapurthala & Tarn Taran "
        "(MAP ID 2025/FL/PB/2/19082025).",
        fontsize=9.2,
        color=MUTED,
        ha="left",
        va="center",
    )
    ftext(
        m,
        fy + 96,
        "Right: SAILAAB flood-2025 RF mask, Beas–Sutlej doab window "
        "lon[74.40, 75.64] × lat[30.78, 31.50].",
        fontsize=9.2,
        color=FAINT,
        ha="left",
        va="center",
    )

    return fig, H, flooded_px


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    ndem_rgb, box, page_px = render_ndem_crop()
    fig, H, flooded_px = compose(ndem_rgb)
    fig.savefig(OUT, dpi=100, facecolor=BG)
    plt.close(fig)
    kb = OUT.stat().st_size / 1024
    print(f"wrote {OUT.relative_to(ROOT)}  (2200x{H}, {kb:.0f} KB)")
    print(f"  NDEM page {page_px[0]}x{page_px[1]} px @ {NDEM_DPI} dpi, crop box {box}")
    print(f"  right-panel flooded pixels: {flooded_px}")


if __name__ == "__main__":
    main()
