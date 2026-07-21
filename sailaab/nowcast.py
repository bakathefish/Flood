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
* assembles the EXACT 16 training features in training order
  (:data:`FEATURE_ORDER`, verified against ``data/models/forecaster_2025.joblib``
  by ``tests/test_nowcast.py``);
* reduces a GFM flood mask to per-district observed fraction / km² with the same
  cos²(lat) Web-Mercator area physics as the decade atlas that made the labels
  (``pipeline/fetch_gfm_decade.py``), so a live ``antecedent_fraction`` is
  in-domain with the trained target;
* shapes the locked ``monitor/nowcast.json`` schema.

The paddy decision (``docs/notes/forecaster.md``) is honoured here: the model was
trained ONLY on core-season windows (``window_start`` month-day >= ``07-25``).
Pre-core windows are out-of-domain, so :func:`build_nowcast_json` emits
``p_event = null`` for them and the ``activates`` countdown target instead.
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


def district_flood_stats(mask, labels, names, bounds, refwater=None) -> dict:
    """Per-district observed flood fraction and km² from a boolean flood ``mask``.

    ``refwater`` (permanent water) is subtracted first, exactly as the decade
    atlas did. Returns ``district -> {observed_fraction, observed_km2,
    flooded_ha, district_ha}``; ``observed_fraction`` is
    ``flooded_ha / district_ha`` (0.0 for an empty district).
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
        out[name] = {
            "observed_fraction": (f_ha / d_ha) if d_ha > 0 else 0.0,
            "observed_km2": f_ha / 100.0,
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
) -> dict:
    """Shape the locked ``monitor/nowcast.json`` payload.

    ``observed`` maps ``district -> {observed_fraction, observed_km2}`` (missing
    districts default to 0.0). ``p_event`` maps ``district -> probability`` when
    the window is core-season, or is ``None`` (pre-core / out-of-domain) in which
    case every ``p_event`` is emitted as ``null``. Rows carry all supplied
    districts, sorted by ``p_event`` (core) or ``observed_km2`` (pre-core), desc.
    """
    rows = []
    for name in districts:
        obs = observed.get(name) or {}
        frac = obs.get("observed_fraction")
        km2 = obs.get("observed_km2")
        pe = None
        if p_event is not None:
            pv = p_event.get(name)
            pe = None if pv is None else round(float(pv), 4)
        rows.append(
            {
                "district": name,
                "p_event": pe,
                "observed_fraction_window": (
                    None if frac is None else round(float(frac), 4)
                ),
                "observed_km2": None if km2 is None else round(float(km2), 1),
            }
        )

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

    return {
        "generated_utc": generated_utc,
        "window_start": window["window_start"],
        "window_end": window["window_end"],
        "core_season": bool(window["core_season"]),
        "activates": window.get("activates"),
        "sources": sources,
        "districts": rows,
        "notes": notes,
    }
