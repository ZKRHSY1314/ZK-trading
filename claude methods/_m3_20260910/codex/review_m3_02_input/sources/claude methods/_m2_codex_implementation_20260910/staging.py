"""Tonghuashun evidence-bound staging; production databases are never writable here.

This writer checks qualifications supplied by a separately reviewed evidence rule.
It does not establish vendor price basis, units or historical identity itself.
Collection, candidate validation and staging-pointer publication remain separate.
Publishing this pointer is neither production promotion nor strict-PIT acceptance.
"""
from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
import csv
import hashlib
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import sys
from urllib.parse import quote


HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
ALLOWED_STAGING_PARENT = HERE / "staging_runs"
M1 = HERE.parent / "_m1_closure"
M2A = HERE.parent / "_m2_pilot"
SOURCE = "tonghuashun"
RESEARCH_START, RESEARCH_END = "2023-09-04", "2026-09-04"
WARMUP_START, WARMUP_END = "2022-08-24", "2023-09-01"
MANIFEST_PIN = "97e251ae84fc927486127a96b4966ed8fc59fac0b744b7d6f186b2b1548886fe"
CALENDAR_PIN = "f1f1ce33c5cceb5c530c3271fc951405cb5624d2f30becec85dc7a85fd47e656"
MODES = ("research", "warmup_collection")
NUMBER_FIELDS = ("open", "high", "low", "close", "volume", "amount")
SHA = re.compile(r"^[0-9a-f]{64}$")
SAFE_RUN_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
CN = timezone(timedelta(hours=8))
PRODUCTION = tuple(PROJECT / name for name in ("trading_local.sqlite3", "market_history.sqlite3"))
PARSER = PROJECT / "backend/app/data/tonghuasun_history.py"
BENCHMARKS = {"SH000300": ("USZI399300", "399300.SZ"),
              "SH000001": ("USHI1A0001", "10001.SH")}
LEGACY_FILES = (M1 / "staging_gate.py", M1 / "acceptance_runner.py",
                M1 / "coverage_gap_generator.py", M2A / "acceptance.py")

TRADING_DDL = """
CREATE TABLE daily_bar_cache (
 symbol TEXT NOT NULL, trade_date TEXT NOT NULL, open REAL, high REAL, low REAL,
 close REAL, volume REAL, amount REAL, source TEXT NOT NULL, quality_status TEXT NOT NULL,
 adjustment_mode TEXT NOT NULL, volume_unit TEXT NOT NULL, PRIMARY KEY(symbol, trade_date));
CREATE TABLE instruments (symbol TEXT PRIMARY KEY, name TEXT);
CREATE TABLE ingest_provenance (
 symbol TEXT, instrument_class TEXT, url TEXT, body_sha256 TEXT, schema TEXT,
 declared_basis TEXT, derived_basis TEXT, derived_unit TEXT, run_id TEXT,
 run_mode TEXT, lineage TEXT);
CREATE TABLE row_evidence (
 symbol TEXT, trade_date TEXT, raw_sha256 TEXT, request_sha256 TEXT, producer_sha256 TEXT,
 parser_sha256 TEXT, capture_receipt_sha256 TEXT, capture_producer_manifest_sha256 TEXT,
 observed_at TEXT, point_index INTEGER, qualification_sha256 TEXT,
 source_name TEXT, source_name_status TEXT,
 PRIMARY KEY(symbol, trade_date));
CREATE TABLE qualification_records (symbol TEXT PRIMARY KEY, record_sha256 TEXT, record_json TEXT);
"""
HISTORY_DDL = """
CREATE TABLE daily_bars (
 symbol TEXT NOT NULL, trade_date TEXT NOT NULL, adjustment_mode TEXT NOT NULL,
 open REAL, high REAL, low REAL, close REAL, volume REAL, amount REAL, provider TEXT,
 fetched_at TEXT, ingest_run_id INTEGER NOT NULL REFERENCES ingest_runs(id),
 PRIMARY KEY(symbol, trade_date, adjustment_mode));
CREATE TABLE ingest_runs (
 id INTEGER PRIMARY KEY, provider TEXT, run_id TEXT, run_mode TEXT, started_at TEXT);
"""


class StagingError(ValueError):
    """Fixed local reason; never includes source data or credentials."""


def _require(condition, reason):
    if not condition:
        raise StagingError(reason)


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _hash_value(value):
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _strict_json(raw):
    def pairs(values):
        result = {}
        for key, value in values:
            _require(key not in result, "duplicate_json_key")
            result[key] = value
        return result
    def constant(_):
        raise StagingError("nonfinite_json_constant")
    try:
        return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)
    except (UnicodeError, ValueError, RecursionError):
        raise StagingError("invalid_evidence_json") from None


def _history_parser():
    name = "m2_ths_staging_history_parser"
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, PARSER)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    module = sys.modules[name]
    _require(Path(module.__file__).resolve() == PARSER.resolve(), "parser_module_shadowed")
    return module


def _path(value):
    raw = Path(value)
    _require(".." not in raw.parts, "path_traversal")
    return raw.absolute()


def _safe_existing_chain(path):
    """Reject symlinks, junctions/reparse points and hardlinked regular files."""
    for item in (path, *path.parents):
        try:
            stat = item.lstat()
        except FileNotFoundError:
            continue
        _require(not item.is_symlink() and not (getattr(stat, "st_file_attributes", 0) & 0x400),
                 "symlink_or_reparse_point")
        if item.is_file():
            _require(stat.st_nlink == 1, "hardlinked_file")


def _strict_hash(value):
    _require(type(value) is str and SHA.fullmatch(value) is not None, "invalid_sha256")
    return value


def _observed(value, trade_date=None):
    _require(type(value) is str and bool(value), "observed_time_missing")
    try:
        moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise StagingError("observed_time_invalid") from None
    _require(moment.tzinfo is not None and moment.utcoffset() is not None, "observed_time_timezone_missing")
    _require(moment <= datetime.now(timezone.utc) + timedelta(seconds=5), "observed_time_in_future")
    if trade_date is not None:
        _require(trade_date <= moment.astimezone(CN).date().isoformat(), "bar_after_observed_time")
    return moment.astimezone(timezone.utc).isoformat()


def _legacy_modules():
    """Load only the reviewed audit modules, never backend application modules."""
    saved = list(sys.path)
    try:
        sys.path.insert(0, str(M1))
        import staging_gate
        _require(Path(staging_gate.__file__).resolve() == (M1 / "staging_gate.py").resolve(), "legacy_module_shadowed")
        name = "m2_ths_legacy_acceptance"
        if name not in sys.modules:
            spec = importlib.util.spec_from_file_location(name, M2A / "acceptance.py")
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            spec.loader.exec_module(module)
        acceptance = sys.modules[name]
        _require(Path(acceptance.__file__).resolve() == (M2A / "acceptance.py").resolve(), "legacy_module_shadowed")
        return staging_gate, acceptance
    finally:
        sys.path[:] = saved


@dataclass(frozen=True)
class Receipt:
    mode: str
    run_id: str
    accepted: bool
    gate_exit: int
    candidate_fingerprint: str
    input_fingerprint: str
    validation_inputs: tuple
    reason: str


class StagingRun:
    def __init__(self, staging_root, run_id, *, manifest_path, calendar_path,
                 expected_manifest_sha256, expected_calendar_sha256,
                 producer_files, evidence_files, evidence_mode="retained_market_capture"):
        _require(type(run_id) is str and SAFE_RUN_ID.fullmatch(run_id) is not None, "invalid_run_id")
        self.root = _path(staging_root)
        _require(evidence_mode in ("retained_market_capture", "synthetic_test_only"), "unsupported_evidence_mode")
        self.evidence_mode = evidence_mode
        if evidence_mode == "synthetic_test_only":
            _require(self.root.name.startswith("synthetic_test_"), "synthetic_test_root_required")
        _safe_existing_chain(self.root)
        _require(self.root.resolve().is_relative_to(ALLOWED_STAGING_PARENT.resolve()), "staging_root_outside_allowlist")
        self.run_id = run_id
        self.run_dir = self.root / ("run_" + run_id)
        self.destinations = {"trading": self.run_dir / "trading.sqlite3", "history": self.run_dir / "history.sqlite3"}
        self.pointer = self.root / "CURRENT.json"
        self.pointer_tmp = self.root / ("CURRENT." + run_id + ".tmp")
        self.manifest = _path(manifest_path)
        self.calendar = _path(calendar_path)
        _require(expected_manifest_sha256 == MANIFEST_PIN and expected_calendar_sha256 == CALENDAR_PIN,
                 "contract_not_approved_pilot")
        self.producers = {str(role): (_path(value[0]), _strict_hash(value[1])) for role, value in producer_files.items()}
        _require(all(role in self.producers for role in ("qualification_rules", "history_parser", "plugin")),
                 "required_producer_pin_missing")
        _require(self.producers["history_parser"][0].resolve() == PARSER.resolve(), "unreviewed_history_parser")
        _require(any(role.startswith("collector_") for role in self.producers), "collector_pin_missing")
        self.evidence = {_strict_hash(key): _path(path) for key, path in evidence_files.items()}
        _require(bool(self.evidence), "evidence_inventory_empty")
        self.input_pins = {self.manifest: MANIFEST_PIN, self.calendar: CALENDAR_PIN,
                           Path(__file__).resolve(): _sha(__file__)}
        self.input_pins.update({path: _sha(path) for path in LEGACY_FILES})
        for path, expected in [*self.producers.values(), *((path, key) for key, path in self.evidence.items())]:
            if path in self.input_pins:
                _require(self.input_pins[path] == expected, "conflicting_input_pin")
            self.input_pins[path] = expected
        for path in self.input_pins:
            _safe_existing_chain(path)
            _require(not path.resolve().is_relative_to(self.root.resolve()), "staging_root_contains_protected_input")
            _require(path.resolve() not in PRODUCTION, "production_input_forbidden")
            _require(path.suffix.lower() not in (".sqlite", ".sqlite3", ".db"), "database_evidence_input_forbidden")
        self._verify_inputs()
        self.entries, self.keys = self._contract()
        self._receipts = {}
        self._receipt_pins = {}
        self._candidate = None
        self._scope_cache = {}
        self._guard_paths()

    def _guard_paths(self):
        for path in (self.root, self.run_dir, *self.destinations.values(), self.pointer, self.pointer_tmp):
            _safe_existing_chain(path)
            _require(path.resolve().is_relative_to(self.root.resolve()), "destination_outside_staging_root")
            _require(path.resolve() not in PRODUCTION, "production_destination_forbidden")
        _require(not self.pointer_tmp.exists(), "publication_temporary_already_exists")

    def _verify_inputs(self):
        for path, expected in self.input_pins.items():
            _safe_existing_chain(path)
            _require(path.is_file() and _sha(path) == expected, "input_pin_mismatch")
        return _hash_value({str(path): expected for path, expected in self.input_pins.items()})

    def _contract(self):
        with self.manifest.open(encoding="utf-8-sig", newline="") as handle:
            entries = list(csv.DictReader(handle))
        _require(len(entries) == 52 and len({e["symbol"] for e in entries}) == 52, "pilot_inventory_not_52_distinct")
        _require(sum(e.get("stratum") == "benchmark" for e in entries) == 2, "pilot_inventory_not_50_plus_2")
        raw_calendar = json.loads(self.calendar.read_text(encoding="utf-8-sig"))
        days = [datetime.fromisoformat(str(v.get("trade_date")) if type(v) is dict else str(v)).date().isoformat() for v in raw_calendar]
        _require(len(days) == len(set(days)), "duplicate_calendar_keys")
        days = sorted(day for day in days if WARMUP_START <= day <= RESEARCH_END)
        _require(sum(day <= WARMUP_END for day in days) == 250, "warmup_contract_not_250")
        result = {}
        for entry in entries:
            symbol = entry["symbol"]
            benchmark = entry["stratum"] == "benchmark"
            listing, delisting = entry.get("list_date"), entry.get("delist_date")
            _require(benchmark or bool(listing), "stock_listing_unknown")
            result[symbol] = {day for day in days if (not listing or day >= listing) and (not delisting or day <= delisting)}
        _require(sum(len(dates) for dates in result.values()) == 45935, "pilot_total_not_45935")
        _require(sum(day >= RESEARCH_START for dates in result.values() for day in dates) == 36193,
                 "research_total_not_36193")
        _require(sum(day <= WARMUP_END for dates in result.values() for day in dates) == 9742,
                 "warmup_total_not_9742")
        return {e["symbol"]: e for e in entries}, result

    def _evidence_json(self, digest):
        _require(type(digest) is str and digest in self.evidence, "evidence_reference_missing")
        path = self.evidence[digest]
        _require(_sha(path) == digest, "evidence_pin_mismatch")
        return _strict_json(path.read_bytes())

    def _qualifications(self, qualifications):
        # Only a retained, pinned external decision artifact is accepted. Passing
        # {"verified": True} or stamping a request parameter is not qualification.
        bundle = self._evidence_json(qualifications)
        _require(type(bundle) is dict and bundle.get("schema") == "m2.ths.qualification_evidence.v1",
                 "qualification_schema_invalid")
        _require(bundle.get("evidence_mode") == self.evidence_mode, "qualification_mode_mismatch")
        _require(bundle.get("rules_sha256") == self.producers["qualification_rules"][1], "qualification_rules_mismatch")
        scopes = bundle.get("scopes")
        _require(type(scopes) is list and len(scopes) == 52, "qualification_inventory_mismatch")
        _require(all(type(value) is dict for value in scopes), "qualification_not_object")
        _require(len({value.get("symbol") for value in scopes}) == 52 and
                 {value.get("symbol") for value in scopes} == set(self.entries), "qualification_inventory_mismatch")
        approved = {}
        for value in scopes:
            symbol = value["symbol"]
            benchmark = self.entries[symbol]["stratum"] == "benchmark"
            _require(value.get("instrument_class") == ("benchmark" if benchmark else "stock"),
                     "qualification_instrument_class_mismatch")
            _require(all(value.get(field) == "verified" for field in
                ("vendor_basis_status", "identity_status")), "qualification_status_not_verified")
            _require(value.get("unit_status") == ("not_applicable" if benchmark else "verified"),
                     "qualification_unit_status_invalid")
            _require(value.get("vendor_basis") == "unadjusted", "vendor_basis_not_verified_unadjusted")
            _require(value.get("rules_sha256") == self.producers["qualification_rules"][1], "qualification_rules_mismatch")
            _require(value.get("plugin_sha256") == self.producers["plugin"][1], "qualification_plugin_mismatch")
            _require(value.get("start_date") == WARMUP_START and value.get("end_date") == RESEARCH_END and
                     type(value.get("period")) is int and value["period"] == 7 and
                     type(value.get("adjustment")) is int and value["adjustment"] == 0,
                     "qualification_window_or_basis_mismatch")
            for field in ("raw_body_sha256", "capture_receipt_sha256", "capture_producer_manifest_sha256"):
                _require(value.get(field) in self.evidence, "qualification_capture_evidence_missing")
            _strict_hash(value.get("request_sha256"))
            references = value.get("evidence_sha256")
            _require(type(references) is list and bool(references) and
                     len(set(references)) == len(references) and all(ref in self.evidence for ref in references),
                     "qualification_evidence_missing")
            if benchmark:
                _require(value.get("volume_unit") == "not_applicable" and
                         value.get("amount_unit") == "not_applicable", "benchmark_liquidity_claim_invalid")
            else:
                _require(value.get("volume_unit") in ("share", "hand"), "stock_volume_unit_unverified")
                _require(value.get("amount_unit") == "CNY", "stock_amount_unit_unverified")
            approved[symbol] = (dict(value), _hash_value(value))
        return approved

    def _capture(self, symbol, qualification):
        key = _hash_value(qualification)
        if key in self._scope_cache:
            return self._scope_cache[key]
        receipt = self._evidence_json(qualification["capture_receipt_sha256"])
        _require(type(receipt) is dict and type(receipt.get("http_status")) is int and receipt["http_status"] == 200,
                 "capture_not_successful_http")
        _require(receipt.get("stop_reason") is None, "capture_stop_reason_present")
        _require(receipt.get("raw_sha256") == qualification["raw_body_sha256"], "capture_body_scope_mismatch")
        job = receipt.get("job")
        _require(type(job) is dict and job.get("symbol") == symbol, "capture_symbol_scope_mismatch")
        request = job.get("payload")
        _require(type(request) is dict and _hash_value(request) == qualification["request_sha256"], "capture_request_scope_mismatch")
        parser = _history_parser()
        if symbol in BENCHMARKS:
            native, source_code = BENCHMARKS[symbol]
            spec = parser.SecuritySpec.benchmark(symbol, host_full_code=native,
                response_full_code=source_code, mapping_evidence="qualification-sha256:" + key)
        else:
            spec = parser.SecuritySpec.stock(symbol)
        _require(job.get("host_full_code") == spec.host_full_code, "capture_native_identity_mismatch")
        _require(set(request) == {"market", "security", "startTimeUtc", "endTimeUtc", "period", "adjustment", "limit", "fields"},
                 "capture_request_fields_invalid")
        for field, expected in (("market", 1), ("period", 7), ("adjustment", 0), ("limit", 5000)):
            _require(type(request.get(field)) is int and request[field] == expected, "capture_request_contract_invalid")
        _require(request.get("fields") == list(parser.FIELDS), "capture_quote_fields_invalid")
        security = request.get("security")
        _require(type(security) is dict, "capture_request_identity_invalid")
        identifiers = set(security) - {"market"}
        _require(len(identifiers) == 1 and identifiers <= {"hostFullCode", "fullCode"}, "capture_requires_one_identifier")
        if "market" in security:
            _require(type(security["market"]) is int and security["market"] == 1, "capture_request_market_invalid")
        identifier = next(iter(identifiers))
        _require(security[identifier] == (spec.host_full_code if identifier == "hostFullCode" else spec.response_full_code),
                 "capture_request_identity_mismatch")
        _require(symbol not in BENCHMARKS or identifier == "hostFullCode", "benchmark_requires_native_identifier")
        expected_request = parser.build_history_request(spec, WARMUP_START, RESEARCH_END)
        for field in ("startTimeUtc", "endTimeUtc"):
            # Existing captured requests differ only in optional millisecond text.
            _require(_observed(request.get(field)) == _observed(expected_request[field]), "capture_request_window_mismatch")
        observed = _observed(receipt.get("observed_at"))
        reserved = _observed(receipt.get("reserved_at"))
        _require(reserved <= observed, "capture_observation_precedes_reservation")
        manifest = self._evidence_json(qualification["capture_producer_manifest_sha256"])
        _require(type(manifest) is dict, "capture_producer_manifest_invalid")
        matches = {digest for role, (path, digest) in self.producers.items()
                   if role.startswith("collector_") and manifest.get(str(path)) == digest}
        _require(bool(matches), "capture_collector_unpinned")
        collector = qualification.get("collector_sha256")
        if collector is None and len(matches) == 1:
            collector = next(iter(matches))
        _require(collector in matches, "capture_collector_ambiguous_or_unpinned")
        raw = self.evidence[qualification["raw_body_sha256"]].read_bytes()
        _require(hashlib.sha256(raw).hexdigest() == qualification["raw_body_sha256"], "capture_body_changed")
        if "raw_bytes" in receipt:
            _require(type(receipt["raw_bytes"]) is int and receipt["raw_bytes"] == len(raw), "capture_byte_count_mismatch")
        try:
            decoded = parser.parse_history_response(raw, spec, WARMUP_START, RESEARCH_END,
                adjustment="none", expected_dates=sorted(self.keys[symbol]))
        except parser.HistoryValidationError:
            raise StagingError("raw_capture_parser_rejected") from None
        _require(decoded["coverage"]["complete"] is True, "raw_capture_coverage_incomplete")
        if "source_security" in receipt:
            _require(receipt["source_security"] == decoded["response_identity"], "capture_receipt_identity_mismatch")
        result = {"rows": decoded["rows"], "observed_at": observed, "collector_sha256": collector,
                  "parser_sha256": self.producers["history_parser"][1],
                  "response_identity": decoded["response_identity"], "name_diagnostics": decoded["name_diagnostics"]}
        self._scope_cache[key] = result
        return result

    def records_from_evidence(self, qualification_bundle_sha256):
        """Rebuild raw-unit rows; qualification is still checked before any DB write."""
        self._verify_inputs()
        approved = self._qualifications(qualification_bundle_sha256)
        result = []
        for symbol, (qualification, _) in approved.items():
            capture = self._capture(symbol, qualification)
            for index, row in enumerate(capture["rows"]):
                result.append({"symbol": symbol, "trade_date": row["date"],
                    **{field: row[field] for field in NUMBER_FIELDS}, "source": SOURCE,
                    "raw_sha256": qualification["raw_body_sha256"], "request_sha256": qualification["request_sha256"],
                    "capture_receipt_sha256": qualification["capture_receipt_sha256"],
                    "capture_producer_manifest_sha256": qualification["capture_producer_manifest_sha256"],
                    "producer_sha256": capture["collector_sha256"], "parser_sha256": capture["parser_sha256"],
                    "observed_at": capture["observed_at"], "point_index": index})
        return result

    def stage_from_evidence(self, qualification_bundle_sha256):
        return self.stage(self.records_from_evidence(qualification_bundle_sha256), qualification_bundle_sha256)

    def _rows(self, records, approved):
        rows, seen = [], set()
        for record in records:
            _require(type(record) is dict, "row_not_object")
            symbol, day = record.get("symbol"), record.get("trade_date")
            _require(symbol in self.entries and day in self.keys[symbol], "row_outside_pilot_contract")
            key = (symbol, day)
            _require(key not in seen, "duplicate_business_key")
            seen.add(key)
            _require(record.get("source") == SOURCE, "row_source_mismatch")
            qualification, _ = approved[symbol]
            for field, scope_field in (("raw_sha256", "raw_body_sha256"), ("request_sha256", "request_sha256"),
                ("capture_receipt_sha256", "capture_receipt_sha256"),
                ("capture_producer_manifest_sha256", "capture_producer_manifest_sha256")):
                _require(record.get(field) == qualification[scope_field], "row_capture_scope_mismatch")
            capture = self._capture(symbol, qualification)
            _require(record.get("producer_sha256") == capture["collector_sha256"] and
                     record.get("parser_sha256") == capture["parser_sha256"], "row_producer_unpinned")
            _require(type(record.get("point_index")) is int and record["point_index"] >= 0, "point_index_invalid")
            observed = _observed(record.get("observed_at"), day)
            _require(observed == capture["observed_at"], "row_observed_time_mismatch")
            _require(record["point_index"] < len(capture["rows"]), "point_index_out_of_bounds")
            original = capture["rows"][record["point_index"]]
            _require(day == original["date"], "row_date_not_from_raw_point")
            benchmark = self.entries[symbol]["stratum"] == "benchmark"
            numbers = {}
            for field in NUMBER_FIELDS:
                value = record.get(field)
                if benchmark and field == "amount" and value is None:
                    numbers[field] = None
                    continue
                _require(not isinstance(value, bool) and isinstance(value, (int, float, str)), "row_number_type_invalid")
                try:
                    number = float(value)
                except (ValueError, OverflowError):
                    raise StagingError("row_number_invalid") from None
                _require(math.isfinite(number), "row_number_nonfinite")
                numbers[field] = number
            _require(all(numbers[f] > 0 for f in NUMBER_FIELDS[:4]), "nonpositive_ohlc")
            _require(numbers["low"] <= min(numbers["open"], numbers["close"]) <=
                     max(numbers["open"], numbers["close"]) <= numbers["high"], "ohlc_order_invalid")
            _require(numbers["volume"] >= 0 and (numbers["amount"] is None or numbers["amount"] >= 0), "negative_liquidity")
            _require(all(numbers[field] == original[field] for field in NUMBER_FIELDS), "row_values_not_from_raw_point")
            rows.append({**record, **numbers, "observed_at": observed,
                "source_name": original["source_name"], "source_name_status":
                    next((item["code"] for item in capture["name_diagnostics"]
                          if item["row_index"] == record["point_index"]), "source_name_observed")})
        expected = {(symbol, day) for symbol, days in self.keys.items() for day in days}
        _require(seen == expected, "pilot_key_inventory_incomplete")
        return sorted(rows, key=lambda row: (row["symbol"], row["trade_date"]))

    def _open_write(self, path):
        _require(path in self.destinations.values() and path.parent == self.run_dir, "sqlite_write_outside_allowlist")
        self._guard_paths()
        _require(path.is_file() and path.stat().st_nlink == 1, "sqlite_target_not_owned_regular_file")
        uri = "file:" + quote(path.as_posix(), safe="/:") + "?mode=rw"
        connection = sqlite3.connect(uri, uri=True)
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=DELETE")
        connection.set_authorizer(lambda action, arg1, arg2, database, trigger:
            sqlite3.SQLITE_DENY if action in (sqlite3.SQLITE_ATTACH, sqlite3.SQLITE_DETACH) else sqlite3.SQLITE_OK)
        return connection

    @staticmethod
    def _json_new(path, value):
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(_canonical(value) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def stage(self, records, qualifications):
        self._guard_paths()
        _require(not self.run_dir.exists(), "run_already_exists")
        self._verify_inputs()
        approved = self._qualifications(qualifications)
        rows = self._rows(records, approved)
        self.root.mkdir(parents=True, exist_ok=True)
        self._guard_paths()
        self.run_dir.mkdir(exist_ok=False)
        try:
            for path in self.destinations.values():
                fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600)
                os.close(fd)
            trading = history = None
            try:
                trading = self._open_write(self.destinations["trading"])
                history = self._open_write(self.destinations["history"])
                trading.executescript(TRADING_DDL)
                history.executescript(HISTORY_DDL)
                started = datetime.now(timezone.utc).isoformat()
                history.execute("INSERT INTO ingest_runs VALUES (1,?,?,?,?)", (SOURCE, self.run_id, "retained_raw_review_only", started))
                for symbol, entry in self.entries.items():
                    trading.execute("INSERT INTO instruments VALUES (?,?)", (symbol, entry.get("name", "")))
                    qualification, qualification_sha = approved[symbol]
                    trading.execute("INSERT INTO qualification_records VALUES (?,?,?)", (symbol, qualification_sha, _canonical(qualification)))
                lineage_seen = set()
                for row in rows:
                    symbol, day = row["symbol"], row["trade_date"]
                    qualification, qualification_sha = approved[symbol]
                    numbers = [row[field] for field in NUMBER_FIELDS]
                    trading.execute("INSERT INTO daily_bar_cache VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                        (symbol, day, *numbers, SOURCE, "qualified_candidate", "none", qualification["volume_unit"]))
                    trading.execute("INSERT INTO row_evidence VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", (symbol, day,
                        row["raw_sha256"], row["request_sha256"], row["producer_sha256"], row["parser_sha256"],
                        row["capture_receipt_sha256"], row["capture_producer_manifest_sha256"],
                        row["observed_at"], row["point_index"], qualification_sha,
                        row["source_name"], row["source_name_status"]))
                    lineage = (symbol, row["raw_sha256"], row["request_sha256"], row["producer_sha256"])
                    if lineage not in lineage_seen:
                        lineage_seen.add(lineage)
                        trading.execute("INSERT INTO ingest_provenance VALUES (?,?,?,?,?,?,?,?,?,?,?)", (symbol,
                            "benchmark" if self.entries[symbol]["stratum"] == "benchmark" else "stock",
                            "request-sha256:" + row["request_sha256"], row["raw_sha256"], "m2.ths.retained_rows.v1",
                            qualification["vendor_basis"], "none", qualification["volume_unit"], self.run_id,
                            "retained_raw_review_only", "same raw capture in two stores; not independent corroboration"))
                    history.execute("INSERT INTO daily_bars VALUES (?,?,?,?,?,?,?,?,?,?,?,1)",
                        (symbol, day, "none", *numbers, SOURCE, row["observed_at"]))
                trading.commit()
                history.commit()
            finally:
                if trading is not None:
                    trading.close()
                if history is not None:
                    history.close()
            self._verify_inputs()
            metadata = {"schema": "m2.ths.staging_candidate.v1", "run_id": self.run_id,
                "source": SOURCE, "rows_per_view": len(rows), "symbols": 52, "stocks": 50, "benchmarks": 2,
                "input_fingerprint": self._verify_inputs(), "qualification_bundle_sha256": qualifications,
                "evidence_mode": self.evidence_mode,
                "source_name_invalid_rows": sum(row["source_name_status"] == "invalid_source_name" for row in rows),
                "source_name_missing_rows": sum(row["source_name_status"] == "missing_source_name" for row in rows),
                "live_trading": False, "production_promoted": False, "strict_pit": False}
            self._json_new(self.run_dir / "candidate.json", metadata)
            self._candidate = self.fingerprint()
            return {**metadata, "candidate_fingerprint": self._candidate, "published": False}
        except Exception:
            failed = self.run_dir / "FAILED.json"
            if not failed.exists():
                self._json_new(failed, {"status": "failed_candidate_retained", "published": False, "live_trading": False})
            raise

    def fingerprint(self):
        paths = [*self.destinations.values(), self.run_dir / "candidate.json"]
        for path in paths:
            _safe_existing_chain(path)
            _require(path.is_file(), "candidate_incomplete")
        return _hash_value({path.name: _sha(path) for path in paths})

    def validate(self, mode, *, archive_trading, archive_history, baseline):
        _require(mode in MODES, "unknown_validation_mode")
        _require(mode not in self._receipts, "validation_mode_already_issued")
        _require(self._candidate is not None and not (self.run_dir / "FAILED.json").exists(), "candidate_not_staged")
        self._guard_paths()
        input_fp = self._verify_inputs()
        before = self.fingerprint()
        _require(before == self._candidate, "candidate_changed_before_validation")
        archives = [_path(archive_trading), _path(archive_history)]
        baseline = _path(baseline)
        for path in [*archives, baseline]:
            _safe_existing_chain(path)
            _require(path.is_file() and path.resolve().is_relative_to(HERE.resolve()), "validation_input_outside_isolated_area")
            _require(path.resolve() not in PRODUCTION and path not in self.destinations.values(), "validation_input_alias")
        _require(archives[0].resolve() != archives[1].resolve(), "archive_views_alias")
        validation_inputs = tuple((str(path), _sha(path)) for path in [*archives, baseline])
        gate, acceptance = _legacy_modules()
        argv = ["validate", "--staging-trading", str(self.destinations["trading"]),
                "--staging-history", str(self.destinations["history"]), "--archive-trading", str(archives[0]),
                "--archive-history", str(archives[1]), "--pilot-manifest", str(self.manifest),
                "--calendar", str(self.calendar), "--baseline", str(baseline), "--history-scope", "all",
                "--pricing-basis", "none", "--history-basis", "none", "--transformation", "identity"]
        if mode == "warmup_collection":
            argv += ["--warmup-consumers", "both", "--warmup-start", WARMUP_START,
                     "--warmup-sessions", "250", "--warmup-required"]
        output = io.StringIO()
        with redirect_stdout(output), redirect_stderr(output):
            code = gate.main(argv)
        text = output.getvalue()
        _require(self.fingerprint() == before and self._verify_inputs() == input_fp, "candidate_or_inputs_changed_during_validation")
        _require(all(_sha(path) == pin for path, pin in validation_inputs), "validation_input_changed")
        kwargs = {"expected_manifest_sha": MANIFEST_PIN, "calendar_path": self.calendar,
                  "expected_calendar_sha": CALENDAR_PIN, "candidate_fingerprint": before}
        if mode == "research":
            verdict = acceptance.accept_research(text, code, manifest_path=self.manifest, **kwargs)
        else:
            verdict = acceptance.accept_warmup_collection(text, code, self.manifest, self.destinations["trading"], **kwargs)
        receipt = Receipt(mode, self.run_id, verdict.accepted, code, before, input_fp, validation_inputs, verdict.reason)
        self._receipts[mode] = receipt
        receipt_path = self.run_dir / (mode + "_receipt.json")
        self._json_new(receipt_path, {**receipt.__dict__, "gate_output": text, "evidence_mode": self.evidence_mode,
            "live_trading": False, "production_promoted": False, "strict_pit": False})
        self._receipt_pins[mode] = _sha(receipt_path)
        return receipt

    def publish(self, receipts):
        self._guard_paths()
        current_inputs = self._verify_inputs()
        current = self.fingerprint()
        _require(current == self._candidate, "candidate_changed_before_publication")
        supplied = list(receipts)
        _require(len(supplied) == 2 and all(type(r) is Receipt for r in supplied), "two_receipts_required")
        _require({r.mode for r in supplied} == set(MODES), "research_and_warmup_receipts_required")
        for receipt in supplied:
            _require(self._receipts.get(receipt.mode) is receipt, "receipt_not_issued_by_this_run")
            _require(receipt.accepted and receipt.run_id == self.run_id and receipt.candidate_fingerprint == current and
                     receipt.input_fingerprint == current_inputs, "receipt_binding_or_acceptance_failed")
            _require(all(_sha(path) == pin for path, pin in receipt.validation_inputs), "validation_input_changed_before_publication")
            receipt_path = self.run_dir / (receipt.mode + "_receipt.json")
            _safe_existing_chain(receipt_path)
            _require(_sha(receipt_path) == self._receipt_pins.get(receipt.mode), "receipt_artifact_changed")
        _require(supplied[0].validation_inputs == supplied[1].validation_inputs, "receipt_validation_inputs_disagree")
        previous_pin = _sha(self.pointer) if self.pointer.exists() else None
        previous = _strict_json(self.pointer.read_bytes()) if self.pointer.exists() else None
        if previous is not None:
            _require(type(previous) is dict and previous.get("schema") == "m2.ths.staging_pointer.v1" and
                     previous.get("evidence_mode") == self.evidence_mode and
                     previous.get("live_trading") is False and previous.get("production_promoted") is False,
                     "previous_pointer_not_compatible_staging_pointer")
        payload = {"schema": "m2.ths.staging_pointer.v1", "run_id": self.run_id, "run_dir": str(self.run_dir),
            "candidate_fingerprint": current, "input_fingerprint": current_inputs,
            "validated_modes": list(MODES), "receipt_sha256": dict(self._receipt_pins),
            "evidence_mode": self.evidence_mode, "previous": previous, "live_trading": False,
            "production_promoted": False, "strict_pit": False}
        self._json_new(self.pointer_tmp, payload)
        # All protected evidence and candidate bytes are checked immediately before the
        # single publication point. Failure retains the old pointer and candidate pair.
        try:
            _require(self._verify_inputs() == current_inputs and self.fingerprint() == current, "publication_recheck_failed")
            _require((_sha(self.pointer) if self.pointer.exists() else None) == previous_pin, "publication_pointer_changed")
            os.replace(self.pointer_tmp, self.pointer)
        except Exception:
            if self.pointer_tmp.exists():
                self.pointer_tmp.unlink()
            raise
        return {"published": True, "pointer": str(self.pointer), "run_id": self.run_id,
                "candidate_fingerprint": current, "evidence_mode": self.evidence_mode,
                "live_trading": False, "production_promoted": False, "strict_pit": False}
