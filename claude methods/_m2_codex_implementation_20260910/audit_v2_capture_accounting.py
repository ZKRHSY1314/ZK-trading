"""Account for every history attempt in the seven v2 capture partitions.

This supplements M2's rejection/lineage inventory without rewriting the reviewed
delivery. Identity-search requests and earlier capability probes are separate.
No SQLite, network, source parsing changes or dataset writes occur.
"""
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import contract_v2 as c

GROUPS = ("qualification_capture", "remaining_capture", "remaining_capture_after_login",
          "remaining_capture_residual32", "remaining_capture_residual27", "remaining_capture_identity24", "warmup3_capture")


def run():
    bundle_path = c.HERE / "qualification_v2_reviewed.json"
    c.require(c.sha(bundle_path) == "992bd79ce9d2e38d1a0a8ae2f9890cd26daebcd3d2ab664d5caab171ec3e0f37", "qualified_bundle_changed")
    bundle = c.read(bundle_path)
    qualified = {cap["raw_sha256"] for scope in bundle["scopes"] for cap in scope["captures"]}
    attempts, groups, used_primary = [], [], set()
    pins = {str(bundle_path): c.sha(bundle_path)}
    for group in GROUPS:
        directory = c.HERE / group
        summary = c.read(directory / "summary.json")
        plan = c.read(directory / "plan.json")
        completed = sorted(directory.glob("completed_*.json"))
        c.require(summary["attempts"] == len(completed), "attempt_count_disagrees_with_receipts")
        c.pin_file(pins, directory / "summary.json")
        c.pin_file(pins, directory / "plan.json")
        groups.append(dict(directory=group, issued=len(completed), stop_reason=summary["stop_reason"],
            unissued_at_this_partition_stop=summary["unissued"],
            note="Residual unissued sets overlap across recovery plans and must not be added together."))
        for receipt_path in completed:
            receipt = c.read(receipt_path)
            job = receipt["job"]
            c.require(job in plan["jobs"], "receipt_job_outside_plan")
            raw_path = directory / ("response_" + str(job["id"]) + ".bin")
            c.pin_file(pins, receipt_path)
            c.pin_file(pins, raw_path, receipt["raw_sha256"])
            status, reason = receipt["http_status"], receipt.get("stop_reason")
            adjustment = job["payload"]["adjustment"]
            rows = None
            if status == 200 and reason is None:
                raw = c.read(raw_path)
                c.require(raw.get("ok") is True and raw.get("error") is None, "successful_receipt_has_failed_response")
                items = raw["data"]["items"]
                c.require(len(items) == 1 and bool(items[0]["points"]), "successful_series_empty")
                rows = len(items[0]["points"])
                if adjustment == 0:
                    category = "qualified_primary_capture"
                    c.require(receipt["raw_sha256"] in qualified, "successful_primary_not_accounted_for_by_qualification")
                    used_primary.add(receipt["raw_sha256"])
                else:
                    c.require(group == "qualification_capture" and adjustment in (1, 2), "unexpected_adjusted_capture")
                    category = "adjustment_control_only"
            else:
                category = "rejected_capture_attempt"
                c.require(receipt["raw_sha256"] not in qualified, "failed_attempt_entered_qualification")
            attempts.append(dict(directory=group, job_id=job["id"], symbol=job["symbol"],
                native_identity=job["host_full_code"], adjustment=adjustment, http_status=status,
                stop_reason=reason, category=category, served_points_if_successful=rows,
                raw_sha256=receipt["raw_sha256"], receipt_sha256=c.sha(receipt_path), raw_bytes=raw_path.stat().st_size))
    c.require(used_primary == qualified, "qualification_capture_inventory_not_exhaustively_accounted_for")
    primary_rows = sum(a["served_points_if_successful"] for a in attempts if a["category"] == "qualified_primary_capture")
    control_rows = sum(a["served_points_if_successful"] for a in attempts if a["category"] == "adjustment_control_only")
    overlap = sum(item["overlap"] for item in bundle["warmup_extension"])
    earlier = sum(item["retained_audit_only"] for item in bundle["warmup_extension"])
    c.require(primary_rows - overlap - earlier == bundle["rows_per_view"], "received_to_selected_row_accounting_mismatch")
    return dict(schema="m2.v2.capture_accounting.v1", generated_at_utc=datetime.now(timezone.utc).isoformat(),
        scope="Seven history-capture partitions used for v2 staging; identity searches and older capability probes excluded and separately retained",
        total_history_attempts=len(attempts), categories=dict(Counter(a["category"] for a in attempts)),
        served_primary_points=primary_rows, served_adjustment_control_points=control_rows,
        duplicate_overlap_points_retained_as_evidence=overlap, earlier_unselected_warmup_points=earlier,
        selected_rows_per_store=bundle["rows_per_view"], row_accounting_passed=True,
        failed_attempts=[a for a in attempts if a["category"] == "rejected_capture_attempt"],
        partition_summaries=groups, attempts=attempts, input_pins=pins, producer_sha256=c.sha(__file__),
        classification_only=True, qualification_modified=False, dataset_modified=False,
        network_requests=0, database_connections=0, live_trading=False)


if __name__ == "__main__":
    result = run()
    target = c.HERE / "v2_capture_accounting.json"
    c.old.StagingRun._json_new(target, result)
    print(json.dumps({k:result[k] for k in ("total_history_attempts","categories","served_primary_points",
        "served_adjustment_control_points","duplicate_overlap_points_retained_as_evidence",
        "earlier_unselected_warmup_points","selected_rows_per_store","row_accounting_passed")}, ensure_ascii=False))
