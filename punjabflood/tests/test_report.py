from __future__ import annotations

import json

import pandas as pd

from punjabflood import report


def test_render_verification_from_synthetic_outputs(tmp_path):
    results = {
        "peak_tests": [],
        "event_timing": [
            {
                "year": 2023,
                "predicted_peak_date": "2023-08-16",
                "predicted_peak_cusecs": 150000.0,
                "observed_peak_date": "2023-08-17",
                "observed_peak_cusecs": 237500.0,
                "lag_days": -1,
                "magnitude_ratio": 0.63,
            },
            {"year": 2025, "note": "no predicted release"},
        ],
        "live_2026": {
            "Pong": {
                "n": 20,
                "bias_pct": -12.0,
                "pearson_r": 0.8,
                "mae_cusecs": 5000.0,
                "mean_obs_cusecs": 34000.0,
                "mean_pred_cusecs": 30000.0,
                "persistence_bias_pct": -1.0,
                "persistence_pearson_r": 0.7,
                "persistence_mae_cusecs": 6000.0,
            }
        },
        "as_issued_events": [
            {
                "year": 2025,
                "dam": "Pong",
                "model": "ecmwf_ifs025",
                "issue_days": 46,
                "flagged_days": 9,
                "hit_days": 7,
                "false_flag_days": 2,
                "missed_days": 1,
                "first_flag_issue_date": "2025-08-20",
                "first_hit_issue_date": "2025-08-24",
                "first_hit_spill_day": 2,
                "pp_first_flag_date": "2025-08-22",
                "pp_first_spill_date": "2025-08-26",
                "lead_days_to_pp_spill": 2,
                "observed_peak_date": "2025-08-31",
                "lead_days_to_observed_peak": 7,
                "max_forecast_peak_release_cusecs": 120000.0,
                "pp_peak_day1_release_cusecs": 150000.0,
            },
            {
                "year": 2024,
                "dam": "Pong",
                "model": "ecmwf_ifs025",
                "issue_days": 46,
                "flagged_days": 0,
                "hit_days": 0,
                "false_flag_days": 0,
                "missed_days": 0,
                "first_flag_issue_date": None,
                "first_hit_issue_date": None,
                "first_hit_spill_day": None,
                "pp_first_flag_date": None,
                "pp_first_spill_date": None,
                "lead_days_to_pp_spill": None,
                "observed_peak_date": None,
                "lead_days_to_observed_peak": None,
                "max_forecast_peak_release_cusecs": 0.0,
                "pp_peak_day1_release_cusecs": 0.0,
            },
            {
                "year": 2025,
                "dam": "Bhakra",
                "model": "ecmwf_ifs025",
                "issue_days": 46,
                "flagged_days": 3,
                "hit_days": 3,
                "false_flag_days": 0,
                "missed_days": 1,
                "first_flag_issue_date": "2025-08-30",
                "first_hit_issue_date": "2025-08-30",
                "first_hit_spill_day": 4,
                "pp_first_flag_date": "2025-08-29",
                "pp_first_spill_date": None,
                "lead_days_to_pp_spill": None,
                "observed_peak_date": None,
                "lead_days_to_observed_peak": None,
                "max_forecast_peak_release_cusecs": 35473.0,
                "pp_peak_day1_release_cusecs": 0.0,
            },
        ],
    }
    (tmp_path / "results.json").write_text(json.dumps(results), encoding="utf-8")
    pd.DataFrame(
        [
            {
                "table": "harike_hussainiwala",
                "predictor": "Pong_max5d_bcm",
                "n_years": 38,
                "n_high": 5,
                "spearman_rho": 0.61,
                "auroc_high": 0.93,
                "brier_skill_score": 0.31,
            },
            {
                "table": "harike_hussainiwala",
                "predictor": "noise",
                "n_years": 38,
                "n_high": 5,
                "spearman_rho": 0.01,
                "auroc_high": 0.50,
                "brier_skill_score": -0.05,
            },
        ]
    ).to_csv(tmp_path / "peak_tests.csv", index=False)
    params = {
        "Pong": {
            "dam": "Pong",
            "area_km2": 13637.0,
            "c": 0.41,
            "w": [0.5, 0.3, 0.15, 0.05],
            "rho": 0.9,
            "intercept_bcm_per_day": -0.01,
            "gamma": 0.0,
            "n_days": 900,
            "r2": 0.55,
            "rmse_bcm": 0.02,
            "rho_raw": 1.07,
        }
    }
    (tmp_path / "params.json").write_text(json.dumps(params), encoding="utf-8")
    pd.DataFrame(
        {
            "date": pd.to_datetime(
                ["2023-08-01", "2023-08-02", "2023-08-03", "2025-08-01", "2025-08-24"]
            ),
            "dam": "Pong",
            "hei": 0.0,
            "storage_basis": ["cwc", "interp", "interp", "press", "cwc"],
            "rain_day1_mm": [10.0, 99.0, 5.0, 60.0, 1.0],
            "inflow_day1_cusecs": [50_000.0, 183_500.0, 40_000.0, 120_000.0, 30_000.0],
            "reanchor_gap_bcm": [float("nan"), float("nan"), 0.4, float("nan"), 0.6],
        }
    ).to_csv(tmp_path / "perfect_prog_hei_daily.csv", index=False)
    # Bhakra flagged under observed rain and never spilled; the largest gap inside the window
    # is the one the note must pick, not the larger one after the window closes
    pd.DataFrame(
        {
            "date": pd.to_datetime(["2025-08-29", "2025-09-02", "2025-09-06", "2025-09-20"]),
            "dam": "Bhakra",
            "hei": [0.0, -0.05, -0.05, -0.1],
            "storage_basis": ["model", "press", "press", "press"],
            "rain_day1_mm": [16.0, 15.0, 3.0, 1.0],
            "inflow_day1_cusecs": [80_000.0, 100_000.0, 48_000.0, 30_000.0],
            "reanchor_gap_bcm": [float("nan"), 0.61, 0.13, 0.9],
        }
    ).to_csv(tmp_path / "perfect_prog_event_bhakra.csv", index=False)
    md = report.render_verification(
        tmp_path, tmp_path / "params.json", era5_imd_path=None, forecast_dir=None
    )
    assert "Rain input check" not in md and "Prospective record" not in md
    assert "| Pong | 13,637 | 0.410 | 0.000 |" in md
    assert "| 0.900 (1.070) |" in md
    assert "| 2023 | 1 | 0 | 0 | 0 | 2 |" in md and "| 2025 | 1 | 0 | 1 | 0 | 0 |" in md
    # the re-anchor note sits between the first perfect-prognosis flag and the spill
    assert (
        "In 2025 the Pong run under observed rain flagged from 2025-08-22 while its spill came "
        "on 2025-08-26. Between the two, the measured storage of 2025-08-24 re-anchored the "
        "model's carried path downward by 0.60 BCM" in md
    )
    assert "In 2024" not in md
    # the wettest day is the day after the issue date; the ratio is against the sourced record
    assert "| 2023 | 2023-08-03 | 99 | 183,500 | 0.25 |" in md
    assert "734,000 cusecs" in md
    assert "| Pong_max5d_bcm | 38 | 5 | +0.61 | 0.93 | +0.31 |" in md
    assert (
        "| 2023 | spill + passage | 2023-08-16 | 150,000 | 2023-08-17 | 237,500 | -1 | 0.63 |" in md
    )
    assert "| 2025 | spill + passage | no predicted release |" in md
    assert "| Pong | 20 | 34,000 | 30,000 | -12% | +0.80 | 5,000 | -1% | +0.70 | 6,000 |" in md
    assert "## As-issued hindcast" in md
    assert (
        "| 2025 | Pong | ecmwf_ifs025 | 46 | 9 (7 hits, 2 false) | 1 | 2025-08-20 | "
        "2025-08-24, day 2 | 2025-08-22 | 2025-08-26 | +2 | 2025-08-31 | +7 | 120,000 | 150,000 |"
        in md
    )
    assert (
        "| 2024 | Pong | ecmwf_ifs025 | 46 | 0 (0 hits, 0 false) | 0 | none | none | none | none | "
        "n/a | none | n/a | 0 | 0 |" in md
    )
    assert (
        "| 2025 | Bhakra | ecmwf_ifs025 | 46 | 3 (3 hits, 0 false) | 1 | 2025-08-30 | "
        "2025-08-30, day 4 | 2025-08-29 | none | n/a | none | n/a | 35,473 | 0 |" in md
    )
    # no spill under observed rain: the note runs from the first flag to the end of the window
    assert (
        "In 2025 the Bhakra run under observed rain flagged from 2025-08-29 and did not force the "
        "spillway within the window (to 2025-09-15). After the first flag, the measured storage "
        "of 2025-09-02 re-anchored the model's carried path downward by 0.61 BCM" in md
    )
    assert "0.90 BCM" not in md


def test_rain_input_rows_and_section(tmp_path):
    era = pd.DataFrame(
        {
            "event": [2023, 2023, 2023, 2025, 2025],
            "date": ["2023-08-12", "2023-08-13", "2023-08-14", "2025-08-25", "2025-08-26"],
            "catchment": ["Pong"] * 5,
            "era5_mm": [10.0, 20.0, 30.0, 40.0, 50.0],
            "imd_mm": [20.0, 30.0, 100.0, 45.0, 55.0],
        }
    )
    rows = report.rain_input_rows(era)
    r23 = rows[rows["event"] == 2023].iloc[0]
    assert r23["days"] == 3 and r23["imd_mm"] == 150.0 and r23["era5_mm"] == 60.0
    assert r23["ratio"] == 0.4
    # the IMD-wettest day is 14 August; ERA5 read 30 mm that day
    assert r23["imd_wettest_mm"] == 100.0 and r23["era5_on_wettest_mm"] == 30.0
    assert rows[rows["event"] == 2025].iloc[0]["ratio"] == 0.9
    p = tmp_path / "era5_vs_imd.csv"
    era.to_csv(p, index=False)
    (tmp_path / "results.json").write_text(json.dumps({"peak_tests": []}), encoding="utf-8")
    pd.DataFrame(
        columns=[
            "table",
            "predictor",
            "n_years",
            "n_high",
            "spearman_rho",
            "auroc_high",
            "brier_skill_score",
        ]
    ).to_csv(tmp_path / "peak_tests.csv", index=False)
    pd.DataFrame(
        [
            {
                "catchment": "Pong",
                "model": "ecmwf_ifs025",
                "lead_days": 2,
                "n_days": 300,
                "n_seasons": 3,
                "factor_min": 1.1,
                "factor_max": 1.3,
                "factor_all_seasons": 1.2,
                "heavy_days_obs": 17,
                "raw_bias_pct": -15.0,
                "raw_mae_mm": 5.0,
                "raw_hit_rate": 0.25,
                "raw_false_alarm_ratio": float("nan"),
                "corrected_bias_pct": 2.0,
                "corrected_mae_mm": 5.4,
                "corrected_hit_rate": 0.4,
                "corrected_false_alarm_ratio": 0.6,
            },
            # lead 7 is outside the product's horizons and is not rendered
            {
                "catchment": "Pong",
                "model": "ecmwf_ifs025",
                "lead_days": 7,
                "n_days": 300,
                "n_seasons": 3,
                "factor_min": 1.0,
                "factor_max": 1.0,
                "factor_all_seasons": 1.0,
                "heavy_days_obs": 17,
                "raw_bias_pct": 0.0,
                "raw_mae_mm": 6.0,
                "raw_hit_rate": 0.1,
                "raw_false_alarm_ratio": 0.9,
                "corrected_bias_pct": 0.0,
                "corrected_mae_mm": 6.0,
                "corrected_hit_rate": 0.1,
                "corrected_false_alarm_ratio": 0.9,
            },
        ]
    ).to_csv(tmp_path / "qpf_bias_test.csv", index=False)
    md = report.render_verification(tmp_path, None, era5_imd_path=p, forecast_dir=None)
    assert "## Rain input check" in md
    assert "| Pong | 2023 | 2023-08-12 to 2023-08-14 | 3 | 150 | 60 | 0.40 | 100 | 30 |" in md
    assert "| Pong | 2025 | 2025-08-25 to 2025-08-26 | 2 | 100 | 90 | 0.90 | 55 | 50 |" in md
    assert "### Multiplicative bias correction" in md
    assert (
        "| Pong | ecmwf_ifs025 | 2 | 300 | 1.10 to 1.30 | -15% / +2% | 5.0 / 5.4 | 0.25 / 0.40 | n/a / 0.60 |"
        in md
    )
    assert "| Pong | ecmwf_ifs025 | 7 |" not in md
    # the counts that decide whether the product applies the correction are computed
    assert (
        "MAE lower after correction in 0 of 1 rows, heavy-day hit rate higher in 1, "
        "false-alarm ratio higher in 0." in md
    )


def _product(issue_date, p_pong, p_pong_err, dhilwan_class, as_on="04-09-2026"):
    return {
        "issue_date": issue_date,
        "bulletin": {"as_on_date": as_on},
        "dams": {
            "Bhakra": {
                "storage_fraction": 0.654,
                "ensemble": {
                    "1": {"p_exhaustion": 0.0},
                    "5": {"p_exhaustion": 0.0, "p_exhaustion_model_error": 0.0},
                },
            },
            "Pong": {
                "storage_fraction": 0.748,
                "ensemble": {
                    "1": {"p_exhaustion": 0.0},
                    "5": {"p_exhaustion": p_pong, "p_exhaustion_model_error": p_pong_err},
                },
            },
        },
        "reaches": [
            {"station": "Dhilwan", "peak_class": dhilwan_class},
            {"station": "Harike Head Works", "peak_class": "low" if dhilwan_class else None},
        ],
    }


def test_prospective_record_section(tmp_path):
    fdir = tmp_path / "forecast"
    fdir.mkdir()
    (fdir / "2026-09-05.json").write_text(
        json.dumps(_product("2026-09-05", 0.0, 0.0, None)), encoding="utf-8"
    )
    (fdir / "2026-09-06.json").write_text(
        json.dumps(_product("2026-09-06", 0.41, 0.47, "medium", as_on="06-09-2026")),
        encoding="utf-8",
    )
    # a rerun saved beside the day's record is not the record
    (fdir / "2026-09-06_rerun_20260906T091500.json").write_text(
        json.dumps(_product("2026-09-06", 0.9, 0.9, "high")), encoding="utf-8"
    )
    # a record written before the model-error field existed
    old = _product("2026-09-07", 0.0, None, None)
    del old["dams"]["Pong"]["ensemble"]["5"]["p_exhaustion_model_error"]
    (fdir / "2026-09-07.json").write_text(json.dumps(old), encoding="utf-8")
    rows = report.prospective_rows(fdir)
    assert list(rows["issue_date"]) == ["2026-09-05", "2026-09-06", "2026-09-07"]
    assert rows.loc[1, "Pong_p_spill"] == 0.41 and rows.loc[1, "worst_class"] == "medium"
    assert rows.loc[1, "worst_station"] == "Dhilwan"
    assert (
        rows.loc[2, "Pong_p_spill_model_error"] is None
        or rows.loc[2, "Pong_p_spill_model_error"] != rows.loc[2, "Pong_p_spill_model_error"]
    )
    (tmp_path / "results.json").write_text(json.dumps({"peak_tests": []}), encoding="utf-8")
    pd.DataFrame(
        columns=[
            "table",
            "predictor",
            "n_years",
            "n_high",
            "spearman_rho",
            "auroc_high",
            "brier_skill_score",
        ]
    ).to_csv(tmp_path / "peak_tests.csv", index=False)
    md = report.render_verification(tmp_path, None, era5_imd_path=None, forecast_dir=fdir)
    assert "## Prospective record" in md
    assert "3 issue dates from 2026-09-05 to 2026-09-07." in md
    assert "Pong: P(spillway forced) above zero on 1 of 3 days." in md
    assert "Bhakra: P(spillway forced) above zero on 0 of 3 days." in md
    assert "Days with any control point at or above the WRD low band: 1." in md
    assert (
        "| 2026-09-06 | 06-09-2026 | 65% | 0.00 / 0.00 | 75% | 0.41 / 0.47 | medium (Dhilwan) |"
        in md
    )
    assert "| 2026-09-05 |" not in md and "| 2026-09-07 |" not in md
    # an empty directory renders the section with its placeholder
    empty = tmp_path / "empty"
    empty.mkdir()
    md2 = report.render_verification(tmp_path, None, era5_imd_path=None, forecast_dir=empty)
    assert "No record yet." in md2
