from __future__ import annotations

import hashlib
import json
from typing import Any

from app.config import settings
from app.storage.sqlite_store import SQLiteStore


def _json_dumps(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)


def _json_loads(value: str | None, fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


class Dataset2StageService:
    """Small stable Dataset2 entrypoint for stage summaries and training dry-runs."""

    def __init__(self) -> None:
        self.store = SQLiteStore(settings.database_path)
        self.store.init()

    def stage_summary(self, limit: int = 20) -> dict[str, Any]:
        limited = max(1, min(int(limit or 20), 100))
        staging_counts = self.store.fetch_all(
            """
            SELECT status, COUNT(*) AS cnt
            FROM dataset2_staging_records
            GROUP BY status
            ORDER BY cnt DESC, status
            """
        )
        label_counts = self.store.fetch_all(
            """
            SELECT COALESCE(action_label, 'unknown') AS label, COUNT(*) AS cnt
            FROM dataset2_staging_records
            GROUP BY COALESCE(action_label, 'unknown')
            ORDER BY cnt DESC, label
            LIMIT ?
            """,
            (limited,),
        )
        split_counts = self.store.fetch_all(
            """
            SELECT COALESCE(split_tag, 'unknown') AS split_tag, COUNT(*) AS cnt
            FROM dataset2_staging_records
            GROUP BY COALESCE(split_tag, 'unknown')
            ORDER BY cnt DESC, split_tag
            """
        )
        latest_events = self.store.fetch_all(
            """
            SELECT id, event_type, payload_json, created_at
            FROM events
            WHERE event_type LIKE 'dataset2_%'
               OR event_type LIKE 'sim_cockpit_action_%'
               OR event_type = 'sim_cockpit_readback_recorded'
            ORDER BY id DESC
            LIMIT ?
            """,
            (limited,),
        )
        total_staging = sum(int(row.get("cnt") or 0) for row in staging_counts)
        total_sim_actions = int(
            (
                self.store.fetch_one(
                    """
                    SELECT COUNT(*) AS cnt
                    FROM sim_cockpit_actions
                    """
                )
                or {}
            ).get("cnt")
            or 0
        )
        total_readbacks = int(
            (
                self.store.fetch_one(
                    """
                    SELECT COUNT(*) AS cnt
                    FROM sim_cockpit_readbacks
                    """
                )
                or {}
            ).get("cnt")
            or 0
        )
        latest = latest_events[0] if latest_events else None
        summary = {
            "schema_version": "dataset2_stage_summary.v1",
            "status": "empty"
            if total_staging == 0 and total_sim_actions == 0 and total_readbacks == 0
            else "ready_for_review",
            "stage": "dataset2_gate",
            "staging_record_count": total_staging,
            "sim_cockpit_action_count": total_sim_actions,
            "sim_cockpit_readback_count": total_readbacks,
            "staging_counts": staging_counts,
            "label_counts": label_counts,
            "split_counts": split_counts,
            "latest_event": self._hydrate_event(latest) if latest else None,
            "training_allowed": False,
            "dry_run_available": True,
            "model_artifact_write_enabled": False,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }
        return summary

    def training_status(self, limit: int = 200, min_samples: int = 4) -> dict[str, Any]:
        limited = max(1, min(int(limit or 200), 1000))
        minimum = max(2, min(int(min_samples or 4), 100))
        samples = self._sample_candidates(limit=limited)
        prepared = self._prepare_training_samples(samples)
        profile = self._training_profile(prepared, min_samples=minimum)
        latest_run = self.latest_training_run()
        return {
            "schema_version": "dataset2_training_status.v1",
            "stage": "dataset2_controlled_training",
            "status": "ready" if profile["training_allowed"] else "blocked",
            "sample_candidate_count": len(prepared),
            "min_samples": minimum,
            "label_counts": profile["label_counts"],
            "source_counts": profile["source_counts"],
            "status_counts": profile["status_counts"],
            "split": profile["split"],
            "training_allowed": profile["training_allowed"],
            "blocked_reasons": profile["blocked_reasons"],
            "latest_run": latest_run,
            "dry_run_available": True,
            "training_mode": "in_memory_majority_label_baseline",
            "model_artifact_write_enabled": False,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def training_run(
        self,
        limit: int = 200,
        requested_by: str = "operator",
        min_samples: int = 4,
    ) -> dict[str, Any]:
        limited = max(1, min(int(limit or 200), 1000))
        minimum = max(2, min(int(min_samples or 4), 100))
        raw_samples = self._sample_candidates(limit=limited)
        samples = self._prepare_training_samples(raw_samples)
        profile = self._training_profile(samples, min_samples=minimum)
        sample_set_hash = hashlib.sha256(_json_dumps(samples).encode("utf-8")).hexdigest()

        result: dict[str, Any] = {
            "schema_version": "dataset2_training_run.v1",
            "stage": "dataset2_controlled_training",
            "status": "blocked",
            "requested_by": requested_by,
            "sample_candidate_count": len(samples),
            "sample_set_hash": sample_set_hash,
            "min_samples": minimum,
            "training_allowed": profile["training_allowed"],
            "blocked_reasons": profile["blocked_reasons"],
            "label_counts": profile["label_counts"],
            "source_counts": profile["source_counts"],
            "status_counts": profile["status_counts"],
            "split": profile["split"],
            "training_mode": "in_memory_majority_label_baseline",
            "training_executed": False,
            "model_artifact_written": False,
            "writes_learning_samples": False,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

        if profile["training_allowed"]:
            train_samples = profile["train_samples"]
            validation_samples = profile["validation_samples"]
            majority_label = self._majority_label(train_samples)
            correct = sum(1 for item in validation_samples if item["training_label"] == majority_label)
            validation_count = len(validation_samples)
            accuracy = correct / validation_count if validation_count else 0.0
            result.update(
                {
                    "status": "completed",
                    "training_executed": True,
                    "model": {
                        "kind": "majority_label_classifier",
                        "majority_label": majority_label,
                        "feature_policy": "audit_metadata_only",
                        "artifact_written": False,
                    },
                    "metrics": {
                        "train_count": len(train_samples),
                        "validation_count": validation_count,
                        "validation_accuracy": accuracy,
                        "correct_validation_count": correct,
                    },
                }
            )
        else:
            result["metrics"] = {
                "train_count": 0,
                "validation_count": 0,
                "validation_accuracy": None,
                "correct_validation_count": 0,
            }

        with self.store.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO events(event_type, payload_json)
                VALUES (?, ?)
                """,
                ("dataset2_training_run", _json_dumps(result)),
            )
            result["event_id"] = int(cursor.lastrowid)
        return result

    def latest_training_run(self) -> dict[str, Any] | None:
        row = self.store.fetch_one(
            """
            SELECT id, event_type, payload_json, created_at
            FROM events
            WHERE event_type = 'dataset2_training_run'
            ORDER BY id DESC
            LIMIT 1
            """
        )
        return self._hydrate_event(row) if row else None

    def training_dry_run(self, limit: int = 200, requested_by: str = "operator") -> dict[str, Any]:
        limited = max(1, min(int(limit or 200), 1000))
        samples = self._sample_candidates(limit=limited)
        payload_hash = hashlib.sha256(_json_dumps(samples).encode("utf-8")).hexdigest()
        action_counts: dict[str, int] = {}
        status_counts: dict[str, int] = {}
        for sample in samples:
            action_counts[str(sample.get("action") or "unknown")] = action_counts.get(str(sample.get("action") or "unknown"), 0) + 1
            status_counts[str(sample.get("status") or "unknown")] = status_counts.get(str(sample.get("status") or "unknown"), 0) + 1
        result = {
            "schema_version": "dataset2_training_dry_run.v1",
            "status": "completed",
            "sample_candidate_count": len(samples),
            "sample_set_hash": payload_hash,
            "action_counts": action_counts,
            "status_counts": status_counts,
            "training_executed": False,
            "model_artifact_written": False,
            "requested_by": requested_by,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }
        with self.store.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO events(event_type, payload_json)
                VALUES (?, ?)
                """,
                ("dataset2_training_dry_run", _json_dumps(result)),
            )
            result["event_id"] = int(cursor.lastrowid)
        return result

    def _sample_candidates(self, limit: int) -> list[dict[str, Any]]:
        readbacks = self.store.fetch_all(
            """
            SELECT r.id, r.action_id, r.readback_type, r.status, r.symbol, r.price, r.quantity,
                   r.order_id, r.payload_json, r.created_at,
                   a.action_type AS linked_action_type,
                   a.risk_result_json AS linked_risk_result_json,
                   a.execution_json AS linked_execution_json,
                   a.blocked_reasons_json AS linked_blocked_reasons_json
            FROM sim_cockpit_readbacks r
            LEFT JOIN sim_cockpit_actions a ON a.id = r.action_id
            ORDER BY r.id DESC
            LIMIT ?
            """,
            (limit,),
        )
        samples: list[dict[str, Any]] = []
        for row in readbacks:
            payload = _json_loads(row.get("payload_json"), {})
            samples.append(
                {
                    "source": "sim_cockpit_readbacks",
                    "source_id": row["id"],
                    "action_id": row.get("action_id"),
                    "symbol": row.get("symbol"),
                    "action": payload.get("action_type") or row.get("linked_action_type") or row.get("readback_type"),
                    "status": row.get("status"),
                    "price": row.get("price"),
                    "quantity": row.get("quantity"),
                    "order_id": row.get("order_id"),
                    "execution_mode": payload.get("execution_mode"),
                    "risk_result": _json_loads(row.get("linked_risk_result_json"), {}),
                    "execution": _json_loads(row.get("linked_execution_json"), {}),
                    "blocked_reasons": payload.get("blocked_reasons")
                    or _json_loads(row.get("linked_blocked_reasons_json"), []),
                    "created_at": row.get("created_at"),
                }
            )
        if len(samples) >= limit:
            return samples

        remaining_after_readbacks = limit - len(samples)
        sim_actions = self.store.fetch_all(
            """
            SELECT id, action_type, status, symbol, price, quantity,
                   risk_result_json, execution_json, blocked_reasons_json, created_at
            FROM sim_cockpit_actions
            ORDER BY id DESC
            LIMIT ?
            """,
            (remaining_after_readbacks,),
        )
        for row in sim_actions:
            samples.append(
                {
                    "source": "sim_cockpit_actions",
                    "source_id": row["id"],
                    "symbol": row.get("symbol"),
                    "action": row.get("action_type"),
                    "status": row.get("status"),
                    "price": row.get("price"),
                    "quantity": row.get("quantity"),
                    "risk_result": _json_loads(row.get("risk_result_json"), {}),
                    "blocked_reasons": _json_loads(row.get("blocked_reasons_json"), []),
                    "execution": {
                        key: value
                        for key, value in _json_loads(row.get("execution_json"), {}).items()
                        if key
                        in {
                            "executor",
                            "status",
                            "simulated_account_action",
                            "real_screen_click_executed",
                            "simulation_only",
                            "live_trading_enabled",
                        }
                    },
                    "created_at": row.get("created_at"),
                }
            )
        if len(samples) >= limit:
            return samples

        remaining = limit - len(samples)
        staged = self.store.fetch_all(
            """
            SELECT id, pattern_id, action_label, risk_level, split_tag,
                   stock_code, signal_date, status, quality_flags_json, created_at
            FROM dataset2_staging_records
            ORDER BY id DESC
            LIMIT ?
            """,
            (remaining,),
        )
        for row in staged:
            samples.append(
                {
                    "source": "dataset2_staging_records",
                    "source_id": row["id"],
                    "symbol": row.get("stock_code"),
                    "action": row.get("action_label"),
                    "status": row.get("status"),
                    "risk_level": row.get("risk_level"),
                    "split_tag": row.get("split_tag"),
                    "signal_date": row.get("signal_date"),
                    "quality_flags": _json_loads(row.get("quality_flags_json"), []),
                    "created_at": row.get("created_at"),
                }
            )
        return samples

    def _prepare_training_samples(self, samples: list[dict[str, Any]]) -> list[dict[str, Any]]:
        prepared: list[dict[str, Any]] = []
        for item in samples:
            label = self._training_label(item)
            prepared.append(
                {
                    **item,
                    "training_label": label,
                    "model_features": {
                        "source": item.get("source"),
                        "action": item.get("action"),
                        "status": item.get("status"),
                        "risk_level": item.get("risk_level"),
                        "has_symbol": bool(item.get("symbol")),
                        "has_price": item.get("price") is not None,
                        "has_quantity": item.get("quantity") is not None,
                        "blocked_reason_count": len(item.get("blocked_reasons") or []),
                    },
                }
            )
        return sorted(
            prepared,
            key=lambda item: (
                str(item.get("created_at") or ""),
                str(item.get("source") or ""),
                int(item.get("source_id") or 0),
            ),
        )

    def _training_profile(self, samples: list[dict[str, Any]], min_samples: int) -> dict[str, Any]:
        label_counts: dict[str, int] = {}
        source_counts: dict[str, int] = {}
        status_counts: dict[str, int] = {}
        for sample in samples:
            label = str(sample.get("training_label") or "unknown")
            source = str(sample.get("source") or "unknown")
            status = str(sample.get("status") or "unknown")
            label_counts[label] = label_counts.get(label, 0) + 1
            source_counts[source] = source_counts.get(source, 0) + 1
            status_counts[status] = status_counts.get(status, 0) + 1

        split_index = int(len(samples) * 0.7)
        if len(samples) >= 2:
            split_index = max(1, min(split_index, len(samples) - 1))
        train_samples = samples[:split_index]
        validation_samples = samples[split_index:]
        blocked_reasons: list[str] = []
        if settings.enable_live_trading:
            blocked_reasons.append("live_trading_enabled")
        if len(samples) < min_samples:
            blocked_reasons.append("insufficient_samples")
        if len(label_counts) < 2:
            blocked_reasons.append("insufficient_label_diversity")
        if not train_samples or not validation_samples:
            blocked_reasons.append("insufficient_time_split")

        return {
            "label_counts": label_counts,
            "source_counts": source_counts,
            "status_counts": status_counts,
            "split": {
                "policy": "time_ordered_70_30",
                "train_count": len(train_samples),
                "validation_count": len(validation_samples),
            },
            "train_samples": train_samples,
            "validation_samples": validation_samples,
            "blocked_reasons": sorted(set(blocked_reasons)),
            "training_allowed": not blocked_reasons,
        }

    def _training_label(self, sample: dict[str, Any]) -> str:
        if sample.get("source") == "dataset2_staging_records" and sample.get("action"):
            return str(sample["action"])
        status = str(sample.get("status") or "").lower()
        if status in {"executed", "dry_run", "completed", "observed"}:
            return "action_feasible"
        if status in {"blocked", "rejected"}:
            return "blocked_or_rejected"
        if status in {"failed", "error"}:
            return "failed_or_error"
        action = str(sample.get("action") or "").lower()
        if action:
            return action
        return "unknown"

    def _majority_label(self, samples: list[dict[str, Any]]) -> str:
        counts: dict[str, int] = {}
        for item in samples:
            label = str(item.get("training_label") or "unknown")
            counts[label] = counts.get(label, 0) + 1
        if not counts:
            return "unknown"
        return sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))[0][0]

    def _hydrate_event(self, row: dict[str, Any] | None) -> dict[str, Any] | None:
        if not row:
            return None
        payload = _json_loads(row.get("payload_json"), {})
        if isinstance(payload, dict) and "event_id" not in payload:
            payload = {**payload, "event_id": row["id"]}
        return {
            "id": row["id"],
            "event_type": row["event_type"],
            "payload": payload,
            "created_at": row.get("created_at"),
        }
