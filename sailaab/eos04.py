# sailaab/eos04.py
"""EOS-04 (RISAT-1A) cross-validation — pure comparison logic.

Protocol pre-declared in ``docs/notes/eos04.md``: detect water on EOS-04 L2B
gamma0 with the SAME physics as our Sentinel-1 products (thresholds from
``sailaab.config``; change mode == the exact Tier-A rule via
``sailaab.sar_local.tier_a_mask``), then score pixel agreement over co-valid
pixels, statewide and per district. numpy only; all raster IO lives in
``pipeline/compare_eos04.py``.
"""

from __future__ import annotations

import numpy as np

from sailaab.config import ABS_VV_THRESHOLD_DB, DIFF_THRESHOLD_DB
from sailaab.sar_local import tier_a_mask


def water_mask_single(
    vv_db,
    reference_water,
    valid=None,
    abs_thresh: float = ABS_VV_THRESHOLD_DB,
) -> np.ndarray:
    """Single-date fallback mode: dark now, not permanent water.

    ``water = (VV < abs_thresh) & ~reference_water`` — used when no usable
    EOS-04 pre-monsoon scene exists. NaN never counts as water; ``valid``
    (optional bool array) further restricts the mask.
    """
    vv = np.asarray(vv_db, dtype="float64")
    ref = np.asarray(reference_water, dtype=bool)
    m = (vv < abs_thresh) & ~ref
    if valid is not None:
        m &= np.asarray(valid, dtype=bool)
    return m


def water_mask_change(
    vv_flood_db,
    vv_pre_db,
    valid=None,
    diff_thresh: float = DIFF_THRESHOLD_DB,
    abs_thresh: float = ABS_VV_THRESHOLD_DB,
) -> np.ndarray:
    """Change mode: the exact Tier-A rule on an EOS-04 pre/flood pair.

    Thin wrapper over ``sar_local.tier_a_mask`` (drop AND dark-now AND
    not-already-dark), computing dVV internally and honouring ``valid``.
    """
    vf = np.asarray(vv_flood_db, dtype="float64")
    vp = np.asarray(vv_pre_db, dtype="float64")
    m = tier_a_mask(vf - vp, vf, vp, diff_thresh=diff_thresh, abs_thresh=abs_thresh)
    if valid is not None:
        m &= np.asarray(valid, dtype=bool)
    return m


def confusion(ours, theirs, valid) -> dict:
    """TP/FP/FN/TN over co-valid pixels, with ``ours`` as the reference.

    TP = both water; FP = theirs-only; FN = ours-only; TN = both dry.
    """
    a = np.asarray(ours, dtype=bool)
    b = np.asarray(theirs, dtype=bool)
    v = np.asarray(valid, dtype=bool)
    return {
        "tp": int(np.count_nonzero(a & b & v)),
        "fp": int(np.count_nonzero(~a & b & v)),
        "fn": int(np.count_nonzero(a & ~b & v)),
        "tn": int(np.count_nonzero(~a & ~b & v)),
    }


def agreement_metrics(conf: dict) -> dict:
    """OA / precision / recall / F1 / IoU from a confusion dict, zero-safe.

    Zero-denominator cases return 0.0; ``n_pos_*`` fields let the caller tell
    "perfect" apart from "nothing to score".
    """
    tp, fp, fn, tn = conf["tp"], conf["fp"], conf["fn"], conf["tn"]
    n = tp + fp + fn + tn

    def _safe(num, den):
        return float(num / den) if den else 0.0

    p = _safe(tp, tp + fp)
    r = _safe(tp, tp + fn)
    return {
        "oa": _safe(tp + tn, n) if n else 0.0,
        "precision": p,
        "recall": r,
        "f1": _safe(2 * p * r, p + r),
        "iou": _safe(tp, tp + fp + fn),
        "n_pos_ours": tp + fn,
        "n_pos_theirs": tp + fp,
    }


def district_agreement(ours, theirs, labels, valid) -> list[dict]:
    """Per-district rows over a positive-integer label raster (0 = background).

    Each row: ``label``, the confusion counts, the agreement metrics, and the
    flood fractions of each mask over the district's valid pixels.
    """
    lab = np.asarray(labels)
    v = np.asarray(valid, dtype=bool)
    rows = []
    for label in np.unique(lab[lab > 0]):
        in_d = (lab == label) & v
        c = confusion(ours, theirs, in_d)
        n_valid = int(np.count_nonzero(in_d))
        row = {"label": int(label), "n_valid": n_valid, **c, **agreement_metrics(c)}
        row["frac_ours"] = (c["tp"] + c["fn"]) / n_valid if n_valid else 0.0
        row["frac_theirs"] = (c["tp"] + c["fp"]) / n_valid if n_valid else 0.0
        rows.append(row)
    return rows


def _ranks(x: np.ndarray) -> np.ndarray:
    """Ascending ranks with ties given their average rank (1-based)."""
    order = np.argsort(x, kind="stable")
    ranks = np.empty(len(x), dtype="float64")
    ranks[order] = np.arange(1, len(x) + 1, dtype="float64")
    for value in np.unique(x):
        tie = x == value
        if np.count_nonzero(tie) > 1:
            ranks[tie] = ranks[tie].mean()
    return ranks


def rank_correlation(a, b) -> float:
    """Spearman ρ (Pearson on average-tie ranks). NaN when either side is
    constant (undefined) — the pre-declared direction check treats that as
    not-evaluable, never as agreement."""
    x = np.asarray(a, dtype="float64")
    y = np.asarray(b, dtype="float64")
    rx, ry = _ranks(x), _ranks(y)
    dx, dy = rx - rx.mean(), ry - ry.mean()
    denom = np.sqrt((dx**2).sum() * (dy**2).sum())
    if denom == 0.0:
        return float("nan")
    return float((dx * dy).sum() / denom)
