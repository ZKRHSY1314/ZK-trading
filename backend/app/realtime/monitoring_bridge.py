from __future__ import annotations

from datetime import datetime
import json
from typing import Any

from app.config import settings
from app.storage.sqlite_store import SQLiteStore


PRICE_JUMP_THRESHOLD = 0.03
STALE_LATENCY_MS = 60_000


class RealtimeMonitoringBridge:
    """Convert persisted realtime events into review-only monitoring alerts."""

    def __init__(self) -> None:
        self.store = SQLiteStore(settings.database_path)
        self.store.init()

    def sync(self, limit: int = 100) -> dict[str, Any]:
        events = self._recent_realtime_events(limit)
        session_id = self._create_session(events)
        created_event_count = 0
        created_alert_count = 0
        skipped_duplicate_count = 0
        alerts_by_type: dict[str, int] = {}
        previous_by_symbol: dict[str, dict[str, Any]] = {}
        provider_health = self._provider_health_by_source()

        for event in events:
            previous = previous_by_symbol.get(event["symbol"])
            if self._monitoring_event_exists(event["id"]):
                skipped_duplicate_count += 1
                previous_by_symbol[event["symbol"]] = event
                continue

            monitoring_event_id = self._insert_monitoring_event(session_id, event, previous)
            created_event_count += 1
            for alert in self._alerts_for_event(
                session_id=session_id,
                event_id=monitoring_event_id,
                event=event,
                previous=previous,
                health=provider_health.get(event["source"]),
            ):
                if self._insert_alert(alert):
                    created_alert_count += 1
                    alert_type = alert["alert_type"]
                    alerts_by_type[alert_type] = alerts_by_type.get(alert_type, 0) + 1
                else:
                    skipped_duplicate_count += 1
            previous_by_symbol[event["symbol"]] = event

        summary = {
            "scanned_event_count": len(events),
            "created_event_count": created_event_count,
            "created_alert_count": created_alert_count,
            "skipped_duplicate_count": skipped_duplicate_count,
            "alerts_by_type": alerts_by_type,
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": False,
        }
        self._finish_session(session_id, summary)
        return {
            "status": "synced",
            "session_id": session_id,
            **summary,
        }

    def _recent_realtime_events(self, limit: int) -> list[dict[str, Any]]:
        rows = self.store.fetch_all(
            """
            SELECT *
            FROM realtime_market_events
            ORDER BY event_ts DESC, id DESC
            LIMIT ?
            """,
            (max(1, min(limit, 500)),),
        )
        return list(reversed(rows))

    def _provider_health_by_source(self) -> dict[str, dict[str, Any]]:
        rows = self.store.fetch_all("SELECT * FROM realtime_provider_health")
        return {row["provider"]: row for row in rows}

    def _create_session(self, events: list[dict[str, Any]]) -> int:
        symbols = sorted({event["symbol"] for event in events})
        with self.store.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO monitoring_sessions(name, status, symbols_json, summary_json)
                VALUES (?, ?, ?, ?)
                """,
                (
                    "realtime_monitoring_sync",
                    "running",
                    json.dumps(symbols, ensure_ascii=False),
                    json.dumps(
                        {
                            "source": "realtime_market_events",
                            "review_only": True,
                            "simulation_only": True,
                            "live_trading_enabled": False,
                        },
                        ensure_ascii=False,
                    ),
                ),
            )
            return int(cursor.lastrowid)

    def _finish_session(self, session_id: int, summary: dict[str, Any]) -> None:
        with self.store.connect() as conn:
            conn.execute(
                """
                UPDATE monitoring_sessions
                SET status = ?, summary_json = ?, completed_at = ?
                WHERE id = ?
                """,
                (
                    "completed",
                    json.dumps(summary, ensure_ascii=False, default=str),
                    datetime.now().isoformat(timespec="seconds"),
                    session_id,
                ),
            )

    def _monitoring_event_exists(self, source_event_id: int) -> bool:
        row = self.store.fetch_one(
            """
            SELECT id
            FROM monitoring_events
            WHERE source_table = 'realtime_market_events' AND source_id = ?
            LIMIT 1
            """,
            (str(source_event_id),),
        )
        return row is not None

    def _insert_monitoring_event(
        self,
        session_id: int,
        event: dict[str, Any],
        previous: dict[str, Any] | None,
    ) -> int:
        price = float(event.get("price") or 0)
        previous_price = float(previous.get("price") or 0) if previous else 0.0
        pct_delta = 0.0 if previous_price <= 0 else round((price - previous_price) / previous_price * 100, 4)
        price_delta = None if previous is None else round(price - previous_price, 4)
        signal = "realtime_price_jump" if abs(pct_delta) >= PRICE_JUMP_THRESHOLD * 100 else "realtime_observe"
        snapshot = {
            "source_event_id": event["id"],
            "event_ts": event["event_ts"],
            "quality_status": event["quality_status"],
            "latency_ms": event.get("latency_ms"),
            "provider_status": event.get("provider_status"),
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": False,
        }
        plan = {
            "action": "observe",
            "allowed": False,
            "reason": "realtime monitoring bridge is review-only",
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": False,
        }
        dedupe_key = f"realtime_event:{event['id']}"
        with self.store.connect() as conn:
            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO monitoring_events(
                    session_id, symbol, name, price, pct_change, price_delta, pct_delta,
                    signal, decision_tier, action, allowed, data_source, summary,
                    snapshot_json, plan_json, source_table, source_id, dedupe_key
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    event["symbol"],
                    event.get("name"),
                    price,
                    pct_delta,
                    price_delta,
                    pct_delta,
                    signal,
                    "review_only",
                    "observe",
                    0,
                    event["source"],
                    f"{event['symbol']} realtime event synced for monitoring review.",
                    json.dumps(snapshot, ensure_ascii=False, default=str),
                    json.dumps(plan, ensure_ascii=False, default=str),
                    "realtime_market_events",
                    str(event["id"]),
                    dedupe_key,
                ),
            )
            if cursor.rowcount:
                return int(cursor.lastrowid)
        row = self.store.fetch_one(
            "SELECT id FROM monitoring_events WHERE dedupe_key = ?",
            (dedupe_key,),
        )
        return int(row["id"]) if row else 0

    def _alerts_for_event(
        self,
        session_id: int,
        event_id: int,
        event: dict[str, Any],
        previous: dict[str, Any] | None,
        health: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        alerts: list[dict[str, Any]] = []
        price = float(event.get("price") or 0)
        previous_price = float(previous.get("price") or 0) if previous else 0.0
        pct_delta = 0.0 if previous_price <= 0 else (price - previous_price) / previous_price
        base_payload = {
            "source_event_id": event["id"],
            "source": event["source"],
            "event_ts": event["event_ts"],
            "quality_status": event["quality_status"],
            "latency_ms": event.get("latency_ms"),
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": False,
        }
        if previous and abs(pct_delta) >= PRICE_JUMP_THRESHOLD:
            alerts.append(
                self._alert(
                    session_id=session_id,
                    event_id=event_id,
                    symbol=event["symbol"],
                    alert_type="realtime_price_jump",
                    severity="medium",
                    message=f"{event['symbol']} realtime price changed {pct_delta:.2%}; review signal quality.",
                    payload={**base_payload, "previous_price": previous_price, "price": price, "pct_delta": pct_delta},
                )
            )

        latency_ms = float(event.get("latency_ms") or 0)
        if latency_ms > STALE_LATENCY_MS or event.get("quality_status") == "stale_realtime":
            alerts.append(
                self._alert(
                    session_id=session_id,
                    event_id=event_id,
                    symbol=event["symbol"],
                    alert_type="realtime_stale_data",
                    severity="medium",
                    message=f"{event['symbol']} realtime event is stale; downgrade to delayed monitoring.",
                    payload=base_payload,
                )
            )

        if health and (
            health.get("status") in {"degraded", "fallback_required"}
            or health.get("quality_status") == "fallback_required"
        ):
            alerts.append(
                self._alert(
                    session_id=session_id,
                    event_id=event_id,
                    symbol=event["symbol"],
                    alert_type="realtime_provider_degraded",
                    severity="high",
                    message=f"{event['source']} provider is degraded; realtime confidence is disabled.",
                    payload={**base_payload, "provider_status": health.get("status")},
                )
            )
        return alerts

    def _alert(
        self,
        session_id: int,
        event_id: int,
        symbol: str,
        alert_type: str,
        severity: str,
        message: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "session_id": session_id,
            "event_id": event_id,
            "symbol": symbol,
            "alert_type": alert_type,
            "severity": severity,
            "message": message,
            "payload": payload,
            "dedupe_key": f"realtime_alert:{alert_type}:{symbol}:{payload['event_ts']}",
        }

    def _insert_alert(self, alert: dict[str, Any]) -> bool:
        with self.store.connect() as conn:
            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO monitoring_alerts(
                    session_id, event_id, symbol, severity, alert_type, message, payload_json, dedupe_key
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    alert["session_id"],
                    alert["event_id"],
                    alert["symbol"],
                    alert["severity"],
                    alert["alert_type"],
                    alert["message"],
                    json.dumps(alert["payload"], ensure_ascii=False, default=str),
                    alert["dedupe_key"],
                ),
            )
            return cursor.rowcount > 0
