# pipeline/run_forecaster_daily.py
"""Daily-issue district flood forecaster, evaluated at honest issue times.

What changed from the window forecaster, and why
------------------------------------------------
The window model scored a ten-day box using rain drawn from inside that same
box, so it could not support a lead-time claim, and it collapsed a decade into
seven windows per district-season, leaving ten onset transitions in three event
seasons. That is too little to select a model on.

This runs the forecast the way it would actually be issued. On every monsoon day
from 25 July, for every district that is not already flooded, using only data
available by the end of that day, it predicts whether the district crosses the
flood threshold within the next three days.

Two pre-declared choices, both fixed before any model was fitted:

*Threshold 0.5% of district area.* The committed 2% threshold was set for the
window product, where ten days of observations are unioned before the fraction
is computed. A single-day snapshot and a ten-day union are different quantities,
so reusing 2% for a daily reading demands roughly 40 to 100 square kilometres of
standing water in one satellite pass. 0.5% is 10 to 25 square kilometres, which
is still thousands of acres of inundated land. The full grid 0.2 / 0.5 / 1 / 2%
is reported as sensitivity, not searched for the best number.

*Horizon 3 days.* Rain falling on the upstream Himalayan catchments reaches the
Punjab plains in roughly one to three days, and a dam release reaches the
downstream reaches inside a day or two. A three-day horizon matches the routing
time; 1, 2 and 5 are reported alongside.

Every feature is a trailing quantity ending on the issue date. Nothing after the
issue date can enter, which is what makes the lead time real.

Run: python -m pipeline.run_forecaster_daily
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from sailaab.forecast_daily import (
    build_climatology,
    climatology_percentile,
    dry_at_issue,
    forward_event,
    trailing_sums,
)
from sailaab.forecast_v2 import (
    block_bootstrap_ci,
    brier_skill,
    quiet_window_alert_rate,
    recall_at_k,
)

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

FLOOD_DAILY = DATA / "gfm_district_daily_2015_2025.csv"
RAIN_DAILY = DATA / "rain_district_daily_2015_2025.csv"
RAIN_CLIMO = DATA / "rain_district_daily_1961_2025.csv"
BOXES = DATA / "rain_daily_boxes_2015_2025.csv"
GFM_PROGRESS = DATA / "gfm" / "_decade_progress.csv"

OUT = DATA / "forecaster_daily_results.csv"
OUT_OOF = DATA / "forecaster_daily_oof.csv"

SEED = 20260806
CORE_MD = "07-25"  # past rice transplanting, as for the window products
THRESHOLD = 0.005  # pre-declared, see module docstring
HORIZON = 3  # pre-declared
THRESHOLD_GRID = (0.002, 0.005, 0.01, 0.02)
HORIZON_GRID = (1, 2, 3, 5)
C_GRID = (0.01, 0.1, 1.0)

RAIN_F = ["rain_1d", "rain_3d", "rain_7d", "rain_14d"]
PCTL_F = ["rain_3d_pctl", "rain_7d_pctl"]
UP_F = ["up_1d", "up_3d", "up_7d"]
STATE_F = ["frac_now", "frac_max3d"]
PRIOR_F = ["prior_wet_days", "prior_max_fraction"]
SEASON_F = ["day_of_season"]
# Observation cadence. GFM reports flooding only where a satellite acquisition
# covered the ground, and a day with no detection can mean either no water or no
# pass. So "water is observed here within three days" is partly a statement about
# when the satellite next looks. These features describe that cadence and nothing
# about the district, which makes a model built on them alone the sharpest null
# available: any skill above it is skill the observation schedule cannot explain.
TIMING_F = ["obs_active_now", "obs_active_3d", "obs_active_7d"]


def _logreg(C=0.1):
    return make_pipeline(
        SimpleImputer(strategy="median"),
        StandardScaler(),
        LogisticRegression(C=C, max_iter=1000, class_weight="balanced"),
    )


def build_frame(with_rain: bool = True) -> pd.DataFrame:
    """Issue-time feature frame: one row per district per monsoon day.

    ``with_rain=False`` skips the 65-year rainfall climatology, which is by
    far the most expensive step and which the selected model does not use,
    since rainfall added no measurable incremental skill. The rain columns
    are still present but empty, so callers that name them do not break.
    """
    flood = pd.read_csv(FLOOD_DAILY, parse_dates=["date"])
    flood["year"] = flood["date"].dt.year

    rain = pd.read_csv(RAIN_DAILY, parse_dates=["date"])
    rain = trailing_sums(rain, windows=(1, 3, 7, 14))

    if with_rain:
        print("building 65-year district rainfall climatology ...")
        climo_daily = pd.read_csv(RAIN_CLIMO, parse_dates=["date"])
        climo = build_climatology(climo_daily, windows=(3, 7), halfwidth=10)
        rain = climatology_percentile(rain, climo, windows=(3, 7))
    else:
        for c in PCTL_F:
            rain[c] = np.nan

    boxes = pd.read_csv(BOXES, parse_dates=["date"]).sort_values("date")
    for w in (1, 3, 7):
        boxes[f"up_{w}d"] = boxes["upstream_mm"].rolling(w, min_periods=1).sum()

    df = flood.merge(
        rain[["date", "district", "api_mm"] + RAIN_F + PCTL_F],
        on=["date", "district"],
        how="left",
        validate="1:1",
    ).merge(boxes[["date"] + UP_F], on="date", how="left", validate="m:1")

    # statewide acquisition cadence, from the fetcher's own probe log
    prog = pd.read_csv(GFM_PROGRESS, parse_dates=["day"]).rename(
        columns={"day": "date"}
    )
    prog["obs_active_now"] = (prog["probe_px"] > 0).astype(float)
    prog = prog.sort_values("date")
    for w in (3, 7):
        prog[f"obs_active_{w}d"] = (
            prog["obs_active_now"].rolling(w, min_periods=1).sum()
        )
    df = df.merge(
        prog[["date"] + TIMING_F], on="date", how="left", validate="m:1"
    )

    df = df.sort_values(["district", "year", "date"]).reset_index(drop=True)
    g = df.groupby(["district", "year"], sort=False)["fraction"]
    df["frac_now"] = df["fraction"]
    df["frac_max3d"] = g.transform(lambda s: s.rolling(3, min_periods=1).max())
    df["day_of_season"] = df.groupby(["district", "year"], sort=False).cumcount()
    df["md"] = df["date"].dt.strftime("%m-%d")
    return df


def _fold_prior(df: pd.DataFrame, train_years, threshold: float) -> pd.DataFrame:
    """District susceptibility from training years only."""
    tr = df[df["year"].isin(train_years)]
    per = tr.groupby(["district", "year"]).agg(
        wet_days=("fraction", lambda s: int((s > threshold).sum())),
        max_fraction=("fraction", "max"),
    )
    out = per.groupby("district").agg(
        prior_wet_days=("wet_days", "mean"),
        prior_max_fraction=("max_fraction", "mean"),
    )
    idx = pd.Index(sorted(df["district"].unique()), name="district")
    return out.reindex(idx).fillna(0.0).reset_index()


VARIANTS = {
    "persistence": None,
    "observation_timing": TIMING_F + SEASON_F,
    "prior_only": PRIOR_F + SEASON_F,
    "state_only": STATE_F,
    "rain_only": RAIN_F + UP_F,
    "rain_climatology": RAIN_F + PCTL_F + UP_F,
    # No rainfall at all: how flood-prone the district is, how much sub-threshold
    # water it already carries, and where in the season it sits.
    "prior_state_season": PRIOR_F + STATE_F + SEASON_F,
    "full": RAIN_F + PCTL_F + UP_F + STATE_F + PRIOR_F + SEASON_F,
    "full_plus_timing": (
        RAIN_F + PCTL_F + UP_F + STATE_F + PRIOR_F + SEASON_F + TIMING_F
    ),
}


def _fit_predict(feats, tr, te, nested_years=None):
    """Fit on ``tr`` and score ``te``.

    ``nested_years`` turns on an inner leave-one-year-out sweep over the
    regularisation grid, run on the training years alone so the judged year
    never influences the choice. The frames are converted to arrays once up
    front: re-slicing a pandas frame inside the sweep dominated the runtime and
    turned a whole-decade evaluation into an overnight job.
    """
    if feats is None:
        return te["frac_now"].fillna(0.0).to_numpy()
    ytr = tr["y"].to_numpy(dtype=float)
    if len(np.unique(ytr)) < 2:
        return np.full(len(te), np.nan)

    Xtr = tr[feats].to_numpy(dtype=float)
    Xte = te[feats].to_numpy(dtype=float)

    if nested_years is None:
        return _logreg(0.1).fit(Xtr, ytr).predict_proba(Xte)[:, 1]

    yrs = np.asarray(nested_years)
    best, best_ap = C_GRID[0], -np.inf
    for C in C_GRID:
        preds, truths = [], []
        for inner in np.unique(yrs):
            m = yrs != inner
            if len(np.unique(ytr[m])) < 2 or (~m).sum() == 0:
                continue
            mdl = _logreg(C).fit(Xtr[m], ytr[m])
            preds.append(mdl.predict_proba(Xtr[~m])[:, 1])
            truths.append(ytr[~m])
        if not preds:
            continue
        yy, pp = np.concatenate(truths), np.concatenate(preds)
        if len(np.unique(yy)) < 2:
            continue
        ap = average_precision_score(yy, pp)
        if ap > best_ap:
            best_ap, best = ap, C
    return _logreg(best).fit(Xtr, ytr).predict_proba(Xte)[:, 1]


def _candidates(
    d: pd.DataFrame, threshold: float, hysteresis: bool, *, require_observed: bool = True
) -> pd.DataFrame:
    """Rows eligible to be forecast on their issue date.

    The district must have been **imaged** on the issue day and found below the
    threshold. With ``hysteresis`` it must also have been below it for the
    previous three days, and the label is raised to three times the threshold.
    That closes the loophole where a district oscillating either side of the
    line supplies cheap "onsets" that are really the same standing water
    crossing back and forth.

    ``require_observed`` defaults to True here even though ``dry_at_issue``
    itself still defaults to False. A district whose issue day nobody imaged
    cannot support the claim "this was an onset rather than water already
    present", because whether the water was already present is exactly what is
    unknown. Admitting those rows is the same "not seen means not flooded"
    inference that made 86.8% of the negative labels fabricated, one layer
    further in.

    Pass ``require_observed=False`` only to reproduce the retracted pre-audit
    figures. It is kept reachable so the retraction can be demonstrated rather
    than merely asserted; it is not a supported evaluation path.
    """
    d = d[d["md"] >= CORE_MD]
    dry = dry_at_issue(d, threshold, require_observed=require_observed)
    if not hysteresis:
        return d[dry]
    g = d.groupby(["district", "year"], sort=False)["fraction"]
    recent_wet = pd.concat(
        [g.shift(i) > threshold for i in (1, 2, 3)], axis=1
    ).fillna(False).astype(bool).any(axis=1)
    return d[dry & ~recent_wet]


def evaluate(
    df: pd.DataFrame,
    threshold: float,
    horizon: int,
    nested=True,
    hysteresis: bool = False,
) -> tuple:
    """LOYO over the issue-day frame. Returns (results_rows, oof_by_variant)."""
    d = df.copy()
    label_thr = threshold * 3 if hysteresis else threshold
    d["y"] = forward_event(d, threshold=label_thr, horizon=horizon)
    d = _candidates(d, threshold, hysteresis)
    d = d.dropna(subset=["y"])

    years = sorted(d["year"].unique())
    oofs = {}
    for name, feats in VARIANTS.items():
        parts = []
        for ty in years:
            trys = [y for y in years if y != ty]
            prior = _fold_prior(d, trys, threshold)
            fold = d.merge(prior, on="district", how="left", validate="m:1")
            tr = fold[fold["year"].isin(trys)]
            te = fold[fold["year"] == ty].copy()
            if te.empty:
                continue
            te["score"] = _fit_predict(
                feats, tr, te, nested_years=tr["year"].to_numpy() if nested else None
            )
            te["ref"] = float(tr["y"].mean())
            parts.append(te)
        oofs[name] = pd.concat(parts, ignore_index=True)

    rows = []
    for name, oof in oofs.items():
        y = oof["y"].to_numpy(dtype=float)
        p = oof["score"].to_numpy(dtype=float)
        groups = oof["date"].astype(str).to_numpy()  # each issue day is a budget
        ok = ~np.isnan(p)
        rows.append(
            {
                "threshold": threshold,
                "horizon": horizon,
                "variant": name,
                "n": len(oof),
                "n_pos": int(np.nansum(y)),
                "ap": float(average_precision_score(y[ok], p[ok])),
                "roc": float(roc_auc_score(y[ok], p[ok])),
                "recall_at_3": recall_at_k(y, p, groups, k=3),
                "recall_at_5": recall_at_k(y, p, groups, k=5),
                "quiet_alert_rate": quiet_window_alert_rate(y, p, groups, 0.5),
                "brier_skill": (
                    np.nan
                    if name == "persistence"
                    else brier_skill(y[ok], p[ok], oof["ref"].to_numpy(float)[ok])
                ),
            }
        )
    return rows, oofs


# Matched ablation: identical learner throughout, only the feature set moves,
# so any gain is attributable to the predictors rather than to the model class.
ABLATION = {
    "observation timing only": TIMING_F + SEASON_F,
    "prior_state_season": PRIOR_F + STATE_F + SEASON_F,
    "  + rain": PRIOR_F + STATE_F + SEASON_F + RAIN_F + UP_F,
    "  + climatology pctl": PRIOR_F + STATE_F + SEASON_F + RAIN_F + UP_F + PCTL_F,
}


def run_ablation(df, threshold, horizon):
    d = df.copy()
    d["y"] = forward_event(d, threshold=threshold, horizon=horizon)
    d = d[d["md"] >= CORE_MD]
    d = d[dry_at_issue(d, threshold, require_observed=True)].dropna(subset=["y"])
    years = sorted(d["year"].unique())
    out = []
    for name, feats in ABLATION.items():
        parts = []
        for ty in years:
            trys = [y for y in years if y != ty]
            fold = d.merge(_fold_prior(d, trys, threshold), on="district",
                           how="left", validate="m:1")
            tr, te = fold[fold["year"].isin(trys)], fold[fold["year"] == ty].copy()
            if te.empty:
                continue
            te["score"] = _fit_predict(feats, tr, te, nested_years=tr["year"].to_numpy())
            parts.append(te)
        o = pd.concat(parts, ignore_index=True)
        ok = ~o["score"].isna()
        out.append({
            "features": name,
            "n_feat": len(feats),
            "ap": float(average_precision_score(o["y"][ok], o["score"][ok])),
            "recall_at_5": recall_at_k(o["y"].to_numpy(float), o["score"].to_numpy(float),
                                       o["date"].astype(str).to_numpy(), k=5),
        })
    return pd.DataFrame(out)


def run_selection(df, threshold, horizon):
    """Choose the entire variant inside each fold, never on the judged year."""
    d = df.copy()
    d["y"] = forward_event(d, threshold=threshold, horizon=horizon)
    d = d[d["md"] >= CORE_MD]
    d = d[dry_at_issue(d, threshold, require_observed=True)].dropna(subset=["y"])
    years = sorted(d["year"].unique())
    parts, picks = [], []
    for ty in years:
        trys = [y for y in years if y != ty]
        fold = d.merge(_fold_prior(d, trys, threshold), on="district",
                       how="left", validate="m:1")
        tr, te = fold[fold["year"].isin(trys)], fold[fold["year"] == ty].copy()
        if te.empty:
            continue
        scores = {}
        for name, feats in VARIANTS.items():
            preds, truths = [], []
            for inner in trys:
                itr, ite = tr[tr["year"] != inner], tr[tr["year"] == inner]
                if ite.empty or itr["y"].nunique() < 2:
                    continue
                preds.append(_fit_predict(feats, itr, ite))
                truths.append(ite["y"].to_numpy(float))
            if not preds:
                continue
            yy, pp = np.concatenate(truths), np.concatenate(preds)
            if len(np.unique(yy)) > 1:
                scores[name] = average_precision_score(yy, pp)
        chosen = max(scores, key=scores.get) if scores else "persistence"
        picks.append(chosen)
        te["score"] = _fit_predict(VARIANTS[chosen], tr, te,
                                   nested_years=tr["year"].to_numpy())
        te["chosen"] = chosen
        parts.append(te)
    return pd.concat(parts, ignore_index=True), picks


def main() -> None:
    df = build_frame()
    print(f"issue-day frame: {len(df)} district-days\n")

    print("=" * 74)
    print(f"PRIMARY: threshold {THRESHOLD:.1%} of district area, horizon {HORIZON} days")
    print("=" * 74)
    rows, oofs = evaluate(df, THRESHOLD, HORIZON)
    res = pd.DataFrame(rows).sort_values("ap", ascending=False)
    print(
        res[
            ["variant", "n", "n_pos", "ap", "roc", "recall_at_3", "recall_at_5",
             "quiet_alert_rate"]
        ].to_string(index=False)
    )

    base = float(res.loc[res["variant"] == "persistence", "ap"].iloc[0])
    best = res.iloc[0]["variant"]
    print(f"\nbest variant: {best}   AP {res.iloc[0]['ap']:.3f} vs persistence {base:.3f}")

    if best != "persistence":
        pb, bb = oofs["persistence"], oofs[best]
        by_year = {}
        for yr in sorted(bb["year"].unique()):
            a, b = bb[bb["year"] == yr], pb[pb["year"] == yr]
            if a["y"].nunique() < 2:
                continue
            by_year[int(yr)] = [
                average_precision_score(a["y"], a["score"].fillna(0))
                - average_precision_score(b["y"], b["score"].fillna(0))
            ]
        print("\nper-year AP difference (best minus persistence):")
        for yr, v in by_year.items():
            print(f"  {yr}: {v[0]:+.3f}")
        if len(by_year) >= 2:
            lo, hi = block_bootstrap_ci(by_year, n=4000, seed=SEED)
            mean = float(np.mean([v[0] for v in by_year.values()]))
            print(
                f"  equal-year mean {mean:+.3f}, year-block interval "
                f"[{lo:+.3f}, {hi:+.3f}] ({len(by_year)} event-year blocks)"
            )

    all_rows = list(rows)
    print("\n" + "=" * 74)
    print("SENSITIVITY: every threshold and horizon, reported not searched")
    print("=" * 74)
    print(f"{'thr':>6} {'hzn':>4} {'pos':>5}  {'best variant':22s} {'AP':>7} {'pers AP':>8} {'R@5':>6}")
    for thr in THRESHOLD_GRID:
        for hzn in HORIZON_GRID:
            if thr == THRESHOLD and hzn == HORIZON:
                r = rows
            else:
                r, _ = evaluate(df, thr, hzn, nested=False)
            all_rows += [x for x in r if x not in all_rows]
            rr = pd.DataFrame(r).sort_values("ap", ascending=False)
            top = rr.iloc[0]
            pers = float(rr.loc[rr["variant"] == "persistence", "ap"].iloc[0])
            print(
                f"{thr:6.3f} {hzn:4d} {int(top['n_pos']):5d}  {top['variant']:22s} "
                f"{top['ap']:7.3f} {pers:8.3f} {top['recall_at_5']:6.3f}"
            )

    print()
    print("MATCHED ABLATION: same learner, only the feature set changes")
    print("=" * 74)
    abl = run_ablation(df, THRESHOLD, HORIZON)
    print(abl.to_string(index=False))

    print()
    print("HONEST SELECTION: whole variant chosen inside each fold")
    print("=" * 74)
    sel, picks = run_selection(df, THRESHOLD, HORIZON)
    y = sel["y"].to_numpy(float)
    groups = sel["date"].astype(str).to_numpy()
    print(f"variants chosen across folds: {dict(Counter(picks))}")
    for label, sc in (("selected", sel["score"].to_numpy(float)),
                      ("persistence", sel["frac_now"].fillna(0.0).to_numpy())):
        ok = ~np.isnan(sc)
        print(f"{label:12s} AP={average_precision_score(y[ok], sc[ok]):.3f}  "
              f"ROC={roc_auc_score(y[ok], sc[ok]):.3f}  "
              f"R@3={recall_at_k(y, sc, groups, k=3):.3f}  "
              f"R@5={recall_at_k(y, sc, groups, k=5):.3f}")
    by_year = {}
    for yr in sorted(sel["year"].unique()):
        s_ = sel[sel["year"] == yr]
        if s_["y"].nunique() < 2:
            continue
        by_year[int(yr)] = [
            average_precision_score(s_["y"], s_["score"].fillna(0))
            - average_precision_score(s_["y"], s_["frac_now"].fillna(0))]
    print("\nper-year AP difference (selected minus persistence):")
    for yr, v in by_year.items():
        print(f"  {yr}: {v[0]:+.3f}")
    if len(by_year) >= 2:
        lo, hi = block_bootstrap_ci(by_year, n=4000, seed=SEED)
        print(f"  equal-year mean {np.mean([v[0] for v in by_year.values()]):+.3f}, "
              f"year-block interval [{lo:+.3f}, {hi:+.3f}] ({len(by_year)} blocks)")
    sel[["date", "district", "year", "chosen", "y", "score", "frac_now"]].to_csv(
        DATA / "forecaster_daily_selection.csv", index=False)

    pd.DataFrame(all_rows).to_csv(OUT, index=False)
    pd.concat(
        [o.assign(variant=n) for n, o in oofs.items()], ignore_index=True
    )[["date", "district", "year", "variant", "y", "score", "frac_now"]].to_csv(
        OUT_OOF, index=False
    )
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
