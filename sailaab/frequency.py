# sailaab/frequency.py
"""Pure logic for the 2015-2025 decade flood-frequency products.

Season-union bookkeeping and frequency counting for the GFM decade batch. Given
per-season boolean flood masks (each = OR of that season's in-window daily masks,
minus reference water), :func:`frequency_count` produces the per-pixel count of
seasons flooded 0..N that becomes ``data/rasters/flood_frequency_2015_2025.tif``.
:func:`window_index` assigns a calendar day to its monsoon window (the half-open
``[start, end)`` windows from :func:`sailaab.windows.monsoon_windows`).
:func:`summarize_repeat_victims` reduces per-season district fractions to the
"repeat victims" recurrence table. :func:`classify_frequency` bins the count
raster into recurrence classes for the atlas legend.

All functions are numpy-only / side-effect free; WMS fetch and rasterio writes
live in ``pipeline/fetch_gfm_decade.py``.
"""

from __future__ import annotations

import numpy as np


def window_index(day: str, windows: list[tuple[str, str]]):
    """Index of the half-open ``[start, end)`` window containing ISO date ``day``.

    ``windows`` is a list of ``(start_iso, end_iso)`` pairs (as produced by
    :func:`sailaab.windows.monsoon_windows`). The start is inclusive and the end
    exclusive, so a day equal to a window's end belongs to the next window, not
    that one. Returns the integer index, or ``None`` if ``day`` lies in no window.
    ISO ``YYYY-MM-DD`` strings compare lexicographically in date order, so no
    parsing is needed.
    """
    for i, (start, end) in enumerate(windows):
        if start <= day < end:
            return i
    return None


def frequency_count(masks):
    """Per-pixel count of ``True`` across an iterable of equal-shape bool masks.

    Each mask is one season's flood union. Returns an ``int32`` array of the same
    shape whose values range ``0..len(masks)``. Raises ``ValueError`` on an empty
    iterable or a shape mismatch.
    """
    out = None
    for m in masks:
        m = np.asarray(m, dtype=bool)
        if out is None:
            out = m.astype(np.int32)
        elif m.shape != out.shape:
            raise ValueError(
                f"shape mismatch in frequency_count: {m.shape} vs {out.shape}"
            )
        else:
            out += m
    if out is None:
        raise ValueError("frequency_count: empty iterable")
    return out


def classify_frequency(freq, edges=(1, 2, 4)):
    """Bin a season-count raster into recurrence classes for the legend.

    With the default ``edges=(1, 2, 4)`` the classes are: ``0`` = never flooded,
    ``1`` = flooded once (1x), ``2`` = 2-3x, ``3`` = >=4x. Class value is the
    number of ``edges`` that ``freq`` is greater-or-equal to, so it generalises to
    any monotone edge tuple.
    """
    freq = np.asarray(freq)
    out = np.zeros(freq.shape, dtype=np.int32)
    for e in edges:
        out += (freq >= e).astype(np.int32)
    return out


def summarize_repeat_victims(per_season, thresholds=(0.01, 0.02)):
    """Reduce per-season district flood fractions to the repeat-victims table.

    Parameters
    ----------
    per_season : dict
        ``district -> list`` of per-season records, each a mapping with keys
        ``"fraction"`` (flooded fraction of the district that season) and
        ``"flooded_ha"`` (flooded hectares that season). One entry per season the
        district was evaluated for; missing/zero seasons should be included as
        ``fraction=0``.
    thresholds : tuple(float, float)
        The two fraction cut-offs reported as ``seasons_with_fraction_gt1pct`` and
        ``seasons_with_fraction_gt2pct`` (strict ``>``). Defaults ``(0.01, 0.02)``.

    Returns
    -------
    dict
        ``district -> {seasons_with_fraction_gt1pct, seasons_with_fraction_gt2pct,
        max_season_fraction, mean_annual_flooded_ha, n_seasons}``. The mean is over
        **all** seasons in the list (zeros included), i.e. mean annual flooded area.
    """
    t1, t2 = thresholds
    out = {}
    for name, records in per_season.items():
        fracs = [float(r["fraction"]) for r in records]
        has = [float(r["flooded_ha"]) for r in records]
        n = len(records)
        out[name] = {
            "seasons_with_fraction_gt1pct": int(sum(1 for f in fracs if f > t1)),
            "seasons_with_fraction_gt2pct": int(sum(1 for f in fracs if f > t2)),
            "max_season_fraction": max(fracs) if fracs else 0.0,
            "mean_annual_flooded_ha": (sum(has) / n) if n else 0.0,
            "n_seasons": n,
        }
    return out
