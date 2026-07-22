#!/usr/bin/env python
# pipeline/make_flood_history.py
"""Render ``atlas/punjab_flood_history.png`` -- Punjab's 2025 flood placed against
the **public damage record** as a *sparse milestone timeline*.

There is no continuous public annual series on the OGD portal (data.gov.in); the
record is a handful of milestones from three resources of different vintages and
different metrics (see ``docs/notes/flood-history.md`` and the consolidated
``data/punjab_flood_damage_history.csv``). The figure is therefore deliberately
sparse -- discrete markers, **no interpolation, no dense line** -- and keeps the
metric classes strictly separate:

  * top panel (log ha): the two AREA classes, drawn with distinct markers --
      flooded area (mapped / "area affected")  and  crop-damage area (girdawari);
  * the 1953-2010 worst-year maximum (2.79 Mha) as an *undated* reference band --
      the source publishes no year, so none is invented (see the red-team note);
  * 2025 enters as TWO separately-labelled points, never merged: 105,183 ha (our
      SAR single-pass mapped extent, flooded_area) and 1.985 lakh ha (official
      Special Girdawari cumulative crop damage, crop_damage_area);
  * bottom panel (count): human lives lost -- the placid 2018-21 baseline
      (single-digit to low-double-digit) against 55 in 2025.

Deterministic: same committed CSV in -> byte-stable PNG out. No network.

Run:  python pipeline/make_flood_history.py
      python -m pytest tests/test_history.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import matplotlib  # noqa: E402

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402
from matplotlib.patheffects import withStroke  # noqa: E402

from sailaab.history import load_history, milestones, period_to_year  # noqa: E402

DATA = ROOT / "data"
IN_CSV = DATA / "punjab_flood_damage_history.csv"
OUT_PNG = ROOT / "atlas" / "punjab_flood_history.png"

# --- dark house palette (matches pipeline/make_headroom.py) ------------------
INK, INK2, LINE2 = "#0a1014", "#0e161d", "#28394a"
PAPER, PAPER_DIM, PAPER_FAINT = "#e9e4d6", "#9aa5a4", "#5c6a70"
FLOODED = "#63e6d5"  # cyan  = flooded area (mapped / "area affected")
CROP = "#f2a900"  # amber = crop-damage area (girdawari / reported)
LIVES = "#e8695b"  # coral = human lives lost
REF = PAPER_DIM  # 1953-2010 worst-year reference (undated)
REF_WASH = "#161d16"  # faint wash above the worst-year line
_HALO = [withStroke(linewidth=2.2, foreground=INK)]

# 2025 max area affected on record (1953-2010), undated in the source
WORST_YEAR_HA = 2.79e6
WORST_YEAR_SPAN = "1953-2010"

# axis window: the dated record runs 2016 -> 2025
XMIN, XMAX = 2015.3, 2026.2


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _class_points(df, cls):
    """Dated (year, value_ha, period) points for an AREA class, undated dropped."""
    m = milestones(df, cls)
    pts = []
    for _, r in m.iterrows():
        yr = period_to_year(r["period"])
        if np.isnan(yr):
            continue  # the undated worst-year span is drawn separately
        pts.append((yr, float(r["value_ha"]), r["period"]))
    return sorted(pts)


def _lives_points(df):
    m = milestones(df, "lives")
    pts = []
    for _, r in m.iterrows():
        yr = period_to_year(r["period"])
        if np.isnan(yr):
            continue
        pts.append((yr, float(r["value"]), r["period"]))
    return sorted(pts)


def _style(ax):
    ax.set_facecolor(INK)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(LINE2)
    ax.tick_params(colors=PAPER_FAINT, labelsize=8)


# --------------------------------------------------------------------------- #
# area panel (log ha) -- the two area classes + the undated worst-year band
# --------------------------------------------------------------------------- #
def _area_panel(ax, df):
    ax.set_yscale("log")
    ax.set_ylim(700, 4.2e6)
    ax.set_xlim(XMIN, XMAX)
    ax.grid(axis="both", color=LINE2, lw=0.55, alpha=0.45, zorder=0)

    # --- 1953-2010 worst year: undated reference band + line -----------------
    ax.axhspan(WORST_YEAR_HA, 4.2e6, color=REF_WASH, zorder=0)
    ax.axhline(WORST_YEAR_HA, color=REF, lw=1.2, ls=(0, (6, 3)), zorder=2)
    ax.annotate(
        "Punjab worst flood year, 1953–2010:  2.79 Mha (2.79 million ha)\n"
        "year not published in source — not placed on the time axis",
        xy=(XMIN + 0.15, WORST_YEAR_HA), xytext=(XMIN + 0.15, WORST_YEAR_HA * 1.28),
        fontsize=7.6, color=PAPER, va="bottom", ha="left", path_effects=_HALO, zorder=6,
    )

    # --- flooded area (cyan circles) -----------------------------------------
    fl = _class_points(df, "flooded_area")
    for yr, val, _period in fl:
        is25 = yr >= 2025
        ax.plot(
            yr, val, "o", color=FLOODED, ms=9 if is25 else 6.5,
            mec=PAPER if is25 else INK, mew=1.4 if is25 else 1.1, zorder=7,
        )

    # --- crop-damage area (amber squares) ------------------------------------
    cr = _class_points(df, "crop_damage_area")
    for yr, val, _period in cr:
        is25 = yr >= 2025
        ax.plot(
            yr, val, "s", color=CROP, ms=9 if is25 else 6.5,
            mec=PAPER if is25 else INK, mew=1.4 if is25 else 1.1, zorder=7,
        )

    # --- 2025 as TWO separately-labelled points (never merged) ---------------
    sar = next(v for y, v, _ in fl if y >= 2025)
    gird = next(v for y, v, _ in cr if y >= 2025)
    ax.annotate(
        f"2025 SAR single-pass\n{sar:,.0f} ha mapped extent",
        xy=(2025, sar), xytext=(2022.05, sar * 0.30),
        fontsize=7.8, color=FLOODED, va="center", ha="left", path_effects=_HALO,
        arrowprops=dict(arrowstyle="-|>", color=FLOODED, lw=1.0,
                        connectionstyle="arc3,rad=0.15", shrinkB=7), zorder=8,
    )
    ax.annotate(
        f"2025 girdawari cumulative\n1.985 lakh ha ({gird:,.0f} ha)",
        xy=(2025, gird), xytext=(2021.7, gird * 3.4),
        fontsize=7.8, color=CROP, va="center", ha="left", path_effects=_HALO,
        arrowprops=dict(arrowstyle="-|>", color=CROP, lw=1.0,
                        connectionstyle="arc3,rad=-0.15", shrinkB=7), zorder=8,
    )

    # y ticks in human area units
    ax.set_yticks([1e3, 1e4, 1e5, 1e6])
    ax.set_yticklabels(["1,000 ha", "10,000 ha", "1 lakh ha", "10 lakh ha (1 Mha)"])
    ax.set_ylabel("area  (hectares, log scale)", fontsize=8.5, color=PAPER_DIM)
    _style(ax)

    handles = [
        Line2D([0], [0], color=FLOODED, marker="o", ms=6.5, mec=INK, lw=0,
               label="flooded area — mapped / “area affected” (ha)"),
        Line2D([0], [0], color=CROP, marker="s", ms=6.5, mec=INK, lw=0,
               label="crop-damage area — girdawari / reported (ha)"),
        Line2D([0], [0], color=REF, lw=1.2, ls=(0, (6, 3)),
               label="1953–2010 worst year, 2.79 Mha (year not published)"),
        Line2D([0], [0], color=PAPER, marker="o", ms=8, mec=PAPER, mew=1.4, lw=0,
               label="2025 (haloed) — two separate points, never merged"),
    ]
    ax.legend(handles=handles, loc="lower right", fontsize=7.0, frameon=False,
              labelcolor=PAPER, labelspacing=0.35, handlelength=1.6,
              borderaxespad=0.5)


# --------------------------------------------------------------------------- #
# lives panel (count, linear)
# --------------------------------------------------------------------------- #
def _lives_panel(ax, df):
    ax.set_xlim(XMIN, XMAX)
    ax.grid(axis="y", color=LINE2, lw=0.55, alpha=0.45, zorder=0)
    pts = _lives_points(df)
    ymax = max(v for _, v, _ in pts)
    ax.set_ylim(0, ymax * 1.35)

    for yr, val, _period in pts:
        is25 = yr >= 2025
        # thin discrete stem (a milestone marker, NOT an interpolation line)
        ax.plot([yr, yr], [0, val], color=LIVES, lw=1.0, alpha=0.45, zorder=2)
        ax.plot(
            yr, val, "D", color=LIVES, ms=8.5 if is25 else 6.0,
            mec=PAPER if is25 else INK, mew=1.4 if is25 else 1.0, zorder=6,
        )
        ax.annotate(f"{val:.0f}", xy=(yr, val), xytext=(0, 6),
                    textcoords="offset points", ha="center", va="bottom",
                    fontsize=7.6, color=PAPER if is25 else PAPER_DIM,
                    weight="bold" if is25 else "normal", path_effects=_HALO, zorder=7)

    ax.annotate(
        "single-digit to low-double-digit\nbaseline, 2018–21",
        xy=(2019.5, 20), xytext=(2016.0, 46),
        fontsize=7.4, color=PAPER_DIM, va="center", ha="left", path_effects=_HALO,
        arrowprops=dict(arrowstyle="-", color=PAPER_FAINT, lw=0.8,
                        connectionstyle="arc3,rad=0.2"), zorder=6,
    )
    ax.set_ylabel("lives lost  (count)", fontsize=8.5, color=PAPER_DIM)
    ax.set_xticks(range(2016, 2026))
    ax.tick_params(axis="x", labelsize=8)
    _style(ax)


# --------------------------------------------------------------------------- #
# figure assembly
# --------------------------------------------------------------------------- #
def build_figure(df):
    fig = plt.figure(figsize=(9.6, 9.4), dpi=200)
    fig.patch.set_facecolor(INK)
    gs = fig.add_gridspec(2, 1, height_ratios=[2.35, 1.0], hspace=0.16,
                          left=0.115, right=0.975, top=0.845, bottom=0.150)
    ax_area = fig.add_subplot(gs[0])
    ax_lives = fig.add_subplot(gs[1])
    _area_panel(ax_area, df)
    _lives_panel(ax_lives, df)
    plt.setp(ax_area.get_xticklabels(), visible=False)

    # ---- title block -------------------------------------------------------
    fig.text(0.115, 0.967, "Punjab floods in 70-year context",
             fontsize=16.5, weight="bold", color=PAPER, ha="left", va="top")
    fig.text(0.115, 0.933,
             "2025 against the public damage record — a sparse milestone "
             "timeline (no continuous public annual series exists)",
             fontsize=9.6, color=PAPER_DIM, ha="left", va="top")
    fig.text(0.115, 0.911,
             "distinct markers per metric class; the classes (flooded area, "
             "crop-damage area, lives) are never conflated",
             fontsize=9.0, color=PAPER_FAINT, ha="left", va="top", style="italic")

    # ---- caption block (framing rules ON the figure) -----------------------
    fig.add_artist(Line2D([0.115, 0.975], [0.122, 0.122], color=LINE2, lw=1.0))
    fig.text(0.115, 0.108,
             "The contrast: a placid 2016–21 baseline (flooded area ≤ 0.023 Mha; "
             "crops ≤ 1.51 lakh ha; single-digit-to-low-double-digit lives) → "
             "2025 at 1.985 lakh ha girdawari crop damage and 55 lives lost. 2025 is the "
             "outlier the recurrence atlas said to prepare for — this figure gives "
             "context, it does not replace the official record.",
             fontsize=7.6, color=PAPER, ha="left", va="top", wrap=True)
    fig.text(0.115, 0.055,
             "Sources — data.gov.in (GODL): max area 1953–2010 "
             "(uuid c00fd02a…, Rajya Sabha); flood damage 2016–2018 (f03e92a4…, "
             "MoEFCC); hydromet damages 2018–19→2021–22 (082dd5e0…). 2025: this "
             "repo — SAR statewide Tier-A 105,183 ha (VERIFICATION-LOG); Special "
             "Girdawari 198,524 ha and 55 deaths (official_relief_2025.csv).",
             fontsize=6.6, color=PAPER_DIM, ha="left", va="top", wrap=True)
    fig.text(0.115, 0.022,
             "The 2.79 Mha worst-year maximum is drawn as an undated reference: the "
             "source table publishes no year, so none is attributed (1988 is widely "
             "cited as Punjab’s worst pre-2025 flood but no citable source pins the "
             "2.79 Mha figure to a year). See docs/notes/flood-history.md.",
             fontsize=6.6, color=PAPER_FAINT, ha="left", va="top", wrap=True)
    return fig


# --------------------------------------------------------------------------- #
def _print_verdict(df):
    print("\n================ PUNJAB FLOOD DAMAGE — 70-YEAR MILESTONES ================")
    print(f"consolidated record: {IN_CSV.relative_to(ROOT)}  ({len(df)} rows)")
    for cls in ("flooded_area", "crop_damage_area", "lives", "houses"):
        m = milestones(df, cls)
        if not len(m):
            continue
        parts = []
        for _, r in m.iterrows():
            if cls in ("flooded_area", "crop_damage_area"):
                parts.append(f"{r['period']}={r['value_ha']:,.0f} ha")
            else:
                parts.append(f"{r['period']}={r['value']:.0f}")
        print(f"  {cls:17s}: " + " | ".join(parts))
    print("  worst year 1953–2010: 2.79 Mha (2,790,000 ha) — year NOT published in source")
    print("===========================================================================")


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    df = load_history(IN_CSV)
    OUT_PNG.parent.mkdir(parents=True, exist_ok=True)
    fig = build_figure(df)
    fig.savefig(OUT_PNG, dpi=200, facecolor=INK, bbox_inches="tight",
                pil_kwargs={"optimize": True})
    plt.close(fig)
    print(f"wrote {OUT_PNG.relative_to(ROOT)}  ({OUT_PNG.stat().st_size / 1024:.0f} KB)")
    _print_verdict(df)
    return df


if __name__ == "__main__":
    main()
