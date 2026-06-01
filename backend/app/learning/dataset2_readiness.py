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

    stage = "V5.6-P21"
    import_queue_event_type = "dataset2_import_queue_review"
    staging_import_event_type = "dataset2_staging_import"
    staging_quality_review_event_type = "dataset2_staging_quality_review"
    staging_fix_plan_event_type = "dataset2_staging_fix_plan"
    staging_fix_plan_approval_event_type = "dataset2_staging_fix_plan_approval"
    staging_fix_preflight_event_type = "dataset2_staging_fix_preflight"
    staging_cleanup_execution_spec_event_type = "dataset2_staging_cleanup_execution_spec"
    staging_cleanup_dry_run_verification_event_type = "dataset2_staging_cleanup_dry_run_verification"
    staging_cleanup_manual_evidence_event_type = "dataset2_staging_cleanup_manual_evidence_verification"
    staging_cleanup_manual_evidence_acceptance_event_type = "dataset2_staging_cleanup_manual_evidence_acceptance_review"
    staging_cleanup_application_review_event_type = "dataset2_staging_cleanup_application_review"
    staging_cleanup_execution_approval_plan_event_type = "dataset2_staging_cleanup_execution_approval_plan"
    staging_cleanup_execution_manual_approval_event_type = "dataset2_staging_cleanup_execution_manual_approval"
    staging_cleanup_execution_preflight_event_type = "dataset2_staging_cleanup_execution_preflight"
    staging_cleanup_execution_dry_run_event_type = "dataset2_staging_cleanup_execution_dry_run"
    staging_cleanup_execution_dry_run_review_event_type = "dataset2_staging_cleanup_execution_dry_run_review"
    staging_cleanup_execution_plan_event_type = "dataset2_staging_cleanup_execution_plan"
    staging_cleanup_execution_plan_preflight_event_type = "dataset2_staging_cleanup_execution_plan_preflight"
    staging_cleanup_execution_controlled_dry_run_event_type = "dataset2_staging_cleanup_execution_controlled_dry_run"
    staging_cleanup_execution_controlled_dry_run_review_event_type = (
        "dataset2_staging_cleanup_execution_controlled_dry_run_review"
    )
    staging_cleanup_execution_controlled_approval_event_type = (
        "dataset2_staging_cleanup_execution_controlled_approval"
    )

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

    def staging_cleanup_execution_spec(
        self,
        preflight_event_id: int | None = None,
        specified_by: str = "operator",
        note: str | None = None,
    ) -> dict[str, Any]:
        store = SQLiteStore(settings.database_path)
        store.init()
        preflight = self._fix_preflight_by_id(store, preflight_event_id) if preflight_event_id else self._latest_fix_preflight(store)
        if preflight is None:
            return {
                "schema_version": "dataset2_staging_cleanup_execution_spec.v1",
                "stage": self.stage,
                "status": "execution_spec_blocked_missing_preflight",
                "generated_at": datetime.now().isoformat(timespec="seconds"),
                "preflight_event_id": preflight_event_id,
                "execution_steps": [],
                "summary": {
                    "step_count": 0,
                    "blocked_source_check_count": 0,
                    "machine_assisted_step_count": 0,
                    "manual_step_count": 0,
                },
                "decision": {
                    "writes_database_now": False,
                    "writes_existing_event_now": False,
                    "writes_staging_records_now": False,
                    "writes_learning_samples_now": False,
                    "mutates_staging_records_now": False,
                    "cleanup_executed_now": False,
                    "execution_spec_can_be_applied_now": False,
                    "can_promote_to_learning_samples_now": False,
                    "training_started_now": False,
                    "can_start_training_now": False,
                    "next_required_action": "run_dataset2_staging_fix_preflight_before_execution_spec",
                },
                "safety_summary": self._safety_summary(),
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            }

        steps = self._cleanup_execution_steps(preflight)
        blocked_source_checks = sum(1 for check in preflight.get("preflight_checks") or [] if check.get("status") == "blocked")
        machine_steps = sum(1 for step in steps if step.get("execution_mode") == "future_reviewed_script")
        manual_steps = sum(1 for step in steps if step.get("execution_mode") == "manual_operator_action")
        payload = {
            "schema_version": "dataset2_staging_cleanup_execution_spec.v1",
            "stage": self.stage,
            "status": "cleanup_execution_spec_ready_for_review" if steps else "cleanup_execution_spec_no_steps",
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "preflight_event_id": preflight.get("id"),
            "approval_event_id": preflight.get("approval_event_id"),
            "fix_plan_event_id": preflight.get("fix_plan_event_id"),
            "quality_review_id": preflight.get("quality_review_id"),
            "package_id": preflight.get("package_id"),
            "source_preflight_status": preflight.get("status"),
            "source_preflight_summary": preflight.get("summary", {}),
            "execution_steps": steps,
            "summary": {
                "step_count": len(steps),
                "blocked_source_check_count": blocked_source_checks,
                "machine_assisted_step_count": machine_steps,
                "manual_step_count": manual_steps,
                "record_body_count": 0,
            },
            "spec": {
                "requires_operator_approval": True,
                "can_execute_now": False,
                "contains_executable_code": False,
                "sql_included": False,
                "record_bodies_included": False,
                "recommended_sequence": [step["id"] for step in steps],
            },
            "decision": {
                "writes_database_now": False,
                "writes_existing_event_now": True,
                "writes_staging_records_now": False,
                "writes_learning_samples_now": False,
                "mutates_staging_records_now": False,
                "cleanup_executed_now": False,
                "execution_spec_can_be_applied_now": False,
                "can_promote_to_learning_samples_now": False,
                "training_started_now": False,
                "training_freeze_allowed": False,
                "can_start_training_now": False,
                "next_required_action": "review_execution_spec_then_build_separate_manual_cleanup_application_stage",
            },
            "review": {
                "specified_by": specified_by or "operator",
                "note": note,
                "record_bodies_included": False,
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
                (
                    self.staging_cleanup_execution_spec_event_type,
                    json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str),
                ),
            )
            event_id = int(cursor.lastrowid)
        return {**payload, "event_id": event_id}

    def list_staging_cleanup_execution_specs(self, limit: int = 20) -> list[dict[str, Any]]:
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
            (self.staging_cleanup_execution_spec_event_type, max(1, min(limit, 100))),
        )
        specs: list[dict[str, Any]] = []
        for row in rows:
            payload = json.loads(row.pop("payload_json") or "{}")
            specs.append(
                {
                    "id": row["id"],
                    "event_type": row["event_type"],
                    "created_at": row["created_at"],
                    **payload,
                }
            )
        return specs

    def staging_cleanup_dry_run_verification(
        self,
        execution_spec_event_id: int | None = None,
        verified_by: str = "operator",
        note: str | None = None,
    ) -> dict[str, Any]:
        store = SQLiteStore(settings.database_path)
        store.init()
        spec = (
            self._cleanup_execution_spec_by_id(store, execution_spec_event_id)
            if execution_spec_event_id
            else self._latest_cleanup_execution_spec(store)
        )
        if spec is None:
            return {
                "schema_version": "dataset2_staging_cleanup_dry_run_verification.v1",
                "stage": self.stage,
                "status": "dry_run_blocked_missing_execution_spec",
                "generated_at": datetime.now().isoformat(timespec="seconds"),
                "execution_spec_event_id": execution_spec_event_id,
                "checks": [],
                "summary": {
                    "check_count": 0,
                    "blocked_check_count": 1,
                    "warning_check_count": 0,
                    "execution_step_count": 0,
                },
                "decision": {
                    "writes_database_now": False,
                    "writes_existing_event_now": False,
                    "writes_staging_records_now": False,
                    "writes_learning_samples_now": False,
                    "mutates_staging_records_now": False,
                    "dry_run_executed_now": False,
                    "cleanup_executed_now": False,
                    "cleanup_application_allowed_now": False,
                    "can_promote_to_learning_samples_now": False,
                    "training_started_now": False,
                    "can_start_training_now": False,
                    "next_required_action": "create_dataset2_cleanup_execution_spec_before_dry_run_verification",
                },
                "safety_summary": self._safety_summary(),
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            }

        checks = self._cleanup_dry_run_checks(spec)
        blocked_count = sum(1 for check in checks if check.get("status") == "blocked")
        warning_count = sum(1 for check in checks if check.get("status") == "warning")
        payload = {
            "schema_version": "dataset2_staging_cleanup_dry_run_verification.v1",
            "stage": self.stage,
            "status": (
                "dry_run_blocked_manual_evidence_required"
                if blocked_count
                else "dry_run_passed_ready_for_manual_application_review"
            ),
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "execution_spec_event_id": spec.get("id"),
            "preflight_event_id": spec.get("preflight_event_id"),
            "approval_event_id": spec.get("approval_event_id"),
            "fix_plan_event_id": spec.get("fix_plan_event_id"),
            "quality_review_id": spec.get("quality_review_id"),
            "package_id": spec.get("package_id"),
            "source_execution_spec_status": spec.get("status"),
            "checks": checks,
            "summary": {
                "check_count": len(checks),
                "blocked_check_count": blocked_count,
                "warning_check_count": warning_count,
                "execution_step_count": len(spec.get("execution_steps") or []),
                "blocked_source_check_count": spec.get("summary", {}).get("blocked_source_check_count", 0),
                "record_body_count": spec.get("summary", {}).get("record_body_count", 0),
            },
            "verification": {
                "verified_by": verified_by or "operator",
                "note": note,
                "dry_run_only": True,
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
                "dry_run_executed_now": True,
                "cleanup_executed_now": False,
                "cleanup_application_allowed_now": False,
                "can_advance_to_manual_cleanup_application_review": blocked_count == 0,
                "can_promote_to_learning_samples_now": False,
                "training_started_now": False,
                "training_freeze_allowed": False,
                "can_start_training_now": False,
                "next_required_action": (
                    "resolve_blocked_dry_run_checks_before_cleanup_application"
                    if blocked_count
                    else "prepare_separate_manual_cleanup_application_stage"
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
                    self.staging_cleanup_dry_run_verification_event_type,
                    json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str),
                ),
            )
            event_id = int(cursor.lastrowid)
        return {**payload, "event_id": event_id}

    def list_staging_cleanup_dry_run_verifications(self, limit: int = 20) -> list[dict[str, Any]]:
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
            (self.staging_cleanup_dry_run_verification_event_type, max(1, min(limit, 100))),
        )
        verifications: list[dict[str, Any]] = []
        for row in rows:
            payload = json.loads(row.pop("payload_json") or "{}")
            verifications.append(
                {
                    "id": row["id"],
                    "event_type": row["event_type"],
                    "created_at": row["created_at"],
                    **payload,
                }
            )
        return verifications

    def staging_cleanup_manual_evidence_verification(
        self,
        dry_run_verification_id: int | None = None,
        evidence_package: dict[str, Any] | None = None,
        verified_by: str = "operator",
        note: str | None = None,
    ) -> dict[str, Any]:
        store = SQLiteStore(settings.database_path)
        store.init()
        dry_run = (
            self._cleanup_dry_run_by_id(store, dry_run_verification_id)
            if dry_run_verification_id
            else self._latest_cleanup_dry_run(store)
        )
        if dry_run is None:
            return {
                "schema_version": "dataset2_staging_cleanup_manual_evidence_verification.v1",
                "stage": self.stage,
                "status": "manual_evidence_blocked_missing_dry_run",
                "generated_at": datetime.now().isoformat(timespec="seconds"),
                "dry_run_verification_id": dry_run_verification_id,
                "checks": [],
                "summary": {
                    "check_count": 0,
                    "blocked_check_count": 1,
                    "warning_check_count": 0,
                    "provided_section_count": 0,
                    "record_bodies_included": False,
                },
                "decision": {
                    "writes_database_now": False,
                    "writes_existing_event_now": False,
                    "writes_staging_records_now": False,
                    "writes_learning_samples_now": False,
                    "mutates_staging_records_now": False,
                    "manual_evidence_accepted_for_review": False,
                    "cleanup_application_allowed_now": False,
                    "cleanup_executed_now": False,
                    "can_promote_to_learning_samples_now": False,
                    "training_started_now": False,
                    "can_start_training_now": False,
                    "next_required_action": "run_dataset2_cleanup_dry_run_verification_before_manual_evidence",
                },
                "safety_summary": self._safety_summary(),
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            }

        evidence = evidence_package if isinstance(evidence_package, dict) else {}
        checks = self._manual_evidence_checks(dry_run, evidence)
        blocked_count = sum(1 for check in checks if check.get("status") == "blocked")
        warning_count = sum(1 for check in checks if check.get("status") == "warning")
        body_hits = self._forbidden_evidence_paths(evidence)
        payload = {
            "schema_version": "dataset2_staging_cleanup_manual_evidence_verification.v1",
            "stage": self.stage,
            "status": (
                "manual_evidence_blocked"
                if blocked_count
                else "manual_evidence_package_verified_for_cleanup_review"
            ),
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "dry_run_verification_id": dry_run.get("id"),
            "execution_spec_event_id": dry_run.get("execution_spec_event_id"),
            "preflight_event_id": dry_run.get("preflight_event_id"),
            "approval_event_id": dry_run.get("approval_event_id"),
            "fix_plan_event_id": dry_run.get("fix_plan_event_id"),
            "quality_review_id": dry_run.get("quality_review_id"),
            "package_id": dry_run.get("package_id"),
            "source_dry_run_status": dry_run.get("status"),
            "evidence_summary": {
                "provided_sections": sorted(evidence.keys()),
                "provided_section_count": len(evidence),
                "evidence_package_hash": self._stable_hash(evidence) if evidence else None,
                "record_bodies_included": bool(body_hits),
                "forbidden_evidence_paths": body_hits,
                "evidence_package_body_included": False,
            },
            "checks": checks,
            "summary": {
                "check_count": len(checks),
                "blocked_check_count": blocked_count,
                "warning_check_count": warning_count,
                "provided_section_count": len(evidence),
                "record_bodies_included": bool(body_hits),
                "dry_run_blocked_check_count": dry_run.get("summary", {}).get("blocked_check_count", 0),
            },
            "verification": {
                "verified_by": verified_by or "operator",
                "note": note,
                "record_bodies_included": False,
                "evidence_package_body_included": False,
                "review_only": True,
                "simulation_only": True,
            },
            "decision": {
                "writes_database_now": False,
                "writes_existing_event_now": True,
                "writes_staging_records_now": False,
                "writes_learning_samples_now": False,
                "mutates_staging_records_now": False,
                "manual_evidence_accepted_for_review": blocked_count == 0,
                "cleanup_application_allowed_now": False,
                "cleanup_executed_now": False,
                "can_promote_to_learning_samples_now": False,
                "training_started_now": False,
                "training_freeze_allowed": False,
                "can_start_training_now": False,
                "next_required_action": (
                    "resolve_manual_evidence_blocks_before_cleanup_application"
                    if blocked_count
                    else "prepare_separate_cleanup_application_review_stage"
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
                    self.staging_cleanup_manual_evidence_event_type,
                    json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str),
                ),
            )
            event_id = int(cursor.lastrowid)
        return {**payload, "event_id": event_id}

    def list_staging_cleanup_manual_evidence_verifications(self, limit: int = 20) -> list[dict[str, Any]]:
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
            (self.staging_cleanup_manual_evidence_event_type, max(1, min(limit, 100))),
        )
        verifications: list[dict[str, Any]] = []
        for row in rows:
            payload = json.loads(row.pop("payload_json") or "{}")
            verifications.append(
                {
                    "id": row["id"],
                    "event_type": row["event_type"],
                    "created_at": row["created_at"],
                    **payload,
                }
            )
        return verifications

    def staging_cleanup_manual_evidence_acceptance_review(
        self,
        manual_evidence_verification_id: int | None = None,
        accepted_by: str = "operator",
        acceptance_decision: str = "accepted_for_cleanup_review",
        note: str | None = None,
    ) -> dict[str, Any]:
        store = SQLiteStore(settings.database_path)
        store.init()
        manual_evidence = (
            self._manual_evidence_by_id(store, manual_evidence_verification_id)
            if manual_evidence_verification_id
            else self._latest_manual_evidence(store)
        )
        if manual_evidence is None:
            return {
                "schema_version": "dataset2_staging_cleanup_manual_evidence_acceptance_review.v1",
                "stage": self.stage,
                "status": "manual_evidence_acceptance_blocked_missing_verification",
                "generated_at": datetime.now().isoformat(timespec="seconds"),
                "manual_evidence_verification_id": manual_evidence_verification_id,
                "checks": [],
                "summary": {
                    "check_count": 0,
                    "blocked_check_count": 1,
                    "warning_check_count": 0,
                    "manual_evidence_check_count": 0,
                    "manual_evidence_blocked_check_count": None,
                    "record_bodies_included": False,
                },
                "decision": {
                    "writes_database_now": False,
                    "writes_existing_event_now": False,
                    "writes_staging_records_now": False,
                    "writes_learning_samples_now": False,
                    "mutates_staging_records_now": False,
                    "manual_evidence_acceptance_recorded": False,
                    "manual_evidence_ready_for_cleanup_application_review": False,
                    "cleanup_application_allowed_now": False,
                    "cleanup_executed_now": False,
                    "can_promote_to_learning_samples_now": False,
                    "training_started_now": False,
                    "training_freeze_allowed": False,
                    "can_start_training_now": False,
                    "next_required_action": "run_dataset2_manual_evidence_verification_before_acceptance_review",
                },
                "safety_summary": self._safety_summary(),
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            }

        checks = self._manual_evidence_acceptance_checks(
            manual_evidence,
            accepted_by=accepted_by,
            acceptance_decision=acceptance_decision,
        )
        blocked_count = sum(1 for check in checks if check.get("status") == "blocked")
        warning_count = sum(1 for check in checks if check.get("status") == "warning")
        ready_for_cleanup_review = blocked_count == 0 and acceptance_decision == "accepted_for_cleanup_review"
        evidence_summary = manual_evidence.get("evidence_summary") or {}
        manual_summary = manual_evidence.get("summary") or {}
        payload = {
            "schema_version": "dataset2_staging_cleanup_manual_evidence_acceptance_review.v1",
            "stage": self.stage,
            "status": (
                "manual_evidence_accepted_for_cleanup_review"
                if ready_for_cleanup_review
                else "manual_evidence_acceptance_blocked"
            ),
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "manual_evidence_verification_id": manual_evidence.get("id"),
            "dry_run_verification_id": manual_evidence.get("dry_run_verification_id"),
            "execution_spec_event_id": manual_evidence.get("execution_spec_event_id"),
            "preflight_event_id": manual_evidence.get("preflight_event_id"),
            "approval_event_id": manual_evidence.get("approval_event_id"),
            "fix_plan_event_id": manual_evidence.get("fix_plan_event_id"),
            "quality_review_id": manual_evidence.get("quality_review_id"),
            "package_id": manual_evidence.get("package_id"),
            "source_manual_evidence_status": manual_evidence.get("status"),
            "evidence_summary": {
                "provided_sections": sorted(evidence_summary.get("provided_sections") or []),
                "provided_section_count": evidence_summary.get("provided_section_count", 0),
                "evidence_package_hash": evidence_summary.get("evidence_package_hash"),
                "record_bodies_included": bool(evidence_summary.get("record_bodies_included")),
                "evidence_package_body_included": False,
            },
            "source_manual_evidence_summary": {
                "check_count": manual_summary.get("check_count", 0),
                "blocked_check_count": manual_summary.get("blocked_check_count", 0),
                "warning_check_count": manual_summary.get("warning_check_count", 0),
                "provided_section_count": manual_summary.get("provided_section_count", 0),
                "record_bodies_included": bool(manual_summary.get("record_bodies_included")),
            },
            "checks": checks,
            "summary": {
                "check_count": len(checks),
                "blocked_check_count": blocked_count,
                "warning_check_count": warning_count,
                "manual_evidence_check_count": manual_summary.get("check_count", 0),
                "manual_evidence_blocked_check_count": manual_summary.get("blocked_check_count", 0),
                "provided_section_count": evidence_summary.get("provided_section_count", 0),
                "record_bodies_included": bool(evidence_summary.get("record_bodies_included"))
                or bool(manual_summary.get("record_bodies_included")),
            },
            "acceptance": {
                "accepted_by": accepted_by or "operator",
                "acceptance_decision": acceptance_decision,
                "note": note,
                "record_bodies_included": False,
                "evidence_package_body_included": False,
                "review_only": True,
                "simulation_only": True,
            },
            "decision": {
                "writes_database_now": False,
                "writes_existing_event_now": True,
                "writes_staging_records_now": False,
                "writes_learning_samples_now": False,
                "mutates_staging_records_now": False,
                "manual_evidence_acceptance_recorded": True,
                "manual_evidence_ready_for_cleanup_application_review": ready_for_cleanup_review,
                "cleanup_application_allowed_now": False,
                "cleanup_executed_now": False,
                "can_promote_to_learning_samples_now": False,
                "training_started_now": False,
                "training_freeze_allowed": False,
                "can_start_training_now": False,
                "next_required_action": (
                    "resolve_manual_evidence_acceptance_blocks_before_cleanup_application_review"
                    if blocked_count
                    else "prepare_separate_cleanup_application_gate_before_any_staging_mutation"
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
                    self.staging_cleanup_manual_evidence_acceptance_event_type,
                    json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str),
                ),
            )
            event_id = int(cursor.lastrowid)
        return {**payload, "event_id": event_id}

    def list_staging_cleanup_manual_evidence_acceptance_reviews(self, limit: int = 20) -> list[dict[str, Any]]:
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
            (self.staging_cleanup_manual_evidence_acceptance_event_type, max(1, min(limit, 100))),
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

    def staging_cleanup_application_review(
        self,
        acceptance_review_id: int | None = None,
        reviewed_by: str = "operator",
        review_decision: str = "ready_for_future_cleanup_application",
        note: str | None = None,
    ) -> dict[str, Any]:
        store = SQLiteStore(settings.database_path)
        store.init()
        acceptance = (
            self._manual_evidence_acceptance_by_id(store, acceptance_review_id)
            if acceptance_review_id
            else self._latest_manual_evidence_acceptance(store)
        )
        if acceptance is None:
            return {
                "schema_version": "dataset2_staging_cleanup_application_review.v1",
                "stage": self.stage,
                "status": "cleanup_application_review_blocked_missing_acceptance",
                "generated_at": datetime.now().isoformat(timespec="seconds"),
                "acceptance_review_id": acceptance_review_id,
                "checks": [],
                "summary": {
                    "check_count": 0,
                    "blocked_check_count": 1,
                    "warning_check_count": 0,
                    "acceptance_blocked_check_count": None,
                    "record_bodies_included": False,
                },
                "decision": {
                    "writes_database_now": False,
                    "writes_existing_event_now": False,
                    "writes_staging_records_now": False,
                    "writes_learning_samples_now": False,
                    "mutates_staging_records_now": False,
                    "cleanup_application_review_recorded": False,
                    "cleanup_application_ready_for_future_plan": False,
                    "cleanup_application_allowed_now": False,
                    "cleanup_executed_now": False,
                    "future_cleanup_execution_requires_separate_approval": True,
                    "can_promote_to_learning_samples_now": False,
                    "training_started_now": False,
                    "training_freeze_allowed": False,
                    "can_start_training_now": False,
                    "next_required_action": "run_dataset2_manual_evidence_acceptance_review_before_cleanup_application_review",
                },
                "safety_summary": self._safety_summary(),
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            }

        checks = self._cleanup_application_review_checks(
            acceptance,
            reviewed_by=reviewed_by,
            review_decision=review_decision,
        )
        blocked_count = sum(1 for check in checks if check.get("status") == "blocked")
        warning_count = sum(1 for check in checks if check.get("status") == "warning")
        ready_for_future_plan = blocked_count == 0 and review_decision == "ready_for_future_cleanup_application"
        acceptance_summary = acceptance.get("summary") or {}
        acceptance_decision = acceptance.get("decision") or {}
        evidence_summary = acceptance.get("evidence_summary") or {}
        payload = {
            "schema_version": "dataset2_staging_cleanup_application_review.v1",
            "stage": self.stage,
            "status": (
                "cleanup_application_review_ready"
                if ready_for_future_plan
                else "cleanup_application_review_blocked"
            ),
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "acceptance_review_id": acceptance.get("id"),
            "manual_evidence_verification_id": acceptance.get("manual_evidence_verification_id"),
            "dry_run_verification_id": acceptance.get("dry_run_verification_id"),
            "execution_spec_event_id": acceptance.get("execution_spec_event_id"),
            "preflight_event_id": acceptance.get("preflight_event_id"),
            "approval_event_id": acceptance.get("approval_event_id"),
            "fix_plan_event_id": acceptance.get("fix_plan_event_id"),
            "quality_review_id": acceptance.get("quality_review_id"),
            "package_id": acceptance.get("package_id"),
            "source_acceptance_status": acceptance.get("status"),
            "evidence_summary": {
                "provided_sections": sorted(evidence_summary.get("provided_sections") or []),
                "provided_section_count": evidence_summary.get("provided_section_count", 0),
                "evidence_package_hash": evidence_summary.get("evidence_package_hash"),
                "record_bodies_included": bool(evidence_summary.get("record_bodies_included")),
                "evidence_package_body_included": False,
            },
            "source_acceptance_summary": {
                "check_count": acceptance_summary.get("check_count", 0),
                "blocked_check_count": acceptance_summary.get("blocked_check_count", 0),
                "warning_check_count": acceptance_summary.get("warning_check_count", 0),
                "manual_evidence_blocked_check_count": acceptance_summary.get("manual_evidence_blocked_check_count"),
                "record_bodies_included": bool(acceptance_summary.get("record_bodies_included")),
            },
            "checks": checks,
            "summary": {
                "check_count": len(checks),
                "blocked_check_count": blocked_count,
                "warning_check_count": warning_count,
                "acceptance_check_count": acceptance_summary.get("check_count", 0),
                "acceptance_blocked_check_count": acceptance_summary.get("blocked_check_count", 0),
                "provided_section_count": evidence_summary.get("provided_section_count", 0),
                "record_bodies_included": bool(evidence_summary.get("record_bodies_included"))
                or bool(acceptance_summary.get("record_bodies_included")),
            },
            "review": {
                "reviewed_by": reviewed_by or "operator",
                "review_decision": review_decision,
                "note": note,
                "record_bodies_included": False,
                "evidence_package_body_included": False,
                "review_only": True,
                "simulation_only": True,
            },
            "decision": {
                "writes_database_now": False,
                "writes_existing_event_now": True,
                "writes_staging_records_now": False,
                "writes_learning_samples_now": False,
                "mutates_staging_records_now": False,
                "cleanup_application_review_recorded": True,
                "cleanup_application_ready_for_future_plan": ready_for_future_plan,
                "cleanup_application_allowed_now": False,
                "cleanup_executed_now": False,
                "future_cleanup_execution_requires_separate_approval": True,
                "can_promote_to_learning_samples_now": False,
                "training_started_now": False,
                "training_freeze_allowed": False,
                "can_start_training_now": False,
                "next_required_action": (
                    "resolve_cleanup_application_review_blocks_before_any_execution_plan"
                    if blocked_count
                    else "prepare_separate_cleanup_execution_approval_before_any_staging_mutation"
                ),
            },
            "source_acceptance_decision": {
                "manual_evidence_ready_for_cleanup_application_review": acceptance_decision.get(
                    "manual_evidence_ready_for_cleanup_application_review"
                ),
                "cleanup_application_allowed_now": acceptance_decision.get("cleanup_application_allowed_now"),
                "cleanup_executed_now": acceptance_decision.get("cleanup_executed_now"),
                "writes_learning_samples_now": acceptance_decision.get("writes_learning_samples_now"),
                "training_started_now": acceptance_decision.get("training_started_now"),
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
                    self.staging_cleanup_application_review_event_type,
                    json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str),
                ),
            )
            event_id = int(cursor.lastrowid)
        return {**payload, "event_id": event_id}

    def list_staging_cleanup_application_reviews(self, limit: int = 20) -> list[dict[str, Any]]:
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
            (self.staging_cleanup_application_review_event_type, max(1, min(limit, 100))),
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

    def staging_cleanup_execution_approval_plan(
        self,
        cleanup_application_review_id: int | None = None,
        planned_by: str = "operator",
        plan_decision: str = "prepared_for_manual_approval",
        note: str | None = None,
    ) -> dict[str, Any]:
        store = SQLiteStore(settings.database_path)
        store.init()
        application = (
            self._cleanup_application_review_by_id(store, cleanup_application_review_id)
            if cleanup_application_review_id
            else self._latest_cleanup_application_review(store)
        )
        if application is None:
            return {
                "schema_version": "dataset2_staging_cleanup_execution_approval_plan.v1",
                "stage": self.stage,
                "status": "cleanup_execution_approval_plan_blocked_missing_application_review",
                "generated_at": datetime.now().isoformat(timespec="seconds"),
                "cleanup_application_review_id": cleanup_application_review_id,
                "approval_plan": {
                    "steps": [],
                    "step_count": 0,
                    "contains_sql": False,
                    "contains_executable_code": False,
                    "can_execute_now": False,
                    "requires_manual_execution_approval": True,
                    "review_only": True,
                    "simulation_only": True,
                },
                "checks": [],
                "summary": {
                    "check_count": 0,
                    "blocked_check_count": 1,
                    "warning_check_count": 0,
                    "application_blocked_check_count": None,
                    "approval_step_count": 0,
                    "record_bodies_included": False,
                },
                "decision": {
                    "writes_database_now": False,
                    "writes_existing_event_now": False,
                    "writes_staging_records_now": False,
                    "writes_learning_samples_now": False,
                    "mutates_staging_records_now": False,
                    "cleanup_execution_approval_plan_recorded": False,
                    "cleanup_execution_plan_ready_for_manual_approval": False,
                    "cleanup_execution_approved_now": False,
                    "cleanup_application_allowed_now": False,
                    "cleanup_executed_now": False,
                    "can_execute_cleanup_now": False,
                    "can_promote_to_learning_samples_now": False,
                    "training_started_now": False,
                    "training_freeze_allowed": False,
                    "can_start_training_now": False,
                    "next_required_action": "run_dataset2_cleanup_application_review_before_execution_approval_plan",
                },
                "safety_summary": self._safety_summary(),
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            }

        approval_steps = self._cleanup_execution_approval_steps(application)
        checks = self._cleanup_execution_approval_plan_checks(
            application,
            approval_steps=approval_steps,
            planned_by=planned_by,
            plan_decision=plan_decision,
        )
        blocked_count = sum(1 for check in checks if check.get("status") == "blocked")
        warning_count = sum(1 for check in checks if check.get("status") == "warning")
        ready_for_manual_approval = blocked_count == 0 and plan_decision == "prepared_for_manual_approval"
        application_summary = application.get("summary") or {}
        application_decision = application.get("decision") or {}
        evidence_summary = application.get("evidence_summary") or {}
        payload = {
            "schema_version": "dataset2_staging_cleanup_execution_approval_plan.v1",
            "stage": self.stage,
            "status": (
                "cleanup_execution_approval_plan_ready"
                if ready_for_manual_approval
                else "cleanup_execution_approval_plan_blocked"
            ),
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "cleanup_application_review_id": application.get("id"),
            "acceptance_review_id": application.get("acceptance_review_id"),
            "manual_evidence_verification_id": application.get("manual_evidence_verification_id"),
            "dry_run_verification_id": application.get("dry_run_verification_id"),
            "execution_spec_event_id": application.get("execution_spec_event_id"),
            "preflight_event_id": application.get("preflight_event_id"),
            "approval_event_id": application.get("approval_event_id"),
            "fix_plan_event_id": application.get("fix_plan_event_id"),
            "quality_review_id": application.get("quality_review_id"),
            "package_id": application.get("package_id"),
            "source_cleanup_application_status": application.get("status"),
            "evidence_summary": {
                "provided_sections": sorted(evidence_summary.get("provided_sections") or []),
                "provided_section_count": evidence_summary.get("provided_section_count", 0),
                "evidence_package_hash": evidence_summary.get("evidence_package_hash"),
                "record_bodies_included": bool(evidence_summary.get("record_bodies_included")),
                "evidence_package_body_included": False,
            },
            "source_cleanup_application_summary": {
                "check_count": application_summary.get("check_count", 0),
                "blocked_check_count": application_summary.get("blocked_check_count", 0),
                "warning_check_count": application_summary.get("warning_check_count", 0),
                "record_bodies_included": bool(application_summary.get("record_bodies_included")),
            },
            "approval_plan": {
                "steps": approval_steps,
                "step_count": len(approval_steps),
                "contains_sql": False,
                "contains_executable_code": False,
                "can_execute_now": False,
                "requires_manual_execution_approval": True,
                "future_execution_requires_separate_approval": True,
                "review_only": True,
                "simulation_only": True,
            },
            "checks": checks,
            "summary": {
                "check_count": len(checks),
                "blocked_check_count": blocked_count,
                "warning_check_count": warning_count,
                "application_check_count": application_summary.get("check_count", 0),
                "application_blocked_check_count": application_summary.get("blocked_check_count", 0),
                "approval_step_count": len(approval_steps),
                "record_bodies_included": bool(evidence_summary.get("record_bodies_included"))
                or bool(application_summary.get("record_bodies_included")),
            },
            "planning": {
                "planned_by": planned_by or "operator",
                "plan_decision": plan_decision,
                "note": note,
                "record_bodies_included": False,
                "evidence_package_body_included": False,
                "review_only": True,
                "simulation_only": True,
            },
            "decision": {
                "writes_database_now": False,
                "writes_existing_event_now": True,
                "writes_staging_records_now": False,
                "writes_learning_samples_now": False,
                "mutates_staging_records_now": False,
                "cleanup_execution_approval_plan_recorded": True,
                "cleanup_execution_plan_ready_for_manual_approval": ready_for_manual_approval,
                "cleanup_execution_approved_now": False,
                "cleanup_application_allowed_now": False,
                "cleanup_executed_now": False,
                "can_execute_cleanup_now": False,
                "future_cleanup_execution_requires_separate_approval": True,
                "can_promote_to_learning_samples_now": False,
                "training_started_now": False,
                "training_freeze_allowed": False,
                "can_start_training_now": False,
                "next_required_action": (
                    "resolve_cleanup_execution_approval_plan_blocks_before_manual_execution_approval"
                    if blocked_count
                    else "prepare_separate_manual_cleanup_execution_approval_before_any_staging_mutation"
                ),
            },
            "source_cleanup_application_decision": {
                "cleanup_application_ready_for_future_plan": application_decision.get(
                    "cleanup_application_ready_for_future_plan"
                ),
                "cleanup_application_allowed_now": application_decision.get("cleanup_application_allowed_now"),
                "cleanup_executed_now": application_decision.get("cleanup_executed_now"),
                "writes_learning_samples_now": application_decision.get("writes_learning_samples_now"),
                "training_started_now": application_decision.get("training_started_now"),
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
                    self.staging_cleanup_execution_approval_plan_event_type,
                    json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str),
                ),
            )
            event_id = int(cursor.lastrowid)
        return {**payload, "event_id": event_id}

    def list_staging_cleanup_execution_approval_plans(self, limit: int = 20) -> list[dict[str, Any]]:
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
            (self.staging_cleanup_execution_approval_plan_event_type, max(1, min(limit, 100))),
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

    def staging_cleanup_execution_manual_approval(
        self,
        approval_plan_id: int | None = None,
        approved_by: str = "operator",
        approval_decision: str = "approved_for_cleanup_execution_preflight",
        note: str | None = None,
    ) -> dict[str, Any]:
        store = SQLiteStore(settings.database_path)
        store.init()
        approval_plan = (
            self._cleanup_execution_approval_plan_by_id(store, approval_plan_id)
            if approval_plan_id
            else self._latest_cleanup_execution_approval_plan(store)
        )
        if approval_plan is None:
            return {
                "schema_version": "dataset2_staging_cleanup_execution_manual_approval.v1",
                "stage": self.stage,
                "status": "cleanup_execution_manual_approval_blocked_missing_approval_plan",
                "generated_at": datetime.now().isoformat(timespec="seconds"),
                "approval_plan_id": approval_plan_id,
                "checks": [],
                "summary": {
                    "check_count": 0,
                    "blocked_check_count": 1,
                    "warning_check_count": 0,
                    "source_plan_blocked_check_count": None,
                    "approval_step_count": 0,
                    "record_bodies_included": False,
                },
                "manual_approval": {
                    "approved_by": approved_by or "operator",
                    "approval_decision": approval_decision,
                    "note": note,
                    "record_bodies_included": False,
                    "evidence_package_body_included": False,
                    "review_only": True,
                    "simulation_only": True,
                },
                "decision": {
                    "writes_database_now": False,
                    "writes_existing_event_now": False,
                    "writes_staging_records_now": False,
                    "writes_learning_samples_now": False,
                    "mutates_staging_records_now": False,
                    "cleanup_execution_manual_approval_recorded": False,
                    "cleanup_execution_approval_metadata_accepted": False,
                    "cleanup_execution_approved_for_future_preflight": False,
                    "cleanup_execution_approved_now": False,
                    "cleanup_application_allowed_now": False,
                    "cleanup_executed_now": False,
                    "can_execute_cleanup_now": False,
                    "can_generate_cleanup_execution_preflight_now": False,
                    "future_cleanup_execution_preflight_required": True,
                    "can_promote_to_learning_samples_now": False,
                    "training_started_now": False,
                    "training_freeze_allowed": False,
                    "can_start_training_now": False,
                    "next_required_action": "run_dataset2_cleanup_execution_approval_plan_before_manual_approval",
                },
                "safety_summary": self._safety_summary(),
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            }

        checks = self._cleanup_execution_manual_approval_checks(
            approval_plan,
            approved_by=approved_by,
            approval_decision=approval_decision,
        )
        blocked_count = sum(1 for check in checks if check.get("status") == "blocked")
        warning_count = sum(1 for check in checks if check.get("status") == "warning")
        approval_accepted = blocked_count == 0 and approval_decision == "approved_for_cleanup_execution_preflight"
        plan_summary = approval_plan.get("summary") or {}
        plan_decision = approval_plan.get("decision") or {}
        evidence_summary = approval_plan.get("evidence_summary") or {}
        approval_plan_body = approval_plan.get("approval_plan") or {}
        payload = {
            "schema_version": "dataset2_staging_cleanup_execution_manual_approval.v1",
            "stage": self.stage,
            "status": (
                "cleanup_execution_manual_approval_ready_for_preflight"
                if approval_accepted
                else "cleanup_execution_manual_approval_blocked"
            ),
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "approval_plan_id": approval_plan.get("id"),
            "cleanup_application_review_id": approval_plan.get("cleanup_application_review_id"),
            "acceptance_review_id": approval_plan.get("acceptance_review_id"),
            "manual_evidence_verification_id": approval_plan.get("manual_evidence_verification_id"),
            "dry_run_verification_id": approval_plan.get("dry_run_verification_id"),
            "execution_spec_event_id": approval_plan.get("execution_spec_event_id"),
            "preflight_event_id": approval_plan.get("preflight_event_id"),
            "approval_event_id": approval_plan.get("approval_event_id"),
            "fix_plan_event_id": approval_plan.get("fix_plan_event_id"),
            "quality_review_id": approval_plan.get("quality_review_id"),
            "package_id": approval_plan.get("package_id"),
            "source_approval_plan_status": approval_plan.get("status"),
            "evidence_summary": {
                "provided_sections": sorted(evidence_summary.get("provided_sections") or []),
                "provided_section_count": evidence_summary.get("provided_section_count", 0),
                "evidence_package_hash": evidence_summary.get("evidence_package_hash"),
                "record_bodies_included": bool(evidence_summary.get("record_bodies_included")),
                "evidence_package_body_included": False,
            },
            "source_approval_plan_summary": {
                "check_count": plan_summary.get("check_count", 0),
                "blocked_check_count": plan_summary.get("blocked_check_count", 0),
                "warning_check_count": plan_summary.get("warning_check_count", 0),
                "approval_step_count": plan_summary.get("approval_step_count", 0),
                "record_bodies_included": bool(plan_summary.get("record_bodies_included")),
            },
            "source_approval_plan": {
                "step_count": approval_plan_body.get("step_count", 0),
                "contains_sql": bool(approval_plan_body.get("contains_sql")),
                "contains_executable_code": bool(approval_plan_body.get("contains_executable_code")),
                "can_execute_now": bool(approval_plan_body.get("can_execute_now")),
                "requires_manual_execution_approval": bool(
                    approval_plan_body.get("requires_manual_execution_approval", True)
                ),
                "steps_body_included": False,
            },
            "checks": checks,
            "summary": {
                "check_count": len(checks),
                "blocked_check_count": blocked_count,
                "warning_check_count": warning_count,
                "source_plan_check_count": plan_summary.get("check_count", 0),
                "source_plan_blocked_check_count": plan_summary.get("blocked_check_count", 0),
                "approval_step_count": approval_plan_body.get("step_count", 0),
                "record_bodies_included": bool(evidence_summary.get("record_bodies_included"))
                or bool(plan_summary.get("record_bodies_included")),
            },
            "manual_approval": {
                "approved_by": approved_by or "operator",
                "approval_decision": approval_decision,
                "note": note,
                "record_bodies_included": False,
                "evidence_package_body_included": False,
                "review_only": True,
                "simulation_only": True,
            },
            "decision": {
                "writes_database_now": False,
                "writes_existing_event_now": True,
                "writes_staging_records_now": False,
                "writes_learning_samples_now": False,
                "mutates_staging_records_now": False,
                "cleanup_execution_manual_approval_recorded": True,
                "cleanup_execution_approval_metadata_accepted": approval_accepted,
                "cleanup_execution_approved_for_future_preflight": approval_accepted,
                "cleanup_execution_approved_now": False,
                "cleanup_application_allowed_now": False,
                "cleanup_executed_now": False,
                "can_execute_cleanup_now": False,
                "can_generate_cleanup_execution_preflight_now": approval_accepted,
                "future_cleanup_execution_preflight_required": True,
                "future_cleanup_execution_requires_separate_run": True,
                "can_promote_to_learning_samples_now": False,
                "training_started_now": False,
                "training_freeze_allowed": False,
                "can_start_training_now": False,
                "next_required_action": (
                    "resolve_cleanup_execution_manual_approval_blocks_before_any_cleanup_preflight"
                    if blocked_count
                    else "run_cleanup_execution_preflight_before_any_staging_mutation"
                ),
            },
            "source_approval_plan_decision": {
                "cleanup_execution_plan_ready_for_manual_approval": plan_decision.get(
                    "cleanup_execution_plan_ready_for_manual_approval"
                ),
                "cleanup_execution_approved_now": plan_decision.get("cleanup_execution_approved_now"),
                "cleanup_application_allowed_now": plan_decision.get("cleanup_application_allowed_now"),
                "cleanup_executed_now": plan_decision.get("cleanup_executed_now"),
                "writes_learning_samples_now": plan_decision.get("writes_learning_samples_now"),
                "training_started_now": plan_decision.get("training_started_now"),
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
                    self.staging_cleanup_execution_manual_approval_event_type,
                    json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str),
                ),
            )
            event_id = int(cursor.lastrowid)
        return {**payload, "event_id": event_id}

    def list_staging_cleanup_execution_manual_approvals(self, limit: int = 20) -> list[dict[str, Any]]:
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
            (self.staging_cleanup_execution_manual_approval_event_type, max(1, min(limit, 100))),
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

    def staging_cleanup_execution_preflight(
        self,
        manual_approval_id: int | None = None,
        requested_by: str = "operator",
        preflight_decision: str = "prepared_for_cleanup_execution_dry_run",
        note: str | None = None,
    ) -> dict[str, Any]:
        store = SQLiteStore(settings.database_path)
        store.init()
        manual_approval = (
            self._cleanup_execution_manual_approval_by_id(store, manual_approval_id)
            if manual_approval_id
            else self._latest_cleanup_execution_manual_approval(store)
        )
        if manual_approval is None:
            return {
                "schema_version": "dataset2_staging_cleanup_execution_preflight.v1",
                "stage": self.stage,
                "status": "cleanup_execution_preflight_blocked_missing_manual_approval",
                "generated_at": datetime.now().isoformat(timespec="seconds"),
                "manual_approval_id": manual_approval_id,
                "preflight": {
                    "lock_key": None,
                    "rollback_plan_required": True,
                    "contains_sql": False,
                    "contains_executable_code": False,
                    "can_execute_now": False,
                    "review_only": True,
                    "simulation_only": True,
                },
                "checks": [],
                "summary": {
                    "check_count": 0,
                    "blocked_check_count": 1,
                    "warning_check_count": 0,
                    "source_manual_approval_blocked_check_count": None,
                    "staging_record_count": 0,
                    "learning_sample_count": 0,
                    "record_bodies_included": False,
                },
                "decision": {
                    "writes_database_now": False,
                    "writes_existing_event_now": False,
                    "writes_staging_records_now": False,
                    "writes_learning_samples_now": False,
                    "mutates_staging_records_now": False,
                    "cleanup_execution_preflight_recorded": False,
                    "cleanup_execution_preflight_ready_for_dry_run": False,
                    "cleanup_execution_approved_now": False,
                    "cleanup_application_allowed_now": False,
                    "cleanup_executed_now": False,
                    "can_execute_cleanup_now": False,
                    "future_cleanup_execution_dry_run_required": True,
                    "can_promote_to_learning_samples_now": False,
                    "training_started_now": False,
                    "training_freeze_allowed": False,
                    "can_start_training_now": False,
                    "next_required_action": "record_dataset2_cleanup_execution_manual_approval_before_preflight",
                },
                "safety_summary": self._safety_summary(),
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            }

        package_id = manual_approval.get("package_id")
        staging_count = self._staging_record_count(store, package_id)
        learning_count = self._learning_sample_count(store)
        lock_key = self._cleanup_preflight_lock_key(manual_approval, staging_count)
        preflight = {
            "lock_key": lock_key,
            "rollback_plan_required": True,
            "rollback_plan": {
                "required": True,
                "mode": "future_transaction_rollback_or_restore_from_snapshot",
                "snapshot_required_before_execution": True,
                "verified_now": False,
            },
            "environment": {
                "database_path": str(settings.database_path),
                "database_path_recorded": bool(settings.database_path),
                "package_id": package_id,
                "staging_record_count": staging_count,
                "learning_sample_count": learning_count,
                "source_dataset_mutation_allowed": False,
            },
            "impact": {
                "package_id": package_id,
                "candidate_staging_record_count": staging_count,
                "learning_sample_count_before": learning_count,
                "expected_learning_sample_count_after": learning_count,
                "affected_rows_body_included": False,
            },
            "contains_sql": False,
            "contains_executable_code": False,
            "can_execute_now": False,
            "review_only": True,
            "simulation_only": True,
        }
        checks = self._cleanup_execution_preflight_checks(
            manual_approval,
            preflight=preflight,
            requested_by=requested_by,
            preflight_decision=preflight_decision,
        )
        blocked_count = sum(1 for check in checks if check.get("status") == "blocked")
        warning_count = sum(1 for check in checks if check.get("status") == "warning")
        ready_for_dry_run = blocked_count == 0 and preflight_decision == "prepared_for_cleanup_execution_dry_run"
        approval_summary = manual_approval.get("summary") or {}
        approval_decision = manual_approval.get("decision") or {}
        evidence_summary = manual_approval.get("evidence_summary") or {}
        payload = {
            "schema_version": "dataset2_staging_cleanup_execution_preflight.v1",
            "stage": self.stage,
            "status": (
                "cleanup_execution_preflight_ready_for_dry_run"
                if ready_for_dry_run
                else "cleanup_execution_preflight_blocked"
            ),
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "manual_approval_id": manual_approval.get("id"),
            "approval_plan_id": manual_approval.get("approval_plan_id"),
            "cleanup_application_review_id": manual_approval.get("cleanup_application_review_id"),
            "acceptance_review_id": manual_approval.get("acceptance_review_id"),
            "manual_evidence_verification_id": manual_approval.get("manual_evidence_verification_id"),
            "dry_run_verification_id": manual_approval.get("dry_run_verification_id"),
            "execution_spec_event_id": manual_approval.get("execution_spec_event_id"),
            "preflight_event_id": manual_approval.get("preflight_event_id"),
            "approval_event_id": manual_approval.get("approval_event_id"),
            "fix_plan_event_id": manual_approval.get("fix_plan_event_id"),
            "quality_review_id": manual_approval.get("quality_review_id"),
            "package_id": package_id,
            "source_manual_approval_status": manual_approval.get("status"),
            "evidence_summary": {
                "provided_sections": sorted(evidence_summary.get("provided_sections") or []),
                "provided_section_count": evidence_summary.get("provided_section_count", 0),
                "evidence_package_hash": evidence_summary.get("evidence_package_hash"),
                "record_bodies_included": bool(evidence_summary.get("record_bodies_included")),
                "evidence_package_body_included": False,
            },
            "source_manual_approval_summary": {
                "check_count": approval_summary.get("check_count", 0),
                "blocked_check_count": approval_summary.get("blocked_check_count", 0),
                "warning_check_count": approval_summary.get("warning_check_count", 0),
                "approval_step_count": approval_summary.get("approval_step_count", 0),
                "record_bodies_included": bool(approval_summary.get("record_bodies_included")),
            },
            "preflight": preflight,
            "checks": checks,
            "summary": {
                "check_count": len(checks),
                "blocked_check_count": blocked_count,
                "warning_check_count": warning_count,
                "source_manual_approval_check_count": approval_summary.get("check_count", 0),
                "source_manual_approval_blocked_check_count": approval_summary.get("blocked_check_count", 0),
                "staging_record_count": staging_count,
                "learning_sample_count": learning_count,
                "record_bodies_included": bool(evidence_summary.get("record_bodies_included"))
                or bool(approval_summary.get("record_bodies_included")),
            },
            "request": {
                "requested_by": requested_by or "operator",
                "preflight_decision": preflight_decision,
                "note": note,
                "record_bodies_included": False,
                "evidence_package_body_included": False,
                "review_only": True,
                "simulation_only": True,
            },
            "decision": {
                "writes_database_now": False,
                "writes_existing_event_now": True,
                "writes_staging_records_now": False,
                "writes_learning_samples_now": False,
                "mutates_staging_records_now": False,
                "cleanup_execution_preflight_recorded": True,
                "cleanup_execution_preflight_ready_for_dry_run": ready_for_dry_run,
                "cleanup_execution_approved_now": False,
                "cleanup_application_allowed_now": False,
                "cleanup_executed_now": False,
                "can_execute_cleanup_now": False,
                "future_cleanup_execution_dry_run_required": True,
                "future_cleanup_execution_requires_separate_run": True,
                "can_promote_to_learning_samples_now": False,
                "training_started_now": False,
                "training_freeze_allowed": False,
                "can_start_training_now": False,
                "next_required_action": (
                    "resolve_cleanup_execution_preflight_blocks_before_any_dry_run"
                    if blocked_count
                    else "run_cleanup_execution_dry_run_before_any_staging_mutation"
                ),
            },
            "source_manual_approval_decision": {
                "cleanup_execution_approval_metadata_accepted": approval_decision.get(
                    "cleanup_execution_approval_metadata_accepted"
                ),
                "cleanup_execution_approved_now": approval_decision.get("cleanup_execution_approved_now"),
                "cleanup_application_allowed_now": approval_decision.get("cleanup_application_allowed_now"),
                "cleanup_executed_now": approval_decision.get("cleanup_executed_now"),
                "writes_learning_samples_now": approval_decision.get("writes_learning_samples_now"),
                "training_started_now": approval_decision.get("training_started_now"),
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
                    self.staging_cleanup_execution_preflight_event_type,
                    json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str),
                ),
            )
            event_id = int(cursor.lastrowid)
        return {**payload, "event_id": event_id}

    def list_staging_cleanup_execution_preflights(self, limit: int = 20) -> list[dict[str, Any]]:
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
            (self.staging_cleanup_execution_preflight_event_type, max(1, min(limit, 100))),
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

    def staging_cleanup_execution_dry_run(
        self,
        preflight_id: int | None = None,
        simulated_by: str = "operator",
        dry_run_decision: str = "simulated_for_manual_review",
        note: str | None = None,
    ) -> dict[str, Any]:
        store = SQLiteStore(settings.database_path)
        store.init()
        preflight = (
            self._cleanup_execution_preflight_by_id(store, preflight_id)
            if preflight_id
            else self._latest_cleanup_execution_preflight(store)
        )
        if preflight is None:
            return {
                "schema_version": "dataset2_staging_cleanup_execution_dry_run.v1",
                "stage": self.stage,
                "status": "cleanup_execution_dry_run_blocked_missing_preflight",
                "generated_at": datetime.now().isoformat(timespec="seconds"),
                "preflight_id": preflight_id,
                "simulation": {
                    "candidate_record_count": 0,
                    "simulated_mutation_count": 0,
                    "contains_sql": False,
                    "contains_executable_code": False,
                    "can_execute_now": False,
                    "record_bodies_included": False,
                    "review_only": True,
                    "simulation_only": True,
                },
                "checks": [],
                "summary": {
                    "check_count": 0,
                    "blocked_check_count": 1,
                    "warning_check_count": 0,
                    "source_preflight_blocked_check_count": None,
                    "candidate_record_count": 0,
                    "simulated_mutation_count": 0,
                    "learning_sample_count": 0,
                    "record_bodies_included": False,
                },
                "decision": {
                    "writes_database_now": False,
                    "writes_existing_event_now": False,
                    "writes_staging_records_now": False,
                    "writes_learning_samples_now": False,
                    "mutates_staging_records_now": False,
                    "cleanup_execution_dry_run_recorded": False,
                    "cleanup_execution_dry_run_ready_for_review": False,
                    "cleanup_execution_approved_now": False,
                    "cleanup_application_allowed_now": False,
                    "cleanup_executed_now": False,
                    "can_execute_cleanup_now": False,
                    "future_cleanup_execution_review_required": True,
                    "can_promote_to_learning_samples_now": False,
                    "training_started_now": False,
                    "training_freeze_allowed": False,
                    "can_start_training_now": False,
                    "next_required_action": "run_dataset2_cleanup_execution_preflight_before_dry_run",
                },
                "safety_summary": self._safety_summary(),
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            }

        package_id = preflight.get("package_id")
        simulation = self._cleanup_execution_dry_run_simulation(store, package_id)
        checks = self._cleanup_execution_dry_run_checks(
            preflight,
            simulation=simulation,
            simulated_by=simulated_by,
            dry_run_decision=dry_run_decision,
        )
        blocked_count = sum(1 for check in checks if check.get("status") == "blocked")
        warning_count = sum(1 for check in checks if check.get("status") == "warning")
        ready_for_review = blocked_count == 0 and dry_run_decision == "simulated_for_manual_review"
        preflight_summary = preflight.get("summary") or {}
        preflight_decision = preflight.get("decision") or {}
        evidence_summary = preflight.get("evidence_summary") or {}
        payload = {
            "schema_version": "dataset2_staging_cleanup_execution_dry_run.v1",
            "stage": self.stage,
            "status": (
                "cleanup_execution_dry_run_ready_for_review"
                if ready_for_review
                else "cleanup_execution_dry_run_blocked"
            ),
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "preflight_id": preflight.get("id"),
            "manual_approval_id": preflight.get("manual_approval_id"),
            "approval_plan_id": preflight.get("approval_plan_id"),
            "cleanup_application_review_id": preflight.get("cleanup_application_review_id"),
            "acceptance_review_id": preflight.get("acceptance_review_id"),
            "manual_evidence_verification_id": preflight.get("manual_evidence_verification_id"),
            "dry_run_verification_id": preflight.get("dry_run_verification_id"),
            "execution_spec_event_id": preflight.get("execution_spec_event_id"),
            "preflight_event_id": preflight.get("preflight_event_id"),
            "approval_event_id": preflight.get("approval_event_id"),
            "fix_plan_event_id": preflight.get("fix_plan_event_id"),
            "quality_review_id": preflight.get("quality_review_id"),
            "package_id": package_id,
            "source_preflight_status": preflight.get("status"),
            "evidence_summary": {
                "provided_sections": sorted(evidence_summary.get("provided_sections") or []),
                "provided_section_count": evidence_summary.get("provided_section_count", 0),
                "evidence_package_hash": evidence_summary.get("evidence_package_hash"),
                "record_bodies_included": bool(evidence_summary.get("record_bodies_included")),
                "evidence_package_body_included": False,
            },
            "source_preflight_summary": {
                "check_count": preflight_summary.get("check_count", 0),
                "blocked_check_count": preflight_summary.get("blocked_check_count", 0),
                "warning_check_count": preflight_summary.get("warning_check_count", 0),
                "staging_record_count": preflight_summary.get("staging_record_count", 0),
                "learning_sample_count": preflight_summary.get("learning_sample_count", 0),
                "record_bodies_included": bool(preflight_summary.get("record_bodies_included")),
            },
            "simulation": simulation,
            "checks": checks,
            "summary": {
                "check_count": len(checks),
                "blocked_check_count": blocked_count,
                "warning_check_count": warning_count,
                "source_preflight_check_count": preflight_summary.get("check_count", 0),
                "source_preflight_blocked_check_count": preflight_summary.get("blocked_check_count", 0),
                "candidate_record_count": simulation.get("candidate_record_count", 0),
                "simulated_mutation_count": simulation.get("simulated_mutation_count", 0),
                "learning_sample_count": simulation.get("learning_sample_count_before", 0),
                "record_bodies_included": False,
            },
            "dry_run": {
                "simulated_by": simulated_by or "operator",
                "dry_run_decision": dry_run_decision,
                "note": note,
                "record_bodies_included": False,
                "evidence_package_body_included": False,
                "review_only": True,
                "simulation_only": True,
            },
            "decision": {
                "writes_database_now": False,
                "writes_existing_event_now": True,
                "writes_staging_records_now": False,
                "writes_learning_samples_now": False,
                "mutates_staging_records_now": False,
                "cleanup_execution_dry_run_recorded": True,
                "cleanup_execution_dry_run_ready_for_review": ready_for_review,
                "cleanup_execution_approved_now": False,
                "cleanup_application_allowed_now": False,
                "cleanup_executed_now": False,
                "can_execute_cleanup_now": False,
                "future_cleanup_execution_review_required": True,
                "future_cleanup_execution_requires_separate_run": True,
                "can_promote_to_learning_samples_now": False,
                "training_started_now": False,
                "training_freeze_allowed": False,
                "can_start_training_now": False,
                "next_required_action": (
                    "resolve_cleanup_execution_dry_run_blocks_before_manual_execution_review"
                    if blocked_count
                    else "review_cleanup_execution_dry_run_before_any_staging_mutation"
                ),
            },
            "source_preflight_decision": {
                "cleanup_execution_preflight_ready_for_dry_run": preflight_decision.get(
                    "cleanup_execution_preflight_ready_for_dry_run"
                ),
                "cleanup_execution_approved_now": preflight_decision.get("cleanup_execution_approved_now"),
                "cleanup_application_allowed_now": preflight_decision.get("cleanup_application_allowed_now"),
                "cleanup_executed_now": preflight_decision.get("cleanup_executed_now"),
                "writes_learning_samples_now": preflight_decision.get("writes_learning_samples_now"),
                "training_started_now": preflight_decision.get("training_started_now"),
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
                    self.staging_cleanup_execution_dry_run_event_type,
                    json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str),
                ),
            )
            event_id = int(cursor.lastrowid)
        return {**payload, "event_id": event_id}

    def list_staging_cleanup_execution_dry_runs(self, limit: int = 20) -> list[dict[str, Any]]:
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
            (self.staging_cleanup_execution_dry_run_event_type, max(1, min(limit, 100))),
        )
        dry_runs: list[dict[str, Any]] = []
        for row in rows:
            payload = json.loads(row.pop("payload_json") or "{}")
            dry_runs.append(
                {
                    "id": row["id"],
                    "event_type": row["event_type"],
                    "created_at": row["created_at"],
                    **payload,
                }
            )
        return dry_runs

    def staging_cleanup_execution_dry_run_review(
        self,
        dry_run_id: int | None = None,
        reviewed_by: str = "operator",
        review_decision: str = "approved_for_cleanup_execution_plan",
        note: str | None = None,
    ) -> dict[str, Any]:
        store = SQLiteStore(settings.database_path)
        store.init()
        dry_run = (
            self._cleanup_execution_dry_run_by_id(store, dry_run_id)
            if dry_run_id
            else self._latest_cleanup_execution_dry_run(store)
        )
        if dry_run is None:
            return {
                "schema_version": "dataset2_staging_cleanup_execution_dry_run_review.v1",
                "stage": self.stage,
                "status": "cleanup_execution_dry_run_review_blocked_missing_dry_run",
                "generated_at": datetime.now().isoformat(timespec="seconds"),
                "dry_run_id": dry_run_id,
                "source_dry_run_status": None,
                "evidence_summary": {
                    "evidence_package_hash": None,
                    "record_bodies_included": False,
                    "evidence_package_body_included": False,
                },
                "source_dry_run_summary": {
                    "check_count": 0,
                    "blocked_check_count": None,
                    "candidate_record_count": 0,
                    "simulated_mutation_count": 0,
                    "record_bodies_included": False,
                },
                "simulation_summary": {
                    "candidate_record_count": 0,
                    "simulated_mutation_count": 0,
                    "contains_sql": False,
                    "contains_executable_code": False,
                    "can_execute_now": False,
                    "record_bodies_included": False,
                    "affected_rows_body_included": False,
                    "learning_sample_count_before": 0,
                    "expected_learning_sample_count_after": 0,
                },
                "checks": [],
                "summary": {
                    "check_count": 0,
                    "blocked_check_count": 1,
                    "warning_check_count": 0,
                    "source_dry_run_blocked_check_count": None,
                    "candidate_record_count": 0,
                    "simulated_mutation_count": 0,
                    "record_bodies_included": False,
                },
                "review": {
                    "reviewed_by": reviewed_by or "operator",
                    "review_decision": review_decision,
                    "note": note,
                    "record_bodies_included": False,
                    "evidence_package_body_included": False,
                    "review_only": True,
                    "simulation_only": True,
                },
                "decision": {
                    "writes_database_now": False,
                    "writes_existing_event_now": False,
                    "writes_staging_records_now": False,
                    "writes_learning_samples_now": False,
                    "mutates_staging_records_now": False,
                    "cleanup_execution_dry_run_review_recorded": False,
                    "cleanup_execution_dry_run_review_accepted": False,
                    "cleanup_execution_approved_now": False,
                    "cleanup_application_allowed_now": False,
                    "cleanup_executed_now": False,
                    "can_execute_cleanup_now": False,
                    "future_cleanup_execution_plan_required": True,
                    "can_promote_to_learning_samples_now": False,
                    "training_started_now": False,
                    "training_freeze_allowed": False,
                    "can_start_training_now": False,
                    "next_required_action": "run_dataset2_cleanup_execution_dry_run_before_manual_review",
                },
                "safety_summary": self._safety_summary(),
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            }

        simulation = dry_run.get("simulation") or {}
        dry_run_summary = dry_run.get("summary") or {}
        checks = self._cleanup_execution_dry_run_review_checks(
            dry_run,
            reviewed_by=reviewed_by,
            review_decision=review_decision,
        )
        blocked_count = sum(1 for check in checks if check.get("status") == "blocked")
        warning_count = sum(1 for check in checks if check.get("status") == "warning")
        accepted = blocked_count == 0 and review_decision == "approved_for_cleanup_execution_plan"
        evidence_summary = dry_run.get("evidence_summary") or {}
        payload = {
            "schema_version": "dataset2_staging_cleanup_execution_dry_run_review.v1",
            "stage": self.stage,
            "status": (
                "cleanup_execution_dry_run_review_accepted"
                if accepted
                else "cleanup_execution_dry_run_review_blocked"
            ),
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "dry_run_id": dry_run.get("id"),
            "preflight_id": dry_run.get("preflight_id"),
            "manual_approval_id": dry_run.get("manual_approval_id"),
            "approval_plan_id": dry_run.get("approval_plan_id"),
            "cleanup_application_review_id": dry_run.get("cleanup_application_review_id"),
            "acceptance_review_id": dry_run.get("acceptance_review_id"),
            "manual_evidence_verification_id": dry_run.get("manual_evidence_verification_id"),
            "dry_run_verification_id": dry_run.get("dry_run_verification_id"),
            "execution_spec_event_id": dry_run.get("execution_spec_event_id"),
            "package_id": dry_run.get("package_id"),
            "source_dry_run_status": dry_run.get("status"),
            "evidence_summary": {
                "provided_sections": sorted(evidence_summary.get("provided_sections") or []),
                "provided_section_count": evidence_summary.get("provided_section_count", 0),
                "evidence_package_hash": evidence_summary.get("evidence_package_hash"),
                "record_bodies_included": bool(evidence_summary.get("record_bodies_included")),
                "evidence_package_body_included": False,
            },
            "source_dry_run_summary": {
                "check_count": dry_run_summary.get("check_count", 0),
                "blocked_check_count": dry_run_summary.get("blocked_check_count", 0),
                "warning_check_count": dry_run_summary.get("warning_check_count", 0),
                "source_preflight_blocked_check_count": dry_run_summary.get("source_preflight_blocked_check_count"),
                "candidate_record_count": dry_run_summary.get("candidate_record_count", 0),
                "simulated_mutation_count": dry_run_summary.get("simulated_mutation_count", 0),
                "learning_sample_count": dry_run_summary.get("learning_sample_count", 0),
                "record_bodies_included": False,
            },
            "simulation_summary": {
                "candidate_record_count": simulation.get("candidate_record_count", 0),
                "records_with_operations": simulation.get("records_with_operations", 0),
                "records_with_quality_flags": simulation.get("records_with_quality_flags", 0),
                "simulated_mutation_count": simulation.get("simulated_mutation_count", 0),
                "operation_counts": simulation.get("operation_counts", {}),
                "field_counts": simulation.get("field_counts", {}),
                "quality_flag_counts": simulation.get("quality_flag_counts", {}),
                "learning_sample_count_before": simulation.get("learning_sample_count_before", 0),
                "expected_learning_sample_count_after": simulation.get("expected_learning_sample_count_after", 0),
                "contains_sql": bool(simulation.get("contains_sql")),
                "contains_executable_code": bool(simulation.get("contains_executable_code")),
                "can_execute_now": bool(simulation.get("can_execute_now")),
                "record_bodies_included": bool(simulation.get("record_bodies_included")),
                "affected_rows_body_included": bool(simulation.get("affected_rows_body_included")),
            },
            "checks": checks,
            "summary": {
                "check_count": len(checks),
                "blocked_check_count": blocked_count,
                "warning_check_count": warning_count,
                "source_dry_run_check_count": dry_run_summary.get("check_count", 0),
                "source_dry_run_blocked_check_count": dry_run_summary.get("blocked_check_count", 0),
                "candidate_record_count": simulation.get("candidate_record_count", 0),
                "simulated_mutation_count": simulation.get("simulated_mutation_count", 0),
                "learning_sample_count": simulation.get("learning_sample_count_before", 0),
                "record_bodies_included": False,
            },
            "review": {
                "reviewed_by": reviewed_by or "operator",
                "review_decision": review_decision,
                "note": note,
                "record_bodies_included": False,
                "evidence_package_body_included": False,
                "review_only": True,
                "simulation_only": True,
            },
            "decision": {
                "writes_database_now": False,
                "writes_existing_event_now": True,
                "writes_staging_records_now": False,
                "writes_learning_samples_now": False,
                "mutates_staging_records_now": False,
                "cleanup_execution_dry_run_review_recorded": True,
                "cleanup_execution_dry_run_review_accepted": accepted,
                "cleanup_execution_approved_now": False,
                "cleanup_application_allowed_now": False,
                "cleanup_executed_now": False,
                "can_execute_cleanup_now": False,
                "future_cleanup_execution_plan_required": True,
                "future_cleanup_execution_requires_separate_run": True,
                "can_promote_to_learning_samples_now": False,
                "training_started_now": False,
                "training_freeze_allowed": False,
                "can_start_training_now": False,
                "next_required_action": (
                    "resolve_cleanup_execution_dry_run_review_blocks_before_cleanup_plan"
                    if blocked_count
                    else "create_separate_cleanup_execution_plan_before_any_staging_mutation"
                ),
            },
            "source_dry_run_decision": {
                "cleanup_execution_dry_run_ready_for_review": (dry_run.get("decision") or {}).get(
                    "cleanup_execution_dry_run_ready_for_review"
                ),
                "cleanup_execution_approved_now": (dry_run.get("decision") or {}).get("cleanup_execution_approved_now"),
                "cleanup_application_allowed_now": (dry_run.get("decision") or {}).get(
                    "cleanup_application_allowed_now"
                ),
                "cleanup_executed_now": (dry_run.get("decision") or {}).get("cleanup_executed_now"),
                "can_execute_cleanup_now": (dry_run.get("decision") or {}).get("can_execute_cleanup_now"),
                "writes_learning_samples_now": (dry_run.get("decision") or {}).get("writes_learning_samples_now"),
                "training_started_now": (dry_run.get("decision") or {}).get("training_started_now"),
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
                    self.staging_cleanup_execution_dry_run_review_event_type,
                    json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str),
                ),
            )
            event_id = int(cursor.lastrowid)
        return {**payload, "event_id": event_id}

    def list_staging_cleanup_execution_dry_run_reviews(self, limit: int = 20) -> list[dict[str, Any]]:
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
            (self.staging_cleanup_execution_dry_run_review_event_type, max(1, min(limit, 100))),
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

    def staging_cleanup_execution_plan(
        self,
        dry_run_review_id: int | None = None,
        planned_by: str = "operator",
        plan_decision: str = "prepared_for_controlled_cleanup_execution_preflight",
        note: str | None = None,
    ) -> dict[str, Any]:
        store = SQLiteStore(settings.database_path)
        store.init()
        review = (
            self._cleanup_execution_dry_run_review_by_id(store, dry_run_review_id)
            if dry_run_review_id
            else self._latest_cleanup_execution_dry_run_review(store)
        )
        if review is None:
            return {
                "schema_version": "dataset2_staging_cleanup_execution_plan.v1",
                "stage": self.stage,
                "status": "cleanup_execution_plan_blocked_missing_dry_run_review",
                "generated_at": datetime.now().isoformat(timespec="seconds"),
                "dry_run_review_id": dry_run_review_id,
                "source_review_status": None,
                "execution_plan": self._empty_cleanup_execution_plan(),
                "checks": [],
                "summary": {
                    "check_count": 0,
                    "blocked_check_count": 1,
                    "warning_check_count": 0,
                    "candidate_record_count": 0,
                    "planned_operation_count": 0,
                    "automated_operation_count": 0,
                    "manual_operation_count": 0,
                    "record_bodies_included": False,
                },
                "planning": {
                    "planned_by": planned_by or "operator",
                    "plan_decision": plan_decision,
                    "note": note,
                    "record_bodies_included": False,
                    "review_only": True,
                    "simulation_only": True,
                },
                "decision": {
                    "writes_database_now": False,
                    "writes_existing_event_now": False,
                    "writes_staging_records_now": False,
                    "writes_learning_samples_now": False,
                    "mutates_staging_records_now": False,
                    "cleanup_execution_plan_recorded": False,
                    "cleanup_execution_plan_ready_for_preflight": False,
                    "cleanup_execution_approved_now": False,
                    "cleanup_application_allowed_now": False,
                    "cleanup_executed_now": False,
                    "can_execute_cleanup_now": False,
                    "manual_backfill_required": False,
                    "can_promote_to_learning_samples_now": False,
                    "training_started_now": False,
                    "training_freeze_allowed": False,
                    "can_start_training_now": False,
                    "next_required_action": "review_dataset2_cleanup_execution_dry_run_before_planning",
                },
                "safety_summary": self._safety_summary(),
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            }

        execution_plan = self._cleanup_execution_plan_from_review(review)
        checks = self._cleanup_execution_plan_checks(
            review,
            execution_plan=execution_plan,
            planned_by=planned_by,
            plan_decision=plan_decision,
        )
        blocked_count = sum(1 for check in checks if check.get("status") == "blocked")
        warning_count = sum(1 for check in checks if check.get("status") == "warning")
        ready_for_preflight = blocked_count == 0 and plan_decision == "prepared_for_controlled_cleanup_execution_preflight"
        evidence_summary = review.get("evidence_summary") or {}
        payload = {
            "schema_version": "dataset2_staging_cleanup_execution_plan.v1",
            "stage": self.stage,
            "status": (
                "cleanup_execution_plan_ready_for_preflight"
                if ready_for_preflight
                else "cleanup_execution_plan_blocked"
            ),
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "dry_run_review_id": review.get("id"),
            "dry_run_id": review.get("dry_run_id"),
            "preflight_id": review.get("preflight_id"),
            "manual_approval_id": review.get("manual_approval_id"),
            "approval_plan_id": review.get("approval_plan_id"),
            "cleanup_application_review_id": review.get("cleanup_application_review_id"),
            "package_id": review.get("package_id"),
            "source_review_status": review.get("status"),
            "evidence_summary": {
                "provided_sections": sorted(evidence_summary.get("provided_sections") or []),
                "provided_section_count": evidence_summary.get("provided_section_count", 0),
                "evidence_package_hash": evidence_summary.get("evidence_package_hash"),
                "record_bodies_included": bool(evidence_summary.get("record_bodies_included")),
                "evidence_package_body_included": False,
            },
            "source_review_summary": {
                "check_count": (review.get("summary") or {}).get("check_count", 0),
                "blocked_check_count": (review.get("summary") or {}).get("blocked_check_count", 0),
                "warning_check_count": (review.get("summary") or {}).get("warning_check_count", 0),
                "candidate_record_count": (review.get("summary") or {}).get("candidate_record_count", 0),
                "simulated_mutation_count": (review.get("summary") or {}).get("simulated_mutation_count", 0),
                "record_bodies_included": False,
            },
            "execution_plan": execution_plan,
            "checks": checks,
            "summary": {
                "check_count": len(checks),
                "blocked_check_count": blocked_count,
                "warning_check_count": warning_count,
                "source_review_blocked_check_count": (review.get("summary") or {}).get("blocked_check_count", 0),
                "candidate_record_count": execution_plan.get("candidate_record_count", 0),
                "planned_operation_count": execution_plan.get("planned_operation_count", 0),
                "automated_operation_count": execution_plan.get("automated_operation_count", 0),
                "manual_operation_count": execution_plan.get("manual_operation_count", 0),
                "record_bodies_included": False,
            },
            "planning": {
                "planned_by": planned_by or "operator",
                "plan_decision": plan_decision,
                "note": note,
                "record_bodies_included": False,
                "evidence_package_body_included": False,
                "review_only": True,
                "simulation_only": True,
            },
            "decision": {
                "writes_database_now": False,
                "writes_existing_event_now": True,
                "writes_staging_records_now": False,
                "writes_learning_samples_now": False,
                "mutates_staging_records_now": False,
                "cleanup_execution_plan_recorded": True,
                "cleanup_execution_plan_ready_for_preflight": ready_for_preflight,
                "cleanup_execution_approved_now": False,
                "cleanup_application_allowed_now": False,
                "cleanup_executed_now": False,
                "can_execute_cleanup_now": False,
                "future_cleanup_execution_preflight_required": True,
                "future_cleanup_execution_requires_separate_run": True,
                "manual_backfill_required": execution_plan.get("manual_operation_count", 0) > 0,
                "can_promote_to_learning_samples_now": False,
                "training_started_now": False,
                "training_freeze_allowed": False,
                "can_start_training_now": False,
                "next_required_action": (
                    "resolve_cleanup_execution_plan_blocks_before_preflight"
                    if blocked_count
                    else "run_controlled_cleanup_execution_preflight_before_any_staging_mutation"
                ),
            },
            "source_review_decision": {
                "cleanup_execution_dry_run_review_accepted": (review.get("decision") or {}).get(
                    "cleanup_execution_dry_run_review_accepted"
                ),
                "cleanup_execution_approved_now": (review.get("decision") or {}).get("cleanup_execution_approved_now"),
                "cleanup_application_allowed_now": (review.get("decision") or {}).get(
                    "cleanup_application_allowed_now"
                ),
                "cleanup_executed_now": (review.get("decision") or {}).get("cleanup_executed_now"),
                "can_execute_cleanup_now": (review.get("decision") or {}).get("can_execute_cleanup_now"),
                "writes_learning_samples_now": (review.get("decision") or {}).get("writes_learning_samples_now"),
                "training_started_now": (review.get("decision") or {}).get("training_started_now"),
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
                    self.staging_cleanup_execution_plan_event_type,
                    json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str),
                ),
            )
            event_id = int(cursor.lastrowid)
        return {**payload, "event_id": event_id}

    def list_staging_cleanup_execution_plans(self, limit: int = 20) -> list[dict[str, Any]]:
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
            (self.staging_cleanup_execution_plan_event_type, max(1, min(limit, 100))),
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

    def staging_cleanup_execution_plan_preflight(
        self,
        execution_plan_id: int | None = None,
        requested_by: str = "operator",
        preflight_decision: str = "prepared_for_controlled_cleanup_execution_dry_run",
        note: str | None = None,
    ) -> dict[str, Any]:
        store = SQLiteStore(settings.database_path)
        store.init()
        plan = (
            self._cleanup_execution_plan_by_id(store, execution_plan_id)
            if execution_plan_id
            else self._latest_cleanup_execution_plan(store)
        )
        if plan is None:
            return {
                "schema_version": "dataset2_staging_cleanup_execution_plan_preflight.v1",
                "stage": self.stage,
                "status": "cleanup_execution_plan_preflight_blocked_missing_plan",
                "generated_at": datetime.now().isoformat(timespec="seconds"),
                "execution_plan_id": execution_plan_id,
                "source_plan_status": None,
                "preflight": self._empty_cleanup_execution_plan_preflight(),
                "checks": [],
                "summary": {
                    "check_count": 0,
                    "blocked_check_count": 1,
                    "warning_check_count": 0,
                    "staging_record_count": 0,
                    "learning_sample_count": 0,
                    "automated_operation_count": 0,
                    "manual_operation_count": 0,
                    "record_bodies_included": False,
                },
                "request": {
                    "requested_by": requested_by or "operator",
                    "preflight_decision": preflight_decision,
                    "note": note,
                    "record_bodies_included": False,
                    "review_only": True,
                    "simulation_only": True,
                },
                "decision": {
                    "writes_database_now": False,
                    "writes_existing_event_now": False,
                    "writes_staging_records_now": False,
                    "writes_learning_samples_now": False,
                    "mutates_staging_records_now": False,
                    "cleanup_execution_plan_preflight_recorded": False,
                    "cleanup_execution_plan_preflight_ready_for_dry_run": False,
                    "cleanup_execution_approved_now": False,
                    "cleanup_application_allowed_now": False,
                    "cleanup_executed_now": False,
                    "can_execute_cleanup_now": False,
                    "future_controlled_cleanup_dry_run_required": True,
                    "can_promote_to_learning_samples_now": False,
                    "training_started_now": False,
                    "training_freeze_allowed": False,
                    "can_start_training_now": False,
                    "next_required_action": "create_dataset2_cleanup_execution_plan_before_preflight",
                },
                "safety_summary": self._safety_summary(),
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            }

        execution_plan = plan.get("execution_plan") or {}
        preflight = self._cleanup_execution_plan_preflight_snapshot(store, plan)
        checks = self._cleanup_execution_plan_preflight_checks(
            plan,
            preflight=preflight,
            requested_by=requested_by,
            preflight_decision=preflight_decision,
        )
        blocked_count = sum(1 for check in checks if check.get("status") == "blocked")
        warning_count = sum(1 for check in checks if check.get("status") == "warning")
        ready_for_dry_run = blocked_count == 0 and preflight_decision == "prepared_for_controlled_cleanup_execution_dry_run"
        evidence_summary = plan.get("evidence_summary") or {}
        payload = {
            "schema_version": "dataset2_staging_cleanup_execution_plan_preflight.v1",
            "stage": self.stage,
            "status": (
                "cleanup_execution_plan_preflight_ready_for_dry_run"
                if ready_for_dry_run
                else "cleanup_execution_plan_preflight_blocked"
            ),
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "execution_plan_id": plan.get("id"),
            "dry_run_review_id": plan.get("dry_run_review_id"),
            "dry_run_id": plan.get("dry_run_id"),
            "preflight_id": plan.get("preflight_id"),
            "manual_approval_id": plan.get("manual_approval_id"),
            "approval_plan_id": plan.get("approval_plan_id"),
            "cleanup_application_review_id": plan.get("cleanup_application_review_id"),
            "package_id": plan.get("package_id"),
            "source_plan_status": plan.get("status"),
            "evidence_summary": {
                "provided_sections": sorted(evidence_summary.get("provided_sections") or []),
                "provided_section_count": evidence_summary.get("provided_section_count", 0),
                "evidence_package_hash": evidence_summary.get("evidence_package_hash"),
                "record_bodies_included": bool(evidence_summary.get("record_bodies_included")),
                "evidence_package_body_included": False,
            },
            "source_plan_summary": {
                "check_count": (plan.get("summary") or {}).get("check_count", 0),
                "blocked_check_count": (plan.get("summary") or {}).get("blocked_check_count", 0),
                "warning_check_count": (plan.get("summary") or {}).get("warning_check_count", 0),
                "candidate_record_count": (plan.get("summary") or {}).get("candidate_record_count", 0),
                "automated_operation_count": (plan.get("summary") or {}).get("automated_operation_count", 0),
                "manual_operation_count": (plan.get("summary") or {}).get("manual_operation_count", 0),
                "record_bodies_included": False,
            },
            "preflight": preflight,
            "checks": checks,
            "summary": {
                "check_count": len(checks),
                "blocked_check_count": blocked_count,
                "warning_check_count": warning_count,
                "source_plan_blocked_check_count": (plan.get("summary") or {}).get("blocked_check_count", 0),
                "staging_record_count": preflight.get("staging_record_count", 0),
                "learning_sample_count": preflight.get("learning_sample_count", 0),
                "automated_operation_count": execution_plan.get("automated_operation_count", 0),
                "manual_operation_count": execution_plan.get("manual_operation_count", 0),
                "record_bodies_included": False,
            },
            "request": {
                "requested_by": requested_by or "operator",
                "preflight_decision": preflight_decision,
                "note": note,
                "record_bodies_included": False,
                "evidence_package_body_included": False,
                "review_only": True,
                "simulation_only": True,
            },
            "decision": {
                "writes_database_now": False,
                "writes_existing_event_now": True,
                "writes_staging_records_now": False,
                "writes_learning_samples_now": False,
                "mutates_staging_records_now": False,
                "cleanup_execution_plan_preflight_recorded": True,
                "cleanup_execution_plan_preflight_ready_for_dry_run": ready_for_dry_run,
                "cleanup_execution_approved_now": False,
                "cleanup_application_allowed_now": False,
                "cleanup_executed_now": False,
                "can_execute_cleanup_now": False,
                "future_controlled_cleanup_dry_run_required": True,
                "future_cleanup_execution_requires_separate_run": True,
                "can_promote_to_learning_samples_now": False,
                "training_started_now": False,
                "training_freeze_allowed": False,
                "can_start_training_now": False,
                "next_required_action": (
                    "resolve_cleanup_execution_plan_preflight_blocks_before_dry_run"
                    if blocked_count
                    else "run_controlled_cleanup_execution_dry_run_before_any_staging_mutation"
                ),
            },
            "source_plan_decision": {
                "cleanup_execution_plan_ready_for_preflight": (plan.get("decision") or {}).get(
                    "cleanup_execution_plan_ready_for_preflight"
                ),
                "cleanup_execution_approved_now": (plan.get("decision") or {}).get("cleanup_execution_approved_now"),
                "cleanup_application_allowed_now": (plan.get("decision") or {}).get("cleanup_application_allowed_now"),
                "cleanup_executed_now": (plan.get("decision") or {}).get("cleanup_executed_now"),
                "can_execute_cleanup_now": (plan.get("decision") or {}).get("can_execute_cleanup_now"),
                "writes_learning_samples_now": (plan.get("decision") or {}).get("writes_learning_samples_now"),
                "training_started_now": (plan.get("decision") or {}).get("training_started_now"),
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
                    self.staging_cleanup_execution_plan_preflight_event_type,
                    json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str),
                ),
            )
            event_id = int(cursor.lastrowid)
        return {**payload, "event_id": event_id}

    def list_staging_cleanup_execution_plan_preflights(self, limit: int = 20) -> list[dict[str, Any]]:
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
            (self.staging_cleanup_execution_plan_preflight_event_type, max(1, min(limit, 100))),
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

    def staging_cleanup_execution_controlled_dry_run(
        self,
        plan_preflight_id: int | None = None,
        simulated_by: str = "operator",
        dry_run_decision: str = "simulated_for_controlled_cleanup_review",
        note: str | None = None,
    ) -> dict[str, Any]:
        store = SQLiteStore(settings.database_path)
        store.init()
        plan_preflight = (
            self._cleanup_execution_plan_preflight_by_id(store, plan_preflight_id)
            if plan_preflight_id
            else self._latest_cleanup_execution_plan_preflight(store)
        )
        if plan_preflight is None:
            return {
                "schema_version": "dataset2_staging_cleanup_execution_controlled_dry_run.v1",
                "stage": self.stage,
                "status": "controlled_cleanup_dry_run_blocked_missing_preflight",
                "generated_at": datetime.now().isoformat(timespec="seconds"),
                "plan_preflight_id": plan_preflight_id,
                "source_preflight_status": None,
                "simulation": self._empty_controlled_cleanup_dry_run_simulation(),
                "checks": [],
                "summary": {
                    "check_count": 0,
                    "blocked_check_count": 1,
                    "warning_check_count": 0,
                    "staging_record_count_before": 0,
                    "expected_staging_record_count_after": 0,
                    "automated_operation_count": 0,
                    "manual_operation_count": 0,
                    "simulated_mutation_count": 0,
                    "record_bodies_included": False,
                },
                "dry_run": {
                    "simulated_by": simulated_by or "operator",
                    "dry_run_decision": dry_run_decision,
                    "note": note,
                    "record_bodies_included": False,
                    "evidence_package_body_included": False,
                    "review_only": True,
                    "simulation_only": True,
                },
                "decision": {
                    "writes_database_now": False,
                    "writes_existing_event_now": False,
                    "writes_staging_records_now": False,
                    "writes_learning_samples_now": False,
                    "mutates_staging_records_now": False,
                    "controlled_cleanup_dry_run_recorded": False,
                    "controlled_cleanup_dry_run_ready_for_review": False,
                    "cleanup_execution_approved_now": False,
                    "cleanup_application_allowed_now": False,
                    "cleanup_executed_now": False,
                    "can_execute_cleanup_now": False,
                    "future_controlled_cleanup_review_required": True,
                    "can_promote_to_learning_samples_now": False,
                    "training_started_now": False,
                    "training_freeze_allowed": False,
                    "can_start_training_now": False,
                    "next_required_action": "run_dataset2_cleanup_execution_plan_preflight_before_controlled_dry_run",
                },
                "safety_summary": self._safety_summary(),
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            }

        simulation = self._controlled_cleanup_dry_run_simulation(store, plan_preflight)
        checks = self._controlled_cleanup_dry_run_checks(
            plan_preflight,
            simulation=simulation,
            simulated_by=simulated_by,
            dry_run_decision=dry_run_decision,
        )
        blocked_count = sum(1 for check in checks if check.get("status") == "blocked")
        warning_count = sum(1 for check in checks if check.get("status") == "warning")
        ready_for_review = blocked_count == 0 and dry_run_decision == "simulated_for_controlled_cleanup_review"
        payload = {
            "schema_version": "dataset2_staging_cleanup_execution_controlled_dry_run.v1",
            "stage": self.stage,
            "status": "controlled_cleanup_dry_run_ready_for_review" if ready_for_review else "controlled_cleanup_dry_run_blocked",
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "plan_preflight_id": plan_preflight.get("id"),
            "execution_plan_id": plan_preflight.get("execution_plan_id"),
            "dry_run_review_id": plan_preflight.get("dry_run_review_id"),
            "dry_run_id": plan_preflight.get("dry_run_id"),
            "preflight_id": plan_preflight.get("preflight_id"),
            "manual_approval_id": plan_preflight.get("manual_approval_id"),
            "package_id": plan_preflight.get("package_id"),
            "source_preflight_status": plan_preflight.get("status"),
            "source_preflight_summary": {
                "check_count": (plan_preflight.get("summary") or {}).get("check_count", 0),
                "blocked_check_count": (plan_preflight.get("summary") or {}).get("blocked_check_count", 0),
                "warning_check_count": (plan_preflight.get("summary") or {}).get("warning_check_count", 0),
                "staging_record_count": (plan_preflight.get("summary") or {}).get("staging_record_count", 0),
                "automated_operation_count": (plan_preflight.get("summary") or {}).get("automated_operation_count", 0),
                "manual_operation_count": (plan_preflight.get("summary") or {}).get("manual_operation_count", 0),
                "record_bodies_included": False,
            },
            "simulation": simulation,
            "checks": checks,
            "summary": {
                "check_count": len(checks),
                "blocked_check_count": blocked_count,
                "warning_check_count": warning_count,
                "source_preflight_blocked_check_count": (plan_preflight.get("summary") or {}).get("blocked_check_count", 0),
                "staging_record_count_before": simulation.get("staging_record_count_before", 0),
                "expected_staging_record_count_after": simulation.get("expected_staging_record_count_after", 0),
                "learning_sample_count_before": simulation.get("learning_sample_count_before", 0),
                "expected_learning_sample_count_after": simulation.get("expected_learning_sample_count_after", 0),
                "automated_operation_count": simulation.get("automated_operation_count", 0),
                "manual_operation_count": simulation.get("manual_operation_count", 0),
                "simulated_quality_flag_reduction_count": simulation.get("simulated_quality_flag_reduction_count", 0),
                "simulated_manual_flag_remaining_count": simulation.get("simulated_manual_flag_remaining_count", 0),
                "simulated_mutation_count": simulation.get("simulated_mutation_count", 0),
                "record_bodies_included": False,
            },
            "dry_run": {
                "simulated_by": simulated_by or "operator",
                "dry_run_decision": dry_run_decision,
                "note": note,
                "record_bodies_included": False,
                "evidence_package_body_included": False,
                "review_only": True,
                "simulation_only": True,
            },
            "decision": {
                "writes_database_now": False,
                "writes_existing_event_now": True,
                "writes_staging_records_now": False,
                "writes_learning_samples_now": False,
                "mutates_staging_records_now": False,
                "controlled_cleanup_dry_run_recorded": True,
                "controlled_cleanup_dry_run_ready_for_review": ready_for_review,
                "cleanup_execution_approved_now": False,
                "cleanup_application_allowed_now": False,
                "cleanup_executed_now": False,
                "can_execute_cleanup_now": False,
                "future_controlled_cleanup_review_required": True,
                "future_cleanup_execution_requires_separate_run": True,
                "manual_backfill_required": int(simulation.get("manual_operation_count") or 0) > 0,
                "can_promote_to_learning_samples_now": False,
                "training_started_now": False,
                "training_freeze_allowed": False,
                "can_start_training_now": False,
                "next_required_action": (
                    "resolve_controlled_cleanup_dry_run_blocks_before_review"
                    if blocked_count
                    else "review_controlled_cleanup_dry_run_before_any_cleanup_execution"
                ),
            },
            "source_preflight_decision": {
                "cleanup_execution_plan_preflight_ready_for_dry_run": (plan_preflight.get("decision") or {}).get(
                    "cleanup_execution_plan_preflight_ready_for_dry_run"
                ),
                "cleanup_execution_approved_now": (plan_preflight.get("decision") or {}).get(
                    "cleanup_execution_approved_now"
                ),
                "cleanup_application_allowed_now": (plan_preflight.get("decision") or {}).get(
                    "cleanup_application_allowed_now"
                ),
                "cleanup_executed_now": (plan_preflight.get("decision") or {}).get("cleanup_executed_now"),
                "can_execute_cleanup_now": (plan_preflight.get("decision") or {}).get("can_execute_cleanup_now"),
                "writes_learning_samples_now": (plan_preflight.get("decision") or {}).get("writes_learning_samples_now"),
                "training_started_now": (plan_preflight.get("decision") or {}).get("training_started_now"),
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
                    self.staging_cleanup_execution_controlled_dry_run_event_type,
                    json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str),
                ),
            )
            event_id = int(cursor.lastrowid)
        return {**payload, "event_id": event_id}

    def list_staging_cleanup_execution_controlled_dry_runs(self, limit: int = 20) -> list[dict[str, Any]]:
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
            (self.staging_cleanup_execution_controlled_dry_run_event_type, max(1, min(limit, 100))),
        )
        dry_runs: list[dict[str, Any]] = []
        for row in rows:
            payload = json.loads(row.pop("payload_json") or "{}")
            dry_runs.append(
                {
                    "id": row["id"],
                    "event_type": row["event_type"],
                    "created_at": row["created_at"],
                    **payload,
                }
            )
        return dry_runs

    def staging_cleanup_execution_controlled_dry_run_review(
        self,
        controlled_dry_run_id: int | None = None,
        reviewed_by: str = "operator",
        review_decision: str = "approved_for_controlled_cleanup_execution_review",
        note: str | None = None,
    ) -> dict[str, Any]:
        store = SQLiteStore(settings.database_path)
        store.init()
        controlled_dry_run = (
            self._cleanup_execution_controlled_dry_run_by_id(store, controlled_dry_run_id)
            if controlled_dry_run_id
            else self._latest_cleanup_execution_controlled_dry_run(store)
        )
        if controlled_dry_run is None:
            return {
                "schema_version": "dataset2_staging_cleanup_execution_controlled_dry_run_review.v1",
                "stage": self.stage,
                "status": "controlled_cleanup_dry_run_review_blocked_missing_dry_run",
                "generated_at": datetime.now().isoformat(timespec="seconds"),
                "controlled_dry_run_id": controlled_dry_run_id,
                "source_dry_run_status": None,
                "source_dry_run_summary": {
                    "check_count": 0,
                    "blocked_check_count": None,
                    "automated_operation_count": 0,
                    "manual_operation_count": 0,
                    "simulated_mutation_count": 0,
                    "record_bodies_included": False,
                },
                "simulation_summary": {
                    "staging_record_count_before": 0,
                    "expected_staging_record_count_after": 0,
                    "learning_sample_count_before": 0,
                    "expected_learning_sample_count_after": 0,
                    "automated_operation_count": 0,
                    "manual_operation_count": 0,
                    "simulated_mutation_count": 0,
                    "contains_sql": False,
                    "contains_executable_code": False,
                    "can_execute_now": False,
                    "record_bodies_included": False,
                    "affected_rows_body_included": False,
                },
                "checks": [],
                "summary": {
                    "check_count": 0,
                    "blocked_check_count": 1,
                    "warning_check_count": 0,
                    "source_dry_run_blocked_check_count": None,
                    "automated_operation_count": 0,
                    "manual_operation_count": 0,
                    "simulated_mutation_count": 0,
                    "record_bodies_included": False,
                },
                "review": {
                    "reviewed_by": reviewed_by or "operator",
                    "review_decision": review_decision,
                    "note": note,
                    "record_bodies_included": False,
                    "evidence_package_body_included": False,
                    "review_only": True,
                    "simulation_only": True,
                },
                "decision": {
                    "writes_database_now": False,
                    "writes_existing_event_now": False,
                    "writes_staging_records_now": False,
                    "writes_learning_samples_now": False,
                    "mutates_staging_records_now": False,
                    "controlled_cleanup_dry_run_review_recorded": False,
                    "controlled_cleanup_dry_run_review_accepted": False,
                    "cleanup_execution_approved_now": False,
                    "cleanup_application_allowed_now": False,
                    "cleanup_executed_now": False,
                    "can_execute_cleanup_now": False,
                    "future_controlled_cleanup_execution_approval_required": True,
                    "can_promote_to_learning_samples_now": False,
                    "training_started_now": False,
                    "training_freeze_allowed": False,
                    "can_start_training_now": False,
                    "next_required_action": "run_dataset2_controlled_cleanup_dry_run_before_review",
                },
                "safety_summary": self._safety_summary(),
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            }

        simulation = controlled_dry_run.get("simulation") or {}
        dry_run_summary = controlled_dry_run.get("summary") or {}
        checks = self._controlled_cleanup_dry_run_review_checks(
            controlled_dry_run,
            reviewed_by=reviewed_by,
            review_decision=review_decision,
        )
        blocked_count = sum(1 for check in checks if check.get("status") == "blocked")
        warning_count = sum(1 for check in checks if check.get("status") == "warning")
        accepted = blocked_count == 0 and review_decision == "approved_for_controlled_cleanup_execution_review"
        payload = {
            "schema_version": "dataset2_staging_cleanup_execution_controlled_dry_run_review.v1",
            "stage": self.stage,
            "status": (
                "controlled_cleanup_dry_run_review_accepted"
                if accepted
                else "controlled_cleanup_dry_run_review_blocked"
            ),
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "controlled_dry_run_id": controlled_dry_run.get("id"),
            "plan_preflight_id": controlled_dry_run.get("plan_preflight_id"),
            "execution_plan_id": controlled_dry_run.get("execution_plan_id"),
            "dry_run_review_id": controlled_dry_run.get("dry_run_review_id"),
            "dry_run_id": controlled_dry_run.get("dry_run_id"),
            "preflight_id": controlled_dry_run.get("preflight_id"),
            "manual_approval_id": controlled_dry_run.get("manual_approval_id"),
            "package_id": controlled_dry_run.get("package_id"),
            "source_dry_run_status": controlled_dry_run.get("status"),
            "source_dry_run_summary": {
                "check_count": dry_run_summary.get("check_count", 0),
                "blocked_check_count": dry_run_summary.get("blocked_check_count", 0),
                "warning_check_count": dry_run_summary.get("warning_check_count", 0),
                "source_preflight_blocked_check_count": dry_run_summary.get("source_preflight_blocked_check_count"),
                "staging_record_count_before": dry_run_summary.get("staging_record_count_before", 0),
                "expected_staging_record_count_after": dry_run_summary.get("expected_staging_record_count_after", 0),
                "automated_operation_count": dry_run_summary.get("automated_operation_count", 0),
                "manual_operation_count": dry_run_summary.get("manual_operation_count", 0),
                "simulated_mutation_count": dry_run_summary.get("simulated_mutation_count", 0),
                "record_bodies_included": False,
            },
            "simulation_summary": {
                "package_id": simulation.get("package_id"),
                "lock_key": simulation.get("lock_key"),
                "staging_record_count_before": simulation.get("staging_record_count_before", 0),
                "expected_staging_record_count_after": simulation.get("expected_staging_record_count_after", 0),
                "learning_sample_count_before": simulation.get("learning_sample_count_before", 0),
                "expected_learning_sample_count_after": simulation.get("expected_learning_sample_count_after", 0),
                "automated_operation_count": simulation.get("automated_operation_count", 0),
                "manual_operation_count": simulation.get("manual_operation_count", 0),
                "simulated_quality_flag_reduction_count": simulation.get(
                    "simulated_quality_flag_reduction_count", 0
                ),
                "simulated_manual_flag_remaining_count": simulation.get(
                    "simulated_manual_flag_remaining_count", 0
                ),
                "simulated_mutation_count": simulation.get("simulated_mutation_count", 0),
                "contains_sql": bool(simulation.get("contains_sql")),
                "contains_executable_code": bool(simulation.get("contains_executable_code")),
                "can_execute_now": bool(simulation.get("can_execute_now")),
                "record_bodies_included": bool(simulation.get("record_bodies_included")),
                "affected_rows_body_included": bool(simulation.get("affected_rows_body_included")),
                "writes_staging_records_now": bool(simulation.get("writes_staging_records_now")),
                "writes_learning_samples_now": bool(simulation.get("writes_learning_samples_now")),
                "mutates_staging_records_now": bool(simulation.get("mutates_staging_records_now")),
            },
            "checks": checks,
            "summary": {
                "check_count": len(checks),
                "blocked_check_count": blocked_count,
                "warning_check_count": warning_count,
                "source_dry_run_check_count": dry_run_summary.get("check_count", 0),
                "source_dry_run_blocked_check_count": dry_run_summary.get("blocked_check_count", 0),
                "automated_operation_count": simulation.get("automated_operation_count", 0),
                "manual_operation_count": simulation.get("manual_operation_count", 0),
                "simulated_mutation_count": simulation.get("simulated_mutation_count", 0),
                "record_bodies_included": False,
            },
            "review": {
                "reviewed_by": reviewed_by or "operator",
                "review_decision": review_decision,
                "note": note,
                "record_bodies_included": False,
                "evidence_package_body_included": False,
                "review_only": True,
                "simulation_only": True,
            },
            "decision": {
                "writes_database_now": False,
                "writes_existing_event_now": True,
                "writes_staging_records_now": False,
                "writes_learning_samples_now": False,
                "mutates_staging_records_now": False,
                "controlled_cleanup_dry_run_review_recorded": True,
                "controlled_cleanup_dry_run_review_accepted": accepted,
                "cleanup_execution_approved_now": False,
                "cleanup_application_allowed_now": False,
                "cleanup_executed_now": False,
                "can_execute_cleanup_now": False,
                "future_controlled_cleanup_execution_approval_required": True,
                "future_cleanup_execution_requires_separate_run": True,
                "can_promote_to_learning_samples_now": False,
                "training_started_now": False,
                "training_freeze_allowed": False,
                "can_start_training_now": False,
                "next_required_action": (
                    "resolve_controlled_cleanup_dry_run_review_blocks_before_execution_approval"
                    if blocked_count
                    else "create_separate_controlled_cleanup_execution_approval_before_any_staging_mutation"
                ),
            },
            "source_dry_run_decision": {
                "controlled_cleanup_dry_run_ready_for_review": (controlled_dry_run.get("decision") or {}).get(
                    "controlled_cleanup_dry_run_ready_for_review"
                ),
                "cleanup_execution_approved_now": (controlled_dry_run.get("decision") or {}).get(
                    "cleanup_execution_approved_now"
                ),
                "cleanup_application_allowed_now": (controlled_dry_run.get("decision") or {}).get(
                    "cleanup_application_allowed_now"
                ),
                "cleanup_executed_now": (controlled_dry_run.get("decision") or {}).get("cleanup_executed_now"),
                "can_execute_cleanup_now": (controlled_dry_run.get("decision") or {}).get("can_execute_cleanup_now"),
                "writes_learning_samples_now": (controlled_dry_run.get("decision") or {}).get(
                    "writes_learning_samples_now"
                ),
                "training_started_now": (controlled_dry_run.get("decision") or {}).get("training_started_now"),
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
                    self.staging_cleanup_execution_controlled_dry_run_review_event_type,
                    json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str),
                ),
            )
            event_id = int(cursor.lastrowid)
        return {**payload, "event_id": event_id}

    def list_staging_cleanup_execution_controlled_dry_run_reviews(self, limit: int = 20) -> list[dict[str, Any]]:
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
            (self.staging_cleanup_execution_controlled_dry_run_review_event_type, max(1, min(limit, 100))),
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

    def staging_cleanup_execution_controlled_approval(
        self,
        controlled_review_id: int | None = None,
        approved_by: str = "operator",
        approval_decision: str = "approved_for_controlled_cleanup_execution_preflight",
        note: str | None = None,
    ) -> dict[str, Any]:
        store = SQLiteStore(settings.database_path)
        store.init()
        review = (
            self._cleanup_execution_controlled_dry_run_review_by_id(store, controlled_review_id)
            if controlled_review_id
            else self._latest_cleanup_execution_controlled_dry_run_review(store)
        )
        if review is None:
            return {
                "schema_version": "dataset2_staging_cleanup_execution_controlled_approval.v1",
                "stage": self.stage,
                "status": "controlled_cleanup_execution_approval_blocked_missing_review",
                "generated_at": datetime.now().isoformat(timespec="seconds"),
                "controlled_review_id": controlled_review_id,
                "source_review_status": None,
                "source_review_summary": {
                    "check_count": 0,
                    "blocked_check_count": None,
                    "automated_operation_count": 0,
                    "manual_operation_count": 0,
                    "simulated_mutation_count": 0,
                    "record_bodies_included": False,
                },
                "approval_scope": self._empty_controlled_cleanup_approval_scope(),
                "checks": [],
                "summary": {
                    "check_count": 0,
                    "blocked_check_count": 1,
                    "warning_check_count": 0,
                    "source_review_blocked_check_count": None,
                    "automated_operation_count": 0,
                    "manual_operation_count": 0,
                    "simulated_mutation_count": 0,
                    "record_bodies_included": False,
                },
                "approval": {
                    "approved_by": approved_by or "operator",
                    "approval_decision": approval_decision,
                    "note": note,
                    "record_bodies_included": False,
                    "evidence_package_body_included": False,
                    "review_only": True,
                    "simulation_only": True,
                },
                "decision": {
                    "writes_database_now": False,
                    "writes_existing_event_now": False,
                    "writes_staging_records_now": False,
                    "writes_learning_samples_now": False,
                    "mutates_staging_records_now": False,
                    "controlled_cleanup_execution_approval_recorded": False,
                    "controlled_cleanup_execution_approval_accepted": False,
                    "controlled_cleanup_approved_for_future_preflight": False,
                    "cleanup_execution_approved_now": False,
                    "cleanup_application_allowed_now": False,
                    "cleanup_executed_now": False,
                    "can_execute_cleanup_now": False,
                    "can_generate_controlled_cleanup_execution_preflight_now": False,
                    "future_controlled_cleanup_execution_preflight_required": True,
                    "can_promote_to_learning_samples_now": False,
                    "training_started_now": False,
                    "training_freeze_allowed": False,
                    "can_start_training_now": False,
                    "next_required_action": "review_dataset2_controlled_cleanup_dry_run_before_approval",
                },
                "safety_summary": self._safety_summary(),
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            }

        approval_scope = self._controlled_cleanup_approval_scope(review)
        checks = self._controlled_cleanup_execution_approval_checks(
            review,
            approval_scope=approval_scope,
            approved_by=approved_by,
            approval_decision=approval_decision,
        )
        blocked_count = sum(1 for check in checks if check.get("status") == "blocked")
        warning_count = sum(1 for check in checks if check.get("status") == "warning")
        accepted = blocked_count == 0 and approval_decision == "approved_for_controlled_cleanup_execution_preflight"
        review_summary = review.get("summary") or {}
        simulation_summary = review.get("simulation_summary") or {}
        payload = {
            "schema_version": "dataset2_staging_cleanup_execution_controlled_approval.v1",
            "stage": self.stage,
            "status": (
                "controlled_cleanup_execution_approval_ready_for_preflight"
                if accepted
                else "controlled_cleanup_execution_approval_blocked"
            ),
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "controlled_review_id": review.get("id"),
            "controlled_dry_run_id": review.get("controlled_dry_run_id"),
            "plan_preflight_id": review.get("plan_preflight_id"),
            "execution_plan_id": review.get("execution_plan_id"),
            "dry_run_review_id": review.get("dry_run_review_id"),
            "dry_run_id": review.get("dry_run_id"),
            "preflight_id": review.get("preflight_id"),
            "manual_approval_id": review.get("manual_approval_id"),
            "package_id": review.get("package_id"),
            "source_review_status": review.get("status"),
            "source_review_summary": {
                "check_count": review_summary.get("check_count", 0),
                "blocked_check_count": review_summary.get("blocked_check_count", 0),
                "warning_check_count": review_summary.get("warning_check_count", 0),
                "source_dry_run_blocked_check_count": review_summary.get("source_dry_run_blocked_check_count"),
                "automated_operation_count": review_summary.get("automated_operation_count", 0),
                "manual_operation_count": review_summary.get("manual_operation_count", 0),
                "simulated_mutation_count": review_summary.get("simulated_mutation_count", 0),
                "record_bodies_included": False,
            },
            "simulation_summary": {
                "package_id": simulation_summary.get("package_id"),
                "lock_key": simulation_summary.get("lock_key"),
                "staging_record_count_before": simulation_summary.get("staging_record_count_before", 0),
                "expected_staging_record_count_after": simulation_summary.get("expected_staging_record_count_after", 0),
                "learning_sample_count_before": simulation_summary.get("learning_sample_count_before", 0),
                "expected_learning_sample_count_after": simulation_summary.get("expected_learning_sample_count_after", 0),
                "automated_operation_count": simulation_summary.get("automated_operation_count", 0),
                "manual_operation_count": simulation_summary.get("manual_operation_count", 0),
                "simulated_mutation_count": simulation_summary.get("simulated_mutation_count", 0),
                "contains_sql": bool(simulation_summary.get("contains_sql")),
                "contains_executable_code": bool(simulation_summary.get("contains_executable_code")),
                "can_execute_now": bool(simulation_summary.get("can_execute_now")),
                "record_bodies_included": bool(simulation_summary.get("record_bodies_included")),
                "affected_rows_body_included": bool(simulation_summary.get("affected_rows_body_included")),
                "writes_staging_records_now": bool(simulation_summary.get("writes_staging_records_now")),
                "writes_learning_samples_now": bool(simulation_summary.get("writes_learning_samples_now")),
                "mutates_staging_records_now": bool(simulation_summary.get("mutates_staging_records_now")),
            },
            "approval_scope": approval_scope,
            "checks": checks,
            "summary": {
                "check_count": len(checks),
                "blocked_check_count": blocked_count,
                "warning_check_count": warning_count,
                "source_review_check_count": review_summary.get("check_count", 0),
                "source_review_blocked_check_count": review_summary.get("blocked_check_count", 0),
                "automated_operation_count": approval_scope.get("automated_operation_count", 0),
                "manual_operation_count": approval_scope.get("manual_operation_count", 0),
                "simulated_mutation_count": approval_scope.get("simulated_mutation_count", 0),
                "record_bodies_included": False,
            },
            "approval": {
                "approved_by": approved_by or "operator",
                "approval_decision": approval_decision,
                "note": note,
                "record_bodies_included": False,
                "evidence_package_body_included": False,
                "review_only": True,
                "simulation_only": True,
            },
            "decision": {
                "writes_database_now": False,
                "writes_existing_event_now": True,
                "writes_staging_records_now": False,
                "writes_learning_samples_now": False,
                "mutates_staging_records_now": False,
                "controlled_cleanup_execution_approval_recorded": True,
                "controlled_cleanup_execution_approval_accepted": accepted,
                "controlled_cleanup_approved_for_future_preflight": accepted,
                "cleanup_execution_approved_now": False,
                "cleanup_application_allowed_now": False,
                "cleanup_executed_now": False,
                "can_execute_cleanup_now": False,
                "can_generate_controlled_cleanup_execution_preflight_now": accepted,
                "future_controlled_cleanup_execution_preflight_required": True,
                "future_cleanup_execution_requires_separate_run": True,
                "can_promote_to_learning_samples_now": False,
                "training_started_now": False,
                "training_freeze_allowed": False,
                "can_start_training_now": False,
                "next_required_action": (
                    "resolve_controlled_cleanup_execution_approval_blocks_before_preflight"
                    if blocked_count
                    else "run_controlled_cleanup_execution_preflight_before_any_staging_mutation"
                ),
            },
            "source_review_decision": {
                "controlled_cleanup_dry_run_review_accepted": (review.get("decision") or {}).get(
                    "controlled_cleanup_dry_run_review_accepted"
                ),
                "cleanup_execution_approved_now": (review.get("decision") or {}).get("cleanup_execution_approved_now"),
                "cleanup_application_allowed_now": (review.get("decision") or {}).get(
                    "cleanup_application_allowed_now"
                ),
                "cleanup_executed_now": (review.get("decision") or {}).get("cleanup_executed_now"),
                "can_execute_cleanup_now": (review.get("decision") or {}).get("can_execute_cleanup_now"),
                "writes_learning_samples_now": (review.get("decision") or {}).get("writes_learning_samples_now"),
                "training_started_now": (review.get("decision") or {}).get("training_started_now"),
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
                    self.staging_cleanup_execution_controlled_approval_event_type,
                    json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str),
                ),
            )
            event_id = int(cursor.lastrowid)
        return {**payload, "event_id": event_id}

    def list_staging_cleanup_execution_controlled_approvals(self, limit: int = 20) -> list[dict[str, Any]]:
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
            (self.staging_cleanup_execution_controlled_approval_event_type, max(1, min(limit, 100))),
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

    def _staging_record_count(self, store: SQLiteStore, package_id: str | None = None) -> int:
        if package_id:
            row = store.fetch_one(
                "SELECT COUNT(*) AS count FROM dataset2_staging_records WHERE package_id = ?",
                (package_id,),
            )
        else:
            row = store.fetch_one("SELECT COUNT(*) AS count FROM dataset2_staging_records")
        return int(row["count"]) if row and row.get("count") is not None else 0

    def _learning_sample_count(self, store: SQLiteStore) -> int:
        row = store.fetch_one("SELECT COUNT(*) AS count FROM learning_samples")
        return int(row["count"]) if row and row.get("count") is not None else 0

    def _cleanup_preflight_lock_key(self, manual_approval: dict[str, Any], staging_count: int) -> str:
        seed = {
            "manual_approval_id": manual_approval.get("id"),
            "approval_plan_id": manual_approval.get("approval_plan_id"),
            "package_id": manual_approval.get("package_id"),
            "evidence_package_hash": (manual_approval.get("evidence_summary") or {}).get("evidence_package_hash"),
            "staging_count": staging_count,
        }
        digest = hashlib.sha256(json.dumps(seed, sort_keys=True, default=str).encode("utf-8")).hexdigest()
        return f"dataset2-cleanup-preflight-{digest[:16]}"

    def _cleanup_execution_dry_run_simulation(self, store: SQLiteStore, package_id: str | None) -> dict[str, Any]:
        clauses: list[str] = []
        params: list[Any] = []
        if package_id:
            clauses.append("package_id = ?")
            params.append(package_id)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = store.fetch_all(
            f"""
            SELECT package_id, action_label, risk_level, split_tag, quality_flags_json, cleanup_operations_json
            FROM dataset2_staging_records
            {where}
            ORDER BY id
            LIMIT 1000
            """,
            tuple(params),
        )
        operation_counts: Counter[str] = Counter()
        field_counts: Counter[str] = Counter()
        quality_flag_counts: Counter[str] = Counter()
        action_counts: Counter[str] = Counter()
        risk_counts: Counter[str] = Counter()
        split_counts: Counter[str] = Counter()
        records_with_operations = 0
        records_with_quality_flags = 0
        for row in rows:
            action_counts[str(row.get("action_label") or "unknown")] += 1
            risk_counts[str(row.get("risk_level") or "unknown")] += 1
            split_counts[str(row.get("split_tag") or "unknown")] += 1
            quality_flags = json.loads(row.get("quality_flags_json") or "[]")
            operations = json.loads(row.get("cleanup_operations_json") or "[]")
            if quality_flags:
                records_with_quality_flags += 1
            if operations:
                records_with_operations += 1
            for flag in quality_flags:
                quality_flag_counts[str(flag)] += 1
            for operation in operations:
                operation_counts[str(operation.get("operation") or "unknown")] += 1
                field_counts[str(operation.get("field") or "unknown")] += 1
        learning_count = self._learning_sample_count(store)
        return {
            "package_id": package_id,
            "candidate_record_count": len(rows),
            "records_with_operations": records_with_operations,
            "records_with_quality_flags": records_with_quality_flags,
            "simulated_mutation_count": sum(operation_counts.values()),
            "operation_counts": dict(operation_counts),
            "field_counts": dict(field_counts),
            "quality_flag_counts": dict(quality_flag_counts),
            "action_label_counts": dict(action_counts),
            "risk_level_counts": dict(risk_counts),
            "split_counts": dict(split_counts),
            "learning_sample_count_before": learning_count,
            "expected_learning_sample_count_after": learning_count,
            "writes_staging_records_now": False,
            "writes_learning_samples_now": False,
            "mutates_staging_records_now": False,
            "contains_sql": False,
            "contains_executable_code": False,
            "can_execute_now": False,
            "record_bodies_included": False,
            "affected_rows_body_included": False,
            "review_only": True,
            "simulation_only": True,
        }

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

    def _fix_preflight_by_id(self, store: SQLiteStore, preflight_id: int | None) -> dict[str, Any] | None:
        if preflight_id is None:
            return None
        row = store.fetch_one(
            """
            SELECT id, event_type, payload_json, created_at
            FROM events
            WHERE event_type = ? AND id = ?
            """,
            (self.staging_fix_preflight_event_type, preflight_id),
        )
        return self._event_payload(row) if row else None

    def _latest_fix_preflight(self, store: SQLiteStore) -> dict[str, Any] | None:
        row = store.fetch_one(
            """
            SELECT id, event_type, payload_json, created_at
            FROM events
            WHERE event_type = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (self.staging_fix_preflight_event_type,),
        )
        return self._event_payload(row) if row else None

    def _cleanup_execution_spec_by_id(self, store: SQLiteStore, spec_id: int | None) -> dict[str, Any] | None:
        if spec_id is None:
            return None
        row = store.fetch_one(
            """
            SELECT id, event_type, payload_json, created_at
            FROM events
            WHERE event_type = ? AND id = ?
            """,
            (self.staging_cleanup_execution_spec_event_type, spec_id),
        )
        return self._event_payload(row) if row else None

    def _latest_cleanup_execution_spec(self, store: SQLiteStore) -> dict[str, Any] | None:
        row = store.fetch_one(
            """
            SELECT id, event_type, payload_json, created_at
            FROM events
            WHERE event_type = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (self.staging_cleanup_execution_spec_event_type,),
        )
        return self._event_payload(row) if row else None

    def _cleanup_dry_run_by_id(self, store: SQLiteStore, dry_run_id: int | None) -> dict[str, Any] | None:
        if dry_run_id is None:
            return None
        row = store.fetch_one(
            """
            SELECT id, event_type, payload_json, created_at
            FROM events
            WHERE event_type = ? AND id = ?
            """,
            (self.staging_cleanup_dry_run_verification_event_type, dry_run_id),
        )
        return self._event_payload(row) if row else None

    def _latest_cleanup_dry_run(self, store: SQLiteStore) -> dict[str, Any] | None:
        row = store.fetch_one(
            """
            SELECT id, event_type, payload_json, created_at
            FROM events
            WHERE event_type = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (self.staging_cleanup_dry_run_verification_event_type,),
        )
        return self._event_payload(row) if row else None

    def _manual_evidence_by_id(self, store: SQLiteStore, manual_evidence_id: int | None) -> dict[str, Any] | None:
        if manual_evidence_id is None:
            return None
        row = store.fetch_one(
            """
            SELECT id, event_type, payload_json, created_at
            FROM events
            WHERE event_type = ? AND id = ?
            """,
            (self.staging_cleanup_manual_evidence_event_type, manual_evidence_id),
        )
        return self._event_payload(row) if row else None

    def _latest_manual_evidence(self, store: SQLiteStore) -> dict[str, Any] | None:
        row = store.fetch_one(
            """
            SELECT id, event_type, payload_json, created_at
            FROM events
            WHERE event_type = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (self.staging_cleanup_manual_evidence_event_type,),
        )
        return self._event_payload(row) if row else None

    def _manual_evidence_acceptance_by_id(self, store: SQLiteStore, acceptance_id: int | None) -> dict[str, Any] | None:
        if acceptance_id is None:
            return None
        row = store.fetch_one(
            """
            SELECT id, event_type, payload_json, created_at
            FROM events
            WHERE event_type = ? AND id = ?
            """,
            (self.staging_cleanup_manual_evidence_acceptance_event_type, acceptance_id),
        )
        return self._event_payload(row) if row else None

    def _latest_manual_evidence_acceptance(self, store: SQLiteStore) -> dict[str, Any] | None:
        row = store.fetch_one(
            """
            SELECT id, event_type, payload_json, created_at
            FROM events
            WHERE event_type = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (self.staging_cleanup_manual_evidence_acceptance_event_type,),
        )
        return self._event_payload(row) if row else None

    def _cleanup_application_review_by_id(self, store: SQLiteStore, review_id: int | None) -> dict[str, Any] | None:
        if review_id is None:
            return None
        row = store.fetch_one(
            """
            SELECT id, event_type, payload_json, created_at
            FROM events
            WHERE event_type = ? AND id = ?
            """,
            (self.staging_cleanup_application_review_event_type, review_id),
        )
        return self._event_payload(row) if row else None

    def _latest_cleanup_application_review(self, store: SQLiteStore) -> dict[str, Any] | None:
        row = store.fetch_one(
            """
            SELECT id, event_type, payload_json, created_at
            FROM events
            WHERE event_type = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (self.staging_cleanup_application_review_event_type,),
        )
        return self._event_payload(row) if row else None

    def _cleanup_execution_approval_plan_by_id(self, store: SQLiteStore, plan_id: int | None) -> dict[str, Any] | None:
        if plan_id is None:
            return None
        row = store.fetch_one(
            """
            SELECT id, event_type, payload_json, created_at
            FROM events
            WHERE event_type = ? AND id = ?
            """,
            (self.staging_cleanup_execution_approval_plan_event_type, plan_id),
        )
        return self._event_payload(row) if row else None

    def _latest_cleanup_execution_approval_plan(self, store: SQLiteStore) -> dict[str, Any] | None:
        row = store.fetch_one(
            """
            SELECT id, event_type, payload_json, created_at
            FROM events
            WHERE event_type = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (self.staging_cleanup_execution_approval_plan_event_type,),
        )
        return self._event_payload(row) if row else None

    def _cleanup_execution_manual_approval_by_id(
        self, store: SQLiteStore, manual_approval_id: int | None
    ) -> dict[str, Any] | None:
        if manual_approval_id is None:
            return None
        row = store.fetch_one(
            """
            SELECT id, event_type, payload_json, created_at
            FROM events
            WHERE event_type = ? AND id = ?
            """,
            (self.staging_cleanup_execution_manual_approval_event_type, manual_approval_id),
        )
        return self._event_payload(row) if row else None

    def _latest_cleanup_execution_manual_approval(self, store: SQLiteStore) -> dict[str, Any] | None:
        row = store.fetch_one(
            """
            SELECT id, event_type, payload_json, created_at
            FROM events
            WHERE event_type = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (self.staging_cleanup_execution_manual_approval_event_type,),
        )
        return self._event_payload(row) if row else None

    def _cleanup_execution_preflight_by_id(self, store: SQLiteStore, preflight_id: int | None) -> dict[str, Any] | None:
        if preflight_id is None:
            return None
        row = store.fetch_one(
            """
            SELECT id, event_type, payload_json, created_at
            FROM events
            WHERE event_type = ? AND id = ?
            """,
            (self.staging_cleanup_execution_preflight_event_type, preflight_id),
        )
        return self._event_payload(row) if row else None

    def _latest_cleanup_execution_preflight(self, store: SQLiteStore) -> dict[str, Any] | None:
        row = store.fetch_one(
            """
            SELECT id, event_type, payload_json, created_at
            FROM events
            WHERE event_type = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (self.staging_cleanup_execution_preflight_event_type,),
        )
        return self._event_payload(row) if row else None

    def _cleanup_execution_dry_run_by_id(self, store: SQLiteStore, dry_run_id: int | None) -> dict[str, Any] | None:
        if dry_run_id is None:
            return None
        row = store.fetch_one(
            """
            SELECT id, event_type, payload_json, created_at
            FROM events
            WHERE event_type = ? AND id = ?
            """,
            (self.staging_cleanup_execution_dry_run_event_type, dry_run_id),
        )
        return self._event_payload(row) if row else None

    def _latest_cleanup_execution_dry_run(self, store: SQLiteStore) -> dict[str, Any] | None:
        row = store.fetch_one(
            """
            SELECT id, event_type, payload_json, created_at
            FROM events
            WHERE event_type = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (self.staging_cleanup_execution_dry_run_event_type,),
        )
        return self._event_payload(row) if row else None

    def _cleanup_execution_dry_run_review_by_id(
        self,
        store: SQLiteStore,
        review_id: int | None,
    ) -> dict[str, Any] | None:
        if review_id is None:
            return None
        row = store.fetch_one(
            """
            SELECT id, event_type, payload_json, created_at
            FROM events
            WHERE event_type = ? AND id = ?
            """,
            (self.staging_cleanup_execution_dry_run_review_event_type, review_id),
        )
        return self._event_payload(row) if row else None

    def _latest_cleanup_execution_dry_run_review(self, store: SQLiteStore) -> dict[str, Any] | None:
        row = store.fetch_one(
            """
            SELECT id, event_type, payload_json, created_at
            FROM events
            WHERE event_type = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (self.staging_cleanup_execution_dry_run_review_event_type,),
        )
        return self._event_payload(row) if row else None

    def _cleanup_execution_plan_by_id(self, store: SQLiteStore, plan_id: int | None) -> dict[str, Any] | None:
        if plan_id is None:
            return None
        row = store.fetch_one(
            """
            SELECT id, event_type, payload_json, created_at
            FROM events
            WHERE event_type = ? AND id = ?
            """,
            (self.staging_cleanup_execution_plan_event_type, plan_id),
        )
        return self._event_payload(row) if row else None

    def _latest_cleanup_execution_plan(self, store: SQLiteStore) -> dict[str, Any] | None:
        row = store.fetch_one(
            """
            SELECT id, event_type, payload_json, created_at
            FROM events
            WHERE event_type = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (self.staging_cleanup_execution_plan_event_type,),
        )
        return self._event_payload(row) if row else None

    def _cleanup_execution_plan_preflight_by_id(
        self,
        store: SQLiteStore,
        plan_preflight_id: int | None,
    ) -> dict[str, Any] | None:
        if plan_preflight_id is None:
            return None
        row = store.fetch_one(
            """
            SELECT id, event_type, payload_json, created_at
            FROM events
            WHERE event_type = ? AND id = ?
            """,
            (self.staging_cleanup_execution_plan_preflight_event_type, plan_preflight_id),
        )
        return self._event_payload(row) if row else None

    def _latest_cleanup_execution_plan_preflight(self, store: SQLiteStore) -> dict[str, Any] | None:
        row = store.fetch_one(
            """
            SELECT id, event_type, payload_json, created_at
            FROM events
            WHERE event_type = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (self.staging_cleanup_execution_plan_preflight_event_type,),
        )
        return self._event_payload(row) if row else None

    def _cleanup_execution_controlled_dry_run_by_id(
        self,
        store: SQLiteStore,
        controlled_dry_run_id: int | None,
    ) -> dict[str, Any] | None:
        if controlled_dry_run_id is None:
            return None
        row = store.fetch_one(
            """
            SELECT id, event_type, payload_json, created_at
            FROM events
            WHERE event_type = ? AND id = ?
            """,
            (self.staging_cleanup_execution_controlled_dry_run_event_type, controlled_dry_run_id),
        )
        return self._event_payload(row) if row else None

    def _latest_cleanup_execution_controlled_dry_run(self, store: SQLiteStore) -> dict[str, Any] | None:
        row = store.fetch_one(
            """
            SELECT id, event_type, payload_json, created_at
            FROM events
            WHERE event_type = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (self.staging_cleanup_execution_controlled_dry_run_event_type,),
        )
        return self._event_payload(row) if row else None

    def _cleanup_execution_controlled_dry_run_review_by_id(
        self,
        store: SQLiteStore,
        review_id: int | None,
    ) -> dict[str, Any] | None:
        if review_id is None:
            return None
        row = store.fetch_one(
            """
            SELECT id, event_type, payload_json, created_at
            FROM events
            WHERE event_type = ? AND id = ?
            """,
            (self.staging_cleanup_execution_controlled_dry_run_review_event_type, review_id),
        )
        return self._event_payload(row) if row else None

    def _latest_cleanup_execution_controlled_dry_run_review(self, store: SQLiteStore) -> dict[str, Any] | None:
        row = store.fetch_one(
            """
            SELECT id, event_type, payload_json, created_at
            FROM events
            WHERE event_type = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (self.staging_cleanup_execution_controlled_dry_run_review_event_type,),
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

    def _cleanup_execution_steps(self, preflight: dict[str, Any]) -> list[dict[str, Any]]:
        steps: list[dict[str, Any]] = []
        for check in preflight.get("preflight_checks") or []:
            name = str(check.get("name") or "unknown_check")
            if name == "time_aware_split_policy":
                steps.append(
                    self._execution_step(
                        check,
                        "deterministic_split_assignment_spec",
                        "future_reviewed_script",
                        "Create deterministic train/validation split assignments after manual approval.",
                        {
                            "sort_keys": ["signal_date", "stock_code", "pattern_id"],
                            "train_ratio": check.get("details", {}).get("train_ratio", 0.7),
                            "validation_ratio": check.get("details", {}).get("validation_ratio", 0.3),
                            "writes_staging_records_now": False,
                        },
                    )
                )
            elif name == "historical_outcome_join_requirements":
                steps.append(
                    self._execution_step(
                        check,
                        "historical_outcome_join_spec",
                        "manual_operator_action",
                        "Prepare reviewed historical outcome source and join keys before any cleanup application.",
                        {
                            "required_fields": check.get("details", {}).get("required_fields", sorted(HISTORICAL_OUTCOME_FIELDS)),
                            "requires_external_reviewed_dataset": True,
                            "writes_staging_records_now": False,
                        },
                    )
                )
            elif name == "quality_flag_resolution_requirements":
                steps.append(
                    self._execution_step(
                        check,
                        "quality_flag_disposition_spec",
                        "manual_operator_action",
                        "Decide whether each quality flag should be corrected, accepted with evidence, or quarantined.",
                        {
                            "quality_flag_evidence": check.get("details", {}).get("quality_flag_evidence", {}),
                            "allowed_dispositions": ["correct_later", "accept_with_evidence", "quarantine"],
                            "writes_staging_records_now": False,
                        },
                    )
                )
            elif name == "label_support_policy_requirements":
                steps.append(
                    self._execution_step(
                        check,
                        "label_support_policy_spec",
                        "manual_operator_action",
                        "Choose class weighting, label consolidation, or sample expansion policy before training freeze.",
                        {
                            "allowed_future_options": check.get("details", {}).get("allowed_future_options", []),
                            "label_evidence": check.get("details", {}).get("label_evidence", {}),
                            "writes_staging_records_now": False,
                        },
                    )
                )
            else:
                steps.append(
                    self._execution_step(
                        check,
                        f"{name}_execution_spec",
                        "manual_operator_action",
                        f"Review preflight check `{name}` before any cleanup application.",
                        {
                            "check_details": check.get("details", {}),
                            "writes_staging_records_now": False,
                        },
                    )
                )
        return steps

    def _execution_step(
        self,
        check: dict[str, Any],
        name: str,
        execution_mode: str,
        title: str,
        details: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "id": f"dataset2_execution_{self._stable_hash({'check': check.get('id'), 'name': name})[:16]}",
            "name": name,
            "source_preflight_check_id": check.get("id"),
            "source_check_status": check.get("status"),
            "gate_name": check.get("gate_name"),
            "priority": check.get("priority"),
            "execution_mode": execution_mode,
            "title": title,
            "details": details,
            "acceptance_checks": [
                *check.get("acceptance_checks", []),
                "Operator approval is recorded before any cleanup application stage.",
                "No staging row, source dataset, or training table is modified by this spec.",
            ],
            "forbidden_actions": [
                "execute_sql",
                "mutate_staging_records",
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

    def _cleanup_dry_run_checks(self, spec: dict[str, Any]) -> list[dict[str, Any]]:
        steps = spec.get("execution_steps") or []
        summary = spec.get("summary") or {}
        spec_meta = spec.get("spec") or {}
        decision = spec.get("decision") or {}
        required_forbidden = {
            "execute_sql",
            "mutate_staging_records",
            "modify_dataset2_source_files",
            "write_learning_samples",
            "start_training",
            "create_export_file",
            "enable_live_trading",
        }
        missing_forbidden = [
            step.get("id")
            for step in steps
            if not required_forbidden.issubset(set(step.get("forbidden_actions") or []))
        ]
        blocked_source_count = int(summary.get("blocked_source_check_count") or 0)
        checks = [
            self._dry_run_check(
                "execution_spec_present",
                "passed" if steps else "blocked",
                len(steps),
                ">0",
                "execution spec must contain reviewed future steps",
            ),
            self._dry_run_check(
                "spec_non_executable",
                "passed" if not spec_meta.get("contains_executable_code") and not spec_meta.get("sql_included") else "blocked",
                {
                    "contains_executable_code": bool(spec_meta.get("contains_executable_code")),
                    "sql_included": bool(spec_meta.get("sql_included")),
                },
                {"contains_executable_code": False, "sql_included": False},
                "dry-run verifier accepts descriptive specs only",
            ),
            self._dry_run_check(
                "record_bodies_excluded",
                "passed" if not spec_meta.get("record_bodies_included") and summary.get("record_body_count", 0) == 0 else "blocked",
                {
                    "record_bodies_included": bool(spec_meta.get("record_bodies_included")),
                    "record_body_count": summary.get("record_body_count", 0),
                },
                {"record_bodies_included": False, "record_body_count": 0},
                "event payloads must not include staged record bodies",
            ),
            self._dry_run_check(
                "no_mutation_allowed",
                "passed"
                if not spec_meta.get("can_execute_now")
                and not decision.get("cleanup_executed_now")
                and not decision.get("mutates_staging_records_now")
                and not decision.get("writes_learning_samples_now")
                else "blocked",
                {
                    "can_execute_now": bool(spec_meta.get("can_execute_now")),
                    "cleanup_executed_now": bool(decision.get("cleanup_executed_now")),
                    "mutates_staging_records_now": bool(decision.get("mutates_staging_records_now")),
                    "writes_learning_samples_now": bool(decision.get("writes_learning_samples_now")),
                },
                False,
                "dry-run verification must not allow cleanup application or training writes",
            ),
            self._dry_run_check(
                "forbidden_actions_complete",
                "passed" if not missing_forbidden else "blocked",
                {"missing_step_ids": missing_forbidden},
                [],
                "every future step must carry the full forbidden-action set",
            ),
            self._dry_run_check(
                "blocked_source_checks_resolved",
                "passed" if blocked_source_count == 0 else "blocked",
                blocked_source_count,
                0,
                "source preflight blocked checks must be resolved before cleanup can be applied",
            ),
            self._dry_run_check(
                "manual_steps_acknowledged",
                "warning" if any(step.get("execution_mode") == "manual_operator_action" for step in steps) else "passed",
                summary.get("manual_step_count", 0),
                "operator review",
                "manual steps require external evidence before a later application stage",
            ),
        ]
        return checks

    def _dry_run_check(self, name: str, status: str, value: Any, limit: Any, reason: str) -> dict[str, Any]:
        return {
            "name": name,
            "status": status,
            "value": value,
            "limit": limit,
            "reason": reason,
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _manual_evidence_checks(self, dry_run: dict[str, Any], evidence: dict[str, Any]) -> list[dict[str, Any]]:
        dry_run_summary = dry_run.get("summary") or {}
        historical = evidence.get("historical_outcome_source") if isinstance(evidence.get("historical_outcome_source"), dict) else {}
        split_ack = evidence.get("split_policy_ack") if isinstance(evidence.get("split_policy_ack"), dict) else {}
        label_policy = evidence.get("label_support_policy") if isinstance(evidence.get("label_support_policy"), dict) else {}
        reviewer = evidence.get("reviewer") if isinstance(evidence.get("reviewer"), dict) else {}
        quality_dispositions = evidence.get("quality_flag_dispositions")
        if isinstance(quality_dispositions, dict):
            disposition_count = len(quality_dispositions)
        elif isinstance(quality_dispositions, list):
            disposition_count = len(quality_dispositions)
        else:
            disposition_count = 0
        field_coverage = historical.get("field_coverage") if isinstance(historical.get("field_coverage"), dict) else {}
        covered_fields = {field for field, covered in field_coverage.items() if covered}
        required_fields = set(HISTORICAL_OUTCOME_FIELDS)
        join_keys = set(historical.get("join_keys") or []) if isinstance(historical.get("join_keys"), list) else set()
        forbidden_paths = self._forbidden_evidence_paths(evidence)
        forbidden_actions = self._forbidden_evidence_action_paths(evidence)
        return [
            self._manual_evidence_check(
                "dry_run_available",
                "passed" if dry_run.get("id") else "blocked",
                dry_run.get("id"),
                "existing dry-run verification",
                "manual evidence must be tied to a dry-run verification",
            ),
            self._manual_evidence_check(
                "dry_run_blocked_checks_addressed",
                "passed" if int(dry_run_summary.get("blocked_check_count") or 0) == 0 or bool(evidence) else "blocked",
                dry_run_summary.get("blocked_check_count", 0),
                "evidence supplied for blocked checks",
                "blocked dry-run checks need explicit manual evidence before cleanup application review",
            ),
            self._manual_evidence_check(
                "historical_outcome_source_reviewed",
                "passed"
                if historical.get("source_hash")
                and {"stock_code", "signal_date"}.issubset(join_keys)
                and required_fields.issubset(covered_fields)
                else "blocked",
                {
                    "source_hash_present": bool(historical.get("source_hash")),
                    "join_keys": sorted(join_keys),
                    "covered_field_count": len(covered_fields),
                    "required_field_count": len(required_fields),
                },
                "source_hash + stock_code/signal_date join keys + full required field coverage",
                "historical outcome evidence must prove joinability and target-field coverage",
            ),
            self._manual_evidence_check(
                "quality_flag_dispositions_reviewed",
                "passed" if disposition_count > 0 else "blocked",
                disposition_count,
                ">0 dispositions",
                "quality flags must be corrected, accepted with evidence, or quarantined before cleanup application",
            ),
            self._manual_evidence_check(
                "split_policy_acknowledged",
                "passed" if split_ack.get("deterministic") is True and bool(split_ack.get("policy_id") or split_ack.get("policy")) else "blocked",
                {
                    "deterministic": split_ack.get("deterministic"),
                    "policy_id": split_ack.get("policy_id") or split_ack.get("policy"),
                },
                "deterministic split policy id",
                "time-aware split policy must be acknowledged before cleanup application",
            ),
            self._manual_evidence_check(
                "label_support_policy_reviewed",
                "passed"
                if label_policy.get("policy") in {"class_weighting", "label_consolidation", "sample_expansion"}
                and bool(label_policy.get("rationale"))
                else "warning",
                {"policy": label_policy.get("policy"), "has_rationale": bool(label_policy.get("rationale"))},
                "class_weighting|label_consolidation|sample_expansion with rationale",
                "low-support labels require a documented policy before training freeze",
            ),
            self._manual_evidence_check(
                "reviewer_metadata_present",
                "passed" if bool(reviewer.get("name")) and bool(reviewer.get("reviewed_at")) else "blocked",
                {"name_present": bool(reviewer.get("name")), "reviewed_at_present": bool(reviewer.get("reviewed_at"))},
                "reviewer.name + reviewer.reviewed_at",
                "manual evidence package must identify the human reviewer and review timestamp",
            ),
            self._manual_evidence_check(
                "record_bodies_excluded",
                "passed" if not forbidden_paths else "blocked",
                {"forbidden_paths": forbidden_paths},
                [],
                "manual evidence package must not include records, rows, normalized_json, or source bodies",
            ),
            self._manual_evidence_check(
                "execution_requests_excluded",
                "passed" if not forbidden_actions else "blocked",
                {"forbidden_paths": forbidden_actions},
                [],
                "manual evidence package must not request SQL, shell, patch, export, training, or learning-sample writes",
            ),
        ]

    def _manual_evidence_check(self, name: str, status: str, value: Any, limit: Any, reason: str) -> dict[str, Any]:
        return {
            "name": name,
            "status": status,
            "value": value,
            "limit": limit,
            "reason": reason,
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _manual_evidence_acceptance_checks(
        self,
        manual_evidence: dict[str, Any],
        accepted_by: str,
        acceptance_decision: str,
    ) -> list[dict[str, Any]]:
        evidence_summary = manual_evidence.get("evidence_summary") or {}
        manual_summary = manual_evidence.get("summary") or {}
        manual_decision = manual_evidence.get("decision") or {}
        check_status = {
            str(check.get("name")): str(check.get("status"))
            for check in manual_evidence.get("checks") or []
            if isinstance(check, dict)
        }
        allowed_decisions = {"accepted_for_cleanup_review", "needs_revision", "rejected"}
        blocked_check_count = int(manual_summary.get("blocked_check_count") or 0)
        return [
            self._manual_evidence_check(
                "manual_evidence_available",
                "passed" if manual_evidence.get("id") else "blocked",
                manual_evidence.get("id"),
                "existing manual evidence verification",
                "acceptance review must reference an existing manual evidence verification event",
            ),
            self._manual_evidence_check(
                "manual_evidence_package_verified",
                "passed"
                if manual_evidence.get("status") == "manual_evidence_package_verified_for_cleanup_review"
                and manual_decision.get("manual_evidence_accepted_for_review") is True
                else "blocked",
                {
                    "status": manual_evidence.get("status"),
                    "manual_evidence_accepted_for_review": manual_decision.get("manual_evidence_accepted_for_review"),
                },
                "manual_evidence_package_verified_for_cleanup_review",
                "only a passed P9 manual evidence verification can be accepted for cleanup review",
            ),
            self._manual_evidence_check(
                "manual_evidence_blocked_checks_clear",
                "passed" if blocked_check_count == 0 else "blocked",
                blocked_check_count,
                0,
                "manual evidence cannot have blocked checks at acceptance time",
            ),
            self._manual_evidence_check(
                "evidence_package_hash_present",
                "passed" if bool(evidence_summary.get("evidence_package_hash")) else "blocked",
                bool(evidence_summary.get("evidence_package_hash")),
                True,
                "acceptance review must pin the exact manual evidence summary hash",
            ),
            self._manual_evidence_check(
                "record_bodies_excluded",
                "passed"
                if not evidence_summary.get("record_bodies_included") and not manual_summary.get("record_bodies_included")
                else "blocked",
                {
                    "evidence_summary_record_bodies": bool(evidence_summary.get("record_bodies_included")),
                    "manual_summary_record_bodies": bool(manual_summary.get("record_bodies_included")),
                },
                "no record bodies",
                "acceptance review must not rely on or persist source record bodies",
            ),
            self._manual_evidence_check(
                "execution_requests_excluded",
                "passed" if check_status.get("execution_requests_excluded") == "passed" else "blocked",
                check_status.get("execution_requests_excluded"),
                "passed",
                "manual evidence must not include SQL, shell, patch, export, training, or mutation requests",
            ),
            self._manual_evidence_check(
                "acceptance_metadata_present",
                "passed" if bool(accepted_by) and acceptance_decision in allowed_decisions else "blocked",
                {"accepted_by_present": bool(accepted_by), "acceptance_decision": acceptance_decision},
                sorted(allowed_decisions),
                "operator acceptance metadata must be explicit and constrained",
            ),
            self._manual_evidence_check(
                "acceptance_decision_allows_review_only_progress",
                "passed" if acceptance_decision == "accepted_for_cleanup_review" else "blocked",
                acceptance_decision,
                "accepted_for_cleanup_review",
                "needs_revision or rejected evidence cannot advance to the next review gate",
            ),
            self._manual_evidence_check(
                "cleanup_and_training_remain_blocked",
                "passed"
                if manual_decision.get("cleanup_application_allowed_now") is False
                and manual_decision.get("cleanup_executed_now") is False
                and manual_decision.get("writes_learning_samples_now") is False
                and manual_decision.get("training_started_now") is False
                else "blocked",
                {
                    "cleanup_application_allowed_now": manual_decision.get("cleanup_application_allowed_now"),
                    "cleanup_executed_now": manual_decision.get("cleanup_executed_now"),
                    "writes_learning_samples_now": manual_decision.get("writes_learning_samples_now"),
                    "training_started_now": manual_decision.get("training_started_now"),
                },
                "all false",
                "P10 acceptance is evidence-only and cannot permit cleanup or training execution",
            ),
        ]

    def _cleanup_application_review_checks(
        self,
        acceptance: dict[str, Any],
        reviewed_by: str,
        review_decision: str,
    ) -> list[dict[str, Any]]:
        evidence_summary = acceptance.get("evidence_summary") or {}
        acceptance_summary = acceptance.get("summary") or {}
        acceptance_decision = acceptance.get("decision") or {}
        allowed_decisions = {"ready_for_future_cleanup_application", "needs_revision", "rejected"}
        blocked_check_count = int(acceptance_summary.get("blocked_check_count") or 0)
        return [
            self._manual_evidence_check(
                "acceptance_review_available",
                "passed" if acceptance.get("id") else "blocked",
                acceptance.get("id"),
                "existing manual evidence acceptance review",
                "cleanup application review must reference an existing P10 acceptance event",
            ),
            self._manual_evidence_check(
                "acceptance_ready_for_cleanup_review",
                "passed"
                if acceptance.get("status") == "manual_evidence_accepted_for_cleanup_review"
                and acceptance_decision.get("manual_evidence_ready_for_cleanup_application_review") is True
                else "blocked",
                {
                    "status": acceptance.get("status"),
                    "manual_evidence_ready_for_cleanup_application_review": acceptance_decision.get(
                        "manual_evidence_ready_for_cleanup_application_review"
                    ),
                },
                "manual_evidence_accepted_for_cleanup_review",
                "only a passed P10 acceptance review can enter cleanup application review",
            ),
            self._manual_evidence_check(
                "acceptance_blocked_checks_clear",
                "passed" if blocked_check_count == 0 else "blocked",
                blocked_check_count,
                0,
                "P10 acceptance checks must have no blocked items",
            ),
            self._manual_evidence_check(
                "evidence_hash_pinned",
                "passed" if bool(evidence_summary.get("evidence_package_hash")) else "blocked",
                bool(evidence_summary.get("evidence_package_hash")),
                True,
                "cleanup application review must pin the evidence package hash carried from P9/P10",
            ),
            self._manual_evidence_check(
                "record_bodies_excluded",
                "passed"
                if not evidence_summary.get("record_bodies_included") and not acceptance_summary.get("record_bodies_included")
                else "blocked",
                {
                    "evidence_summary_record_bodies": bool(evidence_summary.get("record_bodies_included")),
                    "acceptance_summary_record_bodies": bool(acceptance_summary.get("record_bodies_included")),
                },
                "no record bodies",
                "cleanup application review must not persist source records or normalized row bodies",
            ),
            self._manual_evidence_check(
                "review_metadata_present",
                "passed" if bool(reviewed_by) and review_decision in allowed_decisions else "blocked",
                {"reviewed_by_present": bool(reviewed_by), "review_decision": review_decision},
                sorted(allowed_decisions),
                "operator review metadata must be explicit and constrained",
            ),
            self._manual_evidence_check(
                "review_decision_allows_future_gate",
                "passed" if review_decision == "ready_for_future_cleanup_application" else "blocked",
                review_decision,
                "ready_for_future_cleanup_application",
                "needs_revision or rejected cleanup application reviews cannot advance",
            ),
            self._manual_evidence_check(
                "source_acceptance_kept_execution_blocked",
                "passed"
                if acceptance_decision.get("cleanup_application_allowed_now") is False
                and acceptance_decision.get("cleanup_executed_now") is False
                and acceptance_decision.get("writes_learning_samples_now") is False
                and acceptance_decision.get("training_started_now") is False
                else "blocked",
                {
                    "cleanup_application_allowed_now": acceptance_decision.get("cleanup_application_allowed_now"),
                    "cleanup_executed_now": acceptance_decision.get("cleanup_executed_now"),
                    "writes_learning_samples_now": acceptance_decision.get("writes_learning_samples_now"),
                    "training_started_now": acceptance_decision.get("training_started_now"),
                },
                "all false",
                "P10 acceptance must not have granted execution, learning-sample writes, or training",
            ),
            self._manual_evidence_check(
                "cleanup_and_training_remain_blocked",
                "passed",
                {
                    "cleanup_application_allowed_now": False,
                    "cleanup_executed_now": False,
                    "writes_learning_samples_now": False,
                    "training_started_now": False,
                },
                "all false",
                "P11 cleanup application review is still evidence-only and cannot execute cleanup or training",
            ),
        ]

    def _cleanup_execution_approval_steps(self, application: dict[str, Any]) -> list[dict[str, Any]]:
        package_id = application.get("package_id")
        evidence_hash = (application.get("evidence_summary") or {}).get("evidence_package_hash")
        base = {
            "source_cleanup_application_review_id": application.get("id"),
            "package_id": package_id,
            "evidence_package_hash": evidence_hash,
            "contains_sql": False,
            "contains_executable_code": False,
            "can_execute_now": False,
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }
        return [
            {
                **base,
                "id": "confirm_evidence_hash",
                "name": "Confirm P9/P10/P11 evidence hash and metadata chain before execution approval.",
                "execution_mode": "manual_review_required",
                "approval_required": True,
                "acceptance_checks": [
                    "Evidence package hash matches the accepted manual evidence chain.",
                    "No source record bodies are included in the approval plan.",
                ],
                "forbidden_actions": ["execute_sql", "mutate_staging_records", "write_learning_samples", "start_training"],
            },
            {
                **base,
                "id": "approve_deterministic_split_assignment",
                "name": "Approve deterministic split assignment policy for future cleanup execution.",
                "execution_mode": "future_script_after_manual_approval",
                "approval_required": True,
                "acceptance_checks": [
                    "Split policy is deterministic and time-aware.",
                    "Future execution must log affected record counts before mutation.",
                ],
                "forbidden_actions": ["execute_now", "write_source_dataset", "start_training"],
            },
            {
                **base,
                "id": "approve_historical_outcome_join",
                "name": "Approve historical outcome join and target-field coverage for future cleanup execution.",
                "execution_mode": "future_script_after_manual_approval",
                "approval_required": True,
                "acceptance_checks": [
                    "Join keys remain stock_code and signal_date.",
                    "Historical outcome source hash is pinned before any write.",
                ],
                "forbidden_actions": ["execute_now", "store_record_bodies", "write_learning_samples"],
            },
            {
                **base,
                "id": "approve_quality_flag_dispositions",
                "name": "Approve quality flag dispositions and quarantine policy for future cleanup execution.",
                "execution_mode": "future_script_after_manual_approval",
                "approval_required": True,
                "acceptance_checks": [
                    "Every unresolved quality flag is corrected, accepted with evidence, or quarantined.",
                    "Future execution reports before/after quality counts.",
                ],
                "forbidden_actions": ["execute_now", "bypass_quarantine", "start_training"],
            },
            {
                **base,
                "id": "approve_post_cleanup_verification",
                "name": "Approve post-cleanup verification gates before any promotion to learning samples.",
                "execution_mode": "manual_review_required",
                "approval_required": True,
                "acceptance_checks": [
                    "A later stage must rerun staging quality review after cleanup.",
                    "Promotion to learning_samples remains a separate reviewed stage.",
                ],
                "forbidden_actions": ["write_learning_samples", "start_training", "enable_live_trading"],
            },
        ]

    def _cleanup_execution_approval_plan_checks(
        self,
        application: dict[str, Any],
        approval_steps: list[dict[str, Any]],
        planned_by: str,
        plan_decision: str,
    ) -> list[dict[str, Any]]:
        evidence_summary = application.get("evidence_summary") or {}
        application_summary = application.get("summary") or {}
        application_decision = application.get("decision") or {}
        allowed_decisions = {"prepared_for_manual_approval", "needs_revision", "rejected"}
        blocked_check_count = int(application_summary.get("blocked_check_count") or 0)
        contains_sql = any(bool(step.get("contains_sql")) for step in approval_steps)
        contains_executable_code = any(bool(step.get("contains_executable_code")) for step in approval_steps)
        can_execute_now = any(bool(step.get("can_execute_now")) for step in approval_steps)
        forbidden_actions = {
            str(action)
            for step in approval_steps
            for action in (step.get("forbidden_actions") or [])
        }
        required_forbidden = {"execute_sql", "mutate_staging_records", "write_learning_samples", "start_training"}
        return [
            self._manual_evidence_check(
                "cleanup_application_review_available",
                "passed" if application.get("id") else "blocked",
                application.get("id"),
                "existing cleanup application review",
                "execution approval plan must reference an existing P11 cleanup application review",
            ),
            self._manual_evidence_check(
                "cleanup_application_review_ready",
                "passed"
                if application.get("status") == "cleanup_application_review_ready"
                and application_decision.get("cleanup_application_ready_for_future_plan") is True
                else "blocked",
                {
                    "status": application.get("status"),
                    "cleanup_application_ready_for_future_plan": application_decision.get(
                        "cleanup_application_ready_for_future_plan"
                    ),
                },
                "cleanup_application_review_ready",
                "only a passed P11 cleanup application review can generate an approval plan",
            ),
            self._manual_evidence_check(
                "application_blocked_checks_clear",
                "passed" if blocked_check_count == 0 else "blocked",
                blocked_check_count,
                0,
                "P11 cleanup application review checks must have no blocked items",
            ),
            self._manual_evidence_check(
                "evidence_hash_pinned",
                "passed" if bool(evidence_summary.get("evidence_package_hash")) else "blocked",
                bool(evidence_summary.get("evidence_package_hash")),
                True,
                "execution approval plan must pin the evidence hash carried from P9-P11",
            ),
            self._manual_evidence_check(
                "approval_steps_present",
                "passed" if len(approval_steps) >= 5 else "blocked",
                len(approval_steps),
                ">=5 approval steps",
                "future cleanup execution approval must enumerate deterministic review steps",
            ),
            self._manual_evidence_check(
                "plan_contains_no_executable_payload",
                "passed" if not contains_sql and not contains_executable_code and not can_execute_now else "blocked",
                {
                    "contains_sql": contains_sql,
                    "contains_executable_code": contains_executable_code,
                    "can_execute_now": can_execute_now,
                },
                "all false",
                "P12 may prepare an approval plan but cannot include executable SQL or runnable code",
            ),
            self._manual_evidence_check(
                "forbidden_actions_complete",
                "passed" if required_forbidden.issubset(forbidden_actions) else "blocked",
                sorted(forbidden_actions),
                sorted(required_forbidden),
                "approval plan must explicitly forbid SQL, staging mutation, learning-sample writes, and training",
            ),
            self._manual_evidence_check(
                "planning_metadata_present",
                "passed" if bool(planned_by) and plan_decision in allowed_decisions else "blocked",
                {"planned_by_present": bool(planned_by), "plan_decision": plan_decision},
                sorted(allowed_decisions),
                "operator planning metadata must be explicit and constrained",
            ),
            self._manual_evidence_check(
                "plan_decision_allows_manual_approval_path",
                "passed" if plan_decision == "prepared_for_manual_approval" else "blocked",
                plan_decision,
                "prepared_for_manual_approval",
                "needs_revision or rejected approval plans cannot advance",
            ),
            self._manual_evidence_check(
                "source_application_kept_execution_blocked",
                "passed"
                if application_decision.get("cleanup_application_allowed_now") is False
                and application_decision.get("cleanup_executed_now") is False
                and application_decision.get("writes_learning_samples_now") is False
                and application_decision.get("training_started_now") is False
                else "blocked",
                {
                    "cleanup_application_allowed_now": application_decision.get("cleanup_application_allowed_now"),
                    "cleanup_executed_now": application_decision.get("cleanup_executed_now"),
                    "writes_learning_samples_now": application_decision.get("writes_learning_samples_now"),
                    "training_started_now": application_decision.get("training_started_now"),
                },
                "all false",
                "P11 cleanup application review must not have granted execution, learning-sample writes, or training",
            ),
            self._manual_evidence_check(
                "cleanup_and_training_remain_blocked",
                "passed",
                {
                    "cleanup_execution_approved_now": False,
                    "cleanup_application_allowed_now": False,
                    "cleanup_executed_now": False,
                    "writes_learning_samples_now": False,
                    "training_started_now": False,
                },
                "all false",
                "P12 approval plan is still evidence-only and cannot approve cleanup execution or training",
            ),
        ]

    def _cleanup_execution_manual_approval_checks(
        self,
        approval_plan: dict[str, Any],
        approved_by: str,
        approval_decision: str,
    ) -> list[dict[str, Any]]:
        evidence_summary = approval_plan.get("evidence_summary") or {}
        plan_summary = approval_plan.get("summary") or {}
        plan_decision = approval_plan.get("decision") or {}
        plan_body = approval_plan.get("approval_plan") or {}
        allowed_decisions = {"approved_for_cleanup_execution_preflight", "needs_revision", "rejected"}
        blocked_check_count = int(plan_summary.get("blocked_check_count") or 0)
        return [
            self._manual_evidence_check(
                "approval_plan_available",
                "passed" if approval_plan.get("id") else "blocked",
                approval_plan.get("id"),
                "existing cleanup execution approval plan",
                "manual approval metadata must reference an existing P12 approval plan",
            ),
            self._manual_evidence_check(
                "approval_plan_ready_for_manual_approval",
                "passed"
                if approval_plan.get("status") == "cleanup_execution_approval_plan_ready"
                and plan_decision.get("cleanup_execution_plan_ready_for_manual_approval") is True
                else "blocked",
                {
                    "status": approval_plan.get("status"),
                    "cleanup_execution_plan_ready_for_manual_approval": plan_decision.get(
                        "cleanup_execution_plan_ready_for_manual_approval"
                    ),
                },
                "cleanup_execution_approval_plan_ready",
                "only a passed P12 approval plan can receive manual approval metadata",
            ),
            self._manual_evidence_check(
                "source_plan_blocked_checks_clear",
                "passed" if blocked_check_count == 0 else "blocked",
                blocked_check_count,
                0,
                "P12 approval plan checks must have no blocked items",
            ),
            self._manual_evidence_check(
                "evidence_hash_pinned",
                "passed" if bool(evidence_summary.get("evidence_package_hash")) else "blocked",
                bool(evidence_summary.get("evidence_package_hash")),
                True,
                "manual approval must pin the same evidence package hash carried through P9-P12",
            ),
            self._manual_evidence_check(
                "approval_steps_complete",
                "passed" if int(plan_body.get("step_count") or 0) >= 5 else "blocked",
                int(plan_body.get("step_count") or 0),
                ">=5 approval steps",
                "manual approval must be based on the complete P12 approval plan",
            ),
            self._manual_evidence_check(
                "source_plan_contains_no_executable_payload",
                "passed"
                if not plan_body.get("contains_sql")
                and not plan_body.get("contains_executable_code")
                and not plan_body.get("can_execute_now")
                else "blocked",
                {
                    "contains_sql": bool(plan_body.get("contains_sql")),
                    "contains_executable_code": bool(plan_body.get("contains_executable_code")),
                    "can_execute_now": bool(plan_body.get("can_execute_now")),
                },
                "all false",
                "manual approval metadata cannot be based on an executable P12 payload",
            ),
            self._manual_evidence_check(
                "record_bodies_excluded",
                "passed"
                if not evidence_summary.get("record_bodies_included") and not plan_summary.get("record_bodies_included")
                else "blocked",
                {
                    "evidence_summary_record_bodies": bool(evidence_summary.get("record_bodies_included")),
                    "plan_summary_record_bodies": bool(plan_summary.get("record_bodies_included")),
                },
                "no record bodies",
                "manual approval metadata must not persist source or normalized record bodies",
            ),
            self._manual_evidence_check(
                "manual_approval_metadata_present",
                "passed" if bool(approved_by) and approval_decision in allowed_decisions else "blocked",
                {"approved_by_present": bool(approved_by), "approval_decision": approval_decision},
                sorted(allowed_decisions),
                "operator approval metadata must be explicit and constrained",
            ),
            self._manual_evidence_check(
                "manual_approval_allows_preflight_only",
                "passed" if approval_decision == "approved_for_cleanup_execution_preflight" else "blocked",
                approval_decision,
                "approved_for_cleanup_execution_preflight",
                "needs_revision or rejected approval metadata cannot advance to cleanup execution preflight",
            ),
            self._manual_evidence_check(
                "source_plan_kept_execution_blocked",
                "passed"
                if plan_decision.get("cleanup_execution_approved_now") is False
                and plan_decision.get("cleanup_application_allowed_now") is False
                and plan_decision.get("cleanup_executed_now") is False
                and plan_decision.get("writes_learning_samples_now") is False
                and plan_decision.get("training_started_now") is False
                else "blocked",
                {
                    "cleanup_execution_approved_now": plan_decision.get("cleanup_execution_approved_now"),
                    "cleanup_application_allowed_now": plan_decision.get("cleanup_application_allowed_now"),
                    "cleanup_executed_now": plan_decision.get("cleanup_executed_now"),
                    "writes_learning_samples_now": plan_decision.get("writes_learning_samples_now"),
                    "training_started_now": plan_decision.get("training_started_now"),
                },
                "all false",
                "P12 approval plan must not have granted current cleanup execution or training",
            ),
            self._manual_evidence_check(
                "cleanup_and_training_remain_blocked",
                "passed",
                {
                    "cleanup_execution_approved_now": False,
                    "cleanup_application_allowed_now": False,
                    "cleanup_executed_now": False,
                    "can_execute_cleanup_now": False,
                    "writes_learning_samples_now": False,
                    "training_started_now": False,
                },
                "all false",
                "P13 records manual approval metadata only; execution, learning-sample writes, and training stay blocked",
            ),
        ]

    def _cleanup_execution_preflight_checks(
        self,
        manual_approval: dict[str, Any],
        preflight: dict[str, Any],
        requested_by: str,
        preflight_decision: str,
    ) -> list[dict[str, Any]]:
        evidence_summary = manual_approval.get("evidence_summary") or {}
        approval_summary = manual_approval.get("summary") or {}
        approval_decision = manual_approval.get("decision") or {}
        allowed_decisions = {"prepared_for_cleanup_execution_dry_run", "needs_revision", "rejected"}
        blocked_check_count = int(approval_summary.get("blocked_check_count") or 0)
        environment = preflight.get("environment") or {}
        impact = preflight.get("impact") or {}
        rollback = preflight.get("rollback_plan") or {}
        return [
            self._manual_evidence_check(
                "manual_approval_available",
                "passed" if manual_approval.get("id") else "blocked",
                manual_approval.get("id"),
                "existing cleanup execution manual approval",
                "cleanup execution preflight must reference an existing P13 manual approval event",
            ),
            self._manual_evidence_check(
                "manual_approval_ready_for_preflight",
                "passed"
                if manual_approval.get("status") == "cleanup_execution_manual_approval_ready_for_preflight"
                and approval_decision.get("cleanup_execution_approval_metadata_accepted") is True
                and approval_decision.get("can_generate_cleanup_execution_preflight_now") is True
                else "blocked",
                {
                    "status": manual_approval.get("status"),
                    "cleanup_execution_approval_metadata_accepted": approval_decision.get(
                        "cleanup_execution_approval_metadata_accepted"
                    ),
                    "can_generate_cleanup_execution_preflight_now": approval_decision.get(
                        "can_generate_cleanup_execution_preflight_now"
                    ),
                },
                "cleanup_execution_manual_approval_ready_for_preflight",
                "only a passed P13 manual approval can enter cleanup execution preflight",
            ),
            self._manual_evidence_check(
                "source_manual_approval_blocked_checks_clear",
                "passed" if blocked_check_count == 0 else "blocked",
                blocked_check_count,
                0,
                "P13 manual approval checks must have no blocked items",
            ),
            self._manual_evidence_check(
                "evidence_hash_pinned",
                "passed" if bool(evidence_summary.get("evidence_package_hash")) else "blocked",
                bool(evidence_summary.get("evidence_package_hash")),
                True,
                "preflight must pin the evidence package hash carried through P9-P13",
            ),
            self._manual_evidence_check(
                "staging_package_available",
                "passed" if bool(environment.get("package_id")) and int(environment.get("staging_record_count") or 0) > 0 else "blocked",
                {
                    "package_id": environment.get("package_id"),
                    "staging_record_count": environment.get("staging_record_count"),
                },
                "package id with staged rows",
                "cleanup execution preflight needs a staged package to count before any future mutation",
            ),
            self._manual_evidence_check(
                "learning_samples_unchanged",
                "passed"
                if impact.get("learning_sample_count_before") == impact.get("expected_learning_sample_count_after")
                else "blocked",
                {
                    "before": impact.get("learning_sample_count_before"),
                    "expected_after": impact.get("expected_learning_sample_count_after"),
                },
                "unchanged",
                "P14 preflight cannot write or project writes to learning_samples",
            ),
            self._manual_evidence_check(
                "rollback_plan_required",
                "passed"
                if rollback.get("required") is True
                and rollback.get("snapshot_required_before_execution") is True
                and rollback.get("verified_now") is False
                else "blocked",
                rollback,
                "rollback required but not executed",
                "future cleanup execution must have rollback metadata before any mutation",
            ),
            self._manual_evidence_check(
                "lock_key_generated",
                "passed" if bool(preflight.get("lock_key")) else "blocked",
                preflight.get("lock_key"),
                "deterministic lock key",
                "preflight must identify a future execution lock key before any mutation",
            ),
            self._manual_evidence_check(
                "preflight_contains_no_executable_payload",
                "passed"
                if not preflight.get("contains_sql")
                and not preflight.get("contains_executable_code")
                and not preflight.get("can_execute_now")
                else "blocked",
                {
                    "contains_sql": bool(preflight.get("contains_sql")),
                    "contains_executable_code": bool(preflight.get("contains_executable_code")),
                    "can_execute_now": bool(preflight.get("can_execute_now")),
                },
                "all false",
                "P14 preflight cannot contain executable SQL, runnable code, or execution permission",
            ),
            self._manual_evidence_check(
                "request_metadata_present",
                "passed" if bool(requested_by) and preflight_decision in allowed_decisions else "blocked",
                {"requested_by_present": bool(requested_by), "preflight_decision": preflight_decision},
                sorted(allowed_decisions),
                "operator preflight metadata must be explicit and constrained",
            ),
            self._manual_evidence_check(
                "preflight_decision_allows_dry_run_only",
                "passed" if preflight_decision == "prepared_for_cleanup_execution_dry_run" else "blocked",
                preflight_decision,
                "prepared_for_cleanup_execution_dry_run",
                "needs_revision or rejected preflight metadata cannot advance to cleanup execution dry-run",
            ),
            self._manual_evidence_check(
                "source_manual_approval_kept_execution_blocked",
                "passed"
                if approval_decision.get("cleanup_execution_approved_now") is False
                and approval_decision.get("cleanup_application_allowed_now") is False
                and approval_decision.get("cleanup_executed_now") is False
                and approval_decision.get("writes_learning_samples_now") is False
                and approval_decision.get("training_started_now") is False
                else "blocked",
                {
                    "cleanup_execution_approved_now": approval_decision.get("cleanup_execution_approved_now"),
                    "cleanup_application_allowed_now": approval_decision.get("cleanup_application_allowed_now"),
                    "cleanup_executed_now": approval_decision.get("cleanup_executed_now"),
                    "writes_learning_samples_now": approval_decision.get("writes_learning_samples_now"),
                    "training_started_now": approval_decision.get("training_started_now"),
                },
                "all false",
                "P13 approval metadata must not have executed cleanup or training",
            ),
            self._manual_evidence_check(
                "cleanup_and_training_remain_blocked",
                "passed",
                {
                    "cleanup_execution_approved_now": False,
                    "cleanup_application_allowed_now": False,
                    "cleanup_executed_now": False,
                    "can_execute_cleanup_now": False,
                    "writes_learning_samples_now": False,
                    "training_started_now": False,
                },
                "all false",
                "P14 preflight is metadata-only; execution, learning-sample writes, and training stay blocked",
            ),
        ]

    def _cleanup_execution_dry_run_checks(
        self,
        preflight: dict[str, Any],
        simulation: dict[str, Any],
        simulated_by: str,
        dry_run_decision: str,
    ) -> list[dict[str, Any]]:
        preflight_summary = preflight.get("summary") or {}
        preflight_decision = preflight.get("decision") or {}
        allowed_decisions = {"simulated_for_manual_review", "needs_revision", "rejected"}
        blocked_check_count = int(preflight_summary.get("blocked_check_count") or 0)
        return [
            self._manual_evidence_check(
                "preflight_available",
                "passed" if preflight.get("id") else "blocked",
                preflight.get("id"),
                "existing cleanup execution preflight",
                "cleanup execution dry-run must reference an existing P14 preflight event",
            ),
            self._manual_evidence_check(
                "preflight_ready_for_dry_run",
                "passed"
                if preflight.get("status") == "cleanup_execution_preflight_ready_for_dry_run"
                and preflight_decision.get("cleanup_execution_preflight_ready_for_dry_run") is True
                else "blocked",
                {
                    "status": preflight.get("status"),
                    "cleanup_execution_preflight_ready_for_dry_run": preflight_decision.get(
                        "cleanup_execution_preflight_ready_for_dry_run"
                    ),
                },
                "cleanup_execution_preflight_ready_for_dry_run",
                "only a passed P14 preflight can enter cleanup execution dry-run",
            ),
            self._manual_evidence_check(
                "source_preflight_blocked_checks_clear",
                "passed" if blocked_check_count == 0 else "blocked",
                blocked_check_count,
                0,
                "P14 preflight checks must have no blocked items",
            ),
            self._manual_evidence_check(
                "candidate_records_available",
                "passed" if int(simulation.get("candidate_record_count") or 0) > 0 else "blocked",
                simulation.get("candidate_record_count"),
                ">0",
                "dry-run needs candidate staged records to simulate future cleanup impact",
            ),
            self._manual_evidence_check(
                "simulation_contains_no_executable_payload",
                "passed"
                if not simulation.get("contains_sql")
                and not simulation.get("contains_executable_code")
                and not simulation.get("can_execute_now")
                else "blocked",
                {
                    "contains_sql": bool(simulation.get("contains_sql")),
                    "contains_executable_code": bool(simulation.get("contains_executable_code")),
                    "can_execute_now": bool(simulation.get("can_execute_now")),
                },
                "all false",
                "P15 dry-run cannot contain executable SQL, runnable code, or execution permission",
            ),
            self._manual_evidence_check(
                "simulation_is_aggregate_only",
                "passed"
                if simulation.get("record_bodies_included") is False
                and simulation.get("affected_rows_body_included") is False
                else "blocked",
                {
                    "record_bodies_included": simulation.get("record_bodies_included"),
                    "affected_rows_body_included": simulation.get("affected_rows_body_included"),
                },
                "no record bodies",
                "dry-run event may store aggregate counts only, not source or normalized record bodies",
            ),
            self._manual_evidence_check(
                "learning_samples_unchanged",
                "passed"
                if simulation.get("learning_sample_count_before") == simulation.get("expected_learning_sample_count_after")
                else "blocked",
                {
                    "before": simulation.get("learning_sample_count_before"),
                    "expected_after": simulation.get("expected_learning_sample_count_after"),
                },
                "unchanged",
                "P15 dry-run cannot write or project writes to learning_samples",
            ),
            self._manual_evidence_check(
                "dry_run_metadata_present",
                "passed" if bool(simulated_by) and dry_run_decision in allowed_decisions else "blocked",
                {"simulated_by_present": bool(simulated_by), "dry_run_decision": dry_run_decision},
                sorted(allowed_decisions),
                "operator dry-run metadata must be explicit and constrained",
            ),
            self._manual_evidence_check(
                "dry_run_decision_allows_manual_review_only",
                "passed" if dry_run_decision == "simulated_for_manual_review" else "blocked",
                dry_run_decision,
                "simulated_for_manual_review",
                "needs_revision or rejected dry-runs cannot advance to manual execution review",
            ),
            self._manual_evidence_check(
                "source_preflight_kept_execution_blocked",
                "passed"
                if preflight_decision.get("cleanup_execution_approved_now") is False
                and preflight_decision.get("cleanup_application_allowed_now") is False
                and preflight_decision.get("cleanup_executed_now") is False
                and preflight_decision.get("writes_learning_samples_now") is False
                and preflight_decision.get("training_started_now") is False
                else "blocked",
                {
                    "cleanup_execution_approved_now": preflight_decision.get("cleanup_execution_approved_now"),
                    "cleanup_application_allowed_now": preflight_decision.get("cleanup_application_allowed_now"),
                    "cleanup_executed_now": preflight_decision.get("cleanup_executed_now"),
                    "writes_learning_samples_now": preflight_decision.get("writes_learning_samples_now"),
                    "training_started_now": preflight_decision.get("training_started_now"),
                },
                "all false",
                "P14 preflight must not have executed cleanup or training",
            ),
            self._manual_evidence_check(
                "cleanup_and_training_remain_blocked",
                "passed",
                {
                    "cleanup_execution_approved_now": False,
                    "cleanup_application_allowed_now": False,
                    "cleanup_executed_now": False,
                    "can_execute_cleanup_now": False,
                    "writes_learning_samples_now": False,
                    "training_started_now": False,
                },
                "all false",
                "P15 dry-run is aggregate simulation only; execution, learning-sample writes, and training stay blocked",
            ),
        ]

    def _cleanup_execution_dry_run_review_checks(
        self,
        dry_run: dict[str, Any],
        reviewed_by: str,
        review_decision: str,
    ) -> list[dict[str, Any]]:
        summary = dry_run.get("summary") or {}
        decision = dry_run.get("decision") or {}
        simulation = dry_run.get("simulation") or {}
        allowed_decisions = {"approved_for_cleanup_execution_plan", "needs_revision", "rejected"}
        blocked_check_count = int(summary.get("blocked_check_count") or 0)
        return [
            self._manual_evidence_check(
                "dry_run_available",
                "passed" if dry_run.get("id") else "blocked",
                dry_run.get("id"),
                "existing cleanup execution dry-run",
                "cleanup execution dry-run review must reference an existing P15 dry-run event",
            ),
            self._manual_evidence_check(
                "dry_run_ready_for_manual_review",
                "passed"
                if dry_run.get("status") == "cleanup_execution_dry_run_ready_for_review"
                and decision.get("cleanup_execution_dry_run_ready_for_review") is True
                else "blocked",
                {
                    "status": dry_run.get("status"),
                    "cleanup_execution_dry_run_ready_for_review": decision.get(
                        "cleanup_execution_dry_run_ready_for_review"
                    ),
                },
                "cleanup_execution_dry_run_ready_for_review",
                "only a passed P15 dry-run can enter manual review for a future cleanup execution plan",
            ),
            self._manual_evidence_check(
                "source_dry_run_blocked_checks_clear",
                "passed" if blocked_check_count == 0 else "blocked",
                blocked_check_count,
                0,
                "P15 dry-run checks must have no blocked items",
            ),
            self._manual_evidence_check(
                "aggregate_simulation_present",
                "passed" if int(simulation.get("candidate_record_count") or 0) > 0 else "blocked",
                simulation.get("candidate_record_count"),
                ">0",
                "manual review needs aggregate candidate counts from the P15 dry-run",
            ),
            self._manual_evidence_check(
                "simulation_contains_no_executable_payload",
                "passed"
                if not simulation.get("contains_sql")
                and not simulation.get("contains_executable_code")
                and not simulation.get("can_execute_now")
                else "blocked",
                {
                    "contains_sql": bool(simulation.get("contains_sql")),
                    "contains_executable_code": bool(simulation.get("contains_executable_code")),
                    "can_execute_now": bool(simulation.get("can_execute_now")),
                },
                "all false",
                "P16 review cannot approve or carry executable SQL, runnable code, or execution permission",
            ),
            self._manual_evidence_check(
                "aggregate_only_no_record_bodies",
                "passed"
                if simulation.get("record_bodies_included") is False
                and simulation.get("affected_rows_body_included") is False
                and summary.get("record_bodies_included") is False
                else "blocked",
                {
                    "simulation_record_bodies_included": simulation.get("record_bodies_included"),
                    "affected_rows_body_included": simulation.get("affected_rows_body_included"),
                    "summary_record_bodies_included": summary.get("record_bodies_included"),
                },
                "no record bodies",
                "dry-run review may store aggregate counts and hashes only",
            ),
            self._manual_evidence_check(
                "learning_samples_unchanged",
                "passed"
                if simulation.get("learning_sample_count_before") == simulation.get("expected_learning_sample_count_after")
                else "blocked",
                {
                    "before": simulation.get("learning_sample_count_before"),
                    "expected_after": simulation.get("expected_learning_sample_count_after"),
                },
                "unchanged",
                "P16 review cannot write or project writes to learning_samples",
            ),
            self._manual_evidence_check(
                "review_metadata_present",
                "passed" if bool(reviewed_by) and review_decision in allowed_decisions else "blocked",
                {"reviewed_by_present": bool(reviewed_by), "review_decision": review_decision},
                sorted(allowed_decisions),
                "operator review metadata must be explicit and constrained",
            ),
            self._manual_evidence_check(
                "review_decision_allows_future_plan_only",
                "passed" if review_decision == "approved_for_cleanup_execution_plan" else "blocked",
                review_decision,
                "approved_for_cleanup_execution_plan",
                "needs_revision or rejected reviews cannot advance to a later cleanup execution plan",
            ),
            self._manual_evidence_check(
                "source_dry_run_kept_execution_blocked",
                "passed"
                if decision.get("cleanup_execution_approved_now") is False
                and decision.get("cleanup_application_allowed_now") is False
                and decision.get("cleanup_executed_now") is False
                and decision.get("can_execute_cleanup_now") is False
                and decision.get("writes_learning_samples_now") is False
                and decision.get("training_started_now") is False
                else "blocked",
                {
                    "cleanup_execution_approved_now": decision.get("cleanup_execution_approved_now"),
                    "cleanup_application_allowed_now": decision.get("cleanup_application_allowed_now"),
                    "cleanup_executed_now": decision.get("cleanup_executed_now"),
                    "can_execute_cleanup_now": decision.get("can_execute_cleanup_now"),
                    "writes_learning_samples_now": decision.get("writes_learning_samples_now"),
                    "training_started_now": decision.get("training_started_now"),
                },
                "all false",
                "P15 dry-run must not have executed cleanup or training",
            ),
            self._manual_evidence_check(
                "cleanup_and_training_remain_blocked",
                "passed",
                {
                    "cleanup_execution_approved_now": False,
                    "cleanup_application_allowed_now": False,
                    "cleanup_executed_now": False,
                    "can_execute_cleanup_now": False,
                    "writes_learning_samples_now": False,
                    "training_started_now": False,
                },
                "all false",
                "P16 review only permits a future separate execution plan; cleanup and training stay blocked",
            ),
        ]

    def _empty_cleanup_execution_plan(self) -> dict[str, Any]:
        return {
            "scope": "automated_cleanup_operations_only",
            "package_id": None,
            "candidate_record_count": 0,
            "planned_operation_count": 0,
            "automated_operation_count": 0,
            "manual_operation_count": 0,
            "operation_counts": {},
            "automated_operation_counts": {},
            "manual_operation_counts": {},
            "field_counts": {},
            "execution_batches": [],
            "manual_backfill_batches": [],
            "contains_sql": False,
            "contains_executable_code": False,
            "can_execute_now": False,
            "record_bodies_included": False,
            "affected_rows_body_included": False,
            "writes_staging_records_now": False,
            "writes_learning_samples_now": False,
            "review_only": True,
            "simulation_only": True,
        }

    def _cleanup_execution_plan_from_review(self, review: dict[str, Any]) -> dict[str, Any]:
        simulation = review.get("simulation_summary") or {}
        operation_counts = {
            str(name): int(count or 0)
            for name, count in (simulation.get("operation_counts") or {}).items()
        }
        field_counts = {
            str(name): int(count or 0)
            for name, count in (simulation.get("field_counts") or {}).items()
        }
        automated_operations = {"normalize_enum", "parse_stringified_list_items"}
        automated_counts = {
            name: count
            for name, count in operation_counts.items()
            if name in automated_operations and count > 0
        }
        manual_counts = {
            name: count
            for name, count in operation_counts.items()
            if name not in automated_operations and count > 0
        }
        execution_batches = [
            {
                "batch_name": "apply_normalized_preview_to_staging_metadata",
                "operation": name,
                "operation_count": count,
                "mode": "future_controlled_staging_update",
                "requires_preflight": True,
                "requires_transaction": True,
                "allowed_tables": ["dataset2_staging_records"],
                "forbidden_tables": ["learning_samples"],
                "record_bodies_included": False,
                "review_only": True,
                "simulation_only": True,
            }
            for name, count in sorted(automated_counts.items())
        ]
        manual_backfill_batches = [
            {
                "batch_name": f"manual_{name}",
                "operation": name,
                "operation_count": count,
                "mode": "manual_evidence_required_before_training",
                "requires_external_evidence": True,
                "can_execute_automatically": False,
                "record_bodies_included": False,
                "review_only": True,
                "simulation_only": True,
            }
            for name, count in sorted(manual_counts.items())
        ]
        return {
            "scope": "automated_cleanup_operations_only",
            "package_id": review.get("package_id"),
            "candidate_record_count": int(simulation.get("candidate_record_count") or 0),
            "planned_operation_count": sum(automated_counts.values()),
            "automated_operation_count": sum(automated_counts.values()),
            "manual_operation_count": sum(manual_counts.values()),
            "total_simulated_operation_count": sum(operation_counts.values()),
            "operation_counts": operation_counts,
            "automated_operation_counts": automated_counts,
            "manual_operation_counts": manual_counts,
            "field_counts": field_counts,
            "records_with_operations": int(simulation.get("records_with_operations") or 0),
            "records_with_quality_flags": int(simulation.get("records_with_quality_flags") or 0),
            "learning_sample_count_before": int(simulation.get("learning_sample_count_before") or 0),
            "expected_learning_sample_count_after": int(simulation.get("expected_learning_sample_count_after") or 0),
            "execution_batches": execution_batches,
            "manual_backfill_batches": manual_backfill_batches,
            "contains_sql": False,
            "contains_executable_code": False,
            "can_execute_now": False,
            "record_bodies_included": False,
            "affected_rows_body_included": False,
            "writes_staging_records_now": False,
            "writes_learning_samples_now": False,
            "review_only": True,
            "simulation_only": True,
        }

    def _cleanup_execution_plan_checks(
        self,
        review: dict[str, Any],
        execution_plan: dict[str, Any],
        planned_by: str,
        plan_decision: str,
    ) -> list[dict[str, Any]]:
        review_summary = review.get("summary") or {}
        review_decision = review.get("decision") or {}
        allowed_decisions = {"prepared_for_controlled_cleanup_execution_preflight", "needs_revision", "rejected"}
        blocked_check_count = int(review_summary.get("blocked_check_count") or 0)
        return [
            self._manual_evidence_check(
                "dry_run_review_available",
                "passed" if review.get("id") else "blocked",
                review.get("id"),
                "existing cleanup execution dry-run review",
                "cleanup execution plan must reference an existing P16 review event",
            ),
            self._manual_evidence_check(
                "dry_run_review_accepted",
                "passed"
                if review.get("status") == "cleanup_execution_dry_run_review_accepted"
                and review_decision.get("cleanup_execution_dry_run_review_accepted") is True
                else "blocked",
                {
                    "status": review.get("status"),
                    "cleanup_execution_dry_run_review_accepted": review_decision.get(
                        "cleanup_execution_dry_run_review_accepted"
                    ),
                },
                "cleanup_execution_dry_run_review_accepted",
                "only an accepted P16 dry-run review can enter controlled cleanup execution planning",
            ),
            self._manual_evidence_check(
                "source_review_blocked_checks_clear",
                "passed" if blocked_check_count == 0 else "blocked",
                blocked_check_count,
                0,
                "P16 review checks must have no blocked items",
            ),
            self._manual_evidence_check(
                "aggregate_simulation_present",
                "passed" if int(execution_plan.get("candidate_record_count") or 0) > 0 else "blocked",
                execution_plan.get("candidate_record_count"),
                ">0",
                "cleanup execution plan needs aggregate dry-run counts",
            ),
            self._manual_evidence_check(
                "automated_scope_defined",
                "passed" if execution_plan.get("scope") == "automated_cleanup_operations_only" else "blocked",
                execution_plan.get("scope"),
                "automated_cleanup_operations_only",
                "P17 can only plan deterministic automated cleanup operations; manual backfill remains separate",
            ),
            self._manual_evidence_check(
                "plan_contains_no_executable_payload",
                "passed"
                if not execution_plan.get("contains_sql")
                and not execution_plan.get("contains_executable_code")
                and not execution_plan.get("can_execute_now")
                else "blocked",
                {
                    "contains_sql": bool(execution_plan.get("contains_sql")),
                    "contains_executable_code": bool(execution_plan.get("contains_executable_code")),
                    "can_execute_now": bool(execution_plan.get("can_execute_now")),
                },
                "all false",
                "P17 records a plan only; no SQL, runnable code, or execution permission",
            ),
            self._manual_evidence_check(
                "aggregate_only_no_record_bodies",
                "passed"
                if execution_plan.get("record_bodies_included") is False
                and execution_plan.get("affected_rows_body_included") is False
                else "blocked",
                {
                    "record_bodies_included": execution_plan.get("record_bodies_included"),
                    "affected_rows_body_included": execution_plan.get("affected_rows_body_included"),
                },
                "no record bodies",
                "cleanup execution plan may store aggregate operation counts only",
            ),
            self._manual_evidence_check(
                "learning_samples_unchanged",
                "passed"
                if execution_plan.get("learning_sample_count_before")
                == execution_plan.get("expected_learning_sample_count_after")
                else "blocked",
                {
                    "before": execution_plan.get("learning_sample_count_before"),
                    "expected_after": execution_plan.get("expected_learning_sample_count_after"),
                },
                "unchanged",
                "P17 plan cannot write or project writes to learning_samples",
            ),
            self._manual_evidence_check(
                "planning_metadata_present",
                "passed" if bool(planned_by) and plan_decision in allowed_decisions else "blocked",
                {"planned_by_present": bool(planned_by), "plan_decision": plan_decision},
                sorted(allowed_decisions),
                "operator planning metadata must be explicit and constrained",
            ),
            self._manual_evidence_check(
                "plan_decision_allows_preflight_only",
                "passed" if plan_decision == "prepared_for_controlled_cleanup_execution_preflight" else "blocked",
                plan_decision,
                "prepared_for_controlled_cleanup_execution_preflight",
                "needs_revision or rejected plans cannot advance to cleanup execution preflight",
            ),
            self._manual_evidence_check(
                "manual_backfill_separated",
                "warning" if int(execution_plan.get("manual_operation_count") or 0) > 0 else "passed",
                execution_plan.get("manual_operation_count"),
                0,
                "manual evidence and historical-outcome operations remain separated from automated cleanup",
            ),
            self._manual_evidence_check(
                "source_review_kept_execution_blocked",
                "passed"
                if review_decision.get("cleanup_execution_approved_now") is False
                and review_decision.get("cleanup_application_allowed_now") is False
                and review_decision.get("cleanup_executed_now") is False
                and review_decision.get("can_execute_cleanup_now") is False
                and review_decision.get("writes_learning_samples_now") is False
                and review_decision.get("training_started_now") is False
                else "blocked",
                {
                    "cleanup_execution_approved_now": review_decision.get("cleanup_execution_approved_now"),
                    "cleanup_application_allowed_now": review_decision.get("cleanup_application_allowed_now"),
                    "cleanup_executed_now": review_decision.get("cleanup_executed_now"),
                    "can_execute_cleanup_now": review_decision.get("can_execute_cleanup_now"),
                    "writes_learning_samples_now": review_decision.get("writes_learning_samples_now"),
                    "training_started_now": review_decision.get("training_started_now"),
                },
                "all false",
                "P16 review must not have executed cleanup or training",
            ),
            self._manual_evidence_check(
                "cleanup_and_training_remain_blocked",
                "passed",
                {
                    "cleanup_execution_approved_now": False,
                    "cleanup_application_allowed_now": False,
                    "cleanup_executed_now": False,
                    "can_execute_cleanup_now": False,
                    "writes_learning_samples_now": False,
                    "training_started_now": False,
                },
                "all false",
                "P17 creates a controlled plan only; cleanup execution and training stay blocked",
            ),
        ]

    def _empty_cleanup_execution_plan_preflight(self) -> dict[str, Any]:
        return {
            "package_id": None,
            "lock_key": None,
            "staging_record_count": 0,
            "expected_staging_record_count_after": 0,
            "learning_sample_count": 0,
            "expected_learning_sample_count_after": 0,
            "transaction_required": True,
            "rollback_required": True,
            "rollback_plan": [],
            "allowed_tables": ["dataset2_staging_records"],
            "forbidden_tables": ["learning_samples"],
            "automated_batches": [],
            "manual_backfill_batches": [],
            "contains_sql": False,
            "contains_executable_code": False,
            "can_execute_now": False,
            "record_bodies_included": False,
            "review_only": True,
            "simulation_only": True,
        }

    def _cleanup_execution_plan_preflight_snapshot(
        self,
        store: SQLiteStore,
        plan: dict[str, Any],
    ) -> dict[str, Any]:
        execution_plan = plan.get("execution_plan") or {}
        package_id = plan.get("package_id") or execution_plan.get("package_id")
        staging_count = self._staging_record_count(store, package_id)
        learning_count = self._learning_sample_count(store)
        lock_key = self._cleanup_execution_plan_lock_key(plan, staging_count)
        automated_batches = execution_plan.get("execution_batches") or []
        manual_batches = execution_plan.get("manual_backfill_batches") or []
        return {
            "package_id": package_id,
            "lock_key": lock_key,
            "staging_record_count": staging_count,
            "expected_staging_record_count_after": staging_count,
            "learning_sample_count": learning_count,
            "expected_learning_sample_count_after": learning_count,
            "automated_operation_count": execution_plan.get("automated_operation_count", 0),
            "manual_operation_count": execution_plan.get("manual_operation_count", 0),
            "automated_batch_count": len(automated_batches),
            "manual_backfill_batch_count": len(manual_batches),
            "transaction_required": True,
            "rollback_required": True,
            "rollback_plan": [
                "open_single_sqlite_transaction_in_future_execution_stage",
                "snapshot_affected_dataset2_staging_record_ids_before_update",
                "rollback_transaction_on_any_check_failure",
                "rerun_staging_quality_review_after_future_execution",
            ],
            "allowed_tables": ["dataset2_staging_records"],
            "forbidden_tables": ["learning_samples"],
            "allowed_operations": ["normalize_enum", "parse_stringified_list_items"],
            "automated_batches": [
                {
                    "batch_name": batch.get("batch_name"),
                    "operation": batch.get("operation"),
                    "operation_count": batch.get("operation_count", 0),
                    "mode": batch.get("mode"),
                    "requires_preflight": bool(batch.get("requires_preflight")),
                    "requires_transaction": bool(batch.get("requires_transaction")),
                    "record_bodies_included": False,
                }
                for batch in automated_batches
            ],
            "manual_backfill_batches": [
                {
                    "batch_name": batch.get("batch_name"),
                    "operation": batch.get("operation"),
                    "operation_count": batch.get("operation_count", 0),
                    "mode": batch.get("mode"),
                    "can_execute_automatically": bool(batch.get("can_execute_automatically")),
                    "record_bodies_included": False,
                }
                for batch in manual_batches
            ],
            "contains_sql": False,
            "contains_executable_code": False,
            "can_execute_now": False,
            "record_bodies_included": False,
            "affected_rows_body_included": False,
            "writes_staging_records_now": False,
            "writes_learning_samples_now": False,
            "review_only": True,
            "simulation_only": True,
        }

    def _cleanup_execution_plan_lock_key(self, plan: dict[str, Any], staging_count: int) -> str:
        seed = {
            "execution_plan_id": plan.get("id"),
            "dry_run_review_id": plan.get("dry_run_review_id"),
            "package_id": plan.get("package_id"),
            "evidence_package_hash": (plan.get("evidence_summary") or {}).get("evidence_package_hash"),
            "automated_operation_count": (plan.get("execution_plan") or {}).get("automated_operation_count"),
            "staging_count": staging_count,
        }
        digest = hashlib.sha256(json.dumps(seed, sort_keys=True, default=str).encode("utf-8")).hexdigest()
        return f"dataset2-cleanup-plan-preflight-{digest[:16]}"

    def _cleanup_execution_plan_preflight_checks(
        self,
        plan: dict[str, Any],
        preflight: dict[str, Any],
        requested_by: str,
        preflight_decision: str,
    ) -> list[dict[str, Any]]:
        summary = plan.get("summary") or {}
        decision = plan.get("decision") or {}
        execution_plan = plan.get("execution_plan") or {}
        allowed_decisions = {"prepared_for_controlled_cleanup_execution_dry_run", "needs_revision", "rejected"}
        blocked_check_count = int(summary.get("blocked_check_count") or 0)
        allowed_operations = set(preflight.get("allowed_operations") or [])
        automated_operations = {
            str(batch.get("operation") or "")
            for batch in (preflight.get("automated_batches") or [])
            if batch.get("operation")
        }
        return [
            self._manual_evidence_check(
                "execution_plan_available",
                "passed" if plan.get("id") else "blocked",
                plan.get("id"),
                "existing cleanup execution plan",
                "controlled cleanup preflight must reference an existing P17 plan event",
            ),
            self._manual_evidence_check(
                "execution_plan_ready_for_preflight",
                "passed"
                if plan.get("status") == "cleanup_execution_plan_ready_for_preflight"
                and decision.get("cleanup_execution_plan_ready_for_preflight") is True
                else "blocked",
                {
                    "status": plan.get("status"),
                    "cleanup_execution_plan_ready_for_preflight": decision.get(
                        "cleanup_execution_plan_ready_for_preflight"
                    ),
                },
                "cleanup_execution_plan_ready_for_preflight",
                "only a passed P17 execution plan can enter controlled cleanup preflight",
            ),
            self._manual_evidence_check(
                "source_plan_blocked_checks_clear",
                "passed" if blocked_check_count == 0 else "blocked",
                blocked_check_count,
                0,
                "P17 execution plan checks must have no blocked items",
            ),
            self._manual_evidence_check(
                "staging_count_matches_plan",
                "passed"
                if int(preflight.get("staging_record_count") or 0)
                == int(execution_plan.get("candidate_record_count") or 0)
                and int(preflight.get("staging_record_count") or 0) > 0
                else "blocked",
                {
                    "staging_record_count": preflight.get("staging_record_count"),
                    "planned_candidate_record_count": execution_plan.get("candidate_record_count"),
                },
                "matching nonzero counts",
                "future controlled cleanup must run against the same staged package count as the reviewed plan",
            ),
            self._manual_evidence_check(
                "automated_batches_scoped",
                "passed"
                if automated_operations
                and automated_operations.issubset(allowed_operations)
                and int(preflight.get("automated_operation_count") or 0) > 0
                else "blocked",
                {
                    "automated_operations": sorted(automated_operations),
                    "allowed_operations": sorted(allowed_operations),
                    "automated_operation_count": preflight.get("automated_operation_count"),
                },
                "allowed deterministic operations only",
                "P18 preflight only allows deterministic automated cleanup batches",
            ),
            self._manual_evidence_check(
                "manual_backfill_separated",
                "warning" if int(preflight.get("manual_operation_count") or 0) > 0 else "passed",
                preflight.get("manual_operation_count"),
                0,
                "manual evidence and historical-outcome work stays outside the automated cleanup preflight",
            ),
            self._manual_evidence_check(
                "transaction_and_rollback_required",
                "passed" if preflight.get("transaction_required") and preflight.get("rollback_required") else "blocked",
                {
                    "transaction_required": preflight.get("transaction_required"),
                    "rollback_required": preflight.get("rollback_required"),
                    "rollback_step_count": len(preflight.get("rollback_plan") or []),
                },
                "transaction and rollback required",
                "future cleanup execution must be transactional and rollbackable",
            ),
            self._manual_evidence_check(
                "table_scope_limited",
                "passed"
                if preflight.get("allowed_tables") == ["dataset2_staging_records"]
                and "learning_samples" in (preflight.get("forbidden_tables") or [])
                else "blocked",
                {
                    "allowed_tables": preflight.get("allowed_tables"),
                    "forbidden_tables": preflight.get("forbidden_tables"),
                },
                "dataset2_staging_records only; learning_samples forbidden",
                "future cleanup can only touch staging records, never training tables",
            ),
            self._manual_evidence_check(
                "preflight_contains_no_executable_payload",
                "passed"
                if not preflight.get("contains_sql")
                and not preflight.get("contains_executable_code")
                and not preflight.get("can_execute_now")
                else "blocked",
                {
                    "contains_sql": bool(preflight.get("contains_sql")),
                    "contains_executable_code": bool(preflight.get("contains_executable_code")),
                    "can_execute_now": bool(preflight.get("can_execute_now")),
                },
                "all false",
                "P18 preflight cannot contain executable SQL, runnable code, or execution permission",
            ),
            self._manual_evidence_check(
                "aggregate_only_no_record_bodies",
                "passed"
                if preflight.get("record_bodies_included") is False
                and preflight.get("affected_rows_body_included") is False
                else "blocked",
                {
                    "record_bodies_included": preflight.get("record_bodies_included"),
                    "affected_rows_body_included": preflight.get("affected_rows_body_included"),
                },
                "no record bodies",
                "preflight may store counts and batch metadata only",
            ),
            self._manual_evidence_check(
                "learning_samples_unchanged",
                "passed"
                if preflight.get("learning_sample_count")
                == preflight.get("expected_learning_sample_count_after")
                else "blocked",
                {
                    "before": preflight.get("learning_sample_count"),
                    "expected_after": preflight.get("expected_learning_sample_count_after"),
                },
                "unchanged",
                "P18 preflight cannot write or project writes to learning_samples",
            ),
            self._manual_evidence_check(
                "preflight_metadata_present",
                "passed" if bool(requested_by) and preflight_decision in allowed_decisions else "blocked",
                {"requested_by_present": bool(requested_by), "preflight_decision": preflight_decision},
                sorted(allowed_decisions),
                "operator preflight metadata must be explicit and constrained",
            ),
            self._manual_evidence_check(
                "preflight_decision_allows_dry_run_only",
                "passed" if preflight_decision == "prepared_for_controlled_cleanup_execution_dry_run" else "blocked",
                preflight_decision,
                "prepared_for_controlled_cleanup_execution_dry_run",
                "needs_revision or rejected preflights cannot advance to controlled cleanup dry-run",
            ),
            self._manual_evidence_check(
                "source_plan_kept_execution_blocked",
                "passed"
                if decision.get("cleanup_execution_approved_now") is False
                and decision.get("cleanup_application_allowed_now") is False
                and decision.get("cleanup_executed_now") is False
                and decision.get("can_execute_cleanup_now") is False
                and decision.get("writes_learning_samples_now") is False
                and decision.get("training_started_now") is False
                else "blocked",
                {
                    "cleanup_execution_approved_now": decision.get("cleanup_execution_approved_now"),
                    "cleanup_application_allowed_now": decision.get("cleanup_application_allowed_now"),
                    "cleanup_executed_now": decision.get("cleanup_executed_now"),
                    "can_execute_cleanup_now": decision.get("can_execute_cleanup_now"),
                    "writes_learning_samples_now": decision.get("writes_learning_samples_now"),
                    "training_started_now": decision.get("training_started_now"),
                },
                "all false",
                "P17 plan must not have executed cleanup or training",
            ),
            self._manual_evidence_check(
                "cleanup_and_training_remain_blocked",
                "passed",
                {
                    "cleanup_execution_approved_now": False,
                    "cleanup_application_allowed_now": False,
                    "cleanup_executed_now": False,
                    "can_execute_cleanup_now": False,
                    "writes_learning_samples_now": False,
                    "training_started_now": False,
                },
                "all false",
                "P18 preflight only prepares a later dry-run; cleanup execution and training stay blocked",
            ),
        ]

    def _empty_controlled_cleanup_dry_run_simulation(self) -> dict[str, Any]:
        return {
            "package_id": None,
            "lock_key": None,
            "staging_record_count_before": 0,
            "expected_staging_record_count_after": 0,
            "learning_sample_count_before": 0,
            "expected_learning_sample_count_after": 0,
            "automated_operation_count": 0,
            "manual_operation_count": 0,
            "automated_batches": [],
            "manual_backfill_batches": [],
            "simulated_quality_flag_reduction_count": 0,
            "simulated_manual_flag_remaining_count": 0,
            "simulated_mutation_count": 0,
            "staging_count_still_matches": False,
            "contains_sql": False,
            "contains_executable_code": False,
            "can_execute_now": False,
            "record_bodies_included": False,
            "affected_rows_body_included": False,
            "writes_staging_records_now": False,
            "writes_learning_samples_now": False,
            "mutates_staging_records_now": False,
            "review_only": True,
            "simulation_only": True,
        }

    def _controlled_cleanup_dry_run_simulation(
        self,
        store: SQLiteStore,
        plan_preflight: dict[str, Any],
    ) -> dict[str, Any]:
        preflight = plan_preflight.get("preflight") or {}
        package_id = preflight.get("package_id") or plan_preflight.get("package_id")
        current_staging_count = self._staging_record_count(store, package_id)
        current_learning_count = self._learning_sample_count(store)
        preflight_staging_count = int(preflight.get("staging_record_count") or 0)
        automated_count = int(preflight.get("automated_operation_count") or 0)
        manual_count = int(preflight.get("manual_operation_count") or 0)
        automated_batches = preflight.get("automated_batches") or []
        manual_batches = preflight.get("manual_backfill_batches") or []
        return {
            "package_id": package_id,
            "lock_key": preflight.get("lock_key"),
            "source_plan_preflight_id": plan_preflight.get("id"),
            "source_execution_plan_id": plan_preflight.get("execution_plan_id"),
            "staging_record_count_before": current_staging_count,
            "expected_staging_record_count_after": current_staging_count,
            "preflight_staging_record_count": preflight_staging_count,
            "staging_count_still_matches": current_staging_count == preflight_staging_count and current_staging_count > 0,
            "learning_sample_count_before": current_learning_count,
            "expected_learning_sample_count_after": current_learning_count,
            "automated_operation_count": automated_count,
            "manual_operation_count": manual_count,
            "automated_batch_count": len(automated_batches),
            "manual_backfill_batch_count": len(manual_batches),
            "automated_batches": [
                {
                    "batch_name": batch.get("batch_name"),
                    "operation": batch.get("operation"),
                    "operation_count": batch.get("operation_count", 0),
                    "mode": batch.get("mode"),
                    "simulated_effect": "future_quality_flag_or_field_normalization",
                    "record_bodies_included": False,
                }
                for batch in automated_batches
            ],
            "manual_backfill_batches": [
                {
                    "batch_name": batch.get("batch_name"),
                    "operation": batch.get("operation"),
                    "operation_count": batch.get("operation_count", 0),
                    "mode": batch.get("mode"),
                    "simulated_effect": "manual_evidence_required_no_automatic_mutation",
                    "record_bodies_included": False,
                }
                for batch in manual_batches
            ],
            "simulated_quality_flag_reduction_count": automated_count,
            "simulated_manual_flag_remaining_count": manual_count,
            "simulated_mutation_count": automated_count,
            "transaction_required": bool(preflight.get("transaction_required")),
            "rollback_required": bool(preflight.get("rollback_required")),
            "allowed_tables": preflight.get("allowed_tables") or ["dataset2_staging_records"],
            "forbidden_tables": preflight.get("forbidden_tables") or ["learning_samples"],
            "contains_sql": False,
            "contains_executable_code": False,
            "can_execute_now": False,
            "record_bodies_included": False,
            "affected_rows_body_included": False,
            "writes_staging_records_now": False,
            "writes_learning_samples_now": False,
            "mutates_staging_records_now": False,
            "review_only": True,
            "simulation_only": True,
        }

    def _controlled_cleanup_dry_run_checks(
        self,
        plan_preflight: dict[str, Any],
        simulation: dict[str, Any],
        simulated_by: str,
        dry_run_decision: str,
    ) -> list[dict[str, Any]]:
        summary = plan_preflight.get("summary") or {}
        decision = plan_preflight.get("decision") or {}
        blocked_check_count = int(summary.get("blocked_check_count") or 0)
        allowed_decisions = {"simulated_for_controlled_cleanup_review", "needs_revision", "rejected"}
        return [
            self._manual_evidence_check(
                "plan_preflight_available",
                "passed" if plan_preflight.get("id") else "blocked",
                plan_preflight.get("id"),
                "existing cleanup execution plan preflight",
                "controlled cleanup dry-run must reference an existing P18 preflight event",
            ),
            self._manual_evidence_check(
                "plan_preflight_ready_for_dry_run",
                "passed"
                if plan_preflight.get("status") == "cleanup_execution_plan_preflight_ready_for_dry_run"
                and decision.get("cleanup_execution_plan_preflight_ready_for_dry_run") is True
                else "blocked",
                {
                    "status": plan_preflight.get("status"),
                    "cleanup_execution_plan_preflight_ready_for_dry_run": decision.get(
                        "cleanup_execution_plan_preflight_ready_for_dry_run"
                    ),
                },
                "cleanup_execution_plan_preflight_ready_for_dry_run",
                "only a passed P18 preflight can enter controlled cleanup dry-run",
            ),
            self._manual_evidence_check(
                "source_preflight_blocked_checks_clear",
                "passed" if blocked_check_count == 0 else "blocked",
                blocked_check_count,
                0,
                "P18 preflight checks must have no blocked items",
            ),
            self._manual_evidence_check(
                "lock_key_present",
                "passed" if bool(simulation.get("lock_key")) else "blocked",
                simulation.get("lock_key"),
                "deterministic preflight lock key",
                "controlled cleanup dry-run must carry the P18 lock key for later review",
            ),
            self._manual_evidence_check(
                "staging_count_still_matches",
                "passed" if simulation.get("staging_count_still_matches") is True else "blocked",
                {
                    "current": simulation.get("staging_record_count_before"),
                    "preflight": simulation.get("preflight_staging_record_count"),
                },
                "matching nonzero counts",
                "controlled dry-run must simulate the same package count as the P18 preflight",
            ),
            self._manual_evidence_check(
                "automated_dry_run_scope_present",
                "passed"
                if int(simulation.get("automated_operation_count") or 0) > 0
                and int(simulation.get("automated_batch_count") or 0) > 0
                else "blocked",
                {
                    "automated_operation_count": simulation.get("automated_operation_count"),
                    "automated_batch_count": simulation.get("automated_batch_count"),
                },
                ">0 automated operations with scoped batches",
                "controlled dry-run must be limited to the reviewed automated cleanup batches",
            ),
            self._manual_evidence_check(
                "manual_backfill_separated",
                "warning" if int(simulation.get("manual_operation_count") or 0) > 0 else "passed",
                simulation.get("manual_operation_count"),
                0,
                "manual evidence and historical-outcome items remain separate from automated cleanup simulation",
            ),
            self._manual_evidence_check(
                "simulation_contains_no_executable_payload",
                "passed"
                if not simulation.get("contains_sql")
                and not simulation.get("contains_executable_code")
                and not simulation.get("can_execute_now")
                else "blocked",
                {
                    "contains_sql": bool(simulation.get("contains_sql")),
                    "contains_executable_code": bool(simulation.get("contains_executable_code")),
                    "can_execute_now": bool(simulation.get("can_execute_now")),
                },
                "all false",
                "P19 controlled dry-run cannot contain executable SQL, runnable code, or execution permission",
            ),
            self._manual_evidence_check(
                "aggregate_only_no_record_bodies",
                "passed"
                if simulation.get("record_bodies_included") is False
                and simulation.get("affected_rows_body_included") is False
                else "blocked",
                {
                    "record_bodies_included": simulation.get("record_bodies_included"),
                    "affected_rows_body_included": simulation.get("affected_rows_body_included"),
                },
                "no record bodies",
                "controlled dry-run stores aggregate counts only",
            ),
            self._manual_evidence_check(
                "learning_samples_unchanged",
                "passed"
                if simulation.get("learning_sample_count_before") == simulation.get("expected_learning_sample_count_after")
                else "blocked",
                {
                    "before": simulation.get("learning_sample_count_before"),
                    "expected_after": simulation.get("expected_learning_sample_count_after"),
                },
                "unchanged",
                "P19 controlled dry-run cannot write or project writes to learning_samples",
            ),
            self._manual_evidence_check(
                "dry_run_metadata_present",
                "passed" if bool(simulated_by) and dry_run_decision in allowed_decisions else "blocked",
                {"simulated_by_present": bool(simulated_by), "dry_run_decision": dry_run_decision},
                sorted(allowed_decisions),
                "operator dry-run metadata must be explicit and constrained",
            ),
            self._manual_evidence_check(
                "dry_run_decision_allows_review_only",
                "passed" if dry_run_decision == "simulated_for_controlled_cleanup_review" else "blocked",
                dry_run_decision,
                "simulated_for_controlled_cleanup_review",
                "needs_revision or rejected dry-runs cannot advance to later review",
            ),
            self._manual_evidence_check(
                "source_preflight_kept_execution_blocked",
                "passed"
                if decision.get("cleanup_execution_approved_now") is False
                and decision.get("cleanup_application_allowed_now") is False
                and decision.get("cleanup_executed_now") is False
                and decision.get("can_execute_cleanup_now") is False
                and decision.get("writes_learning_samples_now") is False
                and decision.get("training_started_now") is False
                else "blocked",
                {
                    "cleanup_execution_approved_now": decision.get("cleanup_execution_approved_now"),
                    "cleanup_application_allowed_now": decision.get("cleanup_application_allowed_now"),
                    "cleanup_executed_now": decision.get("cleanup_executed_now"),
                    "can_execute_cleanup_now": decision.get("can_execute_cleanup_now"),
                    "writes_learning_samples_now": decision.get("writes_learning_samples_now"),
                    "training_started_now": decision.get("training_started_now"),
                },
                "all false",
                "P18 preflight must not have executed cleanup or training",
            ),
            self._manual_evidence_check(
                "cleanup_and_training_remain_blocked",
                "passed",
                {
                    "cleanup_execution_approved_now": False,
                    "cleanup_application_allowed_now": False,
                    "cleanup_executed_now": False,
                    "can_execute_cleanup_now": False,
                    "writes_learning_samples_now": False,
                    "training_started_now": False,
                },
                "all false",
                "P19 controlled dry-run remains simulation-only; cleanup execution and training stay blocked",
            ),
        ]

    def _controlled_cleanup_dry_run_review_checks(
        self,
        controlled_dry_run: dict[str, Any],
        reviewed_by: str,
        review_decision: str,
    ) -> list[dict[str, Any]]:
        summary = controlled_dry_run.get("summary") or {}
        decision = controlled_dry_run.get("decision") or {}
        simulation = controlled_dry_run.get("simulation") or {}
        blocked_check_count = int(summary.get("blocked_check_count") or 0)
        allowed_decisions = {"approved_for_controlled_cleanup_execution_review", "needs_revision", "rejected"}
        return [
            self._manual_evidence_check(
                "controlled_dry_run_available",
                "passed" if controlled_dry_run.get("id") else "blocked",
                controlled_dry_run.get("id"),
                "existing controlled cleanup dry-run",
                "controlled cleanup dry-run review must reference an existing P19 event",
            ),
            self._manual_evidence_check(
                "controlled_dry_run_ready_for_review",
                "passed"
                if controlled_dry_run.get("status") == "controlled_cleanup_dry_run_ready_for_review"
                and decision.get("controlled_cleanup_dry_run_ready_for_review") is True
                else "blocked",
                {
                    "status": controlled_dry_run.get("status"),
                    "controlled_cleanup_dry_run_ready_for_review": decision.get(
                        "controlled_cleanup_dry_run_ready_for_review"
                    ),
                },
                "controlled_cleanup_dry_run_ready_for_review",
                "only a passed P19 controlled dry-run can enter manual review",
            ),
            self._manual_evidence_check(
                "source_dry_run_blocked_checks_clear",
                "passed" if blocked_check_count == 0 else "blocked",
                blocked_check_count,
                0,
                "P19 controlled dry-run checks must have no blocked items",
            ),
            self._manual_evidence_check(
                "aggregate_simulation_present",
                "passed" if int(simulation.get("simulated_mutation_count") or 0) > 0 else "blocked",
                simulation.get("simulated_mutation_count"),
                ">0",
                "manual review needs aggregate simulated cleanup impact from P19",
            ),
            self._manual_evidence_check(
                "simulation_contains_no_executable_payload",
                "passed"
                if not simulation.get("contains_sql")
                and not simulation.get("contains_executable_code")
                and not simulation.get("can_execute_now")
                else "blocked",
                {
                    "contains_sql": bool(simulation.get("contains_sql")),
                    "contains_executable_code": bool(simulation.get("contains_executable_code")),
                    "can_execute_now": bool(simulation.get("can_execute_now")),
                },
                "all false",
                "P20 review cannot accept executable SQL, runnable code, or execution permission",
            ),
            self._manual_evidence_check(
                "aggregate_only_no_record_bodies",
                "passed"
                if simulation.get("record_bodies_included") is False
                and simulation.get("affected_rows_body_included") is False
                and summary.get("record_bodies_included") is False
                else "blocked",
                {
                    "simulation_record_bodies_included": simulation.get("record_bodies_included"),
                    "affected_rows_body_included": simulation.get("affected_rows_body_included"),
                    "summary_record_bodies_included": summary.get("record_bodies_included"),
                },
                "no record bodies",
                "controlled dry-run review may store aggregate counts and hashes only",
            ),
            self._manual_evidence_check(
                "learning_samples_unchanged",
                "passed"
                if simulation.get("learning_sample_count_before") == simulation.get("expected_learning_sample_count_after")
                else "blocked",
                {
                    "before": simulation.get("learning_sample_count_before"),
                    "expected_after": simulation.get("expected_learning_sample_count_after"),
                },
                "unchanged",
                "P20 review cannot write or project writes to learning_samples",
            ),
            self._manual_evidence_check(
                "review_metadata_present",
                "passed" if bool(reviewed_by) and review_decision in allowed_decisions else "blocked",
                {"reviewed_by_present": bool(reviewed_by), "review_decision": review_decision},
                sorted(allowed_decisions),
                "operator review metadata must be explicit and constrained",
            ),
            self._manual_evidence_check(
                "review_decision_allows_future_execution_review_only",
                "passed" if review_decision == "approved_for_controlled_cleanup_execution_review" else "blocked",
                review_decision,
                "approved_for_controlled_cleanup_execution_review",
                "needs_revision or rejected reviews cannot advance to a later execution approval gate",
            ),
            self._manual_evidence_check(
                "source_dry_run_kept_execution_blocked",
                "passed"
                if decision.get("cleanup_execution_approved_now") is False
                and decision.get("cleanup_application_allowed_now") is False
                and decision.get("cleanup_executed_now") is False
                and decision.get("can_execute_cleanup_now") is False
                and decision.get("writes_learning_samples_now") is False
                and decision.get("training_started_now") is False
                else "blocked",
                {
                    "cleanup_execution_approved_now": decision.get("cleanup_execution_approved_now"),
                    "cleanup_application_allowed_now": decision.get("cleanup_application_allowed_now"),
                    "cleanup_executed_now": decision.get("cleanup_executed_now"),
                    "can_execute_cleanup_now": decision.get("can_execute_cleanup_now"),
                    "writes_learning_samples_now": decision.get("writes_learning_samples_now"),
                    "training_started_now": decision.get("training_started_now"),
                },
                "all false",
                "P19 controlled dry-run must not have executed cleanup or training",
            ),
            self._manual_evidence_check(
                "cleanup_and_training_remain_blocked",
                "passed",
                {
                    "cleanup_execution_approved_now": False,
                    "cleanup_application_allowed_now": False,
                    "cleanup_executed_now": False,
                    "can_execute_cleanup_now": False,
                    "writes_learning_samples_now": False,
                    "training_started_now": False,
                },
                "all false",
                "P20 records review evidence only; cleanup execution and training stay blocked",
            ),
        ]

    def _empty_controlled_cleanup_approval_scope(self) -> dict[str, Any]:
        return {
            "package_id": None,
            "lock_key": None,
            "automated_operation_count": 0,
            "manual_operation_count": 0,
            "simulated_mutation_count": 0,
            "approval_scope": "controlled_cleanup_preflight_only",
            "requires_preflight": True,
            "requires_transaction": True,
            "requires_rollback": True,
            "contains_sql": False,
            "contains_executable_code": False,
            "can_execute_now": False,
            "record_bodies_included": False,
            "affected_rows_body_included": False,
            "writes_staging_records_now": False,
            "writes_learning_samples_now": False,
            "mutates_staging_records_now": False,
            "review_only": True,
            "simulation_only": True,
        }

    def _controlled_cleanup_approval_scope(self, review: dict[str, Any]) -> dict[str, Any]:
        simulation = review.get("simulation_summary") or {}
        return {
            "package_id": simulation.get("package_id") or review.get("package_id"),
            "lock_key": simulation.get("lock_key"),
            "controlled_review_id": review.get("id"),
            "controlled_dry_run_id": review.get("controlled_dry_run_id"),
            "plan_preflight_id": review.get("plan_preflight_id"),
            "execution_plan_id": review.get("execution_plan_id"),
            "automated_operation_count": simulation.get("automated_operation_count", 0),
            "manual_operation_count": simulation.get("manual_operation_count", 0),
            "simulated_mutation_count": simulation.get("simulated_mutation_count", 0),
            "approval_scope": "controlled_cleanup_preflight_only",
            "allowed_next_stage": "controlled_cleanup_execution_preflight",
            "requires_preflight": True,
            "requires_transaction": True,
            "requires_rollback": True,
            "contains_sql": False,
            "contains_executable_code": False,
            "can_execute_now": False,
            "record_bodies_included": False,
            "affected_rows_body_included": False,
            "writes_staging_records_now": False,
            "writes_learning_samples_now": False,
            "mutates_staging_records_now": False,
            "review_only": True,
            "simulation_only": True,
        }

    def _controlled_cleanup_execution_approval_checks(
        self,
        review: dict[str, Any],
        approval_scope: dict[str, Any],
        approved_by: str,
        approval_decision: str,
    ) -> list[dict[str, Any]]:
        summary = review.get("summary") or {}
        decision = review.get("decision") or {}
        simulation = review.get("simulation_summary") or {}
        blocked_check_count = int(summary.get("blocked_check_count") or 0)
        allowed_decisions = {"approved_for_controlled_cleanup_execution_preflight", "needs_revision", "rejected"}
        return [
            self._manual_evidence_check(
                "controlled_review_available",
                "passed" if review.get("id") else "blocked",
                review.get("id"),
                "existing controlled dry-run review",
                "controlled cleanup execution approval must reference an existing P20 review event",
            ),
            self._manual_evidence_check(
                "controlled_review_accepted",
                "passed"
                if review.get("status") == "controlled_cleanup_dry_run_review_accepted"
                and decision.get("controlled_cleanup_dry_run_review_accepted") is True
                else "blocked",
                {
                    "status": review.get("status"),
                    "controlled_cleanup_dry_run_review_accepted": decision.get(
                        "controlled_cleanup_dry_run_review_accepted"
                    ),
                },
                "controlled_cleanup_dry_run_review_accepted",
                "only an accepted P20 review can enter controlled cleanup execution approval",
            ),
            self._manual_evidence_check(
                "source_review_blocked_checks_clear",
                "passed" if blocked_check_count == 0 else "blocked",
                blocked_check_count,
                0,
                "P20 review checks must have no blocked items",
            ),
            self._manual_evidence_check(
                "approval_scope_is_preflight_only",
                "passed" if approval_scope.get("approval_scope") == "controlled_cleanup_preflight_only" else "blocked",
                approval_scope.get("approval_scope"),
                "controlled_cleanup_preflight_only",
                "P21 approval can only authorize a later preflight, not cleanup execution",
            ),
            self._manual_evidence_check(
                "aggregate_simulation_present",
                "passed" if int(approval_scope.get("simulated_mutation_count") or 0) > 0 else "blocked",
                approval_scope.get("simulated_mutation_count"),
                ">0",
                "approval metadata needs aggregate simulated cleanup impact from P20",
            ),
            self._manual_evidence_check(
                "lock_key_present",
                "passed" if bool(approval_scope.get("lock_key")) else "blocked",
                approval_scope.get("lock_key"),
                "P18/P19 lock key",
                "approval must preserve lock-key traceability before any future preflight",
            ),
            self._manual_evidence_check(
                "scope_contains_no_executable_payload",
                "passed"
                if not approval_scope.get("contains_sql")
                and not approval_scope.get("contains_executable_code")
                and not approval_scope.get("can_execute_now")
                else "blocked",
                {
                    "contains_sql": bool(approval_scope.get("contains_sql")),
                    "contains_executable_code": bool(approval_scope.get("contains_executable_code")),
                    "can_execute_now": bool(approval_scope.get("can_execute_now")),
                },
                "all false",
                "P21 approval metadata cannot contain executable SQL, runnable code, or execution permission",
            ),
            self._manual_evidence_check(
                "aggregate_only_no_record_bodies",
                "passed"
                if approval_scope.get("record_bodies_included") is False
                and approval_scope.get("affected_rows_body_included") is False
                else "blocked",
                {
                    "record_bodies_included": approval_scope.get("record_bodies_included"),
                    "affected_rows_body_included": approval_scope.get("affected_rows_body_included"),
                },
                "no record bodies",
                "controlled approval may store aggregate counts only",
            ),
            self._manual_evidence_check(
                "learning_samples_unchanged",
                "passed"
                if simulation.get("learning_sample_count_before") == simulation.get("expected_learning_sample_count_after")
                else "blocked",
                {
                    "before": simulation.get("learning_sample_count_before"),
                    "expected_after": simulation.get("expected_learning_sample_count_after"),
                },
                "unchanged",
                "P21 approval cannot write or project writes to learning_samples",
            ),
            self._manual_evidence_check(
                "approval_metadata_present",
                "passed" if bool(approved_by) and approval_decision in allowed_decisions else "blocked",
                {"approved_by_present": bool(approved_by), "approval_decision": approval_decision},
                sorted(allowed_decisions),
                "operator approval metadata must be explicit and constrained",
            ),
            self._manual_evidence_check(
                "approval_decision_allows_future_preflight_only",
                "passed" if approval_decision == "approved_for_controlled_cleanup_execution_preflight" else "blocked",
                approval_decision,
                "approved_for_controlled_cleanup_execution_preflight",
                "needs_revision or rejected approvals cannot advance to later preflight",
            ),
            self._manual_evidence_check(
                "source_review_kept_execution_blocked",
                "passed"
                if decision.get("cleanup_execution_approved_now") is False
                and decision.get("cleanup_application_allowed_now") is False
                and decision.get("cleanup_executed_now") is False
                and decision.get("can_execute_cleanup_now") is False
                and decision.get("writes_learning_samples_now") is False
                and decision.get("training_started_now") is False
                else "blocked",
                {
                    "cleanup_execution_approved_now": decision.get("cleanup_execution_approved_now"),
                    "cleanup_application_allowed_now": decision.get("cleanup_application_allowed_now"),
                    "cleanup_executed_now": decision.get("cleanup_executed_now"),
                    "can_execute_cleanup_now": decision.get("can_execute_cleanup_now"),
                    "writes_learning_samples_now": decision.get("writes_learning_samples_now"),
                    "training_started_now": decision.get("training_started_now"),
                },
                "all false",
                "P20 review must not have executed cleanup or training",
            ),
            self._manual_evidence_check(
                "cleanup_and_training_remain_blocked",
                "passed",
                {
                    "cleanup_execution_approved_now": False,
                    "cleanup_application_allowed_now": False,
                    "cleanup_executed_now": False,
                    "can_execute_cleanup_now": False,
                    "writes_learning_samples_now": False,
                    "training_started_now": False,
                },
                "all false",
                "P21 records approval metadata only; cleanup execution and training stay blocked",
            ),
        ]

    def _forbidden_evidence_paths(self, value: Any, prefix: str = "") -> list[str]:
        forbidden_keys = {
            "records",
            "rows",
            "source_records",
            "normalized_records",
            "raw_records",
            "record_bodies",
            "normalized_json",
            "payload_json",
            "all_training_patterns",
        }
        return self._matching_evidence_paths(value, forbidden_keys, prefix)

    def _forbidden_evidence_action_paths(self, value: Any, prefix: str = "") -> list[str]:
        forbidden_keys = {
            "sql",
            "execute_sql",
            "shell",
            "command",
            "apply_patch",
            "patch",
            "write_learning_samples",
            "learning_samples",
            "start_training",
            "export_file",
            "download",
            "mutate_staging_records",
        }
        return self._matching_evidence_paths(value, forbidden_keys, prefix)

    def _matching_evidence_paths(self, value: Any, keys: set[str], prefix: str = "") -> list[str]:
        matches: list[str] = []
        if isinstance(value, dict):
            for key, item in value.items():
                key_text = str(key)
                path = f"{prefix}.{key_text}" if prefix else key_text
                if key_text.lower() in keys:
                    matches.append(path)
                matches.extend(self._matching_evidence_paths(item, keys, path))
        elif isinstance(value, list):
            for index, item in enumerate(value):
                path = f"{prefix}[{index}]" if prefix else f"[{index}]"
                matches.extend(self._matching_evidence_paths(item, keys, path))
        return matches

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
