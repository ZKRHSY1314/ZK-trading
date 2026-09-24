from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.config import settings  # noqa: E402


MIN_TRADE_COUNT = 5
MIN_SANDBOX_WIN_RATE = 0.6
MIN_SIGNAL_AVG_RETURN_PCT = 0.0


def _load_json(raw: str | None, default: Any) -> Any:
    if not raw:
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return default


def _latest_offhour_run(run_id: int | None = None) -> dict[str, Any]:
    db_path = Path(settings.database_path)
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        if run_id is None:
            row = conn.execute(
                "SELECT * FROM offhour_research_runs ORDER BY id DESC LIMIT 1"
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM offhour_research_runs WHERE id = ?",
                (run_id,),
            ).fetchone()
    if not row:
        raise SystemExit("No offhour_research_runs row found.")
    return dict(row)


def _recommend_rule_actions(
    sandbox: dict[str, Any],
    signal_backtest: dict[str, Any],
) -> list[dict[str, Any]]:
    sandbox_perf = sandbox.get("pattern_performance") or {}
    signal_perf = signal_backtest.get("pattern_performance") or {}
    pattern_ids = sorted(set(sandbox_perf) | set(signal_perf))
    recommendations: list[dict[str, Any]] = []
    for pattern_id in pattern_ids:
        sandbox_row = sandbox_perf.get(pattern_id) or {}
        signal_row = signal_perf.get(pattern_id) or {}
        sample_count = int(sandbox_row.get("sample_count") or 0)
        trade_count = int(signal_row.get("trade_count") or 0)
        sandbox_win_rate = float(sandbox_row.get("win_rate") or 0)
        signal_win_rate = float(signal_row.get("win_rate") or 0)
        sandbox_avg_close = float(sandbox_row.get("avg_close_return_pct") or 0)
        signal_avg_return = float(signal_row.get("avg_return_pct") or 0)

        if trade_count < MIN_TRADE_COUNT:
            action = "needs_more_samples"
            reason = "trade_count_below_floor"
        elif sandbox_win_rate >= MIN_SANDBOX_WIN_RATE and signal_avg_return > MIN_SIGNAL_AVG_RETURN_PCT:
            action = "include_sandbox_candidate"
            reason = "sandbox_win_rate_and_signal_return_positive"
        elif signal_avg_return <= 0 or sandbox_avg_close <= 0:
            action = "exclude_direct_buy_or_context_only"
            reason = "non_positive_return_or_sandbox_close_return"
        else:
            action = "watch_only"
            reason = "mixed_evidence"

        recommendations.append(
            {
                "pattern_id": pattern_id,
                "action": action,
                "reason": reason,
                "sandbox_sample_count": sample_count,
                "sandbox_win_rate": round(sandbox_win_rate, 6),
                "sandbox_avg_close_return_pct": round(sandbox_avg_close, 6),
                "signal_trade_count": trade_count,
                "signal_win_rate": round(signal_win_rate, 6),
                "signal_avg_return_pct": round(signal_avg_return, 6),
                "allowed_effect": "sandbox_review_only",
            }
        )
    return recommendations


def _compact_trades(signal_backtest: dict[str, Any]) -> list[dict[str, Any]]:
    trades = signal_backtest.get("trades") or []
    fields = [
        "symbol",
        "pattern_id",
        "pattern_name",
        "action_label",
        "signal_date",
        "entry_date",
        "entry_price",
        "quantity",
        "exit_date",
        "exit_reason",
        "realized_pnl_pct",
    ]
    return [{field: trade.get(field) for field in fields} for trade in trades]


def build_summary(run_id: int | None = None) -> dict[str, Any]:
    row = _latest_offhour_run(run_id)
    replay = _load_json(row.get("strategy_replay_json"), {})
    sandbox = _load_json(row.get("sandbox_json"), {})
    backtest = _load_json(row.get("backtest_json"), {})
    artifact = _load_json(row.get("artifact_json"), {})
    signal_backtest = backtest.get("dataset2_signal_backtest") or {}
    signal_optimization = backtest.get("dataset2_signal_optimization") or {}

    return {
        "schema_version": "rule_sandbox_backtest_summary.v1",
        "offhour_run": {
            "id": row.get("id"),
            "status": row.get("status"),
            "created_at": row.get("created_at"),
            "completed_at": row.get("completed_at"),
            "next_action": row.get("next_action"),
            "review_only": bool(row.get("review_only")),
            "simulation_only": bool(row.get("simulation_only")),
            "live_trading_enabled": bool(row.get("live_trading_enabled")),
        },
        "replay": {
            "status": replay.get("status"),
            "signal_count": replay.get("signal_count"),
            "recent_signal_count": replay.get("recent_signal_count"),
            "expanded_signal_count": replay.get("expanded_signal_count"),
            "symbols": replay.get("symbols") or [],
            "action_counts": replay.get("action_counts") or {},
            "pattern_counts": replay.get("pattern_counts") or {},
        },
        "sandbox": {
            "status": sandbox.get("status"),
            "evaluated_count": sandbox.get("evaluated_count", 0),
            "pending_count": sandbox.get("pending_count", 0),
            "outcome_counts": sandbox.get("outcome_counts") or {},
            "pattern_performance": sandbox.get("pattern_performance") or {},
        },
        "historical_backtest": {
            "status": backtest.get("status"),
            "run_id": backtest.get("run_id"),
            "symbols": backtest.get("symbols") or [],
            "start_date": backtest.get("start_date"),
            "end_date": backtest.get("end_date"),
            "metrics": backtest.get("metrics") or {},
            "benchmark": backtest.get("benchmark") or {},
            "execution_warnings": backtest.get("execution_warnings") or [],
            "backtest_budget": backtest.get("backtest_budget") or {},
        },
        "signal_backtest": {
            "status": signal_backtest.get("status"),
            "parameters": signal_backtest.get("parameters") or {},
            "metrics": signal_backtest.get("metrics") or {},
            "pattern_performance": signal_backtest.get("pattern_performance") or {},
            "bought_stocks": _compact_trades(signal_backtest),
        },
        "rule_recommendations": _recommend_rule_actions(sandbox, signal_backtest),
        "optimized_rule_candidates": {
            "best": signal_optimization.get("best") or {},
            "best_experience_aligned": signal_optimization.get("best_experience_aligned") or {},
            "gate": signal_optimization.get("gate") or {},
            "shadow_parameter_evidence": (
                signal_optimization.get("shadow_parameter_evidence") or {}
            ).get("expanded_history_review", {}),
        },
        "artifact_gate": {
            "status": artifact.get("status"),
            "artifact_written": artifact.get("artifact_written"),
            "candidate_only": artifact.get("candidate_only"),
            "auto_loaded": artifact.get("auto_loaded"),
            "artifact_path": artifact.get("artifact_path"),
            "rule_update_gate": artifact.get("rule_update_gate") or {},
            "signal_optimization_gate": artifact.get("signal_optimization_gate") or {},
            "simulation_weight_gate": artifact.get("simulation_weight_gate") or {},
        },
        "policy": {
            "writes_rules_yaml": False,
            "writes_model_artifact": False,
            "places_order": False,
            "allowed_effect": "review_report_only",
        },
    }


def _print_markdown(summary: dict[str, Any]) -> None:
    run = summary["offhour_run"]
    print(f"# Rule Sandbox Backtest Summary - offhour run {run['id']}")
    print()
    print(
        f"- status: {run['status']}; review_only={run['review_only']}; "
        f"simulation_only={run['simulation_only']}; live_trading_enabled={run['live_trading_enabled']}"
    )
    print(f"- next_action: {run['next_action']}")
    print()
    print("## Rule Recommendations")
    for item in summary["rule_recommendations"]:
        print(
            f"- {item['pattern_id']}: {item['action']} "
            f"(sandbox_win={item['sandbox_win_rate']}, signal_avg={item['signal_avg_return_pct']}%, "
            f"trades={item['signal_trade_count']}; reason={item['reason']})"
        )
    print()
    print("## Bought Stocks In Signal Backtest")
    print("| symbol | pattern | signal | entry | qty | exit | return_pct |")
    print("|---|---|---:|---:|---:|---:|---:|")
    for trade in summary["signal_backtest"]["bought_stocks"]:
        print(
            "| {symbol} | {pattern_id} | {signal_date} | {entry_date} | {quantity} | {exit_date} | {realized_pnl_pct} |".format(
                **trade
            )
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", type=int, default=None)
    parser.add_argument("--format", choices=["json", "markdown"], default="json")
    args = parser.parse_args()
    summary = build_summary(args.run_id)
    if args.format == "markdown":
        _print_markdown(summary)
    else:
        print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
