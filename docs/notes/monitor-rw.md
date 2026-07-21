# Secretless live flood monitor (Planetary Computer rewrite)

The 6-hourly monitor was rewritten to need **zero secrets**. It no longer touches
Google Earth Engine or a service-account key; it reads Sentinel-1 RTC from the
**Microsoft Planetary Computer (MPC) anonymous STAC** — the same login-free route
proven in `docs/notes/pc-sar.md` — so the GitHub Action runs green on the public
repo with nothing configured.

## What the Action does (`.github/workflows/monitor.yml`)

Every 6 hours (and on `workflow_dispatch`):

1. `pip install -r requirements.txt`
2. `python -m pytest -q` — never publishes from a red tree.
3. `python -m pipeline.live_monitor` — the secretless monitor (below).
4. Commits any `monitor/` change as **bakathefish <bakathefish@gmail.com>** (the
   repo owner's identity, configured in-workflow) and pushes.

Guards: `concurrency: {group: monitor, cancel-in-progress: false}` so overlapping
schedules queue instead of racing the commit/push, and `timeout-minutes: 25` so a
run caught in an MPC throttling spell is killed cleanly (the watermark is only
advanced on success, so the next run simply retries — no missed passes, no data
loss). The `vars.MONITOR_ENABLED` gate and the `EE_SA_KEY` env are **gone**.

## Why no secrets

`pystac_client.Client.open(STAC, modifier=planetary_computer.sign_inplace)` signs
Azure blob hrefs anonymously (endpoint `.../api/sas/v1/sign`) — no subscription
key, no account. Search + signed COG GETs both succeed unauthenticated. The only
"credential" the job needs is the default `GITHUB_TOKEN` (`permissions:
contents: write`) to push the state commit.

## How the monitor works (`pipeline/live_monitor.py`)

```
MPC STAC search (sentinel-1-rtc, Punjab bbox, last 12 days)
  -> per-scene UTC datetimes
  -> sailaab.monitor.new_scenes() vs monitor/state.json watermark
       no new scenes -> print "no new scenes", exit 0
  -> sailaab.monitor_pc.plan_passes(): which acquisition date(s) to composite
  -> for each new pass date:
       coarse 150 m VV composite of just that pass's scenes (a swath)
       ΔVV = VV_pass − VV_reference        (pre-built composite, below)
       Tier-A mask (sailaab.sar_local) + speckle sieve
       per-district flooded km² (sailaab.districts, polygons reprojected to UTM)
  -> monitor/latest.json  (pass date, per-district km², districts ≥ 25 km²,
                           trilingual alerts from sailaab.alerts)
  -> monitor/latest.png   (statewide VV quicklook + cyan flood overlay)
  -> advance watermark to the latest scene
```

Design constants: `PUNJAB_BBOX = (73.85, 29.53, 76.95, 32.60)`, `LOOKBACK_DAYS =
12` (one S1 revisit), `ALERT_KM2 = 25.0` (district alert floor), `MAX_NEW_SCENES
= 8`.

### Runtime budget (the hard constraint)

MPC's anonymous tier throttles unpredictably — per-scene windowed reads have been
observed anywhere from ~15 s to ~700 s+ for the same window size (consistent with
`docs/notes/pc-sar.md`). The monitor is engineered so a *normal* run stays well
under the 25-minute cap:

- **Coarse 150 m grid** (2003 × 2280, UTM 43N): GDAL pulls a high overview, so
  each scene read is a few MB regardless of throttle — latency-bound, not
  bandwidth-bound.
- **Scenes-only reads**: a single new pass is one relative orbit = ~3–4 frames,
  read in parallel (8-way `ThreadPoolExecutor`, one COG handle per thread). Wall
  time ≈ the slowest single read, not the sum.
- **Backlog guard**: if > `MAX_NEW_SCENES` new scenes appear at once (cold start
  or a long Action outage), only the *latest* date is composited this run
  (`plan_passes` returns `backlog_skipped=True`, dropped dates noted in the JSON);
  the watermark still jumps to the newest scene so the backlog isn't re-read.
- SAS tokens expire ~45–60 min after signing; `pipeline.local_tier_a.read_asset`
  (reused by import) **re-signs on retry**, so a slow run never dies on an expired
  token.

Measured end-to-end (this machine, home link → Azure): **~13 min** for a
cold-start pass composite (3 desc/34 scenes; reads 107 s / 688 s / 731 s in
parallel, so wall time ≈ the slowest read + ~40 s of compute/plot), and
**3.9 s** for a no-new-scenes run (STAC search only). See "Live verification".

**CI is faster than local by construction.** GitHub-hosted runners live in Azure,
the *same cloud that hosts the Planetary Computer blobs*, so on the runner these
COG reads are co-located (seconds, not the minutes a throttled home link sees) and
the job sits comfortably inside `timeout-minutes: 25`. The slow local timings
below reflect home bandwidth (worsened here by a concurrent large download), not
the runner path.

### Reference composite (`monitor/reference_vv_150m.tif`)

The `VV_pre` term of the Tier-A rule is a **pre-built, committed** raster — there
is no per-run baseline fetch, which is what makes a run cheap.

- **Spec**: statewide VV **median** (dB) over the pre-monsoon dry season,
  quantized to **int16 = round(dB × 100)** with `-32768` as nodata, DEFLATE +
  predictor 2, tiled GeoTIFF. Grid: exactly `target_grid(PUNJAB_BBOX, 150)` in
  **EPSG:32643**, so live passes read onto the identical grid and ΔVV is
  pixel-aligned. Codec: `sailaab.monitor_pc.save_reference` / `load_reference`
  (dequantizes to float dB + NaN transparently).
- **Window**: `2026-04-01 .. 2026-05-31` — the *same-year* pre-monsoon dry
  season, the freshest "normal, no standing water" baseline before the 2026
  monsoon (no inter-annual land-use drift). This is a deliberate improvement over
  the config `PRE_2025` / Apr–May 2025 option; `--window` overrides it.
- **Coverage vs cost**: `pipeline.build_reference` takes up to `--per-orbit`
  newest scenes from **each** (orbit_state, relative_orbit) group, so all relative
  orbits — hence the whole state, gap-free — are represented while total scene
  count (and peak RAM for the NaN-median) stays bounded. RTC gamma0 is
  terrain-flattened, so mixing orbits in a *baseline median* is sound; the
  canonical GEE Tier-A (`sailaab.ee_graphs.flood_mask_for_window`) likewise
  medians its pre window over all orbits.
- **Build command** (run once, offline; the Action never rebuilds it):
  `python -m pipeline.build_reference --res 150 --per-orbit 2` (12 scenes: the 2
  newest per orbit across all 6 relative orbits; median-of-2 per swath is
  acceptable for a baseline because each 150 m cell already averages ~15×15
  native 10 m looks, and overlap zones see 4+ scenes). Built 2026-07-21 in
  1,043 s on a home link (2003×2280 grid, valid fraction **0.984**, statewide
  VV median **−8.80 dB**).
- **Size**: **6.65 MB** (6,654,748 B) — far under the 40 MB in-repo commit
  ceiling, so it is committed directly under `monitor/`. (`.gitignore` carries a
  scoped `!monitor/reference_vv_150m.tif` negation because the repo ignores
  `*.tif` globally.)

### Orbit-geometry caveat (documented approximation)

A single live pass images one orbit geometry; the reference is an all-orbit
median. RTC terrain-flattening removes most orbit-dependent backscatter, so the
residual is small next to the −3 dB flood-drop threshold, and the Tier-A
`VV_pre ≥ −15 dB` term still excludes permanent water. A single pass covers only
a **swath**, so districts outside it read 0 km² for that run and `flooded_fraction`
is over the whole district (unimaged = dry); `coverage_fraction` in the JSON
reports how much of Punjab that pass actually saw. This matches the
pre-built-reference design the mission specifies and the conservative posture of
the local Tier-A route.

## Code layout (pure vs IO — repo convention)

| Concern | Module | Tested by |
|---|---|---|
| Watermark (new-scene state) | `sailaab/monitor.py` (unchanged) | `tests/test_monitor.py` |
| Scene grouping, backlog plan, km² shaping, alerts fan-out, reference codec, geom reproject | `sailaab/monitor_pc.py` (new, pure/light-IO) | `tests/test_monitor_pc.py` (14) |
| Tier-A array logic | `sailaab/sar_local.py` (reused) | `tests/test_sar_local.py` |
| District rasterize / reduce | `sailaab/districts.py` (reused) | `tests/test_districts.py` |
| Trilingual alerts | `sailaab/alerts.py` (reused) | `tests/test_alerts.py` |
| STAC / COG IO | `pipeline/local_tier_a.py` (reused **by import**, not edited) | end-to-end run |
| Monitor runner | `pipeline/live_monitor.py` (rewritten, secretless) | end-to-end run |
| Reference builder | `pipeline/build_reference.py` (new, one-time) | end-to-end run |
| Legacy EE monitor | `pipeline/legacy_ee_monitor.py` (old code, verbatim, not in CI) | — |

`sailaab/ee_graphs.py` and the `ee`-marked tests are untouched.

## Live verification (2026-07-21, monsoon active)

Run 1 (`python -m pipeline.live_monitor`, cold start — no watermark yet):

- STAC found **18 scenes across 6 acquisition dates** in the 12-day lookback;
  the backlog guard engaged (`backlog_skipped: true`) and composited only the
  **latest pass, 2026-07-20** (descending/34, 3 scenes, 01:00 UTC), noting the
  skipped dates (07-12, 07-13, 07-15, 07-17, 07-19) in the JSON.
- Pass coverage: **86.7 % of Punjab** imaged by the swath.
- Result: **2.4 km² flooded statewide** — Firozpur 1.6, Tarn Taran 0.5,
  Kapurthala 0.2, Gurdaspur 0.1 km²; **0 districts ≥ 25 km²**, so no alerts.
  Small riverine wet patches along the Sutlej/Beas corridors, hydrologically
  sensible for an active monsoon without a flood event — the honest number.
- Outputs: `monitor/latest.json`, `monitor/latest.png` (VV quicklook + cyan
  mask overlay: rivers dark, cities bright, Ranjit Sagar reservoir visible),
  `monitor/state.json` watermark `2026-07-20T00:59:53Z`.
- Wall time ≈ 13 min on a throttled home link (slowest scene read 731 s).

Run 2 (immediately after): printed **"no new scenes"** and exited 0 in
**3.9 s** — the watermark works; the 6-hourly Action is idle-cheap between
S1 passes.
