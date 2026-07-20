# Sailaab 03 — Decade Batch (Wave 2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Task 3 needs an authenticated EE session.

**Goal:** Flood masks + per-district stats for every monsoon 2015–2025 and the state flood-frequency raster, anchored against NRSC's Sangrur-2023 figure.

**Architecture:** `sailaab/decade.py` holds the pure run-manifest logic (tested). `pipeline/batch_decade.py` becomes a thin CLI: manifest → EE graph per window (same Tier-A logic as gee/02, ported once into `sailaab/ee_graphs.py`) → server-side reduceRegions → Drive CSV exports → frequency raster. The pre-plan draft of `batch_decade.py` is replaced by this plan.

**Tech Stack:** earthengine-api, pandas; depends on plan 02 (config, windows, stats).

---

### Task 1: decade.py — run manifest (pure, TDD)

**Files:**
- Create: `sailaab/decade.py`
- Test: `tests/test_decade.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_decade.py
from sailaab.decade import run_manifest


def test_manifest_covers_all_years_and_windows():
    m = run_manifest([2023, 2025])
    assert {r["year"] for r in m} == {2023, 2025}
    assert all(r["export_name"].startswith("sailaab_decade_") for r in m)
    r0 = [r for r in m if r["year"] == 2023][0]
    assert r0["window"] == ("2023-06-15", "2023-06-25")
    assert r0["pre"] == ("2023-04-01", "2023-05-31")


def test_manifest_export_names_unique():
    m = run_manifest([2015, 2016])
    names = [r["export_name"] for r in m]
    assert len(names) == len(set(names))
```

- [ ] **Step 2: Run to verify FAIL** — `python -m pytest tests/test_decade.py -v` → `ModuleNotFoundError`

- [ ] **Step 3: Minimal implementation**

```python
# sailaab/decade.py
"""Run manifest for the 2015-2025 decade batch (pure logic, no EE)."""
from sailaab import config
from sailaab.windows import monsoon_windows


def run_manifest(years: list[int] | None = None) -> list[dict]:
    years = config.YEARS if years is None else years
    rows = []
    for y in years:
        pre = (f"{y}-{config.PRE_SEASON_MD[0]}", f"{y}-{config.PRE_SEASON_MD[1]}")
        for (w0, w1) in monsoon_windows(y):
            rows.append({
                "year": y, "window": (w0, w1), "pre": pre,
                "export_name": f"sailaab_decade_{y}_{w0.replace('-', '')}",
            })
    return rows
```

- [ ] **Step 4: Run to verify PASS** — `python -m pytest tests/test_decade.py -v` → 2 passed

- [ ] **Step 5: Commit**

```bash
git add sailaab/decade.py tests/test_decade.py
git commit -m "feat: decade run manifest (pure, tested)"
```

---

### Task 2: ee_graphs.py — the one EE-graph module

**Files:**
- Create: `sailaab/ee_graphs.py`
- Test: `tests/test_ee_graphs.py` (marked `ee`, runs only with auth)

- [ ] **Step 1: Write the (gated) smoke test**

```python
# tests/test_ee_graphs.py
import pytest

ee = pytest.importorskip("ee")
pytestmark = pytest.mark.ee  # excluded by default (pytest.ini)


@pytest.fixture(scope="module")
def initialized():
    ee.Initialize()
    return True


def test_punjab_district_count(initialized):
    from sailaab.ee_graphs import punjab_districts
    n = punjab_districts().size().getInfo()
    assert 18 <= n <= 23


def test_flood_mask_graph_builds(initialized):
    from sailaab.ee_graphs import flood_mask_for_window, punjab_districts
    aoi = punjab_districts().union(1).geometry()
    img = flood_mask_for_window(aoi, ("2023-07-05", "2023-07-15"),
                                ("2023-04-01", "2023-05-31"))
    assert img.bandNames().getInfo() == ["flood"]
```

- [ ] **Step 2: Implementation** — port gee/02 logic once, exactly:

```python
# sailaab/ee_graphs.py
"""All Earth Engine graph construction lives here (thin, mirrored from gee/02)."""
import ee

from sailaab import config


def punjab_districts() -> ee.FeatureCollection:
    return ee.FeatureCollection("FAO/GAUL/2015/level2").filter(ee.Filter.And(
        ee.Filter.eq("ADM0_NAME", "India"), ee.Filter.eq("ADM1_NAME", "Punjab")))


def _s1(aoi):
    return (ee.ImageCollection("COPERNICUS/S1_GRD").filterBounds(aoi)
            .filter(ee.Filter.eq("instrumentMode", "IW"))
            .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
            .select(["VV"]))


def _despeckle(img):
    return img.focalMedian(50, "circle", "meters")


def _masks():
    perm = ee.Image("JRC/GSW1_4/GlobalSurfaceWater").select("occurrence").gte(60)
    dem = (ee.ImageCollection("COPERNICUS/DEM/GLO30").select("DEM").mosaic()
           .setDefaultProjection("EPSG:4326", None, 30))
    return perm, ee.Terrain.slope(dem).gt(5)


def flood_mask_for_window(aoi, window: tuple[str, str],
                          pre: tuple[str, str]) -> ee.Image:
    col = _s1(aoi)
    pre_img = col.filterDate(*pre).map(_despeckle).median()
    post = col.filterDate(*window).map(_despeckle).min()
    perm, steep = _masks()
    dvv = post.subtract(pre_img)
    f = (dvv.lt(config.DIFF_THRESHOLD_DB)
         .And(post.lt(config.ABS_VV_THRESHOLD_DB))
         .updateMask(perm.Not()).updateMask(steep.Not()).selfMask())
    return (f.updateMask(f.connectedPixelCount(25)
                          .gte(config.MIN_CONNECTED_PIXELS))
            .rename("flood"))


def district_flood_stats(flood: ee.Image, districts: ee.FeatureCollection,
                         year: int, window_start: str) -> ee.FeatureCollection:
    area_ha = ee.Image.pixelArea().divide(1e4)
    crop = ee.ImageCollection("ESA/WorldCover/v200").first().select("Map").eq(40)
    img = (flood.multiply(area_ha).rename("flooded_ha")
           .addBands(flood.multiply(crop).multiply(area_ha)
                     .rename("crop_flooded_ha")))
    stats = img.reduceRegions(collection=districts, reducer=ee.Reducer.sum(),
                              scale=30, tileScale=4)
    return stats.map(lambda d: d.set("window_start", window_start, "year", year))
```

NOTE: `reduceRegions` with a 2-band image and `sum` yields `flooded_ha`/`crop_flooded_ha` columns; verify column names on the first real export and, if they come out as `sum`/`sum_1`, fix HERE (one place) and extend `tidy_district_export` accordingly — with a new test case pinning the real header.

- [ ] **Step 3: Run gated tests** — `python -m pytest tests/test_ee_graphs.py -m ee -v` (after `earthengine authenticate`). Expected: 2 passed.

- [ ] **Step 4: Commit**

```bash
git add sailaab/ee_graphs.py tests/test_ee_graphs.py
git commit -m "feat: single EE graph module mirroring Tier A logic"
```

---

### Task 3: Thin CLI + anchor run (2023 first)

**Files:**
- Modify (replace draft): `pipeline/batch_decade.py`
- Modify: `docs/VERIFICATION-LOG.md`

- [ ] **Step 1: Replace the draft with the thin CLI**

```python
# pipeline/batch_decade.py
"""Wave 2 runner. Usage:
    python pipeline/batch_decade.py 2023        # one year (anchor first!)
    python pipeline/batch_decade.py             # all years
Exports land in Drive/sailaab; monitor with `earthengine task list`."""
import sys

import ee

from sailaab.decade import run_manifest
from sailaab.ee_graphs import punjab_districts, flood_mask_for_window, \
    district_flood_stats

EE_PROJECT = "ee-YOURUSER"  # set after Task 1 of plan 01


def main():
    ee.Initialize(project=EE_PROJECT)
    years = [int(a) for a in sys.argv[1:]] or None
    districts = punjab_districts()
    aoi = districts.union(1).geometry()

    by_year = {}
    for row in run_manifest(years):
        f = flood_mask_for_window(aoi, row["window"], row["pre"])
        by_year.setdefault(row["year"], []).append(
            district_flood_stats(f, districts, row["year"], row["window"][0]))
    for year, fcs in by_year.items():
        merged = ee.FeatureCollection(fcs).flatten()
        ee.batch.Export.table.toDrive(
            collection=merged, description=f"sailaab_decade_{year}",
            folder="sailaab", fileFormat="CSV").start()
        print(f"queued {year}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Pre-declare the anchor checkpoint (red).** Append to VERIFICATION-LOG:

```markdown
| 2026-07-2X | decade 2023 anchor | Sangrur flooded_ha in mid-Aug-2023 windows within 3,500–11,000 ha (NRSC: 7,121) | | |
| 2026-07-2X | decade 2023 season shape | Jul windows >> Jun windows statewide (known Jul-2023 Sutlej/Ghaggar event) | | |
```

- [ ] **Step 3: Run the anchor year** — `python pipeline/batch_decade.py 2023`; when the Drive CSV lands, load with `tidy_district_export` and check the two rows. Record verdicts. FAIL → debug thresholds/windows before burning quota on 10 more years.

- [ ] **Step 4: Full run** — `python pipeline/batch_decade.py` (queues 2015–2025). If exports throttle, run in two halves; if quota bites hard, fall back to alternate years 2019/2021/2023/2025 (cut-line).

- [ ] **Step 5: Commit**

```bash
git add pipeline/batch_decade.py docs/VERIFICATION-LOG.md
git commit -m "feat: decade batch CLI; 2023 Sangrur anchor verified"
```

---

### Task 4: Frequency raster + decade docs

**Files:**
- Create: `pipeline/export_frequency.py`
- Modify: `docs/METHOD.md` (§3), `docs/VERIFICATION-LOG.md`

- [ ] **Step 1: Frequency export script**

```python
# pipeline/export_frequency.py
"""Season-max OR across years -> flood-frequency raster (counts of seasons flooded)."""
import ee

from sailaab import config
from sailaab.decade import run_manifest
from sailaab.ee_graphs import punjab_districts, flood_mask_for_window

EE_PROJECT = "ee-YOURUSER"


def main():
    ee.Initialize(project=EE_PROJECT)
    aoi = punjab_districts().union(1).geometry()
    season_layers = []
    for year in config.YEARS:
        rows = [r for r in run_manifest([year])]
        season = ee.ImageCollection(
            [flood_mask_for_window(aoi, r["window"], r["pre"]).unmask(0)
             for r in rows]).max()
        season_layers.append(season)
    freq = ee.ImageCollection(season_layers).sum().rename("flood_frequency")
    ee.batch.Export.image.toDrive(
        image=freq.byte(), description="sailaab_flood_frequency_2015_2025",
        folder="sailaab", region=aoi, scale=30, maxPixels=1e10).start()
    print("frequency export queued")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Pre-declare (red):** `| ... | frequency raster | max pixel value ≤ 11; high-frequency pixels concentrate along river belts | | |` → run → record.

- [ ] **Step 3: The headline table.** In a notebook or small script, from the tidied decade CSVs compute: per district, number of seasons with flooded_fraction > 2% → save `atlas/repeat_flooding_districts.csv`. This is the "flooded ≥3 times in 11 years" list for the video.

- [ ] **Step 4: Docs.** METHOD.md §3: windows, per-year pre-season reference (Apr–May, and WHY: monsoon-free baseline), anchor result verbatim, quota compromises if any (which years dropped — no silent caps). DATA-SOURCES rows if new.

- [ ] **Step 5: Commit**

```bash
git add pipeline/export_frequency.py atlas/repeat_flooding_districts.csv docs/
git commit -m "feat: flood-frequency raster + repeat-flooding table"
```
