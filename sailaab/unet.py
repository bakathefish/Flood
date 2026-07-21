# sailaab/unet.py
"""Pure helpers for the Tier-C U-Net flood benchmark.

Everything here is deterministic and unit-tested. The numpy helpers
(``normalize_db``, ``water_metrics``, ``tile_offsets``, ``random_crop_coords``,
``dice_coeff``) carry no torch dependency, so this module imports fine on a
machine without torch. The torch model is built lazily by ``build_unet`` (torch
imported inside the call), mirroring how the rest of ``sailaab`` keeps pure array
logic separate from the heavy IO/framework layer in ``pipeline/``.

Convention (Sen1Floods11): SAR is VV+VH in decibels; labels are ``-1`` no-data
(ignored), ``0`` not-water, ``1`` water.
"""

from __future__ import annotations

import numpy as np

DEFAULT_CLIP = (-35.0, 5.0)  # dB window: kills -inf floors / bright outliers


def normalize_db(x, mean, std, clip=DEFAULT_CLIP):
    """Clip dB then per-channel standardise; non-finite pixels map to 0.

    ``x`` is ``(C, H, W)`` (or ``(H, W)`` for a single channel). ``mean``/``std``
    are per-channel (length ``C``) or scalar. Returns float32 the same shape as
    ``x``. No-data (NaN/inf) becomes 0.0 — i.e. the channel mean after
    standardisation — and never propagates NaN into the network.
    """
    x = np.asarray(x, dtype="float64")
    mean = np.asarray(mean, dtype="float64")
    std = np.asarray(std, dtype="float64")
    finite = np.isfinite(x)
    xc = np.clip(np.where(finite, x, 0.0), clip[0], clip[1])
    if mean.ndim == 1:
        shape = [mean.shape[0]] + [1] * (x.ndim - 1)
        m = mean.reshape(shape)
        s = std.reshape(shape)
    else:
        m, s = mean, std
    out = (xc - m) / s
    out = np.where(finite, out, 0.0)
    return out.astype("float32")


def water_metrics(pred, label, ignore_index: int = -1) -> dict:
    """Water-class confusion metrics, ignoring ``ignore_index`` label pixels.

    ``pred`` is a boolean/0-1 water mask; ``label`` uses the Sen1Floods11
    convention (``-1`` no-data, ``0`` not-water, ``1`` water). Returns tp/fp/fn/tn
    plus IoU, F1, precision, recall and overall accuracy over the valid pixels.
    """
    pred = np.asarray(pred).astype(bool)
    label = np.asarray(label)
    if pred.shape != label.shape:
        raise ValueError(f"shape mismatch {pred.shape} vs {label.shape}")
    valid = label != ignore_index
    p = pred[valid]
    r = label[valid] == 1
    tp = int(np.sum(p & r))
    fp = int(np.sum(p & ~r))
    fn = int(np.sum(~p & r))
    tn = int(np.sum(~p & ~r))
    n = tp + fp + fn + tn
    iou_den = tp + fp + fn
    f1_den = 2 * tp + fp + fn
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "iou": tp / iou_den if iou_den else float("nan"),
        "f1": 2 * tp / f1_den if f1_den else float("nan"),
        "precision": tp / (tp + fp) if (tp + fp) else float("nan"),
        "recall": tp / (tp + fn) if (tp + fn) else float("nan"),
        "oa": (tp + tn) / n if n else float("nan"),
    }


def dice_coeff(pred, target, eps: float = 1.0) -> float:
    """Hard Dice coefficient between two boolean masks (smoothed by ``eps``)."""
    p = np.asarray(pred).astype(bool)
    t = np.asarray(target).astype(bool)
    inter = float(np.sum(p & t))
    return (2.0 * inter + eps) / (float(p.sum()) + float(t.sum()) + eps)


def tile_offsets(height: int, width: int, tile: int, stride: int):
    """Top-left ``(row, col)`` offsets tiling ``height×width`` with ``tile`` windows.

    Windows step by ``stride`` (``stride < tile`` gives overlap). The last window
    in each axis is clamped to ``dim - tile`` so the whole array is covered and no
    window ever runs past the edge. Deterministic row-major order.
    """
    if tile > height or tile > width:
        raise ValueError(f"tile {tile} larger than array {height}x{width}")
    if stride <= 0:
        raise ValueError("stride must be positive")

    def starts(n):
        if n == tile:
            return [0]
        xs = list(range(0, n - tile + 1, stride))
        if xs[-1] != n - tile:
            xs.append(n - tile)
        return xs

    rows, cols = starts(height), starts(width)
    return [(r, c) for r in rows for c in cols]


def random_crop_coords(height: int, width: int, size: int, rng):
    """Random top-left ``(row, col)`` for a ``size×size`` crop, via ``rng``."""
    if size > height or size > width:
        raise ValueError(f"crop {size} larger than array {height}x{width}")
    r = int(rng.integers(0, height - size + 1))
    c = int(rng.integers(0, width - size + 1))
    return r, c


def build_unet(in_ch: int = 2, base: int = 16, depth: int = 4, out_ch: int = 1):
    """Build a small U-Net (``depth`` down/up blocks). torch imported lazily.

    ``base=16, depth=4`` is ~1.9 M params: encoder widths ``[16,32,64,128]``,
    bottleneck ``256``. Input spatial size must be divisible by ``2**depth``.
    """
    import torch
    from torch import nn
    import torch.nn.functional as F

    class DoubleConv(nn.Module):
        def __init__(self, ci, co):
            super().__init__()
            self.net = nn.Sequential(
                nn.Conv2d(ci, co, 3, padding=1, bias=False),
                nn.BatchNorm2d(co),
                nn.ReLU(inplace=True),
                nn.Conv2d(co, co, 3, padding=1, bias=False),
                nn.BatchNorm2d(co),
                nn.ReLU(inplace=True),
            )

        def forward(self, x):
            return self.net(x)

    class UNet(nn.Module):
        def __init__(self, in_ch, base, depth, out_ch):
            super().__init__()
            chs = [base * (2**i) for i in range(depth)]
            self.inc = DoubleConv(in_ch, chs[0])
            self.downs = nn.ModuleList(
                [DoubleConv(chs[i], chs[i + 1]) for i in range(depth - 1)]
            )
            self.pool = nn.MaxPool2d(2)
            self.bottleneck = DoubleConv(chs[-1], chs[-1] * 2)
            dec_in = chs[-1] * 2
            self.upconvs = nn.ModuleList()
            self.decs = nn.ModuleList()
            for c in reversed(chs):
                self.upconvs.append(nn.ConvTranspose2d(dec_in, c, 2, stride=2))
                self.decs.append(DoubleConv(c * 2, c))
                dec_in = c
            self.outc = nn.Conv2d(chs[0], out_ch, 1)

        def forward(self, x):
            skips = []
            x = self.inc(x)
            skips.append(x)
            for down in self.downs:
                x = down(self.pool(x))
                skips.append(x)
            x = self.bottleneck(self.pool(x))
            for upconv, dec, skip in zip(self.upconvs, self.decs, reversed(skips)):
                x = upconv(x)
                if x.shape[-2:] != skip.shape[-2:]:
                    x = F.interpolate(x, size=skip.shape[-2:], mode="nearest")
                x = dec(torch.cat([skip, x], dim=1))
            return self.outc(x)

    return UNet(in_ch, base, depth, out_ch)


def count_params(module) -> int:
    """Total number of trainable parameters in a torch module."""
    return int(sum(p.numel() for p in module.parameters() if p.requires_grad))
