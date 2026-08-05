# pipeline/run_forecaster_selection.py
"""Honest variant selection: choose the whole model inside the fold.

The comparison in `run_forecaster_v2.py` fits many variants and shows all of
them. Reading the best number off that table and calling it the result would be
selection on the test years, which with three event seasons and ten onset
transitions is not a small effect.

This script answers the harder question: if the model had been chosen WITHOUT
seeing the year it is judged on, how well would it have done? For each held-out
year the candidate variants are compared by an inner leave-one-year-out sweep
over the training years only; the winner of that inner sweep is refitted on the
training years and applied once to the held-out year. Nothing about the held-out
year takes part in choosing the variant, the features or the penalty.

The inner comparison uses a fixed penalty for speed; only the selected variant
pays for the full inner penalty sweep. That approximation is recorded here
because it is the one place the procedure is not fully nested.

Run: python -m pipeline.run_forecaster_selection
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score

from sailaab import config
from sailaab.forecast_v2 import (
    block_bootstrap_ci,
    fold_safe_prior,
    quiet_window_alert_rate,
    recall_at_k,
)
from pipeline.run_forecaster_v2 import (
    BASE,
    DIST_RAIN_NOW,
    DIST_RAIN_PRE,
    LEAD5,
    PRIOR,
    SEED,
    STATE_RAIN,
    NestedLogReg,
    _logreg,
    build_frame,
)

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = DATA / "forecaster_selection.csv"

# Candidate pool offered to the selector. Persistence is included so the
# procedure is free to conclude that the baseline was the right choice.
CANDIDATES = {
    "persistence": None,
    "nested_antecedent_prior": BASE + PRIOR,
    "nested_statewide_rain": BASE + STATE_RAIN + PRIOR,
    "nested_district_rain": BASE + STATE_RAIN + DIST_RAIN_NOW + DIST_RAIN_PRE + PRIOR,
    "nested_district_rain_only": BASE + DIST_RAIN_NOW + PRIOR,
    "nested_lead_5day": BASE + DIST_RAIN_PRE + LEAD5 + ["upstream_mm_lag1"] + PRIOR,
}


def _onset(core: pd.DataFrame) -> pd.DataFrame:
    dry = core["antecedent_fraction"] <= config.FLOOD_EVENT_FRACTION
    return core[dry.fillna(True)]


def _inner_ap(frame: pd.DataFrame, feats, train_years) -> float:
    """Inner leave-one-year-out average precision over the training years."""
    preds, truths = [], []
    for inner in train_years:
        tr = frame[frame["year"].isin([y for y in train_years if y != inner])]
        te = frame[frame["year"] == inner]
        if te.empty or tr["flood_event"].nunique() < 2:
            continue
        if feats is None:
            p = te["antecedent_fraction"].fillna(0.0).to_numpy()
        else:
            p = _logreg(0.1).fit(tr[feats], tr["flood_event"]).predict_proba(te[feats])[
                :, 1
            ]
        preds.append(p)
        truths.append(te["flood_event"].to_numpy(dtype=float))
    if not preds:
        return float("nan")
    yy, pp = np.concatenate(truths), np.concatenate(preds)
    if len(np.unique(yy)) < 2:
        return float("nan")
    return float(average_precision_score(yy, pp))


def main() -> None:
    df = build_frame()
    years = sorted(df["year"].unique())

    rows, picks = [], []
    for test_year in years:
        train_years = [y for y in years if y != test_year]
        prior = fold_safe_prior(df, train_years)
        fold = df.merge(prior, on="district", how="left", validate="m:1")
        onset = _onset(fold[fold["core_season"]])

        tr_all = onset[onset["year"].isin(train_years)]
        te = onset[onset["year"] == test_year].copy()
        if te.empty:
            continue

        # choose the variant using ONLY the training years
        scores = {
            name: _inner_ap(tr_all, feats, train_years)
            for name, feats in CANDIDATES.items()
        }
        valid = {k: v for k, v in scores.items() if not np.isnan(v)}
        chosen = max(valid, key=valid.get) if valid else "persistence"
        feats = CANDIDATES[chosen]
        picks.append(chosen)

        if feats is None or tr_all["flood_event"].nunique() < 2:
            te["score"] = te["antecedent_fraction"].fillna(0.0)
            best_c = None
        else:
            m = NestedLogReg(tr_all["year"].to_numpy()).fit(
                tr_all[feats], tr_all["flood_event"]
            )
            te["score"] = m.predict_proba(te[feats])[:, 1]
            best_c = m.best_C_

        te["chosen_variant"] = chosen
        te["chosen_C"] = best_c
        rows.append(te)
        print(
            f"{test_year}: chose {chosen:28s} C={best_c}  "
            f"positives={int(te['flood_event'].sum())}"
        )

    oof = pd.concat(rows, ignore_index=True)
    y = oof["flood_event"].to_numpy(dtype=float)
    p = oof["score"].to_numpy(dtype=float)
    groups = (oof["year"].astype(str) + "|" + oof["window_start"]).to_numpy()

    # the same procedure, but forced to persistence every year
    pb = oof["antecedent_fraction"].fillna(0.0).to_numpy()

    print("\n" + "=" * 68)
    print("HONEST SELECTION: variant chosen inside each fold, onset regime")
    print("=" * 68)
    print(f"variants chosen across folds: {dict(Counter(picks))}")
    for label, scores in (("selected", p), ("persistence", pb)):
        print(
            f"{label:12s} AP={average_precision_score(y, scores):.3f}  "
            f"ROC={roc_auc_score(y, scores):.3f}  "
            f"R@3={recall_at_k(y, scores, groups, k=3):.3f}  "
            f"R@5={recall_at_k(y, scores, groups, k=5):.3f}  "
            f"quiet_alerts={quiet_window_alert_rate(y, scores, groups, 0.5):.3f}"
        )

    by_year = {}
    for yr in sorted(oof["year"].unique()):
        s = oof[oof["year"] == yr]
        if s["flood_event"].nunique() < 2:
            continue
        yy = s["flood_event"].to_numpy(dtype=float)
        by_year[int(yr)] = [
            average_precision_score(yy, s["score"].to_numpy(dtype=float))
            - average_precision_score(
                yy, s["antecedent_fraction"].fillna(0.0).to_numpy()
            )
        ]
    print("\nper event-year AP difference (selected minus persistence):")
    for yr, v in by_year.items():
        print(f"  {yr}: {v[0]:+.3f}")
    if len(by_year) >= 2:
        lo, hi = block_bootstrap_ci(by_year, n=4000, seed=SEED)
        mean = float(np.mean([v[0] for v in by_year.values()]))
        print(
            f"  equal-year mean {mean:+.3f}, year-block interval "
            f"[{lo:+.3f}, {hi:+.3f}] (descriptive, {len(by_year)} blocks)"
        )

    oof.to_csv(OUT, index=False)
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
