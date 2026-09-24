"""One approved, isolated six-REST-attempt Tonghuashun market-data probe.

No project imports, SQLite, trading APIs, source fallback, proxy, retry, or service actions.
Default invocation only prints the fixed plan. --capture requires passing offline review.
"""
from __future__ import annotations
import argparse
import csv
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import http.client
import io
import json
from pathlib import Path
import re
import socket
import subprocess
import threading
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
LIVE = HERE / "ths_live_20260910"
HOME = Path(r"D:\TonghuasunCodex")
PREFLIGHT_HOST = Path(r"C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\powershell\pwsh.exe")
HOST = "127.0.0.1"
PORT = 17180
ROUTE = "/api/v2/quotes/candle"
BASE = f"http://{HOST}:{PORT}"
GRANT = "M2-THS-SIX-READS-20260910"
SYMBOLS = {"SH600011": "600011.SH", "BJ920000": "920000.BJ", "SH000300": "000300.SH"}
CHINA = timezone(timedelta(hours=8))
START = "2022-08-24"
END = "2026-09-04"
START_UTC = "2022-08-23T16:00:00Z"
END_UTC = "2026-09-04T15:59:59.999Z"
FIELDS = ["full_code", "security_name", "open", "high", "low", "latest", "transaction_volume", "transaction_amount", "date_time"]
NUMBERS = {"open": "open", "high": "high", "low": "low", "close": "latest", "volume": "transaction_volume", "amount": "transaction_amount"}
MAX_BYTES = 8 * 1024 * 1024
MAX_ATTEMPTS = 6
TIMEOUT = 30.0
INTERVAL = 1.5
WALL_LIMIT = 900.0
MANIFEST = ROOT / "claude methods/_m1_closure/pilot_symbols.csv"
CALENDAR = ROOT / "backend/.venv/Lib/site-packages/akshare/file_fold/calendar.json"
MANIFEST_PIN = "97e251ae84fc927486127a96b4966ed8fc59fac0b744b7d6f186b2b1548886fe"
CALENDAR_PIN = "f1f1ce33c5cceb5c530c3271fc951405cb5624d2f30becec85dc7a85fd47e656"
ADAPTER_PIN = "19fbd89528ebe933cee267de34d63171afd47aef230132bd3574a3b81883469b"


class StopProbe(Exception):
    """Errors are fixed local codes, never raw server text or credentials."""


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def write_json(path, data, *, exclusive=False):
    with path.open("x" if exclusive else "w", encoding="utf-8", newline="\n") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")
        handle.flush()
        import os
        os.fsync(handle.fileno())


def fixed_jobs():
    result = []
    for symbol, full in SYMBOLS.items():
        for mode in ("count", "range"):
            result.append({"id": len(result) + 1, "symbol": symbol, "mode": mode,
                "payload": {"market": 1, "security": {"market": 1, "code": full[:6], "fullCode": full},
                    "codes": [full], "startTimeUtc": START_UTC if mode == "range" else None,
                    "endTimeUtc": END_UTC, "limit": 1200, "fields": FIELDS[:], "period": 7, "adjustment": 0}})
    return result


def plan():
    return {"grant_id": GRANT, "authorization": "User confirmed the immediately preceding six-request proposal in this Codex task on 2026-09-10 Asia/Taipei.",
        "endpoint": BASE + ROUTE, "method": "POST", "max_rest_attempts": MAX_ATTEMPTS,
        "plugin_internal_attempts": "not controlled or counted by REST attempt budget",
        "socket_and_request_deadline_seconds": TIMEOUT, "total_wall_limit_seconds": WALL_LIMIT,
        "min_seconds_after_completion": INTERVAL, "retries": 0, "redirects": False,
        "proxy": False, "database_access": False, "production_writes": False,
        "live_trading": False, "adjustment_requested": "none", "vendor_basis": "unverified",
        "jobs": fixed_jobs()}


def expected_keys():
    raw_m, raw_c = MANIFEST.read_bytes(), CALENDAR.read_bytes()
    if sha(raw_m) != MANIFEST_PIN or sha(raw_c) != CALENDAR_PIN:
        raise StopProbe("frozen_input_pin_mismatch")
    rows = list(csv.DictReader(io.StringIO(raw_m.decode("utf-8-sig"))))
    entries = {row["symbol"]: row for row in rows}
    calendar = json.loads(raw_c)
    days = [date.fromisoformat(str(v.get("trade_date")) if isinstance(v, dict) else str(v)).isoformat() for v in calendar]
    if len(days) != len(set(days)):
        raise StopProbe("duplicate_calendar_keys")
    result = {}
    for symbol in SYMBOLS:
        entry = entries[symbol]
        benchmark = entry["stratum"] == "benchmark"
        listing = entry.get("list_date")
        if not benchmark and not listing:
            raise StopProbe("unknown_listing_contract")
        eligible = [d for d in days if START <= d <= END and (benchmark or d >= listing)
                    and (not entry.get("delist_date") or d <= entry["delist_date"])]
        result[symbol] = {"listing": listing or None, "benchmark": benchmark,
            "research": [d for d in eligible if d >= "2023-09-04"],
            "warmup": [d for d in eligible if d <= "2023-09-01"]}
    return result


def date_value(value, *, require_timezone=False):
    if value is None or isinstance(value, bool):
        raise ValueError("missing_date")
    text = str(value).strip()
    if re.fullmatch(r"\d{8}", text) and not require_timezone:
        return datetime.strptime(text, "%Y%m%d").date().isoformat()
    if re.fullmatch(r"\d{14}", text) and not require_timezone:
        return datetime.strptime(text, "%Y%m%d%H%M%S").date().isoformat()
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if require_timezone and parsed.tzinfo is None:
        raise ValueError("timestamp_timezone_missing")
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(CHINA)
    return parsed.date().isoformat()


def number(value):
    if isinstance(value, bool) or value is None or not isinstance(value, (str, int, float)):
        raise ValueError("missing_or_invalid_number")
    try:
        result = Decimal(str(value))
    except InvalidOperation:
        raise ValueError("invalid_number") from None
    if not result.is_finite():
        raise ValueError("nonfinite_number")
    return result


def analyze(raw, job, expected):
    errors, rows = [], []
    output = {"symbol": job["symbol"], "mode": job["mode"], "raw_sha256": sha(raw),
        "raw_bytes": len(raw), "errors": errors, "rows": rows,
        "vendor_basis": "unverified", "historical_identity": "unverified",
        "volume_unit": "unverified", "amount_unit": "unverified", "eligible": False}
    try:
        def reject_constant(_value):
            raise ValueError("nonfinite_json_constant")
        envelope = json.loads(raw, parse_constant=reject_constant)
        if not isinstance(envelope, dict) or envelope.get("ok") is not True:
            raise ValueError("api_envelope_not_success")
        data = envelope["data"]
        if not isinstance(data, dict):
            raise ValueError("invalid_data_object")
        output["adjustment_echo"] = data.get("adjustment")
        if data.get("adjustment") is not None and (isinstance(data["adjustment"], bool) or data["adjustment"] != 0):
            errors.append("adjustment_echo_mismatch")
        items = data["items"]
        if not isinstance(items, list) or len(items) != 1:
            raise ValueError("expected_exactly_one_security_item")
        item = items[0]
        identity = item.get("security", {})
        full_code = job["payload"]["security"]["fullCode"]
        output["response_full_code"] = identity.get("fullCode")
        if identity.get("fullCode") != full_code:
            errors.append("response_security_identity_mismatch_or_missing")
        points = item.get("points")
        if not isinstance(points, list):
            raise ValueError("points_not_a_list")
        output["point_count"] = len(points)
        for index, point in enumerate(points):
            try:
                values = point["values"]
                if not isinstance(values, dict):
                    raise ValueError("invalid_values")
                if values.get("full_code") is not None and values["full_code"] != full_code:
                    raise ValueError("point_security_mismatch")
                value_date = values.get("date_time")
                timestamp = point.get("timestampUtc")
                day = date_value(value_date) if value_date is not None else date_value(timestamp, require_timezone=True)
                if value_date is not None and timestamp is not None and date_value(timestamp, require_timezone=True) != day:
                    raise ValueError("timestamp_trade_date_disagreement")
                parsed = {k: number(values[v]) for k, v in NUMBERS.items() if values.get(v) is not None}
                if any(k not in parsed for k in ("open", "high", "low", "close")):
                    raise ValueError("missing_ohlc")
                if any(parsed[k] <= 0 for k in ("open", "high", "low", "close")):
                    raise ValueError("nonpositive_ohlc")
                if parsed["high"] < max(parsed["open"], parsed["close"], parsed["low"]) or parsed["low"] > min(parsed["open"], parsed["close"]):
                    raise ValueError("ohlc_ordering")
                if any(parsed.get(k, 0) < 0 for k in ("volume", "amount")):
                    raise ValueError("negative_volume_or_amount")
                if not expected["benchmark"] and any(k not in parsed for k in ("volume", "amount")):
                    raise ValueError("missing_stock_volume_or_amount")
                rows.append({"index": index, "date": day, **{k: str(v) for k, v in parsed.items()}})
            except (ValueError, TypeError, KeyError, AttributeError, OverflowError) as exc:
                safe_codes = {"point_security_mismatch", "timestamp_trade_date_disagreement", "missing_ohlc",
                    "nonpositive_ohlc", "ohlc_ordering", "negative_volume_or_amount", "missing_stock_volume_or_amount",
                    "missing_or_invalid_number", "invalid_number", "nonfinite_number", "invalid_values", "timestamp_timezone_missing"}
                code = str(exc) if isinstance(exc, ValueError) and str(exc) in safe_codes else "invalid_point"
                errors.append(f"{code}_at_index_{index}")
    except (ValueError, TypeError, KeyError, AttributeError):
        errors.append("unusable_response_shape")
    dates = [r["date"] for r in rows]
    keys = set(dates)
    output.update({"valid_row_count": len(rows), "unique_date_count": len(keys),
        "first_date": min(keys) if keys else None, "last_date": max(keys) if keys else None,
        "duplicate_date_count": len(dates) - len(keys), "ascending": dates == sorted(dates),
        "dates_after_end": sorted(d for d in keys if d > END),
        "dates_before_start": sorted(d for d in keys if d < START),
        "more_than_500_unique_dates": len(keys) > 500})
    if len(keys) != len(dates):
        errors.append("duplicate_dates")
    if output["dates_after_end"] or (job["mode"] == "range" and output["dates_before_start"]):
        errors.append("outside_requested_date_window")
    contract_keys = set(expected["research"] + expected["warmup"])
    output["unexpected_in_target_dates"] = sorted(d for d in keys if START <= d <= END and d not in contract_keys)
    if output["unexpected_in_target_dates"]:
        errors.append("unexpected_target_keys")
    for part in ("research", "warmup"):
        contract = set(expected[part])
        output[part] = {"expected": len(contract), "present": len(contract & keys), "missing": sorted(contract - keys)}
    output["coverage_observed_complete"] = bool(contract_keys) and not errors and contract_keys <= keys
    return output


def compare_pair(left, right):
    # Duplicate dates are defects; never silently pick one as comparison evidence.
    if left["duplicate_date_count"] or right["duplicate_date_count"]:
        return {"comparable": False, "reason": "duplicate_dates"}
    a, b = ({r["date"]: r for r in report["rows"]} for report in (left, right))
    common = sorted(set(a) & set(b))
    mismatch = []
    for day in common:
        if any((a[day].get(k) is None) != (b[day].get(k) is None) or
               (a[day].get(k) is not None and Decimal(a[day][k]) != Decimal(b[day][k])) for k in NUMBERS):
            mismatch.append(day)
    return {"comparable": bool(common), "overlap_dates": len(common), "mismatch_dates": mismatch,
        "range_dates_missing_from_count": sorted(set(b) - set(a)),
        "both_complete": left["coverage_observed_complete"] and right["coverage_observed_complete"],
        "price_basis_proved": False}


def local_credentials():
    # The existing plugin owns credentials. Read only in memory; never persist config or token.
    try:
        config = json.loads((HOME / "config.json").read_bytes())
        endpoint = json.loads((HOME / "runtime/endpoint.json").read_bytes())
    except (OSError, ValueError):
        raise StopProbe("local_configuration_unavailable") from None
    if config.get("enableTradeTools") is not False or config.get("enableAutomatedTradeApi") is not False:
        raise StopProbe("trading_flags_not_explicitly_false")
    if config.get("preferredPort") != PORT or endpoint.get("baseUrl") != BASE:
        raise StopProbe("endpoint_not_exact_pinned_loopback")
    token = config.get("localAccessToken")
    if not isinstance(token, str) or not re.fullmatch(r"[a-fA-F0-9]{64}", token):
        raise StopProbe("credential_shape_invalid")
    return token


def get_preflight():
    script = HERE / "ths_probe_preflight.ps1"
    import base64
    encoded = base64.b64encode(script.read_text(encoding="utf-8-sig").encode("utf-16le")).decode("ascii")
    if not PREFLIGHT_HOST.is_file():
        raise StopProbe("verified_powershell_host_unavailable")
    proc = subprocess.run([str(PREFLIGHT_HOST), "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
        capture_output=True, timeout=30, encoding="utf-8-sig", errors="strict")
    if proc.returncode:
        raise StopProbe("runtime_inventory_failed")
    try:
        result = json.loads(proc.stdout)
    except ValueError:
        raise StopProbe("runtime_inventory_invalid") from None
    if result.get("passed") is not True:
        raise StopProbe("runtime_preflight_not_ready")
    result["powershell_executable"] = str(PREFLIGHT_HOST)
    return result


def fetch(job, token):
    canonical = lambda item: json.dumps(item, sort_keys=True, allow_nan=False)
    if canonical(job) not in {canonical(item) for item in fixed_jobs()}:
        raise StopProbe("request_not_in_fixed_plan")
    deadline = time.monotonic() + TIMEOUT
    connection = http.client.HTTPConnection(HOST, PORT, timeout=TIMEOUT)
    timed_out = threading.Event()
    socket_holder = [None]
    def deadline_close():
        timed_out.set()
        current_socket = socket_holder[0]
        if current_socket is not None:
            try:
                current_socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
    watchdog = threading.Timer(TIMEOUT, deadline_close)
    watchdog.daemon = True
    watchdog.start()
    try:
        connection.connect()
        transport_socket = connection.sock
        socket_holder[0] = transport_socket
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise StopProbe("request_deadline_exceeded")
        transport_socket.settimeout(remaining)
        connection.request("POST", ROUTE, json.dumps(job["payload"]).encode("utf-8"),
            {"Content-Type": "application/json", "Accept": "application/json", "Accept-Encoding": "identity",
             "X-Tonghuasun-Codex-Token": token, "User-Agent": "m2-codex-six-read-probe"})
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise StopProbe("request_deadline_exceeded")
        transport_socket.settimeout(remaining)
        response = connection.getresponse()
        chunks, size = [], 0
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise StopProbe("request_deadline_exceeded")
            transport_socket.settimeout(remaining)
            chunk = response.read1(min(65536, MAX_BYTES + 1 - size))
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
            if size > MAX_BYTES:
                raise StopProbe("response_size_limit_exceeded")
        raw = b"".join(chunks)
        if token.encode("ascii").lower() in raw.lower():
            raise StopProbe("credential_echo_raw_not_retained")
        if timed_out.is_set():
            raise StopProbe("request_deadline_exceeded")
        return response.status, raw
    finally:
        watchdog.cancel()
        connection.close()


def capture():
    expected = expected_keys()
    preflight = get_preflight()
    token = local_credentials()
    # Fixed output directory is also a durable one-shot claim. Never resume or create a fresh grant automatically.
    LIVE.mkdir(exist_ok=False)
    write_json(LIVE / "authorization_and_plan.json", plan(), exclusive=True)
    write_json(LIVE / "preflight.json", preflight, exclusive=True)
    write_json(LIVE / "expected_keys.json", expected, exclusive=True)
    pin_paths = [Path(__file__), HERE / "test_ths_long_history_probe.py", HERE / "ths_probe_preflight.ps1", MANIFEST, CALENDAR]
    write_json(LIVE / "producer_and_contract_pins.json", {str(p): sha(p.read_bytes()) for p in pin_paths}, exclusive=True)
    started = time.monotonic()
    reports, receipts = [], []
    stop_reason = None
    for job in fixed_jobs():
        if len(receipts) >= MAX_ATTEMPTS or time.monotonic() - started + TIMEOUT > WALL_LIMIT:
            stop_reason = "attempt_or_wall_budget_exhausted"
            break
        if receipts:
            time.sleep(INTERVAL)
        receipt = {"job": job, "attempt_reserved_at_utc": datetime.now(timezone.utc).isoformat(), "state": "reserved_before_network"}
        write_json(LIVE / f"attempt_{job['id']}.json", receipt, exclusive=True)
        receipts.append(receipt)
        before = time.monotonic()
        try:
            status, raw = fetch(job, token)
            (LIVE / f"response_{job['id']}.bin").write_bytes(raw)
            receipt.update({"http_status": status, "raw_sha256": sha(raw), "raw_bytes": len(raw), "state": "received"})
            if status != 200:
                raise StopProbe(f"http_status_{status}_stop_no_retry")
            report = analyze(raw, job, expected[job["symbol"]])
            write_json(LIVE / f"analysis_{job['id']}.json", report, exclusive=True)
            reports.append(report)
            if any("identity" in error or "security" in error or "unusable_response" in error or "adjustment" in error for error in report["errors"]):
                raise StopProbe("response_contract_failure")
            print(json.dumps({"attempt": job["id"], "symbol": job["symbol"], "mode": job["mode"],
                "http_status": status, "rows": report["valid_row_count"], "first": report["first_date"], "last": report["last_date"],
                "coverage_observed_complete": report["coverage_observed_complete"], "errors": report["errors"]}), flush=True)
        except StopProbe as error:
            stop_reason = str(error)
        except (OSError, http.client.HTTPException):
            stop_reason = "transport_failed_or_timed_out_no_retry"
        finally:
            receipt["elapsed_seconds"] = round(time.monotonic() - before, 6)
            receipt["stop_reason"] = stop_reason
            write_json(LIVE / f"attempt_{job['id']}_completed.json", receipt, exclusive=True)
        if stop_reason:
            break
    pairs = {symbol: compare_pair(*[r for r in reports if r["symbol"] == symbol])
             for symbol in SYMBOLS if len([r for r in reports if r["symbol"] == symbol]) == 2}
    summary = {"grant_id": GRANT, "rest_attempts_consumed": len(receipts), "rest_attempts_not_issued": MAX_ATTEMPTS - len(receipts),
        "automatic_resume_allowed": False, "stop_reason": stop_reason, "pairs": pairs,
        "elapsed_seconds": round(time.monotonic() - started, 6), "m2_accepted": False, "vendor_basis": "unverified", "eligible": False}
    write_json(LIVE / "summary.json", summary, exclusive=True)
    print(json.dumps(summary), flush=True)
    return 1 if stop_reason else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture", action="store_true")
    args = parser.parse_args()
    try:
        if args.capture:
            raise SystemExit(capture())
        print(json.dumps(plan(), ensure_ascii=False, indent=2))
    except StopProbe as exc:
        print(json.dumps({"stopped_before_or_during_capture": str(exc)}))
        raise SystemExit(2)
