"""Render the verification outputs to Markdown. Every number in ``docs/verification.md``
comes from ``outputs/verification/`` through this module; nothing is typed by hand."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from punjabflood import constants as C

OUT = Path("outputs/verification")
KEY_PREDICTORS = (
    "Pong_max3d_bcm",
    "Pong_max5d_bcm",
    "Bhakra_max5d_bcm",
    "sutlej_beas_max3d_bcm",
    "sutlej_beas_max5d_bcm",
    "Pong_frac_aug15",
    "Bhakra_frac_aug15",
    "Pong_hei_pp_max",
    "Bhakra_hei_pp_max",
    "Pong_release_pp_max",
)


def _fmt(x, nd=2):
    if x is None or (isinstance(x, float) and x != x):
        return "n/a"
    if isinstance(x, int | float):
        return f"{x:+.{nd}f}" if nd and abs(x) < 10 else f"{x:,.0f}"
    return str(x)


def render_verification(out_dir: Path = OUT, params_path: Path | None = None) -> str:
    results = json.loads((out_dir / "results.json").read_text(encoding="utf-8"))
    peaks = pd.read_csv(out_dir / "peak_tests.csv")
    lines = [
        "# Verification report",
        "",
        f"Rendered from `{out_dir.as_posix()}/` (results.json, peak_tests.csv). "
        "Regenerate with `punjabflood verify` then `punjabflood report`.",
        "",
    ]

    if params_path and Path(params_path).exists():
        params = json.loads(Path(params_path).read_text(encoding="utf-8"))
        lines += [
            "## Inflow model parameters",
            "",
            "Fitted by non-negative least squares on day-to-day changes of measured storage "
            "(CWC table, or the CWC level through the dam's own rating) against lagged "
            "catchment rain volumes; spilling days and implausible jumps excluded. The "
            "recession is the lag-2 to lag-1 autocovariance ratio of the residuals, clipped to "
            "[0.50, 0.99]; a raw ratio above the clip means the residual drifts through the "
            "season (base flow and outflow both move slowly) rather than recessing, so the "
            "base is carried as nearly constant over the horizon.",
            "",
            "| dam | area used (km2) | runoff coefficient c | lag weights w0..w3 | recession (raw ratio) | gamma | R2 | RMSE (BCM/day) | days |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
        for dam, p in params.items():
            w = ", ".join(f"{x:.2f}" for x in p["w"])
            raw = p.get("rho_raw")
            raw_s = f"{raw:.3f}" if isinstance(raw, int | float) and raw == raw else "n/a"
            lines.append(
                f"| {dam} | {p['area_km2']:,.0f} | {p['c']:.3f} | {w} | {p['rho']:.3f} ({raw_s}) | "
                f"{p['gamma']:.2f} | {p['r2']:.3f} | {p['rmse_bcm']:.4f} | {p['n_days']} |"
            )
        lines.append("")

    lines += [
        "## Annual peak class, 38 years (1988 to 2025)",
        "",
        "For each WRD peak table, the predictors ranked by area under the ROC curve for the "
        "department's High class. Spearman rho is against the peak discharge itself; the "
        "Brier skill score compares leave-one-year-out logistic probabilities with the "
        "climatological base rate (positive is skill).",
        "",
    ]
    for table, g in peaks.groupby("table"):
        g = g[g["auroc_high"].notna()].sort_values("auroc_high", ascending=False)
        lines += [
            f"### {table}",
            "",
            "| predictor | years | High years | Spearman rho | AUROC (High) | Brier skill |",
            "|---|---|---|---|---|---|",
        ]
        shown = g.head(10)
        for _, r in shown.iterrows():
            lines.append(
                f"| {r['predictor']} | {int(r['n_years'])} | {int(r['n_high'])} | "
                f"{r['spearman_rho']:+.2f} | {r['auroc_high']:.2f} | {r['brier_skill_score']:+.2f} |"
            )
        lines.append("")
        key = g[g["predictor"].isin(KEY_PREDICTORS) & ~g["predictor"].isin(shown["predictor"])]
        if len(key):
            lines += [
                "Other pre-named predictors:",
                "",
                "| predictor | years | High years | Spearman rho | AUROC (High) | Brier skill |",
                "|---|---|---|---|---|---|",
            ]
            for _, r in key.iterrows():
                lines.append(
                    f"| {r['predictor']} | {int(r['n_years'])} | {int(r['n_high'])} | "
                    f"{r['spearman_rho']:+.2f} | {r['auroc_high']:.2f} | {r['brier_skill_score']:+.2f} |"
                )
            lines.append("")

    lines += [
        "## Event timing: routed perfect-prognosis release versus the dated Dhilwan peaks",
        "",
        "The forced release of a full Pong reservoir under the observed rain (one-day-ahead "
        "spill of each day's run, placed on the day it happens) is routed to Dhilwan with the "
        "Annexure Z travel times and compared with the department's dated peak. Only the "
        "spill is routed; turbine passage that also reaches the river is left out, so the "
        "predicted magnitude is a lower bound. The storage that drives the index comes from "
        "the public record, which is weekly in August 2023 and a handful of press points in "
        "August 2025; between measurements the reservoir is carried by the model's own water "
        "balance under the observed rain (one-day inflow less the non-spill passage), and "
        "every measurement re-anchors it.",
        "",
    ]
    et = results.get("event_timing") or []
    if et:
        lines += [
            "| year | predicted peak date | predicted peak (cusecs) | observed peak date | observed peak (cusecs) | lag (days) | magnitude ratio |",
            "|---|---|---|---|---|---|---|",
        ]
        for r in et:
            if "note" in r:
                lines.append(f"| {r['year']} | {r['note']} | | | | | |")
            else:
                lines.append(
                    f"| {r['year']} | {r['predicted_peak_date']} | {r['predicted_peak_cusecs']:,.0f} | "
                    f"{r['observed_peak_date']} | {r['observed_peak_cusecs']:,.0f} | {r['lag_days']:+d} | "
                    f"{r['magnitude_ratio']:.2f} |"
                )
    else:
        lines.append("Not run (no perfect-prognosis series).")
    lines.append("")
    pp_path = out_dir / "perfect_prog_event_pong.csv"
    if not pp_path.exists():
        pp_path = out_dir / "perfect_prog_hei_daily.csv"
    if pp_path.exists() and et:
        pp = pd.read_csv(pp_path, parse_dates=["date"])
        pp = pp[(pp["dam"] == "Pong") & (pp["date"].dt.month == 8)]
        if "storage_basis" in pp.columns and len(pp):
            lines += [
                "Storage basis of the Pong path in August of each event year (days):",
                "",
                "| year | measured (CWC) | CWC level through the rating | press report | carried by the model | interpolated |",
                "|---|---|---|---|---|---|",
            ]
            for r in et:
                g = pp[pp["date"].dt.year == int(r["year"])]["storage_basis"].fillna("")
                n = g.value_counts()
                lines.append(
                    f"| {r['year']} | {int(n.get('cwc', 0))} | {int(n.get('cwc_level', 0))} | "
                    f"{int(n.get('press', 0))} | {int(n.get('model', 0))} | {int(n.get('interp', 0))} |"
                )
            lines.append("")
        if "inflow_day1_cusecs" in pp.columns and len(pp):
            rec = C.PONG.max_observed_inflow_cusecs
            lines += [
                "Model one-day inflow on the wettest catchment day of each event August, against "
                "the largest inflow BBMB has recorded at Pong "
                f"({rec.value:,.0f} cusecs, {rec.note}; {rec.source}). The gap is the "
                "storage-change calibration's known weakness: on days when the dam releases "
                "heavily the storage change understates the inflow, and the largest daily "
                "changes are excluded as implausible, so the runoff coefficient is fitted on "
                "ordinary days and undershoots the extremes.",
                "",
                "| year | wettest day | catchment rain (mm) | model one-day inflow (cusecs) | ratio to the BBMB record |",
                "|---|---|---|---|---|",
            ]
            for r in et:
                g = pp[pp["date"].dt.year == int(r["year"])].dropna(subset=["rain_day1_mm"])
                if g.empty:
                    continue
                i = g["rain_day1_mm"].idxmax()
                day = (g.loc[i, "date"] + pd.Timedelta(days=1)).date().isoformat()
                q = float(g.loc[i, "inflow_day1_cusecs"])
                lines.append(
                    f"| {r['year']} | {day} | {g.loc[i, 'rain_day1_mm']:.0f} | {q:,.0f} | "
                    f"{q / rec.value:.2f} |"
                )
            lines.append("")

    qpf_path = out_dir / "qpf_skill.csv"
    if qpf_path.exists():
        qs = pd.read_csv(qpf_path)
        lines += [
            "## As-issued catchment QPF against observed catchment rain (2024 to 2026 seasons)",
            "",
            "Heavy day: 30 mm or more over the catchment in a day. Lead 0 is the archive's "
            "stitched shortest-lead series.",
            "",
            "| catchment | model | lead (days) | days | obs mean (mm) | bias | r | MAE (mm) | heavy days | hit rate | false-alarm ratio |",
            "|---|---|---|---|---|---|---|---|---|---|---|",
        ]
        for _, r in qs.sort_values(["catchment", "model", "lead_days"]).iterrows():
            lines.append(
                f"| {r['catchment']} | {r['model']} | {int(r['lead_days'])} | {int(r['n_days'])} | "
                f"{r['obs_mean_mm']:.1f} | {r['bias_pct']:+.0f}% | {r['pearson_r']:.2f} | {r['mae_mm']:.1f} | "
                f"{int(r['heavy_days_obs'])} | {_fmt(r['hit_rate']).replace('+', '')} | "
                f"{_fmt(r['false_alarm_ratio']).replace('+', '')} |"
            )
        lines.append("")

    lines += ["## Live 2026: one-day inflow prediction against the BBMB bulletins", ""]
    live = results.get("live_2026") or {}
    if live:
        lines += [
            "| dam | days | mean observed (cusecs) | mean predicted (cusecs) | bias | Pearson r | MAE (cusecs) |",
            "|---|---|---|---|---|---|---|",
        ]
        for dam, m in live.items():
            if "note" in m:
                lines.append(f"| {dam} | {m['n']} | {m['note']} | | | | |")
            else:
                lines.append(
                    f"| {dam} | {m['n']} | {m['mean_obs_cusecs']:,.0f} | {m['mean_pred_cusecs']:,.0f} | "
                    f"{m['bias_pct']:+.0f}% | {m['pearson_r']:+.2f} | {m['mae_cusecs']:,.0f} |"
                )
    else:
        lines.append("Not run.")
    lines.append("")
    return "\n".join(lines)
