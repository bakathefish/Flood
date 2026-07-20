# Sailaab — Method

## 1. Software architecture
Decision logic lives in the pure-Python `sailaab/` package, developed test-first
(pytest, tests/ mirrors the package 1:1). Earth Engine effects are confined to
`gee/*.js` and thin `pipeline/*.py` CLIs. Constants (thresholds, windows,
spatial folds, official comparison bands) are centralized in `sailaab/config.py`.
GEE steps use pre-declared acceptance checkpoints (see VERIFICATION-LOG.md).
<!-- Sections 2+ appended by later plans: 2 Mapping, 3 Decade, 4 Validation,
     5 Forecaster, 6 Monitor -->
