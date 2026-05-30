import json

from app.experience.code_evolution import CodeEvolutionService
from app.storage.sqlite_store import SQLiteStore


def _seed_v3_evidence(store: SQLiteStore) -> None:
    summary = {
        "backtest_warnings": ["insufficient_benchmark_data", "partial_fill_low_liquidity"],
        "portfolio_risk": {
            "posture": "stop_new_entries",
            "gates": [
                {
                    "name": "max_drawdown_stop",
                    "status": "blocked",
                    "value": 0.12,
                    "limit": 0.1,
                    "reason": "drawdown too high",
                }
            ],
        },
        "safety": {
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": False,
        },
    }
    classification = {
        "failure_cases": [
            {"symbol": "SZ002081", "realized_pnl": -100.0, "exit_reason": "stop_loss"}
        ]
    }
    with store.connect() as conn:
        for table in (
            "code_evolution_records",
            "strategy_performance_snapshots",
            "experience_events",
            "experience_reviews",
        ):
            conn.execute(f"DELETE FROM {table}")
        conn.execute(
            """
            INSERT INTO experience_reviews(
                period_type, period_start, period_end, title, summary_json,
                classification_json, next_actions_json, live_trading_enabled
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(period_type, period_start, period_end) DO UPDATE SET
                title = excluded.title,
                summary_json = excluded.summary_json,
                classification_json = excluded.classification_json,
                next_actions_json = excluded.next_actions_json,
                live_trading_enabled = excluded.live_trading_enabled
            """,
            (
                "daily",
                "2026-05-30",
                "2026-05-30",
                "seed review",
                json.dumps(summary),
                json.dumps(classification),
                "[]",
                0,
            ),
        )
        conn.execute(
            """
            INSERT INTO experience_events(
                source_key, event_date, event_type, category, source_table,
                source_id, symbol, outcome_label, confidence, payload_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "test:data_quality:1",
                "2026-05-30",
                "price_readiness",
                "data_quality",
                "price_readiness_reports",
                "1",
                "SZ002081",
                "error",
                0.8,
                json.dumps({"error_message": "missing history"}),
            ),
        )
        conn.execute(
            """
            INSERT INTO strategy_performance_snapshots(
                strategy_name, period_start, period_end, metrics_json, source_run_id
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                "local_rule_v2_5",
                "2026-05-01",
                "2026-05-30",
                json.dumps({"total_return": -0.03, "max_drawdown": 0.12}),
                1,
            ),
        )


def test_code_evolution_generation_is_review_only_and_idempotent(test_db):
    _seed_v3_evidence(test_db)
    service = CodeEvolutionService()

    first = service.generate_review_items(limit=5)
    second = service.generate_review_items(limit=5)

    assert 1 <= first["created_count"] <= 5
    assert second["created_count"] == 0
    assert second["skipped_duplicate_count"] >= first["created_count"]
    assert first["review_only"] is True
    assert first["simulation_only"] is True
    assert first["live_trading_enabled"] is False
    assert {item["status"] for item in first["created"]} == {"draft"}


def test_code_evolution_status_flow(test_db):
    _seed_v3_evidence(test_db)
    service = CodeEvolutionService()
    record = service.generate_review_items(limit=1)["created"][0]

    failed = service.record_validation(record["id"], {"passed": False, "commands": []})
    passed = service.record_validation(record["id"], {"passed": True, "commands": []})
    accepted = service.approve(record["id"], reviewed_by="tester", note="ok")

    assert failed["status"] == "validation_failed"
    assert passed["status"] == "validation_passed"
    assert accepted["status"] == "accepted"
    assert accepted["reviewed_by"] == "tester"


def test_code_evolution_api_smoke_and_safety(client, test_db):
    _seed_v3_evidence(test_db)

    generate_resp = client.post("/api/experience/code-evolution/generate?limit=5")
    records_resp = client.get("/api/experience/code-evolution?limit=10")
    record_id = records_resp.json()[0]["id"]
    detail_resp = client.get(f"/api/experience/code-evolution/{record_id}")
    premature_approve_resp = client.post(
        f"/api/experience/code-evolution/{record_id}/approve",
        json={"reviewed_by": "tester", "note": "not validated"},
    )
    validation_resp = client.post(
        f"/api/experience/code-evolution/{record_id}/validation",
        json={"validation": {"passed": True, "commands": []}},
    )
    approve_resp = client.post(
        f"/api/experience/code-evolution/{record_id}/approve",
        json={"reviewed_by": "tester", "note": "validated"},
    )

    assert generate_resp.status_code == 200
    assert records_resp.status_code == 200
    assert detail_resp.status_code == 200
    assert premature_approve_resp.status_code == 400
    assert validation_resp.status_code == 200
    assert approve_resp.status_code == 200
    assert approve_resp.json()["status"] == "accepted"
    assert client.get("/health").json()["live_trading_enabled"] is False


def test_code_evolution_routes_do_not_add_live_trading_controls(client):
    paths = client.get("/openapi.json").json()["paths"]
    code_evolution_paths = [path for path in paths if path.startswith("/api/experience/code-evolution")]

    assert code_evolution_paths
    assert all("broker" not in path.lower() for path in code_evolution_paths)
    assert all("credential" not in path.lower() for path in code_evolution_paths)
    assert all("live" not in path.lower() for path in code_evolution_paths)
