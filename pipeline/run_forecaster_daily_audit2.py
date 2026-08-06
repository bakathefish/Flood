# pipeline/run_forecaster_daily_audit2.py
"""Round-two audit: the three blockers that stood between this and ratification.

1. EVENT RECALL FROM THE SELECTED SYSTEM. Quoting one variant's recall beside
   another variant's average precision would describe a system nobody ran. Event
   recall is recomputed from the nested, within-fold selected prediction stream,
   which is the thing an honest deployment would have used.

2. DE NOVO AT EVENT LEVEL. The 92% figure was a share of positive district-days,
   not of distinct floods. Recomputed over the 96 distinct onset events.

3. GENUINELY DIFFERENT TRANSPARENT BASELINES. Distance-to-threshold and the
   combined hazard turned out to be monotone transforms of current water, so
   they were rank-equivalent to persistence and proved nothing. Two baselines
   that are not:

   * SEASONAL CLIMATOLOGY. Onset rate per district per week of monsoon,
     estimated on training years only. Answers: is the model doing more than
     knowing which districts flood, and when in the season?
   * SPATIAL PROPAGATION. Water observed recently in districts ADJACENT to the
     target, target excluded. Answers the sharpest alternative explanation of
     all: that the model is simply noticing a flood already visible next door.

Run: python -m pipeline.run_forecaster_daily_audit2
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from shapely.geometry import shape
from sklearn.metrics import average_precision_score

from pipeline.run_forecaster_daily import (
    CORE_MD,
    HORIZON,
    THRESHOLD,
    VARIANTS,
    _candidates,
    _fit_predict,
    _fold_prior,
    build_frame,
)
from pipeline.run_forecaster_daily_audit import _recall_at_k, onset_events
from sailaab.forecast_daily import forward_event

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DISTRICTS = DATA / "punjab_districts.geojson"
OUT = DATA / "forecaster_daily_audit2.csv"


def build_adjacency() -> dict:
    """District -> list of districts whose polygons touch it."""
    gj = json.loads(DISTRICTS.read_text(encoding="utf-8"))
    geoms = {f["properties"]["district"]: shape(f["geometry"]) for f in gj["features"]}
    adj = {}
    for a, ga in geoms.items():
        adj[a] = [
            b for b, gb in geoms.items() if b != a and ga.buffer(1e-9).intersects(gb)
        ]
    return adj


def add_neighbour_water(df: pd.DataFrame, adj: dict) -> pd.DataFrame:
    """Max flooded fraction over the last 3 days in ADJACENT districts.

    Strictly excludes the target district, so any skill it shows is skill from
    the flood being visible somewhere else already.
    """
    d = df.copy()
    d["_f3"] = (
        d.sort_values(["district", "year", "date"])
        .groupby(["district", "year"], sort=False)["fraction"]
        .transform(lambda s: s.rolling(3, min_periods=1).max())
    )
    wide = d.pivot_table(index="date", columns="district", values="_f3")
    out = pd.DataFrame(index=wide.index)
    for dist, nbrs in adj.items():
        cols = [n for n in nbrs if n in wide.columns]
        out[dist] = wide[cols].max(axis=1) if cols else np.nan
    long = out.stack().rename("neighbour_wet3d").reset_index()
    long.columns = ["date", "district", "neighbour_wet3d"]
    return d.drop(columns="_f3").merge(
        long, on=["date", "district"], how="left", validate="1:1"
    )


def seasonal_climatology(tr: pd.DataFrame) -> pd.DataFrame:
    """Onset rate per district per week of monsoon, from training years only."""
    t = tr.copy()
    t["week"] = (t["day_of_season"] // 7).astype(int)
    g = t.groupby(["district", "week"])["y"].mean().rename("season_climo")
    return g.reset_index()


def main() -> None:
    df = build_frame()
    adj = build_adjacency()
    print(f"adjacency: {sum(len(v) for v in adj.values()) // 2} district pairs")
    df = add_neighbour_water(df, adj)

    d = df.copy()
    d["y"] = forward_event(d, threshold=THRESHOLD, horizon=HORIZON)
    d = _candidates(d, THRESHOLD, hysteresis=False).dropna(subset=["y"])

    years = sorted(d["year"].unique())
    parts, picks = [], []
    for ty in years:
        trys = [y for y in years if y != ty]
        fold = d.merge(
            _fold_prior(d, trys, THRESHOLD), on="district", how="left", validate="m:1"
        )
        tr, te = fold[fold["year"].isin(trys)], fold[fold["year"] == ty].copy()
        if te.empty:
            continue

        # choose the whole variant using training years only
        scores = {}
        for name, feats in VARIANTS.items():
            preds, truths = [], []
            for inner in trys:
                itr, ite = tr[tr["year"] != inner], tr[tr["year"] == inner]
                if ite.empty or itr["y"].nunique() < 2:
                    continue
                preds.append(_fit_predict(feats, itr, ite))
                truths.append(ite["y"].to_numpy(float))
            if not preds:
                continue
            yy, pp = np.concatenate(truths), np.concatenate(preds)
            if len(np.unique(yy)) > 1:
                scores[name] = average_precision_score(yy, pp)
        chosen = max(scores, key=scores.get) if scores else "persistence"
        picks.append(chosen)
        te["selected"] = _fit_predict(
            VARIANTS[chosen], tr, te, nested_years=tr["year"].to_numpy()
        )
        te["chosen"] = chosen

        # transparent baselines, fitted on the same training years
        climo = seasonal_climatology(tr)
        te["week"] = (te["day_of_season"] // 7).astype(int)
        te = te.merge(climo, on=["district", "week"], how="left")
        te["season_climo"] = te["season_climo"].fillna(tr["y"].mean())
        # Give the LEARNED model the same information the transparent baseline
        # has: neighbouring-district water and the fold-estimated seasonal
        # climatology. If it cannot beat the simple rule with those in hand,
        # the simple rule is the better system and should be said so.
        tr2 = tr.merge(climo, on=["district", "week"], how="left") if "week" in tr else None
        tr_w = tr.copy()
        tr_w["week"] = (tr_w["day_of_season"] // 7).astype(int)
        tr_w = tr_w.merge(climo, on=["district", "week"], how="left")
        tr_w["season_climo"] = tr_w["season_climo"].fillna(tr["y"].mean())
        tr_w["neighbour"] = tr_w["neighbour_wet3d"].fillna(0.0)
        te["neighbour"] = te["neighbour_wet3d"].fillna(0.0)
        AUG = [
            "prior_wet_days", "prior_max_fraction", "frac_now", "frac_max3d",
            "day_of_season", "neighbour", "season_climo",
        ]
        te["selected_plus"] = _fit_predict(
            AUG, tr_w, te, nested_years=tr_w["year"].to_numpy()
        )
        parts.append(te)

    s = pd.concat(parts, ignore_index=True)
    s["persistence"] = s["frac_now"].fillna(0.0)
    s["neighbour"] = s["neighbour_wet3d"].fillna(0.0)
    # transparent additive: neighbours, season and own water, no learning
    s["climo_plus_neighbour"] = (
        s["season_climo"].rank(pct=True)
        + s["neighbour"].rank(pct=True)
        + s["persistence"].rank(pct=True)
    )

    events = onset_events(df, THRESHOLD)
    cols = ["selected", "selected_plus", "persistence", "season_climo",
            "neighbour", "climo_plus_neighbour"]

    from pipeline.run_forecaster_daily_audit import _event_recall

    rows = []
    print("\n" + "=" * 74)
    print("1+3. SELECTED SYSTEM versus genuinely different transparent baselines")
    print("=" * 74)
    print(f"variants chosen across folds: {dict(pd.Series(picks).value_counts())}")
    base = s["y"].mean()
    print(f"base rate {base:.4f}, n={len(s)}, positive district-days={int(s['y'].sum())}")
    print(f"\n{'scorer':22s} {'AP':>7} {'lift':>6} {'row R@5':>8} {'EVENT R@3':>10} {'EVENT R@5':>10}")
    for c in cols:
        ap = average_precision_score(s["y"], s[c])
        r5 = _recall_at_k(s, c, 5)
        e3, n_ev = _event_recall(s, events, c, 3, HORIZON)
        e5, _ = _event_recall(s, events, c, 5, HORIZON)
        print(f"{c:22s} {ap:7.3f} {ap / base:6.1f} {r5:8.3f} {e3:10.3f} {e5:10.3f}")
        rows.append({"check": "selected_vs_baselines", "scorer": c, "ap": ap,
                     "lift": ap / base, "row_r5": r5, "event_r3": e3, "event_r5": e5})
    print(f"\ndistinct onset events: {n_ev}")

    print("\n" + "=" * 74)
    print("2. DE NOVO AT EVENT LEVEL")
    print("=" * 74)
    full = df.copy()
    full["md"] = full["date"].dt.strftime("%m-%d")
    prev = (
        full.sort_values(["district", "year", "date"])
        .groupby(["district", "year"], sort=False)["fraction"]
        .shift(1)
    )
    full["prev_frac"] = prev
    ev = events.merge(
        full[["date", "district", "prev_frac"]], on=["date", "district"], how="left"
    )
    denovo = (ev["prev_frac"].fillna(0.0) <= 0.0).sum()
    print(f"distinct onset events: {len(ev)}")
    print(f"  preceded by ZERO observed water the day before: {denovo} "
          f"({denovo / len(ev):.1%})")
    print(f"  preceded by some sub-threshold water:           {len(ev) - denovo} "
          f"({1 - denovo / len(ev):.1%})")
    rows.append({"check": "denovo_event_level", "n_events": len(ev),
                 "denovo_events": int(denovo), "share": denovo / len(ev)})

    pd.DataFrame(rows).to_csv(OUT, index=False)
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
