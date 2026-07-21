# sailaab/forecast_features.py
"""Pure feature/metric helpers for the district flood-risk forecaster.

No IO, no Earth Engine, no model fitting — deterministic pandas/numpy transforms
plus thin metric wrappers. Composes with ``sailaab.dataset`` (assemble /
label_events) and ``sailaab.model`` (loyo_splits / fit_eval); those two modules
are used as-is and never edited here.

The paddy cutoff encodes the gfm-decade.md finding: monsoon windows whose
``window_start`` month-day is before ``07-25`` are dominated by rice-transplant
inundation (~20x inflation over the flood floor), so the forecaster's event
labels are only trusted on windows starting on/after the cutoff.
"""

from __future__ import annotations

import re

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.metrics import (
    average_precision_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

PADDY_CUTOFF_MD = "07-25"  # windows starting before this carry the transplant signature


def _slug(name: str) -> str:
    """`Ranjit Sagar` -> `ranjit_sagar`, `Bhakra` -> `bhakra`."""
    return re.sub(r"[^a-z0-9]+", "_", str(name).strip().lower()).strip("_")


def pivot_reservoirs(res: pd.DataFrame) -> pd.DataFrame:
    """Long per-dam reservoir windows -> wide, one row per (year, window_start).

    Input columns: year, window_start, dam, mean_storage, delta_storage.
    Output columns: year, window_start, then for each dam ``<slug>_storage``
    (mean_storage) and ``<slug>_delta`` (delta_storage). A (year, window)
    absent for one dam yields NaN for that dam's columns (XGBoost-native).
    """
    piv = res.pivot_table(
        index=["year", "window_start"],
        columns="dam",
        values=["mean_storage", "delta_storage"],
        aggfunc="mean",
    )
    piv.columns = [
        f"{_slug(dam)}_{'storage' if val == 'mean_storage' else 'delta'}"
        for (val, dam) in piv.columns
    ]
    return (
        piv.reset_index().sort_values(["year", "window_start"]).reset_index(drop=True)
    )


def core_season_mask(df: pd.DataFrame, cutoff_md: str = PADDY_CUTOFF_MD) -> pd.Series:
    """Boolean Series: True where window_start month-day >= cutoff (post transplant)."""
    md = df["window_start"].astype(str).str.slice(5)
    return md >= cutoff_md


def add_district_prior(
    df: pd.DataFrame,
    prior: pd.DataFrame,
    value_cols,
    prefix: str = "prior_",
    key: str = "district",
) -> pd.DataFrame:
    """Left-merge selected per-district columns from a frequency/prior table,
    renamed with ``prefix`` so they are unambiguous features."""
    value_cols = list(value_cols)
    ren = {c: f"{prefix}{c}" for c in value_cols}
    p = prior[[key] + value_cols].rename(columns=ren)
    return df.merge(p, on=key, how="left")


def classification_metrics(y_true, prob, threshold: float = 0.5) -> dict:
    """PR-AUC (average precision), ROC-AUC, F1/precision/recall at ``threshold``,
    base rate and n. Single-class inputs -> AUCs/F1 are NaN (undefined), base
    rate and n still reported. Mirrors the single-class guard in sailaab.model."""
    y_true = np.asarray(y_true, dtype=float)
    prob = np.asarray(prob, dtype=float)
    n = int(len(y_true))
    base = float(np.mean(y_true)) if n else float("nan")
    out = {
        "n": n,
        "n_pos": int(np.nansum(y_true)),
        "base_rate": base,
        "pr_auc": float("nan"),
        "roc_auc": float("nan"),
        "f1": float("nan"),
        "precision": float("nan"),
        "recall": float("nan"),
    }
    if (
        n
        and len(np.unique(y_true[~np.isnan(y_true)])) == 2
        and not np.isnan(prob).all()
    ):
        out["pr_auc"] = float(average_precision_score(y_true, prob))
        out["roc_auc"] = float(roc_auc_score(y_true, prob))
        pred = (prob >= threshold).astype(int)
        out["f1"] = float(f1_score(y_true, pred, zero_division=0))
        out["precision"] = float(precision_score(y_true, pred, zero_division=0))
        out["recall"] = float(recall_score(y_true, pred, zero_division=0))
    return out


def regression_metrics(y_true, y_pred) -> dict:
    """MAE and Spearman rank correlation (+ n). Spearman NaN for < 3 points or
    zero variance."""
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    n = int(len(y_true))
    mae = float(np.mean(np.abs(y_true - y_pred))) if n else float("nan")
    rho = float("nan")
    if n >= 3 and np.std(y_true) > 0 and np.std(y_pred) > 0:
        rho = float(spearmanr(y_true, y_pred).statistic)
    return {"n": n, "mae": mae, "spearman": rho}
