from __future__ import annotations

from collections import Counter
from typing import Any

import pandas as pd

from app.backtest.engine import BacktestEngine
from app.config import settings
from app.models import CandidateTier, RuleHit
from app.rules.loader import load_rule_config
from app.storage.sqlite_store import SQLiteStore


class BacktestRiskDiagnosticsService:
    """Read-only explanation of why a formal backtest produced no buys."""

    def __init__(
        self,
        store: SQLiteStore | None = None,
        config: dict[str, Any] | None = None,
    ) -> None:
        self.store = store or SQLiteStore(settings.database_path)
        self.config = config or load_rule_config()
        self.engine = BacktestEngine(config=self.config)
        self.engine.store = self.store

    def diagnose(
        self,
        *,
        start_date: str,
        end_date: str,
        symbols: list[str],
        symbol_source: str = "input",
        sample_limit: int = 5,
    ) -> dict[str, Any]:
        requested_symbols = [symbol for symbol in symbols if symbol]
        if not requested_symbols:
            return self._empty("no_symbols", symbol_source=symbol_source)

        dfs = self.engine._load_symbol_frames(requested_symbols)
        loaded_symbols = sorted(dfs)
        missing_symbols = sorted(set(requested_symbols) - set(loaded_symbols))
        all_dates = self.engine._trade_dates(dfs, start_date, end_date)

        evaluated = 0
        skipped_due_to_data = 0
        blocked_count = 0
        score_rejected_count = 0
        watch_count = 0
        strong_count = 0
        hard_block_counts: Counter[str] = Counter()
        hard_block_names: dict[str, str] = {}
        hard_block_samples: dict[str, list[dict[str, Any]]] = {}
        rejected_samples: list[dict[str, Any]] = []
        top_non_blocked: list[dict[str, Any]] = []

        for current_date in all_dates:
            curr_dt = pd.to_datetime(current_date)
            for sym, df in dfs.items():
                if curr_dt not in df.index:
                    continue
                hist = df.loc[:curr_dt]
                if len(hist) < 2:
                    continue
                bar = hist.iloc[-1]
                prev_bar = hist.iloc[-2]
                if pd.isna(bar["close"]) or pd.isna(bar["open"]):
                    skipped_due_to_data += 1
                    continue

                snapshot = self.engine._snapshot(sym, current_date, hist, bar, prev_bar)
                decision = self.engine.rule_engine.evaluate(snapshot)
                evaluated += 1
                failed_hard_hits = [
                    hit for hit in decision.hits if hit.hard_block and not hit.passed
                ]

                if decision.blocked:
                    blocked_count += 1
                    for hit in failed_hard_hits:
                        hard_block_counts[hit.rule_id] += 1
                        hard_block_names[hit.rule_id] = hit.name
                        samples = hard_block_samples.setdefault(hit.rule_id, [])
                        if len(samples) < sample_limit:
                            samples.append(
                                {
                                    "symbol": sym,
                                    "trade_date": current_date,
                                    "score": round(float(decision.score), 6),
                                    "reason": hit.reason,
                                    "evidence": hit.evidence,
                                    "threshold": hit.threshold,
                                }
                            )
                    if len(rejected_samples) < sample_limit:
                        rejected_samples.append(
                            {
                                "symbol": sym,
                                "trade_date": current_date,
                                "score": round(float(decision.score), 6),
                                "tier": decision.tier.value,
                                "failed_hard_blocks": [
                                    self._compact_hit(hit) for hit in failed_hard_hits
                                ],
                            }
                        )
                else:
                    if decision.tier == CandidateTier.strong:
                        strong_count += 1
                    elif decision.tier == CandidateTier.watch:
                        watch_count += 1
                    else:
                        score_rejected_count += 1
                    top_non_blocked.append(
                        {
                            "symbol": sym,
                            "trade_date": current_date,
                            "score": round(float(decision.score), 6),
                            "tier": decision.tier.value,
                        }
                    )

        top_non_blocked.sort(key=lambda item: item["score"], reverse=True)
        hard_blocks = [
            {
                "rule_id": rule_id,
                "rule_name": hard_block_names.get(rule_id, rule_id),
                "count": count,
                "share_of_blocked": round(count / blocked_count, 6) if blocked_count else 0.0,
                "samples": hard_block_samples.get(rule_id, []),
            }
            for rule_id, count in hard_block_counts.most_common()
        ]

        status = "ready" if evaluated else "insufficient_data"
        return {
            "schema_version": "backtest_risk_rejection_diagnostics.v1",
            "status": status,
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
            "symbol_source": symbol_source,
            "start_date": start_date,
            "end_date": end_date,
            "requested_symbol_count": len(requested_symbols),
            "loaded_symbol_count": len(loaded_symbols),
            "missing_symbols": missing_symbols,
            "date_count": len(all_dates),
            "evaluated_decision_count": evaluated,
            "blocked_decision_count": blocked_count,
            "score_rejected_decision_count": score_rejected_count,
            "watch_decision_count": watch_count,
            "strong_decision_count": strong_count,
            "skipped_due_to_data_count": skipped_due_to_data,
            "hard_block_summary": hard_blocks,
            "sample_rejections": rejected_samples,
            "top_non_blocked": top_non_blocked[:sample_limit],
            "next_action": self._next_action(
                evaluated=evaluated,
                blocked_count=blocked_count,
                hard_blocks=hard_blocks,
                strong_count=strong_count,
                watch_count=watch_count,
            ),
        }

    @staticmethod
    def _compact_hit(hit: RuleHit) -> dict[str, Any]:
        return {
            "rule_id": hit.rule_id,
            "rule_name": hit.name,
            "reason": hit.reason,
            "threshold": hit.threshold,
            "evidence": hit.evidence,
            "evidence_snippet": hit.evidence_snippet,
            "source": hit.source,
        }

    @staticmethod
    def _empty(status: str, *, symbol_source: str) -> dict[str, Any]:
        return {
            "schema_version": "backtest_risk_rejection_diagnostics.v1",
            "status": status,
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
            "symbol_source": symbol_source,
            "evaluated_decision_count": 0,
            "blocked_decision_count": 0,
            "hard_block_summary": [],
            "sample_rejections": [],
            "top_non_blocked": [],
            "next_action": "provide_backtest_symbols",
        }

    @staticmethod
    def _next_action(
        *,
        evaluated: int,
        blocked_count: int,
        hard_blocks: list[dict[str, Any]],
        strong_count: int,
        watch_count: int,
    ) -> str:
        if evaluated == 0:
            return "refresh_daily_bar_cache_or_select_symbols_with_history"
        if blocked_count and hard_blocks:
            top_rule = hard_blocks[0]["rule_id"]
            return f"review_hard_block_rule:{top_rule}"
        if strong_count or watch_count:
            return "review_execution_model_or_position_limits"
        return "review_score_thresholds_and_strategy_signal_weights"
