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

# Resolved once, and passed as the executable rather than relying on a shell.
# `shell=True` with an argument LIST is not portable: on POSIX only the first
# element becomes the command and the rest are handed to the shell as $0 and $1,
# so `["npm", "run", "build"]` ran a bare `npm`, which prints its usage and
# exits 1. On Windows the list is joined instead, so the same line passed here
# and failed on the runner. The full path also covers Windows, where npm is a
# `.CMD` shim that bare-name resolution misses.
NPM = shutil.which("npm")


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


RETIRED_FEEDS = ("forecaster_2025_hindcast.csv",)


def test_retired_feeds_are_not_shipped_anywhere():
    """Check every served directory, not one of them.

    The previous version of this test looked only in docs/assets/data and
    passed while the retired feed sat in docs/assets, which is a path the site
    actually serves. Enumerate the directories instead of naming one.
    """
    served = [
        PUBLIC,
        ROOT / "docs" / "assets",
        ROOT / "docs" / "assets" / "data",
        WEBAPP / "dist" / "assets",
        # `data/` is not served by the site, but a retired feed kept there is a
        # loaded gun: it is the copy `make_web_assets.py` would republish, and
        # it sat in the tree with no consumer after the model was retired.
        ROOT / "data",
    ]
    offenders = [
        str((d / name).relative_to(ROOT))
        for d in served if d.exists()
        for name in RETIRED_FEEDS if (d / name).exists()
    ]
    assert not offenders, f"retired feed still present at {offenders}"


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
    NPM is None or not (WEBAPP / "node_modules").exists(),
    reason="npm or node_modules unavailable",
)
def test_clean_vite_build_succeeds_and_emits_the_assets():
    proc = subprocess.run(
        [NPM, "run", "build"], cwd=WEBAPP,
        capture_output=True, text=True, timeout=600,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    dist = WEBAPP / "dist"
    assert (dist / "index.html").exists()
    for asset in _requested_assets():
        assert (dist / "assets" / asset).exists(), f"build did not emit {asset}"
