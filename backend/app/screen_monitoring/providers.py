from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol


@dataclass
class ScreenObservationDraft:
    source: str
    app_status: str
    window_title: str | None = None
    confidence: float = 0.0
    detected_items: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    raw_payload: dict[str, Any] = field(default_factory=dict)
    artifact_ref: str | None = None
    observed_at: str | None = None


class ScreenCaptureProvider(Protocol):
    name: str

    def configured(self) -> bool:
        ...

    def capabilities(self) -> dict[str, Any]:
        ...

    def capture_fixture(self, fixture_name: str = "trading_client_online") -> ScreenObservationDraft:
        ...

    def capture_preflight(self, target_window_title: str | None = None) -> dict[str, Any]:
        ...

    def capture_harmless_window_stub(self, target_window_title: str | None = None) -> dict[str, Any]:
        ...


class DisabledScreenCaptureProvider:
    name = "disabled"

    def configured(self) -> bool:
        return False

    def capabilities(self) -> dict[str, Any]:
        return {
            "provider": self.name,
            "status": "disabled",
            "configured": False,
            "capture_supported": False,
            "capture_preflight_supported": True,
            "capture_stub_supported": False,
            "ocr_supported": False,
            "fixture_replay_supported": False,
            "last_error": "No screen capture provider is enabled.",
            "details": {
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": False,
            },
        }

    def capture_fixture(self, fixture_name: str = "trading_client_online") -> ScreenObservationDraft:
        raise RuntimeError("Screen capture provider is disabled.")

    def capture_preflight(self, target_window_title: str | None = None) -> dict[str, Any]:
        return _preflight_result(
            provider=self.name,
            status="blocked",
            reason="screen_capture_provider_disabled",
            target_window_title=target_window_title,
            configured=False,
        )

    def capture_harmless_window_stub(self, target_window_title: str | None = None) -> dict[str, Any]:
        return _capture_stub_result(
            self.capture_preflight(target_window_title=target_window_title),
            artifact_status="not_created",
        )


class FixtureScreenCaptureProvider:
    name = "fixture"

    def configured(self) -> bool:
        return True

    def capabilities(self) -> dict[str, Any]:
        return {
            "provider": self.name,
            "status": "fixture_only",
            "configured": True,
            "capture_supported": False,
            "capture_preflight_supported": True,
            "capture_stub_supported": False,
            "ocr_supported": False,
            "fixture_replay_supported": True,
            "last_error": None,
            "details": {
                "fixture_names": sorted(FIXTURES),
                "real_screen_capture": False,
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": False,
            },
        }

    def capture_fixture(self, fixture_name: str = "trading_client_online") -> ScreenObservationDraft:
        fixture = FIXTURES.get(fixture_name) or FIXTURES["trading_client_online"]
        now = datetime.now().isoformat(timespec="seconds")
        return ScreenObservationDraft(
            source=f"{self.name}:{fixture_name}",
            app_status=fixture["app_status"],
            window_title=fixture["window_title"],
            confidence=float(fixture["confidence"]),
            detected_items=list(fixture["detected_items"]),
            warnings=list(fixture["warnings"]),
            raw_payload={
                "fixture_name": fixture_name,
                "fixture_replay": True,
                "real_screen_capture": False,
                "ocr_executed": False,
                "read_only": True,
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": False,
            },
            artifact_ref=f"fixture://screen_monitoring/{fixture_name}",
            observed_at=now,
        )

    def capture_preflight(self, target_window_title: str | None = None) -> dict[str, Any]:
        return _preflight_result(
            provider=self.name,
            status="blocked",
            reason="fixture_provider_cannot_capture_real_screen",
            target_window_title=target_window_title,
            configured=True,
        )

    def capture_harmless_window_stub(self, target_window_title: str | None = None) -> dict[str, Any]:
        return _capture_stub_result(
            self.capture_preflight(target_window_title=target_window_title),
            artifact_status="not_created",
        )


class LocalSafeScreenCaptureProvider:
    name = "local_safe"

    def __init__(
        self,
        allow_real_capture: bool = False,
        allowed_windows: list[str] | None = None,
        block_broker_windows: bool = True,
        broker_window_terms: list[str] | None = None,
    ) -> None:
        self.allow_real_capture = bool(allow_real_capture)
        self.allowed_windows = [item.strip() for item in allowed_windows or [] if item.strip()]
        self.block_broker_windows = bool(block_broker_windows)
        self.broker_window_terms = [item.strip().lower() for item in broker_window_terms or [] if item.strip()]

    def configured(self) -> bool:
        return self.allow_real_capture and bool(self.allowed_windows)

    def capabilities(self) -> dict[str, Any]:
        configured = self.configured()
        return {
            "provider": self.name,
            "status": "preflight_ready" if configured else "needs_explicit_config",
            "configured": configured,
            "capture_supported": False,
            "capture_preflight_supported": True,
            "capture_stub_supported": True,
            "ocr_supported": False,
            "fixture_replay_supported": False,
            "last_error": None if configured else "SCREEN_CAPTURE_ALLOW_REAL_CAPTURE and SCREEN_CAPTURE_ALLOWED_WINDOWS are required.",
            "details": {
                "allowed_windows": self.allowed_windows,
                "block_broker_windows": self.block_broker_windows,
                "broker_window_terms": self.broker_window_terms,
                "real_screen_capture": False,
                "preflight_only": True,
                "redaction_required": True,
                "operator_review_required": True,
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": False,
            },
        }

    def capture_fixture(self, fixture_name: str = "trading_client_online") -> ScreenObservationDraft:
        raise RuntimeError("local_safe provider does not replay fixtures.")

    def capture_preflight(self, target_window_title: str | None = None) -> dict[str, Any]:
        title = (target_window_title or "").strip()
        if not self.allow_real_capture:
            return _preflight_result(
                provider=self.name,
                status="blocked",
                reason="real_capture_not_explicitly_enabled",
                target_window_title=title,
                configured=False,
            )
        if not self.allowed_windows:
            return _preflight_result(
                provider=self.name,
                status="blocked",
                reason="allowed_window_list_empty",
                target_window_title=title,
                configured=False,
            )
        if not title:
            return _preflight_result(
                provider=self.name,
                status="blocked",
                reason="target_window_title_required",
                target_window_title=title,
                configured=self.configured(),
            )
        lower_title = title.lower()
        matched_broker_terms = [term for term in self.broker_window_terms if term and term in lower_title]
        if self.block_broker_windows and matched_broker_terms:
            return _preflight_result(
                provider=self.name,
                status="blocked",
                reason="broker_or_trading_window_blocked",
                target_window_title=title,
                configured=self.configured(),
                matched_terms=matched_broker_terms,
            )
        allow_match = any(allowed.lower() in lower_title for allowed in self.allowed_windows)
        if not allow_match:
            return _preflight_result(
                provider=self.name,
                status="blocked",
                reason="target_window_not_in_allowlist",
                target_window_title=title,
                configured=self.configured(),
                allowed_windows=self.allowed_windows,
            )
        return _preflight_result(
            provider=self.name,
            status="preflight_passed",
            reason="harmless_window_allowlisted",
            target_window_title=title,
            configured=True,
            allowed_windows=self.allowed_windows,
        )

    def capture_harmless_window_stub(self, target_window_title: str | None = None) -> dict[str, Any]:
        preflight = self.capture_preflight(target_window_title=target_window_title)
        if not preflight.get("capture_would_be_allowed"):
            return _capture_stub_result(preflight, artifact_status="blocked")
        return _capture_stub_result(preflight, artifact_status="stub_created")


FIXTURES: dict[str, dict[str, Any]] = {
    "trading_client_online": {
        "app_status": "online",
        "window_title": "Mock Trading Client - Read Only",
        "confidence": 0.86,
        "detected_items": [
            {"type": "window_status", "value": "online", "confidence": 0.9},
            {"type": "account_area", "value": "visible_redacted", "confidence": 0.82},
            {"type": "readonly_mode", "value": "enabled", "confidence": 0.95},
        ],
        "warnings": [],
    },
    "trading_client_warning_popup": {
        "app_status": "attention_required",
        "window_title": "Mock Trading Client - Warning",
        "confidence": 0.78,
        "detected_items": [
            {"type": "window_status", "value": "online", "confidence": 0.82},
            {"type": "popup", "value": "network_warning", "confidence": 0.74},
        ],
        "warnings": ["fixture_warning_popup_detected", "operator_review_required"],
    },
}


def _preflight_result(
    provider: str,
    status: str,
    reason: str,
    target_window_title: str | None,
    configured: bool,
    **extra: Any,
) -> dict[str, Any]:
    return {
        "status": status,
        "provider": provider,
        "reason": reason,
        "target_window_title": target_window_title,
        "configured": configured,
        "capture_preflight_supported": True,
        "capture_would_be_allowed": status == "preflight_passed",
        "real_screen_capture": False,
        "ocr_executed": False,
        "artifact_ref": None,
        "redaction_required": True,
        "operator_review_required": True,
        "review_only": True,
        "simulation_only": True,
        "live_trading_enabled": False,
        **extra,
    }


def _capture_stub_result(preflight: dict[str, Any], artifact_status: str) -> dict[str, Any]:
    artifact_ref = None
    if artifact_status == "stub_created":
        seed = "|".join(
            [
                str(preflight.get("provider") or "unknown"),
                str(preflight.get("target_window_title") or ""),
                datetime.now().isoformat(timespec="seconds"),
            ]
        )
        digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]
        artifact_ref = f"artifact://screen_capture_stub/{digest}"
    return {
        "status": "captured_stub" if artifact_status == "stub_created" else "blocked",
        "provider": preflight.get("provider"),
        "target_window_title": preflight.get("target_window_title"),
        "artifact_status": artifact_status,
        "artifact_ref": artifact_ref,
        "preflight": preflight,
        "real_screen_capture": False,
        "pixel_data_stored": False,
        "ocr_executed": False,
        "redaction_applied": artifact_status == "stub_created",
        "redaction_required": True,
        "operator_review_required": True,
        "review_only": True,
        "simulation_only": True,
        "live_trading_enabled": False,
    }


def _split_csv(value: str | None) -> list[str]:
    return [item.strip() for item in (value or "").split(",") if item.strip()]


def configured_screen_capture_provider(
    provider_name: str = "disabled",
    allow_real_capture: bool = False,
    allowed_windows: str | list[str] | None = None,
    block_broker_windows: bool = True,
    broker_window_terms: str | list[str] | None = None,
) -> ScreenCaptureProvider:
    normalized = (provider_name or "disabled").strip().lower()
    if normalized == "fixture":
        return FixtureScreenCaptureProvider()
    if normalized == "local_safe":
        return LocalSafeScreenCaptureProvider(
            allow_real_capture=allow_real_capture,
            allowed_windows=_split_csv(allowed_windows) if isinstance(allowed_windows, str) else allowed_windows,
            block_broker_windows=block_broker_windows,
            broker_window_terms=_split_csv(broker_window_terms)
            if isinstance(broker_window_terms, str)
            else broker_window_terms,
        )
    return DisabledScreenCaptureProvider()
