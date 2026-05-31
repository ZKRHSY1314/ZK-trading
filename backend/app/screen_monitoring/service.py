from __future__ import annotations

from datetime import datetime
import hashlib
import json
from typing import Any

from app.config import settings
from app.storage.sqlite_store import SQLiteStore


class ScreenMonitoringService:
    """V4.5 read-only screen observation ledger.

    The first version records operator/mock observations only. It intentionally
    avoids screenshot capture, OCR, clicks, typing, broker actions, or orders.
    """

    def __init__(self) -> None:
        self.store = SQLiteStore(settings.database_path)
        self.store.init()

    def capabilities(self) -> dict[str, Any]:
        return {
            "status": "read_only_ready",
            "stage": "V4.5-P0",
            "capture_provider": "manual_or_mock_only",
            "ocr_provider": "not_configured",
            "allowed_modes": [
                "manual_observation",
                "mock_observation",
                "status_reconciliation",
                "audit_evidence",
            ],
            "forbidden_modes": [
                "screen_click",
                "keyboard_type",
                "broker_action",
                "order_action",
                "credential_access",
                "live_auto_trading",
            ],
            "default_session_name": "screen_readonly_watch",
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": False,
        }

    def start_session(
        self,
        name: str = "screen_readonly_watch",
        source: str = "manual_or_mock",
        window_title: str | None = None,
    ) -> dict[str, Any]:
        safe_name = (name or "screen_readonly_watch").strip()[:80]
        safe_source = (source or "manual_or_mock").strip()[:80]
        with self.store.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO screen_monitoring_sessions(
                    name, status, source, window_title, summary_json,
                    review_only, simulation_only, live_trading_enabled
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    safe_name,
                    "running",
                    safe_source,
                    window_title,
                    json.dumps(self._empty_summary(), ensure_ascii=False),
                    1,
                    1,
                    0,
                ),
            )
            session_id = int(cursor.lastrowid)
        return self.get_session(session_id) or {"id": session_id}

    def latest_session(self) -> dict[str, Any]:
        row = self.store.fetch_one(
            """
            SELECT *
            FROM screen_monitoring_sessions
            ORDER BY id DESC
            LIMIT 1
            """
        )
        if not row:
            return {
                "status": "empty",
                "message": "No read-only screen monitoring session has been recorded.",
                "observations": [],
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": False,
            }
        return self._session_model(row, include_observations=True)

    def get_session(self, session_id: int) -> dict[str, Any] | None:
        row = self.store.fetch_one(
            "SELECT * FROM screen_monitoring_sessions WHERE id = ?",
            (session_id,),
        )
        if not row:
            return None
        return self._session_model(row, include_observations=True)

    def list_observations(self, limit: int = 20) -> list[dict[str, Any]]:
        rows = self.store.fetch_all(
            """
            SELECT *
            FROM screen_observations
            ORDER BY observed_at DESC, id DESC
            LIMIT ?
            """,
            (max(1, min(limit, 200)),),
        )
        return [self._observation_model(row) for row in rows]

    def record_observation(
        self,
        session_id: int | None = None,
        source: str = "manual",
        app_status: str = "unknown",
        window_title: str | None = None,
        confidence: float = 0.0,
        detected_items: list[dict[str, Any]] | None = None,
        warnings: list[str] | None = None,
        raw_payload: dict[str, Any] | None = None,
        artifact_ref: str | None = None,
        observed_at: str | None = None,
    ) -> dict[str, Any]:
        session = self.get_session(session_id) if session_id else self.latest_session()
        if not session or session.get("status") == "empty":
            session = self.start_session(window_title=window_title, source=source)
        safe_detected = detected_items or []
        safe_warnings = warnings or []
        safe_payload = raw_payload or {}
        observed_ts = self._normalize_observed_at(observed_at)
        safety_blocks = self._safety_blocks(safe_payload)
        if safety_blocks:
            safe_warnings = [*safe_warnings, *safety_blocks]
            safe_payload = {
                **safe_payload,
                "safety_blocks": safety_blocks,
                "blocked_from_execution": True,
            }
        dedupe_key = self._dedupe_key(
            int(session["id"]),
            source,
            app_status,
            window_title,
            observed_ts,
            safe_detected,
            safe_warnings,
        )
        with self.store.connect() as conn:
            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO screen_observations(
                    session_id, source, app_status, window_title, observed_at,
                    confidence, detected_items_json, warnings_json, raw_payload_json,
                    artifact_ref, dedupe_key, review_only, simulation_only, live_trading_enabled
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(session["id"]),
                    source[:80],
                    app_status[:80],
                    window_title,
                    observed_ts,
                    max(0.0, min(float(confidence or 0.0), 1.0)),
                    json.dumps(safe_detected, ensure_ascii=False, default=str),
                    json.dumps(safe_warnings, ensure_ascii=False, default=str),
                    json.dumps(safe_payload, ensure_ascii=False, default=str),
                    artifact_ref,
                    dedupe_key,
                    1,
                    1,
                    0,
                ),
            )
            inserted = cursor.rowcount > 0
        self._refresh_session_summary(int(session["id"]))
        row = self.store.fetch_one("SELECT * FROM screen_observations WHERE dedupe_key = ?", (dedupe_key,))
        observation = self._observation_model(row) if row else {}
        observation["inserted"] = inserted
        return observation

    def _refresh_session_summary(self, session_id: int) -> None:
        observations = self.store.fetch_all(
            "SELECT app_status, warnings_json FROM screen_observations WHERE session_id = ?",
            (session_id,),
        )
        status_counts: dict[str, int] = {}
        warning_count = 0
        for item in observations:
            status = str(item.get("app_status") or "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1
            warning_count += len(self._decode_json(item.get("warnings_json", "[]")))
        summary = {
            "observation_count": len(observations),
            "status_counts": status_counts,
            "warning_count": warning_count,
            "read_only": True,
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": False,
        }
        with self.store.connect() as conn:
            conn.execute(
                "UPDATE screen_monitoring_sessions SET summary_json = ? WHERE id = ?",
                (json.dumps(summary, ensure_ascii=False), session_id),
            )

    def _empty_summary(self) -> dict[str, Any]:
        return {
            "observation_count": 0,
            "status_counts": {},
            "warning_count": 0,
            "read_only": True,
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": False,
        }

    def _safety_blocks(self, payload: dict[str, Any]) -> list[str]:
        blocked_terms = (
            "click",
            "keyboard",
            "submit_order",
            "place_order",
            "broker_action",
            "credential",
            "password",
            "live_trading",
        )
        action_text = json.dumps(payload, ensure_ascii=False, default=str).lower()
        return [f"blocked_readonly_payload_term:{term}" for term in blocked_terms if term in action_text]

    def _normalize_observed_at(self, observed_at: str | None) -> str:
        if not observed_at:
            return datetime.now().isoformat(timespec="seconds")
        try:
            return datetime.fromisoformat(observed_at).replace(tzinfo=None).isoformat(timespec="seconds")
        except ValueError:
            return datetime.now().isoformat(timespec="seconds")

    def _dedupe_key(
        self,
        session_id: int,
        source: str,
        app_status: str,
        window_title: str | None,
        observed_at: str,
        detected_items: list[dict[str, Any]],
        warnings: list[str],
    ) -> str:
        payload = json.dumps(
            {
                "session_id": session_id,
                "source": source,
                "app_status": app_status,
                "window_title": window_title,
                "observed_at": observed_at,
                "detected_items": detected_items,
                "warnings": warnings,
            },
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _session_model(self, row: dict[str, Any], include_observations: bool = False) -> dict[str, Any]:
        item = dict(row)
        item["summary"] = self._decode_json(item.pop("summary_json", "{}"))
        item["review_only"] = bool(item.get("review_only"))
        item["simulation_only"] = bool(item.get("simulation_only"))
        item["live_trading_enabled"] = bool(item.get("live_trading_enabled"))
        if include_observations:
            rows = self.store.fetch_all(
                """
                SELECT *
                FROM screen_observations
                WHERE session_id = ?
                ORDER BY observed_at DESC, id DESC
                LIMIT 20
                """,
                (item["id"],),
            )
            item["observations"] = [self._observation_model(obs) for obs in rows]
        return item

    def _observation_model(self, row: dict[str, Any] | None) -> dict[str, Any]:
        if not row:
            return {}
        item = dict(row)
        item["detected_items"] = self._decode_json(item.pop("detected_items_json", "[]"))
        item["warnings"] = self._decode_json(item.pop("warnings_json", "[]"))
        item["raw_payload"] = self._decode_json(item.pop("raw_payload_json", "{}"))
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
