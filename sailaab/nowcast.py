# sailaab/nowcast.py
"""Pure logic for the live district flood-risk nowcast.

No IO, no network, no model loading — deterministic date/pandas/numpy transforms
only. The live fetchers (Open-Meteo rain, keyless GFM WMS observed extent,
data.gov.in CWC reservoirs) and the committed-joblib load live in
``pipeline/fetch_live_inputs.py`` + ``pipeline/nowcast.py``; this module:

* resolves the current monsoon window (and its two antecedent windows) from a
  date, reusing the ``sailaab.windows`` grid and the ``sailaab.frequency``
  half-open window rule — so ``week_of_season`` and the core-season flag are the
  *same* definitions the forecaster trained on;
* assembles the retired 16-feature vector (:data:`FEATURE_ORDER`) that the
  superseded 10-day-window model consumed. That model is no longer deployed;
  the live forecaster reads ten satellite-only features declared in
  ``sailaab/forecast_live.py``. The assembly below is kept only so the
  historical tests that pin the old bundle keep running;
* reduces a GFM flood mask to per-district observed fraction / km² with the same
  cos²(lat) Web-Mercator area physics as the decade atlas that made the labels
  (``pipeline/fetch_gfm_decade.py``), so a live ``antecedent_fraction`` is
  in-domain with the trained target;
* shapes the locked ``monitor/nowcast.json`` schema.

The paddy decision (``docs/notes/forecaster.md``) is honoured here: the model was
trained ONLY on core-season windows (``window_start`` month-day >= ``07-25``).
Pre-core windows are out-of-domain, so :func:`build_nowcast_json` emits
``p_event = null`` for them and the ``activates`` countdown target instead.

Despite its name, ``p_event`` is an uncalibrated ranking score, not a
probability. The field name is kept because the published schema is locked.
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np

from sailaab.forecast_features import PADDY_CUTOFF_MD
from sailaab.frequency import window_index
from sailaab.windows import monsoon_windows

# --- the 16 trained features, in training order (mirrors the committed joblib's
#     ``features`` list; guarded against drift by tests/test_nowcast.py) --------
RAIN_FEATURES = [
    "punjab_mm",
    "upstream_mm",
    "punjab_mm_lag1",
    "upstream_mm_lag1",
    "punjab_mm_lag2",
    "upstream_mm_lag2",
]
RESERVOIR_FEATURES = [
    "bhakra_delta",
    "bhakra_storage",
    "pong_delta",
    "pong_storage",
    "ranjit_sagar_delta",
    "ranjit_sagar_storage",
]
PRIOR_FEATURES = [
    "prior_mean_annual_flooded_ha",
    "prior_seasons_with_fraction_gt2pct",
]
FEATURE_ORDER = (
    RAIN_FEATURES
    + RESERVOIR_FEATURES
    + ["antecedent_fraction", "week_of_season"]
    + PRIOR_FEATURES
)
assert len(FEATURE_ORDER) == 16, FEATURE_ORDER


def _to_iso(d) -> str:
    """Coerce a ``date`` / ``datetime`` / ISO-ish string to a ``YYYY-MM-DD`` str."""
    if isinstance(d, str):
        return d[:10]
    if hasattr(d, "date") and not isinstance(d, date):  # datetime
        return d.date().isoformat()
    return d.isoformat()


def _num(x) -> float:
    """None / '' / 'NA' / NaN -> ``np.nan``; everything else -> float."""
    if x is None:
        return float("nan")
    if isinstance(x, str):
        s = x.strip()
        if s == "" or s.upper() == "NA":
            return float("nan")
        return float(s)
    try:
        v = float(x)
    except (TypeError, ValueError):
        return float("nan")
    return v


def activation_date(year: int, cutoff_md: str = PADDY_CUTOFF_MD) -> str | None:
    """ISO date the model activates: the first monsoon window whose ``window_start``
    month-day reaches the paddy cutoff (``07-25``). ``None`` if no such window."""
    for w0, _w1 in monsoon_windows(year):
        if w0[5:] >= cutoff_md:
            return w0
    return None


def resolve_window(
    today, year: int | None = None, cutoff_md: str = PADDY_CUTOFF_MD
) -> dict:
    """Resolve the monsoon window that contains ``today`` (half-open ``[start, end)``).

    Returns a dict with the current window, its two antecedent windows (for the
    rain lags and the GFM antecedent fraction), ``week_of_season`` (the window's
    0-based index within the season — identical to the forecaster's
    ``groupby([district, year]).cumcount()``), the ``core_season`` flag, and the
    ``activates`` countdown date. If ``today`` falls outside the season it is
    clamped to the first/last window and ``clamped`` records which end.
    """
    today_iso = _to_iso(today)
    if year is None:
        year = int(today_iso[:4])
    windows = monsoon_windows(year)

    idx = window_index(today_iso, windows)
    clamped = None
    if idx is None:
        if today_iso < windows[0][0]:
            idx, clamped = 0, "before_season"
        else:
            idx, clamped = len(windows) - 1, "after_season"

    w0, w1 = windows[idx]
    prev = windows[idx - 1] if idx - 1 >= 0 else None
    prev2 = windows[idx - 2] if idx - 2 >= 0 else None
    md = w0[5:]
    return {
        "year": year,
        "window_index": idx,
        "week_of_season": idx,
        "window_start": w0,
        "window_end": w1,
        "window_md": md,
        "core_season": md >= cutoff_md,
        "activates": activation_date(year, cutoff_md),
        "prev_window": prev,
        "prev2_window": prev2,
        "clamped": clamped,
        "today": today_iso,
    }


def window_days(start: str, end: str, upto=None) -> list[str]:
    """ISO calendar days of the half-open window ``[start, end)``.

    With ``upto`` given, the list is truncated at ``min(upto, end-1)`` inclusive —
    used to pull only the current window's days *so far*. Returns ``[]`` when
    ``upto`` precedes ``start``.
    """
    d0 = date.fromisoformat(start)
    last = date.fromisoformat(end) - timedelta(days=1)
    if upto is not None:
        u = date.fromisoformat(_to_iso(upto))
        if u < last:
            last = u
    out = []
    cur = d0
    while cur <= last:
        out.append(cur.isoformat())
        cur += timedelta(days=1)
    return out


def build_feature_frame(
    districts,
    rain: dict,
    reservoirs: dict,
    antecedent: dict,
    week_of_season: int,
    priors: dict,
):
    """Assemble a one-row-per-district frame with EXACTLY :data:`FEATURE_ORDER`
    columns in training order — the vector the committed XGBoost consumes.

    Parameters
    ----------
    districts : sequence of GAUL district names (defines row order / index).
    rain : dict carrying the 6 :data:`RAIN_FEATURES` (statewide, identical across
        districts). Missing / ``None`` -> ``NaN``.
    reservoirs : dict carrying the 6 :data:`RESERVOIR_FEATURES` (identical across
        districts). Missing / ``None`` / ``NaN`` -> ``NaN`` (XGBoost-native).
    antecedent : dict ``district -> antecedent_fraction`` (previous window's
        observed flood fraction). Missing -> ``NaN``.
    week_of_season : int, constant across districts (the current window index).
    priors : dict ``district -> {prior_mean_annual_flooded_ha,
        prior_seasons_with_fraction_gt2pct}`` (bare ``mean_annual_flooded_ha`` /
        ``seasons_with_fraction_gt2pct`` keys are also accepted). Missing -> ``NaN``.
    """
    import pandas as pd

    rows = []
    for name in districts:
        row = {k: _num(rain.get(k)) for k in RAIN_FEATURES}
        row.update({k: _num(reservoirs.get(k)) for k in RESERVOIR_FEATURES})
        row["antecedent_fraction"] = _num(antecedent.get(name))
        row["week_of_season"] = float(week_of_season)
        pr = priors.get(name, {}) if isinstance(priors, dict) else {}
        row["prior_mean_annual_flooded_ha"] = _num(
            pr.get("prior_mean_annual_flooded_ha", pr.get("mean_annual_flooded_ha"))
        )
        row["prior_seasons_with_fraction_gt2pct"] = _num(
            pr.get(
                "prior_seasons_with_fraction_gt2pct",
                pr.get("seasons_with_fraction_gt2pct"),
            )
        )
        rows.append(row)
    return pd.DataFrame(rows, columns=FEATURE_ORDER, index=list(districts))


# --------------------------------------------------------------------------- #
# GFM flood-mask -> per-district observed fraction / km²
# (same cos²(lat) Web-Mercator physics as pipeline/fetch_gfm_decade.py, so a live
#  antecedent_fraction is in-domain with the trained target)
# --------------------------------------------------------------------------- #
def row_pixel_ha(bounds, nrows: int, ncols: int) -> np.ndarray:
    """Per-row ground area of one pixel, in hectares, for a north-up EPSG:3857
    grid — the Web-Mercator ``cos²(lat)`` correction applied per row (matches
    :func:`sailaab.gfm.web_mercator_area_km2`)."""
    minx, miny, maxx, maxy = bounds
    px = (maxx - minx) / ncols
    py = (maxy - miny) / nrows
    r_earth = 6378137.0
    rows = np.arange(nrows)
    y_center = maxy - (rows + 0.5) * py
    lat = 2.0 * np.arctan(np.exp(y_center / r_earth)) - np.pi / 2.0
    cos2 = np.cos(lat) ** 2
    return (px * py * cos2) / 1.0e4  # m² -> ha


def _areas_ha(mask, labels, row_ha, n_labels: int) -> np.ndarray:
    """Vectorised per-label hectares of ``True`` pixels in ``mask`` (index 1..N;
    0 = background). ``mask`` may be an all-True array to get district totals."""
    mask = np.asarray(mask, dtype=bool)
    labels = np.asarray(labels)
    weight = np.broadcast_to(row_ha[:, None], mask.shape)
    sel = mask & (labels > 0)
    return np.bincount(
        labels[sel].ravel(),
        weights=weight[sel].ravel(),
        minlength=n_labels + 1,
    )


def district_flood_stats(
    mask, labels, names, bounds, refwater=None, *, sensed: bool = True
) -> dict:
    """Per-district observed flood fraction and km² from a boolean flood ``mask``.

    ``refwater`` (permanent water) is subtracted first, exactly as the decade
    atlas did. Returns ``district -> {covered, observed_fraction, observed_km2,
    flooded_ha, district_ha}``.

    ``sensed`` says whether any satellite observation actually came back for
    this window. It has to be passed in, because an all-zero flood mask is
    ambiguous on its own: it looks identical whether the satellite imaged
    Punjab and found no water, or every request to the service failed. Reading
    the second case as the first publishes a state-wide all-clear built on no
    imagery at all, which is the single worst thing this file can do. When
    ``sensed`` is False no district is covered and every value is null.
    """
    m = np.asarray(mask, dtype=bool)
    if refwater is not None:
        m = m & ~np.asarray(refwater, dtype=bool)
    nrows, ncols = m.shape
    rh = row_pixel_ha(bounds, nrows, ncols)
    n = len(names)
    district_ha = _areas_ha(np.ones_like(m), labels, rh, n)
    flooded_ha = _areas_ha(m, labels, rh, n)
    out = {}
    for i, name in enumerate(names, start=1):
        d_ha = float(district_ha[i])
        f_ha = float(flooded_ha[i])
        # Coverage is earned by an observation, not by the district polygon
        # having pixels: district_ha is computed from a constant raster, so on
        # its own it is true for every district on every run, imagery or not.
        covered = sensed and d_ha > 0
        out[name] = {
            # A district absent from this pass has no pixels at all. Reporting
            # 0.0 there would be a false all-clear: each Sentinel-1 pass images
            # a strip, not the whole state, so "not imaged" and "imaged and dry"
            # must stay distinguishable all the way to the site.
            "covered": covered,
            "observed_fraction": (f_ha / d_ha) if covered else None,
            "observed_km2": (f_ha / 100.0) if covered else None,
            "flooded_ha": f_ha,
            "district_ha": d_ha,
        }
    return out


# --------------------------------------------------------------------------- #
# locked JSON schema
# --------------------------------------------------------------------------- #
def build_nowcast_json(
    *,
    generated_utc: str,
    window: dict,
    sources: dict,
    districts,
    observed: dict,
    p_event: dict | None = None,
    notes: str = "",
    forecast: dict | None = None,
    extras: dict | None = None,
) -> dict:
    """Shape the locked ``monitor/nowcast.json`` payload.

    ``observed`` maps ``district -> {observed_fraction, observed_km2}`` (missing
    districts default to 0.0). ``p_event`` maps ``district -> score`` when the
    window is core-season, or is ``None`` (pre-core / out-of-domain) in which
    case every ``p_event`` is emitted as ``null``. Despite the name, the value
    is an uncalibrated ranking score, not a probability: it has never been
    fitted to a reliability curve, so it orders districts against each other
    and nothing more. The field name is kept because the published schema is
    locked. Rows carry all supplied districts, sorted by ``p_event`` (core) or
    ``observed_km2`` (pre-core), desc.

    ``forecast`` is an optional block describing what the score MEANS: the
    horizon, the threshold and the fact that it is a ranking rather than a
    calibrated probability. It is emitted verbatim so the published feed is
    self-describing and a reader cannot mistake the number for a percentage
    chance. ``extras`` maps ``district -> dict`` of additional per-district
    fields (rank, tier, the transparent rule's score) merged into each row.
    Both are optional so callers written against the older schema keep working.
    """
    rows = []
    for name in districts:
        obs = observed.get(name) or {}
        frac = obs.get("observed_fraction")
        km2 = obs.get("observed_km2")
        # Coverage defaults to False. Defaulting to True fails open: a caller
        # that forgot to set it publishes a district as observed when nobody
        # knows whether it was, and the consumer reads a number that has no
        # imagery behind it.
        covered = bool(obs.get("covered", False))
        pe = None
        if p_event is not None:
            pv = p_event.get(name)
            pe = None if pv is None else round(float(pv), 4)
        # A district the satellite could not see gets no score, no rank and no
        # tier. The model will happily return a number for it from priors and
        # climatology alone, and that number looks exactly like a real one.
        # Withholding it at the producer means no consumer can rank it, and
        # surfacing it downstream is not a substitute for never emitting it.
        if not covered:
            pe = None
        rows.append(
            {
                "district": name,
                "p_event": pe,
                "covered": covered,
                "observed_fraction_window": (
                    None if frac is None else round(float(frac), 4)
                ),
                "observed_km2": None if km2 is None else round(float(km2), 1),
            }
        )
        if extras and name in extras:
            rows[-1].update(extras[name])
            # Extras carry the operational fields. An uncovered district must
            # not receive them either, or it re-enters the ranking through the
            # side door with a rank and a reassuring tier.
            if not covered:
                for field in ("rank", "tier", "transparent_score"):
                    if field in rows[-1]:
                        rows[-1][field] = None
                rows[-1]["p_event"] = None

    def _f(x, default):
        return default if x is None else x

    if p_event is not None:
        rows.sort(
            key=lambda r: (
                -_f(r["p_event"], -1.0),
                -_f(r["observed_km2"], 0.0),
                r["district"],
            )
        )
    else:
        rows.sort(key=lambda r: (-_f(r["observed_km2"], 0.0), r["district"]))

    payload_forecast = {"forecast": forecast} if forecast else {}
    return {
        **payload_forecast,
        "generated_utc": generated_utc,
        "window_start": window["window_start"],
        "window_end": window["window_end"],
        # ``None`` survives as null rather than collapsing to False. A reader
        # that cannot tell "outside the season" from "we could not work out
        # what season it is" will render a failed run as a benign off-season
        # state, which is an all-clear by another name.
        "core_season": (
            None
            if window.get("core_season") is None
            else bool(window["core_season"])
        ),
        "activates": window.get("activates"),
        "sources": sources,
        "districts": rows,
        "notes": notes,
    }
