"""Command line: the whole chain, one thin command per step.

punjabflood pull-cwc            CWC daily storage 1991 to date (resumable, slow)
punjabflood build-catchments    HydroBASINS polygons, grid weights, IMD coverage weights
punjabflood build-rain          IMD gridded rain 1961 to 2025 as catchment means
punjabflood pull-rain-recent    ERA5 catchment rain for the current year (IMD lags a year)
punjabflood pull-qpf-archive    as-issued lead 1..7 QPF, 2024 to date (merges by model and season)
punjabflood pull-soil-moisture  ERA5-Land soil moisture 2015 to 2025 into the rain table
punjabflood digitise-guidebook  WRD tables to CSV with page renders
punjabflood calibrate           inflow parameters per dam -> data/reference/inflow_params.json
punjabflood verify              38-year, event-timing and live tests -> outputs/verification
punjabflood forecast            one live cycle -> outputs/forecast/<date>.json and .md
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pandas as pd
import typer

from punjabflood import catchments as catchments_mod
from punjabflood import constants as C
from punjabflood import cwc, guidebook, hei, imdrain, inflow, rain, reservoirs, verify
from punjabflood.openmeteo import OpenMeteo

app = typer.Typer(add_completion=False, help=__doc__)

DATA = Path("data")
RAW = DATA / "raw"
REF = DATA / "reference"
OUT = Path("outputs")
CWC_CSV = RAW / "cwc" / "cwc_daily.csv"
RAIN_CSV = RAW / "rain" / "catchment_daily.csv"  # IMD history plus ERA5 for the current year
QPF_CSV = RAW / "rain" / "qpf_leads_catchment_daily.csv"
ERA5_SEASON_CSV = RAW / "rain" / "era5_dams_{year}_season.csv"  # ERA5 over the dam
# catchments for one season, the reference the real-time grid is judged against
PARAMS_JSON = REF / "inflow_params.json"
FLOOD_SCALE_ERROR_JSON = REF / "flood_scale_error.json"  # committed; the flood-scale
# spread verify measured, for the product's third spill probability
# the dated 2025 dam events the weather watch is scored against: Bhakra's floodgate
# opening (data/reference/bbmb/gate_openings.csv) and the day of the largest dated inflow
# reading at Pong and Ranjit Sagar (data/reference/bbmb/inflow_points.csv)
WATCH_EVENTS_2025 = {"Bhakra": "2025-08-19", "Pong": "2025-08-26", "Ranjit Sagar": "2025-08-27"}
GHAGGAR_CLIM_JSON = REF / "ghaggar_season_3day_totals.json"  # committed; lets a runner without
# the raw rain archive place the Ghaggar forecast in the record's percentiles
DAM_NAMES = ("Bhakra", "Pong", "Ranjit Sagar")
# the flood-scale inflow figures the public record holds (sources inside each file and in
# docs/data-sources.md); the model is checked against them in `verify`
PAC_PERIODS_CSV = REF / "bbmb" / "pac_period_means_2025.csv"
INFLOW_POINTS_CSV = REF / "bbmb" / "inflow_points.csv"
GATE_OPENINGS_CSV = REF / "bbmb" / "gate_openings.csv"  # dated floodgate openings (press)
GAUGE_READINGS_CSV = REF / "wrd" / "gauge_readings_press.csv"  # dated press gauge readings
PRESS_READINGS_CSV = REF / "bbmb" / "press_readings.csv"  # every dated press reading the
# sweeps found (scripts/ingest_readings.py); supersedes inflow_points.csv where present
PRESS_VARIANT = "press inflow fit"
SEASON_PEAKS_CSV = REF / "bbmb" / "season_peak_inflows_2025.csv"
# the inflow-response variant the verification fits and scores beside the response in use
EXCESS_VARIANT = f"excess above {inflow.EXCESS_THRESHOLD_MM:.0f} mm"
# the snowmelt variant: the degree-day melt over the whole Bhakra catchment
# (scripts/pull_snow_bhakra.py writes the table) as a lagged term beside the rain response,
# fitted and judged at Bhakra only under the rule in
# docs/superpowers/plans/2026-09-19-snowmelt-and-watch-hindcast.md
SNOWMELT_VARIANT = "snowmelt"
SNOWMELT_DAMS = ("Bhakra",)
MELT_CSV = RAW / "rain" / "bhakra_melt_daily.csv"


def _log():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


@app.command("pull-cwc")
def pull_cwc(start_year: int = 1991, end_year: int = 2026, months: str = "5,6,7,8,9,10"):
    """Pull the CWC daily storage feed month by month (resumable)."""
    _log()
    get = cwc.make_getter()
    ms = tuple(int(m) for m in months.split(","))
    n = cwc.pull(get, CWC_CSV, years=range(start_year, end_year + 1), months=ms)
    typer.echo(f"appended {n} rows to {CWC_CSV}")


@app.command("build-catchments")
def build_catchments(shp: Path = RAW / "hydrobasins" / "hybas_as_lev08_v1c", imd_year: int = 2023):
    """Upstream sets from HydroBASINS level 8 with IMD coverage weights; writes
    data/reference/catchments/*.geojson."""
    _log()
    cats = catchments_mod.build_all(shp)
    cover = imdrain.coverage_mask(imdrain.open_year(imd_year))
    imdrain.mark_coverage(cats, cover)
    for name, c in cats.items():
        pub = C.DAMS[name].catchment_km2_published if name in C.DAMS else None
        pub_s = f"published {pub.value:,.0f}" if pub else "no published figure"
        typer.echo(
            f"{name}: {c.area_km2:,.0f} km2 ({pub_s}), IMD-covered "
            f"{imdrain.covered_area_km2(c):,.0f} km2, {c.n_points} grid points"
        )
    catchments_mod.save_geojson(cats)


@app.command("build-rain")
def build_rain(start_year: int = 1961, end_year: int = 2025, only: str = ""):
    """IMD gridded rain as catchment means (IMD-covered part), one row per catchment-day.
    ``--only "A,B"`` rebuilds those catchments and keeps every other catchment's rows."""
    _log()
    cats = catchments_mod.load_geojson()
    names = [n.strip() for n in only.split(",") if n.strip()] if only else list(cats)
    missing = [n for n in names if n not in cats]
    if missing:
        raise typer.BadParameter(f"unknown catchment(s): {missing}")
    df = imdrain.catchment_daily(range(start_year, end_year + 1), {n: cats[n] for n in names})
    RAIN_CSV.parent.mkdir(parents=True, exist_ok=True)
    if RAIN_CSV.exists():
        old = pd.read_csv(RAIN_CSV)
        keep = ~(old["source"].isin(["imd", imdrain.RT_SOURCE]) & old["catchment"].isin(names))
        df = pd.concat([df, old[keep]], ignore_index=True)
    # one date format on disk: a partial rebuild mixes fresh Timestamps with the file's
    # strings, and a mixed column would print some rows with a time of day
    df["date"] = pd.to_datetime(df["date"], format="ISO8601").dt.strftime("%Y-%m-%d")
    df = df.sort_values(["catchment", "date"])
    df.to_csv(RAIN_CSV, index=False)
    typer.echo(f"wrote {RAIN_CSV}: {len(df)} rows")
    write_ghaggar_climatology(df)


def write_ghaggar_climatology(rain_daily: pd.DataFrame) -> None:
    from punjabflood import forecast as fc

    imd = rain_daily[rain_daily["source"] == "imd"] if "source" in rain_daily else rain_daily
    years = pd.to_datetime(imd["date"]).dt.year
    fc.save_climatology(
        fc.ghaggar_climatology(imd), GHAGGAR_CLIM_JSON, years=f"{years.min()}-{years.max()}"
    )
    typer.echo(f"wrote {GHAGGAR_CLIM_JSON}")


@app.command("pull-rain-recent")
def pull_rain_recent(
    start: str | None = None, end: str | None = None, source: str = "imd", fetch: bool = True
):
    """Observed rain for the days the IMD archive does not yet have (this year), into the same
    file: with ``--source imd`` (the default) the IMD real-time grid where it has the day
    (source ``imd_rt``; ``--no-fetch`` uses only the files on disk) and ERA5 for the rest;
    with ``--source era5`` ERA5 only. Real-time rows replace ERA5 rows for the same day, and
    ``build-rain`` replaces both when the final year arrives."""
    _log()
    if source not in ("imd", "era5"):
        raise typer.BadParameter("source must be 'imd' or 'era5'")
    cats = catchments_mod.load_geojson()
    today = pd.Timestamp.utcnow().normalize()
    start = start or f"{today.year}-01-01"
    end = end or (today - pd.Timedelta(days=2)).date().isoformat()
    days = pd.date_range(start, end)
    frames = []
    if source == "imd":
        rt_dir = imdrain.realtime_dir()
        with_imd = {n: c for n, c in cats.items() if imdrain.IMD_WEIGHT_COL in c.points}
        present = (
            imdrain.fetch_realtime(days, rt_dir)
            if fetch
            else [d for d in days if imdrain.realtime_path(d, rt_dir).exists()]
        )
        rt = imdrain.catchment_daily_realtime(present, with_imd, rt_dir)
        typer.echo(f"IMD real-time: {len(present)} of {len(days)} days on hand")
        if len(rt):
            frames.append(rt)
    client = OpenMeteo()
    frames += [
        rain.era5_catchment_daily(
            client, c, start, end, years_per_chunk=1, weight_col=imdrain.IMD_WEIGHT_COL
        )
        for c in cats.values()
    ]
    new = merge_recent_rain(pd.read_csv(RAIN_CSV) if RAIN_CSV.exists() else None, frames)
    new.to_csv(RAIN_CSV, index=False)
    typer.echo(f"wrote {RAIN_CSV} ({client.calls} calls, {client.cache_hits} cache hits)")


def merge_recent_rain(old: pd.DataFrame | None, frames: list[pd.DataFrame]) -> pd.DataFrame:
    """One row per catchment and day, the best source kept: final ``imd`` over ``imd_rt``
    over ``era5``. ``frames`` are the fresh pulls; ``old`` the file on disk (its rows of the
    same days and catchments lose to a fresh row of a better or equal source)."""
    rank = {"imd": 0, imdrain.RT_SOURCE: 1, "era5": 2}
    fresh = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    parts = [fresh]
    if old is not None and len(old):
        parts.append(old.assign(_old=1))
    df = pd.concat(parts, ignore_index=True)
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"], format="ISO8601")
    df["_rank"] = df["source"].map(rank).fillna(9)
    df["_old"] = df.get("_old", pd.Series(0, index=df.index)).fillna(0)
    # the soil-moisture columns ride with the day, whichever rain row wins
    sm = [c for c in rain.SM_COLS if c in df.columns]
    if sm:
        carried = df.dropna(subset=sm, how="all").drop_duplicates(["catchment", "date"])
        carried = carried.set_index(["catchment", "date"])[sm]
    df = df.sort_values(["catchment", "date", "_rank", "_old"]).drop_duplicates(
        ["catchment", "date"], keep="first"
    )
    if sm:
        key = pd.MultiIndex.from_frame(df[["catchment", "date"]])
        for c in sm:
            df[c] = df[c].to_numpy() if c in df else float("nan")
            df[c] = pd.Series(df[c].to_numpy(), index=key).fillna(carried[c]).to_numpy()
    df["date"] = df["date"].dt.strftime("%Y-%m-%d")
    return (
        df.drop(columns=["_rank", "_old"]).sort_values(["catchment", "date"]).reset_index(drop=True)
    )


@app.command("pull-era5-season")
def pull_era5_season(year: int = 2025):
    """ERA5 catchment rain over the dam catchments for one June to September season, the
    reference the IMD real-time grid is judged against in ``verify``."""
    _log()
    cats = catchments_mod.load_geojson()
    client = OpenMeteo()
    frames = [
        rain.era5_catchment_daily(
            client,
            cats[d],
            f"{year}-06-01",
            f"{year}-09-30",
            years_per_chunk=1,
            weight_col=imdrain.IMD_WEIGHT_COL,
        )
        for d in DAM_NAMES
        if d in cats
    ]
    path = Path(str(ERA5_SEASON_CSV).format(year=year))
    pd.concat(frames, ignore_index=True).to_csv(path, index=False)
    typer.echo(f"wrote {path} ({client.calls} calls, {client.cache_hits} cache hits)")


@app.command("pull-qpf-archive")
def pull_qpf_archive(models: str = "ecmwf_ifs025,gfs_seamless", seasons: str = "2024,2025,2026"):
    """Archived as-issued lead 1..7 QPF for the monsoon seasons (available from 2024-02)."""
    _log()
    cats = catchments_mod.load_geojson()
    client = OpenMeteo()
    frames = []
    for y in (int(s) for s in seasons.split(",")):
        end = (
            f"{y}-09-30"
            if y < pd.Timestamp.utcnow().year
            else (pd.Timestamp.utcnow().normalize() - pd.Timedelta(days=1)).date().isoformat()
        )
        for name, c in cats.items():
            wc = imdrain.IMD_WEIGHT_COL if name in DAM_NAMES else rain.WEIGHT_COL
            for m in models.split(","):
                frames.append(
                    rain.archived_leads_catchment(client, c, m, f"{y}-06-01", end, weight_col=wc)
                )
    QPF_CSV.parent.mkdir(parents=True, exist_ok=True)
    new = pd.concat(frames, ignore_index=True)
    if QPF_CSV.exists():
        # keep the rows of the models and seasons this pull did not ask for
        new = rain.merge_qpf_leads(pd.read_csv(QPF_CSV), new)
    new.sort_values(["catchment", "model", "lead_days", "target_date"]).to_csv(QPF_CSV, index=False)
    typer.echo(f"wrote {QPF_CSV} ({client.calls} calls, {client.cache_hits} cache hits)")


@app.command("pull-soil-moisture")
def pull_soil_moisture(start: str = "2015-01-01", end: str = "2025-12-31", only: str = ""):
    """ERA5-Land soil moisture (0-7 and 7-28 cm daily means) as catchment means over the
    IMD-covered points of the dam catchments, merged into the rain table's rows by
    (catchment, date). One archive call per point; ``--only "A,B"`` limits the catchments."""
    _log()
    cats = catchments_mod.load_geojson()
    names = [n.strip() for n in only.split(",") if n.strip()] or list(DAM_NAMES)
    client = OpenMeteo()
    frames = [
        rain.era5_catchment_daily(
            client,
            cats[n],
            start,
            end,
            years_per_chunk=11,
            daily=("soil_moisture_0_to_7cm_mean", "soil_moisture_7_to_28cm_mean"),
            weight_col=imdrain.IMD_WEIGHT_COL,
        )
        for n in names
    ]
    new = pd.concat(frames, ignore_index=True)
    merged = rain.merge_soil_moisture(pd.read_csv(RAIN_CSV), new)
    merged.sort_values(["catchment", "date"]).to_csv(RAIN_CSV, index=False)
    filled = int(merged["sm_0_7"].notna().sum())
    typer.echo(
        f"wrote {RAIN_CSV}: {filled} rows carry soil moisture "
        f"({client.calls} calls, {client.cache_hits} cache hits)"
    )


@app.command("digitise-guidebook")
def digitise_guidebook():
    """WRD guidebook tables to data/reference/wrd/*.csv plus page renders for checking."""
    import runpy

    runpy.run_path(
        str(Path(__file__).resolve().parents[1] / "scripts" / "digitise_guidebook.py"),
        run_name="__main__",
    )


def _state(cwc_path: Path = CWC_CSV) -> tuple[pd.DataFrame, dict, pd.DataFrame]:
    src = cwc_path if cwc_path.exists() and cwc_path.stat().st_size > 100 else reservoirs.CWC_LEGACY
    cw = reservoirs.load_cwc(src)
    ratings = reservoirs.fit_ratings(cw)
    cw = reservoirs.reconcile_cwc(cw, ratings)
    n_fix = int((cw["basis"] == "cwc_level").sum())
    if n_fix:
        typer.echo(f"cwc: {n_fix} rows took the rating's storage (stale or inconsistent rows)")
    bulletins = reservoirs.load_bulletins()
    state = reservoirs.daily_state(cw, bulletins, ratings, supplement=reservoirs.load_supplement())
    return state, ratings, bulletins


def _with_melt(rain_daily: pd.DataFrame, melt: pd.DataFrame, cats: dict) -> pd.DataFrame:
    """The rain table with a ``melt_bcm`` column: the catchment melt (mm, from
    ``snow.catchment_melt``) as a volume over the whole catchment area of the catchment
    file (not the IMD-covered part the rain volume uses: the melt comes from every archive
    point). Rows of catchments the melt table lacks get no value."""
    m = melt.copy()
    m["date"] = pd.to_datetime(m["date"]).dt.strftime("%Y-%m-%d")
    m["melt_bcm"] = [
        float(inflow.rain_volume_bcm(v, cats[c].area_km2))
        for v, c in zip(m["melt_mm"], m["catchment"], strict=True)
    ]
    r = rain_daily.copy()
    r["_date"] = pd.to_datetime(r["date"]).dt.strftime("%Y-%m-%d")
    r = r.merge(
        m[["date", "catchment", "melt_bcm"]].rename(columns={"date": "_date"}),
        on=["_date", "catchment"],
        how="left",
    )
    return r.drop(columns="_date")


def _covered_area(rain_daily: pd.DataFrame, name: str, fallback: float) -> float:
    r = rain_daily[rain_daily["catchment"] == name]
    if "area_km2_covered" in r and r["area_km2_covered"].notna().any():
        return float(r["area_km2_covered"].dropna().iloc[0])
    return fallback


def load_press_points() -> pd.DataFrame:
    """The dated press readings with an inflow figure, for the flood-scale check: the merged
    sweep table where it exists (every year, ambiguous rows left out), else the hand-checked
    2023 and 2025 rows. Columns date, dam, inflow_cusecs, source."""
    if PRESS_READINGS_CSV.exists():
        pr = pd.read_csv(PRESS_READINGS_CSV)
        pr = pr[pr["inflow_cusecs"].notna() & ~pr["ambiguous"].astype(bool)].copy()
        pr["source"] = pr["source_title"].fillna("").str.slice(0, 70)
        return pr[["date", "dam", "inflow_cusecs", "source"]].reset_index(drop=True)
    points = pd.read_csv(INFLOW_POINTS_CSV)
    points["source"] = points["source_short"]
    return points[["date", "dam", "inflow_cusecs", "source"]]


def press_inflow_daily(dam: str, up_to_year: int | None = None) -> pd.Series:
    """The dated press readings of a dam's inflow as one value per day (the mean of the
    day's readings, ambiguous rows left out), cusecs indexed by date; empty without the
    merged table."""
    if not PRESS_READINGS_CSV.exists():
        return pd.Series(dtype=float)
    pr = pd.read_csv(PRESS_READINGS_CSV)
    pr = pr[(pr["dam"] == dam) & pr["inflow_cusecs"].notna() & ~pr["ambiguous"].astype(bool)]
    pr["date"] = pd.to_datetime(pr["date"])
    if up_to_year is not None:
        pr = pr[pr["date"].dt.year <= up_to_year]
    return pr.groupby("date")["inflow_cusecs"].mean().sort_index()


def _flood_scale_truth(
    state: pd.DataFrame, event_year: int = 2025
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """The flood-scale inflow figures the record holds, for ``verify.flood_scale_inflow_check``:
    the Public Action Committee period means, the dated press figures, BBMB's own sheets of the
    event year that the Internet Archive kept (from the state, basis ``bbmb``), the season
    peaks stated to the Rajya Sabha, and the record inflow in the Pong emergency action plan.
    Each carries its short source label; the full citations are in the reference tables."""
    periods = pd.read_csv(PAC_PERIODS_CSV)
    periods["source"] = periods["source_short"]
    points = load_press_points()
    sheets = state[
        (state["basis"] == "bbmb")
        & (pd.to_datetime(state["date"]).dt.year == event_year)
        & state["inflow_cusecs"].notna()
    ][["date", "dam", "inflow_cusecs"]].copy()
    sheets["source"] = "BBMB daily sheet, Internet Archive"
    points = pd.concat(
        [points[["date", "dam", "inflow_cusecs", "source"]], sheets], ignore_index=True
    )
    peaks = pd.read_csv(SEASON_PEAKS_CSV)
    peaks["source"] = peaks["source_short"]
    rec = C.PONG.max_observed_inflow_cusecs  # "on 14 August 2023" in its note
    record_days = pd.DataFrame(
        [
            {
                "date": "2023-08-14",
                "dam": "Pong",
                "inflow_cusecs": rec.value,
                "source": "BBMB Pong EAP, largest inflow recorded",
            }
        ]
    )
    return periods, points, peaks, record_days


@app.command("calibrate")
def calibrate(wetness: str = "api"):
    """Fit the inflow model per dam on storage changes and catchment rain. ``--wetness``
    picks the carrier of catchment wetness: api (the five-day rain index), api+sm (the index
    and the ERA5-Land soil-moisture anomaly) or sm (the anomaly alone)."""
    _log()
    state, _, _ = _state()
    rain_daily = pd.read_csv(RAIN_CSV)
    cats = catchments_mod.load_geojson()
    params = {}
    for dam in DAM_NAMES:
        r = rain_daily[rain_daily["catchment"] == dam]
        area = _covered_area(rain_daily, dam, cats[dam].area_km2)
        try:
            p = inflow.calibrate(state, r, dam, area, wetness=wetness)
        except ValueError as exc:
            typer.echo(f"{dam}: {exc}")
            continue
        params[dam] = p.to_dict()
        typer.echo(
            f"{dam}: c={p.c:.3f} w={tuple(round(x, 2) for x in p.w)} rho={p.rho:.3f} "
            f"wetness={p.wetness} gamma={p.gamma:.2f} r2={p.r2:.3f} rmse={p.rmse_bcm:.4f} "
            f"BCM/day n={p.n_days} "
            f"area={area:,.0f} km2"
        )
    PARAMS_JSON.write_text(json.dumps(params, indent=2), encoding="utf-8")
    typer.echo(f"wrote {PARAMS_JSON}")


def load_params(path: Path = PARAMS_JSON) -> dict[str, inflow.InflowParams]:
    d = json.loads(path.read_text(encoding="utf-8"))
    return {k: inflow.InflowParams.from_dict(v) for k, v in d.items()}


@app.command("verify")
def run_verify(horizon_days: int = 5):
    """The three verification tests; writes outputs/verification/*.csv, *.json."""
    _log()
    out = OUT / "verification"
    out.mkdir(parents=True, exist_ok=True)
    state_measured, ratings, bulletins = _state()
    state = reservoirs.fill_gaps(state_measured)
    rain_daily = pd.read_csv(RAIN_CSV)
    cats = catchments_mod.load_geojson()
    if MELT_CSV.exists():
        rain_daily = _with_melt(rain_daily, pd.read_csv(MELT_CSV), cats)
    params = load_params()
    peaks_h = guidebook.load_peaks("harike_hussainiwala")
    peaks_r = guidebook.load_peaks("ropar")
    peaks_d = guidebook.load_peaks("dhilwan")

    pred = None
    for name, c in cats.items():
        rp = verify.rain_predictors(rain_daily, name, _covered_area(rain_daily, name, c.area_km2))
        pred = rp if pred is None else pred.join(rp, how="outer")
    for dam in DAM_NAMES:
        pred = pred.join(verify.storage_predictors(state, dam), how="outer")
    pp_all = []
    for dam in params:
        pp = verify.perfect_prog_hei(state, rain_daily, dam, dam, params[dam], horizon_days)
        if len(pp):
            pp_all.append(pp)
            pred = pred.join(verify.annual_max(pp, "hei", f"{dam}_hei_pp_max"), how="outer")
            pred = pred.join(
                verify.annual_max(pp, "peak_release_cusecs", f"{dam}_release_pp_max"), how="outer"
            )
    if "Bhakra_max5d_bcm" in pred and "Pong_max5d_bcm" in pred:
        pred["sutlej_beas_max5d_bcm"] = pred["Bhakra_max5d_bcm"] + pred["Pong_max5d_bcm"]
        pred["sutlej_beas_max3d_bcm"] = pred["Bhakra_max3d_bcm"] + pred["Pong_max3d_bcm"]
    pred.to_csv(out / "annual_predictors.csv")

    results = {"peak_tests": [], "event_timing": None, "live_2026": {}}
    tests = [
        ("harike_hussainiwala", peaks_h, "harike_us_cusecs"),
        ("ropar", peaks_r, "us_cusecs"),
        ("dhilwan", peaks_d, "discharge_cusecs"),
    ]
    for table, peaks, col in tests:
        pk = peaks.copy()
        if "wrd_class" not in pk:
            pk = pk.join(peaks_h.set_index("year")["wrd_class"], on="year")
        for predictor in pred.columns:
            r = verify.peak_class_test(pred, pk, predictor, peak_col=col)
            r["table"] = table
            results["peak_tests"].append(r)
    pd.DataFrame(
        [{k: v for k, v in r.items() if k != "loyo_probabilities"} for r in results["peak_tests"]]
    ).to_csv(out / "peak_tests.csv", index=False)

    if pp_all:
        pp = pd.concat(pp_all, ignore_index=True)
        pp.to_csv(out / "perfect_prog_hei_daily.csv", index=False)
        if "Pong" in params:
            # event timing: between the sparse measurements of the event weeks the reservoir
            # is carried by the model's own water balance, not by a straight line
            pp_event = verify.perfect_prog_hei(
                state_measured, rain_daily, "Pong", "Pong", params["Pong"], horizon_days, "model"
            )
            pp_event.to_csv(out / "perfect_prog_event_pong.csv", index=False)
            arr = verify.routed_next_day_release(pp_event, "Pong", passage=True)
            arr.to_csv(out / "routed_pong_perfect_prog.csv", index=False)
            results["event_timing"] = verify.event_timing_test(arr, peaks_d).to_dict(
                orient="records"
            )
            if C.flood_cushion("Pong") is not None:
                # the same run with the reservoir allowed to rise to the top of the flood
                # cushion before the spillway must open: the other end of the bracket
                pp_cushion = verify.perfect_prog_hei(
                    state_measured,
                    rain_daily,
                    "Pong",
                    "Pong",
                    params["Pong"],
                    horizon_days,
                    "model",
                    capacity_bcm=C.cushion_capacity_bcm("Pong"),
                )
                pp_cushion.to_csv(out / "perfect_prog_event_pong_cushion.csv", index=False)
                arr_c = verify.routed_next_day_release(pp_cushion, "Pong", passage=True)
                arr_c.to_csv(out / "routed_pong_perfect_prog_cushion.csv", index=False)
                results["event_timing_cushion"] = verify.event_timing_test(arr_c, peaks_d).to_dict(
                    orient="records"
                )
                results["flood_cushion"] = {
                    "dam": "Pong",
                    "top_level_ft": C.flood_cushion("Pong")[0] / C.FOOT_M,
                    "capacity_bcm": C.cushion_capacity_bcm("Pong"),
                    "live_capacity_bcm": C.PONG.live_capacity_bcm.value,
                }
            spill_only = verify.routed_next_day_release(pp_event, "Pong", passage=False)
            results["event_timing_spill_only"] = verify.event_timing_test(
                spill_only, peaks_d
            ).to_dict(orient="records")
            if GAUGE_READINGS_CSV.exists():
                # the dated press readings of the river gauges against the routed release
                gr = pd.read_csv(GAUGE_READINGS_CSV)
                chk = verify.routed_vs_gauge_readings(
                    arr, gr, stations=("Dhilwan", "Harike Head Works", "Ferozepur Head Works")
                )
                chk.to_csv(out / "routed_vs_gauge_readings.csv", index=False)
                results["gauge_readings_check"] = chk.to_dict(orient="records")
        if "Bhakra" in params and C.rule_curve("Bhakra") is not None and GATE_OPENINGS_CSV.exists():
            # the operator's schedule: the day the schedule bound first forces a release in
            # each event season against the dated gate opening, beside the FRL bound
            pp_b = verify.perfect_prog_hei(
                state_measured,
                rain_daily,
                "Bhakra",
                "Bhakra",
                params["Bhakra"],
                horizon_days,
                "model",
            )
            pp_b.to_csv(out / "perfect_prog_event_bhakra.csv", index=False)
            pp_rc = verify.perfect_prog_hei(
                state_measured,
                rain_daily,
                "Bhakra",
                "Bhakra",
                params["Bhakra"],
                horizon_days,
                "model",
                rule_curve_rating=ratings["Bhakra"],
            )
            pp_rc.to_csv(out / "perfect_prog_event_bhakra_rule_curve.csv", index=False)
            openings = pd.read_csv(GATE_OPENINGS_CSV)
            rct = verify.rule_curve_timing_test(pp_b, pp_rc, openings, "Bhakra")
            rct.to_csv(out / "rule_curve_timing.csv", index=False)
            results["rule_curve_timing"] = rct.to_dict(orient="records")
            results["rule_curve"] = {
                "dam": "Bhakra",
                "vintage": C.RULE_CURVE_VINTAGE["Bhakra"],
                "points": [
                    {"month": m, "day": d, "level_ft": lv} for m, d, lv in C.rule_curve("Bhakra")
                ],
                "guideline_2025_08_19_ft": float(
                    C.BHAKRA.extra["rule_curve_guideline_ft_19_aug_2025"].value
                ),
            }
            # the land between Pong and Dhilwan (roadmap, done in the first round): its own
            # rain through a transferred response, added at Dhilwan on the day; Pong's
            # response as the primary transfer, Ranjit Sagar's (the lowest coefficient) as
            # the sensitivity
            local_areas = {
                n: _covered_area(rain_daily, n, cats[n].area_km2)
                for n in C.LOCAL_CATCHMENTS
                if n in cats
            }
            local_by_dam = verify.local_inflow_series(rain_daily, local_areas, params)
            if "Pong" in local_by_dam:
                pd.concat(
                    {
                        f"{n} ({dam})": s
                        for dam, by_cat in local_by_dam.items()
                        for n, s in by_cat.items()
                    },
                    axis=1,
                ).to_csv(out / "local_inflow_daily.csv", index_label="date")
                arr_local = verify.routed_next_day_release(
                    pp_event, "Pong", passage=True, local=local_by_dam["Pong"]
                )
                arr_local.to_csv(out / "routed_pong_perfect_prog_local.csv", index=False)
                results["event_timing_local"] = verify.event_timing_test(
                    arr_local, peaks_d
                ).to_dict(orient="records")
                results["local_inflow_summary"] = verify.local_inflow_summary(
                    local_by_dam["Pong"], arr, peaks_d
                ).to_dict(orient="records")
                if "Ranjit Sagar" in local_by_dam:
                    arr_rs = verify.routed_next_day_release(
                        pp_event, "Pong", passage=True, local=local_by_dam["Ranjit Sagar"]
                    )
                    results["event_timing_local_ranjit_sagar"] = verify.event_timing_test(
                        arr_rs, peaks_d
                    ).to_dict(orient="records")
            # the same run under observed rain for the other dams, saved beside Pong's
            pp_by_dam = {"Pong": pp_event}
            for dam in ("Bhakra", "Ranjit Sagar"):
                if dam in params:
                    pp_by_dam[dam] = verify.perfect_prog_hei(
                        state_measured, rain_daily, dam, dam, params[dam], horizon_days, "model"
                    )
                    pp_by_dam[dam].to_csv(
                        out / f"perfect_prog_event_{dam.lower().replace(' ', '_')}.csv",
                        index=False,
                    )
            # flood scale: the model's one-day inflow against the figures the record holds
            truth = _flood_scale_truth(state_measured)
            fs = verify.flood_scale_inflow_check(pp_by_dam, *truth)
            fs.to_csv(out / "flood_scale_inflow.csv", index=False)
            results["flood_scale_inflow"] = fs.to_dict(orient="records")
            # the response variants, fitted and scored out of sample beside the response in
            # use: a sharper response to heavy rain (threshold excess) and the two
            # soil-moisture wetness carriers; verify.variant_verdict says whether any may
            # replace it
            variants = [
                ("baseline", {}),
                (EXCESS_VARIANT, {"excess_threshold_mm": inflow.EXCESS_THRESHOLD_MM}),
                ("api+sm", {"wetness": "api+sm"}),
                ("sm", {"wetness": "sm"}),
                (SNOWMELT_VARIANT, {"melt": True}),
            ]
            variant_rows: list[dict] = []
            variant_params: dict[tuple[str, str], inflow.InflowParams] = {}
            pp_variant: dict[str, dict] = {n: {} for n, _ in variants if n != "baseline"}
            summaries = {"baseline": verify.flood_scale_summary(fs)}
            fse = verify.flood_scale_error(fs)
            results["flood_scale_error"] = fse
            verify.write_json(
                {
                    **fse,
                    "basis": "log(model / reported) over the Public Action Committee period "
                    "means covered on at least 10 days, 2025; the product samples the spread, "
                    "not the bias",
                },
                FLOOD_SCALE_ERROR_JSON,
            )
            for dam in DAM_NAMES:
                if dam not in params:
                    continue
                r = rain_daily[rain_daily["catchment"] == dam]
                area = _covered_area(rain_daily, dam, cats[dam].area_km2)
                for name, kw in variants:
                    if name == SNOWMELT_VARIANT and (
                        dam not in SNOWMELT_DAMS or "melt_bcm" not in r.columns
                    ):
                        continue
                    try:
                        p_v = inflow.calibrate(state_measured, r, dam, area, **kw)
                    except ValueError as exc:
                        typer.echo(f"{dam} {name}: {exc}")
                        continue
                    variant_params[(dam, name)] = p_v
                    variant_rows.append(
                        {
                            "dam": dam,
                            "variant": name,
                            **inflow.loso_score(
                                state_measured,
                                r,
                                dam,
                                area,
                                kw.get("excess_threshold_mm"),
                                wetness=kw.get("wetness", "api"),
                                melt=kw.get("melt", False),
                            ),
                            "in_sample_rmse_bcm": p_v.rmse_bcm,
                            "c": p_v.c,
                            "c_wet": p_v.c_wet,
                            "w": " ".join(f"{x:.2f}" for x in p_v.w),
                            "c_excess": p_v.c_excess,
                            "w_excess": " ".join(f"{x:.2f}" for x in p_v.w_excess),
                            "wetness": p_v.wetness,
                            "gamma": p_v.gamma,
                            "c_melt": p_v.c_melt,
                            "w_melt": " ".join(f"{x:.2f}" for x in p_v.w_melt),
                            "intercept_bcm_per_day": p_v.intercept_bcm_per_day,
                        }
                    )
                    if name != "baseline":
                        pp_variant[name][dam] = verify.perfect_prog_hei(
                            state_measured, rain_daily, dam, dam, p_v, horizon_days, "model"
                        )
            # the response fitted on the dated press readings of inflow across seasons (moment
            # readings; the years the storage record covers), scored on the storage record
            # fully out of sample and under the same rule as the other variants
            pp_variant[PRESS_VARIANT] = {}
            results["press_inflow_fit"] = {}
            for dam in DAM_NAMES:
                if dam not in params:
                    continue
                daily = press_inflow_daily(dam, up_to_year=pd.Timestamp.utcnow().year - 1)
                r = rain_daily[rain_daily["catchment"] == dam]
                area = _covered_area(rain_daily, dam, cats[dam].area_km2)
                absorb = hei.absorption_cusecs(dam)
                try:
                    p_press = inflow.calibrate_on_inflow(daily, r, dam, area, min_days=30)
                except ValueError as exc:
                    results["press_inflow_fit"][dam] = {
                        "note": str(exc),
                        "n_readings": int(len(daily)),
                    }
                    continue
                p_use = inflow.as_storage_basis(p_press, absorb)
                results["press_inflow_fit"][dam] = {
                    "n_readings": int(len(daily)),
                    "params": p_press.to_dict(),
                    "in_sample": inflow.score_on_inflow(
                        p_press, daily, r, area, absorb, base_from_intercept=True
                    ),
                }
                variant_rows.append(
                    {
                        "dam": dam,
                        "variant": PRESS_VARIANT,
                        **inflow.storage_change_score(p_use, state_measured, r, dam, area),
                        "in_sample_rmse_bcm": p_press.rmse_bcm,
                        "c": p_press.c,
                        "c_wet": p_press.c_wet,
                        "w": " ".join(f"{x:.2f}" for x in p_press.w),
                        "c_excess": 0.0,
                        "w_excess": "",
                        "wetness": p_press.wetness,
                        "gamma": 0.0,
                        "c_melt": 0.0,
                        "w_melt": "",
                        "intercept_bcm_per_day": p_use.intercept_bcm_per_day,
                    }
                )
                pp_variant[PRESS_VARIANT][dam] = verify.perfect_prog_hei(
                    state_measured, rain_daily, dam, dam, p_use, horizon_days, "model"
                )
            if variant_rows:
                loso_df = pd.DataFrame(variant_rows)
                loso_df.to_csv(out / "inflow_variants.csv", index=False)
                verdicts = []
                for name, by_dam in pp_variant.items():
                    if not by_dam or name == SNOWMELT_VARIANT:
                        continue
                    summaries[name] = verify.flood_scale_summary(
                        verify.flood_scale_inflow_check(by_dam, *truth)
                    )
                    verdicts.append(
                        verify.variant_verdict(
                            summaries["baseline"], summaries[name], loso_df, name
                        )
                    )
                results["inflow_variants"] = {
                    "loso": loso_df.to_dict(orient="records"),
                    "flood_scale": summaries,
                    "verdict": next((v for v in verdicts if v["variant"] == EXCESS_VARIANT), None),
                    "verdicts": verdicts,
                }
                # the snowmelt variant is judged at the dams it touches only: the baseline's
                # flood-scale summary over those dams against the variant's
                if pp_variant.get(SNOWMELT_VARIANT):
                    base_sub = verify.flood_scale_summary(fs[fs["dam"].isin(SNOWMELT_DAMS)])
                    var_sub = verify.flood_scale_summary(
                        verify.flood_scale_inflow_check(pp_variant[SNOWMELT_VARIANT], *truth)
                    )
                    p_melt = {
                        d: variant_params[(d, SNOWMELT_VARIANT)]
                        for d in SNOWMELT_DAMS
                        if (d, SNOWMELT_VARIANT) in variant_params
                    }
                    verify.write_json(
                        {d: p.to_dict() for d, p in p_melt.items()},
                        out / "inflow_params_snowmelt.json",
                    )
                    results["snowmelt_verdict"] = {
                        **verify.variant_verdict(
                            base_sub, var_sub, loso_df, SNOWMELT_VARIANT, dams=SNOWMELT_DAMS
                        ),
                        "baseline_flood_scale": base_sub,
                        "variant_flood_scale": var_sub,
                        "params": {
                            d: {
                                "c": p.c,
                                "c_wet": p.c_wet,
                                "c_melt": p.c_melt,
                                "w_melt": list(p.w_melt),
                                "intercept_bcm_per_day": p.intercept_bcm_per_day,
                                "in_sample_rmse_bcm": p.rmse_bcm,
                                "r2": p.r2,
                            }
                            for d, p in p_melt.items()
                        },
                        "melt_table": MELT_CSV.as_posix(),
                    }
                else:
                    results["snowmelt_verdict"] = {
                        "variant": SNOWMELT_VARIANT,
                        "adopt": False,
                        "note": f"no melt table at {MELT_CSV.as_posix()}; run scripts/pull_snow_bhakra.py",
                    }
            if QPF_CSV.exists():
                # what the product would have said: the archived as-issued QPF through the
                # same water balance, one row per issue date, dam and model. The Dhilwan peak
                # is dated in the WRD table (Pong's river); the Ropar peak is not.
                qpf_leads_ev = pd.read_csv(QPF_CSV)
                obs_dates = peaks_d.set_index("year")["date"].to_dict() if "date" in peaks_d else {}
                results["as_issued_events"] = []
                ai_all = []
                for dam, pp_dam in pp_by_dam.items():
                    ai = pd.concat(
                        [
                            verify.as_issued_hei(
                                state_measured,
                                rain_daily,
                                qpf_leads_ev,
                                dam,
                                dam,
                                params[dam],
                                m,
                                horizon_days,
                            )
                            for m in verify.AS_ISSUED_MODELS
                        ],
                        ignore_index=True,
                    )
                    ai_all.append(ai)
                    years = sorted(pd.to_datetime(ai["date"]).dt.year.unique()) if len(ai) else []
                    for y in years:
                        od = obs_dates.get(int(y)) if dam == "Pong" else None
                        od = None if od is None or od != od else pd.Timestamp(od).date().isoformat()
                        results["as_issued_events"] += verify.as_issued_event_summary(
                            ai, pp_dam, int(y), od
                        )
                if ai_all:
                    pd.concat(ai_all, ignore_index=True).to_csv(
                        out / "as_issued_events.csv", index=False
                    )

    qpf_live = pd.read_csv(QPF_CSV) if QPF_CSV.exists() else None
    results["live_horizons"] = []
    for dam in ("Bhakra", "Pong"):
        if dam not in params:
            continue
        b = (
            bulletins[bulletins["dam"] == dam]
            .sort_values("as_on")
            .groupby("date")
            .tail(1)
            .set_index("date")
        )
        r = rain_daily[rain_daily["catchment"] == dam].copy()
        r["date"] = pd.to_datetime(r["date"])
        rs = r.set_index("date")["rain_mm"].sort_index()
        preds, persist = {}, {}
        n_hist = inflow.history_days(params[dam])
        sm = verify.sm_anomaly_series_for(rain_daily, dam, params[dam])
        for d in b.index:
            prev = d - pd.Timedelta(days=1)
            if prev not in b.index:
                continue
            hist = rs.reindex(pd.date_range(prev - pd.Timedelta(days=n_hist - 1), prev))
            fut = rs.reindex([d])
            if hist.isna().any() or fut.isna().any():
                continue
            a = float(sm.get(prev, 0.0)) if sm is not None else 0.0
            base = inflow.base_from_observed(
                params[dam], float(b.loc[prev, "inflow_cusecs"]), hist.to_numpy(), a
            )
            vol = inflow.predict_daily_bcm(
                params[dam], fut.to_numpy(), base, rain_mm_recent=hist.to_numpy(), sm_anom=a
            )
            preds[d] = C.bcm_to_cusec_days(float(vol[0]))
            persist[d] = float(b.loc[prev, "inflow_cusecs"])  # the naive baseline
        obs = b["inflow_cusecs"].astype(float)
        live = verify.live_test(pd.Series(preds), obs)
        base_line = verify.live_test(pd.Series(persist), obs)
        for k in ("bias_pct", "pearson_r", "mae_cusecs"):
            if k in base_line:
                live[f"persistence_{k}"] = base_line[k]
        results["live_2026"][dam] = live
        # the same season one to five days ahead, with observed rain, with the rain forecast
        # issued that day, and by persistence
        lh = verify.live_horizon_test(b, rs, params[dam], qpf_live, dam, sm=sm)
        results["live_horizons"] += lh.to_dict(orient="records")
    if results["live_horizons"]:
        pd.DataFrame(results["live_horizons"]).to_csv(out / "live_horizons.csv", index=False)

    # the same response fitted on the bulletins' measured inflow (the first daily inflow
    # record this project has; one deficit season, in-sample), and the storage-change fit
    # scored against that inflow out of sample; the product keeps the storage-change fit
    results["inflow_calibration_2026"] = {}
    ic_rows = []
    for dam in ("Bhakra", "Pong"):
        if dam not in params:
            continue
        b = bulletins[bulletins["dam"] == dam].copy()
        b["date"] = pd.to_datetime(b["date"])
        daily = b.groupby("date")["inflow_cusecs"].mean().dropna()
        daily = daily[daily.index.year == pd.Timestamp.utcnow().year]
        r = rain_daily[rain_daily["catchment"] == dam]
        area = _covered_area(rain_daily, dam, cats[dam].area_km2)
        absorb = hei.absorption_cusecs(dam)
        entry = {"n_bulletin_days": int(len(daily))}
        try:
            fit = inflow.calibrate_on_inflow(daily, r, dam, area)
            entry["inflow_fit"] = fit.to_dict()
            entry["inflow_fit_in_sample"] = inflow.score_on_inflow(
                fit, daily, r, area, absorb, base_from_intercept=True
            )
        except ValueError as e:
            entry["note"] = str(e)
        entry["storage_fit"] = params[dam].to_dict()
        entry["storage_fit_on_inflow"] = inflow.score_on_inflow(params[dam], daily, r, area, absorb)
        entry["storage_fit_on_inflow_fitted_base"] = inflow.score_on_inflow(
            params[dam], daily, r, area, absorb, fitted_base=True
        )
        results["inflow_calibration_2026"][dam] = entry
        df = inflow.inflow_design(daily, r, area)
        if len(df):
            base_s = max(params[dam].intercept_bcm_per_day + C.cusec_days_to_bcm(absorb), 0.0)
            ic = pd.DataFrame(
                {
                    "date": df.index,
                    "dam": dam,
                    "observed_cusecs": C.bcm_to_cusec_days(df["y"].to_numpy()),
                    "storage_fit_cusecs": C.bcm_to_cusec_days(
                        inflow._quick_from_design(params[dam], df) + base_s
                    ),
                }
            )
            if "inflow_fit" in entry:
                ic["inflow_fit_cusecs"] = C.bcm_to_cusec_days(
                    inflow._quick_from_design(fit, df) + fit.intercept_bcm_per_day
                )
            ic_rows.append(ic)
    if ic_rows:
        pd.concat(ic_rows, ignore_index=True).to_csv(
            out / "inflow_calibration_2026.csv", index=False
        )

    if QPF_CSV.exists():
        qpf_leads = pd.read_csv(QPF_CSV)
        qs = verify.qpf_skill(qpf_leads, rain_daily)
        qs.to_csv(out / "qpf_skill.csv", index=False)
        results["qpf_skill_rows"] = int(len(qs))
        qb = verify.qpf_bias_test(qpf_leads, rain_daily)
        qb.to_csv(out / "qpf_bias_test.csv", index=False)
        results["qpf_bias_rows"] = int(len(qb))
        # the machine-learned model against the primary deterministic model on the days both
        # have; the rule for switching the product's primary is in the function
        from punjabflood import forecast as fc

        results["qpf_model_comparison"] = verify.qpf_model_comparison(
            qpf_leads, rain_daily, fc.INCUMBENT_DETERMINISTIC, "ecmwf_aifs025_single"
        )
        results["qpf_model_comparison"]["primary_in_product"] = fc.PRIMARY_DETERMINISTIC
        # the deterministic models combined against the primary, same rule; the product
        # takes a blend only when the rule passes
        results["qpf_blend_test"] = verify.qpf_blend_test(
            qpf_leads, rain_daily, incumbent=fc.PRIMARY_DETERMINISTIC
        )
        # the weather watch run day by day over the archive, deterministic branch, against
        # the dated 2025 dam events (the score is pre-registered in the plan of 2026-09-19)
        from punjabflood import weather as wx

        wh = verify.weather_watch_hindcast(
            qpf_leads,
            wx.season_3day_climatology(rain_daily, DAM_NAMES),
            events=WATCH_EVENTS_2025,
            primary=fc.PRIMARY_DETERMINISTIC,
            catchments=tuple(DAM_NAMES),
        )
        wh["rows"].to_csv(out / "weather_watch_hindcast.csv", index=False)
        results["weather_watch_hindcast"] = {k: v for k, v in wh.items() if k != "rows"}
        results["weather_watch_hindcast"]["n_rows"] = int(len(wh["rows"]))

    # the in-season observed-rain records against the final IMD grid (the rule for the
    # product's observed record is in the function); the season is the latest one with a
    # final grid, a real-time file and an ERA5 season file
    for year in sorted({int(y) for y in pd.to_datetime(rain_daily["date"]).dt.year}, reverse=True):
        era5_path = Path(str(ERA5_SEASON_CSV).format(year=year))
        rt_dir = imdrain.realtime_dir()
        season = pd.date_range(f"{year}-06-01", f"{year}-09-30")
        final = rain_daily[
            (rain_daily["source"] == "imd") & pd.to_datetime(rain_daily["date"]).isin(season)
        ]
        if not era5_path.exists() or final.empty:
            continue
        with_imd = {n: c for n, c in cats.items() if n in DAM_NAMES}
        rt = imdrain.catchment_daily_realtime(season, with_imd, rt_dir)
        if rt.empty:
            continue
        cmp = verify.realtime_vs_final(final, rt, pd.read_csv(era5_path))
        cmp["season"] = year
        from punjabflood import forecast as fc

        cmp["record_in_product"] = fc.OBSERVED_RECORD
        results["realtime_rain"] = cmp
        pd.DataFrame(cmp["rows"]).to_csv(out / "realtime_rain.csv", index=False)
        break

    verify.write_json(results, out / "results.json")
    typer.echo(
        json.dumps({k: v for k, v in results.items() if k != "peak_tests"}, indent=2, default=str)
    )
    top = sorted(
        (r for r in results["peak_tests"] if "auroc_high" in r), key=lambda r: -r["auroc_high"]
    )[:12]
    for r in top:
        typer.echo(
            f"{r['table']:22s} {r['predictor']:28s} rho={r['spearman_rho']:+.2f} "
            f"auroc_high={r['auroc_high']:.2f} bss={r['brier_skill_score']:+.2f} n={r['n_years']}"
        )


@app.command("forecast")
def run_forecast(issue_date: str | None = None):
    """One live cycle: BBMB bulletin, QPF, index, routing, outputs."""
    _log()
    from punjabflood import forecast as fc

    _, ratings, _ = _state()
    cats = catchments_mod.load_geojson()
    params = load_params()
    rain_daily = pd.read_csv(RAIN_CSV) if RAIN_CSV.exists() else None
    clim = None if rain_daily is not None else fc.load_climatology(GHAGGAR_CLIM_JSON)
    product = fc.run(
        OpenMeteo(),
        cats,
        ratings,
        params,
        issue_date=issue_date,
        rain_daily=rain_daily,
        climatology=clim,
        flood_scale_log_sd=fc.load_flood_scale_error(FLOOD_SCALE_ERROR_JSON),
    )
    typer.echo(fc.render_markdown(product))


@app.command("report")
def run_report(out: Path = Path("docs/verification.md")):
    """Render outputs/verification into docs/verification.md (numbers never typed by hand)."""
    from punjabflood import report

    md = report.render_verification(OUT / "verification", PARAMS_JSON)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md, encoding="utf-8")
    typer.echo(f"wrote {out}")


if __name__ == "__main__":
    app()
