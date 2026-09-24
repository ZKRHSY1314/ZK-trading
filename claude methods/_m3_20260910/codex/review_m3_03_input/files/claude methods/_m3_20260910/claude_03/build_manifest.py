"""Build claude_03/artifact_manifest.json for M3-03-CASE-REVIEW-20260910 (written last).

Pins every file written under claude_03/ (reviews, diagnostics, authored notes + history snapshots, execution
evidence incl. superseded drafts, tools, report) and every consumed source (the 43 pinned bundle files, the
accepted label kernel, frozen policy files, rubric, task/acceptance files, the six in-task Codex notes and the
prior claude_01_r3/claude_02 manifests).  Re-verifies the validation receipt before writing.  No network, SQLite
or account access.

    backend/.venv/Scripts/python.exe -B -X utf8 "claude methods/_m3_20260910/claude_03/build_manifest.py"
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

C03 = Path(__file__).resolve().parent
PROJECT = C03.parents[2]
BUNDLE_REL = "claude methods/_m3_20260910/codex/case_review_bundle_01"
OUT = C03 / "artifact_manifest.json"
TASK_ID = "M3-03-CASE-REVIEW-20260910"
EXTERNAL_SOURCES = {
    "backend/app/research/m3_labels.py": "e20eb21cdea032ced319a8f45a34cdeb03fd4d8b357ac31403306fa73b225393",
    "claude methods/_m3_20260910/policy_freeze.json": "925ae86f772908babef6bc6a08a1ace58c2db7a5e71c7f97af8ad52f2c7a891f",
    "claude methods/_m3_20260910/claude_01_r3/LABEL_POLICY.json": "70180fa31685ac730f74c7abd4a524151d4148c2eda75c0c6dd74ec883ef88e1",
    "claude methods/M3_03_CASE_REVIEW_CLAUDE_TASK_20260910.md": "8a3245704350d71fd465f73d63bcd6901a9e2ddd08f1bcd0b9c9336f514f9a7c",
    "claude methods/M3_02_CODEX_ACCEPTANCE_20260910.md": "4c1fcc2376c93c5ebf233b28b1d2f6608108eadadd8754ca30cb3e79124648dd",
    "claude methods/_m3_20260910/codex/CASE_REVIEW_RUBRIC.md": "a2f5c6450686a600319456d51b8b77dae60e071e9dbf9aebcb9df5aaf3f0da6e",
    "claude methods/_m3_20260910/codex/M3_03_PROVENANCE_DISPLAY_CLARIFICATION.md": "1bb8cb2905bdc200c0f06a9973a856ee5e92d9ef731dce321389a81df6aa585d",
    "claude methods/_m3_20260910/codex/M3_03_WORKING_NARRATIVE_FACT_CHECK.md": "e0c592bd10a424054666fdba6db46d36eb9126fced27a69fdc6804a7acfdaa44",
    "claude methods/_m3_20260910/codex/M3_03_FINAL_WORDING_CHECK.md": "4a2d54681d84bfedee28336862c816ea5785d3f70ce6704b9db008214a23f066",
    "claude methods/_m3_20260910/codex/M3_03_DIAGNOSTIC_WORDING_CHECK.md": "e8698cbcdc2ecabaf869c201d3a439265d31e5aae2a727f5f2449d74f6b7b955",
    "claude methods/_m3_20260910/codex/M3_03_SERIALIZED_EFFECTIVE_TEXT_FEEDBACK.md": "61215ecf8aa1c3e2f6e8658d279e269cb6a81153b4f563090e18d8fa08967b7b",
    "claude methods/_m3_20260910/codex/M3_03_REPORT_COUNT_FACT_CHECK.md": "e2cf48188332076b6a400780359e9a0306b4fc99851741ae9bda699d4f577016",
    "claude methods/_m3_20260910/claude_02/artifact_manifest.json": "4aa337d9840c970700bad7f2566af7e7a84a486ec8180c1b0295664bc0662962",
    "claude methods/_m3_20260910/claude_01_r3/artifact_manifest.json": "7060f61f8eb637d6e92efb075e6a0cfdad041e370d30874afb9172a2d04fce39",
    f"{BUNDLE_REL}/manifest.json": "fa234fded7e448f1d8313ee26f43f1e81902e9294426faf1dc2164747ac887fc",
    f"{BUNDLE_REL}/index.json": "77e29df61a9ffa85379a1505a9f1065574968255ff30249dab4d97b99dcb8fec",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    sources: dict[str, dict] = {}
    for rel, expected in EXTERNAL_SOURCES.items():
        p = PROJECT / rel
        actual = sha(p)
        if actual != expected:
            raise SystemExit(f"consumed source changed: {rel} {actual}")
        sources[rel] = {"sha256": actual, "bytes": p.stat().st_size}
    bundle_manifest = json.loads((PROJECT / BUNDLE_REL / "manifest.json").read_text(encoding="utf-8"))
    for rel, v in bundle_manifest["written"].items():
        p = PROJECT / BUNDLE_REL / rel
        if sha(p) != v["sha256"]:
            raise SystemExit(f"bundle file changed: {rel}")
        sources[f"{BUNDLE_REL}/{rel}"] = {"sha256": v["sha256"], "bytes": p.stat().st_size}

    validation = json.loads((C03 / "execution" / "validation_receipt.json").read_text(encoding="utf-8"))
    receipt = json.loads((C03 / "execution" / "execution_receipt.json").read_text(encoding="utf-8"))
    count_check = json.loads((C03 / "execution" / "report_count_check.json").read_text(encoding="utf-8"))
    if not validation["ok"] or validation["problems"] or validation["execution_id_validated"] != receipt["execution_id"]:
        raise SystemExit("validation receipt is not clean for the current execution")
    if sha(C03 / "tools" / "validate_reviews.py") != validation["validator_sha256"]:
        raise SystemExit("validator changed after validation")

    written: dict[str, dict] = {}
    for p in sorted(C03.rglob("*")):
        if p.is_file() and p != OUT and "__pycache__" not in p.parts:
            rel = p.relative_to(C03).as_posix()
            written[rel] = {"sha256": sha(p), "bytes": p.stat().st_size}
    case_reviews = [r for r in written if r.startswith("reviews/")]
    diag_reviews = [r for r in written if r.startswith("diagnostics/")]
    if len(case_reviews) != 32 or len(diag_reviews) != 8:
        raise SystemExit("unexpected review file count")
    for c in receipt["cases"]:
        if written[f"reviews/{c['case_id']}.json"]["sha256"] != c["review_sha256"]:
            raise SystemExit(f"{c['case_id']}: review file differs from execution receipt")
    for d in receipt["diagnostics"]:
        if written[f"diagnostics/{d['case_id']}.json"]["sha256"] != d["review_sha256"]:
            raise SystemExit(f"{d['case_id']}: diagnostic file differs from execution receipt")

    original_notes = {}
    for rel in written:
        if rel.startswith("authored_notes/") and rel.endswith(".json"):
            original_notes[rel] = written[rel]["sha256"]
    manifest = {
        "schema": "m3.claude_03.artifact_manifest.v1",
        "task_id": TASK_ID,
        "status": "ready_for_review",
        "owner": "Claude agent reviewer (existing ZK-trading / Fable 5.1 project advice fork session a4a3be61-cd46-4bdf-9381-23d97fee303a)",
        "reviewer": {"reviewer_id": receipt["reviewer_id"], "reviewer_kind": receipt["reviewer_kind"], "description": receipt["reviewer_description"]},
        "built_at_utc": datetime.now(timezone.utc).isoformat(),
        "accepted_by_codex": False,
        "serialization": {"generation": receipt["serialization_generation"], "execution_id": receipt["execution_id"],
                          "started_at_utc": receipt["started_at_utc"], "finished_at_utc": receipt["finished_at_utc"],
                          "superseded_draft_execution_id": receipt["superseded_draft"]["draft_execution_id"],
                          "superseded_draft_path": receipt["superseded_draft"]["path"], "raw_supersedes_reference": None,
                          "reviewed_at_semantics": receipt["reviewed_at_semantics"]},
        "validation": {"receipt": "execution/validation_receipt.json", "sha256": written["execution/validation_receipt.json"]["sha256"],
                       "ok": validation["ok"], "problems": validation["problems"], "validated_at_utc": validation["validated_at_utc"],
                       "validator_sha256": validation["validator_sha256"], "runs_on_final_serialization": 1,
                       "stdout": "execution/validate_reviews_stdout.txt"},
        "counts": {
            "cases_reviewed": 32, "diagnostics_reviewed": 8, "control_uses_reviewed": receipt["control_uses_reviewed"],
            "verdicts": receipt["verdict_counts"], "counting_eligible_cases": receipt["counting_eligible_cases"],
            "fragile_control_uses": receipt["fragile_control_uses"], "inadmissible_control_uses": receipt["inadmissible_control_uses"],
            "unique_control_symbols": validation["checks"]["unique_control_symbols"], "control_reuse_max": validation["checks"]["control_reuse_max"],
            "thin_margin_prefixes_strict_lt_0_01": count_check["thin_union_count"], "thin_by_leg": count_check["thin_by_leg"],
            "negative_narrative_groups": {"advance_rebound": count_check["narrative_groups"]["advance_rebound_count"],
                                          "break_decline_possible_lock": count_check["narrative_groups"]["break_decline_possible_lock_count"]},
            "cores_verified_by_dossier_tool": receipt["evidence_inspection_log"]["cores_verified_total"],
            "inspection_log_entries": receipt["evidence_inspection_log"]["entries"],
            "effective_text_cases": receipt["effective_text"]["cases_with_effective_text"],
            "history_snapshots": validation["checks"]["history_snapshots"],
        },
        "target": validation["target"],
        "in_task_feedback_incorporated": [
            {"note": "claude methods/_m3_20260910/codex/M3_03_PROVENANCE_DISPLAY_CLARIFICATION.md", "sha256": EXTERNAL_SOURCES["claude methods/_m3_20260910/codex/M3_03_PROVENANCE_DISPLAY_CLARIFICATION.md"], "applied": "locator-union provenance wording; per-role counts; C012 addendum; provenance_clarification in every review"},
            {"note": "claude methods/_m3_20260910/codex/M3_03_WORKING_NARRATIVE_FACT_CHECK.md", "sha256": EXTERNAL_SOURCES["claude methods/_m3_20260910/codex/M3_03_WORKING_NARRATIVE_FACT_CHECK.md"], "applied": "C016/C012/C019/C022/C013/C004/C008/C009 addenda + effective text"},
            {"note": "claude methods/_m3_20260910/codex/M3_03_FINAL_WORDING_CHECK.md", "sha256": EXTERNAL_SOURCES["claude methods/_m3_20260910/codex/M3_03_FINAL_WORDING_CHECK.md"], "applied": "C031/C018/C027/C032 addenda + effective text"},
            {"note": "claude methods/_m3_20260910/codex/M3_03_DIAGNOSTIC_WORDING_CHECK.md", "sha256": EXTERNAL_SOURCES["claude methods/_m3_20260910/codex/M3_03_DIAGNOSTIC_WORDING_CHECK.md"], "applied": "D007 no_trade correction; retrospective cross-reference segregation"},
            {"note": "claude methods/_m3_20260910/codex/M3_03_SERIALIZED_EFFECTIVE_TEXT_FEEDBACK.md", "sha256": EXTERNAL_SOURCES["claude methods/_m3_20260910/codex/M3_03_SERIALIZED_EFFECTIVE_TEXT_FEEDBACK.md"], "applied": "serializer generation 2: effective text in current fields and raw_review.notes; generation-1 draft preserved under execution/superseded_draft_01/; reviewed_at documented as sealing/binding time"},
            {"note": "claude methods/_m3_20260910/codex/M3_03_REPORT_COUNT_FACT_CHECK.md", "sha256": EXTERNAL_SOURCES["claude methods/_m3_20260910/codex/M3_03_REPORT_COUNT_FACT_CHECK.md"], "applied": "report section 5 corrected to 15/32 thin-margin prefixes and 7+7 negative groups with executed check (tools/check_report_counts.py, re-executed in the validator); C010/C031 thin wording addenda; working report draft preserved under execution/superseded_report_draft_01/"},
        ],
        "verdicts_unchanged_by_feedback": True,
        "preserved_originals": original_notes,
        "superseded_drafts": {
            "execution/superseded_draft_01/DRAFT_STATUS.json": written["execution/superseded_draft_01/DRAFT_STATUS.json"]["sha256"],
            "execution/superseded_report_draft_01/DRAFT_STATUS.json": written["execution/superseded_report_draft_01/DRAFT_STATUS.json"]["sha256"],
        },
        "policy": {"policy_hash": receipt["policy_hash"], "labels_module_sha256": receipt["labels_module_sha256"], "policy_version": "0.3.0-draft",
                   "changed": False},
        "safety": {"review_only": True, "live_trading_enabled": False, "strict_pit": False, "training_eligible": False,
                   "m3_complete": False, "training_ready": False, "sqlite_connections": 0, "network": 0, "account_access": False,
                   "full_chronology_files_opened": 0, "episode_audit_files_opened": 0, "later_outcomes_consulted": False,
                   "codex_reviews_read": False, "codex_serialization_preview_read": False, "subagents_dispatched": 0,
                   "files_written_outside_claude_03": 0, "frozen_inputs_modified": 0, "tuned_to_target": False},
        "sources_read": sources,
        "sources_unchanged_after_run": True,
        "written": written,
        "next": "Codex: independent review of the same bundle, reconciliation of preserved opinions and dissent, canonical ledger and counts.",
    }
    OUT.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"artifact_manifest_sha256": sha(OUT), "written_files": len(written), "sources_read": len(sources),
                      "counts": {k: v for k, v in manifest["counts"].items() if k in ("cases_reviewed", "diagnostics_reviewed", "control_uses_reviewed", "verdicts", "fragile_control_uses", "thin_margin_prefixes_strict_lt_0_01")},
                      "status": manifest["status"]}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
