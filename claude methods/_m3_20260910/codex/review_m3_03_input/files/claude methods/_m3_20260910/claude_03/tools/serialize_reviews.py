"""Serialize the reviewer's authored notes into bound review records (M3-03, claude_03).

This script does not judge anything.  It (1) re-checks the bundle pins, (2) loads each authored note
(authored_notes/C0xx.json, authored_notes/diagnostics.json) that the reviewer wrote after reading the
dossiers, (3) binds it to the exact input hashes (case file, packet, representative core, prefix proof,
control cores, policy), (4) attaches the reviewer identity, timezone-aware timestamps and the execution
reference, (5) derives a ReviewRecord-compatible raw entry with the accepted kernel (no core is mutated),
and (6) writes reviews/C0xx.json and diagnostics/D00x.json plus execution/execution_receipt.json.

It refuses to serialize a case whose authored control list does not cover the packet's controls exactly,
whose verdict is not an allowed value, or whose reasoning fields are empty.

Generation 2 (after codex/M3_03_SERIALIZED_EFFECTIVE_TEXT_FEEDBACK.md): where an authored note carries an
``effective`` block (path-keyed replacement text written by the reviewer to incorporate the hash-linked addenda),
the serialized *current* text and ``raw_review.notes`` use the effective text; the original authored text for every
replaced path is emitted alongside under ``original_authored_text`` and the pre-edit note is preserved by hash under
authored_notes/history/.  The generation-1 serialization is preserved under execution/superseded_draft_01/ and is
not referenced through a raw ``supersedes`` field because it was never attached to any ledger.

    backend/.venv/Scripts/python.exe -B -X utf8 "claude methods/_m3_20260910/claude_03/tools/serialize_reviews.py"
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
CLAUDE_03 = HERE.parent
PROJECT = CLAUDE_03.parents[2]
BUNDLE = PROJECT / "claude methods" / "_m3_20260910" / "codex" / "case_review_bundle_01"
LABELS = PROJECT / "backend" / "app" / "research" / "m3_labels.py"
LABELS_SHA256 = "e20eb21cdea032ced319a8f45a34cdeb03fd4d8b357ac31403306fa73b225393"
POLICY_HASH = "d436ba1402f9d0b53e1008c2a2bd50678a457c3e050561a59ded30dbbd21c025"
BUNDLE_MANIFEST_SHA256 = "fa234fded7e448f1d8313ee26f43f1e81902e9294426faf1dc2164747ac887fc"
BUNDLE_INDEX_SHA256 = "77e29df61a9ffa85379a1505a9f1065574968255ff30249dab4d97b99dcb8fec"
TASK_ID = "M3-03-CASE-REVIEW-20260910"
SESSION_ID = "a4a3be61-cd46-4bdf-9381-23d97fee303a"
REVIEWER_ID = "claude-agent:ZK-trading-Fable-5.1-project-advice-fork:claude-opus-5"
REVIEWER_KIND = "agent"
REVIEWER_DESCRIPTION = ("Claude (Opus 5) agent reviewer running in the existing 'ZK-trading / Fable 5.1 project advice (fork)' "
                        "Claude Code session; the sole reviewer in this delivery. This is an agent review, not a human review, "
                        "and not a Codex review.")
VERDICTS = ("positive", "negative", "ambiguous", "failed", "reject_data")
NOTES = CLAUDE_03 / "authored_notes"
LOG = CLAUDE_03 / "execution" / "evidence_inspection_log.jsonl"
PROVENANCE_CLARIFICATION = (
    "Provenance display clarification (codex/M3_03_PROVENANCE_DISPLAY_CLARIFICATION.md, sha256 1bb8cb29...): the core field "
    "provenance.source_refs and the packet's price_context first/last_consumed_source_ref / consumed_observation_keys are the sorted "
    "set union of stock and benchmark locators built by the accepted m3_labels.py line 1585; they are not a stock-only range and their "
    "earliest locator may belong to the benchmark. Stock-only consumption is input_availability.rows_consumed / features.bars_available; "
    "benchmark consumption is benchmark_availability.rows_consumed. Where an authored note quotes a locator range, that reading applies."
)
SERIALIZATION_GENERATION = 2
SUPERSEDED_DRAFT = {
    "path": "execution/superseded_draft_01/",
    "status_file": "execution/superseded_draft_01/DRAFT_STATUS.json",
    "draft_execution_id": "63ade8b0-7150-46cb-ad5e-7ff1aa9af6a5",
    "reason": ("Generation-1 serialization copied the original authored text into the current fields and raw_review.notes, so withdrawn "
               "wording (e.g. C016 'new 250-session lows', C031 future-markup assertion) remained visible although hash-linked addenda "
               "had corrected it; superseded per codex/M3_03_SERIALIZED_EFFECTIVE_TEXT_FEEDBACK.md sha256 "
               "61215ecf8aa1c3e2f6e8658d279e269cb6a81153b4f563090e18d8fa08967b7b. Verdicts, dispositions' meaning and control "
               "admissibility are unchanged between the generations."),
    "raw_supersedes_reference": None,
    "raw_supersedes_note": "The draft raw_review entries were never attached to a ledger, so there is nothing to supersede at ledger level; the draft is preserved by hash only.",
}
REVIEWED_AT_SEMANTICS = (
    "reviewed_at is the actual sealing/binding time: the UTC instant at which serialize_reviews.py bound this review to its input hashes and "
    "sealed the record in the execution referenced by execution_ref. It is not the time the evidence was inspected or the note was authored. "
    "The real review sequence is established by evidence_inspected_at (from execution/evidence_inspection_log.jsonl), by the authored note's "
    "addenda authored_at_utc values and pre-addendum snapshots under authored_notes/history/, and by effective_text_applied.authored_at_utc."
)


def apply_effective(note: dict) -> tuple[dict, dict, dict | None]:
    """Overlay note['effective']['fields'] onto a deep copy of the note.

    Returns (effective_note, original_values_by_path, effective_meta).  Paths: top-level string field,
    'assessment.<section>', '<list_field>.<index>', 'control_reviews.<SYMBOL>.<field>'.  Every path must exist
    and the replacement must be a non-empty string that differs from the original.
    """
    eff = copy.deepcopy(note)
    meta = note.get("effective")
    if not meta:
        return eff, {}, None
    originals: dict[str, str] = {}
    for path, new in meta["fields"].items():
        if not isinstance(new, str) or not new.strip():
            raise SystemExit(f"{note['case_id']}: effective field {path} must be a non-empty string")
        parts = path.split(".")
        if parts[0] == "assessment" and len(parts) == 2:
            container, key = eff["assessment"], parts[1]
        elif parts[0] == "control_reviews" and len(parts) == 3:
            container = next(c for c in eff["control_reviews"] if c["symbol"] == parts[1]); key = parts[2]
        elif parts[0] in ("supporting_evidence", "contradicting_evidence", "limitations") and len(parts) == 2:
            container, key = eff[parts[0]], int(parts[1])
        elif len(parts) == 1 and parts[0] in ("summary", "disposition", "control_set_assessment", "dependence_and_reuse_notes"):
            container, key = eff, parts[0]
        else:
            raise SystemExit(f"{note['case_id']}: unsupported effective path {path}")
        old = container[key]
        if not isinstance(old, str):
            raise SystemExit(f"{note['case_id']}: effective path {path} does not address a string")
        if old == new:
            raise SystemExit(f"{note['case_id']}: effective field {path} equals the original")
        originals[path] = old
        container[key] = new
    return eff, originals, meta


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_labels():
    if sha(LABELS) != LABELS_SHA256:
        raise SystemExit("accepted label module hash mismatch")
    spec = importlib.util.spec_from_file_location("m3_labels_serialize_readonly", LABELS)
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    if m.POLICY_HASH != POLICY_HASH:
        raise SystemExit("policy hash mismatch")
    return m


def check_bundle_pins() -> dict:
    manifest = json.loads((BUNDLE / "manifest.json").read_text(encoding="utf-8"))
    if sha(BUNDLE / "manifest.json") != BUNDLE_MANIFEST_SHA256 or sha(BUNDLE / "index.json") != BUNDLE_INDEX_SHA256:
        raise SystemExit("bundle manifest/index pin mismatch")
    bad = [rel for rel, v in manifest["written"].items() if sha(BUNDLE / rel) != v["sha256"]]
    if bad:
        raise SystemExit(f"bundle files changed: {bad}")
    return manifest


def inspection_entries(case_id: str) -> list[dict]:
    entries = []
    for line in LOG.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        e = json.loads(line)
        if e.get("case_id") == case_id:
            entries.append(e)
    return entries


def nonempty(value) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return len(value) > 0 and all(nonempty(v) for v in value)
    if isinstance(value, dict):
        return len(value) > 0 and all(nonempty(v) for v in value.values())
    return value is not None


def serialize_case(m, case_id: str, manifest: dict, execution: dict, out_dir: Path) -> dict:
    rel = f"cases/{case_id}.json"
    case_path = BUNDLE / rel
    case_sha = sha(case_path)
    if case_sha != manifest["written"][rel]["sha256"]:
        raise SystemExit(f"{case_id}: case pin mismatch")
    case = json.loads(case_path.read_text(encoding="utf-8"))
    note_path = NOTES / f"{case_id}.json"
    note_sha = sha(note_path)
    authored = json.loads(note_path.read_text(encoding="utf-8"))
    note, original_text, effective_meta = apply_effective(authored)
    if effective_meta:
        snap = CLAUDE_03 / effective_meta["original_note_snapshot"]
        if not snap.exists() or sha(snap) != effective_meta["original_note_sha256"]:
            raise SystemExit(f"{case_id}: effective-text snapshot missing or hash mismatch")
        if note["verdict"] != authored["verdict"] or note["counting_eligible"] != authored["counting_eligible"] or note["control_set_admissible"] != authored["control_set_admissible"]:
            raise SystemExit(f"{case_id}: effective text must not change verdict/admissibility")
    p = case["cutoff_packet"]; rep = case["representative_record"]; prefix = case["prefix_records"]; controls = case["control_records"]
    proof = p["prefix_proof"]
    # ---- consistency between the authored note and the input
    if note["case_id"] != case_id or note["symbol"] != rep["symbol"] or note["representative_date"] != rep["cutoff"]["decision_date"]:
        raise SystemExit(f"{case_id}: note identity mismatch")
    if note["prefix_dates"] != [r["cutoff"]["decision_date"] for r in prefix]:
        raise SystemExit(f"{case_id}: note prefix dates mismatch")
    if note["verdict"] not in VERDICTS:
        raise SystemExit(f"{case_id}: verdict not allowed: {note['verdict']}")
    for key in ("summary", "assessment", "supporting_evidence", "contradicting_evidence", "limitations", "control_set_assessment", "dependence_and_reuse_notes"):
        if not nonempty(note.get(key)):
            raise SystemExit(f"{case_id}: empty reasoning field {key}")
    required_sections = ("prefix_three_sessions", "representative_selection_eligibility", "threshold_margins_and_competing_signals",
                         "observed_state_and_warmup", "benchmark_regime_liquidity_coverage", "source_asof_provenance_adjustment_units",
                         "unknown_st_float_turnover_corporate_actions", "signal_vs_execution_eligibility")
    for key in required_sections:
        if not nonempty(note["assessment"].get(key)):
            raise SystemExit(f"{case_id}: empty assessment section {key}")
    if not isinstance(note.get("control_set_admissible"), bool) or not isinstance(note.get("counting_eligible"), bool):
        raise SystemExit(f"{case_id}: admissibility/counting flags must be bool")
    authored_controls = {c["symbol"]: c for c in note["control_reviews"]}
    packet_symbols = [c["symbol"] for c in controls]
    if sorted(authored_controls) != sorted(packet_symbols) or len(note["control_reviews"]) != len(controls):
        raise SystemExit(f"{case_id}: authored controls {sorted(authored_controls)} != packet controls {sorted(packet_symbols)}")
    control_reviews = []
    for i, ctl in enumerate(controls):
        a = authored_controls[ctl["symbol"]]
        for key in ("assessment", "non_candidate_reason", "uncertainty", "contrast"):
            if not nonempty(a.get(key)):
                raise SystemExit(f"{case_id}: control {ctl['symbol']} empty {key}")
        if not isinstance(a.get("admissible"), bool):
            raise SystemExit(f"{case_id}: control {ctl['symbol']} admissible must be bool")
        frozen_reasons = ctl["labels"]["selection"]["reasons"]
        control_reviews.append({
            "control_index": i, "symbol": ctl["symbol"], "decision_date": ctl["cutoff"]["decision_date"],
            "control_episode_id": ctl["episode_id"], "control_record_hash": ctl["record_hash"],
            "packet_control_record_hash": p["controls"][i]["record_hash"], "match_control_role": p["match"]["controls"][i]["role"],
            "frozen_phase": ctl["labels"]["phase"]["label"], "frozen_selection": ctl["labels"]["selection"]["label"],
            "frozen_selection_reasons": frozen_reasons, "frozen_liquidity_band": ctl["labels"]["liquidity"]["band"],
            "frozen_regime": ctl["labels"]["regime"]["regime"], "amount_20_mean_cny": ctl["features"]["amount_20_mean_cny"],
            "abs_ln_amount_ratio": next(x["abs_ln_amount_ratio"] for x in p["control_ranking"] if x["symbol"] == ctl["symbol"]),
            "cutoff": ctl["cutoff"], "current_state": ctl["current_state"], "in_frozen_universe": ctl["universe"]["in_frozen_universe"],
            "synthetic": ctl["synthetic"], "role": ctl["role"], "listing_date": ctl["security_context"]["listing_date"],
            "board": ctl["labels"]["limit"]["board"], "bars_available": ctl["features"]["bars_available"],
            "suspensions_in_window": ctl["session_view"]["suspensions_in_window"],
            "reviewer_assessment": a["assessment"], "reviewer_non_candidate_reason": a["non_candidate_reason"],
            "reviewer_contrast": a["contrast"], "reviewer_uncertainty": a["uncertainty"],
            "reviewer_admissible": a["admissible"], "reviewer_fragile": bool(a.get("fragile", False)),
            "same_policy_eligibility": {"policy_hash": ctl["policy_hash"] == rep["policy_hash"], "policy_version": ctl["policy_version"] == rep["policy_version"],
                                        "same_date": ctl["cutoff"]["decision_date"] == rep["cutoff"]["decision_date"],
                                        "same_mode_convention": ctl["cutoff"]["mode"] == rep["cutoff"]["mode"] and ctl["cutoff"]["convention"] == rep["cutoff"]["convention"],
                                        "same_band": ctl["labels"]["liquidity"]["band"] == rep["labels"]["liquidity"]["band"],
                                        "same_regime": ctl["labels"]["regime"]["regime"] == rep["labels"]["regime"]["regime"],
                                        "same_universe": ctl["universe"]["universe_sha256"] == rep["universe"]["universe_sha256"],
                                        "non_candidate": ctl["labels"]["selection"]["label"] == "non_candidate", "observed": ctl["current_state"] == "observed"},
        })
    fragile = [c["symbol"] for c in control_reviews if c["reviewer_fragile"]]
    robust = [c["symbol"] for c in control_reviews if c["reviewer_admissible"] and not c["reviewer_fragile"]]
    inadmissible = [c["symbol"] for c in control_reviews if not c["reviewer_admissible"]]
    inspections = inspection_entries(case_id)
    if not inspections:
        raise SystemExit(f"{case_id}: no evidence inspection log entry")
    reviewed_at = datetime.now(timezone.utc).isoformat()
    evidence_refs = [
        f"bundle:cases/{case_id}.json sha256={case_sha}",
        f"bundle:manifest.json sha256={BUNDLE_MANIFEST_SHA256}",
        f"bundle:index.json sha256={BUNDLE_INDEX_SHA256}",
        f"cutoff_packet_hash={p['cutoff_packet_hash']}",
        f"prefix_hash={proof['prefix_hash']}",
        f"dossier:{inspections[-1]['dossier']} sha256={inspections[-1]['dossier_sha256']}",
        f"inspection_log:execution/evidence_inspection_log.jsonl entries={len(inspections)} first={inspections[0]['inspected_at_utc']} last={inspections[-1]['inspected_at_utc']}",
        f"authored_note:authored_notes/{case_id}.json sha256={note_sha}",
        f"source_replay:{case['source_binding']['source_replay_sha256']}",
        f"packet_audit:{case['source_binding']['packet_audit_sha256']}",
    ]
    execution_ref = f"{TASK_ID}:claude_03:execution={execution['execution_id']}:session={SESSION_ID}:receipt=execution/execution_receipt.json"
    raw = m.ReviewRecord(reviewer_id=REVIEWER_ID, reviewer_kind=REVIEWER_KIND, reviewed_at=reviewed_at, verdict=note["verdict"],
                         evidence_refs=tuple(evidence_refs), execution_ref=execution_ref, case_episode_id=rep["episode_id"],
                         case_record_hash=rep["record_hash"], case_policy_hash=rep["policy_hash"], synthetic=False, supersedes=None,
                         supersede_reason="", notes=f"{note['verdict']}: {note['summary']}", case_prefix_hash=proof["prefix_hash"]).validated()
    review = {
        "schema": "m3.claude_03.case_review.v1", "task_id": TASK_ID, "case_id": case_id, "symbol": rep["symbol"],
        "representative_date": rep["cutoff"]["decision_date"], "prefix_dates": note["prefix_dates"],
        "reviewer_id": REVIEWER_ID, "reviewer_kind": REVIEWER_KIND, "reviewer_description": REVIEWER_DESCRIPTION,
        "reviewed_at": reviewed_at, "evidence_inspected_at": [e["inspected_at_utc"] for e in inspections],
        "execution_ref": execution_ref, "execution_id": execution["execution_id"], "session_id": SESSION_ID,
        "input_bindings": {
            "bundle_dir": "claude methods/_m3_20260910/codex/case_review_bundle_01", "case_file": rel, "case_file_sha256": case_sha,
            "bundle_manifest_sha256": BUNDLE_MANIFEST_SHA256, "bundle_index_sha256": BUNDLE_INDEX_SHA256,
            "episode_key": p["episode_key"], "cutoff_packet_hash": p["cutoff_packet_hash"], "original_packet_sha256": case["source_binding"]["original_packet_sha256"],
            "case_episode_id": rep["episode_id"], "case_record_hash": rep["record_hash"], "case_prefix_hash": proof["prefix_hash"],
            "prefix_member_episode_ids": proof["member_episode_ids"], "prefix_member_record_hashes": proof["member_record_hashes"],
            "prefix_established_at": proof["established_at"], "prefix_start": proof["start"],
            "representative_decision_fingerprint": rep["identity"]["decision_fingerprint"],
            "control_record_hashes": [c["record_hash"] for c in controls], "control_count": len(controls),
            "policy_hash": rep["policy_hash"], "policy_version": rep["policy_version"], "labels_module_sha256": LABELS_SHA256,
            "producer_sha256": rep["producer_sha256"], "calendar_fingerprint": rep["calendar"]["fingerprint"], "universe_sha256": rep["universe"]["universe_sha256"],
            "delivery_manifest_sha256": case["source_binding"]["delivery_manifest_sha256"], "source_replay_sha256": case["source_binding"]["source_replay_sha256"],
            "packet_audit_sha256": case["source_binding"]["packet_audit_sha256"],
            "cutoff": rep["cutoff"], "information_time": p["information_time"], "synthetic": rep["synthetic"], "split_role": rep["split_role"],
        },
        "frozen_labels_at_representative": {"phase": rep["labels"]["phase"], "selection": rep["labels"]["selection"], "entry": rep["labels"]["entry"],
                                            "liquidity": rep["labels"]["liquidity"], "regime": rep["labels"]["regime"], "limit": rep["labels"]["limit"],
                                            "position_event": rep["labels"]["position_event"], "current_state": rep["current_state"],
                                            "data_quality": rep["data_quality"], "features": rep["features"], "security_context": rep["security_context"]},
        "verdict": note["verdict"], "verdict_scope": "support for the frozen observable accumulation-proxy episode only; not hidden-actor knowledge, future return or trading suitability",
        "disposition": note["disposition"], "counting_eligible": note["counting_eligible"],
        "summary": note["summary"], "assessment": note["assessment"],
        "supporting_evidence": note["supporting_evidence"], "contradicting_evidence": note["contradicting_evidence"], "limitations": note["limitations"],
        "control_reviews": control_reviews, "control_set_admissible": note["control_set_admissible"], "control_set_assessment": note["control_set_assessment"],
        "control_set_summary": {"selected": len(controls), "reviewer_admissible": len(control_reviews) - len(inadmissible), "reviewer_inadmissible": inadmissible,
                                "reviewer_fragile": fragile, "robust_count": len(robust), "k_min": p["match"]["k_min"], "k_max": p["match"]["k_max"],
                                "robust_meets_k_min": len(robust) >= p["match"]["k_min"],
                                "note": "same-day matched controls bound comparability within date/band/regime/policy; they do not establish causal identification"},
        "dependence_and_reuse_notes": note["dependence_and_reuse_notes"],
        "addenda": note.get("addenda", []), "authored_note_sha256": note_sha, "authored_note_path": f"authored_notes/{case_id}.json",
        "serialization_generation": SERIALIZATION_GENERATION,
        "effective_text_applied": {
            "applied": effective_meta is not None,
            "paths": sorted(original_text),
            "source": effective_meta["source"] if effective_meta else None,
            "authored_at_utc": effective_meta["authored_at_utc"] if effective_meta else None,
            "original_note_sha256": effective_meta["original_note_sha256"] if effective_meta else None,
            "original_note_snapshot": effective_meta["original_note_snapshot"] if effective_meta else None,
            "principle": effective_meta["principle"] if effective_meta else "no correction addenda required effective-text replacement for this case; current text equals the original authored text",
            "note": "The current summary/assessment/evidence/control fields above and raw_review.notes are the effective text (original authored text with the hash-linked addenda incorporated). The verbatim original for every replaced path is in original_authored_text; the addenda record why each replacement was made.",
        },
        "original_authored_text": original_text,
        "reviewed_at_semantics": REVIEWED_AT_SEMANTICS,
        "superseded_draft": SUPERSEDED_DRAFT,
        "provenance_clarification": PROVENANCE_CLARIFICATION,
        "raw_review": raw,
        "review_ledger_note": "raw_review is a ReviewRecord-compatible entry bound to the representative core (case_episode_id/case_record_hash/case_policy_hash) and to the episode prefix (case_prefix_hash); it was validated with the accepted kernel but NOT attached to any input core - input cores are unchanged.",
        "safety": {"review_only": True, "live_trading_enabled": False, "strict_pit": False, "training_eligible": False, "synthetic": False,
                   "later_outcomes_consulted": False, "full_chronology_consulted": False, "episode_audit_consulted": False, "sqlite_connections": 0, "network": 0},
    }
    data = (json.dumps(review, ensure_ascii=False, indent=2, sort_keys=False) + "\n").encode("utf-8")
    (out_dir / f"{case_id}.json").write_bytes(data)
    return {"case_id": case_id, "verdict": note["verdict"], "counting_eligible": note["counting_eligible"], "controls": len(controls),
            "fragile_controls": fragile, "inadmissible_controls": inadmissible, "review_sha256": hashlib.sha256(data).hexdigest(), "reviewed_at": reviewed_at,
            "effective_paths": sorted(original_text)}


def serialize_diagnostics(m, manifest: dict, execution: dict, out_dir: Path) -> list[dict]:
    notes_path = NOTES / "diagnostics.json"
    notes_sha = sha(notes_path)
    notes = json.loads(notes_path.read_text(encoding="utf-8"))
    results = []
    for diag_id in [f"D{i:03d}" for i in range(1, 9)]:
        rel = f"diagnostics/{diag_id}.json"
        path = BUNDLE / rel
        file_sha = sha(path)
        if file_sha != manifest["written"][rel]["sha256"]:
            raise SystemExit(f"{diag_id}: pin mismatch")
        d = json.loads(path.read_text(encoding="utf-8"))
        rec = d["record"]
        note = notes["diagnostics"][diag_id]
        if note["kind"] != d["diagnostic_kind"] or note["symbol"] != rec["symbol"] or note["decision_date"] != rec["cutoff"]["decision_date"]:
            raise SystemExit(f"{diag_id}: note identity mismatch")
        for key in ("semantics_assessment", "bindings_note", "finding"):
            if not nonempty(note.get(key)):
                raise SystemExit(f"{diag_id}: empty {key}")
        if note.get("counts_as_positive_episode") is not False:
            raise SystemExit(f"{diag_id}: diagnostics never count as positive")
        inspections = inspection_entries(diag_id)
        if not inspections:
            raise SystemExit(f"{diag_id}: no evidence inspection log entry")
        reviewed_at = datetime.now(timezone.utc).isoformat()
        execution_ref = f"{TASK_ID}:claude_03:execution={execution['execution_id']}:session={SESSION_ID}:receipt=execution/execution_receipt.json"
        review = {
            "schema": "m3.claude_03.diagnostic_review.v1", "task_id": TASK_ID, "case_id": diag_id, "diagnostic_kind": d["diagnostic_kind"],
            "symbol": rec["symbol"], "decision_date": rec["cutoff"]["decision_date"], "selection_rule": d["selection_rule"],
            "reviewer_id": REVIEWER_ID, "reviewer_kind": REVIEWER_KIND, "reviewer_description": REVIEWER_DESCRIPTION,
            "reviewed_at": reviewed_at, "evidence_inspected_at": [e["inspected_at_utc"] for e in inspections], "execution_ref": execution_ref,
            "execution_id": execution["execution_id"], "session_id": SESSION_ID,
            "input_bindings": {"diagnostic_file": rel, "diagnostic_file_sha256": file_sha, "bundle_manifest_sha256": BUNDLE_MANIFEST_SHA256,
                               "bundle_index_sha256": BUNDLE_INDEX_SHA256, "record_hash": rec["record_hash"], "episode_id": rec["episode_id"],
                               "decision_fingerprint": rec["identity"]["decision_fingerprint"], "policy_hash": rec["policy_hash"], "policy_version": rec["policy_version"],
                               "labels_module_sha256": LABELS_SHA256, "producer_sha256": rec["producer_sha256"], "cutoff": rec["cutoff"],
                               "source_replay_sha256": d["source_replay_sha256"], "origin_provenance_only": d["origin"]},
            "frozen_labels": {"phase": rec["labels"]["phase"], "selection": rec["labels"]["selection"], "entry": rec["labels"]["entry"],
                              "position_event": rec["labels"]["position_event"], "liquidity": rec["labels"]["liquidity"], "regime": rec["labels"]["regime"],
                              "limit": rec["labels"]["limit"], "current_state": rec["current_state"], "data_quality": rec["data_quality"],
                              "features": rec["features"], "security_context": rec["security_context"], "session_view": rec["session_view"]},
            "semantics_assessment": note.get("semantics_assessment_corrected", note["semantics_assessment"]),
            "bindings_note": note.get("bindings_note_corrected", note["bindings_note"]), "finding": note["finding"],
            "original_semantics_assessment": note["semantics_assessment"] if "semantics_assessment_corrected" in note else None,
            "original_bindings_note": note["bindings_note"] if "bindings_note_corrected" in note else None,
            "retrospective_collection_cross_reference": {"text": note.get("retrospective_collection_cross_reference"),
                                                          "status": "collection navigation only; not available at the diagnostic cutoff; excluded from diagnostic evidence and label judgment"},
            "diagnostic_notes_addenda": notes.get("addenda", []),
            "counts_as_positive_episode": False, "excluded_from_positive_counts": True,
            "no_trade_semantics": "position_event=no_trade is the result under absent declared position input (no PositionState supplied); it does not establish that an actual account held nothing or that no fill occurred, and it is not an observed stop, exit or fill result",
            "authored_note_sha256": notes_sha, "authored_note_path": "authored_notes/diagnostics.json", "provenance_clarification": PROVENANCE_CLARIFICATION,
            "serialization_generation": SERIALIZATION_GENERATION,
            "effective_text_applied": {"applied": "semantics_assessment_corrected" in note or "bindings_note_corrected" in note,
                                       "paths": [k for k in ("semantics_assessment", "bindings_note") if f"{k}_corrected" in note],
                                       "note": "semantics_assessment / bindings_note above are the effective text; original_semantics_assessment / original_bindings_note hold the verbatim originals where a correction was applied."},
            "reviewed_at_semantics": REVIEWED_AT_SEMANTICS, "superseded_draft": SUPERSEDED_DRAFT,
            "safety": {"review_only": True, "live_trading_enabled": False, "strict_pit": False, "training_eligible": False, "synthetic": False,
                       "later_outcomes_consulted": False, "full_chronology_consulted": False, "sqlite_connections": 0, "network": 0},
        }
        data = (json.dumps(review, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        (out_dir / f"{diag_id}.json").write_bytes(data)
        results.append({"case_id": diag_id, "kind": d["diagnostic_kind"], "finding": note["finding"], "review_sha256": hashlib.sha256(data).hexdigest(), "reviewed_at": reviewed_at})
    return results


def main() -> int:
    started = datetime.now(timezone.utc).isoformat()
    manifest = check_bundle_pins()
    m = load_labels()
    execution = {"execution_id": str(uuid.uuid4()), "started_at_utc": started}
    reviews_dir = CLAUDE_03 / "reviews"; diags_dir = CLAUDE_03 / "diagnostics"
    reviews_dir.mkdir(exist_ok=True); diags_dir.mkdir(exist_ok=True)
    draft_status_path = CLAUDE_03 / SUPERSEDED_DRAFT["status_file"]
    draft_status = json.loads(draft_status_path.read_text(encoding="utf-8"))
    if draft_status["draft_execution_id"] != SUPERSEDED_DRAFT["draft_execution_id"]:
        raise SystemExit("superseded draft execution id mismatch")
    draft_bad = [rel for rel, h in draft_status["files"].items() if sha(draft_status_path.parent / rel) != h]
    if draft_bad:
        raise SystemExit(f"superseded draft files changed: {draft_bad}")
    case_results = [serialize_case(m, f"C{i:03d}", manifest, execution, reviews_dir) for i in range(1, 33)]
    diag_results = serialize_diagnostics(m, manifest, execution, diags_dir)
    log_entries = [json.loads(l) for l in LOG.read_text(encoding="utf-8").splitlines() if l.strip()]
    effective_cases = sorted(c["case_id"] for c in case_results if c["effective_paths"])
    receipt = {
        "schema": "m3.claude_03.execution_receipt.v1", "task_id": TASK_ID, **execution, "finished_at_utc": datetime.now(timezone.utc).isoformat(),
        "serialization_generation": SERIALIZATION_GENERATION,
        "superseded_draft": {**SUPERSEDED_DRAFT, "status_file_sha256": sha(draft_status_path), "files_verified": len(draft_status["files"])},
        "reviewed_at_semantics": REVIEWED_AT_SEMANTICS,
        "effective_text": {"cases_with_effective_text": effective_cases, "count": len(effective_cases),
                           "paths_by_case": {c["case_id"]: c["effective_paths"] for c in case_results if c["effective_paths"]},
                           "principle": "current text and raw_review.notes incorporate the hash-linked addenda; originals preserved per path and by note snapshot"},
        "reviewer_id": REVIEWER_ID, "reviewer_kind": REVIEWER_KIND, "reviewer_description": REVIEWER_DESCRIPTION, "session_id": SESSION_ID,
        "tools": {"show_case_evidence.py": sha(HERE / "show_case_evidence.py"), "serialize_reviews.py": sha(Path(__file__))},
        "bundle_manifest_sha256": BUNDLE_MANIFEST_SHA256, "bundle_index_sha256": BUNDLE_INDEX_SHA256, "labels_module_sha256": LABELS_SHA256, "policy_hash": POLICY_HASH,
        "evidence_inspection_log": {"path": "execution/evidence_inspection_log.jsonl", "sha256": sha(LOG), "entries": len(log_entries),
                                    "distinct_ids_inspected": sorted({e["case_id"] for e in log_entries}),
                                    "cores_verified_total": sum(e["cores_verified"] for e in log_entries),
                                    "first_inspection_utc": min(e["inspected_at_utc"] for e in log_entries), "last_inspection_utc": max(e["inspected_at_utc"] for e in log_entries),
                                    "problems_reported": sum(len(e["problems"]) for e in log_entries)},
        "cases": case_results, "diagnostics": diag_results,
        "verdict_counts": {v: sum(1 for c in case_results if c["verdict"] == v) for v in VERDICTS},
        "counting_eligible_cases": sum(1 for c in case_results if c["counting_eligible"]),
        "control_uses_reviewed": sum(c["controls"] for c in case_results),
        "fragile_control_uses": sum(len(c["fragile_controls"]) for c in case_results),
        "inadmissible_control_uses": sum(len(c["inadmissible_controls"]) for c in case_results),
        "method": "Each case dossier (execution/dossiers/<id>.txt) was generated by show_case_evidence.py from the pinned bundle file only, read in full by the reviewer, and the authored note in authored_notes/<id>.json was written by hand before serialization; the serializer binds hashes and identities and refuses inconsistent notes. Corrections requested in-task were appended as hash-linked addenda with pre-addendum snapshots under authored_notes/history/; generation 2 additionally overlays the reviewer's path-keyed effective text (note['effective']) so the current text and raw_review.notes incorporate those addenda, with the pre-effective note snapshotted by hash.",
        "no_subagents": "No subagent, workflow or second reviewer was used; the task prohibits dispatching other agents.",
        "safety": {"review_only": True, "live_trading_enabled": False, "strict_pit": False, "training_eligible": False, "sqlite_connections": 0, "network": 0,
                   "full_chronology_files_opened": 0, "episode_audit_files_opened": 0, "later_outcomes_consulted": False, "codex_reviews_read": False},
    }
    (CLAUDE_03 / "execution" / "execution_receipt.json").write_bytes((json.dumps(receipt, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({"execution_id": execution["execution_id"], "cases": len(case_results), "diagnostics": len(diag_results),
                      "verdicts": receipt["verdict_counts"], "control_uses": receipt["control_uses_reviewed"], "fragile": receipt["fragile_control_uses"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
