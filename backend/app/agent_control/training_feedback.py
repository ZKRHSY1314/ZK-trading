"""Stable review-only interface for one training-feedback pass.

The module intentionally stops at evidence aggregation. It extracts completed
agent tasks, labels samples whose future bars are available, and returns a
performance snapshot. It never mutates scoring rules or activates a model.
"""

from typing import Any

from app.agent_control.learning_extraction import AgentLearningExtractionService
from app.agent_control.outcome_labeling import OutcomeLabelingService
from app.agent_control.signal_performance import SignalPerformanceService
from app.config import settings
from app.storage.sqlite_store import SQLiteStore


MIN_RESOLVED_MARKET_SAMPLES = 10
RESOLVED_MARKET_LABELS = {
    "strong_follow_through",
    "mild_follow_through",
    "failed_signal",
    "flat_or_noise",
}


class TrainingFeedbackModule:
    """Small control-plane facade for the observation-to-outcome loop."""

    def __init__(self, store: SQLiteStore | None = None) -> None:
        self.store = store or SQLiteStore(settings.database_path)
        self.store.init()
        self.extraction = AgentLearningExtractionService(store=self.store)
        self.outcomes = OutcomeLabelingService(store=self.store)
        self.performance = SignalPerformanceService(store=self.store)

    def run(self, limit: int = 50, horizon_days: int = 5) -> dict[str, Any]:
        safe_limit = max(1, min(int(limit), 200))
        safe_horizon = max(1, min(int(horizon_days), 60))
        extraction = self.extraction.extract_from_recent(limit=safe_limit)
        labeling = self.outcomes.label_recent(
            limit=safe_limit,
            horizon_days=safe_horizon,
        )
        result = self.snapshot(horizon_days=safe_horizon)
        result.update(
            {
                "schema_version": "training_feedback_run.v1",
                "limit": safe_limit,
                "horizon_days": safe_horizon,
                "steps": {
                    "extract_recent": extraction,
                    "label_recent_with_maturity_guard": labeling,
                    "performance_snapshot": result["performance"],
                },
            }
        )
        return result

    def snapshot(self, horizon_days: int = 5) -> dict[str, Any]:
        safe_horizon = max(1, min(int(horizon_days), 60))
        sample_summary = self.extraction.summary().model_dump(mode="json")
        outcome_summary = self.outcomes.summary().model_dump(mode="json")
        performance = self.performance.performance_summary(horizon_days=safe_horizon)
        placeholders = ",".join("?" for _ in RESOLVED_MARKET_LABELS)
        resolved_row = self.store.fetch_one(
            f"""
            SELECT COUNT(DISTINCT sample_id) AS count
            FROM agent_learning_outcomes
            WHERE horizon_days = ? AND outcome_label IN ({placeholders})
            """,
            (safe_horizon, *tuple(sorted(RESOLVED_MARKET_LABELS))),
        )
        resolved_market_count = int((resolved_row or {}).get("count") or 0)
        horizon_row = self.store.fetch_one(
            """
            SELECT
                COUNT(*) AS outcome_count,
                SUM(CASE WHEN outcome_label = 'pending_future_data' THEN 1 ELSE 0 END) AS pending_count
            FROM agent_learning_outcomes
            WHERE horizon_days = ?
            """,
            (safe_horizon,),
        )
        blocked_reasons: list[str] = []
        if resolved_market_count < MIN_RESOLVED_MARKET_SAMPLES:
            blocked_reasons.append("insufficient_resolved_market_samples")
        if settings.enable_live_trading:
            blocked_reasons.append("live_trading_enabled")
        return {
            "schema_version": "training_feedback_snapshot.v1",
            "status": "ready" if not blocked_reasons else "insufficient_samples",
            "feedback_ready": not blocked_reasons,
            "horizon_days": safe_horizon,
            "sample_count": int(sample_summary.get("total_count") or 0),
            "outcome_count": int((horizon_row or {}).get("outcome_count") or 0),
            "pending_outcome_count": int((horizon_row or {}).get("pending_count") or 0),
            "all_horizon_outcome_count": int(outcome_summary.get("coverage_count") or 0),
            "resolved_market_sample_count": resolved_market_count,
            "minimum_resolved_market_samples": MIN_RESOLVED_MARKET_SAMPLES,
            "blocked_reasons": blocked_reasons,
            "samples": sample_summary,
            "outcomes": outcome_summary,
            "performance": performance,
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
            "scoring_rules_mutated": False,
            "model_activated": False,
        }
