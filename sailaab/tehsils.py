# sailaab/tehsils.py
"""Punjab tehsil (ADM3 sub-district) polygons: load, name-normalize, and the
spatial primitives that assign each tehsil to its parent Punjab district.

Tehsil polygons live in ``data/punjab_tehsils.geojson`` (geoBoundaries gbOpen
IND ADM3, 2018 vintage, CC-BY 4.0), built by ``pipeline/fetch_tehsils.py`` which
filters the all-India ADM3 layer to the tehsils that lie majority-inside the
20 datameet Punjab districts and stamps each with a ``district`` property (the
GAUL/``config`` spelling, via :func:`sailaab.districts.canonical_name`) and a
tidy ``tehsil`` name.

Only genuinely new logic lives here; the rasterize / reduce-to-fraction /
repeat-victim machinery is reused from :mod:`sailaab.districts` and
:mod:`sailaab.frequency`. The three functions here are:

* :func:`normalize_tehsil_name` — clean the geoBoundaries ``shapeName`` quirks
  (stray whitespace, ``"- Ii"`` roman-numeral casing) without merging the
  distinct ``-I`` / ``-II`` sub-tehsils.
* :func:`overlap_fraction` — fraction of a geometry's area lying inside a region.
* :func:`assign_district` — argmax-overlap parent district for a tehsil.

``shapely`` (already a repo dependency; see ``docs/notes/districts.md``) supplies
the geometry algebra; :func:`load_tehsils` itself is ``json``-only.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

DEFAULT_GEOJSON = (
    Path(__file__).resolve().parents[1] / "data" / "punjab_tehsils.geojson"
)

# roman numerals a Punjab sub-tehsil suffix can take (Amritsar-I .. -II, etc.)
_ROMAN = {"I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"}
# a trailing " -I" / "- Ii" / " - II" style suffix (separator + short token)
_SUFFIX_RE = re.compile(r"\s*[-\s]\s*([A-Za-z]{1,4})$")


def normalize_tehsil_name(name: str) -> str:
    """Tidy a geoBoundaries ``shapeName`` into a stable display name.

    Collapses runs of whitespace, and rewrites a trailing roman-numeral part
    suffix to a canonical ``-<UPPER>`` form (``"Amritsar -I" -> "Amritsar-I"``,
    ``"Amritsar- Ii" -> "Amritsar-II"``). Distinct parts stay distinct (``-I`` is
    never merged with ``-II``). A trailing short word that is *not* a roman
    numeral (``"Rampura Phul"``, ``"Talwandi Sabo"``) and parenthetical
    qualifiers (``"Ludhiana (East)"``) are left untouched.
    """
    if name is None:
        return name
    cleaned = " ".join(str(name).split()).strip()

    def _repl(m: re.Match) -> str:
        tok = m.group(1).upper()
        return f"-{tok}" if tok in _ROMAN else m.group(0)

    return _SUFFIX_RE.sub(_repl, cleaned)


def overlap_fraction(geom, region) -> float:
    """Fraction of ``geom``'s area that lies inside ``region`` (``0..1``).

    ``geom`` and ``region`` are shapely geometries in a shared CRS. Returns
    ``0.0`` for a degenerate (zero-area) ``geom``. Areas are planar in whatever
    units the geometries carry — callers pass either lon/lat degrees (fine for a
    scale-free ratio at Punjab's latitude) or a projected CRS.
    """
    area = geom.area
    if area <= 0:
        return 0.0
    return geom.intersection(region).area / area


def assign_district(tehsil_geom, district_pairs):
    """Parent district of a tehsil: the district it overlaps most by area.

    ``district_pairs`` is an iterable of ``(name, geometry)``. Returns
    ``(name, fraction)`` where ``name`` is the max-overlap district and
    ``fraction`` is that overlap as a share of the tehsil's own area (a
    confidence: ``~1.0`` for a tehsil nested cleanly inside one district, lower
    for a border tehsil split across a state line). Raises ``ValueError`` on an
    empty ``district_pairs``.
    """
    best_name = None
    best_area = -1.0
    for name, geom in district_pairs:
        inter = tehsil_geom.intersection(geom).area
        if inter > best_area:
            best_area = inter
            best_name = name
    if best_name is None:
        raise ValueError("assign_district: empty district_pairs")
    tarea = tehsil_geom.area
    frac = (best_area / tarea) if tarea > 0 else 0.0
    return best_name, frac


def load_tehsils(path=DEFAULT_GEOJSON, sort: bool = True):
    """Load tehsil polygons from ``data/punjab_tehsils.geojson``.

    Returns a list of ``(tehsil, district, geometry_dict)``. With ``sort=True``
    (default) the list is ordered by ``(district, tehsil)`` so that
    :func:`sailaab.districts.rasterize_districts` assigns stable labels across
    runs. ``geometry_dict`` is the raw GeoJSON geometry mapping, ready for
    ``shapely.geometry.shape`` or ``rasterize_districts``.
    """
    with open(path, encoding="utf-8") as fh:
        gj = json.load(fh)
    feats = gj["features"] if isinstance(gj, dict) else gj
    out = []
    for feat in feats:
        props = feat.get("properties", {})
        out.append((props.get("tehsil"), props.get("district"), feat["geometry"]))
    if sort:
        out.sort(key=lambda t: (t[1] or "", t[0] or ""))
    return out
