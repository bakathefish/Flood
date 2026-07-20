# tests/test_validation.py
import numpy as np
import pytest

from sailaab.validation import binary_metrics


def test_perfect_agreement():
    a = np.array([1, 1, 0, 0])
    m = binary_metrics(pred=a, ref=a)
    assert m["oa"] == 1.0 and m["f1"] == 1.0 and m["iou"] == 1.0


def test_known_confusion():
    # pred: 1,1,1,0,0,0  ref: 1,0,1,0,1,0  -> TP=2 FP=1 FN=1 TN=2
    pred = np.array([1, 1, 1, 0, 0, 0])
    ref = np.array([1, 0, 1, 0, 1, 0])
    m = binary_metrics(pred, ref)
    assert m["oa"] == pytest.approx(4 / 6)
    assert m["f1"] == pytest.approx(2 * 2 / (2 * 2 + 1 + 1))  # 2TP/(2TP+FP+FN)
    assert m["iou"] == pytest.approx(2 / (2 + 1 + 1))
    assert m["tp"] == 2 and m["fp"] == 1 and m["fn"] == 1 and m["tn"] == 2


def test_shape_mismatch_raises():
    with pytest.raises(ValueError):
        binary_metrics(np.array([1]), np.array([1, 0]))
