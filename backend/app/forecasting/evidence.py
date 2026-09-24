"""Canonical forecast evidence: the one read model behind the scoreboard and calibration.

Everything here reads through ``ForecastFeedback.evaluate`` and the canonical
snapshot selector, so the scoreboard, stored evaluations and calibration
proposals describe the same sample. Three things are kept apart on purpose:

* **Runtime availability** - whether the evidence could be computed and shown.
  Read-only diagnostics stay available whatever the numbers say.
* **Evidence status** - per scope and horizon: ready / insufficient_data /
  degraded (exploratory), with the reasons.
* **Strategy-evidence eligibility** - whether a horizon's evidence may support a
  positive strategy statement. Unknown, non-positive or thin evidence is never
  eligible; missing evidence is never read as zero, and stored evaluations from
  an older or unrecorded canonical policy are never current evidence.

The eligibility thresholds below are predeclared evidence-sufficiency rules,
not tuned trading parameters. Changing them requires a new policy version.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.forecasting.canonical import (
    CANONICAL_POLICY_VERSION,
    SELECTION_CONFIRMED,
    SELECTION_INFERRED,
    canonical_join,
    canonical_snapshot_cte,
)
from app.forecasting.feedback import MATURITY_BASIS, ForecastFeedback, _datetime, _decision_date

EVIDENCE_POLICY_VERSION = "forecast_evidence_policy.v1"
EVIDENCE_POLICY: dict[str, Any] = {
    "version": EVIDENCE_POLICY_VERSION,
    "canonical_policy_version": CANONICAL_POLICY_VERSION,
    "fold_unit": "decision_date",
    "min_independent_decision_dates": 20,
    "min_coverage_of_due": 0.8,
    "require_official_evidence": True,
    "require_ready_status": True,
    "require_positive_rank_ic": True,
}

# Fields surfaced per horizon; everything else stays in the full evaluation.
_HORIZON_FIELDS = (
    "status",
    "evidence_quality",
    "canonical_policy_version",
    "fold_unit",
    "fold_count",
    "canonical_snapshot_count",
    "repeated_snapshot_date_count",
    "confirmed_fold_count",
    "inferred_fold_count",
    "excluded_inferred_snapshot_count",
    "forecast_count",
    "sample_count",
    "directional_forecast_count",
    "directional_sample_count",
    "due_count",
    "matured_due_count",
    "pending_count",
    "coverage",
    "coverage_denominator",
    "coverage_of_due",
    "maturity_basis",
    "spearman_rank_ic",
    "rank_ic_fold_count",
    "precision_at_k",
    "precision_fold_count",
    "brier_score",
    "probability_calibration_status",
    "aggregation",
    "insufficient_reasons",
)


def strategy_evidence_eligibility(
    metrics: dict[str, Any], *, policy: dict[str, Any] = EVIDENCE_POLICY
) -> dict[str, Any]:
    """Can this horizon's evidence support a positive strategy statement?

    Fails closed on anything absent: metrics that predate the decision-date fold
    unit, the maturity fields or the policy version are ineligible, not assumed.
    """

    reasons: list[str] = []
    if metrics.get("canonical_policy_version") != policy["canonical_policy_version"]:
        reasons.append("canonical_policy_version_not_current")
    if policy["require_official_evidence"] and metrics.get("evidence_quality") != "official":
        reasons.append("evidence_not_official")
    status = str(metrics.get("status") or "unknown")
    if policy["require_ready_status"] and status != "ready":
        reasons.append(f"evaluation_status_{status}")
    dates = metrics.get("fold_count") if metrics.get("fold_unit") == policy["fold_unit"] else None
    minimum_dates = int(policy["min_independent_decision_dates"])
    if dates is None:
        reasons.append("independent_decision_dates_unknown")
    elif int(dates) < minimum_dates:
        reasons.append(f"independent_decision_dates_below_{minimum_dates}")
    coverage = metrics.get("coverage_of_due")
    minimum_coverage = float(policy["min_coverage_of_due"])
    if coverage is None:
        reasons.append("no_due_forecasts")
    elif float(coverage) < minimum_coverage:
        reasons.append(f"coverage_of_due_below_{minimum_coverage:g}")
    rank_ic = metrics.get("spearman_rank_ic")
    if policy["require_positive_rank_ic"]:
        if rank_ic is None:
            reasons.append("rank_ic_unknown")
        elif float(rank_ic) <= 0:
            reasons.append("rank_ic_not_positive")
    return {
        "eligible": not reasons,
        "reasons": reasons,
        "policy_version": policy["version"],
    }


class ForecastEvidenceService:
    """Read-only evidence summary. It evaluates; it never labels or persists."""

    def __init__(self, store, *, feedback: ForecastFeedback | None = None) -> None:
        self.store = store
        self.feedback = feedback or ForecastFeedback(store)

    def summary(
        self,
        as_of: str | datetime | None = None,
        *,
        include_inferred: bool = False,
    ) -> dict[str, Any]:
        cutoff = _datetime(as_of or datetime.now(timezone.utc))
        cutoff_text = cutoff.isoformat().replace("+00:00", "Z")
        evaluation = self.feedback.evaluate(cutoff, include_inferred=include_inferred)
        by_scope: dict[str, Any] = {}
        qualified: list[str] = []
        for scope in ("stock", "sector"):
            payload = (evaluation.get("by_scope") or {}).get(scope) or {}
            horizons = []
            for metrics in payload.get("horizons") or []:
                eligibility = strategy_evidence_eligibility(metrics)
                if eligibility["eligible"]:
                    qualified.append(f"{scope}:{metrics.get('horizon_days')}d")
                horizons.append(
                    {
                        "horizon_days": metrics.get("horizon_days"),
                        **{field: metrics.get(field) for field in _HORIZON_FIELDS},
                        "strategy_evidence": eligibility,
                    }
                )
            by_scope[scope] = {
                "status": payload.get("status"),
                "evidence_quality": payload.get("evidence_quality"),
                "target": payload.get("target"),
                "selection": self._selection_inventory(scope, cutoff_text),
                "horizons": horizons,
            }
        return {
            "schema_version": "forecast_evidence.v1",
            "as_of": cutoff_text,
            "canonical_policy_version": CANONICAL_POLICY_VERSION,
            "evidence_policy": dict(EVIDENCE_POLICY),
            "include_inferred": include_inferred,
            "evidence_quality": evaluation.get("evidence_quality"),
            "evidence_status": evaluation.get("status"),
            # Computing and showing evidence does not depend on how good it is.
            "runtime": {"status": "available", "read_only": True},
            "strategy_evidence": {
                "qualified": bool(qualified),
                "qualified_horizons": qualified,
                "policy_version": EVIDENCE_POLICY_VERSION,
            },
            "maturity_basis": MATURITY_BASIS,
            "by_scope": by_scope,
            "stored_evaluations": self._stored_evaluations(),
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": False,
        }

    def _selection_inventory(self, scope: str, cutoff: str) -> dict[str, Any]:
        """What the canonical selector kept and left out, as of the cutoff."""

        raw = self.store.fetch_one(
            """
            SELECT COUNT(DISTINCT decision_id) AS decision_ids, COUNT(*) AS row_count
            FROM forecast_decisions
            WHERE scope = ? AND review_only = 1
              AND decision_cutoff <= ? AND available_at <= ?
            """,
            (scope, cutoff, cutoff),
        ) or {}
        canonical_rows = self.store.fetch_all(
            f"""
            WITH {canonical_snapshot_cte()}
            SELECT d.decision_id, cs.selection_kind, MIN(d.decision_cutoff) AS decision_cutoff
            FROM forecast_decisions d
            {canonical_join("d")}
            WHERE d.scope = ? AND d.review_only = 1
              AND d.decision_cutoff <= ? AND d.available_at <= ?
            GROUP BY d.decision_id, cs.selection_kind
            """,
            (scope, cutoff, cutoff),
        )
        claims = self.store.fetch_one(
            """
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN recorded_count = 0 THEN 1 ELSE 0 END) AS open_claims,
                SUM(CASE WHEN run_kind <> 'scheduled' THEN 1 ELSE 0 END) AS non_scheduled_claims
            FROM forecast_decision_days
            WHERE scope = ?
            """,
            (scope,),
        ) or {}
        confirmed = [row for row in canonical_rows if row["selection_kind"] == SELECTION_CONFIRMED]
        inferred = [row for row in canonical_rows if row["selection_kind"] == SELECTION_INFERRED]
        raw_ids = int(raw.get("decision_ids") or 0)
        return {
            "raw_decision_id_count": raw_ids,
            "raw_row_count": int(raw.get("row_count") or 0),
            "confirmed_snapshot_count": len(confirmed),
            "inferred_snapshot_count": len(inferred),
            # Duplicates, orphans, and snapshots of vintages whose claim is open,
            # mismatched or non-scheduled: kept on disk, excluded on read.
            "non_canonical_decision_id_count": raw_ids - len(confirmed) - len(inferred),
            "confirmed_decision_date_count": len(
                {_decision_date(row["decision_cutoff"]) for row in confirmed}
            ),
            "inferred_decision_date_count": len(
                {_decision_date(row["decision_cutoff"]) for row in inferred}
            ),
            "claims": {
                "total": int(claims.get("total") or 0),
                "open": int(claims.get("open_claims") or 0),
                "non_scheduled": int(claims.get("non_scheduled_claims") or 0),
                "as_of_filtered": False,
            },
        }

    def _stored_evaluations(self) -> dict[str, Any]:
        """Persisted evaluations by canonical policy; only the current one is current."""

        rows = self.store.fetch_all(
            """
            SELECT canonical_policy_version AS policy_version,
                   COUNT(*) AS row_count,
                   SUM(CASE WHEN status = 'ready' THEN 1 ELSE 0 END) AS ready_count,
                   MAX(as_of) AS latest_as_of
            FROM forecast_evaluations
            GROUP BY canonical_policy_version
            ORDER BY canonical_policy_version
            """
        )
        groups = []
        for row in rows:
            version = row["policy_version"]
            groups.append(
                {
                    "canonical_policy_version": version,
                    "qualification": (
                        "current_policy"
                        if version == CANONICAL_POLICY_VERSION
                        else "legacy_unversioned" if version is None else "other_policy"
                    ),
                    "row_count": int(row["row_count"] or 0),
                    "ready_count": int(row["ready_count"] or 0),
                    "latest_as_of": row["latest_as_of"],
                }
            )
        return {
            "groups": groups,
            # A "ready" row computed without a recorded or current policy is a
            # historical record, never current qualified evidence.
            "legacy_ready_count": sum(
                group["ready_count"] for group in groups
                if group["qualification"] != "current_policy"
            ),
        }
