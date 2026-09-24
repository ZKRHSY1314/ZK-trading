"""M2a R1/R3/R4 - the pilot runner: decoder-bound, honest, failure-safe.

Offline by default. `plan()` writes nothing; `collect()` refuses unless explicitly armed
with a `PacedTransport`, and the live transport refuses to run at all.

What the acceptance review broke, and what changed
--------------------------------------------------
R1  The runner requested the expected URLs, kept only `response.url`, threw the BODY
    away, and took its rows from an independent `fetcher(symbol, klass)` callback. With
    every response set to `<html>NOT MARKET DATA</html>` and the callback returning a
    complete grid, the run reported `completed`, `promoted=True` and wrote 45,935 rows
    per view. The callback is GONE. Rows are decoded from the captured bodies by a pure
    decoder, and there is no second data path.

R3  52 consecutive 404 jobs returned `completed`/`promoted=True` with no stop. A
    `RunAborted` raised by the transport was caught generically and retried three times.
    There is now a consecutive-failure stop with reset-on-success, and the rollup is
    honest: anything less than every job succeeding is not `completed` and never
    publishes.

R4  The guard accepted trading and history resolving to the SAME destination, and
    accepted one destination equal to the other's `.partial`. Two sequential
    `os.replace` calls left new-trading + old-history when the second raised. Each run
    now writes into a FRESH run directory that must not already exist, and publication is
    a single pointer write performed only after both views are written AND acceptance has
    succeeded. The previous pair stays intact and referenced until the pointer moves.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import sys
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
M1 = HERE.parent / "_m1_closure"
sys.path.insert(0, str(M1))

from coverage_gap_generator import sessions_between  # noqa: E402
from staging_gate import load_manifest  # noqa: E402

import contextlib
import io as _io

import staging_gate  # noqa: E402

import acceptance as acc  # noqa: E402
import decoder  # noqa: E402
import provenance as prov  # noqa: E402
from transport import PacedTransport, RunAborted, TransportError  # noqa: E402

RESEARCH_START, RESEARCH_END = "2023-09-04", "2026-09-04"
WARMUP_DEPTH = 250
CONSECUTIVE_FAILURE_STOP = 20
POINTER = "CURRENT.json"

#: Fixture runs are marked as fixture runs. This value must never appear in, or be
#: mistaken for, live provenance.
FIXTURE_MODE = "offline_synthetic_fixture"

TRADING_DDL = """
CREATE TABLE IF NOT EXISTS daily_bar_cache (
    symbol TEXT, trade_date TEXT, open REAL, high REAL, low REAL, close REAL,
    volume REAL, amount REAL, source TEXT, quality_status TEXT,
    adjustment_mode TEXT, volume_unit TEXT
);
CREATE TABLE IF NOT EXISTS instruments (symbol TEXT PRIMARY KEY, name TEXT);
CREATE TABLE IF NOT EXISTS ingest_provenance (
    symbol TEXT, instrument_class TEXT, url TEXT, body_sha256 TEXT, schema TEXT,
    declared_basis TEXT, derived_basis TEXT, derived_unit TEXT, run_id TEXT,
    run_mode TEXT, lineage TEXT
);
"""
HISTORY_DDL = """
CREATE TABLE IF NOT EXISTS daily_bars (
    symbol TEXT, trade_date TEXT, adjustment_mode TEXT, open REAL, high REAL, low REAL,
    close REAL, volume REAL, amount REAL, provider TEXT, fetched_at TEXT,
    ingest_run_id INTEGER
);
CREATE TABLE IF NOT EXISTS ingest_runs (
    id INTEGER PRIMARY KEY, provider TEXT, run_id TEXT, run_mode TEXT, started_at TEXT
);
"""


class StagingSafetyError(Exception):
    """A path role would be unsafe. Raised BEFORE any mutation."""


def _resolve(path) -> Path:
    return Path(path).expanduser().resolve()


def _alias(a: Path, b: Path) -> bool:
    if a == b:
        return True
    if os.name == "nt" and str(a).casefold() == str(b).casefold():
        return True
    try:
        if a.exists() and b.exists() and os.path.samefile(a, b):
            return True
    except OSError:
        pass
    return False


def _contained(child: Path, root: Path) -> bool:
    try:
        child.relative_to(root)
        return True
    except ValueError:
        return False


def guard_paths(root, destinations, protected, pointer_roles=None):
    """Validate every role BEFORE any mutation: aliasing, containment, pairwise."""
    root = _resolve(root)
    for role, path in protected:
        p = _resolve(path)
        if _alias(root, p) or _contained(p, root):
            raise StagingSafetyError(
                "staging root %s would contain or alias the protected input --%s (%s)"
                % (root, role, p))

    resolved = {name: _resolve(dest) for name, dest in destinations.items()}
    for name, dest in resolved.items():
        for role, path in protected:
            if _alias(dest, _resolve(path)):
                raise StagingSafetyError(
                    "destination %r resolves to the protected input --%s (%s); refusing"
                    % (name, role, _resolve(path)))
        if not _contained(dest, root):
            raise StagingSafetyError(
                "destination %r resolves to %s, outside the declared staging root %s"
                % (name, dest, root))

    # Pairwise distinctness across BOTH final and temporary roles. Two views writing one
    # file, or one view's final path equal to another's partial, silently destroys data.
    roles = {}
    for name, dest in resolved.items():
        roles["%s.final" % name] = dest
        roles["%s.partial" % name] = dest.with_suffix(dest.suffix + ".partial")
    # The publication roles are real roles. Omitting them let a pre-existing hardlink at
    # CURRENT.json.tmp point at a protected input, which publication then overwrote.
    for extra_name, extra_path in (pointer_roles or {}).items():
        roles[extra_name] = _resolve(extra_path)
    for extra_name, extra_path in (pointer_roles or {}).items():
        target = _resolve(extra_path)
        for role, path in protected:
            if _alias(target, _resolve(path)):
                raise StagingSafetyError(
                    "publication role %r resolves to the protected input --%s (%s); "
                    "refusing" % (extra_name, role, _resolve(path)))
        if not _contained(target, root):
            raise StagingSafetyError(
                "publication role %r resolves to %s, outside the staging root %s"
                % (extra_name, target, root))
    items = sorted(roles.items())
    for i, (name_a, path_a) in enumerate(items):
        for name_b, path_b in items[i + 1:]:
            if _alias(path_a, path_b):
                raise StagingSafetyError(
                    "path role collision: %s and %s both resolve to %s"
                    % (name_a, name_b, path_a))
    return root, resolved


@dataclass
class Budget:
    symbol_jobs: int
    provider_calls: int
    http_attempts_min: int
    http_attempts_ceiling: int
    per_stock_http: int = 2
    per_benchmark_http: int = 1
    notes: list = field(default_factory=list)


#: Publication requires BOTH. A research receipt can never satisfy warm-up collection.
REQUIRED_MODES = ("research", "warmup_collection")


@dataclass(frozen=True)
class ValidationReceipt:
    """Evidence that the unchanged M1 gate ran against ONE candidate in ONE mode.

    Minted only by `PilotRunner.validate_candidate`, which computes the fingerprint
    itself. A receipt carries the mode explicitly so finalization cannot be satisfied by
    two copies of the same one.
    """

    mode: str
    run_id: str
    candidate_fingerprint: str
    manifest_sha: str
    calendar_sha: str
    gate_exit: int
    accepted: bool
    reason: str = ""
    details: dict = field(default_factory=dict)


@dataclass
class JobOutcome:
    symbol: str
    instrument_class: str
    status: str
    rows: int = 0
    reason: str = ""
    provenance: object = None


class PilotRunner:
    def __init__(self, manifest, staging_root, protected, run_id,
                 declared_basis="none", run_mode=FIXTURE_MODE):
        self.manifest = Path(manifest)
        self.root = _resolve(staging_root)
        self.run_id = str(run_id)
        self.run_mode = run_mode
        self.declared_basis = declared_basis
        self.protected = [(r, _resolve(p)) for r, p in protected]
        self.run_dir = self.root / ("run_%s" % self.run_id)
        destinations = {"trading": self.run_dir / "trading.sqlite3",
                        "history": self.run_dir / "history.sqlite3"}
        self.pointer = self.root / POINTER
        # Run-specific, not a fixed shared name, and created exclusively at write time.
        self.pointer_tmp = self.root / ("%s.%s.tmp" % (POINTER, self.run_id))
        self.root, self.destinations = guard_paths(
            self.root, destinations, self.protected,
            pointer_roles={"pointer": self.pointer, "pointer.tmp": self.pointer_tmp})
        self.stocks, self.benchmarks = load_manifest(self.manifest)
        self.sessions = sessions_between("1990-12-19", "2026-12-31")
        before = [s for s in self.sessions if s < RESEARCH_START]
        self.warm = before[-WARMUP_DEPTH:]

    # -------------------------------------------------------------------- dry run
    def plan(self) -> Budget:
        """The default. Writes nothing."""
        stocks, marks = len(self.stocks), len(self.benchmarks)
        minimum = stocks * 2 + marks
        return Budget(
            symbol_jobs=stocks + marks, provider_calls=stocks + marks,
            http_attempts_min=minimum, http_attempts_ceiling=minimum * 3,
            notes=[
                "one combined fetch per symbol covers research AND warm-up: the vendor "
                "URLs take no date parameter and slicing is client-side",
                "a raw stock job issues 2 requests (history + amount); an index job 1",
                "retries are per REQUEST, so a stock job can consume up to 2 x 3 = 6 "
                "of the global ceiling",
                "no fallback source is budgeted: the Tonghuashun adapter caps at 500 "
                "bars. That is a declared limitation, not a source to be developed",
            ])

    # -------------------------------------------------------------------- collect
    def collect(self, transport=None, *, armed=False):
        """Fetch, decode and stage. Returns a COLLECTION result, never a publication.

        There is NO body-override parameter. The previous `responses` mapping was the
        deleted `fetcher` callback wearing a new name: the review made every HTTP response
        `<html>NOT MARKET DATA</html>`, supplied valid envelopes through that mapping, and
        the runner completed 52 jobs and wrote 45,935 rows per view whose recorded body
        hashes matched the replacement, not the response. Bodies now come from exactly one
        place - the captured response object - so a test can only inject data by making the
        injected transport actually return it.
        """
        if not armed:
            raise RunAborted(
                "pilot collection is not armed: M2a is offline-only. plan() is the "
                "default and no network call is performed.")
        if not isinstance(transport, PacedTransport):
            raise RunAborted("collection requires a PacedTransport; unpaced runs are "
                             "not allowed")
        if self.run_dir.exists():
            raise StagingSafetyError(
                "run directory %s already exists; refusing to reuse it. Each run gets a "
                "fresh directory so a previous candidate pair is never overwritten."
                % self.run_dir)
        return self._run(transport)

    def _init_stores(self):
        self.run_dir.mkdir(parents=True, exist_ok=False)
        for name, dest in self.destinations.items():
            conn = sqlite3.connect(dest)
            conn.executescript(TRADING_DDL if name == "trading" else HISTORY_DDL)
            if name == "history":
                conn.execute(
                    "INSERT OR REPLACE INTO ingest_runs VALUES (1,?,?,?,?)",
                    ("sina", self.run_id, self.run_mode, "run:" + self.run_id))
            conn.commit()
            conn.close()

    def _run(self, transport):
        self._init_stores()
        outcomes, consecutive, aborted = [], 0, None
        jobs = ([(e, "stock") for e in self.stocks]
                + [(e, "benchmark") for e in self.benchmarks])
        try:
            for entry, klass in jobs:
                outcome = self._one(entry, klass, transport)
                outcomes.append(outcome)
                if outcome.status == "ok":
                    consecutive = 0
                else:
                    consecutive += 1
                    if consecutive >= CONSECUTIVE_FAILURE_STOP:
                        aborted = ("%d consecutive symbol jobs failed; stopping rather "
                                   "than continuing into a rate-limited or broken source"
                                   % consecutive)
                        break
        except RunAborted as exc:
            aborted = str(exc)

        ok = sum(1 for o in outcomes if o.status == "ok")
        failed = [o for o in outcomes if o.status != "ok"]
        complete = (not aborted and len(outcomes) == len(jobs) and not failed)
        if aborted:
            status = "aborted"
        elif failed:
            status = "completed_with_failures"
        elif len(outcomes) < len(jobs):
            status = "incomplete"
        else:
            status = "collected"

        return {
            "status": status,
            "collection_complete": complete,
            "published": False,             # collection NEVER publishes
            "reason": aborted or "",
            "jobs_expected": len(jobs), "jobs_ok": ok, "jobs_failed": len(failed),
            "outcomes": outcomes, "http_attempts": transport.attempt_count,
            "run_dir": str(self.run_dir), "run_id": self.run_id,
            # Binds this result to the exact bytes on disk, so a candidate that changes
            # after validation cannot be published on the strength of that validation.
            "candidate_fingerprint": (candidate_fingerprint(self.destinations)
                                      if complete else None),
        }

    def _one(self, entry, klass, transport):
        symbol = entry["symbol"]
        try:
            urls = prov.expected_urls(symbol, klass)
        except prov.ProvenanceError as exc:
            return JobOutcome(symbol, klass, "rejected", reason=str(exc))

        captured, observed = [], []
        for url in urls:
            try:
                response = transport.get_with_retries(url, source="sina")
            except RunAborted:
                raise
            except TransportError as exc:
                # A failed primary job is a REPORTED FAILURE. No substitute is invented
                # and no other provider is reached for.
                return JobOutcome(symbol, klass, "failed",
                                  reason="%s: %s" % (url.rsplit("/", 1)[-1][:24], exc))
            # One captured response object is the single source of the body, its hash
            # and its lineage. No override path exists.
            captured.append((response.url, getattr(response, "text", None)))
            observed.append(response.url)

        decoded = []
        for url, body in captured:
            try:
                decoded.append(decoder.decode(body, url=url, expected_symbol=symbol,
                                              kind=klass))
            except decoder.DecodeError as exc:
                return JobOutcome(symbol, klass, "rejected", reason=str(exc))

        try:
            if klass == "stock":
                rows = decoder.merge_stock_responses(decoded[0], decoded[1])
            else:
                rows = [dict(r) for r in decoded[0].rows]
        except decoder.DecodeError as exc:
            return JobOutcome(symbol, klass, "rejected", reason=str(exc))

        bases = {d.declared_basis for d in decoded}
        record = prov.derive(symbol, klass, observed, rows, source="sina",
                             declared_basis=(bases.pop() if len(bases) == 1 else None))
        # The basis check applies to BENCHMARKS too: an index series on an adjusted basis
        # is just as wrong as a stock one.
        try:
            record.require_basis(self.declared_basis)
        except prov.ProvenanceError as exc:
            return JobOutcome(symbol, klass, "rejected", reason=str(exc), provenance=record)
        if klass == "stock" and record.volume_unit == prov.UNKNOWN:
            return JobOutcome(symbol, klass, "rejected", provenance=record,
                              reason="volume unit is UNKNOWN: %s"
                                     % record.evidence.get("unit_reason"))

        self._write(symbol, klass, rows, record, decoded)
        return JobOutcome(symbol, klass, "ok", rows=len(rows), provenance=record)

    def _write(self, symbol, klass, rows, record, decoded):
        tc = sqlite3.connect(self.destinations["trading"])
        tc.execute("INSERT OR IGNORE INTO instruments VALUES (?,?)", (symbol, klass))
        for r in rows:
            tc.execute(
                "INSERT INTO daily_bar_cache VALUES (?,?,?,?,?,?,?,?,?,'ready',?,?)",
                (symbol, r["date"], r.get("open"), r.get("high"), r.get("low"),
                 r.get("close"), r.get("volume"), r.get("amount"), record.source,
                 record.adjustment_mode, record.volume_unit))
        for d in decoded:
            tc.execute(
                "INSERT INTO ingest_provenance VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (symbol, klass, d.url, d.body_sha256, d.schema, d.declared_basis,
                 record.adjustment_mode, record.volume_unit, self.run_id, self.run_mode,
                 "one fetch copied into two stores: lineage consistency, NOT independent "
                 "source corroboration"))
        tc.commit(); tc.close()

        hc = sqlite3.connect(self.destinations["history"])
        for r in rows:
            hc.execute(
                "INSERT INTO daily_bars VALUES (?,?,?,?,?,?,?,?,?,?,?,1)",
                (symbol, r["date"], record.adjustment_mode, r.get("open"), r.get("high"),
                 r.get("low"), r.get("close"), r.get("volume"), r.get("amount"),
                 record.source, "%s:%s" % (self.run_mode, self.run_id)))
        hc.commit(); hc.close()

    # ---------------------------------------------------------------- validation
    #: The official gate arguments for each validation mode. The runner owns these, so a
    #: receipt cannot be minted from a report produced with different flags.
    GATE_ARGS = {
        "research": ["--history-scope", "all", "--pricing-basis", "none",
                     "--history-basis", "none", "--transformation", "identity"],
        "warmup_collection": ["--history-scope", "all", "--pricing-basis", "none",
                              "--history-basis", "none", "--transformation", "identity",
                              "--warmup-consumers", "both", "--warmup-start", "2022-08-24",
                              "--warmup-sessions", "250", "--warmup-required"],
    }

    def validate_candidate(self, mode, *, archive_trading, archive_history, baseline,
                           calendar_path, expected_manifest_sha, expected_calendar_sha):
        """Run the unchanged M1 gate against THESE views and mint a bound receipt.

        This is the only way a publishable receipt comes into existence. Previously the
        acceptance layer copied a caller-supplied fingerprint into its verdict, so a
        report produced by validating candidate A could be re-bound to candidate B's
        fingerprint and published - the gates never entered the binding at all.

        The fingerprint is computed here, before and after the gate runs, and the
        acceptance call receives the fingerprint THIS method measured. A candidate that
        changes while the gate is running is refused rather than certified.
        """
        if mode not in self.GATE_ARGS:
            raise ValueError("unknown validation mode %r" % mode)

        before = candidate_fingerprint(self.destinations)
        argv = ["validate",
                "--staging-trading", str(self.destinations["trading"]),
                "--staging-history", str(self.destinations["history"]),
                "--archive-trading", str(archive_trading),
                "--archive-history", str(archive_history),
                "--pilot-manifest", str(self.manifest),
                "--calendar", str(calendar_path),
                "--baseline", str(baseline)] + self.GATE_ARGS[mode]
        buffer = _io.StringIO()
        with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
            exit_code = staging_gate.main(argv)
        text = buffer.getvalue()
        after = candidate_fingerprint(self.destinations)

        if after != before:
            return ValidationReceipt(
                mode=mode, run_id=self.run_id, candidate_fingerprint=before,
                manifest_sha=expected_manifest_sha, calendar_sha=expected_calendar_sha,
                gate_exit=exit_code, accepted=False,
                reason=("the candidate changed while the gate was running (%s -> %s); "
                        "refusing to certify it" % (before[:12], after[:12])))

        try:
            if mode == "research":
                verdict = acc.accept_research(
                    text, exit_code, manifest_path=self.manifest,
                    expected_manifest_sha=expected_manifest_sha,
                    calendar_path=calendar_path,
                    expected_calendar_sha=expected_calendar_sha,
                    candidate_fingerprint=before)
            else:
                verdict = acc.accept_warmup_collection(
                    text, exit_code, self.manifest, self.destinations["trading"],
                    expected_manifest_sha=expected_manifest_sha,
                    calendar_path=calendar_path,
                    expected_calendar_sha=expected_calendar_sha,
                    candidate_fingerprint=before)
        except acc.AcceptanceError as exc:
            return ValidationReceipt(
                mode=mode, run_id=self.run_id, candidate_fingerprint=before,
                manifest_sha=expected_manifest_sha, calendar_sha=expected_calendar_sha,
                gate_exit=exit_code, accepted=False,
                reason="acceptance refused to interpret the run: %s" % exc)

        return ValidationReceipt(
            mode=mode, run_id=self.run_id, candidate_fingerprint=before,
            manifest_sha=expected_manifest_sha, calendar_sha=expected_calendar_sha,
            gate_exit=exit_code, accepted=verdict.accepted, reason=verdict.reason,
            details=verdict.details)

    # ------------------------------------------------------------------- publish
    def finalize(self, collection, receipts):
        """Publish ONLY on one research AND one warm-up-collection receipt for this run.

        `receipts` is a collection of ValidationReceipt objects minted by
        `validate_candidate`. Passing the same research receipt twice previously
        published a candidate whose real warm-up integrity gate had FAILED, because both
        slots only checked `accepted` and a fingerprint. Mode is now explicit and is
        never inferred from an argument position.
        """
        def refuse(reason):
            return {"published": False, "reason": reason}

        if collection.get("run_id") != self.run_id:
            return refuse("collection belongs to run %r, not this run %r"
                          % (collection.get("run_id"), self.run_id))
        if not collection.get("collection_complete"):
            return refuse("collection is not complete (status=%s, %s/%s jobs ok)"
                          % (collection.get("status"), collection.get("jobs_ok"),
                             collection.get("jobs_expected")))
        missing = [n for n, d in self.destinations.items() if not Path(d).exists()]
        if missing:
            return refuse("candidate view(s) missing on disk: %s" % missing)

        expected = collection.get("candidate_fingerprint")
        current = candidate_fingerprint(self.destinations)
        if not expected:
            return refuse("collection carries no candidate fingerprint")
        if current != expected:
            return refuse("the candidate changed after collection (fingerprint %s -> %s)"
                          % (expected[:12], current[:12]))

        try:
            supplied = list(receipts)
        except TypeError:
            return refuse("receipts must be a collection of ValidationReceipt objects")
        for item in supplied:
            if not isinstance(item, ValidationReceipt):
                return refuse("finalization accepts only ValidationReceipt objects minted "
                              "by validate_candidate; got %s" % type(item).__name__)

        by_mode = {}
        for receipt in supplied:
            if receipt.mode in by_mode:
                return refuse("two %r receipts supplied; one of each required mode is "
                              "expected" % receipt.mode)
            by_mode[receipt.mode] = receipt

        for mode in REQUIRED_MODES:
            receipt = by_mode.get(mode)
            if receipt is None:
                return refuse("no %r receipt supplied; publication requires one research "
                              "receipt AND one warm-up-collection receipt for the same "
                              "candidate" % mode)
            if not receipt.accepted:
                return refuse("%s validation did not succeed: %s"
                              % (mode, receipt.reason))
            if receipt.run_id != self.run_id:
                return refuse("%s receipt was issued for run %r, not this run %r"
                              % (mode, receipt.run_id, self.run_id))
            if receipt.candidate_fingerprint != current:
                return refuse("%s receipt was issued against candidate %s, not this one "
                              "(%s)" % (mode, str(receipt.candidate_fingerprint)[:12],
                                        current[:12]))
        shas = {(r.manifest_sha, r.calendar_sha) for r in by_mode.values()}
        if len(shas) != 1:
            return refuse("the receipts were issued against different frozen inputs: %s"
                          % sorted(shas))

        guard_paths(self.root, self.destinations, self.protected,
                    pointer_roles={"pointer": self.pointer,
                                   "pointer.tmp": self.pointer_tmp})

        previous = None
        if self.pointer.exists():
            try:
                previous = json.loads(self.pointer.read_text(encoding="utf-8")).get("run_id")
            except ValueError:
                previous = "unreadable"

        payload = json.dumps({
            "run_id": self.run_id, "run_dir": str(self.run_dir),
            "run_mode": self.run_mode, "previous_run_id": previous,
            "candidate_fingerprint": current,
            "validated_modes": sorted(by_mode),
            "trading": str(self.destinations["trading"]),
            "history": str(self.destinations["history"]),
        }, indent=2)

        try:
            fd = os.open(self.pointer_tmp, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            return refuse(
                "publication temporary %s already exists; refusing to follow or reuse an "
                "unowned path. The previous pointer and pair are untouched."
                % self.pointer_tmp)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
            os.replace(self.pointer_tmp, self.pointer)
        except Exception as exc:                      # noqa: BLE001
            try:
                if self.pointer_tmp.exists():
                    self.pointer_tmp.unlink()
            except OSError:
                pass
            return refuse("pointer write/replace failed (%s: %s); the previous pointer "
                          "and candidate pair are preserved"
                          % (type(exc).__name__, exc))

        return {"published": True, "pointer": str(self.pointer),
                "previous_run_id": previous, "run_id": self.run_id,
                "candidate_fingerprint": current, "validated_modes": sorted(by_mode)}


def candidate_fingerprint(destinations):
    """Content hash of the exact candidate pair, so a later change is detectable."""
    h = hashlib.sha256()
    for name in sorted(destinations):
        path = Path(destinations[name])
        h.update(("%s:" % name).encode())
        h.update(hashlib.sha256(path.read_bytes()).hexdigest().encode()
                 if path.exists() else b"MISSING")
        h.update(b"\n")
    return h.hexdigest()


def production_fingerprint(paths):
    return {str(p): (Path(p).stat().st_size, Path(p).stat().st_mtime_ns) for p in paths}
