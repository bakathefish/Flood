# pipeline/run_forecaster.py
"""Assemble dataset -> LOYO eval -> 2025 hindcast -> SHAP figure.
Inputs (data/): decade_windows.csv (tidied Wave-2 concat), rain_windows.csv
(district,window_start,rain_mm from GEE IMERG export), reservoirs_daily.csv,
soil_moisture.csv (optional, 2018+). Outputs: atlas/forecaster/*"""

from pathlib import Path

import pandas as pd

from sailaab.dataset import add_lags, assemble, label_events
from sailaab.model import fit_eval

DATA = Path("data")
OUT = Path("atlas/forecaster")
OUT.mkdir(parents=True, exist_ok=True)
FEATURES = [
    "rain_mm",
    "rain_mm_lag1",
    "rain_mm_lag2",
    "reservoir_delta",
    "soil_moisture",
    "antecedent_fraction",
    "week_of_season",
]


def main():
    df = pd.read_csv(
        DATA / "decade_windows.csv"
    )  # district,window_start,year,flooded_fraction
    rain = pd.read_csv(DATA / "rain_windows.csv")  # district,window_start,rain_mm
    df = df.merge(rain, on=["district", "window_start"], how="left")
    res = pd.read_csv(
        DATA / "reservoirs_windows.csv"
    )  # window_start,reservoir_delta (statewide)
    df = df.merge(res, on="window_start", how="left")
    sm = DATA / "soil_moisture_windows.csv"
    if sm.exists():
        df = df.merge(pd.read_csv(sm), on=["district", "window_start"], how="left")
    else:
        df["soil_moisture"] = float("nan")

    df = assemble(label_events(add_lags(df, "rain_mm", 2)))

    # Showcase hindcast: train 2015-2024, predict 2025 — reported verbatim.
    hind = fit_eval(df[df.year <= 2025], FEATURES, "flood_event")
    pd.DataFrame(hind["per_year"]).to_csv(OUT / "loyo_metrics.csv", index=False)

    df2025 = df[df.year == 2025].copy()
    m = fit_eval(df[df.year < 2025], FEATURES, "flood_event")["model"]
    df2025["risk"] = m.predict_proba(df2025[FEATURES])[:, 1]
    df2025.sort_values("risk", ascending=False).to_csv(
        OUT / "hindcast_2025.csv", index=False
    )

    import shap

    ex = shap.TreeExplainer(m)
    sv = ex.shap_values(df[df.year < 2025][FEATURES])
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    shap.summary_plot(sv, df[df.year < 2025][FEATURES], show=False)
    plt.tight_layout()
    plt.savefig(OUT / "shap_summary.png", dpi=200)
    print("wrote", list(OUT.iterdir()))


if __name__ == "__main__":
    main()
