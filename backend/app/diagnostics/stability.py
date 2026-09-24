from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

from app.config import settings
from app.diagnostics.backtest import BacktestRiskDiagnosticsService
from app.diagnostics.data_freshness import DataFreshnessDiagnosticsService
from app.sim_cockpit.service import simulation_window_readiness
from app.storage.sqlite_store import SQLiteStore


V1_ACCEPTABLE_STRICT_HARD_BLOCKS = {"constitution_no_high_position"}
V1_STRATEGY_ATTENTION_ITEMS = {"zero_completed_trades", "candidates_rejected_by_risk"}


class V1StabilityDiagnosticsService:
    """Read-only V1 stabilization snapshot for smoke checks and release reviews."""

    def __init__(self, store: SQLiteStore | None = None) -> None:
        self.store = store or SQLiteStore(settings.database_path)

    def report(self) -> dict[str, Any]:
        data_coverage = self._data_coverage()
        potential_search = self._latest_potential_search()
        backtest = self._latest_backtest()
        strategy_safety_review = self._strategy_safety_review(backtest)
        sim_cockpit = self._sim_cockpit()
        offhour = self._latest_offhour()
        data_freshness = DataFreshnessDiagnosticsService(store=self.store).report()

        attention = self._attention_items(
            data_coverage=data_coverage,
            potential_search=potential_search,
            backtest=backtest,
            sim_cockpit=sim_cockpit,
        )
        accepted_attention = self._accepted_attention_items(
            attention_items=attention,
            strategy_safety_review=strategy_safety_review,
        )
        accepted_set = set(accepted_attention)
        blocking_attention = sorted(item for item in attention if item not in accepted_set)
        release_gate = self._release_gate(
            status="blocked_live_trading_enabled" if settings.enable_live_trading else (
                "needs_attention" if blocking_attention else "ready_for_v1_review"
            ),
            attention_items=attention,
            accepted_attention_items=accepted_attention,
            blocking_attention_items=blocking_attention,
            strategy_safety_review=strategy_safety_review,
            sim_cockpit=sim_cockpit,
        )
        status = "blocked_live_trading_enabled" if settings.enable_live_trading else (
            "needs_attention" if blocking_attention else "ready_for_v1_review"
        )

        return {
            "schema_version": "v1_stability_diagnostics.v1",
            "status": status,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
            "attention_items": attention,
            "accepted_attention_items": accepted_attention,
            "blocking_attention_items": blocking_attention,
            "release_gate": release_gate,
            "safety": {
                "live_trading_enabled": settings.enable_live_trading,
                "broker_api_enabled": False,
                "credential_storage_enabled": False,
                "real_order_execution_enabled": False,
            },
            "data_coverage": data_coverage,
            "data_freshness": data_freshness,
            "latest_potential_search": potential_search,
            "latest_backtest": backtest,
            "strategy_safety_review": strategy_safety_review,
            "latest_offhour_research": offhour,
            "sim_cockpit": sim_cockpit,
        }

    def _data_coverage(self) -> dict[str, Any]:
        summary = self.store.fetch_one(
            """
            SELECT
                COUNT(*) AS row_count,
                COUNT(DISTINCT symbol) AS symbol_count,
                MIN(trade_date) AS first_trade_date,
                MAX(trade_date) AS latest_trade_date,
                SUM(CASE WHEN quality_status = 'ready' THEN 1 ELSE 0 END) AS ready_rows
            FROM daily_bar_cache
            """
        ) or {}
        quality_rows = self.store.fetch_all(
            """
            SELECT quality_status, COUNT(*) AS row_count
            FROM daily_bar_cache
            GROUP BY quality_status
            ORDER BY row_count DESC, quality_status ASC
            """
        )
        benchmark_rows = self.store.fetch_all(
            """
            SELECT
                symbol,
                COUNT(*) AS row_count,
                MIN(trade_date) AS first_trade_date,
                MAX(trade_date) AS latest_trade_date,
                SUM(CASE WHEN quality_status = 'ready' THEN 1 ELSE 0 END) AS ready_rows
            FROM daily_bar_cache
            WHERE symbol IN ('SH000300', 'SH000001')
            GROUP BY symbol
            ORDER BY symbol ASC
            """
        )
        latest_trade_date = summary.get("latest_trade_date")
        lag_days = self._calendar_lag_days(latest_trade_date)
        row_count = int(summary.get("row_count") or 0)
        symbol_count = int(summary.get("symbol_count") or 0)
        status = "empty"
        if row_count:
            status = "stale" if lag_days is not None and lag_days > 7 else "ready"
        return {
            "status": status,
            "row_count": row_count,
            "symbol_count": symbol_count,
            "first_trade_date": summary.get("first_trade_date"),
            "latest_trade_date": latest_trade_date,
            "calendar_lag_days": lag_days,
            "ready_rows": int(summary.get("ready_rows") or 0),
            "quality_counts": [dict(row) for row in quality_rows],
            "benchmark_coverage": [dict(row) for row in benchmark_rows],
        }

    def _latest_potential_search(self) -> dict[str, Any]:
        row = self.store.fetch_one(
            "SELECT * FROM potential_search_runs ORDER BY id DESC LIMIT 1"
        )
        if not row:
            return {
                "status": "empty",
                "errors": [],
                "degraded": True,
                "diagnostic_reasons": ["no_potential_search_run"],
            }
        errors = self._json_loads(row.get("errors_json"), [])
        diagnostic_reasons: list[str] = []
        if row.get("status") != "completed":
            diagnostic_reasons.append(f"status_{row.get('status')}")
        if errors:
            diagnostic_reasons.append("external_discovery_errors")
        if int(row.get("scored_count") or 0) == 0:
            diagnostic_reasons.append("no_scored_candidates")
        return {
            "id": row.get("id"),
            "status": row.get("status"),
            "source": row.get("source"),
            "total_scanned": int(row.get("total_scanned") or 0),
            "stored_count": int(row.get("stored_count") or 0),
            "scored_count": int(row.get("scored_count") or 0),
            "errors": errors,
            "degraded": bool(diagnostic_reasons),
            "diagnostic_reasons": diagnostic_reasons,
            "created_at": row.get("created_at"),
            "completed_at": row.get("completed_at"),
        }

    def _latest_backtest(self) -> dict[str, Any]:
        row = self.store.fetch_one(
            "SELECT * FROM historical_backtest_runs ORDER BY id DESC LIMIT 1"
        )
        if not row:
            return {
                "status": "empty",
                "metrics": {"trade_count": 0},
                "diagnostic_reasons": ["no_backtest_run"],
            }
        metrics = self._json_loads(row.get("metrics_json"), {})
        benchmark = self._json_loads(row.get("benchmark_json"), {})
        warnings = self._json_loads(row.get("execution_warnings_json"), [])
        trade_count = int(metrics.get("trade_count") or 0)
        rejected_by_risk = int(metrics.get("rejected_by_risk_count") or 0)
        benchmark_symbol = row.get("benchmark_symbol") or settings.backtest_default_benchmark_symbol
        current_benchmark_coverage = self._benchmark_coverage_for_range(
            benchmark_symbol=benchmark_symbol,
            start_date=row.get("start_date"),
            end_date=row.get("end_date"),
        )
        symbols, symbol_source = self._latest_backtest_symbols()
        risk_rejection_diagnostics = self._risk_rejection_diagnostics(
            start_date=row.get("start_date"),
            end_date=row.get("end_date"),
            symbols=symbols,
            symbol_source=symbol_source,
            enabled=trade_count == 0 or rejected_by_risk > 0,
        )

        diagnostic_reasons: list[str] = []
        if row.get("status") != "completed":
            diagnostic_reasons.append(f"status_{row.get('status')}")
        if trade_count == 0:
            diagnostic_reasons.append("zero_completed_trades")
        if rejected_by_risk > 0:
            diagnostic_reasons.append("candidates_rejected_by_risk")
        persisted_benchmark_insufficient = (
            benchmark.get("status") == "insufficient_benchmark_data"
            or "insufficient_benchmark_data" in warnings
        )
        if persisted_benchmark_insufficient:
            if current_benchmark_coverage.get("status") == "ready":
                diagnostic_reasons.append("backtest_benchmark_rerun_required")
            else:
                diagnostic_reasons.append("insufficient_benchmark_data")

        return {
            "id": row.get("id"),
            "status": row.get("status"),
            "data_source": row.get("data_source"),
            "start_date": row.get("start_date"),
            "end_date": row.get("end_date"),
            "benchmark_symbol": benchmark_symbol,
            "metrics": metrics,
            "benchmark": benchmark,
            "current_benchmark_coverage": current_benchmark_coverage,
            "risk_rejection_diagnostics": risk_rejection_diagnostics,
            "execution_warnings": warnings,
            "diagnostic_reasons": diagnostic_reasons,
            "created_at": row.get("created_at"),
            "completed_at": row.get("completed_at"),
        }

    def _latest_backtest_symbols(self) -> tuple[list[str], str]:
        offhour = self.store.fetch_one(
            """
            SELECT id, backtest_json
            FROM offhour_research_runs
            ORDER BY id DESC
            LIMIT 1
            """
        )
        if offhour:
            payload = self._json_loads(offhour.get("backtest_json"), {})
            symbols = [str(symbol) for symbol in payload.get("symbols", []) if symbol]
            if symbols:
                return symbols, f"offhour_research_runs:{offhour.get('id')}"

        rows = self.store.fetch_all(
            """
            SELECT symbol, COUNT(*) AS count
            FROM historical_backtest_trades
            WHERE run_id = (SELECT id FROM historical_backtest_runs ORDER BY id DESC LIMIT 1)
            GROUP BY symbol
            ORDER BY count DESC, symbol ASC
            LIMIT 20
            """
        )
        symbols = [str(row["symbol"]) for row in rows if row.get("symbol")]
        if symbols:
            return symbols, "historical_backtest_trades:latest"

        rows = self.store.fetch_all(
            """
            SELECT symbol, COUNT(*) AS bar_count, MAX(trade_date) AS latest_trade_date
            FROM daily_bar_cache
            WHERE quality_status = 'ready'
              AND trade_date != 'ERROR'
              AND symbol NOT LIKE 'SH000%'
              AND symbol NOT LIKE 'SZ399%'
            GROUP BY symbol
            HAVING bar_count >= 3
            ORDER BY latest_trade_date DESC, bar_count DESC, symbol ASC
            LIMIT 10
            """
        )
        return [str(row["symbol"]) for row in rows if row.get("symbol")], "daily_bar_cache_fallback"

    def _risk_rejection_diagnostics(
        self,
        *,
        start_date: Any,
        end_date: Any,
        symbols: list[str],
        symbol_source: str,
        enabled: bool,
    ) -> dict[str, Any]:
        if not enabled:
            return {
                "status": "skipped",
                "reason": "backtest_has_completed_trades_and_no_risk_rejections",
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            }
        if not start_date or not end_date:
            return {
                "status": "skipped",
                "reason": "missing_backtest_date_range",
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            }
        try:
            return BacktestRiskDiagnosticsService(store=self.store).diagnose(
                start_date=str(start_date),
                end_date=str(end_date),
                symbols=symbols,
                symbol_source=symbol_source,
            )
        except Exception as exc:
            return {
                "status": "failed",
                "error": str(exc),
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            }

    def _benchmark_coverage_for_range(
        self,
        *,
        benchmark_symbol: str,
        start_date: Any,
        end_date: Any,
    ) -> dict[str, Any]:
        if not benchmark_symbol or not start_date or not end_date:
            return {
                "symbol": benchmark_symbol,
                "status": "unknown",
                "reason": "missing_benchmark_symbol_or_date_range",
            }
        symbols = sorted({benchmark_symbol, benchmark_symbol.upper(), benchmark_symbol.lower()})
        placeholders = ",".join("?" for _ in symbols)
        row = self.store.fetch_one(
            f"""
            SELECT
                COUNT(*) AS row_count,
                COUNT(DISTINCT trade_date) AS trade_date_count,
                MIN(trade_date) AS first_trade_date,
                MAX(trade_date) AS latest_trade_date,
                SUM(CASE WHEN close IS NOT NULL THEN 1 ELSE 0 END) AS close_count
            FROM daily_bar_cache
            WHERE symbol IN ({placeholders})
              AND quality_status = 'ready'
              AND trade_date >= ?
              AND trade_date <= ?
            """,
            tuple(symbols + [str(start_date), str(end_date)]),
        ) or {}
        close_count = int(row.get("close_count") or 0)
        status = "ready" if close_count >= 2 else "insufficient_benchmark_data"
        return {
            "symbol": benchmark_symbol,
            "status": status,
            "row_count": int(row.get("row_count") or 0),
            "trade_date_count": int(row.get("trade_date_count") or 0),
            "close_count": close_count,
            "first_trade_date": row.get("first_trade_date"),
            "latest_trade_date": row.get("latest_trade_date"),
        }

    def _latest_offhour(self) -> dict[str, Any]:
        row = self.store.fetch_one(
            """
            SELECT id, mode, status, summary_json, next_action, review_only,
                   simulation_only, live_trading_enabled, created_at, completed_at
            FROM offhour_research_runs
            ORDER BY id DESC
            LIMIT 1
            """
        )
        if not row:
            return {
                "status": "empty",
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            }
        summary = self._json_loads(row.get("summary_json"), {})
        return {
            "id": row.get("id"),
            "mode": row.get("mode"),
            "status": row.get("status"),
            "summary_status": summary.get("status"),
            "artifact_status": summary.get("artifact_status"),
            "signal_count": summary.get("signal_count"),
            "signal_backtest_trade_count": summary.get("signal_backtest_trade_count"),
            "signal_optimization_status": summary.get("signal_optimization_status"),
            "next_action": row.get("next_action") or summary.get("next_action"),
            "review_only": bool(row.get("review_only")),
            "simulation_only": bool(row.get("simulation_only")),
            "live_trading_enabled": bool(row.get("live_trading_enabled")),
            "created_at": row.get("created_at"),
            "completed_at": row.get("completed_at"),
        }

    def _sim_cockpit(self) -> dict[str, Any]:
        verification = self.store.fetch_one(
            """
            SELECT id, status, blocked_reasons_json, verified_by, confidence,
                   simulation_mode_detected, real_trading_blocked,
                   live_trading_enabled, raw_payload_json, created_at
            FROM sim_cockpit_window_verifications
            ORDER BY id DESC
            LIMIT 1
            """
        )
        action_count = self._table_count("sim_cockpit_actions")
        readback_count = self._table_count("sim_cockpit_readbacks")
        fill_count = self._table_count("simulation_fills")
        position_count = self._table_count("simulation_positions")
        if not verification:
            readiness = simulation_window_readiness(
                None,
                live_trading_enabled=settings.enable_live_trading,
            )
            return {
                "status": readiness["status"],
                "simulation_actions_allowed": False,
                "blocked_reasons": readiness["blocked_reasons"],
                "verification_freshness": readiness["freshness"],
                "action_count": action_count,
                "readback_count": readback_count,
                "simulation_fill_count": fill_count,
                "simulation_position_count": position_count,
                "live_trading_enabled": settings.enable_live_trading,
            }
        blocked_reasons = self._json_loads(verification.get("blocked_reasons_json"), [])
        readiness = simulation_window_readiness(
            {
                **verification,
                "blocked_reasons": blocked_reasons,
                "raw_payload": self._json_loads(verification.get("raw_payload_json"), {}),
                "simulation_mode_detected": bool(verification.get("simulation_mode_detected")),
                "real_trading_blocked": bool(verification.get("real_trading_blocked")),
                "live_trading_enabled": bool(verification.get("live_trading_enabled")),
            },
            live_trading_enabled=settings.enable_live_trading,
        )
        verified = bool(readiness["ready"])
        return {
            "latest_verification_id": verification.get("id"),
            "status": readiness["status"],
            "simulation_actions_allowed": verified,
            "blocked_reasons": readiness["blocked_reasons"],
            "verification_freshness": readiness["freshness"],
            "verified_by": verification.get("verified_by"),
            "confidence": verification.get("confidence"),
            "simulation_mode_detected": bool(verification.get("simulation_mode_detected")),
            "real_trading_blocked": bool(verification.get("real_trading_blocked")),
            "action_count": action_count,
            "readback_count": readback_count,
            "simulation_fill_count": fill_count,
            "simulation_position_count": position_count,
            "live_trading_enabled": settings.enable_live_trading,
            "created_at": verification.get("created_at"),
        }

    def _attention_items(
        self,
        *,
        data_coverage: dict[str, Any],
        potential_search: dict[str, Any],
        backtest: dict[str, Any],
        sim_cockpit: dict[str, Any],
    ) -> list[str]:
        items: list[str] = []
        if settings.enable_live_trading:
            items.append("live_trading_enabled")
        if data_coverage.get("status") in {"empty", "stale"}:
            items.append(f"daily_bar_cache_{data_coverage.get('status')}")
        if potential_search.get("degraded"):
            items.extend(str(item) for item in potential_search.get("diagnostic_reasons", []))
        items.extend(str(item) for item in backtest.get("diagnostic_reasons", []))
        if sim_cockpit.get("status") != "verified":
            items.append("sim_cockpit_not_verified")
        return sorted(set(items))

    def _strategy_safety_review(self, backtest: dict[str, Any]) -> dict[str, Any]:
        metrics = backtest.get("metrics") or {}
        risk = backtest.get("risk_rejection_diagnostics") or {}
        hard_blocks = risk.get("hard_block_summary") or []
        top_hard_block = hard_blocks[0] if hard_blocks else {}
        trade_count = int(metrics.get("trade_count") or 0)
        rejected_by_risk = int(metrics.get("rejected_by_risk_count") or 0)
        blocked_count = int(risk.get("blocked_decision_count") or 0)
        skipped_due_to_data = int(risk.get("skipped_due_to_data_count") or 0)
        benchmark = backtest.get("benchmark") or {}
        warnings = backtest.get("execution_warnings") or []
        top_rule_id = str(top_hard_block.get("rule_id") or "")
        top_share = float(top_hard_block.get("share_of_blocked") or 0.0)

        checks = {
            "live_trading_disabled": not settings.enable_live_trading,
            "backtest_completed": backtest.get("status") == "completed",
            "benchmark_ready": benchmark.get("status") == "ready",
            "risk_diagnostics_ready": risk.get("status") == "ready",
            "zero_completed_trades": trade_count == 0,
            "risk_rejections_present": rejected_by_risk > 0 and blocked_count > 0,
            "all_blocks_explained_by_single_known_rule": (
                top_rule_id in V1_ACCEPTABLE_STRICT_HARD_BLOCKS
                and top_share >= 0.999
                and int(top_hard_block.get("count") or 0) == blocked_count
            ),
            "no_data_skips": skipped_due_to_data == 0,
            "no_execution_warnings": not warnings,
        }
        accepted = all(checks.values())
        status = "accepted_conservative_no_trade_gate" if accepted else "needs_strategy_review"
        return {
            "schema_version": "v1_strategy_safety_review.v1",
            "status": status,
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
            "accepted_attention_items": (
                sorted(V1_STRATEGY_ATTENTION_ITEMS) if accepted else []
            ),
            "checks": checks,
            "evidence": {
                "latest_backtest_id": backtest.get("id"),
                "start_date": backtest.get("start_date"),
                "end_date": backtest.get("end_date"),
                "trade_count": trade_count,
                "rejected_by_risk_count": rejected_by_risk,
                "blocked_decision_count": blocked_count,
                "evaluated_decision_count": risk.get("evaluated_decision_count"),
                "skipped_due_to_data_count": skipped_due_to_data,
                "top_hard_block_rule_id": top_rule_id,
                "top_hard_block_count": int(top_hard_block.get("count") or 0),
                "top_hard_block_share_of_blocked": top_share,
                "benchmark_status": benchmark.get("status"),
                "execution_warning_count": len(warnings),
            },
            "policy": {
                "strict_backtest_keeps_rule_enabled": True,
                "accepted_strict_hard_blocks": sorted(V1_ACCEPTABLE_STRICT_HARD_BLOCKS),
                "rules_yaml_mutation_required": False,
                "real_order_execution_enabled": False,
                "simulation_relaxation_requires_separate_gates": True,
            },
            "next_action": (
                "keep_strict_rule_and_review_simulation_only_relaxation"
                if accepted
                else "review_backtest_data_or_unexplained_strategy_blocks"
            ),
        }

    @staticmethod
    def _accepted_attention_items(
        *,
        attention_items: list[str],
        strategy_safety_review: dict[str, Any],
    ) -> list[str]:
        accepted = set(strategy_safety_review.get("accepted_attention_items") or [])
        return sorted(item for item in attention_items if item in accepted)

    @staticmethod
    def _release_gate(
        *,
        status: str,
        attention_items: list[str],
        accepted_attention_items: list[str],
        blocking_attention_items: list[str],
        strategy_safety_review: dict[str, Any],
        sim_cockpit: dict[str, Any],
    ) -> dict[str, Any]:
        blocking_set = set(blocking_attention_items)
        only_sim_window_blocked = blocking_set == {"sim_cockpit_not_verified"}
        strategy_accepted = (
            strategy_safety_review.get("status") == "accepted_conservative_no_trade_gate"
        )
        sim_verified = (
            sim_cockpit.get("status") == "verified"
            and sim_cockpit.get("simulation_actions_allowed") is True
        )
        if status == "ready_for_v1_review":
            gate_status = "ready_for_v1_review"
            next_action = "begin_v2_readiness_planning"
        elif only_sim_window_blocked and strategy_accepted:
            gate_status = "externally_blocked_simulation_window"
            next_action = "open_tonghuashun_mncg_simulation_window_then_run_window_detection_record_true"
        else:
            gate_status = "needs_v1_stabilization_work"
            next_action = "resolve_blocking_attention_items"

        return {
            "schema_version": "v1_release_gate.v1",
            "status": gate_status,
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
            "code_data_strategy_stable": bool(
                not settings.enable_live_trading
                and strategy_accepted
                and set(accepted_attention_items).issubset(set(attention_items))
                and only_sim_window_blocked
            ),
            "ready_for_v1_review": status == "ready_for_v1_review",
            "external_blockers": (
                ["tonghuashun_mncg_simulation_window_not_verified"]
                if gate_status == "externally_blocked_simulation_window"
                else []
            ),
            "blocking_attention_items": blocking_attention_items,
            "accepted_attention_items": accepted_attention_items,
            "sim_cockpit_verified": bool(sim_verified),
            "required_external_evidence": [
                "GET /health returns live_trading_enabled=false",
                "GET /api/sim-cockpit/window-detection?record=true returns status=verified for a Tonghuashun mncg simulation window",
                "GET /api/sim-cockpit/status returns simulation_actions_allowed=true",
            ],
            "forbidden_shortcuts": [
                "do_not_use_fixture_or_manual_payload_to_fake_window_verification",
                "do_not_enable_live_trading",
                "do_not_use_real_account_broker_login_or_fund_account_views",
            ],
            "next_action": next_action,
        }

    def _table_count(self, table: str) -> int:
        row = self.store.fetch_one(f"SELECT COUNT(*) AS count FROM {table}") or {}
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
