# The flood timelapse — `atlas/web/timelapse_2025.{gif,mp4}`

The animated day-by-day reveal of the Aug–Sep 2025 flood swallowing Punjab's
river corridors. Regenerated deterministically from the git-ignored GFM day tifs
by `pipeline/make_timelapse.py` (rasterio + PIL; same input → identical output).
The cumulative-union area figure reuses the repo's cos²(lat)-corrected estimator
`sailaab.gfm.web_mercator_area_km2` (`tests/test_gfm.py`), so the annotated km²
matches the atlas everywhere else.

```
# from the repo root, on a tree that has data/gfm/2025/ on disk:
python pipeline/make_timelapse.py
#   -> atlas/web/timelapse_2025.gif    (1280x1120, 18 GIF frames, 309 KB)
#   -> atlas/web/timelapse_2025.mp4    (1280x1120, H.264, 16.4 s, 844 KB)
#   -> atlas/timelapse_final_still.png (1280x1120, 130 KB)
```

The GFM tifs are `.gitignore`d (`data/gfm/`), so they are absent from throwaway
worktrees. Point the script at wherever they live with
`--gfm-dir /path/to/data/gfm/2025 --refwater /path/to/gfm_punjab_refwater.tif`;
the committed outputs were rendered from `data/gfm/2025/` in the main tree.

## What it shows

A **cumulative** reveal, not a per-day flicker: each frame is the running union
of every GFM observation up to that date, minus permanent water, painted bright
cyan. The pixels that *first* turned to water on that day flash brighter
(`#8ff0e5`), so a visible wavefront sweeps down the Ravi/Beas/Sutlej corridors.
Permanent water (rivers, canals, Harike, the BBMB reservoirs) sits underneath in
steel blue; district hairlines and a bottom progress bar give context. A running
counter reads the cumulative "km² beyond permanent water" and the day's delta.
The clip ends on a ~5 s hold of the full extent — **2,951 km² beyond permanent
water**.

The two visual screams line up exactly with the causal figure's rainfall spike
and forced releases: **+1,752 km² on 27 Aug** (the day after the 26 Aug
≈10×-normal rain) and **+341 km² on 4 Sep** (the Bhakra release peak).

## Days used (17 frames, Aug 15 → Sep 15 2025)

Every GFM day tif available in the window is used, one frame each, chronologically.
`cum` = cumulative km² beyond permanent water (full-res, cos²-corrected); `+new` =
that day's increment.

| Frame | Date | cum km² | +new km² |
|---|---|---:|---:|
| 1 | 2025-08-15 | 221 | +221 |
| 2 | 2025-08-16 | 250 | +28 |
| 3 | 2025-08-18 | 262 | +12 |
| 4 | 2025-08-20 | 271 | +8 |
| 5 | 2025-08-22 | 300 | +29 |
| 6 | 2025-08-23 | 382 | +83 |
| 7 | 2025-08-27 | 2,134 | **+1,752** |
| 8 | 2025-08-28 | 2,262 | +127 |
| 9 | 2025-08-30 | 2,280 | +18 |
| 10 | 2025-09-01 | 2,303 | +23 |
| 11 | 2025-09-03 | 2,473 | +170 |
| 12 | 2025-09-04 | 2,814 | **+341** |
| 13 | 2025-09-08 | 2,913 | +99 |
| 14 | 2025-09-09 | 2,930 | +17 |
| 15 | 2025-09-11 | 2,943 | +13 |
| 16 | 2025-09-13 | 2,947 | +4 |
| 17 | 2025-09-15 | 2,951 | +4 |

Then **3 hold frames** on the final extent (1.7 s each). PIL merges the identical
hold frames into one GIF frame with the summed 5.1 s duration, so the on-disk GIF
reports 18 frames while the dwell time is exactly 17×0.65 s + 5.1 s ≈ 16.2 s; the
MP4 carries the holds as real repeated frames (493 frames at 30 fps).

## Design decisions

- **Cumulative union, not per-day.** A per-day mask flickers (a corridor seen on
  Aug 27 vanishes on Aug 28 if that swath wasn't re-imaged). The running union
  only ever grows, which is both the honest "flood-to-date" question and far more
  legible. The current day's *new* pixels (`cum_i & ~cum_{i-1}`) are the only
  thing that flashes brighter.
- **Max-pool decimation.** The 3451×3991 ~100 m grid is downsampled to a 934×1080
  map with an area-box reduce thresholded `> 0` (any set source pixel wins), so
  single-pixel river corridors survive. Nearest-neighbour would drop them.
  Max-pool commutes with the cumulative OR, so decimating per day then unioning
  the small arrays equals unioning at full res.
- **Area from full res, cos²-corrected.** The annotated km² is computed on the
  full-resolution union with `web_mercator_area_km2` (per-row inverse-Mercator
  cos² correction across Punjab's ~3° latitude span), never from the decimated
  display raster — the picture is downsampled, the number is not.
- **Palette = the atlas.** ink `#0a1014`, district hairline `#28394a`, permanent
  water `#1a5f8f`, flood-to-date `#4fd8c9`, fresh-today `#8ff0e5`. The map is a
  hard-classified handful of flat colours, which is what keeps the 20-frame GIF at
  309 KB (adaptive 64-colour palette, no dither) — an order of magnitude under the
  7 MB target. No crossfade tweens: they would bloat the palette and blur the
  wavefront; the fresh-today flash carries the per-day motion instead.
- **Type.** DejaVu Sans Mono (bundled with matplotlib, so no new dependency and
  reproducible everywhere) for the IBM-Plex-Mono-style ISO date stamp; overlaid
  on the map's dark corner with a 2 px ink stroke so it stays legible over cyan.
- **MP4 encode.** H.264 / yuv420p, CRF 20, `+faststart`, via whatever `ffmpeg` is
  on `PATH` (frames piped as raw rgb24; each rendered frame held for
  `round(duration·fps)` video frames). If `ffmpeg` is absent the script prints and
  skips the MP4 — the GIF alone is a complete deliverable.

## Dependencies

Uses only libraries already in `requirements.txt` (rasterio, numpy, matplotlib,
pyproj) plus **Pillow (PIL)**, which is already installed as a matplotlib
dependency. No `imageio`/`imageio-ffmpeg` was added; the MP4 goes straight to the
system `ffmpeg`.
