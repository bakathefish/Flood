# sailaab/model.py
"""LOYO cross-validation and XGBoost wrapper."""

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
from xgboost import XGBClassifier


def loyo_splits(years: list[int]) -> list[tuple[list[int], int]]:
    ys = sorted(set(years))
    return [([y for y in ys if y != t], t) for t in ys]


def _make_model() -> XGBClassifier:
    return XGBClassifier(
        n_estimators=300,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.9,
        eval_metric="logloss",
    )


def fit_eval(df: pd.DataFrame, features: list[str], target: str) -> dict:
    per_year = []
    for train_years, test_year in loyo_splits(df["year"].unique().tolist()):
        tr = df[df["year"].isin(train_years)]
        te = df[df["year"] == test_year]
        if te[target].nunique() < 2:  # AUC undefined; record and skip
            per_year.append(
                {
                    "year": test_year,
                    "auc": float("nan"),
                    "n": len(te),
                    "note": "single-class year",
                }
            )
            continue
        m = _make_model().fit(tr[features], tr[target])
        p = m.predict_proba(te[features])[:, 1]
        per_year.append(
            {
                "year": test_year,
                "auc": float(roc_auc_score(te[target], p)),
                "n": len(te),
            }
        )
    final = _make_model().fit(df[features], df[target])
    return {"per_year": per_year, "model": final}
