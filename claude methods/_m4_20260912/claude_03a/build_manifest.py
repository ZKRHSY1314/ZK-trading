"""Write claude_03a/artifact_manifest.json LAST for M4-03A (after the post-work verification).

Path-root convention: paths relative to the project root D:\\codex-A股交易 with forward slashes.  Pins every file written
under claude_03a/ and every consumed source (task file, three M4 freezes and acceptances, accepted contracts and
modules, the historical evidence named by the task, linked metadata, rules and plan documents).  Records the actual
commands and exit codes from the receipts, the before/after preservation of the three freezes and the 42/316/16
baseline entries, and the unresolved requirements.  The manifest does not contain its own hash.

    backend/.venv/Scripts/python.exe -B -X utf8 "claude methods/_m4_20260912/claude_03a/build_manifest.py"
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
REL = "claude methods/_m4_20260912/claude_03a"
TASK_ID = "M4-03A-HISTORICAL-QUALIFICATION-20260912"
TASK_FILE = "claude methods/M4_03A_HISTORICAL_QUALIFICATION_CLAUDE_TASK_20260912.md"
TASK_SHA = "10c0cc348a1dd42b1406ab101c5abd199c7a84553020572e22012301bc9431c9"
MANIFEST = HERE / "artifact_manifest.json"
M2_RUN = "claude methods/_m2_codex_implementation_20260910/staging_runs/ths_v2_20260910_041710_97ef9c09/run_ths_v2_20260910_041710_97ef9c09"
CONSUMED = [
    TASK_FILE,
    "claude methods/M4_02B_CODEX_ACCEPTANCE_20260912.md", "claude methods/M4_02A_CODEX_ACCEPTANCE_20260912.md", "claude methods/M4_01_CODEX_ACCEPTANCE_20260912.md",
    "claude methods/_m4_20260912/execution_freeze.json", "claude methods/_m4_20260912/portfolio_freeze.json", "claude methods/_m4_20260912/risk_freeze.json",
    "claude methods/_m4_20260912/PLAN.md", "claude methods/_m4_20260912/coordination_state.json",
    "claude methods/_m4_20260912/baseline/start.json", "claude methods/_m4_20260912/baseline/immutable_pins.json",
    "claude methods/_m4_20260912/baseline/tracked_files_before.json", "claude methods/_m4_20260912/baseline/production_files_before.json",
    "claude methods/_m4_20260912/claude_01/CONTRACT.md", "claude methods/_m4_20260912/claude_02a/CONTRACT.md", "claude methods/_m4_20260912/claude_02b/CONTRACT.md",
    "claude methods/THREE_YEAR_RESEARCH_EXECUTION_GOAL.md", "AGENTS.md", "CODEX_CLAUDE_COLLABORATION.md", "CLAUDE.md",
    "backend/app/research/m4_execution.py", "backend/app/research/m4_portfolio.py", "backend/app/research/m4_risk.py",
    "backend/app/research/m3_frozen_reader.py", "backend/app/research/m3_labels.py",
    "claude methods/_m3_20260910/codex/final_acceptance_01/completion.json", "claude methods/_m3_20260910/policy_freeze.json",
    "claude methods/_m3_20260910/codex/development_input_audit_01/README.md", "claude methods/_m3_20260910/codex/development_input_audit_01/manifest.json",
    "claude methods/_m3_20260910/codex/development_input_audit_01/result.json", "claude methods/_m3_20260910/codex/development_input_audit_01/source.py",
    "claude methods/_m2_codex_implementation_20260910/qualification_v2_reviewed.json",
    "claude methods/_m3_20260910/codex/metadata_index_01/index.json", "claude methods/_m3_20260910/codex/metadata_index_01/README.md",
    "claude methods/_m1_closure/pilot_symbols.csv",
    f"{M2_RUN}/candidate.json", f"{M2_RUN}/contract_v2.json",
    "backend/.venv/Lib/site-packages/akshare/file_fold/calendar.json",
    "claude methods/_m4_20260912/codex/M4_03A_REVIEW_01.md",
    "claude methods/_m4_20260912/codex/probe_qualification_proposal_01.py", "claude methods/_m4_20260912/codex/probe_qualification_proposal_02.py",
    "claude methods/_m4_20260912/codex/qualification_review_01/independent_proposal_probes.json", "claude methods/_m4_20260912/codex/qualification_review_01/independent_proposal_probes_02.json",
    "claude methods/_m4_20260912/codex/qualification_review_01/verification.json", "claude methods/_m4_20260912/codex/qualification_review_01/replay_receipt.json",
]
REVIEW_SHA = "394ab7f9ba63ba9237cb2d45490c5da1f02920002781164d271b335938515161"
DATABASES = [f"{M2_RUN}/trading.sqlite3", f"{M2_RUN}/history.sqlite3"]
EXCLUSIONS = ["no SQLite connection or SQL query (candidate and production databases only stat/byte-hashed); the validator's sqlite3 probe is denied by its own guard before any connection",
              "no network, client capture, Tonghuashun/Sina access, account, credential, order, screen or service access",
              "no historical strategy or trade run; no price row consumed; no eligibility count beyond frozen audit aggregates",
              "no other agents or workflows; automation untouched",
              "no edits to accepted M4 modules/tests/freezes, M2/M3 artifacts, Codex evidence, PLAN.md, coordination_state.json, package initializers, configuration or production files",
              "no git staging/commit/push; the pre-existing modified set was left as found", "no M4-03B execution, M5 or training; no self-acceptance"]


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
    receipt = json.loads((ev / "validation_receipt.json").read_text(encoding="utf-8"))
    qual = json.loads((HERE / "qualification.json").read_text(encoding="utf-8"))
    if not (pre["ok"] and post["ok"]):
        raise SystemExit("verification not clean")
    if not receipt["passed"] or receipt["guards"]["denials_during_validation"]:
        raise SystemExit("validation receipt not clean")
    if receipt["qualification_sha256"] != sha256(HERE / "qualification.json") or receipt["matrix_sha256"] != sha256(HERE / "QUALIFICATION_MATRIX.md"):
        raise SystemExit("qualification files changed after the recorded validation; re-run validate_qualification.py")
    if sha256(PROJECT / TASK_FILE) != TASK_SHA:
        raise SystemExit("task file hash changed")
    if sha256(PROJECT / "claude methods/_m4_20260912/codex/M4_03A_REVIEW_01.md") != REVIEW_SHA:
        raise SystemExit("review file hash changed")
    if receipt.get("proposal_mapping_sha256") != sha256(HERE / "proposal_mapping.py") or not receipt.get("full_chain_cases") or not all(c.get("passed") for c in receipt["full_chain_cases"].values()):
        raise SystemExit("full-chain cases missing, failing or stale; re-run validate_qualification.py")
    superseded = {}
    for name in ("delivery_01",):
        status_file = HERE / "superseded" / name / "DELIVERY_STATUS.json"
        meta_all = json.loads(status_file.read_text(encoding="utf-8"))
        for relp, meta in meta_all["files"].items():
            if sha256(HERE / "superseded" / name / relp) != meta["sha256"]:
                raise SystemExit(f"superseded {name} file changed: {relp}")
        superseded[name] = {"path": f"{REL}/superseded/{name}/", "status_file_sha256": sha256(status_file), "files": len(meta_all["files"]), "status": meta_all["status"],
                            "manifest_sha256": meta_all["first_delivery_manifest_sha256"], "validator_sha256": meta_all["first_delivery_validator_sha256"], "proposal_sha256": meta_all["first_delivery_proposal_sha256"]}
    written = {}
    for p in sorted(HERE.rglob("*")):
        if p.is_file() and p != MANIFEST and "__pycache__" not in p.parts:
            written[rel(p)] = {"sha256": sha256(p), "bytes": p.stat().st_size}
    consumed = {relp: {"sha256": sha256(PROJECT / relp), "bytes": (PROJECT / relp).stat().st_size} for relp in CONSUMED}
    for relp in DATABASES:
        p = PROJECT / relp
        consumed[relp] = {"sha256": sha256(p), "bytes": p.stat().st_size, "mtime_ns": p.stat().st_mtime_ns, "access": "byte hash + stat only; no sqlite3 connection",
                          "sidecars_present": any((PROJECT / (relp + s)).exists() for s in ("-wal", "-shm", "-journal"))}
    freezes_before = {k: f"{v['pins_ok']}/{v['pins_total']}" for k, v in pre["freezes"].items()}
    freezes_after = {k: f"{v['pins_ok']}/{v['pins_total']}" for k, v in post["freezes"].items()}
    summary = qual["summary"]
    unresolved = [{"id": r["id"], "verdict": r["verdict"], "consequence": r["consequence"]} for r in qual["requirements"] if r["verdict"] != "present"]
    manifest = {
        "schema": "m4.claude_03a.artifact_manifest.v1",
        "task_id": TASK_ID,
        "task_file_sha256": consumed[TASK_FILE]["sha256"],
        "status": "ready_for_review",
        "owner": "Claude (existing ZK-trading / Fable 5.1 project advice fork session a4a3be61-cd46-4bdf-9381-23d97fee303a)",
        "built_at_utc": datetime.now(timezone.utc).isoformat(),
        "path_root_convention": "relative to project root D:\\codex-A股交易, forward slashes",
        "git": {"branch": post["git"]["branch"], "head": post["git"]["head"], "modified_count_before": len(pre["git"]["status_modified"]),
                "modified_count_after": len(post["git"]["status_modified"]), "modified_set_unchanged": pre["git"]["status_modified"] == post["git"]["status_modified"],
                "staged": post["git"]["staged"]},
        "deliverables": {"qualification_matrix": f"{REL}/QUALIFICATION_MATRIX.md", "qualification_json": f"{REL}/qualification.json",
                         "validator": f"{REL}/validate_qualification.py", "validation_receipt": f"{REL}/evidence/validation_receipt.json",
                         "next_read_proposal": f"{REL}/NEXT_READ_PROPOSAL.md", "proposal_mapping": f"{REL}/proposal_mapping.py", "correction_matrix": f"{REL}/CORRECTION_MATRIX.md",
                         "builder": f"{REL}/build_qualification.py", "verification": f"{REL}/verify_baseline.py"},
        "delivery": {"version": "delivery_02", "supersedes": "delivery_01", "trigger": "claude methods/_m4_20260912/codex/M4_03A_REVIEW_01.md", "trigger_sha256": REVIEW_SHA,
                     "superseded": superseded, "codex_files_modified": False,
                     "full_chain_cases": {name: {"passed": c.get("passed")} for name, c in receipt["full_chain_cases"].items()},
                     "proposal_mapping_sha256": receipt["proposal_mapping_sha256"], "frozen_engines": receipt["frozen_engines"]},
        "qualification_summary": {"requirements": summary["requirements"], "verdicts": summary["verdicts"],
                                  "strict_historical_execution_eligible_requirements": summary["strict_historical_execution_eligible_requirements"],
                                  "strict_historical_baseline_provable_now": summary["strict_historical_baseline_provable_now"], "reason": summary["reason"],
                                  "retrospective_bar_diagnostics_possible": summary["retrospective_bar_diagnostics_possible"],
                                  "hypothetical_replay_possible": summary["hypothetical_replay_possible"], "m4_historical_requirement": summary["m4_historical_requirement"],
                                  "codex_contract_gaps_to_note": summary["codex_contract_gaps_to_note"]},
        "unresolved_requirements": unresolved,
        "frozen": {name: {"path": f"claude methods/_m4_20260912/{name}", "sha256": consumed[f"claude methods/_m4_20260912/{name}"]["sha256"], "policy_hash": post["freezes"][name]["policy_hash"],
                          "pins_before": freezes_before[name], "pins_after": freezes_after[name], "modified": False} for name in ("execution_freeze.json", "portfolio_freeze.json", "risk_freeze.json")},
        "preservation": {"prework": {"freezes": freezes_before, "immutable_pins": pre["baseline"]["immutable_pins"], "tracked_files": {"count": pre["baseline"]["tracked_files"]["count"], "changed_or_missing": pre["baseline"]["tracked_files"]["changed_or_missing"]},
                                     "production_file_positions": {k: pre["baseline"]["production_file_positions"][k] for k in ("count", "unchanged", "changed", "note")},
                                     "evidence_pins_ok": f"{sum(1 for v in pre['evidence_sources'].values() if v['ok'])}/{len(pre['evidence_sources'])}", "candidate_databases_ok": all(v["ok"] for v in pre["candidate_databases"].values())},
                         "postwork": {"freezes": freezes_after, "immutable_pins": post["baseline"]["immutable_pins"], "tracked_files": {"count": post["baseline"]["tracked_files"]["count"], "changed_or_missing": post["baseline"]["tracked_files"]["changed_or_missing"]},
                                      "production_file_positions": {k: post["baseline"]["production_file_positions"][k] for k in ("count", "unchanged", "changed", "note")},
                                      "evidence_pins_ok": f"{sum(1 for v in post['evidence_sources'].values() if v['ok'])}/{len(post['evidence_sources'])}", "candidate_databases_ok": all(v["ok"] for v in post["candidate_databases"].values())},
                         "files": {"prework": f"{REL}/evidence/prework_verification.json", "postwork": f"{REL}/evidence/postwork_verification.json"}},
        "commands": [
            {"purpose": "pre-work verification (task hash, three freezes, evidence pins, database stat/hash, baseline 42/316/16, git)", "command": f"backend/.venv/Scripts/python.exe -B -X utf8 \"{REL}/verify_baseline.py\" prework", "exit_code": 0, "at_utc": pre["verified_at_utc"]},
            {"purpose": "build qualification.json + QUALIFICATION_MATRIX.md from pinned metadata (no SQL)", "command": f"backend/.venv/Scripts/python.exe -B -X utf8 \"{REL}/build_qualification.py\"", "exit_code": 0, "at_utc": qual["built_at_utc"]},
            {"purpose": "guarded validator (pins, coverage, anchors, recomputed numbers, safety flags, 9 synthetic frozen-kernel cases, 5 classifier cases, 10 full-chain causal-mapping cases)", "command": " ".join(receipt["command"]),
             "exit_code": 0 if receipt["passed"] else 1, "started_at_utc": receipt["started_at_utc"], "finished_at_utc": receipt["finished_at_utc"],
             "results": {"pins_ok": sum(1 for v in receipt["pins"].values() if v["ok"]), "pins": len(receipt["pins"]), "rows_ok": sum(1 for v in receipt["row_checks"].values() if v == "ok"),
                         "anchors": receipt["anchor_checks"], "numbers_ok": receipt["number_checks"]["ok"], "synthetic_passed": sum(1 for c in receipt["synthetic_kernel_cases"].values() if c["passed"]),
                         "synthetic_total": len(receipt["synthetic_kernel_cases"]), "full_chain_passed": sum(1 for c in receipt["full_chain_cases"].values() if c.get("passed")), "full_chain_total": len(receipt["full_chain_cases"]),
                         "guard_self_check": receipt["guards"]["self_check"], "denials_during_validation": len(receipt["guards"]["denials_during_validation"]),
                         "app_imported": receipt["app_imported"]}},
            {"purpose": "post-work verification", "command": f"backend/.venv/Scripts/python.exe -B -X utf8 \"{REL}/verify_baseline.py\" postwork", "exit_code": 0, "at_utc": post["verified_at_utc"]},
            {"purpose": "this manifest (written last)", "command": f"backend/.venv/Scripts/python.exe -B -X utf8 \"{REL}/build_manifest.py\"", "exit_code": 0},
        ],
        "exclusions": EXCLUSIONS,
        "limitations": ["static qualification only: no historical execution eligibility count was computed (it needs the authorized M4-03B read)",
                        "all availability classes are 2026 capture/assembly; strict PIT remains false for the whole frozen dataset",
                        "the proposal in NEXT_READ_PROPOSAL.md is for Codex review and is not authorization to execute it",
                        "the full-chain checks run the proposal mapping on synthetic bars only; they prove the mapping is causal and runnable, not that any historical fill occurred"],
        "safety": {"review_only": True, "live_trading_enabled": False, "training_eligible": False, "strict_pit": False, "M3_complete": False, "M4_complete": False,
                   "M4_03B_started": False, "M5_started": False, "sqlite_connections": 0, "network_requests": 0, "historical_trades_run": 0, "price_rows_consumed": 0,
                   "agents_dispatched": 0, "automation_changed": False, "freezes_modified": False, "codex_files_modified": False, "accepted_by_codex": False},
        "written": written, "consumed": consumed,
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"artifact_manifest_sha256": sha256(MANIFEST), "written_files": len(written), "sources_read": len(consumed), "status": manifest["status"],
                      "qualification": manifest["qualification_summary"]["verdicts"], "strict_baseline_provable_now": manifest["qualification_summary"]["strict_historical_baseline_provable_now"],
                      "preservation_postwork": manifest["preservation"]["postwork"], "git": manifest["git"]}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
