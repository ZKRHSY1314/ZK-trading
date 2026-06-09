from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any

from app.config import settings
from app.sim_cockpit.desktop_adapter import (
    EXECUTION_MODES,
    SCREEN_CLICK_CONFIRMATION,
    SIMULATION_MENU_RISK_TERMS,
    TonghuashunDesktopAdapter,
)
from app.storage.sqlite_store import SQLiteStore


SIMULATION_POSITIVE_TERMS = (
    "mncg",
    "simulation",
    "simulated",
    "paper",
    "\u6a21\u62df",
    "\u6a21\u62df\u7092\u80a1",
    "\u6a21\u62df\u76d8",
    "\u6a21\u62df\u4e70\u5165",
    "\u6a21\u62df\u5356\u51fa",
    "\u6a21\u62df\u59d4\u6258",
)

TONGHUASHUN_PROCESS_TERMS = (
    "hexin",
    "xiadan",
    "tonghuashun",
    "ths",
    "\u540c\u82b1\u987a",
)

DANGEROUS_REAL_TRADING_TERMS = (
    "broker_login",
    "broker account",
    "credential",
    "password",
    "live_trading",
    "real_money",
    "real_order",
    "cash_transfer",
    "bank_transfer",
    "broker_submit",
    "\u5b9e\u76d8",
    "\u771f\u5b9e",
    "\u666e\u901a\u4ea4\u6613",
    "\u771f\u5b9e\u59d4\u6258",
    "\u59d4\u6258\u4ea4\u6613",
    "\u5238\u5546\u767b\u5f55",
    "\u5238\u5546",
    "\u8d44\u91d1\u8d26\u53f7",
    "\u94f6\u8bc1",
    "\u94f6\u8bc1\u8f6c\u8d26",
    "\u878d\u8d44\u878d\u5238",
)

ACTION_WHITELIST = {"buy", "sell", "cancel"}
SIMULATED_CASH_BASE = 100000.0
MAX_DAILY_BUYS = 5
MAX_SYMBOL_DAILY_BUYS = 1
MAX_SINGLE_ACTION_RATIO = 0.10
MAX_SCREEN_CLICK_ACTION_RATIO = 0.02
MAX_SCREEN_CLICK_QUANTITY = 100
MAX_VERIFICATION_AGE_SECONDS = 15 * 60


def _json_dumps(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)


def _json_loads(value: str | None, fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def _compact_text(*values: Any) -> str:
    parts: list[str] = []
    for value in values:
        if value is None:
            continue
        if isinstance(value, str):
            parts.append(value)
        else:
            parts.append(_json_dumps(value))
    return " ".join(parts).lower()


def _terms_found(text: str, terms: tuple[str, ...]) -> list[str]:
    text_lower = text.lower()
    return [term for term in terms if term.lower() in text_lower]


def _hash_text(value: str | None) -> str | None:
    if not value:
        return None
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class SimCockpitService:
    """Verified Tonghuashun simulation account action gateway.

    The gateway records simulated account actions only after a recent verified
    simulation window. It never connects to broker APIs and never enables live
    trading. The first executor is an audit fixture so unit tests do not depend
    on a live desktop window.
    """

    def __init__(self) -> None:
        self.store = SQLiteStore(settings.database_path)
        self.store.init()
        self.desktop_adapter = TonghuashunDesktopAdapter()

    def status(self) -> dict[str, Any]:
        latest_verification = self._latest_verification()
        latest_actions = self.latest_actions(limit=10)
        latest_readbacks = self.latest_readbacks(limit=10)
        verified = bool(latest_verification and latest_verification.get("status") == "verified")
        blocked = bool(latest_verification and latest_verification.get("status") == "blocked")
        latest_real_click = any(
            bool((item.get("execution") or {}).get("real_screen_click_executed")) for item in latest_actions[:1]
        )
        return {
            "schema_version": "sim_cockpit_status.v1",
            "stage": "SIM-COCKPIT-P2",
            "gateway": "tonghuashun_simulation_action_gateway",
            "status": "blocked" if blocked else ("verified" if verified else "needs_verification"),
            "simulation_actions_allowed": verified and not settings.enable_live_trading,
            "full_auto_simulation_enabled": True,
            "real_trading_blocked": True,
            "broker_api_enabled": False,
            "credential_storage_enabled": False,
            "real_screen_click_executed": latest_real_click,
            "executor": "desktop_adapter_guarded",
            "default_execution_mode": "dry_run_screen",
            "allowed_execution_modes": sorted(EXECUTION_MODES),
            "desktop_adapter": self.desktop_adapter.capabilities(),
            "live_trading_enabled": settings.enable_live_trading,
            "latest_verification": latest_verification,
            "latest_actions": latest_actions,
            "latest_readbacks": latest_readbacks,
            "safety": {
                "requires_verified_mncg_window": True,
                "requires_tonghuashun_process_marker": True,
                "requires_desktop_verified_window_for_screen_click": True,
                "requires_coordinate_anchors_for_screen_click": True,
                "screen_click_confirmation": SCREEN_CLICK_CONFIRMATION,
                "hard_blocks": list(DANGEROUS_REAL_TRADING_TERMS),
                "review_only": False,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            },
        }

    def detect_desktop_window(
        self,
        target_title: str | None = None,
        record: bool = True,
        verified_by: str = "desktop_adapter",
    ) -> dict[str, Any]:
        detection = self.desktop_adapter.detect(target_title=target_title)
        if not record:
            return detection

        best = detection.get("best_window") or {}
        visible_text = " ".join(str(item) for item in best.get("child_texts") or [])
        window_title = best.get("title") or target_title
        window_payload = self._verification_window_payload(best)
        raw_payload = {
            "source": "desktop_adapter",
            "provider": detection.get("provider"),
            "detection_status": detection.get("status"),
            "window": window_payload,
            "coordinate_anchors": best.get("coordinate_anchors") or {},
            "blocked_reason_count": len(detection.get("blocked_reasons") or []),
        }
        detected_items = [
            {"type": "desktop_window", "value": window_title, "confidence": 0.9 if best else 0.0},
            {"type": "process_name", "value": best.get("process_name"), "confidence": 0.9 if best.get("process_name") else 0.0},
            {"type": "window_rect", "value": best.get("rect"), "confidence": 0.8 if best.get("rect") else 0.0},
        ]
        verification = self.verify_window(
            window_title=window_title,
            visible_text=visible_text,
            detected_items=detected_items,
            raw_payload=raw_payload,
            verified_by=verified_by,
            confidence=0.95 if detection.get("status") == "verified" else 0.0,
        )
        return {**detection, "verification": verification}

    def _verification_window_payload(self, window: dict[str, Any]) -> dict[str, Any]:
        uia = window.get("uia") or {}
        return {
            "hwnd": window.get("hwnd"),
            "pid": window.get("pid"),
            "title": window.get("title"),
            "process_path": window.get("process_path"),
            "process_name": window.get("process_name"),
            "rect": window.get("rect"),
            "child_texts": (window.get("child_texts") or [])[:120],
            "score": window.get("score"),
            "positive_terms": window.get("positive_terms") or [],
            "process_terms": window.get("process_terms") or [],
            "dangerous_terms": window.get("dangerous_terms") or [],
            "evidence_hash": window.get("evidence_hash"),
            "coordinate_anchors": window.get("coordinate_anchors") or {},
            "uia": {
                "status": uia.get("status"),
                "root_name": uia.get("root_name"),
                "root_type": uia.get("root_type"),
                "root_rect": uia.get("root_rect"),
                "texts": (uia.get("texts") or [])[:80],
            },
        }

    def verify_window(
        self,
        window_title: str | None = None,
        visible_text: str | None = None,
        detected_items: list[dict[str, Any]] | None = None,
        raw_payload: dict[str, Any] | None = None,
        verified_by: str = "operator",
        confidence: float = 0.0,
    ) -> dict[str, Any]:
        detected_items = detected_items or []
        raw_payload = raw_payload or {}
        evidence_text = _compact_text(window_title, visible_text, detected_items, raw_payload)
        positive_terms = _terms_found(evidence_text, SIMULATION_POSITIVE_TERMS)
        process_terms = _terms_found(evidence_text, TONGHUASHUN_PROCESS_TERMS)
        dangerous_terms = _terms_found(evidence_text, DANGEROUS_REAL_TRADING_TERMS)
        non_blocking_risk_terms: list[str] = []
        if positive_terms and ("mncg" in positive_terms or "\u6a21\u62df\u7092\u80a1" in positive_terms):
            non_blocking_risk_terms = [term for term in dangerous_terms if term in SIMULATION_MENU_RISK_TERMS]
            dangerous_terms = [term for term in dangerous_terms if term not in SIMULATION_MENU_RISK_TERMS]
        if non_blocking_risk_terms:
            raw_payload = {
                **raw_payload,
                "non_blocking_risk_terms": non_blocking_risk_terms,
            }

        blocked_reasons: list[str] = []
        if settings.enable_live_trading:
            blocked_reasons.append("live_trading_enabled")
        if dangerous_terms:
            blocked_reasons.append("dangerous_real_trading_terms_detected")
        if not process_terms:
            blocked_reasons.append("missing_tonghuashun_process_marker")
        if not (window_title or visible_text):
            blocked_reasons.append("missing_window_or_page_text")
        if not positive_terms:
            blocked_reasons.append("missing_mncg_or_simulation_marker")

        status = "blocked" if blocked_reasons else "verified"
        record = {
            "status": status,
            "window_title": window_title,
            "visible_text_hash": _hash_text(visible_text),
            "positive_terms": positive_terms,
            "process_terms": process_terms,
            "dangerous_terms": dangerous_terms,
            "detected_items": detected_items,
            "raw_payload": raw_payload,
            "blocked_reasons": blocked_reasons,
            "verified_by": verified_by,
            "confidence": max(0.0, min(float(confidence or 0.0), 1.0)),
            "simulation_mode_detected": bool(positive_terms),
            "real_trading_blocked": True,
            "live_trading_enabled": settings.enable_live_trading,
        }
        with self.store.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO sim_cockpit_window_verifications(
                    status, window_title, visible_text_hash, positive_terms_json,
                    process_terms_json, dangerous_terms_json, blocked_reasons_json,
                    detected_items_json, raw_payload_json, verified_by, confidence,
                    simulation_mode_detected, real_trading_blocked, live_trading_enabled
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    status,
                    window_title,
                    record["visible_text_hash"],
                    _json_dumps(positive_terms),
                    _json_dumps(process_terms),
                    _json_dumps(dangerous_terms),
                    _json_dumps(blocked_reasons),
                    _json_dumps(detected_items),
                    _json_dumps(raw_payload),
                    verified_by,
                    record["confidence"],
                    int(record["simulation_mode_detected"]),
                    1,
                    int(settings.enable_live_trading),
                ),
            )
            verification_id = int(cursor.lastrowid)
            conn.execute(
                """
                INSERT INTO events(event_type, payload_json)
                VALUES (?, ?)
                """,
                (
                    "sim_cockpit_window_verified" if status == "verified" else "sim_cockpit_window_blocked",
                    _json_dumps({**record, "verification_id": verification_id}),
                ),
            )
        return {**record, "id": verification_id}

    def buy(
        self,
        symbol: str,
        price: float | None,
        quantity: int | None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        return self.record_action("buy", symbol=symbol, price=price, quantity=quantity, **kwargs)

    def sell(
        self,
        symbol: str,
        price: float | None,
        quantity: int | None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        return self.record_action("sell", symbol=symbol, price=price, quantity=quantity, **kwargs)

    def cancel(self, order_id: str, **kwargs: Any) -> dict[str, Any]:
        return self.record_action("cancel", order_id=order_id, **kwargs)

    def record_action(
        self,
        action_type: str,
        symbol: str | None = None,
        price: float | None = None,
        quantity: int | None = None,
        order_id: str | None = None,
        signal_source: str = "manual_or_system",
        risk_result: dict[str, Any] | None = None,
        window_verification_id: int | None = None,
        requested_by: str = "operator",
        note: str | None = None,
        dry_run: bool = False,
        execution_mode: str = "audit_fixture",
        screen_confirmation: str | None = None,
        screen_coordinates: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        action = action_type.strip().lower()
        execution_mode = (execution_mode or "audit_fixture").strip().lower()
        if dry_run and execution_mode == "audit_fixture":
            execution_mode = "dry_run_screen"
        risk_result = risk_result or {}
        screen_coordinates = screen_coordinates or {}
        blocked_reasons = self._validate_action(
            action,
            symbol=symbol,
            price=price,
            quantity=quantity,
            order_id=order_id,
            signal_source=signal_source,
            risk_result=risk_result,
            window_verification_id=window_verification_id,
            note=note,
            dry_run=dry_run,
            execution_mode=execution_mode,
            screen_confirmation=screen_confirmation,
            screen_coordinates=screen_coordinates,
        )
        verification = self._verification_for_action(window_verification_id)
        if not verification or verification.get("status") != "verified":
            blocked_reasons.append("blocked_needs_verified_simulation_window")
        elif verification.get("live_trading_enabled"):
            blocked_reasons.append("blocked_verified_window_live_trading_enabled")
        elif execution_mode == "screen_click_simulation":
            blocked_reasons.extend(self._screen_click_verification_reasons(verification))

        if settings.enable_live_trading:
            blocked_reasons.append("blocked_live_trading_enabled")

        blocked_reasons = sorted(set(blocked_reasons))
        initial_status = "blocked" if blocked_reasons else ("dry_run" if dry_run else "executed")
        execution = self._build_execution_result(
            action,
            symbol=symbol,
            price=price,
            quantity=quantity,
            order_id=order_id,
            verification=verification,
            status=initial_status,
            dry_run=dry_run,
            execution_mode=execution_mode,
            screen_confirmation=screen_confirmation,
            screen_coordinates=screen_coordinates,
        )
        status = "blocked" if blocked_reasons else str(execution.get("status") or initial_status)
        if execution.get("blocked_reason"):
            blocked_reasons = sorted(set([*blocked_reasons, str(execution["blocked_reason"])]))
            status = "blocked"
        request_payload = {
            "action_type": action,
            "symbol": symbol,
            "price": price,
            "quantity": quantity,
            "order_id": order_id,
            "signal_source": signal_source,
            "risk_result": risk_result,
            "window_verification_id": window_verification_id,
            "requested_by": requested_by,
            "note": note,
            "dry_run": dry_run,
            "execution_mode": execution_mode,
            "screen_confirmation_provided": bool(screen_confirmation),
            "screen_coordinates": screen_coordinates,
            "review_only": False,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }
        verification_id = int(verification["id"]) if verification else None
        with self.store.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO sim_cockpit_actions(
                    verification_id, action_type, status, symbol, price, quantity,
                    order_id, signal_source, risk_result_json, request_json,
                    execution_json, blocked_reasons_json, requested_by
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    verification_id,
                    action,
                    status,
                    symbol,
                    price,
                    quantity,
                    order_id,
                    signal_source,
                    _json_dumps(risk_result),
                    _json_dumps(request_payload),
                    _json_dumps(execution),
                    _json_dumps(blocked_reasons),
                    requested_by,
                ),
            )
            action_id = int(cursor.lastrowid)
            conn.execute(
                """
                INSERT INTO events(event_type, payload_json)
                VALUES (?, ?)
                """,
                (
                    "sim_cockpit_action_" + status,
                    _json_dumps(
                        {
                            "action_id": action_id,
                            "verification_id": verification_id,
                            "action_type": action,
                            "symbol": symbol,
                            "status": status,
                            "blocked_reasons": blocked_reasons,
                            "execution": execution,
                            "simulation_only": True,
                            "live_trading_enabled": settings.enable_live_trading,
                        }
                    ),
                ),
            )
            self._insert_readback(
                conn,
                action_id=action_id,
                readback_type="execution_result",
                status=status,
                symbol=symbol,
                price=price,
                quantity=quantity,
                order_id=order_id,
                payload={
                    "action_id": action_id,
                    "verification_id": verification_id,
                    "execution_mode": execution_mode,
                    "execution": execution,
                    "blocked_reasons": blocked_reasons,
                    "source": "sim_cockpit_action_record",
                    "simulation_only": True,
                    "live_trading_enabled": settings.enable_live_trading,
                },
            )
        return {
            "id": action_id,
            "verification_id": verification_id,
            "action_type": action,
            "status": status,
            "symbol": symbol,
            "price": price,
            "quantity": quantity,
            "order_id": order_id,
            "signal_source": signal_source,
            "risk_result": risk_result,
            "blocked_reasons": blocked_reasons,
            "execution": execution,
            "execution_mode": execution_mode,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def latest_actions(self, limit: int = 20) -> list[dict[str, Any]]:
        rows = self.store.fetch_all(
            """
            SELECT *
            FROM sim_cockpit_actions
            ORDER BY id DESC
            LIMIT ?
            """,
            (max(1, min(int(limit or 20), 100)),),
        )
        return [self._hydrate_action(row) for row in rows]

    def latest_readbacks(self, limit: int = 20) -> list[dict[str, Any]]:
        rows = self.store.fetch_all(
            """
            SELECT *
            FROM sim_cockpit_readbacks
            ORDER BY id DESC
            LIMIT ?
            """,
            (max(1, min(int(limit or 20), 100)),),
        )
        return [self._hydrate_readback(row) for row in rows]

    def record_readback(
        self,
        action_id: int | None,
        readback_type: str,
        status: str,
        symbol: str | None = None,
        price: float | None = None,
        quantity: int | None = None,
        order_id: str | None = None,
        payload: dict[str, Any] | None = None,
        recorded_by: str = "operator",
    ) -> dict[str, Any]:
        payload = payload or {}
        payload_text = _compact_text(readback_type, status, symbol, price, quantity, order_id, payload)
        blocked_reasons = _terms_found(payload_text, DANGEROUS_REAL_TRADING_TERMS)
        normalized_status = "blocked" if blocked_reasons else (status or "observed")
        with self.store.connect() as conn:
            readback_id = self._insert_readback(
                conn,
                action_id=action_id,
                readback_type=readback_type,
                status=normalized_status,
                symbol=symbol,
                price=price,
                quantity=quantity,
                order_id=order_id,
                payload={
                    **payload,
                    "recorded_by": recorded_by,
                    "blocked_reasons": blocked_reasons,
                    "simulation_only": True,
                    "live_trading_enabled": settings.enable_live_trading,
                },
            )
        row = self.store.fetch_one("SELECT * FROM sim_cockpit_readbacks WHERE id = ?", (readback_id,))
        return self._hydrate_readback(row)

    def simulation_cockpit_run(self, limit: int = 5, requested_by: str = "automation_loop") -> dict[str, Any]:
        verification = self._latest_verification()
        if not verification or verification.get("status") != "verified":
            return {
                "status": "blocked",
                "reason": "blocked_needs_verified_simulation_window",
                "attempted_count": 0,
                "executed_count": 0,
                "blocked_count": 0,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            }

        plans = self._recent_simulation_plans(limit=max(1, min(int(limit or 5), 20)))
        actions: list[dict[str, Any]] = []
        for plan in plans:
            if not plan.get("allowed") or str(plan.get("action") or "").lower() not in {"buy", "observe"}:
                continue
            if str(plan.get("action") or "").lower() == "observe":
                continue
            symbol = plan.get("symbol")
            price = plan.get("price")
            quantity = plan.get("quantity") or 100
            if not symbol or price is None:
                continue
            actions.append(
                self.buy(
                    symbol=str(symbol),
                    price=float(price),
                    quantity=int(quantity),
                    signal_source="automation_simulation_plan",
                    risk_result={
                        "simulation_allowed": True,
                        "all_gates_passed": True,
                        "source": "automation_simulation_plan",
                    },
                    window_verification_id=int(verification["id"]),
                    requested_by=requested_by,
                    dry_run=True,
                    execution_mode="dry_run_screen",
                )
            )
            if len(actions) >= limit:
                break

        return {
            "status": "completed",
            "verification_id": verification["id"],
            "candidate_plan_count": len(plans),
            "attempted_count": len(actions),
            "executed_count": len([item for item in actions if item.get("status") == "executed"]),
            "blocked_count": len([item for item in actions if item.get("status") == "blocked"]),
            "actions": actions,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _validate_action(
        self,
        action: str,
        symbol: str | None,
        price: float | None,
        quantity: int | None,
        order_id: str | None,
        signal_source: str,
        risk_result: dict[str, Any],
        window_verification_id: int | None,
        note: str | None,
        dry_run: bool,
        execution_mode: str,
        screen_confirmation: str | None,
        screen_coordinates: dict[str, Any],
    ) -> list[str]:
        reasons: list[str] = []
        if action not in ACTION_WHITELIST:
            reasons.append("action_not_whitelisted")
        if execution_mode not in EXECUTION_MODES:
            reasons.append("execution_mode_not_whitelisted")

        payload_text = _compact_text(
            action,
            symbol,
            price,
            quantity,
            order_id,
            signal_source,
            risk_result,
            window_verification_id,
            note,
            execution_mode,
            screen_coordinates,
        )
        if _terms_found(payload_text, DANGEROUS_REAL_TRADING_TERMS):
            reasons.append("dangerous_real_trading_terms_detected")

        if action in {"buy", "sell"}:
            if not symbol or not re.match(r"^(SH|SZ|BJ)\d{6}$", str(symbol).upper()):
                reasons.append("invalid_a_share_symbol")
            if price is None or float(price) <= 0:
                reasons.append("invalid_price")
            if quantity is None or int(quantity) <= 0:
                reasons.append("invalid_quantity")
            elif int(quantity) % 100 != 0:
                reasons.append("quantity_must_be_lot_size_100")
            if not dry_run and risk_result.get("simulation_allowed") is not True:
                reasons.append("risk_gate_simulation_allowed_not_true")
            if not dry_run and risk_result.get("all_gates_passed") is False:
                reasons.append("risk_gate_failed")
            if action == "buy" and price is not None and quantity is not None:
                amount = float(price) * int(quantity)
                if amount > SIMULATED_CASH_BASE * MAX_SINGLE_ACTION_RATIO:
                    reasons.append("single_action_exceeds_10pct_simulated_cash")
                if execution_mode == "screen_click_simulation":
                    if int(quantity) > MAX_SCREEN_CLICK_QUANTITY:
                        reasons.append("screen_click_quantity_exceeds_first_test_limit")
                    if amount > SIMULATED_CASH_BASE * MAX_SCREEN_CLICK_ACTION_RATIO:
                        reasons.append("screen_click_amount_exceeds_2pct_simulated_cash")
                reasons.extend(self._daily_buy_limit_reasons(str(symbol).upper()))
        elif action == "cancel":
            if not order_id:
                reasons.append("missing_order_id_for_cancel")
        if execution_mode == "screen_click_simulation":
            if screen_confirmation != SCREEN_CLICK_CONFIRMATION:
                reasons.append("missing_screen_click_confirmation")
        return reasons

    def _daily_buy_limit_reasons(self, symbol: str) -> list[str]:
        row = self.store.fetch_one(
            """
            SELECT COUNT(*) AS cnt
            FROM sim_cockpit_actions
            WHERE action_type = 'buy'
              AND status = 'executed'
              AND datetime(created_at) >= datetime('now', '-1 day')
            """
        )
        symbol_row = self.store.fetch_one(
            """
            SELECT COUNT(*) AS cnt
            FROM sim_cockpit_actions
            WHERE action_type = 'buy'
              AND status = 'executed'
              AND upper(symbol) = ?
              AND datetime(created_at) >= datetime('now', '-1 day')
            """,
            (symbol,),
        )
        reasons: list[str] = []
        if int((row or {}).get("cnt") or 0) >= MAX_DAILY_BUYS:
            reasons.append("daily_buy_limit_reached")
        if int((symbol_row or {}).get("cnt") or 0) >= MAX_SYMBOL_DAILY_BUYS:
            reasons.append("symbol_daily_buy_limit_reached")
        return reasons

    def _screen_click_verification_reasons(self, verification: dict[str, Any]) -> list[str]:
        reasons: list[str] = []
        raw_payload = verification.get("raw_payload") or {}
        if raw_payload.get("source") != "desktop_adapter":
            reasons.append("screen_click_requires_desktop_adapter_verification")
        if not raw_payload.get("window"):
            reasons.append("screen_click_requires_detected_window")
        created_at = str(verification.get("created_at") or "")
        try:
            created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
            age_seconds = (now_utc - created.replace(tzinfo=None)).total_seconds()
            if age_seconds > MAX_VERIFICATION_AGE_SECONDS:
                reasons.append("screen_click_window_verification_expired")
        except ValueError:
            reasons.append("screen_click_window_verification_time_unreadable")
        return reasons

    def _insert_readback(
        self,
        conn: Any,
        action_id: int | None,
        readback_type: str,
        status: str,
        symbol: str | None,
        price: float | None,
        quantity: int | None,
        order_id: str | None,
        payload: dict[str, Any],
    ) -> int:
        cursor = conn.execute(
            """
            INSERT INTO sim_cockpit_readbacks(
                action_id, readback_type, status, symbol, price, quantity,
                order_id, payload_json, simulation_only, live_trading_enabled
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                action_id,
                readback_type,
                status,
                symbol,
                price,
                quantity,
                order_id,
                _json_dumps(payload),
                1,
                int(settings.enable_live_trading),
            ),
        )
        readback_id = int(cursor.lastrowid)
        conn.execute(
            """
            INSERT INTO events(event_type, payload_json)
            VALUES (?, ?)
            """,
            (
                "sim_cockpit_readback_recorded",
                _json_dumps(
                    {
                        "readback_id": readback_id,
                        "action_id": action_id,
                        "readback_type": readback_type,
                        "status": status,
                        "symbol": symbol,
                        "simulation_only": True,
                        "live_trading_enabled": settings.enable_live_trading,
                    }
                ),
            ),
        )
        return readback_id

    def _verification_for_action(self, verification_id: int | None) -> dict[str, Any] | None:
        if verification_id:
            row = self.store.fetch_one(
                """
                SELECT *
                FROM sim_cockpit_window_verifications
                WHERE id = ?
                """,
                (verification_id,),
            )
        else:
            row = self.store.fetch_one(
                """
                SELECT *
                FROM sim_cockpit_window_verifications
                ORDER BY id DESC
                LIMIT 1
                """
            )
        return self._hydrate_verification(row) if row else None

    def _latest_verification(self) -> dict[str, Any] | None:
        row = self.store.fetch_one(
            """
            SELECT *
            FROM sim_cockpit_window_verifications
            ORDER BY id DESC
            LIMIT 1
            """
        )
        return self._hydrate_verification(row) if row else None

    def _recent_simulation_plans(self, limit: int) -> list[dict[str, Any]]:
        rows = self.store.fetch_all(
            """
            SELECT symbol, payload_json, created_at
            FROM automation_events
            WHERE event_type = 'simulation_plan_created'
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        )
        plans: list[dict[str, Any]] = []
        for row in rows:
            payload = _json_loads(row.get("payload_json"), {})
            plan = payload.get("plan") or {}
            snapshot = payload.get("snapshot") or {}
            symbol = row.get("symbol") or snapshot.get("symbol")
            plans.append(
                {
                    "symbol": symbol,
                    "action": plan.get("action"),
                    "allowed": bool(plan.get("allowed")),
                    "quantity": plan.get("quantity"),
                    "price": snapshot.get("current_price") or snapshot.get("price"),
                    "created_at": row.get("created_at"),
                }
            )
        return plans

    def _build_execution_result(
        self,
        action: str,
        symbol: str | None,
        price: float | None,
        quantity: int | None,
        order_id: str | None,
        verification: dict[str, Any] | None,
        status: str,
        dry_run: bool,
        execution_mode: str,
        screen_confirmation: str | None,
        screen_coordinates: dict[str, Any],
    ) -> dict[str, Any]:
        base = {
            "executor": "fixture_audit_gateway" if execution_mode == "audit_fixture" else "desktop_adapter_guarded",
            "status": status,
            "action_type": action,
            "symbol": symbol,
            "price": price,
            "quantity": quantity,
            "order_id": order_id,
            "execution_mode": execution_mode,
            "requested_at": datetime.now().isoformat(timespec="seconds"),
            "pre_action_screenshot_ref": "fixture_not_captured",
            "post_action_screenshot_ref": "fixture_not_captured",
            "ocr_text_hash": None,
            "coordinates": [],
            "coordinate_plan": None,
            "simulated_account_action": status in {"executed", "dry_run"},
            "real_screen_click_executed": False,
            "dry_run": dry_run,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }
        if status == "blocked" or execution_mode == "audit_fixture":
            return base

        raw_payload = (verification or {}).get("raw_payload") or {}
        window = raw_payload.get("window") or {}
        if execution_mode == "detect_only":
            detection = self.desktop_adapter.detect()
            return {
                **base,
                "status": "dry_run",
                "detection": detection,
                "simulated_account_action": False,
            }

        coordinate_anchors = screen_coordinates or raw_payload.get("coordinate_anchors") or {}
        plan = self.desktop_adapter.build_coordinate_plan(
            action,
            window=window,
            symbol=symbol,
            price=price,
            quantity=quantity,
            order_id=order_id,
            coordinate_anchors=coordinate_anchors,
        )
        pre_capture = self.desktop_adapter.capture_window_screenshot(window, phase="before", action_type=action)
        result = {
            **base,
            "status": "dry_run" if execution_mode == "dry_run_screen" else "blocked",
            "coordinate_plan": plan,
            "coordinates": plan.get("steps") or [],
            "pre_action_screenshot_ref": pre_capture.get("artifact_ref") or pre_capture.get("reason"),
            "pre_action_screenshot": pre_capture,
            "simulated_account_action": execution_mode == "dry_run_screen",
            "real_screen_click_executed": False,
        }
        if execution_mode == "dry_run_screen":
            return result

        if screen_confirmation != SCREEN_CLICK_CONFIRMATION:
            return {**result, "blocked_reason": "missing_screen_click_confirmation"}
        if not plan.get("plan_ready_for_click"):
            return {**result, "blocked_reason": "coordinate_plan_not_ready_for_click"}

        execution = self.desktop_adapter.execute_coordinate_plan(window, plan)
        post_capture = self.desktop_adapter.capture_window_screenshot(window, phase="after", action_type=action)
        final_status = str(execution.get("status") or "failed")
        return {
            **result,
            "status": final_status,
            "execution_result": execution,
            "post_action_screenshot_ref": post_capture.get("artifact_ref") or post_capture.get("reason"),
            "post_action_screenshot": post_capture,
            "simulated_account_action": final_status == "executed",
            "real_screen_click_executed": bool(execution.get("real_screen_click_executed")),
        }

    def _hydrate_verification(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": row["id"],
            "status": row["status"],
            "window_title": row.get("window_title"),
            "visible_text_hash": row.get("visible_text_hash"),
            "positive_terms": _json_loads(row.get("positive_terms_json"), []),
            "process_terms": _json_loads(row.get("process_terms_json"), []),
            "dangerous_terms": _json_loads(row.get("dangerous_terms_json"), []),
            "blocked_reasons": _json_loads(row.get("blocked_reasons_json"), []),
            "detected_items": _json_loads(row.get("detected_items_json"), []),
            "raw_payload": _json_loads(row.get("raw_payload_json"), {}),
            "verified_by": row.get("verified_by"),
            "confidence": row.get("confidence"),
            "simulation_mode_detected": bool(row.get("simulation_mode_detected")),
            "real_trading_blocked": bool(row.get("real_trading_blocked")),
            "live_trading_enabled": bool(row.get("live_trading_enabled")),
            "created_at": row.get("created_at"),
        }

    def _hydrate_action(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": row["id"],
            "verification_id": row.get("verification_id"),
            "action_type": row.get("action_type"),
            "status": row.get("status"),
            "symbol": row.get("symbol"),
            "price": row.get("price"),
            "quantity": row.get("quantity"),
            "order_id": row.get("order_id"),
            "signal_source": row.get("signal_source"),
            "risk_result": _json_loads(row.get("risk_result_json"), {}),
            "request": _json_loads(row.get("request_json"), {}),
            "execution": _json_loads(row.get("execution_json"), {}),
            "blocked_reasons": _json_loads(row.get("blocked_reasons_json"), []),
            "requested_by": row.get("requested_by"),
            "created_at": row.get("created_at"),
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _hydrate_readback(self, row: dict[str, Any] | None) -> dict[str, Any]:
        if not row:
            return {}
        return {
            "id": row["id"],
            "action_id": row.get("action_id"),
            "readback_type": row.get("readback_type"),
            "status": row.get("status"),
            "symbol": row.get("symbol"),
            "price": row.get("price"),
            "quantity": row.get("quantity"),
            "order_id": row.get("order_id"),
            "payload": _json_loads(row.get("payload_json"), {}),
            "simulation_only": bool(row.get("simulation_only", True)),
            "live_trading_enabled": bool(row.get("live_trading_enabled")),
            "created_at": row.get("created_at"),
        }
