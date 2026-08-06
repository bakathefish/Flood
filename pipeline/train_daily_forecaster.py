# pipeline/train_daily_forecaster.py
"""Fit the deployable daily forecaster and write the live bundle.

The evaluation scripts hold seasons out to measure skill. This one does the
other job: it fits on every season available and saves everything the live
monitor needs to score a new day, so that inference never has to recompute a
training quantity and never has to touch the raw archive.

The bundle carries the fitted pipeline, the feature order it was fitted in, the
district susceptibility priors, the seasonal onset climatology, the district
adjacency, and the operating constants. The nowcast driver asserts the feature
order against `sailaab.forecast_live.FEATURE_ORDER`, so a retrain that changes
the feature set fails loudly instead of silently scoring the wrong columns.

Run: python -m pipeline.train_daily_forecaster

Output (committed):
    data/models/forecaster_daily.joblib
    data/models/forecaster_daily.json   (human-readable provenance)
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from pipeline.run_forecaster_daily import (
    CORE_MD,
    HORIZON,
    THRESHOLD,
    _candidates,
    _fold_prior,
    _logreg,
    build_frame,
)
from pipeline.run_forecaster_daily_audit2 import (
    add_neighbour_water,
    build_adjacency,
    seasonal_climatology,
)
from pipeline.run_forecaster_benchmark import MAX_HOPS, TAU_DAYS, _boosting
from sailaab.hazard import excitation_features
from sailaab.forecast_live import FEATURE_ORDER
from sailaab.forecast_daily import forward_event

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
MODELS = DATA / "models"
BUNDLE = MODELS / "forecaster_daily.joblib"
META = MODELS / "forecaster_daily.json"

# The architecture the walk-forward benchmark selected: regularised gradient
# boosting over susceptibility, observed state, season, neighbouring water and
# the self-exciting terms. Pinned so a retrain reproduces the evaluated system
# rather than re-selecting one.
# Nominal quantile of the OUT-OF-FOLD score distribution. Deriving it from the
# model's own training predictions instead would be resubstitution: the model
# has already fitted those rows, its scores there are inflated, and the
# resulting threshold is far too high. Back-testing at this setting realised
# roughly twenty-eight alerts a season, of which about a third were followed by
# flooding within three days.
ALERT_RATE = 0.001


def main() -> None:
    import joblib

    df = build_frame(with_rain=False)
    adjacency = build_adjacency()
    df = add_neighbour_water(df, adjacency)
    ex = excitation_features(
        df[["date", "district", "fraction"]], adjacency,
        threshold=THRESHOLD, tau=TAU_DAYS, max_hops=MAX_HOPS,
    )
    df = df.merge(ex, on=["date", "district"], how="left", validate="1:1")

    d = df.copy()
    d["y"] = forward_event(d, threshold=THRESHOLD, horizon=HORIZON)
    d = _candidates(d, THRESHOLD, hysteresis=False).dropna(subset=["y"])
    d["neighbour"] = d["neighbour_wet3d"].fillna(0.0)
    d["week"] = (d["day_of_season"] // 7).astype(int)

    years = sorted(d["year"].unique())
    base = d.copy()  # feature-free frame the fold-local rebuilds start from
    priors = _fold_prior(d, years, THRESHOLD)
    d = d.merge(priors, on="district", how="left", validate="m:1")

    climo = seasonal_climatology(d)
    d = d.merge(climo, on=["district", "week"], how="left")
    fallback = float(d["y"].mean())
    d["season_climo"] = d["season_climo"].fillna(fallback)

    X = d[list(FEATURE_ORDER)].to_numpy(dtype=float)
    y = d["y"].to_numpy(dtype=float)
    model = _boosting().fit(X, y)
    # The alert threshold is a quantile of the fitted scores, so the deployed
    # system alerts at the rate the benchmark measured rather than at whatever
    # an arbitrary probability cut happens to produce.
    oof = []
    for iy in years[1:]:
        past = [y for y in years if y < iy]
        # Rebuild the target-derived features inside each fold, exactly as the
        # benchmark does, so the deployed threshold is measured under the same
        # discipline it is quoted under.
        f_prior = _fold_prior(base[base["year"].isin(past)], past, THRESHOLD)
        f_all = base.merge(f_prior, on="district", how="left", validate="m:1")
        i_tr, i_te = f_all[f_all["year"].isin(past)], f_all[f_all["year"] == iy]
        if i_te.empty or i_tr["y"].nunique() < 2:
            continue
        f_climo = seasonal_climatology(i_tr)
        f_fill = float(i_tr["y"].mean())
        i_tr = i_tr.merge(f_climo, on=["district", "week"], how="left")
        i_te = i_te.merge(f_climo, on=["district", "week"], how="left")
        i_tr["season_climo"] = i_tr["season_climo"].fillna(f_fill)
        i_te["season_climo"] = i_te["season_climo"].fillna(f_fill)
        oof.append(
            _boosting()
            .fit(i_tr[list(FEATURE_ORDER)].to_numpy(float), i_tr["y"].to_numpy(float))
            .predict_proba(i_te[list(FEATURE_ORDER)].to_numpy(float))[:, 1]
        )
    oof_scores = np.concatenate(oof) if oof else model.predict_proba(X)[:, 1]
    alert_threshold = float(np.quantile(oof_scores, 1.0 - ALERT_RATE))

    bundle = {
        "model": model,
        "feature_order": list(FEATURE_ORDER),
        "priors": {
            r["district"]: {
                "prior_wet_days": float(r["prior_wet_days"]),
                "prior_max_fraction": float(r["prior_max_fraction"]),
            }
            for _, r in priors.iterrows()
        },
        "climatology": {
            (str(r["district"]), int(r["week"])): float(r["season_climo"])
            for _, r in climo.iterrows()
        },
        "climatology_fallback": fallback,
        "adjacency": adjacency,
        "threshold": THRESHOLD,
        "horizon_days": HORIZON,
        "core_season_md": CORE_MD,
        "alert_rate": ALERT_RATE,
        "alert_threshold": alert_threshold,
        "excite_tau_days": TAU_DAYS,
        "excite_max_hops": MAX_HOPS,
        "trained_years": [int(v) for v in years],
        "n_rows": int(len(d)),
        "n_positive": int(y.sum()),
    }
    MODELS.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, BUNDLE)

    meta = {k: v for k, v in bundle.items()
            if k not in ("model", "climatology", "priors", "adjacency")}
    meta["n_districts"] = len(bundle["priors"])
    meta["n_climatology_cells"] = len(bundle["climatology"])
    meta["feature_order"] = list(FEATURE_ORDER)
    META.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    print(f"trained on {len(years)} seasons {years[0]}-{years[-1]}")
    print(f"  rows {len(d)}, positives {int(y.sum())}, base rate {y.mean():.4f}")
    print(f"  districts {len(bundle['priors'])}, "
          f"climatology cells {len(bundle['climatology'])}, "
          f"adjacency pairs {sum(len(v) for v in adjacency.values()) // 2}")
    imp = dict(zip(FEATURE_ORDER, model.feature_importances_))
    print(f"  alert threshold {alert_threshold:.4f} from {len(oof_scores)} "
          f"out-of-fold scores at a nominal {ALERT_RATE:.2%}")
    print("  feature importance:")
    for k, v in sorted(imp.items(), key=lambda kv: -kv[1]):
        print(f"    {k:22s} {v:.3f}")
    print(f"wrote {BUNDLE}")
    print(f"wrote {META}")


if __name__ == "__main__":
    main()
