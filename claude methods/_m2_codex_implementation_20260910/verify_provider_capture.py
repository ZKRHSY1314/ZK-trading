"""Re-run the pure history parser on eight frozen raw qualification responses.

Only reads source/capture/calendar files and creates the requested summary file.
It does not authenticate, contact a service, initialize the application, or open
a database. This is parser integration evidence, not independent source-basis
qualification. Run with -B to avoid changing frozen evidence directories.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PARSER = ROOT / "backend/app/data/tonghuasun_history.py"
CALENDAR = ROOT / "backend/.venv/Lib/site-packages/akshare/file_fold/calendar.json"
CAPTURE = HERE / "qualification_capture"
START, END = "2022-08-24", "2026-09-04"
RESEARCH_START = "2023-09-04"
CALENDAR_SHA = "f1f1ce33c5cceb5c530c3271fc951405cb5624d2f30becec85dc7a85fd47e656"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run():
    if digest(CALENDAR) != CALENDAR_SHA:
        raise ValueError("frozen calendar differs")
    calendar = json.loads(CALENDAR.read_text(encoding="utf-8-sig"))
    normalized = [day[:4] + "-" + day[4:6] + "-" + day[6:]
                  if len(day) == 8 and day.isdigit() else day for day in calendar]
    expected = [day for day in normalized if START <= day <= END]
    if len(expected) != 978 or len([day for day in expected if day >= RESEARCH_START]) != 728:
        raise ValueError("frozen expected date counts differ")
    module_spec = importlib.util.spec_from_file_location("m2_history_raw_verification", PARSER)
    module = importlib.util.module_from_spec(module_spec)
    sys.modules[module_spec.name] = module
    module_spec.loader.exec_module(module)
    plan = json.loads((CAPTURE / "plan.json").read_text(encoding="utf-8"))
    jobs = plan["jobs"]
    if len(jobs) != 8 or [job["id"] for job in jobs] != list(range(1, 9)):
        raise ValueError("unexpected frozen capture jobs")
    pins = json.loads((CAPTURE / "producer_pins.json").read_text(encoding="utf-8"))
    pins_valid = all(digest(Path(path)) == expected_hash for path, expected_hash in pins.items())
    if not pins_valid:
        raise ValueError("capture producer pin drift")
    specs = {
        "SH000300": module.SecuritySpec.benchmark("SH000300", host_full_code="USZI399300",
            response_full_code="399300.SZ",
            mapping_evidence="qualification_capture/completed_1.json#source_security; canonical alias requires separate reviewed mapping evidence"),
        "SH000001": module.SecuritySpec.benchmark("SH000001", host_full_code="USHI1A0001",
            response_full_code="10001.SH",
            mapping_evidence="qualification_capture/completed_2.json#source_security; host formatter output only, canonical identity requires separate reviewed mapping evidence"),
        "SH600011": module.SecuritySpec.stock("SH600011"),
        "BJ920000": module.SecuritySpec.stock("BJ920000"),
    }
    adjustments = {0: "none", 1: "qfq", 2: "hfq"}
    observations = []
    source_files = {}
    for job in jobs:
        job_id = job["id"]
        raw_path = CAPTURE / f"response_{job_id}.bin"
        receipt_path = CAPTURE / f"completed_{job_id}.json"
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        raw = raw_path.read_bytes()
        raw_sha = hashlib.sha256(raw).hexdigest()
        if (receipt["job"] != job or receipt["raw_sha256"] != raw_sha
                or receipt["raw_bytes"] != len(raw) or receipt["http_status"] != 200):
            raise ValueError(f"capture receipt mismatch at {job_id}")
        spec = specs[job["symbol"]]
        request = job["payload"]
        if (request["security"] != {"hostFullCode": spec.host_full_code}
                or request["startTimeUtc"] != "2022-08-23T16:00:00Z"
                or request["endTimeUtc"] != "2026-09-04T15:59:59.999Z"
                or request["period"] != 7 or request["market"] != 1
                or request["limit"] != 5000 or request["fields"] != list(module.FIELDS)
                or "codes" in request):
            raise ValueError(f"capture request contract mismatch at {job_id}")
        parsed = module.parse_history_response(raw, spec, START, END,
            adjustment=adjustments[request["adjustment"]], expected_dates=expected)
        if (not parsed["coverage"]["complete"] or parsed["eligible"]
                or parsed["mapping_verified"] or parsed["vendor_basis"] != "unverified"
                or parsed["volume_unit"] != "unverified" or parsed["amount_unit"] != "unverified"
                or [row["point_index"] for row in parsed["rows"]] != list(range(978))):
            raise ValueError(f"unexpected parser verdict at {job_id}")
        observations.append({
            "job_id": job_id, "canonical_symbol": parsed["canonical_symbol"],
            "source_security": parsed["response_identity"],
            "requested_adjustment": parsed["requested_adjustment"],
            "response_adjustment": parsed["response_adjustment"],
            "raw_sha256": raw_sha, "raw_bytes": len(raw),
            "receipt_sha256": digest(receipt_path), "observed_at": receipt["observed_at"],
            "rows": len(parsed["rows"]), "first_date": parsed["first_date"],
            "last_date": parsed["last_date"],
            "research_rows": sum(row["date"] >= RESEARCH_START for row in parsed["rows"]),
            "warmup_rows": sum(row["date"] < RESEARCH_START for row in parsed["rows"]),
            "coverage": parsed["coverage"],
            "amount_missing_rows": sum(row["amount"] is None for row in parsed["rows"]),
            "name_diagnostic_counts": dict(Counter(item["code"] for item in parsed["name_diagnostics"])),
            "item_name_status": parsed["item_name_status"],
            "point_indexes_preserved": True, "volume_rescaled": False,
            "vendor_basis": parsed["vendor_basis"], "volume_unit": parsed["volume_unit"],
            "amount_unit": parsed["amount_unit"], "mapping_verified": parsed["mapping_verified"],
            "eligible": parsed["eligible"],
        })
        source_files[str(raw_path.relative_to(ROOT))] = raw_sha
        source_files[str(receipt_path.relative_to(ROOT))] = digest(receipt_path)
    for path in (PARSER, ROOT / "backend/app/data/tonghuasun_provider.py",
                 ROOT / "backend/tests/test_tonghuasun_history.py", Path(__file__),
                 CAPTURE / "plan.json", CAPTURE / "producer_pins.json", CALENDAR):
        source_files[str(path.relative_to(ROOT))] = digest(path)
    return {
        "scope": "pure parser integration against eight frozen qualification raw bodies",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "parser_integration_passed": True, "capture_producer_pins_match": pins_valid,
        "requests_issued": 0, "database_opens": 0,
        "window": {"start": START, "end": END, "expected_dates": len(expected)},
        "observations": observations, "files_sha256": source_files,
        "source_qualified": False, "dataset_eligible": False, "M2_complete": False,
    }


if __name__ == "__main__":
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "provider_raw_parse_summary.json"
    summary = run()
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(summary, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({"parser_integration_passed": True, "raw_bodies": len(summary["observations"]),
                      "output": str(output)}, ensure_ascii=False))
