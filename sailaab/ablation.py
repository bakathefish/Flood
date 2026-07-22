# sailaab/ablation.py
"""Pure helpers for the reservoir-feature ablation of the flood forecaster.

No IO, no model fitting — deterministic list/pandas transforms plus per-variant
metric assembly. The pre-declared protocol lives in ``docs/notes/ablation.md``
(committed before any variant ran); the driver ``pipeline/run_ablation.py``
composes these helpers with the shipped forecaster harness.

Three helpers:
  * ``variant_features`` — the EXACT pre-declared feature drop-lists.
  * ``persistence_scores`` — antecedent_fraction as the (fit-free) risk score.
  * ``ablation_row`` — assemble one CSV row: identity, pooled metrics, the 2025
    flag metrics, and deltas vs the ``full`` baseline.

The 2025 flag-metric constants (``FLAG_TOPN``) are imported from
``pipeline.run_forecaster`` so this module and the shipped forecaster can never
drift apart.
"""

from __future__ import annotations

import pandas as pd

from pipeline.run_forecaster import FLAG_TOPN

# The six reservoir features: {bhakra,pong,ranjit_sagar} x {storage,delta}.
# Pivoted from data/reservoir_windows.csv by forecast_features.pivot_reservoirs.
RESERVOIR_FEATURES = (
    "bhakra_storage",
    "bhakra_delta",
    "pong_storage",
    "pong_delta",
    "ranjit_sagar_storage",
    "ranjit_sagar_delta",
)

# variant -> features to DROP from the base 16-feature list.
_VARIANT_DROP = {
    "full": frozenset(),
    "no_reservoir": frozenset(RESERVOIR_FEATURES),
    "meteo_prior": frozenset(RESERVOIR_FEATURES) | frozenset({"antecedent_fraction"}),
}


def variant_features(features: list[str], variant: str) -> list[str]:
    """Return the pre-declared feature list for ``variant``, preserving the
    order of the surviving features from the base list.

    * ``full``        -> all 16 features unchanged.
    * ``no_reservoir`` -> minus the 6 ``{bhakra,pong,ranjit_sagar}_{storage,delta}`` (10).
    * ``meteo_prior``  -> minus reservoir AND ``antecedent_fraction`` (9).

    ``persistence`` is not a feature-list variant (it skips the fit and scores
    via :func:`persistence_scores`); passing it — or any other name — raises.
    """
    if variant not in _VARIANT_DROP:
        raise ValueError(
            f"unknown variant {variant!r}; expected one of "
            f"{sorted(_VARIANT_DROP)} (persistence has no feature list)"
        )
    drop = _VARIANT_DROP[variant]
    return [f for f in features if f not in drop]


def persistence_scores(core: pd.DataFrame) -> pd.Series:
    """Persistence baseline risk score: a pure passthrough of the observed
    ``antecedent_fraction`` (last window's flooded extent). No fit — every row's
    score is its own antecedent, available at prediction time. Returns a float
    Series aligned to ``core`` (input is not mutated)."""
    return core["antecedent_fraction"].astype(float)


def ablation_row(
    variant: str,
    n_features: int,
    pooled_pr_auc: float,
    pooled_roc_auc: float,
    flags: dict,
    early: dict,
    full_row: dict | None = None,
) -> dict:
    """Assemble one ablation CSV row for ``variant``.

    ``flags`` / ``early`` follow the shape produced by
    ``run_forecaster.hindcast_2025`` (and the persistence equivalent):
      * ``flags[district] = {"best_rank", "best_prob", "flagged"}``
      * ``early[district] = {"rank", "prob"}`` or ``None``

    Metrics: pooled PR-AUC / ROC-AUC, ``hindcast_n_flagged`` (of the 5 named
    districts), ``kapurthala_best_rank``, and ``early_0814_top5_count`` (named
    districts whose 08-14 rank is within FLAG_TOPN — the ~10-day-lead readout).
    Deltas vs ``full`` are 0 when ``full_row`` is None (this row IS the baseline).
    """
    n_flagged = int(sum(bool(v["flagged"]) for v in flags.values()))
    kapurthala_best_rank = int(flags["Kapurthala"]["best_rank"])
    early_top5 = int(
        sum(1 for e in early.values() if e is not None and e["rank"] <= FLAG_TOPN)
    )
    row = {
        "variant": variant,
        "n_features": int(n_features),
        "pooled_pr_auc": round(float(pooled_pr_auc), 6),
        "pooled_roc_auc": round(float(pooled_roc_auc), 6),
        "hindcast_n_flagged": n_flagged,
        "kapurthala_best_rank": kapurthala_best_rank,
        "early_0814_top5_count": early_top5,
    }
    if full_row is None:
        row.update(
            {
                "d_pr_auc": 0.0,
                "d_roc_auc": 0.0,
                "d_n_flagged": 0,
                "d_kapurthala_rank": 0,
                "d_early_top5": 0,
            }
        )
    else:
        row.update(
            {
                "d_pr_auc": round(row["pooled_pr_auc"] - full_row["pooled_pr_auc"], 6),
                "d_roc_auc": round(
                    row["pooled_roc_auc"] - full_row["pooled_roc_auc"], 6
                ),
                "d_n_flagged": row["hindcast_n_flagged"] - full_row["hindcast_n_flagged"],
                "d_kapurthala_rank": (
                    row["kapurthala_best_rank"] - full_row["kapurthala_best_rank"]
                ),
                "d_early_top5": (
                    row["early_0814_top5_count"] - full_row["early_0814_top5_count"]
                ),
            }
        )
    return row
