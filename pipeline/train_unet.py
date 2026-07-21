# pipeline/train_unet.py
"""Tier-C benchmark: train a small CPU U-Net on Sen1Floods11 hand-labeled chips.

Deterministic, CPU-only, timeboxed. Pure array/model logic lives in
``sailaab.unet`` (unit-tested); this is the IO / torch orchestration, mirroring
the other ``pipeline/*.py`` runners.

Data: Sen1Floods11 v1.1 ``flood_events/HandLabeled`` chips (VV+VH dB, 512x512;
labels -1 no-data / 0 not-water / 1 water). Downloaded from the public keyless
GCS bucket into ``--data-dir`` (S1Hand/ + LabelHand/ + flood_{train,valid,test}
_data.csv split lists).

torch is a user-level install (CPU wheels: ``pip install torch --index-url
https://download.pytorch.org/whl/cpu``), deliberately NOT in requirements.txt.

Run:  python -m pipeline.train_unet --data-dir <dir> [--epochs 40] [--max-hours 4.5]
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import time
from pathlib import Path

import numpy as np
import rasterio

from sailaab.unet import (
    build_unet,
    count_params,
    normalize_db,
    random_crop_coords,
    water_metrics,
)

CLIP = (-35.0, 5.0)
SEED = 42
CROP = 256
BATCH = 8
EVAL_BATCH = 4
LR = 1e-3
POS_WEIGHT = 2.0  # mild positive weighting; Dice already handles imbalance
PATIENCE = 4
DEFAULT_DATA_DIR = Path(
    "C:/Users/rudra/AppData/Local/Temp/claude/"
    "C--Users-rudra-OneDrive-Desktop-d/720623cf-3d92-4140-9645-d2526c85c313/"
    "scratchpad/sen1floods11"
)
MODEL_OUT = Path("data/models/unet_sen1floods11.pt")
NOTES = Path("docs/notes/unet.md")
SCRATCH = Path(
    "C:/Users/rudra/AppData/Local/Temp/claude/"
    "C--Users-rudra-OneDrive-Desktop-d/720623cf-3d92-4140-9645-d2526c85c313/scratchpad"
)


def _seed_everything(seed=SEED):
    import torch

    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def _read_split(data_dir: Path, split: str):
    with open(data_dir / f"flood_{split}_data.csv") as fh:
        return [(r[0].strip(), r[1].strip()) for r in csv.reader(fh) if len(r) == 2]


def _read_chip(data_dir: Path, s1: str, lab: str):
    with rasterio.open(data_dir / "S1Hand" / s1) as ds:
        x = ds.read().astype("float64")  # (2, 512, 512) dB
    with rasterio.open(data_dir / "LabelHand" / lab) as ds:
        y = ds.read(1).astype("int16")  # (512, 512) in {-1,0,1}
    return x, y


def _compute_norm_stats(data_dir: Path, train):
    """Per-channel clipped-dB mean/std over the training chips (deterministic)."""
    sums = np.zeros(2)
    sqs = np.zeros(2)
    cnt = np.zeros(2)
    for s1, lab in train:
        x, _ = _read_chip(data_dir, s1, lab)
        for b in range(2):
            v = x[b][np.isfinite(x[b])]
            v = np.clip(v, CLIP[0], CLIP[1])
            sums[b] += v.sum()
            sqs[b] += (v * v).sum()
            cnt[b] += v.size
    mean = sums / cnt
    std = np.sqrt(np.maximum(sqs / cnt - mean**2, 1e-6))
    return mean, std


def _to_tensor_batch(items, data_dir, mean, std, crop=None, rng=None, augment=False):
    """Assemble (X, target, mask) tensors for a list of (s1,lab) chip names.

    With ``augment=True`` (training only) each crop gets a seeded random rot90
    (k in 0..3) plus horizontal flip, applied identically to image and label.
    """
    import torch

    xs, ts, ms = [], [], []
    for s1, lab in items:
        x, y = _read_chip(data_dir, s1, lab)
        if crop is not None:
            r, c = random_crop_coords(x.shape[1], x.shape[2], crop, rng)
            x = x[:, r : r + crop, c : c + crop]
            y = y[r : r + crop, c : c + crop]
        if augment:
            k = int(rng.integers(0, 4))
            if k:
                x = np.rot90(x, k, axes=(1, 2))
                y = np.rot90(y, k, axes=(0, 1))
            if int(rng.integers(0, 2)):
                x = x[:, :, ::-1]
                y = y[:, ::-1]
            x = np.ascontiguousarray(x)
            y = np.ascontiguousarray(y)
        xn = normalize_db(x, mean, std, clip=CLIP)  # (2,H,W) float32
        xs.append(torch.from_numpy(xn))
        ts.append(torch.from_numpy((y == 1).astype("float32"))[None])
        ms.append(torch.from_numpy((y != -1).astype("float32"))[None])
    return torch.stack(xs), torch.stack(ts), torch.stack(ms)


def _masked_bce_dice(logits, target, mask, pos_weight):
    import torch
    import torch.nn.functional as F

    bce = F.binary_cross_entropy_with_logits(
        logits, target, pos_weight=pos_weight, reduction="none"
    )
    bce = (bce * mask).sum() / mask.sum().clamp(min=1.0)
    prob = torch.sigmoid(logits)
    p = prob * mask
    t = target * mask
    inter = (p * t).sum(dim=(1, 2, 3))
    denom = p.sum(dim=(1, 2, 3)) + t.sum(dim=(1, 2, 3))
    dice = 1.0 - (2.0 * inter + 1.0) / (denom + 1.0)
    return bce + dice.mean()


@np.errstate(all="ignore")
def _evaluate(net, items, data_dir, mean, std):
    """Micro-averaged water IoU/F1 over full 512 chips (masking -1)."""
    import torch

    tp = fp = fn = tn = 0
    net.eval()
    with torch.no_grad():
        for i in range(0, len(items), EVAL_BATCH):
            batch = items[i : i + EVAL_BATCH]
            X, _, _ = _to_tensor_batch(batch, data_dir, mean, std)
            logits = net(X)
            preds = (torch.sigmoid(logits) > 0.5).numpy()[:, 0]  # (b,H,W)
            for j, (_, lab) in enumerate(batch):
                _, y = _read_chip(data_dir, *batch[j])
                m = water_metrics(preds[j], y)
                tp += m["tp"]
                fp += m["fp"]
                fn += m["fn"]
                tn += m["tn"]
    iou = tp / (tp + fp + fn) if (tp + fp + fn) else float("nan")
    f1 = 2 * tp / (2 * tp + fp + fn) if (2 * tp + fp + fn) else float("nan")
    prec = tp / (tp + fp) if (tp + fp) else float("nan")
    rec = tp / (tp + fn) if (tp + fn) else float("nan")
    return {
        "iou": iou,
        "f1": f1,
        "precision": prec,
        "recall": rec,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
    }


def _append_note(line: str):
    with open(NOTES, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR))
    ap.add_argument("--epochs", type=int, default=40)
    ap.add_argument("--max-hours", type=float, default=4.5)
    ap.add_argument("--base", type=int, default=16)
    ap.add_argument("--pos-weight", type=float, default=POS_WEIGHT)
    ap.add_argument("--patience", type=int, default=PATIENCE)
    ap.add_argument("--lr", type=float, default=LR)
    ap.add_argument("--no-augment", action="store_true")
    args = ap.parse_args()
    augment = not args.no_augment

    import torch

    torch.set_num_threads(max(1, __import__("os").cpu_count() or 4))
    _seed_everything()
    data_dir = Path(args.data_dir)
    t0 = time.time()
    deadline = t0 + args.max_hours * 3600

    train = _read_split(data_dir, "train")
    valid = _read_split(data_dir, "valid")
    test = _read_split(data_dir, "test")
    print(
        f"[unet] chips train/valid/test = {len(train)}/{len(valid)}/{len(test)}",
        flush=True,
    )

    mean, std = _compute_norm_stats(data_dir, train)
    print(
        f"[unet] norm mean={np.round(mean, 3).tolist()} std={np.round(std, 3).tolist()} "
        f"(clip {CLIP}, +{time.time() - t0:.0f}s)",
        flush=True,
    )

    net = build_unet(in_ch=2, base=args.base, depth=4, out_ch=1)
    nparam = count_params(net)
    print(f"[unet] params = {nparam:,}", flush=True)
    opt = torch.optim.Adam(net.parameters(), lr=args.lr)
    pos_weight = torch.tensor([args.pos_weight])

    _append_note("")
    _append_note(
        f"Model: base={args.base} depth=4 params={nparam:,}; "
        f"norm clip {CLIP} mean={np.round(mean, 3).tolist()} std={np.round(std, 3).tolist()}; "
        f"loss BCE(pos_weight={args.pos_weight})+Dice; Adam {args.lr}; batch {BATCH}; "
        f"crop {CROP}; augment={augment}; patience {args.patience}; seed {SEED}."
    )
    _append_note("")
    _append_note(
        "| epoch | train_loss | valid_IoU | valid_F1 | valid_P | valid_R | sec |"
    )
    _append_note(
        "|------:|-----------:|----------:|---------:|--------:|--------:|----:|"
    )

    rng = np.random.default_rng(SEED)
    order_rng = random.Random(SEED)
    best_iou = -1.0
    best_state = None
    best_epoch = -1
    since_improve = 0
    history = []

    for epoch in range(1, args.epochs + 1):
        te = time.time()
        net.train()
        items = list(train)
        order_rng.shuffle(items)
        losses = []
        for i in range(0, len(items), BATCH):
            batch = items[i : i + BATCH]
            X, target, mask = _to_tensor_batch(
                batch, data_dir, mean, std, crop=CROP, rng=rng, augment=augment
            )
            opt.zero_grad()
            logits = net(X)
            loss = _masked_bce_dice(logits, target, mask, pos_weight)
            loss.backward()
            opt.step()
            losses.append(float(loss.detach()))
        tl = float(np.mean(losses))
        vm = _evaluate(net, valid, data_dir, mean, std)
        dt = time.time() - te
        history.append(
            {
                "epoch": epoch,
                "train_loss": tl,
                **{f"valid_{k}": vm[k] for k in ("iou", "f1", "precision", "recall")},
                "sec": round(dt, 1),
            }
        )
        print(
            f"[unet] epoch {epoch:2d} loss={tl:.4f} valid IoU={vm['iou']:.4f} "
            f"F1={vm['f1']:.4f} P={vm['precision']:.3f} R={vm['recall']:.3f} ({dt:.0f}s)",
            flush=True,
        )
        _append_note(
            f"| {epoch} | {tl:.4f} | {vm['iou']:.4f} | {vm['f1']:.4f} | "
            f"{vm['precision']:.3f} | {vm['recall']:.3f} | {dt:.0f} |"
        )

        if vm["iou"] > best_iou + 1e-4:
            best_iou = vm["iou"]
            best_epoch = epoch
            best_state = {k: v.detach().clone() for k, v in net.state_dict().items()}
            since_improve = 0
        else:
            since_improve += 1
            if since_improve >= args.patience:
                print(
                    f"[unet] early stop: no valid-IoU gain in {args.patience} epochs",
                    flush=True,
                )
                break
        if time.time() > deadline:
            print(
                f"[unet] wall-clock guard hit ({args.max_hours} h) — stopping",
                flush=True,
            )
            break
        # checkpoint interim results each epoch (restartable / observable)
        json.dump(
            {"history": history, "best_epoch": best_epoch, "best_valid_iou": best_iou},
            open(SCRATCH / "unet_train_progress.json", "w"),
            indent=2,
        )

    # --- restore best, evaluate on TEST --------------------------------------
    if best_state is not None:
        net.load_state_dict(best_state)
    test_m = _evaluate(net, test, data_dir, mean, std)
    print(
        f"[unet] BEST epoch {best_epoch} valid IoU={best_iou:.4f} | "
        f"TEST IoU={test_m['iou']:.4f} F1={test_m['f1']:.4f} "
        f"P={test_m['precision']:.3f} R={test_m['recall']:.3f}",
        flush=True,
    )

    # --- save checkpoint ------------------------------------------------------
    MODEL_OUT.parent.mkdir(parents=True, exist_ok=True)
    ckpt = {
        "state_dict": net.state_dict(),
        "arch": {"in_ch": 2, "base": args.base, "depth": 4, "out_ch": 1},
        "norm": {"clip": list(CLIP), "mean": mean.tolist(), "std": std.tolist()},
        "metrics": {
            "best_epoch": best_epoch,
            "valid": {"iou": best_iou},
            "test": test_m,
        },
        "n_params": nparam,
        "seed": SEED,
    }
    torch.save(ckpt, MODEL_OUT)
    size_mb = MODEL_OUT.stat().st_size / 1e6
    print(f"[unet] saved {MODEL_OUT} ({size_mb:.2f} MB)", flush=True)

    results = {
        "counts": {"train": len(train), "valid": len(valid), "test": len(test)},
        "n_params": nparam,
        "norm": ckpt["norm"],
        "best_epoch": best_epoch,
        "epochs_run": len(history),
        "valid_best_iou": best_iou,
        "test": test_m,
        "model_mb": round(size_mb, 2),
        "runtime_s": round(time.time() - t0, 1),
        "history": history,
    }
    json.dump(results, open(SCRATCH / "unet_results.json", "w"), indent=2)

    _append_note("")
    _append_note(
        f"**Best epoch {best_epoch}** (valid IoU {best_iou:.4f}); "
        f"epochs run {len(history)}; model {size_mb:.2f} MB; "
        f"runtime {results['runtime_s']:.0f}s."
    )
    _append_note(
        f"**Sen1Floods11 TEST:** IoU **{test_m['iou']:.4f}**, F1 **{test_m['f1']:.4f}**, "
        f"precision {test_m['precision']:.3f}, recall {test_m['recall']:.3f} "
        f"(micro-averaged over {len(test)} chips, -1 masked)."
    )
    print("=== unet train RESULTS ===", flush=True)
    print(
        json.dumps(
            {
                k: results[k]
                for k in (
                    "test",
                    "valid_best_iou",
                    "best_epoch",
                    "epochs_run",
                    "model_mb",
                    "runtime_s",
                )
            },
            indent=2,
        ),
        flush=True,
    )
    return results


if __name__ == "__main__":
    main()
