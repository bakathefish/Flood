# Sailaab 06 — Live Monitor + Vernacular Alerts (Wave 5) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Tasks 1–2 pure-Python (executable now); Tasks 3–5 need EE service account + repo secrets (user).

**Goal:** A 6-hourly GitHub Action that detects new Sentinel-1 passes over Punjab, runs the flood classifier, updates `monitor/latest.json`, and renders Punjabi/Hindi/English district alerts.

**Architecture:** `sailaab/alerts.py` (template rendering — pure, tested; Punjabi copy reviewed by the user, a native reader) and `sailaab/monitor.py` (new-scene detection against a state file — pure logic, tested). `pipeline/live_monitor.py` wires them to `ee_graphs`. State (`monitor/state.json`, `monitor/latest.json`) is committed by the Action itself.

**Tech Stack:** earthengine-api (service account), GitHub Actions cron, optional Telegram Bot API.

---

### Task 1: alerts.py — trilingual alert rendering (pure, TDD)

**Files:**
- Create: `sailaab/alerts.py`
- Test: `tests/test_alerts.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_alerts.py
import pytest

from sailaab.alerts import render_alert


def test_english_alert_contains_facts():
    s = render_alert("Gurdaspur", flooded_km2=142.7, trend="rising", lang="en")
    assert "Gurdaspur" in s and "142.7" in s and "rising" in s and "1070" in s


def test_punjabi_alert_renders_gurmukhi():
    s = render_alert("Gurdaspur", flooded_km2=142.7, trend="rising", lang="pa")
    assert "ਹੜ੍ਹ" in s          # "flood" in Gurmukhi
    assert "142.7" in s and "1070" in s


def test_hindi_alert_renders_devanagari():
    s = render_alert("Gurdaspur", flooded_km2=10.0, trend="falling", lang="hi")
    assert "बाढ़" in s and "10.0" in s


def test_unknown_language_raises():
    with pytest.raises(ValueError, match="lang"):
        render_alert("Moga", 1.0, "stable", lang="fr")


def test_trend_is_translated_not_english_leaked():
    s = render_alert("Moga", 1.0, "rising", lang="pa")
    assert "rising" not in s
```

- [ ] **Step 2: Run to FAIL** — ModuleNotFoundError.

- [ ] **Step 3: Minimal implementation**

```python
# sailaab/alerts.py
"""Trilingual district flood alerts. 1070 = state disaster helpline.
Punjabi/Hindi copy: reviewed by a native reader before first public render
(plan 06 Task 5 checkpoint). Roadmap: Bhashini API for voice alerts."""

_TREND = {
    "en": {"rising": "rising", "falling": "falling", "stable": "stable"},
    "pa": {"rising": "ਵਧ ਰਿਹਾ", "falling": "ਘਟ ਰਿਹਾ", "stable": "ਸਥਿਰ"},
    "hi": {"rising": "बढ़ रहा", "falling": "घट रहा", "stable": "स्थिर"},
}

_TEMPLATES = {
    "en": ("FLOOD ALERT: ~{km2} sq km under water in {district} district "
           "(satellite-detected). Trend: {trend}. Helpline: 1070"),
    "pa": ("ਹੜ੍ਹ ਚੇਤਾਵਨੀ: {district} ਜ਼ਿਲ੍ਹੇ ਵਿੱਚ ~{km2} ਵਰਗ ਕਿਲੋਮੀਟਰ ਖੇਤਰ ਪਾਣੀ ਹੇਠ ਹੈ "
           "(ਸੈਟੇਲਾਈਟ ਦੁਆਰਾ ਪਛਾਣਿਆ)। ਰੁਝਾਨ: {trend}। ਹੈਲਪਲਾਈਨ: 1070"),
    "hi": ("बाढ़ चेतावनी: {district} जिले में ~{km2} वर्ग किमी क्षेत्र जलमग्न है "
           "(सैटेलाइट द्वारा पहचाना गया)। रुझान: {trend}। हेल्पलाइन: 1070"),
}


def render_alert(district: str, flooded_km2: float, trend: str,
                 lang: str = "pa") -> str:
    if lang not in _TEMPLATES:
        raise ValueError(f"unsupported lang: {lang}")
    return _TEMPLATES[lang].format(district=district,
                                   km2=round(flooded_km2, 1),
                                   trend=_TREND[lang][trend])
```

- [ ] **Step 4: Run to PASS** — 5 passed.
- [ ] **Step 5: Commit** — `git add sailaab/alerts.py tests/test_alerts.py && git commit -m "feat: trilingual flood alert rendering (pa/hi/en)"`

---

### Task 2: monitor.py — new-scene detection state (pure, TDD)

**Files:**
- Create: `sailaab/monitor.py`
- Test: `tests/test_monitor.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_monitor.py
import json

from sailaab.monitor import new_scenes, load_state, save_state


def test_new_scenes_after_watermark():
    dates = ["2026-07-18T01:10:00", "2026-07-19T13:22:00", "2026-07-20T01:10:00"]
    out = new_scenes(dates, last_seen="2026-07-19T00:00:00")
    assert out == ["2026-07-19T13:22:00", "2026-07-20T01:10:00"]


def test_no_new_scenes_returns_empty():
    assert new_scenes(["2026-07-18T01:10:00"], "2026-07-19T00:00:00") == []


def test_state_roundtrip(tmp_path):
    p = tmp_path / "state.json"
    save_state(p, last_seen="2026-07-20T01:10:00")
    assert load_state(p) == "2026-07-20T01:10:00"


def test_missing_state_returns_epoch(tmp_path):
    assert load_state(tmp_path / "nope.json") == "1970-01-01T00:00:00"
```

- [ ] **Step 2: Run to FAIL**, then implement:

```python
# sailaab/monitor.py
"""New-scene watermark logic for the live monitor (pure; EE calls stay in pipeline/)."""
import json
from pathlib import Path

EPOCH = "1970-01-01T00:00:00"


def new_scenes(scene_dates: list[str], last_seen: str) -> list[str]:
    return sorted(d for d in scene_dates if d > last_seen)


def load_state(path: Path) -> str:
    p = Path(path)
    if not p.exists():
        return EPOCH
    return json.loads(p.read_text())["last_seen"]


def save_state(path: Path, last_seen: str) -> None:
    Path(path).write_text(json.dumps({"last_seen": last_seen}))
```

- [ ] **Step 3: Run to PASS** — 4 passed.
- [ ] **Step 4: Commit** — `git add sailaab/monitor.py tests/test_monitor.py && git commit -m "feat: monitor watermark state logic"`

---

### Task 3: live_monitor.py — the runner

**Files:**
- Create: `pipeline/live_monitor.py`

- [ ] **Step 1: Write it**

```python
# pipeline/live_monitor.py
"""6-hourly monitor: new S1 pass over Punjab -> flood stats -> monitor/latest.json.
Auth: EE service account via GOOGLE_APPLICATION_CREDENTIALS or EE_SA_KEY env
(JSON key contents; written to a temp file in CI)."""
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import ee

from sailaab.alerts import render_alert
from sailaab.ee_graphs import punjab_districts, flood_mask_for_window, \
    district_flood_stats
from sailaab.monitor import load_state, new_scenes, save_state

STATE = Path("monitor/state.json")
LATEST = Path("monitor/latest.json")
LOOKBACK_DAYS = 12          # one S1 revisit
ALERT_KM2 = 25.0            # district alert floor


def _init_ee():
    key = os.environ.get("EE_SA_KEY")
    if key:
        kf = Path("ee-key.json"); kf.write_text(key)
        creds = ee.ServiceAccountCredentials(None, str(kf))
        ee.Initialize(creds)
    else:
        ee.Initialize()


def main():
    _init_ee()
    districts = punjab_districts()
    aoi = districts.union(1).geometry()
    now = datetime.now(timezone.utc)
    start = (now - timedelta(days=LOOKBACK_DAYS)).strftime("%Y-%m-%d")

    col = (ee.ImageCollection("COPERNICUS/S1_GRD").filterBounds(aoi)
           .filter(ee.Filter.eq("instrumentMode", "IW"))
           .filterDate(start, now.strftime("%Y-%m-%d")))
    dates = col.aggregate_array("system:time_start").getInfo() or []
    iso = [datetime.fromtimestamp(t / 1000, timezone.utc)
           .strftime("%Y-%m-%dT%H:%M:%S") for t in sorted(dates)]

    fresh = new_scenes(iso, load_state(STATE))
    if not fresh:
        print("no new scenes"); return

    window = (fresh[0][:10], now.strftime("%Y-%m-%d"))
    year = now.year
    pre = (f"{year}-04-01", f"{year}-05-31")
    flood = flood_mask_for_window(aoi, window, pre)
    stats = district_flood_stats(flood, districts, year, window[0]) \
        .getInfo()["features"]

    rows = []
    for f in stats:
        p = f["properties"]
        km2 = float(p.get("flooded_ha") or 0) / 100.0
        rows.append({"district": p["ADM2_NAME"], "flooded_km2": round(km2, 1)})
    rows.sort(key=lambda r: -r["flooded_km2"])
    flagged = [r for r in rows if r["flooded_km2"] >= ALERT_KM2]
    alerts = {lang: [render_alert(r["district"], r["flooded_km2"], "stable", lang)
                     for r in flagged] for lang in ("pa", "hi", "en")}

    LATEST.parent.mkdir(exist_ok=True)
    LATEST.write_text(json.dumps({
        "generated_utc": now.strftime("%Y-%m-%dT%H:%M:%S"),
        "latest_pass": fresh[-1], "window": window,
        "districts": rows, "flagged": flagged, "alerts": alerts,
    }, ensure_ascii=False, indent=1))
    save_state(STATE, fresh[-1])
    print(f"updated: {len(fresh)} new scene(s), {len(flagged)} flagged")


if __name__ == "__main__":
    main()
```

(Trend needs the previous run's stats — v0 emits "stable"; a follow-up compares against the prior `latest.json` and passes rising/falling. Add only if time allows; not a cut-line item.)

- [ ] **Step 2: Local dry-run (user, after EE auth):** `python pipeline/live_monitor.py` twice — first run writes latest.json, second prints "no new scenes". That pair is the acceptance test; log it in VERIFICATION-LOG.
- [ ] **Step 3: Commit** — `git add pipeline/live_monitor.py && git commit -m "feat: live monitor runner"` (add `ee-key.json` to .gitignore in the same commit).

---

### Task 4: GitHub Action

**Files:**
- Create: `.github/workflows/monitor.yml`

- [ ] **Step 1: Write the workflow**

```yaml
name: sailaab-monitor
on:
  schedule:
    - cron: "0 */6 * * *"
  workflow_dispatch: {}
permissions:
  contents: write
jobs:
  monitor:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install -r requirements.txt
      - run: python -m pytest -q          # never publish from a red tree
      - run: python pipeline/live_monitor.py
        env:
          EE_SA_KEY: ${{ secrets.EE_SA_KEY }}
      - name: commit state
        run: |
          git config user.name "sailaab-monitor"
          git config user.email "monitor@users.noreply.github.com"
          git add monitor/
          git diff --cached --quiet || git commit -m "monitor: update latest.json"
          git push
```

- [ ] **Step 2 (user):** Create the EE **service account** (console.cloud.google.com → IAM → service account on the `ee-<user>` project → JSON key; register it for EE at code.earthengine.google.com/register or via the EE service-account docs). Add the JSON as repo secret `EE_SA_KEY`. Push the repo to GitHub (public).
- [ ] **Step 3: Pre-declare (red):** `| ... | monitor Action | two consecutive scheduled runs green; latest.json timestamp advances | | |` → trigger via workflow_dispatch first, then wait for cron → record.
- [ ] **Step 4: Commit** — `git add .github/workflows/monitor.yml && git commit -m "ci: 6-hourly flood monitor"`

---

### Task 5: Copy review + docs

- [ ] **Step 1 (user):** Read the Punjabi and Hindi alert strings aloud; fix phrasing directly in `sailaab/alerts.py` (tests pin structure, not exact wording — keep "ਹੜ੍ਹ"/"बाढ़"/1070 anchors).
- [ ] **Step 2:** METHOD.md §6 — monitor design (watermark, lookback, alert floor, service-account auth), alert-language rationale + Bhashini roadmap. DATA-SOURCES row for the helpline number source.
- [ ] **Step 3: Commit** — `git commit -m "docs: monitor method; alert copy review"`
