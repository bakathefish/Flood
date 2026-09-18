"""Figures for the sprint brief, drawn from the committed verification outputs.

    python scripts/make_brief_figures.py      # writes outputs/figures/brief_*.png

Each figure answers one question the verification report answers in a table; nothing is
recomputed here. Colour and mark rules follow the data-viz method used in
``make_figures.py`` (categorical slots in fixed order, thin marks, hairline grid, ink text,
a legend whenever there are two series).

1. ``brief_live_2026``: live 2026 one-day inflow error, the rain response against the
   persistence forecast, with ERA5 as the observed rain and with IMD's real-time grid.
2. ``brief_realtime_rain``: the two in-season observed-rain records against IMD's final
   grid over the 2025 season, per catchment.
3. ``brief_qpf_models``: ECMWF IFS against ECMWF AIFS on the common rows, leads 1 to 3.
4. ``brief_rule_curve``: the Bhakra filling schedule against the dated gate openings.
5. ``brief_gauge_ratios``: routed Pong release over the press readings of the gauges.
6. ``brief_readings_db``: the press readings database by year and dam.
7. ``brief_weather_watch``: the weather watch of the latest product: what fell over each dam
   catchment, the ensemble's next days, and the level.
8. ``brief_qpf_blend``: the deterministic models combined against the primary one.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_figures import (  # noqa: E402
    AXIS,
    BASELINE,
    INK,
    INK2,
    MUTED,
    OUT,
    REF,
    S1,
    S2,
    S3,
    S4,
    SURFACE,
    VER,
    _save,
    _style,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from punjabflood import constants as C  # noqa: E402

RESULTS = json.load(open(VER / "results.json", encoding="utf-8"))
BEFORE_PATH = Path(sys.argv[1]) if len(sys.argv) > 1 else None


def live_2026():
    after = RESULTS["live_2026"]
    before = json.load(open(BEFORE_PATH, encoding="utf-8"))["live_2026"] if BEFORE_PATH else None
    dams = ["Bhakra", "Pong"]
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.9), sharey=False)
    for ax, dam in zip(axes, dams):
        _style(ax)
        labels, vals, cols = [], [], []
        labels.append("persistence\n(yesterday's inflow)")
        vals.append(after[dam]["persistence_mae_cusecs"])
        cols.append(BASELINE)
        if before:
            labels.append("rain response,\nERA5 as observed rain")
            vals.append(before[dam]["mae_cusecs"])
            cols.append(S2)
        labels.append("rain response,\nIMD real-time grid")
        vals.append(after[dam]["mae_cusecs"])
        cols.append(S1)
        x = range(len(vals))
        ax.bar(x, vals, color=cols, width=0.62)
        for i, v in enumerate(vals):
            ax.text(i, v, f"{v:,.0f}", ha="center", va="bottom", fontsize=8, color=INK2)
        ax.set_xticks(list(x))
        ax.set_xticklabels(labels, fontsize=7.5)
        ax.set_title(f"{dam}, n = {after[dam]['n']} bulletin days", fontsize=9, loc="left")
        ax.set_ylim(0, max(vals) * 1.25)
        ax.set_ylabel("one-day inflow MAE (cusecs)" if dam == "Bhakra" else "")
    fig.suptitle(
        "Live 2026: the rain response against the forecast it must beat",
        fontsize=10,
        y=1.04,
        x=0.01,
        ha="left",
        color=INK,
    )
    _save(fig, "brief_live_2026")


def realtime_rain():
    rows = pd.DataFrame(RESULTS["realtime_rain"]["rows"])
    rows = rows[rows["catchment"].isin(["Bhakra", "Pong", "Ranjit Sagar"])]
    cats = list(dict.fromkeys(rows["catchment"]))
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.8))
    for ax, (metric, label) in zip(
        axes,
        (
            ("pearson_r", "correlation with the final IMD grid"),
            ("bias_pct", "bias against the final grid (%)"),
        ),
    ):
        _style(ax)
        w = 0.36
        for j, (rec, col, name) in enumerate(
            (("era5", S2, "ERA5 (before)"), ("imd_rt", S1, "IMD real-time grid (now)"))
        ):
            sub = rows[rows["record"] == rec].set_index("catchment").reindex(cats)
            xs = [i + (j - 0.5) * w for i in range(len(cats))]
            ax.bar(xs, sub[metric], width=w, color=col, label=name)
            for x, v in zip(xs, sub[metric]):
                ax.text(
                    x,
                    v,
                    f"{v:.2f}" if metric == "pearson_r" else f"{v:+.0f}",
                    ha="center",
                    va="bottom" if v >= 0 else "top",
                    fontsize=7.5,
                    color=INK2,
                )
        ax.set_xticks(range(len(cats)))
        ax.set_xticklabels(cats)
        ax.set_title(label, fontsize=9, loc="left")
        if metric == "bias_pct":
            ax.axhline(0, color=AXIS, lw=0.8)
    axes[0].set_ylim(0, 1.15)
    axes[0].legend(
        frameon=False, fontsize=7.5, loc="upper center", bbox_to_anchor=(0.5, -0.14), ncol=2
    )
    n = int(rows["n_days"].max())
    fig.suptitle(
        f"In-season observed rain, 2025 monsoon ({n} days): what the model now sees",
        fontsize=10,
        y=1.04,
        x=0.01,
        ha="left",
        color=INK,
    )
    _save(fig, "brief_realtime_rain")


def qpf_models():
    q = RESULTS["qpf_model_comparison"]
    metrics = [
        ("hit_rate", "heavy-day hit rate"),
        ("false_alarm_ratio", "false-alarm ratio"),
        ("mae_mm", "MAE (mm/day)"),
        ("bias_pct", "bias (%)"),
    ]
    fig, axes = plt.subplots(1, 4, figsize=(7.4, 2.5))
    for ax, (m, label) in zip(axes, metrics):
        _style(ax)
        vals = [q["incumbent"][m], q["challenger"][m]]
        ax.bar([0, 1], vals, color=[S2, S1], width=0.6)
        for i, v in enumerate(vals):
            ax.text(
                i,
                v,
                f"{v:.2f}"
                if m in ("hit_rate", "false_alarm_ratio")
                else f"{v:+.0f}"
                if m == "bias_pct"
                else f"{v:.1f}",
                ha="center",
                va="bottom" if v >= 0 else "top",
                fontsize=8,
                color=INK2,
            )
        ax.set_xticks([0, 1])
        ax.set_xticklabels(["IFS", "AIFS"])
        ax.set_title(label, fontsize=9, loc="left")
        if m == "bias_pct":
            ax.axhline(0, color=AXIS, lw=0.8)
            ax.set_ylim(min(vals) * 1.4, 5)
        else:
            ax.set_ylim(0, max(vals) * 1.3)
    fig.suptitle(
        f"ECMWF IFS against ECMWF AIFS, leads 1 to 3, {q['n_common_days']:,} common catchment days, {q['incumbent']['heavy_days_obs']} heavy days",
        fontsize=10,
        y=1.04,
        x=0.01,
        ha="left",
        color=INK,
    )
    _save(fig, "brief_qpf_models")


def rule_curve():
    t = pd.read_csv(VER / "rule_curve_timing.csv")
    fig, ax = plt.subplots(figsize=(7.2, 3.0))
    _style(ax)
    days = pd.date_range("2025-07-15", "2025-09-10")
    sched = [C.rule_curve_level_ft("Bhakra", d) for d in days]
    ax.plot(days, sched, color=S1, lw=2, label="2019 filling schedule (level not to be exceeded)")
    ax.axhline(1680, color=BASELINE, lw=1.2, ls="--", label="full reservoir level 1,680 ft")
    ax.scatter(
        [pd.Timestamp("2025-08-19")],
        [1662.0],
        marker="_",
        s=180,
        color=S3,
        lw=2,
        zorder=4,
        label="guideline quoted for 19 Aug 2025 (1,662 ft)",
    )
    for i, r in t.iterrows():
        d = pd.Timestamp(r["opening_date"]).replace(year=2025)
        ax.scatter(
            [d],
            [r["opening_level_ft"]],
            color=S2,
            s=48,
            zorder=5,
            edgecolor=SURFACE,
            lw=1,
            label="gates opened (level then)" if i == 0 else None,
        )
        ax.annotate(
            f"{int(r['year'])}",
            (d, r["opening_level_ft"]),
            textcoords="offset points",
            xytext=(6, -10),
            fontsize=8,
            color=INK2,
        )
        f = pd.Timestamp(r["first_forced_rule"]).replace(year=2025)
        ax.scatter(
            [f],
            [C.rule_curve_level_ft("Bhakra", f)],
            marker="|",
            s=140,
            color=S2,
            lw=1.6,
            zorder=4,
            label="first day the schedule forces a release" if i == 0 else None,
        )
    ax.set_ylim(1645, 1684)
    ax.set_ylabel("Bhakra level (ft)")
    ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%d %b"))
    ax.set_title(
        "Bhakra: the operator's schedule against the dated gate openings (day of year, three seasons overlaid)",
        fontsize=9.5,
        loc="left",
        color=INK,
    )
    ax.legend(frameon=False, fontsize=7.5, loc="lower right")
    _save(fig, "brief_rule_curve")


def gauge_ratios():
    g = pd.read_csv(VER / "routed_vs_gauge_readings.csv")
    g["date"] = pd.to_datetime(g["date"])
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.9), sharey=True)
    cols = {"Dhilwan": S1, "Harike Head Works": S2, "Ferozepur Head Works": S3}
    for ax, yr in zip(axes, (2023, 2025)):
        _style(ax)
        sub = g[g["date"].dt.year == yr]
        for st, col in cols.items():
            s = sub[sub["station"] == st]
            ax.scatter(
                s["date"],
                s["observed_cusecs"] / 1000,
                color=col,
                s=34,
                label=f"{st}, quoted",
                zorder=4,
                edgecolor=SURFACE,
                lw=0.8,
            )
            ax.scatter(
                s["date"],
                s["routed_cusecs"] / 1000,
                color=col,
                s=34,
                marker="x",
                lw=1.2,
                label=f"{st}, routed Pong release",
                zorder=4,
            )
        ax.set_title(f"{yr}", fontsize=9, loc="left")
        ax.xaxis.set_major_locator(matplotlib.dates.DayLocator(interval=2 if yr == 2023 else 4))
        ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%d %b"))
        ax.tick_params(axis="x", labelsize=7.5)
    axes[0].set_ylabel("thousand cusecs")
    axes[0].set_ylim(0, None)
    h, l = axes[1].get_legend_handles_labels()
    axes[1].legend(
        h[:2] + h[2:3] + h[4:5],
        ["quoted by the press", "routed Pong release (spill plus passage)", "Harike", "Ferozepur"],
        frameon=False,
        fontsize=7,
        loc="upper left",
    )
    fig.suptitle(
        "The routed release on the days the press quoted the gauges (dot: quoted; cross: routed)",
        fontsize=10,
        y=1.04,
        x=0.01,
        ha="left",
        color=INK,
    )
    _save(fig, "brief_gauge_ratios")


def readings_db():
    p = pd.read_csv(REF / "bbmb" / "press_readings.csv")
    p["year"] = pd.to_datetime(p["date"]).dt.year
    lvl = p[p["level_ft"].notna()].groupby(["year", "dam"]).size().unstack(fill_value=0)
    inf = p[p["inflow_cusecs"].notna()].groupby(["year", "dam"]).size().unstack(fill_value=0)
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.8), sharey=False)
    cols = {"Bhakra": S1, "Pong": S2, "Ranjit Sagar": S3}
    for ax, (frame, label) in zip(
        axes, ((lvl, "dated level readings"), (inf, "dated inflow readings"))
    ):
        _style(ax)
        bottom = pd.Series(0, index=frame.index, dtype=float)
        for dam, col in cols.items():
            if dam not in frame:
                continue
            ax.bar(
                frame.index,
                frame[dam],
                bottom=bottom,
                color=col,
                width=0.7,
                label=dam,
                edgecolor=SURFACE,
                lw=0.8,
            )
            bottom = bottom + frame[dam]
        for yr, v in bottom.items():
            ax.text(yr, v, f"{int(v)}", ha="center", va="bottom", fontsize=7.5, color=INK2)
        ax.set_title(f"{label} ({int(frame.values.sum())} rows)", fontsize=9, loc="left")
        ax.set_xticks(list(frame.index))
        ax.set_xticklabels([str(y) for y in frame.index], rotation=45, fontsize=7.5)
    axes[0].legend(frameon=False, fontsize=7.5, loc="upper left")
    fig.suptitle(
        f"The press and bulletin readings database, {len(p)} dated rows from four sweeps",
        fontsize=10,
        y=1.04,
        x=0.01,
        ha="left",
        color=INK,
    )
    _save(fig, "brief_readings_db")


def weather_watch():
    fdir = OUT.parent / "forecast"
    latest = sorted(fdir.glob("20??-??-??.json"))[-1]
    prod = json.load(open(latest, encoding="utf-8"))
    watch = prod.get("weather") or {}
    dams = [d for d in ("Bhakra", "Pong", "Ranjit Sagar") if d in watch]
    fig, axes = plt.subplots(1, len(dams), figsize=(7.2, 2.9), sharey=True)
    for ax, dam in zip(axes, dams):
        _style(ax)
        e = watch[dam]
        obs_days = pd.to_datetime(e["observed"]["days"])
        ax.bar(
            obs_days,
            e["observed"]["rain_mm"],
            color=S1,
            width=0.7,
            label="observed (IMD real-time)",
        )
        fc_days = pd.to_datetime(e["forecast"]["dates"])
        ens = e.get("ensemble")
        if ens:
            ax.fill_between(
                fc_days, 0, ens["daily_q90_mm"], color=S2, alpha=0.18, lw=0, label="ensemble to q90"
            )
            ax.plot(
                fc_days,
                ens["daily_q50_mm"],
                color=S2,
                lw=2,
                marker="o",
                ms=4,
                label="ensemble median",
            )
        prim = e["forecast"]["by_model_mm"].get(e["primary_model"])
        if prim:
            ax.plot(fc_days, prim, color=S3, lw=1.6, ls="--", label="AIFS")
        snow = (e.get("temperature") or {}).get("snow_share_3day")
        pct = e["level_basis"]["three_day_percentile"]
        sub = f"{dam}: {e['level']}\n" + (f"next 3 days p{pct:.0f}" if pct is not None else "")
        if snow is not None:
            sub += f", snow share {snow:.2f}"
        ax.set_title(sub, fontsize=8.5, loc="left")
        ax.axvline(
            pd.Timestamp(prod["issue_date"]) + pd.Timedelta(hours=12), color=MUTED, lw=0.8, ls=":"
        )
        ax.xaxis.set_major_locator(matplotlib.dates.DayLocator(interval=3))
        ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%d %b"))
        ax.tick_params(axis="x", labelsize=7)
    axes[0].set_ylabel("catchment rain (mm/day)", fontsize=8)
    axes[0].legend(frameon=False, fontsize=7, loc="upper left")
    fig.suptitle(
        f"Weather watch issued {prod['issue_date']}: what fell, what the ensemble says, and the level",
        fontsize=10,
        y=1.04,
        x=0.01,
        ha="left",
        color=INK,
    )
    _save(fig, "brief_weather_watch")


def qpf_blend():
    bt = RESULTS.get("qpf_blend_test")
    if not bt or not bt.get("n_common_days"):
        return
    sc = bt["scores"]
    names = [bt["incumbent_model"]] + [m for m in bt["models"] if m != bt["incumbent_model"]]
    names += ["equal_mean", "inverse_mae_weighted_loso", "max_of_models"]
    labels = {
        "ecmwf_aifs025_single": "AIFS (primary)",
        "ecmwf_ifs025": "IFS",
        "gfs_seamless": "GFS",
        "equal_mean": "equal mean",
        "inverse_mae_weighted_loso": "inverse-MAE mean",
        "max_of_models": "max of models",
    }
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.6))
    for ax, (key, lab) in zip(
        axes, (("hit_rate", "heavy-day hit rate"), ("mae_mm", "MAE (mm/day)"))
    ):
        _style(ax)
        vals = [sc[n][key] for n in names]
        cols = [
            S1 if n == bt["incumbent_model"] else (S4 if n in bt["models"] else S2) for n in names
        ]
        ax.barh([labels[n] for n in names], vals, color=cols, height=0.6)
        for i, v in enumerate(vals):
            ax.text(v, i, f" {v:.2f}", va="center", fontsize=7.5, color=INK2)
        ax.set_title(lab, fontsize=9, loc="left")
        ax.set_xlim(0, max(vals) * 1.25)
        ax.invert_yaxis()
        ax.tick_params(axis="y", labelsize=7.5)
    fig.subplots_adjust(wspace=0.75)
    far = ", ".join(f"{labels[n]} {sc[n]['false_alarm_ratio']:.2f}" for n in names)
    fig.suptitle(
        f"Combining the models on {bt['n_common_days']:,} common rows: none passes the rule\n"
        f"false-alarm ratio: {far}",
        fontsize=9,
        y=1.06,
        x=0.01,
        ha="left",
        color=INK,
    )
    _save(fig, "brief_qpf_blend")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    live_2026()
    realtime_rain()
    qpf_models()
    rule_curve()
    gauge_ratios()
    readings_db()
    weather_watch()
    qpf_blend()
