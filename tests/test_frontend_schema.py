# tests/test_frontend_schema.py
"""Run the frontend feed-validator suite from the Python gate.

The validator decides whether a live flood board is shown, so it needs
behavioural tests, and those have to run somewhere the normal `pytest` gate
sees them. `node --test` does the work; this wraps it. Skips when node is
absent (the monitor runner has no npm), so it never blocks CI, but it fails
loudly on any machine that can run it.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SUITE = ROOT / "webapp" / "src" / "forecastSchema.test.mjs"
MODULE = ROOT / "webapp" / "src" / "forecastSchema.js"
HAZARD_SUITE = ROOT / "webapp" / "src" / "hazardSchema.test.mjs"
HAZARD_MODULE = ROOT / "webapp" / "src" / "hazardSchema.js"


def test_validator_module_is_committed():
    assert MODULE.exists(), "forecastSchema.js missing"
    assert SUITE.exists(), "forecastSchema.test.mjs missing"
    assert HAZARD_MODULE.exists(), "hazardSchema.js missing"
    assert HAZARD_SUITE.exists(), "hazardSchema.test.mjs missing"


def test_component_uses_the_shared_validator_not_its_own_copy():
    """Validation logic living in two places is how the two drift apart."""
    jsx = (ROOT / "webapp" / "src" / "ForecastSection.jsx").read_text(encoding="utf-8")
    assert "from './forecastSchema'" in jsx
    assert "resolveForecastState(" in jsx
    for gone in ("function validRow", "function boardIsCoherent", "function isRow"):
        assert gone not in jsx, f"{gone} still duplicated in the component"


def test_hazard_section_uses_the_shared_validator():
    """The river watch has the same rule: one validator, imported, not copied."""
    jsx = (ROOT / "webapp" / "src" / "HazardSection.jsx").read_text(encoding="utf-8")
    assert "from './hazardSchema'" in jsx
    assert "resolveHazardState(" in jsx
    # the widest error budget is the one the page prints; the narrower ones
    # would print a calmer number for the same day
    js = HAZARD_MODULE.read_text(encoding="utf-8")
    assert "p_exhaustion_flood_scale" in js
    # the feed is the product's latest.json, not a dated record the Action
    # would have to rename every day
    assert "punjabflood/outputs/forecast/latest.json" in jsx


@pytest.mark.parametrize("suite", [SUITE, HAZARD_SUITE], ids=["forecast", "hazard"])
@pytest.mark.skipif(shutil.which("node") is None, reason="node not available")
def test_node_schema_suite_passes(suite):
    proc = subprocess.run(
        ["node", "--test", str(suite)],
        cwd=ROOT, capture_output=True, text=True, timeout=180,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "fail 0" in proc.stdout, proc.stdout
