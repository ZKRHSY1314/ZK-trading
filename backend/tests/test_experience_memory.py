import json

from app.config import settings
from app.experience.memory import ExperienceMemoryService
from app.storage.sqlite_store import SQLiteStore


def _seed_experience_sources(store: SQLiteStore) -> None:
    with store.connect() as conn:
        conn.execute(
            """
            INSERT INTO candidate_lifecycle_events(
                symbol, name, from_state, to_state, event_type, source, payload_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "SZ002081",
                "sample",
                "auto_discovered",
                "pending_review",
                "add_to_review",
                "test",
                "{}",
                "2026-05-28 10:00:00",
            ),
        )
        conn.execute(
            """
            INSERT INTO monitoring_sessions(name, status, symbols_json, summary_json, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("test_session", "completed", '["SZ002081"]', "{}", "2026-05-28 10:01:00"),
        )
        session_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute(
            """
            INSERT INTO monitoring_events(
                session_id, symbol, name, signal, allowed, summary, snapshot_json, plan_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                "SZ002081",
                "sample",
                "risk_blocked_observe",
                0,
                "risk block",
                "{}",
                "{}",
                "2026-05-28 10:02:00",
            ),
        )
        event_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute(
            """
            INSERT INTO monitoring_alerts(
                session_id, event_id, symbol, severity, alert_type, message, payload_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                event_id,
                "SZ002081",
                "high",
                "risk_blocked_observe",
                "blocked for review",
                "{}",
                "2026-05-28 10:03:00",
            ),
        )
        alert_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute(
            """
            INSERT INTO monitoring_alert_actions(alert_id, action_type, note, created_by, payload_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                alert_id,
                "add_to_review",
                "review only",
                "test",
                "{}",
                "2026-05-28 10:04:00",
            ),
        )
        conn.execute(
            """
            INSERT INTO historical_backtest_runs(
                config_json, data_source, start_date, end_date, status, benchmark_symbol,
                initial_cash, final_cash, metrics_json, benchmark_json, execution_warnings_json, completed_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "{}",
                "daily_bar_cache",
                "2026-03-01",
                "2026-05-28",
                "completed",
                "SH000300",
                100000.0,
                104000.0,
                json.dumps(
                    {
                        "total_return": 0.04,
                        "max_drawdown": 0.03,
                        "closed_trade_count": 2,
                        "expectancy": 1200.0,
                    }
                ),
                json.dumps({"symbol": "SH000300", "status": "ok", "return": 0.01}),
                json.dumps(["partial_fill_low_liquidity"]),
                "2026-05-28 15:10:00",
            ),
        )
        run_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute(
            """
            INSERT INTO historical_backtest_closed_trades(
                run_id, symbol, quantity, entry_date, exit_date, entry_price, exit_price,
                realized_pnl, realized_pnl_pct, holding_days, fees, stamp_tax, exit_reason
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                "SZ002081",
                1000,
                "2026-05-20",
                "2026-05-28",
                10.0,
                11.0,
                980.0,
                0.098,
                8,
                10.0,
                10.0,
                "take_profit",
            ),
        )


def test_experience_memory_captures_and_reviews(test_db):
    _seed_experience_sources(test_db)
    service = ExperienceMemoryService()

    capture = service.capture_recent_events(limit=50)
    second_capture = service.capture_recent_events(limit=50)
    review = service.create_daily_review("2026-05-28")

    assert capture["inserted_count"] >= 4
    assert second_capture["inserted_count"] == 0
    assert capture["live_trading_enabled"] is False
    assert review["live_trading_enabled"] is False
    assert review["summary"]["safety"]["review_only"] is True
    assert review["summary"]["safety"]["simulation_only"] is True
    assert review["summary"]["backtest_metrics"]["closed_trade_count"] == 2
    assert review["strategy_snapshot"] is not None
    assert service.summary()["review_count"] >= 1


def test_experience_api_smoke(client, test_db):
    _seed_experience_sources(test_db)

    review_resp = client.post("/api/experience/reviews/daily?review_date=2026-05-28")
    summary_resp = client.get("/api/experience/summary")
    events_resp = client.get("/api/experience/events?category=closed_trade")
    performance_resp = client.get("/api/experience/strategy-performance")
    evolution_resp = client.get("/api/experience/code-evolution")

    assert review_resp.status_code == 200
    assert summary_resp.status_code == 200
    assert events_resp.status_code == 200
    assert performance_resp.status_code == 200
    assert evolution_resp.status_code == 200
    assert review_resp.json()["summary"]["safety"]["live_trading_enabled"] == settings.enable_live_trading
    assert len(events_resp.json()) >= 1
