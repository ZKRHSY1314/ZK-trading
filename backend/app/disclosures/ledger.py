from __future__ import annotations

import json
import math
import sqlite3
from dataclasses import dataclass, replace
from datetime import date, datetime, timezone
from typing import Any

from app.storage.sqlite_store import SQLiteStore


SUPPORTED_DISCLOSURE_FACT_TYPES = frozenset(
    {
        "balance_sheet",
        "income_statement",
        "cash_flow_statement",
        "earnings_forecast",
        "share_buyback",
        "shareholder_reduction",
        "share_unlock",
        "private_placement",
        "major_contract",
    }
)


class DisclosureConflictError(ValueError):
    """Raised when an immutable disclosure revision is rewritten."""


def _timestamp(value: str | datetime) -> str:
    parsed = value if isinstance(value, datetime) else datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("disclosure timestamps must include a timezone")
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _json_copy(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


@dataclass(frozen=True)
class DisclosureFact:
    fact_id: str
    symbol: str
    fact_type: str
    period_end: str | date | None
    published_at: str | datetime
    first_seen_at: str | datetime
    retrieved_at: str | datetime
    available_at: str | datetime
    source_tier: str
    source_url: str
    raw_hash: str
    revision: int
    metrics: dict[str, Any]
    evidence: list[dict[str, Any]]
    review_only: bool = True

    def __post_init__(self) -> None:
        if not self.fact_id.strip() or not self.symbol.strip():
            raise ValueError("fact_id and symbol are required")
        if self.fact_type not in SUPPORTED_DISCLOSURE_FACT_TYPES:
            raise ValueError(
                f"fact_type must be one of {sorted(SUPPORTED_DISCLOSURE_FACT_TYPES)}"
            )
        if self.revision < 1:
            raise ValueError("revision must be positive")
        if not self.source_tier.strip() or not self.source_url.strip() or not self.raw_hash.strip():
            raise ValueError("source_tier, source_url and raw_hash are required")
        if not self.review_only:
            raise ValueError("Disclosure Ledger only accepts review-only facts")
        if not isinstance(self.metrics, dict):
            raise ValueError("metrics must be an object")
        if not isinstance(self.evidence, list) or not all(
            isinstance(item, dict) for item in self.evidence
        ):
            raise ValueError("evidence must be a list of objects")

        period_end = self.period_end.isoformat() if isinstance(self.period_end, date) else self.period_end
        if period_end is not None:
            date.fromisoformat(period_end)
        timestamps = {
            "published_at": _timestamp(self.published_at),
            "first_seen_at": _timestamp(self.first_seen_at),
            "retrieved_at": _timestamp(self.retrieved_at),
            "available_at": _timestamp(self.available_at),
        }
        if timestamps["available_at"] < max(
            timestamps["published_at"],
            timestamps["first_seen_at"],
            timestamps["retrieved_at"],
        ):
            raise ValueError("available_at cannot precede publication, observation, or retrieval")

        object.__setattr__(self, "symbol", self.symbol.strip().upper())
        object.__setattr__(self, "period_end", period_end)
        for field_name, normalized in timestamps.items():
            object.__setattr__(self, field_name, normalized)
        object.__setattr__(self, "metrics", _json_copy(self.metrics))
        object.__setattr__(self, "evidence", _json_copy(self.evidence))


class DisclosureLedger:
    """Immutable, review-only point-in-time disclosure facts."""

    def __init__(self, store: SQLiteStore) -> None:
        self.store = store
        self.store.init()

    def record(self, fact: DisclosureFact) -> DisclosureFact:
        with self.store.connect() as conn:
            identity_row = conn.execute(
                "SELECT * FROM disclosure_facts WHERE fact_id = ? AND revision = ?",
                (fact.fact_id, fact.revision),
            ).fetchone()
            if identity_row is not None:
                persisted = self._from_row(dict(identity_row))
                if persisted != fact:
                    raise DisclosureConflictError(
                        "immutable revision cannot be rewritten; use the next revision"
                    )
                return persisted

            hash_row = conn.execute(
                "SELECT * FROM disclosure_facts WHERE fact_id = ? AND raw_hash = ?",
                (fact.fact_id, fact.raw_hash),
            ).fetchone()
            if hash_row is not None:
                persisted = self._from_row(dict(hash_row))
                if replace(fact, revision=persisted.revision) != persisted:
                    raise DisclosureConflictError(
                        "raw_hash already exists with a different extracted fact payload"
                    )
                return persisted

            latest_row = conn.execute(
                """
                SELECT * FROM disclosure_facts
                WHERE fact_id = ?
                ORDER BY revision DESC
                LIMIT 1
                """,
                (fact.fact_id,),
            ).fetchone()
            if latest_row is not None and (
                latest_row["symbol"], latest_row["fact_type"], latest_row["period_end"]
            ) != (fact.symbol, fact.fact_type, fact.period_end):
                raise DisclosureConflictError(
                    "fact identity cannot change across revisions: symbol, fact_type, and period_end "
                    "must remain stable"
                )
            if latest_row is not None and fact.available_at < latest_row["available_at"]:
                raise DisclosureConflictError(
                    "revision available_at cannot move backwards in point-in-time history"
                )
            expected_revision = 1 if latest_row is None else int(latest_row["revision"]) + 1
            if fact.revision != expected_revision:
                raise DisclosureConflictError(
                    f"changed disclosure payload must use the next revision; "
                    f"next revision is {expected_revision}"
                )

            try:
                conn.execute(
                    """
                    INSERT INTO disclosure_facts(
                        fact_id, symbol, fact_type, period_end, published_at,
                        first_seen_at, retrieved_at, available_at, source_tier,
                        source_url, raw_hash, revision, metrics_json, evidence_json,
                        review_only
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                    """,
                    self._values(fact),
                )
            except sqlite3.IntegrityError as exc:
                raise DisclosureConflictError("disclosure revision conflicts with history") from exc
        return fact

    def as_of(
        self,
        cutoff: str | datetime,
        *,
        symbol: str | None = None,
        fact_types: set[str] | frozenset[str] | None = None,
    ) -> list[DisclosureFact]:
        normalized_cutoff = _timestamp(cutoff)
        conditions = ["visible.available_at <= ?"]
        params: list[Any] = [normalized_cutoff]
        if symbol is not None:
            conditions.append("visible.symbol = ?")
            params.append(symbol.strip().upper())
        if fact_types:
            placeholders = ", ".join("?" for _ in fact_types)
            conditions.append(f"visible.fact_type IN ({placeholders})")
            params.extend(sorted(fact_types))
        rows = self.store.fetch_all(
            f"""
            SELECT visible.*
            FROM disclosure_facts visible
            WHERE {' AND '.join(conditions)}
              AND visible.revision = (
                  SELECT MAX(candidate.revision)
                  FROM disclosure_facts candidate
                  WHERE candidate.fact_id = visible.fact_id
                    AND candidate.available_at <= ?
              )
            ORDER BY visible.available_at, visible.fact_id
            """,
            tuple([*params, normalized_cutoff]),
        )
        return [self._from_row(row) for row in rows]

    def feature_summary(
        self,
        cutoff: str | datetime,
        *,
        symbol: str,
        fact_types: set[str] | frozenset[str] | None = None,
    ) -> dict[str, Any]:
        normalized_symbol = symbol.strip().upper()
        facts = self.as_of(cutoff, symbol=normalized_symbol, fact_types=fact_types)
        type_counts: dict[str, int] = {}
        source_counts: dict[str, int] = {}
        metric_values: dict[str, list[float]] = {}
        for fact in facts:
            type_counts[fact.fact_type] = type_counts.get(fact.fact_type, 0) + 1
            source_counts[fact.source_tier] = source_counts.get(fact.source_tier, 0) + 1
            for metric_name, value in fact.metrics.items():
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    continue
                numeric_value = float(value)
                if math.isfinite(numeric_value):
                    metric_values.setdefault(metric_name, []).append(numeric_value)

        numeric_metrics = {
            metric_name: {
                "count": len(values),
                "latest": values[-1],
                "min": min(values),
                "max": max(values),
                "mean": sum(values) / len(values),
            }
            for metric_name, values in sorted(metric_values.items())
        }
        return {
            "schema_version": "disclosure_feature_summary.v1",
            "as_of": _timestamp(cutoff),
            "symbol": normalized_symbol,
            "review_only": True,
            "fact_count": len(facts),
            "fact_type_counts": dict(sorted(type_counts.items())),
            "source_tier_counts": dict(sorted(source_counts.items())),
            "latest_available_at": facts[-1].available_at if facts else None,
            "numeric_metrics": numeric_metrics,
            "facts": [
                {
                    "fact_id": fact.fact_id,
                    "fact_type": fact.fact_type,
                    "period_end": fact.period_end,
                    "available_at": fact.available_at,
                    "source_tier": fact.source_tier,
                    "revision": fact.revision,
                }
                for fact in facts
            ],
        }

    def _values(self, fact: DisclosureFact) -> tuple[Any, ...]:
        return (
            fact.fact_id,
            fact.symbol,
            fact.fact_type,
            fact.period_end,
            fact.published_at,
            fact.first_seen_at,
            fact.retrieved_at,
            fact.available_at,
            fact.source_tier,
            fact.source_url,
            fact.raw_hash,
            fact.revision,
            json.dumps(fact.metrics, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            json.dumps(fact.evidence, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        )

    def _from_row(self, row: dict[str, Any]) -> DisclosureFact:
        return DisclosureFact(
            fact_id=row["fact_id"],
            symbol=row["symbol"],
            fact_type=row["fact_type"],
            period_end=row["period_end"],
            published_at=row["published_at"],
            first_seen_at=row["first_seen_at"],
            retrieved_at=row["retrieved_at"],
            available_at=row["available_at"],
            source_tier=row["source_tier"],
            source_url=row["source_url"],
            raw_hash=row["raw_hash"],
            revision=int(row["revision"]),
            metrics=json.loads(row["metrics_json"]),
            evidence=json.loads(row["evidence_json"]),
            review_only=bool(row["review_only"]),
        )


__all__ = [
    "DisclosureConflictError",
    "DisclosureFact",
    "DisclosureLedger",
    "SUPPORTED_DISCLOSURE_FACT_TYPES",
]
