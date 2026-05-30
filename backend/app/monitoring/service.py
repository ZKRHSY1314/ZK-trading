import json
from typing import Any

from app.candidates.lifecycle import CandidateLifecycleService
from app.candidates.local_scanner import LocalCandidateScanner
from app.config import settings
from app.data.snapshot_builder import MarketDataError, MarketSnapshotBuilder
from app.models import MarketSnapshot
from app.simulation.planner import SimulationPlanner
from app.storage.sqlite_store import SQLiteStore


class MonitoringService:
    def __init__(self) -> None:
        self.store = SQLiteStore(settings.database_path)
        self.store.init()

    def start_session(
        self,
        symbols: list[str] | None = None,
        name: str = "intraday_watch",
        limit: int = 5,
    ) -> dict[str, Any]:
        latest_scan = LocalCandidateScanner().latest_scan()
        if not latest_scan:
            latest_scan = LocalCandidateScanner().scan(limit=max(limit, 5), persist=True)

        selected = self._resolve_symbols(symbols, latest_scan, limit)
        with self.store.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO monitoring_sessions(name, status, source_scan_id, symbols_json)
                VALUES (?, ?, ?, ?)
                """,
                (
                    name,
                    "running",
                    latest_scan.get("id") or latest_scan.get("scan_id"),
                    json.dumps(selected, ensure_ascii=False),
                ),
            )
            session_id = int(cursor.lastrowid)
        return self.get_session(session_id) or {"id": session_id, "symbols": selected}

    def run_once(self, session_id: int | None = None, limit: int = 5) -> dict[str, Any]:
        session = self.get_session(session_id) if session_id else self.latest_session()
        if not session or session.get("status") != "running":
            session = self.start_session(limit=limit)

        symbols = session.get("symbols", [])[: max(1, min(limit, 20))]
        events = [self._monitor_symbol(int(session["id"]), item) for item in symbols]
        alerts = [alert for event in events for alert in event.get("alerts", [])]
        summary = {
            "session_id": session["id"],
            "event_count": len(events),
            "planned_count": len([event for event in events if event.get("action")]),
            "allowed_count": len([event for event in events if event.get("allowed")]),
            "alert_count": len(alerts),
            "signals": self._signal_counts(events),
            "alerts": alerts[:20],
            "events": events,
        }
        self._update_session_summary(int(session["id"]), summary)
        return summary

    def latest_session(self) -> dict[str, Any] | None:
        row = self.store.fetch_one(
            """
            SELECT *
            FROM monitoring_sessions
            ORDER BY id DESC
            LIMIT 1
            """
        )
        return self._session_model(row) if row else None

    def get_session(self, session_id: int | None) -> dict[str, Any] | None:
        if session_id is None:
            return None
        row = self.store.fetch_one("SELECT * FROM monitoring_sessions WHERE id = ?", (session_id,))
        return self._session_model(row) if row else None

    def summary(self) -> dict[str, Any]:
        session = self.latest_session()
        if not session:
            return {"session": None, "event_count": 0, "alert_count": 0, "alerts": []}
        alerts = self.list_alerts(session_id=session["id"], limit=20)
        events = self.list_events(session_id=session["id"], limit=100)
        return {
            "session": {
                "id": session["id"],
                "name": session["name"],
                "status": session["status"],
                "created_at": session["created_at"],
            },
            "event_count": len(events),
            "alert_count": len(alerts),
            "signals": self._signal_counts(events),
            "alerts": alerts,
        }

    def list_events(
        self,
        session_id: int | None = None,
        symbol: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        clauses = []
        params: list[Any] = []
        if session_id is not None:
            clauses.append("session_id = ?")
            params.append(session_id)
        if symbol:
            clauses.append("symbol = ?")
            params.append(symbol)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(max(1, min(limit, 500)))
        rows = self.store.fetch_all(
            f"""
            SELECT *
            FROM monitoring_events
            {where}
            ORDER BY id DESC
            LIMIT ?
            """,
            tuple(params),
        )
        return [self._event_model(row) for row in rows]

    def list_alerts(
        self,
        session_id: int | None = None,
        symbol: str | None = None,
        severity: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        clauses = []
        params: list[Any] = []
        if session_id is not None:
            clauses.append("session_id = ?")
            params.append(session_id)
        if symbol:
            clauses.append("symbol = ?")
            params.append(symbol)
        if severity:
            clauses.append("severity = ?")
            params.append(severity)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(max(1, min(limit, 500)))
        rows = self.store.fetch_all(
            f"""
            SELECT *
            FROM monitoring_alerts
            {where}
            ORDER BY id DESC
            LIMIT ?
            """,
            tuple(params),
        )
        return [self._alert_model(row) for row in rows]

    def replay_symbol(self, symbol: str, session_id: int | None = None, limit: int = 100) -> dict[str, Any]:
        session = self.get_session(session_id) if session_id else self.latest_session()
        events = self.list_events(
            session_id=session.get("id") if session else None,
            symbol=symbol,
            limit=limit,
        )
        events = list(reversed(events))
        alerts = self.list_alerts(
            session_id=session.get("id") if session else None,
            symbol=symbol,
            limit=limit,
        )
        return {
            "symbol": symbol,
            "session_id": session.get("id") if session else None,
            "event_count": len(events),
            "alert_count": len(alerts),
            "first_event": events[0] if events else None,
            "latest_event": events[-1] if events else None,
            "events": events,
            "alerts": alerts,
        }

    def create_symbol_review(
        self,
        symbol: str,
        session_id: int | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        replay = self.replay_symbol(symbol=symbol, session_id=session_id, limit=limit)
        events = replay["events"]
        alerts = replay["alerts"]
        prices = [float(event["price"]) for event in events if event.get("price") is not None]
        pct_changes = [
            float(event["pct_change"]) for event in events if event.get("pct_change") is not None
        ]
        signals = self._signal_counts(events)
        data_sources = sorted({event.get("data_source") for event in events if event.get("data_source")})
        latest = replay.get("latest_event") or {}
        name = latest.get("name")
        risk_blocked_count = len([event for event in events if event.get("signal") == "risk_blocked"])
        allowed_count = len([event for event in events if event.get("allowed")])
        fallback_count = len([event for event in events if event.get("data_source") == "tencent_quote_fallback"])
        severity_counts = self._severity_counts(alerts)
        summary = {
            "symbol": symbol,
            "name": name,
            "session_id": replay.get("session_id"),
            "event_count": len(events),
            "alert_count": len(alerts),
            "allowed_count": allowed_count,
            "risk_blocked_count": risk_blocked_count,
            "signals": signals,
            "severity_counts": severity_counts,
            "data_sources": data_sources,
            "price": {
                "first": prices[0] if prices else None,
                "latest": prices[-1] if prices else None,
                "min": min(prices) if prices else None,
                "max": max(prices) if prices else None,
                "delta": round(prices[-1] - prices[0], 4) if len(prices) >= 2 else None,
            },
            "pct_change": {
                "first": pct_changes[0] if pct_changes else None,
                "latest": pct_changes[-1] if pct_changes else None,
                "delta": round(pct_changes[-1] - pct_changes[0], 4)
                if len(pct_changes) >= 2
                else None,
            },
            "diagnosis": self._review_diagnosis(
                event_count=len(events),
                allowed_count=allowed_count,
                risk_blocked_count=risk_blocked_count,
                fallback_count=fallback_count,
                data_sources=data_sources,
            ),
            "next_actions": self._review_next_actions(
                allowed_count=allowed_count,
                risk_blocked_count=risk_blocked_count,
                fallback_count=fallback_count,
                event_count=len(events),
            ),
            "latest_event": latest,
            "recent_alerts": alerts[:10],
            "safety": {
                "live_trading_enabled": settings.enable_live_trading,
                "note": "This review is for simulation and observation only.",
            },
        }
        title = f"{symbol} {name or ''}监控复盘".strip()
        review_id = self._persist_review(
            session_id=replay.get("session_id"),
            symbol=symbol,
            title=title,
            summary=summary,
        )
        return {
            "id": review_id,
            "session_id": replay.get("session_id"),
            "symbol": symbol,
            "title": title,
            "summary": summary,
        }

    def latest_reviews(self, limit: int = 20) -> list[dict[str, Any]]:
        rows = self.store.fetch_all(
            """
            SELECT *
            FROM monitoring_reviews
            ORDER BY id DESC
            LIMIT ?
            """,
            (max(1, min(limit, 100)),),
        )
        return [self._review_model(row) for row in rows]

    def record_alert_action(
        self,
        alert_id: int,
        action_type: str,
        note: str | None = None,
        created_by: str = "user",
    ) -> dict[str, Any]:
        allowed_actions = {
            "acknowledge",
            "ignore_today",
            "add_to_review",
            "simulate_buy_plan",
            "simulate_sell_plan",
        }
        if action_type not in allowed_actions:
            raise ValueError(f"Unsupported monitoring action: {action_type}")
        alert = self.store.fetch_one("SELECT * FROM monitoring_alerts WHERE id = ?", (alert_id,))
        if not alert:
            raise ValueError("Monitoring alert not found")
        payload = {
            "symbol": alert["symbol"],
            "alert_type": alert["alert_type"],
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }
        with self.store.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO monitoring_alert_actions(
                    alert_id, action_type, note, created_by, payload_json
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    alert_id,
                    action_type,
                    note,
                    created_by,
                    json.dumps(payload, ensure_ascii=False),
                ),
            )
            action_id = int(cursor.lastrowid)
        lifecycle_change = self._sync_action_to_candidate_lifecycle(
            alert=dict(alert),
            action_id=action_id,
            action_type=action_type,
            note=note,
            created_by=created_by,
            payload=payload,
        )
        return {
            "id": action_id,
            "alert_id": alert_id,
            "action_type": action_type,
            "note": note,
            "created_by": created_by,
            "payload": payload,
            "candidate_lifecycle": lifecycle_change,
        }

    def alert_lifecycle(self, symbol: str | None = None, limit: int = 100) -> dict[str, Any]:
        clauses = []
        params: list[Any] = []
        if symbol:
            clauses.append("a.symbol = ?")
            params.append(symbol)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(max(1, min(limit, 500)))
        rows = self.store.fetch_all(
            f"""
            SELECT
                a.id AS alert_id,
                a.symbol,
                a.severity,
                a.alert_type,
                a.message,
                a.created_at AS alert_created_at,
                aa.id AS action_id,
                aa.action_type,
                aa.note,
                aa.created_by,
                aa.created_at AS action_created_at
            FROM monitoring_alerts a
            LEFT JOIN monitoring_alert_actions aa ON aa.alert_id = a.id
            {where}
            ORDER BY a.id DESC, aa.id ASC
            LIMIT ?
            """,
            tuple(params),
        )
        grouped: dict[int, dict[str, Any]] = {}
        for row in rows:
            alert_id = int(row["alert_id"])
            item = grouped.setdefault(
                alert_id,
                {
                    "alert_id": alert_id,
                    "symbol": row["symbol"],
                    "severity": row["severity"],
                    "alert_type": row["alert_type"],
                    "message": row["message"],
                    "created_at": row["alert_created_at"],
                    "state": "open",
                    "actions": [],
                },
            )
            if row["action_id"] is not None:
                action = {
                    "id": row["action_id"],
                    "action_type": row["action_type"],
                    "note": row["note"],
                    "created_by": row["created_by"],
                    "created_at": row["action_created_at"],
                }
                item["actions"].append(action)
                if row["action_type"] in {
                    "acknowledge",
                    "ignore_today",
                    "add_to_review",
                    "simulate_buy_plan",
                    "simulate_sell_plan",
                }:
                    item["state"] = row["action_type"]
        items = list(grouped.values())
        return {
            "items": items,
            "open_count": len([item for item in items if item["state"] == "open"]),
            "actioned_count": len([item for item in items if item["state"] != "open"]),
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _sync_action_to_candidate_lifecycle(
        self,
        alert: dict[str, Any],
        action_id: int,
        action_type: str,
        note: str | None,
        created_by: str,
        payload: dict[str, Any],
    ) -> dict[str, Any] | None:
        state_by_action = {
            "add_to_review": "pending_review",
            "simulate_buy_plan": "focus_watch",
            "simulate_sell_plan": "phase_guarded",
        }
        state = state_by_action.get(action_type)
        if not state:
            return None
        lifecycle_payload = {
            **payload,
            "monitoring_alert_id": alert["id"],
            "monitoring_action_id": action_id,
            "action_type": action_type,
            "note": note,
            "created_by": created_by,
        }
        return CandidateLifecycleService().upsert_state(
            symbol=alert["symbol"],
            name=None,
            state=state,
            source=f"monitoring_alert_action:{action_id}",
            score=None,
            rating="monitoring_action",
            risk_level=alert["severity"],
            reason=f"{action_type}: {alert['message']}",
            payload=lifecycle_payload,
            event_type="monitoring_alert_action",
        )

    def _resolve_symbols(
        self,
        symbols: list[str] | None,
        latest_scan: dict[str, Any],
        limit: int,
    ) -> list[dict[str, str | None]]:
        if symbols:
            return [{"symbol": symbol, "name": None} for symbol in symbols[:limit]]

        buckets = latest_scan.get("buckets", {})
        candidates = list(buckets.get("strong", [])) + list(buckets.get("watch", []))
        return [
            {"symbol": item.get("symbol"), "name": item.get("name")}
            for item in candidates[: max(1, min(limit, 20))]
            if item.get("symbol")
        ]

    def _monitor_symbol(self, session_id: int, item: dict[str, Any]) -> dict[str, Any]:
        symbol = item["symbol"]
        name = item.get("name")
        previous = self._latest_event_for_symbol(session_id, symbol)

        try:
            snapshot = MarketSnapshotBuilder().build(symbol, name)
            plan = SimulationPlanner().create_plan(snapshot)
            price_delta = self._delta(snapshot.price, previous.get("price") if previous else None)
            pct_delta = self._delta(snapshot.pct_change, previous.get("pct_change") if previous else None)
            if previous and price_delta == 0 and previous.get("data_source") == snapshot.metadata.get("source"):
                previous["alerts"] = []
                previous["deduped"] = True
                return previous

            signal = self._signal(
                snapshot.price,
                price_delta,
                pct_delta,
                plan.model_dump(mode="json"),
                snapshot,
                previous,
            )
            payload = {
                "session_id": session_id,
                "symbol": snapshot.symbol,
                "name": snapshot.name,
                "price": snapshot.price,
                "pct_change": snapshot.pct_change,
                "price_delta": price_delta,
                "pct_delta": pct_delta,
                "signal": signal,
                "decision_tier": plan.tier.value,
                "action": plan.action,
                "allowed": plan.allowed,
                "data_source": snapshot.metadata.get("source"),
                "snapshot": snapshot.model_dump(mode="json"),
                "plan": plan.model_dump(mode="json"),
            }
            payload["summary"] = self._summary(payload)
        except (ValueError, MarketDataError) as exc:
            payload = {
                "session_id": session_id,
                "symbol": symbol,
                "name": name,
                "price": None,
                "pct_change": None,
                "price_delta": None,
                "pct_delta": None,
                "signal": "data_error",
                "decision_tier": None,
                "action": None,
                "allowed": False,
                "data_source": None,
                "summary": f"{symbol} 行情失败: {exc}",
                "snapshot": {},
                "plan": {},
            }

        event_id = self._persist_event(payload)
        payload["id"] = event_id
        alerts = self._alerts_for_event(payload, previous)
        payload["alerts"] = [self._persist_alert(event_id, alert) for alert in alerts]
        return payload

    def _persist_event(self, payload: dict[str, Any]) -> int:
        with self.store.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO monitoring_events(
                    session_id, symbol, name, price, pct_change, price_delta,
                    pct_delta, signal, decision_tier, action, allowed, data_source,
                    summary, snapshot_json, plan_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["session_id"],
                    payload["symbol"],
                    payload.get("name"),
                    payload.get("price"),
                    payload.get("pct_change"),
                    payload.get("price_delta"),
                    payload.get("pct_delta"),
                    payload["signal"],
                    payload.get("decision_tier"),
                    payload.get("action"),
                    1 if payload.get("allowed") else 0,
                    payload.get("data_source"),
                    payload.get("summary"),
                    json.dumps(payload.get("snapshot", {}), ensure_ascii=False, default=str),
                    json.dumps(payload.get("plan", {}), ensure_ascii=False, default=str),
                ),
            )
            return int(cursor.lastrowid)

    def _persist_alert(self, event_id: int, alert: dict[str, Any]) -> dict[str, Any]:
        with self.store.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO monitoring_alerts(
                    session_id, event_id, symbol, severity, alert_type, message, payload_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    alert["session_id"],
                    event_id,
                    alert["symbol"],
                    alert["severity"],
                    alert["alert_type"],
                    alert["message"],
                    json.dumps(alert.get("payload", {}), ensure_ascii=False, default=str),
                ),
            )
            alert["id"] = int(cursor.lastrowid)
            return alert

    def _persist_review(
        self,
        session_id: int | None,
        symbol: str,
        title: str,
        summary: dict[str, Any],
    ) -> int:
        with self.store.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO monitoring_reviews(session_id, symbol, title, summary_json)
                VALUES (?, ?, ?, ?)
                """,
                (
                    session_id,
                    symbol,
                    title,
                    json.dumps(summary, ensure_ascii=False, default=str),
                ),
            )
            return int(cursor.lastrowid)

    def _latest_event_for_symbol(self, session_id: int, symbol: str) -> dict[str, Any] | None:
        row = self.store.fetch_one(
            """
            SELECT *
            FROM monitoring_events
            WHERE session_id = ? AND symbol = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (session_id, symbol),
        )
        return self._event_model(row) if row else None

    def _update_session_summary(self, session_id: int, summary: dict[str, Any]) -> None:
        with self.store.connect() as conn:
            conn.execute(
                """
                UPDATE monitoring_sessions
                SET summary_json = ?
                WHERE id = ?
                """,
                (json.dumps(summary, ensure_ascii=False, default=str), session_id),
            )

    def _session_model(self, row: dict[str, Any] | None) -> dict[str, Any] | None:
        if not row:
            return None
        row = dict(row)
        row["symbols"] = json.loads(row.pop("symbols_json") or "[]")
        row["summary"] = json.loads(row.pop("summary_json") or "{}")
        row["recent_events"] = self.list_events(session_id=row["id"], limit=20)
        row["recent_alerts"] = self.list_alerts(session_id=row["id"], limit=20)
        return row

    def _event_model(self, row: dict[str, Any]) -> dict[str, Any]:
        row = dict(row)
        row["allowed"] = bool(row.get("allowed"))
        row["snapshot"] = json.loads(row.pop("snapshot_json") or "{}")
        row["plan"] = json.loads(row.pop("plan_json") or "{}")
        return row

    def _alert_model(self, row: dict[str, Any]) -> dict[str, Any]:
        row = dict(row)
        row["payload"] = json.loads(row.pop("payload_json") or "{}")
        return row

    def _review_model(self, row: dict[str, Any]) -> dict[str, Any]:
        row = dict(row)
        row["summary"] = json.loads(row.pop("summary_json") or "{}")
        return row

    def _signal_counts(self, events: list[dict[str, Any]]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for event in events:
            signal = str(event.get("signal") or "unknown")
            counts[signal] = counts.get(signal, 0) + 1
        return counts

    def _severity_counts(self, alerts: list[dict[str, Any]]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for alert in alerts:
            severity = str(alert.get("severity") or "unknown")
            counts[severity] = counts.get(severity, 0) + 1
        return counts

    def _delta(self, current: float | None, previous: float | None) -> float | None:
        if current is None or previous is None:
            return None
        return round(float(current) - float(previous), 4)

    def _signal(
        self,
        price: float | None,
        price_delta: float | None,
        pct_delta: float | None,
        plan: dict[str, Any],
        snapshot: MarketSnapshot | None = None,
        previous: dict[str, Any] | None = None,
    ) -> str:
        if price is None:
            return "no_price"
        if snapshot and snapshot.pct_change is not None:
            limit_pct = float(snapshot.metadata.get("limit_up_threshold") or 10.0)
            if snapshot.pct_change <= -limit_pct + 1.5:
                return "limit_down_warning"
        if previous and price_delta is not None and pct_delta is not None:
            if price_delta > 0 and pct_delta > 1.5:
                return "strong_support_bounce"
        if plan.get("allowed"):
            return "sim_buy_allowed"
        if plan.get("tier") == "rejected":
            return "risk_blocked"
        if pct_delta is not None and pct_delta >= 1:
            return "momentum_up"
        if pct_delta is not None and pct_delta <= -1:
            return "momentum_down"
        if price_delta is not None and price_delta != 0:
            return "price_changed"
        return "observe"

    def _summary(self, event: dict[str, Any]) -> str:
        parts = [f"{event['symbol']} {event.get('name') or ''}".strip(), f"信号 {event['signal']}"]
        if event.get("price_delta") is not None:
            parts.append(f"价格变化 {float(event['price_delta']):+.2f}")
        if event.get("pct_delta") is not None:
            parts.append(f"涨跌幅变化 {float(event['pct_delta']):+.2f}")
        if event.get("action"):
            parts.append(f"模拟动作 {event['action']}")
        return "；".join(parts)

    def _alerts_for_event(
        self,
        event: dict[str, Any],
        previous: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        alerts = []
        base = {
            "session_id": event["session_id"],
            "symbol": event["symbol"],
            "payload": {
                "name": event.get("name"),
                "price": event.get("price"),
                "pct_change": event.get("pct_change"),
                "price_delta": event.get("price_delta"),
                "pct_delta": event.get("pct_delta"),
                "signal": event.get("signal"),
                "action": event.get("action"),
                "allowed": event.get("allowed"),
                "data_source": event.get("data_source"),
            },
        }

        if event.get("allowed"):
            alerts.append(
                {
                    **base,
                    "severity": "high",
                    "alert_type": "sim_buy_allowed",
                    "message": f"{event['symbol']} 模拟计划允许买入，需要人工复核。",
                }
            )

        if event.get("signal") == "limit_down_warning":
            alerts.append(
                {
                    **base,
                    "severity": "high",
                    "alert_type": "limit_down_warning",
                    "message": f"{event['symbol']} is near the limit-down threshold; review risk before any simulation action.",
                }
            )

        if event.get("signal") == "strong_support_bounce":
            alerts.append(
                {
                    **base,
                    "severity": "medium",
                    "alert_type": "strong_support_bounce",
                    "message": f"{event['symbol']} rebounded from the previous monitoring event; review manually.",
                }
            )

        if event.get("signal") == "data_error":
            alerts.append(
                {
                    **base,
                    "severity": "high",
                    "alert_type": "data_error",
                    "message": f"{event['symbol']} 行情获取失败，监控连续性中断。",
                }
            )

        if previous and previous.get("signal") != event.get("signal"):
            alerts.append(
                {
                    **base,
                    "severity": "medium",
                    "alert_type": "signal_changed",
                    "message": f"{event['symbol']} 信号从 {previous.get('signal')} 变为 {event.get('signal')}。",
                }
            )

        pct_delta = event.get("pct_delta")
        if pct_delta is not None and abs(float(pct_delta)) >= 1:
            alerts.append(
                {
                    **base,
                    "severity": "medium",
                    "alert_type": "pct_delta",
                    "message": f"{event['symbol']} 涨跌幅较上一轮变化 {float(pct_delta):+.2f}%。",
                }
            )

        price_delta = event.get("price_delta")
        previous_price = previous.get("price") if previous else None
        if price_delta is not None and previous_price:
            ratio = abs(float(price_delta)) / float(previous_price)
            if ratio >= 0.02:
                alerts.append(
                    {
                        **base,
                        "severity": "medium",
                        "alert_type": "price_delta",
                        "message": f"{event['symbol']} 价格较上一轮变化 {float(price_delta):+.2f}。",
                    }
                )

        if event.get("signal") == "risk_blocked":
            alerts.append(
                {
                    **base,
                    "severity": "low",
                    "alert_type": "risk_blocked_observe",
                    "message": f"{event['symbol']} 仍被风控阻断，仅保留观察。",
                }
            )

        if event.get("data_source") == "tencent_quote_fallback":
            alerts.append(
                {
                    **base,
                    "severity": "low",
                    "alert_type": "fallback_quote",
                    "message": f"{event['symbol']} 使用只读报价兜底，需在复盘中标注数据源。",
                }
            )

        return alerts

    def _review_diagnosis(
        self,
        event_count: int,
        allowed_count: int,
        risk_blocked_count: int,
        fallback_count: int,
        data_sources: list[str],
    ) -> str:
        if event_count == 0:
            return "暂无监控事件，不能形成有效复盘。"
        if allowed_count > 0:
            return "出现模拟买入允许信号，但必须人工复核，不能直接转实盘。"
        if risk_blocked_count == event_count:
            return "全部监控事件均被风控阻断，当前只适合观察和等待条件改善。"
        if fallback_count == event_count and data_sources == ["tencent_quote_fallback"]:
            return "全部事件依赖只读报价兜底，行情连续性需要在复盘中单独标注。"
        return "监控轨迹未出现高优先级买入信号，继续按事件流观察。"

    def _review_next_actions(
        self,
        allowed_count: int,
        risk_blocked_count: int,
        fallback_count: int,
        event_count: int,
    ) -> list[str]:
        actions = ["继续记录下一轮监控事件，观察信号是否从 risk_blocked 变化。"]
        if allowed_count > 0:
            actions.append("对模拟允许买入事件做人工复核，检查铁律、仓位和数据源。")
        if risk_blocked_count:
            actions.append("复核高位红线、风险标记和相似失败案例，避免追高。")
        if fallback_count:
            actions.append("标注只读报价兜底来源，后续补充更稳定的行情源。")
        if event_count < 3:
            actions.append("事件数量偏少，先积累更多轮次再判断主力动向。")
        return actions
