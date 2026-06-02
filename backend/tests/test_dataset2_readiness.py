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


def _cleanup_execution_plan_preflight_chain(service, pack, evidence_package, suffix="HELPER"):
    review = service.create_import_queue_review(source_dir=str(pack), limit=10, reviewed_by=f"{suffix}-tester")
    imported = service.import_reviewed_to_staging(
        source_dir=str(pack),
        limit=10,
        review_event_id=review["event_id"],
        imported_by=f"{suffix}-tester",
    )
    quality = service.staging_quality_review(package_id=imported["package_id"], reviewed_by=f"{suffix}-tester")
    fix_plan = service.staging_fix_plan(quality_review_id=quality["event_id"], planned_by=f"{suffix}-tester")
    approval = service.approve_staging_fix_plan(
        fix_plan_event_id=fix_plan["event_id"],
        approved_by=f"{suffix}-tester",
        approval_decision="approved_for_preflight",
    )
    fix_preflight = service.staging_fix_preflight(approval_event_id=approval["event_id"], requested_by=f"{suffix}-tester")
    spec = service.staging_cleanup_execution_spec(preflight_event_id=fix_preflight["event_id"], specified_by=f"{suffix}-tester")
    dry_run = service.staging_cleanup_dry_run_verification(execution_spec_event_id=spec["event_id"], verified_by=f"{suffix}-tester")
    verified = service.staging_cleanup_manual_evidence_verification(
        dry_run_verification_id=dry_run["event_id"],
        evidence_package=evidence_package,
        verified_by=f"{suffix}-tester",
    )
    accepted = service.staging_cleanup_manual_evidence_acceptance_review(
        manual_evidence_verification_id=verified["event_id"],
        accepted_by=f"{suffix}-tester",
        acceptance_decision="accepted_for_cleanup_review",
    )
    application = service.staging_cleanup_application_review(
        acceptance_review_id=accepted["event_id"],
        reviewed_by=f"{suffix}-tester",
        review_decision="ready_for_future_cleanup_application",
    )
    approval_plan = service.staging_cleanup_execution_approval_plan(
        cleanup_application_review_id=application["event_id"],
        planned_by=f"{suffix}-tester",
        plan_decision="prepared_for_manual_approval",
    )
    manual_approval = service.staging_cleanup_execution_manual_approval(
        approval_plan_id=approval_plan["event_id"],
        approved_by=f"{suffix}-tester",
        approval_decision="approved_for_cleanup_execution_preflight",
    )
    cleanup_preflight = service.staging_cleanup_execution_preflight(
        manual_approval_id=manual_approval["event_id"],
        requested_by=f"{suffix}-tester",
        preflight_decision="prepared_for_cleanup_execution_dry_run",
    )
    cleanup_dry_run = service.staging_cleanup_execution_dry_run(
        preflight_id=cleanup_preflight["event_id"],
        simulated_by=f"{suffix}-tester",
        dry_run_decision="simulated_for_manual_review",
    )
    cleanup_review = service.staging_cleanup_execution_dry_run_review(
        dry_run_id=cleanup_dry_run["event_id"],
        reviewed_by=f"{suffix}-tester",
        review_decision="approved_for_cleanup_execution_plan",
    )
    execution_plan = service.staging_cleanup_execution_plan(
        dry_run_review_id=cleanup_review["event_id"],
        planned_by=f"{suffix}-tester",
        plan_decision="prepared_for_controlled_cleanup_execution_preflight",
    )
    return service.staging_cleanup_execution_plan_preflight(
        execution_plan_id=execution_plan["event_id"],
        requested_by=f"{suffix}-tester",
        preflight_decision="prepared_for_controlled_cleanup_execution_dry_run",
    )


def _controlled_apply_execution_plan_execution_approval_chain(service, pack, evidence_package, suffix="HELPER"):
    plan_preflight = _cleanup_execution_plan_preflight_chain(service, pack, evidence_package, suffix=suffix)
    controlled = service.staging_cleanup_execution_controlled_dry_run(
        plan_preflight_id=plan_preflight["event_id"],
        simulated_by=f"{suffix}-tester",
        dry_run_decision="simulated_for_controlled_cleanup_review",
    )
    review = service.staging_cleanup_execution_controlled_dry_run_review(
        controlled_dry_run_id=controlled["event_id"],
        reviewed_by=f"{suffix}-tester",
        review_decision="approved_for_controlled_cleanup_execution_review",
    )
    approval = service.staging_cleanup_execution_controlled_approval(
        controlled_review_id=review["event_id"],
        approved_by=f"{suffix}-tester",
        approval_decision="approved_for_controlled_cleanup_execution_preflight",
    )
    preflight = service.staging_cleanup_execution_controlled_preflight(
        controlled_approval_id=approval["event_id"],
        requested_by=f"{suffix}-tester",
        preflight_decision="prepared_for_controlled_cleanup_execution_apply_dry_run",
    )
    apply_dry_run = service.staging_cleanup_execution_controlled_apply_dry_run(
        controlled_preflight_id=preflight["event_id"],
        simulated_by=f"{suffix}-tester",
        dry_run_decision="simulated_for_controlled_cleanup_apply_review",
    )
    apply_review = service.staging_cleanup_execution_controlled_apply_dry_run_review(
        apply_dry_run_id=apply_dry_run["event_id"],
        reviewed_by=f"{suffix}-tester",
        review_decision="approved_for_controlled_cleanup_apply_execution_review",
    )
    apply_approval = service.staging_cleanup_execution_controlled_apply_approval(
        apply_review_id=apply_review["event_id"],
        approved_by=f"{suffix}-tester",
        approval_decision="approved_for_controlled_cleanup_apply_execution_preflight",
    )
    apply_preflight = service.staging_cleanup_execution_controlled_apply_preflight(
        apply_approval_id=apply_approval["event_id"],
        requested_by=f"{suffix}-tester",
        preflight_decision="prepared_for_controlled_cleanup_apply_execution_dry_run",
    )
    execution_dry_run = service.staging_cleanup_execution_controlled_apply_execution_dry_run(
        apply_preflight_id=apply_preflight["event_id"],
        simulated_by=f"{suffix}-tester",
        dry_run_decision="simulated_for_controlled_cleanup_apply_execution_review",
    )
    execution_review = service.staging_cleanup_execution_controlled_apply_execution_dry_run_review(
        apply_execution_dry_run_id=execution_dry_run["event_id"],
        reviewed_by=f"{suffix}-tester",
        review_decision="approved_for_controlled_cleanup_apply_execution_plan",
    )
    execution_plan = service.staging_cleanup_execution_controlled_apply_execution_plan(
        apply_execution_review_id=execution_review["event_id"],
        planned_by=f"{suffix}-tester",
        plan_decision="prepared_for_controlled_cleanup_apply_execution_plan_preflight",
    )
    execution_plan_preflight = service.staging_cleanup_execution_controlled_apply_execution_plan_preflight(
        apply_execution_plan_id=execution_plan["event_id"],
        requested_by=f"{suffix}-tester",
        preflight_decision="prepared_for_controlled_cleanup_apply_execution_plan_dry_run",
    )
    execution_plan_dry_run = service.staging_cleanup_execution_controlled_apply_execution_plan_dry_run(
        apply_execution_plan_preflight_id=execution_plan_preflight["event_id"],
        simulated_by=f"{suffix}-tester",
        dry_run_decision="simulated_for_controlled_cleanup_apply_execution_plan_review",
    )
    execution_plan_review = service.staging_cleanup_execution_controlled_apply_execution_plan_dry_run_review(
        apply_execution_plan_dry_run_id=execution_plan_dry_run["event_id"],
        reviewed_by=f"{suffix}-tester",
        review_decision="approved_for_controlled_cleanup_apply_execution_plan_execution_approval",
    )
    execution_plan_approval = service.staging_cleanup_execution_controlled_apply_execution_plan_execution_approval(
        apply_execution_plan_dry_run_review_id=execution_plan_review["event_id"],
        approved_by=f"{suffix}-tester",
        approval_decision="approved_for_controlled_cleanup_apply_execution_plan_execution_preflight",
    )
    return {
        "plan_preflight": plan_preflight,
        "controlled": controlled,
        "review": review,
        "approval": approval,
        "preflight": preflight,
        "apply_dry_run": apply_dry_run,
        "apply_review": apply_review,
        "apply_approval": apply_approval,
        "apply_preflight": apply_preflight,
        "execution_dry_run": execution_dry_run,
        "execution_review": execution_review,
        "execution_plan": execution_plan,
        "execution_plan_preflight": execution_plan_preflight,
        "execution_plan_dry_run": execution_plan_dry_run,
        "execution_plan_review": execution_plan_review,
        "execution_plan_approval": execution_plan_approval,
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

    assert data["stage"] == "V5.6-P43"
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

    assert data["stage"] == "V5.6-P43"
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

    assert data["stage"] == "V5.6-P43"
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

    assert imported["stage"] == "V5.6-P43"
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

    assert quality["stage"] == "V5.6-P43"
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

    assert plan["stage"] == "V5.6-P43"
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

    assert approval["stage"] == "V5.6-P43"
    assert approval["status"] == "fix_plan_approved_for_preflight"
    assert approval["decision"]["approval_allows_fix_application_now"] is False
    assert approval["decision"]["can_generate_preflight_now"] is True
    assert approval["decision"]["writes_learning_samples_now"] is False
    assert preflight["stage"] == "V5.6-P43"
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

    assert spec["stage"] == "V5.6-P43"
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

    assert dry_run["stage"] == "V5.6-P43"
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

    assert verified["stage"] == "V5.6-P43"
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

    assert accepted["stage"] == "V5.6-P43"
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

    assert application["stage"] == "V5.6-P43"
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

    assert approval_plan["stage"] == "V5.6-P43"
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

    assert manual_approval["stage"] == "V5.6-P43"
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

    assert cleanup_preflight["stage"] == "V5.6-P43"
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

    assert cleanup_dry_run["stage"] == "V5.6-P43"
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

    assert cleanup_review["stage"] == "V5.6-P43"
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

    assert execution_plan["stage"] == "V5.6-P43"
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


def test_dataset2_cleanup_execution_plan_preflight_is_metadata_only(tmp_path, test_db):
    pack = _write_dataset2_pack(
        tmp_path,
        [
            _record(
                pattern_id="PLAN_PREFLIGHT_001",
                risk_level="medium_high",
                split_tag="train",
                observable_features=["['big_yang']", "high_volume"],
                evidence_summary="",
            ),
            _record(pattern_id="PLAN_PREFLIGHT_002", action_label="RISK_ALERT", risk_level="high", split_tag="test"),
        ],
    )
    service = Dataset2TrainingReadinessService()

    missing = service.staging_cleanup_execution_plan_preflight(
        execution_plan_id=999999,
        requested_by="tester",
    )
    assert missing["status"] == "cleanup_execution_plan_preflight_blocked_missing_plan"
    assert missing["decision"]["writes_existing_event_now"] is False
    assert missing["decision"]["cleanup_execution_plan_preflight_ready_for_dry_run"] is False
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
    blocked_plan_preflight = service.staging_cleanup_execution_plan_preflight(
        execution_plan_id=blocked_plan["event_id"],
        requested_by="tester",
    )
    assert blocked_plan_preflight["status"] == "cleanup_execution_plan_preflight_blocked"
    assert blocked_plan_preflight["decision"]["cleanup_execution_plan_preflight_recorded"] is True
    assert blocked_plan_preflight["decision"]["cleanup_execution_plan_preflight_ready_for_dry_run"] is False
    assert blocked_plan_preflight["decision"]["can_execute_cleanup_now"] is False
    assert blocked_plan_preflight["decision"]["writes_learning_samples_now"] is False

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
    )
    plan_preflight = service.staging_cleanup_execution_plan_preflight(
        execution_plan_id=execution_plan["event_id"],
        requested_by="tester",
        preflight_decision="prepared_for_controlled_cleanup_execution_dry_run",
        note="preflight controlled cleanup dry-run only",
    )

    assert plan_preflight["stage"] == "V5.6-P43"
    assert plan_preflight["status"] == "cleanup_execution_plan_preflight_ready_for_dry_run"
    assert isinstance(plan_preflight["event_id"], int)
    assert plan_preflight["execution_plan_id"] == execution_plan["event_id"]
    assert plan_preflight["dry_run_review_id"] == cleanup_review["event_id"]
    assert plan_preflight["preflight"]["staging_record_count"] == 2
    assert plan_preflight["preflight"]["expected_staging_record_count_after"] == 2
    assert plan_preflight["preflight"]["learning_sample_count"] == 0
    assert plan_preflight["preflight"]["expected_learning_sample_count_after"] == 0
    assert plan_preflight["preflight"]["automated_operation_count"] >= 1
    assert plan_preflight["preflight"]["manual_operation_count"] >= 1
    assert plan_preflight["preflight"]["transaction_required"] is True
    assert plan_preflight["preflight"]["rollback_required"] is True
    assert plan_preflight["preflight"]["allowed_tables"] == ["dataset2_staging_records"]
    assert "learning_samples" in plan_preflight["preflight"]["forbidden_tables"]
    assert plan_preflight["preflight"]["contains_sql"] is False
    assert plan_preflight["preflight"]["contains_executable_code"] is False
    assert plan_preflight["preflight"]["can_execute_now"] is False
    assert plan_preflight["preflight"]["record_bodies_included"] is False
    assert plan_preflight["decision"]["cleanup_execution_plan_preflight_recorded"] is True
    assert plan_preflight["decision"]["cleanup_execution_plan_preflight_ready_for_dry_run"] is True
    assert plan_preflight["decision"]["cleanup_execution_approved_now"] is False
    assert plan_preflight["decision"]["cleanup_application_allowed_now"] is False
    assert plan_preflight["decision"]["cleanup_executed_now"] is False
    assert plan_preflight["decision"]["can_execute_cleanup_now"] is False
    assert plan_preflight["decision"]["mutates_staging_records_now"] is False
    assert plan_preflight["decision"]["writes_staging_records_now"] is False
    assert plan_preflight["decision"]["writes_learning_samples_now"] is False
    assert plan_preflight["decision"]["training_started_now"] is False
    assert plan_preflight["decision"]["can_start_training_now"] is False
    assert "evidence_package" not in plan_preflight
    assert "historical_outcome_source" not in plan_preflight
    check_status = {check["name"]: check["status"] for check in plan_preflight["checks"]}
    assert check_status["execution_plan_ready_for_preflight"] == "passed"
    assert check_status["transaction_and_rollback_required"] == "passed"
    assert check_status["cleanup_and_training_remain_blocked"] == "passed"
    assert check_status["manual_backfill_separated"] == "warning"

    preflights = service.list_staging_cleanup_execution_plan_preflights(limit=5)
    assert preflights[0]["id"] == plan_preflight["event_id"]
    assert preflights[0]["request"]["requested_by"] == "tester"
    assert "evidence_package" not in preflights[0]


def test_dataset2_controlled_cleanup_dry_run_is_aggregate_only(tmp_path, test_db):
    pack = _write_dataset2_pack(
        tmp_path,
        [
            _record(
                pattern_id="CONTROLLED_DRY_RUN_001",
                risk_level="medium_high",
                split_tag="train",
                observable_features=["['big_yang']", "high_volume"],
                evidence_summary="",
            ),
            _record(pattern_id="CONTROLLED_DRY_RUN_002", action_label="RISK_ALERT", risk_level="high", split_tag="test"),
        ],
    )
    service = Dataset2TrainingReadinessService()

    missing = service.staging_cleanup_execution_controlled_dry_run(
        plan_preflight_id=999999,
        simulated_by="tester",
    )
    assert missing["status"] == "controlled_cleanup_dry_run_blocked_missing_preflight"
    assert missing["decision"]["writes_existing_event_now"] is False
    assert missing["decision"]["controlled_cleanup_dry_run_ready_for_review"] is False
    assert missing["decision"]["cleanup_executed_now"] is False
    assert missing["decision"]["training_started_now"] is False

    blocked_preflight = _cleanup_execution_plan_preflight_chain(service, pack, {}, suffix="blocked")
    assert blocked_preflight["status"] == "cleanup_execution_plan_preflight_blocked"
    blocked_dry_run = service.staging_cleanup_execution_controlled_dry_run(
        plan_preflight_id=blocked_preflight["event_id"],
        simulated_by="tester",
    )
    assert blocked_dry_run["status"] == "controlled_cleanup_dry_run_blocked"
    assert blocked_dry_run["decision"]["controlled_cleanup_dry_run_recorded"] is True
    assert blocked_dry_run["decision"]["controlled_cleanup_dry_run_ready_for_review"] is False
    assert blocked_dry_run["decision"]["can_execute_cleanup_now"] is False
    assert blocked_dry_run["decision"]["writes_learning_samples_now"] is False

    plan_preflight = _cleanup_execution_plan_preflight_chain(service, pack, _manual_evidence_package(), suffix="ready")
    assert plan_preflight["status"] == "cleanup_execution_plan_preflight_ready_for_dry_run"
    controlled = service.staging_cleanup_execution_controlled_dry_run(
        plan_preflight_id=plan_preflight["event_id"],
        simulated_by="tester",
        dry_run_decision="simulated_for_controlled_cleanup_review",
        note="aggregate controlled dry-run only",
    )

    assert controlled["stage"] == "V5.6-P43"
    assert controlled["status"] == "controlled_cleanup_dry_run_ready_for_review"
    assert isinstance(controlled["event_id"], int)
    assert controlled["plan_preflight_id"] == plan_preflight["event_id"]
    assert controlled["execution_plan_id"] == plan_preflight["execution_plan_id"]
    assert controlled["simulation"]["lock_key"] == plan_preflight["preflight"]["lock_key"]
    assert controlled["simulation"]["staging_record_count_before"] == 2
    assert controlled["simulation"]["expected_staging_record_count_after"] == 2
    assert controlled["simulation"]["learning_sample_count_before"] == 0
    assert controlled["simulation"]["expected_learning_sample_count_after"] == 0
    assert controlled["simulation"]["automated_operation_count"] >= 1
    assert controlled["simulation"]["manual_operation_count"] >= 1
    assert controlled["simulation"]["simulated_quality_flag_reduction_count"] == controlled["simulation"]["automated_operation_count"]
    assert controlled["simulation"]["simulated_manual_flag_remaining_count"] == controlled["simulation"]["manual_operation_count"]
    assert controlled["simulation"]["simulated_mutation_count"] == controlled["simulation"]["automated_operation_count"]
    assert controlled["simulation"]["contains_sql"] is False
    assert controlled["simulation"]["contains_executable_code"] is False
    assert controlled["simulation"]["can_execute_now"] is False
    assert controlled["simulation"]["record_bodies_included"] is False
    assert controlled["simulation"]["affected_rows_body_included"] is False
    assert controlled["simulation"]["writes_staging_records_now"] is False
    assert controlled["simulation"]["writes_learning_samples_now"] is False
    assert controlled["simulation"]["mutates_staging_records_now"] is False
    assert controlled["decision"]["controlled_cleanup_dry_run_recorded"] is True
    assert controlled["decision"]["controlled_cleanup_dry_run_ready_for_review"] is True
    assert controlled["decision"]["cleanup_execution_approved_now"] is False
    assert controlled["decision"]["cleanup_application_allowed_now"] is False
    assert controlled["decision"]["cleanup_executed_now"] is False
    assert controlled["decision"]["can_execute_cleanup_now"] is False
    assert controlled["decision"]["writes_staging_records_now"] is False
    assert controlled["decision"]["writes_learning_samples_now"] is False
    assert controlled["decision"]["mutates_staging_records_now"] is False
    assert controlled["decision"]["training_started_now"] is False
    assert controlled["decision"]["can_start_training_now"] is False
    assert "evidence_package" not in controlled
    assert "records" not in controlled["simulation"]
    check_status = {check["name"]: check["status"] for check in controlled["checks"]}
    assert check_status["plan_preflight_ready_for_dry_run"] == "passed"
    assert check_status["staging_count_still_matches"] == "passed"
    assert check_status["manual_backfill_separated"] == "warning"
    assert check_status["cleanup_and_training_remain_blocked"] == "passed"

    dry_runs = service.list_staging_cleanup_execution_controlled_dry_runs(limit=5)
    assert dry_runs[0]["id"] == controlled["event_id"]
    assert dry_runs[0]["dry_run"]["simulated_by"] == "tester"
    assert "evidence_package" not in dry_runs[0]


def test_dataset2_controlled_cleanup_dry_run_review_is_metadata_only(tmp_path, test_db):
    pack = _write_dataset2_pack(
        tmp_path,
        [
            _record(
                pattern_id="CONTROLLED_REVIEW_001",
                risk_level="medium_high",
                split_tag="train",
                observable_features=["['big_yang']", "high_volume"],
                evidence_summary="",
            ),
            _record(pattern_id="CONTROLLED_REVIEW_002", action_label="RISK_ALERT", risk_level="high", split_tag="test"),
        ],
    )
    service = Dataset2TrainingReadinessService()

    missing = service.staging_cleanup_execution_controlled_dry_run_review(
        controlled_dry_run_id=999999,
        reviewed_by="tester",
    )
    assert missing["status"] == "controlled_cleanup_dry_run_review_blocked_missing_dry_run"
    assert missing["decision"]["writes_existing_event_now"] is False
    assert missing["decision"]["controlled_cleanup_dry_run_review_accepted"] is False
    assert missing["decision"]["cleanup_executed_now"] is False
    assert missing["decision"]["training_started_now"] is False

    blocked_preflight = _cleanup_execution_plan_preflight_chain(service, pack, {}, suffix="blocked-review")
    blocked_dry_run = service.staging_cleanup_execution_controlled_dry_run(
        plan_preflight_id=blocked_preflight["event_id"],
        simulated_by="tester",
    )
    blocked_review = service.staging_cleanup_execution_controlled_dry_run_review(
        controlled_dry_run_id=blocked_dry_run["event_id"],
        reviewed_by="tester",
    )
    assert blocked_review["status"] == "controlled_cleanup_dry_run_review_blocked"
    assert blocked_review["decision"]["controlled_cleanup_dry_run_review_recorded"] is True
    assert blocked_review["decision"]["controlled_cleanup_dry_run_review_accepted"] is False
    assert blocked_review["decision"]["can_execute_cleanup_now"] is False
    assert blocked_review["decision"]["writes_learning_samples_now"] is False

    plan_preflight = _cleanup_execution_plan_preflight_chain(service, pack, _manual_evidence_package(), suffix="ready-review")
    controlled = service.staging_cleanup_execution_controlled_dry_run(
        plan_preflight_id=plan_preflight["event_id"],
        simulated_by="tester",
        dry_run_decision="simulated_for_controlled_cleanup_review",
    )
    review = service.staging_cleanup_execution_controlled_dry_run_review(
        controlled_dry_run_id=controlled["event_id"],
        reviewed_by="tester",
        review_decision="approved_for_controlled_cleanup_execution_review",
        note="metadata-only controlled cleanup review",
    )

    assert review["stage"] == "V5.6-P43"
    assert review["status"] == "controlled_cleanup_dry_run_review_accepted"
    assert isinstance(review["event_id"], int)
    assert review["controlled_dry_run_id"] == controlled["event_id"]
    assert review["plan_preflight_id"] == plan_preflight["event_id"]
    assert review["simulation_summary"]["lock_key"] == controlled["simulation"]["lock_key"]
    assert review["simulation_summary"]["automated_operation_count"] >= 1
    assert review["simulation_summary"]["manual_operation_count"] >= 1
    assert review["simulation_summary"]["simulated_mutation_count"] == controlled["simulation"]["simulated_mutation_count"]
    assert review["simulation_summary"]["contains_sql"] is False
    assert review["simulation_summary"]["contains_executable_code"] is False
    assert review["simulation_summary"]["can_execute_now"] is False
    assert review["simulation_summary"]["record_bodies_included"] is False
    assert review["simulation_summary"]["affected_rows_body_included"] is False
    assert review["simulation_summary"]["writes_staging_records_now"] is False
    assert review["simulation_summary"]["writes_learning_samples_now"] is False
    assert review["simulation_summary"]["mutates_staging_records_now"] is False
    assert review["decision"]["controlled_cleanup_dry_run_review_recorded"] is True
    assert review["decision"]["controlled_cleanup_dry_run_review_accepted"] is True
    assert review["decision"]["cleanup_execution_approved_now"] is False
    assert review["decision"]["cleanup_application_allowed_now"] is False
    assert review["decision"]["cleanup_executed_now"] is False
    assert review["decision"]["can_execute_cleanup_now"] is False
    assert review["decision"]["writes_staging_records_now"] is False
    assert review["decision"]["writes_learning_samples_now"] is False
    assert review["decision"]["mutates_staging_records_now"] is False
    assert review["decision"]["training_started_now"] is False
    assert review["decision"]["can_start_training_now"] is False
    assert "evidence_package" not in review
    assert "records" not in review["simulation_summary"]
    check_status = {check["name"]: check["status"] for check in review["checks"]}
    assert check_status["controlled_dry_run_ready_for_review"] == "passed"
    assert check_status["aggregate_simulation_present"] == "passed"
    assert check_status["cleanup_and_training_remain_blocked"] == "passed"

    reviews = service.list_staging_cleanup_execution_controlled_dry_run_reviews(limit=5)
    assert reviews[0]["id"] == review["event_id"]
    assert reviews[0]["review"]["reviewed_by"] == "tester"
    assert "evidence_package" not in reviews[0]


def test_dataset2_controlled_cleanup_execution_approval_is_metadata_only(tmp_path, test_db):
    pack = _write_dataset2_pack(
        tmp_path,
        [
            _record(
                pattern_id="CONTROLLED_APPROVAL_001",
                risk_level="medium_high",
                split_tag="train",
                observable_features=["['big_yang']", "high_volume"],
                evidence_summary="",
            ),
            _record(pattern_id="CONTROLLED_APPROVAL_002", action_label="RISK_ALERT", risk_level="high", split_tag="test"),
        ],
    )
    service = Dataset2TrainingReadinessService()

    missing = service.staging_cleanup_execution_controlled_approval(
        controlled_review_id=999999,
        approved_by="tester",
    )
    assert missing["status"] == "controlled_cleanup_execution_approval_blocked_missing_review"
    assert missing["decision"]["writes_existing_event_now"] is False
    assert missing["decision"]["controlled_cleanup_execution_approval_accepted"] is False
    assert missing["decision"]["cleanup_executed_now"] is False
    assert missing["decision"]["training_started_now"] is False

    blocked_preflight = _cleanup_execution_plan_preflight_chain(service, pack, {}, suffix="blocked-approval")
    blocked_dry_run = service.staging_cleanup_execution_controlled_dry_run(
        plan_preflight_id=blocked_preflight["event_id"],
        simulated_by="tester",
    )
    blocked_review = service.staging_cleanup_execution_controlled_dry_run_review(
        controlled_dry_run_id=blocked_dry_run["event_id"],
        reviewed_by="tester",
    )
    blocked_approval = service.staging_cleanup_execution_controlled_approval(
        controlled_review_id=blocked_review["event_id"],
        approved_by="tester",
    )
    assert blocked_approval["status"] == "controlled_cleanup_execution_approval_blocked"
    assert blocked_approval["decision"]["controlled_cleanup_execution_approval_recorded"] is True
    assert blocked_approval["decision"]["controlled_cleanup_execution_approval_accepted"] is False
    assert blocked_approval["decision"]["can_execute_cleanup_now"] is False
    assert blocked_approval["decision"]["writes_learning_samples_now"] is False

    plan_preflight = _cleanup_execution_plan_preflight_chain(service, pack, _manual_evidence_package(), suffix="ready-approval")
    controlled = service.staging_cleanup_execution_controlled_dry_run(
        plan_preflight_id=plan_preflight["event_id"],
        simulated_by="tester",
        dry_run_decision="simulated_for_controlled_cleanup_review",
    )
    review = service.staging_cleanup_execution_controlled_dry_run_review(
        controlled_dry_run_id=controlled["event_id"],
        reviewed_by="tester",
        review_decision="approved_for_controlled_cleanup_execution_review",
    )
    approval = service.staging_cleanup_execution_controlled_approval(
        controlled_review_id=review["event_id"],
        approved_by="tester",
        approval_decision="approved_for_controlled_cleanup_execution_preflight",
        note="metadata-only controlled cleanup approval",
    )

    assert approval["stage"] == "V5.6-P43"
    assert approval["status"] == "controlled_cleanup_execution_approval_ready_for_preflight"
    assert isinstance(approval["event_id"], int)
    assert approval["controlled_review_id"] == review["event_id"]
    assert approval["controlled_dry_run_id"] == controlled["event_id"]
    assert approval["approval_scope"]["lock_key"] == review["simulation_summary"]["lock_key"]
    assert approval["approval_scope"]["approval_scope"] == "controlled_cleanup_preflight_only"
    assert approval["approval_scope"]["requires_preflight"] is True
    assert approval["approval_scope"]["requires_transaction"] is True
    assert approval["approval_scope"]["requires_rollback"] is True
    assert approval["approval_scope"]["automated_operation_count"] >= 1
    assert approval["approval_scope"]["manual_operation_count"] >= 1
    assert approval["approval_scope"]["simulated_mutation_count"] == review["simulation_summary"]["simulated_mutation_count"]
    assert approval["approval_scope"]["contains_sql"] is False
    assert approval["approval_scope"]["contains_executable_code"] is False
    assert approval["approval_scope"]["can_execute_now"] is False
    assert approval["approval_scope"]["record_bodies_included"] is False
    assert approval["approval_scope"]["affected_rows_body_included"] is False
    assert approval["approval_scope"]["writes_staging_records_now"] is False
    assert approval["approval_scope"]["writes_learning_samples_now"] is False
    assert approval["approval_scope"]["mutates_staging_records_now"] is False
    assert approval["decision"]["controlled_cleanup_execution_approval_recorded"] is True
    assert approval["decision"]["controlled_cleanup_execution_approval_accepted"] is True
    assert approval["decision"]["controlled_cleanup_approved_for_future_preflight"] is True
    assert approval["decision"]["cleanup_execution_approved_now"] is False
    assert approval["decision"]["cleanup_application_allowed_now"] is False
    assert approval["decision"]["cleanup_executed_now"] is False
    assert approval["decision"]["can_execute_cleanup_now"] is False
    assert approval["decision"]["writes_staging_records_now"] is False
    assert approval["decision"]["writes_learning_samples_now"] is False
    assert approval["decision"]["mutates_staging_records_now"] is False
    assert approval["decision"]["training_started_now"] is False
    assert approval["decision"]["can_start_training_now"] is False
    assert "evidence_package" not in approval
    assert "records" not in approval["approval_scope"]
    check_status = {check["name"]: check["status"] for check in approval["checks"]}
    assert check_status["controlled_review_accepted"] == "passed"
    assert check_status["approval_scope_is_preflight_only"] == "passed"
    assert check_status["cleanup_and_training_remain_blocked"] == "passed"

    approvals = service.list_staging_cleanup_execution_controlled_approvals(limit=5)
    assert approvals[0]["id"] == approval["event_id"]
    assert approvals[0]["approval"]["approved_by"] == "tester"
    assert "evidence_package" not in approvals[0]


def test_dataset2_controlled_cleanup_execution_preflight_is_metadata_only(tmp_path, test_db):
    pack = _write_dataset2_pack(
        tmp_path,
        [
            _record(
                pattern_id="CONTROLLED_PREFLIGHT_001",
                risk_level="medium_high",
                split_tag="train",
                observable_features=["['big_yang']", "high_volume"],
                evidence_summary="",
            ),
            _record(pattern_id="CONTROLLED_PREFLIGHT_002", action_label="RISK_ALERT", risk_level="high", split_tag="test"),
        ],
    )
    service = Dataset2TrainingReadinessService()

    missing = service.staging_cleanup_execution_controlled_preflight(
        controlled_approval_id=999999,
        requested_by="tester",
    )
    assert missing["status"] == "controlled_cleanup_execution_preflight_blocked_missing_approval"
    assert missing["decision"]["writes_existing_event_now"] is False
    assert missing["decision"]["controlled_cleanup_execution_preflight_ready_for_apply_dry_run"] is False
    assert missing["decision"]["cleanup_executed_now"] is False
    assert missing["decision"]["training_started_now"] is False

    blocked_preflight_source = _cleanup_execution_plan_preflight_chain(service, pack, {}, suffix="blocked-controlled-preflight")
    blocked_dry_run = service.staging_cleanup_execution_controlled_dry_run(
        plan_preflight_id=blocked_preflight_source["event_id"],
        simulated_by="tester",
    )
    blocked_review = service.staging_cleanup_execution_controlled_dry_run_review(
        controlled_dry_run_id=blocked_dry_run["event_id"],
        reviewed_by="tester",
    )
    blocked_approval = service.staging_cleanup_execution_controlled_approval(
        controlled_review_id=blocked_review["event_id"],
        approved_by="tester",
    )
    blocked_preflight = service.staging_cleanup_execution_controlled_preflight(
        controlled_approval_id=blocked_approval["event_id"],
        requested_by="tester",
    )
    assert blocked_preflight["status"] == "controlled_cleanup_execution_preflight_blocked"
    assert blocked_preflight["decision"]["controlled_cleanup_execution_preflight_recorded"] is True
    assert blocked_preflight["decision"]["controlled_cleanup_execution_preflight_ready_for_apply_dry_run"] is False
    assert blocked_preflight["decision"]["can_execute_cleanup_now"] is False
    assert blocked_preflight["decision"]["writes_learning_samples_now"] is False

    plan_preflight = _cleanup_execution_plan_preflight_chain(service, pack, _manual_evidence_package(), suffix="ready-controlled-preflight")
    controlled = service.staging_cleanup_execution_controlled_dry_run(
        plan_preflight_id=plan_preflight["event_id"],
        simulated_by="tester",
        dry_run_decision="simulated_for_controlled_cleanup_review",
    )
    review = service.staging_cleanup_execution_controlled_dry_run_review(
        controlled_dry_run_id=controlled["event_id"],
        reviewed_by="tester",
        review_decision="approved_for_controlled_cleanup_execution_review",
    )
    approval = service.staging_cleanup_execution_controlled_approval(
        controlled_review_id=review["event_id"],
        approved_by="tester",
        approval_decision="approved_for_controlled_cleanup_execution_preflight",
    )
    preflight = service.staging_cleanup_execution_controlled_preflight(
        controlled_approval_id=approval["event_id"],
        requested_by="tester",
        preflight_decision="prepared_for_controlled_cleanup_execution_apply_dry_run",
        note="metadata-only controlled preflight",
    )

    assert preflight["stage"] == "V5.6-P43"
    assert preflight["status"] == "controlled_cleanup_execution_preflight_ready_for_apply_dry_run"
    assert isinstance(preflight["event_id"], int)
    assert preflight["controlled_approval_id"] == approval["event_id"]
    assert preflight["controlled_review_id"] == review["event_id"]
    assert preflight["preflight"]["lock_key"] == approval["approval_scope"]["lock_key"]
    assert preflight["preflight"]["staging_record_count"] == 2
    assert preflight["preflight"]["expected_staging_record_count_after"] == 2
    assert preflight["preflight"]["learning_sample_count"] == 0
    assert preflight["preflight"]["expected_learning_sample_count_after"] == 0
    assert preflight["preflight"]["automated_operation_count"] >= 1
    assert preflight["preflight"]["manual_operation_count"] >= 1
    assert preflight["preflight"]["transaction_required"] is True
    assert preflight["preflight"]["rollback_required"] is True
    assert preflight["preflight"]["allowed_tables"] == ["dataset2_staging_records"]
    assert "learning_samples" in preflight["preflight"]["forbidden_tables"]
    assert preflight["preflight"]["contains_sql"] is False
    assert preflight["preflight"]["contains_executable_code"] is False
    assert preflight["preflight"]["can_execute_now"] is False
    assert preflight["preflight"]["record_bodies_included"] is False
    assert preflight["preflight"]["writes_staging_records_now"] is False
    assert preflight["preflight"]["writes_learning_samples_now"] is False
    assert preflight["preflight"]["mutates_staging_records_now"] is False
    assert preflight["decision"]["controlled_cleanup_execution_preflight_recorded"] is True
    assert preflight["decision"]["controlled_cleanup_execution_preflight_ready_for_apply_dry_run"] is True
    assert preflight["decision"]["cleanup_execution_approved_now"] is False
    assert preflight["decision"]["cleanup_application_allowed_now"] is False
    assert preflight["decision"]["cleanup_executed_now"] is False
    assert preflight["decision"]["can_execute_cleanup_now"] is False
    assert preflight["decision"]["writes_staging_records_now"] is False
    assert preflight["decision"]["writes_learning_samples_now"] is False
    assert preflight["decision"]["mutates_staging_records_now"] is False
    assert preflight["decision"]["training_started_now"] is False
    assert preflight["decision"]["can_start_training_now"] is False
    assert "evidence_package" not in preflight
    assert "records" not in preflight["preflight"]
    check_status = {check["name"]: check["status"] for check in preflight["checks"]}
    assert check_status["controlled_approval_ready_for_preflight"] == "passed"
    assert check_status["staging_count_matches_approval"] == "passed"
    assert check_status["cleanup_and_training_remain_blocked"] == "passed"

    preflights = service.list_staging_cleanup_execution_controlled_preflights(limit=5)
    assert preflights[0]["id"] == preflight["event_id"]
    assert preflights[0]["request"]["requested_by"] == "tester"
    assert "evidence_package" not in preflights[0]


def test_dataset2_controlled_cleanup_apply_dry_run_is_aggregate_only(tmp_path, test_db):
    pack = _write_dataset2_pack(
        tmp_path,
        [
            _record(
                pattern_id="CONTROLLED_APPLY_DRY_RUN_001",
                risk_level="medium_high",
                split_tag="train",
                observable_features=["['big_yang']", "high_volume"],
                evidence_summary="",
            ),
            _record(pattern_id="CONTROLLED_APPLY_DRY_RUN_002", action_label="RISK_ALERT", risk_level="high", split_tag="test"),
        ],
    )
    service = Dataset2TrainingReadinessService()

    before_missing = service.list_staging_cleanup_execution_controlled_apply_dry_runs(limit=5)
    missing = service.staging_cleanup_execution_controlled_apply_dry_run(
        controlled_preflight_id=999999,
        simulated_by="tester",
    )
    after_missing = service.list_staging_cleanup_execution_controlled_apply_dry_runs(limit=5)
    assert missing["status"] == "controlled_cleanup_apply_dry_run_blocked_missing_preflight"
    assert missing["decision"]["writes_existing_event_now"] is False
    assert missing["decision"]["controlled_cleanup_apply_dry_run_ready_for_review"] is False
    assert missing["decision"]["cleanup_executed_now"] is False
    assert missing["decision"]["training_started_now"] is False
    assert len(after_missing) == len(before_missing)

    blocked_preflight_source = _cleanup_execution_plan_preflight_chain(service, pack, {}, suffix="blocked-apply-dry-run")
    blocked_controlled = service.staging_cleanup_execution_controlled_dry_run(
        plan_preflight_id=blocked_preflight_source["event_id"],
        simulated_by="tester",
    )
    blocked_review = service.staging_cleanup_execution_controlled_dry_run_review(
        controlled_dry_run_id=blocked_controlled["event_id"],
        reviewed_by="tester",
    )
    blocked_approval = service.staging_cleanup_execution_controlled_approval(
        controlled_review_id=blocked_review["event_id"],
        approved_by="tester",
    )
    blocked_preflight = service.staging_cleanup_execution_controlled_preflight(
        controlled_approval_id=blocked_approval["event_id"],
        requested_by="tester",
    )
    blocked_apply = service.staging_cleanup_execution_controlled_apply_dry_run(
        controlled_preflight_id=blocked_preflight["event_id"],
        simulated_by="tester",
    )
    assert blocked_apply["status"] == "controlled_cleanup_apply_dry_run_blocked"
    assert blocked_apply["decision"]["controlled_cleanup_apply_dry_run_recorded"] is True
    assert blocked_apply["decision"]["controlled_cleanup_apply_dry_run_ready_for_review"] is False
    assert blocked_apply["decision"]["can_execute_cleanup_now"] is False
    assert blocked_apply["decision"]["writes_learning_samples_now"] is False
    assert blocked_apply["simulation"]["contains_sql"] is False
    assert blocked_apply["simulation"]["contains_executable_code"] is False
    assert blocked_apply["simulation"]["record_bodies_included"] is False

    plan_preflight = _cleanup_execution_plan_preflight_chain(service, pack, _manual_evidence_package(), suffix="ready-apply-dry-run")
    controlled = service.staging_cleanup_execution_controlled_dry_run(
        plan_preflight_id=plan_preflight["event_id"],
        simulated_by="tester",
        dry_run_decision="simulated_for_controlled_cleanup_review",
    )
    review = service.staging_cleanup_execution_controlled_dry_run_review(
        controlled_dry_run_id=controlled["event_id"],
        reviewed_by="tester",
        review_decision="approved_for_controlled_cleanup_execution_review",
    )
    approval = service.staging_cleanup_execution_controlled_approval(
        controlled_review_id=review["event_id"],
        approved_by="tester",
        approval_decision="approved_for_controlled_cleanup_execution_preflight",
    )
    preflight = service.staging_cleanup_execution_controlled_preflight(
        controlled_approval_id=approval["event_id"],
        requested_by="tester",
        preflight_decision="prepared_for_controlled_cleanup_execution_apply_dry_run",
    )
    apply_dry_run = service.staging_cleanup_execution_controlled_apply_dry_run(
        controlled_preflight_id=preflight["event_id"],
        simulated_by="tester",
        dry_run_decision="simulated_for_controlled_cleanup_apply_review",
        note="aggregate-only controlled apply dry-run",
    )

    assert apply_dry_run["stage"] == "V5.6-P43"
    assert apply_dry_run["status"] == "controlled_cleanup_apply_dry_run_ready_for_review"
    assert isinstance(apply_dry_run["event_id"], int)
    assert apply_dry_run["controlled_preflight_id"] == preflight["event_id"]
    assert apply_dry_run["controlled_approval_id"] == approval["event_id"]
    assert apply_dry_run["controlled_review_id"] == review["event_id"]
    assert apply_dry_run["simulation"]["lock_key"] == preflight["preflight"]["lock_key"]
    assert apply_dry_run["simulation"]["staging_record_count_before"] == 2
    assert apply_dry_run["simulation"]["expected_staging_record_count_after"] == 2
    assert apply_dry_run["simulation"]["preflight_staging_record_count"] == 2
    assert apply_dry_run["simulation"]["staging_count_still_matches"] is True
    assert apply_dry_run["simulation"]["learning_sample_count_before"] == 0
    assert apply_dry_run["simulation"]["expected_learning_sample_count_after"] == 0
    assert apply_dry_run["simulation"]["automated_operation_count"] >= 1
    assert apply_dry_run["simulation"]["manual_operation_count"] >= 1
    assert apply_dry_run["simulation"]["records_with_operations"] >= 1
    assert apply_dry_run["simulation"]["records_with_quality_flags"] >= 1
    assert apply_dry_run["simulation"]["operation_counts"]
    assert apply_dry_run["simulation"]["field_counts"]
    assert apply_dry_run["simulation"]["quality_flag_counts"]
    assert apply_dry_run["simulation"]["simulated_mutation_count"] == apply_dry_run["simulation"]["automated_operation_count"]
    assert apply_dry_run["simulation"]["simulated_quality_flag_reduction_count"] == apply_dry_run["simulation"]["automated_operation_count"]
    assert apply_dry_run["simulation"]["simulated_manual_flag_remaining_count"] == apply_dry_run["simulation"]["manual_operation_count"]
    assert apply_dry_run["simulation"]["transaction_required"] is True
    assert apply_dry_run["simulation"]["rollback_required"] is True
    assert apply_dry_run["simulation"]["allowed_tables"] == ["dataset2_staging_records"]
    assert "learning_samples" in apply_dry_run["simulation"]["forbidden_tables"]
    assert apply_dry_run["simulation"]["contains_sql"] is False
    assert apply_dry_run["simulation"]["contains_executable_code"] is False
    assert apply_dry_run["simulation"]["can_execute_now"] is False
    assert apply_dry_run["simulation"]["record_bodies_included"] is False
    assert apply_dry_run["simulation"]["affected_rows_body_included"] is False
    assert apply_dry_run["simulation"]["writes_staging_records_now"] is False
    assert apply_dry_run["simulation"]["writes_learning_samples_now"] is False
    assert apply_dry_run["simulation"]["mutates_staging_records_now"] is False
    assert apply_dry_run["decision"]["controlled_cleanup_apply_dry_run_recorded"] is True
    assert apply_dry_run["decision"]["controlled_cleanup_apply_dry_run_ready_for_review"] is True
    assert apply_dry_run["decision"]["cleanup_execution_approved_now"] is False
    assert apply_dry_run["decision"]["cleanup_application_allowed_now"] is False
    assert apply_dry_run["decision"]["cleanup_executed_now"] is False
    assert apply_dry_run["decision"]["can_execute_cleanup_now"] is False
    assert apply_dry_run["decision"]["writes_staging_records_now"] is False
    assert apply_dry_run["decision"]["writes_learning_samples_now"] is False
    assert apply_dry_run["decision"]["mutates_staging_records_now"] is False
    assert apply_dry_run["decision"]["training_started_now"] is False
    assert apply_dry_run["decision"]["can_start_training_now"] is False
    assert "evidence_package" not in apply_dry_run
    assert "records" not in apply_dry_run["simulation"]
    check_status = {check["name"]: check["status"] for check in apply_dry_run["checks"]}
    assert check_status["controlled_preflight_ready_for_apply_dry_run"] == "passed"
    assert check_status["apply_simulation_scope_present"] == "passed"
    assert check_status["manual_backfill_separated"] == "warning"
    assert check_status["cleanup_and_training_remain_blocked"] == "passed"

    apply_dry_runs = service.list_staging_cleanup_execution_controlled_apply_dry_runs(limit=5)
    assert apply_dry_runs[0]["id"] == apply_dry_run["event_id"]
    assert apply_dry_runs[0]["dry_run"]["simulated_by"] == "tester"
    assert "evidence_package" not in apply_dry_runs[0]


def test_dataset2_controlled_cleanup_apply_dry_run_review_is_metadata_only(tmp_path, test_db):
    pack = _write_dataset2_pack(
        tmp_path,
        [
            _record(
                pattern_id="CONTROLLED_APPLY_REVIEW_001",
                risk_level="medium_high",
                split_tag="train",
                observable_features=["['big_yang']", "high_volume"],
                evidence_summary="",
            ),
            _record(pattern_id="CONTROLLED_APPLY_REVIEW_002", action_label="RISK_ALERT", risk_level="high", split_tag="test"),
        ],
    )
    service = Dataset2TrainingReadinessService()

    before_missing = service.list_staging_cleanup_execution_controlled_apply_dry_run_reviews(limit=5)
    missing = service.staging_cleanup_execution_controlled_apply_dry_run_review(
        apply_dry_run_id=999999,
        reviewed_by="tester",
    )
    after_missing = service.list_staging_cleanup_execution_controlled_apply_dry_run_reviews(limit=5)
    assert missing["status"] == "controlled_cleanup_apply_dry_run_review_blocked_missing_dry_run"
    assert missing["decision"]["writes_existing_event_now"] is False
    assert missing["decision"]["controlled_cleanup_apply_dry_run_review_accepted"] is False
    assert missing["decision"]["cleanup_executed_now"] is False
    assert missing["decision"]["training_started_now"] is False
    assert len(after_missing) == len(before_missing)

    blocked_preflight_source = _cleanup_execution_plan_preflight_chain(service, pack, {}, suffix="blocked-apply-review")
    blocked_controlled = service.staging_cleanup_execution_controlled_dry_run(
        plan_preflight_id=blocked_preflight_source["event_id"],
        simulated_by="tester",
    )
    blocked_review = service.staging_cleanup_execution_controlled_dry_run_review(
        controlled_dry_run_id=blocked_controlled["event_id"],
        reviewed_by="tester",
    )
    blocked_approval = service.staging_cleanup_execution_controlled_approval(
        controlled_review_id=blocked_review["event_id"],
        approved_by="tester",
    )
    blocked_preflight = service.staging_cleanup_execution_controlled_preflight(
        controlled_approval_id=blocked_approval["event_id"],
        requested_by="tester",
    )
    blocked_apply = service.staging_cleanup_execution_controlled_apply_dry_run(
        controlled_preflight_id=blocked_preflight["event_id"],
        simulated_by="tester",
    )
    blocked_apply_review = service.staging_cleanup_execution_controlled_apply_dry_run_review(
        apply_dry_run_id=blocked_apply["event_id"],
        reviewed_by="tester",
    )
    assert blocked_apply_review["status"] == "controlled_cleanup_apply_dry_run_review_blocked"
    assert blocked_apply_review["decision"]["controlled_cleanup_apply_dry_run_review_recorded"] is True
    assert blocked_apply_review["decision"]["controlled_cleanup_apply_dry_run_review_accepted"] is False
    assert blocked_apply_review["decision"]["can_execute_cleanup_now"] is False
    assert blocked_apply_review["decision"]["writes_learning_samples_now"] is False
    assert blocked_apply_review["simulation_summary"]["contains_sql"] is False
    assert blocked_apply_review["simulation_summary"]["record_bodies_included"] is False

    plan_preflight = _cleanup_execution_plan_preflight_chain(service, pack, _manual_evidence_package(), suffix="ready-apply-review")
    controlled = service.staging_cleanup_execution_controlled_dry_run(
        plan_preflight_id=plan_preflight["event_id"],
        simulated_by="tester",
        dry_run_decision="simulated_for_controlled_cleanup_review",
    )
    review = service.staging_cleanup_execution_controlled_dry_run_review(
        controlled_dry_run_id=controlled["event_id"],
        reviewed_by="tester",
        review_decision="approved_for_controlled_cleanup_execution_review",
    )
    approval = service.staging_cleanup_execution_controlled_approval(
        controlled_review_id=review["event_id"],
        approved_by="tester",
        approval_decision="approved_for_controlled_cleanup_execution_preflight",
    )
    preflight = service.staging_cleanup_execution_controlled_preflight(
        controlled_approval_id=approval["event_id"],
        requested_by="tester",
        preflight_decision="prepared_for_controlled_cleanup_execution_apply_dry_run",
    )
    apply_dry_run = service.staging_cleanup_execution_controlled_apply_dry_run(
        controlled_preflight_id=preflight["event_id"],
        simulated_by="tester",
        dry_run_decision="simulated_for_controlled_cleanup_apply_review",
    )
    apply_review = service.staging_cleanup_execution_controlled_apply_dry_run_review(
        apply_dry_run_id=apply_dry_run["event_id"],
        reviewed_by="tester",
        review_decision="approved_for_controlled_cleanup_apply_execution_review",
        note="metadata-only apply dry-run review",
    )

    assert apply_review["stage"] == "V5.6-P43"
    assert apply_review["status"] == "controlled_cleanup_apply_dry_run_review_accepted"
    assert isinstance(apply_review["event_id"], int)
    assert apply_review["apply_dry_run_id"] == apply_dry_run["event_id"]
    assert apply_review["controlled_preflight_id"] == preflight["event_id"]
    assert apply_review["controlled_approval_id"] == approval["event_id"]
    assert apply_review["simulation_summary"]["lock_key"] == apply_dry_run["simulation"]["lock_key"]
    assert apply_review["simulation_summary"]["staging_record_count_before"] == 2
    assert apply_review["simulation_summary"]["expected_staging_record_count_after"] == 2
    assert apply_review["simulation_summary"]["learning_sample_count_before"] == 0
    assert apply_review["simulation_summary"]["expected_learning_sample_count_after"] == 0
    assert apply_review["simulation_summary"]["automated_operation_count"] >= 1
    assert apply_review["simulation_summary"]["manual_operation_count"] >= 1
    assert apply_review["simulation_summary"]["simulated_mutation_count"] == apply_dry_run["simulation"]["simulated_mutation_count"]
    assert apply_review["simulation_summary"]["contains_sql"] is False
    assert apply_review["simulation_summary"]["contains_executable_code"] is False
    assert apply_review["simulation_summary"]["can_execute_now"] is False
    assert apply_review["simulation_summary"]["record_bodies_included"] is False
    assert apply_review["simulation_summary"]["affected_rows_body_included"] is False
    assert apply_review["simulation_summary"]["writes_staging_records_now"] is False
    assert apply_review["simulation_summary"]["writes_learning_samples_now"] is False
    assert apply_review["simulation_summary"]["mutates_staging_records_now"] is False
    assert apply_review["decision"]["controlled_cleanup_apply_dry_run_review_recorded"] is True
    assert apply_review["decision"]["controlled_cleanup_apply_dry_run_review_accepted"] is True
    assert apply_review["decision"]["cleanup_execution_approved_now"] is False
    assert apply_review["decision"]["cleanup_application_allowed_now"] is False
    assert apply_review["decision"]["cleanup_executed_now"] is False
    assert apply_review["decision"]["can_execute_cleanup_now"] is False
    assert apply_review["decision"]["writes_staging_records_now"] is False
    assert apply_review["decision"]["writes_learning_samples_now"] is False
    assert apply_review["decision"]["mutates_staging_records_now"] is False
    assert apply_review["decision"]["training_started_now"] is False
    assert apply_review["decision"]["can_start_training_now"] is False
    assert "evidence_package" not in apply_review
    assert "records" not in apply_review["simulation_summary"]
    check_status = {check["name"]: check["status"] for check in apply_review["checks"]}
    assert check_status["apply_dry_run_ready_for_review"] == "passed"
    assert check_status["aggregate_apply_simulation_present"] == "passed"
    assert check_status["cleanup_and_training_remain_blocked"] == "passed"

    apply_reviews = service.list_staging_cleanup_execution_controlled_apply_dry_run_reviews(limit=5)
    assert apply_reviews[0]["id"] == apply_review["event_id"]
    assert apply_reviews[0]["review"]["reviewed_by"] == "tester"
    assert "evidence_package" not in apply_reviews[0]


def test_dataset2_controlled_cleanup_apply_approval_is_metadata_only(tmp_path, test_db):
    pack = _write_dataset2_pack(
        tmp_path,
        [
            _record(
                pattern_id="CONTROLLED_APPLY_APPROVAL_001",
                risk_level="medium_high",
                split_tag="train",
                observable_features=["['big_yang']", "high_volume"],
                evidence_summary="",
            ),
            _record(pattern_id="CONTROLLED_APPLY_APPROVAL_002", action_label="RISK_ALERT", risk_level="high", split_tag="test"),
        ],
    )
    service = Dataset2TrainingReadinessService()

    before_missing = service.list_staging_cleanup_execution_controlled_apply_approvals(limit=5)
    missing = service.staging_cleanup_execution_controlled_apply_approval(
        apply_review_id=999999,
        approved_by="tester",
    )
    after_missing = service.list_staging_cleanup_execution_controlled_apply_approvals(limit=5)
    assert missing["status"] == "controlled_cleanup_apply_execution_approval_blocked_missing_review"
    assert missing["decision"]["writes_existing_event_now"] is False
    assert missing["decision"]["controlled_cleanup_apply_execution_approval_accepted"] is False
    assert missing["decision"]["cleanup_executed_now"] is False
    assert missing["decision"]["training_started_now"] is False
    assert len(after_missing) == len(before_missing)

    blocked_preflight_source = _cleanup_execution_plan_preflight_chain(service, pack, {}, suffix="blocked-apply-approval")
    blocked_controlled = service.staging_cleanup_execution_controlled_dry_run(
        plan_preflight_id=blocked_preflight_source["event_id"],
        simulated_by="tester",
    )
    blocked_review = service.staging_cleanup_execution_controlled_dry_run_review(
        controlled_dry_run_id=blocked_controlled["event_id"],
        reviewed_by="tester",
    )
    blocked_approval = service.staging_cleanup_execution_controlled_approval(
        controlled_review_id=blocked_review["event_id"],
        approved_by="tester",
    )
    blocked_preflight = service.staging_cleanup_execution_controlled_preflight(
        controlled_approval_id=blocked_approval["event_id"],
        requested_by="tester",
    )
    blocked_apply = service.staging_cleanup_execution_controlled_apply_dry_run(
        controlled_preflight_id=blocked_preflight["event_id"],
        simulated_by="tester",
    )
    blocked_apply_review = service.staging_cleanup_execution_controlled_apply_dry_run_review(
        apply_dry_run_id=blocked_apply["event_id"],
        reviewed_by="tester",
    )
    blocked_apply_approval = service.staging_cleanup_execution_controlled_apply_approval(
        apply_review_id=blocked_apply_review["event_id"],
        approved_by="tester",
    )
    assert blocked_apply_approval["status"] == "controlled_cleanup_apply_execution_approval_blocked"
    assert blocked_apply_approval["decision"]["controlled_cleanup_apply_execution_approval_recorded"] is True
    assert blocked_apply_approval["decision"]["controlled_cleanup_apply_execution_approval_accepted"] is False
    assert blocked_apply_approval["decision"]["can_execute_cleanup_now"] is False
    assert blocked_apply_approval["decision"]["writes_learning_samples_now"] is False
    assert blocked_apply_approval["approval_scope"]["contains_sql"] is False
    assert blocked_apply_approval["approval_scope"]["record_bodies_included"] is False

    plan_preflight = _cleanup_execution_plan_preflight_chain(service, pack, _manual_evidence_package(), suffix="ready-apply-approval")
    controlled = service.staging_cleanup_execution_controlled_dry_run(
        plan_preflight_id=plan_preflight["event_id"],
        simulated_by="tester",
        dry_run_decision="simulated_for_controlled_cleanup_review",
    )
    review = service.staging_cleanup_execution_controlled_dry_run_review(
        controlled_dry_run_id=controlled["event_id"],
        reviewed_by="tester",
        review_decision="approved_for_controlled_cleanup_execution_review",
    )
    approval = service.staging_cleanup_execution_controlled_approval(
        controlled_review_id=review["event_id"],
        approved_by="tester",
        approval_decision="approved_for_controlled_cleanup_execution_preflight",
    )
    preflight = service.staging_cleanup_execution_controlled_preflight(
        controlled_approval_id=approval["event_id"],
        requested_by="tester",
        preflight_decision="prepared_for_controlled_cleanup_execution_apply_dry_run",
    )
    apply_dry_run = service.staging_cleanup_execution_controlled_apply_dry_run(
        controlled_preflight_id=preflight["event_id"],
        simulated_by="tester",
        dry_run_decision="simulated_for_controlled_cleanup_apply_review",
    )
    apply_review = service.staging_cleanup_execution_controlled_apply_dry_run_review(
        apply_dry_run_id=apply_dry_run["event_id"],
        reviewed_by="tester",
        review_decision="approved_for_controlled_cleanup_apply_execution_review",
    )
    apply_approval = service.staging_cleanup_execution_controlled_apply_approval(
        apply_review_id=apply_review["event_id"],
        approved_by="tester",
        approval_decision="approved_for_controlled_cleanup_apply_execution_preflight",
        note="metadata-only apply execution approval",
    )

    assert apply_approval["stage"] == "V5.6-P43"
    assert apply_approval["status"] == "controlled_cleanup_apply_execution_approval_ready_for_preflight"
    assert isinstance(apply_approval["event_id"], int)
    assert apply_approval["apply_review_id"] == apply_review["event_id"]
    assert apply_approval["apply_dry_run_id"] == apply_dry_run["event_id"]
    assert apply_approval["controlled_preflight_id"] == preflight["event_id"]
    assert apply_approval["approval_scope"]["lock_key"] == apply_review["simulation_summary"]["lock_key"]
    assert apply_approval["approval_scope"]["approval_scope"] == "controlled_apply_preflight_only"
    assert apply_approval["approval_scope"]["allowed_next_stage"] == "controlled_cleanup_apply_execution_preflight"
    assert apply_approval["approval_scope"]["requires_preflight"] is True
    assert apply_approval["approval_scope"]["requires_transaction"] is True
    assert apply_approval["approval_scope"]["requires_rollback"] is True
    assert apply_approval["approval_scope"]["automated_operation_count"] >= 1
    assert apply_approval["approval_scope"]["manual_operation_count"] >= 1
    assert apply_approval["approval_scope"]["simulated_mutation_count"] == apply_review["simulation_summary"]["simulated_mutation_count"]
    assert apply_approval["approval_scope"]["allowed_tables"] == ["dataset2_staging_records"]
    assert "learning_samples" in apply_approval["approval_scope"]["forbidden_tables"]
    assert apply_approval["approval_scope"]["contains_sql"] is False
    assert apply_approval["approval_scope"]["contains_executable_code"] is False
    assert apply_approval["approval_scope"]["can_execute_now"] is False
    assert apply_approval["approval_scope"]["record_bodies_included"] is False
    assert apply_approval["approval_scope"]["affected_rows_body_included"] is False
    assert apply_approval["approval_scope"]["writes_staging_records_now"] is False
    assert apply_approval["approval_scope"]["writes_learning_samples_now"] is False
    assert apply_approval["approval_scope"]["mutates_staging_records_now"] is False
    assert apply_approval["decision"]["controlled_cleanup_apply_execution_approval_recorded"] is True
    assert apply_approval["decision"]["controlled_cleanup_apply_execution_approval_accepted"] is True
    assert apply_approval["decision"]["controlled_cleanup_apply_approved_for_future_preflight"] is True
    assert apply_approval["decision"]["can_generate_controlled_cleanup_apply_execution_preflight_now"] is True
    assert apply_approval["decision"]["cleanup_execution_approved_now"] is False
    assert apply_approval["decision"]["cleanup_application_allowed_now"] is False
    assert apply_approval["decision"]["cleanup_executed_now"] is False
    assert apply_approval["decision"]["can_execute_cleanup_now"] is False
    assert apply_approval["decision"]["writes_staging_records_now"] is False
    assert apply_approval["decision"]["writes_learning_samples_now"] is False
    assert apply_approval["decision"]["mutates_staging_records_now"] is False
    assert apply_approval["decision"]["training_started_now"] is False
    assert apply_approval["decision"]["can_start_training_now"] is False
    assert "evidence_package" not in apply_approval
    assert "records" not in apply_approval["approval_scope"]
    check_status = {check["name"]: check["status"] for check in apply_approval["checks"]}
    assert check_status["apply_review_accepted_for_approval"] == "passed"
    assert check_status["approval_scope_is_preflight_only"] == "passed"
    assert check_status["cleanup_and_training_remain_blocked"] == "passed"

    apply_approvals = service.list_staging_cleanup_execution_controlled_apply_approvals(limit=5)
    assert apply_approvals[0]["id"] == apply_approval["event_id"]
    assert apply_approvals[0]["approval"]["approved_by"] == "tester"
    assert "evidence_package" not in apply_approvals[0]


def test_dataset2_controlled_cleanup_apply_preflight_is_metadata_only(tmp_path, test_db):
    pack = _write_dataset2_pack(
        tmp_path,
        [
            _record(
                pattern_id="CONTROLLED_APPLY_PREFLIGHT_001",
                risk_level="medium_high",
                split_tag="train",
                observable_features=["['big_yang']", "high_volume"],
                evidence_summary="",
            ),
            _record(
                pattern_id="CONTROLLED_APPLY_PREFLIGHT_002",
                action_label="RISK_ALERT",
                risk_level="high",
                split_tag="test",
            ),
        ],
    )
    service = Dataset2TrainingReadinessService()

    before_missing = service.list_staging_cleanup_execution_controlled_apply_preflights(limit=5)
    missing = service.staging_cleanup_execution_controlled_apply_preflight(
        apply_approval_id=999999,
        requested_by="tester",
    )
    after_missing = service.list_staging_cleanup_execution_controlled_apply_preflights(limit=5)
    assert missing["status"] == "controlled_cleanup_apply_execution_preflight_blocked_missing_approval"
    assert missing["decision"]["writes_existing_event_now"] is False
    assert missing["decision"]["controlled_cleanup_apply_execution_preflight_ready_for_dry_run"] is False
    assert missing["decision"]["can_execute_cleanup_now"] is False
    assert missing["decision"]["training_started_now"] is False
    assert len(after_missing) == len(before_missing)

    blocked_preflight_source = _cleanup_execution_plan_preflight_chain(service, pack, {}, suffix="blocked-apply-preflight")
    blocked_controlled = service.staging_cleanup_execution_controlled_dry_run(
        plan_preflight_id=blocked_preflight_source["event_id"],
        simulated_by="tester",
    )
    blocked_review = service.staging_cleanup_execution_controlled_dry_run_review(
        controlled_dry_run_id=blocked_controlled["event_id"],
        reviewed_by="tester",
    )
    blocked_approval = service.staging_cleanup_execution_controlled_approval(
        controlled_review_id=blocked_review["event_id"],
        approved_by="tester",
    )
    blocked_preflight = service.staging_cleanup_execution_controlled_preflight(
        controlled_approval_id=blocked_approval["event_id"],
        requested_by="tester",
    )
    blocked_apply = service.staging_cleanup_execution_controlled_apply_dry_run(
        controlled_preflight_id=blocked_preflight["event_id"],
        simulated_by="tester",
    )
    blocked_apply_review = service.staging_cleanup_execution_controlled_apply_dry_run_review(
        apply_dry_run_id=blocked_apply["event_id"],
        reviewed_by="tester",
    )
    blocked_apply_approval = service.staging_cleanup_execution_controlled_apply_approval(
        apply_review_id=blocked_apply_review["event_id"],
        approved_by="tester",
    )
    blocked_apply_preflight = service.staging_cleanup_execution_controlled_apply_preflight(
        apply_approval_id=blocked_apply_approval["event_id"],
        requested_by="tester",
    )
    assert blocked_apply_preflight["status"] == "controlled_cleanup_apply_execution_preflight_blocked"
    assert blocked_apply_preflight["decision"]["controlled_cleanup_apply_execution_preflight_recorded"] is True
    assert blocked_apply_preflight["decision"]["controlled_cleanup_apply_execution_preflight_ready_for_dry_run"] is False
    assert blocked_apply_preflight["decision"]["can_execute_cleanup_now"] is False
    assert blocked_apply_preflight["decision"]["writes_learning_samples_now"] is False
    assert blocked_apply_preflight["preflight"]["contains_sql"] is False
    assert blocked_apply_preflight["preflight"]["record_bodies_included"] is False

    plan_preflight = _cleanup_execution_plan_preflight_chain(
        service,
        pack,
        _manual_evidence_package(),
        suffix="ready-apply-preflight",
    )
    controlled = service.staging_cleanup_execution_controlled_dry_run(
        plan_preflight_id=plan_preflight["event_id"],
        simulated_by="tester",
        dry_run_decision="simulated_for_controlled_cleanup_review",
    )
    review = service.staging_cleanup_execution_controlled_dry_run_review(
        controlled_dry_run_id=controlled["event_id"],
        reviewed_by="tester",
        review_decision="approved_for_controlled_cleanup_execution_review",
    )
    approval = service.staging_cleanup_execution_controlled_approval(
        controlled_review_id=review["event_id"],
        approved_by="tester",
        approval_decision="approved_for_controlled_cleanup_execution_preflight",
    )
    preflight = service.staging_cleanup_execution_controlled_preflight(
        controlled_approval_id=approval["event_id"],
        requested_by="tester",
        preflight_decision="prepared_for_controlled_cleanup_execution_apply_dry_run",
    )
    apply_dry_run = service.staging_cleanup_execution_controlled_apply_dry_run(
        controlled_preflight_id=preflight["event_id"],
        simulated_by="tester",
        dry_run_decision="simulated_for_controlled_cleanup_apply_review",
    )
    apply_review = service.staging_cleanup_execution_controlled_apply_dry_run_review(
        apply_dry_run_id=apply_dry_run["event_id"],
        reviewed_by="tester",
        review_decision="approved_for_controlled_cleanup_apply_execution_review",
    )
    apply_approval = service.staging_cleanup_execution_controlled_apply_approval(
        apply_review_id=apply_review["event_id"],
        approved_by="tester",
        approval_decision="approved_for_controlled_cleanup_apply_execution_preflight",
    )
    apply_preflight = service.staging_cleanup_execution_controlled_apply_preflight(
        apply_approval_id=apply_approval["event_id"],
        requested_by="tester",
        preflight_decision="prepared_for_controlled_cleanup_apply_execution_dry_run",
        note="metadata-only apply execution preflight",
    )

    assert apply_preflight["stage"] == "V5.6-P43"
    assert apply_preflight["status"] == "controlled_cleanup_apply_execution_preflight_ready_for_dry_run"
    assert isinstance(apply_preflight["event_id"], int)
    assert apply_preflight["apply_approval_id"] == apply_approval["event_id"]
    assert apply_preflight["apply_review_id"] == apply_review["event_id"]
    assert apply_preflight["apply_dry_run_id"] == apply_dry_run["event_id"]
    assert apply_preflight["controlled_preflight_id"] == preflight["event_id"]
    assert apply_preflight["preflight"]["lock_key"] == apply_approval["approval_scope"]["lock_key"]
    assert apply_preflight["preflight"]["staging_record_count"] == 2
    assert apply_preflight["preflight"]["expected_staging_record_count_after"] == 2
    assert apply_preflight["preflight"]["approved_staging_record_count"] == 2
    assert apply_preflight["preflight"]["learning_sample_count"] == 0
    assert apply_preflight["preflight"]["expected_learning_sample_count_after"] == 0
    assert apply_preflight["preflight"]["automated_operation_count"] >= 1
    assert apply_preflight["preflight"]["manual_operation_count"] >= 1
    assert apply_preflight["preflight"]["simulated_mutation_count"] == apply_approval["approval_scope"]["simulated_mutation_count"]
    assert apply_preflight["preflight"]["transaction_required"] is True
    assert apply_preflight["preflight"]["rollback_required"] is True
    assert apply_preflight["preflight"]["allowed_tables"] == ["dataset2_staging_records"]
    assert "learning_samples" in apply_preflight["preflight"]["forbidden_tables"]
    assert apply_preflight["preflight"]["allowed_next_stage"] == "controlled_cleanup_apply_execution_dry_run"
    assert apply_preflight["preflight"]["contains_sql"] is False
    assert apply_preflight["preflight"]["contains_executable_code"] is False
    assert apply_preflight["preflight"]["can_execute_now"] is False
    assert apply_preflight["preflight"]["record_bodies_included"] is False
    assert apply_preflight["preflight"]["affected_rows_body_included"] is False
    assert apply_preflight["preflight"]["writes_staging_records_now"] is False
    assert apply_preflight["preflight"]["writes_learning_samples_now"] is False
    assert apply_preflight["preflight"]["mutates_staging_records_now"] is False
    assert apply_preflight["decision"]["controlled_cleanup_apply_execution_preflight_recorded"] is True
    assert apply_preflight["decision"]["controlled_cleanup_apply_execution_preflight_ready_for_dry_run"] is True
    assert apply_preflight["decision"]["cleanup_execution_approved_now"] is False
    assert apply_preflight["decision"]["cleanup_application_allowed_now"] is False
    assert apply_preflight["decision"]["cleanup_executed_now"] is False
    assert apply_preflight["decision"]["can_execute_cleanup_now"] is False
    assert apply_preflight["decision"]["writes_staging_records_now"] is False
    assert apply_preflight["decision"]["writes_learning_samples_now"] is False
    assert apply_preflight["decision"]["mutates_staging_records_now"] is False
    assert apply_preflight["decision"]["training_started_now"] is False
    assert apply_preflight["decision"]["can_start_training_now"] is False
    assert "evidence_package" not in apply_preflight
    assert "records" not in apply_preflight["preflight"]
    check_status = {check["name"]: check["status"] for check in apply_preflight["checks"]}
    assert check_status["apply_approval_ready_for_preflight"] == "passed"
    assert check_status["staging_count_matches_approval"] == "passed"
    assert check_status["cleanup_and_training_remain_blocked"] == "passed"

    apply_preflights = service.list_staging_cleanup_execution_controlled_apply_preflights(limit=5)
    assert apply_preflights[0]["id"] == apply_preflight["event_id"]
    assert apply_preflights[0]["request"]["requested_by"] == "tester"
    assert "evidence_package" not in apply_preflights[0]


def test_dataset2_controlled_cleanup_apply_execution_dry_run_is_aggregate_only(tmp_path, test_db):
    pack = _write_dataset2_pack(
        tmp_path,
        [
            _record(
                pattern_id="CONTROLLED_APPLY_EXECUTION_DRY_RUN_001",
                risk_level="medium_high",
                split_tag="train",
                observable_features=["['big_yang']", "high_volume"],
                evidence_summary="",
            ),
            _record(
                pattern_id="CONTROLLED_APPLY_EXECUTION_DRY_RUN_002",
                action_label="RISK_ALERT",
                risk_level="high",
                split_tag="test",
            ),
        ],
    )
    service = Dataset2TrainingReadinessService()

    before_missing = service.list_staging_cleanup_execution_controlled_apply_execution_dry_runs(limit=5)
    missing = service.staging_cleanup_execution_controlled_apply_execution_dry_run(
        apply_preflight_id=999999,
        simulated_by="tester",
    )
    after_missing = service.list_staging_cleanup_execution_controlled_apply_execution_dry_runs(limit=5)
    assert missing["status"] == "controlled_cleanup_apply_execution_dry_run_blocked_missing_preflight"
    assert missing["decision"]["writes_existing_event_now"] is False
    assert missing["decision"]["controlled_cleanup_apply_execution_dry_run_ready_for_review"] is False
    assert missing["decision"]["cleanup_executed_now"] is False
    assert missing["decision"]["training_started_now"] is False
    assert len(after_missing) == len(before_missing)

    blocked_preflight_source = _cleanup_execution_plan_preflight_chain(
        service,
        pack,
        {},
        suffix="blocked-apply-execution-dry-run",
    )
    blocked_controlled = service.staging_cleanup_execution_controlled_dry_run(
        plan_preflight_id=blocked_preflight_source["event_id"],
        simulated_by="tester",
    )
    blocked_review = service.staging_cleanup_execution_controlled_dry_run_review(
        controlled_dry_run_id=blocked_controlled["event_id"],
        reviewed_by="tester",
    )
    blocked_approval = service.staging_cleanup_execution_controlled_approval(
        controlled_review_id=blocked_review["event_id"],
        approved_by="tester",
    )
    blocked_preflight = service.staging_cleanup_execution_controlled_preflight(
        controlled_approval_id=blocked_approval["event_id"],
        requested_by="tester",
    )
    blocked_apply = service.staging_cleanup_execution_controlled_apply_dry_run(
        controlled_preflight_id=blocked_preflight["event_id"],
        simulated_by="tester",
    )
    blocked_apply_review = service.staging_cleanup_execution_controlled_apply_dry_run_review(
        apply_dry_run_id=blocked_apply["event_id"],
        reviewed_by="tester",
    )
    blocked_apply_approval = service.staging_cleanup_execution_controlled_apply_approval(
        apply_review_id=blocked_apply_review["event_id"],
        approved_by="tester",
    )
    blocked_apply_preflight = service.staging_cleanup_execution_controlled_apply_preflight(
        apply_approval_id=blocked_apply_approval["event_id"],
        requested_by="tester",
    )
    blocked_execution_dry_run = service.staging_cleanup_execution_controlled_apply_execution_dry_run(
        apply_preflight_id=blocked_apply_preflight["event_id"],
        simulated_by="tester",
    )
    assert blocked_execution_dry_run["status"] == "controlled_cleanup_apply_execution_dry_run_blocked"
    assert blocked_execution_dry_run["decision"]["controlled_cleanup_apply_execution_dry_run_recorded"] is True
    assert blocked_execution_dry_run["decision"]["controlled_cleanup_apply_execution_dry_run_ready_for_review"] is False
    assert blocked_execution_dry_run["decision"]["can_execute_cleanup_now"] is False
    assert blocked_execution_dry_run["decision"]["writes_learning_samples_now"] is False
    assert blocked_execution_dry_run["simulation"]["contains_sql"] is False
    assert blocked_execution_dry_run["simulation"]["record_bodies_included"] is False

    plan_preflight = _cleanup_execution_plan_preflight_chain(
        service,
        pack,
        _manual_evidence_package(),
        suffix="ready-apply-execution-dry-run",
    )
    controlled = service.staging_cleanup_execution_controlled_dry_run(
        plan_preflight_id=plan_preflight["event_id"],
        simulated_by="tester",
        dry_run_decision="simulated_for_controlled_cleanup_review",
    )
    review = service.staging_cleanup_execution_controlled_dry_run_review(
        controlled_dry_run_id=controlled["event_id"],
        reviewed_by="tester",
        review_decision="approved_for_controlled_cleanup_execution_review",
    )
    approval = service.staging_cleanup_execution_controlled_approval(
        controlled_review_id=review["event_id"],
        approved_by="tester",
        approval_decision="approved_for_controlled_cleanup_execution_preflight",
    )
    preflight = service.staging_cleanup_execution_controlled_preflight(
        controlled_approval_id=approval["event_id"],
        requested_by="tester",
        preflight_decision="prepared_for_controlled_cleanup_execution_apply_dry_run",
    )
    apply_dry_run = service.staging_cleanup_execution_controlled_apply_dry_run(
        controlled_preflight_id=preflight["event_id"],
        simulated_by="tester",
        dry_run_decision="simulated_for_controlled_cleanup_apply_review",
    )
    apply_review = service.staging_cleanup_execution_controlled_apply_dry_run_review(
        apply_dry_run_id=apply_dry_run["event_id"],
        reviewed_by="tester",
        review_decision="approved_for_controlled_cleanup_apply_execution_review",
    )
    apply_approval = service.staging_cleanup_execution_controlled_apply_approval(
        apply_review_id=apply_review["event_id"],
        approved_by="tester",
        approval_decision="approved_for_controlled_cleanup_apply_execution_preflight",
    )
    apply_preflight = service.staging_cleanup_execution_controlled_apply_preflight(
        apply_approval_id=apply_approval["event_id"],
        requested_by="tester",
        preflight_decision="prepared_for_controlled_cleanup_apply_execution_dry_run",
    )
    execution_dry_run = service.staging_cleanup_execution_controlled_apply_execution_dry_run(
        apply_preflight_id=apply_preflight["event_id"],
        simulated_by="tester",
        dry_run_decision="simulated_for_controlled_cleanup_apply_execution_review",
        note="aggregate-only apply execution dry-run",
    )

    assert execution_dry_run["stage"] == "V5.6-P43"
    assert execution_dry_run["status"] == "controlled_cleanup_apply_execution_dry_run_ready_for_review"
    assert isinstance(execution_dry_run["event_id"], int)
    assert execution_dry_run["apply_preflight_id"] == apply_preflight["event_id"]
    assert execution_dry_run["apply_approval_id"] == apply_approval["event_id"]
    assert execution_dry_run["apply_review_id"] == apply_review["event_id"]
    assert execution_dry_run["apply_dry_run_id"] == apply_dry_run["event_id"]
    assert execution_dry_run["simulation"]["lock_key"] == apply_preflight["preflight"]["lock_key"]
    assert execution_dry_run["simulation"]["staging_record_count_before"] == 2
    assert execution_dry_run["simulation"]["expected_staging_record_count_after"] == 2
    assert execution_dry_run["simulation"]["preflight_staging_record_count"] == 2
    assert execution_dry_run["simulation"]["staging_count_still_matches"] is True
    assert execution_dry_run["simulation"]["learning_sample_count_before"] == 0
    assert execution_dry_run["simulation"]["expected_learning_sample_count_after"] == 0
    assert execution_dry_run["simulation"]["automated_operation_count"] >= 1
    assert execution_dry_run["simulation"]["manual_operation_count"] >= 1
    assert execution_dry_run["simulation"]["records_with_operations"] >= 1
    assert execution_dry_run["simulation"]["records_with_quality_flags"] >= 1
    assert execution_dry_run["simulation"]["operation_counts"]
    assert execution_dry_run["simulation"]["field_counts"]
    assert execution_dry_run["simulation"]["quality_flag_counts"]
    assert execution_dry_run["simulation"]["simulated_mutation_count"] == execution_dry_run["simulation"]["automated_operation_count"]
    assert execution_dry_run["simulation"]["simulated_quality_flag_reduction_count"] == execution_dry_run["simulation"]["automated_operation_count"]
    assert execution_dry_run["simulation"]["simulated_manual_flag_remaining_count"] == execution_dry_run["simulation"]["manual_operation_count"]
    assert execution_dry_run["simulation"]["transaction_required"] is True
    assert execution_dry_run["simulation"]["rollback_required"] is True
    assert execution_dry_run["simulation"]["allowed_tables"] == ["dataset2_staging_records"]
    assert "learning_samples" in execution_dry_run["simulation"]["forbidden_tables"]
    assert execution_dry_run["simulation"]["contains_sql"] is False
    assert execution_dry_run["simulation"]["contains_executable_code"] is False
    assert execution_dry_run["simulation"]["can_execute_now"] is False
    assert execution_dry_run["simulation"]["record_bodies_included"] is False
    assert execution_dry_run["simulation"]["affected_rows_body_included"] is False
    assert execution_dry_run["simulation"]["writes_staging_records_now"] is False
    assert execution_dry_run["simulation"]["writes_learning_samples_now"] is False
    assert execution_dry_run["simulation"]["mutates_staging_records_now"] is False
    assert execution_dry_run["decision"]["controlled_cleanup_apply_execution_dry_run_recorded"] is True
    assert execution_dry_run["decision"]["controlled_cleanup_apply_execution_dry_run_ready_for_review"] is True
    assert execution_dry_run["decision"]["cleanup_execution_approved_now"] is False
    assert execution_dry_run["decision"]["cleanup_application_allowed_now"] is False
    assert execution_dry_run["decision"]["cleanup_executed_now"] is False
    assert execution_dry_run["decision"]["can_execute_cleanup_now"] is False
    assert execution_dry_run["decision"]["writes_staging_records_now"] is False
    assert execution_dry_run["decision"]["writes_learning_samples_now"] is False
    assert execution_dry_run["decision"]["mutates_staging_records_now"] is False
    assert execution_dry_run["decision"]["training_started_now"] is False
    assert execution_dry_run["decision"]["can_start_training_now"] is False
    assert "evidence_package" not in execution_dry_run
    assert "records" not in execution_dry_run["simulation"]
    check_status = {check["name"]: check["status"] for check in execution_dry_run["checks"]}
    assert check_status["apply_preflight_ready_for_dry_run"] == "passed"
    assert check_status["apply_execution_simulation_scope_present"] == "passed"
    assert check_status["manual_backfill_separated"] == "warning"
    assert check_status["cleanup_and_training_remain_blocked"] == "passed"

    execution_dry_runs = service.list_staging_cleanup_execution_controlled_apply_execution_dry_runs(limit=5)
    assert execution_dry_runs[0]["id"] == execution_dry_run["event_id"]
    assert execution_dry_runs[0]["dry_run"]["simulated_by"] == "tester"
    assert "evidence_package" not in execution_dry_runs[0]


def test_dataset2_controlled_cleanup_apply_execution_dry_run_review_is_metadata_only(tmp_path, test_db):
    pack = _write_dataset2_pack(
        tmp_path,
        [
            _record(
                pattern_id="CONTROLLED_APPLY_EXECUTION_REVIEW_001",
                risk_level="medium_high",
                split_tag="train",
                observable_features=["['big_yang']", "high_volume"],
                evidence_summary="",
            ),
            _record(
                pattern_id="CONTROLLED_APPLY_EXECUTION_REVIEW_002",
                action_label="RISK_ALERT",
                risk_level="high",
                split_tag="test",
            ),
        ],
    )
    service = Dataset2TrainingReadinessService()

    before_missing = service.list_staging_cleanup_execution_controlled_apply_execution_dry_run_reviews(limit=5)
    missing = service.staging_cleanup_execution_controlled_apply_execution_dry_run_review(
        apply_execution_dry_run_id=999999,
        reviewed_by="tester",
    )
    after_missing = service.list_staging_cleanup_execution_controlled_apply_execution_dry_run_reviews(limit=5)
    assert missing["status"] == "controlled_cleanup_apply_execution_dry_run_review_blocked_missing_dry_run"
    assert missing["decision"]["writes_existing_event_now"] is False
    assert missing["decision"]["controlled_cleanup_apply_execution_dry_run_review_accepted"] is False
    assert missing["decision"]["controlled_cleanup_apply_execution_review_ready_for_plan"] is False
    assert missing["decision"]["cleanup_executed_now"] is False
    assert missing["decision"]["training_started_now"] is False
    assert len(after_missing) == len(before_missing)

    blocked_preflight_source = _cleanup_execution_plan_preflight_chain(
        service,
        pack,
        {},
        suffix="blocked-apply-execution-review",
    )
    blocked_controlled = service.staging_cleanup_execution_controlled_dry_run(
        plan_preflight_id=blocked_preflight_source["event_id"],
        simulated_by="tester",
    )
    blocked_review = service.staging_cleanup_execution_controlled_dry_run_review(
        controlled_dry_run_id=blocked_controlled["event_id"],
        reviewed_by="tester",
    )
    blocked_approval = service.staging_cleanup_execution_controlled_approval(
        controlled_review_id=blocked_review["event_id"],
        approved_by="tester",
    )
    blocked_preflight = service.staging_cleanup_execution_controlled_preflight(
        controlled_approval_id=blocked_approval["event_id"],
        requested_by="tester",
    )
    blocked_apply = service.staging_cleanup_execution_controlled_apply_dry_run(
        controlled_preflight_id=blocked_preflight["event_id"],
        simulated_by="tester",
    )
    blocked_apply_review = service.staging_cleanup_execution_controlled_apply_dry_run_review(
        apply_dry_run_id=blocked_apply["event_id"],
        reviewed_by="tester",
    )
    blocked_apply_approval = service.staging_cleanup_execution_controlled_apply_approval(
        apply_review_id=blocked_apply_review["event_id"],
        approved_by="tester",
    )
    blocked_apply_preflight = service.staging_cleanup_execution_controlled_apply_preflight(
        apply_approval_id=blocked_apply_approval["event_id"],
        requested_by="tester",
    )
    blocked_execution_dry_run = service.staging_cleanup_execution_controlled_apply_execution_dry_run(
        apply_preflight_id=blocked_apply_preflight["event_id"],
        simulated_by="tester",
    )
    blocked_execution_review = service.staging_cleanup_execution_controlled_apply_execution_dry_run_review(
        apply_execution_dry_run_id=blocked_execution_dry_run["event_id"],
        reviewed_by="tester",
    )
    assert blocked_execution_review["status"] == "controlled_cleanup_apply_execution_dry_run_review_blocked"
    assert blocked_execution_review["decision"]["controlled_cleanup_apply_execution_dry_run_review_recorded"] is True
    assert blocked_execution_review["decision"]["controlled_cleanup_apply_execution_dry_run_review_accepted"] is False
    assert blocked_execution_review["decision"]["can_execute_cleanup_now"] is False
    assert blocked_execution_review["decision"]["writes_learning_samples_now"] is False
    assert blocked_execution_review["simulation_summary"]["contains_sql"] is False
    assert blocked_execution_review["simulation_summary"]["record_bodies_included"] is False

    plan_preflight = _cleanup_execution_plan_preflight_chain(
        service,
        pack,
        _manual_evidence_package(),
        suffix="ready-apply-execution-review",
    )
    controlled = service.staging_cleanup_execution_controlled_dry_run(
        plan_preflight_id=plan_preflight["event_id"],
        simulated_by="tester",
        dry_run_decision="simulated_for_controlled_cleanup_review",
    )
    review = service.staging_cleanup_execution_controlled_dry_run_review(
        controlled_dry_run_id=controlled["event_id"],
        reviewed_by="tester",
        review_decision="approved_for_controlled_cleanup_execution_review",
    )
    approval = service.staging_cleanup_execution_controlled_approval(
        controlled_review_id=review["event_id"],
        approved_by="tester",
        approval_decision="approved_for_controlled_cleanup_execution_preflight",
    )
    preflight = service.staging_cleanup_execution_controlled_preflight(
        controlled_approval_id=approval["event_id"],
        requested_by="tester",
        preflight_decision="prepared_for_controlled_cleanup_execution_apply_dry_run",
    )
    apply_dry_run = service.staging_cleanup_execution_controlled_apply_dry_run(
        controlled_preflight_id=preflight["event_id"],
        simulated_by="tester",
        dry_run_decision="simulated_for_controlled_cleanup_apply_review",
    )
    apply_review = service.staging_cleanup_execution_controlled_apply_dry_run_review(
        apply_dry_run_id=apply_dry_run["event_id"],
        reviewed_by="tester",
        review_decision="approved_for_controlled_cleanup_apply_execution_review",
    )
    apply_approval = service.staging_cleanup_execution_controlled_apply_approval(
        apply_review_id=apply_review["event_id"],
        approved_by="tester",
        approval_decision="approved_for_controlled_cleanup_apply_execution_preflight",
    )
    apply_preflight = service.staging_cleanup_execution_controlled_apply_preflight(
        apply_approval_id=apply_approval["event_id"],
        requested_by="tester",
        preflight_decision="prepared_for_controlled_cleanup_apply_execution_dry_run",
    )
    execution_dry_run = service.staging_cleanup_execution_controlled_apply_execution_dry_run(
        apply_preflight_id=apply_preflight["event_id"],
        simulated_by="tester",
        dry_run_decision="simulated_for_controlled_cleanup_apply_execution_review",
    )
    execution_review = service.staging_cleanup_execution_controlled_apply_execution_dry_run_review(
        apply_execution_dry_run_id=execution_dry_run["event_id"],
        reviewed_by="tester",
        review_decision="approved_for_controlled_cleanup_apply_execution_plan",
        note="metadata-only apply execution review",
    )

    assert execution_review["stage"] == "V5.6-P43"
    assert execution_review["status"] == "controlled_cleanup_apply_execution_dry_run_review_accepted"
    assert isinstance(execution_review["event_id"], int)
    assert execution_review["apply_execution_dry_run_id"] == execution_dry_run["event_id"]
    assert execution_review["apply_preflight_id"] == apply_preflight["event_id"]
    assert execution_review["apply_approval_id"] == apply_approval["event_id"]
    assert execution_review["apply_review_id"] == apply_review["event_id"]
    assert execution_review["apply_dry_run_id"] == apply_dry_run["event_id"]
    assert execution_review["simulation_summary"]["lock_key"] == execution_dry_run["simulation"]["lock_key"]
    assert execution_review["simulation_summary"]["staging_record_count_before"] == 2
    assert execution_review["simulation_summary"]["expected_staging_record_count_after"] == 2
    assert execution_review["simulation_summary"]["learning_sample_count_before"] == 0
    assert execution_review["simulation_summary"]["expected_learning_sample_count_after"] == 0
    assert execution_review["simulation_summary"]["automated_operation_count"] >= 1
    assert execution_review["simulation_summary"]["manual_operation_count"] >= 1
    assert execution_review["simulation_summary"]["operation_counts"]
    assert execution_review["simulation_summary"]["field_counts"]
    assert execution_review["simulation_summary"]["quality_flag_counts"]
    assert execution_review["simulation_summary"]["simulated_mutation_count"] == execution_review["simulation_summary"]["automated_operation_count"]
    assert execution_review["simulation_summary"]["transaction_required"] is True
    assert execution_review["simulation_summary"]["rollback_required"] is True
    assert execution_review["simulation_summary"]["allowed_tables"] == ["dataset2_staging_records"]
    assert "learning_samples" in execution_review["simulation_summary"]["forbidden_tables"]
    assert execution_review["simulation_summary"]["contains_sql"] is False
    assert execution_review["simulation_summary"]["contains_executable_code"] is False
    assert execution_review["simulation_summary"]["can_execute_now"] is False
    assert execution_review["simulation_summary"]["record_bodies_included"] is False
    assert execution_review["simulation_summary"]["affected_rows_body_included"] is False
    assert execution_review["decision"]["controlled_cleanup_apply_execution_dry_run_review_recorded"] is True
    assert execution_review["decision"]["controlled_cleanup_apply_execution_dry_run_review_accepted"] is True
    assert execution_review["decision"]["controlled_cleanup_apply_execution_review_ready_for_plan"] is True
    assert execution_review["decision"]["cleanup_execution_approved_now"] is False
    assert execution_review["decision"]["cleanup_application_allowed_now"] is False
    assert execution_review["decision"]["cleanup_executed_now"] is False
    assert execution_review["decision"]["can_execute_cleanup_now"] is False
    assert execution_review["decision"]["writes_staging_records_now"] is False
    assert execution_review["decision"]["writes_learning_samples_now"] is False
    assert execution_review["decision"]["mutates_staging_records_now"] is False
    assert execution_review["decision"]["training_started_now"] is False
    assert execution_review["decision"]["can_start_training_now"] is False
    assert "evidence_package" not in execution_review
    assert "records" not in execution_review["simulation_summary"]
    check_status = {check["name"]: check["status"] for check in execution_review["checks"]}
    assert check_status["apply_execution_dry_run_ready_for_review"] == "passed"
    assert check_status["aggregate_apply_execution_simulation_present"] == "passed"
    assert check_status["manual_backfill_separated"] == "warning"
    assert check_status["cleanup_and_training_remain_blocked"] == "passed"

    execution_reviews = service.list_staging_cleanup_execution_controlled_apply_execution_dry_run_reviews(limit=5)
    assert execution_reviews[0]["id"] == execution_review["event_id"]
    assert execution_reviews[0]["review"]["reviewed_by"] == "tester"
    assert "evidence_package" not in execution_reviews[0]


def test_dataset2_controlled_cleanup_apply_execution_plan_is_metadata_only(tmp_path, test_db):
    pack = _write_dataset2_pack(
        tmp_path,
        [
            _record(
                pattern_id="CONTROLLED_APPLY_EXECUTION_PLAN_001",
                risk_level="medium_high",
                split_tag="train",
                observable_features=["['big_yang']", "high_volume"],
                evidence_summary="",
            ),
            _record(
                pattern_id="CONTROLLED_APPLY_EXECUTION_PLAN_002",
                action_label="RISK_ALERT",
                risk_level="high",
                split_tag="test",
            ),
        ],
    )
    service = Dataset2TrainingReadinessService()

    before_missing = service.list_staging_cleanup_execution_controlled_apply_execution_plans(limit=5)
    missing = service.staging_cleanup_execution_controlled_apply_execution_plan(
        apply_execution_review_id=999999,
        planned_by="tester",
    )
    after_missing = service.list_staging_cleanup_execution_controlled_apply_execution_plans(limit=5)
    assert missing["status"] == "controlled_cleanup_apply_execution_plan_blocked_missing_review"
    assert missing["decision"]["writes_existing_event_now"] is False
    assert missing["decision"]["controlled_cleanup_apply_execution_plan_ready_for_preflight"] is False
    assert missing["decision"]["cleanup_executed_now"] is False
    assert missing["decision"]["training_started_now"] is False
    assert len(after_missing) == len(before_missing)

    blocked_preflight_source = _cleanup_execution_plan_preflight_chain(
        service,
        pack,
        {},
        suffix="blocked-apply-execution-plan",
    )
    blocked_controlled = service.staging_cleanup_execution_controlled_dry_run(
        plan_preflight_id=blocked_preflight_source["event_id"],
        simulated_by="tester",
    )
    blocked_review = service.staging_cleanup_execution_controlled_dry_run_review(
        controlled_dry_run_id=blocked_controlled["event_id"],
        reviewed_by="tester",
    )
    blocked_approval = service.staging_cleanup_execution_controlled_approval(
        controlled_review_id=blocked_review["event_id"],
        approved_by="tester",
    )
    blocked_preflight = service.staging_cleanup_execution_controlled_preflight(
        controlled_approval_id=blocked_approval["event_id"],
        requested_by="tester",
    )
    blocked_apply = service.staging_cleanup_execution_controlled_apply_dry_run(
        controlled_preflight_id=blocked_preflight["event_id"],
        simulated_by="tester",
    )
    blocked_apply_review = service.staging_cleanup_execution_controlled_apply_dry_run_review(
        apply_dry_run_id=blocked_apply["event_id"],
        reviewed_by="tester",
    )
    blocked_apply_approval = service.staging_cleanup_execution_controlled_apply_approval(
        apply_review_id=blocked_apply_review["event_id"],
        approved_by="tester",
    )
    blocked_apply_preflight = service.staging_cleanup_execution_controlled_apply_preflight(
        apply_approval_id=blocked_apply_approval["event_id"],
        requested_by="tester",
    )
    blocked_execution_dry_run = service.staging_cleanup_execution_controlled_apply_execution_dry_run(
        apply_preflight_id=blocked_apply_preflight["event_id"],
        simulated_by="tester",
    )
    blocked_execution_review = service.staging_cleanup_execution_controlled_apply_execution_dry_run_review(
        apply_execution_dry_run_id=blocked_execution_dry_run["event_id"],
        reviewed_by="tester",
    )
    blocked_execution_plan = service.staging_cleanup_execution_controlled_apply_execution_plan(
        apply_execution_review_id=blocked_execution_review["event_id"],
        planned_by="tester",
    )
    assert blocked_execution_plan["status"] == "controlled_cleanup_apply_execution_plan_blocked"
    assert blocked_execution_plan["decision"]["controlled_cleanup_apply_execution_plan_recorded"] is True
    assert blocked_execution_plan["decision"]["controlled_cleanup_apply_execution_plan_ready_for_preflight"] is False
    assert blocked_execution_plan["decision"]["can_execute_cleanup_now"] is False
    assert blocked_execution_plan["decision"]["writes_learning_samples_now"] is False
    assert blocked_execution_plan["execution_plan"]["contains_sql"] is False
    assert blocked_execution_plan["execution_plan"]["record_bodies_included"] is False

    plan_preflight = _cleanup_execution_plan_preflight_chain(
        service,
        pack,
        _manual_evidence_package(),
        suffix="ready-apply-execution-plan",
    )
    controlled = service.staging_cleanup_execution_controlled_dry_run(
        plan_preflight_id=plan_preflight["event_id"],
        simulated_by="tester",
        dry_run_decision="simulated_for_controlled_cleanup_review",
    )
    review = service.staging_cleanup_execution_controlled_dry_run_review(
        controlled_dry_run_id=controlled["event_id"],
        reviewed_by="tester",
        review_decision="approved_for_controlled_cleanup_execution_review",
    )
    approval = service.staging_cleanup_execution_controlled_approval(
        controlled_review_id=review["event_id"],
        approved_by="tester",
        approval_decision="approved_for_controlled_cleanup_execution_preflight",
    )
    preflight = service.staging_cleanup_execution_controlled_preflight(
        controlled_approval_id=approval["event_id"],
        requested_by="tester",
        preflight_decision="prepared_for_controlled_cleanup_execution_apply_dry_run",
    )
    apply_dry_run = service.staging_cleanup_execution_controlled_apply_dry_run(
        controlled_preflight_id=preflight["event_id"],
        simulated_by="tester",
        dry_run_decision="simulated_for_controlled_cleanup_apply_review",
    )
    apply_review = service.staging_cleanup_execution_controlled_apply_dry_run_review(
        apply_dry_run_id=apply_dry_run["event_id"],
        reviewed_by="tester",
        review_decision="approved_for_controlled_cleanup_apply_execution_review",
    )
    apply_approval = service.staging_cleanup_execution_controlled_apply_approval(
        apply_review_id=apply_review["event_id"],
        approved_by="tester",
        approval_decision="approved_for_controlled_cleanup_apply_execution_preflight",
    )
    apply_preflight = service.staging_cleanup_execution_controlled_apply_preflight(
        apply_approval_id=apply_approval["event_id"],
        requested_by="tester",
        preflight_decision="prepared_for_controlled_cleanup_apply_execution_dry_run",
    )
    execution_dry_run = service.staging_cleanup_execution_controlled_apply_execution_dry_run(
        apply_preflight_id=apply_preflight["event_id"],
        simulated_by="tester",
        dry_run_decision="simulated_for_controlled_cleanup_apply_execution_review",
    )
    execution_review = service.staging_cleanup_execution_controlled_apply_execution_dry_run_review(
        apply_execution_dry_run_id=execution_dry_run["event_id"],
        reviewed_by="tester",
        review_decision="approved_for_controlled_cleanup_apply_execution_plan",
    )
    execution_plan = service.staging_cleanup_execution_controlled_apply_execution_plan(
        apply_execution_review_id=execution_review["event_id"],
        planned_by="tester",
        plan_decision="prepared_for_controlled_cleanup_apply_execution_plan_preflight",
        note="metadata-only apply execution plan",
    )

    assert execution_plan["stage"] == "V5.6-P43"
    assert execution_plan["status"] == "controlled_cleanup_apply_execution_plan_ready_for_preflight"
    assert isinstance(execution_plan["event_id"], int)
    assert execution_plan["apply_execution_review_id"] == execution_review["event_id"]
    assert execution_plan["apply_execution_dry_run_id"] == execution_dry_run["event_id"]
    assert execution_plan["apply_preflight_id"] == apply_preflight["event_id"]
    assert execution_plan["apply_approval_id"] == apply_approval["event_id"]
    assert execution_plan["apply_review_id"] == apply_review["event_id"]
    assert execution_plan["apply_dry_run_id"] == apply_dry_run["event_id"]
    assert execution_plan["execution_plan"]["lock_key"] == execution_review["simulation_summary"]["lock_key"]
    assert execution_plan["execution_plan"]["candidate_record_count"] == 2
    assert execution_plan["execution_plan"]["planned_operation_count"] >= 1
    assert execution_plan["execution_plan"]["automated_operation_count"] >= 1
    assert execution_plan["execution_plan"]["manual_operation_count"] >= 1
    assert execution_plan["execution_plan"]["operation_counts"]
    assert execution_plan["execution_plan"]["field_counts"]
    assert execution_plan["execution_plan"]["quality_flag_counts"]
    assert execution_plan["execution_plan"]["execution_batches"]
    assert execution_plan["execution_plan"]["manual_backfill_batches"]
    assert execution_plan["execution_plan"]["requires_preflight"] is True
    assert execution_plan["execution_plan"]["requires_transaction"] is True
    assert execution_plan["execution_plan"]["requires_rollback"] is True
    assert execution_plan["execution_plan"]["allowed_next_stage"] == "controlled_cleanup_apply_execution_plan_preflight"
    assert execution_plan["execution_plan"]["allowed_tables"] == ["dataset2_staging_records"]
    assert "learning_samples" in execution_plan["execution_plan"]["forbidden_tables"]
    assert execution_plan["execution_plan"]["contains_sql"] is False
    assert execution_plan["execution_plan"]["contains_executable_code"] is False
    assert execution_plan["execution_plan"]["can_execute_now"] is False
    assert execution_plan["execution_plan"]["record_bodies_included"] is False
    assert execution_plan["execution_plan"]["affected_rows_body_included"] is False
    assert execution_plan["execution_plan"]["writes_staging_records_now"] is False
    assert execution_plan["execution_plan"]["writes_learning_samples_now"] is False
    assert execution_plan["execution_plan"]["mutates_staging_records_now"] is False
    assert execution_plan["decision"]["controlled_cleanup_apply_execution_plan_recorded"] is True
    assert execution_plan["decision"]["controlled_cleanup_apply_execution_plan_ready_for_preflight"] is True
    assert execution_plan["decision"]["cleanup_execution_approved_now"] is False
    assert execution_plan["decision"]["cleanup_application_allowed_now"] is False
    assert execution_plan["decision"]["cleanup_executed_now"] is False
    assert execution_plan["decision"]["can_execute_cleanup_now"] is False
    assert execution_plan["decision"]["writes_staging_records_now"] is False
    assert execution_plan["decision"]["writes_learning_samples_now"] is False
    assert execution_plan["decision"]["mutates_staging_records_now"] is False
    assert execution_plan["decision"]["training_started_now"] is False
    assert execution_plan["decision"]["can_start_training_now"] is False
    assert "evidence_package" not in execution_plan
    assert "records" not in execution_plan["execution_plan"]
    check_status = {check["name"]: check["status"] for check in execution_plan["checks"]}
    assert check_status["apply_execution_review_accepted_for_plan"] == "passed"
    assert check_status["aggregate_apply_execution_plan_scope_present"] == "passed"
    assert check_status["plan_contains_no_executable_payload"] == "passed"
    assert check_status["manual_backfill_separated"] == "warning"
    assert check_status["cleanup_and_training_remain_blocked"] == "passed"

    execution_plans = service.list_staging_cleanup_execution_controlled_apply_execution_plans(limit=5)
    assert execution_plans[0]["id"] == execution_plan["event_id"]
    assert execution_plans[0]["planning"]["planned_by"] == "tester"
    assert "evidence_package" not in execution_plans[0]


def test_dataset2_controlled_cleanup_apply_execution_plan_preflight_is_metadata_only(tmp_path, test_db):
    pack = _write_dataset2_pack(
        tmp_path,
        [
            _record(
                pattern_id="CONTROLLED_APPLY_EXECUTION_PLAN_PREFLIGHT_001",
                risk_level="medium_high",
                split_tag="train",
                observable_features=["['big_yang']", "high_volume"],
                evidence_summary="",
            ),
            _record(
                pattern_id="CONTROLLED_APPLY_EXECUTION_PLAN_PREFLIGHT_002",
                action_label="RISK_ALERT",
                risk_level="high",
                split_tag="test",
            ),
        ],
    )
    service = Dataset2TrainingReadinessService()

    before_missing = service.list_staging_cleanup_execution_controlled_apply_execution_plan_preflights(limit=5)
    missing = service.staging_cleanup_execution_controlled_apply_execution_plan_preflight(
        apply_execution_plan_id=999999,
        requested_by="tester",
    )
    after_missing = service.list_staging_cleanup_execution_controlled_apply_execution_plan_preflights(limit=5)
    assert missing["status"] == "controlled_cleanup_apply_execution_plan_preflight_blocked_missing_plan"
    assert missing["decision"]["writes_existing_event_now"] is False
    assert missing["decision"]["controlled_cleanup_apply_execution_plan_preflight_ready_for_dry_run"] is False
    assert missing["decision"]["cleanup_executed_now"] is False
    assert missing["decision"]["training_started_now"] is False
    assert len(after_missing) == len(before_missing)

    blocked_preflight_source = _cleanup_execution_plan_preflight_chain(
        service,
        pack,
        {},
        suffix="blocked-apply-execution-plan-preflight",
    )
    blocked_controlled = service.staging_cleanup_execution_controlled_dry_run(
        plan_preflight_id=blocked_preflight_source["event_id"],
        simulated_by="tester",
    )
    blocked_review = service.staging_cleanup_execution_controlled_dry_run_review(
        controlled_dry_run_id=blocked_controlled["event_id"],
        reviewed_by="tester",
    )
    blocked_approval = service.staging_cleanup_execution_controlled_approval(
        controlled_review_id=blocked_review["event_id"],
        approved_by="tester",
    )
    blocked_preflight = service.staging_cleanup_execution_controlled_preflight(
        controlled_approval_id=blocked_approval["event_id"],
        requested_by="tester",
    )
    blocked_apply = service.staging_cleanup_execution_controlled_apply_dry_run(
        controlled_preflight_id=blocked_preflight["event_id"],
        simulated_by="tester",
    )
    blocked_apply_review = service.staging_cleanup_execution_controlled_apply_dry_run_review(
        apply_dry_run_id=blocked_apply["event_id"],
        reviewed_by="tester",
    )
    blocked_apply_approval = service.staging_cleanup_execution_controlled_apply_approval(
        apply_review_id=blocked_apply_review["event_id"],
        approved_by="tester",
    )
    blocked_apply_preflight = service.staging_cleanup_execution_controlled_apply_preflight(
        apply_approval_id=blocked_apply_approval["event_id"],
        requested_by="tester",
    )
    blocked_execution_dry_run = service.staging_cleanup_execution_controlled_apply_execution_dry_run(
        apply_preflight_id=blocked_apply_preflight["event_id"],
        simulated_by="tester",
    )
    blocked_execution_review = service.staging_cleanup_execution_controlled_apply_execution_dry_run_review(
        apply_execution_dry_run_id=blocked_execution_dry_run["event_id"],
        reviewed_by="tester",
    )
    blocked_execution_plan = service.staging_cleanup_execution_controlled_apply_execution_plan(
        apply_execution_review_id=blocked_execution_review["event_id"],
        planned_by="tester",
    )
    blocked_plan_preflight = service.staging_cleanup_execution_controlled_apply_execution_plan_preflight(
        apply_execution_plan_id=blocked_execution_plan["event_id"],
        requested_by="tester",
    )
    assert blocked_plan_preflight["status"] == "controlled_cleanup_apply_execution_plan_preflight_blocked"
    assert blocked_plan_preflight["decision"]["controlled_cleanup_apply_execution_plan_preflight_recorded"] is True
    assert blocked_plan_preflight["decision"]["controlled_cleanup_apply_execution_plan_preflight_ready_for_dry_run"] is False
    assert blocked_plan_preflight["decision"]["can_execute_cleanup_now"] is False
    assert blocked_plan_preflight["decision"]["writes_learning_samples_now"] is False
    assert blocked_plan_preflight["preflight"]["contains_sql"] is False
    assert blocked_plan_preflight["preflight"]["record_bodies_included"] is False

    plan_preflight = _cleanup_execution_plan_preflight_chain(
        service,
        pack,
        _manual_evidence_package(),
        suffix="ready-apply-execution-plan-preflight",
    )
    controlled = service.staging_cleanup_execution_controlled_dry_run(
        plan_preflight_id=plan_preflight["event_id"],
        simulated_by="tester",
        dry_run_decision="simulated_for_controlled_cleanup_review",
    )
    review = service.staging_cleanup_execution_controlled_dry_run_review(
        controlled_dry_run_id=controlled["event_id"],
        reviewed_by="tester",
        review_decision="approved_for_controlled_cleanup_execution_review",
    )
    approval = service.staging_cleanup_execution_controlled_approval(
        controlled_review_id=review["event_id"],
        approved_by="tester",
        approval_decision="approved_for_controlled_cleanup_execution_preflight",
    )
    preflight = service.staging_cleanup_execution_controlled_preflight(
        controlled_approval_id=approval["event_id"],
        requested_by="tester",
        preflight_decision="prepared_for_controlled_cleanup_execution_apply_dry_run",
    )
    apply_dry_run = service.staging_cleanup_execution_controlled_apply_dry_run(
        controlled_preflight_id=preflight["event_id"],
        simulated_by="tester",
        dry_run_decision="simulated_for_controlled_cleanup_apply_review",
    )
    apply_review = service.staging_cleanup_execution_controlled_apply_dry_run_review(
        apply_dry_run_id=apply_dry_run["event_id"],
        reviewed_by="tester",
        review_decision="approved_for_controlled_cleanup_apply_execution_review",
    )
    apply_approval = service.staging_cleanup_execution_controlled_apply_approval(
        apply_review_id=apply_review["event_id"],
        approved_by="tester",
        approval_decision="approved_for_controlled_cleanup_apply_execution_preflight",
    )
    apply_preflight = service.staging_cleanup_execution_controlled_apply_preflight(
        apply_approval_id=apply_approval["event_id"],
        requested_by="tester",
        preflight_decision="prepared_for_controlled_cleanup_apply_execution_dry_run",
    )
    execution_dry_run = service.staging_cleanup_execution_controlled_apply_execution_dry_run(
        apply_preflight_id=apply_preflight["event_id"],
        simulated_by="tester",
        dry_run_decision="simulated_for_controlled_cleanup_apply_execution_review",
    )
    execution_review = service.staging_cleanup_execution_controlled_apply_execution_dry_run_review(
        apply_execution_dry_run_id=execution_dry_run["event_id"],
        reviewed_by="tester",
        review_decision="approved_for_controlled_cleanup_apply_execution_plan",
    )
    execution_plan = service.staging_cleanup_execution_controlled_apply_execution_plan(
        apply_execution_review_id=execution_review["event_id"],
        planned_by="tester",
        plan_decision="prepared_for_controlled_cleanup_apply_execution_plan_preflight",
    )
    execution_preflight = service.staging_cleanup_execution_controlled_apply_execution_plan_preflight(
        apply_execution_plan_id=execution_plan["event_id"],
        requested_by="tester",
        preflight_decision="prepared_for_controlled_cleanup_apply_execution_plan_dry_run",
        note="metadata-only apply execution plan preflight",
    )

    assert execution_preflight["stage"] == "V5.6-P43"
    assert execution_preflight["status"] == "controlled_cleanup_apply_execution_plan_preflight_ready_for_dry_run"
    assert isinstance(execution_preflight["event_id"], int)
    assert execution_preflight["apply_execution_plan_id"] == execution_plan["event_id"]
    assert execution_preflight["apply_execution_review_id"] == execution_review["event_id"]
    assert execution_preflight["apply_execution_dry_run_id"] == execution_dry_run["event_id"]
    assert execution_preflight["apply_preflight_id"] == apply_preflight["event_id"]
    assert execution_preflight["apply_approval_id"] == apply_approval["event_id"]
    assert execution_preflight["apply_review_id"] == apply_review["event_id"]
    assert execution_preflight["apply_dry_run_id"] == apply_dry_run["event_id"]
    assert execution_preflight["preflight"]["lock_key"] == execution_plan["execution_plan"]["lock_key"]
    assert execution_preflight["preflight"]["staging_record_count"] == 2
    assert execution_preflight["preflight"]["expected_staging_record_count_after"] == 2
    assert execution_preflight["preflight"]["plan_candidate_record_count"] == 2
    assert execution_preflight["preflight"]["staging_count_still_matches"] is True
    assert execution_preflight["preflight"]["learning_sample_count"] == 0
    assert execution_preflight["preflight"]["expected_learning_sample_count_after"] == 0
    assert execution_preflight["preflight"]["automated_operation_count"] >= 1
    assert execution_preflight["preflight"]["manual_operation_count"] >= 1
    assert execution_preflight["preflight"]["planned_operation_count"] >= 1
    assert execution_preflight["preflight"]["execution_batch_count"] >= 1
    assert execution_preflight["preflight"]["manual_backfill_batch_count"] >= 1
    assert execution_preflight["preflight"]["transaction_required"] is True
    assert execution_preflight["preflight"]["rollback_required"] is True
    assert execution_preflight["preflight"]["allowed_next_stage"] == "controlled_cleanup_apply_execution_plan_dry_run"
    assert execution_preflight["preflight"]["allowed_tables"] == ["dataset2_staging_records"]
    assert "learning_samples" in execution_preflight["preflight"]["forbidden_tables"]
    assert execution_preflight["preflight"]["contains_sql"] is False
    assert execution_preflight["preflight"]["contains_executable_code"] is False
    assert execution_preflight["preflight"]["can_execute_now"] is False
    assert execution_preflight["preflight"]["record_bodies_included"] is False
    assert execution_preflight["preflight"]["affected_rows_body_included"] is False
    assert execution_preflight["preflight"]["writes_staging_records_now"] is False
    assert execution_preflight["preflight"]["writes_learning_samples_now"] is False
    assert execution_preflight["preflight"]["mutates_staging_records_now"] is False
    assert execution_preflight["decision"]["controlled_cleanup_apply_execution_plan_preflight_recorded"] is True
    assert execution_preflight["decision"]["controlled_cleanup_apply_execution_plan_preflight_ready_for_dry_run"] is True
    assert execution_preflight["decision"]["cleanup_execution_approved_now"] is False
    assert execution_preflight["decision"]["cleanup_application_allowed_now"] is False
    assert execution_preflight["decision"]["cleanup_executed_now"] is False
    assert execution_preflight["decision"]["can_execute_cleanup_now"] is False
    assert execution_preflight["decision"]["writes_staging_records_now"] is False
    assert execution_preflight["decision"]["writes_learning_samples_now"] is False
    assert execution_preflight["decision"]["mutates_staging_records_now"] is False
    assert execution_preflight["decision"]["training_started_now"] is False
    assert execution_preflight["decision"]["can_start_training_now"] is False
    assert "evidence_package" not in execution_preflight
    assert "records" not in execution_preflight["preflight"]
    check_status = {check["name"]: check["status"] for check in execution_preflight["checks"]}
    assert check_status["apply_execution_plan_ready_for_preflight"] == "passed"
    assert check_status["staging_count_matches_plan"] == "passed"
    assert check_status["execution_batches_metadata_only"] == "passed"
    assert check_status["cleanup_and_training_remain_blocked"] == "passed"

    execution_preflights = service.list_staging_cleanup_execution_controlled_apply_execution_plan_preflights(limit=5)
    assert execution_preflights[0]["id"] == execution_preflight["event_id"]
    assert execution_preflights[0]["request"]["requested_by"] == "tester"
    assert "evidence_package" not in execution_preflights[0]


def test_dataset2_controlled_cleanup_apply_execution_plan_dry_run_is_metadata_only(tmp_path, test_db):
    pack = _write_dataset2_pack(
        tmp_path,
        [
            _record(
                pattern_id="CONTROLLED_APPLY_EXECUTION_PLAN_DRY_RUN_001",
                risk_level="medium_high",
                split_tag="train",
                observable_features=["['big_yang']", "high_volume"],
                evidence_summary="",
            ),
            _record(
                pattern_id="CONTROLLED_APPLY_EXECUTION_PLAN_DRY_RUN_002",
                action_label="RISK_ALERT",
                risk_level="high",
                split_tag="test",
            ),
        ],
    )
    service = Dataset2TrainingReadinessService()

    before_missing = service.list_staging_cleanup_execution_controlled_apply_execution_plan_dry_runs(limit=5)
    missing = service.staging_cleanup_execution_controlled_apply_execution_plan_dry_run(
        apply_execution_plan_preflight_id=999999,
        simulated_by="tester",
    )
    after_missing = service.list_staging_cleanup_execution_controlled_apply_execution_plan_dry_runs(limit=5)
    assert missing["status"] == "controlled_cleanup_apply_execution_plan_dry_run_blocked_missing_preflight"
    assert missing["decision"]["writes_existing_event_now"] is False
    assert missing["decision"]["controlled_cleanup_apply_execution_plan_dry_run_ready_for_review"] is False
    assert missing["decision"]["cleanup_executed_now"] is False
    assert missing["decision"]["training_started_now"] is False
    assert len(after_missing) == len(before_missing)

    blocked_preflight_source = _cleanup_execution_plan_preflight_chain(
        service,
        pack,
        {},
        suffix="blocked-apply-execution-plan-dry-run",
    )
    blocked_controlled = service.staging_cleanup_execution_controlled_dry_run(
        plan_preflight_id=blocked_preflight_source["event_id"],
        simulated_by="tester",
    )
    blocked_review = service.staging_cleanup_execution_controlled_dry_run_review(
        controlled_dry_run_id=blocked_controlled["event_id"],
        reviewed_by="tester",
    )
    blocked_approval = service.staging_cleanup_execution_controlled_approval(
        controlled_review_id=blocked_review["event_id"],
        approved_by="tester",
    )
    blocked_preflight = service.staging_cleanup_execution_controlled_preflight(
        controlled_approval_id=blocked_approval["event_id"],
        requested_by="tester",
    )
    blocked_apply = service.staging_cleanup_execution_controlled_apply_dry_run(
        controlled_preflight_id=blocked_preflight["event_id"],
        simulated_by="tester",
    )
    blocked_apply_review = service.staging_cleanup_execution_controlled_apply_dry_run_review(
        apply_dry_run_id=blocked_apply["event_id"],
        reviewed_by="tester",
    )
    blocked_apply_approval = service.staging_cleanup_execution_controlled_apply_approval(
        apply_review_id=blocked_apply_review["event_id"],
        approved_by="tester",
    )
    blocked_apply_preflight = service.staging_cleanup_execution_controlled_apply_preflight(
        apply_approval_id=blocked_apply_approval["event_id"],
        requested_by="tester",
    )
    blocked_execution_dry_run = service.staging_cleanup_execution_controlled_apply_execution_dry_run(
        apply_preflight_id=blocked_apply_preflight["event_id"],
        simulated_by="tester",
    )
    blocked_execution_review = service.staging_cleanup_execution_controlled_apply_execution_dry_run_review(
        apply_execution_dry_run_id=blocked_execution_dry_run["event_id"],
        reviewed_by="tester",
    )
    blocked_execution_plan = service.staging_cleanup_execution_controlled_apply_execution_plan(
        apply_execution_review_id=blocked_execution_review["event_id"],
        planned_by="tester",
    )
    blocked_plan_preflight = service.staging_cleanup_execution_controlled_apply_execution_plan_preflight(
        apply_execution_plan_id=blocked_execution_plan["event_id"],
        requested_by="tester",
    )
    blocked_plan_dry_run = service.staging_cleanup_execution_controlled_apply_execution_plan_dry_run(
        apply_execution_plan_preflight_id=blocked_plan_preflight["event_id"],
        simulated_by="tester",
    )
    assert blocked_plan_dry_run["status"] == "controlled_cleanup_apply_execution_plan_dry_run_blocked"
    assert blocked_plan_dry_run["decision"]["controlled_cleanup_apply_execution_plan_dry_run_recorded"] is True
    assert blocked_plan_dry_run["decision"]["controlled_cleanup_apply_execution_plan_dry_run_ready_for_review"] is False
    assert blocked_plan_dry_run["decision"]["can_execute_cleanup_now"] is False
    assert blocked_plan_dry_run["decision"]["writes_learning_samples_now"] is False
    assert blocked_plan_dry_run["dry_run"]["contains_sql"] is False
    assert blocked_plan_dry_run["dry_run"]["record_bodies_included"] is False

    plan_preflight = _cleanup_execution_plan_preflight_chain(
        service,
        pack,
        _manual_evidence_package(),
        suffix="ready-apply-execution-plan-dry-run",
    )
    controlled = service.staging_cleanup_execution_controlled_dry_run(
        plan_preflight_id=plan_preflight["event_id"],
        simulated_by="tester",
        dry_run_decision="simulated_for_controlled_cleanup_review",
    )
    review = service.staging_cleanup_execution_controlled_dry_run_review(
        controlled_dry_run_id=controlled["event_id"],
        reviewed_by="tester",
        review_decision="approved_for_controlled_cleanup_execution_review",
    )
    approval = service.staging_cleanup_execution_controlled_approval(
        controlled_review_id=review["event_id"],
        approved_by="tester",
        approval_decision="approved_for_controlled_cleanup_execution_preflight",
    )
    preflight = service.staging_cleanup_execution_controlled_preflight(
        controlled_approval_id=approval["event_id"],
        requested_by="tester",
        preflight_decision="prepared_for_controlled_cleanup_execution_apply_dry_run",
    )
    apply_dry_run = service.staging_cleanup_execution_controlled_apply_dry_run(
        controlled_preflight_id=preflight["event_id"],
        simulated_by="tester",
        dry_run_decision="simulated_for_controlled_cleanup_apply_review",
    )
    apply_review = service.staging_cleanup_execution_controlled_apply_dry_run_review(
        apply_dry_run_id=apply_dry_run["event_id"],
        reviewed_by="tester",
        review_decision="approved_for_controlled_cleanup_apply_execution_review",
    )
    apply_approval = service.staging_cleanup_execution_controlled_apply_approval(
        apply_review_id=apply_review["event_id"],
        approved_by="tester",
        approval_decision="approved_for_controlled_cleanup_apply_execution_preflight",
    )
    apply_preflight = service.staging_cleanup_execution_controlled_apply_preflight(
        apply_approval_id=apply_approval["event_id"],
        requested_by="tester",
        preflight_decision="prepared_for_controlled_cleanup_apply_execution_dry_run",
    )
    execution_dry_run = service.staging_cleanup_execution_controlled_apply_execution_dry_run(
        apply_preflight_id=apply_preflight["event_id"],
        simulated_by="tester",
        dry_run_decision="simulated_for_controlled_cleanup_apply_execution_review",
    )
    execution_review = service.staging_cleanup_execution_controlled_apply_execution_dry_run_review(
        apply_execution_dry_run_id=execution_dry_run["event_id"],
        reviewed_by="tester",
        review_decision="approved_for_controlled_cleanup_apply_execution_plan",
    )
    execution_plan = service.staging_cleanup_execution_controlled_apply_execution_plan(
        apply_execution_review_id=execution_review["event_id"],
        planned_by="tester",
        plan_decision="prepared_for_controlled_cleanup_apply_execution_plan_preflight",
    )
    execution_preflight = service.staging_cleanup_execution_controlled_apply_execution_plan_preflight(
        apply_execution_plan_id=execution_plan["event_id"],
        requested_by="tester",
        preflight_decision="prepared_for_controlled_cleanup_apply_execution_plan_dry_run",
    )
    staging_before = test_db.fetch_one("SELECT COUNT(*) AS cnt FROM dataset2_staging_records")["cnt"]
    learning_before = test_db.fetch_one("SELECT COUNT(*) AS cnt FROM learning_samples")["cnt"]
    execution_plan_dry_run = service.staging_cleanup_execution_controlled_apply_execution_plan_dry_run(
        apply_execution_plan_preflight_id=execution_preflight["event_id"],
        simulated_by="tester",
        dry_run_decision="simulated_for_controlled_cleanup_apply_execution_plan_review",
        note="metadata-only apply execution plan dry-run",
    )
    staging_after = test_db.fetch_one("SELECT COUNT(*) AS cnt FROM dataset2_staging_records")["cnt"]
    learning_after = test_db.fetch_one("SELECT COUNT(*) AS cnt FROM learning_samples")["cnt"]

    assert execution_plan_dry_run["stage"] == "V5.6-P43"
    assert execution_plan_dry_run["status"] == "controlled_cleanup_apply_execution_plan_dry_run_ready_for_review"
    assert isinstance(execution_plan_dry_run["event_id"], int)
    assert execution_plan_dry_run["apply_execution_plan_preflight_id"] == execution_preflight["event_id"]
    assert execution_plan_dry_run["apply_execution_plan_id"] == execution_plan["event_id"]
    assert execution_plan_dry_run["apply_execution_review_id"] == execution_review["event_id"]
    assert execution_plan_dry_run["apply_execution_dry_run_id"] == execution_dry_run["event_id"]
    assert execution_plan_dry_run["dry_run"]["lock_key"] == execution_preflight["preflight"]["lock_key"]
    assert execution_plan_dry_run["dry_run"]["staging_record_count_before"] == 2
    assert execution_plan_dry_run["dry_run"]["preflight_staging_record_count"] == 2
    assert execution_plan_dry_run["dry_run"]["expected_staging_record_count_after"] == 2
    assert execution_plan_dry_run["dry_run"]["staging_count_still_matches"] is True
    assert execution_plan_dry_run["dry_run"]["learning_sample_count_before"] == 0
    assert execution_plan_dry_run["dry_run"]["expected_learning_sample_count_after"] == 0
    assert execution_plan_dry_run["dry_run"]["automated_operation_count"] >= 1
    assert execution_plan_dry_run["dry_run"]["manual_operation_count"] >= 1
    assert execution_plan_dry_run["dry_run"]["planned_operation_count"] >= 1
    assert execution_plan_dry_run["dry_run"]["execution_batch_count"] >= 1
    assert execution_plan_dry_run["dry_run"]["manual_backfill_batch_count"] >= 1
    assert execution_plan_dry_run["dry_run"]["simulated_mutation_count"] >= 1
    assert execution_plan_dry_run["dry_run"]["transaction_required"] is True
    assert execution_plan_dry_run["dry_run"]["rollback_required"] is True
    assert execution_plan_dry_run["dry_run"]["allowed_next_stage"] == "controlled_cleanup_apply_execution_plan_review"
    assert execution_plan_dry_run["dry_run"]["allowed_tables"] == ["dataset2_staging_records"]
    assert "learning_samples" in execution_plan_dry_run["dry_run"]["forbidden_tables"]
    assert execution_plan_dry_run["dry_run"]["contains_sql"] is False
    assert execution_plan_dry_run["dry_run"]["contains_executable_code"] is False
    assert execution_plan_dry_run["dry_run"]["can_execute_now"] is False
    assert execution_plan_dry_run["dry_run"]["record_bodies_included"] is False
    assert execution_plan_dry_run["dry_run"]["affected_rows_body_included"] is False
    assert execution_plan_dry_run["dry_run"]["writes_staging_records_now"] is False
    assert execution_plan_dry_run["dry_run"]["writes_learning_samples_now"] is False
    assert execution_plan_dry_run["dry_run"]["mutates_staging_records_now"] is False
    assert execution_plan_dry_run["decision"]["controlled_cleanup_apply_execution_plan_dry_run_recorded"] is True
    assert execution_plan_dry_run["decision"]["controlled_cleanup_apply_execution_plan_dry_run_ready_for_review"] is True
    assert execution_plan_dry_run["decision"]["cleanup_execution_approved_now"] is False
    assert execution_plan_dry_run["decision"]["cleanup_application_allowed_now"] is False
    assert execution_plan_dry_run["decision"]["cleanup_executed_now"] is False
    assert execution_plan_dry_run["decision"]["can_execute_cleanup_now"] is False
    assert execution_plan_dry_run["decision"]["writes_staging_records_now"] is False
    assert execution_plan_dry_run["decision"]["writes_learning_samples_now"] is False
    assert execution_plan_dry_run["decision"]["mutates_staging_records_now"] is False
    assert execution_plan_dry_run["decision"]["training_started_now"] is False
    assert execution_plan_dry_run["decision"]["can_start_training_now"] is False
    assert staging_after == staging_before
    assert learning_after == learning_before
    assert "evidence_package" not in execution_plan_dry_run
    assert "records" not in execution_plan_dry_run["dry_run"]
    check_status = {check["name"]: check["status"] for check in execution_plan_dry_run["checks"]}
    assert check_status["apply_execution_plan_preflight_ready_for_dry_run"] == "passed"
    assert check_status["staging_count_still_matches_preflight"] == "passed"
    assert check_status["aggregate_apply_execution_plan_simulation_present"] == "passed"
    assert check_status["manual_backfill_separated"] == "warning"
    assert check_status["cleanup_and_training_remain_blocked"] == "passed"

    dry_runs = service.list_staging_cleanup_execution_controlled_apply_execution_plan_dry_runs(limit=5)
    assert dry_runs[0]["id"] == execution_plan_dry_run["event_id"]
    assert dry_runs[0]["request"]["simulated_by"] == "tester"
    assert "evidence_package" not in dry_runs[0]


def test_dataset2_controlled_cleanup_apply_execution_plan_dry_run_review_is_metadata_only(tmp_path, test_db):
    pack = _write_dataset2_pack(
        tmp_path,
        [
            _record(
                pattern_id="CONTROLLED_APPLY_EXECUTION_PLAN_DRY_RUN_REVIEW_001",
                risk_level="medium_high",
                split_tag="train",
                observable_features=["['big_yang']", "high_volume"],
                evidence_summary="",
            ),
            _record(
                pattern_id="CONTROLLED_APPLY_EXECUTION_PLAN_DRY_RUN_REVIEW_002",
                action_label="RISK_ALERT",
                risk_level="high",
                split_tag="test",
            ),
        ],
    )
    service = Dataset2TrainingReadinessService()

    before_missing = service.list_staging_cleanup_execution_controlled_apply_execution_plan_dry_run_reviews(limit=5)
    missing = service.staging_cleanup_execution_controlled_apply_execution_plan_dry_run_review(
        apply_execution_plan_dry_run_id=999999,
        reviewed_by="tester",
    )
    after_missing = service.list_staging_cleanup_execution_controlled_apply_execution_plan_dry_run_reviews(limit=5)
    assert missing["status"] == "controlled_cleanup_apply_execution_plan_dry_run_review_blocked_missing_dry_run"
    assert missing["decision"]["writes_existing_event_now"] is False
    assert missing["decision"]["controlled_cleanup_apply_execution_plan_dry_run_review_accepted"] is False
    assert missing["decision"]["cleanup_executed_now"] is False
    assert missing["decision"]["training_started_now"] is False
    assert len(after_missing) == len(before_missing)

    blocked_preflight_source = _cleanup_execution_plan_preflight_chain(
        service,
        pack,
        {},
        suffix="blocked-apply-execution-plan-dry-run-review",
    )
    blocked_controlled = service.staging_cleanup_execution_controlled_dry_run(
        plan_preflight_id=blocked_preflight_source["event_id"],
        simulated_by="tester",
    )
    blocked_review = service.staging_cleanup_execution_controlled_dry_run_review(
        controlled_dry_run_id=blocked_controlled["event_id"],
        reviewed_by="tester",
    )
    blocked_approval = service.staging_cleanup_execution_controlled_approval(
        controlled_review_id=blocked_review["event_id"],
        approved_by="tester",
    )
    blocked_preflight = service.staging_cleanup_execution_controlled_preflight(
        controlled_approval_id=blocked_approval["event_id"],
        requested_by="tester",
    )
    blocked_apply = service.staging_cleanup_execution_controlled_apply_dry_run(
        controlled_preflight_id=blocked_preflight["event_id"],
        simulated_by="tester",
    )
    blocked_apply_review = service.staging_cleanup_execution_controlled_apply_dry_run_review(
        apply_dry_run_id=blocked_apply["event_id"],
        reviewed_by="tester",
    )
    blocked_apply_approval = service.staging_cleanup_execution_controlled_apply_approval(
        apply_review_id=blocked_apply_review["event_id"],
        approved_by="tester",
    )
    blocked_apply_preflight = service.staging_cleanup_execution_controlled_apply_preflight(
        apply_approval_id=blocked_apply_approval["event_id"],
        requested_by="tester",
    )
    blocked_execution_dry_run = service.staging_cleanup_execution_controlled_apply_execution_dry_run(
        apply_preflight_id=blocked_apply_preflight["event_id"],
        simulated_by="tester",
    )
    blocked_execution_review = service.staging_cleanup_execution_controlled_apply_execution_dry_run_review(
        apply_execution_dry_run_id=blocked_execution_dry_run["event_id"],
        reviewed_by="tester",
    )
    blocked_execution_plan = service.staging_cleanup_execution_controlled_apply_execution_plan(
        apply_execution_review_id=blocked_execution_review["event_id"],
        planned_by="tester",
    )
    blocked_plan_preflight = service.staging_cleanup_execution_controlled_apply_execution_plan_preflight(
        apply_execution_plan_id=blocked_execution_plan["event_id"],
        requested_by="tester",
    )
    blocked_plan_dry_run = service.staging_cleanup_execution_controlled_apply_execution_plan_dry_run(
        apply_execution_plan_preflight_id=blocked_plan_preflight["event_id"],
        simulated_by="tester",
    )
    blocked_plan_review = service.staging_cleanup_execution_controlled_apply_execution_plan_dry_run_review(
        apply_execution_plan_dry_run_id=blocked_plan_dry_run["event_id"],
        reviewed_by="tester",
    )
    assert blocked_plan_review["status"] == "controlled_cleanup_apply_execution_plan_dry_run_review_blocked"
    assert blocked_plan_review["decision"]["controlled_cleanup_apply_execution_plan_dry_run_review_recorded"] is True
    assert blocked_plan_review["decision"]["controlled_cleanup_apply_execution_plan_dry_run_review_accepted"] is False
    assert blocked_plan_review["decision"]["can_execute_cleanup_now"] is False
    assert blocked_plan_review["decision"]["writes_learning_samples_now"] is False
    assert blocked_plan_review["dry_run_summary"]["contains_sql"] is False
    assert blocked_plan_review["dry_run_summary"]["record_bodies_included"] is False

    plan_preflight = _cleanup_execution_plan_preflight_chain(
        service,
        pack,
        _manual_evidence_package(),
        suffix="ready-apply-execution-plan-dry-run-review",
    )
    controlled = service.staging_cleanup_execution_controlled_dry_run(
        plan_preflight_id=plan_preflight["event_id"],
        simulated_by="tester",
        dry_run_decision="simulated_for_controlled_cleanup_review",
    )
    review = service.staging_cleanup_execution_controlled_dry_run_review(
        controlled_dry_run_id=controlled["event_id"],
        reviewed_by="tester",
        review_decision="approved_for_controlled_cleanup_execution_review",
    )
    approval = service.staging_cleanup_execution_controlled_approval(
        controlled_review_id=review["event_id"],
        approved_by="tester",
        approval_decision="approved_for_controlled_cleanup_execution_preflight",
    )
    preflight = service.staging_cleanup_execution_controlled_preflight(
        controlled_approval_id=approval["event_id"],
        requested_by="tester",
        preflight_decision="prepared_for_controlled_cleanup_execution_apply_dry_run",
    )
    apply_dry_run = service.staging_cleanup_execution_controlled_apply_dry_run(
        controlled_preflight_id=preflight["event_id"],
        simulated_by="tester",
        dry_run_decision="simulated_for_controlled_cleanup_apply_review",
    )
    apply_review = service.staging_cleanup_execution_controlled_apply_dry_run_review(
        apply_dry_run_id=apply_dry_run["event_id"],
        reviewed_by="tester",
        review_decision="approved_for_controlled_cleanup_apply_execution_review",
    )
    apply_approval = service.staging_cleanup_execution_controlled_apply_approval(
        apply_review_id=apply_review["event_id"],
        approved_by="tester",
        approval_decision="approved_for_controlled_cleanup_apply_execution_preflight",
    )
    apply_preflight = service.staging_cleanup_execution_controlled_apply_preflight(
        apply_approval_id=apply_approval["event_id"],
        requested_by="tester",
        preflight_decision="prepared_for_controlled_cleanup_apply_execution_dry_run",
    )
    execution_dry_run = service.staging_cleanup_execution_controlled_apply_execution_dry_run(
        apply_preflight_id=apply_preflight["event_id"],
        simulated_by="tester",
        dry_run_decision="simulated_for_controlled_cleanup_apply_execution_review",
    )
    execution_review = service.staging_cleanup_execution_controlled_apply_execution_dry_run_review(
        apply_execution_dry_run_id=execution_dry_run["event_id"],
        reviewed_by="tester",
        review_decision="approved_for_controlled_cleanup_apply_execution_plan",
    )
    execution_plan = service.staging_cleanup_execution_controlled_apply_execution_plan(
        apply_execution_review_id=execution_review["event_id"],
        planned_by="tester",
        plan_decision="prepared_for_controlled_cleanup_apply_execution_plan_preflight",
    )
    execution_preflight = service.staging_cleanup_execution_controlled_apply_execution_plan_preflight(
        apply_execution_plan_id=execution_plan["event_id"],
        requested_by="tester",
        preflight_decision="prepared_for_controlled_cleanup_apply_execution_plan_dry_run",
    )
    execution_plan_dry_run = service.staging_cleanup_execution_controlled_apply_execution_plan_dry_run(
        apply_execution_plan_preflight_id=execution_preflight["event_id"],
        simulated_by="tester",
        dry_run_decision="simulated_for_controlled_cleanup_apply_execution_plan_review",
    )
    staging_before = test_db.fetch_one("SELECT COUNT(*) AS cnt FROM dataset2_staging_records")["cnt"]
    learning_before = test_db.fetch_one("SELECT COUNT(*) AS cnt FROM learning_samples")["cnt"]
    execution_plan_review = service.staging_cleanup_execution_controlled_apply_execution_plan_dry_run_review(
        apply_execution_plan_dry_run_id=execution_plan_dry_run["event_id"],
        reviewed_by="tester",
        review_decision="approved_for_controlled_cleanup_apply_execution_plan_execution_approval",
        note="metadata-only apply execution plan dry-run review",
    )
    staging_after = test_db.fetch_one("SELECT COUNT(*) AS cnt FROM dataset2_staging_records")["cnt"]
    learning_after = test_db.fetch_one("SELECT COUNT(*) AS cnt FROM learning_samples")["cnt"]

    assert execution_plan_review["stage"] == "V5.6-P43"
    assert execution_plan_review["status"] == "controlled_cleanup_apply_execution_plan_dry_run_review_accepted"
    assert isinstance(execution_plan_review["event_id"], int)
    assert execution_plan_review["apply_execution_plan_dry_run_id"] == execution_plan_dry_run["event_id"]
    assert execution_plan_review["apply_execution_plan_preflight_id"] == execution_preflight["event_id"]
    assert execution_plan_review["apply_execution_plan_id"] == execution_plan["event_id"]
    assert execution_plan_review["apply_execution_review_id"] == execution_review["event_id"]
    assert execution_plan_review["apply_execution_dry_run_id"] == execution_dry_run["event_id"]
    assert execution_plan_review["dry_run_summary"]["lock_key"] == execution_plan_dry_run["dry_run"]["lock_key"]
    assert execution_plan_review["dry_run_summary"]["staging_record_count_before"] == 2
    assert execution_plan_review["dry_run_summary"]["expected_staging_record_count_after"] == 2
    assert execution_plan_review["dry_run_summary"]["learning_sample_count_before"] == 0
    assert execution_plan_review["dry_run_summary"]["expected_learning_sample_count_after"] == 0
    assert execution_plan_review["dry_run_summary"]["automated_operation_count"] >= 1
    assert execution_plan_review["dry_run_summary"]["manual_operation_count"] >= 1
    assert execution_plan_review["dry_run_summary"]["planned_operation_count"] >= 1
    assert execution_plan_review["dry_run_summary"]["simulated_mutation_count"] >= 1
    assert execution_plan_review["dry_run_summary"]["transaction_required"] is True
    assert execution_plan_review["dry_run_summary"]["rollback_required"] is True
    assert execution_plan_review["dry_run_summary"]["allowed_tables"] == ["dataset2_staging_records"]
    assert "learning_samples" in execution_plan_review["dry_run_summary"]["forbidden_tables"]
    assert execution_plan_review["dry_run_summary"]["contains_sql"] is False
    assert execution_plan_review["dry_run_summary"]["contains_executable_code"] is False
    assert execution_plan_review["dry_run_summary"]["can_execute_now"] is False
    assert execution_plan_review["dry_run_summary"]["record_bodies_included"] is False
    assert execution_plan_review["dry_run_summary"]["affected_rows_body_included"] is False
    assert execution_plan_review["decision"]["controlled_cleanup_apply_execution_plan_dry_run_review_recorded"] is True
    assert execution_plan_review["decision"]["controlled_cleanup_apply_execution_plan_dry_run_review_accepted"] is True
    assert execution_plan_review["decision"]["cleanup_execution_approved_now"] is False
    assert execution_plan_review["decision"]["cleanup_application_allowed_now"] is False
    assert execution_plan_review["decision"]["cleanup_executed_now"] is False
    assert execution_plan_review["decision"]["can_execute_cleanup_now"] is False
    assert execution_plan_review["decision"]["writes_staging_records_now"] is False
    assert execution_plan_review["decision"]["writes_learning_samples_now"] is False
    assert execution_plan_review["decision"]["mutates_staging_records_now"] is False
    assert execution_plan_review["decision"]["training_started_now"] is False
    assert execution_plan_review["decision"]["can_start_training_now"] is False
    assert staging_after == staging_before
    assert learning_after == learning_before
    assert "evidence_package" not in execution_plan_review
    assert "records" not in execution_plan_review["dry_run_summary"]
    check_status = {check["name"]: check["status"] for check in execution_plan_review["checks"]}
    assert check_status["apply_execution_plan_dry_run_ready_for_review"] == "passed"
    assert check_status["aggregate_apply_execution_plan_simulation_present"] == "passed"
    assert check_status["manual_backfill_separated"] == "warning"
    assert check_status["review_decision_allows_future_execution_approval_only"] == "passed"
    assert check_status["cleanup_and_training_remain_blocked"] == "passed"

    reviews = service.list_staging_cleanup_execution_controlled_apply_execution_plan_dry_run_reviews(limit=5)
    assert reviews[0]["id"] == execution_plan_review["event_id"]
    assert reviews[0]["review"]["reviewed_by"] == "tester"
    assert "evidence_package" not in reviews[0]


def test_dataset2_controlled_cleanup_apply_execution_plan_execution_approval_is_metadata_only(tmp_path, test_db):
    pack = _write_dataset2_pack(
        tmp_path,
        [
            _record(
                pattern_id="CONTROLLED_APPLY_EXECUTION_PLAN_EXECUTION_APPROVAL_001",
                risk_level="medium_high",
                split_tag="train",
                observable_features=["['big_yang']", "high_volume"],
                evidence_summary="",
            ),
            _record(
                pattern_id="CONTROLLED_APPLY_EXECUTION_PLAN_EXECUTION_APPROVAL_002",
                action_label="RISK_ALERT",
                risk_level="high",
                split_tag="test",
            ),
        ],
    )
    service = Dataset2TrainingReadinessService()

    before_missing = service.list_staging_cleanup_execution_controlled_apply_execution_plan_execution_approvals(limit=5)
    missing = service.staging_cleanup_execution_controlled_apply_execution_plan_execution_approval(
        apply_execution_plan_dry_run_review_id=999999,
        approved_by="tester",
    )
    after_missing = service.list_staging_cleanup_execution_controlled_apply_execution_plan_execution_approvals(limit=5)
    assert missing["status"] == "controlled_cleanup_apply_execution_plan_execution_approval_blocked_missing_review"
    assert missing["decision"]["writes_existing_event_now"] is False
    assert missing["decision"]["controlled_cleanup_apply_execution_plan_execution_approval_accepted"] is False
    assert missing["decision"]["cleanup_executed_now"] is False
    assert missing["decision"]["training_started_now"] is False
    assert len(after_missing) == len(before_missing)

    blocked_preflight_source = _cleanup_execution_plan_preflight_chain(
        service,
        pack,
        {},
        suffix="blocked-apply-execution-plan-execution-approval",
    )
    blocked_controlled = service.staging_cleanup_execution_controlled_dry_run(
        plan_preflight_id=blocked_preflight_source["event_id"],
        simulated_by="tester",
    )
    blocked_review = service.staging_cleanup_execution_controlled_dry_run_review(
        controlled_dry_run_id=blocked_controlled["event_id"],
        reviewed_by="tester",
    )
    blocked_approval = service.staging_cleanup_execution_controlled_approval(
        controlled_review_id=blocked_review["event_id"],
        approved_by="tester",
    )
    blocked_preflight = service.staging_cleanup_execution_controlled_preflight(
        controlled_approval_id=blocked_approval["event_id"],
        requested_by="tester",
    )
    blocked_apply = service.staging_cleanup_execution_controlled_apply_dry_run(
        controlled_preflight_id=blocked_preflight["event_id"],
        simulated_by="tester",
    )
    blocked_apply_review = service.staging_cleanup_execution_controlled_apply_dry_run_review(
        apply_dry_run_id=blocked_apply["event_id"],
        reviewed_by="tester",
    )
    blocked_apply_approval = service.staging_cleanup_execution_controlled_apply_approval(
        apply_review_id=blocked_apply_review["event_id"],
        approved_by="tester",
    )
    blocked_apply_preflight = service.staging_cleanup_execution_controlled_apply_preflight(
        apply_approval_id=blocked_apply_approval["event_id"],
        requested_by="tester",
    )
    blocked_execution_dry_run = service.staging_cleanup_execution_controlled_apply_execution_dry_run(
        apply_preflight_id=blocked_apply_preflight["event_id"],
        simulated_by="tester",
    )
    blocked_execution_review = service.staging_cleanup_execution_controlled_apply_execution_dry_run_review(
        apply_execution_dry_run_id=blocked_execution_dry_run["event_id"],
        reviewed_by="tester",
    )
    blocked_execution_plan = service.staging_cleanup_execution_controlled_apply_execution_plan(
        apply_execution_review_id=blocked_execution_review["event_id"],
        planned_by="tester",
    )
    blocked_plan_preflight = service.staging_cleanup_execution_controlled_apply_execution_plan_preflight(
        apply_execution_plan_id=blocked_execution_plan["event_id"],
        requested_by="tester",
    )
    blocked_plan_dry_run = service.staging_cleanup_execution_controlled_apply_execution_plan_dry_run(
        apply_execution_plan_preflight_id=blocked_plan_preflight["event_id"],
        simulated_by="tester",
    )
    blocked_plan_review = service.staging_cleanup_execution_controlled_apply_execution_plan_dry_run_review(
        apply_execution_plan_dry_run_id=blocked_plan_dry_run["event_id"],
        reviewed_by="tester",
    )
    blocked_plan_approval = service.staging_cleanup_execution_controlled_apply_execution_plan_execution_approval(
        apply_execution_plan_dry_run_review_id=blocked_plan_review["event_id"],
        approved_by="tester",
    )
    assert blocked_plan_approval["status"] == "controlled_cleanup_apply_execution_plan_execution_approval_blocked"
    assert blocked_plan_approval["decision"]["controlled_cleanup_apply_execution_plan_execution_approval_recorded"] is True
    assert blocked_plan_approval["decision"]["controlled_cleanup_apply_execution_plan_execution_approval_accepted"] is False
    assert blocked_plan_approval["decision"]["can_execute_cleanup_now"] is False
    assert blocked_plan_approval["decision"]["writes_learning_samples_now"] is False
    assert blocked_plan_approval["approval_scope"]["contains_sql"] is False
    assert blocked_plan_approval["approval_scope"]["record_bodies_included"] is False

    plan_preflight = _cleanup_execution_plan_preflight_chain(
        service,
        pack,
        _manual_evidence_package(),
        suffix="ready-apply-execution-plan-execution-approval",
    )
    controlled = service.staging_cleanup_execution_controlled_dry_run(
        plan_preflight_id=plan_preflight["event_id"],
        simulated_by="tester",
        dry_run_decision="simulated_for_controlled_cleanup_review",
    )
    review = service.staging_cleanup_execution_controlled_dry_run_review(
        controlled_dry_run_id=controlled["event_id"],
        reviewed_by="tester",
        review_decision="approved_for_controlled_cleanup_execution_review",
    )
    approval = service.staging_cleanup_execution_controlled_approval(
        controlled_review_id=review["event_id"],
        approved_by="tester",
        approval_decision="approved_for_controlled_cleanup_execution_preflight",
    )
    preflight = service.staging_cleanup_execution_controlled_preflight(
        controlled_approval_id=approval["event_id"],
        requested_by="tester",
        preflight_decision="prepared_for_controlled_cleanup_execution_apply_dry_run",
    )
    apply_dry_run = service.staging_cleanup_execution_controlled_apply_dry_run(
        controlled_preflight_id=preflight["event_id"],
        simulated_by="tester",
        dry_run_decision="simulated_for_controlled_cleanup_apply_review",
    )
    apply_review = service.staging_cleanup_execution_controlled_apply_dry_run_review(
        apply_dry_run_id=apply_dry_run["event_id"],
        reviewed_by="tester",
        review_decision="approved_for_controlled_cleanup_apply_execution_review",
    )
    apply_approval = service.staging_cleanup_execution_controlled_apply_approval(
        apply_review_id=apply_review["event_id"],
        approved_by="tester",
        approval_decision="approved_for_controlled_cleanup_apply_execution_preflight",
    )
    apply_preflight = service.staging_cleanup_execution_controlled_apply_preflight(
        apply_approval_id=apply_approval["event_id"],
        requested_by="tester",
        preflight_decision="prepared_for_controlled_cleanup_apply_execution_dry_run",
    )
    execution_dry_run = service.staging_cleanup_execution_controlled_apply_execution_dry_run(
        apply_preflight_id=apply_preflight["event_id"],
        simulated_by="tester",
        dry_run_decision="simulated_for_controlled_cleanup_apply_execution_review",
    )
    execution_review = service.staging_cleanup_execution_controlled_apply_execution_dry_run_review(
        apply_execution_dry_run_id=execution_dry_run["event_id"],
        reviewed_by="tester",
        review_decision="approved_for_controlled_cleanup_apply_execution_plan",
    )
    execution_plan = service.staging_cleanup_execution_controlled_apply_execution_plan(
        apply_execution_review_id=execution_review["event_id"],
        planned_by="tester",
        plan_decision="prepared_for_controlled_cleanup_apply_execution_plan_preflight",
    )
    execution_preflight = service.staging_cleanup_execution_controlled_apply_execution_plan_preflight(
        apply_execution_plan_id=execution_plan["event_id"],
        requested_by="tester",
        preflight_decision="prepared_for_controlled_cleanup_apply_execution_plan_dry_run",
    )
    execution_plan_dry_run = service.staging_cleanup_execution_controlled_apply_execution_plan_dry_run(
        apply_execution_plan_preflight_id=execution_preflight["event_id"],
        simulated_by="tester",
        dry_run_decision="simulated_for_controlled_cleanup_apply_execution_plan_review",
    )
    execution_plan_review = service.staging_cleanup_execution_controlled_apply_execution_plan_dry_run_review(
        apply_execution_plan_dry_run_id=execution_plan_dry_run["event_id"],
        reviewed_by="tester",
        review_decision="approved_for_controlled_cleanup_apply_execution_plan_execution_approval",
    )
    staging_before = test_db.fetch_one("SELECT COUNT(*) AS cnt FROM dataset2_staging_records")["cnt"]
    learning_before = test_db.fetch_one("SELECT COUNT(*) AS cnt FROM learning_samples")["cnt"]
    execution_plan_approval = service.staging_cleanup_execution_controlled_apply_execution_plan_execution_approval(
        apply_execution_plan_dry_run_review_id=execution_plan_review["event_id"],
        approved_by="tester",
        approval_decision="approved_for_controlled_cleanup_apply_execution_plan_execution_preflight",
        note="metadata-only apply execution plan execution approval",
    )
    staging_after = test_db.fetch_one("SELECT COUNT(*) AS cnt FROM dataset2_staging_records")["cnt"]
    learning_after = test_db.fetch_one("SELECT COUNT(*) AS cnt FROM learning_samples")["cnt"]

    assert execution_plan_approval["stage"] == "V5.6-P43"
    assert execution_plan_approval["status"] == "controlled_cleanup_apply_execution_plan_execution_approval_ready_for_preflight"
    assert isinstance(execution_plan_approval["event_id"], int)
    assert execution_plan_approval["apply_execution_plan_dry_run_review_id"] == execution_plan_review["event_id"]
    assert execution_plan_approval["apply_execution_plan_dry_run_id"] == execution_plan_dry_run["event_id"]
    assert execution_plan_approval["apply_execution_plan_preflight_id"] == execution_preflight["event_id"]
    assert execution_plan_approval["apply_execution_plan_id"] == execution_plan["event_id"]
    assert execution_plan_approval["approval_scope"]["lock_key"] == execution_plan_review["dry_run_summary"]["lock_key"]
    assert execution_plan_approval["approval_scope"]["approval_scope"] == "controlled_apply_execution_plan_execution_preflight_only"
    assert execution_plan_approval["approval_scope"]["allowed_next_stage"] == "controlled_cleanup_apply_execution_plan_execution_preflight"
    assert execution_plan_approval["approval_scope"]["requires_preflight"] is True
    assert execution_plan_approval["approval_scope"]["requires_transaction"] is True
    assert execution_plan_approval["approval_scope"]["requires_rollback"] is True
    assert execution_plan_approval["approval_scope"]["automated_operation_count"] >= 1
    assert execution_plan_approval["approval_scope"]["manual_operation_count"] >= 1
    assert execution_plan_approval["approval_scope"]["planned_operation_count"] >= 1
    assert execution_plan_approval["approval_scope"]["simulated_mutation_count"] >= 1
    assert execution_plan_approval["approval_scope"]["staging_record_count_before"] == 2
    assert execution_plan_approval["approval_scope"]["expected_staging_record_count_after"] == 2
    assert execution_plan_approval["approval_scope"]["learning_sample_count_before"] == 0
    assert execution_plan_approval["approval_scope"]["expected_learning_sample_count_after"] == 0
    assert execution_plan_approval["approval_scope"]["allowed_tables"] == ["dataset2_staging_records"]
    assert "learning_samples" in execution_plan_approval["approval_scope"]["forbidden_tables"]
    assert execution_plan_approval["approval_scope"]["contains_sql"] is False
    assert execution_plan_approval["approval_scope"]["contains_executable_code"] is False
    assert execution_plan_approval["approval_scope"]["can_execute_now"] is False
    assert execution_plan_approval["approval_scope"]["record_bodies_included"] is False
    assert execution_plan_approval["approval_scope"]["affected_rows_body_included"] is False
    assert execution_plan_approval["decision"]["controlled_cleanup_apply_execution_plan_execution_approval_recorded"] is True
    assert execution_plan_approval["decision"]["controlled_cleanup_apply_execution_plan_execution_approval_accepted"] is True
    assert execution_plan_approval["decision"]["cleanup_execution_approved_now"] is False
    assert execution_plan_approval["decision"]["cleanup_application_allowed_now"] is False
    assert execution_plan_approval["decision"]["cleanup_executed_now"] is False
    assert execution_plan_approval["decision"]["can_execute_cleanup_now"] is False
    assert execution_plan_approval["decision"]["writes_staging_records_now"] is False
    assert execution_plan_approval["decision"]["writes_learning_samples_now"] is False
    assert execution_plan_approval["decision"]["mutates_staging_records_now"] is False
    assert execution_plan_approval["decision"]["training_started_now"] is False
    assert execution_plan_approval["decision"]["can_start_training_now"] is False
    assert staging_after == staging_before
    assert learning_after == learning_before
    assert "evidence_package" not in execution_plan_approval
    assert "records" not in execution_plan_approval["approval_scope"]
    check_status = {check["name"]: check["status"] for check in execution_plan_approval["checks"]}
    assert check_status["apply_execution_plan_dry_run_review_accepted"] == "passed"
    assert check_status["approval_scope_has_preflight_gate"] == "passed"
    assert check_status["aggregate_apply_execution_plan_simulation_present"] == "passed"
    assert check_status["manual_backfill_separated"] == "warning"
    assert check_status["approval_decision_allows_preflight_only"] == "passed"
    assert check_status["cleanup_and_training_remain_blocked"] == "passed"

    approvals = service.list_staging_cleanup_execution_controlled_apply_execution_plan_execution_approvals(limit=5)
    assert approvals[0]["id"] == execution_plan_approval["event_id"]
    assert approvals[0]["approval"]["approved_by"] == "tester"
    assert "evidence_package" not in approvals[0]


def test_dataset2_controlled_cleanup_apply_execution_plan_execution_preflight_is_metadata_only(tmp_path, test_db):
    pack = _write_dataset2_pack(
        tmp_path,
        [
            _record(
                pattern_id="CONTROLLED_APPLY_EXECUTION_PLAN_EXECUTION_PREFLIGHT_001",
                risk_level="medium_high",
                split_tag="train",
                observable_features=["['big_yang']", "high_volume"],
                evidence_summary="",
            ),
            _record(
                pattern_id="CONTROLLED_APPLY_EXECUTION_PLAN_EXECUTION_PREFLIGHT_002",
                action_label="RISK_ALERT",
                risk_level="high",
                split_tag="test",
            ),
        ],
    )
    service = Dataset2TrainingReadinessService()

    before_missing = service.list_staging_cleanup_execution_controlled_apply_execution_plan_execution_preflights(limit=5)
    missing = service.staging_cleanup_execution_controlled_apply_execution_plan_execution_preflight(
        apply_execution_plan_execution_approval_id=999999,
        requested_by="tester",
    )
    after_missing = service.list_staging_cleanup_execution_controlled_apply_execution_plan_execution_preflights(limit=5)
    assert missing["status"] == "controlled_cleanup_apply_execution_plan_execution_preflight_blocked_missing_approval"
    assert missing["decision"]["writes_existing_event_now"] is False
    assert missing["decision"]["controlled_cleanup_apply_execution_plan_execution_preflight_ready_for_dry_run"] is False
    assert missing["decision"]["cleanup_executed_now"] is False
    assert missing["decision"]["training_started_now"] is False
    assert len(after_missing) == len(before_missing)

    chain = _controlled_apply_execution_plan_execution_approval_chain(
        service,
        pack,
        _manual_evidence_package(),
        suffix="ready-apply-execution-plan-execution-preflight",
    )
    execution_plan_approval = chain["execution_plan_approval"]
    staging_before = test_db.fetch_one("SELECT COUNT(*) AS cnt FROM dataset2_staging_records")["cnt"]
    learning_before = test_db.fetch_one("SELECT COUNT(*) AS cnt FROM learning_samples")["cnt"]
    execution_plan_preflight = service.staging_cleanup_execution_controlled_apply_execution_plan_execution_preflight(
        apply_execution_plan_execution_approval_id=execution_plan_approval["event_id"],
        requested_by="tester",
        preflight_decision="prepared_for_controlled_cleanup_apply_execution_plan_execution_dry_run",
        note="metadata-only apply execution plan execution preflight",
    )
    staging_after = test_db.fetch_one("SELECT COUNT(*) AS cnt FROM dataset2_staging_records")["cnt"]
    learning_after = test_db.fetch_one("SELECT COUNT(*) AS cnt FROM learning_samples")["cnt"]

    assert execution_plan_preflight["stage"] == "V5.6-P43"
    assert execution_plan_preflight["status"] == "controlled_cleanup_apply_execution_plan_execution_preflight_ready_for_dry_run"
    assert isinstance(execution_plan_preflight["event_id"], int)
    assert execution_plan_preflight["apply_execution_plan_execution_approval_id"] == execution_plan_approval["event_id"]
    assert execution_plan_preflight["apply_execution_plan_dry_run_review_id"] == chain["execution_plan_review"]["event_id"]
    assert execution_plan_preflight["apply_execution_plan_dry_run_id"] == chain["execution_plan_dry_run"]["event_id"]
    assert execution_plan_preflight["apply_execution_plan_preflight_id"] == chain["execution_plan_preflight"]["event_id"]
    assert execution_plan_preflight["apply_execution_plan_id"] == chain["execution_plan"]["event_id"]
    assert execution_plan_preflight["preflight"]["lock_key"] == execution_plan_approval["approval_scope"]["lock_key"]
    assert execution_plan_preflight["preflight"]["allowed_next_stage"] == "controlled_cleanup_apply_execution_plan_execution_dry_run"
    assert execution_plan_preflight["preflight"]["staging_record_count"] == 2
    assert execution_plan_preflight["preflight"]["approval_staging_record_count"] == 2
    assert execution_plan_preflight["preflight"]["staging_count_still_matches"] is True
    assert execution_plan_preflight["preflight"]["learning_sample_count"] == 0
    assert execution_plan_preflight["preflight"]["approval_learning_sample_count"] == 0
    assert execution_plan_preflight["preflight"]["learning_sample_count_still_matches"] is True
    assert execution_plan_preflight["preflight"]["automated_operation_count"] >= 1
    assert execution_plan_preflight["preflight"]["manual_operation_count"] >= 1
    assert execution_plan_preflight["preflight"]["planned_operation_count"] >= 1
    assert execution_plan_preflight["preflight"]["simulated_mutation_count"] >= 1
    assert execution_plan_preflight["preflight"]["transaction_required"] is True
    assert execution_plan_preflight["preflight"]["rollback_required"] is True
    assert execution_plan_preflight["preflight"]["allowed_tables"] == ["dataset2_staging_records"]
    assert "learning_samples" in execution_plan_preflight["preflight"]["forbidden_tables"]
    assert execution_plan_preflight["preflight"]["contains_sql"] is False
    assert execution_plan_preflight["preflight"]["contains_executable_code"] is False
    assert execution_plan_preflight["preflight"]["can_execute_now"] is False
    assert execution_plan_preflight["preflight"]["record_bodies_included"] is False
    assert execution_plan_preflight["preflight"]["affected_rows_body_included"] is False
    assert execution_plan_preflight["decision"]["controlled_cleanup_apply_execution_plan_execution_preflight_recorded"] is True
    assert execution_plan_preflight["decision"]["controlled_cleanup_apply_execution_plan_execution_preflight_ready_for_dry_run"] is True
    assert execution_plan_preflight["decision"]["cleanup_execution_approved_now"] is False
    assert execution_plan_preflight["decision"]["cleanup_application_allowed_now"] is False
    assert execution_plan_preflight["decision"]["cleanup_executed_now"] is False
    assert execution_plan_preflight["decision"]["can_execute_cleanup_now"] is False
    assert execution_plan_preflight["decision"]["writes_staging_records_now"] is False
    assert execution_plan_preflight["decision"]["writes_learning_samples_now"] is False
    assert execution_plan_preflight["decision"]["mutates_staging_records_now"] is False
    assert execution_plan_preflight["decision"]["training_started_now"] is False
    assert execution_plan_preflight["decision"]["can_start_training_now"] is False
    assert staging_after == staging_before
    assert learning_after == learning_before
    assert "evidence_package" not in execution_plan_preflight
    assert "records" not in execution_plan_preflight["preflight"]
    check_status = {check["name"]: check["status"] for check in execution_plan_preflight["checks"]}
    assert check_status["apply_execution_plan_execution_approval_accepted"] == "passed"
    assert check_status["lock_key_present"] == "passed"
    assert check_status["staging_count_matches_approval"] == "passed"
    assert check_status["learning_samples_unchanged"] == "passed"
    assert check_status["operation_scope_present"] == "passed"
    assert check_status["manual_backfill_separated"] == "warning"
    assert check_status["preflight_decision_allows_dry_run_only"] == "passed"
    assert check_status["cleanup_and_training_remain_blocked"] == "passed"

    rejected = service.staging_cleanup_execution_controlled_apply_execution_plan_execution_preflight(
        apply_execution_plan_execution_approval_id=execution_plan_approval["event_id"],
        requested_by="tester",
        preflight_decision="rejected",
    )
    assert rejected["status"] == "controlled_cleanup_apply_execution_plan_execution_preflight_blocked"
    assert rejected["decision"]["controlled_cleanup_apply_execution_plan_execution_preflight_recorded"] is True
    assert rejected["decision"]["controlled_cleanup_apply_execution_plan_execution_preflight_ready_for_dry_run"] is False
    assert rejected["decision"]["can_execute_cleanup_now"] is False
    assert rejected["decision"]["writes_learning_samples_now"] is False

    preflights = service.list_staging_cleanup_execution_controlled_apply_execution_plan_execution_preflights(limit=5)
    assert preflights[0]["id"] == rejected["event_id"]
    assert preflights[1]["id"] == execution_plan_preflight["event_id"]
    assert preflights[1]["request"]["requested_by"] == "tester"
    assert "evidence_package" not in preflights[1]


def test_dataset2_controlled_cleanup_apply_execution_plan_execution_dry_run_is_metadata_only(tmp_path, test_db):
    pack = _write_dataset2_pack(
        tmp_path,
        [
            _record(
                pattern_id="CONTROLLED_APPLY_EXECUTION_PLAN_EXECUTION_DRY_RUN_001",
                risk_level="medium_high",
                split_tag="train",
                observable_features=["['big_yang']", "high_volume"],
                evidence_summary="",
            ),
            _record(
                pattern_id="CONTROLLED_APPLY_EXECUTION_PLAN_EXECUTION_DRY_RUN_002",
                action_label="RISK_ALERT",
                risk_level="high",
                split_tag="test",
            ),
        ],
    )
    service = Dataset2TrainingReadinessService()

    before_missing = service.list_staging_cleanup_execution_controlled_apply_execution_plan_execution_dry_runs(limit=5)
    missing = service.staging_cleanup_execution_controlled_apply_execution_plan_execution_dry_run(
        apply_execution_plan_execution_preflight_id=999999,
        simulated_by="tester",
    )
    after_missing = service.list_staging_cleanup_execution_controlled_apply_execution_plan_execution_dry_runs(limit=5)
    assert missing["status"] == "controlled_cleanup_apply_execution_plan_execution_dry_run_blocked_missing_preflight"
    assert missing["decision"]["writes_existing_event_now"] is False
    assert missing["decision"]["controlled_cleanup_apply_execution_plan_execution_dry_run_ready_for_review"] is False
    assert missing["decision"]["cleanup_executed_now"] is False
    assert missing["decision"]["training_started_now"] is False
    assert len(after_missing) == len(before_missing)

    chain = _controlled_apply_execution_plan_execution_approval_chain(
        service,
        pack,
        _manual_evidence_package(),
        suffix="ready-apply-execution-plan-execution-dry-run",
    )
    execution_plan_preflight = service.staging_cleanup_execution_controlled_apply_execution_plan_execution_preflight(
        apply_execution_plan_execution_approval_id=chain["execution_plan_approval"]["event_id"],
        requested_by="tester",
        preflight_decision="prepared_for_controlled_cleanup_apply_execution_plan_execution_dry_run",
    )
    staging_before = test_db.fetch_one("SELECT COUNT(*) AS cnt FROM dataset2_staging_records")["cnt"]
    learning_before = test_db.fetch_one("SELECT COUNT(*) AS cnt FROM learning_samples")["cnt"]
    execution_plan_dry_run = service.staging_cleanup_execution_controlled_apply_execution_plan_execution_dry_run(
        apply_execution_plan_execution_preflight_id=execution_plan_preflight["event_id"],
        simulated_by="tester",
        dry_run_decision="simulated_for_controlled_cleanup_apply_execution_plan_execution_review",
        note="metadata-only apply execution plan execution dry-run",
    )
    staging_after = test_db.fetch_one("SELECT COUNT(*) AS cnt FROM dataset2_staging_records")["cnt"]
    learning_after = test_db.fetch_one("SELECT COUNT(*) AS cnt FROM learning_samples")["cnt"]

    assert execution_plan_dry_run["stage"] == "V5.6-P43"
    assert execution_plan_dry_run["status"] == "controlled_cleanup_apply_execution_plan_execution_dry_run_ready_for_review"
    assert isinstance(execution_plan_dry_run["event_id"], int)
    assert execution_plan_dry_run["apply_execution_plan_execution_preflight_id"] == execution_plan_preflight["event_id"]
    assert execution_plan_dry_run["apply_execution_plan_execution_approval_id"] == chain["execution_plan_approval"]["event_id"]
    assert execution_plan_dry_run["apply_execution_plan_dry_run_review_id"] == chain["execution_plan_review"]["event_id"]
    assert execution_plan_dry_run["apply_execution_plan_dry_run_id"] == chain["execution_plan_dry_run"]["event_id"]
    assert execution_plan_dry_run["apply_execution_plan_preflight_id"] == chain["execution_plan_preflight"]["event_id"]
    assert execution_plan_dry_run["apply_execution_plan_id"] == chain["execution_plan"]["event_id"]
    assert execution_plan_dry_run["dry_run"]["lock_key"] == execution_plan_preflight["preflight"]["lock_key"]
    assert execution_plan_dry_run["dry_run"]["allowed_next_stage"] == "controlled_cleanup_apply_execution_plan_execution_review"
    assert execution_plan_dry_run["dry_run"]["staging_record_count_before"] == 2
    assert execution_plan_dry_run["dry_run"]["preflight_staging_record_count"] == 2
    assert execution_plan_dry_run["dry_run"]["expected_staging_record_count_after"] == 2
    assert execution_plan_dry_run["dry_run"]["staging_count_still_matches"] is True
    assert execution_plan_dry_run["dry_run"]["learning_sample_count_before"] == 0
    assert execution_plan_dry_run["dry_run"]["preflight_learning_sample_count"] == 0
    assert execution_plan_dry_run["dry_run"]["expected_learning_sample_count_after"] == 0
    assert execution_plan_dry_run["dry_run"]["learning_sample_count_still_matches"] is True
    assert execution_plan_dry_run["dry_run"]["automated_operation_count"] >= 1
    assert execution_plan_dry_run["dry_run"]["manual_operation_count"] >= 1
    assert execution_plan_dry_run["dry_run"]["planned_operation_count"] >= 1
    assert execution_plan_dry_run["dry_run"]["simulated_mutation_count"] >= 1
    assert execution_plan_dry_run["dry_run"]["transaction_required"] is True
    assert execution_plan_dry_run["dry_run"]["rollback_required"] is True
    assert execution_plan_dry_run["dry_run"]["allowed_tables"] == ["dataset2_staging_records"]
    assert "learning_samples" in execution_plan_dry_run["dry_run"]["forbidden_tables"]
    assert execution_plan_dry_run["dry_run"]["contains_sql"] is False
    assert execution_plan_dry_run["dry_run"]["contains_executable_code"] is False
    assert execution_plan_dry_run["dry_run"]["can_execute_now"] is False
    assert execution_plan_dry_run["dry_run"]["record_bodies_included"] is False
    assert execution_plan_dry_run["dry_run"]["affected_rows_body_included"] is False
    assert execution_plan_dry_run["decision"]["controlled_cleanup_apply_execution_plan_execution_dry_run_recorded"] is True
    assert execution_plan_dry_run["decision"]["controlled_cleanup_apply_execution_plan_execution_dry_run_ready_for_review"] is True
    assert execution_plan_dry_run["decision"]["cleanup_execution_approved_now"] is False
    assert execution_plan_dry_run["decision"]["cleanup_application_allowed_now"] is False
    assert execution_plan_dry_run["decision"]["cleanup_executed_now"] is False
    assert execution_plan_dry_run["decision"]["can_execute_cleanup_now"] is False
    assert execution_plan_dry_run["decision"]["writes_staging_records_now"] is False
    assert execution_plan_dry_run["decision"]["writes_learning_samples_now"] is False
    assert execution_plan_dry_run["decision"]["mutates_staging_records_now"] is False
    assert execution_plan_dry_run["decision"]["training_started_now"] is False
    assert execution_plan_dry_run["decision"]["can_start_training_now"] is False
    assert staging_after == staging_before
    assert learning_after == learning_before
    assert "evidence_package" not in execution_plan_dry_run
    assert "records" not in execution_plan_dry_run["dry_run"]
    check_status = {check["name"]: check["status"] for check in execution_plan_dry_run["checks"]}
    assert check_status["apply_execution_plan_execution_preflight_ready_for_dry_run"] == "passed"
    assert check_status["lock_key_present"] == "passed"
    assert check_status["staging_count_still_matches_preflight"] == "passed"
    assert check_status["learning_samples_unchanged"] == "passed"
    assert check_status["aggregate_apply_execution_plan_execution_simulation_present"] == "passed"
    assert check_status["manual_backfill_separated"] == "warning"
    assert check_status["dry_run_decision_allows_review_only"] == "passed"
    assert check_status["cleanup_and_training_remain_blocked"] == "passed"

    rejected = service.staging_cleanup_execution_controlled_apply_execution_plan_execution_dry_run(
        apply_execution_plan_execution_preflight_id=execution_plan_preflight["event_id"],
        simulated_by="tester",
        dry_run_decision="rejected",
    )
    assert rejected["status"] == "controlled_cleanup_apply_execution_plan_execution_dry_run_blocked"
    assert rejected["decision"]["controlled_cleanup_apply_execution_plan_execution_dry_run_recorded"] is True
    assert rejected["decision"]["controlled_cleanup_apply_execution_plan_execution_dry_run_ready_for_review"] is False
    assert rejected["decision"]["can_execute_cleanup_now"] is False
    assert rejected["decision"]["writes_learning_samples_now"] is False

    dry_runs = service.list_staging_cleanup_execution_controlled_apply_execution_plan_execution_dry_runs(limit=5)
    assert dry_runs[0]["id"] == rejected["event_id"]
    assert dry_runs[1]["id"] == execution_plan_dry_run["event_id"]
    assert dry_runs[1]["request"]["simulated_by"] == "tester"
    assert "evidence_package" not in dry_runs[1]


def test_dataset2_controlled_cleanup_apply_execution_plan_execution_dry_run_review_is_metadata_only(
    tmp_path,
    test_db,
):
    pack = _write_dataset2_pack(
        tmp_path,
        [
            _record(
                pattern_id="CONTROLLED_APPLY_EXECUTION_PLAN_EXECUTION_DRY_RUN_REVIEW_001",
                risk_level="medium_high",
                split_tag="train",
                observable_features=["['big_yang']", "high_volume"],
                evidence_summary="",
            ),
            _record(
                pattern_id="CONTROLLED_APPLY_EXECUTION_PLAN_EXECUTION_DRY_RUN_REVIEW_002",
                action_label="RISK_ALERT",
                risk_level="high",
                split_tag="test",
            ),
        ],
    )
    service = Dataset2TrainingReadinessService()

    before_missing = (
        service.list_staging_cleanup_execution_controlled_apply_execution_plan_execution_dry_run_reviews(limit=5)
    )
    missing = service.staging_cleanup_execution_controlled_apply_execution_plan_execution_dry_run_review(
        apply_execution_plan_execution_dry_run_id=999999,
        reviewed_by="tester",
    )
    after_missing = (
        service.list_staging_cleanup_execution_controlled_apply_execution_plan_execution_dry_run_reviews(limit=5)
    )
    assert missing["status"] == "controlled_cleanup_apply_execution_plan_execution_dry_run_review_blocked_missing_dry_run"
    assert missing["decision"]["writes_existing_event_now"] is False
    assert missing["decision"]["controlled_cleanup_apply_execution_plan_execution_dry_run_review_accepted"] is False
    assert missing["decision"]["cleanup_executed_now"] is False
    assert missing["decision"]["training_started_now"] is False
    assert len(after_missing) == len(before_missing)

    chain = _controlled_apply_execution_plan_execution_approval_chain(
        service,
        pack,
        _manual_evidence_package(),
        suffix="ready-apply-execution-plan-execution-dry-run-review",
    )
    execution_plan_preflight = service.staging_cleanup_execution_controlled_apply_execution_plan_execution_preflight(
        apply_execution_plan_execution_approval_id=chain["execution_plan_approval"]["event_id"],
        requested_by="tester",
        preflight_decision="prepared_for_controlled_cleanup_apply_execution_plan_execution_dry_run",
    )
    execution_plan_dry_run = service.staging_cleanup_execution_controlled_apply_execution_plan_execution_dry_run(
        apply_execution_plan_execution_preflight_id=execution_plan_preflight["event_id"],
        simulated_by="tester",
        dry_run_decision="simulated_for_controlled_cleanup_apply_execution_plan_execution_review",
    )
    staging_before = test_db.fetch_one("SELECT COUNT(*) AS cnt FROM dataset2_staging_records")["cnt"]
    learning_before = test_db.fetch_one("SELECT COUNT(*) AS cnt FROM learning_samples")["cnt"]
    execution_plan_review = (
        service.staging_cleanup_execution_controlled_apply_execution_plan_execution_dry_run_review(
            apply_execution_plan_execution_dry_run_id=execution_plan_dry_run["event_id"],
            reviewed_by="tester",
            review_decision="approved_for_controlled_cleanup_apply_execution_plan_execution_final_approval",
            note="metadata-only apply execution plan execution dry-run review",
        )
    )
    staging_after = test_db.fetch_one("SELECT COUNT(*) AS cnt FROM dataset2_staging_records")["cnt"]
    learning_after = test_db.fetch_one("SELECT COUNT(*) AS cnt FROM learning_samples")["cnt"]

    assert execution_plan_review["stage"] == "V5.6-P43"
    assert execution_plan_review["status"] == "controlled_cleanup_apply_execution_plan_execution_dry_run_review_accepted"
    assert isinstance(execution_plan_review["event_id"], int)
    assert execution_plan_review["apply_execution_plan_execution_dry_run_id"] == execution_plan_dry_run["event_id"]
    assert execution_plan_review["apply_execution_plan_execution_preflight_id"] == execution_plan_preflight["event_id"]
    assert execution_plan_review["apply_execution_plan_execution_approval_id"] == chain["execution_plan_approval"]["event_id"]
    assert execution_plan_review["apply_execution_plan_dry_run_review_id"] == chain["execution_plan_review"]["event_id"]
    assert execution_plan_review["dry_run_summary"]["lock_key"] == execution_plan_dry_run["dry_run"]["lock_key"]
    assert execution_plan_review["dry_run_summary"]["simulated_mutation_count"] >= 1
    assert execution_plan_review["dry_run_summary"]["manual_operation_count"] >= 1
    assert execution_plan_review["dry_run_summary"]["transaction_required"] is True
    assert execution_plan_review["dry_run_summary"]["rollback_required"] is True
    assert execution_plan_review["dry_run_summary"]["allowed_tables"] == ["dataset2_staging_records"]
    assert "learning_samples" in execution_plan_review["dry_run_summary"]["forbidden_tables"]
    assert execution_plan_review["dry_run_summary"]["contains_sql"] is False
    assert execution_plan_review["dry_run_summary"]["contains_executable_code"] is False
    assert execution_plan_review["dry_run_summary"]["can_execute_now"] is False
    assert execution_plan_review["dry_run_summary"]["record_bodies_included"] is False
    assert execution_plan_review["dry_run_summary"]["affected_rows_body_included"] is False
    assert execution_plan_review["decision"]["controlled_cleanup_apply_execution_plan_execution_dry_run_review_recorded"] is True
    assert execution_plan_review["decision"]["controlled_cleanup_apply_execution_plan_execution_dry_run_review_accepted"] is True
    assert (
        execution_plan_review["decision"][
            "controlled_cleanup_apply_execution_plan_execution_review_ready_for_final_approval"
        ]
        is True
    )
    assert execution_plan_review["decision"]["cleanup_execution_approved_now"] is False
    assert execution_plan_review["decision"]["cleanup_application_allowed_now"] is False
    assert execution_plan_review["decision"]["cleanup_executed_now"] is False
    assert execution_plan_review["decision"]["can_execute_cleanup_now"] is False
    assert execution_plan_review["decision"]["writes_staging_records_now"] is False
    assert execution_plan_review["decision"]["writes_learning_samples_now"] is False
    assert execution_plan_review["decision"]["mutates_staging_records_now"] is False
    assert execution_plan_review["decision"]["training_started_now"] is False
    assert execution_plan_review["decision"]["can_start_training_now"] is False
    assert staging_after == staging_before
    assert learning_after == learning_before
    assert "evidence_package" not in execution_plan_review
    assert "records" not in execution_plan_review["dry_run_summary"]
    check_status = {check["name"]: check["status"] for check in execution_plan_review["checks"]}
    assert check_status["apply_execution_plan_execution_dry_run_ready_for_review"] == "passed"
    assert check_status["source_dry_run_blocked_checks_clear"] == "passed"
    assert check_status["lock_key_present"] == "passed"
    assert check_status["aggregate_apply_execution_plan_execution_simulation_present"] == "passed"
    assert check_status["manual_backfill_separated"] == "warning"
    assert check_status["simulation_contains_no_executable_payload"] == "passed"
    assert check_status["aggregate_only_no_record_bodies"] == "passed"
    assert check_status["learning_samples_unchanged"] == "passed"
    assert check_status["review_decision_allows_future_final_approval_only"] == "passed"
    assert check_status["cleanup_and_training_remain_blocked"] == "passed"

    rejected = service.staging_cleanup_execution_controlled_apply_execution_plan_execution_dry_run_review(
        apply_execution_plan_execution_dry_run_id=execution_plan_dry_run["event_id"],
        reviewed_by="tester",
        review_decision="rejected",
    )
    assert rejected["status"] == "controlled_cleanup_apply_execution_plan_execution_dry_run_review_blocked"
    assert rejected["decision"]["controlled_cleanup_apply_execution_plan_execution_dry_run_review_recorded"] is True
    assert rejected["decision"]["controlled_cleanup_apply_execution_plan_execution_dry_run_review_accepted"] is False
    assert rejected["decision"]["can_execute_cleanup_now"] is False
    assert rejected["decision"]["writes_learning_samples_now"] is False

    reviews = service.list_staging_cleanup_execution_controlled_apply_execution_plan_execution_dry_run_reviews(limit=5)
    assert reviews[0]["id"] == rejected["event_id"]
    assert reviews[1]["id"] == execution_plan_review["event_id"]
    assert reviews[1]["review"]["reviewed_by"] == "tester"
    assert "evidence_package" not in reviews[1]


def test_dataset2_controlled_cleanup_apply_execution_plan_execution_final_approval_is_metadata_only(
    tmp_path,
    test_db,
):
    pack = _write_dataset2_pack(
        tmp_path,
        [
            _record(
                pattern_id="CONTROLLED_APPLY_EXECUTION_PLAN_EXECUTION_FINAL_APPROVAL_001",
                risk_level="medium_high",
                split_tag="train",
                observable_features=["['big_yang']", "high_volume"],
                evidence_summary="",
            ),
            _record(
                pattern_id="CONTROLLED_APPLY_EXECUTION_PLAN_EXECUTION_FINAL_APPROVAL_002",
                action_label="RISK_ALERT",
                risk_level="high",
                split_tag="test",
            ),
        ],
    )
    service = Dataset2TrainingReadinessService()

    before_missing = (
        service.list_staging_cleanup_execution_controlled_apply_execution_plan_execution_final_approvals(limit=5)
    )
    missing = service.staging_cleanup_execution_controlled_apply_execution_plan_execution_final_approval(
        apply_execution_plan_execution_dry_run_review_id=999999,
        approved_by="tester",
    )
    after_missing = (
        service.list_staging_cleanup_execution_controlled_apply_execution_plan_execution_final_approvals(limit=5)
    )
    assert missing["status"] == "controlled_cleanup_apply_execution_plan_execution_final_approval_blocked_missing_review"
    assert missing["decision"]["writes_existing_event_now"] is False
    assert missing["decision"]["controlled_cleanup_apply_execution_plan_execution_final_approval_accepted"] is False
    assert missing["decision"]["cleanup_executed_now"] is False
    assert missing["decision"]["training_started_now"] is False
    assert len(after_missing) == len(before_missing)

    chain = _controlled_apply_execution_plan_execution_approval_chain(
        service,
        pack,
        _manual_evidence_package(),
        suffix="ready-apply-execution-plan-execution-final-approval",
    )
    execution_plan_preflight = service.staging_cleanup_execution_controlled_apply_execution_plan_execution_preflight(
        apply_execution_plan_execution_approval_id=chain["execution_plan_approval"]["event_id"],
        requested_by="tester",
        preflight_decision="prepared_for_controlled_cleanup_apply_execution_plan_execution_dry_run",
    )
    execution_plan_dry_run = service.staging_cleanup_execution_controlled_apply_execution_plan_execution_dry_run(
        apply_execution_plan_execution_preflight_id=execution_plan_preflight["event_id"],
        simulated_by="tester",
        dry_run_decision="simulated_for_controlled_cleanup_apply_execution_plan_execution_review",
    )
    execution_plan_review = (
        service.staging_cleanup_execution_controlled_apply_execution_plan_execution_dry_run_review(
            apply_execution_plan_execution_dry_run_id=execution_plan_dry_run["event_id"],
            reviewed_by="tester",
            review_decision="approved_for_controlled_cleanup_apply_execution_plan_execution_final_approval",
        )
    )
    staging_before = test_db.fetch_one("SELECT COUNT(*) AS cnt FROM dataset2_staging_records")["cnt"]
    learning_before = test_db.fetch_one("SELECT COUNT(*) AS cnt FROM learning_samples")["cnt"]
    final_approval = service.staging_cleanup_execution_controlled_apply_execution_plan_execution_final_approval(
        apply_execution_plan_execution_dry_run_review_id=execution_plan_review["event_id"],
        approved_by="tester",
        approval_decision="approved_for_controlled_cleanup_apply_execution_plan_execution_final_preflight",
        note="metadata-only final approval",
    )
    staging_after = test_db.fetch_one("SELECT COUNT(*) AS cnt FROM dataset2_staging_records")["cnt"]
    learning_after = test_db.fetch_one("SELECT COUNT(*) AS cnt FROM learning_samples")["cnt"]

    assert final_approval["stage"] == "V5.6-P43"
    assert final_approval["status"] == "controlled_cleanup_apply_execution_plan_execution_final_approval_accepted"
    assert isinstance(final_approval["event_id"], int)
    assert final_approval["apply_execution_plan_execution_dry_run_review_id"] == execution_plan_review["event_id"]
    assert final_approval["apply_execution_plan_execution_dry_run_id"] == execution_plan_dry_run["event_id"]
    assert final_approval["apply_execution_plan_execution_preflight_id"] == execution_plan_preflight["event_id"]
    assert final_approval["apply_execution_plan_execution_approval_id"] == chain["execution_plan_approval"]["event_id"]
    assert final_approval["approval_scope"]["lock_key"] == execution_plan_review["dry_run_summary"]["lock_key"]
    assert final_approval["approval_scope"]["allowed_next_stage"] == (
        "controlled_cleanup_apply_execution_plan_execution_final_preflight"
    )
    assert final_approval["approval_scope"]["requires_preflight"] is True
    assert final_approval["approval_scope"]["requires_transaction"] is True
    assert final_approval["approval_scope"]["requires_rollback"] is True
    assert final_approval["approval_scope"]["simulated_mutation_count"] >= 1
    assert final_approval["approval_scope"]["manual_operation_count"] >= 1
    assert final_approval["approval_scope"]["allowed_tables"] == ["dataset2_staging_records"]
    assert "learning_samples" in final_approval["approval_scope"]["forbidden_tables"]
    assert final_approval["approval_scope"]["contains_sql"] is False
    assert final_approval["approval_scope"]["contains_executable_code"] is False
    assert final_approval["approval_scope"]["can_execute_now"] is False
    assert final_approval["approval_scope"]["record_bodies_included"] is False
    assert final_approval["approval_scope"]["affected_rows_body_included"] is False
    assert final_approval["decision"]["controlled_cleanup_apply_execution_plan_execution_final_approval_recorded"] is True
    assert final_approval["decision"]["controlled_cleanup_apply_execution_plan_execution_final_approval_accepted"] is True
    assert (
        final_approval["decision"][
            "controlled_cleanup_apply_execution_plan_execution_final_approval_ready_for_preflight"
        ]
        is True
    )
    assert final_approval["decision"]["cleanup_execution_approved_now"] is False
    assert final_approval["decision"]["cleanup_application_allowed_now"] is False
    assert final_approval["decision"]["cleanup_executed_now"] is False
    assert final_approval["decision"]["can_execute_cleanup_now"] is False
    assert final_approval["decision"]["writes_staging_records_now"] is False
    assert final_approval["decision"]["writes_learning_samples_now"] is False
    assert final_approval["decision"]["mutates_staging_records_now"] is False
    assert final_approval["decision"]["training_started_now"] is False
    assert final_approval["decision"]["can_start_training_now"] is False
    assert staging_after == staging_before
    assert learning_after == learning_before
    assert "evidence_package" not in final_approval
    check_status = {check["name"]: check["status"] for check in final_approval["checks"]}
    assert check_status["apply_execution_plan_execution_dry_run_review_accepted"] == "passed"
    assert check_status["source_review_blocked_checks_clear"] == "passed"
    assert check_status["approval_scope_has_final_preflight_gate"] == "passed"
    assert check_status["lock_key_present"] == "passed"
    assert check_status["manual_backfill_separated"] == "warning"
    assert check_status["approval_scope_contains_no_executable_payload"] == "passed"
    assert check_status["aggregate_only_no_record_bodies"] == "passed"
    assert check_status["learning_samples_unchanged"] == "passed"
    assert check_status["approval_decision_allows_final_preflight_only"] == "passed"
    assert check_status["cleanup_and_training_remain_blocked"] == "passed"

    rejected = service.staging_cleanup_execution_controlled_apply_execution_plan_execution_final_approval(
        apply_execution_plan_execution_dry_run_review_id=execution_plan_review["event_id"],
        approved_by="tester",
        approval_decision="rejected",
    )
    assert rejected["status"] == "controlled_cleanup_apply_execution_plan_execution_final_approval_blocked"
    assert rejected["decision"]["controlled_cleanup_apply_execution_plan_execution_final_approval_recorded"] is True
    assert rejected["decision"]["controlled_cleanup_apply_execution_plan_execution_final_approval_accepted"] is False
    assert rejected["decision"]["can_execute_cleanup_now"] is False
    assert rejected["decision"]["writes_learning_samples_now"] is False

    approvals = service.list_staging_cleanup_execution_controlled_apply_execution_plan_execution_final_approvals(limit=5)
    assert approvals[0]["id"] == rejected["event_id"]
    assert approvals[1]["id"] == final_approval["event_id"]
    assert approvals[1]["approval"]["approved_by"] == "tester"
    assert "evidence_package" not in approvals[1]


def test_dataset2_controlled_cleanup_apply_execution_plan_execution_final_preflight_is_metadata_only(
    tmp_path,
    test_db,
):
    pack = _write_dataset2_pack(
        tmp_path,
        [
            _record(
                pattern_id="CONTROLLED_APPLY_EXECUTION_PLAN_EXECUTION_FINAL_PREFLIGHT_001",
                risk_level="medium_high",
                split_tag="train",
                observable_features=["['big_yang']", "high_volume"],
                evidence_summary="",
            ),
            _record(
                pattern_id="CONTROLLED_APPLY_EXECUTION_PLAN_EXECUTION_FINAL_PREFLIGHT_002",
                action_label="RISK_ALERT",
                risk_level="high",
                split_tag="test",
            ),
        ],
    )
    service = Dataset2TrainingReadinessService()

    before_missing = (
        service.list_staging_cleanup_execution_controlled_apply_execution_plan_execution_final_preflights(limit=5)
    )
    missing = service.staging_cleanup_execution_controlled_apply_execution_plan_execution_final_preflight(
        apply_execution_plan_execution_final_approval_id=999999,
        requested_by="tester",
    )
    after_missing = (
        service.list_staging_cleanup_execution_controlled_apply_execution_plan_execution_final_preflights(limit=5)
    )
    assert missing["status"] == "controlled_cleanup_apply_execution_plan_execution_final_preflight_blocked_missing_final_approval"
    assert missing["decision"]["writes_existing_event_now"] is False
    assert missing["decision"]["controlled_cleanup_apply_execution_plan_execution_final_preflight_ready_for_dry_run"] is False
    assert missing["decision"]["cleanup_executed_now"] is False
    assert missing["decision"]["training_started_now"] is False
    assert len(after_missing) == len(before_missing)

    chain = _controlled_apply_execution_plan_execution_approval_chain(
        service,
        pack,
        _manual_evidence_package(),
        suffix="ready-apply-execution-plan-execution-final-preflight",
    )
    execution_plan_preflight = service.staging_cleanup_execution_controlled_apply_execution_plan_execution_preflight(
        apply_execution_plan_execution_approval_id=chain["execution_plan_approval"]["event_id"],
        requested_by="tester",
        preflight_decision="prepared_for_controlled_cleanup_apply_execution_plan_execution_dry_run",
    )
    execution_plan_dry_run = service.staging_cleanup_execution_controlled_apply_execution_plan_execution_dry_run(
        apply_execution_plan_execution_preflight_id=execution_plan_preflight["event_id"],
        simulated_by="tester",
        dry_run_decision="simulated_for_controlled_cleanup_apply_execution_plan_execution_review",
    )
    execution_plan_review = (
        service.staging_cleanup_execution_controlled_apply_execution_plan_execution_dry_run_review(
            apply_execution_plan_execution_dry_run_id=execution_plan_dry_run["event_id"],
            reviewed_by="tester",
            review_decision="approved_for_controlled_cleanup_apply_execution_plan_execution_final_approval",
        )
    )
    final_approval = service.staging_cleanup_execution_controlled_apply_execution_plan_execution_final_approval(
        apply_execution_plan_execution_dry_run_review_id=execution_plan_review["event_id"],
        approved_by="tester",
        approval_decision="approved_for_controlled_cleanup_apply_execution_plan_execution_final_preflight",
    )
    staging_before = test_db.fetch_one("SELECT COUNT(*) AS cnt FROM dataset2_staging_records")["cnt"]
    learning_before = test_db.fetch_one("SELECT COUNT(*) AS cnt FROM learning_samples")["cnt"]
    final_preflight = service.staging_cleanup_execution_controlled_apply_execution_plan_execution_final_preflight(
        apply_execution_plan_execution_final_approval_id=final_approval["event_id"],
        requested_by="tester",
        preflight_decision="prepared_for_controlled_cleanup_apply_execution_plan_execution_final_dry_run",
        note="metadata-only final preflight",
    )
    staging_after = test_db.fetch_one("SELECT COUNT(*) AS cnt FROM dataset2_staging_records")["cnt"]
    learning_after = test_db.fetch_one("SELECT COUNT(*) AS cnt FROM learning_samples")["cnt"]

    assert final_preflight["stage"] == "V5.6-P43"
    assert final_preflight["status"] == "controlled_cleanup_apply_execution_plan_execution_final_preflight_ready_for_dry_run"
    assert isinstance(final_preflight["event_id"], int)
    assert final_preflight["apply_execution_plan_execution_final_approval_id"] == final_approval["event_id"]
    assert final_preflight["apply_execution_plan_execution_dry_run_review_id"] == execution_plan_review["event_id"]
    assert final_preflight["apply_execution_plan_execution_dry_run_id"] == execution_plan_dry_run["event_id"]
    assert final_preflight["preflight"]["lock_key"] == final_approval["approval_scope"]["lock_key"]
    assert final_preflight["preflight"]["staging_count_still_matches"] is True
    assert final_preflight["preflight"]["learning_sample_count_still_matches"] is True
    assert final_preflight["preflight"]["allowed_next_stage"] == (
        "controlled_cleanup_apply_execution_plan_execution_final_dry_run"
    )
    assert final_preflight["preflight"]["transaction_required"] is True
    assert final_preflight["preflight"]["rollback_required"] is True
    assert final_preflight["preflight"]["simulated_mutation_count"] >= 1
    assert final_preflight["preflight"]["manual_operation_count"] >= 1
    assert final_preflight["preflight"]["allowed_tables"] == ["dataset2_staging_records"]
    assert "learning_samples" in final_preflight["preflight"]["forbidden_tables"]
    assert final_preflight["preflight"]["contains_sql"] is False
    assert final_preflight["preflight"]["contains_executable_code"] is False
    assert final_preflight["preflight"]["can_execute_now"] is False
    assert final_preflight["preflight"]["record_bodies_included"] is False
    assert final_preflight["preflight"]["affected_rows_body_included"] is False
    assert final_preflight["decision"]["controlled_cleanup_apply_execution_plan_execution_final_preflight_recorded"] is True
    assert (
        final_preflight["decision"][
            "controlled_cleanup_apply_execution_plan_execution_final_preflight_ready_for_dry_run"
        ]
        is True
    )
    assert final_preflight["decision"]["cleanup_execution_approved_now"] is False
    assert final_preflight["decision"]["cleanup_application_allowed_now"] is False
    assert final_preflight["decision"]["cleanup_executed_now"] is False
    assert final_preflight["decision"]["can_execute_cleanup_now"] is False
    assert final_preflight["decision"]["writes_staging_records_now"] is False
    assert final_preflight["decision"]["writes_learning_samples_now"] is False
    assert final_preflight["decision"]["mutates_staging_records_now"] is False
    assert final_preflight["decision"]["training_started_now"] is False
    assert final_preflight["decision"]["can_start_training_now"] is False
    assert staging_after == staging_before
    assert learning_after == learning_before
    assert "evidence_package" not in final_preflight
    check_status = {check["name"]: check["status"] for check in final_preflight["checks"]}
    assert check_status["apply_execution_plan_execution_final_approval_accepted"] == "passed"
    assert check_status["source_final_approval_blocked_checks_clear"] == "passed"
    assert check_status["lock_key_present"] == "passed"
    assert check_status["staging_count_still_matches_final_approval"] == "passed"
    assert check_status["learning_sample_count_still_matches_final_approval"] == "passed"
    assert check_status["manual_backfill_separated"] == "warning"
    assert check_status["preflight_contains_no_executable_payload"] == "passed"
    assert check_status["aggregate_only_no_record_bodies"] == "passed"
    assert check_status["preflight_decision_allows_final_dry_run_only"] == "passed"
    assert check_status["cleanup_and_training_remain_blocked"] == "passed"

    rejected = service.staging_cleanup_execution_controlled_apply_execution_plan_execution_final_preflight(
        apply_execution_plan_execution_final_approval_id=final_approval["event_id"],
        requested_by="tester",
        preflight_decision="rejected",
    )
    assert rejected["status"] == "controlled_cleanup_apply_execution_plan_execution_final_preflight_blocked"
    assert rejected["decision"]["controlled_cleanup_apply_execution_plan_execution_final_preflight_recorded"] is True
    assert rejected["decision"]["controlled_cleanup_apply_execution_plan_execution_final_preflight_ready_for_dry_run"] is False
    assert rejected["decision"]["can_execute_cleanup_now"] is False
    assert rejected["decision"]["writes_learning_samples_now"] is False

    preflights = service.list_staging_cleanup_execution_controlled_apply_execution_plan_execution_final_preflights(limit=5)
    assert preflights[0]["id"] == rejected["event_id"]
    assert preflights[1]["id"] == final_preflight["event_id"]
    assert preflights[1]["request"]["requested_by"] == "tester"
    assert "evidence_package" not in preflights[1]


def test_dataset2_controlled_cleanup_apply_execution_plan_execution_final_dry_run_is_metadata_only(
    tmp_path,
    test_db,
):
    pack = _write_dataset2_pack(
        tmp_path,
        [
            _record(
                pattern_id="CONTROLLED_APPLY_EXECUTION_PLAN_EXECUTION_FINAL_DRY_RUN_001",
                risk_level="medium_high",
                split_tag="train",
                observable_features=["['big_yang']", "high_volume"],
                evidence_summary="",
            ),
            _record(
                pattern_id="CONTROLLED_APPLY_EXECUTION_PLAN_EXECUTION_FINAL_DRY_RUN_002",
                action_label="RISK_ALERT",
                risk_level="high",
                split_tag="test",
            ),
        ],
    )
    service = Dataset2TrainingReadinessService()

    before_missing = (
        service.list_staging_cleanup_execution_controlled_apply_execution_plan_execution_final_dry_runs(limit=5)
    )
    missing = service.staging_cleanup_execution_controlled_apply_execution_plan_execution_final_dry_run(
        apply_execution_plan_execution_final_preflight_id=999999,
        simulated_by="tester",
    )
    after_missing = (
        service.list_staging_cleanup_execution_controlled_apply_execution_plan_execution_final_dry_runs(limit=5)
    )
    assert missing["status"] == "controlled_cleanup_apply_execution_plan_execution_final_dry_run_blocked_missing_preflight"
    assert missing["decision"]["writes_existing_event_now"] is False
    assert missing["decision"]["controlled_cleanup_apply_execution_plan_execution_final_dry_run_ready_for_review"] is False
    assert missing["decision"]["cleanup_executed_now"] is False
    assert missing["decision"]["training_started_now"] is False
    assert len(after_missing) == len(before_missing)

    chain = _controlled_apply_execution_plan_execution_approval_chain(
        service,
        pack,
        _manual_evidence_package(),
        suffix="ready-apply-execution-plan-execution-final-dry-run",
    )
    execution_plan_preflight = service.staging_cleanup_execution_controlled_apply_execution_plan_execution_preflight(
        apply_execution_plan_execution_approval_id=chain["execution_plan_approval"]["event_id"],
        requested_by="tester",
        preflight_decision="prepared_for_controlled_cleanup_apply_execution_plan_execution_dry_run",
    )
    execution_plan_dry_run = service.staging_cleanup_execution_controlled_apply_execution_plan_execution_dry_run(
        apply_execution_plan_execution_preflight_id=execution_plan_preflight["event_id"],
        simulated_by="tester",
        dry_run_decision="simulated_for_controlled_cleanup_apply_execution_plan_execution_review",
    )
    execution_plan_review = (
        service.staging_cleanup_execution_controlled_apply_execution_plan_execution_dry_run_review(
            apply_execution_plan_execution_dry_run_id=execution_plan_dry_run["event_id"],
            reviewed_by="tester",
            review_decision="approved_for_controlled_cleanup_apply_execution_plan_execution_final_approval",
        )
    )
    final_approval = service.staging_cleanup_execution_controlled_apply_execution_plan_execution_final_approval(
        apply_execution_plan_execution_dry_run_review_id=execution_plan_review["event_id"],
        approved_by="tester",
        approval_decision="approved_for_controlled_cleanup_apply_execution_plan_execution_final_preflight",
    )
    final_preflight = service.staging_cleanup_execution_controlled_apply_execution_plan_execution_final_preflight(
        apply_execution_plan_execution_final_approval_id=final_approval["event_id"],
        requested_by="tester",
        preflight_decision="prepared_for_controlled_cleanup_apply_execution_plan_execution_final_dry_run",
    )
    staging_before = test_db.fetch_one("SELECT COUNT(*) AS cnt FROM dataset2_staging_records")["cnt"]
    learning_before = test_db.fetch_one("SELECT COUNT(*) AS cnt FROM learning_samples")["cnt"]
    final_dry_run = service.staging_cleanup_execution_controlled_apply_execution_plan_execution_final_dry_run(
        apply_execution_plan_execution_final_preflight_id=final_preflight["event_id"],
        simulated_by="tester",
        dry_run_decision="simulated_for_controlled_cleanup_apply_execution_plan_execution_final_review",
        note="metadata-only final dry-run",
    )
    staging_after = test_db.fetch_one("SELECT COUNT(*) AS cnt FROM dataset2_staging_records")["cnt"]
    learning_after = test_db.fetch_one("SELECT COUNT(*) AS cnt FROM learning_samples")["cnt"]

    assert final_dry_run["stage"] == "V5.6-P43"
    assert final_dry_run["status"] == "controlled_cleanup_apply_execution_plan_execution_final_dry_run_ready_for_review"
    assert isinstance(final_dry_run["event_id"], int)
    assert final_dry_run["apply_execution_plan_execution_final_preflight_id"] == final_preflight["event_id"]
    assert final_dry_run["apply_execution_plan_execution_final_approval_id"] == final_approval["event_id"]
    assert final_dry_run["apply_execution_plan_execution_dry_run_review_id"] == execution_plan_review["event_id"]
    assert final_dry_run["apply_execution_plan_execution_dry_run_id"] == execution_plan_dry_run["event_id"]
    assert final_dry_run["dry_run"]["lock_key"] == final_preflight["preflight"]["lock_key"]
    assert final_dry_run["dry_run"]["staging_count_still_matches"] is True
    assert final_dry_run["dry_run"]["learning_sample_count_still_matches"] is True
    assert final_dry_run["dry_run"]["allowed_next_stage"] == (
        "controlled_cleanup_apply_execution_plan_execution_final_review"
    )
    assert final_dry_run["dry_run"]["transaction_required"] is True
    assert final_dry_run["dry_run"]["rollback_required"] is True
    assert final_dry_run["dry_run"]["simulated_mutation_count"] >= 1
    assert final_dry_run["dry_run"]["manual_operation_count"] >= 1
    assert final_dry_run["dry_run"]["allowed_tables"] == ["dataset2_staging_records"]
    assert "learning_samples" in final_dry_run["dry_run"]["forbidden_tables"]
    assert final_dry_run["dry_run"]["contains_sql"] is False
    assert final_dry_run["dry_run"]["contains_executable_code"] is False
    assert final_dry_run["dry_run"]["can_execute_now"] is False
    assert final_dry_run["dry_run"]["record_bodies_included"] is False
    assert final_dry_run["dry_run"]["affected_rows_body_included"] is False
    assert final_dry_run["decision"]["controlled_cleanup_apply_execution_plan_execution_final_dry_run_recorded"] is True
    assert final_dry_run["decision"]["controlled_cleanup_apply_execution_plan_execution_final_dry_run_ready_for_review"] is True
    assert final_dry_run["decision"]["cleanup_execution_approved_now"] is False
    assert final_dry_run["decision"]["cleanup_application_allowed_now"] is False
    assert final_dry_run["decision"]["cleanup_executed_now"] is False
    assert final_dry_run["decision"]["can_execute_cleanup_now"] is False
    assert final_dry_run["decision"]["writes_staging_records_now"] is False
    assert final_dry_run["decision"]["writes_learning_samples_now"] is False
    assert final_dry_run["decision"]["mutates_staging_records_now"] is False
    assert final_dry_run["decision"]["training_started_now"] is False
    assert final_dry_run["decision"]["can_start_training_now"] is False
    assert staging_after == staging_before
    assert learning_after == learning_before
    assert "evidence_package" not in final_dry_run
    check_status = {check["name"]: check["status"] for check in final_dry_run["checks"]}
    assert check_status["apply_execution_plan_execution_final_preflight_ready_for_dry_run"] == "passed"
    assert check_status["source_preflight_blocked_checks_clear"] == "passed"
    assert check_status["lock_key_present"] == "passed"
    assert check_status["staging_count_still_matches_preflight"] == "passed"
    assert check_status["learning_samples_unchanged"] == "passed"
    assert check_status["manual_backfill_separated"] == "warning"
    assert check_status["simulation_contains_no_executable_payload"] == "passed"
    assert check_status["aggregate_only_no_record_bodies"] == "passed"
    assert check_status["dry_run_decision_allows_final_review_only"] == "passed"
    assert check_status["cleanup_and_training_remain_blocked"] == "passed"

    rejected = service.staging_cleanup_execution_controlled_apply_execution_plan_execution_final_dry_run(
        apply_execution_plan_execution_final_preflight_id=final_preflight["event_id"],
        simulated_by="tester",
        dry_run_decision="rejected",
    )
    assert rejected["status"] == "controlled_cleanup_apply_execution_plan_execution_final_dry_run_blocked"
    assert rejected["decision"]["controlled_cleanup_apply_execution_plan_execution_final_dry_run_recorded"] is True
    assert rejected["decision"]["controlled_cleanup_apply_execution_plan_execution_final_dry_run_ready_for_review"] is False
    assert rejected["decision"]["can_execute_cleanup_now"] is False
    assert rejected["decision"]["writes_learning_samples_now"] is False

    dry_runs = service.list_staging_cleanup_execution_controlled_apply_execution_plan_execution_final_dry_runs(limit=5)
    assert dry_runs[0]["id"] == rejected["event_id"]
    assert dry_runs[1]["id"] == final_dry_run["event_id"]
    assert dry_runs[1]["request"]["simulated_by"] == "tester"
    assert "evidence_package" not in dry_runs[1]


def test_dataset2_controlled_cleanup_apply_execution_plan_execution_final_dry_run_review_is_metadata_only(
    tmp_path,
    test_db,
):
    pack = _write_dataset2_pack(
        tmp_path,
        [
            _record(
                pattern_id="CONTROLLED_APPLY_EXECUTION_PLAN_EXECUTION_FINAL_REVIEW_001",
                risk_level="medium_high",
                split_tag="train",
                observable_features=["['big_yang']", "high_volume"],
                evidence_summary="",
            ),
            _record(
                pattern_id="CONTROLLED_APPLY_EXECUTION_PLAN_EXECUTION_FINAL_REVIEW_002",
                action_label="RISK_ALERT",
                risk_level="high",
                split_tag="test",
            ),
        ],
    )
    service = Dataset2TrainingReadinessService()

    before_missing = service.list_staging_cleanup_execution_controlled_apply_execution_plan_execution_final_dry_run_reviews(
        limit=5
    )
    missing = service.staging_cleanup_execution_controlled_apply_execution_plan_execution_final_dry_run_review(
        apply_execution_plan_execution_final_dry_run_id=999999,
        reviewed_by="tester",
    )
    after_missing = service.list_staging_cleanup_execution_controlled_apply_execution_plan_execution_final_dry_run_reviews(
        limit=5
    )
    assert missing["status"] == (
        "controlled_cleanup_apply_execution_plan_execution_final_dry_run_review_blocked_missing_dry_run"
    )
    assert missing["decision"]["writes_existing_event_now"] is False
    assert (
        missing["decision"]["controlled_cleanup_apply_execution_plan_execution_final_dry_run_review_accepted"]
        is False
    )
    assert missing["decision"]["cleanup_executed_now"] is False
    assert missing["decision"]["training_started_now"] is False
    assert len(after_missing) == len(before_missing)

    chain = _controlled_apply_execution_plan_execution_approval_chain(
        service,
        pack,
        _manual_evidence_package(),
        suffix="ready-apply-execution-plan-execution-final-review",
    )
    execution_plan_preflight = service.staging_cleanup_execution_controlled_apply_execution_plan_execution_preflight(
        apply_execution_plan_execution_approval_id=chain["execution_plan_approval"]["event_id"],
        requested_by="tester",
        preflight_decision="prepared_for_controlled_cleanup_apply_execution_plan_execution_dry_run",
    )
    execution_plan_dry_run = service.staging_cleanup_execution_controlled_apply_execution_plan_execution_dry_run(
        apply_execution_plan_execution_preflight_id=execution_plan_preflight["event_id"],
        simulated_by="tester",
        dry_run_decision="simulated_for_controlled_cleanup_apply_execution_plan_execution_review",
    )
    execution_plan_review = service.staging_cleanup_execution_controlled_apply_execution_plan_execution_dry_run_review(
        apply_execution_plan_execution_dry_run_id=execution_plan_dry_run["event_id"],
        reviewed_by="tester",
        review_decision="approved_for_controlled_cleanup_apply_execution_plan_execution_final_approval",
    )
    final_approval = service.staging_cleanup_execution_controlled_apply_execution_plan_execution_final_approval(
        apply_execution_plan_execution_dry_run_review_id=execution_plan_review["event_id"],
        approved_by="tester",
        approval_decision="approved_for_controlled_cleanup_apply_execution_plan_execution_final_preflight",
    )
    final_preflight = service.staging_cleanup_execution_controlled_apply_execution_plan_execution_final_preflight(
        apply_execution_plan_execution_final_approval_id=final_approval["event_id"],
        requested_by="tester",
        preflight_decision="prepared_for_controlled_cleanup_apply_execution_plan_execution_final_dry_run",
    )
    final_dry_run = service.staging_cleanup_execution_controlled_apply_execution_plan_execution_final_dry_run(
        apply_execution_plan_execution_final_preflight_id=final_preflight["event_id"],
        simulated_by="tester",
        dry_run_decision="simulated_for_controlled_cleanup_apply_execution_plan_execution_final_review",
    )
    staging_before = test_db.fetch_one("SELECT COUNT(*) AS cnt FROM dataset2_staging_records")["cnt"]
    learning_before = test_db.fetch_one("SELECT COUNT(*) AS cnt FROM learning_samples")["cnt"]
    final_review = service.staging_cleanup_execution_controlled_apply_execution_plan_execution_final_dry_run_review(
        apply_execution_plan_execution_final_dry_run_id=final_dry_run["event_id"],
        reviewed_by="tester",
        review_decision="approved_for_controlled_cleanup_apply_execution_plan_execution_final_execution_approval",
        note="metadata-only final dry-run review",
    )
    staging_after = test_db.fetch_one("SELECT COUNT(*) AS cnt FROM dataset2_staging_records")["cnt"]
    learning_after = test_db.fetch_one("SELECT COUNT(*) AS cnt FROM learning_samples")["cnt"]

    assert final_review["stage"] == "V5.6-P43"
    assert final_review["status"] == "controlled_cleanup_apply_execution_plan_execution_final_dry_run_review_accepted"
    assert isinstance(final_review["event_id"], int)
    assert final_review["apply_execution_plan_execution_final_dry_run_id"] == final_dry_run["event_id"]
    assert final_review["apply_execution_plan_execution_final_preflight_id"] == final_preflight["event_id"]
    assert final_review["apply_execution_plan_execution_final_approval_id"] == final_approval["event_id"]
    assert final_review["apply_execution_plan_execution_dry_run_review_id"] == execution_plan_review["event_id"]
    assert final_review["apply_execution_plan_execution_dry_run_id"] == execution_plan_dry_run["event_id"]
    assert final_review["dry_run_summary"]["lock_key"] == final_dry_run["dry_run"]["lock_key"]
    assert final_review["dry_run_summary"]["simulated_mutation_count"] >= 1
    assert final_review["dry_run_summary"]["manual_operation_count"] >= 1
    assert final_review["dry_run_summary"]["transaction_required"] is True
    assert final_review["dry_run_summary"]["rollback_required"] is True
    assert final_review["dry_run_summary"]["allowed_tables"] == ["dataset2_staging_records"]
    assert "learning_samples" in final_review["dry_run_summary"]["forbidden_tables"]
    assert final_review["dry_run_summary"]["contains_sql"] is False
    assert final_review["dry_run_summary"]["contains_executable_code"] is False
    assert final_review["dry_run_summary"]["can_execute_now"] is False
    assert final_review["dry_run_summary"]["record_bodies_included"] is False
    assert final_review["decision"]["controlled_cleanup_apply_execution_plan_execution_final_dry_run_review_recorded"] is True
    assert final_review["decision"]["controlled_cleanup_apply_execution_plan_execution_final_dry_run_review_accepted"] is True
    assert (
        final_review["decision"][
            "controlled_cleanup_apply_execution_plan_execution_final_review_ready_for_execution_approval"
        ]
        is True
    )
    assert final_review["decision"]["cleanup_execution_approved_now"] is False
    assert final_review["decision"]["cleanup_application_allowed_now"] is False
    assert final_review["decision"]["cleanup_executed_now"] is False
    assert final_review["decision"]["can_execute_cleanup_now"] is False
    assert final_review["decision"]["writes_staging_records_now"] is False
    assert final_review["decision"]["writes_learning_samples_now"] is False
    assert final_review["decision"]["mutates_staging_records_now"] is False
    assert final_review["decision"]["training_started_now"] is False
    assert final_review["decision"]["can_start_training_now"] is False
    assert staging_after == staging_before
    assert learning_after == learning_before
    assert "evidence_package" not in final_review
    check_status = {check["name"]: check["status"] for check in final_review["checks"]}
    assert check_status["apply_execution_plan_execution_final_dry_run_ready_for_review"] == "passed"
    assert check_status["source_dry_run_blocked_checks_clear"] == "passed"
    assert check_status["aggregate_final_simulation_present"] == "passed"
    assert check_status["manual_backfill_separated"] == "warning"
    assert check_status["source_dry_run_contains_no_executable_payload"] == "passed"
    assert check_status["aggregate_only_no_record_bodies"] == "passed"
    assert check_status["review_decision_allows_execution_approval_only"] == "passed"
    assert check_status["source_dry_run_kept_execution_blocked"] == "passed"
    assert check_status["cleanup_and_training_remain_blocked"] == "passed"

    rejected = service.staging_cleanup_execution_controlled_apply_execution_plan_execution_final_dry_run_review(
        apply_execution_plan_execution_final_dry_run_id=final_dry_run["event_id"],
        reviewed_by="tester",
        review_decision="rejected",
    )
    assert rejected["status"] == "controlled_cleanup_apply_execution_plan_execution_final_dry_run_review_blocked"
    assert (
        rejected["decision"]["controlled_cleanup_apply_execution_plan_execution_final_dry_run_review_recorded"]
        is True
    )
    assert (
        rejected["decision"]["controlled_cleanup_apply_execution_plan_execution_final_dry_run_review_accepted"]
        is False
    )
    assert rejected["decision"]["can_execute_cleanup_now"] is False
    assert rejected["decision"]["writes_learning_samples_now"] is False

    reviews = service.list_staging_cleanup_execution_controlled_apply_execution_plan_execution_final_dry_run_reviews(
        limit=5
    )
    assert reviews[0]["id"] == rejected["event_id"]
    assert reviews[1]["id"] == final_review["event_id"]
    assert reviews[1]["review"]["reviewed_by"] == "tester"
    assert "evidence_package" not in reviews[1]


def test_dataset2_controlled_cleanup_apply_execution_plan_execution_final_execution_approval_is_metadata_only(
    tmp_path,
    test_db,
):
    pack = _write_dataset2_pack(
        tmp_path,
        [
            _record(
                pattern_id="CONTROLLED_APPLY_EXECUTION_PLAN_EXECUTION_FINAL_EXECUTION_APPROVAL_001",
                risk_level="medium_high",
                split_tag="train",
                observable_features=["['big_yang']", "high_volume"],
                evidence_summary="",
            ),
            _record(
                pattern_id="CONTROLLED_APPLY_EXECUTION_PLAN_EXECUTION_FINAL_EXECUTION_APPROVAL_002",
                action_label="RISK_ALERT",
                risk_level="high",
                split_tag="test",
            ),
        ],
    )
    service = Dataset2TrainingReadinessService()

    before_missing = (
        service.list_staging_cleanup_execution_controlled_apply_execution_plan_execution_final_execution_approvals(
            limit=5
        )
    )
    missing = service.staging_cleanup_execution_controlled_apply_execution_plan_execution_final_execution_approval(
        apply_execution_plan_execution_final_dry_run_review_id=999999,
        approved_by="tester",
    )
    after_missing = (
        service.list_staging_cleanup_execution_controlled_apply_execution_plan_execution_final_execution_approvals(
            limit=5
        )
    )
    assert missing["status"] == (
        "controlled_cleanup_apply_execution_plan_execution_final_execution_approval_blocked_missing_review"
    )
    assert missing["decision"]["writes_existing_event_now"] is False
    assert (
        missing["decision"]["controlled_cleanup_apply_execution_plan_execution_final_execution_approval_accepted"]
        is False
    )
    assert missing["decision"]["cleanup_executed_now"] is False
    assert missing["decision"]["training_started_now"] is False
    assert len(after_missing) == len(before_missing)

    chain = _controlled_apply_execution_plan_execution_approval_chain(
        service,
        pack,
        _manual_evidence_package(),
        suffix="ready-apply-execution-plan-execution-final-execution-approval",
    )
    execution_plan_preflight = service.staging_cleanup_execution_controlled_apply_execution_plan_execution_preflight(
        apply_execution_plan_execution_approval_id=chain["execution_plan_approval"]["event_id"],
        requested_by="tester",
        preflight_decision="prepared_for_controlled_cleanup_apply_execution_plan_execution_dry_run",
    )
    execution_plan_dry_run = service.staging_cleanup_execution_controlled_apply_execution_plan_execution_dry_run(
        apply_execution_plan_execution_preflight_id=execution_plan_preflight["event_id"],
        simulated_by="tester",
        dry_run_decision="simulated_for_controlled_cleanup_apply_execution_plan_execution_review",
    )
    execution_plan_review = service.staging_cleanup_execution_controlled_apply_execution_plan_execution_dry_run_review(
        apply_execution_plan_execution_dry_run_id=execution_plan_dry_run["event_id"],
        reviewed_by="tester",
        review_decision="approved_for_controlled_cleanup_apply_execution_plan_execution_final_approval",
    )
    final_approval = service.staging_cleanup_execution_controlled_apply_execution_plan_execution_final_approval(
        apply_execution_plan_execution_dry_run_review_id=execution_plan_review["event_id"],
        approved_by="tester",
        approval_decision="approved_for_controlled_cleanup_apply_execution_plan_execution_final_preflight",
    )
    final_preflight = service.staging_cleanup_execution_controlled_apply_execution_plan_execution_final_preflight(
        apply_execution_plan_execution_final_approval_id=final_approval["event_id"],
        requested_by="tester",
        preflight_decision="prepared_for_controlled_cleanup_apply_execution_plan_execution_final_dry_run",
    )
    final_dry_run = service.staging_cleanup_execution_controlled_apply_execution_plan_execution_final_dry_run(
        apply_execution_plan_execution_final_preflight_id=final_preflight["event_id"],
        simulated_by="tester",
        dry_run_decision="simulated_for_controlled_cleanup_apply_execution_plan_execution_final_review",
    )
    final_review = service.staging_cleanup_execution_controlled_apply_execution_plan_execution_final_dry_run_review(
        apply_execution_plan_execution_final_dry_run_id=final_dry_run["event_id"],
        reviewed_by="tester",
        review_decision="approved_for_controlled_cleanup_apply_execution_plan_execution_final_execution_approval",
    )
    staging_before = test_db.fetch_one("SELECT COUNT(*) AS cnt FROM dataset2_staging_records")["cnt"]
    learning_before = test_db.fetch_one("SELECT COUNT(*) AS cnt FROM learning_samples")["cnt"]
    execution_approval = (
        service.staging_cleanup_execution_controlled_apply_execution_plan_execution_final_execution_approval(
            apply_execution_plan_execution_final_dry_run_review_id=final_review["event_id"],
            approved_by="tester",
            approval_decision="approved_for_controlled_cleanup_apply_execution_plan_execution_final_execution_preflight",
            note="metadata-only final execution approval",
        )
    )
    staging_after = test_db.fetch_one("SELECT COUNT(*) AS cnt FROM dataset2_staging_records")["cnt"]
    learning_after = test_db.fetch_one("SELECT COUNT(*) AS cnt FROM learning_samples")["cnt"]

    assert execution_approval["stage"] == "V5.6-P43"
    assert execution_approval["status"] == (
        "controlled_cleanup_apply_execution_plan_execution_final_execution_approval_accepted"
    )
    assert isinstance(execution_approval["event_id"], int)
    assert execution_approval["apply_execution_plan_execution_final_dry_run_review_id"] == final_review["event_id"]
    assert execution_approval["apply_execution_plan_execution_final_dry_run_id"] == final_dry_run["event_id"]
    assert execution_approval["apply_execution_plan_execution_final_preflight_id"] == final_preflight["event_id"]
    assert execution_approval["apply_execution_plan_execution_final_approval_id"] == final_approval["event_id"]
    assert execution_approval["approval_scope"]["lock_key"] == final_review["dry_run_summary"]["lock_key"]
    assert execution_approval["approval_scope"]["approval_scope"] == (
        "controlled_apply_execution_plan_execution_final_execution_preflight_only"
    )
    assert execution_approval["approval_scope"]["allowed_next_stage"] == (
        "controlled_cleanup_apply_execution_plan_execution_final_execution_preflight"
    )
    assert execution_approval["approval_scope"]["requires_preflight"] is True
    assert execution_approval["approval_scope"]["requires_transaction"] is True
    assert execution_approval["approval_scope"]["requires_rollback"] is True
    assert execution_approval["approval_scope"]["simulated_mutation_count"] >= 1
    assert execution_approval["approval_scope"]["manual_operation_count"] >= 1
    assert execution_approval["approval_scope"]["allowed_tables"] == ["dataset2_staging_records"]
    assert "learning_samples" in execution_approval["approval_scope"]["forbidden_tables"]
    assert execution_approval["approval_scope"]["contains_sql"] is False
    assert execution_approval["approval_scope"]["contains_executable_code"] is False
    assert execution_approval["approval_scope"]["can_execute_now"] is False
    assert execution_approval["approval_scope"]["record_bodies_included"] is False
    assert (
        execution_approval["decision"][
            "controlled_cleanup_apply_execution_plan_execution_final_execution_approval_recorded"
        ]
        is True
    )
    assert (
        execution_approval["decision"][
            "controlled_cleanup_apply_execution_plan_execution_final_execution_approval_accepted"
        ]
        is True
    )
    assert (
        execution_approval["decision"][
            "controlled_cleanup_apply_execution_plan_execution_final_execution_approval_ready_for_preflight"
        ]
        is True
    )
    assert execution_approval["decision"]["cleanup_execution_approved_now"] is False
    assert execution_approval["decision"]["cleanup_application_allowed_now"] is False
    assert execution_approval["decision"]["cleanup_executed_now"] is False
    assert execution_approval["decision"]["can_execute_cleanup_now"] is False
    assert execution_approval["decision"]["writes_staging_records_now"] is False
    assert execution_approval["decision"]["writes_learning_samples_now"] is False
    assert execution_approval["decision"]["mutates_staging_records_now"] is False
    assert execution_approval["decision"]["training_started_now"] is False
    assert execution_approval["decision"]["can_start_training_now"] is False
    assert staging_after == staging_before
    assert learning_after == learning_before
    assert "evidence_package" not in execution_approval
    check_status = {check["name"]: check["status"] for check in execution_approval["checks"]}
    assert check_status["apply_execution_plan_execution_final_dry_run_review_accepted"] == "passed"
    assert check_status["source_review_blocked_checks_clear"] == "passed"
    assert check_status["approval_scope_has_final_execution_preflight_gate"] == "passed"
    assert check_status["lock_key_present"] == "passed"
    assert check_status["aggregate_final_simulation_present"] == "passed"
    assert check_status["manual_backfill_separated"] == "warning"
    assert check_status["approval_scope_contains_no_executable_payload"] == "passed"
    assert check_status["aggregate_only_no_record_bodies"] == "passed"
    assert check_status["approval_decision_allows_final_execution_preflight_only"] == "passed"
    assert check_status["source_review_kept_execution_blocked"] == "passed"
    assert check_status["cleanup_and_training_remain_blocked"] == "passed"

    rejected = service.staging_cleanup_execution_controlled_apply_execution_plan_execution_final_execution_approval(
        apply_execution_plan_execution_final_dry_run_review_id=final_review["event_id"],
        approved_by="tester",
        approval_decision="rejected",
    )
    assert rejected["status"] == "controlled_cleanup_apply_execution_plan_execution_final_execution_approval_blocked"
    assert (
        rejected["decision"]["controlled_cleanup_apply_execution_plan_execution_final_execution_approval_recorded"]
        is True
    )
    assert (
        rejected["decision"]["controlled_cleanup_apply_execution_plan_execution_final_execution_approval_accepted"]
        is False
    )
    assert rejected["decision"]["can_execute_cleanup_now"] is False
    assert rejected["decision"]["writes_learning_samples_now"] is False

    approvals = service.list_staging_cleanup_execution_controlled_apply_execution_plan_execution_final_execution_approvals(
        limit=5
    )
    assert approvals[0]["id"] == rejected["event_id"]
    assert approvals[1]["id"] == execution_approval["event_id"]
    assert approvals[1]["approval"]["approved_by"] == "tester"
    assert "evidence_package" not in approvals[1]


def test_dataset2_controlled_cleanup_apply_execution_plan_execution_final_execution_preflight_is_metadata_only(
    tmp_path,
    test_db,
):
    pack = _write_dataset2_pack(
        tmp_path,
        [
            _record(
                pattern_id="CONTROLLED_APPLY_EXECUTION_PLAN_EXECUTION_FINAL_EXECUTION_PREFLIGHT_001",
                risk_level="medium_high",
                split_tag="train",
                observable_features=["['big_yang']", "high_volume"],
                evidence_summary="",
            ),
            _record(
                pattern_id="CONTROLLED_APPLY_EXECUTION_PLAN_EXECUTION_FINAL_EXECUTION_PREFLIGHT_002",
                action_label="RISK_ALERT",
                risk_level="high",
                split_tag="test",
            ),
        ],
    )
    service = Dataset2TrainingReadinessService()

    before_missing = (
        service.list_staging_cleanup_execution_controlled_apply_execution_plan_execution_final_execution_preflights(
            limit=5
        )
    )
    missing = service.staging_cleanup_execution_controlled_apply_execution_plan_execution_final_execution_preflight(
        apply_execution_plan_execution_final_execution_approval_id=999999,
        requested_by="tester",
    )
    after_missing = (
        service.list_staging_cleanup_execution_controlled_apply_execution_plan_execution_final_execution_preflights(
            limit=5
        )
    )
    assert missing["status"] == (
        "controlled_cleanup_apply_execution_plan_execution_final_execution_preflight_blocked_missing_approval"
    )
    assert missing["decision"]["writes_existing_event_now"] is False
    assert (
        missing["decision"][
            "controlled_cleanup_apply_execution_plan_execution_final_execution_preflight_ready_for_dry_run"
        ]
        is False
    )
    assert missing["decision"]["cleanup_executed_now"] is False
    assert missing["decision"]["training_started_now"] is False
    assert len(after_missing) == len(before_missing)

    chain = _controlled_apply_execution_plan_execution_approval_chain(
        service,
        pack,
        _manual_evidence_package(),
        suffix="ready-apply-execution-plan-execution-final-execution-preflight",
    )
    execution_plan_preflight = service.staging_cleanup_execution_controlled_apply_execution_plan_execution_preflight(
        apply_execution_plan_execution_approval_id=chain["execution_plan_approval"]["event_id"],
        requested_by="tester",
        preflight_decision="prepared_for_controlled_cleanup_apply_execution_plan_execution_dry_run",
    )
    execution_plan_dry_run = service.staging_cleanup_execution_controlled_apply_execution_plan_execution_dry_run(
        apply_execution_plan_execution_preflight_id=execution_plan_preflight["event_id"],
        simulated_by="tester",
        dry_run_decision="simulated_for_controlled_cleanup_apply_execution_plan_execution_review",
    )
    execution_plan_review = service.staging_cleanup_execution_controlled_apply_execution_plan_execution_dry_run_review(
        apply_execution_plan_execution_dry_run_id=execution_plan_dry_run["event_id"],
        reviewed_by="tester",
        review_decision="approved_for_controlled_cleanup_apply_execution_plan_execution_final_approval",
    )
    final_approval = service.staging_cleanup_execution_controlled_apply_execution_plan_execution_final_approval(
        apply_execution_plan_execution_dry_run_review_id=execution_plan_review["event_id"],
        approved_by="tester",
        approval_decision="approved_for_controlled_cleanup_apply_execution_plan_execution_final_preflight",
    )
    final_preflight = service.staging_cleanup_execution_controlled_apply_execution_plan_execution_final_preflight(
        apply_execution_plan_execution_final_approval_id=final_approval["event_id"],
        requested_by="tester",
        preflight_decision="prepared_for_controlled_cleanup_apply_execution_plan_execution_final_dry_run",
    )
    final_dry_run = service.staging_cleanup_execution_controlled_apply_execution_plan_execution_final_dry_run(
        apply_execution_plan_execution_final_preflight_id=final_preflight["event_id"],
        simulated_by="tester",
        dry_run_decision="simulated_for_controlled_cleanup_apply_execution_plan_execution_final_review",
    )
    final_review = service.staging_cleanup_execution_controlled_apply_execution_plan_execution_final_dry_run_review(
        apply_execution_plan_execution_final_dry_run_id=final_dry_run["event_id"],
        reviewed_by="tester",
        review_decision="approved_for_controlled_cleanup_apply_execution_plan_execution_final_execution_approval",
    )
    final_execution_approval = (
        service.staging_cleanup_execution_controlled_apply_execution_plan_execution_final_execution_approval(
            apply_execution_plan_execution_final_dry_run_review_id=final_review["event_id"],
            approved_by="tester",
            approval_decision="approved_for_controlled_cleanup_apply_execution_plan_execution_final_execution_preflight",
        )
    )
    staging_before = test_db.fetch_one("SELECT COUNT(*) AS cnt FROM dataset2_staging_records")["cnt"]
    learning_before = test_db.fetch_one("SELECT COUNT(*) AS cnt FROM learning_samples")["cnt"]
    preflight = (
        service.staging_cleanup_execution_controlled_apply_execution_plan_execution_final_execution_preflight(
            apply_execution_plan_execution_final_execution_approval_id=final_execution_approval["event_id"],
            requested_by="tester",
            preflight_decision="prepared_for_controlled_cleanup_apply_execution_plan_execution_final_execution_dry_run",
            note="metadata-only final execution preflight",
        )
    )
    staging_after = test_db.fetch_one("SELECT COUNT(*) AS cnt FROM dataset2_staging_records")["cnt"]
    learning_after = test_db.fetch_one("SELECT COUNT(*) AS cnt FROM learning_samples")["cnt"]

    assert preflight["stage"] == "V5.6-P43"
    assert preflight["status"] == (
        "controlled_cleanup_apply_execution_plan_execution_final_execution_preflight_ready_for_dry_run"
    )
    assert isinstance(preflight["event_id"], int)
    assert (
        preflight["apply_execution_plan_execution_final_execution_approval_id"]
        == final_execution_approval["event_id"]
    )
    assert preflight["apply_execution_plan_execution_final_dry_run_review_id"] == final_review["event_id"]
    assert preflight["apply_execution_plan_execution_final_dry_run_id"] == final_dry_run["event_id"]
    assert preflight["apply_execution_plan_execution_final_preflight_id"] == final_preflight["event_id"]
    assert preflight["apply_execution_plan_execution_final_approval_id"] == final_approval["event_id"]
    assert preflight["preflight"]["lock_key"] == final_execution_approval["approval_scope"]["lock_key"]
    assert preflight["preflight"]["allowed_next_stage"] == (
        "controlled_cleanup_apply_execution_plan_execution_final_execution_dry_run"
    )
    assert preflight["preflight"]["staging_count_still_matches"] is True
    assert preflight["preflight"]["learning_sample_count_still_matches"] is True
    assert preflight["preflight"]["transaction_required"] is True
    assert preflight["preflight"]["rollback_required"] is True
    assert preflight["preflight"]["simulated_mutation_count"] >= 1
    assert preflight["preflight"]["manual_operation_count"] >= 1
    assert preflight["preflight"]["allowed_tables"] == ["dataset2_staging_records"]
    assert "learning_samples" in preflight["preflight"]["forbidden_tables"]
    assert preflight["preflight"]["contains_sql"] is False
    assert preflight["preflight"]["contains_executable_code"] is False
    assert preflight["preflight"]["can_execute_now"] is False
    assert preflight["preflight"]["record_bodies_included"] is False
    assert preflight["preflight"]["affected_rows_body_included"] is False
    assert (
        preflight["decision"][
            "controlled_cleanup_apply_execution_plan_execution_final_execution_preflight_recorded"
        ]
        is True
    )
    assert (
        preflight["decision"][
            "controlled_cleanup_apply_execution_plan_execution_final_execution_preflight_ready_for_dry_run"
        ]
        is True
    )
    assert preflight["decision"]["cleanup_execution_approved_now"] is False
    assert preflight["decision"]["cleanup_application_allowed_now"] is False
    assert preflight["decision"]["cleanup_executed_now"] is False
    assert preflight["decision"]["can_execute_cleanup_now"] is False
    assert preflight["decision"]["writes_staging_records_now"] is False
    assert preflight["decision"]["writes_learning_samples_now"] is False
    assert preflight["decision"]["mutates_staging_records_now"] is False
    assert preflight["decision"]["training_started_now"] is False
    assert preflight["decision"]["training_freeze_allowed"] is False
    assert preflight["decision"]["can_start_training_now"] is False
    assert staging_after == staging_before
    assert learning_after == learning_before
    assert "evidence_package" not in preflight
    check_status = {check["name"]: check["status"] for check in preflight["checks"]}
    assert check_status["apply_execution_plan_execution_final_execution_approval_available"] == "passed"
    assert check_status["apply_execution_plan_execution_final_execution_approval_accepted"] == "passed"
    assert check_status["source_approval_blocked_checks_clear"] == "passed"
    assert check_status["lock_key_present"] == "passed"
    assert check_status["staging_count_still_matches_approval"] == "passed"
    assert check_status["learning_samples_unchanged"] == "passed"
    assert check_status["aggregate_final_execution_scope_present"] == "passed"
    assert check_status["manual_backfill_separated"] == "warning"
    assert check_status["transaction_and_rollback_required"] == "passed"
    assert check_status["table_scope_limited"] == "passed"
    assert check_status["source_approval_contains_no_executable_payload"] == "passed"
    assert check_status["preflight_contains_no_executable_payload"] == "passed"
    assert check_status["aggregate_only_no_record_bodies"] == "passed"
    assert check_status["preflight_metadata_present"] == "passed"
    assert check_status["preflight_decision_allows_final_execution_dry_run_only"] == "passed"
    assert check_status["source_approval_kept_execution_blocked"] == "passed"
    assert check_status["cleanup_and_training_remain_blocked"] == "passed"

    rejected = service.staging_cleanup_execution_controlled_apply_execution_plan_execution_final_execution_preflight(
        apply_execution_plan_execution_final_execution_approval_id=final_execution_approval["event_id"],
        requested_by="tester",
        preflight_decision="rejected",
    )
    assert rejected["status"] == "controlled_cleanup_apply_execution_plan_execution_final_execution_preflight_blocked"
    assert (
        rejected["decision"][
            "controlled_cleanup_apply_execution_plan_execution_final_execution_preflight_recorded"
        ]
        is True
    )
    assert (
        rejected["decision"][
            "controlled_cleanup_apply_execution_plan_execution_final_execution_preflight_ready_for_dry_run"
        ]
        is False
    )
    assert rejected["decision"]["can_execute_cleanup_now"] is False
    assert rejected["decision"]["writes_learning_samples_now"] is False

    preflights = service.list_staging_cleanup_execution_controlled_apply_execution_plan_execution_final_execution_preflights(
        limit=5
    )
    assert preflights[0]["id"] == rejected["event_id"]
    assert preflights[1]["id"] == preflight["event_id"]
    assert preflights[1]["request"]["requested_by"] == "tester"
    assert "evidence_package" not in preflights[1]


def test_dataset2_controlled_cleanup_apply_execution_plan_execution_final_execution_dry_run_is_metadata_only(
    tmp_path,
    test_db,
):
    pack = _write_dataset2_pack(
        tmp_path,
        [
            _record(
                pattern_id="CONTROLLED_APPLY_EXECUTION_PLAN_EXECUTION_FINAL_EXECUTION_DRY_RUN_001",
                risk_level="medium_high",
                split_tag="train",
                observable_features=["['big_yang']", "high_volume"],
                evidence_summary="",
            ),
            _record(
                pattern_id="CONTROLLED_APPLY_EXECUTION_PLAN_EXECUTION_FINAL_EXECUTION_DRY_RUN_002",
                action_label="RISK_ALERT",
                risk_level="high",
                split_tag="test",
            ),
        ],
    )
    service = Dataset2TrainingReadinessService()

    before_missing = (
        service.list_staging_cleanup_execution_controlled_apply_execution_plan_execution_final_execution_dry_runs(
            limit=5
        )
    )
    missing = service.staging_cleanup_execution_controlled_apply_execution_plan_execution_final_execution_dry_run(
        apply_execution_plan_execution_final_execution_preflight_id=999999,
        simulated_by="tester",
    )
    after_missing = (
        service.list_staging_cleanup_execution_controlled_apply_execution_plan_execution_final_execution_dry_runs(
            limit=5
        )
    )
    assert missing["status"] == (
        "controlled_cleanup_apply_execution_plan_execution_final_execution_dry_run_blocked_missing_preflight"
    )
    assert missing["decision"]["writes_existing_event_now"] is False
    assert (
        missing["decision"][
            "controlled_cleanup_apply_execution_plan_execution_final_execution_dry_run_ready_for_review"
        ]
        is False
    )
    assert missing["decision"]["cleanup_executed_now"] is False
    assert missing["decision"]["training_started_now"] is False
    assert len(after_missing) == len(before_missing)

    chain = _controlled_apply_execution_plan_execution_approval_chain(
        service,
        pack,
        _manual_evidence_package(),
        suffix="ready-apply-execution-plan-execution-final-execution-dry-run",
    )
    execution_plan_preflight = service.staging_cleanup_execution_controlled_apply_execution_plan_execution_preflight(
        apply_execution_plan_execution_approval_id=chain["execution_plan_approval"]["event_id"],
        requested_by="tester",
        preflight_decision="prepared_for_controlled_cleanup_apply_execution_plan_execution_dry_run",
    )
    execution_plan_dry_run = service.staging_cleanup_execution_controlled_apply_execution_plan_execution_dry_run(
        apply_execution_plan_execution_preflight_id=execution_plan_preflight["event_id"],
        simulated_by="tester",
        dry_run_decision="simulated_for_controlled_cleanup_apply_execution_plan_execution_review",
    )
    execution_plan_review = service.staging_cleanup_execution_controlled_apply_execution_plan_execution_dry_run_review(
        apply_execution_plan_execution_dry_run_id=execution_plan_dry_run["event_id"],
        reviewed_by="tester",
        review_decision="approved_for_controlled_cleanup_apply_execution_plan_execution_final_approval",
    )
    final_approval = service.staging_cleanup_execution_controlled_apply_execution_plan_execution_final_approval(
        apply_execution_plan_execution_dry_run_review_id=execution_plan_review["event_id"],
        approved_by="tester",
        approval_decision="approved_for_controlled_cleanup_apply_execution_plan_execution_final_preflight",
    )
    final_preflight = service.staging_cleanup_execution_controlled_apply_execution_plan_execution_final_preflight(
        apply_execution_plan_execution_final_approval_id=final_approval["event_id"],
        requested_by="tester",
        preflight_decision="prepared_for_controlled_cleanup_apply_execution_plan_execution_final_dry_run",
    )
    final_dry_run = service.staging_cleanup_execution_controlled_apply_execution_plan_execution_final_dry_run(
        apply_execution_plan_execution_final_preflight_id=final_preflight["event_id"],
        simulated_by="tester",
        dry_run_decision="simulated_for_controlled_cleanup_apply_execution_plan_execution_final_review",
    )
    final_review = service.staging_cleanup_execution_controlled_apply_execution_plan_execution_final_dry_run_review(
        apply_execution_plan_execution_final_dry_run_id=final_dry_run["event_id"],
        reviewed_by="tester",
        review_decision="approved_for_controlled_cleanup_apply_execution_plan_execution_final_execution_approval",
    )
    final_execution_approval = (
        service.staging_cleanup_execution_controlled_apply_execution_plan_execution_final_execution_approval(
            apply_execution_plan_execution_final_dry_run_review_id=final_review["event_id"],
            approved_by="tester",
            approval_decision="approved_for_controlled_cleanup_apply_execution_plan_execution_final_execution_preflight",
        )
    )
    final_execution_preflight = (
        service.staging_cleanup_execution_controlled_apply_execution_plan_execution_final_execution_preflight(
            apply_execution_plan_execution_final_execution_approval_id=final_execution_approval["event_id"],
            requested_by="tester",
            preflight_decision="prepared_for_controlled_cleanup_apply_execution_plan_execution_final_execution_dry_run",
        )
    )
    staging_before = test_db.fetch_one("SELECT COUNT(*) AS cnt FROM dataset2_staging_records")["cnt"]
    learning_before = test_db.fetch_one("SELECT COUNT(*) AS cnt FROM learning_samples")["cnt"]
    dry_run = service.staging_cleanup_execution_controlled_apply_execution_plan_execution_final_execution_dry_run(
        apply_execution_plan_execution_final_execution_preflight_id=final_execution_preflight["event_id"],
        simulated_by="tester",
        dry_run_decision="simulated_for_controlled_cleanup_apply_execution_plan_execution_final_execution_review",
        note="metadata-only final execution dry-run",
    )
    staging_after = test_db.fetch_one("SELECT COUNT(*) AS cnt FROM dataset2_staging_records")["cnt"]
    learning_after = test_db.fetch_one("SELECT COUNT(*) AS cnt FROM learning_samples")["cnt"]

    assert dry_run["stage"] == "V5.6-P43"
    assert dry_run["status"] == (
        "controlled_cleanup_apply_execution_plan_execution_final_execution_dry_run_ready_for_review"
    )
    assert isinstance(dry_run["event_id"], int)
    assert (
        dry_run["apply_execution_plan_execution_final_execution_preflight_id"]
        == final_execution_preflight["event_id"]
    )
    assert (
        dry_run["apply_execution_plan_execution_final_execution_approval_id"]
        == final_execution_approval["event_id"]
    )
    assert dry_run["apply_execution_plan_execution_final_dry_run_review_id"] == final_review["event_id"]
    assert dry_run["apply_execution_plan_execution_final_dry_run_id"] == final_dry_run["event_id"]
    assert dry_run["apply_execution_plan_execution_final_preflight_id"] == final_preflight["event_id"]
    assert dry_run["dry_run"]["lock_key"] == final_execution_preflight["preflight"]["lock_key"]
    assert dry_run["dry_run"]["allowed_next_stage"] == (
        "controlled_cleanup_apply_execution_plan_execution_final_execution_review"
    )
    assert dry_run["dry_run"]["staging_count_still_matches"] is True
    assert dry_run["dry_run"]["learning_sample_count_still_matches"] is True
    assert dry_run["dry_run"]["transaction_required"] is True
    assert dry_run["dry_run"]["rollback_required"] is True
    assert dry_run["dry_run"]["simulated_mutation_count"] >= 1
    assert dry_run["dry_run"]["manual_operation_count"] >= 1
    assert dry_run["dry_run"]["allowed_tables"] == ["dataset2_staging_records"]
    assert "learning_samples" in dry_run["dry_run"]["forbidden_tables"]
    assert dry_run["dry_run"]["contains_sql"] is False
    assert dry_run["dry_run"]["contains_executable_code"] is False
    assert dry_run["dry_run"]["can_execute_now"] is False
    assert dry_run["dry_run"]["record_bodies_included"] is False
    assert dry_run["dry_run"]["affected_rows_body_included"] is False
    assert (
        dry_run["decision"][
            "controlled_cleanup_apply_execution_plan_execution_final_execution_dry_run_recorded"
        ]
        is True
    )
    assert (
        dry_run["decision"][
            "controlled_cleanup_apply_execution_plan_execution_final_execution_dry_run_ready_for_review"
        ]
        is True
    )
    assert dry_run["decision"]["cleanup_execution_approved_now"] is False
    assert dry_run["decision"]["cleanup_application_allowed_now"] is False
    assert dry_run["decision"]["cleanup_executed_now"] is False
    assert dry_run["decision"]["can_execute_cleanup_now"] is False
    assert dry_run["decision"]["writes_staging_records_now"] is False
    assert dry_run["decision"]["writes_learning_samples_now"] is False
    assert dry_run["decision"]["mutates_staging_records_now"] is False
    assert dry_run["decision"]["training_started_now"] is False
    assert dry_run["decision"]["training_freeze_allowed"] is False
    assert dry_run["decision"]["can_start_training_now"] is False
    assert staging_after == staging_before
    assert learning_after == learning_before
    assert "evidence_package" not in dry_run
    check_status = {check["name"]: check["status"] for check in dry_run["checks"]}
    assert check_status["apply_execution_plan_execution_final_execution_preflight_available"] == "passed"
    assert check_status["apply_execution_plan_execution_final_execution_preflight_ready_for_dry_run"] == "passed"
    assert check_status["source_preflight_blocked_checks_clear"] == "passed"
    assert check_status["lock_key_present"] == "passed"
    assert check_status["staging_count_still_matches_preflight"] == "passed"
    assert check_status["learning_samples_unchanged"] == "passed"
    assert check_status["aggregate_final_execution_simulation_present"] == "passed"
    assert check_status["manual_backfill_separated"] == "warning"
    assert check_status["transaction_and_rollback_required"] == "passed"
    assert check_status["table_scope_limited"] == "passed"
    assert check_status["simulation_contains_no_executable_payload"] == "passed"
    assert check_status["aggregate_only_no_record_bodies"] == "passed"
    assert check_status["dry_run_metadata_present"] == "passed"
    assert check_status["dry_run_decision_allows_final_execution_review_only"] == "passed"
    assert check_status["source_preflight_kept_execution_blocked"] == "passed"
    assert check_status["cleanup_and_training_remain_blocked"] == "passed"

    rejected = service.staging_cleanup_execution_controlled_apply_execution_plan_execution_final_execution_dry_run(
        apply_execution_plan_execution_final_execution_preflight_id=final_execution_preflight["event_id"],
        simulated_by="tester",
        dry_run_decision="rejected",
    )
    assert rejected["status"] == "controlled_cleanup_apply_execution_plan_execution_final_execution_dry_run_blocked"
    assert (
        rejected["decision"][
            "controlled_cleanup_apply_execution_plan_execution_final_execution_dry_run_recorded"
        ]
        is True
    )
    assert (
        rejected["decision"][
            "controlled_cleanup_apply_execution_plan_execution_final_execution_dry_run_ready_for_review"
        ]
        is False
    )
    assert rejected["decision"]["can_execute_cleanup_now"] is False
    assert rejected["decision"]["writes_learning_samples_now"] is False

    dry_runs = service.list_staging_cleanup_execution_controlled_apply_execution_plan_execution_final_execution_dry_runs(
        limit=5
    )
    assert dry_runs[0]["id"] == rejected["event_id"]
    assert dry_runs[1]["id"] == dry_run["event_id"]
    assert dry_runs[1]["request"]["simulated_by"] == "tester"
    assert "evidence_package" not in dry_runs[1]


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
    cleanup_execution_plan_preflight = client.post(
        "/api/learning/dataset2/staging/cleanup-execution-plan/preflight",
        json={"execution_plan_id": cleanup_execution_plan.json().get("event_id"), "requested_by": "api-test"},
    )
    cleanup_execution_plan_preflights = client.get(
        "/api/learning/dataset2/staging/cleanup-execution-plan/preflights",
        params={"limit": 3},
    )
    cleanup_execution_controlled_dry_run = client.post(
        "/api/learning/dataset2/staging/cleanup-execution-controlled-dry-run",
        json={"plan_preflight_id": cleanup_execution_plan_preflight.json().get("event_id"), "simulated_by": "api-test"},
    )
    cleanup_execution_controlled_dry_runs = client.get(
        "/api/learning/dataset2/staging/cleanup-execution-controlled-dry-runs",
        params={"limit": 3},
    )
    cleanup_execution_controlled_dry_run_review = client.post(
        "/api/learning/dataset2/staging/cleanup-execution-controlled-dry-run-review",
        json={"controlled_dry_run_id": cleanup_execution_controlled_dry_run.json().get("event_id"), "reviewed_by": "api-test"},
    )
    cleanup_execution_controlled_dry_run_reviews = client.get(
        "/api/learning/dataset2/staging/cleanup-execution-controlled-dry-run-reviews",
        params={"limit": 3},
    )
    cleanup_execution_controlled_approval = client.post(
        "/api/learning/dataset2/staging/cleanup-execution-controlled-approval",
        json={"controlled_review_id": cleanup_execution_controlled_dry_run_review.json().get("event_id"), "approved_by": "api-test"},
    )
    cleanup_execution_controlled_approvals = client.get(
        "/api/learning/dataset2/staging/cleanup-execution-controlled-approvals",
        params={"limit": 3},
    )
    cleanup_execution_controlled_preflight = client.post(
        "/api/learning/dataset2/staging/cleanup-execution-controlled-preflight",
        json={"controlled_approval_id": cleanup_execution_controlled_approval.json().get("event_id"), "requested_by": "api-test"},
    )
    cleanup_execution_controlled_preflights = client.get(
        "/api/learning/dataset2/staging/cleanup-execution-controlled-preflights",
        params={"limit": 3},
    )
    cleanup_execution_controlled_apply_dry_run = client.post(
        "/api/learning/dataset2/staging/cleanup-execution-controlled-apply-dry-run",
        json={"controlled_preflight_id": cleanup_execution_controlled_preflight.json().get("event_id"), "simulated_by": "api-test"},
    )
    cleanup_execution_controlled_apply_dry_runs = client.get(
        "/api/learning/dataset2/staging/cleanup-execution-controlled-apply-dry-runs",
        params={"limit": 3},
    )
    cleanup_execution_controlled_apply_dry_run_review = client.post(
        "/api/learning/dataset2/staging/cleanup-execution-controlled-apply-dry-run-review",
        json={
            "apply_dry_run_id": cleanup_execution_controlled_apply_dry_run.json().get("event_id"),
            "reviewed_by": "api-test",
        },
    )
    cleanup_execution_controlled_apply_dry_run_reviews = client.get(
        "/api/learning/dataset2/staging/cleanup-execution-controlled-apply-dry-run-reviews",
        params={"limit": 3},
    )
    cleanup_execution_controlled_apply_approval = client.post(
        "/api/learning/dataset2/staging/cleanup-execution-controlled-apply-approval",
        json={
            "apply_review_id": cleanup_execution_controlled_apply_dry_run_review.json().get("event_id"),
            "approved_by": "api-test",
        },
    )
    cleanup_execution_controlled_apply_approvals = client.get(
        "/api/learning/dataset2/staging/cleanup-execution-controlled-apply-approvals",
        params={"limit": 3},
    )
    cleanup_execution_controlled_apply_preflight = client.post(
        "/api/learning/dataset2/staging/cleanup-execution-controlled-apply-preflight",
        json={
            "apply_approval_id": cleanup_execution_controlled_apply_approval.json().get("event_id"),
            "requested_by": "api-test",
        },
    )
    cleanup_execution_controlled_apply_preflights = client.get(
        "/api/learning/dataset2/staging/cleanup-execution-controlled-apply-preflights",
        params={"limit": 3},
    )
    cleanup_execution_controlled_apply_execution_dry_run = client.post(
        "/api/learning/dataset2/staging/cleanup-execution-controlled-apply-execution-dry-run",
        json={
            "apply_preflight_id": cleanup_execution_controlled_apply_preflight.json().get("event_id"),
            "simulated_by": "api-test",
        },
    )
    cleanup_execution_controlled_apply_execution_dry_runs = client.get(
        "/api/learning/dataset2/staging/cleanup-execution-controlled-apply-execution-dry-runs",
        params={"limit": 3},
    )
    cleanup_execution_controlled_apply_execution_dry_run_review = client.post(
        "/api/learning/dataset2/staging/cleanup-execution-controlled-apply-execution-dry-run-review",
        json={
            "apply_execution_dry_run_id": cleanup_execution_controlled_apply_execution_dry_run.json().get("event_id"),
            "reviewed_by": "api-test",
        },
    )
    cleanup_execution_controlled_apply_execution_dry_run_reviews = client.get(
        "/api/learning/dataset2/staging/cleanup-execution-controlled-apply-execution-dry-run-reviews",
        params={"limit": 3},
    )
    cleanup_execution_controlled_apply_execution_plan = client.post(
        "/api/learning/dataset2/staging/cleanup-execution-controlled-apply-execution-plan",
        json={
            "apply_execution_review_id": cleanup_execution_controlled_apply_execution_dry_run_review.json().get("event_id"),
            "planned_by": "api-test",
        },
    )
    cleanup_execution_controlled_apply_execution_plans = client.get(
        "/api/learning/dataset2/staging/cleanup-execution-controlled-apply-execution-plans",
        params={"limit": 3},
    )
    cleanup_execution_controlled_apply_execution_plan_preflight = client.post(
        "/api/learning/dataset2/staging/cleanup-execution-controlled-apply-execution-plan-preflight",
        json={
            "apply_execution_plan_id": cleanup_execution_controlled_apply_execution_plan.json().get("event_id"),
            "requested_by": "api-test",
        },
    )
    cleanup_execution_controlled_apply_execution_plan_preflights = client.get(
        "/api/learning/dataset2/staging/cleanup-execution-controlled-apply-execution-plan-preflights",
        params={"limit": 3},
    )
    cleanup_execution_controlled_apply_execution_plan_dry_run = client.post(
        "/api/learning/dataset2/staging/cleanup-execution-controlled-apply-execution-plan-dry-run",
        json={
            "apply_execution_plan_preflight_id": cleanup_execution_controlled_apply_execution_plan_preflight.json().get("event_id"),
            "simulated_by": "api-test",
        },
    )
    cleanup_execution_controlled_apply_execution_plan_dry_runs = client.get(
        "/api/learning/dataset2/staging/cleanup-execution-controlled-apply-execution-plan-dry-runs",
        params={"limit": 3},
    )
    cleanup_execution_controlled_apply_execution_plan_dry_run_review = client.post(
        "/api/learning/dataset2/staging/cleanup-execution-controlled-apply-execution-plan-dry-run-review",
        json={
            "apply_execution_plan_dry_run_id": cleanup_execution_controlled_apply_execution_plan_dry_run.json().get("event_id"),
            "reviewed_by": "api-test",
        },
    )
    cleanup_execution_controlled_apply_execution_plan_dry_run_reviews = client.get(
        "/api/learning/dataset2/staging/cleanup-execution-controlled-apply-execution-plan-dry-run-reviews",
        params={"limit": 3},
    )
    cleanup_execution_controlled_apply_execution_plan_execution_approval = client.post(
        "/api/learning/dataset2/staging/cleanup-execution-controlled-apply-execution-plan-execution-approval",
        json={
            "apply_execution_plan_dry_run_review_id": cleanup_execution_controlled_apply_execution_plan_dry_run_review.json().get("event_id"),
            "approved_by": "api-test",
        },
    )
    cleanup_execution_controlled_apply_execution_plan_execution_approvals = client.get(
        "/api/learning/dataset2/staging/cleanup-execution-controlled-apply-execution-plan-execution-approvals",
        params={"limit": 3},
    )
    cleanup_execution_controlled_apply_execution_plan_execution_preflight = client.post(
        "/api/learning/dataset2/staging/cleanup-execution-controlled-apply-execution-plan-execution-preflight",
        json={
            "apply_execution_plan_execution_approval_id": cleanup_execution_controlled_apply_execution_plan_execution_approval.json().get("event_id"),
            "requested_by": "api-test",
        },
    )
    cleanup_execution_controlled_apply_execution_plan_execution_preflights = client.get(
        "/api/learning/dataset2/staging/cleanup-execution-controlled-apply-execution-plan-execution-preflights",
        params={"limit": 3},
    )
    cleanup_execution_controlled_apply_execution_plan_execution_dry_run = client.post(
        "/api/learning/dataset2/staging/cleanup-execution-controlled-apply-execution-plan-execution-dry-run",
        json={
            "apply_execution_plan_execution_preflight_id": cleanup_execution_controlled_apply_execution_plan_execution_preflight.json().get("event_id"),
            "simulated_by": "api-test",
        },
    )
    cleanup_execution_controlled_apply_execution_plan_execution_dry_runs = client.get(
        "/api/learning/dataset2/staging/cleanup-execution-controlled-apply-execution-plan-execution-dry-runs",
        params={"limit": 3},
    )
    cleanup_execution_controlled_apply_execution_plan_execution_dry_run_review = client.post(
        "/api/learning/dataset2/staging/cleanup-execution-controlled-apply-execution-plan-execution-dry-run-review",
        json={
            "apply_execution_plan_execution_dry_run_id": cleanup_execution_controlled_apply_execution_plan_execution_dry_run.json().get("event_id"),
            "reviewed_by": "api-test",
        },
    )
    cleanup_execution_controlled_apply_execution_plan_execution_dry_run_reviews = client.get(
        "/api/learning/dataset2/staging/cleanup-execution-controlled-apply-execution-plan-execution-dry-run-reviews",
        params={"limit": 3},
    )
    cleanup_execution_controlled_apply_execution_plan_execution_final_approval = client.post(
        "/api/learning/dataset2/staging/cleanup-execution-controlled-apply-execution-plan-execution-final-approval",
        json={
            "apply_execution_plan_execution_dry_run_review_id": cleanup_execution_controlled_apply_execution_plan_execution_dry_run_review.json().get("event_id"),
            "approved_by": "api-test",
        },
    )
    cleanup_execution_controlled_apply_execution_plan_execution_final_approvals = client.get(
        "/api/learning/dataset2/staging/cleanup-execution-controlled-apply-execution-plan-execution-final-approvals",
        params={"limit": 3},
    )
    cleanup_execution_controlled_apply_execution_plan_execution_final_preflight = client.post(
        "/api/learning/dataset2/staging/cleanup-execution-controlled-apply-execution-plan-execution-final-preflight",
        json={
            "apply_execution_plan_execution_final_approval_id": cleanup_execution_controlled_apply_execution_plan_execution_final_approval.json().get("event_id"),
            "requested_by": "api-test",
        },
    )
    cleanup_execution_controlled_apply_execution_plan_execution_final_preflights = client.get(
        "/api/learning/dataset2/staging/cleanup-execution-controlled-apply-execution-plan-execution-final-preflights",
        params={"limit": 3},
    )
    cleanup_execution_controlled_apply_execution_plan_execution_final_dry_run = client.post(
        "/api/learning/dataset2/staging/cleanup-execution-controlled-apply-execution-plan-execution-final-dry-run",
        json={
            "apply_execution_plan_execution_final_preflight_id": cleanup_execution_controlled_apply_execution_plan_execution_final_preflight.json().get("event_id"),
            "simulated_by": "api-test",
        },
    )
    cleanup_execution_controlled_apply_execution_plan_execution_final_dry_runs = client.get(
        "/api/learning/dataset2/staging/cleanup-execution-controlled-apply-execution-plan-execution-final-dry-runs",
        params={"limit": 3},
    )
    cleanup_execution_controlled_apply_execution_plan_execution_final_dry_run_review = client.post(
        "/api/learning/dataset2/staging/cleanup-execution-controlled-apply-execution-plan-execution-final-dry-run-review",
        json={
            "apply_execution_plan_execution_final_dry_run_id": cleanup_execution_controlled_apply_execution_plan_execution_final_dry_run.json().get("event_id"),
            "reviewed_by": "api-test",
        },
    )
    cleanup_execution_controlled_apply_execution_plan_execution_final_dry_run_reviews = client.get(
        "/api/learning/dataset2/staging/cleanup-execution-controlled-apply-execution-plan-execution-final-dry-run-reviews",
        params={"limit": 3},
    )
    cleanup_execution_controlled_apply_execution_plan_execution_final_execution_approval = client.post(
        "/api/learning/dataset2/staging/cleanup-execution-controlled-apply-execution-plan-execution-final-execution-approval",
        json={
            "apply_execution_plan_execution_final_dry_run_review_id": cleanup_execution_controlled_apply_execution_plan_execution_final_dry_run_review.json().get("event_id"),
            "approved_by": "api-test",
        },
    )
    cleanup_execution_controlled_apply_execution_plan_execution_final_execution_approvals = client.get(
        "/api/learning/dataset2/staging/cleanup-execution-controlled-apply-execution-plan-execution-final-execution-approvals",
        params={"limit": 3},
    )
    cleanup_execution_controlled_apply_execution_plan_execution_final_execution_preflight = client.post(
        "/api/learning/dataset2/staging/cleanup-execution-controlled-apply-execution-plan-execution-final-execution-preflight",
        json={
            "apply_execution_plan_execution_final_execution_approval_id": cleanup_execution_controlled_apply_execution_plan_execution_final_execution_approval.json().get("event_id"),
            "requested_by": "api-test",
        },
    )
    cleanup_execution_controlled_apply_execution_plan_execution_final_execution_preflights = client.get(
        "/api/learning/dataset2/staging/cleanup-execution-controlled-apply-execution-plan-execution-final-execution-preflights",
        params={"limit": 3},
    )
    cleanup_execution_controlled_apply_execution_plan_execution_final_execution_dry_run = client.post(
        "/api/learning/dataset2/staging/cleanup-execution-controlled-apply-execution-plan-execution-final-execution-dry-run",
        json={
            "apply_execution_plan_execution_final_execution_preflight_id": cleanup_execution_controlled_apply_execution_plan_execution_final_execution_preflight.json().get("event_id"),
            "simulated_by": "api-test",
        },
    )
    cleanup_execution_controlled_apply_execution_plan_execution_final_execution_dry_runs = client.get(
        "/api/learning/dataset2/staging/cleanup-execution-controlled-apply-execution-plan-execution-final-execution-dry-runs",
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
    assert cleanup_execution_plan_preflight.status_code == 200
    assert cleanup_execution_plan_preflights.status_code == 200
    assert cleanup_execution_controlled_dry_run.status_code == 200
    assert cleanup_execution_controlled_dry_runs.status_code == 200
    assert cleanup_execution_controlled_dry_run_review.status_code == 200
    assert cleanup_execution_controlled_dry_run_reviews.status_code == 200
    assert cleanup_execution_controlled_approval.status_code == 200
    assert cleanup_execution_controlled_approvals.status_code == 200
    assert cleanup_execution_controlled_preflight.status_code == 200
    assert cleanup_execution_controlled_preflights.status_code == 200
    assert cleanup_execution_controlled_apply_dry_run.status_code == 200
    assert cleanup_execution_controlled_apply_dry_runs.status_code == 200
    assert cleanup_execution_controlled_apply_dry_run_review.status_code == 200
    assert cleanup_execution_controlled_apply_dry_run_reviews.status_code == 200
    assert cleanup_execution_controlled_apply_approval.status_code == 200
    assert cleanup_execution_controlled_apply_approvals.status_code == 200
    assert cleanup_execution_controlled_apply_preflight.status_code == 200
    assert cleanup_execution_controlled_apply_preflights.status_code == 200
    assert cleanup_execution_controlled_apply_execution_dry_run.status_code == 200
    assert cleanup_execution_controlled_apply_execution_dry_runs.status_code == 200
    assert cleanup_execution_controlled_apply_execution_dry_run_review.status_code == 200
    assert cleanup_execution_controlled_apply_execution_dry_run_reviews.status_code == 200
    assert cleanup_execution_controlled_apply_execution_plan.status_code == 200
    assert cleanup_execution_controlled_apply_execution_plans.status_code == 200
    assert cleanup_execution_controlled_apply_execution_plan_preflight.status_code == 200
    assert cleanup_execution_controlled_apply_execution_plan_preflights.status_code == 200
    assert cleanup_execution_controlled_apply_execution_plan_dry_run.status_code == 200
    assert cleanup_execution_controlled_apply_execution_plan_dry_runs.status_code == 200
    assert cleanup_execution_controlled_apply_execution_plan_dry_run_review.status_code == 200
    assert cleanup_execution_controlled_apply_execution_plan_dry_run_reviews.status_code == 200
    assert cleanup_execution_controlled_apply_execution_plan_execution_approval.status_code == 200
    assert cleanup_execution_controlled_apply_execution_plan_execution_approvals.status_code == 200
    assert cleanup_execution_controlled_apply_execution_plan_execution_preflight.status_code == 200
    assert cleanup_execution_controlled_apply_execution_plan_execution_preflights.status_code == 200
    assert cleanup_execution_controlled_apply_execution_plan_execution_dry_run.status_code == 200
    assert cleanup_execution_controlled_apply_execution_plan_execution_dry_runs.status_code == 200
    assert cleanup_execution_controlled_apply_execution_plan_execution_dry_run_review.status_code == 200
    assert cleanup_execution_controlled_apply_execution_plan_execution_dry_run_reviews.status_code == 200
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_approval.status_code == 200
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_approvals.status_code == 200
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_preflight.status_code == 200
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_preflights.status_code == 200
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_dry_run.status_code == 200
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_dry_runs.status_code == 200
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_dry_run_review.status_code == 200
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_dry_run_reviews.status_code == 200
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_execution_approval.status_code == 200
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_execution_approvals.status_code == 200
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_execution_preflight.status_code == 200
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_execution_preflights.status_code == 200
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_execution_dry_run.status_code == 200
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_execution_dry_runs.status_code == 200
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
    assert cleanup_execution_plan_preflight.json()["preflight"]["can_execute_now"] is False
    assert cleanup_execution_plan_preflight.json()["preflight"]["record_bodies_included"] is False
    assert cleanup_execution_plan_preflight.json()["decision"]["cleanup_execution_plan_preflight_recorded"] is True
    assert cleanup_execution_plan_preflight.json()["decision"]["cleanup_execution_approved_now"] is False
    assert cleanup_execution_plan_preflight.json()["decision"]["cleanup_application_allowed_now"] is False
    assert cleanup_execution_plan_preflight.json()["decision"]["cleanup_executed_now"] is False
    assert cleanup_execution_plan_preflight.json()["decision"]["can_execute_cleanup_now"] is False
    assert cleanup_execution_plan_preflight.json()["decision"]["writes_learning_samples_now"] is False
    assert cleanup_execution_plan_preflight.json()["decision"]["training_started_now"] is False
    assert cleanup_execution_plan_preflights.json()[0]["request"]["requested_by"] == "api-test"
    assert cleanup_execution_controlled_dry_run.json()["simulation"]["can_execute_now"] is False
    assert cleanup_execution_controlled_dry_run.json()["simulation"]["record_bodies_included"] is False
    assert cleanup_execution_controlled_dry_run.json()["decision"]["controlled_cleanup_dry_run_recorded"] is True
    assert cleanup_execution_controlled_dry_run.json()["decision"]["cleanup_execution_approved_now"] is False
    assert cleanup_execution_controlled_dry_run.json()["decision"]["cleanup_application_allowed_now"] is False
    assert cleanup_execution_controlled_dry_run.json()["decision"]["cleanup_executed_now"] is False
    assert cleanup_execution_controlled_dry_run.json()["decision"]["can_execute_cleanup_now"] is False
    assert cleanup_execution_controlled_dry_run.json()["decision"]["writes_learning_samples_now"] is False
    assert cleanup_execution_controlled_dry_run.json()["decision"]["training_started_now"] is False
    assert cleanup_execution_controlled_dry_runs.json()[0]["dry_run"]["simulated_by"] == "api-test"
    assert cleanup_execution_controlled_dry_run_review.json()["simulation_summary"]["can_execute_now"] is False
    assert cleanup_execution_controlled_dry_run_review.json()["simulation_summary"]["record_bodies_included"] is False
    assert cleanup_execution_controlled_dry_run_review.json()["decision"]["controlled_cleanup_dry_run_review_recorded"] is True
    assert cleanup_execution_controlled_dry_run_review.json()["decision"]["cleanup_execution_approved_now"] is False
    assert cleanup_execution_controlled_dry_run_review.json()["decision"]["cleanup_application_allowed_now"] is False
    assert cleanup_execution_controlled_dry_run_review.json()["decision"]["cleanup_executed_now"] is False
    assert cleanup_execution_controlled_dry_run_review.json()["decision"]["can_execute_cleanup_now"] is False
    assert cleanup_execution_controlled_dry_run_review.json()["decision"]["writes_learning_samples_now"] is False
    assert cleanup_execution_controlled_dry_run_review.json()["decision"]["training_started_now"] is False
    assert cleanup_execution_controlled_dry_run_reviews.json()[0]["review"]["reviewed_by"] == "api-test"
    assert cleanup_execution_controlled_approval.json()["approval_scope"]["can_execute_now"] is False
    assert cleanup_execution_controlled_approval.json()["approval_scope"]["record_bodies_included"] is False
    assert cleanup_execution_controlled_approval.json()["decision"]["controlled_cleanup_execution_approval_recorded"] is True
    assert cleanup_execution_controlled_approval.json()["decision"]["cleanup_execution_approved_now"] is False
    assert cleanup_execution_controlled_approval.json()["decision"]["cleanup_application_allowed_now"] is False
    assert cleanup_execution_controlled_approval.json()["decision"]["cleanup_executed_now"] is False
    assert cleanup_execution_controlled_approval.json()["decision"]["can_execute_cleanup_now"] is False
    assert cleanup_execution_controlled_approval.json()["decision"]["writes_learning_samples_now"] is False
    assert cleanup_execution_controlled_approval.json()["decision"]["training_started_now"] is False
    assert cleanup_execution_controlled_approvals.json()[0]["approval"]["approved_by"] == "api-test"
    assert cleanup_execution_controlled_preflight.json()["preflight"]["can_execute_now"] is False
    assert cleanup_execution_controlled_preflight.json()["preflight"]["record_bodies_included"] is False
    assert cleanup_execution_controlled_preflight.json()["decision"]["controlled_cleanup_execution_preflight_recorded"] is True
    assert cleanup_execution_controlled_preflight.json()["decision"]["cleanup_execution_approved_now"] is False
    assert cleanup_execution_controlled_preflight.json()["decision"]["cleanup_application_allowed_now"] is False
    assert cleanup_execution_controlled_preflight.json()["decision"]["cleanup_executed_now"] is False
    assert cleanup_execution_controlled_preflight.json()["decision"]["can_execute_cleanup_now"] is False
    assert cleanup_execution_controlled_preflight.json()["decision"]["writes_learning_samples_now"] is False
    assert cleanup_execution_controlled_preflight.json()["decision"]["training_started_now"] is False
    assert cleanup_execution_controlled_preflights.json()[0]["request"]["requested_by"] == "api-test"
    assert cleanup_execution_controlled_apply_dry_run.json()["simulation"]["can_execute_now"] is False
    assert cleanup_execution_controlled_apply_dry_run.json()["simulation"]["contains_sql"] is False
    assert cleanup_execution_controlled_apply_dry_run.json()["simulation"]["record_bodies_included"] is False
    assert cleanup_execution_controlled_apply_dry_run.json()["decision"]["controlled_cleanup_apply_dry_run_recorded"] is True
    assert cleanup_execution_controlled_apply_dry_run.json()["decision"]["cleanup_execution_approved_now"] is False
    assert cleanup_execution_controlled_apply_dry_run.json()["decision"]["cleanup_application_allowed_now"] is False
    assert cleanup_execution_controlled_apply_dry_run.json()["decision"]["cleanup_executed_now"] is False
    assert cleanup_execution_controlled_apply_dry_run.json()["decision"]["can_execute_cleanup_now"] is False
    assert cleanup_execution_controlled_apply_dry_run.json()["decision"]["writes_learning_samples_now"] is False
    assert cleanup_execution_controlled_apply_dry_run.json()["decision"]["training_started_now"] is False
    assert cleanup_execution_controlled_apply_dry_runs.json()[0]["dry_run"]["simulated_by"] == "api-test"
    assert cleanup_execution_controlled_apply_dry_run_review.json()["simulation_summary"]["can_execute_now"] is False
    assert cleanup_execution_controlled_apply_dry_run_review.json()["simulation_summary"]["contains_sql"] is False
    assert cleanup_execution_controlled_apply_dry_run_review.json()["simulation_summary"]["record_bodies_included"] is False
    assert cleanup_execution_controlled_apply_dry_run_review.json()["decision"]["controlled_cleanup_apply_dry_run_review_recorded"] is True
    assert cleanup_execution_controlled_apply_dry_run_review.json()["decision"]["cleanup_execution_approved_now"] is False
    assert cleanup_execution_controlled_apply_dry_run_review.json()["decision"]["cleanup_application_allowed_now"] is False
    assert cleanup_execution_controlled_apply_dry_run_review.json()["decision"]["cleanup_executed_now"] is False
    assert cleanup_execution_controlled_apply_dry_run_review.json()["decision"]["can_execute_cleanup_now"] is False
    assert cleanup_execution_controlled_apply_dry_run_review.json()["decision"]["writes_learning_samples_now"] is False
    assert cleanup_execution_controlled_apply_dry_run_review.json()["decision"]["training_started_now"] is False
    assert cleanup_execution_controlled_apply_dry_run_reviews.json()[0]["review"]["reviewed_by"] == "api-test"
    assert cleanup_execution_controlled_apply_approval.json()["approval_scope"]["can_execute_now"] is False
    assert cleanup_execution_controlled_apply_approval.json()["approval_scope"]["contains_sql"] is False
    assert cleanup_execution_controlled_apply_approval.json()["approval_scope"]["record_bodies_included"] is False
    assert cleanup_execution_controlled_apply_approval.json()["decision"]["controlled_cleanup_apply_execution_approval_recorded"] is True
    assert cleanup_execution_controlled_apply_approval.json()["decision"]["cleanup_execution_approved_now"] is False
    assert cleanup_execution_controlled_apply_approval.json()["decision"]["cleanup_application_allowed_now"] is False
    assert cleanup_execution_controlled_apply_approval.json()["decision"]["cleanup_executed_now"] is False
    assert cleanup_execution_controlled_apply_approval.json()["decision"]["can_execute_cleanup_now"] is False
    assert cleanup_execution_controlled_apply_approval.json()["decision"]["writes_learning_samples_now"] is False
    assert cleanup_execution_controlled_apply_approval.json()["decision"]["training_started_now"] is False
    assert cleanup_execution_controlled_apply_approvals.json()[0]["approval"]["approved_by"] == "api-test"
    assert cleanup_execution_controlled_apply_preflight.json()["preflight"]["can_execute_now"] is False
    assert cleanup_execution_controlled_apply_preflight.json()["preflight"]["contains_sql"] is False
    assert cleanup_execution_controlled_apply_preflight.json()["preflight"]["record_bodies_included"] is False
    assert cleanup_execution_controlled_apply_preflight.json()["decision"]["controlled_cleanup_apply_execution_preflight_recorded"] is True
    assert cleanup_execution_controlled_apply_preflight.json()["decision"]["cleanup_execution_approved_now"] is False
    assert cleanup_execution_controlled_apply_preflight.json()["decision"]["cleanup_application_allowed_now"] is False
    assert cleanup_execution_controlled_apply_preflight.json()["decision"]["cleanup_executed_now"] is False
    assert cleanup_execution_controlled_apply_preflight.json()["decision"]["can_execute_cleanup_now"] is False
    assert cleanup_execution_controlled_apply_preflight.json()["decision"]["writes_learning_samples_now"] is False
    assert cleanup_execution_controlled_apply_preflight.json()["decision"]["training_started_now"] is False
    assert cleanup_execution_controlled_apply_preflights.json()[0]["request"]["requested_by"] == "api-test"
    assert cleanup_execution_controlled_apply_execution_dry_run.json()["simulation"]["can_execute_now"] is False
    assert cleanup_execution_controlled_apply_execution_dry_run.json()["simulation"]["contains_sql"] is False
    assert cleanup_execution_controlled_apply_execution_dry_run.json()["simulation"]["record_bodies_included"] is False
    assert cleanup_execution_controlled_apply_execution_dry_run.json()["decision"]["controlled_cleanup_apply_execution_dry_run_recorded"] is True
    assert cleanup_execution_controlled_apply_execution_dry_run.json()["decision"]["cleanup_execution_approved_now"] is False
    assert cleanup_execution_controlled_apply_execution_dry_run.json()["decision"]["cleanup_application_allowed_now"] is False
    assert cleanup_execution_controlled_apply_execution_dry_run.json()["decision"]["cleanup_executed_now"] is False
    assert cleanup_execution_controlled_apply_execution_dry_run.json()["decision"]["can_execute_cleanup_now"] is False
    assert cleanup_execution_controlled_apply_execution_dry_run.json()["decision"]["writes_learning_samples_now"] is False
    assert cleanup_execution_controlled_apply_execution_dry_run.json()["decision"]["training_started_now"] is False
    assert cleanup_execution_controlled_apply_execution_dry_runs.json()[0]["dry_run"]["simulated_by"] == "api-test"
    assert cleanup_execution_controlled_apply_execution_dry_run_review.json()["simulation_summary"]["can_execute_now"] is False
    assert cleanup_execution_controlled_apply_execution_dry_run_review.json()["simulation_summary"]["contains_sql"] is False
    assert cleanup_execution_controlled_apply_execution_dry_run_review.json()["simulation_summary"]["record_bodies_included"] is False
    assert cleanup_execution_controlled_apply_execution_dry_run_review.json()["decision"]["controlled_cleanup_apply_execution_dry_run_review_recorded"] is True
    assert cleanup_execution_controlled_apply_execution_dry_run_review.json()["decision"]["cleanup_execution_approved_now"] is False
    assert cleanup_execution_controlled_apply_execution_dry_run_review.json()["decision"]["cleanup_application_allowed_now"] is False
    assert cleanup_execution_controlled_apply_execution_dry_run_review.json()["decision"]["cleanup_executed_now"] is False
    assert cleanup_execution_controlled_apply_execution_dry_run_review.json()["decision"]["can_execute_cleanup_now"] is False
    assert cleanup_execution_controlled_apply_execution_dry_run_review.json()["decision"]["writes_learning_samples_now"] is False
    assert cleanup_execution_controlled_apply_execution_dry_run_review.json()["decision"]["training_started_now"] is False
    assert cleanup_execution_controlled_apply_execution_dry_run_reviews.json()[0]["review"]["reviewed_by"] == "api-test"
    assert cleanup_execution_controlled_apply_execution_plan.json()["execution_plan"]["can_execute_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan.json()["execution_plan"]["contains_sql"] is False
    assert cleanup_execution_controlled_apply_execution_plan.json()["execution_plan"]["record_bodies_included"] is False
    assert cleanup_execution_controlled_apply_execution_plan.json()["decision"]["controlled_cleanup_apply_execution_plan_recorded"] is True
    assert cleanup_execution_controlled_apply_execution_plan.json()["decision"]["cleanup_execution_approved_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan.json()["decision"]["cleanup_application_allowed_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan.json()["decision"]["cleanup_executed_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan.json()["decision"]["can_execute_cleanup_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan.json()["decision"]["writes_learning_samples_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan.json()["decision"]["training_started_now"] is False
    assert cleanup_execution_controlled_apply_execution_plans.json()[0]["planning"]["planned_by"] == "api-test"
    assert cleanup_execution_controlled_apply_execution_plan_preflight.json()["preflight"]["can_execute_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_preflight.json()["preflight"]["contains_sql"] is False
    assert cleanup_execution_controlled_apply_execution_plan_preflight.json()["preflight"]["record_bodies_included"] is False
    assert cleanup_execution_controlled_apply_execution_plan_preflight.json()["decision"]["controlled_cleanup_apply_execution_plan_preflight_recorded"] is True
    assert cleanup_execution_controlled_apply_execution_plan_preflight.json()["decision"]["cleanup_execution_approved_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_preflight.json()["decision"]["cleanup_application_allowed_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_preflight.json()["decision"]["cleanup_executed_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_preflight.json()["decision"]["can_execute_cleanup_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_preflight.json()["decision"]["writes_learning_samples_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_preflight.json()["decision"]["training_started_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_preflights.json()[0]["request"]["requested_by"] == "api-test"
    assert cleanup_execution_controlled_apply_execution_plan_dry_run.json()["dry_run"]["can_execute_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_dry_run.json()["dry_run"]["contains_sql"] is False
    assert cleanup_execution_controlled_apply_execution_plan_dry_run.json()["dry_run"]["record_bodies_included"] is False
    assert cleanup_execution_controlled_apply_execution_plan_dry_run.json()["decision"]["controlled_cleanup_apply_execution_plan_dry_run_recorded"] is True
    assert cleanup_execution_controlled_apply_execution_plan_dry_run.json()["decision"]["cleanup_execution_approved_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_dry_run.json()["decision"]["cleanup_application_allowed_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_dry_run.json()["decision"]["cleanup_executed_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_dry_run.json()["decision"]["can_execute_cleanup_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_dry_run.json()["decision"]["writes_learning_samples_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_dry_run.json()["decision"]["training_started_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_dry_runs.json()[0]["request"]["simulated_by"] == "api-test"
    assert cleanup_execution_controlled_apply_execution_plan_dry_run_review.json()["dry_run_summary"]["can_execute_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_dry_run_review.json()["dry_run_summary"]["contains_sql"] is False
    assert cleanup_execution_controlled_apply_execution_plan_dry_run_review.json()["dry_run_summary"]["record_bodies_included"] is False
    assert cleanup_execution_controlled_apply_execution_plan_dry_run_review.json()["decision"]["controlled_cleanup_apply_execution_plan_dry_run_review_recorded"] is True
    assert cleanup_execution_controlled_apply_execution_plan_dry_run_review.json()["decision"]["cleanup_execution_approved_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_dry_run_review.json()["decision"]["cleanup_application_allowed_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_dry_run_review.json()["decision"]["cleanup_executed_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_dry_run_review.json()["decision"]["can_execute_cleanup_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_dry_run_review.json()["decision"]["writes_learning_samples_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_dry_run_review.json()["decision"]["training_started_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_dry_run_reviews.json()[0]["review"]["reviewed_by"] == "api-test"
    assert cleanup_execution_controlled_apply_execution_plan_execution_approval.json()["approval_scope"]["can_execute_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_approval.json()["approval_scope"]["contains_sql"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_approval.json()["approval_scope"]["record_bodies_included"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_approval.json()["decision"]["controlled_cleanup_apply_execution_plan_execution_approval_recorded"] is True
    assert cleanup_execution_controlled_apply_execution_plan_execution_approval.json()["decision"]["cleanup_execution_approved_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_approval.json()["decision"]["cleanup_application_allowed_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_approval.json()["decision"]["cleanup_executed_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_approval.json()["decision"]["can_execute_cleanup_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_approval.json()["decision"]["writes_learning_samples_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_approval.json()["decision"]["training_started_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_approvals.json()[0]["approval"]["approved_by"] == "api-test"
    assert cleanup_execution_controlled_apply_execution_plan_execution_preflight.json()["preflight"]["can_execute_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_preflight.json()["preflight"]["contains_sql"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_preflight.json()["preflight"]["record_bodies_included"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_preflight.json()["decision"]["controlled_cleanup_apply_execution_plan_execution_preflight_recorded"] is True
    assert cleanup_execution_controlled_apply_execution_plan_execution_preflight.json()["decision"]["cleanup_execution_approved_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_preflight.json()["decision"]["cleanup_application_allowed_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_preflight.json()["decision"]["cleanup_executed_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_preflight.json()["decision"]["can_execute_cleanup_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_preflight.json()["decision"]["writes_learning_samples_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_preflight.json()["decision"]["training_started_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_preflights.json()[0]["request"]["requested_by"] == "api-test"
    assert cleanup_execution_controlled_apply_execution_plan_execution_dry_run.json()["dry_run"]["can_execute_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_dry_run.json()["dry_run"]["contains_sql"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_dry_run.json()["dry_run"]["record_bodies_included"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_dry_run.json()["decision"]["controlled_cleanup_apply_execution_plan_execution_dry_run_recorded"] is True
    assert cleanup_execution_controlled_apply_execution_plan_execution_dry_run.json()["decision"]["cleanup_execution_approved_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_dry_run.json()["decision"]["cleanup_application_allowed_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_dry_run.json()["decision"]["cleanup_executed_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_dry_run.json()["decision"]["can_execute_cleanup_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_dry_run.json()["decision"]["writes_learning_samples_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_dry_run.json()["decision"]["training_started_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_dry_runs.json()[0]["request"]["simulated_by"] == "api-test"
    assert cleanup_execution_controlled_apply_execution_plan_execution_dry_run_review.json()["dry_run_summary"]["can_execute_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_dry_run_review.json()["dry_run_summary"]["contains_sql"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_dry_run_review.json()["dry_run_summary"]["record_bodies_included"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_dry_run_review.json()["decision"]["controlled_cleanup_apply_execution_plan_execution_dry_run_review_recorded"] is True
    assert cleanup_execution_controlled_apply_execution_plan_execution_dry_run_review.json()["decision"]["cleanup_execution_approved_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_dry_run_review.json()["decision"]["cleanup_application_allowed_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_dry_run_review.json()["decision"]["cleanup_executed_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_dry_run_review.json()["decision"]["can_execute_cleanup_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_dry_run_review.json()["decision"]["writes_learning_samples_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_dry_run_review.json()["decision"]["training_started_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_dry_run_reviews.json()[0]["review"]["reviewed_by"] == "api-test"
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_approval.json()["approval_scope"]["can_execute_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_approval.json()["approval_scope"]["contains_sql"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_approval.json()["approval_scope"]["record_bodies_included"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_approval.json()["decision"]["controlled_cleanup_apply_execution_plan_execution_final_approval_recorded"] is True
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_approval.json()["decision"]["cleanup_execution_approved_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_approval.json()["decision"]["cleanup_application_allowed_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_approval.json()["decision"]["cleanup_executed_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_approval.json()["decision"]["can_execute_cleanup_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_approval.json()["decision"]["writes_learning_samples_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_approval.json()["decision"]["training_started_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_approvals.json()[0]["approval"]["approved_by"] == "api-test"
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_preflight.json()["preflight"]["can_execute_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_preflight.json()["preflight"]["contains_sql"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_preflight.json()["preflight"]["record_bodies_included"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_preflight.json()["decision"]["controlled_cleanup_apply_execution_plan_execution_final_preflight_recorded"] is True
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_preflight.json()["decision"]["cleanup_execution_approved_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_preflight.json()["decision"]["cleanup_application_allowed_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_preflight.json()["decision"]["cleanup_executed_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_preflight.json()["decision"]["can_execute_cleanup_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_preflight.json()["decision"]["writes_learning_samples_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_preflight.json()["decision"]["training_started_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_preflights.json()[0]["request"]["requested_by"] == "api-test"
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_dry_run.json()["dry_run"]["can_execute_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_dry_run.json()["dry_run"]["contains_sql"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_dry_run.json()["dry_run"]["record_bodies_included"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_dry_run.json()["decision"]["controlled_cleanup_apply_execution_plan_execution_final_dry_run_recorded"] is True
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_dry_run.json()["decision"]["cleanup_execution_approved_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_dry_run.json()["decision"]["cleanup_application_allowed_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_dry_run.json()["decision"]["cleanup_executed_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_dry_run.json()["decision"]["can_execute_cleanup_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_dry_run.json()["decision"]["writes_learning_samples_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_dry_run.json()["decision"]["training_started_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_dry_runs.json()[0]["request"]["simulated_by"] == "api-test"
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_dry_run_review.json()["dry_run_summary"]["can_execute_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_dry_run_review.json()["dry_run_summary"]["contains_sql"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_dry_run_review.json()["dry_run_summary"]["record_bodies_included"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_dry_run_review.json()["decision"]["controlled_cleanup_apply_execution_plan_execution_final_dry_run_review_recorded"] is True
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_dry_run_review.json()["decision"][
        "controlled_cleanup_apply_execution_plan_execution_final_dry_run_review_accepted"
    ] is (
        cleanup_execution_controlled_apply_execution_plan_execution_final_dry_run_review.json()["status"]
        == "controlled_cleanup_apply_execution_plan_execution_final_dry_run_review_accepted"
    )
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_dry_run_review.json()["decision"]["cleanup_execution_approved_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_dry_run_review.json()["decision"]["cleanup_application_allowed_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_dry_run_review.json()["decision"]["cleanup_executed_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_dry_run_review.json()["decision"]["can_execute_cleanup_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_dry_run_review.json()["decision"]["writes_learning_samples_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_dry_run_review.json()["decision"]["training_started_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_dry_run_reviews.json()[0]["review"]["reviewed_by"] == "api-test"
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_execution_approval.json()["approval_scope"]["can_execute_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_execution_approval.json()["approval_scope"]["contains_sql"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_execution_approval.json()["approval_scope"]["record_bodies_included"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_execution_approval.json()["decision"]["controlled_cleanup_apply_execution_plan_execution_final_execution_approval_recorded"] is True
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_execution_approval.json()["decision"][
        "controlled_cleanup_apply_execution_plan_execution_final_execution_approval_accepted"
    ] is (
        cleanup_execution_controlled_apply_execution_plan_execution_final_execution_approval.json()["status"]
        == "controlled_cleanup_apply_execution_plan_execution_final_execution_approval_accepted"
    )
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_execution_approval.json()["decision"]["cleanup_execution_approved_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_execution_approval.json()["decision"]["cleanup_application_allowed_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_execution_approval.json()["decision"]["cleanup_executed_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_execution_approval.json()["decision"]["can_execute_cleanup_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_execution_approval.json()["decision"]["writes_learning_samples_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_execution_approval.json()["decision"]["training_started_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_execution_approvals.json()[0]["approval"]["approved_by"] == "api-test"
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_execution_preflight.json()["preflight"]["can_execute_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_execution_preflight.json()["preflight"]["contains_sql"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_execution_preflight.json()["preflight"]["record_bodies_included"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_execution_preflight.json()["decision"][
        "controlled_cleanup_apply_execution_plan_execution_final_execution_preflight_recorded"
    ] is True
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_execution_preflight.json()["decision"][
        "controlled_cleanup_apply_execution_plan_execution_final_execution_preflight_ready_for_dry_run"
    ] is (
        cleanup_execution_controlled_apply_execution_plan_execution_final_execution_preflight.json()["status"]
        == "controlled_cleanup_apply_execution_plan_execution_final_execution_preflight_ready_for_dry_run"
    )
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_execution_preflight.json()["decision"]["cleanup_execution_approved_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_execution_preflight.json()["decision"]["cleanup_application_allowed_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_execution_preflight.json()["decision"]["cleanup_executed_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_execution_preflight.json()["decision"]["can_execute_cleanup_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_execution_preflight.json()["decision"]["writes_learning_samples_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_execution_preflight.json()["decision"]["training_started_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_execution_preflights.json()[0]["request"]["requested_by"] == "api-test"
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_execution_dry_run.json()["dry_run"]["can_execute_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_execution_dry_run.json()["dry_run"]["contains_sql"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_execution_dry_run.json()["dry_run"]["record_bodies_included"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_execution_dry_run.json()["decision"][
        "controlled_cleanup_apply_execution_plan_execution_final_execution_dry_run_recorded"
    ] is True
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_execution_dry_run.json()["decision"][
        "controlled_cleanup_apply_execution_plan_execution_final_execution_dry_run_ready_for_review"
    ] is (
        cleanup_execution_controlled_apply_execution_plan_execution_final_execution_dry_run.json()["status"]
        == "controlled_cleanup_apply_execution_plan_execution_final_execution_dry_run_ready_for_review"
    )
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_execution_dry_run.json()["decision"]["cleanup_execution_approved_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_execution_dry_run.json()["decision"]["cleanup_application_allowed_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_execution_dry_run.json()["decision"]["cleanup_executed_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_execution_dry_run.json()["decision"]["can_execute_cleanup_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_execution_dry_run.json()["decision"]["writes_learning_samples_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_execution_dry_run.json()["decision"]["training_started_now"] is False
    assert cleanup_execution_controlled_apply_execution_plan_execution_final_execution_dry_runs.json()[0]["request"]["simulated_by"] == "api-test"
