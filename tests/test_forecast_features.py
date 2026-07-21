# tests/test_forecast_features.py
import numpy as np
import pandas as pd

from sailaab.forecast_features import (
    PADDY_CUTOFF_MD,
    add_district_prior,
    classification_metrics,
    core_season_mask,
    pivot_reservoirs,
    regression_metrics,
)


def _res_long():
    return pd.DataFrame(
        {
            "year": [2020, 2020, 2020, 2020, 2020, 2020],
            "window_start": [
                "2020-07-25",
                "2020-08-04",
                "2020-07-25",
                "2020-08-04",
                "2020-07-25",
                "2020-08-04",
            ],
            "dam": [
                "Bhakra",
                "Bhakra",
                "Pong",
                "Pong",
                "Ranjit Sagar",
                "Ranjit Sagar",
            ],
            "mean_storage": [3.0, 4.0, 5.0, 5.2, 1.0, 1.5],
            "delta_storage": [0.5, 1.0, 0.2, 0.1, 0.05, 0.5],
        }
    )


def test_pivot_reservoirs_one_row_per_window_with_per_dam_cols():
    w = pivot_reservoirs(_res_long())
    assert len(w) == 2  # two windows
    assert {
        "bhakra_storage",
        "bhakra_delta",
        "pong_storage",
        "pong_delta",
        "ranjit_sagar_storage",
        "ranjit_sagar_delta",
    } <= set(w.columns)
    row = w[w.window_start == "2020-08-04"].iloc[0]
    assert row["bhakra_storage"] == 4.0
    assert row["ranjit_sagar_delta"] == 0.5
    assert row["pong_storage"] == 5.2


def test_pivot_reservoirs_missing_cell_is_nan():
    res = _res_long()
    # drop Ranjit Sagar's 2020-08-04 row -> that cell must be NaN, not dropped
    res = res.drop(
        index=res[
            (res.dam == "Ranjit Sagar") & (res.window_start == "2020-08-04")
        ].index
    )
    w = pivot_reservoirs(res)
    assert len(w) == 2
    row = w[w.window_start == "2020-08-04"].iloc[0]
    assert np.isnan(row["ranjit_sagar_storage"])
    assert row["bhakra_storage"] == 4.0  # other dams unaffected


def test_core_season_mask_excludes_paddy_windows():
    df = pd.DataFrame(
        {
            "window_start": [
                "2020-06-15",
                "2020-07-05",
                "2020-07-15",
                "2020-07-25",
                "2020-08-24",
                "2020-09-23",
            ]
        }
    )
    m = core_season_mask(df)
    assert m.tolist() == [False, False, False, True, True, True]
    assert PADDY_CUTOFF_MD == "07-25"


def test_add_district_prior_merges_by_district_with_prefix():
    df = pd.DataFrame({"district": ["A", "A", "B"], "x": [1, 2, 3]})
    prior = pd.DataFrame(
        {"district": ["A", "B"], "mean_annual_flooded_ha": [100.0, 200.0]}
    )
    out = add_district_prior(df, prior, ["mean_annual_flooded_ha"])
    assert "prior_mean_annual_flooded_ha" in out.columns
    assert len(out) == 3  # no row multiplication
    assert out.loc[out.district == "B", "prior_mean_annual_flooded_ha"].iloc[0] == 200.0


def test_classification_metrics_perfect_separation():
    y = np.array([0, 0, 1, 1])
    p = np.array([0.1, 0.2, 0.8, 0.9])
    m = classification_metrics(y, p, threshold=0.5)
    assert m["base_rate"] == 0.5
    assert m["roc_auc"] == 1.0
    assert m["pr_auc"] > 0.99
    assert m["f1"] == 1.0
    assert m["n_pos"] == 2


def test_classification_metrics_single_class_is_nan():
    y = np.array([0, 0, 0])
    p = np.array([0.1, 0.2, 0.3])
    m = classification_metrics(y, p)
    assert np.isnan(m["pr_auc"]) and np.isnan(m["roc_auc"])
    assert m["base_rate"] == 0.0
    assert m["n"] == 3


def test_regression_metrics_monotonic_high_spearman():
    y = np.array([0.0, 0.1, 0.2, 0.3])
    yp = np.array([0.05, 0.12, 0.18, 0.40])
    m = regression_metrics(y, yp)
    assert m["mae"] >= 0
    assert m["spearman"] > 0.9
    assert m["n"] == 4
