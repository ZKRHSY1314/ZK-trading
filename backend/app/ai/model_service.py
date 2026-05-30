from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import json
from typing import Any

from app.ai.model_gateway import DisabledModelGateway, ModelGateway, ModelGatewayResult
from app.config import settings
from app.experience.code_evolution import CodeEvolutionService
from app.storage.sqlite_store import SQLiteStore


ALLOWED_MODEL_OUTPUTS = {"explanation", "attribution", "similar_groups", "validation_request"}
SAFETY_KEYS = {"review_only", "simulation_only", "live_trading_enabled"}
DANGEROUS_TERMS = (
    "broker",
    "order",
    "credential",
    "live_trading",
    "shell",
    "apply_patch",
    "git push",
)


class AIModelGatewayService:
    def __init__(self, gateway: ModelGateway | None = None) -> None:
        self.store = SQLiteStore(settings.database_path)
        self.store.init()
        self.gateway = gateway or DisabledModelGateway()
        self.code_evolution = CodeEvolutionService()

    def capabilities(self) -> dict[str, Any]:
        return {
            "provider": "mock_local_rule",
            "default_provider": "mock_local_rule",
            "external_network": False,
            "api_key_required": False,
            "operations": [
                "code_evolution_explanation",
                "experience_review_summary",
            ],
            "allowed_outputs": sorted(ALLOWED_MODEL_OUTPUTS),
            "forbidden_outputs": [
                "patch",
                "shell_command",
                "broker_action",
                "order_action",
                "credential_request",
                "live_trading_action",
            ],
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": False,
        }

    def explain_code_evolution(self, record_id: int) -> dict[str, Any]:
        record = self.code_evolution.get_record(record_id)
        context = self._code_evolution_context()
        result = self.gateway.explain_code_evolution(record, context)
        safe_result = self._safe_result(result)
        self._record_audit(safe_result)
        model_review = {
            "provider": safe_result.provider,
            "operation": safe_result.operation,
            "response": safe_result.response,
            "safety": safe_result.safety,
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": False,
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
        updated_record = self._write_model_review(record_id, model_review)
        return {
            "record_id": record_id,
            "record": updated_record,
            "model_review": model_review,
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": False,
        }

    def audit_logs(self, operation: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        params: list[Any] = []
        where = ""
        if operation:
            where = "WHERE operation = ?"
            params.append(operation)
        params.append(max(1, min(limit, 200)))
        rows = self.store.fetch_all(
            f"""
            SELECT *
            FROM ai_model_audit_logs
            {where}
            ORDER BY id DESC
            LIMIT ?
            """,
            tuple(params),
        )
        return [self._audit_model(row) for row in rows]

    def summarize_experience_review(self, review_id: int | None = None) -> dict[str, Any]:
        review = self._latest_review() if review_id is None else self._review_by_id(review_id)
        if not review:
            raise ValueError("Experience review not found.")
        events = self._experience_events(limit=100)
        result = self.gateway.summarize_experience_review(review, events)
        safe_result = self._safe_result(result)
        self._record_audit(safe_result)
        return {
            "provider": safe_result.provider,
            "operation": safe_result.operation,
            "response": safe_result.response,
            "safety": safe_result.safety,
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": False,
        }

    def _code_evolution_context(self) -> dict[str, Any]:
        return {
            "experience_events": self._experience_events(limit=120),
            "experience_reviews": self._experience_reviews(limit=20),
            "closed_trades": self._closed_trades(limit=120),
            "strategy_snapshots": self._strategy_snapshots(limit=30),
        }

    def _write_model_review(self, record_id: int, model_review: dict[str, Any]) -> dict[str, Any]:
        record = self.code_evolution.get_record(record_id)
        rationale = deepcopy(record.get("rationale") or {})
        rationale["model_review"] = model_review
        with self.store.connect() as conn:
            conn.execute(
                """
                UPDATE code_evolution_records
                SET rationale_json = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (json.dumps(rationale, ensure_ascii=False, default=str), record_id),
            )
        return self.code_evolution.get_record(record_id)

    def _safe_result(self, result: ModelGatewayResult) -> ModelGatewayResult:
        response, blocked_terms = self._sanitize_value(result.response)
        safety = deepcopy(result.safety)
        safety_blocks = list(safety.get("safety_blocks_applied") or [])
        unexpected_keys = sorted(set(response) - ALLOWED_MODEL_OUTPUTS - SAFETY_KEYS)
        if unexpected_keys:
            for key in unexpected_keys:
                response.pop(key, None)
            safety_blocks.append(f"unexpected_output_keys_removed:{','.join(unexpected_keys)}")
        if blocked_terms:
            safety_blocks.append(f"dangerous_terms_blocked:{','.join(sorted(blocked_terms))}")
        response.update(
            {
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": False,
            }
        )
        safety.update(
            {
                "safety_blocks_applied": safety_blocks,
                "blocked_terms": sorted(blocked_terms),
                "allowed_outputs": sorted(ALLOWED_MODEL_OUTPUTS),
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": False,
            }
        )
        return ModelGatewayResult(
            provider=result.provider,
            operation=result.operation,
            prompt=result.prompt,
            response=response,
            safety=safety,
        )

    def _sanitize_value(self, value: Any) -> tuple[Any, set[str]]:
        blocked_terms: set[str] = set()
        if isinstance(value, str):
            lowered = value.lower()
            matched = {term for term in DANGEROUS_TERMS if term in lowered}
            if matched:
                return "[blocked by V3.5 safety filter]", matched
            return value, blocked_terms
        if isinstance(value, list):
            sanitized_list = []
            for item in value:
                sanitized, terms = self._sanitize_value(item)
                sanitized_list.append(sanitized)
                blocked_terms.update(terms)
            return sanitized_list, blocked_terms
        if isinstance(value, dict):
            sanitized_dict = {}
            for key, item in value.items():
                sanitized, terms = self._sanitize_value(item)
                sanitized_dict[key] = sanitized
                blocked_terms.update(terms)
            return sanitized_dict, blocked_terms
        return value, blocked_terms

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
                    json.dumps(result.prompt, ensure_ascii=False, default=str),
                    json.dumps(result.response, ensure_ascii=False, default=str),
                    json.dumps(result.safety, ensure_ascii=False, default=str),
                    1,
                ),
            )

    def _experience_events(self, limit: int) -> list[dict[str, Any]]:
        rows = self.store.fetch_all(
            """
            SELECT *
            FROM experience_events
            ORDER BY id DESC
            LIMIT ?
            """,
            (max(1, min(limit, 500)),),
        )
        return [self._json_model(row, ["payload_json"]) for row in rows]

    def _experience_reviews(self, limit: int) -> list[dict[str, Any]]:
        rows = self.store.fetch_all(
            """
            SELECT *
            FROM experience_reviews
            ORDER BY id DESC
            LIMIT ?
            """,
            (max(1, min(limit, 100)),),
        )
        return [self._json_model(row, ["summary_json", "classification_json", "next_actions_json"]) for row in rows]

    def _latest_review(self) -> dict[str, Any]:
        row = self.store.fetch_one(
            """
            SELECT *
            FROM experience_reviews
            ORDER BY id DESC
            LIMIT 1
            """
        )
        return self._json_model(row, ["summary_json", "classification_json", "next_actions_json"])

    def _review_by_id(self, review_id: int) -> dict[str, Any]:
        row = self.store.fetch_one("SELECT * FROM experience_reviews WHERE id = ?", (review_id,))
        return self._json_model(row, ["summary_json", "classification_json", "next_actions_json"])

    def _closed_trades(self, limit: int) -> list[dict[str, Any]]:
        rows = self.store.fetch_all(
            """
            SELECT *
            FROM historical_backtest_closed_trades
            ORDER BY id DESC
            LIMIT ?
            """,
            (max(1, min(limit, 500)),),
        )
        return [dict(row) for row in rows]

    def _strategy_snapshots(self, limit: int) -> list[dict[str, Any]]:
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

    def _audit_model(self, row: dict[str, Any]) -> dict[str, Any]:
        item = dict(row)
        item["prompt"] = self._decode_json(item.pop("prompt_json", "{}"))
        item["response"] = self._decode_json(item.pop("response_json", "{}"))
        item["safety"] = self._decode_json(item.pop("safety_json", "{}"))
        item["simulation_only"] = bool(item.get("simulation_only"))
        return item

    def _json_model(self, row: dict[str, Any] | None, json_fields: list[str]) -> dict[str, Any]:
        if not row:
            return {}
        item = dict(row)
        for field in json_fields:
            if field in item:
                item[field.removesuffix("_json")] = self._decode_json(item.pop(field) or "{}")
        return item

    def _decode_json(self, value: Any) -> Any:
        if not isinstance(value, str):
            return value
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
