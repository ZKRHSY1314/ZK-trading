from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.agent_control.service import AgentControlService
from app.ai.weight_optimizer import WeightOptimizer
from app.automation.supervisor import AutomationSupervisor
from app.candidates.auto_discovery import AutoDiscoveryScanner
from app.candidates.lifecycle import CandidateLifecycleService
from app.candidates.local_scanner import LocalCandidateScanner
from app.candidates.offhour_search import OffhourPotentialSearchService
from app.candidates.scoring import CandidateScoringService
from app.config import settings
from app.data.snapshot_builder import MarketDataError, MarketSnapshotBuilder
from app.decision import DecisionAnalyzer
from app.experience.code_evolution import CodeEvolutionService
from app.experience.memory import ExperienceMemoryService
from app.knowledge.repository import KnowledgeRepository
from app.learning.phase_matcher import PhaseSimilarityService
from app.learning.phase_replay import MainForcePhaseReplayService, PhaseReplayError
from app.learning.service import LearningService
from app.models import (
    CandidateDecision,
    DecisionAnalysis,
    LearningBacktestResult,
    LearningReport,
    LearningSample,
    MarketSnapshot,
    SimulationAccountView,
    AutomationEventInput,
    AutomationFinishInput,
    SimulationFill,
    SimulationOrder,
    SimulationPlan,
    AgentControlTask,
    AgentTaskInput,
    ApprovalInput,
    CalibrationReviewInput,
)
from app.monitoring.service import MonitoringService
from app.rules.engine import RuleEngine
from app.rules.loader import load_rule_config
from app.simulation.broker import SimulatedBroker
from app.simulation.planner import SimulationPlanner
from app.storage.sqlite_store import SQLiteStore

router = APIRouter(prefix="/api")


class CodeEvolutionValidationInput(BaseModel):
    validation: dict = Field(default_factory=dict)
    status: str | None = None


class CodeEvolutionReviewInput(BaseModel):
    reviewed_by: str = "user"
    note: str | None = None


@router.get("/system/capabilities")
def capabilities() -> dict[str, object]:
    return {
        "market_data": ["akshare"],
        "storage": "sqlite",
        "live_trading": "disabled",
        "ai_models": ["openai_placeholder", "qwen_placeholder", "local_placeholder"],
    }


@router.get("/automation/capabilities")
def automation_capabilities() -> dict:
    return AutomationSupervisor().capabilities()


@router.post("/automation/run-once")
def automation_run_once(limit: int = 30) -> dict:
    return AutomationSupervisor().run_once(limit)


@router.post("/automation/cycles/run-once")
def automation_cycle_run_once(
    limit: int = 5,
    monitor_limit: int = 5,
    review_symbol: str = "SZ002081",
) -> dict:
    return AutomationSupervisor().run_cycle(
        limit=limit,
        monitor_limit=monitor_limit,
        review_symbol=review_symbol,
    )


@router.get("/automation/latest")
def automation_latest() -> dict:
    latest = AutomationSupervisor().latest_run()
    if latest is None:
        raise HTTPException(status_code=404, detail="尚未产生自动化运行记录")
    return latest


@router.get("/automation/runs")
def automation_runs(limit: int = 20) -> list[dict]:
    return AutomationSupervisor().list_runs(limit)


@router.get("/automation/runs/{run_id}")
def automation_run_detail(run_id: int) -> dict:
    run = AutomationSupervisor().get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="自动化运行不存在")
    return run


@router.post("/automation/runs/start")
def automation_start_external_run(mode: str = "browser_control") -> dict:
    normalized_mode = mode.strip().lower()
    blocked_terms = ("live", "broker", "credential", "password", "order")
    if any(term in normalized_mode for term in blocked_terms):
        raise HTTPException(
            status_code=400,
            detail="External live trading, broker, credential, and order-control modes are blocked.",
        )
    return AutomationSupervisor().start_external_run(mode)


@router.post("/automation/runs/{run_id}/events")
def automation_record_event(run_id: int, event: AutomationEventInput) -> dict:
    try:
        return AutomationSupervisor().record_external_event(
            run_id,
            event.event_type,
            event.symbol,
            event.payload,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/automation/runs/{run_id}/finish")
def automation_finish_external_run(run_id: int, finish: AutomationFinishInput) -> dict:
    try:
        return AutomationSupervisor().finish_external_run(
            run_id,
            finish.status,
            finish.summary,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/knowledge/summary")
def knowledge_summary() -> dict[str, int]:
    store = SQLiteStore(settings.database_path)
    store.init()
    return store.table_counts()


@router.get("/knowledge/principles")
def list_principles() -> list[dict]:
    store = SQLiteStore(settings.database_path)
    return KnowledgeRepository(store).list_principles()


@router.get("/knowledge/strategies")
def list_strategies(category: str | None = None) -> list[dict]:
    store = SQLiteStore(settings.database_path)
    return KnowledgeRepository(store).list_strategies(category)


@router.get("/knowledge/cases")
def search_cases(keyword: str | None = None, case_type: str | None = None) -> list[dict]:
    store = SQLiteStore(settings.database_path)
    if keyword or case_type:
        return KnowledgeRepository(store).search_cases([keyword] if keyword else [], case_type)
    return store.fetch_all(
        """
        SELECT id, case_type, trade_date, stock_text, operation, result, lesson
        FROM trade_cases
        ORDER BY id
        """
    )


@router.get("/knowledge/stocks")
def search_stocks(keyword: str | None = None, limit: int = 50) -> list[dict]:
    store = SQLiteStore(settings.database_path)
    limit = max(1, min(limit, 200))
    if keyword:
        like = f"%{keyword}%"
        return store.fetch_all(
            """
            SELECT symbol, name, current_price, operation_cost_line, sell_target,
                   risk_level, pb, score, rating, dataset_name, source_file
            FROM stock_profiles
            WHERE symbol LIKE ? OR name LIKE ?
            ORDER BY score DESC
            LIMIT ?
            """,
            (like, like, limit),
        )
    return store.fetch_all(
        """
        SELECT symbol, name, current_price, operation_cost_line, sell_target,
               risk_level, pb, score, rating, dataset_name, source_file
        FROM stock_profiles
        ORDER BY score DESC
        LIMIT ?
        """,
        (limit,),
    )


@router.get("/knowledge/user-notes")
def search_user_notes(keyword: str | None = None) -> list[dict]:
    store = SQLiteStore(settings.database_path)
    repository = KnowledgeRepository(store)
    if keyword:
        return repository.search_user_notes([keyword])
    return store.fetch_all(
        """
        SELECT id, symbol, name, note_type, priority, content, tags_json
        FROM user_stock_notes
        ORDER BY priority DESC, id
        """
    )


@router.get("/knowledge/main-force-patterns")
def list_main_force_patterns(symbol: str | None = None, limit: int = 50) -> list[dict]:
    store = SQLiteStore(settings.database_path)
    return KnowledgeRepository(store).list_main_force_patterns(symbol=symbol, limit=limit)


@router.get("/learning/summary")
def learning_summary() -> dict:
    service = LearningService()
    return {
        "sample_counts": service.sample_counts_by_label(),
        "main_force_patterns": service.main_force_pattern_summary(),
        "latest_report": service.latest_report().model_dump(mode="json")
        if service.latest_report()
        else None,
    }


@router.post("/learning/rebuild-samples")
def rebuild_learning_samples() -> dict:
    return LearningService().rebuild_samples()


@router.get("/learning/samples", response_model=list[LearningSample])
def learning_samples(
    label: str | None = None,
    symbol: str | None = None,
    limit: int = 100,
) -> list[LearningSample]:
    return LearningService().list_samples(label=label, symbol=symbol, limit=limit)


@router.post("/learning/backtest", response_model=LearningBacktestResult)
def run_learning_backtest(strategy_name: str = "local_rule_v1") -> LearningBacktestResult:
    return LearningService().run_backtest(strategy_name)


@router.post("/learning/reports/daily", response_model=LearningReport)
def create_learning_report(automation_run_id: int | None = None) -> LearningReport:
    return LearningService().generate_review_report(automation_run_id=automation_run_id)


@router.post("/experience/capture")
def capture_experience_events(limit: int = 300) -> dict:
    return ExperienceMemoryService().capture_recent_events(limit=limit)


@router.post("/experience/reviews/daily")
def create_experience_daily_review(review_date: str | None = None) -> dict:
    return ExperienceMemoryService().create_daily_review(review_date=review_date)


@router.get("/experience/summary")
def experience_summary() -> dict:
    return ExperienceMemoryService().summary()


@router.get("/experience/events")
def experience_events(
    category: str | None = None,
    symbol: str | None = None,
    limit: int = 100,
) -> list[dict]:
    return ExperienceMemoryService().events(category=category, symbol=symbol, limit=limit)


@router.get("/experience/reviews")
def experience_reviews(limit: int = 20) -> list[dict]:
    return ExperienceMemoryService().latest_reviews(limit=limit)


@router.get("/experience/strategy-performance")
def experience_strategy_performance(limit: int = 20) -> list[dict]:
    return ExperienceMemoryService().strategy_performance(limit=limit)


@router.post("/experience/code-evolution/generate")
def generate_code_evolution_reviews(limit: int = 5) -> dict:
    return CodeEvolutionService().generate_review_items(limit=limit)


@router.get("/experience/code-evolution")
def experience_code_evolution(status: str | None = None, limit: int = 20) -> list[dict]:
    return CodeEvolutionService().list_records(status=status, limit=limit)


@router.get("/experience/code-evolution/{record_id}")
def experience_code_evolution_detail(record_id: int) -> dict:
    try:
        return CodeEvolutionService().get_record(record_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/experience/code-evolution/{record_id}/validation")
def record_code_evolution_validation(
    record_id: int,
    input_data: CodeEvolutionValidationInput,
) -> dict:
    try:
        return CodeEvolutionService().record_validation(
            record_id,
            input_data.validation,
            status=input_data.status,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/experience/code-evolution/{record_id}/approve")
def approve_code_evolution_record(record_id: int, input_data: CodeEvolutionReviewInput) -> dict:
    try:
        return CodeEvolutionService().approve(
            record_id,
            reviewed_by=input_data.reviewed_by,
            note=input_data.note,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/experience/code-evolution/{record_id}/reject")
def reject_code_evolution_record(record_id: int, input_data: CodeEvolutionReviewInput) -> dict:
    try:
        return CodeEvolutionService().reject(
            record_id,
            reviewed_by=input_data.reviewed_by,
            note=input_data.note,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/learning/reports/latest", response_model=LearningReport)
def latest_learning_report() -> LearningReport:
    report = LearningService().latest_report()
    if report is None:
        raise HTTPException(status_code=404, detail="尚未生成学习复盘报告")
    return report


@router.post("/learning/phase-replays/core-samples")
def create_core_phase_replays(lookback_years: float = 3) -> dict:
    return MainForcePhaseReplayService().create_core_sample_replays(lookback_years=lookback_years)


@router.post("/learning/phase-replays/{symbol}")
def create_phase_replay(
    symbol: str,
    name: str | None = None,
    lookback_years: float = 3,
) -> dict:
    try:
        return MainForcePhaseReplayService().create_replay(
            symbol=symbol,
            name=name,
            lookback_years=lookback_years,
        )
    except PhaseReplayError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/learning/phase-replays")
def list_phase_replays(symbol: str | None = None, limit: int = 20) -> list[dict]:
    return MainForcePhaseReplayService().latest_replays(symbol=symbol, limit=limit)


@router.get("/learning/phase-replays/{replay_id}")
def get_phase_replay(replay_id: int) -> dict:
    replay = MainForcePhaseReplayService().get_replay(replay_id)
    if replay is None:
        raise HTTPException(status_code=404, detail="阶段回放不存在")
    return replay


@router.post("/learning/phase-matches/{symbol}")
def create_phase_match(
    symbol: str,
    name: str | None = None,
    lookback_years: float = 3,
) -> dict:
    try:
        return PhaseSimilarityService().create_match(
            symbol=symbol,
            name=name,
            lookback_years=lookback_years,
        )
    except PhaseReplayError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/learning/phase-matches")
def list_phase_matches(symbol: str | None = None, limit: int = 20) -> list[dict]:
    return PhaseSimilarityService().latest_matches(symbol=symbol, limit=limit)


@router.get("/learning/phase-matches/{match_id}")
def get_phase_match(match_id: int) -> dict:
    match = PhaseSimilarityService().get_match(match_id)
    if match is None:
        raise HTTPException(status_code=404, detail="阶段匹配不存在")
    return match


@router.post("/monitoring/sessions")
def start_monitoring_session(limit: int = 5, name: str = "intraday_watch") -> dict:
    return MonitoringService().start_session(limit=limit, name=name)


@router.get("/monitoring/sessions/latest")
def latest_monitoring_session() -> dict:
    session = MonitoringService().latest_session()
    if session is None:
        return {
            "status": "empty",
            "summary": None,
            "events": [],
            "alerts": [],
            "message": "尚未创建监控会话",
        }
    return session


@router.get("/monitoring/sessions/{session_id}")
def monitoring_session(session_id: int) -> dict:
    session = MonitoringService().get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="监控会话不存在")
    return session


@router.post("/monitoring/run-once")
def monitoring_run_once(session_id: int | None = None, limit: int = 5) -> dict:
    return MonitoringService().run_once(session_id=session_id, limit=limit)


@router.get("/monitoring/events")
def monitoring_events(
    session_id: int | None = None,
    symbol: str | None = None,
    limit: int = 100,
) -> list[dict]:
    return MonitoringService().list_events(session_id=session_id, symbol=symbol, limit=limit)


@router.get("/monitoring/alerts")
def monitoring_alerts(
    session_id: int | None = None,
    symbol: str | None = None,
    severity: str | None = None,
    limit: int = 100,
) -> list[dict]:
    return MonitoringService().list_alerts(
        session_id=session_id,
        symbol=symbol,
        severity=severity,
        limit=limit,
    )


@router.post("/monitoring/alerts/{alert_id}/action")
def monitoring_alert_action(
    alert_id: int,
    action_type: str,
    note: str | None = None,
    created_by: str = "user",
) -> dict:
    try:
        return MonitoringService().record_alert_action(
            alert_id=alert_id,
            action_type=action_type,
            note=note,
            created_by=created_by,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/monitoring/lifecycle")
def monitoring_lifecycle(symbol: str | None = None, limit: int = 100) -> dict:
    return MonitoringService().alert_lifecycle(symbol=symbol, limit=limit)


@router.get("/monitoring/replay/{symbol}")
def monitoring_replay(symbol: str, session_id: int | None = None, limit: int = 100) -> dict:
    return MonitoringService().replay_symbol(symbol=symbol, session_id=session_id, limit=limit)


@router.post("/monitoring/reviews/{symbol}")
def create_monitoring_review(symbol: str, session_id: int | None = None, limit: int = 100) -> dict:
    return MonitoringService().create_symbol_review(
        symbol=symbol,
        session_id=session_id,
        limit=limit,
    )


@router.get("/monitoring/reviews")
def monitoring_reviews(limit: int = 20) -> list[dict]:
    return MonitoringService().latest_reviews(limit=limit)


@router.get("/monitoring/summary")
def monitoring_summary() -> dict:
    return MonitoringService().summary()


@router.get("/market/snapshot/{symbol}", response_model=MarketSnapshot)
def market_snapshot(symbol: str, name: str | None = None) -> MarketSnapshot:
    try:
        return MarketSnapshotBuilder().build(symbol, name)
    except (ValueError, MarketDataError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/realtime/capabilities")
def realtime_capabilities() -> dict:
    from app.realtime.service import RealtimeMarketService

    return RealtimeMarketService().capabilities()


@router.get("/realtime/provider-health")
def realtime_provider_health() -> list[dict]:
    from app.realtime.service import RealtimeMarketService

    return RealtimeMarketService().provider_health()


@router.get("/realtime/snapshot/{symbol}")
def realtime_snapshot(symbol: str) -> dict:
    from app.realtime.service import RealtimeMarketService

    return RealtimeMarketService().latest_snapshot(symbol)


@router.get("/realtime/events")
def realtime_events(symbol: str | None = None, limit: int = 50) -> list[dict]:
    from app.realtime.service import RealtimeMarketService

    return RealtimeMarketService().list_events(symbol=symbol, limit=limit)


@router.post("/realtime/refresh")
def realtime_refresh(symbols: str = "SZ002081,SZ002115", limit: int = 20) -> dict:
    from app.realtime.service import RealtimeMarketService

    symbol_list = [symbol.strip() for symbol in symbols.split(",") if symbol.strip()]
    return RealtimeMarketService().refresh_symbols(symbols=symbol_list, limit=limit)


@router.post("/realtime/monitoring-sync")
def realtime_monitoring_sync(limit: int = 100) -> dict:
    from app.realtime.monitoring_bridge import RealtimeMonitoringBridge

    return RealtimeMonitoringBridge().sync(limit=limit)


@router.post("/realtime/cycle")
def realtime_cycle(
    symbols: str = "SZ002081,SZ002115",
    refresh_limit: int = 20,
    sync_limit: int = 100,
    replay_limit: int = 100,
) -> dict:
    from app.realtime.service import RealtimeMarketService

    symbol_list = [symbol.strip() for symbol in symbols.split(",") if symbol.strip()]
    return RealtimeMarketService().run_cycle(
        symbols=symbol_list,
        refresh_limit=refresh_limit,
        sync_limit=sync_limit,
        replay_limit=replay_limit,
    )


@router.post("/realtime/replay")
def realtime_replay(symbol: str | None = None, limit: int = 100) -> dict:
    from app.realtime.service import RealtimeMarketService

    return RealtimeMarketService().replay(symbol=symbol, limit=limit)


@router.post("/data/daily-bars/refresh")
def refresh_daily_bars(limit: int = 50, days: int = 120) -> dict:
    from app.data.daily_bar_cache import DailyBarCacheService
    return DailyBarCacheService().refresh_bars(limit=limit, days=days)


@router.get("/data/daily-bars/coverage")
def get_daily_bar_coverage(limit: int = 100) -> list[dict]:
    from app.data.daily_bar_cache import DailyBarCacheService
    return DailyBarCacheService().get_coverage(limit=limit)


@router.get("/data/daily-bars/{symbol}")
def get_daily_bars_for_symbol(symbol: str, limit: int = 120) -> list[dict]:
    from app.data.daily_bar_cache import DailyBarCacheService
    return DailyBarCacheService().get_bars(symbol=symbol, limit=limit)


@router.post("/candidates/evaluate", response_model=CandidateDecision)
def evaluate_candidate(snapshot: MarketSnapshot) -> CandidateDecision:
    engine = RuleEngine(load_rule_config())
    return engine.evaluate(snapshot)


@router.get("/candidates/local-scan")
def local_candidate_scan(limit: int = 100, persist: bool = True) -> dict:
    return LocalCandidateScanner().scan(limit, persist)


@router.post("/candidates/auto-discovery")
def auto_discover_candidates(limit: int = 50, persist: bool = True) -> dict:
    return AutoDiscoveryScanner().scan(limit=limit, persist=persist)


@router.get("/candidates/auto-discovery/latest")
def latest_auto_discovered_candidates(limit: int = 50) -> list[dict]:
    return AutoDiscoveryScanner().latest(limit=limit)


@router.get("/candidates/lifecycle")
def candidate_lifecycle(state: str | None = None, limit: int = 100) -> list[dict]:
    return CandidateLifecycleService().list_current(state=state, limit=limit)


@router.get("/candidates/lifecycle/summary")
def candidate_lifecycle_summary() -> dict:
    return CandidateLifecycleService().summary()


@router.get("/candidates/lifecycle/events")
def candidate_lifecycle_events(symbol: str | None = None, limit: int = 100) -> list[dict]:
    return CandidateLifecycleService().events(symbol=symbol, limit=limit)


@router.post("/candidates/scores/rebuild")
def rebuild_candidate_scores(limit: int = 200, persist: bool = True) -> dict:
    return CandidateScoringService().score_from_lifecycle(limit=limit, persist=persist)


@router.get("/candidates/scores")
def candidate_scores(limit: int = 50, state: str | None = None) -> list[dict]:
    return CandidateScoringService().latest_scores(limit=limit, state=state)


@router.get("/candidates/scores/summary")
def candidate_score_summary(limit: int = 10) -> dict:
    return CandidateScoringService().summary(limit=limit)


@router.post("/candidates/potential-search/run")
def run_potential_search(limit: int = 100, persist: bool = True) -> dict:
    return OffhourPotentialSearchService().run(limit=limit, persist=persist)


@router.get("/candidates/potential-search/latest")
def latest_potential_search() -> dict:
    latest = OffhourPotentialSearchService().latest_run()
    if latest is None:
        return {
            "status": "empty",
            "total_scanned": 0,
            "stored_count": 0,
            "scored_count": 0,
            "items": [],
            "errors": [],
            "message": "尚未产生潜力搜索记录",
        }
    return latest


@router.get("/candidates/potential-search/runs")
def list_potential_search_runs(limit: int = 20) -> list[dict]:
    return OffhourPotentialSearchService().list_runs(limit=limit)


@router.get("/candidates/latest")
def latest_candidate_scan() -> dict:
    latest = LocalCandidateScanner().latest_scan()
    if latest is None:
        raise HTTPException(status_code=404, detail="尚未产生候选池扫描结果")
    return latest


@router.post("/decision/analyze", response_model=DecisionAnalysis)
def analyze_decision(snapshot: MarketSnapshot) -> DecisionAnalysis:
    analyzer = DecisionAnalyzer()
    return analyzer.analyze(snapshot)


@router.get("/decision/analyze-symbol/{symbol}", response_model=DecisionAnalysis)
def analyze_symbol(symbol: str, name: str | None = None) -> DecisionAnalysis:
    try:
        snapshot = MarketSnapshotBuilder().build(symbol, name)
    except (ValueError, MarketDataError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return DecisionAnalyzer().analyze(snapshot)


@router.post("/simulation/orders", response_model=SimulationFill)
def create_simulation_order(order: SimulationOrder) -> SimulationFill:
    broker = SimulatedBroker()
    try:
        return broker.execute(order)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/simulation/account", response_model=SimulationAccountView)
def simulation_account() -> SimulationAccountView:
    return SimulatedBroker().account()


@router.post("/simulation/settle", response_model=SimulationAccountView)
def settle_simulation_account() -> SimulationAccountView:
    return SimulatedBroker().settle_next_day()


@router.get("/simulation/fills")
def simulation_fills(limit: int = 50) -> list[dict]:
    return SimulatedBroker().fills(limit)


@router.post("/simulation/plan", response_model=SimulationPlan)
def create_simulation_plan(snapshot: MarketSnapshot) -> SimulationPlan:
    return SimulationPlanner().create_plan(snapshot)


@router.get("/simulation/plan/{symbol}", response_model=SimulationPlan)
def create_symbol_simulation_plan(symbol: str, name: str | None = None) -> SimulationPlan:
    try:
        snapshot = MarketSnapshotBuilder().build(symbol, name)
    except (ValueError, MarketDataError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return SimulationPlanner().create_plan(snapshot)


@router.post("/ai/weights/propose")
def propose_weight_update(metrics_before: dict[str, float], metrics_after: dict[str, float]) -> dict:
    optimizer = WeightOptimizer()
    return optimizer.validate_candidate_update(metrics_before, metrics_after)


@router.get("/agent-control/capabilities")
def agent_control_capabilities() -> dict:
    return AgentControlService().capabilities()


@router.post("/agent-control/tasks", response_model=AgentControlTask)
def create_agent_control_task(task: AgentTaskInput) -> AgentControlTask:
    try:
        return AgentControlService().create_task(task)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/agent-control/tasks", response_model=list[AgentControlTask])
def list_agent_control_tasks(limit: int = 50) -> list[AgentControlTask]:
    return AgentControlService().list_tasks(limit)


@router.get("/agent-control/tasks/{task_id}", response_model=AgentControlTask)
def get_agent_control_task(task_id: int) -> AgentControlTask:
    task = AgentControlService().get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.post("/agent-control/tasks/{task_id}/approve", response_model=AgentControlTask)
def approve_agent_control_task(task_id: int, input_data: ApprovalInput) -> AgentControlTask:
    try:
        return AgentControlService().approve_task(task_id, input_data.user, input_data.note)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/agent-control/tasks/{task_id}/reject", response_model=AgentControlTask)
def reject_agent_control_task(task_id: int, input_data: ApprovalInput) -> AgentControlTask:
    try:
        return AgentControlService().reject_task(task_id, input_data.user, input_data.note)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/agent-control/audit")
def list_agent_control_audit(limit: int = 50) -> list[dict]:
    return [e.model_dump(mode="json") for e in AgentControlService().list_audit_events(limit)]


@router.post("/agent-control/tasks/{task_id}/run", response_model=AgentControlTask)
def run_agent_control_task(task_id: int) -> AgentControlTask:
    try:
        return AgentControlService().execute_task(task_id)
    except ValueError as exc:
        status_code = 404 if "not found" in str(exc).lower() else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/agent-control/tasks/run-now", response_model=AgentControlTask)
def run_agent_control_task_now(task_type: str, requested_by: str = "codex") -> AgentControlTask:
    service = AgentControlService()
    try:
        task = service.create_task(AgentTaskInput(task_type=task_type, requested_by=requested_by))
        if task.status != "blocked" and task.approval_status != "pending":
            task = service.execute_task(task.id)
        return task
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# ------------------------------------------------------------------
# Agent Learning Samples (observation-to-learning dataset)
# ------------------------------------------------------------------

@router.post("/learning/agent-samples/from-task/{task_id}")
def create_agent_learning_from_task(task_id: int) -> dict:
    from app.agent_control.learning_extraction import AgentLearningExtractionService
    return AgentLearningExtractionService().extract_from_task(task_id)


@router.post("/learning/agent-samples/from-recent")
def create_agent_learning_from_recent(limit: int = 20) -> dict:
    from app.agent_control.learning_extraction import AgentLearningExtractionService
    return AgentLearningExtractionService().extract_from_recent(limit=limit)


@router.get("/learning/agent-samples")
def list_agent_learning_samples(
    sample_type: str | None = None,
    symbol: str | None = None,
    label: str | None = None,
    limit: int = 50,
) -> list[dict]:
    from app.agent_control.learning_extraction import AgentLearningExtractionService
    samples = AgentLearningExtractionService().list_samples(
        sample_type=sample_type,
        symbol=symbol,
        label=label,
        limit=limit,
    )
    return [s.model_dump(mode="json") for s in samples]


@router.get("/learning/agent-samples/summary")
def agent_learning_summary() -> dict:
    from app.agent_control.learning_extraction import AgentLearningExtractionService
    return AgentLearningExtractionService().summary().model_dump(mode="json")


# ------------------------------------------------------------------
# Agent Learning Outcomes
# ------------------------------------------------------------------

@router.post("/learning/agent-outcomes/label-sample/{sample_id}")
def label_agent_outcome(sample_id: int, horizon_days: int = 5) -> dict:
    from app.agent_control.outcome_labeling import OutcomeLabelingService
    return OutcomeLabelingService().label_sample(sample_id, horizon_days)


@router.post("/learning/agent-outcomes/label-recent")
def label_recent_agent_outcomes(limit: int = 50, horizon_days: int = 5) -> dict:
    from app.agent_control.outcome_labeling import OutcomeLabelingService
    return OutcomeLabelingService().label_recent(limit, horizon_days)


@router.get("/learning/agent-outcomes")
def list_agent_outcomes(limit: int = 50) -> list[dict]:
    from app.agent_control.outcome_labeling import OutcomeLabelingService
    outcomes = OutcomeLabelingService().list_outcomes(limit)
    return [o.model_dump(mode="json") for o in outcomes]


@router.get("/learning/agent-outcomes/summary")
def agent_outcomes_summary() -> dict:
    from app.agent_control.outcome_labeling import OutcomeLabelingService
    return OutcomeLabelingService().summary().model_dump(mode="json")


# ------------------------------------------------------------------
# Signal Performance & Calibration Proposals (review-only)
# ------------------------------------------------------------------

@router.get("/learning/signal-performance/summary")
def signal_performance_summary() -> dict:
    from app.agent_control.signal_performance import SignalPerformanceService
    return SignalPerformanceService().performance_summary()


@router.post("/learning/calibration-proposals/generate")
def generate_calibration_proposals(created_by: str = "system") -> dict:
    from app.agent_control.signal_performance import SignalPerformanceService
    return SignalPerformanceService().generate_proposals(created_by=created_by)


@router.get("/learning/calibration-proposals")
def list_calibration_proposals(
    status: str | None = None,
    limit: int = 50,
) -> list[dict]:
    from app.agent_control.signal_performance import SignalPerformanceService
    proposals = SignalPerformanceService().list_proposals(status=status, limit=limit)
    return [p.model_dump(mode="json") for p in proposals]


@router.post("/learning/calibration-proposals/{proposal_id}/approve")
def approve_calibration_proposal(proposal_id: int, input_data: CalibrationReviewInput) -> dict:
    from app.agent_control.signal_performance import SignalPerformanceService
    try:
        proposal = SignalPerformanceService().approve_proposal(
            proposal_id, reviewed_by=input_data.user, review_note=input_data.note
        )
        return proposal.model_dump(mode="json")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/learning/calibration-proposals/{proposal_id}/reject")
def reject_calibration_proposal(proposal_id: int, input_data: CalibrationReviewInput) -> dict:
    from app.agent_control.signal_performance import SignalPerformanceService
    try:
        proposal = SignalPerformanceService().reject_proposal(
            proposal_id, reviewed_by=input_data.user, review_note=input_data.note
        )
        return proposal.model_dump(mode="json")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# ------------------------------------------------------------------
# Sandbox Experiments (approved proposals → what-if simulation)
# ------------------------------------------------------------------

@router.post("/learning/sandbox-experiments/run/{proposal_id}")
def run_sandbox_experiment(proposal_id: int, created_by: str = "system") -> dict:
    from app.agent_control.sandbox_experiments import SandboxExperimentService
    try:
        return SandboxExperimentService().run_experiment(
            proposal_id, created_by=created_by
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/learning/sandbox-experiments/run-approved")
def run_approved_sandbox_experiments(limit: int = 20, created_by: str = "system") -> dict:
    from app.agent_control.sandbox_experiments import SandboxExperimentService
    return SandboxExperimentService().run_approved(limit=limit, created_by=created_by)


@router.get("/learning/sandbox-experiments")
def list_sandbox_experiments(limit: int = 50) -> list[dict]:
    from app.agent_control.sandbox_experiments import SandboxExperimentService
    return SandboxExperimentService().list_experiments(limit=limit)


@router.get("/learning/sandbox-experiments/summary")
def sandbox_experiments_summary() -> dict:
    from app.agent_control.sandbox_experiments import SandboxExperimentService
    return SandboxExperimentService().summary()


# ------------------------------------------------------------------
# Paper Simulation Policies & Runs (simulation-only)
# ------------------------------------------------------------------

@router.post("/learning/simulation-policies/draft-from-experiments")
def draft_simulation_policies(limit: int = 20, created_by: str = "system") -> dict:
    from app.agent_control.paper_simulation import PaperSimulationService
    return PaperSimulationService().draft_policies_from_experiments(
        limit=limit, created_by=created_by
    )


@router.get("/learning/simulation-policies")
def list_simulation_policies(status: str | None = None, limit: int = 50) -> list[dict]:
    from app.agent_control.paper_simulation import PaperSimulationService
    return PaperSimulationService().list_policies(status=status, limit=limit)


@router.post("/learning/simulation-policies/{policy_id}/approve")
def approve_simulation_policy(policy_id: int, input_data: CalibrationReviewInput) -> dict:
    from app.agent_control.paper_simulation import PaperSimulationService
    try:
        return PaperSimulationService().approve_policy(
            policy_id, reviewed_by=input_data.user, review_note=input_data.note
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/learning/simulation-policies/{policy_id}/reject")
def reject_simulation_policy(policy_id: int, input_data: CalibrationReviewInput) -> dict:
    from app.agent_control.paper_simulation import PaperSimulationService
    try:
        return PaperSimulationService().reject_policy(
            policy_id, reviewed_by=input_data.user, review_note=input_data.note
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/learning/paper-simulations/run/{policy_id}")
def run_paper_simulation(policy_id: int, created_by: str = "system") -> dict:
    from app.agent_control.paper_simulation import PaperSimulationService
    try:
        return PaperSimulationService().run_simulation(
            policy_id, created_by=created_by
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/learning/paper-simulations/run-approved")
def run_approved_paper_simulations(limit: int = 20, created_by: str = "system") -> dict:
    from app.agent_control.paper_simulation import PaperSimulationService
    return PaperSimulationService().run_approved_policies(
        limit=limit, created_by=created_by
    )


@router.get("/learning/paper-simulations")
def list_paper_simulations(limit: int = 50) -> list[dict]:
    from app.agent_control.paper_simulation import PaperSimulationService
    return PaperSimulationService().list_runs(limit=limit)


@router.get("/learning/paper-simulations/summary")
def paper_simulations_summary() -> dict:
    from app.agent_control.paper_simulation import PaperSimulationService
    return PaperSimulationService().summary()


# ------------------------------------------------------------------
# Paper Simulation Evaluation
# ------------------------------------------------------------------

@router.post("/learning/paper-simulation-evaluations/evaluate-recent")
def evaluate_recent_paper_simulations(limit: int = 100, horizon_days: int = 5) -> dict:
    from app.agent_control.paper_simulation_evaluation import PaperSimulationEvaluationService
    return PaperSimulationEvaluationService().evaluate_recent(limit=limit, horizon_days=horizon_days)

@router.post("/learning/paper-simulation-evaluations/evaluate-run/{run_id}")
def evaluate_run_paper_simulations(run_id: int, horizon_days: int = 5) -> dict:
    from app.agent_control.paper_simulation_evaluation import PaperSimulationEvaluationService
    return PaperSimulationEvaluationService().evaluate_run(run_id=run_id, horizon_days=horizon_days)

@router.get("/learning/paper-simulation-evaluations")
def list_paper_simulation_evaluations(limit: int = 100) -> list[dict]:
    from app.agent_control.paper_simulation_evaluation import PaperSimulationEvaluationService
    return PaperSimulationEvaluationService().list_evaluations(limit=limit)

@router.get("/learning/paper-simulation-evaluations/summary")
def paper_simulation_evaluations_summary() -> dict:
    from app.agent_control.paper_simulation_evaluation import PaperSimulationEvaluationService
    return PaperSimulationEvaluationService().summary()

@router.get("/learning/paper-simulation-evaluations/policies")
def paper_simulation_evaluations_policies() -> list[dict]:
    from app.agent_control.paper_simulation_evaluation import PaperSimulationEvaluationService
    return PaperSimulationEvaluationService().policy_summary()


# ------------------------------------------------------------------
# Price Readiness
# ------------------------------------------------------------------

@router.post("/data/price-readiness/run")
def run_price_readiness(limit: int = 100) -> dict:
    from app.data.price_readiness import PriceReadinessService
    return PriceReadinessService().run_readiness_check(limit=limit)

@router.get("/data/price-readiness/latest")
def latest_price_readiness(limit: int = 100) -> list[dict]:
    from app.data.price_readiness import PriceReadinessService
    return PriceReadinessService().get_latest_reports(limit=limit)

@router.get("/data/price-readiness/summary")
def summary_price_readiness() -> dict:
    from app.data.price_readiness import PriceReadinessService
    return PriceReadinessService().get_summary()


# ------------------------------------------------------------------
# Market Regime and Portfolio Risk
# ------------------------------------------------------------------


@router.get("/market-regime/latest")
def latest_market_regime(as_of_date: str | None = None) -> dict:
    from app.market_regime.service import MarketRegimeService

    return MarketRegimeService().get_latest_regime(as_of_date=as_of_date)


@router.post("/market-regime/refresh")
def refresh_market_regime(as_of_date: str | None = None) -> dict:
    from app.market_regime.service import MarketRegimeService

    return MarketRegimeService().refresh(as_of_date=as_of_date)


@router.get("/risk/portfolio-state")
def portfolio_risk_state() -> dict:
    from app.risk.portfolio import PortfolioRiskService

    return PortfolioRiskService().state()


# ------------------------------------------------------------------
# Event-Driven Historical Backtesting
# ------------------------------------------------------------------

class BacktestRunInput(BaseModel):
    start_date: str
    end_date: str
    symbols: list[str] = Field(default_factory=list)
    initial_cash: float = 100_000.0
    max_positions: int = 5
    per_symbol_cap: float = 0.2
    benchmark_symbol: str = "SH000300"


@router.post("/backtest/runs")
def run_historical_backtest(input_data: BacktestRunInput) -> dict:
    from app.backtest.engine import BacktestEngine

    return BacktestEngine().run(
        start_date=input_data.start_date,
        end_date=input_data.end_date,
        symbols=input_data.symbols,
        initial_cash=input_data.initial_cash,
        max_positions=input_data.max_positions,
        per_symbol_cap=input_data.per_symbol_cap,
        benchmark_symbol=input_data.benchmark_symbol,
    )


@router.get("/backtest/runs")
def list_backtest_runs(limit: int = 20) -> list[dict]:
    import json

    limit = max(1, min(limit, 100))
    rows = SQLiteStore(settings.database_path).fetch_all(
        "SELECT * FROM historical_backtest_runs ORDER BY id DESC LIMIT ?",
        (limit,),
    )
    results = []
    for row in rows:
        item = dict(row)
        item["metrics"] = json.loads(item.pop("metrics_json") or "{}")
        item["benchmark"] = json.loads(item.pop("benchmark_json", "{}") or "{}")
        item["execution_warnings"] = json.loads(item.pop("execution_warnings_json", "[]") or "[]")
        results.append(item)
    return results


@router.get("/backtest/runs/{run_id}")
def get_backtest_run(run_id: int) -> dict:
    import json

    store = SQLiteStore(settings.database_path)
    run = store.fetch_one("SELECT * FROM historical_backtest_runs WHERE id = ?", (run_id,))
    if not run:
        raise HTTPException(status_code=404, detail="Backtest run not found")
    trades = store.fetch_all(
        "SELECT * FROM historical_backtest_trades WHERE run_id = ? ORDER BY trade_date ASC, id ASC",
        (run_id,),
    )
    equity = store.fetch_all(
        "SELECT * FROM historical_backtest_daily_equity WHERE run_id = ? ORDER BY trade_date ASC",
        (run_id,),
    )
    closed_trades = store.fetch_all(
        "SELECT * FROM historical_backtest_closed_trades WHERE run_id = ? ORDER BY exit_date ASC, id ASC",
        (run_id,),
    )
    run_dict = dict(run)
    run_dict["metrics"] = json.loads(run_dict.pop("metrics_json") or "{}")
    benchmark = json.loads(run_dict.pop("benchmark_json", "{}") or "{}")
    execution_warnings = json.loads(run_dict.pop("execution_warnings_json", "[]") or "[]")
    return {
        "run": run_dict,
        "trades": [dict(row) for row in trades],
        "closed_trades": [dict(row) for row in closed_trades],
        "daily_equity": [dict(row) for row in equity],
        "benchmark": benchmark,
        "execution_warnings": execution_warnings,
    }


# ------------------------------------------------------------------
# AI Review and Proposals
# ------------------------------------------------------------------


@router.get("/ai/model/capabilities")
def ai_model_capabilities() -> dict:
    from app.ai.model_service import AIModelGatewayService

    return AIModelGatewayService().capabilities()


@router.post("/ai/model/explain-code-evolution/{record_id}")
def explain_code_evolution_with_model(record_id: int) -> dict:
    from app.ai.model_service import AIModelGatewayService

    try:
        return AIModelGatewayService().explain_code_evolution(record_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/ai/model/audit-logs")
def ai_model_audit_logs(operation: str | None = None, limit: int = 50) -> list[dict]:
    from app.ai.model_service import AIModelGatewayService

    return AIModelGatewayService().audit_logs(operation=operation, limit=limit)


@router.post("/ai/review/run")
def run_ai_review() -> dict:
    from app.ai.review_worker import AIReviewWorker

    return AIReviewWorker().generate_review()


@router.get("/ai/review/proposals")
def list_ai_proposals(limit: int = 20) -> list[dict]:
    from app.ai.review_worker import AIReviewWorker

    return AIReviewWorker().list_proposals(limit=limit)


@router.post("/ai/review/proposals/{proposal_id}/validate")
def validate_ai_proposal(proposal_id: int) -> dict:
    from app.ai.review_worker import AIReviewWorker

    try:
        return AIReviewWorker().validate_proposal(proposal_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/ai/review/proposals/{proposal_id}/approve-for-simulation")
def approve_ai_proposal_for_simulation(
    proposal_id: int,
    reviewed_by: str = "user",
    note: str | None = None,
) -> dict:
    from app.ai.review_worker import AIReviewWorker

    try:
        return AIReviewWorker().approve_for_simulation(
            proposal_id,
            reviewed_by=reviewed_by,
            note=note,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/ai/review/proposals/{proposal_id}/reject")
def reject_ai_proposal(
    proposal_id: int,
    reviewed_by: str = "user",
    note: str | None = None,
) -> dict:
    from app.ai.review_worker import AIReviewWorker

    try:
        return AIReviewWorker().reject(proposal_id, reviewed_by=reviewed_by, note=note)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
