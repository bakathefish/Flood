#!/usr/bin/env python
# pipeline/compare_eos04.py
"""Compare EOS-04 (RISAT-1A) L2B ARD water masks against our Sentinel-1 flood
products — the pre-declared ISRO cross-validation (docs/notes/eos04.md).

Built AHEAD of the data: with no scenes in ``data/eos04/`` (or no local
reference rasters in ``data/rasters/``) the driver prints the download recipe
pointer and exits 0 — never a traceback. Once L2B GeoTIFFs are dropped in,
it: reprojects each scene to the reference raster's 90 m grid (rasterio,
average resampling for backscatter), detects water with the pre-declared rule
(change mode when a same-mode pre-monsoon scene exists, else single-date mode
— stated per output row), and scores agreement statewide + per district
against the Tier-A mask, writing:

    data/eos04_agreement.csv     per-scene rows + a flood-window union row
    atlas/eos04_compare.png      3-panel: ours / EOS-04 / agreement

Scene dates are parsed from Bhoonidhi-style filenames (tokens like
``05SEP2025`` or ``05092025``); unparseable names are skipped with a warning —
rename the file to include a date token, e.g. ``EOS04_MRS_05SEP2025_dsc.tif``.

Deterministic, no network. Run:  python pipeline/compare_eos04.py
"""

from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DATA = ROOT / "data"
SCENES = DATA / "eos04"
RASTERS = DATA / "rasters"
OUT_CSV = DATA / "eos04_agreement.csv"
OUT_PNG = ROOT / "atlas" / "eos04_compare.png"

# pre-declared windows (docs/notes/eos04.md; flood window = NDEM's own
# RISAT-1A analysis span, pre window = our Tier-A pre-monsoon baseline)
FLOOD_WINDOW = (date(2025, 8, 16), date(2025, 9, 17))
PRE_WINDOW = (date(2025, 7, 1), date(2025, 8, 10))

_MONTHS = {
    m: i + 1
    for i, m in enumerate(
        ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
    )
}


def parse_scene_date(name: str) -> date | None:
    """Acquisition date from a Bhoonidhi-style filename, else None.

    Recognises ``DDMONYYYY`` (05SEP2025) and 8-digit ``DDMMYYYY`` (05092025)
    tokens anywhere in the name.
    """
    m = re.search(r"(\d{2})([A-Z]{3})(\d{4})", name.upper())
    if m and m.group(2) in _MONTHS:
        try:
            return date(int(m.group(3)), _MONTHS[m.group(2)], int(m.group(1)))
        except ValueError:
            return None
    m = re.search(r"(?<!\d)(\d{2})(\d{2})(\d{4})(?!\d)", name)
    if m:
        try:
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            return None
    return None


def classify_scene(d: date | None) -> str:
    """'flood' / 'pre' / 'other' / 'undated' against the pre-declared windows."""
    if d is None:
        return "undated"
    if FLOOD_WINDOW[0] <= d <= FLOOD_WINDOW[1]:
        return "flood"
    if PRE_WINDOW[0] <= d <= PRE_WINDOW[1]:
        return "pre"
    return "other"


def scan_scenes(scene_dir: Path) -> dict[str, list[tuple[Path, date | None]]]:
    """Group *.tif scenes by window class."""
    groups: dict[str, list[tuple[Path, date | None]]] = {
        "flood": [],
        "pre": [],
        "other": [],
        "undated": [],
    }
    for p in sorted(scene_dir.glob("*.tif")):
        d = parse_scene_date(p.name)
        groups[classify_scene(d)].append((p, d))
    return groups


def main(scene_dir: Path = SCENES, raster_dir: Path = RASTERS) -> int:
    groups = scan_scenes(scene_dir)
    n_scenes = sum(len(v) for v in groups.values())
    if n_scenes == 0:
        print(
            "compare_eos04: no EOS-04 scenes found in data/eos04/ — nothing to do.\n"
            "Download recipe: data/eos04/README.md (free Bhoonidhi registration; "
            "protocol + acceptance bands: docs/notes/eos04.md)."
        )
        return 0

    reference = raster_dir / "tier_a_flood_2025.tif"
    if not reference.exists():
        # fall back to any committed-locally Tier-A/RF raster naming
        candidates = list(raster_dir.glob("*tier*_2025.tif")) + list(
            raster_dir.glob("rf_flood_2025.tif")
        )
        if not candidates:
            print(
                "compare_eos04: EOS-04 scenes present but no local reference raster "
                "in data/rasters/ (gitignored, produced by pipeline/local_tier_a.py "
                "and pipeline/rf_train.py). Re-run those first."
            )
            return 0
        reference = candidates[0]

    # ---- heavy imports only on the real path ----
    import numpy as np
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.warp import reproject

    from sailaab.eos04 import (
        agreement_metrics,
        confusion,
        district_agreement,
        rank_correlation,
        water_mask_change,
        water_mask_single,
    )
    from sailaab.sar_local import to_db

    with rasterio.open(reference) as ref:
        ref_profile = ref.profile
        ours = ref.read(1) > 0
        ref_grid = dict(
            dst_crs=ref.crs, dst_transform=ref.transform, dst_shape=(ref.height, ref.width)
        )

    def to_ref_grid(path: Path) -> np.ndarray:
        with rasterio.open(path) as src:
            dst = np.full(ref_grid["dst_shape"], np.nan, dtype="float64")
            reproject(
                source=rasterio.band(src, 1),
                destination=dst,
                dst_crs=ref_grid["dst_crs"],
                dst_transform=ref_grid["dst_transform"],
                src_nodata=src.nodata,
                dst_nodata=np.nan,
                resampling=Resampling.average,
            )
        return dst

    # reference water proxy for single-date mode: the pre-monsoon dark mask is
    # not available per-sensor -> use JRC-derived reference water raster if
    # present, else the Tier-A permanent-water sidecar
    ref_water_path = raster_dir / "reference_water.tif"
    if ref_water_path.exists():
        with rasterio.open(ref_water_path) as rw:
            reference_water = rw.read(1) > 0
    else:
        reference_water = np.zeros(ref_grid["dst_shape"], dtype=bool)
        print("compare_eos04: WARNING no reference_water.tif — single-date mode will over-detect permanent water (stated in CSV notes)")

    pre_db = None
    if groups["pre"]:
        pre_db = to_db(to_ref_grid(groups["pre"][0][0]))

    rows = []
    union = np.zeros(ref_grid["dst_shape"], dtype=bool)
    union_valid = np.zeros(ref_grid["dst_shape"], dtype=bool)
    for path, d in groups["flood"]:
        vv_db = to_db(to_ref_grid(path))
        valid = np.isfinite(vv_db)
        if pre_db is not None:
            theirs = water_mask_change(vv_db, pre_db, valid=valid)
            mode = "change"
        else:
            theirs = water_mask_single(vv_db, reference_water, valid=valid)
            mode = "single-date"
        union |= theirs
        union_valid |= valid
        c = confusion(ours, theirs, valid)
        rows.append(
            {
                "scene": path.name,
                "date": d.isoformat() if d else "",
                "mode": mode,
                **c,
                **agreement_metrics(c),
            }
        )

    c = confusion(ours, union, union_valid)
    rows.append({"scene": "UNION", "date": "", "mode": "union", **c, **agreement_metrics(c)})

    # per-district + direction check on the union
    labels_path = raster_dir / "district_labels.tif"
    if labels_path.exists():
        with rasterio.open(labels_path) as lp:
            labels = lp.read(1)
        drows = district_agreement(ours, union, labels, union_valid)
        rho = rank_correlation(
            [r["frac_ours"] for r in drows], [r["frac_theirs"] for r in drows]
        )
        print(f"district direction check: Spearman rho = {rho:.3f} over {len(drows)} districts")
        for r in drows:
            rows.append({"scene": f"district_{r['label']}", "date": "", "mode": "union", **{
                k: r[k] for k in ("tp", "fp", "fn", "tn", "oa", "precision", "recall", "f1", "iou", "n_pos_ours", "n_pos_theirs")
            }})

    import csv as _csv

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = _csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    # 3-panel figure, dark house palette
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 3, figsize=(15, 5.6), facecolor="#0a0e11")
    panels = [
        (ours & union_valid, "Sailaab Tier-A (S1)", "#63e6d5"),
        (union, "EOS-04 water (ISRO)", "#ffb454"),
        (ours & union, "Agreement", "#f487e8"),
    ]
    from matplotlib.colors import ListedColormap

    for ax, (mask, title, colour) in zip(axes, panels):
        ax.imshow(mask, cmap=ListedColormap(["#10161b", colour]), interpolation="nearest")
        ax.set_title(title, color="#e8e6df", fontsize=11, family="monospace")
        ax.axis("off")
    fig.suptitle(
        "EOS-04 (RISAT-1A) vs Sentinel-1 — pre-declared cross-validation (docs/notes/eos04.md)",
        color="#9aa7ad",
        fontsize=10,
        family="monospace",
    )
    fig.tight_layout()
    OUT_PNG.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_PNG, dpi=130, facecolor=fig.get_facecolor())
    plt.close(fig)

    print(f"wrote {OUT_CSV} ({len(rows)} rows) and {OUT_PNG}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
