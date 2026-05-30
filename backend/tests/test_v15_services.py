from app.ai.review_worker import AIReviewWorker
from app.market_regime.service import MarketRegimeService
from app.monitoring.service import MonitoringService
from app.risk.portfolio import PortfolioRiskService
from app.storage.sqlite_store import SQLiteStore
from app.config import settings


def test_market_regime_refresh_and_portfolio_state():
    store = SQLiteStore(settings.database_path)
    store.init()
    with store.connect() as conn:
        conn.execute("DELETE FROM daily_bar_cache")
        for idx, close in enumerate([100, 101, 102, 103, 104], start=1):
            conn.execute(
                """
                INSERT INTO daily_bar_cache(
                    symbol, trade_date, open, high, low, close, volume, amount, source, quality_status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "sh000001",
                    f"2020-01-0{idx}",
                    close,
                    close + 1,
                    close - 1,
                    close,
                    10000,
                    1000000,
                    "fixture",
                    "ready",
                ),
            )

    regime = MarketRegimeService().refresh("2020-01-05")
    assert regime["regime"] in {"strong", "neutral", "weak", "extreme_risk"}
    state = PortfolioRiskService().state()
    assert state["live_trading_enabled"] is False
    assert state["posture"] in {"normal", "reduce", "stop_new_entries"}


def test_ai_proposal_validation_and_rejection():
    worker = AIReviewWorker()
    proposal = worker.generate_review()
    validation = worker.validate_proposal(proposal["id"])
    assert validation["status"] in {"validation_failed", "validation_passed"}
    rejected = worker.reject(proposal["id"], reviewed_by="pytest", note="test rejection")
    assert rejected["status"] == "rejected"


def test_monitoring_alert_action_lifecycle():
    store = SQLiteStore(settings.database_path)
    store.init()
    with store.connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO monitoring_sessions(name, status, symbols_json)
            VALUES (?, ?, ?)
            """,
            ("pytest", "running", "[]"),
        )
        session_id = int(cursor.lastrowid)
        event_cursor = conn.execute(
            """
            INSERT INTO monitoring_events(session_id, symbol, signal, allowed)
            VALUES (?, ?, ?, ?)
            """,
            (session_id, "SH600000", "sim_buy_allowed", 0),
        )
        alert_cursor = conn.execute(
            """
            INSERT INTO monitoring_alerts(session_id, event_id, symbol, severity, alert_type, message)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (session_id, int(event_cursor.lastrowid), "SH600000", "high", "sim_buy_allowed", "review"),
        )
        alert_id = int(alert_cursor.lastrowid)

    action = MonitoringService().record_alert_action(alert_id, "acknowledge", created_by="pytest")
    assert action["payload"]["live_trading_enabled"] is False
    lifecycle = MonitoringService().alert_lifecycle(symbol="SH600000")
    assert lifecycle["actioned_count"] >= 1
