# sailaab/figstyle.py
"""Shared typography for the atlas figures.

The atlas figures are rendered with matplotlib, whose out-of-the-box font
(DejaVu Sans) plus the machine habit of em dashes in titles makes charts read as
generic / auto-generated. This module gives every figure the same designed
typography as the project site:

  * display headings  -> Bricolage Grotesque (bold)
  * body / labels     -> IBM Plex Sans
  * numbers / ticks   -> IBM Plex Mono

Import side effect: the bundled TTFs in ``assets/fonts/`` are registered with
matplotlib's font manager, so the family names resolve without touching the
user's system fonts. Call :func:`apply` once per figure script to set rcParams.

:func:`clean` is a guard for figure text: it rejects em dashes (and en dashes
used as prose) so no machine-default punctuation slips into a title or caption.
En dashes tightly set inside a numeric or date range (``2015–2025``,
``Aug 20–Sep 5``) are allowed.
"""

from __future__ import annotations

import re
from pathlib import Path

import matplotlib
from matplotlib import font_manager

# --- font family names (as reported by the bundled TTFs) --------------------
FONT_DISPLAY = "Bricolage Grotesque"  # bold headline / figure title
FONT_BODY = "IBM Plex Sans"           # subtitles, annotations, legends, captions
FONT_MONO = "IBM Plex Mono"           # axis + tick labels, numeric callouts

ROOT = Path(__file__).resolve().parents[1]
FONTS_DIR = ROOT / "assets" / "fonts"

# Bundled faces (SIL OFL 1.1; see assets/fonts/LICENSES.txt).
_FONT_FILES = (
    "IBMPlexSans-Regular.ttf",
    "IBMPlexSans-Medium.ttf",
    "IBMPlexSans-SemiBold.ttf",
    "IBMPlexSans-Bold.ttf",
    "IBMPlexMono-Regular.ttf",
    "IBMPlexMono-Medium.ttf",
    "BricolageGrotesque-Bold.ttf",
)

EM_DASH = "—"   # — : never allowed in figure text
EN_DASH = "–"   # – : allowed only tightly set inside a numeric/date range

_registered = False


def register_fonts() -> list[str]:
    """Register the bundled TTFs with matplotlib. Idempotent; missing files are
    skipped silently (a fresh checkout without ``assets/fonts/`` still imports)."""
    global _registered
    registered: list[str] = []
    known = {Path(f.fname).name for f in font_manager.fontManager.ttflist}
    for name in _FONT_FILES:
        path = FONTS_DIR / name
        if not path.exists():
            continue
        if name not in known:
            font_manager.fontManager.addfont(str(path))
        registered.append(name)
    _registered = True
    return registered


def apply(base_size: float = 9.0) -> None:
    """Set matplotlib rcParams to the atlas house typography.

    Body text (IBM Plex Sans) is the default family; individual figures still
    pick Bricolage Grotesque for titles and IBM Plex Mono for tick labels
    explicitly via ``fontfamily=``/``fontproperties=``. Sizes scale off
    ``base_size`` but every script may override per element."""
    if not _registered:
        register_fonts()
    matplotlib.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": [FONT_BODY, "DejaVu Sans", "Arial"],
        "font.monospace": [FONT_MONO, "DejaVu Sans Mono"],
        "font.size": base_size,
        "axes.titlesize": base_size + 1.5,
        "axes.labelsize": base_size,
        "xtick.labelsize": base_size - 1,
        "ytick.labelsize": base_size - 1,
        "legend.fontsize": base_size - 1,
        "figure.titlesize": base_size + 6,
        "axes.titleweight": "bold",
        "font.weight": "normal",
        "pdf.fonttype": 42,   # embed TrueType, not Type-3 outlines
        "ps.fonttype": 42,
        "svg.fonttype": "none",
    })


def mono_ticklabels(*axes) -> None:
    """Set the tick labels on each given axis to IBM Plex Mono.

    Call this after the ticks are fixed (``set_xticks`` / ``set_yticks``) and
    before ``savefig`` so the mono label artists are the ones drawn. Numeric
    tick labels in a monospace face are the atlas house convention."""
    for ax in axes:
        for lab in (*ax.get_xticklabels(), *ax.get_yticklabels()):
            lab.set_fontfamily(FONT_MONO)


def clean(s: str) -> str:
    """Return ``s`` unchanged if it carries no machine-default dash punctuation,
    else raise ``ValueError``.

    Rejects any em dash. Rejects en dashes used as prose (with whitespace on
    either side, or dangling at a boundary). Allows en dashes tightly set inside
    a numeric / date range, e.g. ``"2015–2025"`` or ``"Aug 20–Sep 5"``.
    """
    if EM_DASH in s:
        raise ValueError(
            f"em dash (U+2014) is not allowed in figure text: {s!r}. "
            "Rewrite it as a colon, comma, or period."
        )
    for m in re.finditer(EN_DASH, s):
        i = m.start()
        before = s[i - 1] if i > 0 else ""
        after = s[i + 1] if i + 1 < len(s) else ""
        prose = (before == "" or after == "" or before.isspace() or after.isspace())
        if prose:
            raise ValueError(
                f"en dash (U+2013) used as prose in figure text: {s!r}. "
                "Keep en dashes only tightly set inside a numeric range "
                "(e.g. '2015–2025'); use a colon, comma, or period otherwise."
            )
    return s


# Register on import so family names resolve for any importer.
register_fonts()
