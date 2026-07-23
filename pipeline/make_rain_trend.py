#!/usr/bin/env python
# pipeline/make_rain_trend.py
"""Long-record monsoon rain-loading TREND panel: the honest climate statistic.

Reads the committed 1961-2025 daily box means, computes the three pre-registered
extreme-rain indices per box per monsoon (R95cnt, RX5day, PRCPTOT; see
``docs/notes/rain-trend.md``), runs the pre-registered trend test
(Mann-Kendall with von Storch lag-1 pre-whitening + Theil-Sen slope, alpha=0.05),
and renders one house-style small-multiple per index with the Sen slope line, the
significance verdict, and the 2025 point highlighted. Also reports 2025's
empirical rank + Weibull return period for RX5day (and the other indices).

Deterministic: same daily CSV in -> same CSVs + byte-stable PNG out. No network.

Outputs (committed):
    data/rain_indices_1961_2025.csv    year, box, r95cnt, rx5day, prcptot
    data/rain_trend_results.csv        index, box, n, r1, sen_slope_per_decade,
                                       mk_p_raw, mk_p, prewhitened, verdict
    atlas/rain_trend.png

Run:  python pipeline/make_rain_trend.py
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
import pandas as pd  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patheffects import withStroke  # noqa: E402

from sailaab import climatology as cl  # noqa: E402
from sailaab import figstyle  # noqa: E402

DATA = ROOT / "data"
DAILY_CSV = DATA / "rain_daily_boxes_1961_2025.csv"
INDICES_CSV = DATA / "rain_indices_1961_2025.csv"
RESULTS_CSV = DATA / "rain_trend_results.csv"
OUT = ROOT / "atlas" / "rain_trend.png"

BASE_PERIOD = range(1961, 1991)  # 1961-1990 WMO normal (fixed R95 base)
ALPHA = 0.05

# box column -> (display name, hue): same blue/orange pairing as the causal fig
BOXES = [
    ("upstream_mm", "upstream", "Upstream (Sutlej–Beas–Ravi)", "#2a78d6"),
    ("punjab_mm", "punjab", "Punjab plains", "#eb6834"),
]
INDICES = [
    ("r95cnt", "R95cnt", "Days ≥ 1961–90 95th-pct wet-day threshold", "days"),
    ("rx5day", "RX5day", "Max 5-day monsoon accumulation", "mm"),
    ("prcptot", "PRCPTOT", "Total monsoon rainfall (Jun–Sep)", "mm"),
]

# --- house palette (matches make_causal_figure.py) --------------------------
INK, INK2, MUTED = "#0b0b0b", "#52514e", "#898781"
GRID, AXIS = "#e7e6e0", "#c3c2b7"
SIG_WASH = "#dfeadb"  # faint green tint behind a significant panel
NS_WASH = "#f1f0ea"  # faint neutral tint behind a non-significant panel
HL = "#111111"  # 2025 highlight ring

figstyle.apply()
plt.rcParams.update(
    {
        # generic family (IBM Plex Sans is first in font.sans-serif via
        # figstyle.apply); any rendered glyph must exist in IBM Plex Sans, so the
        # footnote uses a spelled-out "ring" rather than a hollow-circle marker.
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
# compute
# --------------------------------------------------------------------------- #
def _years(daily: pd.DataFrame) -> list[int]:
    d = pd.to_datetime(daily["date"])
    counts = d[d.dt.month.isin([6, 7, 8, 9])].dt.year.value_counts()
    return sorted(int(y) for y, c in counts.items() if c >= 120)  # full monsoons


def _base_years(years: list[int]) -> tuple[list[int], str]:
    have = [y for y in BASE_PERIOD if y in years]
    if len(have) >= 25:
        return have, "1961-1990"
    base = years[:30]  # archive fell short of the 1961-90 base -> first 30 avail
    return base, f"{base[0]}-{base[-1]} (fallback base; 1961-90 unavailable)"


def build_indices(daily: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    years = _years(daily)
    base, base_label = _base_years(years)
    parts = []
    for col, box, *_ in BOXES:
        t = cl.annual_indices(daily, col, years, base)
        t.insert(1, "box", box)
        parts.append(t)
    idx = pd.concat(parts, ignore_index=True).sort_values(["box", "year"])
    idx["rx5day"] = idx["rx5day"].round(3)
    idx["prcptot"] = idx["prcptot"].round(3)
    return idx.reset_index(drop=True), base_label


def build_results(idx: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for key, short, *_ in INDICES:
        for _, box, _disp, _hue in BOXES:
            sub = idx[idx["box"] == box].sort_values("year")
            years = sub["year"].to_numpy(dtype=float)
            y = sub[key].to_numpy(dtype=float)
            mk = cl.mann_kendall_prewhitened(y)
            slope_dec = cl.sens_slope(y, years) * 10.0
            sig = mk["p"] < ALPHA
            direction = "increasing" if slope_dec > 0 else "decreasing"
            verdict = (
                f"significant {direction} trend" if sig else "no significant trend"
            )
            rows.append(
                {
                    "index": short,
                    "box": box,
                    "n": int(mk["n"]),
                    "r1": round(mk["r1"], 3),
                    "sen_slope_per_decade": round(slope_dec, 3),
                    "mk_p_raw": round(mk["p_raw"], 4),
                    "mk_p": round(mk["p"], 4),
                    "prewhitened": mk["prewhitened"],
                    "verdict": verdict,
                }
            )
    return pd.DataFrame(rows)


def context_2025(idx: pd.DataFrame) -> dict:
    """Empirical rank + Weibull return period of 2025 for each index/box."""
    out = {}
    for key, short, *_ in INDICES:
        for _, box, *_ in BOXES:
            sub = idx[idx["box"] == box]
            if 2025 not in set(sub["year"]):
                continue
            vals = sub[key].to_numpy(dtype=float)
            target = float(sub.loc[sub["year"] == 2025, key].iloc[0])
            out[(short, box)] = {
                **cl.empirical_return_period(vals, target),
                "value": target,
            }
    return out


# --------------------------------------------------------------------------- #
# plot
# --------------------------------------------------------------------------- #
def _style(ax):
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", color=GRID, lw=0.8, zorder=0)
    ax.set_axisbelow(True)
    ax.margins(x=0.01)
    ax.tick_params(labelfontfamily=figstyle.FONT_MONO)  # numeric ticks in mono


def _sen_line(ax, years, y, hue, sig):
    slope = cl.sens_slope(y, years.astype(float))
    intercept = np.median(y - slope * years)
    xs = np.array([years.min(), years.max()], dtype=float)
    ax.plot(
        xs,
        intercept + slope * xs,
        color=hue,
        lw=2.0 if sig else 1.5,
        ls="-" if sig else (0, (5, 2)),
        zorder=5,
        solid_capstyle="round",
    )


def build_figure(idx, results, ctx, base_label):
    years_all = np.array(sorted(idx["year"].unique()), dtype=int)
    fig = plt.figure(figsize=(9.2, 10.2), dpi=200)
    gs = fig.add_gridspec(
        3, 1, hspace=0.28, left=0.095, right=0.965, top=0.865, bottom=0.128
    )
    res = results.set_index(["index", "box"])

    for row, (key, short, subtitle, unit) in enumerate(INDICES):
        ax = fig.add_subplot(gs[row])
        panel_sig = any(res.loc[(short, b), "mk_p"] < ALPHA for _, b, *_ in BOXES)
        ax.set_facecolor(SIG_WASH if panel_sig else NS_WASH)

        for col, box, disp, hue in BOXES:
            sub = idx[idx["box"] == box].sort_values("year")
            yr = sub["year"].to_numpy()
            y = sub[key].to_numpy(dtype=float)
            r = res.loc[(short, box)]
            sig = r["mk_p"] < ALPHA

            ax.plot(yr, y, color=hue, lw=0.9, alpha=0.45, zorder=2)
            ax.scatter(yr, y, s=13, color=hue, alpha=0.85, lw=0, zorder=3)
            _sen_line(ax, yr, y, hue, sig)

            # 2025 highlight ring
            if 2025 in set(yr):
                y25 = float(sub.loc[sub["year"] == 2025, key].iloc[0])
                ax.scatter(
                    [2025],
                    [y25],
                    s=95,
                    facecolors="none",
                    edgecolors=HL,
                    lw=1.7,
                    zorder=6,
                )

            # verdict line per box (slope/decade + p), coloured by hue
            tag = "sig." if sig else "n.s."
            _sl = r["sen_slope_per_decade"]
            sign = "+" if _sl > 0 else ("−" if _sl < 0 else "±")
            ax.annotate(
                f"{disp}: {sign}{abs(r['sen_slope_per_decade']):.2f} {unit}/decade  "
                f"(MK p={r['mk_p']:.2f}, {tag})",
                xy=(0.015, 0.955 - 0.10 * (0 if box == "upstream" else 1)),
                xycoords="axes fraction",
                fontsize=8.2,
                color=hue,
                weight="bold",
                ha="left",
                va="top",
                path_effects=_HALO,
                zorder=7,
            )

        ax.set_ylabel(unit, fontsize=9.5, color=INK2)
        ax.set_title(
            f"{short}: {subtitle}",
            fontsize=11,
            color=INK,
            loc="left",
            weight="bold",
            fontfamily=figstyle.FONT_DISPLAY,
            pad=6,
        )
        _style(ax)
        if row < len(INDICES) - 1:
            plt.setp(ax.get_xticklabels(), visible=False)

    # 2025 rank/return callout on the RX5day panel (row 1)
    axr = fig.axes[1]
    c_up = ctx.get(("RX5day", "upstream"))
    c_pj = ctx.get(("RX5day", "punjab"))
    if c_up and c_pj:
        axr.annotate(
            f"2025 RX5day rank {c_up['rank']}/{c_up['n']} upstream, "
            f"{c_pj['rank']}/{c_pj['n']} Punjab\n"
            f"(empirical return ≈ {c_up['return_period']:.0f} & "
            f"{c_pj['return_period']:.0f} yr)",
            xy=(0.985, 0.05),
            xycoords="axes fraction",
            fontsize=8.0,
            color=INK,
            ha="right",
            va="bottom",
            path_effects=_HALO,
            zorder=7,
        )

    # ---- title + caption ---------------------------------------------------
    fig.text(
        0.095,
        0.965,
        figstyle.clean("Is Punjab’s monsoon rain loading trending?"),
        fontsize=16,
        weight="bold",
        color=INK,
        ha="left",
        va="top",
        fontfamily=figstyle.FONT_DISPLAY,
    )
    fig.text(
        0.095,
        0.926,
        "Extreme-rain indices over the two flood-driving catchment boxes · "
        f"IMD 0.25° daily · {years_all.min()}–{years_all.max()} "
        f"({len(years_all)} monsoons)",
        fontsize=9.7,
        color=INK2,
        ha="left",
        va="top",
    )

    fig.add_artist(Line2D([0.095, 0.965], [0.096, 0.096], color=GRID, lw=1.0))
    verdict_bits = []
    for key, short, *_ in INDICES:
        v = []
        for _, box, *_ in BOXES:
            r = res.loc[(short, box)]
            _s = r["sen_slope_per_decade"]
            v.append(
                f"{box} {('+' if _s > 0 else '−' if _s < 0 else '±')}"
                f"{abs(_s):.2f}/dec "
                f"{'sig' if r['mk_p'] < ALPHA else 'n.s.'}"
            )
        verdict_bits.append(f"{short}: " + ", ".join(v))
    fig.text(
        0.095,
        0.080,
        "   ·   ".join(verdict_bits[:2]),
        fontsize=7.6,
        color=INK,
        ha="left",
        va="top",
    )
    fig.text(
        0.095,
        0.058,
        verdict_bits[2],
        fontsize=7.6,
        color=INK,
        ha="left",
        va="top",
    )
    fig.text(
        0.095,
        0.034,
        f"Mann–Kendall (von Storch lag-1 pre-whitening) + Theil–Sen slope, "
        f"α={ALPHA} · R95 base {base_label} · pre-registered indices only "
        "(docs/notes/rain-trend.md).",
        fontsize=6.8,
        color=MUTED,
        ha="left",
        va="top",
    )
    fig.text(
        0.095,
        0.015,
        "Sen line solid = significant, dashed = not · ring = 2025 · green panel = "
        "≥1 box significant, grey = none · boxes as in docs/notes/imd-rain.md.",
        fontsize=6.8,
        color=MUTED,
        ha="left",
        va="top",
    )
    return fig


# --------------------------------------------------------------------------- #
def main():
    try:  # keep console prints safe on Windows cp1252 terminals
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    daily = pd.read_csv(DAILY_CSV)
    idx, base_label = build_indices(daily)
    idx.to_csv(INDICES_CSV, index=False)
    print(f"wrote {INDICES_CSV.relative_to(ROOT)}  ({len(idx)} rows)")

    results = build_results(idx)
    results.to_csv(RESULTS_CSV, index=False)
    print(f"wrote {RESULTS_CSV.relative_to(ROOT)}  ({len(results)} rows)")

    ctx = context_2025(idx)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig = build_figure(idx, results, ctx, base_label)
    fig.savefig(OUT, dpi=200, facecolor="white")
    plt.close(fig)
    print(f"wrote {OUT.relative_to(ROOT)}  ({OUT.stat().st_size / 1024:.0f} KB)")

    # ---- console verdict block ---------------------------------------------
    print(f"\n=== TREND VERDICTS (base {base_label}, alpha={ALPHA}) ===")
    print(results.to_string(index=False))
    print("\n=== 2025 IN CONTEXT (empirical) ===")
    for (short, box), c in ctx.items():
        print(
            f"{short:8s} {box:9s} 2025={c['value']:.1f}  rank {c['rank']}/{c['n']}  "
            f"return~{c['return_period']:.0f} yr  (exceed p={c['exceedance_prob']:.3f})"
        )
    return results, ctx, base_label


if __name__ == "__main__":
    main()
