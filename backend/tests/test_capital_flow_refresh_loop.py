from __future__ import annotations

from datetime import datetime
import json

from scripts import capital_flow_refresh_loop


class _Service:
    def __init__(self, result: dict) -> None:
        self.result = result
        self.calls = 0

    def refresh_market(self) -> dict:
        self.calls += 1
        return self.result


def test_run_once_checks_remote_safety_before_refreshing() -> None:
    service = _Service({"status": "completed"})

    blocked = capital_flow_refresh_loop.run_once(
        "http://127.0.0.1:8000",
        request_fn=lambda *_args, **_kwargs: {
            "status": "ok",
            "live_trading_enabled": True,
        },
        service=service,
    )

    assert blocked["status"] == "blocked"
    assert blocked["reason"] == "remote_live_trading_enabled"
    assert blocked["review_only"] is True
    assert blocked["simulation_only"] is True
    assert blocked["live_trading_enabled"] is True
    assert service.calls == 0


def test_run_once_refreshes_only_market_research_data() -> None:
    service = _Service(
        {
            "status": "completed",
            "accepted_count": 1,
            "snapshot": {
                "status": "available",
                "as_of": "2026-07-17",
                "source": "akshare.eastmoney.stock_market_fund_flow",
                "live_trading_enabled": False,
            },
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": False,
        }
    )

    result = capital_flow_refresh_loop.run_once(
        "http://127.0.0.1:8000",
        request_fn=lambda *_args, **_kwargs: {
            "status": "ok",
            "live_trading_enabled": False,
        },
        service=service,
    )

    assert result["status"] == "completed"
    assert result["snapshot"]["as_of"] == "2026-07-17"
    assert result["review_only"] is True
    assert result["simulation_only"] is True
    assert result["live_trading_enabled"] is False
    assert service.calls == 1


def test_worker_writes_auditable_degraded_heartbeat(tmp_path) -> None:
    heartbeat_path = tmp_path / "capital-flow-heartbeat.json"
    service = _Service(
        {
            "status": "degraded",
            "reason": "capital_flow_provider_failed",
            "retained_last_known": True,
            "snapshot": {
                "status": "degraded",
                "as_of": "2026-07-17",
                "source": "akshare.eastmoney.stock_market_fund_flow",
            },
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": False,
        }
    )

    exit_code = capital_flow_refresh_loop.main(
        [
            "--max-cycles",
            "1",
            "--heartbeat-path",
            str(heartbeat_path),
            "--interval-seconds",
            "900",
            "--retry-seconds",
            "300",
        ],
        request_fn=lambda *_args, **_kwargs: {
            "status": "ok",
            "live_trading_enabled": False,
        },
        service=service,
        now_fn=lambda: datetime.fromisoformat("2026-07-19T10:00:00+08:00"),
    )

    assert exit_code == 2
    heartbeat = json.loads(heartbeat_path.read_text(encoding="utf-8"))
    assert heartbeat["worker"] == "capital_flow_refresh"
    assert heartbeat["status"] == "degraded"
    assert heartbeat["last_snapshot_date"] == "2026-07-17"
    assert heartbeat["retained_last_known"] is True
    assert heartbeat["next_interval_seconds"] == 300
    assert heartbeat["review_only"] is True
    assert heartbeat["simulation_only"] is True
    assert heartbeat["live_trading_enabled"] is False
