from __future__ import annotations

from datetime import datetime
import json
from typing import Any

from app.config import settings
from app.realtime.providers import (
    AShareHubRealtimeProvider,
    AkshareFallbackRealtimeProvider,
    RealtimeMarketProvider,
    RealtimeQuote,
    configured_realtime_provider,
)
from app.storage.sqlite_store import SQLiteStore


class RealtimeMarketService:
    def __init__(self, provider: RealtimeMarketProvider | None = None) -> None:
        self.store = SQLiteStore(settings.database_path)
        self.store.init()
        self.provider = provider or configured_realtime_provider()

    def capabilities(self) -> dict[str, Any]:
        active_health = self.provider.health()
        return {
            "status": "ready",
            "active_provider": active_health["provider"],
            "provider_status": active_health["status"],
            "providers": [
                {
                    "name": "asharehub",
                    "role": "external_realtime_candidate",
                    "configured": AShareHubRealtimeProvider().configured(),
                    "enabled_when": "REALTIME_PROVIDER=asharehub and ASHAREHUB_API_KEY is configured",
                },
                {
                    "name": "akshare_fallback",
                    "role": "fallback_delayed_source",
                    "configured": True,
                    "enabled_when": "fallback only; never labeled reliable second-level realtime",
                },
                {
                    "name": "vnapi",
                    "role": "future_institutional_provider_candidate",
                    "configured": False,
                    "enabled_when": "future explicit connector and authorized account",
                },
                {
                    "name": "joinquant_enterprise",
                    "role": "future_enterprise_provider_candidate",
                    "configured": False,
                    "enabled_when": "future explicit connector and authorized account",
                },
            ],
            "allowed_modes": ["second_level_monitoring", "second_level_alerts", "second_level_simulation", "replay"],
            "forbidden_modes": [
                "broker_action",
                "order_action",
                "credential_access",
                "screen_click_trading",
                "live_auto_trading",
            ],
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": False,
        }

    def provider_health(self) -> list[dict[str, Any]]:
        base = [
            self._health_model(AShareHubRealtimeProvider().health()),
            self._health_model(AkshareFallbackRealtimeProvider().health()),
            self._health_model(self.provider.health()),
        ]
        persisted = self.store.fetch_all(
            """
            SELECT *
            FROM realtime_provider_health
            ORDER BY updated_at DESC
            """
        )
        by_provider = {item["provider"]: item for item in base}
        for row in persisted:
            by_provider[row["provider"]] = self._provider_health_row(row)
        return list(by_provider.values())

    def latest_snapshot(self, symbol: str) -> dict[str, Any]:
        row = self.store.fetch_one(
            """
            SELECT *
            FROM realtime_market_events
            WHERE symbol = ?
            ORDER BY event_ts DESC, id DESC
            LIMIT 1
            """,
            (symbol,),
        )
        if not row:
            return {
                "symbol": symbol,
                "status": "no_realtime_event",
                "quality_status": "no_data",
                "fallback_status": "fallback_available",
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": False,
            }
        event = self._event_model(row)
        return {
            "status": "ok" if event["quality_status"] == "realtime_ok" else "degraded",
            "event": event,
            "provider_health": self.provider_health(),
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": False,
        }

    def list_events(self, symbol: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        params: list[Any] = []
        where = ""
        if symbol:
            where = "WHERE symbol = ?"
            params.append(symbol)
        params.append(max(1, min(limit, 500)))
        rows = self.store.fetch_all(
            f"""
            SELECT *
            FROM realtime_market_events
            {where}
            ORDER BY event_ts DESC, id DESC
            LIMIT ?
            """,
            tuple(params),
        )
        return [self._event_model(row) for row in rows]

    def ingest_quote(self, quote: RealtimeQuote) -> dict[str, Any]:
        received_ts = datetime.now()
        event_ts = quote.event_ts.replace(tzinfo=None)
        latency_ms = max(0.0, (received_ts - event_ts).total_seconds() * 1000)
        quality_status = self._quality_status(quote.quality_status, latency_ms, quote.fallback_used)
        dedupe_key = self._dedupe_key(quote.source, quote.symbol, event_ts)
        with self.store.connect() as conn:
            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO realtime_market_events(
                    symbol, name, price, volume, amount, source, provider_status,
                    event_ts, received_ts, latency_ms, quality_status, fallback_used,
                    payload_json, dedupe_key
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    quote.symbol,
                    quote.name,
                    quote.price,
                    quote.volume,
                    quote.amount,
                    quote.source,
                    quote.provider_status,
                    event_ts.isoformat(timespec="seconds"),
                    received_ts.isoformat(timespec="seconds"),
                    latency_ms,
                    quality_status,
                    1 if quote.fallback_used else 0,
                    json.dumps(quote.payload, ensure_ascii=False, default=str),
                    dedupe_key,
                ),
            )
            inserted = cursor.rowcount > 0
        self._record_provider_health(
            provider=quote.source,
            status=quote.provider_status,
            configured=True,
            last_error=None,
            last_event_ts=event_ts.isoformat(timespec="seconds"),
            latency_ms=latency_ms,
            quality_status=quality_status,
            details={"inserted": inserted, "fallback_used": quote.fallback_used},
        )
        row = self.store.fetch_one("SELECT * FROM realtime_market_events WHERE dedupe_key = ?", (dedupe_key,))
        event = self._event_model(row) if row else {}
        event["inserted"] = inserted
        return event

    def refresh_quote(self, symbol: str) -> dict[str, Any]:
        try:
            quote = self.provider.fetch_quote(symbol)
            return self.ingest_quote(quote)
        except Exception as exc:
            self._record_provider_health(
                provider=self.provider.health()["provider"],
                status="degraded",
                configured=self.provider.configured(),
                last_error=str(exc),
                last_event_ts=None,
                latency_ms=None,
                quality_status="fallback_required",
                details={
                    "fallback_provider": "akshare_fallback",
                    "review_only": True,
                    "simulation_only": True,
                    "live_trading_enabled": False,
                },
            )
            return {
                "symbol": symbol,
                "status": "degraded",
                "quality_status": "fallback_required",
                "error": str(exc),
                "fallback_provider": "akshare_fallback",
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": False,
            }

    def replay(self, symbol: str | None = None, limit: int = 100) -> dict[str, Any]:
        events = list(reversed(self.list_events(symbol=symbol, limit=limit)))
        signals: list[dict[str, Any]] = []
        previous_by_symbol: dict[str, dict[str, Any]] = {}
        for event in events:
            previous = previous_by_symbol.get(event["symbol"])
            signal = self._replay_signal(event, previous)
            signals.append(signal)
            previous_by_symbol[event["symbol"]] = event
        signals.sort(key=lambda item: (item["event_ts"], -float(item["strength"] or 0), item["symbol"]))
        return {
            "status": "replayed",
            "event_count": len(events),
            "signals": signals,
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": False,
        }

    def _replay_signal(self, event: dict[str, Any], previous: dict[str, Any] | None) -> dict[str, Any]:
        if not previous:
            return {
                "symbol": event["symbol"],
                "event_ts": event["event_ts"],
                "signal_type": "observe",
                "strength": 0,
                "reason": "first_event",
                "quality_status": event["quality_status"],
            }
        prev_price = float(previous.get("price") or 0)
        price = float(event.get("price") or 0)
        pct_change = 0.0 if prev_price <= 0 else (price - prev_price) / prev_price
        if pct_change >= 0.03:
            signal_type = "momentum_up"
        elif pct_change <= -0.03:
            signal_type = "momentum_down"
        else:
            signal_type = "observe"
        return {
            "symbol": event["symbol"],
            "event_ts": event["event_ts"],
            "signal_type": signal_type,
            "strength": round(abs(pct_change), 6),
            "price": price,
            "previous_price": prev_price,
            "quality_status": event["quality_status"],
            "reason": "replay_price_change",
        }

    def _quality_status(self, requested: str, latency_ms: float, fallback_used: bool) -> str:
        if fallback_used:
            return "fallback_delayed"
        if latency_ms > 60_000:
            return "stale_realtime"
        if requested in {"realtime_ok", "mock_realtime", "fallback_delayed", "stale_realtime"}:
            return requested
        return "realtime_ok"

    def _dedupe_key(self, source: str, symbol: str, event_ts: datetime) -> str:
        return f"{source}:{symbol}:{event_ts.isoformat(timespec='seconds')}"

    def _record_provider_health(
        self,
        provider: str,
        status: str,
        configured: bool,
        last_error: str | None,
        last_event_ts: str | None,
        latency_ms: float | None,
        quality_status: str,
        details: dict[str, Any],
    ) -> None:
        with self.store.connect() as conn:
            conn.execute(
                """
                INSERT INTO realtime_provider_health(
                    provider, status, configured, last_error, last_event_ts,
                    latency_ms, quality_status, details_json, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(provider) DO UPDATE SET
                    status = excluded.status,
                    configured = excluded.configured,
                    last_error = excluded.last_error,
                    last_event_ts = excluded.last_event_ts,
                    latency_ms = excluded.latency_ms,
                    quality_status = excluded.quality_status,
                    details_json = excluded.details_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    provider,
                    status,
                    1 if configured else 0,
                    last_error,
                    last_event_ts,
                    latency_ms,
                    quality_status,
                    json.dumps(details, ensure_ascii=False, default=str),
                ),
            )

    def _event_model(self, row: dict[str, Any] | None) -> dict[str, Any]:
        if not row:
            return {}
        item = dict(row)
        item["fallback_used"] = bool(item.get("fallback_used"))
        item["payload"] = self._decode_json(item.pop("payload_json", "{}"))
        item["review_only"] = True
        item["simulation_only"] = True
        item["live_trading_enabled"] = False
        return item

    def _provider_health_row(self, row: dict[str, Any]) -> dict[str, Any]:
        item = dict(row)
        item["configured"] = bool(item.get("configured"))
        item["details"] = self._decode_json(item.pop("details_json", "{}"))
        item["review_only"] = True
        item["simulation_only"] = True
        item["live_trading_enabled"] = False
        return item

    def _health_model(self, health: dict[str, Any]) -> dict[str, Any]:
        return {
            **health,
            "configured": bool(health.get("configured")),
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": False,
        }

    def _decode_json(self, value: Any) -> Any:
        if not isinstance(value, str):
            return value
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
