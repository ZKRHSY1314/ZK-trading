from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any

import yaml


DEFAULT_DB_PATH = Path("trading_local.sqlite3")
DEFAULT_RULES_PATH = Path("backend/configs/rules.yaml")
DEFAULT_CANDIDATE_RULES_PATH = Path("backend/configs/review_only_buy_sell_rules.yaml")


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle) or {}
    if not isinstance(loaded, dict):
        return {}
    return loaded


def fetch_one(con: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> tuple[Any, ...]:
    row = con.execute(sql, params).fetchone()
    return tuple(row) if row else ()


def latest_backtest(con: sqlite3.Connection) -> dict[str, Any]:
    con.row_factory = sqlite3.Row
    row = con.execute(
        """
        SELECT id, status, start_date, end_date, initial_cash, final_cash,
               metrics_json, execution_warnings_json, created_at
        FROM historical_backtest_runs
        ORDER BY id DESC
        LIMIT 1
        """
    ).fetchone()
    if not row:
        return {"status": "missing"}
    result = dict(row)
    for key in ("metrics_json", "execution_warnings_json"):
        try:
            result[key] = json.loads(result.get(key) or "{}")
        except json.JSONDecodeError:
            result[key] = result.get(key)
    return result


def rule_capacity(config: dict[str, Any]) -> dict[str, Any]:
    tiers = config.get("candidate_tiers") or {}
    rules = config.get("rules") or []
    enabled = [rule for rule in rules if rule.get("enabled", True)]
    implemented_ids = {
        "constitution_no_high_position",
        "dengzhan_low_position_limit_up",
        "dengzhan_forced_divergence",
        "risk_no_chasing_after_big_rise",
    }
    scoring_rules = [
        rule
        for rule in enabled
        if rule.get("group") not in {"constitution", "risk"}
        and str(rule.get("id") or "") in implemented_ids
    ]
    max_positive_score = sum(float(rule.get("weight") or 0) for rule in scoring_rules)
    strong_min = float(tiers.get("strong_min_score") or 0)
    watch_min = float(tiers.get("watch_min_score") or 0)
    return {
        "enabled_rule_count": len(enabled),
        "scoring_rule_count": len(scoring_rules),
        "max_positive_score": round(max_positive_score, 4),
        "strong_min_score": strong_min,
        "watch_min_score": watch_min,
        "can_reach_strong": max_positive_score >= strong_min,
        "can_reach_watch": max_positive_score >= watch_min,
        "scoring_rule_ids": [str(rule.get("id")) for rule in scoring_rules],
    }


def db_diagnostics(con: sqlite3.Connection) -> dict[str, Any]:
    daily = fetch_one(
        con,
        """
        SELECT COUNT(*),
               SUM(CASE WHEN amount IS NULL OR amount <= 0 THEN 1 ELSE 0 END),
               COUNT(DISTINCT symbol),
               MIN(trade_date),
               MAX(trade_date)
        FROM daily_bar_cache
        """,
    )
    scores = fetch_one(
        con,
        """
        SELECT COUNT(*), COUNT(DISTINCT symbol), MIN(total_score),
               AVG(total_score), MAX(total_score)
        FROM candidate_scores
        """,
    )
    replay_count = fetch_one(
        con,
        """
        SELECT COUNT(*), COUNT(DISTINCT symbol), MAX(created_at)
        FROM main_force_phase_replays
        """,
    )
    exit_rows = con.execute(
        """
        SELECT exit_reason, COUNT(*) AS count, AVG(realized_pnl_pct) AS avg_pnl_pct
        FROM historical_backtest_closed_trades
        GROUP BY exit_reason
        """
    ).fetchall()
    exits = [
        {
            "exit_reason": row[0],
            "count": int(row[1]),
            "avg_pnl_pct": round(float(row[2] or 0), 4),
        }
        for row in exit_rows
    ]
    rating_rows = con.execute(
        """
        SELECT rating, COUNT(*) AS count, AVG(total_score) AS avg_score, MAX(total_score) AS max_score
        FROM candidate_scores
        GROUP BY rating
        ORDER BY count DESC
        """
    ).fetchall()
    ratings = [
        {
            "rating": row[0],
            "count": int(row[1]),
            "avg_score": round(float(row[2] or 0), 4),
            "max_score": round(float(row[3] or 0), 4),
        }
        for row in rating_rows
    ]
    return {
        "daily_bar_cache": {
            "row_count": int(daily[0] or 0),
            "missing_or_zero_amount_count": int(daily[1] or 0),
            "distinct_symbols": int(daily[2] or 0),
            "min_trade_date": daily[3],
            "max_trade_date": daily[4],
        },
        "candidate_scores": {
            "row_count": int(scores[0] or 0),
            "distinct_symbols": int(scores[1] or 0),
            "min_score": round(float(scores[2] or 0), 4),
            "avg_score": round(float(scores[3] or 0), 4),
            "max_score": round(float(scores[4] or 0), 4),
            "ratings": ratings,
        },
        "main_force_phase_replays": {
            "row_count": int(replay_count[0] or 0),
            "distinct_symbols": int(replay_count[1] or 0),
            "latest_created_at": replay_count[2],
        },
        "closed_trade_exits": exits,
    }


def candidate_rule_summary(config: dict[str, Any]) -> dict[str, Any]:
    return {
        "scope": config.get("scope"),
        "review_only": bool(config.get("review_only")),
        "simulation_only": bool(config.get("simulation_only")),
        "writes_rules_yaml": bool(config.get("writes_rules_yaml")),
        "buy_rule_ids": [rule.get("id") for rule in config.get("buy_rules") or []],
        "sell_rule_ids": [rule.get("id") for rule in config.get("sell_rules") or []],
        "risk_filter_ids": [rule.get("id") for rule in config.get("risk_filters") or []],
    }


def findings(rule_info: dict[str, Any], db_info: dict[str, Any], backtest: dict[str, Any]) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    if not rule_info["can_reach_strong"]:
        output.append(
            {
                "severity": "high",
                "problem": "RuleEngine cannot reach strong tier with current implemented scoring rules.",
                "evidence": (
                    f"max_positive_score={rule_info['max_positive_score']} "
                    f"< strong_min_score={rule_info['strong_min_score']}"
                ),
                "solution": "Add sandbox-validated scoring rules or lower thresholds only in review-only experiments.",
            }
        )
    latest_metrics = backtest.get("metrics_json") if isinstance(backtest.get("metrics_json"), dict) else {}
    if latest_metrics.get("trade_count", 0) == 0:
        output.append(
            {
                "severity": "high",
                "problem": "Formal historical backtest still has zero trades.",
                "evidence": (
                    f"trade_count={latest_metrics.get('trade_count')}, "
                    f"rejected_by_risk_count={latest_metrics.get('rejected_by_risk_count')}"
                ),
                "solution": "Separate hard-block diagnostics from candidate scoring, then replay candidate rules before promotion.",
            }
        )
    daily = db_info["daily_bar_cache"]
    if daily["row_count"] and daily["missing_or_zero_amount_count"] == daily["row_count"]:
        output.append(
            {
                "severity": "high",
                "problem": "Backtest execution liquidity cannot work because amount is missing for all cached bars.",
                "evidence": (
                    f"missing_or_zero_amount_count={daily['missing_or_zero_amount_count']} "
                    f"of {daily['row_count']}"
                ),
                "solution": "Repair daily bar amount from a reliable provider or a clearly labeled amount proxy before executable backtests.",
            }
        )
    if not db_info["closed_trade_exits"]:
        output.append(
            {
                "severity": "medium",
                "problem": "No closed-trade exit distribution exists for the formal backtest.",
                "evidence": "historical_backtest_closed_trades is empty.",
                "solution": "Run sandbox signal backtests with staged exit rules, then compare exit reasons before formal integration.",
            }
        )
    output.append(
        {
            "severity": "medium",
            "problem": "Formal BacktestEngine exits are fixed at 8% stop loss, 15% take profit, or 5 holding days.",
            "evidence": "This conflicts with long-base main-force 2.6x staged take-profit discipline.",
            "solution": "Introduce a review-only exit policy layer before changing formal backtest exits.",
        }
    )
    return output


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Strategy Gap Diagnostics",
        "",
        "Review-only diagnostics. No orders, no broker API, no production rules.yaml mutation.",
        "",
        "## Rule Capacity",
        "",
        f"- max_positive_score: {report['rule_capacity']['max_positive_score']}",
        f"- strong_min_score: {report['rule_capacity']['strong_min_score']}",
        f"- can_reach_strong: {str(report['rule_capacity']['can_reach_strong']).lower()}",
        f"- scoring_rule_ids: {', '.join(report['rule_capacity']['scoring_rule_ids'])}",
        "",
        "## Data Coverage",
        "",
    ]
    daily = report["db"]["daily_bar_cache"]
    lines.extend(
        [
            f"- daily_bar_cache rows: {daily['row_count']}",
            f"- symbols: {daily['distinct_symbols']}",
            f"- date range: {daily['min_trade_date']}..{daily['max_trade_date']}",
            f"- missing_or_zero_amount_count: {daily['missing_or_zero_amount_count']}",
            "",
            "## Candidate Rule Layer",
            "",
            f"- scope: {report['candidate_rules']['scope']}",
            f"- writes_rules_yaml: {str(report['candidate_rules']['writes_rules_yaml']).lower()}",
            f"- buy rules: {', '.join(report['candidate_rules']['buy_rule_ids'])}",
            f"- sell rules: {', '.join(report['candidate_rules']['sell_rule_ids'])}",
            "",
            "## Findings",
            "",
        ]
    )
    for item in report["findings"]:
        lines.extend(
            [
                f"### {item['severity'].upper()}: {item['problem']}",
                f"- evidence: {item['evidence']}",
                f"- solution: {item['solution']}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    rules = load_yaml(Path(args.rules_path))
    candidate_rules = load_yaml(Path(args.candidate_rules_path))
    con = sqlite3.connect(args.db_path)
    rule_info = rule_capacity(rules)
    db_info = db_diagnostics(con)
    backtest = latest_backtest(con)
    return {
        "rule_capacity": rule_info,
        "db": db_info,
        "latest_backtest": backtest,
        "candidate_rules": candidate_rule_summary(candidate_rules),
        "findings": findings(rule_info, db_info, backtest),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Review-only strategy gap diagnostics.")
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH))
    parser.add_argument("--rules-path", default=str(DEFAULT_RULES_PATH))
    parser.add_argument("--candidate-rules-path", default=str(DEFAULT_CANDIDATE_RULES_PATH))
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    args = parser.parse_args()

    report = build_report(args)
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
