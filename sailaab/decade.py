# sailaab/decade.py
"""Run manifest for the 2015-2025 decade batch (pure logic, no EE)."""

from sailaab import config
from sailaab.windows import monsoon_windows


def run_manifest(years: list[int] | None = None) -> list[dict]:
    years = config.YEARS if years is None else years
    rows = []
    for y in years:
        pre = (f"{y}-{config.PRE_SEASON_MD[0]}", f"{y}-{config.PRE_SEASON_MD[1]}")
        for w0, w1 in monsoon_windows(y):
            rows.append(
                {
                    "year": y,
                    "window": (w0, w1),
                    "pre": pre,
                    "export_name": f"sailaab_decade_{y}_{w0.replace('-', '')}",
                }
            )
    return rows
