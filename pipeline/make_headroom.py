#!/usr/bin/env python
# pipeline/make_headroom.py
"""Render ``atlas/headroom_2025.png`` + ``data/headroom_2025.csv`` — the dam
head*room* deficit analysis: how much LESS pre-positioned empty storage the three
BBMB dams held on the eve of the 2025 flood than the median of their own
2015-2024 practice would have provided on the same day-of-season.

This is **arithmetic on storage curves**, not a hydraulic simulation, and it is
framed with hard discipline (see ``docs/notes/headroom.md``): never "avoidable";
the +10σ rain is the primary cause; dams have legitimate reasons to fill early;
SANDRP's qualitative version is the prior work; and the BBMB→CWC reporting gap
(series ends 11 Jul 2025) limits post-Jul precision to cited supplement points.

Per dam it computes, for each date 2025-08-01 → 2025-08-25:
    storage_2025_bcm − median_curve_bcm  =  headroom deficit (BCM and % points),
where the 2025 storage is the CWC daily API (to 11 Jul) spliced to cited
BBMB/press points (Ranjit Sagar's level-only window via the dam's own hypsometric
rating), interpolated with NO extrapolation. It then does the Aug 26-27 release-
surge buffer arithmetic (``deficit ÷ peak-release`` = days of buffer).

Deterministic: same committed CSVs in → same CSV + byte-stable PNG out. No network.

Run:  python pipeline/make_headroom.py
      python -m pytest tests/test_headroom.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import matplotlib  # noqa: E402

matplotlib.use("Agg")

import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402
from matplotlib.patheffects import withStroke  # noqa: E402

from sailaab import headroom as hr  # noqa: E402
from sailaab.causal import LIVE_CAPACITY_BCM  # noqa: E402
from sailaab.reservoirs import normalize  # noqa: E402

DATA = ROOT / "data"
OUT_CSV = DATA / "headroom_2025.csv"
OUT_PNG = ROOT / "atlas" / "headroom_2025.png"

# --- analysis anchors -------------------------------------------------------
PRIOR_YEARS = range(2015, 2025)  # 2015-2024 decade baseline
DAMS = [("Bhakra", "Sutlej"), ("Pong", "Beas"), ("Ranjit Sagar", "Ravi")]
START = pd.Timestamp("2025-06-01")
END = pd.Timestamp("2025-09-30")
DEFICIT_DATES = pd.date_range("2025-08-01", "2025-08-25", freq="D")
HEADLINE = pd.Timestamp("2025-08-25")  # eve of the Aug 26-27 surge
GAP0, GAP1 = pd.Timestamp("2025-07-11"), pd.Timestamp("2025-08-01")  # reporting gap
SURGE0, SURGE1 = pd.Timestamp("2025-08-26"), pd.Timestamp("2025-08-27")  # release surge

# documented peak releases (cusecs), docs/notes/reservoirs.md
PEAK_RELEASE_CUSECS = {"Bhakra": 85_000, "Pong": 100_000, "Ranjit Sagar": 173_000}
SUTLEJ_CUMULATIVE_CUSECS = 260_000  # basin-scale context only

# --- dark house palette (matches pipeline/duration_2025.py) -----------------
INK, INK2, LINE2 = "#0a1014", "#0e161d", "#28394a"
PAPER, PAPER_DIM, PAPER_FAINT = "#e9e4d6", "#9aa5a4", "#5c6a70"
BAND = "#1f8a84"  # cyan IQR fill = the 2015-24 "normal" envelope
MEDIAN = "#63e6d5"  # bright cyan = decade-median practice
Y2025 = "#f2a900"  # amber = 2025 (the anomaly against the norm)
GAP_WASH = "#121a20"  # reporting-gap band
SURGE_WASH = "#4a3410"  # Aug 26-27 release-surge band
_HALO = [withStroke(linewidth=2.2, foreground=INK)]


# --------------------------------------------------------------------------- #
# data assembly
# --------------------------------------------------------------------------- #
def load():
    daily = normalize(pd.read_csv(DATA / "reservoirs_2015_2025.csv"))
    supp = normalize(pd.read_csv(DATA / "reservoirs_2025_flood_supplement.csv"))
    return daily, supp


def cited_2025_points(daily, supp, dam) -> pd.DataFrame:
    """All dated 2025 storage(-equivalent) points for ``dam``, tagged by basis:
    dense CWC API storage (to 11 Jul), then cited BBMB/press storage / %-full, the
    Pong FRL crossing (level > FRL → at live capacity), and Ranjit Sagar's
    level-only points mapped through its own 2015-24 hypsometric rating.
    """
    cap = LIVE_CAPACITY_BCM[dam]
    pts = []
    api = daily[(daily["dam"] == dam) & (daily["date"].dt.year == 2025)].dropna(
        subset=["storage_value"]
    )
    for _, r in api.iterrows():
        pts.append((r["date"], r["storage_value"], "api"))

    for _, r in supp[supp["dam"] == dam].sort_values("date").iterrows():
        if pd.notna(r["storage_value"]):
            pts.append((r["date"], r["storage_value"], "press_storage"))
        elif pd.notna(r["pct_capacity"]):
            pts.append((r["date"], r["pct_capacity"] / 100.0 * cap, "press_pct"))

    if dam == "Pong":
        # 26 Aug level 1393 ft > FRL 1390 ft → at/above brim: use live capacity
        # as a conservative at-FRL storage anchor for the Aug 18→26 interpolation.
        pts.append((pd.Timestamp("2025-08-26"), cap, "frl_crossing"))
    if dam == "Ranjit Sagar":
        levels = supp[supp["dam"] == dam].dropna(subset=["level_m"])
        for _, r in levels.iterrows():
            est = float(
                hr.rating_level_to_storage(
                    daily, dam, [r["level_m"]], prior_years=PRIOR_YEARS
                )[0]
            )
            pts.append((r["date"], est, "hypsometric"))

    df = pd.DataFrame(pts, columns=["date", "storage_bcm", "basis"]).sort_values("date")
    return df.drop_duplicates("date", keep="first").reset_index(drop=True)


def _basis_for(date, cited) -> str:
    """Provenance tag for one interpolated/measured date."""
    hit = cited[cited["date"] == date]
    if len(hit):
        return hit.iloc[0]["basis"]
    before = cited[cited["date"] < date].tail(1)
    after = cited[cited["date"] > date].head(1)
    if len(before) == 0 or len(after) == 0:
        return "none"
    gap = (after.iloc[0]["date"] - before.iloc[0]["date"]).days
    ends = {before.iloc[0]["basis"], after.iloc[0]["basis"]}
    if "hypsometric" in ends:
        tag = "interp_hyps"
    elif "frl_crossing" in ends:
        tag = "interp_frl"
    else:
        tag = "interp"
    return tag + ("_wide" if gap > 21 else "")


def build_deficit_table(daily, supp):
    """The per-dam Aug 1-25 headroom-deficit rows + the median curves for the fig."""
    rows = []
    curves = {}
    for dam, _river in DAMS:
        cap = LIVE_CAPACITY_BCM[dam]
        curve = hr.median_fill_curve(daily, dam, PRIOR_YEARS, as_pct_of=cap)
        curves[dam] = curve
        cited = cited_2025_points(daily, supp, dam)
        st = hr.interp_no_extrap(cited["date"], cited["storage_bcm"], DEFICIT_DATES)
        doys = hr.season_day(DEFICIT_DATES)
        med = curve.loc[doys, "q50"].to_numpy()
        dbcm, dpct = hr.headroom_deficit(st, med, cap)
        for i, dt in enumerate(DEFICIT_DATES):
            rows.append(
                {
                    "dam": dam,
                    "date": dt.strftime("%Y-%m-%d"),
                    "storage_2025_bcm": None if np.isnan(st[i]) else round(float(st[i]), 4),
                    "median_curve_bcm": None if np.isnan(med[i]) else round(float(med[i]), 4),
                    "deficit_bcm": None if np.isnan(dbcm[i]) else round(float(dbcm[i]), 4),
                    "deficit_pctpts": None if np.isnan(dpct[i]) else round(float(dpct[i]), 2),
                    "basis": _basis_for(dt, cited),
                }
            )
    table = pd.DataFrame(rows)
    return table, curves


# --------------------------------------------------------------------------- #
# buffer arithmetic (Aug 26-27 release surge)
# --------------------------------------------------------------------------- #
def buffer_arithmetic(table):
    """Per dam at 2025-08-25: deficit, and the days of the documented peak release
    that the missing headroom would have buffered had 2025 tracked the median."""
    out = {}
    for dam, _river in DAMS:
        row = table[(table["dam"] == dam) & (table["date"] == HEADLINE.strftime("%Y-%m-%d"))]
        d_bcm = row["deficit_bcm"].iloc[0]
        d_pct = row["deficit_pctpts"].iloc[0]
        peak = PEAK_RELEASE_CUSECS[dam]
        rate = hr.cusecs_to_bcm_per_day(peak)
        days = hr.absorbable_days(d_bcm, peak) if d_bcm is not None else float("nan")
        sub = table[table["dam"] == dam]["deficit_bcm"].dropna()
        subp = table[table["dam"] == dam]["deficit_pctpts"].dropna()
        out[dam] = {
            "deficit_bcm": d_bcm,
            "deficit_pctpts": d_pct,
            "peak_cusecs": peak,
            "peak_bcm_per_day": rate,
            "absorbable_days": days,
            "mean_deficit_bcm": float(sub.mean()),
            "mean_deficit_pctpts": float(subp.mean()),
        }
    return out


# --------------------------------------------------------------------------- #
# figure (dark house style, 3 small-multiple panels)
# --------------------------------------------------------------------------- #
def _smooth(series, win=7):
    return series.rolling(win, center=True, min_periods=1).mean()


def _style(ax):
    ax.set_facecolor(INK)
    ax.grid(axis="y", color=LINE2, lw=0.6, alpha=0.55, zorder=0)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(LINE2)
    ax.tick_params(colors=PAPER_FAINT, labelsize=8)
    ax.margins(x=0)


def _panel(ax, dam, river, daily, supp, curve, table):
    cap = LIVE_CAPACITY_BCM[dam]
    dates_full = pd.date_range(START, END, freq="D")
    doys = hr.season_day(dates_full)
    p25 = curve.loc[doys, "q25_pct"].to_numpy()
    p50 = curve.loc[doys, "q50_pct"].to_numpy()
    p75 = curve.loc[doys, "q75_pct"].to_numpy()
    ny = curve.loc[doys, "n_years"].to_numpy()

    # reporting-gap + surge washes
    ax.axvspan(GAP0, GAP1, color=GAP_WASH, zorder=0)
    ax.axvspan(SURGE0, SURGE1, color=SURGE_WASH, zorder=0)
    # FRL / brim
    ax.axhline(100, color=PAPER_FAINT, lw=1.0, ls=(0, (6, 3)), zorder=2)

    # 2015-24 IQR band (raw) + smoothed median guide
    ax.fill_between(dates_full, p25, p75, color=BAND, alpha=0.22, lw=0, zorder=1)
    ax.plot(dates_full, p50, color=MEDIAN, lw=0.8, alpha=0.35, zorder=3)
    ax.plot(dates_full, _smooth(pd.Series(p50)).to_numpy(), color=MEDIAN, lw=2.0,
            solid_capstyle="round", zorder=4)

    # 2025: solid API (to 11 Jul) + dashed cited/estimated points after
    cited = cited_2025_points(daily, supp, dam)
    api = cited[cited["basis"] == "api"]
    ax.plot(api["date"], api["storage_bcm"] / cap * 100.0, color=Y2025, lw=2.0,
            solid_capstyle="round", zorder=6)
    post = cited[cited["date"] >= GAP0].sort_values("date")
    ax.plot(post["date"], post["storage_bcm"] / cap * 100.0, color=Y2025, lw=1.7,
            ls=(0, (5, 2)), zorder=6)
    non_api = cited[cited["basis"] != "api"]
    ax.plot(non_api["date"], non_api["storage_bcm"] / cap * 100.0, "o", color=Y2025,
            ms=5.5, mec=INK, mew=1.2, zorder=7)

    # Aug 25 deficit bracket (raw median vs 2025)
    trow = table[(table["dam"] == dam) & (table["date"] == HEADLINE.strftime("%Y-%m-%d"))].iloc[0]
    if trow["deficit_bcm"] is not None:
        s_pct = trow["storage_2025_bcm"] / cap * 100.0
        m_pct = trow["median_curve_bcm"] / cap * 100.0
        ax.annotate("", xy=(HEADLINE, s_pct), xytext=(HEADLINE, m_pct),
                    arrowprops=dict(arrowstyle="<->", color=PAPER, lw=1.4), zorder=8)
        sign = "+" if trow["deficit_bcm"] >= 0 else "−"
        ax.annotate(
            f"25 Aug deficit\n{sign}{abs(trow['deficit_bcm']):.2f} BCM "
            f"({sign}{abs(trow['deficit_pctpts']):.0f} pts)",
            xy=(HEADLINE, (s_pct + m_pct) / 2),
            xytext=(pd.Timestamp("2025-07-16"), min(96, max(s_pct, m_pct) + 6)),
            fontsize=7.6, color=PAPER, va="center", ha="left", path_effects=_HALO,
            arrowprops=dict(arrowstyle="-|>", color=PAPER_DIM, lw=1.0,
                            connectionstyle="arc3,rad=-0.2", shrinkB=6), zorder=8,
        )

    ax.set_ylim(0, 108)
    ax.set_yticks([0, 25, 50, 75, 100])
    ax.set_ylabel("% live cap", fontsize=8.5, color=PAPER_DIM)
    ax.set_title(f"{dam}  ·  {river}", fontsize=11, color=PAPER, loc="left",
                 weight="bold", pad=4)
    ax.annotate(
        f"live cap {cap:.3f} BCM · median from {int(ny.min())}–{int(ny.max())} "
        f"prior yrs/day",
        xy=(0.995, 0.055), xycoords="axes fraction", fontsize=6.8, color=PAPER_FAINT,
        ha="right", va="bottom",
    )
    _style(ax)


def build_figure(daily, supp, curves, table, buf):
    fig = plt.figure(figsize=(9.6, 10.6), dpi=200)
    fig.patch.set_facecolor(INK)
    gs = fig.add_gridspec(3, 1, hspace=0.22, left=0.075, right=0.975, top=0.845,
                          bottom=0.140)
    axes = [fig.add_subplot(gs[i]) for i in range(3)]
    for ax, (dam, river) in zip(axes, DAMS):
        _panel(ax, dam, river, daily, supp, curves[dam], table)

    for ax in axes[:-1]:
        plt.setp(ax.get_xticklabels(), visible=False)
    axb = axes[-1]
    axb.set_xlim(START, END)
    axb.xaxis.set_major_locator(mdates.MonthLocator())
    axb.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
    axb.xaxis.set_minor_locator(mdates.MonthLocator(bymonthday=15))
    for ax in axes:
        ax.set_xlim(START, END)

    # ---- title block -------------------------------------------------------
    fig.text(0.075, 0.967, "Dam headroom on the eve of the 2025 flood",
             fontsize=16.5, weight="bold", color=PAPER, ha="left", va="top")
    fig.text(0.075, 0.933,
             "The management component — 2025 storage (amber) vs each dam's own "
             "2015–24 median filling curve (cyan, IQR shaded)",
             fontsize=9.6, color=PAPER_DIM, ha="left", va="top")
    fig.text(0.075, 0.911,
             "% of live capacity by day-of-season, Jun 1 → Sep 30",
             fontsize=9.0, color=PAPER_FAINT, ha="left", va="top", style="italic")

    # legend
    handles = [
        Line2D([0], [0], color=Y2025, lw=2.2, label="2025 storage (solid = CWC API to 11 Jul)"),
        Line2D([0], [0], color=Y2025, lw=1.7, ls=(0, (5, 2)), marker="o", ms=5,
               mec=INK, label="2025 cited BBMB/press · Ranjit Sagar hypsometric"),
        Line2D([0], [0], color=MEDIAN, lw=2.2, label="2015–24 median (7-day smoothed)"),
        Patch(facecolor=BAND, alpha=0.30, label="2015–24 IQR (p25–p75, raw)"),
        Line2D([0], [0], color=PAPER_FAINT, lw=1.0, ls=(0, (6, 3)), label="FRL / brim (100%)"),
    ]
    axes[0].legend(handles=handles, loc="upper left", fontsize=7.2, frameon=False,
                   labelcolor=PAPER, labelspacing=0.3, handlelength=1.9,
                   borderaxespad=0.4, ncol=1)

    # ---- caption block (framing rules ON the figure) -----------------------
    fig.add_artist(Line2D([0.075, 0.975], [0.112, 0.112], color=LINE2, lw=1.0))
    b = buf
    cap_line = (
        f"On 25 Aug 2025 (eve of the Aug 26–27 release surge): Pong held "
        f"{b['Pong']['deficit_bcm']:+.2f} BCM ({b['Pong']['deficit_pctpts']:+.0f} pts) and Ranjit Sagar "
        f"{b['Ranjit Sagar']['deficit_bcm']:+.2f} BCM ({b['Ranjit Sagar']['deficit_pctpts']:+.0f} pts) MORE than "
        f"their decade-median fill — both above their normal IQR; Bhakra "
        f"{b['Bhakra']['deficit_bcm']:+.2f} BCM ({b['Bhakra']['deficit_pctpts']:+.0f} pts) tracked its median. "
        f"That missing headroom equals only ~{b['Ranjit Sagar']['absorbable_days']:.0f}–"
        f"{b['Pong']['absorbable_days']:.0f} days of each dam's peak documented release."
    )
    fig.text(0.075, 0.100, cap_line, fontsize=8.0, color=PAPER, ha="left", va="top",
             wrap=True)
    fig.text(0.075, 0.055,
             "NOT a claim the flood was avoidable — the record +10σ upstream rain is the "
             "primary cause (atlas/causal_2025.png). Dams fill early for legitimate "
             "irrigation/power and forecast-uncertainty reasons; this only measures the gap "
             "to the decade-median practice. Qualitative prior work: SANDRP (2025-09-07).",
             fontsize=7.0, color=PAPER_DIM, ha="left", va="top", wrap=True)
    fig.text(0.075, 0.020,
             "Data — reservoirs: CWC via data.gov.in (daily, to 11 Jul 2025); Aug–Sep window "
             "BBMB via press (SANDRP, The Tribune, Down To Earth, Babushahi). Ranjit Sagar Aug "
             "storage = hypsometric estimate from its own 2015–24 level↔storage rating. "
             "Deficit = 2025 − raw daily median; see docs/notes/headroom.md.",
             fontsize=6.6, color=PAPER_FAINT, ha="left", va="top", wrap=True)
    return fig


# --------------------------------------------------------------------------- #
def _print_verdict(buf, table):
    print("\n================ 2025 HEADROOM DEFICIT (vs 2015-24 median) ================")
    for dam, _r in DAMS:
        b = buf[dam]
        print(
            f"{dam:13s}  Aug25 deficit {b['deficit_bcm']:+.3f} BCM / {b['deficit_pctpts']:+5.1f} pts"
            f"   | Aug1-25 mean {b['mean_deficit_bcm']:+.3f} BCM / {b['mean_deficit_pctpts']:+5.1f} pts"
        )
        print(
            f"               buffer: {b['deficit_bcm']:+.3f} BCM ÷ {b['peak_cusecs']:,} cusecs "
            f"({b['peak_bcm_per_day']:.4f} BCM/day) = {b['absorbable_days']:.2f} days of peak release"
        )
    tot = sum(buf[d]["deficit_bcm"] for d, _ in DAMS)
    print(f"\ntotal Aug-25 pre-positioning deficit across the three dams: {tot:+.3f} BCM")
    print("===========================================================================")


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    daily, supp = load()
    table, curves = build_deficit_table(daily, supp)
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(OUT_CSV, index=False)
    print(f"wrote {OUT_CSV.relative_to(ROOT)}  ({len(table)} rows)")

    buf = buffer_arithmetic(table)
    OUT_PNG.parent.mkdir(parents=True, exist_ok=True)
    fig = build_figure(daily, supp, curves, table, buf)
    fig.savefig(OUT_PNG, dpi=200, facecolor=INK, bbox_inches="tight",
                pil_kwargs={"optimize": True})
    plt.close(fig)
    print(f"wrote {OUT_PNG.relative_to(ROOT)}  ({OUT_PNG.stat().st_size / 1024:.0f} KB)")

    _print_verdict(buf, table)
    return table, buf


if __name__ == "__main__":
    main()
