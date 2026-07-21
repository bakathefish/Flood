# sailaab/duration.py
"""Pure logic for the 2025 submergence-DURATION atlas (how many days each pixel
stayed underwater), the genuinely new product on top of the GFM decade batch.

Submergence duration is **interval-censored**: Sentinel-1 / GFM observe a pixel's
wet/dry state only on the ~1-3-day revisit passes, never continuously, and a ``0``
in a daily mask conflates *observed-dry* with *not-imaged* (no S1 swath). We
therefore compute two bracketing per-pixel estimators from a pixel's sequence of
event-window observations (sorted integer day-numbers ``t_i`` with wet flags
``b_i``; permanent water is subtracted upstream so those flags are already 0):

* :func:`days_observed_wet` — LOWER bound (the committed raster). A day counts as
  underwater only if it is an observed-wet pass or is bridged between two wet
  passes no more than ``max_bridge`` days apart::

      Σ_i b_i  +  Σ_{i : g_i ≤ G} (b_i·b_{i+1})·(g_i − 1)     (g_i = t_{i+1} − t_i)

  i.e. sum over each maximal run of consecutive wet passes of
  ``run_last − run_first + 1``. A dry pass or a gap > G breaks the run.

* :func:`span_duration` — UPPER bound. ``last_wet − first_wet + 1`` (fills the
  interior dry-pass gaps too). By construction
  ``0 ≤ days_observed_wet ≤ span_duration`` pixelwise.

:func:`duration_classes` bins a duration raster into the atlas legend classes
(1-2, 3-6, 7-13, 14+ days). The date helpers :func:`day_offsets` /
:func:`filter_window` turn ISO pass dates into the day-numbers / window selection.

Rationale, the Aug-15 event clock, and the pre-declared checkpoints live in
``docs/notes/duration.md``. All functions here are numpy-only and side-effect
free; WMS/rasterio IO and the products live in ``pipeline/duration_2025.py``.
"""

from __future__ import annotations

from datetime import date

import numpy as np

# Legend / CSV bins. edges (1,3,7,14): 0 = never, 1 = 1-2 d, 2 = 3-6 d,
# 3 = 7-13 d, 4 = 14+ d. The 3-6 / 7-13 split is the agronomic major-vs-total
# paddy submergence-loss boundary (docs/notes/duration.md).
DURATION_CLASS_EDGES = (1, 3, 7, 14)
DURATION_CLASS_LABELS = ("1-2", "3-6", "7-13", "14+")


def day_offsets(day_isos, origin_iso: str) -> np.ndarray:
    """Integer day-numbers of ISO ``YYYY-MM-DD`` dates relative to ``origin_iso``.

    ``day_offsets(["2025-08-15", "2025-08-18"], "2025-08-15") -> array([0, 3])``.
    Dates before the origin give negative numbers.
    """
    o = date.fromisoformat(origin_iso)
    return np.array(
        [(date.fromisoformat(str(d)) - o).days for d in day_isos], dtype=np.int64
    )


def filter_window(day_isos, start_iso: str, end_iso: str) -> list[int]:
    """Indices of ISO days lying in the closed window ``[start_iso, end_iso]``.

    ISO ``YYYY-MM-DD`` strings compare lexicographically in date order, so the
    inclusive bound check needs no parsing. Used to drop the Jun/Jul paddy passes
    (start the event clock at Aug 15) and anything past Sep 30.
    """
    return [i for i, d in enumerate(day_isos) if start_iso <= str(d) <= end_iso]


def _validate(day_numbers, wet):
    dn = np.asarray(day_numbers)
    w = np.asarray(wet, dtype=bool)
    if dn.ndim != 1:
        raise ValueError(f"day_numbers must be 1-D, got shape {dn.shape}")
    if dn.size == 0:
        raise ValueError("day_numbers is empty")
    if w.shape[0] != dn.shape[0]:
        raise ValueError(
            f"wet axis 0 ({w.shape[0]}) must match day_numbers ({dn.shape[0]})"
        )
    if dn.size > 1 and not np.all(np.diff(dn) > 0):
        raise ValueError("day_numbers must be strictly increasing (sorted, unique)")
    return dn, w


def _bcast(vec, ndim):
    """Reshape a length-k 1-D vector to broadcast against a (k, ...) array."""
    return np.asarray(vec).reshape((-1,) + (1,) * (ndim - 1))


def days_observed_wet(day_numbers, wet, max_bridge: int = 4) -> np.ndarray:
    """LOWER-bound submergence duration (days): the wet-bridge estimator.

    ``wet`` is a boolean array whose first axis indexes the observations aligned
    to ``day_numbers`` (a strictly increasing 1-D int array); trailing axes are the
    pixel grid (or absent for a single time series). Returns an ``int64`` array of
    the trailing shape.

    Each wet pass contributes 1 day; each pair of consecutive wet passes separated
    by a gap ``≤ max_bridge`` contributes its ``gap − 1`` unobserved in-between
    days. A dry pass or a gap ``> max_bridge`` breaks the run, so intermittent or
    unconfirmed wetness is never credited (see ``docs/notes/duration.md``).
    """
    if max_bridge < 1:
        raise ValueError("max_bridge must be >= 1")
    dn, w = _validate(day_numbers, wet)

    base = w.sum(axis=0)
    if dn.size == 1:
        return base.astype(np.int64)

    gaps = np.diff(dn)  # (k-1,)
    interior = np.maximum(gaps - 1, 0)
    bridgeable = gaps <= max_bridge
    add_per_pair = interior * bridgeable  # (k-1,) int, in-between days per gap
    both_wet = w[:-1] & w[1:]  # (k-1, ...)
    add = (both_wet * _bcast(add_per_pair, w.ndim)).sum(axis=0)
    return (base + add).astype(np.int64)


def span_duration(day_numbers, wet) -> np.ndarray:
    """UPPER-bound submergence duration (days): ``last_wet − first_wet + 1``.

    Fills every day between a pixel's first and last wet pass, bridging across dry
    / unconfirmed passes too. ``0`` where the pixel is never wet. Same argument
    shapes as :func:`days_observed_wet`; returns an ``int64`` trailing-shape array.
    """
    dn, w = _validate(day_numbers, wet)
    any_wet = w.any(axis=0)
    dnb = _bcast(dn, w.ndim)
    hi = int(dn.max()) + 1
    first = np.where(w, dnb, hi).min(axis=0)
    last = np.where(w, dnb, -1).max(axis=0)
    return np.where(any_wet, last - first + 1, 0).astype(np.int64)


def duration_classes(duration, edges=DURATION_CLASS_EDGES) -> np.ndarray:
    """Bin a duration raster (days) into legend classes.

    Class value = number of ``edges`` that ``duration`` is ``>=`` to. With the
    default ``edges=(1, 3, 7, 14)``: ``0`` = never, ``1`` = 1-2 d, ``2`` = 3-6 d,
    ``3`` = 7-13 d, ``4`` = 14+ d. Generalises to any monotone edge tuple.
    """
    d = np.asarray(duration)
    out = np.zeros(d.shape, dtype=np.int32)
    for e in edges:
        out += (d >= e).astype(np.int32)
    return out
