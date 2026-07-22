# tests/test_eos04.py
"""EOS-04 cross-validation pure logic — TDD on hand-countable synthetic arrays.

Protocol under test is pre-declared in docs/notes/eos04.md: two water-mask
modes (change = the exact Tier-A rule; single-date fallback), co-valid-pixel
confusion/agreement metrics, per-district aggregation over a label raster, and
the Spearman direction check — all buildable and tested before any real EOS-04
scene exists.
"""

from __future__ import annotations

import numpy as np
import pytest

from sailaab import config
from sailaab.eos04 import (
    agreement_metrics,
    confusion,
    district_agreement,
    rank_correlation,
    water_mask_change,
    water_mask_single,
)
from sailaab.sar_local import tier_a_mask


# ---------------------------------------------------------------- masks

def test_single_mode_thresholds_and_reference_water():
    vv = np.array([[-20.0, -10.0], [-16.0, -20.0]])
    ref_water = np.array([[False, False], [False, True]])
    m = water_mask_single(vv, ref_water)
    # -20 dark -> water; -10 bright -> dry; -16 < -15 -> water; -20 but permanent -> excluded
    assert m.tolist() == [[True, False], [True, False]]


def test_single_mode_nan_is_never_water():
    vv = np.array([[np.nan, -20.0]])
    m = water_mask_single(vv, np.zeros((1, 2), dtype=bool))
    assert m.tolist() == [[False, True]]


def test_single_mode_valid_mask_applies():
    vv = np.full((2, 2), -20.0)
    valid = np.array([[True, False], [True, True]])
    m = water_mask_single(vv, np.zeros((2, 2), dtype=bool), valid=valid)
    assert m.tolist() == [[True, False], [True, True]]


def test_single_mode_uses_config_threshold_by_default():
    just_above = config.ABS_VV_THRESHOLD_DB + 0.1
    just_below = config.ABS_VV_THRESHOLD_DB - 0.1
    vv = np.array([[just_above, just_below]])
    m = water_mask_single(vv, np.zeros((1, 2), dtype=bool))
    assert m.tolist() == [[False, True]]


def test_change_mode_matches_tier_a_rule():
    vv_pre = np.array([[-10.0, -10.0, -20.0, -10.0]])
    vv_flood = np.array([[-20.0, -12.0, -22.0, np.nan]])
    dvv = vv_flood - vv_pre
    ours = water_mask_change(vv_flood, vv_pre)
    ref = tier_a_mask(dvv, vv_flood, vv_pre)
    assert ours.tolist() == ref.tolist()
    # drop+dark -> water; drop too small -> dry; pre already dark (permanent) -> no; NaN -> no
    assert ours.tolist() == [[True, False, False, False]]


def test_change_mode_valid_mask_applies():
    vv_pre = np.full((1, 2), -10.0)
    vv_flood = np.full((1, 2), -20.0)
    m = water_mask_change(vv_flood, vv_pre, valid=np.array([[True, False]]))
    assert m.tolist() == [[True, False]]


# ---------------------------------------------------------------- confusion

def _conf_case():
    # 4x4: ours has 3 water, theirs has 3 water, 2 overlap; one disagreement
    # pixel is invalid and must not count.
    ours = np.zeros((4, 4), dtype=bool)
    theirs = np.zeros((4, 4), dtype=bool)
    ours[0, 0] = ours[0, 1] = ours[1, 0] = True
    theirs[0, 0] = theirs[0, 1] = theirs[3, 3] = True
    valid = np.ones((4, 4), dtype=bool)
    valid[3, 3] = False  # theirs-only pixel excluded
    return ours, theirs, valid


def test_confusion_exact_counts():
    ours, theirs, valid = _conf_case()
    c = confusion(ours, theirs, valid)
    assert (c["tp"], c["fp"], c["fn"], c["tn"]) == (2, 0, 1, 12)


def test_confusion_counts_are_python_ints():
    ours, theirs, valid = _conf_case()
    assert all(isinstance(v, int) for v in confusion(ours, theirs, valid).values())


def test_agreement_metrics_exact_values():
    # tp=2 fp=1 fn=1 tn=12 -> P=2/3 R=2/3 F1=2/3 IoU=2/4 OA=14/16
    m = agreement_metrics({"tp": 2, "fp": 1, "fn": 1, "tn": 12})
    assert m["precision"] == pytest.approx(2 / 3)
    assert m["recall"] == pytest.approx(2 / 3)
    assert m["f1"] == pytest.approx(2 / 3)
    assert m["iou"] == pytest.approx(0.5)
    assert m["oa"] == pytest.approx(14 / 16)
    assert m["n_pos_ours"] == 3 and m["n_pos_theirs"] == 3


def test_agreement_metrics_all_dry_is_zero_safe():
    m = agreement_metrics({"tp": 0, "fp": 0, "fn": 0, "tn": 10})
    assert m["oa"] == 1.0
    assert m["precision"] == 0.0 and m["recall"] == 0.0
    assert m["f1"] == 0.0 and m["iou"] == 0.0
    assert m["n_pos_ours"] == 0 and m["n_pos_theirs"] == 0


def test_agreement_metrics_empty_intersection():
    m = agreement_metrics({"tp": 0, "fp": 2, "fn": 3, "tn": 5})
    assert m["precision"] == 0.0 and m["recall"] == 0.0 and m["iou"] == 0.0


# ---------------------------------------------------------------- districts

def test_district_agreement_per_label_counts():
    labels = np.array([[1, 1, 2, 2]] * 2)  # two districts, 4 px each
    ours = np.array([[True, False, True, True]] * 2)
    theirs = np.array([[True, True, False, True]] * 2)
    rows = district_agreement(ours, theirs, labels, np.ones_like(labels, bool))
    by = {r["label"]: r for r in rows}
    assert set(by) == {1, 2}
    # district 1 per row: ours=[T,F] theirs=[T,T] -> tp1 fp1 fn0 tn0; x2 rows
    assert (by[1]["tp"], by[1]["fp"], by[1]["fn"], by[1]["tn"]) == (2, 2, 0, 0)
    # district 2 per row: ours=[T,T] theirs=[F,T] -> tp1 fp0 fn1 tn0; x2 rows
    assert (by[2]["tp"], by[2]["fp"], by[2]["fn"], by[2]["tn"]) == (2, 0, 2, 0)
    assert by[2]["recall"] == pytest.approx(0.5)
    # flood fractions over valid pixels of the label
    assert by[1]["frac_ours"] == pytest.approx(0.5)
    assert by[1]["frac_theirs"] == pytest.approx(1.0)


def test_district_agreement_ignores_label_zero_and_invalid():
    labels = np.array([[0, 1], [1, 1]])
    ours = np.ones((2, 2), dtype=bool)
    theirs = np.ones((2, 2), dtype=bool)
    valid = np.array([[True, True], [True, False]])
    rows = district_agreement(ours, theirs, labels, valid)
    assert [r["label"] for r in rows] == [1]
    assert rows[0]["tp"] == 2  # label-0 pixel and invalid pixel excluded


# ---------------------------------------------------------------- direction

def test_rank_correlation_perfect_and_reversed():
    a = [0.5, 0.4, 0.3, 0.2, 0.1]
    assert rank_correlation(a, [5, 4, 3, 2, 1]) == pytest.approx(1.0)
    assert rank_correlation(a, [1, 2, 3, 4, 5]) == pytest.approx(-1.0)


def test_rank_correlation_hand_case_with_tie():
    # ranks a: [1,2,3,4]; b has a tie -> average ranks [1.5,1.5,3,4]
    a = [10.0, 8.0, 6.0, 4.0]
    b = [7.0, 7.0, 5.0, 1.0]
    # spearman = pearson of ranks: hand value 0.9486832980505138
    assert rank_correlation(a, b) == pytest.approx(0.9486832980505138)


def test_rank_correlation_degenerate_returns_nan():
    assert np.isnan(rank_correlation([1.0, 1.0, 1.0], [1.0, 2.0, 3.0]))


# ---------------------------------------------------------------- driver

def test_parse_scene_date_formats():
    from datetime import date

    from pipeline.compare_eos04 import parse_scene_date

    assert parse_scene_date("EOS04_MRS_05SEP2025_dsc_L2B.tif") == date(2025, 9, 5)
    assert parse_scene_date("pbflood50dsc1608_05092025_map.tif") == date(2025, 9, 5)
    assert parse_scene_date("no_date_here.tif") is None
    assert parse_scene_date("EOS04_99XYZ2025.tif") is None


def test_classify_scene_windows():
    from datetime import date

    from pipeline.compare_eos04 import classify_scene

    assert classify_scene(date(2025, 8, 25)) == "flood"
    assert classify_scene(date(2025, 7, 15)) == "pre"
    assert classify_scene(date(2025, 6, 1)) == "other"
    assert classify_scene(None) == "undated"


def test_driver_graceful_without_scenes(tmp_path, capsys):
    from pipeline.compare_eos04 import main

    assert main(scene_dir=tmp_path) == 0
    assert "data/eos04/README.md" in capsys.readouterr().out


def test_driver_graceful_without_reference_rasters(tmp_path, capsys):
    from pipeline.compare_eos04 import main

    scenes = tmp_path / "scenes"
    scenes.mkdir()
    (scenes / "EOS04_MRS_05SEP2025.tif").write_bytes(b"")
    empty_rasters = tmp_path / "rasters"
    empty_rasters.mkdir()
    assert main(scene_dir=scenes, raster_dir=empty_rasters) == 0
    assert "no local reference raster" in capsys.readouterr().out
