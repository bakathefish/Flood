# sailaab/forecast_live.py
"""Inference for the daily flood forecast: features, baseline rule, ranking.

The forecast this supports is stated in `docs/notes/forecaster-daily.md`: for
each district, on the day the forecast is issued, will Copernicus GFM observe
flooding above the threshold on any of the next three days? Everything here is
causal by construction. A feature may only look at the issue date and earlier,
and the helpers drop anything dated later even if a caller hands it over, so a
late-arriving observation cannot silently turn a forecast into a hindcast.

Two scores are produced for every district, because the evaluation found they
are better at different jobs and neither dominates:

* the LEARNED score, which ranked district risk better by average precision in
  every season containing a flood;
* the TRANSPARENT rule, an unweighted rank-sum of the district's own water, its
  seasonal onset climatology and water observed in adjacent districts, which
  caught more distinct onsets at a fixed five-district alert budget.

The watch set is taken from the transparent rule, since that is the method that
performed better under the alert-budget objective, and the learned score
supplies the ranking. Publishing both, and saying which is used for what, is the
honest reflection of a result where the simple rule is not beaten outright.

No rainfall is used. Rain added no measurable incremental skill under this model
and validation protocol, so the live path does not depend on a rain feed at all.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from sailaab import config

# The order the model was fitted in. Inference must present columns in exactly
# this order; the nowcast driver asserts it against the saved bundle.
FEATURE_ORDER = (
    "prior_wet_days",
    "prior_max_fraction",
    "frac_now",
    "frac_max3d",
    "day_of_season",
    "neighbour",
    "season_climo",
    # Self-excitation by graph ring: how much flooding has recently happened in
    # this district, in the districts touching it, and two hops out, decayed
    # exponentially in time. The benchmark attributes most of the operational
    # gain to these three columns.
    "excite_h0",
    "excite_h1",
    "excite_h2",
)

EXCITE_TAU_DAYS = 3.0  # decay time, matched to the upstream routing time
EXCITE_MAX_HOPS = 2
HISTORY_DAYS = 21  # enough for the 3-day state and for the excitation to decay

STATE_DAYS = 3  # trailing window for the district's own water and its neighbours


def season_day_index(issue_date, season_start_md: str = config.SEASON_START_MD) -> int:
    """Days since the monsoon season opened, 0 on the first day.

    Matches the training frame, where ``day_of_season`` counts rows from the
    season start. Negative before the season opens, which the caller treats as
    out of domain rather than clamping.
    """
    d = pd.Timestamp(issue_date)
    start = pd.Timestamp(f"{d.year}-{season_start_md}")
    return int((d - start).days)


def build_live_features(
    recent: pd.DataFrame,
    issue_date,
    districts,
    priors: dict,
    climo: dict,
    adjacency: dict,
    threshold: float | None = None,
    climo_fallback: float | None = None,
    tau: float = EXCITE_TAU_DAYS,
    max_hops: int = EXCITE_MAX_HOPS,
) -> pd.DataFrame:
    """Feature frame for one issue day, one row per district, in FEATURE_ORDER.

    ``recent`` is a tidy ``date, district, fraction`` frame of observed flooded
    fractions. Rows dated after ``issue_date`` are discarded. A district with no
    observation for the issue day yields NaN rather than 0.0: an unimaged
    district is unknown, not dry, and the difference must survive all the way to
    the model.

    ``priors`` maps district to the susceptibility features, ``climo`` maps
    ``(district, week_of_season)`` to the training onset rate, and ``adjacency``
    maps district to its neighbours. Missing entries yield NaN.
    """
    issue = pd.Timestamp(issue_date)
    r = recent.copy()
    r["date"] = pd.to_datetime(r["date"])
    r = r[r["date"] <= issue]  # never look past the issue date

    day = int(season_day_index(issue))
    week = day // 7

    today = r[r["date"] == issue].set_index("district")["fraction"]
    window_start = issue - pd.Timedelta(days=STATE_DAYS - 1)
    recent_win = r[r["date"] >= window_start]
    max3 = recent_win.groupby("district")["fraction"].max()

    # Self-excitation from the observed history. Computed on the trimmed frame,
    # so it can only ever see days at or before the issue date.
    excite = {}
    if threshold is not None and len(r):
        from sailaab.hazard import excitation_features

        ex = excitation_features(
            r[["date", "district", "fraction"]],
            {d: adjacency.get(d, []) for d in districts},
            threshold=threshold,
            tau=tau,
            max_hops=max_hops,
        )
        ex = ex[ex["date"] == issue]
        excite = ex.set_index("district").to_dict("index")

    rows = {}
    for name in districts:
        ex_row = excite.get(name, {})
        nbrs = adjacency.get(name, [])
        nbr_vals = max3.reindex(nbrs).dropna() if nbrs else pd.Series(dtype=float)
        p = priors.get(name, {})
        rows[name] = {
            "prior_wet_days": float(p["prior_wet_days"]) if p else np.nan,
            "prior_max_fraction": float(p["prior_max_fraction"]) if p else np.nan,
            "frac_now": float(today[name]) if name in today.index else np.nan,
            "frac_max3d": float(max3[name]) if name in max3.index else np.nan,
            "day_of_season": float(day),
            "neighbour": float(nbr_vals.max()) if len(nbr_vals) else np.nan,
            # Training filled an absent (district, week) cell with the global
            # onset rate, so live must fill it the same way. Emitting NaN here
            # would send the model down a missing-value branch that never
            # existed at fit time.
            "season_climo": float(
                climo.get(
                    (name, week),
                    np.nan if climo_fallback is None else climo_fallback,
                )
            ),
            "excite_h0": float(ex_row.get("excite_h0", np.nan)),
            "excite_h1": float(ex_row.get("excite_h1", np.nan)),
            "excite_h2": float(ex_row.get("excite_h2", np.nan)),
        }
    return pd.DataFrame.from_dict(rows, orient="index")[list(FEATURE_ORDER)]


def transparent_score(features: pd.DataFrame) -> pd.Series:
    """Unweighted rank-sum of own water, seasonal climatology and neighbours.

    Deliberately unfitted. It is the baseline the learned model has to justify
    itself against, and at a fixed alert budget it caught more distinct onsets,
    so it also serves as the operational watch list rather than only as a foil.
    Missing components rank lowest rather than removing the district.
    """
    parts = []
    for col in ("frac_now", "season_climo", "neighbour"):
        s = features[col] if col in features else pd.Series(np.nan, index=features.index)
        parts.append(s.rank(pct=True, na_option="bottom"))
    return sum(parts)


def rank_and_tier(
    model_score: pd.Series,
    transparent: pd.Series,
    k: int = 5,
    alert_threshold: float | None = None,
) -> list[dict]:
    """Per-district rows ordered by the learned score, with an operating tier.

    ``watch``    the learned score is at or above ``alert_threshold``, the
                 operating point the benchmark measured. At that point the model
                 issued roughly seven alerts a season and four in five were
                 followed by a flood within three days, which is why the alert
                 is a threshold rather than a fixed number of districts: warning
                 five districts every day, including through quiet weeks, sends
                 almost every alert into an empty sky;
    ``elevated`` inside the learned model's top ``k`` but below the threshold,
                 so it leads the ranking on a day that carries no real signal;
    ``low``      neither.

    When no threshold is supplied the tiers fall back to the transparent rule's
    top ``k``, which is the behaviour used before an operating point existed.
    """
    idx = list(transparent.index)
    m = model_score.reindex(idx)
    t = transparent.reindex(idx)

    if alert_threshold is None:
        watch = set(t.dropna().sort_values(ascending=False).head(k).index)
    else:
        watch = set(m.dropna()[m.dropna() >= alert_threshold].index)
    model_top = set(m.dropna().sort_values(ascending=False).head(k).index)

    order = m.sort_values(ascending=False, na_position="last").index
    out = []
    for i, name in enumerate(order, start=1):
        val = m[name]
        if name in watch:
            tier = "watch"
        elif name in model_top:
            tier = "elevated"
        else:
            tier = "low"
        out.append(
            {
                "district": name,
                "rank": i,
                "p_event": None if pd.isna(val) else float(val),
                "transparent_score": None if pd.isna(t[name]) else float(t[name]),
                "tier": tier,
            }
        )
    return out


# Minimum share of districts that must carry a fresh observation before a
# statewide board is publishable at all, and how old the newest observation may
# be. Both are deliberately strict: this system's failure mode of record is
# turning "the satellite did not look" into "there is no water".
MIN_COVERAGE = 0.5
MAX_STALENESS_DAYS = 3


def forecast_is_publishable(recent, issue_date, districts) -> tuple[bool, str]:
    """Whether the observations support publishing a forecast at all.

    Returns ``(False, reason)`` when the imagery is absent, too sparse or too
    old. The caller must then publish an explicit unavailable state rather than
    scoring the model on priors and climatology alone, because a model fed only
    static features will happily report that nothing is above the alert
    threshold, and that reads to a user as an all-clear.
    """
    issue = pd.Timestamp(issue_date)
    if recent is None or len(recent) == 0:
        return False, "no satellite observations were retrieved"

    r = recent.copy()
    r["date"] = pd.to_datetime(r["date"])
    r = r[r["date"] <= issue]
    if r.empty:
        return False, "no satellite observations at or before the issue date"

    newest = r["date"].max()
    age = (issue - newest).days
    if age > MAX_STALENESS_DAYS:
        return False, (
            f"newest observation is stale: {age} days old "
            f"({newest.date()}), limit {MAX_STALENESS_DAYS}"
        )

    fresh = r[r["date"] >= issue - pd.Timedelta(days=MAX_STALENESS_DAYS)]
    covered = fresh["district"].nunique()
    total = len(list(districts)) or 1
    if covered / total < MIN_COVERAGE:
        return False, (
            f"only {covered} of {total} districts have a recent observation, "
            f"below the {MIN_COVERAGE:.0%} floor"
        )
    return True, f"{covered} of {total} districts observed within {age} day(s)"
