# Sailaab 04 — Validation & Impact Analytics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Tasks 2–5 need the user (GFM login, QGIS, GEE session).

**Goal:** Independent validation numbers (GFM agreement, NDEM comparison, official-band check) and the impact analytics (crop loss, exposure, ₹ estimate, causal dam-rainfall figure).

**Architecture:** `sailaab/validation.py` holds tested metric math (confusion/OA/F1/IoU on numpy arrays). External references (GFM rasters, NDEM PDF) are compared through small scripts using that module; every comparison is checkpointed in VERIFICATION-LOG.md.

**Tech Stack:** numpy, pandas, matplotlib; QGIS (georeferencer); GFM portal; GEE for the sampling exports.

---

### Task 1: validation.py — metric math (pure, TDD)

**Files:**
- Create: `sailaab/validation.py`
- Test: `tests/test_validation.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_validation.py
import numpy as np
import pytest

from sailaab.validation import binary_metrics


def test_perfect_agreement():
    a = np.array([1, 1, 0, 0])
    m = binary_metrics(pred=a, ref=a)
    assert m["oa"] == 1.0 and m["f1"] == 1.0 and m["iou"] == 1.0


def test_known_confusion():
    # pred: 1,1,1,0,0,0  ref: 1,0,1,0,1,0  -> TP=2 FP=1 FN=1 TN=2
    pred = np.array([1, 1, 1, 0, 0, 0])
    ref = np.array([1, 0, 1, 0, 1, 0])
    m = binary_metrics(pred, ref)
    assert m["oa"] == pytest.approx(4 / 6)
    assert m["f1"] == pytest.approx(2 * 2 / (2 * 2 + 1 + 1))  # 2TP/(2TP+FP+FN)
    assert m["iou"] == pytest.approx(2 / (2 + 1 + 1))
    assert m["tp"] == 2 and m["fp"] == 1 and m["fn"] == 1 and m["tn"] == 2


def test_shape_mismatch_raises():
    with pytest.raises(ValueError):
        binary_metrics(np.array([1]), np.array([1, 0]))
```

- [ ] **Step 2: Run to FAIL** — `python -m pytest tests/test_validation.py -v` → ModuleNotFoundError

- [ ] **Step 3: Minimal implementation**

```python
# sailaab/validation.py
"""Binary agreement metrics for flood-mask comparison."""
import numpy as np


def binary_metrics(pred: np.ndarray, ref: np.ndarray) -> dict:
    if pred.shape != ref.shape:
        raise ValueError(f"shape mismatch {pred.shape} vs {ref.shape}")
    p = pred.astype(bool).ravel()
    r = ref.astype(bool).ravel()
    tp = int(np.sum(p & r)); fp = int(np.sum(p & ~r))
    fn = int(np.sum(~p & r)); tn = int(np.sum(~p & ~r))
    n = tp + fp + fn + tn
    f1_den = 2 * tp + fp + fn
    iou_den = tp + fp + fn
    return {
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "oa": (tp + tn) / n if n else float("nan"),
        "f1": 2 * tp / f1_den if f1_den else float("nan"),
        "iou": tp / iou_den if iou_den else float("nan"),
    }
```

- [ ] **Step 4: Run to PASS** — 3 passed
- [ ] **Step 5: Commit** — `git add sailaab/validation.py tests/test_validation.py && git commit -m "feat: binary agreement metrics"`

---

### Task 2: GFM cross-validation (user + GEE)

**Files:**
- Create: `pipeline/compare_gfm.py` (below), `data/gfm/` (downloaded layers)
- Modify: `docs/VERIFICATION-LOG.md`

- [ ] **Step 1:** Log in to global-flood.emergency.copernicus.eu → download flood-extent output (GeoTIFF/vector) for tiles covering Punjab, dates Aug 27–Sep 5 2025 → `data/gfm/`.
- [ ] **Step 2: Pre-declare (red):** `| ... | GFM agreement | OA ≥ 0.90 and IoU(flood) ≥ 0.5 on 5,000 fresh random points | | |` (IoU on the rare class is the stricter, honest number — GFM VV-only differs from us by design).
- [ ] **Step 3: Comparison script** — sample fresh random points (NOT the RF training strata), extract our exported `sailaab_RF_floodmask_2025` GeoTIFF and the GFM raster at those points (rasterio), run `binary_metrics`:

```python
# pipeline/compare_gfm.py
"""Sample-point agreement between Sailaab RF mask and Copernicus GFM."""
import numpy as np
import rasterio
from rasterio.warp import transform as warp_transform

from sailaab.validation import binary_metrics

OURS = "data/sailaab_RF_floodmask_2025.tif"
GFM = "data/gfm/gfm_punjab_20250827_0905.tif"  # adjust to the real filename
N = 5000
RNG = np.random.default_rng(42)


def sample_values(path, xs, ys, src_crs):
    with rasterio.open(path) as ds:
        if ds.crs != src_crs:
            xs, ys = warp_transform(src_crs, ds.crs, xs, ys)
        return np.array([v[0] for v in ds.sample(zip(xs, ys))])


def main():
    with rasterio.open(OURS) as ds:
        b = ds.bounds
        xs = RNG.uniform(b.left, b.right, N)
        ys = RNG.uniform(b.bottom, b.top, N)
        crs = ds.crs
    ours = sample_values(OURS, xs, ys, crs) > 0
    gfm = sample_values(GFM, xs, ys, crs) > 0
    print(binary_metrics(ours, gfm))


if __name__ == "__main__":
    main()
```
(Add `rasterio>=1.3` to requirements.txt in this step.)
- [ ] **Step 4:** Run, record verdict + numbers in the log. FAIL → inspect WHERE disagreement clusters (urban? riverine?) before touching thresholds; document either way in METHOD.md §4.
- [ ] **Step 5: Commit** — `git add pipeline/compare_gfm.py requirements.txt docs/VERIFICATION-LOG.md && git commit -m "feat: GFM cross-validation"` (GFM rasters stay out of git — add `data/gfm/` to .gitignore in this commit).

---

### Task 3: NDEM comparison (user + QGIS, 1 h timebox)

- [ ] **Step 1:** Download the NDEM Kapurthala/Tarn Taran PDF (URL in strategy doc §NDEM) → `docs/ndem/`. Check sibling folders for more 2025 Punjab maps.
- [ ] **Step 2:** QGIS georeferencer: 4–6 GCPs on road/river intersections → GeoTIFF. **If >1 h, STOP** → fallback: same-extent side-by-side PNG (our mask styled identically) → `atlas/ndem_comparison.png`. Either way the output goes in the atlas.
- [ ] **Step 3:** If georeferenced: digitize 100 stratified check points (50 flood / 50 dry per the NDEM map), extract our mask, `binary_metrics`, log with pre-declared band `OA ≥ 0.80` (different dates → looser band, stated).
- [ ] **Step 4: Commit** — `git add docs/ndem atlas/ && git commit -m "feat: NDEM comparison"`

---

### Task 4: Impact tables + ₹ estimate

**Files:**
- Create: `pipeline/impact_tables.py`, `atlas/impact/`
- Test: extend `tests/test_stats.py`

- [ ] **Step 1: Failing test for the ₹ math** (pure function first):

```python
# append to tests/test_stats.py
from sailaab.stats import crop_value_at_risk


def test_crop_value_at_risk_order_of_magnitude():
    # 150,000 ha * 6.5 t/ha * ₹23,200/t ≈ ₹2.26e10 (₹2,262 crore)
    v = crop_value_at_risk(ha=150_000)
    assert v == pytest.approx(150_000 * 6.5 * 23_200)


def test_crop_value_custom_yield():
    assert crop_value_at_risk(ha=100, yield_t_per_ha=5, price_per_t=20_000) == \
        100 * 5 * 20_000
```

- [ ] **Step 2: FAIL run**, then implement:

```python
# append to sailaab/stats.py
PADDY_YIELD_T_PER_HA = 6.5      # Punjab avg (cite in DATA-SOURCES)
PADDY_MSP_PER_T = 23_200        # ≈ MSP 2025 grade-A ₹2,320/quintal


def crop_value_at_risk(ha: float, yield_t_per_ha: float = PADDY_YIELD_T_PER_HA,
                       price_per_t: float = PADDY_MSP_PER_T) -> float:
    """Order-of-magnitude value of flooded paddy. Clearly an estimate —
    label it as such everywhere it is displayed."""
    return ha * yield_t_per_ha * price_per_t
```

- [ ] **Step 3: PASS run, commit** — `git commit -m "feat: crop value-at-risk estimate"`
- [ ] **Step 4: Tables + figures script** — `pipeline/impact_tables.py` reads `data/sailaab_RF_district_stats_2025.csv` via `tidy_district_export`, emits: ranked crop-loss bar chart, district choropleth-ready CSV, statewide totals vs `config.OFFICIAL_CROP_FLOODED_HA_BAND` and `OFFICIAL_POP_AFFECTED` → `atlas/impact/`. Matplotlib, one figure per file, dataviz-skill styling.
- [ ] **Step 5: Commit** — `git add pipeline/impact_tables.py atlas/impact && git commit -m "feat: impact tables and figures"`

---

### Task 5: The causal figure (dam releases × rainfall)

**Files:**
- Create: `pipeline/causal_figure.py`, `data/reservoirs_aug2025.csv`, `atlas/causal_figure.png`

- [ ] **Step 1:** Get reservoir daily levels Aug 1 – Sep 10 2025: AIKosh CWC dataset first; if stale → India-WRIS; last resort → hand-key from CWC bulletins (3 dams × 40 days). Save `data/reservoirs_aug2025.csv` with columns `date,dam,level,unit` + a `source` column.
- [ ] **Step 2:** Rainfall strip: IMERG/CHIRPS daily statewide mean (GEE export) or IMD gridded if downloaded → `data/rainfall_aug2025.csv`.
- [ ] **Step 3:** `pipeline/causal_figure.py`: two-panel figure — top: daily rainfall bars (Aug 22–28 shaded); bottom: three dam-level curves with danger marks (Bhakra 1,680 ft) and release annotations (Aug 26–27, ~2.6 lakh cusecs Sutlej / >2 lakh Ravi). Annotate flood-peak window. Export `atlas/causal_figure.png`.
- [ ] **Step 4: Checkpoint:** figure reviewed by the user against the SANDRP/news numbers cited in the strategy doc (they're secondary sources — mark each annotation's source in a caption footnote).
- [ ] **Step 5: Commit + METHOD.md §4** (validation results verbatim, impact method, estimate caveats) — `git commit -m "feat: causal figure; docs: validation & impact method"`
