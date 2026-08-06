# tests/test_hazard.py
import numpy as np
import pandas as pd
import pytest

from sailaab.hazard import (
    FirthLogistic,
    contingency_scores,
    excitation_features,
    graph_rings,
    prior_correct,
)

ADJ = {"A": ["B"], "B": ["A", "C"], "C": ["B"], "D": []}


# --- graph_rings --------------------------------------------------------------
def test_rings_are_hop_counts_on_the_adjacency_graph():
    rings = graph_rings(ADJ, max_hops=2)
    assert rings["A"][0] == ["A"]
    assert rings["A"][1] == ["B"]
    assert rings["A"][2] == ["C"]


def test_isolated_district_has_only_itself():
    rings = graph_rings(ADJ, max_hops=2)
    assert rings["D"][0] == ["D"]
    assert rings["D"][1] == []
    assert rings["D"][2] == []


def test_rings_do_not_revisit_nearer_districts():
    # B is one hop from A, so it must not also appear at two hops
    rings = graph_rings(ADJ, max_hops=2)
    assert "B" not in rings["A"][2]
    assert "A" not in rings["A"][1]


# --- excitation_features ------------------------------------------------------
def _daily(rows):
    return pd.DataFrame(
        [{"date": d, "district": k, "fraction": v} for d, k, v in rows]
    )


def test_excitation_decays_with_time():
    daily = _daily(
        [("2020-08-01", "A", 1.0)]
        + [(f"2020-08-0{d}", "A", 0.0) for d in range(2, 6)]
    )
    out = excitation_features(daily, ADJ, threshold=0.5, tau=2.0, max_hops=0)
    v = (
        out[out["district"] == "A"].sort_values("date")["excite_h0"].tolist()
    )
    assert v[0] == pytest.approx(0.0)  # the event day itself contributes nothing yet
    assert v[1] > v[2] > v[3]  # strictly decaying afterwards
    assert v[1] == pytest.approx(np.exp(-1 / 2.0))


def test_excitation_is_strictly_causal():
    """An event tomorrow must not raise today's excitation."""
    a = excitation_features(
        _daily([("2020-08-01", "A", 0.0), ("2020-08-02", "A", 0.0)]),
        ADJ, threshold=0.5, tau=2.0, max_hops=0,
    )
    b = excitation_features(
        _daily([("2020-08-01", "A", 0.0), ("2020-08-02", "A", 1.0)]),
        ADJ, threshold=0.5, tau=2.0, max_hops=0,
    )
    first_a = a[a["date"] == pd.Timestamp("2020-08-01")]["excite_h0"].iloc[0]
    first_b = b[b["date"] == pd.Timestamp("2020-08-01")]["excite_h0"].iloc[0]
    assert first_a == first_b == pytest.approx(0.0)


def test_neighbour_ring_carries_excitation_across_the_graph():
    daily = _daily(
        [("2020-08-01", "A", 1.0), ("2020-08-02", "A", 0.0)]
        + [("2020-08-01", d, 0.0) for d in ("B", "C", "D")]
        + [("2020-08-02", d, 0.0) for d in ("B", "C", "D")]
    )
    out = excitation_features(daily, ADJ, threshold=0.5, tau=2.0, max_hops=2)
    day2 = out[out["date"] == pd.Timestamp("2020-08-02")].set_index("district")
    assert day2.loc["B", "excite_h1"] > 0  # B touches A
    assert day2.loc["C", "excite_h2"] > 0  # C is two hops from A
    assert day2.loc["D", "excite_h1"] == pytest.approx(0.0)  # D is disconnected
    assert day2.loc["A", "excite_h0"] > 0  # A excites itself


def test_subthreshold_water_is_not_an_event():
    daily = _daily([("2020-08-01", "A", 0.4), ("2020-08-02", "A", 0.0)])
    out = excitation_features(daily, ADJ, threshold=0.5, tau=2.0, max_hops=0)
    assert out["excite_h0"].max() == pytest.approx(0.0)


# --- FirthLogistic ------------------------------------------------------------
def test_firth_gives_finite_estimates_under_separation():
    """Plain maximum likelihood diverges when the classes are perfectly
    separable. Firth's penalty is the standard fix and must stay finite."""
    X = np.array([[-2.0], [-1.0], [1.0], [2.0]])
    y = np.array([0.0, 0.0, 1.0, 1.0])
    m = FirthLogistic().fit(X, y)
    assert np.all(np.isfinite(m.coef_))
    assert np.isfinite(m.intercept_)


def test_firth_recovers_the_direction_of_a_clear_signal():
    rng = np.random.default_rng(0)
    X = rng.normal(size=(400, 1))
    y = (X[:, 0] + rng.normal(scale=0.3, size=400) > 1.5).astype(float)
    m = FirthLogistic().fit(X, y)
    assert m.coef_[0] > 0


def test_firth_predict_proba_is_bounded_and_two_column():
    X = np.array([[-2.0], [-1.0], [1.0], [2.0]])
    y = np.array([0.0, 0.0, 1.0, 1.0])
    p = FirthLogistic().fit(X, y).predict_proba(X)
    assert p.shape == (4, 2)
    assert np.all((p >= 0) & (p <= 1))
    assert np.allclose(p.sum(axis=1), 1.0)


def test_firth_handles_a_single_class_without_raising():
    X = np.array([[0.0], [1.0]])
    y = np.array([0.0, 0.0])
    m = FirthLogistic().fit(X, y)
    assert np.all(np.isfinite(m.predict_proba(X)))


# --- prior_correct ------------------------------------------------------------
def test_prior_correction_pulls_balanced_probabilities_down_to_the_base_rate():
    # a balanced fit says 0.5; the true base rate is 2%, so the corrected
    # probability must land near 2%, not near 50%
    p = prior_correct(np.array([0.5]), tau=0.02, sample_rate=0.5)
    assert p[0] == pytest.approx(0.02, abs=1e-9)


def test_prior_correction_is_identity_when_sample_matches_population():
    p = np.array([0.1, 0.4, 0.9])
    assert np.allclose(prior_correct(p, tau=0.3, sample_rate=0.3), p)


def test_prior_correction_preserves_ranking():
    p = np.array([0.2, 0.5, 0.8])
    out = prior_correct(p, tau=0.02, sample_rate=0.5)
    assert np.all(np.diff(out) > 0)


def test_prior_correction_handles_the_endpoints():
    out = prior_correct(np.array([0.0, 1.0]), tau=0.02, sample_rate=0.5)
    assert out[0] == pytest.approx(0.0)
    assert out[1] == pytest.approx(1.0)


# --- contingency_scores -------------------------------------------------------
def test_pod_far_csi_match_their_definitions():
    y = np.array([1, 1, 1, 0, 0, 0, 0])
    alert = np.array([1, 1, 0, 1, 0, 0, 0])
    s = contingency_scores(y, alert)
    assert s["hits"] == 2 and s["misses"] == 1 and s["false_alarms"] == 1
    assert s["pod"] == pytest.approx(2 / 3)
    assert s["far"] == pytest.approx(1 / 3)
    assert s["csi"] == pytest.approx(2 / 4)


def test_perfect_forecast_scores_perfectly():
    y = np.array([1, 0, 1, 0])
    s = contingency_scores(y, y)
    assert s["pod"] == 1.0 and s["far"] == 0.0 and s["csi"] == 1.0


def test_no_alerts_gives_zero_pod_and_undefined_far():
    y = np.array([1, 0, 1])
    s = contingency_scores(y, np.zeros(3))
    assert s["pod"] == 0.0
    assert np.isnan(s["far"])
    assert s["csi"] == 0.0


def test_bias_reports_over_and_under_warning():
    y = np.array([1, 0, 0, 0])
    over = contingency_scores(y, np.array([1, 1, 1, 0]))
    assert over["bias"] == pytest.approx(3.0)  # three alerts for one event
