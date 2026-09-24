"""M4-03B runner: guarded synthetic validation -> ONE bounded read of the two pinned candidate stores -> reconciliation
and sealing -> four predeclared branches x two repeats over the frozen engines -> receipts under claude_03b/runs/<run_id>/.

Order of operations (each step aborts the run with a failure receipt; nothing is retried or widened):
  1. guard install + self-check (synthetic mode: every SQLite connect denied);
  2. the pre-work verification receipt (claude_03b/evidence/prework_verification.json) must be clean and its recorded
     database states must equal the files now; in-process byte re-verification of every pinned input;
  3. the synthetic test module runs in-process (13 focused tests incl. the two-symbol global-order case and the
     future-suffix control) and must pass;
  4. read phase: exactly two connections (file:<posix>?mode=ro&immutable=1, uri=True, isolation_level=None),
     extension loading disabled, PRAGMA query_only=ON read back == 1, authorizer SELECT/READ/FUNCTION/read-pragma
     only; Q1-Q9 exactly as the accepted proposal (Q10 omitted); rows fetched once; connections closed in finally;
     files re-verified; guard left read phase;
  5. reconciliation exactly as the frozen reader's rules + the prior audit's totals and numeric digest; sealed snapshot;
  6. branches assumed_full_fill / assumed_fixed_5000 / assumed_capacity_none / raw, each twice from the sealed snapshot
     on a fresh ledger; output hashes must agree between repeats;
  7. outputs written once (run folder must not exist).

    backend/.venv/Scripts/python.exe -B -X utf8 "claude methods/_m4_20260912/claude_03b/run_m4_03b_replay.py"
"""
from __future__ import annotations

import csv
import hashlib
import importlib.util
import io
import json
import sqlite3
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[2]
EVIDENCE = HERE / "evidence"
RUNS = HERE / "runs"
sys.dont_write_bytecode = True
M2_RUN = PROJECT / "claude methods/_m2_codex_implementation_20260910/staging_runs/ths_v2_20260910_041710_97ef9c09/run_ths_v2_20260910_041710_97ef9c09"
STORES = {"trading": (M2_RUN / "trading.sqlite3", "c0b26660ab903541e7e213ee312c565be73547bb3cc8c142486999717e3edeca", 38969344),
          "history": (M2_RUN / "history.sqlite3", "eda17434ab67496c33eed275b35045c140bad72802b4dcbf981ff22422c53003", 10604544)}
INPUTS = {
    "qualification": ("claude methods/_m2_codex_implementation_20260910/qualification_v2_reviewed.json", "992bd79ce9d2e38d1a0a8ae2f9890cd26daebcd3d2ab664d5caab171ec3e0f37"),
    "metadata_index": ("claude methods/_m3_20260910/codex/metadata_index_01/index.json", "14f1bad7d393b4e15bf73111a9d96a78c8b156784f9ccbb084d6b606d3a152e9"),
    "calendar": ("backend/.venv/Lib/site-packages/akshare/file_fold/calendar.json", "f1f1ce33c5cceb5c530c3271fc951405cb5624d2f30becec85dc7a85fd47e656"),
    "pilot": ("claude methods/_m1_closure/pilot_symbols.csv", "97e251ae84fc927486127a96b4966ed8fc59fac0b744b7d6f186b2b1548886fe"),
    "audit_result": ("claude methods/_m3_20260910/codex/development_input_audit_01/result.json", "dd3ac6ffde13ba0127a39163d23e3cebb148ca9a93f90d25c17cd4a22402d157"),
    "proposal": ("claude methods/_m4_20260912/claude_03a/NEXT_READ_PROPOSAL.md", "b7c9c3346341ba38b597c36d18f80f34ed0ab532168ea45d22283555731b5203"),
    "task_file": ("claude methods/M4_03B_DEVELOPMENT_REPLAY_CLAUDE_TASK_20260912.md", "8290d8c862dfa507c97e501cdfea8df79de65af729df72c42970727456d00816"),
}
END = "2025-03-31"
QUERIES = [
    ("Q1_trading_prices", "trading", "SELECT symbol, trade_date, open, high, low, close, volume, amount, source, quality_status, adjustment_mode, volume_unit FROM daily_bar_cache WHERE trade_date <= ? ORDER BY symbol, trade_date", (END,), 27900),
    ("Q2_history_prices", "history", "SELECT symbol, trade_date, adjustment_mode, open, high, low, close, volume, amount, provider, fetched_at, ingest_run_id FROM daily_bars WHERE trade_date <= ? ORDER BY symbol, trade_date", (END,), 27900),
    ("Q3_row_evidence", "trading", "SELECT symbol, trade_date, raw_sha256, request_sha256, producer_sha256, parser_sha256, capture_receipt_sha256, capture_producer_manifest_sha256, observed_at, point_index, qualification_sha256, source_name, source_name_status FROM row_evidence WHERE trade_date <= ? ORDER BY symbol, trade_date", (END,), 27900),
    ("Q4_coverage_trading", "trading", "SELECT symbol, trade_date, classification FROM coverage_inventory WHERE trade_date <= ? ORDER BY symbol, trade_date", (END,), 28100),
    ("Q4_coverage_history", "history", "SELECT symbol, trade_date, classification FROM coverage_inventory WHERE trade_date <= ? ORDER BY symbol, trade_date", (END,), 28100),
    ("Q5_suspensions_trading", "trading", "SELECT symbol, trade_date, evidence_sha256, record_json FROM suspension_records WHERE trade_date <= ? ORDER BY symbol, trade_date", (END,), 200),
    ("Q5_suspensions_history", "history", "SELECT symbol, trade_date, evidence_sha256, record_json FROM suspension_records WHERE trade_date <= ? ORDER BY symbol, trade_date", (END,), 200),
    ("Q6_qualification_records", "trading", "SELECT symbol, record_sha256, record_json FROM qualification_records ORDER BY symbol", (), 52),
    ("Q7_instruments", "trading", "SELECT symbol FROM instruments", (), 52),
    ("Q8_contract_trading", "trading", "SELECT contract_json FROM dataset_contract", (), 1),
    ("Q8_contract_history", "history", "SELECT contract_json FROM dataset_contract", (), 1),
    ("Q9_ingest_runs", "history", "SELECT id, run_id FROM ingest_runs", (), 1),
]
ALLOWED_PRAGMAS = {"query_only", "table_info", "page_count", "page_size", "schema_version", "index_list", "index_info"}


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def store_state(path: Path) -> dict:
    st = path.stat()
    return {"resolved": str(path.resolve()), "sha256": sha256(path), "bytes": st.st_size, "mtime_ns": st.st_mtime_ns,
            "sidecars_present": {s: Path(str(path) + s).exists() for s in ("-wal", "-shm", "-journal")}}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class RunFailure(RuntimeError):
    pass


def write_json(path: Path, payload) -> str:
    text = json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True, default=str) + "\n"
    path.write_text(text, encoding="utf-8")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main() -> int:
    started = now()
    guard = load_module("m4_03b_guard", HERE / "guard.py")
    guard.install()
    EVIDENCE.mkdir(exist_ok=True)
    RUNS.mkdir(exist_ok=True)
    receipt: dict = {"schema": "m4.claude_03b.run_receipt.v1", "task_id": "M4-03B-DEVELOPMENT-REPLAY-20260912", "started_at_utc": started,
                     "command": [sys.executable, "-B", "-X", "utf8", str(Path(__file__).resolve().relative_to(PROJECT).as_posix())], "steps": [], "passed": False}
    failure_path = EVIDENCE / f"run_failure_{started.replace(':', '').replace('-', '').replace('.', '')[:15]}.json"

    def step(name: str, **info):
        receipt["steps"].append({"step": name, "at_utc": now(), **info})

    try:
        # 1. guard self-check
        receipt["guard_self_check"] = guard.self_check(EVIDENCE)
        if any(v != "denied" for k, v in receipt["guard_self_check"].items() if k not in ("probe_file_created", "write_inside_claude_03b", "self_check_denials")) or receipt["guard_self_check"]["probe_file_created"]:
            raise RunFailure("guard self-check did not deny every probe")
        step("guard_self_check", outcome=receipt["guard_self_check"])
        # 2. pre-work receipt + in-process byte verification
        pre_path = EVIDENCE / "prework_verification.json"
        pre = json.loads(pre_path.read_text(encoding="utf-8"))
        if not pre["ok"]:
            raise RunFailure("pre-work verification not clean")
        inputs_state = {}
        for key, (rel, expected) in INPUTS.items():
            got = sha256(PROJECT / rel)
            inputs_state[rel] = {"sha256": got, "ok": got == expected}
            if got != expected:
                raise RunFailure(f"input hash mismatch {rel}")
        stores_before = {}
        for key, (path, expected, size) in STORES.items():
            st = store_state(path)
            rel = path.resolve().relative_to(PROJECT).as_posix()
            recorded = pre["candidate_databases"][rel]
            ok = st["sha256"] == expected and st["bytes"] == size and not any(st["sidecars_present"].values()) and st["mtime_ns"] == recorded["mtime_ns"] and st["sha256"] == recorded["sha256"]
            stores_before[key] = {**st, "expected": expected, "ok": ok, "matches_prework_receipt": st["mtime_ns"] == recorded["mtime_ns"]}
            if not ok:
                raise RunFailure(f"store state changed or wrong: {key}")
        receipt["inputs"], receipt["stores_before_read"] = inputs_state, stores_before
        step("input_verification", inputs=len(inputs_state), stores_ok=True, prework_receipt_sha256=sha256(pre_path))
        # 3. synthetic validation in-process
        core = load_module("m4_03b_replay_core", HERE / "replay_core.py")
        mods = core.load_frozen(PROJECT)
        tests = load_module("m4_03b_test_replay_synthetic", HERE / "test_replay_synthetic.py")
        stream = io.StringIO()
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(tests))
        synthetic_receipt = {"tests_run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors), "skipped": len(result.skipped), "successful": result.wasSuccessful(),
                             "stdout": stream.getvalue(), "scenarios": tests.SCENARIOS, "guard_denials_during_tests": len(guard.DENIAL_LOG)}
        write_json(EVIDENCE / "synthetic_test_receipt.json", synthetic_receipt)
        receipt["synthetic_validation"] = {k: v for k, v in synthetic_receipt.items() if k not in ("stdout", "scenarios")}
        if not result.wasSuccessful() or guard.DENIAL_LOG or result.testsRun < 13:
            raise RunFailure("synthetic validation failed; no historical read is attempted")
        step("synthetic_validation", tests_run=result.testsRun, successful=True)
        # 4. read phase --------------------------------------------------------------------------------------------
        allowed = guard.enter_read_phase([STORES["trading"][0], STORES["history"][0]])
        conns: dict[str, sqlite3.Connection] = {}
        sql_log, rows = [], {}
        connection_audit = {}
        try:
            for key, (path, expected, size) in STORES.items():
                uri = guard.uri_for(path)
                conn = sqlite3.connect(uri, uri=True, isolation_level=None)
                try:
                    conn.enable_load_extension(False)
                    ext = "disabled"
                except AttributeError:
                    ext = "unavailable_in_build"
                conn.execute("PRAGMA query_only=ON")
                qo = conn.execute("PRAGMA query_only").fetchone()[0]
                if qo != 1:
                    raise RunFailure(f"query_only read-back {qo!r}")

                def authorize(action, a1, a2, dbname, source, _allowed=ALLOWED_PRAGMAS):
                    if action in (sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION):
                        return sqlite3.SQLITE_OK
                    if action == sqlite3.SQLITE_PRAGMA and a1 in _allowed and a2 is None:
                        return sqlite3.SQLITE_OK
                    return sqlite3.SQLITE_DENY

                conn.set_authorizer(authorize)
                conns[key] = conn
                connection_audit[key] = {"uri": uri, "uri_flags": "mode=ro&immutable=1", "uri_true": True, "isolation_level": None, "query_only_read_back": qo,
                                         "extension_loading": ext, "authorizer": "SELECT/READ/FUNCTION + read-only pragmas; everything else SQLITE_DENY"}
            for name, store, sql, params, expected_rows in QUERIES:
                fetched = conns[store].execute(sql, params).fetchall()
                rows[name] = [tuple(r) for r in fetched]
                sql_log.append({"name": name, "store": store, "uri": connection_audit[store]["uri"], "sql": sql, "parameters": list(params), "rows": len(fetched), "expected_rows": expected_rows})
                if len(fetched) != expected_rows:
                    raise RunFailure(f"row count mismatch {name}: {len(fetched)} != {expected_rows}")
        finally:
            for c in conns.values():
                c.close()
            guard.leave_read_phase()
        stores_after = {key: store_state(path) for key, (path, expected, size) in STORES.items()}
        for key in STORES:
            if {k: stores_after[key][k] for k in ("sha256", "bytes", "mtime_ns")} != {k: stores_before[key][k] for k in ("sha256", "bytes", "mtime_ns")} or any(stores_after[key]["sidecars_present"].values()):
                raise RunFailure(f"store modified during read: {key}")
        receipt["read_phase"] = {"allowed_uris": allowed, "connections": connection_audit, "connections_opened": len(guard.CONNECTIONS), "guard_connection_log": guard.CONNECTIONS,
                                 "sql_log": sql_log, "stores_after_read": stores_after, "denials_during_read": len(guard.DENIAL_LOG), "q10_omitted": True}
        if len(guard.CONNECTIONS) != 2 or guard.DENIAL_LOG:
            raise RunFailure("connection count or denials unexpected")
        step("read_phase", connections=2, queries=len(sql_log))
        # 5. reconciliation + sealing ---------------------------------------------------------------------------------
        qualification = json.loads((PROJECT / INPUTS["qualification"][0]).read_text(encoding="utf-8"))
        index_doc = json.loads((PROJECT / INPUTS["metadata_index"][0]).read_text(encoding="utf-8"))
        calendar_raw = json.loads((PROJECT / INPUTS["calendar"][0]).read_text(encoding="utf-8"))
        pilot = list(csv.DictReader((PROJECT / INPUTS["pilot"][0]).open(encoding="utf-8")))
        audit = json.loads((PROJECT / INPUTS["audit_result"][0]).read_text(encoding="utf-8"))
        snap, recon = core.snapshot_from_rows(rows, qualification, index_doc, calendar_raw, pilot)
        recon["audit_numeric_rows_sha256"] = audit["numeric_rows_sha256"]
        recon["numeric_digest_matches_prior_audit"] = recon.get("numeric_rows_sha256") == audit["numeric_rows_sha256"]
        recon["prior_audit_totals"] = {"price_keys_selected": audit["price_keys_selected"], "suspension_keys_selected": audit["suspension_keys_selected"], "development_sessions": audit["development_sessions"]}
        if snap is None or not recon["passed"] or recon["exclusion_count"] != 0 or recon["accepted_price_keys"] != 27900 or recon["accepted_halt_keys"] != 200 or not recon["numeric_digest_matches_prior_audit"]:
            raise RunFailure(f"reconciliation failed: {recon.get('problems')} exclusions={recon.get('exclusion_count')}")
        depths = core.warmup_depths(snap)
        input_hash, mhash = snap.input_hash, core.model_hash(mods)
        run_id = core.sha256_text(input_hash + mhash)[:16]
        run_dir = RUNS / run_id
        if run_dir.exists():
            raise RunFailure(f"run folder exists: {run_dir}; refusing to overwrite")
        receipt["sealed_input"] = {"input_hash": input_hash, "model_hash": mhash, "run_id": run_id, "bars": sum(len(v) for v in snap.bars.values()), "halt_keys": sum(len(v) for v in snap.halts.values()),
                                   "stocks": len(snap.stocks), "calendar_slice": recon["calendar"], "numeric_rows_sha256": recon["numeric_rows_sha256"], "matches_prior_audit_digest": recon["numeric_digest_matches_prior_audit"]}
        step("reconciliation_and_seal", input_hash=input_hash, run_id=run_id)
        # 6. branches x 2 --------------------------------------------------------------------------------------------
        branch_results, determinism = {}, {}
        for branch in core.BRANCHES:
            first = core.Replay(mods, snap, branch).run()
            second = core.Replay(mods, snap, branch).run()
            h1, h2 = core.output_hash(first), core.output_hash(second)
            determinism[branch] = {"repeat_1_output_hash": h1, "repeat_2_output_hash": h2, "identical": h1 == h2, "engine_chain_hash": first["engine_chain_hash"], "ledger_state_hash": first["ledger_state_hash"],
                                   "repeat_2_engine_chain_hash": second["engine_chain_hash"]}
            if h1 != h2:
                raise RunFailure(f"non-deterministic branch {branch}")
            branch_results[branch] = first
            step("branch", branch=branch, output_hash=h1, records=len(first["records"]))
        # 7. outputs ----------------------------------------------------------------------------------------------
        run_dir.mkdir(parents=True)
        files = {}
        files["sql_log.json"] = write_json(run_dir / "sql_log.json", {"connections": connection_audit, "queries": sql_log, "q10_omitted": True})
        files["reconciliation.json"] = write_json(run_dir / "reconciliation.json", recon)
        files["warmup_depths.json"] = write_json(run_dir / "warmup_depths.json", {"window": [core.WARM_START, core.WARM_END], "per_symbol": depths,
                                                                                 "stocks_with_full_250": sum(1 for s, d in depths.items() if snap.roles[s] == "stock" and d["bars_in_window"] == 250),
                                                                                 "stocks_with_zero": sum(1 for s, d in depths.items() if snap.roles[s] == "stock" and d["bars_in_window"] == 0)})
        branches_out = {}
        for branch, res in branch_results.items():
            bdir = run_dir / "branches" / branch
            bdir.mkdir(parents=True)
            rec = core.write_jsonl_gz(bdir / "research_records.jsonl.gz", res["records"])
            led = core.write_jsonl_gz(bdir / "ledger_records.jsonl.gz", res["ledger_records"])
            summary = {"branch": branch, "variant": res["variant"], "capacity_variant": res["capacity_variant"], "funnel": res["funnel"], "per_symbol": res["per_symbol"],
                       "performance": res["performance"], "censored": res["censored"], "diagnostics": res["diagnostics"], "ledger_snapshot": res["ledger_snapshot"],
                       "ledger_reconcile": res["ledger_reconcile"], "reservations_final": res["reservations_final"], "engine_chain_hash": res["engine_chain_hash"],
                       "ledger_state_hash": res["ledger_state_hash"], "output_hash": determinism[branch]["repeat_1_output_hash"], "records": rec, "ledger_records_file": led}
            files[f"branches/{branch}/summary.json"] = write_json(bdir / "summary.json", summary)
            files[f"branches/{branch}/research_records.jsonl.gz"] = rec["file_sha256"]
            files[f"branches/{branch}/ledger_records.jsonl.gz"] = led["file_sha256"]
            branches_out[branch] = {"funnel": res["funnel"], "performance": {k: res["performance"].get(k) for k in ("status", "complete", "cash", "equity", "return", "realized_pnl_total", "unresolved_positions")},
                                    "benchmark": res["performance"].get("benchmark"), "censored": res["censored"], "records": rec["records"], "ledger_records": led["records"],
                                    "ledger_reconcile_ok": res["ledger_reconcile"]["ok"], "capacity_ids": len(res["ledger_reconcile"].get("capacity", {}))}
        files["funnel.json"] = write_json(run_dir / "funnel.json", {"branches": branches_out, "determinism": determinism})
        receipt.update({"run_dir": run_dir.relative_to(PROJECT).as_posix(), "run_id": run_id, "branches": branches_out, "determinism": determinism, "files": files,
                        "stores_final": {key: store_state(path) for key, (path, expected, size) in STORES.items()}, "guard": guard.receipt(), "frozen_hashes": mods["hashes"],
                        "engine_policy_hashes": {"kernel": mods["k"].POLICY_HASH, "ledger": mods["p"].LEDGER_POLICY_HASH, "risk": mods["r"].RISK_POLICY_HASH},
                        "safety": {"sqlite_connections": len(guard.CONNECTIONS), "production_sqlite_connections": 0, "network_requests": 0, "holdout_price_rows_read": 0,
                                   "review_only": True, "live_trading_enabled": False, "training_eligible": False, "strict_pit": False, "M4_complete": False, "M5_started": False},
                        "passed": True, "finished_at_utc": now()})
        receipt["files"]["receipt.json"] = None
        write_json(run_dir / "receipt.json", receipt)
        print(json.dumps({"passed": True, "run_id": run_id, "run_dir": receipt["run_dir"], "connections": len(guard.CONNECTIONS), "input_hash": input_hash,
                          "branches": {b: {"attempts": v["funnel"]["attempt_outcomes"], "performance": v["performance"]} for b, v in branches_out.items()},
                          "determinism": {b: v["identical"] for b, v in determinism.items()}}, ensure_ascii=False, indent=1))
        return 0
    except Exception as exc:  # noqa: BLE001 - preserve the failure receipt
        receipt.update({"passed": False, "failure": f"{type(exc).__name__}: {exc}", "guard": guard.receipt(), "finished_at_utc": now()})
        write_json(failure_path, receipt)
        print(json.dumps({"passed": False, "failure": receipt["failure"], "receipt": failure_path.relative_to(PROJECT).as_posix()}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())
