"""Sandbox experiment service for approved calibration proposals.

Runs what-if simulations for approved proposals using historical
outcomes and sample data.  Results are stored for human review.

Safety:
- No live trading or broker control.
- No credentials.
- No order placement.
- No production scoring/rule mutation.
- Experiments are sandbox-only.
"""

import json
from datetime import datetime
from typing import Any

from app.config import settings
from app.storage.sqlite_store import SQLiteStore

# Minimum resolved outcomes required for meaningful metrics.
MIN_RESOLVED_FOR_METRICS = 3


class SandboxExperimentService:
    def __init__(self) -> None:
        self.store = SQLiteStore(settings.database_path)

    # ------------------------------------------------------------------
    # Run a single experiment
    # ------------------------------------------------------------------

    def run_experiment(
        self,
        proposal_id: int,
        created_by: str = "system",
    ) -> dict[str, Any]:
        """Run a sandbox experiment for an approved proposal.

        Only proposals with status='approved' are accepted.
        This method never mutates scoring rules, candidate scores,
        strategy rules, or settings.
        """
        self.store.init()

        proposal = self.store.fetch_one(
            "SELECT * FROM agent_calibration_proposals WHERE id = ?",
            (proposal_id,),
        )
        if not proposal:
            raise ValueError(f"Proposal {proposal_id} not found")
        if proposal["status"] != "approved":
            raise ValueError(
                f"Proposal {proposal_id} has status '{proposal['status']}'; "
                f"only 'approved' proposals can run sandbox experiments"
            )

        # Parse proposal data
        evidence = _parse_json(proposal.get("evidence_json", "{}"))
        proposal_data = _parse_json(proposal.get("proposal_json", "{}"))
        action = proposal_data.get("action", "unknown")
        proposal_type = proposal["proposal_type"]
        target = proposal["target"]

        # Check for existing experiment
        existing = self.store.fetch_one(
            "SELECT id FROM agent_sandbox_experiments "
            "WHERE proposal_id = ? AND status IN ('completed', 'running') "
            "ORDER BY id DESC LIMIT 1",
            (proposal_id,),
        )
        if existing:
            return self._load_experiment(existing["id"])

        # Compute baseline metrics from current outcomes
        baseline_metrics = self._compute_baseline_metrics(proposal_type, target)

        # Compute proposed metrics (what-if evaluation)
        proposed_metrics = self._compute_proposed_metrics(
            action, proposal_type, target, evidence, proposal_data, baseline_metrics
        )

        # Build comparison
        comparison = self._build_comparison(baseline_metrics, proposed_metrics, action)

        # Determine conclusion
        conclusion = self._determine_conclusion(
            action, baseline_metrics, proposed_metrics, comparison
        )

        # Persist the experiment
        now = datetime.now().isoformat(timespec="seconds")
        with self.store.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO agent_sandbox_experiments (
                    proposal_id, status,
                    baseline_metrics_json, proposed_metrics_json,
                    comparison_json, conclusion,
                    created_by, created_at, updated_at, completed_at
                ) VALUES (?, 'completed', ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    proposal_id,
                    json.dumps(baseline_metrics, ensure_ascii=False, default=str),
                    json.dumps(proposed_metrics, ensure_ascii=False, default=str),
                    json.dumps(comparison, ensure_ascii=False, default=str),
                    conclusion,
                    created_by,
                    now,
                    now,
                    now,
                ),
            )
            experiment_id = cursor.lastrowid

        return self._load_experiment(experiment_id)

    # ------------------------------------------------------------------
    # Run experiments for all approved proposals
    # ------------------------------------------------------------------

    def run_approved(
        self,
        limit: int = 20,
        created_by: str = "system",
    ) -> dict[str, Any]:
        """Run experiments for approved proposals that lack an experiment."""
        self.store.init()
        limit = max(1, min(int(limit), 200))

        approved = self.store.fetch_all(
            """
            SELECT p.id
            FROM agent_calibration_proposals p
            LEFT JOIN agent_sandbox_experiments e
                ON e.proposal_id = p.id AND e.status = 'completed'
            WHERE p.status = 'approved'
              AND e.id IS NULL
            ORDER BY p.id
            LIMIT ?
            """,
            (limit,),
        )

        results: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []
        for row in approved:
            try:
                result = self.run_experiment(row["id"], created_by=created_by)
                results.append(result)
            except Exception as exc:
                errors.append({"proposal_id": row["id"], "error": str(exc)})

        return {
            "run_count": len(results),
            "error_count": len(errors),
            "experiments": results,
            "errors": errors,
        }

    # ------------------------------------------------------------------
    # List / summary
    # ------------------------------------------------------------------

    def list_experiments(self, limit: int = 50) -> list[dict[str, Any]]:
        self.store.init()
        self._normalize_stored_conclusions()
        limit = max(1, min(int(limit), 500))
        rows = self.store.fetch_all(
            "SELECT * FROM agent_sandbox_experiments ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
        return [self._row_to_dict(r) for r in rows]

    def summary(self) -> dict[str, Any]:
        self.store.init()
        self._normalize_stored_conclusions()
        total = self.store.fetch_one(
            "SELECT COUNT(*) AS cnt FROM agent_sandbox_experiments"
        )
        by_conclusion = self.store.fetch_all(
            "SELECT conclusion, COUNT(*) AS cnt "
            "FROM agent_sandbox_experiments GROUP BY conclusion"
        )
        by_status = self.store.fetch_all(
            "SELECT status, COUNT(*) AS cnt "
            "FROM agent_sandbox_experiments GROUP BY status"
        )

        # Count approved proposals without an experiment
        pending_proposals = self.store.fetch_one(
            """
            SELECT COUNT(*) AS cnt
            FROM agent_calibration_proposals p
            LEFT JOIN agent_sandbox_experiments e
                ON e.proposal_id = p.id AND e.status = 'completed'
            WHERE p.status = 'approved'
              AND e.id IS NULL
            """
        )

        return {
            "total_experiments": total["cnt"] if total else 0,
            "by_conclusion": {r["conclusion"]: r["cnt"] for r in by_conclusion},
            "by_status": {r["status"]: r["cnt"] for r in by_status},
            "approved_proposals_without_experiment": (
                pending_proposals["cnt"] if pending_proposals else 0
            ),
        }

    # ------------------------------------------------------------------
    # Baseline metrics computation
    # ------------------------------------------------------------------

    def _compute_baseline_metrics(
        self, proposal_type: str, target: str
    ) -> dict[str, Any]:
        """Compute baseline metrics from existing outcomes for the target group."""
        rows = self._fetch_outcome_rows(proposal_type, target)
        if not rows:
            return {
                "sample_count": 0,
                "note": "No matching outcome rows found for baseline.",
            }
        return self._aggregate_metrics(rows, label="baseline")

    # ------------------------------------------------------------------
    # Proposed metrics computation (what-if)
    # ------------------------------------------------------------------

    def _compute_proposed_metrics(
        self,
        action: str,
        proposal_type: str,
        target: str,
        evidence: dict[str, Any],
        proposal_data: dict[str, Any],
        baseline: dict[str, Any],
    ) -> dict[str, Any]:
        """Compute what-if metrics for the proposed action.

        This evaluates the *expected impact* of the proposal without
        mutating any production state.
        """
        if action == "increase_review_priority":
            return self._what_if_increase_priority(
                proposal_type, target, evidence, baseline
            )
        elif action == "reduce_score_contribution":
            return self._what_if_reduce_contribution(
                proposal_type, target, evidence, baseline
            )
        elif action in ("wait_for_more_data", "wait_for_future_data"):
            return {
                "action": action,
                "behavior_change": False,
                "note": (
                    "No behavior change - this proposal recommends "
                    "waiting for additional data before acting."
                ),
                "baseline_sample_count": baseline.get("sample_count", 0),
            }
        elif action == "keep_current":
            return {
                "action": action,
                "behavior_change": False,
                "note": (
                    "No behavior change - evidence is insufficient "
                    "for a strong recommendation."
                ),
                "baseline_sample_count": baseline.get("sample_count", 0),
            }
        else:
            return {
                "action": action,
                "behavior_change": False,
                "note": f"Unknown action '{action}'; no simulation performed.",
            }

    def _what_if_increase_priority(
        self,
        proposal_type: str,
        target: str,
        evidence: dict[str, Any],
        baseline: dict[str, Any],
    ) -> dict[str, Any]:
        """Estimate coverage/priority impact for increase_review_priority."""
        rows = self._fetch_outcome_rows(proposal_type, target)
        total_samples_all = self.store.fetch_one(
            "SELECT COUNT(*) AS cnt FROM agent_learning_samples"
        )
        total_all = total_samples_all["cnt"] if total_samples_all else 0

        group_count = len(rows)
        coverage_pct = (group_count / total_all * 100) if total_all > 0 else 0

        # Simulated effect: if priority increased, these samples would be
        # reviewed earlier. Estimate how many strong/mild follow-throughs
        # would be surfaced sooner.
        metrics = self._aggregate_metrics(rows, label="proposed_increased_priority")
        metrics["action"] = "increase_review_priority"
        metrics["behavior_change"] = True
        metrics["estimated_coverage_pct"] = round(coverage_pct, 2)
        metrics["group_count"] = group_count
        metrics["total_population"] = total_all
        metrics["note"] = (
            f"Increasing priority would surface {group_count} samples "
            f"({coverage_pct:.1f}% of population) for earlier review."
        )
        return metrics

    def _what_if_reduce_contribution(
        self,
        proposal_type: str,
        target: str,
        evidence: dict[str, Any],
        baseline: dict[str, Any],
    ) -> dict[str, Any]:
        """Estimate how many samples would be demoted by reducing contribution."""
        rows = self._fetch_outcome_rows(proposal_type, target)
        resolved = [
            r for r in rows
            if r.get("outcome_label")
            and r["outcome_label"] != "pending_future_data"
        ]
        total = len(resolved)

        # Count how many would be "demoted" - those that actually had
        # follow-through outcomes would lose priority unnecessarily.
        strong = sum(
            1 for r in resolved if r["outcome_label"] == "strong_follow_through"
        )
        mild = sum(
            1 for r in resolved if r["outcome_label"] == "mild_follow_through"
        )
        failed = sum(
            1 for r in resolved if r["outcome_label"] == "failed_signal"
        )

        demoted_good = strong + mild
        justified_demotion = failed

        metrics = self._aggregate_metrics(rows, label="proposed_reduced_contribution")
        metrics["action"] = "reduce_score_contribution"
        metrics["behavior_change"] = True
        metrics["total_resolved"] = total
        metrics["demoted_good_outcomes"] = demoted_good
        metrics["justified_demotions"] = justified_demotion
        metrics["collateral_damage_pct"] = (
            round(demoted_good / total * 100, 2) if total > 0 else 0
        )
        metrics["note"] = (
            f"Reducing contribution would demote {total} samples. "
            f"{justified_demotion} failed signals justify demotion, "
            f"but {demoted_good} positive outcomes would also be demoted "
            f"({metrics['collateral_damage_pct']:.1f}% collateral damage)."
        )
        return metrics

    # ------------------------------------------------------------------
    # Comparison and conclusion
    # ------------------------------------------------------------------

    def _build_comparison(
        self,
        baseline: dict[str, Any],
        proposed: dict[str, Any],
        action: str,
    ) -> dict[str, Any]:
        """Build a before/after comparison dict."""
        comparison: dict[str, Any] = {
            "action": action,
            "baseline_sample_count": baseline.get("sample_count", 0),
            "proposed_behavior_change": proposed.get("behavior_change", False),
        }

        # Compare numeric metrics that exist in both
        for key in [
            "avg_close_return",
            "avg_max_return",
            "avg_min_return",
            "strong_follow_through_count",
            "mild_follow_through_count",
            "failed_signal_count",
            "large_drawdown_count",
        ]:
            b_val = baseline.get(key)
            p_val = proposed.get(key)
            if b_val is not None and p_val is not None:
                comparison[f"{key}_baseline"] = b_val
                comparison[f"{key}_proposed"] = p_val
                if isinstance(b_val, (int, float)) and isinstance(
                    p_val, (int, float)
                ):
                    comparison[f"{key}_delta"] = round(p_val - b_val, 4)

        return comparison

    def _determine_conclusion(
        self,
        action: str,
        baseline: dict[str, Any],
        proposed: dict[str, Any],
        comparison: dict[str, Any],
    ) -> str:
        """Determine a human-readable conclusion for the experiment."""
        resolved_count = baseline.get("resolved_count", 0)
        if resolved_count < MIN_RESOLVED_FOR_METRICS:
            return "insufficient_evidence"

        if not proposed.get("behavior_change", False):
            return "no_behavior_change"

        if action == "increase_review_priority":
            coverage = proposed.get("estimated_coverage_pct", 0)
            if coverage > 0:
                return "priority_increase_viable"
            return "insufficient_evidence"

        if action == "reduce_score_contribution":
            collateral = proposed.get("collateral_damage_pct", 100)
            if collateral < 30:
                return "reduction_justified"
            elif collateral < 60:
                return "reduction_mixed"
            else:
                return "reduction_high_collateral"

        return "inconclusive"

    # ------------------------------------------------------------------
    # Data fetching helpers
    # ------------------------------------------------------------------

    def _fetch_outcome_rows(
        self, proposal_type: str, target: str
    ) -> list[dict[str, Any]]:
        """Fetch outcome rows matching the proposal's group."""
        if proposal_type == "sample_type":
            return self.store.fetch_all(
                """
                SELECT s.*, o.outcome_label, o.risk_outcome,
                       o.close_return_pct, o.max_return_pct, o.min_return_pct
                FROM agent_learning_outcomes o
                JOIN agent_learning_samples s ON s.id = o.sample_id
                WHERE s.sample_type = ?
                """,
                (target,),
            )
        elif proposal_type == "label":
            return self.store.fetch_all(
                """
                SELECT s.*, o.outcome_label, o.risk_outcome,
                       o.close_return_pct, o.max_return_pct, o.min_return_pct
                FROM agent_learning_outcomes o
                JOIN agent_learning_samples s ON s.id = o.sample_id
                WHERE s.label = ?
                """,
                (target,),
            )
        elif proposal_type == "risk_flag":
            # Risk flags are stored as JSON arrays
            return self.store.fetch_all(
                """
                SELECT s.*, o.outcome_label, o.risk_outcome,
                       o.close_return_pct, o.max_return_pct, o.min_return_pct
                FROM agent_learning_outcomes o
                JOIN agent_learning_samples s ON s.id = o.sample_id
                WHERE s.risk_flags_json LIKE ?
                """,
                (f'%"{target}"%',),
            )
        elif proposal_type == "symbol":
            return self.store.fetch_all(
                """
                SELECT s.*, o.outcome_label, o.risk_outcome,
                       o.close_return_pct, o.max_return_pct, o.min_return_pct
                FROM agent_learning_outcomes o
                JOIN agent_learning_samples s ON s.id = o.sample_id
                WHERE s.symbol = ?
                """,
                (target,),
            )
        else:
            return []

    def _aggregate_metrics(
        self, rows: list[dict[str, Any]], label: str = ""
    ) -> dict[str, Any]:
        """Aggregate standard metrics from outcome rows."""
        total = len(rows)
        resolved = [
            r for r in rows
            if r.get("outcome_label")
            and r["outcome_label"] != "pending_future_data"
        ]
        pending = [
            r for r in rows
            if r.get("outcome_label") == "pending_future_data"
        ]

        strong = sum(
            1 for r in resolved if r["outcome_label"] == "strong_follow_through"
        )
        mild = sum(
            1 for r in resolved if r["outcome_label"] == "mild_follow_through"
        )
        failed = sum(
            1 for r in resolved if r["outcome_label"] == "failed_signal"
        )
        large_dd = sum(
            1 for r in resolved if r.get("risk_outcome") == "large_drawdown"
        )

        close_returns = [
            r["close_return_pct"]
            for r in resolved
            if r.get("close_return_pct") is not None
        ]
        max_returns = [
            r["max_return_pct"]
            for r in resolved
            if r.get("max_return_pct") is not None
        ]
        min_returns = [
            r["min_return_pct"]
            for r in resolved
            if r.get("min_return_pct") is not None
        ]

        metrics: dict[str, Any] = {
            "label": label,
            "sample_count": total,
            "resolved_count": len(resolved),
            "pending_count": len(pending),
            "strong_follow_through_count": strong,
            "mild_follow_through_count": mild,
            "failed_signal_count": failed,
            "large_drawdown_count": large_dd,
            "avg_close_return": (
                round(sum(close_returns) / len(close_returns), 4)
                if close_returns
                else None
            ),
            "avg_max_return": (
                round(sum(max_returns) / len(max_returns), 4)
                if max_returns
                else None
            ),
            "avg_min_return": (
                round(sum(min_returns) / len(min_returns), 4)
                if min_returns
                else None
            ),
        }

        if len(resolved) < MIN_RESOLVED_FOR_METRICS:
            metrics["small_sample_warning"] = True
            metrics["small_sample_reason"] = (
                f"Only {len(resolved)} resolved outcomes; "
                f"{MIN_RESOLVED_FOR_METRICS} required for a conclusion."
            )

        return metrics

    # ------------------------------------------------------------------
    # Row helpers
    # ------------------------------------------------------------------

    def _load_experiment(self, experiment_id: int) -> dict[str, Any]:
        self._normalize_stored_conclusions(experiment_id=experiment_id)
        row = self.store.fetch_one(
            "SELECT * FROM agent_sandbox_experiments WHERE id = ?",
            (experiment_id,),
        )
        if not row:
            raise ValueError(f"Experiment {experiment_id} not found")
        return self._row_to_dict(row)

    def _row_to_dict(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": row["id"],
            "proposal_id": row["proposal_id"],
            "status": row["status"],
            "baseline_metrics": _parse_json(
                row.get("baseline_metrics_json", "{}")
            ),
            "proposed_metrics": _parse_json(
                row.get("proposed_metrics_json", "{}")
            ),
            "comparison": _parse_json(row.get("comparison_json", "{}")),
            "conclusion": row["conclusion"],
            "created_by": row.get("created_by"),
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
            "completed_at": row.get("completed_at"),
        }

    def _normalize_stored_conclusions(self, experiment_id: int | None = None) -> None:
        """Keep stored sandbox conclusions aligned with current evidence guards."""
        sql = (
            "SELECT id, baseline_metrics_json, proposed_metrics_json, conclusion "
            "FROM agent_sandbox_experiments"
        )
        params: tuple[Any, ...] = ()
        if experiment_id is not None:
            sql += " WHERE id = ?"
            params = (experiment_id,)

        rows = self.store.fetch_all(sql, params)
        updates: list[tuple[str, str, int]] = []
        for row in rows:
            baseline = _parse_json(row.get("baseline_metrics_json", "{}"))
            resolved_count = int(baseline.get("resolved_count") or 0)
            conclusion = row.get("conclusion") or ""
            if resolved_count < MIN_RESOLVED_FOR_METRICS:
                conclusion = "insufficient_evidence"

            proposed_metrics = _parse_json(row.get("proposed_metrics_json", "{}"))
            note = proposed_metrics.get("note")
            if isinstance(note, str):
                clean_note = note.replace("\u00e2\u0080\u0094", "-").replace(
                    "\u2014", "-"
                )
                if clean_note != note:
                    proposed_metrics["note"] = clean_note

            proposed_json = json.dumps(
                proposed_metrics, ensure_ascii=False, default=str
            )
            if (
                conclusion != (row.get("conclusion") or "")
                or proposed_json != (row.get("proposed_metrics_json") or "{}")
            ):
                updates.append((conclusion, proposed_json, row["id"]))

        if not updates:
            return

        now = datetime.now().isoformat(timespec="seconds")
        with self.store.connect() as conn:
            conn.executemany(
                """
                UPDATE agent_sandbox_experiments
                SET conclusion = ?, proposed_metrics_json = ?, updated_at = ?
                WHERE id = ?
                """,
                [
                    (conclusion, proposed_json, now, experiment_id)
                    for conclusion, proposed_json, experiment_id in updates
                ],
            )


def _parse_json(raw: Any) -> dict[str, Any]:
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}
