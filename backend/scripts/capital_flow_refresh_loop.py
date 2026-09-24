from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
from datetime import datetime
import json
import os
from pathlib import Path
import sys
import time
from typing import Any
import urllib.request


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.config import settings  # noqa: E402
from app.data.capital_flow import CapitalFlowService  # noqa: E402


DEFAULT_HEARTBEAT_PATH = (
    PROJECT_ROOT / "backend" / "logs" / "capital_flow_refresh_heartbeat.json"
)
DEFAULT_INTERVAL_SECONDS = 900
DEFAULT_RETRY_SECONDS = 300
RequestFn = Callable[..., dict[str, Any]]
NowFn = Callable[[], datetime]


def request_json(url: str, *, timeout: int = 15) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=max(1, int(timeout))) as response:  # noqa: S310
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("health response must be an object")
    return payload


def run_once(
    api_base: str,
    *,
    request_fn: RequestFn = request_json,
    service: Any | None = None,
) -> dict[str, Any]:
    health = request_fn(f"{api_base.rstrip('/')}/health", timeout=15)
    if health.get("live_trading_enabled") is not False:
        return {
            "status": "blocked",
            "reason": "remote_live_trading_enabled",
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": health.get("live_trading_enabled"),
            "orders_generated": False,
        }
    if settings.enable_live_trading:
        return {
            "status": "blocked",
            "reason": "local_live_trading_enabled",
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": True,
            "orders_generated": False,
        }
    if health.get("status") != "ok":
        return {
            "status": "degraded",
            "reason": "remote_health_not_ok",
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": False,
            "orders_generated": False,
        }

    result = (service or CapitalFlowService()).refresh_market()
    if (
        result.get("review_only") is not True
        or result.get("simulation_only") is not True
        or result.get("live_trading_enabled") is not False
    ):
        return {
            "status": "blocked",
            "reason": "unsafe_capital_flow_response",
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": False,
            "orders_generated": False,
        }
    return result


def write_heartbeat(path: str | Path, payload: dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    try:
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)


def next_interval_seconds(
    status: str,
    *,
    interval_seconds: int,
    retry_seconds: int,
) -> int:
    if str(status or "").strip().lower() == "completed":
        return max(60, min(int(interval_seconds), 86_400))
    return max(60, min(int(retry_seconds), 3_600))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Continuously refresh auditable vendor-derived A-share capital flow."
    )
    parser.add_argument("--api-base", default="http://127.0.0.1:8000")
    parser.add_argument("--heartbeat-path", default=str(DEFAULT_HEARTBEAT_PATH))
    parser.add_argument("--interval-seconds", type=int, default=DEFAULT_INTERVAL_SECONDS)
    parser.add_argument("--retry-seconds", type=int, default=DEFAULT_RETRY_SECONDS)
    parser.add_argument("--max-cycles", type=int, default=0, help="0 runs forever")
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    request_fn: RequestFn = request_json,
    service: Any | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
    now_fn: NowFn = lambda: datetime.now().astimezone(),
) -> int:
    args = build_parser().parse_args(argv)
    interval_seconds = max(60, min(int(args.interval_seconds), 86_400))
    retry_seconds = max(60, min(int(args.retry_seconds), 3_600))
    max_cycles = max(0, int(args.max_cycles))
    runner = service or CapitalFlowService()
    cycle = 0
    last_status = "failed"
    while max_cycles <= 0 or cycle < max_cycles:
        cycle += 1
        started = now_fn()
        base = {
            "schema_version": "capital_flow_refresh_heartbeat.v1",
            "worker": "capital_flow_refresh",
            "pid": os.getpid(),
            "cycle": cycle,
            "started_at": started.isoformat(timespec="seconds"),
            "completed_at": started.isoformat(timespec="seconds"),
            "interval_seconds": interval_seconds,
            "retry_interval_seconds": retry_seconds,
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": False,
            "orders_generated": False,
        }
        write_heartbeat(
            args.heartbeat_path,
            {
                **base,
                "status": "running",
                "phase": "refreshing",
                "next_interval_seconds": None,
            },
        )
        error = None
        try:
            result = run_once(
                args.api_base,
                request_fn=request_fn,
                service=runner,
            )
            last_status = str(result.get("status") or "failed").strip().lower()
        except Exception as exc:  # Keep the long-running source worker alive.
            error = f"{type(exc).__name__}: {exc}"[-2_000:]
            result = {
                "status": "failed",
                "reason": "capital_flow_refresh_exception",
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": False,
            }
            last_status = "failed"
        completed = now_fn()
        next_interval = next_interval_seconds(
            last_status,
            interval_seconds=interval_seconds,
            retry_seconds=retry_seconds,
        )
        snapshot = result.get("snapshot") or {}
        heartbeat = {
            **base,
            "status": last_status,
            "phase": "idle" if last_status == "completed" else "retry_wait",
            "completed_at": completed.isoformat(timespec="seconds"),
            "duration_seconds": max(
                0.0,
                round((completed - started).total_seconds(), 3),
            ),
            "next_interval_seconds": next_interval,
            "accepted_count": int(result.get("accepted_count") or 0),
            "duplicate_count": int(result.get("duplicate_count") or 0),
            "last_snapshot_date": snapshot.get("as_of"),
            "snapshot_status": snapshot.get("status"),
            "source": snapshot.get("source"),
            "retained_last_known": bool(result.get("retained_last_known")),
            "reason": result.get("reason"),
            "error": error or result.get("error"),
        }
        write_heartbeat(args.heartbeat_path, heartbeat)
        print(json.dumps(heartbeat, ensure_ascii=False), flush=True)
        if max_cycles <= 0 or cycle < max_cycles:
            sleep_fn(next_interval)
    if last_status == "completed":
        return 0
    if last_status in {"degraded", "partial", "blocked"}:
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
