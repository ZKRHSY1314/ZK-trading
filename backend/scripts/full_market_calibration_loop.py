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
import urllib.error
import urllib.request


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_HEARTBEAT_PATH = (
    PROJECT_ROOT / "backend" / "logs" / "full_market_calibration_heartbeat.json"
)
DEFAULT_INTERVAL_SECONDS = 86_400
DEFAULT_RETRY_SECONDS = 1_800
DEFAULT_DEADLINE_SECONDS = 900
SUCCESSFUL_CALIBRATION_STATUSES = frozenset({"ready", "insufficient_data"})


RequestFn = Callable[..., dict[str, Any]]


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
    with urllib.request.urlopen(request, timeout=max(1, int(timeout))) as response:  # noqa: S310
        result = json.loads(response.read().decode("utf-8"))
    if not isinstance(result, dict):
        raise ValueError("full_market_calibration_response_must_be_an_object")
    return result


def _safety(*, live_trading_enabled: Any = False) -> dict[str, Any]:
    return {
        "research_only": True,
        "simulation_only": True,
        "live_trading_enabled": live_trading_enabled,
        "execution_allowed": False,
        "orders_generated": False,
    }


def run_once(
    api_base: str,
    *,
    deadline_seconds: int = DEFAULT_DEADLINE_SECONDS,
    horizon_trading_days: int = 20,
    target_return_pct: float = 8.0,
    min_history_bars: int = 60,
    lookback_bars: int = 120,
    validation_fraction: float = 0.2,
    score_bin_width: int = 10,
    sample_stride: int = 10,
    min_train_samples: int = 200,
    min_validation_samples: int = 50,
    min_bin_samples: int = 30,
    as_of_date: str | None = None,
    request_fn: RequestFn = request_json,
) -> dict[str, Any]:
    deadline = max(60, min(int(deadline_seconds), 3_600))
    base_url = api_base.rstrip("/")
    health = request_fn(
        "GET",
        f"{base_url}/health",
        None,
        timeout=min(30, deadline),
    )
    if health.get("live_trading_enabled") is not False:
        return {
            "status": "blocked",
            "reason": "remote_live_trading_enabled",
            "safety": _safety(live_trading_enabled=health.get("live_trading_enabled")),
        }
    if health.get("status") != "ok":
        return {
            "status": "partial",
            "reason": "remote_health_not_ok",
            "remote_health_status": health.get("status"),
            "safety": _safety(),
        }
    payload = {
        "horizon_trading_days": max(1, min(int(horizon_trading_days), 250)),
        "target_return_pct": max(0.1, min(float(target_return_pct), 100.0)),
        "min_history_bars": max(60, min(int(min_history_bars), 500)),
        "lookback_bars": max(60, min(int(lookback_bars), 500)),
        "validation_fraction": max(0.1, min(float(validation_fraction), 0.5)),
        "score_bin_width": int(score_bin_width),
        "sample_stride": max(1, min(int(sample_stride), 60)),
        "min_train_samples": max(1, min(int(min_train_samples), 1_000_000)),
        "min_validation_samples": max(1, min(int(min_validation_samples), 1_000_000)),
        "min_bin_samples": max(1, min(int(min_bin_samples), 1_000_000)),
        "as_of_date": as_of_date or None,
    }
    if payload["lookback_bars"] < payload["min_history_bars"]:
        payload["lookback_bars"] = payload["min_history_bars"]
    if payload["score_bin_width"] not in {1, 2, 4, 5, 10, 20, 25, 50}:
        raise ValueError("score_bin_width must evenly divide 100 and be at most 50")
    result = request_fn(
        "POST",
        f"{base_url}/api/candidates/full-market-calibration/run",
        payload,
        timeout=deadline,
    )
    if str(result.get("status") or "").lower() in SUCCESSFUL_CALIBRATION_STATUSES:
        safety = result.get("safety") or {}
        if (
            safety.get("research_only") is not True
            or safety.get("simulation_only") is not True
            or safety.get("live_trading_enabled") is not False
            or safety.get("execution_allowed") is not False
            or safety.get("orders_generated") is not False
        ):
            return {
                "status": "blocked",
                "reason": "unsafe_calibration_response",
                "safety": _safety(),
            }
    return result


def next_interval_seconds(
    status: str,
    *,
    interval_seconds: int,
    retry_seconds: int,
) -> int:
    if str(status).lower() == "completed":
        return max(60, min(int(interval_seconds), 604_800))
    return max(60, min(int(retry_seconds), 86_400))


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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Continuously persist research-only full-market score calibration."
    )
    parser.add_argument("--api-base", default="http://127.0.0.1:8000")
    parser.add_argument("--heartbeat-path", default=str(DEFAULT_HEARTBEAT_PATH))
    parser.add_argument("--interval-seconds", type=int, default=DEFAULT_INTERVAL_SECONDS)
    parser.add_argument("--retry-seconds", type=int, default=DEFAULT_RETRY_SECONDS)
    parser.add_argument("--deadline-seconds", type=int, default=DEFAULT_DEADLINE_SECONDS)
    parser.add_argument("--max-cycles", type=int, default=0, help="0 runs forever")
    parser.add_argument("--horizon-trading-days", type=int, default=20)
    parser.add_argument("--target-return-pct", type=float, default=8.0)
    parser.add_argument("--min-history-bars", type=int, default=60)
    parser.add_argument("--lookback-bars", type=int, default=120)
    parser.add_argument("--validation-fraction", type=float, default=0.2)
    parser.add_argument(
        "--score-bin-width",
        type=int,
        choices=(1, 2, 4, 5, 10, 20, 25, 50),
        default=10,
    )
    parser.add_argument("--sample-stride", type=int, default=10)
    parser.add_argument("--min-train-samples", type=int, default=200)
    parser.add_argument("--min-validation-samples", type=int, default=50)
    parser.add_argument("--min-bin-samples", type=int, default=30)
    parser.add_argument("--as-of-date", default=None)
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    request_fn: RequestFn = request_json,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> int:
    args = build_parser().parse_args(argv)
    interval_seconds = max(60, min(int(args.interval_seconds), 604_800))
    retry_seconds = max(60, min(int(args.retry_seconds), 86_400))
    deadline_seconds = max(60, min(int(args.deadline_seconds), 3_600))
    max_cycles = max(0, int(args.max_cycles))
    cycle = 0
    worker_status = "failed"
    while max_cycles <= 0 or cycle < max_cycles:
        cycle += 1
        started = datetime.now().astimezone()
        base = {
            "schema_version": "full_market_calibration_heartbeat.v1",
            "worker": "full_market_calibration",
            "pid": os.getpid(),
            "cycle": cycle,
            "started_at": started.isoformat(timespec="seconds"),
            "completed_at": started.isoformat(timespec="seconds"),
            "interval_seconds": interval_seconds,
            "retry_interval_seconds": retry_seconds,
            "deadline_seconds": deadline_seconds,
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
                "phase": "calibrating",
                "calibration_status": None,
                "error": None,
                "next_interval_seconds": None,
            },
        )
        error = None
        try:
            result = run_once(
                args.api_base,
                deadline_seconds=deadline_seconds,
                horizon_trading_days=args.horizon_trading_days,
                target_return_pct=args.target_return_pct,
                min_history_bars=args.min_history_bars,
                lookback_bars=args.lookback_bars,
                validation_fraction=args.validation_fraction,
                score_bin_width=args.score_bin_width,
                sample_stride=args.sample_stride,
                min_train_samples=args.min_train_samples,
                min_validation_samples=args.min_validation_samples,
                min_bin_samples=args.min_bin_samples,
                as_of_date=args.as_of_date,
                request_fn=request_fn,
            )
            calibration_status = str(result.get("status") or "failed").lower()
            worker_status = (
                "completed"
                if calibration_status in SUCCESSFUL_CALIBRATION_STATUSES
                else calibration_status
            )
        except (
            OSError,
            TimeoutError,
            ValueError,
            json.JSONDecodeError,
            urllib.error.URLError,
        ) as exc:
            result = {}
            calibration_status = "failed"
            worker_status = "failed"
            error = f"{type(exc).__name__}: {exc}"[-2_000:]
        completed = datetime.now().astimezone()
        next_interval = next_interval_seconds(
            worker_status,
            interval_seconds=interval_seconds,
            retry_seconds=retry_seconds,
        )
        training = result.get("training") or {}
        validation = result.get("validation") or {}
        heartbeat = {
            **base,
            "status": worker_status,
            "calibration_status": calibration_status,
            "phase": "idle" if worker_status == "completed" else "retry_wait",
            "completed_at": completed.isoformat(timespec="seconds"),
            "duration_seconds": round((completed - started).total_seconds(), 3),
            "next_interval_seconds": next_interval,
            "as_of_date": result.get("as_of_date"),
            "calibration_run_id": result.get("calibration_run_id"),
            "training_sample_count": int(training.get("sample_count") or 0),
            "validation_sample_count": int(validation.get("sample_count") or 0),
            "mapped_validation_sample_count": int(validation.get("mapped_sample_count") or 0),
            "error": error,
        }
        write_heartbeat(args.heartbeat_path, heartbeat)
        print(json.dumps(heartbeat, ensure_ascii=False), flush=True)
        if max_cycles <= 0 or cycle < max_cycles:
            sleep_fn(next_interval)
    return 0 if worker_status == "completed" else 1


if __name__ == "__main__":
    sys.exit(main())
