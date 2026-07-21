# pipeline/run_forecaster.py
"""District flood-risk forecaster: assemble -> LOYO -> 2025 hindcast -> SHAP.

Reuses `sailaab.dataset` (assemble/label_events), `sailaab.model`
(loyo_splits/fit_eval), and `sailaab.forecast_features` (reservoir pivot,
core-season mask, district prior, metric wrappers). All inputs are committed
CSVs (no network). See `docs/notes/forecaster.md` for the pre-declared bands and
the paddy-contamination decision that scopes modelling to core-season windows.

Committed outputs:
  data/forecaster_dataset.csv        full assembled district x window x year frame
  data/forecaster_loyo_metrics.csv   per-year + pooled LOYO metrics
  data/models/forecaster_2025.joblib final classifier (fit 2015-2024, core season)
  atlas/forecaster_shap.png          SHAP mean-|value| summary bar

Run: python -m pipeline.run_forecaster   (or python pipeline/run_forecaster.py)
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from sailaab import config
from sailaab.dataset import assemble, label_events
from sailaab.forecast_features import (
    PADDY_CUTOFF_MD,
    add_district_prior,
    classification_metrics,
    core_season_mask,
    pivot_reservoirs,
    regression_metrics,
)
from sailaab.model import fit_eval, loyo_splits

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
ATLAS = ROOT / "atlas"
MODELS = DATA / "models"

RAIN_FEATURES = [
    "punjab_mm",
    "upstream_mm",
    "punjab_mm_lag1",
    "upstream_mm_lag1",
    "punjab_mm_lag2",
    "upstream_mm_lag2",
]
PRIOR_COLS = ["mean_annual_flooded_ha", "seasons_with_fraction_gt2pct"]

NAMED_2025 = ["Firozpur", "Gurdaspur", "Kapurthala", "Tarn Taran", "Amritsar"]
EVENT_WINDOWS_2025 = ["08-14", "08-24", "09-03"]  # windows spanning Aug 22 - Sep 6
EARLY_WARN_MD = "08-14"  # first event window, before the Aug 26-27 dam-release peak
F1_THRESHOLD = 0.50
FLAG_TOPN = 5
FLAG_PROB = 0.50


def _mk_clf():
    """XGBoost classifier mirroring sailaab.model._make_model."""
    from xgboost import XGBClassifier

    return XGBClassifier(
        n_estimators=300,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.9,
        eval_metric="logloss",
    )


def _mk_reg():
    from xgboost import XGBRegressor

    return XGBRegressor(
        n_estimators=300,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.9,
    )


def build_dataset() -> tuple[pd.DataFrame, list[str]]:
    """Join target + rain + reservoirs + district prior, add antecedent/week/event
    over the FULL season, return (full assembled frame, feature list)."""
    tgt = pd.read_csv(DATA / "gfm_district_window_fractions_2015_2025.csv").rename(
        columns={"fraction": "flooded_fraction"}
    )
    rain = pd.read_csv(DATA / "rain_windows_2015_2025.csv").drop(columns=["window_end"])
    resw = pivot_reservoirs(pd.read_csv(DATA / "reservoir_windows.csv"))
    prior = pd.read_csv(DATA / "flood_frequency_districts_late_season.csv")

    df = tgt.merge(rain, on=["year", "window_start"], how="left")
    df = df.merge(resw, on=["year", "window_start"], how="left")
    df = add_district_prior(df, prior, PRIOR_COLS)

    # antecedent_fraction + week_of_season over the full 11-window season, then label
    df = assemble(label_events(df, threshold=config.FLOOD_EVENT_FRACTION))
    df["window_md"] = df["window_start"].astype(str).str.slice(5)
    df["core_season"] = core_season_mask(df).astype(int)

    res_feats = sorted(c for c in df.columns if c.endswith(("_storage", "_delta")))
    prior_feats = sorted(f"prior_{c}" for c in PRIOR_COLS)
    features = (
        RAIN_FEATURES
        + res_feats
        + ["antecedent_fraction", "week_of_season"]
        + prior_feats
    )
    return df, features


def loyo_oof(core: pd.DataFrame, features: list[str]) -> pd.DataFrame:
    """Leave-one-year-out out-of-fold predictions (classifier prob + regressor
    fraction) for every core-season row, using sailaab.model.loyo_splits folds."""
    years = sorted(core["year"].unique())
    oof = core[
        ["year", "district", "window_md", "flood_event", "flooded_fraction"]
    ].copy()
    oof["prob"] = np.nan
    oof["pred_frac"] = np.nan
    for train_years, test_year in loyo_splits(years):
        tr = core[core.year.isin(train_years)]
        te = core[core.year == test_year]
        clf = _mk_clf().fit(tr[features], tr["flood_event"])
        oof.loc[te.index, "prob"] = clf.predict_proba(te[features])[:, 1]
        reg = _mk_reg().fit(tr[features], tr["flooded_fraction"])
        oof.loc[te.index, "pred_frac"] = reg.predict(te[features])
    return oof


def loyo_metrics_table(oof: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for y in sorted(oof.year.unique()):
        d = oof[oof.year == y]
        cm = classification_metrics(d.flood_event, d.prob, F1_THRESHOLD)
        rm = regression_metrics(d.flooded_fraction, d.pred_frac)
        rows.append(
            {
                "year": str(y),
                **{f"cls_{k}": v for k, v in cm.items()},
                **{f"reg_{k}": v for k, v in rm.items()},
            }
        )
    cm = classification_metrics(oof.flood_event, oof.prob, F1_THRESHOLD)
    rm = regression_metrics(oof.flooded_fraction, oof.pred_frac)
    rows.append(
        {
            "year": "POOLED",
            **{f"cls_{k}": v for k, v in cm.items()},
            **{f"reg_{k}": v for k, v in rm.items()},
        }
    )
    return pd.DataFrame(rows)


def hindcast_2025(core: pd.DataFrame, features: list[str]):
    """Fit classifier on 2015-2024 core season, score every 2025 core window."""
    train = core[core.year < 2025]
    model = _mk_clf().fit(train[features], train["flood_event"])
    c25 = core[core.year == 2025].copy()
    c25["risk"] = model.predict_proba(c25[features])[:, 1]
    # per-window rank (1 = highest risk of the 20 districts)
    c25["rank"] = (
        c25.groupby("window_md")["risk"].rank(ascending=False, method="min").astype(int)
    )

    ev = c25[c25.window_md.isin(EVENT_WINDOWS_2025)]
    flags = {}
    for d in NAMED_2025:
        sub = ev[ev.district == d]
        best_rank = int(sub["rank"].min()) if len(sub) else 99
        best_prob = float(sub["risk"].max()) if len(sub) else float("nan")
        flagged = bool(best_rank <= FLAG_TOPN or best_prob >= FLAG_PROB)
        flags[d] = {
            "best_rank": best_rank,
            "best_prob": round(best_prob, 4),
            "flagged": flagged,
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
    return model, c25, flags, early


def shap_summary(model, train_feats: pd.DataFrame, features: list[str], out_png: Path):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import shap

    expl = shap.TreeExplainer(model)
    sv = expl.shap_values(train_feats[features])
    mean_abs = np.abs(sv).mean(axis=0)
    order = np.argsort(mean_abs)[::-1]
    top = [(features[i], float(mean_abs[i])) for i in order]

    plt.figure(figsize=(7, 5))
    shap.summary_plot(
        sv,
        train_feats[features],
        plot_type="bar",
        show=False,
        max_display=len(features),
    )
    plt.tight_layout()
    out_png.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_png, dpi=120)
    plt.close("all")
    return top


def main():
    MODELS.mkdir(parents=True, exist_ok=True)
    ATLAS.mkdir(parents=True, exist_ok=True)

    df, features = build_dataset()
    core = df[df.core_season == 1].copy()

    # ---- LOYO (my own OOF loop; richer metrics than fit_eval's ROC-AUC) ----
    oof = loyo_oof(core, features)
    metrics = loyo_metrics_table(oof)
    metrics.to_csv(DATA / "forecaster_loyo_metrics.csv", index=False)

    # cross-check against sailaab.model.fit_eval canonical per-year ROC-AUC
    fe = fit_eval(core, features, "flood_event")
    fe_auc = {int(r["year"]): r.get("auc") for r in fe["per_year"]}

    # ---- 2025 showcase hindcast ----
    model, c25, flags, early = hindcast_2025(core, features)

    # ---- SHAP on the 2015-2024 core-season fit ----
    top = shap_summary(
        model, core[core.year < 2025], features, ATLAS / "forecaster_shap.png"
    )

    # ---- persist ----
    df.to_csv(DATA / "forecaster_dataset.csv", index=False)
    import joblib

    joblib.dump(
        {
            "model": model,
            "features": features,
            "trained_years": "2015-2024",
            "target": "flood_event",
            "event_fraction": config.FLOOD_EVENT_FRACTION,
            "paddy_cutoff_md": PADDY_CUTOFF_MD,
        },
        MODELS / "forecaster_2025.joblib",
    )

    pooled = metrics[metrics.year == "POOLED"].iloc[0].to_dict()
    sizes = {
        "forecaster_dataset.csv": (DATA / "forecaster_dataset.csv").stat().st_size,
        "forecaster_2025.joblib": (MODELS / "forecaster_2025.joblib").stat().st_size,
        "forecaster_shap.png": (ATLAS / "forecaster_shap.png").stat().st_size,
    }
    summary = {
        "n_core_rows": int(len(core)),
        "base_rate": float((core.flood_event).mean()),
        "pooled": {k: pooled[k] for k in pooled if k != "year"},
        "per_year": metrics[metrics.year != "POOLED"][
            [
                "year",
                "cls_n_pos",
                "cls_pr_auc",
                "cls_roc_auc",
                "reg_spearman",
                "reg_mae",
            ]
        ].to_dict("records"),
        "fit_eval_auc_crosscheck": fe_auc,
        "shap_top": top[:6],
        "hindcast_flags": flags,
        "early_warning_rank_0814": early,
        "n_flagged": int(sum(v["flagged"] for v in flags.values())),
        "file_sizes_bytes": sizes,
    }
    print("FORECASTER_SUMMARY_JSON_START")
    print(json.dumps(summary, indent=2, default=float))
    print("FORECASTER_SUMMARY_JSON_END")


if __name__ == "__main__":
    main()
