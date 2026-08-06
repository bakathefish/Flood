# pipeline/run_forecaster_benchmark.py
"""Benchmark the candidate architectures under walk-forward, and pick one.

Every candidate is scored the way the system would actually run: each season is
forecast using only seasons that already happened. Nothing is chosen on a season
it is judged on.

Candidates, and why each is here rather than something fancier:

  persistence            carry today's water forward. The floor.
  transparent            unweighted rank-sum of own water, seasonal onset
                         climatology and neighbouring water. No fitting. This is
                         the rule the learned model has to justify itself
                         against, and it is genuinely hard to beat at a fixed
                         alert budget.
  logistic               the current model: susceptibility, state, season,
                         neighbour, climatology, class-balanced logistic.
  hawkes                 the same plus a self-exciting term: past flood days
                         decayed exponentially in time and by graph ring in
                         space. The parsimonious form of what a graph neural
                         network learns for flood routing, at a size ninety-six
                         events can support.
  hawkes_firth           the same features fitted by Firth penalised likelihood
                         with a King and Zeng prior correction, the standard
                         treatment for a base rate this low. Reported as a
                         diagnostic; it does not make the score a calibrated
                         probability, which would need a reliability check that
                         has not been done.
  gradient_boosting      included because the flood-susceptibility literature
                         usually reports boosting beating logistic regression.
                         Reported whatever it does.

Scores reported: average precision and event recall, plus the contingency scores
an operational flood service actually verifies against, probability of
detection, false alarm ratio and critical success index at a five-district daily
alert budget.

Run: python -m pipeline.run_forecaster_benchmark
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from pipeline.run_forecaster_daily import (
    HORIZON,
    THRESHOLD,
    _candidates,
    _fold_prior,
    build_frame,
)
from pipeline.run_forecaster_daily_audit import _event_recall, onset_events
from pipeline.run_forecaster_daily_audit2 import (
    add_neighbour_water,
    build_adjacency,
    seasonal_climatology,
)
from sailaab.forecast_daily import forward_event
from sailaab.hazard import (
    FirthLogistic,
    contingency_scores,
    excitation_features,
    prior_correct,
)

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = DATA / "forecaster_benchmark.csv"
# Per-district walk-forward scores for the most recent flood season, published
# so the public proof chart shows the deployed model rather than a superseded
# one. Written from the same fold that the benchmark scores, so the chart and
# the table can never drift apart.
OUT_SEASON = DATA / "forecaster_2025_walkforward.csv"
N_BOOT = 2000  # enough for a stable 95% percentile interval at this size

FIRST_TEST_YEAR = 2019
ALERT_K = 5
# Nominal quantiles swept over the inner out-of-fold scores. The REALIZED alert
# volume is what gets reported: later seasons score higher than the seasons the
# threshold was derived from, so nominal and realized diverge, and only the
# realized number describes what an operator would live with.
RATES = (0.0002, 0.0005, 0.001, 0.002, 0.005, 0.01, 0.02)
TAU_DAYS = 3.0  # excitation decay, matched to the routing time
MAX_HOPS = 2

BASE_F = [
    "prior_wet_days", "prior_max_fraction", "frac_now", "frac_max3d",
    "day_of_season", "neighbour", "season_climo",
]
EXCITE_F = [f"excite_h{h}" for h in range(MAX_HOPS + 1)]


def _balanced():
    return make_pipeline(
        SimpleImputer(strategy="median"),
        StandardScaler(),
        LogisticRegression(C=0.1, max_iter=1000, class_weight="balanced"),
    )


def _boosting():
    from xgboost import XGBClassifier

    return XGBClassifier(
        n_estimators=200, max_depth=3, learning_rate=0.05, subsample=0.8,
        colsample_bytree=0.8, reg_lambda=5.0, min_child_weight=5,
        eval_metric="logloss", random_state=20260806,
    )


def _fit_firth(Xtr, ytr, Xte):
    """Firth fit on the raw base rate, then a prior correction that is the
    identity, since nothing was re-balanced. Kept explicit so the correction is
    visible rather than assumed."""
    imp = SimpleImputer(strategy="median").fit(Xtr)
    sc = StandardScaler().fit(imp.transform(Xtr))
    A = sc.transform(imp.transform(Xtr))
    B = sc.transform(imp.transform(Xte))
    m = FirthLogistic().fit(A, ytr)
    return m.predict_proba(B)[:, 1]


def _fit_balanced_corrected(Xtr, ytr, Xte):
    """Class-balanced fit, then King and Zeng back onto the population rate."""
    m = _balanced().fit(Xtr, ytr)
    p = m.predict_proba(Xte)[:, 1]
    return prior_correct(p, tau=float(ytr.mean()), sample_rate=0.5)


def main() -> None:
    print("building frame (no rainfall: the model does not use it) ...")
    df = build_frame(with_rain=False)
    adjacency = build_adjacency()
    df = add_neighbour_water(df, adjacency)

    ex = excitation_features(
        df[["date", "district", "fraction"]], adjacency,
        threshold=THRESHOLD, tau=TAU_DAYS, max_hops=MAX_HOPS,
    )
    df = df.merge(ex, on=["date", "district"], how="left", validate="1:1")

    d = df.copy()
    d["y"] = forward_event(d, threshold=THRESHOLD, horizon=HORIZON)
    d = _candidates(d, THRESHOLD, hysteresis=False).dropna(subset=["y"])
    d["neighbour"] = d["neighbour_wet3d"].fillna(0.0)
    d["week"] = (d["day_of_season"] // 7).astype(int)

    years = sorted(d["year"].unique())
    parts = []
    for ty in [y for y in years if y >= FIRST_TEST_YEAR]:
        past = [y for y in years if y < ty]
        tr = d[d["year"].isin(past)]
        te = d[d["year"] == ty].copy()
        if te.empty or tr["y"].nunique() < 2:
            continue
        prior = _fold_prior(tr, past, THRESHOLD)
        tr = tr.merge(prior, on="district", how="left", validate="m:1")
        te = te.merge(prior, on="district", how="left", validate="m:1")
        climo = seasonal_climatology(tr)
        fill = float(tr["y"].mean())
        tr = tr.merge(climo, on=["district", "week"], how="left")
        te = te.merge(climo, on=["district", "week"], how="left")
        tr["season_climo"] = tr["season_climo"].fillna(fill)
        te["season_climo"] = te["season_climo"].fillna(fill)

        ytr = tr["y"].to_numpy(float)
        Xb_tr, Xb_te = tr[BASE_F].to_numpy(float), te[BASE_F].to_numpy(float)
        HF = BASE_F + EXCITE_F
        Xh_tr, Xh_te = tr[HF].to_numpy(float), te[HF].to_numpy(float)

        te["persistence"] = te["frac_now"].fillna(0.0)
        te["transparent"] = (
            te["season_climo"].rank(pct=True)
            + te["neighbour"].rank(pct=True)
            + te["frac_now"].fillna(0.0).rank(pct=True)
        )
        te["logistic"] = _balanced().fit(Xb_tr, ytr).predict_proba(Xb_te)[:, 1]
        te["hawkes"] = _balanced().fit(Xh_tr, ytr).predict_proba(Xh_te)[:, 1]
        te["hawkes_firth"] = _fit_firth(Xh_tr, ytr, Xh_te)
        te["hawkes_corrected"] = _fit_balanced_corrected(Xh_tr, ytr, Xh_te)
        te["gradient_boosting"] = (
            _boosting().fit(Xh_tr, ytr).predict_proba(Xh_te)[:, 1]
        )
        # matched ablation: identical learner, excitation removed, so the gain
        # can be attributed to the features rather than to the model class
        te["boosting_no_excite"] = (
            _boosting().fit(Xb_tr, ytr).predict_proba(Xb_te)[:, 1]
        )
        # Alert threshold from INNER out-of-fold scores. Two things are wrong
        # with the obvious alternatives: a quantile of the pooled test scores
        # peeks at the season being judged, and a quantile of the model's own
        # training predictions is resubstitution, which is optimistic because
        # the model has already fitted those rows. So an inner walk-forward is
        # run inside the training years, and the threshold is taken from
        # predictions each inner model never saw.
        inner = []
        for iy in past[1:]:
            i_past = [y for y in past if y < iy]
            # Rebuild the target-derived features INSIDE the inner fold. Reusing
            # the outer fold's priors and climatology would let an inner
            # validation season shape its own features, and would let later
            # training seasons reach back into earlier inner folds.
            raw = d[d["year"].isin(past)]
            i_prior = _fold_prior(raw[raw["year"].isin(i_past)], i_past, THRESHOLD)
            i_all = raw.drop(
                columns=["prior_wet_days", "prior_max_fraction", "season_climo"],
                errors="ignore",
            ).merge(i_prior, on="district", how="left", validate="m:1")
            i_tr = i_all[i_all["year"].isin(i_past)]
            i_te = i_all[i_all["year"] == iy]
            if i_te.empty or i_tr["y"].nunique() < 2:
                continue
            i_climo = seasonal_climatology(i_tr)
            i_fill = float(i_tr["y"].mean())
            i_tr = i_tr.merge(i_climo, on=["district", "week"], how="left")
            i_te = i_te.merge(i_climo, on=["district", "week"], how="left")
            i_tr["season_climo"] = i_tr["season_climo"].fillna(i_fill)
            i_te["season_climo"] = i_te["season_climo"].fillna(i_fill)
            inner.append(
                _boosting()
                .fit(i_tr[HF].to_numpy(float), i_tr["y"].to_numpy(float))
                .predict_proba(i_te[HF].to_numpy(float))[:, 1]
            )
        oof = np.concatenate(inner) if inner else np.array([0.5])
        for rate in RATES:
            te[f"thr_{rate}"] = float(np.quantile(oof, 1.0 - rate))
        parts.append(te)
        print(f"  {ty}: fitted on {len(past)} prior seasons, "
              f"{int(te['y'].sum())} positive district-days")

    s = pd.concat(parts, ignore_index=True)
    events = onset_events(df, THRESHOLD)
    events = events[events["year"] >= FIRST_TEST_YEAR]

    cols = ["persistence", "transparent", "logistic", "hawkes", "hawkes_firth",
            "hawkes_corrected", "boosting_no_excite", "gradient_boosting"]
    base = s["y"].mean()
    print("\n" + "=" * 86)
    print(f"WALK-FORWARD BENCHMARK  seasons {FIRST_TEST_YEAR}-{years[-1]}  "
          f"n={len(s)}  positives={int(s['y'].sum())}  base={base:.4f}")
    print("=" * 86)
    print(f"{'candidate':20s} {'AP':>7} {'lift':>6} {'evR@5':>7} "
          f"{'POD':>6} {'FAR':>6} {'CSI':>6} {'Brier skill':>12}")

    # a top-k alert per issue day, which is the operating point the whole
    # evaluation is built around
    ref = np.full(len(s), base)
    rows = []
    for c in cols:
        alert = np.zeros(len(s), dtype=float)
        for _, g in s.groupby("date"):
            top = g.nlargest(ALERT_K, c).index
            alert[s.index.get_indexer(top)] = 1.0
        cs = contingency_scores(s["y"].to_numpy(float), alert)
        ap = average_precision_score(s["y"], s[c])
        e5, _ = _event_recall(s, events, c, ALERT_K, HORIZON)
        # Brier skill only means anything for a score on a probability scale
        if c in ("hawkes_firth", "hawkes_corrected", "gradient_boosting",
                 "boosting_no_excite"):
            bs = brier_score_loss(s["y"], np.clip(s[c], 0, 1))
            bss = 1.0 - bs / brier_score_loss(s["y"], ref)
            bss_s = f"{bss:12.3f}"
        else:
            bss = float("nan")
            bss_s = f"{'-':>12}"
        print(f"{c:20s} {ap:7.3f} {ap / base:6.1f} {e5:7.3f} "
              f"{cs['pod']:6.3f} {cs['far']:6.3f} {cs['csi']:6.3f} {bss_s}")
        rows.append({"candidate": c, "ap": ap, "lift": ap / base, "event_r5": e5,
                     **{k: cs[k] for k in ("pod", "far", "csi", "bias", "hits",
                                           "misses", "false_alarms")},
                     "brier_skill": bss})

    print("\nper-season average precision:")
    hdr = "  season " + "".join(f"{c[:12]:>14}" for c in cols)
    print(hdr)
    for yr in sorted(s["year"].unique()):
        sub = s[s["year"] == yr]
        if sub["y"].nunique() < 2:
            continue
        line = f"  {yr}   "
        for c in cols:
            line += f"{average_precision_score(sub['y'], sub[c]):14.3f}"
        print(line)
        rows.append({"candidate": "per_season", "year": int(yr),
                     **{c: average_precision_score(sub["y"], sub[c]) for c in cols}})

    print()
    print("=" * 86)
    print("OPERATING POINT: alert only when the score is high, not five every day")
    print("=" * 86)
    print(f"{'candidate':20s} {'rate':>6} {'alerts':>7} {'POD':>6} {'FAR':>6} "
          f"{'CSI':>6} {'bias':>6}")
    for c in ("transparent", "boosting_no_excite", "gradient_boosting"):
        for rate in (0.005, 0.01, 0.02, 0.05):
            thr = s[c].quantile(1.0 - rate)
            alert = (s[c] >= thr).astype(float).to_numpy()
            cs = contingency_scores(s["y"].to_numpy(float), alert)
            print(f"{c:20s} {rate:6.1%} {int(alert.sum()):7d} {cs['pod']:6.3f} "
                  f"{cs['far']:6.3f} {cs['csi']:6.3f} {cs['bias']:6.2f}")
            rows.append({"candidate": f"{c}@rate{rate}", "alert_rate": rate,
                         **{k: cs[k] for k in ("pod", "far", "csi", "bias",
                                               "hits", "misses", "false_alarms")}})

    # Event level is what an operator experiences: one flood warned or missed,
    # and how many warnings a season costs.
    n_seasons = s["year"].nunique()
    print()
    print("=" * 86)
    print("EVENT LEVEL at the same operating points")
    print("=" * 86)
    print(f"{'candidate':20s} {'rate':>6} {'alerts/season':>14} {'events warned':>14} "
          f"{'event POD':>10} {'alert precision':>16}")
    for c in ("transparent", "boosting_no_excite", "gradient_boosting"):
        for rate in (0.005, 0.01, 0.02):
            thr = s[c].quantile(1.0 - rate)
            fired = s[s[c] >= thr]
            issued = {(pd.Timestamp(r.date), r.district) for r in fired.itertuples()}
            warned = 0
            for _, e in events.iterrows():
                day = pd.Timestamp(e["date"])
                if any((day - pd.Timedelta(days=h), e["district"]) in issued
                       for h in range(1, HORIZON + 1)):
                    warned += 1
            useful = sum(
                1 for (dy, dist) in issued
                if any(
                    ((dy + pd.Timedelta(days=h)), dist)
                    in {(pd.Timestamp(e["date"]), e["district"])
                        for _, e in events.iterrows()}
                    for h in range(1, HORIZON + 1)
                )
            )
            print(f"{c:20s} {rate:6.1%} {len(fired) / n_seasons:14.1f} "
                  f"{warned:>6d}/{len(events):<7d} {warned / len(events):10.3f} "
                  f"{useful / max(len(issued), 1):16.3f}")
            rows.append({"candidate": f"{c}@event{rate}", "alert_rate": rate,
                         "alerts_per_season": len(fired) / n_seasons,
                         "events_warned": warned, "n_events": len(events),
                         "event_pod": warned / len(events),
                         "alert_precision": useful / max(len(issued), 1)})

    print()
    print("=" * 86)
    print("FOLD-SAFE OPERATING POINT: threshold from inner out-of-fold scores")
    print("=" * 86)
    print(f"{'nominal':>8} {'alerts/season':>14} {'events warned':>14} {'event POD':>10} "
          f"{'alert precision':>16} {'FAR':>7}")
    ev_set = {(pd.Timestamp(e["date"]), e["district"]) for _, e in events.iterrows()}
    for rate in RATES:
        fired = s[s["gradient_boosting"] >= s[f"thr_{rate}"]]
        issued = {(pd.Timestamp(r.date), r.district) for r in fired.itertuples()}
        warned = sum(
            1 for (dy, dist) in ev_set
            if any((dy - pd.Timedelta(days=h), dist) in issued
                   for h in range(1, HORIZON + 1))
        )
        useful = sum(
            1 for (dy, dist) in issued
            if any((dy + pd.Timedelta(days=h), dist) in ev_set
                   for h in range(1, HORIZON + 1))
        )
        alert = (s["gradient_boosting"] >= s[f"thr_{rate}"]).astype(float).to_numpy()
        cs = contingency_scores(s["y"].to_numpy(float), alert)
        prec = useful / max(len(issued), 1)
        print(f"{rate:8.3%} {len(fired) / n_seasons:14.1f} {warned:>6d}/{len(ev_set):<7d} "
              f"{warned / len(ev_set):10.3f} {prec:16.3f} {cs['far']:7.3f}")
        rows.append({"candidate": f"foldsafe@{rate}", "alert_rate": rate,
                     "alerts_per_season": len(fired) / n_seasons,
                     "events_warned": warned, "n_events": len(ev_set),
                     "event_pod": warned / len(ev_set), "alert_precision": prec,
                     "far": cs["far"]})


    # ---- how much of this could be luck -------------------------------- #
    # Pooled AP over correlated district-days looks far more certain than it
    # is: the target spans three days so consecutive rows share outcomes, and
    # neighbouring districts flood together. Resample seasons, then blocks of
    # whole days inside them, and score every candidate on the same drawn rows
    # so the deltas between them are paired.
    from sailaab.uncertainty import (
        BLOCK_DAYS, delete_one_season, delta_ci, percentile_ci, season_summary,
        two_stage_bootstrap,
    )

    cand = {c: s[c].to_numpy(float) for c in cols}
    yv = s["y"].to_numpy(float)
    sv = s["year"].to_numpy()
    dv = pd.to_datetime(s["date"]).dt.dayofyear.to_numpy()
    pooled = {c: average_precision_score(s["y"], s[c]) for c in cols}

    print("")
    print("=" * 86)
    print(
        f"UNCERTAINTY  two-stage block bootstrap (seasons, then "
        f"{BLOCK_DAYS}-day blocks), B={N_BOOT}"
    )
    print("=" * 86)
    boot = two_stage_bootstrap(yv, cand, sv, dv, n_boot=N_BOOT, seed=0)
    print(f"{'candidate':20s} {'AP':>7} {'95% CI':>20}")
    for c in cols:
        lo, hi = percentile_ci(boot[c])
        print(f"{c:20s} {pooled[c]:7.3f}  [{lo:6.3f}, {hi:6.3f}]")
        rows.append(
            {"candidate": f"ci@{c}", "ap": pooled[c], "ci_lo": lo, "ci_hi": hi}
        )

    print("")
    print("paired deltas on the same resampled rows:")
    for a, b in (
        ("gradient_boosting", "boosting_no_excite"),
        ("gradient_boosting", "persistence"),
        ("boosting_no_excite", "persistence"),
    ):
        dd = delta_ci(boot, a, b, observed=pooled[a] - pooled[b])
        print(
            f"  {a} - {b}: {dd['delta']:+.3f} "
            f"[{dd['lo']:+.3f}, {dd['hi']:+.3f}]  ahead in "
            f"{dd['p_a_better']:.0%} of draws"
        )
        rows.append(
            {
                "candidate": f"delta@{a}-{b}",
                "ap": dd["delta"],
                "ci_lo": dd["lo"],
                "ci_hi": dd["hi"],
                "p_better": dd["p_a_better"],
                "boot_mean": dd["boot_mean"],
            }
        )

    per, agg = season_summary(yv, cand, sv)
    print("")
    print("pooled against the typical season:")
    print(f"{'candidate':20s} {'pooled':>7} {'mean':>7} {'median':>7}")
    for c in cols:
        print(
            f"{c:20s} {pooled[c]:7.3f} {agg[c]['mean']:7.3f} "
            f"{agg[c]['median']:7.3f}"
        )
        rows.append(
            {
                "candidate": f"seasonal@{c}",
                "ap": pooled[c],
                "season_mean": agg[c]["mean"],
                "season_median": agg[c]["median"],
            }
        )

    print("")
    print("delete-one-season sensitivity (AP with that season removed):")
    d1 = delete_one_season(yv, cand, sv)
    order = sorted(d1)
    print(f"{'candidate':20s} " + "  ".join(f"{int(y):>7}" for y in order))
    for c in cols:
        print(f"{c:20s} " + "  ".join(f"{d1[y][c]:7.3f}" for y in order))
        for y in order:
            rows.append(
                {"candidate": f"drop{int(y)}@{c}", "ap": d1[y][c], "year": int(y)}
            )


    pd.DataFrame(rows).to_csv(OUT, index=False)
    print(f"\nwrote {OUT}")

    # Per-district scores for the latest flood season, straight out of the
    # walk-forward fold: 2025 is forecast by a model that saw only 2015-2024.
    season = s[s["year"] == s["year"].max()]
    season[["district", "date", "gradient_boosting", "y"]].rename(
        columns={"gradient_boosting": "score", "y": "flooded_within_3d"}
    ).to_csv(OUT_SEASON, index=False)
    print(f"wrote {OUT_SEASON}  ({len(season)} district-days)")


if __name__ == "__main__":
    main()
