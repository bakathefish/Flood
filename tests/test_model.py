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
    df = pd.DataFrame(
        {"year": years, "x1": x1, "noise": rng.normal(0, 1, n), "flood_event": y}
    )
    res = fit_eval(df, features=["x1", "noise"], target="flood_event")
    assert all(r["auc"] > 0.95 for r in res["per_year"])
    assert res["model"] is not None
