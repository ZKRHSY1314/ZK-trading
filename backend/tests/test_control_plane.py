from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from app.control_plane.service import ControlPlaneService
from app.data.trading_calendar import trading_session_age
from app.storage.sqlite_store import SQLiteStore


SHANGHAI = ZoneInfo("Asia/Shanghai")


class _Pulse:
    def __init__(self, status: str = "completed") -> None:
        self.status = status

    def latest_context(self, limit: int) -> dict:
        return {"status": "completed", "top_sectors": [{"sector": "ai_compute"}]}

    def run(self, **_: object) -> dict:
        return {
            "status": self.status,
            "run_id": 7,
            "item_count": 12,
            "sector_count": 2,
            "source_count": 4,
            "successful_source_count": 3,
            "sector_signals": [{"sector": "ai_compute", "heat_score": 55}],
            "errors": [],
        }


class _Feedback:
    def snapshot(self) -> dict:
        return {"status": "needs_outcomes", "sample_count": 4, "mature_outcome_count": 0}

    def run(self, **_: object) -> dict:
        return {
            "status": "partial",
            "created_samples": 3,
            "labeled_outcomes": 0,
            "mature_outcome_count": 0,
            "blocked_reasons": ["insufficient_mature_outcomes"],
        }


class _Selection:
    def run(self, **_: object) -> dict:
        return {
            "status": "completed",
            "schema_version": "strategy_selection_v2.1",
            "date": "2026-07-10",
            "config_version": "pytest-v1",
            "summary": {"candidate_count": 1},
            "daily_candidate_snapshot": [
                {
                    "symbol": "SZ000001",
                    "name": "fixture",
                    "plan_type": "WATCH_ONLY_PLAN",
                    "final_score": 65,
                    "risk_flags": [],
                }
            ],
            "data_gap_candidates": [],
        }


class _AgentControl:
    def create_task(self, task):
        assert task.task_type == "full_simulation_cycle"
        assert task.payload["limit"] == 20
        assert task.payload["decision_snapshot"]["schema_version"] == "strategy_selection_v2.1"
        assert task.payload["decision_snapshot"]["daily_candidate_snapshot"][0]["symbol"] == "SZ000001"
        return SimpleNamespace(id=99)

    def execute_task(self, task_id: int):
        assert task_id == 99
        return SimpleNamespace(
            id=99,
            model_dump=lambda **_: {
                "id": 99,
                "status": "completed",
                "result": {"status": "partial"},
                "error": None,
            },
        )


def _service(
    test_db,
    *,
    hour: int = 10,
    pulse_status: str = "completed",
    market_status: str = "missing",
) -> ControlPlaneService:
    return ControlPlaneService(
        store=test_db,
        public_opinion_factory=lambda: _Pulse(pulse_status),
        feedback_factory=_Feedback,
        selection_factory=_Selection,
        agent_control_factory=_AgentControl,
        market_data_factory=lambda _now, _limit: {
            "status": market_status,
            "latest_trade_date": "2026-07-10" if market_status == "fresh" else None,
            "decision_allowed": market_status == "fresh",
        },
        market_data_refresh_factory=lambda _: {"processed": 0, "results": []},
        clock=lambda: datetime(2026, 7, 10, hour, 0, tzinfo=SHANGHAI),
    )


def test_control_plane_status_is_read_only_and_reports_feedback_gap(test_db):
    result = _service(test_db).status()

    assert result["status"] == "attention"
    assert result["market_stage"] == "intraday"
    assert result["recommended_profile"] == "full"
    assert "training_feedback_needs_outcomes" in result["attention_reasons"]
    assert "market_data_missing" in result["attention_reasons"]
    assert result["safety"]["live_trading_enabled"] is False
    assert result["safety"]["real_order_placement"] is False


def test_control_plane_full_run_preserves_partial_business_status(test_db):
    result = _service(test_db, market_status="fresh").run_once(
        profile="full",
        limit=20,
        monitor_limit=3,
        requested_by="pytest",
    )

    assert result["status"] == "partial"
    assert result["task_id"] == 99
    assert [step["step_id"] for step in result["steps"]] == [
        "market_pulse",
        "decision_snapshot",
        "simulation_cycle",
        "training_feedback",
    ]
    simulation = next(step for step in result["steps"] if step["step_id"] == "simulation_cycle")
    assert simulation["status"] == "partial"
    assert result["safety"]["broker_access"] is False


def test_control_plane_persists_every_ranked_candidate_horizon_in_forecast_ledger(test_db):
    result = _service(test_db, market_status="fresh").run_once(
        profile="pulse",
        limit=20,
        requested_by="pytest-ledger",
    )

    decision = next(step for step in result["steps"] if step["step_id"] == "decision_snapshot")
    decision_id = decision["details"]["snapshot_id"]
    rows = test_db.fetch_all(
        """
        SELECT decision_id, scope, subject, horizon_days, review_only
        FROM forecast_decisions
        WHERE decision_id = ?
        ORDER BY horizon_days
        """,
        (decision_id,),
    )

    assert [row["horizon_days"] for row in rows] == [1, 3, 5, 10, 20]
    assert {row["subject"] for row in rows} == {"SZ000001"}
    assert {row["scope"] for row in rows} == {"stock"}
    assert all(row["review_only"] == 1 for row in rows)
    assert decision["details"]["forecast_ledger"]["recorded_count"] == 5


def test_control_plane_full_run_skips_simulation_when_market_data_is_stale(test_db):
    result = _service(test_db, market_status="stale").run_once(profile="full", limit=20)

    simulation = next(step for step in result["steps"] if step["step_id"] == "simulation_cycle")
    assert result["task_id"] is None
    assert simulation["status"] == "partial"
    assert simulation["reason"] == "daily_bar_cache_stale"


def test_control_plane_refreshes_stale_market_data_before_simulation(test_db):
    state = {"status": "stale"}

    def market_data(_now, _limit):
        return {
            "status": state["status"],
            "latest_trade_date": "2026-07-10" if state["status"] == "fresh" else "2026-06-29",
            "decision_allowed": state["status"] == "fresh",
        }

    def refresh(_):
        state["status"] = "fresh"
        return {"processed": 1, "results": [{"status": "success"}]}

    service = ControlPlaneService(
        store=test_db,
        public_opinion_factory=_Pulse,
        feedback_factory=_Feedback,
        selection_factory=_Selection,
        agent_control_factory=_AgentControl,
        market_data_factory=market_data,
        market_data_refresh_factory=refresh,
        clock=lambda: datetime(2026, 7, 10, 10, 0, tzinfo=SHANGHAI),
    )

    result = service.run_once(profile="full", limit=20)

    refresh_step = next(step for step in result["steps"] if step["step_id"] == "market_data_refresh")
    assert refresh_step["status"] == "completed"
    assert result["market_data"]["status"] == "fresh"
    assert result["task_id"] == 99


def test_control_plane_adaptive_offhour_runs_maintenance(test_db):
    result = _service(test_db, hour=22).run_once(profile="adaptive", limit=20)

    assert result["profile"] == "maintenance"
    assert [step["step_id"] for step in result["steps"]] == [
        "market_pulse",
        "market_data_refresh",
        "decision_snapshot",
        "training_feedback",
    ]
    decision = next(step for step in result["steps"] if step["step_id"] == "decision_snapshot")
    assert decision["status"] == "partial"
    assert decision["details"]["reason"] == "daily_bar_cache_missing"


def test_control_plane_insufficient_training_samples_is_partial(test_db):
    class InsufficientFeedback(_Feedback):
        def run(self, **_: object) -> dict:
            return {"status": "insufficient_samples", "blocked_reasons": ["not_mature"]}

    service = ControlPlaneService(
        store=test_db,
        public_opinion_factory=_Pulse,
        feedback_factory=InsufficientFeedback,
        selection_factory=_Selection,
        agent_control_factory=_AgentControl,
        clock=lambda: datetime(2026, 7, 10, 22, 0, tzinfo=SHANGHAI),
    )

    result = service.run_once(profile="training", limit=20)

    assert result["status"] == "partial"
    assert result["steps"][0]["status"] == "partial"


def test_control_plane_source_failure_is_not_reported_completed(test_db):
    result = _service(test_db, pulse_status="partial").run_once(profile="pulse", limit=20)

    assert result["status"] == "partial"
    assert result["steps"][0]["status"] == "partial"


def test_control_plane_requires_broad_latest_bar_coverage(tmp_path):
    store = SQLiteStore(tmp_path / "market.sqlite3")
    store.init()
    with store.connect() as conn:
        for symbol, trade_date in (("SH600001", "2026-07-10"), ("SZ000001", "2026-07-09")):
            conn.execute(
                """
                INSERT INTO daily_bar_cache(
                    symbol, trade_date, open, high, low, close, source, quality_status
                ) VALUES (?, ?, 10, 10.2, 9.8, 10.1, 'pytest', 'ready')
                """,
                (symbol, trade_date),
            )
    service = ControlPlaneService(
        store=store,
        clock=lambda: datetime(2026, 7, 10, 22, 0, tzinfo=SHANGHAI),
    )

    snapshot = service._market_data_snapshot(datetime(2026, 7, 10, 22, 0, tzinfo=SHANGHAI))

    assert snapshot["status"] == "incomplete"
    assert snapshot["latest_coverage_ratio"] == 0.5
    assert snapshot["decision_allowed"] is False


def test_control_plane_coverage_uses_selection_universe_not_cache_history(tmp_path):
    store = SQLiteStore(tmp_path / "selection-universe.sqlite3")
    store.init()
    with store.connect() as conn:
        for symbol in ("SH600010", "SH600011", "SH600012"):
            conn.execute(
                """
                INSERT INTO stock_profiles(
                    symbol, name, current_price, dataset_name, source_file, raw_json
                ) VALUES (?, ?, 10, 'production', 'import.csv', '{}')
                """,
                (symbol, symbol),
            )
        conn.execute(
            """
            INSERT INTO daily_bar_cache(
                symbol, trade_date, open, high, low, close, source, quality_status
            ) VALUES ('SH600010', '2026-07-10', 10, 10.2, 9.8, 10.1, 'pytest', 'ready')
            """
        )
    service = ControlPlaneService(store=store)

    snapshot = service._market_data_snapshot(
        datetime(2026, 7, 10, 22, 0, tzinfo=SHANGHAI),
        limit=5,
    )

    assert snapshot["universe_source"] == "selection_v2"
    assert snapshot["total_symbol_count"] == 3
    assert snapshot["latest_symbol_count"] == 1
    assert snapshot["latest_coverage_ratio"] == 0.3333
    assert snapshot["status"] == "incomplete"


def test_control_plane_requires_current_session_bar_after_close(tmp_path):
    store = SQLiteStore(tmp_path / "close-freshness.sqlite3")
    store.init()
    with store.connect() as conn:
        conn.execute(
            """
            INSERT INTO daily_bar_cache(
                symbol, trade_date, open, high, low, close, source, quality_status
            ) VALUES ('SH600020', '2026-07-09', 10, 10.2, 9.8, 10.1, 'pytest', 'ready')
            """
        )
    service = ControlPlaneService(store=store)

    intraday = service._market_data_snapshot(
        datetime(2026, 7, 10, 10, 0, tzinfo=SHANGHAI),
        limit=5,
    )
    after_close = service._market_data_snapshot(
        datetime(2026, 7, 10, 16, 0, tzinfo=SHANGHAI),
        limit=5,
    )

    assert intraday["status"] == "fresh"
    assert after_close["status"] == "stale"


def test_trading_session_age_respects_exchange_holiday_gap():
    sessions = {
        datetime(2026, 1, 30, tzinfo=SHANGHAI).date(),
        datetime(2026, 2, 5, tzinfo=SHANGHAI).date(),
    }

    intraday_age, source = trading_session_age(
        datetime(2026, 1, 30, tzinfo=SHANGHAI).date(),
        datetime(2026, 2, 5, tzinfo=SHANGHAI).date(),
        exclude_target_session=True,
        trading_dates=sessions,
    )
    after_close_age, _ = trading_session_age(
        datetime(2026, 1, 30, tzinfo=SHANGHAI).date(),
        datetime(2026, 2, 5, tzinfo=SHANGHAI).date(),
        exclude_target_session=False,
        trading_dates=sessions,
    )

    assert source == "injected"
    assert intraday_age == 0
    assert after_close_age == 1


def test_control_plane_status_route_is_mounted(client):
    response = client.get("/api/control-plane/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "control_plane_status.v1"
    assert payload["safety"]["live_trading_enabled"] is False
    assert payload["safety"]["real_order_placement"] is False
