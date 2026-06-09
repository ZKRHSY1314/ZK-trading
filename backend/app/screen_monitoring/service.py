from __future__ import annotations

from datetime import datetime, timedelta
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
            "stage": "V4.5-P21",
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
                "provider_config_proposal",
                "provider_readiness_replay",
                "screen_readiness_audit_report",
                "screen_readiness_audit_acknowledgement",
                "screen_readiness_timeline",
                "screen_readiness_evidence_export",
                "screen_readiness_evidence_verifier",
                "screen_readiness_evidence_comparison",
                "screen_readiness_health_digest",
                "screen_readiness_digest_history_proposal",
                "screen_readiness_digest_history_migration_checklist",
                "screen_readiness_digest_history_migration_spec_verifier",
                "screen_readiness_digest_history_migration_spec_approval",
                "screen_readiness_digest_history_release_readiness",
                "screen_readiness_digest_history_approval_review",
                "screen_readiness_digest_history_release_package",
                "tonghuashun_simulation_observation",
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
            "stage": "V4.5-P21",
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

    def screen_readiness_audit_report(self, limit: int = 20) -> dict[str, Any]:
        safe_limit = max(1, min(limit, 100))
        capabilities = self.capabilities()
        readiness = self.provider_readiness_runbook()
        policy = self.artifact_retention_policy()
        session = self.latest_session()
        observations = self.list_observations(limit=safe_limit)
        artifact_reviews = self.list_artifact_reviews(limit=safe_limit)
        proposals = self.list_provider_config_proposals(limit=safe_limit)
        replay_runs = self.list_provider_replay_runs(limit=safe_limit)
        readiness_checks = readiness.get("checks") or []
        readiness_blocked = [item for item in readiness_checks if item.get("status") != "ready"]
        artifact_pending = [item for item in artifact_reviews if item.get("review_status") == "pending_review"]
        proposal_pending = [item for item in proposals if item.get("status") == "pending_review"]
        replay_blocked = [item for item in replay_runs if item.get("status") != "replay_passed"]
        observation_warnings = sum(len(item.get("warnings") or []) for item in observations)
        safety_matrix = self._screen_audit_safety_matrix(capabilities, readiness, policy, observations, artifact_reviews, proposals, replay_runs)
        blockers = [
            {
                "source": "provider_readiness",
                "name": item.get("name"),
                "reason": item.get("reason"),
                "status": item.get("status"),
            }
            for item in readiness_blocked
        ]
        blockers.extend(
            {
                "source": "provider_replay",
                "name": item.get("scenario_name"),
                "reason": "scenario replay did not pass all checks",
                "status": item.get("status"),
            }
            for item in replay_blocked[:5]
        )
        status = "review_required" if blockers or artifact_pending or proposal_pending else "readiness_evidence_clean"
        summary = {
            "readiness_status": readiness.get("status"),
            "active_provider": readiness.get("active_provider"),
            "provider_status": readiness.get("provider_status"),
            "ready_check_count": sum(1 for item in readiness_checks if item.get("status") == "ready"),
            "blocked_check_count": len(readiness_blocked),
            "observation_count": len(observations),
            "observation_warning_count": observation_warnings,
            "artifact_review_count": len(artifact_reviews),
            "artifact_pending_count": len(artifact_pending),
            "config_proposal_count": len(proposals),
            "config_pending_count": len(proposal_pending),
            "provider_replay_count": len(replay_runs),
            "provider_replay_blocked_count": len(replay_blocked),
            "safety_passed": all(item["status"] == "passed" for item in safety_matrix),
            "allowed_output": "review_only_screen_readiness_report",
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": False,
        }
        return {
            "status": status,
            "stage": "V4.5-P21",
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "summary": summary,
            "blockers": blockers[:20],
            "evidence": {
                "capabilities": {
                    "status": capabilities.get("status"),
                    "stage": capabilities.get("stage"),
                    "capture_provider": capabilities.get("capture_provider"),
                    "provider_status": capabilities.get("provider_status"),
                    "allowed_modes": capabilities.get("allowed_modes"),
                    "forbidden_modes": capabilities.get("forbidden_modes"),
                    "review_only": True,
                    "simulation_only": True,
                    "live_trading_enabled": False,
                },
                "provider_readiness": readiness,
                "artifact_policy": policy,
                "latest_session": session,
                "recent_observations": observations,
                "artifact_reviews": artifact_reviews,
                "config_proposals": proposals,
                "provider_replay_runs": replay_runs,
            },
            "safety_matrix": safety_matrix,
            "next_safe_steps": self._screen_audit_next_steps(
                blockers,
                artifact_pending,
                proposal_pending,
                replay_runs,
            ),
            "forbidden_actions": [
                "screen_click",
                "keyboard_type",
                "real_pixel_capture",
                "pixel_storage",
                "ocr_execution",
                "broker_action",
                "order_action",
                "credential_access",
                "live_auto_trading",
            ],
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": False,
        }

    def screen_readiness_evidence_export(self, limit: int = 50) -> dict[str, Any]:
        safe_limit = max(1, min(limit, 200))
        capabilities = self.capabilities()
        readiness = self.provider_readiness_runbook()
        report = self.screen_readiness_audit_report(limit=min(safe_limit, 100))
        acknowledgements = self.list_screen_readiness_audit_acknowledgements(limit=safe_limit)
        timeline = self.screen_readiness_timeline(limit=safe_limit)
        evidence_bundle = {
            "schema_version": "screen_readiness_evidence_export.v1",
            "status": "export_ready",
            "stage": "V4.5-P21",
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "bundle_scope": [
                "capabilities",
                "provider_readiness",
                "readiness_audit_report",
                "readiness_audit_acknowledgements",
                "readiness_timeline",
            ],
            "capabilities": capabilities,
            "provider_readiness": readiness,
            "readiness_audit_report": report,
            "readiness_audit_acknowledgements": acknowledgements,
            "readiness_timeline": timeline,
            "export_metadata": {
                "format": "json",
                "delivery": "api_response_only",
                "writes_file": False,
                "download_created": False,
                "operator_archive_ready": True,
                "allowed_output": "review_only_screen_readiness_evidence_export",
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": False,
            },
            "safety": self._screen_evidence_export_safety(capabilities, readiness, report, acknowledgements, timeline),
            "forbidden_actions": [
                "write_env",
                "execute_command",
                "screen_click",
                "keyboard_type",
                "inspect_window",
                "real_pixel_capture",
                "pixel_storage",
                "ocr_execution",
                "broker_action",
                "order_action",
                "credential_access",
                "live_auto_trading",
            ],
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": False,
        }
        evidence_bundle["bundle_hash"] = self._screen_evidence_export_hash(evidence_bundle)
        return evidence_bundle

    def verify_screen_readiness_evidence_export(self, limit: int = 50) -> dict[str, Any]:
        bundle = self.screen_readiness_evidence_export(limit=limit)
        checks = [
            self._screen_evidence_check(
                "schema_version",
                bundle.get("schema_version") == "screen_readiness_evidence_export.v1",
                bundle.get("schema_version"),
                "screen_readiness_evidence_export.v1",
                "export schema must be recognized before manual archive/review",
            ),
            self._screen_evidence_check(
                "bundle_hash_recomputable",
                bundle.get("bundle_hash") == self._screen_evidence_export_hash(bundle),
                bundle.get("bundle_hash"),
                self._screen_evidence_export_hash(bundle),
                "bundle hash must be reproducible after removing runtime timestamps",
            ),
            self._screen_evidence_check(
                "api_response_only",
                bundle.get("export_metadata", {}).get("delivery") == "api_response_only",
                bundle.get("export_metadata", {}).get("delivery"),
                "api_response_only",
                "verifier must not approve file writes or downloads",
            ),
            self._screen_evidence_check(
                "no_file_write",
                bundle.get("export_metadata", {}).get("writes_file") is False
                and bundle.get("safety", {}).get("writes_file") is False,
                {
                    "metadata": bundle.get("export_metadata", {}).get("writes_file"),
                    "safety": bundle.get("safety", {}).get("writes_file"),
                },
                False,
                "evidence export is review material only and must not write files",
            ),
            self._screen_evidence_check(
                "no_download",
                bundle.get("export_metadata", {}).get("download_created") is False
                and bundle.get("safety", {}).get("download_created") is False,
                {
                    "metadata": bundle.get("export_metadata", {}).get("download_created"),
                    "safety": bundle.get("safety", {}).get("download_created"),
                },
                False,
                "operator archive is manual; API must not create downloads",
            ),
            self._screen_evidence_check(
                "no_command_or_env_write",
                bundle.get("safety", {}).get("executes_commands") is False
                and bundle.get("safety", {}).get("writes_env") is False,
                {
                    "executes_commands": bundle.get("safety", {}).get("executes_commands"),
                    "writes_env": bundle.get("safety", {}).get("writes_env"),
                },
                False,
                "verifier must not approve command execution or env mutation",
            ),
            self._screen_evidence_check(
                "no_capture_or_ocr",
                bundle.get("safety", {}).get("real_screen_capture") is False
                and bundle.get("safety", {}).get("pixel_data_stored") is False
                and bundle.get("safety", {}).get("ocr_executed") is False,
                {
                    "real_screen_capture": bundle.get("safety", {}).get("real_screen_capture"),
                    "pixel_data_stored": bundle.get("safety", {}).get("pixel_data_stored"),
                    "ocr_executed": bundle.get("safety", {}).get("ocr_executed"),
                },
                False,
                "P12 verifier must remain metadata-only",
            ),
            self._screen_evidence_check(
                "no_broker_or_order",
                bundle.get("safety", {}).get("broker_action") is False
                and bundle.get("safety", {}).get("order_action") is False
                and bundle.get("safety", {}).get("credential_access") is False,
                {
                    "broker_action": bundle.get("safety", {}).get("broker_action"),
                    "order_action": bundle.get("safety", {}).get("order_action"),
                    "credential_access": bundle.get("safety", {}).get("credential_access"),
                },
                False,
                "screen evidence must never authorize broker, order, or credential operations",
            ),
            self._screen_evidence_check(
                "live_trading_disabled_everywhere",
                bundle.get("live_trading_enabled") is False
                and bundle.get("capabilities", {}).get("live_trading_enabled") is False
                and bundle.get("provider_readiness", {}).get("live_trading_enabled") is False
                and bundle.get("readiness_audit_report", {}).get("live_trading_enabled") is False
                and bundle.get("readiness_timeline", {}).get("live_trading_enabled") is False
                and bundle.get("export_metadata", {}).get("live_trading_enabled") is False
                and bundle.get("safety", {}).get("live_trading_enabled") is False,
                {
                    "bundle": bundle.get("live_trading_enabled"),
                    "capabilities": bundle.get("capabilities", {}).get("live_trading_enabled"),
                    "provider_readiness": bundle.get("provider_readiness", {}).get("live_trading_enabled"),
                    "readiness_audit_report": bundle.get("readiness_audit_report", {}).get("live_trading_enabled"),
                    "readiness_timeline": bundle.get("readiness_timeline", {}).get("live_trading_enabled"),
                    "export_metadata": bundle.get("export_metadata", {}).get("live_trading_enabled"),
                    "safety": bundle.get("safety", {}).get("live_trading_enabled"),
                },
                False,
                "all nested evidence must keep live trading disabled",
            ),
            self._screen_evidence_check(
                "required_bundle_sections_present",
                all(section in bundle for section in bundle.get("bundle_scope", []))
                and self._screen_required_paths_present(
                    bundle,
                    [
                        "capabilities.allowed_modes",
                        "provider_readiness.checks",
                        "readiness_audit_report.safety_matrix",
                        "readiness_audit_acknowledgements",
                        "readiness_timeline.items",
                        "export_metadata.allowed_output",
                        "safety.allowed_output",
                    ],
                ),
                bundle.get("bundle_scope"),
                "all scoped sections and safety paths present",
                "manual reviewers need complete evidence, not a partial bundle",
            ),
            self._screen_evidence_check(
                "forbidden_actions_declared",
                self._screen_forbidden_actions_covered(bundle),
                bundle.get("forbidden_actions"),
                [
                    "write_env",
                    "execute_command",
                    "screen_click",
                    "keyboard_type",
                    "real_pixel_capture",
                    "ocr_execution",
                    "broker_action",
                    "order_action",
                    "credential_access",
                    "live_auto_trading",
                ],
                "export must explicitly declare blocked dangerous actions",
            ),
            self._screen_evidence_check(
                "review_and_simulation_only",
                bundle.get("review_only") is True
                and bundle.get("simulation_only") is True
                and bundle.get("export_metadata", {}).get("review_only") is True
                and bundle.get("export_metadata", {}).get("simulation_only") is True,
                {
                    "bundle_review_only": bundle.get("review_only"),
                    "bundle_simulation_only": bundle.get("simulation_only"),
                    "metadata_review_only": bundle.get("export_metadata", {}).get("review_only"),
                    "metadata_simulation_only": bundle.get("export_metadata", {}).get("simulation_only"),
                },
                True,
                "verifier output is evidence for review and simulation only",
            ),
        ]
        failed = [item for item in checks if item["status"] != "passed"]
        return {
            "schema_version": "screen_readiness_evidence_verifier.v1",
            "status": "verification_passed" if not failed else "verification_failed",
            "stage": "V4.5-P21",
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "export_bundle_hash": bundle.get("bundle_hash"),
            "verified_export_stage": bundle.get("stage"),
            "check_count": len(checks),
            "passed_count": len(checks) - len(failed),
            "failed_count": len(failed),
            "checks": checks,
            "failed_checks": failed,
            "safety_summary": {
                "writes_file": False,
                "download_created": False,
                "executes_commands": False,
                "writes_env": False,
                "real_screen_capture": False,
                "pixel_data_stored": False,
                "ocr_executed": False,
                "broker_action": False,
                "order_action": False,
                "credential_access": False,
                "live_trading_enabled": False,
            },
            "allowed_output": "review_only_screen_readiness_evidence_verifier",
            "forbidden_actions": bundle.get("forbidden_actions", []),
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": False,
        }

    def compare_screen_readiness_evidence(self, limit: int = 50) -> dict[str, Any]:
        baseline = self.verify_screen_readiness_evidence_export(limit=limit)
        candidate = self.verify_screen_readiness_evidence_export(limit=limit)
        baseline_summary = self._screen_verification_comparison_summary(baseline)
        candidate_summary = self._screen_verification_comparison_summary(candidate)
        differences = self._screen_verification_differences(baseline_summary, candidate_summary)
        return {
            "schema_version": "screen_readiness_evidence_comparison.v1",
            "status": "comparison_stable" if not differences else "comparison_changed",
            "stage": "V4.5-P21",
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "baseline": baseline_summary,
            "candidate": candidate_summary,
            "difference_count": len(differences),
            "differences": differences,
            "comparison_scope": [
                "export_bundle_hash",
                "verification_status",
                "check_counts",
                "failed_check_names",
                "check_statuses",
                "safety_summary",
                "forbidden_actions",
            ],
            "safety_summary": {
                "writes_file": False,
                "download_created": False,
                "executes_commands": False,
                "writes_env": False,
                "real_screen_capture": False,
                "pixel_data_stored": False,
                "ocr_executed": False,
                "broker_action": False,
                "order_action": False,
                "credential_access": False,
                "live_trading_enabled": False,
            },
            "allowed_output": "review_only_screen_readiness_evidence_comparison",
            "forbidden_actions": baseline.get("forbidden_actions", []),
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": False,
        }

    def screen_readiness_health_digest(self, limit: int = 50) -> dict[str, Any]:
        safe_limit = max(1, min(limit, 200))
        capabilities = self.capabilities()
        readiness = self.provider_readiness_runbook()
        report = self.screen_readiness_audit_report(limit=min(safe_limit, 100))
        acknowledgements = self.list_screen_readiness_audit_acknowledgements(limit=safe_limit)
        timeline = self.screen_readiness_timeline(limit=safe_limit)
        export = self.screen_readiness_evidence_export(limit=safe_limit)
        verification = self.verify_screen_readiness_evidence_export(limit=safe_limit)
        comparison = self.compare_screen_readiness_evidence(limit=safe_limit)
        report_summary = report.get("summary", {})
        readiness_blocked = [
            item.get("name")
            for item in readiness.get("checks", [])
            if item.get("status") != "ready"
        ]
        health_flags = [
            self._screen_health_flag("live_trading_disabled", not settings.enable_live_trading, "live trading remains disabled"),
            self._screen_health_flag("verification_passed", verification.get("status") == "verification_passed", "evidence verifier passed"),
            self._screen_health_flag("comparison_stable", comparison.get("status") == "comparison_stable", "repeated verifier summaries are stable"),
            self._screen_health_flag("safety_matrix_passed", bool(report_summary.get("safety_passed")), "audit safety matrix passed"),
            self._screen_health_flag(
                "no_file_or_download",
                export.get("export_metadata", {}).get("writes_file") is False
                and export.get("export_metadata", {}).get("download_created") is False,
                "evidence output is API response only",
            ),
            self._screen_health_flag(
                "no_capture_or_ocr",
                export.get("safety", {}).get("real_screen_capture") is False
                and export.get("safety", {}).get("pixel_data_stored") is False
                and export.get("safety", {}).get("ocr_executed") is False,
                "digest did not require capture, pixels, or OCR",
            ),
            self._screen_health_flag(
                "no_broker_or_order",
                export.get("safety", {}).get("broker_action") is False
                and export.get("safety", {}).get("order_action") is False
                and export.get("safety", {}).get("credential_access") is False,
                "digest did not require broker, order, or credential access",
            ),
        ]
        failed_flags = [item for item in health_flags if item["status"] != "passed"]
        return {
            "schema_version": "screen_readiness_health_digest.v1",
            "status": "health_digest_clean" if not failed_flags else "health_digest_review_required",
            "stage": "V4.5-P21",
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "summary": {
                "capture_provider": capabilities.get("capture_provider"),
                "provider_status": capabilities.get("provider_status"),
                "readiness_status": readiness.get("status"),
                "audit_status": report.get("status"),
                "export_status": export.get("status"),
                "verification_status": verification.get("status"),
                "comparison_status": comparison.get("status"),
                "acknowledgement_count": len(acknowledgements),
                "timeline_item_count": timeline.get("item_count", 0),
                "readiness_blocked_count": len(readiness_blocked),
                "audit_blocked_check_count": report_summary.get("blocked_check_count", 0),
                "artifact_pending_count": report_summary.get("artifact_pending_count", 0),
                "config_pending_count": report_summary.get("config_pending_count", 0),
                "verification_failed_count": verification.get("failed_count", 0),
                "comparison_difference_count": comparison.get("difference_count", 0),
                "export_bundle_hash": export.get("bundle_hash"),
                "allowed_output": "review_only_screen_readiness_health_digest",
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": False,
            },
            "module_statuses": [
                self._screen_digest_module("capabilities", capabilities.get("status"), capabilities.get("stage"), capabilities.get("live_trading_enabled")),
                self._screen_digest_module("provider_readiness", readiness.get("status"), readiness.get("stage"), readiness.get("live_trading_enabled")),
                self._screen_digest_module("readiness_audit_report", report.get("status"), report.get("stage"), report.get("live_trading_enabled")),
                self._screen_digest_module("readiness_timeline", timeline.get("status"), timeline.get("stage"), timeline.get("live_trading_enabled")),
                self._screen_digest_module("evidence_export", export.get("status"), export.get("stage"), export.get("live_trading_enabled")),
                self._screen_digest_module("evidence_verifier", verification.get("status"), verification.get("stage"), verification.get("live_trading_enabled")),
                self._screen_digest_module("evidence_comparison", comparison.get("status"), comparison.get("stage"), comparison.get("live_trading_enabled")),
            ],
            "health_flags": health_flags,
            "failed_flags": failed_flags,
            "operator_notes": [
                "Digest is an API response only and does not persist evidence snapshots.",
                "Provider readiness may still require manual review when provider is disabled or local_safe is not configured.",
                "Any future real capture/OCR or broker workflow remains outside this digest and requires separate reviewed stages.",
            ],
            "safety_summary": {
                "writes_file": False,
                "download_created": False,
                "executes_commands": False,
                "writes_env": False,
                "real_screen_capture": False,
                "pixel_data_stored": False,
                "ocr_executed": False,
                "broker_action": False,
                "order_action": False,
                "credential_access": False,
                "live_trading_enabled": False,
            },
            "allowed_output": "review_only_screen_readiness_health_digest",
            "forbidden_actions": export.get("forbidden_actions", []),
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": False,
        }

    def screen_readiness_digest_history_proposal(self, limit: int = 50) -> dict[str, Any]:
        digest = self.screen_readiness_health_digest(limit=limit)
        summary = digest.get("summary", {})
        retention_fields = [
            "digest_status",
            "generated_at",
            "stage",
            "export_bundle_hash",
            "readiness_status",
            "audit_status",
            "verification_status",
            "comparison_status",
            "acknowledgement_count",
            "timeline_item_count",
            "readiness_blocked_count",
            "artifact_pending_count",
            "config_pending_count",
            "verification_failed_count",
            "comparison_difference_count",
            "failed_health_flag_names",
            "safety_summary",
        ]
        return {
            "schema_version": "screen_readiness_digest_history_proposal.v1",
            "status": "proposal_ready",
            "stage": "V4.5-P21",
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "proposal": {
                "name": "screen_readiness_digest_history",
                "purpose": "operator_review_only_digest_trend",
                "default_state": "not_persisted",
                "recommended_retention_days": 30,
                "max_records_per_day": 24,
                "dedupe_key": "export_bundle_hash + digest_status + failed_health_flag_names",
                "storage_mode": "future_reviewed_metadata_only_table",
                "required_fields": retention_fields,
                "excluded_fields": [
                    "raw_pixels",
                    "ocr_text",
                    "window_handles",
                    "broker_account",
                    "broker_credentials",
                    "orders",
                    "positions",
                    "full_screenshot",
                    "plaintext_secrets",
                ],
                "operator_review_required": True,
                "apply_automatically": False,
                "writes_database_now": False,
                "writes_file": False,
                "download_created": False,
                "executes_commands": False,
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": False,
            },
            "current_digest_summary": {
                "digest_status": digest.get("status"),
                "digest_stage": digest.get("stage"),
                "export_bundle_hash": summary.get("export_bundle_hash"),
                "readiness_status": summary.get("readiness_status"),
                "audit_status": summary.get("audit_status"),
                "verification_status": summary.get("verification_status"),
                "comparison_status": summary.get("comparison_status"),
                "failed_health_flag_names": [item.get("name") for item in digest.get("failed_flags", [])],
                "allowed_output": summary.get("allowed_output"),
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": False,
            },
            "review_gates": [
                self._screen_digest_history_gate("schema_review", True, "retention schema must be reviewed before persistence"),
                self._screen_digest_history_gate("retention_policy_review", True, "retention duration and dedupe policy require operator approval"),
                self._screen_digest_history_gate("safety_field_review", True, "stored metadata must exclude pixels, OCR text, broker data, orders, credentials, and secrets"),
                self._screen_digest_history_gate("migration_required", True, "future persistence requires an explicit SQLite migration and tests"),
                self._screen_digest_history_gate("manual_enable_required", True, "proposal does not enable any retention job automatically"),
            ],
            "safety_summary": {
                "writes_database_now": False,
                "writes_file": False,
                "download_created": False,
                "executes_commands": False,
                "writes_env": False,
                "real_screen_capture": False,
                "pixel_data_stored": False,
                "ocr_executed": False,
                "broker_action": False,
                "order_action": False,
                "credential_access": False,
                "live_trading_enabled": False,
            },
            "allowed_output": "review_only_screen_readiness_digest_history_proposal",
            "forbidden_actions": [
                "write_env",
                "execute_command",
                "write_file",
                "create_download",
                "persist_snapshot_without_review",
                "screen_click",
                "keyboard_type",
                "inspect_window",
                "real_pixel_capture",
                "pixel_storage",
                "ocr_execution",
                "broker_action",
                "order_action",
                "credential_access",
                "live_auto_trading",
            ],
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": False,
        }

    def screen_readiness_digest_history_migration_checklist(self, limit: int = 50) -> dict[str, Any]:
        proposal_doc = self.screen_readiness_digest_history_proposal(limit=limit)
        proposal = proposal_doc.get("proposal", {})
        current_digest = proposal_doc.get("current_digest_summary", {})
        required_fields = proposal.get("required_fields") or []
        excluded_fields = proposal.get("excluded_fields") or []
        forbidden_sensitive_fields = [
            "raw_pixels",
            "ocr_text",
            "broker_credentials",
            "orders",
            "positions",
            "plaintext_secrets",
        ]
        sensitive_fields_excluded = all(field in excluded_fields for field in forbidden_sensitive_fields)
        checks = [
            self._screen_digest_migration_check(
                "proposal_available",
                proposal_doc.get("status") == "proposal_ready",
                "P15 digest history proposal must exist before migration review",
            ),
            self._screen_digest_migration_check(
                "required_fields_defined",
                len(required_fields) >= 10,
                "future table fields must cover digest status, hashes, module statuses, counts, failed flags, and safety summary",
            ),
            self._screen_digest_migration_check(
                "sensitive_fields_excluded",
                sensitive_fields_excluded,
                "migration must exclude pixels, OCR text, broker data, orders, positions, credentials, and secrets",
            ),
            self._screen_digest_migration_check(
                "retention_policy_defined",
                int(proposal.get("recommended_retention_days") or 0) > 0 and int(proposal.get("max_records_per_day") or 0) > 0,
                "retention duration and per-day cap must be explicit before a migration can be reviewed",
            ),
            self._screen_digest_migration_check(
                "dedupe_key_defined",
                bool(proposal.get("dedupe_key")),
                "dedupe key must prevent repeated digest snapshots from expanding history indefinitely",
            ),
            self._screen_digest_migration_check(
                "current_digest_hash_available",
                bool(current_digest.get("export_bundle_hash")),
                "current digest export hash is required as the future history snapshot identity input",
            ),
            self._screen_digest_migration_check(
                "manual_operator_approval_required",
                bool(proposal.get("operator_review_required")) and not bool(proposal.get("apply_automatically")),
                "future persistence must require manual operator review and must not apply automatically",
            ),
            self._screen_digest_migration_check(
                "migration_file_required",
                False,
                "a future reviewed SQLite migration file is required before any table can be created",
                status_if_false="review_required",
            ),
            self._screen_digest_migration_check(
                "rollback_plan_required",
                False,
                "future migration must include a rollback plan and tests before persistence is enabled",
                status_if_false="review_required",
            ),
            self._screen_digest_migration_check(
                "persistence_not_enabled_now",
                not bool(proposal.get("writes_database_now")),
                "this endpoint must not create tables, insert snapshots, or enable retention jobs",
            ),
            self._screen_digest_migration_check(
                "live_trading_disabled",
                not settings.enable_live_trading and proposal_doc.get("live_trading_enabled") is False,
                "migration planning must preserve disabled live trading state",
            ),
        ]
        blocked_checks = [item for item in checks if item["status"] == "blocked"]
        review_required_checks = [item for item in checks if item["status"] == "review_required"]
        safety_summary = {
            "writes_database_now": False,
            "creates_table_now": False,
            "runs_migration_now": False,
            "writes_migration_file_now": False,
            "writes_file": False,
            "download_created": False,
            "executes_commands": False,
            "writes_env": False,
            "real_screen_capture": False,
            "pixel_data_stored": False,
            "ocr_executed": False,
            "broker_action": False,
            "order_action": False,
            "credential_access": False,
            "live_trading_enabled": False,
        }
        return {
            "schema_version": "screen_readiness_digest_history_migration_checklist.v1",
            "status": "migration_review_ready" if not blocked_checks else "migration_blocked",
            "stage": "V4.5-P21",
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "migration_plan": {
                "target_table": "screen_readiness_digest_history",
                "source_schema": proposal_doc.get("schema_version"),
                "source_digest_stage": current_digest.get("digest_stage"),
                "migration_type": "future_reviewed_sqlite_metadata_table",
                "default_state": "not_applied",
                "table_exists_now": False,
                "create_table_now": False,
                "backfill_now": False,
                "writes_database_now": False,
                "writes_migration_file_now": False,
                "apply_automatically": False,
                "operator_review_required": True,
                "rollback_required": True,
                "test_required": True,
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": False,
            },
            "field_mapping": [
                {"source": field, "target": field, "storage": "metadata_json_or_column"}
                for field in required_fields
            ],
            "excluded_fields": excluded_fields,
            "checks": checks,
            "summary": {
                "required_check_count": len(checks),
                "passed_check_count": len([item for item in checks if item["status"] == "passed"]),
                "review_required_count": len(review_required_checks),
                "blocked_check_count": len(blocked_checks),
                "migration_allowed_now": False,
                "manual_review_required": True,
                "current_export_bundle_hash": current_digest.get("export_bundle_hash"),
                "proposal_allowed_output": proposal_doc.get("allowed_output"),
                "allowed_output": "review_only_screen_readiness_digest_history_migration_checklist",
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": False,
            },
            "required_future_artifacts": [
                "reviewed_sqlite_migration",
                "rollback_plan",
                "migration_unit_tests",
                "api_smoke_tests",
                "forbidden_tracked_file_scan",
                "operator_approval_record",
            ],
            "safety_summary": safety_summary,
            "allowed_output": "review_only_screen_readiness_digest_history_migration_checklist",
            "forbidden_actions": [
                "create_table_now",
                "run_migration_now",
                "write_migration_file_now",
                "insert_digest_snapshot_now",
                "write_env",
                "execute_command",
                "write_file",
                "create_download",
                "screen_click",
                "keyboard_type",
                "inspect_window",
                "real_pixel_capture",
                "pixel_storage",
                "ocr_execution",
                "broker_action",
                "order_action",
                "credential_access",
                "live_auto_trading",
            ],
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": False,
        }

    def verify_screen_readiness_digest_history_migration_spec(
        self,
        spec_text: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        checklist = self.screen_readiness_digest_history_migration_checklist(limit=limit)
        target_table = str(checklist.get("migration_plan", {}).get("target_table") or "screen_readiness_digest_history")
        field_names = [str(item.get("target")) for item in checklist.get("field_mapping", []) if item.get("target")]
        spec = spec_text if spec_text is not None else self._default_digest_history_migration_spec(field_names)
        normalized = " ".join(spec.lower().split())
        dangerous_terms = [
            " drop ",
            " delete ",
            " insert ",
            " update ",
            " alter ",
            " pragma ",
            " attach ",
            " detach ",
            " vacuum ",
            " replace ",
            " truncate ",
        ]
        sensitive_terms = [
            "raw_pixels",
            "ocr_text",
            "broker_credentials",
            "broker_account",
            "orders",
            "positions",
            "plaintext_secrets",
            "full_screenshot",
        ]
        missing_fields = [
            field
            for field in field_names
            if field.lower() not in normalized
        ]
        dangerous_matches = [term.strip() for term in dangerous_terms if term in f" {normalized} "]
        sensitive_matches = [term for term in sensitive_terms if term in normalized]
        checks = [
            self._screen_digest_migration_spec_check(
                "spec_text_present",
                bool(spec.strip()),
                "migration spec text must be provided or generated from the safe default",
            ),
            self._screen_digest_migration_spec_check(
                "target_table_named",
                target_table.lower() in normalized,
                "spec must name the digest history target table",
            ),
            self._screen_digest_migration_spec_check(
                "create_table_shape_present",
                "create table" in normalized and "if not exists" in normalized,
                "dry-run spec should describe a guarded CREATE TABLE shape",
            ),
            self._screen_digest_migration_spec_check(
                "required_fields_covered",
                not missing_fields,
                "spec must cover every P15/P16 required metadata field",
                details={"missing_fields": missing_fields[:20]},
            ),
            self._screen_digest_migration_spec_check(
                "sensitive_fields_absent",
                not sensitive_matches,
                "spec must not include pixels, OCR text, broker data, orders, positions, credentials, or secrets",
                details={"sensitive_matches": sensitive_matches},
            ),
            self._screen_digest_migration_spec_check(
                "dangerous_sql_absent",
                not dangerous_matches,
                "dry-run verifier rejects destructive or data-mutating SQL terms",
                details={"dangerous_matches": dangerous_matches},
            ),
            self._screen_digest_migration_spec_check(
                "operator_approval_required",
                checklist.get("summary", {}).get("manual_review_required") is True,
                "operator approval must remain required before any future migration",
            ),
            self._screen_digest_migration_spec_check(
                "migration_not_allowed_now",
                checklist.get("summary", {}).get("migration_allowed_now") is False,
                "dry-run verification must not enable migration execution",
            ),
            self._screen_digest_migration_spec_check(
                "live_trading_disabled",
                not settings.enable_live_trading and checklist.get("live_trading_enabled") is False,
                "migration spec verification must preserve disabled live trading state",
            ),
        ]
        failed = [item for item in checks if item["status"] != "passed"]
        spec_hash = hashlib.sha256(spec.encode("utf-8")).hexdigest()
        safety_summary = {
            "executes_sql": False,
            "runs_migration_now": False,
            "creates_table_now": False,
            "writes_database_now": False,
            "writes_migration_file_now": False,
            "writes_file": False,
            "download_created": False,
            "executes_commands": False,
            "writes_env": False,
            "real_screen_capture": False,
            "pixel_data_stored": False,
            "ocr_executed": False,
            "broker_action": False,
            "order_action": False,
            "credential_access": False,
            "live_trading_enabled": False,
        }
        return {
            "schema_version": "screen_readiness_digest_history_migration_spec_verifier.v1",
            "status": "spec_verification_passed" if not failed else "spec_verification_failed",
            "stage": "V4.5-P21",
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "spec_hash": spec_hash,
            "spec_preview": spec[:800],
            "target_table": target_table,
            "check_count": len(checks),
            "passed_count": len(checks) - len(failed),
            "failed_count": len(failed),
            "checks": checks,
            "failed_checks": failed,
            "missing_fields": missing_fields,
            "safety_blocks": [
                {"name": "dangerous_sql", "matches": dangerous_matches, "blocked": bool(dangerous_matches)},
                {"name": "sensitive_fields", "matches": sensitive_matches, "blocked": bool(sensitive_matches)},
            ],
            "source_checklist_status": checklist.get("status"),
            "migration_allowed_now": False,
            "safety_summary": safety_summary,
            "allowed_output": "review_only_screen_readiness_digest_history_migration_spec_verifier",
            "forbidden_actions": [
                "execute_sql",
                "run_migration_now",
                "create_table_now",
                "write_migration_file_now",
                "insert_digest_snapshot_now",
                "write_env",
                "execute_command",
                "write_file",
                "create_download",
                "screen_click",
                "keyboard_type",
                "inspect_window",
                "real_pixel_capture",
                "pixel_storage",
                "ocr_execution",
                "broker_action",
                "order_action",
                "credential_access",
                "live_auto_trading",
            ],
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": False,
        }

    def approve_screen_readiness_digest_history_migration_spec(
        self,
        spec_text: str | None = None,
        approved_by: str = "operator",
        note: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        verification = self.verify_screen_readiness_digest_history_migration_spec(spec_text=spec_text, limit=limit)
        now = datetime.now().isoformat(timespec="seconds")
        verification_passed = verification.get("status") == "spec_verification_passed"
        approval = {
            "schema_version": "screen_readiness_digest_history_migration_spec_approval.v1",
            "status": "approval_metadata_recorded" if verification_passed else "approval_blocked",
            "stage": "V4.5-P21",
            "approved_at": now,
            "approved_by": (approved_by or "operator")[:80],
            "approval_note": note,
            "approval_effect": "audit_metadata_only",
            "spec_hash": verification.get("spec_hash"),
            "verification_status": verification.get("status"),
            "verification_failed_count": verification.get("failed_count", 0),
            "source_checklist_status": verification.get("source_checklist_status"),
            "migration_allowed_now": False,
            "future_migration_still_requires": [
                "reviewed_sqlite_migration",
                "rollback_plan",
                "migration_unit_tests",
                "api_smoke_tests",
                "forbidden_tracked_file_scan",
                "explicit_release_approval",
            ],
            "safety_summary": {
                "writes_database_event_now": verification_passed,
                "creates_table_now": False,
                "runs_migration_now": False,
                "executes_sql": False,
                "writes_digest_history_table_now": False,
                "writes_migration_file_now": False,
                "writes_file": False,
                "download_created": False,
                "executes_commands": False,
                "writes_env": False,
                "real_screen_capture": False,
                "pixel_data_stored": False,
                "ocr_executed": False,
                "broker_action": False,
                "order_action": False,
                "credential_access": False,
                "live_trading_enabled": False,
            },
            "allowed_output": "review_only_screen_readiness_digest_history_migration_spec_approval",
            "forbidden_actions": [
                "execute_sql",
                "run_migration_now",
                "create_table_now",
                "write_migration_file_now",
                "insert_digest_snapshot_now",
                "write_env",
                "execute_command",
                "write_file",
                "create_download",
                "screen_click",
                "keyboard_type",
                "inspect_window",
                "real_pixel_capture",
                "pixel_storage",
                "ocr_execution",
                "broker_action",
                "order_action",
                "credential_access",
                "live_auto_trading",
            ],
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": False,
        }
        if not verification_passed:
            approval["event_id"] = None
            approval["verification"] = verification
            return approval

        payload = dict(approval)
        payload["verification"] = {
            "schema_version": verification.get("schema_version"),
            "status": verification.get("status"),
            "spec_hash": verification.get("spec_hash"),
            "failed_count": verification.get("failed_count"),
            "allowed_output": verification.get("allowed_output"),
            "migration_allowed_now": verification.get("migration_allowed_now"),
            "live_trading_enabled": verification.get("live_trading_enabled"),
        }
        with self.store.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO events(event_type, payload_json)
                VALUES (?, ?)
                """,
                (
                    "screen_digest_migration_spec_approval",
                    json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str),
                ),
            )
            event_id = int(cursor.lastrowid or 0)
        approval["event_id"] = event_id
        approval["verification"] = payload["verification"]
        return approval

    def list_screen_readiness_digest_history_migration_spec_approvals(self, limit: int = 20) -> list[dict[str, Any]]:
        rows = self.store.fetch_all(
            """
            SELECT id, event_type, payload_json, created_at
            FROM events
            WHERE event_type = ?
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            ("screen_digest_migration_spec_approval", max(1, min(limit, 200))),
        )
        approvals: list[dict[str, Any]] = []
        for row in rows:
            payload = self._decode_json(row.get("payload_json") or "{}")
            item = payload if isinstance(payload, dict) else {}
            item["event_id"] = row.get("id")
            item["event_type"] = row.get("event_type")
            item["created_at"] = row.get("created_at")
            item["review_only"] = True
            item["simulation_only"] = True
            item["live_trading_enabled"] = False
            approvals.append(item)
        return approvals

    def screen_readiness_digest_history_release_readiness(self, limit: int = 50) -> dict[str, Any]:
        checklist = self.screen_readiness_digest_history_migration_checklist(limit=limit)
        verification = self.verify_screen_readiness_digest_history_migration_spec(limit=limit)
        approvals = self.list_screen_readiness_digest_history_migration_spec_approvals(limit=limit)
        latest_approval = approvals[0] if approvals else None
        checklist_ready = checklist.get("status") == "migration_review_ready"
        verification_ready = verification.get("status") == "spec_verification_passed"
        approval_ready = bool(latest_approval) and latest_approval.get("verification_status") == "spec_verification_passed"
        safety_ready = (
            verification.get("safety_summary", {}).get("executes_sql") is False
            and verification.get("safety_summary", {}).get("creates_table_now") is False
            and (latest_approval or {}).get("safety_summary", {}).get("runs_migration_now", False) is False
            and not settings.enable_live_trading
        )
        gates = [
            self._screen_digest_release_gate(
                "migration_checklist_ready",
                checklist_ready,
                "P16 migration readiness checklist must be review-ready",
            ),
            self._screen_digest_release_gate(
                "migration_spec_verified",
                verification_ready,
                "P17 dry-run migration spec verifier must pass",
            ),
            self._screen_digest_release_gate(
                "operator_approval_recorded",
                approval_ready,
                "P18 operator approval metadata is required before a release can be reviewed",
                status_if_false="review_required",
            ),
            self._screen_digest_release_gate(
                "latest_approval_matches_spec",
                bool(latest_approval) and latest_approval.get("spec_hash") == verification.get("spec_hash"),
                "latest approval must match the currently verified spec hash",
                status_if_false="review_required",
            ),
            self._screen_digest_release_gate(
                "no_migration_execution_enabled",
                verification.get("migration_allowed_now") is False
                and checklist.get("summary", {}).get("migration_allowed_now") is False
                and (latest_approval or {}).get("migration_allowed_now", False) is False,
                "release readiness summary must not enable migration execution",
            ),
            self._screen_digest_release_gate(
                "safety_summary_clean",
                safety_ready,
                "release readiness summary must preserve no SQL execution, no table creation, no migration, and disabled live trading",
            ),
        ]
        blocked = [gate for gate in gates if gate["status"] == "blocked"]
        review_required = [gate for gate in gates if gate["status"] == "review_required"]
        if blocked:
            status = "release_blocked"
        elif review_required:
            status = "release_review_required"
        else:
            status = "release_evidence_ready"
        safety_summary = {
            "executes_sql": False,
            "runs_migration_now": False,
            "creates_table_now": False,
            "writes_database_now": False,
            "writes_digest_history_table_now": False,
            "writes_migration_file_now": False,
            "writes_file": False,
            "download_created": False,
            "executes_commands": False,
            "writes_env": False,
            "real_screen_capture": False,
            "pixel_data_stored": False,
            "ocr_executed": False,
            "broker_action": False,
            "order_action": False,
            "credential_access": False,
            "live_trading_enabled": False,
        }
        return {
            "schema_version": "screen_readiness_digest_history_release_readiness.v1",
            "status": status,
            "stage": "V4.5-P21",
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "decision": {
                "go_no_go": "go_for_manual_release_review" if status == "release_evidence_ready" else "no_go",
                "migration_allowed_now": False,
                "requires_human_release_approval": True,
                "reason": "all evidence gates passed" if status == "release_evidence_ready" else "release evidence is incomplete or requires review",
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": False,
            },
            "evidence": {
                "checklist_status": checklist.get("status"),
                "verification_status": verification.get("status"),
                "verification_failed_count": verification.get("failed_count"),
                "approval_count": len(approvals),
                "latest_approval_status": latest_approval.get("status") if latest_approval else None,
                "latest_approval_event_id": latest_approval.get("event_id") if latest_approval else None,
                "spec_hash": verification.get("spec_hash"),
                "approved_spec_hash": latest_approval.get("spec_hash") if latest_approval else None,
                "allowed_output": "review_only_screen_readiness_digest_history_release_readiness",
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": False,
            },
            "gates": gates,
            "blocked_gates": blocked,
            "review_required_gates": review_required,
            "required_before_actual_migration": [
                "separate_reviewed_migration_file",
                "rollback_plan",
                "migration_tests",
                "api_smoke_tests",
                "database_backup_plan",
                "explicit_operator_release_approval",
            ],
            "safety_summary": safety_summary,
            "allowed_output": "review_only_screen_readiness_digest_history_release_readiness",
            "forbidden_actions": [
                "execute_sql",
                "run_migration_now",
                "create_table_now",
                "write_migration_file_now",
                "insert_digest_snapshot_now",
                "write_env",
                "execute_command",
                "write_file",
                "create_download",
                "screen_click",
                "keyboard_type",
                "inspect_window",
                "real_pixel_capture",
                "pixel_storage",
                "ocr_execution",
                "broker_action",
                "order_action",
                "credential_access",
                "live_auto_trading",
            ],
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": False,
        }

    def screen_readiness_digest_history_approval_review(
        self,
        limit: int = 50,
        max_age_days: int = 7,
    ) -> dict[str, Any]:
        safe_max_age_days = max(1, min(max_age_days, 365))
        release = self.screen_readiness_digest_history_release_readiness(limit=limit)
        verification = self.verify_screen_readiness_digest_history_migration_spec(limit=limit)
        approvals = self.list_screen_readiness_digest_history_migration_spec_approvals(limit=limit)
        latest_approval = approvals[0] if approvals else None
        now = datetime.now()
        approval_time = self._parse_datetime(
            latest_approval.get("approved_at") or latest_approval.get("created_at") if latest_approval else None
        )
        approval_age_hours = round((now - approval_time).total_seconds() / 3600, 3) if approval_time else None
        approval_age_days = round(float(approval_age_hours or 0) / 24, 3) if approval_age_hours is not None else None
        expires_at = (
            (approval_time + timedelta(days=safe_max_age_days)).isoformat(timespec="seconds")
            if approval_time
            else None
        )
        current_spec_hash = verification.get("spec_hash")
        approved_spec_hash = latest_approval.get("spec_hash") if latest_approval else None
        approval_recorded = bool(latest_approval)
        approval_not_expired = bool(approval_time) and approval_age_days is not None and approval_age_days <= safe_max_age_days
        spec_hash_matches = bool(latest_approval) and approved_spec_hash == current_spec_hash
        release_ready = release.get("status") == "release_evidence_ready"
        gates = [
            self._screen_digest_release_gate(
                "approval_recorded",
                approval_recorded,
                "latest operator approval metadata must exist before migration release review",
                status_if_false="review_required",
            ),
            self._screen_digest_release_gate(
                "approval_within_validity_window",
                approval_not_expired,
                f"approval metadata must be newer than {safe_max_age_days} day(s)",
                status_if_false="review_required",
            ),
            self._screen_digest_release_gate(
                "approval_matches_current_spec",
                spec_hash_matches,
                "latest approval spec hash must match the currently verified migration spec hash",
                status_if_false="review_required",
            ),
            self._screen_digest_release_gate(
                "release_readiness_evidence_ready",
                release_ready,
                "P19 release readiness must be evidence-ready before approval can be treated as current",
                status_if_false="review_required",
            ),
            self._screen_digest_release_gate(
                "no_migration_execution_enabled",
                release.get("decision", {}).get("migration_allowed_now") is False
                and verification.get("migration_allowed_now") is False
                and (latest_approval or {}).get("migration_allowed_now", False) is False,
                "approval review must not enable migration execution",
            ),
            self._screen_digest_release_gate(
                "live_trading_disabled",
                not settings.enable_live_trading
                and release.get("live_trading_enabled") is False
                and verification.get("live_trading_enabled") is False,
                "live trading must remain disabled",
            ),
        ]
        blocked = [gate for gate in gates if gate["status"] == "blocked"]
        review_required = [gate for gate in gates if gate["status"] == "review_required"]
        if blocked:
            status = "approval_review_blocked"
        elif not approval_recorded:
            status = "approval_review_required"
        elif review_required:
            status = "approval_rotation_required"
        else:
            status = "approval_current"
        next_required_action = "none"
        if status == "approval_review_required":
            next_required_action = "record_operator_approval_metadata"
        elif status == "approval_rotation_required":
            next_required_action = "refresh_operator_approval_metadata"
        elif status == "approval_review_blocked":
            next_required_action = "resolve_blocked_release_evidence"
        return {
            "schema_version": "screen_readiness_digest_history_approval_review.v1",
            "status": status,
            "stage": "V4.5-P21",
            "generated_at": now.isoformat(timespec="seconds"),
            "review_policy": {
                "max_age_days": safe_max_age_days,
                "rotation_required_when": [
                    "approval_missing",
                    "approval_expired",
                    "spec_hash_changed",
                    "release_readiness_not_ready",
                ],
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": False,
            },
            "latest_approval": {
                "event_id": latest_approval.get("event_id") if latest_approval else None,
                "status": latest_approval.get("status") if latest_approval else None,
                "approved_at": latest_approval.get("approved_at") if latest_approval else None,
                "created_at": latest_approval.get("created_at") if latest_approval else None,
                "approved_by": latest_approval.get("approved_by") if latest_approval else None,
                "spec_hash": approved_spec_hash,
                "verification_status": latest_approval.get("verification_status") if latest_approval else None,
                "approval_age_hours": approval_age_hours,
                "approval_age_days": approval_age_days,
                "expires_at": expires_at,
                "is_expired": False if approval_not_expired else bool(latest_approval),
                "matches_current_spec": spec_hash_matches,
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": False,
            },
            "current_spec": {
                "spec_hash": current_spec_hash,
                "verification_status": verification.get("status"),
                "failed_count": verification.get("failed_count"),
                "migration_allowed_now": False,
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": False,
            },
            "release_readiness": {
                "status": release.get("status"),
                "go_no_go": release.get("decision", {}).get("go_no_go"),
                "approval_count": release.get("evidence", {}).get("approval_count"),
                "latest_approval_event_id": release.get("evidence", {}).get("latest_approval_event_id"),
                "migration_allowed_now": False,
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": False,
            },
            "gates": gates,
            "blocked_gates": blocked,
            "review_required_gates": review_required,
            "decision": {
                "next_required_action": next_required_action,
                "migration_allowed_now": False,
                "approval_can_be_reused_for_manual_release_review": status == "approval_current",
                "requires_human_release_approval": True,
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": False,
            },
            "safety_summary": {
                "executes_sql": False,
                "runs_migration_now": False,
                "creates_table_now": False,
                "writes_database_now": False,
                "writes_digest_history_table_now": False,
                "writes_migration_file_now": False,
                "writes_file": False,
                "download_created": False,
                "executes_commands": False,
                "writes_env": False,
                "real_screen_capture": False,
                "pixel_data_stored": False,
                "ocr_executed": False,
                "broker_action": False,
                "order_action": False,
                "credential_access": False,
                "live_trading_enabled": False,
            },
            "allowed_output": "review_only_screen_readiness_digest_history_approval_review",
            "forbidden_actions": [
                "execute_sql",
                "run_migration_now",
                "create_table_now",
                "write_migration_file_now",
                "insert_digest_snapshot_now",
                "write_env",
                "execute_command",
                "write_file",
                "create_download",
                "screen_click",
                "keyboard_type",
                "inspect_window",
                "real_pixel_capture",
                "pixel_storage",
                "ocr_execution",
                "broker_action",
                "order_action",
                "credential_access",
                "live_auto_trading",
            ],
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": False,
        }

    def screen_readiness_digest_history_release_package(
        self,
        limit: int = 50,
        max_age_days: int = 7,
    ) -> dict[str, Any]:
        proposal = self.screen_readiness_digest_history_proposal(limit=limit)
        checklist = self.screen_readiness_digest_history_migration_checklist(limit=limit)
        verification = self.verify_screen_readiness_digest_history_migration_spec(limit=limit)
        approvals = self.list_screen_readiness_digest_history_migration_spec_approvals(limit=limit)
        release = self.screen_readiness_digest_history_release_readiness(limit=limit)
        approval_review = self.screen_readiness_digest_history_approval_review(
            limit=limit,
            max_age_days=max_age_days,
        )
        latest_approval = approvals[0] if approvals else None
        manifest_items = [
            self._screen_digest_release_package_item(
                "P15_retention_proposal",
                proposal.get("status"),
                proposal.get("allowed_output"),
                proposal.get("generated_at"),
                proposal.get("live_trading_enabled") is False
                and proposal.get("safety_summary", {}).get("writes_database_now") is False,
            ),
            self._screen_digest_release_package_item(
                "P16_migration_checklist",
                checklist.get("status"),
                checklist.get("allowed_output"),
                checklist.get("generated_at"),
                checklist.get("summary", {}).get("migration_allowed_now") is False
                and checklist.get("safety_summary", {}).get("runs_migration_now") is False,
            ),
            self._screen_digest_release_package_item(
                "P17_spec_verifier",
                verification.get("status"),
                verification.get("allowed_output"),
                verification.get("generated_at"),
                verification.get("status") == "spec_verification_passed"
                and verification.get("failed_count") == 0
                and verification.get("safety_summary", {}).get("executes_sql") is False,
            ),
            self._screen_digest_release_package_item(
                "P18_approval_metadata",
                latest_approval.get("status") if latest_approval else "missing",
                latest_approval.get("allowed_output") if latest_approval else "missing",
                latest_approval.get("approved_at") if latest_approval else None,
                bool(latest_approval)
                and latest_approval.get("verification_status") == "spec_verification_passed"
                and latest_approval.get("migration_allowed_now") is False,
            ),
            self._screen_digest_release_package_item(
                "P19_release_readiness",
                release.get("status"),
                release.get("allowed_output"),
                release.get("generated_at"),
                release.get("status") == "release_evidence_ready"
                and release.get("decision", {}).get("migration_allowed_now") is False,
            ),
            self._screen_digest_release_package_item(
                "P20_approval_freshness",
                approval_review.get("status"),
                approval_review.get("allowed_output"),
                approval_review.get("generated_at"),
                approval_review.get("status") == "approval_current"
                and approval_review.get("decision", {}).get("migration_allowed_now") is False,
            ),
        ]
        package_id_payload = {
            "proposal_status": proposal.get("status"),
            "checklist_status": checklist.get("status"),
            "spec_hash": verification.get("spec_hash"),
            "latest_approval_event_id": latest_approval.get("event_id") if latest_approval else None,
            "latest_approval_spec_hash": latest_approval.get("spec_hash") if latest_approval else None,
            "release_status": release.get("status"),
            "approval_review_status": approval_review.get("status"),
            "max_age_days": max(1, min(max_age_days, 365)),
        }
        package_id = hashlib.sha256(
            json.dumps(package_id_payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()
        gates = [
            self._screen_digest_release_gate(
                "retention_proposal_ready",
                proposal.get("status") == "proposal_ready",
                "P15 retention proposal evidence must be ready",
                status_if_false="review_required",
            ),
            self._screen_digest_release_gate(
                "migration_checklist_ready",
                checklist.get("status") == "migration_review_ready",
                "P16 migration checklist must be review-ready",
                status_if_false="review_required",
            ),
            self._screen_digest_release_gate(
                "spec_verifier_passed",
                verification.get("status") == "spec_verification_passed" and verification.get("failed_count") == 0,
                "P17 dry-run verifier must pass without failed checks",
                status_if_false="review_required",
            ),
            self._screen_digest_release_gate(
                "approval_current",
                approval_review.get("status") == "approval_current",
                "P20 approval freshness review must be current",
                status_if_false="review_required",
            ),
            self._screen_digest_release_gate(
                "release_readiness_ready",
                release.get("status") == "release_evidence_ready",
                "P19 release readiness must be evidence-ready",
                status_if_false="review_required",
            ),
            self._screen_digest_release_gate(
                "no_execution_or_persistence_enabled",
                proposal.get("safety_summary", {}).get("writes_database_now") is False
                and checklist.get("safety_summary", {}).get("runs_migration_now") is False
                and verification.get("safety_summary", {}).get("executes_sql") is False
                and release.get("safety_summary", {}).get("runs_migration_now") is False
                and approval_review.get("safety_summary", {}).get("writes_database_now") is False,
                "release package must not enable SQL, migrations, table creation, or digest-history writes",
            ),
            self._screen_digest_release_gate(
                "live_trading_disabled",
                not settings.enable_live_trading
                and proposal.get("live_trading_enabled") is False
                and release.get("live_trading_enabled") is False
                and approval_review.get("live_trading_enabled") is False,
                "live trading must remain disabled",
            ),
        ]
        blocked = [gate for gate in gates if gate["status"] == "blocked"]
        review_required = [gate for gate in gates if gate["status"] == "review_required"]
        if blocked:
            status = "release_package_blocked"
        elif review_required:
            status = "release_package_review_required"
        else:
            status = "release_package_ready_for_manual_review"
        return {
            "schema_version": "screen_readiness_digest_history_release_package.v1",
            "status": status,
            "stage": "V4.5-P21",
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "package_id": package_id,
            "package_id_inputs": package_id_payload,
            "manifest": {
                "name": "screen_readiness_digest_history_manual_release_package",
                "purpose": "manual review evidence for a future SQLite digest-history migration",
                "items": manifest_items,
                "required_manual_artifacts_before_execution": [
                    "reviewed_migration_file",
                    "rollback_plan",
                    "database_backup_plan",
                    "migration_unit_tests",
                    "api_smoke_tests",
                    "forbidden_tracked_file_scan",
                    "explicit_operator_release_approval",
                ],
                "delivery": "api_response_only",
                "writes_file": False,
                "download_created": False,
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": False,
            },
            "evidence": {
                "proposal_status": proposal.get("status"),
                "checklist_status": checklist.get("status"),
                "verification_status": verification.get("status"),
                "verification_failed_count": verification.get("failed_count"),
                "latest_approval_event_id": latest_approval.get("event_id") if latest_approval else None,
                "latest_approval_status": latest_approval.get("status") if latest_approval else None,
                "release_readiness_status": release.get("status"),
                "approval_review_status": approval_review.get("status"),
                "spec_hash": verification.get("spec_hash"),
                "approved_spec_hash": latest_approval.get("spec_hash") if latest_approval else None,
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": False,
            },
            "gates": gates,
            "blocked_gates": blocked,
            "review_required_gates": review_required,
            "decision": {
                "go_no_go": "ready_for_manual_release_review" if status == "release_package_ready_for_manual_review" else "no_go",
                "migration_allowed_now": False,
                "execution_allowed_now": False,
                "requires_human_release_approval": True,
                "next_required_action": "manual_release_review" if status == "release_package_ready_for_manual_review" else "complete_missing_release_evidence",
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": False,
            },
            "safety_summary": {
                "executes_sql": False,
                "runs_migration_now": False,
                "creates_table_now": False,
                "writes_database_now": False,
                "writes_digest_history_table_now": False,
                "writes_migration_file_now": False,
                "writes_file": False,
                "download_created": False,
                "executes_commands": False,
                "writes_env": False,
                "real_screen_capture": False,
                "pixel_data_stored": False,
                "ocr_executed": False,
                "broker_action": False,
                "order_action": False,
                "credential_access": False,
                "live_trading_enabled": False,
            },
            "allowed_output": "review_only_screen_readiness_digest_history_release_package",
            "forbidden_actions": [
                "execute_sql",
                "run_migration_now",
                "create_table_now",
                "write_migration_file_now",
                "insert_digest_snapshot_now",
                "write_env",
                "execute_command",
                "write_file",
                "create_download",
                "screen_click",
                "keyboard_type",
                "inspect_window",
                "real_pixel_capture",
                "pixel_storage",
                "ocr_execution",
                "broker_action",
                "order_action",
                "credential_access",
                "live_auto_trading",
            ],
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": False,
        }

    def screen_readiness_timeline(self, limit: int = 50) -> dict[str, Any]:
        safe_limit = max(1, min(limit, 200))
        report = self.screen_readiness_audit_report(limit=min(safe_limit, 50))
        items: list[dict[str, Any]] = [
            self._timeline_item(
                "readiness_audit_report",
                "current",
                report.get("generated_at"),
                f"Readiness audit / {report.get('status')}",
                str(report.get("status") or "unknown"),
                {
                    "stage": report.get("stage"),
                    "blocked_check_count": report.get("summary", {}).get("blocked_check_count", 0),
                    "artifact_pending_count": report.get("summary", {}).get("artifact_pending_count", 0),
                    "config_pending_count": report.get("summary", {}).get("config_pending_count", 0),
                    "allowed_output": report.get("summary", {}).get("allowed_output"),
                },
            )
        ]
        for observation in self.list_observations(limit=safe_limit):
            items.append(
                self._timeline_item(
                    "screen_observation",
                    observation.get("id"),
                    observation.get("observed_at") or observation.get("created_at"),
                    f"{observation.get('app_status')} / {observation.get('source')}",
                    str(observation.get("app_status") or "unknown"),
                    {
                        "window_title": observation.get("window_title"),
                        "warning_count": len(observation.get("warnings") or []),
                        "artifact_ref": observation.get("artifact_ref"),
                    },
                )
            )
        for review in self.list_artifact_reviews(limit=safe_limit):
            items.append(
                self._timeline_item(
                    "artifact_review",
                    review.get("id"),
                    review.get("updated_at") or review.get("created_at"),
                    f"Artifact review / {review.get('review_status')}",
                    str(review.get("review_status") or "unknown"),
                    {
                        "artifact_status": review.get("artifact_status"),
                        "artifact_ref": review.get("artifact_ref"),
                        "decision_effect": review.get("retention_policy", {}).get("review_queue", {}).get("decision_effect"),
                    },
                )
            )
        for proposal in self.list_provider_config_proposals(limit=safe_limit):
            items.append(
                self._timeline_item(
                    "provider_config_proposal",
                    proposal.get("id"),
                    proposal.get("updated_at") or proposal.get("created_at"),
                    f"Provider config proposal / {proposal.get('status')}",
                    str(proposal.get("status") or "unknown"),
                    {
                        "provider": proposal.get("provider"),
                        "target_window_title": proposal.get("target_window_title"),
                        "writes_env": bool(proposal.get("proposal", {}).get("writes_env")),
                        "executes_commands": bool(proposal.get("proposal", {}).get("executes_commands")),
                    },
                )
            )
        for run in self.list_provider_replay_runs(limit=safe_limit):
            items.append(
                self._timeline_item(
                    "provider_replay_run",
                    run.get("id"),
                    run.get("created_at"),
                    f"Provider replay / {run.get('status')}",
                    str(run.get("status") or "unknown"),
                    {
                        "scenario_name": run.get("scenario_name"),
                        "proposal_id": run.get("proposal_id"),
                        "passed_count": run.get("summary", {}).get("passed_count", 0),
                        "blocked_count": run.get("summary", {}).get("blocked_count", 0),
                    },
                )
            )
        for ack in self.list_screen_readiness_audit_acknowledgements(limit=safe_limit):
            items.append(
                self._timeline_item(
                    "readiness_audit_acknowledgement",
                    ack.get("id"),
                    ack.get("updated_at") or ack.get("created_at"),
                    f"Readiness audit acknowledged / {ack.get('acknowledged_by')}",
                    str(ack.get("status") or "unknown"),
                    {
                        "report_status": ack.get("report_status"),
                        "report_stage": ack.get("report_stage"),
                        "acknowledgement_effect": ack.get("acknowledgement_effect"),
                    },
                )
            )
        for approval in self.list_screen_readiness_digest_history_migration_spec_approvals(limit=safe_limit):
            items.append(
                self._timeline_item(
                    "digest_history_migration_spec_approval",
                    approval.get("event_id"),
                    approval.get("created_at") or approval.get("approved_at"),
                    f"Migration spec approval / {approval.get('approved_by')}",
                    str(approval.get("status") or "unknown"),
                    {
                        "approval_effect": approval.get("approval_effect"),
                        "spec_hash": approval.get("spec_hash"),
                        "verification_status": approval.get("verification_status"),
                        "migration_allowed_now": approval.get("migration_allowed_now"),
                    },
                )
            )
        ordered = sorted(items, key=lambda item: item["event_ts"] or "", reverse=True)[:safe_limit]
        counts_by_type: dict[str, int] = {}
        for item in ordered:
            item_type = str(item["item_type"])
            counts_by_type[item_type] = counts_by_type.get(item_type, 0) + 1
        return {
            "status": "timeline_ready",
            "stage": "V4.5-P21",
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "item_count": len(ordered),
            "counts_by_type": counts_by_type,
            "items": ordered,
            "allowed_output": "review_only_screen_readiness_timeline",
            "forbidden_actions": [
                "screen_click",
                "keyboard_type",
                "real_pixel_capture",
                "pixel_storage",
                "ocr_execution",
                "broker_action",
                "order_action",
                "credential_access",
                "live_auto_trading",
            ],
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": False,
        }

    def acknowledge_screen_readiness_audit(
        self,
        acknowledged_by: str = "operator",
        note: str | None = None,
    ) -> dict[str, Any]:
        report = self.screen_readiness_audit_report()
        report_hash = self._screen_audit_report_hash(report)
        now = datetime.now().isoformat(timespec="seconds")
        summary = report.get("summary") or {}
        safety_matrix = report.get("safety_matrix") or []
        with self.store.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO screen_readiness_audit_acknowledgements(
                    status, report_hash, report_status, report_stage,
                    summary_json, safety_matrix_json, report_json,
                    acknowledged_by, acknowledgement_note, acknowledgement_effect,
                    review_only, simulation_only, live_trading_enabled,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(report_hash) DO UPDATE SET
                    status = excluded.status,
                    report_status = excluded.report_status,
                    report_stage = excluded.report_stage,
                    summary_json = excluded.summary_json,
                    safety_matrix_json = excluded.safety_matrix_json,
                    report_json = excluded.report_json,
                    acknowledged_by = excluded.acknowledged_by,
                    acknowledgement_note = excluded.acknowledgement_note,
                    acknowledgement_effect = excluded.acknowledgement_effect,
                    review_only = excluded.review_only,
                    simulation_only = excluded.simulation_only,
                    live_trading_enabled = excluded.live_trading_enabled,
                    updated_at = excluded.updated_at
                """,
                (
                    "acknowledged",
                    report_hash,
                    str(report.get("status") or "unknown"),
                    str(report.get("stage") or "V4.5-P21"),
                    json.dumps(summary, ensure_ascii=False, default=str),
                    json.dumps(safety_matrix, ensure_ascii=False, default=str),
                    json.dumps(report, ensure_ascii=False, default=str),
                    (acknowledged_by or "operator")[:80],
                    note,
                    "audit_status_only",
                    1,
                    1,
                    0,
                    now,
                    now,
                ),
            )
            ack_id = int(cursor.lastrowid or 0)
        if not ack_id:
            row = self.store.fetch_one(
                "SELECT id FROM screen_readiness_audit_acknowledgements WHERE report_hash = ?",
                (report_hash,),
            )
            ack_id = int(row["id"]) if row else 0
        return self.get_screen_readiness_audit_acknowledgement(ack_id) or {
            "id": ack_id,
            "status": "acknowledged",
            "report_hash": report_hash,
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": False,
        }

    def list_screen_readiness_audit_acknowledgements(self, limit: int = 20) -> list[dict[str, Any]]:
        rows = self.store.fetch_all(
            """
            SELECT *
            FROM screen_readiness_audit_acknowledgements
            ORDER BY updated_at DESC, id DESC
            LIMIT ?
            """,
            (max(1, min(limit, 200)),),
        )
        return [self._screen_readiness_audit_ack_model(row) for row in rows]

    def get_screen_readiness_audit_acknowledgement(self, ack_id: int) -> dict[str, Any] | None:
        row = self.store.fetch_one(
            "SELECT * FROM screen_readiness_audit_acknowledgements WHERE id = ?",
            (ack_id,),
        )
        return self._screen_readiness_audit_ack_model(row) if row else None

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

    def replay_provider_readiness_scenario(
        self,
        proposal_id: int | None = None,
        scenario_name: str = "local_safe_fixture_readiness",
    ) -> dict[str, Any]:
        proposal = self._resolve_config_proposal(proposal_id)
        readiness = self.provider_readiness_runbook()
        fixture_capabilities = FixtureScreenCaptureProvider().capabilities()
        steps = [
            self._scenario_step(
                "load_config_proposal",
                bool(proposal),
                "proposal loaded" if proposal else "no proposal available; replay uses current readiness only",
                {"proposal_id": proposal.get("id") if proposal else None},
            ),
            self._scenario_step(
                "verify_no_env_write",
                not proposal or not bool(proposal.get("proposal", {}).get("writes_env")),
                "config proposal must not write .env",
                {"writes_env": proposal.get("proposal", {}).get("writes_env") if proposal else False},
            ),
            self._scenario_step(
                "verify_no_command_execution",
                not proposal or not bool(proposal.get("proposal", {}).get("executes_commands")),
                "config proposal must not execute shell or GUI commands",
                {"executes_commands": proposal.get("proposal", {}).get("executes_commands") if proposal else False},
            ),
            self._scenario_step(
                "fixture_provider_available",
                bool(fixture_capabilities.get("fixture_replay_supported")),
                "fixture provider can simulate observation persistence without desktop access",
                {"provider": fixture_capabilities.get("provider")},
            ),
            self._scenario_step(
                "real_pixel_capture_blocked",
                True,
                "real pixel capture remains blocked during scenario replay",
                {"real_screen_capture": False, "pixel_data_stored": False},
            ),
            self._scenario_step(
                "ocr_execution_blocked",
                True,
                "OCR remains blocked during scenario replay",
                {"ocr_executed": False},
            ),
            self._scenario_step(
                "live_trading_disabled",
                not settings.enable_live_trading,
                "live trading must remain disabled",
                {"live_trading_enabled": False},
            ),
        ]
        status = "replay_passed" if all(step["status"] == "passed" for step in steps) else "replay_blocked"
        summary = {
            "scenario_name": scenario_name,
            "proposal_id": proposal.get("id") if proposal else None,
            "step_count": len(steps),
            "passed_count": sum(1 for step in steps if step["status"] == "passed"),
            "blocked_count": sum(1 for step in steps if step["status"] != "passed"),
            "readiness_status": readiness["status"],
            "allowed_output": "review_only_scenario_replay",
            "forbidden_actions": readiness["runbook"]["blocked_actions"],
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": False,
        }
        with self.store.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO screen_provider_replay_runs(
                    status, proposal_id, scenario_name, step_json, summary_json,
                    review_only, simulation_only, live_trading_enabled
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    status,
                    proposal.get("id") if proposal else None,
                    scenario_name[:120],
                    json.dumps(steps, ensure_ascii=False, default=str),
                    json.dumps(summary, ensure_ascii=False, default=str),
                    1,
                    1,
                    0,
                ),
            )
            run_id = int(cursor.lastrowid)
        return self.get_provider_replay_run(run_id) or {"id": run_id, "status": status}

    def list_provider_replay_runs(self, limit: int = 20) -> list[dict[str, Any]]:
        rows = self.store.fetch_all(
            """
            SELECT r.*, p.title AS proposal_title, p.status AS proposal_status
            FROM screen_provider_replay_runs r
            LEFT JOIN screen_provider_config_proposals p ON p.id = r.proposal_id
            ORDER BY r.created_at DESC, r.id DESC
            LIMIT ?
            """,
            (max(1, min(limit, 200)),),
        )
        return [self._provider_replay_run_model(row) for row in rows]

    def get_provider_replay_run(self, run_id: int) -> dict[str, Any] | None:
        row = self.store.fetch_one(
            """
            SELECT r.*, p.title AS proposal_title, p.status AS proposal_status
            FROM screen_provider_replay_runs r
            LEFT JOIN screen_provider_config_proposals p ON p.id = r.proposal_id
            WHERE r.id = ?
            """,
            (run_id,),
        )
        return self._provider_replay_run_model(row) if row else None

    def generate_provider_config_proposal(self, target_window_title: str | None = None) -> dict[str, Any]:
        title = (target_window_title or "Untitled - Notepad").strip()[:120]
        allowed_windows = sorted({title, "Calculator"})
        broker_terms = self._split_csv(settings.screen_capture_broker_window_terms)
        proposal = {
            "provider": "local_safe",
            "target_window_title": title,
            "env_patch": {
                "SCREEN_CAPTURE_PROVIDER": "local_safe",
                "SCREEN_CAPTURE_ALLOW_REAL_CAPTURE": "true",
                "SCREEN_CAPTURE_ALLOWED_WINDOWS": ",".join(allowed_windows),
                "SCREEN_CAPTURE_BLOCK_BROKER_WINDOWS": "true",
                "SCREEN_CAPTURE_BROKER_WINDOW_TERMS": ",".join(broker_terms),
            },
            "manual_review_required": True,
            "apply_automatically": False,
            "writes_env": False,
            "executes_commands": False,
            "real_screen_capture_enabled_by_api": False,
            "ocr_enabled_by_api": False,
            "operator_steps": [
                "Review the harmless window title and broker deny terms.",
                "If accepted, apply settings manually outside the API after closing broker software.",
                "Restart the backend manually and re-check /api/screen-monitoring/provider-readiness.",
                "Run capture-preflight against the harmless window before any metadata stub.",
            ],
            "rollback_steps": [
                "Set SCREEN_CAPTURE_PROVIDER=disabled.",
                "Set SCREEN_CAPTURE_ALLOW_REAL_CAPTURE=false.",
                "Restart the backend manually and verify provider status is disabled.",
            ],
        }
        rationale = {
            "summary": "Operator-reviewed local_safe configuration proposal for harmless-window preflight only.",
            "why": [
                "A reviewed allowlist prevents accidental broker-window observation.",
                "Broker deny terms remain enabled and must include Chinese trading-client keywords.",
                "The backend stores this as audit evidence only and does not mutate .env.",
            ],
            "safety": {
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": False,
                "pixel_capture": False,
                "ocr_execution": False,
                "screen_click": False,
                "broker_action": False,
                "credential_access": False,
            },
        }
        now = datetime.now().isoformat(timespec="seconds")
        with self.store.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO screen_provider_config_proposals(
                    status, title, provider, target_window_title,
                    proposal_json, rationale_json,
                    review_only, simulation_only, live_trading_enabled,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "pending_review",
                    "local_safe harmless-window configuration proposal",
                    "local_safe",
                    title,
                    json.dumps(proposal, ensure_ascii=False, default=str),
                    json.dumps(rationale, ensure_ascii=False, default=str),
                    1,
                    1,
                    0,
                    now,
                    now,
                ),
            )
            proposal_id = int(cursor.lastrowid)
        return self.get_provider_config_proposal(proposal_id) or {"id": proposal_id}

    def list_provider_config_proposals(self, status: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
        normalized = (status or "").strip()
        params: tuple[Any, ...]
        where = ""
        if normalized:
            where = "WHERE status = ?"
            params = (normalized, max(1, min(limit, 200)))
        else:
            params = (max(1, min(limit, 200)),)
        rows = self.store.fetch_all(
            f"""
            SELECT *
            FROM screen_provider_config_proposals
            {where}
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            params,
        )
        return [self._provider_config_proposal_model(row) for row in rows]

    def decide_provider_config_proposal(
        self,
        proposal_id: int,
        decision: str,
        reviewed_by: str = "operator",
        note: str | None = None,
    ) -> dict[str, Any]:
        normalized = decision.strip().lower()
        if normalized not in {"accepted", "rejected"}:
            raise ValueError("provider config proposal decision must be accepted or rejected")
        reviewed_at = datetime.now().isoformat(timespec="seconds")
        with self.store.connect() as conn:
            cursor = conn.execute(
                """
                UPDATE screen_provider_config_proposals
                SET status = ?, reviewed_by = ?, review_note = ?,
                    reviewed_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (normalized, reviewed_by[:80], note, reviewed_at, reviewed_at, proposal_id),
            )
            if cursor.rowcount == 0:
                raise ValueError(f"screen provider config proposal {proposal_id} not found")
        return self.get_provider_config_proposal(proposal_id) or {"id": proposal_id, "status": normalized}

    def get_provider_config_proposal(self, proposal_id: int) -> dict[str, Any] | None:
        row = self.store.fetch_one(
            "SELECT * FROM screen_provider_config_proposals WHERE id = ?",
            (proposal_id,),
        )
        return self._provider_config_proposal_model(row) if row else None

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

    def record_tonghuashun_simulation_observation(
        self,
        session_id: int | None = None,
        window_title: str | None = None,
        confidence: float = 0.85,
        detected_items: list[dict[str, Any]] | None = None,
        raw_payload: dict[str, Any] | None = None,
        artifact_ref: str | None = None,
        observed_at: str | None = None,
        observed_by: str = "operator",
        note: str | None = None,
    ) -> dict[str, Any]:
        """Record Tonghuashun simulated委托 evidence without clicking or OCR."""
        title = (window_title or "").strip()
        marker_text = f"{title} {json.dumps(raw_payload or {}, ensure_ascii=False, default=str)}".lower()
        simulation_markers = ["mncg", "模拟", "模拟炒股", "模拟委托"]
        simulation_mode_detected = any(marker.lower() in marker_text for marker in simulation_markers)
        safe_detected = list(detected_items or [])
        safe_detected.extend(
            [
                {
                    "type": "simulation_mode_marker",
                    "value": "mncg_or_simulation_text_present" if simulation_mode_detected else "missing",
                    "confidence": 0.9 if simulation_mode_detected else 0.25,
                },
                {
                    "type": "visible_control_boundary",
                    "value": "buy_sell_cancel_submit_controls_are_observation_only",
                    "automation_allowed": False,
                },
            ]
        )
        warnings = [
            "tonghuashun_simulation_observation_is_read_only",
            "interactive_trading_controls_visible_but_not_actionable_by_automation",
        ]
        if not simulation_mode_detected:
            warnings.append("simulation_mode_marker_missing_or_uncertain")
        payload = {
            **(raw_payload or {}),
            "schema_version": "tonghuashun_simulation_observation.v1",
            "stage": "V4.5-P22",
            "observed_by": observed_by or "operator",
            "note": note,
            "simulation_mode_detected": simulation_mode_detected,
            "allowed_use": [
                "read_only_screen_observation",
                "manual_simulation_review",
                "training_label_metadata",
                "experience_memory_evidence",
            ],
            "forbidden_actions": [
                "screen_click",
                "keyboard_type",
                "buy",
                "sell",
                "cancel_order",
                "submit_order",
                "broker_action",
                "credential_access",
                "funds_or_position_read_for_live_trading",
                "live_auto_trading",
            ],
            "real_screen_capture": False,
            "ocr_executed": False,
            "pixel_data_stored": False,
            "screen_click_executed": False,
            "keyboard_type_executed": False,
            "broker_action_executed": False,
            "order_action_executed": False,
            "credential_accessed": False,
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": False,
        }
        observation = self.record_observation(
            session_id=session_id,
            source="tonghuashun_simulation",
            app_status="simulation_observed" if simulation_mode_detected else "attention_required",
            window_title=title or "Tonghuashun simulation window",
            confidence=confidence if simulation_mode_detected else min(confidence, 0.45),
            detected_items=safe_detected,
            warnings=warnings,
            raw_payload=payload,
            artifact_ref=artifact_ref,
            observed_at=observed_at,
        )
        observation["tonghuashun_simulation"] = {
            "simulation_mode_detected": simulation_mode_detected,
            "training_label_ready": bool(simulation_mode_detected and observation.get("inserted") is True),
            "automation_actions_allowed": False,
            "manual_order_entry_required": True,
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": False,
        }
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

    def _resolve_config_proposal(self, proposal_id: int | None) -> dict[str, Any]:
        if proposal_id:
            return self.get_provider_config_proposal(proposal_id) or {}
        proposals = self.list_provider_config_proposals(limit=1)
        return proposals[0] if proposals else {}

    def _scenario_step(
        self,
        name: str,
        passed: bool,
        reason: str,
        evidence: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "name": name,
            "status": "passed" if passed else "blocked",
            "reason": reason,
            "evidence": evidence or {},
            "real_screen_capture": False,
            "pixel_data_stored": False,
            "ocr_executed": False,
            "writes_env": False,
            "executes_commands": False,
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": False,
        }

    def _screen_audit_safety_matrix(
        self,
        capabilities: dict[str, Any],
        readiness: dict[str, Any],
        policy: dict[str, Any],
        observations: list[dict[str, Any]],
        artifact_reviews: list[dict[str, Any]],
        proposals: list[dict[str, Any]],
        replay_runs: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        return [
            self._screen_audit_safety_check(
                "live_trading_disabled",
                not settings.enable_live_trading
                and not bool(capabilities.get("live_trading_enabled"))
                and not bool(readiness.get("live_trading_enabled")),
                "screen readiness report must never enable live trading",
            ),
            self._screen_audit_safety_check(
                "pixel_capture_blocked",
                not bool(policy.get("pixel_data_stored"))
                and all(not bool(item.get("raw_payload", {}).get("pixel_data_stored")) for item in observations),
                "audit evidence is metadata-only; no pixel data may be stored",
            ),
            self._screen_audit_safety_check(
                "ocr_execution_blocked",
                not bool(policy.get("ocr_executed"))
                and all(not bool(item.get("raw_payload", {}).get("ocr_executed")) for item in observations),
                "OCR must remain blocked in V4.5 readiness reporting",
            ),
            self._screen_audit_safety_check(
                "artifact_reviews_are_audit_only",
                all(item.get("live_trading_enabled") is False for item in artifact_reviews),
                "artifact accept/reject decisions are audit status only",
            ),
            self._screen_audit_safety_check(
                "config_proposals_do_not_apply",
                all(
                    not bool((item.get("proposal") or {}).get("writes_env"))
                    and not bool((item.get("proposal") or {}).get("executes_commands"))
                    and not bool((item.get("proposal") or {}).get("apply_automatically"))
                    for item in proposals
                ),
                "provider config proposals must not write env, execute commands, or apply automatically",
            ),
            self._screen_audit_safety_check(
                "provider_replays_are_review_only",
                all(
                    item.get("review_only") is True
                    and item.get("simulation_only") is True
                    and item.get("live_trading_enabled") is False
                    and not any(bool(step.get("real_screen_capture")) for step in item.get("steps", []))
                    for item in replay_runs
                ),
                "provider replay runs must preserve review-only metadata and block capture",
            ),
        ]

    def _screen_audit_safety_check(self, name: str, passed: bool, reason: str) -> dict[str, Any]:
        return {
            "name": name,
            "status": "passed" if passed else "blocked",
            "reason": reason,
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": False,
        }

    def _screen_audit_report_hash(self, report: dict[str, Any]) -> str:
        payload = {
            "status": report.get("status"),
            "stage": report.get("stage"),
            "summary": report.get("summary") or {},
            "blockers": report.get("blockers") or [],
            "safety_matrix": report.get("safety_matrix") or [],
            "forbidden_actions": report.get("forbidden_actions") or [],
        }
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def _screen_evidence_export_hash(self, bundle: dict[str, Any]) -> str:
        payload = self._without_evidence_export_runtime_fields(bundle)
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def _without_evidence_export_runtime_fields(self, value: Any) -> Any:
        if isinstance(value, dict):
            runtime_keys = {"generated_at", "bundle_hash"}
            if value.get("item_type") == "readiness_audit_report" and value.get("source_id") == "current":
                runtime_keys.add("event_ts")
            return {
                key: self._without_evidence_export_runtime_fields(item)
                for key, item in value.items()
                if key not in runtime_keys
            }
        if isinstance(value, list):
            return [self._without_evidence_export_runtime_fields(item) for item in value]
        return value

    def _screen_evidence_check(
        self,
        name: str,
        passed: bool,
        value: Any,
        expected: Any,
        reason: str,
    ) -> dict[str, Any]:
        return {
            "name": name,
            "status": "passed" if passed else "failed",
            "value": value,
            "expected": expected,
            "reason": reason,
            "severity": "blocker" if not passed else "info",
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": False,
        }

    def _screen_required_paths_present(self, bundle: dict[str, Any], paths: list[str]) -> bool:
        for path in paths:
            current: Any = bundle
            for part in path.split("."):
                if not isinstance(current, dict) or part not in current:
                    return False
                current = current[part]
        return True

    def _screen_forbidden_actions_covered(self, bundle: dict[str, Any]) -> bool:
        required = {
            "write_env",
            "execute_command",
            "screen_click",
            "keyboard_type",
            "real_pixel_capture",
            "ocr_execution",
            "broker_action",
            "order_action",
            "credential_access",
            "live_auto_trading",
        }
        return required.issubset(set(bundle.get("forbidden_actions") or []))

    def _screen_verification_comparison_summary(self, verification: dict[str, Any]) -> dict[str, Any]:
        return {
            "schema_version": verification.get("schema_version"),
            "status": verification.get("status"),
            "stage": verification.get("stage"),
            "export_bundle_hash": verification.get("export_bundle_hash"),
            "verified_export_stage": verification.get("verified_export_stage"),
            "check_count": verification.get("check_count"),
            "passed_count": verification.get("passed_count"),
            "failed_count": verification.get("failed_count"),
            "failed_check_names": [item.get("name") for item in verification.get("failed_checks", [])],
            "check_statuses": {
                str(item.get("name")): item.get("status")
                for item in verification.get("checks", [])
            },
            "safety_summary": verification.get("safety_summary", {}),
            "allowed_output": verification.get("allowed_output"),
            "forbidden_actions": sorted(verification.get("forbidden_actions") or []),
            "review_only": verification.get("review_only") is True,
            "simulation_only": verification.get("simulation_only") is True,
            "live_trading_enabled": verification.get("live_trading_enabled") is True,
        }

    def _screen_verification_differences(
        self,
        baseline: dict[str, Any],
        candidate: dict[str, Any],
    ) -> list[dict[str, Any]]:
        differences: list[dict[str, Any]] = []
        for key in [
            "schema_version",
            "status",
            "export_bundle_hash",
            "verified_export_stage",
            "check_count",
            "passed_count",
            "failed_count",
            "failed_check_names",
            "check_statuses",
            "safety_summary",
            "forbidden_actions",
            "review_only",
            "simulation_only",
            "live_trading_enabled",
        ]:
            if baseline.get(key) != candidate.get(key):
                differences.append(
                    {
                        "field": key,
                        "status": "changed",
                        "baseline": baseline.get(key),
                        "candidate": candidate.get(key),
                        "reason": "current evidence verification changed between two read-only checks",
                        "review_only": True,
                        "simulation_only": True,
                        "live_trading_enabled": False,
                    }
                )
        return differences

    def _screen_health_flag(self, name: str, passed: bool, reason: str) -> dict[str, Any]:
        return {
            "name": name,
            "status": "passed" if passed else "review_required",
            "reason": reason,
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": False,
        }

    def _screen_digest_module(
        self,
        name: str,
        status: Any,
        stage: Any,
        live_trading_enabled: Any,
    ) -> dict[str, Any]:
        return {
            "name": name,
            "status": status,
            "stage": stage,
            "live_trading_enabled": bool(live_trading_enabled),
            "review_only": True,
            "simulation_only": True,
        }

    def _screen_digest_history_gate(self, name: str, required: bool, reason: str) -> dict[str, Any]:
        return {
            "name": name,
            "status": "required" if required else "optional",
            "reason": reason,
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": False,
        }

    def _screen_digest_migration_check(
        self,
        name: str,
        passed: bool,
        reason: str,
        *,
        status_if_false: str = "blocked",
    ) -> dict[str, Any]:
        return {
            "name": name,
            "status": "passed" if passed else status_if_false,
            "required": True,
            "reason": reason,
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": False,
        }

    def _screen_digest_migration_spec_check(
        self,
        name: str,
        passed: bool,
        reason: str,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "name": name,
            "status": "passed" if passed else "failed",
            "reason": reason,
            "details": details or {},
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": False,
        }

    def _screen_digest_release_gate(
        self,
        name: str,
        passed: bool,
        reason: str,
        *,
        status_if_false: str = "blocked",
    ) -> dict[str, Any]:
        return {
            "name": name,
            "status": "passed" if passed else status_if_false,
            "reason": reason,
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": False,
        }

    def _screen_digest_release_package_item(
        self,
        name: str,
        status: Any,
        allowed_output: Any,
        generated_at: Any,
        included: bool,
    ) -> dict[str, Any]:
        return {
            "name": name,
            "status": status,
            "allowed_output": allowed_output,
            "generated_at": generated_at,
            "included": bool(included),
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": False,
        }

    def _default_digest_history_migration_spec(self, field_names: list[str]) -> str:
        lines = [
            "CREATE TABLE IF NOT EXISTS screen_readiness_digest_history (",
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,",
        ]
        for field in field_names:
            column_type = "TEXT"
            if field.endswith("_count"):
                column_type = "INTEGER"
            elif field == "safety_summary" or field.endswith("_names"):
                column_type = "JSON"
            lines.append(f"  {field} {column_type},")
        lines.extend(
            [
                "  created_at TEXT NOT NULL,",
                "  review_only INTEGER NOT NULL DEFAULT 1,",
                "  simulation_only INTEGER NOT NULL DEFAULT 1,",
                "  live_trading_enabled INTEGER NOT NULL DEFAULT 0",
                ");",
                "-- dry-run spec only; do not execute without separate reviewed migration, rollback plan, tests, and operator approval",
            ]
        )
        return "\n".join(lines)

    def _screen_evidence_export_safety(
        self,
        capabilities: dict[str, Any],
        readiness: dict[str, Any],
        report: dict[str, Any],
        acknowledgements: list[dict[str, Any]],
        timeline: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "writes_env": False,
            "executes_commands": False,
            "writes_file": False,
            "download_created": False,
            "real_screen_capture": False,
            "pixel_data_stored": False,
            "ocr_executed": False,
            "broker_action": False,
            "order_action": False,
            "credential_access": False,
            "live_trading_enabled": False,
            "capabilities_live_disabled": capabilities.get("live_trading_enabled") is False,
            "readiness_live_disabled": readiness.get("live_trading_enabled") is False,
            "report_live_disabled": report.get("live_trading_enabled") is False,
            "acknowledgements_live_disabled": all(item.get("live_trading_enabled") is False for item in acknowledgements),
            "timeline_live_disabled": timeline.get("live_trading_enabled") is False,
            "allowed_output": "review_only_screen_readiness_evidence_export",
            "review_only": True,
            "simulation_only": True,
        }

    def _timeline_item(
        self,
        item_type: str,
        source_id: Any,
        event_ts: Any,
        title: str,
        status: str,
        summary: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "id": f"{item_type}:{source_id}",
            "item_type": item_type,
            "source_id": source_id,
            "event_ts": str(event_ts or ""),
            "title": title,
            "status": status,
            "summary": summary or {},
            "writes_env": False,
            "executes_commands": False,
            "real_screen_capture": False,
            "pixel_data_stored": False,
            "ocr_executed": False,
            "broker_action": False,
            "order_action": False,
            "credential_access": False,
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": False,
        }

    def _screen_audit_next_steps(
        self,
        blockers: list[dict[str, Any]],
        artifact_pending: list[dict[str, Any]],
        proposal_pending: list[dict[str, Any]],
        replay_runs: list[dict[str, Any]],
    ) -> list[str]:
        steps: list[str] = []
        if blockers:
            steps.append("Review blocked readiness checks before any further screen provider changes.")
        if proposal_pending:
            steps.append("Accept or reject pending local-safe config proposals; do not apply them through the API.")
        if artifact_pending:
            steps.append("Review pending artifact metadata and mark accepted/rejected for audit only.")
        if not replay_runs:
            steps.append("Run provider-readiness replay after generating or reviewing a local-safe config proposal.")
        if not steps:
            steps.append("Keep using fixture/manual observations until a separate harmless-window provider stage is reviewed.")
        steps.append("Confirm /health keeps live_trading_enabled=false before every screen monitoring workflow.")
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

    def _parse_datetime(self, value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(str(value)).replace(tzinfo=None)
        except ValueError:
            return None

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

    def _provider_config_proposal_model(self, row: dict[str, Any] | None) -> dict[str, Any]:
        if not row:
            return {}
        item = dict(row)
        item["proposal"] = self._decode_json(item.pop("proposal_json", "{}"))
        item["rationale"] = self._decode_json(item.pop("rationale_json", "{}"))
        item["review_only"] = bool(item.get("review_only"))
        item["simulation_only"] = bool(item.get("simulation_only"))
        item["live_trading_enabled"] = bool(item.get("live_trading_enabled"))
        return item

    def _provider_replay_run_model(self, row: dict[str, Any] | None) -> dict[str, Any]:
        if not row:
            return {}
        item = dict(row)
        item["steps"] = self._decode_json(item.pop("step_json", "[]"))
        item["summary"] = self._decode_json(item.pop("summary_json", "{}"))
        item["review_only"] = bool(item.get("review_only"))
        item["simulation_only"] = bool(item.get("simulation_only"))
        item["live_trading_enabled"] = bool(item.get("live_trading_enabled"))
        return item

    def _screen_readiness_audit_ack_model(self, row: dict[str, Any] | None) -> dict[str, Any]:
        if not row:
            return {}
        item = dict(row)
        item["summary"] = self._decode_json(item.pop("summary_json", "{}"))
        item["safety_matrix"] = self._decode_json(item.pop("safety_matrix_json", "[]"))
        item["report"] = self._decode_json(item.pop("report_json", "{}"))
        item["review_only"] = bool(item.get("review_only"))
        item["simulation_only"] = bool(item.get("simulation_only"))
        item["live_trading_enabled"] = bool(item.get("live_trading_enabled"))
        item["writes_env"] = False
        item["executes_commands"] = False
        item["real_screen_capture"] = False
        item["pixel_data_stored"] = False
        item["ocr_executed"] = False
        item["broker_action"] = False
        item["order_action"] = False
        item["credential_access"] = False
        return item

    def _decode_json(self, value: Any) -> Any:
        if not isinstance(value, str):
            return value
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
