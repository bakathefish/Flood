from __future__ import annotations

from datetime import UTC, datetime

import pytest

from punjabflood import openmeteo


class Resp:
    def __init__(self, code, payload=None, text=""):
        self.status_code = code
        self._p = payload
        self.text = text

    def json(self):
        if self._p is None:
            raise ValueError("no json")
        return self._p


class FakeSession:
    headers: dict = {}

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, dict(params)))
        return self.responses.pop(0)


def make(responses, tmp_cache, clock=None):
    slept = []
    sess = FakeSession(responses)
    om = openmeteo.OpenMeteo(
        cache_dir=tmp_cache, session=sess, sleep=slept.append, spacing_s=0, clock=clock
    )
    return om, sess, slept


def test_cache_hit_avoids_second_call_and_key_is_order_independent(tmp_cache):
    payload = {"daily": {"time": ["2023-08-10"], "precipitation_sum": [9.4]}}
    om, sess, _ = make([Resp(200, payload)], tmp_cache)
    a = om.get("archive", {"latitude": 31.9, "longitude": 76.5, "daily": ["precipitation_sum"]})
    b = om.get("archive", {"daily": "precipitation_sum", "longitude": 76.5, "latitude": 31.9})
    assert a == b == payload
    assert len(sess.calls) == 1
    assert om.cache_hits == 1
    # the query sent joins list parameters with commas
    assert sess.calls[0][1]["daily"] == "precipitation_sum"


def test_minutely_429_sleeps_a_minute_then_retries(tmp_cache):
    om, sess, slept = make(
        [
            Resp(429, {"error": True, "reason": "Minutely API request limit exceeded"}),
            Resp(200, {"ok": 1}),
        ],
        tmp_cache,
    )
    assert om.get("forecast", {"latitude": 1, "longitude": 2}) == {"ok": 1}
    assert slept == [61]
    assert len(sess.calls) == 2


def test_hourly_429_sleeps_to_the_next_hour(tmp_cache):
    clock = lambda: datetime(2026, 9, 5, 12, 40, 10, tzinfo=UTC)  # noqa: E731
    om, _, slept = make(
        [
            Resp(429, {"error": True, "reason": "Hourly API request limit exceeded"}),
            Resp(200, {"ok": 1}),
        ],
        tmp_cache,
        clock=clock,
    )
    om.get("archive", {"latitude": 1, "longitude": 2})
    assert slept == [(60 - 40) * 60 - 10 + 5]


def test_daily_429_fails_fast(tmp_cache):
    om, _, slept = make(
        [Resp(429, {"error": True, "reason": "Daily API request limit exceeded"})], tmp_cache
    )
    with pytest.raises(openmeteo.QuotaExhausted):
        om.get("archive", {"latitude": 1, "longitude": 2})
    assert slept == []


def test_error_payload_with_200_raises(tmp_cache):
    om, _, _ = make([Resp(200, {"error": True, "reason": "Data corrupted at path"})], tmp_cache)
    with pytest.raises(openmeteo.OpenMeteoError):
        om.get("historical", {"latitude": 1, "longitude": 2})


def test_forecast_cache_key_includes_issue_date(tmp_cache):
    om, sess, _ = make([Resp(200, {"a": 1}), Resp(200, {"a": 2})], tmp_cache)
    r1 = om.forecast_daily(31.9, 76.5, issue_date="2026-09-05")
    r2 = om.forecast_daily(31.9, 76.5, issue_date="2026-09-06")
    r3 = om.forecast_daily(31.9, 76.5, issue_date="2026-09-05")
    assert (r1, r2, r3) == ({"a": 1}, {"a": 2}, {"a": 1})
    assert len(sess.calls) == 2
    # the private cache-key parameter is still sent (Open-Meteo ignores unknown params)
    assert "_issue_date" in sess.calls[0][1]


def test_previous_runs_builds_the_hourly_variable_list(tmp_cache):
    om, sess, _ = make([Resp(200, {"hourly": {}})], tmp_cache)
    om.previous_runs_hourly(31.9, 76.5, "gfs_seamless", "2025-08-20", "2025-09-05", leads=(1, 3))
    q = sess.calls[0][1]
    assert q["hourly"] == "precipitation,precipitation_previous_day1,precipitation_previous_day3"
    assert q["models"] == "gfs_seamless"
