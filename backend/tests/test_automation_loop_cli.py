import importlib.util
from pathlib import Path


def load_automation_loop_module():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "automation_loop.py"
    spec = importlib.util.spec_from_file_location("automation_loop", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_summarize_strategy_training_plan_keeps_safety_boundaries():
    automation_loop = load_automation_loop_module()
    packet = {
        "status": "ready",
        "learning_readiness": "ready_for_supervised_dry_run_learning",
        "confidence_calibration": {"score": 75.0, "tier": "backtest_ready_simulation_needed"},
        "promotion_gate": {
            "target_validation_return_pct": 20.0,
            "stable_candidate_validation_return_pct": 203.4,
            "stable_candidate_validation_win_rate": 0.8,
            "passed_20pct_review_gate": True,
            "human_confirm_readiness": {
                "status": "not_ready_for_human_confirm",
                "missing_requirements": ["supervised_dry_run_samples", "supervised_readbacks"],
                "checks": [
                    {"name": "validation_return_above_20pct", "passed": True},
                    {"name": "supervised_dry_run_samples", "passed": False},
                ],
            }
        },
        "simulation_training_evidence": {
            "dry_run_count": 0,
            "readback_count": 0,
            "unique_symbol_count": 0,
            "outcome_review": {
                "evaluated_session_count": 0,
                "win_rate_5d": None,
                "average_return_pct_5d": None,
                "average_max_drawdown_pct": None,
            },
        },
        "candidate_shadow_outcome_review": {
            "schema_version": "strategy_candidate_shadow_outcome_review.v1",
            "status": "ready",
            "evaluated_count": 1,
            "win_rate_5d": 1.0,
            "average_return_pct_5d": 8.4,
            "average_max_drawdown_pct": -1.1,
            "counts_toward_human_confirm": False,
            "allowed_effect": "historical_shadow_review_only",
        },
        "strategy_scoring_matrix": {
            "status": "ready",
            "method": "dataset1_experience_priors_plus_dataset2_rule_memory_plus_execution_readiness",
            "top_symbol": "SH603120",
            "top_candidates": [
                {
                    "rank": 1,
                    "symbol": "SH603120",
                    "score": 83.0,
                    "tier": "high_priority_supervised_dry_run",
                    "action_label": "SIM_BUY_CANDIDATE",
                    "components": {
                        "phase_score": {"score": 20},
                        "volume_price_score": {"score": 20},
                        "entry_timing_score": {"score": 13},
                        "exit_discipline_score": {"score": 15},
                        "execution_readiness_score": {"score": 15},
                        "risk_penalty": {"score": 0},
                    },
                    "outcome_evidence": {
                        "candidate_strategy_win_rate": 0.8,
                        "candidate_strategy_average_return_pct": 11.2,
                        "supports_20pct_goal": True,
                    },
                    "recommended_learning_action": "Prioritize for supervised dry-run.",
                }
            ],
            "target_alignment": {
                "offline_20pct_gate_passed": True,
                "stable_validation_return_pct": 203.4,
                "stable_validation_win_rate": 0.8,
                "top_candidate_supports_20pct_goal": True,
                "top_candidate_strategy_win_rate": 0.8,
                "top_candidate_strategy_average_return_pct": 11.2,
            },
            "permission_policy": {
                "may_change_strategy_weight_now": False,
                "may_submit_order": False,
                "may_enable_screen_click": False,
                "allowed_effect": "candidate_learning_priority_only",
            },
            "live_trading_enabled": False,
        },
        "simulation_training_plan": {
            "status": "needs_supervised_samples",
            "remaining_requirements": {"dry_run_samples": 20, "readbacks": 20},
            "candidate_queue": [
                {
                    "rank": 1,
                    "symbol": "SH603120",
                    "confidence_tier": "high_confidence_dry_run_review",
                    "recommended_mode": "dry_run_screen_candidate",
                    "target_next_dry_run_samples": 8,
                    "minimum_readbacks_required": 8,
                    "sample_mode": "detect_only_then_dry_run_screen",
                    "max_first_probe_quantity": 100,
                    "max_first_probe_cash_pct": 0.03,
                    "stop_conditions": ["real_account_or_broker_terms_detected"],
                    "allowed_effect": "sample_collection_instruction_only",
                }
            ],
            "warnings": [],
            "next_action": "Collect supervised dry-run/readback samples.",
        },
        "permission_policy": {
            "may_submit_order": False,
            "may_enable_screen_click": False,
            "may_write_rules_yaml": False,
            "may_write_model_artifact": False,
            "may_open_real_money_human_confirm": False,
            "allowed_effect": "codex_supervision_and_strategy_learning_only",
        },
        "live_trading_enabled": False,
    }

    summary = automation_loop.summarize_strategy_training_plan(packet)

    assert summary["schema_version"] == "strategy_training_plan_supervisor_summary.v1"
    assert summary["confidence_score"] == 75.0
    assert summary["confidence_tier"] == "backtest_ready_simulation_needed"
    assert summary["training_plan_status"] == "needs_supervised_samples"
    assert summary["remaining_requirements"]["dry_run_samples"] == 20
    assert summary["next_batch_target_dry_run_samples"] == 8
    assert summary["candidate_queue"][0]["symbol"] == "SH603120"
    assert summary["candidate_queue"][0]["allowed_effect"] == "sample_collection_instruction_only"
    scoring_summary = summary["strategy_scoring_matrix_summary"]
    assert scoring_summary["schema_version"] == "strategy_scoring_matrix_supervisor_summary.v1"
    assert scoring_summary["top_symbol"] == "SH603120"
    assert scoring_summary["top_candidates"][0]["score"] == 83.0
    assert scoring_summary["top_candidates"][0]["risk_penalty"] == 0
    assert scoring_summary["top_candidates"][0]["candidate_strategy_win_rate"] == 0.8
    assert scoring_summary["top_candidates"][0]["candidate_strategy_average_return_pct"] == 11.2
    assert scoring_summary["top_candidates"][0]["supports_20pct_goal"] is True
    assert scoring_summary["target_alignment"]["top_candidate_supports_20pct_goal"] is True
    assert scoring_summary["permission_policy"]["may_change_strategy_weight_now"] is False
    assert scoring_summary["permission_policy"]["may_submit_order"] is False
    target_progress = summary["target_progress"]
    assert target_progress["schema_version"] == "strategy_target_progress.v1"
    assert target_progress["offline_20pct_return_gate_passed"] is True
    assert target_progress["top_scored_symbol"] == "SH603120"
    assert target_progress["top_scored_candidate_supports_20pct_goal"] is True
    assert target_progress["top_scored_candidate_strategy_win_rate"] == 0.8
    assert target_progress["top_scored_candidate_strategy_average_return_pct"] == 11.2
    assert target_progress["shadow_candidate_evaluated_count"] == 1
    assert target_progress["shadow_candidate_win_rate_5d"] == 1.0
    assert target_progress["shadow_candidate_average_return_pct_5d"] == 8.4
    assert target_progress["shadow_candidate_average_drawdown_pct"] == -1.1
    assert target_progress["shadow_candidate_counts_toward_human_confirm"] is False
    assert target_progress["supervised_dry_run_count"] == 0
    assert target_progress["ready_for_human_confirm"] is False
    assert target_progress["may_open_real_money_human_confirm"] is False
    assert "supervised_dry_run_samples" in target_progress["failed_human_confirm_checks"]
    assert summary["permission_policy"]["may_submit_order"] is False
    assert summary["permission_policy"]["may_enable_screen_click"] is False
    assert summary["permission_policy"]["may_write_rules_yaml"] is False
    assert summary["permission_policy"]["may_write_model_artifact"] is False
    assert summary["permission_policy"]["may_open_real_money_human_confirm"] is False
    assert summary["allowed_effect"] == "supervisor_summary_only"
    assert summary["review_only"] is True
    assert summary["simulation_only"] is True
    assert summary["live_trading_enabled"] is False


def test_summarize_supervised_sample_gate_blocks_unverified_window():
    automation_loop = load_automation_loop_module()
    training_summary = {
        "candidate_queue": [
            {
                "symbol": "SH603120",
                "target_next_dry_run_samples": 8,
                "minimum_readbacks_required": 8,
                "sample_mode": "detect_only_then_dry_run_screen",
            }
        ],
        "remaining_requirements": {"dry_run_samples": 20, "readbacks": 20},
        "permission_policy": {
            "may_submit_order": False,
            "may_enable_screen_click": False,
        },
        "live_trading_enabled": False,
    }

    gate = automation_loop.summarize_supervised_sample_gate(
        {"status": "blocked", "blocked_reasons": ["window_not_found"]},
        {"status": "unverified"},
        training_summary,
    )

    assert gate["schema_version"] == "sim_cockpit_supervised_sample_gate.v1"
    assert gate["status"] == "blocked"
    assert "window_detection_not_verified" in gate["blocked_reasons"]
    assert "sim_cockpit_status_not_verified" in gate["blocked_reasons"]
    assert gate["can_collect_dry_run_samples"] is False
    assert gate["can_submit_order"] is False
    assert gate["can_enable_screen_click"] is False


def test_summarize_supervised_sample_gate_allows_dry_run_collection_only():
    automation_loop = load_automation_loop_module()
    training_summary = {
        "candidate_queue": [
            {
                "symbol": "SH603120",
                "target_next_dry_run_samples": 8,
                "minimum_readbacks_required": 8,
                "sample_mode": "detect_only_then_dry_run_screen",
            }
        ],
        "remaining_requirements": {"dry_run_samples": 20, "readbacks": 20},
        "permission_policy": {
            "may_submit_order": False,
            "may_enable_screen_click": False,
        },
        "live_trading_enabled": False,
    }

    gate = automation_loop.summarize_supervised_sample_gate(
        {"status": "verified"},
        {"status": "verified"},
        training_summary,
    )

    assert gate["status"] == "ready_for_supervised_dry_run_collection"
    assert gate["blocked_reasons"] == []
    assert gate["can_collect_dry_run_samples"] is True
    assert gate["can_submit_order"] is False
    assert gate["can_enable_screen_click"] is False
    assert gate["next_sample_symbols"][0]["symbol"] == "SH603120"
    assert gate["allowed_effect"] == "supervised_sample_gate_only"


def test_supervised_next_action_uses_training_queue_when_gate_ready():
    automation_loop = load_automation_loop_module()

    message = automation_loop._supervised_next_action(
        {"status": "verified"},
        {"status": "verified"},
        {"training_allowed": True},
        {"status": "completed"},
        {"top_candidates": [{"symbol": "SH603120"}]},
        {"training_plan_status": "needs_supervised_samples"},
        {
            "status": "ready_for_supervised_dry_run_collection",
            "next_sample_symbols": [
                {"symbol": "SH603120", "target_next_dry_run_samples": 8},
                {"symbol": "SH603330", "target_next_dry_run_samples": 6},
            ],
        },
    )

    assert "SH603120:8" in message
    assert "screen-click permission disabled" in message


def test_sim_cockpit_current_safety_summary_separates_historical_click_from_current_gate():
    automation_loop = load_automation_loop_module()
    cockpit_status = {
        "status": "blocked",
        "real_screen_click_executed": True,
        "live_trading_enabled": False,
        "latest_verification": {
            "id": 37,
            "status": "blocked",
            "blocked_reasons": ["missing_window_or_page_text"],
        },
        "latest_actions": [
            {
                "id": 6,
                "status": "executed",
                "symbol": "SZ000001",
                "signal_source": "historical_fixture",
                "execution": {"real_screen_click_executed": True},
            }
        ],
    }
    sample_gate = {
        "status": "blocked",
        "can_collect_dry_run_samples": False,
        "blocked_reasons": ["window_detection_not_verified"],
    }

    summary = automation_loop.summarize_sim_cockpit_current_safety(cockpit_status, sample_gate)

    assert summary["schema_version"] == "sim_cockpit_current_safety_summary.v1"
    assert summary["current_status"] == "blocked"
    assert summary["current_window_verified"] is False
    assert summary["current_dry_run_collection_ready"] is False
    assert summary["current_order_submission_allowed"] is False
    assert summary["current_screen_click_allowed"] is False
    assert summary["historical_latest_action_real_screen_click_executed"] is True
    assert summary["historical_latest_action"]["id"] == 6
    assert "window_detection_not_verified" in summary["blocked_reasons"]
    assert summary["allowed_effect"] == "current_safety_summary_only"


def test_sim_cockpit_window_readiness_checklist_blocks_missing_window():
    automation_loop = load_automation_loop_module()
    detection = {
        "status": "needs_simulation_window",
        "blocked_reasons": ["tonghuashun_window_not_found"],
        "verification": {
            "status": "blocked",
            "blocked_reasons": [
                "missing_tonghuashun_process_marker",
                "missing_window_or_page_text",
            ],
            "raw_payload": {"window": {"coordinate_anchors": {}}},
        },
    }
    cockpit_status = {
        "status": "blocked",
        "live_trading_enabled": False,
        "latest_verification": {
            "status": "blocked",
            "blocked_reasons": ["missing_window_or_page_text"],
        },
    }
    sample_gate = {
        "status": "blocked",
        "blocked_reasons": [
            "window_detection_not_verified",
            "sim_cockpit_status_not_verified",
        ],
    }

    checklist = automation_loop.summarize_sim_cockpit_window_readiness(
        detection,
        cockpit_status,
        sample_gate,
    )

    assert checklist["schema_version"] == "sim_cockpit_window_readiness_checklist.v1"
    assert checklist["status"] == "blocked"
    assert checklist["blocking_stage"] == "window_detection"
    assert "tonghuashun_window_not_found" in checklist["blocked_reasons"]
    assert "missing_tonghuashun_process_marker" in checklist["blocked_reasons"]
    assert "Open Tonghuashun" in checklist["safe_next_action"]
    assert checklist["can_collect_dry_run_samples"] is False
    assert checklist["can_submit_order"] is False
    assert checklist["can_enable_screen_click"] is False
    assert checklist["allowed_effect"] == "window_readiness_guidance_only"
    assert checklist["live_trading_enabled"] is False
    statuses = {item["name"]: item["status"] for item in checklist["operator_checklist"]}
    assert statuses["open_tonghuashun_client"] == "blocked"
    assert statuses["sample_gate_ready"] == "blocked"


def test_sim_cockpit_window_readiness_checklist_allows_dry_run_collection_only():
    automation_loop = load_automation_loop_module()
    detection = {
        "status": "verified",
        "verification": {
            "status": "verified",
            "simulation_mode_detected": True,
            "process_terms": ["xiadan"],
            "raw_payload": {
                "coordinate_anchors": {
                    "buy_tab": {"x": 10, "y": 10},
                    "symbol_input": {"x": 20, "y": 20},
                }
            },
        },
    }
    cockpit_status = {
        "status": "verified",
        "live_trading_enabled": False,
        "latest_verification": {"status": "verified", "process_terms": ["xiadan"]},
    }
    sample_gate = {
        "status": "ready_for_supervised_dry_run_collection",
        "blocked_reasons": [],
    }

    checklist = automation_loop.summarize_sim_cockpit_window_readiness(
        detection,
        cockpit_status,
        sample_gate,
    )

    assert checklist["status"] == "ready_for_supervised_dry_run_collection"
    assert checklist["blocking_stage"] == "ready"
    assert checklist["blocked_reasons"] == []
    assert checklist["can_collect_dry_run_samples"] is True
    assert checklist["can_submit_order"] is False
    assert checklist["can_enable_screen_click"] is False
    assert checklist["anchor_count"] == 2
    assert "dry-run/readback samples only" in checklist["safe_next_action"]
    statuses = {item["name"]: item["status"] for item in checklist["operator_checklist"]}
    assert all(status == "passed" for status in statuses.values())
