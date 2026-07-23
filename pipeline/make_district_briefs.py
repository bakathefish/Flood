#!/usr/bin/env python
# pipeline/make_district_briefs.py
"""Print-ready A4 flood brief, one PDF per Punjab district (20 total).

The tangible "real users" artifact: the single sheet a District Collector's
office would pin to a wall.  Light paper ground, ink text, cyan (water) and
amber (risk) accents; A4 portrait; one page per district.

Layout
------
* Header   SAILAAB wordmark + "District Flood Brief -- <District>", the district
           name echoed in Gurmukhi, and the project URL (no QR libs -> URL is
           printed).
* Left     mini-map: the district's tehsils shaded by their 2025 RF-derived
           flooded fraction (white -> cyan), the district outline in ink, and
           neighbouring districts greyed for context.
* Right    stat block -- 2025 flooded ha (RF + Tier-A), cropland flooded ha,
           value-at-risk (Rs crore), population exposed (RF & GFM brackets),
           decade seasons >1% / >2%, hindcast peak P + statewide rank, and the
           district's tehsils table (2025 ha, decade seasons flooded) worst-first.
* Footer   one-line method, open-data + validation credit, generation date.

Gurmukhi
--------
matplotlib has no complex-text-layout engine, so Indic pre-base vowel signs
render in logical (not visual) order.  The single systematic breaker for these
20 names is the short-i matra U+0A3F, which must display *before* its consonant.
``_shape_gurmukhi`` reorders it deterministically (over an optional nukta), which
makes all 20 names read correctly; two names carry a halant subjoined conjunct
(U+0A4D) that renders inline rather than stacked -- a documented, cosmetic-only
limitation (see docs/notes/briefs.md).  Rendering uses the Windows "Nirmala UI"
font; if it is unavailable the brief falls back to English-only and prints a note.

Inputs (all committed, repo-relative)
    data/district_flood_stats_2025.csv
    data/district_var_v2.csv           (VaR v2, DES district yields — display value)
    data/flood_frequency_districts_late_season.csv
    data/forecaster_2025_hindcast.csv
    data/tehsil_flood_stats_2025.csv
    data/tehsil_repeat_victims.csv
    data/pop_exposure_2025.csv
    data/punjab_districts.geojson
    data/punjab_tehsils.geojson

The statewide RF flood raster (data/rasters/rf_flood_2025.tif) is gitignored and
stays local, so the mini-map's flood signal is the committed per-tehsil RF
flooded fraction rendered as a vector choropleth -- fully reproducible from the
repo and lighter than a raster inset.

Outputs
    briefs/<District>.pdf          x20   (deterministic; same inputs -> same bytes)
    atlas/briefs_preview.png              3 exemplars side-by-side for the synopsis

Deterministic: no network, no randomness, fixed PDF CreationDate.

Run:  python pipeline/make_district_briefs.py            # all 20 + preview
      python pipeline/make_district_briefs.py Firozpur Kapurthala   # subset
Deps: matplotlib, numpy (already in requirements.txt); Nirmala UI font optional.
"""

from __future__ import annotations

import csv
import json
import math
import sys
from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib import font_manager as fm  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap, PowerNorm  # noqa: E402
from matplotlib.font_manager import FontProperties  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import PathPatch  # noqa: E402
from matplotlib.patheffects import withStroke  # noqa: E402
from matplotlib.path import Path as MPath  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sailaab.districts import canonical_name  # noqa: E402

DATA = ROOT / "data"
OUT = ROOT / "briefs"
ATLAS = ROOT / "atlas"

# --------------------------------------------------------------------------- #
# constants                                                                     #
# --------------------------------------------------------------------------- #
GEN_DATE = "2026-07-22"  # printed in the footer + fixed PDF timestamp
PROJECT_URL = "bakathefish.github.io/Flood"
REPO = "github.com/bakathefish/Flood"
N_DECADE_SEASONS = 11  # 2015-2025 monsoons (see README)
EXEMPLARS = ("Firozpur", "Kapurthala", "Gurdaspur")  # for the composite preview

# Fixed PDF metadata -> byte-stable output (no embedded run timestamp).
_PDF_META = {
    "Creator": "sailaab/pipeline/make_district_briefs.py",
    "Producer": "matplotlib",
    "CreationDate": datetime(2026, 7, 22, 0, 0, 0),
    "ModDate": datetime(2026, 7, 22, 0, 0, 0),
}

# --- palette: light "paper" print ------------------------------------------ #
PAPER = "#FBFAF7"  # warm paper ground
INK = "#1B1E24"  # near-black body ink
SUBINK = "#484D57"  # secondary ink
FAINT = "#8A909B"  # captions / units
HAIR = "#D9DCE2"  # hairline rules
CYAN = "#0E7C9B"  # water / flood accent (deep, print-safe)
CYAN_DK = "#0A5C74"
AMBER = "#B26B12"  # risk / rupee / forecast accent
NEIGH_FILL = "#EDEEF1"  # greyed neighbouring districts
NEIGH_EDGE = "#CBCFD7"
TEHSIL_EDGE = "#9AA0AB"  # borders between the focus district's tehsils

# flood choropleth ramp (white -> cyan), fixed statewide scale for comparability
FLOOD_CMAP = LinearSegmentedColormap.from_list(
    "sailaab_flood",
    ["#FFFFFF", "#D7EEF4", "#8FD3E4", "#3EB1CE", "#0E7C9B", "#08485C"],
)
FLOOD_VMAX = 0.11  # statewide max tehsil fraction ~0.107 (Sultanpur Lodhi)
FLOOD_NORM = PowerNorm(gamma=0.55, vmin=0.0, vmax=FLOOD_VMAX)

# Gurmukhi (Nirmala UI) district names, keyed by canonical English spelling.
GURMUKHI = {
    "Amritsar": "ਅੰਮ੍ਰਿਤਸਰ",
    "Gurdaspur": "ਗੁਰਦਾਸਪੁਰ",
    "Firozpur": "ਫ਼ਿਰੋਜ਼ਪੁਰ",
    "Kapurthala": "ਕਪੂਰਥਲਾ",
    "Tarn Taran": "ਤਰਨ ਤਾਰਨ",
    "Jalandhar": "ਜਲੰਧਰ",
    "Ludhiana": "ਲੁਧਿਆਣਾ",
    "Patiala": "ਪਟਿਆਲਾ",
    "Sangrur": "ਸੰਗਰੂਰ",
    "Bathinda": "ਬਠਿੰਡਾ",
    "Moga": "ਮੋਗਾ",
    "Muktsar": "ਮੁਕਤਸਰ",
    "Faridkot": "ਫ਼ਰੀਦਕੋਟ",
    "Barnala": "ਬਰਨਾਲਾ",
    "Mansa": "ਮਾਨਸਾ",
    "Hoshiarpur": "ਹੁਸ਼ਿਆਰਪੁਰ",
    "Rupnagar": "ਰੂਪਨਗਰ",
    "Nawanshahr": "ਨਵਾਂਸ਼ਹਿਰ",
    "Fatehgarh Sahib": "ਫ਼ਤਹਿਗੜ੍ਹ ਸਾਹਿਬ",
    "Sahibzada Ajit Singh Nagar": "ਸਾਹਿਬਜ਼ਾਦਾ ਅਜੀਤ ਸਿੰਘ ਨਗਰ",
}

# A handful of districts carry a widely-used second name; shown as a sub-label.
ALT_NAME = {
    "Nawanshahr": "Shaheed Bhagat Singh Nagar",
    "Sahibzada Ajit Singh Nagar": "Mohali",
    "Muktsar": "Sri Muktsar Sahib",
}

# --------------------------------------------------------------------------- #
# Gurmukhi shaping (deterministic pre-base i-matra reorder)                     #
# --------------------------------------------------------------------------- #
_I_MATRA = "ਿ"  # ਿ  short-i, a pre-base (left-joining) vowel sign
_NUKTA = "਼"  # ਼   combining nukta


def _is_gurmukhi_consonant(ch: str) -> bool:
    o = ord(ch)
    return 0x0A15 <= o <= 0x0A39 or 0x0A59 <= o <= 0x0A5E


def _shape_gurmukhi(s: str) -> str:
    """Move each pre-base short-i matra before its consonant (over a nukta).

    matplotlib does not reorder Indic pre-base matras, so ``ਫ਼ਿ`` (typed
    consonant-then-matra) would draw the i-stroke on the wrong side.  We emit the
    matra just before its base consonant so a non-shaping renderer draws it on
    the correct (left) side.  Deterministic and idempotent for these names.
    """
    res: list[str] = []
    for ch in s:
        if ch == _I_MATRA and res:
            j = len(res) - 1
            if res[j] == _NUKTA:  # keep the matra left of the nukta too
                j -= 1
            j = max(j, 0)
            res.insert(j, ch)
        else:
            res.append(ch)
    return "".join(res)


def _load_gurmukhi_font() -> FontProperties | None:
    """Return a Nirmala UI FontProperties, or None if unavailable."""
    for cand in (r"C:\Windows\Fonts\Nirmala.ttc", r"C:\Windows\Fonts\Nirmala.ttf"):
        p = Path(cand)
        if p.exists():
            try:
                fm.fontManager.addfont(str(p))
                return FontProperties(fname=str(p))
            except Exception:
                pass
    # last resort: a system font advertising Gurmukhi coverage
    for name in ("Nirmala UI", "Noto Sans Gurmukhi", "Raavi"):
        try:
            path = fm.findfont(FontProperties(family=name), fallback_to_default=False)
            return FontProperties(fname=path)
        except Exception:
            continue
    return None


# --------------------------------------------------------------------------- #
# data loading                                                                  #
# --------------------------------------------------------------------------- #
def _read_csv(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _fnum(v: str, default: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def load_tables() -> dict:
    """Load every committed table, keyed by canonical district name."""
    dist = {
        canonical_name(r["district"]): r
        for r in _read_csv(DATA / "district_flood_stats_2025.csv")
    }
    # VaR v2 (DES district yields) supersedes the flat-yield v1 for display;
    # district_flood_stats_2025.csv itself stays untouched (docs/notes/gov-data.md)
    for r in _read_csv(DATA / "district_var_v2.csv"):
        d = canonical_name(r["district"])
        if d in dist:
            dist[d]["crop_var_inr"] = r["crop_var_inr_v2"]
    freq = {
        canonical_name(r["district"]): r
        for r in _read_csv(DATA / "flood_frequency_districts_late_season.csv")
    }
    pop = {
        canonical_name(r["district"]): r
        for r in _read_csv(DATA / "pop_exposure_2025.csv")
    }

    # forecaster: peak p_event per district + statewide rank
    peak: dict[str, tuple[float, str]] = {}
    for r in _read_csv(DATA / "forecaster_2025_hindcast.csv"):
        d = canonical_name(r["district"])
        p = _fnum(r["p_event"])
        if d not in peak or p > peak[d][0]:
            peak[d] = (p, r["window_start"])
    order = sorted(peak.items(), key=lambda kv: (-kv[1][0], kv[0]))
    rank = {d: i for i, (d, _) in enumerate(order, start=1)}

    # tehsils: join 2025 stats with decade repeat-victim seasons
    seasons = {
        (canonical_name(r["district"]), r["tehsil"]): r
        for r in _read_csv(DATA / "tehsil_repeat_victims.csv")
    }
    tehsils: dict[str, list[dict]] = {}
    for r in _read_csv(DATA / "tehsil_flood_stats_2025.csv"):
        d = canonical_name(r["district"])
        sv = seasons.get((d, r["tehsil"]), {})
        tehsils.setdefault(d, []).append(
            {
                "tehsil": r["tehsil"],
                "rf_ha": _fnum(r["rf_flooded_ha"]),
                "fraction": _fnum(r["fraction"]),
                "seasons_gt1": int(_fnum(sv.get("seasons_gt1pct", 0))),
                "seasons_gt2": int(_fnum(sv.get("seasons_gt2pct", 0))),
            }
        )
    for d in tehsils:
        tehsils[d].sort(key=lambda t: (-t["rf_ha"], t["tehsil"]))

    return {
        "dist": dist,
        "freq": freq,
        "pop": pop,
        "peak": peak,
        "rank": rank,
        "n_rank": len(rank),
        "tehsils": tehsils,
    }


# --------------------------------------------------------------------------- #
# geometry helpers                                                              #
# --------------------------------------------------------------------------- #
def _geom_parts(geom: dict) -> list[list[list]]:
    """GeoJSON geometry -> list of polygon parts; each part = [exterior, *holes]."""
    t = geom["type"]
    if t == "Polygon":
        return [geom["coordinates"]]
    if t == "MultiPolygon":
        return list(geom["coordinates"])
    return []


def _ring_signed_area(r: np.ndarray) -> float:
    x, y = r[:, 0], r[:, 1]
    return 0.5 * float(np.sum(x[:-1] * y[1:] - x[1:] * y[:-1]))


def _compound_path(parts: list[list[list]]) -> MPath:
    """Build a filled matplotlib Path from polygon parts, holes wound opposite."""
    verts: list[np.ndarray] = []
    codes: list[np.ndarray] = []
    for rings in parts:
        for i, ring in enumerate(rings):
            r = np.asarray(ring, dtype=float)
            if r.shape[0] < 3:
                continue
            if not np.array_equal(r[0], r[-1]):
                r = np.vstack([r, r[0]])
            area = _ring_signed_area(r)
            if i == 0 and area < 0:  # exterior -> CCW
                r = r[::-1]
            elif i > 0 and area > 0:  # hole -> CW
                r = r[::-1]
            n = len(r)
            c = np.full(n, MPath.LINETO, dtype=np.uint8)
            c[0] = MPath.MOVETO
            c[-1] = MPath.CLOSEPOLY
            verts.append(r)
            codes.append(c)
    return MPath(np.vstack(verts), np.concatenate(codes))


def _bbox(parts: list[list[list]]) -> tuple[float, float, float, float]:
    xs: list[float] = []
    ys: list[float] = []
    for rings in parts:
        ext = np.asarray(rings[0], dtype=float)
        xs.extend(ext[:, 0].tolist())
        ys.extend(ext[:, 1].tolist())
    return min(xs), min(ys), max(xs), max(ys)


def load_geometry() -> dict:
    """Load district & tehsil polygons, keyed by canonical names."""
    dg = json.loads((DATA / "punjab_districts.geojson").read_text(encoding="utf-8"))
    districts: dict[str, dict] = {}
    for f in dg["features"]:
        name = canonical_name(f["properties"]["district"])
        parts = _geom_parts(f["geometry"])
        districts[name] = {"parts": parts, "bbox": _bbox(parts)}

    tg = json.loads((DATA / "punjab_tehsils.geojson").read_text(encoding="utf-8"))
    tehsils: dict[str, list[dict]] = {}
    for f in tg["features"]:
        d = canonical_name(f["properties"]["district"])
        parts = _geom_parts(f["geometry"])
        tehsils.setdefault(d, []).append(
            {"tehsil": f["properties"]["tehsil"], "parts": parts, "bbox": _bbox(parts)}
        )
    return {"districts": districts, "tehsils": tehsils}


# --------------------------------------------------------------------------- #
# number formatting                                                             #
# --------------------------------------------------------------------------- #
def _ha(v: float) -> str:
    return f"{v:,.0f}"


def _persons(v: float) -> str:
    return f"{v:,.0f}"


def _crore(inr: float) -> str:
    cr = inr / 1e7
    if cr >= 100:
        return f"{cr:,.0f}"
    if cr >= 10:
        return f"{cr:.1f}"
    return f"{cr:.2f}"


def _pct(frac: float) -> str:
    return f"{frac * 100:.2f}%"


# --------------------------------------------------------------------------- #
# drawing                                                                       #
# --------------------------------------------------------------------------- #
def _minimap(ax, name: str, geom: dict, tehsil_frac: dict) -> None:
    """District mini-map: greyed neighbours, tehsil flood choropleth, ink outline."""
    districts = geom["districts"]
    foc = districts[name]
    x0, y0, x1, y1 = foc["bbox"]
    padx = (x1 - x0) * 0.16 + 0.02
    pady = (y1 - y0) * 0.16 + 0.02
    win = (x0 - padx, y0 - pady, x1 + padx, y1 + pady)

    # neighbours (all districts, greyed) -- drawn first, clipped by the window
    for dn, d in districts.items():
        if dn == name:
            continue
        bx0, by0, bx1, by1 = d["bbox"]
        if bx1 < win[0] or bx0 > win[2] or by1 < win[1] or by0 > win[3]:
            continue
        ax.add_patch(
            PathPatch(
                _compound_path(d["parts"]),
                facecolor=NEIGH_FILL,
                edgecolor=NEIGH_EDGE,
                linewidth=0.5,
                zorder=1,
            )
        )

    # focus tehsils, shaded by 2025 RF flooded fraction
    worst = []
    for t in geom["tehsils"].get(name, []):
        frac = tehsil_frac.get((name, t["tehsil"]), 0.0)
        ax.add_patch(
            PathPatch(
                _compound_path(t["parts"]),
                facecolor=FLOOD_CMAP(FLOOD_NORM(frac)),
                edgecolor=TEHSIL_EDGE,
                linewidth=0.45,
                zorder=2,
            )
        )
        worst.append((frac, t))

    # district outline (ink)
    ax.add_patch(
        PathPatch(
            _compound_path(foc["parts"]),
            facecolor="none",
            edgecolor=INK,
            linewidth=1.6,
            zorder=4,
        )
    )

    # label the two worst-flooded tehsils
    worst.sort(key=lambda fr: -fr[0])
    for frac, t in worst[:2]:
        if frac <= 0:
            continue
        bx0, by0, bx1, by1 = t["bbox"]
        cx, cy = (bx0 + bx1) / 2, (by0 + by1) / 2
        txt = ax.text(
            cx,
            cy,
            t["tehsil"],
            fontsize=6.0,
            color=INK,
            ha="center",
            va="center",
            zorder=5,
        )
        txt.set_path_effects([withStroke(linewidth=1.8, foreground="white")])

    mean_lat = (win[1] + win[3]) / 2
    ax.set_xlim(win[0], win[2])
    ax.set_ylim(win[1], win[3])
    ax.set_aspect(1.0 / math.cos(math.radians(mean_lat)))
    ax.axis("off")


def _flood_legend(ax) -> None:
    """Slim horizontal legend for the flood-fraction ramp."""
    grad = np.linspace(0, 1, 256).reshape(1, -1)
    ax.imshow(grad, aspect="auto", cmap=FLOOD_CMAP, extent=(0, 1, 0, 1), origin="lower")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_yticks([])
    # tick positions follow the PowerNorm so labels sit at true fractions
    ticks = [0.0, 0.02, 0.05, 0.11]
    ax.set_xticks([FLOOD_NORM(t) for t in ticks])
    ax.set_xticklabels([f"{int(t * 100)}%" for t in ticks], fontsize=6.5, color=SUBINK)
    ax.tick_params(length=2, pad=1.5, colors=SUBINK)
    for s in ax.spines.values():
        s.set_edgecolor(HAIR)
        s.set_linewidth(0.5)


def _tile(fig, x, y, label, value, unit, accent, *, vsize=16.5, sub=None):
    """One stat tile placed in figure coordinates (label above, big value)."""
    fig.text(
        x,
        y,
        label.upper(),
        fontsize=6.6,
        color=FAINT,
        ha="left",
        va="baseline",
        family="DejaVu Sans",
    )
    vt = fig.text(
        x,
        y - 0.0235,
        value,
        fontsize=vsize,
        color=accent,
        ha="left",
        va="baseline",
        family="DejaVu Sans",
        weight="bold",
    )
    if unit:
        # place the unit just after the measured value (Agg renderer, no draw)
        bb = vt.get_window_extent(fig.canvas.get_renderer())
        inv = fig.transFigure.inverted()
        x_after = inv.transform((bb.x1, bb.y0))[0] + 0.006
        fig.text(
            x_after,
            y - 0.0235,
            unit,
            fontsize=8,
            color=SUBINK,
            ha="left",
            va="baseline",
            family="DejaVu Sans",
        )
    if sub:
        fig.text(
            x,
            y - 0.0335,
            sub,
            fontsize=6.4,
            color=SUBINK,
            ha="left",
            va="baseline",
            family="DejaVu Sans",
        )


def _section(fig, x, y, w, text, accent=CYAN):
    fig.text(
        x,
        y,
        text.upper(),
        fontsize=8.2,
        color=accent,
        ha="left",
        va="baseline",
        family="DejaVu Sans",
        weight="bold",
    )
    _hline(fig, x, x + w, y - 0.008, accent, 0.9)


def _hline(fig, x0, x1, y, color, lw):
    """Add a horizontal rule in figure coordinates."""
    ln = Line2D(
        [x0, x1], [y, y], transform=fig.transFigure, color=color, linewidth=lw, zorder=0
    )
    fig.add_artist(ln)
    return ln


def _fit_text(fig, x, y, text, base_size, max_w, *, min_size=13.0, **kw):
    """Place text, shrinking the font so its width stays within ``max_w`` (fig fraction)."""
    t = fig.text(x, y, text, fontsize=base_size, **kw)
    w = t.get_window_extent(fig.canvas.get_renderer()).width / fig.bbox.width
    if w > max_w:
        t.set_fontsize(max(base_size * max_w / w, min_size))
    return t


# --------------------------------------------------------------------------- #
# one brief                                                                     #
# --------------------------------------------------------------------------- #
def build_brief(name: str, tables: dict, geom: dict, guru_fp) -> plt.Figure:
    d = tables["dist"][name]
    fr = tables["freq"][name]
    pp = tables["pop"][name]
    peak_p, peak_win = tables["peak"][name]
    rank = tables["rank"][name]
    n_rank = tables["n_rank"]
    tehsils = tables["tehsils"].get(name, [])
    tehsil_frac = {(name, t["tehsil"]): t["fraction"] for t in tehsils}

    fig = plt.figure(figsize=(8.27, 11.69), dpi=200)  # A4 portrait
    fig.patch.set_facecolor(PAPER)

    # ---- header ----------------------------------------------------------- #
    fig.text(
        0.055,
        0.958,
        "SAILAAB",
        fontsize=19,
        color=INK,
        weight="bold",
        family="DejaVu Sans",
        va="baseline",
    )
    # cyan accent tick under the wordmark
    _hline(fig, 0.055, 0.20, 0.9435, CYAN, 2.4)
    fig.text(
        0.275,
        0.958,
        "DISTRICT  FLOOD  BRIEF",
        fontsize=9.5,
        color=SUBINK,
        weight="bold",
        family="DejaVu Sans",
        va="baseline",
    )
    fig.text(
        0.275,
        0.9405,
        "2025 monsoon  +  decade context",
        fontsize=8.2,
        color=FAINT,
        family="DejaVu Sans",
        va="baseline",
    )

    # right-aligned URL block
    fig.text(
        0.945,
        0.958,
        PROJECT_URL,
        fontsize=9.5,
        color=AMBER,
        ha="right",
        weight="bold",
        family="DejaVu Sans",
        va="baseline",
    )
    fig.text(
        0.945,
        0.9405,
        "open data · no login",
        fontsize=8.2,
        color=FAINT,
        ha="right",
        family="DejaVu Sans",
        va="baseline",
    )

    # district name (English, left) + Gurmukhi echo (right) -- each auto-fit to
    # its half so long names (e.g. Sahibzada Ajit Singh Nagar) never collide.
    _fit_text(
        fig,
        0.055,
        0.902,
        name,
        31,
        0.50,
        min_size=17.0,
        color=INK,
        weight="bold",
        family="DejaVu Sans",
        va="baseline",
        ha="left",
    )
    alt = ALT_NAME.get(name)
    if alt:
        fig.text(
            0.058,
            0.879,
            f"also {alt}",
            fontsize=8.5,
            color=FAINT,
            family="DejaVu Sans",
            va="baseline",
        )
    if guru_fp is not None and name in GURMUKHI:
        _fit_text(
            fig,
            0.945,
            0.902,
            _shape_gurmukhi(GURMUKHI[name]),
            26,
            0.37,
            min_size=14.0,
            color=CYAN_DK,
            ha="right",
            va="baseline",
            fontproperties=guru_fp,
        )
    else:
        fig.text(
            0.945,
            0.902,
            "(Gurmukhi unavailable)",
            fontsize=8,
            color=FAINT,
            ha="right",
            va="baseline",
            family="DejaVu Sans",
        )

    _hline(fig, 0.055, 0.945, 0.868, INK, 1.3)

    # ---- left column: adaptive mini-map ----------------------------------- #
    # Size the map box to the district's true (latitude-corrected) aspect so the
    # polygon fills it without letterboxing, top-anchored under the header.
    lx, lw = 0.055, 0.40
    bx0, by0, bx1, by1 = geom["districts"][name]["bbox"]
    padx = (bx1 - bx0) * 0.16 + 0.02
    pady = (by1 - by0) * 0.16 + 0.02
    latm = math.radians((by0 - pady + by1 + pady) / 2)
    data_ratio = (by1 - by0 + 2 * pady) / ((bx1 - bx0 + 2 * padx) * math.cos(latm))
    box_h = min(max(lw * 8.27 * data_ratio / 11.69, 0.26), 0.52)

    fig.text(
        lx,
        0.853,
        "2025 FLOOD EXTENT BY TEHSIL",
        fontsize=8.2,
        color=CYAN,
        weight="bold",
        family="DejaVu Sans",
        va="baseline",
    )
    map_top = 0.838
    ax_map = fig.add_axes((lx, map_top - box_h, lw, box_h))
    ax_map.set_facecolor(PAPER)
    _minimap(ax_map, name, geom, tehsil_frac)

    leg_y = map_top - box_h - 0.040
    ax_leg = fig.add_axes((lx + 0.02, leg_y, 0.24, 0.013))
    _flood_legend(ax_leg)
    fig.text(
        lx + 0.02,
        leg_y - 0.022,
        "share of tehsil area flooded (RF, 2025)",
        fontsize=6.6,
        color=FAINT,
        family="DejaVu Sans",
        va="baseline",
    )
    fig.text(
        lx + 0.02,
        leg_y - 0.037,
        "neighbouring districts greyed · outline = district",
        fontsize=6.6,
        color=FAINT,
        family="DejaVu Sans",
        va="baseline",
    )

    # ---- right column: stats ---------------------------------------------- #
    rx = 0.505
    rw = 0.44
    col2 = rx + 0.225
    r1, r2, r3 = 0.820, 0.763, 0.706  # 2025 rows
    d1, d2, d3 = 0.632, 0.575, 0.518  # decade rows

    # 2025 monsoon block
    _section(fig, rx, 0.848, rw, "2025 monsoon impact", CYAN)
    _tile(fig, rx, r1, "RF flooded", _ha(_fnum(d["rf_flooded_ha"])), "ha", CYAN)
    _tile(fig, col2, r1, "Tier-A flooded", _ha(_fnum(d["tierA_flooded_ha"])), "ha", INK)
    _tile(fig, rx, r2, "Cropland flooded", _ha(_fnum(d["crop_flooded_ha"])), "ha", CYAN)
    _tile(
        fig,
        col2,
        r2,
        "Value at risk",
        "₹" + _crore(_fnum(d["crop_var_inr"])),
        "cr",
        AMBER,
        sub="paddy MSP × DES yields",
    )
    _tile(
        fig,
        rx,
        r3,
        "People exposed · RF",
        _persons(_fnum(pp["pop_exposed_rf"])),
        "",
        CYAN,
    )
    _tile(
        fig,
        col2,
        r3,
        "People exposed · GFM",
        _persons(_fnum(pp["pop_exposed_gfm"])),
        "",
        INK,
    )

    # decade block
    _section(fig, rx, 0.660, rw, "decade context · 2015–2025", CYAN)
    _tile(
        fig,
        rx,
        d1,
        "Seasons > 1%",
        f"{int(_fnum(fr['seasons_with_fraction_gt1pct']))}",
        f"/ {N_DECADE_SEASONS}",
        INK,
    )
    _tile(
        fig,
        col2,
        d1,
        "Seasons > 2%",
        f"{int(_fnum(fr['seasons_with_fraction_gt2pct']))}",
        f"/ {N_DECADE_SEASONS}",
        INK,
    )
    _tile(
        fig,
        rx,
        d2,
        "Worst season",
        _pct(_fnum(fr["max_season_fraction"])),
        "",
        INK,
        sub="peak decade flooded share",
    )
    _tile(
        fig,
        col2,
        d2,
        "Mean annual",
        _ha(_fnum(fr["mean_annual_flooded_ha"])),
        "ha",
        INK,
        sub="avg flooded / season",
    )
    peak_txt = f"{peak_p:.2f}" if peak_p >= 0.01 else "<0.01"
    _tile(
        fig,
        rx,
        d3,
        "Forecast peak P",
        peak_txt,
        "",
        AMBER,
        sub=f"window {peak_win}",
    )
    _tile(
        fig,
        col2,
        d3,
        "Statewide rank",
        f"#{rank}",
        f"/ {n_rank}",
        AMBER,
        sub="by forecast peak P",
    )

    # ---- tehsil table ----------------------------------------------------- #
    _section(fig, rx, 0.454, rw, "tehsils · worst first", CYAN)
    ty = 0.432
    fig.text(
        rx,
        ty,
        "TEHSIL",
        fontsize=7,
        color=FAINT,
        weight="bold",
        family="DejaVu Sans",
        va="baseline",
    )
    fig.text(
        rx + 0.305,
        ty,
        "2025 ha",
        fontsize=7,
        color=FAINT,
        weight="bold",
        family="DejaVu Sans",
        va="baseline",
        ha="right",
    )
    fig.text(
        rx + 0.44,
        ty,
        "≥1% seasons",
        fontsize=7,
        color=FAINT,
        weight="bold",
        family="DejaVu Sans",
        va="baseline",
        ha="right",
    )
    _hline(fig, rx, rx + rw, ty - 0.006, HAIR, 0.8)

    row_h = 0.0176
    max_rows = 15
    shown = tehsils[:max_rows]
    for i, t in enumerate(shown):
        yy = ty - 0.020 - i * row_h
        strong = t["rf_ha"] >= 100
        fig.text(
            rx,
            yy,
            t["tehsil"],
            fontsize=7.6,
            color=INK if strong else SUBINK,
            family="DejaVu Sans",
            va="baseline",
        )
        fig.text(
            rx + 0.305,
            yy,
            _ha(t["rf_ha"]),
            fontsize=7.6,
            color=INK if strong else SUBINK,
            family="DejaVu Sans",
            va="baseline",
            ha="right",
        )
        s1 = t["seasons_gt1"]
        badge = "—" if s1 == 0 else ("●" * min(s1, 6))
        bcol = FAINT if s1 == 0 else (AMBER if s1 >= 3 else CYAN)
        fig.text(
            rx + 0.44,
            yy,
            badge,
            fontsize=7.6,
            color=bcol,
            family="DejaVu Sans",
            va="baseline",
            ha="right",
        )
    if len(tehsils) > max_rows:
        yy = ty - 0.020 - len(shown) * row_h
        fig.text(
            rx,
            yy,
            f"+ {len(tehsils) - max_rows} more tehsils",
            fontsize=6.8,
            color=FAINT,
            style="italic",
            family="DejaVu Sans",
            va="baseline",
        )

    # ---- footer ----------------------------------------------------------- #
    _hline(fig, 0.055, 0.945, 0.058, HAIR, 0.8)
    fig.text(
        0.055,
        0.043,
        "Method: Sentinel-1 SAR change-detection (Tier-A) + "
        "Random-Forest flood mask; per-tehsil reduction; XGBoost forecaster "
        "(leave-one-year-out).",
        fontsize=6.6,
        color=SUBINK,
        family="DejaVu Sans",
        va="baseline",
    )
    fig.text(
        0.055,
        0.030,
        f"Open data: {REPO} · validated vs Copernicus GFM & "
        "ISRO NDEM. Crop value order-of-magnitude (paddy MSP × DES district yields).",
        fontsize=6.6,
        color=SUBINK,
        family="DejaVu Sans",
        va="baseline",
    )
    fig.text(
        0.945,
        0.030,
        f"Generated {GEN_DATE}",
        fontsize=6.6,
        color=FAINT,
        ha="right",
        family="DejaVu Sans",
        va="baseline",
    )

    return fig


# --------------------------------------------------------------------------- #
# orchestration                                                                 #
# --------------------------------------------------------------------------- #
def _save_pdf(fig: plt.Figure, path: Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, format="pdf", facecolor=PAPER, metadata=_PDF_META)
    return path.stat().st_size


def make_preview(names: list[str], tables, geom, guru_fp, out: Path) -> int:
    """Composite exemplar briefs side-by-side into a single PNG (< 1.2 MB)."""
    from io import BytesIO

    from PIL import Image

    dpi = 100  # 100 dpi -> ~827x1169 px per A4 page; mostly-white -> small PNG
    imgs: list[Image.Image] = []
    for nm in names:
        f = build_brief(nm, tables, geom, guru_fp)
        buf = BytesIO()
        f.savefig(buf, format="png", dpi=dpi, facecolor=PAPER)
        plt.close(f)
        buf.seek(0)
        imgs.append(Image.open(buf).convert("RGB"))

    h = min(im.height for im in imgs)
    imgs = [
        im
        if im.height == h
        else im.resize((round(im.width * h / im.height), h), Image.LANCZOS)
        for im in imgs
    ]
    gap, margin = 22, 16
    bg = (247, 247, 245)
    w = sum(im.width for im in imgs) + gap * (len(imgs) - 1) + 2 * margin
    canvas = Image.new("RGB", (w, h + 2 * margin), bg)
    x = margin
    for im in imgs:
        canvas.paste(im, (x, margin))
        x += im.width + gap

    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out, format="PNG", optimize=True)
    return out.stat().st_size


def main(argv: list[str]) -> int:
    guru_fp = _load_gurmukhi_font()
    tables = load_tables()
    geom = load_geometry()

    all_names = sorted(
        tables["dist"], key=lambda n: (-_fnum(tables["dist"][n]["rf_flooded_ha"]), n)
    )
    want = [canonical_name(a) for a in argv] if argv else all_names

    OUT.mkdir(parents=True, exist_ok=True)
    total = 0
    print(
        f"Gurmukhi font: {'Nirmala UI' if guru_fp else 'UNAVAILABLE -> English-only'}"
    )
    for nm in want:
        if nm not in tables["dist"]:
            print(f"  ! unknown district: {nm}")
            continue
        fig = build_brief(nm, tables, geom, guru_fp)
        size = _save_pdf(fig, OUT / f"{nm}.pdf")
        plt.close(fig)
        total += size
        flag = "" if size < 400_000 else "  <-- OVER 400 KB"
        print(f"  {nm:30s} {size / 1024:7.1f} KB{flag}")
    print(f"  {'TOTAL':30s} {total / 1024 / 1024:7.2f} MB")

    if not argv:
        psize = make_preview(
            list(EXEMPLARS), tables, geom, guru_fp, ATLAS / "briefs_preview.png"
        )
        print(f"  preview atlas/briefs_preview.png  {psize / 1024:7.1f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
