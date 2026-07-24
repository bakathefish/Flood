# tests/test_live_render.py
"""Rendering tests for pipeline.live_monitor.render_latest_png.

The heavy STAC/COG IO in pipeline.live_monitor is exercised only by the
end-to-end run; here we drive the pure matplotlib renderer with small synthetic
arrays to pin its new framed-card contract: a fixed ~1200x900 (4:3) canvas, the
unimaged-land wash + 'no pass' chip when coverage is partial, and the em-dash
guard inherited from figstyle.clean.
"""

from __future__ import annotations

import numpy as np
import pytest

live_monitor = pytest.importorskip("pipeline.live_monitor")
render_latest_png = live_monitor.render_latest_png

FOOTER = "Sentinel-1 RTC via Microsoft Planetary Computer (anonymous STAC)."


def _synthetic(coverage_cols):
    """A tiny two-district grid whose SAR swath covers the leftmost columns."""
    H, W = 160, 140
    labels = np.zeros((H, W), dtype=int)
    labels[20:150, 20:120] = 1
    labels[70:150, 70:120] = 2
    vv = np.full((H, W), np.nan)
    vv[:, :coverage_cols] = -9.0 + np.linspace(-2, 2, coverage_cols)[None, :]
    mask = np.zeros((H, W), dtype=bool)
    mask[80:95, 30:45] = True  # a flood blob inside the imaged part
    return vv, mask, labels


def test_writes_fixed_size_4x3_card(tmp_path):
    from PIL import Image

    vv, mask, labels = _synthetic(coverage_cols=80)  # ~partial coverage
    out = tmp_path / "latest.png"
    render_latest_png(
        vv, mask, labels, out,
        title="Punjab flood monitor",
        subtitle="pass 2026-07-20  ·  704 km² new surface water  ·  36% imaged",
        footer=FOOTER,
        status=["3 district(s) at or above 25 km²", "Ferozepur  88 km²"],
    )
    assert out.exists()
    assert Image.open(out).size == (1200, 900)  # ~1200px wide, 4:3


def test_partial_and_full_coverage_both_render(tmp_path):
    # partial (large unimaged area -> wash + 'no pass' chip path)
    vv, mask, labels = _synthetic(coverage_cols=60)
    render_latest_png(
        vv, mask, labels, tmp_path / "partial.png",
        title="Punjab flood monitor", subtitle="partial", footer=FOOTER,
    )
    # fully imaged (no 'no pass' chip, no wash chip) -> different branch
    H, W = 160, 140
    labels = np.zeros((H, W), dtype=int)
    labels[20:150, 20:120] = 1
    vv = np.full((H, W), -9.0)  # every pixel imaged
    mask = np.zeros((H, W), dtype=bool)
    render_latest_png(
        vv, mask, labels, tmp_path / "full.png",
        title="Punjab flood monitor", subtitle="full", footer=FOOTER,
        status=["no district at or above the 25 km² alert floor"],
    )
    assert (tmp_path / "partial.png").exists()
    assert (tmp_path / "full.png").exists()


def test_writes_compressed_jpg_twin(tmp_path):
    """The SAR field makes the PNG ~700 KB; the site loads a JPEG twin.

    Contract: rendering latest.png also writes latest.jpg on the same canvas
    (1200x900), and the JPEG is materially smaller than the PNG.
    """
    from PIL import Image

    vv, mask, labels = _synthetic(coverage_cols=80)
    out = tmp_path / "latest.png"
    render_latest_png(
        vv, mask, labels, out,
        title="Punjab flood monitor", subtitle="jpg twin", footer=FOOTER,
        status=["no district at or above the 25 km² alert floor"],
    )
    jpg = out.with_suffix(".jpg")
    assert jpg.exists(), "render must also emit the web JPEG twin"
    with Image.open(jpg) as im:
        assert im.format == "JPEG"
        assert im.size == (1200, 900)
    assert jpg.stat().st_size < out.stat().st_size


def test_em_dash_in_any_slot_is_rejected(tmp_path):
    vv, mask, labels = _synthetic(coverage_cols=80)
    for bad in ("title", "subtitle", "footer"):
        kwargs = dict(title="ok", subtitle="ok", footer="ok")
        kwargs[bad] = "flooded — again"  # em dash
        with pytest.raises(ValueError):
            render_latest_png(vv, mask, labels, tmp_path / f"{bad}.png", **kwargs)
