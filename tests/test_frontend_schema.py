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


def test_validator_module_is_committed():
    assert MODULE.exists(), "forecastSchema.js missing"
    assert SUITE.exists(), "forecastSchema.test.mjs missing"


def test_component_uses_the_shared_validator_not_its_own_copy():
    """Validation logic living in two places is how the two drift apart."""
    jsx = (ROOT / "webapp" / "src" / "ForecastSection.jsx").read_text(encoding="utf-8")
    assert "from './forecastSchema'" in jsx
    assert "resolveForecastState(" in jsx
    for gone in ("function validRow", "function boardIsCoherent", "function isRow"):
        assert gone not in jsx, f"{gone} still duplicated in the component"


@pytest.mark.skipif(shutil.which("node") is None, reason="node not available")
def test_node_schema_suite_passes():
    proc = subprocess.run(
        ["node", "--test", str(SUITE)],
        cwd=ROOT, capture_output=True, text=True, timeout=180,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "fail 0" in proc.stdout, proc.stdout
