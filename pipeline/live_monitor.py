# pipeline/live_monitor.py
"""6-hourly live flood monitor: ZERO secrets, Microsoft Planetary Computer.

Queries the anonymous MPC STAC for Sentinel-1 RTC scenes over Punjab in the last
``LOOKBACK_DAYS`` days, advances the ``monitor/state.json`` watermark
(:mod:`sailaab.monitor`), and for each genuinely new acquisition date builds a
coarse (150 m) VV composite of just that pass, diffs it against the committed
pre-monsoon reference composite (``monitor/reference_vv_150m.tif``), applies the
Tier-A rule (:mod:`sailaab.sar_local`), reduces the mask to per-district flooded
km² (:mod:`sailaab.districts`), and writes ``monitor/latest.json`` +
``monitor/latest.png``. No new scenes -> print and exit 0.

No Earth Engine, no service account, no subscription key: MPC asset signing is
anonymous. The legacy EE path is preserved verbatim in
``pipeline/legacy_ee_monitor.py``. Heavy STAC/COG IO is reused by import from
``pipeline.local_tier_a`` (unchanged); pure grouping/shaping/codec logic is in
``sailaab.monitor_pc`` (unit-tested).

Runtime is kept under the runner budget by: coarse 150 m grid, reading only the
new pass's scenes (a swath, not the whole archive), and processing the latest
date only when a backlog of >``MAX_NEW_SCENES`` scenes arrives at once.
"""

from __future__ import annotations

import json
import os
import textwrap
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

from pipeline.local_tier_a import (
    composite_window,
    open_client,
    search_window,
)
from sailaab import figstyle
from sailaab.districts import district_fractions, load_districts, rasterize_districts
from sailaab.monitor import load_state, new_scenes, save_state
from sailaab.monitor_pc import (
    build_alerts,
    district_km2_rows,
    group_by_date,
    load_reference,
    plan_passes,
    reproject_geoms,
)
from sailaab.sar_local import sieve_mask, tier_a_mask

PUNJAB_BBOX = (73.85, 29.53, 76.95, 32.60)
COLLECTION = "sentinel-1-rtc"
REF_PATH = Path("monitor/reference_vv_150m.tif")
STATE = Path("monitor/state.json")
LATEST = Path("monitor/latest.json")
LATEST_PNG = Path("monitor/latest.png")

LOOKBACK_DAYS = 12  # one S1 revisit cycle
ALERT_KM2 = 25.0  # district alert floor
MAX_NEW_SCENES = 8  # above this, composite the latest date only (backlog guard)

SOURCE = "Sentinel-1 RTC via Microsoft Planetary Computer (anonymous STAC)"
REFERENCE_DESC = "pre-monsoon VV dry-season median, 150 m (see monitor/reference)"


def _pixel_area_ha(transform) -> float:
    return abs(transform.a) * abs(transform.e) / 1e4


def _district_labels(transform, width, height, crs):
    """Rasterize the 20 Punjab districts onto the SAR UTM grid.

    Polygons ship in lon/lat; they are reprojected to the reference CRS and burnt
    with :func:`sailaab.districts.rasterize_districts` (label i+1 for the i-th
    district, background 0). Returns ``(labels, names)`` with GAUL spellings.
    """
    districts = load_districts(canonicalize=True)  # [(gaul_name, lonlat_geom)]
    names = [n for n, _ in districts]
    epsg = crs.to_epsg()
    utm_pairs = reproject_geoms(districts, "EPSG:4326", f"EPSG:{epsg}")
    labels = rasterize_districts(utm_pairs, transform, (height, width))
    return labels, names


def process_pass(items, ref_db, transform, width, height, labels, names, px_area_ha):
    """Composite one acquisition date's scenes and reduce to per-district km².

    ΔVV = VV_pass - VV_reference on the shared grid; Tier-A mask + speckle sieve;
    then :func:`sailaab.districts.district_fractions`. Returns the VV dB field,
    the mask, sorted district rows, flagged rows, statewide total km², and the
    fraction of Punjab this pass actually imaged.
    """
    vv_flood = composite_window(items, transform, width, height, asset="vv", tag="pass")
    dvv = vv_flood - ref_db
    valid = np.isfinite(dvv)
    mask = sieve_mask(tier_a_mask(dvv, vv_flood, ref_db))

    fractions = district_fractions(labels, mask, px_area_ha, names=names)
    rows, flagged = district_km2_rows(fractions, ALERT_KM2)
    total_km2 = round(sum(r["flooded_km2"] for r in rows), 1)

    state = labels > 0
    coverage = float((valid & state).sum()) / float(state.sum()) if state.any() else 0.0
    return {
        "vv_flood": vv_flood,
        "mask": mask,
        "rows": rows,
        "flagged": flagged,
        "total_km2": total_km2,
        "coverage": round(coverage, 3),
        "scenes": len(items),
    }


# --------------------------------------------------------------------------- #
# latest-pass PNG (dark house style, matches the atlas figures)
# --------------------------------------------------------------------------- #
# ink ground, cyan Tier-A new water, hairline districts, and a very dark wash
# over land the pass did not image. Kept in this module (not the shared
# local_tier_a._save_overlay_png, which still styles the plain check overlays)
# so the public monitor still reads as one design system.
_INK = "#0a1014"          # figure + axes ground
_WASH = "#0e161d"         # land not imaged this pass (a hair above the ink)
_PAPER = "#e9e4d6"
_PAPER_DIM = "#9aa5a4"
_PAPER_FAINT = "#5c6a70"
_HAIR = "#5c6b82"         # district hairlines
_CHIP_BG = "#12202b"      # legend / no-pass chip fill
_CYAN = (0.20, 0.86, 1.0)  # Tier-A new surface water (echoes the quicklook cyan)


def _rgb(hex_color):
    """``'#rrggbb'`` -> ``(r, g, b)`` floats in [0, 1]."""
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def _rgba8(rgb, alpha):
    """``(r,g,b)`` floats + alpha float -> uint8 RGBA (memory-light overlays)."""
    return (*(int(round(c * 255)) for c in rgb), int(round(alpha * 255)))


def render_latest_png(vv_flood_db, mask, labels, path, *, title, subtitle,
                      footer, status=()):
    """Render ``monitor/latest.png`` as a framed dark-house monitor card.

    The canvas is a ~1200x900 (4:3) ink card with a portrait Punjab map on the
    left and an information column on the right, so the frame stays filled even
    when a single Sentinel-1 pass images only part of the state. The map shows
    the pass's VV backscatter dimmed under the cyan Tier-A inundation, district
    hairlines burnt from ``labels``, and every pixel the pass did NOT image
    washed in a very dark ink (``_WASH``) rather than left as void; when more
    than 15% of Punjab is unimaged a small 'no pass this cycle over this area'
    chip is anchored in the gap. ``title`` (Bricolage bold), ``subtitle`` (Plex
    Sans), the right-column ``status`` lines and ``footer`` (Plex Mono) are all
    guarded against em dashes via :func:`figstyle.clean`.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    from matplotlib.patches import Rectangle

    figstyle.apply()

    vv = np.asarray(vv_flood_db, dtype="float64")
    m = np.asarray(mask, dtype=bool)
    lab = np.asarray(labels)
    inside = lab > 0
    valid = np.isfinite(vv)
    uncovered = inside & ~valid
    uncov_frac = float(uncovered.sum()) / float(inside.sum()) if inside.any() else 0.0

    # crop window: district bounding box + a small margin, so Punjab fills the map
    ys, xs = np.where(inside if inside.any() else valid)
    r0, r1, c0, c1 = int(ys.min()), int(ys.max()), int(xs.min()), int(xs.max())
    mr = max(1, round(0.03 * (r1 - r0)))
    mc = max(1, round(0.03 * (c1 - c0)))
    r0, r1 = max(0, r0 - mr), min(lab.shape[0] - 1, r1 + mr)
    c0, c1 = max(0, c0 - mc), min(lab.shape[1] - 1, c1 + mc)

    fig = plt.figure(figsize=(9.6, 7.2), dpi=125)
    fig.patch.set_facecolor(_INK)

    # title block (top, full width, left aligned)
    fig.text(0.045, 0.945, figstyle.clean(title), color=_PAPER, fontsize=20,
             fontfamily=figstyle.FONT_DISPLAY, fontweight="bold", va="top")
    fig.text(0.045, 0.898, figstyle.clean(subtitle), color=_PAPER_DIM,
             fontsize=11.5, fontfamily=figstyle.FONT_BODY, va="top")

    # map axes (left, portrait, honest equal aspect)
    ax = fig.add_axes([0.045, 0.070, 0.545, 0.780])
    ax.set_facecolor(_INK)

    # land the pass did not image: a very dark wash over the ink (under all else)
    wash = np.zeros((*lab.shape, 4), np.uint8)
    wash[~valid] = _rgba8(_rgb(_WASH), 1.0)
    ax.imshow(wash, interpolation="nearest", zorder=1)

    # pass VV backscatter where imaged, dimmed so the ink ground dominates
    ax.imshow(np.where(valid, vv, np.nan), cmap="Greys_r", vmin=-25, vmax=0,
              alpha=0.55, interpolation="nearest", zorder=2)

    # cyan Tier-A new surface water
    flood = np.zeros((*m.shape, 4), np.uint8)
    flood[m] = _rgba8(_CYAN, 0.94)
    ax.imshow(flood, interpolation="nearest", zorder=4)

    # district hairlines (edge = label change), over covered + uncovered land
    edges = np.zeros(lab.shape, bool)
    edges[:, 1:] |= lab[:, 1:] != lab[:, :-1]
    edges[1:, :] |= lab[1:, :] != lab[:-1, :]
    hair = np.zeros((*lab.shape, 4), np.uint8)
    hair[edges] = _rgba8(_rgb(_HAIR), 0.55)
    ax.imshow(hair, interpolation="nearest", zorder=5)

    ax.set_xlim(c0, c1)
    ax.set_ylim(r1, r0)  # image orientation (origin upper)
    ax.set_aspect("equal")
    ax.axis("off")

    # 'no pass this cycle over this area' chip, only when the gap is material
    if uncov_frac > 0.15:
        yy, xx = np.where(uncovered)
        ax.text(float(xx.mean()), float(yy.mean()),
                figstyle.clean("no pass this cycle\nover this area"),
                color=_PAPER_DIM, fontsize=8.6, fontfamily=figstyle.FONT_MONO,
                ha="center", va="center", linespacing=1.4, zorder=6,
                bbox=dict(boxstyle="round,pad=0.5", facecolor=_CHIP_BG,
                          edgecolor=_HAIR, linewidth=0.8, alpha=0.92))

    # information column (right): legend chips + status readout
    info = fig.add_axes([0.625, 0.070, 0.345, 0.780])
    info.set_xlim(0, 1)
    info.set_ylim(0, 1)
    info.axis("off")

    y = 0.965
    info.text(0.0, y, "THIS PASS", color=_PAPER_FAINT, fontsize=9.0,
              fontfamily=figstyle.FONT_MONO, va="top")
    y -= 0.056

    def _chip(y, color, label, line=False):
        if line:
            info.add_line(Line2D([0.0, 0.055], [y, y], color=color, lw=2.2,
                                 solid_capstyle="round"))
        else:
            info.add_patch(Rectangle((0.0, y - 0.013), 0.055, 0.026,
                                     facecolor=color, edgecolor=_rgb(_HAIR),
                                     linewidth=0.8))
        info.text(0.085, y, figstyle.clean(label), color=_PAPER_DIM,
                  fontsize=10.5, fontfamily=figstyle.FONT_BODY, va="center")

    _chip(y, _CYAN, "new surface water")
    y -= 0.052
    _chip(y, _rgb(_HAIR), "district boundaries", line=True)
    y -= 0.052
    if uncov_frac > 0.001:
        _chip(y, _rgb(_WASH), "not imaged this pass")
        y -= 0.052

    y -= 0.030
    for i, line in enumerate(status):
        # wrap to the info column; an unwrapped long line runs off the canvas
        for piece in textwrap.wrap(figstyle.clean(line), width=28) or [""]:
            info.text(0.0, y, piece,
                      color=_PAPER if i == 0 else _PAPER_DIM,
                      fontsize=10.8 if i == 0 else 10.0,
                      fontfamily=figstyle.FONT_MONO, va="top")
            y -= 0.050

    # footer attribution (bottom, full width, Plex Mono)
    fig.text(0.045, 0.030, figstyle.clean(footer), color=_PAPER_FAINT,
             fontsize=7.3, fontfamily=figstyle.FONT_MONO, va="bottom")

    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=125, facecolor=_INK, pil_kwargs={"optimize": True})
    plt.close(fig)


def main():
    # Bound each remote COG HTTP request so a stalled socket under MPC's
    # anonymous throttling aborts and is retried (read_asset re-signs + retries)
    # instead of hanging the whole job. Per-request, not per-scene, so
    # slow-but-progressing reads still complete; a genuinely stuck request can't
    # burn the 25-minute runner budget. Overridable from the environment.
    os.environ.setdefault("GDAL_HTTP_TIMEOUT", "120")
    os.environ.setdefault("GDAL_HTTP_MAX_RETRY", "3")
    os.environ.setdefault("GDAL_HTTP_RETRY_DELAY", "3")

    if not REF_PATH.exists():
        raise SystemExit(
            f"missing reference composite {REF_PATH}; build it once with "
            f"`python -m pipeline.build_reference` and commit it."
        )
    ref_db, transform, crs, width, height = load_reference(REF_PATH)
    px_area_ha = _pixel_area_ha(transform)

    now = datetime.now(timezone.utc)
    start = (now - timedelta(days=LOOKBACK_DAYS)).strftime("%Y-%m-%d")
    client = open_client()
    items = search_window(
        client, PUNJAB_BBOX, (start, now.strftime("%Y-%m-%d")), COLLECTION
    )
    iso = sorted(it.properties["datetime"] for it in items)

    fresh = new_scenes(iso, load_state(STATE))
    if not fresh:
        print("no new scenes")
        return

    dates_to_process, backlog = plan_passes(fresh, MAX_NEW_SCENES)
    fresh_by_date = group_by_date(fresh)
    items_by_date: dict[str, list] = {}
    for it in items:
        items_by_date.setdefault(it.properties["datetime"][:10], []).append(it)

    skipped_dates = [d for d in sorted(fresh_by_date) if d not in dates_to_process]
    print(
        f"{len(fresh)} new scene(s) across {len(fresh_by_date)} date(s); "
        f"processing {dates_to_process}"
        + (f" (backlog: skipped {skipped_dates})" if backlog else "")
    )

    labels, names = _district_labels(transform, width, height, crs)

    passes = []
    latest_result = None
    latest_date = dates_to_process[-1]
    for date in dates_to_process:
        res = process_pass(
            items_by_date[date],
            ref_db,
            transform,
            width,
            height,
            labels,
            names,
            px_area_ha,
        )
        passes.append(
            {
                "date": date,
                "scenes": res["scenes"],
                "total_flooded_km2": res["total_km2"],
                "flagged": len(res["flagged"]),
                "coverage_fraction": res["coverage"],
            }
        )
        print(
            f"  {date}: {res['scenes']} scene(s), {res['total_km2']} km² flooded, "
            f"{len(res['flagged'])} district(s) flagged, coverage {res['coverage']:.0%}"
        )
        if date == latest_date:
            latest_result = res

    alerts = build_alerts(latest_result["flagged"], trend="stable")

    LATEST.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": SOURCE,
        "reference": REFERENCE_DESC,
        "lookback_days": LOOKBACK_DAYS,
        "alert_floor_km2": ALERT_KM2,
        "latest_pass": latest_date,
        "latest_pass_utc": fresh[-1],
        "new_scenes": len(fresh),
        "backlog_skipped": backlog,
        "skipped_dates": skipped_dates,
        "coverage_fraction": latest_result["coverage"],
        "total_flooded_km2": latest_result["total_km2"],
        "passes": passes,
        "districts": latest_result["rows"],
        "flagged": latest_result["flagged"],
        "alerts": alerts,
    }
    LATEST.write_text(
        json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8"
    )

    subtitle = (
        f"pass {latest_date}  ·  {latest_result['total_km2']:.0f} km² new surface "
        f"water  ·  {latest_result['coverage']:.0%} of Punjab imaged"
    )
    flagged = latest_result["flagged"]
    if flagged:
        status = [f"{len(flagged)} district(s) at or above {ALERT_KM2:.0f} km²"]
        status += [
            f"{r['district']}  {r['flooded_km2']:.0f} km²" for r in flagged[:6]
        ]
    else:
        status = [f"no district at or above the {ALERT_KM2:.0f} km² alert floor"]
    if backlog:
        status.append(f"backlog: {len(skipped_dates)} earlier date(s) skipped")

    render_latest_png(
        latest_result["vv_flood"],
        latest_result["mask"],
        labels,
        LATEST_PNG,
        title="Punjab flood monitor",
        subtitle=subtitle,
        footer=f"{SOURCE}. Reference: {REFERENCE_DESC}.",
        status=status,
    )

    save_state(STATE, fresh[-1])
    print(
        f"updated: latest pass {latest_date}, {latest_result['total_km2']} km² flooded, "
        f"{len(latest_result['flagged'])} district(s) >= {ALERT_KM2} km²"
    )


if __name__ == "__main__":
    main()
