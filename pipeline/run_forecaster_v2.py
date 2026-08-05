# pipeline/run_forecaster_v2.py
"""Forecaster v2: does district-resolved rainfall actually add skill?

The v1 forecaster lost to a one-feature persistence baseline on PR-AUC. The
diagnosis was structural: within any window the rain and reservoir columns were
statewide constants, so the only predictor varying across both district and
window was the lagged target itself. This script rebuilds the experiment with
district-resolved IMD rainfall and re-runs the comparison under a stricter
protocol than v1 used:

  * fold-safe district priors, rebuilt from each fold's training years
    (v1 computed them once over 2015-2025, so every held-out year leaked into
    its own features);
  * antecedent flooding reset at each season boundary (v1 shifted across the
    year break, so the first window of a season inherited the previous
    September);
  * ranking metrics scored inside each window, because pooled ROC-AUC is
    dominated by the eight seasons that contain no flood at all;
  * an issue-time variant that uses ONLY information available when the window
    opens, which is the only regime in which a lead-time claim is defensible.

Nothing here overwrites the v1 outputs. Results land beside them so the two can
be compared, and a losing variant is reported as a loss.

Run: python -m pipeline.run_forecaster_v2
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer

from sailaab import config
from sailaab.forecast_features import PADDY_CUTOFF_MD
from sailaab.forecast_v2 import (
    block_bootstrap_ci,
    brier_skill,
    fold_safe_prior,
    quiet_window_alert_rate,
    recall_at_k,
)

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

TARGET = DATA / "gfm_district_window_fractions_2015_2025.csv"
RAIN_STATE = DATA / "rain_windows_2015_2025.csv"
RAIN_DIST = DATA / "rain_district_windows_2015_2025.csv"
RES = DATA / "reservoir_windows.csv"

OUT_METRICS = DATA / "forecaster_v2_comparison.csv"
OUT_OOF = DATA / "forecaster_v2_oof.csv"

SEED = 20260805

STATE_RAIN = [
    "punjab_mm",
    "upstream_mm",
    "punjab_mm_lag1",
    "upstream_mm_lag1",
    "punjab_mm_lag2",
    "upstream_mm_lag2",
]
RES_COLS = [
    "bhakra_storage",
    "pong_storage",
    "ranjit_sagar_storage",
    "bhakra_delta",
    "pong_delta",
    "ranjit_sagar_delta",
]
DIST_RAIN_NOW = ["district_mm", "district_max1d", "district_max3d", "district_p90"]
DIST_RAIN_PRE = ["district_mm_lag1", "district_mm_lag2", "api_start"]
# Rain already on the ground a few days into the window. Everything else
# inside the window arrives too late to warn anyone, so these are the only
# rainfall predictors that can support a warning-time claim.
LEAD3 = ["district_first3d"]
LEAD5 = ["district_first5d"]
PRIOR = ["prior_mean_annual_flooded_ha", "prior_seasons_with_fraction_gt2pct"]
BASE = ["antecedent_fraction", "week_of_season"]


def _xgb(tr=None):
    from xgboost import XGBClassifier

    return XGBClassifier(
        n_estimators=300,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.9,
        eval_metric="logloss",
        random_state=SEED,
    )


def _xgb_small(tr=None):
    """Capacity matched to the sample. 27 positives cannot support 300 deep
    trees; this is the regularized challenger."""
    from xgboost import XGBClassifier

    return XGBClassifier(
        n_estimators=120,
        max_depth=2,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_lambda=5.0,
        min_child_weight=3,
        eval_metric="logloss",
        random_state=SEED,
    )


def _logreg(C: float = 0.1):
    return make_pipeline(
        SimpleImputer(strategy="median"),
        StandardScaler(),
        LogisticRegression(C=C, max_iter=2000, class_weight="balanced"),
    )


C_GRID = (0.01, 0.03, 0.1, 0.3, 1.0)


class NestedLogReg:
    """Penalised logistic regression whose regularisation strength is chosen by
    an inner leave-one-year-out sweep over the TRAINING years only.

    Picking C on the outer test year would be exactly the post-hoc tuning this
    evaluation is trying to avoid, so the grid is resolved inside each fold and
    the outer year never participates in the choice.
    """

    def __init__(self, year_col: np.ndarray):
        self.year_col = np.asarray(year_col)
        self.best_C_ = None
        self.model_ = None

    def fit(self, X, y):
        y = np.asarray(y)
        years = sorted(set(self.year_col.tolist()))
        best, best_ap = C_GRID[0], -np.inf
        for C in C_GRID:
            preds, truths = [], []
            for inner in years:
                m_tr = self.year_col != inner
                m_te = ~m_tr
                if len(np.unique(y[m_tr])) < 2 or m_te.sum() == 0:
                    continue
                mdl = _logreg(C).fit(X[m_tr], y[m_tr])
                preds.append(mdl.predict_proba(X[m_te])[:, 1])
                truths.append(y[m_te])
            if not preds:
                continue
            yy = np.concatenate(truths)
            pp = np.concatenate(preds)
            if len(np.unique(yy)) < 2:
                continue
            ap = average_precision_score(yy, pp)
            if ap > best_ap:
                best_ap, best = ap, C
        self.best_C_ = best
        self.model_ = _logreg(best).fit(X, y)
        return self

    def predict_proba(self, X):
        return self.model_.predict_proba(X)


def build_frame() -> pd.DataFrame:
    """District x window x year frame with every candidate feature attached.

    Priors are deliberately NOT joined here: they are rebuilt per fold.
    """
    tgt = pd.read_csv(TARGET).rename(columns={"fraction": "flooded_fraction"})
    tgt["year"] = pd.to_datetime(tgt["window_start"]).dt.year

    # antecedent flooding: previous window WITHIN the same season, computed on
    # the full 11-window grid before the core-season filter so the first core
    # window still sees the real mid-July antecedent.
    tgt = tgt.sort_values(["district", "year", "window_start"]).reset_index(drop=True)
    tgt["antecedent_fraction"] = tgt.groupby(["district", "year"])[
        "flooded_fraction"
    ].shift(1)
    tgt["week_of_season"] = tgt.groupby(["district", "year"]).cumcount()
    tgt["flood_event"] = (
        tgt["flooded_fraction"] > config.FLOOD_EVENT_FRACTION
    ).astype(int)

    state = pd.read_csv(RAIN_STATE)[["year", "window_start"] + STATE_RAIN]
    dist = pd.read_csv(RAIN_DIST)
    res = pd.read_csv(RES)

    from sailaab.forecast_features import pivot_reservoirs

    resw = pivot_reservoirs(res)

    df = tgt.merge(state, on=["year", "window_start"], how="left", validate="m:1")
    keep = (
        ["district", "year", "window_start"]
        + DIST_RAIN_NOW
        + DIST_RAIN_PRE
        + LEAD3
        + LEAD5
    )
    df = df.merge(
        dist[keep],
        on=["district", "year", "window_start"],
        how="left",
        validate="1:1",
    )
    df = df.merge(resw, on=["year", "window_start"], how="left", validate="m:1")

    md = df["window_start"].astype(str).str.slice(5)
    df["core_season"] = md >= PADDY_CUTOFF_MD
    return df


def _logreg_fixed(tr=None):
    return _logreg(0.1)


def _nested_logreg(tr):
    return NestedLogReg(tr["year"].to_numpy())


# Compact, physically motivated onset predictors, declared before the run:
# storm intensity, how saturated the ground already was, upstream catchment
# rain that has to route down, the window total, and static susceptibility.
ONSET_PHYS = [
    "district_max3d",
    "api_start",
    "upstream_mm",
    "district_mm",
    "prior_seasons_with_fraction_gt2pct",
]


VARIANTS = {
    # name: (features, model factory)
    "persistence": (["antecedent_fraction"], None),
    "v1_statewide": (BASE + STATE_RAIN + RES_COLS + PRIOR, _xgb),
    "v1_no_reservoir": (BASE + STATE_RAIN + PRIOR, _xgb),
    "v2_district_rain": (
        BASE + STATE_RAIN + DIST_RAIN_NOW + DIST_RAIN_PRE + PRIOR,
        _xgb,
    ),
    "v2_district_rain_small": (
        BASE + STATE_RAIN + DIST_RAIN_NOW + DIST_RAIN_PRE + PRIOR,
        _xgb_small,
    ),
    "v2_district_rain_logreg": (
        BASE + STATE_RAIN + DIST_RAIN_NOW + DIST_RAIN_PRE + PRIOR,
        _logreg_fixed,
    ),
    "v2_onset_physics": (ONSET_PHYS, _nested_logreg),
    "v2_district_rain_nested": (
        BASE + STATE_RAIN + DIST_RAIN_NOW + DIST_RAIN_PRE + PRIOR,
        _nested_logreg,
    ),
    # Matched ablations: SAME learner as the best variant, with the district
    # rainfall removed. Without these the gain cannot be attributed to the
    # rainfall rather than to the change of learner.
    "v2_nested_no_district_rain": (BASE + STATE_RAIN + PRIOR, _nested_logreg),
    "v2_nested_antecedent_prior": (BASE + PRIOR, _nested_logreg),
    "v2_nested_district_rain_only": (BASE + DIST_RAIN_NOW + PRIOR, _nested_logreg),
    # Genuine short-lead forecast: only the opening days of the window are
    # visible, and the model must rank flooding over the whole window.
    "v2_lead_3day": (BASE + DIST_RAIN_PRE + LEAD3 + ["upstream_mm_lag1"] + PRIOR, _nested_logreg),
    "v2_lead_5day": (BASE + DIST_RAIN_PRE + LEAD5 + ["upstream_mm_lag1"] + PRIOR, _nested_logreg),
    # Only what is knowable when the window opens: no rain from inside the
    # window being predicted. This is the honest early-warning regime.
    "v2_issue_time": (
        BASE
        + ["punjab_mm_lag1", "upstream_mm_lag1", "punjab_mm_lag2", "upstream_mm_lag2"]
        + DIST_RAIN_PRE
        + PRIOR,
        _xgb_small,
    ),
}


def run_variant(
    df: pd.DataFrame, features, factory, onset_only: bool = False
) -> pd.DataFrame:
    """Leave-one-year-out out-of-fold scores with fold-safe priors.

    ``onset_only`` restricts both fitting and scoring to district-windows that
    were dry when the window opened. That is the early-warning question: which
    dry district is about to flood. Scoring every row instead lets a model
    collect credit for continuation, where water observed last window is still
    on the ground this window and the lagged target answers almost by itself.
    """
    years = sorted(df["year"].unique())
    out = []
    for test_year in years:
        train_years = [y for y in years if y != test_year]
        prior = fold_safe_prior(df, train_years)

        fold = df.merge(prior, on="district", how="left", validate="m:1")
        core = fold[fold["core_season"]]
        if onset_only:
            dry = core["antecedent_fraction"] <= config.FLOOD_EVENT_FRACTION
            core = core[dry.fillna(True)]
        tr = core[core["year"].isin(train_years)]
        te = core[core["year"] == test_year].copy()

        if factory is None:  # persistence: the lagged target IS the score
            te["score"] = te["antecedent_fraction"].fillna(0.0)
        elif tr["flood_event"].nunique() < 2:
            te["score"] = np.nan
        else:
            m = factory(tr)
            m.fit(tr[features], tr["flood_event"])
            te["score"] = m.predict_proba(te[features])[:, 1]

        # reference forecast: the training-fold climatology
        te["ref"] = float(tr["flood_event"].mean())
        out.append(
            te[
                [
                    "district",
                    "year",
                    "window_start",
                    "flood_event",
                    "flooded_fraction",
                    "score",
                    "ref",
                ]
            ]
        )
    return pd.concat(out, ignore_index=True)


def score_variant(name: str, oof: pd.DataFrame) -> dict:
    y = oof["flood_event"].to_numpy(dtype=float)
    p = oof["score"].to_numpy(dtype=float)
    groups = (oof["year"].astype(str) + "|" + oof["window_start"]).to_numpy()
    ok = ~np.isnan(p)

    rec = {
        "variant": name,
        "pooled_ap": float(average_precision_score(y[ok], p[ok])),
        "pooled_roc": float(roc_auc_score(y[ok], p[ok])),
        "recall_at_3": recall_at_k(y, p, groups, k=3),
        "recall_at_5": recall_at_k(y, p, groups, k=5),
        "quiet_alert_rate_p50": quiet_window_alert_rate(y, p, groups, threshold=0.5),
    }
    if name != "persistence":
        rec["brier_skill_vs_climatology"] = brier_skill(
            y[ok], p[ok], oof["ref"].to_numpy(dtype=float)[ok]
        )
    else:
        rec["brier_skill_vs_climatology"] = np.nan

    # per event-year average precision
    for yr in (2019, 2023, 2025):
        sub = oof[oof["year"] == yr]
        yy = sub["flood_event"].to_numpy(dtype=float)
        pp = sub["score"].to_numpy(dtype=float)
        m = ~np.isnan(pp)
        rec[f"ap_{yr}"] = (
            float(average_precision_score(yy[m], pp[m]))
            if m.any() and len(np.unique(yy[m])) == 2
            else np.nan
        )

    # 2025: how many of the districts that actually flooded make the top 5 of
    # their window, and how many are caught anywhere in the season top 5
    s25 = oof[oof["year"] == 2025]
    flooded = sorted(s25[s25["flood_event"] == 1]["district"].unique())
    caught = set()
    for _, g in s25.groupby("window_start"):
        top = g.nlargest(5, "score")["district"].tolist()
        caught |= {
            d for d in g[g["flood_event"] == 1]["district"].tolist() if d in top
        }
    rec["n_flooded_2025"] = len(flooded)
    rec["caught_2025_top5"] = len(caught)
    rec["missed_2025"] = ",".join(sorted(set(flooded) - caught)) or "-"
    return rec


def main() -> None:
    df = build_frame()
    core = df[df["core_season"]]
    print(
        f"frame: {len(df)} rows, core-season {len(core)}, "
        f"positives {int(core['flood_event'].sum())}, "
        f"base rate {core['flood_event'].mean() * 100:.2f}%"
    )

    varies = (
        core.groupby(["year", "window_start"])["district_mm"].nunique() > 1
    ).mean()
    print(f"district rainfall varies within window: {varies * 100:.1f}% of windows\n")

    rows, oofs = [], {}
    for name, (feats, fac) in VARIANTS.items():
        oof = run_variant(df, feats, fac)
        oofs[name] = oof
        rec = score_variant(name, oof)
        rec["n_features"] = len(feats)
        rows.append(rec)
        print(
            f"{name:26s} AP={rec['pooled_ap']:.3f}  R@5={rec['recall_at_5']:.3f}  "
            f"2025 caught {rec['caught_2025_top5']}/{rec['n_flooded_2025']}"
        )

    res = pd.DataFrame(rows)
    base_ap = float(res.loc[res["variant"] == "persistence", "pooled_ap"].iloc[0])
    res["d_ap_vs_persistence"] = res["pooled_ap"] - base_ap
    res = res.sort_values("pooled_ap", ascending=False)

    # Year-block bootstrap on the best variant's per-window AP advantage
    best = res.iloc[0]["variant"]
    if best != "persistence":
        pb = oofs["persistence"]
        bb = oofs[best]
        by_year = {}
        for yr in sorted(bb["year"].unique()):
            a = bb[bb["year"] == yr]
            b = pb[pb["year"] == yr]
            if a["flood_event"].nunique() < 2:
                continue
            by_year[int(yr)] = [
                average_precision_score(a["flood_event"], a["score"].fillna(0))
                - average_precision_score(b["flood_event"], b["score"].fillna(0))
            ]
        if len(by_year) >= 2:
            lo, hi = block_bootstrap_ci(by_year, n=4000, seed=SEED)
            print(
                f"\nyear-block bootstrap, {best} minus persistence AP on event "
                f"years: {np.mean([v[0] for v in by_year.values()]):+.3f} "
                f"[{lo:+.3f}, {hi:+.3f}] (descriptive; {len(by_year)} event years)"
            )

    # --- ONSET regime -------------------------------------------------------
    # Restricted to district-windows that were dry at issue time. This is the
    # question an early-warning system exists to answer, and the one the lagged
    # target cannot answer for itself.
    print("\n" + "=" * 72)
    print("ONSET ONLY: district was dry when the window opened")
    print("=" * 72)
    onset_rows, onset_oofs = [], {}
    for name, (feats, fac) in VARIANTS.items():
        oof = run_variant(df, feats, fac, onset_only=True)
        onset_oofs[name] = oof
        rec = score_variant(name, oof)
        rec["n_features"] = len(feats)
        rec["regime"] = "onset"
        onset_rows.append(rec)
        print(
            f"{name:26s} AP={rec['pooled_ap']:.3f}  R@5={rec['recall_at_5']:.3f}  "
            f"2025 caught {rec['caught_2025_top5']}/{rec['n_flooded_2025']}"
        )

    ores = pd.DataFrame(onset_rows)
    obase = float(ores.loc[ores["variant"] == "persistence", "pooled_ap"].iloc[0])
    ores["d_ap_vs_persistence"] = ores["pooled_ap"] - obase
    ores = ores.sort_values("pooled_ap", ascending=False)
    print()
    print(
        ores[
            [
                "variant",
                "n_features",
                "pooled_ap",
                "d_ap_vs_persistence",
                "recall_at_5",
                "caught_2025_top5",
            ]
        ].to_string(index=False)
    )

    obest = ores.iloc[0]["variant"]
    if obest != "persistence":
        pb, bb = onset_oofs["persistence"], onset_oofs[obest]
        by_year = {}
        for yr in sorted(bb["year"].unique()):
            a = bb[bb["year"] == yr]
            b = pb[pb["year"] == yr]
            if a["flood_event"].nunique() < 2:
                continue
            by_year[int(yr)] = [
                average_precision_score(a["flood_event"], a["score"].fillna(0))
                - average_precision_score(b["flood_event"], b["score"].fillna(0))
            ]
        if len(by_year) >= 2:
            lo, hi = block_bootstrap_ci(by_year, n=4000, seed=SEED)
            print(
                f"\nyear-block bootstrap, {obest} minus persistence AP on onset: "
                f"{np.mean([v[0] for v in by_year.values()]):+.3f} "
                f"[{lo:+.3f}, {hi:+.3f}] (descriptive; {len(by_year)} event years)"
            )

    res["regime"] = "all_rows"
    res = pd.concat([res, ores], ignore_index=True)
    res.to_csv(OUT_METRICS, index=False)
    pd.concat(
        [o.assign(variant=n) for n, o in oofs.items()], ignore_index=True
    ).to_csv(OUT_OOF, index=False)
    print(f"\nwrote {OUT_METRICS}")
    print(
        res[
            [
                "variant",
                "n_features",
                "pooled_ap",
                "d_ap_vs_persistence",
                "recall_at_5",
                "caught_2025_top5",
                "missed_2025",
            ]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()
