"""The daily hazard product: pull the state, pull the rain forecasts, compute the
headroom-exhaustion index per dam and horizon, route the forced release, classify the
arrivals, and write JSON and Markdown.

This is a hazard watch on physical quantities. It is not an official warning; the Punjab
WRD, CWC, BBMB and IMD issue those. Every output carries that sentence.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from punjabflood import constants as C
from punjabflood import hei, inflow, rain, routing
from punjabflood.catchments import Catchment
from punjabflood.imdrain import IMD_WEIGHT_COL, covered_area_km2
from punjabflood.openmeteo import OpenMeteo

log = logging.getLogger(__name__)

BBMB_URL = "https://bbmb.gov.in/writereaddata/Portal/images/pdf/res_data.pdf"
DISCLAIMER = (
    "Hazard watch computed from public data (BBMB bulletin, CWC storage, Open-Meteo rain "
    "forecasts, Punjab WRD travel times and thresholds). Not an official warning: the Punjab "
    "Water Resources Department, CWC, BBMB and IMD issue those."
)
HORIZONS = (1, 2, 3, 4, 5)
RECENT_DAYS = 6  # observed days before the issue date carried into the quick response and API
DETERMINISTIC_MODELS = (
    "gfs_seamless",
    "ecmwf_ifs025",
    "ecmwf_aifs025_single",
    "icon_seamless",
    "best_match",
)
# the deterministic model that drives the local term and the deterministic fallback release
# (the spill probability comes from the IFS ensemble either way). It changes only under the
# rule in `verify.qpf_model_comparison`, with the numbers in the verification report:
# switched from ecmwf_ifs025 to AIFS on 2026-09-17 (heavy-day hit rate higher, false-alarm
# ratio not higher, on the 2,034 dam-catchment rows both had at leads 1 to 3).
INCUMBENT_DETERMINISTIC = "ecmwf_ifs025"
PRIMARY_DETERMINISTIC = "ecmwf_aifs025_single"
DAM_CATCHMENT = {"Bhakra": "Bhakra", "Pong": "Pong", "Ranjit Sagar": "Ranjit Sagar"}
GHAGGAR_CATCHMENTS = ("Ghaggar Bhankarpur", "Ghaggar Khanauri")


# -- BBMB bulletin --------------------------------------------------------------------
def parse_bulletin_text(text: str) -> dict:
    """The as-on stamp and the Bhakra and Pong rows (level ft, inflow, outflow cusecs)."""
    rec: dict = {}
    m = re.search(
        r"as\s+on\s+([0-9]{1,2}[-/][0-9]{1,2}[-/][0-9]{2,4})\s*([0-9]{1,2}[:.][0-9]{2})?\s*(Hrs)?",
        text,
        re.I,
    )
    if m:
        rec["as_on_date"] = m.group(1)
        rec["as_on_time"] = m.group(2)
    tail = text.split("Latest BBMB Reservoir Data", 1)[-1]
    row_re = re.compile(
        r"^\s*(Bhakra|Pong)\s+([0-9][0-9,]*\.?[0-9]*)\s+([0-9][0-9,]*)\s+([0-9][0-9,]*)\s*$", re.I
    )
    for line in tail.splitlines():
        mm = row_re.match(line)
        if not mm:
            continue
        dam = mm.group(1).lower()
        num = lambda s: float(s.replace(",", ""))  # noqa: E731
        rec[dam + "_level_ft"] = num(mm.group(2))
        rec[dam + "_inflow_cusecs"] = int(num(mm.group(3)))
        rec[dam + "_outflow_cusecs"] = int(num(mm.group(4)))
    return rec


def fetch_bulletin(
    raw_dir: Path = Path("data/raw/bbmb"),
    session: requests.Session | None = None,
    timeout: float = 90.0,
) -> dict:
    """Download today's BBMB bulletin, parse it, archive the PDF and append the record to
    ``raw_dir/bulletins.jsonl`` (BBMB overwrites the file daily and keeps no archive)."""
    import pypdfium2 as pdfium

    sess = session or requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Accept": "application/pdf,*/*",
    }
    # bbmb.gov.in serves an incomplete certificate chain; the poller has needed verify=False
    # since August 2026. Integrity is checked on content (a PDF that parses to the two rows).
    r = sess.get(BBMB_URL, headers=headers, timeout=timeout, verify=False)
    r.raise_for_status()
    content = r.content
    if content[:4] != b"%PDF":
        raise RuntimeError("BBMB bulletin is not a PDF")
    raw_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    pdf_path = raw_dir / f"res_data_{ts}.pdf"
    pdf_path.write_bytes(content)
    doc = pdfium.PdfDocument(str(pdf_path))
    text = "\n".join(page.get_textpage().get_text_range() for page in doc)
    doc.close()
    rec = {
        "captured_utc": ts,
        "source_url": BBMB_URL,
        "bytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
        "raw_text": text,
    }
    rec.update(parse_bulletin_text(text))
    with (raw_dir / "bulletins.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


# -- product ----------------------------------------------------------------------------
def dam_state_from_bulletin(rec: dict, ratings: dict) -> dict[str, dict]:
    out = {}
    for key, dam in (("bhakra", "Bhakra"), ("pong", "Pong")):
        lvl_ft = rec.get(f"{key}_level_ft")
        if lvl_ft is None or dam not in ratings:
            continue
        lvl_m = lvl_ft * C.FOOT_M
        out[dam] = {
            "level_ft": lvl_ft,
            "level_m": lvl_m,
            "storage_bcm": float(ratings[dam].storage(lvl_m)),
            "inflow_cusecs": rec.get(f"{key}_inflow_cusecs"),
            "outflow_cusecs": rec.get(f"{key}_outflow_cusecs"),
            "basis": "bbmb bulletin as on "
            + str(rec.get("as_on_date"))
            + " "
            + str(rec.get("as_on_time")),
        }
    return out


def _series_by_model(qpf_det: pd.DataFrame, catchment: str, model: str) -> np.ndarray:
    g = qpf_det[(qpf_det["catchment"] == catchment) & (qpf_det["model"] == model)].sort_values(
        "target_date"
    )
    return g["rain_mm"].to_numpy(dtype=float)


def _members(qpf_ens: pd.DataFrame, catchment: str) -> dict[int, np.ndarray]:
    g = qpf_ens[qpf_ens["catchment"] == catchment]
    return {
        int(m): grp.sort_values("target_date")["rain_mm"].to_numpy(dtype=float)
        for m, grp in g.groupby("member")
    }


def _river_series(
    dam: str, spill_cusecs, outflow_today_cusecs: float, absorb_cusecs: float, dates
) -> pd.Series:
    """What reaches the river on each forecast day. On a day the spillway is forced, the
    spill plus the turbine passage the water balance assumed (a full reservoir passes its
    inflow, so the turbines run), the same rule the event test routes; on any other day
    today's outflow continued, the operator's choice persisting. The diversion capacity is
    taken off in ``routing.river_release``."""
    spill = np.asarray(spill_cusecs, dtype=float)
    total = np.where(spill > 0, absorb_cusecs + spill, outflow_today_cusecs)
    return pd.Series(routing.river_release(dam, total), index=dates)


def build_product(
    issue_date: str,
    states: dict[str, dict],
    qpf_det: pd.DataFrame,
    qpf_ens: pd.DataFrame,
    recent_rain: dict[str, list[float]],
    params: dict[str, inflow.InflowParams],
    ghaggar_climatology: dict[str, np.ndarray] | None = None,
    horizons=HORIZONS,
    local_areas: dict[str, float] | None = None,
    soil_moisture: dict[str, dict] | None = None,
) -> dict:
    """Assemble the hazard product from already-pulled inputs (pure; tested with fakes).
    ``local_areas``: IMD-covered area (km2) per local catchment (``constants.LOCAL_CATCHMENTS``)
    whose QPF is in ``qpf_det``; with it the local inflow term is computed from the
    transferred response and added at the control points that catchment feeds.
    ``soil_moisture``: per dam catchment the latest ERA5-Land day on record
    (``{"date", "sm_0_7"}``); its anomaly against the parameters' climatology multiplies
    the rain response where the parameters carry a soil-moisture sensitivity, and the day,
    value, anomaly and age are recorded on the product."""
    product = {
        "issue_date": issue_date,
        "generated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "disclaimer": DISCLAIMER,
        "dams": {},
        "reaches": [],
        "ghaggar": {},
        "local_inflow": {},
        "attribution": [
            "Weather data by Open-Meteo.com",
            "HydroBASINS (Lehner & Grill 2013)",
            "BBMB reservoir bulletin",
            "CWC daily reservoir data (data.gov.in)",
            "IMD gridded rainfall (Pai et al. 2014)",
            "Punjab WRD Flood Preparedness Guidebook 2026",
        ],
    }
    release_series: dict[str, pd.Series] = {}
    dates = pd.date_range(pd.Timestamp(issue_date) + pd.Timedelta(days=1), periods=max(horizons))
    for dam, st in states.items():
        if dam not in params:
            continue
        p = params[dam]
        cat = DAM_CATCHMENT[dam]
        absorb = hei.absorption_cusecs(dam)
        recent = recent_rain.get(cat, [])
        sm_anom = 0.0
        sm_rec = (soil_moisture or {}).get(cat)
        if sm_rec and p.uses_sm and sm_rec.get("sm_0_7") == sm_rec.get("sm_0_7"):
            sm_anom = inflow.sm_anomaly(p, float(sm_rec["sm_0_7"]), sm_rec["date"])
        base = inflow.base_from_observed(p, float(st["inflow_cusecs"] or 0.0), recent, sm_anom)
        entry = {
            "state": st,
            "storage_fraction": st["storage_bcm"] / C.DAMS[dam].live_capacity_bcm.value,
            "headroom_bcm": max(C.DAMS[dam].live_capacity_bcm.value - st["storage_bcm"], 0.0),
            "absorption_cusecs": absorb,
            "base_inflow_cusecs": base,
            "recent_rain_mm": [float(x) for x in recent],
            "deterministic": {},
            "ensemble": {},
        }
        if sm_rec and p.uses_sm:
            entry["soil_moisture"] = {
                "date": str(sm_rec["date"]),
                "sm_0_7": float(sm_rec["sm_0_7"]),
                "anomaly": sm_anom,
                "age_days": int((pd.Timestamp(issue_date) - pd.Timestamp(sm_rec["date"])).days),
                "wetness": p.wetness,
            }
        det_daily = {}
        for model in DETERMINISTIC_MODELS:
            fc = _series_by_model(qpf_det, cat, model)
            if len(fc) == 0:
                continue
            daily = inflow.predict_daily_bcm(
                p, fc[: max(horizons)], base, rain_mm_recent=recent, sm_anom=sm_anom
            )
            det_daily[model] = daily
            entry["deterministic"][model] = {
                "qpf_mm_by_day": [float(x) for x in fc[: max(horizons)]],
                "inflow_bcm_by_day": [float(x) for x in daily],
                "horizons": {
                    str(H): hei.headroom_exhaustion(
                        dam, st["storage_bcm"], daily[:H], absorb
                    ).to_dict()
                    for H in horizons
                },
            }
        members = _members(qpf_ens, cat)
        if members:
            h_max = max(horizons)
            # the daily prediction is causal, so one run per member over the longest horizon
            # serves every shorter one by slicing
            member_daily = [
                inflow.predict_daily_bcm(
                    p, fc[:h_max], base, rain_mm_recent=recent, sm_anom=sm_anom
                )
                for fc in members.values()
            ]
            res_max: list[hei.HEIResult] = []
            for H in horizons:
                daily_h = [d[:H] for d in member_daily if len(d) >= H]
                res = [hei.headroom_exhaustion(dam, st["storage_bcm"], d, absorb) for d in daily_h]
                summary = hei.ensemble_summary(res)
                # the inflow model's own error, sampled on top of the QPF spread
                summary.update(
                    hei.ensemble_summary_with_error(
                        dam, st["storage_bcm"], daily_h, absorb, p.rmse_bcm, p.resid_acf1
                    )
                )
                entry["ensemble"][str(H)] = summary
                if H == h_max:
                    res_max = res
            cushion = C.flood_cushion(dam)
            if cushion is not None:
                # the same members against the top of the flood cushion: what the dam can
                # hold before the spillway must open if BBMB lets it rise above FRL
                cap_c = cushion[1]
                ens_c = {}
                for H in horizons:
                    daily_h = [d[:H] for d in member_daily if len(d) >= H]
                    res_c = [
                        hei.headroom_exhaustion(dam, st["storage_bcm"], d, absorb, capacity_bcm=cap_c)
                        for d in daily_h
                    ]
                    summary_c = hei.ensemble_summary(res_c)
                    summary_c.update(
                        hei.ensemble_summary_with_error(
                            dam, st["storage_bcm"], daily_h, absorb, p.rmse_bcm, p.resid_acf1,
                            capacity_bcm=cap_c,
                        )
                    )
                    ens_c[str(H)] = summary_c
                entry["cushion"] = {
                    "top_level_ft": cushion[0] / C.FOOT_M,
                    "capacity_bcm": cap_c,
                    "headroom_bcm": max(cap_c - st["storage_bcm"], 0.0),
                    "deterministic": {
                        str(H): hei.headroom_exhaustion(
                            dam, st["storage_bcm"], det_daily[m][:H], absorb, capacity_bcm=cap_c
                        ).to_dict()
                        for m in [PRIMARY_DETERMINISTIC if PRIMARY_DETERMINISTIC in det_daily else next(iter(det_daily))]
                        for H in horizons
                    }
                    if det_daily
                    else {},
                    "ensemble": ens_c,
                }
            rel = np.array([r.release_by_day_cusecs for r in res_max])
            median_rel = np.median(rel, axis=0)
            entry["forced_release_median_cusecs_by_day"] = [float(x) for x in median_rel]
            outflow = float(st.get("outflow_cusecs") or 0.0)
            release_series[dam] = _river_series(dam, median_rel, outflow, absorb, dates)
        elif det_daily:
            model = (
                PRIMARY_DETERMINISTIC
                if PRIMARY_DETERMINISTIC in det_daily
                else next(iter(det_daily))
            )
            res = hei.headroom_exhaustion(dam, st["storage_bcm"], det_daily[model], absorb)
            outflow = float(st.get("outflow_cusecs") or 0.0)
            release_series[dam] = _river_series(
                dam, np.array(res.release_by_day_cusecs), outflow, absorb, dates
            )
        product["dams"][dam] = entry

    # the land between the dams and the head works: its forecast rain through a dam's
    # transferred response, added at the control points it feeds (no base flow, a lower
    # bound); the primary deterministic model where present, else the first on file
    local_series: dict[str, pd.Series] = {}
    for name, lc in C.LOCAL_CATCHMENTS.items():
        if not local_areas or name not in local_areas or lc.transfer_dam not in params:
            continue
        det = {m: _series_by_model(qpf_det, name, m) for m in DETERMINISTIC_MODELS}
        det = {m: v for m, v in det.items() if len(v)}
        if not det:
            continue
        model = PRIMARY_DETERMINISTIC if PRIMARY_DETERMINISTIC in det else next(iter(det))
        fc = det[model][: max(horizons)]
        recent = recent_rain.get(name, [])
        cusecs = inflow.local_inflow_forecast_cusecs(
            params[lc.transfer_dam], local_areas[name], recent, fc
        )
        local_series[name] = pd.Series(cusecs, index=dates[: len(cusecs)])
        product["local_inflow"][name] = {
            "model": model,
            "transfer_dam": lc.transfer_dam,
            "area_km2": float(local_areas[name]),
            "stations": list(lc.stations),
            "qpf_mm_by_day": [float(x) for x in fc],
            "recent_rain_mm": [float(x) for x in recent],
            "cusecs_by_day": [float(x) for x in cusecs],
        }

    if release_series or local_series:
        arr = routing.arrivals(release_series, local=local_series or None)
        arr = arr[arr["date"] > pd.Timestamp(issue_date)]
        for st_name, g in arr.groupby("station"):
            g = g.sort_values("date")
            worst = g.loc[g["cusecs"].idxmax()]
            product["reaches"].append(
                {
                    "station": st_name,
                    "river": g["river"].iloc[0],
                    "peak_cusecs": float(worst["cusecs"]),
                    "peak_date": worst["date"].date().isoformat(),
                    "peak_class": worst["class"],
                    "by_day": [
                        {"date": d.date().isoformat(), "cusecs": float(q), "class": c}
                        for d, q, c in zip(g["date"], g["cusecs"], g["class"], strict=True)
                    ],
                }
            )

    for cat in GHAGGAR_CATCHMENTS:
        det = {m: _series_by_model(qpf_det, cat, m) for m in DETERMINISTIC_MODELS}
        det = {m: v for m, v in det.items() if len(v)}
        if not det:
            continue
        three_day = {m: float(v[:3].sum()) for m, v in det.items()}
        entry = {"qpf_3day_mm": three_day, "recent_rain_mm": recent_rain.get(cat, [])}
        if ghaggar_climatology and cat in ghaggar_climatology:
            clim = np.asarray(ghaggar_climatology[cat])
            entry["qpf_3day_percentile"] = {
                m: float((clim < v).mean() * 100) for m, v in three_day.items()
            }
        product["ghaggar"][cat] = entry
    return product


def render_markdown(product: dict) -> str:
    lines = [
        f"# Punjab river hazard watch, issued {product['issue_date']}",
        "",
        f"_{product['disclaimer']}_",
        "",
    ]
    for dam, e in product["dams"].items():
        st = e["state"]
        lines.append(f"## {dam}")
        lines.append(
            f"Level {st.get('level_ft', float('nan')):.2f} ft, storage {st['storage_bcm']:.3f} BCM "
            f"({e['storage_fraction'] * 100:.1f}% of live capacity), headroom {e['headroom_bcm']:.3f} BCM, "
            f"inflow {st.get('inflow_cusecs')} cusecs, outflow {st.get('outflow_cusecs')} cusecs "
            f"({st.get('basis')})."
        )
        srcs = (product.get("recent_rain_source") or {}).get(dam)
        if srcs:
            n_imd = sum(1 for s in srcs if s == "imd_rt")
            lines.append(
                f"Observed rain of the previous {len(srcs)} days: {n_imd} from the IMD "
                f"real-time grid, {len(srcs) - n_imd} from the {RECENT_MODEL} model's past days "
                f"({', '.join(f'{v:.1f}' for v in e.get('recent_rain_mm', []))} mm)."
            )
        if e.get("soil_moisture"):
            s = e["soil_moisture"]
            lines.append(
                f"Soil moisture (ERA5-Land 0-7 cm, catchment mean) {s['sm_0_7']:.3f} on "
                f"{s['date']}, {s['anomaly']:+.2f} against its day-of-year climatology "
                f"({s['age_days']} days before issue); the rain response carries it "
                f"(wetness carrier {s['wetness']})."
            )
        if e.get("cushion"):
            c = e["cushion"]
            lines.append(
                f"With the flood cushion to {c['top_level_ft']:.0f} ft ({c['capacity_bcm']:.3f} BCM, "
                f"headroom {c['headroom_bcm']:.3f} BCM), P(spillway forced) by horizon: "
                + ", ".join(
                    f"{H} d {s['p_exhaustion']:.2f}"
                    + (
                        f" ({s['p_exhaustion_model_error']:.2f} with model error)"
                        if s.get("p_exhaustion_model_error") is not None
                        else ""
                    )
                    for H, s in c["ensemble"].items()
                )
                + ". The table below and the routed arrivals are the FRL bound."
            )
        elif dam in C.DAMS and C.flood_cushion(dam) is None:
            lines.append(
                "No flood-cushion scenario: no published storage figure above FRL for this dam; "
                "the FRL bound below is an early, upper bound."
            )
        if e["ensemble"]:
            lines.append("")
            lines.append(
                "| horizon (days) | P(spillway forced), QPF spread | P(spillway forced), QPF spread "
                "and model error | HEI median | peak forced release, median (cusecs) |"
            )
            lines.append("|---|---|---|---|---|")
            for H, s in e["ensemble"].items():
                pe = s.get("p_exhaustion_model_error")
                lines.append(
                    f"| {H} | {s['p_exhaustion']:.2f} | {'n/a' if pe is None else f'{pe:.2f}'} | "
                    f"{s['hei_q50']:+.3f} | {s['peak_release_q50_cusecs']:,.0f} |"
                )
        lines.append("")
    if product["reaches"]:
        lines.append("## Routed arrivals at WRD control points")
        lines.append("| station | peak (cusecs) | date | WRD class |")
        lines.append("|---|---|---|---|")
        for r in product["reaches"]:
            lines.append(
                f"| {r['station']} | {r['peak_cusecs']:,.0f} | {r['peak_date']} | {r['peak_class'] or 'below low'} |"
            )
        lines.append("")
    if product.get("local_inflow"):
        lines.append(
            "Local inflow added at the control points (runoff of the HydroBASINS sub-basins "
            "between the dams and the head works from their own forecast rain, with a dam's "
            "calibrated response transferred; no base flow, so a lower bound):"
        )
        for name, li in product["local_inflow"].items():
            peak = max(li["cusecs_by_day"]) if li["cusecs_by_day"] else 0.0
            lines.append(
                f"- {name} ({li['area_km2']:,.0f} km2, {li['transfer_dam']} response, "
                f"{li['model']}): peak {peak:,.0f} cusecs, added at {', '.join(li['stations'])}"
            )
        lines.append("")
    if product["ghaggar"]:
        lines.append("## Ghaggar rain index (no gauge model; catchment QPF only)")
        for cat, g in product["ghaggar"].items():
            q = ", ".join(f"{m} {v:.0f} mm" for m, v in g["qpf_3day_mm"].items())
            pct = g.get("qpf_3day_percentile")
            extra = (
                (
                    " (percentile of 1961-2025 season 3-day totals: "
                    + ", ".join(f"{m} {v:.0f}" for m, v in pct.items())
                    + ")"
                )
                if pct
                else ""
            )
            lines.append(f"- {cat}: next 3 days {q}{extra}")
        lines.append("")
    lines.append("Attribution: " + "; ".join(product["attribution"]) + ".")
    return "\n".join(lines)


def write_outputs(product: dict, out_dir: Path = Path("outputs/forecast")) -> tuple[Path, Path]:
    """Write the dated record. A prospective record is never rewritten: if a record for the
    issue date already exists, the new run is saved beside it with its generation time in
    the name (``<date>_rerun_<UTC stamp>``), and the first record of the day stands."""
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = str(product["issue_date"])
    if (out_dir / f"{stem}.json").exists():
        stamp = str(product.get("generated_utc", "")).replace(":", "").replace("-", "")[:15]
        stem = f"{stem}_rerun_{stamp or 'later'}"
        n = 1
        while (out_dir / f"{stem}.json").exists():
            n += 1
            stem = f"{product['issue_date']}_rerun_{stamp or 'later'}_{n}"
    jp = out_dir / f"{stem}.json"
    mp = out_dir / f"{stem}.md"
    jp.write_text(json.dumps(product, indent=2, default=str), encoding="utf-8")
    mp.write_text(render_markdown(product), encoding="utf-8")
    return jp, mp


def ghaggar_climatology(rain_daily: pd.DataFrame) -> dict[str, np.ndarray]:
    """Season (Jun-Sep) 3-day rain totals per Ghaggar catchment from the observed record."""
    out = {}
    for cat in GHAGGAR_CATCHMENTS:
        g = rain_daily[rain_daily["catchment"] == cat].copy()
        if g.empty:
            continue
        g["date"] = pd.to_datetime(g["date"])
        s = g.set_index("date")["rain_mm"].sort_index().rolling(3).sum()
        out[cat] = s[s.index.month.isin([6, 7, 8, 9])].dropna().to_numpy()
    return out


def save_climatology(clim: dict[str, np.ndarray], path: Path, years: str = "") -> None:
    """Persist the season 3-day totals (rounded to 0.01 mm) so a runner without the raw rain
    archive can still place a forecast in the record's percentiles."""
    path.parent.mkdir(parents=True, exist_ok=True)
    obj = {
        "what": "Jun-Sep 3-day catchment rain totals (mm) from the observed record",
        "years": years,
        "totals": {k: [round(float(x), 2) for x in v] for k, v in clim.items()},
    }
    path.write_text(json.dumps(obj), encoding="utf-8")


def load_climatology(path: Path) -> dict[str, np.ndarray] | None:
    if not Path(path).exists():
        return None
    obj = json.loads(Path(path).read_text(encoding="utf-8"))
    return {k: np.asarray(v, dtype=float) for k, v in obj["totals"].items()}


SOIL_LOOKBACK_DAYS = 14  # the ERA5-Land archive lags about five days; look back far enough


def latest_soil_moisture(
    client: OpenMeteo,
    catchments: dict[str, Catchment],
    params: dict[str, inflow.InflowParams],
    issue_date: str,
) -> dict[str, dict]:
    """The latest ERA5-Land 0-7 cm soil-moisture day on record for each dam catchment whose
    parameters carry a soil-moisture sensitivity, as ``{"date", "sm_0_7"}``. One archive
    call per point per issue date (the cache key carries the end date); catchments without
    a value in the window are left out."""
    out = {}
    end = pd.Timestamp(issue_date)
    start = (end - pd.Timedelta(days=SOIL_LOOKBACK_DAYS)).date().isoformat()
    for dam, cat_name in DAM_CATCHMENT.items():
        p = params.get(dam)
        cat = catchments.get(cat_name)
        if p is None or cat is None or not p.uses_sm:
            continue
        try:
            df = rain.era5_catchment_daily(
                client,
                cat,
                start,
                end.date().isoformat(),
                years_per_chunk=1,
                daily=("soil_moisture_0_to_7cm_mean",),
                weight_col=IMD_WEIGHT_COL,
            )
        except Exception as exc:  # the product must not fail for want of the anomaly
            log.warning("soil moisture pull failed for %s: %s", cat_name, exc)
            continue
        good = df[df["sm_0_7"].notna()].sort_values("date")
        if good.empty:
            continue
        last = good.iloc[-1]
        out[cat_name] = {
            "date": pd.Timestamp(last["date"]).date().isoformat(),
            "sm_0_7": float(last["sm_0_7"]),
        }
    return out


RECENT_MODEL = "best_match"  # the past days of Open-Meteo's best-match model, the fallback
# The product's observed record for the days before the issue date: the incumbent is the
# best-match model's past days; "imd_rt" takes the IMD real-time grid where the service has
# the day. Switched only by the rule in verify.realtime_vs_final (report section "The
# in-season observed rain"); until then the incumbent stands.
OBSERVED_RECORD = "imd_rt"


def recent_rain(
    client: OpenMeteo,
    catchments: dict[str, Catchment],
    issue_date: str,
    rt_dir: Path | None = None,
    fetch=None,
    days: int = RECENT_DAYS,
    record: str | None = None,
) -> tuple[dict[str, list[float]], dict[str, list[str]]]:
    """The observed rain of the ``days`` days before the issue date for every catchment, and
    the source of each day. Catchments with IMD coverage weights (the calibrated index) take
    each day from the IMD real-time grid when it is on disk or can be fetched (``fetch``
    defaults to ``imdrain.fetch_realtime``; pass ``fetch=False`` to use only what is on
    disk), and the best-match model's past day otherwise; the others take the model.
    ``record`` (default ``OBSERVED_RECORD``) set to the model's name takes the model for
    every day, the real-time grid untouched."""
    from punjabflood import imdrain

    record = OBSERVED_RECORD if record is None else record

    issue = pd.Timestamp(issue_date)
    want = [issue - pd.Timedelta(days=k) for k in range(days, 0, -1)]
    rt_dir = imdrain.realtime_dir() if rt_dir is None else Path(rt_dir)
    with_imd = {n: c for n, c in catchments.items() if IMD_WEIGHT_COL in c.points}
    grid = pd.DataFrame()
    if with_imd and record == imdrain.RT_SOURCE:
        if fetch is None:
            fetch = imdrain.fetch_realtime
        if fetch is not False:
            try:
                fetch(want, rt_dir)
            except Exception:  # noqa: BLE001 - the service failing is a fallback, not an error
                log.warning("IMD real-time fetch failed; the model's past days stand in")
        grid = imdrain.catchment_daily_realtime(want, with_imd, rt_dir)
        if len(grid):
            grid["date"] = pd.to_datetime(grid["date"])
    recent, sources = {}, {}
    for name, cat in catchments.items():
        calibrated_index = name in DAM_CATCHMENT.values() or name in C.LOCAL_CATCHMENTS
        wc = (
            IMD_WEIGHT_COL
            if calibrated_index and IMD_WEIGHT_COL in cat.points
            else rain.WEIGHT_COL
        )
        past = rain.forecast_catchment(
            client,
            cat,
            models=(RECENT_MODEL,),
            days=1,
            issue_date=issue_date,
            past_days=days,
            weight_col=wc,
        )
        past = past.sort_values("target_date")
        model_days = past.set_index(pd.to_datetime(past["target_date"]))["rain_mm"]
        imd_days = (
            grid[grid["catchment"] == name].set_index("date")["rain_mm"]
            if len(grid)
            else pd.Series(dtype=float)
        )
        vals, srcs = [], []
        for d in want:
            if d in imd_days.index and imd_days[d] == imd_days[d]:
                vals.append(float(imd_days[d]))
                srcs.append(imdrain.RT_SOURCE)
            elif d in model_days.index and model_days[d] == model_days[d]:
                vals.append(float(model_days[d]))
                srcs.append(RECENT_MODEL)
        recent[name] = vals
        sources[name] = srcs
    return recent, sources


def run(
    client: OpenMeteo,
    catchments: dict[str, Catchment],
    ratings: dict,
    params: dict[str, inflow.InflowParams],
    issue_date: str | None = None,
    rain_daily: pd.DataFrame | None = None,
    bulletin: dict | None = None,
    out_dir: Path = Path("outputs/forecast"),
    climatology: dict[str, np.ndarray] | None = None,
    rt_dir: Path | None = None,
) -> dict:
    """One live cycle: bulletin, deterministic and ensemble QPF for every catchment, recent
    rain from the best-match model's past days, then the product on disk. Dam catchments use
    the IMD-coverage weights so the forecast index matches the calibrated one. The Ghaggar
    percentiles come from ``rain_daily`` when the observed record is on disk, else from a
    saved ``climatology`` (see ``save_climatology``)."""
    issue_date = issue_date or datetime.now(UTC).date().isoformat()
    rec = bulletin or fetch_bulletin()
    states = dam_state_from_bulletin(rec, ratings)
    det_frames, ens_frames = [], []
    recent, recent_sources = recent_rain(client, catchments, issue_date, rt_dir=rt_dir)
    for name, cat in catchments.items():
        calibrated_index = name in DAM_CATCHMENT.values() or name in C.LOCAL_CATCHMENTS
        wc = IMD_WEIGHT_COL if calibrated_index else rain.WEIGHT_COL
        det_frames.append(
            rain.forecast_catchment(
                client,
                cat,
                models=DETERMINISTIC_MODELS,
                days=max(HORIZONS) + 1,
                issue_date=issue_date,
                weight_col=wc,
            )
        )
        if name in DAM_CATCHMENT.values():
            ens_frames.append(
                rain.ensemble_catchment(
                    client, cat, days=max(HORIZONS) + 1, issue_date=issue_date, weight_col=wc
                )
            )
    qpf_det = pd.concat(det_frames, ignore_index=True)
    qpf_det = qpf_det[qpf_det["target_date"] > pd.Timestamp(issue_date)]
    qpf_ens = (
        pd.concat(ens_frames, ignore_index=True)
        if ens_frames
        else pd.DataFrame(columns=["target_date", "member", "rain_mm", "catchment", "model"])
    )
    if len(qpf_ens):
        qpf_ens = qpf_ens[qpf_ens["target_date"] > pd.Timestamp(issue_date)]
    clim = ghaggar_climatology(rain_daily) if rain_daily is not None else climatology
    local_areas = {
        name: covered_area_km2(cat)
        for name, cat in catchments.items()
        if name in C.LOCAL_CATCHMENTS and IMD_WEIGHT_COL in cat.points
    }
    soil = latest_soil_moisture(client, catchments, params, issue_date)
    product = build_product(
        issue_date,
        states,
        qpf_det,
        qpf_ens,
        recent,
        params,
        clim,
        local_areas=local_areas or None,
        soil_moisture=soil or None,
    )
    product["bulletin"] = {k: v for k, v in rec.items() if k != "raw_text"}
    product["recent_rain_source"] = recent_sources
    write_outputs(product, out_dir)
    return product
