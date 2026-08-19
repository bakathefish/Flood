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


# A district is only called observed when nearly all of it was imaged. Half was
# a number I picked, and it certifies a district-wide zero while half the
# district was never seen. Whole-district claims need whole-district imagery.
MIN_OBSERVED_FRACTION = 0.95


def district_acquisition(
    labels,
    names,
    footprint,
    min_fraction: float = MIN_OBSERVED_FRACTION,
    unresolved=None,
) -> dict:
    """What share of each district a Sentinel-1 acquisition actually covered.

    ``footprint`` is the union of GFM's ``gfm_sentinel_1_footprint`` layer over
    the days in question: the boundaries of the imagery the product was made
    from. Intersecting it with the district labels answers the question the
    flood mask cannot, because an empty flood mask over a district looks the
    same whether the satellite imaged it and found nothing or never flew.

    Returns ``district -> {acquisition_fraction, state}`` where state is
    ``observed`` (at least ``min_fraction`` of the district imaged),
    ``partial`` (some imagery, but not enough to stand behind a district-wide
    number) or ``not_observed``. ``footprint=None`` means the layer could not
    be retrieved at all, which is ``unknown`` for every district: different
    from not observed, and both different from dry.
    """
    n = len(names)
    if footprint is None:
        return {
            name: {"acquisition_fraction": None, "state": "unknown"} for name in names
        }
    fp = np.asarray(footprint, dtype=bool)
    lab = np.asarray(labels)
    unres = None if unresolved is None else np.asarray(unresolved, dtype=bool)
    out = {}
    for i, name in enumerate(names, start=1):
        in_district = lab == i
        total = int(in_district.sum())
        if total == 0:
            out[name] = {"acquisition_fraction": None, "state": "unknown"}
            continue
        # The satellite imaged this district but we could not retrieve what was
        # under the imagery. That is an open question, not an empty one, and it
        # must not resolve to dry.
        if unres is not None and bool((in_district & unres).any()):
            out[name] = {
                "acquisition_fraction": round(
                    float((in_district & fp).sum()) / total, 4
                ),
                "state": "unresolved",
            }
            continue
        frac = float((in_district & fp).sum()) / total
        if frac >= min_fraction:
            state = "observed"
        elif frac > 0.0:
            state = "partial"
        else:
            state = "not_observed"
        out[name] = {"acquisition_fraction": round(frac, 4), "state": state}
    return out


def district_flood_stats(
    mask, labels, names, bounds, refwater=None, *, acquisition: dict | None = None
) -> dict:
    """Per-district observed flood fraction and km² from a boolean flood ``mask``.

    ``refwater`` (permanent water) is subtracted first, exactly as the decade
    atlas did. Returns ``district -> {covered, observed_fraction, observed_km2,
    flooded_ha, district_ha}``.

    Coverage comes from ``acquisition`` and from nothing else. An all-zero
    flood mask is ambiguous on its own: it looks identical whether the
    satellite imaged Punjab and found no water or every request failed, and
    reading the second as the first publishes a state-wide all-clear built on
    no imagery, which is the worst thing this file can do. Without an
    acquisition argument no district is covered and every value is null.

    There used to be a ``sensed`` flag here meaning "some request somewhere
    succeeded". It was never the right question — a successful response says
    nothing about whether this district was under the pass — and once the
    footprint layer arrived it stopped being read at all while its docstring
    went on describing behaviour that no longer happened.
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
        #
        # When the acquisition footprint is available it decides, per district,
        # and that is the honest answer: a district the satellite did not fly
        # over is not covered no matter how many other tiles came back. The
        # fetch-count fallback below is an upper bound and is only used when
        # the footprint layer could not be retrieved.
        if acquisition is not None:
            covered = acquisition.get(name, {}).get("state") == "observed"
        else:
            # No acquisition information at all. The old behaviour here was to
            # fall back on "some request somewhere succeeded", which is the
            # exact defect the footprint work exists to remove: it grants
            # coverage to every district after any single flood response.
            # Calling it an upper bound in prose does not make publishing a
            # zero on it safe, so nothing is covered when nothing is known.
            covered = False
        out[name] = {
            # A district absent from this pass has no pixels at all. Reporting
            # 0.0 there would be a false all-clear: each Sentinel-1 pass images
            # a strip, not the whole state, so "not imaged" and "imaged and dry"
            # must stay distinguishable all the way to the site.
            "covered": covered,
            # "unknown", not "sensed". The old fallback word survived the
            # footprint change and became a vocabulary the consumer does not
            # know, so on a footprint-outage cycle the whole feed was rejected
            # as malformed and the page listed nothing at all, where it used to
            # name every unimaged district. Failing closed is right; losing the
            # disclosure while doing it is the exact quiet failure this module
            # keeps warning about. Without a footprint there is no evidence of
            # acquisition, and "unknown" is the honest word for that.
            "acquisition_state": (
                acquisition.get(name, {}).get("state")
                if acquisition is not None
                else "unknown"
            ),
            "acquisition_fraction": (
                acquisition.get(name, {}).get("acquisition_fraction")
                if acquisition is not None
                else None
            ),
            "observed_fraction": (f_ha / d_ha) if covered else None,
            "observed_km2": (f_ha / 100.0) if covered else None,
            "flooded_ha": f_ha,
            "district_ha": d_ha,
        }
    return out


# --------------------------------------------------------------------------- #
# locked JSON schema
# --------------------------------------------------------------------------- #

# Everything a row can say about a district beyond the bare fact that nobody
# imaged it. An uncovered row carries none of them.
#
# This is the rule the cleanup below used to approximate by listing the three
# fields that had gone wrong most recently. Each time a new operational field
# was added the list was not, so the next field through was published on rows
# that had no observation behind it: ``latest_input`` and ``input_age_days``
# arrived after the list was written and were re-attached to uncovered rows by
# the extras merge, which put a date and an age on twenty districts the
# footprint said were never imaged. Stating the rule once means adding a field
# to the payload cannot silently exempt it.
UNCOVERED_NULL_FIELDS = (
    "p_event",
    "rank",
    "tier",
    "transparent_score",
    "latest_input",
    "input_age_days",
    "observed_fraction_window",
    "observed_km2",
)


def _evidence_inside_window(name, last_seen: dict, window_start) -> bool:
    """Whether the district's newest observation falls inside the window.

    ``recent`` only carries a district-day whose footprint cleared the coverage
    threshold on that date, so a date in ``last_seen`` means "properly imaged,
    on that day". The question this answers is whether any such day lies inside
    the window whose measurement the row is about to publish.

    Membership alone was not enough, and the gap is not hypothetical. In the
    first days of a window the rolling history still reaches back into the
    window that just ended, so a district could hold a two-day-old observation
    from the PREVIOUS window while the current window covered it only as a
    mosaic of partial passes. The row then published a window fraction earned
    by exactly the temporal mosaic MIN_OBSERVED_FRACTION exists to forbid, with
    its stated evidence pointing outside the window it was certifying.
    """
    latest = (last_seen.get(name) or {}).get("latest")
    if latest is None:
        return False
    return window_start is None or latest >= window_start


def coverage_is_earned(name, observed: dict, last_seen, window_start) -> bool:
    """Whether a district may present itself as covered, and carry a score.

    Three conditions, and each one has been the sole survivor of a defect:
    the flag is set, the state agrees with the flag, and there is an
    observation inside the window to point at. ``last_seen=None`` means the
    recent history was never fetched, which makes the third condition not
    applicable rather than failed.
    """
    obs = observed.get(name) or {}
    if obs.get("covered") is not True:
        return False
    # `covered` and `acquisition_state` are two spellings of one fact and the
    # consumer checks them against each other. A caller that sets one and not
    # the other is not making a claim this function can repair, so it fails
    # closed rather than upgrading the state to match the flag.
    if (obs.get("acquisition_state") or "unknown") != "observed":
        return False
    if last_seen is None:
        return True
    return _evidence_inside_window(name, last_seen, window_start)


def publishable_districts(
    order, eligible, observed: dict, last_seen=None, window_start=None
) -> list[str]:
    """Districts that may carry a score, in ``order``.

    Two separate things have to be true, and they are checked over two
    different observation sets because they are two different questions.
    ``eligible`` answers "is there a recent enough observation to score from",
    computed by :mod:`sailaab.forecast_live` over the rolling history. The
    acquisition state in ``observed`` answers "did a pass actually cover this
    district in the window we are publishing", computed from the Sentinel-1
    footprint. A score needs both, and the intersection is the only set the
    feed may present as scored.

    Taking the intersection here, before ranking, rather than letting
    :func:`build_nowcast_json` null the scores afterwards, is what keeps the
    forecast block's own coverage sentence describing the rows beside it. When
    the two sets diverged, the block went on reporting the gate's count while
    every row said not_observed, and the feed asserted both "20 of 20
    districts observed" and "nobody was imaged" in the same document.
    """
    return [
        name
        for name in order
        if name in eligible
        and coverage_is_earned(name, observed, last_seen, window_start)
    ]


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
    last_seen: dict | None = None,
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
        # ...but coverage from the window union alone is not enough to publish.
        #
        # The union combines partial passes taken on different days. Two passes
        # each imaging half a district, on opposite halves, union to "100%
        # covered" and can then certify a district-wide zero, which is exactly
        # what MIN_OBSERVED_FRACTION exists to forbid: a single pass must cover
        # the district, not a temporal mosaic. Such a row published
        # `covered: true` with a 0.0 flood fraction and no observation date at
        # all, and the map drew the zero.
        #
        # So a coverage claim needs an observation to point at. When the recent
        # history was fetched and this district is not in it, the claim is
        # withdrawn rather than published without evidence.
        acq_state = obs.get("acquisition_state") or "unknown"
        # The same predicate the ranking used, so a row cannot be built on one
        # answer while its score was decided on another.
        if covered and not coverage_is_earned(
            name, observed, last_seen, window.get("window_start")
        ):
            covered = False
            # The measurement goes with the claim. Leaving the fraction behind
            # would republish the mosaic reading under an uncovered row, which
            # is the same zero the map drew before, just relabelled.
            frac = km2 = None
            # ...and so does the STATE, which is the half this guard forgot.
            # `covered` is defined to the consumer as exactly
            # `acquisition_state == "observed"`, so withdrawing one and leaving
            # the other publishes a row that contradicts itself on the single
            # fact both fields describe, and the whole feed fails validation on
            # it. That is the same defect this guard was written to fix,
            # committed by the fix.
            #
            # "unresolved" is the honest word and the only legal one. The
            # footprint really did image this district, so the fraction stands
            # and neither "not_observed" (which demands 0.0) nor "unknown"
            # (which demands no fraction at all) can carry it; what could not
            # be resolved is what was under the imagery, which is precisely
            # what "unresolved" means everywhere else in this file.
            if acq_state == "observed":
                acq_state = "unresolved"
        pe = None
        if p_event is not None:
            pv = p_event.get(name)
            pe = None if pv is None else round(float(pv), 4)
        rows.append(
            {
                "district": name,
                "p_event": pe,
                "covered": covered,
                # `covered` is a boolean summary of a four-state answer. Publish
                # the state too, or a consumer cannot tell "half the district
                # was imaged" from "none of it was" from "the footprint layer
                # was unreachable", and all three collapse into one grey.
                "acquisition_state": acq_state,
                "acquisition_fraction": obs.get("acquisition_fraction"),
                # Every row states every operational field, null when it has
                # none. Omitting a key is not the same as saying null: it
                # leaves a consumer to guess whether the producer had nothing
                # to report or never considered the question, and a consumer
                # that guesses "nothing to report" prints reassurance.
                "rank": None,
                "tier": None,
                "transparent_score": None,
                # How old the imagery behind this row is. A score with no
                # visible age reads as current, and the whole reason this row
                # can exist without a score is that freshness is a separate
                # question from coverage. A district imaged nine days ago and
                # not since gets no score, and says so with a date rather than
                # by going blank.
                "latest_input": (last_seen or {}).get(name, {}).get("latest"),
                "input_age_days": (last_seen or {}).get(name, {}).get("age_days"),
                "observed_fraction_window": (
                    None if frac is None else round(float(frac), 4)
                ),
                "observed_km2": None if km2 is None else round(float(km2), 1),
            }
        )
        if extras and name in extras:
            rows[-1].update(extras[name])

        # The one place the uncovered rule is applied, and it is applied last.
        #
        # A district the satellite could not see gets no score, no rank, no
        # tier, no measurement and no observation date. The model will happily
        # return a number for it from priors and climatology alone, and that
        # number looks exactly like a real one; the extras merge above will
        # happily put it back after the row was built without it. So the rule
        # runs after everything that can write to the row, over the whole field
        # list rather than over the fields someone remembered.
        if not covered:
            for field in UNCOVERED_NULL_FIELDS:
                rows[-1][field] = None

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
            None if window.get("core_season") is None else bool(window["core_season"])
        ),
        "activates": window.get("activates"),
        "sources": sources,
        "districts": rows,
        "notes": notes,
    }
