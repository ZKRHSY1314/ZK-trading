"""Write claude_02a/artifact_manifest.json LAST for M4-02A (after the post-work verification).

Path-root convention: paths relative to the project root D:\\codex-A股交易 with forward slashes.  Pins every file
written under claude_02a/ plus the two new code files, and every consumed source (task file, freeze, acceptance,
frozen kernel/tests, M4-01 contract/matrix, Codex integration snapshots inspected, plan/coordination/baseline,
collaboration rules).  Records the actual commands/exit codes from the receipts and the preservation results.
The manifest does not contain its own hash.

    backend/.venv/Scripts/python.exe -B -X utf8 "claude methods/_m4_20260912/claude_02a/build_manifest.py"
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[2]
REL = "claude methods/_m4_20260912/claude_02a"
TASK_ID = "M4-02A-PORTFOLIO-LEDGER-20260912"
LEDGER_REL = "backend/app/research/m4_portfolio.py"
TESTS_REL = "backend/tests/test_m4_portfolio.py"
MANIFEST = HERE / "artifact_manifest.json"
CONSUMED = [
    "claude methods/M4_02A_PORTFOLIO_LEDGER_CLAUDE_TASK_20260912.md",
    "claude methods/M4_01_CODEX_ACCEPTANCE_20260912.md",
    "claude methods/_m4_20260912/execution_freeze.json",
    "claude methods/_m4_20260912/PLAN.md",
    "claude methods/_m4_20260912/coordination_state.json",
    "claude methods/_m4_20260912/baseline/start.json",
    "claude methods/_m4_20260912/baseline/immutable_pins.json",
    "claude methods/_m4_20260912/baseline/tracked_files_before.json",
    "claude methods/_m4_20260912/baseline/production_files_before.json",
    "claude methods/_m4_20260912/claude_01/CONTRACT.md",
    "claude methods/_m4_20260912/claude_01/CORRECTION_MATRIX.md",
    "claude methods/_m4_20260912/codex/acceptance_review_01/claude_delivery_02_m4_execution.py",
    "claude methods/_m4_20260912/codex/acceptance_review_01/claude_delivery_02_test_m4_execution.py",
    "claude methods/_m4_20260912/codex/acceptance_review_01/final_m4_execution.py",
    "claude methods/_m4_20260912/codex/acceptance_review_01/final_test_m4_execution.py",
    "backend/app/research/m4_execution.py",
    "backend/tests/test_m4_execution.py",
    "AGENTS.md",
    "CODEX_CLAUDE_COLLABORATION.md",
    "CLAUDE.md",
    "claude methods/_m4_20260912/codex/M4_02A_REVIEW_01.md",
    "claude methods/_m4_20260912/codex/probe_portfolio_01.py",
    "claude methods/_m4_20260912/codex/portfolio_review_01/results.json",
    "claude methods/_m4_20260912/codex/portfolio_review_01/m4_portfolio.py",
    "claude methods/_m4_20260912/codex/portfolio_review_01/m4_execution.py",
    "claude methods/_m4_20260912/codex/M4_02A_REVIEW_02.md",
    "claude methods/_m4_20260912/codex/probe_portfolio_02.py",
    "claude methods/_m4_20260912/codex/probe_portfolio_calendar_02.py",
    "claude methods/_m4_20260912/codex/portfolio_review_02/calendar_binding_results.json",
    "claude methods/_m4_20260912/codex/portfolio_review_02/results.json",
    "claude methods/_m4_20260912/codex/portfolio_review_02/m4_portfolio.py",
]
EXCLUSIONS = ["no SQLite connection or SQL query (production/market databases only stat/byte-hashed by the verification script)",
              "no network, client, account, credential, order or screen access", "no other agents or workflows",
              "no edits to M4-01 code/tests/claude_01, M2/M3 artifacts, Codex files, package initializers, configuration or legacy backtest",
              "no git staging/commit/push; the pre-existing modified set was left as found", "no M4-02B strategy/risk logic, M4-03 historical reading, M5 or training"]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def rel(path: Path) -> str:
    return path.resolve().relative_to(PROJECT).as_posix()


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


def main() -> int:
    pre = json.loads((HERE / "evidence" / "prework_verification.json").read_text(encoding="utf-8"))
    post = json.loads((HERE / "evidence" / "postwork_verification.json").read_text(encoding="utf-8"))
    receipt = json.loads((HERE / "evidence" / "execution_receipt.json").read_text(encoding="utf-8"))
    kernel_rerun = json.loads((HERE / "evidence" / "kernel_suite_rerun_receipt.json").read_text(encoding="utf-8"))
    if not (pre["ok"] and post["ok"]):
        raise SystemExit("verification not clean")
    if receipt["exit_code"] != 0 or kernel_rerun["exit_code"] != 0:
        raise SystemExit("test receipts not clean")
    for relp in (LEDGER_REL, TESTS_REL):
        if receipt["files"][relp]["sha256_after"] != sha256(PROJECT / relp):
            raise SystemExit(f"{relp} changed after the recorded run")
    replay = json.loads((HERE / "evidence" / "codex_probe_portfolio_replay_01.json").read_text(encoding="utf-8"))
    if replay["current_source_hashes"][LEDGER_REL] != sha256(PROJECT / LEDGER_REL) or replay["summary"]["passed_now"] != replay["summary"]["checks"]:
        raise SystemExit("codex probe replay stale or failing; re-run replay_codex_probe_portfolio_01.py")
    replay2 = json.loads((HERE / "evidence" / "codex_probe_calendar_replay_02.json").read_text(encoding="utf-8"))
    if replay2["current_source_hashes"][LEDGER_REL] != sha256(PROJECT / LEDGER_REL) or replay2["summary"]["passed_now"] != replay2["summary"]["checks"]:
        raise SystemExit("codex calendar replay stale or failing; re-run replay_codex_probe_calendar_02.py")
    superseded = {}
    for name in ("delivery_01", "delivery_02"):
        status = json.loads((HERE / "superseded" / name / "DELIVERY_STATUS.json").read_text(encoding="utf-8"))
        for relp, meta in status["files"].items():
            if sha256(HERE / "superseded" / name / relp) != meta["sha256"]:
                raise SystemExit(f"superseded {name} file changed: {relp}")
        superseded[name] = status
    delivery_01 = superseded["delivery_01"]
    kernel = load("m4_execution_manifest_readonly", PROJECT / "backend/app/research/m4_execution.py")
    ledger = load("m4_portfolio_manifest_readonly", PROJECT / LEDGER_REL)
    written = {}
    for p in sorted(HERE.rglob("*")):
        if p.is_file() and p != MANIFEST and "__pycache__" not in p.parts:
            written[rel(p)] = {"sha256": sha256(p), "bytes": p.stat().st_size}
    for relp in (LEDGER_REL, TESTS_REL):
        written[relp] = {"sha256": sha256(PROJECT / relp), "bytes": (PROJECT / relp).stat().st_size}
    consumed = {relp: {"sha256": sha256(PROJECT / relp), "bytes": (PROJECT / relp).stat().st_size} for relp in CONSUMED}
    manifest = {
        "schema": "m4.claude_02a.artifact_manifest.v1",
        "task_id": TASK_ID,
        "task_file_sha256": consumed["claude methods/M4_02A_PORTFOLIO_LEDGER_CLAUDE_TASK_20260912.md"]["sha256"],
        "status": "ready_for_review",
        "owner": "Claude (existing ZK-trading / Fable 5.1 project advice fork session a4a3be61-cd46-4bdf-9381-23d97fee303a)",
        "built_at_utc": datetime.now(timezone.utc).isoformat(),
        "path_root_convention": "relative to project root D:\\codex-A股交易, forward slashes",
        "git": {"branch": post["git"]["branch"], "head": post["git"]["head"], "modified_count_before": len(pre["git"]["status_modified"]),
                "modified_count_after": len(post["git"]["status_modified"]), "modified_set_unchanged": pre["git"]["status_modified"] == post["git"]["status_modified"],
                "staged": post["git"]["staged"]},
        "frozen_kernel": {"path": "backend/app/research/m4_execution.py", "sha256": consumed["backend/app/research/m4_execution.py"]["sha256"],
                          "expected": "83a28b543b9ecc5edf8080ea39fa388f8b2bb5a8724ef68b4b532041216678c7", "policy_hash": kernel.POLICY_HASH,
                          "tests_sha256": consumed["backend/tests/test_m4_execution.py"]["sha256"], "integration_revision": "M4-01-codex-integration-1",
                          "codex_integration_fix_inspected": True, "material_concern": None, "modified": False},
        "ledger": {"path": LEDGER_REL, "sha256": written[LEDGER_REL]["sha256"], "contract_version": ledger.LEDGER_CONTRACT_VERSION, "policy_hash": ledger.LEDGER_POLICY_HASH,
                   "tests": TESTS_REL, "tests_sha256": written[TESTS_REL]["sha256"]},
        "delivery": {"version": "delivery_03", "supersedes": ["delivery_01", "delivery_02"],
                     "triggers": [{"review": "claude methods/_m4_20260912/codex/M4_02A_REVIEW_01.md", "sha256": consumed["claude methods/_m4_20260912/codex/M4_02A_REVIEW_01.md"]["sha256"]},
                                  {"review": "claude methods/_m4_20260912/codex/M4_02A_REVIEW_02.md", "sha256": consumed["claude methods/_m4_20260912/codex/M4_02A_REVIEW_02.md"]["sha256"]}],
                     "correction_matrix": f"{REL}/CORRECTION_MATRIX.md",
                     "superseded_delivery_01": {"path": f"{REL}/superseded/delivery_01/", "status_file_sha256": sha256(HERE / "superseded" / "delivery_01" / "DELIVERY_STATUS.json"),
                                                "ledger_sha256": delivery_01["first_delivery_ledger_sha256"], "tests_sha256": delivery_01["first_delivery_tests_sha256"],
                                                "manifest_sha256": delivery_01["first_delivery_manifest_sha256"], "files": len(delivery_01["files"])},
                     "superseded_delivery_02": {"path": f"{REL}/superseded/delivery_02/", "status_file_sha256": sha256(HERE / "superseded" / "delivery_02" / "DELIVERY_STATUS.json"),
                                                "ledger_sha256": superseded["delivery_02"]["delivery_02_ledger_sha256"], "tests_sha256": superseded["delivery_02"]["delivery_02_tests_sha256"],
                                                "manifest_sha256": superseded["delivery_02"]["delivery_02_manifest_sha256"], "files": len(superseded["delivery_02"]["files"])},
                     "codex_probe_replays": [{"file": f"{REL}/evidence/codex_probe_portfolio_replay_01.json", "checks": replay["summary"]["checks"],
                                              "passed_now": replay["summary"]["passed_now"], "passed_on_first_delivery": replay["summary"]["passed_on_first_delivery"],
                                              "frozen_results_sha256": replay["frozen_results_sha256"]},
                                             {"file": f"{REL}/evidence/codex_probe_calendar_replay_02.json", "checks": replay2["summary"]["checks"],
                                              "passed_now": replay2["summary"]["passed_now"], "passed_on_delivery_02": replay2["summary"]["passed_on_delivery_02"],
                                              "frozen_results_sha256": replay2["frozen_results_sha256"]}],
                     "codex_files_modified": False},
        "commands": [
            {"purpose": "pre-work verification", "command": f"backend/.venv/Scripts/python.exe -B -X utf8 \"{REL}/verify_pins.py\" prework", "exit_code": 0 if pre["ok"] else 1,
             "at_utc": pre["verified_at_utc"]},
            {"purpose": "codex probe replay (review 01: 5 checks, verbatim fixtures)", "command": f"backend/.venv/Scripts/python.exe -B -X utf8 \"{REL}/replay_codex_probe_portfolio_01.py\"",
             "exit_code": 0 if replay["summary"]["passed_now"] == replay["summary"]["checks"] else 1, "at_utc": replay["observed_at_utc"]},
            {"purpose": "codex probe replay (review 02: 2 calendar checks, verbatim fixtures)", "command": f"backend/.venv/Scripts/python.exe -B -X utf8 \"{REL}/replay_codex_probe_calendar_02.py\"",
             "exit_code": 0 if replay2["summary"]["passed_now"] == replay2["summary"]["checks"] else 1, "at_utc": replay2["observed_at_utc"]},
            {"purpose": "ledger suite (guarded, final code, run once)", "command": " ".join(receipt["command"]), "exit_code": receipt["exit_code"],
             "started_at_utc": receipt["started_at_utc"], "finished_at_utc": receipt["finished_at_utc"], "tests": {k: v for k, v in receipt["tests"].items() if k != "names"}},
            {"purpose": "frozen kernel suite read-only rerun (guarded)", "command": " ".join(kernel_rerun["command"]), "exit_code": kernel_rerun["exit_code"],
             "started_at_utc": kernel_rerun["started_at_utc"], "finished_at_utc": kernel_rerun["finished_at_utc"], "tests": {k: v for k, v in kernel_rerun["tests"].items() if k != "names"}},
            {"purpose": "post-work verification", "command": f"backend/.venv/Scripts/python.exe -B -X utf8 \"{REL}/verify_pins.py\" postwork", "exit_code": 0 if post["ok"] else 1,
             "at_utc": post["verified_at_utc"]},
        ],
        "tests_actually_run": {"ledger_suite": receipt["tests"]["run"], "ledger_failures": receipt["tests"]["failures"], "ledger_errors": receipt["tests"]["errors"],
                               "kernel_suite_rerun": kernel_rerun["tests"]["run"], "kernel_failures": kernel_rerun["tests"]["failures"],
                               "focused_development_runs": "several direct unittest runs of the same file during development, not recorded as evidence",
                               "guards": receipt["guards"]["self_check"], "guard_denials_during_tests": receipt["guards"]["denial_count_during_tests"],
                               "isolation": receipt["isolation"]},
        "preservation": {"prework": {"freeze_pins": f"{pre['execution_freeze']['pins_ok']}/{pre['execution_freeze']['pins_total']}",
                                     "immutable_pins": pre["baseline"]["immutable_pins"], "tracked_changed": pre["baseline"]["tracked_files"]["changed_or_missing"],
                                     "production_unchanged": f"{pre['baseline']['production_file_positions']['unchanged']}/{pre['baseline']['production_file_positions']['count']}"},
                         "postwork": {"freeze_pins": f"{post['execution_freeze']['pins_ok']}/{post['execution_freeze']['pins_total']}",
                                      "immutable_pins": post["baseline"]["immutable_pins"], "tracked_changed": post["baseline"]["tracked_files"]["changed_or_missing"],
                                      "production_unchanged": f"{post['baseline']['production_file_positions']['unchanged']}/{post['baseline']['production_file_positions']['count']}",
                                      "production_changed": post["baseline"]["production_file_positions"]["changed"]},
                         "files": {"prework": f"{REL}/evidence/prework_verification.json", "postwork": f"{REL}/evidence/postwork_verification.json"}},
        "exclusions": EXCLUSIONS,
        "safety": {"review_only": True, "live_trading_enabled": False, "training_eligible": False, "strict_pit": False, "M3_complete": False, "M4_complete": False,
                   "M4_02B_started": False, "M4_03_started": False, "M5_started": False, "sqlite_connections": 0, "network_requests": 0, "agents_dispatched": 0,
                   "automation_changed": False, "freeze_modified": False, "codex_files_modified": False, "accepted_by_codex": False, "synthetic_only": True,
                   "hypothetical_fee_schedules_only": True},
        "written": written,
        "sources_read": consumed,
        "next": "Codex independent review of the ledger, tests, contract and evidence; M4-02B only on a new task file after ledger acceptance.",
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"artifact_manifest_sha256": sha256(MANIFEST), "written_files": len(written), "sources_read": len(consumed), "status": manifest["status"],
                      "ledger_policy_hash": ledger.LEDGER_POLICY_HASH, "preservation": manifest["preservation"]["postwork"], "git": manifest["git"]}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
