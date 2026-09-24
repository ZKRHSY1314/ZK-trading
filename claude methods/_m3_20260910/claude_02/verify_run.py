"""Independent re-verification of a claude_02 development run (no SQLite, no network).

Re-verifies: frozen input pins, chronology file hashes vs index, every record (frozen-module
verify_record + validate_ledger, pending ledger, retrospective close+3600s cutoff, consumed
dates within the bound, strict_pit=false, training_eligible=false), every packet (prefix
proof recomputed from the complete chronology, representative/member bindings, same-date
control cores, revalidate_match through a RecordRegistry), and the waterfall counts.

    D:/codex-A股交易/backend/.venv/Scripts/python.exe -B -X utf8 "claude methods/_m3_20260910/claude_02/verify_run.py" dev_run_01
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[2]
READER = PROJECT / "backend" / "app" / "research" / "m3_frozen_reader.py"


_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _dates(obj):
    if isinstance(obj, dict):
        for v in obj.values():
            yield from _dates(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _dates(v)
    elif isinstance(obj, str):
        if _DATE_RE.match(obj):
            yield obj
        elif "#" in obj and _DATE_RE.match(obj.split("#")[0]):
            yield obj.split("#")[0]


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    run_name = sys.argv[1] if len(sys.argv) > 1 else "dev_run_01"
    out = HERE / "runs" / run_name
    spec = importlib.util.spec_from_file_location("m3_frozen_reader_verify", READER)
    r = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = r
    spec.loader.exec_module(r)
    m = r.load_labels()
    receipt = json.loads((out / "run_receipt.json").read_text(encoding="utf-8"))
    problems: list[str] = []
    checks: dict[str, int] = {"records": 0, "packets": 0, "matches_revalidated": 0, "chronology_files": 0}

    for name, spec_ in r._specs(r.FROZEN_M2).items():
        actual = r.verify_source(spec_)
        if actual["sha256"] != receipt["inputs"][name]["sha256"]:
            problems.append(f"input_changed:{name}")
    if receipt["labels_sha256"] != r.FROZEN_LABELS_SHA256 or receipt["policy_hash"] != m.POLICY_HASH:
        problems.append("labels_or_policy_pin_mismatch")

    index = json.loads((out / "chronology_index.json").read_text(encoding="utf-8"))
    inventory = json.loads((out / "inventory.json").read_text(encoding="utf-8"))
    cal = inventory["calendar"]
    calendar_sessions = tuple(d for d in r.load_calendar(r.FROZEN_M2.calendar) if cal["first"] <= d <= cal["last"])
    calendar = m.SessionCalendar(calendar_sessions, cal["source_ref"], cal["available_at"], synthetic=cal["synthetic"])
    if calendar.fingerprint() != cal["fingerprint"]:
        problems.append("calendar_fingerprint_mismatch")
    records_by_symbol: dict[str, list[dict]] = {}
    by_key: dict[tuple[str, str], dict] = {}
    for symbol, info in index["files"].items():
        path = out / "chronology" / f"{symbol}.jsonl.gz"
        if sha(path) != info["sha256_gzip"]:
            problems.append(f"chronology_hash_mismatch:{symbol}")
            continue
        checks["chronology_files"] += 1
        records = [e["record"] for e in r.read_jsonl_gz(path)]
        if len(records) != info["records"]:
            problems.append(f"chronology_count_mismatch:{symbol}")
        for rec in records:
            checks["records"] += 1
            try:
                m.verify_record(rec)
                m.validate_ledger(rec)
            except Exception as exc:  # noqa: BLE001 - report, do not abort
                problems.append(f"record_invalid:{symbol}:{rec.get('cutoff', {}).get('decision_date')}:{exc}")
                continue
            if rec["review_ledger"]["entries"] or rec["review_ledger"]["status"] != "pending_review":
                problems.append(f"record_not_pending:{symbol}:{rec['cutoff']['decision_date']}")
            if rec["cutoff"]["mode"] != "retrospective" or rec["cutoff"]["convention"] != "close+3600s":
                problems.append(f"cutoff_convention:{symbol}:{rec['cutoff']['decision_date']}")
            if (rec["input_availability"]["max_trade_date_consumed"] or "0000") > r.PRICE_CONSUMPTION_MAX_DATE:
                problems.append(f"consumed_beyond_bound:{symbol}:{rec['cutoff']['decision_date']}")
            if rec["pit"]["strict_pit_eligible"] or rec["pit"]["training_eligible"] or not rec["review_only"] or rec["live_trading_enabled"]:
                problems.append(f"flags:{symbol}:{rec['cutoff']['decision_date']}")
            if rec["synthetic"] != receipt["synthetic"] or rec["calendar"]["fingerprint"] != cal["fingerprint"]:
                problems.append(f"identity_context:{symbol}:{rec['cutoff']['decision_date']}")
            by_key[(symbol, rec["cutoff"]["decision_date"])] = rec
        records_by_symbol[symbol] = records
    if checks["records"] != index["total_records"] or checks["records"] != receipt["records_generated"]:
        problems.append("record_totals_disagree")

    episodes = json.loads((out / "episodes.json").read_text(encoding="utf-8"))
    for p in episodes["packets"]:
        packet_path = out / "packets" / f"{p['episode_key']}.json"
        if sha(packet_path) != p["packet_sha256"]:
            problems.append(f"packet_hash:{p['episode_key']}")
            continue
        packet = json.loads(packet_path.read_text(encoding="utf-8"))
        checks["packets"] += 1
        if packet["review_status"] != "pending_review" or packet["reviews"]:
            problems.append(f"packet_not_pending:{p['episode_key']}")
        if packet.get("schema") != "m3.frozen_reader.cutoff_review_packet.v2" or packet.get("cutoff_packet_hash") != r.cutoff_packet_hash(packet):
            problems.append(f"cutoff_packet_hash:{p['episode_key']}")
        rep_date_p = packet["representative"]["decision_date"]
        later_dates = sorted({d for d in _dates(packet) if d > rep_date_p})
        if later_dates:
            problems.append(f"packet_contains_later_dates:{p['episode_key']}:{later_dates[:3]}")
        for forbidden in ("known_end_so_far", "status", "closed_reason", "selection_path", "eligibility_changes", "end"):
            if forbidden in packet:
                problems.append(f"packet_contains_retrospective_field:{p['episode_key']}:{forbidden}")
        audit_path = out / "episode_audit" / f"{p['episode_key']}.json"
        if not audit_path.is_file() or sha(audit_path) != p.get("episode_audit_sha256"):
            problems.append(f"episode_audit_hash:{p['episode_key']}")
        else:
            checks["episode_audits"] = checks.get("episode_audits", 0) + 1
            audit = json.loads(audit_path.read_text(encoding="utf-8"))
            if not audit.get("not_cutoff_known") or audit.get("prefix_hash") != packet["prefix_proof"]["prefix_hash"]:
                problems.append(f"episode_audit_binding:{p['episode_key']}")
        proof = packet["prefix_proof"]
        recs = records_by_symbol.get(packet["symbol"], [])
        rep = by_key.get((packet["symbol"], packet["representative"]["decision_date"]))
        if rep is None or rep["record_hash"] != proof["representative_record_hash"] or rep["episode_id"] != packet["representative"]["episode_id"]:
            problems.append(f"representative_binding:{p['episode_key']}")
            continue
        recomputed = m.prefix_proof_for(recs, calendar, rep)
        if recomputed is None or recomputed["prefix_hash"] != proof["prefix_hash"]:
            problems.append(f"prefix_proof:{p['episode_key']}")
        if [mm["record_hash"] for mm in packet["members"]] != proof["member_record_hashes"]:
            problems.append(f"member_binding:{p['episode_key']}")
        if packet.get("match"):
            controls = []
            for c in packet["controls"]:
                crec = by_key.get((c["symbol"], packet["representative"]["decision_date"]))
                if crec is None or crec["record_hash"] != c["record_hash"]:
                    problems.append(f"control_binding:{p['episode_key']}:{c['symbol']}")
                    continue
                controls.append(crec)
            try:
                m.revalidate_match(packet["match"], m.RecordRegistry([rep] + controls))
                checks["matches_revalidated"] += 1
            except Exception as exc:  # noqa: BLE001
                problems.append(f"match_revalidation:{p['episode_key']}:{exc}")
    waterfall = json.loads((out / "waterfall.json").read_text(encoding="utf-8"))["waterfall"]
    if waterfall["records_generated"] != checks["records"]:
        problems.append("waterfall_records_mismatch")
    if waterfall["independently_reviewed"] != 0 or waterfall["qualified_reviewed_positive_episodes"] != 0 or waterfall["target"]["met"]:
        problems.append("reviewed_counts_must_be_zero")
    result = {"schema": "m3.claude_02.verify_run.v1", "run": run_name, "checks": checks, "problems": problems, "ok": not problems,
              "reader_sha256": sha(READER), "labels_sha256": r.FROZEN_LABELS_SHA256, "policy_hash": m.POLICY_HASH}
    (out / "verify_run_result.json").write_bytes((json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    print(json.dumps(result, ensure_ascii=False, indent=1))
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
