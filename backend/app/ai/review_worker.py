from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import json
from typing import Any

from app.ai.model_gateway import DisabledModelGateway, ModelGatewayResult
from app.backtest.engine import BacktestEngine
from app.config import settings
from app.storage.sqlite_store import SQLiteStore


class AIReviewWorker:
    def __init__(self):
        self.store = SQLiteStore(settings.database_path)
        self.store.init()
        self.gateway = DisabledModelGateway()

    def generate_review(self) -> dict:
        trades = self.store.fetch_all(
            """
            SELECT *
            FROM historical_backtest_trades
            ORDER BY trade_date DESC, id DESC
            LIMIT 50
            """
        )
        gateway_result = self.gateway.propose_parameter_patch([dict(row) for row in trades])
        self._record_audit(gateway_result)
        proposed_patch = gateway_result.response["proposed_patch"]
        applied_blocks = gateway_result.safety["safety_blocks_applied"]
        with self.store.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO ai_parameter_proposals (
                    trades_analyzed, proposed_patch_json, safety_blocks_json, status
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    len(trades),
                    json.dumps(proposed_patch, ensure_ascii=False),
                    json.dumps(applied_blocks, ensure_ascii=False),
                    "draft",
                ),
            )
            proposal_id = int(cursor.lastrowid)
        return {
            "id": proposal_id,
            "status": "success",
            "trades_analyzed": len(trades),
            "proposed_patch": proposed_patch,
            "safety_blocks_applied": applied_blocks,
            "timestamp": datetime.now().isoformat(),
            "provider": gateway_result.provider,
            "simulation_only": True,
        }

    def list_proposals(self, limit: int = 20) -> list[dict]:
        rows = self.store.fetch_all(
            """
            SELECT *
            FROM ai_parameter_proposals
            ORDER BY id DESC
            LIMIT ?
            """,
            (max(1, min(limit, 100)),),
        )
        return [self._proposal_model(row) for row in rows]

    def validate_proposal(self, proposal_id: int) -> dict:
        proposal = self._get_proposal(proposal_id)
        patch = proposal["proposed_patch"]
        latest_run = self.store.fetch_one(
            """
            SELECT *
            FROM historical_backtest_runs
            WHERE status = 'completed'
            ORDER BY id DESC
            LIMIT 1
            """
        )
        validation = {
            "status": "validation_failed",
            "checks": {
                "has_completed_backtest": latest_run is not None,
                "sample_size": False,
                "out_of_sample_not_worse": False,
                "hard_blocks_preserved": self._hard_blocks_preserved(patch),
                "live_trading_disabled": settings.enable_live_trading is False,
            },
            "in_sample": {},
            "out_of_sample": {},
            "validated_at": datetime.now().isoformat(),
            "simulation_only": True,
        }
        if latest_run:
            validation.update(self._split_validation(dict(latest_run), patch))
        if all(validation["checks"].values()):
            validation["status"] = "validation_passed"
        with self.store.connect() as conn:
            conn.execute(
                """
                UPDATE ai_parameter_proposals
                SET status = ?, validation_json = ?
                WHERE id = ?
                """,
                (
                    validation["status"],
                    json.dumps(validation, ensure_ascii=False),
                    proposal_id,
                ),
            )
        return validation

    def approve_for_simulation(
        self,
        proposal_id: int,
        reviewed_by: str = "user",
        note: str | None = None,
    ) -> dict:
        proposal = self._get_proposal(proposal_id)
        if proposal["status"] != "validation_passed":
            raise ValueError("AI proposal must pass validation before simulation approval.")
        return self._review(proposal_id, "approved_for_simulation", reviewed_by, note)

    def reject(
        self,
        proposal_id: int,
        reviewed_by: str = "user",
        note: str | None = None,
    ) -> dict:
        self._get_proposal(proposal_id)
        return self._review(proposal_id, "rejected", reviewed_by, note)

    def _split_validation(self, latest_run: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
        start_date = latest_run.get("start_date")
        end_date = latest_run.get("end_date")
        benchmark_symbol = latest_run.get("benchmark_symbol") or settings.backtest_default_benchmark_symbol
        base_config = json.loads(latest_run.get("config_json") or "{}")
        proposed_config = self._merge_patch(base_config, patch)
        dates = self._dates_between(start_date, end_date)
        if len(dates) < 4:
            return {
                "checks": {
                    "has_completed_backtest": True,
                    "sample_size": False,
                    "out_of_sample_not_worse": False,
                    "hard_blocks_preserved": self._hard_blocks_preserved(patch),
                    "live_trading_disabled": settings.enable_live_trading is False,
                },
                "failure_reason": "insufficient_dates_for_time_series_split",
            }
        split_index = max(1, int(len(dates) * 0.7) - 1)
        train_start = dates[0]
        train_end = dates[split_index]
        out_start = dates[min(split_index + 1, len(dates) - 1)]
        out_end = dates[-1]
        before_train = BacktestEngine(config=base_config).run(
            train_start,
            train_end,
            [],
            float(latest_run.get("initial_cash") or 100000),
            5,
            0.2,
            benchmark_symbol=benchmark_symbol,
            persist=False,
        )
        after_train = BacktestEngine(config=proposed_config).run(
            train_start,
            train_end,
            [],
            float(latest_run.get("initial_cash") or 100000),
            5,
            0.2,
            benchmark_symbol=benchmark_symbol,
            persist=False,
        )
        before_out = BacktestEngine(config=base_config).run(
            out_start,
            out_end,
            [],
            float(latest_run.get("initial_cash") or 100000),
            5,
            0.2,
            benchmark_symbol=benchmark_symbol,
            persist=False,
        )
        after_out = BacktestEngine(config=proposed_config).run(
            out_start,
            out_end,
            [],
            float(latest_run.get("initial_cash") or 100000),
            5,
            0.2,
            benchmark_symbol=benchmark_symbol,
            persist=False,
        )
        before_out_metrics = before_out["metrics"]
        after_out_metrics = after_out["metrics"]
        sample_size = int(after_out_metrics.get("closed_trade_count") or 0) >= 20
        out_of_sample_not_worse = (
            float(after_out_metrics.get("total_return") or 0) >= float(before_out_metrics.get("total_return") or 0)
            and float(after_out_metrics.get("max_drawdown") or 0) <= float(before_out_metrics.get("max_drawdown") or 0)
        )
        return {
            "checks": {
                "has_completed_backtest": True,
                "sample_size": sample_size,
                "out_of_sample_not_worse": out_of_sample_not_worse,
                "hard_blocks_preserved": self._hard_blocks_preserved(patch),
                "live_trading_disabled": settings.enable_live_trading is False,
            },
            "in_sample": {
                "period": {"start": train_start, "end": train_end},
                "before": before_train["metrics"],
                "after": after_train["metrics"],
            },
            "out_of_sample": {
                "period": {"start": out_start, "end": out_end},
                "before": before_out_metrics,
                "after": after_out_metrics,
            },
        }

    def _dates_between(self, start_date: str | None, end_date: str | None) -> list[str]:
        if not start_date or not end_date:
            return []
        rows = self.store.fetch_all(
            """
            SELECT DISTINCT trade_date
            FROM daily_bar_cache
            WHERE quality_status = 'ready'
              AND trade_date >= ?
              AND trade_date <= ?
            ORDER BY trade_date ASC
            """,
            (start_date, end_date),
        )
        return [row["trade_date"] for row in rows]

    def _merge_patch(self, base_config: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
        merged = deepcopy(base_config)
        if "candidate_tiers" in patch:
            merged.setdefault("candidate_tiers", {}).update(patch["candidate_tiers"])
        patch_rules = {rule.get("id"): rule for rule in patch.get("rules", []) if rule.get("id")}
        for rule in merged.get("rules", []):
            if rule.get("id") in patch_rules:
                rule.update(patch_rules[rule["id"]])
        return merged

    def _record_audit(self, result: ModelGatewayResult) -> None:
        with self.store.connect() as conn:
            conn.execute(
                """
                INSERT INTO ai_model_audit_logs(
                    provider, operation, prompt_json, response_json, safety_json, simulation_only
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    result.provider,
                    result.operation,
                    json.dumps(result.prompt, ensure_ascii=False),
                    json.dumps(result.response, ensure_ascii=False),
                    json.dumps(result.safety, ensure_ascii=False),
                    1,
                ),
            )

    def _review(
        self,
        proposal_id: int,
        status: str,
        reviewed_by: str,
        note: str | None,
    ) -> dict:
        reviewed_at = datetime.now().isoformat()
        with self.store.connect() as conn:
            conn.execute(
                """
                UPDATE ai_parameter_proposals
                SET status = ?, reviewed_by = ?, review_note = ?, reviewed_at = ?
                WHERE id = ?
                """,
                (status, reviewed_by, note, reviewed_at, proposal_id),
            )
        proposal = self._get_proposal(proposal_id)
        proposal["reviewed_at"] = reviewed_at
        return proposal

    def _get_proposal(self, proposal_id: int) -> dict:
        row = self.store.fetch_one(
            "SELECT * FROM ai_parameter_proposals WHERE id = ?",
            (proposal_id,),
        )
        if not row:
            raise ValueError("AI proposal not found.")
        return self._proposal_model(row)

    def _proposal_model(self, row) -> dict:
        item = dict(row)
        item["proposed_patch"] = json.loads(item.pop("proposed_patch_json") or "{}")
        item["safety_blocks"] = json.loads(item.pop("safety_blocks_json") or "[]")
        item["validation"] = json.loads(item.pop("validation_json") or "{}")
        return item

    def _hard_blocks_preserved(self, patch: dict) -> bool:
        return all(rule.get("hard_block", True) for rule in patch.get("rules", []))
