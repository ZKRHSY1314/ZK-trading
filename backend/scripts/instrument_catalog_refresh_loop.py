from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request
from collections.abc import Callable
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.data.instrument_catalog import (  # noqa: E402
    DEFAULT_MANIFEST_PATH,
    InstrumentCatalogRefreshService,
)
from app.data.market_history import DEFAULT_MARKET_HISTORY_PATH  # noqa: E402


RequestFn = Callable[[str, int], dict[str, Any]]
DEFAULT_HEARTBEAT_PATH = (
    PROJECT_ROOT / "backend" / "logs" / "instrument_catalog_refresh_heartbeat.json"
)
DEFAULT_INTERVAL_SECONDS = 86_400
DEFAULT_RETRY_SECONDS = 900


def _request_json(url: str, timeout: int) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=timeout) as response:  # noqa: S310
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("health response must be an object")
    return payload


def run_once(
    api_base: str,
    *,
    database_path: str | Path = DEFAULT_MARKET_HISTORY_PATH,
    manifest_path: str | Path = DEFAULT_MANIFEST_PATH,
    request_fn: RequestFn = _request_json,
    service: Any | None = None,
) -> dict[str, Any]:
    health = request_fn(f"{api_base.rstrip('/')}/health", 10)
    if health.get("live_trading_enabled") is not False:
        return {
            "status": "blocked",
            "reason": "remote_live_trading_enabled",
            "writes_enabled": False,
            "safety": {
                "research_only": True,
                "simulation_only": True,
                "live_trading_enabled": health.get("live_trading_enabled"),
                "broker_or_order_capability": False,
            },
        }
    if health.get("status") != "ok":
        return {
            "status": "partial",
            "reason": "remote_health_not_ok",
            "remote_health_status": health.get("status"),
            "writes_enabled": False,
            "safety": {
                "research_only": True,
                "simulation_only": True,
                "live_trading_enabled": False,
                "broker_or_order_capability": False,
            },
        }
    runner = service or InstrumentCatalogRefreshService(database_path=database_path)
    return runner.run(apply=True, manifest_path=manifest_path)


def _write_heartbeat(path: str | Path, payload: dict[str, Any]) -> None:
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


def _heartbeat_contract(
    *,
    cycle: int,
    completed_at: str,
    interval_seconds: int,
    retry_interval_seconds: int,
    minimum_member_count: int,
    minimum_retained_ratio: float,
) -> dict[str, Any]:
    return {
        "pid": os.getpid(),
        "cycle": cycle,
        "completed_at": completed_at,
        "interval_seconds": interval_seconds,
        "retry_interval_seconds": retry_interval_seconds,
        "minimum_member_count": minimum_member_count,
        "minimum_retained_ratio": minimum_retained_ratio,
        "review_only": True,
        "simulation_only": True,
        "live_trading_enabled": False,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Continuously refresh the complete research-only A-share instrument catalog."
        )
    )
    parser.add_argument("--api-base", default="http://127.0.0.1:8000")
    parser.add_argument("--database-path", default=str(DEFAULT_MARKET_HISTORY_PATH))
    parser.add_argument("--manifest-path", default=str(DEFAULT_MANIFEST_PATH))
    parser.add_argument("--heartbeat-path", default=str(DEFAULT_HEARTBEAT_PATH))
    parser.add_argument("--interval-seconds", type=int, default=DEFAULT_INTERVAL_SECONDS)
    parser.add_argument("--retry-seconds", type=int, default=DEFAULT_RETRY_SECONDS)
    parser.add_argument("--minimum-member-count", type=int, default=4_000)
    parser.add_argument("--minimum-retained-ratio", type=float, default=0.9)
    parser.add_argument("--once", action="store_true")
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    request_fn: RequestFn = _request_json,
    service: Any | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> int:
    args = build_parser().parse_args(argv)
    interval_seconds = max(60, int(args.interval_seconds))
    retry_seconds = max(60, int(args.retry_seconds))
    minimum_member_count = max(1, int(args.minimum_member_count))
    minimum_retained_ratio = min(
        1.0,
        max(0.5, float(args.minimum_retained_ratio)),
    )
    runner = service or InstrumentCatalogRefreshService(
        database_path=args.database_path,
        minimum_member_count=minimum_member_count,
        minimum_retained_ratio=minimum_retained_ratio,
    )
    cycle = 0
    while True:
        cycle += 1
        started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        _write_heartbeat(
            args.heartbeat_path,
            {
                **_heartbeat_contract(
                    cycle=cycle,
                    completed_at=started_at,
                    interval_seconds=interval_seconds,
                    retry_interval_seconds=retry_seconds,
                    minimum_member_count=minimum_member_count,
                    minimum_retained_ratio=minimum_retained_ratio,
                ),
                "worker": "instrument_catalog_refresh",
                "status": "running",
                "phase": "refreshing",
                "updated_at": started_at,
                "next_interval_seconds": None,
                "safety": {
                    "research_only": True,
                    "simulation_only": True,
                    "live_trading_enabled": False,
                },
            },
        )
        try:
            result = run_once(
                args.api_base,
                database_path=args.database_path,
                manifest_path=args.manifest_path,
                request_fn=request_fn,
                service=runner,
            )
        except Exception as exc:
            result = {
                "status": "failed",
                "reason": "instrument_catalog_refresh_exception",
                "error": str(exc),
                "writes_enabled": False,
                "safety": {
                    "research_only": True,
                    "simulation_only": True,
                    "live_trading_enabled": False,
                    "broker_or_order_capability": False,
                    "writes_enabled": False,
                },
            }
        status = str(result.get("status") or "failed")
        next_interval = interval_seconds if status == "completed" else retry_seconds
        completed_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        _write_heartbeat(
            args.heartbeat_path,
            {
                **_heartbeat_contract(
                    cycle=cycle,
                    completed_at=completed_at,
                    interval_seconds=interval_seconds,
                    retry_interval_seconds=retry_seconds,
                    minimum_member_count=minimum_member_count,
                    minimum_retained_ratio=minimum_retained_ratio,
                ),
                "worker": "instrument_catalog_refresh",
                "status": status,
                "phase": "sleeping",
                "updated_at": completed_at,
                "last_started_at": started_at,
                "last_completed_at": completed_at,
                "next_interval_seconds": next_interval,
                "result": result,
                "safety": result.get("safety")
                or {
                    "research_only": True,
                    "simulation_only": True,
                    "live_trading_enabled": False,
                },
            },
        )
        if args.once:
            print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
            if status == "completed":
                return 0
            if status in {"partial", "blocked", "planned"}:
                return 2
            return 1
        sleep_fn(next_interval)


if __name__ == "__main__":
    raise SystemExit(main())
