# pipeline/nowcast.py
"""Live nowcast driver — every monitor cycle, predict the CURRENT 10-day window's
per-district flood risk with the committed forecaster from keyless live inputs,
and write ``monitor/nowcast.json`` (the locked schema the site is wired against).

Flow: resolve the current monsoon window from today's date (``sailaab.nowcast``)
-> pull live GFM observed extent, Open-Meteo rain, and CWC reservoirs
(``pipeline.fetch_live_inputs``) -> assemble the EXACT 16 training features
-> ``predict_proba`` for all 20 districts **iff** the window is core-season
(``window_start`` >= Jul 25; pre-core windows are out-of-domain, so ``p_event`` is
null and the ``activates`` countdown carries) -> shape + write JSON.

CI contract: this script must NEVER fail the monitor job. Every exception is
caught, a valid nulls JSON is written, and the process exits 0.

Run: ``python -m pipeline.nowcast``
"""

from __future__ import annotations

import json
import traceback
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from sailaab import nowcast

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
MODEL_PATH = DATA / "models" / "forecaster_2025.joblib"
PRIOR_CSV = DATA / "flood_frequency_districts_late_season.csv"
OUT = ROOT / "monitor" / "nowcast.json"

CALIBRATION_NOTE = (
    "Rain is Open-Meteo (ERA5 archive + forecast model, keyless, CC-BY 4.0); the "
    "forecaster trained on IMD 0.25deg gauge rain, so absolute rain magnitudes are "
    "not identically calibrated (treat rain features as a consistent proxy)."
)


def load_priors() -> dict:
    """District prior features from the committed late-season frequency table."""
    df = pd.read_csv(PRIOR_CSV)
    return {
        str(r["district"]): {
            "prior_mean_annual_flooded_ha": float(r["mean_annual_flooded_ha"]),
            "prior_seasons_with_fraction_gt2pct": float(
                r["seasons_with_fraction_gt2pct"]
            ),
        }
        for _, r in df.iterrows()
    }


def load_model():
    import joblib

    bundle = joblib.load(MODEL_PATH)
    return bundle["model"], list(bundle["features"])


def _fallback_districts():
    try:
        from sailaab.districts import load_districts

        return [n for n, _ in load_districts(canonicalize=True)]
    except Exception:
        try:
            return sorted(load_priors())
        except Exception:
            return []


def _write(payload) -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")


def _build_notes(
    window, rain_source, rain_meta, res_source, gfm_meta, model_note
) -> str:
    parts = []
    if model_note:
        parts.append(model_note)
    parts.append(CALIBRATION_NOTE)
    if res_source != "cwc":
        parts.append(
            "Reservoir storage/delta features are NaN: the BBMB dams (Bhakra, Pong, "
            "Ranjit Sagar) stopped reporting to the CWC data.gov.in feed in Jul 2025 "
            "and carry no 2026 rows; XGBoost ingests the missing values natively."
        )
    if rain_source == "open-meteo":
        cd, ct = (
            rain_meta.get("current_days_counted"),
            rain_meta.get("current_days_total"),
        )
        if cd is not None:
            parts.append(f"Current-window rain summed over {cd}/{ct} elapsed days.")
    else:
        parts.append(
            "Rain source degraded (Open-Meteo unreachable); rain features NaN."
        )
    parts.append(
        f"GFM observed extent: {gfm_meta.get('current_days_active', 0)} S1-active of "
        f"{gfm_meta.get('current_days', 0)} current-window days and "
        f"{gfm_meta.get('prev_days_active', 0)}/{gfm_meta.get('prev_days', 0)} antecedent-"
        f"window days (~{gfm_meta.get('grid_px')} px grid, permanent water removed)."
    )
    return " ".join(parts)


def degraded(generated, today_iso, reason) -> dict:
    """A schema-valid nulls payload for the never-fail CI contract."""
    try:
        window = nowcast.resolve_window(today_iso)
    except Exception:
        window = {
            "window_start": None,
            "window_end": None,
            "core_season": False,
            "activates": None,
        }
    return nowcast.build_nowcast_json(
        generated_utc=generated,
        window=window,
        sources={
            "rain": "unavailable",
            "reservoirs": "unavailable",
            "labels": "unavailable",
        },
        districts=_fallback_districts(),
        observed={},
        p_event=None,
        notes=f"DEGRADED: {reason}",
    )


def _print_summary(payload, window, rain, reservoirs, res_source, gfm_meta) -> None:
    print("NOWCAST_SUMMARY_JSON_START")
    top = payload["districts"][:6]
    print(
        json.dumps(
            {
                "generated_utc": payload["generated_utc"],
                "window": [payload["window_start"], payload["window_end"]],
                "core_season": payload["core_season"],
                "activates": payload["activates"],
                "sources": payload["sources"],
                "rain": {
                    "punjab_mm_sofar": rain.get("punjab_mm"),
                    "upstream_mm_sofar": rain.get("upstream_mm"),
                    "punjab_mm_lag1": rain.get("punjab_mm_lag1"),
                    "upstream_mm_lag1": rain.get("upstream_mm_lag1"),
                },
                "reservoirs_source": res_source,
                "gfm": {
                    k: gfm_meta.get(k)
                    for k in (
                        "current_days",
                        "current_days_active",
                        "prev_days",
                        "prev_days_active",
                        "wms_requests",
                    )
                },
                "top_observed": [
                    {
                        "district": d["district"],
                        "observed_km2": d["observed_km2"],
                        "observed_fraction_window": d["observed_fraction_window"],
                        "p_event": d["p_event"],
                    }
                    for d in top
                ],
            },
            indent=2,
            default=float,
        )
    )
    print("NOWCAST_SUMMARY_JSON_END")


def main() -> int:
    generated_dt = datetime.now(timezone.utc)
    generated = generated_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    today_iso = generated_dt.strftime("%Y-%m-%d")
    try:
        from pipeline.fetch_live_inputs import (
            fetch_gfm_observed,
            fetch_rain,
            fetch_reservoirs,
        )

        window = nowcast.resolve_window(today_iso)
        priors = load_priors()

        # GFM first: it defines the canonical district order everything keys on.
        observed, antecedent, gfm_meta = fetch_gfm_observed(window, today_iso)
        districts = gfm_meta["names"]

        rain, rain_source, rain_meta = fetch_rain(window, today_iso)
        reservoirs, res_source, _res_note = fetch_reservoirs(window, today_iso)

        X = nowcast.build_feature_frame(
            districts, rain, reservoirs, antecedent, window["week_of_season"], priors
        )

        p_event = None
        model_note = ""
        if window["core_season"]:
            model, feats = load_model()
            if feats != list(nowcast.FEATURE_ORDER):
                raise RuntimeError(f"model feature drift: {feats}")
            proba = model.predict_proba(X[feats])[:, 1]
            p_event = {d: float(p) for d, p in zip(districts, proba)}
        else:
            model_note = (
                f"Current window {window['window_start']} is pre-core-season "
                f"(before {window['activates']}) and out-of-domain for the "
                f"paddy-filtered forecaster; p_event stays null until "
                f"{window['activates']}."
            )

        notes = _build_notes(
            window, rain_source, rain_meta, res_source, gfm_meta, model_note
        )
        payload = nowcast.build_nowcast_json(
            generated_utc=generated,
            window=window,
            sources={"rain": rain_source, "reservoirs": res_source, "labels": "gfm"},
            districts=districts,
            observed=observed,
            p_event=p_event,
            notes=notes,
        )
        _write(payload)
        _print_summary(payload, window, rain, reservoirs, res_source, gfm_meta)
        print(f"NOWCAST OK -> {OUT}")
    except Exception as exc:  # never fail the monitor job
        traceback.print_exc()
        try:
            _write(degraded(generated, today_iso, f"{type(exc).__name__}: {exc}"))
        except Exception:
            traceback.print_exc()
        print(f"NOWCAST DEGRADED -> {OUT}")
    return 0


if __name__ == "__main__":
    try:
        code = main()
    except Exception:  # pragma: no cover - last-resort guard
        traceback.print_exc()
        code = 0
    raise SystemExit(code)
