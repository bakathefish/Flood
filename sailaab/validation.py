# sailaab/validation.py
"""Binary agreement metrics for flood-mask comparison."""

import numpy as np


def binary_metrics(pred: np.ndarray, ref: np.ndarray) -> dict:
    if pred.shape != ref.shape:
        raise ValueError(f"shape mismatch {pred.shape} vs {ref.shape}")
    p = pred.astype(bool).ravel()
    r = ref.astype(bool).ravel()
    tp = int(np.sum(p & r))
    fp = int(np.sum(p & ~r))
    fn = int(np.sum(~p & r))
    tn = int(np.sum(~p & ~r))
    n = tp + fp + fn + tn
    f1_den = 2 * tp + fp + fn
    iou_den = tp + fp + fn
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "oa": (tp + tn) / n if n else float("nan"),
        "f1": 2 * tp / f1_den if f1_den else float("nan"),
        "iou": tp / iou_den if iou_den else float("nan"),
    }
