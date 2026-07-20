# tests/test_monitor.py
import json

from sailaab.monitor import new_scenes, load_state, save_state


def test_new_scenes_after_watermark():
    dates = ["2026-07-18T01:10:00", "2026-07-19T13:22:00", "2026-07-20T01:10:00"]
    out = new_scenes(dates, last_seen="2026-07-19T00:00:00")
    assert out == ["2026-07-19T13:22:00", "2026-07-20T01:10:00"]


def test_no_new_scenes_returns_empty():
    assert new_scenes(["2026-07-18T01:10:00"], "2026-07-19T00:00:00") == []


def test_state_roundtrip(tmp_path):
    p = tmp_path / "state.json"
    save_state(p, last_seen="2026-07-20T01:10:00")
    assert load_state(p) == "2026-07-20T01:10:00"


def test_missing_state_returns_epoch(tmp_path):
    assert load_state(tmp_path / "nope.json") == "1970-01-01T00:00:00"
