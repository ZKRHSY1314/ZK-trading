from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.automation.supervisor import AutomationSupervisor
from app.config import PROJECT_ROOT, _resolve_project_relative_path
from app.models import CandidateTier, MarketSnapshot, SimulationPlan


def test_database_path_resolution_is_project_root_relative():
    resolved = _resolve_project_relative_path(Path("./trading_local.sqlite3"))

    assert resolved == (PROJECT_ROOT / "trading_local.sqlite3").resolve()
    assert _resolve_project_relative_path(Path(":memory:")) == Path(":memory:")


def test_run_cycle_records_monitoring_quality_gate_without_missing_run_id(monkeypatch, test_db):
    supervisor = AutomationSupervisor()
    run_id = supervisor._start_run("pytest_cycle")

    def fake_run_once(self, limit=30):
        return {"run_id": run_id, "status": "completed", "summary": {"status": "completed"}}

    class FakeLearningService:
        def latest_report(self):
            return None

    class FakeMonitoringService:
        def run_once(self, limit=5):
            return {
                "session_id": 1,
                "quality_gates": [
                    {
                        "symbol": "SZ002081",
                        "quality_grade": "degrade",
                        "quality_source": "pytest",
                        "risk_blocked": [],
                        "suppress_actions": True,
                    }
                ],
                "quality_events_count": 1,
                "suppressed_by_quality_symbols": ["SZ002081"],
                "quality_next_action": "degrade_only",
            }

        def create_symbol_review(self, symbol, session_id=None):
            return {"symbol": symbol, "session_id": session_id}

    monkeypatch.setattr(AutomationSupervisor, "run_once", fake_run_once)
    monkeypatch.setattr("app.learning.service.LearningService", FakeLearningService)
    monkeypatch.setattr("app.monitoring.service.MonitoringService", FakeMonitoringService)

    result = supervisor.run_cycle(limit=1, monitor_limit=1, review_symbol="SZ002081")

    assert result["monitoring"]["quality_next_action"] == "degrade_only"
    assert "monitoring_error" not in result
    assert not [step for step in result["failed_steps"] if step.get("step_id") == "monitoring"]

    row = test_db.fetch_one(
        """
        SELECT event_type, symbol, payload_json
        FROM automation_events
        WHERE run_id = ? AND event_type = 'automation_monitoring_quality_gate'
        """,
        (run_id,),
    )
    assert row is not None
    assert row["symbol"] == "SZ002081"


def test_phase_guardrail_relaxation_plan_is_not_overridden():
    supervisor = AutomationSupervisor()
    relaxed = SimulationPlan(
        symbol="SZ301310",
        action="buy",
        allowed=True,
        tier=CandidateTier.watch,
        reference_price=46.75,
        quantity=100,
        position_ratio=0.023375,
        estimated_amount=4675.0,
        reasons=[
            "Simulation-only phase guardrail relaxation: distribution-like phase risk is downgraded to a 100-share learning probe after main-force markup confirmation."
        ],
        live_trading_enabled=False,
    )
    hard_blocked = SimulationPlan(
        symbol="SZ301310",
        action="observe",
        allowed=False,
        tier=CandidateTier.watch,
        reference_price=46.75,
        quantity=0,
        position_ratio=0,
        estimated_amount=0,
        reasons=["Phase similarity guardrail triggered."],
        blocked_reason="phase_guardrail",
        live_trading_enabled=False,
    )

    assert supervisor._plan_relaxes_phase_guardrail(relaxed) is True
    assert supervisor._plan_relaxes_phase_guardrail(hard_blocked) is False


def test_plan_snapshot_freshness_rechecks_actual_candidate_trade_date():
    snapshot = MarketSnapshot(
        symbol="SH600000",
        trade_date=date(2026, 7, 9),
        price=12.0,
        metadata={"data_quality": "daily_bar"},
    )
    sessions = [date(2026, 7, 9), date(2026, 7, 10)]

    after_close = AutomationSupervisor._snapshot_freshness(
        snapshot,
        now=datetime(2026, 7, 10, 16, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        trading_dates=sessions,
    )
    before_close = AutomationSupervisor._snapshot_freshness(
        snapshot,
        now=datetime(2026, 7, 10, 14, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        trading_dates=sessions,
    )

    assert after_close["allowed"] is False
    assert after_close["trading_session_age"] == 1
    assert before_close["allowed"] is True
