"""Render the verification outputs to Markdown. Every number in ``docs/verification.md``
comes from ``outputs/verification/`` through this module; nothing is typed by hand."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from punjabflood import constants as C
from punjabflood.verify import EVENT_WINDOW

OUT = Path("outputs/verification")
ERA5_IMD_CSV = Path("data/reference/rain/era5_vs_imd_event_windows.csv")
FORECAST_DIR = Path("outputs/forecast")
CLASS_ORDER = {"low": 1, "medium": 2, "high": 3}
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


_MONTH = {7: "July", 8: "August", 9: "September", 6: "June", 10: "October"}


def _num(x, spec: str) -> str:
    """A number in the given format spec, or ``n/a`` when missing."""
    if x is None or (isinstance(x, float) and x != x):
        return "n/a"
    return format(float(x), spec)


def _rate(x) -> str:
    """A rate in [0, 1] to two decimals, n/a when undefined."""
    return "n/a" if x is None or x != x else f"{x:.2f}"


def rain_input_rows(era5_imd: pd.DataFrame) -> pd.DataFrame:
    """Per catchment and event window: IMD and ERA5 totals, their ratio, and ERA5 on the
    IMD-wettest day. ``era5_imd`` has columns event, date, catchment, era5_mm, imd_mm."""
    df = era5_imd.dropna(subset=["era5_mm", "imd_mm"]).copy()
    df["date"] = pd.to_datetime(df["date"])
    rows = []
    for (catchment, event), g in df.groupby(["catchment", "event"], sort=True):
        i = g["imd_mm"].idxmax()
        rows.append(
            {
                "catchment": catchment,
                "event": int(event),
                "window": f"{g['date'].min().date()} to {g['date'].max().date()}",
                "days": int(len(g)),
                "imd_mm": float(g["imd_mm"].sum()),
                "era5_mm": float(g["era5_mm"].sum()),
                "ratio": float(g["era5_mm"].sum() / g["imd_mm"].sum()),
                "imd_wettest_mm": float(g.loc[i, "imd_mm"]),
                "era5_on_wettest_mm": float(g.loc[i, "era5_mm"]),
            }
        )
    return pd.DataFrame(rows)


def prospective_rows(forecast_dir: Path) -> pd.DataFrame:
    """One row per issue date of the prospective record: the first record of each day
    (``<date>.json``; reruns saved beside it are not the record), with each dam's storage
    fraction and P(spillway forced) at the longest horizon, with and without the model
    error, and the worst WRD class at any control point."""
    rows = []
    for p in sorted(Path(forecast_dir).glob("????-??-??.json")):
        prod = json.loads(p.read_text(encoding="utf-8"))
        row: dict = {
            "issue_date": prod["issue_date"],
            "bulletin_as_on": (prod.get("bulletin") or {}).get("as_on_date"),
        }
        for dam, e in (prod.get("dams") or {}).items():
            ens = e.get("ensemble") or {}
            top = ens[str(max(int(k) for k in ens))] if ens else {}
            row[f"{dam}_storage_fraction"] = e.get("storage_fraction")
            row[f"{dam}_p_spill"] = top.get("p_exhaustion")
            row[f"{dam}_p_spill_model_error"] = top.get("p_exhaustion_model_error")
            row[f"{dam}_p_spill_flood_scale"] = top.get("p_exhaustion_flood_scale")
        worst_class, worst_station = None, None
        for r in prod.get("reaches") or []:
            c = r.get("peak_class")
            if c and CLASS_ORDER.get(c, 0) > CLASS_ORDER.get(worst_class or "", 0):
                worst_class, worst_station = c, r.get("station")
        row["worst_class"] = worst_class
        row["worst_station"] = worst_station
        rows.append(row)
    return pd.DataFrame(rows)


def _prospective_lines(forecast_dir: Path) -> list[str]:
    pr = prospective_rows(forecast_dir)
    lines = [
        "## Prospective record, 2026 season",
        "",
        "Issued daily from the committed inputs and the live BBMB bulletin; a record is never "
        "rewritten (`outputs/forecast/`). P(spillway forced) is at the five-day horizon.",
        "",
    ]
    if pr.empty:
        return lines + ["No record yet.", ""]
    dams = sorted({c[: -len("_p_spill")] for c in pr.columns if c.endswith("_p_spill")})
    n = len(pr)
    plural = "s" if n != 1 else ""
    parts = [f"{n} issue date{plural} from {pr['issue_date'].min()} to {pr['issue_date'].max()}."]
    for dam in dams:
        k = int((pr[f"{dam}_p_spill"].fillna(0) > 0).sum())
        parts.append(f"{dam}: P(spillway forced) above zero on {k} of {n} days.")
    classed = pr["worst_class"].notna()
    parts.append(f"Days with any control point at or above the WRD low band: {int(classed.sum())}.")
    lines += [" ".join(parts), ""]
    flagged = pr[classed | (pr[[f"{d}_p_spill" for d in dams]].fillna(0) > 0).any(axis=1)]
    if flagged.empty:
        lines += [
            "No day so far has put a forced spill or a classed arrival on the record.",
            "",
        ]
        return lines
    head = "| issue date | bulletin as on |"
    sep = "|---|---|"
    for dam in dams:
        head += f" {dam} storage | {dam} P(spill), QPF spread / with model error / with flood-scale error |"
        sep += "|---|---|"
    lines += [head + " worst class (station) |", sep + "---|"]
    for _, r in flagged.iterrows():
        cells = [str(r["issue_date"]), str(r["bulletin_as_on"])]
        for dam in dams:
            sf = r.get(f"{dam}_storage_fraction")
            p1 = r.get(f"{dam}_p_spill")
            p2 = r.get(f"{dam}_p_spill_model_error")
            p3 = r.get(f"{dam}_p_spill_flood_scale")
            cells.append("n/a" if sf is None or sf != sf else f"{sf * 100:.0f}%")
            cells.append(
                ("n/a" if p1 is None or p1 != p1 else f"{p1:.2f}")
                + " / "
                + ("n/a" if p2 is None or p2 != p2 else f"{p2:.2f}")
                + " / "
                + ("n/a" if p3 is None or p3 != p3 else f"{p3:.2f}")
            )
        wc = r["worst_class"]
        cells.append("none" if wc is None or wc != wc else f"{wc} ({r['worst_station']})")
        lines.append("| " + " | ".join(cells) + " |")
    lines.append("")
    return lines


def _ratio_range(s: pd.Series) -> str:
    lo, hi = float(s.min()), float(s.max())
    return f"{lo:.2f}" if abs(hi - lo) < 0.005 else f"{lo:.2f} to {hi:.2f}"


def reanchor_note(
    pp: pd.DataFrame,
    dam: str,
    year: int,
    first_flag: str,
    first_spill: str | None,
    window_end: tuple[int, int] = EVENT_WINDOW[1],
) -> str | None:
    """Why the model's own flags can run ahead of its spill, or come without one: from the
    first perfect-prognosis flag to the spill (with no spill, to the end of the event window),
    the largest downward re-anchor of the carried storage path at a measurement
    (``reanchor_gap_bcm`` from ``verify.carry_storage``)."""
    if "reanchor_gap_bcm" not in pp.columns or "dam" not in pp.columns:
        return None
    end = pd.Timestamp(first_spill) if first_spill else pd.Timestamp(year, *window_end)
    d = pd.to_datetime(pp["date"])
    g = pp[
        (pp["dam"] == dam) & (d >= pd.Timestamp(first_flag)) & (d <= end) & (d.dt.year == year)
    ].dropna(subset=["reanchor_gap_bcm"])
    g = g[g["reanchor_gap_bcm"] > 0]
    if g.empty:
        return None
    i = g["reanchor_gap_bcm"].idxmax()
    when = pd.Timestamp(g.loc[i, "date"]).date().isoformat()
    gap = f"{g.loc[i, 'reanchor_gap_bcm']:.2f} BCM"
    cause = (
        "the reservoir gained less than the water balance says, which is the dam passing more "
        "than its turbines, the inflow over-predicted, or both; the public record cannot "
        "separate them."
    )
    if first_spill:
        return (
            f"In {year} the {dam} run under observed rain flagged from {first_flag} while its "
            f"spill came on {first_spill}. Between the two, the measured storage of {when} "
            f"re-anchored the model's carried path downward by {gap}: {cause} The flags before "
            "that date were therefore calls of a spill unless water was released, which is what "
            "the index means, and the as-issued hits scored against them carry the same reading."
        )
    return (
        f"In {year} the {dam} run under observed rain flagged from {first_flag} and did not force "
        f"the spillway within the window (to {end.date().isoformat()}). After the first flag, the "
        f"measured storage of {when} re-anchored the model's carried path downward by {gap}: "
        f"{cause} The flags were therefore calls of a spill unless water was released, which is "
        "what the index means; the as-issued hits scored against them carry the same reading, "
        "and after the re-anchor the observed rain did not fill the reservoir before the window "
        "closed."
    )


def render_verification(
    out_dir: Path = OUT,
    params_path: Path | None = None,
    era5_imd_path: Path | None = ERA5_IMD_CSV,
    forecast_dir: Path | None = FORECAST_DIR,
) -> str:
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
            "| dam | area used (km2) | runoff coefficient c (dry) | c_wet per 100 mm antecedent | lag weights w0..w3 | recession (raw ratio) | gamma | R2 | RMSE (BCM/day) | days | wetness carrier |",
            "|---|---|---|---|---|---|---|---|---|---|---|",
        ]
        for dam, p in params.items():
            w = ", ".join(f"{x:.2f}" for x in p["w"])
            raw = p.get("rho_raw")
            raw_s = f"{raw:.3f}" if isinstance(raw, int | float) and raw == raw else "n/a"
            lines.append(
                f"| {dam} | {p['area_km2']:,.0f} | {p['c']:.3f} | {p.get('c_wet', 0.0):.3f} | {w} | "
                f"{p['rho']:.3f} ({raw_s}) | {p['gamma']:.2f} | {p['r2']:.3f} | {p['rmse_bcm']:.4f} | "
                f"{p['n_days']} | {p.get('wetness', 'api')} |"
            )
        lines.append(
            "The coefficient in force on a day is c plus c_wet times the previous five days' "
            "catchment rain over 100 mm, capped at 0.95, times one plus gamma times the "
            "ERA5-Land 0-7 cm soil-moisture anomaly (fractional, against a 31-day day-of-year "
            "climatology) where the wetness carrier includes soil moisture (`api+sm` or `sm`; "
            "gamma is zero under `api`)."
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
        "Annexure Z travel times and compared with the department's dated peak. The river "
        "release on a spill day is the spill plus the turbine passage less the Mukerian Hydel "
        "Channel's capacity (a full reservoir passes its inflow, so the turbines run); this is "
        "the lower bound on what the dam sends down the Beas, and the spill-only row below it "
        "is the lower bound of that. The rows with the local term add the runoff of the land "
        "between Pong and Dhilwan (the Beas local catchment, the HydroBASINS sub-basins that "
        "drain to Dhilwan below the dam) from its own IMD rain, with a dam's calibrated "
        "response transferred because no gauge exists to fit one on: Pong's response as the "
        "primary, Ranjit Sagar's (the lowest fitted coefficient) as the sensitivity; no base "
        "flow, so the term is a lower bound, and it arrives on the day it runs off. "
        "The storage that drives the index comes from the public record, which is weekly in "
        "August 2023 and a handful of press points in August 2025; between measurements the "
        "reservoir is carried by the model's own water balance under the observed rain "
        "(one-day inflow less the non-spill passage), and every measurement re-anchors it.",
        "",
    ]
    fcush = results.get("flood_cushion")
    if fcush:
        lines += [
            f"The rows marked flood cushion let {fcush['dam']} rise to {fcush['top_level_ft']:.0f} ft "
            f"({fcush['capacity_bcm']:.3f} BCM live, the design pair in the emergency action plan) "
            f"before the spillway must open, against {fcush['live_capacity_bcm']:.3f} BCM at the "
            "reduced FRL in the other rows; the storage above FRL is rated on the straight line "
            "between the two published points. The dam did rise into the cushion in both events, "
            "so the two settings bracket what BBMB did: the FRL bound fires early and high, the "
            "cushion bound late and low.",
            "",
        ]
    rc = results.get("rule_curve")
    rct = results.get("rule_curve_timing") or []
    if rc and rct:
        pts = "; ".join(
            f"{q['level_ft']:,.0f} ft up to {q['day']} {_MONTH[q['month']]}" for q in rc["points"]
        )
        lines += [
            f"### The operator's schedule at {rc['dam']}",
            "",
            f"The forced release above is the spillway's bound. BBMB opens the gates earlier, under "
            f"a filling schedule; the one in hand for {rc['dam']} ({rc['vintage']}) reads {pts}, "
            "a level holding up to its date and a straight line from the last point below FRL to "
            "the date FRL may be reached. The press quotes a guideline of "
            f"{rc['guideline_2025_08_19_ft']:,.0f} ft for 19 August 2025, below that line, so the "
            "schedule has been lowered since and this scenario is the 2019 rule. For each dated "
            "gate opening, the first day of the season on which each bound forces a release (the "
            "schedule bound counting a release above a tenth of the turbine passage), and its lag "
            "from the opening; the storage between measurements is the model's carry.",
            "",
            "| year | gates opened | level then (ft) | schedule level that day (ft) | first forced, FRL bound | lag (days) | first forced, schedule bound | lag (days) |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for r in rct:
            lines.append(
                f"| {r['year']} | {r['opening_date']} | {r['opening_level_ft']:,.2f} | "
                f"{_num(r.get('schedule_level_ft'), ',.1f')} | "
                f"{r.get('first_forced_frl') or 'none in the season'} | {_num(r.get('lag_frl_days'), '+.0f')} | "
                f"{r.get('first_forced_rule') or 'none in the season'} | {_num(r.get('lag_rule_days'), '+.0f')} |"
            )
        lines.append("")
    gc = results.get("gauge_readings_check") or []
    if gc:
        lines += [
            "### The routed release on the days the press quoted the gauges",
            "",
            "The dated press readings of the river gauges (moment readings, ambiguous rows left "
            "out) against the routed Pong release (spill plus passage, no local term) on the same "
            "day, as a ratio; a check of the hydrograph's level on dated days, not a fit.",
            "",
            "| station | date | quoted (cusecs) | routed (cusecs) | ratio |",
            "|---|---|---|---|---|",
        ]
        for r in gc:
            lines.append(
                f"| {r['station']} | {r['date']} | {r['observed_cusecs']:,.0f} | "
                f"{_num(r.get('routed_cusecs'), ',.0f')} | {_num(r.get('ratio'), '.2f')} |"
            )
        lines.append("")
    et = results.get("event_timing") or []
    et_cushion = results.get("event_timing_cushion") or []
    et_spill = results.get("event_timing_spill_only") or []
    et_local = results.get("event_timing_local") or []
    et_local_rs = results.get("event_timing_local_ranjit_sagar") or []
    if et:
        lines += [
            "| year | release routed | predicted peak date | predicted peak (cusecs) | observed peak date | observed peak (cusecs) | lag (days) | magnitude ratio |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for label, rows in (
            ("spill + passage", et),
            ("spill + passage, flood cushion", et_cushion),
            ("spill only", et_spill),
            ("spill + passage + local inflow, Pong response", et_local),
            ("spill + passage + local inflow, Ranjit Sagar response", et_local_rs),
        ):
            for r in rows:
                if r.get("note") and r["note"] == r["note"]:
                    lines.append(f"| {r['year']} | {label} | {r['note']} | | | | | |")
                else:
                    lines.append(
                        f"| {r['year']} | {label} | {r['predicted_peak_date']} | "
                        f"{r['predicted_peak_cusecs']:,.0f} | {r['observed_peak_date']} | "
                        f"{r['observed_peak_cusecs']:,.0f} | {int(r['lag_days']):+d} | "
                        f"{r['magnitude_ratio']:.2f} |"
                    )
    else:
        lines.append("Not run (no perfect-prognosis series).")
    lines.append("")
    ls = results.get("local_inflow_summary") or []
    if ls:
        lines += [
            "Local inflow at Dhilwan on the department's peak days (Pong response "
            "transferred; the routed dam release is the spill-plus-passage row above):",
            "",
            "| year | observed peak date | local inflow that day (cusecs) | share of the "
            "observed peak | largest within 3 days (cusecs, date) | routed dam release that "
            "day (cusecs) | dam plus local, ratio to observed |",
            "|---|---|---|---|---|---|---|",
        ]
        for r in ls:
            note = r.get("note")
            if note and note == note:
                lines.append(
                    f"| {r['year']} | {r.get('observed_peak_date', '')} | {note} | | | | |"
                )
                continue
            lines.append(
                f"| {r['year']} | {r['observed_peak_date']} | "
                f"{r['local_on_peak_day_cusecs']:,.0f} | {r['local_share_of_observed_peak']:.2f} | "
                f"{r['local_max_within_3_days_cusecs']:,.0f} ({r['local_max_date']}) | "
                f"{r['routed_dam_on_peak_day_cusecs']:,.0f} | {r['dam_plus_local_ratio']:.2f} |"
            )
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
    fs_path = out_dir / "flood_scale_inflow.csv"
    if fs_path.exists():
        fs = pd.read_csv(fs_path)
        lines += [
            "### Flood-scale inflow: the model against the figures the record holds",
            "",
            "The runoff coefficient is fitted on ordinary filling days (the storage-change "
            "relation), so what the model does at flood scale has to be checked against whatever "
            "flood-scale inflow the public record holds: BBMB's daily sheets where the Internet "
            "Archive kept them, dated press figures credited to the dam offices, the period means "
            "of BBMB inflow that the Public Action Committee compiled for August to early "
            "September 2025, the season's largest inflows as stated to the Rajya Sabha, and the "
            "record inflow in the Pong emergency action plan. Each is set against the model's "
            "one-day inflow under observed rain (the perfect-prognosis run with its base-flow "
            "stand-in) on the same day or days: a period mean against the model's mean over the "
            "same days, a season peak against the model's largest day of the same June to "
            "September. A period mean is a daily quantity like the model's; the season peaks, "
            "the dated press figures and the sheets' figures are readings at a time of day, so "
            "against a daily volume those ratios are lower bounds on the model's share of the "
            "day's mean. The full citations are in `data-sources.md` and the reference tables.",
            "",
            "| dam | figure | model days | reported (cusecs) | model (cusecs) | model / reported | source |",
            "|---|---|---|---|---|---|---|",
        ]
        for _, r in fs.iterrows():
            if r["kind"] == "period mean":
                what = f"mean, {r['start']} to {r['end']}"
            elif r["kind"] == "season peak":
                what = f"largest day of {str(r['start'])[:4]}"
            else:
                what = f"{r['kind']}, {r['start']}"
            model = "n/a" if r["model_cusecs"] != r["model_cusecs"] else f"{r['model_cusecs']:,.0f}"
            ratio = "n/a" if r["ratio"] != r["ratio"] else f"{r['ratio']:.2f}"
            lines.append(
                f"| {r['dam']} | {what} | {int(r['n_days'])} | {r['truth_cusecs']:,.0f} | {model} | "
                f"{ratio} | {r['source']} |"
            )
        days = fs[fs["kind"].isin(["day", "record day"])].dropna(subset=["ratio"])
        if len(days):
            parts = []
            for year, g in days.groupby(days["start"].str[:4]):
                parts.append(
                    f"{year}: {len(g)} dated figures, the model at {_ratio_range(g['ratio'])} of "
                    f"the reading, median {g['ratio'].median():.2f}"
                )
            lines += [
                "",
                "Dated figures by year (readings at a time of day against the model's daily "
                "volume; " + "; ".join(parts) + ").",
            ]
        fse = results.get("flood_scale_error")
        if fse and fse.get("n_periods"):
            sd = fse.get("log_sd")
            lines += [
                "",
                f"The spread of the model's log ratio to the {fse['n_periods']} period means "
                f"(sample standard deviation) is "
                f"{'not defined, fewer than three periods' if sd is None or sd != sd else f'{sd:.2f}'}"
                f", with a mean log ratio of {fse['log_bias']:+.2f}; the dated readings "
                f"({fse['n_dated_days']}) spread {_num(fse.get('dated_log_sd'), '.2f')}, wider "
                "because they are moments, not daily means. The product samples the period-mean "
                "spread as a multiplicative volume error on every inflow path for its third spill "
                "probability (an outer estimate), and does not apply the bias.",
            ]
        pm = fs[(fs["kind"] == "period mean") & (fs["n_days"] >= 10)].dropna(subset=["ratio"])
        pk = fs[fs["kind"] == "season peak"].dropna(subset=["ratio"])
        if len(pm) and len(pk):
            lines += [
                "",
                "Where the run covers at least 10 of a period's days, the model's mean is "
                f"{_ratio_range(pm['ratio'])} of the reported mean; its largest day of the season "
                f"is {_ratio_range(pk['ratio'])} of the stated peak. The flood's volume is close to "
                "right and its peak day is not: the model spreads the volume over more days than "
                "the river does, which is consistent with lag weights fitted on ordinary days.",
            ]
        lines.append("")

    iv = results.get("inflow_variants")
    if iv and iv.get("loso"):
        lines += [
            "### Response variants, tested out of sample",
            "",
            "Each variant is fitted on the same storage record beside the response in use and "
            "scored leave-one-season-out (each season by a fit on the others). Rain above the "
            "heavy-day threshold in a catchment day gets its own coefficient and lag weights "
            "(the threshold-excess variant). The soil-moisture variants change the carrier of "
            "catchment wetness: `api+sm` keeps the five-day rain index and adds the ERA5-Land "
            "0-7 cm soil-moisture anomaly through gamma; `sm` drops the rain index and keeps "
            "the anomaly alone (each fold's climatology leaves the held-out season out). The "
            "press inflow fit is the same response fitted on every dated press reading of "
            "inflow the sweeps found (moment readings, all seasons before the current one), "
            "expressed in the storage-change convention and scored on the storage record, "
            "where every season is out of sample for it (`seasons` counts them). The "
            "rule before any variant can replace the response the product uses: the held-out "
            "error may not rise at any dam, the season-peak ratios of the flood-scale table "
            "must rise, and the period means may not move further from the reported means "
            "than the baseline's worst one does. Heavy-day bias is observed minus predicted "
            "storage change, positive when heavy days are under-predicted.",
            "",
            "| dam | variant | seasons | days | held-out RMSE (BCM/day) | heavy days | heavy-day RMSE (BCM/day) | heavy-day bias (BCM/day) | c | c_wet | w | c_excess | w_excess | wetness | gamma |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
        ]
        for r in iv["loso"]:
            lines.append(
                f"| {r['dam']} | {r['variant']} | {int(r['n_seasons'])} | {int(r['n_days'])} | "
                f"{_num(r.get('rmse_bcm'), '.4f')} | {int(r['n_heavy_days'])} | "
                f"{_num(r.get('heavy_rmse_bcm'), '.4f')} | {_num(r.get('heavy_bias_bcm'), '+.4f')} | "
                f"{r['c']:.3f} | {r['c_wet']:.3f} | {r['w']} | {r['c_excess']:.3f} | {r['w_excess'] or 'none'} | "
                f"{r.get('wetness', 'api')} | {_num(r.get('gamma', 0.0), '.2f')} |"
            )
        lines += [
            "",
            "| variant | period means covered | worst deviation of a period mean from 1 | season-peak ratio, smallest | season-peak ratio, largest |",
            "|---|---|---|---|---|",
        ]
        for name, s in (iv.get("flood_scale") or {}).items():
            lines.append(
                f"| {name} | {int(s['n_period_means'])} | "
                f"{_num(s.get('period_mean_worst_deviation'), '.2f')} | "
                f"{_num(s.get('season_peak_ratio_min'), '.2f')} | "
                f"{_num(s.get('season_peak_ratio_max'), '.2f')} |"
            )
        verdicts = iv.get("verdicts") or ([iv["verdict"]] if iv.get("verdict") else [])
        for vd in verdicts:
            conds = [
                ("the held-out error does not rise at any dam", vd["loso_error_not_higher"]),
                ("the season peaks rise", vd["season_peaks_higher"]),
                ("the period means hold", vd["period_means_hold"]),
            ]
            said = "; ".join(f"{c} ({'passes' if ok else 'fails'})" for c, ok in conds)
            lines += [
                "",
                f"Verdict on '{vd['variant']}', {'adopted' if vd['adopt'] else 'not adopted'}. "
                f"Conditions: {said}.",
            ]
        lines.append("")

    ai = results.get("as_issued_events") or []
    if ai:
        lines += [
            "## As-issued hindcast: what the product would have said, each dam, 2024 to 2026",
            "",
            "For each issue date the recorded or model-carried storage and the rain forecast "
            "actually issued that day (archived lead 1 to 5 QPF, deterministic) go through the "
            "same water balance as the live product. A flagged day is an issue date whose "
            "forecast forces the spillway within five days. BBMB's gate log is not public, so "
            "the model's own run under observed rain (perfect prognosis) is the reference: a "
            "flag is a hit when that run also forces the spillway within five days of the same "
            "issue date, a false flag otherwise, and a perfect-prognosis flag without an "
            "as-issued flag is a miss. The first hit is the warning; the lead is counted from "
            "it to the model's first spill under observed rain and to the dated Dhilwan peak. "
            "The window is 1 August to 15 September.",
            "",
            "| year | dam | model | issue days | flagged (hits, false) | missed | first flag of any kind | first hit (issue date, spill on day) | earliest possible flag (observed rain) | first spill under observed rain | lead (days) | observed Dhilwan peak (Pong only) | lead (days) | largest forecast peak release (cusecs) | perfect-prognosis peak release (cusecs) |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
        ]

        def _d(x):
            return "none" if x is None or x != x else str(x)

        def _n(x):
            return "n/a" if x is None or x != x else f"{int(x):+d}"

        for r in ai:
            first_hit = (
                "none"
                if r.get("first_hit_issue_date") is None
                else f"{r['first_hit_issue_date']}, day {r['first_hit_spill_day']}"
            )
            lines.append(
                f"| {r['year']} | {r.get('dam') or 'Pong'} | {r['model']} | {r['issue_days']} | "
                f"{r['flagged_days']} ({r['hit_days']} hits, {r['false_flag_days']} false) | "
                f"{r['missed_days']} | {_d(r.get('first_flag_issue_date'))} | {first_hit} | "
                f"{_d(r.get('pp_first_flag_date'))} | {_d(r.get('pp_first_spill_date'))} | "
                f"{_n(r.get('lead_days_to_pp_spill'))} | {_d(r.get('observed_peak_date'))} | "
                f"{_n(r.get('lead_days_to_observed_peak'))} | "
                f"{r['max_forecast_peak_release_cusecs']:,.0f} | {r['pp_peak_day1_release_cusecs']:,.0f} |"
            )
        lines.append("")
        seen = set()
        for r in ai:
            dam = r.get("dam") or "Pong"
            key = (dam, r["year"], r.get("pp_first_flag_date"), r.get("pp_first_spill_date"))
            if key in seen or key[2] is None:
                continue
            seen.add(key)
            pp_ev = out_dir / f"perfect_prog_event_{dam.lower().replace(' ', '_')}.csv"
            if not pp_ev.exists():
                pp_ev = out_dir / "perfect_prog_hei_daily.csv"
            if not pp_ev.exists():
                continue
            note = reanchor_note(
                pd.read_csv(pp_ev, parse_dates=["date"]), dam, int(r["year"]), key[2], key[3]
            )
            if note:
                lines += [note, ""]

    if era5_imd_path is not None and Path(era5_imd_path).exists():
        ri = rain_input_rows(pd.read_csv(era5_imd_path))
        lines += [
            "## Rain input check: ERA5 against the IMD grid over the event windows",
            "",
            "ERA5 (0.25 degree reanalysis, through Open-Meteo) is the rain record the product "
            "uses for the current season, and the forecast models it ingests share its "
            "resolution and physics over these mountain catchments. The IMD gridded analysis "
            "is the observed record the model is calibrated on. A reanalysis that misses the "
            "rain of an event says the forecasts will too; the ratio column is the size of "
            "that miss over each event window.",
            "",
            "| catchment | event | window | days | IMD total (mm) | ERA5 total (mm) | ERA5 / IMD | IMD wettest day (mm) | ERA5 that day (mm) |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
        for _, r in ri.iterrows():
            lines.append(
                f"| {r['catchment']} | {r['event']} | {r['window']} | {r['days']} | "
                f"{r['imd_mm']:.0f} | {r['era5_mm']:.0f} | {r['ratio']:.2f} | "
                f"{r['imd_wettest_mm']:.0f} | {r['era5_on_wettest_mm']:.0f} |"
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

    qb_path = out_dir / "qpf_bias_test.csv"
    if qb_path.exists():
        qb = pd.read_csv(qb_path)
        qb = qb[qb["lead_days"].between(1, 5)]
        lines += [
            "### Multiplicative bias correction, tested out of sample",
            "",
            "One factor per catchment, model and lead (observed season rain over forecast season "
            "rain, clipped to 0.5 to 2), fitted on every season but one and applied to the "
            "held-out season; the held-out days of all seasons are scored together. Pearson r "
            "does not move under a scale factor, so the columns that can move are shown raw and "
            "corrected. Leads 1 to 5 are the product's horizons.",
            "",
            "| catchment | model | lead (days) | days | held-out factors | bias raw / corrected | MAE (mm) raw / corrected | hit rate raw / corrected | false-alarm ratio raw / corrected |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
        for _, r in qb.sort_values(["catchment", "model", "lead_days"]).iterrows():
            lines.append(
                f"| {r['catchment']} | {r['model']} | {int(r['lead_days'])} | {int(r['n_days'])} | "
                f"{r['factor_min']:.2f} to {r['factor_max']:.2f} | "
                f"{r['raw_bias_pct']:+.0f}% / {r['corrected_bias_pct']:+.0f}% | "
                f"{r['raw_mae_mm']:.1f} / {r['corrected_mae_mm']:.1f} | "
                f"{_rate(r['raw_hit_rate'])} / {_rate(r['corrected_hit_rate'])} | "
                f"{_rate(r['raw_false_alarm_ratio'])} / {_rate(r['corrected_false_alarm_ratio'])} |"
            )
        lines.append("")
        dams = qb[qb["catchment"].isin(list(C.DAMS))]
        if len(dams):
            better_mae = int((dams["corrected_mae_mm"] < dams["raw_mae_mm"]).sum())
            better_hit = int((dams["corrected_hit_rate"] > dams["raw_hit_rate"]).sum())
            worse_far = int(
                (dams["corrected_false_alarm_ratio"] > dams["raw_false_alarm_ratio"]).sum()
            )
            lines += [
                f"Held-out days, dam catchments, leads 1 to 5: MAE lower after correction in "
                f"{better_mae} of {len(dams)} rows, heavy-day hit rate higher in {better_hit}, "
                f"false-alarm ratio higher in {worse_far}. The product applies a correction only "
                "when MAE and hit rate both improve on the held-out seasons for a dam catchment; "
                "the rule is in `design.md`.",
                "",
            ]

    mc = results.get("qpf_model_comparison")
    if mc and mc.get("n_common_days"):
        inc, ch = mc["incumbent"], mc["challenger"]
        rule = (
            "the challenger replaces the incumbent as the product's primary deterministic "
            "model only if its heavy-day hit rate is higher and its false-alarm ratio is not "
            "higher on those rows"
        )
        lines += [
            "### The machine-learned model against the primary deterministic model",
            "",
            f"`{mc['challenger_model']}` (ECMWF AIFS, the machine-learned forecast) and "
            f"`{mc['incumbent_model']}` scored on exactly the same rows: the dam catchments, "
            f"leads {', '.join(str(x) for x in mc['leads'])}, every target day both have in the "
            f"archive ({mc['n_common_days']:,} rows). The rule, written before the pull: {rule}. "
            "The spill probability comes from the IFS ensemble either way; the primary "
            "deterministic model drives the local term and the deterministic fallback.",
            "",
            "| model | obs mean (mm) | bias | r | MAE (mm) | heavy days | hit rate | false-alarm ratio |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for name, s in ((mc["incumbent_model"], inc), (mc["challenger_model"], ch)):
            lines.append(
                f"| {name} | {s['obs_mean_mm']:.1f} | {s['bias_pct']:+.0f}% | "
                f"{_num(s.get('pearson_r'), '.2f')} | {s['mae_mm']:.1f} | "
                f"{int(s['heavy_days_obs'])} | {_rate(s.get('hit_rate'))} | "
                f"{_rate(s.get('false_alarm_ratio'))} |"
            )
        lines += [
            "",
            f"Hit rate higher: {'yes' if mc.get('hit_rate_higher') else 'no'}; false-alarm "
            f"ratio not higher: {'yes' if mc.get('false_alarm_not_higher') else 'no'}. "
            f"Verdict: the primary deterministic model "
            f"{'switches to ' + mc['challenger_model'] if mc.get('switch') else 'stays ' + mc['incumbent_model']}."
            + (
                f" The product's primary is `{mc['primary_in_product']}`."
                if mc.get("primary_in_product")
                else ""
            ),
            "",
        ]

    bt = results.get("qpf_blend_test")
    if bt and bt.get("n_common_days"):
        sc = bt["scores"]
        inc = sc.get(bt["incumbent_model"], {})
        lines += [
            "### The deterministic models combined against the primary one",
            "",
            f"Three ways of combining `{'`, `'.join(bt['models'])}` scored on the "
            f"{bt['n_common_days']:,} (catchment, day, lead) rows all of them have over the dam "
            f"catchments at leads {', '.join(str(x) for x in bt['leads'])}: the equal-weight "
            "mean, an inverse-MAE weighted mean with the weights fitted on every season but the "
            "one scored, and the largest of the three (the hazard-minded blend). Same rule as "
            "the model switch: a blend replaces the primary only if its heavy-day hit rate is "
            "higher and its false-alarm ratio is not higher on the same rows.",
            "",
            "| rain source | bias | r | MAE (mm) | heavy days | hit rate | false-alarm ratio "
            "| passes the rule |",
            "|---|---|---|---|---|---|---|---|",
        ]
        order = [bt["incumbent_model"]] + [m for m in bt["models"] if m != bt["incumbent_model"]]
        order += ["equal_mean", "inverse_mae_weighted_loso", "max_of_models"]
        for name in order:
            s_ = sc.get(name)
            if not s_:
                continue
            verdict = "" if "passes_rule" not in s_ else ("yes" if s_["passes_rule"] else "no")
            lines.append(
                f"| {name} | {s_['bias_pct']:+.0f}% | {_num(s_.get('pearson_r'), '.2f')} | "
                f"{s_['mae_mm']:.2f} | {int(s_['heavy_days_obs'])} | {_rate(s_.get('hit_rate'))} | "
                f"{_rate(s_.get('false_alarm_ratio'))} | {verdict} |"
            )
        w = bt.get("weights_all_seasons") or {}
        lines += [
            "",
            "Weights fitted on every season: "
            + ", ".join(f"{m} {v:.2f}" for m, v in w.items())
            + ". "
            + (
                f"Verdict: the product takes `{bt['adopt']}`."
                if bt.get("adopt")
                else f"Verdict: no blend passes; the primary stays `{bt['incumbent_model']}`. "
                "The means lower the MAE and raise the correlation but miss more of the heavy "
                "days (the models disagree on their timing, so averaging smears them); the "
                "maximum catches more heavy days at a higher false-alarm ratio."
            ),
            "",
        ]

    rr = results.get("realtime_rain")
    if rr and rr.get("rows"):
        lines += [
            "### The in-season observed rain: IMD real-time grid and ERA5 against the final grid",
            "",
            f"The runoff model is calibrated on the final IMD grid, which arrives after the "
            f"season. In season the product has to carry the previous days' rain from something "
            f"else: until now the best-match model's past days (ERA5 physics), and the record on "
            f"disk was ERA5. IMD Pune serves a preliminary real-time analysis on the same "
            f"lattice. Both are scored here against the final grid over the {rr['season']} "
            f"season on the dam catchments, on the days each has (heavy day: "
            f"{rr['heavy_mm']:.0f} mm or more). The rule, written before the pull: the real-time "
            "grid replaces the model's past days as the product's observed record only if its "
            "MAE is lower than ERA5's at every dam and its heavy-day hit rate is not lower at any.",
            "",
            "| catchment | record | days | final mean (mm) | bias | r | MAE (mm) | heavy days | hit rate | false-alarm ratio |",
            "|---|---|---|---|---|---|---|---|---|---|",
        ]
        for s in rr["rows"]:
            lines.append(
                f"| {s['catchment']} | {s['record']} | {int(s['n_days'])} | {s['obs_mean_mm']:.1f} | "
                f"{s['bias_pct']:+.0f}% | {_num(s.get('pearson_r'), '.2f')} | {s['mae_mm']:.1f} | "
                f"{int(s['heavy_days_obs'])} | {_rate(s.get('hit_rate'))} | "
                f"{_rate(s.get('false_alarm_ratio'))} |"
            )
        verdict = (
            "the product's observed record switches to the IMD real-time grid, the model's "
            "past days standing in for any day the service does not have"
            if rr.get("switch")
            else "the product keeps the model's past days"
        )
        lines += [
            "",
            f"MAE lower at every dam: {'yes' if rr.get('mae_lower_everywhere') else 'no'}; "
            f"hit rate not lower at any: {'yes' if rr.get('hit_rate_not_lower') else 'no'}"
            + (f"; dams without real-time days: {', '.join(rr['dams_missing'])}" if rr.get("dams_missing") else "")
            + f". Verdict: {verdict}."
            + (
                f" The product's observed record is `{rr['record_in_product']}`."
                if rr.get("record_in_product")
                else ""
            ),
            "",
        ]

    lines += [
        "## Live 2026: one-day inflow prediction against the BBMB bulletins",
        "",
        "Persistence (tomorrow's inflow equals today's) is the baseline any one-day "
        "prediction has to beat; the model's base component is that persistence with the "
        "rain response added, so the difference between the two rows is what the rain "
        "brings.",
        "",
    ]
    live = results.get("live_2026") or {}
    if live:
        lines += [
            "| dam | days | mean observed (cusecs) | mean predicted (cusecs) | bias | Pearson r | MAE (cusecs) | persistence bias | persistence r | persistence MAE |",
            "|---|---|---|---|---|---|---|---|---|---|",
        ]
        for dam, m in live.items():
            if "note" in m:
                lines.append(f"| {dam} | {m['n']} | {m['note']} | | | | | | | |")
            else:
                pb = m.get("persistence_bias_pct")
                pr = m.get("persistence_pearson_r")
                pm = m.get("persistence_mae_cusecs")
                lines.append(
                    f"| {dam} | {m['n']} | {m['mean_obs_cusecs']:,.0f} | {m['mean_pred_cusecs']:,.0f} | "
                    f"{m['bias_pct']:+.0f}% | {m['pearson_r']:+.2f} | {m['mae_cusecs']:,.0f} | "
                    f"{'n/a' if pb is None else f'{pb:+.0f}%'} | "
                    f"{'n/a' if pr is None else f'{pr:+.2f}'} | "
                    f"{'n/a' if pm is None else f'{pm:,.0f}'} |"
                )
    else:
        lines.append("Not run.")
    lines.append("")

    ic = results.get("inflow_calibration_2026") or {}
    if ic:
        lines += [
            "### The response fitted on measured inflow, 2026 bulletins",
            "",
            "The runoff response in force is fitted on day-to-day storage change, which is "
            "inflow minus a release the record does not show. The bulletin capture that began "
            "in August 2026 is the first daily inflow record this project has had, so the same "
            "response (coefficient, wetness term, lag weights, a constant base) is fitted on "
            "the daily mean of the bulletins' inflow and the storage-change fit is scored "
            "against that inflow out of sample (its base is the intercept plus the non-spill "
            "passage, as in every verification run, and again with the base fitted on these "
            "days so the response is judged on its own). One deficit season, in-sample for "
            "the inflow fit: the product keeps the storage-change parameters, and the live "
            "product takes its base from the bulletin, not from the intercept; the ratio of "
            "the two coefficients is the measure of what the storage record cannot see.",
            "",
            "| dam | bulletin days | fit | c (dry) | c_wet | lag weights | base (cusecs) | R2 | "
            "bias against measured inflow | r | MAE (cusecs) | c ratio, inflow fit over storage fit |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|",
        ]
        for dam, e in ic.items():
            s_fit = e.get("storage_fit") or {}
            s_sc = e.get("storage_fit_on_inflow") or {}
            i_fit = e.get("inflow_fit")
            i_sc = e.get("inflow_fit_in_sample") or {}
            w_s = ", ".join(f"{x:.2f}" for x in s_fit.get("w", []))
            lines.append(
                f"| {dam} | {e.get('n_bulletin_days', 0)} | storage change, 2015 to 2025 | "
                f"{s_fit.get('c', float('nan')):.3f} | {s_fit.get('c_wet', 0.0):.3f} | {w_s} | "
                f"{_num(s_sc.get('base_cusecs'), ',.0f')} | {_num(s_fit.get('r2'), '.3f')} | "
                f"{_num(s_sc.get('bias_pct'), '+.0f')}% | {_num(s_sc.get('pearson_r'), '.2f')} | "
                f"{_num(s_sc.get('mae_cusecs'), ',.0f')} | {_num(s_sc.get('coefficient_ratio'), '.2f')} |"
            )
            s_fb = e.get("storage_fit_on_inflow_fitted_base") or {}
            if s_fb:
                lines.append(
                    f"| {dam} | {s_fb.get('n_days', 0)} | storage change, base fitted on 2026 | "
                    f"{s_fit.get('c', float('nan')):.3f} | {s_fit.get('c_wet', 0.0):.3f} | {w_s} | "
                    f"{_num(s_fb.get('base_cusecs'), ',.0f')} | | "
                    f"{_num(s_fb.get('bias_pct'), '+.0f')}% | {_num(s_fb.get('pearson_r'), '.2f')} | "
                    f"{_num(s_fb.get('mae_cusecs'), ',.0f')} | |"
                )
            if i_fit:
                w_i = ", ".join(f"{x:.2f}" for x in i_fit.get("w", []))
                lines.append(
                    f"| {dam} | {i_fit.get('n_days', 0)} | measured inflow, 2026 (in sample) | "
                    f"{i_fit['c']:.3f} | {i_fit.get('c_wet', 0.0):.3f} | {w_i} | "
                    f"{_num(i_sc.get('base_cusecs'), ',.0f')} | {_num(i_fit.get('r2'), '.3f')} | "
                    f"{_num(i_sc.get('bias_pct'), '+.0f')}% | {_num(i_sc.get('pearson_r'), '.2f')} | "
                    f"{_num(i_sc.get('mae_cusecs'), ',.0f')} | |"
                )
            elif e.get("note"):
                lines.append(f"| {dam} | {e.get('n_bulletin_days', 0)} | measured inflow | {e['note']} | | | | | | | | |")
        lines.append("")

    lh = results.get("live_horizons") or []
    if lh:
        lines += [
            "### By horizon, with observed and with forecast rain",
            "",
            "From each bulletin day, the inflow one to five days ahead: predicted with the "
            "observed catchment rain of the days in between (what the hydrology alone can do), "
            "with the rain forecast issued that day (what the product does, per model), and by "
            "persistence (the inflow stays at the day's value). Scored on the days a bulletin "
            "exists for the target day.",
            "",
            "| dam | horizon (days) | rain | days | bias | Pearson r | MAE (cusecs) |",
            "|---|---|---|---|---|---|---|",
        ]
        for r in lh:
            bp = r.get("bias_pct")
            if bp is None or bp != bp:
                lines.append(
                    f"| {r['dam']} | {int(r['horizon_days'])} | {r['rain']} | {int(r['n'])} | "
                    f"{r.get('note') or 'too few days'} | | |"
                )
            else:
                lines.append(
                    f"| {r['dam']} | {int(r['horizon_days'])} | {r['rain']} | {int(r['n'])} | "
                    f"{bp:+.0f}% | {_fmt(r.get('pearson_r'))} | {r['mae_cusecs']:,.0f} |"
                )
        lines.append("")

    if forecast_dir is not None and Path(forecast_dir).exists():
        lines += _prospective_lines(Path(forecast_dir))
    return "\n".join(lines)
