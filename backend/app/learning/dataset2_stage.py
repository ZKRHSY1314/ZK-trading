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
            "rule_family_performance_memory": profile["rule_family_performance_memory"],
            "split": profile["split"],
            "training_allowed": profile["training_allowed"],
            "blocked_reasons": profile["blocked_reasons"],
            "latest_run": latest_run,
            "dry_run_available": True,
            "training_mode": "in_memory_grouped_label_baseline",
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
            "rule_family_performance_memory": profile["rule_family_performance_memory"],
            "split": profile["split"],
            "training_mode": "in_memory_grouped_label_baseline",
            "training_executed": False,
            "model_artifact_written": False,
            "writes_learning_samples": False,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

        if profile["training_allowed"]:
            train_samples = profile["train_samples"]
            validation_samples = profile["validation_samples"]
            model = self._grouped_label_model(train_samples)
            metrics = self._evaluate_grouped_label_model(model, validation_samples)
            model_summary = {key: value for key, value in model.items() if key != "rules"}
            result.update(
                {
                    "status": "completed",
                    "training_executed": True,
                    "model": model_summary,
                    "metrics": {
                        "train_count": len(train_samples),
                        "validation_count": len(validation_samples),
                        **metrics,
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
                   stock_code, signal_date, status, normalized_json, quality_flags_json, created_at
            FROM dataset2_staging_records
            ORDER BY id DESC
            LIMIT ?
            """,
            (remaining,),
        )
        for row in staged:
            normalized = _json_loads(row.get("normalized_json"), {})
            samples.append(
                {
                    "source": "dataset2_staging_records",
                    "source_id": row["id"],
                    "symbol": row.get("stock_code"),
                    "pattern_id": row.get("pattern_id"),
                    "pattern_name": normalized.get("pattern_name"),
                    "category": normalized.get("category"),
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
                        "pattern_id": item.get("pattern_id"),
                        "pattern_name": item.get("pattern_name"),
                        "category": item.get("category"),
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
        rule_family_memory = self._rule_family_performance_memory(samples)

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
            "rule_family_performance_memory": rule_family_memory,
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

    def _rule_family_performance_memory(self, samples: list[dict[str, Any]]) -> dict[str, Any]:
        staging_groups = self._staging_rule_family_groups(samples)
        backtest_groups = self._offhour_backtest_rule_family_groups(limit=12)
        execution_groups = self._sim_cockpit_execution_groups(samples)
        backtest_trade_count = sum(int(group.get("trade_count") or 0) for group in backtest_groups)
        positive_groups = [
            group
            for group in backtest_groups
            if int(group.get("trade_count") or 0) > 0 and float(group.get("average_return_pct") or 0) > 0
        ]
        return {
            "schema_version": "dataset2_rule_family_performance_memory.v1",
            "status": "ready" if staging_groups or backtest_groups or execution_groups else "empty",
            "summary": {
                "staging_group_count": len(staging_groups),
                "backtest_group_count": len(backtest_groups),
                "backtest_trade_count": backtest_trade_count,
                "positive_backtest_group_count": len(positive_groups),
                "execution_group_count": len(execution_groups),
                "source": "dataset2_staging_records + offhour_research_runs + sim_cockpit_actions/readbacks",
            },
            "top_staging_groups": staging_groups[:10],
            "top_backtest_groups": backtest_groups[:10],
            "top_execution_groups": execution_groups[:10],
            "interpretation": [
                "Backtest groups summarize review-only Dataset2 signal trades; they are not production strategy rules.",
                "Execution groups summarize simulated action/readback quality and cannot grant order permission.",
                "Use this memory to prioritize further dry-run and research review, not to bypass portfolio or sim-cockpit gates.",
            ],
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _staging_rule_family_groups(self, samples: list[dict[str, Any]]) -> list[dict[str, Any]]:
        groups: dict[str, dict[str, Any]] = {}
        for sample in samples:
            if sample.get("source") != "dataset2_staging_records":
                continue
            key = self._rule_family_key(sample)
            group = groups.setdefault(
                key,
                {
                    "key": key,
                    "pattern_id": sample.get("pattern_id"),
                    "pattern_name": sample.get("pattern_name"),
                    "category": sample.get("category"),
                    "action_label": sample.get("action"),
                    "risk_level": sample.get("risk_level"),
                    "sample_count": 0,
                    "label_counts": {},
                    "status_counts": {},
                },
            )
            group["sample_count"] += 1
            label = str(sample.get("training_label") or sample.get("action") or "unknown")
            status = str(sample.get("status") or "unknown")
            group["label_counts"][label] = group["label_counts"].get(label, 0) + 1
            group["status_counts"][status] = group["status_counts"].get(status, 0) + 1
        return sorted(
            groups.values(),
            key=lambda item: (-int(item.get("sample_count") or 0), str(item.get("key") or "")),
        )

    def _offhour_backtest_rule_family_groups(self, limit: int = 12) -> list[dict[str, Any]]:
        rows = self.store.fetch_all(
            """
            SELECT id, backtest_json
            FROM offhour_research_runs
            WHERE backtest_json LIKE '%dataset2_signal_backtest%'
            ORDER BY id DESC
            LIMIT ?
            """,
            (max(1, min(int(limit or 12), 50)),),
        )
        groups: dict[str, dict[str, Any]] = {}
        for row in rows:
            backtest = _json_loads(row.get("backtest_json"), {})
            signal_backtest = backtest.get("dataset2_signal_backtest") or {}
            trades = signal_backtest.get("trades") or []
            if not isinstance(trades, list):
                continue
            for trade in trades:
                if not isinstance(trade, dict):
                    continue
                if trade.get("review_only") is False or trade.get("simulation_only") is False:
                    continue
                key = self._rule_family_key(
                    {
                        "pattern_id": trade.get("pattern_id"),
                        "pattern_name": trade.get("pattern_name"),
                        "category": trade.get("category"),
                        "action": trade.get("action_label"),
                        "risk_level": trade.get("risk_level"),
                    }
                )
                group = groups.setdefault(
                    key,
                    {
                        "key": key,
                        "pattern_id": trade.get("pattern_id"),
                        "pattern_name": trade.get("pattern_name"),
                        "category": trade.get("category"),
                        "action_label": trade.get("action_label"),
                        "risk_level": trade.get("risk_level"),
                        "trade_count": 0,
                        "win_count": 0,
                        "loss_count": 0,
                        "total_return_pct": 0.0,
                        "best_return_pct": None,
                        "worst_return_pct": None,
                        "symbols": set(),
                        "source_run_ids": set(),
                    },
                )
                try:
                    return_pct = float(trade.get("realized_pnl_pct") or 0.0)
                except (TypeError, ValueError):
                    return_pct = 0.0
                group["trade_count"] += 1
                group["win_count"] += 1 if return_pct > 0 else 0
                group["loss_count"] += 1 if return_pct < 0 else 0
                group["total_return_pct"] += return_pct
                group["best_return_pct"] = return_pct if group["best_return_pct"] is None else max(group["best_return_pct"], return_pct)
                group["worst_return_pct"] = return_pct if group["worst_return_pct"] is None else min(group["worst_return_pct"], return_pct)
                if trade.get("symbol"):
                    group["symbols"].add(str(trade["symbol"]))
                group["source_run_ids"].add(int(row["id"]))
        normalized: list[dict[str, Any]] = []
        for group in groups.values():
            trade_count = int(group["trade_count"] or 0)
            average_return = group["total_return_pct"] / trade_count if trade_count else 0.0
            normalized.append(
                {
                    **{key: value for key, value in group.items() if key not in {"symbols", "source_run_ids"}},
                    "win_rate": round(group["win_count"] / trade_count, 6) if trade_count else 0.0,
                    "average_return_pct": round(average_return, 6),
                    "total_return_pct": round(float(group["total_return_pct"] or 0.0), 6),
                    "best_return_pct": round(float(group["best_return_pct"] or 0.0), 6),
                    "worst_return_pct": round(float(group["worst_return_pct"] or 0.0), 6),
                    "symbols": sorted(group["symbols"])[:12],
                    "source_run_ids": sorted(group["source_run_ids"], reverse=True)[:12],
                    "review_priority_score": round(average_return * min(trade_count, 20), 6),
                    "review_only": True,
                    "simulation_only": True,
                }
            )
        return sorted(
            normalized,
            key=lambda item: (
                -float(item.get("review_priority_score") or 0.0),
                -int(item.get("trade_count") or 0),
                str(item.get("key") or ""),
            ),
        )

    def _sim_cockpit_execution_groups(self, samples: list[dict[str, Any]]) -> list[dict[str, Any]]:
        groups: dict[str, dict[str, Any]] = {}
        for sample in samples:
            if sample.get("source") not in {"sim_cockpit_actions", "sim_cockpit_readbacks"}:
                continue
            risk_result = sample.get("risk_result") or {}
            source_key = risk_result.get("source") or sample.get("source")
            status_key = risk_result.get("status") or sample.get("status") or "unknown"
            action_key = sample.get("action") or "unknown"
            key = "|".join(str(part or "unknown") for part in [source_key, action_key, status_key])
            group = groups.setdefault(
                key,
                {
                    "key": key,
                    "source": source_key,
                    "action": action_key,
                    "status": status_key,
                    "sample_count": 0,
                    "dry_run_count": 0,
                    "executed_count": 0,
                    "blocked_count": 0,
                    "failed_count": 0,
                    "readback_count": 0,
                    "blocked_reason_counts": {},
                },
            )
            group["sample_count"] += 1
            status = str(sample.get("status") or "").lower()
            if sample.get("source") == "sim_cockpit_readbacks":
                group["readback_count"] += 1
            if status == "dry_run":
                group["dry_run_count"] += 1
            elif status == "executed":
                group["executed_count"] += 1
            elif status == "blocked":
                group["blocked_count"] += 1
            elif status in {"failed", "error"}:
                group["failed_count"] += 1
            for reason in sample.get("blocked_reasons") or []:
                reason_text = str(reason)
                group["blocked_reason_counts"][reason_text] = group["blocked_reason_counts"].get(reason_text, 0) + 1
        normalized = []
        for group in groups.values():
            sample_count = int(group.get("sample_count") or 0)
            feasible_count = int(group.get("dry_run_count") or 0) + int(group.get("executed_count") or 0)
            normalized.append(
                {
                    **group,
                    "feasible_rate": round(feasible_count / sample_count, 6) if sample_count else 0.0,
                    "blocked_rate": round(int(group.get("blocked_count") or 0) / sample_count, 6) if sample_count else 0.0,
                    "review_only": True,
                    "simulation_only": True,
                }
            )
        return sorted(
            normalized,
            key=lambda item: (-int(item.get("sample_count") or 0), str(item.get("key") or "")),
        )

    def _rule_family_key(self, sample: dict[str, Any]) -> str:
        return "|".join(
            str(part or "unknown")
            for part in [
                sample.get("pattern_id"),
                sample.get("category"),
                sample.get("action"),
                sample.get("risk_level"),
            ]
        )

    def _majority_label(self, samples: list[dict[str, Any]]) -> str:
        counts: dict[str, int] = {}
        for item in samples:
            label = str(item.get("training_label") or "unknown")
            counts[label] = counts.get(label, 0) + 1
        if not counts:
            return "unknown"
        return sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))[0][0]

    def _grouped_label_model(self, train_samples: list[dict[str, Any]]) -> dict[str, Any]:
        majority_label = self._majority_label(train_samples)
        group_levels = [
            "source_action_status_risk",
            "source_action_status",
            "source_action",
            "source",
        ]
        rules: dict[str, dict[str, dict[str, Any]]] = {level: {} for level in group_levels}
        for level in group_levels:
            grouped_counts: dict[str, dict[str, int]] = {}
            for sample in train_samples:
                key = self._feature_group_key(sample, level)
                label = str(sample.get("training_label") or "unknown")
                grouped_counts.setdefault(key, {})
                grouped_counts[key][label] = grouped_counts[key].get(label, 0) + 1
            for key, counts in grouped_counts.items():
                label, count = sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))[0]
                total = sum(counts.values())
                rules[level][key] = {
                    "label": label,
                    "sample_count": total,
                    "confidence": round(count / total, 6) if total else 0.0,
                    "label_counts": counts,
                }
        return {
            "kind": "hierarchical_grouped_label_classifier",
            "fallback_majority_label": majority_label,
            "group_levels": group_levels,
            "group_rule_counts": {level: len(rules[level]) for level in group_levels},
            "top_groups": {
                level: sorted(
                    rules[level].items(),
                    key=lambda item: (-int(item[1].get("sample_count") or 0), item[0]),
                )[:10]
                for level in group_levels
            },
            "rules": rules,
            "feature_policy": "audit_metadata_grouped_statistics_only",
            "artifact_written": False,
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _evaluate_grouped_label_model(
        self,
        model: dict[str, Any],
        validation_samples: list[dict[str, Any]],
    ) -> dict[str, Any]:
        validation_count = len(validation_samples)
        majority_label = str(model.get("fallback_majority_label") or "unknown")
        grouped_correct = 0
        majority_correct = 0
        fallback_count = 0
        prediction_counts: dict[str, int] = {}
        level_counts: dict[str, int] = {}
        for sample in validation_samples:
            predicted_label, level = self._predict_grouped_label(model, sample)
            actual_label = str(sample.get("training_label") or "unknown")
            if predicted_label == actual_label:
                grouped_correct += 1
            if majority_label == actual_label:
                majority_correct += 1
            if level == "fallback_majority":
                fallback_count += 1
            prediction_counts[predicted_label] = prediction_counts.get(predicted_label, 0) + 1
            level_counts[level] = level_counts.get(level, 0) + 1
        grouped_accuracy = grouped_correct / validation_count if validation_count else 0.0
        majority_accuracy = majority_correct / validation_count if validation_count else 0.0
        return {
            "validation_accuracy": grouped_accuracy,
            "grouped_validation_accuracy": grouped_accuracy,
            "majority_validation_accuracy": majority_accuracy,
            "accuracy_lift_vs_majority": grouped_accuracy - majority_accuracy,
            "correct_validation_count": grouped_correct,
            "majority_correct_validation_count": majority_correct,
            "fallback_prediction_count": fallback_count,
            "prediction_counts": prediction_counts,
            "prediction_level_counts": level_counts,
        }

    def _predict_grouped_label(self, model: dict[str, Any], sample: dict[str, Any]) -> tuple[str, str]:
        rules = model.get("rules") or {}
        for level in model.get("group_levels") or []:
            key = self._feature_group_key(sample, str(level))
            rule = (rules.get(level) or {}).get(key)
            if isinstance(rule, dict) and rule.get("label"):
                return str(rule["label"]), str(level)
        return str(model.get("fallback_majority_label") or "unknown"), "fallback_majority"

    def _feature_group_key(self, sample: dict[str, Any], level: str) -> str:
        features = sample.get("model_features") or {}
        source = str(features.get("source") or sample.get("source") or "unknown")
        action = str(features.get("action") or sample.get("action") or "unknown")
        status = str(features.get("status") or sample.get("status") or "unknown")
        risk = str(features.get("risk_level") or sample.get("risk_level") or "unknown")
        if level == "source_action_status_risk":
            return "|".join([source, action, status, risk])
        if level == "source_action_status":
            return "|".join([source, action, status])
        if level == "source_action":
            return "|".join([source, action])
        if level == "source":
            return source
        return "global"

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
