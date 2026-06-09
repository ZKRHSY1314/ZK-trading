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
        "sim_cockpit_status": cockpit_status,
        "sim_cockpit_cycle": cockpit_cycle,
        "dataset2_training_status": dataset2_status,
        "dataset2_training_run": dataset2_run,
        "next_action": _supervised_next_action(detection, cockpit_status, dataset2_status, dataset2_run),
        "simulation_only": True,
        "live_trading_enabled": health.get("live_trading_enabled"),
    }


def _supervised_next_action(
    detection: dict,
    cockpit_status: dict,
    dataset2_status: dict,
    dataset2_run: dict,
) -> str:
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
    return "Review in-memory training metrics; model artifact writing remains disabled."


def run_offhour_research_status(api_base: str) -> dict:
    """Inspect off-hour research-loop capabilities and latest audit state."""
    health = ensure_simulation_health(api_base)
    capabilities = request_json("GET", f"{api_base}/api/research/offhour/capabilities")
    latest = request_json("GET", f"{api_base}/api/research/offhour/runs/latest")
    model_candidate = request_json("GET", f"{api_base}/api/research/offhour/model-candidates/latest")
    return {
        "health": health,
        "capabilities": capabilities,
        "latest_run": latest,
        "latest_model_candidate": model_candidate,
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
    parser.add_argument("--mode", choices=["api", "cycle", "discovery", "potential", "browser", "monitor", "agent-task", "agent-learning", "agent-outcomes", "signal-performance", "sandbox-experiments", "paper-simulation", "paper-evaluation", "price-readiness", "daily-bar-cache", "backtest", "experience-review", "code-evolution-review", "realtime-refresh", "realtime-monitoring-sync", "realtime-cycle", "simulation-cockpit-run", "dataset2-training-status", "dataset2-training-run", "sim-cockpit-supervised-cycle", "offhour-research-status", "offhour-research-loop"], default="cycle")
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
