from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import math
import re
from typing import Any

from app.config import settings
from app.models import CapitalFlowSnapshot
from app.storage.sqlite_store import SQLiteStore


@dataclass(frozen=True)
class MarkSnapshot:
    price: float | None
    previous_close: float | None
    source: str
    as_of: str | None
    freshness: str


@dataclass(frozen=True)
class ScreenPositionSnapshot:
    status: str
    positions: list[dict[str, Any]]
    as_of: str | None
    scope: str | None
    reason: str | None


class SimulationMarketDataService:
    """Read-only market data adapter for simulation valuation and UI contracts."""

    def __init__(self, store: SQLiteStore | None = None) -> None:
        if store is not None:
            self.store = store
        else:
            self.store = SQLiteStore(settings.database_path)

    def mark_snapshot(self, symbol: str) -> MarkSnapshot:
        normalized_symbol = symbol.strip().upper()
        daily_rows = self.store.fetch_all(
            """
            SELECT trade_date, close, source, adjustment_mode, quality_status
            FROM daily_bar_cache
            WHERE symbol = ?
              AND trade_date != 'ERROR'
              AND close IS NOT NULL
              AND close > 0
              AND quality_status = 'ready'
              AND adjustment_mode = 'qfq'
            ORDER BY trade_date DESC, id DESC
            LIMIT 2
            """,
            (normalized_symbol,),
        )
        realtime = self.store.fetch_one(
            """
            SELECT price, source, provider_status, event_ts, quality_status, fallback_used
            FROM realtime_market_events
            WHERE symbol = ?
              AND price > 0
              AND lower(provider_status) NOT IN ('error', 'failed', 'disabled')
              AND lower(quality_status) NOT IN ('error', 'invalid', 'rejected', 'unavailable')
            ORDER BY event_ts DESC, id DESC
            LIMIT 1
            """,
            (normalized_symbol,),
        )

        realtime_freshness = (
            self._realtime_freshness(
                str(realtime["event_ts"]),
                quality_status=str(realtime.get("quality_status") or ""),
                fallback_used=bool(realtime.get("fallback_used")),
            )
            if realtime
            else "unavailable"
        )
        if (
            realtime
            and realtime_freshness != "stale"
            and self._realtime_not_older_than_daily(realtime, daily_rows)
        ):
            event_ts = str(realtime["event_ts"])
            return MarkSnapshot(
                price=round(float(realtime["price"]), 4),
                previous_close=self._previous_close_for_realtime(event_ts, daily_rows),
                source=f"realtime_market_events:{realtime['source']}",
                as_of=event_ts,
                freshness=realtime_freshness,
            )

        if daily_rows:
            latest = daily_rows[0]
            previous_close = float(daily_rows[1]["close"]) if len(daily_rows) > 1 else None
            adjustment = str(latest.get("adjustment_mode") or "unknown")
            return MarkSnapshot(
                price=round(float(latest["close"]), 4),
                previous_close=round(previous_close, 4) if previous_close is not None else None,
                source=f"daily_bar_cache:{latest['source']}:{adjustment}",
                as_of=str(latest["trade_date"]),
                freshness=self._daily_freshness(str(latest["trade_date"])),
            )

        return MarkSnapshot(
            price=None,
            previous_close=None,
            source="unavailable",
            as_of=None,
            freshness="unavailable",
        )

    def screen_position_snapshot(self) -> ScreenPositionSnapshot:
        row = self.store.fetch_one(
            """
            SELECT id, status, payload_json, simulation_only,
                   live_trading_enabled, created_at
            FROM sim_cockpit_readbacks
            WHERE readback_type = 'screen_positions'
            ORDER BY datetime(created_at) DESC, id DESC
            LIMIT 1
            """
        )
        if not row:
            return self._unavailable_screen_positions("screen_positions_evidence_missing")
        if not bool(row.get("simulation_only")) or bool(row.get("live_trading_enabled")):
            return self._unavailable_screen_positions("screen_positions_safety_contract_failed")
        if self._evidence_age_seconds(row.get("created_at")) is None:
            return self._unavailable_screen_positions("screen_positions_time_unreadable")
        if not self._evidence_is_fresh(row.get("created_at")):
            return self._unavailable_screen_positions("screen_positions_evidence_expired")

        payload = self._json_object(row.get("payload_json"))
        readback = payload.get("screen_readback")
        if not isinstance(readback, dict):
            return self._unavailable_screen_positions("screen_positions_payload_invalid")
        if (
            readback.get("readback_type") != "positions"
            or readback.get("parsed") is not True
            or bool(readback.get("requires_visual_or_ocr_review"))
            or str(row.get("status") or "") not in {"positions_parsed", "no_position_detected"}
        ):
            return self._unavailable_screen_positions("screen_positions_not_parsed")

        verification_id = payload.get("window_verification_id")
        if isinstance(verification_id, bool):
            verification_id = None
        try:
            verification_id = int(verification_id)
        except (TypeError, ValueError):
            return self._unavailable_screen_positions("screen_positions_verification_missing")
        verification = self.store.fetch_one(
            """
            SELECT status, simulation_mode_detected, real_trading_blocked,
                   live_trading_enabled, blocked_reasons_json, created_at
            FROM sim_cockpit_window_verifications
            WHERE id = ?
            """,
            (verification_id,),
        )
        blocked_reasons = (
            self._json_list(verification.get("blocked_reasons_json"))
            if verification
            else None
        )
        if not verification or (
            verification.get("status") != "verified"
            or not bool(verification.get("simulation_mode_detected"))
            or not bool(verification.get("real_trading_blocked"))
            or bool(verification.get("live_trading_enabled"))
            or blocked_reasons is None
            or bool(blocked_reasons)
        ):
            return self._unavailable_screen_positions("screen_positions_verification_failed")
        if not self._evidence_is_fresh(verification.get("created_at")):
            return self._unavailable_screen_positions("screen_positions_verification_expired")

        raw_positions = readback.get("positions")
        if not isinstance(raw_positions, list):
            return self._unavailable_screen_positions("screen_positions_payload_invalid")
        positions: list[dict[str, Any]] = []
        for item in raw_positions:
            normalized = self._screen_position(item)
            if normalized is None:
                return self._unavailable_screen_positions("screen_positions_payload_invalid")
            positions.append(normalized)
        scope = str(readback.get("scope") or "full_account")
        return ScreenPositionSnapshot(
            status="available",
            positions=positions,
            as_of=str(row.get("created_at")),
            scope=scope,
            reason=None,
        )

    @staticmethod
    def _unavailable_screen_positions(reason: str) -> ScreenPositionSnapshot:
        return ScreenPositionSnapshot(
            status="unavailable",
            positions=[],
            as_of=None,
            scope=None,
            reason=reason,
        )

    @staticmethod
    def _json_list(value: Any) -> list[Any] | None:
        if isinstance(value, list):
            return value
        if not isinstance(value, str) or not value:
            return None
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError, json.JSONDecodeError):
            return None
        return parsed if isinstance(parsed, list) else None

    @classmethod
    def _evidence_age_seconds(cls, value: Any) -> float | None:
        parsed = cls._parse_datetime(str(value or ""))
        if parsed is None:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        else:
            parsed = parsed.astimezone(timezone.utc)
        return (datetime.now(timezone.utc) - parsed).total_seconds()

    @classmethod
    def _evidence_is_fresh(cls, value: Any) -> bool:
        age_seconds = cls._evidence_age_seconds(value)
        return age_seconds is not None and -60 <= age_seconds <= 15 * 60

    @classmethod
    def _screen_position(cls, value: Any) -> dict[str, Any] | None:
        if not isinstance(value, dict):
            return None
        symbol = str(value.get("symbol") or "").strip().upper()
        if not re.fullmatch(r"(?:SH|SZ|BJ)\d{6}", symbol):
            return None
        quantity = cls._nonnegative_int(value.get("quantity"))
        if quantity is None:
            return None
        sellable = cls._nonnegative_int(value.get("sellable_quantity"), optional=True)
        if sellable is not None and sellable > quantity:
            return None
        result: dict[str, Any] = {
            "symbol": symbol,
            "name": str(value.get("name")) if value.get("name") is not None else None,
            "quantity": quantity,
            "sellable_quantity": sellable,
        }
        for key in ("avg_cost", "mark_price", "market_value"):
            number = cls._finite_number(value.get(key), optional=True)
            if number is not None and number < 0:
                return None
            result[key] = number
        result["today_pnl"] = cls._finite_number(value.get("today_pnl"), optional=True)
        return result

    @staticmethod
    def _nonnegative_int(value: Any, *, optional: bool = False) -> int | None:
        if value is None and optional:
            return None
        if isinstance(value, bool):
            return None
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return None
        return parsed if parsed >= 0 else None

    @staticmethod
    def _finite_number(value: Any, *, optional: bool = False) -> float | None:
        if value is None and optional:
            return None
        if isinstance(value, bool):
            return None
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return None
        return parsed if math.isfinite(parsed) else None

    def capital_flow(self, symbol: str | None = None) -> CapitalFlowSnapshot:
        normalized_symbol = symbol.strip().upper() if symbol else None
        if normalized_symbol:
            rows = self.store.fetch_all(
                """
                SELECT symbol, source, provider_status, event_ts, quality_status,
                       fallback_used, payload_json
                FROM realtime_market_events
                WHERE symbol = ?
                  AND json_valid(payload_json) = 1
                  AND lower(COALESCE(json_extract(payload_json, '$.event_type'), ''))
                      = 'capital_flow'
                  AND lower(COALESCE(
                        json_extract(payload_json, '$.capital_flow.scope'),
                        json_extract(payload_json, '$.money_flow.scope'),
                        json_extract(payload_json, '$.fund_flow.scope'),
                        ''
                  )) IN ('symbol', 'stock', 'security')
                ORDER BY event_ts DESC, id DESC
                LIMIT 50
                """,
                (normalized_symbol,),
            )
        else:
            rows = self.store.fetch_all(
                """
                SELECT symbol, source, provider_status, event_ts, quality_status,
                       fallback_used, payload_json
                FROM realtime_market_events
                WHERE json_valid(payload_json) = 1
                  AND lower(COALESCE(json_extract(payload_json, '$.event_type'), ''))
                      = 'capital_flow'
                  AND lower(COALESCE(
                        json_extract(payload_json, '$.capital_flow.scope'),
                        json_extract(payload_json, '$.money_flow.scope'),
                        json_extract(payload_json, '$.fund_flow.scope'),
                        ''
                  )) IN ('market', 'all_a_share', 'broad_market')
                ORDER BY event_ts DESC, id DESC
                LIMIT 50
                """
            )
        rejection_reason = "no_verified_capital_flow_source"
        for row in rows:
            payload = self._json_object(row.get("payload_json"))
            flow = self._flow_payload(payload)
            if flow is None:
                continue
            flow_scope = str(flow.get("scope") or "").strip().lower()
            if normalized_symbol:
                if flow_scope and flow_scope not in {"symbol", "stock", "security"}:
                    rejection_reason = "capital_flow_scope_mismatch"
                    continue
                response_scope = "symbol"
            else:
                if flow_scope not in {"market", "all_a_share", "broad_market"}:
                    rejection_reason = "verified_market_capital_flow_unavailable"
                    continue
                response_scope = "market"
            if not self._is_trustworthy_flow_event(row, flow):
                rejection_reason = "capital_flow_source_not_verified"
                continue

            unit = flow.get("unit") or payload.get("capital_flow_unit")
            if not isinstance(unit, str) or not unit.strip():
                rejection_reason = "capital_flow_unit_missing"
                continue
            values = {
                "net_inflow": self._number(flow, "net_inflow", "net_flow", "net_amount"),
                "main_inflow": self._number(flow, "main_inflow", "main_buy"),
                "main_outflow": self._number(flow, "main_outflow", "main_sell"),
                "retail_inflow": self._number(flow, "retail_inflow", "retail_buy"),
                "retail_outflow": self._number(flow, "retail_outflow", "retail_sell"),
                "large_order_net": self._number(flow, "large_order_net", "large_net"),
                "medium_order_net": self._number(flow, "medium_order_net", "medium_net"),
                "small_order_net": self._number(flow, "small_order_net", "small_net"),
            }
            if all(value is None for value in values.values()):
                rejection_reason = "capital_flow_values_missing"
                continue

            as_of = str(flow.get("as_of") or flow.get("timestamp") or row["event_ts"])
            source = str(flow.get("source") or row["source"])
            return CapitalFlowSnapshot(
                symbol=normalized_symbol,
                status="available",
                scope=response_scope,
                source=source,
                as_of=as_of,
                freshness=self._realtime_freshness(
                    as_of,
                    quality_status=str(row.get("quality_status") or ""),
                    fallback_used=bool(row.get("fallback_used")),
                ),
                unit=unit.strip(),
                **values,
            )

        return CapitalFlowSnapshot(
            symbol=normalized_symbol,
            status="unavailable",
            scope="symbol" if normalized_symbol else "market",
            source="unavailable",
            as_of=None,
            freshness="unavailable",
            unit=None,
            reason=rejection_reason,
        )

    @staticmethod
    def _json_object(value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return value
        if not isinstance(value, str) or not value:
            return {}
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}
        return parsed if isinstance(parsed, dict) else {}

    @staticmethod
    def _flow_payload(payload: dict[str, Any]) -> dict[str, Any] | None:
        for key in ("capital_flow", "money_flow", "fund_flow"):
            value = payload.get(key)
            if isinstance(value, dict):
                return value
        return None

    @staticmethod
    def _is_trustworthy_flow_event(row: dict[str, Any], flow: dict[str, Any]) -> bool:
        if flow.get("verified") is not True:
            return False
        source = str(row.get("source") or "").lower()
        provider_status = str(row.get("provider_status") or "").lower()
        quality_status = str(row.get("quality_status") or "").lower()
        if not source or any(token in source for token in ("mock", "fallback", "disabled", "fixture")):
            return False
        if provider_status not in {"ok", "ready", "available", "success"}:
            return False
        if bool(row.get("fallback_used")):
            return False
        if any(token in quality_status for token in ("mock", "fallback", "error", "invalid", "rejected")):
            return False
        return True

    @staticmethod
    def _number(payload: dict[str, Any], *keys: str) -> float | None:
        for key in keys:
            value = payload.get(key)
            if value is None or isinstance(value, bool):
                continue
            try:
                parsed = float(value)
            except (TypeError, ValueError):
                continue
            if math.isfinite(parsed):
                return parsed
        return None

    @staticmethod
    def _parse_datetime(value: str) -> datetime | None:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None

    @classmethod
    def _realtime_freshness(cls, as_of: str, *, quality_status: str, fallback_used: bool) -> str:
        parsed = cls._parse_datetime(as_of)
        if parsed is None:
            return "unknown"
        now = datetime.now(parsed.tzinfo) if parsed.tzinfo else datetime.now()
        age_seconds = (now - parsed).total_seconds()
        if age_seconds < -60:
            return "stale"
        age_seconds = max(0.0, age_seconds)
        degraded = fallback_used or any(
            token in quality_status.lower() for token in ("fallback", "delayed", "stale")
        )
        if age_seconds <= 60 and not degraded:
            return "fresh"
        if age_seconds <= 900 and "stale" not in quality_status.lower():
            return "delayed"
        return "stale"

    @staticmethod
    def _daily_freshness(trade_date: str) -> str:
        try:
            age_days = (datetime.now().date() - datetime.fromisoformat(trade_date).date()).days
        except (TypeError, ValueError):
            return "unknown"
        if age_days <= 0:
            return "end_of_day"
        if age_days <= 3:
            return "previous_close"
        return "stale"

    @classmethod
    def _realtime_not_older_than_daily(cls, realtime: dict[str, Any], daily_rows: list[dict[str, Any]]) -> bool:
        if not daily_rows:
            return True
        event_ts = cls._parse_datetime(str(realtime.get("event_ts") or ""))
        if event_ts is None:
            return False
        try:
            latest_daily = datetime.fromisoformat(str(daily_rows[0]["trade_date"])).date()
        except (TypeError, ValueError):
            return True
        # A ready bar for the same trade date is the completed close. Once it
        # exists, an intraday quote from that session must not overwrite it.
        return event_ts.date() > latest_daily

    @classmethod
    def _previous_close_for_realtime(
        cls,
        event_ts: str,
        daily_rows: list[dict[str, Any]],
    ) -> float | None:
        if not daily_rows:
            return None
        event = cls._parse_datetime(event_ts)
        latest = daily_rows[0]
        try:
            latest_date = datetime.fromisoformat(str(latest["trade_date"])).date()
        except (TypeError, ValueError):
            latest_date = None
        if event is not None and latest_date == event.date():
            row = daily_rows[1] if len(daily_rows) > 1 else None
        else:
            row = latest
        return round(float(row["close"]), 4) if row is not None else None
