from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import re
from typing import Any

from app.market_intelligence.models import EventFact, SectorThesis, iso_utc, parse_utc
from app.market_intelligence.taxonomy import INDUSTRY_CHAIN_EDGES, SECTOR_TAXONOMY
from app.market_regime.service import MarketRegimeService
from app.storage.sqlite_store import SQLiteStore


_MARKET_SYMBOL_SECTORS = {
    "SOX": "semiconductors",
    "SMH": "semiconductors",
    "NVDA": "semiconductors",
    "BRENT": "oil_gas",
    "BZ=F": "oil_gas",
    "WTI": "oil_gas",
    "CL=F": "oil_gas",
    "GOLD": "gold",
    "GC=F": "gold",
    "XAU": "gold",
    "BTC": "crypto",
    "BTC-USD": "crypto",
    "DXY": "rates_fx",
    "US10Y": "rates_fx",
    "CNH": "rates_fx",
    "BDI": "shipping",
}

_INVALIDATION = {
    "semiconductors": (
        "global semiconductor relative strength reverses",
        "domestic sector breadth fails to confirm within the stated horizon",
    ),
    "oil_gas": (
        "supply disruption is resolved or crude prices reverse",
        "domestic price controls neutralize upstream earnings exposure",
    ),
    "gold": (
        "real yields and the dollar rise together while gold breaks down",
        "safe-haven demand is not confirmed across independent sources",
    ),
    "crypto": (
        "liquidity or regulatory conditions reverse",
        "cross-market risk appetite fails to confirm",
    ),
    "rates_fx": (
        "policy guidance or rate expectations reverse",
        "currency move is not confirmed after the next liquid session",
    ),
    "shipping": (
        "shipping route normalizes or freight rates fail to respond",
        "the disruption does not reduce effective capacity",
    ),
}


class MarketIntelligenceService:
    """Build auditable, review-only sector theses from point-in-time facts."""

    def __init__(self, store: SQLiteStore):
        self.store = store
        self.regime = MarketRegimeService(store=store)

    def build_snapshot(
        self,
        evidence: list[dict[str, Any]],
        *,
        as_of: str | None = None,
    ) -> dict[str, Any]:
        cutoff_dt = parse_utc(as_of or datetime.now(timezone.utc).isoformat(), field="as_of")
        assert cutoff_dt is not None
        cutoff = iso_utc(cutoff_dt) or ""

        accepted: list[tuple[EventFact, dict[str, Any]]] = []
        rejected: list[dict[str, str]] = []
        for index, item in enumerate(evidence or []):
            payload = self._event_payload(item)
            try:
                fact = EventFact.from_evidence(payload)
            except (TypeError, ValueError) as exc:
                rejected.append({"index": str(index), "reason": str(exc)})
                continue
            available = parse_utc(fact.available_at, field="available_at")
            if available is not None and available <= cutoff_dt:
                accepted.append((fact, item))
            else:
                rejected.append({"index": str(index), "reason": "not_available_at_as_of"})

        cross_market = self.regime.get_cross_market_features(cutoff)
        theses = self._build_theses(accepted, cross_market, cutoff)
        return {
            "status": "ready" if theses else "insufficient_data",
            "schema_version": "market_intelligence_snapshot.v1",
            "as_of": cutoff,
            "event_facts": [fact.to_dict() for fact, _ in accepted],
            "cross_market_context": cross_market,
            "sector_theses": [thesis.to_dict() for thesis in theses],
            "rejected": rejected,
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": False,
            "auto_trade_allowed": False,
        }

    @staticmethod
    def _event_payload(item: dict[str, Any]) -> dict[str, Any]:
        nested = item.get("event_fact")
        if isinstance(nested, dict):
            return {**item, **nested}
        return item

    def _build_theses(
        self,
        accepted: list[tuple[EventFact, dict[str, Any]]],
        cross_market: dict[str, Any],
        as_of: str,
    ) -> list[SectorThesis]:
        by_sector: dict[str, list[tuple[EventFact, dict[str, Any]]]] = {}
        for fact, item in accepted:
            for sector in self._sectors_for(item, fact):
                by_sector.setdefault(sector, []).append((fact, item))

        market_by_sector: dict[str, list[dict[str, Any]]] = {}
        for feature in cross_market.get("features") or []:
            sector = _MARKET_SYMBOL_SECTORS.get(str(feature.get("symbol") or "").upper())
            if sector:
                market_by_sector.setdefault(sector, []).append(feature)

        theses: list[SectorThesis] = []
        for sector, facts in sorted(by_sector.items()):
            relevant_market = market_by_sector.get(sector, [])
            direction = self._aggregate_direction([fact for fact, _ in facts])
            confidence = self._confidence([fact for fact, _ in facts], relevant_market, direction)
            event_types = {fact.type for fact, _ in facts}
            horizon = self._horizon(event_types)
            event_ids = tuple(dict.fromkeys(fact.event_id for fact, _ in facts))
            digest = hashlib.sha256(
                f"{sector}|{as_of}|{'|'.join(event_ids)}".encode("utf-8")
            ).hexdigest()[:20]
            rationale = [
                f"{len(facts)} point-in-time event fact(s) map to {sector}",
            ]
            if relevant_market:
                rationale.append(
                    f"{len(relevant_market)} available cross-market feature(s) checked at cutoff"
                )
            theses.append(
                SectorThesis(
                    thesis_id=f"thesis-{digest}",
                    as_of=as_of,
                    sector=sector,
                    direction=direction,
                    horizon=horizon,
                    decay=self._decay(horizon),
                    invalidation=_INVALIDATION.get(
                        sector,
                        (
                            "new evidence reverses the event thesis",
                            "sector breadth fails to confirm within the stated horizon",
                        ),
                    ),
                    confidence=confidence,
                    industry_chain_edges=INDUSTRY_CHAIN_EDGES.get(
                        sector,
                        (
                            {
                                "from": "event_driver",
                                "to": sector,
                                "relation": "hypothesized_exposure",
                                "direction": direction,
                            },
                        ),
                    ),
                    event_ids=event_ids,
                    rationale=tuple(rationale),
                    cross_market_features=tuple(relevant_market),
                )
            )
        theses.sort(key=lambda item: (item.confidence, item.sector), reverse=True)
        return theses

    @staticmethod
    def _sectors_for(item: dict[str, Any], fact: EventFact) -> list[str]:
        sectors: list[str] = []
        for match in item.get("matched_sectors") or []:
            value = str(match.get("sector") if isinstance(match, dict) else match or "")
            if value in SECTOR_TAXONOMY and value not in sectors:
                sectors.append(value)
        for hint in item.get("sector_hints") or []:
            value = str(hint.get("sector") if isinstance(hint, dict) else hint or "").strip()
            lowered = value.casefold()
            for sector, payload in SECTOR_TAXONOMY.items():
                candidates = [sector, payload["display_name"], *payload["keywords"]]
                if (
                    lowered in {str(candidate).casefold() for candidate in candidates}
                    and sector not in sectors
                ):
                    sectors.append(sector)
        text = " ".join(
            [
                str(item.get("title") or ""),
                str(item.get("summary") or ""),
                *fact.entities,
            ]
        )
        for sector, payload in SECTOR_TAXONOMY.items():
            if sector in sectors:
                continue
            if any(
                MarketIntelligenceService._contains_keyword(text, keyword)
                for keyword in payload["keywords"]
            ):
                sectors.append(sector)
        return sectors

    @staticmethod
    def _contains_keyword(text: str, keyword: str) -> bool:
        if keyword.isascii():
            return bool(
                re.search(
                    rf"(?<![A-Za-z0-9_]){re.escape(keyword)}(?![A-Za-z0-9_])",
                    text,
                    flags=re.IGNORECASE,
                )
            )
        return keyword.casefold() in text.casefold()

    @staticmethod
    def _aggregate_direction(facts: list[EventFact]) -> str:
        score = 0.0
        seen: set[str] = set()
        for fact in facts:
            seen.add(fact.direction)
            if fact.direction == "positive":
                score += max(0.1, fact.magnitude)
            elif fact.direction == "negative":
                score -= max(0.1, fact.magnitude)
        if "mixed" in seen or ({"positive", "negative"} <= seen):
            return "mixed"
        if score > 0:
            return "positive"
        if score < 0:
            return "negative"
        return "neutral"

    @staticmethod
    def _confidence(
        facts: list[EventFact],
        market: list[dict[str, Any]],
        direction: str,
    ) -> float:
        tier_bonus = {"official": 0.16, "primary_media": 0.10, "market_media": 0.04}
        base = 0.35
        base += min(0.28, sum(fact.magnitude for fact in facts) * 0.35)
        base += max((tier_bonus.get(fact.source_tier, 0.0) for fact in facts), default=0.0)
        market_directions = []
        for feature in market:
            move = feature.get("return_5d")
            if move is None:
                move = feature.get("return_1d")
            if move is not None:
                market_directions.append(
                    "positive" if float(move) > 0 else "negative" if float(move) < 0 else "neutral"
                )
        if direction in market_directions:
            base += 0.12
        elif market_directions and direction in {"positive", "negative"}:
            base -= 0.08
        return round(max(0.05, min(0.95, base)), 4)

    @staticmethod
    def _horizon(event_types: set[str]) -> str:
        if event_types & {"policy", "regulation", "monetary_policy"}:
            return "1-3m"
        if event_types & {
            "listing",
            "earnings",
            "cross_market_move",
            "commodity_move",
            "geopolitical",
            "supply_disruption",
        }:
            return "1-4w"
        return "1-5d"

    @staticmethod
    def _decay(horizon: str) -> str:
        return {
            "1-5d": "exponential_half_life_2_trading_days",
            "1-4w": "exponential_half_life_5_trading_days",
            "1-3m": "exponential_half_life_20_trading_days",
        }[horizon]
