from __future__ import annotations

from datetime import datetime
import json
from typing import Any

from app.config import settings
from app.learning.service import LearningService
from app.risk.portfolio import PortfolioRiskService
from app.storage.sqlite_store import SQLiteStore


class ExperienceMemoryService:
    def __init__(self) -> None:
        self.store = SQLiteStore(settings.database_path)
        self.store.init()

    def capture_recent_events(self, limit: int = 300) -> dict[str, Any]:
        inserted = 0
        inserted += self._capture_table(
            table="candidate_lifecycle_events",
            category="candidate_lifecycle",
            event_type_field="event_type",
            symbol_field="symbol",
            name_field="name",
            date_field="created_at",
            payload_fields=["from_state", "to_state", "source"],
            limit=limit,
        )
        inserted += self._capture_table(
            table="monitoring_alerts",
            category="monitoring_alert",
            event_type_field="alert_type",
            symbol_field="symbol",
            date_field="created_at",
            outcome_field="severity",
            payload_fields=["session_id", "event_id", "severity", "message", "payload_json"],
            limit=limit,
        )
        inserted += self._capture_table(
            table="monitoring_alert_actions",
            category="operator_action",
            event_type_field="action_type",
            date_field="created_at",
            payload_fields=["alert_id", "note", "created_by", "payload_json"],
            limit=limit,
        )
        inserted += self._capture_table(
            table="simulation_fills",
            category="simulation_fill",
            event_type_field="side",
            symbol_field="symbol",
            date_field="created_at",
            payload_fields=["quantity", "fill_price", "amount", "fee", "stamp_tax"],
            limit=limit,
        )
        inserted += self._capture_table(
            table="historical_backtest_trades",
            category="backtest_execution",
            event_type_field="side",
            symbol_field="symbol",
            date_field="trade_date",
            outcome_field="fill_status",
            payload_fields=["run_id", "quantity", "price", "reason", "reject_reason", "liquidity_cap_amount"],
            limit=limit,
        )
        inserted += self._capture_table(
            table="historical_backtest_closed_trades",
            category="closed_trade",
            event_type="closed_trade",
            symbol_field="symbol",
            date_field="exit_date",
            outcome_from=lambda row: "success" if float(row.get("realized_pnl") or 0) > 0 else "failure",
            payload_fields=[
                "run_id",
                "quantity",
                "entry_date",
                "exit_date",
                "entry_price",
                "exit_price",
                "realized_pnl",
                "realized_pnl_pct",
                "holding_days",
                "exit_reason",
            ],
            limit=limit,
        )
        inserted += self._capture_table(
            table="ai_parameter_proposals",
            category="ai_proposal",
            event_type="ai_parameter_proposal",
            date_field="created_at",
            outcome_field="status",
            payload_fields=["trades_analyzed", "proposed_patch_json", "safety_blocks_json", "validation_json"],
            limit=limit,
        )
        inserted += self._capture_table(
            table="ai_model_audit_logs",
            category="ai_audit",
            event_type_field="operation",
            date_field="created_at",
            outcome_field="provider",
            payload_fields=["prompt_json", "response_json", "safety_json", "simulation_only"],
            limit=limit,
        )
        inserted += self._capture_table(
            table="price_readiness_reports",
            category="data_quality",
            event_type="price_readiness",
            symbol_field="symbol",
            name_field="name",
            date_field="updated_at",
            outcome_field="coverage_status",
            payload_fields=["source", "latest_price", "history_points", "error_message", "metrics_json"],
            limit=limit,
        )
        return {
            "status": "captured",
            "inserted_count": inserted,
            "summary": self.summary(),
            "live_trading_enabled": settings.enable_live_trading,
        }

    def create_daily_review(self, review_date: str | None = None) -> dict[str, Any]:
        review_date = review_date or datetime.now().strftime("%Y-%m-%d")
        self.capture_recent_events()
        learning_report = LearningService().generate_review_report(report_type="daily")
        latest_backtest = self._latest_backtest()
        portfolio = PortfolioRiskService().state()
        classifications = self._classifications(review_date)
        strategy_snapshot = self._persist_strategy_snapshot(review_date, latest_backtest, portfolio)
        summary = {
            "candidate_snapshot": learning_report.summary.get("candidate_snapshot", {}),
            "monitoring_alerts": learning_report.summary.get("monitoring_alerts", []),
            "paper_simulation_outcomes": learning_report.summary.get("paper_simulation_outcomes", {}),
            "backtest_metrics": latest_backtest.get("metrics") if latest_backtest else {},
            "backtest_benchmark": latest_backtest.get("benchmark") if latest_backtest else {},
            "backtest_warnings": latest_backtest.get("execution_warnings") if latest_backtest else [],
            "portfolio_risk": {
                "posture": portfolio.get("posture"),
                "gates": portfolio.get("gates", []),
            },
            "open_review_items": learning_report.summary.get("open_review_items", {}),
            "next_actions": self._next_actions(classifications, latest_backtest, portfolio),
            "safety": {
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            },
        }
        with self.store.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO experience_reviews(
                    period_type, period_start, period_end, title, summary_json,
                    classification_json, next_actions_json, source_report_id,
                    live_trading_enabled
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(period_type, period_start, period_end) DO UPDATE SET
                    title = excluded.title,
                    summary_json = excluded.summary_json,
                    classification_json = excluded.classification_json,
                    next_actions_json = excluded.next_actions_json,
                    source_report_id = excluded.source_report_id,
                    live_trading_enabled = excluded.live_trading_enabled,
                    created_at = CURRENT_TIMESTAMP
                """,
                (
                    "daily",
                    review_date,
                    review_date,
                    f"{review_date} trading experience review",
                    json.dumps(summary, ensure_ascii=False, default=str),
                    json.dumps(classifications, ensure_ascii=False, default=str),
                    json.dumps(summary["next_actions"], ensure_ascii=False, default=str),
                    learning_report.id,
                    1 if settings.enable_live_trading else 0,
                ),
            )
            review_id = int(cursor.lastrowid or 0)
        return {
            "id": review_id,
            "period_type": "daily",
            "period_start": review_date,
            "period_end": review_date,
            "summary": summary,
            "classifications": classifications,
            "strategy_snapshot": strategy_snapshot,
            "source_learning_report_id": learning_report.id,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def summary(self) -> dict[str, Any]:
        counts = self.store.fetch_all(
            """
            SELECT category, COUNT(*) AS count
            FROM experience_events
            GROUP BY category
            ORDER BY count DESC
            """
        )
        latest_review = self.latest_reviews(limit=1)
        return {
            "event_counts": {row["category"]: int(row["count"]) for row in counts},
            "review_count": self._count("experience_reviews"),
            "strategy_snapshot_count": self._count("strategy_performance_snapshots"),
            "code_evolution_count": self._count("code_evolution_records"),
            "latest_review": latest_review[0] if latest_review else None,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def events(
        self,
        category: str | None = None,
        symbol: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        clauses = []
        params: list[Any] = []
        if category:
            clauses.append("category = ?")
            params.append(category)
        if symbol:
            clauses.append("symbol = ?")
            params.append(symbol)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(max(1, min(limit, 500)))
        rows = self.store.fetch_all(
            f"""
            SELECT *
            FROM experience_events
            {where}
            ORDER BY id DESC
            LIMIT ?
            """,
            tuple(params),
        )
        return [self._json_model(row, ["payload_json"]) for row in rows]

    def latest_reviews(self, limit: int = 20) -> list[dict[str, Any]]:
        rows = self.store.fetch_all(
            """
            SELECT *
            FROM experience_reviews
            ORDER BY id DESC
            LIMIT ?
            """,
            (max(1, min(limit, 100)),),
        )
        return [
            self._json_model(row, ["summary_json", "classification_json", "next_actions_json"])
            for row in rows
        ]

    def strategy_performance(self, limit: int = 20) -> list[dict[str, Any]]:
        rows = self.store.fetch_all(
            """
            SELECT *
            FROM strategy_performance_snapshots
            ORDER BY id DESC
            LIMIT ?
            """,
            (max(1, min(limit, 100)),),
        )
        return [self._json_model(row, ["metrics_json"]) for row in rows]

    def code_evolution_records(self, limit: int = 20) -> list[dict[str, Any]]:
        rows = self.store.fetch_all(
            """
            SELECT *
            FROM code_evolution_records
            ORDER BY id DESC
            LIMIT ?
            """,
            (max(1, min(limit, 100)),),
        )
        return [
            self._json_model(row, ["rationale_json", "plan_json", "validation_json"])
            for row in rows
        ]

    def record_code_evolution_plan(
        self,
        title: str,
        rationale: dict[str, Any],
        plan: dict[str, Any],
        validation: dict[str, Any] | None = None,
        record_type: str = "codex_plan",
        status: str = "draft",
    ) -> dict[str, Any]:
        with self.store.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO code_evolution_records(
                    record_type, status, title, rationale_json, plan_json, validation_json
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    record_type,
                    status,
                    title,
                    json.dumps(rationale, ensure_ascii=False, default=str),
                    json.dumps(plan, ensure_ascii=False, default=str),
                    json.dumps(validation or {}, ensure_ascii=False, default=str),
                ),
            )
            record_id = int(cursor.lastrowid)
        row = self.store.fetch_one("SELECT * FROM code_evolution_records WHERE id = ?", (record_id,))
        return self._json_model(row, ["rationale_json", "plan_json", "validation_json"])

    def _capture_table(
        self,
        table: str,
        category: str,
        event_type: str | None = None,
        event_type_field: str | None = None,
        symbol_field: str | None = None,
        name_field: str | None = None,
        date_field: str = "created_at",
        outcome_field: str | None = None,
        outcome_from=None,
        payload_fields: list[str] | None = None,
        limit: int = 300,
    ) -> int:
        rows = self.store.fetch_all(
            f"""
            SELECT *
            FROM {table}
            ORDER BY id DESC
            LIMIT ?
            """,
            (max(1, min(limit, 1000)),),
        )
        inserted = 0
        for row in rows:
            source_id = str(row.get("id"))
            source_key = f"{table}:{source_id}:{event_type or row.get(event_type_field or '')}"
            row_event_type = event_type or str(row.get(event_type_field or "event") or "event")
            outcome = outcome_from(row) if outcome_from else row.get(outcome_field) if outcome_field else None
            payload = {field: row.get(field) for field in payload_fields or []}
            payload = {key: self._decode_json(value) for key, value in payload.items()}
            inserted += self._insert_event(
                source_key=source_key,
                event_date=self._date_only(row.get(date_field)),
                event_type=row_event_type,
                category=category,
                source_table=table,
                source_id=source_id,
                symbol=row.get(symbol_field) if symbol_field else None,
                name=row.get(name_field) if name_field else None,
                outcome_label=outcome,
                confidence=0.8,
                payload=payload,
            )
        return inserted

    def _insert_event(
        self,
        source_key: str,
        event_date: str | None,
        event_type: str,
        category: str,
        source_table: str,
        source_id: str | None,
        symbol: str | None,
        name: str | None,
        outcome_label: str | None,
        confidence: float,
        payload: dict[str, Any],
    ) -> int:
        with self.store.connect() as conn:
            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO experience_events(
                    source_key, event_date, event_type, category, source_table,
                    source_id, symbol, name, outcome_label, confidence, payload_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source_key,
                    event_date,
                    event_type,
                    category,
                    source_table,
                    source_id,
                    symbol,
                    name,
                    outcome_label,
                    confidence,
                    json.dumps(payload, ensure_ascii=False, default=str),
                ),
            )
            return 1 if cursor.rowcount else 0

    def _classifications(self, review_date: str) -> dict[str, Any]:
        rows = self.store.fetch_all(
            """
            SELECT category, outcome_label, COUNT(*) AS count
            FROM experience_events
            WHERE event_date IS NULL OR event_date <= ?
            GROUP BY category, outcome_label
            """,
            (review_date,),
        )
        closed = self.store.fetch_all(
            """
            SELECT symbol, realized_pnl, exit_reason
            FROM historical_backtest_closed_trades
            ORDER BY id DESC
            LIMIT 200
            """
        )
        return {
            "by_category_outcome": [
                {
                    "category": row["category"],
                    "outcome_label": row["outcome_label"] or "unknown",
                    "count": int(row["count"]),
                }
                for row in rows
            ],
            "success_cases": [row for row in closed if float(row.get("realized_pnl") or 0) > 0][:10],
            "failure_cases": [row for row in closed if float(row.get("realized_pnl") or 0) <= 0][:10],
            "risk_block_success_count": self._event_count("monitoring_alert", "risk_blocked_observe"),
            "data_issue_count": self._event_count("data_quality", "error"),
        }

    def _persist_strategy_snapshot(
        self,
        review_date: str,
        latest_backtest: dict[str, Any] | None,
        portfolio: dict[str, Any],
    ) -> dict[str, Any] | None:
        if not latest_backtest:
            return None
        metrics = {
            **(latest_backtest.get("metrics") or {}),
            "benchmark": latest_backtest.get("benchmark") or {},
            "execution_warnings": latest_backtest.get("execution_warnings") or [],
            "portfolio_posture": portfolio.get("posture"),
            "risk_gates": portfolio.get("gates", []),
            "review_only": True,
        }
        with self.store.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO strategy_performance_snapshots(
                    strategy_name, period_start, period_end, market_regime,
                    metrics_json, source_run_id
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(strategy_name, period_start, period_end, source_run_id) DO UPDATE SET
                    market_regime = excluded.market_regime,
                    metrics_json = excluded.metrics_json,
                    created_at = CURRENT_TIMESTAMP
                """,
                (
                    "local_rule_v2_5",
                    latest_backtest.get("start_date") or review_date,
                    latest_backtest.get("end_date") or review_date,
                    (portfolio.get("market_regime") or {}).get("regime"),
                    json.dumps(metrics, ensure_ascii=False, default=str),
                    latest_backtest.get("id"),
                ),
            )
            snapshot_id = int(cursor.lastrowid or 0)
        return {"id": snapshot_id, "metrics": metrics}

    def _latest_backtest(self) -> dict[str, Any] | None:
        row = self.store.fetch_one(
            """
            SELECT *
            FROM historical_backtest_runs
            ORDER BY id DESC
            LIMIT 1
            """
        )
        if not row:
            return None
        row["metrics"] = self._decode_json(row.pop("metrics_json", "{}"))
        row["benchmark"] = self._decode_json(row.pop("benchmark_json", "{}"))
        row["execution_warnings"] = self._decode_json(row.pop("execution_warnings_json", "[]"))
        return row

    def _next_actions(
        self,
        classifications: dict[str, Any],
        latest_backtest: dict[str, Any] | None,
        portfolio: dict[str, Any],
    ) -> list[str]:
        actions = [
            "Keep collecting daily review samples, prioritizing candidates already in review or focus-watch states."
        ]
        if latest_backtest and latest_backtest.get("execution_warnings"):
            actions.append(
                "Review backtest execution warnings and separate price-limit blocks, liquidity issues, and missing data."
            )
        if portfolio.get("posture") == "stop_new_entries":
            actions.append(
                "Portfolio risk is blocking new entries; next cycle should only observe and review risk."
            )
        if classifications.get("failure_cases"):
            actions.append(
                "Attribute failure cases to early entry, chasing highs, market-regime deterioration, or data quality."
            )
        return actions

    def _json_model(self, row: dict[str, Any] | None, json_fields: list[str]) -> dict[str, Any]:
        if not row:
            return {}
        item = dict(row)
        for field in json_fields:
            if field in item:
                key = field.removesuffix("_json")
                item[key] = self._decode_json(item.pop(field) or "{}")
        return item

    def _decode_json(self, value: Any) -> Any:
        if not isinstance(value, str):
            return value
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value

    def _date_only(self, value: Any) -> str | None:
        if value is None:
            return None
        return str(value)[:10]

    def _count(self, table: str) -> int:
        row = self.store.fetch_one(f"SELECT COUNT(*) AS count FROM {table}")
        return int(row["count"]) if row else 0

    def _event_count(self, category: str, outcome_label: str | None = None) -> int:
        if outcome_label is None:
            row = self.store.fetch_one(
                "SELECT COUNT(*) AS count FROM experience_events WHERE category = ?",
                (category,),
            )
        else:
            row = self.store.fetch_one(
                """
                SELECT COUNT(*) AS count
                FROM experience_events
                WHERE category = ? AND outcome_label = ?
                """,
                (category, outcome_label),
            )
        return int(row["count"]) if row else 0
