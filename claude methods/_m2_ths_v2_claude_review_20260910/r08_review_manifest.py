"""R08 - manifest of every input consulted and every output produced by this review.

Hashes files only. Writes review_manifest.json in this directory. Run last.
"""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CM = HERE.parent
PROJECT = CM.parent
PHASE = CM / "_m2_codex_implementation_20260910"
RUN_ID = "ths_v2_20260910_041710_97ef9c09"
RUN = PHASE / "staging_runs" / RUN_ID / f"run_{RUN_ID}"

INPUTS = [
    CM / "M2_TONGHUASUN_V2_CLAUDE_REVIEW_TASK_20260910.md",
    CM / "M2_TONGHUASUN_V2_CODEX_ACCEPTANCE_20260910.md",
    CM / "THREE_YEAR_RESEARCH_EXECUTION_GOAL.md",
    PROJECT / "AGENTS.md", PROJECT / "CODEX_CLAUDE_COLLABORATION.md",
    PHASE / "v2_delivery_manifest.json", PHASE / "acceptance_v2_authority.json",
    PHASE / "M2_ACCEPTANCE_REVISION_PROPOSAL.md", PHASE / "qualification_v2_reviewed.json",
    PHASE / "qualification_pilot52.json", PHASE / "pilot52_blocker_review_v3.json",
    PHASE / "contract_v2.py", PHASE / "staging_v2.py", PHASE / "run_staging_v2.py",
    PHASE / "verify_preservation_v2.py", PHASE / "staging.py", PHASE / "run_actual_staging.py",
    PHASE / "qualification_pilot_rules.py", PHASE / "test_contract_v2.py", PHASE / "test_run_actual_staging.py",
    PHASE / "v2_focused_test_observation.json", PHASE / "unit_anchor_evidence.json",
    PHASE / "unit_semantics_static_review.md", PHASE / "preservation_after_v2_staging.json",
    PHASE / "baseline/production_files_before.json",
    PHASE / "gap_evidence/bse_trading_explanation_browser_20211119.pdf",
    PHASE / "gap_evidence/bse_trading_explanation_browser_20211119.receipt.json",
    PHASE / "gap_evidence/exchange_dom_observations_20260910.json",
    PHASE / "qualification_capture/plan.json",
    PHASE / "staging_runs" / RUN_ID / "CURRENT.json",
    RUN / "candidate.json", RUN / "contract_v2.json", RUN / "research_receipt.json",
    RUN / "warmup_collection_receipt.json", RUN / "research_original_gate.json",
    RUN / "warmup_collection_original_gate.json", RUN / "trading.sqlite3", RUN / "history.sqlite3",
    PHASE / "contract_v2_runs" / RUN_ID / "completion.json",
    PHASE / "contract_v2_runs" / RUN_ID / "before.json",
    PHASE / "contract_v2_runs" / RUN_ID / "after_publication.json",
    PHASE / "contract_v2_runs/test_v2_20260910_041620_5f1eafd6/completion.json",
    PROJECT / "backend/app/data/tonghuasun_history.py",
    PROJECT / "backend/.venv/Lib/site-packages/akshare/file_fold/calendar.json",
    CM / "_m1_closure/pilot_symbols.csv",
]


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    out = {"schema": "m2.ths.v2.claude_review_manifest.v1", "run_id": RUN_ID, "inputs": {}, "outputs": {},
           "sqlite_opened_read_only": [str(RUN / "trading.sqlite3"), str(RUN / "history.sqlite3")],
           "production_databases_opened": [], "network_requests": 0}
    for p in INPUTS:
        out["inputs"][str(p)] = {"sha256": sha(p), "bytes": p.stat().st_size} if p.is_file() else {"missing": True}
    for p in sorted(HERE.iterdir()):
        if p.is_file() and p.name != "review_manifest.json":
            out["outputs"][p.name] = {"sha256": sha(p), "bytes": p.stat().st_size}
    report = CM / "M2_TONGHUASUN_V2_CLAUDE_INDEPENDENT_REVIEW_20260910.md"
    if report.is_file():
        out["report"] = {"path": str(report), "sha256": sha(report), "bytes": report.stat().st_size}
    json.dump(out, open(HERE / "review_manifest.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print("inputs:", len(out["inputs"]), "missing:", sum(1 for v in out["inputs"].values() if v.get("missing")))
    print("outputs:", list(out["outputs"]))
    if "report" in out:
        print("report:", out["report"]["sha256"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
