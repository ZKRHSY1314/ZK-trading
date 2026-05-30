from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import json
from typing import Any, Protocol
from urllib.error import URLError
from urllib.request import Request, urlopen

from app.config import settings


@dataclass(frozen=True)
class RealtimeQuote:
    symbol: str
    price: float
    source: str
    event_ts: datetime
    name: str | None = None
    volume: float | None = None
    amount: float | None = None
    quality_status: str = "realtime_ok"
    provider_status: str = "ok"
    fallback_used: bool = False
    payload: dict[str, Any] = field(default_factory=dict)


class RealtimeMarketProvider(Protocol):
    name: str

    def configured(self) -> bool:
        ...

    def health(self) -> dict[str, Any]:
        ...

    def fetch_quote(self, symbol: str) -> RealtimeQuote:
        ...


class DisabledRealtimeMarketProvider:
    name = "disabled"

    def configured(self) -> bool:
        return False

    def health(self) -> dict[str, Any]:
        return {
            "provider": self.name,
            "status": "disabled",
            "configured": False,
            "quality_status": "needs_config",
            "last_error": "No realtime provider is enabled.",
            "details": {
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": False,
            },
        }

    def fetch_quote(self, symbol: str) -> RealtimeQuote:
        raise RuntimeError("Realtime provider is disabled.")


class AkshareFallbackRealtimeProvider:
    name = "akshare_fallback"

    def configured(self) -> bool:
        return True

    def health(self) -> dict[str, Any]:
        return {
            "provider": self.name,
            "status": "fallback_available",
            "configured": True,
            "quality_status": "fallback_delayed",
            "last_error": None,
            "details": {
                "note": "AKShare remains a fallback source and is not labeled as reliable second-level realtime.",
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": False,
            },
        }

    def fetch_quote(self, symbol: str) -> RealtimeQuote:
        raise RuntimeError("AKShare fallback is not used for second-level realtime snapshots in V4.0-P0.")


class AShareHubRealtimeProvider:
    name = "asharehub"

    def configured(self) -> bool:
        return bool(settings.asharehub_api_key)

    def health(self) -> dict[str, Any]:
        configured = self.configured()
        return {
            "provider": self.name,
            "status": "configured" if configured else "disabled",
            "configured": configured,
            "quality_status": "ready" if configured else "needs_config",
            "last_error": None if configured else "ASHAREHUB_API_KEY is not configured.",
            "details": {
                "base_url": settings.asharehub_base_url,
                "external_network": configured,
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": False,
            },
        }

    def fetch_quote(self, symbol: str) -> RealtimeQuote:
        if not self.configured():
            raise RuntimeError("ASHAREHUB_API_KEY is not configured.")
        url = f"{settings.asharehub_base_url.rstrip('/')}/quote?symbol={symbol}"
        request = Request(url, headers={"Authorization": f"Bearer {settings.asharehub_api_key}"})
        try:
            with urlopen(request, timeout=settings.realtime_request_timeout_seconds) as response:
                data = json.loads(response.read().decode("utf-8"))
        except (OSError, URLError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"AShareHub quote fetch failed: {exc}") from exc
        price = data.get("price") or data.get("close") or data.get("last")
        if price is None:
            raise RuntimeError("AShareHub response did not include a price field.")
        event_ts = self._parse_ts(data.get("timestamp") or data.get("time") or data.get("event_ts"))
        return RealtimeQuote(
            symbol=symbol,
            name=data.get("name"),
            price=float(price),
            volume=self._float_or_none(data.get("volume")),
            amount=self._float_or_none(data.get("amount")),
            source=self.name,
            event_ts=event_ts,
            quality_status="realtime_ok",
            provider_status="ok",
            payload=data,
        )

    def _parse_ts(self, value: Any) -> datetime:
        if isinstance(value, str) and value:
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
            except ValueError:
                pass
        return datetime.now()

    def _float_or_none(self, value: Any) -> float | None:
        try:
            return None if value is None else float(value)
        except (TypeError, ValueError):
            return None


class MockRealtimeMarketProvider:
    name = "mock_local_rule"

    def __init__(self, quotes: list[RealtimeQuote] | None = None) -> None:
        self._quotes = quotes or []

    def configured(self) -> bool:
        return True

    def health(self) -> dict[str, Any]:
        return {
            "provider": self.name,
            "status": "ready",
            "configured": True,
            "quality_status": "mock_realtime",
            "last_error": None,
            "details": {
                "external_network": False,
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": False,
            },
        }

    def fetch_quote(self, symbol: str) -> RealtimeQuote:
        for quote in reversed(self._quotes):
            if quote.symbol == symbol:
                return quote
        raise RuntimeError(f"No mock quote available for {symbol}.")


def configured_realtime_provider() -> RealtimeMarketProvider:
    provider = settings.realtime_provider.lower().strip()
    if provider == "asharehub":
        return AShareHubRealtimeProvider()
    if provider == "akshare_fallback":
        return AkshareFallbackRealtimeProvider()
    return DisabledRealtimeMarketProvider()
