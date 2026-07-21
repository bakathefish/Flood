# tests/test_gfm.py
import numpy as np
import pytest

from sailaab.gfm import (
    FLOOD_RGB,
    REF_WATER_RGB,
    color_mask,
    flood_mask,
    ref_water_mask,
    union_masks,
    subtract_mask,
    tile_offsets,
    tile_bounds,
    paste_tile,
    web_mercator_area_km2,
)


def _rgba(pixels):
    """pixels: 2D list of (r,g,b,a) tuples -> uint8 array (H,W,4)."""
    return np.array(pixels, dtype=np.uint8)


# --- colour decode -----------------------------------------------------------


def test_flood_mask_selects_pink_only():
    # One solid flood pixel, plus every known artifact colour from the GFM
    # observed-flood-extent group layer (swath outline red, timestamp orange,
    # minor green, reference-water blue) which must all be rejected.
    img = _rgba(
        [
            [FLOOD_RGB + (255,), (192, 0, 0, 255), (255, 118, 13, 255)],
            [(112, 173, 71, 255), REF_WATER_RGB + (255,), (0, 0, 0, 0)],
        ]
    )
    m = flood_mask(img)
    assert m.shape == (2, 3)
    assert m[0, 0]  # pink flood
    assert not m[0, 1]  # red outline
    assert not m[0, 2]  # orange timestamp
    assert not m[1, 0]  # green minor class
    assert not m[1, 1]  # blue reference water
    assert not m[1, 2]  # fully transparent
    assert m.sum() == 1


def test_flood_mask_tolerates_antialiased_pink():
    # Edge-blended pink near the flood colour should still count.
    img = _rgba([[(230, 74, 118, 220)]])
    assert flood_mask(img)[0, 0]


def test_flood_mask_alpha_floor():
    # Correct colour but near-transparent (faint AA halo) is rejected.
    faint = _rgba([[FLOOD_RGB + (10,)]])
    assert not flood_mask(faint)[0, 0]
    assert flood_mask(faint, alpha_min=1)[0, 0]


def test_ref_water_mask_selects_blue_only():
    img = _rgba([[REF_WATER_RGB + (255,), FLOOD_RGB + (255,)]])
    m = ref_water_mask(img)
    assert m[0, 0] and not m[0, 1]


def test_color_mask_rejects_non_rgba():
    with pytest.raises(ValueError):
        color_mask(np.zeros((2, 2, 3), np.uint8), FLOOD_RGB)


# --- set algebra -------------------------------------------------------------


def test_union_masks_or():
    a = np.array([[1, 0], [0, 0]], bool)
    b = np.array([[0, 0], [1, 0]], bool)
    u = union_masks([a, b])
    assert u.tolist() == [[True, False], [True, False]]


def test_union_masks_empty_raises():
    with pytest.raises(ValueError):
        union_masks([])


def test_union_masks_shape_mismatch_raises():
    with pytest.raises(ValueError):
        union_masks([np.zeros((2, 2), bool), np.zeros((2, 3), bool)])


def test_subtract_mask_removes_reference_water():
    flood = np.array([[1, 1], [1, 0]], bool)
    water = np.array([[0, 1], [0, 0]], bool)
    out = subtract_mask(flood, water)
    assert out.tolist() == [[True, False], [True, False]]


def test_subtract_mask_shape_mismatch_raises():
    with pytest.raises(ValueError):
        subtract_mask(np.zeros((2, 2), bool), np.zeros((3, 2), bool))


# --- tiling ------------------------------------------------------------------


def test_tile_offsets_single_when_small():
    assert tile_offsets(100, 80, max_tile=2048) == [(0, 0, 100, 80)]


def test_tile_offsets_exact_multiple():
    tiles = tile_offsets(4096, 2048, max_tile=2048)
    assert tiles == [(0, 0, 2048, 2048), (2048, 0, 2048, 2048)]


def test_tile_offsets_ragged_cover_exactly():
    w, h, mt = 3451, 3991, 2048
    tiles = tile_offsets(w, h, max_tile=mt)
    # every tile within the cap
    assert all(tw <= mt and th <= mt for _, _, tw, th in tiles)
    # exact, non-overlapping cover: painted area == w*h and no pixel twice
    canvas = np.zeros((h, w), np.int32)
    for co, ro, tw, th in tiles:
        canvas[ro : ro + th, co : co + tw] += 1
    assert canvas.min() == 1 and canvas.max() == 1
    assert sum(tw * th for _, _, tw, th in tiles) == w * h


def test_tile_offsets_validates():
    with pytest.raises(ValueError):
        tile_offsets(0, 10)
    with pytest.raises(ValueError):
        tile_offsets(10, 10, max_tile=0)


# --- tile world bounds (north-up: row 0 == max y) ----------------------------


def test_tile_bounds_full_grid_is_full_bounds():
    fb = (100.0, 200.0, 500.0, 900.0)
    assert tile_bounds(fb, 40, 70, 0, 0, 40, 70) == pytest.approx(fb)


def test_tile_bounds_northwest_quarter():
    # 2x2 tiling of a 400x800 world into 200x400 pixel tiles.
    fb = (0.0, 0.0, 400.0, 800.0)  # minx,miny,maxx,maxy
    # NW tile: col_off=0,row_off=0,tw=200,th=400 -> x in [0,200], y in [400,800]
    assert tile_bounds(fb, 400, 800, 0, 0, 200, 400) == pytest.approx(
        (0.0, 400.0, 200.0, 800.0)
    )
    # SE tile: col_off=200,row_off=400 -> x in [200,400], y in [0,400]
    assert tile_bounds(fb, 400, 800, 200, 400, 200, 400) == pytest.approx(
        (200.0, 0.0, 400.0, 400.0)
    )


def test_paste_tile_places_block():
    canvas = np.zeros((4, 4), np.uint8)
    tile = np.ones((2, 2), np.uint8)
    paste_tile(canvas, tile, col_off=1, row_off=2)
    expect = np.array(
        [[0, 0, 0, 0], [0, 0, 0, 0], [0, 1, 1, 0], [0, 1, 1, 0]], np.uint8
    )
    assert (canvas == expect).all()


# --- area with Web-Mercator cos^2(lat) correction ----------------------------


def test_area_equator_unit_pixel():
    # 1000 m x 1000 m mercator pixel at the equator = 1 km^2 ground (no distortion).
    mask = np.array([[True]])
    assert web_mercator_area_km2(mask, (0.0, 0.0, 1000.0, 1000.0)) == pytest.approx(
        1.0, rel=1e-4
    )


def test_area_false_is_zero():
    mask = np.zeros((5, 5), bool)
    assert web_mercator_area_km2(mask, (0.0, 0.0, 5000.0, 5000.0)) == 0.0


def test_area_shrinks_with_latitude():
    # Same pixel geometry, higher latitude band -> less ground area (cos^2 < 1).
    eq = web_mercator_area_km2(np.array([[True]]), (0.0, 0.0, 1000.0, 1000.0))
    hi = web_mercator_area_km2(np.array([[True]]), (0.0, 5.0e6, 1000.0, 5.0e6 + 1000.0))
    assert hi < eq


def test_area_matches_cos2_hand_calc():
    # One pixel high in the northern hemisphere; compare to an explicit
    # inverse-Mercator cos^2(lat) computation.
    y0 = 3.6e6
    bounds = (0.0, y0, 1000.0, y0 + 1000.0)
    R = 6378137.0
    yc = y0 + 500.0
    lat = 2.0 * np.arctan(np.exp(yc / R)) - np.pi / 2
    expect = (1000.0 * 1000.0 * np.cos(lat) ** 2) / 1e6
    assert web_mercator_area_km2(np.array([[True]]), bounds) == pytest.approx(
        expect, rel=1e-6
    )
