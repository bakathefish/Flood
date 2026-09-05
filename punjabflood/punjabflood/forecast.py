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
from punjabflood.imdrain import IMD_WEIGHT_COL
from punjabflood.openmeteo import OpenMeteo

log = logging.getLogger(__name__)

BBMB_URL = "https://bbmb.gov.in/writereaddata/Portal/images/pdf/res_data.pdf"
DISCLAIMER = (
    "Hazard watch computed from public data (BBMB bulletin, CWC storage, Open-Meteo rain "
    "forecasts, Punjab WRD travel times and thresholds). Not an official warning: the Punjab "
    "Water Resources Department, CWC, BBMB and IMD issue those."
)
HORIZONS = (1, 2, 3, 4, 5)
DETERMINISTIC_MODELS = ("gfs_seamless", "ecmwf_ifs025", "icon_seamless", "best_match")
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


def build_product(
    issue_date: str,
    states: dict[str, dict],
    qpf_det: pd.DataFrame,
    qpf_ens: pd.DataFrame,
    recent_rain: dict[str, list[float]],
    params: dict[str, inflow.InflowParams],
    ghaggar_climatology: dict[str, np.ndarray] | None = None,
    horizons=HORIZONS,
) -> dict:
    """Assemble the hazard product from already-pulled inputs (pure; tested with fakes)."""
    product = {
        "issue_date": issue_date,
        "generated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "disclaimer": DISCLAIMER,
        "dams": {},
        "reaches": [],
        "ghaggar": {},
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
        base = inflow.base_from_observed(p, float(st["inflow_cusecs"] or 0.0), recent)
        entry = {
            "state": st,
            "storage_fraction": st["storage_bcm"] / C.DAMS[dam].live_capacity_bcm.value,
            "headroom_bcm": max(C.DAMS[dam].live_capacity_bcm.value - st["storage_bcm"], 0.0),
            "absorption_cusecs": absorb,
            "base_inflow_cusecs": base,
            "deterministic": {},
            "ensemble": {},
        }
        det_daily = {}
        for model in DETERMINISTIC_MODELS:
            fc = _series_by_model(qpf_det, cat, model)
            if len(fc) == 0:
                continue
            daily = inflow.predict_daily_bcm(p, fc[: max(horizons)], base, rain_mm_recent=recent)
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
            for H in horizons:
                res = [
                    hei.headroom_exhaustion(
                        dam,
                        st["storage_bcm"],
                        inflow.predict_daily_bcm(p, fc[:H], base, rain_mm_recent=recent),
                        absorb,
                    )
                    for fc in members.values()
                    if len(fc) >= H
                ]
                entry["ensemble"][str(H)] = hei.ensemble_summary(res)
            H = max(horizons)
            rel = np.array(
                [
                    hei.headroom_exhaustion(
                        dam,
                        st["storage_bcm"],
                        inflow.predict_daily_bcm(p, fc[:H], base, rain_mm_recent=recent),
                        absorb,
                    ).release_by_day_cusecs
                    for fc in members.values()
                    if len(fc) >= H
                ]
            )
            median_rel = np.median(rel, axis=0)
            entry["forced_release_median_cusecs_by_day"] = [float(x) for x in median_rel]
            # what actually reaches the river: today's outflow continues, plus forced spill
            outflow = float(st.get("outflow_cusecs") or 0.0)
            total = outflow + median_rel
            release_series[dam] = pd.Series(routing.river_release(dam, total), index=dates)
        elif det_daily:
            model = "ecmwf_ifs025" if "ecmwf_ifs025" in det_daily else next(iter(det_daily))
            res = hei.headroom_exhaustion(dam, st["storage_bcm"], det_daily[model], absorb)
            outflow = float(st.get("outflow_cusecs") or 0.0)
            total = outflow + np.array(res.release_by_day_cusecs)
            release_series[dam] = pd.Series(routing.river_release(dam, total), index=dates)
        product["dams"][dam] = entry

    if release_series:
        arr = routing.arrivals(release_series)
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
        if e["ensemble"]:
            lines.append("")
            lines.append(
                "| horizon (days) | P(spillway forced) | HEI median | peak forced release, median (cusecs) |"
            )
            lines.append("|---|---|---|---|")
            for H, s in e["ensemble"].items():
                lines.append(
                    f"| {H} | {s['p_exhaustion']:.2f} | {s['hei_q50']:+.3f} | {s['peak_release_q50_cusecs']:,.0f} |"
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
    out_dir.mkdir(parents=True, exist_ok=True)
    jp = out_dir / f"{product['issue_date']}.json"
    mp = out_dir / f"{product['issue_date']}.md"
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
) -> dict:
    """One live cycle: bulletin, deterministic and ensemble QPF for every catchment, recent
    rain from the best-match model's past days, then the product on disk. Dam catchments use
    the IMD-coverage weights so the forecast index matches the calibrated one. The Ghaggar
    percentiles come from ``rain_daily`` when the observed record is on disk, else from a
    saved ``climatology`` (see ``save_climatology``)."""
    issue_date = issue_date or datetime.now(UTC).date().isoformat()
    rec = bulletin or fetch_bulletin()
    states = dam_state_from_bulletin(rec, ratings)
    det_frames, ens_frames, recent = [], [], {}
    for name, cat in catchments.items():
        wc = IMD_WEIGHT_COL if name in DAM_CATCHMENT.values() else rain.WEIGHT_COL
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
        past = rain.forecast_catchment(
            client,
            cat,
            models=("best_match",),
            days=1,
            issue_date=issue_date,
            past_days=3,
            weight_col=wc,
        )
        past = past.sort_values("target_date")
        past = past[past["target_date"] < pd.Timestamp(issue_date)]
        recent[name] = [float(x) for x in past["rain_mm"].to_numpy()]
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
    product = build_product(issue_date, states, qpf_det, qpf_ens, recent, params, clim)
    product["bulletin"] = {k: v for k, v in rec.items() if k != "raw_text"}
    write_outputs(product, out_dir)
    return product
