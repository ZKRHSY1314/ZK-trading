from datetime import date, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class CandidateTier(str, Enum):
    strong = "strong"
    watch = "watch"
    rejected = "rejected"


class TradeSide(str, Enum):
    buy = "buy"
    sell = "sell"


class MarketSnapshot(BaseModel):
    symbol: str
    name: str | None = None
    trade_date: date | None = None
    price: float
    pct_change: float | None = None
    high: float | None = None
    low: float | None = None
    open: float | None = None
    close: float | None = None
    volume: float | None = None
    amount: float | None = None
    pb: float | None = None
    market_cap_billion: float | None = None
    historical_high: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RuleHit(BaseModel):
    rule_id: str
    name: str
    group: str
    passed: bool
    score_delta: float = 0
    hard_block: bool = False
    reason: str


class CandidateDecision(BaseModel):
    symbol: str
    name: str | None = None
    score: float
    tier: CandidateTier
    blocked: bool
    hits: list[RuleHit]


class KnowledgeContext(BaseModel):
    principles: list[dict[str, Any]] = Field(default_factory=list)
    related_strategies: list[dict[str, Any]] = Field(default_factory=list)
    related_cases: list[dict[str, Any]] = Field(default_factory=list)
    stock_profiles: list[dict[str, Any]] = Field(default_factory=list)
    trade_records: list[dict[str, Any]] = Field(default_factory=list)
    user_notes: list[dict[str, Any]] = Field(default_factory=list)


class Explanation(BaseModel):
    signal_summary: str
    matched_rules: list[str] = Field(default_factory=list)
    risk_blockers: list[str] = Field(default_factory=list)
    data_quality: str
    similar_cases: list[dict[str, Any]] = Field(default_factory=list)
    uncertainty_notes: list[str] = Field(default_factory=list)
    simulation_disclaimer: str = "This is a simulation review based on historical data. Not investment advice."



class DecisionAnalysis(BaseModel):
    snapshot: MarketSnapshot
    decision: CandidateDecision
    knowledge: KnowledgeContext
    risk_notes: list[str] = Field(default_factory=list)
    suggested_next_actions: list[str] = Field(default_factory=list)
    explanation: Explanation | None = None


class SimulationOrder(BaseModel):
    symbol: str
    side: TradeSide
    quantity: int
    price: float
    requested_at: datetime = Field(default_factory=datetime.now)


class SimulationFill(BaseModel):
    order: SimulationOrder
    filled_quantity: int
    fill_price: float
    fee: float
    stamp_tax: float
    filled_at: datetime = Field(default_factory=datetime.now)


class SimulationPositionView(BaseModel):
    symbol: str
    name: str | None = None
    quantity: int
    sellable_quantity: int
    avg_cost: float


class SimulationAccountView(BaseModel):
    account_id: int
    name: str
    cash: float
    initial_cash: float
    positions: list[SimulationPositionView] = Field(default_factory=list)


class SimulationPlan(BaseModel):
    symbol: str
    name: str | None = None
    action: str
    allowed: bool
    tier: CandidateTier
    reference_price: float
    quantity: int
    position_ratio: float
    estimated_amount: float
    stop_loss: float | None = None
    target_price: float | None = None
    reasons: list[str] = Field(default_factory=list)
    risk_notes: list[str] = Field(default_factory=list)
    live_trading_enabled: bool = False


class AutomationEventInput(BaseModel):
    event_type: str
    symbol: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class AutomationFinishInput(BaseModel):
    status: str = "completed"
    summary: dict[str, Any] = Field(default_factory=dict)


class LearningSample(BaseModel):
    id: str
    source_type: str
    source_id: str
    symbol: str | None = None
    name: str | None = None
    label: str
    outcome_score: float = 0
    entry_price: float | None = None
    exit_price: float | None = None
    return_pct: float | None = None
    risk_level: str | None = None
    rating: str | None = None
    features: dict[str, Any] = Field(default_factory=dict)
    lessons: list[str] = Field(default_factory=list)


class LearningBacktestResult(BaseModel):
    id: int | None = None
    strategy_name: str
    sample_count: int
    win_rate: float
    avg_return: float
    profit_loss_ratio: float
    max_drawdown: float
    blocked_success_count: int
    false_positive_count: int
    pending_count: int
    summary: dict[str, Any] = Field(default_factory=dict)


class LearningReport(BaseModel):
    id: int | None = None
    automation_run_id: int | None = None
    report_type: str = "daily"
    title: str
    summary: dict[str, Any] = Field(default_factory=dict)
    created_at: str | None = None


class AgentTaskInput(BaseModel):
    task_type: str
    requested_by: str = "codex"
    payload: dict[str, Any] = Field(default_factory=dict)


class AgentControlEvent(BaseModel):
    id: int | None = None
    task_id: int
    event_type: str
    message: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str | None = None


class AgentControlTask(BaseModel):
    id: int | None = None
    task_type: str
    status: str
    requested_by: str
    payload: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    approval_status: str = "auto_approved"
    approved_by: str | None = None
    approved_at: str | None = None
    rejected_by: str | None = None
    rejected_at: str | None = None
    approval_note: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    completed_at: str | None = None
    events: list[AgentControlEvent] = Field(default_factory=list)


class ApprovalInput(BaseModel):
    user: str = "admin"
    note: str | None = None


class AgentLearningSample(BaseModel):
    id: int | None = None
    source_task_id: int
    sample_type: str
    symbol: str | None = None
    name: str | None = None
    features: dict[str, Any] = Field(default_factory=dict)
    decision: dict[str, Any] = Field(default_factory=dict)
    risk_flags: list[str] = Field(default_factory=list)
    label: str | None = None
    label_source: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class AgentLearningSummary(BaseModel):
    total_count: int = 0
    by_sample_type: dict[str, int] = Field(default_factory=dict)
    by_label: dict[str, int] = Field(default_factory=dict)


class AgentLearningOutcome(BaseModel):
    id: int | None = None
    sample_id: int
    symbol: str | None = None
    horizon_days: int
    start_date: str | None = None
    end_date: str | None = None
    start_price: float | None = None
    end_price: float | None = None
    max_return_pct: float | None = None
    min_return_pct: float | None = None
    close_return_pct: float | None = None
    outcome_label: str
    risk_outcome: str
    metrics: dict[str, Any] = Field(default_factory=dict)
    created_at: str | None = None
    updated_at: str | None = None


class AgentOutcomeSummary(BaseModel):
    coverage_count: int = 0
    pending_count: int = 0
    by_sample_type: dict[str, dict[str, Any]] = Field(default_factory=dict)
    by_label: dict[str, int] = Field(default_factory=dict)


class CalibrationProposal(BaseModel):
    id: int | None = None
    proposal_type: str
    target: str
    status: str = "pending"
    evidence: dict[str, Any] = Field(default_factory=dict)
    proposal: dict[str, Any] = Field(default_factory=dict)
    created_by: str | None = None
    reviewed_by: str | None = None
    review_note: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    reviewed_at: str | None = None


class CalibrationReviewInput(BaseModel):
    user: str = "admin"
    note: str | None = None


class SandboxExperiment(BaseModel):
    id: int | None = None
    proposal_id: int
    status: str = "pending"
    baseline_metrics: dict[str, Any] = Field(default_factory=dict)
    proposed_metrics: dict[str, Any] = Field(default_factory=dict)
    comparison: dict[str, Any] = Field(default_factory=dict)
    conclusion: str | None = None
    created_by: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    completed_at: str | None = None


class SimulationPolicy(BaseModel):
    id: int | None = None
    source_experiment_id: int
    policy_type: str
    status: str = "draft"
    policy_json: dict[str, Any] = Field(default_factory=dict)
    risk_limits_json: dict[str, Any] = Field(default_factory=dict)
    created_by: str | None = None
    reviewed_by: str | None = None
    review_note: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    reviewed_at: str | None = None


class PaperSimulationRun(BaseModel):
    id: int | None = None
    policy_id: int
    status: str = "pending"
    started_at: str | None = None
    completed_at: str | None = None
    metrics_json: dict[str, Any] = Field(default_factory=dict)
    created_by: str | None = None
    created_at: str | None = None


class PaperSimulationAction(BaseModel):
    id: int | None = None
    run_id: int
    symbol: str
    action_type: str
    reason_json: dict[str, Any] = Field(default_factory=dict)
    simulated_price: float | None = None
    simulated_quantity: int | None = None
    risk_flags_json: list[str] = Field(default_factory=list)
    created_at: str | None = None


class SimulationPolicyReviewInput(BaseModel):
    user: str = "admin"
    note: str | None = None


class PaperSimulationEvaluation(BaseModel):
    id: int | None = None
    run_id: int
    action_id: int
    policy_id: int
    symbol: str
    horizon_days: int
    status: str
    entry_price: float | None = None
    future_price: float | None = None
    max_return_pct: float | None = None
    min_return_pct: float | None = None
    close_return_pct: float | None = None
    outcome_label: str | None = None
    risk_outcome: str | None = None
    metrics_json: dict[str, Any] = Field(default_factory=dict)
    created_at: str | None = None
    updated_at: str | None = None


class PriceReadinessReport(BaseModel):
    id: int | None = None
    symbol: str
    name: str | None = None
    source: str
    latest_price: float | None = None
    latest_price_at: str | None = None
    coverage_status: str
    history_points: int = 0
    error_message: str | None = None
    metrics_json: dict[str, Any] = Field(default_factory=dict)
    created_at: str | None = None
    updated_at: str | None = None


class DailyBarCache(BaseModel):
    id: int | None = None
    symbol: str
    trade_date: str
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    volume: float | None = None
    amount: float | None = None
    source: str
    quality_status: str
    created_at: str | None = None
    updated_at: str | None = None


