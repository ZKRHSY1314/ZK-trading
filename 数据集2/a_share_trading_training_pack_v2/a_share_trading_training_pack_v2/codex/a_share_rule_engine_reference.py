#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A股 AI 交易驾驶舱 - 规则引擎参考骨架
用途：把数据集中的弱标签规则用于候选评分、解释和模拟交易记录。
限制：本文件不连接券商、不提交订单、不修改实盘配置。
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List

SAFE_ACTIONS = {
    "SIM_BUY_CANDIDATE", "HOLD_OR_TRAIL", "REDUCE_OR_EXIT",
    "AVOID_OR_WAIT", "WAIT_CONFIRMATION", "RISK_ALERT", "NO_TRADE"
}

def load_strategy_set(path: str | Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if data.get("mode") != "simulation_and_training_only":
        raise ValueError("strategy set must be simulation_and_training_only")
    return data

def score_rule(rule: Dict[str, Any], observed_tags: Iterable[str], observed_text: str = "") -> float:
    tags = set(observed_tags)
    cond = rule.get("conditions", {})
    rule_tags = set(cond.get("software_tags", []))
    if not rule_tags:
        return 0.0
    tag_score = len(tags & rule_tags) / max(1, len(rule_tags))
    text_score = 0.0
    text = observed_text or ""
    for feature in cond.get("observable_features", []):
        if feature and feature[:8] in text:
            text_score += 0.05
    return min(1.0, tag_score + text_score)

def evaluate(strategy_set: Dict[str, Any], observed_features: Dict[str, Any], threshold: float = 0.25) -> List[Dict[str, Any]]:
    """Return ranked simulation-only signals.

    observed_features example:
    {
      "tags": ["intraday_t", "price_cross_above_vwap", "volume_surge"],
      "text": "分时上穿均价线并放量",
      "timeframe": "intraday"
    }
    """
    observed_tags = observed_features.get("tags", [])
    observed_text = observed_features.get("text", "")
    timeframe = observed_features.get("timeframe")
    results: List[Dict[str, Any]] = []
    for rule in strategy_set.get("rules", []):
        if timeframe and rule.get("timeframe") not in (timeframe, "intraday/daily", "daily/intraday", "system"):
            # allow loose match for mixed timeframe rules only
            pass
        score = score_rule(rule, observed_tags, observed_text)
        if score >= threshold:
            action = rule.get("outputs", {}).get("action_label", "WAIT_CONFIRMATION")
            if action not in SAFE_ACTIONS:
                action = "WAIT_CONFIRMATION"
            results.append({
                "score": round(score, 4),
                "pattern_id": rule.get("pattern_id"),
                "name": rule.get("name"),
                "category": rule.get("category"),
                "expected_bias": rule.get("outputs", {}).get("expected_bias"),
                "action_label": action,
                "risk_level": rule.get("outputs", {}).get("risk_level"),
                "simulate_only": True,
                "allow_live_order": False,
                "confirmations_needed": rule.get("conditions", {}).get("confirmation_signals", []),
                "source": rule.get("source", {})
            })
    results.sort(key=lambda x: x["score"], reverse=True)
    return results

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("strategy_set")
    parser.add_argument("--tags", nargs="*", default=[])
    parser.add_argument("--text", default="")
    args = parser.parse_args()
    ss = load_strategy_set(args.strategy_set)
    print(json.dumps(evaluate(ss, {"tags": args.tags, "text": args.text}), ensure_ascii=False, indent=2))
