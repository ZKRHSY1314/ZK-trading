"""Explicit, pinned execution of the new M2 staging candidate; default is read-only.

Never performs HTTP, client/login operations, production SQLite access or promotion.
Run without --execute to inspect readiness. Execution requires the reviewed exact
qualification-bundle SHA and creates new audit/candidate directories exclusively.
"""
from __future__ import annotations

import argparse
import ctypes
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import sys
from urllib.parse import parse_qsl, unquote, urlsplit
import uuid

import staging as staging


HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
BUNDLE = HERE / "qualification_pilot52.json"
PRODUCTION_BASELINE = HERE / "baseline/production_files_before.json"
ARCHIVE_BASELINE = HERE / "archive_copies/new_phase_baseline.json"
COPY_RECEIPT = HERE / "archive_copies/copy_receipt.json"
ARCHIVES = {"trading": HERE / "archive_copies/trading_local.sqlite3",
            "history": HERE / "archive_copies/market_history.sqlite3"}
MANIFEST = HERE.parent / "_m1_closure/pilot_symbols.csv"
CALENDAR = PROJECT / "backend/.venv/Lib/site-packages/akshare/file_fold/calendar.json"
PLUGIN = Path(r"D:\同花顺软件\同花顺远航版\bin\PluginSdks\ThsPlugin.Adapters.Hevo.dll")
PLUGIN_SHA = "19fbd89528ebe933cee267de34d63171afd47aef230132bd3574a3b81883469b"
FIXED_PINS = {
    PRODUCTION_BASELINE: "ad8c4b94105af897628d4c6556829b242e27ed8b0b31273fb6a9e5e5d114ddcd",
    ARCHIVE_BASELINE: "8b2e0e992905e6da1815f6c17d54c00ab379f1cad3df7b2f13239aabac40db31",
    COPY_RECEIPT: "94ebddde4661bc3414decc9a7ab8d509673c7b9450c4078a40f2a192e67fcc9f",
    MANIFEST: staging.MANIFEST_PIN, CALENDAR: staging.CALENDAR_PIN, PLUGIN: PLUGIN_SHA,
}
CAPTURE_ENTRIES = {HERE / group / "producer_pins.json": HERE / entry for group, entry in (
    ("qualification_capture", "capture.py"),
    ("remaining_capture_after_login", "collect_remaining_after_login.py"),
    ("remaining_capture_residual32", "collect_residual32.py"),
    ("remaining_capture_residual27", "collect_residual27.py"),
    ("remaining_capture_identity24", "collect_identity24.py"),
)}


class IntegrationError(ValueError):
    pass


def require(condition, code):
    if not condition:
        raise IntegrationError(code)


def digest(path):
    staging._safe_existing_chain(Path(path))
    result = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def read_json(path):
    return staging._strict_json(Path(path).read_bytes())


def now():
    return datetime.now(timezone.utc).isoformat()


def production_contract():
    require(digest(PRODUCTION_BASELINE) == FIXED_PINS[PRODUCTION_BASELINE], "production_baseline_pin_mismatch")
    baseline = read_json(PRODUCTION_BASELINE)
    mains = [PROJECT / name for name in ("trading_local.sqlite3", "market_history.sqlite3")]
    mains += [PROJECT / "backend" / name for name in ("trading_local.sqlite3", "market_history.sqlite3")]
    expected = {str(path) + suffix for path in mains for suffix in ("", "-wal", "-shm", "-journal")}
    require(set(baseline.get("files", {})) == expected, "production_baseline_inventory_not_complete")
    for value in baseline["files"].values():
        require(value == {"exists": False} or (value.get("stable_during_read") is True
                and type(value.get("size")) is int and type(value.get("mtime_ns")) is int
                and staging.SHA.fullmatch(str(value.get("sha256", "")))), "production_baseline_record_invalid")
    return baseline["files"]


def check_production(expected):
    observations = {}
    for name, before in expected.items():
        path = Path(name)
        staging._safe_existing_chain(path)
        if not path.exists():
            observations[name] = {"exists": False, "matches": before.get("exists") is False}
            continue
        first = path.stat()
        observed = {"exists": True, "size": first.st_size, "mtime_ns": first.st_mtime_ns,
                    "sha256": digest(path)}
        last = path.stat()
        observed["stable_during_read"] = ((first.st_size, first.st_mtime_ns, first.st_ino) ==
                                           (last.st_size, last.st_mtime_ns, last.st_ino))
        observed["matches"] = before.get("exists") is not False and observed["stable_during_read"] and all(
            observed[field] == before[field] for field in ("size", "mtime_ns", "sha256"))
        observations[name] = observed
    return {"at_utc": now(), "method": "byte reads only; no production SQLite connection",
            "baseline_sha256": FIXED_PINS[PRODUCTION_BASELINE],
            "passed": all(item["matches"] for item in observations.values()), "files": observations}


class ProductionReadLocks:
    """Hold existing production files open for read with writes/deletes unshared."""

    def __init__(self, expected):
        self.expected, self.handles = expected, []

    def __enter__(self):
        require(os.name == "nt", "actual_execution_requires_windows_read_locks")
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.kernel.CreateFileW.argtypes = (ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32,
            ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p)
        self.kernel.CreateFileW.restype = ctypes.c_void_p
        self.kernel.CloseHandle.argtypes = (ctypes.c_void_p,)
        self.kernel.CloseHandle.restype = ctypes.c_int
        try:
            for name, value in self.expected.items():
                if value.get("exists") is False:
                    require(not Path(name).exists(), "previously_absent_production_file_present")
                    continue
                handle = self.kernel.CreateFileW(name, 0x80000000, 1, None, 3, 0x08000000, None)
                require(handle not in (None, ctypes.c_void_p(-1).value), "production_read_lock_unavailable")
                self.handles.append(handle)
            return self
        except Exception:
            self.__exit__(None, None, None)
            raise

    def __exit__(self, *_):
        for handle in reversed(self.handles):
            self.kernel.CloseHandle(handle)
        self.handles.clear()


class AuditBoundary:
    """Guard Python connections and every SQLite ATTACH in this integration process."""

    def __init__(self, candidate_paths=()):
        self.candidates = {Path(path).resolve() for path in candidate_paths}
        self.archives = {path.resolve() for path in ARCHIVES.values()}
        self.connections, self.attachments, self.denials = [], [], []

    def sqlite_path(self, database, *, attach=False):
        value = os.fspath(database)
        require(type(value) is str, "sqlite_path_not_text")
        if value in (":memory:", "file::memory:"):
            require(not attach, "sqlite_memory_attach_forbidden")
            return "memory"
        require(value.startswith("file:"), "sqlite_requires_explicit_uri")
        parsed = urlsplit(value)
        require(parsed.scheme == "file" and not parsed.netloc and not parsed.fragment,
                "sqlite_uri_authority_or_fragment_forbidden")
        pairs = parse_qsl(parsed.query, keep_blank_values=True, strict_parsing=True)
        require(len(pairs) == 1 and pairs[0][0] == "mode", "sqlite_uri_query_not_explicit_mode")
        mode = pairs[0][1]
        decoded = unquote(parsed.path, errors="strict")
        if os.name == "nt" and len(decoded) >= 4 and decoded[0] == "/" and decoded[2] == ":":
            decoded = decoded[1:]
        path = Path(decoded)
        require(path.is_absolute() and ".." not in path.parts, "sqlite_path_not_absolute")
        staging._safe_existing_chain(path)
        path = path.resolve()
        require((path in self.archives and mode == "ro") or
                (path in self.candidates and mode in ("ro", "rw") and (not attach or mode == "ro")),
                "sqlite_outside_reviewed_paths_or_mode")
        return str(path)

    def authorizer(self, action, arg1, arg2, database, trigger, connection=None):
        if action == sqlite3.SQLITE_ATTACH:
            try:
                if arg1 is None:
                    # SQLite authorizes ATTACH ? before substituting parameters.
                    # Only the enclosing, already checked execute may permit it.
                    approved = getattr(connection, "_validated_attach", None)
                    require(approved is not None, "unvalidated_parameterized_attach")
                    self.attachments.append(approved)
                else:
                    self.attachments.append(self.sqlite_path(arg1, attach=True))
            except (IntegrationError, ValueError, OSError, staging.StagingError):
                self.denials.append("sqlite_attach_denied")
                return sqlite3.SQLITE_DENY
        if action == sqlite3.SQLITE_FUNCTION and str(arg2).lower() == "load_extension":
            self.denials.append("sqlite_extension_denied")
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK

    def hook(self, event, args):
        if event.startswith("socket.") or event == "subprocess.Popen" or event.startswith(("os.exec", "os.spawn")) or event == "os.system":
            self.denials.append("network_or_process_denied")
            raise IntegrationError("network_or_process_forbidden")
        if event == "sqlite3.connect":
            try:
                self.connections.append(self.sqlite_path(args[0]))
            except Exception:
                self.denials.append("sqlite_connect_denied")
                raise
        elif event in ("sqlite3.enable_load_extension", "sqlite3.load_extension"):
            self.denials.append("sqlite_extension_denied")
            raise IntegrationError("sqlite_extension_forbidden")

    def install(self):
        # CPython emits connect/handle before Connection.__init__ is complete.
        # The pre-connect audit check stays independent; all reviewed modules
        # call sqlite3.connect, so install the ATTACH authorizer immediately after
        # the native connection returns, before handing it to those modules.
        original_connect = sqlite3.connect
        sys.addaudithook(self.hook)
        boundary = self

        def checked_execute(connection, sql, parameters, call):
            approved = None
            if type(sql) is str and re.fullmatch(r"\s*ATTACH\s+\?\s+AS\s+[A-Za-z_][A-Za-z0-9_]{0,63}\s*;?\s*", sql, re.I):
                require(isinstance(parameters, (tuple, list)) and len(parameters) == 1, "attach_parameters_invalid")
                approved = boundary.sqlite_path(parameters[0], attach=True)
            previous = getattr(connection, "_validated_attach", None)
            connection._validated_attach = approved
            try:
                return call()
            finally:
                connection._validated_attach = previous

        class GuardedCursor(sqlite3.Cursor):
            def execute(self, sql, parameters=()):
                return checked_execute(self.connection, sql, parameters,
                    lambda: super(GuardedCursor, self).execute(sql, parameters))

        class GuardedConnection(sqlite3.Connection):
            def execute(self, sql, parameters=()):
                return checked_execute(self, sql, parameters,
                    lambda: super(GuardedConnection, self).execute(sql, parameters))

            def cursor(self, factory=sqlite3.Cursor):
                require(factory is sqlite3.Cursor, "custom_sqlite_cursor_factory_forbidden")
                return super().cursor(factory=GuardedCursor)

        def guarded_connect(*args, **kwargs):
            database = args[0] if args else kwargs.get("database")
            self.sqlite_path(database)
            factory = args[5] if len(args) > 5 else kwargs.get("factory", sqlite3.Connection)
            require(factory is sqlite3.Connection, "custom_sqlite_connection_factory_forbidden")
            if os.fspath(database).startswith("file:"):
                uri = args[7] if len(args) > 7 else kwargs.get("uri", False)
                require(uri is True, "sqlite_uri_flag_required")
            if len(args) > 5:
                args = list(args)
                args[5] = GuardedConnection
            else:
                kwargs["factory"] = GuardedConnection
            connection = original_connect(*args, **kwargs)
            connection.set_authorizer(lambda *arguments: self.authorizer(*arguments, connection=connection))
            return connection

        sqlite3.connect = guarded_connect


def prepare(bundle_sha=None):
    """Byte-only readiness review. No directory, database or pointer is created."""
    actual_sha = digest(BUNDLE)
    if bundle_sha is not None:
        require(staging.SHA.fullmatch(bundle_sha) is not None and actual_sha == bundle_sha, "reviewed_bundle_pin_mismatch")
    bundle = read_json(BUNDLE)
    require(bundle.get("schema") == "m2.ths.qualification_evidence.v1" and
            bundle.get("evidence_mode") == "retained_market_capture", "bundle_schema_or_mode_invalid")
    inventory = {actual_sha: BUNDLE}
    for item in bundle.get("artifacts", []):
        path, expected = Path(item["path"]), staging._strict_hash(item["sha256"])
        require(digest(path) == expected, "bundle_artifact_pin_mismatch")
        if expected in inventory:
            require(digest(inventory[expected]) == expected, "conflicting_artifact_hash")
        inventory[expected] = path
    producers = {"qualification_rules": (HERE / "qualification_pilot_rules.py", bundle["rules_sha256"]),
                 "qualification_builder": (HERE / "official/build_pilot52_qualification.py", bundle["builder_sha256"]),
                 "history_parser": (staging.PARSER, digest(staging.PARSER)), "plugin": (PLUGIN, PLUGIN_SHA),
                 **{"collector_" + str(i): (entry, digest(entry))
                    for i, entry in enumerate(CAPTURE_ENTRIES.values())}}
    for path, expected in producers.values():
        require(digest(path) == staging._strict_hash(expected), "qualification_producer_pin_mismatch")
    require(producers["history_parser"][1] ==
            "605d65965b1aee56f0f64c5c2446078aefa8d237d7a3d09b5f7403e4a24c2779",
            "reviewed_history_parser_pin_mismatch")
    scopes = bundle.get("scopes", [])
    seen_manifests = set()
    for scope in scopes:
        manifest_sha = scope["capture_producer_manifest_sha256"]
        require(manifest_sha in inventory, "capture_producer_manifest_absent")
        producer_manifest = inventory[manifest_sha].resolve()
        require(producer_manifest in CAPTURE_ENTRIES, "capture_producer_manifest_outside_fixed_captures")
        pins = read_json(producer_manifest)
        entry = CAPTURE_ENTRIES[producer_manifest]
        require(pins.get(str(entry)) == scope.get("collector_sha256"), "scope_does_not_bind_real_collector_entry")
        if manifest_sha not in seen_manifests:
            seen_manifests.add(manifest_sha)
            for path_text, expected in pins.items():
                path = Path(path_text)
                require(path.suffix.lower() not in (".sqlite3", ".sqlite", ".db"), "capture_manifest_database_reference")
                require(digest(path) == staging._strict_hash(expected), "captured_producer_pin_mismatch")
                producers["capture_dependency_" + str(len(producers))] = (path, expected)
    for path, expected in FIXED_PINS.items():
        require(digest(path) == expected, "fixed_phase_input_pin_mismatch")
    archives = read_json(ARCHIVE_BASELINE)
    copy = read_json(COPY_RECEIPT)
    require(copy.get("kind") == "new_phase_copy_baseline_not_historical_baseline" and
            copy.get("all_existing_copies_byte_equal") is True and copy.get("source_sqlite_connections") == 0 and
            copy.get("source_checkpoint_operations") == 0, "archive_copy_receipt_invalid")
    require(archives.get("calendar_sha256") == staging.CALENDAR_PIN, "archive_calendar_mismatch")
    for role, path in ARCHIVES.items():
        record = archives["archives"][role]
        require(Path(record["path"]).resolve() == path.resolve() and path.stat().st_size == record["bytes"] and
                digest(path) == record["file_sha256"], "isolated_archive_differs_from_new_baseline")
    import csv
    entries = {row["symbol"]: row for row in csv.DictReader(MANIFEST.open(encoding="utf-8-sig"))}
    issues = []
    if len(scopes) != 52 or len({scope.get("symbol") for scope in scopes}) != 52 or {scope.get("symbol") for scope in scopes} != set(entries):
        issues.append("scope_inventory_not_exact_52")
    for scope in scopes:
        symbol = scope.get("symbol")
        expected_class = "benchmark" if symbol in staging.BENCHMARKS else "stock"
        if scope.get("instrument_class") != expected_class:
            issues.append(symbol + ":instrument_class_mismatch")
        if scope.get("vendor_basis_status") != "verified" or scope.get("identity_status") != "verified":
            issues.append(symbol + ":basis_or_identity_not_verified")
        if scope.get("unit_status") != ("not_applicable" if expected_class == "benchmark" else "verified"):
            issues.append(symbol + ":unit_not_qualified")
        if scope.get("date_coverage_complete") is not True:
            issues.append(symbol + ":frozen_date_coverage_incomplete")
    if bundle.get("staging_eligible") is not True:
        issues.append("bundle_staging_eligible_not_true")
    expected_production = production_contract()
    production = check_production(expected_production)
    if not production["passed"]:
        issues.append("production_preservation_mismatch")
    report = {"at_utc": now(), "mode": "readiness_only", "bundle_sha256": actual_sha,
              "scopes": len(scopes), "ready": not issues, "issues": issues,
              "production_preservation": production, "network_requests": 0, "database_connections": 0,
              "directories_created": 0, "live_trading": False, "production_promoted": False}
    return report, inventory, producers, expected_production


def execute(bundle_sha, boundary):
    require(bundle_sha is not None, "execute_requires_reviewed_bundle_sha")
    readiness, inventory, producers, expected = prepare(bundle_sha)
    require(readiness["ready"], "qualification_or_preservation_not_ready")
    run_id = "ths_" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:12]
    audit_dir = HERE / "actual_runs" / run_id
    stage_root = staging.ALLOWED_STAGING_PARENT / run_id
    require(not audit_dir.exists() and not stage_root.exists(), "new_run_paths_required")
    staging._safe_existing_chain(audit_dir)
    audit_dir.mkdir(parents=True, exist_ok=False)
    run = staging.StagingRun(stage_root, run_id, manifest_path=MANIFEST, calendar_path=CALENDAR,
        expected_manifest_sha256=staging.MANIFEST_PIN, expected_calendar_sha256=staging.CALENDAR_PIN,
        producer_files=producers, evidence_files=inventory)
    boundary.candidates = {path.resolve() for path in run.destinations.values()}
    input_pins = {str(path): digest(path) for path in (Path(__file__), HERE / "staging.py", *FIXED_PINS)}
    sequence = 0
    published_sha = None

    def checkpoint(label):
        nonlocal sequence
        for path, pin in input_pins.items():
            require(digest(path) == pin, "integration_input_changed")
        run._verify_inputs()
        result = check_production(expected)
        sequence += 1
        staging.StagingRun._json_new(audit_dir / (f"preservation_{sequence:02d}_" + label + ".json"), result)
        require(result["passed"], "production_preservation_changed_" + label)
        return result

    try:
        staging.StagingRun._json_new(audit_dir / "readiness.json", readiness)
        staging.StagingRun._json_new(audit_dir / "integration_inputs.json", input_pins)
        with ProductionReadLocks(expected):
            checkpoint("before_stage")
            candidate = run.stage_from_evidence(bundle_sha)
            staging.StagingRun._json_new(audit_dir / "candidate_receipt.json", candidate)
            checkpoint("after_stage_before_run_a")
            research = run.validate("research", archive_trading=ARCHIVES["trading"],
                archive_history=ARCHIVES["history"], baseline=ARCHIVE_BASELINE)
            checkpoint("after_run_a")
            require(research.accepted, "run_a_not_accepted")
            checkpoint("before_run_b")
            warmup = run.validate("warmup_collection", archive_trading=ARCHIVES["trading"],
                archive_history=ARCHIVES["history"], baseline=ARCHIVE_BASELINE)
            checkpoint("after_run_b")
            require(warmup.accepted, "run_b_not_accepted")
            checkpoint("before_publication")
            require(not run.pointer.exists(), "unexpected_existing_pointer")
            publication = run.publish([research, warmup])
            published_sha = digest(run.pointer)
            checkpoint("after_publication")
            require(digest(run.pointer) == published_sha, "published_pointer_changed")
            require(not boundary.denials, "audit_boundary_denial_observed")
            receipt = {"at_utc": now(), "status": "staging_published", "run_id": run_id,
                "candidate": candidate, "publication": publication, "pointer_sha256": published_sha,
                "gate_receipt_sha256": dict(run._receipt_pins), "production_preservation_checks": sequence,
                "production_read_locks": "FileAccess.Read FileShare.Read held during all stage/gate/publication steps",
                "sqlite_connections": boundary.connections, "sqlite_attachments": boundary.attachments,
                "audit_denials": boundary.denials, "network_requests": 0, "production_sqlite_connections": 0,
                "live_trading": False, "production_promoted": False, "strict_pit": False}
            staging.StagingRun._json_new(audit_dir / "completion.json", receipt)
            return receipt
    except Exception as exc:
        pointer_removed = False
        # This root had no prior pointer. Remove only byte-identical publication
        # by this run; a foreign replacement is retained for independent review.
        if published_sha is not None and run.pointer.exists() and digest(run.pointer) == published_sha:
            pointer = read_json(run.pointer)
            if pointer.get("run_id") == run_id and Path(pointer.get("run_dir", "")).resolve() == run.run_dir.resolve():
                run.pointer.unlink()
                pointer_removed = True
        staging.StagingRun._json_new(audit_dir / "failure.json", {"at_utc": now(), "status": "failed_candidate_retained",
            "reason": str(exc) if isinstance(exc, (IntegrationError, staging.StagingError)) else type(exc).__name__,
            "run_id": run_id, "own_pointer_removed": pointer_removed, "audit_denials": boundary.denials,
            "live_trading": False, "production_promoted": False})
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="explicitly create, validate and publish a new staging candidate")
    parser.add_argument("--bundle-sha", help="reviewed SHA-256 of the exact qualification bundle; mandatory for execution")
    args = parser.parse_args(argv)
    boundary = AuditBoundary()
    boundary.install()
    try:
        if args.execute:
            result = execute(args.bundle_sha, boundary)
        else:
            result, _, _, _ = prepare(args.bundle_sha)
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    except (IntegrationError, staging.StagingError, OSError, ValueError, KeyError) as exc:
        reason = str(exc) if isinstance(exc, (IntegrationError, staging.StagingError)) else type(exc).__name__
        print(json.dumps({"status": "stopped", "reason": reason, "live_trading": False,
                          "production_promoted": False}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
