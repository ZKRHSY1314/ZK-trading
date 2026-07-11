from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.storage.sqlite_store import SQLiteStore


FORECAST_HORIZONS = frozenset({1, 3, 5, 10, 20})
FORECAST_SCOPES = frozenset({"sector", "stock", "system"})


class ForecastConflictError(ValueError):
    """Raised when a caller tries to rewrite an immutable ledger identity."""


def _timestamp(value: str | datetime) -> str:
    parsed = value if isinstance(value, datetime) else datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("forecast timestamps must include a timezone")
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _json_copy(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


@dataclass(frozen=True)
class ForecastDecision:
    decision_id: str
    scope: str
    subject: str
    decision_cutoff: str | datetime
    available_at: str | datetime
    horizon_days: int
    rank: int | None
    score: float | None
    probability: float | None
    model_version: str
    prompt_version: str
    data_version: str
    features: dict[str, Any]
    evidence: list[dict[str, Any]]
    reasons: list[str]
    status: str
    review_only: bool = True

    def __post_init__(self) -> None:
        if not self.decision_id.strip() or not self.subject.strip():
            raise ValueError("decision_id and subject are required")
        if self.scope not in FORECAST_SCOPES:
            raise ValueError(f"scope must be one of {sorted(FORECAST_SCOPES)}")
        if self.horizon_days not in FORECAST_HORIZONS:
            raise ValueError(f"horizon_days must be one of {sorted(FORECAST_HORIZONS)}")
        if self.rank is not None and self.rank < 1:
            raise ValueError("rank must be positive")
        if self.probability is not None and not 0.0 <= self.probability <= 1.0:
            raise ValueError("probability must be between 0 and 1")
        if not self.review_only:
            raise ValueError("Forecast Ledger only accepts review-only decisions")

        decision_cutoff = _timestamp(self.decision_cutoff)
        available_at = _timestamp(self.available_at)
        if available_at > decision_cutoff:
            raise ValueError("available_at cannot be after decision_cutoff")
        evidence = _json_copy(self.evidence)
        for item in evidence:
            evidence_available_at = item.get("available_at")
            if evidence_available_at is None:
                continue
            normalized_evidence_time = _timestamp(evidence_available_at)
            if normalized_evidence_time > decision_cutoff:
                raise ValueError("evidence available_at cannot be after decision_cutoff")
            item["available_at"] = normalized_evidence_time
        object.__setattr__(self, "decision_cutoff", decision_cutoff)
        object.__setattr__(self, "available_at", available_at)
        object.__setattr__(self, "features", _json_copy(self.features))
        object.__setattr__(self, "evidence", evidence)
        object.__setattr__(self, "reasons", _json_copy(self.reasons))


@dataclass(frozen=True)
class ForecastOutcome:
    decision_id: str
    scope: str
    subject: str
    horizon_days: int
    observed_at: str | datetime
    continuous_return: float
    benchmark_return: float
    sector_return: float
    data_version: str
    evidence: dict[str, Any]
    status: str = "matured"
    review_only: bool = True
    benchmark_neutral_return: float = field(init=False)
    sector_neutral_return: float = field(init=False)

    def __post_init__(self) -> None:
        if not self.decision_id.strip() or not self.subject.strip():
            raise ValueError("decision_id and subject are required")
        if self.scope not in FORECAST_SCOPES:
            raise ValueError(f"scope must be one of {sorted(FORECAST_SCOPES)}")
        if self.horizon_days not in FORECAST_HORIZONS:
            raise ValueError(f"horizon_days must be one of {sorted(FORECAST_HORIZONS)}")
        returns = (self.continuous_return, self.benchmark_return, self.sector_return)
        if not all(math.isfinite(value) for value in returns):
            raise ValueError("outcome returns must be finite decimal values")
        if not self.data_version.strip():
            raise ValueError("outcome data_version is required")
        if self.status != "matured":
            raise ValueError("Forecast Ledger outcomes must have matured status")
        if not self.review_only:
            raise ValueError("Forecast Ledger only accepts review-only outcomes")

        object.__setattr__(self, "observed_at", _timestamp(self.observed_at))
        object.__setattr__(self, "evidence", _json_copy(self.evidence))
        object.__setattr__(
            self,
            "benchmark_neutral_return",
            self.continuous_return - self.benchmark_return,
        )
        object.__setattr__(
            self,
            "sector_neutral_return",
            self.continuous_return - self.sector_return,
        )


@dataclass(frozen=True)
class MaturedForecast:
    forecast: ForecastDecision
    outcome: ForecastOutcome


class ForecastLedger:
    """Immutable, review-only point-in-time forecast ledger."""

    def __init__(self, store: SQLiteStore) -> None:
        self.store = store
        self.store.init()

    def record_forecast(self, forecast: ForecastDecision) -> ForecastDecision:
        with self.store.connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO forecast_decisions(
                    decision_id, scope, subject, decision_cutoff, available_at,
                    horizon_days, rank, score, probability, model_version,
                    prompt_version, data_version, features_json, evidence_json,
                    reasons_json, status, review_only
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                """,
                self._forecast_values(forecast),
            )
            row = conn.execute(
                """
                SELECT * FROM forecast_decisions
                WHERE decision_id = ? AND scope = ? AND subject = ? AND horizon_days = ?
                """,
                (forecast.decision_id, forecast.scope, forecast.subject, forecast.horizon_days),
            ).fetchone()
        persisted = self._forecast_from_row(dict(row))
        if persisted != forecast:
            raise ForecastConflictError(
                "forecast identity is immutable; use a new decision_id for changed evidence"
            )
        return persisted

    def record_outcome(self, outcome: ForecastOutcome) -> ForecastOutcome:
        identity = (outcome.decision_id, outcome.scope, outcome.subject, outcome.horizon_days)
        with self.store.connect() as conn:
            forecast_row = conn.execute(
                """
                SELECT * FROM forecast_decisions
                WHERE decision_id = ? AND scope = ? AND subject = ? AND horizon_days = ?
                """,
                identity,
            ).fetchone()
            if forecast_row is None:
                raise ValueError("outcome requires a matching immutable forecast")
            if outcome.observed_at < forecast_row["decision_cutoff"]:
                raise ValueError("observed_at cannot be before decision_cutoff")
            conn.execute(
                """
                INSERT OR IGNORE INTO forecast_outcomes(
                    decision_id, scope, subject, horizon_days, observed_at,
                    continuous_return, benchmark_return, sector_return,
                    benchmark_neutral_return, sector_neutral_return, data_version,
                    evidence_json, status, review_only
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                """,
                self._outcome_values(outcome),
            )
            row = conn.execute(
                """
                SELECT * FROM forecast_outcomes
                WHERE decision_id = ? AND scope = ? AND subject = ? AND horizon_days = ?
                """,
                identity,
            ).fetchone()
        persisted = self._outcome_from_row(dict(row))
        if persisted != outcome:
            raise ForecastConflictError(
                "outcome identity is immutable; changed labels require a new decision_id"
            )
        return persisted

    def latest(
        self,
        *,
        scope: str | None = None,
        subject: str | None = None,
        horizon_days: int | None = None,
    ) -> list[ForecastDecision]:
        conditions, params = self._filters(scope, subject, horizon_days)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        anchor = self.store.fetch_one(
            f"""
            SELECT decision_id
            FROM forecast_decisions
            {where}
            ORDER BY decision_cutoff DESC, available_at DESC, id DESC
            LIMIT 1
            """,
            tuple(params),
        )
        if anchor is None:
            return []
        conditions.append("decision_id = ?")
        params.append(anchor["decision_id"])
        rows = self.store.fetch_all(
            f"""
            SELECT * FROM forecast_decisions
            WHERE {' AND '.join(conditions)}
            ORDER BY scope, rank IS NULL, rank, subject, horizon_days
            """,
            tuple(params),
        )
        return [self._forecast_from_row(row) for row in rows]

    def as_of(
        self,
        cutoff: str | datetime,
        *,
        scope: str | None = None,
        subject: str | None = None,
        horizon_days: int | None = None,
    ) -> list[ForecastDecision]:
        normalized_cutoff = _timestamp(cutoff)
        conditions, params = self._filters(scope, subject, horizon_days)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        anchor = self.store.fetch_one(
            f"""
            SELECT decision_id, MAX(decision_cutoff) AS snapshot_cutoff
            FROM forecast_decisions
            {where}
            GROUP BY decision_id
            HAVING MAX(decision_cutoff) <= ? AND MAX(available_at) <= ?
            ORDER BY snapshot_cutoff DESC, decision_id DESC
            LIMIT 1
            """,
            tuple([*params, normalized_cutoff, normalized_cutoff]),
        )
        if anchor is None:
            return []
        conditions.append("decision_id = ?")
        params.append(anchor["decision_id"])
        rows = self.store.fetch_all(
            f"""
            SELECT * FROM forecast_decisions
            WHERE {' AND '.join(conditions)}
              AND decision_cutoff <= ? AND available_at <= ?
            ORDER BY scope, rank IS NULL, rank, subject, horizon_days
            """,
            tuple([*params, normalized_cutoff, normalized_cutoff]),
        )
        return [self._forecast_from_row(row) for row in rows]

    def matured(
        self,
        as_of: str | datetime,
        *,
        scope: str | None = None,
        subject: str | None = None,
        horizon_days: int | None = None,
    ) -> list[MaturedForecast]:
        cutoff = _timestamp(as_of)
        conditions = ["o.status = 'matured'", "o.observed_at <= ?"]
        params: list[Any] = [cutoff]
        for column, value in (("scope", scope), ("subject", subject), ("horizon_days", horizon_days)):
            if value is not None:
                conditions.append(f"d.{column} = ?")
                params.append(value)
        rows = self.store.fetch_all(
            f"""
            SELECT
                d.*,
                o.observed_at AS outcome_observed_at,
                o.continuous_return AS outcome_continuous_return,
                o.benchmark_return AS outcome_benchmark_return,
                o.sector_return AS outcome_sector_return,
                o.data_version AS outcome_data_version,
                o.evidence_json AS outcome_evidence_json,
                o.status AS outcome_status,
                o.review_only AS outcome_review_only
            FROM forecast_decisions d
            JOIN forecast_outcomes o
              ON o.decision_id = d.decision_id
             AND o.scope = d.scope
             AND o.subject = d.subject
             AND o.horizon_days = d.horizon_days
            WHERE {' AND '.join(conditions)}
            ORDER BY d.decision_cutoff ASC, d.decision_id, d.scope, d.subject, d.horizon_days
            """,
            tuple(params),
        )
        return [
            MaturedForecast(
                forecast=self._forecast_from_row(row),
                outcome=ForecastOutcome(
                    decision_id=row["decision_id"],
                    scope=row["scope"],
                    subject=row["subject"],
                    horizon_days=int(row["horizon_days"]),
                    observed_at=row["outcome_observed_at"],
                    continuous_return=row["outcome_continuous_return"],
                    benchmark_return=row["outcome_benchmark_return"],
                    sector_return=row["outcome_sector_return"],
                    data_version=row["outcome_data_version"],
                    evidence=json.loads(row["outcome_evidence_json"]),
                    status=row["outcome_status"],
                    review_only=bool(row["outcome_review_only"]),
                ),
            )
            for row in rows
        ]

    def _filters(
        self,
        scope: str | None,
        subject: str | None,
        horizon_days: int | None,
    ) -> tuple[list[str], list[Any]]:
        conditions: list[str] = []
        params: list[Any] = []
        for column, value in (("scope", scope), ("subject", subject), ("horizon_days", horizon_days)):
            if value is not None:
                conditions.append(f"{column} = ?")
                params.append(value)
        return conditions, params

    def _forecast_values(self, forecast: ForecastDecision) -> tuple[Any, ...]:
        return (
            forecast.decision_id,
            forecast.scope,
            forecast.subject,
            forecast.decision_cutoff,
            forecast.available_at,
            forecast.horizon_days,
            forecast.rank,
            forecast.score,
            forecast.probability,
            forecast.model_version,
            forecast.prompt_version,
            forecast.data_version,
            json.dumps(forecast.features, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            json.dumps(forecast.evidence, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            json.dumps(forecast.reasons, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            forecast.status,
        )

    def _outcome_values(self, outcome: ForecastOutcome) -> tuple[Any, ...]:
        return (
            outcome.decision_id,
            outcome.scope,
            outcome.subject,
            outcome.horizon_days,
            outcome.observed_at,
            outcome.continuous_return,
            outcome.benchmark_return,
            outcome.sector_return,
            outcome.benchmark_neutral_return,
            outcome.sector_neutral_return,
            outcome.data_version,
            json.dumps(outcome.evidence, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            outcome.status,
        )

    def _outcome_from_row(self, row: dict[str, Any]) -> ForecastOutcome:
        return ForecastOutcome(
            decision_id=row["decision_id"],
            scope=row["scope"],
            subject=row["subject"],
            horizon_days=int(row["horizon_days"]),
            observed_at=row["observed_at"],
            continuous_return=row["continuous_return"],
            benchmark_return=row["benchmark_return"],
            sector_return=row["sector_return"],
            data_version=row["data_version"],
            evidence=json.loads(row["evidence_json"]),
            status=row["status"],
            review_only=bool(row["review_only"]),
        )

    def _forecast_from_row(self, row: dict[str, Any]) -> ForecastDecision:
        return ForecastDecision(
            decision_id=row["decision_id"],
            scope=row["scope"],
            subject=row["subject"],
            decision_cutoff=row["decision_cutoff"],
            available_at=row["available_at"],
            horizon_days=int(row["horizon_days"]),
            rank=row["rank"],
            score=row["score"],
            probability=row["probability"],
            model_version=row["model_version"],
            prompt_version=row["prompt_version"],
            data_version=row["data_version"],
            features=json.loads(row["features_json"]),
            evidence=json.loads(row["evidence_json"]),
            reasons=json.loads(row["reasons_json"]),
            status=row["status"],
            review_only=bool(row["review_only"]),
        )
