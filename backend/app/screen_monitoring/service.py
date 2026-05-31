from __future__ import annotations

from datetime import datetime
import hashlib
import json
from typing import Any

from app.config import settings
from app.screen_monitoring.providers import (
    FixtureScreenCaptureProvider,
    ScreenCaptureProvider,
    configured_screen_capture_provider,
)
from app.storage.sqlite_store import SQLiteStore


class ScreenMonitoringService:
    """V4.5 read-only screen observation ledger.

    The first version records operator/mock observations only. It intentionally
    avoids screenshot capture, OCR, clicks, typing, broker actions, or orders.
    """

    def __init__(self, provider: ScreenCaptureProvider | None = None) -> None:
        self.store = SQLiteStore(settings.database_path)
        self.store.init()
        self.provider = provider or configured_screen_capture_provider(
            settings.screen_capture_provider,
            allow_real_capture=settings.screen_capture_allow_real_capture,
            allowed_windows=settings.screen_capture_allowed_windows,
            block_broker_windows=settings.screen_capture_block_broker_windows,
            broker_window_terms=settings.screen_capture_broker_window_terms,
        )

    def capabilities(self) -> dict[str, Any]:
        provider_capabilities = self.provider.capabilities()
        return {
            "status": "read_only_ready",
            "stage": "V4.5-P5",
            "capture_provider": provider_capabilities["provider"],
            "provider_status": provider_capabilities["status"],
            "provider_configured": provider_capabilities["configured"],
            "ocr_provider": "fixture_only" if provider_capabilities["fixture_replay_supported"] else "not_configured",
            "provider_capabilities": provider_capabilities,
            "allowed_modes": [
                "manual_observation",
                "mock_observation",
                "fixture_replay",
                "capture_preflight",
                "capture_artifact_stub",
                "artifact_review_queue",
                "artifact_retention_policy",
                "provider_readiness_runbook",
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

    def provider_readiness_runbook(self) -> dict[str, Any]:
        provider_capabilities = self.provider.capabilities()
        details = provider_capabilities.get("details") or {}
        provider = str(provider_capabilities.get("provider") or "unknown")
        configured = bool(provider_capabilities.get("configured"))
        allowed_windows = details.get("allowed_windows") or self._split_csv(settings.screen_capture_allowed_windows)
        broker_terms = details.get("broker_window_terms") or self._split_csv(settings.screen_capture_broker_window_terms)
        checks = [
            self._readiness_check(
                "provider_selected",
                provider != "disabled",
                provider,
                "fixture or local_safe",
                "default provider is disabled" if provider == "disabled" else "provider selected",
            ),
            self._readiness_check(
                "provider_configured",
                configured or provider == "fixture",
                str(configured),
                "true for local_safe, fixture-only for fixtures",
                provider_capabilities.get("last_error") or "provider configuration accepted",
            ),
            self._readiness_check(
                "harmless_window_allowlist",
                provider != "local_safe" or bool(allowed_windows),
                ", ".join(allowed_windows) if allowed_windows else "",
                "one or more non-broker harmless window titles",
                "local_safe requires SCREEN_CAPTURE_ALLOWED_WINDOWS before future capture attempts",
            ),
            self._readiness_check(
                "broker_window_denylist",
                bool(settings.screen_capture_block_broker_windows),
                str(settings.screen_capture_block_broker_windows),
                "true",
                "broker/trading windows must stay blocked",
            ),
            self._readiness_check(
                "broker_window_terms",
                bool(broker_terms),
                ", ".join(broker_terms[:8]),
                "broker, trading, 交易, 证券, 券商, etc.",
                "deny terms prevent accidental broker-window observation",
            ),
            self._readiness_check(
                "real_pixel_capture_adapter",
                False,
                str(provider_capabilities.get("capture_supported")),
                "false in V4.5-P5",
                "real screenshot capture is intentionally not implemented in this stage",
            ),
            self._readiness_check(
                "ocr_adapter",
                False,
                str(provider_capabilities.get("ocr_supported")),
                "false in V4.5-P5",
                "OCR execution is intentionally not implemented in this stage",
            ),
            self._readiness_check(
                "live_trading_disabled",
                not settings.enable_live_trading,
                str(settings.enable_live_trading),
                "false",
                "screen monitoring must not enable live trading",
            ),
        ]
        return {
            "status": self._readiness_status(provider, configured),
            "stage": "V4.5-P5",
            "active_provider": provider,
            "provider_status": provider_capabilities.get("status"),
            "provider_configured": configured,
            "checks": checks,
            "environment": {
                "SCREEN_CAPTURE_PROVIDER": settings.screen_capture_provider,
                "SCREEN_CAPTURE_ALLOW_REAL_CAPTURE": settings.screen_capture_allow_real_capture,
                "SCREEN_CAPTURE_ALLOWED_WINDOWS_SET": bool(settings.screen_capture_allowed_windows.strip()),
                "SCREEN_CAPTURE_BLOCK_BROKER_WINDOWS": settings.screen_capture_block_broker_windows,
                "SCREEN_CAPTURE_BROKER_WINDOW_TERMS_SET": bool(settings.screen_capture_broker_window_terms.strip()),
            },
            "runbook": {
                "safe_sequence": [
                    "Review /api/screen-monitoring/provider-readiness before changing any local screen config.",
                    "Use fixture replay to validate UI and persistence without touching the desktop.",
                    "Use capture preflight only against a harmless allowlisted window such as Notepad.",
                    "Use capture-stub to create metadata-only artifact evidence after preflight.",
                    "Sync artifact reviews and accept/reject metadata manually.",
                ],
                "safe_api_checks": [
                    "GET /api/screen-monitoring/capabilities",
                    "GET /api/screen-monitoring/providers",
                    "GET /api/screen-monitoring/provider-readiness",
                    "POST /api/screen-monitoring/capture-preflight",
                    "POST /api/screen-monitoring/capture-stub",
                    "GET /health",
                ],
                "blocked_actions": [
                    "screen_click",
                    "keyboard_type",
                    "real_pixel_capture",
                    "ocr_execution",
                    "broker_action",
                    "order_action",
                    "credential_access",
                    "live_auto_trading",
                ],
            },
            "next_safe_steps": self._readiness_next_steps(provider, configured, allowed_windows),
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": False,
        }

    def artifact_retention_policy(self) -> dict[str, Any]:
        return {
            "status": "metadata_only_policy",
            "artifact_kind": "screen_capture_stub_metadata",
            "retention_days": 7,
            "max_review_queue_items": 100,
            "artifact_schemes": ["artifact://screen_capture_stub", "fixture://screen_monitoring"],
            "pixel_data_stored": False,
            "real_screen_capture": False,
            "ocr_executed": False,
            "redaction": {
                "mode": "metadata_only_redacted",
                "redaction_required": True,
                "store_window_title": True,
                "store_pixel_data": False,
                "store_credentials": False,
                "store_account_numbers": False,
            },
            "review_queue": {
                "default_status": "pending_review",
                "allowed_decisions": ["accepted", "rejected"],
                "decision_effect": "audit_status_only",
            },
            "forbidden_actions": [
                "screen_click",
                "keyboard_type",
                "broker_action",
                "order_action",
                "credential_access",
                "pixel_storage",
                "ocr_execution",
                "live_auto_trading",
            ],
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": False,
        }

    def provider_capabilities(self) -> list[dict[str, Any]]:
        providers = [
            self.provider.capabilities(),
            configured_screen_capture_provider(
                "local_safe",
                allow_real_capture=settings.screen_capture_allow_real_capture,
                allowed_windows=settings.screen_capture_allowed_windows,
                block_broker_windows=settings.screen_capture_block_broker_windows,
                broker_window_terms=settings.screen_capture_broker_window_terms,
            ).capabilities(),
            FixtureScreenCaptureProvider().capabilities(),
            configured_screen_capture_provider("disabled").capabilities(),
        ]
        deduped: dict[str, dict[str, Any]] = {}
        for item in providers:
            deduped[str(item["provider"])] = {
                **item,
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": False,
            }
        return list(deduped.values())

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

    def replay_fixture(
        self,
        fixture_name: str = "trading_client_online",
        session_id: int | None = None,
    ) -> dict[str, Any]:
        provider = FixtureScreenCaptureProvider()
        draft = provider.capture_fixture(fixture_name)
        observation = self.record_observation(
            session_id=session_id,
            source=draft.source,
            app_status=draft.app_status,
            window_title=draft.window_title,
            confidence=draft.confidence,
            detected_items=draft.detected_items,
            warnings=draft.warnings,
            raw_payload=draft.raw_payload,
            artifact_ref=draft.artifact_ref,
            observed_at=draft.observed_at,
        )
        return {
            "status": "replayed",
            "provider": provider.name,
            "fixture_name": fixture_name,
            "observation": observation,
            "real_screen_capture": False,
            "ocr_executed": False,
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": False,
        }

    def capture_preflight(self, target_window_title: str | None = None) -> dict[str, Any]:
        result = self.provider.capture_preflight(target_window_title=target_window_title)
        app_status = "capture_preflight_ready" if result.get("capture_would_be_allowed") else "capture_preflight_blocked"
        warnings = [] if result.get("capture_would_be_allowed") else [str(result.get("reason") or "preflight_blocked")]
        observation = self.record_observation(
            source=f"preflight:{result.get('provider', 'unknown')}",
            app_status=app_status,
            window_title=target_window_title,
            confidence=1.0 if result.get("capture_would_be_allowed") else 0.2,
            detected_items=[
                {
                    "type": "capture_preflight",
                    "value": result.get("status"),
                    "reason": result.get("reason"),
                }
            ],
            warnings=warnings,
            raw_payload=result,
            artifact_ref=result.get("artifact_ref"),
        )
        return {
            **result,
            "observation": observation,
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": False,
        }

    def sync_artifact_review_queue(self, limit: int = 100) -> dict[str, Any]:
        rows = self.store.fetch_all(
            """
            SELECT *
            FROM screen_observations
            WHERE app_status IN ('capture_artifact_stub_ready', 'capture_artifact_stub_blocked')
               OR source LIKE 'capture_stub:%'
            ORDER BY observed_at DESC, id DESC
            LIMIT ?
            """,
            (max(1, min(limit, 500)),),
        )
        created = 0
        skipped = 0
        reviews: list[dict[str, Any]] = []
        for row in rows:
            review = self._ensure_artifact_review(self._observation_model(row))
            reviews.append(review)
            created += 1 if review.get("inserted") else 0
            skipped += 0 if review.get("inserted") else 1
        return {
            "status": "synced",
            "scanned_observation_count": len(rows),
            "created_review_count": created,
            "skipped_existing_count": skipped,
            "reviews": reviews,
            "policy": self.artifact_retention_policy(),
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": False,
        }

    def list_artifact_reviews(self, status: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
        normalized = (status or "").strip()
        params: tuple[Any, ...]
        where = ""
        if normalized:
            where = "WHERE r.review_status = ?"
            params = (normalized, max(1, min(limit, 200)))
        else:
            params = (max(1, min(limit, 200)),)
        rows = self.store.fetch_all(
            f"""
            SELECT r.*, o.source, o.app_status, o.window_title, o.observed_at,
                   o.confidence, o.detected_items_json, o.warnings_json, o.raw_payload_json,
                   o.dedupe_key, o.created_at AS observation_created_at
            FROM screen_artifact_reviews r
            JOIN screen_observations o ON o.id = r.observation_id
            {where}
            ORDER BY r.created_at DESC, r.id DESC
            LIMIT ?
            """,
            params,
        )
        return [self._artifact_review_model(row) for row in rows]

    def decide_artifact_review(
        self,
        review_id: int,
        decision: str,
        reviewed_by: str = "operator",
        note: str | None = None,
    ) -> dict[str, Any]:
        normalized = decision.strip().lower()
        if normalized not in {"accepted", "rejected"}:
            raise ValueError("artifact review decision must be accepted or rejected")
        reviewed_at = datetime.now().isoformat(timespec="seconds")
        with self.store.connect() as conn:
            cursor = conn.execute(
                """
                UPDATE screen_artifact_reviews
                SET review_status = ?, reviewed_by = ?, review_note = ?,
                    reviewed_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (normalized, reviewed_by[:80], note, reviewed_at, reviewed_at, review_id),
            )
            if cursor.rowcount == 0:
                raise ValueError(f"screen artifact review {review_id} not found")
        review = self.get_artifact_review(review_id)
        return review or {"id": review_id, "review_status": normalized}

    def get_artifact_review(self, review_id: int) -> dict[str, Any] | None:
        rows = self.store.fetch_all(
            """
            SELECT r.*, o.source, o.app_status, o.window_title, o.observed_at,
                   o.confidence, o.detected_items_json, o.warnings_json, o.raw_payload_json,
                   o.dedupe_key, o.created_at AS observation_created_at
            FROM screen_artifact_reviews r
            JOIN screen_observations o ON o.id = r.observation_id
            WHERE r.id = ?
            LIMIT 1
            """,
            (review_id,),
        )
        return self._artifact_review_model(rows[0]) if rows else None

    def capture_harmless_window_stub(self, target_window_title: str | None = None) -> dict[str, Any]:
        result = self.provider.capture_harmless_window_stub(target_window_title=target_window_title)
        preflight = result.get("preflight") or {}
        created = result.get("artifact_status") == "stub_created"
        reason = str(preflight.get("reason") or result.get("artifact_status") or "capture_artifact_stub_blocked")
        observation = self.record_observation(
            source=f"capture_stub:{result.get('provider', 'unknown')}",
            app_status="capture_artifact_stub_ready" if created else "capture_artifact_stub_blocked",
            window_title=target_window_title,
            confidence=1.0 if created else 0.2,
            detected_items=[
                {
                    "type": "capture_artifact_stub",
                    "value": result.get("artifact_status"),
                    "reason": reason,
                }
            ],
            warnings=[] if created else [reason],
            raw_payload=result,
            artifact_ref=result.get("artifact_ref"),
        )
        review = self._ensure_artifact_review(observation)
        return {
            **result,
            "observation": observation,
            "artifact_review": review,
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": False,
        }

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

    def _ensure_artifact_review(self, observation: dict[str, Any]) -> dict[str, Any]:
        observation_id = observation.get("id")
        if not observation_id:
            return {}
        raw_payload = observation.get("raw_payload") or {}
        artifact_status = str(raw_payload.get("artifact_status") or "not_created")
        policy = self.artifact_retention_policy()
        redaction = {
            "mode": policy["redaction"]["mode"],
            "redaction_applied": bool(raw_payload.get("redaction_applied")),
            "pixel_data_stored": False,
            "ocr_executed": False,
            "real_screen_capture": False,
            "operator_review_required": True,
        }
        with self.store.connect() as conn:
            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO screen_artifact_reviews(
                    observation_id, artifact_ref, artifact_status, review_status,
                    retention_policy_json, redaction_json,
                    review_only, simulation_only, live_trading_enabled
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(observation_id),
                    observation.get("artifact_ref"),
                    artifact_status,
                    "pending_review",
                    json.dumps(policy, ensure_ascii=False, default=str),
                    json.dumps(redaction, ensure_ascii=False, default=str),
                    1,
                    1,
                    0,
                ),
            )
            inserted = cursor.rowcount > 0
        review = self.store.fetch_one(
            """
            SELECT r.*, o.source, o.app_status, o.window_title, o.observed_at,
                   o.confidence, o.detected_items_json, o.warnings_json, o.raw_payload_json,
                   o.dedupe_key, o.created_at AS observation_created_at
            FROM screen_artifact_reviews r
            JOIN screen_observations o ON o.id = r.observation_id
            WHERE r.observation_id = ?
            """,
            (int(observation_id),),
        )
        item = self._artifact_review_model(review) if review else {}
        item["inserted"] = inserted
        return item

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

    def _readiness_status(self, provider: str, configured: bool) -> str:
        if provider == "disabled":
            return "disabled_needs_provider_selection"
        if provider == "fixture":
            return "fixture_only_ready"
        if provider == "local_safe" and configured:
            return "preflight_ready_metadata_only"
        if provider == "local_safe":
            return "needs_explicit_local_safe_config"
        return "unknown_provider_review_required"

    def _readiness_check(
        self,
        name: str,
        passed: bool,
        value: str,
        expected: str,
        reason: str,
    ) -> dict[str, Any]:
        return {
            "name": name,
            "status": "ready" if passed else "blocked",
            "value": value,
            "expected": expected,
            "reason": reason,
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": False,
        }

    def _readiness_next_steps(self, provider: str, configured: bool, allowed_windows: list[str]) -> list[str]:
        steps: list[str] = []
        if provider == "disabled":
            steps.append("Keep provider disabled for normal operation; use fixture replay for UI and persistence checks.")
            steps.append("If testing local_safe later, configure only harmless window titles and keep broker denylist enabled.")
        if provider == "local_safe" and not configured:
            steps.append("Set SCREEN_CAPTURE_ALLOW_REAL_CAPTURE=true only for a reviewed harmless-window test session.")
        if provider == "local_safe" and not allowed_windows:
            steps.append("Set SCREEN_CAPTURE_ALLOWED_WINDOWS to harmless titles such as Notepad or Calculator, never broker windows.")
        if provider == "local_safe" and configured:
            steps.append("Run capture preflight against the harmless allowlisted window before creating metadata-only stubs.")
        steps.append("Confirm /health reports live_trading_enabled=false before any screen-monitoring run.")
        return steps

    def _safety_blocks(self, payload: dict[str, Any]) -> list[str]:
        blocked_terms = (
            "click",
            "keyboard",
            "submit_order",
            "place_order",
            "broker_action",
            "credential",
            "password",
            "enable_live_trading",
            "live_auto_trading",
        )
        action_text = json.dumps(payload, ensure_ascii=False, default=str).lower()
        return [f"blocked_readonly_payload_term:{term}" for term in blocked_terms if term in action_text]

    def _split_csv(self, value: str | None) -> list[str]:
        return [item.strip() for item in (value or "").split(",") if item.strip()]

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

    def _artifact_review_model(self, row: dict[str, Any] | None) -> dict[str, Any]:
        if not row:
            return {}
        item = dict(row)
        item["retention_policy"] = self._decode_json(item.pop("retention_policy_json", "{}"))
        item["redaction"] = self._decode_json(item.pop("redaction_json", "{}"))
        observation = {
            "id": item.pop("observation_id"),
            "source": item.pop("source", None),
            "app_status": item.pop("app_status", None),
            "window_title": item.pop("window_title", None),
            "observed_at": item.pop("observed_at", None),
            "confidence": item.pop("confidence", 0),
            "detected_items": self._decode_json(item.pop("detected_items_json", "[]")),
            "warnings": self._decode_json(item.pop("warnings_json", "[]")),
            "raw_payload": self._decode_json(item.pop("raw_payload_json", "{}")),
            "artifact_ref": item.get("artifact_ref"),
            "dedupe_key": item.pop("dedupe_key", None),
            "created_at": item.pop("observation_created_at", None),
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": False,
        }
        item["observation"] = observation
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
