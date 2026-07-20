# sailaab/config.py
"""Single source of truth for constants. gee/*.js mirrors these values —
if you change one here, plan 01 Task 5 (JS sync) must be re-run."""

# --- SAR thresholds (dB), kept in sync with gee/02 ---
DIFF_THRESHOLD_DB = -3.0  # dVV = post - pre
ABS_VV_THRESHOLD_DB = -15.0  # post VV ceiling for water
MIN_CONNECTED_PIXELS = 10

# --- 2025 event windows (ISO dates) ---
PRE_2025 = ("2025-07-01", "2025-08-10")
FLOOD_2025 = ("2025-08-25", "2025-09-06")

# --- Decade run ---
YEARS = list(range(2015, 2026))
SEASON_START_MD = "06-15"
SEASON_END_MD = "09-30"
WINDOW_DAYS = 10
PRE_SEASON_MD = ("04-01", "05-31")  # dry-season reference per year

# --- Spatial CV folds (GAUL ADM2_NAME spellings; verified by plan 01 Task 5) ---
FOLD_RAVI_BEAS = [
    "Gurdaspur",
    "Amritsar",
    "Kapurthala",
    "Tarn Taran",
    "Hoshiarpur",
    "Jalandhar",
]
FOLD_SUTLEJ = [
    "Firozpur",
    "Faridkot",
    "Ludhiana",
    "Moga",
    "Rupnagar",
    "Nawanshahr",
    "Fatehgarh Sahib",
]

# --- Honesty bands (official 2025 figures for comparison, not calibration) ---
OFFICIAL_CROP_FLOODED_HA_BAND = (148_000, 175_000)
OFFICIAL_POP_AFFECTED = 355_000
SANGRUR_2023_NRSC_HA = 7_121  # NRSC anchor for the decade run

FLOOD_EVENT_FRACTION = 0.02  # >2% of district area flooded = "event" (forecaster)
