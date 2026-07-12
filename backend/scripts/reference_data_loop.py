from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
from contextlib import contextmanager
from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Iterator

from app.config import settings


PROJECT_ROOT = Path(__file__).resolve().parents[2]
HEARTBEAT_PATH = PROJECT_ROOT / "backend" / "logs" / "reference_data_heartbeat.json"
DEFAULT_INTERVAL_SECONDS = 4 * 60 * 60
UNSUCCESSFUL_STATUSES = frozenset(
    {"failed", "blocked", "error", "partial", "degraded", "empty"}
)


def write_heartbeat(payload: dict[str, Any], *, path: Path = HEARTBEAT_PATH) -> None:
    """Atomically replace the worker heartbeat with a complete UTF-8 payload."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def run_once(
    *,
    service_factory: Callable[[], Any] | None = None,
    board_limit: int | None,
    disclosure_limit: int | None,
    global_days: int,
    rate_limit_seconds: float,
    skip_sox: bool,
    timeout_seconds: int = 900,
) -> dict[str, Any]:
    """Run one guarded local-ledger refresh without touching the Control Plane."""

    if settings.enable_live_trading:
        return {
            "status": "blocked",
            "reason": "live_trading_enabled",
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": True,
            "writes_enabled": False,
        }
    if service_factory is None:
        return _run_subprocess(
            board_limit=board_limit,
            disclosure_limit=disclosure_limit,
            global_days=global_days,
            rate_limit_seconds=rate_limit_seconds,
            skip_sox=skip_sox,
            timeout_seconds=timeout_seconds,
        )
    service = service_factory()
    return service.run(
        apply=True,
        board_limit=board_limit,
        disclosure_limit=disclosure_limit,
        rate_limit_seconds=rate_limit_seconds,
        global_days=global_days,
        include_global=True,
        include_sox=not skip_sox,
        global_symbol_limit=None,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Continuously refresh review-only local reference ledgers."
    )
    parser.add_argument(
        "--interval-seconds",
        type=int,
        default=DEFAULT_INTERVAL_SECONDS,
        help="Seconds between completed cycles (default: 14400 / four hours).",
    )
    parser.add_argument("--max-cycles", type=int, default=0, help="0 runs forever")
    parser.add_argument("--board-limit", type=int, default=50)
    parser.add_argument("--disclosure-limit", type=int, default=500)
    parser.add_argument("--global-days", type=int, default=30)
    parser.add_argument("--rate-limit-seconds", type=float, default=0.2)
    parser.add_argument(
        "--cycle-timeout-seconds",
        type=int,
        default=900,
        help="Terminate a hung ingest subprocess after this many seconds (default: 900).",
    )
    parser.add_argument(
        "--skip-sox",
        action="store_true",
        help="Skip the slower SOX history source for this worker.",
    )
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    service_factory: Callable[[], Any] | None = None,
    heartbeat_path: Path = HEARTBEAT_PATH,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> int:
    args = build_parser().parse_args(argv)
    if args.max_cycles < 0:
        raise ValueError("max_cycles cannot be negative")
    if args.board_limit is not None and args.board_limit < 1:
        raise ValueError("board_limit must be positive")
    if args.disclosure_limit is not None and args.disclosure_limit < 1:
        raise ValueError("disclosure_limit must be positive")
    if not 6 <= args.global_days <= 3660:
        raise ValueError("global_days must be between 6 and 3660")
    if args.rate_limit_seconds < 0:
        raise ValueError("rate_limit_seconds cannot be negative")
    if not 60 <= args.cycle_timeout_seconds <= 3600:
        raise ValueError("cycle_timeout_seconds must be between 60 and 3600")

    lock_path = heartbeat_path.with_suffix(".lock")
    with _worker_lock(lock_path):
        return _run_cycles(
            args=args,
            service_factory=service_factory,
            heartbeat_path=heartbeat_path,
            sleep_fn=sleep_fn,
        )


def _run_cycles(
    *,
    args: argparse.Namespace,
    service_factory: Callable[[], Any] | None,
    heartbeat_path: Path,
    sleep_fn: Callable[[float], None],
) -> int:
    interval_seconds = max(60, int(args.interval_seconds))
    cycle = 0
    had_unsuccessful_cycle = False
    while args.max_cycles <= 0 or cycle < args.max_cycles:
        cycle += 1
        started = datetime.now().astimezone()
        base_heartbeat = {
            "schema_version": "reference_data_heartbeat.v1",
            "pid": os.getpid(),
            "cycle": cycle,
            "started_at": started.isoformat(timespec="seconds"),
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
            "writes_enabled": not settings.enable_live_trading,
            "apply": True,
            "interval_seconds": interval_seconds,
            "cycle_timeout_seconds": int(args.cycle_timeout_seconds),
        }
        write_heartbeat(
            {
                **base_heartbeat,
                "status": "running",
                "completed_at": started.isoformat(timespec="seconds"),
                "duration_seconds": None,
                "summary": {},
                "error": None,
            },
            path=heartbeat_path,
        )
        error = None
        result: dict[str, Any] = {}
        try:
            result = run_once(
                service_factory=service_factory,
                board_limit=args.board_limit,
                disclosure_limit=args.disclosure_limit,
                global_days=args.global_days,
                rate_limit_seconds=args.rate_limit_seconds,
                skip_sox=args.skip_sox,
                timeout_seconds=int(args.cycle_timeout_seconds),
            )
            status = str(result.get("status") or "failed").strip().lower()
        except Exception as exc:  # Keep an unbounded worker alive across source failures.
            status = "failed"
            error = f"{type(exc).__name__}: {exc}"[-2000:]
        if status in UNSUCCESSFUL_STATUSES:
            had_unsuccessful_cycle = True
        completed = datetime.now().astimezone()
        heartbeat = {
            **base_heartbeat,
            "status": status,
            "completed_at": completed.isoformat(timespec="seconds"),
            "duration_seconds": round((completed - started).total_seconds(), 2),
            "summary": _result_summary(result),
            "error": error,
        }
        write_heartbeat(heartbeat, path=heartbeat_path)
        print(json.dumps(heartbeat, ensure_ascii=False), flush=True)
        if args.max_cycles <= 0 or cycle < args.max_cycles:
            sleep_fn(interval_seconds)
    return 1 if had_unsuccessful_cycle else 0


@contextmanager
def _worker_lock(path: Path) -> Iterator[None]:
    """Hold an OS-backed single-instance lock for the worker lifetime."""
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+b")
    locked = False
    try:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            locked = True
        except OSError as exc:
            raise RuntimeError("another reference-data worker already holds the lock") from exc
        handle.seek(0)
        handle.truncate()
        handle.write(str(os.getpid()).encode("ascii"))
        handle.flush()
        yield
    finally:
        if locked:
            handle.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


def _run_subprocess(
    *,
    board_limit: int | None,
    disclosure_limit: int | None,
    global_days: int,
    rate_limit_seconds: float,
    skip_sox: bool,
    timeout_seconds: int,
) -> dict[str, Any]:
    command = [
        sys.executable,
        "-X",
        "utf8",
        "-m",
        "scripts.ingest_reference_data",
        "--apply",
        "--global-days",
        str(global_days),
        "--rate-limit-seconds",
        str(rate_limit_seconds),
    ]
    if board_limit is not None:
        command.extend(("--board-limit", str(board_limit)))
    if disclosure_limit is not None:
        command.extend(("--disclosure-limit", str(disclosure_limit)))
    if skip_sox:
        command.append("--skip-sox")
    try:
        completed = subprocess.run(
            command,
            cwd=PROJECT_ROOT / "backend",
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise TimeoutError(
            f"reference ingest exceeded {timeout_seconds} seconds and was terminated"
        ) from exc
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        stderr = completed.stderr.strip()[-1000:]
        raise RuntimeError(
            f"reference ingest subprocess returned invalid JSON "
            f"(exit={completed.returncode}, stderr={stderr})"
        ) from exc
    if not isinstance(result, dict):
        raise RuntimeError("reference ingest subprocess JSON must be an object")
    result["subprocess_exit_code"] = completed.returncode
    result["cycle_timeout_seconds"] = timeout_seconds
    return result


def _result_summary(result: dict[str, Any]) -> dict[str, Any]:
    sectors = result.get("sectors") if isinstance(result.get("sectors"), dict) else {}
    disclosures = (
        result.get("disclosures") if isinstance(result.get("disclosures"), dict) else {}
    )
    global_markets = (
        result.get("global_markets")
        if isinstance(result.get("global_markets"), dict)
        else {}
    )
    return {
        "mode": result.get("mode"),
        "sector_status": sectors.get("status"),
        "sector_memberships_written": sectors.get("membership_records_written", 0),
        "disclosure_status": disclosures.get("status"),
        "disclosure_facts_written": disclosures.get("facts_written", 0),
        "global_market_status": global_markets.get("status"),
        "global_bars_written": global_markets.get("bar_records_written", 0),
        "global_ready_source_coverage_pct": global_markets.get(
            "ready_source_coverage_pct"
        ),
        "reason": result.get("reason"),
    }


if __name__ == "__main__":
    sys.exit(main())
