from __future__ import annotations

import hashlib
import json
from typing import Any

from app.config import settings
from app.storage.sqlite_store import SQLiteStore


class ForecastCalibrationService:
    """Persist evaluation changes and create review-only challenger proposals."""

    def __init__(self, store: SQLiteStore) -> None:
        self.store = store
        self.store.init()

    def persist(
        self,
        evaluation: dict[str, Any],
        *,
        created_by: str = "forecast_feedback",
    ) -> dict[str, Any]:
        if settings.enable_live_trading:
            return self._blocked()
        if evaluation.get("review_only") is not True:
            raise ValueError("forecast evaluation must be explicitly review-only")

        as_of = str(evaluation.get("as_of") or "").strip()
        if not as_of:
            raise ValueError("forecast evaluation as_of is required")
        snapshots: list[dict[str, Any]] = []
        proposals: list[dict[str, Any]] = []
        for scope, payload in (evaluation.get("by_scope") or {}).items():
            if scope not in {"stock", "sector"} or not isinstance(payload, dict):
                continue
            for metrics in payload.get("horizons") or []:
                if not isinstance(metrics, dict):
                    continue
                snapshot = self._record_snapshot(
                    as_of=as_of,
                    scope=scope,
                    metrics=metrics,
                )
                snapshots.append(snapshot)
                if metrics.get("status") == "ready":
                    proposals.append(
                        self._upsert_proposal(
                            evaluation_id=snapshot["evaluation_id"],
                            as_of=as_of,
                            scope=scope,
                            metrics=metrics,
                            created_by=created_by,
                        )
                    )
        return {
            "status": "completed" if snapshots else "insufficient_data",
            "schema_version": "forecast_calibration_run.v1",
            "evaluation_snapshot_count": len(snapshots),
            "new_evaluation_snapshot_count": sum(
                1 for snapshot in snapshots if snapshot["inserted"]
            ),
            "proposal_count": len(proposals),
            "proposal_ids": [proposal["id"] for proposal in proposals],
            "review_only": True,
            "apply_automatically": False,
            "live_trading_enabled": False,
        }

    def _record_snapshot(
        self,
        *,
        as_of: str,
        scope: str,
        metrics: dict[str, Any],
    ) -> dict[str, Any]:
        horizon_days = int(metrics["horizon_days"])
        canonical = json.dumps(
            {"scope": scope, "horizon_days": horizon_days, "metrics": metrics},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        evaluation_id = (
            "forecast-eval-" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:24]
        )
        with self.store.connect() as conn:
            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO forecast_evaluations(
                    evaluation_id, as_of, scope, horizon_days, status,
                    sample_count, fold_count, coverage, precision_at_k,
                    spearman_rank_ic, brier_score, metrics_json, review_only
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                """,
                (
                    evaluation_id,
                    as_of,
                    scope,
                    horizon_days,
                    str(metrics.get("status") or "insufficient_data"),
                    int(metrics.get("sample_count") or 0),
                    int(metrics.get("fold_count") or 0),
                    float(metrics.get("coverage") or 0.0),
                    metrics.get("precision_at_k"),
                    metrics.get("spearman_rank_ic"),
                    metrics.get("brier_score"),
                    canonical,
                ),
            )
            inserted = cursor.rowcount == 1
        return {
            "evaluation_id": evaluation_id,
            "scope": scope,
            "horizon_days": horizon_days,
            "inserted": inserted,
        }

    def _upsert_proposal(
        self,
        *,
        evaluation_id: str,
        as_of: str,
        scope: str,
        metrics: dict[str, Any],
        created_by: str,
    ) -> dict[str, Any]:
        horizon_days = int(metrics["horizon_days"])
        target = f"{scope}:{horizon_days}d"
        proposal = self._proposal(metrics, scope=scope)
        evidence = {
            "evaluation_id": evaluation_id,
            "as_of": as_of,
            "scope": scope,
            "horizon_days": horizon_days,
            "metrics": metrics,
            "review_only": True,
        }
        evidence_json = json.dumps(evidence, ensure_ascii=False, sort_keys=True, default=str)
        proposal_json = json.dumps(proposal, ensure_ascii=False, sort_keys=True, default=str)
        with self.store.connect() as conn:
            existing = conn.execute(
                """
                SELECT id FROM agent_calibration_proposals
                WHERE proposal_type = 'forecast_calibration'
                  AND target = ?
                  AND status = 'pending'
                ORDER BY id DESC LIMIT 1
                """,
                (target,),
            ).fetchone()
            if existing:
                proposal_id = int(existing["id"])
                conn.execute(
                    """
                    UPDATE agent_calibration_proposals
                    SET evidence_json = ?, proposal_json = ?, created_by = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (evidence_json, proposal_json, created_by, proposal_id),
                )
            else:
                cursor = conn.execute(
                    """
                    INSERT INTO agent_calibration_proposals(
                        proposal_type, target, status, evidence_json,
                        proposal_json, created_by
                    ) VALUES ('forecast_calibration', ?, 'pending', ?, ?, ?)
                    """,
                    (target, evidence_json, proposal_json, created_by),
                )
                proposal_id = int(cursor.lastrowid)
        return {"id": proposal_id, "target": target, "action": proposal["action"]}

    @staticmethod
    def _proposal(metrics: dict[str, Any], *, scope: str) -> dict[str, Any]:
        coverage_value = (
            metrics.get("directional_coverage") if scope == "sector" else metrics.get("coverage")
        )
        coverage = float(coverage_value or 0.0)
        precision = metrics.get("precision_at_k")
        rank_ic = metrics.get("spearman_rank_ic")
        brier = metrics.get("brier_score")
        if coverage < 0.8:
            action = "improve_data_coverage"
            reason = f"Evaluation coverage is {coverage:.1%}, below the 80% review threshold."
        elif (rank_ic is not None and float(rank_ic) < 0) or (
            precision is not None and float(precision) < 0.5
        ):
            action = "train_challenger_reduce_review_priority"
            reason = "Out-of-sample ranking evidence is adverse; train a challenger before reuse."
        elif brier is not None and float(brier) > 0.25:
            action = "recalibrate_probability"
            reason = "Directional ranking may remain useful, but probability calibration is weak."
        elif (rank_ic is not None and float(rank_ic) >= 0.05) or (
            precision is not None and float(precision) >= 0.55
        ):
            action = "retain_champion_validate_challenger"
            reason = (
                "Out-of-sample evidence is positive enough for continued challenger validation."
            )
        else:
            action = "continue_monitoring"
            reason = "Metrics are ready but do not justify a model or priority change."
        return {
            "action": action,
            "reason": reason,
            "recommendation": (
                "Run a versioned sandbox/challenger experiment and require human review; "
                "do not mutate active scoring automatically."
            ),
            "review_only": True,
            "apply_automatically": False,
        }

    @staticmethod
    def _blocked() -> dict[str, Any]:
        return {
            "status": "blocked",
            "schema_version": "forecast_calibration_run.v1",
            "reason": "live_trading_enabled",
            "evaluation_snapshot_count": 0,
            "new_evaluation_snapshot_count": 0,
            "proposal_count": 0,
            "proposal_ids": [],
            "review_only": True,
            "apply_automatically": False,
            "live_trading_enabled": True,
        }
