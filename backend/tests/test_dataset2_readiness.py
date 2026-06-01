import json

from app.learning.dataset2_readiness import Dataset2TrainingReadinessService


def _write_dataset2_pack(tmp_path, records):
    pack = tmp_path / "a_share_trading_training_pack_v2"
    (pack / "dataset").mkdir(parents=True)
    (pack / "validation").mkdir()
    (pack / "schemas").mkdir()
    with (pack / "dataset" / "all_training_patterns.jsonl").open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    (pack / "validation" / "check_report.json").write_text(
        json.dumps({"dataset_version": "0.2.0", "status": "PASS"}),
        encoding="utf-8",
    )
    (pack / "validation" / "manifest.json").write_text(
        json.dumps({"status": "PASS"}),
        encoding="utf-8",
    )
    (pack / "schemas" / "pattern_schema.json").write_text(
        json.dumps({"title": "fixture schema"}),
        encoding="utf-8",
    )
    return pack


def _record(**overrides):
    data = {
        "dataset_version": "0.2.0",
        "pattern_id": "FIXTURE_001",
        "pattern_name": "fixture pattern",
        "category": "fixture",
        "source_id": "SRC_FIXTURE",
        "source_document": "fixture.pdf",
        "timeframe": "daily",
        "market_phase": ["low_area"],
        "preconditions": ["clean setup"],
        "observable_features": ["high_volume"],
        "trigger_conditions": ["price and volume confirm"],
        "confirmation_signals": ["follow through"],
        "negative_filters": ["limit up without liquidity"],
        "invalidation_conditions": ["breaks support"],
        "expected_bias": "bullish",
        "action_label": "WAIT_CONFIRMATION",
        "risk_level": "medium",
        "confidence": "medium",
        "software_tags": ["fixture"],
        "rule_logic": "wait for confirmation",
        "evidence_summary": "fixture evidence",
        "training_notes": "fixture notes",
        "stock_code": "SZ000001",
        "signal_date": "2026-05-01",
        "entry_price": 10.0,
        "exit_price": 10.5,
        "forward_return_5d": 0.05,
        "max_favorable_excursion": 0.08,
        "max_adverse_excursion": -0.02,
        "benchmark_return": 0.01,
        "split_tag": "train",
        "model_targets": {
            "direction_bias": "bullish",
            "trade_intent": "simulate_only",
            "allow_live_order": False,
            "requires_backtest": True,
            "requires_human_review_for_real_trade": True,
        },
    }
    data.update(overrides)
    return data


def _manual_evidence_package():
    return {
        "historical_outcome_source": {
            "source_name": "reviewed_outcome_fixture",
            "source_hash": "abc123",
            "join_keys": ["stock_code", "signal_date"],
            "field_coverage": {
                "stock_code": True,
                "signal_date": True,
                "entry_price": True,
                "exit_price": True,
                "forward_return_5d": True,
                "max_favorable_excursion": True,
                "max_adverse_excursion": True,
                "benchmark_return": True,
                "split_tag": True,
            },
        },
        "quality_flag_dispositions": [
            {"flag": "risk_level_normalized", "disposition": "accept_with_evidence", "evidence_ref": "manual-review-1"}
        ],
        "split_policy_ack": {"policy_id": "time_aware_70_30", "deterministic": True},
        "label_support_policy": {"policy": "class_weighting", "rationale": "low-support labels remain separated"},
        "reviewer": {"name": "tester", "reviewed_at": "2026-06-01T10:00:00"},
    }


def test_dataset2_readiness_blocks_unclean_training_data(tmp_path):
    pack = _write_dataset2_pack(
        tmp_path,
        [
            _record(
                pattern_id="BAD_RISK",
                risk_level="low_to_medium",
                observable_features=["['big_yang']", "high_volume"],
                evidence_summary="",
                invalidation_conditions=[],
                stock_code=None,
            ),
            _record(pattern_id="GOOD_RISK", action_label="RISK_ALERT", risk_level="high"),
        ],
    )

    data = Dataset2TrainingReadinessService().readiness(source_dir=str(pack))

    assert data["stage"] == "V5.6-P17"
    assert data["status"] == "training_blocked_cleanup_required"
    assert data["quality"]["invalid_risk_level_count"] == 1
    assert data["quality"]["stringified_list_item_count"] == 1
    assert data["quality"]["missing_evidence_counts"]["evidence_summary"] == 1
    assert data["decision"]["can_use_as_rule_knowledge"] is True
    assert data["decision"]["can_start_training_now"] is False
    assert data["safety_summary"]["training_started_now"] is False
    assert data["safety_summary"]["writes_database_now"] is False
    assert data["live_trading_enabled"] is False


def test_dataset2_normalized_preview_cleans_known_weak_labels(tmp_path):
    pack = _write_dataset2_pack(
        tmp_path,
        [
            _record(
                pattern_id="NORMALIZE_ME",
                risk_level="medium_high",
                observable_features=["['big_yang']", "high_volume"],
            )
        ],
    )

    data = Dataset2TrainingReadinessService().normalized_preview(source_dir=str(pack))

    assert data["status"] == "normalized_preview_ready"
    assert data["decision"]["training_started_now"] is False
    assert data["records"][0]["risk_level"] == "high"
    assert data["records"][0]["risk_level_original"] == "medium_high"
    assert data["records"][0]["observable_features"] == ["big_yang", "high_volume"]
    assert "risk_level_normalized" in data["records"][0]["quality_flags"]
    assert data["records"][0]["cleanup_operations"][0]["operation"] == "normalize_enum"


def test_dataset2_cleanup_package_summarizes_review_actions_without_writes(tmp_path):
    pack = _write_dataset2_pack(
        tmp_path,
        [
            _record(
                pattern_id="NEEDS_CLEANUP",
                risk_level="low_to_medium",
                observable_features=["['big_yang']", "high_volume"],
                evidence_summary="",
                signal_date=None,
            )
        ],
    )

    data = Dataset2TrainingReadinessService().cleanup_package(source_dir=str(pack))

    assert data["stage"] == "V5.6-P17"
    assert data["status"] == "cleanup_package_ready_for_review"
    assert len(data["package_id"]) == 64
    assert len(data["normalized_records_hash"]) == 64
    assert data["summary"]["risk_level_change_count"] == 1
    assert data["summary"]["stringified_list_item_count"] == 1
    assert data["summary"]["missing_evidence_total"] >= 1
    assert data["decision"]["cleanup_package_ready"] is True
    assert data["decision"]["cleanup_can_be_applied_automatically"] is False
    assert data["decision"]["can_export_file_now"] is False
    assert data["decision"]["can_import_to_database_now"] is False
    assert data["decision"]["can_start_training_now"] is False
    assert data["safety_summary"]["writes_source_dataset"] is False
    assert data["safety_summary"]["normalized_records_persisted"] is False
    assert data["safety_summary"]["training_started_now"] is False
    actions = {item["name"]: item for item in data["cleanup_actions"]}
    assert actions["risk_level_normalization"]["status"] == "ready_for_review"
    assert actions["stringified_list_normalization"]["count"] == 1
    assert actions["historical_outcome_join_required"]["status"] == "blocked"


def test_dataset2_import_queue_review_records_metadata_only(tmp_path, test_db):
    pack = _write_dataset2_pack(
        tmp_path,
        [
            _record(
                pattern_id="QUEUE_REVIEW",
                risk_level="low_to_medium",
                observable_features=["['big_yang']", "high_volume"],
                evidence_summary="",
                signal_date=None,
            )
        ],
    )
    service = Dataset2TrainingReadinessService()

    data = service.create_import_queue_review(
        source_dir=str(pack),
        limit=10,
        reviewed_by="tester",
        note="metadata only",
    )

    assert data["stage"] == "V5.6-P17"
    assert data["status"] == "import_queue_review_recorded"
    assert isinstance(data["event_id"], int)
    assert data["decision"]["writes_existing_event_now"] is True
    assert data["decision"]["normalized_records_persisted"] is False
    assert data["decision"]["training_started_now"] is False
    assert data["decision"]["can_import_to_database_now"] is False
    assert data["safety_summary"]["writes_existing_event_now"] is True
    assert data["safety_summary"]["writes_database_now"] is False
    assert data["safety_summary"]["normalized_records_persisted"] is False
    assert data["normalized_records_preview"] is None

    reviews = service.list_import_queue_reviews(limit=5)
    latest = reviews[0]
    assert latest["id"] == data["event_id"]
    assert latest["package_id"] == data["package_id"]
    assert latest["review"]["reviewed_by"] == "tester"
    assert latest["review"]["source_records_included"] is False
    assert latest["review"]["normalized_records_included"] is False
    assert "normalized_records_preview" not in latest


def test_dataset2_staging_import_requires_review_and_avoids_training_tables(tmp_path, test_db):
    pack = _write_dataset2_pack(
        tmp_path,
        [
            _record(pattern_id="STAGE_001", risk_level="medium_high"),
            _record(pattern_id="STAGE_002", action_label="RISK_ALERT", risk_level="high"),
        ],
    )
    service = Dataset2TrainingReadinessService()

    blocked = service.import_reviewed_to_staging(source_dir=str(pack), limit=10, imported_by="tester")

    assert blocked["status"] == "import_blocked_missing_review"
    assert blocked["decision"]["writes_database_now"] is False
    assert blocked["decision"]["writes_staging_records_now"] is False
    assert blocked["decision"]["training_started_now"] is False

    review = service.create_import_queue_review(source_dir=str(pack), limit=10, reviewed_by="tester")
    imported = service.import_reviewed_to_staging(
        source_dir=str(pack),
        limit=10,
        review_event_id=review["event_id"],
        imported_by="tester",
        note="stage reviewed records only",
    )

    assert imported["stage"] == "V5.6-P17"
    assert imported["status"] == "staging_import_recorded"
    assert imported["imported_count"] == 2
    assert imported["review_event_id"] == review["event_id"]
    assert imported["decision"]["writes_staging_records_now"] is True
    assert imported["decision"]["writes_learning_samples_now"] is False
    assert imported["decision"]["normalized_records_persisted_to_staging"] is True
    assert imported["decision"]["normalized_records_persisted_to_training"] is False
    assert imported["decision"]["training_started_now"] is False
    assert imported["decision"]["can_start_training_now"] is False

    staged = service.list_staging_records(package_id=imported["package_id"], limit=10)
    assert len(staged) == 2
    assert {item["pattern_id"] for item in staged} == {"STAGE_001", "STAGE_002"}
    assert staged[0]["status"] == "staged_review_only"
    assert staged[0]["review_only"] is True
    assert staged[0]["live_trading_enabled"] is False

    summary = service.staging_summary()
    assert summary["record_count"] == 2
    assert summary["decision"]["writes_learning_samples_now"] is False
    assert summary["decision"]["learning_sample_count"] == 0
    assert summary["decision"]["training_started_now"] is False


def test_dataset2_staging_quality_review_blocks_training_freeze(tmp_path, test_db):
    pack = _write_dataset2_pack(
        tmp_path,
        [
            _record(pattern_id="FREEZE_001", risk_level="medium_high", split_tag="train"),
            _record(pattern_id="FREEZE_002", action_label="RISK_ALERT", risk_level="high", split_tag="train"),
        ],
    )
    service = Dataset2TrainingReadinessService()
    review = service.create_import_queue_review(source_dir=str(pack), limit=10, reviewed_by="tester")
    imported = service.import_reviewed_to_staging(
        source_dir=str(pack),
        limit=10,
        review_event_id=review["event_id"],
        imported_by="tester",
    )

    quality = service.staging_quality_review(
        package_id=imported["package_id"],
        reviewed_by="tester",
        note="freeze gate review",
    )

    assert quality["stage"] == "V5.6-P17"
    assert quality["status"] == "training_freeze_blocked"
    assert isinstance(quality["event_id"], int)
    assert quality["record_count"] == 2
    assert quality["summary"]["blocked_gate_count"] >= 1
    gate_status = {gate["name"]: gate["status"] for gate in quality["gates"]}
    assert gate_status["staging_records_present"] == "passed"
    assert gate_status["split_coverage"] == "blocked"
    assert quality["decision"]["writes_learning_samples_now"] is False
    assert quality["decision"]["training_started_now"] is False
    assert quality["decision"]["training_freeze_allowed"] is False
    assert quality["decision"]["can_start_training_now"] is False
    assert quality["review"]["record_bodies_included"] is False
    assert "records" not in quality

    reviews = service.list_staging_quality_reviews(limit=5)
    assert reviews[0]["id"] == quality["event_id"]
    assert reviews[0]["package_id"] == imported["package_id"]


def test_dataset2_staging_fix_plan_uses_quality_review_without_mutation(tmp_path, test_db):
    pack = _write_dataset2_pack(
        tmp_path,
        [
            _record(pattern_id="FIX_PLAN_001", risk_level="medium_high", split_tag="train"),
            _record(pattern_id="FIX_PLAN_002", action_label="RISK_ALERT", risk_level="high", split_tag="train"),
        ],
    )
    service = Dataset2TrainingReadinessService()

    missing = service.staging_fix_plan(quality_review_id=999999, planned_by="tester")
    assert missing["status"] == "fix_plan_blocked_missing_quality_review"
    assert missing["decision"]["writes_existing_event_now"] is False
    assert missing["decision"]["training_started_now"] is False

    review = service.create_import_queue_review(source_dir=str(pack), limit=10, reviewed_by="tester")
    imported = service.import_reviewed_to_staging(
        source_dir=str(pack),
        limit=10,
        review_event_id=review["event_id"],
        imported_by="tester",
    )
    quality = service.staging_quality_review(package_id=imported["package_id"], reviewed_by="tester")
    plan = service.staging_fix_plan(
        quality_review_id=quality["event_id"],
        planned_by="tester",
        note="plan only",
    )

    assert plan["stage"] == "V5.6-P17"
    assert plan["status"] == "fix_plan_ready_for_review"
    assert isinstance(plan["event_id"], int)
    assert plan["quality_review_id"] == quality["event_id"]
    assert plan["summary"]["action_item_count"] >= 1
    assert plan["plan"]["can_be_applied_automatically_now"] is False
    assert plan["plan"]["record_bodies_included"] is False
    assert plan["decision"]["writes_staging_records_now"] is False
    assert plan["decision"]["writes_learning_samples_now"] is False
    assert plan["decision"]["mutates_staging_records_now"] is False
    assert plan["decision"]["training_started_now"] is False
    assert plan["decision"]["can_start_training_now"] is False
    assert all(item["review_only"] is True for item in plan["action_items"])
    assert any(item["gate_name"] == "split_coverage" for item in plan["action_items"])

    plans = service.list_staging_fix_plans(limit=5)
    assert plans[0]["id"] == plan["event_id"]
    assert plans[0]["review"]["planned_by"] == "tester"


def test_dataset2_staging_fix_plan_approval_and_preflight_are_metadata_only(tmp_path, test_db):
    pack = _write_dataset2_pack(
        tmp_path,
        [
            _record(pattern_id="FIX_PREFLIGHT_001", risk_level="medium_high", split_tag="train"),
            _record(pattern_id="FIX_PREFLIGHT_002", action_label="RISK_ALERT", risk_level="high", split_tag="train"),
        ],
    )
    service = Dataset2TrainingReadinessService()

    blocked_preflight = service.staging_fix_preflight(approval_event_id=999999, requested_by="tester")
    assert blocked_preflight["status"] == "preflight_blocked_missing_approval"
    assert blocked_preflight["decision"]["writes_existing_event_now"] is False
    assert blocked_preflight["decision"]["mutates_staging_records_now"] is False

    missing_approval = service.approve_staging_fix_plan(fix_plan_event_id=999999, approved_by="tester")
    assert missing_approval["status"] == "approval_blocked_missing_fix_plan"
    assert missing_approval["decision"]["can_generate_preflight_now"] is False

    review = service.create_import_queue_review(source_dir=str(pack), limit=10, reviewed_by="tester")
    imported = service.import_reviewed_to_staging(
        source_dir=str(pack),
        limit=10,
        review_event_id=review["event_id"],
        imported_by="tester",
    )
    quality = service.staging_quality_review(package_id=imported["package_id"], reviewed_by="tester")
    plan = service.staging_fix_plan(quality_review_id=quality["event_id"], planned_by="tester")
    approval = service.approve_staging_fix_plan(
        fix_plan_event_id=plan["event_id"],
        approved_by="tester",
        approval_decision="approved_for_preflight",
        note="metadata approval only",
    )
    preflight = service.staging_fix_preflight(
        approval_event_id=approval["event_id"],
        requested_by="tester",
        note="preflight only",
    )

    assert approval["stage"] == "V5.6-P17"
    assert approval["status"] == "fix_plan_approved_for_preflight"
    assert approval["decision"]["approval_allows_fix_application_now"] is False
    assert approval["decision"]["can_generate_preflight_now"] is True
    assert approval["decision"]["writes_learning_samples_now"] is False
    assert preflight["stage"] == "V5.6-P17"
    assert preflight["status"] == "fix_preflight_ready_for_manual_execution"
    assert preflight["summary"]["check_count"] >= 1
    assert preflight["summary"]["record_mutation_count"] == 0
    assert preflight["decision"]["fixes_applied_now"] is False
    assert preflight["decision"]["mutates_staging_records_now"] is False
    assert preflight["decision"]["writes_learning_samples_now"] is False
    assert preflight["decision"]["training_started_now"] is False
    assert any(check["name"] == "time_aware_split_policy" for check in preflight["preflight_checks"])

    approvals = service.list_staging_fix_plan_approvals(limit=5)
    preflights = service.list_staging_fix_preflights(limit=5)
    assert approvals[0]["id"] == approval["event_id"]
    assert preflights[0]["id"] == preflight["event_id"]


def test_dataset2_cleanup_execution_spec_is_review_only(tmp_path, test_db):
    pack = _write_dataset2_pack(
        tmp_path,
        [
            _record(pattern_id="EXEC_SPEC_001", risk_level="medium_high", split_tag="train"),
            _record(pattern_id="EXEC_SPEC_002", action_label="RISK_ALERT", risk_level="high", split_tag="train"),
        ],
    )
    service = Dataset2TrainingReadinessService()

    missing = service.staging_cleanup_execution_spec(preflight_event_id=999999, specified_by="tester")
    assert missing["status"] == "execution_spec_blocked_missing_preflight"
    assert missing["decision"]["writes_existing_event_now"] is False
    assert missing["decision"]["cleanup_executed_now"] is False

    review = service.create_import_queue_review(source_dir=str(pack), limit=10, reviewed_by="tester")
    imported = service.import_reviewed_to_staging(
        source_dir=str(pack),
        limit=10,
        review_event_id=review["event_id"],
        imported_by="tester",
    )
    quality = service.staging_quality_review(package_id=imported["package_id"], reviewed_by="tester")
    plan = service.staging_fix_plan(quality_review_id=quality["event_id"], planned_by="tester")
    approval = service.approve_staging_fix_plan(
        fix_plan_event_id=plan["event_id"],
        approved_by="tester",
        approval_decision="approved_for_preflight",
    )
    preflight = service.staging_fix_preflight(approval_event_id=approval["event_id"], requested_by="tester")
    spec = service.staging_cleanup_execution_spec(
        preflight_event_id=preflight["event_id"],
        specified_by="tester",
        note="spec only",
    )

    assert spec["stage"] == "V5.6-P17"
    assert spec["status"] == "cleanup_execution_spec_ready_for_review"
    assert isinstance(spec["event_id"], int)
    assert spec["preflight_event_id"] == preflight["event_id"]
    assert spec["summary"]["step_count"] >= 1
    assert spec["summary"]["record_body_count"] == 0
    assert spec["spec"]["can_execute_now"] is False
    assert spec["spec"]["contains_executable_code"] is False
    assert spec["spec"]["sql_included"] is False
    assert spec["spec"]["record_bodies_included"] is False
    assert spec["decision"]["execution_spec_can_be_applied_now"] is False
    assert spec["decision"]["cleanup_executed_now"] is False
    assert spec["decision"]["mutates_staging_records_now"] is False
    assert spec["decision"]["writes_learning_samples_now"] is False
    assert spec["decision"]["training_started_now"] is False
    assert any(step["name"] == "deterministic_split_assignment_spec" for step in spec["execution_steps"])
    assert all("write_learning_samples" in step["forbidden_actions"] for step in spec["execution_steps"])

    specs = service.list_staging_cleanup_execution_specs(limit=5)
    assert specs[0]["id"] == spec["event_id"]
    assert specs[0]["review"]["specified_by"] == "tester"


def test_dataset2_cleanup_dry_run_verification_blocks_application_without_mutation(tmp_path, test_db):
    pack = _write_dataset2_pack(
        tmp_path,
        [
            _record(pattern_id="DRY_RUN_001", risk_level="medium_high", split_tag="train"),
            _record(pattern_id="DRY_RUN_002", action_label="RISK_ALERT", risk_level="high", split_tag="train"),
        ],
    )
    service = Dataset2TrainingReadinessService()

    missing = service.staging_cleanup_dry_run_verification(execution_spec_event_id=999999, verified_by="tester")
    assert missing["status"] == "dry_run_blocked_missing_execution_spec"
    assert missing["decision"]["writes_existing_event_now"] is False
    assert missing["decision"]["cleanup_application_allowed_now"] is False

    review = service.create_import_queue_review(source_dir=str(pack), limit=10, reviewed_by="tester")
    imported = service.import_reviewed_to_staging(
        source_dir=str(pack),
        limit=10,
        review_event_id=review["event_id"],
        imported_by="tester",
    )
    quality = service.staging_quality_review(package_id=imported["package_id"], reviewed_by="tester")
    plan = service.staging_fix_plan(quality_review_id=quality["event_id"], planned_by="tester")
    approval = service.approve_staging_fix_plan(
        fix_plan_event_id=plan["event_id"],
        approved_by="tester",
        approval_decision="approved_for_preflight",
    )
    preflight = service.staging_fix_preflight(approval_event_id=approval["event_id"], requested_by="tester")
    spec = service.staging_cleanup_execution_spec(preflight_event_id=preflight["event_id"], specified_by="tester")
    dry_run = service.staging_cleanup_dry_run_verification(
        execution_spec_event_id=spec["event_id"],
        verified_by="tester",
        note="verify only",
    )

    assert dry_run["stage"] == "V5.6-P17"
    assert dry_run["status"] == "dry_run_blocked_manual_evidence_required"
    assert isinstance(dry_run["event_id"], int)
    assert dry_run["execution_spec_event_id"] == spec["event_id"]
    assert dry_run["summary"]["check_count"] >= 1
    assert dry_run["summary"]["blocked_check_count"] >= 1
    assert dry_run["summary"]["execution_step_count"] == spec["summary"]["step_count"]
    check_status = {check["name"]: check["status"] for check in dry_run["checks"]}
    assert check_status["spec_non_executable"] == "passed"
    assert check_status["record_bodies_excluded"] == "passed"
    assert check_status["no_mutation_allowed"] == "passed"
    assert check_status["blocked_source_checks_resolved"] == "blocked"
    assert dry_run["decision"]["dry_run_executed_now"] is True
    assert dry_run["decision"]["cleanup_executed_now"] is False
    assert dry_run["decision"]["cleanup_application_allowed_now"] is False
    assert dry_run["decision"]["mutates_staging_records_now"] is False
    assert dry_run["decision"]["writes_learning_samples_now"] is False
    assert dry_run["decision"]["training_started_now"] is False

    dry_runs = service.list_staging_cleanup_dry_run_verifications(limit=5)
    assert dry_runs[0]["id"] == dry_run["event_id"]
    assert dry_runs[0]["verification"]["verified_by"] == "tester"


def test_dataset2_manual_evidence_verification_summarizes_package_without_record_bodies(tmp_path, test_db):
    pack = _write_dataset2_pack(
        tmp_path,
        [
            _record(pattern_id="MANUAL_EVIDENCE_001", risk_level="medium_high", split_tag="train"),
            _record(pattern_id="MANUAL_EVIDENCE_002", action_label="RISK_ALERT", risk_level="high", split_tag="train"),
        ],
    )
    service = Dataset2TrainingReadinessService()

    missing = service.staging_cleanup_manual_evidence_verification(dry_run_verification_id=999999, verified_by="tester")
    assert missing["status"] == "manual_evidence_blocked_missing_dry_run"
    assert missing["decision"]["writes_existing_event_now"] is False
    assert missing["decision"]["cleanup_application_allowed_now"] is False

    review = service.create_import_queue_review(source_dir=str(pack), limit=10, reviewed_by="tester")
    imported = service.import_reviewed_to_staging(
        source_dir=str(pack),
        limit=10,
        review_event_id=review["event_id"],
        imported_by="tester",
    )
    quality = service.staging_quality_review(package_id=imported["package_id"], reviewed_by="tester")
    plan = service.staging_fix_plan(quality_review_id=quality["event_id"], planned_by="tester")
    approval = service.approve_staging_fix_plan(
        fix_plan_event_id=plan["event_id"],
        approved_by="tester",
        approval_decision="approved_for_preflight",
    )
    preflight = service.staging_fix_preflight(approval_event_id=approval["event_id"], requested_by="tester")
    spec = service.staging_cleanup_execution_spec(preflight_event_id=preflight["event_id"], specified_by="tester")
    dry_run = service.staging_cleanup_dry_run_verification(execution_spec_event_id=spec["event_id"], verified_by="tester")

    blocked = service.staging_cleanup_manual_evidence_verification(
        dry_run_verification_id=dry_run["event_id"],
        evidence_package={},
        verified_by="tester",
    )
    assert blocked["status"] == "manual_evidence_blocked"
    assert blocked["decision"]["manual_evidence_accepted_for_review"] is False

    verified = service.staging_cleanup_manual_evidence_verification(
        dry_run_verification_id=dry_run["event_id"],
        evidence_package=_manual_evidence_package(),
        verified_by="tester",
        note="evidence summary only",
    )

    assert verified["stage"] == "V5.6-P17"
    assert verified["status"] == "manual_evidence_package_verified_for_cleanup_review"
    assert isinstance(verified["event_id"], int)
    assert verified["dry_run_verification_id"] == dry_run["event_id"]
    assert verified["summary"]["blocked_check_count"] == 0
    assert verified["summary"]["record_bodies_included"] is False
    assert verified["evidence_summary"]["evidence_package_hash"]
    assert verified["evidence_summary"]["evidence_package_body_included"] is False
    assert "historical_outcome_source" in verified["evidence_summary"]["provided_sections"]
    assert "historical_outcome_source" not in verified
    assert verified["decision"]["manual_evidence_accepted_for_review"] is True
    assert verified["decision"]["cleanup_application_allowed_now"] is False
    assert verified["decision"]["cleanup_executed_now"] is False
    assert verified["decision"]["mutates_staging_records_now"] is False
    assert verified["decision"]["writes_learning_samples_now"] is False
    assert verified["decision"]["training_started_now"] is False
    check_status = {check["name"]: check["status"] for check in verified["checks"]}
    assert check_status["record_bodies_excluded"] == "passed"
    assert check_status["execution_requests_excluded"] == "passed"

    verifications = service.list_staging_cleanup_manual_evidence_verifications(limit=5)
    assert verifications[0]["id"] == verified["event_id"]
    assert verifications[0]["verification"]["verified_by"] == "tester"
    assert "evidence_package" not in verifications[0]


def test_dataset2_manual_evidence_acceptance_review_records_metadata_only(tmp_path, test_db):
    pack = _write_dataset2_pack(
        tmp_path,
        [
            _record(pattern_id="MANUAL_ACCEPT_001", risk_level="medium_high", split_tag="train"),
            _record(pattern_id="MANUAL_ACCEPT_002", action_label="RISK_ALERT", risk_level="high", split_tag="train"),
        ],
    )
    service = Dataset2TrainingReadinessService()

    missing = service.staging_cleanup_manual_evidence_acceptance_review(
        manual_evidence_verification_id=999999,
        accepted_by="tester",
    )
    assert missing["status"] == "manual_evidence_acceptance_blocked_missing_verification"
    assert missing["decision"]["writes_existing_event_now"] is False
    assert missing["decision"]["cleanup_application_allowed_now"] is False

    review = service.create_import_queue_review(source_dir=str(pack), limit=10, reviewed_by="tester")
    imported = service.import_reviewed_to_staging(
        source_dir=str(pack),
        limit=10,
        review_event_id=review["event_id"],
        imported_by="tester",
    )
    quality = service.staging_quality_review(package_id=imported["package_id"], reviewed_by="tester")
    plan = service.staging_fix_plan(quality_review_id=quality["event_id"], planned_by="tester")
    approval = service.approve_staging_fix_plan(
        fix_plan_event_id=plan["event_id"],
        approved_by="tester",
        approval_decision="approved_for_preflight",
    )
    preflight = service.staging_fix_preflight(approval_event_id=approval["event_id"], requested_by="tester")
    spec = service.staging_cleanup_execution_spec(preflight_event_id=preflight["event_id"], specified_by="tester")
    dry_run = service.staging_cleanup_dry_run_verification(execution_spec_event_id=spec["event_id"], verified_by="tester")

    blocked_manual = service.staging_cleanup_manual_evidence_verification(
        dry_run_verification_id=dry_run["event_id"],
        evidence_package={},
        verified_by="tester",
    )
    blocked_acceptance = service.staging_cleanup_manual_evidence_acceptance_review(
        manual_evidence_verification_id=blocked_manual["event_id"],
        accepted_by="tester",
    )
    assert blocked_acceptance["status"] == "manual_evidence_acceptance_blocked"
    assert blocked_acceptance["decision"]["manual_evidence_ready_for_cleanup_application_review"] is False
    assert blocked_acceptance["decision"]["cleanup_executed_now"] is False

    verified = service.staging_cleanup_manual_evidence_verification(
        dry_run_verification_id=dry_run["event_id"],
        evidence_package=_manual_evidence_package(),
        verified_by="tester",
        note="evidence summary only",
    )
    accepted = service.staging_cleanup_manual_evidence_acceptance_review(
        manual_evidence_verification_id=verified["event_id"],
        accepted_by="tester",
        acceptance_decision="accepted_for_cleanup_review",
        note="metadata-only acceptance for next review gate",
    )

    assert accepted["stage"] == "V5.6-P17"
    assert accepted["status"] == "manual_evidence_accepted_for_cleanup_review"
    assert isinstance(accepted["event_id"], int)
    assert accepted["manual_evidence_verification_id"] == verified["event_id"]
    assert accepted["evidence_summary"]["evidence_package_hash"] == verified["evidence_summary"]["evidence_package_hash"]
    assert accepted["evidence_summary"]["evidence_package_body_included"] is False
    assert accepted["source_manual_evidence_summary"]["blocked_check_count"] == 0
    assert accepted["decision"]["manual_evidence_acceptance_recorded"] is True
    assert accepted["decision"]["manual_evidence_ready_for_cleanup_application_review"] is True
    assert accepted["decision"]["cleanup_application_allowed_now"] is False
    assert accepted["decision"]["cleanup_executed_now"] is False
    assert accepted["decision"]["mutates_staging_records_now"] is False
    assert accepted["decision"]["writes_learning_samples_now"] is False
    assert accepted["decision"]["training_started_now"] is False
    assert accepted["decision"]["can_start_training_now"] is False
    assert "historical_outcome_source" not in accepted
    check_status = {check["name"]: check["status"] for check in accepted["checks"]}
    assert check_status["manual_evidence_package_verified"] == "passed"
    assert check_status["cleanup_and_training_remain_blocked"] == "passed"

    reviews = service.list_staging_cleanup_manual_evidence_acceptance_reviews(limit=5)
    assert reviews[0]["id"] == accepted["event_id"]
    assert reviews[0]["acceptance"]["accepted_by"] == "tester"
    assert "evidence_package" not in reviews[0]


def test_dataset2_cleanup_application_review_keeps_execution_blocked(tmp_path, test_db):
    pack = _write_dataset2_pack(
        tmp_path,
        [
            _record(pattern_id="CLEANUP_APP_001", risk_level="medium_high", split_tag="train"),
            _record(pattern_id="CLEANUP_APP_002", action_label="RISK_ALERT", risk_level="high", split_tag="train"),
        ],
    )
    service = Dataset2TrainingReadinessService()

    missing = service.staging_cleanup_application_review(acceptance_review_id=999999, reviewed_by="tester")
    assert missing["status"] == "cleanup_application_review_blocked_missing_acceptance"
    assert missing["decision"]["writes_existing_event_now"] is False
    assert missing["decision"]["cleanup_application_allowed_now"] is False

    review = service.create_import_queue_review(source_dir=str(pack), limit=10, reviewed_by="tester")
    imported = service.import_reviewed_to_staging(
        source_dir=str(pack),
        limit=10,
        review_event_id=review["event_id"],
        imported_by="tester",
    )
    quality = service.staging_quality_review(package_id=imported["package_id"], reviewed_by="tester")
    plan = service.staging_fix_plan(quality_review_id=quality["event_id"], planned_by="tester")
    approval = service.approve_staging_fix_plan(
        fix_plan_event_id=plan["event_id"],
        approved_by="tester",
        approval_decision="approved_for_preflight",
    )
    preflight = service.staging_fix_preflight(approval_event_id=approval["event_id"], requested_by="tester")
    spec = service.staging_cleanup_execution_spec(preflight_event_id=preflight["event_id"], specified_by="tester")
    dry_run = service.staging_cleanup_dry_run_verification(execution_spec_event_id=spec["event_id"], verified_by="tester")

    blocked_manual = service.staging_cleanup_manual_evidence_verification(
        dry_run_verification_id=dry_run["event_id"],
        evidence_package={},
        verified_by="tester",
    )
    blocked_acceptance = service.staging_cleanup_manual_evidence_acceptance_review(
        manual_evidence_verification_id=blocked_manual["event_id"],
        accepted_by="tester",
    )
    blocked_application = service.staging_cleanup_application_review(
        acceptance_review_id=blocked_acceptance["event_id"],
        reviewed_by="tester",
    )
    assert blocked_application["status"] == "cleanup_application_review_blocked"
    assert blocked_application["decision"]["cleanup_application_ready_for_future_plan"] is False
    assert blocked_application["decision"]["cleanup_executed_now"] is False

    verified = service.staging_cleanup_manual_evidence_verification(
        dry_run_verification_id=dry_run["event_id"],
        evidence_package=_manual_evidence_package(),
        verified_by="tester",
        note="evidence summary only",
    )
    accepted = service.staging_cleanup_manual_evidence_acceptance_review(
        manual_evidence_verification_id=verified["event_id"],
        accepted_by="tester",
        acceptance_decision="accepted_for_cleanup_review",
    )
    application = service.staging_cleanup_application_review(
        acceptance_review_id=accepted["event_id"],
        reviewed_by="tester",
        review_decision="ready_for_future_cleanup_application",
        note="metadata-only application gate",
    )

    assert application["stage"] == "V5.6-P17"
    assert application["status"] == "cleanup_application_review_ready"
    assert isinstance(application["event_id"], int)
    assert application["acceptance_review_id"] == accepted["event_id"]
    assert application["manual_evidence_verification_id"] == verified["event_id"]
    assert application["evidence_summary"]["evidence_package_hash"] == verified["evidence_summary"]["evidence_package_hash"]
    assert application["evidence_summary"]["evidence_package_body_included"] is False
    assert application["source_acceptance_summary"]["blocked_check_count"] == 0
    assert application["decision"]["cleanup_application_review_recorded"] is True
    assert application["decision"]["cleanup_application_ready_for_future_plan"] is True
    assert application["decision"]["cleanup_application_allowed_now"] is False
    assert application["decision"]["cleanup_executed_now"] is False
    assert application["decision"]["mutates_staging_records_now"] is False
    assert application["decision"]["writes_staging_records_now"] is False
    assert application["decision"]["writes_learning_samples_now"] is False
    assert application["decision"]["training_started_now"] is False
    assert application["decision"]["can_start_training_now"] is False
    assert application["decision"]["future_cleanup_execution_requires_separate_approval"] is True
    assert "evidence_package" not in application
    assert "historical_outcome_source" not in application
    check_status = {check["name"]: check["status"] for check in application["checks"]}
    assert check_status["acceptance_ready_for_cleanup_review"] == "passed"
    assert check_status["cleanup_and_training_remain_blocked"] == "passed"

    reviews = service.list_staging_cleanup_application_reviews(limit=5)
    assert reviews[0]["id"] == application["event_id"]
    assert reviews[0]["review"]["reviewed_by"] == "tester"
    assert "evidence_package" not in reviews[0]


def test_dataset2_cleanup_execution_approval_plan_is_metadata_only(tmp_path, test_db):
    pack = _write_dataset2_pack(
        tmp_path,
        [
            _record(pattern_id="CLEANUP_APPROVAL_001", risk_level="medium_high", split_tag="train"),
            _record(pattern_id="CLEANUP_APPROVAL_002", action_label="RISK_ALERT", risk_level="high", split_tag="train"),
        ],
    )
    service = Dataset2TrainingReadinessService()

    missing = service.staging_cleanup_execution_approval_plan(
        cleanup_application_review_id=999999,
        planned_by="tester",
    )
    assert missing["status"] == "cleanup_execution_approval_plan_blocked_missing_application_review"
    assert missing["decision"]["writes_existing_event_now"] is False
    assert missing["decision"]["cleanup_execution_approved_now"] is False
    assert missing["decision"]["cleanup_executed_now"] is False

    review = service.create_import_queue_review(source_dir=str(pack), limit=10, reviewed_by="tester")
    imported = service.import_reviewed_to_staging(
        source_dir=str(pack),
        limit=10,
        review_event_id=review["event_id"],
        imported_by="tester",
    )
    quality = service.staging_quality_review(package_id=imported["package_id"], reviewed_by="tester")
    plan = service.staging_fix_plan(quality_review_id=quality["event_id"], planned_by="tester")
    approval = service.approve_staging_fix_plan(
        fix_plan_event_id=plan["event_id"],
        approved_by="tester",
        approval_decision="approved_for_preflight",
    )
    preflight = service.staging_fix_preflight(approval_event_id=approval["event_id"], requested_by="tester")
    spec = service.staging_cleanup_execution_spec(preflight_event_id=preflight["event_id"], specified_by="tester")
    dry_run = service.staging_cleanup_dry_run_verification(execution_spec_event_id=spec["event_id"], verified_by="tester")

    blocked_manual = service.staging_cleanup_manual_evidence_verification(
        dry_run_verification_id=dry_run["event_id"],
        evidence_package={},
        verified_by="tester",
    )
    blocked_acceptance = service.staging_cleanup_manual_evidence_acceptance_review(
        manual_evidence_verification_id=blocked_manual["event_id"],
        accepted_by="tester",
    )
    blocked_application = service.staging_cleanup_application_review(
        acceptance_review_id=blocked_acceptance["event_id"],
        reviewed_by="tester",
    )
    blocked_plan = service.staging_cleanup_execution_approval_plan(
        cleanup_application_review_id=blocked_application["event_id"],
        planned_by="tester",
    )
    assert blocked_plan["status"] == "cleanup_execution_approval_plan_blocked"
    assert blocked_plan["decision"]["cleanup_execution_plan_ready_for_manual_approval"] is False
    assert blocked_plan["decision"]["cleanup_execution_approved_now"] is False

    verified = service.staging_cleanup_manual_evidence_verification(
        dry_run_verification_id=dry_run["event_id"],
        evidence_package=_manual_evidence_package(),
        verified_by="tester",
    )
    accepted = service.staging_cleanup_manual_evidence_acceptance_review(
        manual_evidence_verification_id=verified["event_id"],
        accepted_by="tester",
        acceptance_decision="accepted_for_cleanup_review",
    )
    application = service.staging_cleanup_application_review(
        acceptance_review_id=accepted["event_id"],
        reviewed_by="tester",
        review_decision="ready_for_future_cleanup_application",
    )
    approval_plan = service.staging_cleanup_execution_approval_plan(
        cleanup_application_review_id=application["event_id"],
        planned_by="tester",
        plan_decision="prepared_for_manual_approval",
        note="approval plan only",
    )

    assert approval_plan["stage"] == "V5.6-P17"
    assert approval_plan["status"] == "cleanup_execution_approval_plan_ready"
    assert isinstance(approval_plan["event_id"], int)
    assert approval_plan["cleanup_application_review_id"] == application["event_id"]
    assert approval_plan["acceptance_review_id"] == accepted["event_id"]
    assert approval_plan["manual_evidence_verification_id"] == verified["event_id"]
    assert approval_plan["evidence_summary"]["evidence_package_hash"] == verified["evidence_summary"]["evidence_package_hash"]
    assert approval_plan["approval_plan"]["step_count"] >= 5
    assert approval_plan["approval_plan"]["contains_sql"] is False
    assert approval_plan["approval_plan"]["contains_executable_code"] is False
    assert approval_plan["approval_plan"]["can_execute_now"] is False
    assert approval_plan["approval_plan"]["requires_manual_execution_approval"] is True
    assert approval_plan["decision"]["cleanup_execution_approval_plan_recorded"] is True
    assert approval_plan["decision"]["cleanup_execution_plan_ready_for_manual_approval"] is True
    assert approval_plan["decision"]["cleanup_execution_approved_now"] is False
    assert approval_plan["decision"]["cleanup_application_allowed_now"] is False
    assert approval_plan["decision"]["cleanup_executed_now"] is False
    assert approval_plan["decision"]["mutates_staging_records_now"] is False
    assert approval_plan["decision"]["writes_staging_records_now"] is False
    assert approval_plan["decision"]["writes_learning_samples_now"] is False
    assert approval_plan["decision"]["training_started_now"] is False
    assert approval_plan["decision"]["can_start_training_now"] is False
    assert "evidence_package" not in approval_plan
    assert "historical_outcome_source" not in approval_plan
    check_status = {check["name"]: check["status"] for check in approval_plan["checks"]}
    assert check_status["cleanup_application_review_ready"] == "passed"
    assert check_status["plan_contains_no_executable_payload"] == "passed"
    assert check_status["cleanup_and_training_remain_blocked"] == "passed"

    plans = service.list_staging_cleanup_execution_approval_plans(limit=5)
    assert plans[0]["id"] == approval_plan["event_id"]
    assert plans[0]["planning"]["planned_by"] == "tester"
    assert "evidence_package" not in plans[0]


def test_dataset2_cleanup_execution_manual_approval_is_metadata_only(tmp_path, test_db):
    pack = _write_dataset2_pack(
        tmp_path,
        [
            _record(pattern_id="MANUAL_APPROVAL_001", risk_level="medium_high", split_tag="train"),
            _record(pattern_id="MANUAL_APPROVAL_002", action_label="RISK_ALERT", risk_level="high", split_tag="train"),
        ],
    )
    service = Dataset2TrainingReadinessService()

    missing = service.staging_cleanup_execution_manual_approval(
        approval_plan_id=999999,
        approved_by="tester",
    )
    assert missing["status"] == "cleanup_execution_manual_approval_blocked_missing_approval_plan"
    assert missing["decision"]["writes_existing_event_now"] is False
    assert missing["decision"]["cleanup_execution_approval_metadata_accepted"] is False
    assert missing["decision"]["cleanup_executed_now"] is False

    review = service.create_import_queue_review(source_dir=str(pack), limit=10, reviewed_by="tester")
    imported = service.import_reviewed_to_staging(
        source_dir=str(pack),
        limit=10,
        review_event_id=review["event_id"],
        imported_by="tester",
    )
    quality = service.staging_quality_review(package_id=imported["package_id"], reviewed_by="tester")
    plan = service.staging_fix_plan(quality_review_id=quality["event_id"], planned_by="tester")
    approval = service.approve_staging_fix_plan(
        fix_plan_event_id=plan["event_id"],
        approved_by="tester",
        approval_decision="approved_for_preflight",
    )
    preflight = service.staging_fix_preflight(approval_event_id=approval["event_id"], requested_by="tester")
    spec = service.staging_cleanup_execution_spec(preflight_event_id=preflight["event_id"], specified_by="tester")
    dry_run = service.staging_cleanup_dry_run_verification(execution_spec_event_id=spec["event_id"], verified_by="tester")

    blocked_manual = service.staging_cleanup_manual_evidence_verification(
        dry_run_verification_id=dry_run["event_id"],
        evidence_package={},
        verified_by="tester",
    )
    blocked_acceptance = service.staging_cleanup_manual_evidence_acceptance_review(
        manual_evidence_verification_id=blocked_manual["event_id"],
        accepted_by="tester",
    )
    blocked_application = service.staging_cleanup_application_review(
        acceptance_review_id=blocked_acceptance["event_id"],
        reviewed_by="tester",
    )
    blocked_plan = service.staging_cleanup_execution_approval_plan(
        cleanup_application_review_id=blocked_application["event_id"],
        planned_by="tester",
    )
    blocked_approval = service.staging_cleanup_execution_manual_approval(
        approval_plan_id=blocked_plan["event_id"],
        approved_by="tester",
    )
    assert blocked_approval["status"] == "cleanup_execution_manual_approval_blocked"
    assert blocked_approval["decision"]["cleanup_execution_approval_metadata_accepted"] is False
    assert blocked_approval["decision"]["can_generate_cleanup_execution_preflight_now"] is False

    verified = service.staging_cleanup_manual_evidence_verification(
        dry_run_verification_id=dry_run["event_id"],
        evidence_package=_manual_evidence_package(),
        verified_by="tester",
    )
    accepted = service.staging_cleanup_manual_evidence_acceptance_review(
        manual_evidence_verification_id=verified["event_id"],
        accepted_by="tester",
        acceptance_decision="accepted_for_cleanup_review",
    )
    application = service.staging_cleanup_application_review(
        acceptance_review_id=accepted["event_id"],
        reviewed_by="tester",
        review_decision="ready_for_future_cleanup_application",
    )
    approval_plan = service.staging_cleanup_execution_approval_plan(
        cleanup_application_review_id=application["event_id"],
        planned_by="tester",
        plan_decision="prepared_for_manual_approval",
    )
    manual_approval = service.staging_cleanup_execution_manual_approval(
        approval_plan_id=approval_plan["event_id"],
        approved_by="tester",
        approval_decision="approved_for_cleanup_execution_preflight",
        note="metadata approval only",
    )

    assert manual_approval["stage"] == "V5.6-P17"
    assert manual_approval["status"] == "cleanup_execution_manual_approval_ready_for_preflight"
    assert isinstance(manual_approval["event_id"], int)
    assert manual_approval["approval_plan_id"] == approval_plan["event_id"]
    assert manual_approval["cleanup_application_review_id"] == application["event_id"]
    assert manual_approval["manual_evidence_verification_id"] == verified["event_id"]
    assert manual_approval["evidence_summary"]["evidence_package_hash"] == verified["evidence_summary"]["evidence_package_hash"]
    assert manual_approval["source_approval_plan"]["step_count"] >= 5
    assert manual_approval["source_approval_plan"]["contains_sql"] is False
    assert manual_approval["source_approval_plan"]["contains_executable_code"] is False
    assert manual_approval["source_approval_plan"]["can_execute_now"] is False
    assert manual_approval["manual_approval"]["approved_by"] == "tester"
    assert manual_approval["decision"]["cleanup_execution_manual_approval_recorded"] is True
    assert manual_approval["decision"]["cleanup_execution_approval_metadata_accepted"] is True
    assert manual_approval["decision"]["cleanup_execution_approved_for_future_preflight"] is True
    assert manual_approval["decision"]["cleanup_execution_approved_now"] is False
    assert manual_approval["decision"]["cleanup_application_allowed_now"] is False
    assert manual_approval["decision"]["cleanup_executed_now"] is False
    assert manual_approval["decision"]["can_execute_cleanup_now"] is False
    assert manual_approval["decision"]["mutates_staging_records_now"] is False
    assert manual_approval["decision"]["writes_staging_records_now"] is False
    assert manual_approval["decision"]["writes_learning_samples_now"] is False
    assert manual_approval["decision"]["training_started_now"] is False
    assert manual_approval["decision"]["can_start_training_now"] is False
    assert "evidence_package" not in manual_approval
    assert "historical_outcome_source" not in manual_approval
    check_status = {check["name"]: check["status"] for check in manual_approval["checks"]}
    assert check_status["approval_plan_ready_for_manual_approval"] == "passed"
    assert check_status["source_plan_contains_no_executable_payload"] == "passed"
    assert check_status["cleanup_and_training_remain_blocked"] == "passed"

    approvals = service.list_staging_cleanup_execution_manual_approvals(limit=5)
    assert approvals[0]["id"] == manual_approval["event_id"]
    assert approvals[0]["manual_approval"]["approved_by"] == "tester"
    assert "evidence_package" not in approvals[0]


def test_dataset2_cleanup_execution_preflight_is_metadata_only(tmp_path, test_db):
    pack = _write_dataset2_pack(
        tmp_path,
        [
            _record(pattern_id="EXECUTION_PREFLIGHT_001", risk_level="medium_high", split_tag="train"),
            _record(pattern_id="EXECUTION_PREFLIGHT_002", action_label="RISK_ALERT", risk_level="high", split_tag="train"),
        ],
    )
    service = Dataset2TrainingReadinessService()

    missing = service.staging_cleanup_execution_preflight(
        manual_approval_id=999999,
        requested_by="tester",
    )
    assert missing["status"] == "cleanup_execution_preflight_blocked_missing_manual_approval"
    assert missing["decision"]["writes_existing_event_now"] is False
    assert missing["decision"]["cleanup_execution_preflight_ready_for_dry_run"] is False
    assert missing["decision"]["cleanup_executed_now"] is False

    review = service.create_import_queue_review(source_dir=str(pack), limit=10, reviewed_by="tester")
    imported = service.import_reviewed_to_staging(
        source_dir=str(pack),
        limit=10,
        review_event_id=review["event_id"],
        imported_by="tester",
    )
    quality = service.staging_quality_review(package_id=imported["package_id"], reviewed_by="tester")
    plan = service.staging_fix_plan(quality_review_id=quality["event_id"], planned_by="tester")
    approval = service.approve_staging_fix_plan(
        fix_plan_event_id=plan["event_id"],
        approved_by="tester",
        approval_decision="approved_for_preflight",
    )
    fix_preflight = service.staging_fix_preflight(approval_event_id=approval["event_id"], requested_by="tester")
    spec = service.staging_cleanup_execution_spec(preflight_event_id=fix_preflight["event_id"], specified_by="tester")
    dry_run = service.staging_cleanup_dry_run_verification(execution_spec_event_id=spec["event_id"], verified_by="tester")

    blocked_manual = service.staging_cleanup_manual_evidence_verification(
        dry_run_verification_id=dry_run["event_id"],
        evidence_package={},
        verified_by="tester",
    )
    blocked_acceptance = service.staging_cleanup_manual_evidence_acceptance_review(
        manual_evidence_verification_id=blocked_manual["event_id"],
        accepted_by="tester",
    )
    blocked_application = service.staging_cleanup_application_review(
        acceptance_review_id=blocked_acceptance["event_id"],
        reviewed_by="tester",
    )
    blocked_plan = service.staging_cleanup_execution_approval_plan(
        cleanup_application_review_id=blocked_application["event_id"],
        planned_by="tester",
    )
    blocked_approval = service.staging_cleanup_execution_manual_approval(
        approval_plan_id=blocked_plan["event_id"],
        approved_by="tester",
    )
    blocked_preflight = service.staging_cleanup_execution_preflight(
        manual_approval_id=blocked_approval["event_id"],
        requested_by="tester",
    )
    assert blocked_preflight["status"] == "cleanup_execution_preflight_blocked"
    assert blocked_preflight["decision"]["cleanup_execution_preflight_ready_for_dry_run"] is False
    assert blocked_preflight["decision"]["can_execute_cleanup_now"] is False

    verified = service.staging_cleanup_manual_evidence_verification(
        dry_run_verification_id=dry_run["event_id"],
        evidence_package=_manual_evidence_package(),
        verified_by="tester",
    )
    accepted = service.staging_cleanup_manual_evidence_acceptance_review(
        manual_evidence_verification_id=verified["event_id"],
        accepted_by="tester",
        acceptance_decision="accepted_for_cleanup_review",
    )
    application = service.staging_cleanup_application_review(
        acceptance_review_id=accepted["event_id"],
        reviewed_by="tester",
        review_decision="ready_for_future_cleanup_application",
    )
    approval_plan = service.staging_cleanup_execution_approval_plan(
        cleanup_application_review_id=application["event_id"],
        planned_by="tester",
        plan_decision="prepared_for_manual_approval",
    )
    manual_approval = service.staging_cleanup_execution_manual_approval(
        approval_plan_id=approval_plan["event_id"],
        approved_by="tester",
        approval_decision="approved_for_cleanup_execution_preflight",
    )
    cleanup_preflight = service.staging_cleanup_execution_preflight(
        manual_approval_id=manual_approval["event_id"],
        requested_by="tester",
        preflight_decision="prepared_for_cleanup_execution_dry_run",
        note="preflight metadata only",
    )

    assert cleanup_preflight["stage"] == "V5.6-P17"
    assert cleanup_preflight["status"] == "cleanup_execution_preflight_ready_for_dry_run"
    assert isinstance(cleanup_preflight["event_id"], int)
    assert cleanup_preflight["manual_approval_id"] == manual_approval["event_id"]
    assert cleanup_preflight["approval_plan_id"] == approval_plan["event_id"]
    assert cleanup_preflight["evidence_summary"]["evidence_package_hash"] == verified["evidence_summary"]["evidence_package_hash"]
    assert cleanup_preflight["preflight"]["lock_key"].startswith("dataset2-cleanup-preflight-")
    assert cleanup_preflight["preflight"]["rollback_plan"]["required"] is True
    assert cleanup_preflight["preflight"]["rollback_plan"]["verified_now"] is False
    assert cleanup_preflight["preflight"]["contains_sql"] is False
    assert cleanup_preflight["preflight"]["contains_executable_code"] is False
    assert cleanup_preflight["preflight"]["can_execute_now"] is False
    assert cleanup_preflight["summary"]["staging_record_count"] == 2
    assert cleanup_preflight["summary"]["learning_sample_count"] == 0
    assert cleanup_preflight["decision"]["cleanup_execution_preflight_recorded"] is True
    assert cleanup_preflight["decision"]["cleanup_execution_preflight_ready_for_dry_run"] is True
    assert cleanup_preflight["decision"]["cleanup_execution_approved_now"] is False
    assert cleanup_preflight["decision"]["cleanup_application_allowed_now"] is False
    assert cleanup_preflight["decision"]["cleanup_executed_now"] is False
    assert cleanup_preflight["decision"]["can_execute_cleanup_now"] is False
    assert cleanup_preflight["decision"]["mutates_staging_records_now"] is False
    assert cleanup_preflight["decision"]["writes_staging_records_now"] is False
    assert cleanup_preflight["decision"]["writes_learning_samples_now"] is False
    assert cleanup_preflight["decision"]["training_started_now"] is False
    assert cleanup_preflight["decision"]["can_start_training_now"] is False
    assert "evidence_package" not in cleanup_preflight
    assert "historical_outcome_source" not in cleanup_preflight
    check_status = {check["name"]: check["status"] for check in cleanup_preflight["checks"]}
    assert check_status["manual_approval_ready_for_preflight"] == "passed"
    assert check_status["preflight_contains_no_executable_payload"] == "passed"
    assert check_status["cleanup_and_training_remain_blocked"] == "passed"

    preflights = service.list_staging_cleanup_execution_preflights(limit=5)
    assert preflights[0]["id"] == cleanup_preflight["event_id"]
    assert preflights[0]["request"]["requested_by"] == "tester"
    assert "evidence_package" not in preflights[0]


def test_dataset2_cleanup_execution_dry_run_is_aggregate_only(tmp_path, test_db):
    pack = _write_dataset2_pack(
        tmp_path,
        [
            _record(pattern_id="EXECUTION_DRY_RUN_001", risk_level="medium_high", split_tag="train"),
            _record(pattern_id="EXECUTION_DRY_RUN_002", action_label="RISK_ALERT", risk_level="high", split_tag="train"),
        ],
    )
    service = Dataset2TrainingReadinessService()

    missing = service.staging_cleanup_execution_dry_run(
        preflight_id=999999,
        simulated_by="tester",
    )
    assert missing["status"] == "cleanup_execution_dry_run_blocked_missing_preflight"
    assert missing["decision"]["writes_existing_event_now"] is False
    assert missing["decision"]["cleanup_execution_dry_run_ready_for_review"] is False
    assert missing["decision"]["cleanup_executed_now"] is False

    review = service.create_import_queue_review(source_dir=str(pack), limit=10, reviewed_by="tester")
    imported = service.import_reviewed_to_staging(
        source_dir=str(pack),
        limit=10,
        review_event_id=review["event_id"],
        imported_by="tester",
    )
    quality = service.staging_quality_review(package_id=imported["package_id"], reviewed_by="tester")
    plan = service.staging_fix_plan(quality_review_id=quality["event_id"], planned_by="tester")
    approval = service.approve_staging_fix_plan(
        fix_plan_event_id=plan["event_id"],
        approved_by="tester",
        approval_decision="approved_for_preflight",
    )
    fix_preflight = service.staging_fix_preflight(approval_event_id=approval["event_id"], requested_by="tester")
    spec = service.staging_cleanup_execution_spec(preflight_event_id=fix_preflight["event_id"], specified_by="tester")
    dry_run = service.staging_cleanup_dry_run_verification(execution_spec_event_id=spec["event_id"], verified_by="tester")

    blocked_manual = service.staging_cleanup_manual_evidence_verification(
        dry_run_verification_id=dry_run["event_id"],
        evidence_package={},
        verified_by="tester",
    )
    blocked_acceptance = service.staging_cleanup_manual_evidence_acceptance_review(
        manual_evidence_verification_id=blocked_manual["event_id"],
        accepted_by="tester",
    )
    blocked_application = service.staging_cleanup_application_review(
        acceptance_review_id=blocked_acceptance["event_id"],
        reviewed_by="tester",
    )
    blocked_plan = service.staging_cleanup_execution_approval_plan(
        cleanup_application_review_id=blocked_application["event_id"],
        planned_by="tester",
    )
    blocked_approval = service.staging_cleanup_execution_manual_approval(
        approval_plan_id=blocked_plan["event_id"],
        approved_by="tester",
    )
    blocked_preflight = service.staging_cleanup_execution_preflight(
        manual_approval_id=blocked_approval["event_id"],
        requested_by="tester",
    )
    blocked_dry_run = service.staging_cleanup_execution_dry_run(
        preflight_id=blocked_preflight["event_id"],
        simulated_by="tester",
    )
    assert blocked_dry_run["status"] == "cleanup_execution_dry_run_blocked"
    assert blocked_dry_run["decision"]["cleanup_execution_dry_run_ready_for_review"] is False
    assert blocked_dry_run["decision"]["can_execute_cleanup_now"] is False

    verified = service.staging_cleanup_manual_evidence_verification(
        dry_run_verification_id=dry_run["event_id"],
        evidence_package=_manual_evidence_package(),
        verified_by="tester",
    )
    accepted = service.staging_cleanup_manual_evidence_acceptance_review(
        manual_evidence_verification_id=verified["event_id"],
        accepted_by="tester",
        acceptance_decision="accepted_for_cleanup_review",
    )
    application = service.staging_cleanup_application_review(
        acceptance_review_id=accepted["event_id"],
        reviewed_by="tester",
        review_decision="ready_for_future_cleanup_application",
    )
    approval_plan = service.staging_cleanup_execution_approval_plan(
        cleanup_application_review_id=application["event_id"],
        planned_by="tester",
        plan_decision="prepared_for_manual_approval",
    )
    manual_approval = service.staging_cleanup_execution_manual_approval(
        approval_plan_id=approval_plan["event_id"],
        approved_by="tester",
        approval_decision="approved_for_cleanup_execution_preflight",
    )
    cleanup_preflight = service.staging_cleanup_execution_preflight(
        manual_approval_id=manual_approval["event_id"],
        requested_by="tester",
        preflight_decision="prepared_for_cleanup_execution_dry_run",
    )
    cleanup_dry_run = service.staging_cleanup_execution_dry_run(
        preflight_id=cleanup_preflight["event_id"],
        simulated_by="tester",
        dry_run_decision="simulated_for_manual_review",
        note="aggregate dry-run only",
    )

    assert cleanup_dry_run["stage"] == "V5.6-P17"
    assert cleanup_dry_run["status"] == "cleanup_execution_dry_run_ready_for_review"
    assert isinstance(cleanup_dry_run["event_id"], int)
    assert cleanup_dry_run["preflight_id"] == cleanup_preflight["event_id"]
    assert cleanup_dry_run["manual_approval_id"] == manual_approval["event_id"]
    assert cleanup_dry_run["evidence_summary"]["evidence_package_hash"] == verified["evidence_summary"]["evidence_package_hash"]
    assert cleanup_dry_run["simulation"]["candidate_record_count"] == 2
    assert cleanup_dry_run["simulation"]["records_with_operations"] >= 1
    assert cleanup_dry_run["simulation"]["simulated_mutation_count"] >= 1
    assert cleanup_dry_run["simulation"]["operation_counts"]["normalize_enum"] == 1
    assert cleanup_dry_run["simulation"]["contains_sql"] is False
    assert cleanup_dry_run["simulation"]["contains_executable_code"] is False
    assert cleanup_dry_run["simulation"]["can_execute_now"] is False
    assert cleanup_dry_run["simulation"]["record_bodies_included"] is False
    assert cleanup_dry_run["decision"]["cleanup_execution_dry_run_recorded"] is True
    assert cleanup_dry_run["decision"]["cleanup_execution_dry_run_ready_for_review"] is True
    assert cleanup_dry_run["decision"]["cleanup_execution_approved_now"] is False
    assert cleanup_dry_run["decision"]["cleanup_application_allowed_now"] is False
    assert cleanup_dry_run["decision"]["cleanup_executed_now"] is False
    assert cleanup_dry_run["decision"]["can_execute_cleanup_now"] is False
    assert cleanup_dry_run["decision"]["mutates_staging_records_now"] is False
    assert cleanup_dry_run["decision"]["writes_staging_records_now"] is False
    assert cleanup_dry_run["decision"]["writes_learning_samples_now"] is False
    assert cleanup_dry_run["decision"]["training_started_now"] is False
    assert cleanup_dry_run["decision"]["can_start_training_now"] is False
    assert "evidence_package" not in cleanup_dry_run
    assert "historical_outcome_source" not in cleanup_dry_run
    check_status = {check["name"]: check["status"] for check in cleanup_dry_run["checks"]}
    assert check_status["preflight_ready_for_dry_run"] == "passed"
    assert check_status["simulation_contains_no_executable_payload"] == "passed"
    assert check_status["cleanup_and_training_remain_blocked"] == "passed"

    dry_runs = service.list_staging_cleanup_execution_dry_runs(limit=5)
    assert dry_runs[0]["id"] == cleanup_dry_run["event_id"]
    assert dry_runs[0]["dry_run"]["simulated_by"] == "tester"
    assert "evidence_package" not in dry_runs[0]


def test_dataset2_cleanup_execution_dry_run_review_is_metadata_only(tmp_path, test_db):
    pack = _write_dataset2_pack(
        tmp_path,
        [
            _record(pattern_id="EXECUTION_REVIEW_001", risk_level="medium_high", split_tag="train"),
            _record(pattern_id="EXECUTION_REVIEW_002", action_label="RISK_ALERT", risk_level="high", split_tag="test"),
        ],
    )
    service = Dataset2TrainingReadinessService()

    missing = service.staging_cleanup_execution_dry_run_review(
        dry_run_id=999999,
        reviewed_by="tester",
    )
    assert missing["status"] == "cleanup_execution_dry_run_review_blocked_missing_dry_run"
    assert missing["decision"]["writes_existing_event_now"] is False
    assert missing["decision"]["cleanup_execution_dry_run_review_accepted"] is False
    assert missing["decision"]["cleanup_executed_now"] is False
    assert missing["decision"]["training_started_now"] is False

    review = service.create_import_queue_review(source_dir=str(pack), limit=10, reviewed_by="tester")
    imported = service.import_reviewed_to_staging(
        source_dir=str(pack),
        limit=10,
        review_event_id=review["event_id"],
        imported_by="tester",
    )
    quality = service.staging_quality_review(package_id=imported["package_id"], reviewed_by="tester")
    plan = service.staging_fix_plan(quality_review_id=quality["event_id"], planned_by="tester")
    approval = service.approve_staging_fix_plan(
        fix_plan_event_id=plan["event_id"],
        approved_by="tester",
        approval_decision="approved_for_preflight",
    )
    fix_preflight = service.staging_fix_preflight(approval_event_id=approval["event_id"], requested_by="tester")
    spec = service.staging_cleanup_execution_spec(preflight_event_id=fix_preflight["event_id"], specified_by="tester")
    dry_run = service.staging_cleanup_dry_run_verification(execution_spec_event_id=spec["event_id"], verified_by="tester")
    blocked_manual = service.staging_cleanup_manual_evidence_verification(
        dry_run_verification_id=dry_run["event_id"],
        evidence_package={},
        verified_by="tester",
    )
    blocked_acceptance = service.staging_cleanup_manual_evidence_acceptance_review(
        manual_evidence_verification_id=blocked_manual["event_id"],
        accepted_by="tester",
    )
    blocked_application = service.staging_cleanup_application_review(
        acceptance_review_id=blocked_acceptance["event_id"],
        reviewed_by="tester",
    )
    blocked_plan = service.staging_cleanup_execution_approval_plan(
        cleanup_application_review_id=blocked_application["event_id"],
        planned_by="tester",
    )
    blocked_approval = service.staging_cleanup_execution_manual_approval(
        approval_plan_id=blocked_plan["event_id"],
        approved_by="tester",
    )
    blocked_preflight = service.staging_cleanup_execution_preflight(
        manual_approval_id=blocked_approval["event_id"],
        requested_by="tester",
    )
    blocked_dry_run = service.staging_cleanup_execution_dry_run(
        preflight_id=blocked_preflight["event_id"],
        simulated_by="tester",
    )
    blocked_review = service.staging_cleanup_execution_dry_run_review(
        dry_run_id=blocked_dry_run["event_id"],
        reviewed_by="tester",
    )
    assert blocked_review["status"] == "cleanup_execution_dry_run_review_blocked"
    assert blocked_review["decision"]["cleanup_execution_dry_run_review_recorded"] is True
    assert blocked_review["decision"]["cleanup_execution_dry_run_review_accepted"] is False
    assert blocked_review["decision"]["can_execute_cleanup_now"] is False
    assert blocked_review["decision"]["writes_learning_samples_now"] is False

    verified = service.staging_cleanup_manual_evidence_verification(
        dry_run_verification_id=dry_run["event_id"],
        evidence_package=_manual_evidence_package(),
        verified_by="tester",
    )
    accepted = service.staging_cleanup_manual_evidence_acceptance_review(
        manual_evidence_verification_id=verified["event_id"],
        accepted_by="tester",
        acceptance_decision="accepted_for_cleanup_review",
    )
    application = service.staging_cleanup_application_review(
        acceptance_review_id=accepted["event_id"],
        reviewed_by="tester",
        review_decision="ready_for_future_cleanup_application",
    )
    approval_plan = service.staging_cleanup_execution_approval_plan(
        cleanup_application_review_id=application["event_id"],
        planned_by="tester",
        plan_decision="prepared_for_manual_approval",
    )
    manual_approval = service.staging_cleanup_execution_manual_approval(
        approval_plan_id=approval_plan["event_id"],
        approved_by="tester",
        approval_decision="approved_for_cleanup_execution_preflight",
    )
    cleanup_preflight = service.staging_cleanup_execution_preflight(
        manual_approval_id=manual_approval["event_id"],
        requested_by="tester",
        preflight_decision="prepared_for_cleanup_execution_dry_run",
    )
    cleanup_dry_run = service.staging_cleanup_execution_dry_run(
        preflight_id=cleanup_preflight["event_id"],
        simulated_by="tester",
        dry_run_decision="simulated_for_manual_review",
    )
    cleanup_review = service.staging_cleanup_execution_dry_run_review(
        dry_run_id=cleanup_dry_run["event_id"],
        reviewed_by="tester",
        review_decision="approved_for_cleanup_execution_plan",
        note="review aggregate dry-run only",
    )

    assert cleanup_review["stage"] == "V5.6-P17"
    assert cleanup_review["status"] == "cleanup_execution_dry_run_review_accepted"
    assert isinstance(cleanup_review["event_id"], int)
    assert cleanup_review["dry_run_id"] == cleanup_dry_run["event_id"]
    assert cleanup_review["preflight_id"] == cleanup_preflight["event_id"]
    assert cleanup_review["evidence_summary"]["evidence_package_hash"] == verified["evidence_summary"]["evidence_package_hash"]
    assert cleanup_review["source_dry_run_summary"]["blocked_check_count"] == 0
    assert cleanup_review["simulation_summary"]["candidate_record_count"] == 2
    assert cleanup_review["simulation_summary"]["simulated_mutation_count"] >= 1
    assert cleanup_review["simulation_summary"]["record_bodies_included"] is False
    assert cleanup_review["simulation_summary"]["contains_sql"] is False
    assert cleanup_review["simulation_summary"]["contains_executable_code"] is False
    assert cleanup_review["simulation_summary"]["can_execute_now"] is False
    assert cleanup_review["decision"]["cleanup_execution_dry_run_review_recorded"] is True
    assert cleanup_review["decision"]["cleanup_execution_dry_run_review_accepted"] is True
    assert cleanup_review["decision"]["cleanup_execution_approved_now"] is False
    assert cleanup_review["decision"]["cleanup_application_allowed_now"] is False
    assert cleanup_review["decision"]["cleanup_executed_now"] is False
    assert cleanup_review["decision"]["can_execute_cleanup_now"] is False
    assert cleanup_review["decision"]["future_cleanup_execution_plan_required"] is True
    assert cleanup_review["decision"]["mutates_staging_records_now"] is False
    assert cleanup_review["decision"]["writes_staging_records_now"] is False
    assert cleanup_review["decision"]["writes_learning_samples_now"] is False
    assert cleanup_review["decision"]["training_started_now"] is False
    assert cleanup_review["decision"]["can_start_training_now"] is False
    assert "evidence_package" not in cleanup_review
    assert "historical_outcome_source" not in cleanup_review
    check_status = {check["name"]: check["status"] for check in cleanup_review["checks"]}
    assert check_status["dry_run_ready_for_manual_review"] == "passed"
    assert check_status["aggregate_only_no_record_bodies"] == "passed"
    assert check_status["cleanup_and_training_remain_blocked"] == "passed"

    reviews = service.list_staging_cleanup_execution_dry_run_reviews(limit=5)
    assert reviews[0]["id"] == cleanup_review["event_id"]
    assert reviews[0]["review"]["reviewed_by"] == "tester"
    assert "evidence_package" not in reviews[0]


def test_dataset2_cleanup_execution_plan_is_preflight_only(tmp_path, test_db):
    pack = _write_dataset2_pack(
        tmp_path,
        [
            _record(
                pattern_id="EXECUTION_PLAN_001",
                risk_level="medium_high",
                split_tag="train",
                observable_features=["['big_yang']", "high_volume"],
            ),
            _record(pattern_id="EXECUTION_PLAN_002", action_label="RISK_ALERT", risk_level="high", split_tag="test"),
        ],
    )
    service = Dataset2TrainingReadinessService()

    missing = service.staging_cleanup_execution_plan(
        dry_run_review_id=999999,
        planned_by="tester",
    )
    assert missing["status"] == "cleanup_execution_plan_blocked_missing_dry_run_review"
    assert missing["decision"]["writes_existing_event_now"] is False
    assert missing["decision"]["cleanup_execution_plan_ready_for_preflight"] is False
    assert missing["decision"]["cleanup_executed_now"] is False
    assert missing["decision"]["training_started_now"] is False

    review = service.create_import_queue_review(source_dir=str(pack), limit=10, reviewed_by="tester")
    imported = service.import_reviewed_to_staging(
        source_dir=str(pack),
        limit=10,
        review_event_id=review["event_id"],
        imported_by="tester",
    )
    quality = service.staging_quality_review(package_id=imported["package_id"], reviewed_by="tester")
    fix_plan = service.staging_fix_plan(quality_review_id=quality["event_id"], planned_by="tester")
    approval = service.approve_staging_fix_plan(
        fix_plan_event_id=fix_plan["event_id"],
        approved_by="tester",
        approval_decision="approved_for_preflight",
    )
    fix_preflight = service.staging_fix_preflight(approval_event_id=approval["event_id"], requested_by="tester")
    spec = service.staging_cleanup_execution_spec(preflight_event_id=fix_preflight["event_id"], specified_by="tester")
    dry_run = service.staging_cleanup_dry_run_verification(execution_spec_event_id=spec["event_id"], verified_by="tester")
    blocked_manual = service.staging_cleanup_manual_evidence_verification(
        dry_run_verification_id=dry_run["event_id"],
        evidence_package={},
        verified_by="tester",
    )
    blocked_acceptance = service.staging_cleanup_manual_evidence_acceptance_review(
        manual_evidence_verification_id=blocked_manual["event_id"],
        accepted_by="tester",
    )
    blocked_application = service.staging_cleanup_application_review(
        acceptance_review_id=blocked_acceptance["event_id"],
        reviewed_by="tester",
    )
    blocked_approval_plan = service.staging_cleanup_execution_approval_plan(
        cleanup_application_review_id=blocked_application["event_id"],
        planned_by="tester",
    )
    blocked_approval = service.staging_cleanup_execution_manual_approval(
        approval_plan_id=blocked_approval_plan["event_id"],
        approved_by="tester",
    )
    blocked_preflight = service.staging_cleanup_execution_preflight(
        manual_approval_id=blocked_approval["event_id"],
        requested_by="tester",
    )
    blocked_dry_run = service.staging_cleanup_execution_dry_run(
        preflight_id=blocked_preflight["event_id"],
        simulated_by="tester",
    )
    blocked_review = service.staging_cleanup_execution_dry_run_review(
        dry_run_id=blocked_dry_run["event_id"],
        reviewed_by="tester",
    )
    blocked_plan = service.staging_cleanup_execution_plan(
        dry_run_review_id=blocked_review["event_id"],
        planned_by="tester",
    )
    assert blocked_plan["status"] == "cleanup_execution_plan_blocked"
    assert blocked_plan["decision"]["cleanup_execution_plan_recorded"] is True
    assert blocked_plan["decision"]["cleanup_execution_plan_ready_for_preflight"] is False
    assert blocked_plan["decision"]["can_execute_cleanup_now"] is False
    assert blocked_plan["decision"]["training_started_now"] is False

    verified = service.staging_cleanup_manual_evidence_verification(
        dry_run_verification_id=dry_run["event_id"],
        evidence_package=_manual_evidence_package(),
        verified_by="tester",
    )
    accepted = service.staging_cleanup_manual_evidence_acceptance_review(
        manual_evidence_verification_id=verified["event_id"],
        accepted_by="tester",
        acceptance_decision="accepted_for_cleanup_review",
    )
    application = service.staging_cleanup_application_review(
        acceptance_review_id=accepted["event_id"],
        reviewed_by="tester",
        review_decision="ready_for_future_cleanup_application",
    )
    approval_plan = service.staging_cleanup_execution_approval_plan(
        cleanup_application_review_id=application["event_id"],
        planned_by="tester",
        plan_decision="prepared_for_manual_approval",
    )
    manual_approval = service.staging_cleanup_execution_manual_approval(
        approval_plan_id=approval_plan["event_id"],
        approved_by="tester",
        approval_decision="approved_for_cleanup_execution_preflight",
    )
    cleanup_preflight = service.staging_cleanup_execution_preflight(
        manual_approval_id=manual_approval["event_id"],
        requested_by="tester",
        preflight_decision="prepared_for_cleanup_execution_dry_run",
    )
    cleanup_dry_run = service.staging_cleanup_execution_dry_run(
        preflight_id=cleanup_preflight["event_id"],
        simulated_by="tester",
        dry_run_decision="simulated_for_manual_review",
    )
    cleanup_review = service.staging_cleanup_execution_dry_run_review(
        dry_run_id=cleanup_dry_run["event_id"],
        reviewed_by="tester",
        review_decision="approved_for_cleanup_execution_plan",
    )
    execution_plan = service.staging_cleanup_execution_plan(
        dry_run_review_id=cleanup_review["event_id"],
        planned_by="tester",
        plan_decision="prepared_for_controlled_cleanup_execution_preflight",
        note="plan automated cleanup only",
    )

    assert execution_plan["stage"] == "V5.6-P17"
    assert execution_plan["status"] == "cleanup_execution_plan_ready_for_preflight"
    assert isinstance(execution_plan["event_id"], int)
    assert execution_plan["dry_run_review_id"] == cleanup_review["event_id"]
    assert execution_plan["dry_run_id"] == cleanup_dry_run["event_id"]
    assert execution_plan["execution_plan"]["scope"] == "automated_cleanup_operations_only"
    assert execution_plan["execution_plan"]["planned_operation_count"] >= 1
    assert execution_plan["execution_plan"]["automated_operation_counts"]["normalize_enum"] == 1
    assert execution_plan["execution_plan"]["automated_operation_counts"]["parse_stringified_list_items"] == 1
    assert execution_plan["execution_plan"]["contains_sql"] is False
    assert execution_plan["execution_plan"]["contains_executable_code"] is False
    assert execution_plan["execution_plan"]["can_execute_now"] is False
    assert execution_plan["execution_plan"]["record_bodies_included"] is False
    assert execution_plan["decision"]["cleanup_execution_plan_recorded"] is True
    assert execution_plan["decision"]["cleanup_execution_plan_ready_for_preflight"] is True
    assert execution_plan["decision"]["cleanup_execution_approved_now"] is False
    assert execution_plan["decision"]["cleanup_application_allowed_now"] is False
    assert execution_plan["decision"]["cleanup_executed_now"] is False
    assert execution_plan["decision"]["can_execute_cleanup_now"] is False
    assert execution_plan["decision"]["mutates_staging_records_now"] is False
    assert execution_plan["decision"]["writes_staging_records_now"] is False
    assert execution_plan["decision"]["writes_learning_samples_now"] is False
    assert execution_plan["decision"]["training_started_now"] is False
    assert execution_plan["decision"]["can_start_training_now"] is False
    assert "evidence_package" not in execution_plan
    assert "historical_outcome_source" not in execution_plan
    check_status = {check["name"]: check["status"] for check in execution_plan["checks"]}
    assert check_status["dry_run_review_accepted"] == "passed"
    assert check_status["plan_contains_no_executable_payload"] == "passed"
    assert check_status["cleanup_and_training_remain_blocked"] == "passed"

    plans = service.list_staging_cleanup_execution_plans(limit=5)
    assert plans[0]["id"] == execution_plan["event_id"]
    assert plans[0]["planning"]["planned_by"] == "tester"
    assert "evidence_package" not in plans[0]


def test_dataset2_readiness_api_smoke(client, tmp_path):
    pack = _write_dataset2_pack(tmp_path, [_record()])

    readiness = client.get("/api/learning/dataset2/readiness", params={"source_dir": str(pack)})
    preview = client.post("/api/learning/dataset2/normalized-preview", params={"source_dir": str(pack), "limit": 1})
    cleanup = client.post("/api/learning/dataset2/cleanup-package", params={"source_dir": str(pack), "limit": 1})
    queue = client.post(
        "/api/learning/dataset2/import-queue/review",
        json={"source_dir": str(pack), "limit": 1, "reviewed_by": "api-test"},
    )
    reviews = client.get("/api/learning/dataset2/import-queue/reviews", params={"limit": 3})
    staging = client.post(
        "/api/learning/dataset2/staging/import",
        json={"source_dir": str(pack), "limit": 1, "review_event_id": queue.json().get("event_id"), "imported_by": "api-test"},
    )
    staging_records = client.get("/api/learning/dataset2/staging/records", params={"limit": 3})
    staging_summary = client.get("/api/learning/dataset2/staging/summary")
    quality = client.post(
        "/api/learning/dataset2/staging/quality-review",
        json={"package_id": staging.json().get("package_id"), "reviewed_by": "api-test"},
    )
    quality_reviews = client.get("/api/learning/dataset2/staging/quality-reviews", params={"limit": 3})
    fix_plan = client.post(
        "/api/learning/dataset2/staging/fix-plan",
        json={"quality_review_id": quality.json().get("event_id"), "planned_by": "api-test"},
    )
    fix_plans = client.get("/api/learning/dataset2/staging/fix-plans", params={"limit": 3})
    approval = client.post(
        "/api/learning/dataset2/staging/fix-plan/approval",
        json={
            "fix_plan_event_id": fix_plan.json().get("event_id"),
            "approved_by": "api-test",
            "approval_decision": "approved_for_preflight",
        },
    )
    approvals = client.get("/api/learning/dataset2/staging/fix-plan/approvals", params={"limit": 3})
    preflight = client.post(
        "/api/learning/dataset2/staging/fix-preflight",
        json={"approval_event_id": approval.json().get("event_id"), "requested_by": "api-test"},
    )
    preflights = client.get("/api/learning/dataset2/staging/fix-preflights", params={"limit": 3})
    execution_spec = client.post(
        "/api/learning/dataset2/staging/cleanup-execution-spec",
        json={"preflight_event_id": preflight.json().get("event_id"), "specified_by": "api-test"},
    )
    execution_specs = client.get("/api/learning/dataset2/staging/cleanup-execution-specs", params={"limit": 3})
    dry_run = client.post(
        "/api/learning/dataset2/staging/cleanup-execution-spec/dry-run-verify",
        json={"execution_spec_event_id": execution_spec.json().get("event_id"), "verified_by": "api-test"},
    )
    dry_runs = client.get(
        "/api/learning/dataset2/staging/cleanup-execution-spec/dry-run-verifications",
        params={"limit": 3},
    )
    manual_evidence = client.post(
        "/api/learning/dataset2/staging/cleanup-manual-evidence/verify",
        json={"dry_run_verification_id": dry_run.json().get("event_id"), "verified_by": "api-test"},
    )
    manual_evidence_history = client.get(
        "/api/learning/dataset2/staging/cleanup-manual-evidence/verifications",
        params={"limit": 3},
    )
    manual_acceptance = client.post(
        "/api/learning/dataset2/staging/cleanup-manual-evidence/acceptance-review",
        json={"manual_evidence_verification_id": manual_evidence.json().get("event_id"), "accepted_by": "api-test"},
    )
    manual_acceptance_history = client.get(
        "/api/learning/dataset2/staging/cleanup-manual-evidence/acceptance-reviews",
        params={"limit": 3},
    )
    cleanup_application = client.post(
        "/api/learning/dataset2/staging/cleanup-application-review",
        json={"acceptance_review_id": manual_acceptance.json().get("event_id"), "reviewed_by": "api-test"},
    )
    cleanup_application_history = client.get(
        "/api/learning/dataset2/staging/cleanup-application-reviews",
        params={"limit": 3},
    )
    execution_approval_plan = client.post(
        "/api/learning/dataset2/staging/cleanup-execution-approval-plan",
        json={"cleanup_application_review_id": cleanup_application.json().get("event_id"), "planned_by": "api-test"},
    )
    execution_approval_plans = client.get(
        "/api/learning/dataset2/staging/cleanup-execution-approval-plans",
        params={"limit": 3},
    )
    execution_manual_approval = client.post(
        "/api/learning/dataset2/staging/cleanup-execution-manual-approval",
        json={"approval_plan_id": execution_approval_plan.json().get("event_id"), "approved_by": "api-test"},
    )
    execution_manual_approvals = client.get(
        "/api/learning/dataset2/staging/cleanup-execution-manual-approvals",
        params={"limit": 3},
    )
    cleanup_preflight = client.post(
        "/api/learning/dataset2/staging/cleanup-execution-preflight",
        json={"manual_approval_id": execution_manual_approval.json().get("event_id"), "requested_by": "api-test"},
    )
    cleanup_preflights = client.get(
        "/api/learning/dataset2/staging/cleanup-execution-preflights",
        params={"limit": 3},
    )
    cleanup_execution_dry_run = client.post(
        "/api/learning/dataset2/staging/cleanup-execution-dry-run",
        json={"preflight_id": cleanup_preflight.json().get("event_id"), "simulated_by": "api-test"},
    )
    cleanup_execution_dry_runs = client.get(
        "/api/learning/dataset2/staging/cleanup-execution-dry-runs",
        params={"limit": 3},
    )
    cleanup_execution_dry_run_review = client.post(
        "/api/learning/dataset2/staging/cleanup-execution-dry-run-review",
        json={"dry_run_id": cleanup_execution_dry_run.json().get("event_id"), "reviewed_by": "api-test"},
    )
    cleanup_execution_dry_run_reviews = client.get(
        "/api/learning/dataset2/staging/cleanup-execution-dry-run-reviews",
        params={"limit": 3},
    )
    cleanup_execution_plan = client.post(
        "/api/learning/dataset2/staging/cleanup-execution-plan",
        json={"dry_run_review_id": cleanup_execution_dry_run_review.json().get("event_id"), "planned_by": "api-test"},
    )
    cleanup_execution_plans = client.get(
        "/api/learning/dataset2/staging/cleanup-execution-plans",
        params={"limit": 3},
    )

    assert readiness.status_code == 200
    assert preview.status_code == 200
    assert cleanup.status_code == 200
    assert queue.status_code == 200
    assert reviews.status_code == 200
    assert staging.status_code == 200
    assert staging_records.status_code == 200
    assert staging_summary.status_code == 200
    assert quality.status_code == 200
    assert quality_reviews.status_code == 200
    assert fix_plan.status_code == 200
    assert fix_plans.status_code == 200
    assert approval.status_code == 200
    assert approvals.status_code == 200
    assert preflight.status_code == 200
    assert preflights.status_code == 200
    assert execution_spec.status_code == 200
    assert execution_specs.status_code == 200
    assert dry_run.status_code == 200
    assert dry_runs.status_code == 200
    assert manual_evidence.status_code == 200
    assert manual_evidence_history.status_code == 200
    assert manual_acceptance.status_code == 200
    assert manual_acceptance_history.status_code == 200
    assert cleanup_application.status_code == 200
    assert cleanup_application_history.status_code == 200
    assert execution_approval_plan.status_code == 200
    assert execution_approval_plans.status_code == 200
    assert execution_manual_approval.status_code == 200
    assert execution_manual_approvals.status_code == 200
    assert cleanup_preflight.status_code == 200
    assert cleanup_preflights.status_code == 200
    assert cleanup_execution_dry_run.status_code == 200
    assert cleanup_execution_dry_runs.status_code == 200
    assert cleanup_execution_dry_run_review.status_code == 200
    assert cleanup_execution_dry_run_reviews.status_code == 200
    assert cleanup_execution_plan.status_code == 200
    assert cleanup_execution_plans.status_code == 200
    assert readiness.json()["decision"]["can_start_training_now"] is False
    assert preview.json()["preview_count"] == 1
    assert preview.json()["safety_summary"]["allow_live_order"] is False
    assert cleanup.json()["decision"]["can_import_to_database_now"] is False
    assert queue.json()["decision"]["training_started_now"] is False
    assert queue.json()["decision"]["normalized_records_persisted"] is False
    assert reviews.json()[0]["review"]["reviewed_by"] == "api-test"
    assert staging.json()["decision"]["writes_learning_samples_now"] is False
    assert staging.json()["decision"]["training_started_now"] is False
    assert staging_records.json()[0]["status"] == "staged_review_only"
    assert staging_summary.json()["decision"]["can_start_training_now"] is False
    assert quality.json()["decision"]["training_started_now"] is False
    assert quality.json()["decision"]["writes_learning_samples_now"] is False
    assert quality_reviews.json()[0]["review"]["reviewed_by"] == "api-test"
    assert fix_plan.json()["decision"]["training_started_now"] is False
    assert fix_plan.json()["decision"]["writes_learning_samples_now"] is False
    assert fix_plan.json()["plan"]["can_be_applied_automatically_now"] is False
    assert fix_plans.json()[0]["review"]["planned_by"] == "api-test"
    assert approval.json()["decision"]["approval_allows_fix_application_now"] is False
    assert approval.json()["decision"]["can_generate_preflight_now"] is True
    assert approvals.json()[0]["approval"]["approved_by"] == "api-test"
    assert preflight.json()["decision"]["fixes_applied_now"] is False
    assert preflight.json()["decision"]["writes_learning_samples_now"] is False
    assert preflights.json()[0]["request"]["requested_by"] == "api-test"
    assert execution_spec.json()["spec"]["can_execute_now"] is False
    assert execution_spec.json()["decision"]["cleanup_executed_now"] is False
    assert execution_spec.json()["decision"]["writes_learning_samples_now"] is False
    assert execution_specs.json()[0]["review"]["specified_by"] == "api-test"
    assert dry_run.json()["decision"]["cleanup_application_allowed_now"] is False
    assert dry_run.json()["decision"]["cleanup_executed_now"] is False
    assert dry_run.json()["decision"]["writes_learning_samples_now"] is False
    assert dry_runs.json()[0]["verification"]["verified_by"] == "api-test"
    assert manual_evidence.json()["decision"]["cleanup_application_allowed_now"] is False
    assert manual_evidence.json()["decision"]["writes_learning_samples_now"] is False
    assert manual_evidence.json()["verification"]["evidence_package_body_included"] is False
    assert manual_evidence_history.json()[0]["verification"]["verified_by"] == "api-test"
    assert manual_acceptance.json()["decision"]["cleanup_application_allowed_now"] is False
    assert manual_acceptance.json()["decision"]["cleanup_executed_now"] is False
    assert manual_acceptance.json()["decision"]["writes_learning_samples_now"] is False
    assert manual_acceptance.json()["decision"]["training_started_now"] is False
    assert manual_acceptance_history.json()[0]["acceptance"]["accepted_by"] == "api-test"
    assert cleanup_application.json()["decision"]["cleanup_application_allowed_now"] is False
    assert cleanup_application.json()["decision"]["cleanup_executed_now"] is False
    assert cleanup_application.json()["decision"]["writes_learning_samples_now"] is False
    assert cleanup_application.json()["decision"]["training_started_now"] is False
    assert cleanup_application_history.json()[0]["review"]["reviewed_by"] == "api-test"
    assert execution_approval_plan.json()["approval_plan"]["can_execute_now"] is False
    assert execution_approval_plan.json()["decision"]["cleanup_execution_approved_now"] is False
    assert execution_approval_plan.json()["decision"]["cleanup_application_allowed_now"] is False
    assert execution_approval_plan.json()["decision"]["cleanup_executed_now"] is False
    assert execution_approval_plan.json()["decision"]["writes_learning_samples_now"] is False
    assert execution_approval_plan.json()["decision"]["training_started_now"] is False
    assert execution_approval_plans.json()[0]["planning"]["planned_by"] == "api-test"
    assert execution_manual_approval.json()["source_approval_plan"]["can_execute_now"] is False
    assert execution_manual_approval.json()["decision"]["cleanup_execution_manual_approval_recorded"] is True
    assert execution_manual_approval.json()["decision"]["cleanup_execution_approved_now"] is False
    assert execution_manual_approval.json()["decision"]["cleanup_application_allowed_now"] is False
    assert execution_manual_approval.json()["decision"]["cleanup_executed_now"] is False
    assert execution_manual_approval.json()["decision"]["can_execute_cleanup_now"] is False
    assert execution_manual_approval.json()["decision"]["writes_learning_samples_now"] is False
    assert execution_manual_approval.json()["decision"]["training_started_now"] is False
    assert execution_manual_approvals.json()[0]["manual_approval"]["approved_by"] == "api-test"
    assert cleanup_preflight.json()["preflight"]["can_execute_now"] is False
    assert cleanup_preflight.json()["preflight"]["contains_sql"] is False
    assert cleanup_preflight.json()["decision"]["cleanup_execution_preflight_recorded"] is True
    assert cleanup_preflight.json()["decision"]["cleanup_execution_approved_now"] is False
    assert cleanup_preflight.json()["decision"]["cleanup_application_allowed_now"] is False
    assert cleanup_preflight.json()["decision"]["cleanup_executed_now"] is False
    assert cleanup_preflight.json()["decision"]["can_execute_cleanup_now"] is False
    assert cleanup_preflight.json()["decision"]["writes_learning_samples_now"] is False
    assert cleanup_preflight.json()["decision"]["training_started_now"] is False
    assert cleanup_preflights.json()[0]["request"]["requested_by"] == "api-test"
    assert cleanup_execution_dry_run.json()["simulation"]["can_execute_now"] is False
    assert cleanup_execution_dry_run.json()["simulation"]["record_bodies_included"] is False
    assert cleanup_execution_dry_run.json()["decision"]["cleanup_execution_dry_run_recorded"] is True
    assert cleanup_execution_dry_run.json()["decision"]["cleanup_execution_approved_now"] is False
    assert cleanup_execution_dry_run.json()["decision"]["cleanup_application_allowed_now"] is False
    assert cleanup_execution_dry_run.json()["decision"]["cleanup_executed_now"] is False
    assert cleanup_execution_dry_run.json()["decision"]["can_execute_cleanup_now"] is False
    assert cleanup_execution_dry_run.json()["decision"]["writes_learning_samples_now"] is False
    assert cleanup_execution_dry_run.json()["decision"]["training_started_now"] is False
    assert cleanup_execution_dry_runs.json()[0]["dry_run"]["simulated_by"] == "api-test"
    assert cleanup_execution_dry_run_review.json()["simulation_summary"]["can_execute_now"] is False
    assert cleanup_execution_dry_run_review.json()["simulation_summary"]["record_bodies_included"] is False
    assert cleanup_execution_dry_run_review.json()["decision"]["cleanup_execution_dry_run_review_recorded"] is True
    assert cleanup_execution_dry_run_review.json()["decision"]["cleanup_execution_approved_now"] is False
    assert cleanup_execution_dry_run_review.json()["decision"]["cleanup_application_allowed_now"] is False
    assert cleanup_execution_dry_run_review.json()["decision"]["cleanup_executed_now"] is False
    assert cleanup_execution_dry_run_review.json()["decision"]["can_execute_cleanup_now"] is False
    assert cleanup_execution_dry_run_review.json()["decision"]["writes_learning_samples_now"] is False
    assert cleanup_execution_dry_run_review.json()["decision"]["training_started_now"] is False
    assert cleanup_execution_dry_run_reviews.json()[0]["review"]["reviewed_by"] == "api-test"
    assert cleanup_execution_plan.json()["execution_plan"]["can_execute_now"] is False
    assert cleanup_execution_plan.json()["execution_plan"]["record_bodies_included"] is False
    assert cleanup_execution_plan.json()["decision"]["cleanup_execution_plan_recorded"] is True
    assert cleanup_execution_plan.json()["decision"]["cleanup_execution_approved_now"] is False
    assert cleanup_execution_plan.json()["decision"]["cleanup_application_allowed_now"] is False
    assert cleanup_execution_plan.json()["decision"]["cleanup_executed_now"] is False
    assert cleanup_execution_plan.json()["decision"]["can_execute_cleanup_now"] is False
    assert cleanup_execution_plan.json()["decision"]["writes_learning_samples_now"] is False
    assert cleanup_execution_plan.json()["decision"]["training_started_now"] is False
    assert cleanup_execution_plans.json()[0]["planning"]["planned_by"] == "api-test"
