from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
import time
from typing import Any

from app.config import PROJECT_ROOT, settings


_PROCESS_STARTED_MONOTONIC = time.monotonic()
_PROCESS_STARTED_AT = datetime.now(timezone.utc)
_REQUIRED_RUNTIME_TABLES = frozenset(
    {
        "automation_events",
        "automation_runs",
        "daily_bar_cache",
        "public_opinion_runs",
    }
)
_DEFAULT_HEARTBEATS = {
    "control_plane": PROJECT_ROOT / "backend" / "logs" / "control_plane_heartbeat.json",
    "codex_market_pulse": PROJECT_ROOT
    / "backend"
    / "logs"
    / "codex_market_pulse_heartbeat.json",
}


def process_health() -> dict[str, Any]:
    """Return a dependency-free process liveness snapshot."""

    return {
        "status": "ok",
        "service": settings.app_name,
        "environment": settings.app_env,
        "pid": os.getpid(),
        "started_at": _PROCESS_STARTED_AT.isoformat(timespec="seconds"),
        "uptime_seconds": max(0.0, round(time.monotonic() - _PROCESS_STARTED_MONOTONIC, 3)),
        "live_trading_enabled": settings.enable_live_trading,
    }


def readiness_snapshot(
    database_path: str | Path | None = None,
    heartbeat_paths: dict[str, Path] | None = None,
) -> dict[str, Any]:
    """Inspect runtime readiness using a query-only SQLite connection."""

    path = Path(database_path or settings.database_path)
    blockers: list[str] = []
    database: dict[str, Any] = {
        "path": str(path),
        "exists": False,
        "readable": False,
        "schema_ready": False,
        "missing_required_tables": sorted(_REQUIRED_RUNTIME_TABLES),
    }

    if settings.enable_live_trading:
        blockers.append("live_trading_enabled")

    if str(path) == ":memory:":
        blockers.append("ephemeral_memory_database_not_readable_across_connections")
    elif not path.is_file():
        blockers.append("database_missing")
    else:
        database["exists"] = True
        try:
            uri = path.resolve().as_uri() + "?mode=ro"
            with sqlite3.connect(uri, uri=True, timeout=1.0) as connection:
                connection.execute("PRAGMA query_only = ON")
                connection.execute("SELECT 1").fetchone()
                table_names = {
                    str(row[0])
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    ).fetchall()
                }
            missing_tables = sorted(_REQUIRED_RUNTIME_TABLES - table_names)
            database.update(
                {
                    "readable": True,
                    "schema_ready": not missing_tables,
                    "missing_required_tables": missing_tables,
                }
            )
            if missing_tables:
                blockers.append("database_schema_incomplete")
        except sqlite3.Error as exc:
            database["error"] = str(exc)
            blockers.append("database_unreadable")

    workers = {
        name: _heartbeat_snapshot(
            path,
            stale_after_seconds=1800 if name == "control_plane" else 18000,
        )
        for name, path in (heartbeat_paths or _DEFAULT_HEARTBEATS).items()
    }
    attention = [
        f"{name}_heartbeat_{snapshot['status']}"
        for name, snapshot in workers.items()
        if snapshot["status"] != "healthy"
    ]

    return {
        "status": "blocked" if blockers else "ready",
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "environment": settings.app_env,
        "live_trading_enabled": settings.enable_live_trading,
        "database": database,
        "workers": workers,
        "blockers": blockers,
        "attention": attention,
        "read_only": True,
    }


def _heartbeat_snapshot(path: Path, *, stale_after_seconds: int = 18000) -> dict[str, Any]:
    result: dict[str, Any] = {
        "path": str(path),
        "status": "missing",
        "age_seconds": None,
    }
    if not path.is_file():
        return result
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        return {**result, "status": "invalid", "error": str(exc)}
    completed_at = payload.get("completed_at")
    try:
        timestamp = datetime.fromisoformat(str(completed_at).replace("Z", "+00:00"))
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        age_seconds = max(0.0, (datetime.now(timezone.utc) - timestamp.astimezone(timezone.utc)).total_seconds())
    except (TypeError, ValueError):
        return {**result, "status": "invalid", "heartbeat": payload}
    last_status = str(payload.get("status") or "unknown").strip().lower()
    if age_seconds > stale_after_seconds:
        runtime_status = "stale"
    elif last_status in {
        "failed",
        "blocked",
        "partial",
        "degraded",
        "error",
        "empty",
        "insufficient_data",
    }:
        runtime_status = "degraded"
    else:
        runtime_status = "healthy"
    return {
        **result,
        "status": runtime_status,
        "age_seconds": round(age_seconds, 2),
        "pid": payload.get("pid"),
        "cycle": payload.get("cycle"),
        "last_status": last_status,
        "completed_at": completed_at,
    }
