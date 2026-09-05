from __future__ import annotations

import csv
import json

from punjabflood import cwc


def test_normalise_record_maps_units_and_na():
    rec = {
        "Date": "2023-08-15",
        "Level": "510.12",
        "Storage": "5.9",
        "Full_reservoir_level": "512.06",
        "Live_capacity_FRL": "6.229",
        "Lat": "31.41",
        "Long": "76.43",
        "Agency_name": "BBMB",
    }
    row = cwc.normalise_record(rec, "Bhakra")
    assert row["date"] == "2023-08-15"
    assert row["level_m"] == 510.12
    assert row["storage_bcm"] == 5.9
    assert abs(row["pct_live"] - 5.9 / 6.229 * 100) < 1e-3  # stored rounded to 3 dp
    assert row["lat"] == 31.41 and row["lon"] == 76.43

    rec["Storage"] = "NA"
    row = cwc.normalise_record(rec, "Bhakra")
    assert row["storage_bcm"] is None and row["pct_live"] is None


def test_parse_date_accepts_both_orders_and_rejects_junk():
    assert cwc._parse_date("2001-07-03") == "2001-07-03"
    assert cwc._parse_date("03-07-2001") == "2001-07-03"
    assert cwc._parse_date("03/07/2001 00:00:00") == "2001-07-03"
    assert cwc._parse_date("NA") is None
    assert cwc._parse_date("") is None


def _fake_feed(pages_by_offset):
    calls = []

    def get(params):
        calls.append(params)
        return pages_by_offset[params["offset"]]

    return get, calls


def test_fetch_month_follows_pagination_until_short_page():
    def rec(day):
        return {
            "Date": f"1995-09-{day:02d}",
            "Level": "500",
            "Storage": "5",
            "Full_reservoir_level": "512.06",
            "Live_capacity_FRL": "6.229",
        }

    pages = {
        0: {"total": 23, "records": [rec(d) for d in range(1, 11)]},
        10: {"total": 23, "records": [rec(d) for d in range(11, 21)]},
        20: {"total": 23, "records": [rec(d) for d in range(21, 24)]},
    }
    get, calls = _fake_feed(pages)
    rows = cwc.fetch_month(get, "Bhakra", 1995, 9)
    assert len(rows) == 23
    assert [c["offset"] for c in calls] == [0, 10, 20]
    assert calls[0]["filters[Reservoir_name]"] == "Gobind Sagar-Bhakra Reservoir"
    assert calls[0]["filters[Month]"] == "09"


def test_pull_is_resumable_and_records_empty_months(tmp_path):
    served = {}

    def get(params):
        key = (params["filters[Reservoir_name]"], params["filters[Year]"], params["filters[Month]"])
        served[key] = served.get(key, 0) + 1
        if params["filters[Month]"] == "07":
            return {"total": 0, "records": []}
        return {
            "total": 1,
            "records": [
                {
                    "Date": f"{params['filters[Year]']}-{params['filters[Month]']}-01",
                    "Level": "1",
                    "Storage": "1",
                    "Live_capacity_FRL": "2",
                }
            ],
        }

    out = tmp_path / "cwc.csv"
    n = cwc.pull(get, out, dams=("Pong",), years=(2001,), months=(6, 7))
    assert n == 1
    with out.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert rows[0]["dam"] == "Pong" and rows[0]["date"] == "2001-06-01"
    manifest = [
        json.loads(line) for line in out.with_suffix(".manifest.jsonl").read_text().splitlines()
    ]
    assert {(m["month"], m["rows"]) for m in manifest} == {(6, 1), (7, 0)}

    # second run: nothing re-fetched, nothing appended
    n2 = cwc.pull(get, out, dams=("Pong",), years=(2001,), months=(6, 7))
    assert n2 == 0
    assert all(v == 1 for v in served.values())


def test_getter_backs_off_on_429_then_succeeds():
    class Resp:
        def __init__(self, code, payload=None):
            self.status_code = code
            self._p = payload or {}

        def json(self):
            return self._p

        def raise_for_status(self):
            if self.status_code >= 400:
                raise RuntimeError(self.status_code)

    class Sess:
        headers = {}

        def __init__(self):
            self.n = 0

        def get(self, url, params=None, timeout=None):
            self.n += 1
            return Resp(429) if self.n < 3 else Resp(200, {"records": [], "total": 0})

    slept = []
    get = cwc.make_getter(session=Sess(), spacing_s=0, backoff_s=(1, 2, 4), sleep=slept.append)
    j = get({"limit": 10})
    assert j == {"records": [], "total": 0}
    assert slept[:2] == [1, 2]


def test_getter_retries_gateway_errors_and_gives_up_after_budget():
    class Resp:
        def __init__(self, code):
            self.status_code = code

        def json(self):
            return {}

        def raise_for_status(self):
            raise RuntimeError(self.status_code)

    class Sess:
        headers = {}

        def get(self, url, params=None, timeout=None):
            return Resp(502)

    slept = []
    get = cwc.make_getter(
        session=Sess(), spacing_s=0, outage_wait_s=(1, 2), max_outage_s=5, sleep=slept.append
    )
    import pytest

    with pytest.raises(cwc.Throttled):
        get({"limit": 10})
    # 1 + 2 + 2 = 5 fits the budget; the next 2 would exceed it
    assert slept == [1, 2, 2]
