"""Sailaab — Wave 4: district flood-risk forecaster.

Unit of analysis: (district, 10-day monsoon window), 2015–2025.
Target:      SAR-derived flooded fraction (from Wave 2 CSVs) — regression + binary.
Predictors:  upstream-basin rainfall (current + 2 lags), reservoir level/Δstorage,
             NRSC VIC soil moisture (2018+, NaN before — GBM handles it),
             antecedent flooded fraction, week-of-season.
Validation:  leave-one-year-out CV; showcase holdout = train 2015–2024, predict 2025.

Inputs expected in data/:
    decade_windows.csv    <- concat of sailaab_decade_<year>.csv exports (Wave 2)
    rainfall_windows.csv  <- per-basin IMERG/CHIRPS sums per window (export via GEE;
                             upstream Sutlej/Beas/Ravi basins from WWF/HydroSHEDS)
    reservoirs.csv        <- AIKosh CWC daily reservoir levels (Bhakra/Pong/Thein)
    soil_moisture.csv     <- AIKosh NRSC VIC daily district soil moisture (2018+)

Run:  python pipeline/forecaster.py
Deps: pip install pandas xgboost scikit-learn shap matplotlib
"""

from pathlib import Path

import pandas as pd

DATA = Path(__file__).resolve().parent.parent / "data"
FLOOD_FRACTION_EVENT_THRESHOLD = 0.02  # >2% of district area flooded = "event"


def load_targets() -> pd.DataFrame:
    """Wave 2 output -> (district, window_start, flooded_ha, flooded_fraction)."""
    df = pd.read_csv(DATA / "decade_windows.csv")
    # TODO: normalize column names from GEE export; add district area to compute
    # flooded_fraction = flooded_ha / district_area_ha
    raise NotImplementedError("wire up after first Wave 2 export lands")


def load_predictors() -> pd.DataFrame:
    """Join rainfall (lag 0/1/2), reservoir level + 10-day delta, soil moisture,
    antecedent flooded fraction, week-of-season index onto the target frame."""
    raise NotImplementedError


def build_dataset() -> pd.DataFrame:
    y = load_targets()
    x = load_predictors()
    df = y.merge(x, on=["district", "window_start"], how="left")
    df.to_csv(DATA / "forecaster_dataset.csv", index=False)
    return df


def loyo_cv(df: pd.DataFrame):
    """Leave-one-year-out CV with XGBoost; report per-year AUC/PR + regression R2."""
    import xgboost  # noqa: F401  # imported here so dataset work runs without it

    # TODO:
    #  for year in 2016..2025: train on all other years, predict `year`
    #  classification: flooded_fraction > FLOOD_FRACTION_EVENT_THRESHOLD
    #  keep 2025 results separately — that's the showcase hindcast
    raise NotImplementedError


def shap_report(model, X):
    """SHAP summary plot -> atlas/shap_summary.png. The 'dam storage change is the
    #2 predictor' figure for the synopsis/video comes from here."""
    raise NotImplementedError


if __name__ == "__main__":
    build_dataset()
