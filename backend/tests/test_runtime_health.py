from datetime import datetime, timedelta, timezone
import json

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.runtime.status import readiness_snapshot


def test_livez_reports_process_health(client):
    response = client.get("/livez")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["live_trading_enabled"] is False
    assert isinstance(payload["pid"], int)
    assert payload["pid"] > 0


def test_readyz_reports_read_only_database_snapshot(client, test_db):
    modified_before = test_db.db_path.stat().st_mtime_ns

    response = client.get("/readyz")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["live_trading_enabled"] is False
    assert payload["database"]["readable"] is True
    assert payload["database"]["schema_ready"] is True
    assert payload["database"]["missing_required_tables"] == []
    assert "control_plane" in payload["workers"]
    assert "codex_decision_review" in payload["workers"]
    assert "reference_data" in payload["workers"]
    assert "full_market_features" in payload["workers"]
    assert "market_history_refresh" in payload["workers"]
    assert "capital_flow_refresh" in payload["workers"]
    assert "instrument_catalog_refresh" in payload["workers"]
    assert "full_market_calibration" in payload["workers"]
    assert isinstance(payload["attention"], list)
    assert test_db.db_path.stat().st_mtime_ns == modified_before


def test_app_lifespan_initializes_runtime_database_before_readyz(tmp_path):
    original_path = settings.database_path
    settings.database_path = tmp_path / "runtime.sqlite3"
    try:
        with TestClient(app) as runtime_client:
            response = runtime_client.get("/readyz")
    finally:
        settings.database_path = original_path

    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_readiness_reports_worker_heartbeat_without_mutating_it(tmp_path, test_db):
    heartbeat = tmp_path / "worker.json"
    heartbeat.write_text(
        '{"pid":123,"cycle":4,"status":"partial","completed_at":"2099-01-01T00:00:00+00:00"}',
        encoding="utf-8",
    )
    modified_before = heartbeat.stat().st_mtime_ns

    snapshot = readiness_snapshot(
        test_db.db_path,
        heartbeat_paths={"control_plane": heartbeat},
    )

    assert snapshot["status"] == "ready"
    assert snapshot["workers"]["control_plane"]["status"] == "degraded"
    assert "control_plane_heartbeat_degraded" in snapshot["attention"]
    assert snapshot["workers"]["control_plane"]["pid"] == 123
    assert heartbeat.stat().st_mtime_ns == modified_before


def test_readiness_does_not_call_an_empty_market_pulse_healthy(tmp_path, test_db):
    heartbeat = tmp_path / "codex-worker.json"
    heartbeat.write_text(
        '{"pid":456,"cycle":2,"status":"empty","completed_at":"2099-01-01T00:00:00+00:00"}',
        encoding="utf-8",
    )

    snapshot = readiness_snapshot(
        test_db.db_path,
        heartbeat_paths={"codex_market_pulse": heartbeat},
    )

    assert snapshot["workers"]["codex_market_pulse"]["status"] == "degraded"
    assert "codex_market_pulse_heartbeat_degraded" in snapshot["attention"]


def test_readiness_reports_failed_decision_review_as_degraded(tmp_path, test_db):
    heartbeat = tmp_path / "decision-worker.json"
    heartbeat.write_text(
        '{"pid":457,"cycle":2,"status":"failed",'
        '"completed_at":"2099-01-01T00:00:00+00:00"}',
        encoding="utf-8",
    )

    snapshot = readiness_snapshot(
        test_db.db_path,
        heartbeat_paths={"codex_decision_review": heartbeat},
    )

    assert snapshot["workers"]["codex_decision_review"]["status"] == "degraded"
    assert "codex_decision_review_heartbeat_degraded" in snapshot["attention"]


def test_readiness_reports_an_active_cycle_as_running_not_healthy(tmp_path, test_db):
    heartbeat = tmp_path / "running-worker.json"
    heartbeat.write_text(
        json.dumps(
            {
                "pid": 458,
                "cycle": 3,
                "status": "running",
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "timeout_seconds": 900,
            }
        ),
        encoding="utf-8",
    )

    snapshot = readiness_snapshot(
        test_db.db_path,
        heartbeat_paths={"codex_market_pulse": heartbeat},
    )

    assert snapshot["workers"]["codex_market_pulse"]["status"] == "running"
    assert "codex_market_pulse_heartbeat_running" in snapshot["attention"]


def test_reference_data_heartbeat_uses_a_five_hour_stale_window(tmp_path, test_db):
    heartbeat = tmp_path / "reference-worker.json"
    completed_at = datetime.now(timezone.utc) - timedelta(hours=4, minutes=30)
    heartbeat.write_text(
        json.dumps(
            {
                "pid": 789,
                "cycle": 3,
                "status": "completed",
                "completed_at": completed_at.isoformat(),
            }
        ),
        encoding="utf-8",
    )

    healthy = readiness_snapshot(
        test_db.db_path,
        heartbeat_paths={"reference_data": heartbeat},
    )

    assert healthy["workers"]["reference_data"]["status"] == "healthy"
    assert healthy["workers"]["reference_data"]["pid"] == 789

    stale_at = datetime.now(timezone.utc) - timedelta(hours=5, minutes=1)
    heartbeat.write_text(
        json.dumps(
            {
                "pid": 789,
                "cycle": 3,
                "status": "completed",
                "completed_at": stale_at.isoformat(),
            }
        ),
        encoding="utf-8",
    )
    stale = readiness_snapshot(
        test_db.db_path,
        heartbeat_paths={"reference_data": heartbeat},
    )

    assert stale["workers"]["reference_data"]["status"] == "stale"
    assert "reference_data_heartbeat_stale" in stale["attention"]


def test_market_history_refresh_heartbeat_uses_a_five_hour_stale_window(
    tmp_path, test_db
):
    heartbeat = tmp_path / "market-history-refresh-worker.json"
    completed_at = datetime.now(timezone.utc) - timedelta(hours=4, minutes=30)
    heartbeat.write_text(
        json.dumps(
            {
                "pid": 790,
                "cycle": 2,
                "status": "completed",
                "completed_at": completed_at.isoformat(),
                "timeout_seconds": 900,
                "deadline_seconds": 900,
            }
        ),
        encoding="utf-8",
    )

    healthy = readiness_snapshot(
        test_db.db_path,
        heartbeat_paths={"market_history_refresh": heartbeat},
    )

    assert healthy["workers"]["market_history_refresh"]["status"] == "healthy"
    assert healthy["workers"]["market_history_refresh"]["pid"] == 790
    assert healthy["workers"]["market_history_refresh"]["timeout_seconds"] == 900
    assert healthy["workers"]["market_history_refresh"]["deadline_seconds"] == 900

    stale_at = datetime.now(timezone.utc) - timedelta(hours=5, minutes=1)
    heartbeat.write_text(
        json.dumps(
            {
                "pid": 790,
                "cycle": 2,
                "status": "completed",
                "completed_at": stale_at.isoformat(),
            }
        ),
        encoding="utf-8",
    )
    stale = readiness_snapshot(
        test_db.db_path,
        heartbeat_paths={"market_history_refresh": heartbeat},
    )

    assert stale["workers"]["market_history_refresh"]["status"] == "stale"
    assert "market_history_refresh_heartbeat_stale" in stale["attention"]


def test_capital_flow_refresh_heartbeat_uses_a_thirty_minute_stale_window(
    tmp_path, test_db
):
    heartbeat = tmp_path / "capital-flow-refresh-worker.json"
    heartbeat.write_text(
        json.dumps(
            {
                "pid": 793,
                "cycle": 5,
                "status": "degraded",
                "completed_at": (
                    datetime.now(timezone.utc) - timedelta(minutes=29)
                ).isoformat(),
            }
        ),
        encoding="utf-8",
    )

    healthy_age = readiness_snapshot(
        test_db.db_path,
        heartbeat_paths={"capital_flow_refresh": heartbeat},
    )
    assert healthy_age["workers"]["capital_flow_refresh"]["status"] == "degraded"

    heartbeat.write_text(
        json.dumps(
            {
                "pid": 793,
                "cycle": 5,
                "status": "completed",
                "completed_at": (
                    datetime.now(timezone.utc) - timedelta(minutes=31)
                ).isoformat(),
            }
        ),
        encoding="utf-8",
    )
    stale = readiness_snapshot(
        test_db.db_path,
        heartbeat_paths={"capital_flow_refresh": heartbeat},
    )
    assert stale["workers"]["capital_flow_refresh"]["status"] == "stale"
    assert "capital_flow_refresh_heartbeat_stale" in stale["attention"]


def test_daily_research_workers_use_a_twenty_five_hour_stale_window(
    tmp_path, test_db
):
    heartbeat = tmp_path / "daily-research-worker.json"
    completed_at = datetime.now(timezone.utc) - timedelta(hours=24, minutes=30)
    heartbeat.write_text(
        json.dumps(
            {
                "pid": 791,
                "cycle": 4,
                "status": "completed",
                "completed_at": completed_at.isoformat(),
                "deadline_seconds": 900,
            }
        ),
        encoding="utf-8",
    )

    for worker_name in ("instrument_catalog_refresh", "full_market_calibration"):
        healthy = readiness_snapshot(
            test_db.db_path,
            heartbeat_paths={worker_name: heartbeat},
        )
        assert healthy["workers"][worker_name]["status"] == "healthy"
        assert healthy["workers"][worker_name]["pid"] == 791

    stale_at = datetime.now(timezone.utc) - timedelta(hours=25, minutes=1)
    heartbeat.write_text(
        json.dumps(
            {
                "pid": 791,
                "cycle": 4,
                "status": "completed",
                "completed_at": stale_at.isoformat(),
            }
        ),
        encoding="utf-8",
    )
    for worker_name in ("instrument_catalog_refresh", "full_market_calibration"):
        stale = readiness_snapshot(
            test_db.db_path,
            heartbeat_paths={worker_name: heartbeat},
        )
        assert stale["workers"][worker_name]["status"] == "stale"
        assert f"{worker_name}_heartbeat_stale" in stale["attention"]
