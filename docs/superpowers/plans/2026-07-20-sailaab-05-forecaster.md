# Sailaab 05 — Forecaster (Wave 4) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Tasks 1–3 are pure-Python (executable now); Task 4 needs Wave-2/3 data.

**Goal:** District flood-risk model (XGBoost) trained on Wave-2 SAR-derived labels, leave-one-year-out validated, with the 2025 hindcast and SHAP attribution figure.

**Architecture:** `sailaab/dataset.py` (joins/lags/targets — pure, tested on synthetic frames) + `sailaab/model.py` (LOYO splitting + fit/eval — tested on synthetic separable data) + thin `pipeline/run_forecaster.py`. The pre-plan draft `pipeline/forecaster.py` is deleted, replaced by these modules.

**Tech Stack:** pandas, xgboost, scikit-learn, shap, matplotlib.

---

### Task 1: dataset.py — lags, targets, joins (pure, TDD)

**Files:**
- Create: `sailaab/dataset.py`
- Test: `tests/test_dataset.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_dataset.py
import pandas as pd
import pytest

from sailaab.dataset import add_lags, label_events, assemble


def _frame():
    return pd.DataFrame({
        "district": ["A", "A", "A", "B", "B", "B"],
        "window_start": ["2024-06-15", "2024-06-25", "2024-07-05"] * 2,
        "year": [2024] * 6,
        "flooded_fraction": [0.0, 0.01, 0.30, 0.0, 0.0, 0.05],
        "rain_mm": [10.0, 80.0, 250.0, 5.0, 40.0, 90.0],
    })


def test_add_lags_shifts_within_district():
    df = add_lags(_frame(), "rain_mm", lags=2)
    a = df[df.district == "A"].sort_values("window_start")
    assert pd.isna(a["rain_mm_lag1"].iloc[0])
    assert a["rain_mm_lag1"].iloc[1] == 10.0
    assert a["rain_mm_lag1"].iloc[2] == 80.0
    assert a["rain_mm_lag2"].iloc[2] == 10.0


def test_lags_do_not_leak_across_districts():
    df = add_lags(_frame(), "rain_mm", lags=1)
    b = df[df.district == "B"].sort_values("window_start")
    assert pd.isna(b["rain_mm_lag1"].iloc[0])  # not A's last value


def test_label_events_uses_config_threshold():
    df = label_events(_frame(), threshold=0.02)
    assert df["flood_event"].tolist() == [0, 0, 1, 0, 0, 1]


def test_assemble_adds_antecedent_and_week_index():
    df = assemble(_frame())
    a = df[df.district == "A"].sort_values("window_start")
    assert a["antecedent_fraction"].iloc[2] == 0.01  # previous window's fraction
    assert a["week_of_season"].tolist() == [0, 1, 2]
```

- [ ] **Step 2: Run to FAIL** — ModuleNotFoundError.

- [ ] **Step 3: Minimal implementation**

```python
# sailaab/dataset.py
"""Forecaster dataset assembly — pure pandas, no EE."""
import pandas as pd

from sailaab import config


def add_lags(df: pd.DataFrame, col: str, lags: int) -> pd.DataFrame:
    out = df.sort_values(["district", "window_start"]).copy()
    for k in range(1, lags + 1):
        out[f"{col}_lag{k}"] = out.groupby("district")[col].shift(k)
    return out


def label_events(df: pd.DataFrame,
                 threshold: float = config.FLOOD_EVENT_FRACTION) -> pd.DataFrame:
    out = df.copy()
    out["flood_event"] = (out["flooded_fraction"] > threshold).astype(int)
    return out


def assemble(df: pd.DataFrame) -> pd.DataFrame:
    out = df.sort_values(["district", "window_start"]).copy()
    out["antecedent_fraction"] = out.groupby("district")["flooded_fraction"].shift(1)
    out["week_of_season"] = out.groupby(["district", "year"]).cumcount()
    return out
```

- [ ] **Step 4: Run to PASS** — 4 passed.
- [ ] **Step 5: Commit** — `git add sailaab/dataset.py tests/test_dataset.py && git commit -m "feat: forecaster dataset assembly (lags, events, antecedent)"`

---

### Task 2: model.py — LOYO splits + fit/eval (pure, TDD)

**Files:**
- Create: `sailaab/model.py`
- Test: `tests/test_model.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_model.py
import numpy as np
import pandas as pd

from sailaab.model import loyo_splits, fit_eval


def test_loyo_splits_cover_each_year_once():
    s = loyo_splits([2015, 2016, 2017])
    assert [t for (_, t) in s] == [2015, 2016, 2017]
    for train, test in s:
        assert test not in train and len(train) == 2


def test_fit_eval_learns_separable_synthetic():
    rng = np.random.default_rng(0)
    n = 600
    years = rng.choice([2020, 2021, 2022], n)
    x1 = rng.normal(0, 1, n)
    y = (x1 > 0.5).astype(int)  # perfectly separable on x1
    df = pd.DataFrame({"year": years, "x1": x1, "noise": rng.normal(0, 1, n),
                       "flood_event": y})
    res = fit_eval(df, features=["x1", "noise"], target="flood_event")
    assert all(r["auc"] > 0.95 for r in res["per_year"])
    assert res["model"] is not None
```

- [ ] **Step 2: Run to FAIL**, then implement:

```python
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
    return XGBClassifier(n_estimators=300, max_depth=4, learning_rate=0.05,
                         subsample=0.9, eval_metric="logloss")


def fit_eval(df: pd.DataFrame, features: list[str], target: str) -> dict:
    per_year = []
    for train_years, test_year in loyo_splits(df["year"].unique().tolist()):
        tr = df[df["year"].isin(train_years)]
        te = df[df["year"] == test_year]
        if te[target].nunique() < 2:   # AUC undefined; record and skip
            per_year.append({"year": test_year, "auc": float("nan"),
                             "n": len(te), "note": "single-class year"})
            continue
        m = _make_model().fit(tr[features], tr[target])
        p = m.predict_proba(te[features])[:, 1]
        per_year.append({"year": test_year,
                         "auc": float(roc_auc_score(te[target], p)),
                         "n": len(te)})
    final = _make_model().fit(df[features], df[target])
    return {"per_year": per_year, "model": final}
```

- [ ] **Step 3: Run to PASS** (xgboost import may take a few seconds first run).
- [ ] **Step 4: Delete the pre-plan draft** — `git rm pipeline/forecaster.py`
- [ ] **Step 5: Commit** — `git add sailaab/model.py tests/test_model.py && git commit -m "feat: LOYO CV + XGBoost wrapper; remove draft forecaster"`

---

### Task 3: run_forecaster.py — thin CLI

**Files:**
- Create: `pipeline/run_forecaster.py`

- [ ] **Step 1: Write it** (runnable as soon as Wave-2/3 CSVs exist in data/):

```python
# pipeline/run_forecaster.py
"""Assemble dataset -> LOYO eval -> 2025 hindcast -> SHAP figure.
Inputs (data/): decade_windows.csv (tidied Wave-2 concat), rain_windows.csv
(district,window_start,rain_mm from GEE IMERG export), reservoirs_daily.csv,
soil_moisture.csv (optional, 2018+). Outputs: atlas/forecaster/*"""
from pathlib import Path

import pandas as pd

from sailaab.dataset import add_lags, assemble, label_events
from sailaab.model import fit_eval

DATA = Path("data"); OUT = Path("atlas/forecaster"); OUT.mkdir(parents=True, exist_ok=True)
FEATURES = ["rain_mm", "rain_mm_lag1", "rain_mm_lag2", "reservoir_delta",
            "soil_moisture", "antecedent_fraction", "week_of_season"]


def main():
    df = pd.read_csv(DATA / "decade_windows.csv")            # district,window_start,year,flooded_fraction
    rain = pd.read_csv(DATA / "rain_windows.csv")            # district,window_start,rain_mm
    df = df.merge(rain, on=["district", "window_start"], how="left")
    res = pd.read_csv(DATA / "reservoirs_windows.csv")       # window_start,reservoir_delta (statewide)
    df = df.merge(res, on="window_start", how="left")
    sm = DATA / "soil_moisture_windows.csv"
    if sm.exists():
        df = df.merge(pd.read_csv(sm), on=["district", "window_start"], how="left")
    else:
        df["soil_moisture"] = float("nan")

    df = assemble(label_events(add_lags(df, "rain_mm", 2)))

    # Showcase hindcast: train 2015-2024, predict 2025 — reported verbatim.
    hind = fit_eval(df[df.year <= 2025], FEATURES, "flood_event")
    pd.DataFrame(hind["per_year"]).to_csv(OUT / "loyo_metrics.csv", index=False)

    df2025 = df[df.year == 2025].copy()
    m = fit_eval(df[df.year < 2025], FEATURES, "flood_event")["model"]
    df2025["risk"] = m.predict_proba(df2025[FEATURES])[:, 1]
    df2025.sort_values("risk", ascending=False).to_csv(
        OUT / "hindcast_2025.csv", index=False)

    import shap
    ex = shap.TreeExplainer(m)
    sv = ex.shap_values(df[df.year < 2025][FEATURES])
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    shap.summary_plot(sv, df[df.year < 2025][FEATURES], show=False)
    plt.tight_layout(); plt.savefig(OUT / "shap_summary.png", dpi=200)
    print("wrote", list(OUT.iterdir()))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Commit** — `git add pipeline/run_forecaster.py && git commit -m "feat: forecaster CLI (LOYO, 2025 hindcast, SHAP)"`

---

### Task 4: Data feeds + the hindcast checkpoint (needs Wave 2 done)

- [ ] **Step 1:** Rain per district-window: GEE export using `ee_graphs.punjab_districts()` + IMERG V07 sum per window (small addition to `pipeline/` mirroring `district_flood_stats` — reduceRegions with sum of precipitation) → `data/rain_windows.csv`. NOTE: upstream-basin rain (HydroSHEDS) is the better feature — add as `rain_upstream_mm` if time allows; district rain is the v0.
- [ ] **Step 2:** Reservoir windows: from `data/reservoirs_aug2025.csv`-style daily series for all years (AIKosh/WRIS bulk), compute per-window mean level delta → `data/reservoirs_windows.csv`. If multi-year daily reservoir data proves unavailable, drop the feature and SAY SO in METHOD.md §5 (no silent feature).
- [ ] **Step 3: Pre-declare (red) in VERIFICATION-LOG:**

```markdown
| 2026-07-2X | forecaster LOYO | median per-year AUC ≥ 0.70 (2016–2024) | | |
| 2026-07-2X | 2025 hindcast | reported VERBATIM whatever it shows; success = Gurdaspur/Ferozepur/Kapurthala among top-5 risk in Aug 22–Sep 1 windows | | |
```

- [ ] **Step 4:** Run `python pipeline/run_forecaster.py`, record results verbatim (both outcomes are publishable — the framing for a miss is "hindcast skill under the most extreme event in the record").
- [ ] **Step 5: METHOD.md §5** — features, why GBM over deep nets (2.5k rows, interpretability), LOYO table, hindcast narrative, SHAP figure reference. Commit — `git commit -m "feat: forecaster trained; docs: forecaster method"`
