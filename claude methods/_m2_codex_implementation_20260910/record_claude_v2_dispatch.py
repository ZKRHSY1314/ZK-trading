"""Record the user-authorized, visibly submitted single Claude task."""
from datetime import datetime, timezone
import json
from pathlib import Path
import hashlib

HERE = Path(__file__).resolve().parent
STATE = HERE.parent / "_m2_codex_review/m2_claude_coordination_state.json"


def main():
    old_raw = STATE.read_bytes()
    backup = HERE / "claude_resume_coordination_before.json"
    with backup.open("xb") as handle:
        handle.write(old_raw)
    state = json.loads(old_raw)
    at = datetime.now(timezone.utc).isoformat()
    previous = {k:state.get(k) for k in ("current_task","authorization","prohibitions","state_limits","automation","latest_review","next_action")}
    state.setdefault("codex_claude_resumption_history", []).append(dict(at_utc=at, previous=previous,
        backup=str(backup), backup_sha256=hashlib.sha256(old_raw).hexdigest()))
    state["updated_at_utc"] = at
    state["authorization"] = "User explicitly requested an acceptance document, renewed Claude delegation and 15-minute patrol until M2 completion. Codex completed the approved v2 staging step. Current Claude scope is the exact independent-review instruction file: offline retained evidence plus read-only opens of the two named isolated candidate SQLite files; own new review outputs/synthetic fixtures only. No production promotion, live trading or new capture authority is inferred."
    state["current_task"] = dict(id="M2-THS-V2-INDEPENDENT-REVIEW-20260910", status="submitted_observed_running",
        owner="Fable 5.1 project advice (fork)", instruction_file="claude methods/M2_TONGHUASUN_V2_CLAUDE_REVIEW_TASK_20260910.md",
        allowed_write_scope=["claude methods/M2_TONGHUASUN_V2_CLAUDE_INDEPENDENT_REVIEW_20260910.md", "claude methods/_m2_ths_v2_claude_review_20260910/"],
        allowed_network="none", submitted_at_utc=at, submission_visible=True,
        observed_status="Claude UI Message 42 contains task ID and exact manifest pin; sole fork Running, Claude is responding, Stop button; Ran 3 commands visible. Prior Message 41 is completed; other sessions Idle. No user draft overwritten.",
        manifest="claude methods/_m2_codex_implementation_20260910/v2_delivery_manifest.json",
        manifest_sha256="eca6bea3c47ef0d37573f4b20d10d6ffe7956738a98118b7298e703142f7154e",
        candidate_run_id="ths_v2_20260910_041710_97ef9c09", completion_observed=False)
    state["last_ui_observation"] = dict(at_utc=at, window_id=264394, app="Claude_pzs8sxrjxfjjc!Claude",
        status="submitted_observed_running", message=42, evidence=state["current_task"]["observed_status"])
    state["latest_review"] = dict(report="claude methods/M2_TONGHUASUN_V2_CODEX_ACCEPTANCE_20260910.md",
        verdict="codex_self_validation_passed_pending_claude_independent_review", at_utc=at,
        run_id="ths_v2_20260910_041710_97ef9c09", rows_per_view=45685, suspension_records=298, M2_complete=False)
    state["state_limits"] = dict(legacy_sina_capability="FAIL_with_EV6_preserved", tonghuasun_long_history="actual_52_security_capture_and_v2_staging_validated_pending_independent_review",
        v2_dataset_state="ready_for_review", original_contract="FAIL_preserved", strict_pit=False,
        listing_depth_shortfalls=14, U6="deferred_not_implicitly_completed", production_promoted=False, live_trading=False, M2_complete=False)
    state["prohibitions"] = ["production SQLite opens/writes or promotion", "live trading, broker/account/fund/credential access",
        "new source capture or service/client operations in current Claude task", "in-place edits of pinned code/evidence/candidates/pointer",
        "unapproved threshold/policy changes, training, Git staging/commit/push", "duplicate workers or Claude-controlled automation/email"]
    state["next_action"] = "Inspect the sole running Claude task at 15-minute intervals. Do not resend while running. Review stable delivery against exact inputs and full M2 definition; integrate or issue a precise new corrective write scope for substantive blockers. Preserve all frozen versions. Pause the existing heartbeat only when M2 is verified complete or a genuine unavoidable block is documented."
    state["codex_takeover"]["claude_dispatch_enabled"] = True
    state["coordination_speedup"] = dict(interval_minutes=15, requested_by="User explicit 2026-09-10 request to resume Claude and patrol every 15 min until M2 complete",
        rules="Verify changed stable artifacts and actual UI before dispatch; same-round substantive review/correction; no duplicate writers or style-only rounds.")
    state["automation"] = dict(id="claude", status="update_pending", interval_minutes=15,
        target_thread_id="01a086db-3c02-7a21-bf22-26e4f73e24b0", previous_configuration_preserved_in_history=True)
    tmp = STATE.with_name("m2_claude_coordination_state.v2.tmp")
    if tmp.exists():
        raise RuntimeError("coordination temp already exists")
    with tmp.open("x", encoding="utf-8") as handle:
        json.dump(state,handle,ensure_ascii=False,indent=2)
    if STATE.read_bytes() != old_raw:
        raise RuntimeError("coordination changed during update")
    tmp.replace(STATE)
    print(json.dumps({"task":state["current_task"]["id"],"status":state["current_task"]["status"]}))


if __name__ == "__main__":
    main()
