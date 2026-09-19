from __future__ import annotations

from types import SimpleNamespace

import pandas as pd

from punjabflood import cli
from tests.test_inflow import _synthetic_melt


def _two_dams():
    """The synthetic record at two dams, both with a melt column on the rain table."""
    s_b, r_b = _synthetic_melt(c_melt=0.6)
    s_p, r_p = _synthetic_melt(c_melt=0.6, seed=7)
    s_b = s_b.assign(dam="Bhakra")
    s_p = s_p.assign(dam="Pong")
    r_b = r_b.assign(catchment="Bhakra")
    r_p = r_p.assign(catchment="Pong")
    state = pd.concat([s_b, s_p], ignore_index=True)
    rain = pd.concat([r_b, r_p], ignore_index=True)
    cats = {"Bhakra": SimpleNamespace(area_km2=12560.0), "Pong": SimpleNamespace(area_km2=12560.0)}
    return state, rain, cats


def test_fit_params_puts_the_melt_term_on_bhakra_only():
    state, rain, cats = _two_dams()
    fitted = cli.fit_params(state, rain, cats, melt=True, dams=("Bhakra", "Pong"))
    assert set(fitted) == {"Bhakra", "Pong"}
    assert fitted["Bhakra"].has_melt and fitted["Bhakra"].c_melt > 0
    assert not fitted["Pong"].has_melt and fitted["Pong"].c_melt == 0.0
    plain = cli.fit_params(state, rain, cats, melt=False, dams=("Bhakra", "Pong"))
    assert not plain["Bhakra"].has_melt
    # the file form round-trips the term
    back = {k: cli.inflow.InflowParams.from_dict(v.to_dict()) for k, v in fitted.items()}
    assert back["Bhakra"].w_melt == fitted["Bhakra"].w_melt
    assert back["Pong"].w_melt == ()


def test_fit_params_skips_a_dam_the_record_lacks():
    state, rain, cats = _two_dams()
    fitted = cli.fit_params(state, rain, cats, melt=False, dams=("Bhakra", "Pong", "Ranjit Sagar"))
    assert "Ranjit Sagar" not in fitted
