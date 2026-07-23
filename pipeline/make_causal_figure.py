#!/usr/bin/env python
# pipeline/make_causal_figure.py
"""Render ``atlas/causal_2025.png`` - the one causal figure of the entry.

The chart argues, from data already committed in ``data/``, WHY Punjab flooded in
2025 by stacking the causal chain on a shared June 1 -> September 30 time axis:

    Panel A  extreme late-August rain over the upstream (Sutlej/Beas/Ravi) and
             Punjab boxes, against the 2015-2024 same-day "normal" band.
    Panel B  the three BBMB dams (Bhakra / Pong / Ranjit Sagar) filling to the
             brim - solid = CWC daily API (to 11 Jul), dashed = BBMB/press for
             the Aug-Sep flood window the API never reported - then the forced
             releases that inundated the plains.

Deterministic: same CSVs in -> byte-stable PNG out. No network, no randomness.

Run:  python pipeline/make_causal_figure.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Allow `python pipeline/make_causal_figure.py` (script dir on path, not root).
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import matplotlib  # noqa: E402

matplotlib.use("Agg")

import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patheffects import withStroke  # noqa: E402

from sailaab import causal  # noqa: E402
from sailaab import figstyle  # noqa: E402
from sailaab.reservoirs import normalize  # noqa: E402

DATA = ROOT / "data"
OUT = ROOT / "atlas" / "causal_2025.png"

# --- time anchors -----------------------------------------------------------
START = pd.Timestamp("2025-06-01")
END = pd.Timestamp("2025-09-30")
FLOOD0 = pd.Timestamp("2025-08-26")  # flood window (shaded both panels)
FLOOD1 = pd.Timestamp("2025-09-06")
GAP0 = pd.Timestamp("2025-07-11")  # CWC/BBMB reporting blackout
GAP1 = pd.Timestamp("2025-08-01")
PRIOR_YEARS = range(2015, 2025)

# --- ink & palette (validated: rain pair blue/orange, dam trio violet/green/red
#     pass scripts/validate_palette.js --pairs all on the white surface) -------
INK = "#0b0b0b"
INK2 = "#52514e"
MUTED = "#898781"
GRID = "#e7e6e0"
AXIS = "#c3c2b7"
BAND = "#d7d6cf"  # 2015-24 "normal" rainfall silhouette
FLOOD_WASH = "#eda100"  # flood-window highlight (amber, low alpha)
GAP_WASH = "#f1f0ea"  # reporting-gap band

BLUE = "#2a78d6"  # upstream rain (the driver)
ORANGE = "#eb6834"  # Punjab-plains rain
DAMS = (("Bhakra", "#4a3aa7"), ("Pong", "#e34948"), ("Ranjit Sagar", "#008300"))
DAM_COLOR = dict(DAMS)

# Gurmukhi-capable face for the bilingual subtitle; falls back to the default
# sans (English-only subtitle) if the system can't render Gurmukhi.
_GUR_NAME = "Nirmala UI"
_HAVE_GUR = any(f.name == _GUR_NAME for f in font_manager.fontManager.ttflist)
GUR = font_manager.FontProperties(family=_GUR_NAME) if _HAVE_GUR else None

figstyle.apply()
plt.rcParams.update(
    {
        # generic family (IBM Plex Sans is first in font.sans-serif via
        # figstyle.apply); any rendered glyph must exist in IBM Plex Sans, so the
        # reporting-gap note spells out "severed" instead of a slashed arrow.
        "font.family": "sans-serif",
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "axes.edgecolor": AXIS,
        "axes.linewidth": 0.9,
        "text.color": INK,
        "axes.labelcolor": INK2,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
    }
)

_HALO = [withStroke(linewidth=2.4, foreground="white")]


# --------------------------------------------------------------------------- #
# data
# --------------------------------------------------------------------------- #
def load_data():
    rain = pd.read_csv(DATA / "rain_daily_boxes_2015_2025.csv", parse_dates=["date"])
    daily = normalize(pd.read_csv(DATA / "reservoirs_2015_2025.csv"))
    supp = normalize(pd.read_csv(DATA / "reservoirs_2025_flood_supplement.csv"))
    return rain, daily, supp


def _season(df):
    return df[(df["date"] >= START) & (df["date"] <= END)].sort_values("date")


# --------------------------------------------------------------------------- #
# panels
# --------------------------------------------------------------------------- #
def _style_axes(ax):
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", color=GRID, lw=0.8, zorder=0)
    ax.set_axisbelow(True)
    ax.margins(x=0)
    ax.tick_params(labelfontfamily=figstyle.FONT_MONO,  # numeric ticks in mono
                   colors=INK2, length=0)               # muted labels, no marks


def panel_rain(ax, rain):
    r25 = _season(rain)
    clim = causal.same_day_climatology(
        rain,
        ["upstream_mm", "punjab_mm"],
        PRIOR_YEARS,
        r25["date"],
        quantiles=(0.5,),
    )
    x = r25["date"].values

    # 2015-24 "normal": same-day median silhouette (upstream = the driver)
    ax.fill_between(x, 0, clim["upstream_mm_p50"], color=BAND, lw=0, zorder=1)

    # 2025 daily traces
    ax.fill_between(x, 0, r25["upstream_mm"], color=BLUE, alpha=0.10, lw=0, zorder=2)
    ax.plot(x, r25["upstream_mm"], color=BLUE, lw=1.7, solid_capstyle="round", zorder=4)
    ax.plot(x, r25["punjab_mm"], color=ORANGE, lw=1.4, solid_capstyle="round", zorder=3)

    # scream the peak (26 Aug)
    pk = r25.loc[r25["upstream_mm"].idxmax()]
    up_med = float(clim.loc[pk["date"], "upstream_mm_p50"])
    ratio = pk["upstream_mm"] / up_med if up_med else float("nan")
    ax.annotate(
        f"26 Aug: {pk['upstream_mm']:.0f} mm upstream, {pk['punjab_mm']:.0f} mm Punjab\n"
        f"≈{ratio:.0f}× the 2015–24 same-day median",
        xy=(pk["date"], pk["punjab_mm"]),
        xytext=(pd.Timestamp("2025-07-05"), 45),
        fontsize=8.3,
        color=INK,
        va="center",
        ha="left",
        path_effects=_HALO,
        arrowprops=dict(
            arrowstyle="-|>",
            color=INK,
            lw=1.2,
            mutation_scale=12,
            alpha=0.9,
            connectionstyle="arc3,rad=-0.18",
            shrinkA=5,
            shrinkB=7,
        ),
    )

    ax.set_ylim(0, 72)
    ax.set_yticks([0, 20, 40, 60])
    ax.set_ylabel("Rainfall\n(mm / day)", fontsize=9.5, color=INK2)
    handles = [
        Line2D([0], [0], color=BLUE, lw=2.2, label="Upstream catchments (2025)"),
        Line2D([0], [0], color=ORANGE, lw=2.2, label="Punjab plains (2025)"),
        Line2D([0], [0], color=BAND, lw=7, label="2015–24 normal (same-day median)"),
    ]
    ax.legend(
        handles=handles,
        loc="upper left",
        fontsize=7.8,
        frameon=False,
        borderaxespad=0.3,
        handlelength=1.6,
        labelspacing=0.35,
    )
    _style_axes(ax)


def _label(
    ax, x, y, text, color, dx=6, dy=0, ha="left", va="center", size=8.2, weight="bold"
):
    ax.annotate(
        text,
        xy=(x, y),
        xytext=(dx, dy),
        textcoords="offset points",
        fontsize=size,
        color=color,
        ha=ha,
        va=va,
        weight=weight,
        path_effects=_HALO,
        zorder=8,
    )


def panel_reservoirs(ax, daily, supp):
    for dam, color in DAMS:
        d = _season(daily)
        d = d[(d["dam"] == dam) & (d["date"] <= GAP0)].dropna(subset=["pct_capacity"])
        ax.plot(
            d["date"],
            d["pct_capacity"],
            color=color,
            lw=1.9,
            solid_capstyle="round",
            zorder=4,
        )

        s = supp[supp["dam"] == dam].dropna(subset=["pct_capacity"]).sort_values("date")
        if len(s):
            ax.plot(
                s["date"],
                s["pct_capacity"],
                color=color,
                lw=1.7,
                ls=(0, (5, 2)),
                zorder=4,
            )
            ax.plot(
                s["date"],
                s["pct_capacity"],
                "o",
                color=color,
                ms=6.5,
                mec="white",
                mew=1.6,
                zorder=6,
            )

    # direct labels (secondary encoding for the red/green pair)
    _label(ax, pd.Timestamp("2025-09-03"), 93, "Bhakra 93%", DAM_COLOR["Bhakra"], dy=2)
    _label(
        ax,
        pd.Timestamp("2025-08-08"),
        83,
        "Pong",
        DAM_COLOR["Pong"],
        dx=-6,
        dy=-2,
        ha="right",
    )
    _label(
        ax,
        pd.Timestamp("2025-07-11"),
        37,
        "Ranjit Sagar",
        DAM_COLOR["Ranjit Sagar"],
        dx=-6,
        dy=11,
        ha="right",
    )

    # FRL / danger reference (100 % of live capacity == brim-full)
    ax.axhline(100, color=INK2, lw=1.2, ls=(0, (6, 3)), zorder=3)
    ax.annotate(
        "FRL: brim-full / danger level  (Bhakra 1,680 ft · Pong 1,390 ft)",
        xy=(START, 100),
        xytext=(2, 3),
        textcoords="offset points",
        fontsize=7.8,
        color=INK2,
        va="bottom",
        ha="left",
        path_effects=_HALO,
    )

    # consolidated causal callouts (sparse, high-value)
    ax.annotate(
        "Near-full by early Sept: Bhakra 1,678 ft,\n"
        "~1.5 ft under danger; Pong over its 1,390 ft brim\n(1,393 ft, 26 Aug)",
        xy=(pd.Timestamp("2025-09-03"), 93),
        xytext=(pd.Timestamp("2025-06-10"), 88),
        fontsize=8.0,
        color=INK,
        va="top",
        ha="left",
        path_effects=_HALO,
        arrowprops=dict(
            arrowstyle="-|>",
            color=INK,
            lw=1.2,
            mutation_scale=12,
            alpha=0.9,
            connectionstyle="arc3,rad=-0.14",
            shrinkA=5,
            shrinkB=7,
        ),
    )
    # Releases are outflow events (cusecs), not points on the % axis -> a clean
    # text block during the shaded flood window rather than an arrow to nowhere.
    ax.text(
        pd.Timestamp("2025-06-10"),
        58,
        "Forced releases → downstream flood:\n"
        "Ranjit Sagar 1.73 lakh cusecs (27 Aug),\nBhakra ~85,000 cusecs (4 Sep)",
        fontsize=8.0,
        color=INK,
        va="top",
        ha="left",
        path_effects=_HALO,
    )

    # Pong keeps rising past its FRL after its last %-reported point (level-only
    # thereafter): a thin arrow to just over the 100 % brim carries the story
    # without asserting a precise %.
    ax.annotate(
        "",
        xy=(pd.Timestamp("2025-08-26"), 101),
        xytext=(pd.Timestamp("2025-08-18"), 85),
        arrowprops=dict(
            arrowstyle="-|>",
            color=DAM_COLOR["Pong"],
            lw=1.3,
            ls=(0, (4, 2)),
            mutation_scale=12,
            alpha=0.9,
            connectionstyle="arc3,rad=-0.18",
            shrinkA=6,
            shrinkB=3,
        ),
        zorder=5,
    )

    ax.set_ylim(0, 108)
    ax.set_yticks([0, 25, 50, 75, 100])
    ax.set_ylabel("Reservoir storage\n(% of live capacity)", fontsize=9.5, color=INK2)

    handles = [
        Line2D([0], [0], color=DAM_COLOR["Bhakra"], lw=2.4, label="Bhakra (Sutlej)"),
        Line2D([0], [0], color=DAM_COLOR["Pong"], lw=2.4, label="Pong (Beas)"),
        Line2D(
            [0],
            [0],
            color=DAM_COLOR["Ranjit Sagar"],
            lw=2.4,
            label="Ranjit Sagar (Ravi)",
        ),
        Line2D(
            [0], [0], color=MUTED, lw=2.0, ls="-", label="CWC daily API (to 11 Jul)"
        ),
        Line2D(
            [0],
            [0],
            color=MUTED,
            lw=2.0,
            ls=(0, (5, 2)),
            marker="o",
            ms=6,
            mec="white",
            label="BBMB / press-reported",
        ),
    ]
    ax.legend(
        handles=handles,
        loc="lower right",
        fontsize=7.8,
        frameon=False,
        borderaxespad=0.5,
        handlelength=1.9,
        labelspacing=0.35,
        ncol=1,
    )
    _style_axes(ax)


def _spans(ax, flood_label=False, gap_label=False, flood_y=70, gap_y=52):
    ax.axvspan(GAP0, GAP1, color=GAP_WASH, zorder=0)
    ax.axvspan(FLOOD0, FLOOD1, color=FLOOD_WASH, alpha=0.11, zorder=0)
    mid_gap = GAP0 + (GAP1 - GAP0) / 2
    mid_fl = FLOOD0 + (FLOOD1 - FLOOD0) / 2
    if flood_label:
        ax.annotate(
            "flood window\n26 Aug–6 Sep",
            xy=(mid_fl, flood_y),
            textcoords="data",
            fontsize=7.2,
            color="#9a6b00",
            ha="center",
            va="top",
            weight="bold",
        )
    if gap_label:
        ax.annotate(
            "reporting gap\n(BBMB → CWC severed, 11 Jul)",
            xy=(mid_gap, gap_y),
            textcoords="data",
            fontsize=7.2,
            color=MUTED,
            ha="center",
            va="center",
            style="italic",
        )


# --------------------------------------------------------------------------- #
# figure
# --------------------------------------------------------------------------- #
def build(rain, daily, supp):
    fig = plt.figure(figsize=(10, 7), dpi=200)
    gs = fig.add_gridspec(
        2,
        1,
        height_ratios=[1.0, 2.05],
        hspace=0.10,
        left=0.085,
        right=0.975,
        top=0.845,
        bottom=0.235,
    )
    axA = fig.add_subplot(gs[0])
    axB = fig.add_subplot(gs[1], sharex=axA)

    panel_rain(axA, rain)
    panel_reservoirs(axB, daily, supp)
    _spans(axA, flood_label=True, flood_y=70)
    _spans(axB, gap_label=True, gap_y=52)

    axB.set_xlim(START, END)
    axB.xaxis.set_major_locator(mdates.MonthLocator())
    axB.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
    axB.xaxis.set_minor_locator(mdates.MonthLocator(bymonthday=15))
    plt.setp(axA.get_xticklabels(), visible=False)
    axB.tick_params(axis="x", length=0)

    # ---- title block -------------------------------------------------------
    fig.text(
        0.085,
        0.965,
        figstyle.clean("Why Punjab flooded in 2025"),
        fontsize=18,
        weight="bold",
        color=INK,
        ha="left",
        va="top",
        fontfamily=figstyle.FONT_DISPLAY,
    )
    sub = "ਸੈਲਾਬ 2025: ਹੜ੍ਹ ਕਿਉਂ ਆਇਆ" if GUR else "Sailaab 2025: why the flood came"
    fig.text(
        0.085,
        0.918,
        sub,
        fontsize=13,
        color=INK2,
        ha="left",
        va="top",
        fontproperties=GUR,
    )
    fig.text(
        0.975,
        0.960,
        "Upstream rain → near-full reservoirs → forced releases",
        fontsize=9.5,
        color=MUTED,
        ha="right",
        va="top",
        style="italic",
    )

    # ---- caption block -----------------------------------------------------
    fig.add_artist(Line2D([0.085, 0.975], [0.170, 0.170], color=GRID, lw=1.0))
    causal_sentence = (
        "Record late-August rain over the Sutlej–Beas–Ravi catchments (≈10× the 2015–24 "
        "same-day median) filled reservoirs that were already climbing: Bhakra to 93% "
        "of live capacity (1,678 ft, ~1.5 ft below its 1,680 ft danger level) and Pong "
        "over its 1,390 ft brim, forcing emergency releases (Ranjit Sagar 1.73 lakh "
        "cusecs, Bhakra ~85,000 cusecs) that inundated the plains downstream: Punjab’s "
        "worst floods since 1988."
    )
    fig.text(
        0.085,
        0.150,
        causal_sentence,
        fontsize=8.6,
        color=INK,
        ha="left",
        va="top",
        wrap=True,
    )
    fig.text(
        0.085,
        0.045,
        "Data. Rainfall: IMD 0.25° gridded, area-mean over the upstream & Punjab boxes.  "
        "Reservoirs: CWC via data.gov.in (daily, to 11 Jul 2025); Aug–Sep flood window "
        "BBMB via press (SANDRP, The Tribune, Down To Earth, Babushahi).  "
        "Solid = API · dashed = BBMB/press-reported.",
        fontsize=7.0,
        color=MUTED,
        ha="left",
        va="top",
        wrap=True,
    )
    return fig


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    rain, daily, supp = load_data()
    fig = build(rain, daily, supp)
    fig.savefig(OUT, dpi=200, facecolor="white")
    plt.close(fig)
    kb = OUT.stat().st_size / 1024
    print(f"wrote {OUT.relative_to(ROOT)}  ({kb:.0f} KB)")


if __name__ == "__main__":
    main()
