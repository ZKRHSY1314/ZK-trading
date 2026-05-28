"""Signal performance aggregation and calibration proposal service.

This service evaluates which signals, sample types, risk flags, and scoring
components are working based on outcome labels. It generates calibration
proposals for human review — proposals never mutate scoring weights or
strategy rules automatically.

Safety:
- No live trading or broker control.
- No credentials.
- No order placement.
- No automatic weight/rule mutation.
- Proposals are review-only.
"""

import json
from datetime import datetime
from typing import Any

from app.config import settings
from app.models import CalibrationProposal
from app.storage.sqlite_store import SQLiteStore

SMALL_SAMPLE_THRESHOLD = 10


class SignalPerformanceService:
    def __init__(self) -> None:
        self.store = SQLiteStore(settings.database_path)

    # ------------------------------------------------------------------
    # Performance summary
    # ------------------------------------------------------------------

    def performance_summary(self) -> dict[str, Any]:
        """Aggregate outcomes by sample_type, label, risk_flag, symbol, and
        scoring components.  Return structured performance rows with honest
        small-sample warnings."""
        self.store.init()

        rows = self.store.fetch_all(
            """
            SELECT
                s.id            AS sample_id,
                s.sample_type,
                s.symbol,
                s.name,
                s.label         AS original_label,
                s.risk_flags_json,
                s.features_json,
                o.outcome_label,
                o.risk_outcome,
                o.close_return_pct,
                o.max_return_pct,
                o.min_return_pct
            FROM agent_learning_outcomes o
            JOIN agent_learning_samples s ON s.id = o.sample_id
            ORDER BY s.sample_type, s.symbol
            """
        )

        by_sample_type = self._aggregate_group(rows, key_fn=lambda r: r["sample_type"])
        by_label = self._aggregate_group(rows, key_fn=lambda r: r["original_label"] or "unlabeled")
        by_risk_flag = self._aggregate_by_risk_flag(rows)
        by_symbol = self._aggregate_group(
            [r for r in rows if r["symbol"]],
            key_fn=lambda r: r["symbol"],
        )
        by_scoring_component = self._aggregate_by_scoring_component(rows)

        return {
            "total_samples_with_outcomes": len(rows),
            "by_sample_type": by_sample_type,
            "by_label": by_label,
            "by_risk_flag": by_risk_flag,
            "by_symbol": by_symbol,
            "by_scoring_component": by_scoring_component,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
        }

    # ------------------------------------------------------------------
    # Calibration proposals
    # ------------------------------------------------------------------

    def generate_proposals(self, created_by: str = "system") -> dict[str, Any]:
        """Generate calibration proposals based on performance summary.

        Proposals are review-only and never mutate scoring weights or
        strategy rules.
        """
        self.store.init()
        summary = self.performance_summary()
        proposals: list[dict[str, Any]] = []

        # --- by sample_type ---
        for group_key, stats in summary.get("by_sample_type", {}).items():
            proposal = self._propose_for_group("sample_type", group_key, stats)
            if proposal:
                proposals.append(proposal)

        # --- by label ---
        for group_key, stats in summary.get("by_label", {}).items():
            proposal = self._propose_for_group("label", group_key, stats)
            if proposal:
                proposals.append(proposal)

        # --- by risk_flag ---
        for group_key, stats in summary.get("by_risk_flag", {}).items():
            proposal = self._propose_for_group("risk_flag", group_key, stats)
            if proposal:
                proposals.append(proposal)

        # --- by symbol (only when sample count >= threshold) ---
        for group_key, stats in summary.get("by_symbol", {}).items():
            if stats.get("sample_count", 0) >= SMALL_SAMPLE_THRESHOLD:
                proposal = self._propose_for_group("symbol", group_key, stats)
                if proposal:
                    proposals.append(proposal)

        # Persist proposals
        saved: list[dict[str, Any]] = []
        for p in proposals:
            saved.append(self._save_proposal(
                proposal_type=p["proposal_type"],
                target=p["target"],
                evidence_json=p["evidence"],
                proposal_json=p["proposal"],
                created_by=created_by,
            ))

        return {
            "generated_count": len(saved),
            "proposals": saved,
            "summary_snapshot": {
                "total_samples_with_outcomes": summary["total_samples_with_outcomes"],
                "sample_type_count": len(summary.get("by_sample_type", {})),
                "label_count": len(summary.get("by_label", {})),
                "risk_flag_count": len(summary.get("by_risk_flag", {})),
                "symbol_count": len(summary.get("by_symbol", {})),
            },
            "generated_at": summary["generated_at"],
        }

    def list_proposals(
        self,
        status: str | None = None,
        limit: int = 50,
    ) -> list[CalibrationProposal]:
        self.store.init()
        limit = max(1, min(int(limit), 500))
        if status:
            rows = self.store.fetch_all(
                "SELECT * FROM agent_calibration_proposals WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                (status, limit),
            )
        else:
            rows = self.store.fetch_all(
                "SELECT * FROM agent_calibration_proposals ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )
        return [self._row_to_proposal(r) for r in rows]

    def get_proposal(self, proposal_id: int) -> CalibrationProposal | None:
        self.store.init()
        row = self.store.fetch_one(
            "SELECT * FROM agent_calibration_proposals WHERE id = ?",
            (proposal_id,),
        )
        if not row:
            return None
        return self._row_to_proposal(row)

    def approve_proposal(
        self,
        proposal_id: int,
        reviewed_by: str = "admin",
        review_note: str | None = None,
    ) -> CalibrationProposal:
        self.store.init()
        row = self.store.fetch_one(
            "SELECT * FROM agent_calibration_proposals WHERE id = ?",
            (proposal_id,),
        )
        if not row:
            raise ValueError(f"Proposal {proposal_id} not found")
        if row["status"] != "pending":
            raise ValueError(
                f"Proposal {proposal_id} is '{row['status']}', can only approve 'pending'"
            )

        now = datetime.now().isoformat(timespec="seconds")
        with self.store.connect() as conn:
            conn.execute(
                """
                UPDATE agent_calibration_proposals
                SET status = 'approved',
                    reviewed_by = ?,
                    review_note = ?,
                    reviewed_at = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (reviewed_by, review_note, now, now, proposal_id),
            )
        return self.get_proposal(proposal_id)  # type: ignore[return-value]

    def reject_proposal(
        self,
        proposal_id: int,
        reviewed_by: str = "admin",
        review_note: str | None = None,
    ) -> CalibrationProposal:
        self.store.init()
        row = self.store.fetch_one(
            "SELECT * FROM agent_calibration_proposals WHERE id = ?",
            (proposal_id,),
        )
        if not row:
            raise ValueError(f"Proposal {proposal_id} not found")
        if row["status"] != "pending":
            raise ValueError(
                f"Proposal {proposal_id} is '{row['status']}', can only reject 'pending'"
            )

        now = datetime.now().isoformat(timespec="seconds")
        with self.store.connect() as conn:
            conn.execute(
                """
                UPDATE agent_calibration_proposals
                SET status = 'rejected',
                    reviewed_by = ?,
                    review_note = ?,
                    reviewed_at = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (reviewed_by, review_note, now, now, proposal_id),
            )
        return self.get_proposal(proposal_id)  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _aggregate_group(
        self,
        rows: list[dict[str, Any]],
        key_fn,
    ) -> dict[str, dict[str, Any]]:
        groups: dict[str, list[dict[str, Any]]] = {}
        for r in rows:
            key = key_fn(r)
            if key is None:
                continue
            groups.setdefault(key, []).append(r)

        result: dict[str, dict[str, Any]] = {}
        for key, items in groups.items():
            result[key] = self._compute_stats(items)
        return result

    def _aggregate_by_risk_flag(
        self, rows: list[dict[str, Any]]
    ) -> dict[str, dict[str, Any]]:
        groups: dict[str, list[dict[str, Any]]] = {}
        for r in rows:
            flags_raw = r.get("risk_flags_json", "[]")
            try:
                flags = json.loads(flags_raw) if isinstance(flags_raw, str) else flags_raw
            except (json.JSONDecodeError, TypeError):
                flags = []
            if not flags:
                groups.setdefault("no_risk_flag", []).append(r)
            else:
                for flag in flags:
                    groups.setdefault(str(flag), []).append(r)
        result: dict[str, dict[str, Any]] = {}
        for key, items in groups.items():
            result[key] = self._compute_stats(items)
        return result

    def _aggregate_by_scoring_component(
        self, rows: list[dict[str, Any]]
    ) -> dict[str, dict[str, Any]]:
        """Group by scoring components found in features_json."""
        component_keys = [
            "discovery_score",
            "volume_score",
            "phase_score",
            "lifecycle_score",
            "focus_score",
            "risk_penalty",
            "potential_score",
        ]
        groups: dict[str, list[dict[str, Any]]] = {}

        for r in rows:
            features_raw = r.get("features_json", "{}")
            try:
                features = json.loads(features_raw) if isinstance(features_raw, str) else features_raw
            except (json.JSONDecodeError, TypeError):
                features = {}
            if not isinstance(features, dict):
                continue
            components = features.get("components")
            if isinstance(components, dict):
                merged_features = {**features, **components}
            else:
                merged_features = features
            for ck in component_keys:
                val = merged_features.get(ck)
                if val is not None and isinstance(val, (int, float)):
                    bucket = f"{ck}:{'high' if val >= 5 else 'low'}"
                    groups.setdefault(bucket, []).append(r)

        result: dict[str, dict[str, Any]] = {}
        for key, items in groups.items():
            result[key] = self._compute_stats(items)
        return result

    def _compute_stats(self, items: list[dict[str, Any]]) -> dict[str, Any]:
        total = len(items)
        outcomes = [i for i in items if i.get("outcome_label")]
        outcome_count = len(outcomes)
        pending = [i for i in outcomes if i["outcome_label"] == "pending_future_data"]
        pending_count = len(pending)
        pending_rate = pending_count / outcome_count if outcome_count > 0 else 0.0

        strong = sum(1 for i in outcomes if i["outcome_label"] == "strong_follow_through")
        mild = sum(1 for i in outcomes if i["outcome_label"] == "mild_follow_through")
        failed = sum(1 for i in outcomes if i["outcome_label"] == "failed_signal")

        close_returns = [
            i["close_return_pct"]
            for i in outcomes
            if i.get("close_return_pct") is not None
        ]
        max_returns = [
            i["max_return_pct"]
            for i in outcomes
            if i.get("max_return_pct") is not None
        ]
        min_returns = [
            i["min_return_pct"]
            for i in outcomes
            if i.get("min_return_pct") is not None
        ]
        large_drawdown = sum(
            1
            for i in outcomes
            if i.get("risk_outcome") == "large_drawdown"
        )

        stats: dict[str, Any] = {
            "sample_count": total,
            "outcome_count": outcome_count,
            "pending_count": pending_count,
            "pending_rate": round(pending_rate, 4),
            "strong_follow_through_count": strong,
            "mild_follow_through_count": mild,
            "failed_signal_count": failed,
            "avg_close_return": round(sum(close_returns) / len(close_returns), 4) if close_returns else None,
            "avg_max_return": round(sum(max_returns) / len(max_returns), 4) if max_returns else None,
            "avg_min_return": round(sum(min_returns) / len(min_returns), 4) if min_returns else None,
            "large_drawdown_count": large_drawdown,
        }
        if total < SMALL_SAMPLE_THRESHOLD:
            stats["small_sample_warning"] = True
        return stats

    def _propose_for_group(
        self,
        proposal_type: str,
        target: str,
        stats: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Generate a single calibration proposal for one group based on its stats.

        Returns None if evidence is insufficient for a meaningful proposal.
        """
        sample_count = stats.get("sample_count", 0)
        if sample_count == 0:
            return None

        # If small sample, propose "wait for more data"
        if stats.get("small_sample_warning"):
            return {
                "proposal_type": proposal_type,
                "target": target,
                "evidence": stats,
                "proposal": {
                    "action": "wait_for_more_data",
                    "reason": f"Only {sample_count} samples - insufficient for calibration.",
                    "recommendation": "Collect more data before making adjustments.",
                    "review_only": True,
                },
            }

        pending_rate = stats.get("pending_rate", 0)
        strong = stats.get("strong_follow_through_count", 0)
        mild = stats.get("mild_follow_through_count", 0)
        failed = stats.get("failed_signal_count", 0)
        large_dd = stats.get("large_drawdown_count", 0)
        outcome_count = stats.get("outcome_count", 0)

        # Pending-heavy: too many outcomes still waiting
        if pending_rate > 0.5:
            return {
                "proposal_type": proposal_type,
                "target": target,
                "evidence": stats,
                "proposal": {
                    "action": "wait_for_future_data",
                    "reason": f"Pending rate {pending_rate:.0%} — majority of outcomes unresolved.",
                    "recommendation": "Re-evaluate after more future data is available.",
                    "review_only": True,
                },
            }

        resolved = outcome_count - stats.get("pending_count", 0)
        if resolved == 0:
            return None

        follow_through_rate = (strong + mild) / resolved if resolved > 0 else 0
        fail_rate = failed / resolved if resolved > 0 else 0
        dd_rate = large_dd / resolved if resolved > 0 else 0

        # Strong performer
        if follow_through_rate >= 0.6 and dd_rate < 0.15:
            return {
                "proposal_type": proposal_type,
                "target": target,
                "evidence": stats,
                "proposal": {
                    "action": "increase_review_priority",
                    "reason": (
                        f"Follow-through rate {follow_through_rate:.0%} with "
                        f"low drawdown risk ({dd_rate:.0%}). "
                        f"Strong: {strong}, Mild: {mild}, Failed: {failed}."
                    ),
                    "recommendation": (
                        "Consider increasing review priority for this signal group. "
                        "This is a review-only proposal — no weights or rules change."
                    ),
                    "review_only": True,
                },
            }

        # High failure / drawdown
        if fail_rate >= 0.4 or dd_rate >= 0.3:
            return {
                "proposal_type": proposal_type,
                "target": target,
                "evidence": stats,
                "proposal": {
                    "action": "reduce_score_contribution",
                    "reason": (
                        f"Failure rate {fail_rate:.0%}, large drawdown rate {dd_rate:.0%}. "
                        f"Strong: {strong}, Mild: {mild}, Failed: {failed}, "
                        f"Large drawdowns: {large_dd}."
                    ),
                    "recommendation": (
                        "Consider reducing score contribution for this signal group. "
                        "This is a review-only proposal — no weights or rules change."
                    ),
                    "review_only": True,
                },
            }

        # Inconclusive — keep / no-op
        return {
            "proposal_type": proposal_type,
            "target": target,
            "evidence": stats,
            "proposal": {
                "action": "keep_current",
                "reason": (
                    f"Mixed results: follow-through {follow_through_rate:.0%}, "
                    f"fail {fail_rate:.0%}, drawdown {dd_rate:.0%}. "
                    f"Evidence insufficient for a strong recommendation."
                ),
                "recommendation": (
                    "No change recommended at this time. Continue monitoring."
                ),
                "review_only": True,
            },
        }

    def _save_proposal(
        self,
        proposal_type: str,
        target: str,
        evidence_json: dict[str, Any],
        proposal_json: dict[str, Any],
        created_by: str,
    ) -> dict[str, Any]:
        with self.store.connect() as conn:
            existing = conn.execute(
                """
                SELECT id
                FROM agent_calibration_proposals
                WHERE proposal_type = ?
                  AND target = ?
                  AND status = 'pending'
                ORDER BY id DESC
                LIMIT 1
                """,
                (proposal_type, target),
            ).fetchone()
            if existing:
                now = datetime.now().isoformat(timespec="seconds")
                conn.execute(
                    """
                    UPDATE agent_calibration_proposals
                    SET evidence_json = ?,
                        proposal_json = ?,
                        created_by = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        json.dumps(evidence_json, ensure_ascii=False, default=str),
                        json.dumps(proposal_json, ensure_ascii=False, default=str),
                        created_by,
                        now,
                        existing["id"],
                    ),
                )
                proposal_id = existing["id"]
            else:
                cursor = conn.execute(
                    """
                    INSERT INTO agent_calibration_proposals (
                        proposal_type, target, status,
                        evidence_json, proposal_json,
                        created_by
                    ) VALUES (?, ?, 'pending', ?, ?, ?)
                    """,
                    (
                        proposal_type,
                        target,
                        json.dumps(evidence_json, ensure_ascii=False, default=str),
                        json.dumps(proposal_json, ensure_ascii=False, default=str),
                        created_by,
                    ),
                )
                proposal_id = cursor.lastrowid
        row = self.store.fetch_one(
            "SELECT * FROM agent_calibration_proposals WHERE id = ?",
            (proposal_id,),
        )
        return self._row_to_proposal(row).model_dump(mode="json")  # type: ignore[union-attr]

    def _row_to_proposal(self, row: dict[str, Any]) -> CalibrationProposal:
        evidence = {}
        proposal = {}
        if row.get("evidence_json"):
            try:
                evidence = json.loads(row["evidence_json"])
            except (json.JSONDecodeError, TypeError):
                pass
        if row.get("proposal_json"):
            try:
                proposal = json.loads(row["proposal_json"])
            except (json.JSONDecodeError, TypeError):
                pass
        return CalibrationProposal(
            id=row["id"],
            proposal_type=row["proposal_type"],
            target=row["target"],
            status=row["status"],
            evidence=evidence,
            proposal=proposal,
            created_by=row.get("created_by"),
            reviewed_by=row.get("reviewed_by"),
            review_note=row.get("review_note"),
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
            reviewed_at=row.get("reviewed_at"),
        )
