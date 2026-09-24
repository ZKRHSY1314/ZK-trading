"""Read-only final evidence replay and immutable handoff inventory, no SQLite."""
from datetime import datetime, timezone
from pathlib import Path
import json
import contract_v2 as c

HERE = c.HERE
RUN = "ths_v2_20260910_041710_97ef9c09"
ROOT = HERE / "staging_runs" / RUN
R = ROOT / ("run_" + RUN)
A = HERE / "contract_v2_runs" / RUN


def main():
    bundle, rows = c.build()
    c.require(bundle == c.read(HERE / "qualification_v2_reviewed.json"), "final_source_replay_disagrees")
    complete = c.read(A / "completion.json")
    c.require(complete["status"] == "staging_v2_published" and c.sha(ROOT / "CURRENT.json") == complete["pointer_sha256"], "published_state_changed")
    c.require(c.guard.check_production(c.guard.production_contract())["passed"], "production_changed_after_publication")
    c.require(c.read(HERE / "preservation_after_v2_staging.json")["passed"], "final_preservation_not_passed")
    for mode, pin in complete["gate_receipt_sha256"].items():
        c.require(c.sha(R / (mode + "_receipt.json")) == pin, "gate_receipt_changed")
    test = dict(schema="m2.v2.focused_test_observation.v1", recorded_at_utc=datetime.now(timezone.utc).isoformat(),
        method="Codex observed completed exec tool output; raw terminal stream not separately saved",
        command="backend/.venv/Scripts/python.exe -X utf8 -B -m unittest -v test_contract_v2 test_run_actual_staging",
        cwd=str(HERE), exit_code=0, tests=9, failures=0,
        exact_source_sha256={n:c.sha(HERE/n) for n in ("test_contract_v2.py","test_run_actual_staging.py","contract_v2.py","staging_v2.py","run_actual_staging.py")},
        actual_tamper_run="test_v2_20260910_041620_5f1eafd6", production_modified=False)
    c.old.StagingRun._json_new(HERE / "v2_focused_test_observation.json", test)
    files = [*R.iterdir(), ROOT / "CURRENT.json", *A.iterdir(),
        *[HERE/n for n in ("contract_v2.py","staging_v2.py","run_staging_v2.py","test_contract_v2.py",
            "verify_preservation_v2.py","preservation_after_v2_staging.json","v2_focused_test_observation.json",
            "qualification_v2_reviewed.json","acceptance_v2_authority.json","M2_ACCEPTANCE_REVISION_PROPOSAL.md","PLAN.md")],
        HERE / "contract_v2_runs/test_v2_20260910_041620_5f1eafd6/completion.json",
        HERE.parent / "M2_TONGHUASUN_V2_CODEX_ACCEPTANCE_20260910.md",
        HERE.parent / "M2_TONGHUASUN_V2_CLAUDE_REVIEW_TASK_20260910.md", Path(__file__)]
    inventory = {str(p.resolve()):dict(sha256=c.sha(p), bytes=p.stat().st_size) for p in files if p.is_file()}
    result = dict(schema="m2.ths.v2_delivery_manifest.v1", generated_at_utc=datetime.now(timezone.utc).isoformat(),
        run_id=RUN, run_dir=str(R), state="ready_for_claude_independent_review", artifacts=inventory,
        transitive_evidence_pins=bundle["input_pins"], retained_source_replay_verified=True,
        row_records_sha256=c.value_sha(rows), row_count=len(rows), production_preserved=True,
        live_trading=False, production_promoted=False, strict_pit=False, M2_complete=False)
    c.old.StagingRun._json_new(HERE / "v2_delivery_manifest.json", result)
    print(json.dumps(dict(artifacts=len(inventory), transitive_inputs=len(bundle["input_pins"]), rows=len(rows),
        manifest_sha256=c.sha(HERE / "v2_delivery_manifest.json")), ensure_ascii=False))


if __name__ == "__main__":
    main()
