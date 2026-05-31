from __future__ import annotations

import ast
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from app.config import settings
from app.storage.sqlite_store import SQLiteStore


ALLOWED_ACTION_LABELS = {
    "SIM_BUY_CANDIDATE",
    "HOLD_OR_TRAIL",
    "REDUCE_OR_EXIT",
    "AVOID_OR_WAIT",
    "WAIT_CONFIRMATION",
    "RISK_ALERT",
    "NO_TRADE",
}
ALLOWED_RISK_LEVELS = {"low", "medium", "high"}
RISK_NORMALIZATION = {
    "low_to_medium": "medium",
    "medium_to_high": "high",
    "medium_high": "high",
}
LIST_FIELDS = {
    "market_phase",
    "preconditions",
    "observable_features",
    "trigger_conditions",
    "confirmation_signals",
    "negative_filters",
    "invalidation_conditions",
    "software_tags",
}
EVIDENCE_FIELDS = {
    "evidence_summary",
    "trigger_conditions",
    "negative_filters",
    "invalidation_conditions",
}
HISTORICAL_OUTCOME_FIELDS = {
    "stock_code",
    "signal_date",
    "entry_price",
    "exit_price",
    "forward_return_5d",
    "max_favorable_excursion",
    "max_adverse_excursion",
    "benchmark_return",
    "split_tag",
}
LOW_SUPPORT_ACTION_THRESHOLD = 5


class Dataset2TrainingReadinessService:
    """Read-only quality gate before dataset2 can be used for training."""

    stage = "V5.6-P6"
    import_queue_event_type = "dataset2_import_queue_review"
    staging_import_event_type = "dataset2_staging_import"
    staging_quality_review_event_type = "dataset2_staging_quality_review"
    staging_fix_plan_event_type = "dataset2_staging_fix_plan"
    staging_fix_plan_approval_event_type = "dataset2_staging_fix_plan_approval"
    staging_fix_preflight_event_type = "dataset2_staging_fix_preflight"

    def readiness(self, source_dir: str | None = None, limit: int = 500) -> dict[str, Any]:
        pack = self._locate_pack(source_dir)
        if pack is None:
            return self._missing_dataset_response(source_dir)

        records = self._read_jsonl(pack / "dataset" / "all_training_patterns.jsonl", limit=limit)
        check_report = self._read_json(pack / "validation" / "check_report.json")
        manifest = self._read_json(pack / "validation" / "manifest.json")
        schema = self._read_json(pack / "schemas" / "pattern_schema.json")
        analysis = self._analyze(records)
        gates = self._gates(analysis, records)
        blocked = [gate for gate in gates if gate["status"] == "blocked"]
        warnings = [gate for gate in gates if gate["status"] == "warning"]

        return {
            "schema_version": "dataset2_training_readiness.v1",
            "stage": self.stage,
            "status": "training_blocked_cleanup_required" if blocked else "training_readiness_review_passed",
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "source_dir": str(pack),
            "dataset_version": self._dataset_version(records, check_report),
            "record_count": len(records),
            "data_hash": self._file_hash(pack / "dataset" / "all_training_patterns.jsonl"),
            "manifest_status": manifest.get("status") or check_report.get("status") or "unknown",
            "schema_title": schema.get("title", "unknown"),
            "counts": {
                "action_labels": dict(analysis["action_counts"]),
                "risk_levels": dict(analysis["risk_counts"]),
                "categories": dict(analysis["category_counts"]),
                "sources": dict(analysis["source_counts"]),
            },
            "quality": {
                "invalid_risk_level_count": len(analysis["invalid_risk_levels"]),
                "invalid_action_label_count": len(analysis["invalid_action_labels"]),
                "stringified_list_item_count": analysis["stringified_list_item_count"],
                "missing_evidence_counts": dict(analysis["missing_evidence_counts"]),
                "empty_rule_logic_count": analysis["empty_rule_logic_count"],
                "empty_training_notes_count": analysis["empty_training_notes_count"],
                "missing_historical_outcome_field_counts": dict(analysis["missing_historical_outcome_field_counts"]),
                "unsafe_model_target_count": len(analysis["unsafe_model_targets"]),
                "low_support_action_labels": analysis["low_support_action_labels"],
            },
            "examples": {
                "invalid_risk_levels": analysis["invalid_risk_levels"][:10],
                "invalid_action_labels": analysis["invalid_action_labels"][:10],
                "stringified_list_items": analysis["stringified_list_items"][:10],
                "unsafe_model_targets": analysis["unsafe_model_targets"][:10],
            },
            "gates": gates,
            "decision": {
                "can_use_as_rule_knowledge": len(analysis["unsafe_model_targets"]) == 0 and bool(records),
                "can_import_normalized_preview": bool(records),
                "training_gate_passed": not blocked,
                "can_start_training_now": False,
                "training_blocked_reason_count": len(blocked),
                "warning_count": len(warnings),
                "next_required_action": (
                    "clean_dataset2_schema_and_evidence_before_training"
                    if blocked
                    else "manual_review_before_training_freeze"
                ),
            },
            "safety_summary": self._safety_summary(),
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def normalized_preview(
        self,
        source_dir: str | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        pack = self._locate_pack(source_dir)
        if pack is None:
            return self._missing_dataset_response(source_dir)

        safe_limit = max(1, min(limit, 100))
        records = self._read_jsonl(pack / "dataset" / "all_training_patterns.jsonl", limit=safe_limit)
        normalized = [self._normalize_record(record) for record in records]
        return {
            "schema_version": "dataset2_normalized_preview.v1",
            "stage": self.stage,
            "status": "normalized_preview_ready",
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "source_dir": str(pack),
            "preview_count": len(normalized),
            "records": normalized,
            "decision": {
                "writes_database_now": False,
                "training_started_now": False,
                "allowed_output": "review_only_normalized_dataset2_preview",
                "next_required_action": "review_readiness_gate_before_any_import_or_training",
            },
            "safety_summary": self._safety_summary(),
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def cleanup_package(
        self,
        source_dir: str | None = None,
        limit: int = 1000,
    ) -> dict[str, Any]:
        pack = self._locate_pack(source_dir)
        if pack is None:
            return self._missing_dataset_response(source_dir)

        safe_limit = max(1, min(limit, 1000))
        source_path = pack / "dataset" / "all_training_patterns.jsonl"
        records = self._read_jsonl(source_path, limit=safe_limit)
        normalized = [self._normalize_record(record) for record in records]
        analysis = self._analyze(records)
        cleanup_actions = self._cleanup_actions(analysis)
        normalized_hash = self._normalized_records_hash(normalized)
        source_hash = self._file_hash(source_path)
        package_id = self._stable_hash(
            {
                "source_hash": source_hash,
                "normalized_hash": normalized_hash,
                "record_count": len(records),
                "cleanup_actions": cleanup_actions,
            }
        )

        blocking_action_count = sum(1 for action in cleanup_actions if action["status"] == "blocked")
        review_action_count = sum(1 for action in cleanup_actions if action["status"] != "passed")
        return {
            "schema_version": "dataset2_cleanup_package.v1",
            "stage": self.stage,
            "status": "cleanup_package_ready_for_review" if records else "dataset2_not_found",
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "source_dir": str(pack),
            "package_id": package_id,
            "record_count": len(records),
            "source_data_hash": source_hash,
            "normalized_records_hash": normalized_hash,
            "summary": {
                "risk_level_change_count": len(analysis["invalid_risk_levels"]),
                "stringified_list_item_count": analysis["stringified_list_item_count"],
                "missing_evidence_total": sum(analysis["missing_evidence_counts"].values()),
                "missing_historical_outcome_total": sum(
                    analysis["missing_historical_outcome_field_counts"].values()
                ),
                "low_support_action_label_count": len(analysis["low_support_action_labels"]),
                "unsafe_model_target_count": len(analysis["unsafe_model_targets"]),
                "review_action_count": review_action_count,
                "blocking_action_count": blocking_action_count,
            },
            "cleanup_actions": cleanup_actions,
            "normalized_records_preview": normalized[: min(20, len(normalized))],
            "gates": [
                self._gate("source_dataset_mutation", "passed", False, False, "source dataset files are not modified"),
                self._gate("file_export", "passed", False, False, "API returns package only; no file is written"),
                self._gate("database_write", "passed", False, False, "normalized records are not persisted in V5.6-P1"),
                self._gate("training_start", "passed", False, False, "training remains blocked until a later reviewed stage"),
                self._gate(
                    "cleanup_review",
                    "blocked" if blocking_action_count else "warning",
                    review_action_count,
                    0,
                    "operator review is required before import, export, or training",
                ),
            ],
            "decision": {
                "cleanup_package_ready": bool(records),
                "cleanup_can_be_applied_automatically": False,
                "can_export_file_now": False,
                "can_import_to_database_now": False,
                "can_start_training_now": False,
                "next_required_action": "review_cleanup_package_then_create_separate_dataset2_import_stage",
            },
            "safety_summary": self._safety_summary(),
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def create_import_queue_review(
        self,
        source_dir: str | None = None,
        limit: int = 1000,
        reviewed_by: str = "operator",
        note: str | None = None,
    ) -> dict[str, Any]:
        cleanup = self.cleanup_package(source_dir=source_dir, limit=limit)
        if cleanup.get("status") == "dataset2_not_found":
            return cleanup

        action_summaries = [
            {
                "name": action.get("name"),
                "status": action.get("status"),
                "count": action.get("count", 0),
            }
            for action in cleanup.get("cleanup_actions", [])
        ]
        payload = {
            "schema_version": "dataset2_import_queue_review.v1",
            "stage": self.stage,
            "status": "import_queue_review_recorded",
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "package_id": cleanup.get("package_id"),
            "source_data_hash": cleanup.get("source_data_hash"),
            "normalized_records_hash": cleanup.get("normalized_records_hash"),
            "record_count": cleanup.get("record_count", 0),
            "summary": cleanup.get("summary", {}),
            "cleanup_actions": action_summaries,
            "review": {
                "reviewed_by": reviewed_by or "operator",
                "note": note,
                "review_only": True,
                "simulation_only": True,
                "source_records_included": False,
                "normalized_records_included": False,
            },
            "decision": {
                "writes_existing_event_now": True,
                "normalized_records_persisted": False,
                "training_started_now": False,
                "can_import_to_database_now": False,
                "can_start_training_now": False,
                "next_required_action": "manual_review_import_queue_metadata_before_any_dataset2_import",
            },
            "safety_summary": self._safety_summary(writes_existing_event_now=True),
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }
        store = SQLiteStore(settings.database_path)
        store.init()
        with store.connect() as conn:
            cursor = conn.execute(
                "INSERT INTO events (event_type, payload_json) VALUES (?, ?)",
                (self.import_queue_event_type, json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)),
            )
            event_id = int(cursor.lastrowid)
        return {
            **payload,
            "event_id": event_id,
            "stored_in": "events",
            "normalized_records_preview": None,
        }

    def list_import_queue_reviews(self, limit: int = 20) -> list[dict[str, Any]]:
        store = SQLiteStore(settings.database_path)
        store.init()
        rows = store.fetch_all(
            """
            SELECT id, event_type, payload_json, created_at
            FROM events
            WHERE event_type = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (self.import_queue_event_type, max(1, min(limit, 100))),
        )
        reviews: list[dict[str, Any]] = []
        for row in rows:
            payload = json.loads(row.pop("payload_json") or "{}")
            reviews.append(
                {
                    "id": row["id"],
                    "event_type": row["event_type"],
                    "created_at": row["created_at"],
                    **payload,
                }
            )
        return reviews

    def import_reviewed_to_staging(
        self,
        source_dir: str | None = None,
        limit: int = 1000,
        review_event_id: int | None = None,
        imported_by: str = "operator",
        note: str | None = None,
    ) -> dict[str, Any]:
        pack = self._locate_pack(source_dir)
        if pack is None:
            return self._missing_dataset_response(source_dir)

        safe_limit = max(1, min(limit, 1000))
        source_path = pack / "dataset" / "all_training_patterns.jsonl"
        records = self._read_jsonl(source_path, limit=safe_limit)
        normalized = [self._normalize_record(record) for record in records]
        source_hash = self._file_hash(source_path)
        normalized_hash = self._normalized_records_hash(normalized)
        cleanup_actions = self._cleanup_actions(self._analyze(records))
        package_id = self._stable_hash(
            {
                "source_hash": source_hash,
                "normalized_hash": normalized_hash,
                "record_count": len(records),
                "cleanup_actions": cleanup_actions,
            }
        )
        store = SQLiteStore(settings.database_path)
        store.init()
        review = self._matching_import_queue_review(
            store=store,
            package_id=package_id,
            normalized_records_hash=normalized_hash,
            review_event_id=review_event_id,
        )
        if review is None:
            return {
                "schema_version": "dataset2_staging_import.v1",
                "stage": self.stage,
                "status": "import_blocked_missing_review",
                "generated_at": datetime.now().isoformat(timespec="seconds"),
                "package_id": package_id,
                "record_count": len(records),
                "source_data_hash": source_hash,
                "normalized_records_hash": normalized_hash,
                "imported_count": 0,
                "decision": {
                    "writes_database_now": False,
                    "writes_staging_records_now": False,
                    "writes_learning_samples_now": False,
                    "normalized_records_persisted_to_staging": False,
                    "normalized_records_persisted_to_training": False,
                    "training_started_now": False,
                    "can_start_training_now": False,
                    "next_required_action": "record_dataset2_import_queue_review_before_staging_import",
                },
                "safety_summary": self._safety_summary(),
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            }

        now = datetime.now().isoformat(timespec="seconds")
        with store.connect() as conn:
            conn.execute("DELETE FROM dataset2_staging_records WHERE package_id = ?", (package_id,))
            for record in normalized:
                conn.execute(
                    """
                    INSERT INTO dataset2_staging_records (
                        package_id, source_data_hash, normalized_records_hash,
                        pattern_id, action_label, risk_level, split_tag, stock_code, signal_date,
                        normalized_json, quality_flags_json, cleanup_operations_json,
                        review_event_id, status, imported_by, import_note, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        package_id,
                        source_hash,
                        normalized_hash,
                        str(record.get("pattern_id") or ""),
                        record.get("action_label"),
                        record.get("risk_level"),
                        record.get("split_tag"),
                        record.get("stock_code"),
                        record.get("signal_date"),
                        json.dumps(record, ensure_ascii=False, sort_keys=True, default=str),
                        json.dumps(record.get("quality_flags") or [], ensure_ascii=False, sort_keys=True, default=str),
                        json.dumps(record.get("cleanup_operations") or [], ensure_ascii=False, sort_keys=True, default=str),
                        review["id"],
                        "staged_review_only",
                        imported_by or "operator",
                        note,
                        now,
                    ),
                )
            payload = {
                "schema_version": "dataset2_staging_import_event.v1",
                "stage": self.stage,
                "status": "staging_import_recorded",
                "package_id": package_id,
                "source_data_hash": source_hash,
                "normalized_records_hash": normalized_hash,
                "record_count": len(normalized),
                "review_event_id": review["id"],
                "imported_by": imported_by or "operator",
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            }
            cursor = conn.execute(
                "INSERT INTO events (event_type, payload_json) VALUES (?, ?)",
                (self.staging_import_event_type, json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)),
            )
            event_id = int(cursor.lastrowid)

        return {
            "schema_version": "dataset2_staging_import.v1",
            "stage": self.stage,
            "status": "staging_import_recorded",
            "generated_at": now,
            "package_id": package_id,
            "source_data_hash": source_hash,
            "normalized_records_hash": normalized_hash,
            "record_count": len(normalized),
            "imported_count": len(normalized),
            "review_event_id": review["id"],
            "staging_import_event_id": event_id,
            "decision": {
                "writes_database_now": True,
                "writes_existing_event_now": True,
                "writes_staging_records_now": True,
                "writes_learning_samples_now": False,
                "normalized_records_persisted_to_staging": True,
                "normalized_records_persisted_to_training": False,
                "training_started_now": False,
                "can_import_to_learning_samples_now": False,
                "can_start_training_now": False,
                "next_required_action": "review_staging_quality_before_training_freeze",
            },
            "safety_summary": self._safety_summary(
                writes_database_now=True,
                writes_existing_event_now=True,
                writes_staging_records_now=True,
                normalized_records_persisted_to_staging=True,
            ),
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def list_staging_records(self, package_id: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
        store = SQLiteStore(settings.database_path)
        store.init()
        params: list[Any] = []
        where = ""
        if package_id:
            where = "WHERE package_id = ?"
            params.append(package_id)
        params.append(max(1, min(limit, 1000)))
        rows = store.fetch_all(
            f"""
            SELECT *
            FROM dataset2_staging_records
            {where}
            ORDER BY id DESC
            LIMIT ?
            """,
            tuple(params),
        )
        return [self._staging_row(row) for row in rows]

    def staging_summary(self) -> dict[str, Any]:
        store = SQLiteStore(settings.database_path)
        store.init()
        total = store.fetch_one("SELECT COUNT(*) AS count FROM dataset2_staging_records") or {"count": 0}
        packages = store.fetch_all(
            """
            SELECT package_id, COUNT(*) AS record_count, MAX(created_at) AS latest_created_at
            FROM dataset2_staging_records
            GROUP BY package_id
            ORDER BY latest_created_at DESC
            LIMIT 5
            """
        )
        action_rows = store.fetch_all(
            """
            SELECT action_label, COUNT(*) AS count
            FROM dataset2_staging_records
            GROUP BY action_label
            ORDER BY count DESC
            """
        )
        risk_rows = store.fetch_all(
            """
            SELECT risk_level, COUNT(*) AS count
            FROM dataset2_staging_records
            GROUP BY risk_level
            ORDER BY count DESC
            """
        )
        learning_count = store.fetch_one("SELECT COUNT(*) AS count FROM learning_samples") or {"count": 0}
        return {
            "schema_version": "dataset2_staging_summary.v1",
            "stage": self.stage,
            "status": "staging_records_available" if total["count"] else "staging_empty",
            "record_count": total["count"],
            "package_count": len(packages),
            "latest_packages": packages,
            "action_label_counts": {row["action_label"] or "unknown": row["count"] for row in action_rows},
            "risk_level_counts": {row["risk_level"] or "unknown": row["count"] for row in risk_rows},
            "decision": {
                "writes_database_now": False,
                "writes_learning_samples_now": False,
                "learning_sample_count": learning_count["count"],
                "training_started_now": False,
                "can_start_training_now": False,
                "next_required_action": "review_staged_records_before_dataset2_training_freeze",
            },
            "safety_summary": self._safety_summary(),
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def staging_quality_review(
        self,
        package_id: str | None = None,
        reviewed_by: str = "operator",
        note: str | None = None,
    ) -> dict[str, Any]:
        store = SQLiteStore(settings.database_path)
        store.init()
        resolved_package_id = package_id or self._latest_staging_package_id(store)
        rows = self.list_staging_records(package_id=resolved_package_id, limit=1000) if resolved_package_id else []
        action_counts: Counter[str] = Counter()
        risk_counts: Counter[str] = Counter()
        split_counts: Counter[str] = Counter()
        quality_flag_counts: Counter[str] = Counter()
        cleanup_operation_counts: Counter[str] = Counter()
        missing_historical_count = 0
        missing_required_count = 0

        for row in rows:
            normalized = row.get("normalized") or {}
            action_counts[str(row.get("action_label") or "unknown")] += 1
            risk_counts[str(row.get("risk_level") or "unknown")] += 1
            split_counts[str(row.get("split_tag") or "unknown")] += 1
            for flag in row.get("quality_flags") or []:
                quality_flag_counts[str(flag)] += 1
            for operation in row.get("cleanup_operations") or []:
                cleanup_operation_counts[str(operation.get("operation") or "unknown")] += 1
            if any(self._is_empty(normalized.get(field)) for field in HISTORICAL_OUTCOME_FIELDS):
                missing_historical_count += 1
            if not row.get("pattern_id") or row.get("action_label") not in ALLOWED_ACTION_LABELS or row.get("risk_level") not in ALLOWED_RISK_LEVELS:
                missing_required_count += 1

        low_support_labels = [
            {"action_label": label, "count": count}
            for label, count in sorted(action_counts.items())
            if label != "unknown" and count < LOW_SUPPORT_ACTION_THRESHOLD
        ]
        split_names = {name for name in split_counts if name and name != "unknown"}
        has_out_of_sample = bool(split_names.intersection({"validation", "valid", "test", "out_of_sample"}))
        gates = [
            self._gate("staging_records_present", "passed" if rows else "blocked", len(rows), ">0", "staged records must exist before training freeze review"),
            self._gate("required_fields_valid", "passed" if missing_required_count == 0 else "blocked", missing_required_count, 0, "pattern id, action label, and risk level must be valid"),
            self._gate("quality_flags_cleared", "passed" if not quality_flag_counts else "blocked", sum(quality_flag_counts.values()), 0, "cleanup quality flags must be reviewed before training freeze"),
            self._gate("historical_outcomes_complete", "passed" if missing_historical_count == 0 else "blocked", missing_historical_count, 0, "training needs complete dated outcome fields"),
            self._gate("label_support", "passed" if not low_support_labels else "warning", len(low_support_labels), 0, "low-support action labels should be expanded or weighted"),
            self._gate("split_coverage", "passed" if has_out_of_sample else "blocked", dict(split_counts), "train+validation/test", "freeze needs an out-of-sample split"),
            self._gate("learning_samples_isolation", "passed", False, False, "P4 review does not write learning_samples"),
            self._gate("training_start", "passed", False, False, "P4 review never starts training"),
        ]
        blocked = [gate for gate in gates if gate["status"] == "blocked"]
        warnings = [gate for gate in gates if gate["status"] == "warning"]
        payload = {
            "schema_version": "dataset2_staging_quality_review.v1",
            "stage": self.stage,
            "status": "training_freeze_blocked" if blocked else "training_freeze_review_passed",
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "package_id": resolved_package_id,
            "record_count": len(rows),
            "counts": {
                "action_labels": dict(action_counts),
                "risk_levels": dict(risk_counts),
                "splits": dict(split_counts),
                "quality_flags": dict(quality_flag_counts),
                "cleanup_operations": dict(cleanup_operation_counts),
            },
            "summary": {
                "blocked_gate_count": len(blocked),
                "warning_gate_count": len(warnings),
                "missing_historical_count": missing_historical_count,
                "missing_required_count": missing_required_count,
                "low_support_label_count": len(low_support_labels),
            },
            "gates": gates,
            "review": {
                "reviewed_by": reviewed_by or "operator",
                "note": note,
                "record_bodies_included": False,
                "review_only": True,
                "simulation_only": True,
            },
            "decision": {
                "writes_database_now": False,
                "writes_existing_event_now": True,
                "writes_learning_samples_now": False,
                "training_started_now": False,
                "training_freeze_allowed": False,
                "can_start_training_now": False,
                "next_required_action": "fix_blocked_staging_gates_before_training_freeze" if blocked else "manual_approval_required_before_training_freeze",
            },
            "safety_summary": self._safety_summary(writes_existing_event_now=True),
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }
        with store.connect() as conn:
            cursor = conn.execute(
                "INSERT INTO events (event_type, payload_json) VALUES (?, ?)",
                (self.staging_quality_review_event_type, json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)),
            )
            event_id = int(cursor.lastrowid)
        return {**payload, "event_id": event_id}

    def list_staging_quality_reviews(self, limit: int = 20) -> list[dict[str, Any]]:
        store = SQLiteStore(settings.database_path)
        store.init()
        rows = store.fetch_all(
            """
            SELECT id, event_type, payload_json, created_at
            FROM events
            WHERE event_type = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (self.staging_quality_review_event_type, max(1, min(limit, 100))),
        )
        reviews: list[dict[str, Any]] = []
        for row in rows:
            payload = json.loads(row.pop("payload_json") or "{}")
            reviews.append(
                {
                    "id": row["id"],
                    "event_type": row["event_type"],
                    "created_at": row["created_at"],
                    **payload,
                }
            )
        return reviews

    def staging_fix_plan(
        self,
        quality_review_id: int | None = None,
        planned_by: str = "operator",
        note: str | None = None,
    ) -> dict[str, Any]:
        store = SQLiteStore(settings.database_path)
        store.init()
        quality_review = self._quality_review_by_id(store, quality_review_id) if quality_review_id else self._latest_quality_review(store)
        if quality_review is None:
            return {
                "schema_version": "dataset2_staging_fix_plan.v1",
                "stage": self.stage,
                "status": "fix_plan_blocked_missing_quality_review",
                "generated_at": datetime.now().isoformat(timespec="seconds"),
                "quality_review_id": quality_review_id,
                "package_id": None,
                "action_items": [],
                "summary": {
                    "action_item_count": 0,
                    "blocked_gate_count": 0,
                    "warning_gate_count": 0,
                    "manual_action_count": 0,
                    "automated_action_count": 0,
                },
                "decision": {
                    "writes_database_now": False,
                    "writes_existing_event_now": False,
                    "writes_staging_records_now": False,
                    "writes_learning_samples_now": False,
                    "mutates_staging_records_now": False,
                    "training_started_now": False,
                    "can_start_training_now": False,
                    "next_required_action": "run_dataset2_staging_quality_review_before_fix_plan",
                },
                "safety_summary": self._safety_summary(),
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            }

        gates = quality_review.get("gates") or []
        action_items = self._fix_plan_action_items(quality_review)
        manual_count = sum(1 for item in action_items if item.get("execution_mode") == "manual_review_required")
        automated_count = sum(1 for item in action_items if item.get("execution_mode") == "future_script_after_review")
        payload = {
            "schema_version": "dataset2_staging_fix_plan.v1",
            "stage": self.stage,
            "status": "fix_plan_ready_for_review" if action_items else "fix_plan_not_required",
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "quality_review_id": quality_review.get("id"),
            "package_id": quality_review.get("package_id"),
            "record_count": quality_review.get("record_count", 0),
            "source_quality_status": quality_review.get("status"),
            "source_summary": quality_review.get("summary", {}),
            "action_items": action_items,
            "summary": {
                "action_item_count": len(action_items),
                "blocked_gate_count": sum(1 for gate in gates if gate.get("status") == "blocked"),
                "warning_gate_count": sum(1 for gate in gates if gate.get("status") == "warning"),
                "manual_action_count": manual_count,
                "automated_action_count": automated_count,
            },
            "plan": {
                "requires_operator_approval": True,
                "can_be_applied_automatically_now": False,
                "record_bodies_included": False,
                "recommended_sequence": [item["id"] for item in action_items],
            },
            "decision": {
                "writes_database_now": False,
                "writes_existing_event_now": True,
                "writes_staging_records_now": False,
                "writes_learning_samples_now": False,
                "mutates_staging_records_now": False,
                "training_started_now": False,
                "training_freeze_allowed": False,
                "can_start_training_now": False,
                "next_required_action": "review_fix_plan_then_build_separate_approved_cleanup_stage",
            },
            "review": {
                "planned_by": planned_by or "operator",
                "note": note,
                "review_only": True,
                "simulation_only": True,
            },
            "safety_summary": self._safety_summary(writes_existing_event_now=True),
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }
        with store.connect() as conn:
            cursor = conn.execute(
                "INSERT INTO events (event_type, payload_json) VALUES (?, ?)",
                (self.staging_fix_plan_event_type, json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)),
            )
            event_id = int(cursor.lastrowid)
        return {**payload, "event_id": event_id}

    def list_staging_fix_plans(self, limit: int = 20) -> list[dict[str, Any]]:
        store = SQLiteStore(settings.database_path)
        store.init()
        rows = store.fetch_all(
            """
            SELECT id, event_type, payload_json, created_at
            FROM events
            WHERE event_type = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (self.staging_fix_plan_event_type, max(1, min(limit, 100))),
        )
        plans: list[dict[str, Any]] = []
        for row in rows:
            payload = json.loads(row.pop("payload_json") or "{}")
            plans.append(
                {
                    "id": row["id"],
                    "event_type": row["event_type"],
                    "created_at": row["created_at"],
                    **payload,
                }
            )
        return plans

    def approve_staging_fix_plan(
        self,
        fix_plan_event_id: int | None = None,
        approved_by: str = "operator",
        approval_decision: str = "approved_for_preflight",
        note: str | None = None,
    ) -> dict[str, Any]:
        store = SQLiteStore(settings.database_path)
        store.init()
        fix_plan = self._fix_plan_by_id(store, fix_plan_event_id) if fix_plan_event_id else self._latest_fix_plan(store)
        if fix_plan is None:
            return {
                "schema_version": "dataset2_staging_fix_plan_approval.v1",
                "stage": self.stage,
                "status": "approval_blocked_missing_fix_plan",
                "generated_at": datetime.now().isoformat(timespec="seconds"),
                "fix_plan_event_id": fix_plan_event_id,
                "approval": {
                    "approved_by": approved_by or "operator",
                    "approval_decision": approval_decision,
                    "note": note,
                    "review_only": True,
                    "simulation_only": True,
                },
                "decision": {
                    "writes_database_now": False,
                    "writes_existing_event_now": False,
                    "writes_staging_records_now": False,
                    "writes_learning_samples_now": False,
                    "mutates_staging_records_now": False,
                    "approval_allows_fix_application_now": False,
                    "can_generate_preflight_now": False,
                    "training_started_now": False,
                    "can_start_training_now": False,
                    "next_required_action": "generate_dataset2_staging_fix_plan_before_approval",
                },
                "safety_summary": self._safety_summary(),
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            }

        allowed_decisions = {"approved_for_preflight", "rejected", "needs_revision"}
        normalized_decision = approval_decision if approval_decision in allowed_decisions else "needs_revision"
        can_generate_preflight = normalized_decision == "approved_for_preflight" and fix_plan.get("status") == "fix_plan_ready_for_review"
        payload = {
            "schema_version": "dataset2_staging_fix_plan_approval.v1",
            "stage": self.stage,
            "status": "fix_plan_approved_for_preflight" if can_generate_preflight else "fix_plan_not_approved_for_preflight",
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "fix_plan_event_id": fix_plan.get("id"),
            "quality_review_id": fix_plan.get("quality_review_id"),
            "package_id": fix_plan.get("package_id"),
            "source_fix_plan_status": fix_plan.get("status"),
            "source_summary": fix_plan.get("summary", {}),
            "approval": {
                "approved_by": approved_by or "operator",
                "approval_decision": normalized_decision,
                "requested_decision": approval_decision,
                "note": note,
                "record_bodies_included": False,
                "review_only": True,
                "simulation_only": True,
            },
            "decision": {
                "writes_database_now": False,
                "writes_existing_event_now": True,
                "writes_staging_records_now": False,
                "writes_learning_samples_now": False,
                "mutates_staging_records_now": False,
                "approval_allows_fix_application_now": False,
                "can_generate_preflight_now": can_generate_preflight,
                "training_started_now": False,
                "can_start_training_now": False,
                "next_required_action": (
                    "run_dataset2_staging_fix_preflight"
                    if can_generate_preflight
                    else "revise_or_reject_dataset2_staging_fix_plan"
                ),
            },
            "safety_summary": self._safety_summary(writes_existing_event_now=True),
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }
        with store.connect() as conn:
            cursor = conn.execute(
                "INSERT INTO events (event_type, payload_json) VALUES (?, ?)",
                (
                    self.staging_fix_plan_approval_event_type,
                    json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str),
                ),
            )
            event_id = int(cursor.lastrowid)
        return {**payload, "event_id": event_id}

    def list_staging_fix_plan_approvals(self, limit: int = 20) -> list[dict[str, Any]]:
        store = SQLiteStore(settings.database_path)
        store.init()
        rows = store.fetch_all(
            """
            SELECT id, event_type, payload_json, created_at
            FROM events
            WHERE event_type = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (self.staging_fix_plan_approval_event_type, max(1, min(limit, 100))),
        )
        approvals: list[dict[str, Any]] = []
        for row in rows:
            payload = json.loads(row.pop("payload_json") or "{}")
            approvals.append(
                {
                    "id": row["id"],
                    "event_type": row["event_type"],
                    "created_at": row["created_at"],
                    **payload,
                }
            )
        return approvals

    def staging_fix_preflight(
        self,
        approval_event_id: int | None = None,
        requested_by: str = "operator",
        note: str | None = None,
    ) -> dict[str, Any]:
        store = SQLiteStore(settings.database_path)
        store.init()
        approval = self._fix_plan_approval_by_id(store, approval_event_id) if approval_event_id else self._latest_fix_plan_approval(store)
        if approval is None or not approval.get("decision", {}).get("can_generate_preflight_now"):
            return {
                "schema_version": "dataset2_staging_fix_preflight.v1",
                "stage": self.stage,
                "status": "preflight_blocked_missing_approval",
                "generated_at": datetime.now().isoformat(timespec="seconds"),
                "approval_event_id": approval_event_id,
                "fix_plan_event_id": approval.get("fix_plan_event_id") if approval else None,
                "preflight_checks": [],
                "summary": {
                    "check_count": 0,
                    "blocked_check_count": 1,
                    "record_mutation_count": 0,
                },
                "decision": {
                    "writes_database_now": False,
                    "writes_existing_event_now": False,
                    "writes_staging_records_now": False,
                    "writes_learning_samples_now": False,
                    "mutates_staging_records_now": False,
                    "fixes_applied_now": False,
                    "training_started_now": False,
                    "can_start_training_now": False,
                    "next_required_action": "record_approved_dataset2_fix_plan_before_preflight",
                },
                "safety_summary": self._safety_summary(),
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            }

        fix_plan = self._fix_plan_by_id(store, int(approval["fix_plan_event_id"]))
        checks = self._fix_preflight_checks(fix_plan or {})
        blocked_count = sum(1 for check in checks if check.get("status") == "blocked")
        payload = {
            "schema_version": "dataset2_staging_fix_preflight.v1",
            "stage": self.stage,
            "status": "fix_preflight_ready_for_manual_execution" if checks else "fix_preflight_no_actions",
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "approval_event_id": approval.get("id"),
            "fix_plan_event_id": approval.get("fix_plan_event_id"),
            "quality_review_id": approval.get("quality_review_id"),
            "package_id": approval.get("package_id"),
            "preflight_checks": checks,
            "summary": {
                "check_count": len(checks),
                "blocked_check_count": blocked_count,
                "record_mutation_count": 0,
                "action_item_count": len((fix_plan or {}).get("action_items") or []),
            },
            "request": {
                "requested_by": requested_by or "operator",
                "note": note,
                "record_bodies_included": False,
                "review_only": True,
                "simulation_only": True,
            },
            "decision": {
                "writes_database_now": False,
                "writes_existing_event_now": True,
                "writes_staging_records_now": False,
                "writes_learning_samples_now": False,
                "mutates_staging_records_now": False,
                "fixes_applied_now": False,
                "training_started_now": False,
                "training_freeze_allowed": False,
                "can_start_training_now": False,
                "next_required_action": "manual_execute_reviewed_fix_steps_then_rerun_quality_review",
            },
            "safety_summary": self._safety_summary(writes_existing_event_now=True),
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }
        with store.connect() as conn:
            cursor = conn.execute(
                "INSERT INTO events (event_type, payload_json) VALUES (?, ?)",
                (
                    self.staging_fix_preflight_event_type,
                    json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str),
                ),
            )
            event_id = int(cursor.lastrowid)
        return {**payload, "event_id": event_id}

    def list_staging_fix_preflights(self, limit: int = 20) -> list[dict[str, Any]]:
        store = SQLiteStore(settings.database_path)
        store.init()
        rows = store.fetch_all(
            """
            SELECT id, event_type, payload_json, created_at
            FROM events
            WHERE event_type = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (self.staging_fix_preflight_event_type, max(1, min(limit, 100))),
        )
        preflights: list[dict[str, Any]] = []
        for row in rows:
            payload = json.loads(row.pop("payload_json") or "{}")
            preflights.append(
                {
                    "id": row["id"],
                    "event_type": row["event_type"],
                    "created_at": row["created_at"],
                    **payload,
                }
            )
        return preflights

    def _locate_pack(self, source_dir: str | None) -> Path | None:
        candidates: list[Path] = []
        if source_dir:
            candidates.append(Path(source_dir))
        else:
            cwd = Path.cwd()
            candidates.extend(
                [
                    cwd.parent / "数据集2" / "a_share_trading_training_pack_v2",
                    cwd.parent
                    / "数据集2"
                    / "a_share_trading_training_pack_v2"
                    / "a_share_trading_training_pack_v2",
                    cwd.parent / "数据集2" / "a_share_trading_training_pack_v2",
                    cwd.parent
                    / "数据集2"
                    / "a_share_trading_training_pack_v2"
                    / "a_share_trading_training_pack_v2",
                    cwd / "数据集2" / "a_share_trading_training_pack_v2",
                ]
            )

        for candidate in candidates:
            if self._has_dataset(candidate):
                return candidate
            nested = candidate / "a_share_trading_training_pack_v2"
            if self._has_dataset(nested):
                return nested
            if candidate.exists():
                matches = list(candidate.rglob("dataset/all_training_patterns.jsonl"))
                if matches:
                    return matches[0].parents[1]
        return None

    def _has_dataset(self, path: Path) -> bool:
        return (path / "dataset" / "all_training_patterns.jsonl").exists()

    def _read_jsonl(self, path: Path, limit: int) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        safe_limit = max(1, min(limit, 1000))
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if len(records) >= safe_limit:
                    break
                line = line.strip()
                if line:
                    records.append(json.loads(line))
        return records

    def _read_json(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    def _matching_import_queue_review(
        self,
        store: SQLiteStore,
        package_id: str,
        normalized_records_hash: str,
        review_event_id: int | None = None,
    ) -> dict[str, Any] | None:
        clauses = ["event_type = ?"]
        params: list[Any] = [self.import_queue_event_type]
        if review_event_id is not None:
            clauses.append("id = ?")
            params.append(review_event_id)
        rows = store.fetch_all(
            f"""
            SELECT id, event_type, payload_json, created_at
            FROM events
            WHERE {' AND '.join(clauses)}
            ORDER BY id DESC
            LIMIT 100
            """,
            tuple(params),
        )
        for row in rows:
            payload = json.loads(row.pop("payload_json") or "{}")
            if (
                payload.get("package_id") == package_id
                and payload.get("normalized_records_hash") == normalized_records_hash
            ):
                return {
                    "id": row["id"],
                    "event_type": row["event_type"],
                    "created_at": row["created_at"],
                    **payload,
                }
        return None

    def _latest_staging_package_id(self, store: SQLiteStore) -> str | None:
        row = store.fetch_one(
            """
            SELECT package_id
            FROM dataset2_staging_records
            GROUP BY package_id
            ORDER BY MAX(created_at) DESC
            LIMIT 1
            """
        )
        return str(row["package_id"]) if row and row.get("package_id") else None

    def _quality_review_by_id(self, store: SQLiteStore, review_id: int | None) -> dict[str, Any] | None:
        if review_id is None:
            return None
        row = store.fetch_one(
            """
            SELECT id, event_type, payload_json, created_at
            FROM events
            WHERE event_type = ? AND id = ?
            """,
            (self.staging_quality_review_event_type, review_id),
        )
        return self._event_payload(row) if row else None

    def _latest_quality_review(self, store: SQLiteStore) -> dict[str, Any] | None:
        row = store.fetch_one(
            """
            SELECT id, event_type, payload_json, created_at
            FROM events
            WHERE event_type = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (self.staging_quality_review_event_type,),
        )
        return self._event_payload(row) if row else None

    def _fix_plan_by_id(self, store: SQLiteStore, fix_plan_id: int | None) -> dict[str, Any] | None:
        if fix_plan_id is None:
            return None
        row = store.fetch_one(
            """
            SELECT id, event_type, payload_json, created_at
            FROM events
            WHERE event_type = ? AND id = ?
            """,
            (self.staging_fix_plan_event_type, fix_plan_id),
        )
        return self._event_payload(row) if row else None

    def _latest_fix_plan(self, store: SQLiteStore) -> dict[str, Any] | None:
        row = store.fetch_one(
            """
            SELECT id, event_type, payload_json, created_at
            FROM events
            WHERE event_type = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (self.staging_fix_plan_event_type,),
        )
        return self._event_payload(row) if row else None

    def _fix_plan_approval_by_id(self, store: SQLiteStore, approval_id: int | None) -> dict[str, Any] | None:
        if approval_id is None:
            return None
        row = store.fetch_one(
            """
            SELECT id, event_type, payload_json, created_at
            FROM events
            WHERE event_type = ? AND id = ?
            """,
            (self.staging_fix_plan_approval_event_type, approval_id),
        )
        return self._event_payload(row) if row else None

    def _latest_fix_plan_approval(self, store: SQLiteStore) -> dict[str, Any] | None:
        row = store.fetch_one(
            """
            SELECT id, event_type, payload_json, created_at
            FROM events
            WHERE event_type = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (self.staging_fix_plan_approval_event_type,),
        )
        return self._event_payload(row) if row else None

    def _event_payload(self, row: dict[str, Any]) -> dict[str, Any]:
        payload = json.loads(row.get("payload_json") or "{}")
        return {
            "id": row["id"],
            "event_type": row["event_type"],
            "created_at": row["created_at"],
            **payload,
        }

    def _fix_plan_action_items(self, quality_review: dict[str, Any]) -> list[dict[str, Any]]:
        counts = quality_review.get("counts") or {}
        summary = quality_review.get("summary") or {}
        gates = quality_review.get("gates") or []
        items: list[dict[str, Any]] = []
        for gate in gates:
            if gate.get("status") == "passed":
                continue
            name = str(gate.get("name") or "unknown_gate")
            if name == "quality_flags_cleared":
                items.append(
                    self._fix_item(
                        name,
                        "P0",
                        "manual_review_required",
                        "Review and clear staged quality flags before any training freeze.",
                        {
                            "quality_flags": counts.get("quality_flags", {}),
                            "cleanup_operations": counts.get("cleanup_operations", {}),
                        },
                        [
                            "Every quality flag is either corrected in a later approved stage or explicitly accepted with reviewer evidence.",
                            "No source dataset file is modified by this plan.",
                        ],
                    )
                )
            elif name == "historical_outcomes_complete":
                items.append(
                    self._fix_item(
                        name,
                        "P0",
                        "manual_review_required",
                        "Backfill or join dated historical outcome fields for staged records.",
                        {"missing_historical_count": summary.get("missing_historical_count", 0)},
                        [
                            "Missing stock/date/entry/exit/forward-return/MAE/MFE/benchmark fields are resolved or records are quarantined.",
                            "Outcome joins are validated before promotion to any training table.",
                        ],
                    )
                )
            elif name == "split_coverage":
                items.append(
                    self._fix_item(
                        name,
                        "P0",
                        "future_script_after_review",
                        "Create a deterministic time-aware train/validation or train/test split proposal.",
                        {"splits": counts.get("splits", {})},
                        [
                            "Out-of-sample split exists and is reproducible.",
                            "Split policy is recorded before any training freeze.",
                        ],
                    )
                )
            elif name == "label_support":
                items.append(
                    self._fix_item(
                        name,
                        "P1",
                        "manual_review_required",
                        "Review low-support action labels and decide weighting, consolidation, or sample expansion.",
                        {"low_support_label_count": summary.get("low_support_label_count", 0), "action_labels": counts.get("action_labels", {})},
                        [
                            "Low-support labels have a documented weighting/consolidation decision.",
                            "Classifier target distribution is reviewed before training.",
                        ],
                    )
                )
            else:
                items.append(
                    self._fix_item(
                        name,
                        "P1" if gate.get("status") == "warning" else "P0",
                        "manual_review_required",
                        f"Resolve gate `{name}` before training freeze.",
                        {"gate": gate},
                        ["Gate status is passed or explicitly deferred with reviewer evidence."],
                    )
                )
        return items

    def _fix_item(
        self,
        gate_name: str,
        priority: str,
        execution_mode: str,
        title: str,
        evidence: dict[str, Any],
        acceptance_checks: list[str],
    ) -> dict[str, Any]:
        item_id = self._stable_hash({"gate": gate_name, "priority": priority, "title": title})[:16]
        return {
            "id": f"dataset2_fix_{item_id}",
            "gate_name": gate_name,
            "priority": priority,
            "execution_mode": execution_mode,
            "title": title,
            "evidence": evidence,
            "acceptance_checks": acceptance_checks,
            "forbidden_actions": [
                "modify_dataset2_source_files",
                "write_learning_samples",
                "start_training",
                "create_export_file",
                "enable_live_trading",
            ],
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _fix_preflight_checks(self, fix_plan: dict[str, Any]) -> list[dict[str, Any]]:
        checks: list[dict[str, Any]] = []
        for item in fix_plan.get("action_items") or []:
            gate_name = str(item.get("gate_name") or "unknown_gate")
            if gate_name == "split_coverage":
                checks.append(
                    self._preflight_check(
                        item,
                        "time_aware_split_policy",
                        "ready_for_manual_execution",
                        {
                            "policy": "sort_by_signal_date_stock_code_pattern_id_then_70_30_train_validation",
                            "train_ratio": 0.7,
                            "validation_ratio": 0.3,
                            "writes_staging_records_now": False,
                        },
                    )
                )
            elif gate_name == "historical_outcomes_complete":
                checks.append(
                    self._preflight_check(
                        item,
                        "historical_outcome_join_requirements",
                        "blocked",
                        {
                            "requires_operator_dataset": True,
                            "required_fields": sorted(HISTORICAL_OUTCOME_FIELDS),
                            "writes_staging_records_now": False,
                        },
                    )
                )
            elif gate_name == "quality_flags_cleared":
                checks.append(
                    self._preflight_check(
                        item,
                        "quality_flag_resolution_requirements",
                        "blocked",
                        {
                            "requires_manual_flag_disposition": True,
                            "quality_flag_evidence": item.get("evidence", {}),
                            "writes_staging_records_now": False,
                        },
                    )
                )
            elif gate_name == "label_support":
                checks.append(
                    self._preflight_check(
                        item,
                        "label_support_policy_requirements",
                        "needs_review",
                        {
                            "allowed_future_options": ["class_weighting", "label_consolidation", "sample_expansion"],
                            "label_evidence": item.get("evidence", {}),
                            "writes_staging_records_now": False,
                        },
                    )
                )
            else:
                checks.append(
                    self._preflight_check(
                        item,
                        f"{gate_name}_manual_requirements",
                        "needs_review",
                        {
                            "gate_evidence": item.get("evidence", {}),
                            "writes_staging_records_now": False,
                        },
                    )
                )
        return checks

    def _preflight_check(
        self,
        item: dict[str, Any],
        name: str,
        status: str,
        details: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "id": f"dataset2_preflight_{self._stable_hash({'item': item.get('id'), 'name': name})[:16]}",
            "name": name,
            "source_action_item_id": item.get("id"),
            "gate_name": item.get("gate_name"),
            "priority": item.get("priority"),
            "status": status,
            "details": details,
            "acceptance_checks": item.get("acceptance_checks", []),
            "forbidden_actions": [
                "modify_dataset2_source_files",
                "mutate_staging_records",
                "write_learning_samples",
                "start_training",
                "create_export_file",
                "enable_live_trading",
            ],
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _staging_row(self, row: dict[str, Any]) -> dict[str, Any]:
        row = dict(row)
        row["normalized"] = json.loads(row.pop("normalized_json") or "{}")
        row["quality_flags"] = json.loads(row.pop("quality_flags_json") or "[]")
        row["cleanup_operations"] = json.loads(row.pop("cleanup_operations_json") or "[]")
        row["review_only"] = True
        row["simulation_only"] = True
        row["live_trading_enabled"] = settings.enable_live_trading
        return row

    def _analyze(self, records: list[dict[str, Any]]) -> dict[str, Any]:
        action_counts: Counter[str] = Counter()
        risk_counts: Counter[str] = Counter()
        category_counts: Counter[str] = Counter()
        source_counts: Counter[str] = Counter()
        missing_evidence_counts: defaultdict[str, int] = defaultdict(int)
        missing_historical_counts: defaultdict[str, int] = defaultdict(int)
        invalid_risk_levels: list[dict[str, Any]] = []
        invalid_action_labels: list[dict[str, Any]] = []
        unsafe_targets: list[dict[str, Any]] = []
        stringified_items: list[dict[str, Any]] = []
        stringified_count = 0
        empty_rule_logic_count = 0
        empty_training_notes_count = 0

        for record in records:
            pattern_id = str(record.get("pattern_id") or "")
            action = str(record.get("action_label") or "")
            risk = str(record.get("risk_level") or "")
            action_counts[action] += 1
            risk_counts[risk] += 1
            category_counts[str(record.get("category") or "unknown")] += 1
            source_counts[str(record.get("source_id") or "unknown")] += 1

            if risk not in ALLOWED_RISK_LEVELS:
                invalid_risk_levels.append(
                    {
                        "pattern_id": pattern_id,
                        "pattern_name": record.get("pattern_name"),
                        "risk_level": risk,
                        "normalized_risk_level": RISK_NORMALIZATION.get(risk),
                    }
                )
            if action not in ALLOWED_ACTION_LABELS:
                invalid_action_labels.append(
                    {
                        "pattern_id": pattern_id,
                        "pattern_name": record.get("pattern_name"),
                        "action_label": action,
                    }
                )

            for field in LIST_FIELDS:
                values = record.get(field)
                if isinstance(values, list):
                    for value in values:
                        if self._looks_stringified_list(value):
                            stringified_count += 1
                            stringified_items.append(
                                {
                                    "pattern_id": pattern_id,
                                    "field": field,
                                    "value": str(value),
                                }
                            )

            for field in EVIDENCE_FIELDS:
                if self._is_empty(record.get(field)):
                    missing_evidence_counts[field] += 1
            for field in HISTORICAL_OUTCOME_FIELDS:
                if self._is_empty(record.get(field)):
                    missing_historical_counts[field] += 1
            if self._is_empty(record.get("rule_logic")):
                empty_rule_logic_count += 1
            if self._is_empty(record.get("training_notes")):
                empty_training_notes_count += 1

            targets = record.get("model_targets") or {}
            if targets.get("allow_live_order") is not False or targets.get("requires_backtest") is not True:
                unsafe_targets.append(
                    {
                        "pattern_id": pattern_id,
                        "allow_live_order": targets.get("allow_live_order"),
                        "requires_backtest": targets.get("requires_backtest"),
                    }
                )

        low_support = [
            {"action_label": label, "count": action_counts.get(label, 0)}
            for label in sorted(ALLOWED_ACTION_LABELS)
            if action_counts.get(label, 0) < LOW_SUPPORT_ACTION_THRESHOLD
        ]

        return {
            "action_counts": action_counts,
            "risk_counts": risk_counts,
            "category_counts": category_counts,
            "source_counts": source_counts,
            "invalid_risk_levels": invalid_risk_levels,
            "invalid_action_labels": invalid_action_labels,
            "unsafe_model_targets": unsafe_targets,
            "stringified_list_item_count": stringified_count,
            "stringified_list_items": stringified_items,
            "missing_evidence_counts": missing_evidence_counts,
            "missing_historical_outcome_field_counts": missing_historical_counts,
            "empty_rule_logic_count": empty_rule_logic_count,
            "empty_training_notes_count": empty_training_notes_count,
            "low_support_action_labels": low_support,
        }

    def _gates(self, analysis: dict[str, Any], records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        missing_evidence_total = sum(analysis["missing_evidence_counts"].values())
        missing_outcome_total = sum(analysis["missing_historical_outcome_field_counts"].values())
        return [
            self._gate("dataset_present", "passed" if records else "blocked", len(records), ">0", "dataset records must be readable"),
            self._gate(
                "risk_level_schema",
                "passed" if not analysis["invalid_risk_levels"] else "blocked",
                len(analysis["invalid_risk_levels"]),
                0,
                "risk_level must normalize to low/medium/high before training",
            ),
            self._gate(
                "action_label_schema",
                "passed" if not analysis["invalid_action_labels"] else "blocked",
                len(analysis["invalid_action_labels"]),
                0,
                "action_label must use the controlled enum",
            ),
            self._gate(
                "stringified_list_cleanup",
                "passed" if analysis["stringified_list_item_count"] == 0 else "blocked",
                analysis["stringified_list_item_count"],
                0,
                "list fields must contain clean feature strings, not serialized Python lists",
            ),
            self._gate(
                "evidence_completeness",
                "passed" if missing_evidence_total == 0 else "blocked",
                missing_evidence_total,
                0,
                "evidence, trigger, filter, and invalidation fields must be filled before training",
            ),
            self._gate(
                "historical_outcome_examples",
                "passed" if missing_outcome_total == 0 else "blocked",
                missing_outcome_total,
                0,
                "training needs dated stock/outcome fields, not only teaching rules",
            ),
            self._gate(
                "label_balance",
                "passed" if not analysis["low_support_action_labels"] else "warning",
                len(analysis["low_support_action_labels"]),
                0,
                "low-support action labels should be expanded or weighted before classifier training",
            ),
            self._gate(
                "model_target_safety",
                "passed" if not analysis["unsafe_model_targets"] else "blocked",
                len(analysis["unsafe_model_targets"]),
                0,
                "dataset2 must remain simulate-only and require backtest review",
            ),
        ]

    def _gate(self, name: str, status: str, value: Any, limit: Any, reason: str) -> dict[str, Any]:
        return {"name": name, "status": status, "value": value, "limit": limit, "reason": reason}

    def _normalize_record(self, record: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(record)
        original_risk = str(record.get("risk_level") or "")
        normalized["risk_level_original"] = original_risk
        normalized["risk_level"] = RISK_NORMALIZATION.get(original_risk, original_risk)
        normalized["risk_range_note"] = (
            f"normalized from {original_risk}" if original_risk != normalized["risk_level"] else None
        )
        for field in LIST_FIELDS:
            normalized[field] = self._normalize_list(record.get(field))
        normalized["quality_flags"] = self._record_quality_flags(record)
        normalized["cleanup_operations"] = self._record_cleanup_operations(record)
        normalized["training_gate"] = {
            "rule_knowledge_only": True,
            "training_ready": not normalized["quality_flags"],
            "training_started_now": False,
            "requires_historical_outcome_dataset": True,
            "allow_live_order": False,
        }
        return normalized

    def _cleanup_actions(self, analysis: dict[str, Any]) -> list[dict[str, Any]]:
        missing_evidence = dict(analysis["missing_evidence_counts"])
        missing_historical = dict(analysis["missing_historical_outcome_field_counts"])
        unmapped_risk = [
            item
            for item in analysis["invalid_risk_levels"]
            if not item.get("normalized_risk_level")
        ]
        return [
            {
                "name": "risk_level_normalization",
                "status": "blocked" if unmapped_risk else ("ready_for_review" if analysis["invalid_risk_levels"] else "passed"),
                "count": len(analysis["invalid_risk_levels"]),
                "reason": "map known range values into low/medium/high and review unmapped values",
                "automated_preview_only": True,
            },
            {
                "name": "stringified_list_normalization",
                "status": "ready_for_review" if analysis["stringified_list_item_count"] else "passed",
                "count": analysis["stringified_list_item_count"],
                "reason": "convert serialized Python-style list strings into clean list items",
                "automated_preview_only": True,
            },
            {
                "name": "evidence_backfill_queue",
                "status": "blocked" if missing_evidence else "passed",
                "count": sum(missing_evidence.values()),
                "fields": missing_evidence,
                "reason": "evidence, trigger, filter, and invalidation fields need human-reviewed backfill",
                "automated_preview_only": False,
            },
            {
                "name": "historical_outcome_join_required",
                "status": "blocked" if missing_historical else "passed",
                "count": sum(missing_historical.values()),
                "fields": missing_historical,
                "reason": "rule cards still need dated stock/outcome examples before training",
                "automated_preview_only": False,
            },
            {
                "name": "label_support_review",
                "status": "warning" if analysis["low_support_action_labels"] else "passed",
                "count": len(analysis["low_support_action_labels"]),
                "labels": analysis["low_support_action_labels"],
                "reason": "low-support labels need weighting or more samples before classifier training",
                "automated_preview_only": False,
            },
            {
                "name": "model_target_safety_review",
                "status": "blocked" if analysis["unsafe_model_targets"] else "passed",
                "count": len(analysis["unsafe_model_targets"]),
                "reason": "all model targets must stay simulate-only and require backtest review",
                "automated_preview_only": False,
            },
        ]

    def _record_cleanup_operations(self, record: dict[str, Any]) -> list[dict[str, Any]]:
        operations: list[dict[str, Any]] = []
        original_risk = str(record.get("risk_level") or "")
        normalized_risk = RISK_NORMALIZATION.get(original_risk, original_risk)
        if original_risk != normalized_risk:
            operations.append(
                {
                    "field": "risk_level",
                    "operation": "normalize_enum",
                    "from": original_risk,
                    "to": normalized_risk,
                    "requires_review": True,
                }
            )
        for field in LIST_FIELDS:
            values = record.get(field)
            if isinstance(values, list) and any(self._looks_stringified_list(item) for item in values):
                operations.append(
                    {
                        "field": field,
                        "operation": "parse_stringified_list_items",
                        "requires_review": True,
                    }
                )
        for field in EVIDENCE_FIELDS:
            if self._is_empty(record.get(field)):
                operations.append(
                    {
                        "field": field,
                        "operation": "backfill_evidence",
                        "requires_review": True,
                    }
                )
        if any(self._is_empty(record.get(field)) for field in HISTORICAL_OUTCOME_FIELDS):
            operations.append(
                {
                    "field": "historical_outcome_fields",
                    "operation": "join_historical_outcome_example",
                    "requires_review": True,
                }
            )
        return operations

    def _normalize_list(self, value: Any) -> list[Any]:
        if value is None:
            return []
        values = value if isinstance(value, list) else [value]
        normalized: list[Any] = []
        for item in values:
            if self._looks_stringified_list(item):
                try:
                    parsed = ast.literal_eval(str(item))
                    if isinstance(parsed, list):
                        normalized.extend(parsed)
                        continue
                except (SyntaxError, ValueError):
                    pass
            normalized.append(item)
        return normalized

    def _record_quality_flags(self, record: dict[str, Any]) -> list[str]:
        flags: list[str] = []
        if str(record.get("risk_level") or "") not in ALLOWED_RISK_LEVELS:
            flags.append("risk_level_normalized")
        if any(
            self._looks_stringified_list(item)
            for field in LIST_FIELDS
            for item in (record.get(field) if isinstance(record.get(field), list) else [])
        ):
            flags.append("stringified_list_cleaned")
        for field in EVIDENCE_FIELDS:
            if self._is_empty(record.get(field)):
                flags.append(f"missing_{field}")
        if any(self._is_empty(record.get(field)) for field in HISTORICAL_OUTCOME_FIELDS):
            flags.append("missing_historical_outcome_fields")
        return flags

    def _looks_stringified_list(self, value: Any) -> bool:
        if not isinstance(value, str):
            return False
        stripped = value.strip()
        return (stripped.startswith("[") and stripped.endswith("]")) or (
            stripped.startswith("(") and stripped.endswith(")")
        )

    def _is_empty(self, value: Any) -> bool:
        return value is None or value == "" or value == [] or value == {}

    def _dataset_version(self, records: list[dict[str, Any]], check_report: dict[str, Any]) -> str | None:
        return check_report.get("dataset_version") or (records[0].get("dataset_version") if records else None)

    def _file_hash(self, path: Path) -> str | None:
        if not path.exists():
            return None
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _normalized_records_hash(self, records: list[dict[str, Any]]) -> str:
        return self._stable_hash(records)

    def _stable_hash(self, payload: Any) -> str:
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def _missing_dataset_response(self, source_dir: str | None) -> dict[str, Any]:
        return {
            "schema_version": "dataset2_training_readiness.v1",
            "stage": self.stage,
            "status": "dataset2_not_found",
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "source_dir": source_dir,
            "record_count": 0,
            "gates": [
                self._gate(
                    "dataset_present",
                    "blocked",
                    0,
                    ">0",
                    "dataset2 pack must contain dataset/all_training_patterns.jsonl",
                )
            ],
            "decision": {
                "can_use_as_rule_knowledge": False,
                "can_import_normalized_preview": False,
                "can_start_training_now": False,
                "next_required_action": "provide_dataset2_source_dir",
            },
            "safety_summary": self._safety_summary(),
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _safety_summary(
        self,
        writes_database_now: bool = False,
        writes_existing_event_now: bool = False,
        writes_staging_records_now: bool = False,
        normalized_records_persisted_to_staging: bool = False,
    ) -> dict[str, bool]:
        return {
            "review_only": True,
            "simulation_only": True,
            "training_started_now": False,
            "writes_database_now": writes_database_now,
            "writes_existing_event_now": writes_existing_event_now,
            "writes_staging_records_now": writes_staging_records_now,
            "writes_learning_samples_now": False,
            "writes_file": False,
            "writes_source_dataset": False,
            "normalized_records_persisted": False,
            "normalized_records_persisted_to_staging": normalized_records_persisted_to_staging,
            "normalized_records_persisted_to_training": False,
            "allow_live_order": False,
            "requires_backtest_before_training": True,
            "connects_broker": False,
            "places_real_trade": False,
            "screen_click_trading": False,
            "live_trading_enabled": settings.enable_live_trading,
        }
