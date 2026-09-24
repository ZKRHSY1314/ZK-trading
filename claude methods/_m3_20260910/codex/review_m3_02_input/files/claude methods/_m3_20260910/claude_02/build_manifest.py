"""Build the claude_02 artifact manifest for M3-02 (pins every output, every source read, the accepted label
policy/module and every actual database connection).  No SQLite, no network.  Run last.

    D:/codex-A股交易/backend/.venv/Scripts/python.exe -B -X utf8 "claude methods/_m3_20260910/claude_02/build_manifest.py" dev_run_01
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[2]

SOURCES_READ = [
    "claude methods/M3_02_FROZEN_READER_CLAUDE_TASK_20260910.md",
    "claude methods/M3_01_R3_CODEX_REVIEW_20260910.md",
    "claude methods/_m3_20260910/policy_freeze.json",
    "claude methods/_m3_20260910/codex/READER_CONTRACT_PREPARATION.md",
    "claude methods/_m3_20260910/codex/CASE_REVIEW_RUBRIC.md",
    "claude methods/_m3_20260910/codex/metadata_index_01/README.md",
    "claude methods/_m3_20260910/codex/metadata_index_01/index.json",
    "claude methods/_m3_20260910/codex/review_03_validation.json",
    "claude methods/_m3_20260910/codex/M3_02_WORKING_BOUNDARY_FEEDBACK.md",
    "claude methods/_m3_20260910/codex/M3_02_WORKING_PACKET_CUTOFF_FEEDBACK.md",
    "claude methods/_m3_20260910/codex/test_independent_reader_boundary.py",
    "claude methods/_m3_20260910/codex/run_reader_boundary_review.py",
    "claude methods/_m3_20260910/codex/reader_working_boundary_tests_01/execution.json",
    "claude methods/_m3_20260910/codex/reader_working_boundary_tests_01/stderr.txt",
    "claude methods/_m3_20260910/codex/reader_working_preview_input_01/snapshot.json",
    "claude methods/_m3_20260910/codex/audit_working_packet_cutoffs.py",
    "claude methods/_m3_20260910/codex/reader_working_packet_cutoff_audit_01/result.json",
    "claude methods/_m3_20260910/codex/test_independent_r3_bound.py",
    "claude methods/_m3_20260910/claude_01_r3/artifact_manifest.json",
    "claude methods/_m3_20260910/claude_01_r3/LABEL_POLICY.json",
    "claude methods/THREE_YEAR_RESEARCH_EXECUTION_GOAL.md",
    "AGENTS.md", "CODEX_CLAUDE_COLLABORATION.md",
    "claude methods/_m2_codex_implementation_20260910/qualification_v2_reviewed.json",
    "claude methods/_m2_codex_implementation_20260910/staging.py",
    "claude methods/_m2_codex_implementation_20260910/staging_v2.py",
    "claude methods/_m2_ths_v2_claude_review_20260910/r02_db_schema.json",
    "claude methods/_m2_ths_v2_claude_review_20260910/r06_basis_unit_controls.json",
    "claude methods/_m1_closure/pilot_symbols.csv",
    "backend/.venv/Lib/site-packages/akshare/file_fold/calendar.json",
    "claude methods/_m2_codex_implementation_20260910/staging_runs/ths_v2_20260910_041710_97ef9c09/run_ths_v2_20260910_041710_97ef9c09/trading.sqlite3",
    "claude methods/_m2_codex_implementation_20260910/staging_runs/ths_v2_20260910_041710_97ef9c09/run_ths_v2_20260910_041710_97ef9c09/history.sqlite3",
]
PRESERVED = {
    "backend/app/research/m3_labels.py": "e20eb21cdea032ced319a8f45a34cdeb03fd4d8b357ac31403306fa73b225393",
    "backend/tests/test_m3_labels.py": "41eba60b21b507250f9a9a4f359fdc330232306c61b535f3d82db18ba9e45180",
    "claude methods/_m3_20260910/policy_freeze.json": "925ae86f772908babef6bc6a08a1ace58c2db7a5e71c7f97af8ad52f2c7a891f",
    "claude methods/_m3_20260910/claude_01_r3/artifact_manifest.json": "7060f61f8eb637d6e92efb075e6a0cfdad041e370d30874afb9172a2d04fce39",
    "claude methods/_m3_20260910/claude_01_r2/artifact_manifest.json": "34b28360fc9842876a2c321d7316bec2b7f1e0b3935f1cfd17711ac1857d7451",
    "claude methods/_m3_20260910/claude_01/artifact_manifest.json": "428bb425661239de755dca6ac49e5128a923f8b90ebdb19e1c85d404e67a5147",
    "claude methods/M3_01_R3_CODEX_REVIEW_20260910.md": "871999df90a932b69e7ca85e74b92e668ce5a0f5f43d2f0bb5caa3b8791313ef",
    "claude methods/M3_02_FROZEN_READER_CLAUDE_TASK_20260910.md": "13908dc657d0a1c3829703527cb936916296f55fa490436c19824ec83ff33d96",
    "claude methods/_m2_codex_implementation_20260910/qualification_v2_reviewed.json": "992bd79ce9d2e38d1a0a8ae2f9890cd26daebcd3d2ab664d5caab171ec3e0f37",
    "claude methods/_m2_codex_implementation_20260910/staging_runs/ths_v2_20260910_041710_97ef9c09/run_ths_v2_20260910_041710_97ef9c09/trading.sqlite3": "c0b26660ab903541e7e213ee312c565be73547bb3cc8c142486999717e3edeca",
    "claude methods/_m2_codex_implementation_20260910/staging_runs/ths_v2_20260910_041710_97ef9c09/run_ths_v2_20260910_041710_97ef9c09/history.sqlite3": "eda17434ab67496c33eed275b35045c140bad72802b4dcbf981ff22422c53003",
    "backend/.venv/Lib/site-packages/akshare/file_fold/calendar.json": "f1f1ce33c5cceb5c530c3271fc951405cb5624d2f30becec85dc7a85fd47e656",
    "claude methods/_m1_closure/pilot_symbols.csv": "97e251ae84fc927486127a96b4966ed8fc59fac0b744b7d6f186b2b1548886fe",
    "claude methods/_m3_20260910/codex/metadata_index_01/index.json": "14f1bad7d393b4e15bf73111a9d96a78c8b156784f9ccbb084d6b606d3a152e9",
    "claude methods/_m3_20260910/codex/M3_02_WORKING_BOUNDARY_FEEDBACK.md": "e39ac4292af4c3bf916fe1c054379ab3cfe3f57dde9996d252afc97977ec9a65",
    "claude methods/_m3_20260910/codex/M3_02_WORKING_PACKET_CUTOFF_FEEDBACK.md": "addaf3e136a996bcbdf4e2a772aee2e30ec7d8b9e4809df64546cd1e13108280",
    "claude methods/_m3_20260910/codex/audit_working_packet_cutoffs.py": "70daebb68354f0506e1097b34f033d3f122439a81504e777358be53aa58b3c8b",
    "claude methods/_m3_20260910/codex/reader_working_packet_cutoff_audit_01/result.json": "0b3f86e71f98a492a855a7a8ab04c5d1d0a1523c828d6cdfbdfcfba6172e872e",
    "claude methods/_m3_20260910/codex/test_independent_reader_boundary.py": "32c881182a508f32e6e589be8ff65d28e1a7a96b094e49a18fde2a554fa02cac",
    "claude methods/_m3_20260910/codex/reader_working_boundary_tests_01/execution.json": "db573288f722c12be56dd427d0bb265050e04c0ad9d0438c44aace92f8f275cb",
}


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    run_name = sys.argv[1] if len(sys.argv) > 1 else "dev_run_01"
    run_dir = HERE / "runs" / run_name
    receipt = json.loads((run_dir / "run_receipt.json").read_text(encoding="utf-8"))
    transcript = json.loads((run_dir / "real_run_transcript.json").read_text(encoding="utf-8"))
    verify = json.loads((run_dir / "verify_run_result.json").read_text(encoding="utf-8")) if (run_dir / "verify_run_result.json").is_file() else None
    earlier = {}
    for name in sorted(p.name for p in (HERE / "runs").iterdir() if p.is_dir() and p.name != run_name):
        rc = json.loads((HERE / "runs" / name / "run_receipt.json").read_text(encoding="utf-8"))
        earlier[name] = {"reader_sha256": rc["reader_sha256"], "reader_version": rc["reader_version"], "status": rc["status"],
                         "records_generated": rc.get("records_generated"), "retained_as": "earlier attempt / pre-feedback evidence; not the final run"}
    manifest: dict = {
        "schema": "m3.claude_02.artifact_manifest.v1", "task_id": "M3-02-FROZEN-READER-20260910", "status": "ready_for_review",
        "final_run": run_name, "earlier_runs_retained": earlier,
        "in_task_feedback_incorporated": ["claude methods/_m3_20260910/codex/M3_02_WORKING_BOUNDARY_FEEDBACK.md (e39ac429…)",
                                          "claude methods/_m3_20260910/codex/M3_02_WORKING_PACKET_CUTOFF_FEEDBACK.md (addaf3e1…)"],
        "owner": "Claude (existing ZK-trading / Fable 5.1 project advice fork)", "accepted_by_codex": False, "run_name": run_name,
        "policy": {"namespace": "m3.labels", "policy_id": "m3_label_policy", "policy_version": receipt["policy_version"], "policy_hash": receipt["policy_hash"],
                   "labels_module_sha256": receipt["labels_sha256"], "freeze": "claude methods/_m3_20260910/policy_freeze.json"},
        "reader_sha256": receipt["reader_sha256"], "cutoff": {"mode": receipt["cutoff_mode"], "convention": receipt["cutoff_convention"]},
        "development": receipt["development"], "price_consumption_max_date": receipt["price_consumption_max_date"],
        "database_connections": transcript["connections"], "denied_actions": transcript["denied_actions"],
        "sources_unchanged_after_run": transcript["sources_unchanged"], "run_status": receipt["status"],
        "records_generated": receipt["records_generated"], "waterfall": receipt["waterfall"], "verify_run": verify,
        "written": {}, "sources_read": {}, "preserved_originals": {},
        "safety": {"review_only": True, "live_trading_enabled": False, "strict_pit": False, "training_eligible": False, "production_sqlite_connections": 0,
                   "network_requests": 0, "subprocesses": 0, "held_out_prices_consumed": False, "real_reviews": 0, "independently_reviewed_positives": 0,
                   "git_mutations": 0, "py_compile_used": False, "universe_expanded": False, "thresholds_tuned": False},
    }
    for rel in ("backend/app/research/m3_frozen_reader.py", "backend/tests/test_m3_frozen_reader.py"):
        p = PROJECT / rel
        manifest["written"][rel] = {"sha256": sha(p), "bytes": p.stat().st_size, "new_file": True}
    for p in sorted(HERE.rglob("*")):
        if p.is_file() and p.name != "artifact_manifest.json" and "scratch" not in p.parts:
            manifest["written"][p.relative_to(PROJECT).as_posix()] = {"sha256": sha(p), "bytes": p.stat().st_size}
    for rel in SOURCES_READ:
        p = PROJECT / rel
        manifest["sources_read"][rel] = {"sha256": sha(p), "bytes": p.stat().st_size} if p.is_file() else {"missing": True}
    for rel, expected in PRESERVED.items():
        p = PROJECT / rel
        actual = sha(p) if p.is_file() else None
        manifest["preserved_originals"][rel] = {"sha256": actual, "expected": expected, "match": actual == expected}
    data = (json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    (HERE / "artifact_manifest.json").write_bytes(data)
    print("written", len(manifest["written"]), "sources", len(manifest["sources_read"]), "missing", sum(1 for v in manifest["sources_read"].values() if v.get("missing")),
          "preserved", all(v["match"] for v in manifest["preserved_originals"].values()))
    print("manifest_sha256", hashlib.sha256(data).hexdigest())
    return 0


if __name__ == "__main__":
    sys.exit(main())
