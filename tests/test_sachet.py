"""The Sachet archive must never fabricate absence, and never lose an update.

Two failure modes are worth pinning hard, because both have already bitten this
project once in other fetchers. The first is a transient HTTP failure recorded
as "no alerts", which manufactures a quiet day that never happened. The second
is deduplicating on the CAP identifier alone, which silently drops a reissued
alert whose text changed, so an upgrade from watch to warning would vanish.

The Punjab lens is deliberately loose and is tested as loose. It runs at read
time over a complete archive, so an over-match is recoverable by tightening it
later, and an under-match would be recoverable too. That is only true while the
capture stays unfiltered, which is what ``test_capture_is_unfiltered`` defends.
"""

from __future__ import annotations

import ast
import inspect
import json
import re

import pytest

from pipeline import fetch_sachet as fs


def alert(**kw) -> dict:
    base = {
        "identifier": 1786090220067027,
        "disaster_type": "Flood",
        "area_description": "Gumla,Simdega districts of Jharkhand",
        "alert_source": "Jharkhand SDMA",
        "warning_message": "river rising",
        "severity": "ALERT",
    }
    base.update(kw)
    return base


# --- identity -------------------------------------------------------------


def test_content_hash_ignores_our_own_bookkeeping():
    """Stamping an alert must not change what alert it is."""
    a = alert()
    stamped = {**a, "_first_seen_utc": "2026-08-07T00:00:00Z", "_content_sha1": "x"}
    assert fs.content_sha1(a) == fs.content_sha1(stamped)


def test_content_hash_is_order_independent():
    a = alert()
    shuffled = dict(reversed(list(a.items())))
    assert fs.content_sha1(a) == fs.content_sha1(shuffled)


def test_repoll_of_an_unchanged_alert_adds_nothing():
    seen = "2026-08-07T00:00:00Z"
    first = fs.merge([], [alert()], seen)
    assert len(first) == 1
    assert fs.merge(first, [alert()], "2026-08-07T06:00:00Z") == []


def test_a_reissue_under_the_same_identifier_is_kept():
    """CAP reissues share an identifier. Dropping them would lose escalations."""
    seen = "2026-08-07T00:00:00Z"
    first = fs.merge([], [alert(severity="ALERT")], seen)
    second = fs.merge(first, [alert(severity="SEVERE")], "2026-08-07T06:00:00Z")
    assert len(second) == 1
    assert second[0]["severity"] == "SEVERE"


def test_first_seen_records_when_we_saw_it_not_when_it_was_issued():
    fresh = fs.merge([], [alert()], "2026-08-07T03:00:00Z")
    assert fresh[0]["_first_seen_utc"] == "2026-08-07T03:00:00Z"


def test_merge_dedupes_within_a_single_poll():
    fresh = fs.merge([], [alert(), alert()], "2026-08-07T00:00:00Z")
    assert len(fresh) == 1


# --- absence is never fabricated -----------------------------------------


def test_fetch_raises_rather_than_returning_empty_when_unreachable(monkeypatch):
    """The whole point: a failed poll must not read as a quiet day."""
    monkeypatch.setattr(fs.time, "sleep", lambda *_: None)
    monkeypatch.setattr(
        fs.urllib.request, "urlopen", lambda *a, **k: (_ for _ in ()).throw(OSError("down"))
    )
    with pytest.raises(RuntimeError, match="unreachable"):
        fs.fetch(retries=2, backoff=0)


def test_fetch_retries_before_giving_up(monkeypatch):
    calls = {"n": 0}

    class Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps([alert()]).encode()

    def flaky(*a, **k):
        calls["n"] += 1
        if calls["n"] < 3:
            raise OSError("transient")
        return Resp()

    monkeypatch.setattr(fs.time, "sleep", lambda *_: None)
    monkeypatch.setattr(fs.urllib.request, "urlopen", flaky)
    assert len(fs.fetch(retries=4, backoff=0)) == 1
    assert calls["n"] == 3


def test_a_genuinely_empty_window_is_distinguishable_from_a_failure(monkeypatch):
    class Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b"[]"

    monkeypatch.setattr(fs.urllib.request, "urlopen", lambda *a, **k: Resp())
    assert fs.fetch(retries=1, backoff=0) == []


def test_unrecognised_payload_shape_raises(monkeypatch):
    class Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b'"a bare string"'

    monkeypatch.setattr(fs.urllib.request, "urlopen", lambda *a, **k: Resp())
    with pytest.raises(ValueError, match="payload shape"):
        fs.fetch(retries=1, backoff=0)


def test_missing_archive_is_empty_not_an_error(tmp_path):
    assert fs.read_archive(tmp_path / "nope.jsonl") == []


# --- the lens is a lens, not a filter ------------------------------------


def test_capture_is_unfiltered():
    """A non-Punjab alert must survive merge. If this fails, evidence is being
    discarded at write time and no later change of definition can recover it."""
    fresh = fs.merge([], [alert(area_description="Dhubri district of Assam")], "t")
    assert len(fresh) == 1


def test_lens_catches_the_state_name():
    rows = [alert(area_description="Ferozepur district of Punjab")]
    assert len(fs.punjab_view(rows, ["Punjab", "Tarn Taran"])) == 1


def test_lens_catches_a_district_without_the_state_name():
    rows = [alert(area_description="Tarn Taran, Kapurthala")]
    assert len(fs.punjab_view(rows, ["Punjab", "Tarn Taran"])) == 1


def test_lens_reads_the_sender_field_too():
    rows = [alert(alert_source="Punjab SDMA", area_description="unspecified")]
    assert len(fs.punjab_view(rows, ["Punjab"])) == 1


def test_lens_does_not_take_haryana():
    """A Haryana row must not be counted as Punjab.

    Haryana SDMA appears as a sender in both captured responses (2026-08-07 and
    2026-08-09), which is what makes this the neighbour worth pinning; the lens
    must not widen to it.
    """
    rows = [alert(area_description="Ambala district of Haryana", alert_source="Haryana SDMA")]
    assert fs.punjab_view(rows, fs.punjab_names(fs.DISTRICTS)) == []


def test_lens_over_matches_and_that_is_recorded():
    """Known and accepted: bare name matching also takes a same-named place in
    another state, and would take Pakistan's Punjab if it ever appeared. The
    archive is complete, so tightening this later costs nothing."""
    rows = [alert(area_description="Mansa town, Gandhinagar district of Gujarat")]
    assert len(fs.punjab_view(rows, ["Punjab", "Mansa"])) == 1


def test_district_names_load_from_the_committed_boundary_file():
    names = fs.punjab_names()
    assert "Punjab" in names
    assert "Tarn Taran" in names
    assert len(names) == 21  # the state plus its twenty districts


# --- reporting ------------------------------------------------------------


def test_is_flood_reads_the_declared_type():
    assert fs.is_flood(alert(disaster_type="Flash Flood"))
    assert fs.is_flood(alert(disaster_type="Flood"))
    assert not fs.is_flood(alert(disaster_type="Moderate Thunderstorms"))
    assert not fs.is_flood(alert(disaster_type=None))


def test_summary_counts_punjab_floods_separately():
    rows = [
        {**alert(area_description="Tarn Taran, Punjab"), "_first_seen_utc": "2026-08-07T00:00:00Z"},
        {
            **alert(identifier=2, disaster_type="Cyclone", area_description="Punjab"),
            "_first_seen_utc": "2026-08-08T00:00:00Z",
        },
        {
            **alert(identifier=3, area_description="Dhubri, Assam"),
            "_first_seen_utc": "2026-08-06T00:00:00Z",
        },
    ]
    s = fs.summarise(rows)
    assert s["alerts"] == 3
    assert s["flood"] == 2
    assert s["punjab"] == 2
    assert s["punjab_flood"] == 1
    assert s["first_seen"].startswith("2026-08-06")
    assert s["last_seen"].startswith("2026-08-08")


def test_summary_of_an_empty_archive_does_not_crash():
    s = fs.summarise([])
    assert s["alerts"] == 0 and s["first_seen"] == ""


def test_round_trip_through_the_archive_file(tmp_path, monkeypatch):
    path = tmp_path / "alerts.jsonl"
    monkeypatch.setattr(fs, "OUT", path)
    fresh = fs.merge([], [alert(), alert(identifier=2, disaster_type="Cyclone")], "t")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for row in fresh:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    back = fs.read_archive(path)
    assert len(back) == 2
    assert fs.merge(back, [alert()], "t2") == []


# --- the write-ahead poll protocol (F2+F3) --------------------------------
#
# Every test below exists because a specific failure mode was found in review,
# not because it seemed thorough. The shape of the protocol is: a
# `started` row is durable BEFORE the network call, an `observed` row is durable
# BEFORE the archive is touched, and a terminal `result` row is written in a
# `finally`. Anything that dies in between leaves a recorded gap that the next
# run repairs, which is why several of these kill the process deliberately.


import os
import subprocess
import sys
import time as _time
import uuid
from pathlib import Path


@pytest.fixture
def sach(tmp_path, monkeypatch):
    """A private archive+manifest+lock trio, so tests never touch real evidence."""
    d = tmp_path / "sachet"
    d.mkdir()
    monkeypatch.setattr(fs, "OUT", d / "alerts.jsonl")
    monkeypatch.setattr(fs, "POLLS", d / "polls.jsonl")
    monkeypatch.setattr(fs, "LOCK", d / ".lock")
    return d


def rows_of(path):
    if not Path(path).exists():
        return []
    return [
        json.loads(l)
        for l in Path(path).read_text(encoding="utf-8").splitlines()
        if l.strip()
    ]


def kinds(path):
    return [r["kind"] for r in rows_of(path)]


def stub_fetch(monkeypatch, payload):
    monkeypatch.setattr(fs, "fetch", lambda *a, **k: payload)


# --- ordering: the write that precedes the risk ---------------------------


def test_started_row_is_durable_before_the_network_call(sach, monkeypatch):
    """A hung endpoint killed mid-fetch must still have left an attempt on disk."""
    seen = {}

    def exploding_fetch(*a, **k):
        seen["manifest"] = kinds(fs.POLLS)
        raise RuntimeError("endpoint hung")

    monkeypatch.setattr(fs, "fetch", exploding_fetch)
    with pytest.raises(RuntimeError):
        fs.poll()
    assert seen["manifest"] == ["started"], "started row was not durable before fetch"


def test_observed_row_is_durable_before_the_archive_is_touched(sach, monkeypatch):
    """Residency is membership, not insertion: what the poll SAW must survive."""
    seen = {}
    stub_fetch(monkeypatch, [alert()])

    def watching_replace(rows, path=None):
        seen["manifest"] = kinds(fs.POLLS)
        raise RuntimeError("died before the replace landed")

    monkeypatch.setattr(fs, "atomic_replace_archive", watching_replace)
    with pytest.raises(RuntimeError):
        fs.poll()
    assert seen["manifest"] == ["started", "observed"]


def test_observed_row_carries_every_returned_hash_not_only_the_new_ones(sach, monkeypatch):
    """Archive holds X, poll returns X+Y: a merge-only record loses the evidence
    that X was still being served, because residency is membership and not
    insertion."""
    stub_fetch(monkeypatch, [alert()])
    fs.poll()
    stub_fetch(monkeypatch, [alert(), alert(identifier=2)])
    fs.poll()
    observed = [r for r in rows_of(fs.POLLS) if r["kind"] == "observed"][-1]
    assert len(observed["sha1s"]) == 2, "observed row recorded only the new alert"
    assert observed["returned"] == 2


def test_a_raised_fetch_still_writes_its_terminal_row(sach, monkeypatch):
    monkeypatch.setattr(fs, "fetch", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("down")))
    with pytest.raises(RuntimeError):
        fs.poll()
    result = [r for r in rows_of(fs.POLLS) if r["kind"] == "result"]
    assert len(result) == 1
    assert result[0]["outcome"] == "failed"
    assert "down" in result[0]["error"]


def test_ok_empty_and_failed_are_each_recorded_and_distinguishable(sach, monkeypatch):
    stub_fetch(monkeypatch, [alert()])
    fs.poll()
    stub_fetch(monkeypatch, [])
    fs.poll()
    monkeypatch.setattr(fs, "fetch", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")))
    with pytest.raises(RuntimeError):
        fs.poll()
    outcomes = [r["outcome"] for r in rows_of(fs.POLLS) if r["kind"] == "result"]
    assert outcomes == ["ok", "empty", "failed"]
    assert len(set(outcomes)) == 3, "an empty window is indistinguishable from a failure"


# --- the archive write is atomic (F2) -------------------------------------


def test_a_truncated_final_line_raises_archive_corrupt_naming_the_line(sach):
    fs.OUT.write_text(
        '{"identifier": 1, "_content_sha1": "a"}\n{"identifier": 2, "_cont\n',
        encoding="utf-8",
    )
    with pytest.raises(fs.ArchiveCorrupt) as exc:
        fs.read_archive(fs.OUT)
    assert "2" in str(exc.value), "the corrupt line number must be named"


def test_a_corrupt_archive_is_never_silently_skipped(sach):
    """Skipping the bad line would silently drop evidence and let the next write
    re-add it as new, which is how the 16,460-row duplication happened."""
    fs.OUT.write_text(
        '{"identifier": 1, "_content_sha1": "a"}\nnot json at all\n', encoding="utf-8"
    )
    with pytest.raises(fs.ArchiveCorrupt):
        fs.read_archive(fs.OUT)


def test_an_interrupted_replace_leaves_the_archive_at_its_pre_write_content(sach, monkeypatch):
    fs.OUT.write_text(
        '{"identifier": 1, "_content_sha1": "a", "_poll_id": "p"}\n', encoding="utf-8"
    )
    before = fs.OUT.read_text(encoding="utf-8")
    monkeypatch.setattr(
        fs.os, "replace", lambda *a, **k: (_ for _ in ()).throw(OSError("interrupted"))
    )
    with pytest.raises(OSError):
        fs.atomic_replace_archive(
            [
                {"identifier": 1, "_content_sha1": "a", "_poll_id": "p"},
                {"identifier": 2, "_content_sha1": "b", "_poll_id": "p"},
            ],
            fs.OUT,
        )
    assert fs.OUT.read_text(encoding="utf-8") == before


def test_the_archive_write_appends_without_rewriting_history(sach, monkeypatch):
    stub_fetch(monkeypatch, [alert()])
    fs.poll()
    first = fs.OUT.read_text(encoding="utf-8")
    stub_fetch(monkeypatch, [alert(identifier=2)])
    fs.poll()
    assert fs.OUT.read_text(encoding="utf-8").startswith(first), "an existing row was rewritten"


# --- F4b: the write path is callable and idempotent -----------------------


def test_two_sequential_polls_over_one_archive_add_each_alert_once(sach, monkeypatch):
    stub_fetch(monkeypatch, [alert(), alert(identifier=2)])
    fs.poll()
    fs.poll()
    assert len(fs.read_archive(fs.OUT)) == 2


def test_read_archive_resolves_the_path_at_call_time(sach):
    """It bound OUT at definition time, so monkeypatching OUT did not redirect
    it and a test could read the real archive."""
    fs.OUT.write_text('{"identifier": 9, "_content_sha1": "z"}\n', encoding="utf-8")
    assert len(fs.read_archive()) == 1


# --- F4: a lock that is never stolen from a live holder -------------------


def test_a_held_live_lock_makes_the_second_call_exit_without_writing(sach, monkeypatch):
    fs.LOCK.write_text("held by another run", encoding="utf-8")
    stub_fetch(monkeypatch, [alert()])
    rc = fs.main([])
    assert rc != 0
    assert not fs.OUT.exists(), "a contending run wrote to the archive"
    assert not fs.POLLS.exists(), "a contending run wrote to the manifest"


def test_live_old_lock_is_not_stolen(sach):
    """Creation age must not break a lock. A slow but live run heartbeats; a
    killed one does not. Keying on creation time stole locks from live runs.

    The holder is a real `acquire_lock` rather than a hand-written file, because
    the heartbeat is now ownership-checked and only the holder may make it: the
    run whose liveness is in question is the run that took the lock.
    """
    fs.acquire_lock(fs.LOCK, poll_id="live-holder-1111")
    old = _time.time() - (fs.LOCK_DEAD_AFTER * 4)
    os.utime(fs.LOCK, (old, old))
    fs.heartbeat(fs.LOCK, poll_id="live-holder-1111")
    with pytest.raises(fs.LockHeld):
        fs.acquire_lock(fs.LOCK)


def test_a_lock_whose_heartbeat_is_older_than_the_threshold_is_broken(sach):
    fs.LOCK.write_text("dead holder", encoding="utf-8")
    old = _time.time() - (fs.LOCK_DEAD_AFTER + 60)
    os.utime(fs.LOCK, (old, old))
    fs.acquire_lock(fs.LOCK)
    assert fs.LOCK.exists()


def test_the_lock_is_not_pid_based():
    """`fetch_footprint_cache.py`'s `_alive()` returns False on PermissionError,
    so a live foreign-owned holder read as dead. Liveness here is heartbeat only."""
    src = Path("pipeline/fetch_sachet.py").read_text(encoding="utf-8")
    assert "os.kill" not in src
    assert "psutil" not in src


# --- F3a(i): bootstrap covers exactly the pre-manifest rows ---------------


def test_manifest_bootstrap_covers_all_existing_archive_hashes(sach, monkeypatch):
    fs.OUT.write_text(
        '{"identifier": 1, "_content_sha1": "aaa"}\n{"identifier": 2, "_content_sha1": "bbb"}\n',
        encoding="utf-8",
    )
    stub_fetch(monkeypatch, [])
    fs.poll()
    boot = [r for r in rows_of(fs.POLLS) if r["kind"] == "bootstrap"]
    assert len(boot) == 1
    assert set(boot[0]["sha1s"]) == {"aaa", "bbb"}


def test_bootstrap_rows_are_not_counted_as_observed_attempts(sach, monkeypatch):
    fs.OUT.write_text('{"identifier": 1, "_content_sha1": "aaa"}\n', encoding="utf-8")
    stub_fetch(monkeypatch, [])
    fs.poll()
    boot = [r for r in rows_of(fs.POLLS) if r["kind"] == "bootstrap"][0]
    assert boot["returned"] is None
    assert boot["poll_id"] is None


def test_bootstrap_runs_inside_the_recorded_attempt(sach, monkeypatch):
    """A DECLARED CONTRACT CHANGE, and the reason it costs nothing.

    This asserted that the bootstrap row is the first row in the manifest. It can
    no longer be: bootstrap can raise, and nothing that can raise may run before
    the attempt is recorded, or a first run over a corrupt archive leaves no trace
    that it ever happened. So the order is now `started` first, then bootstrap
    inside the same attempt.

    Nothing the old ordering was for is lost. Bootstrap and orphan recovery are
    disjoint because bootstrap keys on the ABSENCE of `_poll_id`, never on which
    ran first, which is the whole point of that key and is asserted separately in
    `test_first_run_crash_before_bootstrap_never_attributes_legacy_hashes_to_orphan`.
    """
    fs.OUT.write_text('{"identifier": 1, "_content_sha1": "aaa"}\n', encoding="utf-8")
    stub_fetch(monkeypatch, [])
    fs.poll(poll_id="the-attempt")
    assert kinds(fs.POLLS)[0] == "started", "the attempt was not recorded first"
    boot = [r for r in rows_of(fs.POLLS) if r["kind"] == "bootstrap"]
    assert len(boot) == 1 and boot[0]["sha1s"] == ["aaa"]
    assert boot[0]["poll_id"] is None, "bootstrap was attributed to the running attempt"


def test_first_run_crash_before_bootstrap_never_attributes_legacy_hashes_to_orphan(
    sach, monkeypatch
):
    """Keyed on the ABSENCE of `_poll_id`, which makes bootstrap and orphan
    recovery disjoint by construction rather than by ordering. "Cover every
    uncovered hash" would instead let a bootstrap running after a crash swallow
    the crashed poll's rows."""
    fs.OUT.write_text('{"identifier": 1, "_content_sha1": "legacy"}\n', encoding="utf-8")
    pid = str(uuid.uuid4())
    fs.append_manifest(
        {"kind": "started", "poll_id": pid, "utc": "2026-08-09T00:00:00Z"}, fs.POLLS
    )
    with fs.OUT.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"identifier": 2, "_content_sha1": "crashed", "_poll_id": pid}) + "\n")
    stub_fetch(monkeypatch, [])
    fs.poll()
    boot = [r for r in rows_of(fs.POLLS) if r["kind"] == "bootstrap"][0]
    assert boot["sha1s"] == ["legacy"], "bootstrap swallowed the crashed poll's row"
    rec = [r for r in rows_of(fs.POLLS) if r["kind"] == "reconciled"][0]
    assert rec["sha1s"] == ["crashed"]


def test_poll_id_is_stripped_by_content_sha1():
    """Stamping provenance must not change what alert it is."""
    a = alert()
    assert fs.content_sha1(a) == fs.content_sha1({**a, "_poll_id": "anything"})


# --- F3a(iii): orphan reconciliation, terminating and honest --------------


def test_an_orphaned_started_row_produces_a_reconciled_row_on_the_next_run(sach, monkeypatch):
    pid = str(uuid.uuid4())
    fs.append_manifest(
        {"kind": "started", "poll_id": pid, "utc": "2026-08-09T00:00:00Z"}, fs.POLLS
    )
    stub_fetch(monkeypatch, [])
    fs.poll()
    rec = [r for r in rows_of(fs.POLLS) if r["kind"] == "reconciled"]
    assert len(rec) == 1
    assert rec[0]["poll_id"] == pid


def test_reconciliation_is_idempotent_after_orphan_is_reconciled(sach, monkeypatch):
    """A reconciled orphan still lacks a `result` row, so selecting on "no result"
    alone re-reconciles it on every later run, forever."""
    pid = str(uuid.uuid4())
    fs.append_manifest(
        {"kind": "started", "poll_id": pid, "utc": "2026-08-09T00:00:00Z"}, fs.POLLS
    )
    stub_fetch(monkeypatch, [])
    fs.poll()
    fs.poll()
    fs.poll()
    rec = [r for r in rows_of(fs.POLLS) if r["kind"] == "reconciled" and r["poll_id"] == pid]
    assert len(rec) == 1, f"reconciliation did not terminate: {len(rec)} rows"


def test_reconciliation_attributes_only_the_orphaned_polls_hashes(sach, monkeypatch):
    a_id, b_id = str(uuid.uuid4()), str(uuid.uuid4())
    fs.append_manifest({"kind": "started", "poll_id": a_id, "utc": "t"}, fs.POLLS)
    fs.append_manifest(
        {
            "kind": "result",
            "poll_id": a_id,
            "utc": "t",
            "outcome": "ok",
            "new": 1,
            "archived_sha1s": ["mine"],
            "error": None,
            "elapsed_s": 0.1,
        },
        fs.POLLS,
    )
    fs.append_manifest({"kind": "started", "poll_id": b_id, "utc": "t"}, fs.POLLS)
    fs.OUT.write_text(
        json.dumps({"identifier": 1, "_content_sha1": "mine", "_poll_id": a_id})
        + "\n"
        + json.dumps({"identifier": 2, "_content_sha1": "theirs", "_poll_id": b_id})
        + "\n",
        encoding="utf-8",
    )
    stub_fetch(monkeypatch, [])
    fs.poll()
    rec = [r for r in rows_of(fs.POLLS) if r["kind"] == "reconciled"]
    assert len(rec) == 1 and rec[0]["poll_id"] == b_id
    assert rec[0]["sha1s"] == ["theirs"], "reconciliation claimed another poll's rows"


def test_an_orphan_with_no_observed_row_reconciles_to_membership_unknown(sach, monkeypatch):
    pid = str(uuid.uuid4())
    fs.append_manifest({"kind": "started", "poll_id": pid, "utc": "t"}, fs.POLLS)
    stub_fetch(monkeypatch, [])
    fs.poll()
    rec = [r for r in rows_of(fs.POLLS) if r["kind"] == "reconciled"][0]
    assert rec["membership_known"] is False


def test_an_orphan_with_an_observed_row_reconciles_to_membership_known(sach, monkeypatch):
    pid = str(uuid.uuid4())
    fs.append_manifest({"kind": "started", "poll_id": pid, "utc": "t"}, fs.POLLS)
    fs.append_manifest(
        {"kind": "observed", "poll_id": pid, "utc": "t", "returned": 1, "sha1s": ["seen"]},
        fs.POLLS,
    )
    stub_fetch(monkeypatch, [])
    fs.poll()
    rec = [r for r in rows_of(fs.POLLS) if r["kind"] == "reconciled"][0]
    assert rec["membership_known"] is True


def test_two_orphans_produce_ambiguous_rows_plus_one_unattributed_row(sach, monkeypatch):
    """Never a guess: an archive hash that no surviving row can be attributed to
    is recorded as unattributed rather than assigned to whichever orphan is
    convenient."""
    a_id, b_id = str(uuid.uuid4()), str(uuid.uuid4())
    for pid in (a_id, b_id):
        fs.append_manifest({"kind": "started", "poll_id": pid, "utc": "t"}, fs.POLLS)
    fs.append_manifest(
        {"kind": "bootstrap", "poll_id": None, "utc": "t", "returned": None, "sha1s": []},
        fs.POLLS,
    )
    fs.OUT.write_text(
        json.dumps({"identifier": 1, "_content_sha1": "orphaned"}) + "\n", encoding="utf-8"
    )
    stub_fetch(monkeypatch, [])
    fs.poll()
    rec = [r for r in rows_of(fs.POLLS) if r["kind"] == "reconciled"]
    assert len(rec) == 2
    # `attribution` rather than a boolean: the schema field states WHICH case
    # this is, which a reader can check, where a bare True said only "something
    # was ambiguous somewhere".
    assert {r["attribution"] for r in rec} == {"ambiguous"}
    un = [r for r in rows_of(fs.POLLS) if r["kind"] == "unattributed"]
    assert len(un) == 1 and un[0]["sha1s"] == ["orphaned"] and un[0]["poll_id"] is None


def test_failure_after_archive_before_result_reconciles_on_next_start(sach, monkeypatch):
    stub_fetch(monkeypatch, [alert()])
    real_append = fs.append_manifest

    def fail_on_result(row, path=None):
        if row.get("kind") == "result":
            raise RuntimeError("died between archive and result")
        return real_append(row, path)

    monkeypatch.setattr(fs, "append_manifest", fail_on_result)
    with pytest.raises(RuntimeError):
        fs.poll()
    monkeypatch.setattr(fs, "append_manifest", real_append)
    stub_fetch(monkeypatch, [])
    fs.poll()
    rec = [r for r in rows_of(fs.POLLS) if r["kind"] == "reconciled"]
    assert len(rec) == 1
    assert len(rec[0]["sha1s"]) == 1, "the archived-but-uncounted row was not recovered"


# --- the coverage invariant ----------------------------------------------


def test_archive_coverage_uses_archived_sha1s_and_ignores_observed_sha1s():
    """`observed` is deliberately OUTSIDE the invariant: a poll can die between
    observing and archiving, so an observed hash need not be in the archive."""
    archive = [{"identifier": 1, "_content_sha1": "a", "_poll_id": "p"}]
    manifest = [
        {"kind": "started", "poll_id": "p", "utc": "t"},
        {"kind": "observed", "poll_id": "p", "utc": "t", "returned": 2, "sha1s": ["a", "never"]},
        {
            "kind": "result",
            "poll_id": "p",
            "utc": "t",
            "outcome": "ok",
            "new": 1,
            "archived_sha1s": ["a"],
            "error": None,
            "elapsed_s": 0.1,
        },
    ]
    assert fs.uncovered_hashes(archive, manifest) == set()
    manifest[2]["archived_sha1s"] = []
    assert fs.uncovered_hashes(archive, manifest) == {"a"}


def test_archive_coverage_accepts_unattributed_hashes_for_ambiguous_orphans():
    """The invariant must not reject its own recovery path."""
    archive = [{"identifier": 1, "_content_sha1": "x"}]
    manifest = [{"kind": "unattributed", "poll_id": None, "utc": "t", "sha1s": ["x"]}]
    assert fs.uncovered_hashes(archive, manifest) == set()


def test_the_coverage_invariant_holds_over_a_real_sequence_of_polls(sach, monkeypatch):
    stub_fetch(monkeypatch, [alert()])
    fs.poll()
    stub_fetch(monkeypatch, [alert(), alert(identifier=2)])
    fs.poll()
    stub_fetch(monkeypatch, [])
    fs.poll()
    assert fs.uncovered_hashes(fs.read_archive(fs.OUT), rows_of(fs.POLLS)) == set()


def test_all_manifest_rows_have_declared_kind_and_poll_id(sach, monkeypatch):
    stub_fetch(monkeypatch, [alert()])
    fs.poll()
    for row in rows_of(fs.POLLS):
        assert row["kind"] in fs.MANIFEST_KINDS, row["kind"]
        assert "poll_id" in row
        if row["kind"] == "result":
            assert row["outcome"] in ("ok", "empty", "failed")
        else:
            assert "outcome" not in row, f"{row['kind']} row carries an outcome"


# --- F3a(ii): temp files never become committable ------------------------


def test_a_stale_tmp_present_at_startup_is_removed_before_the_run(sach, monkeypatch):
    stale = Path(str(fs.OUT) + ".tmp")
    stale.write_text("junk from a killed run", encoding="utf-8")
    stub_fetch(monkeypatch, [alert()])
    fs.poll()
    assert not stale.exists()


def test_a_contending_run_does_not_delete_live_holders_temp_file(sach, monkeypatch):
    """Cleanup runs only AFTER the lock is acquired, so a run that loses the race
    exits touching nothing."""
    live_tmp = Path(str(fs.OUT) + ".tmp")
    live_tmp.write_text("the live holder's staged write", encoding="utf-8")
    fs.LOCK.write_text("live holder", encoding="utf-8")
    stub_fetch(monkeypatch, [alert()])
    rc = fs.main([])
    assert rc != 0
    assert live_tmp.read_text(encoding="utf-8") == "the live holder's staged write"


def test_the_temp_file_pattern_is_git_ignored():
    """Asserted through git itself, not by reading .gitignore, because what
    matters is what git would stage.

    Every transient this module can leave in that directory is named: the archive
    temp, the manifest temp, the lock, and the takeover claim. A new transient
    that no pattern covers is a new way for the workflow's `git add` to stage
    something that is not evidence.
    """
    transients = [
        "data/sachet/alerts.jsonl.tmp",
        "data/sachet/polls.jsonl.tmp",
        "data/sachet/.lock",
        "data/sachet/.lock.takeover.1786363586000000000.tmp",
    ]
    out = subprocess.run(
        ["git", "check-ignore", "-v", *transients], capture_output=True, text=True
    )
    assert out.returncode == 0, f"temp and lock files are not ignored: {out.stdout} {out.stderr}"
    assert out.stdout.count("\n") >= len(transients), (
        f"only some transients are ignored: {out.stdout}"
    )


def test_the_archive_and_manifest_themselves_are_not_ignored():
    """They are evidence and there is no way to re-obtain them."""
    for p in ("data/sachet/alerts.jsonl", "data/sachet/polls.jsonl"):
        out = subprocess.run(["git", "check-ignore", p], capture_output=True, text=True)
        assert out.returncode != 0, f"{p} is git-ignored but must be committed"


# --- the kill tests: what survives a SIGKILL ------------------------------
#
# `finally` does not run under SIGKILL, which is the whole reason the protocol
# writes ahead instead of relying on handlers. These spawn a real subprocess and
# kill it, because monkeypatching cannot demonstrate that.


KILL_HARNESS = "\n".join([
    "import os, signal, sys, time",
    "sys.path.insert(0, {root!r})",
    "from pathlib import Path",
    "from pipeline import fetch_sachet as fs",
    "fs.OUT = Path({out!r}); fs.POLLS = Path({polls!r}); fs.LOCK = Path({lock!r})",
    "def hang_fetch(*a, **k):",
    "    os.kill(os.getpid(), signal.SIGTERM)",
    "    time.sleep(30)",
    "fs.fetch = hang_fetch",
    "fs.poll()",
])


def _run_killed(tmp_path, root):
    d = tmp_path / "killed"
    d.mkdir(exist_ok=True)
    script = tmp_path / "harness.py"
    script.write_text(
        KILL_HARNESS.format(
            root=str(root),
            out=str(d / "alerts.jsonl"),
            polls=str(d / "polls.jsonl"),
            lock=str(d / ".lock"),
        ),
        encoding="utf-8",
    )
    subprocess.run([sys.executable, str(script)], capture_output=True, timeout=120)
    return d


def test_forced_timeout_records_a_durable_timed_out_poll(tmp_path):
    """Killed after the write-ahead row: the attempt is on disk even though no
    handler ran."""
    d = _run_killed(tmp_path, Path.cwd())
    manifest = rows_of(d / "polls.jsonl")
    assert [r["kind"] for r in manifest] == ["started"]
    assert manifest[0]["poll_id"]


def test_sigkill_after_fetch_before_observed_marks_membership_unknown(tmp_path, monkeypatch):
    """The crash boundary: a poll that got a response and died before recording
    it leaves no row for what it saw, so the honest record is 'we cannot know'."""
    d = _run_killed(tmp_path, Path.cwd())
    monkeypatch.setattr(fs, "OUT", d / "alerts.jsonl")
    monkeypatch.setattr(fs, "POLLS", d / "polls.jsonl")
    monkeypatch.setattr(fs, "LOCK", d / ".lock")
    monkeypatch.setattr(fs, "fetch", lambda *a, **k: [])
    fs.poll()
    rec = [r for r in rows_of(fs.POLLS) if r["kind"] == "reconciled"]
    assert len(rec) == 1 and rec[0]["membership_known"] is False


def test_sigkill_during_atomic_replace_leaves_no_stageable_temp_artifact(tmp_path):
    d = _run_killed(tmp_path, Path.cwd())
    leftovers = [p.name for p in d.iterdir() if p.name.endswith(".tmp")]
    assert leftovers == [], f"a stageable temp file survived: {leftovers}"


def test_failure_between_alert_and_manifest_replaces_preserves_a_recoverable_cross_file_invariant(
    sach, monkeypatch
):
    """Two files with no shared transaction: whatever the interleaving, the next
    run must be able to state the coverage invariant truthfully."""
    stub_fetch(monkeypatch, [alert()])
    real = fs.append_manifest
    monkeypatch.setattr(
        fs,
        "append_manifest",
        lambda row, path=None: (_ for _ in ()).throw(RuntimeError("gap"))
        if row.get("kind") == "result"
        else real(row, path),
    )
    with pytest.raises(RuntimeError):
        fs.poll()
    monkeypatch.setattr(fs, "append_manifest", real)
    stub_fetch(monkeypatch, [])
    fs.poll()
    assert fs.uncovered_hashes(fs.read_archive(fs.OUT), rows_of(fs.POLLS)) == set()


# --- F9: the committed surfaces say what the capture actually does --------
#
# Four surfaces described the feed, and every one of them carried claims the
# retained responses do not support: a retention bound inferred from two polls,
# an open question the 2026-08-09 capture settled, and a reason-for-absence
# inference. The rule these pin is the one the design argues for: a sentence
# must assert a property of a retained artifact, not of the world.
#
# Two things this block learned the hard way, both worth stating because both
# were live bugs in the first version of these tests:
#
#   * ASSERTING a retracted claim and MENTIONING one are different. The note has
#     to be able to say "this reading is refuted" without tripping a scan for the
#     reading's own words, so a hit is a failure only when its sentence carries
#     no refutation marker.
#   * On a code surface the corpus is docstrings and comments, not source. Scan
#     the source and this file's own list of forbidden phrases matches itself,
#     which is the same self-reference trap that made the proposal gate's
#     self-report check pass on forged input.

SURFACES = {
    "note": (Path("docs/notes/sachet.md"), "markdown"),
    "fetcher": (Path("pipeline/fetch_sachet.py"), "python"),
    "workflow": (Path(".github/workflows/monitor.yml"), "yaml"),
    "tests": (Path("tests/test_sachet.py"), "python"),
}

CAPTURE_UTC = "2026-08-09T18:38:10Z"
RECON_UTC = "2026-08-07T08:24:50Z"
PUNJAB_ID = "1786259146152036"

REFUTATION_MARKERS = ("refut", "closed", "no longer", "was deleted", "retracted", "not supported")

# Words that make a sentence a statement about the whole retained set rather than
# about one response, and the markers that scope it back to named responses.
# Declared here rather than buried in the rule, because both lists are the part a
# reader has to be able to argue with.
RESPONSE_RETENTION_WORDS = ("retain", "captur", "kept", "keeps", "held", "holds",
                            "stored", "stores", "so far")
RESPONSE_SCOPE_MARKERS = ("draw on", "draws on", "drawn on", "rest on", "rests on")


def _response_count_violations(prose: str) -> list:
    """Sentences saying how many responses are held, which the next poll falsifies.

    Positional rather than grammatical: a cardinal within a couple of words of
    "response(s)", in EITHER order, is a count of responses whatever the sentence
    shape. That is the whole design. Matching phrasings instead let "Two responses
    are retained" through a rule written against "three captured responses", which
    is the same word order reversed.

    Three things excuse such a count, and all three are about the claim rather than
    the wording: the sentence scopes to which responses an observation rests on, it
    quotes the stale claim rather than asserting it, or it records that the claim
    was refuted.
    """
    # TWO DECLARED LIMITS, both from false positives this rule produced on its own
    # first run over the real surfaces, and both fixed here rather than by editing
    # the prose, because the prose was right both times.
    #
    #  1. A DATE IS NOT A COUNT. "both captured responses (2026-08-07 and
    #     2026-08-09)" names which responses and states no total, but anything that
    #     reads the digits of a date as a cardinal sees a count in the month
    #     number, so dates come out of the sentence before the search.
    #  2. "one response" IS THE SINGULAR ARTICLE, not a total, and the sentence
    #     that states this very rule uses it. A rule that rejects its own statement
    #     is not a rule. The cost is the declared limit: a surface that said "one
    #     response is retained" would pass, which is a sentence nobody writes and
    #     which the dated-measurement rule would catch anyway.
    number = r"(?:two|three|four|five|six|seven|eight|nine|ten|\d{1,3})"
    near = re.compile(
        rf"\b{number}\b(?:\W+\w+){{0,2}}\W+responses?\b"
        rf"|\bresponses?\b(?:\W+\w+){{0,2}}\W+{number}\b",
        re.I,
    )
    # Headings and table rows are their own units. A markdown heading carries no
    # terminal period, so unwrapping first glued "### The 2026-08-07 absence, kept
    # because it is true of that response" onto the paragraph beneath it and
    # reported a count that neither one states. Same too-wide-a-window defect that
    # let three stale counts through the sweep, found here by this rule's own first
    # run over the real note.
    units, body = [], []
    for line in prose.splitlines():
        if line.lstrip().startswith(("#", "|")):
            units.append(line)
        else:
            body.append(line)
    flat = re.sub(r"(?<!\n)\n(?!\n)", " ", "\n".join(body))
    units += re.split(r"(?<=[.!?])\s+", flat)

    out = []
    for sentence in units:
        low = sentence.lower()
        if not any(w in low for w in RESPONSE_RETENTION_WORDS):
            continue
        if any(m in low for m in RESPONSE_SCOPE_MARKERS + REFUTATION_MARKERS):
            continue
        unquoted = re.sub(r'"[^"]{0,300}"', " ", sentence)
        unquoted = re.sub(r"`[^`]{0,300}`", " ", unquoted)
        unquoted = re.sub(r"\d{4}-\d{2}(?:-\d{2})?(?:T[\d:]+Z?)?", " ", unquoted)
        hit = near.search(unquoted)
        if hit:
            out.append(re.sub(r"\s+", " ", hit.group(0)).strip())
    return out


def _prose(text: str, kind: str) -> str:
    """The prose a surface publishes. Code lines are not English assertions."""
    if kind == "markdown":
        return text
    if kind == "yaml":
        return "\n".join(
            re.sub(r"^\s*#\s?", "", l) for l in text.splitlines() if l.lstrip().startswith("#")
        )
    out = []
    try:
        tree = ast.parse(text)
    except SyntaxError:                                      # pragma: no cover
        tree = None
    if tree is not None:
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                                 ast.AsyncFunctionDef)):
                doc = ast.get_docstring(node)
                if doc:
                    out.append(doc)
    out.extend(
        re.sub(r"^\s*#\s?", "", l) for l in text.splitlines() if l.lstrip().startswith("#")
    )
    return "\n".join(out)


def surface_prose() -> dict:
    return {
        name: _prose(path.read_text(encoding="utf-8"), kind)
        for name, (path, kind) in SURFACES.items()
    }


def unwrapped(text: str) -> str:
    """Collapse single newlines so a claim and its qualifier sit on one line.

    A line-based scan reported that the note failed to say how many identifiers
    the zero-overlap observation covered, when "All 68" was simply on the
    previous physical line.
    """
    return re.sub(r"(?<!\n)\n(?!\n)", " ", text)


def sentences_around(text: str, needle: str) -> list:
    """Every sentence in `text` containing `needle`, case-insensitively."""
    flat = unwrapped(text)
    hits = []
    for sentence in re.split(r"(?<=[.!?])\s+", flat):
        if needle.lower() in sentence.lower():
            hits.append(sentence)
    return hits


def test_retracted_sachet_claims_absent_from_committed_surfaces():
    """The claims the capture refuted must not be ASSERTED on any surface.

    Mentioning one in order to record that it is refuted is allowed and is how
    the note preserves its own correction history.
    """
    retracted = [
        "not established that Punjab",
        "does not publish to Sachet at all",
        "serves roughly the last day",
        "serves only a rolling",
        "useless for a retrospective test",
    ]
    bad = []
    for name, prose in surface_prose().items():
        for claim in retracted:
            for sentence in sentences_around(prose, claim):
                if not any(m in sentence.lower() for m in REFUTATION_MARKERS):
                    bad.append(f"{name}: {sentence.strip()[:110]!r}")
    assert not bad, f"retracted claims still asserted: {bad}"


def test_a_retracted_claim_asserted_without_its_refutation_is_caught():
    """Negative control for the test above, because 'allow it when refuted' is
    exactly the kind of escape hatch that stops a scan from catching anything."""
    forged = "The feed serves roughly the last day only, so history must be kept."
    hits = sentences_around(forged, "serves roughly the last day")
    assert hits and not any(m in hits[0].lower() for m in REFUTATION_MARKERS)


def test_sachet_surfaces_do_not_describe_settled_punjab_question_as_open():
    """Whether Punjab reaches this feed is settled by identifier
    1786259146152036 in the 2026-08-09 response."""
    bad = []
    for name, prose in surface_prose().items():
        for phrase in ("open question 2", "two open questions", "does punjab publish"):
            for sentence in sentences_around(prose, phrase):
                if not any(m in sentence.lower() for m in REFUTATION_MARKERS):
                    bad.append(f"{name}: {sentence.strip()[:110]!r}")
    assert not bad, f"a settled question is still described as open: {bad}"


def test_sachet_note_preserves_dated_2026_08_07_absence():
    """A true dated observation must survive the correction of the conclusion
    drawn from it. Deleting it would damage the record rather than fix it."""
    text = SURFACES["note"][0].read_text(encoding="utf-8")
    assert "2026-08-07" in text
    assert "zero rows naming" in text.lower()
    assert "haryana sdma" in text.lower(), "the neighbouring sender table was dropped"


def test_preserved_dated_observations_are_scoped_to_retained_artifact():
    """The absence must be a property of that response, not of the feed."""
    text = SURFACES["note"][0].read_text(encoding="utf-8")
    hits = sentences_around(text, "zero rows naming")
    assert hits, "the absence sentence moved; rescope this test with it"
    assert any("response" in h.lower() for h in hits), (
        f"absence is not scoped to a retained response: {hits}"
    )
    assert any("2026-08-07" in h for h in hits), "the absence is stated without its date"


def test_sachet_surfaces_do_not_infer_reason_for_sender_absence():
    """A single later row cannot establish WHY a sender was absent earlier. A
    surface may name that as an inference; it may not assert it."""
    for name, prose in surface_prose().items():
        for phrase in ("simply had nothing to say", "had nothing to say on a day"):
            assert phrase not in prose.lower(), f"{name} asserts a reason for the absence"
    note = SURFACES["note"][0].read_text(encoding="utf-8")
    for sentence in sentences_around(note, "nothing to publish"):
        assert "reason" in sentence.lower() or "does **not** confirm" in sentence.lower(), (
            f"the alternative reading is stated without marking it an inference: {sentence!r}"
        )


def test_sachet_surfaces_contain_only_dated_artifact_observations():
    """Every figure in the note is tied to a dated response or to the archive."""
    text = SURFACES["note"][0].read_text(encoding="utf-8")
    assert "70 alerts" in text and "56 alerts" in text
    assert RECON_UTC in text and CAPTURE_UTC in text, "both poll timestamps must be cited"
    assert PUNJAB_ID in text, "the settling identifier must be cited"


def test_no_surface_asserts_a_retention_bound():
    """Two polls 58 hours apart cannot measure the width of a window. A surface
    may say no backfill route is known; it may not say how long the feed keeps
    an alert."""
    pattern = re.compile(
        r"(serves|keeps|retains|holds)[^.]{0,40}(last|rolling|~?\d+[- ]?(day|hour))", re.I
    )
    bad = []
    for name, prose in surface_prose().items():
        for m in pattern.finditer(unwrapped(prose)):
            sentence = sentences_around(prose, m.group(0))
            if not sentence or not any(
                mark in sentence[0].lower() for mark in REFUTATION_MARKERS
            ):
                bad.append(f"{name}: {m.group(0)!r}")
    assert not bad, f"a retention bound is asserted: {bad}"


def test_the_archive_figures_in_the_note_are_dated_and_not_a_running_total():
    """The note may quote the archive's size only as a dated measurement.

    The first version of this test asserted the note's row count equalled the
    live file. That would have turned the next scheduled run red: monitor.yml
    runs the suite BEFORE `fetch_sachet.py`, so the poll that appends rows leaves
    the note stale for the following run, and "never publish from a red tree"
    would then take down the whole publish. A growing number cannot be pinned;
    a dated observation can.
    """
    text = SURFACES["note"][0].read_text(encoding="utf-8")
    hits = sentences_around(text, "rows in")
    assert hits, "the note states no archive size at all"
    claim = hits[0]
    assert re.search(r"2026-\d{2}-\d{2}", claim), (
        f"the archive size is stated without the date it was measured: {claim!r}"
    )
    rows = int(re.search(r"(\d+) rows in", claim).group(1))
    live = len([
        l for l in Path("data/sachet/alerts.jsonl").read_text(encoding="utf-8").splitlines()
        if l.strip()
    ])
    assert rows <= live, (
        f"the note claims {rows} rows measured in the past but the archive holds "
        f"{live}; an append-only archive cannot shrink, so one of them is wrong"
    )


def test_the_two_polls_zero_overlap_is_stated_with_both_timestamps():
    """The measurement that replaced the retention claim, cited so a reader can
    recompute it rather than take it."""
    text = SURFACES["note"][0].read_text(encoding="utf-8")
    hits = sentences_around(text, "were absent at")
    assert hits, "the zero-overlap observation is missing from the note"
    claim = hits[0]
    assert RECON_UTC in claim and CAPTURE_UTC in claim, (
        f"the observation must cite both poll timestamps: {claim!r}"
    )
    assert "68" in claim, f"the observation must say how many identifiers it covers: {claim!r}"


def test_the_fetcher_docstring_states_what_the_capture_settles():
    """The docstring is the surface a reader of the code meets first, and it
    carried the retracted claim in its own words."""
    doc = ast.get_docstring(ast.parse(SURFACES["fetcher"][0].read_text(encoding="utf-8")))
    assert doc, "the fetcher lost its module docstring"
    assert PUNJAB_ID in doc, "the settling identifier is not in the fetcher docstring"
    assert RECON_UTC in doc and CAPTURE_UTC in doc
    assert "watch" in doc.lower(), "the WATCH-not-flood caveat is missing"


# --- the four tests the implementation review named ------------------------
#
# Every one of these covers a defect that 79 passing tests did not catch, and
# the reason each slipped through is worth recording next to the test.


def test_failed_archive_replace_never_claims_unwritten_hashes(sach, monkeypatch):
    """A result row must never claim hashes the archive did not receive.

    `fresh` was computed before the replace and the `finally` reported it, so a
    replace that RAISED still produced `new > 0` and an `archived_sha1s` list.
    That is archive-before-terminal inverted, and it is worse than a wrong
    number: those hashes read as covered by the coverage invariant forever, so
    reconciliation would never repair the gap.

    The existing interrupted-replace test checked the ARCHIVE was untouched and
    never checked what the manifest then said about it.
    """
    stub_fetch(monkeypatch, [alert(), alert(identifier=2)])
    monkeypatch.setattr(
        fs, "atomic_replace_archive",
        lambda rows, path=None: (_ for _ in ()).throw(OSError("replace failed")),
    )
    with pytest.raises(OSError):
        fs.poll()

    result = [r for r in rows_of(fs.POLLS) if r["kind"] == "result"][0]
    assert result["outcome"] == "failed"
    assert result["new"] == 0, "the result row counted alerts the archive never got"
    assert result["archived_sha1s"] == [], (
        "the result row claimed hashes that were never written"
    )
    # And the invariant must not have been satisfied by a false claim: the
    # archive is empty, so there is nothing to cover either way.
    assert fs.read_archive(fs.OUT) == []
    assert fs.uncovered_hashes(fs.read_archive(fs.OUT), rows_of(fs.POLLS)) == set()


def test_a_partial_replace_failure_still_reconciles_on_the_next_run(sach, monkeypatch):
    """The same defect from the other side: when the replace SUCCEEDS but the
    result row never lands, the hashes must be uncovered so repair can find them."""
    stub_fetch(monkeypatch, [alert()])
    real = fs.append_manifest
    monkeypatch.setattr(
        fs, "append_manifest",
        lambda row, path=None: (_ for _ in ()).throw(RuntimeError("gap"))
        if row.get("kind") == "result" else real(row, path),
    )
    with pytest.raises(RuntimeError):
        fs.poll()
    assert fs.uncovered_hashes(fs.read_archive(fs.OUT), rows_of(fs.POLLS)) != set(), (
        "an archived-but-unreported row must read as uncovered until repaired"
    )
    monkeypatch.setattr(fs, "append_manifest", real)
    stub_fetch(monkeypatch, [])
    fs.poll()
    assert fs.uncovered_hashes(fs.read_archive(fs.OUT), rows_of(fs.POLLS)) == set()


def test_fetch_heartbeats_at_start_of_every_retry_attempt(sach, monkeypatch):
    """The lock is never stolen from a live holder ONLY if the holder heartbeats.

    `heartbeat()` existed and production never called it, so the guarantee rested
    on a function only the tests invoked. A run retrying four times with backoff
    could sit well past the dead threshold without refreshing anything.
    """
    fs.acquire_lock(fs.LOCK)
    beats = []
    monkeypatch.setattr(fs, "heartbeat", lambda path=None: beats.append(path))
    monkeypatch.setattr(fs.time, "sleep", lambda *_: None)

    calls = {"n": 0}

    class Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps([alert()]).encode()

    def flaky(*a, **k):
        calls["n"] += 1
        if calls["n"] < 3:
            raise OSError("transient")
        return Resp()

    monkeypatch.setattr(fs.urllib.request, "urlopen", flaky)
    fs.fetch(retries=4, backoff=0)
    assert len(beats) == 3, f"heartbeat fired {len(beats)} times for 3 attempts"


def test_a_slow_run_that_heartbeats_keeps_its_lock(sach, monkeypatch):
    """The property the heartbeat exists for, asserted end to end."""
    fs.acquire_lock(fs.LOCK)
    old = _time.time() - (fs.LOCK_DEAD_AFTER * 2)
    os.utime(fs.LOCK, (old, old))

    monkeypatch.setattr(fs.time, "sleep", lambda *_: None)
    monkeypatch.setattr(
        fs.urllib.request, "urlopen",
        lambda *a, **k: (_ for _ in ()).throw(OSError("down")),
    )
    with pytest.raises(RuntimeError):
        fs.fetch(retries=2, backoff=0)
    # Having heartbeated during the retries, the lock is no longer breakable.
    with pytest.raises(fs.LockHeld):
        fs.acquire_lock(fs.LOCK)


def test_bootstrap_emits_one_row_per_first_seen_utc(sach, monkeypatch):
    """The signed contract is one bootstrap row per distinct `_first_seen_utc`.

    One combined row loses which day each legacy alert was first seen, which is
    the only provenance those rows have: they predate the manifest, so
    `_first_seen_utc` is the whole record of when they arrived.
    """
    fs.OUT.write_text(
        json.dumps({"identifier": 1, "_content_sha1": "a",
                    "_first_seen_utc": "2026-08-07T08:24:50Z"}) + "\n" +
        json.dumps({"identifier": 2, "_content_sha1": "b",
                    "_first_seen_utc": "2026-08-07T08:24:50Z"}) + "\n" +
        json.dumps({"identifier": 3, "_content_sha1": "c",
                    "_first_seen_utc": "2026-08-09T18:38:10Z"}) + "\n",
        encoding="utf-8")
    stub_fetch(monkeypatch, [])
    fs.poll()

    boot = [r for r in rows_of(fs.POLLS) if r["kind"] == "bootstrap"]
    assert len(boot) == 2, f"expected one row per first_seen_utc, got {len(boot)}"
    by_utc = {r["utc"]: r for r in boot}
    assert set(by_utc) == {"2026-08-07T08:24:50Z", "2026-08-09T18:38:10Z"}
    assert sorted(by_utc["2026-08-07T08:24:50Z"]["sha1s"]) == ["a", "b"]
    assert by_utc["2026-08-09T18:38:10Z"]["sha1s"] == ["c"]
    for row in boot:
        assert row["returned"] is None and row["poll_id"] is None
        assert "predates the manifest" in row["note"]
    assert fs.uncovered_hashes(fs.read_archive(fs.OUT), rows_of(fs.POLLS)) == set()


def test_bootstrap_rows_carrying_no_first_seen_utc_are_still_covered(sach, monkeypatch):
    """A legacy row with no `_first_seen_utc` cannot be grouped by one, and
    dropping it would leave the invariant false on day one."""
    fs.OUT.write_text(json.dumps({"identifier": 1, "_content_sha1": "nodate"}) + "\n",
                      encoding="utf-8")
    stub_fetch(monkeypatch, [])
    fs.poll()
    assert fs.uncovered_hashes(fs.read_archive(fs.OUT), rows_of(fs.POLLS)) == set()


def test_reconciliation_implements_declared_attribution_schema(sach, monkeypatch):
    """`reconciled` rows carry `attribution`, valued sole_orphan or ambiguous.

    A boolean `ambiguous` is not the signed schema, and the difference is not
    cosmetic: `sole_orphan` states that the residue is attributable to exactly
    one attempt, which is a claim a reader can check, while a bare False says
    only that nothing was ambiguous.
    """
    pid = str(uuid.uuid4())
    fs.append_manifest({"kind": "started", "poll_id": pid, "utc": "t"}, fs.POLLS)
    fs.append_manifest({"kind": "bootstrap", "poll_id": None, "utc": "t",
                        "returned": None, "sha1s": [], "note": "predates the manifest"},
                       fs.POLLS)
    fs.OUT.write_text(json.dumps({"identifier": 1, "_content_sha1": "residual"}) + "\n",
                      encoding="utf-8")
    stub_fetch(monkeypatch, [])
    fs.poll()

    rec = [r for r in rows_of(fs.POLLS) if r["kind"] == "reconciled"]
    assert len(rec) == 1
    assert rec[0]["attribution"] == "sole_orphan", (
        f"expected the sole-orphan branch, got {rec[0].get('attribution')!r}"
    )
    assert rec[0]["sha1s"] == ["residual"], "the sole orphan must claim the residue"
    assert "ambiguous" not in rec[0], "the boolean was left beside the schema field"
    assert fs.uncovered_hashes(fs.read_archive(fs.OUT), rows_of(fs.POLLS)) == set()


def test_multiple_orphans_use_the_ambiguous_attribution_value(sach, monkeypatch):
    a_id, b_id = str(uuid.uuid4()), str(uuid.uuid4())
    for pid in (a_id, b_id):
        fs.append_manifest({"kind": "started", "poll_id": pid, "utc": "t"}, fs.POLLS)
    fs.append_manifest({"kind": "bootstrap", "poll_id": None, "utc": "t",
                        "returned": None, "sha1s": [], "note": "predates the manifest"},
                       fs.POLLS)
    fs.OUT.write_text(json.dumps({"identifier": 1, "_content_sha1": "residual"}) + "\n",
                      encoding="utf-8")
    stub_fetch(monkeypatch, [])
    fs.poll()

    rec = [r for r in rows_of(fs.POLLS) if r["kind"] == "reconciled"]
    assert len(rec) == 2
    assert {r["attribution"] for r in rec} == {"ambiguous"}
    un = [r for r in rows_of(fs.POLLS) if r["kind"] == "unattributed"]
    assert len(un) == 1 and un[0]["sha1s"] == ["residual"] and un[0]["poll_id"] is None


def test_a_stamped_hash_is_never_filed_as_unattributable(sach, monkeypatch):
    """The deviation from the literal contract, pinned so it is visible.

    The contract says that with more than one orphan every orphan gets `sha1s:
    []` and the residue goes to an `unattributed` row, whose declared meaning is
    "unclaimed hashes that multiple orphans could equally explain". A row
    carrying an unambiguous `_poll_id` IS explained, so filing it there would be
    a false statement in the record. Stamped hashes therefore stay with the poll
    that stamped them, and only unstamped residue is called unattributable.
    """
    a_id, b_id = str(uuid.uuid4()), str(uuid.uuid4())
    for pid in (a_id, b_id):
        fs.append_manifest({"kind": "started", "poll_id": pid, "utc": "t"}, fs.POLLS)
    fs.append_manifest({"kind": "bootstrap", "poll_id": None, "utc": "t",
                        "returned": None, "sha1s": [], "note": "predates the manifest"},
                       fs.POLLS)
    fs.OUT.write_text(
        json.dumps({"identifier": 1, "_content_sha1": "stamped", "_poll_id": a_id}) + "\n" +
        json.dumps({"identifier": 2, "_content_sha1": "loose"}) + "\n",
        encoding="utf-8")
    stub_fetch(monkeypatch, [])
    fs.poll()

    rec = {r["poll_id"]: r for r in rows_of(fs.POLLS) if r["kind"] == "reconciled"}
    assert rec[a_id]["sha1s"] == ["stamped"], "a provably-attributable hash was discarded"
    assert rec[b_id]["sha1s"] == []
    un = [r for r in rows_of(fs.POLLS) if r["kind"] == "unattributed"]
    assert un[0]["sha1s"] == ["loose"], "only unstamped residue is unattributable"
    assert fs.uncovered_hashes(fs.read_archive(fs.OUT), rows_of(fs.POLLS)) == set()


def test_note_scopes_enumeration_claim_to_tested_routes():
    """"No enumeration endpoint exists" is a claim about the site; the evidence
    covers the routes tried and the HTML inspected.

    Same class as the retention bound and the Punjab non-publication claim: true
    for all anyone here knows, and still a defect, because nothing retained
    establishes what the site does not expose.
    """
    text = SURFACES["note"][0].read_text(encoding="utf-8")
    for banned in ("No enumeration endpoint exists", "no enumeration endpoint exists"):
        assert banned not in text, f"unscoped enumeration claim: {banned!r}"
    hits = sentences_around(text, "enumeration routes")
    assert hits, "the note no longer records the enumeration probe at all"
    claim = hits[0].lower()
    assert "tried" in claim or "returned 404" in claim, (
        f"the enumeration result is not scoped to what was tried: {hits[0]!r}"
    )


# --- counters on the stated contract: lock contents, release, attempt ids ---


def test_lock_file_contains_attempt_poll_id_and_no_pid(sach, monkeypatch):
    """The lock names the ATTEMPT holding it, and never a PID.

    The contract is explicit that a PID must not appear, because PID liveness is
    the mechanism this design exists to avoid, and a PID in the file invites the
    next reader to use it. Production wrote the PID as the first field anyway.

    My earlier test asserted `os.kill` and `psutil` were absent from the source,
    which was true and missed the point: it checked that we do not USE a pid for
    liveness, never that we do not WRITE one. So the lock also carried nothing
    linking it to the manifest attempt that held it.
    """
    stub_fetch(monkeypatch, [alert()])
    seen = {}

    real_fetch = fs.fetch

    def capture_then_fetch(*a, **k):
        seen["lock"] = fs.LOCK.read_text(encoding="utf-8")
        return [alert()]

    monkeypatch.setattr(fs, "fetch", capture_then_fetch)
    assert fs.main([]) == 0

    body = seen["lock"]
    assert str(os.getpid()) not in body, f"the lock file names a PID: {body!r}"
    assert "pid" not in body.lower(), f"the lock file mentions a pid: {body!r}"

    # It must name the attempt, and that id must be the one in the manifest.
    started = [r for r in rows_of(fs.POLLS) if r["kind"] == "started"]
    assert len(started) == 1
    assert started[0]["poll_id"] in body, (
        f"the lock does not name its attempt: {body!r} vs {started[0]['poll_id']}"
    )
    # And a timestamp, so a reader can see how old the attempt is.
    assert re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", body), body


def test_the_lock_is_released_after_a_successful_run(sach, monkeypatch):
    stub_fetch(monkeypatch, [alert()])
    assert fs.main([]) == 0
    assert not fs.LOCK.exists(), "the lock outlived the run that took it"


def test_round_trip_through_main_twice(sach, monkeypatch):
    """Two successful `main()` calls over one archive add each alert once.

    This is B7 from the original diagnosis and it stayed open through fourteen
    rounds: the old round-trip test hand-rolled the write loop instead of calling
    the entry point, so nothing ever exercised `main()` end to end twice. A test
    that re-implements the code under test cannot catch the code under test.
    """
    stub_fetch(monkeypatch, [alert(), alert(identifier=2, disaster_type="Cyclone")])
    assert fs.main([]) == 0
    first = fs.OUT.read_text(encoding="utf-8")
    assert len(fs.read_archive(fs.OUT)) == 2

    assert fs.main([]) == 0
    assert len(fs.read_archive(fs.OUT)) == 2, "the second run duplicated the archive"
    assert fs.OUT.read_text(encoding="utf-8") == first, "the second run rewrote history"

    # Both attempts are recorded, and the invariant holds across both.
    assert [r["kind"] for r in rows_of(fs.POLLS)].count("result") == 2
    assert fs.uncovered_hashes(fs.read_archive(fs.OUT), rows_of(fs.POLLS)) == set()
    assert not fs.LOCK.exists()


def test_main_twice_records_two_distinct_attempts(sach, monkeypatch):
    """Deduplicating the ARCHIVE must not deduplicate the RECORD of polling."""
    stub_fetch(monkeypatch, [alert()])
    fs.main([])
    fs.main([])
    ids = [r["poll_id"] for r in rows_of(fs.POLLS) if r["kind"] == "started"]
    assert len(ids) == 2 and len(set(ids)) == 2, "two runs collapsed into one attempt"


def test_note_scopes_manifest_completeness_to_post_bootstrap_polls():
    """The note may not claim the manifest records every poll.

    F3a says in terms that the bootstrap row RECONSTRUCTS pre-manifest hashes
    rather than recording the attempts that fetched them, and that it cannot know
    how many the feed served on those days. A completeness claim written one
    section away from the design that denies completeness is the same defect class
    as the retention bound: a true-sounding sentence the artifacts do not support.
    """
    text = SURFACES["note"][0].read_text(encoding="utf-8")

    # Checking for a banned SUBSTRING was the wrong shape, and it failed on a
    # correctly scoped sentence: "records every poll made since the manifest
    # began" contains "records every poll". What matters is not whether the words
    # appear but whether the sentence carries its scope, so the claim and its
    # qualifier are checked together.
    # Narrowed to sentences that make a RECORDING claim about every poll. Plain
    # "every poll writes a started row" describes the protocol and is not a
    # completeness claim about the manifest, so matching "every poll" alone
    # flagged a correct sentence.
    claim = re.compile(r"record(?:s|ed|ing|\s+of)?\s+(?:\w+\s+){0,3}every poll", re.I)
    scope = ("since", "from that point", "forward from", "after the manifest",
             "makes no claim before")
    for hit in sentences_around(text, "every poll"):
        if not claim.search(hit):
            continue
        assert any(m in hit.lower() for m in scope), (
            f"the manifest's completeness is claimed without its starting point: {hit!r}"
        )

    hits = sentences_around(text, "polls.jsonl")
    assert hits, "the note no longer mentions the manifest at all"
    joined = " ".join(hits).lower()
    assert "reconstruct" in joined, (
        f"the note does not say the first row is a reconstruction: {hits!r}"
    )

    # Negative control, because "allow it when scoped" is the kind of allowance
    # that stops a check from catching anything.
    forged = "The manifest records every poll ever made against the feed."
    assert not any(m in forged.lower() for m in scope)


# --- counters on the prose: a surface must match the protocol it describes --


def test_note_describes_conditional_observed_and_result_rows():
    """The note must not promise rows the protocol does not always write.

    It said every poll writes an `observed` row and a terminal `result` row. A
    failed fetch never writes `observed`, and a poll killed by the step timeout
    leaves only `started`, which is the entire reason the ordering exists. So the
    note contradicted the protocol it documents, and in the direction that
    matters: a reader would treat a missing row as data loss rather than as the
    record it is.
    """
    text = SURFACES["note"][0].read_text(encoding="utf-8")
    for hit in sentences_around(text, "observed"):
        if "every poll" not in hit.lower():
            continue
        assert "only if" in hit.lower() or "depends" in hit.lower(), (
            f"the note promises an observed row unconditionally: {hit!r}"
        )
    low = text.lower()
    assert "only if the fetch returned" in low, (
        "the note does not say the observed row is conditional on a response"
    )
    assert "does not" in low and "started" in low, (
        "the note does not say a killed poll leaves only its started row"
    )


def test_poll_docstring_matches_return_value():
    """A docstring that names the wrong return value is a lie a reader acts on."""
    import ast as _ast

    src = SURFACES["fetcher"][0].read_text(encoding="utf-8")
    tree = _ast.parse(src)
    fn = next(n for n in tree.body
              if isinstance(n, _ast.FunctionDef) and n.name == "poll")
    doc = _ast.get_docstring(fn) or ""
    assert "terminal row" not in doc.split("Returns")[-1].split(".")[0], (
        "the docstring still claims poll() returns the terminal row"
    )
    # The keys it really returns must be the keys it advertises.
    returned = set()
    for node in _ast.walk(fn):
        if isinstance(node, _ast.Return) and isinstance(node.value, _ast.Dict):
            returned |= {k.value for k in node.value.keys
                         if isinstance(k, _ast.Constant)}
    assert returned, "poll() no longer returns a dict; update this test with it"
    for key in returned:
        assert key in doc, f"poll() returns {key!r} and the docstring does not say so"


def test_sachet_surfaces_remove_or_mark_satellite_revisit_claims_as_inference():
    """The fourth claim family the F9 inventory named, and the last to be fixed.

    Three families were rescoped and this one shipped anyway: the note's title
    asserted the feed's dates are not set by satellite revisit, and the fetcher
    opened by asserting the same about every ground-truth source. Both are claims
    about the world; the archive covers the routes this project has actually
    reached, over the days it has actually polled.
    """
    for name in ("note", "fetcher"):
        text = SURFACES[name][0].read_text(encoding="utf-8")
        prose = _prose(text, SURFACES[name][1])
        for banned in ("dates are not set by satellite revisit",
                       "sources this project reaches through satellite products carry"):
            assert banned.lower() not in prose.lower(), f"{name}: unscoped {banned!r}"

        # Where the framing survives, it must be marked as an inference or scoped
        # to what was actually reached.
        for hit in sentences_around(prose, "revisit"):
            low = hit.lower()
            if "inference" in low or "has reached" in low or "has actually reached" in low:
                continue
            assert "gap" in low or "acquisition" in low or "overpass" in low, (
                f"{name}: unscoped revisit claim: {hit!r}"
            )


def test_no_surface_states_a_total_count_of_retained_responses():
    """A count of captured responses is a number the pipeline increments.

    The note's title said "what three captured responses show" and the fourth poll
    made it stale within the hour. Same rule as the archive row count: a surface
    may name the specific dated responses an observation rests on, and may not
    state a total that grows. The one test in this file that pins a count pins it
    as a dated measurement with a monotonic bound for exactly this reason.

    EVERY declared surface, and any grammar. The first version of this scanned two
    of the four surfaces and matched one word order, so "Two responses are
    retained" in the fetcher and "three captured responses" in a docstring in this
    very file both walked straight through the rule written to stop them. That is
    the too-narrow class again: a rule about counts that only sees the phrasing its
    author happened to have in mind. `_response_count_violations` is positional
    instead, and `test_response_count_rule_covers_all_declared_surfaces_and_grammar`
    is the control that keeps it that way.
    """
    for name in SURFACES:
        prose = _prose(SURFACES[name][0].read_text(encoding="utf-8"), SURFACES[name][1])
        bad = _response_count_violations(prose)
        assert not bad, (
            f"{name}: states a total count of responses, which grows every poll: {bad}"
        )


def test_response_count_rule_covers_all_declared_surfaces_and_grammar():
    """The control over the rule above, because the rule was the defect twice.

    Two independent ways it went wrong, so two things are pinned here. It scanned a
    subset of the surfaces, and it matched a subset of the grammars. Neither is
    visible from reading the rule: both look like a rule about response counts.
    """
    # Every surface the project declares is scanned. Not a copy of the list, the
    # list, so adding a fifth surface cannot leave it unscanned.
    scanned = inspect.getsource(test_no_surface_states_a_total_count_of_retained_responses)
    assert "for name in SURFACES" in scanned, (
        "the surface test enumerates surfaces by hand again"
    )
    assert len(SURFACES) >= 4, SURFACES

    # Any grammar. Each of these states a total that the next poll falsifies, and
    # the first two are the exact sentences that survived the previous version.
    for stated in (
        "Two responses are retained, at 2026-08-07T08:24:50Z and 2026-08-09T18:38:10Z.",
        "What is retained covers three captured responses.",
        "The archive keeps four responses so far.",
        "So far 5 responses have been captured.",
        "Responses retained: two.",
    ):
        assert _response_count_violations(stated), f"a growing total went unseen: {stated!r}"

    # And what is allowed stays allowed, or the rule would just ban arithmetic:
    # naming WHICH responses an observation rests on, quoting a stale claim in
    # order to record it, and per-response counts that do not grow.
    for scoped in (
        "The observations below draw on the responses of 2026-08-07T08:24:50Z and "
        "2026-08-09T18:38:10Z.",
        'The title said "what three captured responses show" and the fourth poll '
        "made it stale, so the count is no longer on any surface.",
        "All 68 identifiers in the 2026-08-07 response were absent from the "
        "2026-08-09 response.",
    ):
        assert not _response_count_violations(scoped), f"a scoped claim was rejected: {scoped!r}"


# --- counters on the protocol's own record-keeping --------------------------
#
# Three defects that share a shape: the protocol's own record-keeping was not
# held to the standard the protocol imposes on the archive. The manifest was written the one way the
# archive is never written; the lock was taken over by two operations with no
# check between them; and the preflight ran before the row that records that
# anything was attempted at all.


def test_interrupted_manifest_append_leaves_previous_manifest_parseable(sach, monkeypatch):
    """A survival record that cannot survive the kill it exists to record.

    `append_manifest` wrote in place, so an interruption partway through the
    write left a truncated line in the file `read_manifest` reads strictly.
    Every later poll then raised `ArchiveCorrupt` in its first few lines, before
    any repair could run: one unlucky kill and the capture is dead for good. It
    would have fired in CI, where a step timeout kills by design.

    The check is on the file the READER reads: at the moment the new bytes are
    durable, the manifest must still be exactly what it was, because that is the
    only condition under which an interruption at that point cannot corrupt it.
    """
    import stat as _stat

    fs.append_manifest({"kind": "started", "poll_id": "first", "utc": "t"}, fs.POLLS)
    before = fs.POLLS.read_text(encoding="utf-8")

    real_fsync = os.fsync
    seen = []

    def dying_fsync(fd):
        if _stat.S_ISDIR(os.fstat(fd).st_mode):  # the directory entry, not the data
            return real_fsync(fd)
        real_fsync(fd)
        seen.append(fs.POLLS.read_text(encoding="utf-8"))
        raise OSError("killed with the staged bytes already on disk")

    monkeypatch.setattr(os, "fsync", dying_fsync)
    with pytest.raises(OSError):
        fs.append_manifest({"kind": "started", "poll_id": "second", "utc": "t"}, fs.POLLS)
    monkeypatch.setattr(os, "fsync", real_fsync)

    assert seen, "nothing was ever fsynced, so no durability is being claimed"
    assert seen[0] == before, (
        "the new row was written into the file the reader reads, so an "
        "interruption at that point truncates the manifest"
    )
    assert [r["poll_id"] for r in fs.read_manifest(fs.POLLS)] == ["first"]
    assert fs.POLLS.read_text(encoding="utf-8") == before


def test_the_manifest_is_replaced_never_appended_in_place(sach):
    """The same property as the test above, reached by a different instrument.

    One check on the bytes at the fsync boundary and one on the identity of the
    file itself, because "written atomically" has more than one shape and a
    check for one shape is the class of hole this tranche keeps finding. An
    implementation that unlinked and rewrote in place would pass the identity
    check while failing the byte check; one that appended after fsyncing
    something else would pass the byte check while failing this one.
    """
    fs.append_manifest({"kind": "started", "poll_id": "a", "utc": "t"}, fs.POLLS)
    first = fs.POLLS.stat()
    if not first.st_ino:  # pragma: no cover - filesystem without file ids
        pytest.skip("no usable file identity on this filesystem")
    fs.append_manifest({"kind": "started", "poll_id": "b", "utc": "t"}, fs.POLLS)
    assert fs.POLLS.stat().st_ino != first.st_ino, (
        "the manifest was mutated in place, so a partial write lands in it"
    )


def test_rewriting_the_manifest_preserves_earlier_rows_byte_for_byte(sach):
    """Writing the whole file must not reformat the history it rewrites.

    The manifest is a provenance record. Re-serialising an old row would change
    bytes a later reader may already have quoted, and would hide a hand-repaired
    line by silently normalising it.

    LIMIT, stated because the name of this test is broader than what it checks: the
    fixture is written here and is therefore LF, so it cannot see line endings being
    normalised on a CRLF file, which is what the live manifest is. The claim this
    pins is that earlier ROWS survive, not that earlier BYTES do.
    """
    fs.append_manifest({"kind": "started", "poll_id": "a", "utc": "t"}, fs.POLLS)
    before = fs.POLLS.read_text(encoding="utf-8")
    fs.append_manifest({"kind": "started", "poll_id": "b", "utc": "t"}, fs.POLLS)
    after = fs.POLLS.read_text(encoding="utf-8")
    assert after.startswith(before), "an earlier manifest row was rewritten"
    assert len(fs.read_manifest(fs.POLLS)) == 2


def test_a_manifest_missing_its_final_newline_is_not_welded_to_the_next_row(sach):
    """The truncation that parses, and is therefore the dangerous one.

    A kill can land after a row's bytes and before its newline. That file still
    reads correctly, so nothing complains; appending to it then joins two JSON
    objects on one line and makes BOTH unreadable, which is the brick. Closing
    the line loses nothing and is the only repair that drops no evidence.
    """
    fs.POLLS.parent.mkdir(parents=True, exist_ok=True)
    fs.POLLS.write_text(
        '{"kind": "started", "poll_id": "a", "utc": "t"}\n'
        '{"kind": "observed", "poll_id": "a", "utc": "t", "returned": 0, "sha1s": []}',
        encoding="utf-8",
    )
    assert len(fs.read_manifest(fs.POLLS)) == 2, "the fixture itself must parse"
    fs.append_manifest({"kind": "started", "poll_id": "b", "utc": "t"}, fs.POLLS)
    rows = fs.read_manifest(fs.POLLS)
    assert [r["poll_id"] for r in rows] == ["a", "a", "b"]


def test_stale_lock_takeover_is_single_winner_and_owner_safe(sach, monkeypatch):
    """Two runs that both judge one lock dead must not both end up holding it.

    The takeover was `unlink` then `O_EXCL` create: two operations with nothing
    between them tying the second to the first. Interleaved, both contenders came
    away believing they held the lock, and the loser's unlink deleted the
    winner's live lock on the way past. Two writers on one archive is the
    duplication incident this project exists to stop repeating.

    The interleaving is forced rather than raced: the competing run completes an
    entire takeover while we sit between judging the lock stale and acting on it.
    """
    fs.LOCK.write_text("dead-attempt-0000 2026-08-09T00:00:00Z\n", encoding="utf-8")
    dead = _time.time() - (fs.LOCK_DEAD_AFTER + 60)
    os.utime(fs.LOCK, (dead, dead))

    real_time = _time.time
    fired = {"n": 0}

    def overtaken():
        if fired["n"] == 0:
            fired["n"] = 1
            fs.acquire_lock(fs.LOCK, poll_id="winner-1111")
        return real_time()

    monkeypatch.setattr(fs.time, "time", overtaken)
    try:
        with pytest.raises(fs.LockHeld) as refused:
            fs.acquire_lock(fs.LOCK, poll_id="loser-2222")
    finally:
        monkeypatch.setattr(fs.time, "time", real_time)

    assert fired["n"] == 1, "the interleaving never happened, so nothing was tested"
    body = fs.LOCK.read_text(encoding="utf-8")
    assert "winner-1111" in body, f"the winner's lock was destroyed: {body!r}"
    assert "loser-2222" not in body, f"a second run took the same lock: {body!r}"

    # WHICH refusal it was, because there is a way to pass this test for the
    # wrong reason: a run that happens to re-read the mtime after being overtaken
    # sees a fresh lock and stands down as though it had never judged it dead,
    # which leaves the dangerous path untested. The refusal has to be the one that
    # comes from having judged the lock dead and then checked again before acting.
    assert "re-taken while it was being examined" in str(refused.value), (
        f"the takeover path was never reached, so nothing was tested: {refused.value}"
    )

    # And the loser's own cleanup must not delete the lock it does not hold.
    fs.release_lock(fs.LOCK, poll_id="loser-2222")
    assert fs.LOCK.exists(), "the loser released a lock held by another run"
    assert "winner-1111" in fs.LOCK.read_text(encoding="utf-8")


def test_a_broken_lock_is_not_released_by_the_run_it_was_taken_from(sach):
    """The sequence a step timeout actually produces.

    A run stalls past the dead threshold, the next run breaks the lock and takes
    it, and then the stalled run reaches its `finally`. An unconditional unlink
    there deletes the new holder's lock, so a third run walks straight into the
    archive the second one is writing.
    """
    fs.acquire_lock(fs.LOCK, poll_id="stalled-1111")
    dead = _time.time() - (fs.LOCK_DEAD_AFTER + 60)
    os.utime(fs.LOCK, (dead, dead))
    fs.acquire_lock(fs.LOCK, poll_id="taker-2222")

    fs.release_lock(fs.LOCK, poll_id="stalled-1111")
    assert fs.LOCK.exists(), "the broken-from run deleted the new holder's lock"
    assert "taker-2222" in fs.LOCK.read_text(encoding="utf-8")

    # The holder itself still can, and the lock does not outlive it.
    assert fs.release_lock(fs.LOCK, poll_id="taker-2222") is True
    assert not fs.LOCK.exists()


def test_heartbeat_does_not_keep_a_lock_alive_for_a_run_that_does_not_hold_it(sach):
    """A heartbeat is a statement about the holder, so only the holder may make it.

    Refreshing a foreign lock would keep a dead holder looking alive for as long
    as any contender kept retrying, and would make the contender's own death
    invisible, which inverts the one thing the heartbeat is for.
    """
    fs.LOCK.write_text("other-attempt-9999 2026-08-09T00:00:00Z\n", encoding="utf-8")
    dead = _time.time() - (fs.LOCK_DEAD_AFTER + 60)
    os.utime(fs.LOCK, (dead, dead))
    was = fs.LOCK.stat().st_mtime_ns

    fs.heartbeat(fs.LOCK, poll_id="not-the-holder")
    assert fs.LOCK.stat().st_mtime_ns == was, "a non-holder refreshed the lock"

    # The point of not refreshing it: the dead lock is still breakable.
    fs.acquire_lock(fs.LOCK, poll_id="breaker-3333")
    assert "breaker-3333" in fs.LOCK.read_text(encoding="utf-8")


def test_preflight_failure_records_durable_attempt(sach, monkeypatch):
    """Everything that could fail ran BEFORE the row that records the attempt.

    Cleanup, both reads, bootstrap and repair all sit in front of the network
    call, and every one of them can raise. With the `started` row written after
    them, a corrupt archive or a read error produced an attempt with no trace
    anywhere: indistinguishable, to every later reader, from a run that never
    happened. The property is that no failure inside a poll is silent.

    The corruption here is real rather than injected, because the mechanism is
    the point: `read_archive` raising is exactly what a truncated archive does.
    """
    fs.OUT.write_text(
        '{"identifier": 1, "_content_sha1": "a"}\n{"identifier": 2, "_content_s',
        encoding="utf-8",
    )
    stub_fetch(monkeypatch, [])
    with pytest.raises(fs.ArchiveCorrupt):
        fs.poll(poll_id="preflight-victim")

    rows = rows_of(fs.POLLS)
    assert [r["kind"] for r in rows] == ["started", "result"], (
        f"a preflight failure left no durable trace of the attempt: {rows!r}"
    )
    assert rows[0]["poll_id"] == "preflight-victim"
    assert rows[-1]["outcome"] == "failed"
    assert "ArchiveCorrupt" in (rows[-1]["error"] or "")


@pytest.mark.parametrize(
    "step",
    ["clear_stale_temp", "read_archive", "read_manifest", "bootstrap_manifest", "reconcile"],
)
def test_no_step_of_a_poll_can_fail_without_a_durable_trace(sach, monkeypatch, step):
    """Named one at a time, because "the preflight" is five separate risks.

    Fixing only the one failure that was demonstrated would leave the same hole
    behind the other four. Checking one shape of a many-shaped thing is the
    recurring defect in this write path, and naming all five steps is what keeps
    the fix from being another instance of it.
    """
    stub_fetch(monkeypatch, [alert()])

    def boom(*a, **k):
        raise RuntimeError(f"{step} failed")

    monkeypatch.setattr(fs, step, boom)
    with pytest.raises(RuntimeError):
        fs.poll(poll_id=f"victim-of-{step}")

    rows = rows_of(fs.POLLS)
    kept = [r["kind"] for r in rows]
    assert kept and kept[0] == "started", f"{step}: no attempt was recorded: {kept!r}"
    assert rows[0]["poll_id"] == f"victim-of-{step}"
    result = [r for r in rows if r["kind"] == "result"]
    assert len(result) == 1, f"{step}: the failure was not recorded: {kept!r}"
    assert result[0]["outcome"] == "failed"
    assert step in (result[0]["error"] or ""), result[0]["error"]


def test_the_running_attempt_is_never_reconciled_as_its_own_orphan(sach, monkeypatch):
    """The regression the reordering could have introduced, pinned before it could.

    With the `started` row now written before the repair pass, the running
    attempt is itself a `started` row with no terminal row, which is the exact
    shape `orphans()` selects. Left alone it would reconcile itself on every
    poll, and every archive row would be filed as recovered from a crash that
    never happened.
    """
    stub_fetch(monkeypatch, [alert()])
    fs.poll(poll_id="live-attempt")
    rows = rows_of(fs.POLLS)
    assert [r for r in rows if r["kind"] == "reconciled"] == [], (
        "the poll reconciled itself while it was still running"
    )
    assert [r["kind"] for r in rows] == ["started", "observed", "result"]
    assert fs.uncovered_hashes(fs.read_archive(fs.OUT), rows) == set()


def _dead_lock(when_ago: float | None = None) -> "os.stat_result":
    """A lock file whose heartbeat is old enough to be breakable."""
    fs.LOCK.write_text("dead-attempt-0000 2026-08-09T00:00:00Z\n", encoding="utf-8")
    dead = _time.time() - (when_ago or (fs.LOCK_DEAD_AFTER + 60))
    os.utime(fs.LOCK, (dead, dead))
    return fs.LOCK.stat()


def _claim_path(observed) -> "Path":
    return fs.LOCK.with_name(f"{fs.LOCK.name}.takeover.{observed.st_mtime_ns}.tmp")


def test_only_one_contender_may_claim_the_takeover_of_a_dead_lock(sach):
    """The other half of the primitive, checked where the contention happens.

    The interleaving test above forces one ordering. This asserts the property
    that makes every ordering safe: the claim on a dead lock is created `O_EXCL`
    under a name keyed on the mtime that was judged dead, so two runs that saw the
    same dead lock cannot both be the one that removes it. Whichever arrives
    second is told the lock is held, which is true: it is being taken over.
    """
    observed = _dead_lock()
    claim = _claim_path(observed)
    fd = os.open(claim, os.O_CREAT | os.O_EXCL | os.O_WRONLY)  # the first contender's
    os.close(fd)

    with pytest.raises(fs.LockHeld) as refused:
        fs.break_stale_lock(fs.LOCK, observed, 9999.0)

    assert "already taking over" in str(refused.value), str(refused.value)
    assert fs.LOCK.exists(), "a lock another run was taking over was removed anyway"
    assert claim.exists(), "the second contender deleted the first contender's claim"


def test_the_winning_contender_removes_the_dead_lock_and_leaves_no_claim(sach):
    """Uncontended, the takeover must actually happen and clean up after itself.

    Stated separately from the refusal, because a primitive that refused
    everything would pass every test above while stopping the capture dead.
    """
    observed = _dead_lock()
    fs.break_stale_lock(fs.LOCK, observed, 9999.0)
    assert not fs.LOCK.exists(), "the dead lock was not removed"
    assert list(fs.LOCK.parent.glob("*.tmp")) == [], "the claim file was left behind"


def test_a_takeover_claim_left_by_a_killed_contender_does_not_wedge_the_lock(sach):
    """Leftovers must be recoverable, or the fix trades one wedge for another.

    A run killed mid-takeover leaves its claim behind. Because the claim is keyed
    on the dead lock's mtime it can only ever block a takeover of that same dead
    state, and it is a temp file like any other, so the sweep a poll already runs
    while holding the lock clears it. What must not happen is a leftover that
    stops the capture for good, which is the shape of the defect being fixed here
    and would be no better for being a different file.
    """
    observed = _dead_lock()
    orphaned = _claim_path(observed)
    orphaned.write_text("", encoding="utf-8")

    with pytest.raises(fs.LockHeld):
        fs.acquire_lock(fs.LOCK, poll_id="blocked-1111")

    assert orphaned.name in fs.clear_stale_temp(fs.OUT, fs.POLLS)
    fs.acquire_lock(fs.LOCK, poll_id="unblocked-2222")
    assert "unblocked-2222" in fs.LOCK.read_text(encoding="utf-8")


# A real process, really terminated, at the one instant the defect was fatal.
# `finally` does not run, no handler participates, and the kill lands between the
# staged manifest write and the replace that would publish it. Deterministic
# because the harness chooses the instant rather than racing for it.
KILL_IN_MANIFEST_HARNESS = "\n".join([
    "import os, signal, sys",
    "sys.path.insert(0, {root!r})",
    "from pathlib import Path",
    "from pipeline import fetch_sachet as fs",
    "fs.OUT = Path({out!r}); fs.POLLS = Path({polls!r}); fs.LOCK = Path({lock!r})",
    "fs.fetch = lambda *a, **k: [{{'identifier': 7, 'disaster_type': 'Flood'}}]",
    "real_replace = os.replace",
    "seen = []",
    "def replace_or_die(src, dst):",
    "    if str(dst).endswith('polls.jsonl'):",
    "        seen.append(str(dst))",
    "        if len(seen) == 2:",  # the `observed` row: staged, never published
    "            os.kill(os.getpid(), signal.SIGTERM)",
    "    return real_replace(src, dst)",
    "os.replace = replace_or_die",
    "fs.poll(poll_id='killed-mid-manifest-write')",
])


def test_a_kill_between_staging_a_manifest_row_and_publishing_it_is_recoverable(tmp_path):
    """The defect, at the instant it was fatal, in a process that really dies.

    An append in place had the new bytes inside the file the reader reads before
    anything made them permanent, so a kill here left a truncated line and every
    later poll raised `ArchiveCorrupt` in its first few lines, before repair could
    run. The capture was one unlucky kill away from dead, permanently, in the one
    environment that kills by design.

    What must be true after this kill: the manifest parses, it says exactly what
    it said before the interrupted write, and the next poll recovers the attempt
    instead of stopping on it.
    """
    d = tmp_path / "killed-manifest"
    d.mkdir()
    script = tmp_path / "kill_manifest_harness.py"
    script.write_text(
        KILL_IN_MANIFEST_HARNESS.format(
            root=str(Path.cwd()),
            out=str(d / "alerts.jsonl"),
            polls=str(d / "polls.jsonl"),
            lock=str(d / ".lock"),
        ),
        encoding="utf-8",
    )
    subprocess.run([sys.executable, str(script)], capture_output=True, timeout=120)

    polls = d / "polls.jsonl"
    assert polls.exists(), "the attempt was never recorded at all"
    surviving = fs.read_manifest(polls)  # raises ArchiveCorrupt if the file is torn
    assert [r["kind"] for r in surviving] == ["started"], (
        f"the interrupted write reached the live manifest: {surviving!r}"
    )
    assert surviving[0]["poll_id"] == "killed-mid-manifest-write"

    # The staged bytes are still on disk under the temp name, which is exactly
    # where an interrupted write belongs, and the ordinary sweep clears them.
    assert (d / "polls.jsonl.tmp").exists(), "nothing was staged, so nothing was tested"

    # And the capture carries on: the next poll sweeps, repairs the orphan, and
    # leaves the coverage invariant true.
    import pytest as _pytest  # local: this test does not use the `sach` fixture

    mp = _pytest.MonkeyPatch()
    try:
        mp.setattr(fs, "OUT", d / "alerts.jsonl")
        mp.setattr(fs, "POLLS", polls)
        mp.setattr(fs, "LOCK", d / ".lock")
        mp.setattr(fs, "fetch", lambda *a, **k: [])
        fs.poll(poll_id="the-run-after")
    finally:
        mp.undo()

    assert not (d / "polls.jsonl.tmp").exists(), "the staged leftover was never swept"
    after = fs.read_manifest(polls)
    rec = [r for r in after if r["kind"] == "reconciled"]
    assert len(rec) == 1 and rec[0]["poll_id"] == "killed-mid-manifest-write"
    assert rec[0]["membership_known"] is False, (
        "the killed poll never recorded what it saw, so membership cannot be known"
    )
    assert fs.uncovered_hashes(fs.read_archive(d / "alerts.jsonl"), after) == set()


# --- the three held-back lock/manifest fixes ---------------------------------
def test_a_heartbeat_whose_lock_vanishes_mid_touch_is_not_a_capture_failure(sach, monkeypatch):
    """The ownership check and the touch are two operations, and this runs inside
    every fetch retry, so a lock broken in the gap must not become the error a poll
    reports."""
    fs.acquire_lock(fs.LOCK, poll_id="holder-1111")
    real_utime = os.utime

    def vanishing_utime(path, times=None):
        fs.LOCK.unlink()          # another run breaks it in the gap
        return real_utime(path, times)

    monkeypatch.setattr(fs.os, "utime", vanishing_utime)
    fs.heartbeat(fs.LOCK, poll_id="holder-1111")   # must not raise
    monkeypatch.setattr(fs.os, "utime", real_utime)
    assert not fs.LOCK.exists()


def test_releasing_on_behalf_of_another_attempt_leaves_our_own_claim_intact(sach):
    """The registry is the fallback for callers that pass no id, so it must survive a
    release attempt made on behalf of a different attempt."""
    fs.acquire_lock(fs.LOCK, poll_id="holder-1111")
    assert fs.release_lock(fs.LOCK, poll_id="someone-else-9999") is False
    assert fs.LOCK.exists(), "a release for another attempt deleted the lock"

    # The holder can still release it with no argument, through the registry.
    assert fs.release_lock(fs.LOCK) is True
    assert not fs.LOCK.exists()


def test_appending_to_a_crlf_manifest_does_not_rewrite_its_line_endings(sach):
    """The live manifest is CRLF, and the promise is that earlier rows are untouched.

    `test_rewriting_the_manifest_preserves_earlier_rows_byte_for_byte` cannot see
    this, because a fixture it writes itself is never CRLF: the property was checked
    only on the input shape that cannot break it.
    """
    fs.POLLS.parent.mkdir(parents=True, exist_ok=True)
    first = b'{"kind": "started", "poll_id": "a", "utc": "t"}\r\n'
    fs.POLLS.write_bytes(first)

    fs.append_manifest({"kind": "started", "poll_id": "b", "utc": "t"}, fs.POLLS)

    raw = fs.POLLS.read_bytes()
    assert raw.startswith(first), "an earlier row's line ending was rewritten"
    assert raw.count(b"\r\n") == 1, f"line endings were normalised: {raw!r}"
    assert [r["poll_id"] for r in fs.read_manifest(fs.POLLS)] == ["a", "b"]
