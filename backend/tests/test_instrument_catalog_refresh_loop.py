from __future__ import annotations

import json
import os
from pathlib import Path

from scripts import instrument_catalog_refresh_loop


class ServiceMustNotRun:
    def run(self, **kwargs):
        raise AssertionError("catalog service must not run when remote live trading is enabled")


class CompletedService:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def run(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "status": "completed",
            "member_count": 5_528,
            "snapshot_id": 7,
            "writes_enabled": True,
            "safety": {
                "research_only": True,
                "simulation_only": True,
                "live_trading_enabled": False,
                "broker_or_order_capability": False,
                "writes_enabled": True,
            },
        }


def test_run_once_blocks_before_service_when_remote_health_enables_live_trading(
    tmp_path: Path,
) -> None:
    def request_fn(url: str, timeout: int):
        assert url == "http://127.0.0.1:8000/health"
        assert timeout == 10
        return {"status": "ok", "live_trading_enabled": True}

    result = instrument_catalog_refresh_loop.run_once(
        "http://127.0.0.1:8000",
        database_path=tmp_path / "market_history.sqlite3",
        manifest_path=tmp_path / "current_a_share_universe.json",
        request_fn=request_fn,
        service=ServiceMustNotRun(),
    )

    assert result["status"] == "blocked"
    assert result["reason"] == "remote_live_trading_enabled"
    assert result["writes_enabled"] is False
    assert result["safety"]["research_only"] is True
    assert result["safety"]["simulation_only"] is True
    assert result["safety"]["live_trading_enabled"] is True


def test_run_once_refuses_write_when_remote_health_is_not_ok(tmp_path: Path) -> None:
    result = instrument_catalog_refresh_loop.run_once(
        "http://127.0.0.1:8000",
        database_path=tmp_path / "market_history.sqlite3",
        manifest_path=tmp_path / "current_a_share_universe.json",
        request_fn=lambda url, timeout: {
            "status": "degraded",
            "live_trading_enabled": False,
        },
        service=ServiceMustNotRun(),
    )

    assert result["status"] == "partial"
    assert result["reason"] == "remote_health_not_ok"
    assert result["writes_enabled"] is False
    assert result["safety"]["live_trading_enabled"] is False


def test_once_mode_writes_completed_heartbeat_and_uses_daily_success_interval(
    tmp_path: Path,
) -> None:
    heartbeat_path = tmp_path / "instrument_catalog_heartbeat.json"
    service = CompletedService()

    exit_code = instrument_catalog_refresh_loop.main(
        [
            "--once",
            "--database-path",
            str(tmp_path / "market_history.sqlite3"),
            "--manifest-path",
            str(tmp_path / "current_a_share_universe.json"),
            "--heartbeat-path",
            str(heartbeat_path),
            "--interval-seconds",
            "86400",
            "--retry-seconds",
            "900",
        ],
        request_fn=lambda url, timeout: {
            "status": "ok",
            "live_trading_enabled": False,
        },
        service=service,
    )

    assert exit_code == 0
    assert service.calls == [
        {"apply": True, "manifest_path": str(tmp_path / "current_a_share_universe.json")}
    ]
    heartbeat = json.loads(heartbeat_path.read_text(encoding="utf-8"))
    assert heartbeat["worker"] == "instrument_catalog_refresh"
    assert heartbeat["status"] == "completed"
    assert heartbeat["phase"] == "sleeping"
    assert heartbeat["next_interval_seconds"] == 86_400
    assert heartbeat["result"]["member_count"] == 5_528
    assert heartbeat["result"]["safety"]["live_trading_enabled"] is False


def test_every_heartbeat_contains_the_continuous_stack_contract(
    tmp_path: Path,
    monkeypatch,
) -> None:
    heartbeats: list[dict] = []
    monkeypatch.setattr(
        instrument_catalog_refresh_loop,
        "_write_heartbeat",
        lambda path, payload: heartbeats.append(payload),
    )

    exit_code = instrument_catalog_refresh_loop.main(
        [
            "--once",
            "--heartbeat-path",
            str(tmp_path / "heartbeat.json"),
            "--interval-seconds",
            "7200",
            "--retry-seconds",
            "600",
            "--minimum-member-count",
            "4000",
            "--minimum-retained-ratio",
            "0.9",
        ],
        request_fn=lambda url, timeout: {
            "status": "ok",
            "live_trading_enabled": False,
        },
        service=CompletedService(),
    )

    assert exit_code == 0
    assert [heartbeat["status"] for heartbeat in heartbeats] == ["running", "completed"]
    for heartbeat in heartbeats:
        assert heartbeat["pid"] == os.getpid()
        assert heartbeat["cycle"] == 1
        assert heartbeat["completed_at"]
        assert heartbeat["interval_seconds"] == 7_200
        assert heartbeat["retry_interval_seconds"] == 600
        assert heartbeat["minimum_member_count"] == 4_000
        assert heartbeat["minimum_retained_ratio"] == 0.9
        assert heartbeat["review_only"] is True
        assert heartbeat["simulation_only"] is True
        assert heartbeat["live_trading_enabled"] is False
        assert "safety" in heartbeat
    assert heartbeats[-1]["completed_at"] == heartbeats[-1]["last_completed_at"]
    assert "result" in heartbeats[-1]
