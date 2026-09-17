"""The board figures build from the committed verification outputs and land where the
docs say (`outputs/figures/<name>.png` and `.svg`); numbers on them come from those
outputs, never typed in."""

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "make_figures.py"


@pytest.fixture(scope="module")
def figs(tmp_path_factory):
    spec = importlib.util.spec_from_file_location("make_figures", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["make_figures"] = mod
    spec.loader.exec_module(mod)
    mod.OUT = tmp_path_factory.mktemp("figures")
    return mod


@pytest.mark.parametrize("name", ["event_2025_dhilwan", "flood_scale_ratios", "horizon_mae"])
def test_each_figure_builds_png_and_svg(figs, name):
    png = figs.ALL[name]()
    assert png.exists() and png.stat().st_size > 10_000
    svg = png.with_suffix(".svg")
    assert svg.exists()
    text = svg.read_text(encoding="utf-8")
    assert "<svg" in text


def test_event_figure_carries_the_verification_numbers(figs):
    png = figs.event_2025_dhilwan()
    text = png.with_suffix(".svg").read_text(encoding="utf-8")
    # the observed peak and the model peak from results.json / the WRD table
    assert "235,494" in text
    # the model-peak ratio the figure prints is the one verification recorded, not a typed one
    import json

    et = json.load(open("outputs/verification/results.json", encoding="utf-8"))["event_timing_local"]
    ratio = next(r["magnitude_ratio"] for r in et if r["year"] == 2025)
    assert f"ratio {ratio:.2f}" in text
    assert "first ECMWF flag 15 Aug" in text
