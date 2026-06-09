from __future__ import annotations

import hashlib
import json
import os
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from app.backtest.engine import BacktestEngine
from app.candidates.offhour_search import OffhourPotentialSearchService
from app.config import settings
from app.data.daily_bar_cache import DailyBarCacheService
from app.storage.sqlite_store import SQLiteStore


SAFE_ACTIONS = {
    "SIM_BUY_CANDIDATE",
    "HOLD_OR_TRAIL",
    "REDUCE_OR_EXIT",
    "AVOID_OR_WAIT",
    "WAIT_CONFIRMATION",
    "RISK_ALERT",
    "NO_TRADE",
}

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_ARTIFACT_DIR = PROJECT_ROOT / "backend" / "output" / "model_candidates"


def _json_dumps(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)


def _json_loads(value: str | None, fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return fallback


def _sha256_payload(payload: Any) -> str:
    return hashlib.sha256(_json_dumps(payload).encode("utf-8")).hexdigest()


class StrategySourceError(ValueError):
    """Raised when Dataset2 strategy files are unsafe or unavailable."""


class Dataset2StrategyAdapter:
    """Read Dataset2 rules as simulation-only research signals."""

    def __init__(self, source_dir: str | Path | None = None) -> None:
        self.source_dir = Path(source_dir) if source_dir else self._discover_source_dir()

    def capabilities(self) -> dict[str, Any]:
        source_dir = self.source_dir
        strategy_path = source_dir / "strategies" / "strategy_set.json"
        risk_path = source_dir / "strategies" / "risk_controls.json"
        return {
            "source_dir": str(source_dir),
            "strategy_set_exists": strategy_path.exists(),
            "risk_controls_exists": risk_path.exists(),
            "mode_required": "simulation_and_training_only",
            "allowed_actions": sorted(SAFE_ACTIONS),
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def load(self) -> dict[str, Any]:
        strategy_path = self.source_dir / "strategies" / "strategy_set.json"
        risk_path = self.source_dir / "strategies" / "risk_controls.json"
        if not strategy_path.exists():
            raise StrategySourceError(f"Dataset2 strategy_set.json not found: {strategy_path}")
        if not risk_path.exists():
            raise StrategySourceError(f"Dataset2 risk_controls.json not found: {risk_path}")

        strategy_set = json.loads(strategy_path.read_text(encoding="utf-8"))
        risk_controls = json.loads(risk_path.read_text(encoding="utf-8"))
        mode = strategy_set.get("mode")
        if mode != "simulation_and_training_only":
            raise StrategySourceError(f"Dataset2 strategy mode is {mode!r}; expected simulation_and_training_only")

        rules = strategy_set.get("rules") or []
        unsafe_rules: list[dict[str, Any]] = []
        for rule in rules:
            outputs = rule.get("outputs") or {}
            action = outputs.get("action_label")
            allow_live_order = outputs.get("allow_live_order")
            if action not in SAFE_ACTIONS or allow_live_order is not False:
                unsafe_rules.append(
                    {
                        "pattern_id": rule.get("pattern_id"),
                        "action_label": action,
                        "allow_live_order": allow_live_order,
                    }
                )
        if unsafe_rules:
            raise StrategySourceError(
                f"Dataset2 contains unsafe strategy outputs: {unsafe_rules[:5]}"
            )

        return {
            "source_dir": str(self.source_dir),
            "strategy_path": str(strategy_path),
            "risk_path": str(risk_path),
            "strategy_set": strategy_set,
            "risk_controls": risk_controls,
            "rule_count": len(rules),
            "source_hash": _sha256_payload(
                {
                    "strategy_set": strategy_set,
                    "risk_controls": risk_controls,
                }
            ),
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def evaluate(self, rules: list[dict[str, Any]], features: dict[str, Any], threshold: float = 0.5) -> list[dict[str, Any]]:
        observed_tags = set(features.get("tags") or [])
        timeframe = features.get("timeframe")
        matches: list[dict[str, Any]] = []
        for rule in rules:
            rule_timeframe = str(rule.get("timeframe") or "")
            if timeframe and rule_timeframe not in {timeframe, "daily_3bar", "daily/intraday", "intraday/daily", "system"}:
                continue
            conditions = rule.get("conditions") or {}
            rule_tags = set(conditions.get("software_tags") or [])
            if not rule_tags:
                continue
            score = len(observed_tags & rule_tags) / max(1, len(rule_tags))
            if score < threshold:
                continue
            outputs = rule.get("outputs") or {}
            matches.append(
                {
                    "score": round(score, 6),
                    "pattern_id": rule.get("pattern_id"),
                    "pattern_name": rule.get("name"),
                    "category": rule.get("category"),
                    "timeframe": rule_timeframe,
                    "action_label": outputs.get("action_label", "WAIT_CONFIRMATION"),
                    "expected_bias": outputs.get("expected_bias"),
                    "risk_level": outputs.get("risk_level"),
                    "confidence": outputs.get("confidence"),
                    "matched_tags": sorted(observed_tags & rule_tags),
                    "required_tags": sorted(rule_tags),
                    "allow_live_order": False,
                    "review_only": True,
                    "simulation_only": True,
                }
            )
        return sorted(matches, key=lambda item: (-item["score"], item["pattern_id"] or ""))

    def _discover_source_dir(self) -> Path:
        env_path = os.environ.get("DATASET2_SOURCE_DIR")
        if env_path:
            return Path(env_path)
        roots = [
            PROJECT_ROOT.parent,
            PROJECT_ROOT,
            Path.cwd(),
            Path.cwd().parent,
        ]
        for root in roots:
            candidate = root / "dataset2" / "a_share_trading_training_pack_v2" / "a_share_trading_training_pack_v2"
            if (candidate / "strategies" / "strategy_set.json").exists():
                return candidate
            if not root.exists():
                continue
            for child in root.iterdir():
                if child.name in {"dataset2", "a_share_trading_training_pack_v2"} or child.name.startswith("数据集"):
                    nested = child / "a_share_trading_training_pack_v2" / "a_share_trading_training_pack_v2"
                    if (nested / "strategies" / "strategy_set.json").exists():
                        return nested
                    if (child / "strategies" / "strategy_set.json").exists():
                        return child
        return PROJECT_ROOT.parent / "数据集2" / "a_share_trading_training_pack_v2" / "a_share_trading_training_pack_v2"


class OffhourResearchLoopService:
    """Balanced off-hour search, Dataset2 replay, sandbox review, and artifact loop."""

    def __init__(
        self,
        dataset2_source_dir: str | Path | None = None,
        artifact_dir: str | Path | None = None,
    ) -> None:
        self.store = SQLiteStore(settings.database_path)
        self.store.init()
        self.adapter = Dataset2StrategyAdapter(dataset2_source_dir)
        self.artifact_dir = Path(artifact_dir) if artifact_dir else DEFAULT_ARTIFACT_DIR

    def capabilities(self) -> dict[str, Any]:
        return {
            "schema_version": "offhour_research_capabilities.v1",
            "mode": "balanced_search_replay",
            "supported_steps": [
                "health_guard",
                "offhour_potential_search",
                "daily_bar_coverage_check",
                "dataset2_strategy_replay",
                "historical_backtest_review",
                "sandbox_outcome_review",
                "model_candidate_artifact",
                "codex_supervisor_next_action",
            ],
            "default_budget_split": {"potential_search": 0.5, "strategy_replay": 0.5},
            "dataset2": self.adapter.capabilities(),
            "artifact_dir": str(self.artifact_dir),
            "artifact_policy": "candidate_review_only_not_loaded",
            "forbidden_actions": [
                "broker_login",
                "credential_storage",
                "real_order",
                "live_trading",
                "screen_click_trading",
                "rules_yaml_autowrite",
            ],
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def run(
        self,
        limit: int = 100,
        strategy_limit: int = 50,
        history_days: int = 240,
        write_artifact: bool = True,
        refresh_history: bool = False,
        requested_by: str = "codex",
    ) -> dict[str, Any]:
        limit = max(1, min(int(limit or 100), 500))
        strategy_limit = max(1, min(int(strategy_limit or 50), 500))
        history_days = max(30, min(int(history_days or 240), 1000))
        started_at = datetime.now().isoformat(timespec="seconds")

        if settings.enable_live_trading:
            result = self._blocked_result(
                started_at=started_at,
                requested_by=requested_by,
                reason="live_trading_enabled",
            )
            result["run_id"] = self._persist(result)
            return result

        try:
            source = self.adapter.load()
        except StrategySourceError as exc:
            result = self._blocked_result(
                started_at=started_at,
                requested_by=requested_by,
                reason=str(exc),
            )
            result["run_id"] = self._persist(result)
            return result

        potential = self._run_potential_search(limit=max(1, limit // 2))
        symbols = self._select_symbols(potential, strategy_limit)
        coverage = self._coverage(symbols)
        refresh = self._refresh_history(limit=min(limit, 100), days=history_days) if refresh_history else None
        if refresh_history:
            coverage = self._coverage(symbols)

        replay = self._strategy_replay(
            symbols=symbols,
            rules=source["strategy_set"].get("rules") or [],
            limit=strategy_limit,
            history_days=history_days,
        )
        backtest = self._backtest(replay["symbols"], history_days=history_days)
        sandbox = self._sandbox(replay["signals"], horizon_days=5)
        artifact = self._write_model_candidate(source, replay, backtest, sandbox) if write_artifact and sandbox["evaluated_count"] else {
            "status": "skipped",
            "reason": "no_evaluated_sandbox_signals",
            "artifact_written": False,
        }

        status = "completed"
        blocked_reasons: list[str] = []
        if replay["signal_count"] == 0:
            status = "blocked"
            blocked_reasons.append("insufficient_history_data" if not coverage["ready_symbols"] else "no_dataset2_strategy_matches")
        elif backtest["status"] not in {"completed", "partial", "skipped"}:
            status = "partial"

        result = {
            "schema_version": "offhour_research_run.v1",
            "status": status,
            "mode": "balanced_search_replay",
            "started_at": started_at,
            "completed_at": datetime.now().isoformat(timespec="seconds"),
            "requested_by": requested_by,
            "budget": {
                "limit": limit,
                "strategy_limit": strategy_limit,
                "history_days": history_days,
                "potential_search_limit": max(1, limit // 2),
                "refresh_history": refresh_history,
            },
            "dataset2_source": {
                "source_dir": source["source_dir"],
                "rule_count": source["rule_count"],
                "source_hash": source["source_hash"],
                "mode": source["strategy_set"].get("mode"),
            },
            "potential_search": potential,
            "daily_bar_coverage": coverage,
            "history_refresh": refresh,
            "strategy_replay": replay,
            "backtest": backtest,
            "sandbox": sandbox,
            "model_candidate": artifact,
            "blocked_reasons": blocked_reasons,
            "next_action": self._next_action(status, replay, sandbox, artifact, coverage),
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }
        result["run_id"] = self._persist(result)
        return result

    def latest_run(self) -> dict[str, Any] | None:
        row = self.store.fetch_one(
            """
            SELECT *
            FROM offhour_research_runs
            ORDER BY id DESC
            LIMIT 1
            """
        )
        return self._row_model(row) if row else None

    def get_run(self, run_id: int) -> dict[str, Any] | None:
        row = self.store.fetch_one(
            "SELECT * FROM offhour_research_runs WHERE id = ?",
            (run_id,),
        )
        return self._row_model(row) if row else None

    def latest_model_candidate(self) -> dict[str, Any]:
        row = self.store.fetch_one(
            """
            SELECT id, artifact_json, created_at, completed_at
            FROM offhour_research_runs
            WHERE artifact_json IS NOT NULL
              AND artifact_json != '{}'
            ORDER BY id DESC
            LIMIT 1
            """
        )
        if not row:
            return {
                "status": "empty",
                "artifact_written": False,
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            }
        artifact = _json_loads(row.get("artifact_json"), {})
        return {
            "run_id": row["id"],
            "artifact": artifact,
            "created_at": row.get("created_at"),
            "completed_at": row.get("completed_at"),
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _run_potential_search(self, limit: int) -> dict[str, Any]:
        try:
            result = OffhourPotentialSearchService().run(limit=limit, persist=True)
            return {
                "status": result.get("status", "unknown"),
                "run_id": result.get("run_id"),
                "total_scanned": result.get("total_scanned", 0),
                "stored_count": result.get("stored_count", 0),
                "scored_count": result.get("scored_count", 0),
                "top_scored_symbols": result.get("top_scored_symbols", []),
                "top_scored_items": result.get("top_scored_items", []),
                "errors": result.get("errors", []),
            }
        except Exception as exc:
            return {
                "status": "failed",
                "error": str(exc),
                "top_scored_symbols": [],
                "top_scored_items": [],
                "errors": [str(exc)],
            }

    def _select_symbols(self, potential: dict[str, Any], limit: int) -> list[str]:
        selected: list[str] = []
        for symbol in potential.get("top_scored_symbols") or []:
            if symbol and symbol not in selected:
                selected.append(symbol)
        for item in potential.get("top_scored_items") or []:
            symbol = item.get("symbol")
            if symbol and symbol not in selected:
                selected.append(symbol)
        if len(selected) >= limit:
            return selected[:limit]

        rows = self.store.fetch_all(
            """
            SELECT symbol, COUNT(*) AS cnt, MAX(trade_date) AS last_trade_date
            FROM daily_bar_cache
            WHERE quality_status = 'ready'
              AND trade_date != 'ERROR'
            GROUP BY symbol
            HAVING cnt >= 3
            ORDER BY last_trade_date DESC, cnt DESC, symbol ASC
            LIMIT ?
            """,
            (limit * 2,),
        )
        for row in rows:
            symbol = row.get("symbol")
            if symbol and symbol not in selected:
                selected.append(symbol)
            if len(selected) >= limit:
                break
        return selected

    def _coverage(self, symbols: list[str]) -> dict[str, Any]:
        if not symbols:
            return {
                "status": "empty",
                "checked_symbols": 0,
                "ready_symbols": [],
                "missing_symbols": [],
            }
        rows = self.store.fetch_all(
            f"""
            SELECT symbol, COUNT(*) AS bar_count, MIN(trade_date) AS first_trade_date, MAX(trade_date) AS last_trade_date
            FROM daily_bar_cache
            WHERE symbol IN ({",".join("?" for _ in symbols)})
              AND quality_status = 'ready'
              AND trade_date != 'ERROR'
            GROUP BY symbol
            """,
            tuple(symbols),
        )
        by_symbol = {row["symbol"]: dict(row) for row in rows}
        ready = [symbol for symbol in symbols if int(by_symbol.get(symbol, {}).get("bar_count") or 0) >= 3]
        missing = [symbol for symbol in symbols if symbol not in ready]
        return {
            "status": "ready" if ready else "insufficient_history_data",
            "checked_symbols": len(symbols),
            "ready_symbols": ready,
            "missing_symbols": missing,
            "items": list(by_symbol.values()),
        }

    def _refresh_history(self, limit: int, days: int) -> dict[str, Any]:
        try:
            return DailyBarCacheService().refresh_bars(limit=limit, days=days)
        except Exception as exc:
            return {
                "status": "failed",
                "error": str(exc),
                "fallback": "existing_daily_bar_cache_only",
            }

    def _strategy_replay(
        self,
        symbols: list[str],
        rules: list[dict[str, Any]],
        limit: int,
        history_days: int,
    ) -> dict[str, Any]:
        if not symbols:
            return {
                "status": "blocked",
                "reason": "no_symbols_available",
                "signal_count": 0,
                "signals": [],
                "symbols": [],
                "pattern_counts": {},
                "action_counts": {},
            }
        cutoff = (datetime.now() - timedelta(days=history_days)).date().isoformat()
        signals: list[dict[str, Any]] = []
        for symbol in symbols:
            rows = self.store.fetch_all(
                """
                SELECT symbol, trade_date, open, high, low, close, volume, amount
                FROM daily_bar_cache
                WHERE symbol = ?
                  AND quality_status = 'ready'
                  AND trade_date >= ?
                  AND trade_date != 'ERROR'
                ORDER BY trade_date ASC
                """,
                (symbol, cutoff),
            )
            if len(rows) < 3:
                continue
            for idx in range(2, len(rows)):
                row = dict(rows[idx])
                prev = dict(rows[idx - 1])
                prev2 = dict(rows[idx - 2])
                features = self._features(row, prev, prev2, [dict(item) for item in rows[: idx + 1]])
                matches = self.adapter.evaluate(rules, features, threshold=0.5)
                if not matches:
                    continue
                best = matches[0]
                if best["action_label"] not in {"SIM_BUY_CANDIDATE", "HOLD_OR_TRAIL", "WAIT_CONFIRMATION", "RISK_ALERT"}:
                    continue
                signal = {
                    "symbol": symbol,
                    "signal_date": row["trade_date"],
                    "close": row["close"],
                    "pct_change": features["pct_change"],
                    "tags": features["tags"],
                    "pattern_id": best["pattern_id"],
                    "pattern_name": best["pattern_name"],
                    "category": best["category"],
                    "action_label": best["action_label"],
                    "risk_level": best["risk_level"],
                    "score": best["score"],
                    "matched_tags": best["matched_tags"],
                    "match_count": len(matches),
                    "top_matches": matches[:3],
                    "review_only": True,
                    "simulation_only": True,
                    "allow_live_order": False,
                }
                signals.append(signal)
        signals.sort(key=lambda item: (-float(item["score"]), item["signal_date"], item["symbol"]))
        limited = signals[:limit]
        pattern_counts = Counter(str(item["pattern_id"]) for item in limited)
        action_counts = Counter(str(item["action_label"]) for item in limited)
        return {
            "status": "completed" if limited else "blocked",
            "reason": None if limited else "no_dataset2_strategy_matches",
            "signal_count": len(limited),
            "signals": limited,
            "symbols": sorted({item["symbol"] for item in limited}),
            "pattern_counts": dict(pattern_counts),
            "action_counts": dict(action_counts),
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _features(
        self,
        row: dict[str, Any],
        prev: dict[str, Any],
        prev2: dict[str, Any],
        history: list[dict[str, Any]],
    ) -> dict[str, Any]:
        close = float(row["close"])
        open_ = float(row["open"])
        prev_close = float(prev["close"]) or close
        prev_volume = float(prev["volume"] or 0)
        prev2_volume = float(prev2["volume"] or 0)
        volume = float(row["volume"] or 0)
        amount = float(row["amount"] or 0)
        pct = (close - prev_close) / prev_close * 100 if prev_close else 0.0
        body_pct = abs(close - open_) / prev_close * 100 if prev_close else 0.0
        recent = history[-20:]
        avg_volume = sum(float(item["volume"] or 0) for item in recent[:-1]) / max(1, len(recent) - 1)
        volume_ratio = volume / avg_volume if avg_volume else 1.0
        rolling_high = max(float(item["high"]) for item in recent)
        five_day_base = float(history[-6]["close"]) if len(history) >= 6 else prev_close
        five_day_pct = (close - five_day_base) / five_day_base * 100 if five_day_base else 0.0
        tags = {"single_candle", "daily"}
        if close >= open_ and body_pct >= 5:
            tags.add("big_yang")
        elif close < open_ and body_pct >= 5:
            tags.add("big_yin")
        elif body_pct >= 2:
            tags.add("medium_body")
        else:
            tags.add("small_body")
        if volume_ratio >= 1.5:
            tags.add("high_volume")
            tags.add("volume_surge")
        if volume_ratio <= 0.75:
            tags.add("low_volume")
        if pct > 0 and volume_ratio >= 1.2:
            tags.add("price_volume_rise")
        if pct > 0 and volume < prev_volume:
            tags.add("price_up_volume_down")
        if pct >= 5 and volume_ratio < 0.9:
            tags.update({"low_volume_big_rise", "lockup"})
        if pct >= 5 and volume_ratio >= 1.2:
            tags.update({"bullish_attack", "volume_increasing"})
        if pct >= 9.5:
            tags.add("limit_up")
        if pct <= -5 and volume_ratio >= 1.2:
            tags.update({"big_fall", "distribution"})
        if close >= rolling_high * 0.92:
            tags.add("top_risk")
        if five_day_pct >= 5:
            tags.add("up_phase")
        if five_day_pct <= -5:
            tags.add("down_phase")
        if volume > prev_volume > prev2_volume:
            tags.add("volume_increasing")
        if amount >= 100_000_000:
            tags.add("high_amount")
        if "small_body" in tags and "high_volume" in tags:
            tags.add("turning_point")
        if "small_body" in tags and "low_volume" in tags:
            tags.add("sideways")
        if "top_risk" in tags and pct < 1.5 and volume_ratio >= 1.2:
            tags.update({"volume_up_price_stall", "reduce"})
        return {
            "timeframe": "daily",
            "tags": sorted(tags),
            "pct_change": round(pct, 6),
            "body_pct": round(body_pct, 6),
            "volume_ratio": round(volume_ratio, 6),
            "five_day_pct": round(five_day_pct, 6),
        }

    def _backtest(self, symbols: list[str], history_days: int) -> dict[str, Any]:
        if not symbols:
            return {"status": "skipped", "reason": "no_replay_symbols"}
        date_range = self._date_range(symbols)
        if not date_range:
            return {"status": "skipped", "reason": "insufficient_history_data"}
        start_date, end_date = date_range
        min_start = (datetime.fromisoformat(end_date) - timedelta(days=history_days)).date().isoformat()
        start_date = max(start_date, min_start)
        try:
            result = BacktestEngine().run(
                start_date=start_date,
                end_date=end_date,
                symbols=symbols[:20],
                initial_cash=100000.0,
                max_positions=min(5, max(1, len(symbols))),
                per_symbol_cap=0.2,
                benchmark_symbol=settings.backtest_default_benchmark_symbol,
                persist=True,
            )
            return {
                "status": result.get("status"),
                "run_id": result.get("run_id"),
                "symbols": symbols[:20],
                "start_date": start_date,
                "end_date": end_date,
                "metrics": result.get("metrics", {}),
                "benchmark": result.get("benchmark", {}),
                "execution_warnings": result.get("execution_warnings", []),
                "simulation_only": True,
            }
        except Exception as exc:
            return {
                "status": "failed",
                "error": str(exc),
                "symbols": symbols[:20],
                "simulation_only": True,
            }

    def _date_range(self, symbols: list[str]) -> tuple[str, str] | None:
        rows = self.store.fetch_all(
            f"""
            SELECT MIN(trade_date) AS start_date, MAX(trade_date) AS end_date
            FROM daily_bar_cache
            WHERE symbol IN ({",".join("?" for _ in symbols)})
              AND quality_status = 'ready'
              AND trade_date != 'ERROR'
            """,
            tuple(symbols),
        )
        if not rows or not rows[0].get("start_date") or not rows[0].get("end_date"):
            return None
        return str(rows[0]["start_date"]), str(rows[0]["end_date"])

    def _sandbox(self, signals: list[dict[str, Any]], horizon_days: int) -> dict[str, Any]:
        evaluations: list[dict[str, Any]] = []
        for signal in signals:
            rows = self.store.fetch_all(
                """
                SELECT trade_date, close
                FROM daily_bar_cache
                WHERE symbol = ?
                  AND quality_status = 'ready'
                  AND trade_date > ?
                ORDER BY trade_date ASC
                LIMIT ?
                """,
                (signal["symbol"], signal["signal_date"], horizon_days),
            )
            if not rows:
                evaluations.append(
                    {
                        "symbol": signal["symbol"],
                        "signal_date": signal["signal_date"],
                        "pattern_id": signal["pattern_id"],
                        "status": "pending_future_data",
                        "outcome_label": "pending",
                    }
                )
                continue
            entry = float(signal["close"])
            closes = [float(row["close"]) for row in rows]
            max_return = (max(closes) - entry) / entry * 100 if entry else 0.0
            min_return = (min(closes) - entry) / entry * 100 if entry else 0.0
            close_return = (closes[-1] - entry) / entry * 100 if entry else 0.0
            if max_return >= 3:
                label = "strong_follow_through"
            elif max_return >= 1:
                label = "mild_follow_through"
            elif close_return <= -3 or min_return <= -4:
                label = "failed_signal"
            else:
                label = "flat_or_noise"
            evaluations.append(
                {
                    "symbol": signal["symbol"],
                    "signal_date": signal["signal_date"],
                    "pattern_id": signal["pattern_id"],
                    "action_label": signal["action_label"],
                    "status": "completed",
                    "entry_price": entry,
                    "horizon_days": len(rows),
                    "max_return_pct": round(max_return, 6),
                    "min_return_pct": round(min_return, 6),
                    "close_return_pct": round(close_return, 6),
                    "outcome_label": label,
                    "review_only": True,
                    "simulation_only": True,
                }
            )
        completed = [item for item in evaluations if item["status"] == "completed"]
        outcome_counts = Counter(item["outcome_label"] for item in evaluations)
        by_pattern: dict[str, dict[str, Any]] = {}
        for item in completed:
            pid = str(item["pattern_id"])
            slot = by_pattern.setdefault(pid, {"sample_count": 0, "wins": 0, "avg_close_return_pct": 0.0})
            slot["sample_count"] += 1
            slot["wins"] += 1 if item["outcome_label"] in {"strong_follow_through", "mild_follow_through"} else 0
            slot["avg_close_return_pct"] += float(item["close_return_pct"])
        for slot in by_pattern.values():
            count = slot["sample_count"]
            slot["win_rate"] = round(slot["wins"] / count, 6) if count else 0.0
            slot["avg_close_return_pct"] = round(slot["avg_close_return_pct"] / count, 6) if count else 0.0
        return {
            "status": "completed" if completed else "blocked",
            "evaluated_count": len(completed),
            "pending_count": len(evaluations) - len(completed),
            "outcome_counts": dict(outcome_counts),
            "pattern_performance": by_pattern,
            "evaluations": evaluations[:50],
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _write_model_candidate(
        self,
        source: dict[str, Any],
        replay: dict[str, Any],
        backtest: dict[str, Any],
        sandbox: dict[str, Any],
    ) -> dict[str, Any]:
        pattern_perf = sandbox.get("pattern_performance") or {}
        ranked_patterns = sorted(
            (
                {
                    "pattern_id": pattern_id,
                    **metrics,
                }
                for pattern_id, metrics in pattern_perf.items()
            ),
            key=lambda item: (-float(item.get("win_rate") or 0), -int(item.get("sample_count") or 0), item["pattern_id"]),
        )
        payload = {
            "schema_version": "offhour_model_candidate.v1",
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "artifact_kind": "dataset2_strategy_scorecard",
            "status": "candidate_review_only",
            "source_hash": source["source_hash"],
            "signal_count": replay.get("signal_count", 0),
            "evaluated_count": sandbox.get("evaluated_count", 0),
            "top_patterns": ranked_patterns[:20],
            "action_counts": replay.get("action_counts", {}),
            "outcome_counts": sandbox.get("outcome_counts", {}),
            "backtest_metrics": backtest.get("metrics", {}),
            "usage_policy": {
                "candidate_only": True,
                "auto_loaded": False,
                "writes_rules_yaml": False,
                "broker_or_order_action": False,
                "requires_human_review": True,
            },
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }
        artifact_hash = _sha256_payload(payload)
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        path = self.artifact_dir / f"offhour_model_candidate_{artifact_hash[:12]}.json"
        path.write_text(_json_dumps(payload), encoding="utf-8")
        return {
            "status": "written",
            "artifact_written": True,
            "artifact_path": str(path),
            "artifact_hash": artifact_hash,
            "artifact_kind": payload["artifact_kind"],
            "candidate_only": True,
            "auto_loaded": False,
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _next_action(
        self,
        status: str,
        replay: dict[str, Any],
        sandbox: dict[str, Any],
        artifact: dict[str, Any],
        coverage: dict[str, Any],
    ) -> str:
        if status == "blocked" and coverage.get("status") == "insufficient_history_data":
            return "Refresh daily_bar_cache for more candidate symbols, then rerun offhour research loop."
        if replay.get("signal_count", 0) == 0:
            return "Broaden Dataset2 tag mapping or collect more daily history before candidate artifact review."
        if sandbox.get("evaluated_count", 0) < 3:
            return "Collect more future bars for replayed signals before trusting pattern performance."
        if artifact.get("status") == "written":
            return "Review candidate scorecard artifact; keep it detached from production rules until manually accepted."
        return "Review replay and sandbox evidence; no production strategy changes were made."

    def _blocked_result(self, started_at: str, requested_by: str, reason: str) -> dict[str, Any]:
        return {
            "schema_version": "offhour_research_run.v1",
            "status": "blocked",
            "mode": "balanced_search_replay",
            "started_at": started_at,
            "completed_at": datetime.now().isoformat(timespec="seconds"),
            "requested_by": requested_by,
            "blocked_reasons": [reason],
            "potential_search": {},
            "daily_bar_coverage": {},
            "strategy_replay": {"status": "blocked", "signal_count": 0, "signals": []},
            "backtest": {"status": "skipped"},
            "sandbox": {"status": "skipped", "evaluated_count": 0},
            "model_candidate": {"status": "skipped", "artifact_written": False},
            "next_action": "Fix blocked safety or Dataset2 source issue before rerunning offhour research loop.",
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _persist(self, result: dict[str, Any]) -> int:
        summary = {
            "status": result.get("status"),
            "signal_count": (result.get("strategy_replay") or {}).get("signal_count", 0),
            "evaluated_count": (result.get("sandbox") or {}).get("evaluated_count", 0),
            "artifact_status": (result.get("model_candidate") or {}).get("status"),
            "blocked_reasons": result.get("blocked_reasons", []),
            "next_action": result.get("next_action"),
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }
        with self.store.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO offhour_research_runs(
                    mode, status, requested_by, summary_json, potential_search_json,
                    strategy_replay_json, backtest_json, sandbox_json, artifact_json,
                    next_action, review_only, simulation_only, live_trading_enabled, completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    result.get("mode", "balanced_search_replay"),
                    result.get("status", "unknown"),
                    result.get("requested_by"),
                    _json_dumps(summary),
                    _json_dumps(result.get("potential_search") or {}),
                    _json_dumps(result.get("strategy_replay") or {}),
                    _json_dumps(result.get("backtest") or {}),
                    _json_dumps(result.get("sandbox") or {}),
                    _json_dumps(result.get("model_candidate") or {}),
                    result.get("next_action"),
                    1,
                    1,
                    1 if settings.enable_live_trading else 0,
                    result.get("completed_at"),
                ),
            )
            return int(cursor.lastrowid)

    def _row_model(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "run_id": row["id"],
            "id": row["id"],
            "mode": row.get("mode"),
            "status": row.get("status"),
            "requested_by": row.get("requested_by"),
            "summary": _json_loads(row.get("summary_json"), {}),
            "potential_search": _json_loads(row.get("potential_search_json"), {}),
            "strategy_replay": _json_loads(row.get("strategy_replay_json"), {}),
            "backtest": _json_loads(row.get("backtest_json"), {}),
            "sandbox": _json_loads(row.get("sandbox_json"), {}),
            "model_candidate": _json_loads(row.get("artifact_json"), {}),
            "next_action": row.get("next_action"),
            "review_only": bool(row.get("review_only")),
            "simulation_only": bool(row.get("simulation_only")),
            "live_trading_enabled": bool(row.get("live_trading_enabled")),
            "created_at": row.get("created_at"),
            "completed_at": row.get("completed_at"),
        }
