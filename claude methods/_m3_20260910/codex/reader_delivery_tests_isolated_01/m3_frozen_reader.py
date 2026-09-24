"""M3-02 frozen reader: deterministic, isolated, strictly read-only reader of the exact
M2 candidate stores, producing the development-interval label chronology, episode-prefix
inventory and same-date control evidence as *pending review*.

Boundaries (M3_02_FROZEN_READER_CLAUDE_TASK_20260910.md):

* Only the two hash-pinned candidate SQLite files may be connected, read-only
  (``mode=ro&immutable=1``, ``PRAGMA query_only``, authorizer denying writes/ATTACH/
  extension loading).  Paths, byte sizes and SHA-256 are verified before every
  connection and again afterwards; sidecar files (-wal/-shm/-journal) are rejected.
* Real price consumption is bounded to ``trade_date <= 2025-03-31``; decisions are
  generated only for development sessions 2023-09-04 .. 2025-03-31.  Validation and
  final-holdout OHLCVA are never selected.
* The accepted label module (``m3_labels.py``, pinned sha256) is loaded by file path
  and its policy hash is verified; nothing else from ``app`` is imported.
* Import and construction have no I/O side effects.  Every connection is logged with
  its SQL text *and* bound parameters, and ``PRAGMA query_only`` is read back.
* The real configuration is fixed: a non-synthetic ``FrozenInputs`` must equal
  ``FROZEN_M2`` field by field (sources, pins, dates, benchmark) and is validated as a
  pure comparison before any file or database action; synthetic inputs are confined to
  the authorized scratch scope and can never point at the real stores.  Output
  directories must lie inside the authorized ``claude_02`` scope.
* Outputs are pending review: empty validated ledgers, no reviewer identities.
* Review-facing packets (``packets/``) are built only from the three prefix members, the
  representative record and same-date controls/context — nothing dated after the
  representative cutoff.  Retrospective episode metadata (end, status, later selection
  transitions, censoring) lives in ``episode_audit/`` and ``episodes.json`` with an explicit
  later information time and is excluded from review input.
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import importlib.util
import io
import json
import sqlite3
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import quote

READER_VERSION = "m3_frozen_reader.v3"
OUTPUT_SCHEMA = "m3.frozen_reader.run.v1"

PROJECT_ROOT = Path(__file__).resolve().parents[3]
LABELS_MODULE_PATH = Path(__file__).resolve().with_name("m3_labels.py")
FROZEN_LABELS_SHA256 = "e20eb21cdea032ced319a8f45a34cdeb03fd4d8b357ac31403306fa73b225393"
FROZEN_POLICY_HASH = "d436ba1402f9d0b53e1008c2a2bd50678a457c3e050561a59ded30dbbd21c025"
FROZEN_POLICY_VERSION = "0.3.0-draft"

DEVELOPMENT_START = "2023-09-04"
DEVELOPMENT_END = "2025-03-31"
PRICE_CONSUMPTION_MAX_DATE = "2025-03-31"
CUTOFF_OFFSET_SECONDS = 3600  # close+3600s: Cutoff(date, date+'T16:00:00+08:00', retrospective)
CUTOFF_MODE = "retrospective"
EVIDENCE_ASSEMBLY_AT = "2026-09-10T06:52:37.442011+00:00"  # metadata index assembled_at_utc: evidence assembly time, NOT historical availability
SESSION_TZ = timezone(timedelta(hours=8))
NUMBER_FIELDS = ("open", "high", "low", "close", "volume", "amount")
M2_SOURCE = "tonghuashun"
M2_QUALITY = "qualified_candidate"

_M2_RUN = PROJECT_ROOT / "claude methods" / "_m2_codex_implementation_20260910" / "staging_runs" / "ths_v2_20260910_041710_97ef9c09" / "run_ths_v2_20260910_041710_97ef9c09"


@dataclass(frozen=True)
class SourceSpec:
    path: str
    sha256: str
    bytes: int | None = None
    kind: str = "file"

    def resolved(self) -> Path:
        return Path(self.path).resolve()


@dataclass(frozen=True)
class FrozenInputs:
    """All inputs a run may touch.  ``synthetic`` marks a fixture set (never the real stores)."""

    trading: SourceSpec
    history: SourceSpec
    qualification: SourceSpec
    calendar: SourceSpec
    universe: SourceSpec
    metadata_index: SourceSpec | None = None
    labels_sha256: str = FROZEN_LABELS_SHA256
    policy_hash: str = FROZEN_POLICY_HASH
    synthetic: bool = False
    benchmark_symbol: str = "SH000300"
    development_start: str = DEVELOPMENT_START
    development_end: str = DEVELOPMENT_END
    price_max_date: str = PRICE_CONSUMPTION_MAX_DATE
    evidence_assembly_at: str = EVIDENCE_ASSEMBLY_AT


FROZEN_M2 = FrozenInputs(
    trading=SourceSpec(str(_M2_RUN / "trading.sqlite3"), "c0b26660ab903541e7e213ee312c565be73547bb3cc8c142486999717e3edeca", 38969344, "sqlite"),
    history=SourceSpec(str(_M2_RUN / "history.sqlite3"), "eda17434ab67496c33eed275b35045c140bad72802b4dcbf981ff22422c53003", 10604544, "sqlite"),
    qualification=SourceSpec(str(_M2_RUN.parents[2] / "qualification_v2_reviewed.json"), "992bd79ce9d2e38d1a0a8ae2f9890cd26daebcd3d2ab664d5caab171ec3e0f37"),
    calendar=SourceSpec(str(PROJECT_ROOT / "backend" / ".venv" / "Lib" / "site-packages" / "akshare" / "file_fold" / "calendar.json"),
                        "f1f1ce33c5cceb5c530c3271fc951405cb5624d2f30becec85dc7a85fd47e656"),
    universe=SourceSpec(str(PROJECT_ROOT / "claude methods" / "_m1_closure" / "pilot_symbols.csv"), "97e251ae84fc927486127a96b4966ed8fc59fac0b744b7d6f186b2b1548886fe"),
    metadata_index=SourceSpec(str(PROJECT_ROOT / "claude methods" / "_m3_20260910" / "codex" / "metadata_index_01" / "index.json"),
                              "14f1bad7d393b4e15bf73111a9d96a78c8b156784f9ccbb084d6b606d3a152e9"),
)


CLAUDE_02_SCOPE = PROJECT_ROOT / "claude methods" / "_m3_20260910" / "claude_02"
SYNTHETIC_SCRATCH_SCOPE = CLAUDE_02_SCOPE / "scratch"
OUTPUT_SCOPES = (CLAUDE_02_SCOPE / "runs", SYNTHETIC_SCRATCH_SCOPE)


class ReaderError(RuntimeError):
    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


# --------------------------------------------------------------------------- #
# Fixed-configuration validation (pure comparisons; no file or database I/O)   #
# --------------------------------------------------------------------------- #


def _inside(path: Path, scope: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(scope.resolve(strict=False))
        return True
    except ValueError:
        return False


def _is_real_store_path(path: Path) -> bool:
    real = {Path(FROZEN_M2.trading.path).resolve(strict=False), Path(FROZEN_M2.history.path).resolve(strict=False)}
    return path.resolve(strict=False) in real


def validate_configuration(inputs: FrozenInputs) -> dict[str, Any]:
    """Fail closed unless the configuration is exactly the task's fixed real configuration
    (``FROZEN_M2``) or an explicitly synthetic set confined to the authorized scratch scope.
    Pure comparison: nothing is opened, hashed or stat-ed here."""
    if not isinstance(inputs, FrozenInputs) or not isinstance(inputs.synthetic, bool):
        raise ReaderError("configuration_invalid", "FrozenInputs with a bool synthetic flag required")
    if not inputs.synthetic:
        if inputs != FROZEN_M2:
            differing = sorted(name for name in FROZEN_M2.__dataclass_fields__ if getattr(inputs, name) != getattr(FROZEN_M2, name))
            raise ReaderError("real_configuration_not_frozen", "non-synthetic inputs must equal FROZEN_M2 exactly; differing: " + ",".join(differing))
        return {"mode": "real", "scope": "FROZEN_M2"}
    specs = _specs(inputs)
    for name, spec in specs.items():
        path = Path(spec.path)
        if not path.is_absolute() or not _inside(path, SYNTHETIC_SCRATCH_SCOPE):
            raise ReaderError("synthetic_source_outside_scratch_scope", f"{name}: {spec.path}")
        if _is_real_store_path(path):
            raise ReaderError("synthetic_flag_cannot_relabel_real_store", f"{name}: {spec.path}")
        if not isinstance(spec.sha256, str) or len(spec.sha256) != 64:
            raise ReaderError("configuration_invalid", f"{name}: sha256 pin required")
    if inputs.price_max_date > inputs.development_end or inputs.development_start > inputs.development_end:
        raise ReaderError("configuration_invalid", "price_max_date must not exceed development_end")
    if inputs.labels_sha256 != FROZEN_LABELS_SHA256 or inputs.policy_hash != FROZEN_POLICY_HASH:
        raise ReaderError("configuration_invalid", "synthetic runs still use the frozen label module and policy")
    return {"mode": "synthetic", "scope": str(SYNTHETIC_SCRATCH_SCOPE)}


def validate_output_dir(output_dir: str | Path) -> Path:
    """Output must lie inside the authorized claude_02 run/scratch scope (pure path check)."""
    out = Path(output_dir)
    if not out.is_absolute():
        raise ReaderError("output_dir_not_absolute", str(out))
    if not any(_inside(out, scope) for scope in OUTPUT_SCOPES) or out.resolve(strict=False) in {scope.resolve(strict=False) for scope in OUTPUT_SCOPES}:
        raise ReaderError("output_dir_outside_scope", f"{out} not inside {[str(x) for x in OUTPUT_SCOPES]}")
    return out


def _authorized_store_spec(spec: SourceSpec, inputs: FrozenInputs | None) -> str:
    """A store may be opened only for the two fixed real specs or for a validated synthetic set that lists it."""
    if inputs is None:
        if spec in (FROZEN_M2.trading, FROZEN_M2.history):
            return "real"
        raise ReaderError("store_not_authorized", "only the two frozen M2 specs may be opened without a validated synthetic configuration")
    mode = validate_configuration(inputs)["mode"]
    if spec not in (inputs.trading, inputs.history):
        raise ReaderError("store_not_authorized", f"{spec.path} is not the trading/history spec of the validated configuration")
    return mode


# --------------------------------------------------------------------------- #
# Hashing and canonical helpers (identical to the M2 staging conventions)     #
# --------------------------------------------------------------------------- #


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def hash_value(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_source(spec: SourceSpec) -> dict[str, Any]:
    """Resolve the exact path, verify byte size/hash and reject SQLite sidecars.  No connection."""
    path = spec.resolved()
    if not path.is_file():
        raise ReaderError("source_missing", str(path))
    if Path(spec.path).resolve() != path or not path.is_absolute():
        raise ReaderError("source_path_not_exact", str(path))
    size = path.stat().st_size
    if spec.bytes is not None and size != spec.bytes:
        raise ReaderError("source_size_mismatch", f"{path}: {size} != {spec.bytes}")
    digest = sha256_file(path)
    if digest != spec.sha256:
        raise ReaderError("source_hash_mismatch", f"{path}: {digest} != {spec.sha256}")
    if spec.kind == "sqlite":
        for suffix in ("-wal", "-shm", "-journal"):
            if Path(str(path) + suffix).exists():
                raise ReaderError("source_sidecar_present", str(path) + suffix)
    return {"path": str(path), "sha256": digest, "bytes": size}


# --------------------------------------------------------------------------- #
# Read-only SQLite access with an audit log                                   #
# --------------------------------------------------------------------------- #

_ALLOWED_ACTIONS = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION}
_ALLOWED_PRAGMAS = {"table_info", "table_list", "integrity_check", "quick_check", "foreign_key_check", "user_version", "journal_mode",
                    "page_count", "page_size", "schema_version", "query_only", "index_list", "index_info"}


@dataclass
class ReadLog:
    """Audit of every connection and statement (SQL text + bound parameters) of a run."""

    connections: list[dict[str, Any]] = field(default_factory=list)
    statements: list[dict[str, Any]] = field(default_factory=list)
    denied: list[str] = field(default_factory=list)

    def record(self) -> dict[str, Any]:
        distinct = sorted({canonical(st) for st in self.statements})
        return {"connections": list(self.connections), "statements": list(self.statements),
                "distinct_statements": [json.loads(x) for x in distinct], "statement_count": len(self.statements),
                "denied_actions": list(self.denied)}


class ReadOnlyStore:
    """Context manager around a verified, immutable, query-only SQLite connection.

    Construction stores configuration only (no file I/O).  Entering the context first
    authorizes the spec against the fixed real specs or a validated synthetic configuration,
    then verifies path/size/hash/sidecars, connects read-only, reads ``PRAGMA query_only``
    back, installs the authorizer and logs the connection; exiting re-verifies the file."""

    def __init__(self, spec: SourceSpec, log: ReadLog, role: str, inputs: FrozenInputs | None = None) -> None:
        if spec.kind != "sqlite":
            raise ReaderError("not_a_sqlite_source", spec.path)
        self.spec, self.log, self.role, self.inputs = spec, log, role, inputs
        self.verified: dict[str, Any] | None = None
        self.conn: sqlite3.Connection | None = None
        self.log_index: int | None = None

    def __enter__(self) -> "ReadOnlyStore":
        mode = _authorized_store_spec(self.spec, self.inputs)
        self.verified = verify_source(self.spec)
        uri = "file:" + quote(Path(self.verified["path"]).as_posix(), safe="/:") + "?mode=ro&immutable=1"
        conn = sqlite3.connect(uri, uri=True, isolation_level=None)
        try:
            conn.enable_load_extension(False)
        except AttributeError:  # extension loading unavailable in this build: nothing to disable
            pass
        conn.execute("PRAGMA query_only=ON")
        query_only = conn.execute("PRAGMA query_only").fetchone()[0]
        if query_only != 1:
            conn.close()
            raise ReaderError("query_only_not_effective", str(query_only))
        conn.set_authorizer(self._authorize)
        self.conn = conn
        self.log_index = len(self.log.connections)
        self.log.connections.append({"role": self.role, "mode": mode, "path": self.verified["path"], "sha256_before": self.verified["sha256"],
                                     "bytes": self.verified["bytes"], "uri_flags": "mode=ro&immutable=1", "query_only_read_back": query_only,
                                     "authorizer": "select/read/function/pragma-read only"})
        return self

    def __exit__(self, *exc: Any) -> None:
        if self.conn is not None:
            self.conn.close()
            self.conn = None
        after = verify_source(self.spec)
        if self.log_index is not None:
            self.log.connections[self.log_index]["sha256_after"] = after["sha256"]

    def _authorize(self, action: int, arg1: Any, arg2: Any, dbname: Any, source: Any) -> int:
        if action in _ALLOWED_ACTIONS:
            return sqlite3.SQLITE_OK
        if action == sqlite3.SQLITE_PRAGMA and arg1 in _ALLOWED_PRAGMAS and arg2 is None:
            return sqlite3.SQLITE_OK
        self.log.denied.append(f"action={action} arg1={arg1!r} arg2={arg2!r}")
        return sqlite3.SQLITE_DENY

    def rows(self, sql: str, params: Sequence[Any] = ()) -> list[tuple]:
        assert self.conn is not None
        self.log.statements.append({"connection": self.role, "sql": " ".join(sql.split()), "params": list(params)})
        return self.conn.execute(sql, params).fetchall()

    def one(self, sql: str, params: Sequence[Any] = ()) -> Any:
        return self.rows(sql, params)[0][0]


# --------------------------------------------------------------------------- #
# Frozen label module                                                         #
# --------------------------------------------------------------------------- #

_LABELS_CACHE: dict[str, Any] = {}


def load_labels(expected_sha256: str = FROZEN_LABELS_SHA256, expected_policy_hash: str = FROZEN_POLICY_HASH) -> Any:
    """Load the accepted label module by file path and verify its pins (fail closed)."""
    key = f"{expected_sha256}:{expected_policy_hash}"
    if key in _LABELS_CACHE:
        return _LABELS_CACHE[key]
    actual = sha256_file(LABELS_MODULE_PATH)
    if actual != expected_sha256:
        raise ReaderError("labels_module_not_frozen", f"{LABELS_MODULE_PATH}: {actual} != {expected_sha256}")
    name = "m3_labels_frozen_" + expected_sha256[:12]
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, LABELS_MODULE_PATH)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    module = sys.modules[name]
    if module.POLICY_HASH != expected_policy_hash or module.POLICY_VERSION != FROZEN_POLICY_VERSION:
        raise ReaderError("policy_not_frozen", f"{module.POLICY_HASH} / {module.POLICY_VERSION}")
    module.assert_policy_integrity()
    _LABELS_CACHE[key] = module
    return module


# --------------------------------------------------------------------------- #
# Frozen metadata loading                                                     #
# --------------------------------------------------------------------------- #


def load_calendar(spec: SourceSpec) -> list[str]:
    verify_source(spec)
    raw = json.loads(Path(spec.path).read_text(encoding="utf-8"))
    sessions = []
    for item in raw:
        text = str(item)
        iso = f"{text[:4]}-{text[4:6]}-{text[6:8]}" if len(text) == 8 and text.isdigit() else text[:10]
        sessions.append(iso)
    if sessions != sorted(set(sessions)):
        raise ReaderError("calendar_not_sorted_unique", spec.path)
    return sessions


def load_universe(spec: SourceSpec) -> list[dict[str, str]]:
    verify_source(spec)
    with open(spec.path, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        if not row.get("symbol") or row.get("stratum") is None:
            raise ReaderError("universe_row_malformed", canonical(row))
    return rows


def load_json(spec: SourceSpec) -> Any:
    verify_source(spec)
    return json.loads(Path(spec.path).read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# Reconciliation of the two stores against the frozen qualification          #
# --------------------------------------------------------------------------- #


@dataclass
class Reconciliation:
    price_rows: dict[str, list[dict[str, Any]]] = field(default_factory=dict)      # symbol -> validated permitted price rows
    suspensions: dict[str, list[dict[str, Any]]] = field(default_factory=dict)     # symbol -> validated permitted suspension rows
    exclusions: list[dict[str, Any]] = field(default_factory=list)                 # row-level exclusions (symbol, date, reason)
    problems: list[str] = field(default_factory=list)                              # structural problems (run refused)
    counts: dict[str, Any] = field(default_factory=dict)
    scopes: dict[str, dict[str, Any]] = field(default_factory=dict)
    ledger: dict[tuple[str, str], dict[str, Any]] = field(default_factory=dict)


def _exclude(rec: Reconciliation, symbol: str, date: str, reason: str, detail: str = "") -> None:
    rec.exclusions.append({"symbol": symbol, "trade_date": date, "reason": reason, "detail": detail})


def reconcile(inputs: FrozenInputs, log: ReadLog) -> Reconciliation:
    """Row-level reconciliation of trading.daily_bar_cache against history.daily_bars, row_evidence lineage,
    qualification records, coverage inventory and suspension records, restricted to trade_date <= price_max_date."""
    validate_configuration(inputs)
    rec = Reconciliation()
    qualification = load_json(inputs.qualification)
    scopes = {s["symbol"]: s for s in qualification["scopes"]}
    rec.scopes = scopes
    for gap in qualification["suspension_ledger"]:
        rec.ledger[(gap["symbol"], gap["date"])] = gap
    max_date = inputs.price_max_date
    with ReadOnlyStore(inputs.trading, log, "trading", inputs) as trading, ReadOnlyStore(inputs.history, log, "history", inputs) as history:
        # structural checks (metadata only)
        counts = {
            "trading_rows_total": trading.one("SELECT COUNT(*) FROM daily_bar_cache"),
            "history_rows_total": history.one("SELECT COUNT(*) FROM daily_bars"),
            "trading_rows_permitted": trading.one("SELECT COUNT(*) FROM daily_bar_cache WHERE trade_date <= ?", (max_date,)),
            "history_rows_permitted": history.one("SELECT COUNT(*) FROM daily_bars WHERE trade_date <= ?", (max_date,)),
            "trading_rows_beyond_permitted_not_selected": trading.one("SELECT COUNT(*) FROM daily_bar_cache WHERE trade_date > ?", (max_date,)),
            "row_evidence_total": trading.one("SELECT COUNT(*) FROM row_evidence"),
            "suspension_records_trading": trading.one("SELECT COUNT(*) FROM suspension_records"),
            "suspension_records_history": history.one("SELECT COUNT(*) FROM suspension_records"),
            "coverage_trading": trading.one("SELECT COUNT(*) FROM coverage_inventory"),
            "coverage_history": history.one("SELECT COUNT(*) FROM coverage_inventory"),
            "qualification_records": trading.one("SELECT COUNT(*) FROM qualification_records"),
            "instruments": trading.one("SELECT COUNT(*) FROM instruments"),
            "ingest_runs": history.one("SELECT COUNT(*) FROM ingest_runs"),
        }
        rec.counts = counts
        if counts["trading_rows_total"] != counts["history_rows_total"] or counts["trading_rows_total"] != counts["row_evidence_total"]:
            rec.problems.append(f"row_count_mismatch:{counts['trading_rows_total']}/{counts['history_rows_total']}/{counts['row_evidence_total']}")
        if counts["suspension_records_trading"] != counts["suspension_records_history"] or counts["coverage_trading"] != counts["coverage_history"]:
            rec.problems.append("suspension_or_coverage_count_mismatch_between_stores")
        contract_t = trading.rows("SELECT contract_json FROM dataset_contract")
        contract_h = history.rows("SELECT contract_json FROM dataset_contract")
        if len(contract_t) != 1 or len(contract_h) != 1 or contract_t != contract_h:
            rec.problems.append("dataset_contract_mismatch_between_stores")
        counts["dataset_contract_sha256"] = hash_value(json.loads(contract_t[0][0])) if len(contract_t) == 1 else None
        # qualification records must equal the frozen per-symbol scopes
        stored_qual = {}
        for symbol, sha, rec_json in trading.rows("SELECT symbol, record_sha256, record_json FROM qualification_records"):
            scope = scopes.get(symbol)
            if scope is None:
                rec.problems.append(f"qualification_record_without_frozen_scope:{symbol}")
                continue
            if sha != hash_value(scope) or rec_json != canonical(scope):
                rec.problems.append(f"qualification_record_mismatch:{symbol}")
            stored_qual[symbol] = sha
        for symbol in scopes:
            if symbol not in stored_qual:
                rec.problems.append(f"frozen_scope_without_qualification_record:{symbol}")
        instruments = {s for (s,) in trading.rows("SELECT symbol FROM instruments")}
        if instruments != set(scopes):
            rec.problems.append("instruments_differ_from_frozen_scopes")
        if rec.problems:
            return rec

        # permitted rows (never select OHLCVA beyond price_max_date)
        t_rows = trading.rows("SELECT symbol, trade_date, open, high, low, close, volume, amount, source, quality_status, adjustment_mode, volume_unit "
                              "FROM daily_bar_cache WHERE trade_date <= ? ORDER BY symbol, trade_date", (max_date,))
        h_rows = history.rows("SELECT symbol, trade_date, adjustment_mode, open, high, low, close, volume, amount, provider, fetched_at, ingest_run_id "
                              "FROM daily_bars WHERE trade_date <= ? ORDER BY symbol, trade_date", (max_date,))
        ev_rows = trading.rows("SELECT symbol, trade_date, raw_sha256, request_sha256, producer_sha256, parser_sha256, capture_receipt_sha256, "
                               "capture_producer_manifest_sha256, observed_at, point_index, qualification_sha256, source_name, source_name_status "
                               "FROM row_evidence WHERE trade_date <= ? ORDER BY symbol, trade_date", (max_date,))
        cov_t = trading.rows("SELECT symbol, trade_date, classification FROM coverage_inventory WHERE trade_date <= ? ORDER BY symbol, trade_date", (max_date,))
        cov_h = history.rows("SELECT symbol, trade_date, classification FROM coverage_inventory WHERE trade_date <= ? ORDER BY symbol, trade_date", (max_date,))
        sus_t = trading.rows("SELECT symbol, trade_date, evidence_sha256, record_json FROM suspension_records WHERE trade_date <= ? ORDER BY symbol, trade_date", (max_date,))
        sus_h = history.rows("SELECT symbol, trade_date, evidence_sha256, record_json FROM suspension_records WHERE trade_date <= ? ORDER BY symbol, trade_date", (max_date,))

    h_map = {(r[0], r[1]): r for r in h_rows}
    price_keys_all = {(r[0], r[1]) for r in t_rows}
    ev_map = {(r[0], r[1]): r for r in ev_rows}
    cov_map_t = {(r[0], r[1]): r[2] for r in cov_t}
    cov_map_h = {(r[0], r[1]): r[2] for r in cov_h}
    sus_map_t = {(r[0], r[1]): r for r in sus_t}
    sus_map_h = {(r[0], r[1]): r for r in sus_h}
    if cov_map_t != cov_map_h:
        rec.problems.append("coverage_inventory_differs_between_stores")
    if {k: (v[2], v[3]) for k, v in sus_map_t.items()} != {k: (v[2], v[3]) for k, v in sus_map_h.items()}:
        rec.problems.append("suspension_records_differ_between_stores")
    if rec.problems:
        return rec

    accepted_price_keys: set[tuple[str, str]] = set()
    for row in t_rows:
        symbol, date = row[0], row[1]
        numbers = row[2:8]
        source, quality, adjustment, volume_unit = row[8], row[9], row[10], row[11]
        scope = scopes.get(symbol)
        key = (symbol, date)
        if scope is None:
            _exclude(rec, symbol, date, "symbol_without_frozen_scope")
            continue
        h = h_map.get(key)
        if h is None:
            _exclude(rec, symbol, date, "missing_in_history")
            continue
        if any(not isinstance(v, (int, float)) or v != v for v in numbers):
            _exclude(rec, symbol, date, "nonfinite_or_null_numeric")
            continue
        if tuple(numbers) != tuple(h[3:9]):
            _exclude(rec, symbol, date, "numeric_mismatch_between_stores", canonical({"trading": list(numbers), "history": list(h[3:9])}))
            continue
        if adjustment != "none" or h[2] != "none":
            _exclude(rec, symbol, date, "adjustment_mode_not_none", f"{adjustment}/{h[2]}")
            continue
        if quality != M2_QUALITY:
            _exclude(rec, symbol, date, "quality_status_not_qualified", str(quality))
            continue
        if source != M2_SOURCE or h[9] != M2_SOURCE:
            _exclude(rec, symbol, date, "source_provider_mismatch", f"{source}/{h[9]}")
            continue
        if volume_unit != scope["volume_unit"]:
            _exclude(rec, symbol, date, "volume_unit_mismatch_with_scope", f"{volume_unit} vs {scope['volume_unit']}")
            continue
        ev = ev_map.get(key)
        if ev is None:
            _exclude(rec, symbol, date, "row_evidence_missing")
            continue
        raw, request, producer, parser, receipt, manifest, observed_at, point_index, qual_sha = ev[2:11]
        if not all(isinstance(x, str) and len(x) == 64 for x in (raw, request, producer, parser, receipt, manifest)):
            _exclude(rec, symbol, date, "row_evidence_lineage_malformed")
            continue
        capture = next((c for c in scope["captures"] if c["raw_sha256"] == raw and c["request_sha256"] == request and c["producer_sha256"] == producer
                        and c["parser_sha256"] == parser and c["capture_receipt_sha256"] == receipt and c["capture_producer_manifest_sha256"] == manifest), None)
        if capture is None:
            _exclude(rec, symbol, date, "row_evidence_lineage_not_in_frozen_capture")
            continue
        if not isinstance(point_index, int) or point_index < 0 or point_index >= capture["rows"]:
            _exclude(rec, symbol, date, "point_index_out_of_capture_range", str(point_index))
            continue
        if observed_at != h[10] or observed_at != capture["observed_at"]:
            _exclude(rec, symbol, date, "observed_at_fetched_at_mismatch", f"{observed_at}/{h[10]}/{capture['observed_at']}")
            continue
        if qual_sha != hash_value(scope):
            _exclude(rec, symbol, date, "qualification_sha_mismatch")
            continue
        if date not in scope["expected_price_dates"]:
            _exclude(rec, symbol, date, "price_key_not_expected_by_scope")
            continue
        if key in sus_map_t:
            _exclude(rec, symbol, date, "price_and_suspension_conflict")
            continue
        if cov_map_t.get(key) != "price":
            _exclude(rec, symbol, date, "coverage_classification_not_price", str(cov_map_t.get(key)))
            continue
        accepted_price_keys.add(key)
        rec.price_rows.setdefault(symbol, []).append({
            "symbol": symbol, "trade_date": date, "open": numbers[0], "high": numbers[1], "low": numbers[2], "close": numbers[3],
            "volume": numbers[4], "amount": numbers[5], "volume_unit": volume_unit, "amount_unit": scope["amount_unit"],
            "observed_at": observed_at, "raw_sha256": raw, "point_index": point_index, "capture_receipt_sha256": receipt,
            "qualification_sha256": qual_sha, "ingest_run_id": h[11],
        })
    # history rows without trading counterpart
    for key in h_map:
        if key not in price_keys_all:
            _exclude(rec, key[0], key[1], "missing_in_trading")
    # expected price dates absent from the store (permitted range)
    for symbol, scope in scopes.items():
        for date in scope["expected_price_dates"]:
            if date <= max_date and (symbol, date) not in accepted_price_keys and not any(e["symbol"] == symbol and e["trade_date"] == date for e in rec.exclusions):
                _exclude(rec, symbol, date, "expected_price_key_missing_from_store")
    # suspensions
    for key, (symbol, date, evidence_sha, record_json) in sus_map_t.items():
        gap = rec.ledger.get(key)
        if gap is None:
            _exclude(rec, symbol, date, "suspension_not_in_frozen_ledger")
            continue
        if evidence_sha != hash_value(gap) or record_json != canonical(gap):
            _exclude(rec, symbol, date, "suspension_evidence_hash_mismatch")
            continue
        if cov_map_t.get(key) != "full_day_suspension":
            _exclude(rec, symbol, date, "coverage_classification_not_suspension", str(cov_map_t.get(key)))
            continue
        if key in price_keys_all:
            _exclude(rec, symbol, date, "price_and_suspension_conflict")
            continue
        scope = scopes.get(symbol)
        if scope is None or date not in scope["suspended_dates"]:
            _exclude(rec, symbol, date, "suspension_not_expected_by_scope")
            continue
        rec.suspensions.setdefault(symbol, []).append({"symbol": symbol, "trade_date": date, "evidence_sha256": evidence_sha,
                                                       "status": gap.get("status"), "window": gap.get("window"),
                                                       "document_sha256": [e.get("sha256") for e in gap.get("evidence", [])]})
    for symbol, scope in scopes.items():
        for date in scope["suspended_dates"]:
            if date <= max_date and (symbol, date) not in sus_map_t:
                _exclude(rec, symbol, date, "expected_suspension_missing_from_store")
    # coverage keys must be exactly the accepted price + suspension keys (permitted range)
    already = {(e["symbol"], e["trade_date"]) for e in rec.exclusions}
    stray = [k for k in cov_map_t if k not in accepted_price_keys and k not in sus_map_t and k not in already]
    for symbol, date in stray:
        _exclude(rec, symbol, date, "coverage_key_without_price_or_suspension")
    rec.counts.update({
        "permitted_price_rows_accepted": len(accepted_price_keys),
        "permitted_suspensions_accepted": sum(len(v) for v in rec.suspensions.values()),
        "row_exclusions": len(rec.exclusions),
        "symbols_with_rows": len(rec.price_rows),
    })
    return rec


# --------------------------------------------------------------------------- #
# Context assembly (listing, events, coverage) — all from frozen metadata     #
# --------------------------------------------------------------------------- #


def _iso_dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


def cutoff_for(m: Any, date: str, offset_seconds: int = CUTOFF_OFFSET_SECONDS) -> Any:
    return m.Cutoff(date, (m.close_time(date) + timedelta(seconds=offset_seconds)).isoformat(), CUTOFF_MODE)


def known_events(metadata_index: Mapping[str, Any] | None, qualification: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Partial known cash events per symbol, cross-checked against the frozen qualification controls."""
    events: dict[str, list[dict[str, Any]]] = {}
    if metadata_index is not None:
        for inst in metadata_index.get("instruments", []):
            if inst.get("known_cash_events"):
                events[inst["symbol"]] = [{"ex_date": e["ex_date"], "cash_per_share_CNY": e.get("cash_per_share_CNY"),
                                          "document_sha256": e.get("document_sha256"), "event_type": e.get("event_type")}
                                         for e in inst["known_cash_events"]]
    for symbol, control in qualification.get("controls", {}).items():
        ex_dates = sorted(b["ex_date"] for b in control.get("boundaries", []))
        indexed = sorted(e["ex_date"] for e in events.get(symbol, []))
        if metadata_index is not None and ex_dates != indexed:
            raise ReaderError("known_events_disagree_with_frozen_qualification", f"{symbol}: {ex_dates} vs {indexed}")
        if metadata_index is None:
            events[symbol] = [{"ex_date": d, "cash_per_share_CNY": None, "document_sha256": None, "event_type": "cash_implementation"} for d in ex_dates]
    return events


def security_context_for(m: Any, symbol: str, listing: Mapping[str, Any], events: Sequence[Mapping[str, Any]], cutoff_date: str,
                         evidence_assembly_at: str) -> Any:
    """Facts consumable at ``cutoff_date``: listing date (frozen pilot metadata / official BJ fact) and the partial known
    cash events with ex_date <= cutoff.  Availability is the evidence-assembly time (2026), never historical availability.
    ST status, float shares, turnover and names stay unknown."""
    known = [e for e in events if e["ex_date"] <= cutoff_date]
    refs = [listing["evidence_ref"]] + [f"document_sha256:{e['document_sha256']}" if e.get("document_sha256") else f"frozen_qualification_control_boundary:{e['ex_date']}" for e in known]
    status = m.CA_PARTIAL_KNOWN if events else m.CA_UNKNOWN
    return m.SecurityContext(listing_date=listing["listing_date"], name=None, st_status="unknown", corporate_action_status=status,
                             known_ex_dates=tuple(e["ex_date"] for e in known), float_shares=None, turnover_available=False,
                             evidence_refs=tuple(refs), facts_available_at=evidence_assembly_at)


def observations_for(m: Any, symbol: str, price_rows: Sequence[Mapping[str, Any]], suspensions: Sequence[Mapping[str, Any]],
                     max_date: str, benchmark: bool) -> list[Any]:
    """Observations up to ``max_date`` in trade-date order.  source_ref = trade_date#point_index (row_evidence PK + point index)."""
    obs = []
    for r in price_rows:
        if r["trade_date"] > max_date:
            continue
        obs.append(m.Observation(symbol=symbol, trade_date=r["trade_date"], kind="price", available_at=r["observed_at"],
                                 source_ref=f"{r['trade_date']}#{r['point_index']}", open=r["open"], high=r["high"], low=r["low"], close=r["close"],
                                 volume=r["volume"], amount=r["amount"], adjustment_mode="none",
                                 volume_unit=r["volume_unit"], amount_unit=r["amount_unit"]))
    if not benchmark:
        for s in suspensions:
            if s["trade_date"] > max_date:
                continue
            obs.append(m.Observation(symbol=symbol, trade_date=s["trade_date"], kind="full_day_suspension",
                                     available_at=EVIDENCE_ASSEMBLY_AT, source_ref=f"suspension#{s['evidence_sha256'][:16]}"))
    obs.sort(key=lambda o: o.trade_date)
    return obs


# --------------------------------------------------------------------------- #
# Deterministic output helpers                                                #
# --------------------------------------------------------------------------- #


def write_json(path: Path, payload: Any) -> str:
    """Deterministic JSON (sorted keys, LF newlines, UTF-8 bytes) and its SHA-256."""
    data = (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def write_jsonl_gz(path: Path, records: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Deterministic gzip (mtime=0, no filename) of one canonical JSON line per record."""
    buffer = io.BytesIO()
    count = 0
    plain = hashlib.sha256()
    with gzip.GzipFile(fileobj=buffer, mode="wb", mtime=0, filename="") as gz:
        for record in records:
            line = (canonical(record) + "\n").encode("utf-8")
            plain.update(line)
            gz.write(line)
            count += 1
    data = buffer.getvalue()
    path.write_bytes(data)
    return {"path": str(path), "records": count, "sha256_gzip": hashlib.sha256(data).hexdigest(), "sha256_jsonl": plain.hexdigest(), "bytes": len(data)}


def read_jsonl_gz(path: Path) -> list[dict[str, Any]]:
    with gzip.open(path, "rb") as gz:
        return [json.loads(line) for line in gz.read().decode("utf-8").splitlines() if line]


# --------------------------------------------------------------------------- #
# The development run                                                         #
# --------------------------------------------------------------------------- #


def run_development(output_dir: str | Path, inputs: FrozenInputs = FROZEN_M2, symbols: Sequence[str] | None = None,
                    now_utc: str | None = None) -> dict[str, Any]:
    """Execute the bounded development run into a fresh directory inside the authorized scope
    (refuses to overwrite).  The configuration and the output scope are validated as pure
    comparisons before any file is hashed, read or written."""
    configuration = validate_configuration(inputs)
    out = validate_output_dir(output_dir)
    if out.exists():
        raise ReaderError("output_dir_exists", str(out))
    log = ReadLog()
    m = load_labels(inputs.labels_sha256, inputs.policy_hash)
    pins_before = {name: verify_source(spec) for name, spec in _specs(inputs).items()}
    calendar_sessions = load_calendar(inputs.calendar)
    universe_rows = load_universe(inputs.universe)
    qualification = load_json(inputs.qualification)
    metadata_index = load_json(inputs.metadata_index) if inputs.metadata_index is not None else None
    events = known_events(metadata_index, qualification)
    rec = reconcile(inputs, log)
    out.mkdir(parents=True)
    (out / "chronology").mkdir()
    (out / "packets").mkdir()
    (out / "episode_audit").mkdir()
    receipt: dict[str, Any] = {"schema": OUTPUT_SCHEMA, "reader_version": READER_VERSION, "reader_sha256": sha256_file(Path(__file__)),
                               "configuration": configuration, "output_dir": str(out),
                               "labels_sha256": inputs.labels_sha256, "policy_hash": m.POLICY_HASH, "policy_version": m.POLICY_VERSION,
                               "synthetic": inputs.synthetic, "inputs": pins_before, "development": [inputs.development_start, inputs.development_end],
                               "price_consumption_max_date": inputs.price_max_date, "cutoff_mode": CUTOFF_MODE,
                               "cutoff_convention": f"close+{CUTOFF_OFFSET_SECONDS}s", "evidence_assembly_at": inputs.evidence_assembly_at,
                               "evidence_assembly_at_is_historical_availability": False, "strict_pit": False, "training_eligible": False,
                               "review_only": True, "live_trading_enabled": False, "reconciliation_counts": rec.counts,
                               "structural_problems": rec.problems, "started_at_utc": now_utc}
    write_json(out / "exclusions.json", {"schema": "m3.frozen_reader.exclusions.v1", "row_exclusions": rec.exclusions, "structural_problems": rec.problems})
    if rec.problems:
        receipt["status"] = "refused_structural_problems"
        receipt["read_log"] = log.record()
        write_json(out / "run_receipt.json", receipt)
        return receipt

    # calendar slice: sessions from the earliest permitted observation to the development end
    first_obs = min((r["trade_date"] for rows in rec.price_rows.values() for r in rows), default=inputs.development_start)
    sessions = tuple(d for d in calendar_sessions if first_obs <= d <= inputs.development_end)
    calendar = m.SessionCalendar(sessions, f"{Path(inputs.calendar.path).name} sha256={inputs.calendar.sha256} slice {sessions[0]}..{sessions[-1]}",
                                 inputs.evidence_assembly_at, synthetic=inputs.synthetic)
    dev_sessions = [d for d in sessions if inputs.development_start <= d <= inputs.development_end]
    stocks = [r for r in universe_rows if r["stratum"] != "benchmark"]
    benchmarks = [r["symbol"] for r in universe_rows if r["stratum"] == "benchmark"]
    if inputs.benchmark_symbol not in benchmarks:
        raise ReaderError("benchmark_not_in_universe", inputs.benchmark_symbol)
    universe = m.FrozenUniverse(frozenset(r["symbol"] for r in stocks), f"{Path(inputs.universe.path).name} sha256={inputs.universe.sha256}", inputs.universe.sha256)
    listing_grade = {}
    if metadata_index is not None:
        for inst in metadata_index.get("instruments", []):
            ev = inst.get("listing_evidence") or {}
            listing_grade[inst["symbol"]] = ev.get("identity_kind") or ev.get("status") or "unknown"
    listings = {}
    for r in stocks:
        grade = listing_grade.get(r["symbol"], "retained_pilot_metadata_only")
        listings[r["symbol"]] = {"listing_date": r["list_date"] or None, "source_grade": grade,
                                 "evidence_ref": f"pilot_symbols.csv sha256={inputs.universe.sha256} list_date; grade={grade}"}
    selected = [r["symbol"] for r in stocks if symbols is None or r["symbol"] in set(symbols)]

    # cohort coverage per development session (evidence keys / expected listed frozen stocks; benchmarks excluded)
    price_keys = {(s, r["trade_date"]) for s, rows in rec.price_rows.items() for r in rows}
    susp_keys = {(s, r["trade_date"]) for s, rows in rec.suspensions.items() for r in rows}
    cohort: dict[str, dict[str, Any]] = {}
    for d in dev_sessions:
        expected = [r["symbol"] for r in stocks if listings[r["symbol"]]["listing_date"] and listings[r["symbol"]]["listing_date"] <= d]
        prices = sum(1 for s in expected if (s, d) in price_keys)
        susp = sum(1 for s in expected if (s, d) in susp_keys)
        cohort[d] = {"expected_listed_frozen_stocks": len(expected), "valid_price_keys": prices, "evidenced_suspension_keys": susp,
                     "evidence_key_coverage": (prices + susp) / len(expected) if expected else None,
                     "price_availability": prices / len(expected) if expected else None,
                     "denominator": "frozen pilot stocks with listing_date <= session (50-stock universe, benchmarks excluded)",
                     "observation_time": inputs.evidence_assembly_at}

    # benchmark observations (price-only regime input; retained not_applicable units)
    bench_obs_all = observations_for(m, inputs.benchmark_symbol, rec.price_rows.get(inputs.benchmark_symbol, []), [], inputs.price_max_date, benchmark=True)

    chronology_index: dict[str, Any] = {}
    summaries: dict[str, dict[str, dict[str, Any]]] = {}   # date -> symbol -> case_summary
    offsets: dict[str, dict[str, int]] = {}                # symbol -> date -> line offset in the uncompressed JSONL
    decision_exclusions: list[dict[str, Any]] = []
    waterfall: dict[str, Any] = {"expected_stock_session_keys": 0, "not_listed": 0, "no_observations_before_cutoff": 0, "records_generated": 0,
                                 "current_state": {"observed": 0, "suspended": 0, "missing": 0}, "phase": {}, "selection": {},
                                 "quality_gate_reasons": {}, "strict_pit_eligible": 0, "training_eligible": 0}
    inventory: dict[str, Any] = {}
    all_records_by_symbol: dict[str, list[dict[str, Any]]] = {}
    for symbol in selected:
        listing = listings[symbol]
        price_rows = rec.price_rows.get(symbol, [])
        susp_rows = rec.suspensions.get(symbol, [])
        obs_all = observations_for(m, symbol, price_rows, susp_rows, inputs.price_max_date, benchmark=False)
        records: list[dict[str, Any]] = []
        inv = {"symbol": symbol, "listing_date": listing["listing_date"], "listing_source_grade": listing["source_grade"],
               "permitted_price_rows": len(price_rows), "permitted_suspensions": len(susp_rows),
               "first_permitted_observation": obs_all[0].trade_date if obs_all else None, "last_permitted_observation": obs_all[-1].trade_date if obs_all else None,
               "development_sessions_expected": 0, "development_sessions_listed": 0, "records": 0, "excluded_not_listed": 0,
               "excluded_no_observations": 0, "warmup_shortfall_at_first_decision": None, "known_cash_events_total_retained": len(events.get(symbol, [])),
               "known_cash_events_in_development": sorted(e["ex_date"] for e in events.get(symbol, []) if inputs.development_start <= e["ex_date"] <= inputs.development_end)}
        for d in dev_sessions:
            waterfall["expected_stock_session_keys"] += 1
            inv["development_sessions_expected"] += 1
            if listing["listing_date"] is None or d < listing["listing_date"]:
                waterfall["not_listed"] += 1
                inv["excluded_not_listed"] += 1
                decision_exclusions.append({"symbol": symbol, "trade_date": d, "reason": "not_listed"})
                continue
            inv["development_sessions_listed"] += 1
            obs = [o for o in obs_all if o.trade_date <= d]
            if not obs:
                waterfall["no_observations_before_cutoff"] += 1
                inv["excluded_no_observations"] += 1
                decision_exclusions.append({"symbol": symbol, "trade_date": d, "reason": "no_observations_before_cutoff"})
                continue
            bench_obs = [o for o in bench_obs_all if o.trade_date <= d]
            cov = cohort[d]
            coverage = m.Coverage(cov["evidence_key_coverage"], f"m3_frozen_reader cohort {d}: {cov['valid_price_keys']}+{cov['evidenced_suspension_keys']}/{cov['expected_listed_frozen_stocks']}",
                                  inputs.evidence_assembly_at) if cov["evidence_key_coverage"] is not None else None
            request = m.LabelRequest(symbol=symbol, observations=obs, cutoff=cutoff_for(m, d), calendar=calendar,
                                     security=security_context_for(m, symbol, listing, events.get(symbol, []), d, inputs.evidence_assembly_at),
                                     benchmark_symbol=inputs.benchmark_symbol if bench_obs else None, benchmark_observations=bench_obs,
                                     universe_coverage_on_decision_date=coverage, synthetic=inputs.synthetic, universe=universe)
            record = m.generate_labels(request)
            m.verify_record(record)
            m.validate_ledger(record)
            if inv["warmup_shortfall_at_first_decision"] is None:
                inv["warmup_shortfall_at_first_decision"] = max(0, m.POLICY["windows"]["warmup_required_sessions"] - record["features"]["bars_available"])
            consumed = [o for o in obs if o.kind == "price"]
            envelope = {"record": record,
                        "source_map": {"consumed_price_keys": len(consumed), "first_consumed": consumed[0].trade_date if consumed else None,
                                       "last_consumed": consumed[-1].trade_date if consumed else None,
                                       "consumed_lineage_sha256": hashlib.sha256("\n".join(f"{o.trade_date}|{o.source_ref}" for o in obs).encode()).hexdigest(),
                                       "benchmark_symbol": inputs.benchmark_symbol if bench_obs else None, "benchmark_consumed_keys": len(bench_obs),
                                       "row_evidence_lookup": "trading.row_evidence(symbol, trade_date) -> raw_sha256/point_index equals source_ref trade_date#point_index"}}
            records.append(envelope)
            waterfall["records_generated"] += 1
            waterfall["current_state"][record["current_state"]] += 1
            _bump(waterfall["phase"], record["labels"]["phase"]["label"])
            _bump(waterfall["selection"], record["labels"]["selection"]["label"])
            if record["labels"]["phase"]["rule"] == "quality_gate":
                for reason in record["labels"]["phase"]["reasons"]:
                    _bump(waterfall["quality_gate_reasons"], reason.split(":")[0])
            waterfall["strict_pit_eligible"] += int(record["pit"]["strict_pit_eligible"])
            waterfall["training_eligible"] += int(record["pit"]["training_eligible"])
            summaries.setdefault(d, {})[symbol] = m.case_summary(record)
        inv["records"] = len(records)
        inventory[symbol] = inv
        all_records_by_symbol[symbol] = [e["record"] for e in records]
        info = write_jsonl_gz(out / "chronology" / f"{symbol}.jsonl.gz", records)
        chronology_index[symbol] = {k: v for k, v in info.items() if k != "path"}
        offsets[symbol] = {e["record"]["cutoff"]["decision_date"]: i for i, e in enumerate(records)}

    # episodes, prefix proofs, controls, packets
    episodes_out: list[dict[str, Any]] = []
    packets_index: list[dict[str, Any]] = []
    controls_out: dict[str, Any] = {}
    control_uses: dict[str, int] = {}
    waterfall.update({"episodes_total": 0, "episodes_by_phase": {}, "accumulation_episodes": 0, "accumulation_duration_established": 0,
                      "representatives_candidate": 0, "representatives_not_candidate": 0, "matched_3_to_5_controls": 0, "unmatched": 0,
                      "pending_review": 0, "independently_reviewed": 0, "qualified_reviewed_positive_episodes": 0})
    qualified_episode_summaries: list[dict[str, Any]] = []
    for symbol in selected:
        records = all_records_by_symbol.get(symbol) or []
        if not records:
            continue
        episodes = m.build_episodes(records, calendar)
        for ep in episodes:
            waterfall["episodes_total"] += 1
            _bump(waterfall["episodes_by_phase"], ep["phase"])
            entry = {k: ep[k] for k in ("symbol", "phase", "kind", "start", "end", "sessions", "selection_at_start", "selection_at_end", "eligibility_changes",
                                        "candidate_sessions", "min_duration_established_at", "closed_reason", "status", "meets_min_sessions",
                                        "episode_key", "episode_content_hash", "member_episode_ids", "member_record_hashes", "selection_path",
                                        "start_session_index", "end_session_index")}
            if ep["phase"] != m.PHASE_ACCUMULATION:
                episodes_out.append(entry)
                continue
            waterfall["accumulation_episodes"] += 1
            proof = m.episode_prefix_proof(ep)
            entry["prefix_proof"] = proof
            if proof is None:
                entry["packet"] = None
                entry["exclusion"] = "duration_not_established"
                episodes_out.append(entry)
                continue
            waterfall["accumulation_duration_established"] += 1
            rep_date = proof["established_at"]
            rep_line = offsets[symbol][rep_date]
            rep = records[rep_line]
            if rep["record_hash"] != proof["representative_record_hash"]:
                raise ReaderError("representative_binding_mismatch", f"{symbol} {rep_date}")
            member_lines = [offsets[symbol][d] for d in _member_dates(records, offsets[symbol], proof)]
            prefix_records = [records[i] for i in member_lines]
            pool_summaries = [s for sym, s in sorted(summaries.get(rep_date, {}).items()) if sym != symbol]
            pool_records = [all_records_by_symbol[s["symbol"]][offsets[s["symbol"]][rep_date]] for s in pool_summaries]
            packet = build_cutoff_packet(m, ep, proof, prefix_records, rep, pool_records, listings[symbol]["source_grade"], symbol, inputs.synthetic)
            if packet["match"] is None:
                waterfall["representatives_not_candidate"] += 1
            else:
                waterfall["representatives_candidate"] += 1
                m.revalidate_match(packet["match"], m.RecordRegistry([rep] + pool_records))
                if packet["match"]["unmatched"]:
                    waterfall["unmatched"] += 1
                else:
                    waterfall["matched_3_to_5_controls"] += 1
                    waterfall["pending_review"] += 1
                    for c in packet["match"]["controls"]:
                        control_uses[c["episode_id"]] = control_uses.get(c["episode_id"], 0) + 1
                    qualified_episode_summaries.append({"symbol": symbol, "phase": ep["phase"], "start_session_index": ep["start_session_index"],
                                                        "end_session_index": ep["end_session_index"], "episode_key": ep["episode_key"], "synthetic": inputs.synthetic})
                controls_out[ep["episode_key"]] = {"date": rep_date, "controls": [c["episode_id"] for c in packet["match"]["controls"]], "unmatched": packet["match"]["unmatched"],
                                                   "rejected_pool_counts": packet["match"]["rejected_pool_counts"], "pool_size": len(pool_summaries)}
            # chronology line references (locators only; they carry no later information)
            packet["representative"]["chronology_file"] = f"chronology/{symbol}.jsonl.gz"
            packet["representative"]["line"] = rep_line
            for member, line in zip(packet["members"], member_lines):
                member["chronology_file"] = f"chronology/{symbol}.jsonl.gz"
                member["line"] = line
            for c in packet.get("controls", []):
                c["chronology_file"] = f"chronology/{c['symbol']}.jsonl.gz"
                c["line"] = offsets[c["symbol"]][rep_date]
            packet_hash = write_json(out / "packets" / f"{ep['episode_key']}.json", packet)
            audit = retrospective_episode_audit(ep, proof, inputs.development_end)
            audit_hash = write_json(out / "episode_audit" / f"{ep['episode_key']}.json", audit)
            entry["packet"] = f"packets/{ep['episode_key']}.json"
            entry["packet_sha256"] = packet_hash
            entry["cutoff_packet_hash"] = packet["cutoff_packet_hash"]
            entry["episode_audit"] = f"episode_audit/{ep['episode_key']}.json"
            entry["episode_audit_sha256"] = audit_hash
            entry["exclusion"] = packet.get("exclusion")
            packets_index.append({"episode_key": ep["episode_key"], "symbol": symbol, "representative_date": rep_date, "packet_sha256": packet_hash,
                                  "cutoff_packet_hash": packet["cutoff_packet_hash"], "episode_audit_sha256": audit_hash,
                                  "exclusion": packet.get("exclusion"), "control_count": (packet["match"] or {}).get("control_count")})
            episodes_out.append(entry)
    groups = m.dependence_groups(qualified_episode_summaries, m.PHASE_ACCUMULATION, include_synthetic=inputs.synthetic)
    waterfall["potential_positive_episodes_pending_review"] = waterfall["matched_3_to_5_controls"]
    waterfall["effective_dependence_groups_of_pending_potential_positives"] = groups["effective_decision_groups_arithmetic"]
    waterfall["unique_controls_used"] = len(control_uses)
    waterfall["control_uses"] = sum(control_uses.values())
    waterfall["control_reuse_max"] = max(control_uses.values(), default=0)
    waterfall["target"] = {"criterion": "at least 50 independently reviewed positive episodes with 3-5 matched controls each",
                           "independently_reviewed_positive_episodes": 0, "met": False,
                           "note": "matched pending episodes are potential positives awaiting actual individual reviews; none is reviewed here"}
    waterfall["decision_exclusions"] = len(decision_exclusions)
    waterfall["row_exclusions"] = len(rec.exclusions)

    write_json(out / "decision_exclusions.json", {"schema": "m3.frozen_reader.decision_exclusions.v1", "exclusions": decision_exclusions})
    write_json(out / "inventory.json", {"schema": "m3.frozen_reader.inventory.v1", "stocks": inventory, "benchmarks": benchmarks, "benchmark_used_for_regime": inputs.benchmark_symbol,
                                        "universe_sha256": inputs.universe.sha256, "development_sessions": len(dev_sessions), "calendar": calendar.record(),
                                        "listing_source_grades": {s: listings[s]["source_grade"] for s in selected}})
    write_json(out / "cohort_coverage.json", {"schema": "m3.frozen_reader.cohort_coverage.v1", "sessions": cohort})
    write_json(out / "episodes.json", {"schema": "m3.frozen_reader.episodes.v2",
                                       "information_time": f"retrospective full development interval through {inputs.development_end}; NOT cutoff-known review input",
                                       "episodes": episodes_out, "packets": packets_index})
    write_json(out / "controls.json", {"schema": "m3.frozen_reader.controls.v1", "by_episode": controls_out, "control_uses": control_uses, "dependence_groups": groups})
    write_json(out / "waterfall.json", {"schema": "m3.frozen_reader.waterfall.v1", "waterfall": waterfall})
    write_json(out / "chronology_index.json", {"schema": "m3.frozen_reader.chronology_index.v1", "files": chronology_index,
                                               "total_records": sum(v["records"] for v in chronology_index.values()),
                                               "line_format": "one JSON object per line: {record: <m3.labels.output.v3 record>, source_map: {...}}"})
    pins_after = {name: verify_source(spec) for name, spec in _specs(inputs).items()}
    receipt.update({"status": "completed", "inputs_after": pins_after, "inputs_unchanged": pins_after == pins_before, "read_log": log.record(),
                    "records_generated": waterfall["records_generated"], "waterfall": waterfall, "chronology_index": chronology_index,
                    "reconciliation_counts": rec.counts, "symbols_selected": selected})
    receipt_hash = write_json(out / "run_receipt.json", receipt)
    receipt["run_receipt_sha256"] = receipt_hash
    return receipt


def _member_dates(records: Sequence[Mapping[str, Any]], offsets: Mapping[str, int], proof: Mapping[str, Any]) -> list[str]:
    by_id = {r["episode_id"]: r["cutoff"]["decision_date"] for r in records}
    return [by_id[eid] for eid in proof["member_episode_ids"]]


_CUTOFF_PACKET_HASH_EXCLUDED = ("cutoff_packet_hash", "review_status", "reviews")


def cutoff_packet_hash(packet: Mapping[str, Any]) -> str:
    """Stable binding of the cutoff review packet: everything except the hash itself and the (empty) review fields;
    chronology locators are excluded because they are file positions, not evidence."""
    core = {k: v for k, v in packet.items() if k not in _CUTOFF_PACKET_HASH_EXCLUDED}
    core["representative"] = {k: v for k, v in packet["representative"].items() if k not in ("chronology_file", "line")}
    core["members"] = [{k: v for k, v in mm.items() if k not in ("chronology_file", "line")} for mm in packet["members"]]
    if packet.get("controls"):
        core["controls"] = [{k: v for k, v in c.items() if k not in ("chronology_file", "line")} for c in packet["controls"]]
    return hashlib.sha256(canonical(core).encode("utf-8")).hexdigest()


def build_cutoff_packet(m: Any, ep: Mapping[str, Any], proof: Mapping[str, Any], prefix_records: Sequence[Mapping[str, Any]],
                        rep: Mapping[str, Any], pool_records: Sequence[Mapping[str, Any]], listing_grade: str, symbol: str, synthetic: bool) -> dict[str, Any]:
    """The review-facing packet: only the three prefix members, the representative record and same-date
    controls/context.  It never sees the episode's later members, end, status or later transitions."""
    rep_date = proof["established_at"]
    if [r["record_hash"] for r in prefix_records] != proof["member_record_hashes"] or prefix_records[-1]["record_hash"] != rep["record_hash"]:
        raise ReaderError("prefix_records_do_not_match_proof", ep["episode_key"])
    if any(r["cutoff"]["decision_date"] > rep_date for r in prefix_records) or any(c["cutoff"]["decision_date"] != rep_date for c in pool_records):
        raise ReaderError("packet_input_dated_after_cutoff", ep["episode_key"])
    prefix_path = [{"decision_date": r["cutoff"]["decision_date"], "phase": r["labels"]["phase"]["label"], "selection": r["labels"]["selection"]["label"]} for r in prefix_records]
    packet: dict[str, Any] = {
        "schema": "m3.frozen_reader.cutoff_review_packet.v2", "review_status": "pending_review", "reviews": [], "synthetic": synthetic,
        "information_time": f"cutoff {rep['cutoff']['as_of']} (representative decision {rep_date}); nothing later is included",
        "episode_key": ep["episode_key"], "symbol": symbol, "phase": ep["phase"], "prefix_start": proof["start"],
        "prefix_proof": proof,
        "representative": {"decision_date": rep_date, "episode_id": rep["episode_id"], "record_hash": rep["record_hash"], "cutoff": rep["cutoff"],
                           "selection": rep["labels"]["selection"], "phase_label": rep["labels"]["phase"], "current_state": rep["current_state"]},
        "members": [{"decision_date": r["cutoff"]["decision_date"], "episode_id": r["episode_id"], "record_hash": r["record_hash"]} for r in prefix_records],
        "prefix_path": prefix_path,
        "price_context": {"consumed_observation_keys": rep["input_availability"]["rows_consumed"],
                          "first_consumed_source_ref": rep["provenance"]["source_refs"][0], "last_consumed_source_ref": rep["provenance"]["source_refs"][-1],
                          "input_fingerprint": rep["provenance"]["input_fingerprint"], "benchmark_fingerprint": rep["provenance"]["benchmark_fingerprint"],
                          "calendar_fingerprint": rep["calendar"]["fingerprint"], "max_trade_date_consumed": rep["input_availability"]["max_trade_date_consumed"]},
        "warmup_depth_at_representative": rep["features"].get("bars_available"),
        "numerical_values": {k: rep["features"].get(k) for k in ("close", "position_250", "ma_spread_20_60", "return_20", "return_60", "return_120",
                                                                  "volume_ratio_20", "close_to_high", "drawdown_from_lookback_high", "amount_20_mean_cny", "bars_available")},
        "supporting_evidence": _supporting(m, rep), "contradicting_evidence": _contradicting(m, rep, prefix_path),
        "uncertainties": {"data_quality": rep["data_quality"], "adjustment_uncertainty": rep["semantics"]["adjustment_uncertainty"],
                          "corporate_action_status": rep["security_context"].get("corporate_action_status"),
                          "known_ex_dates_at_cutoff": rep["security_context"].get("known_ex_dates"), "st_status": "unknown",
                          "strict_pit_eligible": rep["pit"]["strict_pit_eligible"], "coverage": rep["identity"]["decision_inputs"]["coverage"],
                          "listing_source_grade": listing_grade},
        "regime": rep["labels"]["regime"], "liquidity": rep["labels"]["liquidity"], "limit": rep["labels"]["limit"],
        "control_pool": {"date": rep_date, "pool_size": len(pool_records),
                         "pool": [{k: s[k] for k in ("symbol", "episode_id", "record_hash", "selection", "phase", "liquidity_band", "regime", "current_state", "amount_20_mean_cny")}
                                  for s in (m.case_summary(c) for c in pool_records)]},
        "match": None, "control_ranking": None, "controls": [], "exclusion": None,
    }
    if rep["labels"]["selection"]["label"] != m.SELECTION_CANDIDATE:
        packet["exclusion"] = f"representative_selection_{rep['labels']['selection']['label']}"
    elif rep["labels"]["liquidity"]["band"] == m.LIQUIDITY_UNKNOWN or rep["labels"]["regime"]["regime"] == m.REGIME_UNKNOWN:
        packet["exclusion"] = "representative_context_unknown"
    else:
        match = m.match_controls(rep, pool_records)
        packet["match"] = match
        packet["control_ranking"] = _ranking(m, rep, pool_records)
        summaries_by_symbol = {c["symbol"]: m.case_summary(c) for c in pool_records}
        packet["controls"] = [{"symbol": c["symbol"], "episode_id": c["episode_id"], "record_hash": c["record_hash"],
                               "core_summary": summaries_by_symbol[c["symbol"]], "review_status": "pending_review"} for c in match["controls"]]
        if match["unmatched"]:
            packet["exclusion"] = f"unmatched_{match['control_count']}_controls"
    packet["cutoff_packet_hash"] = cutoff_packet_hash(packet)
    return packet


def retrospective_episode_audit(ep: Mapping[str, Any], proof: Mapping[str, Any], development_end: str) -> dict[str, Any]:
    """Audit-only retrospective metadata of the whole episode (information time = development end).  Not review input."""
    return {"schema": "m3.frozen_reader.episode_audit.v1", "not_cutoff_known": True,
            "information_time": f"retrospective full development interval through {development_end}",
            "episode_key": ep["episode_key"], "symbol": ep["symbol"], "phase": ep["phase"], "prefix_hash": proof["prefix_hash"],
            "representative_date": proof["established_at"], "start": ep["start"], "end_known_at_development_end": ep["end"], "sessions": ep["sessions"],
            "status": ep["status"], "closed_reason": ep["closed_reason"], "selection_at_start": ep["selection_at_start"], "selection_at_end": ep["selection_at_end"],
            "eligibility_changes": ep["eligibility_changes"], "selection_path": ep["selection_path"], "candidate_sessions": ep["candidate_sessions"],
            "member_episode_ids": ep["member_episode_ids"], "member_record_hashes": ep["member_record_hashes"], "episode_content_hash": ep["episode_content_hash"],
            "use": "exhaustive accounting and dependence analysis only; excluded from the cutoff review bundle"}


def _ranking(m: Any, rep: Mapping[str, Any], pool: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Deterministic ranking key of the full eligible pool (same key as match_controls)."""
    p = m.case_summary(rep)
    out = []
    for c in pool:
        s = m.case_summary(c)
        eligible = (s["selection"] == m.SELECTION_NON_CANDIDATE and s["liquidity_band"] == p["liquidity_band"] and s["regime"] == p["regime"]
                    and s["current_state"] == m.CURRENT_OBSERVED and s["liquidity_band"] != m.LIQUIDITY_UNKNOWN and s["regime"] != m.REGIME_UNKNOWN)
        amt_p, amt_c = p["amount_20_mean_cny"], s["amount_20_mean_cny"]
        key = abs(_ln(amt_c / amt_p)) if amt_p and amt_c else None
        out.append({"symbol": s["symbol"], "episode_id": s["episode_id"], "eligible": eligible, "selection": s["selection"], "liquidity_band": s["liquidity_band"],
                    "regime": s["regime"], "current_state": s["current_state"], "abs_ln_amount_ratio": key})
    return sorted(out, key=lambda x: (not x["eligible"], x["abs_ln_amount_ratio"] if x["abs_ln_amount_ratio"] is not None else float("inf"), x["symbol"]))


def _ln(x: float) -> float:
    import math
    return math.log(x)


def _supporting(m: Any, rep: Mapping[str, Any]) -> list[str]:
    f = rep["features"]
    r = m.POLICY["phase_rules"]["accumulation"]
    out = []
    if f.get("position_250") is not None:
        out.append(f"position_250={f['position_250']:.4f} < {r['position_250_lt']}")
    if f.get("ma_spread_20_60") is not None:
        out.append(f"ma_spread_20_60={f['ma_spread_20_60']:.4f} < {r['ma_spread_20_60_lt']}")
    if f.get("return_120") is not None:
        out.append(f"return_120={f['return_120']:.4f} < {r['return_120_lt']}")
    out.append("selection at representative: " + ", ".join(rep["labels"]["selection"]["reasons"]))
    return out


def _contradicting(m: Any, rep: Mapping[str, Any], prefix_path: Sequence[Mapping[str, Any]]) -> list[str]:
    """Only cutoff-known contradictions: the representative's data quality, threshold proximity and the
    three prefix members' own selection states (all dated <= the representative cutoff)."""
    f = rep["features"]
    out = list(rep["data_quality"])
    if f.get("volume_ratio_20") is not None and f["volume_ratio_20"] > m.POLICY["phase_rules"]["distribution"]["volume_ratio_20_gt"]:
        out.append(f"volume_ratio_20={f['volume_ratio_20']:.3f} above the distribution volume threshold")
    if f.get("position_250") is not None and f["position_250"] > 0.5:
        out.append(f"position_250={f['position_250']:.3f} in the upper half of the 250-bar range")
    non_candidate_members = [p for p in prefix_path if p["selection"] != m.SELECTION_CANDIDATE]
    if non_candidate_members:
        out.append("prefix members not selected as candidate: " + "; ".join(f"{p['decision_date']}={p['selection']}" for p in non_candidate_members))
    return out


def _bump(table: dict[str, int], key: str) -> None:
    table[key] = table.get(key, 0) + 1


def _specs(inputs: FrozenInputs) -> dict[str, SourceSpec]:
    specs = {"trading": inputs.trading, "history": inputs.history, "qualification": inputs.qualification, "calendar": inputs.calendar, "universe": inputs.universe}
    if inputs.metadata_index is not None:
        specs["metadata_index"] = inputs.metadata_index
    return specs


__all__ = ["READER_VERSION", "OUTPUT_SCHEMA", "FROZEN_M2", "FrozenInputs", "SourceSpec", "ReaderError", "ReadLog", "ReadOnlyStore",
           "validate_configuration", "validate_output_dir", "CLAUDE_02_SCOPE", "SYNTHETIC_SCRATCH_SCOPE", "OUTPUT_SCOPES",
           "verify_source", "load_labels", "load_calendar", "load_universe", "load_json", "reconcile", "Reconciliation", "known_events",
           "security_context_for", "observations_for", "cutoff_for", "run_development", "write_jsonl_gz", "read_jsonl_gz", "canonical", "hash_value",
           "build_cutoff_packet", "cutoff_packet_hash", "retrospective_episode_audit",
           "sha256_file", "DEVELOPMENT_START", "DEVELOPMENT_END", "PRICE_CONSUMPTION_MAX_DATE", "CUTOFF_OFFSET_SECONDS", "EVIDENCE_ASSEMBLY_AT"]
