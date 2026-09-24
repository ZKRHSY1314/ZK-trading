"""M2b P-A - the bounded capture runner. Default mode opens nothing and writes nothing.

Two modes
---------
`--plan` (default)      prints the five URLs derived from the INSTALLED adapter constants
                        in job order, the pre-flight results F1-F8, the proxy/TLS block
                        and the intended output root. It makes no network connection,
                        opens no database and creates no file or directory, so its output
                        can be pasted into a review and into the boundary-1b
                        authorization request. (F4 does start the JS engine to prove the
                        pinned routine evaluates; that engine's asyncio self-pipe is a
                        LOCAL socket pair, which is why the guards in this project are
                        connection-level rather than a blanket socket block.)
`--i-authorize-live-calls <run_id>`
                        the ONLY path that opens a socket. Boundary 1b, and it still
                        refuses unless the pre-flight passes.

The three review requirements
-----------------------------
**S1 - a deadline that actually bounds the run.** A read timeout bounds the gap between
socket reads, not the call, and `requests` with `stream=False` consumes `r.content`
inside `session.get` (`requests/sessions.py:826-827`), so an outer check before each
request can never regain control from a response that keeps trickling. Three mechanisms
replace that unenforceable check:

  1. `stream=True` plus `read_body_streamed`, which checks the deadline and a byte
     budget after every chunk. Control returns to us between chunks, so a trickling
     response is cut off by us, not waited out.
  2. `supervise`, which runs a whole job in a worker thread and stops waiting at the
     deadline. This covers what chunking cannot: a call blocked before the first chunk,
     and a decoder that will not return.
  3. Finite JS limits in P-B (`timeout_sec`, `max_memory`, row and payload caps).

  Honest limit: Python cannot safely kill a thread, and this runner will not terminate
  processes - not its own, and certainly not unrelated applications or services. What is
  guaranteed is that the RUN stops: no further attempt is issued, the partial evidence is
  already on disk (the manifest is written at every attempt boundary), the session is
  closed and the worker is a daemon, so interpreter exit does not wait for it.

  Allowances, stated once and enforced by the same clock:

    run deadline            WALL_CLOCK_CAP_SEC   900 s   capture + decode + checks + replay
    in-flight read grace    SHUTDOWN_GRACE_SEC    45 s   an abandoned read may run on this long
    finalization            FINALIZE_BUDGET_SEC  120 s   seal, report, retention - each step
                                                         supervised; a step that outlives
                                                         it is abandoned and the run is
                                                         reported INCOMPLETE, never done
    seal wait               SEAL_TIMEOUT_SEC      30 s   part of finalization

  Total documented runtime: at most 900 + 45 + 120 s before the process reports and
  exits. Abandoned daemon threads never delay exit and can never write into the tree.

**R1 - evidence ownership.** Every mutation of the evidence tree - raw bodies, failed
bodies, request records, attempt records, the manifest - goes through one
`EvidenceStore`. Workers stage bytes OUTSIDE the tree and publish them in a single
critical section that also appends the record and rewrites the manifest. The seal takes
that same lock, so finalization never runs concurrently with a worker that can publish,
and a worker that wakes after the seal is refused and its staged bytes are discarded.

**R2 - bounded finalization.** Reporting and retention run step by step under their own
declared deadline, each step supervised. An overrun that returns and a step that blocks
are both reported as `incomplete_finalization` with the partial evidence location; a
negative remaining budget is never reported as success.

**R3 - attempts are evidence.** The actual wire attempt is the unit of evidence: each
attempt's start and end are persisted at the boundary, retries included, and the checks
reconcile every issued request against its attempt records.

**S2 - deterministic outcomes.** This module only RECORDS what happened per attempt
(status, payload state, whether a request was skipped). Classification lives in one table
in `smoke_checks.py`, so a transport failure can never turn into a capability finding.

**S3 - frozen reference inputs.** `read_reference_extract` copies the exact cache rows
and fields the checks consume into `reference/reference_extract.json` at capture time.
Every later check reads that file. `db_guard()` makes "replay does not open production" a
runtime guarantee rather than a promise.
"""

from __future__ import annotations

import argparse
import ast
import contextlib
import datetime as _dt
import errno
import hashlib
import json
import os
import re
import socket
import sqlite3
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

SMOKE_DIR = Path(__file__).resolve().parent
REPO_ROOT = SMOKE_DIR.parents[1]
sys.path.insert(0, str(SMOKE_DIR))
sys.path.insert(0, str(REPO_ROOT / "claude methods" / "_m2_pilot"))

import sina_klc_decoder as dec                        # noqa: E402
import smoke_outcomes as out                          # noqa: E402  (the shared table)
import transport as tp                                # noqa: E402  (unchanged M2a)

# ------------------------------------------------------------------------- constants
MANIFEST = REPO_ROOT / "claude methods" / "_m1_closure" / "pilot_symbols.csv"
CALENDAR = (REPO_ROOT / "backend" / ".venv" / "Lib" / "site-packages" / "akshare"
            / "file_fold" / "calendar.json")
TRADING_DB = REPO_ROOT / "trading_local.sqlite3"
MARKET_DB = REPO_ROOT / "market_history.sqlite3"
MARKET_WAL = REPO_ROOT / "market_history.sqlite3-wal"
MARKET_SHM = REPO_ROOT / "market_history.sqlite3-shm"
TMP_ROOT = REPO_ROOT / "tmp"
EVIDENCE_ROOT = SMOKE_DIR
HEARTBEAT = REPO_ROOT / "backend" / "logs" / "market_history_refresh_heartbeat.json"

AKSHARE_VERSION = "1.18.64"
MANIFEST_SHA256 = "97e251ae84fc927486127a96b4966ed8fc59fac0b744b7d6f186b2b1548886fe"
CALENDAR_SHA256 = "f1f1ce33c5cceb5c530c3271fc951405cb5624d2f30becec85dc7a85fd47e656"

RESEARCH_START, RESEARCH_END = "2023-09-04", "2026-09-04"
WARMUP_START, WARMUP_END = "2022-08-24", "2023-09-01"
WINDOW_START, WINDOW_END = WARMUP_START, RESEARCH_END
BJ_CODE_BOUNDARY = "2024-08-13"

CEILING = 15
MIN_INTERVAL = 1.5
CONNECT_TIMEOUT = 10.0
READ_TIMEOUT = 30.0
WALL_CLOCK_CAP_SEC = 15 * 60.0
#: One read timeout plus socket close. The run may overrun the cap by at most this.
SHUTDOWN_GRACE_SEC = 45.0
SUPERVISE_POLL_SEC = 0.25
CHUNK_BYTES = 64 * 1024
MAX_RESPONSE_BYTES = dec.MAX_BODY_BYTES
MAX_TOTAL_BYTES = 32 * 1024 * 1024
CONSECUTIVE_FAILED_JOBS_STOP = 2
MAX_REFERENCE_ROWS = 5000
#: Finalization runs AFTER the run deadline may already have expired - evidence must
#: still be written - so it gets its own explicitly declared, bounded allowance.
FINALIZE_BUDGET_SEC = 120.0
#: A separate offline replay is a different run and states its own budget.
REPLAY_BUDGET_SEC = 600.0
#: Bounded wait for the evidence lock when sealing the tree. Part of finalization. A
#: worker still holding the lock after this is reported, never waited on indefinitely.
SEAL_TIMEOUT_SEC = 30.0
#: Staged bytes live in a sibling of the output root, never inside the evidence tree.
PENDING_SUFFIX = ".pending"

SOURCE_KEY = "sina"

#: Section 2 job order. The two capability jobs run first so the consecutive-failure
#: stop can never skip them.
JOBS = (
    {"job": "sh600011", "manifest_symbol": "SH600011", "adapter_symbol": "sh600011",
     "instrument_class": "stock", "role": "ordinary_control"},
    {"job": "sh000300", "manifest_symbol": "SH000300", "adapter_symbol": "sh000300",
     "instrument_class": "benchmark", "role": "benchmark"},
    {"job": "bj920000", "manifest_symbol": "BJ920000", "adapter_symbol": "bj920000",
     "instrument_class": "stock", "role": "bj_code_history"},
)

#: Header names never copied verbatim into evidence, even though the expected request
#: environment is credential-free today. A future header must not leak by default.
SENSITIVE_HEADERS = frozenset({
    "authorization", "proxy-authorization", "cookie", "set-cookie", "x-api-key",
    "api-key", "x-auth-token", "authentication", "www-authenticate",
    "proxy-authenticate", "x-csrf-token",
})


class SmokeError(Exception):
    """A precondition of the smoke is not met. Raised before anything is written."""


class PreflightError(SmokeError):
    """A pre-flight check failed; no request may be issued."""


class DeadlineExceeded(tp.RunAborted):
    """The end-to-end budget is spent.

    Subclassing `RunAborted` is deliberate: when the injected live callable raises this,
    the unchanged `PacedTransport` records the attempt, latches `aborted_reason` and
    refuses every later call, so the stop is sticky without editing validated M2a code.
    """


class BodyTooLarge(SmokeError):
    """A response exceeded the byte budget while it was still arriving."""


class EvidenceSealed(SmokeError):
    """The evidence tree is finalized; a late publication was refused, not applied."""


class EvidenceUnsealable(SmokeError):
    """The owner could not take the evidence lock within its bound; the tree is partial."""


# ------------------------------------------------------------------ S1: the deadline
class Deadline:
    """A monotonic end-to-end budget covering reads, retries, backoff and decoding.

    The clock is injected, so tests exercise real expiry decisions without real waiting.
    """

    def __init__(self, budget_sec, *, clock, grace_sec=SHUTDOWN_GRACE_SEC, label="run"):
        budget_sec = float(budget_sec)
        if budget_sec <= 0:
            raise ValueError("deadline budget must be positive, got %r" % (budget_sec,))
        self.budget = budget_sec
        self.grace = float(grace_sec)
        self.label = label
        self._clock = clock
        self.started_at = clock()

    def elapsed(self):
        return self._clock() - self.started_at

    def remaining(self):
        return self.budget - self.elapsed()

    def expired(self):
        return self.remaining() <= 0

    def check(self, stage):
        if self.expired():
            raise DeadlineExceeded(
                "%s deadline of %.0fs expired at stage %r after %.1fs; no further work "
                "is started" % (self.label, self.budget, stage, self.elapsed()))

    def snapshot(self):
        return {"budget_sec": self.budget, "grace_sec": self.grace,
                "elapsed_sec": round(self.elapsed(), 3),
                "remaining_sec": round(self.remaining(), 3)}


def supervise(fn, *, deadline, poll_sec=SUPERVISE_POLL_SEC, name="m2b-worker",
              thread_factory=threading.Thread):
    """Run `fn` in a daemon worker and stop waiting for it at the deadline.

    Returns `fn`'s value, re-raises its exception, or raises `DeadlineExceeded`. An
    abandoned worker is never killed: see the module docstring for why, and for what is
    guaranteed instead.
    """
    box = {}

    def runner():
        try:
            box["value"] = fn()
        except BaseException as exc:                  # noqa: BLE001 - relayed verbatim
            box["error"] = exc

    worker = thread_factory(target=runner, name=name, daemon=True)
    worker.start()
    while True:
        worker.join(poll_sec)
        if not worker.is_alive():
            break
        if deadline.expired():
            raise DeadlineExceeded(
                "%s deadline of %.0fs expired while %r was still running; the run stops "
                "and the worker is abandoned (never killed), so shutdown may take up to "
                "a further %.0fs" % (deadline.label, deadline.budget, name, deadline.grace))
    if "error" in box:
        raise box["error"]
    return box.get("value")


def read_body_streamed(response, *, deadline, max_bytes=MAX_RESPONSE_BYTES,
                       chunk_size=CHUNK_BYTES):
    """Consume a streamed body under the deadline and a byte budget.

    This is the mechanism that makes the deadline real. With `stream=False` the body is
    already fully read by the time `session.get` returns, so nothing outside it can stop
    a response that keeps sending small chunks inside every read timeout.
    """
    chunks = []
    total = 0
    for chunk in response.iter_content(chunk_size=chunk_size):
        if chunk:
            total += len(chunk)
            if total > max_bytes:
                raise BodyTooLarge(
                    "response exceeded the %d-byte budget while still arriving; "
                    "aborting the read" % max_bytes)
            chunks.append(chunk)
        if deadline.expired():
            raise DeadlineExceeded(
                "%s deadline of %.0fs expired with %d bytes of the body received; the "
                "read is cut off rather than waited out"
                % (deadline.label, deadline.budget, total))
    return b"".join(chunks)


# ------------------------------------------------------- R1: the evidence owner
def _atomic_write(target, data):
    """Write bytes so a reader never sees a partial file."""
    target = Path(target)
    part = target.with_name(target.name + ".part")
    part.write_bytes(data)
    os.replace(part, target)


class EvidenceStore:
    """The ONE owner of the evidence tree. Every mutation goes through it.

    Why a boolean was not enough: `cancelled` guarded two manifest helpers while the raw
    body was written by a bare `Path.write_bytes`. A worker paused inside that write woke
    after the supervisor had finalized the aborted manifest and created a raw file that no
    record bound - an orphan that could race inventory, retention and cleanup.

    Rules, enforced by construction:

    * Workers never write into the tree. A body is STAGED into `<root>.pending/`, a
      sibling outside the tree, without holding the lock, so a blocked disk write blocks
      only the worker. It is then PUBLISHED: one critical section that moves the staged
      file into the tree, appends the record and rewrites the manifest. The tree never
      holds a body without its record, and never a record without its body.
    * `seal()` takes the same lock, runs the final manifest write and sets `sealed`.
      Every later `publish`/`mutate` is refused and the staged bytes are discarded. The
      lock makes the seal and an in-progress publication mutually exclusive, so
      finalization never runs concurrently with a worker that can publish.
    * The seal wait is bounded (`SEAL_TIMEOUT_SEC`). If a worker holds the lock longer,
      the flag is set anyway - no NEW publication can start - `final()` does NOT run, and
      the owner reports the tree as unsealed and partial and writes nothing more into it.
    * Post-seal writes (report, retention) are owner-only: the owner thread, or a thread
      carrying a token the owner issued and can revoke. A finalization worker abandoned
      at its deadline has its token revoked, so it cannot write into or clean up the
      retained tree afterwards. Capture workers never receive a token.
    """

    def __init__(self, root, *, owner_ident=None):
        self.root = Path(root)
        self.pending_root = self.root.with_name(self.root.name + PENDING_SUFFIX)
        self._lock = threading.Lock()
        self.sealed = False
        self.seal_reason = None
        #: Set by the owner, inside a critical section, the moment a worker is abandoned
        #: or the run aborts: from then on every WORKER publication is refused, before the
        #: seal. The seal alone left a window - close the abandoned job, fingerprint the
        #: protected inputs, seal - in which a worker that woke could still publish.
        self.refusing = None
        self.owner_ident = (owner_ident if owner_ident is not None
                            else threading.get_ident())
        self._tokens = set()
        self._holder = None
        self.published = []
        self.refused = []
        self._staged = 0

    def _is_worker(self):
        return threading.get_ident() != self.owner_ident

    def closed_for_workers(self):
        """True once workers may no longer publish: sealed, or refusing after an abort."""
        return self.sealed or (self.refusing is not None and self._is_worker())

    def refuse_workers(self, reason):
        """Owner only; call inside a critical section (`mutate`) so no publication is in
        flight when the flag is set and none can start afterwards."""
        self.refusing = reason

    def in_critical_section(self):
        """True for the thread currently inside publish/mutate/seal.

        A FORCED seal (lock not obtained in time) sets the flag while a worker is inside
        its critical section. That worker's body/record/manifest publication must still
        complete as ONE unit - stopping it halfway would leave a body without its
        record - so the late-write guards do not apply to the holder of the lock. No new
        critical section can start after the flag is set.
        """
        return self._holder == threading.get_ident()

    # ------------------------------------------------------------- worker side
    def stage(self, name, data):
        """Write `data` OUTSIDE the tree. No lock is held.

        The refusal is re-checked after the directory exists, so a worker that passed
        the first check before the seal cannot recreate the pending directory after
        `discard_pending()` has removed it.
        """
        if self.closed_for_workers():
            raise EvidenceSealed("the evidence tree is closed (%s); nothing is staged "
                                 "for %r" % (self.seal_reason or self.refusing, name))
        self.pending_root.mkdir(parents=True, exist_ok=True)
        if self.closed_for_workers():
            self._prune_pending()
            raise EvidenceSealed("the evidence tree closed while staging %r" % name)
        self._staged += 1
        path = self.pending_root / ("%04d_%s" % (self._staged, name))
        path.write_bytes(data)
        return path

    def publish(self, relative, staged, then):
        """Move a staged file into the tree and run `then()` under the SAME lock.

        `then` appends the record and rewrites the manifest, so body and record become
        visible together. Refused after the seal; the staged file is then discarded.
        """
        with self._lock:
            self._holder = threading.get_ident()
            try:
                if self.closed_for_workers():
                    self._discard(staged)
                    reason = self.seal_reason or self.refusing
                    self.refused.append({"relative": relative, "reason": reason})
                    raise EvidenceSealed("the evidence tree is closed (%s); refusing to "
                                         "publish %s" % (reason, relative))
                target = self.root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                os.replace(staged, target)
                self.published.append(relative)
                try:
                    return then()
                except BaseException:
                    # Transactional: if the record/manifest half fails, the body half is
                    # undone. Publishing is all-or-nothing, so the tree can never hold a
                    # body that no record binds - the orphan R1 exists to prevent.
                    with contextlib.suppress(OSError):
                        os.replace(target, staged)
                    self.published.pop()
                    raise
            finally:
                self._holder = None

    def mutate(self, then, *, timeout=None):
        """A record/manifest mutation with no body, under the same rules.

        Workers wait for the lock; the owner passes a `timeout` so a worker blocked
        inside a publication can never make the owner wait indefinitely.
        """
        if timeout is None:
            self._lock.acquire()
        elif not self._lock.acquire(timeout=timeout):
            # The owner could not get the lock in time. Force the seal NOW so no new
            # publication can start and no second wait is taken by a later seal call.
            if not self.sealed:
                self.sealed = True
                self.seal_reason = ("FORCED: a worker held the evidence lock past %.0fs "
                                    "during an owner mutation" % timeout)
            raise EvidenceUnsealable(
                "the evidence lock could not be taken within %.0fs; a worker holds it "
                "inside a publication. The tree is now force-sealed" % timeout)
        self._holder = threading.get_ident()
        try:
            if self.closed_for_workers():
                reason = self.seal_reason or self.refusing
                self.refused.append({"relative": None, "reason": reason})
                raise EvidenceSealed("the evidence tree is closed (%s); refusing a late "
                                     "mutation" % reason)
            return then()
        finally:
            self._holder = None
            self._lock.release()

    # -------------------------------------------------------------- owner side
    def seal(self, reason, final, *, timeout=None):
        """Run `final()` and set `sealed` inside one bounded critical section.

        Returns `(True, value)` when sealed under the lock. Returns `(False, None)` when
        the lock could not be taken in time: the flag is still set so no new publication
        starts, but `final()` did not run and the tree is unsealed and partial.
        """
        timeout = SEAL_TIMEOUT_SEC if timeout is None else timeout
        if self.sealed:
            # Already sealed (possibly forced by a failed owner mutation): never wait
            # a second time.
            return False, None
        if not self._lock.acquire(timeout=timeout):
            self.sealed = True
            self.seal_reason = ("%s (FORCED: a worker held the evidence lock past %.0fs)"
                                % (reason, timeout))
            return False, None
        self._holder = threading.get_ident()
        try:
            value = final()
            self.sealed, self.seal_reason = True, reason
            return True, value
        finally:
            self._holder = None
            self._lock.release()

    def issue_token(self):
        token = object()
        self._tokens.add(token)
        return token

    def revoke(self, token, *, timeout=None):
        """Revoke under the lock, so it cannot interleave with a guarded operation.

        If the lock cannot be taken in time (the abandoned worker is blocked inside
        exactly one guarded operation), the token is revoked anyway: that one operation
        completes as a unit and every later one is refused.
        """
        timeout = SEAL_TIMEOUT_SEC if timeout is None else timeout
        acquired = self._lock.acquire(timeout=timeout)
        try:
            self._tokens.discard(token)
        finally:
            if acquired:
                self._lock.release()

    def token_valid(self, token):
        return token in self._tokens

    def _authorize(self, token, what):
        if token is not None:
            if token not in self._tokens:
                raise EvidenceSealed("finalization token revoked; refusing to %s" % what)
        elif self._is_worker():
            raise EvidenceSealed("only the owner thread may %s" % what)

    def _guarded(self, token, what, operation, *, timeout=None):
        """Run one tree operation under the lock with the authorization re-checked
        immediately before it. A revoked token can never start it; a worker blocked
        inside it completes exactly that one operation."""
        timeout = SEAL_TIMEOUT_SEC if timeout is None else timeout
        if not self._lock.acquire(timeout=timeout):
            raise EvidenceUnsealable("the evidence lock could not be taken within %.0fs "
                                     "to %s" % (timeout, what))
        self._holder = threading.get_ident()
        try:
            self._authorize(token, what)
            return operation()
        finally:
            self._holder = None
            self._lock.release()

    def owner_write(self, relative, data, *, token=None):
        """A post-seal write by the owner (or a token the owner issued and not revoked).

        Staged OUTSIDE the tree first; the move into the tree is the guarded operation,
        so a worker abandoned while blocked in the write cannot land it after its token
        is revoked - the same discipline `publish` applies to worker bodies.
        """
        self._authorize(token, "write %s" % relative)
        self.pending_root.mkdir(parents=True, exist_ok=True)
        self._staged += 1
        staged = self.pending_root / ("%04d_owner_%s" % (self._staged,
                                                       relative.replace("/", "_")))
        staged.write_bytes(data)
        target = self.root / relative

        def move():
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(staged, target)
            return target

        try:
            return self._guarded(token, "write %s into the tree" % relative, move)
        except EvidenceSealed:
            self._discard(staged)
            raise

    def owner_rename(self, source, destination, *, token=None):
        """The retention rename, guarded the same way."""
        return self._guarded(token, "rename %s to %s" % (source, destination),
                             lambda: os.rename(source, destination))

    def owner_detach(self, relative, *, token=None):
        """Move a subtree OUT of the tree (into the pending area) under the guard.

        Deleting inside the tree is never done directly: an abandoned worker blocked in
        an `rmtree` would keep deleting after its token was revoked. Detaching is one
        rename; the detached subtree is removed outside the tree afterwards.
        """
        self.pending_root.mkdir(parents=True, exist_ok=True)
        self._staged += 1
        destination = self.pending_root / ("%04d_detached_%s"
                                           % (self._staged, relative.replace("/", "_")))
        source = self.root / relative

        def move():
            os.rename(source, destination)
            return destination

        return self._guarded(token, "detach %s from the tree" % relative, move)

    def relocate(self, new_root, *, token=None):
        self._authorize(token, "relocate the tree root")
        self.root = Path(new_root)

    def discard_pending(self, *, token=None):
        """Remove the pending directory; report what a straggler may have left."""
        import shutil

        self._authorize(token, "remove the staging directory")
        leftover = []
        if self.pending_root.exists():
            leftover = sorted(p.name for p in self.pending_root.iterdir())
            shutil.rmtree(self.pending_root, ignore_errors=True)
        return {"leftover_staged": leftover,
                "still_present": self.pending_root.exists()}

    def _prune_pending(self):
        with contextlib.suppress(OSError):
            self.pending_root.rmdir()             # only succeeds when empty

    def _discard(self, staged):
        with contextlib.suppress(OSError):
            Path(staged).unlink()
        self._prune_pending()


# ------------------------------------------------------------------------- redaction
def redact_headers(headers):
    """Drop credential-bearing header values; keep the names so their presence shows."""
    out = {}
    for key, value in dict(headers or {}).items():
        out[key] = "<redacted>" if str(key).lower() in SENSITIVE_HEADERS else value
    return out


def redact_url(url):
    """Strip any userinfo from a URL before it reaches evidence or a log."""
    if not url:
        return url
    parts = urlsplit(str(url))
    if "@" in parts.netloc:
        host = parts.netloc.rsplit("@", 1)[1]
        parts = parts._replace(netloc="<redacted>@" + host)
    return urlunsplit(parts)


def redact_proxies(proxies):
    return {scheme: redact_url(value) for scheme, value in dict(proxies or {}).items()}


# ---------------------------------------------------- G4/G5: URLs from the ADAPTER
def adapter_constants():
    """Read the URL templates from the INSTALLED package, never from a local copy.

    M2a's templates are wrong for the live path: its index template omits `hisdata/` and
    the `d=2020_2_4` query (G4) and it formats the uppercase manifest symbol (G5). Both
    would make a real index job fail closed for the wrong reason.
    """
    from akshare.stock import cons as stock_cons
    from akshare.index import cons as index_cons
    import akshare

    return {
        "akshare_version": getattr(akshare, "__version__", None),
        "stock_hist": stock_cons.zh_sina_a_stock_hist_url,
        "stock_amount": stock_cons.zh_sina_a_stock_amount_url,
        "index_hist": index_cons.zh_sina_index_stock_hist_url,
        "index_params": {"d": "2020_2_4"},
    }


def expected_requests(constants=None):
    """The five requests, in job order, derived from the installed constants."""
    c = constants or adapter_constants()
    query = "&".join("%s=%s" % kv for kv in sorted(c["index_params"].items()))
    out = []
    for job in JOBS:
        sym = job["adapter_symbol"]
        if job["instrument_class"] == "stock":
            out.append({"job": job["job"], "symbol": sym, "kind": "klc",
                        "url": c["stock_hist"].format(sym)})
            out.append({"job": job["job"], "symbol": sym, "kind": "outstanding_share",
                        "url": c["stock_amount"].format(sym, sym)})
        else:
            out.append({"job": job["job"], "symbol": sym, "kind": "klc",
                        "url": c["index_hist"].format(sym) + "?" + query})
    for index, item in enumerate(out, start=1):
        item["index"] = index
        item["filename"] = "%02d_%s_%s.bin" % (
            index, item["symbol"],
            "klc_kl.js" if item["kind"] == "klc" else "getAmountBySymbol")
    return out


# ------------------------------------------------------------ S3: the frozen reference
REFERENCE_FIELDS = ("symbol", "trade_date", "close", "volume", "amount", "source",
                    "adjustment_mode", "volume_unit", "quality_status", "updated_at")
REFERENCE_SQL = (
    "SELECT symbol, trade_date, close, volume, amount, source, adjustment_mode, "
    "volume_unit, quality_status, updated_at FROM daily_bar_cache "
    "WHERE symbol IN (%s) AND quality_status = 'ready' "
    "AND trade_date >= ? AND trade_date <= ? ORDER BY symbol, trade_date")
REFERENCE_RULES = {
    "database": "trading_local.sqlite3",
    "table": "daily_bar_cache",
    "open_mode": "file:...?mode=ro plus PRAGMA query_only=1",
    "filters": ["quality_status = 'ready'",
                "trade_date between %s and %s" % (WINDOW_START, WINDOW_END)],
    "basis_expected": out.BASIS_EXPECTED,
    "thresholds": out.THRESHOLDS,
    "corroboration_span_rule": "reference sessions with volume > 0",
    "never_opened": "market_history.sqlite3",
    "note": ("adjustment_mode is recorded, not filtered, so a mixed-basis overlap is "
             "visible as a reference-quality reason instead of being silently dropped"),
}


#: Addresses that are not "the network" for our purposes.
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost", "0.0.0.0", "", None})


def proxy_endpoints(getproxies=None):
    """`{(host, port)}` for every proxy the environment configures.

    This machine routes external HTTP(S) through `http://127.0.0.1:7892`, so "loopback
    is allowed" would have left a tunnel straight to the vendor open. These endpoints are
    read from the environment and refused like any remote host - by address, without
    contacting them.
    """
    if getproxies is None:
        import urllib.request

        getproxies = urllib.request.getproxies
    endpoints = set()
    for scheme, value in (getproxies() or {}).items():
        if scheme in ("no",) or not value:
            continue
        parts = urlsplit(value if "//" in str(value) else "//" + str(value))
        if parts.hostname:
            endpoints.add((parts.hostname, parts.port))
    return endpoints


@contextlib.contextmanager
def no_remote_connections(reason="this code path must not reach the network",
                          getproxies=None, requests_module=None):
    """Refuse every connection to a non-loopback host, every configured proxy endpoint,
    and every genuine HTTP request through `requests`.

    Deliberately NOT a blanket `socket.socket` block. The JS engine this project decodes
    with (`py_mini_racer`) starts an asyncio loop whose self-pipe is a loopback socket
    pair on Windows, so forbidding the socket class itself would break the very adapter
    replay this guard is meant to protect - the replay would then always FAIL for a
    reason that has nothing to do with the vendor.

    Three layers, because "non-loopback only" was not enough:

    1. connections to a non-loopback host are refused;
    2. connections to a LOOPBACK PROXY endpoint are refused too - the observed
       environment tunnels external HTTPS through `127.0.0.1:7892`, which the first layer
       alone would have permitted;
    3. `requests.Session.request` itself is refused, so no genuine HTTP call can even
       begin, whatever it would have dialled.

    Nothing here contacts the proxy: the endpoint is read from the environment and
    matched by address.
    """
    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex
    real_create = socket.create_connection
    real_getaddrinfo = socket.getaddrinfo
    proxies = proxy_endpoints(getproxies)

    def host_of(address):
        if isinstance(address, (tuple, list)) and address:
            return str(address[0])
        return address if address is None else str(address)

    def port_of(address):
        if isinstance(address, (tuple, list)) and len(address) > 1:
            try:
                return int(address[1])
            except (TypeError, ValueError):
                return None
        return None

    def guard(address):
        host, port = host_of(address), port_of(address)
        if host not in LOOPBACK_HOSTS:
            raise AssertionError("%s (refused a connection to %r)" % (reason, host))
        for proxy_host, proxy_port in proxies:
            if host == proxy_host and (proxy_port is None or port == proxy_port):
                raise AssertionError(
                    "%s (refused a connection to the configured proxy %s:%s - a loopback "
                    "proxy is a tunnel to the vendor, not a local resource)"
                    % (reason, proxy_host, proxy_port))

    def connect(self, address, *args, **kwargs):
        guard(address)
        return real_connect(self, address, *args, **kwargs)

    def connect_ex(self, address, *args, **kwargs):
        guard(address)
        return real_connect_ex(self, address, *args, **kwargs)

    def create_connection(address, *args, **kwargs):
        guard(address)
        return real_create(address, *args, **kwargs)

    def getaddrinfo(host, *args, **kwargs):
        guard(host)
        return real_getaddrinfo(host, *args, **kwargs)

    def refuse_request(self, method, url, *args, **kwargs):
        raise AssertionError("%s (refused a genuine HTTP %s to %r)"
                             % (reason, method, redact_url(url)))

    requests_module = requests_module or _import_requests()
    real_request = getattr(getattr(requests_module, "Session", None), "request", None)

    socket.socket.connect = connect
    socket.socket.connect_ex = connect_ex
    socket.create_connection = create_connection
    socket.getaddrinfo = getaddrinfo
    if real_request is not None:
        requests_module.Session.request = refuse_request
    try:
        yield
    finally:
        socket.socket.connect = real_connect
        socket.socket.connect_ex = real_connect_ex
        socket.create_connection = real_create
        socket.getaddrinfo = real_getaddrinfo
        if real_request is not None:
            requests_module.Session.request = real_request


@contextlib.contextmanager
def db_guard(reason="replay must not open a production database"):
    """Make `sqlite3.connect` raise for the duration. Enforcement, not a promise."""
    original = sqlite3.connect

    def refuse(*args, **kwargs):
        raise SmokeError("%s (attempted sqlite3.connect(%r))"
                         % (reason, args[0] if args else None))

    sqlite3.connect = refuse
    try:
        yield
    finally:
        sqlite3.connect = original


def read_reference_extract(db_path=TRADING_DB, jobs=JOBS, *,
                           window=(WINDOW_START, WINDOW_END),
                           max_rows=MAX_REFERENCE_ROWS, connector=None):
    """Copy ONLY the rows and fields the checks consume, once, read-only.

    Everything downstream reads this extract, so a later cache refresh cannot change a
    replayed result while the captured response hashes stay identical (S3).
    """
    db_path = Path(db_path)
    if not db_path.exists():
        raise SmokeError("reference database not found: %s" % db_path)
    symbols = [j["manifest_symbol"] for j in jobs]
    sql = REFERENCE_SQL % ",".join("?" * len(symbols))
    connect = connector or (lambda p: sqlite3.connect("file:%s?mode=ro" % p, uri=True))
    conn = connect(str(db_path))
    try:
        conn.execute("PRAGMA query_only=1")
        cursor = conn.execute(sql, (*symbols, window[0], window[1]))
        raw = cursor.fetchall()
    finally:
        conn.close()
    if len(raw) > max_rows:
        raise SmokeError("reference extract would hold %d rows, above the %d-row cap"
                         % (len(raw), max_rows))

    rows = {sym: [] for sym in symbols}
    for record in raw:
        item = dict(zip(REFERENCE_FIELDS, record))
        rows.setdefault(item["symbol"], []).append(
            {k: item[k] for k in REFERENCE_FIELDS if k != "symbol"})

    extract = {
        "schema": "m2b.reference_extract.v1",
        "rules": dict(REFERENCE_RULES, sql=sql, symbols=symbols, window=list(window)),
        "database_fingerprint": fingerprint_path(db_path),
        "rows": rows,
        "row_counts": {sym: len(items) for sym, items in rows.items()},
    }
    extract["content_sha256"] = canonical_sha256(
        {"rules": extract["rules"], "rows": rows})
    return extract


# ------------------------------------------------------------------------ utilities
def canonical_json(payload):
    return json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def canonical_sha256(payload):
    return hashlib.sha256(canonical_json(payload)).hexdigest()


def fingerprint_path(path):
    path = Path(path)
    if not path.exists():
        return {"path": str(path), "exists": False}
    stat = path.stat()
    record = {"path": str(path), "exists": True, "size": stat.st_size,
              "mtime_ns": stat.st_mtime_ns}
    if stat.st_size <= 4 * 1024 * 1024:
        record["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    return record


def protected_fingerprints():
    """Everything the smoke must not change. The invalidation set is flagged."""
    out = {"invalidation_set": {}, "inputs": {}, "reported_only": {}}
    for path in (TRADING_DB, MARKET_DB, MARKET_WAL):
        out["invalidation_set"][path.name] = fingerprint_path(path)
    out["reported_only"][MARKET_SHM.name] = fingerprint_path(MARKET_SHM)
    out["inputs"][MANIFEST.name] = fingerprint_path(MANIFEST)
    out["inputs"][CALENDAR.name] = fingerprint_path(CALENDAR)
    for folder in ("_m1_closure", "_m2_pilot"):
        base = REPO_ROOT / "claude methods" / folder
        for py in sorted(base.glob("*.py")):
            out["inputs"]["%s/%s" % (folder, py.name)] = fingerprint_path(py)
    app = REPO_ROOT / "backend" / "app"
    if app.exists():
        digest = hashlib.sha256()
        for py in sorted(app.rglob("*.py")):
            digest.update(py.relative_to(app).as_posix().encode("utf-8"))
            digest.update(hashlib.sha256(py.read_bytes()).digest())
        out["inputs"]["backend/app/**.py"] = {"tree_sha256": digest.hexdigest()}
    return out


def compare_fingerprints(before, after):
    """Return `(invalidating_changes, reported_changes)`."""
    invalidating, reported = [], []
    for section in ("invalidation_set", "inputs"):
        for key, value in before.get(section, {}).items():
            if after.get(section, {}).get(key) != value:
                invalidating.append("%s/%s" % (section, key))
    for key, value in before.get("reported_only", {}).items():
        if after.get("reported_only", {}).get(key) != value:
            reported.append("reported_only/%s" % key)
    return invalidating, reported


def utc_now():
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _git(args):
    try:
        out = subprocess.run(["git", *args], cwd=str(REPO_ROOT), capture_output=True,
                             text=True, timeout=30, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        return None, str(exc)
    return out.stdout.strip(), (out.stderr or "").strip()


class InventoryUnavailable(SmokeError):
    """The process inventory could not be obtained, completely and unambiguously.

    D2. This exists so that "we could not look" can never be reported as "nothing is
    running". The previous lister swallowed every failure into an empty list: a non-zero
    exit, blank stdout, unparseable JSON or a strict-decode error all produced `[]`, and
    F8 then matched nothing and PASSED. Missing safety evidence is not safety.
    """


#: Producer-side encoding is stated explicitly rather than inherited from the console
#: code page, and the parent decodes the bytes STRICTLY. Lossy replacement is deliberately
#: not used: a body we cannot decode is a body we cannot vouch for, and silently mangling
#: a command line could turn a running worker into an unrecognised one.
_INVENTORY_PS = (
    "[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false); "
    "Get-CimInstance Win32_Process | Select-Object ProcessId,Name,CommandLine "
    "| ConvertTo-Json -Compress")

#: Image names the project's own stack runs under. A process with one of these names and
#: an unreadable command line is AMBIGUOUS, not absent (see `classify_process`).
_STACK_IMAGES = frozenset({"python", "pythonw", "python3", "uvicorn", "node",
                           "powershell", "pwsh"})


def _run_inventory_command(argv, timeout):            # pragma: no cover - spawns a shell
    try:
        return subprocess.run(argv, capture_output=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired as exc:
        raise InventoryUnavailable("the process inventory timed out after %ss" % timeout) from exc
    except (OSError, subprocess.SubprocessError) as exc:
        raise InventoryUnavailable("the process inventory could not be run: %s" % exc) from exc


def _decode_inventory(completed, *, encoding="utf-8-sig"):
    """Bytes -> text, strictly, with the process's own exit status honoured first."""
    if completed.returncode != 0:
        raise InventoryUnavailable(
            "the process inventory command exited %d; refusing to treat its output as a "
            "complete picture" % completed.returncode)
    raw = completed.stdout or b""
    if not raw.strip():
        raise InventoryUnavailable("the process inventory returned no output")
    try:
        return raw.decode(encoding, errors="strict")
    except UnicodeDecodeError as exc:
        raise InventoryUnavailable(
            "the process inventory did not decode as %s: %s. It is NOT re-read with "
            "errors='replace': a mangled command line could hide a running worker."
            % (encoding, exc)) from exc


def _normalize_inventory(text):
    """Parse and validate the shape. Anything incomplete raises."""
    try:
        data = json.loads(text)
    except ValueError as exc:
        raise InventoryUnavailable("the process inventory is not valid JSON: %s" % exc) from exc
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list):
        raise InventoryUnavailable("the process inventory is %s, not a list"
                                   % type(data).__name__)
    if not data:
        raise InventoryUnavailable(
            "the process inventory is empty; a machine always has running processes, so "
            "an empty list means the query failed rather than that nothing is running")
    items = []
    for index, item in enumerate(data):
        if not isinstance(item, dict):
            raise InventoryUnavailable("inventory record %d is %s, not an object"
                                       % (index, type(item).__name__))
        if "ProcessId" not in item or item.get("ProcessId") is None:
            raise InventoryUnavailable("inventory record %d carries no ProcessId" % index)
        if "CommandLine" not in item:
            raise InventoryUnavailable(
                "inventory record %d (pid %s) has no CommandLine field at all; the query "
                "did not return the columns this check needs"
                % (index, item.get("ProcessId")))
        command = item.get("CommandLine")
        if command is not None and not isinstance(command, str):
            raise InventoryUnavailable(
                "inventory record %d (pid %s) has a non-string CommandLine (%s)"
                % (index, item.get("ProcessId"), type(command).__name__))
        name = item.get("Name")
        if name is not None and not isinstance(name, str):
            raise InventoryUnavailable(
                "inventory record %d (pid %s) has a non-string Name (%s)"
                % (index, item.get("ProcessId"), type(name).__name__))
        # A blank or whitespace-only command line carries no more information than a
        # null one. Calling it "available" let an empty string stand in for evidence.
        available = command is not None and command.strip() != ""
        items.append({"pid": item.get("ProcessId"),
                      "name": (name or "").strip(),
                      "cmdline": command or "",
                      "cmdline_available": available})
    return items


def default_process_lister(timeout=120):              # pragma: no cover - spawns a shell
    """A read-only process inventory. Never signals or terminates anything.

    Raises `InventoryUnavailable` rather than returning a partial or empty list.
    """
    if os.name != "nt":
        completed = _run_inventory_command(["ps", "-eo", "pid=,comm=,args="], timeout)
        text = _decode_inventory(completed, encoding="utf-8")
        items = []
        for line in text.splitlines():
            pid, _, rest = line.strip().partition(" ")
            comm, _, args = rest.strip().partition(" ")
            if pid.isdigit():
                items.append({"pid": int(pid), "name": comm.strip(),
                              "cmdline": args.strip(), "cmdline_available": bool(args.strip())})
        if not items:
            raise InventoryUnavailable("the process inventory listed no processes")
        return items
    completed = _run_inventory_command(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", _INVENTORY_PS], timeout)
    return _normalize_inventory(_decode_inventory(completed))


# ------------------------------------------------------- D2: what the stack looks like
def _tokenize(cmdline):
    """Split a Windows command line on whitespace, honouring double quotes."""
    tokens, current, quoted = [], [], False
    for ch in cmdline or "":
        if ch == '"':
            quoted = not quoted
        elif ch.isspace() and not quoted:
            if current:
                tokens.append("".join(current))
                current = []
        else:
            current.append(ch)
    if current:
        tokens.append("".join(current))
    return tokens


#: Flags after which the remaining tokens are a program STRING rather than an argument
#: vector. That program may be a LAUNCH or it may merely quote one - the two are told
#: apart by `_inline_verdict`, never assumed. An earlier comment here claimed inline code
#: is necessarily "talking about" a launch; that was wrong, and it let
#: `python -c "uvicorn.run('app.main:app', ...)"` through as harmless.
_INLINE_PROGRAM_FLAGS = frozenset({"-c", "-command", "-encodedcommand", "-e", "-ec"})

#: The worker entrypoints `scripts/run_stack.ps1` starts. They are matched by BASENAME so
#: that the same script started from the backend working directory - `scripts\\x_loop.py`,
#: with no `backend/` prefix - is recognised too. The interpreter identity check is what
#: keeps this from matching an editor or a grep that merely names the file.
_KNOWN_WORKERS = frozenset({
    "control_plane_loop.py", "reference_data_loop.py", "full_market_feature_loop.py",
    "market_history_refresh_loop.py", "capital_flow_refresh_loop.py",
    "instrument_catalog_refresh_loop.py", "full_market_calibration_loop.py",
    "codex_market_pulse.py", "codex_decision_review.py", "automation_loop.py",
})
_LOOP_SCRIPT = re.compile(r"backend[\\/]scripts[\\/][A-Za-z0-9_]+\.py$", re.I)
_STACK_PS1 = re.compile(r"[\\/]?(run_stack|ensure_stack)\.ps1$", re.I)
_VITE_ENTRY = re.compile(r"[\\/]vite[\\/]bin[\\/]vite\.js$", re.I)

#: Longest inline program inspected. Bounded on purpose: this is pattern recognition of a
#: few known launch shapes, not a shell parser, and nothing here is ever evaluated.
MAX_INLINE_PROGRAM_CHARS = 4096

#: Python source that STARTS something. Recognising the shape is not evaluating it.
_PY_INVOKES = (
    re.compile(r"\buvicorn\s*\.\s*run\s*\(", re.I),
    re.compile(r"\brunpy\s*\.\s*run_(path|module)\s*\(", re.I),
    re.compile(r"\bexec\s*\(\s*open\s*\(", re.I),
    re.compile(r"\bsubprocess\s*\.\s*(run|Popen|call|check_call|check_output)\s*\(", re.I),
    re.compile(r"\bos\s*\.\s*(system|popen|execl|execv|execvp|spawn\w*)\s*\(", re.I),
)
#: Calls a program may make and still be provably inert. Bare names only - an attribute
#: call such as `os.system` is not on this list and never will be.
_INERT_CALLS = frozenset({"print", "repr", "str", "len", "format"})
#: Bound on the parsed shape, so the check stays finite on a hostile program.
MAX_INLINE_AST_NODES = 400


def _python_program_is_inert(program):
    """`(inert, reason)` - is the WHOLE program only literal printing?

    The previous rule was `^\\s*(print|repr|str)\\s*\\(.*\\)\\s*;?\\s*$` with a greedy
    `.*`, which a compound program satisfied by merely STARTING with a print:
    `print('starting'); from uvicorn import run; run('app.main:app')` matched it and was
    called harmless. A harmless prefix is not a harmless program.

    This parses the program into an AST and requires **every** statement to be an
    expression statement calling one of `_INERT_CALLS` by bare name, with literal
    arguments only. Parsing is not evaluation: `ast.parse` builds a tree and runs
    nothing. Anything it cannot prove inert - an import, an assignment, a loop, an
    attribute call, a name argument, a comprehension, a syntax error - is not inert, and
    the caller then treats a relevant program as ambiguous rather than harmless.
    """
    try:
        tree = ast.parse(program, mode="exec")
    except (SyntaxError, ValueError, MemoryError, RecursionError) as exc:
        return False, "the program does not parse as Python (%s)" % type(exc).__name__
    nodes = 0
    for _node in ast.walk(tree):
        nodes += 1
        if nodes > MAX_INLINE_AST_NODES:
            return False, ("the program has more than %d nodes, beyond the bound this "
                           "check inspects" % MAX_INLINE_AST_NODES)
    if not tree.body:
        return True, "the program is empty"

    def literal(node):
        if isinstance(node, ast.Constant):
            return True
        if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
            return all(literal(item) for item in node.elts)
        if isinstance(node, ast.Dict):
            return all(k is not None and literal(k) for k in node.keys) and \
                   all(literal(v) for v in node.values)
        if isinstance(node, ast.JoinedStr):
            # An f-string may interpolate arbitrary expressions; only a constant one is
            # inert, and that is indistinguishable from a plain string anyway.
            return all(isinstance(v, ast.Constant) for v in node.values)
        return False

    for statement in tree.body:
        if not isinstance(statement, ast.Expr):
            return False, ("the program contains a %s statement, not only literal printing"
                           % type(statement).__name__)
        call = statement.value
        if not isinstance(call, ast.Call):
            if literal(call):
                continue                    # a bare literal expression does nothing
            return False, "the program contains a non-call expression that is not a literal"
        if not isinstance(call.func, ast.Name) or call.func.id not in _INERT_CALLS:
            name = getattr(call.func, "id", type(call.func).__name__)
            return False, "the program calls %r, which is not a provably inert call" % name
        for argument in list(call.args) + [kw.value for kw in call.keywords]:
            if not literal(argument):
                return False, ("an argument to %s is not a literal, so its effect is "
                               "not established" % call.func.id)
    return True, "every statement is a literal print or representation call"


#: Read-only PowerShell verbs. Necessary but NOT sufficient - see `_ps_program_is_inert`.
_PS_READONLY_VERBS = frozenset({
    "get-item", "get-childitem", "get-content", "select-string", "test-path",
    "resolve-path", "get-date", "get-location", "write-output", "write-host",
    "ls", "dir", "cat", "type", "gc", "gi", "gci", "echo", "pwd",
})
#: Anything that sequences, pipes, invokes, substitutes or redirects. Their presence
#: means the program is more than one simple read-only command, so it cannot be proven
#: inert here. This is a refusal rule, not a parser.
_PS_COMPOUND = re.compile(r"[;|&`{}()$><\n\r]")


def _ps_program_is_inert(program):
    """`(inert, reason)` - is the WHOLE program one simple read-only command?

    The previous rule only looked at the first verb, so
    `Get-Item .; python.exe scripts/control_plane_loop.py` and
    `Get-Item $(python.exe scripts/control_plane_loop.py)` both passed as listings. A
    command that merely BEGINS with a read-only verb is not a read-only command.
    """
    text = program.strip()
    if not text:
        return True, "the program is empty"
    if _PS_COMPOUND.search(text):
        return False, ("the program sequences, pipes, invokes, substitutes or redirects, "
                       "so it is not a single simple read-only command")
    tokens = _tokenize(text)
    if not tokens:
        return True, "the program is empty"
    if tokens[0].lower() not in _PS_READONLY_VERBS:
        return False, "the program's command %r is not a known read-only verb" % tokens[0]
    for argument in tokens[1:]:
        if argument.startswith("$") or "$" in argument:
            return False, "an argument is a variable or expression, not a literal"
    return True, "a single read-only command with literal arguments"

#: PowerShell that STARTS something: the call/dot operators, Start-Process, iex.
_PS_INVOKES = (
    re.compile(r"(?:^|[;&|({\s])[&.]\s*['\"]?[^'\";|]*\.ps1", re.I),
    re.compile(r"\bStart-Process\b", re.I),
    re.compile(r"\b(Invoke-Expression|iex)\b", re.I),
    re.compile(r"\bpython(?:\.exe)?\b[^;|]*\b-m\s+uvicorn\b", re.I),
)
#: Substrings that make an inline program RELEVANT - i.e. about this project's stack.
_RELEVANT_MARKERS = ("app.main:app", "uvicorn", "run_stack.ps1", "ensure_stack.ps1",
                     "vite.js") + tuple(sorted(_KNOWN_WORKERS))


def _inline_verdict(program, *, python):
    """`(verdict, reason)` for the program string behind `-c` / `-Command`.

    Three outcomes, deliberately: `stack` when a recognised launch shape is present,
    `other` when the program only names a target inside a literal print or a read-only
    listing verb, and `ambiguous` when it names a target in some other way. Ambiguous
    fails F8, because "we could not tell" is not "it is not running".
    """
    if not program:
        return "other", "no inline program"
    if len(program) > MAX_INLINE_PROGRAM_CHARS:
        return "ambiguous", ("the inline program is %d characters, beyond the %d-character "
                             "bound this check inspects" % (len(program),
                                                            MAX_INLINE_PROGRAM_CHARS))
    lowered = program.lower()
    relevant = [m for m in _RELEVANT_MARKERS if m.lower() in lowered]
    if not relevant:
        return "other", "the inline program does not name any stack target"

    # Inertness is established FIRST, over the whole program. The invocation patterns are
    # substring searches and cannot tell a call from the same text inside a string
    # literal, so consulting them first misread `print('uvicorn.run(app.main:app)')` as a
    # launch. Reordering alone would not have been enough - the old harmless rules were
    # themselves unsound, which is why both were replaced.
    inert, why = (_python_program_is_inert(program) if python
                  else _ps_program_is_inert(program))
    if inert:
        return "other", ("the inline program names %s but is provably inert: %s"
                         % (relevant[0], why))

    for pattern in (_PY_INVOKES if python else _PS_INVOKES):
        if pattern.search(program):
            return "stack", ("the inline program invokes a stack target (%s) - matched %s"
                             % (relevant[0], pattern.pattern[:40]))
    return "ambiguous", ("the inline program names %s and could not be proven inert (%s), "
                         "nor does it match a recognised launch, so it cannot be ruled out"
                         % (relevant[0], why))


def _inline_program(tokens):
    """The program string that follows the first inline-program flag, or None."""
    for index, token in enumerate(tokens):
        if token.lower() in _INLINE_PROGRAM_FLAGS:
            return " ".join(tokens[index + 1:]).strip()
    return None


def _effective_tokens(tokens):
    """Tokens that are real arguments, stopping at the first inline-program flag."""
    out = []
    for token in tokens:
        if token.lower() in _INLINE_PROGRAM_FLAGS:
            break
        out.append(token)
    return out


def classify_process(record):
    """`(verdict, reason)` for one inventory record.

    `verdict` is one of `stack` (this is the project's own API/worker/frontend/launcher),
    `ambiguous` (an image the stack uses whose command line we cannot read, so absence is
    unproven) or `other`.

    The forms recognised are the ones `scripts/run_stack.ps1` actually starts:

    * the API   - `python.exe -X utf8 -m uvicorn app.main:app --host ... --port ...`
                  (`run_stack.ps1:338`; the previous regex demanded `backend` after
                  `uvicorn` and therefore missed this exact command);
    * a worker  - `python.exe -X utf8 <BackendRoot>\\scripts\\<name>_loop.py ...`, and the
                  other `backend/scripts/*.py` workers launched the same way;
    * the front - `node.exe <...>\\node_modules\\vite\\bin\\vite.js --host ...`, or npm run dev;
    * a launcher- `powershell -File <...>\\run_stack.ps1` / `ensure_stack.ps1`.
    """
    name = (record.get("name") or "").strip().lower()
    raw_command = (record.get("cmdline") or "").strip()
    # A blank or whitespace-only command line is no more informative than a null one.
    available = bool(record.get("cmdline_available", True)) and bool(raw_command)
    if not available:
        base = re.split(r"[\\/]", name)[-1]
        if base.endswith(".exe"):
            base = base[:-4]
        if not base:
            # Neither a usable image name nor a readable command line. Unidentifiable
            # must never collapse into unrelated.
            return "ambiguous", ("the record carries neither a usable image name nor a "
                                 "readable command line, so this process cannot be shown "
                                 "not to be part of the stack")
        if base in _STACK_IMAGES:
            return "ambiguous", ("%s has no readable command line, so it cannot be shown "
                                 "not to be part of the stack" % base)
        return "other", "command line unavailable, image is not one the stack uses"

    all_tokens = _tokenize(raw_command)
    tokens = _effective_tokens(all_tokens)
    lowered = [t.lower() for t in tokens]

    def image_is(*names):
        """True when the process image - by inventory name or argv[0] - is one of these.

        Matched with the directory and any `.exe` stripped, so `python.exe`,
        `D:\\...\\.venv\\Scripts\\python.exe` and a bare `python` are all recognised.
        """
        candidates = [name]
        if lowered:
            candidates.append(lowered[0])
        for candidate in candidates:
            if not candidate:
                continue
            base = re.split(r"[\\/]", candidate)[-1]
            if base.endswith(".exe"):
                base = base[:-4]
            if base in names:
                return True
        return False

    is_python = image_is("python", "pythonw", "python3")
    is_node = image_is("node")
    is_shell = image_is("powershell", "pwsh")
    is_uvicorn_exe = image_is("uvicorn")

    # --- the API ------------------------------------------------------------------
    if is_python or is_uvicorn_exe:
        for index, token in enumerate(lowered):
            if token == "uvicorn" and (index == 0 or lowered[index - 1] == "-m"):
                if any(t == "app.main:app" for t in lowered):
                    return "stack", "uvicorn serving app.main:app (the project API)"
                return "stack", "uvicorn launched from this interpreter"
        if is_uvicorn_exe and any(t == "app.main:app" for t in lowered):
            return "stack", "uvicorn executable serving app.main:app"

    # --- a worker -----------------------------------------------------------------
    # Absolute (`...\\backend\\scripts\\x_loop.py`) AND backend-relative
    # (`scripts\\x_loop.py`, or a bare basename) forms. Starting the same script from the
    # backend working directory omits the `backend/` prefix, which the earlier pattern
    # required - so a running worker read as a stopped machine.
    if is_python:
        for token in tokens:
            if _LOOP_SCRIPT.search(token):
                return "stack", "backend worker script %s" % token
            basename = re.split(r"[\\/]", token)[-1].lower()
            if basename in _KNOWN_WORKERS:
                return "stack", ("known worker entrypoint %s (relative or absolute form)"
                                 % basename)

    # --- the frontend -------------------------------------------------------------
    if is_node:
        for token in tokens:
            if _VITE_ENTRY.search(token):
                return "stack", "vite dev server %s" % token
        if "dev" in lowered and ("run" in lowered or "npm" in lowered):
            return "stack", "npm run dev (frontend)"

    # --- a launcher ---------------------------------------------------------------
    if is_shell:
        for token in tokens:
            if _STACK_PS1.search(token):
                return "stack", "stack launcher %s" % token

    # --- an inline program ---------------------------------------------------------
    # Everything above looked at the argument vector only. `-c` / `-Command` carries a
    # PROGRAM, and that program may itself start the API, a worker or the launcher inside
    # this very process - no child need appear. It is inspected, never evaluated.
    if is_python or is_shell or is_node:
        program = _inline_program(all_tokens)
        if program is not None:
            verdict, reason = _inline_verdict(program, python=is_python)
            if verdict != "other":
                return verdict, reason
            if "provably inert" in reason:
                # Keep the finding rather than the generic default: "this program names a
                # stack target and was proven inert" is evidence a reviewer should see.
                return "other", reason

    return "other", "no stack launch form matched"


# ------------------------------------------------------------------ pre-flight F1-F8
@dataclass
class Check:
    id: str
    status: str
    detail: str
    data: dict = field(default_factory=dict)

    def as_dict(self):
        return {"id": self.id, "status": self.status, "detail": self.detail,
                "data": self.data}


def preflight(*, out_root, evidence_dir, session=None, probe_reference=False,
              process_lister=default_process_lister, requests_module=None,
              reference_reader=None):
    """F1-F8. Returns `(checks, data)`. Never writes; opens a database only if asked."""
    checks = []
    data = {}

    # F1 ---------------------------------------------------------------- provenance
    branch, _ = _git(["rev-parse", "--abbrev-ref", "HEAD"])
    head, _ = _git(["rev-parse", "--short", "HEAD"])
    status, _ = _git(["status", "--short"])
    if head is None:
        checks.append(Check("F1", "FAIL", "git is not available; provenance unrecordable"))
    else:
        info = {"branch": branch, "head": head,
                "status_sha256": hashlib.sha256((status or "").encode("utf-8")).hexdigest(),
                "status_lines": len((status or "").splitlines())}
        data["git"] = info
        checks.append(Check("F1", "PASS", "branch %s @ %s, %d dirty paths"
                            % (branch, head, info["status_lines"]), info))

    # F2 ------------------------------------------------- protected inputs + reference
    prints = protected_fingerprints()
    data["protected_before"] = prints
    manifest_sha = prints["inputs"].get(MANIFEST.name, {}).get("sha256")
    calendar_sha = prints["inputs"].get(CALENDAR.name, {}).get("sha256")
    pinned_ok = (manifest_sha == MANIFEST_SHA256 and calendar_sha == CALENDAR_SHA256)
    if not pinned_ok:
        checks.append(Check("F2", "FAIL",
                            "manifest/calendar hashes do not match the pinned values",
                            {"manifest_sha256": manifest_sha,
                             "calendar_sha256": calendar_sha}))
    elif probe_reference:
        try:
            extract = (reference_reader or read_reference_extract)()
        except Exception as exc:                      # noqa: BLE001
            checks.append(Check("F2", "FAIL", "reference extract failed: %s" % exc))
        else:
            data["reference_extract"] = extract
            checks.append(Check("F2", "PASS",
                                "protected inputs fingerprinted; reference extract frozen",
                                {"row_counts": extract["row_counts"],
                                 "content_sha256": extract["content_sha256"]}))
    else:
        checks.append(Check(
            "F2", "PASS",
            "protected inputs fingerprinted; reference extract PLANNED (not read: "
            "--plan opens no database)",
            {"planned_sql": REFERENCE_SQL % ",".join("?" * len(JOBS)),
             "planned_symbols": [j["manifest_symbol"] for j in JOBS],
             "planned_window": [WINDOW_START, WINDOW_END]}))

    # F3 ------------------------------------------------------------ adapter identity
    try:
        constants = adapter_constants()
    except Exception as exc:                          # noqa: BLE001
        checks.append(Check("F3", "FAIL", "the installed adapter is unreadable: %s" % exc))
        constants = None
    else:
        data["adapter_constants"] = {k: v for k, v in constants.items()}
        version_ok = constants["akshare_version"] == AKSHARE_VERSION
        shapes_ok = (constants["stock_hist"].endswith("/hisdata_klc2/klc_kl.js")
                     and "getAmountBySymbol" in constants["stock_amount"]
                     and constants["index_hist"].endswith("/hisdata/klc_kl.js"))
        checks.append(Check(
            "F3", "PASS" if version_ok and shapes_ok else "FAIL",
            "akshare %s; URL constants %s" % (constants["akshare_version"],
                                              "as pinned" if shapes_ok else "CHANGED"),
            {"expected_version": AKSHARE_VERSION}))

    # F4 ----------------------------------------------------------- vendor JS routine
    try:
        from akshare.stock.cons import hk_js_decode

        routine_sha = hashlib.sha256(hk_js_decode.encode("utf-8")).hexdigest()
        if routine_sha != dec.HK_JS_DECODE_SHA256:
            checks.append(Check("F4", "FAIL", "hk_js_decode changed (sha256 %s)"
                                % routine_sha[:16], {"sha256": routine_sha}))
        else:
            import py_mini_racer

            py_mini_racer.MiniRacer().eval(hk_js_decode, timeout_sec=dec.DECODE_TIMEOUT_SEC)
            data["hk_js_decode_sha256"] = routine_sha
            checks.append(Check("F4", "PASS", "pinned routine evaluates in py_mini_racer",
                                {"sha256": routine_sha, "chars": len(hk_js_decode)}))
    except Exception as exc:                          # noqa: BLE001
        checks.append(Check("F4", "FAIL", "the JS routine is unusable: %s" % exc))

    # F5 ------------------------------------------------------------- session retries
    requests_module = requests_module or _import_requests()
    if requests_module is None:
        checks.append(Check("F5", "FAIL", "requests is not importable"))
        session = None
    else:
        session = session or requests_module.Session()
        try:
            tp.assert_no_hidden_retries(session)
        except tp.RunAborted as exc:
            checks.append(Check("F5", "FAIL", str(exc)))
        else:
            totals = {k: getattr(getattr(a, "max_retries", None), "total", None)
                      for k, a in getattr(session, "adapters", {}).items()}
            checks.append(Check("F5", "PASS", "no library-level retries", {"totals": totals}))

    # F6 ------------------------------------------------------------------ path roles
    out_root = Path(out_root).resolve()
    evidence_dir = Path(evidence_dir).resolve()
    problems = []
    if out_root.exists():
        problems.append("output root already exists: %s" % out_root)
    if evidence_dir.exists():
        problems.append("evidence directory already exists: %s" % evidence_dir)
    if TMP_ROOT.resolve() not in out_root.parents:
        problems.append("output root %s is not inside %s" % (out_root, TMP_ROOT))
    for label, protected in (("trading", TRADING_DB), ("history", MARKET_DB),
                             ("manifest", MANIFEST), ("calendar", CALENDAR)):
        target = protected.resolve()
        if out_root == target or out_root in target.parents or evidence_dir == target:
            problems.append("a smoke path aliases the protected input %s" % label)
    # Retention is ONE rename, so both roots must be on the same volume.
    try:
        anchor_out = next(p for p in [out_root, *out_root.parents] if p.exists())
        anchor_evidence = next(p for p in [evidence_dir, *evidence_dir.parents]
                               if p.exists())
        if os.stat(anchor_out).st_dev != os.stat(anchor_evidence).st_dev:
            problems.append("the evidence directory %s is not on the same volume as %s; "
                            "retention is a single rename and would fail"
                            % (evidence_dir, out_root))
    except (OSError, StopIteration) as exc:
        problems.append("could not compare volumes for the smoke paths: %s" % exc)
    checks.append(Check("F6", "FAIL" if problems else "PASS",
                        "; ".join(problems) if problems else
                        "output root and evidence directory are free and correctly placed",
                        {"out_root": str(out_root), "evidence_dir": str(evidence_dir)}))

    # F7 --------------------------------------------------------------- TLS trust pin
    tls = {"env_overrides": {}}
    problems = []
    for name in ("REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE", "SSL_CERT_FILE", "SSL_CERT_DIR"):
        value = os.environ.get(name)
        tls["env_overrides"][name] = value
        if value:
            problems.append("%s is set" % name)
    if session is not None and requests_module is not None:
        if session.verify is not True:
            problems.append("session.verify is %r" % (session.verify,))
        if session.cert is not None:
            problems.append("session.cert is set")
        try:
            for item in expected_requests(data.get("adapter_constants")):
                merged = session.merge_environment_settings(item["url"], {}, None, None, None)
                if merged.get("verify") is not True:
                    problems.append("verify would be overridden for %s" % item["url"])
        except Exception as exc:                      # noqa: BLE001
            problems.append("merge_environment_settings failed: %s" % exc)
        try:
            import certifi

            bundle = Path(requests_module.utils.DEFAULT_CA_BUNDLE_PATH)
            tls["certifi_version"] = certifi.__version__
            tls["ca_bundle"] = str(bundle)
            if bundle.resolve() != Path(certifi.where()).resolve():
                problems.append("the CA bundle is not certifi's")
            elif (REPO_ROOT / "backend" / ".venv").resolve() not in bundle.resolve().parents:
                problems.append("the CA bundle is outside backend/.venv")
            else:
                raw = bundle.read_bytes()
                tls["ca_bundle_sha256"] = hashlib.sha256(raw).hexdigest()
                tls["ca_bundle_bytes"] = len(raw)
        except Exception as exc:                      # noqa: BLE001
            problems.append("certifi is unusable: %s" % exc)
        try:
            tls["proxies"] = redact_proxies(
                requests_module.utils.get_environ_proxies(expected_requests(
                    data.get("adapter_constants"))[0]["url"]))
        except Exception:                             # noqa: BLE001
            tls["proxies"] = {}
    data["tls"] = tls
    checks.append(Check("F7", "FAIL" if problems else "PASS",
                        "; ".join(problems) if problems else
                        "TLS trust pinned to certifi inside backend/.venv, no override",
                        tls))

    # F8 -------------------------------------------------------- the stack is stopped
    #
    # D2. This check now fails CLOSED. It reports "stopped" only when it obtained a
    # complete inventory AND every record in it could be classified. An unavailable,
    # empty, malformed or partially readable inventory is a FAIL, because none of those
    # is evidence that nothing is running. Whatever the answer, no service is ever
    # started or stopped to obtain it.
    try:
        inventory = process_lister()
    except InventoryUnavailable as exc:
        data["process_inventory_size"] = 0
        checks.append(Check("F8", "FAIL",
                            "the process inventory is unavailable, so the stack cannot be "
                            "shown to be stopped: %s" % exc,
                            {"process_count": 0, "inventory_available": False}))
    except Exception as exc:                          # noqa: BLE001
        data["process_inventory_size"] = 0
        checks.append(Check("F8", "FAIL", "process inventory unavailable: %s: %s"
                            % (type(exc).__name__, exc),
                            {"process_count": 0, "inventory_available": False}))
    else:
        if not isinstance(inventory, list) or not inventory:
            data["process_inventory_size"] = 0
            checks.append(Check(
                "F8", "FAIL",
                "the process inventory is empty; that is a failed query, not an idle "
                "machine, and it is never read as 'the stack is stopped'",
                {"process_count": 0, "inventory_available": False}))
            return checks, data

        running, ambiguous = [], []
        for record in inventory:
            verdict, reason = classify_process(record)
            if verdict == "stack":
                running.append((record.get("pid"), reason,
                                redact_url(record.get("cmdline") or "")[:200]))
            elif verdict == "ambiguous":
                ambiguous.append((record.get("pid"), record.get("name"), reason))

        heartbeat_pid = None
        if HEARTBEAT.exists():
            try:
                heartbeat_pid = json.loads(HEARTBEAT.read_text(encoding="utf-8")).get("pid")
            except (ValueError, OSError):
                heartbeat_pid = "unreadable"
        live_heartbeat = [p for p in inventory
                          if heartbeat_pid is not None and p.get("pid") == heartbeat_pid]
        info = {"process_count": len(inventory),
                "inventory_available": True,
                "stack_matches": [{"pid": p, "why": why, "cmdline": cmd}
                                  for p, why, cmd in running],
                "unreadable_relevant": [{"pid": p, "name": n, "why": why}
                                        for p, n, why in ambiguous],
                "heartbeat_pid": heartbeat_pid,
                "heartbeat_pid_alive": bool(live_heartbeat)}
        data["process_inventory_size"] = len(inventory)

        problems = []
        if running:
            problems.append("the local stack appears to be running (%d process(es): %s); "
                            "stopping a service is the user's action, not the smoke's"
                            % (len(running), [p for p, _w, _c in running]))
        if ambiguous:
            problems.append("%d process(es) run under an image the stack uses but expose no "
                            "readable command line (%s), so their absence from the stack is "
                            "unproven" % (len(ambiguous), [p for p, _n, _w in ambiguous]))
        if live_heartbeat:
            problems.append("the refresh-loop heartbeat pid %s is alive" % heartbeat_pid)
        checks.append(Check("F8", "FAIL" if problems else "PASS",
                            "; ".join(problems) if problems else
                            "local stack stopped (%d processes inventoried, all classified)"
                            % len(inventory), info))
    return checks, data


def _import_requests():
    try:
        import requests

        return requests
    except Exception:                                 # noqa: BLE001
        return None


# ------------------------------------------------------------------ captured response
@dataclass
class CapturedResponse:
    """What `PacedTransport` needs, plus everything the evidence needs."""

    status: int
    text: str
    url: str
    headers: dict = field(default_factory=dict)
    content: bytes = b""
    encoding: str = None
    apparent_encoding: str = None
    requested_url: str = ""
    elapsed_sec: float = 0.0
    body_error: str = None


class TlsFailure(SmokeError):
    """A certificate/TLS failure. Deliberately NOT a builtin ConnectionError.

    `requests.exceptions.SSLError` inherits `ConnectionError`, so catching the broad
    parent mapped a certificate failure onto the builtin `ConnectionError`, which the
    unchanged M2a transport - correctly, for a real connection error - classifies as
    transient and retries. The result was three attempts against an unauthenticated
    channel. Repeating a TLS failure cannot make the channel authentic, so it is raised
    as a type the transport treats as non-retryable.
    """


class TimedTransport:
    """Stamps the ACTUAL post-pacing attempt start, for every attempt including retries.

    `PacedTransport.get_with_retries` sleeps out the pacing interval and then calls the
    injected callable, so the only place a true wire-attempt start can be observed is
    immediately around that call. The runner previously stamped the time before
    `get_with_retries`, i.e. before the pacing wait, and retries had no timestamp at all:
    a correctly paced run (0.0, 1.5, 3.0, 4.5, 6.0) was recorded as 0.0, 0.0, 1.5, 3.0,
    4.5 and failed its own pacing check with a 0.000 s gap.

    This wrapper sits between the transport and whatever callable is injected, so live
    and fake transports are measured the same way.

    R3: the attempt is the unit of evidence. Each entry carries the request it serves and
    its attempt number, and `on_attempt` is called at the START and at the END of every
    wire attempt so the manifest is persisted at the actual attempt boundary - an
    interrupted retry sequence therefore leaves every attempt it made on disk, not only
    the ones a completed retry group would have reported afterwards. A sealed tree refuses
    the call before it reaches the wire, so no late request can be issued.
    """

    def __init__(self, inner, *, clock, now=utc_now, store=None, on_attempt=None):
        self.inner = inner
        self.clock = clock
        self.now = now
        self.store = store
        self.on_attempt = on_attempt
        self.log = []
        self.current_request = None
        self._counts = {}

    def _notify(self, entry, phase):
        if self.on_attempt is not None:
            self.on_attempt(entry, phase)

    def __call__(self, url, *, timeout, allow_redirects):
        if self.store is not None and self.store.closed_for_workers():
            # The late call never reaches the wire. It is still LOGGED, because the
            # unchanged M2a transport counts the RunAborted we raise as an attempt, and
            # the retained records must agree with that count; `refused_before_wire`
            # says what it was, so it is never read as a gap in the evidence.
            index = self.current_request
            number = self._counts.get(index, 0) + 1
            self._counts[index] = number
            now = round(self.clock(), 6)
            self.log.append({"request_index": index, "attempt_no": number,
                             "url": redact_url(url), "source": SOURCE_KEY,
                             "started_at_monotonic": now, "started_at_utc": self.now(),
                             "finished_at_monotonic": now, "elapsed_sec": 0.0,
                             "status": None, "error": "RunAborted",
                             "transport_outcome": None, "waited_sec": None,
                             "refused_before_wire": True})
            raise tp.RunAborted("the evidence tree is closed (%s); no late request is "
                                "issued" % (self.store.seal_reason or self.store.refusing))
        index = self.current_request
        number = self._counts.get(index, 0) + 1
        self._counts[index] = number
        entry = {"request_index": index, "attempt_no": number, "url": redact_url(url),
                 "source": SOURCE_KEY, "started_at_monotonic": round(self.clock(), 6),
                 "started_at_utc": self.now(), "finished_at_monotonic": None,
                 "elapsed_sec": None, "status": None, "error": None,
                 "transport_outcome": None, "waited_sec": None}
        self.log.append(entry)
        # Persisted BEFORE the wire call: a call that never returns is still evidenced
        # as started. A sealed tree refuses this and the attempt is never issued.
        self._notify(entry, "start")
        try:
            response = self.inner(url, timeout=timeout, allow_redirects=allow_redirects)
        except BaseException as exc:                  # noqa: BLE001 - recorded, re-raised
            entry["error"] = type(exc).__name__
            entry["finished_at_monotonic"] = round(self.clock(), 6)
            entry["elapsed_sec"] = round(entry["finished_at_monotonic"]
                                         - entry["started_at_monotonic"], 6)
            self._notify(entry, "end")
            raise
        entry["status"] = getattr(response, "status", None)
        entry["finished_at_monotonic"] = round(self.clock(), 6)
        entry["elapsed_sec"] = round(entry["finished_at_monotonic"]
                                     - entry["started_at_monotonic"], 6)
        self._notify(entry, "end")
        return response


class LiveSinaTransport:
    """The only code in this repository that contacts the vendor. Armed mode only.

    A thin adapter over `session.get`, injected into the unchanged `PacedTransport`:

    * `SSLError` is caught BEFORE the broad `ConnectionError` and raised as `TlsFailure`,
      which is non-retryable (see that class);
    * a known **403/429 is latched from the response headers, before any body is read**.
      Status handling used to happen only after full body consumption, so a stop status
      whose body then timed out was reported as a retryable timeout: three attempts, and
      `aborted_reason` still NULL. A stop we already know about is never waited on;
    * any other non-200 still yields **bounded** evidence - a short, size-capped body read
      whose failure cannot mask the status - so a failed attempt is not evidence-free;
    * the body is streamed under the deadline and the result exposes `.status`, which a
      `requests.Response` does not have.

    `last_capture` holds the most recent `CapturedResponse` even when the transport then
    raises, so the runner can write the raw body and headers for a failed attempt.
    """

    #: Budget for reading the (small) body of a non-200 response. A failed attempt is
    #: worth evidence, but not worth waiting a full read timeout for.
    ERROR_BODY_BYTES = 256 * 1024

    def __init__(self, session, *, deadline, requests_module, clock=time.monotonic,
                 max_bytes=MAX_RESPONSE_BYTES, max_total_bytes=MAX_TOTAL_BYTES,
                 chunk_size=CHUNK_BYTES):
        self.session = session
        self.deadline = deadline
        self.requests = requests_module
        self.clock = clock
        self.max_bytes = max_bytes
        self.max_total_bytes = max_total_bytes
        self.chunk_size = chunk_size
        self.total_bytes = 0
        self.last_capture = None

    def _build(self, response, url, body, started, *, body_error=None):
        # Give `requests` the body back so `.text` and `.apparent_encoding` are exactly
        # what the adapter would have seen; fall back to an explicit decode if the
        # library internals ever change shape.
        text, apparent = None, None
        try:
            response._content = body
            response._content_consumed = True
            text = response.text
            apparent = response.apparent_encoding
        except Exception:                             # noqa: BLE001
            text = str(body, getattr(response, "encoding", None) or "utf-8",
                       errors="replace")
        captured = CapturedResponse(
            status=response.status_code, text=text, url=response.url,
            headers=redact_headers(response.headers), content=body,
            encoding=getattr(response, "encoding", None), apparent_encoding=apparent,
            requested_url=url, elapsed_sec=round(self.clock() - started, 3),
            body_error=body_error)
        self.last_capture = captured
        return captured

    def __call__(self, url, *, timeout, allow_redirects):
        self.deadline.check("before-request")
        started = self.clock()
        self.last_capture = None
        exceptions = self.requests.exceptions
        try:
            response = self.session.get(url, timeout=timeout,
                                        allow_redirects=allow_redirects, stream=True)
        except exceptions.SSLError as exc:
            raise TlsFailure("TLS/certificate failure, not retried: %s" % exc) from exc
        except exceptions.Timeout as exc:
            raise TimeoutError("request timed out: %s" % exc) from exc
        except exceptions.ConnectionError as exc:
            raise ConnectionError("connection failed: %s" % exc) from exc

        status = getattr(response, "status_code", None)

        if status in tp.STOP_STATUS:
            # Latched from the headers. No body read, no waiting, no chance for a body
            # error to turn a known stop into a retryable event.
            with contextlib.suppress(Exception):
                response.close()
            return self._build(response, url, b"", started,
                               body_error="body not read: 403/429 latched at headers")

        limit = self.max_bytes if status == 200 else self.ERROR_BODY_BYTES
        body, body_error = b"", None
        try:
            body = read_body_streamed(response, deadline=self.deadline, max_bytes=limit,
                                      chunk_size=self.chunk_size)
        except (BodyTooLarge, DeadlineExceeded):
            if status == 200:
                raise
            body_error = "bounded body read stopped early"
        except exceptions.SSLError as exc:
            if status == 200:
                raise TlsFailure("TLS failure while reading the body: %s" % exc) from exc
            body_error = "TLS failure while reading the body: %s" % exc
        except exceptions.Timeout as exc:
            if status == 200:
                raise TimeoutError("body read timed out: %s" % exc) from exc
            body_error = "body read timed out: %s" % exc
        except exceptions.ConnectionError as exc:
            if status == 200:
                raise ConnectionError("body read failed: %s" % exc) from exc
            body_error = "body read failed: %s" % exc
        finally:
            with contextlib.suppress(Exception):
                response.close()

        self.total_bytes += len(body)
        if self.total_bytes > self.max_total_bytes:
            raise DeadlineExceeded("total captured bytes exceeded the %d-byte run budget"
                                   % self.max_total_bytes)
        return self._build(response, url, body, started, body_error=body_error)


# ------------------------------------------------------------------------- the runner
class SmokeRun:
    def __init__(self, run_id, *, out_root=None, evidence_root=EVIDENCE_ROOT,
                 clock=time.monotonic, sleeper=time.sleep,
                 wall_clock_cap=WALL_CLOCK_CAP_SEC, now=utc_now):
        if not re.fullmatch(r"\d{8}T\d{6}Z", str(run_id)):
            raise SmokeError("run_id must look like YYYYMMDDTHHMMSSZ, got %r" % (run_id,))
        self.run_id = str(run_id)
        self.out_root = Path(out_root) if out_root else (TMP_ROOT / ("m2b_smoke_%s" % run_id))
        self.evidence_dir = Path(evidence_root) / ("evidence_%s" % run_id)
        self.clock = clock
        self.sleeper = sleeper
        self.wall_clock_cap = float(wall_clock_cap)
        self.now = now
        self.deadline = None
        self.requests_log = []
        #: R1: the evidence owner. Created by `capture()`; every write goes through it.
        self.store = None
        self.routine = None
        self.routine_sha256 = dec.HK_JS_DECODE_SHA256
        self.racer_factory = None
        self._live = None
        self._timed = None
        self._paced = None
        self._state = {"run_status": "completed", "abort_reason": None,
                       "consecutive_failed_jobs": 0}
        self._started_utc = None
        self._data = {}
        self._last_manifest = None

    @property
    def cancelled(self):
        """True once the evidence tree is sealed: every later write is refused."""
        return bool(self.store is not None and self.store.sealed)

    @property
    def attempts(self):
        """One entry per ACTUAL wire attempt, retries included (R3)."""
        timed = getattr(self, "_timed", None)
        return list(timed.log) if timed is not None else []

    def _on_attempt(self, entry, phase):
        """Persist the manifest at the attempt boundary - start and end of every attempt."""
        self.store.mutate(lambda: self._flush(self._state, self._started_utc, self._data))

    def _paced_sleeper(self, seconds):
        """The sleeper handed to the unchanged M2a transport for pacing and backoff.

        M2a classifies an attempt AFTER the injected callable returns, i.e. after the
        end-of-attempt flush, so the on-disk evidence of a just-finished attempt would
        stay unclassified for the whole backoff wait. Flushing here, before any wait,
        persists that classification first. Refused flushes (closed tree) are ignored:
        the attempt itself was already refused or the tree is final.
        """
        if self.store is not None and not self.store.closed_for_workers():
            with contextlib.suppress(EvidenceSealed):
                self.store.mutate(lambda: self._flush(self._state, self._started_utc,
                                                      self._data))
        self.sleeper(seconds)

    # ------------------------------------------------------------------ plan mode
    def plan(self, *, process_lister=default_process_lister, requests_module=None):
        """Write nothing, contact nothing, print everything armed mode would do."""
        constants = None
        with contextlib.suppress(Exception):
            constants = adapter_constants()
        planned = expected_requests(constants)
        checks, data = preflight(out_root=self.out_root, evidence_dir=self.evidence_dir,
                                 probe_reference=False, process_lister=process_lister,
                                 requests_module=requests_module)
        return {
            "mode": "plan",
            "run_id": self.run_id,
            "writes": [],
            "out_root": str(self.out_root),
            "evidence_dir": str(self.evidence_dir),
            "requests": planned,
            "budget": {"nominal_attempts": len(planned), "ceiling": CEILING,
                       "min_interval_sec": MIN_INTERVAL,
                       "connect_timeout_sec": CONNECT_TIMEOUT,
                       "read_timeout_sec": READ_TIMEOUT,
                       "wall_clock_cap_sec": self.wall_clock_cap,
                       "shutdown_grace_sec": SHUTDOWN_GRACE_SEC,
                       "finalize_budget_sec": FINALIZE_BUDGET_SEC,
                       "seal_timeout_sec": SEAL_TIMEOUT_SEC,
                       "max_response_bytes": MAX_RESPONSE_BYTES,
                       "max_total_bytes": MAX_TOTAL_BYTES,
                       "consecutive_failed_jobs_stop": CONSECUTIVE_FAILED_JOBS_STOP},
            "preflight": [c.as_dict() for c in checks],
            "preflight_ok": all(c.status == "PASS" for c in checks),
            "environment": {k: data.get(k) for k in
                            ("git", "adapter_constants", "tls", "hk_js_decode_sha256",
                             "process_inventory_size")},
            "reference_plan": REFERENCE_RULES,
        }

    # ----------------------------------------------------------------- armed mode
    def capture(self, *, session, requests_module, process_lister=default_process_lister,
                transport_factory=None, supervise_jobs=True,
                poll_sec=SUPERVISE_POLL_SEC, reference_reader=None, deadline=None,
                routine=None, routine_sha256=dec.HK_JS_DECODE_SHA256,
                racer_factory=None):
        """Issue the five requests under every control. Boundary 1b only.

        `deadline` lets the pipeline hand capture the SAME deadline the later phases use,
        so an initial run cannot silently reset its budget between phases. Omitting it
        starts a fresh `wall_clock_cap` budget, which is what a bare capture wants.
        """
        checks, data = preflight(out_root=self.out_root, evidence_dir=self.evidence_dir,
                                 session=session, probe_reference=True,
                                 process_lister=process_lister,
                                 requests_module=requests_module,
                                 reference_reader=reference_reader)
        failed = [c for c in checks if c.status != "PASS"]
        if failed:
            raise PreflightError("pre-flight failed before any request: %s"
                                 % ", ".join("%s %s" % (c.id, c.detail) for c in failed))

        self.store = EvidenceStore(self.out_root)
        if self.store.pending_root.exists():
            raise PreflightError("staging directory already exists: %s"
                                 % self.store.pending_root)
        self.out_root.mkdir(parents=True, exist_ok=False)
        (self.out_root / "raw").mkdir()
        (self.out_root / "reference").mkdir()
        self.store.owner_write(
            "reference/reference_extract.json",
            json.dumps(data["reference_extract"], indent=2,
                       ensure_ascii=False).encode("utf-8"))

        self.deadline = deadline or Deadline(self.wall_clock_cap, clock=self.clock,
                                             label="smoke run")
        self.routine, self.routine_sha256 = routine, routine_sha256
        self.racer_factory = racer_factory
        live = (transport_factory or LiveSinaTransport)(
            session, deadline=self.deadline, requests_module=requests_module,
            clock=self.clock)
        self._live = live
        timed = TimedTransport(live, clock=self.clock, now=self.now, store=self.store,
                               on_attempt=self._on_attempt)
        self._timed = timed
        paced = tp.PacedTransport(timed, clock=self.clock, sleeper=self._paced_sleeper,
                                  min_interval=MIN_INTERVAL, ceiling=CEILING,
                                  connect_timeout=CONNECT_TIMEOUT,
                                  read_timeout=READ_TIMEOUT, session=session)
        self._paced = paced

        planned = expected_requests(data.get("adapter_constants"))
        by_job = {}
        for item in planned:
            by_job.setdefault(item["job"], []).append(item)

        state = {"run_status": "completed", "abort_reason": None,
                 "consecutive_failed_jobs": 0}
        started_utc = self.now()
        self._state, self._started_utc, self._data = state, started_utc, data

        def close_unissued(items, reason, scope):
            # Owner-side mutation: bounded, because an abandoned worker may hold the
            # evidence lock inside a publication that is still in flight. A request whose
            # worker was abandoned after its attempt STARTED is recorded as aborted and
            # abandoned - its response, if any, was never published - not as skipped:
            # the attempt evidence exists and must reconcile.
            def then():
                # Workers are refused from THIS critical section on - before the
                # abandonment record exists and before the seal - so a worker that
                # wakes in between can neither publish beside the abandonment record
                # nor issue a further attempt.
                self.store.refuse_workers(reason)
                for item in items:
                    if any(r["index"] == item["index"] for r in self.requests_log):
                        continue
                    started = [a for a in self.attempts
                               if a.get("request_index") == item["index"]]
                    if started:
                        self._record(item, {
                            "outcome": "aborted", "status": None, "abandoned": True,
                            "reason": "the run aborted while this request's worker was "
                                      "in flight; its response, if any, was never "
                                      "published"})
                    else:
                        self._record_skip(item, reason, scope)
                return self._flush(state, started_utc, data)
            return self.store.mutate(then, timeout=SEAL_TIMEOUT_SEC)

        for job in JOBS:
            if state["abort_reason"]:
                close_unissued(by_job[job["job"]], "run already aborted", out.SKIP_RUN_GLOBAL)
                continue

            def run_job(items=by_job[job["job"]]):
                return self._run_job(items, paced)

            try:
                if supervise_jobs:
                    outcome = supervise(run_job, deadline=self.deadline, poll_sec=poll_sec,
                                        name="m2b-%s" % job["job"])
                else:
                    outcome = run_job()
            except tp.RunAborted as exc:
                state["abort_reason"] = str(exc)
                state["run_status"] = "aborted"
                close_unissued(by_job[job["job"]], "run aborted", out.SKIP_RUN_GLOBAL)
                continue

            if outcome["job_ok"]:
                state["consecutive_failed_jobs"] = 0
            else:
                state["consecutive_failed_jobs"] += 1
                if state["consecutive_failed_jobs"] >= CONSECUTIVE_FAILED_JOBS_STOP:
                    state["abort_reason"] = (
                        "%d consecutive failed jobs; stopping before any further request"
                        % state["consecutive_failed_jobs"])
                    state["run_status"] = "aborted"
            self.store.mutate(lambda: self._flush(state, started_utc, data),
                              timeout=SEAL_TIMEOUT_SEC)

        after = protected_fingerprints()
        invalidating, reported = compare_fingerprints(data["protected_before"], after)
        # The final manifest write and the seal are ONE bounded critical section: no
        # worker publication can interleave with it, and none can follow it.
        sealed, manifest = self.store.seal(
            "capture finalized",
            lambda: self._flush(state, started_utc, data, after=after,
                                invalidating=invalidating, reported=reported))
        if not sealed:
            raise EvidenceUnsealable(
                "could not seal the evidence tree within %.0fs: a worker still holds the "
                "evidence lock. The tree at %s is partial and UNSEALED; nothing more is "
                "written into it" % (SEAL_TIMEOUT_SEC, self.out_root))
        return manifest


    # ------------------------------------------------- the one bounded pipeline (S1)
    def run_pipeline(self, *, session, requests_module,
                     process_lister=default_process_lister, reference_reader=None,
                     transport_factory=None, supervise_jobs=True, routine=None,
                     routine_sha256=dec.HK_JS_DECODE_SHA256, racer_factory=None,
                     replay_fn=None, keep_raw=True, plan_text=None):
        """capture -> decode -> checks -> report -> retention, under ONE deadline.

        The first delivery had these as separate functions and an armed CLI that only
        captured and printed a status line. Existing separately is not the same as being
        a bounded workflow, so this is the single entry point the armed run uses.

        Budgets, stated rather than implied:

        * ONE `wall_clock_cap` deadline starts here and covers capture, decoding, the
          checks and the installed-adapter replay. Phases do not silently reset it.
        * Finalization - writing `checks.json` / `REPORT.md` and moving the evidence out
          of `tmp/` - gets its own explicitly declared `FINALIZE_BUDGET_SEC`, because
          evidence must still be written after the run deadline has expired. It is
          bounded, not unbounded.
        * A separate offline replay (`smoke_checks.replay`) gets a fresh explicit budget
          of its own; it is a different run.
        """
        import smoke_checks as chk

        deadline = Deadline(self.wall_clock_cap, clock=self.clock, label="smoke run")
        record = {"run_id": self.run_id, "phase": "capture", "error": None,
                  "capability": None, "run_status": None, "finalize": None}
        manifest, unsealed = None, False
        try:
            manifest = self.capture(
                session=session, requests_module=requests_module,
                process_lister=process_lister, transport_factory=transport_factory,
                supervise_jobs=supervise_jobs, reference_reader=reference_reader,
                deadline=deadline, routine=routine, routine_sha256=routine_sha256,
                racer_factory=racer_factory)
        except PreflightError:
            raise
        except EvidenceUnsealable as exc:
            record["error"] = "capture: %s" % exc
            manifest, unsealed = self._last_manifest, True
        except BaseException as exc:                  # noqa: BLE001 - reported, not lost
            record["error"] = "capture: %s: %s" % (type(exc).__name__, exc)
            manifest = self._last_manifest
        # The finalization allowance starts the moment capture is over; every bounded
        # wait from here on is charged to it.
        finalize = Deadline(FINALIZE_BUDGET_SEC, clock=self.clock, grace_sec=0.0,
                            label="finalization")
        if self.store is not None and not self.store.sealed:
            # capture raised before it could seal. Seal now - bounded - before any other
            # write; the last flushed manifest stands, nothing is added to it. A tree
            # already force-sealed by a failed owner mutation returns at once.
            sealed, _ = self.store.seal("sealed after a capture failure", lambda: None,
                                        timeout=min(SEAL_TIMEOUT_SEC,
                                                    max(finalize.remaining(), 0.1)))
            unsealed = unsealed or not sealed
        if manifest is None:
            raise SmokeError("capture produced no manifest; nothing to finalize")
        record["run_status"] = manifest.get("run_status")
        if unsealed:
            # A worker still holds the evidence lock inside a publication that was in
            # flight: the tree may still change once. Nothing is written into it, it is
            # not retained, and the run is reported incomplete with its location.
            record.update(
                phase="incomplete_finalization",
                capability=out.CAPABILITY_INCONCLUSIVE,
                cleanup=None,
                finalize=dict(finalize.snapshot(),
                              status="unsealed", step="seal", partial=True,
                              steps_done=[], error=record["error"],
                              evidence_location=[str(self.out_root)],
                              note=("a capture worker held the evidence lock past the "
                                    "%.0fs seal timeout; the tree is partial, unsealed "
                                    "and NOT retained; no further write was made"
                                    % SEAL_TIMEOUT_SEC)))
            record["deadline"] = deadline.snapshot()
            return record

        record["phase"] = "checks"
        result = None
        try:
            extract = json.loads((self.out_root / "reference" / "reference_extract.json")
                                 .read_text(encoding="utf-8"))
            result = chk.run_checks(manifest=manifest, raw_dir=self.out_root / "raw",
                                    reference_extract=extract, deadline=deadline,
                                    routine=routine, routine_sha256=routine_sha256,
                                    racer_factory=racer_factory,
                                    **({"replay_fn": replay_fn} if replay_fn else {}))
        except DeadlineExceeded as exc:
            record["error"] = "checks: %s" % exc
        except BaseException as exc:                  # noqa: BLE001
            record["error"] = "checks: %s: %s" % (type(exc).__name__, exc)

        # ---- finalization: bounded step by step, never reported done after expiry ----
        record["phase"] = "finalize"
        if result is not None:
            record["capability"] = result["deterministic"]["verdicts"]["capability"]
            checks_text = json.dumps(result, indent=2, ensure_ascii=False, default=str)
            report_text = chk.render_report(result, manifest)
        else:
            record["capability"] = out.CAPABILITY_INCONCLUSIVE
            checks_text = None
            report_text = (
                "# M2b smoke report\n\nrun_id: %s\nrun status: %s\n\nThe checks did not "
                "complete: %s\n\nCapability verdict: INCONCLUSIVE. The captured evidence "
                "below is preserved.\n"
                % (self.run_id, manifest.get("run_status"), record["error"]))
        token = self.store.issue_token()
        progress = {"renamed": False}

        def write(name, text):
            return lambda: self.store.owner_write(name, text.encode("utf-8"), token=token)

        steps = []
        if plan_text:
            steps.append(("plan", write("plan.txt", plan_text)))
        if checks_text is not None:
            steps.append(("checks", write("checks.json", checks_text)))
        steps.append(("report", write("REPORT.md", report_text)))
        steps.append(("retain", lambda: self.cleanup(keep_raw=keep_raw, token=token,
                                                     progress=progress)))
        outcome = self._finalize(steps, finalize, token, progress)
        record["finalize"] = outcome
        record["cleanup"] = outcome.get("cleanup")
        record["deadline"] = deadline.snapshot()
        record["phase"] = ("done" if outcome["status"] == "complete"
                           else "incomplete_finalization")
        return record

    def _finalize(self, steps, finalize, token, progress):
        """Run every finalization step under the finalization deadline, supervised (R2).

        A step that outlives the deadline is ABANDONED: its token is revoked first, so
        it can no longer write into or clean up the retained tree, and the outcome names
        every location the evidence may be in. A step that RETURNS after the deadline is
        an overrun: the evidence is complete, but the run is still not reported done and
        the exit status is non-zero. A negative remaining budget is never success.
        """
        outcome = {"status": "complete", "step": None, "partial": False,
                   "evidence_location": [], "cleanup": None, "steps_done": [],
                   "error": None}
        try:
            for name, step in steps:
                if finalize.expired():
                    # A previous step RETURNED after the budget: an overrun, not an
                    # abandonment - no worker exists, and this step never starts.
                    outcome.update(status="overrun", step=name, partial=True,
                                   error="the finalization budget was spent before step "
                                         "%r started" % name)
                    break
                outcome["step"] = name
                value = supervise(step, deadline=finalize, poll_sec=SUPERVISE_POLL_SEC,
                                  name="m2b-finalize-%s" % name)
                outcome["steps_done"].append(name)
                if name == "retain":
                    outcome["cleanup"] = value
            else:
                if finalize.expired():
                    outcome.update(status="overrun")
        except DeadlineExceeded as exc:
            outcome.update(status="abandoned", partial=True, error=str(exc))
        except Exception as exc:                      # noqa: BLE001 - reported, not lost
            outcome.update(status="failed", partial=True,
                           error="%s: %s" % (type(exc).__name__, exc))
        finally:
            # Revoked under the lock: a worker blocked inside one guarded operation
            # completes exactly that one; nothing it does afterwards is authorized.
            self.store.revoke(token, timeout=min(SEAL_TIMEOUT_SEC,
                                                 max(finalize.remaining(), 0.1)))
        outcome.update(finalize.snapshot())
        if progress.get("renamed"):
            outcome["evidence_location"] = [str(self.evidence_dir)]
        elif outcome["status"] == "abandoned" and outcome["step"] == "retain":
            outcome["evidence_location"] = [str(self.out_root), str(self.evidence_dir)]
        else:
            outcome["evidence_location"] = [str(self.out_root)]
        outcome["note"] = {
            "complete": "finalization completed within its budget",
            "overrun": ("finalization returned %.1fs AFTER its %.0fs budget; the evidence "
                        "is complete but the run is reported INCOMPLETE, not done"
                        % (-finalize.remaining(), finalize.budget)),
            "abandoned": ("finalization step %r outlived its %.0fs budget and was "
                          "abandoned; its token is revoked, so at most the single guarded "
                          "operation it was blocked in completes and nothing after it is "
                          "authorized. If it was the retention rename, the tree is at "
                          "exactly ONE of the listed locations, unmodified either way"
                          % (outcome["step"], finalize.budget)),
            "failed": ("finalization step %r failed; partial evidence is preserved at "
                       "the listed location" % outcome["step"]),
        }[outcome["status"]]
        return outcome

    # ---------------------------------------------------------------- Section 8
    MOVED = ("plan.txt", "capture_manifest.json", "checks.json", "REPORT.md")
    MOVED_DIRS = ("raw", "reference", "decoded")

    def cleanup(self, *, keep_raw=True, token=None, progress=None):
        """Retain the evidence tree and delete the temporary root - as ONE rename.

        The tree is not moved file by file. `REPORT.md` receives the output-tree hash
        listing, the raw bodies are dropped when `keep_raw=False` (the user's alternative
        at 1b: only their SHA-256 hashes, already inside REPORT.md, are kept), and then
        the whole output root is renamed to the evidence directory in one operation, so
        retention can never be half done. Staged bytes never lived inside the tree.

        Every write here is owner-only: the owner thread, or a finalization token the
        owner revokes when it abandons a blocked step.
        """
        import shutil

        progress = progress if progress is not None else {}
        if self.store is None:
            self.store = EvidenceStore(self.out_root)
            self.store.sealed, self.store.seal_reason = True, "cleanup of a bare tree"
        if not self.out_root.exists():
            raise SmokeError("nothing to clean up: %s does not exist" % self.out_root)
        if self.evidence_dir.exists():
            raise SmokeError("refusing to overwrite an existing evidence directory: %s"
                             % self.evidence_dir)
        digests = {}
        for path in sorted(self.out_root.rglob("*")):
            if path.is_file():
                digests[path.relative_to(self.out_root).as_posix()] = hashlib.sha256(
                    path.read_bytes()).hexdigest()
        report = self.out_root / "REPORT.md"
        if report.exists():
            listing = "\n".join("- `%s` `%s`" % (name, digest)
                                for name, digest in sorted(digests.items()))
            self.store.owner_write(
                "REPORT.md",
                (report.read_text(encoding="utf-8")
                 + "\n\n## Output tree SHA-256\n\n" + listing + "\n").encode("utf-8"),
                token=token)
        detached = None
        if not keep_raw and (self.out_root / "raw").exists():
            # Never deleted INSIDE the tree: detached by one guarded rename and removed
            # outside it, so an abandoned step cannot keep deleting retained bodies.
            detached = self.store.owner_detach("raw", token=token)
        self.evidence_dir.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.store.owner_rename(self.out_root, self.evidence_dir, token=token)
        except OSError as exc:
            # No cross-device fallback: a copy-then-delete is not one rename and could
            # leave the tree duplicated. The step fails with the tree intact.
            raise SmokeError(
                "retention is one rename, which requires the evidence directory to be on "
                "the same volume as %s (%s: %s); the tree is intact at %s"
                % (TMP_ROOT, type(exc).__name__, exc, self.out_root)) from exc
        progress["renamed"] = True
        self.store.relocate(self.evidence_dir, token=token)
        if detached is not None:
            shutil.rmtree(detached, ignore_errors=True)
        pending = self.store.discard_pending(token=token)
        return {"evidence_dir": str(self.evidence_dir), "removed": str(self.out_root),
                "files": sorted(digests), "raw_retained": keep_raw, "pending": pending}

    # -------------------------------------------------------------------- internals
    def _publish_failure(self, item, extra, capture):
        """Record a failed/aborted request, with its bounded body if one exists.

        `PacedTransport` raises on a non-200 before the runner sees a response, so a
        failed attempt used to leave no body or header record at all. The live adapter
        keeps its last `CapturedResponse`, which is what this reads. Body, record and
        manifest are published as ONE critical section, or refused as one (R1).
        """
        extra = dict(extra)
        if capture is not None:
            extra.update({"served_url": redact_url(capture.url),
                          "headers": redact_headers(capture.headers),
                          "bytes": len(capture.content),
                          "encoding": capture.encoding,
                          "body_error": capture.body_error})

        def then():
            record = self._record(item, extra)
            self._flush(self._state, self._started_utc, self._data)
            return record

        if capture is not None and capture.content:
            name = "failed_%s" % item["filename"]
            staged = self.store.stage(name, capture.content)
            extra["raw_file"] = name
            extra["body_sha256"] = hashlib.sha256(capture.content).hexdigest()
            return self.store.publish("raw/" + name, staged, then)
        return self.store.mutate(then)

    def _skip_rest(self, items, reason, scope):
        if not items:
            return None

        def then():
            for later in items:
                # Idempotent: a request that already carries a terminal record is left
                # alone. A second record for one request is never legal.
                if any(r["index"] == later["index"] for r in self.requests_log):
                    continue
                self._record_skip(later, reason, scope)
            return self._flush(self._state, self._started_utc, self._data)

        return self.store.mutate(then)

    def _classify(self, item, content, encoding):
        """The SAME outcome-table classification the checker will apply, applied NOW."""
        self.deadline.check("classify-%s" % item["filename"])

        def work():
            job = next(j for j in JOBS if j["job"] == item["job"])
            return out.classify_payload(
                content, item["kind"], encoding=encoding, routine=self.routine,
                routine_sha256=self.routine_sha256, racer_factory=self.racer_factory,
                expected_symbol=item["symbol"],
                instrument_class=job["instrument_class"])

        return supervise(work, deadline=self.deadline, poll_sec=SUPERVISE_POLL_SEC,
                         name="m2b-classify-%02d" % item["index"])

    def _run_job(self, items, paced):
        """One symbol job, with the shared outcome table deciding continuation.

        Capture used to treat every HTTP 200 as success and issue the job's next request
        regardless of what came back, so HTML or an empty body still produced a
        `completed` five-request run that the checker then contradicted. The payload is
        now classified BEFORE the dependent request is issued, by the same table.
        """
        for position, item in enumerate(items):
            self.deadline.check("before-%s" % item["filename"])
            self._timed.current_request = item["index"]
            try:
                response = paced.get_with_retries(item["url"], source=SOURCE_KEY)
            except tp.RunAborted:
                # A vendor stop latched from the headers aborts the run through
                # RunAborted; the record keeps the status the live adapter saw and the
                # transport's own classification, so it stays a vendor stop downstream.
                capture = getattr(self._live, "last_capture", None)
                self._publish_failure(
                    item, {"outcome": "aborted",
                           "status": getattr(capture, "status", None),
                           "transport_outcome": (paced.attempts[-1].outcome
                                                 if paced.attempts else None)},
                    capture)
                self._skip_rest(items[position + 1:], "the run aborted during this job",
                                out.SKIP_RUN_GLOBAL)
                raise
            except tp.TransportError as exc:
                # `transport_outcome` is the unchanged M2a transport's OWN classification
                # of the last attempt. The checks read it instead of parsing the message,
                # so a TLS failure can never be mistaken for a transient network fault.
                last = paced.attempts[-1].outcome if paced.attempts else None
                failure_kind = "tls" if isinstance(exc.__cause__, TlsFailure) else None
                self._publish_failure(
                    item, {"outcome": "failed", "status": exc.status, "error": str(exc),
                           "transport_outcome": last, "failure_kind": failure_kind,
                           "retryable": bool(exc.retryable)},
                    getattr(self._live, "last_capture", None))
                self._skip_rest(items[position + 1:],
                                "the job's earlier request failed; the documented "
                                "failed-job rule does not issue this one",
                                out.SKIP_JOB_LOCAL)
                return {"job_ok": False}

            # R1: stage OUTSIDE the tree, then publish body + record + manifest as one
            # critical section. Classification follows; a worker abandoned inside it
            # leaves a body WITH its record (payload state pending), never an orphan.
            staged = self.store.stage(item["filename"], response.content)
            extra = {
                "outcome": "ok", "status": response.status,
                "served_url": redact_url(response.url),
                "bytes": len(response.content),
                "body_sha256": hashlib.sha256(response.content).hexdigest(),
                "text_sha256": dec.sha256_text(response.text),
                "encoding": response.encoding,
                "apparent_encoding": response.apparent_encoding,
                "headers": redact_headers(response.headers),
                "elapsed_sec": response.elapsed_sec,
                "raw_file": item["filename"],
                "payload_state": None,
                "payload_reason": "classification pending",
                "request_result": None,
            }

            def published():
                record = self._record(item, extra)
                self._flush(self._state, self._started_utc, self._data)
                return record

            record = self.store.publish("raw/" + item["filename"], staged, published)
            state, _decoded, reason = self._classify(item, response.content,
                                                     response.encoding)
            row = out.lookup_outcome("ok", state)

            def classified():
                record.update(payload_state=state, payload_reason=reason,
                              request_result=row["request_result"])
                return self._flush(self._state, self._started_utc, self._data)

            self.store.mutate(classified)
            if row["skip_remaining"]:
                self._skip_rest(items[position + 1:],
                                "the outcome table classified this job's payload as %r; "
                                "the dependent request is not issued" % state,
                                out.SKIP_JOB_LOCAL)
                return {"job_ok": False}
        return {"job_ok": True}

    def _late(self):
        """A write after the seal from OUTSIDE a critical section already in progress."""
        return self.cancelled and not (self.store is not None
                                       and self.store.in_critical_section())

    def _record(self, item, extra, started_mono=None, started_utc=None):
        if self._late():
            raise EvidenceSealed("the run is finalized; refusing a late record for "
                                 "request %d" % item["index"])
        if any(r["index"] == item["index"] for r in self.requests_log):
            raise EvidenceSealed("request %d already has its terminal record; a second "
                                 "record is never legal" % item["index"])
        positions = [n for n, a in enumerate(self.attempts)
                     if a.get("request_index") == item["index"]]
        record = {"index": item["index"], "job": item["job"], "symbol": item["symbol"],
                  "kind": item["kind"], "requested_url": item["url"],
                  "source_key": SOURCE_KEY,
                  "started_at_monotonic": round(started_mono if started_mono is not None
                                                else self.clock(), 6),
                  "started_at_utc": started_utc or self.now(),
                  # R3: the request is bound to its actual attempts, by position.
                  "attempt_count": len(positions),
                  "attempt_positions": positions}
        record.update(extra)
        self.requests_log.append(record)
        return record

    def _record_skip(self, item, reason, scope=out.SKIP_JOB_LOCAL):
        return self._record(item, {"outcome": "skipped", "status": None,
                                   "reason": reason, "skip_scope": scope})

    def _flush(self, state, started_utc, data, after=None, invalidating=None,
               reported=None):
        """Write the manifest at every attempt boundary and every record change.

        Called only inside the store's critical sections, so it can never interleave
        with the seal. The attempt list is the runner's OWN boundary log - persisted at
        the start and end of each wire attempt - merged with the unchanged M2a
        transport's classification of the same attempt once that exists.
        """
        if self._late():
            raise EvidenceSealed(
                "the run is finalized; refusing a late manifest write. A worker that "
                "woke after the abort must not race finalization or cleanup.")
        paced_attempts = list(getattr(getattr(self, "_paced", None), "attempts", []))
        attempts = []
        for index, entry in enumerate(self.attempts):
            entry = dict(entry)
            if index < len(paced_attempts):
                entry["transport_outcome"] = paced_attempts[index].outcome
                entry["source"] = paced_attempts[index].source
                entry["waited_sec"] = round(paced_attempts[index].waited, 3)
            attempts.append(entry)
        stamped = all(a.get("started_at_monotonic") is not None
                      and a.get("started_at_utc") for a in attempts)
        manifest = {
            "schema": "m2b.capture_manifest.v3",
            "run_id": self.run_id,
            "run_mode": "live_smoke",
            "started_at_utc": started_utc,
            "finished_at_utc": self.now(),
            "run_status": state["run_status"],
            "abort_reason": state["abort_reason"],
            "requests": list(self.requests_log),
            "attempts": attempts,
            # The unchanged M2a transport's own count: the checks reconcile it with the
            # attempt records so a truncated list cannot pass.
            "attempt_count_transport": len(paced_attempts),
            "attempt_timestamps_complete": stamped,
            "deadline": self.deadline.snapshot() if self.deadline else None,
            "environment": {k: data.get(k) for k in
                            ("git", "adapter_constants", "tls", "hk_js_decode_sha256",
                             "process_inventory_size")},
            "protected_before": data.get("protected_before"),
            "reference_extract_sha256": data.get("reference_extract", {}).get(
                "content_sha256"),
        }
        if after is not None:
            manifest["protected_after"] = after
            manifest["invalidating_changes"] = invalidating or []
            manifest["reported_changes"] = reported or []
            manifest["run_valid"] = not invalidating
        _atomic_write(self.out_root / "capture_manifest.json",
                      json.dumps(manifest, indent=2, ensure_ascii=False).encode("utf-8"))
        self._last_manifest = manifest
        return manifest


# ------------------------------------------------------------------------------- CLI
def render_plan(plan):
    lines = []
    add = lines.append
    add("M2b smoke - PLAN (writes nothing, opens no database, contacts no host)")
    add("run_id                : %s" % plan["run_id"])
    add("would create          : %s" % plan["out_root"])
    add("would create at cleanup: %s" % plan["evidence_dir"])
    add("writes in this mode   : none")
    add("")
    add("Requests, in job order, derived from the INSTALLED adapter constants:")
    for item in plan["requests"]:
        add("  %02d %-10s %-18s %s" % (item["index"], item["job"], item["kind"],
                                       item["url"]))
    add("")
    budget = plan["budget"]
    add("Budget and controls:")
    for key in sorted(budget):
        add("  %-30s %s" % (key, budget[key]))
    add("")
    add("Pre-flight:")
    for check in plan["preflight"]:
        add("  %-3s %-7s %s" % (check["id"], check["status"], check["detail"]))
    add("")
    tls = (plan["environment"].get("tls") or {})
    add("TLS / proxy:")
    add("  ca_bundle        %s" % tls.get("ca_bundle"))
    add("  ca_bundle_sha256 %s" % tls.get("ca_bundle_sha256"))
    add("  certifi          %s" % tls.get("certifi_version"))
    add("  env overrides    %s" % tls.get("env_overrides"))
    add("  effective proxy  %s" % tls.get("proxies"))
    add("")
    add("Reference extract (S3), frozen at capture time and used by every check:")
    for key in sorted(plan["reference_plan"]):
        add("  %-24s %s" % (key, plan["reference_plan"][key]))
    add("")
    add("PLAN RESULT: %s" % ("pre-flight all PASS" if plan["preflight_ok"]
                             else "PRE-FLIGHT NOT CLEAN - armed mode would refuse"))
    return "\n".join(lines)


def exit_code_for(record):
    """0 only for a completed run, an unqualified or BJ-qualified PASS, and a
    finalization that completed within its budget. Everything else - an overrun that
    returned, an abandoned step, an unsealed tree - is 1, so a negative remaining
    finalization budget can never look like success to a caller."""
    finalize = record.get("finalize") or {}
    ok = (record.get("phase") == "done"
          and record.get("run_status") == "completed"
          and record.get("capability") in (out.CAPABILITY_PASS, out.CAPABILITY_PASS_BJ)
          and finalize.get("status") == "complete")
    return 0 if ok else 1


def build_parser():
    parser = argparse.ArgumentParser(
        description="M2b bounded three-symbol real-source capture (default: plan only)")
    parser.add_argument("--plan", action="store_true", default=True,
                        help="print the plan; write nothing, open nothing (default)")
    parser.add_argument("--i-authorize-live-calls", dest="run_id", default=None,
                        help="ARMED: issue the five requests for this run_id "
                             "(YYYYMMDDTHHMMSSZ). Boundary 1b only.")
    parser.add_argument("--json", action="store_true",
                        help="emit the plan as JSON instead of text")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.run_id:
        run = SmokeRun(args.run_id)
        requests_module = _import_requests()
        if requests_module is None:
            print("requests is not importable; refusing to arm", file=sys.stderr)
            return 2
        session = requests_module.Session()
        plan_text = render_plan(run.plan(requests_module=requests_module))
        try:
            # ONE bounded workflow: capture, decode, check, report, retain.
            record = run.run_pipeline(session=session, requests_module=requests_module,
                                      plan_text=plan_text)
        except PreflightError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        finally:
            with contextlib.suppress(Exception):
                session.close()
        print(json.dumps(record, indent=2, ensure_ascii=False, default=str))
        return exit_code_for(record)

    plan = SmokeRun(_dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")).plan()
    print(json.dumps(plan, indent=2, ensure_ascii=False) if args.json else render_plan(plan))
    return 0 if plan["preflight_ok"] else 1


if __name__ == "__main__":                            # pragma: no cover
    raise SystemExit(main())
