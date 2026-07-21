# tests/test_exposure.py
import numpy as np
import pytest
from rasterio.transform import from_bounds

from sailaab.exposure import (
    counts_to_density,
    density_to_counts,
    population_in_mask_by_district,
    total_population,
    webmerc_pixel_area_m2,
)


# --------------------------------------------------------------------------- #
# counts <-> density (the head-count-conserving core)
# --------------------------------------------------------------------------- #
def test_counts_density_roundtrip_conserves_sum():
    counts = np.array([[0.0, 2.0, 5.0], [4.0, 6.0, 9.0]])
    area = 1_000_000.0  # equal-area 1 km px
    dens = counts_to_density(counts, area)
    back = density_to_counts(dens, area)
    assert np.allclose(back, counts)
    assert back.sum() == pytest.approx(counts.sum())


def test_density_to_counts_upsample_conserves_total():
    # one 1 km cell of 900 people -> ten-by-ten 100 m cells must still sum to 900
    src_area = 1_000_000.0
    dens = counts_to_density(np.array([[900.0]]), src_area)  # people/m^2
    fine_area = 100.0 * 100.0
    fine = density_to_counts(np.full((10, 10), float(dens[0, 0])), fine_area)
    assert fine.sum() == pytest.approx(900.0)


def test_counts_to_density_scalar_matches_manual():
    dens = counts_to_density(np.array([[1000.0]]), 1_000_000.0)
    assert dens[0, 0] == pytest.approx(1e-3)


def test_counts_to_density_array_area_broadcasts_per_row():
    counts = np.array([[100.0, 100.0], [100.0, 100.0]])
    area = np.array([[1000.0], [2000.0]])  # row-varying (geographic source)
    dens = counts_to_density(counts, area)
    assert dens[0, 0] == pytest.approx(0.1)
    assert dens[1, 0] == pytest.approx(0.05)


def test_counts_to_density_honours_nodata():
    counts = np.array([[-200.0, 5.0]])
    dens = counts_to_density(counts, 1_000_000.0, nodata=-200.0)
    assert dens[0, 0] == 0.0
    assert dens[0, 1] == pytest.approx(5e-6)


def test_counts_to_density_nonfinite_becomes_zero():
    counts = np.array([[np.nan, np.inf, 3.0]])
    dens = counts_to_density(counts, 10.0)
    assert dens[0, 0] == 0.0
    assert dens[0, 1] == 0.0
    assert dens[0, 2] == pytest.approx(0.3)


def test_density_to_counts_ignores_nonfinite():
    counts = density_to_counts(np.array([[np.nan, 0.5]]), 100.0)
    assert counts[0, 0] == 0.0
    assert counts[0, 1] == pytest.approx(50.0)


# --------------------------------------------------------------------------- #
# EPSG:3857 true-ground pixel area (cos^2 lat)
# --------------------------------------------------------------------------- #
def test_webmerc_pixel_area_shrinks_with_latitude():
    # north-up 3857 grid spanning the equator up to ~45N-ish in projected metres
    transform = from_bounds(0.0, 0.0, 300.0, 300.0, 3, 3)  # 100 m px
    area = webmerc_pixel_area_m2(transform, (3, 3))
    assert area.shape == (3, 3)
    # every ground area is <= the projected 100x100 = 10 000 m^2
    assert np.all(area <= 100.0 * 100.0 + 1e-6)
    # rows further north (smaller y, higher row index here since north-up top=300)
    # -> lower latitude near equator bottom is largest; area decreases upward
    assert area[0, 0] < area[2, 0]  # top row (north) smaller than bottom row


def test_webmerc_pixel_area_near_equator_approx_projected():
    # a pixel straddling y=0 has latitude ~0 -> cos^2 ~ 1 -> area ~ projected
    transform = from_bounds(0.0, -50.0, 100.0, 50.0, 1, 1)  # single 100 m px at equator
    area = webmerc_pixel_area_m2(transform, (1, 1))
    assert area[0, 0] == pytest.approx(100.0 * 100.0, rel=1e-4)


def test_webmerc_pixel_area_matches_gfm_area_helper():
    # cross-check against the established sailaab.gfm.web_mercator_area_km2 physics
    from sailaab.gfm import web_mercator_area_km2

    bounds = (8_220_944.0, 3_443_277.0, 8_566_034.0, 3_842_330.0)  # Punjab 3857 box
    nrows, ncols = 40, 35
    transform = from_bounds(*bounds, ncols, nrows)
    area = webmerc_pixel_area_m2(transform, (nrows, ncols))
    total_km2 = area.sum() / 1e6
    ref_km2 = web_mercator_area_km2(np.ones((nrows, ncols), bool), bounds)
    assert total_km2 == pytest.approx(ref_km2, rel=1e-6)


# --------------------------------------------------------------------------- #
# mask-sum per district
# --------------------------------------------------------------------------- #
def _toy():
    # 2 rows x 4 cols; districts 1 (left half) and 2 (right half)
    labels = np.array([[1, 1, 2, 2], [1, 1, 2, 2]])
    pop = np.array([[10.0, 20.0, 30.0, 40.0], [1.0, 2.0, 3.0, 4.0]])
    mask = np.array([[1, 0, 1, 0], [0, 0, 0, 1]], dtype="uint8")
    return labels, pop, mask


def test_population_in_mask_by_district_counts_only_flooded():
    labels, pop, mask = _toy()
    out = population_in_mask_by_district(pop, labels, mask)
    # district 1 flooded cells: (0,0)=10 only -> 10 ; total = 10+20+1+2 = 33
    assert out[1]["pop_exposed"] == pytest.approx(10.0)
    assert out[1]["pop_total"] == pytest.approx(33.0)
    assert out[1]["exposed_fraction"] == pytest.approx(10.0 / 33.0)
    # district 2 flooded cells: (0,2)=30 and (1,3)=4 -> 34 ; total = 30+40+3+4 = 77
    assert out[2]["pop_exposed"] == pytest.approx(34.0)
    assert out[2]["pop_total"] == pytest.approx(77.0)


def test_population_in_mask_by_district_background_excluded_and_named():
    labels = np.array([[0, 1, 2]])
    pop = np.array([[99.0, 5.0, 7.0]])
    mask = np.array([[1, 1, 0]], dtype="uint8")
    out = population_in_mask_by_district(pop, labels, mask, names=["Aville", "Bpur"])
    assert set(out) == {"Aville", "Bpur"}  # label 0 (the 99 people) dropped
    assert out["Aville"]["pop_exposed"] == pytest.approx(5.0)
    assert out["Bpur"]["pop_exposed"] == 0.0  # present but dry
    assert out["Bpur"]["exposed_fraction"] == 0.0


def test_population_in_mask_by_district_nonfinite_pop_is_zero():
    labels = np.array([[1, 1]])
    pop = np.array([[np.nan, 8.0]])
    mask = np.array([[1, 1]], dtype="uint8")
    out = population_in_mask_by_district(pop, labels, mask)
    assert out[1]["pop_exposed"] == pytest.approx(8.0)
    assert out[1]["pop_total"] == pytest.approx(8.0)


def test_population_in_mask_by_district_nonfinite_mask_never_floods():
    labels = np.array([[1, 1]])
    pop = np.array([[5.0, 8.0]])
    mask = np.array([[np.nan, 1.0]])
    out = population_in_mask_by_district(pop, labels, mask)
    assert out[1]["pop_exposed"] == pytest.approx(8.0)  # nan cell excluded


def test_population_in_mask_zero_population_district_fraction_zero():
    labels = np.array([[1, 1]])
    pop = np.array([[0.0, 0.0]])
    mask = np.array([[1, 1]], dtype="uint8")
    out = population_in_mask_by_district(pop, labels, mask)
    assert out[1]["exposed_fraction"] == 0.0


# --------------------------------------------------------------------------- #
# conservation helper
# --------------------------------------------------------------------------- #
def test_total_population_ignores_nonfinite():
    pop = np.array([[np.nan, 2.0], [3.0, np.inf]])
    assert total_population(pop) == pytest.approx(5.0)


def test_total_population_restricted_to_districts():
    pop = np.array([[10.0, 20.0], [30.0, 40.0]])
    labels = np.array([[0, 1], [1, 0]])  # only the 20 and 30 are inside districts
    assert total_population(pop, labels) == pytest.approx(50.0)


def test_total_population_matches_sum_of_district_totals():
    labels, pop, mask = _toy()
    out = population_in_mask_by_district(pop, labels, mask)
    summed = sum(d["pop_total"] for d in out.values())
    assert summed == pytest.approx(total_population(pop, labels))
