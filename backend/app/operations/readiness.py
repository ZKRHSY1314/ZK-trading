from __future__ import annotations

from datetime import date, datetime
import json
from pathlib import Path
from typing import Any

from app.automation.supervisor import AutomationSupervisor
from app.candidates.selection_v2 import StrategySelectionV2Service
from app.config import settings
from app.diagnostics.stability import V1StabilityDiagnosticsService
from app.public_opinion.service import CodexPublicOpinionService
from app.storage.sqlite_store import SQLiteStore


class OperationReadinessService:
    """Unified, review-only readiness report for controlled operation."""

    def __init__(self, store: SQLiteStore | None = None) -> None:
        self.store = store or SQLiteStore(settings.database_path)
        self.store.init()

    def report(self, *, selection_limit: int = 80) -> dict[str, Any]:
        safe_selection_limit = max(1, min(int(selection_limit), 300))
        runtime = self._runtime_readiness()
        automation = self._automation_training_readiness()
        judgment = self._judgment_readiness(selection_limit=safe_selection_limit)
        public_opinion = self._public_opinion_readiness()

        requirements = {
            "runtime_operation": runtime,
            "automation_training": automation,
            "judgment_efficiency_accuracy": judgment,
            "codex_public_opinion": public_opinion,
        }
        blocking = [
            key
            for key, value in requirements.items()
            if value.get("status") in {"blocked", "missing"}
        ]
        attention = [
            key
            for key, value in requirements.items()
            if value.get("status") in {"needs_attention", "partial"}
        ]

        if settings.enable_live_trading:
            status = "blocked_live_trading_enabled"
            next_action = "disable_live_trading_before_any_operation"
        elif blocking:
            status = "blocked"
            next_action = f"resolve_blocking_requirements: {', '.join(blocking)}"
        elif attention:
            status = "needs_attention"
            next_action = f"continue_review_only_stabilization: {', '.join(attention)}"
        else:
            status = "ready_for_controlled_review_run"
            next_action = "run_scheduled_review_only_cycles_and_collect_training_outcomes"

        return {
            "schema_version": "operation_readiness.v1",
            "status": status,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
            "requirements": requirements,
            "blocking_requirements": blocking,
            "attention_requirements": attention,
            "next_action": next_action,
            "safety": {
                "allow_live_order": False,
                "execution_allowed": False,
                "broker_api_enabled": False,
                "credential_storage_enabled": False,
                "screen_click_trading_enabled": False,
            },
        }

    def _runtime_readiness(self) -> dict[str, Any]:
        db_path = Path(settings.database_path)
        db_exists = db_path.exists() or str(settings.database_path) == ":memory:"
        key_tables = {
            table: self._table_count(table)
            for table in [
                "automation_runs",
                "potential_search_runs",
                "candidate_scores",
                "daily_bar_cache",
                "offhour_research_runs",
                "public_opinion_runs",
            ]
        }
        daily = self.store.fetch_one(
            """
            SELECT COUNT(*) AS row_count,
                   COUNT(DISTINCT symbol) AS symbol_count,
                   MAX(trade_date) AS latest_trade_date
            FROM daily_bar_cache
            WHERE trade_date != 'ERROR'
            """
        ) or {}
        latest_trade_date = daily.get("latest_trade_date")
        lag_days = self._calendar_lag_days(latest_trade_date)
        blockers: list[str] = []
        warnings: list[str] = []
        if settings.enable_live_trading:
            blockers.append("live_trading_enabled")
        if not db_exists:
            blockers.append("database_missing")
        if key_tables.get("daily_bar_cache", 0) == 0:
            blockers.append("daily_bar_cache_empty")
        if lag_days is not None and lag_days > 10:
            warnings.append("daily_bar_cache_stale")
        if key_tables.get("candidate_scores", 0) == 0 and key_tables.get("potential_search_runs", 0) == 0:
            warnings.append("candidate_evidence_missing")

        status = "blocked" if blockers else ("needs_attention" if warnings else "ready")
        return {
            "status": status,
            "blockers": blockers,
            "warnings": warnings,
            "evidence": {
                "database_path": str(db_path),
                "database_exists": db_exists,
                "key_table_counts": key_tables,
                "daily_bar_cache": {
                    "row_count": int(daily.get("row_count") or 0),
                    "symbol_count": int(daily.get("symbol_count") or 0),
                    "latest_trade_date": latest_trade_date,
                    "calendar_lag_days": lag_days,
                },
                "health_contract": {
                    "expected_live_trading_enabled": False,
                    "actual_live_trading_enabled": settings.enable_live_trading,
                },
            },
            "next_action": (
                "restore_database_and_daily_bar_cache"
                if blockers
                else "refresh_daily_bar_cache_then_recheck"
                if warnings
                else "runtime_ready_for_review_only_cycles"
            ),
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _automation_training_readiness(self) -> dict[str, Any]:
        capabilities = AutomationSupervisor().capabilities()
        latest_run = self._latest_automation_run()
        counts = {
            table: self._table_count(table)
            for table in [
                "automation_runs",
                "automation_events",
                "agent_control_tasks",
                "agent_learning_samples",
                "agent_learning_outcomes",
                "learning_samples",
                "learning_reports",
                "dataset2_staging_records",
                "sim_cockpit_actions",
                "sim_cockpit_readbacks",
            ]
        }
        training_evidence_count = (
            counts["agent_learning_samples"]
            + counts["agent_learning_outcomes"]
            + counts["learning_samples"]
            + counts["dataset2_staging_records"]
            + counts["sim_cockpit_actions"]
            + counts["sim_cockpit_readbacks"]
        )
        supported_steps = set(capabilities.get("supported_steps") or [])
        missing_steps = sorted(
            {
                "offhour_research_loop",
                "dataset2_training_run_in_memory",
                "sim_cockpit_supervised_cycle",
                "public_opinion_capture",
            }
            - supported_steps
        )
        blockers: list[str] = []
        warnings: list[str] = []
        if settings.enable_live_trading:
            blockers.append("live_trading_enabled")
        if missing_steps:
            blockers.append("automation_capabilities_missing")
        if training_evidence_count == 0:
            warnings.append("no_training_evidence_samples")
        if not latest_run:
            warnings.append("no_automation_run_history")
        elif latest_run.get("status") not in {"completed", "partial"}:
            warnings.append(f"latest_automation_status_{latest_run.get('status')}")

        status = "blocked" if blockers else ("needs_attention" if warnings else "ready")
        return {
            "status": status,
            "blockers": blockers,
            "warnings": warnings,
            "evidence": {
                "automation_mode": capabilities.get("mode"),
                "supported_steps_present": sorted(supported_steps),
                "missing_required_steps": missing_steps,
                "latest_automation_run": latest_run,
                "table_counts": counts,
                "training_evidence_count": training_evidence_count,
            },
            "next_action": (
                "restore_required_automation_capabilities"
                if blockers
                else "run_sim_cockpit_supervised_cycle_or_dataset2_training_run_to_collect_samples"
                if warnings
                else "continue_scheduled_training_cycles"
            ),
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _judgment_readiness(self, *, selection_limit: int) -> dict[str, Any]:
        try:
            selection = StrategySelectionV2Service(store=self.store).run(
                mode="balanced",
                limit=selection_limit,
                write_artifacts=False,
            )
            selection_error = None
        except Exception as exc:
            selection = {}
            selection_error = str(exc)

        try:
            stability = V1StabilityDiagnosticsService(store=self.store).report()
        except Exception as exc:
            stability = {"status": "unavailable", "error": str(exc)}
        strategy_safety_review = stability.get("strategy_safety_review") or {}
        latest_backtest = self._latest_backtest()
        summary = selection.get("summary") or {}
        filter_diagnostics = selection.get("filter_diagnostics") or {}
        top_blocking_reasons = filter_diagnostics.get("top_blocking_reasons") or []
        top_reason_counts = {
            str(item.get("reason")): int(item.get("count") or 0)
            for item in top_blocking_reasons
        }
        candidate_count = int(summary.get("candidate_count") or 0)
        data_gap_count = int(summary.get("data_gap_count") or 0)
        invalid_data_count = top_reason_counts.get("HF004_INVALID_DATA", 0)
        active_candidate_count = int(
            filter_diagnostics.get("active_candidate_count") or candidate_count
        )
        potential_search = stability.get("latest_potential_search") or {}
        degraded_discovery_accepted_by_selection = (
            active_candidate_count >= min(selection_limit, 20)
            and int(potential_search.get("scored_count") or 0) > 0
        )
        conservative_no_trade_accepted = (
            strategy_safety_review.get("status") == "accepted_conservative_no_trade_gate"
        )
        blockers: list[str] = []
        warnings: list[str] = []
        if selection_error:
            blockers.append("selection_v2_failed")
        if candidate_count == 0:
            warnings.append("no_selection_candidates")
        if not top_blocking_reasons:
            warnings.append("missing_filter_diagnostics")
        if candidate_count and invalid_data_count / candidate_count >= 0.3:
            warnings.append("selection_invalid_data_high")
        if candidate_count == 0 and data_gap_count:
            warnings.append("selection_data_gap_all_candidates")
        if not latest_backtest:
            warnings.append("no_historical_backtest")
        elif (
            (latest_backtest.get("metrics") or {}).get("trade_count", 0) == 0
            and not conservative_no_trade_accepted
        ):
            warnings.append("latest_backtest_zero_trades")
        judgment_related_v1_items = {
            "external_discovery_errors",
            "status_partial",
            "no_scored_candidates",
            "daily_bar_cache_empty",
            "daily_bar_cache_stale",
        }
        for item in stability.get("blocking_attention_items") or []:
            if (
                item in {"external_discovery_errors", "status_partial"}
                and degraded_discovery_accepted_by_selection
            ):
                continue
            if item in judgment_related_v1_items:
                warnings.append(f"v1_stability_{item}")

        status = "blocked" if blockers else ("needs_attention" if warnings else "ready")
        return {
            "status": status,
            "blockers": blockers,
            "warnings": warnings,
            "evidence": {
                "selection_status": selection.get("status"),
                "selection_summary": summary,
                "top_blocking_reasons": top_blocking_reasons,
                "invalid_data_count": invalid_data_count,
                "data_gap_count": data_gap_count,
                "active_candidate_count": active_candidate_count,
                "degraded_discovery_accepted_by_selection": degraded_discovery_accepted_by_selection,
                "latest_potential_search": potential_search,
                "public_opinion_context_status": (
                    selection.get("public_opinion_context") or {}
                ).get("status"),
                "latest_backtest": latest_backtest,
                "v1_stability_status": stability.get("status"),
                "v1_blocking_attention_items": stability.get("blocking_attention_items") or [],
                "strategy_safety_review_status": strategy_safety_review.get("status"),
                "conservative_no_trade_accepted": conservative_no_trade_accepted,
                "selection_error": selection_error,
            },
            "next_action": (
                "fix_selection_v2_before_operation"
                if blockers
                else "refresh_invalid_candidate_data_and_rerun_discovery_then_backtest"
                if warnings
                else "use_selection_v2_for_review_only_candidate_ranking"
            ),
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _public_opinion_readiness(self) -> dict[str, Any]:
        context = CodexPublicOpinionService(store=self.store).latest_context(limit=5)
        blockers: list[str] = []
        warnings: list[str] = []
        if settings.enable_live_trading:
            blockers.append("live_trading_enabled")
        if context.get("status") == "empty":
            warnings.append("no_public_opinion_run")
        if int(context.get("sector_count") or 0) == 0:
            warnings.append("no_sector_signals")
        top_sectors = list(context.get("top_sectors") or [])
        status = "blocked" if blockers else ("needs_attention" if warnings else "ready")
        return {
            "status": status,
            "blockers": blockers,
            "warnings": warnings,
            "evidence": {
                "latest_context_status": context.get("status"),
                "run_id": context.get("run_id"),
                "item_count": context.get("item_count", 0),
                "sector_count": context.get("sector_count", 0),
                "top_sectors": [
                    {
                        "sector": item.get("sector"),
                        "display_name": item.get("display_name"),
                        "heat_score": item.get("heat_score"),
                        "item_count": item.get("item_count"),
                        "suggested_action": item.get("suggested_action"),
                    }
                    for item in top_sectors[:5]
                ],
            },
            "next_action": (
                "rerun_public_opinion_capture"
                if warnings
                else "feed_sector_context_into_selection_v2_review"
            ),
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _latest_automation_run(self) -> dict[str, Any] | None:
        row = self.store.fetch_one(
            """
            SELECT id, mode, status, summary_json, created_at, completed_at
            FROM automation_runs
            ORDER BY id DESC
            LIMIT 1
            """
        )
        if not row:
            return None
        summary = self._json_loads(row.get("summary_json"), {})
        return {
            "id": row.get("id"),
            "mode": row.get("mode"),
            "status": row.get("status"),
            "summary_status": summary.get("status"),
            "created_at": row.get("created_at"),
            "completed_at": row.get("completed_at"),
        }

    def _latest_backtest(self) -> dict[str, Any] | None:
        row = self.store.fetch_one(
            """
            SELECT id, status, start_date, end_date, metrics_json, benchmark_json,
                   created_at, completed_at
            FROM historical_backtest_runs
            ORDER BY id DESC
            LIMIT 1
            """
        )
        if not row:
            return None
        return {
            "id": row.get("id"),
            "status": row.get("status"),
            "start_date": row.get("start_date"),
            "end_date": row.get("end_date"),
            "metrics": self._json_loads(row.get("metrics_json"), {}),
            "benchmark": self._json_loads(row.get("benchmark_json"), {}),
            "created_at": row.get("created_at"),
            "completed_at": row.get("completed_at"),
        }

    def _table_count(self, table: str) -> int:
        try:
            row = self.store.fetch_one(f"SELECT COUNT(*) AS count FROM {table}") or {}
        except Exception:
            return 0
        return int(row.get("count") or 0)

    @staticmethod
    def _json_loads(value: Any, default: Any) -> Any:
        if value in (None, ""):
            return default
        if isinstance(value, (dict, list)):
            return value
        try:
            return json.loads(str(value))
        except json.JSONDecodeError:
            return default

    @staticmethod
    def _calendar_lag_days(value: Any) -> int | None:
        if not value:
            return None
        try:
            parsed = date.fromisoformat(str(value)[:10])
        except ValueError:
            return None
        return (date.today() - parsed).days
