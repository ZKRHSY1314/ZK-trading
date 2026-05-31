from app.screen_monitoring.providers import LocalSafeScreenCaptureProvider
from app.screen_monitoring.service import ScreenMonitoringService


def _reset_screen_monitoring(store) -> None:
    with store.connect() as conn:
        conn.execute("DELETE FROM events WHERE event_type = 'screen_digest_migration_spec_approval'")
        conn.execute("DELETE FROM screen_readiness_audit_acknowledgements")
        conn.execute("DELETE FROM screen_provider_replay_runs")
        conn.execute("DELETE FROM screen_provider_config_proposals")
        conn.execute("DELETE FROM screen_artifact_reviews")
        conn.execute("DELETE FROM screen_observations")
        conn.execute("DELETE FROM screen_monitoring_sessions")


def test_screen_monitoring_capabilities_are_read_only(test_db):
    _reset_screen_monitoring(test_db)
    capabilities = ScreenMonitoringService().capabilities()

    assert capabilities["stage"] == "V4.5-P19"
    assert capabilities["capture_provider"] == "disabled"
    assert capabilities["provider_status"] == "disabled"
    assert capabilities["provider_configured"] is False
    assert capabilities["ocr_provider"] == "not_configured"
    assert capabilities["provider_capabilities"]["capture_supported"] is False
    assert capabilities["provider_capabilities"]["capture_stub_supported"] is False
    assert capabilities["review_only"] is True
    assert capabilities["simulation_only"] is True
    assert capabilities["live_trading_enabled"] is False
    assert "screen_click" in capabilities["forbidden_modes"]
    assert "order_action" in capabilities["forbidden_modes"]
    assert "fixture_replay" in capabilities["allowed_modes"]
    assert "capture_artifact_stub" in capabilities["allowed_modes"]
    assert "artifact_review_queue" in capabilities["allowed_modes"]
    assert "provider_readiness_runbook" in capabilities["allowed_modes"]
    assert "provider_config_proposal" in capabilities["allowed_modes"]
    assert "provider_readiness_replay" in capabilities["allowed_modes"]
    assert "screen_readiness_audit_report" in capabilities["allowed_modes"]
    assert "screen_readiness_audit_acknowledgement" in capabilities["allowed_modes"]
    assert "screen_readiness_timeline" in capabilities["allowed_modes"]
    assert "screen_readiness_evidence_export" in capabilities["allowed_modes"]
    assert "screen_readiness_evidence_verifier" in capabilities["allowed_modes"]
    assert "screen_readiness_evidence_comparison" in capabilities["allowed_modes"]
    assert "screen_readiness_health_digest" in capabilities["allowed_modes"]
    assert "screen_readiness_digest_history_proposal" in capabilities["allowed_modes"]
    assert "screen_readiness_digest_history_migration_checklist" in capabilities["allowed_modes"]
    assert "screen_readiness_digest_history_migration_spec_verifier" in capabilities["allowed_modes"]
    assert "screen_readiness_digest_history_migration_spec_approval" in capabilities["allowed_modes"]
    assert "screen_readiness_digest_history_release_readiness" in capabilities["allowed_modes"]


def test_screen_observation_creates_session_and_summary(test_db):
    _reset_screen_monitoring(test_db)
    service = ScreenMonitoringService()

    observation = service.record_observation(
        source="mock",
        app_status="online",
        window_title="Mock Trading Client",
        confidence=0.8,
        detected_items=[{"type": "window_status", "value": "online"}],
        raw_payload={"fixture": True, "read_only": True},
    )
    latest = service.latest_session()
    observations = service.list_observations()

    assert observation["inserted"] is True
    assert observation["app_status"] == "online"
    assert observation["live_trading_enabled"] is False
    assert latest["status"] == "running"
    assert latest["summary"]["observation_count"] == 1
    assert latest["summary"]["status_counts"]["online"] == 1
    assert observations[0]["id"] == observation["id"]


def test_screen_observation_dedupes_same_observation(test_db):
    _reset_screen_monitoring(test_db)
    service = ScreenMonitoringService()
    session = service.start_session(window_title="Mock Trading Client")

    first = service.record_observation(
        session_id=session["id"],
        source="mock",
        app_status="online",
        window_title="Mock Trading Client",
        confidence=0.8,
        observed_at="2026-05-31T10:00:00",
        detected_items=[{"type": "window_status", "value": "online"}],
    )
    second = service.record_observation(
        session_id=session["id"],
        source="mock",
        app_status="online",
        window_title="Mock Trading Client",
        confidence=0.8,
        observed_at="2026-05-31T10:00:00",
        detected_items=[{"type": "window_status", "value": "online"}],
    )

    assert first["inserted"] is True
    assert second["inserted"] is False
    assert len(service.list_observations()) == 1


def test_screen_observation_safety_blocks_dangerous_payload_terms(test_db):
    _reset_screen_monitoring(test_db)
    service = ScreenMonitoringService()

    observation = service.record_observation(
        source="manual",
        app_status="online",
        raw_payload={"requested_action": "click submit_order"},
    )

    assert observation["live_trading_enabled"] is False
    assert observation["raw_payload"]["blocked_from_execution"] is True
    assert any("click" in item for item in observation["warnings"])
    assert any("submit_order" in item for item in observation["warnings"])


def test_screen_fixture_replay_records_observation_without_real_capture(test_db):
    _reset_screen_monitoring(test_db)
    service = ScreenMonitoringService()

    result = service.replay_fixture("trading_client_warning_popup")
    latest = service.latest_session()

    assert result["status"] == "replayed"
    assert result["provider"] == "fixture"
    assert result["real_screen_capture"] is False
    assert result["ocr_executed"] is False
    assert result["live_trading_enabled"] is False
    assert result["observation"]["app_status"] == "attention_required"
    assert result["observation"]["raw_payload"]["fixture_replay"] is True
    assert result["observation"]["raw_payload"]["ocr_executed"] is False
    assert latest["summary"]["observation_count"] == 1
    assert latest["summary"]["status_counts"]["attention_required"] == 1


def test_screen_provider_capabilities_include_fixture_but_default_disabled(test_db):
    _reset_screen_monitoring(test_db)
    providers = ScreenMonitoringService().provider_capabilities()
    by_provider = {item["provider"]: item for item in providers}

    assert by_provider["disabled"]["configured"] is False
    assert by_provider["disabled"]["capture_supported"] is False
    assert by_provider["disabled"]["capture_stub_supported"] is False
    assert by_provider["fixture"]["configured"] is True
    assert by_provider["fixture"]["fixture_replay_supported"] is True
    assert by_provider["local_safe"]["capture_stub_supported"] is True
    assert by_provider["fixture"]["details"]["real_screen_capture"] is False
    assert all(item["live_trading_enabled"] is False for item in providers)


def test_screen_provider_readiness_runbook_is_read_only_and_blocks_real_adapters(test_db):
    _reset_screen_monitoring(test_db)
    readiness = ScreenMonitoringService().provider_readiness_runbook()
    checks = {item["name"]: item for item in readiness["checks"]}

    assert readiness["stage"] == "V4.5-P19"
    assert readiness["status"] == "disabled_needs_provider_selection"
    assert readiness["active_provider"] == "disabled"
    assert checks["provider_selected"]["status"] == "blocked"
    assert checks["real_pixel_capture_adapter"]["status"] == "blocked"
    assert checks["ocr_adapter"]["status"] == "blocked"
    assert checks["live_trading_disabled"]["status"] == "ready"
    assert "real_pixel_capture" in readiness["runbook"]["blocked_actions"]
    assert "GET /api/screen-monitoring/provider-readiness" in readiness["runbook"]["safe_api_checks"]
    assert readiness["review_only"] is True
    assert readiness["simulation_only"] is True
    assert readiness["live_trading_enabled"] is False


def test_local_safe_provider_readiness_reports_preflight_only_state(test_db):
    _reset_screen_monitoring(test_db)
    provider = LocalSafeScreenCaptureProvider(
        allow_real_capture=True,
        allowed_windows=["Notepad"],
        broker_window_terms=["trading", "证券"],
    )
    readiness = ScreenMonitoringService(provider=provider).provider_readiness_runbook()
    checks = {item["name"]: item for item in readiness["checks"]}

    assert readiness["status"] == "preflight_ready_metadata_only"
    assert readiness["active_provider"] == "local_safe"
    assert readiness["provider_configured"] is True
    assert checks["provider_selected"]["status"] == "ready"
    assert checks["provider_configured"]["status"] == "ready"
    assert checks["harmless_window_allowlist"]["status"] == "ready"
    assert checks["real_pixel_capture_adapter"]["status"] == "blocked"
    assert checks["ocr_adapter"]["status"] == "blocked"
    assert readiness["environment"]["SCREEN_CAPTURE_ALLOWED_WINDOWS_SET"] is False
    assert any("capture preflight" in step.lower() for step in readiness["next_safe_steps"])


def test_provider_config_proposal_is_review_only_and_does_not_apply_env(test_db):
    _reset_screen_monitoring(test_db)
    service = ScreenMonitoringService()

    proposal = service.generate_provider_config_proposal("Untitled - Notepad")
    listed = service.list_provider_config_proposals()
    accepted = service.decide_provider_config_proposal(
        proposal["id"],
        "accepted",
        reviewed_by="tester",
        note="reviewed but not applied",
    )

    assert proposal["status"] == "pending_review"
    assert proposal["provider"] == "local_safe"
    assert proposal["proposal"]["env_patch"]["SCREEN_CAPTURE_PROVIDER"] == "local_safe"
    assert proposal["proposal"]["writes_env"] is False
    assert proposal["proposal"]["executes_commands"] is False
    assert proposal["proposal"]["real_screen_capture_enabled_by_api"] is False
    assert proposal["proposal"]["ocr_enabled_by_api"] is False
    assert proposal["rationale"]["safety"]["pixel_capture"] is False
    assert proposal["live_trading_enabled"] is False
    assert listed[0]["id"] == proposal["id"]
    assert accepted["status"] == "accepted"
    assert accepted["reviewed_by"] == "tester"
    assert accepted["review_note"] == "reviewed but not applied"
    assert accepted["proposal"]["apply_automatically"] is False
    assert accepted["live_trading_enabled"] is False


def test_provider_readiness_scenario_replay_uses_proposal_without_side_effects(test_db):
    _reset_screen_monitoring(test_db)
    service = ScreenMonitoringService()
    proposal = service.generate_provider_config_proposal("Untitled - Notepad")

    replay = service.replay_provider_readiness_scenario(proposal_id=proposal["id"])
    listed = service.list_provider_replay_runs()

    assert replay["status"] == "replay_passed"
    assert replay["proposal_id"] == proposal["id"]
    assert replay["summary"]["proposal_id"] == proposal["id"]
    assert replay["summary"]["allowed_output"] == "review_only_scenario_replay"
    assert replay["summary"]["blocked_count"] == 0
    assert all(step["real_screen_capture"] is False for step in replay["steps"])
    assert all(step["pixel_data_stored"] is False for step in replay["steps"])
    assert all(step["ocr_executed"] is False for step in replay["steps"])
    assert all(step["writes_env"] is False for step in replay["steps"])
    assert all(step["executes_commands"] is False for step in replay["steps"])
    assert replay["review_only"] is True
    assert replay["simulation_only"] is True
    assert replay["live_trading_enabled"] is False
    assert listed[0]["id"] == replay["id"]


def test_screen_readiness_audit_report_consolidates_safe_evidence(test_db):
    _reset_screen_monitoring(test_db)
    service = ScreenMonitoringService()
    proposal = service.generate_provider_config_proposal("Untitled - Notepad")
    service.replay_provider_readiness_scenario(proposal_id=proposal["id"])
    service.record_observation(
        source="capture_stub:local_safe",
        app_status="capture_artifact_stub_ready",
        window_title="Untitled - Notepad",
        confidence=1.0,
        detected_items=[{"type": "capture_artifact_stub", "value": "stub_created"}],
        raw_payload={
            "artifact_status": "stub_created",
            "real_screen_capture": False,
            "pixel_data_stored": False,
            "ocr_executed": False,
            "redaction_applied": True,
        },
        artifact_ref="artifact://screen_capture_stub/audit-report",
        observed_at="2026-05-31T10:00:00",
    )
    service.sync_artifact_review_queue()

    report = service.screen_readiness_audit_report()
    safety = {item["name"]: item for item in report["safety_matrix"]}

    assert report["stage"] == "V4.5-P19"
    assert report["status"] == "review_required"
    assert report["summary"]["allowed_output"] == "review_only_screen_readiness_report"
    assert report["summary"]["config_proposal_count"] == 1
    assert report["summary"]["provider_replay_count"] == 1
    assert report["summary"]["artifact_review_count"] == 1
    assert report["summary"]["observation_count"] >= 1
    assert report["summary"]["safety_passed"] is True
    assert report["evidence"]["provider_readiness"]["live_trading_enabled"] is False
    assert report["evidence"]["artifact_policy"]["pixel_data_stored"] is False
    assert report["evidence"]["provider_replay_runs"][0]["summary"]["allowed_output"] == "review_only_scenario_replay"
    assert safety["live_trading_disabled"]["status"] == "passed"
    assert safety["pixel_capture_blocked"]["status"] == "passed"
    assert safety["ocr_execution_blocked"]["status"] == "passed"
    assert safety["config_proposals_do_not_apply"]["status"] == "passed"
    assert "real_pixel_capture" in report["forbidden_actions"]
    assert report["review_only"] is True
    assert report["simulation_only"] is True
    assert report["live_trading_enabled"] is False


def test_screen_readiness_audit_acknowledgement_is_audit_only(test_db):
    _reset_screen_monitoring(test_db)
    service = ScreenMonitoringService()
    proposal = service.generate_provider_config_proposal("Untitled - Notepad")
    service.replay_provider_readiness_scenario(proposal_id=proposal["id"])

    ack = service.acknowledge_screen_readiness_audit(
        acknowledged_by="tester",
        note="reviewed readiness evidence",
    )
    listed = service.list_screen_readiness_audit_acknowledgements()

    assert ack["status"] == "acknowledged"
    assert ack["report_stage"] == "V4.5-P19"
    assert len(ack["report_hash"]) == 64
    assert ack["acknowledged_by"] == "tester"
    assert ack["acknowledgement_note"] == "reviewed readiness evidence"
    assert ack["acknowledgement_effect"] == "audit_status_only"
    assert ack["summary"]["allowed_output"] == "review_only_screen_readiness_report"
    assert ack["report"]["live_trading_enabled"] is False
    assert ack["writes_env"] is False
    assert ack["executes_commands"] is False
    assert ack["real_screen_capture"] is False
    assert ack["pixel_data_stored"] is False
    assert ack["ocr_executed"] is False
    assert ack["broker_action"] is False
    assert ack["order_action"] is False
    assert ack["credential_access"] is False
    assert ack["review_only"] is True
    assert ack["simulation_only"] is True
    assert ack["live_trading_enabled"] is False
    assert listed[0]["id"] == ack["id"]


def test_screen_readiness_timeline_is_read_only_and_chronological(test_db):
    _reset_screen_monitoring(test_db)
    service = ScreenMonitoringService()
    proposal = service.generate_provider_config_proposal("Untitled - Notepad")
    service.replay_provider_readiness_scenario(proposal_id=proposal["id"])
    service.record_observation(
        source="capture_stub:local_safe",
        app_status="capture_artifact_stub_ready",
        window_title="Untitled - Notepad",
        confidence=1.0,
        detected_items=[{"type": "capture_artifact_stub", "value": "stub_created"}],
        raw_payload={
            "artifact_status": "stub_created",
            "real_screen_capture": False,
            "pixel_data_stored": False,
            "ocr_executed": False,
        },
        artifact_ref="artifact://screen_capture_stub/timeline",
        observed_at="2026-05-31T10:00:00",
    )
    service.sync_artifact_review_queue()
    service.acknowledge_screen_readiness_audit(acknowledged_by="tester")

    timeline = service.screen_readiness_timeline(limit=20)
    item_types = {item["item_type"] for item in timeline["items"]}
    event_ts = [item["event_ts"] for item in timeline["items"]]

    assert timeline["status"] == "timeline_ready"
    assert timeline["stage"] == "V4.5-P19"
    assert timeline["allowed_output"] == "review_only_screen_readiness_timeline"
    assert "readiness_audit_report" in item_types
    assert "screen_observation" in item_types
    assert "artifact_review" in item_types
    assert "provider_config_proposal" in item_types
    assert "provider_replay_run" in item_types
    assert "readiness_audit_acknowledgement" in item_types
    assert event_ts == sorted(event_ts, reverse=True)
    assert all(item["writes_env"] is False for item in timeline["items"])
    assert all(item["executes_commands"] is False for item in timeline["items"])
    assert all(item["real_screen_capture"] is False for item in timeline["items"])
    assert all(item["pixel_data_stored"] is False for item in timeline["items"])
    assert all(item["ocr_executed"] is False for item in timeline["items"])
    assert all(item["broker_action"] is False for item in timeline["items"])
    assert all(item["order_action"] is False for item in timeline["items"])
    assert all(item["credential_access"] is False for item in timeline["items"])
    assert timeline["review_only"] is True
    assert timeline["simulation_only"] is True
    assert timeline["live_trading_enabled"] is False


def test_screen_readiness_evidence_export_is_json_only_bundle(test_db):
    _reset_screen_monitoring(test_db)
    service = ScreenMonitoringService()
    proposal = service.generate_provider_config_proposal("Untitled - Notepad")
    service.replay_provider_readiness_scenario(proposal_id=proposal["id"])
    service.acknowledge_screen_readiness_audit(acknowledged_by="tester")

    bundle = service.screen_readiness_evidence_export(limit=20)

    assert bundle["schema_version"] == "screen_readiness_evidence_export.v1"
    assert bundle["status"] == "export_ready"
    assert bundle["stage"] == "V4.5-P19"
    assert len(bundle["bundle_hash"]) == 64
    assert bundle["export_metadata"]["format"] == "json"
    assert bundle["export_metadata"]["delivery"] == "api_response_only"
    assert bundle["export_metadata"]["writes_file"] is False
    assert bundle["export_metadata"]["download_created"] is False
    assert bundle["export_metadata"]["allowed_output"] == "review_only_screen_readiness_evidence_export"
    assert bundle["capabilities"]["live_trading_enabled"] is False
    assert bundle["provider_readiness"]["live_trading_enabled"] is False
    assert bundle["readiness_audit_report"]["live_trading_enabled"] is False
    assert bundle["readiness_audit_acknowledgements"][0]["live_trading_enabled"] is False
    assert bundle["readiness_timeline"]["allowed_output"] == "review_only_screen_readiness_timeline"
    assert bundle["safety"]["writes_env"] is False
    assert bundle["safety"]["executes_commands"] is False
    assert bundle["safety"]["writes_file"] is False
    assert bundle["safety"]["real_screen_capture"] is False
    assert bundle["safety"]["pixel_data_stored"] is False
    assert bundle["safety"]["ocr_executed"] is False
    assert bundle["safety"]["broker_action"] is False
    assert bundle["safety"]["order_action"] is False
    assert bundle["safety"]["credential_access"] is False
    assert bundle["review_only"] is True
    assert bundle["simulation_only"] is True
    assert bundle["live_trading_enabled"] is False


def test_screen_readiness_evidence_verifier_checks_bundle_safety(test_db):
    _reset_screen_monitoring(test_db)
    service = ScreenMonitoringService()
    proposal = service.generate_provider_config_proposal("Untitled - Notepad")
    service.replay_provider_readiness_scenario(proposal_id=proposal["id"])
    service.acknowledge_screen_readiness_audit(acknowledged_by="tester")

    verification = service.verify_screen_readiness_evidence_export(limit=20)
    checks = {item["name"]: item for item in verification["checks"]}

    assert verification["schema_version"] == "screen_readiness_evidence_verifier.v1"
    assert verification["status"] == "verification_passed"
    assert verification["stage"] == "V4.5-P19"
    assert len(verification["export_bundle_hash"]) == 64
    assert verification["check_count"] == verification["passed_count"]
    assert verification["failed_count"] == 0
    assert checks["bundle_hash_recomputable"]["status"] == "passed"
    assert checks["api_response_only"]["status"] == "passed"
    assert checks["no_file_write"]["status"] == "passed"
    assert checks["no_capture_or_ocr"]["status"] == "passed"
    assert checks["no_broker_or_order"]["status"] == "passed"
    assert checks["live_trading_disabled_everywhere"]["status"] == "passed"
    assert verification["safety_summary"]["writes_file"] is False
    assert verification["safety_summary"]["ocr_executed"] is False
    assert verification["safety_summary"]["broker_action"] is False
    assert verification["allowed_output"] == "review_only_screen_readiness_evidence_verifier"
    assert verification["review_only"] is True
    assert verification["simulation_only"] is True
    assert verification["live_trading_enabled"] is False


def test_screen_readiness_evidence_comparison_is_read_only_and_stable(test_db):
    _reset_screen_monitoring(test_db)
    service = ScreenMonitoringService()
    proposal = service.generate_provider_config_proposal("Untitled - Notepad")
    service.replay_provider_readiness_scenario(proposal_id=proposal["id"])
    service.acknowledge_screen_readiness_audit(acknowledged_by="tester")

    comparison = service.compare_screen_readiness_evidence(limit=20)

    assert comparison["schema_version"] == "screen_readiness_evidence_comparison.v1"
    assert comparison["status"] == "comparison_stable"
    assert comparison["stage"] == "V4.5-P19"
    assert comparison["baseline"]["export_bundle_hash"] == comparison["candidate"]["export_bundle_hash"]
    assert comparison["baseline"]["failed_count"] == 0
    assert comparison["candidate"]["failed_count"] == 0
    assert comparison["difference_count"] == 0
    assert comparison["differences"] == []
    assert "safety_summary" in comparison["comparison_scope"]
    assert comparison["safety_summary"]["writes_file"] is False
    assert comparison["safety_summary"]["download_created"] is False
    assert comparison["safety_summary"]["executes_commands"] is False
    assert comparison["safety_summary"]["ocr_executed"] is False
    assert comparison["safety_summary"]["broker_action"] is False
    assert comparison["safety_summary"]["order_action"] is False
    assert comparison["safety_summary"]["credential_access"] is False
    assert comparison["allowed_output"] == "review_only_screen_readiness_evidence_comparison"
    assert comparison["review_only"] is True
    assert comparison["simulation_only"] is True
    assert comparison["live_trading_enabled"] is False


def test_screen_readiness_health_digest_summarizes_read_only_evidence(test_db):
    _reset_screen_monitoring(test_db)
    service = ScreenMonitoringService()
    proposal = service.generate_provider_config_proposal("Untitled - Notepad")
    service.replay_provider_readiness_scenario(proposal_id=proposal["id"])
    service.acknowledge_screen_readiness_audit(acknowledged_by="tester")

    digest = service.screen_readiness_health_digest(limit=20)
    flags = {item["name"]: item for item in digest["health_flags"]}
    modules = {item["name"]: item for item in digest["module_statuses"]}

    assert digest["schema_version"] == "screen_readiness_health_digest.v1"
    assert digest["status"] == "health_digest_clean"
    assert digest["stage"] == "V4.5-P19"
    assert digest["summary"]["verification_status"] == "verification_passed"
    assert digest["summary"]["comparison_status"] == "comparison_stable"
    assert digest["summary"]["acknowledgement_count"] == 1
    assert len(digest["summary"]["export_bundle_hash"]) == 64
    assert modules["evidence_verifier"]["live_trading_enabled"] is False
    assert modules["evidence_comparison"]["stage"] == "V4.5-P19"
    assert flags["live_trading_disabled"]["status"] == "passed"
    assert flags["verification_passed"]["status"] == "passed"
    assert flags["comparison_stable"]["status"] == "passed"
    assert flags["no_capture_or_ocr"]["status"] == "passed"
    assert flags["no_broker_or_order"]["status"] == "passed"
    assert digest["safety_summary"]["writes_file"] is False
    assert digest["safety_summary"]["download_created"] is False
    assert digest["safety_summary"]["executes_commands"] is False
    assert digest["safety_summary"]["writes_env"] is False
    assert digest["safety_summary"]["real_screen_capture"] is False
    assert digest["safety_summary"]["ocr_executed"] is False
    assert digest["safety_summary"]["broker_action"] is False
    assert digest["safety_summary"]["live_trading_enabled"] is False
    assert digest["allowed_output"] == "review_only_screen_readiness_health_digest"
    assert digest["review_only"] is True
    assert digest["simulation_only"] is True
    assert digest["live_trading_enabled"] is False


def test_screen_readiness_digest_history_proposal_is_review_only(test_db):
    _reset_screen_monitoring(test_db)
    service = ScreenMonitoringService()
    proposal = service.generate_provider_config_proposal("Untitled - Notepad")
    service.replay_provider_readiness_scenario(proposal_id=proposal["id"])
    service.acknowledge_screen_readiness_audit(acknowledged_by="tester")

    proposal_doc = service.screen_readiness_digest_history_proposal(limit=20)
    gates = {item["name"]: item for item in proposal_doc["review_gates"]}

    assert proposal_doc["schema_version"] == "screen_readiness_digest_history_proposal.v1"
    assert proposal_doc["status"] == "proposal_ready"
    assert proposal_doc["stage"] == "V4.5-P19"
    assert proposal_doc["proposal"]["default_state"] == "not_persisted"
    assert proposal_doc["proposal"]["apply_automatically"] is False
    assert proposal_doc["proposal"]["writes_database_now"] is False
    assert proposal_doc["proposal"]["writes_file"] is False
    assert proposal_doc["proposal"]["download_created"] is False
    assert "ocr_text" in proposal_doc["proposal"]["excluded_fields"]
    assert "broker_credentials" in proposal_doc["proposal"]["excluded_fields"]
    assert len(proposal_doc["current_digest_summary"]["export_bundle_hash"]) == 64
    assert proposal_doc["current_digest_summary"]["live_trading_enabled"] is False
    assert gates["schema_review"]["status"] == "required"
    assert gates["manual_enable_required"]["status"] == "required"
    assert proposal_doc["safety_summary"]["writes_database_now"] is False
    assert proposal_doc["safety_summary"]["real_screen_capture"] is False
    assert proposal_doc["safety_summary"]["ocr_executed"] is False
    assert proposal_doc["safety_summary"]["broker_action"] is False
    assert proposal_doc["allowed_output"] == "review_only_screen_readiness_digest_history_proposal"
    assert proposal_doc["review_only"] is True
    assert proposal_doc["simulation_only"] is True
    assert proposal_doc["live_trading_enabled"] is False


def test_screen_readiness_digest_history_migration_checklist_is_review_only(test_db):
    _reset_screen_monitoring(test_db)
    service = ScreenMonitoringService()
    proposal = service.generate_provider_config_proposal("Untitled - Notepad")
    service.replay_provider_readiness_scenario(proposal_id=proposal["id"])
    service.acknowledge_screen_readiness_audit(acknowledged_by="tester")

    checklist = service.screen_readiness_digest_history_migration_checklist(limit=20)
    checks = {item["name"]: item for item in checklist["checks"]}

    assert checklist["schema_version"] == "screen_readiness_digest_history_migration_checklist.v1"
    assert checklist["status"] == "migration_review_ready"
    assert checklist["stage"] == "V4.5-P19"
    assert checklist["migration_plan"]["target_table"] == "screen_readiness_digest_history"
    assert checklist["migration_plan"]["default_state"] == "not_applied"
    assert checklist["migration_plan"]["create_table_now"] is False
    assert checklist["migration_plan"]["writes_database_now"] is False
    assert checklist["migration_plan"]["writes_migration_file_now"] is False
    assert checklist["migration_plan"]["apply_automatically"] is False
    assert checklist["migration_plan"]["rollback_required"] is True
    assert checklist["migration_plan"]["test_required"] is True
    assert len(checklist["field_mapping"]) >= 10
    assert "ocr_text" in checklist["excluded_fields"]
    assert "broker_credentials" in checklist["excluded_fields"]
    assert checks["migration_file_required"]["status"] == "review_required"
    assert checks["rollback_plan_required"]["status"] == "review_required"
    assert checks["persistence_not_enabled_now"]["status"] == "passed"
    assert checklist["summary"]["migration_allowed_now"] is False
    assert checklist["summary"]["review_required_count"] == 2
    assert checklist["summary"]["blocked_check_count"] == 0
    assert len(checklist["summary"]["current_export_bundle_hash"]) == 64
    assert "reviewed_sqlite_migration" in checklist["required_future_artifacts"]
    assert checklist["safety_summary"]["creates_table_now"] is False
    assert checklist["safety_summary"]["runs_migration_now"] is False
    assert checklist["safety_summary"]["writes_database_now"] is False
    assert checklist["safety_summary"]["real_screen_capture"] is False
    assert checklist["safety_summary"]["ocr_executed"] is False
    assert checklist["safety_summary"]["broker_action"] is False
    assert checklist["allowed_output"] == "review_only_screen_readiness_digest_history_migration_checklist"
    assert "run_migration_now" in checklist["forbidden_actions"]
    assert checklist["review_only"] is True
    assert checklist["simulation_only"] is True
    assert checklist["live_trading_enabled"] is False


def test_screen_readiness_digest_history_migration_spec_verifier_is_dry_run(test_db):
    _reset_screen_monitoring(test_db)
    service = ScreenMonitoringService()
    proposal = service.generate_provider_config_proposal("Untitled - Notepad")
    service.replay_provider_readiness_scenario(proposal_id=proposal["id"])
    service.acknowledge_screen_readiness_audit(acknowledged_by="tester")

    verification = service.verify_screen_readiness_digest_history_migration_spec(limit=20)
    checks = {item["name"]: item for item in verification["checks"]}

    assert verification["schema_version"] == "screen_readiness_digest_history_migration_spec_verifier.v1"
    assert verification["status"] == "spec_verification_passed"
    assert verification["stage"] == "V4.5-P19"
    assert len(verification["spec_hash"]) == 64
    assert verification["target_table"] == "screen_readiness_digest_history"
    assert verification["failed_count"] == 0
    assert verification["missing_fields"] == []
    assert checks["required_fields_covered"]["status"] == "passed"
    assert checks["dangerous_sql_absent"]["status"] == "passed"
    assert checks["sensitive_fields_absent"]["status"] == "passed"
    assert verification["migration_allowed_now"] is False
    assert verification["safety_summary"]["executes_sql"] is False
    assert verification["safety_summary"]["runs_migration_now"] is False
    assert verification["safety_summary"]["creates_table_now"] is False
    assert verification["safety_summary"]["writes_database_now"] is False
    assert verification["safety_summary"]["writes_migration_file_now"] is False
    assert verification["safety_summary"]["ocr_executed"] is False
    assert verification["safety_summary"]["broker_action"] is False
    assert verification["allowed_output"] == "review_only_screen_readiness_digest_history_migration_spec_verifier"
    assert "execute_sql" in verification["forbidden_actions"]
    assert verification["review_only"] is True
    assert verification["simulation_only"] is True
    assert verification["live_trading_enabled"] is False


def test_screen_readiness_digest_history_migration_spec_verifier_blocks_unsafe_text(test_db):
    _reset_screen_monitoring(test_db)
    service = ScreenMonitoringService()

    verification = service.verify_screen_readiness_digest_history_migration_spec(
        spec_text="DROP TABLE screen_readiness_digest_history; -- ocr_text broker_credentials",
        limit=20,
    )
    failed = {item["name"]: item for item in verification["failed_checks"]}

    assert verification["status"] == "spec_verification_failed"
    assert failed["dangerous_sql_absent"]["details"]["dangerous_matches"] == ["drop"]
    assert "ocr_text" in failed["sensitive_fields_absent"]["details"]["sensitive_matches"]
    assert "broker_credentials" in failed["sensitive_fields_absent"]["details"]["sensitive_matches"]
    assert verification["safety_blocks"][0]["blocked"] is True
    assert verification["safety_blocks"][1]["blocked"] is True
    assert verification["safety_summary"]["executes_sql"] is False
    assert verification["live_trading_enabled"] is False


def test_screen_readiness_digest_history_migration_spec_approval_is_metadata_only(test_db):
    _reset_screen_monitoring(test_db)
    service = ScreenMonitoringService()

    approval = service.approve_screen_readiness_digest_history_migration_spec(
        approved_by="tester",
        note="reviewed dry-run spec",
        limit=20,
    )
    approvals = service.list_screen_readiness_digest_history_migration_spec_approvals(limit=5)
    timeline = service.screen_readiness_timeline(limit=20)
    timeline_types = {item["item_type"] for item in timeline["items"]}

    assert approval["schema_version"] == "screen_readiness_digest_history_migration_spec_approval.v1"
    assert approval["status"] == "approval_metadata_recorded"
    assert approval["stage"] == "V4.5-P19"
    assert approval["event_id"] is not None
    assert approval["approved_by"] == "tester"
    assert approval["approval_effect"] == "audit_metadata_only"
    assert len(approval["spec_hash"]) == 64
    assert approval["verification_status"] == "spec_verification_passed"
    assert approval["verification_failed_count"] == 0
    assert approval["migration_allowed_now"] is False
    assert approval["safety_summary"]["writes_database_event_now"] is True
    assert approval["safety_summary"]["writes_digest_history_table_now"] is False
    assert approval["safety_summary"]["creates_table_now"] is False
    assert approval["safety_summary"]["runs_migration_now"] is False
    assert approval["safety_summary"]["executes_sql"] is False
    assert approval["safety_summary"]["writes_migration_file_now"] is False
    assert approval["safety_summary"]["broker_action"] is False
    assert approval["allowed_output"] == "review_only_screen_readiness_digest_history_migration_spec_approval"
    assert "explicit_release_approval" in approval["future_migration_still_requires"]
    assert "run_migration_now" in approval["forbidden_actions"]
    assert approval["review_only"] is True
    assert approval["simulation_only"] is True
    assert approval["live_trading_enabled"] is False
    assert approvals[0]["event_id"] == approval["event_id"]
    assert approvals[0]["approval_effect"] == "audit_metadata_only"
    assert "digest_history_migration_spec_approval" in timeline_types


def test_screen_readiness_digest_history_migration_spec_approval_blocks_failed_spec(test_db):
    _reset_screen_monitoring(test_db)
    service = ScreenMonitoringService()

    approval = service.approve_screen_readiness_digest_history_migration_spec(
        spec_text="DROP TABLE screen_readiness_digest_history; -- ocr_text",
        approved_by="tester",
        note="unsafe spec should not be approved",
    )
    approvals = service.list_screen_readiness_digest_history_migration_spec_approvals(limit=5)

    assert approval["status"] == "approval_blocked"
    assert approval["event_id"] is None
    assert approval["verification_status"] == "spec_verification_failed"
    assert approval["verification"]["status"] == "spec_verification_failed"
    assert approval["safety_summary"]["writes_database_event_now"] is False
    assert approval["safety_summary"]["executes_sql"] is False
    assert approval["migration_allowed_now"] is False
    assert approvals == []
    assert approval["live_trading_enabled"] is False


def test_screen_readiness_digest_history_release_readiness_requires_approval(test_db):
    _reset_screen_monitoring(test_db)
    service = ScreenMonitoringService()

    readiness = service.screen_readiness_digest_history_release_readiness(limit=20)
    gates = {item["name"]: item for item in readiness["gates"]}

    assert readiness["schema_version"] == "screen_readiness_digest_history_release_readiness.v1"
    assert readiness["status"] == "release_review_required"
    assert readiness["stage"] == "V4.5-P19"
    assert readiness["decision"]["go_no_go"] == "no_go"
    assert readiness["decision"]["migration_allowed_now"] is False
    assert readiness["evidence"]["approval_count"] == 0
    assert readiness["evidence"]["allowed_output"] == "review_only_screen_readiness_digest_history_release_readiness"
    assert gates["migration_checklist_ready"]["status"] == "passed"
    assert gates["migration_spec_verified"]["status"] == "passed"
    assert gates["operator_approval_recorded"]["status"] == "review_required"
    assert gates["latest_approval_matches_spec"]["status"] == "review_required"
    assert readiness["safety_summary"]["executes_sql"] is False
    assert readiness["safety_summary"]["runs_migration_now"] is False
    assert readiness["safety_summary"]["creates_table_now"] is False
    assert readiness["safety_summary"]["writes_migration_file_now"] is False
    assert readiness["safety_summary"]["writes_digest_history_table_now"] is False
    assert readiness["safety_summary"]["broker_action"] is False
    assert readiness["safety_summary"]["order_action"] is False
    assert readiness["safety_summary"]["credential_access"] is False
    assert readiness["allowed_output"] == "review_only_screen_readiness_digest_history_release_readiness"
    assert "execute_sql" in readiness["forbidden_actions"]
    assert "run_migration_now" in readiness["forbidden_actions"]
    assert readiness["review_only"] is True
    assert readiness["simulation_only"] is True
    assert readiness["live_trading_enabled"] is False


def test_screen_readiness_digest_history_release_readiness_summarizes_approved_spec(test_db):
    _reset_screen_monitoring(test_db)
    service = ScreenMonitoringService()
    approval = service.approve_screen_readiness_digest_history_migration_spec(
        approved_by="tester",
        note="reviewed release readiness source",
        limit=20,
    )

    readiness = service.screen_readiness_digest_history_release_readiness(limit=20)
    gates = {item["name"]: item for item in readiness["gates"]}

    assert readiness["status"] == "release_evidence_ready"
    assert readiness["stage"] == "V4.5-P19"
    assert readiness["decision"]["go_no_go"] == "go_for_manual_release_review"
    assert readiness["decision"]["requires_human_release_approval"] is True
    assert readiness["decision"]["migration_allowed_now"] is False
    assert readiness["evidence"]["approval_count"] == 1
    assert readiness["evidence"]["latest_approval_event_id"] == approval["event_id"]
    assert readiness["evidence"]["approved_spec_hash"] == readiness["evidence"]["spec_hash"]
    assert readiness["evidence"]["latest_approval_status"] == "approval_metadata_recorded"
    assert gates["migration_checklist_ready"]["status"] == "passed"
    assert gates["migration_spec_verified"]["status"] == "passed"
    assert gates["operator_approval_recorded"]["status"] == "passed"
    assert gates["latest_approval_matches_spec"]["status"] == "passed"
    assert gates["no_migration_execution_enabled"]["status"] == "passed"
    assert readiness["required_before_actual_migration"] == [
        "separate_reviewed_migration_file",
        "rollback_plan",
        "migration_tests",
        "api_smoke_tests",
        "database_backup_plan",
        "explicit_operator_release_approval",
    ]
    assert readiness["safety_summary"]["executes_sql"] is False
    assert readiness["safety_summary"]["runs_migration_now"] is False
    assert readiness["safety_summary"]["creates_table_now"] is False
    assert readiness["safety_summary"]["live_trading_enabled"] is False
    assert readiness["live_trading_enabled"] is False


def test_local_safe_preflight_requires_explicit_config(test_db):
    _reset_screen_monitoring(test_db)
    provider = LocalSafeScreenCaptureProvider(
        allow_real_capture=False,
        allowed_windows=["Notepad"],
        broker_window_terms=["trading", "证券"],
    )
    service = ScreenMonitoringService(provider=provider)

    result = service.capture_preflight("Notepad")

    assert result["status"] == "blocked"
    assert result["reason"] == "real_capture_not_explicitly_enabled"
    assert result["capture_would_be_allowed"] is False
    assert result["real_screen_capture"] is False
    assert result["ocr_executed"] is False
    assert result["observation"]["app_status"] == "capture_preflight_blocked"
    assert result["live_trading_enabled"] is False


def test_local_safe_preflight_blocks_broker_windows_even_if_allowlisted(test_db):
    _reset_screen_monitoring(test_db)
    provider = LocalSafeScreenCaptureProvider(
        allow_real_capture=True,
        allowed_windows=["Mock", "Trading"],
        broker_window_terms=["trading", "证券"],
    )
    service = ScreenMonitoringService(provider=provider)

    result = service.capture_preflight("Mock Trading Client")

    assert result["status"] == "blocked"
    assert result["reason"] == "broker_or_trading_window_blocked"
    assert "trading" in result["matched_terms"]
    assert result["capture_would_be_allowed"] is False
    assert result["real_screen_capture"] is False
    assert result["observation"]["warnings"] == ["broker_or_trading_window_blocked"]


def test_local_safe_preflight_passes_harmless_allowlisted_window(test_db):
    _reset_screen_monitoring(test_db)
    provider = LocalSafeScreenCaptureProvider(
        allow_real_capture=True,
        allowed_windows=["Notepad", "Calculator"],
        broker_window_terms=["trading", "证券"],
    )
    service = ScreenMonitoringService(provider=provider)

    result = service.capture_preflight("Untitled - Notepad")
    latest = service.latest_session()

    assert result["status"] == "preflight_passed"
    assert result["reason"] == "harmless_window_allowlisted"
    assert result["capture_would_be_allowed"] is True
    assert result["real_screen_capture"] is False
    assert result["ocr_executed"] is False
    assert result["redaction_required"] is True
    assert result["operator_review_required"] is True
    assert result["observation"]["app_status"] == "capture_preflight_ready"
    assert latest["summary"]["status_counts"]["capture_preflight_ready"] == 1


def test_local_safe_capture_stub_blocks_without_preflight_pass(test_db):
    _reset_screen_monitoring(test_db)
    provider = LocalSafeScreenCaptureProvider(
        allow_real_capture=False,
        allowed_windows=["Notepad"],
        broker_window_terms=["trading", "证券"],
    )
    service = ScreenMonitoringService(provider=provider)

    result = service.capture_harmless_window_stub("Untitled - Notepad")

    assert result["status"] == "blocked"
    assert result["artifact_status"] == "blocked"
    assert result["artifact_ref"] is None
    assert result["real_screen_capture"] is False
    assert result["pixel_data_stored"] is False
    assert result["ocr_executed"] is False
    assert result["observation"]["app_status"] == "capture_artifact_stub_blocked"
    assert result["observation"]["warnings"] == ["real_capture_not_explicitly_enabled"]
    assert result["artifact_review"]["review_status"] == "pending_review"
    assert result["artifact_review"]["redaction"]["pixel_data_stored"] is False


def test_local_safe_capture_stub_records_redacted_artifact_ref_after_harmless_preflight(test_db):
    _reset_screen_monitoring(test_db)
    provider = LocalSafeScreenCaptureProvider(
        allow_real_capture=True,
        allowed_windows=["Notepad"],
        broker_window_terms=["trading", "证券"],
    )
    service = ScreenMonitoringService(provider=provider)

    result = service.capture_harmless_window_stub("Untitled - Notepad")
    latest = service.latest_session()

    assert result["status"] == "captured_stub"
    assert result["artifact_status"] == "stub_created"
    assert result["artifact_ref"].startswith("artifact://screen_capture_stub/")
    assert result["real_screen_capture"] is False
    assert result["pixel_data_stored"] is False
    assert result["ocr_executed"] is False
    assert result["redaction_applied"] is True
    assert result["observation"]["artifact_ref"] == result["artifact_ref"]
    assert result["observation"]["app_status"] == "capture_artifact_stub_ready"
    assert result["artifact_review"]["artifact_ref"] == result["artifact_ref"]
    assert result["artifact_review"]["review_status"] == "pending_review"
    assert latest["summary"]["status_counts"]["capture_artifact_stub_ready"] == 1


def test_screen_artifact_retention_policy_is_metadata_only(test_db):
    _reset_screen_monitoring(test_db)
    policy = ScreenMonitoringService().artifact_retention_policy()

    assert policy["status"] == "metadata_only_policy"
    assert policy["retention_days"] == 7
    assert policy["pixel_data_stored"] is False
    assert policy["real_screen_capture"] is False
    assert policy["ocr_executed"] is False
    assert policy["redaction"]["store_pixel_data"] is False
    assert policy["review_queue"]["decision_effect"] == "audit_status_only"
    assert policy["live_trading_enabled"] is False


def test_screen_artifact_review_queue_sync_and_decision_are_audit_only(test_db):
    _reset_screen_monitoring(test_db)
    service = ScreenMonitoringService()
    observation = service.record_observation(
        source="capture_stub:local_safe",
        app_status="capture_artifact_stub_ready",
        window_title="Untitled - Notepad",
        confidence=1.0,
        detected_items=[{"type": "capture_artifact_stub", "value": "stub_created"}],
        raw_payload={
            "artifact_status": "stub_created",
            "real_screen_capture": False,
            "pixel_data_stored": False,
            "ocr_executed": False,
            "redaction_applied": True,
        },
        artifact_ref="artifact://screen_capture_stub/test-review",
        observed_at="2026-05-31T10:00:00",
    )

    sync = service.sync_artifact_review_queue()
    reviews = service.list_artifact_reviews()
    accepted = service.decide_artifact_review(reviews[0]["id"], "accepted", reviewed_by="tester", note="metadata ok")

    assert observation["inserted"] is True
    assert sync["created_review_count"] == 1
    assert sync["policy"]["pixel_data_stored"] is False
    assert len(reviews) == 1
    assert reviews[0]["review_status"] == "pending_review"
    assert reviews[0]["artifact_ref"] == "artifact://screen_capture_stub/test-review"
    assert reviews[0]["observation"]["raw_payload"]["pixel_data_stored"] is False
    assert accepted["review_status"] == "accepted"
    assert accepted["reviewed_by"] == "tester"
    assert accepted["review_note"] == "metadata ok"
    assert accepted["review_only"] is True
    assert accepted["simulation_only"] is True
    assert accepted["live_trading_enabled"] is False


def test_screen_monitoring_api_smoke(client, test_db):
    _reset_screen_monitoring(test_db)

    capabilities_resp = client.get("/api/screen-monitoring/capabilities")
    providers_resp = client.get("/api/screen-monitoring/providers")
    provider_readiness_resp = client.get("/api/screen-monitoring/provider-readiness")
    readiness_audit_empty_resp = client.get("/api/screen-monitoring/readiness-audit?limit=5")
    readiness_ack_empty_resp = client.get("/api/screen-monitoring/readiness-audit/acknowledgements?limit=5")
    readiness_timeline_empty_resp = client.get("/api/screen-monitoring/readiness-timeline?limit=5")
    readiness_export_empty_resp = client.get("/api/screen-monitoring/readiness-export?limit=5")
    readiness_verify_empty_resp = client.get("/api/screen-monitoring/readiness-export/verify?limit=5")
    readiness_compare_empty_resp = client.get("/api/screen-monitoring/readiness-export/compare?limit=5")
    readiness_health_empty_resp = client.get("/api/screen-monitoring/readiness-health?limit=5")
    readiness_history_proposal_empty_resp = client.get("/api/screen-monitoring/readiness-health/history-proposal?limit=5")
    readiness_history_migration_empty_resp = client.get("/api/screen-monitoring/readiness-health/history-migration-checklist?limit=5")
    readiness_history_spec_empty_resp = client.post(
        "/api/screen-monitoring/readiness-health/history-migration-spec/verify?limit=5",
        json={"spec_text": None},
    )
    readiness_history_spec_approvals_empty_resp = client.get(
        "/api/screen-monitoring/readiness-health/history-migration-spec/approvals?limit=5"
    )
    readiness_history_release_empty_resp = client.get(
        "/api/screen-monitoring/readiness-health/history-migration-release-readiness?limit=5"
    )
    empty_latest_resp = client.get("/api/screen-monitoring/sessions/latest")
    session_resp = client.post(
        "/api/screen-monitoring/sessions",
        json={"name": "test_screen_watch", "source": "mock", "window_title": "Mock Trading Client"},
    )
    observation_resp = client.post("/api/screen-monitoring/observations/mock")
    fixture_resp = client.post(
        "/api/screen-monitoring/observations/fixture-replay",
        json={"fixture_name": "trading_client_online"},
    )
    preflight_resp = client.post(
        "/api/screen-monitoring/capture-preflight",
        json={"target_window_title": "Mock Trading Client"},
    )
    capture_stub_resp = client.post(
        "/api/screen-monitoring/capture-stub",
        json={"target_window_title": "Mock Trading Client"},
    )
    artifact_policy_resp = client.get("/api/screen-monitoring/artifact-policy")
    artifact_sync_resp = client.post("/api/screen-monitoring/artifact-reviews/sync?limit=20")
    artifact_reviews_resp = client.get("/api/screen-monitoring/artifact-reviews?limit=5")
    observations_resp = client.get("/api/screen-monitoring/observations?limit=5")
    latest_resp = client.get("/api/screen-monitoring/sessions/latest")

    assert capabilities_resp.status_code == 200
    assert providers_resp.status_code == 200
    assert provider_readiness_resp.status_code == 200
    assert readiness_audit_empty_resp.status_code == 200
    assert readiness_ack_empty_resp.status_code == 200
    assert readiness_timeline_empty_resp.status_code == 200
    assert readiness_export_empty_resp.status_code == 200
    assert readiness_verify_empty_resp.status_code == 200
    assert readiness_compare_empty_resp.status_code == 200
    assert readiness_health_empty_resp.status_code == 200
    assert readiness_history_proposal_empty_resp.status_code == 200
    assert readiness_history_migration_empty_resp.status_code == 200
    assert readiness_history_spec_empty_resp.status_code == 200
    assert readiness_history_spec_approvals_empty_resp.status_code == 200
    assert readiness_history_release_empty_resp.status_code == 200
    assert empty_latest_resp.status_code == 200
    assert session_resp.status_code == 200
    assert observation_resp.status_code == 200
    assert fixture_resp.status_code == 200
    assert preflight_resp.status_code == 200
    assert capture_stub_resp.status_code == 200
    assert artifact_policy_resp.status_code == 200
    assert artifact_sync_resp.status_code == 200
    assert artifact_reviews_resp.status_code == 200
    assert observations_resp.status_code == 200
    assert latest_resp.status_code == 200
    assert capabilities_resp.json()["live_trading_enabled"] is False
    assert capabilities_resp.json()["provider_configured"] is False
    assert provider_readiness_resp.json()["stage"] == "V4.5-P19"
    assert provider_readiness_resp.json()["live_trading_enabled"] is False
    assert "ocr_execution" in provider_readiness_resp.json()["runbook"]["blocked_actions"]
    assert readiness_audit_empty_resp.json()["stage"] == "V4.5-P19"
    assert readiness_audit_empty_resp.json()["summary"]["allowed_output"] == "review_only_screen_readiness_report"
    assert readiness_ack_empty_resp.json() == []
    assert readiness_timeline_empty_resp.json()["stage"] == "V4.5-P19"
    assert readiness_timeline_empty_resp.json()["allowed_output"] == "review_only_screen_readiness_timeline"
    assert readiness_export_empty_resp.json()["stage"] == "V4.5-P19"
    assert readiness_export_empty_resp.json()["export_metadata"]["writes_file"] is False
    assert readiness_export_empty_resp.json()["safety"]["ocr_executed"] is False
    assert readiness_verify_empty_resp.json()["stage"] == "V4.5-P19"
    assert readiness_verify_empty_resp.json()["status"] == "verification_passed"
    assert readiness_compare_empty_resp.json()["stage"] == "V4.5-P19"
    assert readiness_compare_empty_resp.json()["status"] == "comparison_stable"
    assert readiness_health_empty_resp.json()["stage"] == "V4.5-P19"
    assert readiness_health_empty_resp.json()["allowed_output"] == "review_only_screen_readiness_health_digest"
    assert readiness_history_proposal_empty_resp.json()["stage"] == "V4.5-P19"
    assert readiness_history_proposal_empty_resp.json()["proposal"]["writes_database_now"] is False
    assert readiness_history_migration_empty_resp.json()["stage"] == "V4.5-P19"
    assert readiness_history_migration_empty_resp.json()["migration_plan"]["create_table_now"] is False
    assert readiness_history_migration_empty_resp.json()["summary"]["migration_allowed_now"] is False
    assert readiness_history_spec_empty_resp.json()["stage"] == "V4.5-P19"
    assert readiness_history_spec_empty_resp.json()["status"] == "spec_verification_passed"
    assert readiness_history_spec_empty_resp.json()["safety_summary"]["executes_sql"] is False
    assert readiness_history_spec_empty_resp.json()["migration_allowed_now"] is False
    assert readiness_history_spec_approvals_empty_resp.json() == []
    assert readiness_history_release_empty_resp.json()["stage"] == "V4.5-P19"
    assert readiness_history_release_empty_resp.json()["status"] == "release_review_required"
    assert readiness_history_release_empty_resp.json()["decision"]["migration_allowed_now"] is False
    assert readiness_history_release_empty_resp.json()["safety_summary"]["executes_sql"] is False
    config_proposal_resp = client.post(
        "/api/screen-monitoring/provider-config-proposals",
        json={"target_window_title": "Untitled - Notepad"},
    )
    config_proposals_resp = client.get("/api/screen-monitoring/provider-config-proposals?limit=5")
    assert config_proposal_resp.status_code == 200
    assert config_proposals_resp.status_code == 200
    assert config_proposal_resp.json()["proposal"]["writes_env"] is False
    assert config_proposal_resp.json()["proposal"]["executes_commands"] is False
    proposal_id = config_proposal_resp.json()["id"]
    config_approve_resp = client.post(
        f"/api/screen-monitoring/provider-config-proposals/{proposal_id}/approve",
        json={"reviewed_by": "api-smoke", "note": "proposal reviewed"},
    )
    config_reject_resp = client.post(
        f"/api/screen-monitoring/provider-config-proposals/{proposal_id}/reject",
        json={"reviewed_by": "api-smoke", "note": "proposal rejected"},
    )
    provider_replay_resp = client.post(
        "/api/screen-monitoring/provider-replay",
        json={"proposal_id": proposal_id, "scenario_name": "api_smoke_replay"},
    )
    provider_replay_runs_resp = client.get("/api/screen-monitoring/provider-replay?limit=5")
    readiness_audit_resp = client.get("/api/screen-monitoring/readiness-audit?limit=5")
    readiness_ack_resp = client.post(
        "/api/screen-monitoring/readiness-audit/acknowledge",
        json={"acknowledged_by": "api-smoke", "note": "readiness report reviewed"},
    )
    readiness_acks_resp = client.get("/api/screen-monitoring/readiness-audit/acknowledgements?limit=5")
    readiness_timeline_resp = client.get("/api/screen-monitoring/readiness-timeline?limit=20")
    readiness_export_resp = client.get("/api/screen-monitoring/readiness-export?limit=20")
    readiness_verify_resp = client.get("/api/screen-monitoring/readiness-export/verify?limit=20")
    readiness_compare_resp = client.get("/api/screen-monitoring/readiness-export/compare?limit=20")
    readiness_health_resp = client.get("/api/screen-monitoring/readiness-health?limit=20")
    readiness_history_proposal_resp = client.get("/api/screen-monitoring/readiness-health/history-proposal?limit=20")
    readiness_history_migration_resp = client.get("/api/screen-monitoring/readiness-health/history-migration-checklist?limit=20")
    readiness_history_spec_resp = client.post(
        "/api/screen-monitoring/readiness-health/history-migration-spec/verify?limit=20",
        json={"spec_text": None},
    )
    readiness_history_spec_approval_resp = client.post(
        "/api/screen-monitoring/readiness-health/history-migration-spec/approve?limit=20",
        json={"spec_text": None, "approved_by": "api-smoke", "note": "spec metadata reviewed"},
    )
    readiness_history_spec_approvals_resp = client.get(
        "/api/screen-monitoring/readiness-health/history-migration-spec/approvals?limit=5"
    )
    readiness_history_release_resp = client.get(
        "/api/screen-monitoring/readiness-health/history-migration-release-readiness?limit=20"
    )
    assert config_approve_resp.status_code == 200
    assert config_reject_resp.status_code == 200
    assert provider_replay_resp.status_code == 200
    assert provider_replay_runs_resp.status_code == 200
    assert readiness_audit_resp.status_code == 200
    assert readiness_ack_resp.status_code == 200
    assert readiness_acks_resp.status_code == 200
    assert readiness_timeline_resp.status_code == 200
    assert readiness_export_resp.status_code == 200
    assert readiness_verify_resp.status_code == 200
    assert readiness_compare_resp.status_code == 200
    assert readiness_health_resp.status_code == 200
    assert readiness_history_proposal_resp.status_code == 200
    assert readiness_history_migration_resp.status_code == 200
    assert readiness_history_spec_resp.status_code == 200
    assert readiness_history_spec_approval_resp.status_code == 200
    assert readiness_history_spec_approvals_resp.status_code == 200
    assert readiness_history_release_resp.status_code == 200
    assert config_approve_resp.json()["status"] == "accepted"
    assert config_reject_resp.json()["status"] == "rejected"
    assert config_reject_resp.json()["live_trading_enabled"] is False
    assert provider_replay_resp.json()["status"] == "replay_passed"
    assert provider_replay_resp.json()["summary"]["allowed_output"] == "review_only_scenario_replay"
    assert provider_replay_resp.json()["live_trading_enabled"] is False
    assert provider_replay_runs_resp.json()[0]["scenario_name"] == "api_smoke_replay"
    assert readiness_audit_resp.json()["summary"]["provider_replay_count"] >= 1
    assert readiness_audit_resp.json()["summary"]["live_trading_enabled"] is False
    assert readiness_audit_resp.json()["summary"]["allowed_output"] == "review_only_screen_readiness_report"
    assert readiness_ack_resp.json()["acknowledgement_effect"] == "audit_status_only"
    assert readiness_ack_resp.json()["acknowledged_by"] == "api-smoke"
    assert readiness_ack_resp.json()["writes_env"] is False
    assert readiness_ack_resp.json()["executes_commands"] is False
    assert readiness_ack_resp.json()["live_trading_enabled"] is False
    assert readiness_acks_resp.json()[0]["id"] == readiness_ack_resp.json()["id"]
    timeline_types = {item["item_type"] for item in readiness_timeline_resp.json()["items"]}
    assert "readiness_audit_report" in timeline_types
    assert "readiness_audit_acknowledgement" in timeline_types
    assert readiness_timeline_resp.json()["live_trading_enabled"] is False
    assert readiness_export_resp.json()["schema_version"] == "screen_readiness_evidence_export.v1"
    assert readiness_export_resp.json()["export_metadata"]["allowed_output"] == "review_only_screen_readiness_evidence_export"
    assert readiness_export_resp.json()["safety"]["writes_file"] is False
    assert readiness_export_resp.json()["safety"]["live_trading_enabled"] is False
    assert readiness_verify_resp.json()["schema_version"] == "screen_readiness_evidence_verifier.v1"
    assert readiness_verify_resp.json()["status"] == "verification_passed"
    assert readiness_verify_resp.json()["failed_count"] == 0
    assert readiness_verify_resp.json()["allowed_output"] == "review_only_screen_readiness_evidence_verifier"
    assert readiness_verify_resp.json()["safety_summary"]["live_trading_enabled"] is False
    assert readiness_compare_resp.json()["schema_version"] == "screen_readiness_evidence_comparison.v1"
    assert readiness_compare_resp.json()["status"] == "comparison_stable"
    assert readiness_compare_resp.json()["difference_count"] == 0
    assert readiness_compare_resp.json()["allowed_output"] == "review_only_screen_readiness_evidence_comparison"
    assert readiness_compare_resp.json()["safety_summary"]["live_trading_enabled"] is False
    assert readiness_health_resp.json()["schema_version"] == "screen_readiness_health_digest.v1"
    assert readiness_health_resp.json()["status"] == "health_digest_clean"
    assert readiness_health_resp.json()["summary"]["verification_status"] == "verification_passed"
    assert readiness_health_resp.json()["summary"]["comparison_status"] == "comparison_stable"
    assert readiness_health_resp.json()["safety_summary"]["ocr_executed"] is False
    assert readiness_health_resp.json()["live_trading_enabled"] is False
    assert readiness_history_proposal_resp.json()["schema_version"] == "screen_readiness_digest_history_proposal.v1"
    assert readiness_history_proposal_resp.json()["status"] == "proposal_ready"
    assert readiness_history_proposal_resp.json()["proposal"]["default_state"] == "not_persisted"
    assert readiness_history_proposal_resp.json()["safety_summary"]["writes_database_now"] is False
    assert readiness_history_proposal_resp.json()["live_trading_enabled"] is False
    assert readiness_history_migration_resp.json()["schema_version"] == "screen_readiness_digest_history_migration_checklist.v1"
    assert readiness_history_migration_resp.json()["status"] == "migration_review_ready"
    assert readiness_history_migration_resp.json()["migration_plan"]["default_state"] == "not_applied"
    assert readiness_history_migration_resp.json()["migration_plan"]["writes_database_now"] is False
    assert readiness_history_migration_resp.json()["summary"]["migration_allowed_now"] is False
    assert readiness_history_migration_resp.json()["safety_summary"]["runs_migration_now"] is False
    assert readiness_history_migration_resp.json()["live_trading_enabled"] is False
    assert readiness_history_spec_resp.json()["schema_version"] == "screen_readiness_digest_history_migration_spec_verifier.v1"
    assert readiness_history_spec_resp.json()["status"] == "spec_verification_passed"
    assert readiness_history_spec_resp.json()["failed_count"] == 0
    assert readiness_history_spec_resp.json()["migration_allowed_now"] is False
    assert readiness_history_spec_resp.json()["safety_summary"]["executes_sql"] is False
    assert readiness_history_spec_resp.json()["live_trading_enabled"] is False
    assert readiness_history_spec_approval_resp.json()["schema_version"] == "screen_readiness_digest_history_migration_spec_approval.v1"
    assert readiness_history_spec_approval_resp.json()["status"] == "approval_metadata_recorded"
    assert readiness_history_spec_approval_resp.json()["approval_effect"] == "audit_metadata_only"
    assert readiness_history_spec_approval_resp.json()["approved_by"] == "api-smoke"
    assert readiness_history_spec_approval_resp.json()["safety_summary"]["creates_table_now"] is False
    assert readiness_history_spec_approval_resp.json()["safety_summary"]["runs_migration_now"] is False
    assert readiness_history_spec_approval_resp.json()["migration_allowed_now"] is False
    assert readiness_history_spec_approval_resp.json()["live_trading_enabled"] is False
    assert readiness_history_spec_approvals_resp.json()[0]["event_id"] == readiness_history_spec_approval_resp.json()["event_id"]
    assert readiness_history_release_resp.json()["schema_version"] == "screen_readiness_digest_history_release_readiness.v1"
    assert readiness_history_release_resp.json()["status"] == "release_evidence_ready"
    assert readiness_history_release_resp.json()["decision"]["go_no_go"] == "go_for_manual_release_review"
    assert readiness_history_release_resp.json()["evidence"]["approval_count"] >= 1
    assert readiness_history_release_resp.json()["safety_summary"]["runs_migration_now"] is False
    assert readiness_history_release_resp.json()["safety_summary"]["creates_table_now"] is False
    assert readiness_history_release_resp.json()["live_trading_enabled"] is False
    assert any(item["provider"] == "fixture" for item in providers_resp.json())
    assert empty_latest_resp.json()["status"] == "empty"
    assert session_resp.json()["status"] == "running"
    assert observation_resp.json()["review_only"] is True
    assert observation_resp.json()["simulation_only"] is True
    assert observation_resp.json()["live_trading_enabled"] is False
    assert fixture_resp.json()["real_screen_capture"] is False
    assert fixture_resp.json()["ocr_executed"] is False
    assert fixture_resp.json()["observation"]["raw_payload"]["fixture_replay"] is True
    assert preflight_resp.json()["status"] == "blocked"
    assert preflight_resp.json()["capture_would_be_allowed"] is False
    assert preflight_resp.json()["real_screen_capture"] is False
    assert capture_stub_resp.json()["status"] == "blocked"
    assert capture_stub_resp.json()["artifact_status"] == "not_created"
    assert capture_stub_resp.json()["real_screen_capture"] is False
    assert capture_stub_resp.json()["pixel_data_stored"] is False
    assert capture_stub_resp.json()["ocr_executed"] is False
    assert capture_stub_resp.json()["observation"]["app_status"] == "capture_artifact_stub_blocked"
    assert capture_stub_resp.json()["artifact_review"]["review_status"] == "pending_review"
    assert artifact_policy_resp.json()["pixel_data_stored"] is False
    assert artifact_policy_resp.json()["review_queue"]["decision_effect"] == "audit_status_only"
    assert artifact_sync_resp.json()["skipped_existing_count"] >= 1
    assert artifact_reviews_resp.json()[0]["review_status"] == "pending_review"
    review_id = artifact_reviews_resp.json()[0]["id"]
    approve_resp = client.post(
        f"/api/screen-monitoring/artifact-reviews/{review_id}/approve",
        json={"reviewed_by": "api-smoke", "note": "metadata reviewed"},
    )
    reject_resp = client.post(
        f"/api/screen-monitoring/artifact-reviews/{review_id}/reject",
        json={"reviewed_by": "api-smoke", "note": "metadata rejected"},
    )
    assert approve_resp.status_code == 200
    assert reject_resp.status_code == 200
    assert approve_resp.json()["review_status"] == "accepted"
    assert reject_resp.json()["review_status"] == "rejected"
    assert reject_resp.json()["live_trading_enabled"] is False
    assert observations_resp.json()
    assert latest_resp.json()["summary"]["observation_count"] == 4
    assert client.get("/health").json()["live_trading_enabled"] is False
