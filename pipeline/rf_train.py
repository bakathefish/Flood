# pipeline/rf_train.py
"""Train + honestly cross-validate the 2025 Punjab Random-Forest flood classifier.

Consumes the canonical-grid rasters written by ``pipeline.rf_build_features`` and
``pipeline.rf_aux_layers``:

    features : rf_vv_flood, rf_vh_flood, rf_dvv, rf_dvh, [rf_slope]
    labels   : local_tierA_punjab_tierA_floodmask (Tier-A) & rf_gfm_union (GFM),
               permanent water = rf_gfm_refwater | (rf_vv_pre < -15 dB)
    context  : rf_cropland (ESA WorldCover 2021 class 40)

Steps: agreement-strata labels -> stratified balanced point sample (committed CSV)
-> honest spatial CV across the Ravi/Beas vs Sutlej basins -> final fit on all
points -> statewide RF flood raster -> independent random-point check vs GFM ->
per-district + crop-flooded stats (committed CSV) -> quicklooks -> joblib model.

Pure array logic is in ``sailaab.rf`` (unit-tested); this is the IO / sklearn
orchestration. Run: ``python -m pipeline.rf_train``.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
from rasterio.warp import transform_geom
from sklearn.ensemble import RandomForestClassifier
import joblib

from pipeline.local_tier_a import AOIS, DST_CRS, target_grid
from sailaab import config
from sailaab.districts import (
    district_fractions,
    fold_of,
    load_districts,
    rasterize_districts,
)
from sailaab.rf import (
    agreement_labels,
    sample_features,
    stratified_balanced_sample,
    xy_from_index,
)
from sailaab.sar_local import flooded_hectares
from sailaab.validation import binary_metrics

RES = 90.0
PX_AREA_M2 = RES * RES
PX_AREA_HA = PX_AREA_M2 / 1e4  # 0.81 ha per 90 m pixel
N_PER_CLASS = 4000
N_TREES = 200
SEED = 42

RASTER_DIR = Path("data/rasters")
MODEL_DIR = Path("data/models")
ATLAS = Path("atlas")
SCRATCH = Path(
    "C:/Users/rudra/AppData/Local/Temp/claude/"
    "C--Users-rudra-OneDrive-Desktop-d/720623cf-3d92-4140-9645-d2526c85c313/scratchpad"
)

BASE_FEATURES = [
    ("VV_flood", "rf_vv_flood.tif"),
    ("VH_flood", "rf_vh_flood.tif"),
    ("dVV", "rf_dvv.tif"),
    ("dVH", "rf_dvh.tif"),
]


def _read(path):
    with rasterio.open(path) as ds:
        arr = ds.read(1).astype("float64")
        nod = ds.nodata
    if nod is not None and not (isinstance(nod, float) and np.isnan(nod)):
        arr[arr == nod] = np.nan
    return arr


def load_layers():
    feats = list(BASE_FEATURES)
    if (RASTER_DIR / "rf_slope.tif").exists():
        feats.append(("slope", "rf_slope.tif"))
        print("[train] slope layer present -> included in feature stack")
    else:
        print("[train] slope layer ABSENT -> proceeding without slope")
    names = [n for n, _ in feats]
    arrays = [_read(RASTER_DIR / f) for _, f in feats]
    layers = {
        "feat_names": names,
        "feat_arrays": arrays,
        "vv_pre": _read(RASTER_DIR / "rf_vv_pre.tif"),
        "tier_a": _read(RASTER_DIR / "local_tierA_punjab_tierA_floodmask.tif") > 0,
        "gfm_union": _read(RASTER_DIR / "rf_gfm_union.tif") > 0,
        "gfm_refwater": _read(RASTER_DIR / "rf_gfm_refwater.tif") > 0,
        "cropland": _read(RASTER_DIR / "rf_cropland.tif") > 0,
    }
    return layers


def district_grid(transform, shape):
    """Rasterize districts (reprojected 4326->UTM) onto the canonical grid."""
    pairs = load_districts(canonicalize=True)  # sorted (name, geom_4326)
    names = [n for n, _ in pairs]
    geoms_utm = [transform_geom("EPSG:4326", DST_CRS, g) for _, g in pairs]
    labels = rasterize_districts(geoms_utm, transform, shape)
    return labels, names


def main():
    t0 = time.time()
    transform, width, height = target_grid(AOIS["punjab"], RES)
    shape = (height, width)
    print(f"[train] canonical grid {width}x{height} @ {RES} m ({DST_CRS})", flush=True)

    L = load_layers()
    feat_names = L["feat_names"]
    feat_arrays = L["feat_arrays"]

    # pixels with every feature finite (RF cannot take NaN)
    feat_valid = np.ones(shape, dtype=bool)
    for a in feat_arrays:
        feat_valid &= np.isfinite(a)

    districts, dnames = district_grid(transform, shape)
    in_punjab = districts > 0

    # --- agreement-strata labels (only where features complete) --------------
    label = agreement_labels(
        L["tier_a"], L["gfm_union"], L["gfm_refwater"], L["vv_pre"], valid=feat_valid
    )
    n_pos = int((label == 1).sum())
    n_neg = int((label == 0).sum())
    print(f"[train] label pixels: flood={n_pos:,} dry={n_neg:,}", flush=True)

    # --- stratified balanced point sample ------------------------------------
    rng = np.random.default_rng(SEED)
    idx = stratified_balanced_sample(label, districts, N_PER_CLASS, rng=rng)
    X = sample_features(feat_arrays, idx)
    y = label.ravel()[idx].astype(int)
    xs, ys = xy_from_index(idx, list(transform)[:6], width)
    pt_district = np.array([dnames[d - 1] for d in districts.ravel()[idx]])
    pt_fold = np.array([fold_of(n) for n in pt_district], dtype=object)

    df = pd.DataFrame({"x": xs, "y": ys, "district": pt_district})
    for k, nm in enumerate(feat_names):
        df[nm] = X[:, k]
    df["label"] = y
    Path("data").mkdir(exist_ok=True)
    df.to_csv("data/rf_training_points_2025.csv", index=False)
    print(
        f"[train] wrote data/rf_training_points_2025.csv "
        f"({len(df)} pts: {int((y == 1).sum())} flood / {int((y == 0).sum())} dry)",
        flush=True,
    )

    # --- honest spatial CV across basins -------------------------------------
    def rf():
        return RandomForestClassifier(
            n_estimators=N_TREES, n_jobs=-1, random_state=SEED
        )

    m_rb = pt_fold == "ravi_beas"
    m_su = pt_fold == "sutlej"
    cv = {}
    for tag, tr, te, desc in [
        ("A", m_rb, m_su, "train Ravi/Beas -> test Sutlej"),
        ("B", m_su, m_rb, "train Sutlej -> test Ravi/Beas"),
    ]:
        clf = rf().fit(X[tr], y[tr])
        pred = clf.predict(X[te])
        met = binary_metrics(pred.astype(bool), y[te].astype(bool))
        met.update(n_train=int(tr.sum()), n_test=int(te.sum()), desc=desc)
        cv[tag] = met
        print(
            f"[cv {tag}] {desc}: OA={met['oa']:.3f} F1={met['f1']:.3f} "
            f"IoU={met['iou']:.3f} (train {met['n_train']}, test {met['n_test']})",
            flush=True,
        )

    # --- final model on all points -------------------------------------------
    final = rf().fit(X, y)
    importances = dict(
        zip(feat_names, [round(float(v), 4) for v in final.feature_importances_])
    )
    print(f"[train] feature importances: {importances}", flush=True)

    # --- statewide prediction -------------------------------------------------
    valid_flat = np.flatnonzero(feat_valid.ravel())
    Xall = sample_features(feat_arrays, valid_flat)
    print(f"[train] predicting {len(valid_flat):,} valid pixels ...", flush=True)
    pred_all = final.predict(Xall).astype(bool)
    rf_flood = np.zeros(shape, dtype=bool)
    rf_flood.ravel()[valid_flat] = pred_all
    rf_flood &= in_punjab  # report inside Punjab districts only

    with rasterio.open(
        RASTER_DIR / "rf_flood_2025.tif",
        "w",
        driver="GTiff",
        height=height,
        width=width,
        count=1,
        dtype="uint8",
        crs=DST_CRS,
        transform=transform,
        nodata=0,
        compress="lzw",
    ) as ds:
        ds.write(rf_flood.astype("uint8"), 1)

    tier_a_in = L["tier_a"] & in_punjab
    tierA_ha = flooded_hectares(tier_a_in, PX_AREA_M2)
    rf_ha = flooded_hectares(rf_flood, PX_AREA_M2)
    gfm_in = L["gfm_union"] & in_punjab
    crop_flood = rf_flood & L["cropland"]
    crop_ha = flooded_hectares(crop_flood, PX_AREA_M2)
    print(
        f"[train] Tier-A={tierA_ha:,.0f} ha  RF={rf_ha:,.0f} ha  "
        f"GFM={flooded_hectares(gfm_in, PX_AREA_M2):,.0f} ha  "
        f"crop-flooded={crop_ha:,.0f} ha",
        flush=True,
    )

    # --- independent check: fresh random points (not training strata) vs GFM --
    rng2 = np.random.default_rng(SEED + 1)
    pool = np.flatnonzero((feat_valid & in_punjab).ravel())
    fresh = np.setdiff1d(pool, idx, assume_unique=False)
    n_fresh = min(5000, len(fresh))
    fidx = rng2.choice(fresh, size=n_fresh, replace=False)
    rf_at = rf_flood.ravel()[fidx]
    gfm_at = L["gfm_union"].ravel()[fidx]
    ind = binary_metrics(rf_at, gfm_at)
    confusion = {
        "rf_flood_gfm_flood": int(np.sum(rf_at & gfm_at)),
        "rf_flood_gfm_dry": int(np.sum(rf_at & ~gfm_at)),
        "rf_dry_gfm_flood": int(np.sum(~rf_at & gfm_at)),
        "rf_dry_gfm_dry": int(np.sum(~rf_at & ~gfm_at)),
    }
    print(
        f"[check] fresh N={n_fresh} RF vs GFM: OA={ind['oa']:.3f} "
        f"F1={ind['f1']:.3f} IoU={ind['iou']:.3f} {confusion}",
        flush=True,
    )

    # --- per-district + crop stats -------------------------------------------
    tierA_d = district_fractions(districts, tier_a_in, PX_AREA_HA, names=dnames)
    rf_d = district_fractions(districts, rf_flood, PX_AREA_HA, names=dnames)
    crop_d = district_fractions(districts, crop_flood, PX_AREA_HA, names=dnames)
    rows = []
    for n in dnames:
        rows.append(
            {
                "district": n,
                "tierA_flooded_ha": round(tierA_d[n]["flooded_ha"], 1),
                "rf_flooded_ha": round(rf_d[n]["flooded_ha"], 1),
                "crop_flooded_ha": round(crop_d[n]["flooded_ha"], 1),
                "fraction": round(rf_d[n]["flooded_fraction"], 5),
            }
        )
    stats = pd.DataFrame(rows).sort_values("rf_flooded_ha", ascending=False)
    stats.to_csv("data/district_flood_stats_2025.csv", index=False)
    top6 = stats.head(6)["district"].tolist()
    print(f"[train] wrote data/district_flood_stats_2025.csv; top6={top6}", flush=True)

    # --- quicklooks -----------------------------------------------------------
    _quicklook_rf(rf_flood, L["gfm_refwater"], districts, ATLAS / "rf_flood_2025.png")
    _quicklook_3panel(
        tier_a_in, rf_flood, gfm_in, ATLAS / "rf_tierA_gfm_compare_2025.png"
    )

    # --- save model -----------------------------------------------------------
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    mpath = MODEL_DIR / "rf_2025.joblib"
    joblib.dump(final, mpath, compress=3)
    msize_mb = mpath.stat().st_size / 1e6

    results = {
        "grid": {"width": width, "height": height, "res_m": RES, "crs": DST_CRS},
        "features": feat_names,
        "label_pixels": {"flood": n_pos, "dry": n_neg},
        "n_points": {
            "total": len(df),
            "flood": int((y == 1).sum()),
            "dry": int((y == 0).sum()),
        },
        "points_by_fold": {
            "ravi_beas": int(m_rb.sum()),
            "sutlej": int(m_su.sum()),
            "other": int((~m_rb & ~m_su).sum()),
        },
        "cv": cv,
        "feature_importances": importances,
        "areas_ha": {
            "tierA": round(tierA_ha, 1),
            "rf": round(rf_ha, 1),
            "gfm": round(flooded_hectares(gfm_in, PX_AREA_M2), 1),
            "crop_flooded": round(crop_ha, 1),
            "rf_vs_tierA_pct": round((rf_ha - tierA_ha) / tierA_ha * 100, 1),
        },
        "independent_check": {"n": n_fresh, **ind, "confusion": confusion},
        "top6_rf_districts": top6,
        "district_stats_top8": stats.head(8).to_dict("records"),
        "model_joblib_mb": round(msize_mb, 2),
        "runtime_s": round(time.time() - t0, 1),
    }
    SCRATCH.mkdir(parents=True, exist_ok=True)
    with open(SCRATCH / "rf_results.json", "w") as fh:
        json.dump(results, fh, indent=2, default=str)
    print("=== rf_train RESULTS ===", flush=True)
    print(json.dumps(results, indent=2, default=str), flush=True)
    return results


# --------------------------------------------------------------------------- #
# Quicklooks (PIL-free, matplotlib; downsampled; kept small)
# --------------------------------------------------------------------------- #
def _orpool(mask, f):
    m = np.asarray(mask, bool)
    h, w = m.shape
    ph, pw = (-h) % f, (-w) % f
    if ph or pw:
        m = np.pad(m, ((0, ph), (0, pw)))
    H, W = m.shape
    return m.reshape(H // f, f, W // f, f).any(axis=(1, 3))


def _edges(labels, f):
    lab = labels[::f, ::f]
    e = np.zeros(lab.shape, bool)
    e[1:, :] |= lab[1:, :] != lab[:-1, :]
    e[:, 1:] |= lab[:, 1:] != lab[:, :-1]
    return e


def _quicklook_rf(rf_flood, refwater, districts, path, max_w=1400):
    f = max(1, int(np.ceil(rf_flood.shape[1] / max_w)))
    fl = _orpool(rf_flood, f)
    wt = _orpool(refwater, f)
    ed = _edges(districts, f)[: fl.shape[0], : fl.shape[1]]
    rgb = np.full((*fl.shape, 3), 245, np.uint8)
    rgb[wt] = (200, 224, 240)
    rgb[ed] = (150, 150, 150)
    rgb[fl] = (0, 90, 200)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(7, 8))
    ax.imshow(rgb)
    ax.set_title("Sailaab RF flood — Punjab 2025 (district boundaries)", fontsize=11)
    ax.axis("off")
    fig.savefig(path, dpi=130, bbox_inches="tight")
    plt.close(fig)


def _quicklook_3panel(tier_a, rf_flood, gfm, path, max_w=900):
    f = max(1, int(np.ceil(rf_flood.shape[1] / max_w)))
    panels = [
        ("Tier-A SAR", _orpool(tier_a, f)),
        ("Sailaab RF", _orpool(rf_flood, f)),
        ("GFM union", _orpool(gfm, f)),
    ]
    fig, axes = plt.subplots(1, 3, figsize=(13, 6))
    for ax, (title, m) in zip(axes, panels):
        rgb = np.full((*m.shape, 3), 245, np.uint8)
        rgb[m] = (0, 90, 200)
        ax.imshow(rgb)
        ax.set_title(title, fontsize=11)
        ax.axis("off")
    fig.suptitle("Punjab 2025 flood extent — Tier-A vs RF vs GFM", fontsize=12)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=110, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()
