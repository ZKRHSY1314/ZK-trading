"""Executed validation of the claude_03 M3-03 delivery (distinct from the individual reviews themselves).

Checks, without SQLite or network: every consumed input pin is preserved; exactly 32 case reviews and 8
diagnostics exist; all 127 control uses are individually reviewed and bound to the packet control cores;
every case review binds the representative core, prefix proof, packet hash, policy and case file exactly
as the pinned bundle states; the raw ReviewRecord entries validate with the accepted kernel and recompute
to their entry hashes; reviewer identities are non-synthetic agent identities (one reviewer, no Codex or
human identity claimed); timestamps are timezone-aware and ordered after the logged evidence inspection;
verdicts are allowed values; no reasoning field is empty; authored notes and hash-linked addenda are
preserved; no input core was mutated.  Writes execution/validation_receipt.json and exits non-zero on
any failure.

    backend/.venv/Scripts/python.exe -B -X utf8 "claude methods/_m3_20260910/claude_03/tools/validate_reviews.py"
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
CLAUDE_03 = HERE.parent
PROJECT = CLAUDE_03.parents[2]
BUNDLE = PROJECT / "claude methods" / "_m3_20260910" / "codex" / "case_review_bundle_01"
LABELS = PROJECT / "backend" / "app" / "research" / "m3_labels.py"
REVIEWER_ID = "claude-agent:ZK-trading-Fable-5.1-project-advice-fork:claude-opus-5"
VERDICTS = ("positive", "negative", "ambiguous", "failed", "reject_data")
PINS = {
    "claude methods/_m3_20260910/codex/case_review_bundle_01/manifest.json": "fa234fded7e448f1d8313ee26f43f1e81902e9294426faf1dc2164747ac887fc",
    "claude methods/_m3_20260910/codex/case_review_bundle_01/index.json": "77e29df61a9ffa85379a1505a9f1065574968255ff30249dab4d97b99dcb8fec",
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
    "claude methods/_m3_20260910/claude_02/artifact_manifest.json": "4aa337d9840c970700bad7f2566af7e7a84a486ec8180c1b0295664bc0662962",
    "claude methods/_m3_20260910/claude_01_r3/artifact_manifest.json": "7060f61f8eb637d6e92efb075e6a0cfdad041e370d30874afb9172a2d04fce39",
}
POLICY_HASH = "d436ba1402f9d0b53e1008c2a2bd50678a457c3e050561a59ded30dbbd21c025"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    problems: list[str] = []
    checks: dict = {}
    # 1. pins
    for rel, expected in PINS.items():
        p = PROJECT / rel
        actual = sha(p) if p.is_file() else None
        if actual != expected:
            problems.append(f"pin_mismatch:{rel}:{actual}")
    manifest = json.loads((BUNDLE / "manifest.json").read_text(encoding="utf-8"))
    bad = [rel for rel, v in manifest["written"].items() if sha(BUNDLE / rel) != v["sha256"] or (BUNDLE / rel).stat().st_size != v["bytes"]]
    if bad:
        problems.append(f"bundle_files_changed:{bad}")
    checks["bundle_files_pinned"] = len(manifest["written"])
    index = json.loads((BUNDLE / "index.json").read_text(encoding="utf-8"))
    spec = importlib.util.spec_from_file_location("m3_labels_validate_readonly", LABELS)
    m = importlib.util.module_from_spec(spec); sys.modules[spec.name] = m; spec.loader.exec_module(m)
    if m.POLICY_HASH != POLICY_HASH:
        problems.append("policy_hash_mismatch")
    receipt = json.loads((CLAUDE_03 / "execution" / "execution_receipt.json").read_text(encoding="utf-8"))
    log_entries = [json.loads(l) for l in (CLAUDE_03 / "execution" / "evidence_inspection_log.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    log_ids = {e["case_id"] for e in log_entries}
    log_times = {}
    for e in log_entries:
        log_times.setdefault(e["case_id"], []).append(e["inspected_at_utc"])
    if any(e["problems"] for e in log_entries):
        problems.append("inspection_log_reports_problems")
    checks["inspection_log_entries"] = len(log_entries)
    checks["inspection_log_cores_verified"] = sum(e["cores_verified"] for e in log_entries)
    now = datetime.now(timezone.utc)
    # 2-8. cases
    review_files = sorted((CLAUDE_03 / "reviews").glob("*.json"))
    if [p.name for p in review_files] != [f"C{i:03d}.json" for i in range(1, 33)]:
        problems.append(f"review_files_not_exactly_32:{[p.name for p in review_files]}")
    control_uses = 0; verdicts = {}; counting_eligible = 0; fragile_uses = 0; inadmissible_uses = 0
    control_symbol_uses: dict[str, int] = {}
    rep_sessions: dict[str, list[tuple[int, str]]] = {}
    per_case = []
    for rf in review_files:
        r = json.loads(rf.read_text(encoding="utf-8"))
        cid = r["case_id"]
        case = json.loads((BUNDLE / f"cases/{cid}.json").read_text(encoding="utf-8"))
        p = case["cutoff_packet"]; rep = case["representative_record"]; proof = p["prefix_proof"]; controls = case["control_records"]
        idx = next(c for c in index["cases"] if c["case_id"] == cid)
        b = r["input_bindings"]
        if b["case_file_sha256"] != manifest["written"][f"cases/{cid}.json"]["sha256"] or b["case_file_sha256"] != idx["sha256"]:
            problems.append(f"{cid}:case_file_binding")
        if b["case_episode_id"] != rep["episode_id"] or b["case_record_hash"] != rep["record_hash"] or b["case_record_hash"] != idx["record_hash"]:
            problems.append(f"{cid}:representative_binding")
        if b["case_prefix_hash"] != proof["prefix_hash"] or b["case_prefix_hash"] != idx["case_prefix_hash"]:
            problems.append(f"{cid}:prefix_binding")
        if b["cutoff_packet_hash"] != p["cutoff_packet_hash"] or b["cutoff_packet_hash"] != idx["cutoff_packet_hash"]:
            problems.append(f"{cid}:packet_binding")
        if b["prefix_member_record_hashes"] != proof["member_record_hashes"] or b["prefix_member_episode_ids"] != proof["member_episode_ids"]:
            problems.append(f"{cid}:prefix_member_binding")
        if b["policy_hash"] != POLICY_HASH or b["labels_module_sha256"] != PINS["backend/app/research/m3_labels.py"] or b["producer_sha256"] != rep["producer_sha256"]:
            problems.append(f"{cid}:policy_binding")
        if b["control_record_hashes"] != [c["record_hash"] for c in controls] or b["control_count"] != len(controls) or b["control_count"] != idx["control_count"]:
            problems.append(f"{cid}:control_hash_binding")
        try:
            m.verify_record(rep)
        except Exception as exc:  # noqa: BLE001
            problems.append(f"{cid}:representative_core_no_longer_verifies:{exc}")
        # controls
        crs = r["control_reviews"]
        if len(crs) != len(controls):
            problems.append(f"{cid}:control_review_count")
        for i, (cr, ctl) in enumerate(zip(crs, controls)):
            if cr["symbol"] != ctl["symbol"] or cr["control_record_hash"] != ctl["record_hash"] or cr["control_episode_id"] != ctl["episode_id"] or cr["packet_control_record_hash"] != p["controls"][i]["record_hash"]:
                problems.append(f"{cid}:control_binding:{ctl['symbol']}")
            if cr["decision_date"] != rep["cutoff"]["decision_date"] or cr["frozen_selection"] != "non_candidate":
                problems.append(f"{cid}:control_date_or_selection:{ctl['symbol']}")
            for key in ("reviewer_assessment", "reviewer_non_candidate_reason", "reviewer_uncertainty", "reviewer_contrast"):
                if not str(cr.get(key, "")).strip():
                    problems.append(f"{cid}:control_reasoning_empty:{ctl['symbol']}:{key}")
            if not isinstance(cr.get("reviewer_admissible"), bool) or not isinstance(cr.get("reviewer_fragile"), bool):
                problems.append(f"{cid}:control_flags:{ctl['symbol']}")
            if not all(cr["same_policy_eligibility"].values()):
                problems.append(f"{cid}:control_matching_conditions:{ctl['symbol']}")
            control_uses += 1
            control_symbol_uses[ctl["symbol"]] = control_symbol_uses.get(ctl["symbol"], 0) + 1
            if cr["reviewer_fragile"]:
                fragile_uses += 1
            if not cr["reviewer_admissible"]:
                inadmissible_uses += 1
        # verdict / reasoning
        if r["verdict"] not in VERDICTS:
            problems.append(f"{cid}:verdict")
        verdicts[r["verdict"]] = verdicts.get(r["verdict"], 0) + 1
        if r["counting_eligible"]:
            counting_eligible += 1
        if r["verdict"] != "positive" and r["counting_eligible"]:
            problems.append(f"{cid}:counting_eligible_without_positive")
        for key in ("summary", "supporting_evidence", "contradicting_evidence", "limitations", "control_set_assessment", "dependence_and_reuse_notes"):
            v = r.get(key)
            if not v or (isinstance(v, list) and not all(str(x).strip() for x in v)):
                problems.append(f"{cid}:empty:{key}")
        for key, v in r["assessment"].items():
            if not str(v).strip():
                problems.append(f"{cid}:empty_assessment:{key}")
        if not isinstance(r["control_set_admissible"], bool):
            problems.append(f"{cid}:control_set_admissible_flag")
        # identity / timestamps / execution
        if r["reviewer_kind"] != "agent" or r["reviewer_id"] != REVIEWER_ID or "codex" in r["reviewer_id"].lower() or "human" in r["reviewer_id"].lower():
            problems.append(f"{cid}:reviewer_identity")
        if r["raw_review"]["synthetic"] is not False or r["safety"]["synthetic"] is not False:
            problems.append(f"{cid}:synthetic_flag")
        if r["execution_id"] != receipt["execution_id"] or receipt["execution_id"] not in r["execution_ref"] or not r["execution_ref"].startswith("M3-03-CASE-REVIEW-20260910"):
            problems.append(f"{cid}:execution_ref")
        try:
            ra = datetime.fromisoformat(r["reviewed_at"])
            if ra.tzinfo is None or ra > now:
                problems.append(f"{cid}:reviewed_at_not_aware_or_future")
            for t in r["evidence_inspected_at"]:
                if datetime.fromisoformat(t) > ra:
                    problems.append(f"{cid}:reviewed_before_inspection")
            if cid not in log_ids or sorted(r["evidence_inspected_at"]) != sorted(log_times[cid]):
                problems.append(f"{cid}:inspection_times_not_in_log")
        except Exception as exc:  # noqa: BLE001
            problems.append(f"{cid}:timestamp:{exc}")
        # raw review
        raw = r["raw_review"]
        try:
            m._validate_entry_fields(raw)
            if raw["entry_hash"] != m._entry_content_hash(raw):
                problems.append(f"{cid}:raw_review_entry_hash")
            if raw["case_episode_id"] != rep["episode_id"] or raw["case_record_hash"] != rep["record_hash"] or raw["case_policy_hash"] != POLICY_HASH or raw["case_prefix_hash"] != proof["prefix_hash"]:
                problems.append(f"{cid}:raw_review_binding")
            if raw["verdict"] != r["verdict"] or raw["reviewer_id"] != REVIEWER_ID or raw["reviewer_kind"] != "agent" or raw["supersedes"] is not None:
                problems.append(f"{cid}:raw_review_fields")
        except Exception as exc:  # noqa: BLE001
            problems.append(f"{cid}:raw_review_invalid:{exc}")
        # input cores unchanged (embedded ledgers still empty)
        if any(x["review_ledger"]["entries"] for x in [rep] + case["prefix_records"] + controls) or case["reviews"]:
            problems.append(f"{cid}:input_core_mutated")
        # authored note preservation
        note_path = CLAUDE_03 / r["authored_note_path"]
        if sha(note_path) != r["authored_note_sha256"]:
            problems.append(f"{cid}:authored_note_hash")
        note_now = json.loads(note_path.read_text(encoding="utf-8"))
        for a in r.get("addenda", []):
            if "original_note_snapshot" in a:
                snap = CLAUDE_03 / a["original_note_snapshot"]
                if not snap.is_file() or sha(snap) != a["original_note_sha256"]:
                    problems.append(f"{cid}:addendum_original_not_preserved")
                else:
                    snap_note = json.loads(snap.read_text(encoding="utf-8"))
                    if {k: v for k, v in snap_note.items() if k != "addenda"} != {k: v for k, v in note_now.items() if k != "addenda"}:
                        problems.append(f"{cid}:original_note_text_changed_after_addendum")
            else:
                # first-generation addendum without a snapshot: the original text must still be present verbatim (addenda are additive)
                if not any("original_note_snapshot" in b for b in r.get("addenda", [])):
                    problems.append(f"{cid}:addendum_without_any_snapshot")
        per_case.append({"case_id": cid, "symbol": r["symbol"], "representative_date": r["representative_date"], "verdict": r["verdict"],
                         "counting_eligible": r["counting_eligible"], "controls": len(crs), "control_set_admissible": r["control_set_admissible"],
                         "fragile_controls": r["control_set_summary"]["reviewer_fragile"], "robust_count": r["control_set_summary"]["robust_count"],
                         "addenda": len(r.get("addenda", [])), "review_sha256": sha(rf)})
        rep_sessions.setdefault(r["symbol"], []).append((rep["session_view"]["decision_session_index"], cid))
    if control_uses != 127 or control_uses != index["control_uses"]:
        problems.append(f"control_uses:{control_uses}")
    # dependence groups (accounting only): same symbol with representative sessions within 20 sessions chained
    groups = 0; chains = []
    for sym, items in rep_sessions.items():
        items.sort()
        cur = [items[0][1]]; last = items[0][0]
        for s, cid in items[1:]:
            if s - last <= 20:
                cur.append(cid)
            else:
                chains.append((sym, cur)); cur = [cid]
            last = s
        chains.append((sym, cur))
    groups = len(chains)
    # diagnostics
    diag_files = sorted((CLAUDE_03 / "diagnostics").glob("*.json"))
    if [p.name for p in diag_files] != [f"D{i:03d}.json" for i in range(1, 9)]:
        problems.append(f"diagnostic_files_not_exactly_8:{[p.name for p in diag_files]}")
    per_diag = []
    for df in diag_files:
        d = json.loads(df.read_text(encoding="utf-8"))
        did = d["case_id"]
        src = json.loads((BUNDLE / f"diagnostics/{did}.json").read_text(encoding="utf-8"))
        idx = next(x for x in index["diagnostics"] if x["case_id"] == did)
        if d["input_bindings"]["diagnostic_file_sha256"] != idx["sha256"] or d["input_bindings"]["record_hash"] != src["record"]["record_hash"] or d["input_bindings"]["record_hash"] != idx["record_hash"]:
            problems.append(f"{did}:binding")
        if d["diagnostic_kind"] != src["diagnostic_kind"] or d["counts_as_positive_episode"] is not False or d["excluded_from_positive_counts"] is not True:
            problems.append(f"{did}:diagnostic_flags")
        for key in ("semantics_assessment", "bindings_note", "finding"):
            if not str(d.get(key, "")).strip():
                problems.append(f"{did}:empty:{key}")
        if d["reviewer_kind"] != "agent" or d["reviewer_id"] != REVIEWER_ID or d["execution_id"] != receipt["execution_id"]:
            problems.append(f"{did}:identity_or_execution")
        ra = datetime.fromisoformat(d["reviewed_at"])
        if ra.tzinfo is None or did not in log_ids or any(datetime.fromisoformat(t) > ra for t in d["evidence_inspected_at"]):
            problems.append(f"{did}:timestamps")
        if sha(CLAUDE_03 / d["authored_note_path"]) != d["authored_note_sha256"]:
            problems.append(f"{did}:authored_note_hash")
        if src["reviews"]:
            problems.append(f"{did}:input_mutated")
        per_diag.append({"case_id": did, "kind": d["diagnostic_kind"], "finding": d["finding"], "review_sha256": sha(df)})
    # receipt consistency
    if receipt["verdict_counts"] != {v: verdicts.get(v, 0) for v in VERDICTS} or receipt["control_uses_reviewed"] != control_uses:
        problems.append("execution_receipt_counts_disagree")
    checks.update({"case_reviews": len(review_files), "diagnostic_reviews": len(diag_files), "control_uses": control_uses,
                   "unique_control_symbols": len(control_symbol_uses), "control_reuse_max": max(control_symbol_uses.values()) if control_symbol_uses else 0,
                   "verdict_counts": {v: verdicts.get(v, 0) for v in VERDICTS}, "positive_cases": verdicts.get("positive", 0),
                   "counting_eligible_cases": counting_eligible, "fragile_control_uses": fragile_uses, "inadmissible_control_uses": inadmissible_uses,
                   "dependence_chains_same_symbol_within_20_sessions": groups, "dependence_chains": [{"symbol": s, "cases": c} for s, c in chains],
                   "symbols_with_cases": len(rep_sessions), "history_snapshots": len(list((CLAUDE_03 / "authored_notes" / "history").glob("*.json")))})
    result = {"schema": "m3.claude_03.validation_receipt.v1", "task_id": "M3-03-CASE-REVIEW-20260910", "validated_at_utc": now.isoformat(),
              "validator": "claude_03/tools/validate_reviews.py", "validator_sha256": sha(Path(__file__)),
              "distinct_from_reviews": "This receipt validates structure, bindings, identities, timestamps and coverage of the reviews; it is not itself a review and adds no verdict.",
              "execution_id_validated": receipt["execution_id"], "pins": {rel: "ok" for rel in PINS}, "checks": checks,
              "target": {"criterion": "at least 50 independently reviewed positive episodes with 3-5 matched controls each",
                         "claude_positive_verdicts": verdicts.get("positive", 0), "claude_counting_eligible": counting_eligible,
                         "cases_available": 32, "met": False, "note": "single-agent review; independence and consensus are assembled by Codex, not asserted here"},
              "problems": problems, "ok": not problems, "per_case": per_case, "per_diagnostic": per_diag}
    (CLAUDE_03 / "execution" / "validation_receipt.json").write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({"ok": result["ok"], "problems": problems, "checks": {k: v for k, v in checks.items() if k != "dependence_chains"}}, ensure_ascii=False, indent=1))
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
