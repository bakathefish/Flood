"""Shared fixtures. Network tests are opt-in: run ``pytest -m network`` to include them."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


def pytest_collection_modifyitems(config, items):
    if config.getoption("-m"):
        return
    skip = pytest.mark.skip(reason="network test; run with -m network")
    for item in items:
        if "network" in item.keywords:
            item.add_marker(skip)


@pytest.fixture
def repo_root() -> Path:
    return REPO


@pytest.fixture
def tmp_cache(tmp_path) -> Path:
    d = tmp_path / "cache"
    d.mkdir()
    return d
