# pipeline/run_forecaster_daily_audit.py
"""Three checks that decide what the daily forecaster may actually claim.

Each of these can overturn the headline numbers, so each is run and reported
whatever it says.

1. EVENT-DEDUPLICATED RECALL. With a three-day horizon a single onset produces
   up to three positive district-days, so per-row recall can count one flood
   three times. Recall is recomputed per onset EVENT: an event counts as caught
   once if an alert fired on any of the days that legitimately precede it.

2. DE NOVO VERSUS ESCALATION. Candidate rows split into those showing no water
   at all at issue time and those already carrying water below the alarm
   threshold. If the skill lives only in the second group, the system forecasts
   the escalation of visible inundation rather than the arrival of new flooding,
   and must say so.

3. STRONGER BASELINES. Persistence ranks by current water alone. Beating only
   that proves little, so the model is also compared against explicit
   transparent hazards: distance to the threshold, the district's own historical
   wet-day rate, and the two combined.

Run: python -m pipeline.run_forecaster_daily_audit
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score

from pipeline.run_forecaster_daily import (
    CORE_MD,
    HORIZON,
    PRIOR_F,
    SEASON_F,
    STATE_F,
    THRESHOLD,
    _candidates,
    _fit_predict,
    _fold_prior,
    build_frame,
)
from sailaab.forecast_daily import forward_event

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = DATA / "forecaster_daily_audit.csv"

WINNER = PRIOR_F + STATE_F + SEASON_F


def _scored(df: pd.DataFrame, threshold: float, horizon: int) -> pd.DataFrame:
    """Out-of-fold scores for the winning feature set, plus the baselines."""
    d = df.copy()
    d["y"] = forward_event(d, threshold=threshold, horizon=horizon)
    d = _candidates(d, threshold, hysteresis=False).dropna(subset=["y"])

    years = sorted(d["year"].unique())
    parts = []
    for ty in years:
        trys = [y for y in years if y != ty]
        fold = d.merge(
            _fold_prior(d, trys, threshold), on="district", how="left", validate="m:1"
        )
        tr, te = fold[fold["year"].isin(trys)], fold[fold["year"] == ty].copy()
        if te.empty:
            continue
        te["model"] = _fit_predict(WINNER, tr, te, nested_years=tr["year"].to_numpy())
        parts.append(te)
    s = pd.concat(parts, ignore_index=True)

    # transparent hazards, no fitting involved
    s["persistence"] = s["frac_now"].fillna(0.0)
    s["distance_to_threshold"] = -(threshold - s["frac_now"].fillna(0.0))
    s["district_wet_rate"] = s["prior_wet_days"].fillna(0.0)
    s["hazard_combined"] = s["persistence"] + 1e-6 * s["district_wet_rate"]
    return s


def _recall_at_k(sub: pd.DataFrame, col: str, k: int) -> float:
    """Row-level recall at k within each issue day."""
    hits = tot = 0
    for _, g in sub.groupby("date"):
        if g["y"].sum() == 0:
            continue
        top = g.nlargest(k, col).index
        hits += int(g.loc[top, "y"].sum())
        tot += int(g["y"].sum())
    return hits / tot if tot else float("nan")


def onset_events(full: pd.DataFrame, threshold: float) -> pd.DataFrame:
    """Distinct onset events: the day a district first crosses the threshold.

    Crossings must be read off the FULL daily series, not the scored candidate
    set: candidates are restricted to rows below the threshold, so by
    construction no crossing day appears among them.
    """
    d = full.copy()
    d["md"] = d["date"].dt.strftime("%m-%d")
    d = d[d["md"] >= CORE_MD].sort_values(["district", "year", "date"])
    wet = d["fraction"].fillna(0.0) > threshold
    prev = wet.groupby([d["district"], d["year"]]).shift(1).fillna(False)
    ev = d[wet & ~prev.astype(bool)]
    return ev[["date", "district", "year"]].reset_index(drop=True)


def _event_recall(sub: pd.DataFrame, events: pd.DataFrame, col: str, k: int, horizon: int):
    """Recall over deduplicated onset events.

    An event counts as caught once if its district appeared in the top ``k`` on
    any issue day from one to ``horizon`` days before the crossing. This is the
    number an operator experiences: one flood warned or missed, however many
    rows the horizon happened to label.
    """
    alerts = set()
    for day, g in sub.groupby("date"):
        for dist in g.nlargest(k, col)["district"]:
            alerts.add((pd.Timestamp(day), dist))

    caught = 0
    for _, e in events.iterrows():
        day = pd.Timestamp(e["date"])
        if any(
            (day - pd.Timedelta(days=h), e["district"]) in alerts
            for h in range(1, horizon + 1)
        ):
            caught += 1
    total = len(events)
    return (caught / total if total else float("nan")), total


def main() -> None:
    df = build_frame()
    s = _scored(df, THRESHOLD, HORIZON)
    events = onset_events(df, THRESHOLD)
    cols = [
        "model",
        "persistence",
        "distance_to_threshold",
        "hazard_combined",
        "district_wet_rate",
    ]

    rows = []
    print("=" * 74)
    print("1. EVENT-DEDUPLICATED RECALL versus per-row recall")
    print("=" * 74)
    print(f"{'scorer':24s} {'row R@3':>8} {'row R@5':>8} {'event R@3':>10} {'event R@5':>10}")
    n_ev = 0
    for c in cols:
        r3, r5 = _recall_at_k(s, c, 3), _recall_at_k(s, c, 5)
        e3, n_ev = _event_recall(s, events, c, 3, HORIZON)
        e5, _ = _event_recall(s, events, c, 5, HORIZON)
        print(f"{c:24s} {r3:8.3f} {r5:8.3f} {e3:10.3f} {e5:10.3f}")
        rows.append(
            {
                "check": "event_recall",
                "scorer": c,
                "row_r3": r3,
                "row_r5": r5,
                "event_r3": e3,
                "event_r5": e5,
            }
        )
    print(f"\ndistinct onset events: {n_ev}")

    print("\n" + "=" * 74)
    print("2. DE NOVO (no water at issue) versus ESCALATION (water below alarm)")
    print("=" * 74)
    denovo = s[s["frac_now"].fillna(0.0) <= 0.0]
    esc = s[s["frac_now"].fillna(0.0) > 0.0]
    for label, sub in (
        ("de novo (frac_now = 0)", denovo),
        ("escalation (0 < frac < thr)", esc),
    ):
        if sub.empty or sub["y"].nunique() < 2:
            print(f"{label:28s} n={len(sub):6d}  not evaluable")
            continue
        print(
            f"{label:28s} n={len(sub):6d}  positives={int(sub['y'].sum()):4d}  "
            f"base={sub['y'].mean():.4f}"
        )
        for c in cols:
            ap = average_precision_score(sub["y"], sub[c])
            print(f"    {c:22s} AP={ap:.3f}  lift={ap / sub['y'].mean():5.1f}x")
            rows.append(
                {
                    "check": "denovo_split",
                    "group": label,
                    "scorer": c,
                    "ap": ap,
                    "n": len(sub),
                    "base": sub["y"].mean(),
                }
            )

    print("\n" + "=" * 74)
    print("3. STRONGER BASELINES, all rows")
    print("=" * 74)
    base = s["y"].mean()
    print(f"base rate {base:.4f}, n={len(s)}, positives={int(s['y'].sum())}")
    for c in cols:
        ap = average_precision_score(s["y"], s[c])
        print(f"  {c:24s} AP={ap:.3f}  lift={ap / base:5.1f}x")
        rows.append({"check": "baselines", "scorer": c, "ap": ap, "base": base})

    pd.DataFrame(rows).to_csv(OUT, index=False)
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
