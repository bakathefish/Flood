# tests/test_stac_retry.py
"""The monitor's two STAC calls (catalog open, scene search) retry transient
Planetary Computer failures instead of failing the six-hourly job on the first
one. The two failures the Action has logged were a server-side timeout (26 Aug
2026) and a certificate hostname mismatch (15 Sep 2026); both cleared by the
next run. No network: the client is faked."""

import ssl

import pystac_client.exceptions as pce
import pytest
import requests

from pipeline import local_tier_a as lta


class _Flaky:
    """Fails ``n_fail`` times with the given error, then returns ``value``."""

    def __init__(self, n_fail, err, value="ok"):
        self.n_fail, self.err, self.value, self.calls = n_fail, err, value, 0

    def __call__(self, *a, **k):
        self.calls += 1
        if self.calls <= self.n_fail:
            raise self.err
        return self.value


@pytest.fixture
def no_sleep(monkeypatch):
    slept = []
    monkeypatch.setattr(lta.time, "sleep", lambda s: slept.append(s))
    return slept


def test_retry_recovers_from_api_error(no_sleep):
    fn = _Flaky(2, pce.APIError("The request exceeded the maximum allowed time"))
    assert lta._with_retry(fn, "open") == "ok"
    assert fn.calls == 3
    assert no_sleep == list(lta.STAC_RETRY_DELAYS[:2])


def test_retry_recovers_from_ssl_and_connection_errors(no_sleep):
    for err in (
        ssl.SSLCertVerificationError("Hostname mismatch"),
        requests.ConnectionError("reset"),
    ):
        fn = _Flaky(1, err)
        assert lta._with_retry(fn, "search") == "ok"
        assert fn.calls == 2


def test_retry_gives_up_after_the_last_delay(no_sleep):
    n = len(lta.STAC_RETRY_DELAYS) + 1
    fn = _Flaky(n + 5, pce.APIError("still down"))
    with pytest.raises(pce.APIError):
        lta._with_retry(fn, "open")
    assert fn.calls == n
    assert no_sleep == list(lta.STAC_RETRY_DELAYS)


def test_retry_does_not_mask_programming_errors(no_sleep):
    fn = _Flaky(1, TypeError("bad call"))
    with pytest.raises(TypeError):
        lta._with_retry(fn, "open")
    assert fn.calls == 1 and no_sleep == []


def test_open_client_and_search_window_go_through_retry(monkeypatch, no_sleep):
    class _Search:
        def items(self):
            return iter(["a", "b"])

    class _Client:
        def __init__(self):
            self.n = 0

        def search(self, **kw):
            self.n += 1
            if self.n == 1:
                raise pce.APIError("timeout")
            assert kw["collections"] == [lta.COLLECTION]
            return _Search()

    opens = _Flaky(1, pce.APIError("502"), value=_Client())
    monkeypatch.setattr(lta.pystac_client.Client, "open", staticmethod(opens))
    client = lta.open_client()
    assert opens.calls == 2
    assert lta.search_window(client, (0, 0, 1, 1), ("2026-09-01", "2026-09-12")) == [
        "a",
        "b",
    ]
    assert client.n == 2
