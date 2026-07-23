# Current-season timelapse `atlas/web/timelapse_current.{gif}`

A rolling reveal of the flood extent for the **current** monsoon so far (1 June
of this year to today, India Standard Time), the live sibling of the fixed 2025
`docs/notes/timelapse.md` product. One frame per day that carried a Sentinel-1
pass; the cumulative union grows in the same dark-cartography style (cyan
flood-to-date, brighter fresh-today wavefront, permanent water underneath, a
running km² counter beyond permanent water). Built by
`pipeline/make_current_timelapse.py`, pure logic in `sailaab/nowlapse.py`
(`tests/test_nowlapse.py`).

- **Source / layer.** Copernicus Global Flood Monitoring (GFM) observed flood
  extent via the keyless GloFAS WMS (`ows.globalfloods.eu`), decoded with
  `sailaab.gfm`. Days imaged by S1 are found via the `gfm_sentinel_1_footprint`
  layer; days with no pass are skipped (no frame), so the clip is honest about
  where the satellite actually looked.
- **Refresh cadence.** Regenerated every monitor CI cycle (6-hourly). Decoded
  daily masks are cached under `data/gfm/current/` (git-ignored), so a rerun
  only fetches new days plus a short trailing window (recent S1 scenes are still
  being processed by GFM, so the last 10 days are always refreshed). The manifest
  `monitor/current_timelapse.json` records `season_start`, `last_day`,
  `days_with_coverage`, and `cumulative_km2`.
- **Caveat (read this).** GFM is a Sentinel-1-derived product with its own SAR
  flood algorithm (its own commission/omission error), not ground truth. Crucially,
  **June and July are Punjab's paddy-transplant season**: flood-irrigated rice
  fields are standing water, so GFM's observed-water layer paints most of the
  plains cyan long before any disaster flood. That is exactly why the forecaster
  is paddy-filtered to core-season windows (`window_start` >= 25 July, see
  `docs/notes/forecaster.md`), and it is why the early-season cumulative km² here
  is large (paddy, not flooding). This clip shows observed surface water beyond
  permanent water, honestly labelled with GFM's own layer name; treat pre-25-July
  extent as transplant inundation. km² is a pixel-fraction estimate of the
  cos²(lat)-corrected bounding-box area (validated within ~1% of the per-row
  estimator). It shows what the satellite observed, refreshed as the season unfolds.
