from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import sys
import time
import urllib.error
import urllib.request


PROJECT_ROOT = Path(__file__).resolve().parents[2]
HEARTBEAT_PATH = PROJECT_ROOT / "backend" / "logs" / "control_plane_heartbeat.json"
RETRY_INTERVAL_SECONDS = 300
UNSUCCESSFUL_STATUSES = frozenset({"failed", "blocked", "partial", "degraded", "error"})


def next_interval_seconds(status: str, configured_interval_seconds: int) -> int:
    configured = max(30, int(configured_interval_seconds))
    if str(status).strip().lower() in UNSUCCESSFUL_STATUSES:
        return min(configured, RETRY_INTERVAL_SECONDS)
    return configured


def request_json(
    method: str,
    url: str,
    payload: dict | None = None,
    *,
    timeout: int = 240,
) -> dict:
    body = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=max(1, int(timeout))) as response:
        return json.loads(response.read().decode("utf-8"))


def write_heartbeat(payload: dict) -> None:
    HEARTBEAT_PATH.parent.mkdir(parents=True, exist_ok=True)
    temp = HEARTBEAT_PATH.with_suffix(".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(HEARTBEAT_PATH)


def run_slot(api_base: str, profile: str, limit: int, *, timeout_seconds: int = 240) -> dict:
    health = request_json("GET", f"{api_base}/health", timeout=min(30, timeout_seconds))
    if health.get("live_trading_enabled") is not False:
        return {"status": "blocked", "reason": "live_trading_enabled", "health": health}
    return request_json(
        "POST",
        f"{api_base}/api/control-plane/run-once",
        {"profile": profile, "limit": limit, "requested_by": "control_plane_worker"},
        timeout=timeout_seconds,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the review-only cockpit control plane.")
    parser.add_argument("--api-base", default="http://127.0.0.1:8000")
    parser.add_argument(
        "--profile",
        choices=["adaptive", "pulse", "training", "maintenance", "full"],
        default="adaptive",
    )
    parser.add_argument("--interval-seconds", type=int, default=900)
    parser.add_argument("--max-cycles", type=int, default=0, help="0 runs forever")
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--timeout-seconds", type=int, default=240)
    args = parser.parse_args()

    cycle = 0
    while args.max_cycles <= 0 or cycle < args.max_cycles:
        cycle += 1
        started_at = datetime.now().astimezone().isoformat(timespec="seconds")
        write_heartbeat(
            {
                "schema_version": "control_plane_heartbeat.v1",
                "pid": __import__("os").getpid(),
                "cycle": cycle,
                "status": "running",
                "started_at": started_at,
                "completed_at": started_at,
                "profile": args.profile,
                "error": None,
                "duration_ms": None,
                "interval_seconds": max(30, int(args.interval_seconds)),
                "timeout_seconds": max(30, int(args.timeout_seconds)),
            }
        )
        try:
            result = run_slot(
                args.api_base.rstrip("/"),
                args.profile,
                args.limit,
                timeout_seconds=max(30, int(args.timeout_seconds)),
            )
            status = str(result.get("status") or "failed")
            error = None
        except (OSError, urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
            result = {}
            status = "failed"
            error = str(exc)
        heartbeat = {
            "schema_version": "control_plane_heartbeat.v1",
            "pid": __import__("os").getpid(),
            "cycle": cycle,
            "status": status,
            "started_at": started_at,
            "completed_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "profile": args.profile,
            "error": error,
            "duration_ms": result.get("duration_ms"),
            "interval_seconds": max(30, int(args.interval_seconds)),
            "timeout_seconds": max(30, int(args.timeout_seconds)),
            "next_interval_seconds": next_interval_seconds(status, args.interval_seconds),
        }
        write_heartbeat(heartbeat)
        print(json.dumps(heartbeat, ensure_ascii=False), flush=True)
        if args.max_cycles <= 0 or cycle < args.max_cycles:
            time.sleep(heartbeat["next_interval_seconds"])
    return 0 if status not in {"failed", "blocked"} else 1


if __name__ == "__main__":
    sys.exit(main())
