"""Write claude_02b/artifact_manifest.json LAST for M4-02B (after the post-work verification).

Path-root convention: paths relative to the project root D:\\codex-A股交易 with forward slashes.  Pins every file written
under claude_02b/ plus the two new code files, and every consumed source (task file, both freezes, acceptances, frozen
kernel/ledger sources and tests, contracts, plan/coordination/baseline, collaboration rules).  Records actual commands,
exit codes and counts from the receipts and the preservation results.  The manifest does not contain its own hash.

    backend/.venv/Scripts/python.exe -B -X utf8 "claude methods/_m4_20260912/claude_02b/build_manifest.py"
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
REL = "claude methods/_m4_20260912/claude_02b"
TASK_ID = "M4-02B-RISK-EXIT-20260912"
RISK_REL = "backend/app/research/m4_risk.py"
TESTS_REL = "backend/tests/test_m4_risk.py"
MANIFEST = HERE / "artifact_manifest.json"
CONSUMED = [
    "claude methods/M4_02B_RISK_EXIT_CLAUDE_TASK_20260912.md",
    "claude methods/M4_02A_CODEX_ACCEPTANCE_20260912.md",
    "claude methods/M4_01_CODEX_ACCEPTANCE_20260912.md",
    "claude methods/_m4_20260912/execution_freeze.json",
    "claude methods/_m4_20260912/portfolio_freeze.json",
    "claude methods/_m4_20260912/PLAN.md",
    "claude methods/_m4_20260912/coordination_state.json",
    "claude methods/_m4_20260912/baseline/start.json",
    "claude methods/_m4_20260912/baseline/immutable_pins.json",
    "claude methods/_m4_20260912/baseline/tracked_files_before.json",
    "claude methods/_m4_20260912/baseline/production_files_before.json",
    "claude methods/_m4_20260912/claude_01/CONTRACT.md",
    "claude methods/_m4_20260912/claude_02a/CONTRACT.md",
    "claude methods/THREE_YEAR_RESEARCH_EXECUTION_GOAL.md",
    "backend/app/research/m4_execution.py",
    "backend/tests/test_m4_execution.py",
    "backend/app/research/m4_portfolio.py",
    "backend/tests/test_m4_portfolio.py",
    "AGENTS.md",
    "CODEX_CLAUDE_COLLABORATION.md",
    "CLAUDE.md",
    "claude methods/_m4_20260912/codex/M4_02B_REVIEW_01.md",
    "claude methods/_m4_20260912/codex/probe_risk_01.py",
    "claude methods/_m4_20260912/codex/risk_review_01/results.json",
    "claude methods/_m4_20260912/codex/risk_review_01/m4_risk.py",
    "claude methods/_m4_20260912/codex/M4_02B_REVIEW_02.md",
    "claude methods/_m4_20260912/codex/probe_risk_02.py",
    "claude methods/_m4_20260912/codex/probe_risk_additional_02.py",
    "claude methods/_m4_20260912/codex/risk_review_02/results.json",
    "claude methods/_m4_20260912/codex/risk_review_02/additional_results.json",
    "claude methods/_m4_20260912/codex/risk_review_02/m4_risk.py",
]
EXCLUSIONS = ["no SQLite connection or SQL query (databases only stat/byte-hashed by the verification script)",
              "no network, client, account, credential, order, screen or service access", "no other agents or workflows; automation untouched",
              "no edits to frozen M4-01 / M4-02A code, tests or evidence, M2/M3 artifacts, Codex files, package initializers, configuration, legacy engine or frontend",
              "no git staging/commit/push; the pre-existing modified set was left as found", "no historical data (M4-03), M5 or training; no self-acceptance"]


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
    ev = HERE / "evidence"
    pre = json.loads((ev / "prework_verification.json").read_text(encoding="utf-8"))
    post = json.loads((ev / "postwork_verification.json").read_text(encoding="utf-8"))
    receipt = json.loads((ev / "execution_receipt.json").read_text(encoding="utf-8"))
    kernel_rerun = json.loads((ev / "kernel_suite_rerun_receipt.json").read_text(encoding="utf-8"))
    ledger_rerun = json.loads((ev / "ledger_suite_rerun_receipt.json").read_text(encoding="utf-8"))
    if not (pre["ok"] and post["ok"]):
        raise SystemExit("verification not clean")
    for rc in (receipt, kernel_rerun, ledger_rerun):
        if rc["exit_code"] != 0 or not rc["tests"]["successful"] or not rc["frozen_pins_ok"]:
            raise SystemExit(f"receipt not clean: {rc['suite']}")
    for relp in (RISK_REL, TESTS_REL):
        if receipt["files"][relp]["sha256_after"] != sha256(PROJECT / relp):
            raise SystemExit(f"{relp} changed after the recorded run")
    replay = json.loads((ev / "codex_probe_risk_replay_01.json").read_text(encoding="utf-8"))
    if replay["current_source_hashes"][RISK_REL] != sha256(PROJECT / RISK_REL) or replay["summary"]["passed_now"] != replay["summary"]["checks"]:
        raise SystemExit("codex probe replay stale or failing; re-run replay_codex_probe_risk_01.py")
    replay2 = json.loads((ev / "codex_probe_risk_replay_02.json").read_text(encoding="utf-8"))
    if replay2["current_source_hashes"][RISK_REL] != sha256(PROJECT / RISK_REL) or replay2["summary"]["passed_now"] != replay2["summary"]["checks"]:
        raise SystemExit("codex probe replay 02 stale or failing; re-run replay_codex_probe_risk_02.py")
    superseded = {}
    for name in ("delivery_01", "delivery_02"):
        status_file = HERE / "superseded" / name / "DELIVERY_STATUS.json"
        meta_all = json.loads(status_file.read_text(encoding="utf-8"))
        for relp, meta in meta_all["files"].items():
            if sha256(HERE / "superseded" / name / relp) != meta["sha256"]:
                raise SystemExit(f"superseded {name} file changed: {relp}")
        superseded[name] = {"path": f"{REL}/superseded/{name}/", "status_file_sha256": sha256(status_file), "files": len(meta_all["files"]),
                            "risk_sha256": meta_all["files"]["code/m4_risk.py"]["sha256"], "tests_sha256": meta_all["files"]["code/test_m4_risk.py"]["sha256"],
                            "manifest_sha256": meta_all["files"]["artifact_manifest.json"]["sha256"], "status": meta_all["status"]}
    kernel = load("m4_execution_manifest_readonly", PROJECT / "backend/app/research/m4_execution.py")
    ledger = load("m4_portfolio_manifest_readonly", PROJECT / "backend/app/research/m4_portfolio.py")
    risk = load("m4_risk_manifest_readonly", PROJECT / RISK_REL)
    written = {}
    for p in sorted(HERE.rglob("*")):
        if p.is_file() and p != MANIFEST and "__pycache__" not in p.parts:
            written[rel(p)] = {"sha256": sha256(p), "bytes": p.stat().st_size}
    for relp in (RISK_REL, TESTS_REL):
        written[relp] = {"sha256": sha256(PROJECT / relp), "bytes": (PROJECT / relp).stat().st_size}
    consumed = {relp: {"sha256": sha256(PROJECT / relp), "bytes": (PROJECT / relp).stat().st_size} for relp in CONSUMED}
    manifest = {
        "schema": "m4.claude_02b.artifact_manifest.v1",
        "task_id": TASK_ID,
        "task_file_sha256": consumed["claude methods/M4_02B_RISK_EXIT_CLAUDE_TASK_20260912.md"]["sha256"],
        "status": "ready_for_review",
        "owner": "Claude (existing ZK-trading / Fable 5.1 project advice fork session a4a3be61-cd46-4bdf-9381-23d97fee303a)",
        "built_at_utc": datetime.now(timezone.utc).isoformat(),
        "path_root_convention": "relative to project root D:\\codex-A股交易, forward slashes",
        "git": {"branch": post["git"]["branch"], "head": post["git"]["head"], "modified_count_before": len(pre["git"]["status_modified"]),
                "modified_count_after": len(post["git"]["status_modified"]), "modified_set_unchanged": pre["git"]["status_modified"] == post["git"]["status_modified"],
                "staged": post["git"]["staged"]},
        "frozen": {"execution_freeze_sha256": consumed["claude methods/_m4_20260912/execution_freeze.json"]["sha256"],
                   "portfolio_freeze_sha256": consumed["claude methods/_m4_20260912/portfolio_freeze.json"]["sha256"],
                   "kernel": {"path": "backend/app/research/m4_execution.py", "sha256": consumed["backend/app/research/m4_execution.py"]["sha256"], "policy_hash": kernel.POLICY_HASH},
                   "ledger": {"path": "backend/app/research/m4_portfolio.py", "sha256": consumed["backend/app/research/m4_portfolio.py"]["sha256"], "policy_hash": ledger.LEDGER_POLICY_HASH},
                   "modified": False, "pins_ok": {"execution_freeze": f"{post['execution_freeze']['pins_ok']}/{post['execution_freeze']['pins_total']}",
                                                  "portfolio_freeze": f"{post['portfolio_freeze']['pins_ok']}/{post['portfolio_freeze']['pins_total']}"}},
        "code": {RISK_REL: written[RISK_REL], TESTS_REL: written[TESTS_REL]},
        "delivery": {"version": "delivery_03", "supersedes": ["delivery_02", "delivery_01"],
                     "triggers": [{"review": "claude methods/_m4_20260912/codex/M4_02B_REVIEW_01.md", "sha256": consumed["claude methods/_m4_20260912/codex/M4_02B_REVIEW_01.md"]["sha256"]},
                                  {"review": "claude methods/_m4_20260912/codex/M4_02B_REVIEW_02.md", "sha256": consumed["claude methods/_m4_20260912/codex/M4_02B_REVIEW_02.md"]["sha256"]}],
                     "correction_matrix": f"{REL}/CORRECTION_MATRIX.md", "superseded": superseded,
                     "codex_probe_replays": [
                         {"file": f"{REL}/evidence/codex_probe_risk_replay_01.json", "checks": replay["summary"]["checks"], "passed_now": replay["summary"]["passed_now"],
                          "passed_on_first_delivery": replay["summary"]["passed_on_first_delivery"], "frozen_results_sha256": replay["frozen_results_sha256"], "adaptation": replay["adaptation"]},
                         {"file": f"{REL}/evidence/codex_probe_risk_replay_02.json", "checks": replay2["summary"]["checks"], "passed_now": replay2["summary"]["passed_now"],
                          "passed_on_second_delivery": replay2["summary"]["passed_on_second_delivery"], "frozen_results_sha256": replay2["frozen_results_sha256"], "adaptation": replay2["adaptation"]}],
                     "codex_files_modified": False},
        "execution_policy": {"contract_version": risk.RISK_CONTRACT_VERSION, "risk_policy_hash": risk.RISK_POLICY_HASH, "policy": risk.RISK_POLICY, "frozen": False,
                             "status": "proposed_pending_codex_review"},
        "commands": [
            {"purpose": "pre-work verification", "command": f"backend/.venv/Scripts/python.exe -B -X utf8 \"{REL}/verify_pins.py\" prework", "exit_code": 0 if pre["ok"] else 1, "at_utc": pre["verified_at_utc"]},
            {"purpose": "codex probe replay (review 01: 5 checks, verbatim fixtures; policy phase adaptation documented)", "command": f"backend/.venv/Scripts/python.exe -B -X utf8 \"{REL}/replay_codex_probe_risk_01.py\"",
             "exit_code": 0 if replay["summary"]["passed_now"] == replay["summary"]["checks"] else 1, "at_utc": replay["observed_at_utc"]},
            {"purpose": "codex probe replay (review 02: 6 additional checks, verbatim fixtures)", "command": f"backend/.venv/Scripts/python.exe -B -X utf8 \"{REL}/replay_codex_probe_risk_02.py\"",
             "exit_code": 0 if replay2["summary"]["passed_now"] == replay2["summary"]["checks"] else 1, "at_utc": replay2["observed_at_utc"]},
            {"purpose": "risk suite (guarded, final code, run once)", "command": " ".join(receipt["command"]), "exit_code": receipt["exit_code"],
             "started_at_utc": receipt["started_at_utc"], "finished_at_utc": receipt["finished_at_utc"], "tests": {k: v for k, v in receipt["tests"].items() if k != "names"}},
            {"purpose": "frozen kernel suite read-only rerun (guarded)", "command": " ".join(kernel_rerun["command"]), "exit_code": kernel_rerun["exit_code"],
             "started_at_utc": kernel_rerun["started_at_utc"], "finished_at_utc": kernel_rerun["finished_at_utc"], "tests": {k: v for k, v in kernel_rerun["tests"].items() if k != "names"}},
            {"purpose": "frozen ledger suite read-only rerun (guarded)", "command": " ".join(ledger_rerun["command"]), "exit_code": ledger_rerun["exit_code"],
             "started_at_utc": ledger_rerun["started_at_utc"], "finished_at_utc": ledger_rerun["finished_at_utc"], "tests": {k: v for k, v in ledger_rerun["tests"].items() if k != "names"}},
            {"purpose": "post-work verification", "command": f"backend/.venv/Scripts/python.exe -B -X utf8 \"{REL}/verify_pins.py\" postwork", "exit_code": 0 if post["ok"] else 1, "at_utc": post["verified_at_utc"]},
        ],
        "tests_actually_run": {"risk_suite": receipt["tests"]["run"], "risk_failures": receipt["tests"]["failures"], "risk_errors": receipt["tests"]["errors"],
                               "kernel_suite_rerun": kernel_rerun["tests"]["run"], "ledger_suite_rerun": ledger_rerun["tests"]["run"],
                               "focused_development_runs": "several direct unittest runs of the same file during development, not recorded as evidence",
                               "guards": receipt["guards"]["self_check"], "guard_denials_during_tests": receipt["guards"]["denial_count_during_tests"],
                               "isolation": receipt["isolation"], "scenarios": receipt["risk_scenarios"]},
        "preservation": {"prework": {"execution_freeze_pins": f"{pre['execution_freeze']['pins_ok']}/{pre['execution_freeze']['pins_total']}",
                                     "portfolio_freeze_pins": f"{pre['portfolio_freeze']['pins_ok']}/{pre['portfolio_freeze']['pins_total']}",
                                     "immutable_pins": pre["baseline"]["immutable_pins"], "tracked_changed": pre["baseline"]["tracked_files"]["changed_or_missing"],
                                     "production_unchanged": f"{pre['baseline']['production_file_positions']['unchanged']}/{pre['baseline']['production_file_positions']['count']}"},
                         "postwork": {"execution_freeze_pins": f"{post['execution_freeze']['pins_ok']}/{post['execution_freeze']['pins_total']}",
                                      "portfolio_freeze_pins": f"{post['portfolio_freeze']['pins_ok']}/{post['portfolio_freeze']['pins_total']}",
                                      "immutable_pins": post["baseline"]["immutable_pins"], "tracked_changed": post["baseline"]["tracked_files"]["changed_or_missing"],
                                      "production_unchanged": f"{post['baseline']['production_file_positions']['unchanged']}/{post['baseline']['production_file_positions']['count']}",
                                      "production_changed": post["baseline"]["production_file_positions"]["changed"]},
                         "files": {"prework": f"{REL}/evidence/prework_verification.json", "postwork": f"{REL}/evidence/postwork_verification.json"}},
        "limitations": ["prior-close decisions only; no intraday decisions or intrabar ordering inference", "one exit intent per symbol; exits sell the full position",
                        "a gap at execution downsizes the intent itself; a valid unaffordable print cancels it (declared choices)",
                        "the current-risk re-check needs causally eligible marks for other holdings (max_mark_age_sessions + 1); otherwise the buy is refused",
                        "marks injected for the target symbol at execution are not consulted (the observed print values it); performance is a view gated by ledger time only",
                        "a kernel-rejected attempt that reached the ledger advances the policy event clock (it is recorded attempt history); policy refusals and duplicates do not",
                        "entry sessions before the injected calendar cannot be aged for max_holding", "delisted holdings stay unresolved (no settlement/corporate-action support in the frozen contracts)",
                        "hypothetical fees, slippage, lot and policy parameters; synthetic evidence only; no historical execution evidence; M4 not complete"],
        "exclusions": EXCLUSIONS,
        "safety": {"review_only": True, "live_trading_enabled": False, "training_eligible": False, "strict_pit": False, "M3_complete": False, "M4_complete": False,
                   "M4_03_started": False, "M5_started": False, "sqlite_connections": 0, "network_requests": 0, "agents_dispatched": 0, "automation_changed": False,
                   "freezes_modified": False, "codex_files_modified": False, "accepted_by_codex": False, "synthetic_only": True, "hypothetical_fee_schedules_only": True},
        "written": written,
        "sources_read": consumed,
        "next": "Codex independent review of the risk/exit layer, tests, contract and evidence; M4-03 (historical qualification) only on a new task file.",
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"artifact_manifest_sha256": sha256(MANIFEST), "written_files": len(written), "sources_read": len(consumed), "status": manifest["status"],
                      "risk_policy_hash": risk.RISK_POLICY_HASH, "code": manifest["code"], "preservation": manifest["preservation"]["postwork"], "git": manifest["git"]}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
