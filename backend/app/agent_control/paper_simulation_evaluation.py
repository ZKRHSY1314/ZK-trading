"""Paper simulation outcome evaluation service.

Evaluates paper simulation actions against subsequent market data
to determine if the simulation policy is effective.

Safety:
- Evaluation only, does not mutate production candidate scores, rules, or settings.
- Only uses local historical/monitoring data.
- Does not call external broker APIs.
- Clearly labels all results as "simulation_only".
"""

import json
from datetime import datetime, timedelta
from typing import Any

from app.config import settings
from app.storage.sqlite_store import SQLiteStore

# Thresholds for evaluating returns
STRONG_FOLLOW_THROUGH_THRESH = 3.0
MILD_FOLLOW_THROUGH_THRESH = 1.0
FAILURE_THRESH = -3.0
LARGE_DRAWDOWN_THRESH = -4.0


def _parse_json(raw: Any) -> dict[str, Any]:
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}


class PaperSimulationEvaluationService:
    def __init__(self) -> None:
        self.store = SQLiteStore(settings.database_path)

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    def evaluate_recent(self, limit: int = 100, horizon_days: int = 5) -> dict[str, Any]:
        """Evaluate recent actions from completed paper simulation runs."""
        self.store.init()
        limit = max(1, min(int(limit), 500))
        horizon_days = self._clamp_horizon_days(horizon_days)

        # Find actions from completed runs that haven't been evaluated for this horizon
        # or are stuck in pending_future_data.
        actions = self.store.fetch_all(
            """
            SELECT a.id as action_id, a.run_id, a.symbol, a.action_type,
                   a.simulated_price, a.created_at,
                   r.policy_id
            FROM agent_paper_simulation_actions a
            JOIN agent_paper_simulation_runs r ON r.id = a.run_id
            LEFT JOIN agent_paper_simulation_evaluations e
                ON e.action_id = a.id AND e.horizon_days = ?
            WHERE r.status = 'completed'
              AND (e.id IS NULL OR e.status = 'pending_future_data')
            ORDER BY a.id DESC
            LIMIT ?
            """,
            (horizon_days, limit),
        )

        results = []
        for act in actions:
            try:
                res = self.evaluate_action(act, horizon_days)
                results.append(res)
            except Exception as e:
                # Store error evaluation
                res = self._store_evaluation(
                    action_id=act["action_id"],
                    run_id=act["run_id"],
                    policy_id=act["policy_id"],
                    symbol=act["symbol"],
                    horizon_days=horizon_days,
                    status="error",
                    metrics_json={"error": str(e)},
                )
                results.append(res)

        return {
            "evaluated_count": len(results),
            "results": results,
            "horizon_days": horizon_days,
        }

    def evaluate_run(self, run_id: int, horizon_days: int = 5) -> dict[str, Any]:
        """Evaluate all actions in a specific paper simulation run."""
        self.store.init()
        horizon_days = self._clamp_horizon_days(horizon_days)

        actions = self.store.fetch_all(
            """
            SELECT a.id as action_id, a.run_id, a.symbol, a.action_type,
                   a.simulated_price, a.created_at,
                   r.policy_id
            FROM agent_paper_simulation_actions a
            JOIN agent_paper_simulation_runs r ON r.id = a.run_id
            WHERE a.run_id = ?
            """,
            (run_id,),
        )

        results = []
        for act in actions:
            try:
                res = self.evaluate_action(act, horizon_days)
                results.append(res)
            except Exception as e:
                res = self._store_evaluation(
                    action_id=act["action_id"],
                    run_id=act["run_id"],
                    policy_id=act["policy_id"],
                    symbol=act["symbol"],
                    horizon_days=horizon_days,
                    status="error",
                    metrics_json={"error": str(e)},
                )
                results.append(res)

        return {
            "evaluated_count": len(results),
            "results": results,
            "horizon_days": horizon_days,
            "run_id": run_id,
        }

    def evaluate_action(self, action_row: dict[str, Any], horizon_days: int) -> dict[str, Any]:
        """Evaluate a single paper simulation action."""
        horizon_days = self._clamp_horizon_days(horizon_days)
        action_id = action_row["action_id"]
        run_id = action_row["run_id"]
        policy_id = action_row["policy_id"]
        symbol = action_row["symbol"]
        action_type = action_row["action_type"]
        entry_price = action_row.get("simulated_price")
        created_at_str = action_row["created_at"]

        if not entry_price:
            # If no price was simulated (e.g., skip due to missing price)
            return self._store_evaluation(
                action_id=action_id,
                run_id=run_id,
                policy_id=policy_id,
                symbol=symbol,
                horizon_days=horizon_days,
                status="skipped_no_price",
                metrics_json={"action_type": action_type},
            )

        # Look for future data
        try:
            created_at = datetime.fromisoformat(created_at_str)
        except ValueError:
            created_at = datetime.now()

        horizon_date = created_at + timedelta(days=horizon_days)

        # Look up cached daily bars after the action date and up to the horizon.
        # Excluding the action date avoids using same-day close data for intraday actions.
        first_future_date = (created_at + timedelta(days=1)).date().isoformat()
        profiles = self.store.fetch_all(
            """
            SELECT close as current_price, trade_date || 'T00:00:00' as created_at
            FROM daily_bar_cache
            WHERE symbol = ?
              AND trade_date >= ?
              AND trade_date <= ?
              AND trade_date != 'ERROR'
            ORDER BY trade_date ASC
            """,
            (symbol, first_future_date, horizon_date.date().isoformat()),
        )

        if not profiles:
            # No future data found
            # Check if we're still waiting for horizon_date
            if datetime.now() < horizon_date:
                status = "pending_future_data"
            else:
                status = "pending_future_data"  # even if time passed, we lack the data
            return self._store_evaluation(
                action_id=action_id,
                run_id=run_id,
                policy_id=policy_id,
                symbol=symbol,
                horizon_days=horizon_days,
                status=status,
                entry_price=entry_price,
                metrics_json={
                    "action_type": action_type,
                    "reason": "No daily bar cache rows found in future horizon",
                },
            )

        prices = [p["current_price"] for p in profiles if p["current_price"] is not None]
        if not prices:
            return self._store_evaluation(
                action_id=action_id,
                run_id=run_id,
                policy_id=policy_id,
                symbol=symbol,
                horizon_days=horizon_days,
                status="pending_future_data",
                entry_price=entry_price,
                metrics_json={
                    "action_type": action_type,
                    "reason": "No valid close prices in daily bar cache horizon",
                },
            )

        max_price = max(prices)
        min_price = min(prices)
        close_price = prices[-1]

        max_ret = (max_price - entry_price) / entry_price * 100.0
        min_ret = (min_price - entry_price) / entry_price * 100.0
        close_ret = (close_price - entry_price) / entry_price * 100.0

        # Assign outcome labels
        outcome_label = self._determine_outcome_label(max_ret, close_ret)
        risk_outcome = self._determine_risk_outcome(min_ret)

        return self._store_evaluation(
            action_id=action_id,
            run_id=run_id,
            policy_id=policy_id,
            symbol=symbol,
            horizon_days=horizon_days,
            status="completed",
            entry_price=entry_price,
            future_price=close_price,
            max_return_pct=max_ret,
            min_return_pct=min_ret,
            close_return_pct=close_ret,
            outcome_label=outcome_label,
            risk_outcome=risk_outcome,
            metrics_json={
                "action_type": action_type,
                "data_points": len(prices),
                "simulation_only": True,
            },
        )

    def _determine_outcome_label(self, max_ret: float, close_ret: float) -> str:
        if max_ret >= STRONG_FOLLOW_THROUGH_THRESH:
            return "strong_follow_through"
        if max_ret >= MILD_FOLLOW_THROUGH_THRESH:
            return "mild_follow_through"
        if max_ret < FAILURE_THRESH or close_ret < FAILURE_THRESH:
            return "failed_signal"
        return "flat_or_noise"

    def _determine_risk_outcome(self, min_ret: float) -> str:
        if min_ret <= LARGE_DRAWDOWN_THRESH:
            return "large_drawdown"
        if min_ret < 0:
            return "normal_drawdown"
        return "low_drawdown"

    def _clamp_horizon_days(self, horizon_days: int) -> int:
        return max(1, min(int(horizon_days), 60))

    def _store_evaluation(
        self,
        action_id: int,
        run_id: int,
        policy_id: int,
        symbol: str,
        horizon_days: int,
        status: str,
        entry_price: float | None = None,
        future_price: float | None = None,
        max_return_pct: float | None = None,
        min_return_pct: float | None = None,
        close_return_pct: float | None = None,
        outcome_label: str | None = None,
        risk_outcome: str | None = None,
        metrics_json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Upsert evaluation record."""
        now = datetime.now().isoformat(timespec="seconds")
        metrics = metrics_json or {}

        with self.store.connect() as conn:
            # Check if exists
            existing = conn.execute(
                "SELECT id FROM agent_paper_simulation_evaluations WHERE action_id = ? AND horizon_days = ?",
                (action_id, horizon_days)
            ).fetchone()

            if existing:
                eval_id = existing["id"]
                conn.execute(
                    """
                    UPDATE agent_paper_simulation_evaluations
                    SET status = ?, entry_price = ?, future_price = ?,
                        max_return_pct = ?, min_return_pct = ?, close_return_pct = ?,
                        outcome_label = ?, risk_outcome = ?, metrics_json = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        status, entry_price, future_price,
                        max_return_pct, min_return_pct, close_return_pct,
                        outcome_label, risk_outcome,
                        json.dumps(metrics, ensure_ascii=False, default=str),
                        now, eval_id
                    )
                )
            else:
                cursor = conn.execute(
                    """
                    INSERT INTO agent_paper_simulation_evaluations (
                        run_id, action_id, policy_id, symbol, horizon_days,
                        status, entry_price, future_price,
                        max_return_pct, min_return_pct, close_return_pct,
                        outcome_label, risk_outcome, metrics_json,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id, action_id, policy_id, symbol, horizon_days,
                        status, entry_price, future_price,
                        max_return_pct, min_return_pct, close_return_pct,
                        outcome_label, risk_outcome,
                        json.dumps(metrics, ensure_ascii=False, default=str),
                        now, now
                    )
                )
                eval_id = cursor.lastrowid

        return self._get_evaluation(eval_id)

    def _get_evaluation(self, eval_id: int) -> dict[str, Any]:
        row = self.store.fetch_one(
            "SELECT * FROM agent_paper_simulation_evaluations WHERE id = ?",
            (eval_id,)
        )
        if not row:
            raise ValueError(f"Evaluation {eval_id} not found")
        return self._row_to_dict(row)

    def _row_to_dict(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": row["id"],
            "run_id": row["run_id"],
            "action_id": row["action_id"],
            "policy_id": row["policy_id"],
            "symbol": row["symbol"],
            "horizon_days": row["horizon_days"],
            "status": row["status"],
            "entry_price": row.get("entry_price"),
            "future_price": row.get("future_price"),
            "max_return_pct": row.get("max_return_pct"),
            "min_return_pct": row.get("min_return_pct"),
            "close_return_pct": row.get("close_return_pct"),
            "outcome_label": row.get("outcome_label"),
            "risk_outcome": row.get("risk_outcome"),
            "metrics": _parse_json(row.get("metrics_json", "{}")),
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
        }

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def list_evaluations(self, limit: int = 100) -> list[dict[str, Any]]:
        self.store.init()
        limit = max(1, min(int(limit), 500))
        rows = self.store.fetch_all(
            "SELECT * FROM agent_paper_simulation_evaluations ORDER BY updated_at DESC LIMIT ?",
            (limit,)
        )
        return [self._row_to_dict(r) for r in rows]

    def summary(self) -> dict[str, Any]:
        self.store.init()
        total = self.store.fetch_one("SELECT COUNT(*) AS cnt FROM agent_paper_simulation_evaluations")
        by_status = self.store.fetch_all(
            "SELECT status, COUNT(*) AS cnt FROM agent_paper_simulation_evaluations GROUP BY status"
        )
        by_label = self.store.fetch_all(
            "SELECT outcome_label, COUNT(*) AS cnt FROM agent_paper_simulation_evaluations WHERE outcome_label IS NOT NULL GROUP BY outcome_label"
        )
        by_risk = self.store.fetch_all(
            "SELECT risk_outcome, COUNT(*) AS cnt FROM agent_paper_simulation_evaluations WHERE risk_outcome IS NOT NULL GROUP BY risk_outcome"
        )

        return {
            "total_evaluations": total["cnt"] if total else 0,
            "by_status": {r["status"]: r["cnt"] for r in by_status},
            "by_outcome_label": {r["outcome_label"]: r["cnt"] for r in by_label},
            "by_risk_outcome": {r["risk_outcome"]: r["cnt"] for r in by_risk},
            "disclaimer": "Evaluations are for SIMULATED actions only.",
        }

    def policy_summary(self) -> list[dict[str, Any]]:
        """Summarize evaluation results grouped by policy."""
        self.store.init()

        policies = self.store.fetch_all(
            "SELECT id, policy_type, status FROM agent_simulation_policies WHERE status = 'approved'"
        )

        results = []
        for p in policies:
            pid = p["id"]
            evals = self.store.fetch_all(
                "SELECT * FROM agent_paper_simulation_evaluations WHERE policy_id = ?",
                (pid,)
            )

            total = len(evals)
            if total == 0:
                continue

            completed = sum(1 for e in evals if e["status"] == "completed")
            pending = sum(1 for e in evals if e["status"] == "pending_future_data")
            skipped = sum(1 for e in evals if e["status"] == "skipped_no_price")
            errors = sum(1 for e in evals if e["status"] == "error")

            strong = sum(1 for e in evals if e["outcome_label"] == "strong_follow_through")
            mild = sum(1 for e in evals if e["outcome_label"] == "mild_follow_through")
            failed = sum(1 for e in evals if e["outcome_label"] == "failed_signal")
            large_drawdowns = sum(1 for e in evals if e["risk_outcome"] == "large_drawdown")

            # Determine a conservative conclusion
            if completed == 0:
                conclusion = "pending_future_data" if pending > 0 else "insufficient_price_data"
            else:
                positive_ratio = (strong + mild) / completed
                if positive_ratio > 0.5 and large_drawdowns == 0:
                    conclusion = "promising_simulation_policy"
                elif failed > completed * 0.3 or large_drawdowns > 0:
                    conclusion = "weak_simulation_policy"
                else:
                    conclusion = "mixed_or_unproven_policy"

            results.append({
                "policy_id": pid,
                "policy_type": p["policy_type"],
                "total_evaluations": total,
                "completed": completed,
                "pending_future_data": pending,
                "skipped_no_price": skipped,
                "errors": errors,
                "strong_follow_through": strong,
                "mild_follow_through": mild,
                "failed_signal": failed,
                "large_drawdowns": large_drawdowns,
                "conclusion": conclusion,
                "disclaimer": "Simulation only. Not investment advice.",
            })

        return results
