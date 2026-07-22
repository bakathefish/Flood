# tests/test_ablation.py
"""Unit tests for the reservoir-feature ablation pure helpers.

Covers the three helpers owned by ``sailaab.ablation`` — exact variant feature
lists (16 / 10 / 9), the persistence antecedent-fraction passthrough, and the
per-variant row assembly (schema, 2025 flag metrics, deltas vs full). Flag
metrics are checked against the SAME constants the driver uses, imported from
``pipeline.run_forecaster`` (never re-declared here).
"""

import pandas as pd
import pytest

from pipeline.run_forecaster import FLAG_TOPN, NAMED_2025
from sailaab.ablation import ablation_row, persistence_scores, variant_features

# The shipped 16-feature list order (pipeline.run_forecaster.build_dataset).
FULL_16 = [
    "punjab_mm",
    "upstream_mm",
    "punjab_mm_lag1",
    "upstream_mm_lag1",
    "punjab_mm_lag2",
    "upstream_mm_lag2",
    "bhakra_delta",
    "bhakra_storage",
    "pong_delta",
    "pong_storage",
    "ranjit_sagar_delta",
    "ranjit_sagar_storage",
    "antecedent_fraction",
    "week_of_season",
    "prior_mean_annual_flooded_ha",
    "prior_seasons_with_fraction_gt2pct",
]
RESERVOIR_6 = {
    "bhakra_delta",
    "bhakra_storage",
    "pong_delta",
    "pong_storage",
    "ranjit_sagar_delta",
    "ranjit_sagar_storage",
}


# --- variant_features -------------------------------------------------------


def test_variant_full_is_all_16_unchanged():
    out = variant_features(FULL_16, "full")
    assert out == FULL_16
    assert len(out) == 16


def test_variant_no_reservoir_drops_exactly_the_six_reservoir_features():
    out = variant_features(FULL_16, "no_reservoir")
    assert len(out) == 10
    # exactly the six reservoir features are removed, nothing else
    assert set(FULL_16) - set(out) == RESERVOIR_6
    assert set(out).isdisjoint(RESERVOIR_6)
    # order of surviving features is preserved
    assert out == [f for f in FULL_16 if f not in RESERVOIR_6]


def test_variant_meteo_prior_drops_reservoir_and_antecedent_fraction():
    out = variant_features(FULL_16, "meteo_prior")
    assert len(out) == 9
    assert set(FULL_16) - set(out) == RESERVOIR_6 | {"antecedent_fraction"}
    assert "antecedent_fraction" not in out
    # rain + week + prior only, in original order
    assert out == [
        f for f in FULL_16 if f not in (RESERVOIR_6 | {"antecedent_fraction"})
    ]


def test_variant_features_does_not_mutate_input():
    original = list(FULL_16)
    variant_features(FULL_16, "no_reservoir")
    assert FULL_16 == original


def test_variant_unknown_raises_value_error():
    with pytest.raises(ValueError):
        variant_features(FULL_16, "bogus")


# --- persistence_scores -----------------------------------------------------


def test_persistence_scores_is_pure_passthrough_of_antecedent_fraction():
    core = pd.DataFrame(
        {
            "antecedent_fraction": [0.0, 0.03, 0.5, 0.012],
            "flood_event": [0, 1, 1, 0],
            "district": ["A", "B", "C", "D"],
        }
    )
    s = persistence_scores(core)
    assert list(s) == [0.0, 0.03, 0.5, 0.012]
    # index preserved for alignment, input unmutated
    assert list(s.index) == list(core.index)
    assert list(core.columns) == ["antecedent_fraction", "flood_event", "district"]


# --- ablation_row -----------------------------------------------------------


def _named_flags(ranks, probs, flagged):
    return {
        d: {"best_rank": ranks[d], "best_prob": probs[d], "flagged": flagged[d]}
        for d in NAMED_2025
    }


def test_ablation_row_schema_and_flag_metrics_full_baseline():
    flags = {
        "Firozpur": {"best_rank": 2, "best_prob": 0.502, "flagged": True},
        "Gurdaspur": {"best_rank": 4, "best_prob": 0.131, "flagged": True},
        "Kapurthala": {"best_rank": 1, "best_prob": 0.721, "flagged": True},
        "Tarn Taran": {"best_rank": 2, "best_prob": 0.434, "flagged": True},
        "Amritsar": {"best_rank": 5, "best_prob": 0.019, "flagged": True},
    }
    early = {
        "Kapurthala": {"rank": 1, "prob": 0.7},
        "Firozpur": {"rank": 2, "prob": 0.5},
        "Tarn Taran": {"rank": 3, "prob": 0.4},
        "Gurdaspur": {"rank": 5, "prob": 0.1},
        "Amritsar": {"rank": 9, "prob": 0.0},
    }
    row = ablation_row("full", 16, 0.26871129, 0.94588871, flags, early)
    assert row["variant"] == "full"
    assert row["n_features"] == 16
    assert row["pooled_pr_auc"] == 0.268711
    assert row["pooled_roc_auc"] == 0.945889
    assert row["hindcast_n_flagged"] == 5
    assert row["kapurthala_best_rank"] == 1
    # ranks <= FLAG_TOPN (5): K1, F2, T3, G5 -> 4 ; Amritsar #9 excluded
    assert row["early_0814_top5_count"] == 4
    # a full baseline has zero deltas
    assert row["d_pr_auc"] == 0.0
    assert row["d_roc_auc"] == 0.0
    assert row["d_n_flagged"] == 0
    assert row["d_kapurthala_rank"] == 0
    assert row["d_early_top5"] == 0


def test_ablation_row_early_count_uses_imported_flag_topn():
    flags = _named_flags(
        ranks={d: 1 for d in NAMED_2025},
        probs={d: 0.9 for d in NAMED_2025},
        flagged={d: True for d in NAMED_2025},
    )
    early = {
        NAMED_2025[0]: {"rank": FLAG_TOPN, "prob": 0.1},  # exactly at cut -> counts
        NAMED_2025[1]: {"rank": FLAG_TOPN + 1, "prob": 0.1},  # just beyond -> excluded
        NAMED_2025[2]: {"rank": 1, "prob": 0.9},  # counts
        NAMED_2025[3]: None,  # missing window -> excluded
        NAMED_2025[4]: {"rank": 3, "prob": 0.5},  # counts
    }
    row = ablation_row("no_reservoir", 10, 0.2, 0.9, flags, early)
    assert row["early_0814_top5_count"] == 3


def test_ablation_row_deltas_vs_full():
    flags_full = _named_flags(
        ranks={d: 3 for d in NAMED_2025},
        probs={d: 0.1 for d in NAMED_2025},
        flagged={d: True for d in NAMED_2025},
    )
    early_full = {d: {"rank": 2, "prob": 0.1} for d in NAMED_2025}
    full = ablation_row("full", 16, 0.269, 0.946, flags_full, early_full)

    # variant loses one flag (Amritsar) and Kapurthala drops from rank 3 to 6
    flags_v = _named_flags(
        ranks={**{d: 3 for d in NAMED_2025}, "Kapurthala": 6},
        probs={d: 0.1 for d in NAMED_2025},
        flagged={**{d: True for d in NAMED_2025}, "Amritsar": False},
    )
    early_v = {d: {"rank": 2, "prob": 0.1} for d in NAMED_2025}
    v = ablation_row("no_reservoir", 10, 0.249, 0.900, flags_v, early_v, full_row=full)

    assert v["d_pr_auc"] == round(0.249 - 0.269, 6)
    assert v["d_roc_auc"] == round(0.900 - 0.946, 6)
    assert v["d_n_flagged"] == -1
    assert v["d_kapurthala_rank"] == 3  # 6 - 3
    assert v["d_early_top5"] == 0


def test_ablation_row_counts_only_flagged_true():
    flags = _named_flags(
        ranks={d: 7 for d in NAMED_2025},
        probs={d: 0.1 for d in NAMED_2025},
        flagged={
            "Firozpur": True,
            "Gurdaspur": False,
            "Kapurthala": True,
            "Tarn Taran": False,
            "Amritsar": False,
        },
    )
    early = {d: None for d in NAMED_2025}
    row = ablation_row("persistence", 1, 0.05, 0.60, flags, early)
    assert row["hindcast_n_flagged"] == 2
    assert row["early_0814_top5_count"] == 0
