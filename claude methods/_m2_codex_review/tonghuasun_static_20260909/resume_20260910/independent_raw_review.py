"""Independent stdlib-only replay of retained evidence, with no producer imports.

Reads only the audit evidence, pinned producer source bytes, and the two exact
calendar/manifest contract files. No network, configuration, tokens, services,
database access, or production mutation. Writes only this review's JSON output.
"""
from collections import Counter
import csv
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import io
import json
from pathlib import Path
import re
import unicodedata


HERE = Path(__file__).resolve().parent
STATIC = HERE.parent
PROJECT = STATIC.parents[2]
CAPTURE = HERE / "capture"
OLD = STATIC / "ths_live_20260910"
PILOT = PROJECT / "claude methods/_m1_closure/pilot_symbols.csv"
CALENDAR = PROJECT / "backend/.venv/Lib/site-packages/akshare/file_fold/calendar.json"
START, END = "2022-08-24", "2026-09-04"
CHINA = timezone(timedelta(hours=8))
SYMBOLS = {"SH600011": "600011.SH", "BJ920000": "920000.BJ", "SH000300": "000300.SH"}
FIELDS = ("open", "high", "low", "latest", "transaction_volume", "transaction_amount")


def require(condition, code):
    if not condition:
        raise ValueError(code)


def safe_path(path):
    path = Path(path).resolve()
    require(path.is_relative_to(STATIC) or path in (PILOT, CALENDAR), "read_outside_review_allowlist")
    return path


def raw_bytes(path):
    return safe_path(path).read_bytes()


def digest(path):
    return hashlib.sha256(raw_bytes(path)).hexdigest()


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate_json_key")
        result[key] = value
    return result


def reject_constant(value):
    raise ValueError("nonfinite_json_constant")


def decode(raw):
    return json.loads(raw, parse_float=Decimal, parse_constant=reject_constant, object_pairs_hook=unique_object)


def read_json(path):
    return decode(raw_bytes(path))


def verify_pins(path):
    pins = read_json(path)
    checks = [{"path": name, "expected_sha256": expected, "actual_sha256": digest(name)} for name, expected in pins.items()]
    for check in checks:
        check["matched"] = check["expected_sha256"] == check["actual_sha256"]
    return {"count": len(checks), "all_matched": all(c["matched"] for c in checks), "checks": checks}


def expected_keys():
    entries = {row["symbol"]: row for row in csv.DictReader(io.StringIO(raw_bytes(PILOT).decode("utf-8-sig")))}
    calendar = read_json(CALENDAR)
    labels = [str(row["trade_date"]) if isinstance(row, dict) else str(row) for row in calendar]
    dates = [datetime.strptime(day, "%Y%m%d" if re.fullmatch(r"\d{8}", day) else "%Y-%m-%d").date().isoformat() for day in labels]
    require(len(dates) == len(set(dates)), "duplicate_calendar_date")
    for day in dates:
        require(datetime.strptime(day, "%Y-%m-%d").date().isoformat() == day, "invalid_calendar_date")
    result = {}
    for symbol in SYMBOLS:
        entry = entries[symbol]
        benchmark = entry["stratum"] == "benchmark"
        listing, delisting = entry.get("list_date"), entry.get("delist_date")
        require(benchmark or bool(listing), "missing_listing_date")
        eligible = sorted(day for day in dates if START <= day <= END and
            (benchmark or day >= listing) and (not delisting or day <= delisting))
        result[symbol] = {"listing": listing or None, "benchmark": benchmark,
            "research": [day for day in eligible if day >= "2023-09-04"],
            "warmup": [day for day in eligible if day <= "2023-09-01"]}
    return result


def point_day(point):
    value = point["values"]["date_time"]
    require(type(value) in (int, str), "date_time_type")
    text = str(value)
    require(re.fullmatch(r"\d{8}", text) is not None, "date_time_format")
    day = datetime.strptime(text, "%Y%m%d").date().isoformat()
    stamp = datetime.fromisoformat(point["timestampUtc"].replace("Z", "+00:00"))
    require(stamp.tzinfo is not None and stamp.utcoffset() is not None, "timestamp_timezone_missing")
    require(stamp.astimezone(CHINA).date().isoformat() == day, "dual_date_disagreement")
    return day


def numeric(value):
    require(type(value) in (int, str, Decimal), "numeric_type_invalid")
    number = Decimal(value)
    require(number.is_finite(), "numeric_not_finite")
    return number


def review_response(job_id, contracts):
    reserved = read_json(CAPTURE / f"attempt_{job_id}.json")
    receipt = read_json(CAPTURE / f"attempt_{job_id}_completed.json")
    job = receipt["job"]
    raw = raw_bytes(CAPTURE / f"response_{job_id}.bin")
    payload = decode(raw)
    issues = []
    rows, names = [], []
    require(receipt["raw_sha256"] == hashlib.sha256(raw).hexdigest(), "receipt_raw_hash_mismatch")
    require(receipt["raw_bytes"] == len(raw), "receipt_raw_size_mismatch")
    require(reserved["job"] == job and reserved["state"] == "reserved_before_network", "reservation_mismatch")
    require(reserved["attempt_reserved_at_utc"] == receipt["attempt_reserved_at_utc"], "reservation_time_mismatch")
    require(receipt["state"] == "received" and receipt["cumulative_attempt_number"] == job_id, "completion_state_mismatch")
    require(payload.get("ok") is True, "response_envelope_unsuccessful")
    items = payload["data"]["items"]
    expected_code = SYMBOLS[job["symbol"]]
    identities = [{"full_code": item.get("security", {}).get("fullCode"),
        "point_count": len(item.get("points", [])), "name_empty": item.get("security", {}).get("name") == ""} for item in items]
    if len(items) != 1:
        issues.append("expected_one_security_item")
    else:
        if items[0]["security"].get("fullCode") != expected_code:
            issues.append("item_security_mismatch")
        for index, point in enumerate(items[0]["points"]):
            try:
                values = point["values"]
                require(values.get("full_code") == expected_code, "point_security_mismatch")
                day = point_day(point)
                numbers = {field: numeric(values[field]) for field in FIELDS}
                require(all(numbers[field] > 0 for field in FIELDS[:4]), "nonpositive_price")
                require(numbers["low"] <= min(numbers["open"], numbers["latest"]) <=
                    max(numbers["open"], numbers["latest"]) <= numbers["high"], "ohlc_order_invalid")
                require(numbers["transaction_volume"] >= 0 and numbers["transaction_amount"] >= 0, "negative_liquidity")
                rows.append({"date": day, "values": numbers})
                names.append(values.get("security_name"))
            except (ValueError, KeyError, TypeError, ArithmeticError) as error:
                issues.append({"point_index": index, "error_type": type(error).__name__})
    dates = [row["date"] for row in rows]
    keys = set(dates)
    duplicates = sorted(day for day, count in Counter(dates).items() if count > 1)
    if duplicates:
        issues.append("duplicate_dates")
    expected = contracts[job["symbol"]]
    target = set(expected["research"] + expected["warmup"])
    missing = sorted(target - keys)
    unexpected = sorted(day for day in keys if START <= day <= END and day not in target)
    before = sorted(day for day in keys if day < START)
    after = sorted(day for day in keys if day > END)
    if unexpected or after or (job["mode"] == "range" and before):
        issues.append("unexpected_request_window_keys")
    if missing:
        issues.append("target_dates_missing")
    nonempty_names = [name for name in names if isinstance(name, str) and name]
    private_names = [name for name in nonempty_names if all(unicodedata.category(char) == "Co" for char in name)]
    private_codes = sorted({f"U+{ord(char):04X}" for name in private_names for char in name})
    point_count = sum(len(item.get("points", [])) for item in items)
    out = {"original_job": job_id, "symbol": job["symbol"], "mode": job["mode"],
        "http_status": receipt["http_status"], "raw_bytes": len(raw), "raw_sha256": hashlib.sha256(raw).hexdigest(),
        "raw_receipt_hash_and_size_match": True, "reservation_and_completion_match": True,
        "item_count": len(items), "identities": identities, "point_count": point_count,
        "valid_ohlcv_amount_rows": len(rows), "unique_dates": len(keys), "duplicate_dates": duplicates,
        "ascending": dates == sorted(dates), "first_date": min(keys) if keys else None,
        "last_date": max(keys) if keys else None, "more_than_500_unique_dates": len(keys) > 500,
        "target_expected": len(target), "target_present": len(target & keys), "target_missing": missing,
        "unexpected_target_dates": unexpected, "before_target_count": len(before), "after_end_dates": after,
        "research_expected": len(expected["research"]), "research_present": len(set(expected["research"]) & keys),
        "warmup_expected": len(expected["warmup"]), "warmup_present": len(set(expected["warmup"]) & keys),
        "requested_limit": job["payload"]["limit"], "returned_minus_requested_limit": point_count - job["payload"]["limit"],
        "count_exceeds_requested_limit": job["mode"] == "count" and point_count > job["payload"]["limit"],
        "adjustment_requested": job["payload"]["adjustment"], "adjustment_echo_present": "adjustment" in payload["data"],
        "security_name_private_use_only_rows": len(private_names), "security_name_private_use_codepoints": private_codes,
        "issues": issues, "observed_target_complete_and_structurally_valid": bool(target) and not issues,
        "vendor_basis": "unverified", "historical_identity": "unverified", "volume_unit": "unverified",
        "amount_unit": "unverified", "eligible": False}
    saved = read_json(CAPTURE / f"analysis_{job_id}.json")
    out["independent_counts_agree_with_saved_analysis"] = (
        len(rows) == saved["valid_row_count"] and len(keys) == saved["unique_date_count"] and
        out["observed_target_complete_and_structurally_valid"] == saved["coverage_observed_complete"])
    return out, rows


def main():
    new_pins = verify_pins(CAPTURE / "producer_and_contract_pins.json")
    old_pins = verify_pins(OLD / "producer_and_contract_pins.json")
    prior_ref = read_json(CAPTURE / "prior_evidence.json")
    old_manifest = read_json(STATIC / "probe_delivery_manifest.json")
    old_artifacts = {name: digest(STATIC / name) == expected for name, expected in old_manifest["artifacts"].items()}
    require(digest(STATIC / "probe_delivery_manifest.json") == prior_ref["prior_manifest_sha256"], "prior_manifest_pin_mismatch")
    require(digest(OLD / "summary.json") == prior_ref["prior_summary_sha256"], "prior_summary_pin_mismatch")
    contracts = expected_keys()
    require(contracts == read_json(CAPTURE / "expected_keys.json"), "independent_expected_keys_disagreement")
    require(contracts == read_json(OLD / "expected_keys.json"), "old_expected_keys_disagreement")
    reports, parsed_rows = {}, {}
    for job_id in (2, 3, 4, 5):
        reports[str(job_id)], parsed_rows[job_id] = review_response(job_id, contracts)
    count = {row["date"]: row["values"] for row in parsed_rows[3]}
    ranged = {row["date"]: row["values"] for row in parsed_rows[4]}
    common = sorted(set(count) & set(ranged))
    differing = [day for day in common if count[day] != ranged[day]]
    old_receipt = read_json(OLD / "attempt_1_completed.json")
    old_summary = read_json(OLD / "summary.json")
    summary = read_json(CAPTURE / "summary.json")
    old_raw = raw_bytes(OLD / "response_1.bin")
    require(hashlib.sha256(old_raw).hexdigest() == old_receipt["raw_sha256"] and len(old_raw) == old_receipt["raw_bytes"], "old_raw_receipt_mismatch")
    reserved_ids = sorted(int(p.stem.split("_")[1]) for p in CAPTURE.glob("attempt_*.json") if re.fullmatch(r"attempt_\d+", p.stem))
    completed_ids = sorted(int(p.stem.split("_")[1]) for p in CAPTURE.glob("attempt_*_completed.json"))
    budget = {"prior_attempt_ids": [1], "prior_http_status": old_receipt["http_status"],
        "new_reserved_ids": reserved_ids, "new_completed_ids": completed_ids,
        "cumulative_attempts": 1 + len(reserved_ids), "unissued_original_jobs": [6],
        "job_1_not_reissued": 1 not in reserved_ids, "job_6_files_absent": not any(CAPTURE.glob("*6*")),
        "summary_matches_receipts": reserved_ids == [2, 3, 4, 5] and completed_ids == reserved_ids and
            old_summary["rest_attempts_consumed"] == 1 and old_receipt["http_status"] == 401 and
            summary["prior_rest_attempts"] == 1 and summary["new_rest_attempts"] == 4 and
            summary["cumulative_rest_attempts"] == 5 and summary["rest_attempts_not_issued"] == 1 and
            summary["stop_reason"] == "response_contract_failure",
        "stopped_on_job_5_contract_failure": read_json(CAPTURE / "attempt_5_completed.json")["stop_reason"] == "response_contract_failure",
        "automatic_resume_allowed": False}
    output = {"review_kind": "independent_stdlib_raw_replay_without_producer_imports",
        "reviewer_source_sha256": digest(Path(__file__)), "new_producer_and_contract_pins": new_pins,
        "old_producer_and_contract_pins": old_pins, "old_delivery_artifacts_count": len(old_artifacts),
        "old_delivery_artifacts_all_matched": all(old_artifacts.values()),
        "old_delivery_artifact_mismatches": [name for name, matched in old_artifacts.items() if not matched],
        "expected_keys_independently_reconstructed_from_pinned_csv_calendar": True,
        "old_raw_sha256": hashlib.sha256(old_raw).hexdigest(), "old_raw_bytes": len(old_raw),
        "responses": reports,
        "BJ920000_count_range_comparison": {"overlap_dates": len(common), "numeric_mismatch_dates": differing,
            "range_dates_absent_from_count": sorted(set(ranged) - set(count)),
            "count_only_dates": len(set(count) - set(ranged)), "compared_fields": list(FIELDS),
            "price_basis_proved": False, "historical_code_migration_proved": False},
        "SH600011_count_range_comparison": {"available": False, "reason": "original_count_HTTP401_never_reissued"},
        "budget": budget, "count_limit_finding": "Job 3 requested 1200 and returned 1201 unique dates; cause not established.",
        "index_finding": "Job 5 returned HTTP 200 with two SH/SZ security items and zero points; unusable index evidence, not success.",
        "scope_limitations": ["Three structural row checks do not establish adjustment basis or units.",
            "Current BJ full_code echoed on old dates does not prove historical code migration continuity.",
            "All observed security_name values are private-use characters and item names are empty.",
            "No successful SH600011 count response or SH000300 long-history response was observed."],
        "vendor_basis": "unverified", "historical_identity": "unverified", "volume_unit": "unverified",
        "amount_unit": "unverified", "eligible": False, "m2_accepted": False}
    output["evidence_consistency_passed"] = new_pins["all_matched"] and old_pins["all_matched"] and all(old_artifacts.values()) and budget["summary_matches_receipts"] and all(r["independent_counts_agree_with_saved_analysis"] for r in reports.values())
    (HERE / "independent_raw_review.json").write_text(json.dumps(output, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"evidence_consistency_passed": output["evidence_consistency_passed"],
        "rows": {key: value["valid_ohlcv_amount_rows"] for key, value in reports.items()},
        "bj_overlap": len(common), "bj_mismatches": len(differing), "budget": budget,
        "producer_pins": [new_pins["count"], old_pins["count"]], "old_artifacts": len(old_artifacts)}))


if __name__ == "__main__":
    main()
