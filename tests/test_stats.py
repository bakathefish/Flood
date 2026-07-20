# tests/test_stats.py
import pandas as pd
import pytest

from sailaab.stats import tidy_district_export, flooded_fraction


def _raw():
    # Shape of a GEE reduceRegions CSV export (system:index etc. dropped here)
    return pd.DataFrame(
        {
            "ADM2_NAME": ["Gurdaspur", "Firozpur"],
            "flooded_ha": [12000.4, 8000.2],
            "crop_flooded_ha": [9000.1, 6500.0],
            "window_start": ["2025-08-25", "2025-08-25"],
            "year": [2025, 2025],
        }
    )


def test_tidy_renames_and_types():
    df = tidy_district_export(_raw())
    assert list(df.columns) == [
        "district",
        "window_start",
        "year",
        "flooded_ha",
        "crop_flooded_ha",
    ]
    assert df["flooded_ha"].dtype == float


def test_tidy_rejects_missing_columns():
    with pytest.raises(ValueError, match="ADM2_NAME"):
        tidy_district_export(pd.DataFrame({"x": [1]}))


def test_flooded_fraction_joins_area():
    df = tidy_district_export(_raw())
    areas = pd.DataFrame(
        {"district": ["Gurdaspur", "Firozpur"], "area_ha": [356_900, 528_000]}
    )
    out = flooded_fraction(df, areas)
    assert out.loc[out.district == "Gurdaspur", "flooded_fraction"].iloc[
        0
    ] == pytest.approx(12000.4 / 356_900)


def test_flooded_fraction_errors_on_unknown_district():
    df = tidy_district_export(_raw())
    areas = pd.DataFrame({"district": ["Gurdaspur"], "area_ha": [356_900.0]})
    with pytest.raises(ValueError, match="Firozpur"):
        flooded_fraction(df, areas)


from sailaab.stats import crop_value_at_risk


def test_crop_value_at_risk_order_of_magnitude():
    # 150,000 ha * 6.5 t/ha * ₹23,200/t ≈ ₹2.26e10 (₹2,262 crore)
    v = crop_value_at_risk(ha=150_000)
    assert v == pytest.approx(150_000 * 6.5 * 23_200)


def test_crop_value_custom_yield():
    assert (
        crop_value_at_risk(ha=100, yield_t_per_ha=5, price_per_t=20_000)
        == 100 * 5 * 20_000
    )
