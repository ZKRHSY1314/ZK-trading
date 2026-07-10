"""Agent Learning Extraction Service.

Converts completed safe agent-control tasks into structured learning samples
for training and evaluation. This is observation-only data — no live trading,
no order placement, no credential storage.
"""

import json
from typing import Any

from app.config import settings
from app.models import AgentLearningSample, AgentLearningSummary
from app.storage.sqlite_store import SQLiteStore


# Task types that produce per-item samples (one sample per candidate/event)
_PER_ITEM_TASK_TYPES = {
    "potential_search",
    "offhour_potential_search",
    "auto_discovery_scan",
    "monitoring_run",
    "full_simulation_cycle",
}
# Task types that produce a single system-health sample (no stock symbol)
_SYSTEM_TASK_TYPES = {
    "local_dashboard_observation",
    "public_opinion_capture",
}

# Statuses that should be skipped entirely
_SKIP_STATUSES = {"blocked", "rejected", "failed", "pending"}


class AgentLearningExtractionService:
    """Extract learning samples from completed agent-control tasks."""

    def __init__(self, store: SQLiteStore | None = None) -> None:
        self.store = store or SQLiteStore(settings.database_path)
        self.store.init()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract_from_task(self, task_id: int) -> dict[str, Any]:
        """Extract learning samples from a single completed task.

        Returns a dict with created_count and skipped reasons.
        """
        task = self._fetch_task(task_id)
        if task is None:
            return {"task_id": task_id, "created_count": 0, "error": "task_not_found"}

        skip_reason = self._should_skip(task)
        if skip_reason:
            result = {"task_id": task_id, "created_count": 0, "skipped": skip_reason}
            if str(task.get("status") or "").lower() != "pending":
                self._mark_task_processed(task_id, result)
            return result

        samples = self._extract_samples(task)
        created = self._persist_samples_strict(samples)
        result = {
            "task_id": task_id,
            "task_type": task["task_type"],
            "created_count": created,
            "total_extracted": len(samples),
        }
        self._mark_task_processed(task_id, result)
        return result

    def extract_from_recent(self, limit: int = 20) -> dict[str, Any]:
        """Extract learning samples from recent completed tasks."""
        limit = max(1, min(limit, 200))
        rows = self.store.fetch_all(
            """
            SELECT task.id
            FROM agent_control_tasks task
            WHERE task.status = 'completed'
              AND NOT EXISTS (
                  SELECT 1
                  FROM agent_control_events event
                  WHERE event.task_id = task.id
                    AND event.event_type = 'learning_extraction_processed'
              )
            ORDER BY task.id ASC
            LIMIT ?
            """,
            (limit,),
        )
        results = []
        total_created = 0
        for row in rows:
            result = self.extract_from_task(row["id"])
            total_created += result.get("created_count", 0)
            results.append(result)

        return {
            "tasks_processed": len(results),
            "total_created": total_created,
            "details": results,
        }

    def _mark_task_processed(self, task_id: int, result: dict[str, Any]) -> None:
        with self.store.connect() as conn:
            conn.execute(
                """
                INSERT INTO agent_control_events(task_id, event_type, message, metadata_json)
                SELECT ?, 'learning_extraction_processed', ?, ?
                WHERE NOT EXISTS (
                    SELECT 1 FROM agent_control_events
                    WHERE task_id = ? AND event_type = 'learning_extraction_processed'
                )
                """,
                (
                    task_id,
                    "Learning extraction processed",
                    json.dumps(result, ensure_ascii=False, default=str),
                    task_id,
                ),
            )

    def list_samples(
        self,
        sample_type: str | None = None,
        symbol: str | None = None,
        label: str | None = None,
        limit: int = 50,
    ) -> list[AgentLearningSample]:
        """List agent learning samples with optional filters."""
        clauses: list[str] = []
        params: list[Any] = []
        if sample_type:
            clauses.append("sample_type = ?")
            params.append(sample_type)
        if symbol:
            clauses.append("symbol = ?")
            params.append(symbol)
        if label:
            clauses.append("label = ?")
            params.append(label)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        limit = max(1, min(limit, 500))
        params.append(limit)
        rows = self.store.fetch_all(
            f"""
            SELECT * FROM agent_learning_samples
            {where}
            ORDER BY id DESC
            LIMIT ?
            """,
            tuple(params),
        )
        return [self._to_model(row) for row in rows]

    def summary(self) -> AgentLearningSummary:
        """Summary counts by sample_type and label."""
        total_row = self.store.fetch_one(
            "SELECT COUNT(*) AS cnt FROM agent_learning_samples"
        )
        total = int(total_row["cnt"]) if total_row else 0

        type_rows = self.store.fetch_all(
            """
            SELECT sample_type, COUNT(*) AS cnt
            FROM agent_learning_samples
            GROUP BY sample_type
            ORDER BY cnt DESC
            """
        )
        by_type = {row["sample_type"]: int(row["cnt"]) for row in type_rows}

        label_rows = self.store.fetch_all(
            """
            SELECT COALESCE(label, 'unlabeled') AS lbl, COUNT(*) AS cnt
            FROM agent_learning_samples
            GROUP BY lbl
            ORDER BY cnt DESC
            """
        )
        by_label = {row["lbl"]: int(row["cnt"]) for row in label_rows}

        return AgentLearningSummary(
            total_count=total,
            by_sample_type=by_type,
            by_label=by_label,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _fetch_task(self, task_id: int) -> dict[str, Any] | None:
        return self.store.fetch_one(
            "SELECT * FROM agent_control_tasks WHERE id = ?", (task_id,)
        )

    def _should_skip(self, task: dict[str, Any]) -> str | None:
        status = task.get("status", "")
        if status in _SKIP_STATUSES:
            return f"status_{status}"
        approval = task.get("approval_status", "")
        if approval in ("blocked", "rejected"):
            return f"approval_{approval}"
        if status != "completed":
            return f"not_completed_{status}"
        return None

    def _extract_samples(self, task: dict[str, Any]) -> list[dict[str, Any]]:
        task_type = task.get("task_type", "")
        result = json.loads(task.get("result_json") or "{}")
        task_id = task["id"]

        approval_meta = {
            "approval_status": task.get("approval_status"),
            "approved_by": task.get("approved_by"),
            "approved_at": task.get("approved_at"),
            "requested_by": task.get("requested_by"),
        }

        if task_type in ("potential_search", "offhour_potential_search"):
            return self._samples_from_potential_search(task_id, task_type, result, approval_meta)
        elif task_type == "auto_discovery_scan":
            return self._samples_from_auto_discovery(task_id, result, approval_meta)
        elif task_type == "monitoring_run":
            return self._samples_from_monitoring(task_id, result, approval_meta)
        elif task_type == "local_dashboard_observation":
            return self._samples_from_dashboard_observation(task_id, result, approval_meta)
        elif task_type == "full_simulation_cycle":
            return self._samples_from_full_simulation_cycle(
                task_id, result, approval_meta
            )
        elif task_type == "public_opinion_capture":
            return self._samples_from_public_opinion_capture(
                task_id, result, approval_meta
            )
        return []

    def _samples_from_potential_search(
        self, task_id: int, task_type: str, result: dict, approval_meta: dict
    ) -> list[dict[str, Any]]:
        samples = []
        items = result.get("top_scored_items") or result.get("items") or []
        for item in items:
            symbol = item.get("symbol")
            if not symbol:
                continue
            risk_flags = []
            if item.get("lifecycle_state") == "phase_guarded":
                risk_flags.append("phase_guarded")
            if item.get("lifecycle_state") == "rejected":
                risk_flags.append("rejected_lifecycle")

            samples.append({
                "source_task_id": task_id,
                "sample_type": task_type,
                "symbol": symbol,
                "name": item.get("name"),
                "features": {
                    "signal_date": item.get("signal_date") or item.get("trade_date"),
                    "current_price": item.get("current_price"),
                    "pct_change": item.get("pct_change"),
                    "turnover_rate": item.get("turnover_rate"),
                    "amount": item.get("amount"),
                    "potential_score": item.get("potential_score"),
                    "lifecycle_state": item.get("lifecycle_state"),
                    "reasons": item.get("reasons", []),
                    "components": item.get("components", {}),
                },
                "decision": {
                    "source": item.get("source", task_type),
                    "approval": approval_meta,
                },
                "risk_flags": risk_flags,
                "label": self._infer_label(item),
                "label_source": "auto_extraction",
            })
        return samples

    def _samples_from_auto_discovery(
        self, task_id: int, result: dict, approval_meta: dict
    ) -> list[dict[str, Any]]:
        samples = []
        items = result.get("items") or []
        for item in items:
            symbol = item.get("symbol")
            if not symbol:
                continue
            risk_flags = []
            discovery_type = item.get("discovery_type", "")
            if discovery_type == "limit_up":
                risk_flags.append("limit_up_chasing_risk")

            samples.append({
                "source_task_id": task_id,
                "sample_type": "auto_discovery_scan",
                "symbol": symbol,
                "name": item.get("name"),
                "features": {
                    "discovery_type": discovery_type,
                    "priority": item.get("priority"),
                    "pct_change": item.get("pct_change"),
                    "current_price": item.get("current_price"),
                    "turnover_rate": item.get("turnover_rate"),
                    "amount": item.get("amount"),
                    "reasons": item.get("reasons", []),
                },
                "decision": {
                    "source": "auto_discovery",
                    "approval": approval_meta,
                },
                "risk_flags": risk_flags,
                "label": "discovered",
                "label_source": "auto_extraction",
            })
        return samples

    def _samples_from_monitoring(
        self, task_id: int, result: dict, approval_meta: dict
    ) -> list[dict[str, Any]]:
        samples = []
        events = result.get("events") or []
        for event in events:
            symbol = event.get("symbol")
            if not symbol:
                continue
            risk_flags = []
            signal = event.get("signal", "")
            if signal == "risk_blocked":
                risk_flags.append("risk_blocked")
            if not event.get("allowed", False):
                risk_flags.append("sim_not_allowed")

            samples.append({
                "source_task_id": task_id,
                "sample_type": "monitoring_run",
                "symbol": symbol,
                "name": event.get("name"),
                "features": {
                    "price": event.get("price"),
                    "pct_change": event.get("pct_change"),
                    "signal": signal,
                    "action": event.get("action"),
                    "allowed": event.get("allowed"),
                    "summary": event.get("summary"),
                },
                "decision": {
                    "signal": signal,
                    "action": event.get("action"),
                    "allowed": event.get("allowed"),
                    "approval": approval_meta,
                },
                "risk_flags": risk_flags,
                "label": self._monitoring_label(event),
                "label_source": "auto_extraction",
            })

        # Also extract alerts if present
        alerts = result.get("alerts") or []
        for alert in alerts:
            symbol = alert.get("symbol")
            if not symbol:
                continue
            # Alerts are separate monitoring samples
            samples.append({
                "source_task_id": task_id,
                "sample_type": "monitoring_alert",
                "symbol": symbol,
                "name": None,
                "features": {
                    "severity": alert.get("severity"),
                    "alert_type": alert.get("alert_type"),
                    "message": alert.get("message"),
                },
                "decision": {
                    "alert_type": alert.get("alert_type"),
                    "approval": approval_meta,
                },
                "risk_flags": [alert.get("severity", "info")],
                "label": f"alert_{alert.get('alert_type', 'unknown')}",
                "label_source": "auto_extraction",
            })
        return samples

    def _samples_from_dashboard_observation(
        self, task_id: int, result: dict, approval_meta: dict
    ) -> list[dict[str, Any]]:
        risk_flags = []
        if not result.get("dashboard_reachable", False):
            risk_flags.append("dashboard_unreachable")
        health = result.get("backend_health") or {}
        if health.get("live_trading_enabled", False):
            risk_flags.append("live_trading_detected")

        return [{
            "source_task_id": task_id,
            "sample_type": "local_dashboard_observation",
            "symbol": None,
            "name": None,
            "features": {
                "dashboard_reachable": result.get("dashboard_reachable"),
                "status_code": result.get("status_code"),
                "html_bytes": result.get("html_bytes"),
                "app_root_present": result.get("app_root_present"),
                "checked_at": result.get("checked_at"),
                "backend_health": health,
            },
            "decision": {
                "source": "dashboard_observation",
                "approval": approval_meta,
            },
            "risk_flags": risk_flags,
            "label": "system_healthy" if result.get("dashboard_reachable") else "system_degraded",
            "label_source": "auto_extraction",
        }]

    def _samples_from_full_simulation_cycle(
        self,
        task_id: int,
        result: dict[str, Any],
        approval_meta: dict[str, Any],
    ) -> list[dict[str, Any]]:
        automation = result.get("automation") or {}
        run_id = automation.get("run_id") or result.get("automation_run_id")
        event_payloads: list[dict[str, Any]] = []
        if run_id is not None:
            rows = self.store.fetch_all(
                """
                SELECT symbol, payload_json, created_at
                FROM automation_events
                WHERE run_id = ? AND event_type = 'simulation_plan_created'
                ORDER BY id
                """,
                (run_id,),
            )
            for row in rows:
                payload = self._json_object(row.get("payload_json"))
                if row.get("symbol") and not payload.get("symbol"):
                    payload["symbol"] = row["symbol"]
                payload.setdefault("event_created_at", row.get("created_at"))
                event_payloads.append(payload)

        if not event_payloads:
            summary = automation.get("summary") or result.get("summary") or {}
            event_payloads = [
                {**item, "symbol": item.get("symbol")}
                for item in summary.get("items") or []
                if isinstance(item, dict) and item.get("symbol")
            ]

        samples: list[dict[str, Any]] = []
        seen_symbols: set[str] = set()
        for payload in event_payloads:
            candidate = payload.get("candidate") or {}
            snapshot = payload.get("snapshot") or {}
            decision = payload.get("decision") or {}
            plan = payload.get("plan") or payload
            symbol = (
                payload.get("symbol")
                or snapshot.get("symbol")
                or candidate.get("symbol")
                or plan.get("symbol")
            )
            if not symbol or symbol in seen_symbols:
                continue
            seen_symbols.add(str(symbol))
            risk_blocks = payload.get("risk_blocked") or plan.get("risk_blocked") or []
            risk_flags = self._risk_flags_from_blocks(risk_blocks)
            allowed = bool(plan.get("allowed", payload.get("allowed", False)))
            signal_date = snapshot.get("trade_date") or payload.get("signal_date")
            samples.append(
                {
                    "source_task_id": task_id,
                    "sample_type": "full_simulation_cycle",
                    "symbol": str(symbol),
                    "name": snapshot.get("name") or candidate.get("name"),
                    "features": {
                        "signal_date": signal_date,
                        "snapshot": snapshot,
                        "candidate": candidate,
                        "decision_score": decision.get("score"),
                        "decision_raw_score": decision.get("raw_score"),
                        "decision_max_score": decision.get("max_score"),
                        "tier": decision.get("tier") or payload.get("tier"),
                        "action": plan.get("action") or payload.get("action"),
                        "allowed": allowed,
                        "automation_run_id": run_id,
                    },
                    "decision": {
                        "decision": decision,
                        "plan": plan,
                        "approval": approval_meta,
                    },
                    "risk_flags": risk_flags,
                    "label": (
                        "simulation_plan_created"
                        if allowed
                        else "simulation_plan_blocked"
                    ),
                    "label_source": "automation_plan_status",
                }
            )
        return samples

    def _samples_from_public_opinion_capture(
        self,
        task_id: int,
        result: dict[str, Any],
        approval_meta: dict[str, Any],
    ) -> list[dict[str, Any]]:
        sectors = [
            item
            for item in result.get("sector_signals") or []
            if isinstance(item, dict)
        ]
        sectors.sort(
            key=lambda item: (
                -float(item.get("heat_score") or 0),
                str(item.get("sector") or ""),
            )
        )
        risk_flags = [
            f"sector_risk:{item.get('sector')}"
            for item in sectors
            if int(item.get("risk_count") or 0) > 0
            or item.get("suggested_action") == "risk_review_only"
        ]
        return [
            {
                "source_task_id": task_id,
                "sample_type": "public_opinion_capture",
                "symbol": None,
                "name": "market_sector_context",
                "features": {
                    "run_id": result.get("run_id"),
                    "status": result.get("status"),
                    "source_count": result.get("source_count"),
                    "item_count": result.get("item_count"),
                    "sector_count": result.get("sector_count"),
                    "top_sectors": sectors[:20],
                    "error_count": len(result.get("errors") or []),
                    "review_only": result.get("review_only", True),
                    "simulation_only": result.get("simulation_only", True),
                },
                "decision": {
                    "summary": result.get("summary") or {},
                    "next_action": result.get("next_action"),
                    "approval": approval_meta,
                },
                "risk_flags": risk_flags,
                "label": (
                    "sector_context_ready" if sectors else "sector_context_empty"
                ),
                "label_source": "public_opinion_context",
            }
        ]

    def _risk_flags_from_blocks(self, blocks: Any) -> list[str]:
        flags: list[str] = []
        if not isinstance(blocks, list):
            return flags
        for block in blocks:
            if isinstance(block, dict):
                value = (
                    block.get("rule_id")
                    or block.get("code")
                    or block.get("reason")
                )
            else:
                value = block
            if value:
                flags.append(str(value))
        return list(dict.fromkeys(flags))

    def _json_object(self, raw: Any) -> dict[str, Any]:
        if isinstance(raw, dict):
            return raw
        try:
            parsed = json.loads(raw or "{}")
        except (json.JSONDecodeError, TypeError):
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def _infer_label(self, item: dict[str, Any]) -> str:
        """Infer a label for a potential search or scored item."""
        score = float(item.get("potential_score") or 0)
        state = item.get("lifecycle_state", "")
        if state in ("rejected", "phase_guarded"):
            return "risk_flagged"
        if score >= 20:
            return "high_potential"
        if score >= 10:
            return "moderate_potential"
        return "low_potential"

    def _monitoring_label(self, event: dict[str, Any]) -> str:
        signal = event.get("signal", "")
        allowed = event.get("allowed", False)
        if signal == "risk_blocked":
            return "risk_blocked"
        if allowed:
            return "sim_buy_signal"
        return f"signal_{signal}" if signal else "observed"

    def _persist_samples(self, samples: list[dict[str, Any]]) -> int:
        """Persist samples with idempotent upsert.

        Uses INSERT OR IGNORE with the UNIQUE index on
        (source_task_id, sample_type, symbol) for dedup.
        """
        created = 0
        with self.store.connect() as conn:
            for sample in samples:
                try:
                    conn.execute(
                        """
                        INSERT INTO agent_learning_samples (
                            source_task_id, sample_type, symbol, name,
                            features_json, decision_json, risk_flags_json,
                            label, label_source
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            sample["source_task_id"],
                            sample["sample_type"],
                            sample.get("symbol"),
                            sample.get("name"),
                            json.dumps(sample.get("features", {}), ensure_ascii=False, default=str),
                            json.dumps(sample.get("decision", {}), ensure_ascii=False, default=str),
                            json.dumps(sample.get("risk_flags", []), ensure_ascii=False),
                            sample.get("label"),
                            sample.get("label_source"),
                        ),
                    )
                    created += 1
                except Exception:
                    # UNIQUE constraint violation → duplicate, skip
                    pass
        return created

    def _persist_samples_strict(self, samples: list[dict[str, Any]]) -> int:
        """Persist samples idempotently without hiding non-dedup database errors."""
        created = 0
        with self.store.connect() as conn:
            for sample in samples:
                cursor = conn.execute(
                    """
                    INSERT OR IGNORE INTO agent_learning_samples (
                        source_task_id, sample_type, symbol, name,
                        features_json, decision_json, risk_flags_json,
                        label, label_source
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        sample["source_task_id"],
                        sample["sample_type"],
                        sample.get("symbol"),
                        sample.get("name"),
                        json.dumps(sample.get("features", {}), ensure_ascii=False, default=str),
                        json.dumps(sample.get("decision", {}), ensure_ascii=False, default=str),
                        json.dumps(sample.get("risk_flags", []), ensure_ascii=False),
                        sample.get("label"),
                        sample.get("label_source"),
                    ),
                )
                created += int(cursor.rowcount or 0)
        return created

    def _to_model(self, row: dict[str, Any]) -> AgentLearningSample:
        return AgentLearningSample(
            id=row["id"],
            source_task_id=row["source_task_id"],
            sample_type=row["sample_type"],
            symbol=row.get("symbol"),
            name=row.get("name"),
            features=json.loads(row.get("features_json") or "{}"),
            decision=json.loads(row.get("decision_json") or "{}"),
            risk_flags=json.loads(row.get("risk_flags_json") or "[]"),
            label=row.get("label"),
            label_source=row.get("label_source"),
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
        )
