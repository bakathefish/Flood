#!/usr/bin/env python
"""Build ``data/punjab_tehsils.geojson`` (tehsil = ADM3 sub-district level).

Source: **geoBoundaries gbOpen IND ADM3** (2018 vintage, CC-BY 4.0), the
documented fallback in ``docs/notes/districts.md`` (datameet/maps carries no
sub-district layer — only Districts / States / constituencies). geoBoundaries
gbOpen ADM3 ships one flat ``shapeName`` per feature and *no* parent-district
field, so each tehsil is assigned to its Punjab district by **spatial
intersection** with the 20 datameet district polygons in
``data/punjab_districts.geojson`` — exactly the keyless, name-join-free route the
notes prescribe.

Pipeline (all pure geometry reused from :mod:`sailaab.tehsils`):

1. download the all-India ADM3 layer (6,824 features) — or read a local ``--src``;
2. keep every tehsil whose area lies **>= 50 % inside** the Punjab state union
   (union of the 20 districts) — the "is this a Punjab tehsil?" test;
3. assign each kept tehsil to its **max-overlap** district (canonical GAUL
   spelling via :func:`sailaab.districts.canonical_name`);
4. **clip** the tehsil to the Punjab union so area + flood stay within-state;
5. normalise the ``shapeName`` (:func:`sailaab.tehsils.normalize_tehsil_name`);
6. emit a tidy FeatureCollection with only ``tehsil`` + ``district`` properties,
   sorted by ``(district, tehsil)`` for stable rasterize labels.

No API key. See ``docs/notes/tehsils.md`` for provenance, the licence, the access
date, and the name-normalisation table.

Usage:
    python pipeline/fetch_tehsils.py                 # download ADM3, build
    python pipeline/fetch_tehsils.py --src ind_adm3.geojson   # use a local copy
"""

from __future__ import annotations

import argparse
import json
import ssl
import urllib.request
from pathlib import Path

from shapely.geometry import mapping, shape
from shapely.ops import unary_union
from shapely.strtree import STRtree

from sailaab.districts import DEFAULT_GEOJSON as DEFAULT_DISTRICTS
from sailaab.districts import canonical_name, load_districts
from sailaab.tehsils import assign_district, normalize_tehsil_name, overlap_fraction

# geoBoundaries gbOpen IND ADM3, pinned release commit (from the /api metadata).
SOURCE_URL = (
    "https://github.com/wmgeolab/geoBoundaries/raw/9469f09/"
    "releaseData/gbOpen/IND/ADM3/geoBoundaries-IND-ADM3.geojson"
)
MIN_IN_PUNJAB = 0.5  # keep a tehsil if >= 50 % of its area is inside Punjab
OUT = Path(__file__).resolve().parents[1] / "data" / "punjab_tehsils.geojson"


def fetch_adm3(src: str | None) -> dict:
    if src:
        return json.loads(Path(src).read_text(encoding="utf-8"))
    req = urllib.request.Request(SOURCE_URL, headers={"User-Agent": "sailaab/1.0"})
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=180, context=ctx) as resp:
        return json.loads(resp.read())


def _clean(geom):
    """Make a geometry valid and drop non-polygonal debris from a clip."""
    if not geom.is_valid:
        geom = geom.buffer(0)
    if geom.geom_type in ("Polygon", "MultiPolygon"):
        return geom
    # GeometryCollection from a border clip -> keep only the polygonal parts
    polys = [g for g in getattr(geom, "geoms", []) if g.geom_type.endswith("Polygon")]
    return unary_union(polys) if polys else geom


def build(adm3: dict, districts_geojson=None):
    dpath = districts_geojson or DEFAULT_DISTRICTS
    pairs = load_districts(dpath, canonicalize=True)
    dgeoms = []  # (canon_name, shapely_geom)
    for name, g in pairs:
        sg = shape(g)
        dgeoms.append((name, sg if sg.is_valid else sg.buffer(0)))
    punjab = unary_union([g for _, g in dgeoms])

    tgeoms, tnames = [], []
    for f in adm3["features"]:
        sg = shape(f["geometry"])
        tgeoms.append(sg if sg.is_valid else sg.buffer(0))
        tnames.append(f["properties"].get("shapeName", ""))

    tree = STRtree(tgeoms)
    feats = []
    for i in tree.query(punjab):  # bbox-prefilter to tehsils near Punjab
        i = int(i)
        tg = tgeoms[i]
        if overlap_fraction(tg, punjab) < MIN_IN_PUNJAB:
            continue
        district, _ = assign_district(tg, dgeoms)
        clipped = _clean(tg.intersection(punjab))
        if clipped.is_empty:
            continue
        feats.append(
            {
                "type": "Feature",
                "properties": {
                    "tehsil": normalize_tehsil_name(tnames[i]),
                    "district": canonical_name(district),
                },
                "geometry": mapping(clipped),
            }
        )
    feats.sort(key=lambda f: (f["properties"]["district"], f["properties"]["tehsil"]))
    return {
        "type": "FeatureCollection",
        "name": "punjab_tehsils_gbOpen_adm3",
        "features": feats,
    }


def _write(fc: dict, out: Path) -> float:
    out.parent.mkdir(parents=True, exist_ok=True)
    body = ",\n".join(
        json.dumps(feat, separators=(",", ":")) for feat in fc["features"]
    )
    out.write_text(
        '{"type":"FeatureCollection",'
        f'"name":"{fc["name"]}","features":[\n{body}\n]}}\n',
        encoding="utf-8",
    )
    return out.stat().st_size / 1e6


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--src", help="local IND ADM3 geojson (default: download)")
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--districts", help="override punjab_districts.geojson path")
    args = ap.parse_args()

    fc = build(fetch_adm3(args.src), districts_geojson=args.districts)
    out = Path(args.out)
    mb = _write(fc, out)

    from collections import Counter

    per_d = Counter(f["properties"]["district"] for f in fc["features"])
    print(f"wrote {len(fc['features'])} tehsils -> {out} ({mb:.2f} MB)")
    for d in sorted(per_d):
        print(f"  {d:28s} {per_d[d]}")
    if mb >= 6.0:
        print(f"WARNING: {mb:.2f} MB exceeds the 6 MB budget -- simplify needed")


if __name__ == "__main__":
    main()
