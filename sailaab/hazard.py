# sailaab/hazard.py
"""Rare-event hazard modelling: self-excitation, Firth logistic, warning scores.

Three pieces, each taken from an established literature rather than invented
here, and each chosen because it fits the specific shape of this problem: about
two hundred and eighty positive district-days in eleven monsoons, spread over
twenty spatial units connected by rivers.

SELF-EXCITATION. Flood onsets are not independent draws. One district flooding
raises the chance that it, and the districts downstream and beside it, flood in
the following days. That is the defining property of a self-exciting point
process, the family used for earthquake aftershocks, crime and epidemics, where
each event raises the intensity of further events in its temporal and spatial
neighbourhood. The full machinery is far too rich for ninety-six events, so what
is used here is its feature: an excitation term that sums past flood days with an
exponential decay in time and a ring decay in graph distance. Two interpretable
numbers, a decay time and a hop, instead of a fitted branching structure. This
is also the parsimonious cousin of the graph neural networks now used for flood
routing, which learn propagation over the river network but need far more events
than exist here.

FIRTH LOGISTIC AND PRIOR CORRECTION. With a two percent base rate this is
textbook rare-events territory, where maximum likelihood is biased away from
zero and can fail to exist at all under separation. Firth's penalised likelihood
is the standard remedy and always returns finite estimates. Firth alone biases
predicted probabilities toward one half, so King and Zeng's prior correction is
applied afterwards to put them back on the population scale. Together they turn
a ranking score into a probability that can be quoted honestly.

WARNING SCORES. Average precision is a machine-learning metric. Operational
flood warning is verified with probability of detection, false alarm ratio and
critical success index, computed from a contingency table. Reporting those makes
the result legible to the people who would actually use it.
"""

from __future__ import annotations

from collections import deque

import numpy as np
import pandas as pd


# --------------------------------------------------------------------------- #
# self-excitation
# --------------------------------------------------------------------------- #
def graph_rings(adjacency: dict, max_hops: int = 2) -> dict:
    """``district -> {hop: [districts exactly that many hops away]}``.

    Hop 0 is the district itself. Breadth-first, so a district appears in
    exactly one ring, the nearest one that reaches it.
    """
    rings = {}
    for start in adjacency:
        seen = {start: 0}
        q = deque([start])
        while q:
            cur = q.popleft()
            if seen[cur] >= max_hops:
                continue
            for nxt in adjacency.get(cur, []):
                if nxt not in seen:
                    seen[nxt] = seen[cur] + 1
                    q.append(nxt)
        rings[start] = {
            h: sorted(d for d, dist in seen.items() if dist == h)
            for h in range(max_hops + 1)
        }
    return rings


def excitation_features(
    daily: pd.DataFrame,
    adjacency: dict,
    threshold: float,
    tau: float = 3.0,
    max_hops: int = 2,
    value_col: str = "fraction",
    key: str = "district",
    date_col: str = "date",
) -> pd.DataFrame:
    """Self-exciting intensity per district-day, split by graph ring.

    ``excite_h<k>`` on day t is the sum over every district exactly k hops away,
    and every earlier day t', of ``exp(-(t - t') / tau)`` where that district was
    above ``threshold`` on t'. The event day itself contributes nothing to its
    own value, so the feature is strictly causal: it describes what had already
    happened when the forecast was issued.

    ``tau`` is the decay time in days. Three is the default because that is the
    routing time from upstream catchment rain and dam release to the plains.
    """
    d = daily.copy()
    d[date_col] = pd.to_datetime(d[date_col])
    rings = graph_rings(adjacency, max_hops=max_hops)

    wide = (
        d.pivot_table(index=date_col, columns=key, values=value_col, aggfunc="max")
        .sort_index()
    )
    # A missing observation is NOT a dry day. Letting NaN fall through to False
    # would make an unimaged district-day contribute zero excitation, which
    # lowers apparent risk exactly where the satellite failed to look. Carry the
    # last observed state forward instead, and only treat a district as quiet
    # once something was actually seen.
    seen = wide.ffill()
    events = (seen > threshold).astype(float)
    events[seen.isna()] = 0.0  # nothing ever observed for this district yet
    days = events.index
    cols = list(events.columns)
    n = len(days)

    # Recursive decay: e_t = exp(-dt/tau) * (e_{t-1} + event_{t-1}). Exact for
    # the exponential kernel and linear in the number of days, so it stays cheap
    # over a decade of daily rows.
    per_district = np.zeros((n, len(cols)), dtype=float)
    ev = events.to_numpy(dtype=float)
    for i in range(1, n):
        dt = (days[i] - days[i - 1]).days or 1
        decay = float(np.exp(-dt / float(tau)))
        per_district[i] = decay * (per_district[i - 1] + ev[i - 1])

    idx = {c: j for j, c in enumerate(cols)}
    out = []
    for i, day in enumerate(days):
        for name in adjacency:
            row = {date_col: day, key: name}
            for h in range(max_hops + 1):
                members = [m for m in rings[name][h] if m in idx]
                row[f"excite_h{h}"] = (
                    float(sum(per_district[i, idx[m]] for m in members))
                    if members
                    else 0.0
                )
            out.append(row)
    return pd.DataFrame(out)


# --------------------------------------------------------------------------- #
# rare-event logistic regression
# --------------------------------------------------------------------------- #
class FirthLogistic:
    """Logistic regression with Firth's penalised likelihood.

    Firth adds the Jeffreys prior to the likelihood, which removes the
    first-order small-sample bias and guarantees finite estimates even when the
    classes separate, the two failure modes of plain maximum likelihood on rare
    events. Fitted by Newton-Raphson on the penalised score.

    Features are expected pre-standardised; the caller owns imputation and
    scaling so this stays a plain estimator.
    """

    def __init__(self, max_iter: int = 50, tol: float = 1e-6, ridge: float = 1e-6):
        self.max_iter = max_iter
        self.tol = tol
        self.ridge = ridge
        self.coef_ = None
        self.intercept_ = 0.0

    def fit(self, X, y):
        X = np.asarray(X, dtype=float)
        y = np.asarray(y, dtype=float).ravel()
        n, p = X.shape
        Z = np.column_stack([np.ones(n), X])  # intercept first
        beta = np.zeros(p + 1)

        for _ in range(self.max_iter):
            eta = Z @ beta
            pi = 1.0 / (1.0 + np.exp(-np.clip(eta, -35, 35)))
            w = np.clip(pi * (1.0 - pi), 1e-10, None)
            ZW = Z * w[:, None]
            info = Z.T @ ZW + self.ridge * np.eye(p + 1)
            try:
                inv = np.linalg.inv(info)
            except np.linalg.LinAlgError:
                inv = np.linalg.pinv(info)
            # hat diagonals of the weighted design
            h = np.einsum("ij,jk,ik->i", ZW, inv, ZW) / np.clip(w, 1e-10, None)
            # Firth-penalised score
            score = Z.T @ (y - pi + h * (0.5 - pi))
            step = inv @ score
            # damp the step so a near-singular information matrix cannot throw
            # the fit across the parameter space
            norm = np.linalg.norm(step)
            if norm > 5.0:
                step *= 5.0 / norm
            beta_new = beta + step
            if np.max(np.abs(beta_new - beta)) < self.tol:
                beta = beta_new
                break
            beta = beta_new

        self.intercept_ = float(beta[0])
        self.coef_ = beta[1:]
        return self

    def decision_function(self, X):
        X = np.asarray(X, dtype=float)
        return self.intercept_ + X @ self.coef_

    def predict_proba(self, X):
        eta = np.clip(self.decision_function(X), -35, 35)
        p1 = 1.0 / (1.0 + np.exp(-eta))
        return np.column_stack([1.0 - p1, p1])


def prior_correct(proba, tau: float, sample_rate: float):
    """King and Zeng prior correction for a fit made on a re-balanced sample.

    Fitting with balanced class weights (or on an oversampled positive set)
    inflates predicted probabilities, because the model believes positives are
    far more common than they are. This maps them back onto the population base
    rate ``tau`` given the effective positive rate ``sample_rate`` used in
    fitting. Monotone, so the ranking is untouched and only the scale moves.
    """
    p = np.asarray(proba, dtype=float)
    if not (0 < tau < 1) or not (0 < sample_rate < 1):
        raise ValueError("tau and sample_rate must lie strictly in (0, 1)")
    factor = (tau / (1.0 - tau)) * ((1.0 - sample_rate) / sample_rate)
    with np.errstate(divide="ignore", invalid="ignore"):
        odds = p / (1.0 - p)
        corrected = odds * factor
        out = corrected / (1.0 + corrected)
    out = np.where(p >= 1.0, 1.0, out)
    out = np.where(p <= 0.0, 0.0, out)
    return out


# --------------------------------------------------------------------------- #
# operational verification
# --------------------------------------------------------------------------- #
def contingency_scores(y_true, alert) -> dict:
    """Probability of detection, false alarm ratio, critical success index.

    The standard contingency scores used to verify operational flood warnings:

        POD  = hits / (hits + misses)          fraction of floods warned
        FAR  = false alarms / (hits + FA)      fraction of warnings that were wrong
        CSI  = hits / (hits + misses + FA)     overall success, penalising both
        bias = (hits + FA) / (hits + misses)   over-warning above 1

    FAR is undefined and reported as NaN when nothing was ever alerted.
    """
    y = np.asarray(y_true, dtype=float)
    a = np.asarray(alert, dtype=float)
    ok = ~(np.isnan(y) | np.isnan(a))
    y, a = y[ok] > 0.5, a[ok] > 0.5

    hits = int(np.sum(y & a))
    misses = int(np.sum(y & ~a))
    fa = int(np.sum(~y & a))
    correct_neg = int(np.sum(~y & ~a))

    obs = hits + misses
    warned = hits + fa
    return {
        "hits": hits,
        "misses": misses,
        "false_alarms": fa,
        "correct_negatives": correct_neg,
        "pod": (hits / obs) if obs else float("nan"),
        "far": (fa / warned) if warned else float("nan"),
        "csi": (hits / (hits + misses + fa)) if (hits + misses + fa) else float("nan"),
        "bias": (warned / obs) if obs else float("nan"),
    }
