# Sailaab 02 — Python Core Library Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the tested pure-Python core (`sailaab/`: config, windows, stats) that every pipeline CLI depends on.

**Architecture:** Zero Earth Engine imports in this package — everything here is deterministic and unit-testable. `config.py` is the single source of truth for constants shared with the GEE JS scripts (thresholds, windows, district folds); JS keeps its own copies with a comment pointing here, and plan 01 has a task to reconcile spellings.

**Tech Stack:** Python 3.11+, pytest, pandas.

---

### Task 1: Project skeleton + test harness

**Files:**
- Create: `requirements.txt`, `sailaab/__init__.py`, `tests/__init__.py`, `pytest.ini`

- [ ] **Step 1: Write requirements.txt**

```
earthengine-api>=1.4
pandas>=2.2
pytest>=8.0
xgboost>=2.1
scikit-learn>=1.5
shap>=0.46
matplotlib>=3.9
numpy>=1.26
```

- [ ] **Step 2: Create empty package + pytest.ini**

`sailaab/__init__.py` and `tests/__init__.py`: empty files.

`pytest.ini`:
```ini
[pytest]
testpaths = tests
markers =
    ee: requires authenticated Earth Engine (excluded by default)
addopts = -m "not ee"
```

- [ ] **Step 3: Install and verify harness**

Run: `pip install -r requirements.txt` then `python -m pytest -v`
Expected: `no tests ran` (exit code 5 is fine — harness works)

- [ ] **Step 4: Commit**

```bash
git add requirements.txt pytest.ini sailaab/__init__.py tests/__init__.py
git commit -m "chore: python package skeleton + pytest harness"
```

---

### Task 2: config.py — shared constants

**Files:**
- Create: `sailaab/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_config.py
from sailaab import config


def test_thresholds_are_negative_db():
    assert config.DIFF_THRESHOLD_DB < 0
    assert config.ABS_VV_THRESHOLD_DB < 0


def test_2025_event_windows_ordered():
    assert config.PRE_2025 == ("2025-07-01", "2025-08-10")
    assert config.FLOOD_2025 == ("2025-08-25", "2025-09-06")
    assert config.PRE_2025[1] < config.FLOOD_2025[0]


def test_spatial_folds_do_not_overlap():
    assert not set(config.FOLD_RAVI_BEAS) & set(config.FOLD_SUTLEJ)
    assert len(config.FOLD_RAVI_BEAS) >= 5 and len(config.FOLD_SUTLEJ) >= 5


def test_official_bands_present():
    lo, hi = config.OFFICIAL_CROP_FLOODED_HA_BAND
    assert 100_000 < lo < hi < 250_000
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_config.py -v`
Expected: FAIL — `ImportError: cannot import name 'config'`

- [ ] **Step 3: Write minimal implementation**

```python
# sailaab/config.py
"""Single source of truth for constants. gee/*.js mirrors these values —
if you change one here, plan 01 Task 5 (JS sync) must be re-run."""

# --- SAR thresholds (dB), kept in sync with gee/02 ---
DIFF_THRESHOLD_DB = -3.0     # dVV = post - pre
ABS_VV_THRESHOLD_DB = -15.0  # post VV ceiling for water
MIN_CONNECTED_PIXELS = 10

# --- 2025 event windows (ISO dates) ---
PRE_2025 = ("2025-07-01", "2025-08-10")
FLOOD_2025 = ("2025-08-25", "2025-09-06")

# --- Decade run ---
YEARS = list(range(2015, 2026))
SEASON_START_MD = "06-15"
SEASON_END_MD = "09-30"
WINDOW_DAYS = 10
PRE_SEASON_MD = ("04-01", "05-31")  # dry-season reference per year

# --- Spatial CV folds (GAUL ADM2_NAME spellings; verified by plan 01 Task 5) ---
FOLD_RAVI_BEAS = ["Gurdaspur", "Amritsar", "Kapurthala", "Tarn Taran",
                  "Hoshiarpur", "Jalandhar"]
FOLD_SUTLEJ = ["Firozpur", "Faridkot", "Ludhiana", "Moga", "Rupnagar",
               "Nawanshahr", "Fatehgarh Sahib"]

# --- Honesty bands (official 2025 figures for comparison, not calibration) ---
OFFICIAL_CROP_FLOODED_HA_BAND = (148_000, 175_000)
OFFICIAL_POP_AFFECTED = 355_000
SANGRUR_2023_NRSC_HA = 7_121  # NRSC anchor for the decade run

FLOOD_EVENT_FRACTION = 0.02  # >2% of district area flooded = "event" (forecaster)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_config.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add sailaab/config.py tests/test_config.py
git commit -m "feat: shared config constants with honesty bands"
```

---

### Task 3: windows.py — monsoon window generation

**Files:**
- Create: `sailaab/windows.py`
- Test: `tests/test_windows.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_windows.py
from sailaab.windows import monsoon_windows


def test_first_window_starts_on_season_start():
    w = monsoon_windows(2025)
    assert w[0] == ("2025-06-15", "2025-06-25")


def test_windows_are_contiguous_and_ordered():
    w = monsoon_windows(2025)
    for (a, b), (c, d) in zip(w, w[1:]):
        assert b == c and a < b


def test_final_window_truncates_at_season_end():
    w = monsoon_windows(2025)
    assert w[-1][1] == "2025-09-30"
    # Jun 15 -> Sep 30 = 107 days = 10 full 10-day windows + 7-day remainder
    assert len(w) == 11


def test_respects_custom_window_length():
    w = monsoon_windows(2025, window_days=30)
    assert len(w) == 4  # 30+30+30+17
    assert w[-1] == ("2025-09-13", "2025-09-30")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_windows.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'sailaab.windows'`

- [ ] **Step 3: Write minimal implementation**

```python
# sailaab/windows.py
"""Monsoon-season window generation for the decade batch and forecaster."""
from datetime import date, timedelta

from sailaab import config


def monsoon_windows(year: int,
                    start_md: str = config.SEASON_START_MD,
                    end_md: str = config.SEASON_END_MD,
                    window_days: int = config.WINDOW_DAYS) -> list[tuple[str, str]]:
    """Contiguous [start, end) windows covering the season; final window
    truncated at season end. Dates are ISO strings (GEE-friendly)."""
    start = date.fromisoformat(f"{year}-{start_md}")
    end = date.fromisoformat(f"{year}-{end_md}")
    out = []
    cur = start
    while cur < end:
        nxt = min(cur + timedelta(days=window_days), end)
        out.append((cur.isoformat(), nxt.isoformat()))
        cur = nxt
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_windows.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add sailaab/windows.py tests/test_windows.py
git commit -m "feat: monsoon window generation with truncated final window"
```

---

### Task 4: stats.py — GEE export tidying + area math

**Files:**
- Create: `sailaab/stats.py`
- Test: `tests/test_stats.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_stats.py
import pandas as pd
import pytest

from sailaab.stats import tidy_district_export, flooded_fraction


def _raw():
    # Shape of a GEE reduceRegions CSV export (system:index etc. dropped here)
    return pd.DataFrame({
        "ADM2_NAME": ["Gurdaspur", "Firozpur"],
        "flooded_ha": [12000.4, 8000.2],
        "crop_flooded_ha": [9000.1, 6500.0],
        "window_start": ["2025-08-25", "2025-08-25"],
        "year": [2025, 2025],
    })


def test_tidy_renames_and_types():
    df = tidy_district_export(_raw())
    assert list(df.columns) == ["district", "window_start", "year",
                                "flooded_ha", "crop_flooded_ha"]
    assert df["flooded_ha"].dtype == float


def test_tidy_rejects_missing_columns():
    with pytest.raises(ValueError, match="ADM2_NAME"):
        tidy_district_export(pd.DataFrame({"x": [1]}))


def test_flooded_fraction_joins_area():
    df = tidy_district_export(_raw())
    areas = pd.DataFrame({"district": ["Gurdaspur", "Firozpur"],
                          "area_ha": [356_900, 528_000]})
    out = flooded_fraction(df, areas)
    assert out.loc[out.district == "Gurdaspur", "flooded_fraction"].iloc[0] == \
        pytest.approx(12000.4 / 356_900)


def test_flooded_fraction_errors_on_unknown_district():
    df = tidy_district_export(_raw())
    areas = pd.DataFrame({"district": ["Gurdaspur"], "area_ha": [356_900.0]})
    with pytest.raises(ValueError, match="Firozpur"):
        flooded_fraction(df, areas)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_stats.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'sailaab.stats'`

- [ ] **Step 3: Write minimal implementation**

```python
# sailaab/stats.py
"""Tidy GEE reduceRegions exports into analysis frames."""
import pandas as pd

_REQUIRED = ["ADM2_NAME", "flooded_ha", "crop_flooded_ha", "window_start", "year"]


def tidy_district_export(raw: pd.DataFrame) -> pd.DataFrame:
    missing = [c for c in _REQUIRED if c not in raw.columns]
    if missing:
        raise ValueError(f"export missing columns: {missing}")
    df = raw[_REQUIRED].rename(columns={"ADM2_NAME": "district"}).copy()
    df["flooded_ha"] = df["flooded_ha"].astype(float)
    df["crop_flooded_ha"] = df["crop_flooded_ha"].astype(float)
    return df[["district", "window_start", "year", "flooded_ha", "crop_flooded_ha"]]


def flooded_fraction(df: pd.DataFrame, district_areas: pd.DataFrame) -> pd.DataFrame:
    unknown = set(df["district"]) - set(district_areas["district"])
    if unknown:
        raise ValueError(f"no area for districts: {sorted(unknown)}")
    out = df.merge(district_areas, on="district", how="left")
    out["flooded_fraction"] = out["flooded_ha"] / out["area_ha"]
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_stats.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add sailaab/stats.py tests/test_stats.py
git commit -m "feat: tidy GEE district exports + flooded fraction"
```

---

### Task 5: Documentation for the core lib

**Files:**
- Create: `docs/METHOD.md` (section 1), `docs/DATA-SOURCES.md` (header), `docs/VERIFICATION-LOG.md` (header)

- [ ] **Step 1: Write the doc skeletons**

`docs/METHOD.md`:
```markdown
# Sailaab — Method

## 1. Software architecture
Decision logic lives in the pure-Python `sailaab/` package, developed test-first
(pytest, tests/ mirrors the package 1:1). Earth Engine effects are confined to
`gee/*.js` and thin `pipeline/*.py` CLIs. Constants (thresholds, windows,
spatial folds, official comparison bands) are centralized in `sailaab/config.py`.
GEE steps use pre-declared acceptance checkpoints (see VERIFICATION-LOG.md).
<!-- Sections 2+ appended by later plans: 2 Mapping, 3 Decade, 4 Validation,
     5 Forecaster, 6 Monitor -->
```

`docs/DATA-SOURCES.md`:
```markdown
# Data sources
| Dataset | Provider | Access | License | Accessed | Used for |
|---|---|---|---|---|---|
<!-- rows appended by each plan when a dataset is first touched -->
```

`docs/VERIFICATION-LOG.md`:
```markdown
# Verification log
Checkpoint discipline: expected band is written BEFORE the run. FAIL stops the wave.
| Date | Step | Expected | Actual | Verdict |
|---|---|---|---|---|
```

- [ ] **Step 2: Commit**

```bash
git add docs/METHOD.md docs/DATA-SOURCES.md docs/VERIFICATION-LOG.md
git commit -m "docs: method, data-sources and verification-log skeletons"
```
