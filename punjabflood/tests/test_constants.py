from __future__ import annotations

import math

import pytest

from punjabflood import constants as C


def test_unit_conversions_are_exact():
    assert C.CUSEC_M3_PER_S == pytest.approx(0.028316846592, abs=1e-15)
    assert C.cusecs_to_m3s(100_000) == pytest.approx(2831.6846592)
    assert C.m3s_to_cusecs(C.cusecs_to_m3s(12345.0)) == pytest.approx(12345.0)
    # one lakh cusecs for one day is 0.2447 BCM
    assert C.cusec_days_to_bcm(100_000) == pytest.approx(0.24465755, rel=1e-6)
    assert C.bcm_to_cusec_days(C.cusec_days_to_bcm(7.5)) == pytest.approx(7.5)
    assert C.feet_to_m(1680.0) == pytest.approx(512.064)


def test_reach_tables_add_up_to_annexure_z_totals():
    for river, total in C.ANNEXURE_Z_TOTALS.items():
        chain = [r for r in C.REACHES if r.river == river]
        end = "Harike Head Works" if river != "Ghaggar" else "Sardulgarh"
        hours = C.travel_hours(river, chain[0].frm, end)
        assert hours == pytest.approx(total.value), river
        km = sum(
            r.km for r in chain if not (river == "Sutlej" and r.to == "Hussainiwala Head Works")
        )
        # the Beas reaches print 5 + 34.3 + 14.7 + 35 + 126.3 = 215.3 against a total of 215
        assert km == pytest.approx(C.ANNEXURE_Z_TOTAL_KM[river], abs=0.5), river


def test_travel_hours_intermediate_and_errors():
    assert C.travel_hours("Sutlej", "Bhakra Dam", "Ropar Head Works") == 18
    assert C.travel_hours("Sutlej", "Ropar Head Works", "Harike Head Works") == 34
    assert C.travel_hours("Beas", "Pong Dam", "Tanda Bridge") == 26
    with pytest.raises(ValueError):
        C.travel_hours("Sutlej", "Harike Head Works", "Bhakra Dam")
    with pytest.raises(KeyError):
        C.travel_hours("Sutlej", "Bhakra Dam", "Dhilwan")


def test_thresholds_are_ordered_and_classify_on_boundaries():
    for cp in C.CONTROL_POINTS.values():
        assert cp.low_min < cp.low_max <= cp.med_min < cp.med_max <= cp.high_min, cp.station
        assert cp.classify(cp.low_min - 1) is None
        assert cp.classify(cp.low_min) == "low"
        assert cp.classify(cp.med_min) == "medium"
        assert cp.classify(cp.high_min) == "high"
        assert cp.classify(cp.high_min * 3) == "high"
        assert cp.classify(math.nan) is None
    harike = C.CONTROL_POINTS["Harike Head Works"]
    assert harike.classify(301_061) == "high"  # WRD 2023 annual peak, classed H
    assert harike.classify(119_250) == "low"  # WRD 2019 annual peak, classed L
    # the printed Dhilwan gap classifies as low, as documented
    assert C.CONTROL_POINTS["Dhilwan"].classify(175_000) == "low"
    assert C.CONTROL_POINTS["Dhilwan"].note


def test_every_dam_constant_carries_a_source():
    for dam in C.DAMS.values():
        for name in ("frl_ft", "frl_m", "live_capacity_bcm"):
            s = getattr(dam, name)
            assert s.source and s.value > 0, (dam.name, name)
        for name in (
            "mwl_ft",
            "min_level_ft",
            "gross_capacity_bcm",
            "catchment_km2_published",
            "spillway_capacity_cusecs",
            "turbine_capacity_cusecs",
            "max_observed_inflow_cusecs",
        ):
            s = getattr(dam, name)
            assert s is None or (s.source and s.value > 0), (dam.name, name)
        assert dam.frl_m.value == pytest.approx(C.feet_to_m(dam.frl_ft.value), abs=0.01)
    assert C.PONG.turbine_capacity_cusecs.value == 6 * 7600
    assert C.PONG.spillway_capacity_cusecs.value == 437_000
    assert C.RANJIT_SAGAR.spillway_capacity_cusecs.value == pytest.approx(C.m3s_to_cusecs(24_637.0))


def test_extra_constants_carry_sources_and_the_rule_curve_is_ordered():
    for dam in C.DAMS.values():
        for name, s in dam.extra.items():
            if isinstance(s, C.Sourced):
                assert s.source and s.value > 0, (dam.name, name)
    # the 2019 Bhakra filling schedule: below FRL, rising through the season, page cited
    jul = C.BHAKRA.extra["rule_curve_max_level_ft_31_jul"]
    aug = C.BHAKRA.extra["rule_curve_max_level_ft_15_aug"]
    assert jul.value < aug.value < C.BHAKRA.frl_ft.value
    assert "page 44" in jul.source and "2019" in jul.note and "2019" in aug.note
    # nothing of the kind is claimed for Pong or Ranjit Sagar
    assert C.BHAKRA.extra["rule_curve_frl_date_31_aug"].value == C.BHAKRA.frl_ft.value
    assert not any(k.startswith("rule_curve") for k in C.PONG.extra)
    assert not any(k.startswith("rule_curve") for k in C.RANJIT_SAGAR.extra)


def test_flood_cushion_is_published_for_pong_only():
    top_m, top_bcm = C.flood_cushion("Pong")
    assert top_m == pytest.approx(1400.0 * C.FOOT_M)
    assert top_bcm == pytest.approx(7.290)
    assert top_bcm > C.PONG.live_capacity_bcm.value
    assert C.cushion_capacity_bcm("Pong") == pytest.approx(7.290)
    for dam in ("Bhakra", "Ranjit Sagar"):
        assert C.flood_cushion(dam) is None
        assert C.cushion_capacity_bcm(dam) == C.DAMS[dam].live_capacity_bcm.value


def test_rule_curve_level_holds_to_its_date_then_rises_to_frl():
    pts = C.rule_curve("Bhakra")
    assert [(m, d) for m, d, _ in pts] == [(7, 31), (8, 15), (8, 31)]
    assert [lv for _, _, lv in pts] == [1650.0, 1670.0, 1680.0]
    frl = C.BHAKRA.frl_ft.value
    assert pts[-1][2] == frl
    # a point's level holds up to and on its date
    assert C.rule_curve_level_ft("Bhakra", "2023-06-15") == 1650.0
    assert C.rule_curve_level_ft("Bhakra", "2023-07-31") == 1650.0
    assert C.rule_curve_level_ft("Bhakra", "2023-08-01") == 1670.0
    assert C.rule_curve_level_ft("Bhakra", "2023-08-15") == 1670.0
    # a straight line from 15 August to the date FRL may be reached
    mid = C.rule_curve_level_ft("Bhakra", "2023-08-23")
    assert 1670.0 < mid < 1680.0 and mid == pytest.approx(1670.0 + 10.0 * 8 / 16)
    assert C.rule_curve_level_ft("Bhakra", "2023-08-31") == frl
    assert C.rule_curve_level_ft("Bhakra", "2023-09-20") == frl
    import datetime

    assert C.rule_curve_level_ft("Bhakra", datetime.date(2025, 8, 19)) == pytest.approx(1672.5)
    # the 2025 guideline sits below the 2019 line: evidence of a revision, recorded with it
    g = C.BHAKRA.extra["rule_curve_guideline_ft_19_aug_2025"]
    assert g.value == 1662.0 and "tribuneindia" in g.source
    assert g.value < C.rule_curve_level_ft("Bhakra", "2025-08-19")
    # nothing of the kind for the other dams
    for dam in ("Pong", "Ranjit Sagar"):
        assert C.rule_curve(dam) is None and C.rule_curve_level_ft(dam, "2025-08-19") is None
    assert "2019" in C.RULE_CURVE_VINTAGE["Bhakra"]

