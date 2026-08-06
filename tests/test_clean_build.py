# tests/test_clean_build.py
"""A fresh checkout must be able to build and serve the site.

The committed docs/ output was tested; the build that produces it was not. So
the proof chart could reference a data file that existed only in docs/ and had
never been written to Vite's public directory, and nothing failed until someone
built from a clean tree and got a 404 with no visible error.

The full `npm run build` is only run when node and the installed dependencies
are both present, so this never blocks the monitor runner. The asset-wiring
checks are pure filesystem work and always run.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WEBAPP = ROOT / "webapp"
PUBLIC = WEBAPP / "public" / "assets"
SRC = WEBAPP / "src"


def _requested_assets() -> set[str]:
    """Every `assets/<file>` a component fetches at runtime."""
    wanted: set[str] = set()
    for f in SRC.glob("*.jsx"):
        wanted |= set(re.findall(r"['\"]assets/([A-Za-z0-9_.-]+\.(?:csv|json))['\"]",
                                 f.read_text(encoding="utf-8")))
    return wanted


def test_components_request_at_least_one_asset():
    assert _requested_assets(), "no runtime assets found; the scan is broken"


def test_every_requested_asset_ships_in_the_vite_public_dir():
    missing = sorted(a for a in _requested_assets() if not (PUBLIC / a).exists())
    assert not missing, (
        f"a clean `vite build` would 404 on {missing}; "
        "add them to webapp/public/assets (pipeline/make_web_assets.py writes them)"
    )


def test_retired_feeds_are_not_shipped():
    assert not (PUBLIC / "forecaster_2025_hindcast.csv").exists(), (
        "the superseded hindcast feed is still in the public dir"
    )
    stale = ROOT / "docs" / "assets" / "data" / "forecaster_2025_hindcast.csv"
    assert not stale.exists(), "docs/assets/data still carries the superseded feed"


def test_walkforward_feed_is_identical_everywhere_it_ships():
    source = (ROOT / "data" / "forecaster_2025_walkforward.csv").read_bytes()
    for copy in (
        PUBLIC / "forecaster_2025_walkforward.csv",
        ROOT / "docs" / "assets" / "forecaster_2025_walkforward.csv",
        ROOT / "docs" / "assets" / "data" / "forecaster_2025_walkforward.csv",
    ):
        assert copy.exists(), f"missing {copy.relative_to(ROOT)}"
        assert copy.read_bytes() == source, f"{copy.relative_to(ROOT)} has drifted"


@pytest.mark.skipif(
    shutil.which("npm") is None or not (WEBAPP / "node_modules").exists(),
    reason="npm or node_modules unavailable",
)
def test_clean_vite_build_succeeds_and_emits_the_assets():
    proc = subprocess.run(
        ["npm", "run", "build"], cwd=WEBAPP,
        capture_output=True, text=True, timeout=600, shell=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    dist = WEBAPP / "dist"
    assert (dist / "index.html").exists()
    for asset in _requested_assets():
        assert (dist / "assets" / asset).exists(), f"build did not emit {asset}"
