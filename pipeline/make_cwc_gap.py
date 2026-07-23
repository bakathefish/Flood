#!/usr/bin/env python
# pipeline/make_cwc_gap.py
"""Render ``atlas/cwc_station_gap.png`` - the CWC flood-forecast station gap:
in the Central Water Commission's own state-wise table of *existing flood
forecasting stations* ("as on Jan 2018", data.gov.in OGD resource
``0ff82e77-8f0c-479c-823e-246c0b38a2c6``, GODL-India), **Punjab is absent** -
zero level-forecast stations, zero inflow-forecast stations - while the national
network counts 226 (166 level + 60 inflow) across 22 states/UTs.

The figure is a horizontal, stacked (level + inflow) bar ranking of the 22
listed states by total stations, with **Punjab pinned at 0** at the foot of the
ranking and annotated. The vintage caveat ("as on Jan 2018") is carried verbatim
on the caption, per ``docs/notes/cwc-gap.md``; the currency red-team (Punjab
still has no CWC FF station in CWC's current public lists) is cited there and
summarised on the figure as a muted secondary line.

Pure logic (load/validate/rank/absent-state->0) lives in ``sailaab.cwc``; this
driver does only IO and plotting. Deterministic: same committed CSV in -> same
byte-stable PNG out. No network.

Run:  python pipeline/make_cwc_gap.py
      python -m pytest tests/test_cwc.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import matplotlib  # noqa: E402

matplotlib.use("Agg")

import numpy as np  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402
from matplotlib.patheffects import withStroke  # noqa: E402

from sailaab import cwc  # noqa: E402
from sailaab import figstyle  # noqa: E402

DATA = ROOT / "data"
IN_CSV = DATA / "cwc_ff_stations_2018.csv"
OUT_PNG = ROOT / "atlas" / "cwc_station_gap.png"

# --- dark house palette (matches pipeline/make_headroom.py) ------------------
INK, INK2, LINE2 = "#0a1014", "#0e161d", "#28394a"
PAPER, PAPER_DIM, PAPER_FAINT = "#e9e4d6", "#9aa5a4", "#5c6a70"
LEVEL = "#63e6d5"  # bright cyan = level-forecast stations
INFLOW = "#1f8a84"  # deep cyan = inflow-forecast stations
PUNJAB = "#f2a900"  # amber = Punjab (the anomaly: zero)
PUNJAB_WASH = "#3a2a08"  # faint amber row wash behind Punjab
_HALO = [withStroke(linewidth=2.2, foreground=INK)]

# Punjab's listed neighbours, called out in the caption (from the same table).
NEIGHBOURS = ("Haryana", "Jammu and Kashmir", "Rajasthan")


def _style(ax):
    ax.set_facecolor(INK)
    ax.grid(axis="x", color=LINE2, lw=0.6, alpha=0.55, zorder=0)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(LINE2)
    ax.tick_params(colors=PAPER_FAINT, labelsize=8, length=0)
    ax.tick_params(axis="x", labelfontfamily=figstyle.FONT_MONO)  # numeric ticks


def build_figure(states_ranked, tot):
    """Stacked horizontal bar ranking (level + inflow) of the 22 listed states,
    with Punjab pinned at 0 at the foot of the ranking."""
    figstyle.apply()
    labels = states_ranked["state_ut"].tolist() + ["Punjab"]
    level = np.append(states_ranked["level_stations"].to_numpy(), 0)
    inflow = np.append(states_ranked["inflow_stations"].to_numpy(), 0)
    total = np.append(states_ranked["total_stations"].to_numpy(), 0)

    n = len(labels)  # 23 rows: 22 listed + Punjab
    y = np.arange(n)[::-1]  # row 0 (Uttar Pradesh, 40) at the top
    punjab_y = y[-1]  # Punjab is the last label -> bottom row

    fig = plt.figure(figsize=(9.6, 10.6), dpi=200)
    fig.patch.set_facecolor(INK)
    ax = fig.add_axes([0.195, 0.150, 0.775, 0.700])

    # faint amber wash behind the Punjab row
    ax.axhspan(punjab_y - 0.5, punjab_y + 0.5, color=PUNJAB_WASH, zorder=0)

    ax.barh(y, level, height=0.72, color=LEVEL, zorder=3, label="level-forecast")
    ax.barh(y, inflow, left=level, height=0.72, color=INFLOW, zorder=3,
            label="inflow-forecast")

    # total label at the end of each listed bar
    for yi, lv, inf, tt in zip(y, level, inflow, total):
        if tt > 0:
            ax.annotate(f"{tt}", xy=(tt, yi), xytext=(4, 0),
                        textcoords="offset points", va="center", ha="left",
                        fontsize=7.6, color=PAPER_DIM, zorder=4)

    # Punjab: a hard zero. Mark the origin and annotate.
    ax.plot([0], [punjab_y], marker="|", ms=13, mew=2.4, color=PUNJAB, zorder=6)
    ax.annotate(
        "PUNJAB: 0 stations\n(absent from the table)",
        xy=(0, punjab_y), xytext=(6.2, punjab_y + 1.15),
        fontsize=9.6, color=PUNJAB, va="center", ha="left", weight="bold",
        path_effects=_HALO,
        arrowprops=dict(arrowstyle="-|>", color=PUNJAB, lw=1.6,
                        connectionstyle="arc3,rad=0.18", shrinkA=2, shrinkB=6),
        zorder=7,
    )

    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=8.4)
    for tick, lab in zip(ax.get_yticklabels(), labels):
        if lab == "Punjab":
            tick.set_color(PUNJAB)
            tick.set_fontweight("bold")
        elif lab in NEIGHBOURS:
            tick.set_color(PAPER)
        else:
            tick.set_color(PAPER_DIM)
    ax.set_ylim(-0.9, n - 0.1)
    ax.set_xlim(0, 44)
    ax.set_xlabel("number of CWC flood-forecasting stations", fontsize=9,
                  color=PAPER_DIM, labelpad=6)
    _style(ax)

    # ---- title block -------------------------------------------------------
    fig.text(0.030, 0.972,
             figstyle.clean("Punjab is not on the map of India's flood-forecast network"),
             fontsize=16.5, weight="bold", color=PAPER, ha="left", va="top",
             fontfamily=figstyle.FONT_DISPLAY)
    fig.text(0.030, 0.940,
             f"CWC's own state-wise table lists {tot['total']} flood-forecasting "
             f"stations ({tot['level']} level + {tot['inflow']} inflow) across 22 "
             "states/UTs. Punjab has none",
             fontsize=9.8, color=PAPER_DIM, ha="left", va="top")
    fig.text(0.030, 0.918,
             "State-wise Existing Flood Forecasting Stations of the Central Water "
             'Commission, "as on Jan 2018"',
             fontsize=9.0, color=PAPER_FAINT, ha="left", va="top", style="italic")

    # legend: parked in the empty upper-right, clear of the long top bars
    handles = [
        Patch(facecolor=LEVEL, label="level-forecast stations (166)"),
        Patch(facecolor=INFLOW, label="inflow-forecast stations (60)"),
        Line2D([0], [0], marker="|", color=PUNJAB, lw=0, ms=11, mew=2.4,
               label="Punjab: zero (absent from the table)"),
    ]
    ax.legend(handles=handles, loc="upper right", bbox_to_anchor=(1.0, 0.82),
              fontsize=8.0, frameon=False, labelcolor=PAPER, labelspacing=0.5,
              borderaxespad=0.6, handlelength=1.4)

    # ---- caption block (vintage caveat ON the figure, verbatim) ------------
    fig.add_artist(Line2D([0.030, 0.970], [0.088, 0.088], color=LINE2, lw=1.0))
    fig.text(
        0.030, 0.078,
        'Vintage: this is CWC\'s network "as on Jan 2018", the newest state-wise '
        "table published on the OGD portal (sweep 2026-07-22). Punjab’s listed "
        "neighbours: Haryana 1, Jammu & Kashmir 3, Rajasthan 3; Punjab, 0.",
        fontsize=7.4, color=PAPER, ha="left", va="top", wrap=True,
    )
    fig.text(
        0.030, 0.040,
        "Still absent today: CWC's 2024 network (340 stations, 200 level + 140 "
        "inflow) lists no flood-forecasting, level or inflow site in Punjab "
        "(SANDRP North-India overviews 2019/2023; CWC 2024). "
        "Data: data.gov.in resource 0ff82e77-8f0c-479c-823e-246c0b38a2c6, GODL-India.",
        fontsize=6.6, color=PAPER_FAINT, ha="left", va="top", wrap=True,
    )
    return fig


def _print_verdict(states_ranked, tot):
    print("\n================ CWC FLOOD-FORECAST STATION GAP (as on Jan 2018) ================")
    print(f"national network : {tot['total']} stations = {tot['level']} level + {tot['inflow']} inflow")
    print(f"states/UTs listed: {len(states_ranked)}")
    print(f"Punjab           : {cwc.station_count(states_ranked, 'Punjab')} (absent from the table)")
    print(f"Haryana          : {cwc.station_count(states_ranked, 'Haryana')} "
          f"(level {cwc.station_count(states_ranked, 'Haryana', 'level')}, "
          f"inflow {cwc.station_count(states_ranked, 'Haryana', 'inflow')})")
    top = states_ranked.head(3)
    print("top 3 by total   : " + ", ".join(
        f"{r.state_ut} {r.total_stations}" for r in top.itertuples()))
    print("================================================================================")


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    df = cwc.load_stations(IN_CSV)
    tot = cwc.national_totals(df)
    ranked = cwc.state_totals(df)

    OUT_PNG.parent.mkdir(parents=True, exist_ok=True)
    fig = build_figure(ranked, tot)
    fig.savefig(OUT_PNG, dpi=200, facecolor=INK, pil_kwargs={"optimize": True})
    plt.close(fig)
    print(f"wrote {OUT_PNG.relative_to(ROOT)}  ({OUT_PNG.stat().st_size / 1024:.0f} KB)")

    _print_verdict(ranked, tot)
    return ranked, tot


if __name__ == "__main__":
    main()
