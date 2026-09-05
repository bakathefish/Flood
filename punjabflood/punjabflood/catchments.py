"""Catchments above the dams and the Ghaggar index points, from HydroBASINS.

HydroBASINS (Lehner & Grill 2013, v1c, Asia, level 8) gives every sub-basin an id, the id
of the next sub-basin downstream (``NEXT_DOWN``, 0 at a sink) and its own area. The
catchment above a point is the sub-basin that contains the point plus everything that
drains into it, found by walking ``NEXT_DOWN`` links backwards.

Level 8 is coarse: the sub-basin containing a dam also holds some land below the dam. The
resulting areas are compared with the published catchment areas in the tests and the
residuals are reported, not hidden. Rain is sampled on the 0.25 degree grid shared by
ERA5 and the IMD gridded product; every grid point is weighted by the geodesic area of its
cell that lies inside the catchment polygon. Extra weight columns (for example the IMD
coverage weight) travel with the points through the GeoJSON files.

Licence: HydroSHEDS products are free for non-commercial and commercial use with
attribution to the HydroSHEDS project and the cited paper.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import shapefile
from pyproj import Geod
from shapely.geometry import MultiPolygon, Polygon, box, mapping, shape
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from punjabflood import constants as C

GEOD = Geod(ellps="WGS84")
DEFAULT_SHP = Path("data/raw/hydrobasins/hybas_as_lev08_v1c")
DEFAULT_OUT = Path("data/reference/catchments")
# generous window around the Indus and Ghaggar headwaters (lon_min, lat_min, lon_max, lat_max)
WINDOW = (72.0, 27.0, 84.0, 36.0)
GRID_STEP = 0.25  # ERA5 and IMD grids, points at multiples of 0.25 degrees
POINT_KEYS = ("lat", "lon")


@dataclass
class Catchment:
    name: str
    outlet: int
    polygon: BaseGeometry
    area_km2: float
    upstream_ids: frozenset[int]
    points: pd.DataFrame  # columns lat, lon, weight_km2 (+ optional extra weight columns)

    @property
    def n_points(self) -> int:
        return len(self.points)


def geodesic_area_km2(geom: BaseGeometry) -> float:
    """Area on the WGS84 ellipsoid, in km2, for a polygon or multipolygon."""
    if geom.is_empty:
        return 0.0
    if isinstance(geom, MultiPolygon):
        return float(sum(geodesic_area_km2(p) for p in geom.geoms))
    if isinstance(geom, Polygon):
        area, _ = GEOD.geometry_area_perimeter(geom)
        return abs(area) / 1e6
    return float(sum(geodesic_area_km2(g) for g in getattr(geom, "geoms", []) if g.area > 0))


def load_hydrobasins(shp_path: Path = DEFAULT_SHP, window=WINDOW):
    """Return ``(records, geometries)`` keyed by HYBAS_ID for sub-basins whose bounding box
    touches ``window``."""
    sf = shapefile.Reader(str(shp_path))
    fields = [f[0] for f in sf.fields[1:]]
    recs: dict[int, dict] = {}
    geoms: dict[int, BaseGeometry] = {}
    lon0, lat0, lon1, lat1 = window
    for sr in sf.iterShapeRecords():
        b = sr.shape.bbox
        if b[2] < lon0 or b[0] > lon1 or b[3] < lat0 or b[1] > lat1:
            continue
        r = dict(zip(fields, sr.record, strict=True))
        hid = int(r["HYBAS_ID"])
        recs[hid] = r
        geoms[hid] = shape(sr.shape.__geo_interface__)
    return recs, geoms


def upstream_set(outlet: int, recs: dict[int, dict]) -> set[int]:
    """The outlet sub-basin and every sub-basin that drains into it (transitively)."""
    ups: dict[int, list[int]] = {}
    for hid, r in recs.items():
        ups.setdefault(int(r["NEXT_DOWN"]), []).append(hid)
    out = {outlet}
    stack = [outlet]
    while stack:
        h = stack.pop()
        for u in ups.get(h, []):
            if u not in out:
                out.add(u)
                stack.append(u)
    return out


def catchment_polygon(outlet: int, recs, geoms) -> tuple[BaseGeometry, frozenset[int]]:
    ids = upstream_set(outlet, recs)
    poly = unary_union([geoms[h] for h in ids if h in geoms])
    return poly, frozenset(ids)


def sample_grid(polygon: BaseGeometry, step_deg: float = GRID_STEP) -> pd.DataFrame:
    """Grid points at multiples of ``step_deg`` whose cell intersects the polygon, weighted
    by the geodesic area (km2) of the intersection."""
    minx, miny, maxx, maxy = polygon.bounds
    half = step_deg / 2.0
    i0 = int((minx - half) // step_deg)
    i1 = int((maxx + half) // step_deg) + 1
    j0 = int((miny - half) // step_deg)
    j1 = int((maxy + half) // step_deg) + 1
    rows = []
    for i in range(i0, i1 + 1):
        lon = i * step_deg
        for j in range(j0, j1 + 1):
            lat = j * step_deg
            cell = box(lon - half, lat - half, lon + half, lat + half)
            inter = cell.intersection(polygon)
            if inter.is_empty:
                continue
            w = geodesic_area_km2(inter)
            if w <= 0:
                continue
            rows.append({"lat": round(lat, 4), "lon": round(lon, 4), "weight_km2": w})
    df = pd.DataFrame(rows, columns=["lat", "lon", "weight_km2"])
    return df.sort_values(["lat", "lon"]).reset_index(drop=True)


def build(name: str, outlet: int, recs, geoms, step_deg: float = GRID_STEP) -> Catchment:
    poly, ids = catchment_polygon(outlet, recs, geoms)
    return Catchment(
        name=name,
        outlet=outlet,
        polygon=poly,
        area_km2=geodesic_area_km2(poly),
        upstream_ids=ids,
        points=sample_grid(poly, step_deg),
    )


def targets() -> dict[str, int]:
    """Name -> HydroBASINS outlet id for the three dams and the two Ghaggar index points."""
    t = {d.name: d.hydrobasins_outlet for d in C.DAMS.values()}
    for k, v in C.GHAGGAR_BASINS.items():
        t[f"Ghaggar {k}"] = v["hydrobasins_outlet"]
    return t


def build_all(shp_path: Path = DEFAULT_SHP, step_deg: float = GRID_STEP) -> dict[str, Catchment]:
    recs, geoms = load_hydrobasins(shp_path)
    return {name: build(name, outlet, recs, geoms, step_deg) for name, outlet in targets().items()}


def save_geojson(cats: dict[str, Catchment], out_dir: Path = DEFAULT_OUT) -> list[Path]:
    """One GeoJSON per catchment: the polygon feature plus one point feature per grid cell
    carrying every weight column. Downstream modules read these and never touch the 34 MB
    HydroBASINS archive."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name, c in cats.items():
        feats = [
            {
                "type": "Feature",
                "geometry": mapping(c.polygon),
                "properties": {
                    "kind": "catchment",
                    "name": name,
                    "outlet": c.outlet,
                    "area_km2": round(c.area_km2, 1),
                    "n_subbasins": len(c.upstream_ids),
                    "source": C.SRC_HYDROBASINS,
                },
            }
        ]
        weight_cols = [col for col in c.points.columns if col not in POINT_KEYS]
        for row in c.points.itertuples(index=False):
            props = {"kind": "grid_point"}
            for col in weight_cols:
                props[col] = round(float(getattr(row, col)), 3)
            feats.append(
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [row.lon, row.lat]},
                    "properties": props,
                }
            )
        path = out_dir / (name.lower().replace(" ", "_") + ".geojson")
        path.write_text(
            json.dumps({"type": "FeatureCollection", "features": feats}), encoding="utf-8"
        )
        written.append(path)
    return written


def load_geojson(out_dir: Path = DEFAULT_OUT) -> dict[str, Catchment]:
    cats: dict[str, Catchment] = {}
    for path in sorted(Path(out_dir).glob("*.geojson")):
        fc = json.loads(path.read_text(encoding="utf-8"))
        poly_feat = next(f for f in fc["features"] if f["properties"]["kind"] == "catchment")
        pts = []
        for f in fc["features"]:
            if f["properties"]["kind"] != "grid_point":
                continue
            row = {"lat": f["geometry"]["coordinates"][1], "lon": f["geometry"]["coordinates"][0]}
            row.update({k: v for k, v in f["properties"].items() if k != "kind"})
            pts.append(row)
        p = poly_feat["properties"]
        points = pd.DataFrame(pts)
        if points.empty:
            points = pd.DataFrame(columns=["lat", "lon", "weight_km2"])
        cats[p["name"]] = Catchment(
            name=p["name"],
            outlet=int(p["outlet"]),
            polygon=shape(poly_feat["geometry"]),
            area_km2=float(p["area_km2"]),
            upstream_ids=frozenset(),
            points=points,
        )
    return cats
