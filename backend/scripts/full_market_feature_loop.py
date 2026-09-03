from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import sys
import time
from typing import Any
import urllib.error
from urllib.parse import urlencode
import urllib.request


PROJECT_ROOT = Path(__file__).resolve().parents[2]
HEARTBEAT_PATH = PROJECT_ROOT / "backend" / "logs" / "full_market_feature_heartbeat.json"
RETRY_INTERVAL_SECONDS = 900
UNSUCCESSFUL_STATUSES = frozenset({"failed", "blocked", "partial", "degraded", "error"})


def request_json(
    method: str,
    url: str,
    payload: dict[str, Any] | None = None,
    *,
    timeout: int = 30,
) -> dict[str, Any]:
    body = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=max(1, int(timeout))) as response:
        result = json.loads(response.read().decode("utf-8"))
    if not isinstance(result, dict):
        raise ValueError("full_market_feature_response_must_be_an_object")
    return result


def next_interval_seconds(status: str, configured_interval_seconds: int) -> int:
    configured = max(60, int(configured_interval_seconds))
    if str(status).strip().lower() in UNSUCCESSFUL_STATUSES:
        return min(configured, RETRY_INTERVAL_SECONDS)
    return configured


def run_once(
    api_base: str,
    *,
    candidate_limit: int,
    lookback_bars: int,
    timeout_seconds: int,
) -> dict[str, Any]:
    health = request_json(
        "GET",
        f"{api_base.rstrip('/')}/health",
        timeout=min(30, timeout_seconds),
    )
    if health.get("live_trading_enabled") is not False:
        return {
            "status": "blocked",
            "reason": "live_trading_enabled",
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": health.get("live_trading_enabled"),
        }
    query = urlencode(
        {
            "candidate_limit": max(1, min(int(candidate_limit), 500)),
            "lookback_bars": max(60, min(int(lookback_bars), 500)),
            "persist": "true",
            "force": "false",
        }
    )
    return request_json(
        "POST",
        f"{api_base.rstrip('/')}/api/candidates/full-market-scan/run?{query}",
        timeout=max(60, int(timeout_seconds)),
    )


def write_heartbeat(payload: dict[str, Any]) -> None:
    HEARTBEAT_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = HEARTBEAT_PATH.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(HEARTBEAT_PATH)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Continuously refresh review-only full-market daily features."
    )
    parser.add_argument("--api-base", default="http://127.0.0.1:8000")
    parser.add_argument("--interval-seconds", type=int, default=14_400)
    parser.add_argument("--max-cycles", type=int, default=0, help="0 runs forever")
    parser.add_argument("--candidate-limit", type=int, default=300)
    parser.add_argument("--lookback-bars", type=int, default=120)
    parser.add_argument("--timeout-seconds", type=int, default=300)
    args = parser.parse_args()

    cycle = 0
    final_status = "failed"
    while args.max_cycles <= 0 or cycle < args.max_cycles:
        cycle += 1
        started = datetime.now().astimezone()
        base = {
            "schema_version": "full_market_feature_heartbeat.v1",
            "pid": os.getpid(),
            "cycle": cycle,
            "started_at": started.isoformat(timespec="seconds"),
            "candidate_limit": max(1, min(int(args.candidate_limit), 500)),
            "lookback_bars": max(60, min(int(args.lookback_bars), 500)),
            "interval_seconds": max(60, int(args.interval_seconds)),
            "timeout_seconds": max(60, int(args.timeout_seconds)),
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": False,
        }
        write_heartbeat(
            {
                **base,
                "status": "running",
                "phase": "feature_scan",
                "completed_at": started.isoformat(timespec="seconds"),
                "error": None,
            }
        )
        error = None
        try:
            result = run_once(
                args.api_base,
                candidate_limit=base["candidate_limit"],
                lookback_bars=base["lookback_bars"],
                timeout_seconds=base["timeout_seconds"],
            )
            final_status = str(result.get("status") or "failed").strip().lower()
        except (
            OSError,
            TimeoutError,
            ValueError,
            json.JSONDecodeError,
            urllib.error.URLError,
        ) as exc:
            result = {}
            final_status = "failed"
            error = f"{type(exc).__name__}: {exc}"[-2000:]
        completed = datetime.now().astimezone()
        next_interval = next_interval_seconds(final_status, base["interval_seconds"])
        heartbeat = {
            **base,
            "status": final_status,
            "phase": "idle" if final_status == "completed" else "retry_wait",
            "completed_at": completed.isoformat(timespec="seconds"),
            "duration_seconds": round((completed - started).total_seconds(), 3),
            "as_of_date": result.get("as_of_date"),
            "universe_count": result.get("universe_count", 0),
            "qfq_ready_count": result.get("qfq_ready_count", 0),
            "eligible_count": result.get("eligible_count", 0),
            "selected_count": result.get("selected_count", 0),
            "incremental": result.get("incremental") or {},
            "scan_id": result.get("scan_id"),
            "error": error,
            "next_interval_seconds": next_interval,
        }
        write_heartbeat(heartbeat)
        print(json.dumps(heartbeat, ensure_ascii=False), flush=True)
        if args.max_cycles <= 0 or cycle < args.max_cycles:
            time.sleep(next_interval)
    return 0 if final_status not in {"failed", "blocked"} else 1


if __name__ == "__main__":
    sys.exit(main())
