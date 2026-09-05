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
            "date": pd.to_datetime(["2023-08-01", "2023-08-02", "2023-08-03", "2025-08-01"]),
            "dam": "Pong",
            "hei": 0.0,
            "storage_basis": ["cwc", "interp", "interp", "press"],
            "rain_day1_mm": [10.0, 99.0, 5.0, 60.0],
            "inflow_day1_cusecs": [50_000.0, 183_500.0, 40_000.0, 120_000.0],
        }
    ).to_csv(tmp_path / "perfect_prog_hei_daily.csv", index=False)
    md = report.render_verification(tmp_path, tmp_path / "params.json", era5_imd_path=None)
    assert "Rain input check" not in md
    assert "| Pong | 13,637 | 0.410 | 0.000 |" in md
    assert "| 0.900 (1.070) |" in md
    assert "| 2023 | 1 | 0 | 0 | 0 | 2 |" in md and "| 2025 | 0 | 0 | 1 | 0 | 0 |" in md
    # the wettest day is the day after the issue date; the ratio is against the sourced record
    assert "| 2023 | 2023-08-03 | 99 | 183,500 | 0.25 |" in md
    assert "734,000 cusecs" in md
    assert "| Pong_max5d_bcm | 38 | 5 | +0.61 | 0.93 | +0.31 |" in md
    assert (
        "| 2023 | spill + passage | 2023-08-16 | 150,000 | 2023-08-17 | 237,500 | -1 | 0.63 |" in md
    )
    assert "| 2025 | spill + passage | no predicted release |" in md
    assert "| Pong | 20 | 34,000 | 30,000 | -12% | +0.80 | 5,000 | -1% | +0.70 | 6,000 |" in md


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
    md = report.render_verification(tmp_path, None, era5_imd_path=p)
    assert "## Rain input check" in md
    assert "| Pong | 2023 | 2023-08-12 to 2023-08-14 | 3 | 150 | 60 | 0.40 | 100 | 30 |" in md
    assert "| Pong | 2025 | 2025-08-25 to 2025-08-26 | 2 | 100 | 90 | 0.90 | 55 | 50 |" in md
