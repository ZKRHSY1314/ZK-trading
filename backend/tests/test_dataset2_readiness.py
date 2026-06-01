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

    assert data["stage"] == "V5.6-P8"
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

    assert data["stage"] == "V5.6-P8"
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

    assert data["stage"] == "V5.6-P8"
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

    assert imported["stage"] == "V5.6-P8"
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

    assert quality["stage"] == "V5.6-P8"
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

    assert plan["stage"] == "V5.6-P8"
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

    assert approval["stage"] == "V5.6-P8"
    assert approval["status"] == "fix_plan_approved_for_preflight"
    assert approval["decision"]["approval_allows_fix_application_now"] is False
    assert approval["decision"]["can_generate_preflight_now"] is True
    assert approval["decision"]["writes_learning_samples_now"] is False
    assert preflight["stage"] == "V5.6-P8"
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

    assert spec["stage"] == "V5.6-P8"
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

    assert dry_run["stage"] == "V5.6-P8"
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
