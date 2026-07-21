# tests/test_unet.py
"""Unit tests for the pure helpers behind the Tier-C U-Net benchmark.

The numpy helpers run everywhere; the single torch test skips cleanly when torch
is absent (torch is a user-level install, deliberately not in requirements.txt).
"""

import numpy as np
import pytest

from sailaab.unet import (
    dice_coeff,
    normalize_db,
    random_crop_coords,
    tile_offsets,
    water_metrics,
)


# --- normalize_db ---------------------------------------------------------- #
def test_normalize_db_standardises_per_channel():
    rng = np.random.default_rng(0)
    x = np.stack(
        [rng.normal(-8, 3, (32, 32)), rng.normal(-14, 2, (32, 32))]
    )  # (2,H,W), inside clip window
    mean = x.reshape(2, -1).mean(1)
    std = x.reshape(2, -1).std(1)
    out = normalize_db(x, mean, std, clip=(-60.0, 60.0))
    assert out.shape == x.shape
    assert out.dtype == np.float32
    # each channel is now ~zero-mean / unit-std
    assert np.allclose(out.reshape(2, -1).mean(1), 0, atol=1e-4)
    assert np.allclose(out.reshape(2, -1).std(1), 1, atol=1e-4)


def test_normalize_db_nodata_maps_to_zero():
    x = np.array([[[-8.0, np.nan], [np.inf, -10.0]]])  # (1,2,2)
    out = normalize_db(x, mean=[-9.0], std=[1.0])
    assert out[0, 0, 1] == 0.0  # NaN -> 0
    assert out[0, 1, 0] == 0.0  # inf -> 0
    assert np.isfinite(out).all()
    assert out[0, 0, 0] == pytest.approx(1.0)  # (-8 - -9)/1


def test_normalize_db_clips_before_scaling():
    x = np.array([[[100.0, -100.0]]])  # both outside default clip window
    out = normalize_db(x, mean=[0.0], std=[1.0])  # clip (-35, 5)
    assert out[0, 0, 0] == pytest.approx(5.0)
    assert out[0, 0, 1] == pytest.approx(-35.0)


# --- water_metrics --------------------------------------------------------- #
def test_water_metrics_perfect_prediction():
    label = np.array([[1, 0, -1], [1, 0, 0]])
    pred = np.array([[1, 0, 1], [1, 0, 0]], dtype=bool)  # the -1 pixel is ignored
    m = water_metrics(pred, label)
    assert m["iou"] == 1.0
    assert m["f1"] == 1.0
    assert m["precision"] == 1.0 and m["recall"] == 1.0
    assert m["tp"] == 2 and m["fp"] == 0 and m["fn"] == 0


def test_water_metrics_ignores_masked_pixels():
    # every real disagreement is hidden behind ignore_index -> perfect score
    label = np.array([[-1, -1], [1, 0]])
    pred = np.array([[1, 1], [1, 0]], dtype=bool)
    m = water_metrics(pred, label)
    assert m["tp"] == 1 and m["fp"] == 0 and m["fn"] == 0
    assert m["iou"] == 1.0


def test_water_metrics_precision_recall():
    label = np.array([1, 1, 1, 0, 0])
    pred = np.array([1, 1, 0, 1, 0], dtype=bool)  # tp=2 fp=1 fn=1 tn=1
    m = water_metrics(pred, label)
    assert m["tp"] == 2 and m["fp"] == 1 and m["fn"] == 1 and m["tn"] == 1
    assert m["precision"] == pytest.approx(2 / 3)
    assert m["recall"] == pytest.approx(2 / 3)
    assert m["iou"] == pytest.approx(2 / 4)


def test_water_metrics_shape_mismatch_raises():
    with pytest.raises(ValueError):
        water_metrics(np.zeros((2, 2), bool), np.zeros((3, 3), int))


# --- dice_coeff ------------------------------------------------------------ #
def test_dice_coeff_identical_and_disjoint():
    a = np.array([[1, 1], [0, 0]], bool)
    assert dice_coeff(a, a, eps=0.0) == pytest.approx(1.0)
    b = ~a
    assert dice_coeff(a, b, eps=0.0) == pytest.approx(0.0)


# --- tile_offsets ---------------------------------------------------------- #
def test_tile_offsets_cover_every_pixel_with_overlap():
    H, W, tile, stride = 100, 90, 40, 32
    offs = tile_offsets(H, W, tile, stride)
    covered = np.zeros((H, W), bool)
    for r, c in offs:
        assert 0 <= r <= H - tile and 0 <= c <= W - tile  # never past edge
        covered[r : r + tile, c : c + tile] = True
    assert covered.all()  # full coverage incl. the clamped edge tiles


def test_tile_offsets_exact_fit_single_tile():
    assert tile_offsets(64, 64, 64, 64) == [(0, 0)]


def test_tile_offsets_rejects_oversized_tile():
    with pytest.raises(ValueError):
        tile_offsets(32, 32, 64, 32)


# --- random_crop_coords ---------------------------------------------------- #
def test_random_crop_coords_within_bounds_and_deterministic():
    r1 = random_crop_coords(512, 512, 256, np.random.default_rng(1))
    r2 = random_crop_coords(512, 512, 256, np.random.default_rng(1))
    assert r1 == r2  # same seed -> same crop
    r, c = r1
    assert 0 <= r <= 256 and 0 <= c <= 256


def test_random_crop_coords_rejects_oversized():
    with pytest.raises(ValueError):
        random_crop_coords(128, 128, 256, np.random.default_rng(0))


# --- torch model (skips cleanly without torch) ----------------------------- #
def test_build_unet_forward_shape_and_size():
    torch = pytest.importorskip("torch")
    from sailaab.unet import build_unet, count_params

    torch.manual_seed(0)
    net = build_unet(in_ch=2, base=16, depth=4, out_ch=1).eval()
    n = count_params(net)
    assert 1_000_000 < n < 3_000_000  # small U-Net, ~1.9M params
    with torch.no_grad():
        y = net(torch.zeros(2, 2, 256, 256))
    assert tuple(y.shape) == (2, 1, 256, 256)
