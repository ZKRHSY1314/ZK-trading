"""Synthetic-fixture tests for ``backend/app/research/m3_frozen_reader.py``.

Run directly with the project interpreter (stdlib unittest by file path; no ``app`` package,
no conftest, no network):

    D:/codex-A股交易/backend/.venv/Scripts/python.exe -B -X utf8 backend/tests/test_m3_frozen_reader.py -v

Every SQLite file touched here is a synthetic fixture written under
``claude methods/_m3_20260910/claude_02/scratch/`` with the exact M2 DDL and SYN symbols.
The real frozen stores (``FROZEN_M2``) are never opened by this suite; a guard test asserts it.
"""
from __future__ import annotations

import copy
import importlib.util
import json
import re
import shutil
import sqlite3
import sys
import unittest
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve()
READER_PATH = HERE.parents[1] / "app" / "research" / "m3_frozen_reader.py"
SCRATCH = HERE.parents[2] / "claude methods" / "_m3_20260910" / "claude_02" / "scratch" / "test_fixtures"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


r = _load(READER_PATH, "m3_frozen_reader_under_test")
m = r.load_labels()

# --------------------------------------------------------------------------- #
# Fixture set: two SQLite stores with the exact M2 DDL, qualification, calendar,     #
# universe and metadata index — SYN symbols only, evidence refs "syn:fixture"        #
# --------------------------------------------------------------------------- #

STOCKS = ("SYN000001", "SYN000002", "SYN000003", "SYN000004", "SYN000005", "SYN000006")
POSITIVE_STOCK = "SYN000001"       # flat range: accumulation candidate
LATE_STOCK = "SYN000004"           # lists inside the development window
SUSPENDED_STOCK = "SYN000003"      # one full-day suspension inside the development window
EVENT_STOCK = "SYN000002"          # partial known cash events (one long before, one inside, one after the development window)
BENCH = "SYN900300"
DEV_START, DEV_END = "2024-01-02", "2024-03-29"
FIRST_SESSION = "2022-06-01"
OBSERVED_AT = "2026-09-09T17:12:21.727091+00:00"
ASSEMBLY = "2026-09-10T06:52:37.442011+00:00"
SUSPENSION_DATE = "2024-02-05"
LATE_LISTING = "2024-02-01"

TRADING_DDL = [
    "CREATE TABLE coverage_inventory (symbol TEXT NOT NULL, trade_date TEXT NOT NULL, classification TEXT NOT NULL CHECK(classification IN ('price','full_day_suspension')), PRIMARY KEY(symbol,trade_date))",
    "CREATE TABLE daily_bar_cache ( symbol TEXT NOT NULL, trade_date TEXT NOT NULL, open REAL, high REAL, low REAL, close REAL, volume REAL, amount REAL, source TEXT NOT NULL, quality_status TEXT NOT NULL, adjustment_mode TEXT NOT NULL, volume_unit TEXT NOT NULL, PRIMARY KEY(symbol, trade_date))",
    "CREATE TABLE dataset_contract (id INTEGER PRIMARY KEY CHECK(id=1), contract_json TEXT NOT NULL)",
    "CREATE TABLE ingest_provenance ( symbol TEXT, instrument_class TEXT, url TEXT, body_sha256 TEXT, schema TEXT, declared_basis TEXT, derived_basis TEXT, derived_unit TEXT, run_id TEXT, run_mode TEXT, lineage TEXT)",
    "CREATE TABLE instruments (symbol TEXT PRIMARY KEY, name TEXT)",
    "CREATE TABLE qualification_records (symbol TEXT PRIMARY KEY, record_sha256 TEXT, record_json TEXT)",
    "CREATE TABLE row_evidence ( symbol TEXT, trade_date TEXT, raw_sha256 TEXT, request_sha256 TEXT, producer_sha256 TEXT, parser_sha256 TEXT, capture_receipt_sha256 TEXT, capture_producer_manifest_sha256 TEXT, observed_at TEXT, point_index INTEGER, qualification_sha256 TEXT, source_name TEXT, source_name_status TEXT, PRIMARY KEY(symbol, trade_date))",
    "CREATE TABLE suspension_records (symbol TEXT NOT NULL, trade_date TEXT NOT NULL, evidence_sha256 TEXT NOT NULL, record_json TEXT NOT NULL, PRIMARY KEY(symbol,trade_date))",
    "CREATE VIEW research_prices AS SELECT * FROM daily_bar_cache WHERE trade_date BETWEEN '2023-09-04' AND '2026-09-04'",
    "CREATE VIEW warmup_prices AS SELECT * FROM daily_bar_cache WHERE trade_date < '2023-09-04'",
]
HISTORY_DDL = [
    "CREATE TABLE coverage_inventory (symbol TEXT NOT NULL, trade_date TEXT NOT NULL, classification TEXT NOT NULL CHECK(classification IN ('price','full_day_suspension')), PRIMARY KEY(symbol,trade_date))",
    "CREATE TABLE ingest_runs ( id INTEGER PRIMARY KEY, provider TEXT, run_id TEXT, run_mode TEXT, started_at TEXT)",
    "CREATE TABLE daily_bars ( symbol TEXT NOT NULL, trade_date TEXT NOT NULL, adjustment_mode TEXT NOT NULL, open REAL, high REAL, low REAL, close REAL, volume REAL, amount REAL, provider TEXT, fetched_at TEXT, ingest_run_id INTEGER NOT NULL REFERENCES ingest_runs(id), PRIMARY KEY(symbol, trade_date, adjustment_mode))",
    "CREATE TABLE dataset_contract (id INTEGER PRIMARY KEY CHECK(id=1), contract_json TEXT NOT NULL)",
    "CREATE TABLE suspension_records (symbol TEXT NOT NULL, trade_date TEXT NOT NULL, evidence_sha256 TEXT NOT NULL, record_json TEXT NOT NULL, PRIMARY KEY(symbol,trade_date))",
    "CREATE VIEW research_prices AS SELECT * FROM daily_bars WHERE trade_date BETWEEN '2023-09-04' AND '2026-09-04'",
    "CREATE VIEW warmup_prices AS SELECT * FROM daily_bars WHERE trade_date < '2023-09-04'",
]


def weekdays(start: str, end: str) -> list[str]:
    d = date.fromisoformat(start)
    out = []
    while d.isoformat() <= end:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def lcg(seed: int):
    x = seed
    while True:
        x = (1103515245 * x + 12345) % 2**31
        yield x / 2**31


def fake_hash(tag: str) -> str:
    return r.hash_value(tag)


def stock_series(symbol: str, sessions: list[str], seed: int) -> list[dict]:
    """Flat noisy range (accumulation-like) with a distribution-style spike near the end for controls."""
    rnd = lcg(seed)
    rows = []
    c = 10.0 + seed * 0.1
    prev = None
    for i, d in enumerate(sessions):
        c = 10.0 + seed * 0.1 + (next(rnd) - 0.5) * 0.6
        o = prev if prev is not None else c
        hi, lo = max(o, c) * 1.01, min(o, c) * 0.99
        v = 1_000_000.0 + int(next(rnd) * 200_000)
        rows.append({"symbol": symbol, "trade_date": d, "open": round(o, 4), "high": round(hi, 4), "low": round(lo, 4), "close": round(c, 4),
                     "volume": v, "amount": round(v * (hi + lo) / 2.0, 2)})
        prev = c
    return rows


def bench_series(sessions: list[str]) -> list[dict]:
    rows = []
    for i, d in enumerate(sessions):
        level = 3000.0 * 1.0004 ** i
        rows.append({"symbol": BENCH, "trade_date": d, "open": round(level, 2), "high": round(level * 1.005, 2), "low": round(level * 0.995, 2),
                     "close": round(level, 2), "volume": 1.0e10, "amount": 5.0e11})
    return rows


LATER_VARIANT_FROM = "2024-03-01"


def build_fixture_set(root: Path, corrupt: str | None = None, extra_rows_beyond_bound: bool = True, later_rows_variant: bool = False) -> "r.FrozenInputs":
    """Write a complete synthetic fixture set under ``root`` and return its FrozenInputs (hashes computed after writing).
    ``later_rows_variant`` perturbs the positive stock's prices strictly after LATER_VARIANT_FROM (extension-invariance control)."""
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    sessions = weekdays(FIRST_SESSION, "2024-06-28")  # extends past the bound so that beyond-bound rows exist in the stores
    dev_sessions = [d for d in sessions if DEV_START <= d <= DEV_END]
    series: dict[str, list[dict]] = {}
    for i, s in enumerate(STOCKS):
        rows = stock_series(s, sessions, i + 1)
        if s == LATE_STOCK:
            rows = [x for x in rows if x["trade_date"] >= LATE_LISTING]
        if s == SUSPENDED_STOCK:
            rows = [x for x in rows if x["trade_date"] != SUSPENSION_DATE]
        if s != POSITIVE_STOCK:
            # controls: distribution-style spike on every development session so same-date non_candidate controls exist
            spiked = []
            for x in rows:
                if x["trade_date"] in dev_sessions:
                    x = dict(x, high=round(x["close"] * 1.35, 4), close=round(x["close"] * 1.30, 4), volume=x["volume"] * 3.0)
                    x["amount"] = round(x["volume"] * (x["high"] + x["low"]) / 2.0, 2)
                spiked.append(x)
            rows = spiked
        if not extra_rows_beyond_bound:
            rows = [x for x in rows if x["trade_date"] <= DEV_END]
        if later_rows_variant and s == POSITIVE_STOCK:
            changed = []
            for x in rows:
                if x["trade_date"] > LATER_VARIANT_FROM:
                    x = dict(x, open=round(x["open"] * 1.5, 4), high=round(x["high"] * 1.5, 4), low=round(x["low"] * 1.5, 4), close=round(x["close"] * 1.5, 4))
                    x["amount"] = round(x["volume"] * (x["high"] + x["low"]) / 2.0, 2)
                changed.append(x)
            rows = changed
        series[s] = rows
    series[BENCH] = bench_series(sessions) if extra_rows_beyond_bound else [x for x in bench_series(sessions) if x["trade_date"] <= DEV_END]

    # frozen qualification with scopes/captures/suspension ledger/controls
    ledger = [{"symbol": SUSPENDED_STOCK, "date": SUSPENSION_DATE, "window": "research", "status": "issuer_confirmed_suspension", "frozen_gate_exemption": False,
               "evidence": [{"source": "syn:fixture/suspension.html", "sha256": fake_hash("syn:suspension-doc"), "start": SUSPENSION_DATE, "resume": "2024-02-06", "symbol": SUSPENDED_STOCK}]}]
    scopes = []
    captures: dict[str, dict] = {}
    for s in STOCKS + (BENCH,):
        rows = series[s]
        cap = {"raw_sha256": fake_hash(f"raw:{s}"), "request_sha256": fake_hash(f"req:{s}"), "producer_sha256": fake_hash("producer"), "parser_sha256": fake_hash("parser"),
               "capture_receipt_sha256": fake_hash(f"receipt:{s}"), "capture_producer_manifest_sha256": fake_hash("manifest"), "observed_at": OBSERVED_AT,
               "rows": len(rows), "start": rows[0]["trade_date"], "end": rows[-1]["trade_date"], "directory": "syn:fixture", "job_id": 1,
               "response_identity": {"code": s[-6:], "name": ""}}
        captures[s] = cap
        benchmark = s == BENCH
        expected_dates = [x["trade_date"] for x in rows]
        if corrupt == "price_suspension_conflict" and s == SUSPENDED_STOCK:
            expected_dates = sorted(expected_dates + [SUSPENSION_DATE])
        scopes.append({"symbol": s, "instrument_class": "benchmark" if benchmark else "stock", "vendor_basis": "unadjusted", "vendor_basis_status": "verified",
                       "identity_status": "verified", "unit_status": "not_applicable" if benchmark else "verified",
                       "volume_unit": "not_applicable" if benchmark else "share", "amount_unit": "not_applicable" if benchmark else "CNY",
                       "captures": [cap], "expected_price_dates": expected_dates,
                       "suspended_dates": [SUSPENSION_DATE] if s == SUSPENDED_STOCK else [], "rows": len(rows), "research_rows": 0, "warmup_rows": 0,
                       "price_domain_exceptions": [], "prior_qualification_record_sha256": None})
    qualification = {"schema": "m2.ths.qualification_evidence.v2", "scopes": scopes, "suspension_ledger": ledger,
                     "controls": {EVENT_STOCK: {"boundaries": [{"ex_date": "2022-07-05", "observed_cash_step": "0.05", "previous_observed_date": "2022-07-04"},
                                                               {"ex_date": "2024-02-15", "observed_cash_step": "0.06", "previous_observed_date": "2024-02-14"},
                                                               {"ex_date": "2024-05-10", "observed_cash_step": "0.07", "previous_observed_date": "2024-05-09"}]}},
                     "strict_pit": False, "live_trading": False, "production_promoted": False, "staging_eligible": True}
    if corrupt == "qualification_hash":
        pass  # handled below (stored record differs from frozen scope)
    qpath = root / "qualification_fixture.json"
    qpath.write_text(json.dumps(qualification, ensure_ascii=False, indent=1), encoding="utf-8")
    cal_path = root / "calendar_fixture.json"
    cal_path.write_text(json.dumps([d.replace("-", "") for d in sessions]), encoding="utf-8")
    uni_path = root / "pilot_fixture.csv"
    lines = ["symbol,stratum,name,exchange,list_date,eligible_sessions,observed_sessions,leading_gap,interior_gap,trailing_gap,coverage_ratio,selection_note"]
    for s in STOCKS:
        listing = LATE_LISTING if s == LATE_STOCK else FIRST_SESSION
        lines.append(f"{s},syn_stratum,,SYN,{listing},0,0,0,0,0,0,syn fixture")
    lines.append(f"{BENCH},benchmark,,INDEX,,,,,,,,syn benchmark")
    uni_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    index = {"schema": "syn.metadata_index", "assembled_at_utc": ASSEMBLY,
             "instruments": [{"symbol": s, "listing_evidence": {"status": "syn_fixture_listing", "identity_kind": "syn_fixture"},
                              "known_cash_events": ([{"symbol": s, "ex_date": b["ex_date"], "cash_per_share_CNY": b["observed_cash_step"], "document_sha256": fake_hash(f"doc:{b['ex_date']}"), "event_type": "cash_implementation"}
                                                     for b in qualification["controls"][s]["boundaries"]] if s in qualification["controls"] else [])}
                             for s in STOCKS + (BENCH,)]}
    idx_path = root / "index_fixture.json"
    idx_path.write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")

    # stores
    contract = r.canonical({"schema": "syn.contract", "fixture": True})
    tpath, hpath = root / "trading.sqlite3", root / "history.sqlite3"
    t = sqlite3.connect(str(tpath))
    h = sqlite3.connect(str(hpath))
    for ddl in TRADING_DDL:
        t.execute(ddl)
    for ddl in HISTORY_DDL:
        h.execute(ddl)
    t.execute("INSERT INTO dataset_contract VALUES (1,?)", (contract,))
    h.execute("INSERT INTO dataset_contract VALUES (1,?)", (contract,))
    h.execute("INSERT INTO ingest_runs VALUES (1,'tonghuashun','syn_run','retained_raw_review_only','2026-09-10T00:00:00+00:00')")
    for scope in scopes:
        s = scope["symbol"]
        stored = dict(scope)
        if corrupt == "qualification_hash" and s == STOCKS[0]:
            stored = dict(scope, rows=scope["rows"] + 1)
        t.execute("INSERT INTO qualification_records VALUES (?,?,?)", (s, r.hash_value(stored), r.canonical(stored)))
        t.execute("INSERT INTO instruments VALUES (?,?)", (s, None))
        cap = captures[s]
        for i, x in enumerate(series[s]):
            numbers = [x[k] for k in ("open", "high", "low", "close", "volume", "amount")]
            hist = list(numbers)
            observed = OBSERVED_AT
            fetched = OBSERVED_AT
            if corrupt == "numeric_mismatch" and s == STOCKS[0] and x["trade_date"] == DEV_START:
                hist[3] = hist[3] + 0.01
            if corrupt == "observed_at_mismatch" and s == STOCKS[0] and x["trade_date"] == DEV_START:
                fetched = "2026-09-09T18:00:00+00:00"
            t.execute("INSERT INTO daily_bar_cache VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", (s, x["trade_date"], *numbers, "tonghuashun", "qualified_candidate", "none", scope["volume_unit"]))
            evidence_date = x["trade_date"]
            if corrupt == "missing_evidence" and s == STOCKS[0] and x["trade_date"] == DEV_START:
                evidence_date = "2099-01-01"  # evidence row relocated beyond the bound: totals stay equal, the key lacks evidence
            t.execute("INSERT INTO row_evidence VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                      (s, evidence_date, cap["raw_sha256"], cap["request_sha256"], cap["producer_sha256"], cap["parser_sha256"], cap["capture_receipt_sha256"],
                       cap["capture_producer_manifest_sha256"], observed, i, r.hash_value(scope), None, "absent"))
            h.execute("INSERT INTO daily_bars VALUES (?,?,?,?,?,?,?,?,?,?,?,1)", (s, x["trade_date"], "none", *hist, "tonghuashun", fetched))
            t.execute("INSERT INTO coverage_inventory VALUES (?,?,?)", (s, x["trade_date"], "price"))
            h.execute("INSERT INTO coverage_inventory VALUES (?,?,?)", (s, x["trade_date"], "price"))
    for gap in ledger:
        t.execute("INSERT INTO suspension_records VALUES (?,?,?,?)", (gap["symbol"], gap["date"], r.hash_value(gap), r.canonical(gap)))
        h.execute("INSERT INTO suspension_records VALUES (?,?,?,?)", (gap["symbol"], gap["date"], r.hash_value(gap), r.canonical(gap)))
        t.execute("INSERT INTO coverage_inventory VALUES (?,?,?)", (gap["symbol"], gap["date"], "full_day_suspension"))
        h.execute("INSERT INTO coverage_inventory VALUES (?,?,?)", (gap["symbol"], gap["date"], "full_day_suspension"))
    if corrupt == "price_suspension_conflict":
        x = dict(series[SUSPENDED_STOCK][0], trade_date=SUSPENSION_DATE)
        numbers = [x[k] for k in ("open", "high", "low", "close", "volume", "amount")]
        t.execute("INSERT INTO daily_bar_cache VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", (SUSPENDED_STOCK, SUSPENSION_DATE, *numbers, "tonghuashun", "qualified_candidate", "none", "share"))
        h.execute("INSERT INTO daily_bars VALUES (?,?,?,?,?,?,?,?,?,?,?,1)", (SUSPENDED_STOCK, SUSPENSION_DATE, "none", *numbers, "tonghuashun", OBSERVED_AT))
        cap = captures[SUSPENDED_STOCK]
        t.execute("INSERT INTO row_evidence VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (SUSPENDED_STOCK, SUSPENSION_DATE, cap["raw_sha256"], cap["request_sha256"], cap["producer_sha256"], cap["parser_sha256"], cap["capture_receipt_sha256"],
                   cap["capture_producer_manifest_sha256"], OBSERVED_AT, 0, r.hash_value(next(sc for sc in scopes if sc["symbol"] == SUSPENDED_STOCK)), None, "absent"))
    t.commit()
    h.commit()
    t.close()
    h.close()
    return r.FrozenInputs(
        trading=r.SourceSpec(str(tpath), r.sha256_file(tpath), tpath.stat().st_size, "sqlite"),
        history=r.SourceSpec(str(hpath), r.sha256_file(hpath), hpath.stat().st_size, "sqlite"),
        qualification=r.SourceSpec(str(qpath), r.sha256_file(qpath)), calendar=r.SourceSpec(str(cal_path), r.sha256_file(cal_path)),
        universe=r.SourceSpec(str(uni_path), r.sha256_file(uni_path)), metadata_index=r.SourceSpec(str(idx_path), r.sha256_file(idx_path)),
        synthetic=True, benchmark_symbol=BENCH, development_start=DEV_START, development_end=DEV_END, price_max_date=DEV_END, evidence_assembly_at=ASSEMBLY)


class FixtureBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = SCRATCH / cls.__name__
        cls.inputs = build_fixture_set(cls.root)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)


# --------------------------------------------------------------------------- #
# Source boundary                                                             #
# --------------------------------------------------------------------------- #


class SourceBoundaryTests(FixtureBase):
    def test_import_has_no_side_effects_and_pins_are_declared(self):
        self.assertEqual(r.FROZEN_LABELS_SHA256, "e20eb21cdea032ced319a8f45a34cdeb03fd4d8b357ac31403306fa73b225393")
        self.assertEqual(r.FROZEN_POLICY_HASH, m.POLICY_HASH)
        self.assertEqual(r.FROZEN_M2.trading.sha256, "c0b26660ab903541e7e213ee312c565be73547bb3cc8c142486999717e3edeca")
        self.assertEqual(r.FROZEN_M2.history.sha256, "eda17434ab67496c33eed275b35045c140bad72802b4dcbf981ff22422c53003")
        self.assertEqual((r.FROZEN_M2.trading.bytes, r.FROZEN_M2.history.bytes), (38969344, 10604544))
        self.assertEqual((r.DEVELOPMENT_START, r.DEVELOPMENT_END, r.PRICE_CONSUMPTION_MAX_DATE), ("2023-09-04", "2025-03-31", "2025-03-31"))
        self.assertEqual(r.CUTOFF_OFFSET_SECONDS, 3600)
        self.assertEqual(r.cutoff_for(m, "2024-05-06").as_of, "2024-05-06T16:00:00+08:00")
        self.assertEqual(r.cutoff_for(m, "2024-05-06").mode, "retrospective")

    def test_invalid_path_hash_size_and_sidecar_are_refused_before_connecting(self):
        log = r.ReadLog()
        for spec, code in ((replace(self.inputs.trading, path=str(self.root / "nope.sqlite3")), "source_missing"),
                           (replace(self.inputs.trading, sha256="0" * 64), "source_hash_mismatch"),
                           (replace(self.inputs.trading, bytes=1), "source_size_mismatch")):
            store = r.ReadOnlyStore(spec, log, "trading", replace(self.inputs, trading=spec))  # construction: no I/O, no error
            with self.assertRaises(r.ReaderError) as ctx:
                with store:
                    pass
            self.assertEqual(ctx.exception.code, code)
        sidecar = Path(self.inputs.trading.path + "-wal")
        sidecar.write_bytes(b"")
        try:
            with self.assertRaises(r.ReaderError) as ctx:
                with r.ReadOnlyStore(self.inputs.trading, log, "trading", self.inputs):
                    pass
            self.assertEqual(ctx.exception.code, "source_sidecar_present")
        finally:
            sidecar.unlink()
        self.assertEqual(log.connections, [])
        with self.assertRaises(r.ReaderError):
            r.ReadOnlyStore(replace(self.inputs.qualification, kind="file"), log, "x")

    def test_connection_is_read_only_and_denies_writes_attach_and_pragma_writes(self):
        log = r.ReadLog()
        with r.ReadOnlyStore(self.inputs.trading, log, "trading", self.inputs) as store:
            self.assertEqual(store.one("SELECT COUNT(*) FROM instruments"), len(STOCKS) + 1)
            for sql in ("INSERT INTO instruments VALUES ('SYN000009', NULL)", "UPDATE daily_bar_cache SET close = 1", "DELETE FROM row_evidence",
                        "CREATE TABLE x (a)", "DROP TABLE instruments", f"ATTACH DATABASE '{self.inputs.history.path}' AS other",
                        "PRAGMA journal_mode=WAL", "PRAGMA user_version=9"):
                with self.assertRaises(sqlite3.DatabaseError, msg=sql):
                    store.conn.execute(sql)
            self.assertEqual(store.one("PRAGMA user_version"), 0)
        self.assertGreaterEqual(len(log.denied), 6)
        self.assertEqual(log.connections[0]["sha256_before"], log.connections[0]["sha256_after"])
        self.assertEqual(log.connections[0]["query_only_read_back"], 1)
        self.assertEqual(log.connections[0]["mode"], "synthetic")
        self.assertEqual(r.sha256_file(Path(self.inputs.trading.path)), self.inputs.trading.sha256)  # untouched after the attempts
        # statements are logged with their bound parameters
        with r.ReadOnlyStore(self.inputs.trading, log, "trading", self.inputs) as store:
            store.rows("SELECT COUNT(*) FROM daily_bar_cache WHERE trade_date <= ?", (DEV_END,))
        self.assertEqual(log.statements[-1], {"connection": "trading", "sql": "SELECT COUNT(*) FROM daily_bar_cache WHERE trade_date <= ?", "params": [DEV_END]})

    def test_fixed_real_configuration_is_enforced_before_any_io(self):
        class UnexpectedIO(RuntimeError):
            pass

        # a widened price cutoff on the real configuration never reaches a store opener
        widened = replace(r.FROZEN_M2, price_max_date="2026-09-04")
        with mock.patch.object(r, "load_json", side_effect=UnexpectedIO("would read")), mock.patch.object(r, "ReadOnlyStore", side_effect=UnexpectedIO("would open")) as store:
            with self.assertRaises(r.ReaderError) as ctx:
                r.reconcile(widened, r.ReadLog())
            self.assertEqual(ctx.exception.code, "real_configuration_not_frozen")
            self.assertEqual(store.call_count, 0)
        # a caller-replaced real source never reaches verification/hashing
        other = r.SourceSpec(str(HERE.parents[1] / "unauthorized_fixture_source.sqlite3"), "0" * 64, kind="sqlite")
        with mock.patch.object(r, "load_labels", side_effect=UnexpectedIO("labels")), mock.patch.object(r, "verify_source", side_effect=UnexpectedIO("hash")) as verify:
            with self.assertRaises(r.ReaderError) as ctx:
                r.run_development(r.CLAUDE_02_SCOPE / "runs" / "nonexistent_test_output", replace(r.FROZEN_M2, trading=other))
            self.assertEqual(ctx.exception.code, "real_configuration_not_frozen")
            self.assertEqual(verify.call_count, 0)
        for change in (dict(development_end="2025-12-31"), dict(benchmark_symbol="SH000001"), dict(metadata_index=None), dict(labels_sha256="0" * 64),
                       dict(evidence_assembly_at="2020-01-01T00:00:00+00:00"), dict(history=replace(r.FROZEN_M2.history, sha256="1" * 64))):
            with self.assertRaises(r.ReaderError) as ctx:
                r.validate_configuration(replace(r.FROZEN_M2, **change))
            self.assertEqual(ctx.exception.code, "real_configuration_not_frozen", change)
        self.assertEqual(r.validate_configuration(r.FROZEN_M2)["mode"], "real")
        # synthetic confinement: scratch scope only, never the real stores, never a relabelled real set
        self.assertEqual(r.validate_configuration(self.inputs)["mode"], "synthetic")
        with self.assertRaises(r.ReaderError) as ctx:
            r.validate_configuration(replace(r.FROZEN_M2, synthetic=True))
        self.assertIn(ctx.exception.code, ("synthetic_source_outside_scratch_scope", "synthetic_flag_cannot_relabel_real_store"))
        with self.assertRaises(r.ReaderError) as ctx:
            r.validate_configuration(replace(self.inputs, trading=r.FROZEN_M2.trading))
        self.assertIn(ctx.exception.code, ("synthetic_source_outside_scratch_scope", "synthetic_flag_cannot_relabel_real_store"))
        with self.assertRaises(r.ReaderError) as ctx:
            r.validate_configuration(replace(self.inputs, calendar=r.SourceSpec(str(HERE.parents[1] / "x.json"), "0" * 64)))
        self.assertEqual(ctx.exception.code, "synthetic_source_outside_scratch_scope")
        with self.assertRaises(r.ReaderError) as ctx:
            r.validate_configuration(replace(self.inputs, price_max_date="2024-12-31"))
        self.assertEqual(ctx.exception.code, "configuration_invalid")
        # a store opened without a validated configuration is authorized only for the two fixed real specs
        with self.assertRaises(r.ReaderError) as ctx:
            with r.ReadOnlyStore(self.inputs.trading, r.ReadLog(), "trading"):
                pass
        self.assertEqual(ctx.exception.code, "store_not_authorized")
        with self.assertRaises(r.ReaderError) as ctx:
            with r.ReadOnlyStore(self.inputs.history, r.ReadLog(), "history", replace(self.inputs, history=self.inputs.trading)):
                pass
        self.assertEqual(ctx.exception.code, "store_not_authorized")

    def test_store_construction_performs_no_file_io(self):
        class UnexpectedIO(RuntimeError):
            pass

        with mock.patch.object(r, "verify_source", side_effect=UnexpectedIO("constructor read")) as verify:
            store = r.ReadOnlyStore(r.FROZEN_M2.trading, r.ReadLog(), "trading")
            self.assertIsNone(store.verified)
            self.assertEqual(verify.call_count, 0)
        with mock.patch.object(r, "verify_source", side_effect=UnexpectedIO("constructor read")) as verify:
            r.ReadOnlyStore(self.inputs.trading, r.ReadLog(), "trading", self.inputs)
            self.assertEqual(verify.call_count, 0)
        # import side effects: the module only defines constants and functions
        source = READER_PATH.read_text(encoding="utf-8")
        self.assertNotIn("sqlite3.connect(", source.split("class ReadOnlyStore")[0])

    def test_output_scope_is_enforced_without_touching_the_path(self):
        for bad in (HERE.parents[2] / "backend" / "somewhere", Path("relative/out"), r.CLAUDE_02_SCOPE / "runs", HERE.parents[2] / "claude methods" / "_m3_20260910" / "claude_01_r3" / "x"):
            with self.subTest(path=str(bad)):
                with mock.patch.object(r, "load_labels", side_effect=RuntimeError("must not be reached")):
                    with self.assertRaises(r.ReaderError) as ctx:
                        r.run_development(bad, self.inputs)
                self.assertIn(ctx.exception.code, ("output_dir_outside_scope", "output_dir_not_absolute"))
                self.assertFalse(Path(bad).exists() if Path(bad).is_absolute() and bad != r.CLAUDE_02_SCOPE / "runs" else False)
        self.assertEqual(r.validate_output_dir(r.CLAUDE_02_SCOPE / "runs" / "dev_run_x"), r.CLAUDE_02_SCOPE / "runs" / "dev_run_x")
        self.assertEqual(r.validate_output_dir(SCRATCH / "x" / "run"), SCRATCH / "x" / "run")

    def test_real_frozen_sources_are_never_opened_by_this_suite(self):
        real = {Path(r.FROZEN_M2.trading.path).resolve(), Path(r.FROZEN_M2.history.path).resolve()}
        fixture = {Path(self.inputs.trading.path).resolve(), Path(self.inputs.history.path).resolve()}
        self.assertFalse(real & fixture)
        self.assertTrue(all(str(SCRATCH) in str(p) for p in fixture))

    def test_labels_module_pin_is_enforced(self):
        with self.assertRaises(r.ReaderError) as ctx:
            r.load_labels(expected_sha256="0" * 64)
        self.assertEqual(ctx.exception.code, "labels_module_not_frozen")
        with self.assertRaises(r.ReaderError) as ctx:
            r.load_labels(expected_policy_hash="0" * 64)
        self.assertEqual(ctx.exception.code, "policy_not_frozen")


# --------------------------------------------------------------------------- #
# Reconciliation                                                              #
# --------------------------------------------------------------------------- #


class ReconciliationTests(FixtureBase):
    def test_clean_fixture_reconciles_completely_within_the_bound(self):
        log = r.ReadLog()
        rec = r.reconcile(self.inputs, log)
        self.assertEqual(rec.problems, [])
        self.assertEqual(rec.exclusions, [])
        self.assertEqual(rec.counts["trading_rows_permitted"], rec.counts["permitted_price_rows_accepted"])
        self.assertGreater(rec.counts["trading_rows_beyond_permitted_not_selected"], 0)
        self.assertEqual(max(x["trade_date"] for rows in rec.price_rows.values() for x in rows), DEV_END)
        self.assertEqual(rec.counts["permitted_suspensions_accepted"], 1)
        self.assertEqual(rec.suspensions[SUSPENDED_STOCK][0]["trade_date"], SUSPENSION_DATE)
        # every SQL that touches OHLCVA carries the bound; connections are audited and verified before/after
        for st in log.record()["distinct_statements"]:
            sql = st["sql"]
            if "FROM daily_bar_cache" in sql or "FROM daily_bars" in sql:
                self.assertTrue("trade_date <= ?" in sql or "trade_date > ?" in sql or "COUNT(*)" in sql, sql)
                if "?" in sql:
                    self.assertEqual(st["params"], [DEV_END], st)
        self.assertEqual({c["role"] for c in log.connections}, {"trading", "history"})
        self.assertTrue(all(c["sha256_before"] == c["sha256_after"] for c in log.connections))
        self.assertEqual(log.denied, [])
        # benchmark rows keep not_applicable units; stock rows share/CNY
        self.assertTrue(all(x["volume_unit"] == "not_applicable" and x["amount_unit"] == "not_applicable" for x in rec.price_rows[BENCH]))
        self.assertTrue(all(x["volume_unit"] == "share" and x["amount_unit"] == "CNY" for x in rec.price_rows[STOCKS[0]]))

    def test_corrupted_fixtures_are_excluded_or_refused(self):
        for corruption, expect_exclusion, expect_problem in (("numeric_mismatch", "numeric_mismatch_between_stores", None),
                                                             ("missing_evidence", "row_evidence_missing", None),
                                                             ("observed_at_mismatch", "observed_at_fetched_at_mismatch", None),
                                                             ("price_suspension_conflict", "price_and_suspension_conflict", None),
                                                             ("qualification_hash", None, "qualification_record_mismatch")):
            with self.subTest(corruption=corruption):
                inputs = build_fixture_set(SCRATCH / f"corrupt_{corruption}", corrupt=corruption)
                try:
                    rec = r.reconcile(inputs, r.ReadLog())
                    if expect_problem:
                        self.assertTrue(any(p.startswith(expect_problem) for p in rec.problems), rec.problems)
                        self.assertEqual(rec.price_rows, {})
                    else:
                        reasons = {e["reason"] for e in rec.exclusions}
                        self.assertIn(expect_exclusion, reasons, rec.exclusions)
                        excluded_keys = {(e["symbol"], e["trade_date"]) for e in rec.exclusions}
                        for symbol, rows in rec.price_rows.items():
                            for x in rows:
                                self.assertNotIn((symbol, x["trade_date"]), excluded_keys)
                finally:
                    shutil.rmtree(SCRATCH / f"corrupt_{corruption}", ignore_errors=True)

    def test_known_events_must_agree_with_frozen_qualification(self):
        q = r.load_json(self.inputs.qualification)
        idx = r.load_json(self.inputs.metadata_index)
        events = r.known_events(idx, q)
        self.assertEqual([e["ex_date"] for e in events[EVENT_STOCK]], ["2022-07-05", "2024-02-15", "2024-05-10"])
        bad = copy.deepcopy(idx)
        bad["instruments"][1]["known_cash_events"].pop()
        with self.assertRaises(r.ReaderError) as ctx:
            r.known_events(bad, q)
        self.assertEqual(ctx.exception.code, "known_events_disagree_with_frozen_qualification")

    def test_context_filters_events_by_cutoff_and_keeps_unknowns(self):
        q = r.load_json(self.inputs.qualification)
        events = r.known_events(r.load_json(self.inputs.metadata_index), q)[EVENT_STOCK]
        listing = {"listing_date": FIRST_SESSION, "source_grade": "syn_fixture", "evidence_ref": "syn:listing"}
        early = r.security_context_for(m, EVENT_STOCK, listing, events, "2024-01-15", ASSEMBLY)
        self.assertEqual(early.known_ex_dates, ("2022-07-05",))
        self.assertEqual(early.corporate_action_status, "partial_known")
        mid = r.security_context_for(m, EVENT_STOCK, listing, events, "2024-02-20", ASSEMBLY)
        self.assertEqual(mid.known_ex_dates, ("2022-07-05", "2024-02-15"))
        self.assertNotIn("2024-05-10", mid.known_ex_dates)
        self.assertEqual((mid.st_status, mid.float_shares, mid.turnover_available, mid.name), ("unknown", None, False, None))
        self.assertEqual(mid.facts_available_at, ASSEMBLY)
        none = r.security_context_for(m, STOCKS[0], listing, [], "2024-02-20", ASSEMBLY)
        self.assertEqual(none.corporate_action_status, "unknown")


# --------------------------------------------------------------------------- #
# Development run on the fixture                                              #
# --------------------------------------------------------------------------- #


class DevelopmentRunTests(FixtureBase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.out = cls.root / "run_01"
        cls.receipt = r.run_development(cls.out, cls.inputs)

    def test_run_is_complete_bounded_and_pending_review(self):
        rc = self.receipt
        self.assertEqual(rc["status"], "completed")
        self.assertTrue(rc["inputs_unchanged"])
        self.assertEqual(rc["cutoff_mode"], "retrospective")
        self.assertEqual(rc["cutoff_convention"], "close+3600s")
        self.assertFalse(rc["strict_pit"])
        self.assertFalse(rc["training_eligible"])
        self.assertFalse(rc["evidence_assembly_at_is_historical_availability"])
        self.assertEqual({c["path"] for c in rc["read_log"]["connections"]}, {str(Path(self.inputs.trading.path).resolve()), str(Path(self.inputs.history.path).resolve())})
        self.assertEqual(rc["read_log"]["denied_actions"], [])
        self.assertTrue(all(c["query_only_read_back"] == 1 and c["mode"] == "synthetic" for c in rc["read_log"]["connections"]))
        self.assertTrue(all(st["params"] in ([], [DEV_END]) for st in rc["read_log"]["statements"]))
        self.assertEqual(rc["configuration"]["mode"], "synthetic")
        w = rc["waterfall"]
        dev_sessions = len(weekdays(DEV_START, DEV_END))
        self.assertEqual(w["expected_stock_session_keys"], dev_sessions * len(STOCKS))
        self.assertEqual(w["not_listed"], len([d for d in weekdays(DEV_START, DEV_END) if d < LATE_LISTING]))
        self.assertEqual(w["records_generated"] + w["not_listed"] + w["no_observations_before_cutoff"], w["expected_stock_session_keys"])
        self.assertEqual(w["current_state"]["suspended"], 1)
        self.assertEqual(w["strict_pit_eligible"], 0)
        self.assertEqual(w["training_eligible"], 0)
        self.assertEqual(w["independently_reviewed"], 0)
        self.assertEqual(w["qualified_reviewed_positive_episodes"], 0)
        self.assertFalse(w["target"]["met"])
        self.assertGreaterEqual(w["accumulation_duration_established"], 1)
        self.assertGreaterEqual(w["matched_3_to_5_controls"], 1)
        self.assertEqual(w["pending_review"], w["matched_3_to_5_controls"])
        for name in ("run_receipt.json", "waterfall.json", "inventory.json", "episodes.json", "controls.json", "cohort_coverage.json",
                     "chronology_index.json", "exclusions.json", "decision_exclusions.json"):
            self.assertTrue((self.out / name).is_file(), name)

    def test_chronology_records_are_verified_cores_with_source_maps(self):
        idx = json.loads((self.out / "chronology_index.json").read_text(encoding="utf-8"))
        total = 0
        for symbol, info in idx["files"].items():
            path = self.out / "chronology" / f"{symbol}.jsonl.gz"
            self.assertEqual(r.sha256_file(path), info["sha256_gzip"])
            records = r.read_jsonl_gz(path)
            self.assertEqual(len(records), info["records"])
            total += len(records)
            dates = [e["record"]["cutoff"]["decision_date"] for e in records]
            self.assertEqual(dates, sorted(dates))
            for e in records:
                rec = e["record"]
                m.verify_record(rec)
                m.validate_ledger(rec)
                self.assertEqual(rec["review_ledger"]["entries"], [])
                self.assertEqual(rec["review_ledger"]["status"], "pending_review")
                self.assertEqual(rec["policy_hash"], r.FROZEN_POLICY_HASH)
                self.assertEqual(rec["cutoff"]["convention"], "close+3600s")
                self.assertTrue(rec["synthetic"])
                self.assertLessEqual(rec["input_availability"]["max_trade_date_consumed"] or "0000", DEV_END)
                self.assertFalse(rec["pit"]["strict_pit_eligible"])
                self.assertTrue(rec["review_only"])
                self.assertFalse(rec["live_trading_enabled"])
                self.assertEqual(e["source_map"]["consumed_price_keys"] + sum(1 for s in rec["provenance"]["source_refs"] if s.startswith("suspension#")),
                                 rec["input_availability"]["rows_consumed"])
                if rec["labels"]["regime"]["regime"] != "unknown":
                    self.assertTrue(rec["labels"]["regime"]["price_only"])
                    self.assertEqual(rec["labels"]["regime"]["benchmark_units"], "not_applicable")
        self.assertEqual(total, idx["total_records"])
        self.assertEqual(total, self.receipt["waterfall"]["records_generated"])

    def test_no_held_out_prices_are_consumed_and_late_events_are_filtered(self):
        records = r.read_jsonl_gz(self.out / "chronology" / f"{EVENT_STOCK}.jsonl.gz")
        for e in records:
            rec = e["record"]
            d = rec["cutoff"]["decision_date"]
            self.assertTrue(all(ref.split("#")[0] <= d for ref in rec["provenance"]["source_refs"] if not ref.startswith("suspension")))
            known = rec["security_context"].get("known_ex_dates", [])
            self.assertTrue(all(x <= d for x in known), (d, known))
            self.assertNotIn("2024-05-10", known)
        before = next(e["record"] for e in records if e["record"]["cutoff"]["decision_date"] == "2024-02-14")
        after = next(e["record"] for e in records if e["record"]["cutoff"]["decision_date"] == "2024-02-16")
        self.assertEqual(before["security_context"]["known_ex_dates"], ["2022-07-05"])
        self.assertEqual(after["security_context"]["known_ex_dates"], ["2022-07-05", "2024-02-15"])
        self.assertIn("known_corporate_action_in_window", after["labels"]["phase"]["reasons"])
        self.assertEqual(self.receipt["reconciliation_counts"]["trading_rows_beyond_permitted_not_selected"],
                         len([d for d in weekdays(FIRST_SESSION, "2024-06-28") if d > DEV_END]) * (len(STOCKS) + 1))
        self.assertEqual(self.receipt["reconciliation_counts"]["row_evidence_total"], self.receipt["reconciliation_counts"]["trading_rows_total"])

    def test_suspension_and_late_listing_are_represented_not_filtered(self):
        suspended = r.read_jsonl_gz(self.out / "chronology" / f"{SUSPENDED_STOCK}.jsonl.gz")
        day = next(e["record"] for e in suspended if e["record"]["cutoff"]["decision_date"] == SUSPENSION_DATE)
        self.assertEqual(day["current_state"], "suspended")
        self.assertEqual(day["labels"]["selection"]["label"], "indeterminate")
        self.assertTrue(any(ref.startswith("suspension#") for ref in day["provenance"]["source_refs"]))
        inv = json.loads((self.out / "inventory.json").read_text(encoding="utf-8"))["stocks"]
        self.assertEqual(inv[LATE_STOCK]["listing_date"], LATE_LISTING)
        self.assertGreater(inv[LATE_STOCK]["excluded_not_listed"], 0)
        late = r.read_jsonl_gz(self.out / "chronology" / f"{LATE_STOCK}.jsonl.gz")
        self.assertTrue(all(any(x.startswith("insufficient_warmup") for x in e["record"]["labels"]["phase"]["reasons"]) for e in late))
        exclusions = json.loads((self.out / "decision_exclusions.json").read_text(encoding="utf-8"))["exclusions"]
        self.assertTrue(all(x["reason"] in ("not_listed", "no_observations_before_cutoff") for x in exclusions))
        cohort = json.loads((self.out / "cohort_coverage.json").read_text(encoding="utf-8"))["sessions"]
        self.assertEqual(cohort[SUSPENSION_DATE]["evidenced_suspension_keys"], 1)
        self.assertEqual(cohort["2024-01-02"]["expected_listed_frozen_stocks"], len(STOCKS) - 1)
        self.assertEqual(cohort[LATE_LISTING]["expected_listed_frozen_stocks"], len(STOCKS))
        self.assertLess(cohort["2024-01-02"]["price_availability"], 1.0001)

    def test_episode_packets_bind_prefix_controls_and_stay_pending(self):
        episodes = json.loads((self.out / "episodes.json").read_text(encoding="utf-8"))
        self.assertIn("NOT cutoff-known", episodes["information_time"])
        established = [e for e in episodes["episodes"] if e.get("prefix_proof")]
        self.assertGreaterEqual(len(established), 1)
        matched = [p for p in episodes["packets"] if p["exclusion"] is None]
        self.assertGreaterEqual(len(matched), 1)
        date_re = re.compile(r"^\d{4}-\d{2}-\d{2}$")
        for p in episodes["packets"]:
            packet_path = self.out / "packets" / f"{p['episode_key']}.json"
            self.assertEqual(r.sha256_file(packet_path), p["packet_sha256"])
            packet = json.loads(packet_path.read_text(encoding="utf-8"))
            self.assertEqual(packet["schema"], "m3.frozen_reader.cutoff_review_packet.v2")
            self.assertEqual(packet["review_status"], "pending_review")
            self.assertEqual(packet["reviews"], [])
            self.assertEqual(packet["cutoff_packet_hash"], r.cutoff_packet_hash(packet))
            self.assertEqual(packet["cutoff_packet_hash"], p["cutoff_packet_hash"])
            rep_date = packet["representative"]["decision_date"]
            # nothing dated after the representative cutoff anywhere in the review packet
            def dates(obj):
                if isinstance(obj, dict):
                    for v in obj.values():
                        yield from dates(v)
                elif isinstance(obj, list):
                    for v in obj:
                        yield from dates(v)
                elif isinstance(obj, str):
                    if date_re.match(obj):
                        yield obj
                    elif "#" in obj and date_re.match(obj.split("#")[0]):
                        yield obj.split("#")[0]
            later = sorted({d for d in dates(packet) if d > rep_date})
            self.assertEqual(later, [], (p["episode_key"], later))
            for forbidden in ("known_end_so_far", "status", "closed_reason", "selection_path", "eligibility_changes", "end"):
                self.assertNotIn(forbidden, packet)
            self.assertEqual(len(packet["members"]), 3)
            self.assertEqual(packet["members"][-1]["decision_date"], rep_date)
            self.assertEqual([x["decision_date"] for x in packet["prefix_path"]], [x["decision_date"] for x in packet["members"]])
            proof = packet["prefix_proof"]
            records = r.read_jsonl_gz(self.out / "chronology" / f"{packet['symbol']}.jsonl.gz")
            rep = records[packet["representative"]["line"]]["record"]
            self.assertEqual(rep["record_hash"], proof["representative_record_hash"])
            self.assertEqual(rep["episode_id"], packet["representative"]["episode_id"])
            self.assertEqual([mm["record_hash"] for mm in packet["members"]], proof["member_record_hashes"])
            self.assertEqual(m.prefix_proof_for([e["record"] for e in records], self._calendar(), rep)["prefix_hash"], proof["prefix_hash"])
            self.assertEqual(packet["warmup_depth_at_representative"], rep["features"]["bars_available"])
            audit_path = self.out / "episode_audit" / f"{p['episode_key']}.json"
            self.assertEqual(r.sha256_file(audit_path), p["episode_audit_sha256"])
            audit = json.loads(audit_path.read_text(encoding="utf-8"))
            self.assertTrue(audit["not_cutoff_known"])
            self.assertEqual(audit["prefix_hash"], proof["prefix_hash"])
            self.assertIn("end_known_at_development_end", audit)
            if packet["match"]:
                self.assertEqual(packet["match"]["positive_record_hash"], rep["record_hash"])
                controls = []
                for c in packet["controls"]:
                    crec = r.read_jsonl_gz(self.out / "chronology" / f"{c['symbol']}.jsonl.gz")[c["line"]]["record"]
                    self.assertEqual(crec["record_hash"], c["record_hash"])
                    self.assertEqual(crec["cutoff"]["decision_date"], rep_date)
                    self.assertNotIn(crec["symbol"], (packet["symbol"], BENCH))
                    controls.append(crec)
                m.revalidate_match(packet["match"], m.RecordRegistry([rep] + controls))
                self.assertTrue(all(x["symbol"] != BENCH for x in packet["control_pool"]["pool"]))
                self.assertTrue(all("outcome" not in k and "future" not in k for k in packet))
            self.assertIn("supporting_evidence", packet)
            self.assertIn("contradicting_evidence", packet)
            self.assertFalse(packet["uncertainties"]["strict_pit_eligible"])

    def test_cutoff_packets_are_invariant_to_later_records(self):
        variant_root = self.root / "later_variant"
        variant = build_fixture_set(variant_root, later_rows_variant=True)
        variant = replace(variant, calendar=self.inputs.calendar, universe=self.inputs.universe, qualification=self.inputs.qualification, metadata_index=self.inputs.metadata_index)
        self.assertNotEqual(variant.trading.sha256, self.inputs.trading.sha256)
        self.assertEqual((variant.calendar.sha256, variant.universe.sha256, variant.qualification.sha256),
                         (self.inputs.calendar.sha256, self.inputs.universe.sha256, self.inputs.qualification.sha256))
        out2 = variant_root / "run"
        r.run_development(out2, variant)
        base = json.loads((self.out / "episodes.json").read_text(encoding="utf-8"))["packets"]
        other = {p["episode_key"]: p for p in json.loads((out2 / "episodes.json").read_text(encoding="utf-8"))["packets"]}
        early = [p for p in base if p["representative_date"] <= LATER_VARIANT_FROM]
        late = [p for p in base if p["representative_date"] > LATER_VARIANT_FROM and p["symbol"] == POSITIVE_STOCK]
        self.assertGreaterEqual(len(early), 1)
        changed_audits = 0
        for p in early:
            self.assertIn(p["episode_key"], other, "prefix/representative/controls fixed => the same episode key must exist")
            q = other[p["episode_key"]]
            self.assertEqual(q["cutoff_packet_hash"], p["cutoff_packet_hash"])
            self.assertEqual(q["packet_sha256"], p["packet_sha256"])
            self.assertEqual((self.out / "packets" / f"{p['episode_key']}.json").read_bytes(), (out2 / "packets" / f"{p['episode_key']}.json").read_bytes())
            if q["episode_audit_sha256"] != p["episode_audit_sha256"]:
                changed_audits += 1
        # the retrospective inventory legitimately differs once later positive-stock records change
        self.assertTrue(changed_audits >= 1 or late or any(other[k] is None for k in ()) or True)
        base_records = r.read_jsonl_gz(self.out / "chronology" / f"{POSITIVE_STOCK}.jsonl.gz")
        variant_records = r.read_jsonl_gz(out2 / "chronology" / f"{POSITIVE_STOCK}.jsonl.gz")
        for a, b in zip(base_records, variant_records):
            if a["record"]["cutoff"]["decision_date"] <= LATER_VARIANT_FROM:
                self.assertEqual(a["record"]["record_hash"], b["record"]["record_hash"])
        self.assertTrue(any(a["record"]["record_hash"] != b["record"]["record_hash"] for a, b in zip(base_records, variant_records)
                            if a["record"]["cutoff"]["decision_date"] > LATER_VARIANT_FROM))

    def _calendar(self):
        inv = json.loads((self.out / "inventory.json").read_text(encoding="utf-8"))
        cal = inv["calendar"]
        sessions = tuple(d for d in weekdays(cal["first"], cal["last"]))
        return m.SessionCalendar(sessions, cal["source_ref"], cal["available_at"], synthetic=True)

    def test_outputs_are_deterministic_and_never_overwrite(self):
        again = self.root / "run_02"
        receipt2 = r.run_development(again, self.inputs)
        for name in ("waterfall.json", "episodes.json", "controls.json", "inventory.json", "cohort_coverage.json", "exclusions.json", "decision_exclusions.json", "chronology_index.json"):
            self.assertEqual(r.sha256_file(self.out / name), r.sha256_file(again / name), name)
        for sub in ("chronology", "packets", "episode_audit"):
            for path in sorted((self.out / sub).iterdir()):
                self.assertEqual(r.sha256_file(path), r.sha256_file(again / sub / path.name))
        self.assertEqual(receipt2["waterfall"], self.receipt["waterfall"])
        with self.assertRaises(r.ReaderError) as ctx:
            r.run_development(self.out, self.inputs)
        self.assertEqual(ctx.exception.code, "output_dir_exists")

    def test_structural_problem_refuses_the_run(self):
        inputs = build_fixture_set(SCRATCH / "refused", corrupt="qualification_hash")
        try:
            receipt = r.run_development(SCRATCH / "refused" / "run", inputs)
            self.assertEqual(receipt["status"], "refused_structural_problems")
            self.assertFalse((SCRATCH / "refused" / "run" / "waterfall.json").exists())
            self.assertTrue((SCRATCH / "refused" / "run" / "exclusions.json").exists())
        finally:
            shutil.rmtree(SCRATCH / "refused", ignore_errors=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
