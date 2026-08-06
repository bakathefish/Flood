# pipeline/run_forecaster_walkforward.py
"""Walk-forward operational simulation: train only on the past.

Leave-one-year-out lets a fold trained on 2016-2025 predict 2015, which no
operator could ever have done. This runs the system the way it would actually
have been run: for each season from 2019 onward, fit on every season strictly
before it and forecast that season cold. A model is never shown its own future.

This is the strongest internal check available, and it is not an independent
confirmation. The feature class was chosen after seeing aggregate results on
these same seasons, so an optimistic bias remains at that level. The genuinely
confirmatory test is the 2026 monsoon, which is in progress and which no part of
this model has seen.

Run: python -m pipeline.run_forecaster_walkforward
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score

from pipeline.run_forecaster_daily import (
    HORIZON,
    THRESHOLD,
    _candidates,
    _fit_predict,
    _fold_prior,
    build_frame,
)
from pipeline.run_forecaster_daily_audit import _event_recall, _recall_at_k, onset_events
from pipeline.run_forecaster_daily_audit2 import (
    add_neighbour_water,
    build_adjacency,
    seasonal_climatology,
)
from sailaab.forecast_daily import forward_event

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = DATA / "forecaster_walkforward.csv"

AUG = [
    "prior_wet_days", "prior_max_fraction", "frac_now", "frac_max3d",
    "day_of_season", "neighbour", "season_climo",
]
FIRST_TEST_YEAR = 2019  # needs at least four prior seasons to fit on


def main() -> None:
    df = build_frame()
    df = add_neighbour_water(df, build_adjacency())
    d = df.copy()
    d["y"] = forward_event(d, threshold=THRESHOLD, horizon=HORIZON)
    d = _candidates(d, THRESHOLD, hysteresis=False).dropna(subset=["y"])
    d["neighbour"] = d["neighbour_wet3d"].fillna(0.0)
    d["week"] = (d["day_of_season"] // 7).astype(int)

    years = sorted(d["year"].unique())
    parts = []
    for ty in [y for y in years if y >= FIRST_TEST_YEAR]:
        past = [y for y in years if y < ty]
        tr_raw = d[d["year"].isin(past)]
        te_raw = d[d["year"] == ty]
        if te_raw.empty or tr_raw["y"].nunique() < 2:
            continue
        prior = _fold_prior(d[d["year"].isin(past)], past, THRESHOLD)
        tr = tr_raw.merge(prior, on="district", how="left", validate="m:1")
        te = te_raw.merge(prior, on="district", how="left", validate="m:1").copy()

        climo = seasonal_climatology(tr)
        tr = tr.merge(climo, on=["district", "week"], how="left")
        te = te.merge(climo, on=["district", "week"], how="left")
        fill = float(tr["y"].mean())
        tr["season_climo"] = tr["season_climo"].fillna(fill)
        te["season_climo"] = te["season_climo"].fillna(fill)

        te["model"] = _fit_predict(AUG, tr, te, nested_years=tr["year"].to_numpy())
        te["climo_plus_neighbour"] = (
            te["season_climo"].rank(pct=True)
            + te["neighbour"].rank(pct=True)
            + te["frac_now"].fillna(0.0).rank(pct=True)
        )
        te["persistence"] = te["frac_now"].fillna(0.0)
        te["n_train_years"] = len(past)
        parts.append(te)
        print(f"{ty}: trained on {len(past)} prior seasons ({past[0]}-{past[-1]}), "
              f"{int(te['y'].sum())} positive district-days")

    s = pd.concat(parts, ignore_index=True)
    events = onset_events(df, THRESHOLD)
    events = events[events["year"] >= FIRST_TEST_YEAR]

    print("\n" + "=" * 74)
    print("WALK-FORWARD: each season forecast using only earlier seasons")
    print("=" * 74)
    base = s["y"].mean()
    print(f"seasons {FIRST_TEST_YEAR}-{years[-1]}, n={len(s)}, "
          f"positive district-days={int(s['y'].sum())}, base rate {base:.4f}")
    print(f"distinct onset events in this period: {len(events)}\n")
    print(f"{'scorer':22s} {'AP':>7} {'lift':>6} {'row R@5':>8} {'EVENT R@3':>10} {'EVENT R@5':>10}")
    rows = []
    for c in ("model", "climo_plus_neighbour", "persistence"):
        ap = average_precision_score(s["y"], s[c])
        r5 = _recall_at_k(s, c, 5)
        e3, n_ev = _event_recall(s, events, c, 3, HORIZON)
        e5, _ = _event_recall(s, events, c, 5, HORIZON)
        print(f"{c:22s} {ap:7.3f} {ap / base:6.1f} {r5:8.3f} {e3:10.3f} {e5:10.3f}")
        rows.append({"scorer": c, "ap": ap, "lift": ap / base, "row_r5": r5,
                     "event_r3": e3, "event_r5": e5, "n_events": n_ev})

    print("\nper-season average precision:")
    for yr in sorted(s["year"].unique()):
        sub = s[s["year"] == yr]
        if sub["y"].nunique() < 2:
            print(f"  {yr}: no positives")
            continue
        m = average_precision_score(sub["y"], sub["model"])
        p = average_precision_score(sub["y"], sub["persistence"])
        cn = average_precision_score(sub["y"], sub["climo_plus_neighbour"])
        print(f"  {yr}: model {m:.3f}  climo+nbr {cn:.3f}  persistence {p:.3f}"
              f"   ({int(sub['y'].sum())} positives)")
        rows.append({"scorer": "per_year", "year": int(yr), "ap": m,
                     "ap_climo_nbr": cn, "ap_persistence": p})

    pd.DataFrame(rows).to_csv(OUT, index=False)
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
