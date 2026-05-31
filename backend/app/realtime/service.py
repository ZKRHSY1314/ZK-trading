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

    def scheduler_plan(self) -> dict[str, Any]:
        health = self.provider.health()
        configured = bool(self.provider.configured())
        cadence = {
            "workday_trading_hours": [
                {"time": "10:00", "mode": "realtime-cycle", "reason": "morning momentum and provider health check"},
                {"time": "13:00", "mode": "realtime-cycle", "reason": "midday trend persistence check"},
                {"time": "16:00", "mode": "realtime-cycle", "reason": "post-market replay and alert audit"},
            ],
            "non_trading_day": [
                {"time": "20:00", "mode": "potential", "reason": "off-hours candidate discovery remains lower risk"},
            ],
            "provider_unconfigured_behavior": "run only as review evidence; do not invent realtime prices",
        }
        return {
            "status": "ready" if configured else "needs_config",
            "active_provider": health.get("provider"),
            "provider_status": health.get("status"),
            "recommended_mode": "realtime-cycle",
            "recommended_symbols": ["SZ002081", "SZ002115"],
            "command_examples": [
                "backend\\.venv\\Scripts\\python.exe backend\\scripts\\automation_loop.py --mode realtime-cycle --symbols SZ002081,SZ002115 --limit 20 --max-cycles 1",
                "backend\\.venv\\Scripts\\python.exe backend\\scripts\\automation_loop.py --mode realtime-refresh --symbols SZ002081,SZ002115 --limit 20 --max-cycles 1",
                "backend\\.venv\\Scripts\\python.exe backend\\scripts\\automation_loop.py --mode realtime-monitoring-sync --limit 100 --max-cycles 1",
            ],
            "cadence": cadence,
            "pause_controls": [
                "Pause the Codex/OS automation that calls realtime-cycle.",
                "Leave REALTIME_PROVIDER=disabled when no authorized realtime data source is configured.",
                "Use provider-health and realtime-cycle history before resuming a failed cadence.",
            ],
            "degrade_controls": [
                "fallback_required means review_required, not realtime_ok.",
                "disabled or needs_config providers must not write fake realtime prices.",
                "monitoring alerts are review evidence only and never trigger broker/order actions.",
            ],
            "forbidden_actions": [
                "broker_order",
                "credential_access",
                "screen_click_trading",
                "live_auto_trading",
                "risk_gate_bypass",
            ],
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": False,
        }

    def automation_proposal(self) -> dict[str, Any]:
        health = self.provider.health()
        configured = bool(self.provider.configured())
        evidence_endpoints = [
            "/api/realtime/cycles/latest",
            "/api/realtime/cycles?limit=10",
            "/api/realtime/provider-health",
            "/api/realtime/scheduler-plan",
            "/health",
        ]
        proposals = [
            {
                "id": "v4_realtime_cycle_workday",
                "name": "ZK V4 realtime cycle review",
                "mode": "realtime-cycle",
                "status": "proposal_ready" if configured else "needs_provider_config",
                "default_status": "paused_until_user_review",
                "cadence_text": "周一至周五 10:00 / 13:00 / 16:00 Asia/Shanghai；节假日仍需人工复核。",
                "command": (
                    "backend\\.venv\\Scripts\\python.exe backend\\scripts\\automation_loop.py "
                    "--mode realtime-cycle --symbols SZ002081,SZ002115 --limit 20 --max-cycles 1"
                ),
                "summary": "刷新实时事件 -> 同步监控提醒 -> replay -> 写入 realtime_cycle_runs 证据。",
                "evidence_endpoints": evidence_endpoints,
                "expected_output": [
                    "provider health and fallback state",
                    "created monitoring alert counts",
                    "replay signal summary",
                    "latest realtime_cycle_runs evidence",
                    "live_trading_enabled=false confirmation",
                ],
                "requires_provider_config": True,
                "provider_unconfigured_behavior": "return needs_config/fallback_required and do not write fake realtime prices",
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": False,
                "requires_user_review": True,
            },
            {
                "id": "v4_offhour_potential_search",
                "name": "ZK offhour potential search review",
                "mode": "potential",
                "status": "proposal_ready",
                "default_status": "paused_until_user_review",
                "cadence_text": "每日 20:00 Asia/Shanghai；非交易日/盘后用于候选池发现，交易日历需人工复核。",
                "command": (
                    "backend\\.venv\\Scripts\\python.exe backend\\scripts\\automation_loop.py "
                    "--mode potential --limit 200 --max-cycles 1"
                ),
                "summary": "盘后/非交易时段搜索潜力股，写入候选生命周期和评分证据。",
                "evidence_endpoints": [
                    "/api/candidates/auto-discovery/latest?limit=50",
                    "/api/candidates/lifecycle?limit=50",
                    "/api/candidates/scores?limit=50",
                    "/api/candidates/potential-search/latest",
                    "/health",
                ],
                "expected_output": [
                    "candidate discovery counts",
                    "lifecycle state changes",
                    "score evidence",
                    "no live trading or broker action confirmation",
                ],
                "requires_provider_config": False,
                "provider_unconfigured_behavior": "use existing off-hour candidate search sources and keep review-only evidence",
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": False,
                "requires_user_review": True,
            },
        ]
        forbidden_actions = [
            "broker_order",
            "order_action",
            "credential_access",
            "screen_click_trading",
            "live_auto_trading",
            "risk_gate_bypass",
        ]
        return {
            "status": "review_required",
            "active_provider": health.get("provider"),
            "provider_status": health.get("status"),
            "provider_configured": configured,
            "proposal_count": len(proposals),
            "proposals": proposals,
            "acceptance_checks": [
                "Automation remains paused or suggested until the operator explicitly enables it.",
                "Every run confirms /health live_trading_enabled=false.",
                "No backend API executes shell commands or creates recurring jobs.",
                "No broker/order/credential/screen-click/live-trading capability is added.",
            ],
            "pause_controls": [
                "Pause or delete the Codex app automation from the automation card.",
                "Keep REALTIME_PROVIDER=disabled when no authorized realtime source is configured.",
                "Review provider-health and realtime cycle history before resuming.",
            ],
            "forbidden_actions": forbidden_actions,
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

    def refresh_symbols(self, symbols: list[str] | None = None, limit: int = 20) -> dict[str, Any]:
        requested_symbols = self._normalize_symbols(symbols, limit)
        items: list[dict[str, Any]] = []
        refreshed_count = 0
        failed_count = 0
        for symbol in requested_symbols:
            result = self.refresh_quote(symbol)
            items.append(result)
            if result.get("inserted"):
                refreshed_count += 1
            elif result.get("status") == "degraded" or result.get("quality_status") == "fallback_required":
                failed_count += 1

        health = self.provider.health()
        fallback_required = failed_count > 0 and refreshed_count == 0
        status = "fallback_required" if fallback_required else "completed"
        if failed_count and refreshed_count:
            status = "partial"
        return {
            "status": status,
            "provider": health.get("provider"),
            "provider_status": health.get("status"),
            "configured": bool(self.provider.configured()),
            "requested_count": len(requested_symbols),
            "refreshed_count": refreshed_count,
            "failed_count": failed_count,
            "items": items,
            "fallback_required": fallback_required,
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": False,
        }

    def run_cycle(
        self,
        symbols: list[str] | None = None,
        refresh_limit: int = 20,
        sync_limit: int = 100,
        replay_limit: int = 100,
        persist: bool = True,
    ) -> dict[str, Any]:
        from app.realtime.monitoring_bridge import RealtimeMonitoringBridge

        requested_symbols = self._normalize_symbols(symbols, refresh_limit)
        refresh = self.refresh_symbols(symbols=requested_symbols, limit=refresh_limit)
        sync = RealtimeMonitoringBridge().sync(limit=sync_limit)
        replay = self.replay(limit=replay_limit)
        status = "completed"
        if refresh.get("fallback_required") or sync.get("created_alert_count", 0) > 0:
            status = "review_required"
        result = {
            "status": status,
            "steps": {
                "refresh": refresh,
                "monitoring_sync": sync,
                "replay": replay,
            },
            "summary": {
                "refreshed_count": refresh.get("refreshed_count", 0),
                "refresh_failed_count": refresh.get("failed_count", 0),
                "created_alert_count": sync.get("created_alert_count", 0),
                "replay_event_count": replay.get("event_count", 0),
                "signal_counts": replay.get("summary", {}).get("signal_counts", {}),
                "quality_counts": replay.get("summary", {}).get("quality_counts", {}),
                "fallback_required": bool(refresh.get("fallback_required")),
            },
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": False,
        }
        if persist:
            result["run_id"] = self._persist_cycle_run(requested_symbols, result)
        return result

    def list_cycle_runs(self, limit: int = 20) -> list[dict[str, Any]]:
        rows = self.store.fetch_all(
            """
            SELECT *
            FROM realtime_cycle_runs
            ORDER BY id DESC
            LIMIT ?
            """,
            (max(1, min(limit, 200)),),
        )
        return [self._cycle_run_model(row) for row in rows]

    def latest_cycle_run(self) -> dict[str, Any]:
        row = self.store.fetch_one(
            """
            SELECT *
            FROM realtime_cycle_runs
            ORDER BY id DESC
            LIMIT 1
            """
        )
        if not row:
            return {
                "status": "empty",
                "message": "No realtime cycle run has been recorded.",
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": False,
            }
        return self._cycle_run_model(row)

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
            "summary": self._replay_summary(events, signals),
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

    def _replay_summary(self, events: list[dict[str, Any]], signals: list[dict[str, Any]]) -> dict[str, Any]:
        signal_counts: dict[str, int] = {}
        quality_counts: dict[str, int] = {}
        latency_values: list[float] = []
        for signal in signals:
            signal_type = str(signal.get("signal_type") or "unknown")
            signal_counts[signal_type] = signal_counts.get(signal_type, 0) + 1
        for event in events:
            quality = str(event.get("quality_status") or "unknown")
            quality_counts[quality] = quality_counts.get(quality, 0) + 1
            latency = event.get("latency_ms")
            if latency is not None:
                latency_values.append(float(latency))
        strongest = sorted(
            [signal for signal in signals if signal.get("signal_type") != "observe"],
            key=lambda item: float(item.get("strength") or 0),
            reverse=True,
        )[:5]
        return {
            "symbol_count": len({event["symbol"] for event in events}),
            "symbols": sorted({event["symbol"] for event in events}),
            "signal_counts": signal_counts,
            "quality_counts": quality_counts,
            "latency_ms": {
                "min": round(min(latency_values), 3) if latency_values else None,
                "max": round(max(latency_values), 3) if latency_values else None,
                "avg": round(sum(latency_values) / len(latency_values), 3) if latency_values else None,
            },
            "strongest_signals": strongest,
            "ordered_by": ["event_ts", "strength_desc", "symbol"],
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": False,
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

    def _normalize_symbols(self, symbols: list[str] | None, limit: int) -> list[str]:
        cleaned: list[str] = []
        seen: set[str] = set()
        for symbol in symbols or []:
            normalized = str(symbol or "").strip().upper()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            cleaned.append(normalized)
        return cleaned[: max(1, min(limit, 200))]

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

    def _persist_cycle_run(self, symbols: list[str], result: dict[str, Any]) -> int:
        summary = result.get("summary", {})
        steps = result.get("steps", {})
        refresh = steps.get("refresh", {})
        sync = steps.get("monitoring_sync", {})
        with self.store.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO realtime_cycle_runs(
                    status, symbols_json, provider, refresh_status, monitoring_session_id,
                    refreshed_count, refresh_failed_count, created_alert_count,
                    replay_event_count, fallback_required, summary_json, steps_json,
                    review_only, simulation_only, live_trading_enabled
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    result["status"],
                    json.dumps(symbols, ensure_ascii=False),
                    refresh.get("provider"),
                    refresh.get("status"),
                    sync.get("session_id"),
                    int(summary.get("refreshed_count") or 0),
                    int(summary.get("refresh_failed_count") or 0),
                    int(summary.get("created_alert_count") or 0),
                    int(summary.get("replay_event_count") or 0),
                    1 if summary.get("fallback_required") else 0,
                    json.dumps(summary, ensure_ascii=False, default=str),
                    json.dumps(steps, ensure_ascii=False, default=str),
                    1,
                    1,
                    0,
                ),
            )
            return int(cursor.lastrowid)

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

    def _cycle_run_model(self, row: dict[str, Any]) -> dict[str, Any]:
        item = dict(row)
        item["symbols"] = self._decode_json(item.pop("symbols_json", "[]"))
        item["summary"] = self._decode_json(item.pop("summary_json", "{}"))
        item["steps"] = self._decode_json(item.pop("steps_json", "{}"))
        item["fallback_required"] = bool(item.get("fallback_required"))
        item["review_only"] = bool(item.get("review_only"))
        item["simulation_only"] = bool(item.get("simulation_only"))
        item["live_trading_enabled"] = bool(item.get("live_trading_enabled"))
        return item

    def _decode_json(self, value: Any) -> Any:
        if not isinstance(value, str):
            return value
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
