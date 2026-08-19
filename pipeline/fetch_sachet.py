#!/usr/bin/env python
"""Archive India's national disaster-alert feed (NDMA Sachet), keyless.

Why this exists. Of the ground-truth sources this project has reached, each comes
through a satellite product and carries the revisit gap into its own dates: a
Copernicus GFM footprint or an NDEM acquisition timestamp records a day somebody
imaged the water, which is not the day the water arrived. Every alert captured so far is a CAP message
stamped by a state disaster authority, the CWC or an IMD office. That an alert here would therefore be datable
independently of an overpass is an inference from those responses, not a property
of the feed they establish; the archive is what would test it.

WHAT THE CAPTURED RESPONSES ESTABLISH, AND WHAT THEY DO NOT.

The three points below draw on the responses of 2026-08-07T08:24:50Z and
2026-08-09T18:38:10Z. Later polls have added more; `data/sachet/polls.jsonl` is
the record of which, and no count of them belongs here, because it changes.

* The 2026-08-09 response contained a row whose `alert_source` was "Punjab SDMA"
  and whose `sender_org_id` was "36", identifier 1786259146152036. Punjab does
  reach this feed. That row was a WATCH-level advisory, not a flood observation,
  so it says nothing about flooding on that date.
* The 2026-08-07 response contained zero rows naming Punjab. That is a dated
  observation about that response and is not a statement about any other day.
* All 68 identifiers in the 2026-08-07 response were absent from the 2026-08-09
  response. That is the whole of what the two polls show about turnover. No
  retention bound is asserted here: two polls 58 hours apart cannot measure the
  width of a window, and every date parameter tried on the endpoint
  (`fromDate`, `startDate`, `start_date`, `date`, `from`/`to`) returned the
  identical current set, so no backfill route is known. History exists only if
  it is kept from now on, which is the reason this runs on a schedule.

WHY THE WRITE PATH LOOKS THE WAY IT DOES.

Each poll writes ahead of the risk it is about to take, because `finally` does
not run when the process is killed:

  1. a `started` row is made durable in the manifest BEFORE anything that can
     fail, so a hung endpoint killed by a step timeout leaves a recorded
     attempt, and so does a corrupt archive or a failed read in the preflight;
  2. an `observed` row carrying EVERY returned hash is fsynced BEFORE the
     archive is touched, because residency is membership rather than insertion:
     a poll that re-serves an alert we already hold is evidence the alert was
     still being served, and merging alone would not record that;
  3. BOTH files are written through a temp file and one atomic replace, so an
     interrupted write leaves the previous content exactly as it was. The
     manifest is named deliberately: it was appended in place while the archive
     was not, which made the record less durable than the thing it records, and
     one interrupted append then bricked every later poll;
  4. a terminal `result` row records the outcome, and any `started` row that
     ends up with neither a `result` nor a `reconciled` row is repaired on the
     next run rather than left as a silent gap.

What it deliberately does not do. It does not filter, label, or interpret. Every
alert from every state is stored verbatim, because a capture that is claim-free
cannot be wrong, and because a label definition settled later must not be
constrained by what a filter written today happened to keep. :func:`punjab_view`
is a read-time lens over the archive, never applied on the way in.

A failed fetch is an error, not an empty capture. Recording a transient HTTP
failure as "no alerts" would fabricate absence, which is precisely the class of
mistake this project exists to stop repeating.

Source: https://sachet.ndma.gov.in (NDMA, Government of India). No login, no API
key; a browser User-Agent is required. See docs/notes/sachet.md.

    python pipeline/fetch_sachet.py            # append one poll to the archive
    python pipeline/fetch_sachet.py --summary  # what the archive holds so far
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

ENDPOINT = "https://sachet.ndma.gov.in/cap_public_website/FetchAllAlertDetails"
UA = "Mozilla/5.0 (compatible; sailaab/1.0; +https://github.com/bakathefish/Flood)"
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "sachet" / "alerts.jsonl"
POLLS = ROOT / "data" / "sachet" / "polls.jsonl"
LOCK = ROOT / "data" / "sachet" / ".lock"
DISTRICTS = ROOT / "data" / "punjab_districts.geojson"

RETRIES = 4
BACKOFF = 5.0

# Three times the workflow's step timeout. A lock is broken only when its
# heartbeat is older than this, never because it was CREATED long ago: a slow
# but live run refreshes its heartbeat and a killed one cannot.
LOCK_DEAD_AFTER = 30 * 60

# Bounded retry on taking the lock, for the one case worth retrying: a holder
# that releases between our failed create and our look at what we collided with.
LOCK_ACQUIRE_TRIES = 3

# Which attempt this process took which lock for, keyed by path. Only a fallback
# for callers that do not pass their `poll_id`; the lock file itself is the
# authority, because a stalled run's memory of holding a lock outlives the lock.
_HELD: dict[str, str] = {}

# Bounded retry on the atomic replace. Windows fails the replace with WinError 5
# while another handle has the destination open for reading, which is transient;
# a permanent failure must still raise rather than be swallowed.
REPLACE_RETRIES = 5
REPLACE_PAUSE = 0.2

MANIFEST_KINDS = (
    "started",
    "observed",
    "result",
    "reconciled",
    "bootstrap",
    "unattributed",
)

# Our own bookkeeping, stripped before hashing so a re-poll of an unchanged
# alert does not look like a new one, and so stamping provenance onto a row
# never changes what alert it is.
META = ("_first_seen_utc", "_content_sha1", "_poll_id")


class ArchiveCorrupt(Exception):
    """A line in the archive is not readable JSON.

    Raised rather than skipped. Skipping would drop evidence silently and let
    the next poll re-add the same alert as new, which is the mechanism behind
    this project's 16,460-row duplication incident.
    """


class LockHeld(Exception):
    """Another run holds the capture lock and is still alive."""


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch(
    url: str = ENDPOINT, retries: int = RETRIES, backoff: float = BACKOFF
) -> list:
    """The current alert window, or raise.

    Retries transient failures. Never returns [] to mean "the request failed":
    an empty list here means the feed genuinely carried no alerts.
    """
    last = None
    for attempt in range(retries):
        # The lock's "never steal from a live holder" guarantee is exactly this
        # call. Without it the guarantee rested on a function only the tests
        # invoked, and a run retrying with backoff could sit past the dead
        # threshold without ever saying it was alive.
        heartbeat()
        try:
            req = urllib.request.Request(
                url,
                data=b"{}",
                method="POST",
                headers={"Content-Type": "application/json", "User-Agent": UA},
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except (
            urllib.error.URLError,
            TimeoutError,
            json.JSONDecodeError,
            OSError,
        ) as exc:
            last = exc
            if attempt < retries - 1:
                time.sleep(backoff * (attempt + 1))
            continue
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            for key in ("alerts", "data", "result"):
                if isinstance(payload.get(key), list):
                    return payload[key]
        raise ValueError(f"unrecognised payload shape: {type(payload).__name__}")
    raise RuntimeError(f"Sachet unreachable after {retries} attempts: {last!r}")


def content_sha1(alert: dict) -> str:
    """Stable hash of an alert's own fields, ignoring our bookkeeping.

    CAP alerts can be reissued under the same identifier with changed text, so
    the identifier alone is not an identity. Hashing the content keeps updates
    as new rows while dropping true re-polls of the same alert.
    """
    body = {k: v for k, v in alert.items() if k not in META}
    packed = json.dumps(body, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha1(packed.encode("utf-8")).hexdigest()


def _line(row: dict) -> str:
    return json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"


def _display(path: Path) -> str:
    """A readable path for the runner line, whether or not it sits under the repo.

    `Path.relative_to(ROOT)` raises when it does not, which crashed `main()` on
    any redirected archive. Nothing caught it because no test called `main()`
    twice over a temporary archive, which is the original B7 gap.
    """
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def read_archive(path: Path | None = None) -> list:
    """Every alert kept so far, oldest first. Missing file is an empty archive.

    `path` resolves at call time. It used to default to the module-level `OUT`
    in the signature, which bound the real archive at import and meant a test
    redirecting `OUT` still read live evidence.
    """
    path = OUT if path is None else Path(path)
    if not path.exists():
        return []
    rows = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ArchiveCorrupt(f"{path} line {n} is not valid JSON: {exc}") from exc
    return rows


def read_manifest(path: Path | None = None) -> list:
    """Every poll record, oldest first."""
    path = POLLS if path is None else Path(path)
    if not path.exists():
        return []
    rows = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ArchiveCorrupt(f"{path} line {n} is not valid JSON: {exc}") from exc
    return rows


def _atomic_write_text(path: Path, text: str) -> None:
    """Make `text` the whole of `path`, through a temp file and one replace.

    BOTH files this module keeps are written this way, and that is the point.
    The archive was written atomically from the start while the manifest was
    appended in place, which made the record less durable than the thing it was
    a record of: an interruption partway through an append left a truncated line
    in the file :func:`read_manifest` reads strictly, so every later poll raised
    :class:`ArchiveCorrupt` before it could repair anything. One unlucky kill and
    the capture was dead for good, in CI, where step timeouts kill by design. A
    survival record that cannot survive the kill it exists to record is worse
    than none, because the next run reads it and stops.

    `os.replace` rather than `os.rename`, because `os.rename` fails on Windows
    when the destination exists. The retry loop is for WinError 5, which Windows
    raises while another handle has the destination open for reading; a failure
    that survives the loop is re-raised, so a permanent problem never passes as
    a successful write.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(str(path) + ".tmp")
    try:
        with tmp.open("w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        for attempt in range(REPLACE_RETRIES):
            try:
                os.replace(tmp, path)
                break
            except PermissionError:
                if attempt == REPLACE_RETRIES - 1:
                    raise
                time.sleep(REPLACE_PAUSE * (attempt + 1))
    finally:
        if tmp.exists():
            tmp.unlink()
    # Durability of the directory entry itself. Not possible on Windows, where
    # opening a directory raises PermissionError; needed on the Linux runner.
    if os.name != "nt":
        fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def append_manifest(row: dict, path: Path | None = None) -> None:
    """Add one manifest row, durably, without ever writing into the live file.

    Existing rows are carried over VERBATIM, byte for byte, rather than
    re-serialised. The manifest is a provenance record: re-encoding an old row
    would change bytes a later reader may already have quoted, and would quietly
    normalise away a line somebody repaired by hand.

    That promise was weaker here until the read stopped going through text mode.
    Universal-newline translation rewrote the line endings of every earlier row,
    and every row of the live manifest is CRLF because the in-place append this
    replaced ran on Windows, so the one file whose whole point is that it is not
    reformatted was reformatted on its first atomic rewrite. The wording is
    restored to "verbatim" in the same change that makes it true, and
    `test_appending_to_a_crlf_manifest_does_not_rewrite_its_line_endings` is the
    fixture that can falsify it.
    """
    path = POLLS if path is None else Path(path)
    # Read as BYTES and decode, because universal-newline translation would rewrite
    # the line endings of rows written earlier. The live manifest is CRLF throughout:
    # the in-place append this replaced ran on Windows, where text mode turns every
    # newline into a carriage-return pair. Reading it with `read_text` strips the CR,
    # so the first atomic rewrite would silently reformat every historical row in the
    # one file whose promise is that it does not.
    existing = path.read_bytes().decode("utf-8") if path.exists() else ""
    if existing and not existing.endswith("\n"):
        # A kill landed after a row's bytes and before its newline. That file
        # still reads correctly, so nothing complains, and appending to it would
        # join two JSON objects on one line and make BOTH unreadable. Closing the
        # line is the only repair here that drops no evidence.
        existing += "\n"
    _atomic_write_text(path, existing + _line(row))


def atomic_replace_archive(rows: list, path: Path | None = None) -> None:
    """Write the whole archive through a temp file and one atomic replace."""
    path = OUT if path is None else Path(path)
    _atomic_write_text(path, "".join(_line(row) for row in rows))


def clear_stale_temp(*paths: Path | None) -> list:
    """Remove temp files left by a killed run. Callers must hold the lock.

    Every path whose directory could hold one of our temp files must be named:
    the manifest stages its writes the same way the archive does, so sweeping
    only the archive's directory would leave a manifest temp behind whenever the
    two are kept apart.

    Ordering matters more than the cleanup does: a run that has NOT acquired the
    lock must touch nothing, or it would delete the staged write of the live
    holder it just lost the race to.
    """
    targets = [Path(p) for p in paths if p is not None] or [OUT]
    removed = []
    for folder in dict.fromkeys(t.parent for t in targets):
        for leftover in folder.glob("*.tmp"):
            leftover.unlink()
            removed.append(leftover.name)
    return removed


def lock_holder(path: Path | None = None) -> str | None:
    """The attempt id named by the lock file, or None if there is no lock.

    Ownership is read from the disk rather than remembered, because the run that
    must not release a lock is exactly the run whose lock was already broken and
    re-taken while it was stalled: it still believes it holds one.
    """
    path = LOCK if path is None else Path(path)
    try:
        fields = path.read_text(encoding="utf-8").split()
    except FileNotFoundError:
        return None
    return fields[0] if fields else None


def _holds(path: Path, poll_id: str | None) -> bool:
    """Whether the lock on disk names this attempt. `_HELD` is the fallback."""
    want = poll_id or _HELD.get(os.fspath(path))
    return want is not None and lock_holder(path) == want


def heartbeat(path: Path | None = None, poll_id: str | None = None) -> None:
    """Refresh the lock's mtime to say the holder is still alive.

    Ownership-checked. A heartbeat is a statement about the holder, so only the
    holder may make it: refreshing a foreign lock would keep a dead holder
    looking alive for as long as any contender kept retrying, and would make the
    contender's own death invisible, which inverts the one thing it is for.
    """
    path = LOCK if path is None else Path(path)
    mine = poll_id or _HELD.get(os.fspath(path))
    if mine is None or lock_holder(path) != mine:
        return
    try:
        os.utime(path, None)
    except FileNotFoundError:
        # The lock was removed between the ownership check and the touch. Nothing
        # to refresh, and it must not become the error a poll reports: this runs
        # inside every fetch retry, so an unguarded raise here would surface as a
        # capture failure whose message says nothing about the lock.
        return
    # The check and the touch are still two operations, so read the owner back
    # and find out which file we actually refreshed. A contender that broke this
    # lock and re-took it inside that window now owns the mtime we just moved,
    # and the honest response is to stop claiming the lock rather than to keep
    # heartbeating someone else's.
    #
    # This narrows the race and makes losing it detectable; it does not remove
    # it, because the touch cannot be made conditional on the owner without a
    # file handle os.utime will accept on every platform this runs on. Losing it
    # requires our lock to be older than LOCK_DEAD_AFTER already, which means a
    # contender was entitled to break it and the refresh we handed them was to a
    # lock whose holder is genuinely alive.
    if lock_holder(path) != mine:
        _HELD.pop(os.fspath(path), None)


def break_stale_lock(path: Path, observed: os.stat_result, age: float) -> None:
    """Remove one dead lock, and let exactly one contender be the one who does.

    Create-then-verify, in two halves that answer the two ways the old
    `unlink`-then-create went wrong.

    The claim file is created `O_EXCL` under a name keyed on the mtime the caller
    judged dead, so two runs that saw the same dead lock contend for the same
    name and the filesystem settles which of them proceeds. That is the half that
    stops both contenders from creating the lock and both believing they hold it.

    The re-stat is the other half. A contender can be overtaken between judging
    the lock and acting on that judgement, and the lock it is about to delete may
    by then be the live lock of the run that overtook it. Confirming the mtime is
    still the one that was judged dead is what turns two independent operations
    into one decision.
    """
    claim = path.with_name(f"{path.name}.takeover.{observed.st_mtime_ns}.tmp")
    try:
        fd = os.open(claim, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise LockHeld(
            f"{path}: another run is already taking over the dead lock"
        ) from None
    os.close(fd)
    try:
        try:
            current = path.stat()
        except FileNotFoundError:
            return  # the holder released it; the O_EXCL create decides from here
        if current.st_mtime_ns != observed.st_mtime_ns:
            raise LockHeld(
                f"{path} was re-taken while it was being examined, standing down"
            ) from None
        print(
            f"sachet: breaking lock with no heartbeat for {age:.0f}s", file=sys.stderr
        )
        path.unlink()
    finally:
        if claim.exists():
            claim.unlink()


def acquire_lock(
    path: Path | None = None,
    dead_after: float = LOCK_DEAD_AFTER,
    poll_id: str | None = None,
) -> Path:
    """Take the capture lock, or raise :class:`LockHeld`.

    Liveness is the heartbeat and nothing else. It is deliberately not
    PID-based: `fetch_footprint_cache.py`'s `_alive()` returns False when
    checking a process it cannot signal, so a live foreign-owned holder read as
    dead, and that is the incident class this design exists to avoid.

    The file therefore names the ATTEMPT, not the process: `poll_id` and a
    timestamp. Writing a PID would leave the next reader an invitation to use
    the mechanism this whole design refuses, and it left the lock with nothing
    tying it to the manifest row for the attempt holding it. That id is also what
    makes ownership checkable, which is what :func:`release_lock` needs.

    The loop exists for one case: a holder that releases the lock between our
    failed create and our look at it. Retrying is right there, where standing
    down would skip a poll for no reason.
    """
    path = LOCK if path is None else Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Unique even when no `poll_id` is given, because ownership is only a check
    # if the name in the file belongs to one attempt and no other.
    attempt = poll_id or f"unattributed-{uuid.uuid4().hex[:12]}"

    for _ in range(LOCK_ACQUIRE_TRIES):
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                observed = path.stat()
            except FileNotFoundError:
                continue
            age = time.time() - observed.st_mtime
            if age <= dead_after:
                raise LockHeld(
                    f"{path} held, last heartbeat {age:.0f}s ago "
                    f"(dead after {dead_after:.0f}s)"
                ) from None
            break_stale_lock(path, observed, age)
            continue
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(f"{attempt} {utcnow()}\n")
        _HELD[os.fspath(path)] = attempt
        return path
    raise LockHeld(f"{path} could not be taken in {LOCK_ACQUIRE_TRIES} attempts")


def release_lock(path: Path | None = None, poll_id: str | None = None) -> bool:
    """Delete the lock, but only when it is this attempt that is named in it.

    The unconditional unlink was the second half of the takeover defect. A run
    that stalls past the dead threshold has its lock broken and re-taken by the
    next run, and then reaches its own `finally` and deletes the NEW holder's
    lock, so a third run walks straight into the archive the second is writing.

    Returns whether the lock was released, so a caller can tell "cleaned up" from
    "that lock was not mine", rather than having both look like success.
    """
    path = LOCK if path is None else Path(path)
    if not _holds(path, poll_id):
        # A claim of OURS on this path is void when the file no longer names it,
        # and only then. Dropping it unconditionally would let a release attempt
        # made on behalf of some other attempt id discard this process's own live
        # registration, so the holder's later no-argument release would find
        # nothing to check itself against.
        if lock_holder(path) != _HELD.get(os.fspath(path)):
            _HELD.pop(os.fspath(path), None)
        return False
    # Move it aside first, then look at what we moved.
    #
    # `unlink` after a separate ownership check deletes whatever is at the path
    # NOW, which is not necessarily the file the check looked at: a contender
    # that broke this lock and took its own in the gap had that lock deleted by
    # us, and a third run then walked into the archive the second was writing,
    # which is the exact failure the ownership check was added to prevent.
    # `os.replace` is atomic on both platforms this runs on, so exactly one
    # caller can win the move, and the winner reads the contents at leisure
    # knowing nobody else holds them.
    mine = poll_id or _HELD.get(os.fspath(path))
    staged = path.with_name(f"{path.name}.releasing-{os.getpid()}")
    try:
        os.replace(path, staged)
    except (FileNotFoundError, PermissionError):
        # Gone, or another process is mid-move. Either way it is not ours to
        # delete any more.
        _HELD.pop(os.fspath(path), None)
        return False
    try:
        fields = staged.read_text(encoding="utf-8").split()
        holder = fields[0] if fields else None
    except OSError:
        holder = None
    if holder != mine:
        # We moved a lock that had already changed hands, so put it back — but
        # only into a path nobody has taken in the meantime.
        #
        # An unconditional replace here was its own version of the bug this
        # whole function is about. Vacating `path` makes it look free, so a
        # third run can legitimately acquire it in that gap, and restoring over
        # the top destroys a live claim that has done nothing wrong. The
        # exclusive create is the same primitive acquire_lock uses, so whoever
        # holds the path keeps it and we surrender our copy instead.
        #
        # The residual is that the original holder's lock was invisible for the
        # width of that gap. That is recoverable by design: ownership is read
        # from disk on every check, so the holder discovers it no longer holds
        # rather than acting on a stale belief.
        #
        # A narrower cousin: the exclusive create and the content write below
        # are two steps, so an OSError between them (ENOSPC, say) leaves an
        # empty file at `path` instead of old-content-or-nothing. It cannot
        # clobber a live claim — the create only succeeded because the path
        # was vacant — and the same read-from-disk discipline means readers
        # see an unparseable lock, not a wrong one.
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            pass  # somebody else holds it now; leave them alone
        except OSError:
            pass
        else:
            try:
                with os.fdopen(fd, "wb") as fh:
                    fh.write(staged.read_bytes())
            except OSError:
                pass
        staged.unlink(missing_ok=True)
        _HELD.pop(os.fspath(path), None)
        return False
    staged.unlink(missing_ok=True)
    _HELD.pop(os.fspath(path), None)
    return True


def merge(
    existing: list, incoming: list, seen_utc: str, poll_id: str | None = None
) -> list:
    """New alerts only, stamped with when we first saw them and which poll saw them.

    Identity is (identifier, content hash), so a reissue is kept and a re-poll
    is not. Order within a poll is preserved. `_poll_id` is provenance only: it
    is stripped before hashing, so stamping it cannot change identity.
    """
    known = {(r.get("identifier"), r.get("_content_sha1")) for r in existing}
    fresh = []
    for alert in incoming:
        digest = content_sha1(alert)
        key = (alert.get("identifier"), digest)
        if key in known:
            continue
        known.add(key)
        row = {**alert, "_first_seen_utc": seen_utc, "_content_sha1": digest}
        if poll_id is not None:
            row["_poll_id"] = poll_id
        fresh.append(row)
    return fresh


def covered_hashes(manifest: list) -> set:
    """Hashes the manifest accounts for being in the archive.

    `observed` is deliberately excluded. A poll can be killed between recording
    what it saw and writing it, so an observed hash need not be in the archive;
    including it would make the invariant fail on a correctly recorded crash.
    `unattributed` IS included, because it is the honest record of a hash whose
    poll cannot be identified, and an invariant that rejected its own recovery
    path would force a guess.
    """
    covered: set = set()
    for row in manifest:
        if row.get("kind") == "result":
            covered.update(row.get("archived_sha1s") or [])
        elif row.get("kind") in ("bootstrap", "reconciled", "unattributed"):
            covered.update(row.get("sha1s") or [])
    return covered


def uncovered_hashes(archive: list, manifest: list) -> set:
    """Archive hashes no manifest row accounts for. Empty is the invariant."""
    return {
        r.get("_content_sha1") for r in archive if r.get("_content_sha1")
    } - covered_hashes(manifest)


def bootstrap_manifest(archive: list, manifest: list, path: Path | None = None) -> list:
    """Account for archive rows that predate the manifest. Runs at most once.

    Keyed on the ABSENCE of `_poll_id`, not on "every uncovered hash". That
    distinction is the whole point: any row a poll wrote carries a `_poll_id`
    even if the poll then crashed, so bootstrap and orphan recovery are disjoint
    by construction rather than by getting their order right.

    ONE ROW PER DISTINCT `_first_seen_utc`, not one combined row. Those rows
    predate the manifest, so `_first_seen_utc` is the only provenance they have,
    and collapsing them into a single row would throw away which day each legacy
    alert arrived. A legacy row with no `_first_seen_utc` at all cannot be grouped
    by one and gets its own row keyed `unknown`, because dropping it would leave
    the coverage invariant false on day one, which is the defect bootstrap exists
    to fix.
    """
    if any(r.get("kind") == "bootstrap" for r in manifest):
        return []

    by_day: dict[str, list[str]] = {}
    for row in archive:
        if row.get("_poll_id"):
            continue
        digest = row.get("_content_sha1")
        if not digest:
            continue
        by_day.setdefault(row.get("_first_seen_utc") or "unknown", []).append(digest)

    written = []
    for day in sorted(by_day):
        row = {
            "kind": "bootstrap",
            "poll_id": None,
            "utc": day,
            "returned": None,
            "sha1s": sorted(by_day[day]),
            "note": "predates the manifest; reconstructed from _first_seen_utc",
        }
        append_manifest(row, path)
        written.append(row)
    return written


def orphans(manifest: list, current: str | None = None) -> list:
    """`started` polls with NEITHER a `result` nor a `reconciled` row.

    Selecting on the absence of both is what makes repair terminate. Selecting
    on "no result" alone re-reconciled an already-reconciled orphan on every
    subsequent run, forever, because reconciling never produces a result row.

    `current` is the attempt doing the asking, and it is never its own orphan. It
    has exactly the shape of one, because its `started` row is on disk and its
    terminal row cannot be yet, so without the exclusion a poll would reconcile
    itself on every run and file its own rows as recovered from a crash that
    never happened.
    """
    terminal = {
        r.get("poll_id") for r in manifest if r.get("kind") in ("result", "reconciled")
    }
    seen, out = set(), []
    for row in manifest:
        pid = row.get("poll_id")
        if row.get("kind") != "started" or pid in terminal or pid in seen:
            continue
        if current is not None and pid == current:
            continue
        seen.add(pid)
        out.append(pid)
    return out


def reconcile(
    archive: list,
    manifest: list,
    path: Path | None = None,
    current: str | None = None,
) -> list:
    """Repair recorded gaps: one row per orphaned poll, and never a guess.

    Two mechanisms, in this order, because they answer different questions.

    A hash carrying a `_poll_id` stamp needs no rule: the row says which attempt
    wrote it, so it goes to that attempt's `reconciled` row. What is left over is
    the residue that no stamp explains, and the residue is what `attribution`
    describes: `sole_orphan` when exactly one attempt could have produced it, and
    `ambiguous` when more than one could, in which case the residue goes to a
    single `unattributed` row rather than being assigned to whichever orphan is
    convenient.

    ONE DELIBERATE DEVIATION FROM THE LITERAL CONTRACT, recorded because it is a
    deviation. The contract says that with more than one orphan every orphan gets
    `sha1s: []`. Followed literally, a hash carrying an unambiguous `_poll_id`
    would be moved into a row whose declared meaning is "unclaimed hashes that
    multiple orphans could equally explain", which would be a false statement in
    the record: that hash IS explained. So stamped hashes stay with the poll that
    stamped them and only unstamped residue is called unattributable. See
    `test_a_stamped_hash_is_never_filed_as_unattributable`.
    """
    pending = orphans(manifest, current)
    if not pending:
        return []

    by_poll: dict = {}
    for row in archive:
        pid, digest = row.get("_poll_id"), row.get("_content_sha1")
        if pid and digest:
            by_poll.setdefault(pid, []).append(digest)

    claimed = {h for pid in pending for h in by_poll.get(pid, [])}
    residue = sorted(uncovered_hashes(archive, manifest) - claimed)
    sole = len(pending) == 1

    observed_for = {r.get("poll_id") for r in manifest if r.get("kind") == "observed"}
    written = []
    for pid in pending:
        mine = sorted(by_poll.get(pid, []))
        row = {
            "kind": "reconciled",
            "poll_id": pid,
            "utc": utcnow(),
            # The sole orphan is the only attempt the residue could belong to, so
            # it carries it. With several, no orphan may claim it.
            "sha1s": sorted(set(mine) | set(residue)) if sole else mine,
            "attribution": "sole_orphan" if sole else "ambiguous",
            # False means only "we cannot know whether the fetch returned", not
            # that it did not: the poll died before it could record what it saw.
            "membership_known": pid in observed_for,
        }
        append_manifest(row, path)
        written.append(row)

    if residue and not sole:
        row = {
            "kind": "unattributed",
            "poll_id": None,
            "utc": utcnow(),
            "sha1s": residue,
        }
        append_manifest(row, path)
        written.append(row)
    return written


def poll(
    archive_path: Path | None = None,
    manifest_path: Path | None = None,
    poll_id: str | None = None,
) -> dict:
    """One poll, write-ahead. Callers hold the lock; :func:`main` takes it.

    `poll_id` is passed in by :func:`main` so the lock file and the `started` row
    name the same attempt. Called directly without one, it mints its own.

    The `started` row comes before the PREFLIGHT, not merely before the network
    call. Cleanup, both reads, bootstrap and repair can every one of them raise,
    and with the row written after them a corrupt archive or a failed read left an
    attempt with no trace at all: indistinguishable, to every later reader, from a
    run that never happened. Nothing inside a poll may fail silently, so the
    recording comes first and everything that can fail sits inside the `try`.

    Returns a summary of the attempt, `{outcome, returned, new}`, for the runner
    line. The terminal row itself goes to the manifest rather than to the caller.
    Raises whatever the fetch or the write raised, after that row is durable.
    """
    archive_path = OUT if archive_path is None else Path(archive_path)
    manifest_path = POLLS if manifest_path is None else Path(manifest_path)
    archive_path.parent.mkdir(parents=True, exist_ok=True)

    poll_id = poll_id or str(uuid.uuid4())
    started = time.monotonic()
    append_manifest(
        {"kind": "started", "poll_id": poll_id, "utc": utcnow()}, manifest_path
    )

    # `archived` is assigned only AFTER the replace returns, and it is what the
    # terminal row reports. Reporting `fresh` instead let a replace that RAISED
    # still produce `new > 0` and a list of `archived_sha1s`, which is
    # archive-before-terminal inverted: the manifest would claim hashes the
    # archive never received, and the coverage invariant would then read them as
    # covered forever, so reconciliation could never repair the gap.
    outcome, error, incoming, archived = "failed", None, [], []
    try:
        clear_stale_temp(archive_path, manifest_path)

        archive = read_archive(archive_path)
        manifest = read_manifest(manifest_path)
        bootstrap_manifest(archive, manifest, manifest_path)
        # `current=poll_id`: this attempt's own `started` row is now on disk
        # before the repair pass, and an attempt still running is not an orphan.
        reconcile(archive, read_manifest(manifest_path), manifest_path, current=poll_id)

        incoming = fetch()
        append_manifest(
            {
                "kind": "observed",
                "poll_id": poll_id,
                "utc": utcnow(),
                "returned": len(incoming),
                "sha1s": [content_sha1(a) for a in incoming],
            },
            manifest_path,
        )
        archive = read_archive(archive_path)
        fresh = merge(archive, incoming, utcnow(), poll_id)
        if fresh:
            atomic_replace_archive(archive + fresh, archive_path)
        archived = [r["_content_sha1"] for r in fresh]
        outcome = "ok" if incoming else "empty"
        return {"outcome": outcome, "returned": len(incoming), "new": len(archived)}
    except BaseException as exc:  # noqa: BLE001 - recorded, then re-raised
        error = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        append_manifest(
            {
                "kind": "result",
                "poll_id": poll_id,
                "utc": utcnow(),
                "outcome": outcome,
                "new": len(archived),
                "archived_sha1s": archived,
                "error": error,
                "elapsed_s": round(time.monotonic() - started, 3),
            },
            manifest_path,
        )


def punjab_names(path: Path = DISTRICTS) -> list:
    """Punjab plus its twenty district names, for the read-time lens."""
    names = ["Punjab"]
    if path.exists():
        gj = json.loads(path.read_text(encoding="utf-8"))
        names += [f["properties"]["district"] for f in gj["features"]]
    return names


def punjab_view(rows: list, names: list | None = None) -> list:
    """Alerts naming Punjab or one of its districts. A lens, not a filter.

    Applied when reading the archive, never when writing it, so that changing
    what counts as a Punjab alert never costs evidence already captured.
    """
    needles = [n.lower() for n in (names if names is not None else punjab_names())]
    out = []
    for row in rows:
        hay = " ".join(
            str(row.get(f) or "")
            for f in (
                "area_description",
                "alert_source",
                "warning_message",
                "area_covered",
            )
        ).lower()
        if any(n in hay for n in needles):
            out.append(row)
    return out


def is_flood(alert: dict) -> bool:
    """Whether an alert's declared disaster type is a flood type."""
    return "flood" in str(alert.get("disaster_type") or "").lower()


def summarise(rows: list) -> dict:
    """What the archive holds, for the runner line and the tests."""
    pb = punjab_view(rows)
    return {
        "alerts": len(rows),
        "flood": sum(1 for r in rows if is_flood(r)),
        "punjab": len(pb),
        "punjab_flood": sum(1 for r in pb if is_flood(r)),
        "senders": len({r.get("alert_source") for r in rows if r.get("alert_source")}),
        "first_seen": min((r.get("_first_seen_utc", "") for r in rows), default=""),
        "last_seen": max((r.get("_first_seen_utc", "") for r in rows), default=""),
    }


def main(argv: list | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--summary", action="store_true", help="report the archive, fetch nothing"
    )
    args = ap.parse_args(argv)

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):  # pragma: no cover - non-standard stdout
        pass

    if args.summary:
        s = summarise(read_archive())
        print(
            f"sachet archive: {s['alerts']:,} alerts ({s['flood']:,} flood) "
            f"from {s['senders']} senders, {s['first_seen'][:10] or '-'} to "
            f"{s['last_seen'][:10] or '-'}"
        )
        print(f"  Punjab: {s['punjab']} alerts, {s['punjab_flood']} of them flood")
        return 0

    # One id for the attempt, shared by the lock file and the manifest rows, so a
    # lock found on disk can be traced to the poll that holds it.
    attempt = str(uuid.uuid4())

    try:
        acquire_lock(poll_id=attempt)
    except LockHeld as exc:
        # Not an error worth failing the workflow over, and deliberately before
        # any write: a run that loses the race must touch nothing at all.
        print(f"sachet: another run holds the lock, skipping ({exc})", file=sys.stderr)
        return 3

    try:
        res = poll(poll_id=attempt)
    except Exception as exc:  # noqa: BLE001 - the manifest row is the record
        print(f"sachet: poll failed, recorded in the manifest: {exc}", file=sys.stderr)
        return 1
    finally:
        # By attempt id, so that a run whose lock was already broken and re-taken
        # while it stalled cannot delete the new holder's lock on its way out.
        release_lock(poll_id=attempt)

    pb = punjab_view(read_archive())
    print(
        f"sachet: polled {res['returned']} alerts, {res['new']} new "
        f"({res['outcome']}), {len(pb)} naming Punjab in the archive "
        f"-> {_display(OUT)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
