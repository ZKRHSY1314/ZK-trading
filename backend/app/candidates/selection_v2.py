from __future__ import annotations

from collections import Counter
from datetime import date, datetime, time
import json
from pathlib import Path
import re
from statistics import mean
from typing import Any
from zoneinfo import ZoneInfo

import yaml

from app.config import PROJECT_ROOT, settings
from app.data.trading_calendar import trading_session_age
from app.forecasting import ForecastLedger
from app.learning.structure_scoring import ObservableStructureScorer
from app.market_intelligence import SectorExposureResolver
from app.public_opinion.service import CodexPublicOpinionService, SECTOR_TAXONOMY
from app.storage.sqlite_store import SQLiteStore


CONFIG_PATH = PROJECT_ROOT / "backend" / "configs" / "strategy_scoring_v1.yaml"
ARTIFACT_ROOT = PROJECT_ROOT / "output" / "strategy_selection_v2"

PLAN_BUCKETS = {
    "SIM_BUY_PLAN": "strict_buy_plans",
    "WAIT_PULLBACK_PLAN": "wait_pullback_plans",
    "WAIT_BREAKOUT_PLAN": "wait_breakout_plans",
    "WATCH_ONLY_PLAN": "watch_only_candidates",
    "RISK_ALERT_PLAN": "risk_alerts",
    "REJECT_HARD": "rejected_candidates",
    "REJECT_SOFT": "rejected_candidates",
    "SECTOR_BAROMETER": "watch_only_candidates",
}

FORBID_BUY_FLAGS = {
    "HIGH_DISTRIBUTION",
    "VOLUME_ABNORMAL",
    "MA_BREAKDOWN",
    "A_KILL_REPAIR",
    "A_KILL_UNSTABLE",
    "PB_HIGH",
    "CHASE_RISK",
    "DATA_WEAK",
    "STRUCTURE_DISTRIBUTION_VETO",
}


class StrategySelectionV2Service:
    """Hard-risk + soft-score + scenario-plan selection pipeline.

    This service is deliberately simulation/review-only. It produces candidate
    evidence and plan artifacts; it never calls broker, screen-click, account,
    credential, or live-order code.
    """

    def __init__(self, store: SQLiteStore | None = None, config_path: Path | None = None) -> None:
        self.store = store or SQLiteStore(settings.database_path)
        self.store.init()
        self._sector_exposure = SectorExposureResolver(self.store)
        self.config = self._load_config(config_path or CONFIG_PATH)

    def run(
        self,
        *,
        mode: str = "balanced",
        limit: int = 200,
        write_artifacts: bool = False,
        as_of_date: str | None = None,
    ) -> dict[str, Any]:
        mode = mode if mode in {"strict", "balanced", "exploratory"} else "balanced"
        run_date = as_of_date or date.today().isoformat()
        rows = self._candidate_rows(
            limit=max(1, min(int(limit), 500)),
            as_of_date=run_date,
            strict_point_in_time=as_of_date is not None,
        )
        public_opinion_context = self._public_opinion_context(as_of_date=run_date)
        active_rows, data_gap_rows = self._split_rows_by_market_basis(
            rows,
            as_of_date=run_date,
        )
        candidates = [
            self._evaluate_candidate(
                row,
                run_date=run_date,
                mode=mode,
                public_opinion_context=public_opinion_context,
            )
            for row in active_rows
        ]
        candidates.sort(key=lambda item: item["final_score"], reverse=True)
        data_gap_candidates = [
            self._data_gap_candidate(row, run_date=run_date)
            for row in data_gap_rows
        ]

        strict_cap = int(self.config["mode_defaults"]["strict"].get("max_buy_plan_count", 3))
        sim_count = 0
        for candidate in candidates:
            if candidate["plan_type"] != "SIM_BUY_PLAN":
                continue
            sim_count += 1
            if sim_count > strict_cap:
                candidate["plan_type"] = "WAIT_PULLBACK_PLAN"
                candidate["final_action"] = "WAIT_PULLBACK_PLAN"
                candidate["reasons"].append("Strict mode daily simulated-buy cap reached; downgraded to wait plan.")

        buckets = {bucket: [] for bucket in set(PLAN_BUCKETS.values())}
        for candidate in candidates:
            buckets[PLAN_BUCKETS.get(candidate["plan_type"], "rejected_candidates")].append(candidate)

        diagnostics = self._diagnostics(
            candidates,
            run_date,
            data_gap_candidates=data_gap_candidates,
        )
        result = {
            "status": "completed",
            "schema_version": "strategy_selection_v2.1",
            "date": run_date,
            "mode": mode,
            "source": (
                "candidate_lifecycle+stock_profiles+auto_discovered_candidates+"
                "potential_search_items+candidate_scores+daily_bar_cache+realtime_market_events+"
                "public_opinion_sector_signals"
            ),
            "config_version": self.config.get("version", "1.0"),
            "safety": {
                "simulate_only": True,
                "allow_live_order": False,
                "execution_allowed": False if mode == "exploratory" else True,
                "live_trading_enabled": False,
                "requires_human_review": True,
            },
            "summary": {
                "candidate_count": len(candidates),
                "data_gap_count": len(data_gap_candidates),
                "strict_buy_plan_count": len(buckets["strict_buy_plans"]),
                "wait_pullback_plan_count": len(buckets["wait_pullback_plans"]),
                "wait_breakout_plan_count": len(buckets["wait_breakout_plans"]),
                "watch_only_count": len(buckets["watch_only_candidates"]),
                "reject_count": len(buckets["rejected_candidates"]),
                "risk_alert_count": len(buckets["risk_alerts"]),
                "top_blocking_reasons": diagnostics["top_blocking_reasons"],
                "recommendation": diagnostics["recommendation"],
            },
            "strict_buy_plans": buckets["strict_buy_plans"],
            "wait_pullback_plans": buckets["wait_pullback_plans"],
            "wait_breakout_plans": buckets["wait_breakout_plans"],
            "watch_only_candidates": buckets["watch_only_candidates"],
            "rejected_candidates": buckets["rejected_candidates"],
            "risk_alerts": buckets["risk_alerts"],
            "daily_candidate_snapshot": candidates,
            "data_gap_candidates": data_gap_candidates,
            "filter_diagnostics": diagnostics,
            "public_opinion_context": public_opinion_context,
            "daily_summary_md": self._daily_summary(diagnostics),
        }
        if write_artifacts:
            result["artifact_dir"] = str(self.write_artifacts(result))
        return result

    def write_artifacts(self, result: dict[str, Any]) -> Path:
        out_dir = ARTIFACT_ROOT / str(result["date"])
        out_dir.mkdir(parents=True, exist_ok=True)
        self._write_jsonl(out_dir / "daily_candidate_snapshot.jsonl", result["daily_candidate_snapshot"])
        self._write_json(out_dir / "strict_buy_plans.json", result["strict_buy_plans"])
        self._write_json(out_dir / "wait_pullback_plans.json", result["wait_pullback_plans"])
        self._write_json(out_dir / "wait_breakout_plans.json", result["wait_breakout_plans"])
        self._write_jsonl(out_dir / "watch_only_candidates.jsonl", result["watch_only_candidates"])
        self._write_jsonl(out_dir / "rejected_candidates.jsonl", result["rejected_candidates"])
        self._write_jsonl(out_dir / "data_gap_candidates.jsonl", result.get("data_gap_candidates", []))
        self._write_json(out_dir / "filter_diagnostics.json", result["filter_diagnostics"])
        self._write_jsonl(out_dir / "risk_alerts.jsonl", result["risk_alerts"])
        (out_dir / "daily_summary.md").write_text(result["daily_summary_md"], encoding="utf-8")
        return out_dir

    def candidate_universe(
        self,
        limit: int = 30,
        as_of_date: str | None = None,
    ) -> list[str]:
        rows = self._candidate_rows(
            limit=max(1, min(int(limit), 500)),
            as_of_date=as_of_date or date.today().isoformat(),
            strict_point_in_time=as_of_date is not None,
        )
        return [
            symbol
            for symbol in (self._normalize_symbol(row.get("symbol")) for row in rows)
            if symbol
        ]

    def _candidate_rows(
        self,
        *,
        limit: int,
        as_of_date: str,
        strict_point_in_time: bool,
    ) -> list[dict[str, Any]]:
        by_symbol: dict[str, dict[str, Any]] = {}

        for row in self.store.fetch_all(
            """
            SELECT symbol, name, state, score, rating, risk_level, source, reason, raw_json, updated_at
            FROM candidate_lifecycle
            WHERE date(updated_at) <= date(?)
            ORDER BY updated_at DESC, score DESC
            LIMIT ?
            """,
            (as_of_date, limit),
        ):
            symbol = self._normalize_symbol(row.get("symbol"))
            if not symbol:
                continue
            merged = by_symbol.setdefault(symbol, {"symbol": symbol})
            merged.setdefault("_evidence_sources", []).append("candidate_lifecycle")
            merged.setdefault("_source_scores", {})["candidate_lifecycle"] = self._float(
                row.get("score")
            ) or 0.0
            merged.update({k: v for k, v in row.items() if v is not None})
            merged["symbol"] = symbol
            merged["lifecycle_raw"] = self._json(row.get("raw_json"))

        for row in self.store.fetch_all(
            """
            SELECT symbol, name, current_price, pct_change, five_day_pct,
                   operation_cost_line, sell_target, stop_loss, risk_level,
                   profit_rate, pb, pe_ttm, recent_high, limit_up_count,
                   test_line_count, score, rating, dataset_name, source_file, raw_json
            FROM stock_profiles
            WHERE symbol IS NOT NULL
            ORDER BY score DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        ):
            symbol = self._normalize_symbol(row.get("symbol"))
            if not symbol:
                continue
            profile_raw = self._json(row.get("raw_json"))
            if strict_point_in_time and not self._profile_available_as_of(
                profile_raw,
                as_of_date,
            ):
                continue
            merged = by_symbol.setdefault(symbol, {"symbol": symbol})
            merged.setdefault("_evidence_sources", []).append("stock_profiles")
            merged.setdefault("_source_scores", {})["stock_profiles"] = self._float(
                row.get("score")
            ) or 0.0
            for key, value in row.items():
                if value is not None or key not in merged:
                    merged[key] = value
            merged["symbol"] = symbol
            merged["profile_raw"] = profile_raw

        for row in self.store.fetch_all(
            """
            SELECT adc.symbol, adc.name, adc.trade_date, adc.current_price,
                   adc.pct_change, adc.turnover_rate, adc.volume, adc.amount,
                   adc.priority, adc.discovery_type, adc.source,
                   adc.reasons_json, adc.raw_json, adc.created_at
            FROM auto_discovered_candidates adc
            JOIN (
                SELECT symbol, MAX(id) AS latest_id
                FROM auto_discovered_candidates
                WHERE symbol IS NOT NULL
                  AND date(created_at) <= date(?)
                  AND (
                      trade_date IS NULL
                      OR date(trade_date) <= date(?)
                  )
                GROUP BY symbol
            ) latest ON latest.latest_id = adc.id
            ORDER BY adc.id DESC
            LIMIT ?
            """,
            (as_of_date, as_of_date, limit),
        ):
            symbol = self._normalize_symbol(row.get("symbol"))
            if not symbol:
                continue
            merged = by_symbol.setdefault(symbol, {"symbol": symbol})
            merged.setdefault("_evidence_sources", []).append("auto_discovered_candidates")
            merged.setdefault("_source_scores", {})["auto_discovered_candidates"] = self._float(
                row.get("priority")
            ) or 0.0
            merged.update({k: v for k, v in row.items() if v is not None})
            merged["symbol"] = symbol
            merged["auto_discovery"] = {
                "discovery_type": row.get("discovery_type"),
                "priority": row.get("priority"),
                "reasons": self._json(row.get("reasons_json"), default=[]),
                "source": row.get("source"),
                "created_at": row.get("created_at"),
            }

        for row in self.store.fetch_all(
            """
            SELECT psi.symbol, psi.name, psi.current_price, psi.pct_change,
                   psi.turnover_rate, psi.amount, psi.lifecycle_state AS state,
                   psi.potential_score AS score, psi.source, psi.reasons_json,
                   psi.components_json, psi.raw_json, psi.created_at
            FROM potential_search_items psi
            JOIN (
                SELECT symbol, MAX(id) AS latest_id
                FROM potential_search_items
                WHERE symbol IS NOT NULL
                  AND date(created_at) <= date(?)
                GROUP BY symbol
            ) latest ON latest.latest_id = psi.id
            ORDER BY psi.potential_score DESC, psi.id DESC
            LIMIT ?
            """,
            (as_of_date, limit),
        ):
            symbol = self._normalize_symbol(row.get("symbol"))
            if not symbol:
                continue
            merged = by_symbol.setdefault(symbol, {"symbol": symbol})
            merged.setdefault("_evidence_sources", []).append("potential_search_items")
            merged.setdefault("_source_scores", {})["potential_search_items"] = self._float(
                row.get("score")
            ) or 0.0
            for key, value in row.items():
                if value is not None:
                    merged[key] = value
            merged["symbol"] = symbol
            merged["potential_search"] = {
                "score": row.get("score"),
                "reasons": self._json(row.get("reasons_json"), default=[]),
                "components": self._json(row.get("components_json"), default={}),
                "source": row.get("source"),
                "created_at": row.get("created_at"),
            }
            raw = self._json(row.get("raw_json"))
            if raw:
                merged.setdefault("potential_raw", raw)

        for row in self.store.fetch_all(
            """
            SELECT cs.symbol, cs.name, cs.total_score AS score, cs.rating,
                   cs.state, cs.source, cs.reasons_json, cs.components_json,
                   cs.raw_json, cs.created_at
            FROM candidate_scores cs
            JOIN (
                SELECT symbol, MAX(id) AS latest_id
                FROM candidate_scores
                WHERE symbol IS NOT NULL
                  AND date(created_at) <= date(?)
                GROUP BY symbol
            ) latest ON latest.latest_id = cs.id
            ORDER BY cs.total_score DESC, cs.id DESC
            LIMIT ?
            """,
            (as_of_date, limit),
        ):
            symbol = self._normalize_symbol(row.get("symbol"))
            if not symbol:
                continue
            merged = by_symbol.setdefault(symbol, {"symbol": symbol})
            merged.setdefault("_evidence_sources", []).append("candidate_scores")
            merged.setdefault("_source_scores", {})["candidate_scores"] = self._float(
                row.get("score")
            ) or 0.0
            for key, value in row.items():
                if value is not None and (key not in merged or merged.get(key) is None):
                    merged[key] = value
            merged["symbol"] = symbol
            merged["score_evidence"] = {
                "score": row.get("score"),
                "rating": row.get("rating"),
                "state": row.get("state"),
                "reasons": self._json(row.get("reasons_json"), default=[]),
                "components": self._json(row.get("components_json"), default={}),
                "source": row.get("source"),
                "created_at": row.get("created_at"),
            }
            raw = self._json(row.get("raw_json"))
            if raw:
                merged.setdefault("score_raw", raw)

        rows = list(by_symbol.values())
        has_real_evidence = any(not self._unit_test_only(row) for row in rows)
        if has_real_evidence:
            rows = [row for row in rows if not self._unit_test_only(row)]
        for row in rows:
            row["_fixture_only"] = self._unit_test_only(row)
            source_scores = row.pop("_source_scores", {})
            row["universe_rank_score"] = max(
                (float(value or 0) for value in source_scores.values()),
                default=0.0,
            )
            row["universe_rank_sources"] = source_scores
            row["evidence_sources"] = list(dict.fromkeys(row.pop("_evidence_sources", [])))
        rows.sort(
            key=lambda row: (
                float(row.get("universe_rank_score") or 0),
                str(row.get("updated_at") or row.get("created_at") or ""),
                len(row.get("evidence_sources") or []),
                str(row.get("symbol") or ""),
            ),
            reverse=True,
        )
        return rows[:limit]

    def _split_rows_by_market_basis(
        self,
        rows: list[dict[str, Any]],
        *,
        as_of_date: str,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        symbols = [
            symbol
            for symbol in (self._normalize_symbol(row.get("symbol")) for row in rows)
            if symbol
        ]
        bar_symbols = self._symbols_with_daily_bars(symbols, as_of_date=as_of_date)
        realtime_symbols = self._symbols_with_realtime_price(
            symbols,
            as_of_date=as_of_date,
        )
        active: list[dict[str, Any]] = []
        data_gap: list[dict[str, Any]] = []
        for row in rows:
            symbol = self._normalize_symbol(row.get("symbol"))
            price = self._float(row.get("current_price") or row.get("price"))
            has_market_basis = bool(
                price
                or (symbol and symbol in bar_symbols)
                or (symbol and symbol in realtime_symbols)
            )
            if has_market_basis:
                active.append(row)
            else:
                gap_row = dict(row)
                gap_row["data_gap_reason"] = "missing_price_and_daily_bar_cache"
                data_gap.append(gap_row)
        return active, data_gap

    def _symbols_with_daily_bars(
        self,
        symbols: list[str],
        *,
        as_of_date: str,
    ) -> set[str]:
        unique = sorted(set(symbols))
        if not unique:
            return set()
        placeholders = ",".join("?" for _ in unique)
        rows = self.store.fetch_all(
            f"""
            SELECT DISTINCT symbol
            FROM daily_bar_cache
            WHERE symbol IN ({placeholders})
              AND trade_date != 'ERROR'
              AND date(trade_date) <= date(?)
              AND close IS NOT NULL
            """,
            (*unique, as_of_date),
        )
        return {str(row.get("symbol")) for row in rows if row.get("symbol")}

    def _symbols_with_realtime_price(
        self,
        symbols: list[str],
        *,
        as_of_date: str,
    ) -> set[str]:
        unique = sorted(set(symbols))
        if not unique:
            return set()
        placeholders = ",".join("?" for _ in unique)
        rows = self.store.fetch_all(
            f"""
            SELECT symbol
            FROM realtime_market_events
            WHERE symbol IN ({placeholders})
              AND price IS NOT NULL
              AND price > 0
              AND substr(event_ts, 1, 10) <= ?
            GROUP BY symbol
            """,
            (*unique, as_of_date),
        )
        return {str(row.get("symbol")) for row in rows if row.get("symbol")}

    def _data_gap_candidate(self, row: dict[str, Any], *, run_date: str) -> dict[str, Any]:
        symbol = self._normalize_symbol(row.get("symbol")) or str(row.get("symbol") or "")
        code = symbol[2:] if len(symbol) == 8 else symbol
        score_evidence = row.get("score_evidence") or {}
        return {
            "date": run_date,
            "symbol": symbol,
            "code": code,
            "name": row.get("name"),
            "plan_type": "DATA_GAP_SKIPPED",
            "final_action": "REFRESH_MARKET_DATA_BEFORE_RANKING",
            "data_gap_reason": row.get("data_gap_reason") or "missing_price_and_daily_bar_cache",
            "evidence_sources": list(row.get("evidence_sources") or []),
            "source": row.get("source") or score_evidence.get("source"),
            "score": row.get("score") or score_evidence.get("score"),
            "rating": row.get("rating") or score_evidence.get("rating"),
            "state": row.get("state") or score_evidence.get("state"),
            "created_at": row.get("created_at") or score_evidence.get("created_at"),
            "reasons": [
                "Skipped from active ranking because no price, realtime quote, or daily_bar_cache close was available.",
                "Refresh daily_bar_cache/realtime quote before using this candidate for judgment or training.",
                "simulate_only=true; allow_live_order=false",
            ],
            "simulate_only": True,
            "allow_live_order": False,
            "execution_allowed": False,
            "for_training_only": True,
            "review_only": True,
        }

    def _unit_test_only(self, row: dict[str, Any]) -> bool:
        sources = set(row.get("_evidence_sources") or [])
        if sources != {"stock_profiles"}:
            return False
        dataset_name = str(row.get("dataset_name") or "").lower()
        source_file = str(row.get("source_file") or "").lower()
        return dataset_name == "unit_test" or source_file.startswith("test_")

    @staticmethod
    def _profile_available_as_of(
        raw: dict[str, Any],
        as_of_date: str,
    ) -> bool:
        """Reject mutable profiles that cannot prove when they were known."""
        snapshot_value = next(
            (
                raw.get(key)
                for key in ("as_of_date", "snapshot_date", "trade_date", "data_date")
                if raw.get(key)
            ),
            None,
        )
        if not snapshot_value:
            return False
        try:
            snapshot_date = date.fromisoformat(str(snapshot_value)[:10])
            target_date = date.fromisoformat(str(as_of_date)[:10])
        except ValueError:
            return False
        return snapshot_date <= target_date

    @staticmethod
    def _fixture_market_data_allowed(row: dict[str, Any]) -> bool:
        return row.get("_fixture_only") is True

    def _evaluate_candidate(
        self,
        row: dict[str, Any],
        *,
        run_date: str,
        mode: str,
        public_opinion_context: dict[str, Any],
    ) -> dict[str, Any]:
        symbol = self._normalize_symbol(row.get("symbol")) or str(row.get("symbol") or "")
        bars = self._daily_bars(symbol, as_of_date=run_date)
        realtime = self._latest_realtime(symbol, as_of_date=run_date)
        features = self._features(
            row,
            bars,
            realtime,
            public_opinion_context,
            run_date=run_date,
        )
        hard_blocks = self._hard_blocks(row, features)
        position_class = self._position_class(features)
        tailwind = features.get("public_opinion_tailwind") or {}
        sector_probability = None
        if tailwind.get("matched"):
            sector_probability = max(
                0.0,
                min(1.0, float(tailwind.get("heat_score") or 0.0) / 100.0),
            )
        features["structure_signal"] = ObservableStructureScorer.score(
            features,
            position_class=position_class,
            sector_probability=sector_probability,
        ).as_dict()
        strategies = self._strategy_candidates(row, features, position_class)
        base_components = self._base_components(row, features, position_class, strategies)
        base_score = round(sum(base_components.values()), 2)
        risk_flags, risk_penalty = self._risk_flags(row, features, position_class)
        final_score = round(max(0.0, min(100.0, base_score - risk_penalty)), 2)
        plan_type = self._plan_type(
            mode=mode,
            hard_blocks=hard_blocks,
            final_score=final_score,
            risk_penalty=risk_penalty,
            buy_maturity=base_components["buy_maturity"],
            risk_flags=risk_flags,
            position_class=position_class,
            strategies=strategies,
            features=features,
        )
        strategy_id = strategies[0] if strategies else "UNCLASSIFIED"
        plan = self._plan_payload(
            row=row,
            run_date=run_date,
            symbol=symbol,
            strategy_id=strategy_id,
            strategies=strategies,
            position_class=position_class,
            base_components=base_components,
            base_score=base_score,
            risk_penalty=risk_penalty,
            final_score=final_score,
            risk_flags=risk_flags,
            hard_blocks=hard_blocks,
            plan_type=plan_type,
            features=features,
        )
        return plan

    def _features(
        self,
        row: dict[str, Any],
        bars: list[dict[str, Any]],
        realtime: dict[str, Any] | None,
        public_opinion_context: dict[str, Any],
        *,
        run_date: str,
    ) -> dict[str, Any]:
        closes = [self._float(bar.get("close")) for bar in bars]
        highs = [self._float(bar.get("high")) for bar in bars]
        lows = [self._float(bar.get("low")) for bar in bars]
        volumes = [self._float(bar.get("volume")) for bar in bars]
        amounts = [self._float(bar.get("amount")) for bar in bars]
        closes = [value for value in closes if value is not None]
        highs = [value for value in highs if value is not None]
        lows = [value for value in lows if value is not None]
        volumes = [value for value in volumes if value is not None]
        amounts = [value for value in amounts if value is not None]

        realtime_freshness = self._realtime_freshness(realtime, run_date)
        usable_realtime = realtime if realtime_freshness["fresh"] else None
        realtime_price = self._float((usable_realtime or {}).get("price"))
        latest_bar = bars[-1] if bars else {}
        row_snapshot_freshness = self._candidate_snapshot_freshness(row, run_date)
        row_snapshot_fresh = row_snapshot_freshness["fresh"]
        row_snapshot_price = (
            self._float(row.get("current_price") or row.get("price"))
            if row_snapshot_fresh
            else None
        )
        price = (
            realtime_price
            or row_snapshot_price
            or self._float(latest_bar.get("close"))
            or self._float(row.get("current_price"))
            or self._float(row.get("price"))
        )
        pct_change = (
            self._float(row.get("pct_change"))
            if row_snapshot_fresh
            else self._pct_change_from_bars(bars) or self._float(row.get("pct_change"))
        )
        price_source = (
            "fresh_realtime"
            if realtime_price is not None
            else "same_day_candidate_snapshot"
            if row_snapshot_price is not None
            else "daily_bar_cache"
            if latest_bar
            else "stale_profile_fallback"
        )
        high_250 = max(highs[-250:]) if highs else None
        low_250 = min(lows[-250:]) if lows else None
        high_500 = max(highs[-500:]) if highs else high_250
        low_500 = min(lows[-500:]) if lows else low_250
        percentile_250 = self._percentile(price, low_250, high_250)
        percentile_500 = self._percentile(price, low_500, high_500)
        drawdown_250 = self._pct_down(price, high_250)
        bounce_250 = self._pct_up(price, low_250)
        ma5 = self._ma(closes, 5)
        ma10 = self._ma(closes, 10)
        ma20 = self._ma(closes, 20)
        ma5_prev = self._ma(closes[:-1], 5)
        ma10_prev = self._ma(closes[:-1], 10)
        ma20_prev = self._ma(closes[:-1], 20)
        volume_ratio = self._ratio(volumes[-1] if volumes else None, mean(volumes[-6:-1]) if len(volumes) >= 6 else None)
        avg_amount_20 = mean(amounts[-20:]) if amounts else None
        latest_high = self._float(latest_bar.get("high"))
        latest_low = self._float(latest_bar.get("low"))
        latest_open = self._float(latest_bar.get("open"))
        latest_close = self._float(latest_bar.get("close")) or price
        candle_range = (latest_high - latest_low) if latest_high and latest_low else None
        upper_shadow_ratio = None
        if candle_range and candle_range > 0 and latest_high and latest_open and latest_close:
            upper_shadow_ratio = (latest_high - max(latest_open, latest_close)) / candle_range
        recent_high_breakout = False
        if price and len(highs) >= 21:
            recent_high_breakout = price >= max(highs[-21:-1]) * 0.995
        discovery = row.get("auto_discovery") or row.get("lifecycle_raw", {}).get("auto_discovery") or {}
        discovery_type = discovery.get("discovery_type") or row.get("discovery_type") or row.get("rating")
        is_limit_like = discovery_type in {"limit_up", "limit_up_priority"} or (pct_change is not None and pct_change >= 9.5)
        is_near_limit = discovery_type in {"near_limit_up", "near_limit_up_priority"} or (pct_change is not None and pct_change >= 7.0)
        raw_profile = row.get("profile_raw") or row.get("lifecycle_raw") or {}
        market_cap = self._float(
            row.get("market_cap_billion")
            or row.get("market_cap")
            or raw_profile.get("market_cap_billion")
            or raw_profile.get("market_cap")
        )
        if market_cap and market_cap > 10000:
            market_cap = round(market_cap / 100000000, 2)
        pb = self._float(row.get("pb"))
        cost_price = self._float(row.get("avg_cost") or raw_profile.get("avg_cost"))
        if cost_price is None and len(closes) >= 20:
            cost_price = mean(closes[-60:] if len(closes) >= 60 else closes)
        operation_cost_line = self._float(row.get("operation_cost_line"))
        if operation_cost_line is None and cost_price:
            operation_cost_line = cost_price * 1.3
        target_price = self._float(row.get("sell_target"))
        if target_price is None and cost_price:
            target_price = cost_price * 2.6
        cost_line_near = bool(
            price
            and operation_cost_line
            and abs(price - operation_cost_line) / operation_cost_line <= 0.08
        )
        fast_drawdown_120 = self._pct_down(price, max(highs[-120:]) if highs else None)
        a_kill_repair = bool(
            fast_drawdown_120 is not None
            and fast_drawdown_120 >= 30
            and percentile_250 is not None
            and percentile_250 <= 55
        )
        public_opinion_tailwind = self._candidate_public_opinion_tailwind(
            row,
            public_opinion_context,
            as_of_date=run_date,
        )
        market_data = self._market_data_freshness(
            bars,
            run_date,
            fixture=self._fixture_market_data_allowed(row),
        )
        return {
            "bars_count": len(bars),
            "price": price,
            "price_source": price_source,
            "pct_change": pct_change,
            "pb": pb,
            "market_cap_billion": market_cap,
            "price_percentile_250d": percentile_250,
            "price_percentile_500d": percentile_500,
            "drawdown_from_250d_high": drawdown_250,
            "bounce_from_250d_low": bounce_250,
            "above_ma5": bool(price and ma5 and price >= ma5),
            "above_ma10": bool(price and ma10 and price >= ma10),
            "above_ma20": bool(price and ma20 and price >= ma20),
            "ma5_slope": self._pct_change(ma5, ma5_prev),
            "ma10_slope": self._pct_change(ma10, ma10_prev),
            "ma20_slope": self._pct_change(ma20, ma20_prev),
            "recent_high_breakout": recent_high_breakout,
            "volume_ratio": volume_ratio,
            "avg_amount_20": avg_amount_20,
            "upper_shadow_ratio": upper_shadow_ratio,
            "is_limit_like": is_limit_like,
            "is_near_limit": is_near_limit,
            "cost_price": cost_price,
            "operation_cost_line": operation_cost_line,
            "target_price": target_price,
            "cost_line_near": cost_line_near,
            "a_kill_repair": a_kill_repair,
            "latest_realtime": usable_realtime,
            "realtime_freshness": realtime_freshness,
            "candidate_snapshot_freshness": row_snapshot_freshness,
            "public_opinion_tailwind": public_opinion_tailwind,
            "data_quality": self._data_quality(bars, usable_realtime, price),
            "market_data": market_data,
        }

    def _hard_blocks(self, row: dict[str, Any], features: dict[str, Any]) -> list[str]:
        name = str(row.get("name") or "")
        risk = str(row.get("risk_level") or "")
        blocks: list[str] = []
        if "ST" in name.upper() or "*ST" in name.upper():
            blocks.append("HF001_ST")
        if "退市" in name or "退市" in risk:
            blocks.append("HF002_DELISTING_RISK")
        if "停牌" in risk:
            blocks.append("HF003_SUSPENDED")
        if not features.get("price") or features["price"] <= 0:
            blocks.append("HF004_INVALID_DATA")
        if features.get("pct_change") is not None and features["pct_change"] <= -9.8:
            blocks.append("HF006_UNTRADEABLE_LIMIT_DOWN")
        if not (features.get("market_data") or {}).get("fresh", False):
            blocks.append("HF007_STALE_MARKET_DATA")
        return blocks

    def _position_class(self, features: dict[str, Any]) -> str:
        percentile = features.get("price_percentile_250d")
        volume_ratio = features.get("volume_ratio") or 0
        upper_shadow = features.get("upper_shadow_ratio") or 0
        if features.get("a_kill_repair"):
            return "A_KILL_REPAIR"
        if features.get("cost_line_near"):
            return "COST_LINE_NEAR"
        if percentile is None:
            return "DATA_WEAK"
        if percentile <= 35:
            if features.get("above_ma5") or features.get("is_limit_like") or volume_ratio >= 1.2:
                return "LOW_BASE"
            return "WEAK_LOW"
        if percentile <= 65:
            return "MID_RECOVERY"
        if upper_shadow >= 0.45 and volume_ratio >= 2.0:
            return "HIGH_DISTRIBUTION"
        if features.get("recent_high_breakout") and (features.get("above_ma5") or features.get("above_ma10")):
            return "HIGH_BREAKOUT"
        return "HIGH_DISTRIBUTION" if volume_ratio >= 3.5 else "MID_RECOVERY"

    def _strategy_candidates(
        self,
        row: dict[str, Any],
        features: dict[str, Any],
        position_class: str,
    ) -> list[str]:
        strategies: list[str] = []
        market_cap = features.get("market_cap_billion")
        if position_class == "LOW_BASE" and features.get("is_near_limit"):
            strategies.append("STRATEGY_003_A")
        if position_class in {"MID_RECOVERY", "HIGH_BREAKOUT"}:
            strategies.append("STRATEGY_003_B")
        if position_class == "A_KILL_REPAIR":
            strategies.append("STRATEGY_003_C")
        if position_class == "COST_LINE_NEAR":
            strategies.append("STRATEGY_004")
        if market_cap and market_cap >= 200:
            strategies.append("STRATEGY_005")
        if not strategies:
            strategies.append("STRATEGY_003_B" if features.get("is_near_limit") else "WATCH_REVIEW")
        return strategies

    def _base_components(
        self,
        row: dict[str, Any],
        features: dict[str, Any],
        position_class: str,
        strategies: list[str],
    ) -> dict[str, float]:
        weights = self.config["score_weights"]
        pct_change = features.get("pct_change") or 0
        volume_ratio = features.get("volume_ratio") or 0
        avg_amount = features.get("avg_amount_20") or 0
        market_cap = features.get("market_cap_billion")
        pb = features.get("pb")
        components = {key: 0.0 for key in weights}

        public_opinion_tailwind = features.get("public_opinion_tailwind") or {}
        public_opinion_bonus = 0.0
        if public_opinion_tailwind.get("matched"):
            if (
                int(public_opinion_tailwind.get("fresh_positive_count") or 0) > 0
                and int(public_opinion_tailwind.get("fresh_risk_count") or 0) == 0
                and (
                    int(
                        public_opinion_tailwind.get(
                            "fresh_official_positive_policy_count"
                        )
                        or 0
                    )
                    >= 1
                    or int(public_opinion_tailwind.get("fresh_positive_source_count") or 0)
                    >= 2
                )
                and public_opinion_tailwind.get("suggested_action")
                not in {"risk_review_only", "mixed_review_only"}
            ):
                public_opinion_bonus = min(4.0, float(public_opinion_tailwind.get("heat_score") or 0) / 12.0)
        components["market_sector"] = min(
            weights["market_sector"],
            3.0 + (2.0 if "STRATEGY_005" in strategies else 0.0) + public_opinion_bonus,
        )
        if features.get("is_limit_like"):
            components["limit_up_quality"] += 8.0
        elif features.get("is_near_limit") or pct_change >= 5:
            components["limit_up_quality"] += 5.0
        if volume_ratio and 1.0 <= volume_ratio <= 3.0:
            components["limit_up_quality"] += 2.0
        if position_class == "LOW_BASE":
            components["limit_up_quality"] += 2.0

        components["price_position"] = {
            "LOW_BASE": 12.0,
            "WEAK_LOW": 4.0,
            "MID_RECOVERY": 8.0,
            "HIGH_BREAKOUT": 7.0,
            "HIGH_DISTRIBUTION": 2.0,
            "A_KILL_REPAIR": 5.0,
            "COST_LINE_NEAR": 8.0,
            "DATA_WEAK": 1.0,
        }.get(position_class, 4.0)

        if volume_ratio and 0.8 <= volume_ratio <= 3.5:
            components["volume_price_health"] += 5.0
        if avg_amount >= self.config["hard_filters"]["min_20d_avg_amount"]:
            components["volume_price_health"] += 4.0
        if features.get("is_near_limit") and volume_ratio <= 5:
            components["volume_price_health"] += 3.0
        if position_class not in {"HIGH_DISTRIBUTION", "WEAK_LOW"}:
            components["volume_price_health"] += 2.0

        for key in ("above_ma5", "above_ma10", "above_ma20"):
            if features.get(key):
                components["trend_ma"] += 2.0
        for key in ("ma5_slope", "ma10_slope"):
            if (features.get(key) or 0) > 0:
                components["trend_ma"] += 2.0

        if position_class == "LOW_BASE" and features.get("is_limit_like"):
            components["buy_maturity"] = 8.0
        elif position_class == "HIGH_BREAKOUT":
            components["buy_maturity"] = 5.0
        elif position_class == "COST_LINE_NEAR":
            components["buy_maturity"] = 4.0
        elif position_class == "A_KILL_REPAIR":
            components["buy_maturity"] = 3.0
        elif position_class == "MID_RECOVERY":
            components["buy_maturity"] = 5.0
        else:
            components["buy_maturity"] = 2.0

        if market_cap is not None:
            if 50 <= market_cap <= 100:
                components["market_cap_liquidity"] += 3.0
            elif 100 < market_cap <= 200:
                components["market_cap_liquidity"] += 2.0
            elif market_cap > 200:
                components["market_cap_liquidity"] += 1.0
        if avg_amount >= self.config["hard_filters"]["min_20d_avg_amount"]:
            components["market_cap_liquidity"] += 3.0

        if pb is None:
            components["valuation_finance"] += 1.0
        elif 2 <= pb <= 5:
            components["valuation_finance"] += 4.0
        elif 5 < pb <= 6:
            components["valuation_finance"] += 2.0

        if features.get("cost_line_near"):
            components["cost_chip_logic"] += 4.0
        if features.get("target_price") and features.get("price") and features["target_price"] > features["price"] * 1.2:
            components["cost_chip_logic"] += 2.0
        if position_class in {"LOW_BASE", "COST_LINE_NEAR", "MID_RECOVERY"}:
            components["cost_chip_logic"] += 1.0

        if features.get("bars_count", 0) >= 60:
            components["data_explainability"] += 2.0
        if features.get("price") and row.get("name"):
            components["data_explainability"] += 1.0
        if features.get("data_quality") != "missing_price":
            components["data_explainability"] += 1.0

        structure = features.get("structure_signal") or {}
        if float(structure.get("confidence") or 0.0) >= 0.45:
            if structure.get("distribution_veto"):
                components["buy_maturity"] = min(components["buy_maturity"], 1.0)
            else:
                components["buy_maturity"] += min(
                    3.0,
                    float(structure.get("pre_markup_probability") or 0.0) * 3.0,
                )

        return {
            key: round(min(float(weights[key]), value), 2)
            for key, value in components.items()
        }

    def _public_opinion_context(self, *, as_of_date: str) -> dict[str, Any]:
        try:
            service = CodexPublicOpinionService(store=self.store)
            sector_forecasts = self._sector_forecasts_as_of(as_of_date)
            captures = self.store.fetch_all(
                """
                SELECT id, status, item_count, sector_count, summary_json,
                       review_only, simulation_only, live_trading_enabled,
                       created_at, completed_at
                FROM public_opinion_runs
                WHERE date(created_at) <= date(?)
                  AND date(COALESCE(completed_at, created_at)) <= date(?)
                ORDER BY id DESC
                LIMIT 24
                """,
                (as_of_date, as_of_date),
            )
            if not captures:
                return {
                    "status": "completed" if sector_forecasts else "empty",
                    "as_of_date": as_of_date,
                    "top_sectors": list(sector_forecasts),
                    "sector_forecasts": sector_forecasts,
                    "review_only": True,
                    "simulation_only": True,
                    "live_trading_enabled": settings.enable_live_trading,
                }
            latest_capture = captures[0]
            usable = [
                row
                for row in captures
                if str(row.get("status") or "") in {"completed", "partial"}
                and int(row.get("item_count") or 0) > 0
            ]
            selected = usable[0] if usable else latest_capture
            rows = self.store.fetch_all(
                """
                SELECT *
                FROM public_opinion_sector_signals
                WHERE run_id = ?
                  AND date(created_at) <= date(?)
                ORDER BY heat_score DESC, item_count DESC, sector ASC
                LIMIT 8
                """,
                (selected["id"], as_of_date),
            )
            sectors = [service._hydrate_sector_signal(row) for row in rows]
            by_sector = {str(item.get("sector")): item for item in sectors}
            for forecast in sector_forecasts:
                existing = by_sector.get(str(forecast.get("sector")))
                if existing is None:
                    sectors.append(dict(forecast))
                    continue
                existing.update(
                    {
                        "sector_forecast": True,
                        "forecast_confidence": forecast.get("forecast_confidence"),
                        "forecast_direction": forecast.get("forecast_direction"),
                        "forecast_horizon": forecast.get("forecast_horizon"),
                        "forecast_decision_id": forecast.get("forecast_decision_id"),
                    }
                )
            run_status = str(selected.get("status") or "empty")
            return {
                "status": run_status,
                "run_status": run_status,
                "freshness_status": "available_as_of_date",
                "as_of_date": as_of_date,
                "run_id": selected.get("id"),
                "latest_capture_run_id": latest_capture.get("id"),
                "latest_capture_status": latest_capture.get("status"),
                "selection_reason": "latest_usable_run_available_as_of_date",
                "item_count": selected.get("item_count"),
                "sector_count": selected.get("sector_count"),
                "summary": self._json(selected.get("summary_json")),
                "top_sectors": sectors if (usable or sector_forecasts) else [],
                "sector_forecasts": sector_forecasts,
                "review_only": bool(selected.get("review_only")),
                "simulation_only": bool(selected.get("simulation_only")),
                "live_trading_enabled": bool(selected.get("live_trading_enabled")),
                "created_at": selected.get("created_at"),
                "completed_at": selected.get("completed_at"),
            }
        except Exception as exc:
            return {
                "status": "unavailable",
                "error": str(exc),
                "as_of_date": as_of_date,
                "top_sectors": [],
                "sector_forecasts": [],
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            }

    def _candidate_public_opinion_tailwind(
        self,
        row: dict[str, Any],
        context: dict[str, Any],
        *,
        as_of_date: str,
    ) -> dict[str, Any]:
        sectors = list(context.get("top_sectors") or [])
        if not sectors:
            return {
                "matched": False,
                "context_status": context.get("status", "empty"),
                "top_sector_count": 0,
            }

        text_parts = [
            row.get("symbol"),
            row.get("name"),
            row.get("rating"),
            row.get("risk_level"),
            row.get("source"),
            row.get("reason"),
            row.get("state"),
        ]
        for key in ("profile_raw", "lifecycle_raw", "potential_raw", "score_raw"):
            if row.get(key):
                text_parts.append(json.dumps(row.get(key), ensure_ascii=False, default=str))
        candidate_text = " ".join(str(part or "") for part in text_parts).lower()
        membership_rows = self._sector_exposure.sectors_for(
            self._normalize_symbol(row.get("symbol")) or str(row.get("symbol") or ""),
            as_of=as_of_date,
        )
        membership_sectors = {str(item.get("sector")) for item in membership_rows}

        best: dict[str, Any] | None = None
        best_score = -1.0
        for sector in sectors:
            fresh_item_count = int(sector.get("fresh_item_count") or 0)
            independent_source_count = int(sector.get("independent_source_count") or 0)
            fresh_independent_source_count = int(
                sector.get("fresh_independent_source_count") or 0
            )
            policy_count = int(sector.get("policy_count") or 0)
            official_policy_count = int(sector.get("official_policy_count") or 0)
            fresh_official_policy_count = int(
                sector.get("fresh_official_policy_count") or 0
            )
            sector_forecast = bool(sector.get("sector_forecast"))
            forecast_confidence = float(sector.get("forecast_confidence") or 0.0)
            confidence_ok = (
                fresh_item_count > 0
                and (
                    fresh_independent_source_count >= 2
                    or fresh_official_policy_count >= 1
                )
            ) or (sector_forecast and forecast_confidence >= 0.55)
            if not confidence_ok:
                continue
            keywords = [str(keyword) for keyword in sector.get("keywords") or []]
            matched_keywords = [
                keyword
                for keyword in keywords
                if keyword and self._candidate_keyword_match(candidate_text, keyword)
            ]
            membership_match = str(sector.get("sector")) in membership_sectors
            if membership_match:
                matched_keywords.append(f"sector_membership:{sector.get('sector')}")
            if not matched_keywords:
                continue
            heat_score = float(sector.get("heat_score") or 0)
            score = heat_score + len(matched_keywords) * 5
            if score > best_score:
                best_score = score
                best = {
                    "matched": True,
                    "context_status": context.get("status"),
                    "run_id": context.get("run_id"),
                    "sector": sector.get("sector"),
                    "display_name": sector.get("display_name"),
                    "heat_score": heat_score,
                    "item_count": sector.get("item_count"),
                    "fresh_item_count": fresh_item_count,
                    "independent_source_count": independent_source_count,
                    "fresh_independent_source_count": fresh_independent_source_count,
                    "policy_count": policy_count,
                    "official_policy_count": official_policy_count,
                    "fresh_official_policy_count": fresh_official_policy_count,
                    "fresh_official_positive_policy_count": int(
                        sector.get("fresh_official_positive_policy_count") or 0
                    ),
                    "positive_count": int(sector.get("positive_count") or 0),
                    "risk_count": int(sector.get("risk_count") or 0),
                    "fresh_positive_count": int(sector.get("fresh_positive_count") or 0),
                    "fresh_risk_count": int(sector.get("fresh_risk_count") or 0),
                    "fresh_positive_source_count": int(
                        sector.get("fresh_positive_source_count") or 0
                    ),
                    "suggested_action": sector.get("suggested_action"),
                    "matched_keywords": matched_keywords,
                    "matched_via": (
                        "sector_membership_history" if membership_match else "candidate_text"
                    ),
                    "sector_forecast": sector_forecast,
                    "forecast_confidence": forecast_confidence,
                    "forecast_direction": sector.get("forecast_direction"),
                    "forecast_horizon": sector.get("forecast_horizon"),
                    "sector_memberships": membership_rows,
                    "evidence": list(sector.get("evidence") or [])[:3],
                    "review_only": True,
                    "simulation_only": True,
                    "live_trading_enabled": settings.enable_live_trading,
                }
        if best:
            return best
        return {
            "matched": False,
            "context_status": context.get("status"),
            "run_id": context.get("run_id"),
            "top_sector_count": len(sectors),
            "score_effect": "none_without_candidate_sector_match",
            "confidence_gate": "requires_fresh_and_two_sources_or_official_policy",
            "top_sectors": [
                {
                    "sector": sector.get("sector"),
                    "display_name": sector.get("display_name"),
                    "heat_score": sector.get("heat_score"),
                }
                for sector in sectors[:3]
            ],
        }

    def _sector_forecasts_as_of(self, as_of_date: str) -> list[dict[str, Any]]:
        cutoff = f"{str(as_of_date)[:10]}T23:59:59+08:00"
        forecasts = ForecastLedger(self.store).as_of(
            cutoff,
            scope="sector",
            horizon_days=5,
        )
        rows: list[dict[str, Any]] = []
        for forecast in forecasts:
            features = forecast.features or {}
            sector = forecast.subject
            taxonomy = SECTOR_TAXONOMY.get(sector, {})
            direction = str(features.get("direction") or "neutral")
            confidence = float(forecast.probability or features.get("confidence") or 0.0)
            positive = direction == "positive"
            risk = direction in {"negative", "mixed"}
            rows.append(
                {
                    "sector": sector,
                    "display_name": taxonomy.get("display_name", sector),
                    "keywords": list(taxonomy.get("keywords") or []),
                    "heat_score": round(confidence * 100.0, 4),
                    "item_count": len(features.get("event_ids") or []),
                    "fresh_item_count": len(features.get("event_ids") or []) or 1,
                    "positive_count": 1 if positive else 0,
                    "risk_count": 1 if risk else 0,
                    "fresh_positive_count": 1 if positive else 0,
                    "fresh_risk_count": 1 if risk else 0,
                    "suggested_action": (
                        "sector_watch_review_only" if positive else "risk_review_only"
                    ),
                    "sector_forecast": True,
                    "forecast_confidence": confidence,
                    "forecast_direction": direction,
                    "forecast_horizon": features.get("horizon"),
                    "forecast_decision_id": forecast.decision_id,
                    "evidence": list(forecast.evidence),
                    "review_only": True,
                }
            )
        return rows

    @staticmethod
    def _candidate_keyword_match(candidate_text: str, keyword: str) -> bool:
        normalized = keyword.strip().lower()
        if not normalized:
            return False
        if re.fullmatch(r"[a-z0-9.+-]+", normalized):
            return bool(
                re.search(
                    rf"(?<![a-z0-9]){re.escape(normalized)}(?![a-z0-9])",
                    candidate_text,
                )
            )
        return normalized in candidate_text

    def _risk_flags(
        self,
        row: dict[str, Any],
        features: dict[str, Any],
        position_class: str,
    ) -> tuple[list[str], float]:
        flags: list[str] = []
        penalty = 0.0
        ranges = self.config["risk_penalties"]

        def add(flag: str, weight: float = 0.5) -> None:
            nonlocal penalty
            if flag not in flags:
                flags.append(flag)
            low, high = ranges.get(flag, [4, 8])
            penalty += low + (high - low) * weight

        if features.get("bars_count", 0) < 20:
            add("DATA_WEAK", 0.65)
        if position_class == "HIGH_DISTRIBUTION":
            add("HIGH_DISTRIBUTION", 0.75)
        if (features.get("structure_signal") or {}).get("distribution_veto"):
            add("STRUCTURE_DISTRIBUTION_VETO", 0.85)
        if (features.get("volume_ratio") or 0) >= 5:
            add("VOLUME_ABNORMAL", 0.65)
        if (
            features.get("above_ma5") is False
            and features.get("above_ma10") is False
            and (features.get("ma5_slope") or 0) < 0
        ):
            add("MA_BREAKDOWN", 0.5)
        if features.get("pb") and features["pb"] > 6:
            add("PB_HIGH", 0.45)
        if features.get("market_cap_billion") and features["market_cap_billion"] > 200:
            add("MARKET_CAP_TOO_LARGE", 0.35)
        avg_amount = features.get("avg_amount_20")
        if avg_amount is not None and avg_amount < self.config["hard_filters"]["min_20d_avg_amount"]:
            add("LOW_LIQUIDITY", 0.5)
        if position_class == "A_KILL_REPAIR":
            flags.extend(["A_KILL_REPAIR", "HIGH_VOLATILITY"])
            if not features.get("above_ma20"):
                add("A_KILL_UNSTABLE", 0.5)
        if (
            (features.get("price_percentile_250d") or 0) >= 70
            and (features.get("pct_change") or 0) >= 5
            and position_class != "HIGH_BREAKOUT"
        ):
            add("CHASE_RISK", 0.5)
        public_opinion_tailwind = features.get("public_opinion_tailwind") or {}
        if (
            public_opinion_tailwind.get("matched")
            and public_opinion_tailwind.get("suggested_action")
            in {"risk_review_only", "mixed_review_only"}
        ):
            add("SECTOR_RETREAT", 0.5)
        return list(dict.fromkeys(flags)), round(min(35.0, penalty), 2)

    def _plan_type(
        self,
        *,
        mode: str,
        hard_blocks: list[str],
        final_score: float,
        risk_penalty: float,
        buy_maturity: float,
        risk_flags: list[str],
        position_class: str,
        strategies: list[str],
        features: dict[str, Any],
    ) -> str:
        if hard_blocks:
            return "REJECT_HARD"
        if "HIGH_DISTRIBUTION" in risk_flags:
            return "RISK_ALERT_PLAN"
        if mode == "exploratory":
            return "WATCH_ONLY_PLAN" if final_score >= 35 else "REJECT_SOFT"
        if "STRATEGY_005" in strategies and features.get("market_cap_billion", 0) >= 1000:
            return "SECTOR_BAROMETER"
        if position_class == "COST_LINE_NEAR":
            return "WAIT_BREAKOUT_PLAN" if final_score >= 35 else "WATCH_ONLY_PLAN"
        if position_class == "A_KILL_REPAIR":
            return "WAIT_PULLBACK_PLAN" if final_score >= 50 else "WATCH_ONLY_PLAN"
        threshold = self.config["plan_thresholds"]["SIM_BUY_PLAN"]
        if (
            final_score >= threshold["min_final_score"]
            and risk_penalty <= threshold["max_risk_penalty"]
            and buy_maturity >= threshold["min_buy_maturity_score"]
            and not set(risk_flags).intersection(FORBID_BUY_FLAGS)
        ):
            return "SIM_BUY_PLAN"
        if final_score >= self.config["plan_thresholds"]["WAIT_PULLBACK_PLAN"]["min_final_score"]:
            return "WAIT_PULLBACK_PLAN"
        if final_score >= self.config["plan_thresholds"]["WAIT_BREAKOUT_PLAN"]["min_final_score"]:
            return "WAIT_BREAKOUT_PLAN"
        if final_score >= self.config["plan_thresholds"]["WATCH_ONLY_PLAN"]["min_final_score"]:
            return "WATCH_ONLY_PLAN"
        return "REJECT_SOFT"

    def _plan_payload(
        self,
        *,
        row: dict[str, Any],
        run_date: str,
        symbol: str,
        strategy_id: str,
        strategies: list[str],
        position_class: str,
        base_components: dict[str, float],
        base_score: float,
        risk_penalty: float,
        final_score: float,
        risk_flags: list[str],
        hard_blocks: list[str],
        plan_type: str,
        features: dict[str, Any],
    ) -> dict[str, Any]:
        price = features.get("price") or 0
        stop_loss = self._stop_loss(price, plan_type, position_class)
        take_profit = self._take_profit(price, features)
        code = symbol[2:] if len(symbol) == 8 else symbol
        return {
            "date": run_date,
            "plan_id": f"V2-{run_date.replace('-', '')}-{symbol}",
            "symbol": symbol,
            "code": code,
            "name": row.get("name"),
            "strategy_id": strategy_id,
            "strategy_candidates": strategies,
            "position_class": position_class,
            "raw_signals": self._raw_signals(row, features),
            "plan_type": plan_type,
            "final_action": plan_type,
            "entry_trigger": self._entry_trigger(plan_type, position_class),
            "entry_price_plan": round(float(price), 3) if price else None,
            "stop_loss_plan": stop_loss,
            "take_profit_plan": take_profit,
            "invalid_conditions": self._invalid_conditions(position_class),
            "position_size_level": self._position_size(plan_type, position_class),
            "base_score": base_score,
            "risk_penalty": risk_penalty,
            "final_score": final_score,
            "score_components": base_components,
            "risk_flags": risk_flags,
            "hard_blocks": hard_blocks,
            "rejected_by": hard_blocks or risk_flags,
            "would_have_plan_type": plan_type if plan_type.startswith("WAIT") else None,
            "simulate_only": True,
            "allow_live_order": False,
            "execution_allowed": False,
            "for_training_only": plan_type in {"WATCH_ONLY_PLAN", "REJECT_SOFT", "SECTOR_BAROMETER"},
            "evidence": self._evidence(features, position_class),
            "features": features,
            "reasons": self._reasons(plan_type, final_score, risk_penalty, risk_flags, hard_blocks, position_class),
            "future_return_1d": None,
            "future_return_3d": None,
            "future_return_5d": None,
            "future_return_10d": None,
            "future_return_20d": None,
            "max_favorable_excursion": None,
            "max_adverse_excursion": None,
            "review_label": None,
        }

    def _diagnostics(
        self,
        candidates: list[dict[str, Any]],
        run_date: str,
        *,
        data_gap_candidates: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        data_gap_candidates = data_gap_candidates or []
        hard = [item for item in candidates if item["plan_type"] == "REJECT_HARD"]
        soft = [item for item in candidates if item["plan_type"] == "REJECT_SOFT"]
        counter: Counter[str] = Counter()
        for item in candidates:
            for reason in item.get("hard_blocks") or item.get("risk_flags") or [item["plan_type"]]:
                counter[reason] += 1
        if data_gap_candidates:
            counter["DATA_GAP_SKIPPED"] += len(data_gap_candidates)
        top = [{"reason": reason, "count": count} for reason, count in counter.most_common(8)]
        strict_buy = len([item for item in candidates if item["plan_type"] == "SIM_BUY_PLAN"])
        wait_pullback = len([item for item in candidates if item["plan_type"] == "WAIT_PULLBACK_PLAN"])
        wait_breakout = len([item for item in candidates if item["plan_type"] == "WAIT_BREAKOUT_PLAN"])
        watch = len([item for item in candidates if item["plan_type"] in {"WATCH_ONLY_PLAN", "SECTOR_BAROMETER"}])
        recommendation = (
            "严格模式无模拟买入计划，但存在等待/观察样本。不要放宽实盘风控，继续进入模拟观察和回测。"
            if strict_buy == 0
            else "存在少量严格模拟买入计划；仍需人工确认、模拟执行和后续复盘，不允许实盘自动化。"
        )
        return {
            "date": run_date,
            "universe_count": len(candidates) + len(data_gap_candidates),
            "active_candidate_count": len(candidates),
            "data_gap_count": len(data_gap_candidates),
            "data_gap_sample": [
                {
                    "symbol": item.get("symbol"),
                    "name": item.get("name"),
                    "source": item.get("source"),
                    "reason": item.get("data_gap_reason"),
                }
                for item in data_gap_candidates[:10]
            ],
            "raw_signal_count": len([item for item in candidates if item.get("raw_signals")]),
            "after_hard_filter_count": len(candidates) - len(hard),
            "strict_buy_plan_count": strict_buy,
            "wait_pullback_plan_count": wait_pullback,
            "wait_breakout_plan_count": wait_breakout,
            "watch_only_count": watch,
            "reject_soft_count": len(soft),
            "reject_hard_count": len(hard),
            "risk_alert_count": len([item for item in candidates if item["plan_type"] == "RISK_ALERT_PLAN"]),
            "top_blocking_reasons": top,
            "recommendation": recommendation,
            "simulate_only": True,
            "allow_live_order": False,
        }

    def _daily_summary(self, diagnostics: dict[str, Any]) -> str:
        reasons = ", ".join(
            f"{item['reason']}({item['count']})"
            for item in diagnostics.get("top_blocking_reasons", [])[:5]
        ) or "暂无"
        return (
            f"# {diagnostics['date']} V2 选股与模拟计划总结\n\n"
            "今日严格模式没有生成模拟买入计划不代表系统失效；没有候选、拒绝原因和复盘样本才是失败。\n\n"
            f"- 原始候选：{diagnostics['raw_signal_count']} 只\n"
            f"- 硬过滤后：{diagnostics['after_hard_filter_count']} 只\n"
            f"- 严格模拟买入计划：{diagnostics['strict_buy_plan_count']} 只\n"
            f"- 等回踩计划：{diagnostics['wait_pullback_plan_count']} 只\n"
            f"- 等突破计划：{diagnostics['wait_breakout_plan_count']} 只\n"
            f"- 仅观察候选：{diagnostics['watch_only_count']} 只\n"
            f"- 软拒绝跟踪：{diagnostics['reject_soft_count']} 只\n"
            f"- 硬过滤拒绝：{diagnostics['reject_hard_count']} 只\n\n"
            f"主要卡点：{reasons}。\n\n"
            f"处理建议：{diagnostics['recommendation']}\n"
        )

    def _daily_bars(
        self,
        symbol: str,
        *,
        as_of_date: str,
    ) -> list[dict[str, Any]]:
        return self.store.fetch_all(
            """
            SELECT trade_date, open, high, low, close, volume, amount, source, quality_status, updated_at
            FROM daily_bar_cache
            WHERE symbol = ?
              AND trade_date != 'ERROR'
              AND date(trade_date) <= date(?)
              AND open > 0 AND high > 0 AND low > 0 AND close > 0
              AND (quality_status IS NULL OR LOWER(quality_status) IN ('ready', 'ok', 'valid'))
            ORDER BY trade_date ASC
            """,
            (symbol, as_of_date),
        )

    def _latest_realtime(
        self,
        symbol: str,
        *,
        as_of_date: str,
    ) -> dict[str, Any] | None:
        row = self.store.fetch_one(
            """
            SELECT symbol, name, price, volume, amount, source, provider_status,
                   event_ts, received_ts, latency_ms, quality_status, fallback_used
            FROM realtime_market_events
            WHERE symbol = ?
              AND substr(event_ts, 1, 10) <= ?
            ORDER BY event_ts DESC, id DESC
            LIMIT 1
            """,
            (symbol, as_of_date),
        )
        return row

    def _load_config(self, path: Path) -> dict[str, Any]:
        return yaml.safe_load(path.read_text(encoding="utf-8"))

    def _raw_signals(self, row: dict[str, Any], features: dict[str, Any]) -> list[str]:
        signals: list[str] = []
        if features.get("is_limit_like"):
            signals.append("FIRST_LIMIT_UP" if (row.get("limit_up_count") in {None, 0, 1}) else "LIMIT_UP")
        elif features.get("is_near_limit"):
            signals.append("NEAR_LIMIT_UP")
        if features.get("recent_high_breakout"):
            signals.append("HIGH_BREAKOUT")
        if features.get("cost_line_near"):
            signals.append("COST_LINE_NEAR")
        if features.get("a_kill_repair"):
            signals.append("A_KILL_REPAIR")
        if row.get("auto_discovery"):
            signals.append("AUTO_DISCOVERY")
        if (features.get("public_opinion_tailwind") or {}).get("matched"):
            signals.append("PUBLIC_OPINION_SECTOR_TAILWIND")
        return list(dict.fromkeys(signals))

    def _entry_trigger(self, plan_type: str, position_class: str) -> str:
        if plan_type == "SIM_BUY_PLAN":
            return "回踩5日线不破且分时承接确认后，仅生成模拟买入计划。"
        if plan_type == "WAIT_PULLBACK_PLAN":
            return "等待缩量回踩5日线或关键支撑不破，禁止放量追高。"
        if plan_type == "WAIT_BREAKOUT_PLAN":
            return "等待平台突破或运行成本线回踩确认，未确认前只观察。"
        if position_class == "A_KILL_REPAIR":
            return "A杀修复只允许低吸观察，必须等待止跌结构和缩量确认。"
        return "记录观察条件和后续收益回填，不触发交易。"

    def _invalid_conditions(self, position_class: str) -> list[str]:
        common = ["放量跌破5日线", "板块核心股退潮", "高开低走放量长阴"]
        if position_class == "A_KILL_REPAIR":
            common.append("修复失败并再次破位")
        if position_class == "COST_LINE_NEAR":
            common.append("跌破运行成本线且无法收回")
        return common

    def _position_size(self, plan_type: str, position_class: str) -> str:
        if plan_type != "SIM_BUY_PLAN":
            return "NO_EXECUTION_REVIEW"
        if position_class == "A_KILL_REPAIR":
            return "SMALL_SIM"
        return "NORMAL_SIM"

    def _stop_loss(self, price: float, plan_type: str, position_class: str) -> float | None:
        if not price or plan_type not in {"SIM_BUY_PLAN", "WAIT_PULLBACK_PLAN", "WAIT_BREAKOUT_PLAN"}:
            return None
        ratio = 0.94 if position_class == "A_KILL_REPAIR" else 0.95
        return round(price * ratio, 3)

    def _take_profit(self, price: float, features: dict[str, Any]) -> float | None:
        if features.get("target_price"):
            return round(float(features["target_price"]), 3)
        if price:
            return round(price * 1.12, 3)
        return None

    def _evidence(self, features: dict[str, Any], position_class: str) -> dict[str, Any]:
        return {
            "price_position": position_class,
            "price_percentile_250d": features.get("price_percentile_250d"),
            "volume_price": f"volume_ratio={features.get('volume_ratio')}",
            "trend": {
                "above_ma5": features.get("above_ma5"),
                "ma5_slope": features.get("ma5_slope"),
            },
            "public_opinion": features.get("public_opinion_tailwind"),
            "data_quality": features.get("data_quality"),
        }

    def _reasons(
        self,
        plan_type: str,
        final_score: float,
        risk_penalty: float,
        risk_flags: list[str],
        hard_blocks: list[str],
        position_class: str,
    ) -> list[str]:
        reasons = [f"V2 final_score={final_score:.1f}, risk_penalty={risk_penalty:.1f}"]
        reasons.append(f"position_class={position_class}, plan_type={plan_type}")
        if hard_blocks:
            reasons.append("Hard filter: " + ",".join(hard_blocks))
        if risk_flags:
            reasons.append("Risk flags: " + ",".join(risk_flags))
        reasons.append("simulate_only=true; allow_live_order=false")
        return reasons

    def _data_quality(
        self,
        bars: list[dict[str, Any]],
        realtime: dict[str, Any] | None,
        price: float | None,
    ) -> str:
        if not price:
            return "missing_price"
        if realtime and realtime.get("quality_status") == "realtime_ok":
            return "realtime_ok_with_daily_bar" if bars else "realtime_only"
        if bars:
            return "daily_bar_cache"
        return "profile_or_partial"

    @staticmethod
    def _market_data_freshness(
        bars: list[dict[str, Any]],
        run_date: str,
        *,
        fixture: bool,
    ) -> dict[str, Any]:
        latest_value = (bars[-1] if bars else {}).get("trade_date")
        if not latest_value:
            return {
                "fresh": False,
                "status": "missing",
                "latest_trade_date": None,
                "business_session_age": None,
            }
        if fixture:
            return {
                "fresh": True,
                "status": "fixture",
                "latest_trade_date": str(latest_value),
                "business_session_age": 0,
            }
        try:
            latest_date = date.fromisoformat(str(latest_value)[:10])
            target_date = date.fromisoformat(str(run_date)[:10])
        except ValueError:
            return {
                "fresh": False,
                "status": "invalid",
                "latest_trade_date": str(latest_value),
                "business_session_age": None,
            }
        if latest_date > target_date:
            return {
                "fresh": False,
                "status": "future",
                "latest_trade_date": latest_date.isoformat(),
                "business_session_age": 0,
            }
        now = datetime.now(ZoneInfo("Asia/Shanghai"))
        allow_previous_session = (
            target_date == now.date()
            and now.time() <= time(15, 0)
        )
        business_age, calendar_source = trading_session_age(
            latest_date,
            target_date,
            exclude_target_session=allow_previous_session,
        )
        fresh = business_age == 0
        return {
            "fresh": fresh,
            "status": "fresh" if fresh else "stale",
            "latest_trade_date": latest_date.isoformat(),
            "business_session_age": business_age,
            "trading_calendar_source": calendar_source,
        }

    @staticmethod
    def _realtime_freshness(
        realtime: dict[str, Any] | None,
        run_date: str,
    ) -> dict[str, Any]:
        if not realtime:
            return {"fresh": False, "status": "missing", "age_minutes": None}
        raw_timestamp = realtime.get("event_ts") or realtime.get("received_ts")
        if not raw_timestamp:
            return {"fresh": False, "status": "missing_timestamp", "age_minutes": None}
        try:
            parsed = datetime.fromisoformat(str(raw_timestamp).replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=ZoneInfo("Asia/Shanghai"))
            local_timestamp = parsed.astimezone(ZoneInfo("Asia/Shanghai"))
            target_date = date.fromisoformat(str(run_date)[:10])
        except ValueError:
            return {"fresh": False, "status": "invalid_timestamp", "age_minutes": None}
        if local_timestamp.date() != target_date:
            return {
                "fresh": False,
                "status": "stale_date",
                "event_ts": local_timestamp.isoformat(),
                "age_minutes": None,
            }
        now = datetime.now(ZoneInfo("Asia/Shanghai"))
        if target_date != now.date():
            return {
                "fresh": True,
                "status": "historical_same_day",
                "event_ts": local_timestamp.isoformat(),
                "age_minutes": None,
            }
        age_minutes = (now - local_timestamp).total_seconds() / 60
        fresh = -5 <= age_minutes <= 30
        return {
            "fresh": fresh,
            "status": "fresh" if fresh else "stale_age",
            "event_ts": local_timestamp.isoformat(),
            "age_minutes": round(age_minutes, 2),
        }

    @staticmethod
    def _candidate_snapshot_freshness(
        row: dict[str, Any],
        run_date: str,
    ) -> dict[str, Any]:
        trade_date = str(row.get("trade_date") or "")[:10]
        target_date = str(run_date)[:10]
        if not trade_date or trade_date != target_date:
            return {"fresh": False, "status": "date_mismatch", "age_minutes": None}
        now = datetime.now(ZoneInfo("Asia/Shanghai"))
        try:
            target = date.fromisoformat(target_date)
        except ValueError:
            return {"fresh": False, "status": "invalid_date", "age_minutes": None}
        if target != now.date():
            return {"fresh": True, "status": "historical_same_day", "age_minutes": None}
        if now.time() > time(15, 0):
            return {"fresh": False, "status": "after_close", "age_minutes": None}
        raw_timestamp = row.get("updated_at") or row.get("created_at")
        if not raw_timestamp:
            return {"fresh": False, "status": "missing_timestamp", "age_minutes": None}
        try:
            parsed = datetime.fromisoformat(str(raw_timestamp).replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=ZoneInfo("Asia/Shanghai"))
            local_timestamp = parsed.astimezone(ZoneInfo("Asia/Shanghai"))
        except ValueError:
            return {"fresh": False, "status": "invalid_timestamp", "age_minutes": None}
        age_minutes = (now - local_timestamp).total_seconds() / 60
        fresh = -5 <= age_minutes <= 30
        return {
            "fresh": fresh,
            "status": "fresh" if fresh else "stale_age",
            "age_minutes": round(age_minutes, 2),
        }

    def _write_json(self, path: Path, payload: Any) -> None:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
        path.write_text(
            "".join(json.dumps(row, ensure_ascii=False, default=str) + "\n" for row in rows),
            encoding="utf-8",
        )

    def _normalize_symbol(self, value: Any) -> str | None:
        symbol = str(value or "").strip().upper().replace(".", "")
        if not symbol:
            return None
        if len(symbol) == 8 and symbol[:2] in {"SH", "SZ"} and symbol[2:].isdigit():
            return symbol
        if len(symbol) == 6 and symbol.isdigit():
            return ("SH" if symbol.startswith("6") else "SZ") + symbol
        return symbol if len(symbol) >= 6 else None

    def _json(self, value: Any, default: Any | None = None) -> Any:
        if default is None:
            default = {}
        if value is None:
            return default
        if isinstance(value, (dict, list)):
            return value
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return default

    def _float(self, value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _ma(self, values: list[float], size: int) -> float | None:
        if len(values) < size:
            return None
        return mean(values[-size:])

    def _ratio(self, numerator: float | None, denominator: float | None) -> float | None:
        if numerator is None or not denominator:
            return None
        return round(numerator / denominator, 4)

    def _percentile(self, price: float | None, low: float | None, high: float | None) -> float | None:
        if price is None or low is None or high is None or high <= low:
            return None
        return round(max(0.0, min(100.0, (price - low) / (high - low) * 100)), 4)

    def _pct_down(self, price: float | None, high: float | None) -> float | None:
        if price is None or not high:
            return None
        return round(max(0.0, (high - price) / high * 100), 4)

    def _pct_up(self, price: float | None, low: float | None) -> float | None:
        if price is None or not low:
            return None
        return round((price - low) / low * 100, 4)

    def _pct_change(self, current: float | None, previous: float | None) -> float | None:
        if current is None or not previous:
            return None
        return round((current - previous) / previous * 100, 4)

    def _pct_change_from_bars(self, bars: list[dict[str, Any]]) -> float | None:
        if len(bars) < 2:
            return None
        current = self._float(bars[-1].get("close"))
        previous = self._float(bars[-2].get("close"))
        return self._pct_change(current, previous)
