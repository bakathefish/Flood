# pipeline/run_ablation.py
"""Reservoir-feature ablation for the district flood forecaster.

Pre-declared protocol: ``docs/notes/ablation.md`` (committed BEFORE this ran).
Tests whether the 6 reservoir features carry *incremental* skill or the model is
robust without them, across four pre-declared variants (full / no_reservoir /
meteo_prior / persistence).

Reuses the shipped forecaster harness verbatim so the comparison is
apples-to-apples on the identical 1540-row core-season frame:
  * ``build_dataset`` / ``hindcast_2025`` and the flag constants
    (FLAG_TOPN, FLAG_PROB, EVENT_WINDOWS_2025, EARLY_WARN_MD, NAMED_2025,
    F1_THRESHOLD) from ``pipeline.run_forecaster``;
  * ``loyo_splits`` from ``sailaab.model``;
  * the private ``_mk_clf`` classifier factory from ``pipeline.run_forecaster``
    (imported within-repo, by design — the ablation MUST use the identical
    classifier construction so the ``full`` variant reproduces the shipped
    pooled metrics as a consistency gate).

Classifier only — the fraction regressor is NOT part of this ablation. The only
degree of freedom across variants is the feature list
(``sailaab.ablation.variant_features``); ``persistence`` skips the fit entirely
and scores by antecedent_fraction (``sailaab.ablation.persistence_scores``),
applying the SAME flag formula (the P>=0.50 criterion simply will not trigger on
raw fractions).

Committed output (the ONLY file written; overwrites no run_forecaster artifact):
  data/forecaster_ablation.csv   one row per variant with pooled metrics,
                                 2025 flag metrics, and deltas vs full.

All inputs are committed CSVs (no network). Deterministic: rerun -> byte-identical.

Run: python -m pipeline.run_ablation
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from pipeline.run_forecaster import (
    EARLY_WARN_MD,
    EVENT_WINDOWS_2025,
    F1_THRESHOLD,
    FLAG_PROB,
    FLAG_TOPN,
    NAMED_2025,
    _mk_clf,
    build_dataset,
    hindcast_2025,
)
from sailaab.ablation import ablation_row, persistence_scores, variant_features
from sailaab.forecast_features import classification_metrics
from sailaab.model import loyo_splits

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT_CSV = DATA / "forecaster_ablation.csv"

# Shipped POOLED targets (data/forecaster_loyo_metrics.csv) — the consistency gate.
GATE_PR_AUC = 0.26871129603879135
GATE_ROC_AUC = 0.9458887175344545
GATE_TOL = 0.005


def loyo_oof_clf(core: pd.DataFrame, features: list[str]) -> pd.DataFrame:
    """Classifier-only leave-one-year-out out-of-fold probabilities.

    Mirrors the classifier half of ``run_forecaster.loyo_oof`` exactly (same
    ``_mk_clf``, same ``loyo_splits`` folds, same feature-frame slicing),
    omitting the fraction regressor which plays no part in this ablation. Because
    each fold refits a fresh ``_mk_clf`` on identical data, the ``full`` variant
    reproduces the shipped classifier probabilities bit-for-bit."""
    years = sorted(core["year"].unique())
    oof = core[["year", "district", "window_md", "flood_event"]].copy()
    oof["prob"] = np.nan
    for train_years, test_year in loyo_splits(years):
        tr = core[core.year.isin(train_years)]
        te = core[core.year == test_year]
        clf = _mk_clf().fit(tr[features], tr["flood_event"])
        oof.loc[te.index, "prob"] = clf.predict_proba(te[features])[:, 1]
    return oof


def pooled_pr_roc(oof: pd.DataFrame) -> tuple[float, float]:
    """Pooled out-of-fold PR-AUC and ROC-AUC via the shipped metric wrapper
    (identical to the POOLED row of ``run_forecaster.loyo_metrics_table``)."""
    m = classification_metrics(oof["flood_event"], oof["prob"], F1_THRESHOLD)
    return m["pr_auc"], m["roc_auc"]


def persistence_hindcast(core: pd.DataFrame) -> tuple[dict, dict]:
    """2025 flag/early readout for the persistence baseline: rank districts per
    window by ``antecedent_fraction`` and apply the shipped flag formula verbatim
    (top-``FLAG_TOPN`` of 20 OR P>=``FLAG_PROB``). Replicates the flag block of
    ``run_forecaster.hindcast_2025`` with the score column swapped for the
    fit-free persistence score."""
    c25 = core[core.year == 2025].copy()
    c25["risk"] = persistence_scores(c25)
    c25["rank"] = (
        c25.groupby("window_md")["risk"].rank(ascending=False, method="min").astype(int)
    )
    ev = c25[c25.window_md.isin(EVENT_WINDOWS_2025)]
    flags = {}
    for d in NAMED_2025:
        sub = ev[ev.district == d]
        best_rank = int(sub["rank"].min()) if len(sub) else 99
        best_prob = float(sub["risk"].max()) if len(sub) else float("nan")
        flags[d] = {
            "best_rank": best_rank,
            "best_prob": round(best_prob, 4),
            "flagged": bool(best_rank <= FLAG_TOPN or best_prob >= FLAG_PROB),
        }
    early = {}
    ew = c25[c25.window_md == EARLY_WARN_MD]
    for d in NAMED_2025:
        sub = ew[ew.district == d]
        early[d] = (
            {
                "rank": int(sub["rank"].iloc[0]),
                "prob": round(float(sub["risk"].iloc[0]), 4),
            }
            if len(sub)
            else None
        )
    return flags, early


def main():
    df, features = build_dataset()
    core = df[df.core_season == 1].copy()
    n_nan_antecedent = int(core["antecedent_fraction"].isna().sum())

    rows = []
    debug = {}

    # ---- full FIRST: consistency gate before any other number is read ----
    full_feats = variant_features(features, "full")
    full_oof = loyo_oof_clf(core, full_feats)
    full_pr, full_roc = pooled_pr_roc(full_oof)
    gate_pass = (
        abs(full_pr - GATE_PR_AUC) <= GATE_TOL
        and abs(full_roc - GATE_ROC_AUC) <= GATE_TOL
    )
    if not gate_pass:
        raise SystemExit(
            "CONSISTENCY GATE FAILED — halting before any other variant is read.\n"
            f"  full pooled PR-AUC = {full_pr:.6f} "
            f"(target {GATE_PR_AUC:.6f} +/- {GATE_TOL})\n"
            f"  full pooled ROC-AUC = {full_roc:.6f} "
            f"(target {GATE_ROC_AUC:.6f} +/- {GATE_TOL})\n"
            "Debug library versions / fold construction before trusting any result."
        )

    _, _, full_flags, full_early = hindcast_2025(core, full_feats)
    full_row = ablation_row(
        "full", len(full_feats), full_pr, full_roc, full_flags, full_early
    )
    rows.append(full_row)
    debug["full"] = {"flags": full_flags, "early": full_early}

    # ---- remaining model variants (deltas vs full) ----
    for variant in ["no_reservoir", "meteo_prior"]:
        feats = variant_features(features, variant)
        oof = loyo_oof_clf(core, feats)
        pr, roc = pooled_pr_roc(oof)
        _, _, flags, early = hindcast_2025(core, feats)
        rows.append(
            ablation_row(variant, len(feats), pr, roc, flags, early, full_row=full_row)
        )
        debug[variant] = {"flags": flags, "early": early}

    # ---- persistence (no fit; antecedent_fraction as the score) ----
    p_metrics = classification_metrics(
        core["flood_event"], persistence_scores(core), F1_THRESHOLD
    )
    p_flags, p_early = persistence_hindcast(core)
    rows.append(
        ablation_row(
            "persistence",
            1,
            p_metrics["pr_auc"],
            p_metrics["roc_auc"],
            p_flags,
            p_early,
            full_row=full_row,
        )
    )
    debug["persistence"] = {"flags": p_flags, "early": p_early}

    out = pd.DataFrame(rows)
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT_CSV, index=False)

    # ---- pre-declared expectation checks (reported either way) ----
    by = {r["variant"]: r for r in rows}
    exp_a = (
        by["full"]["pooled_pr_auc"]
        >= by["no_reservoir"]["pooled_pr_auc"]
        >= by["meteo_prior"]["pooled_pr_auc"]
    )
    exp_b = all(
        by[v]["pooled_pr_auc"] > by["persistence"]["pooled_pr_auc"]
        for v in ("full", "no_reservoir", "meteo_prior")
    )

    summary = {
        "n_core_rows": int(len(core)),
        "n_events": int(core.flood_event.sum()),
        "base_rate": float(core.flood_event.mean()),
        "n_nan_antecedent_core": n_nan_antecedent,
        "consistency_gate": {
            "full_pr_auc": full_pr,
            "full_roc_auc": full_roc,
            "target_pr_auc": GATE_PR_AUC,
            "target_roc_auc": GATE_ROC_AUC,
            "tol": GATE_TOL,
            "pass": gate_pass,
        },
        "expectation_a_monotone_pr": bool(exp_a),
        "expectation_b_beats_persistence": bool(exp_b),
        "rows": rows,
        "flags": {k: debug[k]["flags"] for k in debug},
        "early": {k: debug[k]["early"] for k in debug},
    }
    print("ABLATION_SUMMARY_JSON_START")
    print(json.dumps(summary, indent=2, default=float))
    print("ABLATION_SUMMARY_JSON_END")


if __name__ == "__main__":
    main()
