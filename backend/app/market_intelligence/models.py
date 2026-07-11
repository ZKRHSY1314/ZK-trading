from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Any


_IDENTIFIER_RE = re.compile(r"[^a-zA-Z0-9_.:-]+")
_EVENT_DIRECTIONS = {"positive", "negative", "mixed", "neutral"}
_EVENT_STATUSES = {"new", "ongoing", "updated", "resolved", "unconfirmed"}
_SOURCE_TIERS = {"official", "primary_media", "market_media"}


def parse_utc(value: Any, *, field: str, required: bool = True) -> datetime | None:
    if value in (None, ""):
        if required:
            raise ValueError(f"{field}_required")
        return None
    text = str(value).strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{field}_invalid") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def iso_utc(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _identifier(value: Any, fallback: str) -> str:
    cleaned = _IDENTIFIER_RE.sub("-", str(value or "").strip()).strip("-")
    return cleaned[:160] or fallback


def _strings(value: Any, *, limit: int = 30) -> tuple[str, ...]:
    values = value if isinstance(value, list) else [value]
    result: list[str] = []
    for item in values:
        text = str(item or "").strip()
        if text and text not in result:
            result.append(text[:240])
        if len(result) >= limit:
            break
    return tuple(result)


@dataclass(frozen=True)
class EventFact:
    event_id: str
    cluster_id: str
    type: str
    entities: tuple[str, ...]
    geography: tuple[str, ...]
    status: str
    direction: str
    magnitude: float
    published_at: str | None
    first_seen_at: str
    retrieved_at: str
    available_at: str
    revision: int
    source_tier: str
    evidence_urls: tuple[str, ...]
    raw_hash: str

    @classmethod
    def from_evidence(cls, evidence: dict[str, Any]) -> "EventFact":
        retrieved = parse_utc(evidence.get("retrieved_at"), field="retrieved_at")
        assert retrieved is not None
        published = parse_utc(evidence.get("published_at"), field="published_at", required=False)
        supplied_first_seen = parse_utc(
            evidence.get("first_seen_at"), field="first_seen_at", required=False
        )
        first_seen = supplied_first_seen or retrieved
        supplied_available = parse_utc(
            evidence.get("available_at"), field="available_at", required=False
        )
        # A source may claim an earlier time, but this system could not use the fact
        # before it retrieved it. This conservative gate prevents look-ahead leakage.
        available = max(retrieved, supplied_available or retrieved)

        event_type = _identifier(evidence.get("type"), "other").lower()
        entities = _strings(evidence.get("entities") or [])
        geography = _strings(evidence.get("geography") or [])
        direction = str(evidence.get("direction") or "neutral").strip().lower()
        if direction not in _EVENT_DIRECTIONS:
            direction = "neutral"
        status = str(evidence.get("status") or "new").strip().lower()
        if status not in _EVENT_STATUSES:
            status = "unconfirmed"
        source_tier = str(evidence.get("source_tier") or "market_media").strip().lower()
        if source_tier not in _SOURCE_TIERS:
            source_tier = "market_media"
        magnitude = max(0.0, min(1.0, float(evidence.get("magnitude") or 0.0)))
        revision = max(1, int(evidence.get("revision") or 1))
        evidence_urls = _strings(
            evidence.get("evidence_urls") or evidence.get("url") or [], limit=20
        )

        raw_material = {
            "title": str(evidence.get("title") or ""),
            "summary": str(evidence.get("summary") or ""),
            "claims": evidence.get("claims") or [],
            "type": event_type,
            "entities": entities,
            "geography": geography,
            "published_at": iso_utc(published),
            "evidence_urls": evidence_urls,
        }
        raw_hash = hashlib.sha256(
            json.dumps(
                raw_material,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        event_fallback = f"evt-{raw_hash[:20]}"
        cluster_material = "|".join(
            [
                event_type,
                *sorted(entity.casefold() for entity in entities),
                (iso_utc(published) or "")[:10],
            ]
        )
        cluster_hash = hashlib.sha256(cluster_material.encode("utf-8")).hexdigest()

        return cls(
            event_id=_identifier(evidence.get("event_id"), event_fallback),
            cluster_id=_identifier(evidence.get("cluster_id"), f"cluster-{cluster_hash[:20]}"),
            type=event_type,
            entities=entities,
            geography=geography,
            status=status,
            direction=direction,
            magnitude=round(magnitude, 4),
            published_at=iso_utc(published),
            first_seen_at=iso_utc(first_seen) or "",
            retrieved_at=iso_utc(retrieved) or "",
            available_at=iso_utc(available) or "",
            revision=revision,
            source_tier=source_tier,
            evidence_urls=evidence_urls,
            raw_hash=raw_hash,
        )

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["entities"] = list(self.entities)
        result["geography"] = list(self.geography)
        result["evidence_urls"] = list(self.evidence_urls)
        return result


@dataclass(frozen=True)
class SectorThesis:
    thesis_id: str
    as_of: str
    sector: str
    direction: str
    horizon: str
    decay: str
    invalidation: tuple[str, ...]
    confidence: float
    industry_chain_edges: tuple[dict[str, str], ...]
    event_ids: tuple[str, ...]
    rationale: tuple[str, ...]
    cross_market_features: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        for key in (
            "invalidation",
            "industry_chain_edges",
            "event_ids",
            "rationale",
            "cross_market_features",
        ):
            result[key] = list(result[key])
        result.update(
            {
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": False,
                "auto_trade_allowed": False,
            }
        )
        return result
