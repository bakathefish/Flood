"""Board figures from the committed verification outputs; nothing is recomputed here.

    python scripts/make_figures.py            # writes outputs/figures/*.png and *.svg

Three figures, each answering one question the verification report answers in a table:

1. ``event_2025_dhilwan``: what the routed forced release of Pong looked like against the
   department's observed peak on the Beas at Dhilwan, with and without the local term, and
   when the as-issued forecasts first flagged the spill.
2. ``flood_scale_ratios``: model inflow over the flood-scale figures the record holds
   (period means, dated days, season peaks), as ratios; volumes close, peak days low.
3. ``horizon_mae``: live 2026 one-day inflow error by lead, rain response against the
   persistence forecast it has to beat, one panel per dam.

Colour and mark rules follow the data-viz method (categorical slots in fixed order, thin
marks, hairline grid, text in ink tokens, a legend whenever there are two series).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
VER = ROOT / "outputs" / "verification"
REF = ROOT / "data" / "reference"
OUT = ROOT / "outputs" / "figures"

# palette (light surface); series slots in fixed order, never cycled
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
S1, S2, S3, S4 = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"  # blue, orange, aqua, yellow
BASELINE = "#b5b3ab"  # de-emphasis tone for the persistence reference, not a series slot

plt.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.sans-serif": ["Segoe UI", "DejaVu Sans", "Arial"],
        "font.size": 9,
        "axes.edgecolor": AXIS,
        "axes.linewidth": 0.8,
        "axes.labelcolor": INK2,
        "axes.titlecolor": INK,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "xtick.labelcolor": INK2,
        "ytick.labelcolor": INK2,
        "grid.color": GRID,
        "grid.linewidth": 0.8,
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "legend.frameon": False,
        "legend.fontsize": 8,
        "axes.formatter.use_locale": False,
        "svg.fonttype": "none",  # text stays text in the SVG (editable on the board, searchable)
    }
)


def _style(ax, *, ygrid=True):
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.tick_params(length=0)
    if ygrid:
        ax.grid(axis="y", linestyle="-")
        ax.set_axisbelow(True)


def _thousands(ax, axis="y"):
    fmt = matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}")
    (ax.yaxis if axis == "y" else ax.xaxis).set_major_formatter(fmt)


def _save(fig, name):
    OUT.mkdir(parents=True, exist_ok=True)
    for ext in ("png", "svg"):
        fig.savefig(OUT / f"{name}.{ext}", dpi=300, bbox_inches="tight", pad_inches=0.15)
    plt.close(fig)
    return OUT / f"{name}.png"


# --------------------------------------------------------------------------- #
# 1. the 2025 event at Dhilwan
# --------------------------------------------------------------------------- #
def event_2025_dhilwan(start="2025-08-10", end="2025-09-10"):
    with_local = pd.read_csv(VER / "routed_pong_perfect_prog_local.csv", parse_dates=["date"])
    without = pd.read_csv(VER / "routed_pong_perfect_prog.csv", parse_dates=["date"])
    peaks = pd.read_csv(REF / "wrd" / "peaks_dhilwan.csv", parse_dates=["date"])
    thr = pd.read_csv(REF / "wrd" / "thresholds.csv")
    res = json.loads((VER / "results.json").read_text())

    def cut(df):
        d = df[(df.station == "Dhilwan") & (df.date >= start) & (df.date <= end)]
        return d.set_index("date")["cusecs"]

    a, b = cut(with_local), cut(without)
    peak = peaks[peaks.year == 2025].iloc[0]
    t = thr[thr.station == "Dhilwan"].iloc[0]
    flags = {
        r["model"]: r["first_flag_issue_date"]
        for r in res["as_issued_events"]
        if r["year"] == 2025 and r["dam"] == "Pong"
    }

    fig, ax = plt.subplots(figsize=(7.2, 3.9))
    _style(ax)
    # WRD bands as hairlines with muted labels at the right edge
    for level, label in [
        (t.low_min, "Low"),
        (t.med_min, "Medium"),
        (t.high_min, "High"),
    ]:
        ax.axhline(level, color=GRID, lw=0.8, zorder=1)
        ax.annotate(
            f"WRD {label} from {level:,.0f}",
            xy=(1.0, level),
            xycoords=("axes fraction", "data"),
            xytext=(4, 2),
            textcoords="offset points",
            fontsize=7,
            color=MUTED,
            va="bottom",
            ha="left",
        )
    ax.plot(
        b.index,
        b.values,
        color=S2,
        lw=2,
        solid_joinstyle="round",
        label="Pong forced release, routed (spill + passage)",
    )
    ax.plot(
        a.index,
        a.values,
        color=S1,
        lw=2,
        solid_joinstyle="round",
        label="with the Beas local runoff added",
    )
    # observed peak
    ax.scatter(
        [peak.date],
        [peak.discharge_cusecs],
        s=42,
        color=INK,
        zorder=5,
        edgecolor=SURFACE,
        linewidth=1.5,
    )
    ax.annotate(
        f"WRD observed peak\n{peak.discharge_cusecs:,.0f} cusecs, {peak.date:%d %b}",
        xy=(peak.date, peak.discharge_cusecs),
        xytext=(10, 6),
        textcoords="offset points",
        fontsize=8,
        color=INK,
        ha="left",
        va="bottom",
    )
    # model peak label
    ipk = a.idxmax()
    ax.annotate(
        f"model peak {a.max():,.0f}\n{ipk:%d %b}, ratio {a.max() / peak.discharge_cusecs:.2f}",
        xy=(ipk, a.max()),
        xytext=(-8, 8),
        textcoords="offset points",
        fontsize=8,
        color=INK2,
        ha="right",
        va="bottom",
    )
    ax.set_ylim(0, max(a.max(), peak.discharge_cusecs) * 1.28)
    # first as-issued flags, labelled just under the top of the plot
    for model, name, dy in [("ecmwf_ifs025", "ECMWF", 0), ("gfs_seamless", "GFS", -11)]:
        if flags.get(model):
            d = pd.Timestamp(flags[model])
            ax.axvline(d, color=AXIS, lw=0.8, zorder=1)
            ax.annotate(
                f"first {name} flag {d:%d %b}",
                xy=(d, 0.99),
                xycoords=("data", "axes fraction"),
                xytext=(3, dy),
                textcoords="offset points",
                fontsize=7,
                color=MUTED,
                ha="left",
                va="top",
            )
    ax.set_ylabel("cusecs at Dhilwan")
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=5))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
    _thousands(ax)
    ax.set_title(
        "Beas at Dhilwan, August to September 2025: "
        "routed forced release against the observed peak",
        loc="left",
        fontsize=10,
        pad=10,
    )
    ax.legend(loc="upper left", bbox_to_anchor=(0.0, 0.92))
    fig.text(
        0.01,
        -0.03,
        "Release: Pong at full level under observed IMD rain, one day ahead, routed with the "
        "WRD travel times; a lower bound (no base flow, the operator not modelled). "
        "Peak: WRD Flood Preparedness Guidebook 2026. Flags: archived ECMWF and GFS "
        "forecasts, issue date of the first forced-spill flag.",
        fontsize=6.5,
        color=MUTED,
        ha="left",
        va="top",
        wrap=True,
    )
    return _save(fig, "event_2025_dhilwan")


# --------------------------------------------------------------------------- #
# 2. flood-scale ratios
# --------------------------------------------------------------------------- #
def flood_scale_ratios():
    df = pd.read_csv(VER / "flood_scale_inflow.csv")
    order = {"period mean": 0, "day": 1, "season peak": 2, "record day": 3}
    df["k"] = df.kind.map(order)
    df = df.sort_values(["k", "dam", "start"]).reset_index(drop=True)

    def label(r):
        s, e = pd.Timestamp(r.start), pd.Timestamp(r.end)
        if r.kind == "period mean":
            when = f"{s:%d %b} to {e:%d %b %Y}"
        elif r.kind == "season peak":
            when = f"{s:%Y} season, undated"
        else:
            when = f"{s:%d %b %Y}"
        return f"{r.dam}, {when}"

    df["label"] = df.apply(label, axis=1)
    groups = {
        0: "Period mean inflow (BBMB data released by the Public Action Committee)",
        1: "Single dated readings (press, BBMB sheets)",
        2: "Season peak inflow (Rajya Sabha reply)",
        3: "Record inflow day (Pong EAP)",
    }
    n = len(df)
    fig, ax = plt.subplots(figsize=(7.2, 0.34 * n + 1.6))
    _style(ax, ygrid=False)
    ax.grid(axis="x", linestyle="-")
    ax.set_axisbelow(True)
    ys = []
    y = 0
    prev = None
    ticklabels = []
    for _, r in df.iterrows():
        if r.k != prev:
            y += 1.1 if prev is not None else 0
            ax.text(
                0,
                y + 0.35,
                groups[r.k],
                fontsize=7.5,
                color=INK2,
                ha="left",
                va="center",
                transform=ax.get_yaxis_transform(),
            )
            y += 1.2
            prev = r.k
        ys.append(y)
        ticklabels.append(r.label)
        y += 1
    ax.barh(ys, df.ratio, height=0.62, color=S1, zorder=3)
    for yy, v in zip(ys, df.ratio, strict=True):
        ax.text(v + 0.03, yy, f"{v:.2f}", va="center", ha="left", fontsize=8, color=INK)
    ax.axvline(1.0, color=INK2, lw=0.8, zorder=4)
    ax.set_yticks(ys, ticklabels, fontsize=8)
    ax.invert_yaxis()
    ax.set_xlim(0, max(1.4, df.ratio.max() * 1.12))
    ax.set_xlabel("model inflow / reported inflow")
    ax.set_title(
        "Flood-scale check: model one-day inflow against the figures the public record holds",
        loc="left",
        fontsize=10,
        pad=10,
    )
    fig.text(
        0.01,
        -0.02,
        "Volumes over the flood periods sit near the reported means; the model's largest "
        "days fall short of the stated peaks. Reported peaks are readings at a moment and "
        "the model's day is a daily volume, so the peak ratios are lower bounds. "
        "Pong 24 Sep 2025 is a recession day where the base-flow stand-in runs high.",
        fontsize=6.5,
        color=MUTED,
        ha="left",
        va="top",
        wrap=True,
    )
    return _save(fig, "flood_scale_ratios")


# --------------------------------------------------------------------------- #
# 3. horizon MAE against persistence
# --------------------------------------------------------------------------- #
def horizon_mae():
    df = pd.read_csv(VER / "live_horizons.csv")
    series = [
        ("persistence", "persistence (yesterday's inflow)", BASELINE),
        ("observed rain", "rain response, observed rain", S1),
        ("ecmwf_ifs025", "rain response, ECMWF as issued", S2),
        ("gfs_seamless", "rain response, GFS as issued", S3),
        ("ecmwf_aifs025_single", "rain response, ECMWF AIFS as issued", S4),
    ]
    dams = ["Bhakra", "Pong"]
    fig, axes = plt.subplots(1, len(dams), figsize=(7.2, 3.4), sharex=True)
    for ax, dam in zip(axes, dams, strict=True):
        _style(ax)
        d = df[df.dam == dam]
        for key, name, color in series:
            s = d[d.rain == key].sort_values("horizon_days")
            lw = 2
            ax.plot(
                s.horizon_days,
                s.mae_cusecs,
                color=color,
                lw=lw,
                marker="o",
                ms=5,
                mec=SURFACE,
                mew=1.2,
                label=name,
                solid_joinstyle="round",
            )
        ax.set_title(dam, loc="left", fontsize=10)
        ax.set_xticks([1, 2, 3, 4, 5])
        ax.set_xlabel("days ahead")
        ax.set_ylim(0, d.mae_cusecs.max() * 1.15)
        _thousands(ax)
        n = int(d[d.horizon_days == 1].n.max())
        ax.text(
            0.99,
            0.02,
            f"n = {n} issue days at day 1",
            transform=ax.transAxes,
            fontsize=7,
            color=MUTED,
            ha="right",
            va="bottom",
        )
    axes[0].set_ylabel("mean absolute error, one-day inflow (cusecs)")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=2, bbox_to_anchor=(0.5, -0.12))
    fig.suptitle(
        "Live 2026 test: inflow error by lead, rain response against persistence",
        x=0.01,
        ha="left",
        fontsize=10,
    )
    fig.text(
        0.01,
        -0.2,
        "One-day inflow from the BBMB bulletin, verified against the bulletin's own reading; "
        "lower is better. The rain response must beat persistence to be worth issuing: it "
        "does at Pong at every lead, and at Bhakra from day 3 with ECMWF rain.",
        fontsize=6.5,
        color=MUTED,
        ha="left",
        va="top",
        wrap=True,
    )
    fig.tight_layout()
    return _save(fig, "horizon_mae")


ALL = {
    "event_2025_dhilwan": event_2025_dhilwan,
    "flood_scale_ratios": flood_scale_ratios,
    "horizon_mae": horizon_mae,
}


def main(names=None):
    for name in names or ALL:
        print(ALL[name]())


if __name__ == "__main__":
    main(sys.argv[1:] or None)
