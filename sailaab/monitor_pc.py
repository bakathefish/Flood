# sailaab/monitor_pc.py
"""Pure logic + reference-raster codec for the secretless Planetary Computer
live monitor.

Scene-date grouping, backlog planning, per-district km² shaping, trilingual
alert fan-out, and the quantized reference-composite codec live here and are
unit-tested against small in-memory inputs. All STAC search / COG IO lives in
``pipeline/live_monitor.py`` — the same pure/IO split as
``sailaab.sar_local`` vs ``pipeline.local_tier_a``.

The watermark itself (``new_scenes`` / ``load_state`` / ``save_state``) stays in
``sailaab.monitor``; this module adds only the Planetary-Computer-specific
grouping and shaping on top of it.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import rasterio

from sailaab.alerts import render_alert

# --- reference quantization -------------------------------------------------
# The pre-built dry-season reference is stored as int16 = round(VV_dB * 100),
# which spans VV's physical range (~-30..+5 dB) with 0.01 dB resolution inside a
# 2-byte cell. QUANT_NODATA (int16 min) doubles as the GeoTIFF nodata value and
# happens to equal RTC's own -32768 sentinel.
QUANT_SCALE = 100.0
QUANT_NODATA = -32768


# --------------------------------------------------------------------------- #
# scene-date grouping / backlog planning
# --------------------------------------------------------------------------- #
def scene_date(iso: str) -> str:
    """ISO acquisition datetime -> UTC calendar date.

    ``'2026-07-20T00:59:03.430430Z' -> '2026-07-20'``. STAC datetimes are always
    UTC (``Z``), so a lexical slice is exact and keeps chronological ordering.
    """
    return iso[:10]


def group_by_date(datetimes) -> dict[str, list[str]]:
    """Map ``YYYY-MM-DD -> sorted [ISO datetimes acquired that date]``."""
    out: dict[str, list[str]] = {}
    for dt in datetimes:
        out.setdefault(scene_date(dt), []).append(dt)
    for d in out:
        out[d].sort()
    return out


def plan_passes(new_iso, max_scenes: int = 8):
    """Decide which acquisition dates this run should composite.

    Returns ``(dates, backlog_skipped)``. Normally every new date is processed
    oldest->newest. If more than ``max_scenes`` new scenes arrived at once (cold
    start, or the Action was paused for a while) only the **latest** date is
    processed, to keep a single run comfortably under the runner budget; then
    ``backlog_skipped`` is ``True`` and the caller notes the dropped dates.
    """
    by = group_by_date(new_iso)
    dates = sorted(by)
    if not dates:
        return [], False
    if len(list(new_iso)) > max_scenes:
        return [dates[-1]], True
    return dates, False


# --------------------------------------------------------------------------- #
# district shaping / alerts
# --------------------------------------------------------------------------- #
def km2(ha: float) -> float:
    """Hectares -> square kilometres."""
    return ha / 100.0


def district_km2_rows(fractions: dict, alert_km2: float):
    """Shape :func:`sailaab.districts.district_fractions` output for JSON.

    ``fractions`` maps district name ->
    ``{flooded_ha, district_ha, flooded_fraction}``. Returns ``(rows, flagged)``:
    ``rows`` sorted by ``flooded_km2`` descending (ties by name) with
    ``flooded_km2`` and ``flooded_fraction`` rounded; ``flagged`` is the subset
    at or above the ``alert_km2`` district alert floor.
    """
    rows = []
    for name, d in fractions.items():
        rows.append(
            {
                "district": name,
                "flooded_km2": round(km2(d["flooded_ha"]), 1),
                "flooded_fraction": round(float(d["flooded_fraction"]), 4),
            }
        )
    rows.sort(key=lambda r: (-r["flooded_km2"], r["district"]))
    flagged = [r for r in rows if r["flooded_km2"] >= alert_km2]
    return rows, flagged


def build_alerts(flagged, trend: str = "stable", langs=("pa", "hi", "en")) -> dict:
    """Render trilingual alert strings for the flagged districts.

    Thin fan-out over :func:`sailaab.alerts.render_alert` so the JSON carries
    ready-to-broadcast Punjabi / Hindi / English copy per flagged district.
    """
    return {
        lang: [
            render_alert(r["district"], r["flooded_km2"], trend, lang) for r in flagged
        ]
        for lang in langs
    }


# --------------------------------------------------------------------------- #
# reference-composite codec (quantized int16 dB GeoTIFF)
# --------------------------------------------------------------------------- #
def quantize_db(arr_db) -> np.ndarray:
    """float VV dB array -> int16 ``round(dB * 100)``; NaN -> ``QUANT_NODATA``."""
    a = np.asarray(arr_db, dtype="float64")
    q = np.where(np.isfinite(a), np.round(a * QUANT_SCALE), QUANT_NODATA)
    q = np.clip(q, -32768, 32767)
    return q.astype("int16")


def dequantize_db(arr_q) -> np.ndarray:
    """int16 ``dB * 100`` -> float VV dB; ``QUANT_NODATA`` -> NaN."""
    a = np.asarray(arr_q)
    out = a.astype("float64") / QUANT_SCALE
    out[a == QUANT_NODATA] = np.nan
    return out


def save_reference(path, arr_db, transform, crs) -> None:
    """Write the quantized reference composite as a DEFLATE GeoTIFF.

    int16, tiled, ``predictor=2`` — a smooth statewide dB field compresses to a
    few MB, well under the 40 MB in-repo commit ceiling the Action depends on.
    """
    q = quantize_db(arr_db)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=q.shape[0],
        width=q.shape[1],
        count=1,
        dtype="int16",
        crs=crs,
        transform=transform,
        nodata=QUANT_NODATA,
        compress="deflate",
        predictor=2,
        tiled=True,
    ) as dst:
        dst.write(q, 1)


def load_reference(path):
    """Read the reference GeoTIFF -> ``(arr_db, transform, crs, width, height)``.

    Dequantizes transparently, so callers see a float dB array with NaN nodata
    on exactly the grid new scenes must be read onto (pixel-aligned ΔVV).
    """
    with rasterio.open(path) as src:
        q = src.read(1)
        return dequantize_db(q), src.transform, src.crs, src.width, src.height


# --------------------------------------------------------------------------- #
# geometry reprojection (lon/lat district polygons -> SAR UTM grid)
# --------------------------------------------------------------------------- #
def reproject_geoms(pairs, src_crs: str = "EPSG:4326", dst_crs: str = "EPSG:32643"):
    """Reproject ``[(name, geojson_geom), ...]`` into ``dst_crs``.

    District polygons ship in lon/lat but the SAR reference / live composites are
    UTM 43N; the polygons must be burned onto that UTM grid to reduce a mask to
    per-district area. Returns pairs with the same names and reprojected GeoJSON
    geometry mappings.
    """
    from pyproj import Transformer
    from shapely.geometry import mapping, shape
    from shapely.ops import transform as shapely_transform

    tr = Transformer.from_crs(src_crs, dst_crs, always_xy=True)

    def _fn(x, y, z=None):
        return tr.transform(x, y)

    return [
        (name, mapping(shapely_transform(_fn, shape(geom)))) for name, geom in pairs
    ]
