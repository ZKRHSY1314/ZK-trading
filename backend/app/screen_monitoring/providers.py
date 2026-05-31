from __future__ import annotations

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


def configured_screen_capture_provider(provider_name: str = "disabled") -> ScreenCaptureProvider:
    normalized = (provider_name or "disabled").strip().lower()
    if normalized == "fixture":
        return FixtureScreenCaptureProvider()
    return DisabledScreenCaptureProvider()
