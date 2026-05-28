"""Paper simulation runner and policy gate service.

Turns approved sandbox experiment outcomes into simulation-only policy
drafts, then runs paper-trading simulations under a human-approved gate.

Safety:
- Simulation-only. No live trading or broker control.
- No credentials storage.
- No real order placement.
- No production scoring/rule mutation.
- Simulated actions are explicitly labelled as simulation or observation.
"""

import json
from datetime import datetime
from typing import Any

from app.config import settings
from app.storage.sqlite_store import SQLiteStore

# Conclusions from sandbox experiments that are eligible for policy drafting.
ELIGIBLE_CONCLUSIONS = {
    "priority_increase_viable",
    "reduction_justified",
    "reduction_mixed",
    "insufficient_evidence",  # observation-only policy
}

# Conservative risk limits applied by default.
DEFAULT_RISK_LIMITS = {
    "max_candidates_per_run": 30,
    "max_simulated_position_ratio": 0.10,
    "skip_missing_price": True,
    "skip_high_risk_unless_observe": True,
}


def _parse_json(raw: Any) -> dict[str, Any]:
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}


def _parse_json_list(raw: Any) -> list[Any]:
    if not raw:
        return []
    if isinstance(raw, list):
        return raw
    try:
        result = json.loads(raw)
        return result if isinstance(result, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


class PaperSimulationService:
    def __init__(self) -> None:
        self.store = SQLiteStore(settings.database_path)

    # ------------------------------------------------------------------
    # Policy drafting from sandbox experiments
    # ------------------------------------------------------------------

    def draft_policies_from_experiments(
        self,
        limit: int = 20,
        created_by: str = "system",
    ) -> dict[str, Any]:
        """Generate draft policies from eligible completed sandbox experiments.

        Only experiments with conclusions in ELIGIBLE_CONCLUSIONS are used.
        Policies are always created as 'draft' - never auto-approved.
        Duplicate active drafts for the same source experiment + policy type
        are skipped.
        """
        self.store.init()
        limit = max(1, min(int(limit), 200))

        placeholders = ", ".join("?" for _ in ELIGIBLE_CONCLUSIONS)
        eligible = self.store.fetch_all(
            f"""
            SELECT e.*, p.proposal_type, p.target, p.proposal_json AS proposal_data_json
            FROM agent_sandbox_experiments e
            JOIN agent_calibration_proposals p ON p.id = e.proposal_id
            WHERE e.status = 'completed'
              AND e.conclusion IN ({placeholders})
            ORDER BY e.id DESC
            LIMIT ?
            """,
            (*ELIGIBLE_CONCLUSIONS, limit),
        )

        created: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []

        for exp_row in eligible:
            experiment_id = exp_row["id"]
            conclusion = exp_row["conclusion"]
            proposal_type = exp_row.get("proposal_type", "unknown")
            target = exp_row.get("target", "unknown")

            # Determine policy type from conclusion
            policy_type = self._conclusion_to_policy_type(conclusion)

            # Check for existing active draft for this experiment + policy type
            existing = self.store.fetch_one(
                """
                SELECT id FROM agent_simulation_policies
                WHERE source_experiment_id = ?
                  AND policy_type = ?
                  AND status IN ('draft', 'approved')
                LIMIT 1
                """,
                (experiment_id, policy_type),
            )
            if existing:
                skipped.append({
                    "experiment_id": experiment_id,
                    "policy_type": policy_type,
                    "reason": "active_draft_or_approved_exists",
                    "existing_policy_id": existing["id"],
                })
                continue

            # Build policy JSON
            proposed_metrics = _parse_json(exp_row.get("proposed_metrics_json", "{}"))
            comparison = _parse_json(exp_row.get("comparison_json", "{}"))
            proposal_data = _parse_json(exp_row.get("proposal_data_json", "{}"))

            policy_json = {
                "simulation_only": True,
                "disclaimer": (
                    "This policy is for SIMULATION ONLY. "
                    "It does not constitute investment advice, real trading "
                    "instructions, or broker automation."
                ),
                "policy_type": policy_type,
                "source_conclusion": conclusion,
                "source_proposal_type": proposal_type,
                "source_target": target,
                "action": proposed_metrics.get("action", proposal_data.get("action", "observe")),
                "observe_only": conclusion == "insufficient_evidence",
                "proposed_behavior": proposed_metrics.get("note", ""),
                "comparison_summary": {
                    k: v for k, v in comparison.items()
                    if k in ("action", "baseline_sample_count", "proposed_behavior_change")
                },
            }

            risk_limits = dict(DEFAULT_RISK_LIMITS)
            if conclusion == "insufficient_evidence":
                # Observation-only: no simulated entries
                risk_limits["allow_simulated_entry"] = False
            else:
                risk_limits["allow_simulated_entry"] = True

            now = datetime.now().isoformat(timespec="seconds")
            with self.store.connect() as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO agent_simulation_policies (
                        source_experiment_id, policy_type, status,
                        policy_json, risk_limits_json,
                        created_by, created_at, updated_at
                    ) VALUES (?, ?, 'draft', ?, ?, ?, ?, ?)
                    """,
                    (
                        experiment_id,
                        policy_type,
                        json.dumps(policy_json, ensure_ascii=False, default=str),
                        json.dumps(risk_limits, ensure_ascii=False, default=str),
                        created_by,
                        now,
                        now,
                    ),
                )
                policy_id = cursor.lastrowid

            created.append({
                "policy_id": policy_id,
                "experiment_id": experiment_id,
                "policy_type": policy_type,
                "status": "draft",
                "conclusion": conclusion,
            })

        return {
            "created_count": len(created),
            "skipped_count": len(skipped),
            "created": created,
            "skipped": skipped,
        }

    # ------------------------------------------------------------------
    # Approval gate
    # ------------------------------------------------------------------

    def approve_policy(
        self,
        policy_id: int,
        reviewed_by: str = "admin",
        review_note: str | None = None,
    ) -> dict[str, Any]:
        """Approve a draft simulation policy for running.

        Only draft policies can be approved.
        This does NOT mutate candidate scores, scoring rules,
        strategy rules, settings, or broker state.
        """
        self.store.init()
        policy = self._get_policy(policy_id)
        if policy["status"] != "draft":
            raise ValueError(
                f"Policy {policy_id} has status '{policy['status']}'; "
                f"only 'draft' policies can be approved"
            )

        now = datetime.now().isoformat(timespec="seconds")
        with self.store.connect() as conn:
            conn.execute(
                """
                UPDATE agent_simulation_policies
                SET status = 'approved', reviewed_by = ?, review_note = ?,
                    reviewed_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (reviewed_by, review_note, now, now, policy_id),
            )

        return self._load_policy(policy_id)

    def reject_policy(
        self,
        policy_id: int,
        reviewed_by: str = "admin",
        review_note: str | None = None,
    ) -> dict[str, Any]:
        """Reject a draft simulation policy.

        Only draft policies can be rejected.
        """
        self.store.init()
        policy = self._get_policy(policy_id)
        if policy["status"] != "draft":
            raise ValueError(
                f"Policy {policy_id} has status '{policy['status']}'; "
                f"only 'draft' policies can be rejected"
            )

        now = datetime.now().isoformat(timespec="seconds")
        with self.store.connect() as conn:
            conn.execute(
                """
                UPDATE agent_simulation_policies
                SET status = 'rejected', reviewed_by = ?, review_note = ?,
                    reviewed_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (reviewed_by, review_note, now, now, policy_id),
            )

        return self._load_policy(policy_id)

    # ------------------------------------------------------------------
    # Simulation runner
    # ------------------------------------------------------------------

    def run_simulation(
        self,
        policy_id: int,
        created_by: str = "system",
    ) -> dict[str, Any]:
        """Run a paper simulation for an approved policy.

        Only 'approved' policies may run simulations. Draft, rejected,
        and archived policies are blocked.

        Uses current candidate scores and local historical/monitoring
        data to create simulated actions. All actions are explicitly
        labelled as simulated or observational.

        Safety:
        - Does not call external broker software.
        - Does not store credentials.
        - Does not place real orders.
        - Does not mutate candidate scores, scoring rules, or settings.
        """
        self.store.init()
        policy = self._get_policy(policy_id)

        if policy["status"] != "approved":
            raise ValueError(
                f"Policy {policy_id} has status '{policy['status']}'; "
                f"only 'approved' policies can run simulations. "
                f"Draft/rejected/archived policies are blocked."
            )

        policy_data = _parse_json(policy.get("policy_json", "{}"))
        risk_limits = _parse_json(policy.get("risk_limits_json", "{}"))
        observe_only = policy_data.get("observe_only", False)

        max_candidates = risk_limits.get(
            "max_candidates_per_run",
            DEFAULT_RISK_LIMITS["max_candidates_per_run"],
        )
        max_position_ratio = risk_limits.get(
            "max_simulated_position_ratio",
            DEFAULT_RISK_LIMITS["max_simulated_position_ratio"],
        )
        skip_missing_price = risk_limits.get(
            "skip_missing_price",
            DEFAULT_RISK_LIMITS["skip_missing_price"],
        )
        skip_high_risk = risk_limits.get(
            "skip_high_risk_unless_observe",
            DEFAULT_RISK_LIMITS["skip_high_risk_unless_observe"],
        )

        # Create the run record
        now = datetime.now().isoformat(timespec="seconds")
        with self.store.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO agent_paper_simulation_runs (
                    policy_id, status, started_at, created_by, created_at
                ) VALUES (?, 'running', ?, ?, ?)
                """,
                (policy_id, now, created_by, now),
            )
            run_id = cursor.lastrowid

        # Fetch candidate scores for simulation
        candidates = self.store.fetch_all(
            """
            SELECT cs.symbol, cs.name, cs.total_score, cs.rating, cs.state,
                   cs.reasons_json, cs.components_json
            FROM candidate_scores cs
            JOIN (
                SELECT symbol, MAX(id) AS latest_id
                FROM candidate_scores
                GROUP BY symbol
            ) latest ON latest.latest_id = cs.id
            ORDER BY cs.total_score DESC
            LIMIT ?
            """,
            (max_candidates,),
        )

        actions: list[dict[str, Any]] = []
        skipped_count = 0
        observe_count = 0
        simulated_entry_count = 0
        simulated_exit_count = 0
        skip_count = 0

        for candidate in candidates:
            symbol = candidate["symbol"]
            score = candidate.get("total_score", 0) or 0
            state = candidate.get("state", "unknown")
            components = _parse_json(candidate.get("components_json", "{}"))
            reasons = _parse_json_list(candidate.get("reasons_json", "[]"))
            simulated_qty: int | None = None

            # Look up latest price from monitoring events or stock profiles
            price_info = self._lookup_price(symbol)
            price = price_info.get("price")
            risk_flags: list[str] = []

            # Check risk conditions
            if price is None and skip_missing_price:
                risk_flags.append("missing_price_data")
                action_type = "skip"
                reason = {
                    "simulation_only": True,
                    "label": "SIMULATED skip - missing price data",
                    "score": score,
                    "state": state,
                }
                skip_count += 1
            elif state in ("rejected", "phase_guarded") and skip_high_risk and not observe_only:
                risk_flags.append(f"high_risk_state:{state}")
                action_type = "skip"
                reason = {
                    "simulation_only": True,
                    "label": f"SIMULATED skip - high risk state ({state})",
                    "score": score,
                    "state": state,
                }
                skip_count += 1
            elif observe_only:
                action_type = "observe"
                reason = {
                    "simulation_only": True,
                    "label": "OBSERVATION ONLY - insufficient evidence policy",
                    "score": score,
                    "state": state,
                    "components": components,
                }
                observe_count += 1
            elif score >= 70 and state in ("focus_watch", "pending_review", "auto_discovered"):
                # Simulate entry for high-score candidates in actionable states
                simulated_qty = 100  # minimum lot
                if price and price > 0:
                    # Check position ratio limit
                    estimated_amount = price * simulated_qty
                    if estimated_amount > max_position_ratio * 100_000:
                        risk_flags.append("exceeds_position_ratio_limit")
                        action_type = "observe"
                        reason = {
                            "simulation_only": True,
                            "label": "SIMULATED observe - exceeds position ratio limit",
                            "score": score,
                            "estimated_amount": estimated_amount,
                            "max_ratio": max_position_ratio,
                        }
                        observe_count += 1
                    else:
                        action_type = "simulated_entry"
                        simulated_qty = 100
                        reason = {
                            "simulation_only": True,
                            "label": "SIMULATED entry - NOT a real order",
                            "score": score,
                            "state": state,
                            "components": components,
                            "reasons": reasons[:3],
                        }
                        simulated_entry_count += 1
                else:
                    action_type = "observe"
                    reason = {
                        "simulation_only": True,
                        "label": "SIMULATED observe - no valid price for entry",
                        "score": score,
                    }
                    observe_count += 1
            elif score < 30 and state == "rejected":
                action_type = "simulated_exit"
                simulated_qty = 100
                reason = {
                    "simulation_only": True,
                    "label": "SIMULATED exit - NOT a real order",
                    "score": score,
                    "state": state,
                }
                simulated_exit_count += 1
            else:
                action_type = "observe"
                reason = {
                    "simulation_only": True,
                    "label": "SIMULATED observe - does not meet entry/exit criteria",
                    "score": score,
                    "state": state,
                }
                observe_count += 1

            # Store the action
            with self.store.connect() as conn:
                conn.execute(
                    """
                    INSERT INTO agent_paper_simulation_actions (
                        run_id, symbol, action_type, reason_json,
                        simulated_price, simulated_quantity,
                        risk_flags_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        symbol,
                        action_type,
                        json.dumps(reason, ensure_ascii=False, default=str),
                        price,
                        simulated_qty,
                        json.dumps(risk_flags, ensure_ascii=False, default=str),
                        now,
                    ),
                )

            actions.append({
                "symbol": symbol,
                "name": candidate.get("name"),
                "action_type": action_type,
                "simulated_price": price,
                "risk_flags": risk_flags,
            })

        # Compute metrics
        metrics = {
            "total_candidates": len(candidates),
            "observe_count": observe_count,
            "simulated_entry_count": simulated_entry_count,
            "simulated_exit_count": simulated_exit_count,
            "skip_count": skip_count,
            "policy_type": policy_data.get("policy_type", "unknown"),
            "observe_only": observe_only,
            "disclaimer": (
                "All actions are SIMULATED. No real orders were placed. "
                "This is not investment advice."
            ),
        }

        # Complete the run
        completed_at = datetime.now().isoformat(timespec="seconds")
        with self.store.connect() as conn:
            conn.execute(
                """
                UPDATE agent_paper_simulation_runs
                SET status = 'completed', completed_at = ?,
                    metrics_json = ?
                WHERE id = ?
                """,
                (
                    completed_at,
                    json.dumps(metrics, ensure_ascii=False, default=str),
                    run_id,
                ),
            )

        return self._load_run(run_id)

    def run_approved_policies(
        self,
        limit: int = 20,
        created_by: str = "system",
    ) -> dict[str, Any]:
        """Run simulations for all approved policies that haven't been run yet."""
        self.store.init()
        limit = max(1, min(int(limit), 200))

        approved = self.store.fetch_all(
            """
            SELECT sp.id
            FROM agent_simulation_policies sp
            LEFT JOIN agent_paper_simulation_runs r
                ON r.policy_id = sp.id AND r.status = 'completed'
            WHERE sp.status = 'approved'
              AND r.id IS NULL
            ORDER BY sp.id
            LIMIT ?
            """,
            (limit,),
        )

        results: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []

        for row in approved:
            try:
                result = self.run_simulation(row["id"], created_by=created_by)
                results.append(result)
            except Exception as exc:
                errors.append({"policy_id": row["id"], "error": str(exc)})

        return {
            "run_count": len(results),
            "error_count": len(errors),
            "runs": results,
            "errors": errors,
        }

    # ------------------------------------------------------------------
    # List / summary
    # ------------------------------------------------------------------

    def list_policies(
        self,
        status: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        self.store.init()
        limit = max(1, min(int(limit), 500))

        if status:
            rows = self.store.fetch_all(
                "SELECT * FROM agent_simulation_policies WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                (status, limit),
            )
        else:
            rows = self.store.fetch_all(
                "SELECT * FROM agent_simulation_policies ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )
        return [self._policy_row_to_dict(r) for r in rows]

    def list_runs(self, limit: int = 50) -> list[dict[str, Any]]:
        self.store.init()
        limit = max(1, min(int(limit), 500))
        rows = self.store.fetch_all(
            "SELECT * FROM agent_paper_simulation_runs ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
        return [self._run_row_to_dict(r) for r in rows]

    def summary(self) -> dict[str, Any]:
        self.store.init()

        policy_total = self.store.fetch_one(
            "SELECT COUNT(*) AS cnt FROM agent_simulation_policies"
        )
        policy_by_status = self.store.fetch_all(
            "SELECT status, COUNT(*) AS cnt FROM agent_simulation_policies GROUP BY status"
        )

        run_total = self.store.fetch_one(
            "SELECT COUNT(*) AS cnt FROM agent_paper_simulation_runs"
        )
        run_by_status = self.store.fetch_all(
            "SELECT status, COUNT(*) AS cnt FROM agent_paper_simulation_runs GROUP BY status"
        )

        action_total = self.store.fetch_one(
            "SELECT COUNT(*) AS cnt FROM agent_paper_simulation_actions"
        )
        action_by_type = self.store.fetch_all(
            "SELECT action_type, COUNT(*) AS cnt FROM agent_paper_simulation_actions GROUP BY action_type"
        )

        # Recent run metrics
        latest_run = self.store.fetch_one(
            """
            SELECT metrics_json FROM agent_paper_simulation_runs
            WHERE status = 'completed'
            ORDER BY completed_at DESC LIMIT 1
            """
        )

        return {
            "policy_count": policy_total["cnt"] if policy_total else 0,
            "policy_by_status": {r["status"]: r["cnt"] for r in policy_by_status},
            "run_count": run_total["cnt"] if run_total else 0,
            "run_by_status": {r["status"]: r["cnt"] for r in run_by_status},
            "action_count": action_total["cnt"] if action_total else 0,
            "action_by_type": {r["action_type"]: r["cnt"] for r in action_by_type},
            "latest_run_metrics": _parse_json(latest_run["metrics_json"]) if latest_run else None,
            "disclaimer": (
                "All simulation data is for analysis purposes only. "
                "No real trading was performed."
            ),
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_policy(self, policy_id: int) -> dict[str, Any]:
        row = self.store.fetch_one(
            "SELECT * FROM agent_simulation_policies WHERE id = ?",
            (policy_id,),
        )
        if not row:
            raise ValueError(f"Simulation policy {policy_id} not found")
        return dict(row)

    def _load_policy(self, policy_id: int) -> dict[str, Any]:
        row = self.store.fetch_one(
            "SELECT * FROM agent_simulation_policies WHERE id = ?",
            (policy_id,),
        )
        if not row:
            raise ValueError(f"Simulation policy {policy_id} not found")
        return self._policy_row_to_dict(row)

    def _load_run(self, run_id: int) -> dict[str, Any]:
        row = self.store.fetch_one(
            "SELECT * FROM agent_paper_simulation_runs WHERE id = ?",
            (run_id,),
        )
        if not row:
            raise ValueError(f"Paper simulation run {run_id} not found")
        result = self._run_row_to_dict(row)

        # Include actions
        actions = self.store.fetch_all(
            "SELECT * FROM agent_paper_simulation_actions WHERE run_id = ? ORDER BY id",
            (run_id,),
        )
        result["actions"] = [self._action_row_to_dict(a) for a in actions]
        return result

    def _policy_row_to_dict(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": row["id"],
            "source_experiment_id": row["source_experiment_id"],
            "policy_type": row["policy_type"],
            "status": row["status"],
            "policy": _parse_json(row.get("policy_json", "{}")),
            "risk_limits": _parse_json(row.get("risk_limits_json", "{}")),
            "created_by": row.get("created_by"),
            "reviewed_by": row.get("reviewed_by"),
            "review_note": row.get("review_note"),
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
            "reviewed_at": row.get("reviewed_at"),
        }

    def _run_row_to_dict(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": row["id"],
            "policy_id": row["policy_id"],
            "status": row["status"],
            "started_at": row.get("started_at"),
            "completed_at": row.get("completed_at"),
            "metrics": _parse_json(row.get("metrics_json", "{}")),
            "created_by": row.get("created_by"),
            "created_at": row.get("created_at"),
        }

    def _action_row_to_dict(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": row["id"],
            "run_id": row["run_id"],
            "symbol": row["symbol"],
            "action_type": row["action_type"],
            "reason": _parse_json(row.get("reason_json", "{}")),
            "simulated_price": row.get("simulated_price"),
            "simulated_quantity": row.get("simulated_quantity"),
            "risk_flags": _parse_json_list(row.get("risk_flags_json", "[]")),
            "created_at": row.get("created_at"),
        }

    def _conclusion_to_policy_type(self, conclusion: str) -> str:
        mapping = {
            "priority_increase_viable": "priority_increase",
            "reduction_justified": "score_reduction",
            "reduction_mixed": "score_reduction_mixed",
            "insufficient_evidence": "observation_only",
        }
        return mapping.get(conclusion, "observation_only")

    def _lookup_price(self, symbol: str) -> dict[str, Any]:
        """Look up latest price from price readiness, monitoring events or stock profiles.

        Degrades gracefully if no price data is found.
        """
        # Try price_readiness_reports first (safest/latest validated price)
        readiness = self.store.fetch_one(
            """
            SELECT latest_price, source, coverage_status FROM price_readiness_reports
            WHERE symbol = ?
              AND latest_price IS NOT NULL
              AND coverage_status IN ('ready', 'insufficient_history')
            ORDER BY updated_at DESC LIMIT 1
            """,
            (symbol,),
        )
        if readiness and readiness.get("latest_price"):
            return {
                "price": readiness["latest_price"],
                "source": f"readiness:{readiness.get('source')}",
                "status": readiness.get("coverage_status")
            }

        # Try monitoring events next (most recent data)
        event = self.store.fetch_one(
            """
            SELECT price, pct_change FROM monitoring_events
            WHERE symbol = ? AND price IS NOT NULL
            ORDER BY created_at DESC LIMIT 1
            """,
            (symbol,),
        )
        if event and event.get("price"):
            return {"price": event["price"], "source": "monitoring_event"}

        # Fall back to stock profiles
        profile = self.store.fetch_one(
            """
            SELECT current_price FROM stock_profiles
            WHERE symbol = ? AND current_price IS NOT NULL
            ORDER BY id DESC LIMIT 1
            """,
            (symbol,),
        )
        if profile and profile.get("current_price"):
            return {"price": profile["current_price"], "source": "stock_profile"}

        return {"price": None, "source": "none"}
