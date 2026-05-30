from __future__ import annotations

from datetime import datetime
import json
from typing import Any

from app.config import settings
from app.storage.sqlite_store import SQLiteStore


ACTIVE_STATUSES = {"draft", "pending_validation", "validation_passed", "validation_failed", "accepted"}
VALID_STATUSES = ACTIVE_STATUSES | {"rejected"}


class CodeEvolutionService:
    def __init__(self) -> None:
        self.store = SQLiteStore(settings.database_path)
        self.store.init()

    def generate_review_items(self, limit: int = 5) -> dict[str, Any]:
        candidates = self._candidate_items()
        created: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []

        for item in candidates[: max(1, min(limit, 10))]:
            existing = self._find_active_duplicate(item["record_type"], item["title"])
            if existing:
                skipped.append(existing)
                continue
            created.append(self._insert_record(item))

        return {
            "status": "generated",
            "created_count": len(created),
            "skipped_duplicate_count": len(skipped),
            "created": created,
            "skipped_duplicates": skipped,
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def list_records(self, status: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
        params: list[Any] = []
        where = ""
        if status:
            where = "WHERE status = ?"
            params.append(status)
        params.append(max(1, min(limit, 100)))
        rows = self.store.fetch_all(
            f"""
            SELECT *
            FROM code_evolution_records
            {where}
            ORDER BY id DESC
            LIMIT ?
            """,
            tuple(params),
        )
        return [self._record_model(row) for row in rows]

    def get_record(self, record_id: int) -> dict[str, Any]:
        row = self.store.fetch_one("SELECT * FROM code_evolution_records WHERE id = ?", (record_id,))
        if not row:
            raise ValueError("Code evolution record not found.")
        return self._record_model(row)

    def record_validation(
        self,
        record_id: int,
        validation: dict[str, Any],
        status: str | None = None,
    ) -> dict[str, Any]:
        self.get_record(record_id)
        next_status = status or ("validation_passed" if self._validation_passed(validation) else "validation_failed")
        if next_status not in {"pending_validation", "validation_passed", "validation_failed"}:
            raise ValueError("Invalid validation status.")
        validation = {
            **validation,
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
            "recorded_at": datetime.now().isoformat(timespec="seconds"),
        }
        with self.store.connect() as conn:
            conn.execute(
                """
                UPDATE code_evolution_records
                SET status = ?, validation_json = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (next_status, json.dumps(validation, ensure_ascii=False, default=str), record_id),
            )
        return self.get_record(record_id)

    def approve(self, record_id: int, reviewed_by: str = "user", note: str | None = None) -> dict[str, Any]:
        record = self.get_record(record_id)
        if record["status"] != "validation_passed":
            raise ValueError("Code evolution record must pass validation before acceptance.")
        return self._review(record_id, "accepted", reviewed_by, note)

    def reject(self, record_id: int, reviewed_by: str = "user", note: str | None = None) -> dict[str, Any]:
        self.get_record(record_id)
        return self._review(record_id, "rejected", reviewed_by, note)

    def _candidate_items(self) -> list[dict[str, Any]]:
        review = self._latest_review()
        events = self._recent_events()
        snapshot = self._latest_strategy_snapshot()
        candidates: list[dict[str, Any]] = []

        data_events = [
            event
            for event in events
            if event.get("category") == "data_quality"
            and str(event.get("outcome_label") or "").lower() not in {"ready", "ok", "unknown"}
        ]
        benchmark_warnings = [
            warning
            for warning in (review.get("summary", {}).get("backtest_warnings") or [])
            if "benchmark" in str(warning).lower() or "data" in str(warning).lower()
        ]
        if data_events or benchmark_warnings:
            candidates.append(
                self._make_item(
                    "data_quality_fix",
                    "Review data quality gaps before expanding candidate scans",
                    "high",
                    evidence={"events": data_events[:5], "warnings": benchmark_warnings[:5]},
                    actions=[
                        "Inspect price readiness errors and stale/missing history.",
                        "Separate benchmark insufficiency from candidate data gaps.",
                        "Add a regression fixture for the observed missing-data condition.",
                    ],
                )
            )

        portfolio = review.get("summary", {}).get("portfolio_risk") or {}
        blocked_gates = [
            gate for gate in portfolio.get("gates", []) if str(gate.get("status")).lower() == "blocked"
        ]
        if portfolio.get("posture") == "stop_new_entries" or blocked_gates:
            candidates.append(
                self._make_item(
                    "risk_control_review",
                    "Review blocked portfolio-risk gates before new entries",
                    "high",
                    evidence={"posture": portfolio.get("posture"), "blocked_gates": blocked_gates},
                    actions=[
                        "Confirm whether blocked gates match the intended simulation posture.",
                        "Add or update tests around the triggered risk gate.",
                        "Keep downstream planners in stop_new_entries until validation passes.",
                    ],
                )
            )

        classification = review.get("classification") or review.get("classifications") or {}
        failure_cases = classification.get("failure_cases") or []
        if failure_cases:
            candidates.append(
                self._make_item(
                    "strategy_attribution",
                    "Attribute recent failed closed trades to strategy causes",
                    "medium",
                    evidence={"failure_cases": failure_cases[:10]},
                    actions=[
                        "Classify failures as early entry, chasing highs, weak market, or data issue.",
                        "Compare failed samples against successful main-force phase patterns.",
                        "Create review-only rule proposal only after attribution is stable.",
                    ],
                )
            )

        backtest_warnings = review.get("summary", {}).get("backtest_warnings") or []
        execution_events = [
            event
            for event in events
            if event.get("category") == "backtest_execution"
            and str(event.get("outcome_label") or "").lower() in {"partial", "rejected"}
        ]
        if backtest_warnings or execution_events:
            candidates.append(
                self._make_item(
                    "backtest_execution_review",
                    "Review backtest execution warnings and liquidity assumptions",
                    "medium",
                    evidence={"warnings": backtest_warnings[:10], "execution_events": execution_events[:10]},
                    actions=[
                        "Check partial/rejected fills for limit-price and liquidity assumptions.",
                        "Add fixtures for any new execution warning pattern.",
                        "Do not loosen execution realism to improve headline metrics.",
                    ],
                )
            )

        candidates.append(
            self._make_item(
                "code_maintenance",
                "Maintain V3.0 validation and review-panel coverage",
                "medium",
                evidence={
                    "latest_review_id": review.get("id"),
                    "latest_strategy_snapshot_id": snapshot.get("id") if snapshot else None,
                    "existing_code_evolution_count": self._count_records(),
                },
                actions=[
                    "Run the CLI validation pipeline before accepting any review item.",
                    "Keep forbidden tracked-file scan in the V3.0 release checklist.",
                    "Keep the frontend panel read-only except approve/reject review actions.",
                ],
            )
        )
        return candidates

    def _make_item(
        self,
        record_type: str,
        title: str,
        severity: str,
        evidence: dict[str, Any],
        actions: list[str],
    ) -> dict[str, Any]:
        return {
            "record_type": record_type,
            "status": "draft",
            "title": title,
            "rationale": {
                "severity": severity,
                "evidence": evidence,
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
                "generated_by": "deterministic_v3_code_evolution_service",
            },
            "plan": {
                "actions": actions,
                "acceptance_criteria": [
                    "Backend tests pass.",
                    "Frontend typecheck and build pass.",
                    "Forbidden tracked-file scan has no matches.",
                    "No live trading, broker, credential, or real order capability is added.",
                ],
                "allowed_output": "review_record_only",
            },
            "validation": {
                "status": "not_run",
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            },
        }

    def _insert_record(self, item: dict[str, Any]) -> dict[str, Any]:
        with self.store.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO code_evolution_records(
                    record_type, status, title, rationale_json, plan_json, validation_json
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    item["record_type"],
                    item["status"],
                    item["title"],
                    json.dumps(item["rationale"], ensure_ascii=False, default=str),
                    json.dumps(item["plan"], ensure_ascii=False, default=str),
                    json.dumps(item["validation"], ensure_ascii=False, default=str),
                ),
            )
            record_id = int(cursor.lastrowid)
        return self.get_record(record_id)

    def _find_active_duplicate(self, record_type: str, title: str) -> dict[str, Any] | None:
        placeholders = ",".join("?" for _ in ACTIVE_STATUSES)
        row = self.store.fetch_one(
            f"""
            SELECT *
            FROM code_evolution_records
            WHERE record_type = ?
              AND title = ?
              AND status IN ({placeholders})
            ORDER BY id DESC
            LIMIT 1
            """,
            (record_type, title, *sorted(ACTIVE_STATUSES)),
        )
        return self._record_model(row) if row else None

    def _review(self, record_id: int, status: str, reviewed_by: str, note: str | None) -> dict[str, Any]:
        reviewed_at = datetime.now().isoformat(timespec="seconds")
        with self.store.connect() as conn:
            conn.execute(
                """
                UPDATE code_evolution_records
                SET status = ?, reviewed_by = ?, review_note = ?, reviewed_at = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (status, reviewed_by, note, reviewed_at, record_id),
            )
        return self.get_record(record_id)

    def _latest_review(self) -> dict[str, Any]:
        row = self.store.fetch_one(
            """
            SELECT *
            FROM experience_reviews
            ORDER BY id DESC
            LIMIT 1
            """
        )
        return self._record_json(row, ["summary_json", "classification_json", "next_actions_json"])

    def _recent_events(self, limit: int = 200) -> list[dict[str, Any]]:
        rows = self.store.fetch_all(
            """
            SELECT *
            FROM experience_events
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [self._record_json(row, ["payload_json"]) for row in rows]

    def _latest_strategy_snapshot(self) -> dict[str, Any]:
        row = self.store.fetch_one(
            """
            SELECT *
            FROM strategy_performance_snapshots
            ORDER BY id DESC
            LIMIT 1
            """
        )
        return self._record_json(row, ["metrics_json"])

    def _count_records(self) -> int:
        row = self.store.fetch_one("SELECT COUNT(*) AS count FROM code_evolution_records")
        return int(row["count"]) if row else 0

    def _validation_passed(self, validation: dict[str, Any]) -> bool:
        if validation.get("passed") is True:
            return True
        commands = validation.get("commands")
        if isinstance(commands, list) and commands:
            return all(command.get("returncode") == 0 for command in commands)
        checks = validation.get("checks")
        if isinstance(checks, dict) and checks:
            return all(bool(value) for value in checks.values())
        return False

    def _record_model(self, row: dict[str, Any]) -> dict[str, Any]:
        item = self._record_json(row, ["rationale_json", "plan_json", "validation_json"])
        item.setdefault("review_only", True)
        item.setdefault("simulation_only", True)
        item.setdefault("live_trading_enabled", settings.enable_live_trading)
        return item

    def _record_json(self, row: dict[str, Any] | None, json_fields: list[str]) -> dict[str, Any]:
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
