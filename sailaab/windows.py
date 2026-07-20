# sailaab/windows.py
"""Monsoon-season window generation for the decade batch and forecaster."""

from datetime import date, timedelta

from sailaab import config


def monsoon_windows(
    year: int,
    start_md: str = config.SEASON_START_MD,
    end_md: str = config.SEASON_END_MD,
    window_days: int = config.WINDOW_DAYS,
) -> list[tuple[str, str]]:
    """Contiguous [start, end) windows covering the season; final window
    truncated at season end. Dates are ISO strings (GEE-friendly)."""
    start = date.fromisoformat(f"{year}-{start_md}")
    end = date.fromisoformat(f"{year}-{end_md}")
    out = []
    cur = start
    while cur < end:
        nxt = min(cur + timedelta(days=window_days), end)
        out.append((cur.isoformat(), nxt.isoformat()))
        cur = nxt
    return out
