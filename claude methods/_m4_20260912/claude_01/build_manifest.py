"""Write execution_policy.json, run the before/after preservation check and write artifact_manifest.json LAST.

Path-root convention used everywhere in the outputs: paths are relative to the project root
``D:\\codex-A股交易`` with forward slashes (the baseline files written by Codex use backslashes
and absolute Windows paths; they are normalized before comparison).  Read-only git commands
(``git status --porcelain``, ``git diff --stat``) are the only subprocesses; nothing is staged.

    backend/.venv/Scripts/python.exe -B -X utf8 "claude methods/_m4_20260912/claude_01/build_manifest.py"
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[2]
M4 = HERE.parent
TASK_ID = "M4-01-EXECUTION-CONTRACT-20260912"
MODULE_REL = "backend/app/research/m4_execution.py"
TESTS_REL = "backend/tests/test_m4_execution.py"
CLAUDE_01_REL = "claude methods/_m4_20260912/claude_01"
MANIFEST = HERE / "artifact_manifest.json"
POLICY_FILE = HERE / "execution_policy.json"
PRESERVATION_FILE = HERE / "evidence" / "preservation_check.json"

CONSUMED_SOURCES = [
    "claude methods/M4_01_EXECUTION_CONTRACT_CLAUDE_TASK_20260912.md",
    "claude methods/_m4_20260912/PLAN.md",
    "claude methods/_m4_20260912/coordination_state.json",
    "claude methods/_m4_20260912/codex/INITIAL_STATIC_FINDINGS.md",
    "claude methods/_m4_20260912/baseline/start.json",
    "claude methods/_m4_20260912/baseline/immutable_pins.json",
    "claude methods/_m4_20260912/baseline/tracked_files_before.json",
    "claude methods/_m4_20260912/baseline/production_files_before.json",
    "claude methods/_m4_20260912/baseline/git_status_before.txt",
    "claude methods/_m4_20260912/baseline/git_exclude_before.txt",
    "claude methods/_m4_20260912/baseline/automation_before.json",
    "claude methods/THREE_YEAR_RESEARCH_EXECUTION_GOAL.md",
    "claude methods/M3_FINAL_ACCEPTANCE_20260910.md",
    "claude methods/_m3_20260910/codex/final_acceptance_01/completion.json",
    "AGENTS.md",
    "CODEX_CLAUDE_COLLABORATION.md",
    "CLAUDE.md",
    "backend/app/backtest/engine.py",
    "backend/app/backtest/execution.py",
    "backend/app/backtest/ledger.py",
    "backend/tests/test_backtest_engine.py",
    "backend/tests/conftest.py",
    "backend/app/config.py",
    "backend/app/data/price_limits.py",
    "backend/app/research/m3_labels.py",
    "backend/app/__init__.py",
    "backend/app/research/__init__.py",
    "claude methods/_m4_20260912/codex/M4_01_WORKING_REVIEW_01.md",
    "claude methods/_m4_20260912/codex/probe_m4_working_01.py",
    "claude methods/_m4_20260912/codex/working_review_01/results.json",
    "claude methods/_m4_20260912/codex/working_review_01/m4_execution_snapshot.py",
]
EXPECTED_NEW_UNTRACKED = {MODULE_REL, TESTS_REL}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def rel(path: Path) -> str:
    return path.resolve().relative_to(PROJECT).as_posix()


def norm(path_text: str) -> str:
    p = Path(path_text)
    if p.is_absolute():
        try:
            return p.resolve().relative_to(PROJECT).as_posix()
        except ValueError:
            return p.as_posix()
    return path_text.replace("\\", "/")


def load_kernel():
    spec = importlib.util.spec_from_file_location("m4_execution_manifest_readonly", PROJECT / MODULE_REL)
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


def write_policy(m) -> None:
    policy = {
        "schema": "m4.claude_01.execution_policy.v1",
        "task_id": TASK_ID,
        "contract_version": m.CONTRACT_VERSION,
        "policy_hash": m.POLICY_HASH,
        "module": {"path": MODULE_REL, "sha256": sha256(PROJECT / MODULE_REL), "bytes": (PROJECT / MODULE_REL).stat().st_size},
        "tests": {"path": TESTS_REL, "sha256": sha256(PROJECT / TESTS_REL), "bytes": (PROJECT / TESTS_REL).stat().st_size},
        "status": "proposed_pending_codex_review",
        "frozen": False,
        "freeze_rule": "Freeze by delivered file hashes and policy_hash only after Codex's independent review; the implementer does not self-accept.",
        "review_only": True, "live_trading_enabled": False, "synthetic_fixtures_only": True, "real_tariffs_encoded": False,
        "policy": m.POLICY,
        "reject_codes": list(m.REJECT_CODES), "unfilled_codes": list(m.UNFILLED_CODES), "statuses": list(m.STATUSES),
        "written_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    POLICY_FILE.write_text(json.dumps(policy, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def git(*args: str) -> str:
    out = subprocess.run(["git", *args], cwd=PROJECT, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    return out.stdout


def preservation_check() -> dict:
    baseline = M4 / "baseline"
    pins = json.loads((baseline / "immutable_pins.json").read_text(encoding="utf-8"))
    tracked = json.loads((baseline / "tracked_files_before.json").read_text(encoding="utf-8"))
    production = json.loads((baseline / "production_files_before.json").read_text(encoding="utf-8"))
    status_before = (baseline / "git_status_before.txt").read_text(encoding="utf-8").splitlines()

    pin_results = {}
    for raw, expected in pins.items():   # raw keys kept: the baseline lists policy_freeze.json twice (two path spellings)
        p = PROJECT / norm(raw)
        actual = sha256(p) if p.is_file() else None
        pin_results[raw] = {"path": norm(raw), "expected": expected, "actual": actual, "unchanged": actual == expected}
    tracked_results = {"count": len(tracked), "unchanged": 0, "changed": [], "missing": []}
    for raw, expected in tracked.items():
        p = PROJECT / norm(raw)
        if not p.is_file():
            tracked_results["missing"].append(norm(raw))
            continue
        if sha256(p) == expected:
            tracked_results["unchanged"] += 1
        else:
            tracked_results["changed"].append(norm(raw))
    production_results = {}
    for raw, before in production.items():
        p = Path(raw)
        now = {"exists": p.exists()}
        if p.exists():
            st = p.stat()
            now.update({"size": st.st_size, "mtime_ns": st.st_mtime_ns, "sha256": sha256(p)})
        same = now.get("exists") == before.get("exists") and all(now.get(k) == before.get(k) for k in ("size", "mtime_ns", "sha256") if k in before)
        production_results[norm(raw)] = {"before": before, "after": now, "unchanged": same}

    status_after = git("status", "--porcelain").splitlines()
    modified_after = sorted(line for line in status_after if not line.startswith("?? "))
    modified_before = sorted(line for line in status_before if not line.startswith("?? "))
    # untracked files classified by modification time against the M4 baseline start (Codex's start.json)
    started = datetime.fromisoformat(json.loads((baseline / "start.json").read_text(encoding="utf-8"))["started_at_utc"])
    untracked = [x for x in git("ls-files", "--others", "--exclude-standard", "-z").split("\0") if x]
    classes = {"in_scope_written_by_this_task": [], "codex_owned_m4": [], "ide_state_dot_vs": [], "pre_existing": [], "unexpected_new": []}
    for path in untracked:
        fp = PROJECT / path
        if not fp.is_file():
            continue
        is_new = datetime.fromtimestamp(fp.stat().st_mtime, tz=timezone.utc) >= started
        if path in EXPECTED_NEW_UNTRACKED or path.startswith(CLAUDE_01_REL + "/"):
            classes["in_scope_written_by_this_task"].append(path)
        elif path.startswith("claude methods/_m4_20260912/"):
            classes["codex_owned_m4"].append(path)
        elif path.startswith(".vs/"):
            classes["ide_state_dot_vs"].append(path)
        elif is_new:
            classes["unexpected_new"].append(path)
        else:
            classes["pre_existing"].append(path)
    added_untracked = sorted(classes["in_scope_written_by_this_task"])
    return {
        "schema": "m4.claude_01.preservation_check.v1",
        "task_id": TASK_ID,
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "baseline_files": {rel(baseline / n): sha256(baseline / n) for n in ("immutable_pins.json", "tracked_files_before.json", "production_files_before.json", "git_status_before.txt", "start.json")},
        "immutable_pins": {"count": len(pin_results), "distinct_paths": len({v["path"] for v in pin_results.values()}),
                           "unchanged": sum(1 for v in pin_results.values() if v["unchanged"]),
                           "changed": [k for k, v in pin_results.items() if not v["unchanged"]], "detail": pin_results},
        "tracked_files": tracked_results,
        "production_file_positions": {"count": len(production_results), "unchanged": sum(1 for v in production_results.values() if v["unchanged"]),
                                      "changed": [k for k, v in production_results.items() if not v["unchanged"]], "detail": production_results,
                                      "note": "byte hashing only; no SQLite connection was opened; WAL/SHM files belong to processes outside this task"},
        "git": {"modified_or_staged_same_as_baseline": modified_after == modified_before,
                "modified_before_count": len(modified_before), "modified_after_count": len(modified_after),
                "baseline_start_utc": started.isoformat(), "untracked_files_total": len(untracked),
                "untracked_classes": {k: (v if k != "pre_existing" else len(v)) for k, v in classes.items()},
                "new_untracked_written_by_this_task": added_untracked,
                "unexpected_new_untracked": sorted(classes["unexpected_new"]),
                "diff_stat_tracked": git("diff", "--stat").strip().splitlines()[-1:] , "staged": git("diff", "--cached", "--name-only").strip().splitlines(),
                "note": "'claude methods/' is untracked as a whole (baseline shows the same); local exclude rules were not edited by this task"},
    }


def main() -> int:
    m = load_kernel()
    write_policy(m)
    (HERE / "evidence").mkdir(exist_ok=True)
    preservation = preservation_check()
    PRESERVATION_FILE.write_text(json.dumps(preservation, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    receipt = json.loads((HERE / "evidence" / "execution_receipt.json").read_text(encoding="utf-8"))
    if receipt["exit_code"] != 0 or not receipt["tests"]["successful"]:
        raise SystemExit("execution receipt is not clean; manifest not written")
    for relp in (MODULE_REL, TESTS_REL):
        if receipt["files"][relp]["sha256"] != sha256(PROJECT / relp):
            raise SystemExit(f"{relp} changed after the recorded test run; re-run run_m4_tests.py first")
    replay = json.loads((HERE / "evidence" / "codex_probe_replay_01.json").read_text(encoding="utf-8"))
    if replay["current_source_sha256"] != sha256(PROJECT / MODULE_REL) or replay["summary"]["expectation_met_now"] != replay["summary"]["checks"]:
        raise SystemExit("codex probe replay is stale or not fully met; re-run replay_codex_probe_01.py")
    delivery_01 = json.loads((HERE / "superseded" / "delivery_01" / "DELIVERY_STATUS.json").read_text(encoding="utf-8"))
    for relp, meta in delivery_01["files"].items():
        if sha256(HERE / "superseded" / "delivery_01" / relp) != meta["sha256"]:
            raise SystemExit(f"superseded delivery_01 file changed: {relp}")

    written = {}
    for p in sorted(HERE.rglob("*")):
        if p.is_file() and p != MANIFEST and "__pycache__" not in p.parts:
            written[rel(p)] = {"sha256": sha256(p), "bytes": p.stat().st_size}
    for relp in (MODULE_REL, TESTS_REL):
        written[relp] = {"sha256": sha256(PROJECT / relp), "bytes": (PROJECT / relp).stat().st_size}
    consumed = {}
    for relp in CONSUMED_SOURCES:
        p = PROJECT / relp
        consumed[relp] = {"sha256": sha256(p), "bytes": p.stat().st_size}

    manifest = {
        "schema": "m4.claude_01.artifact_manifest.v1",
        "task_id": TASK_ID,
        "task_file_sha256": consumed["claude methods/M4_01_EXECUTION_CONTRACT_CLAUDE_TASK_20260912.md"]["sha256"],
        "status": "ready_for_review",
        "owner": "Claude (existing ZK-trading / Fable 5.1 project advice fork session a4a3be61-cd46-4bdf-9381-23d97fee303a)",
        "built_at_utc": datetime.now(timezone.utc).isoformat(),
        "path_root_convention": "relative to project root D:\\codex-A股交易, forward slashes; baseline files by Codex use absolute/backslash paths and were normalized for comparison",
        "contract": {"version": m.CONTRACT_VERSION, "policy_hash": m.POLICY_HASH, "frozen": False, "status": "proposed_pending_codex_review",
                     "execution_policy_file": f"{CLAUDE_01_REL}/execution_policy.json"},
        "code": {MODULE_REL: written[MODULE_REL], TESTS_REL: written[TESTS_REL]},
        "delivery": {"version": "delivery_02", "supersedes": "delivery_01", "trigger": "claude methods/_m4_20260912/codex/M4_01_WORKING_REVIEW_01.md",
                     "trigger_sha256": consumed["claude methods/_m4_20260912/codex/M4_01_WORKING_REVIEW_01.md"]["sha256"],
                     "correction_matrix": f"{CLAUDE_01_REL}/CORRECTION_MATRIX.md",
                     "superseded_delivery_01": {"path": f"{CLAUDE_01_REL}/superseded/delivery_01/", "status_file_sha256": sha256(HERE / "superseded" / "delivery_01" / "DELIVERY_STATUS.json"),
                                                "module_sha256": delivery_01["first_delivery_module_sha256"], "tests_sha256": delivery_01["first_delivery_tests_sha256"],
                                                "manifest_sha256": delivery_01["first_delivery_manifest_sha256"], "files": len(delivery_01["files"])},
                     "codex_probe_replay": {"file": f"{CLAUDE_01_REL}/evidence/codex_probe_replay_01.json", "checks": replay["summary"]["checks"],
                                            "expectation_met_now": replay["summary"]["expectation_met_now"],
                                            "expectation_met_on_first_delivery": replay["summary"]["expectation_met_on_first_delivery"],
                                            "frozen_results_sha256": replay["frozen_results_sha256"], "codex_files_modified": False}},
        "test_execution": {"receipt": f"{CLAUDE_01_REL}/evidence/execution_receipt.json", "command": receipt["command"],
                           "started_at_utc": receipt["started_at_utc"], "finished_at_utc": receipt["finished_at_utc"], "exit_code": receipt["exit_code"],
                           "tests_run": receipt["tests"]["run"], "failures": receipt["tests"]["failures"], "errors": receipt["tests"]["errors"],
                           "recorded_cases": receipt["recorded_cases"], "guards": {"self_check": receipt["guards"]["self_check"],
                           "denials_during_tests": receipt["guards"]["denial_count_during_tests"]}, "isolation": receipt["isolation"]},
        "preservation": {"file": f"{CLAUDE_01_REL}/evidence/preservation_check.json",
                         "immutable_pins_unchanged": f"{preservation['immutable_pins']['unchanged']}/{preservation['immutable_pins']['count']}",
                         "tracked_files_unchanged": f"{preservation['tracked_files']['unchanged']}/{preservation['tracked_files']['count']}",
                         "tracked_changed": preservation["tracked_files"]["changed"], "tracked_missing": preservation["tracked_files"]["missing"],
                         "production_positions_unchanged": f"{preservation['production_file_positions']['unchanged']}/{preservation['production_file_positions']['count']}",
                         "production_changed": preservation["production_file_positions"]["changed"],
                         "git_modified_set_same_as_baseline": preservation["git"]["modified_or_staged_same_as_baseline"],
                         "new_untracked_written_by_this_task": preservation["git"]["new_untracked_written_by_this_task"],
                         "untracked_classes": {k: (v if isinstance(v, int) else len(v)) for k, v in preservation["git"]["untracked_classes"].items()},
                         "unexpected_new_untracked": preservation["git"]["unexpected_new_untracked"], "staged": preservation["git"]["staged"]},
        "written": written,
        "sources_read": consumed,
        "m3_state_preserved": {"M3_complete": False, "dual_positive": 0, "strict_pit": False, "training_eligible": False, "modified": False},
        "safety": {"review_only": True, "live_trading_enabled": False, "sqlite_connections": 0, "network_requests": 0, "subprocesses_in_tests": 0,
                   "legacy_engine_instantiated": False, "legacy_tests_run": False, "settings_imported": False, "market_capture": False,
                   "accounts_or_credentials": False, "training": False, "M2_M3_files_modified": False, "git_staged_or_committed": False,
                   "agents_or_workflows_dispatched": 0, "real_data_adapter": False, "historical_price_extraction": False, "codex_files_modified": False,
                   "hypothetical_fee_schedules_only": True, "accepted_by_codex": False, "M4_complete": False, "M4_02_started": False},
        "remaining_requirements": {
            "M4-02_portfolio": ["allocation / maximum exposure valued with prices observed at or before the decision instant",
                                "stop-loss / exit priority and partial take-profit ordering", "cooldown counted in exchange sessions",
                                "FIFO lots, realized PnL and independent cash reconciliation from ledger_entry",
                                "multi-order sequencing within a session via capacity consumed_quantity",
                                "benchmark series and delisted securities without survivorship leakage",
                                "hand-calculated non-zero controlled baseline and time-suffix invariance at portfolio level",
                                "freeze of this execution contract after Codex review"],
            "M4-03_historical_evidence": ["static qualification of frozen development data for execution validation",
                                          "adapter exposing contemporaneous vs predeclared_assumption per field with assumption_ref",
                                          "unknown ST / adjustment / capacity remain unknown unless evidenced",
                                          "separate reporting of synthetic proof, assumption-based replay and real execution evidence",
                                          "sources, exclusions and reasons for zero or unprovable baselines; no selection, hold-out consumption or universe widening"],
            "final_M4_acceptance": "each of the six original M4 acceptance items stated with scope, tests and historical evidence; unproven items are not marked passed",
        },
        "next": "Codex independent review of the kernel, tests, contract and gap analysis; no self-acceptance; M4-02 only on a new task file.",
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"artifact_manifest_sha256": sha256(MANIFEST), "written_files": len(written), "sources_read": len(consumed),
                      "policy_hash": m.POLICY_HASH, "preservation": manifest["preservation"], "status": manifest["status"]}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
