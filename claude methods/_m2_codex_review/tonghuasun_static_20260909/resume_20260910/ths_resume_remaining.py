"""Explicitly authorized continuation of original jobs 2..6; never rerun job 1."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import base64
import hashlib
import http.client
import importlib.util
import json
import subprocess
import time

HERE = Path(__file__).resolve().parent
PRIOR = HERE.parent
LIVE = HERE / "capture"
PINS = {
    "ths_long_history_probe.py": "1eb483b623458ac912d877e1f2cca6a7fb6bef343abbe35725374cc60b08ec67",
    "endpoint_identity_guard.py": "db6c3b6d4dc385cc39a05ad6a8d5cc1d0019d2a2b5988e0af22eea1a637b6483",
    "probe_delivery_manifest.json": "759c626d22886aac586972be2e4e73c57fed047a93378116ba4a1951d36214e5",
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_pinned(name, module_name):
    path = PRIOR / name
    if digest(path) != PINS[name]:
        raise RuntimeError("frozen_module_pin_mismatch")
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


base = load_pinned("ths_long_history_probe.py", "frozen_ths_probe")
guard = load_pinned("endpoint_identity_guard.py", "reviewed_endpoint_guard")


def remaining_jobs():
    return base.fixed_jobs()[1:]


def continuation_plan():
    return {
        "grant_id": base.GRANT, "continuation": "user_confirmed_after_401_stop",
        "authorized_client_restart": "project profile only, completed; user confirmed manual market login",
        "prior_attempts_consumed": 1, "max_new_attempts": 5, "max_cumulative_attempts": 6,
        "repeat_job_1": False, "jobs": remaining_jobs(), "retries": 0,
        "endpoint": base.BASE + base.ROUTE, "method": "POST",
        "request_deadline_seconds": base.TIMEOUT, "max_response_bytes": base.MAX_BYTES,
        "interval_after_completion_seconds": base.INTERVAL, "wall_limit_seconds": base.WALL_LIMIT,
        "market_data_only": True, "database_access": False, "production_writes": False,
        "live_trading": False, "vendor_basis": "unverified", "eligible": False,
    }


def verify_prior():
    manifest_path = PRIOR / "probe_delivery_manifest.json"
    if digest(manifest_path) != PINS[manifest_path.name]:
        raise base.StopProbe("old_delivery_manifest_changed")
    manifest = json.loads(manifest_path.read_bytes())
    for name, expected in manifest["artifacts"].items():
        if digest(PRIOR / name) != expected:
            raise base.StopProbe("old_evidence_changed")
    prior_summary_path = PRIOR / "ths_live_20260910/summary.json"
    old = json.loads(prior_summary_path.read_bytes())
    if old["rest_attempts_consumed"] != 1 or old["rest_attempts_not_issued"] != 5 or old["stop_reason"] != "http_status_401_stop_no_retry":
        raise base.StopProbe("prior_budget_not_expected")
    return {"prior_manifest_sha256": digest(manifest_path),
        "prior_summary_sha256": digest(prior_summary_path), "prior_artifacts_verified": len(manifest["artifacts"]),
        "prior_attempts_consumed": 1, "original_attempt_1_result": "HTTP 401, retained unchanged"}


def preflight():
    script = HERE / "ths_resume_preflight.ps1"
    encoded = base64.b64encode(script.read_text(encoding="utf-8-sig").encode("utf-16le")).decode("ascii")
    proc = subprocess.run([str(base.PREFLIGHT_HOST), "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
        capture_output=True, timeout=30, encoding="utf-8-sig", errors="strict")
    if proc.returncode:
        raise base.StopProbe("runtime_inventory_failed")
    try:
        result = json.loads(proc.stdout)
        launch = json.loads((HERE / "client_launch_receipt.json").read_bytes())
        host = result["host_process"]
        if result.get("passed") is not True or host["pid"] != launch["context"]["host_process_id"]:
            raise base.StopProbe("runtime_or_authorized_launch_identity_mismatch")
        endpoint_path = base.HOME / "runtime/endpoint.json"
        endpoint = json.loads(endpoint_path.read_bytes())
        endpoint_mtime = datetime.fromtimestamp(endpoint_path.stat().st_mtime, timezone.utc)
        checked = guard.validate_endpoint_identity(endpoint, current_pid=host["pid"],
            host_created_at=host["started_utc"], endpoint_mtime=endpoint_mtime)
        result["project_endpoint_identity"] = {"path": str(endpoint_path),
            "processId": endpoint.get("processId"), "startedAtUtc": endpoint.get("startedAtUtc"),
            "file_mtime_utc": endpoint_mtime.isoformat(), "gate": checked}
        if checked["passed"] is not True:
            raise base.StopProbe("project_endpoint_identity_or_freshness_failed")
    except (KeyError, ValueError, TypeError):
        raise base.StopProbe("runtime_metadata_unusable") from None
    return result


def fetch_remaining(job, token):
    canonical = lambda value: json.dumps(value, sort_keys=True, allow_nan=False)
    if canonical(job) not in {canonical(item) for item in remaining_jobs()}:
        raise base.StopProbe("request_not_in_remaining_plan")
    return base.fetch(job, token)


def capture():
    prior = verify_prior()
    expected = base.expected_keys()
    runtime = preflight()  # Includes project endpoint PID and freshness BEFORE reading a token.
    if LIVE.exists():
        raise base.StopProbe("continuation_already_claimed")
    token = base.local_credentials()
    LIVE.mkdir(exist_ok=False)
    base.write_json(LIVE / "authorization_and_plan.json", continuation_plan(), exclusive=True)
    base.write_json(LIVE / "prior_evidence.json", prior, exclusive=True)
    base.write_json(LIVE / "preflight.json", runtime, exclusive=True)
    base.write_json(LIVE / "expected_keys.json", expected, exclusive=True)
    producers = [Path(__file__), HERE / "ths_resume_preflight.ps1", HERE / "test_ths_resume_remaining.py",
        HERE / "client_launch_receipt.json", PRIOR / "ths_long_history_probe.py", PRIOR / "endpoint_identity_guard.py",
        base.MANIFEST, base.CALENDAR]
    base.write_json(LIVE / "producer_and_contract_pins.json", {str(p): digest(p) for p in producers}, exclusive=True)
    started = time.monotonic()
    receipts, reports = [], []
    stop_reason = None
    for job in remaining_jobs():
        if len(receipts) >= 5 or time.monotonic() - started + base.TIMEOUT > base.WALL_LIMIT:
            stop_reason = "attempt_or_wall_budget_exhausted"
            break
        if receipts:
            time.sleep(base.INTERVAL)
        receipt = {"job": job, "attempt_reserved_at_utc": datetime.now(timezone.utc).isoformat(),
            "cumulative_attempt_number": 1 + len(receipts) + 1, "state": "reserved_before_network"}
        base.write_json(LIVE / f"attempt_{job['id']}.json", receipt, exclusive=True)
        receipts.append(receipt)
        before = time.monotonic()
        try:
            status, raw = fetch_remaining(job, token)
            (LIVE / f"response_{job['id']}.bin").write_bytes(raw)
            receipt.update({"http_status": status, "raw_sha256": base.sha(raw), "raw_bytes": len(raw), "state": "received"})
            if status != 200:
                raise base.StopProbe(f"http_status_{status}_stop_no_retry")
            report = base.analyze(raw, job, expected[job["symbol"]])
            base.write_json(LIVE / f"analysis_{job['id']}.json", report, exclusive=True)
            reports.append(report)
            if any("identity" in error or "security" in error or "unusable_response" in error or "adjustment" in error for error in report["errors"]):
                raise base.StopProbe("response_contract_failure")
            print(json.dumps({"original_job": job["id"], "symbol": job["symbol"], "mode": job["mode"],
                "http_status": status, "rows": report["valid_row_count"], "first": report["first_date"], "last": report["last_date"],
                "coverage_observed_complete": report["coverage_observed_complete"], "errors": report["errors"]}), flush=True)
        except base.StopProbe as error:
            stop_reason = str(error)
        except (OSError, http.client.HTTPException):
            stop_reason = "transport_failed_or_timed_out_no_retry"
        finally:
            receipt["elapsed_seconds"] = round(time.monotonic() - before, 6)
            receipt["stop_reason"] = stop_reason
            base.write_json(LIVE / f"attempt_{job['id']}_completed.json", receipt, exclusive=True)
        if stop_reason:
            break
    pairs = {symbol: base.compare_pair(*[r for r in reports if r["symbol"] == symbol])
             for symbol in base.SYMBOLS if len([r for r in reports if r["symbol"] == symbol]) == 2}
    summary = {"grant_id": base.GRANT, "prior_rest_attempts": 1, "new_rest_attempts": len(receipts),
        "cumulative_rest_attempts": 1 + len(receipts), "rest_attempts_not_issued": 5 - len(receipts),
        "automatic_resume_allowed": False, "job_1_reissued": False, "stop_reason": stop_reason,
        "pairs": pairs, "SH600011_count": "original HTTP401; no successful count observation",
        "elapsed_seconds": round(time.monotonic() - started, 6),
        "m2_accepted": False, "vendor_basis": "unverified", "eligible": False}
    base.write_json(LIVE / "summary.json", summary, exclusive=True)
    print(json.dumps(summary), flush=True)
    return 1 if stop_reason else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture", action="store_true")
    args = parser.parse_args()
    try:
        if args.capture:
            raise SystemExit(capture())
        print(json.dumps(continuation_plan(), ensure_ascii=False, indent=2))
    except base.StopProbe as error:
        print(json.dumps({"stopped": str(error)}))
        raise SystemExit(2)
