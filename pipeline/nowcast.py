# pipeline/nowcast.py
"""Live nowcast driver — every monitor cycle, score each district's chance of the
satellite seeing flooding within three days, using the committed daily
forecaster and keyless live inputs, and write ``monitor/nowcast.json`` (the
locked schema the site is wired against).

Flow: resolve the current monsoon window from today's date (``sailaab.nowcast``)
-> pull live GFM observed extent plus recent history (``pipeline.fetch_live_inputs``)
-> assemble the EXACT 10 training features, all derived from satellite flood
observations; rain and reservoirs are fetched as page context only and are not
model inputs -> ``predict_proba`` for all 20 districts **iff** the window is
core-season AND coverage passes the publication gate -> shape + write JSON.
Districts the satellite could not see carry null score, rank and tier.

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

from sailaab import forecast_live, nowcast

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
MODEL_PATH = DATA / "models" / "forecaster_daily.joblib"
PRIOR_CSV = DATA / "flood_frequency_districts_late_season.csv"
OUT = ROOT / "monitor" / "nowcast.json"


class ForecastUnavailable(RuntimeError):
    """Raised when the observations cannot support publishing a forecast."""


CALIBRATION_NOTE = (
    "The score is a ranking score, not a calibrated probability: it has not been "
    "fitted to a reliability curve, so compare districts against each other and "
    "read the tier, rather than reading the number as a chance of flooding. Rain "
    "shown alongside is Open-Meteo (ERA5 archive + forecast model, keyless, "
    "CC-BY 4.0) and is page context, not a model input."
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


def load_bundle():
    """The deployed daily forecaster and everything inference needs with it."""
    import joblib

    b = joblib.load(MODEL_PATH)
    if list(b["feature_order"]) != list(forecast_live.FEATURE_ORDER):
        raise RuntimeError(f"model feature drift: {b['feature_order']}")
    return b


def _load_model_legacy():
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
    # The deployed forecaster reads satellite flood history only: prior-season
    # district behaviour, what the satellite sees now and over three days,
    # position in the season, neighbouring districts, the district-week
    # climatology, and flood activity decaying across the district graph.
    # Rainfall was tested as a feature family and measurably did not help, so
    # it is not an input. Reservoir storage is not an input either. Both are
    # still fetched and shown on the page as context for a reader, and saying
    # so plainly is the point: nothing below drives the score above.
    parts.append(
        "Forecast inputs are satellite flood history only: district priors, "
        "observed extent now and over three days, position in the season, "
        "neighbouring districts, the district-week climatology, and recent "
        "flooding decaying across the district graph. Rainfall was tested as a "
        "feature family and did not improve the forecast, so it is not an "
        "input; reservoir storage is not an input either. Both appear below as "
        "context only and do not move the score."
    )
    if res_source != "cwc":
        parts.append(
            "Reservoir context is unavailable: the BBMB dams (Bhakra, Pong, "
            "Ranjit Sagar) stopped reporting to the CWC data.gov.in feed in "
            "Jul 2025 and carry no 2026 rows."
        )
    if rain_source == "open-meteo":
        cd, ct = (
            rain_meta.get("current_days_counted"),
            rain_meta.get("current_days_total"),
        )
        if cd is not None:
            parts.append(
                f"Rain context summed over {cd}/{ct} elapsed days of the window."
            )
    else:
        parts.append("Rain context unavailable (Open-Meteo unreachable).")
    parts.append(
        f"GFM: {gfm_meta.get('current_days_fetched', 0)} of "
        f"{gfm_meta.get('current_days', 0)} current-window days returned data, "
        f"{gfm_meta.get('current_days_with_flood', 0)} of those carried flood "
        f"pixels; antecedent window "
        f"{gfm_meta.get('prev_days_fetched', 0)}/{gfm_meta.get('prev_days', 0)} "
        f"returned (~{gfm_meta.get('grid_px')} px grid, permanent water removed)."
    )
    # This sentence used to warn that the counts above were service responses
    # rather than acquisitions, and that coverage was therefore an upper bound.
    # That was true until coverage started coming from the Sentinel-1 footprint
    # layer. Leaving it in place made the prose contradict the data sitting
    # beside it in the same file, which is worse than the original overclaim:
    # a reader who believed the note would discount rows that are now sound.
    n_names = len(gfm_meta.get("names") or ()) or None
    if gfm_meta.get("footprint_available"):
        obs = gfm_meta.get("districts_observed", 0)
        unres = gfm_meta.get("districts_unresolved", 0)
        parts.append(
            f"Coverage is decided by the Sentinel-1 acquisition footprint, not by "
            f"whether a tile returned: {obs}"
            f"{f' of {n_names}' if n_names else ''} districts were imaged across "
            f"at least 95% of their area over the window"
            f"{f', {unres} were imaged but their flood product did not resolve' if unres else ''}. "
            f"Districts with no pass are published without a score rather than as dry."
        )
    else:
        # "none are scored" used to be guaranteed because scoring eligibility
        # and this flag came from the same fetch. Unifying the predicate on the
        # recent history moved eligibility and left this sentence keyed to the
        # current-window fetch, so at a window boundary the note could report
        # districts above the alert threshold and, a sentence later, that
        # nothing had been imaged. The claim is now made only when it is true.
        scored = gfm_meta.get("eligible_districts")
        parts.append(
            "The Sentinel-1 footprint layer was unreachable for the current "
            "window, so district coverage over the window cannot be shown. "
            "An empty flood mask over unimaged ground is not a dry day."
            + (
                " No district is scored."
                if not scored
                else f" Scoring used the {scored} district(s) with a recent "
                f"acquisition in the rolling history, which is fetched "
                f"separately and did resolve."
            )
        )
    return " ".join(parts)


def degraded(generated, today_iso, reason) -> dict:
    """A schema-valid nulls payload for the never-fail CI contract.

    Two things this must never do. It must not claim to know the season when
    the failure was working out the season, because a reader turns
    ``core_season: false`` into "the forecaster is resting until the monsoon",
    which is a reassuring thing to print on the day the pipeline broke. And it
    must carry an explicit unavailable marker rather than merely omitting the
    forecast, so a consumer that never learned the omission rule still shows
    the failure.
    """
    try:
        window = nowcast.resolve_window(today_iso)
    except Exception:
        window = {
            "window_start": None,
            "window_end": None,
            "core_season": None,  # unknown, not "out of season"
            "activates": None,
        }
    return nowcast.build_nowcast_json(
        generated_utc=generated,
        window=window,
        sources={
            "forecast_inputs": "unavailable",
            "labels": "unavailable",
            "context_rain": "unavailable",
            "context_reservoirs": "unavailable",
        },
        districts=_fallback_districts(),
        observed={},
        p_event=None,
        forecast={
            "status": "unavailable",
            "reason": reason,
            "note": (
                "No forecast was produced this cycle. This is not an all-clear: "
                "absence of a forecast is absence of information."
            ),
        },
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
                        "current_days_fetched",
                        "current_days_with_flood",
                        # the acquisition counters decide who gets scored at
                        # all, so they belong in the run summary beside the
                        # response counts rather than only inside the rows
                        "footprint_days_fetched",
                        "footprint_available",
                        "districts_observed",
                        "districts_unresolved",
                        "prev_days",
                        "prev_days_fetched",
                        "prev_days_with_flood",
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
    # Bound up front so the unavailable handler can publish whatever was
    # learned before the forecast was withheld, instead of a row of blanks.
    # `last_seen` stays None until the recent history is actually fetched:
    # None means "not applicable", {} means "fetched, and nobody qualified",
    # and the two withdraw coverage claims very differently.
    districts: list = []
    observed: dict = {}
    last_seen = None
    try:
        from pipeline.fetch_live_inputs import (
            fetch_gfm_observed,
            fetch_gfm_recent,
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

        p_event = None
        extras = None
        # None, not {}: outside core season the recent history is never
        # fetched, so there is no observation set to test coverage against.
        # An empty dict means "fetched, and nobody qualified", which correctly
        # withdraws every coverage claim; None means "not applicable".
        last_seen = None
        forecast_block = None
        model_note = ""
        if window["core_season"]:
            bundle = load_bundle()
            recent, recent_meta = fetch_gfm_recent(
                today_iso, days_back=forecast_live.HISTORY_DAYS
            )
            gfm_meta["history_days_fetched"] = recent_meta["days_fetched"]
            # Read before the gate, not after it. Every district that was
            # imaged at all carries its date and age, including the stale ones
            # eligibility excludes — and including on the cycles where the
            # forecast is withheld, which are exactly the cycles where a reader
            # most needs to see when each district was last looked at.
            last_seen = forecast_live.latest_observation(recent, today_iso)

            # Safety gate. Scoring the model on priors and climatology alone
            # when the imagery is missing produces a board of low numbers and a
            # note saying nothing is above threshold, which a reader takes as an
            # all-clear. Absence of imagery is absence of knowledge.
            publishable, coverage_reason = forecast_live.forecast_is_publishable(
                recent, today_iso, districts
            )
            gfm_meta["forecast_coverage"] = coverage_reason
            if not publishable:
                raise ForecastUnavailable(coverage_reason)

            X = forecast_live.build_live_features(
                recent,
                today_iso,
                districts,
                bundle["priors"],
                bundle["climatology"],
                bundle["adjacency"],
                threshold=bundle["threshold"],
                climo_fallback=bundle.get("climatology_fallback"),
                tau=bundle.get("excite_tau_days", forecast_live.EXCITE_TAU_DAYS),
                max_hops=bundle.get("excite_max_hops", forecast_live.EXCITE_MAX_HOPS),
            )
            proba = bundle["model"].predict_proba(
                X[list(bundle["feature_order"])].to_numpy(dtype=float)
            )[:, 1]
            model_score = pd.Series(proba, index=X.index)
            trans = forecast_live.transparent_score(X)
            # Drop the districts the satellite could not see BEFORE ranking.
            # Ranking them and nulling afterwards leaves the survivors holding
            # positions that were decided partly by rows nobody observed, and
            # leaves the alert count in the note including them.
            #
            # This uses the SAME set the publication gate just used, rather than
            # the cumulative window union it used to consult. The union counted
            # a district as covered on the strength of a single pass at the top
            # of the monsoon window, which meant a district could be ranked on
            # imagery nine days old that the gate's freshness rule never saw.
            eligible = forecast_live.eligible_districts(recent, today_iso)
            gfm_meta["eligible_districts"] = len(eligible)
            # ...and it is intersected with the window's acquisition footprint,
            # because eligibility and coverage are still two questions.
            #
            # The rolling history and the current window are different day
            # ranges, and on the first cycle of a new monsoon window they
            # disagree completely: every district can hold a one-day-old
            # observation from the window that just ended while the new
            # window's footprint has recorded no pass at all. That is what
            # happened on 14 Aug. The gate passed on the history, the rows were
            # built from the footprint and said not_observed twenty times over,
            # and the feed published a forecast block reporting "20 of 20
            # districts observed" above them.
            seen = nowcast.publishable_districts(X.index, eligible, observed)
            gfm_meta["publishable_districts"] = len(seen)
            if not seen:
                # No row can carry a score, so there is no forecast — and
                # saying so is not the same as publishing an empty one. A block
                # with a threshold and a validation record, sitting over twenty
                # unscored rows, reads as a forecast that found nothing rather
                # than as no forecast at all.
                raise ForecastUnavailable(
                    f"{len(eligible)} of {len(districts)} districts hold a recent "
                    f"observation, but the Sentinel-1 footprint records no pass "
                    f"covering any of them in the current window "
                    f"({window['window_start']} onwards), so no district can be "
                    f"scored"
                )
            model_score = model_score.loc[seen]
            trans = trans.loc[seen]
            ranked = forecast_live.rank_and_tier(
                model_score, trans, alert_threshold=bundle["alert_threshold"]
            )
            p_event = {r["district"]: r["p_event"] for r in ranked}
            extras = {
                r["district"]: {
                    "rank": r["rank"],
                    "tier": r["tier"],
                    "transparent_score": r["transparent_score"],
                    "latest_input": last_seen.get(r["district"], {}).get("latest"),
                    "input_age_days": last_seen.get(r["district"], {}).get("age_days"),
                }
                for r in ranked
            }
            forecast_block = {
                "kind": "district flood onset",
                "horizon_days": bundle["horizon_days"],
                "threshold_fraction": bundle["threshold"],
                "issued_for": today_iso,
                "definition": (
                    "model score for Copernicus GFM observing flooding above "
                    f"{bundle['threshold']:.1%} of district area on any of the "
                    f"next {bundle['horizon_days']} days, using only what was "
                    "known on the issue day"
                ),
                "calibration": (
                    "a ranking score, not a calibrated probability: it has not "
                    "been fitted to a reliability curve, so read the tier and "
                    "the rank rather than the number"
                ),
                "coverage": coverage_reason,
                "alert_threshold": bundle["alert_threshold"],
                "alert_rate": bundle["alert_rate"],
                "trained_years": bundle["trained_years"],
                "validation": (
                    "walk-forward, each season forecast using only earlier "
                    "seasons, with the alert threshold taken from inner "
                    "out-of-fold scores. At this operating point back-testing "
                    "raised about 24 alerts a season, roughly one in three "
                    "followed by flooding within three days, catching about "
                    "one onset in four. Season-level performance is "
                    "heterogeneous. Retrospective and post-selection; the 2026 "
                    "monsoon is the prospective test."
                ),
            }
            n_watch = sum(1 for r in ranked if r["tier"] == "watch")
            n_seen, n_all = len(ranked), len(X.index)
            scope = (
                ""
                if n_seen == n_all
                else (
                    f" Ranks are among the {n_seen} of {n_all} districts the "
                    f"satellite imaged this cycle; the rest carry no score."
                )
            )
            # Never open with an all-clear that nothing was looked at. "No
            # district is above the alert threshold today" used to lead the
            # note even when the satellite had imaged nobody, and the
            # correction arrived several sentences later, where a reader who
            # has already taken the first sentence as reassurance will not
            # reach it. That case no longer reaches this line at all: a cycle
            # with nothing to score raises ForecastUnavailable above and is
            # published as an absent forecast rather than as an empty one, so
            # the threshold statement below is only ever made about districts
            # that were actually imaged.
            model_note = (
                f"{n_watch} district(s) above the alert threshold."
                if n_watch
                else "No district is above the alert threshold today."
            ) + scope
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
            last_seen=last_seen,
            generated_utc=generated,
            window=window,
            sources={
                "forecast_inputs": "gfm",
                "labels": "gfm",
                "context_rain": rain_source,
                "context_reservoirs": res_source,
            },
            districts=districts,
            observed=observed,
            p_event=p_event,
            notes=notes,
            forecast=forecast_block,
            extras=extras,
        )
        _write(payload)
        _print_summary(payload, window, rain, reservoirs, res_source, gfm_meta)
        print(f"NOWCAST OK -> {OUT}")
    except ForecastUnavailable as unavailable:
        # Publish the observations, withhold the forecast, and say why in the
        # notes. Never emit a board of low scores built on no imagery.
        #
        # It used to say that and then pass `observed={}`, so every row went
        # out as acquisition_state "unknown" and the page could not name a
        # single district the satellite had missed. The footprint had already
        # been fetched and had already answered that question; throwing the
        # answer away on the one cycle a reader most needs it is the quiet
        # failure this file keeps warning about, committed by the handler
        # whose comment promises the opposite.
        try:
            payload = nowcast.build_nowcast_json(
                generated_utc=generated,
                window=nowcast.resolve_window(today_iso),
                sources={
                    "forecast_inputs": "gfm",
                    "labels": "gfm",
                    "context_rain": "unavailable",
                    "context_reservoirs": "unavailable",
                },
                districts=districts or _fallback_districts(),
                observed=observed,
                last_seen=last_seen,
                p_event=None,
                notes=(
                    "Forecast unavailable for this cycle: "
                    f"{unavailable}. No district-level risk is published, and "
                    "this is NOT an all-clear. Absence of satellite imagery is "
                    "absence of information."
                ),
                # The disclaimer travels inside the forecast block, not only in
                # the surrounding notes. A consumer that reads the block alone
                # sees "unavailable" plus a reason, and "the imagery is stale"
                # is not self-evidently different from "nothing is happening".
                forecast={
                    "kind": "district flood onset",
                    "status": "unavailable",
                    "reason": str(unavailable),
                    "note": (
                        "No forecast was produced this cycle. This is not "
                        "an all-clear: absence of a forecast is absence of "
                        "information, not evidence of calm."
                    ),
                },
            )
            _write(payload)
        except Exception:
            traceback.print_exc()
        print(f"NOWCAST UNAVAILABLE -> {OUT}")
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
