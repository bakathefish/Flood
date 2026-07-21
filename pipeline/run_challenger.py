# pipeline/run_challenger.py
"""Champion vs challenger forecaster experiment + champion conformal intervals.

CHAMPION  = the committed 16-feature forecaster (frozen).
CHALLENGER = champion's 16 features + 6 sub-daily ERA5 intensity features
             (``data/rain_intensity_windows.csv``).

Everything reuses the champion harness verbatim — ``pipeline.run_forecaster``'s
``build_dataset`` / ``loyo_oof`` / ``loyo_metrics_table`` / ``hindcast_2025`` and
the same ``sailaab.model`` LOYO folds and XGBoost config — so the comparison is
apples-to-apples on the identical 1540-row core-season frame. The adoption rule
was pre-declared in ``docs/notes/challenger.md`` BEFORE this ran.

Conformal (both outcomes): split-conformal prediction intervals for the champion's
regression head from LOYO-honest out-of-fold residuals (``sailaab.conformal``).

Committed outputs:
  data/rain_intensity_windows.csv     (built by pipeline/fetch_era5_intensity.py)
  data/forecaster_challenger_loyo.csv champion-vs-challenger per-year + pooled LOYO
  data/forecaster_conformal.csv       champion per-row pred + 80/95 intervals
  data/models/forecaster_2025_v2.joblib  ONLY if the challenger is adopted

Run: python -m pipeline.run_challenger
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from pipeline.run_forecaster import (
    EVENT_WINDOWS_2025,
    NAMED_2025,
    _mk_clf,
    build_dataset,
    hindcast_2025,
    loyo_metrics_table,
    loyo_oof,
)
from sailaab import config
from sailaab.conformal import empirical_coverage, loyo_conformal
from sailaab.forecast_features import PADDY_CUTOFF_MD

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
MODELS = DATA / "models"

INTENSITY_CSV = DATA / "rain_intensity_windows.csv"
INTENSITY_COLS = [
    "punjab_max_3h_mm",
    "punjab_max_24h_mm",
    "punjab_hours_ge5mm",
    "upstream_max_3h_mm",
    "upstream_max_24h_mm",
    "upstream_hours_ge5mm",
]

# Pre-declared adoption thresholds (docs/notes/challenger.md).
ROC_GAIN_MIN = 0.005
PR_GAIN_MIN = 0.02
HINDCAST_MIN_FLAGS = 5


def build_challenger_frame():
    """Champion assembled frame + merged intensity columns; returns
    ``(df, champion_features, challenger_features)``."""
    df, champ_features = build_dataset()
    intens = pd.read_csv(INTENSITY_CSV).drop(columns=["window_end"])
    df = df.merge(intens, on=["year", "window_start"], how="left")
    missing = df.loc[df.core_season == 1, INTENSITY_COLS].isna().any().any()
    if missing:
        raise RuntimeError("intensity columns have NaNs on core-season rows")
    chal_features = champ_features + INTENSITY_COLS
    return df, champ_features, chal_features


def _pooled(metrics: pd.DataFrame) -> pd.Series:
    return metrics[metrics.year == "POOLED"].iloc[0]


def side_by_side(champ_m: pd.DataFrame, chal_m: pd.DataFrame) -> pd.DataFrame:
    """Merge the two LOYO metric tables into one champion-vs-challenger frame."""
    keep = ["year", "cls_n_pos", "cls_pr_auc", "cls_roc_auc", "reg_spearman", "reg_mae"]
    a = champ_m[keep].rename(columns={c: f"champ_{c}" for c in keep if c != "year"})
    b = chal_m[keep].rename(columns={c: f"chal_{c}" for c in keep if c != "year"})
    m = a.merge(b, on="year")
    m["d_pr_auc"] = m["chal_cls_pr_auc"] - m["champ_cls_pr_auc"]
    m["d_roc_auc"] = m["chal_cls_roc_auc"] - m["champ_cls_roc_auc"]
    return m


def decide(champ_pooled: pd.Series, chal_pooled: pd.Series, chal_flags: int) -> dict:
    """Apply the three pre-declared thresholds. Adopt iff ALL hold."""
    roc_gain = float(chal_pooled.cls_roc_auc - champ_pooled.cls_roc_auc)
    pr_gain = float(chal_pooled.cls_pr_auc - champ_pooled.cls_pr_auc)
    c1 = roc_gain >= ROC_GAIN_MIN
    c2 = pr_gain >= PR_GAIN_MIN
    c3 = chal_flags >= HINDCAST_MIN_FLAGS
    return {
        "roc_gain": roc_gain,
        "pr_gain": pr_gain,
        "chal_flags": int(chal_flags),
        "cond_roc": bool(c1),
        "cond_pr": bool(c2),
        "cond_hindcast": bool(c3),
        "adopt": bool(c1 and c2 and c3),
    }


def champion_conformal(core: pd.DataFrame, champ_oof: pd.DataFrame) -> tuple:
    """LOYO-honest split-conformal intervals for the champion regression head.
    Returns ``(conformal_df, coverage_dict)``."""
    years = core["year"].to_numpy()
    y_true = core["flooded_fraction"].to_numpy()
    pred = champ_oof.loc[core.index, "pred_frac"].to_numpy()
    conf = loyo_conformal(
        years, y_true, pred, coverage_levels=(0.80, 0.95), lo_clip=0.0, hi_clip=1.0
    )
    cov = {
        "cov80": empirical_coverage(y_true, conf[0.80]["lo"], conf[0.80]["hi"]),
        "cov95": empirical_coverage(y_true, conf[0.95]["lo"], conf[0.95]["hi"]),
        "n": int(len(core)),
    }
    out = (
        pd.DataFrame(
            {
                "year": years,
                "window": core["window_start"].to_numpy(),
                "district": core["district"].to_numpy(),
                "pred": pred.round(6),
                "lo80": conf[0.80]["lo"].round(6),
                "hi80": conf[0.80]["hi"].round(6),
                "lo95": conf[0.95]["lo"].round(6),
                "hi95": conf[0.95]["hi"].round(6),
            }
        )
        .sort_values(["year", "window", "district"])
        .reset_index(drop=True)
    )
    return out, cov


def main():
    MODELS.mkdir(parents=True, exist_ok=True)
    df, champ_features, chal_features = build_challenger_frame()
    core = df[df.core_season == 1].copy()

    # ---- LOYO champion vs challenger on the identical core frame ----
    champ_oof = loyo_oof(core, champ_features)
    chal_oof = loyo_oof(core, chal_features)
    champ_m = loyo_metrics_table(champ_oof)
    chal_m = loyo_metrics_table(chal_oof)
    table = side_by_side(champ_m, chal_m)
    table.to_csv(DATA / "forecaster_challenger_loyo.csv", index=False)

    champ_pooled = _pooled(champ_m)
    chal_pooled = _pooled(chal_m)

    # ---- 2025 hindcast for both feature sets ----
    _, _, champ_flags, champ_early = hindcast_2025(core, champ_features)
    chal_model, _, chal_flags, chal_early = hindcast_2025(core, chal_features)
    champ_nflag = int(sum(v["flagged"] for v in champ_flags.values()))
    chal_nflag = int(sum(v["flagged"] for v in chal_flags.values()))

    # ---- verdict (pre-declared rule) ----
    verdict = decide(champ_pooled, chal_pooled, chal_nflag)

    if verdict["adopt"]:
        import joblib

        joblib.dump(
            {
                "model": chal_model,
                "features": chal_features,
                "trained_years": "2015-2024",
                "target": "flood_event",
                "event_fraction": config.FLOOD_EVENT_FRACTION,
                "paddy_cutoff_md": PADDY_CUTOFF_MD,
                "parent": "forecaster_2025.joblib",
                "added_features": INTENSITY_COLS,
            },
            MODELS / "forecaster_2025_v2.joblib",
        )

    # ---- champion conformal (runs regardless of verdict) ----
    conformal_df, cov = champion_conformal(core, champ_oof)
    conformal_df.to_csv(DATA / "forecaster_conformal.csv", index=False)

    summary = {
        "n_core_rows": int(len(core)),
        "n_events": int(core.flood_event.sum()),
        "champion_pooled": {
            "pr_auc": float(champ_pooled.cls_pr_auc),
            "roc_auc": float(champ_pooled.cls_roc_auc),
            "spearman": float(champ_pooled.reg_spearman),
            "mae": float(champ_pooled.reg_mae),
        },
        "challenger_pooled": {
            "pr_auc": float(chal_pooled.cls_pr_auc),
            "roc_auc": float(chal_pooled.cls_roc_auc),
            "spearman": float(chal_pooled.reg_spearman),
            "mae": float(chal_pooled.reg_mae),
        },
        "champion_hindcast_flags": {k: v["flagged"] for k, v in champ_flags.items()},
        "challenger_hindcast_flags": {
            k: {
                "best_rank": v["best_rank"],
                "best_prob": v["best_prob"],
                "flagged": v["flagged"],
            }
            for k, v in chal_flags.items()
        },
        "champion_n_flagged": champ_nflag,
        "challenger_n_flagged": chal_nflag,
        "verdict": verdict,
        "conformal_coverage": cov,
        "side_by_side": table.to_dict("records"),
    }
    print("CHALLENGER_SUMMARY_JSON_START")
    print(json.dumps(summary, indent=2, default=float))
    print("CHALLENGER_SUMMARY_JSON_END")


if __name__ == "__main__":
    main()
