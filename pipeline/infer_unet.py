# pipeline/infer_unet.py
"""Tier-C benchmark, part 2: run the Sen1Floods11 U-Net on the Punjab composites.

Loads the checkpoint from ``pipeline.train_unet``, tiles the 90 m statewide VV+VH
dB composites (``data/rasters/rf_vv_flood.tif`` + ``rf_vh_flood.tif``) into
overlapping 256-px windows, runs the net, averages the overlaps, thresholds at
0.5, and restricts to the Punjab district mask (the same region the RF classifier
reports on). Then it builds the honest 3-method benchmark table — threshold
(Tier-A) vs RF vs U-Net — with statewide flooded ha and per-pixel + sample-point
agreement against the GFM reference.

Deterministic, CPU-only. torch is a user-level install (not in requirements.txt).

Run:  python -m pipeline.infer_unet
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from rasterio.warp import transform_geom

from pipeline.local_tier_a import AOIS, DST_CRS, target_grid
from sailaab.districts import load_districts, rasterize_districts
from sailaab.sar_local import flooded_hectares, sieve_mask, tier_a_mask
from sailaab.unet import build_unet, normalize_db, tile_offsets
from sailaab.validation import binary_metrics

RES = 90.0
PX_AREA_M2 = RES * RES  # 8100 m^2 -> 0.81 ha / pixel
TILE = 256
STRIDE = 192  # 64-px overlap
INFER_BATCH = 8
SEED = 42

RASTER_DIR = Path("data/rasters")
MODEL_PATH = Path("data/models/unet_sen1floods11.pt")
CSV_OUT = Path("data/unet_benchmark.csv")
QUICKLOOK = Path("atlas/checks/unet_punjab_quicklook.png")
NOTES = Path("docs/notes/unet.md")
SCRATCH = Path(
    "C:/Users/rudra/AppData/Local/Temp/claude/"
    "C--Users-rudra-OneDrive-Desktop-d/720623cf-3d92-4140-9645-d2526c85c313/scratchpad"
)


def _read(path):
    with rasterio.open(path) as ds:
        arr = ds.read(1).astype("float64")
        nod = ds.nodata
    if nod is not None and not (isinstance(nod, float) and np.isnan(nod)):
        arr[arr == nod] = np.nan
    return arr


def _pr(pred, ref):
    """Precision/recall/IoU/F1 of ``pred`` treating ``ref`` as ground truth."""
    m = binary_metrics(pred, ref)
    tp, fp, fn = m["tp"], m["fp"], m["fn"]
    m["precision"] = tp / (tp + fp) if (tp + fp) else float("nan")
    m["recall"] = tp / (tp + fn) if (tp + fn) else float("nan")
    return m


def in_punjab_mask(transform, shape):
    pairs = load_districts(canonicalize=True)
    geoms_utm = [transform_geom("EPSG:4326", DST_CRS, g) for _, g in pairs]
    return rasterize_districts(geoms_utm, transform, shape) > 0


def infer_water(net, vv, vh, norm, valid):
    """Tile + average overlaps -> per-pixel water probability over the grid."""
    import torch

    H, W = vv.shape
    x = np.stack([vv, vh])  # (2,H,W) dB, NaN nodata
    xn = normalize_db(x, norm["mean"], norm["std"], clip=tuple(norm["clip"]))
    prob_sum = np.zeros((H, W), dtype="float32")
    count = np.zeros((H, W), dtype="float32")
    offs = tile_offsets(H, W, TILE, STRIDE)
    net.eval()
    with torch.no_grad():
        for i in range(0, len(offs), INFER_BATCH):
            chunk = offs[i : i + INFER_BATCH]
            batch = np.stack([xn[:, r : r + TILE, c : c + TILE] for r, c in chunk])
            logits = net(torch.from_numpy(batch))
            probs = torch.sigmoid(logits).numpy()[:, 0]  # (b,TILE,TILE)
            for (r, c), p in zip(chunk, probs):
                prob_sum[r : r + TILE, c : c + TILE] += p
                count[r : r + TILE, c : c + TILE] += 1.0
    prob = np.where(count > 0, prob_sum / np.maximum(count, 1e-6), 0.0)
    prob[~valid] = 0.0
    return prob


# --------------------------------------------------------------------------- #
# Quicklook (matplotlib, downsampled OR-pool; mirrors pipeline.rf_train style)
# --------------------------------------------------------------------------- #
def _orpool(mask, f):
    m = np.asarray(mask, bool)
    h, w = m.shape
    ph, pw = (-h) % f, (-w) % f
    if ph or pw:
        m = np.pad(m, ((0, ph), (0, pw)))
    H, W = m.shape
    return m.reshape(H // f, f, W // f, f).any(axis=(1, 3))


def _quicklook(unet, rf, tier_a, gfm, path, max_w=900):
    f = max(1, int(np.ceil(unet.shape[1] / max_w)))
    panels = [
        ("U-Net (Sen1Floods11)", unet),
        ("RF (Sailaab)", rf),
        ("Threshold (Tier-A)", tier_a),
        ("GFM union (ref)", gfm),
    ]
    fig, axes = plt.subplots(1, 4, figsize=(17, 6))
    for ax, (title, m) in zip(axes, panels):
        mm = _orpool(m, f)
        rgb = np.full((*mm.shape, 3), 245, np.uint8)
        rgb[mm] = (0, 90, 200)
        ax.imshow(rgb)
        ax.set_title(title, fontsize=11)
        ax.axis("off")
    fig.suptitle(
        "Punjab 2025 open-water / flood extent — U-Net vs RF vs Threshold vs GFM "
        "(90 m; U-Net trained on 10 m Sen1Floods11)",
        fontsize=12,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=110, bbox_inches="tight")
    plt.close(fig)


def main():
    t0 = time.time()
    import torch

    torch.manual_seed(SEED)
    np.random.seed(SEED)
    torch.set_num_threads(max(1, __import__("os").cpu_count() or 4))

    ckpt = torch.load(MODEL_PATH, map_location="cpu", weights_only=False)
    net = build_unet(**ckpt["arch"])
    net.load_state_dict(ckpt["state_dict"])
    norm = ckpt["norm"]
    print(
        f"[infer] loaded {MODEL_PATH} (test IoU {ckpt['metrics']['test']['iou']:.4f})",
        flush=True,
    )

    transform, width, height = target_grid(AOIS["punjab"], RES)
    shape = (height, width)
    vv = _read(RASTER_DIR / "rf_vv_flood.tif")
    vh = _read(RASTER_DIR / "rf_vh_flood.tif")
    assert vv.shape == shape, f"{vv.shape} vs {shape}"
    valid = np.isfinite(vv) & np.isfinite(vh)
    in_pj = in_punjab_mask(transform, shape)
    print(
        f"[infer] grid {width}x{height} @ {RES} m; valid {valid.mean():.3f}; "
        f"in-Punjab px {int(in_pj.sum()):,}",
        flush=True,
    )

    prob = infer_water(net, vv, vh, norm, valid)
    unet = (prob >= 0.5) & valid & in_pj
    print(
        f"[infer] U-Net water px in Punjab = {int(unet.sum()):,} "
        f"(+{time.time() - t0:.0f}s)",
        flush=True,
    )

    rf = (_read(RASTER_DIR / "rf_flood_2025.tif") > 0) & in_pj
    # Tier-A is recomputed from the SAME composites via the unit-tested pure
    # functions (sailaab.sar_local) rather than read from the uint8 artifact:
    # the on-disk mask file can be a stale product of an earlier standalone run
    # (observed: 3.2 kha in-district vs the committed 33.9 kha). Recomputation
    # reproduces rf_grid.json's tierA_flooded_ha and the committed district
    # stats exactly.
    vv_pre = _read(RASTER_DIR / "rf_vv_pre.tif")
    tier_a = sieve_mask(tier_a_mask(vv - vv_pre, vv, vv_pre)) & in_pj
    gfm = (_read(RASTER_DIR / "rf_gfm_union.tif") > 0) & in_pj

    methods = {"unet": unet, "rf": rf, "tier_a": tier_a}
    ha = {k: flooded_hectares(v, PX_AREA_M2) for k, v in methods.items()}
    ha["gfm"] = flooded_hectares(gfm, PX_AREA_M2)

    # full-raster agreement vs GFM (in Punjab)
    vs_gfm = {k: _pr(methods[k], gfm) for k in methods}

    # sample-point agreement (fresh random points in valid & in-Punjab)
    rng = np.random.default_rng(SEED + 7)
    pool = np.flatnonzero((valid & in_pj).ravel())
    n_pts = min(5000, len(pool))
    pidx = rng.choice(pool, size=n_pts, replace=False)
    pt = {k: _pr(methods[k].ravel()[pidx], gfm.ravel()[pidx]) for k in methods}
    # U-Net vs the flood-change references too (context)
    unet_vs_rf = _pr(unet, rf)
    unet_vs_tierA = _pr(unet, tier_a)

    # --- benchmark CSV: the 3-method table -----------------------------------
    def _row(method, mask, name, notes):
        g = _pr(mask, gfm)
        return {
            "method": name,
            "statewide_flooded_ha": round(ha[method], 1),
            "px_vs_gfm_precision": round(g["precision"], 4),
            "px_vs_gfm_recall": round(g["recall"], 4),
            "px_vs_gfm_iou": round(g["iou"], 4),
            "px_vs_gfm_f1": round(g["f1"], 4),
            "notes": notes,
        }

    import csv as _csv

    rows = [
        _row(
            "tier_a",
            tier_a,
            "threshold_tierA",
            "UN-SPIDER dVV<-3dB & VV<-15dB change-detection; flood-change (excludes permanent water)",
        ),
        _row(
            "rf",
            rf,
            "random_forest",
            "RF on VV/VH/dVV/dVH(+slope), Tier-A/GFM agreement labels; flood-change",
        ),
        _row(
            "unet",
            unet,
            "unet_sen1floods11",
            f"small U-Net trained on 10m Sen1Floods11 hand-labeled water (test IoU "
            f"{ckpt['metrics']['test']['iou']:.3f}); labels open-water (incl. permanent); "
            f"applied across 10m->90m domain gap",
        ),
    ]
    CSV_OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(CSV_OUT, "w", newline="", encoding="utf-8") as fh:
        w = _csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"[infer] wrote {CSV_OUT}", flush=True)

    _quicklook(unet, rf, tier_a, gfm, QUICKLOOK)
    print(f"[infer] wrote {QUICKLOOK}", flush=True)

    results = {
        "grid": {"width": width, "height": height, "res_m": RES, "crs": DST_CRS},
        "in_punjab_px": int(in_pj.sum()),
        "areas_ha": {k: round(v, 1) for k, v in ha.items()},
        "unet_vs_gfm_fullraster": vs_gfm["unet"],
        "rf_vs_gfm_fullraster": vs_gfm["rf"],
        "tierA_vs_gfm_fullraster": vs_gfm["tier_a"],
        "unet_vs_gfm_points": {"n": n_pts, **pt["unet"]},
        "rf_vs_gfm_points": {"n": n_pts, **pt["rf"]},
        "tierA_vs_gfm_points": {"n": n_pts, **pt["tier_a"]},
        "unet_vs_rf_fullraster": unet_vs_rf,
        "unet_vs_tierA_fullraster": unet_vs_tierA,
        "checkpoint_metrics": ckpt["metrics"],
        "runtime_s": round(time.time() - t0, 1),
    }
    SCRATCH.mkdir(parents=True, exist_ok=True)
    json.dump(
        results, open(SCRATCH / "unet_infer_results.json", "w"), indent=2, default=str
    )
    print("=== infer_unet RESULTS ===", flush=True)
    print(json.dumps(results, indent=2, default=str), flush=True)
    return results


if __name__ == "__main__":
    main()
