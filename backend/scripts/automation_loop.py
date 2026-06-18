import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path


DEFAULT_API_BASE = "http://127.0.0.1:8000"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIR = PROJECT_ROOT / "frontend"
CYCLE_LIMIT = 8
CYCLE_MONITOR_LIMIT = 5
CYCLE_REVIEW_SYMBOL = "SZ002081"


def request_json(method: str, url: str) -> dict:
    request = urllib.request.Request(url, method=method)
    with urllib.request.urlopen(request, timeout=180) as response:
        return json.loads(response.read().decode("utf-8"))


def request_json_payload(method: str, url: str, payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method=method,
    )
    with urllib.request.urlopen(request, timeout=180) as response:
        return json.loads(response.read().decode("utf-8"))


def ensure_simulation_health(api_base: str) -> dict:
    health = request_json("GET", f"{api_base}/health")
    if health.get("live_trading_enabled") is not False:
        raise RuntimeError(f"Live trading safety check failed: {health}")
    return health


def summarize_simulation_review_plan(plan: dict) -> dict:
    candidates = list(plan.get("candidates") or [])
    tier_counts: dict[str, int] = {}
    top_candidates = []
    for item in candidates:
        quality = item.get("evidence_quality") or {}
        tier = str(quality.get("confidence_tier") or "unscored")
        tier_counts[tier] = tier_counts.get(tier, 0) + 1
    for item in candidates[:5]:
        quality = item.get("evidence_quality") or {}
        top_candidates.append(
            {
                "symbol": item.get("symbol"),
                "recommended_mode": item.get("recommended_mode"),
                "confidence_tier": quality.get("confidence_tier"),
                "confidence_score": quality.get("confidence_score"),
                "priority_score": item.get("priority_score"),
                "confidence_adjusted_priority_score": item.get("confidence_adjusted_priority_score"),
                "blockers": item.get("blockers") or [],
                "caution_flags": item.get("caution_flags") or [],
                "max_initial_cash": (item.get("position_plan") or {}).get("max_initial_cash"),
            }
        )
    permission = plan.get("permission_policy") or {}
    return {
        "schema_version": "simulation_review_plan_supervisor_summary.v1",
        "status": plan.get("status"),
        "candidate_count": plan.get("candidate_count", len(candidates)),
        "ready_dry_run_candidate_count": plan.get("ready_dry_run_candidate_count", 0),
        "confidence_tier_counts": tier_counts,
        "top_candidates": top_candidates,
        "may_submit_order": permission.get("may_submit_order") is True,
        "may_enable_screen_click": permission.get("may_enable_screen_click") is True,
        "review_only": plan.get("review_only", True),
        "simulation_only": plan.get("simulation_only", True),
        "live_trading_enabled": plan.get("live_trading_enabled"),
    }


def summarize_strategy_training_plan(packet: dict) -> dict:
    plan = packet.get("simulation_training_plan") or {}
    confidence = packet.get("confidence_calibration") or {}
    scoring_matrix = packet.get("strategy_scoring_matrix") or {}
    promotion_gate = packet.get("promotion_gate") or {}
    human_confirm = promotion_gate.get("human_confirm_readiness") or {}
    permission = packet.get("permission_policy") or {}
    queue = list(plan.get("candidate_queue") or [])
    compact_queue = []
    for item in queue[:5]:
        compact_queue.append(
            {
                "rank": item.get("rank"),
                "symbol": item.get("symbol"),
                "confidence_tier": item.get("confidence_tier"),
                "recommended_mode": item.get("recommended_mode"),
                "target_next_dry_run_samples": item.get("target_next_dry_run_samples", 0),
                "minimum_readbacks_required": item.get("minimum_readbacks_required", 0),
                "sample_mode": item.get("sample_mode"),
                "max_first_probe_quantity": item.get("max_first_probe_quantity"),
                "max_first_probe_cash_pct": item.get("max_first_probe_cash_pct"),
                "stop_conditions": (item.get("stop_conditions") or [])[:5],
                "allowed_effect": item.get("allowed_effect"),
            }
        )
    next_batch_target = sum(int(item.get("target_next_dry_run_samples") or 0) for item in queue)
    scoring_summary = summarize_strategy_scoring_matrix(scoring_matrix)
    target_progress = summarize_strategy_target_progress(packet, scoring_summary)
    return {
        "schema_version": "strategy_training_plan_supervisor_summary.v1",
        "packet_status": packet.get("status"),
        "learning_readiness": packet.get("learning_readiness"),
        "confidence_score": confidence.get("score"),
        "confidence_tier": confidence.get("tier"),
        "human_confirm_status": human_confirm.get("status"),
        "missing_requirements": human_confirm.get("missing_requirements") or [],
        "training_plan_status": plan.get("status"),
        "remaining_requirements": plan.get("remaining_requirements") or {},
        "candidate_queue_count": len(queue),
        "next_batch_target_dry_run_samples": next_batch_target,
        "candidate_queue": compact_queue,
        "strategy_scoring_matrix_summary": scoring_summary,
        "target_progress": target_progress,
        "warnings": plan.get("warnings") or [],
        "permission_policy": {
            "may_submit_order": permission.get("may_submit_order") is True,
            "may_enable_screen_click": permission.get("may_enable_screen_click") is True,
            "may_write_rules_yaml": permission.get("may_write_rules_yaml") is True,
            "may_write_model_artifact": permission.get("may_write_model_artifact") is True,
            "may_open_real_money_human_confirm": permission.get("may_open_real_money_human_confirm") is True,
            "allowed_effect": permission.get("allowed_effect"),
        },
        "next_action": plan.get("next_action") or packet.get("next_action"),
        "allowed_effect": "supervisor_summary_only",
        "review_only": True,
        "simulation_only": True,
        "live_trading_enabled": packet.get("live_trading_enabled"),
    }


def summarize_strategy_scoring_matrix(matrix: dict) -> dict:
    rows = list(matrix.get("top_candidates") or [])
    compact_rows = []
    for row in rows[:5]:
        components = row.get("components") or {}
        outcome = row.get("outcome_evidence") or {}
        compact_rows.append(
            {
                "rank": row.get("rank"),
                "symbol": row.get("symbol"),
                "score": row.get("score"),
                "tier": row.get("tier"),
                "action_label": row.get("action_label"),
                "candidate_strategy_win_rate": outcome.get("candidate_strategy_win_rate"),
                "candidate_strategy_average_return_pct": outcome.get("candidate_strategy_average_return_pct"),
                "supports_20pct_goal": outcome.get("supports_20pct_goal") is True,
                "phase_score": (components.get("phase_score") or {}).get("score"),
                "volume_price_score": (components.get("volume_price_score") or {}).get("score"),
                "entry_timing_score": (components.get("entry_timing_score") or {}).get("score"),
                "exit_discipline_score": (components.get("exit_discipline_score") or {}).get("score"),
                "execution_readiness_score": (components.get("execution_readiness_score") or {}).get("score"),
                "risk_penalty": (components.get("risk_penalty") or {}).get("score"),
                "recommended_learning_action": row.get("recommended_learning_action"),
            }
        )
    return {
        "schema_version": "strategy_scoring_matrix_supervisor_summary.v1",
        "status": matrix.get("status", "missing"),
        "method": matrix.get("method"),
        "top_symbol": matrix.get("top_symbol"),
        "top_candidate_count": len(rows),
        "top_candidates": compact_rows,
        "target_alignment": matrix.get("target_alignment") or {},
        "permission_policy": {
            "may_change_strategy_weight_now": (matrix.get("permission_policy") or {}).get("may_change_strategy_weight_now") is True,
            "may_submit_order": (matrix.get("permission_policy") or {}).get("may_submit_order") is True,
            "may_enable_screen_click": (matrix.get("permission_policy") or {}).get("may_enable_screen_click") is True,
            "allowed_effect": (matrix.get("permission_policy") or {}).get("allowed_effect"),
        },
        "allowed_effect": "scoring_matrix_summary_only",
        "review_only": True,
        "simulation_only": True,
        "live_trading_enabled": matrix.get("live_trading_enabled"),
    }


def summarize_strategy_target_progress(packet: dict, scoring_summary: dict) -> dict:
    promotion_gate = packet.get("promotion_gate") or {}
    human_confirm = promotion_gate.get("human_confirm_readiness") or {}
    simulation_evidence = packet.get("simulation_training_evidence") or {}
    outcome_review = simulation_evidence.get("outcome_review") or {}
    shadow_review = packet.get("candidate_shadow_outcome_review") or {}
    stable_return = promotion_gate.get("stable_candidate_validation_return_pct")
    stable_win_rate = promotion_gate.get("stable_candidate_validation_win_rate")
    passed_offline_return = bool(promotion_gate.get("passed_20pct_review_gate"))
    checks = human_confirm.get("checks") or []
    failed_checks = [item.get("name") for item in checks if item.get("passed") is not True]
    ready_for_human_confirm = human_confirm.get("status") == "ready_for_human_confirm_review"
    return {
        "schema_version": "strategy_target_progress.v1",
        "target_validation_return_pct": promotion_gate.get("target_validation_return_pct", 20.0),
        "stable_candidate_validation_return_pct": stable_return,
        "stable_candidate_validation_win_rate": stable_win_rate,
        "offline_20pct_return_gate_passed": passed_offline_return,
        "supervised_dry_run_count": simulation_evidence.get("dry_run_count", 0),
        "supervised_readback_count": simulation_evidence.get("readback_count", 0),
        "unique_symbol_count": simulation_evidence.get("unique_symbol_count", 0),
        "evaluated_session_count": outcome_review.get("evaluated_session_count", 0),
        "simulated_win_rate_5d": outcome_review.get("win_rate_5d"),
        "simulated_average_return_pct_5d": outcome_review.get("average_return_pct_5d"),
        "simulated_average_drawdown_pct": outcome_review.get("average_max_drawdown_pct"),
        "shadow_candidate_evaluated_count": shadow_review.get("evaluated_count", 0),
        "shadow_candidate_win_rate_5d": shadow_review.get("win_rate_5d"),
        "shadow_candidate_average_return_pct_5d": shadow_review.get("average_return_pct_5d"),
        "shadow_candidate_average_drawdown_pct": shadow_review.get("average_max_drawdown_pct"),
        "shadow_candidate_counts_toward_human_confirm": (
            shadow_review.get("counts_toward_human_confirm") is True
        ),
        "top_scored_symbol": scoring_summary.get("top_symbol"),
        "top_scored_candidate_supports_20pct_goal": (
            scoring_summary.get("target_alignment") or {}
        ).get("top_candidate_supports_20pct_goal") is True,
        "top_scored_candidate_strategy_win_rate": (
            scoring_summary.get("target_alignment") or {}
        ).get("top_candidate_strategy_win_rate"),
        "top_scored_candidate_strategy_average_return_pct": (
            scoring_summary.get("target_alignment") or {}
        ).get("top_candidate_strategy_average_return_pct"),
        "failed_human_confirm_checks": failed_checks,
        "human_confirm_status": human_confirm.get("status"),
        "ready_for_human_confirm": ready_for_human_confirm,
        "next_evidence_gap": (
            "collect_supervised_dry_run_readback_outcomes"
            if not ready_for_human_confirm
            else "manual_review_required_before_any_real_money_permission"
        ),
        "may_open_real_money_human_confirm": False,
        "allowed_effect": "progress_reporting_only",
        "review_only": True,
        "simulation_only": True,
        "live_trading_enabled": packet.get("live_trading_enabled"),
    }


def summarize_supervised_sample_gate(
    detection: dict,
    cockpit_status: dict,
    training_plan_summary: dict,
) -> dict:
    queue = [
        item
        for item in (training_plan_summary.get("candidate_queue") or [])
        if int(item.get("target_next_dry_run_samples") or 0) > 0
    ]
    blocked_reasons: list[str] = []
    if detection.get("status") != "verified":
        blocked_reasons.append("window_detection_not_verified")
    if cockpit_status.get("status") != "verified":
        blocked_reasons.append("sim_cockpit_status_not_verified")
    if not queue:
        blocked_reasons.append("no_training_plan_candidate_queue")
    permission = training_plan_summary.get("permission_policy") or {}
    if permission.get("may_submit_order") is True:
        blocked_reasons.append("unexpected_order_permission_true")
    if permission.get("may_enable_screen_click") is True:
        blocked_reasons.append("unexpected_screen_click_permission_true")
    if training_plan_summary.get("live_trading_enabled") is not False:
        blocked_reasons.append("live_trading_not_confirmed_disabled")

    return {
        "schema_version": "sim_cockpit_supervised_sample_gate.v1",
        "status": "ready_for_supervised_dry_run_collection" if not blocked_reasons else "blocked",
        "blocked_reasons": blocked_reasons,
        "can_collect_dry_run_samples": not blocked_reasons,
        "can_submit_order": False,
        "can_enable_screen_click": False,
        "next_sample_symbols": [
            {
                "symbol": item.get("symbol"),
                "target_next_dry_run_samples": item.get("target_next_dry_run_samples"),
                "minimum_readbacks_required": item.get("minimum_readbacks_required"),
                "sample_mode": item.get("sample_mode"),
            }
            for item in queue[:3]
        ],
        "remaining_requirements": training_plan_summary.get("remaining_requirements") or {},
        "allowed_effect": "supervised_sample_gate_only",
        "review_only": True,
        "simulation_only": True,
        "live_trading_enabled": training_plan_summary.get("live_trading_enabled"),
    }


def _unique_strings(values: list[object]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value is None:
            continue
        text = str(value)
        if not text or text in seen:
            continue
        result.append(text)
        seen.add(text)
    return result


def summarize_sim_cockpit_window_readiness(
    detection: dict,
    cockpit_status: dict,
    supervised_sample_gate: dict,
) -> dict:
    verification = detection.get("verification") or {}
    latest_verification = cockpit_status.get("latest_verification") or {}
    raw_payload = verification.get("raw_payload") or {}
    raw_window = raw_payload.get("window") or {}
    anchors = raw_payload.get("coordinate_anchors") or raw_window.get("coordinate_anchors") or {}
    dangerous_terms = _unique_strings(
        list(verification.get("dangerous_terms") or [])
        + list(latest_verification.get("dangerous_terms") or [])
        + list(raw_window.get("dangerous_terms") or [])
    )
    blocked_reasons = _unique_strings(
        list(detection.get("blocked_reasons") or [])
        + list(verification.get("blocked_reasons") or [])
        + list(latest_verification.get("blocked_reasons") or [])
        + list(supervised_sample_gate.get("blocked_reasons") or [])
    )
    detection_verified = detection.get("status") == "verified"
    cockpit_verified = cockpit_status.get("status") == "verified"
    sample_ready = supervised_sample_gate.get("status") == "ready_for_supervised_dry_run_collection"
    process_marker_present = bool(
        verification.get("process_terms")
        or latest_verification.get("process_terms")
        or raw_window.get("process_terms")
        or raw_window.get("process_name")
    )
    simulation_marker_present = bool(
        detection_verified
        and (
            verification.get("simulation_mode_detected") is True
            or latest_verification.get("simulation_mode_detected") is True
            or raw_window.get("positive_terms")
        )
    )
    anchors_present = bool(anchors)

    if dangerous_terms:
        blocking_stage = "dangerous_terms"
    elif not process_marker_present or not detection_verified:
        blocking_stage = "window_detection"
    elif not cockpit_verified:
        blocking_stage = "sim_cockpit_status"
    elif not sample_ready:
        blocking_stage = "sample_gate"
    else:
        blocking_stage = "ready"

    checklist = [
        {
            "name": "open_tonghuashun_client",
            "status": "passed" if process_marker_present else "blocked",
            "required": True,
            "hint": "Open Tonghuashun and keep the simulated trading client visible.",
        },
        {
            "name": "enter_simulated_trading_window",
            "status": "passed" if detection_verified and cockpit_verified else "blocked",
            "required": True,
            "hint": "Switch to the mncg/simulated trading window, then rerun supervised cycle.",
        },
        {
            "name": "simulation_marker_present",
            "status": "passed" if simulation_marker_present else "blocked",
            "required": True,
            "hint": "The latest desktop evidence must contain current mncg/simulated-account markers.",
        },
        {
            "name": "coordinate_anchors_present",
            "status": "passed" if anchors_present else "blocked",
            "required": True,
            "hint": "Detected anchors must include the buy/sell inputs and submit controls before dry-run planning.",
        },
        {
            "name": "dangerous_terms_absent",
            "status": "blocked" if dangerous_terms else "passed",
            "required": True,
            "hint": "Real account, broker login, funds, transfer, or live entrustment terms must be absent.",
        },
        {
            "name": "sample_gate_ready",
            "status": "passed" if sample_ready else "blocked",
            "required": True,
            "hint": "Training queue, health, current window verification, and permission policy must all pass.",
        },
    ]

    if dangerous_terms:
        safe_next_action = (
            "Stop immediately and leave screen control disabled; dangerous real-trading terms were detected."
        )
    elif not process_marker_present or not detection_verified:
        safe_next_action = (
            "Open Tonghuashun and switch to the mncg simulated trading window; rerun supervised cycle before any dry-run."
        )
    elif not cockpit_verified:
        safe_next_action = (
            "Keep the simulated window visible and record verification again; do not click or submit."
        )
    elif not sample_ready:
        safe_next_action = (
            "Review the blocked sample gate and collect only the missing verification/readback evidence."
        )
    else:
        safe_next_action = (
            "Collect supervised dry-run/readback samples only; order submission and screen-click execution stay disabled."
        )

    status = "ready_for_supervised_dry_run_collection" if blocking_stage == "ready" else "blocked"
    return {
        "schema_version": "sim_cockpit_window_readiness_checklist.v1",
        "status": status,
        "blocking_stage": blocking_stage,
        "blocked_reasons": blocked_reasons,
        "operator_checklist": checklist,
        "safe_next_action": safe_next_action,
        "can_collect_dry_run_samples": status == "ready_for_supervised_dry_run_collection",
        "can_submit_order": False,
        "can_enable_screen_click": False,
        "dangerous_terms": dangerous_terms,
        "anchor_count": len(anchors),
        "allowed_effect": "window_readiness_guidance_only",
        "review_only": True,
        "simulation_only": True,
        "live_trading_enabled": cockpit_status.get("live_trading_enabled"),
    }


def summarize_sim_cockpit_current_safety(
    cockpit_status: dict,
    supervised_sample_gate: dict,
) -> dict:
    latest_actions = list(cockpit_status.get("latest_actions") or [])
    latest_action = latest_actions[0] if latest_actions else {}
    latest_execution = latest_action.get("execution") or {}
    latest_verification = cockpit_status.get("latest_verification") or {}
    historical_click_seen = bool(cockpit_status.get("real_screen_click_executed"))
    current_verified = cockpit_status.get("status") == "verified"
    sample_ready = supervised_sample_gate.get("status") == "ready_for_supervised_dry_run_collection"
    return {
        "schema_version": "sim_cockpit_current_safety_summary.v1",
        "current_status": cockpit_status.get("status"),
        "current_window_verified": current_verified,
        "current_dry_run_collection_ready": bool(
            sample_ready and supervised_sample_gate.get("can_collect_dry_run_samples") is True
        ),
        "current_order_submission_allowed": False,
        "current_screen_click_allowed": False,
        "historical_latest_action_real_screen_click_executed": historical_click_seen,
        "historical_latest_action": {
            "id": latest_action.get("id"),
            "status": latest_action.get("status"),
            "symbol": latest_action.get("symbol"),
            "signal_source": latest_action.get("signal_source"),
            "real_screen_click_executed": bool(latest_execution.get("real_screen_click_executed")),
        } if latest_action else None,
        "latest_verification": {
            "id": latest_verification.get("id"),
            "status": latest_verification.get("status"),
            "blocked_reasons": latest_verification.get("blocked_reasons") or [],
        } if latest_verification else None,
        "blocked_reasons": supervised_sample_gate.get("blocked_reasons") or [],
        "interpretation": (
            "Historical screen-click actions may exist, but current collection remains blocked until the "
            "latest simulated window verification and sample gate pass."
            if not current_verified or not sample_ready
            else "Current gate permits supervised dry-run sample collection only; order submission and screen-click execution remain disabled."
        ),
        "allowed_effect": "current_safety_summary_only",
        "review_only": True,
        "simulation_only": True,
        "live_trading_enabled": cockpit_status.get("live_trading_enabled"),
    }


def run_api_cycle(api_base: str, limit: int) -> dict:
    query = urllib.parse.urlencode({"limit": limit})
    return request_json("POST", f"{api_base}/api/automation/run-once?{query}")


def run_full_cycle(api_base: str, limit: int, monitor_limit: int, review_symbol: str) -> dict:
    effective_cycle_params = {
        "limit": CYCLE_LIMIT,
        "monitor_limit": CYCLE_MONITOR_LIMIT,
        "review_symbol": CYCLE_REVIEW_SYMBOL,
    }
    query = urllib.parse.urlencode(effective_cycle_params)
    response = request_json("POST", f"{api_base}/api/automation/cycles/run-once?{query}")
    if isinstance(response, dict):
        response["effective_params"] = effective_cycle_params
        response["effective_cycle_params"] = effective_cycle_params
    return response


def run_discovery_cycle(api_base: str, limit: int) -> dict:
    query = urllib.parse.urlencode({"limit": limit, "persist": "true"})
    return request_json("POST", f"{api_base}/api/candidates/auto-discovery?{query}")


def run_potential_cycle(api_base: str, limit: int) -> dict:
    query = urllib.parse.urlencode({"limit": limit, "persist": "true"})
    return request_json("POST", f"{api_base}/api/candidates/potential-search/run?{query}")


def run_monitor_cycle(api_base: str, limit: int) -> dict:
    query = urllib.parse.urlencode({"limit": limit})
    return request_json("POST", f"{api_base}/api/monitoring/run-once?{query}")


def run_agent_task(api_base: str, task_type: str) -> dict:
    query = urllib.parse.urlencode({"task_type": task_type})
    return request_json("POST", f"{api_base}/api/agent-control/tasks/run-now?{query}")


def run_agent_learning(api_base: str, limit: int) -> dict:
    query = urllib.parse.urlencode({"limit": limit})
    return request_json("POST", f"{api_base}/api/learning/agent-samples/from-recent?{query}")


def run_agent_outcomes(api_base: str, limit: int, horizon_days: int = 5) -> dict:
    query = urllib.parse.urlencode({"limit": limit, "horizon_days": horizon_days})
    return request_json("POST", f"{api_base}/api/learning/agent-outcomes/label-recent?{query}")


def run_signal_performance(api_base: str) -> dict:
    return request_json("POST", f"{api_base}/api/learning/calibration-proposals/generate?created_by=automation_loop")


def run_sandbox_experiments(api_base: str, limit: int) -> dict:
    query = urllib.parse.urlencode({"limit": limit, "created_by": "automation_loop"})
    return request_json("POST", f"{api_base}/api/learning/sandbox-experiments/run-approved?{query}")


def run_paper_simulation(api_base: str, limit: int) -> dict:
    """Paper simulation mode: draft policies then run already-approved ones.

    This mode NEVER auto-approves policies. Drafts are created from
    eligible sandbox experiments, and only human-approved policies
    are executed.
    """
    results: dict = {"steps": []}

    # Step 1: Draft policies from eligible experiments
    draft_query = urllib.parse.urlencode({"limit": limit, "created_by": "automation_loop"})
    draft_result = request_json(
        "POST",
        f"{api_base}/api/learning/simulation-policies/draft-from-experiments?{draft_query}",
    )
    results["steps"].append({"action": "draft_policies", "result": draft_result})

    # Step 2: Run only already-approved policies (never auto-approve)
    run_query = urllib.parse.urlencode({"limit": limit, "created_by": "automation_loop"})
    run_result = request_json(
        "POST",
        f"{api_base}/api/learning/paper-simulations/run-approved?{run_query}",
    )
    results["steps"].append({"action": "run_approved", "result": run_result})

    results["drafted_count"] = draft_result.get("created_count", 0)
    results["run_count"] = run_result.get("run_count", 0)
    return results


def run_paper_evaluation(api_base: str, limit: int) -> dict:
    """Evaluate recent paper simulation actions."""
    query = urllib.parse.urlencode({"limit": limit, "horizon_days": 5})
    return request_json("POST", f"{api_base}/api/learning/paper-simulation-evaluations/evaluate-recent?{query}")


def run_price_readiness(api_base: str, limit: int) -> dict:
    """Run price readiness check for top candidates."""
    query = urllib.parse.urlencode({"limit": limit})
    return request_json("POST", f"{api_base}/api/data/price-readiness/run?{query}")


def run_daily_bar_cache(api_base: str, limit: int) -> dict:
    """Run daily bar cache refresh for top candidates."""
    query = urllib.parse.urlencode({"limit": limit, "days": 120})
    return request_json("POST", f"{api_base}/api/data/daily-bars/refresh?{query}")


def run_backtest_cycle(api_base: str, limit: int) -> dict:
    """Run a safe historical backtest request through the local API."""
    from datetime import timedelta

    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
    payload = {
        "start_date": start_date,
        "end_date": end_date,
        "symbols": [],
        "initial_cash": 100000.0,
        "max_positions": max(1, min(limit, 10)),
        "per_symbol_cap": 0.2,
    }
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"{api_base}/api/backtest/runs",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=180) as response:
        return json.loads(response.read().decode("utf-8"))


def run_experience_review(api_base: str) -> dict:
    """Capture recent simulation evidence and write a review-only daily memory."""
    return request_json("POST", f"{api_base}/api/experience/reviews/daily")


def run_code_evolution_review(api_base: str, limit: int) -> dict:
    """Generate review-only code evolution suggestions from experience memory."""
    query = urllib.parse.urlencode({"limit": limit})
    return request_json("POST", f"{api_base}/api/experience/code-evolution/generate?{query}")


def run_realtime_refresh(api_base: str, symbols: str, limit: int) -> dict:
    """Refresh configured realtime provider events without creating live orders."""
    query = urllib.parse.urlencode({"symbols": symbols, "limit": limit})
    return request_json("POST", f"{api_base}/api/realtime/refresh?{query}")


def run_realtime_monitoring_sync(api_base: str, limit: int) -> dict:
    """Sync persisted realtime events into review-only monitoring alerts."""
    query = urllib.parse.urlencode({"limit": limit})
    return request_json("POST", f"{api_base}/api/realtime/monitoring-sync?{query}")


def run_realtime_cycle(api_base: str, symbols: str, limit: int) -> dict:
    """Run refresh -> monitoring sync -> replay as one scheduler-safe cycle."""
    query = urllib.parse.urlencode(
        {
            "symbols": symbols,
            "refresh_limit": limit,
            "sync_limit": max(limit, 100),
            "replay_limit": max(limit, 100),
        }
    )
    return request_json("POST", f"{api_base}/api/realtime/cycle?{query}")


def run_simulation_cockpit(api_base: str, limit: int) -> dict:
    """Run verified Tonghuashun simulation-account actions only."""
    query = urllib.parse.urlencode({"limit": limit})
    return request_json("POST", f"{api_base}/api/automation/cycles/simulation-cockpit-run?{query}")


def run_dataset2_training_status(api_base: str, limit: int) -> dict:
    """Inspect Dataset2 controlled-training readiness after the health guard."""
    health = ensure_simulation_health(api_base)
    query = urllib.parse.urlencode({"limit": limit})
    status = request_json("GET", f"{api_base}/api/learning/dataset2/training/status?{query}")
    return {
        "health": health,
        "dataset2_training": status,
        "simulation_only": True,
        "live_trading_enabled": health.get("live_trading_enabled"),
    }


def run_dataset2_training_run(api_base: str, limit: int) -> dict:
    """Run in-memory Dataset2 training dry-run; never writes a model artifact."""
    health = ensure_simulation_health(api_base)
    result = request_json_payload(
        "POST",
        f"{api_base}/api/learning/dataset2/training/run",
        {"limit": limit, "requested_by": "automation_loop"},
    )
    return {
        "health": health,
        "dataset2_training_run": result,
        "simulation_only": True,
        "live_trading_enabled": health.get("live_trading_enabled"),
    }


def run_sim_cockpit_supervised_cycle(api_base: str, limit: int) -> dict:
    """Codex-supervised detect/dry-run/training loop with no live trading path."""
    health = ensure_simulation_health(api_base)
    review_query = urllib.parse.urlencode({"limit": max(limit, 8)})
    simulation_review_plan = request_json(
        "GET", f"{api_base}/api/research/offhour/simulation-review-plan/latest?{review_query}"
    )
    simulation_review_plan_summary = summarize_simulation_review_plan(simulation_review_plan)
    learning_query = urllib.parse.urlencode({"limit": max(limit, 8)})
    strategy_learning_packet = request_json(
        "GET", f"{api_base}/api/research/offhour/strategy-learning-packet/latest?{learning_query}"
    )
    strategy_training_plan_summary = summarize_strategy_training_plan(strategy_learning_packet)
    detection = request_json("GET", f"{api_base}/api/sim-cockpit/window-detection?record=false")
    pre_detection_status = request_json("GET", f"{api_base}/api/sim-cockpit/status")
    detection_reasons = set(detection.get("blocked_reasons") or [])
    should_record_detection = (
        detection.get("status") == "verified"
        or "dangerous_real_trading_terms_detected" in detection_reasons
        or "live_trading_enabled" in detection_reasons
        or pre_detection_status.get("status") != "verified"
    )
    if should_record_detection:
        detection = request_json("GET", f"{api_base}/api/sim-cockpit/window-detection?record=true")
    cockpit_status = request_json("GET", f"{api_base}/api/sim-cockpit/status")
    supervised_sample_gate = summarize_supervised_sample_gate(
        detection,
        cockpit_status,
        strategy_training_plan_summary,
    )
    current_safety_summary = summarize_sim_cockpit_current_safety(
        cockpit_status,
        supervised_sample_gate,
    )
    window_readiness_checklist = summarize_sim_cockpit_window_readiness(
        detection,
        cockpit_status,
        supervised_sample_gate,
    )
    cockpit_cycle = run_simulation_cockpit(api_base, limit)
    query = urllib.parse.urlencode({"limit": max(limit, 20)})
    dataset2_status = request_json("GET", f"{api_base}/api/learning/dataset2/training/status?{query}")
    dataset2_run = request_json_payload(
        "POST",
        f"{api_base}/api/learning/dataset2/training/run",
        {"limit": max(limit, 20), "requested_by": "automation_loop_supervisor"},
    )
    return {
        "health": health,
        "window_detection": detection,
        "window_detection_recorded": should_record_detection,
        "latest_simulation_review_plan_summary": simulation_review_plan_summary,
        "strategy_training_plan_summary": strategy_training_plan_summary,
        "supervised_sample_gate": supervised_sample_gate,
        "sim_cockpit_window_readiness_checklist": window_readiness_checklist,
        "sim_cockpit_current_safety_summary": current_safety_summary,
        "sim_cockpit_status": cockpit_status,
        "sim_cockpit_cycle": cockpit_cycle,
        "dataset2_training_status": dataset2_status,
        "dataset2_training_run": dataset2_run,
        "next_action": _supervised_next_action(
            detection,
            cockpit_status,
            dataset2_status,
            dataset2_run,
            simulation_review_plan_summary,
            strategy_training_plan_summary,
            supervised_sample_gate,
            window_readiness_checklist,
        ),
        "simulation_only": True,
        "live_trading_enabled": health.get("live_trading_enabled"),
    }


def _supervised_next_action(
    detection: dict,
    cockpit_status: dict,
    dataset2_status: dict,
    dataset2_run: dict,
    simulation_review_plan_summary: dict | None = None,
    strategy_training_plan_summary: dict | None = None,
    supervised_sample_gate: dict | None = None,
    window_readiness_checklist: dict | None = None,
) -> str:
    summary = simulation_review_plan_summary or {}
    top_candidates = summary.get("top_candidates") or []
    training_summary = strategy_training_plan_summary or {}
    sample_gate = supervised_sample_gate or {}
    readiness = window_readiness_checklist or {}
    next_sample_symbols = sample_gate.get("next_sample_symbols") or []
    if readiness.get("status") == "blocked" and readiness.get("safe_next_action"):
        return str(readiness.get("safe_next_action"))
    if detection.get("status") != "verified":
        if cockpit_status.get("status") == "verified":
            return (
                "Read-only simulation evidence is verified, so dry-run collection may continue; "
                "desktop marker detection still needs improvement before screen-click simulation."
            )
        reasons = ", ".join(detection.get("blocked_reasons") or ["window_not_verified"])
        return f"Open Tonghuashun simulated trading window and rerun supervised cycle: {reasons}."
    if cockpit_status.get("status") != "verified":
        return "Verify the Tonghuashun simulated-account window, then rerun detect/dry-run collection."
    if not dataset2_status.get("training_allowed"):
        reasons = ", ".join(dataset2_status.get("blocked_reasons") or ["unknown"])
        return f"Collect more simulation readbacks or staged records before training: {reasons}."
    if dataset2_run.get("status") != "completed":
        reasons = ", ".join(dataset2_run.get("blocked_reasons") or ["unknown"])
        return f"Training run stayed blocked: {reasons}."
    if sample_gate.get("status") == "ready_for_supervised_dry_run_collection" and next_sample_symbols:
        symbols = ", ".join(
            f"{item.get('symbol')}:{item.get('target_next_dry_run_samples')}"
            for item in next_sample_symbols
            if item.get("symbol")
        )
        return (
            "Collect supervised dry-run/readback samples from the training queue "
            f"({symbols}); keep orders and screen-click permission disabled until separate gates pass."
        )
    if training_summary.get("training_plan_status") == "needs_supervised_samples":
        reasons = ", ".join(sample_gate.get("blocked_reasons") or ["sample_gate_not_ready"])
        return f"Training plan needs samples, but supervised sample gate is blocked: {reasons}."
    if top_candidates:
        symbols = ", ".join(str(item.get("symbol")) for item in top_candidates[:3] if item.get("symbol"))
        return (
            "Review in-memory training metrics and dry-run the latest offhour evidence candidates "
            f"({symbols}); model artifact writing and screen-click permission remain disabled."
        )
    return "Review in-memory training metrics; model artifact writing remains disabled."


def run_offhour_research_status(api_base: str) -> dict:
    """Inspect off-hour research-loop capabilities and latest audit state."""
    health = ensure_simulation_health(api_base)
    capabilities = request_json("GET", f"{api_base}/api/research/offhour/capabilities")
    latest = request_json("GET", f"{api_base}/api/research/offhour/runs/latest")
    model_candidate = request_json("GET", f"{api_base}/api/research/offhour/model-candidates/latest")
    simulation_review_plan = request_json("GET", f"{api_base}/api/research/offhour/simulation-review-plan/latest")
    simulation_review_plan_summary = summarize_simulation_review_plan(simulation_review_plan)
    strategy_learning_packet = request_json(
        "GET", f"{api_base}/api/research/offhour/strategy-learning-packet/latest?limit=5"
    )
    return {
        "health": health,
        "capabilities": capabilities,
        "latest_run": latest,
        "latest_model_candidate": model_candidate,
        "latest_simulation_review_plan": simulation_review_plan,
        "latest_simulation_review_plan_summary": simulation_review_plan_summary,
        "latest_strategy_learning_packet": strategy_learning_packet,
        "simulation_only": True,
        "live_trading_enabled": health.get("live_trading_enabled"),
    }


def run_offhour_simulation_review_plan(api_base: str, limit: int) -> dict:
    """Inspect the latest off-hour dry-run candidate plan without executing it."""
    health = ensure_simulation_health(api_base)
    query = urllib.parse.urlencode({"limit": limit})
    plan = request_json("GET", f"{api_base}/api/research/offhour/simulation-review-plan/latest?{query}")
    plan_summary = summarize_simulation_review_plan(plan)
    return {
        "health": health,
        "simulation_review_plan": plan,
        "simulation_review_plan_summary": plan_summary,
        "next_action": (
            "Use detect_only/dry_run_screen during trading time; require Sim-Cockpit verification before clicks."
            if plan.get("status") == "ready_for_dry_run_review"
            else "Rerun offhour research loop or refresh daily bars before trading-time simulation review."
        ),
        "simulation_only": True,
        "live_trading_enabled": health.get("live_trading_enabled"),
    }


def run_offhour_strategy_learning_packet(api_base: str, limit: int) -> dict:
    """Inspect the current Dataset1+Dataset2 strategy learning packet."""
    health = ensure_simulation_health(api_base)
    query = urllib.parse.urlencode({"limit": limit})
    packet = request_json("GET", f"{api_base}/api/research/offhour/strategy-learning-packet/latest?{query}")
    return {
        "health": health,
        "strategy_learning_packet": packet,
        "next_action": packet.get("next_action")
        or "Review learning packet before any supervised dry-run collection.",
        "simulation_only": True,
        "live_trading_enabled": health.get("live_trading_enabled"),
    }


def run_offhour_training_plan_summary(api_base: str, limit: int) -> dict:
    """Return a compact next-batch supervised simulation training plan."""
    health = ensure_simulation_health(api_base)
    query = urllib.parse.urlencode({"limit": limit})
    packet = request_json("GET", f"{api_base}/api/research/offhour/strategy-learning-packet/latest?{query}")
    summary = summarize_strategy_training_plan(packet)
    return {
        "health": health,
        "strategy_training_plan_summary": summary,
        "next_action": summary.get("next_action")
        or "Collect supervised dry-run/readback samples only after simulation-window verification.",
        "simulation_only": True,
        "live_trading_enabled": health.get("live_trading_enabled"),
    }


def run_offhour_research_loop(api_base: str, limit: int) -> dict:
    """Run balanced potential search + Dataset2 strategy replay + sandbox review."""
    health = ensure_simulation_health(api_base)
    result = request_json_payload(
        "POST",
        f"{api_base}/api/research/offhour/run",
        {
            "limit": max(10, limit),
            "strategy_limit": max(5, limit),
            "history_days": 240,
            "write_artifact": True,
            "refresh_history": False,
            "requested_by": "automation_loop",
        },
    )
    return {
        "health": health,
        "offhour_research": result,
        "simulation_only": True,
        "live_trading_enabled": health.get("live_trading_enabled"),
    }


def run_browser_cycle() -> dict:
    completed = subprocess.run(
        ["npm.cmd", "run", "automation:browser"],
        cwd=FRONTEND_DIR,
        capture_output=True,
        text=True,
        timeout=300,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr or completed.stdout)
    return {
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def append_log(payload: dict) -> None:
    log_dir = PROJECT_ROOT / "backend" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    with (log_dir / "automation_loop.jsonl").open("a", encoding="utf-8") as file:
        file.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run safe simulation automation loop.")
    parser.add_argument("--api-base", default=DEFAULT_API_BASE)
    parser.add_argument("--mode", choices=["api", "cycle", "discovery", "potential", "browser", "monitor", "agent-task", "agent-learning", "agent-outcomes", "signal-performance", "sandbox-experiments", "paper-simulation", "paper-evaluation", "price-readiness", "daily-bar-cache", "backtest", "experience-review", "code-evolution-review", "realtime-refresh", "realtime-monitoring-sync", "realtime-cycle", "simulation-cockpit-run", "dataset2-training-status", "dataset2-training-run", "sim-cockpit-supervised-cycle", "offhour-research-status", "offhour-simulation-review-plan", "offhour-strategy-learning-packet", "offhour-training-plan-summary", "offhour-research-loop"], default="cycle")
    parser.add_argument("--task-type", default="offhour_potential_search", help="Task type for agent-task mode")
    parser.add_argument("--interval-seconds", type=int, default=60)
    parser.add_argument("--max-cycles", type=int, default=1, help="Use 0 to run forever.")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--monitor-limit", type=int, default=5)
    parser.add_argument("--review-symbol", default="SZ002081")
    parser.add_argument("--symbols", default="SZ002081,SZ002115")
    parser.add_argument("--continue-on-error", action="store_true")
    args = parser.parse_args()

    cycle = 0
    while args.max_cycles <= 0 or cycle < args.max_cycles:
        cycle += 1
        entry = {
            "cycle": cycle,
            "mode": args.mode,
            "started_at": datetime.now().isoformat(timespec="seconds"),
        }
        try:
            if args.mode == "browser":
                entry["result"] = run_browser_cycle()
            elif args.mode == "monitor":
                entry["result"] = run_monitor_cycle(args.api_base, args.limit)
            elif args.mode == "agent-task":
                entry["result"] = run_agent_task(args.api_base, args.task_type)
            elif args.mode == "discovery":
                entry["result"] = run_discovery_cycle(args.api_base, args.limit)
            elif args.mode == "potential":
                entry["result"] = run_potential_cycle(args.api_base, args.limit)
            elif args.mode == "cycle":
                entry["result"] = run_full_cycle(
                    args.api_base,
                    CYCLE_LIMIT,
                    CYCLE_MONITOR_LIMIT,
                    CYCLE_REVIEW_SYMBOL,
                )
            elif args.mode == "agent-learning":
                entry["result"] = run_agent_learning(args.api_base, args.limit)
            elif args.mode == "agent-outcomes":
                entry["result"] = run_agent_outcomes(args.api_base, args.limit)
            elif args.mode == "signal-performance":
                entry["result"] = run_signal_performance(args.api_base)
            elif args.mode == "sandbox-experiments":
                entry["result"] = run_sandbox_experiments(args.api_base, args.limit)
            elif args.mode == "paper-simulation":
                entry["result"] = run_paper_simulation(args.api_base, args.limit)
            elif args.mode == "paper-evaluation":
                entry["result"] = run_paper_evaluation(args.api_base, args.limit)
            elif args.mode == "price-readiness":
                entry["result"] = run_price_readiness(args.api_base, args.limit)
            elif args.mode == "daily-bar-cache":
                entry["result"] = run_daily_bar_cache(args.api_base, args.limit)
            elif args.mode == "backtest":
                entry["result"] = run_backtest_cycle(args.api_base, args.limit)
            elif args.mode == "experience-review":
                entry["result"] = run_experience_review(args.api_base)
            elif args.mode == "code-evolution-review":
                entry["result"] = run_code_evolution_review(args.api_base, args.limit)
            elif args.mode == "realtime-refresh":
                entry["result"] = run_realtime_refresh(args.api_base, args.symbols, args.limit)
            elif args.mode == "realtime-monitoring-sync":
                entry["result"] = run_realtime_monitoring_sync(args.api_base, args.limit)
            elif args.mode == "realtime-cycle":
                entry["result"] = run_realtime_cycle(args.api_base, args.symbols, args.limit)
            elif args.mode == "simulation-cockpit-run":
                entry["result"] = run_simulation_cockpit(args.api_base, args.limit)
            elif args.mode == "dataset2-training-status":
                entry["result"] = run_dataset2_training_status(args.api_base, args.limit)
            elif args.mode == "dataset2-training-run":
                entry["result"] = run_dataset2_training_run(args.api_base, args.limit)
            elif args.mode == "sim-cockpit-supervised-cycle":
                entry["result"] = run_sim_cockpit_supervised_cycle(args.api_base, args.limit)
            elif args.mode == "offhour-research-status":
                entry["result"] = run_offhour_research_status(args.api_base)
            elif args.mode == "offhour-simulation-review-plan":
                entry["result"] = run_offhour_simulation_review_plan(args.api_base, args.limit)
            elif args.mode == "offhour-strategy-learning-packet":
                entry["result"] = run_offhour_strategy_learning_packet(args.api_base, args.limit)
            elif args.mode == "offhour-training-plan-summary":
                entry["result"] = run_offhour_training_plan_summary(args.api_base, args.limit)
            elif args.mode == "offhour-research-loop":
                entry["result"] = run_offhour_research_loop(args.api_base, args.limit)
            else:
                entry["result"] = run_api_cycle(args.api_base, args.limit)
            entry["status"] = "completed"
        except (urllib.error.URLError, RuntimeError, subprocess.TimeoutExpired) as exc:
            entry["status"] = "failed"
            entry["error"] = str(exc)
            if isinstance(exc, urllib.error.URLError):
                entry["next_action"] = "Check backend API health and connectivity."
            else:
                entry["next_action"] = "Check provider stability or fallback data sources."
            append_log(entry)
            print(json.dumps(entry, ensure_ascii=False, indent=2))
            if not args.continue_on_error:
                return 1
        else:
            append_log(entry)
            print(json.dumps(entry, ensure_ascii=False, indent=2))

        if args.max_cycles <= 0 or cycle < args.max_cycles:
            time.sleep(max(1, args.interval_seconds))

    return 0


if __name__ == "__main__":
    sys.exit(main())
