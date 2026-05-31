from __future__ import annotations

import ast
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from app.config import settings


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

    stage = "V5.6-P1"

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

    def _safety_summary(self) -> dict[str, bool]:
        return {
            "review_only": True,
            "simulation_only": True,
            "training_started_now": False,
            "writes_database_now": False,
            "writes_file": False,
            "writes_source_dataset": False,
            "normalized_records_persisted": False,
            "allow_live_order": False,
            "requires_backtest_before_training": True,
            "connects_broker": False,
            "places_real_trade": False,
            "screen_click_trading": False,
            "live_trading_enabled": settings.enable_live_trading,
        }
