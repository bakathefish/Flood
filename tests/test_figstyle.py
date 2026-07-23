# tests/test_figstyle.py
"""Pure tests for sailaab.figstyle (no rendering).

Covers: the bundled fonts register with matplotlib when the files exist, the
public family-name constants, apply() wiring rcParams, and clean()'s dash
policy (em dash rejected; prose en dash rejected; numeric-range en dash kept).
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
import pytest
from matplotlib import font_manager

from sailaab import figstyle


def test_family_name_constants():
    assert figstyle.FONT_DISPLAY == "Bricolage Grotesque"
    assert figstyle.FONT_BODY == "IBM Plex Sans"
    assert figstyle.FONT_MONO == "IBM Plex Mono"


def test_fonts_registered_when_files_exist():
    """Every bundled TTF that exists on disk is known to the font manager, and
    the three house families resolve by name to a bundled file."""
    registered = figstyle.register_fonts()
    on_disk = [f for f in figstyle._FONT_FILES if (figstyle.FONTS_DIR / f).exists()]
    assert set(registered) == set(on_disk)

    if not on_disk:
        pytest.skip("assets/fonts/ not present in this checkout")

    known = {Path(f.fname).name for f in font_manager.fontManager.ttflist}
    for name in on_disk:
        assert name in known

    # Each house family resolves to one of our bundled files (not a fallback).
    bundled = {str((figstyle.FONTS_DIR / f).resolve()) for f in on_disk}
    for family in (figstyle.FONT_DISPLAY, figstyle.FONT_BODY, figstyle.FONT_MONO):
        resolved = font_manager.findfont(
            font_manager.FontProperties(family=family), fallback_to_default=False
        )
        assert str(Path(resolved).resolve()) in bundled, (family, resolved)


def test_weight_selection_picks_distinct_plex_files():
    """IBM Plex Sans weight requests resolve to the matching static instance."""
    if not (figstyle.FONTS_DIR / "IBMPlexSans-SemiBold.ttf").exists():
        pytest.skip("assets/fonts/ not present in this checkout")
    figstyle.register_fonts()
    got = {}
    for weight, tag in ((400, "Regular"), (500, "Medium"),
                        (600, "SemiBold"), (700, "Bold")):
        fp = font_manager.FontProperties(family=figstyle.FONT_BODY, weight=weight)
        got[tag] = Path(font_manager.findfont(fp, fallback_to_default=False)).name
    assert got["Regular"] == "IBMPlexSans-Regular.ttf"
    assert got["SemiBold"] == "IBMPlexSans-SemiBold.ttf"
    assert got["Bold"] == "IBMPlexSans-Bold.ttf"


def test_apply_sets_body_family_and_sizes():
    figstyle.apply(base_size=10.0)
    assert figstyle.FONT_BODY in matplotlib.rcParams["font.sans-serif"]
    assert matplotlib.rcParams["font.sans-serif"][0] == figstyle.FONT_BODY
    assert matplotlib.rcParams["font.size"] == 10.0
    # sizes scale off base_size
    assert matplotlib.rcParams["xtick.labelsize"] == 9.0


def test_mono_ticklabels_sets_family_on_fixed_ticks():
    matplotlib.use("Agg")
    from matplotlib.figure import Figure

    fig = Figure()
    ax = fig.add_subplot(111)
    ax.set_xticks([0, 1, 2])
    ax.set_xticklabels(["a", "b", "c"])
    figstyle.mono_ticklabels(ax)
    for lab in ax.get_xticklabels():
        assert lab.get_fontfamily()[0] == figstyle.FONT_MONO


def test_clean_accepts_numeric_range():
    assert figstyle.clean("2015–2025") == "2015–2025"


def test_clean_accepts_date_range():
    assert figstyle.clean("Aug 20–Sep 5") == "Aug 20–Sep 5"


def test_clean_accepts_plain_prose():
    s = "Punjab has no CWC flood-forecast station: zero."
    assert figstyle.clean(s) == s


def test_clean_rejects_em_dash():
    with pytest.raises(ValueError):
        figstyle.clean("foo — bar")


def test_clean_rejects_em_dash_tightly_set():
    with pytest.raises(ValueError):
        figstyle.clean("foo—bar")


def test_clean_rejects_prose_en_dash():
    with pytest.raises(ValueError):
        figstyle.clean("foo – bar")


def test_clean_rejects_dangling_en_dash():
    with pytest.raises(ValueError):
        figstyle.clean("trailing –")
