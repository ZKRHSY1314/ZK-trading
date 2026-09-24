"""Executed arithmetic check for REVIEW_REPORT.md section-5 counts (M3-03).

Recomputes, from the 96 embedded prefix cores of the pinned bundle, the
set of cases with at least one member whose deciding accumulation-leg margin
(0.65-position_250, 0.09-ma_spread_20_60, 0.25-return_120) is strictly
below 0.01, and cross-checks the negative narrative groupings against the
authored verdicts. Reads only the bundle case files and the authored notes;
writes execution/report_count_check.json. No network, SQLite or account
access.

Run: backend/.venv/Scripts/python.exe -B -X utf8 <this file>
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
C03 = HERE.parent
ROOT = C03.parents[2]
BUNDLE = C03.parent / "codex" / "case_review_bundle_01"
NOTES = C03 / "authored_notes"
OUT = C03 / "execution" / "report_count_check.json"

THIN = 0.01
LEGS = {
    "position": ("position_250", 0.65),
    "spread": ("ma_spread_20_60", 0.09),
    "return_120": ("return_120", 0.25),
}

# Narrative groupings as stated in the corrected report (section 5).
ADVANCE_REBOUND = ["C002", "C003", "C006", "C008", "C009", "C018", "C019"]
BREAK_DECLINE = ["C004", "C012", "C013", "C016", "C020", "C022", "C032"]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    manifest = json.loads((BUNDLE / "manifest.json").read_text(encoding="utf-8"))
    per_case: dict[str, dict] = {}
    thin: dict[str, list[str]] = {k: [] for k in LEGS}
    cores = 0
    for i in range(1, 33):
        cid = f"C{i:03d}"
        case = json.loads((BUNDLE / "cases" / f"{cid}.json").read_text(encoding="utf-8"))
        members = case["prefix_records"]
        assert len(members) == 3, cid
        cores += len(members)
        margins = {}
        for leg, (feat, cap) in LEGS.items():
            vals = []
            for rec in members:
                v = rec["features"].get(feat)
                assert v is not None, (cid, feat)
                vals.append(cap - float(v))
            margins[leg] = {"per_member": vals, "min": min(vals), "thin": min(vals) < THIN}
            if min(vals) < THIN:
                thin[leg].append(cid)
        per_case[cid] = {"margins": margins, "any_thin": any(m["thin"] for m in margins.values())}
    union = sorted(c for c, d in per_case.items() if d["any_thin"])

    verdicts = {}
    for i in range(1, 33):
        cid = f"C{i:03d}"
        verdicts[cid] = json.loads((NOTES / f"{cid}.json").read_text(encoding="utf-8"))["verdict"]
    negatives = sorted(c for c, v in verdicts.items() if v == "negative")
    groups_ok = (
        sorted(ADVANCE_REBOUND + BREAK_DECLINE) == negatives
        and not set(ADVANCE_REBOUND) & set(BREAK_DECLINE)
    )

    result = {
        "check": "report_section5_counts",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "bundle_manifest_sha256": sha(BUNDLE / "manifest.json"),
        "bundle_index_sha256": sha(BUNDLE / "index.json"),
        "prefix_cores_examined": cores,
        "thin_criterion": "min over the 3 prefix members of (0.65-position_250), (0.09-ma_spread_20_60), (0.25-return_120); thin iff strictly < 0.01",
        "thin_by_leg": thin,
        "thin_union": union,
        "thin_union_count": len(union),
        "legs_disjoint": len(set(thin["position"]) & set(thin["spread"])) == 0
        and len(set(thin["position"]) & set(thin["return_120"])) == 0
        and len(set(thin["spread"]) & set(thin["return_120"])) == 0,
        "examples_not_thin": {
            "C010_min_position_margin": per_case["C010"]["margins"]["position"]["min"],
            "C031_min_return_120_margin": per_case["C031"]["margins"]["return_120"]["min"],
            "C019_min_return_120_margin": per_case["C019"]["margins"]["return_120"]["min"],
            "C026_min_position_margin": per_case["C026"]["margins"]["position"]["min"],
        },
        "verdict_counts": {v: sum(1 for x in verdicts.values() if x == v) for v in ("positive", "negative", "ambiguous", "failed", "reject_data")},
        "negatives": negatives,
        "narrative_groups": {
            "advance_rebound": ADVANCE_REBOUND,
            "advance_rebound_count": len(ADVANCE_REBOUND),
            "break_decline_possible_lock": BREAK_DECLINE,
            "break_decline_possible_lock_count": len(BREAK_DECLINE),
            "partition_of_negatives": groups_ok,
        },
        "superseded_report_claim": {
            "thin_union_count": 20,
            "narrative_counts": {"advance_rebound": 8, "break_decline": 6},
            "status": "withdrawn; corrected per M3_03_REPORT_COUNT_FACT_CHECK.md sha256 e2cf48188332076b6a400780359e9a0306b4fc99851741ae9bda699d4f577016",
        },
        "per_case": per_case,
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("prefix_cores_examined", "thin_by_leg", "thin_union_count", "legs_disjoint", "examples_not_thin", "verdict_counts")}, indent=2))
    print("narrative partition ok:", groups_ok, "negatives:", len(negatives))
    print("wrote", OUT)
    return 0 if groups_ok else 1


if __name__ == "__main__":
    sys.exit(main())
