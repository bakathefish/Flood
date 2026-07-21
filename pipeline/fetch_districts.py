#!/usr/bin/env python
"""Fetch Punjab district polygons (keyless) and write data/punjab_districts.geojson.

Source: datameet/maps Census-2011 district boundaries (ODbL), served raw from
GitHub. We pull the all-India FeatureCollection, keep ST_NM=='Punjab' (20
districts, the Census-2011 / GAUL-2015 vintage the rest of the pipeline uses),
and re-emit a tidy FeatureCollection whose only property is ``district`` (the
datameet DISTRICT spelling). Name reconciliation to the GAUL ADM2_NAME spellings
in ``sailaab.config`` lives in ``sailaab.districts`` (NAME_ALIASES), not here.

No login, no API key. See docs/notes/districts.md for provenance + the mapping
table. Stdlib only (urllib); the geometry is small (~0.4 MB) so no simplify step
is needed to stay well under the 5 MB budget.
"""

import json
import ssl
import urllib.request
from pathlib import Path

SOURCE_URL = (
    "https://raw.githubusercontent.com/datameet/maps/master/"
    "docs/data/geojson/dists11.geojson"
)
STATE = "Punjab"
OUT = Path(__file__).resolve().parents[1] / "data" / "punjab_districts.geojson"


def fetch(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "sailaab/1.0"})
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=120, context=ctx) as resp:
        return json.loads(resp.read())


def build(gj: dict, state: str = STATE) -> dict:
    feats = []
    for f in gj["features"]:
        if f["properties"].get("ST_NM") != state:
            continue
        feats.append(
            {
                "type": "Feature",
                "properties": {"district": f["properties"]["DISTRICT"], "state": state},
                "geometry": f["geometry"],
            }
        )
    feats.sort(key=lambda f: f["properties"]["district"])
    return {
        "type": "FeatureCollection",
        "name": "punjab_districts_census2011_datameet",
        "features": feats,
    }


def main() -> None:
    out = build(fetch(SOURCE_URL))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    # compact separators keep the file small; one line per feature for diffs
    body = ",\n".join(
        json.dumps(feat, separators=(",", ":")) for feat in out["features"]
    )
    OUT.write_text(
        '{"type":"FeatureCollection",'
        f'"name":"{out["name"]}","features":[\n{body}\n]}}\n',
        encoding="utf-8",
    )
    kb = OUT.stat().st_size / 1024
    print(f"wrote {len(out['features'])} districts -> {OUT} ({kb:.0f} KB)")


if __name__ == "__main__":
    main()
