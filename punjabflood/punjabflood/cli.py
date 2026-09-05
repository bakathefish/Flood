"""Command line: the whole chain, one thin command per step.

punjabflood pull-cwc            CWC daily storage 1991 to date (resumable, slow)
punjabflood build-catchments    HydroBASINS polygons, grid weights, IMD coverage weights
punjabflood build-rain          IMD gridded rain 1961 to 2025 as catchment means
punjabflood pull-rain-recent    ERA5 catchment rain for the current year (IMD lags a year)
punjabflood pull-qpf-archive    as-issued lead 1..7 QPF, 2024 to date
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
from punjabflood import cwc, guidebook, imdrain, inflow, rain, reservoirs, verify
from punjabflood.openmeteo import OpenMeteo

app = typer.Typer(add_completion=False, help=__doc__)

DATA = Path("data")
RAW = DATA / "raw"
REF = DATA / "reference"
OUT = Path("outputs")
CWC_CSV = RAW / "cwc" / "cwc_daily.csv"
RAIN_CSV = RAW / "rain" / "catchment_daily.csv"  # IMD history plus ERA5 for the current year
QPF_CSV = RAW / "rain" / "qpf_leads_catchment_daily.csv"
PARAMS_JSON = REF / "inflow_params.json"
GHAGGAR_CLIM_JSON = REF / "ghaggar_season_3day_totals.json"  # committed; lets a runner without
# the raw rain archive place the Ghaggar forecast in the record's percentiles
DAM_NAMES = ("Bhakra", "Pong", "Ranjit Sagar")


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
def build_rain(start_year: int = 1961, end_year: int = 2025):
    """IMD gridded rain as catchment means (IMD-covered part), one row per catchment-day."""
    _log()
    cats = catchments_mod.load_geojson()
    df = imdrain.catchment_daily(range(start_year, end_year + 1), cats)
    RAIN_CSV.parent.mkdir(parents=True, exist_ok=True)
    if RAIN_CSV.exists():
        old = pd.read_csv(RAIN_CSV)
        old = old[old["source"] != "imd"]
        df = pd.concat([df, old], ignore_index=True)
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
def pull_rain_recent(start: str | None = None, end: str | None = None):
    """ERA5 rain over the IMD-covered points for the days the IMD archive does not yet have
    (this year), appended to the same file with source 'era5'."""
    _log()
    cats = catchments_mod.load_geojson()
    today = pd.Timestamp.utcnow().normalize()
    start = start or f"{today.year}-01-01"
    end = end or (today - pd.Timedelta(days=2)).date().isoformat()
    client = OpenMeteo()
    frames = [
        rain.era5_catchment_daily(
            client, c, start, end, years_per_chunk=1, weight_col=imdrain.IMD_WEIGHT_COL
        )
        for c in cats.values()
    ]
    new = pd.concat(frames, ignore_index=True)
    if RAIN_CSV.exists():
        old = pd.read_csv(RAIN_CSV)
        old["date"] = pd.to_datetime(old["date"])
        new["date"] = pd.to_datetime(new["date"])
        keep = ~(
            (old["source"] == "era5") & old["date"].between(new["date"].min(), new["date"].max())
        )
        new = pd.concat([old[keep], new], ignore_index=True)
    new.sort_values(["catchment", "date"]).to_csv(RAIN_CSV, index=False)
    typer.echo(f"wrote {RAIN_CSV} ({client.calls} calls, {client.cache_hits} cache hits)")


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
    pd.concat(frames).to_csv(QPF_CSV, index=False)
    typer.echo(f"wrote {QPF_CSV}")


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


def _covered_area(rain_daily: pd.DataFrame, name: str, fallback: float) -> float:
    r = rain_daily[rain_daily["catchment"] == name]
    if "area_km2_covered" in r and r["area_km2_covered"].notna().any():
        return float(r["area_km2_covered"].dropna().iloc[0])
    return fallback


@app.command("calibrate")
def calibrate():
    """Fit the inflow model per dam on storage changes and catchment rain."""
    _log()
    state, _, _ = _state()
    rain_daily = pd.read_csv(RAIN_CSV)
    cats = catchments_mod.load_geojson()
    params = {}
    for dam in DAM_NAMES:
        r = rain_daily[rain_daily["catchment"] == dam]
        area = _covered_area(rain_daily, dam, cats[dam].area_km2)
        try:
            p = inflow.calibrate(state, r, dam, area)
        except ValueError as exc:
            typer.echo(f"{dam}: {exc}")
            continue
        params[dam] = p.to_dict()
        typer.echo(
            f"{dam}: c={p.c:.3f} w={tuple(round(x, 2) for x in p.w)} rho={p.rho:.3f} "
            f"gamma={p.gamma:.2f} r2={p.r2:.3f} rmse={p.rmse_bcm:.4f} BCM/day n={p.n_days} "
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
    state_measured, _, bulletins = _state()
    state = reservoirs.fill_gaps(state_measured)
    rain_daily = pd.read_csv(RAIN_CSV)
    cats = catchments_mod.load_geojson()
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
            spill_only = verify.routed_next_day_release(pp_event, "Pong", passage=False)
            results["event_timing_spill_only"] = verify.event_timing_test(
                spill_only, peaks_d
            ).to_dict(orient="records")
            if QPF_CSV.exists():
                # what the product would have said: the archived as-issued QPF through the
                # same water balance, one row per issue date and model
                qpf_leads_ev = pd.read_csv(QPF_CSV)
                ai = pd.concat(
                    [
                        verify.as_issued_hei(
                            state_measured,
                            rain_daily,
                            qpf_leads_ev,
                            "Pong",
                            "Pong",
                            params["Pong"],
                            m,
                            horizon_days,
                        )
                        for m in verify.AS_ISSUED_MODELS
                    ],
                    ignore_index=True,
                )
                ai.to_csv(out / "as_issued_event_pong.csv", index=False)
                obs_dates = peaks_d.set_index("year")["date"].to_dict() if "date" in peaks_d else {}
                results["as_issued_events"] = []
                years = sorted(pd.to_datetime(ai["date"]).dt.year.unique()) if len(ai) else []
                for y in years:
                    od = obs_dates.get(int(y))
                    od = None if od is None or od != od else pd.Timestamp(od).date().isoformat()
                    results["as_issued_events"] += verify.as_issued_event_summary(
                        ai, pp_event, int(y), od
                    )

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
        for d in b.index:
            prev = d - pd.Timedelta(days=1)
            if prev not in b.index:
                continue
            hist = rs.reindex(pd.date_range(prev - pd.Timedelta(days=n_hist - 1), prev))
            fut = rs.reindex([d])
            if hist.isna().any() or fut.isna().any():
                continue
            base = inflow.base_from_observed(
                params[dam], float(b.loc[prev, "inflow_cusecs"]), hist.to_numpy()
            )
            vol = inflow.predict_daily_bcm(
                params[dam], fut.to_numpy(), base, rain_mm_recent=hist.to_numpy()
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

    if QPF_CSV.exists():
        qpf_leads = pd.read_csv(QPF_CSV)
        qs = verify.qpf_skill(qpf_leads, rain_daily)
        qs.to_csv(out / "qpf_skill.csv", index=False)
        results["qpf_skill_rows"] = int(len(qs))
        qb = verify.qpf_bias_test(qpf_leads, rain_daily)
        qb.to_csv(out / "qpf_bias_test.csv", index=False)
        results["qpf_bias_rows"] = int(len(qb))

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
