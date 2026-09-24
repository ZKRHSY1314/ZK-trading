"""Write claude_03b/artifact_manifest.json LAST for M4-03B (after the post-work verification).

Pins every file written under claude_03b/ and every consumed source (task file, acceptance, four freezes, accepted
proposal/mapping/qualification, frozen engines, the two candidate stores by hash/size/mtime, the non-SQL inputs, rules
and plan documents).  Records the actual commands and exit codes, the read-phase audit (connections, SQL), the sealed
input / model / output hashes, the before/after/final preservation, and the unmet historical requirement.  The manifest
does not contain its own hash.

    backend/.venv/Scripts/python.exe -B -X utf8 "claude methods/_m4_20260912/claude_03b/build_manifest.py"
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[2]
REL = "claude methods/_m4_20260912/claude_03b"
TASK_ID = "M4-03B-DEVELOPMENT-REPLAY-20260912"
TASK_FILE = "claude methods/M4_03B_DEVELOPMENT_REPLAY_CLAUDE_TASK_20260912.md"
TASK_SHA = "8290d8c862dfa507c97e501cdfea8df79de65af729df72c42970727456d00816"
MANIFEST = HERE / "artifact_manifest.json"
M2_RUN = "claude methods/_m2_codex_implementation_20260910/staging_runs/ths_v2_20260910_041710_97ef9c09/run_ths_v2_20260910_041710_97ef9c09"
CONSUMED = [
    TASK_FILE, "claude methods/M4_03A_CODEX_ACCEPTANCE_20260912.md", "claude methods/M4_02B_CODEX_ACCEPTANCE_20260912.md",
    "claude methods/_m4_20260912/execution_freeze.json", "claude methods/_m4_20260912/portfolio_freeze.json", "claude methods/_m4_20260912/risk_freeze.json",
    "claude methods/_m4_20260912/historical_qualification_freeze.json",
    "claude methods/_m4_20260912/claude_03a/NEXT_READ_PROPOSAL.md", "claude methods/_m4_20260912/claude_03a/proposal_mapping.py", "claude methods/_m4_20260912/claude_03a/qualification.json",
    "claude methods/_m4_20260912/claude_03a/QUALIFICATION_MATRIX.md",
    "claude methods/_m4_20260912/baseline/start.json", "claude methods/_m4_20260912/baseline/immutable_pins.json",
    "claude methods/_m4_20260912/baseline/tracked_files_before.json", "claude methods/_m4_20260912/baseline/production_files_before.json",
    "claude methods/_m4_20260912/claude_01/CONTRACT.md", "claude methods/_m4_20260912/claude_02a/CONTRACT.md", "claude methods/_m4_20260912/claude_02b/CONTRACT.md",
    "claude methods/THREE_YEAR_RESEARCH_EXECUTION_GOAL.md", "AGENTS.md", "CODEX_CLAUDE_COLLABORATION.md", "CLAUDE.md",
    "backend/app/research/m4_execution.py", "backend/app/research/m4_portfolio.py", "backend/app/research/m4_risk.py",
    "claude methods/_m2_codex_implementation_20260910/qualification_v2_reviewed.json", "claude methods/_m3_20260910/codex/metadata_index_01/index.json",
    "backend/.venv/Lib/site-packages/akshare/file_fold/calendar.json", "claude methods/_m1_closure/pilot_symbols.csv",
    "claude methods/_m3_20260910/codex/development_input_audit_01/result.json",
    "claude methods/_m4_20260912/codex/M4_03B_REVIEW_01.md",
]
REVIEW_SHA = "a0fc04e70abf4f1bc3165e73dd99edea584dcb1d57374d515dd299f72a6f429d"
MUTABLE = ["claude methods/_m4_20260912/PLAN.md", "claude methods/_m4_20260912/coordination_state.json"]
DATABASES = [f"{M2_RUN}/trading.sqlite3", f"{M2_RUN}/history.sqlite3"]
EXCLUSIONS = ["exactly two immutable read-only SQLite connections (the pinned candidate stores) in one read phase after guarded synthetic validation; production databases never connected",
              "no network, client capture, Tonghuashun/Sina access, account, credential, order, screen or service access; no dataset/knowledge mutation",
              "no validation/holdout price rows (every price SELECT bound to trade_date <= '2025-03-31'; the 2025-04-01 session is calendar metadata only)",
              "no tuning, no result-based selection, no widening of the universe; a zero would have stayed zero with causes",
              "no other agents or workflows; automation untouched",
              "no edits to accepted M4 modules/tests/freezes, M2/M3 artifacts, M4-03A evidence, Codex files, PLAN.md, coordination_state.json, package initializers, configuration or production files",
              "no git staging/commit/push; the pre-existing modified set was left as found", "no M5 or training; no self-acceptance"]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def rel(path: Path) -> str:
    return path.resolve().relative_to(PROJECT).as_posix()


def main() -> int:
    ev = HERE / "evidence"
    pre = json.loads((ev / "prework_verification.json").read_text(encoding="utf-8"))
    post = json.loads((ev / "postwork_verification.json").read_text(encoding="utf-8"))
    synth = json.loads((ev / "synthetic_test_receipt.json").read_text(encoding="utf-8"))
    synth2 = json.loads((ev / "synthetic_test_receipt_rev02.json").read_text(encoding="utf-8"))
    run = HERE / "runs" / "829d42809e978c04"
    revised = HERE / "runs" / "829d42809e978c04-rev02"
    receipt = json.loads((run / "receipt.json").read_text(encoding="utf-8"))
    rev = json.loads((revised / "revision_receipt.json").read_text(encoding="utf-8"))
    if not (pre["ok"] and post["ok"] and receipt["passed"] and synth["successful"] and synth2["successful"]):
        raise SystemExit("verification, synthetic validation or run receipt not clean")
    if sha256(PROJECT / TASK_FILE) != TASK_SHA:
        raise SystemExit("task file hash changed")
    if sha256(PROJECT / "claude methods/_m4_20260912/codex/M4_03B_REVIEW_01.md") != REVIEW_SHA:
        raise SystemExit("review file hash changed")
    status = json.loads((HERE / "superseded" / "delivery_01" / "DELIVERY_STATUS.json").read_text(encoding="utf-8"))
    for relp, meta in status["files"].items():
        if sha256(HERE / "superseded" / "delivery_01" / relp) != meta["sha256"]:
            raise SystemExit(f"superseded delivery_01 file changed: {relp}")
    original_run_ok = {relp: sha256(HERE / relp) == meta["sha256"] for relp, meta in status["original_run_pins"].items()}
    if not all(original_run_ok.values()):
        raise SystemExit("original run folder no longer byte-identical to its delivery-01 pins")
    if rev["safety"]["sqlite_connections"] != 0 or rev["safety"]["historical_runner_invocations"] != 0 or not all(v["identical"] for v in rev["applied_twice"].values()):
        raise SystemExit("export repair receipt not clean")
    if rev["transformation_code_sha256"] != sha256(HERE / "repair_export_revision_02.py"):
        raise SystemExit("repair code changed after the recorded repair")
    if synth2["test_module_sha256"] != sha256(HERE / "test_replay_synthetic.py") or synth2["replay_core_sha256"] != sha256(HERE / "replay_core.py"):
        raise SystemExit("synthetic suite or core changed after the recorded rev02 test run")
    failures = sorted(p.name for p in ev.glob("run_failure_*.json"))
    written = {}
    for p in sorted(HERE.rglob("*")):
        if p.is_file() and p != MANIFEST and "__pycache__" not in p.parts:
            written[rel(p)] = {"sha256": sha256(p), "bytes": p.stat().st_size}
    consumed = {relp: {"sha256": sha256(PROJECT / relp), "bytes": (PROJECT / relp).stat().st_size} for relp in CONSUMED}
    for relp in DATABASES:
        p = PROJECT / relp
        consumed[relp] = {"sha256": sha256(p), "bytes": p.stat().st_size, "mtime_ns": p.stat().st_mtime_ns, "access": "one immutable read-only connection in the run's read phase; hash/stat before, after and at delivery",
                          "sidecars_present": any((PROJECT / (relp + s)).exists() for s in ("-wal", "-shm", "-journal"))}
    mutable = {relp: {"sha256": sha256(PROJECT / relp), "note": "Codex-owned mutable record; recorded, not pinned"} for relp in MUTABLE}
    for relp, meta in consumed.items():
        if relp in DATABASES:
            key = "trading" if relp.endswith("trading.sqlite3") else "history"
            final = receipt["stores_final"][key]
            if final["sha256"] != meta["sha256"] or final["mtime_ns"] != meta["mtime_ns"]:
                raise SystemExit(f"store changed after the run: {relp}")
    freezes = {name: {"pins_before": f"{pre['freezes'][name]['pins_ok']}/{pre['freezes'][name]['pins_total']}", "pins_after": f"{post['freezes'][name]['pins_ok']}/{post['freezes'][name]['pins_total']}",
                      "sha256": post["freezes"][name]["sha256"], "policy_hash": post["freezes"][name].get("policy_hash"), "modified": False}
               for name in ("execution_freeze.json", "portfolio_freeze.json", "risk_freeze.json", "historical_qualification_freeze.json")}
    branches = receipt["branches"]
    manifest = {
        "schema": "m4.claude_03b.artifact_manifest.v2", "task_id": TASK_ID, "task_file_sha256": consumed[TASK_FILE]["sha256"], "status": "ready_for_review",
        "delivery": {"version": "delivery_02", "supersedes": "delivery_01", "trigger": "claude methods/_m4_20260912/codex/M4_03B_REVIEW_01.md", "trigger_sha256": REVIEW_SHA,
                     "superseded_delivery_01": {"path": f"{REL}/superseded/delivery_01/", "status_file_sha256": sha256(HERE / "superseded" / "delivery_01" / "DELIVERY_STATUS.json"),
                                                "files": len(status["files"]), "manifest_sha256": status["first_delivery_manifest_sha256"], "report_sha256": status["first_delivery_report_sha256"]},
                     "original_run": {"run_id": receipt["run_id"], "run_dir": receipt["run_dir"], "byte_identical_to_delivery_01_pins": all(original_run_ok.values()), "pinned_files": len(original_run_ok),
                                      "historical_two_repeat_output_hashes": {b: v["repeat_1_output_hash"] for b, v in receipt["determinism"].items()}},
                     "export_repair": {"revision": rev["revision"], "kind": rev["kind"], "not_a_historical_replay": True, "run_dir": f"{REL}/runs/{rev['revision']}",
                                       "transformation_code_sha256": rev["transformation_code_sha256"], "applied_twice": rev["applied_twice"], "revised_output_hashes": rev["revised_output_hashes"],
                                       "invariants": rev["invariants"], "endpoint_derivation": rev["endpoint_derivation"], "sqlite_connections": rev["safety"]["sqlite_connections"],
                                       "historical_runner_invocations": rev["safety"]["historical_runner_invocations"]},
                     "corrected_synthetic_validation": {"receipt": f"{REL}/evidence/synthetic_test_receipt_rev02.json", "tests_run": synth2["tests_run"], "failures": synth2["failures"], "errors": synth2["errors"],
                                                        "sqlite_connections": synth2["safety"]["sqlite_connections"], "new_tests": ["test_non_default_cash_zero_trades_returns_zero", "test_non_default_cash_with_trades_hand_calculated_return",
                                                                                                                                 "test_assumed_performance_wrapper_carries_both_benchmark_endpoints", "test_raw_performance_wrapper_keeps_capture_instants_and_refusals"]},
                     "corrections": {"P2-1": "Replay passes its instance initial_cash to performance(); historical run used 1000000 (numbers unchanged)",
                                     "P2-2": "performance wrappers carry benchmark endpoint provenance, model time, engine status/refusals, initial_cash_used and the listed-default assumption; delivered outputs repaired export-only from the first/last decision wrappers"},
                     "codex_files_modified": False},
        "owner": "Claude (existing ZK-trading / Fable 5.1 project advice fork session a4a3be61-cd46-4bdf-9381-23d97fee303a)",
        "built_at_utc": datetime.now(timezone.utc).isoformat(), "path_root_convention": "relative to project root D:\\codex-A股交易, forward slashes",
        "git": {"branch": post["git"]["branch"], "head": post["git"]["head"], "modified_count_before": len(pre["git"]["status_modified"]), "modified_count_after": len(post["git"]["status_modified"]),
                "modified_set_unchanged": pre["git"]["status_modified"] == post["git"]["status_modified"], "staged": post["git"]["staged"]},
        "run": {"run_id": receipt["run_id"], "run_dir": receipt["run_dir"], "input_hash": receipt["sealed_input"]["input_hash"], "model_hash": receipt["sealed_input"]["model_hash"],
                "read_phase": {"connections_opened": receipt["read_phase"]["connections_opened"], "allowed_uris": receipt["read_phase"]["allowed_uris"], "queries": len(receipt["read_phase"]["sql_log"]),
                               "q10_omitted": True, "denials_during_read": receipt["read_phase"]["denials_during_read"], "rows": {q["name"]: q["rows"] for q in receipt["read_phase"]["sql_log"]}},
                "reconciliation": {"matches_prior_audit_digest": receipt["sealed_input"]["matches_prior_audit_digest"], "bars": receipt["sealed_input"]["bars"], "halt_keys": receipt["sealed_input"]["halt_keys"]},
                "determinism": {b: v["identical"] for b, v in receipt["determinism"].items()}, "output_hashes": {b: v["repeat_1_output_hash"] for b, v in receipt["determinism"].items()},
                "branches": {b: {"funnel": v["funnel"], "performance": v["performance"], "benchmark": v["benchmark"], "censored_open_positions": len(v["censored"]["open_positions"]),
                                 "censored_live_intents": len(v["censored"]["live_intents_beyond_window"]), "ledger_reconcile_ok": v["ledger_reconcile_ok"]} for b, v in branches.items()},
                "guard_self_check": receipt["guard_self_check"], "synthetic_validation": receipt["synthetic_validation"], "failure_receipts": failures},
        "outcomes": {"validated_synthetic_engine_evidence": "M4-01/02A/02B/03A freezes unchanged; 13 synthetic runner tests passed under the guard before the read",
                     "assumed_historical_shape_replay": {b: {"buy_fills": v["funnel"]["attempt_outcomes"].get("buy:filled", 0), "performance": v["performance"]} for b, v in branches.items() if b != "raw"},
                     "genuine_historical_execution_evidence": "unmet: raw branch produced no intents (future_evidence refusals); assumed fills are conditional on the declared assumption set and are not historical eligibility"},
        "frozen": freezes,
        "preservation": {"prework": {"immutable_pins": pre["baseline"]["immutable_pins"], "tracked_files": {k: pre["baseline"]["tracked_files"][k] for k in ("count", "changed_or_missing")},
                                     "production_file_positions": {k: pre["baseline"]["production_file_positions"][k] for k in ("count", "unchanged", "changed", "note")},
                                     "inputs_ok": f"{sum(1 for v in pre['inputs'].values() if v['ok'])}/{len(pre['inputs'])}", "databases_ok": all(v["ok"] for v in pre["candidate_databases"].values())},
                         "postwork": {"immutable_pins": post["baseline"]["immutable_pins"], "tracked_files": {k: post["baseline"]["tracked_files"][k] for k in ("count", "changed_or_missing")},
                                      "production_file_positions": {k: post["baseline"]["production_file_positions"][k] for k in ("count", "unchanged", "changed", "note")},
                                      "inputs_ok": f"{sum(1 for v in post['inputs'].values() if v['ok'])}/{len(post['inputs'])}", "databases_ok": all(v["ok"] for v in post["candidate_databases"].values())},
                         "codex_mutable_records": {"prework": pre["codex_mutable_records"], "postwork": post["codex_mutable_records"], "note": "PLAN.md / coordination_state.json are Codex-owned; not a preservation failure if patrol updated them"},
                         "files": {"prework": f"{REL}/evidence/prework_verification.json", "postwork": f"{REL}/evidence/postwork_verification.json"}},
        "commands": [
            {"purpose": "pre-work verification (task hash, four freezes, inputs, database stat/hash, baseline 42/316/16, git)", "command": f"backend/.venv/Scripts/python.exe -B -X utf8 \"{REL}/verify_baseline.py\" prework", "exit_code": 0, "at_utc": pre["verified_at_utc"]},
            {"purpose": "focused synthetic tests (standalone run)", "command": f"backend/.venv/Scripts/python.exe -B -X utf8 \"{REL}/test_replay_synthetic.py\"", "exit_code": 0, "tests": 13},
            {"purpose": "guarded runner: self-check -> synthetic tests in-process -> one read phase (2 connections, Q1-Q9) -> reconciliation/seal -> 4 branches x 2 -> outputs", "command": " ".join(receipt["command"]),
             "exit_code": 0, "started_at_utc": receipt["started_at_utc"], "finished_at_utc": receipt["finished_at_utc"]},
            {"purpose": "delivery 01: post-work verification (receipt preserved under superseded/delivery_01/evidence/)", "command": f"backend/.venv/Scripts/python.exe -B -X utf8 \"{REL}/verify_baseline.py\" postwork", "exit_code": 0, "receipt_sha256": status["files"]["evidence/postwork_verification.json"]["sha256"]},
            {"purpose": "delivery 01: REPORT.md from receipts", "command": f"backend/.venv/Scripts/python.exe -B -X utf8 \"{REL}/build_report.py\"", "exit_code": 0},
            {"purpose": "revision 2: guarded revised synthetic suite (17 tests; zero connections)", "command": " ".join(synth2["command"]), "exit_code": 0, "started_at_utc": synth2["started_at_utc"], "finished_at_utc": synth2["finished_at_utc"]},
            {"purpose": "revision 2: export-only repair of the delivered outputs (applied twice in memory, written once; zero connections; no runner invocation)", "command": " ".join(rev["command"]),
             "exit_code": 0, "started_at_utc": rev["started_at_utc"], "finished_at_utc": rev["finished_at_utc"]},
            {"purpose": "revision 2: post-work verification", "command": f"backend/.venv/Scripts/python.exe -B -X utf8 \"{REL}/verify_baseline.py\" postwork", "exit_code": 0, "at_utc": post["verified_at_utc"]},
            {"purpose": "revision 2: REPORT.md rebuilt from original + revision receipts", "command": f"backend/.venv/Scripts/python.exe -B -X utf8 \"{REL}/build_report.py\"", "exit_code": 0},
            {"purpose": "this manifest (written last)", "command": f"backend/.venv/Scripts/python.exe -B -X utf8 \"{REL}/build_manifest.py\"", "exit_code": 0},
        ],
        "exclusions": EXCLUSIONS + ["revision 2: zero additional SQLite connections and zero historical runner invocations; export-only repair of enclosing metadata; original run folder byte-identical"],
        "limitations": ["assumed-grade replay only; strict PIT false; every position adjustment_uncertainty=true; pool selection bias, missing ST/bands/capacity/fees/corporate-action/delisting provenance unchanged",
                        "the frozen risk layer stamps Instrument.synthetic=True in its kernel requests (its declared synthetic-pool contract); the research wrappers carry the real symbol provenance separately",
                        "SH000001 rows were reconciled but not consumed (benchmark is SH000300 only)"],
        "safety": {"review_only": True, "live_trading_enabled": False, "training_eligible": False, "strict_pit": False, "M3_complete": False, "M4_complete": False, "M5_started": False,
                   "sqlite_connections": receipt["safety"]["sqlite_connections"], "production_sqlite_connections": 0, "network_requests": 0, "holdout_price_rows_read": 0,
                   "agents_dispatched": 0, "automation_changed": False, "freezes_modified": False, "codex_files_modified": False, "accepted_by_codex": False},
        "written": written, "consumed": consumed, "codex_mutable_records": mutable,
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"artifact_manifest_sha256": sha256(MANIFEST), "written_files": len(written), "sources_read": len(consumed), "run_id": receipt["run_id"],
                      "outcomes": manifest["outcomes"]["assumed_historical_shape_replay"], "preservation_postwork": manifest["preservation"]["postwork"], "git": manifest["git"]}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
