from __future__ import annotations

import argparse
from collections.abc import Callable, Iterable, Sequence
from contextlib import closing
from datetime import date, datetime, time as datetime_time, timedelta
import json
import os
from pathlib import Path
import sqlite3
import sys
import time
from typing import Any
import urllib.error
from urllib.parse import urlencode
import urllib.request
from zoneinfo import ZoneInfo


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.config import settings  # noqa: E402
from app.data.daily_bar_cache import DailyBarCacheService  # noqa: E402
from app.data.market_history import DEFAULT_MARKET_HISTORY_PATH  # noqa: E402
from app.data.trading_calendar import trading_session_age  # noqa: E402
from app.storage.sqlite_store import SQLiteStore  # noqa: E402
from scripts.backfill_market_universe import DEFAULT_MANIFEST_PATH  # noqa: E402
from scripts.seed_market_history import (  # noqa: E402
    CandidateHistorySeeder,
    UNIT_VERIFIED_QFQ_SOURCE,
)

HEARTBEAT_PATH = PROJECT_ROOT / "backend" / "logs" / "market_history_refresh_heartbeat.json"
SHANGHAI = ZoneInfo("Asia/Shanghai")
SESSION_FINALIZATION_TIME = datetime_time(15, 15)
DEFAULT_INTERVAL_SECONDS = 14_400
DEFAULT_RETRY_INTERVAL_SECONDS = 900
DEFAULT_DEADLINE_SECONDS = 900
DEFAULT_DAYS = 150
DEFAULT_BATCH_SIZE = 200
DEFAULT_MAX_WORKERS = 20
DEFAULT_SEED_BATCH_SIZE = 500
DEFAULT_GAP_RECOVERY_LIMIT = 500
UNSUCCESSFUL_STATUSES = frozenset({"blocked", "failed", "partial", "error"})
DAILY_BAR_SOURCE_POLICIES = (
    "tonghuasun_first",
    "tonghuasun_only",
    "tencent_first",
    "akshare_first",
    "akshare_only",
)

RequestFn = Callable[..., dict[str, Any]]
ProgressFn = Callable[[dict[str, Any]], None]


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
        raise ValueError("market_history_refresh_response_must_be_an_object")
    return result


def _safety(live_trading_enabled: object) -> dict[str, Any]:
    return {
        "review_only": True,
        "simulation_only": True,
        "live_trading_enabled": live_trading_enabled,
        "broker_or_order_capability": False,
    }


def _emit(progress_fn: ProgressFn | None, **payload: Any) -> None:
    if progress_fn is not None:
        progress_fn(payload)


def _connect_read_only(path: str | Path) -> sqlite3.Connection:
    target = Path(path).resolve()
    connection = sqlite3.connect(
        f"{target.as_uri()}?mode=ro",
        uri=True,
        timeout=5,
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    connection.execute("PRAGMA busy_timeout = 5000")
    return connection


def _latest_qfq_dates(
    database_path: str | Path,
    *,
    table: str,
    symbols: Sequence[str],
) -> dict[str, date]:
    if table not in {"daily_bar_cache", "daily_bars"}:
        raise ValueError(f"unsupported daily-bar table: {table}")
    if not Path(database_path).exists() or not symbols:
        return {}
    provenance_column = "source" if table == "daily_bar_cache" else "provider"
    source_filter = (
        f"AND (lower(COALESCE({provenance_column}, '')) NOT LIKE '%sina%' "
        f"OR lower(COALESCE({provenance_column}, '')) = "
        f"'{UNIT_VERIFIED_QFQ_SOURCE}')"
    )
    result: dict[str, date] = {}
    with closing(_connect_read_only(database_path)) as connection:
        for offset in range(0, len(symbols), 400):
            batch = list(symbols[offset : offset + 400])
            placeholders = ",".join("?" for _ in batch)
            rows = connection.execute(
                f"""
                SELECT symbol, MAX(date(trade_date)) AS latest_trade_date
                FROM {table}
                WHERE symbol IN ({placeholders})
                  AND trade_date != 'ERROR'
                  AND quality_status = 'ready'
                  AND adjustment_mode = 'qfq'
                  {source_filter}
                GROUP BY symbol
                """,
                tuple(batch),
            ).fetchall()
            for row in rows:
                value = row["latest_trade_date"]
                if value:
                    result[str(row["symbol"])] = date.fromisoformat(str(value)[:10])
    return result


def _full_market_snapshot_matches_manifest(
    database_path: str | Path,
    *,
    universe_hash: str,
    expected_member_count: int,
) -> bool:
    if not Path(database_path).exists():
        return False
    try:
        with closing(_connect_read_only(database_path)) as connection:
            row = connection.execute(
                """
                SELECT snapshot.id, snapshot.member_count, snapshot.source_hash,
                       COUNT(member.symbol) AS actual_member_count
                FROM universe_snapshots AS snapshot
                LEFT JOIN universe_members AS member
                  ON member.snapshot_id = snapshot.id
                WHERE snapshot.universe_name = 'a_share_full_market_cache'
                GROUP BY snapshot.id, snapshot.member_count, snapshot.source_hash
                ORDER BY date(snapshot.snapshot_date) DESC, snapshot.id DESC
                LIMIT 1
                """
            ).fetchone()
    except sqlite3.Error:
        return False
    return bool(
        row is not None
        and str(row["source_hash"] or "") == str(universe_hash)
        and int(row["member_count"] or 0) == int(expected_member_count)
        and int(row["actual_member_count"] or 0) == int(expected_member_count)
    )


def latest_completed_session(
    current: datetime,
    *,
    known_latest: date | None,
    trading_dates: Iterable[date] | None = None,
) -> tuple[date | None, str]:
    local = current.astimezone(SHANGHAI)
    cutoff = local.date()
    if local.time() < SESSION_FINALIZATION_TIME:
        cutoff -= timedelta(days=1)
    calendar_source = "not_required"
    for offset in range(0, 32):
        candidate = cutoff - timedelta(days=offset)
        age, calendar_source = trading_session_age(
            candidate - timedelta(days=1),
            candidate,
            exclude_target_session=False,
            trading_dates=trading_dates,
        )
        if age == 1:
            return candidate, calendar_source
    if known_latest is not None and known_latest <= cutoff:
        return known_latest, calendar_source
    return None, calendar_source


def _run_scan(
    request_fn: RequestFn,
    api_base: str,
    *,
    candidate_limit: int,
    lookback_bars: int,
    timeout_seconds: int,
) -> dict[str, Any]:
    query = urlencode(
        {
            "candidate_limit": max(1, min(int(candidate_limit), 500)),
            "lookback_bars": max(60, min(int(lookback_bars), 500)),
            "persist": "true",
            "force": "false",
        }
    )
    return request_fn(
        "POST",
        f"{api_base.rstrip('/')}/api/candidates/full-market-scan/run?{query}",
        timeout=max(60, int(timeout_seconds)),
    )


def _seed_history(
    *,
    source_database: str | Path,
    target_database: str | Path,
    universe_manifest_path: str | Path,
    current: datetime,
    bars_per_symbol: int,
    seed_batch_size: int,
    deadline_at: float,
    progress_fn: ProgressFn | None,
) -> dict[str, Any]:
    seeder = CandidateHistorySeeder(source_database, target_database)
    resume_after: str | None = None
    batches = 0
    seeded_symbols = 0
    write_stats = {
        "bars_inserted": 0,
        "bars_updated": 0,
        "bars_unchanged": 0,
    }
    errors: list[dict[str, Any]] = []
    while True:
        if time.monotonic() >= deadline_at:
            errors.append({"stage": "seed", "error": "deadline_exceeded"})
            break
        result = seeder.run(
            apply=True,
            universe_scope="full_market_cache",
            universe_manifest_path=universe_manifest_path,
            bars_per_symbol=bars_per_symbol,
            resume_after=resume_after,
            symbol_limit=seed_batch_size,
            now=current,
        )
        batches += 1
        candidate_count = int(result.get("candidate_count") or 0)
        seeded_symbols += int(result.get("candidate_symbols_with_bars") or 0)
        for key in write_stats:
            write_stats[key] += int((result.get("write_stats") or {}).get(key) or 0)
        next_resume = result.get("last_processed_symbol")
        _emit(
            progress_fn,
            phase="seed",
            status="running",
            progress={
                "seed_batches": batches,
                "seeded_symbols": seeded_symbols,
                "last_processed_symbol": next_resume,
            },
        )
        if result.get("status") in {"blocked", "error"}:
            errors.append(
                {
                    "stage": "seed",
                    "error": str(result.get("reason") or result.get("error") or result["status"]),
                    "result_status": result.get("status"),
                }
            )
            break
        if candidate_count == 0 or candidate_count < seed_batch_size:
            break
        if not next_resume or next_resume == resume_after:
            errors.append({"stage": "seed", "error": "resume_cursor_did_not_advance"})
            break
        resume_after = str(next_resume)
    return {
        "seed_batches": batches,
        "seeded_symbols": seeded_symbols,
        "write_stats": write_stats,
        "errors": errors,
    }


def run_once(
    api_base: str,
    *,
    source_database: str | Path = settings.database_path,
    target_database: str | Path = DEFAULT_MARKET_HISTORY_PATH,
    universe_manifest_path: str | Path = DEFAULT_MANIFEST_PATH,
    days: int = DEFAULT_DAYS,
    source_policy: str | None = None,
    batch_size: int = DEFAULT_BATCH_SIZE,
    max_workers: int = DEFAULT_MAX_WORKERS,
    seed_batch_size: int = DEFAULT_SEED_BATCH_SIZE,
    gap_recovery_limit: int = DEFAULT_GAP_RECOVERY_LIMIT,
    deadline_seconds: int = DEFAULT_DEADLINE_SECONDS,
    scan_timeout_seconds: int = 300,
    candidate_limit: int = 300,
    lookback_bars: int = 120,
    now: datetime | None = None,
    trading_dates: Iterable[date] | None = None,
    request_fn: RequestFn = request_json,
    progress_fn: ProgressFn | None = None,
) -> dict[str, Any]:
    started_monotonic = time.monotonic()
    days = max(120, min(int(days), 500))
    source_policy = str(
        source_policy or settings.daily_bar_source_policy
    ).strip().lower()
    if source_policy not in DAILY_BAR_SOURCE_POLICIES:
        raise ValueError(f"unsupported daily-bar source policy: {source_policy}")
    batch_size = max(1, min(int(batch_size), 200))
    max_workers = max(1, min(int(max_workers), 20))
    seed_batch_size = max(1, min(int(seed_batch_size), 500))
    gap_recovery_limit = max(0, min(int(gap_recovery_limit), 1_000))
    deadline_seconds = max(60, int(deadline_seconds))
    deadline_at = started_monotonic + deadline_seconds
    health = request_fn(
        "GET",
        f"{api_base.rstrip('/')}/health",
        timeout=30,
    )
    live_enabled = health.get("live_trading_enabled")
    if live_enabled is not False:
        return {
            "status": "blocked",
            "reason": "live_trading_enabled",
            "safety": _safety(live_enabled),
        }
    if settings.enable_live_trading:
        return {
            "status": "blocked",
            "reason": "local_live_trading_enabled",
            "safety": _safety(True),
        }

    current = (now or datetime.now(tz=SHANGHAI)).astimezone(SHANGHAI)
    _emit(progress_fn, phase="planning", status="running")
    manifest = CandidateHistorySeeder._load_universe_manifest(universe_manifest_path)
    official_symbols = list(manifest["symbols"])
    universe_snapshot_refresh_needed = not _full_market_snapshot_matches_manifest(
        target_database,
        universe_hash=str(manifest["universe_hash"]),
        expected_member_count=len(official_symbols),
    )
    cache_dates = _latest_qfq_dates(
        source_database,
        table="daily_bar_cache",
        symbols=official_symbols,
    )
    history_dates = _latest_qfq_dates(
        target_database,
        table="daily_bars",
        symbols=official_symbols,
    )
    known_latest = max(
        [*cache_dates.values(), *history_dates.values()],
        default=None,
    )
    target_session, calendar_source = latest_completed_session(
        current,
        known_latest=known_latest,
        trading_dates=trading_dates,
    )
    if target_session is None:
        return {
            "status": "partial",
            "reason": "completed_trading_session_unavailable",
            "target_session": None,
            "calendar_source": calendar_source,
            "official_universe_count": len(official_symbols),
            "qfq_ready_count": len(cache_dates),
            "errors": [
                {
                    "stage": "calendar",
                    "error": "completed_trading_session_unavailable",
                }
            ],
            "safety": _safety(False),
        }
    stale_symbols = sorted(
        symbol
        for symbol, latest in cache_dates.items()
        if latest < target_session
    )
    qfq_gap_symbols = sorted(set(official_symbols) - set(cache_dates))
    qfq_gap_recovery_symbols = qfq_gap_symbols[:gap_recovery_limit]
    refresh_symbols = sorted(set(stale_symbols) | set(qfq_gap_recovery_symbols))
    seed_symbols = sorted(
        symbol
        for symbol, latest in cache_dates.items()
        if history_dates.get(symbol) is None or history_dates[symbol] < latest
    )
    base = {
        "target_session": target_session.isoformat(),
        "calendar_source": calendar_source,
        "official_universe_count": len(official_symbols),
        "qfq_ready_count": len(cache_dates),
        "qfq_gap_count_before": len(qfq_gap_symbols),
        "qfq_gap_recovery_planned": len(qfq_gap_recovery_symbols),
        "qfq_gap_recovered": 0,
        "qfq_gap_remaining": len(qfq_gap_symbols),
        "permanent_qfq_gap_count": len(qfq_gap_symbols),
        "refresh_planned": len(refresh_symbols),
        "seed_planned": len(seed_symbols),
        "universe_snapshot_refresh_needed": universe_snapshot_refresh_needed,
        "universe_snapshot_refreshed": False,
        "source_policy": source_policy,
        "safety": _safety(False),
    }
    if not refresh_symbols and not seed_symbols and not universe_snapshot_refresh_needed:
        _emit(progress_fn, phase="scan", status="running", progress=base)
        scan = _run_scan(
            request_fn,
            api_base,
            candidate_limit=candidate_limit,
            lookback_bars=lookback_bars,
            timeout_seconds=scan_timeout_seconds,
        )
        scan_status = str(scan.get("status") or "error").strip().lower()
        scan_errors = []
        if scan_status in UNSUCCESSFUL_STATUSES:
            scan_errors.append(
                {
                    "stage": "scan",
                    "status": scan_status,
                    "error": str(
                        scan.get("error") or scan.get("reason") or scan_status
                    ),
                }
            )
        return {
            **base,
            "status": "partial" if scan_errors else "skipped",
            "reason": "up_to_date_scan_failed" if scan_errors else "up_to_date",
            "refreshed": 0,
            "refresh_failed": 0,
            "seed_batches": 0,
            "seeded_symbols": 0,
            "scan": scan,
            "errors": scan_errors,
        }

    errors: list[dict[str, Any]] = []
    refresh_results: dict[str, dict[str, Any]] = {}
    cache_service = DailyBarCacheService(store=SQLiteStore(source_database))
    for offset in range(0, len(refresh_symbols), batch_size):
        if time.monotonic() >= deadline_at:
            errors.append({"stage": "refresh", "error": "deadline_exceeded"})
            break
        batch = refresh_symbols[offset : offset + batch_size]
        response = cache_service.refresh_symbols(
            batch,
            days=days,
            source_policy=source_policy,
            max_workers=max_workers,
        )
        items = {
            str(item.get("symbol")): dict(item)
            for item in response.get("results", [])
            if isinstance(item, dict) and item.get("symbol")
        }
        for symbol in batch:
            item = items.get(symbol)
            if item is None:
                item = {
                    "symbol": symbol,
                    "status": "error",
                    "error": "refresh_result_missing",
                }
            refresh_results[symbol] = item
            if item.get("status") != "success":
                errors.append(
                    {
                        "stage": "refresh",
                        "symbol": symbol,
                        "status": item.get("status") or "error",
                        "error": item.get("error") or "qfq_refresh_not_successful",
                        "attempts": item.get("attempts") or [],
                    }
                )
        _emit(
            progress_fn,
            phase="refresh",
            status="running",
            progress={
                "planned": len(refresh_symbols),
                "attempted": min(offset + len(batch), len(refresh_symbols)),
                "successful": sum(
                    item.get("status") == "success"
                    for item in refresh_results.values()
                ),
                "failed": sum(
                    item.get("status") != "success"
                    for item in refresh_results.values()
                ),
            },
        )

    refreshed_cache_dates = _latest_qfq_dates(
        source_database,
        table="daily_bar_cache",
        symbols=official_symbols,
    )
    recovered_qfq_gaps = sorted(
        symbol for symbol in qfq_gap_recovery_symbols if symbol in refreshed_cache_dates
    )
    remaining_qfq_gaps = sorted(set(official_symbols) - set(refreshed_cache_dates))
    refreshed_symbols = sorted(
        symbol
        for symbol in refresh_symbols
        if refreshed_cache_dates.get(symbol) is not None
        and refreshed_cache_dates[symbol] >= target_session
    )
    still_stale = sorted(set(refresh_symbols) - set(refreshed_symbols))
    already_reported = {
        str(item.get("symbol"))
        for item in errors
        if item.get("stage") == "refresh" and item.get("symbol")
    }
    for symbol in still_stale:
        if symbol not in already_reported:
            errors.append(
                {
                    "stage": "refresh",
                    "symbol": symbol,
                    "status": "stale",
                    "error": "target_session_not_reached",
                    "latest_trade_date": (
                        refreshed_cache_dates[symbol].isoformat()
                        if symbol in refreshed_cache_dates
                        else None
                    ),
                    "target_session": target_session.isoformat(),
                }
            )

    refreshed_history_dates = _latest_qfq_dates(
        target_database,
        table="daily_bars",
        symbols=official_symbols,
    )
    seed_symbols = sorted(
        symbol
        for symbol, latest in refreshed_cache_dates.items()
        if refreshed_history_dates.get(symbol) is None
        or refreshed_history_dates[symbol] < latest
    )
    seed_summary = {
        "seed_batches": 0,
        "seeded_symbols": 0,
        "write_stats": {},
        "errors": [],
    }
    if seed_symbols or universe_snapshot_refresh_needed:
        seed_summary = _seed_history(
            source_database=source_database,
            target_database=target_database,
            universe_manifest_path=universe_manifest_path,
            current=current,
            bars_per_symbol=days,
            seed_batch_size=seed_batch_size,
            deadline_at=deadline_at,
            progress_fn=progress_fn,
        )
        errors.extend(seed_summary["errors"])
    universe_snapshot_refreshed = _full_market_snapshot_matches_manifest(
        target_database,
        universe_hash=str(manifest["universe_hash"]),
        expected_member_count=len(official_symbols),
    )

    _emit(progress_fn, phase="scan", status="running", progress=base)
    scan = _run_scan(
        request_fn,
        api_base,
        candidate_limit=candidate_limit,
        lookback_bars=lookback_bars,
        timeout_seconds=scan_timeout_seconds,
    )
    scan_status = str(scan.get("status") or "error").strip().lower()
    if scan_status in UNSUCCESSFUL_STATUSES:
        errors.append(
            {
                "stage": "scan",
                "status": scan_status,
                "error": str(scan.get("error") or scan.get("reason") or scan_status),
            }
        )
    final_status = "partial" if errors or still_stale else "completed"
    return {
        **base,
        "status": final_status,
        "qfq_ready_count": len(refreshed_cache_dates),
        "qfq_gap_recovered": len(recovered_qfq_gaps),
        "qfq_gap_remaining": len(remaining_qfq_gaps),
        "permanent_qfq_gap_count": len(remaining_qfq_gaps),
        "refresh_planned": len(refresh_symbols),
        "refreshed": len(refreshed_symbols),
        "refresh_failed": len(still_stale),
        "seed_planned": len(seed_symbols),
        "seed_batches": seed_summary["seed_batches"],
        "seeded_symbols": seed_summary["seeded_symbols"],
        "seed_write_stats": seed_summary["write_stats"],
        "universe_snapshot_refresh_needed": universe_snapshot_refresh_needed,
        "universe_snapshot_refreshed": universe_snapshot_refreshed,
        "scan": scan,
        "errors": errors,
        "duration_seconds": round(time.monotonic() - started_monotonic, 3),
    }


def next_interval_seconds(
    status: str,
    configured_interval_seconds: int,
    retry_interval_seconds: int = DEFAULT_RETRY_INTERVAL_SECONDS,
    *,
    reason: str | None = None,
    now: datetime | None = None,
) -> int:
    configured = max(60, int(configured_interval_seconds))
    retry = max(60, int(retry_interval_seconds))
    if str(status or "").strip().lower() in UNSUCCESSFUL_STATUSES:
        return min(configured, retry)
    local = (now or datetime.now(tz=SHANGHAI)).astimezone(SHANGHAI)
    if (
        str(status or "").strip().lower() == "skipped"
        and reason == "up_to_date"
        and local.weekday() < 5
        and local.time() < SESSION_FINALIZATION_TIME
    ):
        finalization = datetime.combine(
            local.date(),
            SESSION_FINALIZATION_TIME,
            tzinfo=SHANGHAI,
        )
        until_finalization = int((finalization - local).total_seconds()) + 60
        return min(configured, max(60, until_finalization))
    return configured


def write_heartbeat(payload: dict[str, Any], path: str | Path = HEARTBEAT_PATH) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(target)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Refresh the latest completed-session qfq bars for the current official "
            "A-share universe, seed research history, then run the review-only scan."
        )
    )
    parser.add_argument("--api-base", default="http://127.0.0.1:8000")
    parser.add_argument("--interval-seconds", type=int, default=DEFAULT_INTERVAL_SECONDS)
    parser.add_argument(
        "--retry-interval-seconds",
        type=int,
        default=DEFAULT_RETRY_INTERVAL_SECONDS,
    )
    parser.add_argument("--max-cycles", type=int, default=0, help="0 runs forever")
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS)
    parser.add_argument(
        "--source-policy",
        choices=DAILY_BAR_SOURCE_POLICIES,
        default=settings.daily_bar_source_policy,
        help=(
            "Daily-bar source order; tonghuasun_first uses the configured local "
            "Tonghuashun service and then falls back to public providers."
        ),
    )
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--max-workers", type=int, default=DEFAULT_MAX_WORKERS)
    parser.add_argument("--seed-batch-size", type=int, default=DEFAULT_SEED_BATCH_SIZE)
    parser.add_argument(
        "--gap-recovery-limit",
        type=int,
        default=DEFAULT_GAP_RECOVERY_LIMIT,
        help="Maximum official-universe symbols without qfq history to retry per cycle.",
    )
    parser.add_argument("--deadline-seconds", type=int, default=DEFAULT_DEADLINE_SECONDS)
    parser.add_argument("--scan-timeout-seconds", type=int, default=300)
    parser.add_argument("--candidate-limit", type=int, default=300)
    parser.add_argument("--lookback-bars", type=int, default=120)
    parser.add_argument("--source-database", default=str(settings.database_path))
    parser.add_argument("--target-database", default=str(DEFAULT_MARKET_HISTORY_PATH))
    parser.add_argument(
        "--universe-manifest-path",
        default=str(DEFAULT_MANIFEST_PATH),
    )
    parser.add_argument("--heartbeat-path", default=str(HEARTBEAT_PATH))
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    runner: Callable[..., dict[str, Any]] | None = None,
) -> int:
    args = build_parser().parse_args(argv)
    run_cycle = runner or run_once
    interval_seconds = max(60, int(args.interval_seconds))
    retry_interval_seconds = max(60, int(args.retry_interval_seconds))
    deadline_seconds = max(60, int(args.deadline_seconds))
    days = max(120, min(int(args.days), 500))
    batch_size = max(1, min(int(args.batch_size), 200))
    max_workers = max(1, min(int(args.max_workers), 20))
    seed_batch_size = max(1, min(int(args.seed_batch_size), 500))
    gap_recovery_limit = max(0, min(int(args.gap_recovery_limit), 1_000))
    cycle = 0
    final_status = "failed"
    while args.max_cycles <= 0 or cycle < args.max_cycles:
        cycle += 1
        started = datetime.now().astimezone()
        started_monotonic = time.monotonic()
        base = {
            "schema_version": "market_history_refresh_heartbeat.v1",
            "pid": os.getpid(),
            "cycle": cycle,
            "started_at": started.isoformat(timespec="seconds"),
            "completed_at": started.isoformat(timespec="seconds"),
            "interval_seconds": interval_seconds,
            "retry_interval_seconds": retry_interval_seconds,
            "deadline_seconds": deadline_seconds,
            "timeout_seconds": deadline_seconds,
            "days": days,
            "source_policy": args.source_policy,
            "batch_size": batch_size,
            "max_workers": max_workers,
            "seed_batch_size": seed_batch_size,
            "gap_recovery_limit": gap_recovery_limit,
            "scan_timeout_seconds": max(1, int(args.scan_timeout_seconds)),
            "candidate_limit": max(1, min(int(args.candidate_limit), 500)),
            "lookback_bars": max(60, min(int(args.lookback_bars), 500)),
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": False,
        }
        latest_progress: dict[str, Any] = {}

        def _progress(event: dict[str, Any]) -> None:
            nonlocal latest_progress
            if isinstance(event.get("progress"), dict):
                latest_progress = dict(event["progress"])
            completed = datetime.now().astimezone()
            write_heartbeat(
                {
                    **base,
                    "status": str(event.get("status") or "running"),
                    "phase": str(event.get("phase") or "planning"),
                    "completed_at": completed.isoformat(timespec="seconds"),
                    "duration_seconds": round(time.monotonic() - started_monotonic, 3),
                    "progress": latest_progress,
                    "errors": [],
                    "error_count": 0,
                },
                args.heartbeat_path,
            )

        _progress({"status": "running", "phase": "health", "progress": {}})
        try:
            result = run_cycle(
                args.api_base,
                source_database=args.source_database,
                target_database=args.target_database,
                universe_manifest_path=args.universe_manifest_path,
                days=days,
                source_policy=args.source_policy,
                batch_size=batch_size,
                max_workers=max_workers,
                seed_batch_size=seed_batch_size,
                gap_recovery_limit=gap_recovery_limit,
                deadline_seconds=deadline_seconds,
                scan_timeout_seconds=base["scan_timeout_seconds"],
                candidate_limit=base["candidate_limit"],
                lookback_bars=base["lookback_bars"],
                progress_fn=_progress,
            )
            final_status = str(result.get("status") or "failed").strip().lower()
        except (
            OSError,
            TimeoutError,
            ValueError,
            RuntimeError,
            KeyError,
            sqlite3.Error,
            json.JSONDecodeError,
            urllib.error.URLError,
        ) as exc:
            final_status = "failed"
            result = {
                "status": "failed",
                "errors": [
                    {
                        "stage": "worker",
                        "error": f"{type(exc).__name__}: {exc}"[-2000:],
                    }
                ],
                "safety": _safety(bool(settings.enable_live_trading)),
            }
        completed = datetime.now().astimezone()
        next_interval = next_interval_seconds(
            final_status,
            interval_seconds,
            retry_interval_seconds,
            reason=str(result.get("reason") or "") or None,
            now=completed,
        )
        errors = [
            dict(item)
            for item in (result.get("errors") or [])[:50]
            if isinstance(item, dict)
        ]
        scan = result.get("scan") if isinstance(result.get("scan"), dict) else {}
        heartbeat = {
            **base,
            "status": final_status,
            "phase": (
                "idle" if final_status in {"completed", "skipped"} else "retry_wait"
            ),
            "completed_at": completed.isoformat(timespec="seconds"),
            "duration_seconds": round(time.monotonic() - started_monotonic, 3),
            "next_interval_seconds": next_interval,
            "target_session": result.get("target_session"),
            "calendar_source": result.get("calendar_source"),
            "official_universe_count": int(result.get("official_universe_count") or 0),
            "qfq_ready_count": int(result.get("qfq_ready_count") or 0),
            "qfq_gap_count_before": int(result.get("qfq_gap_count_before") or 0),
            "qfq_gap_recovery_planned": int(
                result.get("qfq_gap_recovery_planned") or 0
            ),
            "qfq_gap_recovered": int(result.get("qfq_gap_recovered") or 0),
            "qfq_gap_remaining": int(result.get("qfq_gap_remaining") or 0),
            "permanent_qfq_gap_count": int(result.get("permanent_qfq_gap_count") or 0),
            "refresh_planned": int(result.get("refresh_planned") or 0),
            "refreshed": int(result.get("refreshed") or 0),
            "refresh_failed": int(result.get("refresh_failed") or 0),
            "seed_batches": int(result.get("seed_batches") or 0),
            "seeded_symbols": int(result.get("seeded_symbols") or 0),
            "scan_status": scan.get("status"),
            "scan_id": scan.get("scan_id"),
            "selected_count": int(scan.get("selected_count") or 0),
            "progress": latest_progress,
            "errors": errors,
            "error_count": len(result.get("errors") or []),
            "errors_truncated": len(result.get("errors") or []) > len(errors),
            "review_only": bool((result.get("safety") or {}).get("review_only", True)),
            "simulation_only": bool(
                (result.get("safety") or {}).get("simulation_only", True)
            ),
            "live_trading_enabled": (result.get("safety") or {}).get(
                "live_trading_enabled",
                False,
            ),
        }
        write_heartbeat(heartbeat, args.heartbeat_path)
        print(json.dumps(heartbeat, ensure_ascii=False), flush=True)
        if args.max_cycles <= 0 or cycle < args.max_cycles:
            time.sleep(next_interval)
    return 1 if final_status in {"blocked", "failed", "error"} else 0


if __name__ == "__main__":
    raise SystemExit(main())
