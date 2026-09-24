"""Three bounded native historical requests under the approved v2 warmup contract."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import subprocess
import time
import collect_identity24 as transport

HERE = Path(__file__).resolve().parent
base = transport.base
START, END = "2022-05-01", "2023-09-01"
SYMBOLS = ("SZ002656", "SH600110", "SH600226")
PINS = {
    "capture.py": "c87217e73ead9c8a7d5f0d05919d0aa664401582ab392e0ce49715342903ba40",
    "collect_identity24.py": "97157369add2956480eaf345f568b26a392ac4f1063cd6a751bf4e68c272801b",
    "M2_ACCEPTANCE_REVISION_PROPOSAL.md": "939357d0e44428bc1f7f074e1edc60cb762b6d80fc4f100f411ac2c2849a35c1",
}
PARSER = HERE.parents[1] / "backend/app/data/tonghuasun_history.py"
PARSER_PIN = "605d65965b1aee56f0f64c5c2446078aefa8d237d7a3d09b5f7403e4a24c2779"


def parser_module():
    if base.sha(PARSER.read_bytes()) != PARSER_PIN:
        raise base.StopCapture("parser_pin_mismatch")
    spec = importlib.util.spec_from_file_location("m2_warmup_parser", PARSER)
    parser = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = parser
    spec.loader.exec_module(parser)
    return parser


def plan():
    transport.pinned_inputs()
    for name, pin in PINS.items():
        if base.sha((HERE / name).read_bytes()) != pin:
            raise base.StopCapture("retained_input_changed")
    authority = json.loads((HERE / "acceptance_v2_authority.json").read_bytes())
    if authority["user_reply"] != "可以" or authority["proposal_sha256"] != PINS["M2_ACCEPTANCE_REVISION_PROPOSAL.md"]:
        raise base.StopCapture("revision_authority_mismatch")
    parser = parser_module()
    jobs = []
    for i, symbol in enumerate(SYMBOLS, 1):
        spec = parser.SecuritySpec.stock(symbol)
        payload = parser.build_history_request(spec, START, END)
        payload["security"] = {"hostFullCode": spec.host_full_code}
        jobs.append({"id": i, "symbol": symbol, "host_full_code": spec.host_full_code,
                     "payload": payload})
    return {"schema": "m2.warmup3_plan.v2", "jobs": jobs, "max_attempts": 3,
            "start": START, "end": END, "minimum_actual_warmup_observations": 250,
            "request_timeout_seconds": base.TIMEOUT, "max_response_bytes": 8 * 1024 * 1024,
            "min_seconds_after_completion": base.INTERVAL, "batch_deadline_seconds": 600,
            "retries": 0, "market_only": True, "database_access": False, "live_trading": False,
            "authority_sha256": base.sha((HERE / "acceptance_v2_authority.json").read_bytes()),
            "manifest_sha256": transport.MANIFEST_PIN, "calendar_sha256": transport.CALENDAR_PIN}


def digest_plan(value):
    return base.sha(json.dumps(value, sort_keys=True, allow_nan=False).encode())


def run(reviewed_plan_sha):
    proposed = plan()
    if digest_plan(proposed) != reviewed_plan_sha:
        raise base.StopCapture("reviewed_plan_hash_mismatch")
    runtime = transport.preflight()
    out = HERE / "warmup3_capture"
    out.mkdir(exist_ok=False)
    parser = parser_module()
    paths = [Path(__file__), HERE / "test_collect_warmup3.py", HERE / "acceptance_v2_authority.json",
             PARSER, transport.MANIFEST, transport.CALENDAR, HERE / "preflight_residual27.ps1",
             base.PRIOR / "endpoint_identity_guard.py", *[HERE / name for name in PINS]]
    pins = {str(path.resolve()): base.sha(path.read_bytes()) for path in paths}
    base.write_json(out / "plan.json", proposed)
    base.write_json(out / "producer_pins.json", pins)
    base.write_json(out / "initial_preflight.json", runtime)
    started, attempted, stop = time.monotonic(), 0, None
    for job in proposed["jobs"]:
        if attempted:
            time.sleep(base.INTERVAL)
        try:
            if any(base.sha(Path(path).read_bytes()) != pin for path, pin in pins.items()):
                raise base.StopCapture("producer_changed")
            current = transport.preflight()
            if current["endpoint_sha256"] != runtime["endpoint_sha256"]:
                raise base.StopCapture("endpoint_generation_changed")
            if time.monotonic() - started + base.TIMEOUT > 600:
                raise base.StopCapture("batch_deadline")
            token = base.credentials(current)
        except (base.StopCapture, OSError, subprocess.SubprocessError) as exc:
            stop = str(exc) if isinstance(exc, base.StopCapture) else "preflight_io_failure"
            break
        receipt = {"job": job, "state": "reserved_before_http", "reserved_at": datetime.now(timezone.utc).isoformat()}
        base.write_json(out / f"preflight_{job['id']}.json", current)
        base.write_json(out / f"request_{job['id']}.json", job["payload"])
        receipt["request_sha256"] = base.sha((out / f"request_{job['id']}.json").read_bytes())
        base.write_json(out / f"attempt_{job['id']}.json", receipt)
        attempted += 1
        try:
            status, raw = base.fetch(job["payload"], token)
            with (out / f"response_{job['id']}.bin").open("xb") as handle:
                handle.write(raw)
            receipt.update(http_status=status, raw_sha256=base.sha(raw), raw_bytes=len(raw), observed_at=datetime.now(timezone.utc).isoformat())
            if status != 200:
                raise base.StopCapture("http_status_" + str(status))
            decoded = parser.parse_history_response(raw, parser.SecuritySpec.stock(job["symbol"]), START, END)
            if len(decoded["rows"]) < 250:
                raise base.StopCapture("actual_warmup_depth_below_250")
            receipt.update(state="received_unqualified", source_security=decoded["response_identity"],
                           row_count=len(decoded["rows"]), first_date=decoded["first_date"], last_date=decoded["last_date"])
        except base.StopCapture as exc:
            stop = str(exc)
        except parser.HistoryValidationError as exc:
            stop = "parser_" + exc.code
        except Exception as exc:
            stop = "request_failed_" + type(exc).__name__
        finally:
            del token
            receipt["stop_reason"] = stop
            base.write_json(out / f"completed_{job['id']}.json", receipt)
            print(json.dumps({"symbol": job["symbol"], "rows": receipt.get("row_count"), "stop_reason": stop}), flush=True)
        if stop:
            break
    summary = {"attempts": attempted, "unissued": 3 - attempted, "stop_reason": stop,
               "elapsed_seconds": time.monotonic() - started, "eligible": False,
               "database_access": False, "live_trading": False}
    base.write_json(out / "summary.json", summary)
    print(json.dumps(summary), flush=True)
    return int(stop is not None)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--capture", action="store_true"); ap.add_argument("--sha")
    args = ap.parse_args()
    try:
        if args.capture:
            raise SystemExit(run(args.sha))
        proposed = plan()
        print(json.dumps({"plan": proposed, "canonical_sha256": digest_plan(proposed)}, indent=2))
    except (base.StopCapture, FileExistsError) as exc:
        print(json.dumps({"stopped": str(exc) if isinstance(exc, base.StopCapture) else "existing_claim_no_resume"}))
        raise SystemExit(2)
