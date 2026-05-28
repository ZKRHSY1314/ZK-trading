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


def request_json(method: str, url: str) -> dict:
    request = urllib.request.Request(url, method=method)
    with urllib.request.urlopen(request, timeout=180) as response:
        return json.loads(response.read().decode("utf-8"))


def run_api_cycle(api_base: str, limit: int) -> dict:
    query = urllib.parse.urlencode({"limit": limit})
    return request_json("POST", f"{api_base}/api/automation/run-once?{query}")


def run_full_cycle(api_base: str, limit: int, monitor_limit: int, review_symbol: str) -> dict:
    query = urllib.parse.urlencode(
        {
            "limit": limit,
            "monitor_limit": monitor_limit,
            "review_symbol": review_symbol,
        }
    )
    return request_json("POST", f"{api_base}/api/automation/cycles/run-once?{query}")


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
    parser.add_argument("--mode", choices=["api", "cycle", "discovery", "potential", "browser", "monitor", "agent-task", "agent-learning", "agent-outcomes", "signal-performance", "sandbox-experiments", "paper-simulation", "paper-evaluation", "price-readiness", "daily-bar-cache"], default="cycle")
    parser.add_argument("--task-type", default="offhour_potential_search", help="Task type for agent-task mode")
    parser.add_argument("--interval-seconds", type=int, default=60)
    parser.add_argument("--max-cycles", type=int, default=1, help="Use 0 to run forever.")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--monitor-limit", type=int, default=5)
    parser.add_argument("--review-symbol", default="SZ002081")
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
                    args.limit,
                    args.monitor_limit,
                    args.review_symbol,
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
