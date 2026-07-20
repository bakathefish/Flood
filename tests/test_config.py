# tests/test_config.py
from sailaab import config


def test_thresholds_are_negative_db():
    assert config.DIFF_THRESHOLD_DB < 0
    assert config.ABS_VV_THRESHOLD_DB < 0


def test_2025_event_windows_ordered():
    assert config.PRE_2025 == ("2025-07-01", "2025-08-10")
    assert config.FLOOD_2025 == ("2025-08-25", "2025-09-06")
    assert config.PRE_2025[1] < config.FLOOD_2025[0]


def test_spatial_folds_do_not_overlap():
    assert not set(config.FOLD_RAVI_BEAS) & set(config.FOLD_SUTLEJ)
    assert len(config.FOLD_RAVI_BEAS) >= 5 and len(config.FOLD_SUTLEJ) >= 5


def test_official_bands_present():
    lo, hi = config.OFFICIAL_CROP_FLOODED_HA_BAND
    assert 100_000 < lo < hi < 250_000
