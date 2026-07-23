# sailaab/nowlapse.py
"""Pure logic for the rolling CURRENT-monsoon flood timelapse.

The sibling of ``pipeline/make_timelapse.py`` (the fixed Aug-Sep 2025 product),
but for the season *so far*: every day from 1 June of the current year up to
today (India Standard Time) is a candidate frame, and the animation is refreshed
by CI as new Sentinel-1 passes land.

This module is numpy-only and side-effect free, exactly like ``sailaab.gfm`` and
``sailaab.nowcast``. All network / WMS / PIL / rasterio IO lives in the driver
``pipeline/make_current_timelapse.py``. What lives here:

* IST-aware season-day enumeration (1 Jun of the current year .. today);
* the cumulative-mask update (running union + the pixels that first turned wet
  today) -- the same OR recurrence as ``pipeline/make_timelapse.cumulative_and_fresh``,
  re-implemented here so this module imports without rasterio/matplotlib;
* km^2 from pixel counts given the bounding box's ground area (a flat
  pixel-fraction estimate; the driver passes the cos^2(lat)-corrected bbox area
  from ``sailaab.gfm.web_mercator_area_km2`` so the total is physically right);
* frame-label strings that carry NO em/en dashes -- middots and colons only.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import numpy as np

# India Standard Time is a fixed UTC+05:30 offset (India observes no DST), so a
# plain fixed-offset timezone is exact -- no zoneinfo database dependency.
IST = timezone(timedelta(hours=5, minutes=30))

# The monsoon season window starts 1 June each year.
SEASON_START_MONTH = 6
SEASON_START_DAY = 1


# ---------------------------------------------------------------------------
# date coercion + IST-aware "today" and season-day enumeration
# ---------------------------------------------------------------------------
def _coerce_date(d) -> date:
    """Coerce a ``date`` / ``datetime`` / ``YYYY-MM-DD`` string to a ``date``.

    A ``datetime`` is reduced with ``.date()`` (no timezone shift applied here;
    use :func:`today_ist` to convert an instant to the IST calendar day).
    """
    if isinstance(d, datetime):  # must precede the date check (datetime <: date)
        return d.date()
    if isinstance(d, date):
        return d
    if isinstance(d, str):
        return date.fromisoformat(d[:10])
    raise TypeError(f"cannot coerce {type(d).__name__} to a date")


def today_ist(now: datetime | None = None) -> date:
    """The current calendar day in India Standard Time.

    ``now`` defaults to the real UTC instant. A naive ``now`` is treated as UTC.
    Returns the IST-local ``date`` (so a UTC instant after 18:30 rolls to the
    next Indian day).
    """
    if now is None:
        now = datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return now.astimezone(IST).date()


def season_start(year: int) -> date:
    """1 June of ``year`` -- the first candidate day of the season."""
    return date(year, SEASON_START_MONTH, SEASON_START_DAY)


def season_days(today, year: int | None = None) -> list[str]:
    """ISO days from 1 June of ``year`` (default: ``today``'s year) to ``today``,
    inclusive.

    Returns ``[]`` when ``today`` precedes 1 June (season not yet begun).
    """
    today_d = _coerce_date(today)
    if year is None:
        year = today_d.year
    start = season_start(year)
    if today_d < start:
        return []
    out = []
    cur = start
    while cur <= today_d:
        out.append(cur.isoformat())
        cur += timedelta(days=1)
    return out


# ---------------------------------------------------------------------------
# cumulative-mask update (running union + fresh-today wavefront)
# ---------------------------------------------------------------------------
def update_cumulative(cum, day_mask):
    """Add ``day_mask`` to a running union ``cum``.

    Returns ``(new_cum, fresh)`` where ``fresh`` is the pixels that first turned
    wet on this day (``day_mask & ~cum``). Pass ``cum=None`` for the first day
    (then ``fresh == day_mask``). Adapted from
    ``pipeline/make_timelapse.cumulative_and_fresh`` so this module stays
    numpy-only.
    """
    day = np.asarray(day_mask, dtype=bool)
    if cum is None:
        return day.copy(), day.copy()
    cum = np.asarray(cum, dtype=bool)
    if day.shape != cum.shape:
        raise ValueError(f"shape mismatch: day {day.shape} vs cum {cum.shape}")
    fresh = day & ~cum
    return (cum | day), fresh


def cumulative_and_fresh(day_masks):
    """Yield ``(cum, fresh)`` boolean arrays for each day in ``day_masks``.

    ``cum`` is the running union up to and including this day; ``fresh`` is the
    pixels that first became wet on it. Mirrors
    ``pipeline/make_timelapse.cumulative_and_fresh`` (kept here, numpy-only).
    """
    cum = None
    for m in day_masks:
        cum, fresh = update_cumulative(cum, m)
        yield cum.copy(), fresh


# ---------------------------------------------------------------------------
# km^2 from pixel counts given the bounding box ground area
# ---------------------------------------------------------------------------
def km2_from_pixels(n_pixels, total_pixels, bbox_area_km2) -> float:
    """Ground area (km^2) of ``n_pixels`` out of ``total_pixels`` covering a
    bounding box of ``bbox_area_km2``.

    A flat pixel-fraction estimate: ``n_pixels / total_pixels * bbox_area_km2``.
    The driver passes the cos^2(lat)-corrected bbox area (from
    ``sailaab.gfm.web_mercator_area_km2`` on an all-True grid), so the box total
    is physically exact and only the intra-box distribution is approximated.
    """
    total = int(total_pixels)
    if total <= 0:
        raise ValueError("total_pixels must be positive")
    return float(n_pixels) / float(total) * float(bbox_area_km2)


def mask_km2(mask, bbox_area_km2) -> float:
    """km^2 of the ``True`` pixels in a boolean ``mask`` over a box of
    ``bbox_area_km2`` (via :func:`km2_from_pixels`)."""
    m = np.asarray(mask, dtype=bool)
    return km2_from_pixels(int(m.sum()), int(m.size), bbox_area_km2)


# ---------------------------------------------------------------------------
# frame-label strings -- NO em/en dashes (middots + colons only)
# ---------------------------------------------------------------------------
def fmt_km2(value) -> str:
    """``2951.2 -> '2,951 km2'`` with a superscript two (copied from
    ``pipeline/make_timelapse.fmt_km2``; thousands-separated, no decimals)."""
    return f"{round(value):,} km²"


def pretty_date(d) -> str:
    """``'2026-06-01' -> '01 Jun 2026'`` (day, abbreviated month, year)."""
    return _coerce_date(d).strftime("%d %b %Y")


def season_range_label(start, last) -> str:
    """``('2026-06-01', '2026-07-23') -> '01 Jun · 23 Jul 2026'``.

    Middot separator (never a dash), so the label is safe for the no-dash rule.
    """
    a = _coerce_date(start)
    b = _coerce_date(last)
    return f"{a.strftime('%d %b')} · {b.strftime('%d %b %Y')}"


def kicker(year) -> str:
    """Top-of-frame kicker, e.g. ``'PUNJAB · MONSOON 2026'`` (middot)."""
    return f"PUNJAB · MONSOON {int(year)}"


def delta_label(new_km2) -> str:
    """Today's increment caption, e.g. ``'+12 km2 this day'``."""
    return f"+{fmt_km2(new_km2)} this day"


def coverage_caption(n_covered) -> str:
    """``3 -> '3 days with a Sentinel-1 pass'`` (singular-aware)."""
    n = int(n_covered)
    day_word = "day" if n == 1 else "days"
    return f"{n} {day_word} with a Sentinel-1 pass"
