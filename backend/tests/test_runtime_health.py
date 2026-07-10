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
