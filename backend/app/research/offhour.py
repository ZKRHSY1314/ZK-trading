from __future__ import annotations

import hashlib
import csv
import json
import sqlite3
import os
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from app.backtest.execution import BacktestExecutionModel
from app.backtest.engine import BacktestEngine
from app.candidates.offhour_search import OffhourPotentialSearchService
from app.config import settings
from app.data.daily_bar_cache import DailyBarCacheService
from app.data.price_limits import infer_board_type, limit_up_threshold
from app.data.symbols import normalize_a_share_code
from app.learning.phase_replay import MainForcePhaseReplayService
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

DATASET1_EXPERIENCE_ALIGNED_FILTERS = {
    "entry_close_above_signal",
    "entry_green_above_signal",
    "strong_reclaim",
    "dataset1_stabilized_reclaim",
    "dataset1_low_risk_stabilized_reclaim",
    "dataset1_accumulation_reclaim",
}

MIN_PROMOTION_SAMPLE_COUNT = 10
MIN_PROMOTION_WIN_RATE = 0.65
MIN_PROMOTION_AVG_RETURN_PCT = 1.0
MIN_SIGNAL_BACKTEST_TRADE_COUNT = 3
MIN_SIGNAL_BACKTEST_WIN_RATE = 0.5
MIN_SIGNAL_BACKTEST_AVG_RETURN_PCT = 0.0
MIN_SHADOW_VALIDATION_TRADE_COUNT = 2
MIN_SHADOW_VALIDATION_WIN_RATE = 0.58
MIN_SHADOW_VALIDATION_CUMULATIVE_RETURN_PCT = 20.0
MIN_OPTIMIZED_VALIDATION_WIN_RATE = 0.58
MIN_OPTIMIZED_VALIDATION_CUMULATIVE_RETURN_PCT = 20.0
MIN_WALK_FORWARD_FOLD_COUNT = 3
MIN_WALK_FORWARD_TRADE_COUNT = 6
MIN_WALK_FORWARD_FOLD_TRADE_COUNT = 3
MIN_WALK_FORWARD_WIN_RATE = 0.58
MIN_WALK_FORWARD_MIN_FOLD_WIN_RATE = 0.4
MIN_WALK_FORWARD_CUMULATIVE_RETURN_PCT = 20.0
MAX_WALK_FORWARD_FOLD_DRAWDOWN_PCT = -8.0
SIGNAL_BACKTEST_ACTIONS = {"SIM_BUY_CANDIDATE", "WAIT_CONFIRMATION"}
SIGNAL_OPTIMIZATION_CONFIRMATION_FILTERS = (
    "none",
    "entry_close_above_signal",
    "entry_green_above_signal",
    "strong_reclaim",
    "dataset1_stabilized_reclaim",
    "dataset1_low_risk_stabilized_reclaim",
    "dataset1_accumulation_reclaim",
)
SIGNAL_OPTIMIZATION_ATTRIBUTION_FILTERS = (
    "none",
    "star_requires_strong_reclaim",
    "turning_point_requires_green_or_strong",
    "star_and_turning_point_quality_gate",
    "block_dataset1_distribution_risk",
)
MAX_SIGNAL_OPTIMIZATION_SIGNAL_COUNT = 120
MAX_SIGNAL_OPTIMIZATION_EXPANDED_SIGNAL_COUNT = 600
MAX_SIGNAL_OPTIMIZATION_ENTRY_DELAY_DAYS = 2
MAX_SIGNAL_OPTIMIZATION_HORIZON_DAYS = 8
MAX_DEEP_SIGNAL_OPTIMIZATION_ENTRY_DELAY_DAYS = 3
MAX_DEEP_SIGNAL_OPTIMIZATION_HORIZON_DAYS = 10
SIM_REVIEW_PLAN_MAX_ITEMS = 12
SIM_REVIEW_PLAN_MAX_STRATEGY_OVERLAYS = 5
SIM_REVIEW_PLAN_DATA_FRESHNESS_MAX_DAYS = 5
SIM_REVIEW_PLAN_REFERENCE_CASH = 200_000.0
SIM_REVIEW_PLAN_MAX_INITIAL_POSITION_RATIO = 0.02
SIM_REVIEW_PLAN_MAX_CONFIRMED_POSITION_RATIO = 0.08
BROAD_MOMENTUM_TRACK = "broad_momentum_candidate"
DATASET1_STABILIZED_TRACK = "dataset1_stabilized_candidate"
RECLAIM_WATCH_MAX_ITEMS = 20
RECLAIM_WATCH_RECENT_SIGNAL_LIMIT = 120
RECLAIM_WATCH_MAX_SIGNAL_AGE_DAYS = 20
RECLAIM_TRANSITION_MAX_SIGNALS = 300
RECLAIM_TRANSITION_HORIZONS = (3, 5, 10)
NEAR_RECLAIM_CLOSE_RATIO = 0.985
NEAR_RECLAIM_OPEN_RATIO = 0.98
RECLAIM_REVIEW_INTRADAY_FLOOR_RATIO = 0.995
PHASE_CONFIDENCE_TARGET_TIERS = {
    "high_review_confidence_dry_run_only",
    "medium_review_confidence_dry_run_only",
}
MIN_PHASE_CONFIDENCE_WF_SAMPLE_COUNT = 6
MIN_PHASE_CONFIDENCE_WF_FOLD_COUNT = 3
MIN_PHASE_CONFIDENCE_WF_FOLD_SAMPLE_COUNT = 2
MIN_PHASE_CONFIDENCE_WF_WIN_RATE = 0.58
MIN_PHASE_CONFIDENCE_WF_MIN_FOLD_WIN_RATE = 0.4
MIN_PHASE_CONFIDENCE_WF_CUMULATIVE_RETURN_PCT = 20.0
MAX_PHASE_CONFIDENCE_WF_FOLD_LOSS_PCT = -8.0

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_ARTIFACT_DIR = PROJECT_ROOT / "backend" / "output" / "model_candidates"
MAX_INLINE_HISTORY_REFRESH_LIMIT = 20
MAX_INLINE_HISTORY_REFRESH_DAYS = 240
BENCHMARK_HISTORY_SYMBOLS = ("SH000300", "SH000001")
MIN_BENCHMARK_READY_BARS = 5
FOCUS_PHASE_TARGETS = [
    {
        "symbol": "SZ002115",
        "name": "三维通信",
        "role": "method_success_markup_sample",
        "dataset1_anchor": "成功预测主力动向并盈利；同时有开盘/反弹卖出纪律教训。",
        "supervision_policy": "learn_pre_markup_accumulation_and_sell_into_strength",
    },
    {
        "symbol": "SZ002081",
        "name": "金螳螂",
        "role": "completed_markup_distribution_training_sample",
        "dataset1_anchor": "用户补充：前几天主力已完成拉升出货，短期不应按新高追击。",
        "supervision_policy": "training_reference_only_after_distribution",
    },
    {
        "symbol": "SH600135",
        "name": "乐凯胶片",
        "role": "focus_watch_execution_discipline_sample",
        "dataset1_anchor": "重点关注；历史教训包含未及时卖出、越跌越补、买早买高。",
        "supervision_policy": "require_stabilization_and_execution_discipline",
    },
]


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


class Dataset1ExperienceAdapter:
    """Read Dataset1 strategy and case files as review-only constraints."""

    def __init__(self, source_dir: str | Path | None = None) -> None:
        self.source_dir = Path(source_dir) if source_dir else PROJECT_ROOT.parent / "数据集1"

    def summary(self) -> dict[str, Any]:
        if not self.source_dir.exists():
            return {
                "status": "missing",
                "source_dir": str(self.source_dir),
                "constraints": self._default_constraints(),
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            }

        success_cases = self._read_csv("案例库_成功案例.csv")
        failure_cases = self._read_csv("案例库_失败案例.csv")
        buy_rules = self._read_csv("战法库_买入策略.csv")
        sell_rules = self._read_csv("战法库_卖出策略.csv")
        strategy = self._read_json("trading_strategy.json", {})
        constitution = self._read_json("trading_constitution.json", {})
        return {
            "status": "ready",
            "source_dir": str(self.source_dir),
            "counts": {
                "success_cases": len(success_cases),
                "failure_cases": len(failure_cases),
                "buy_rules": len(buy_rules),
                "sell_rules": len(sell_rules),
                "strategy_sections": len(strategy) if isinstance(strategy, dict) else 0,
                "constitution_rules": len((constitution or {}).get("交易铁律") or []) if isinstance(constitution, dict) else 0,
            },
            "anchors": {
                "success_cases": [self._case_anchor(row) for row in success_cases[:5]],
                "failure_lessons": [self._lesson_anchor(row) for row in failure_cases[:5]],
                "buy_rules": [row.get("策略名") for row in buy_rules[:8] if row.get("策略名")],
                "sell_rules": [row.get("策略名") for row in sell_rules[:8] if row.get("策略名")],
            },
            "constraints": self._default_constraints(),
            "strategy_synthesis": self._strategy_synthesis(),
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _read_json(self, name: str, fallback: Any) -> Any:
        path = self.source_dir / name
        if not path.exists():
            return fallback
        try:
            return json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            return fallback

    def _read_csv(self, name: str) -> list[dict[str, Any]]:
        path = self.source_dir / name
        if not path.exists():
            return []
        try:
            with path.open("r", encoding="utf-8-sig", newline="") as file:
                return [dict(row) for row in csv.DictReader(file)]
        except (OSError, UnicodeDecodeError, csv.Error):
            return []

    def _case_anchor(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": row.get("id"),
            "stock": row.get("股票"),
            "result": row.get("结果"),
            "lesson": row.get("经验") or row.get("教训"),
        }

    def _lesson_anchor(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": row.get("id"),
            "stock": row.get("股票"),
            "failure": row.get("结果"),
            "lesson": row.get("教训") or row.get("经验"),
        }

    def _default_constraints(self) -> list[dict[str, Any]]:
        return [
            {
                "constraint_id": "dataset1_wait_for_stabilization",
                "summary": "Avoid buying too early; prefer confirmation after stabilization or pullback support.",
                "simulation_effect": "favor entry_delay_days >= 2 when validation metrics stay strong",
            },
            {
                "constraint_id": "dataset1_staged_position",
                "summary": "Use small first probes and staged add-ons instead of one-shot full entries.",
                "simulation_effect": "keep first simulated entry ratio modest and require fresh gates for add-ons",
            },
            {
                "constraint_id": "dataset1_sell_into_strength",
                "summary": "When markup has already expanded, sell or reduce into strength rather than chase.",
                "simulation_effect": "prefer take-profit and trailing review over late high-position entries",
            },
            {
                "constraint_id": "dataset1_auction_open_risk",
                "summary": "Weak open or failed auction after prior strength should trigger reduction review.",
                "simulation_effect": "do not convert weak-open follow-up into new buy signals",
            },
            {
                "constraint_id": "dataset1_low_position_limitup_quality",
                "summary": "Prefer low-position first limit-up candidates with moderate market cap, lower PB, and enough liquidity.",
                "simulation_effect": "use as ranking context only; never treat a limit-up label as a direct fillable buy order",
            },
            {
                "constraint_id": "dataset1_dealer_cost_target",
                "summary": "For long-accumulation candidates, estimate dealer cost from the base range and treat cost x 2.6 as a review target zone.",
                "simulation_effect": "avoid late chasing near target zones; use target proximity for staged take-profit review",
            },
            {
                "constraint_id": "dataset1_stabilized_reclaim",
                "summary": "After a Dataset2 signal, prefer entries that reclaim the signal close without breaking deeply below it.",
                "simulation_effect": "include dataset1_stabilized_reclaim in off-hour parameter optimization",
            },
            {
                "constraint_id": "dataset1_distribution_risk_filter",
                "summary": "Avoid converting high-position, distribution, big-fall, or volume-up-price-stall signals into fresh entries.",
                "simulation_effect": "include low-risk stabilized reclaim and accumulation reclaim filters in optimization",
            },
        ]

    def _strategy_synthesis(self) -> dict[str, Any]:
        return {
            "primary_playbook": [
                "screen low-position/high-quality limit-up or strong trend candidates",
                "wait for Dataset2 volume-price signal and Dataset1 stabilization confirmation",
                "start with small simulated probe only after risk gates pass",
                "add in stages only after readback confirms holding strength",
                "sell into strength by ladder or reduce on weak open / failed reclaim",
            ],
            "avoidance_rules": [
                "do not chase one-line limit-up fills in backtest or simulation",
                "do not add after a large markup without fresh confirmation",
                "do not average down before forced divergence/support confirmation",
                "do not treat weak-label Dataset2 patterns as supervised profit evidence",
            ],
            "research_use_only": True,
            "review_only": True,
            "simulation_only": True,
        }


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
        self.experience_adapter = Dataset1ExperienceAdapter()
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
            "dataset1": self.experience_adapter.summary(),
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

        dataset1_experience = self.experience_adapter.summary()
        potential = self._run_potential_search(limit=max(1, limit // 2))
        symbols = self._select_symbols(potential, strategy_limit)
        coverage = self._coverage(symbols)
        refresh = (
            self._refresh_history(
                limit=min(limit, MAX_INLINE_HISTORY_REFRESH_LIMIT),
                days=min(history_days, MAX_INLINE_HISTORY_REFRESH_DAYS),
                requested_limit=limit,
                requested_days=history_days,
            )
            if refresh_history
            else None
        )
        if refresh_history:
            coverage = self._coverage(symbols)

        replay = self._strategy_replay(
            symbols=symbols,
            rules=source["strategy_set"].get("rules") or [],
            limit=strategy_limit,
            history_days=history_days,
        )
        backtest = self._backtest(replay["symbols"], history_days=history_days)
        signal_backtest = self._signal_backtest(replay, horizon_days=5)
        signal_optimization = self._signal_parameter_grid(replay)
        reclaim_watchlist = self._reclaim_watchlist(replay)
        reclaim_transition_study = self._reclaim_transition_study(replay)
        focus_phase_diagnostics = self._focus_phase_diagnostics()
        sandbox = self._sandbox(replay["signals"], horizon_days=5)
        phase_similarity_performance = self._phase_similarity_performance(replay, sandbox)
        benchmark_history = self._ensure_benchmark_history(
            days=min(history_days, MAX_INLINE_HISTORY_REFRESH_DAYS),
            enabled=self._phase_confidence_needs_benchmark(phase_similarity_performance),
        )
        phase_confidence_walk_forward = self._phase_confidence_walk_forward(phase_similarity_performance)
        artifact = self._write_model_candidate(
            source,
            dataset1_experience,
            replay,
            backtest,
            signal_backtest,
            signal_optimization,
            reclaim_watchlist,
            reclaim_transition_study,
            focus_phase_diagnostics,
            phase_similarity_performance,
            phase_confidence_walk_forward,
            sandbox,
        ) if write_artifact and sandbox["evaluated_count"] else {
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
            "dataset1_experience": dataset1_experience,
            "potential_search": potential,
            "daily_bar_coverage": coverage,
            "history_refresh": refresh,
            "strategy_replay": replay,
            "backtest": backtest,
            "signal_backtest": signal_backtest,
            "signal_optimization": signal_optimization,
            "reclaim_watchlist": reclaim_watchlist,
            "reclaim_transition_study": reclaim_transition_study,
            "focus_phase_diagnostics": focus_phase_diagnostics,
            "phase_similarity_performance": phase_similarity_performance,
            "benchmark_history": benchmark_history,
            "phase_confidence_walk_forward": phase_confidence_walk_forward,
            "sandbox": sandbox,
            "model_candidate": artifact,
            "blocked_reasons": blocked_reasons,
            "next_action": self._next_action(
                status,
                replay,
                signal_backtest,
                sandbox,
                artifact,
                coverage,
                reclaim_watchlist,
                reclaim_transition_study,
            ),
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
        artifact_detail = self._load_model_candidate_detail(artifact)
        return {
            "run_id": row["id"],
            "artifact": artifact,
            "artifact_detail": artifact_detail,
            "created_at": row.get("created_at"),
            "completed_at": row.get("completed_at"),
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def latest_simulation_review_plan(self, limit: int = SIM_REVIEW_PLAN_MAX_ITEMS) -> dict[str, Any]:
        """Return the latest bounded dry-run plan derived from off-hour research."""
        limit = max(1, min(int(limit or SIM_REVIEW_PLAN_MAX_ITEMS), 50))
        candidate = self.latest_model_candidate()
        if candidate.get("status") == "empty":
            return {
                "status": "empty",
                "reason": "no_offhour_model_candidate",
                "candidate_count": 0,
                "ready_dry_run_candidate_count": 0,
                "candidates": [],
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            }

        detail = candidate.get("artifact_detail") or {}
        plan = detail.get("simulation_review_plan") or {}
        if not plan:
            return {
                "status": "missing",
                "reason": "latest_candidate_has_no_simulation_review_plan",
                "run_id": candidate.get("run_id"),
                "artifact": candidate.get("artifact"),
                "candidate_count": 0,
                "ready_dry_run_candidate_count": 0,
                "candidates": [],
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            }

        candidates = list(plan.get("candidates") or [])[:limit]
        ready_count = sum(
            1 for item in candidates if item.get("recommended_mode") == "dry_run_screen_candidate"
        )
        return {
            "schema_version": "latest_simulation_review_plan.v1",
            "status": plan.get("status", "unknown"),
            "run_id": candidate.get("run_id"),
            "artifact": candidate.get("artifact"),
            "artifact_detail_status": detail.get("status"),
            "data_freshness": plan.get("data_freshness") or {},
            "strategy_overlays": (plan.get("strategy_overlays") or [])[:SIM_REVIEW_PLAN_MAX_STRATEGY_OVERLAYS],
            "strategy_overlay_count": plan.get("strategy_overlay_count", 0),
            "candidate_count": len(candidates),
            "total_candidate_count": plan.get("candidate_count", len(plan.get("candidates") or [])),
            "ready_dry_run_candidate_count": ready_count,
            "total_ready_dry_run_candidate_count": plan.get("ready_dry_run_candidate_count", ready_count),
            "candidates": candidates,
            "portfolio_limits": plan.get("portfolio_limits") or {},
            "permission_policy": plan.get("permission_policy") or {},
            "supervisor_notes": plan.get("supervisor_notes") or [],
            "allowed_effect": "read_latest_review_plan_only",
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def latest_strategy_learning_packet(self, limit: int = 8) -> dict[str, Any]:
        """Return a compact, review-only learning packet for Codex supervision."""
        limit = max(1, min(int(limit or 8), 20))
        candidate = self.latest_model_candidate()
        if candidate.get("status") == "empty":
            return {
                "schema_version": "offhour_strategy_learning_supervisor_packet.v1",
                "status": "empty",
                "reason": "no_offhour_model_candidate",
                "learning_readiness": "blocked",
                "candidates": [],
                "next_action": "Run offhour research loop before building a strategy learning packet.",
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            }

        detail = candidate.get("artifact_detail") or {}
        if detail.get("status") != "loaded":
            return {
                "schema_version": "offhour_strategy_learning_supervisor_packet.v1",
                "status": "blocked",
                "reason": "latest_model_candidate_detail_not_loaded",
                "run_id": candidate.get("run_id"),
                "artifact_detail_status": detail.get("status"),
                "learning_readiness": "blocked",
                "candidates": [],
                "next_action": "Regenerate the offhour model-candidate artifact or fix artifact loading.",
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            }

        review_plan = self.latest_simulation_review_plan(limit=limit)
        signal_optimization = detail.get("signal_optimization") or {}
        stable = signal_optimization.get("selected_stable_candidate") or {}
        stable_metrics = self._strategy_learning_stable_metrics(stable)
        rule_memory = detail.get("rule_family_performance_memory") or {}
        synthesis = detail.get("strategy_synthesis") or {}
        active = synthesis.get("active_simulation_hypothesis") or {}
        focus = detail.get("focus_phase_diagnostics") or {}
        phase_similarity = detail.get("phase_similarity_performance") or {}
        phase_walk = detail.get("phase_confidence_walk_forward") or {}
        priority = detail.get("candidate_review_priority_framework") or {}

        candidates = [
            self._strategy_learning_candidate(item, stable_metrics, priority)
            for item in (review_plan.get("candidates") or [])[:limit]
        ]
        ready_count = sum(1 for item in candidates if item.get("recommended_mode") == "dry_run_screen_candidate")
        passed_20pct = bool(stable_metrics.get("validation_return_pct", 0) >= 20)
        high_confidence_count = sum(
            1
            for item in candidates
            if str(item.get("confidence_tier") or "").startswith("high_confidence")
        )
        simulation_evidence = self._strategy_learning_simulation_evidence()
        candidate_shadow_outcomes = self._strategy_learning_candidate_shadow_outcomes(candidates)
        human_confirm_readiness = self._strategy_learning_human_confirm_readiness(
            stable_metrics=stable_metrics,
            simulation_evidence=simulation_evidence,
            candidates=candidates,
        )
        confidence_calibration = self._strategy_learning_confidence_calibration(
            stable_metrics=stable_metrics,
            rule_memory=rule_memory,
            candidates=candidates,
            simulation_evidence=simulation_evidence,
            human_confirm_readiness=human_confirm_readiness,
        )
        simulation_training_plan = self._strategy_learning_simulation_training_plan(
            candidates=candidates,
            simulation_evidence=simulation_evidence,
            human_confirm_readiness=human_confirm_readiness,
            confidence_calibration=confidence_calibration,
        )
        strategy_scoring_matrix = self._strategy_learning_scoring_matrix(
            candidates=candidates,
            stable_metrics=stable_metrics,
            rule_memory=rule_memory,
            priority=priority,
            confidence_calibration=confidence_calibration,
        )
        learning_readiness = (
            "ready_for_supervised_dry_run_learning"
            if ready_count and passed_20pct
            else "needs_more_evidence"
        )

        return {
            "schema_version": "offhour_strategy_learning_supervisor_packet.v1",
            "status": "ready" if learning_readiness.startswith("ready") else "partial",
            "run_id": candidate.get("run_id"),
            "artifact": candidate.get("artifact"),
            "learning_readiness": learning_readiness,
            "evidence_summary": {
                "selected_stable_candidate": stable_metrics,
                "rule_family_gate": detail.get("rule_family_review_gate") or {},
                "candidate_review_priority": {
                    "status": priority.get("status"),
                    "score": priority.get("review_priority_score"),
                    "tier": priority.get("review_priority_tier"),
                    "next_action": priority.get("next_action"),
                    "allowed_effect": priority.get("allowed_effect"),
                },
                "rule_family_top_groups": self._strategy_learning_rule_groups(rule_memory),
                "phase_confidence": {
                    "status": phase_walk.get("status"),
                    "passed_group_count": phase_walk.get("passed_group_count", 0),
                    "reason": phase_walk.get("reason"),
                },
                "focus_phase_next_actions": (focus.get("supervision") or {}).get("next_actions", [])[:5],
                "phase_similarity_top_groups": self._strategy_learning_phase_groups(phase_similarity),
            },
            "simulation_training_evidence": simulation_evidence,
            "candidate_shadow_outcome_review": candidate_shadow_outcomes,
            "confidence_calibration": confidence_calibration,
            "strategy_scoring_matrix": strategy_scoring_matrix,
            "simulation_training_plan": simulation_training_plan,
            "dataset1_dataset2_synthesis": {
                "summary": active.get("summary"),
                "dataset1_playbook": synthesis.get("dataset1_playbook", [])[:5],
                "dual_track_guidance": synthesis.get("dual_track_guidance") or {},
                "loss_attribution": (signal_optimization.get("signal_loss_attribution") or {}),
                "parameter_failure_attribution": (
                    signal_optimization.get("parameter_failure_attribution") or {}
                ),
                "learning_filter_candidates": (
                    signal_optimization.get("learning_filter_candidates") or []
                )[:5],
            },
            "candidate_count": len(candidates),
            "ready_dry_run_candidate_count": ready_count,
            "high_confidence_candidate_count": high_confidence_count,
            "candidates": candidates,
            "supervisor_checklist": [
                "Confirm /health.live_trading_enabled=false.",
                "Verify Tonghuashun simulated-account window before recording dry-run samples.",
                "Compare fresh trading-time signal with offhour confidence tier and Dataset1 phase risk.",
                "Record dry-run readback and blocked reasons into Dataset2 before any wider sizing discussion.",
                "Reject candidates with stale data, distribution-risk phase, or missing lot-size/cash fit.",
            ],
            "simulation_training_targets": {
                "min_supervised_dry_run_samples": 20,
                "min_supervised_readbacks": 20,
                "min_unique_symbols": 3,
                "min_evaluated_sessions": 5,
                "target_simulated_win_rate": 0.65,
                "target_average_return_pct": 5.0,
                "max_average_drawdown_pct": 6.0,
                "allowed_effect": "training_quality_gate_only",
            },
            "promotion_gate": {
                "target_validation_return_pct": 20.0,
                "stable_candidate_validation_return_pct": stable_metrics.get("validation_return_pct"),
                "stable_candidate_validation_win_rate": stable_metrics.get("validation_win_rate"),
                "passed_20pct_review_gate": passed_20pct,
                "human_confirm_readiness": human_confirm_readiness,
                "still_requires": [
                    "fresh_trading_time_risk_gates",
                    "sim_cockpit_verification",
                    "dry_run_readback",
                    "multi_day_simulated_outcome_review",
                    "human_review_before_any_real-money permission",
                ],
            },
            "permission_policy": {
                "may_submit_order": False,
                "may_enable_screen_click": False,
                "may_write_rules_yaml": False,
                "may_write_model_artifact": False,
                "may_open_real_money_human_confirm": False,
                "may_change_live_trading": False,
                "allowed_effect": "codex_supervision_and_strategy_learning_only",
            },
            "next_action": (
                "Use the top high-confidence candidate for supervised dry-run learning after Sim-Cockpit verification."
                if high_confidence_count
                else "Collect more simulation readbacks and refresh offhour research before expanding candidates."
            ),
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _strategy_learning_scoring_matrix(
        self,
        candidates: list[dict[str, Any]],
        stable_metrics: dict[str, Any],
        rule_memory: dict[str, Any],
        priority: dict[str, Any],
        confidence_calibration: dict[str, Any],
    ) -> dict[str, Any]:
        """Score review candidates across Dataset1/Dataset2 learning dimensions."""
        top_rule_groups = rule_memory.get("top_backtest_groups") or []
        top_pattern_ids = {
            str(item.get("pattern_id"))
            for item in top_rule_groups[:10]
            if item.get("pattern_id")
        }
        stable_validation_return = self._float_or_zero(stable_metrics.get("validation_return_pct"))
        stable_validation_win_rate = self._float_or_zero(stable_metrics.get("validation_win_rate"))
        global_priority_high = priority.get("review_priority_tier") == "high_review_priority"
        global_confidence_tier = confidence_calibration.get("tier")
        rows = []

        for rank, item in enumerate(candidates, start=1):
            confidence_tier = str(item.get("confidence_tier") or "")
            action_label = str(item.get("action_label") or "")
            pattern_id = str(item.get("pattern_id") or "")
            risk_level = str(item.get("risk_level") or "").lower()
            strategy = item.get("strategy_evidence") or {}
            position_plan = item.get("position_plan") or {}
            blockers = list(item.get("blockers") or [])
            caution_flags = list(item.get("caution_flags") or [])

            phase_score = 0.0
            phase_reasons: list[str] = []
            if confidence_tier.startswith("high_confidence"):
                phase_score += 8
                phase_reasons.append("offhour_high_confidence_candidate")
            elif "medium_confidence" in confidence_tier:
                phase_score += 5
                phase_reasons.append("offhour_medium_confidence_candidate")
            if stable_validation_return >= 20.0:
                phase_score += 5
                phase_reasons.append("stable_validation_return_above_20pct")
            if stable_validation_win_rate >= 0.58:
                phase_score += 4
                phase_reasons.append("stable_validation_win_rate_above_review_gate")
            if not self._has_distribution_risk(blockers + caution_flags):
                phase_score += 3
                phase_reasons.append("no_distribution_or_late_cycle_flag")

            volume_price_score = 0.0
            volume_reasons: list[str] = []
            if action_label == "SIM_BUY_CANDIDATE":
                volume_price_score += 6
                volume_reasons.append("dataset2_buy_candidate_signal")
            elif action_label == "WAIT_CONFIRMATION":
                volume_price_score += 4
                volume_reasons.append("dataset2_confirmation_signal")
            if pattern_id in top_pattern_ids:
                volume_price_score += 5
                volume_reasons.append("pattern_in_top_rule_family_memory")
            if risk_level in {"low", "medium", "medium_low"}:
                volume_price_score += 4
                volume_reasons.append("rule_risk_level_within_review_range")
            if self._float_or_zero(strategy.get("win_rate")) >= 0.58:
                volume_price_score += 3
                volume_reasons.append("candidate_strategy_win_rate_above_gate")
            if self._float_or_zero(strategy.get("average_return_pct")) > 0:
                volume_price_score += 2
                volume_reasons.append("candidate_strategy_average_return_positive")

            entry_timing_score = 0.0
            entry_reasons: list[str] = []
            if item.get("recommended_mode") == "dry_run_screen_candidate":
                entry_timing_score += 5
                entry_reasons.append("eligible_for_dry_run_review_mode")
            if strategy.get("walk_forward_status") == "passed_for_simulation_review":
                entry_timing_score += 4
                entry_reasons.append("walk_forward_candidate_passed_review")
            if not blockers:
                entry_timing_score += 4
                entry_reasons.append("no_offhour_blockers")
            if action_label == "WAIT_CONFIRMATION":
                entry_timing_score += 2
                entry_reasons.append("entry_requires_confirmation_not_chase")

            exit_discipline_score = 0.0
            exit_reasons: list[str] = []
            max_initial_ratio = self._float_or_zero(position_plan.get("max_initial_position_ratio"))
            if max_initial_ratio and max_initial_ratio <= SIM_REVIEW_PLAN_MAX_INITIAL_POSITION_RATIO:
                exit_discipline_score += 5
                exit_reasons.append("initial_position_within_two_percent_review_cap")
            if position_plan.get("staged_add_policy"):
                exit_discipline_score += 4
                exit_reasons.append("staged_add_policy_present")
            else:
                exit_discipline_score += 2
                exit_reasons.append("default_small_probe_policy_required")
            if item.get("next_session_validation"):
                exit_discipline_score += 3
                exit_reasons.append("next_session_validation_checks_present")
            if item.get("invalidation_signals"):
                exit_discipline_score += 3
                exit_reasons.append("invalidation_signals_present")

            execution_readiness_score = 0.0
            execution_reasons: list[str] = []
            if position_plan.get("max_initial_cash"):
                execution_readiness_score += 4
                execution_reasons.append("cash_cap_available")
            if item.get("training_contract"):
                execution_readiness_score += 4
                execution_reasons.append("training_contract_available")
            if settings.enable_live_trading is False:
                execution_readiness_score += 4
                execution_reasons.append("health_policy_live_trading_disabled")
            if global_priority_high:
                execution_readiness_score += 3
                execution_reasons.append("global_review_priority_high")

            risk_penalty = 0.0
            risk_reasons: list[str] = []
            for reason in blockers:
                risk_penalty += 8
                risk_reasons.append(f"blocker:{reason}")
            for reason in caution_flags:
                risk_penalty += 3
                risk_reasons.append(f"caution:{reason}")
            if self._has_distribution_risk(blockers + caution_flags):
                risk_penalty += 8
                risk_reasons.append("distribution_or_completed_markup_risk")
            if confidence_tier.startswith("low_confidence"):
                risk_penalty += 5
                risk_reasons.append("low_confidence_candidate")
            if global_confidence_tier == "needs_research_replay":
                risk_penalty += 5
                risk_reasons.append("global_confidence_needs_research_replay")

            gross_score = (
                phase_score
                + volume_price_score
                + entry_timing_score
                + exit_discipline_score
                + execution_readiness_score
            )
            final_score = max(0.0, min(100.0, gross_score - risk_penalty))
            if final_score >= 75 and not blockers:
                tier = "high_priority_supervised_dry_run"
            elif final_score >= 60 and not blockers:
                tier = "medium_priority_supervised_dry_run"
            elif final_score >= 45:
                tier = "watch_or_collect_more_evidence"
            else:
                tier = "blocked_or_low_priority"
            candidate_win_rate = self._float_or_zero(strategy.get("win_rate"))
            candidate_average_return = self._float_or_zero(strategy.get("average_return_pct"))
            supports_20pct_goal = bool(
                stable_validation_return >= 20.0
                and stable_validation_win_rate >= 0.58
                and candidate_win_rate >= 0.58
                and candidate_average_return > 0
                and risk_penalty <= 5
                and not blockers
            )

            rows.append(
                {
                    "rank": rank,
                    "symbol": item.get("symbol"),
                    "pattern_id": item.get("pattern_id"),
                    "action_label": item.get("action_label"),
                    "confidence_tier": item.get("confidence_tier"),
                    "score": round(final_score, 6),
                    "gross_score": round(gross_score, 6),
                    "tier": tier,
                    "components": {
                        "phase_score": {
                            "score": round(phase_score, 6),
                            "max_score": 20,
                            "reasons": phase_reasons,
                        },
                        "volume_price_score": {
                            "score": round(volume_price_score, 6),
                            "max_score": 20,
                            "reasons": volume_reasons,
                        },
                        "entry_timing_score": {
                            "score": round(entry_timing_score, 6),
                            "max_score": 15,
                            "reasons": entry_reasons,
                        },
                        "exit_discipline_score": {
                            "score": round(exit_discipline_score, 6),
                            "max_score": 15,
                            "reasons": exit_reasons,
                        },
                        "execution_readiness_score": {
                            "score": round(execution_readiness_score, 6),
                            "max_score": 15,
                            "reasons": execution_reasons,
                        },
                        "risk_penalty": {
                            "score": round(risk_penalty, 6),
                            "reasons": risk_reasons,
                        },
                    },
                    "outcome_evidence": {
                        "candidate_strategy_win_rate": candidate_win_rate,
                        "candidate_strategy_average_return_pct": candidate_average_return,
                        "candidate_walk_forward_status": strategy.get("walk_forward_status"),
                        "stable_validation_return_pct": stable_validation_return,
                        "stable_validation_win_rate": stable_validation_win_rate,
                        "supports_20pct_goal": supports_20pct_goal,
                        "requires_supervised_outcome_review": True,
                    },
                    "recommended_learning_action": self._strategy_score_next_action(tier),
                    "may_change_strategy_weight_now": False,
                    "may_submit_order": False,
                    "may_enable_screen_click": False,
                    "review_only": True,
                    "simulation_only": True,
                    "live_trading_enabled": settings.enable_live_trading,
                }
            )

        rows.sort(key=lambda row: (-float(row.get("score") or 0), int(row.get("rank") or 0)))
        top_row = rows[0] if rows else {}
        top_outcome = top_row.get("outcome_evidence") or {}
        return {
            "schema_version": "strategy_learning_scoring_matrix.v1",
            "status": "ready" if rows else "empty",
            "method": "dataset1_experience_priors_plus_dataset2_rule_memory_plus_execution_readiness",
            "score_layers": [
                "phase_score",
                "volume_price_score",
                "entry_timing_score",
                "exit_discipline_score",
                "execution_readiness_score",
                "risk_penalty",
            ],
            "top_candidates": rows[:8],
            "top_symbol": rows[0].get("symbol") if rows else None,
            "target_alignment": {
                "offline_20pct_gate_passed": stable_validation_return >= 20.0,
                "stable_validation_return_pct": stable_validation_return,
                "stable_validation_win_rate": stable_validation_win_rate,
                "top_candidate_supports_20pct_goal": top_outcome.get("supports_20pct_goal") is True,
                "top_candidate_strategy_win_rate": top_outcome.get("candidate_strategy_win_rate"),
                "top_candidate_strategy_average_return_pct": top_outcome.get("candidate_strategy_average_return_pct"),
                "still_requires": [
                    "supervised_dry_run_samples",
                    "supervised_readbacks",
                    "multi_symbol_coverage",
                    "multi_session_outcome_review",
                    "simulated_win_rate_return_drawdown_evidence",
                ],
                "allowed_effect": "target_alignment_reporting_only",
            },
            "permission_policy": {
                "may_change_strategy_weight_now": False,
                "may_submit_order": False,
                "may_enable_screen_click": False,
                "may_open_real_money_human_confirm": False,
                "allowed_effect": "candidate_learning_priority_only",
            },
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _has_distribution_risk(self, values: list[Any]) -> bool:
        risk_terms = (
            "distribution",
            "post_distribution",
            "late_cycle",
            "completed_markup",
            "completed_distribution",
            "late_markup",
            "high_position",
        )
        joined = " ".join(str(value).lower() for value in values)
        return any(term in joined for term in risk_terms)

    def _strategy_score_next_action(self, tier: str) -> str:
        if tier == "high_priority_supervised_dry_run":
            return "Prioritize for supervised detect_only/dry_run_screen sample collection after current window and risk gates pass."
        if tier == "medium_priority_supervised_dry_run":
            return "Use as a backup supervised dry-run sample after the high-priority queue has enough diversity."
        if tier == "watch_or_collect_more_evidence":
            return "Keep on watchlist and collect more market/readback evidence before expanding sample allocation."
        return "Do not allocate supervised samples until blockers or evidence gaps are resolved."

    def _strategy_learning_simulation_training_plan(
        self,
        candidates: list[dict[str, Any]],
        simulation_evidence: dict[str, Any],
        human_confirm_readiness: dict[str, Any],
        confidence_calibration: dict[str, Any],
    ) -> dict[str, Any]:
        targets = {
            "min_supervised_dry_run_samples": 20,
            "min_supervised_readbacks": 20,
            "min_unique_symbols": 3,
            "min_evaluated_sessions": 5,
        }
        outcome_review = simulation_evidence.get("outcome_review") or {}
        current = {
            "dry_run_count": int(simulation_evidence.get("dry_run_count") or 0),
            "readback_count": int(simulation_evidence.get("readback_count") or 0),
            "unique_symbol_count": int(simulation_evidence.get("unique_symbol_count") or 0),
            "evaluated_session_count": int(outcome_review.get("evaluated_session_count") or 0),
        }
        gaps = {
            "dry_run_samples": max(0, targets["min_supervised_dry_run_samples"] - current["dry_run_count"]),
            "readbacks": max(0, targets["min_supervised_readbacks"] - current["readback_count"]),
            "unique_symbols": max(0, targets["min_unique_symbols"] - current["unique_symbol_count"]),
            "evaluated_sessions": max(0, targets["min_evaluated_sessions"] - current["evaluated_session_count"]),
        }
        missing_requirements = set(human_confirm_readiness.get("missing_requirements") or [])
        eligible_candidates = [
            item
            for item in candidates
            if item.get("recommended_mode") == "dry_run_screen_candidate" and not item.get("blockers")
        ]
        warnings = []
        if len({item.get("symbol") for item in eligible_candidates if item.get("symbol")}) < targets["min_unique_symbols"]:
            warnings.append("insufficient_candidate_symbol_diversity_for_target")
        if confidence_calibration.get("tier") == "needs_research_replay":
            warnings.append("offline_confidence_too_low_for_sample_expansion")
        if "simulated_drawdown_target" in missing_requirements:
            warnings.append("outcome_drawdown_not_yet_verified")

        remaining_batch = gaps["dry_run_samples"]
        queue = []
        for index, item in enumerate(eligible_candidates[:5]):
            confidence_tier = str(item.get("confidence_tier") or "")
            if confidence_tier.startswith("high_confidence"):
                default_batch = 8
            elif "medium_confidence" in confidence_tier:
                default_batch = 6
            else:
                default_batch = 3
            if remaining_batch > 0:
                target_samples = min(default_batch, remaining_batch)
                remaining_batch -= target_samples
            else:
                target_samples = 0
            queue.append(
                {
                    "rank": index + 1,
                    "symbol": item.get("symbol"),
                    "confidence_tier": item.get("confidence_tier"),
                    "recommended_mode": item.get("recommended_mode"),
                    "target_next_dry_run_samples": target_samples,
                    "minimum_readbacks_required": target_samples,
                    "outcome_windows": ["1d", "3d", "5d"],
                    "max_first_probe_quantity": 100,
                    "max_first_probe_cash_pct": 0.03,
                    "sample_mode": "detect_only_then_dry_run_screen",
                    "requires": [
                        "health_live_trading_disabled",
                        "sim_cockpit_window_verified",
                        "fresh_trading_time_risk_gates",
                        "dry_run_action_recorded",
                        "readback_recorded",
                    ],
                    "stop_conditions": [
                        "real_account_or_broker_terms_detected",
                        "risk_gate_blocked",
                        "stale_or_missing_price",
                        "drawdown_exceeds_training_target",
                        "screen_click_permission_missing",
                    ],
                    "allowed_effect": "sample_collection_instruction_only",
                    "review_only": True,
                    "simulation_only": True,
                    "live_trading_enabled": settings.enable_live_trading,
                }
            )

        if remaining_batch > 0 and queue:
            queue[0]["target_next_dry_run_samples"] += remaining_batch
            queue[0]["minimum_readbacks_required"] += remaining_batch
            warnings.append("sample_gap_exceeds_diversified_queue_capacity")
        elif remaining_batch > 0:
            warnings.append("no_eligible_dry_run_candidates")

        status = "target_met" if not any(gaps.values()) else "needs_supervised_samples"
        if gaps["dry_run_samples"] == 0 and gaps["readbacks"] == 0 and gaps["evaluated_sessions"] > 0:
            status = "needs_future_outcome_review"
        return {
            "schema_version": "strategy_learning_simulation_training_plan.v1",
            "status": status,
            "targets": targets,
            "current": current,
            "remaining_requirements": gaps,
            "candidate_queue": queue,
            "batch_policy": {
                "preferred_symbol_count": targets["min_unique_symbols"],
                "max_candidates_in_next_batch": 5,
                "default_high_confidence_samples": 8,
                "default_medium_confidence_samples": 6,
                "collect_readback_for_every_sample": True,
                "do_not_submit_orders_from_this_plan": True,
            },
            "warnings": warnings,
            "next_action": (
                "Collect supervised dry-run/readback samples from the queue after simulated-window verification."
                if queue and status != "target_met"
                else "Refresh off-hour research or wait for outcome bars before changing confidence."
            ),
            "allowed_effect": "sample_collection_plan_only",
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _strategy_learning_confidence_calibration(
        self,
        stable_metrics: dict[str, Any],
        rule_memory: dict[str, Any],
        candidates: list[dict[str, Any]],
        simulation_evidence: dict[str, Any],
        human_confirm_readiness: dict[str, Any],
    ) -> dict[str, Any]:
        components: list[dict[str, Any]] = []

        def add_component(
            name: str,
            score: float,
            max_score: float,
            reasons: list[str],
            missing: list[str],
        ) -> None:
            components.append(
                {
                    "name": name,
                    "score": round(score, 6),
                    "max_score": max_score,
                    "reasons": reasons,
                    "missing": missing,
                }
            )

        validation_return = self._float_or_zero(stable_metrics.get("validation_return_pct"))
        validation_win_rate = self._float_or_zero(stable_metrics.get("validation_win_rate"))
        walk_forward_return = self._float_or_zero(stable_metrics.get("walk_forward_return_pct"))
        walk_forward_win_rate = self._float_or_zero(stable_metrics.get("walk_forward_win_rate"))
        score = 0.0
        reasons: list[str] = []
        missing: list[str] = []
        if validation_return >= 20.0:
            score += 15
            reasons.append("validation_return_above_20pct")
        else:
            missing.append("validation_return_below_20pct")
        if validation_win_rate >= 0.65:
            score += 10
            reasons.append("validation_win_rate_above_65pct")
        else:
            missing.append("validation_win_rate_below_65pct")
        if walk_forward_return > 0:
            score += 5
            reasons.append("walk_forward_return_positive")
        else:
            missing.append("walk_forward_return_not_positive")
        if walk_forward_win_rate >= 0.65:
            score += 5
            reasons.append("walk_forward_win_rate_above_65pct")
        else:
            missing.append("walk_forward_win_rate_below_65pct")
        add_component("offline_strategy_evidence", score, 35, reasons, missing)

        top_group = ((rule_memory.get("top_backtest_groups") or []) + [{}])[0]
        score = 0.0
        reasons = []
        missing = []
        if top_group:
            win_rate = self._float_or_zero(top_group.get("win_rate"))
            avg_return = self._float_or_zero(top_group.get("average_return_pct"))
            trade_count = int(top_group.get("trade_count") or 0)
            worst_return = self._float_or_zero(top_group.get("worst_return_pct"))
            if win_rate >= 0.58:
                score += 8
                reasons.append("top_rule_group_win_rate_above_gate")
            else:
                missing.append("top_rule_group_win_rate_below_gate")
            if avg_return > 0:
                score += 6
                reasons.append("top_rule_group_average_return_positive")
            else:
                missing.append("top_rule_group_average_return_not_positive")
            if trade_count >= 20:
                score += 4
                reasons.append("top_rule_group_trade_count_sufficient")
            else:
                missing.append("top_rule_group_trade_count_insufficient")
            if worst_return >= -8.0:
                score += 2
                reasons.append("top_rule_group_worst_return_within_review_limit")
            else:
                missing.append("top_rule_group_worst_return_too_deep")
        else:
            missing.append("no_rule_family_backtest_group")
        add_component("rule_family_evidence", score, 20, reasons, missing)

        high_confidence = [
            item for item in candidates if str(item.get("confidence_tier") or "").startswith("high_confidence")
        ]
        ready_candidates = [
            item for item in candidates if item.get("recommended_mode") == "dry_run_screen_candidate"
        ]
        first_candidate = candidates[0] if candidates else {}
        score = 0.0
        reasons = []
        missing = []
        if high_confidence:
            score += 10
            reasons.append("high_confidence_candidate_available")
        else:
            missing.append("no_high_confidence_candidate")
        if ready_candidates:
            score += 5
            reasons.append("dry_run_candidate_available")
        else:
            missing.append("no_dry_run_candidate")
        if first_candidate and not first_candidate.get("blockers"):
            score += 5
            reasons.append("top_candidate_has_no_offhour_blockers")
        else:
            missing.append("top_candidate_blocked_or_missing")
        add_component("candidate_quality", score, 20, reasons, missing)

        dry_run_count = int(simulation_evidence.get("dry_run_count") or 0)
        readback_count = int(simulation_evidence.get("readback_count") or 0)
        unique_symbol_count = int(simulation_evidence.get("unique_symbol_count") or 0)
        score = 0.0
        reasons = []
        missing = []
        if dry_run_count >= 20:
            score += 5
            reasons.append("supervised_dry_run_samples_sufficient")
        else:
            missing.append("supervised_dry_run_samples_insufficient")
        if readback_count >= 20:
            score += 5
            reasons.append("supervised_readbacks_sufficient")
        else:
            missing.append("supervised_readbacks_insufficient")
        if unique_symbol_count >= 3:
            score += 5
            reasons.append("multi_symbol_simulation_coverage_sufficient")
        else:
            missing.append("multi_symbol_simulation_coverage_insufficient")
        add_component("simulation_execution_evidence", score, 15, reasons, missing)

        outcome_review = simulation_evidence.get("outcome_review") or {}
        evaluated_sessions = int(outcome_review.get("evaluated_session_count") or 0)
        win_rate_5d = outcome_review.get("win_rate_5d")
        average_return_5d = outcome_review.get("average_return_pct_5d")
        average_drawdown = outcome_review.get("average_max_drawdown_pct")
        score = 0.0
        reasons = []
        missing = []
        if evaluated_sessions >= 5:
            score += 3
            reasons.append("multi_session_outcome_review_ready")
        else:
            missing.append("multi_session_outcome_review_insufficient")
        if win_rate_5d is not None and self._float_or_zero(win_rate_5d) >= 0.65:
            score += 3
            reasons.append("simulated_5d_win_rate_above_target")
        else:
            missing.append("simulated_5d_win_rate_below_or_missing")
        if average_return_5d is not None and self._float_or_zero(average_return_5d) >= 5.0:
            score += 2
            reasons.append("simulated_5d_average_return_above_target")
        else:
            missing.append("simulated_5d_average_return_below_or_missing")
        if average_drawdown is not None and abs(self._float_or_zero(average_drawdown)) <= 6.0:
            score += 2
            reasons.append("simulated_average_drawdown_within_target")
        else:
            missing.append("simulated_average_drawdown_missing_or_too_deep")
        add_component("simulation_outcome_evidence", score, 10, reasons, missing)

        total_score = round(sum(item["score"] for item in components), 6)
        component_scores = {item["name"]: item["score"] for item in components}
        missing_requirements = list(human_confirm_readiness.get("missing_requirements") or [])
        passed_offline = validation_return >= 20.0 and validation_win_rate >= 0.65
        has_high_candidate = bool(high_confidence)
        if human_confirm_readiness.get("status") == "ready_for_human_confirm_review" and total_score >= 85:
            tier = "ready_for_human_confirm_review"
        elif passed_offline and has_high_candidate:
            tier = "backtest_ready_simulation_needed"
        elif total_score >= 40:
            tier = "watch_and_collect_more_evidence"
        else:
            tier = "needs_research_replay"

        component_missing = [
            missing_item
            for component in components
            for missing_item in component["missing"]
        ]
        top_blockers = []
        for item in missing_requirements + component_missing:
            if item not in top_blockers:
                top_blockers.append(item)
        return {
            "schema_version": "strategy_learning_confidence_calibration.v1",
            "score": total_score,
            "max_score": 100,
            "tier": tier,
            "components": components,
            "component_scores": component_scores,
            "top_blockers": top_blockers[:10],
            "interpretation": (
                "Offline evidence can justify supervised simulation learning, but permission must stay capped "
                "until dry-run/readback/outcome evidence clears the promotion gate."
                if tier == "backtest_ready_simulation_needed"
                else "Use this score as a reporting signal only; it does not change trading permissions."
            ),
            "allowed_effect": "confidence_reporting_only",
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _strategy_learning_stable_metrics(self, stable: dict[str, Any]) -> dict[str, Any]:
        metrics = stable.get("metrics") or stable.get("evidence") or {}
        validation_metrics = stable.get("source_validation_metrics") or {}
        params = stable.get("parameters") or {}
        return {
            "status": stable.get("status") or stable.get("selected_status"),
            "parameters": params,
            "validation_return_pct": self._float_or_zero(
                stable.get("validation_return_pct")
                or stable.get("validation_cumulative_return_pct")
                or validation_metrics.get("equal_weight_cumulative_return_pct")
                or metrics.get("validation_return_pct")
                or metrics.get("cumulative_return_pct")
            ),
            "validation_win_rate": self._float_or_zero(
                stable.get("validation_win_rate")
                or validation_metrics.get("win_rate")
                or metrics.get("validation_win_rate")
                or metrics.get("win_rate")
            ),
            "walk_forward_return_pct": self._float_or_zero(
                stable.get("walk_forward_return_pct")
                or stable.get("walk_forward_cumulative_return_pct")
                or stable.get("total_equal_weight_cumulative_return_pct")
                or metrics.get("walk_forward_return_pct")
            ),
            "walk_forward_win_rate": self._float_or_zero(
                stable.get("walk_forward_win_rate")
                or stable.get("weighted_win_rate")
                or metrics.get("walk_forward_win_rate")
            ),
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _strategy_learning_rule_groups(self, memory: dict[str, Any]) -> list[dict[str, Any]]:
        groups = []
        for item in (memory.get("top_backtest_groups") or [])[:5]:
            groups.append(
                {
                    "pattern_id": item.get("pattern_id"),
                    "pattern_name": item.get("pattern_name"),
                    "action_label": item.get("action_label"),
                    "risk_level": item.get("risk_level"),
                    "trade_count": item.get("trade_count"),
                    "win_rate": item.get("win_rate"),
                    "average_return_pct": item.get("average_return_pct"),
                    "total_return_pct": item.get("total_return_pct"),
                    "worst_return_pct": item.get("worst_return_pct"),
                    "review_priority_score": item.get("review_priority_score"),
                    "symbols": (item.get("symbols") or [])[:8],
                    "learning_takeaway": self._rule_group_takeaway(item),
                    "review_only": True,
                    "simulation_only": True,
                }
            )
        return groups

    def _strategy_learning_phase_groups(self, phase_similarity: dict[str, Any]) -> list[dict[str, Any]]:
        rows = []
        for item in (phase_similarity.get("by_group") or [])[:5]:
            rows.append(
                {
                    "key": item.get("key"),
                    "core_symbol": item.get("core_symbol"),
                    "target_latest_phase": item.get("target_latest_phase"),
                    "sample_role": item.get("sample_role"),
                    "confidence_tier": item.get("confidence_tier"),
                    "confidence_score": item.get("confidence_score"),
                    "win_rate": item.get("win_rate"),
                    "average_close_return_pct": item.get("average_close_return_pct"),
                    "average_min_return_pct": item.get("average_min_return_pct"),
                    "suggested_treatment": item.get("suggested_treatment"),
                    "downside_risk_note": item.get("downside_risk_note"),
                    "review_only": True,
                    "simulation_only": True,
                }
            )
        return rows

    def _strategy_learning_candidate(
        self,
        item: dict[str, Any],
        stable_metrics: dict[str, Any],
        priority: dict[str, Any],
    ) -> dict[str, Any]:
        quality = item.get("evidence_quality") or {}
        position = item.get("position_plan") or {}
        strategy = item.get("best_strategy") or {}
        blockers = item.get("blockers") or []
        caution_flags = item.get("caution_flags") or []
        confidence_tier = quality.get("confidence_tier")
        return {
            "symbol": item.get("symbol"),
            "recommended_mode": item.get("recommended_mode"),
            "confidence_tier": confidence_tier,
            "confidence_score": quality.get("confidence_score"),
            "priority_score": item.get("priority_score"),
            "confidence_adjusted_priority_score": item.get("confidence_adjusted_priority_score"),
            "signal_date": item.get("signal_date"),
            "pattern_id": item.get("pattern_id"),
            "action_label": item.get("action_label"),
            "risk_level": item.get("risk_level"),
            "price": item.get("close") or item.get("latest_close") or item.get("signal_close"),
            "position_plan": {
                "max_initial_cash": position.get("max_initial_cash"),
                "max_initial_position_ratio": position.get("max_initial_position_ratio"),
                "max_confirmed_cash": position.get("max_confirmed_cash"),
                "staged_add_policy": position.get("staged_add_policy"),
            },
            "strategy_evidence": {
                "strategy_id": strategy.get("experiment_id"),
                "win_rate": strategy.get("win_rate"),
                "average_return_pct": strategy.get("average_return_pct"),
                "walk_forward_status": strategy.get("walk_forward_status"),
                "market_context_status": strategy.get("market_context_status"),
                "stable_validation_return_pct": stable_metrics.get("validation_return_pct"),
                "stable_validation_win_rate": stable_metrics.get("validation_win_rate"),
                "review_priority_tier": priority.get("review_priority_tier"),
            },
            "why_prioritized": self._candidate_learning_reasons(item, stable_metrics, priority),
            "next_session_validation": self._candidate_next_session_validation(item),
            "invalidation_signals": self._candidate_invalidation_signals(item),
            "training_contract": self._candidate_training_contract(item),
            "blockers": blockers,
            "caution_flags": caution_flags,
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _candidate_learning_reasons(
        self,
        item: dict[str, Any],
        stable_metrics: dict[str, Any],
        priority: dict[str, Any],
    ) -> list[str]:
        reasons = []
        quality = item.get("evidence_quality") or {}
        if str(quality.get("confidence_tier") or "").startswith("high_confidence"):
            reasons.append("highest_evidence_quality_candidate")
        if self._float_or_zero(stable_metrics.get("validation_return_pct")) >= 20:
            reasons.append("stable_candidate_validation_return_above_20pct")
        if self._float_or_zero(stable_metrics.get("validation_win_rate")) >= 0.58:
            reasons.append("stable_candidate_validation_win_rate_above_gate")
        if priority.get("review_priority_tier") == "high_review_priority":
            reasons.append("combined_review_priority_high")
        if item.get("recommended_mode") == "dry_run_screen_candidate":
            reasons.append("eligible_for_dry_run_review_only")
        if item.get("caution_flags"):
            reasons.append("requires_smaller_probe_due_to_caution_flags")
        return reasons or ["candidate_requires_more_evidence"]

    def _candidate_next_session_validation(self, item: dict[str, Any]) -> list[str]:
        triggers = item.get("next_session_triggers") or {}
        checks = [
            "fresh_quote_not_stale",
            "portfolio_risk_gates_not_blocked",
            "sim_cockpit_window_verified_before_dry_run",
            "record_execution_readback_for_dataset2",
        ]
        if triggers:
            checks.append("compare_fresh_market_with_next_session_triggers")
        if item.get("action_label") == "WAIT_CONFIRMATION":
            checks.append("wait_for_reclaim_or_green_confirmation")
        else:
            checks.append("avoid_chasing_if_open_gap_or_late_markup_distribution_risk")
        return checks

    def _candidate_invalidation_signals(self, item: dict[str, Any]) -> list[str]:
        signals = [
            "live_trading_enabled_true",
            "real_account_or_broker_terms_detected",
            "fresh_risk_gate_blocked",
            "missing_sim_cockpit_verification",
            "stale_or_missing_daily_bar_data",
        ]
        if item.get("blockers"):
            signals.append("offhour_review_plan_blockers_present")
        if "high_volatility_board_requires_smaller_probe" in set(item.get("caution_flags") or []):
            signals.append("board_volatility_requires_observe_or_minimum_probe")
        return signals

    def _candidate_training_contract(self, item: dict[str, Any]) -> dict[str, Any]:
        action_label = str(item.get("action_label") or "")
        caution_flags = item.get("caution_flags") or []
        base_success = [
            "dry_run_action_recorded",
            "execution_readback_recorded",
            "no_real_screen_click_for_review_sample",
            "fresh_quote_and_daily_bar_available",
        ]
        if action_label == "WAIT_CONFIRMATION":
            base_success.append("reclaim_or_green_confirmation_observed")
        else:
            base_success.append("no_late_markup_or_distribution_warning")
        failure_labels = [
            "risk_gate_blocked",
            "window_verification_failed",
            "stale_data",
            "gap_chase_or_late_markup",
            "next_session_drawdown_exceeds_plan",
        ]
        if caution_flags:
            failure_labels.append("caution_flag_requires_probe_downgrade")
        return {
            "schema_version": "candidate_simulation_training_contract.v1",
            "objective": "Collect supervised dry-run and readback evidence before changing confidence.",
            "sample_mode": "detect_only_then_dry_run_screen",
            "minimum_next_samples": 1,
            "preferred_outcome_windows": ["1d", "3d", "5d"],
            "success_labels": base_success,
            "failure_labels": failure_labels,
            "record_to": ["sim_cockpit_actions", "sim_cockpit_readbacks", "dataset2_training_candidates"],
            "allowed_effect": "training_sample_collection_only",
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _strategy_learning_simulation_evidence(self) -> dict[str, Any]:
        sources = (
            "offhour_simulation_review_plan",
            "dataset2_reclaim_review",
            "automation_simulation_plan",
        )
        placeholders = ", ".join("?" for _ in sources)
        actions = self.store.fetch_all(
            f"""
            SELECT id, symbol, action_type, status, price, quantity, signal_source, created_at
            FROM sim_cockpit_actions
            WHERE signal_source IN ({placeholders})
            ORDER BY id DESC
            LIMIT 200
            """,
            sources,
        )
        action_ids = [int(row["id"]) for row in actions if row.get("id") is not None]
        readbacks: list[dict[str, Any]] = []
        if action_ids:
            id_placeholders = ", ".join("?" for _ in action_ids)
            readbacks = self.store.fetch_all(
                f"""
                SELECT id, action_id, status, readback_type, symbol, created_at
                FROM sim_cockpit_readbacks
                WHERE action_id IN ({id_placeholders})
                ORDER BY id DESC
                LIMIT 300
                """,
                tuple(action_ids),
            )
        status_counts: dict[str, int] = {}
        source_counts: dict[str, int] = {}
        symbols: set[str] = set()
        for row in actions:
            status = str(row.get("status") or "unknown")
            source = str(row.get("signal_source") or "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1
            source_counts[source] = source_counts.get(source, 0) + 1
            if row.get("symbol"):
                symbols.add(str(row["symbol"]))
        readback_status_counts: dict[str, int] = {}
        for row in readbacks:
            status = str(row.get("status") or "unknown")
            readback_status_counts[status] = readback_status_counts.get(status, 0) + 1
        dry_run_count = status_counts.get("dry_run", 0)
        executed_count = status_counts.get("executed", 0)
        blocked_count = status_counts.get("blocked", 0)
        outcome_review = self._strategy_learning_simulation_outcome_review(actions)
        return {
            "schema_version": "strategy_learning_simulation_evidence.v1",
            "source_action_limit": 200,
            "action_count": len(actions),
            "dry_run_count": dry_run_count,
            "executed_count": executed_count,
            "blocked_count": blocked_count,
            "readback_count": len(readbacks),
            "unique_symbol_count": len(symbols),
            "status_counts": status_counts,
            "source_counts": source_counts,
            "readback_status_counts": readback_status_counts,
            "outcome_review": outcome_review,
            "latest_actions": [
                {
                    "id": row.get("id"),
                    "symbol": row.get("symbol"),
                    "action_type": row.get("action_type"),
                    "status": row.get("status"),
                    "signal_source": row.get("signal_source"),
                    "created_at": row.get("created_at"),
                }
                for row in actions[:10]
            ],
            "interpretation": (
                "Simulation evidence is enough for Dataset2 dry-run learning only; "
                "it cannot grant live trading or screen-click permission."
            ),
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _strategy_learning_simulation_outcome_review(
        self,
        actions: list[dict[str, Any]],
    ) -> dict[str, Any]:
        outcomes: list[dict[str, Any]] = []
        for action in actions:
            if str(action.get("action_type") or "") != "buy":
                continue
            if str(action.get("status") or "") not in {"dry_run", "executed"}:
                continue
            symbol = str(action.get("symbol") or "").upper()
            entry_price = self._float_or_zero(action.get("price"))
            action_date = self._date_prefix(str(action.get("created_at") or ""))
            if not symbol or entry_price <= 0 or not action_date:
                outcomes.append(
                    {
                        "action_id": action.get("id"),
                        "symbol": symbol or None,
                        "status": "pending",
                        "reason": "missing_symbol_price_or_action_date",
                    }
                )
                continue
            bars = self._future_daily_bars(symbol, action_date, limit=5)
            if not bars:
                outcomes.append(
                    {
                        "action_id": action.get("id"),
                        "symbol": symbol,
                        "entry_price": entry_price,
                        "action_date": action_date,
                        "status": "pending_future_bars",
                        "available_future_bar_count": 0,
                    }
                )
                continue
            outcome = {
                "schema_version": "sim_cockpit_dry_run_outcome.v1",
                "action_id": action.get("id"),
                "symbol": symbol,
                "entry_price": entry_price,
                "action_date": action_date,
                "status": "evaluated" if len(bars) >= 5 else "pending_future_bars",
                "available_future_bar_count": len(bars),
                "horizon_returns": self._horizon_returns(entry_price, bars),
                "max_return_pct": self._max_return_pct(entry_price, bars),
                "max_drawdown_pct": self._max_drawdown_pct(entry_price, bars),
                "last_evaluated_trade_date": bars[-1].get("trade_date"),
                "review_only": True,
                "simulation_only": True,
            }
            outcomes.append(outcome)

        evaluated = [item for item in outcomes if item.get("status") == "evaluated"]
        returns_5d = [
            self._float_or_zero((item.get("horizon_returns") or {}).get("5d_return_pct"))
            for item in evaluated
            if (item.get("horizon_returns") or {}).get("5d_return_pct") is not None
        ]
        drawdowns = [
            self._float_or_zero(item.get("max_drawdown_pct"))
            for item in evaluated
            if item.get("max_drawdown_pct") is not None
        ]
        win_count = sum(1 for value in returns_5d if value > 0)
        average_return = round(sum(returns_5d) / len(returns_5d), 6) if returns_5d else None
        average_drawdown = round(sum(drawdowns) / len(drawdowns), 6) if drawdowns else None
        return {
            "schema_version": "sim_cockpit_dry_run_outcome_review.v1",
            "status": "ready" if evaluated else "pending",
            "evaluated_session_count": len(evaluated),
            "pending_session_count": len(outcomes) - len(evaluated),
            "win_count_5d": win_count,
            "win_rate_5d": round(win_count / len(returns_5d), 6) if returns_5d else None,
            "average_return_pct_5d": average_return,
            "average_max_drawdown_pct": average_drawdown,
            "outcomes": outcomes[:20],
            "allowed_effect": "simulation_training_evaluation_only",
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _strategy_learning_candidate_shadow_outcomes(
        self,
        candidates: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Review candidate outcomes against local daily bars without granting permission."""
        outcomes: list[dict[str, Any]] = []
        for item in candidates[:20]:
            symbol = str(item.get("symbol") or "").upper()
            signal_date = self._date_prefix(str(item.get("signal_date") or ""))
            entry_price = self._float_or_zero(item.get("price"))
            if not symbol or not signal_date or entry_price <= 0:
                outcomes.append(
                    {
                        "schema_version": "strategy_candidate_shadow_outcome.v1",
                        "symbol": symbol or None,
                        "signal_date": signal_date,
                        "entry_price": entry_price if entry_price > 0 else None,
                        "status": "pending",
                        "reason": "missing_symbol_signal_date_or_price",
                        "source": "strategy_scoring_matrix_candidate",
                        "counts_toward_human_confirm": False,
                        "review_only": True,
                        "simulation_only": True,
                    }
                )
                continue

            bars = self._future_daily_bars(symbol, signal_date, limit=5)
            if not bars:
                outcomes.append(
                    {
                        "schema_version": "strategy_candidate_shadow_outcome.v1",
                        "symbol": symbol,
                        "signal_date": signal_date,
                        "entry_price": entry_price,
                        "status": "pending_future_bars",
                        "available_future_bar_count": 0,
                        "source": "strategy_scoring_matrix_candidate",
                        "counts_toward_human_confirm": False,
                        "review_only": True,
                        "simulation_only": True,
                    }
                )
                continue

            outcomes.append(
                {
                    "schema_version": "strategy_candidate_shadow_outcome.v1",
                    "symbol": symbol,
                    "signal_date": signal_date,
                    "entry_price": entry_price,
                    "status": "evaluated" if len(bars) >= 5 else "pending_future_bars",
                    "available_future_bar_count": len(bars),
                    "horizon_returns": self._horizon_returns(entry_price, bars),
                    "max_return_pct": self._max_return_pct(entry_price, bars),
                    "max_drawdown_pct": self._max_drawdown_pct(entry_price, bars),
                    "last_evaluated_trade_date": bars[-1].get("trade_date"),
                    "source": "strategy_scoring_matrix_candidate",
                    "counts_toward_human_confirm": False,
                    "review_only": True,
                    "simulation_only": True,
                }
            )

        evaluated = [item for item in outcomes if item.get("status") == "evaluated"]
        returns_5d = [
            self._float_or_zero((item.get("horizon_returns") or {}).get("5d_return_pct"))
            for item in evaluated
            if (item.get("horizon_returns") or {}).get("5d_return_pct") is not None
        ]
        drawdowns = [
            self._float_or_zero(item.get("max_drawdown_pct"))
            for item in evaluated
            if item.get("max_drawdown_pct") is not None
        ]
        win_count = sum(1 for value in returns_5d if value > 0)
        return {
            "schema_version": "strategy_candidate_shadow_outcome_review.v1",
            "status": "ready" if evaluated else "pending",
            "candidate_count": len(candidates),
            "evaluated_count": len(evaluated),
            "pending_count": len(outcomes) - len(evaluated),
            "win_count_5d": win_count,
            "win_rate_5d": round(win_count / len(returns_5d), 6) if returns_5d else None,
            "average_return_pct_5d": (
                round(sum(returns_5d) / len(returns_5d), 6) if returns_5d else None
            ),
            "average_max_drawdown_pct": (
                round(sum(drawdowns) / len(drawdowns), 6) if drawdowns else None
            ),
            "outcomes": outcomes[:20],
            "counts_toward_human_confirm": False,
            "allowed_effect": "historical_shadow_review_only",
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _future_daily_bars(self, symbol: str, action_date: str, limit: int = 5) -> list[dict[str, Any]]:
        rows = self.store.fetch_all(
            """
            SELECT trade_date, open, high, low, close, volume, amount, quality_status
            FROM daily_bar_cache
            WHERE upper(symbol) = ?
              AND trade_date > ?
              AND trade_date != 'ERROR'
              AND close IS NOT NULL
            ORDER BY trade_date ASC
            LIMIT ?
            """,
            (symbol.upper(), action_date, max(1, min(int(limit or 5), 20))),
        )
        return rows

    def _horizon_returns(self, entry_price: float, bars: list[dict[str, Any]]) -> dict[str, float | None]:
        result: dict[str, float | None] = {}
        for horizon in (1, 3, 5):
            key = f"{horizon}d_return_pct"
            if len(bars) < horizon:
                result[key] = None
                continue
            close = self._float_or_zero(bars[horizon - 1].get("close"))
            result[key] = round((close - entry_price) / entry_price * 100, 6) if entry_price > 0 else None
        return result

    def _max_return_pct(self, entry_price: float, bars: list[dict[str, Any]]) -> float | None:
        highs = [self._float_or_zero(row.get("high")) for row in bars if row.get("high") is not None]
        if not highs or entry_price <= 0:
            return None
        return round((max(highs) - entry_price) / entry_price * 100, 6)

    def _max_drawdown_pct(self, entry_price: float, bars: list[dict[str, Any]]) -> float | None:
        lows = [self._float_or_zero(row.get("low")) for row in bars if row.get("low") is not None]
        if not lows or entry_price <= 0:
            return None
        return round((min(lows) - entry_price) / entry_price * 100, 6)

    def _date_prefix(self, value: str) -> str | None:
        if not value:
            return None
        return value[:10] if len(value) >= 10 else None

    def _strategy_learning_human_confirm_readiness(
        self,
        stable_metrics: dict[str, Any],
        simulation_evidence: dict[str, Any],
        candidates: list[dict[str, Any]],
    ) -> dict[str, Any]:
        outcome_review = simulation_evidence.get("outcome_review") or {}
        evaluated_sessions = int(outcome_review.get("evaluated_session_count") or 0)
        win_rate_5d = outcome_review.get("win_rate_5d")
        average_return_5d = outcome_review.get("average_return_pct_5d")
        average_drawdown = outcome_review.get("average_max_drawdown_pct")
        checks = [
            {
                "name": "live_trading_disabled",
                "passed": settings.enable_live_trading is False,
                "value": settings.enable_live_trading,
                "required": False,
            },
            {
                "name": "validation_return_above_20pct",
                "passed": self._float_or_zero(stable_metrics.get("validation_return_pct")) >= 20.0,
                "value": stable_metrics.get("validation_return_pct"),
                "required": ">=20.0",
            },
            {
                "name": "validation_win_rate_above_65pct",
                "passed": self._float_or_zero(stable_metrics.get("validation_win_rate")) >= 0.65,
                "value": stable_metrics.get("validation_win_rate"),
                "required": ">=0.65",
            },
            {
                "name": "supervised_dry_run_samples",
                "passed": int(simulation_evidence.get("dry_run_count") or 0) >= 20,
                "value": simulation_evidence.get("dry_run_count", 0),
                "required": ">=20",
            },
            {
                "name": "supervised_readbacks",
                "passed": int(simulation_evidence.get("readback_count") or 0) >= 20,
                "value": simulation_evidence.get("readback_count", 0),
                "required": ">=20",
            },
            {
                "name": "multi_symbol_coverage",
                "passed": int(simulation_evidence.get("unique_symbol_count") or 0) >= 3,
                "value": simulation_evidence.get("unique_symbol_count", 0),
                "required": ">=3",
            },
            {
                "name": "high_confidence_candidate_available",
                "passed": any(
                    str(item.get("confidence_tier") or "").startswith("high_confidence")
                    for item in candidates
                ),
                "value": [
                    item.get("symbol")
                    for item in candidates
                    if str(item.get("confidence_tier") or "").startswith("high_confidence")
                ],
                "required": ">=1",
            },
            {
                "name": "multi_session_outcome_review",
                "passed": evaluated_sessions >= 5,
                "value": evaluated_sessions,
                "required": ">=5 evaluated sessions with acceptable drawdown",
            },
            {
                "name": "simulated_win_rate_target",
                "passed": win_rate_5d is not None and self._float_or_zero(win_rate_5d) >= 0.65,
                "value": win_rate_5d,
                "required": ">=0.65",
            },
            {
                "name": "simulated_average_return_target",
                "passed": average_return_5d is not None and self._float_or_zero(average_return_5d) >= 5.0,
                "value": average_return_5d,
                "required": ">=5.0",
            },
            {
                "name": "simulated_drawdown_target",
                "passed": average_drawdown is not None and abs(self._float_or_zero(average_drawdown)) <= 6.0,
                "value": average_drawdown,
                "required": "average max drawdown no worse than -6.0",
            },
        ]
        missing = [item["name"] for item in checks if not item["passed"]]
        return {
            "schema_version": "human_confirm_readiness_gate.v1",
            "status": "ready_for_human_confirm_review" if not missing else "not_ready_for_human_confirm",
            "missing_requirements": missing,
            "checks": checks,
            "allowed_effect": "readiness_report_only",
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _rule_group_takeaway(self, item: dict[str, Any]) -> str:
        action = item.get("action_label")
        win_rate = self._float_or_zero(item.get("win_rate"))
        avg = self._float_or_zero(item.get("average_return_pct"))
        if action == "WAIT_CONFIRMATION":
            return "Use as confirmation/watch evidence; wait for reclaim before dry-run entry."
        if win_rate >= 0.58 and avg > 0:
            return "Use for simulation-review priority while keeping Dataset1 phase-risk filters."
        return "Keep as observation evidence until win rate and average return improve."

    def _float_or_zero(self, value: Any) -> float:
        try:
            return float(value or 0.0)
        except (TypeError, ValueError):
            return 0.0

    def _load_model_candidate_detail(self, artifact: dict[str, Any]) -> dict[str, Any]:
        """Return bounded, UI-ready detail from the ignored candidate artifact."""
        path_value = artifact.get("artifact_path")
        if not artifact.get("artifact_written") or not path_value:
            return {
                "status": "not_written",
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            }

        path = Path(str(path_value))
        if not path.exists():
            return {
                "status": "missing",
                "artifact_path": str(path),
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            }

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            return {
                "status": "read_failed",
                "artifact_path": str(path),
                "error": str(exc),
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            }

        signal_optimization = payload.get("signal_optimization") or {}
        detail = {
            "status": "loaded",
            "schema_version": payload.get("schema_version"),
            "artifact_kind": payload.get("artifact_kind"),
            "artifact_path": str(path),
            "strategy_synthesis": payload.get("strategy_synthesis") or {},
            "simulation_review_plan": payload.get("simulation_review_plan") or {},
            "signal_optimization": {
                "status": signal_optimization.get("status"),
                "gate": signal_optimization.get("gate"),
                "best": signal_optimization.get("best"),
                "best_experience_aligned": signal_optimization.get("best_experience_aligned"),
                "selected_stable_candidate": signal_optimization.get("selected_stable_candidate"),
                "stable_candidate_tracks": signal_optimization.get("stable_candidate_tracks"),
                "track_tradeoff_attribution": signal_optimization.get("track_tradeoff_attribution"),
                "signal_loss_attribution": signal_optimization.get("signal_loss_attribution"),
                "parameter_failure_attribution": signal_optimization.get("parameter_failure_attribution"),
                "shadow_parameter_evidence": signal_optimization.get("shadow_parameter_evidence"),
                "learning_filter_candidates": (signal_optimization.get("learning_filter_candidates") or [])[:5],
                "optimization_budget": signal_optimization.get("optimization_budget"),
            },
            "rule_family_performance_memory": payload.get("rule_family_performance_memory") or {},
            "rule_family_review_gate": payload.get("rule_family_review_gate") or {},
            "candidate_review_priority_framework": payload.get("candidate_review_priority_framework") or {},
            "focus_phase_diagnostics": payload.get("focus_phase_diagnostics") or {},
            "phase_similarity_performance": payload.get("phase_similarity_performance") or {},
            "phase_confidence_walk_forward": payload.get("phase_confidence_walk_forward") or {},
            "top_patterns": (payload.get("top_patterns") or [])[:8],
            "strategy_recommendations": (payload.get("strategy_recommendations") or [])[:5],
            "usage_policy": payload.get("usage_policy") or {},
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }
        return detail

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

    def _refresh_history(
        self,
        limit: int,
        days: int,
        requested_limit: int | None = None,
        requested_days: int | None = None,
    ) -> dict[str, Any]:
        try:
            result = DailyBarCacheService().refresh_bars(limit=limit, days=days)
            result["inline_refresh_budget"] = {
                "requested_limit": requested_limit if requested_limit is not None else limit,
                "requested_days": requested_days if requested_days is not None else days,
                "effective_limit": limit,
                "effective_days": days,
                "cap_reason": "bounded_offhour_api_latency",
            }
            return result
        except Exception as exc:
            return {
                "status": "failed",
                "error": str(exc),
                "fallback": "existing_daily_bar_cache_only",
                "inline_refresh_budget": {
                    "requested_limit": requested_limit if requested_limit is not None else limit,
                    "requested_days": requested_days if requested_days is not None else days,
                    "effective_limit": limit,
                    "effective_days": days,
                    "cap_reason": "bounded_offhour_api_latency",
                },
            }

    def _phase_confidence_needs_benchmark(self, phase_similarity_performance: dict[str, Any]) -> bool:
        items = phase_similarity_performance.get("items") or []
        groups = phase_similarity_performance.get("by_group") or []
        target_groups = [
            group
            for group in groups
            if group.get("confidence_tier") in PHASE_CONFIDENCE_TARGET_TIERS
        ]
        return bool(items and target_groups)

    def _benchmark_coverage(self) -> dict[str, Any]:
        rows = self.store.fetch_all(
            f"""
            SELECT symbol,
                   COUNT(*) AS bar_count,
                   MIN(trade_date) AS first_trade_date,
                   MAX(trade_date) AS last_trade_date,
                   MAX(source) AS source
            FROM daily_bar_cache
            WHERE symbol IN ({",".join("?" for _ in BENCHMARK_HISTORY_SYMBOLS)})
              AND quality_status = 'ready'
              AND trade_date != 'ERROR'
            GROUP BY symbol
            """,
            BENCHMARK_HISTORY_SYMBOLS,
        )
        by_symbol = {row["symbol"]: dict(row) for row in rows}
        ready_symbols = [
            symbol
            for symbol in BENCHMARK_HISTORY_SYMBOLS
            if int(by_symbol.get(symbol, {}).get("bar_count") or 0) >= MIN_BENCHMARK_READY_BARS
        ]
        missing_symbols = [symbol for symbol in BENCHMARK_HISTORY_SYMBOLS if symbol not in ready_symbols]
        return {
            "status": "ready" if ready_symbols else "insufficient_benchmark_data",
            "checked_symbols": len(BENCHMARK_HISTORY_SYMBOLS),
            "ready_symbols": ready_symbols,
            "missing_symbols": missing_symbols,
            "items": list(by_symbol.values()),
            "minimum_ready_bars": MIN_BENCHMARK_READY_BARS,
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _ensure_benchmark_history(self, days: int, enabled: bool = True) -> dict[str, Any]:
        days = max(1, min(int(days), MAX_INLINE_HISTORY_REFRESH_DAYS))
        before = self._benchmark_coverage()
        if not enabled:
            return {
                "status": "skipped",
                "reason": "phase_confidence_has_no_target_groups",
                "coverage": before,
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            }
        if before["status"] == "ready":
            return {
                "status": "ready",
                "refreshed": False,
                "coverage": before,
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            }
        try:
            refresh = DailyBarCacheService().refresh_benchmark_bars(
                symbols=BENCHMARK_HISTORY_SYMBOLS,
                days=days,
            )
            after = self._benchmark_coverage()
            return {
                "status": "ready" if after["status"] == "ready" else "partial",
                "refreshed": True,
                "before": before,
                "after": after,
                "refresh": refresh,
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            }
        except Exception as exc:
            return {
                "status": "failed",
                "refreshed": False,
                "before": before,
                "error": str(exc),
                "fallback": "existing_benchmark_cache_only",
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
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
        recent_signals = sorted(
            signals,
            key=lambda item: (str(item["signal_date"]), float(item["score"]), str(item["symbol"])),
            reverse=True,
        )[:RECLAIM_WATCH_RECENT_SIGNAL_LIMIT]
        expanded_signals = sorted(
            [
                signal
                for signal in signals
                if signal.get("action_label") in SIGNAL_BACKTEST_ACTIONS
            ],
            key=lambda item: (
                str(item.get("signal_date") or ""),
                str(item.get("symbol") or ""),
                str(item.get("pattern_id") or ""),
            ),
        )[-MAX_SIGNAL_OPTIMIZATION_EXPANDED_SIGNAL_COUNT:]
        pattern_counts = Counter(str(item["pattern_id"]) for item in limited)
        action_counts = Counter(str(item["action_label"]) for item in limited)
        return {
            "status": "completed" if limited else "blocked",
            "reason": None if limited else "no_dataset2_strategy_matches",
            "signal_count": len(limited),
            "recent_signal_count": len(recent_signals),
            "expanded_signal_count": len(expanded_signals),
            "expanded_signal_budget": {
                "max_signal_count": MAX_SIGNAL_OPTIMIZATION_EXPANDED_SIGNAL_COUNT,
                "source_action": "all_actionable_cached_replay_signals",
                "bounded_for_artifact_size": True,
                "review_only": True,
                "simulation_only": True,
            },
            "signals": limited,
            "recent_signals": recent_signals,
            "expanded_signals": expanded_signals,
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
        deep_backtest = os.getenv("OFFHOUR_RESEARCH_DEEP_BACKTEST", "").lower() in {"1", "true", "yes"}
        symbol_cap = 20 if deep_backtest else 10
        backtest_symbols = symbols[:symbol_cap]
        date_range = self._date_range(backtest_symbols)
        if not date_range:
            return {"status": "skipped", "reason": "insufficient_history_data"}
        start_date, end_date = date_range
        min_start = (datetime.fromisoformat(end_date) - timedelta(days=history_days)).date().isoformat()
        start_date = max(start_date, min_start)
        try:
            result = BacktestEngine().run(
                start_date=start_date,
                end_date=end_date,
                symbols=backtest_symbols,
                initial_cash=100000.0,
                max_positions=min(5, max(1, len(backtest_symbols))),
                per_symbol_cap=0.2,
                benchmark_symbol=settings.backtest_default_benchmark_symbol,
                persist=deep_backtest,
            )
            return {
                "status": result.get("status"),
                "run_id": result.get("run_id"),
                "symbols": backtest_symbols,
                "start_date": start_date,
                "end_date": end_date,
                "metrics": result.get("metrics", {}),
                "benchmark": result.get("benchmark", {}),
                "execution_warnings": result.get("execution_warnings", []),
                "backtest_budget": {
                    "profile": "deep" if deep_backtest else "balanced",
                    "requested_symbol_count": len(symbols),
                    "effective_symbol_count": len(backtest_symbols),
                    "persisted_historical_backtest": deep_backtest,
                    "deep_mode_env": "OFFHOUR_RESEARCH_DEEP_BACKTEST=1",
                },
                "review_only": True,
                "simulation_only": True,
            }
        except Exception as exc:
            return {
                "status": "failed",
                "error": str(exc),
                "symbols": backtest_symbols,
                "backtest_budget": {
                    "profile": "deep" if deep_backtest else "balanced",
                    "requested_symbol_count": len(symbols),
                    "effective_symbol_count": len(backtest_symbols),
                    "persisted_historical_backtest": deep_backtest,
                    "deep_mode_env": "OFFHOUR_RESEARCH_DEEP_BACKTEST=1",
                },
                "review_only": True,
                "simulation_only": True,
            }

    def _signal_backtest(
        self,
        replay: dict[str, Any],
        horizon_days: int = 5,
        entry_delay_days: int = 1,
        stop_loss_pct: float = 0.05,
        take_profit_pct: float = 0.08,
        wait_position_ratio: float = 0.06,
        buy_position_ratio: float = 0.08,
        confirmation_filter: str = "none",
        attribution_filter: str = "none",
        signals: list[dict[str, Any]] | None = None,
        include_trades: bool = True,
        trade_limit: int = 50,
    ) -> dict[str, Any]:
        """Trade Dataset2 replay signals directly with realistic execution guards.

        This is deliberately separate from the production RuleEngine backtest: it
        checks whether a Dataset2 pattern can produce auditable simulated fills
        before it is ever considered for planner/rule weight review.
        """
        signals = [
            signal
            for signal in (signals if signals is not None else replay.get("signals") or [])
            if signal.get("action_label") in SIGNAL_BACKTEST_ACTIONS
        ]
        parameters = {
            "entry_delay_days": int(entry_delay_days),
            "horizon_days": int(horizon_days),
            "stop_loss_pct": round(float(stop_loss_pct), 4),
            "take_profit_pct": round(float(take_profit_pct), 4),
            "wait_position_ratio": round(float(wait_position_ratio), 4),
            "buy_position_ratio": round(float(buy_position_ratio), 4),
            "confirmation_filter": confirmation_filter,
            "attribution_filter": attribution_filter,
        }
        if not signals:
            return {
                "status": "skipped",
                "reason": "no_actionable_dataset2_signals",
                "metrics": {"trade_count": 0, "closed_trade_count": 0},
                "parameters": parameters,
                "pattern_performance": {},
                "trades": [],
                "execution_warnings": [],
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            }

        execution = BacktestExecutionModel()
        initial_cash = settings.default_cash
        closed: list[dict[str, Any]] = []
        warnings: list[str] = []
        rejected_entries = 0
        rejected_exits = 0
        skipped_by_filter = 0
        skipped_by_attribution_filter = 0
        for signal in sorted(signals, key=lambda item: (item["signal_date"], item["symbol"])):
            entry_bar = self._next_ready_bar(signal["symbol"], signal["signal_date"], offset=max(0, entry_delay_days - 1))
            if not entry_bar:
                warnings.append(f"{signal['symbol']} {signal['signal_date']} skipped: no_next_entry_bar")
                continue
            previous_close = self._previous_close(signal["symbol"], entry_bar["trade_date"], fallback=float(signal["close"]))
            if not self._confirmation_filter_passes(signal, entry_bar, previous_close, confirmation_filter):
                skipped_by_filter += 1
                continue
            if not self._signal_attribution_filter_passes(signal, entry_bar, previous_close, attribution_filter):
                skipped_by_attribution_filter += 1
                continue
            entry_exec_bar = self._execution_bar(entry_bar)
            entry_price = round(float(entry_bar["open"]) * (1 + settings.slippage_rate), 4)
            position_ratio = buy_position_ratio if signal.get("action_label") == "SIM_BUY_CANDIDATE" else wait_position_ratio
            requested_qty = int((initial_cash * position_ratio) / entry_price) // settings.min_order_lot * settings.min_order_lot
            buy_decision = execution.decide(
                side="buy",
                requested_quantity=requested_qty,
                price=entry_price,
                bar=entry_exec_bar,
                previous_close=previous_close,
                limit_pct=self._limit_pct(signal["symbol"]),
            )
            if buy_decision.fill_status == "rejected":
                rejected_entries += 1
                warnings.append(
                    f"{signal['symbol']} {signal['signal_date']} entry rejected: {buy_decision.reject_reason}"
                )
                continue

            exit_plan = self._signal_exit_plan(
                signal["symbol"],
                entry_date=str(entry_bar["trade_date"]),
                entry_price=buy_decision.price,
                horizon_days=horizon_days,
                stop_loss_pct=stop_loss_pct,
                take_profit_pct=take_profit_pct,
            )
            if not exit_plan:
                warnings.append(f"{signal['symbol']} {signal['signal_date']} skipped: no_exit_bar")
                continue
            exit_exec_bar = self._execution_bar(exit_plan["bar"])

            sell_decision = execution.decide(
                side="sell",
                requested_quantity=buy_decision.filled_quantity,
                price=round(exit_plan["exit_price"] * (1 - settings.slippage_rate), 4),
                bar=exit_exec_bar,
                previous_close=self._previous_close(signal["symbol"], exit_plan["exit_date"], fallback=buy_decision.price),
                limit_pct=self._limit_pct(signal["symbol"]),
            )
            if sell_decision.fill_status == "rejected":
                rejected_exits += 1
                warnings.append(
                    f"{signal['symbol']} {signal['signal_date']} exit rejected: {sell_decision.reject_reason}"
                )
                continue

            entry_cost = buy_decision.price * buy_decision.filled_quantity + buy_decision.fee
            exit_value = sell_decision.price * sell_decision.filled_quantity - sell_decision.fee - sell_decision.stamp_tax
            realized_pnl = exit_value - entry_cost
            realized_pct = realized_pnl / entry_cost * 100 if entry_cost else 0.0
            signal_close = float(signal.get("close") or 0)
            entry_open = float(entry_bar.get("open") or 0)
            entry_close = float(entry_bar.get("close") or 0)
            closed.append(
                {
                    "symbol": signal["symbol"],
                    "pattern_id": signal["pattern_id"],
                    "action_label": signal["action_label"],
                    "signal_date": signal["signal_date"],
                    "entry_date": entry_bar["trade_date"],
                    "exit_date": exit_plan["exit_date"],
                    "entry_price": buy_decision.price,
                    "exit_price": sell_decision.price,
                    "quantity": sell_decision.filled_quantity,
                    "realized_pnl": round(realized_pnl, 6),
                    "realized_pnl_pct": round(realized_pct, 6),
                    "exit_reason": exit_plan["exit_reason"],
                    "buy_fill_status": buy_decision.fill_status,
                    "sell_fill_status": sell_decision.fill_status,
                    "entry_open": entry_open,
                    "entry_close": entry_close,
                    "entry_low": float(entry_bar.get("low") or 0),
                    "entry_gap_pct": round((entry_open - previous_close) / previous_close * 100, 6)
                    if previous_close
                    else 0.0,
                    "entry_close_vs_signal_pct": round((entry_close - signal_close) / signal_close * 100, 6)
                    if signal_close
                    else 0.0,
                    "liquidity_amount_estimated": bool(
                        entry_exec_bar.get("amount_estimated") or exit_exec_bar.get("amount_estimated")
                    ),
                    "signal_close": signal.get("close"),
                    "signal_pct_change": signal.get("pct_change"),
                    "signal_tags": signal.get("tags") or [],
                    "matched_tags": signal.get("matched_tags") or [],
                    "risk_level": signal.get("risk_level"),
                    "score": signal.get("score"),
                    "category": signal.get("category"),
                    "pattern_name": signal.get("pattern_name"),
                    "review_only": True,
                    "simulation_only": True,
                }
            )

        metrics = self._signal_backtest_metrics(closed, rejected_entries, rejected_exits)
        metrics["skipped_by_confirmation_filter"] = skipped_by_filter
        metrics["skipped_by_attribution_filter"] = skipped_by_attribution_filter
        return {
            "status": "completed" if closed else "blocked",
            "reason": None if closed else "no_closed_signal_trades",
            "metrics": metrics,
            "parameters": parameters,
            "pattern_performance": self._signal_pattern_performance(closed),
            "trades": closed[: max(0, int(trade_limit))] if include_trades else [],
            "execution_warnings": warnings[:100],
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _reclaim_watchlist(self, replay: dict[str, Any]) -> dict[str, Any]:
        source_signals = replay.get("recent_signals") or replay.get("signals") or []
        signals = [
            signal
            for signal in source_signals
            if signal.get("action_label") in SIGNAL_BACKTEST_ACTIONS
        ]
        if not signals:
            return {
                "schema_version": "reclaim_watchlist.v1",
                "status": "skipped",
                "reason": "no_actionable_dataset2_signals",
                "items": [],
                "counts": {},
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            }

        items: list[dict[str, Any]] = []
        seen_symbols: set[str] = set()
        ordered_signals = sorted(
            signals,
            key=lambda item: (str(item.get("signal_date") or ""), float(item.get("score") or 0)),
            reverse=True,
        )
        for signal in ordered_signals:
            symbol = str(signal.get("symbol") or "")
            if not symbol or symbol in seen_symbols:
                continue
            seen_symbols.add(symbol)
            item = self._reclaim_watch_item(signal)
            if item:
                items.append(item)
            if len(items) >= RECLAIM_WATCH_MAX_ITEMS:
                break

        counts = Counter(str(item.get("status") or "unknown") for item in items)
        active_count = sum(
            counts.get(status, 0)
            for status in {"near_reclaim_watch", "reclaim_review", "pullback_watch"}
        )
        return {
            "schema_version": "reclaim_watchlist.v1",
            "status": "completed" if items else "empty",
            "input_signal_count": len(signals),
            "item_count": len(items),
            "active_watch_count": active_count,
            "counts": dict(counts),
            "items": items,
            "policy": {
                "near_reclaim_watch": "observe only until a future close or verified intraday price reclaims the signal price.",
                "reclaim_review": "eligible for manual review or dry-run simulation evidence only; it does not permit orders.",
                "blocked_failed_markup_risk": "hard risk tags keep the symbol observe-only.",
                "writes_rules_yaml": False,
                "auto_apply": False,
                "broker_or_order_action": False,
            },
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _reclaim_watch_item(self, signal: dict[str, Any]) -> dict[str, Any] | None:
        symbol = str(signal.get("symbol") or "")
        signal_date = str(signal.get("signal_date") or "")
        signal_close = float(signal.get("close") or 0)
        latest_bar = self._latest_ready_bar_after(symbol, signal_date)
        if signal_close <= 0:
            return None
        if not latest_bar:
            return {
                "symbol": symbol,
                "signal_date": signal_date,
                "pattern_id": signal.get("pattern_id"),
                "pattern_name": signal.get("pattern_name"),
                "action_label": signal.get("action_label"),
                "status": "pending_future_data",
                "reason": "no_ready_bar_after_signal",
                "signal_close": signal_close,
                "allowed_effect": "observe_only",
                "review_only": True,
                "simulation_only": True,
            }

        return self._reclaim_status_item(signal, latest_bar)

    def _reclaim_status_item(self, signal: dict[str, Any], latest_bar: dict[str, Any]) -> dict[str, Any]:
        symbol = str(signal.get("symbol") or "")
        signal_date = str(signal.get("signal_date") or "")
        signal_close = float(signal.get("close") or 0)
        latest_close = float(latest_bar.get("close") or 0)
        latest_open = float(latest_bar.get("open") or 0)
        signal_age_days = self._trade_date_delta_days(signal_date, str(latest_bar.get("trade_date") or ""))
        close_vs_signal_pct = (latest_close - signal_close) / signal_close * 100 if signal_close else 0.0
        open_vs_signal_pct = (latest_open - signal_close) / signal_close * 100 if signal_close else 0.0
        latest_features = self._features_for_trade_date(symbol, str(latest_bar.get("trade_date") or ""))
        signal_tags = set(str(tag) for tag in (signal.get("tags") or []))
        latest_tags = set(str(tag) for tag in (latest_features.get("tags") or []))
        matched_tags = set(str(tag) for tag in (signal.get("matched_tags") or []))
        risk_tags = sorted(
            (signal_tags | latest_tags | matched_tags)
            & {"top_risk", "distribution", "big_fall", "volume_up_price_stall", "reduce", "down_phase", "big_yin"}
        )
        hard_risk = bool(set(risk_tags) & {"distribution", "big_fall", "volume_up_price_stall", "reduce", "big_yin"})
        weak_open = latest_open < signal_close * NEAR_RECLAIM_OPEN_RATIO
        weak_intraday = latest_close < latest_open * RECLAIM_REVIEW_INTRADAY_FLOOR_RATIO

        if signal_age_days is not None and signal_age_days > RECLAIM_WATCH_MAX_SIGNAL_AGE_DAYS:
            status = "stale_historical_signal"
            next_confirmation = ["new_recent_dataset2_signal_required"]
            allowed_effect = "historical_research_only"
        elif hard_risk:
            status = "blocked_failed_markup_risk"
            next_confirmation = ["risk_tags_clear_in_later_bars", "manual_phase_review"]
            allowed_effect = "observe_only"
        elif latest_close >= signal_close and not weak_open and not weak_intraday:
            status = "reclaim_review"
            next_confirmation = [
                "portfolio_risk_gates_passed",
                "fresh_quote_confirms_reclaim",
                "dry_run_screen_before_any_simulated_click",
            ]
            allowed_effect = "raise_review_priority_and_dry_run_only"
        elif latest_close >= signal_close * NEAR_RECLAIM_CLOSE_RATIO and not weak_open:
            status = "near_reclaim_watch"
            next_confirmation = [
                "future_close_or_intraday_price_reclaims_signal_price",
                "no_new_hard_risk_tags",
                "portfolio_risk_gates_passed",
            ]
            allowed_effect = "watch_for_reclaim_only_not_dry_run"
        elif latest_close >= signal_close * 0.95:
            status = "pullback_watch"
            next_confirmation = [
                "price_stabilizes_near_signal_price",
                "volume_contracts_or_follow_through_returns",
            ]
            allowed_effect = "observe_only"
        else:
            status = "inactive_deep_pullback"
            next_confirmation = ["new_dataset2_signal_required"]
            allowed_effect = "observe_only"

        return {
            "symbol": symbol,
            "signal_date": signal_date,
            "latest_trade_date": latest_bar.get("trade_date"),
            "pattern_id": signal.get("pattern_id"),
            "pattern_name": signal.get("pattern_name"),
            "category": signal.get("category"),
            "action_label": signal.get("action_label"),
            "score": signal.get("score"),
            "risk_level": signal.get("risk_level"),
            "status": status,
            "signal_close": signal_close,
            "latest_open": latest_open,
            "latest_close": latest_close,
            "signal_age_days": signal_age_days,
            "close_vs_signal_pct": round(close_vs_signal_pct, 6),
            "open_vs_signal_pct": round(open_vs_signal_pct, 6),
            "signal_tags": sorted(signal_tags),
            "latest_tags": sorted(latest_tags),
            "matched_tags": sorted(matched_tags),
            "risk_tags": risk_tags,
            "conditions": {
                "near_signal_price": latest_close >= signal_close * NEAR_RECLAIM_CLOSE_RATIO,
                "reclaimed_signal_price": latest_close >= signal_close,
                "no_deep_gap_down": not weak_open,
                "no_weak_intraday_close": not weak_intraday,
                "no_hard_risk_tags": not hard_risk,
            },
            "requires_next_confirmation": next_confirmation,
            "allowed_effect": allowed_effect,
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _reclaim_transition_study(self, replay: dict[str, Any]) -> dict[str, Any]:
        signals = self._unique_reclaim_study_signals(replay)
        if not signals:
            return {
                "schema_version": "reclaim_transition_study.v1",
                "status": "skipped",
                "reason": "no_actionable_dataset2_signals",
                "input_signal_count": 0,
                "evaluated_count": 0,
                "pending_count": 0,
                "primary_horizon_days": 5,
                "horizons": list(RECLAIM_TRANSITION_HORIZONS),
                "by_status": {},
                "items": [],
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            }

        items = [self._reclaim_transition_item(signal) for signal in signals]
        evaluated = [
            item
            for item in items
            if item.get("primary_return_pct") is not None
        ]
        pending_count = len(items) - len(evaluated)
        by_status = self._reclaim_transition_by_status(evaluated)
        risk_tag_attribution = self._reclaim_transition_risk_tag_attribution(evaluated)
        return {
            "schema_version": "reclaim_transition_study.v1",
            "status": "completed" if evaluated else "blocked",
            "reason": None if evaluated else "insufficient_future_data_for_reclaim_transition_study",
            "input_signal_count": len(signals),
            "evaluated_count": len(evaluated),
            "pending_count": pending_count,
            "primary_horizon_days": 5,
            "horizons": list(RECLAIM_TRANSITION_HORIZONS),
            "by_status": by_status,
            "risk_tag_attribution": risk_tag_attribution,
            "supervision": self._reclaim_transition_supervision(by_status, risk_tag_attribution),
            "items": items[:50],
            "policy": {
                "uses_next_ready_bar_only_for_classification": True,
                "no_future_data_in_status_classification": True,
                "writes_rules_yaml": False,
                "auto_apply": False,
                "broker_or_order_action": False,
            },
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _unique_reclaim_study_signals(self, replay: dict[str, Any]) -> list[dict[str, Any]]:
        source_signals = [*(replay.get("signals") or []), *(replay.get("recent_signals") or [])]
        ordered = sorted(
            [
                signal
                for signal in source_signals
                if signal.get("action_label") in SIGNAL_BACKTEST_ACTIONS
            ],
            key=lambda item: (str(item.get("signal_date") or ""), float(item.get("score") or 0), str(item.get("symbol") or "")),
            reverse=True,
        )
        unique: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str, str]] = set()
        for signal in ordered:
            key = (
                str(signal.get("symbol") or ""),
                str(signal.get("signal_date") or ""),
                str(signal.get("pattern_id") or ""),
                str(signal.get("action_label") or ""),
            )
            if not key[0] or not key[1] or key in seen:
                continue
            seen.add(key)
            unique.append(signal)
            if len(unique) >= RECLAIM_TRANSITION_MAX_SIGNALS:
                break
        return unique

    def _reclaim_transition_item(self, signal: dict[str, Any]) -> dict[str, Any]:
        symbol = str(signal.get("symbol") or "")
        signal_date = str(signal.get("signal_date") or "")
        transition_bar = self._next_ready_bar(symbol, signal_date)
        if not transition_bar:
            return {
                "symbol": symbol,
                "signal_date": signal_date,
                "pattern_id": signal.get("pattern_id"),
                "action_label": signal.get("action_label"),
                "transition_status": "pending_future_data",
                "outcome_status": "pending_future_data",
                "reason": "no_next_ready_bar_after_signal",
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            }

        status_item = self._reclaim_status_item(signal, transition_bar)
        transition_date = str(transition_bar.get("trade_date") or "")
        transition_close = float(transition_bar.get("close") or 0)
        future_rows = self._future_ready_bars(symbol, transition_date, max(RECLAIM_TRANSITION_HORIZONS))
        horizon_returns = self._transition_horizon_returns(
            transition_close,
            future_rows,
            RECLAIM_TRANSITION_HORIZONS,
        )
        primary = horizon_returns.get("5") or {}
        return {
            "symbol": symbol,
            "signal_date": signal_date,
            "transition_date": transition_date,
            "pattern_id": signal.get("pattern_id"),
            "pattern_name": signal.get("pattern_name"),
            "action_label": signal.get("action_label"),
            "score": signal.get("score"),
            "transition_status": status_item.get("status"),
            "allowed_effect": status_item.get("allowed_effect"),
            "transition_close_vs_signal_pct": status_item.get("close_vs_signal_pct"),
            "risk_tags": status_item.get("risk_tags", []),
            "transition_close": transition_close,
            "outcome_status": primary.get("status", "pending_future_data"),
            "primary_horizon_days": 5,
            "primary_return_pct": primary.get("close_return_pct"),
            "primary_max_return_pct": primary.get("max_return_pct"),
            "primary_min_return_pct": primary.get("min_return_pct"),
            "horizon_returns": horizon_returns,
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _future_ready_bars(self, symbol: str, after_date: str, limit: int) -> list[dict[str, Any]]:
        series = self._ready_bars_for_symbol(symbol)
        if series is not None:
            return [
                dict(row)
                for row in series
                if str(row.get("trade_date") or "") > after_date
            ][: max(1, int(limit))]
        rows = self.store.fetch_all(
            """
            SELECT symbol, trade_date, open, high, low, close, volume, amount
            FROM daily_bar_cache
            WHERE symbol = ?
              AND quality_status = 'ready'
              AND trade_date > ?
              AND trade_date != 'ERROR'
            ORDER BY trade_date ASC
            LIMIT ?
            """,
            (symbol, after_date, max(1, int(limit))),
        )
        return [dict(row) for row in rows]

    def _transition_horizon_returns(
        self,
        entry_price: float,
        rows: list[dict[str, Any]],
        horizons: tuple[int, ...],
    ) -> dict[str, dict[str, Any]]:
        results: dict[str, dict[str, Any]] = {}
        for horizon in horizons:
            key = str(int(horizon))
            if entry_price <= 0 or not rows:
                results[key] = {
                    "status": "pending_future_data",
                    "available_days": 0,
                    "horizon_days": int(horizon),
                }
                continue
            subset = rows[: min(len(rows), int(horizon))]
            close = float(subset[-1].get("close") or 0)
            highs = [float(row.get("high") or row.get("close") or 0) for row in subset]
            lows = [float(row.get("low") or row.get("close") or 0) for row in subset]
            results[key] = {
                "status": "completed" if len(subset) >= int(horizon) else "partial",
                "available_days": len(subset),
                "horizon_days": int(horizon),
                "exit_date": subset[-1].get("trade_date"),
                "close_return_pct": round((close - entry_price) / entry_price * 100, 6) if entry_price else 0.0,
                "max_return_pct": round((max(highs) - entry_price) / entry_price * 100, 6) if entry_price else 0.0,
                "min_return_pct": round((min(lows) - entry_price) / entry_price * 100, 6) if entry_price else 0.0,
            }
        return results

    def _reclaim_transition_by_status(self, items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for item in items:
            grouped.setdefault(str(item.get("transition_status") or "unknown"), []).append(item)

        result: dict[str, dict[str, Any]] = {}
        for status, status_items in grouped.items():
            returns = [float(item.get("primary_return_pct") or 0) for item in status_items]
            max_returns = [float(item.get("primary_max_return_pct") or 0) for item in status_items]
            min_returns = [float(item.get("primary_min_return_pct") or 0) for item in status_items]
            summary = self._return_summary(returns)
            summary["sample_count"] = len(status_items)
            summary["average_max_return_pct"] = round(sum(max_returns) / len(max_returns), 6) if max_returns else 0.0
            summary["average_min_return_pct"] = round(sum(min_returns) / len(min_returns), 6) if min_returns else 0.0
            summary["allowed_effect"] = self._reclaim_status_allowed_effect(status)
            summary["suggested_review_treatment"] = self._reclaim_transition_treatment(status, summary)
            summary["examples"] = sorted(
                [
                    {
                        "symbol": item.get("symbol"),
                        "signal_date": item.get("signal_date"),
                        "transition_date": item.get("transition_date"),
                        "pattern_id": item.get("pattern_id"),
                        "primary_return_pct": item.get("primary_return_pct"),
                        "primary_max_return_pct": item.get("primary_max_return_pct"),
                        "primary_min_return_pct": item.get("primary_min_return_pct"),
                        "risk_tags": item.get("risk_tags", []),
                        "review_only": True,
                        "simulation_only": True,
                    }
                    for item in status_items
                ],
                key=lambda item: abs(float(item.get("primary_return_pct") or 0)),
                reverse=True,
            )[:5]
            summary["review_only"] = True
            summary["simulation_only"] = True
            result[status] = summary
        return result

    def _reclaim_transition_risk_tag_attribution(self, items: list[dict[str, Any]]) -> dict[str, Any]:
        by_tag: dict[str, list[dict[str, Any]]] = {}
        by_status_tag: dict[str, list[dict[str, Any]]] = {}
        for item in items:
            risk_tags = [str(tag) for tag in (item.get("risk_tags") or [])] or ["no_risk_tag"]
            status = str(item.get("transition_status") or "unknown")
            for tag in risk_tags:
                by_tag.setdefault(tag, []).append(item)
                by_status_tag.setdefault(f"{status}:{tag}", []).append(item)

        return {
            "schema_version": "reclaim_transition_risk_tag_attribution.v1",
            "by_tag": self._risk_tag_summary_rows(by_tag),
            "by_status_tag": self._risk_tag_summary_rows(by_status_tag),
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _risk_tag_summary_rows(self, groups: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for key, group_items in groups.items():
            returns = [float(item.get("primary_return_pct") or 0) for item in group_items]
            summary = self._return_summary(returns)
            rows.append(
                {
                    "key": key,
                    "sample_count": len(group_items),
                    "win_rate": summary.get("win_rate"),
                    "average_return_pct": summary.get("average_return_pct"),
                    "cumulative_return_pct": summary.get("cumulative_return_pct"),
                    "best_return_pct": summary.get("best_return_pct"),
                    "worst_return_pct": summary.get("worst_return_pct"),
                    "suggested_treatment": self._risk_tag_treatment(key, summary),
                    "examples": [
                        {
                            "symbol": item.get("symbol"),
                            "signal_date": item.get("signal_date"),
                            "transition_status": item.get("transition_status"),
                            "primary_return_pct": item.get("primary_return_pct"),
                            "review_only": True,
                            "simulation_only": True,
                        }
                        for item in sorted(
                            group_items,
                            key=lambda item: abs(float(item.get("primary_return_pct") or 0)),
                            reverse=True,
                        )[:3]
                    ],
                    "review_only": True,
                    "simulation_only": True,
                }
            )
        return sorted(
            rows,
            key=lambda row: (-int(row.get("sample_count") or 0), float(row.get("average_return_pct") or 0), str(row["key"])),
        )

    def _risk_tag_treatment(self, key: str, summary: dict[str, Any]) -> str:
        sample_count = int(summary.get("count") or 0)
        win_rate = float(summary.get("win_rate") or 0)
        average_return = float(summary.get("average_return_pct") or 0)
        worst_return = float(summary.get("worst_return_pct") or 0)
        if any(tag in key for tag in ("blocked_failed_markup_risk", "distribution", "big_fall", "volume_up_price_stall", "reduce", "big_yin")):
            return "observe_only_hard_risk"
        if sample_count >= 5 and (average_return < 0 or worst_return <= -8):
            return "downgrade_to_smallest_dry_run_or_observe"
        if sample_count >= 5 and win_rate >= 0.6 and average_return > 0:
            return "risk_tag_acceptable_for_review_only_priority"
        return "collect_more_samples_before_risk_tag_weight_change"

    def _reclaim_status_allowed_effect(self, status: str) -> str:
        return {
            "reclaim_review": "raise_review_priority_and_dry_run_only",
            "near_reclaim_watch": "watch_for_reclaim_only_not_dry_run",
            "pullback_watch": "observe_only",
            "blocked_failed_markup_risk": "observe_only",
            "inactive_deep_pullback": "observe_only",
            "stale_historical_signal": "historical_research_only",
            "pending_future_data": "observe_only",
        }.get(status, "observe_only")

    def _reclaim_transition_treatment(self, status: str, summary: dict[str, Any]) -> str:
        sample_count = int(summary.get("sample_count") or summary.get("count") or 0)
        win_rate = float(summary.get("win_rate") or 0)
        average_return = float(summary.get("average_return_pct") or 0)
        if status == "reclaim_review" and sample_count >= 3 and win_rate >= 0.5 and average_return > 0:
            return "eligible_for_small_dry_run_priority_review"
        if status == "near_reclaim_watch" and sample_count >= 3 and average_return > 0:
            return "keep_wider_watch_band_but_wait_for_reclaim"
        if status == "blocked_failed_markup_risk":
            return "keep_blocked_until_new_signal_and_risk_tags_clear"
        return "collect_more_samples_before_weight_change"

    def _reclaim_transition_supervision(
        self,
        by_status: dict[str, dict[str, Any]],
        risk_tag_attribution: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        reclaim = by_status.get("reclaim_review") or {}
        near = by_status.get("near_reclaim_watch") or {}
        blocked = by_status.get("blocked_failed_markup_risk") or {}
        recommendations: list[str] = []
        if self._reclaim_transition_treatment("reclaim_review", reclaim) == "eligible_for_small_dry_run_priority_review":
            recommendations.append("Reclaimed signals may receive small dry-run priority, still capped by simulation risk gates.")
        if self._reclaim_transition_treatment("near_reclaim_watch", near) == "keep_wider_watch_band_but_wait_for_reclaim":
            recommendations.append("Near-reclaim signals support a wider watch band, but not immediate simulated orders.")
        if int(blocked.get("sample_count") or 0) > 0:
            recommendations.append("Failed-markup risk remains observe-only unless later bars clear hard risk tags.")
        risk_rows = (risk_tag_attribution or {}).get("by_status_tag") or []
        downgrade_rows = [
            row
            for row in risk_rows
            if row.get("suggested_treatment") in {"downgrade_to_smallest_dry_run_or_observe", "observe_only_hard_risk"}
        ]
        if downgrade_rows:
            top = downgrade_rows[0]
            recommendations.append(
                f"Risk tag attribution flags {top.get('key')} for conservative handling; do not raise size from status alone."
            )
        if not recommendations:
            recommendations.append("Collect more post-signal bars before changing simulation weights.")
        return {
            "recommendations": recommendations,
            "suggested_positioning": {
                "reclaim_review_max_initial_simulated_position_ratio": 0.02,
                "near_reclaim_position_ratio": 0.0,
                "blocked_failed_markup_position_ratio": 0.0,
                "requires_portfolio_risk_gates": True,
                "requires_dry_run_screen_before_simulated_click": True,
            },
            "writes_rules_yaml": False,
            "auto_apply": False,
            "broker_or_order_action": False,
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _trade_date_delta_days(self, start: str, end: str) -> int | None:
        try:
            return (datetime.fromisoformat(end).date() - datetime.fromisoformat(start).date()).days
        except (TypeError, ValueError):
            return None

    def _ready_bars_for_symbol(self, symbol: str) -> list[dict[str, Any]] | None:
        cache = getattr(self, "_daily_bar_series_cache", None)
        if cache is None:
            return None
        if symbol not in cache:
            rows = self.store.fetch_all(
                """
                SELECT symbol, trade_date, open, high, low, close, volume, amount
                FROM daily_bar_cache
                WHERE symbol = ?
                  AND quality_status = 'ready'
                  AND trade_date != 'ERROR'
                ORDER BY trade_date ASC
                """,
                (symbol,),
            )
            cache[symbol] = [dict(row) for row in rows]
        return cache[symbol]

    def _latest_ready_bar_after(self, symbol: str, after_date: str) -> dict[str, Any] | None:
        series = self._ready_bars_for_symbol(symbol)
        if series is not None:
            matches = [bar for bar in series if str(bar.get("trade_date") or "") > after_date]
            return dict(matches[-1]) if matches else None
        row = self.store.fetch_one(
            """
            SELECT symbol, trade_date, open, high, low, close, volume, amount
            FROM daily_bar_cache
            WHERE symbol = ?
              AND quality_status = 'ready'
              AND trade_date > ?
              AND trade_date != 'ERROR'
            ORDER BY trade_date DESC
            LIMIT 1
            """,
            (symbol, after_date),
        )
        return dict(row) if row else None

    def _features_for_trade_date(self, symbol: str, trade_date: str) -> dict[str, Any]:
        series = self._ready_bars_for_symbol(symbol)
        if series is not None:
            ordered = [dict(row) for row in series if str(row.get("trade_date") or "") <= trade_date][-20:]
            if len(ordered) < 3:
                return {"tags": [], "status": "insufficient_history"}
            return self._features(ordered[-1], ordered[-2], ordered[-3], ordered)
        rows = self.store.fetch_all(
            """
            SELECT symbol, trade_date, open, high, low, close, volume, amount
            FROM daily_bar_cache
            WHERE symbol = ?
              AND quality_status = 'ready'
              AND trade_date <= ?
              AND trade_date != 'ERROR'
            ORDER BY trade_date DESC
            LIMIT 20
            """,
            (symbol, trade_date),
        )
        ordered = [dict(row) for row in reversed(rows)]
        if len(ordered) < 3:
            return {"tags": [], "status": "insufficient_history"}
        return self._features(ordered[-1], ordered[-2], ordered[-3], ordered)

    def _signal_parameter_grid(self, replay: dict[str, Any]) -> dict[str, Any]:
        sample = self._signal_optimization_sample(replay)
        signals = sample["signals"]
        if len(signals) < MIN_SIGNAL_BACKTEST_TRADE_COUNT * 2:
            parameter_failure_attribution = {
                "schema_version": "signal_parameter_failure_attribution.v1",
                "status": "skipped",
                "reason": "too_few_actionable_signals_for_train_validation",
                "complete_window_failures": {},
                "train_gate_failures": {},
                "validation_gate_failures": {},
                "near_miss_train_candidates": [],
                "near_miss_validation_candidates": [],
                "walk_forward_blockers": ["too_few_actionable_signals_for_train_validation"],
                "diagnosis": {
                    "signal_count": len(signals),
                    "required_signal_count": MIN_SIGNAL_BACKTEST_TRADE_COUNT * 2,
                    "candidate_generation_blocked": True,
                    "review_only": True,
                    "simulation_only": True,
                },
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            }
            shadow_parameter_evidence = self._shadow_parameter_evidence(
                parameter_failure_attribution,
                replay=replay,
                expanded_signals=sample.get("expanded_signals") or signals,
            )
            return {
                "status": "skipped",
                "reason": "too_few_actionable_signals_for_train_validation",
                "signal_count": len(signals),
                "sample": sample["summary"],
                "parameter_failure_attribution": parameter_failure_attribution,
                "shadow_parameter_evidence": shadow_parameter_evidence,
                "gate": {
                    "status": "blocked",
                    "reasons": ["too_few_actionable_signals_for_train_validation"],
                    "requires_human_review": True,
                    "writes_rules_yaml": False,
                    "auto_apply": False,
                    "simulation_only": True,
                    "live_trading_enabled": settings.enable_live_trading,
                },
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            }

        train_signals, validation_signals = self._chronological_signal_split(signals)
        candidates: list[dict[str, Any]] = []
        previous_cache = getattr(self, "_signal_backtest_cache", None)
        previous_series_cache = getattr(self, "_daily_bar_series_cache", None)
        self._signal_backtest_cache = {}
        self._daily_bar_series_cache = {}
        deep_optimization = os.getenv("OFFHOUR_RESEARCH_DEEP_OPTIMIZATION", "").lower() in {"1", "true", "yes"}
        entry_delays = [1, 2, 3] if deep_optimization else [1, 2]
        horizons = [3, 5, 8, 10] if deep_optimization else [3, 5, 8]
        stop_losses = [0.04, 0.06]
        take_profits = [0.08, 0.12, 0.18]
        confirmation_filters = list(SIGNAL_OPTIMIZATION_CONFIRMATION_FILTERS)
        full_grid_size = (
            len(entry_delays)
            * len(horizons)
            * len(stop_losses)
            * len(take_profits)
            * len(confirmation_filters)
        )
        train_evaluation_count = 0
        validation_evaluation_count = 0
        skipped_by_train_gate = 0
        skipped_by_complete_window = 0
        complete_window_failures: Counter[str] = Counter()
        train_gate_failures: Counter[str] = Counter()
        validation_gate_failures: Counter[str] = Counter()
        near_miss_train_candidates: list[dict[str, Any]] = []
        near_miss_validation_candidates: list[dict[str, Any]] = []
        window_cache: dict[tuple[int, int], dict[str, Any]] = {}

        def compact_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
            keys = (
                "trade_count",
                "win_rate",
                "average_return_pct",
                "equal_weight_cumulative_return_pct",
                "expectancy_pct",
                "max_drawdown_pct",
                "loss_count",
            )
            compact: dict[str, Any] = {}
            for key in keys:
                if key not in metrics:
                    continue
                value = metrics.get(key)
                if isinstance(value, float):
                    compact[key] = round(value, 6)
                else:
                    compact[key] = value
            return compact

        def parameter_snapshot(
            *,
            entry_delay: int,
            horizon: int,
            stop_loss: float,
            take_profit: float,
            confirmation_filter: str,
        ) -> dict[str, Any]:
            return {
                "entry_delay_days": entry_delay,
                "horizon_days": horizon,
                "stop_loss_pct": stop_loss,
                "take_profit_pct": take_profit,
                "confirmation_filter": confirmation_filter,
            }

        def append_near_miss(
            bucket: list[dict[str, Any]],
            item: dict[str, Any],
            *,
            sort_key: str,
            limit: int = 5,
        ) -> None:
            bucket.append(item)
            bucket.sort(
                key=lambda row: (
                    -float(row.get(sort_key) or 0),
                    _json_dumps(row.get("parameters") or {}),
                )
            )
            del bucket[limit:]

        for entry_delay in entry_delays:
            for horizon in horizons:
                window_key = (entry_delay, horizon)
                window_cache[window_key] = self._signals_with_complete_backtest_window(
                    signals,
                    entry_delay_days=entry_delay,
                    horizon_days=horizon,
                )
                eligible_train_signals, eligible_validation_signals = self._chronological_signal_split(
                    window_cache[window_key]["signals"]
                )
                for stop_loss in stop_losses:
                    for take_profit in take_profits:
                        for confirmation_filter in confirmation_filters:
                            if (
                                len(eligible_train_signals) < MIN_SIGNAL_BACKTEST_TRADE_COUNT
                                or len(eligible_validation_signals) < MIN_SIGNAL_BACKTEST_TRADE_COUNT
                            ):
                                skipped_by_complete_window += 1
                                if len(eligible_train_signals) < MIN_SIGNAL_BACKTEST_TRADE_COUNT:
                                    complete_window_failures["complete_window_train_signals_too_low"] += 1
                                if len(eligible_validation_signals) < MIN_SIGNAL_BACKTEST_TRADE_COUNT:
                                    complete_window_failures["complete_window_validation_signals_too_low"] += 1
                                continue
                            train = self._signal_backtest(
                                replay,
                                horizon_days=horizon,
                                entry_delay_days=entry_delay,
                                stop_loss_pct=stop_loss,
                                take_profit_pct=take_profit,
                                confirmation_filter=confirmation_filter,
                                signals=eligible_train_signals,
                                include_trades=False,
                            )
                            train_evaluation_count += 1
                            train_metrics = train.get("metrics") or {}
                            train_fail_reasons: list[str] = []
                            if int(train_metrics.get("trade_count") or 0) < MIN_SIGNAL_BACKTEST_TRADE_COUNT:
                                train_fail_reasons.append("train_trade_count_too_low")
                            if float(train_metrics.get("win_rate") or 0) < 0.4:
                                train_fail_reasons.append("train_win_rate_below_floor")
                            if float(train_metrics.get("average_return_pct") or 0) < -1.0:
                                train_fail_reasons.append("train_average_return_below_floor")
                            if train_fail_reasons:
                                skipped_by_train_gate += 1
                                train_gate_failures.update(train_fail_reasons)
                                train_score = (
                                    float(train_metrics.get("equal_weight_cumulative_return_pct") or 0)
                                    + float(train_metrics.get("win_rate") or 0) * 10
                                    + float(train_metrics.get("average_return_pct") or 0)
                                )
                                append_near_miss(
                                    near_miss_train_candidates,
                                    {
                                        "stage": "train_gate",
                                        "score": round(train_score, 6),
                                        "failed_reasons": train_fail_reasons,
                                        "parameters": parameter_snapshot(
                                            entry_delay=entry_delay,
                                            horizon=horizon,
                                            stop_loss=stop_loss,
                                            take_profit=take_profit,
                                            confirmation_filter=confirmation_filter,
                                        ),
                                        "metrics": compact_metrics(train_metrics),
                                        "review_only": True,
                                        "simulation_only": True,
                                    },
                                    sort_key="score",
                                )
                                continue
                            validation = self._signal_backtest(
                                replay,
                                horizon_days=horizon,
                                entry_delay_days=entry_delay,
                                stop_loss_pct=stop_loss,
                                take_profit_pct=take_profit,
                                confirmation_filter=confirmation_filter,
                                signals=eligible_validation_signals,
                                include_trades=False,
                            )
                            validation_evaluation_count += 1
                            validation_metrics = validation.get("metrics") or {}
                            if int(validation_metrics.get("trade_count") or 0) < MIN_SIGNAL_BACKTEST_TRADE_COUNT:
                                validation_gate_failures["validation_trade_count_too_low"] += 1
                                validation_score = (
                                    float(validation_metrics.get("equal_weight_cumulative_return_pct") or 0)
                                    + float(validation_metrics.get("win_rate") or 0) * 10
                                    + float(validation_metrics.get("average_return_pct") or 0)
                                )
                                append_near_miss(
                                    near_miss_validation_candidates,
                                    {
                                        "stage": "validation_gate",
                                        "score": round(validation_score, 6),
                                        "failed_reasons": ["validation_trade_count_too_low"],
                                        "parameters": validation.get("parameters")
                                        or parameter_snapshot(
                                            entry_delay=entry_delay,
                                            horizon=horizon,
                                            stop_loss=stop_loss,
                                            take_profit=take_profit,
                                            confirmation_filter=confirmation_filter,
                                        ),
                                        "train_metrics": compact_metrics(train_metrics),
                                        "validation_metrics": compact_metrics(validation_metrics),
                                        "review_only": True,
                                        "simulation_only": True,
                                    },
                                    sort_key="score",
                                )
                                continue
                            score = (
                                float(validation_metrics.get("equal_weight_cumulative_return_pct") or 0)
                                + float(validation_metrics.get("win_rate") or 0) * 10
                                + float(validation_metrics.get("expectancy_pct") or 0)
                                + min(10.0, float(train_metrics.get("equal_weight_cumulative_return_pct") or 0) / 2)
                            )
                            candidates.append(
                                {
                                    "score": round(score, 6),
                                    "parameters": validation.get("parameters") or {},
                                    "train_metrics": train_metrics,
                                    "validation_metrics": validation_metrics,
                                    "review_only": True,
                                    "simulation_only": True,
                                }
                            )

        candidates.sort(
            key=lambda item: (
                -float(item["validation_metrics"].get("equal_weight_cumulative_return_pct") or 0),
                -float(item["validation_metrics"].get("average_return_pct") or 0),
                -float(item["validation_metrics"].get("win_rate") or 0),
                _json_dumps(item["parameters"]),
            )
        )
        base_candidate_count = len(candidates)
        base_experience_aligned_candidates = [
            item
            for item in candidates
            if int((item.get("parameters") or {}).get("entry_delay_days") or 0) >= 2
            and (item.get("parameters") or {}).get("confirmation_filter") in DATASET1_EXPERIENCE_ALIGNED_FILTERS
        ]
        learning_filter_result = self._signal_learning_filter_candidates(
            replay=replay,
            train_signals=train_signals,
            validation_signals=validation_signals,
            base_candidates=candidates,
            experience_aligned_candidates=base_experience_aligned_candidates,
            all_signals=signals,
        )
        candidates.extend(learning_filter_result.get("candidates") or [])
        candidates.sort(
            key=lambda item: (
                -float(item["validation_metrics"].get("equal_weight_cumulative_return_pct") or 0),
                -float(item["validation_metrics"].get("average_return_pct") or 0),
                -float(item["validation_metrics"].get("win_rate") or 0),
                _json_dumps(item["parameters"]),
            )
        )
        best = candidates[0] if candidates else None
        experience_aligned_candidates = [
            item
            for item in candidates
            if int((item.get("parameters") or {}).get("entry_delay_days") or 0) >= 2
            and (
                (item.get("parameters") or {}).get("confirmation_filter") in DATASET1_EXPERIENCE_ALIGNED_FILTERS
                or (item.get("parameters") or {}).get("attribution_filter") not in {None, "", "none"}
            )
        ]
        best_experience_aligned = experience_aligned_candidates[0] if experience_aligned_candidates else None
        walk_forward = self._signal_walk_forward_validation(
            replay=replay,
            signals=signals,
            candidates=self._walk_forward_candidate_pool(candidates, experience_aligned_candidates),
        )
        selected_stable_candidate = self._selected_stable_candidate(walk_forward)
        stable_candidate_tracks = walk_forward.get("stable_candidate_tracks") or self._stable_candidate_tracks(
            walk_forward.get("top_candidates") or []
        )
        track_tradeoff_attribution = self._stable_candidate_tradeoff_attribution(
            replay=replay,
            signals=signals,
            stable_candidate_tracks=stable_candidate_tracks,
        )
        signal_loss_attribution = self._signal_loss_attribution(
            replay=replay,
            signals=signals,
            candidate=selected_stable_candidate,
        )
        selected_validation_metrics = (selected_stable_candidate or {}).get("source_validation_metrics") or {}
        passed = bool(
            selected_stable_candidate
            and float(selected_validation_metrics.get("win_rate") or 0) >= MIN_OPTIMIZED_VALIDATION_WIN_RATE
            and float(selected_validation_metrics.get("equal_weight_cumulative_return_pct") or 0)
            >= MIN_OPTIMIZED_VALIDATION_CUMULATIVE_RETURN_PCT
            and float(selected_validation_metrics.get("average_return_pct") or 0) > 0
        )
        reasons: list[str] = []
        if not best:
            reasons.append("no_parameter_candidate_with_enough_validation_trades")
        if not selected_stable_candidate:
            reasons.append("no_stable_candidate_meeting_validation_thresholds")
        if (walk_forward.get("gate") or {}).get("status") != "passed_for_simulation_review":
            reasons.append("walk_forward_validation_not_passed")
        parameter_failure_attribution = {
            "schema_version": "signal_parameter_failure_attribution.v1",
            "status": "ready",
            "complete_window_failures": dict(complete_window_failures),
            "train_gate_failures": dict(train_gate_failures),
            "validation_gate_failures": dict(validation_gate_failures),
            "near_miss_train_candidates": near_miss_train_candidates,
            "near_miss_validation_candidates": near_miss_validation_candidates,
            "walk_forward_blockers": (walk_forward.get("gate") or {}).get("reasons") or [],
            "diagnosis": {
                "base_candidate_count": base_candidate_count,
                "learning_filter_candidate_count": len(learning_filter_result.get("candidates") or []),
                "stable_candidate_available": bool(selected_stable_candidate),
                "candidate_generation_blocked": base_candidate_count == 0,
                "review_only": True,
                "simulation_only": True,
            },
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }
        shadow_parameter_evidence = self._shadow_parameter_evidence(
            parameter_failure_attribution,
            replay=replay,
            expanded_signals=sample.get("expanded_signals") or signals,
            selected_candidate=selected_stable_candidate,
        )

        result = {
            "status": "passed_for_simulation_review" if passed else "blocked",
            "signal_count": len(signals),
            "sample": sample["summary"],
            "train_signal_count": len(train_signals),
            "validation_signal_count": len(validation_signals),
            "split": "chronological_70_30",
            "optimization_budget": {
                "profile": "deep" if deep_optimization else "balanced",
                "sample": sample["summary"],
                "full_grid_size": full_grid_size,
                "base_candidate_count": base_candidate_count,
                "train_evaluation_count": train_evaluation_count,
                "validation_evaluation_count": validation_evaluation_count,
                "skipped_by_train_gate": skipped_by_train_gate,
                "skipped_by_complete_window": skipped_by_complete_window,
                "complete_window": self._complete_window_budget(window_cache),
                "learning_filter_budget": learning_filter_result.get("budget") or {},
                "deep_mode_env": "OFFHOUR_RESEARCH_DEEP_OPTIMIZATION=1",
            },
            "best": best,
            "best_experience_aligned": best_experience_aligned,
            "selected_stable_candidate": selected_stable_candidate,
            "stable_candidate_tracks": stable_candidate_tracks,
            "track_tradeoff_attribution": track_tradeoff_attribution,
            "signal_loss_attribution": signal_loss_attribution,
            "parameter_failure_attribution": parameter_failure_attribution,
            "shadow_parameter_evidence": shadow_parameter_evidence,
            "learning_filter_candidates": learning_filter_result.get("top_candidates") or [],
            "walk_forward": walk_forward,
            "top_candidates": candidates[:10],
            "top_experience_aligned_candidates": experience_aligned_candidates[:5],
            "gate": {
                "status": "passed_for_simulation_review" if passed else "blocked",
                "reasons": reasons,
                "min_validation_win_rate": MIN_OPTIMIZED_VALIDATION_WIN_RATE,
                "min_validation_cumulative_return_pct": MIN_OPTIMIZED_VALIDATION_CUMULATIVE_RETURN_PCT,
                "requires_walk_forward_validation": True,
                "requires_human_review": True,
                "writes_rules_yaml": False,
                "auto_apply": False,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            },
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }
        if previous_cache is None:
            try:
                delattr(self, "_signal_backtest_cache")
            except AttributeError:
                pass
        else:
            self._signal_backtest_cache = previous_cache
        if previous_series_cache is None:
            try:
                delattr(self, "_daily_bar_series_cache")
            except AttributeError:
                pass
        else:
            self._daily_bar_series_cache = previous_series_cache
        return result

    def _shadow_parameter_evidence(
        self,
        parameter_failure_attribution: dict[str, Any],
        replay: dict[str, Any] | None = None,
        expanded_signals: list[dict[str, Any]] | None = None,
        selected_candidate: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Promote promising but under-sampled parameters into review-only evidence."""
        near_misses = parameter_failure_attribution.get("near_miss_validation_candidates") or []
        shadow_candidates: list[dict[str, Any]] = []
        seen_parameter_keys: set[str] = set()

        if isinstance(selected_candidate, dict) and selected_candidate.get("parameters"):
            parameters = selected_candidate.get("parameters") or {}
            parameter_key = _json_dumps(parameters)
            train_metrics = (
                selected_candidate.get("source_train_metrics")
                or selected_candidate.get("train_metrics")
                or {}
            )
            validation_metrics = (
                selected_candidate.get("source_validation_metrics")
                or selected_candidate.get("validation_metrics")
                or {}
            )
            validation_trade_count = int(
                validation_metrics.get("trade_count")
                or selected_candidate.get("trade_count")
                or 0
            )
            confirmation_filter = str(parameters.get("confirmation_filter") or "")
            evidence_tags = ["selected_stable_candidate", "walk_forward_passed"]
            if confirmation_filter in DATASET1_EXPERIENCE_ALIGNED_FILTERS:
                evidence_tags.append("dataset1_experience_aligned_confirmation")
            if "reclaim" in confirmation_filter:
                evidence_tags.append("reclaim_confirmation_family")
            shadow_candidates.append(
                {
                    "shadow_status": "selected_stable_candidate_requires_expanded_history_review",
                    "source": "selected_stable_candidate",
                    "source_priority": 0,
                    "parameters": parameters,
                    "train_metrics": train_metrics,
                    "validation_metrics": validation_metrics,
                    "validation_trade_count": validation_trade_count,
                    "missing_validation_trades": 0,
                    "evidence_tags": evidence_tags,
                    "blocked_from_stable_reason": None,
                    "allowed_effect": "expanded_history_review_only",
                    "review_only": True,
                    "simulation_only": True,
                }
            )
            seen_parameter_keys.add(parameter_key)

        for item in near_misses:
            validation_metrics = item.get("validation_metrics") or {}
            train_metrics = item.get("train_metrics") or {}
            parameters = item.get("parameters") or {}
            parameter_key = _json_dumps(parameters)
            if parameter_key in seen_parameter_keys:
                continue
            validation_trade_count = int(validation_metrics.get("trade_count") or 0)
            validation_win_rate = float(validation_metrics.get("win_rate") or 0)
            validation_average_return = float(validation_metrics.get("average_return_pct") or 0)
            validation_cumulative_return = float(
                validation_metrics.get("equal_weight_cumulative_return_pct") or 0
            )
            if validation_trade_count < MIN_SHADOW_VALIDATION_TRADE_COUNT:
                continue
            if validation_trade_count >= MIN_SIGNAL_BACKTEST_TRADE_COUNT:
                continue
            if validation_win_rate < MIN_SHADOW_VALIDATION_WIN_RATE:
                continue
            if validation_cumulative_return < MIN_SHADOW_VALIDATION_CUMULATIVE_RETURN_PCT:
                continue
            if validation_average_return <= 0:
                continue

            confirmation_filter = str(parameters.get("confirmation_filter") or "")
            evidence_tags = ["validation_return_above_shadow_floor"]
            if confirmation_filter in DATASET1_EXPERIENCE_ALIGNED_FILTERS:
                evidence_tags.append("dataset1_experience_aligned_confirmation")
            if "reclaim" in confirmation_filter:
                evidence_tags.append("reclaim_confirmation_family")

            shadow_candidates.append(
                {
                    "shadow_status": "near_miss_requires_more_validation",
                    "source": "near_miss_validation_candidate",
                    "source_priority": 1,
                    "parameters": parameters,
                    "train_metrics": train_metrics,
                    "validation_metrics": validation_metrics,
                    "validation_trade_count": validation_trade_count,
                    "missing_validation_trades": max(
                        0,
                        MIN_SIGNAL_BACKTEST_TRADE_COUNT - validation_trade_count,
                    ),
                    "evidence_tags": evidence_tags,
                    "blocked_from_stable_reason": "validation_trade_count_below_stable_floor",
                    "allowed_effect": "expand_history_and_review_priority_only",
                    "review_only": True,
                    "simulation_only": True,
                }
            )
            seen_parameter_keys.add(parameter_key)

        shadow_candidates.sort(
            key=lambda row: (
                int(row.get("source_priority") or 9),
                -float((row.get("validation_metrics") or {}).get("equal_weight_cumulative_return_pct") or 0),
                -float((row.get("validation_metrics") or {}).get("average_return_pct") or 0),
                -float((row.get("validation_metrics") or {}).get("win_rate") or 0),
                _json_dumps(row.get("parameters") or {}),
            )
        )
        top_candidates = shadow_candidates[:5]
        expanded_history_review = self._shadow_parameter_expanded_history_review(
            replay=replay or {},
            expanded_signals=expanded_signals or [],
            shadow_candidates=top_candidates,
        )
        status = "review_ready" if top_candidates else "insufficient_shadow_evidence"
        selected_candidate_included = any(
            item.get("source") == "selected_stable_candidate" for item in top_candidates
        )
        next_action = (
            "expand_history_instances_for_selected_stable_candidate"
            if selected_candidate_included
            else
            "expand_history_instances_for_shadow_candidates"
            if top_candidates
            else "collect_more_actionable_signals_before_parameter_review"
        )
        return {
            "schema_version": "shadow_parameter_evidence.v1",
            "status": status,
            "shadow_candidate_count": len(shadow_candidates),
            "selected_candidate_included": selected_candidate_included,
            "top_shadow_candidates": top_candidates,
            "expanded_history_review": expanded_history_review,
            "stable_promotion_requirements": {
                "min_validation_trade_count": MIN_SIGNAL_BACKTEST_TRADE_COUNT,
                "min_validation_win_rate": MIN_OPTIMIZED_VALIDATION_WIN_RATE,
                "min_validation_cumulative_return_pct": MIN_OPTIMIZED_VALIDATION_CUMULATIVE_RETURN_PCT,
                "requires_positive_average_return": True,
                "requires_walk_forward_validation": True,
            },
            "shadow_thresholds": {
                "min_validation_trade_count": MIN_SHADOW_VALIDATION_TRADE_COUNT,
                "max_validation_trade_count": MIN_SIGNAL_BACKTEST_TRADE_COUNT - 1,
                "min_validation_win_rate": MIN_SHADOW_VALIDATION_WIN_RATE,
                "min_validation_cumulative_return_pct": MIN_SHADOW_VALIDATION_CUMULATIVE_RETURN_PCT,
            },
            "next_action": next_action,
            "allowed_effect": "review_and_dataset_expansion_only",
            "does_not_change": [
                "stable_candidate_parameters",
                "production_rules",
                "rules_yaml",
                "position_sizing",
                "broker_or_order_action",
                "live_trading_enabled",
            ],
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _shadow_parameter_expanded_history_review(
        self,
        replay: dict[str, Any],
        expanded_signals: list[dict[str, Any]],
        shadow_candidates: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if not shadow_candidates:
            return {
                "schema_version": "shadow_parameter_expanded_history_review.v1",
                "status": "skipped",
                "reason": "no_shadow_candidates",
                "reviewed_candidate_count": 0,
                "walk_forward_review": self._empty_shadow_walk_forward_review("no_shadow_candidates"),
                "weak_fold_attribution": self._empty_shadow_weak_fold_attribution("no_shadow_candidates"),
                "phase_context_split": self._empty_shadow_phase_context_split("no_shadow_candidates"),
                "next_action": "collect_more_shadow_candidate_samples",
                "items": [],
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            }

        ordered_signals = sorted(
            [
                signal
                for signal in expanded_signals
                if signal.get("action_label") in SIGNAL_BACKTEST_ACTIONS
            ],
            key=lambda item: (
                str(item.get("signal_date") or ""),
                str(item.get("symbol") or ""),
                str(item.get("pattern_id") or ""),
            ),
        )
        if len(ordered_signals) < MIN_SIGNAL_BACKTEST_TRADE_COUNT * 2:
            return {
                "schema_version": "shadow_parameter_expanded_history_review.v1",
                "status": "blocked",
                "reason": "too_few_expanded_signals_for_train_validation",
                "expanded_signal_count": len(ordered_signals),
                "reviewed_candidate_count": 0,
                "walk_forward_review": self._empty_shadow_walk_forward_review(
                    "too_few_expanded_signals_for_train_validation"
                ),
                "weak_fold_attribution": self._empty_shadow_weak_fold_attribution(
                    "too_few_expanded_signals_for_train_validation"
                ),
                "phase_context_split": self._empty_shadow_phase_context_split(
                    "too_few_expanded_signals_for_train_validation"
                ),
                "next_action": "collect_more_expanded_signals_before_walk_forward",
                "items": [],
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            }

        items: list[dict[str, Any]] = []
        for candidate in shadow_candidates:
            params = candidate.get("parameters") or {}
            entry_delay = int(params.get("entry_delay_days") or 1)
            horizon = int(params.get("horizon_days") or 5)
            complete_window = self._signals_with_complete_backtest_window(
                ordered_signals,
                entry_delay_days=entry_delay,
                horizon_days=horizon,
            )
            eligible = complete_window.get("signals") or []
            train_signals, validation_signals = self._chronological_signal_split(eligible)
            if not validation_signals:
                items.append(
                    {
                        "status": "blocked",
                        "reason": "no_expanded_validation_signals",
                        "parameters": params,
                        "complete_window": complete_window.get("summary") or {},
                        "expanded_signal_count": len(ordered_signals),
                        "eligible_signal_count": len(eligible),
                        "review_only": True,
                        "simulation_only": True,
                    }
                )
                continue

            backtest_kwargs = {
                "horizon_days": horizon,
                "entry_delay_days": entry_delay,
                "stop_loss_pct": float(params.get("stop_loss_pct") or 0.05),
                "take_profit_pct": float(params.get("take_profit_pct") or 0.08),
                "wait_position_ratio": float(params.get("wait_position_ratio") or 0.06),
                "buy_position_ratio": float(params.get("buy_position_ratio") or 0.08),
                "confirmation_filter": str(params.get("confirmation_filter") or "none"),
                "attribution_filter": str(params.get("attribution_filter") or "none"),
            }
            train = self._signal_backtest(
                replay,
                signals=train_signals,
                include_trades=False,
                **backtest_kwargs,
            )
            validation = self._signal_backtest(
                replay,
                signals=validation_signals,
                include_trades=False,
                **backtest_kwargs,
            )
            train_metrics = train.get("metrics") or {}
            validation_metrics = validation.get("metrics") or {}
            promotion_blockers: list[str] = []
            if int(validation_metrics.get("trade_count") or 0) < MIN_SIGNAL_BACKTEST_TRADE_COUNT:
                promotion_blockers.append("expanded_validation_trade_count_too_low")
            if float(validation_metrics.get("win_rate") or 0) < MIN_OPTIMIZED_VALIDATION_WIN_RATE:
                promotion_blockers.append("expanded_validation_win_rate_below_floor")
            if (
                float(validation_metrics.get("equal_weight_cumulative_return_pct") or 0)
                < MIN_OPTIMIZED_VALIDATION_CUMULATIVE_RETURN_PCT
            ):
                promotion_blockers.append("expanded_validation_return_below_floor")
            if float(validation_metrics.get("average_return_pct") or 0) <= 0:
                promotion_blockers.append("expanded_validation_average_return_not_positive")

            items.append(
                {
                    "status": "stable_thresholds_met_review_only" if not promotion_blockers else "blocked",
                    "parameters": params,
                    "expanded_signal_count": len(ordered_signals),
                    "eligible_signal_count": len(eligible),
                    "train_signal_count": len(train_signals),
                    "validation_signal_count": len(validation_signals),
                    "complete_window": complete_window.get("summary") or {},
                    "train_metrics": train_metrics,
                    "validation_metrics": validation_metrics,
                    "promotion_blockers": promotion_blockers,
                    "allowed_effect": "evidence_only_requires_walk_forward_review",
                    "review_only": True,
                    "simulation_only": True,
                }
            )

        items.sort(
            key=lambda item: (
                -float((item.get("validation_metrics") or {}).get("equal_weight_cumulative_return_pct") or 0),
                -float((item.get("validation_metrics") or {}).get("average_return_pct") or 0),
                _json_dumps(item.get("parameters") or {}),
            )
        )
        pass_count = sum(1 for item in items if item.get("status") == "stable_thresholds_met_review_only")
        walk_forward_candidates = [
            {
                "score": round(
                    float((item.get("validation_metrics") or {}).get("equal_weight_cumulative_return_pct") or 0)
                    + float((item.get("validation_metrics") or {}).get("win_rate") or 0) * 10
                    + float((item.get("validation_metrics") or {}).get("expectancy_pct") or 0),
                    6,
                ),
                "parameters": item.get("parameters") or {},
                "train_metrics": item.get("train_metrics") or {},
                "validation_metrics": item.get("validation_metrics") or {},
                "review_only": True,
                "simulation_only": True,
            }
            for item in items
            if item.get("status") == "stable_thresholds_met_review_only"
        ]
        walk_forward_review = (
            self._signal_walk_forward_validation(
                replay=replay,
                signals=ordered_signals,
                candidates=walk_forward_candidates,
            )
            if walk_forward_candidates
            else {
                "status": "skipped",
                "reason": "no_expanded_shadow_candidate_met_stable_thresholds",
                "candidate_count": 0,
                "gate": {
                    "status": "blocked",
                    "reasons": ["no_expanded_shadow_candidate_met_stable_thresholds"],
                    "requires_human_review": True,
                    "writes_rules_yaml": False,
                    "auto_apply": False,
                    "simulation_only": True,
                    "live_trading_enabled": settings.enable_live_trading,
                },
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            }
        )
        weak_fold_attribution = self._shadow_walk_forward_weak_fold_attribution(
            replay=replay,
            signals=ordered_signals,
            walk_forward_review=walk_forward_review,
        )
        phase_context_split = self._shadow_phase_context_split(
            replay=replay,
            signals=ordered_signals,
            reviewed_items=items,
        )
        walk_forward_reasons = (walk_forward_review.get("gate") or {}).get("reasons") or []
        if walk_forward_review.get("status") == "passed_for_simulation_review":
            next_action = "promote_shadow_candidate_to_stable_review_queue"
        elif "walk_forward_fold_trade_count_too_low" in walk_forward_reasons:
            next_action = "expand_reclaim_samples_across_more_time_folds"
        elif "walk_forward_min_fold_win_rate_too_low" in walk_forward_reasons:
            next_action = "stratify_shadow_candidate_by_phase_and_market_context"
        elif pass_count:
            next_action = "continue_walk_forward_review_before_stable_promotion"
        else:
            next_action = "collect_more_shadow_candidate_samples"
        return {
            "schema_version": "shadow_parameter_expanded_history_review.v1",
            "status": "review_ready" if items else "blocked",
            "expanded_signal_count": len(ordered_signals),
            "reviewed_candidate_count": len(items),
            "stable_threshold_review_count": pass_count,
            "walk_forward_review": walk_forward_review,
            "weak_fold_attribution": weak_fold_attribution,
            "phase_context_split": phase_context_split,
            "next_action": next_action,
            "items": items[:5],
            "allowed_effect": "evidence_only_no_rule_or_trade_change",
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _shadow_phase_context_split(
        self,
        replay: dict[str, Any],
        signals: list[dict[str, Any]],
        reviewed_items: list[dict[str, Any]],
    ) -> dict[str, Any]:
        stable_items = [
            item
            for item in reviewed_items
            if item.get("status") == "stable_thresholds_met_review_only"
        ]
        if not stable_items:
            return self._empty_shadow_phase_context_split("no_stable_threshold_shadow_items")

        candidate = stable_items[0]
        params = candidate.get("parameters") or {}
        entry_delay = int(params.get("entry_delay_days") or 1)
        horizon = int(params.get("horizon_days") or 5)
        complete_window = self._signals_with_complete_backtest_window(
            signals,
            entry_delay_days=entry_delay,
            horizon_days=horizon,
        )
        eligible = complete_window.get("signals") or []
        if not eligible:
            return self._empty_shadow_phase_context_split("no_complete_window_signals_for_phase_split")

        backtest = self._signal_backtest(
            replay,
            signals=eligible,
            horizon_days=horizon,
            entry_delay_days=entry_delay,
            stop_loss_pct=float(params.get("stop_loss_pct") or 0.05),
            take_profit_pct=float(params.get("take_profit_pct") or 0.08),
            wait_position_ratio=float(params.get("wait_position_ratio") or 0.06),
            buy_position_ratio=float(params.get("buy_position_ratio") or 0.08),
            confirmation_filter=str(params.get("confirmation_filter") or "none"),
            attribution_filter=str(params.get("attribution_filter") or "none"),
            include_trades=True,
            trade_limit=500,
        )
        trades = backtest.get("trades") or []
        buckets: dict[str, list[dict[str, Any]]] = {
            "risk_mixed": [],
            "follow_through": [],
            "stabilization": [],
            "other": [],
        }
        for trade in trades:
            buckets[self._shadow_trade_context_bucket(trade)].append(trade)

        bucket_rows = []
        for bucket_name, bucket_trades in buckets.items():
            summary = self._trade_return_summary(bucket_trades)
            tag_summary = self._trade_tag_summary(bucket_trades)
            passed_review = bool(
                int(summary.get("count") or 0) >= MIN_SIGNAL_BACKTEST_TRADE_COUNT
                and float(summary.get("win_rate") or 0) >= MIN_OPTIMIZED_VALIDATION_WIN_RATE
                and float(summary.get("cumulative_return_pct") or 0)
                >= MIN_OPTIMIZED_VALIDATION_CUMULATIVE_RETURN_PCT
                and float(summary.get("average_return_pct") or 0) > 0
            )
            bucket_rows.append(
                {
                    "bucket": bucket_name,
                    "status": "passed_context_review" if passed_review else "needs_more_review",
                    "trade_summary": summary,
                    "tag_summary": tag_summary,
                    "top_symbols": self._trade_count_rows(bucket_trades, "symbol", limit=6),
                    "top_patterns": self._trade_count_rows(bucket_trades, "pattern_id", limit=6),
                    "examples": self._compact_trade_examples(bucket_trades, limit=6),
                    "review_only": True,
                    "simulation_only": True,
                }
            )
        bucket_rows.sort(
            key=lambda row: (
                row["status"] != "passed_context_review",
                -float((row.get("trade_summary") or {}).get("cumulative_return_pct") or 0),
                str(row.get("bucket") or ""),
            )
        )
        passed_buckets = [
            row["bucket"]
            for row in bucket_rows
            if row.get("status") == "passed_context_review"
        ]
        risk_row = next((row for row in bucket_rows if row.get("bucket") == "risk_mixed"), {})
        risk_summary = risk_row.get("trade_summary") or {}
        if "follow_through" in passed_buckets:
            next_action = "walk_forward_follow_through_context_only"
        elif int(risk_summary.get("loss_count") or 0) > 0:
            next_action = "test_distribution_and_high_volatility_filters"
        elif passed_buckets:
            next_action = "review_passed_context_buckets"
        else:
            next_action = "collect_more_phase_context_samples"
        return {
            "schema_version": "shadow_phase_context_split.v1",
            "status": "review_ready",
            "parameters": params,
            "eligible_signal_count": len(eligible),
            "trade_count": len(trades),
            "overall_trade_summary": self._trade_return_summary(trades),
            "overall_tag_summary": self._trade_tag_summary(trades),
            "passed_context_buckets": passed_buckets,
            "buckets": bucket_rows,
            "filter_experiments": self._shadow_context_filter_experiments(
                replay=replay,
                signals=signals,
                base_params=params,
            ),
            "next_action": next_action,
            "allowed_effect": "review_only_context_filter_hypothesis",
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _shadow_context_filter_experiments(
        self,
        replay: dict[str, Any],
        signals: list[dict[str, Any]],
        base_params: dict[str, Any],
    ) -> dict[str, Any]:
        if not signals:
            return self._empty_shadow_context_filter_experiments("no_signals_for_filter_experiment")

        base = {
            "entry_delay_days": int(base_params.get("entry_delay_days") or 1),
            "horizon_days": int(base_params.get("horizon_days") or 5),
            "stop_loss_pct": float(base_params.get("stop_loss_pct") or 0.05),
            "take_profit_pct": float(base_params.get("take_profit_pct") or 0.08),
            "wait_position_ratio": float(base_params.get("wait_position_ratio") or 0.06),
            "buy_position_ratio": float(base_params.get("buy_position_ratio") or 0.08),
            "confirmation_filter": str(base_params.get("confirmation_filter") or "none"),
            "attribution_filter": str(base_params.get("attribution_filter") or "none"),
        }

        experiment_specs = [
            {
                "experiment_id": "base_shadow_candidate",
                "description": "Current best shadow candidate without an additional context prefilter.",
                "prefilter": "none",
                "params": {},
            },
            {
                "experiment_id": "strong_reclaim_confirmation",
                "description": "Require a stronger next-bar reclaim before simulated entry.",
                "prefilter": "none",
                "params": {"confirmation_filter": "strong_reclaim"},
            },
            {
                "experiment_id": "low_risk_stabilized_reclaim",
                "description": "Use Dataset1 low-risk stabilization confirmation to remove obvious distribution tags.",
                "prefilter": "none",
                "params": {"confirmation_filter": "dataset1_low_risk_stabilized_reclaim"},
            },
            {
                "experiment_id": "exclude_high_volatility_board",
                "description": "Exclude STAR and ChiNext high-volatility boards before backtesting.",
                "prefilter": "exclude_high_volatility_board",
                "params": {},
            },
            {
                "experiment_id": "exclude_distribution_risk_tags",
                "description": "Exclude Dataset1 distribution and stall risk tags before backtesting.",
                "prefilter": "exclude_distribution_risk_tags",
                "params": {},
            },
            {
                "experiment_id": "exclude_high_vol_and_distribution_risk",
                "description": "Exclude both high-volatility boards and Dataset1 distribution risk tags.",
                "prefilter": "exclude_high_vol_and_distribution_risk",
                "params": {},
            },
            {
                "experiment_id": "strong_reclaim_no_high_vol",
                "description": "Require strong reclaim and exclude high-volatility boards.",
                "prefilter": "exclude_high_volatility_board",
                "params": {"confirmation_filter": "strong_reclaim"},
            },
            {
                "experiment_id": "exclude_benchmark_neutral",
                "description": "Exclude signals from neutral benchmark context after market attribution showed weak neutral-regime returns.",
                "prefilter": "exclude_benchmark_neutral",
                "params": {},
            },
            {
                "experiment_id": "strong_reclaim_exclude_benchmark_neutral",
                "description": "Require strong reclaim and exclude neutral benchmark context.",
                "prefilter": "exclude_benchmark_neutral",
                "params": {"confirmation_filter": "strong_reclaim"},
            },
        ]

        items: list[dict[str, Any]] = []
        ordered_signals = sorted(
            [
                signal
                for signal in signals
                if signal.get("action_label") in SIGNAL_BACKTEST_ACTIONS
            ],
            key=lambda item: (
                str(item.get("signal_date") or ""),
                str(item.get("symbol") or ""),
                str(item.get("pattern_id") or ""),
            ),
        )
        for spec in experiment_specs:
            params = {**base, **(spec.get("params") or {})}
            prefilter = str(spec.get("prefilter") or "none")
            filtered_signals = self._shadow_prefilter_signals(ordered_signals, prefilter)
            complete_window = self._signals_with_complete_backtest_window(
                filtered_signals,
                entry_delay_days=int(params["entry_delay_days"]),
                horizon_days=int(params["horizon_days"]),
            )
            eligible = complete_window.get("signals") or []
            backtest = self._signal_backtest(
                replay,
                signals=eligible,
                horizon_days=int(params["horizon_days"]),
                entry_delay_days=int(params["entry_delay_days"]),
                stop_loss_pct=float(params["stop_loss_pct"]),
                take_profit_pct=float(params["take_profit_pct"]),
                wait_position_ratio=float(params["wait_position_ratio"]),
                buy_position_ratio=float(params["buy_position_ratio"]),
                confirmation_filter=str(params["confirmation_filter"]),
                attribution_filter=str(params["attribution_filter"]),
                include_trades=True,
                trade_limit=80,
            )
            metrics = backtest.get("metrics") or {}
            trades = backtest.get("trades") or []
            market_context = self._shadow_filter_market_context(trades)
            walk_forward = self._shadow_filter_experiment_walk_forward(
                replay=replay,
                signals=filtered_signals,
                params=params,
                metrics=metrics,
            )
            status = self._shadow_filter_experiment_status(metrics, walk_forward)
            items.append(
                {
                    "experiment_id": spec["experiment_id"],
                    "status": status,
                    "description": spec["description"],
                    "prefilter": prefilter,
                    "parameters": params,
                    "input_signal_count": len(ordered_signals),
                    "filtered_signal_count": len(filtered_signals),
                    "eligible_signal_count": len(eligible),
                    "complete_window": complete_window.get("summary") or {},
                    "metrics": metrics,
                    "walk_forward": walk_forward,
                    "market_context": market_context,
                    "tag_summary": self._trade_tag_summary(trades),
                    "top_symbols": self._trade_count_rows(trades, "symbol", limit=5),
                    "top_patterns": self._trade_count_rows(trades, "pattern_id", limit=5),
                    "examples": self._compact_trade_examples(trades, limit=5),
                    "allowed_effect": "review_only_filter_hypothesis",
                    "review_only": True,
                    "simulation_only": True,
                    "live_trading_enabled": settings.enable_live_trading,
                }
            )

        items.sort(
            key=lambda item: (
                item.get("status") != "passed_walk_forward_review",
                item.get("status") != "passed_metric_review_only",
                -float((item.get("metrics") or {}).get("equal_weight_cumulative_return_pct") or 0),
                -float((item.get("metrics") or {}).get("win_rate") or 0),
                str(item.get("experiment_id") or ""),
            )
        )
        passed_items = [
            item
            for item in items
            if item.get("status") in {"passed_walk_forward_review", "passed_metric_review_only"}
        ]
        strategy_comparison = self._shadow_filter_strategy_comparison(items)
        return {
            "schema_version": "shadow_context_filter_experiments.v1",
            "status": "review_ready" if items else "skipped",
            "experiment_count": len(items),
            "passed_experiment_count": len(passed_items),
            "items": items,
            "strategy_comparison": strategy_comparison,
            "next_action": "walk_forward_review_passed_filters" if passed_items else "collect_more_filter_experiment_samples",
            "allowed_effect": "review_only_filter_hypothesis_no_rule_or_trade_change",
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _shadow_prefilter_signals(self, signals: list[dict[str, Any]], prefilter: str) -> list[dict[str, Any]]:
        if prefilter in {"", "none", None}:
            return list(signals)
        if prefilter == "exclude_high_volatility_board":
            return [signal for signal in signals if not self._is_high_volatility_board_signal(signal)]
        if prefilter == "exclude_distribution_risk_tags":
            return [signal for signal in signals if not self._has_dataset1_distribution_risk(signal)]
        if prefilter == "exclude_high_vol_and_distribution_risk":
            return [
                signal
                for signal in signals
                if not self._is_high_volatility_board_signal(signal)
                and not self._has_dataset1_distribution_risk(signal)
            ]
        if prefilter == "exclude_benchmark_neutral":
            return [
                signal
                for signal in signals
                if self._phase_confidence_market_regime(str(signal.get("signal_date") or "")).get("regime")
                != "benchmark_neutral"
            ]
        return list(signals)

    def _is_high_volatility_board_signal(self, signal: dict[str, Any]) -> bool:
        symbol = str(signal.get("symbol") or "")
        normalized = normalize_a_share_code(symbol) if symbol else ""
        return bool(
            symbol.startswith(("SH688", "SZ300", "SZ301"))
            or normalized.startswith(("SH688", "SZ300", "SZ301"))
            or infer_board_type(normalized, None) in {"star", "chinext"}
        )

    def _shadow_filter_experiment_walk_forward(
        self,
        replay: dict[str, Any],
        signals: list[dict[str, Any]],
        params: dict[str, Any],
        metrics: dict[str, Any],
    ) -> dict[str, Any]:
        if int(metrics.get("trade_count") or 0) < MIN_SIGNAL_BACKTEST_TRADE_COUNT:
            return {
                "status": "skipped",
                "reason": "too_few_full_history_trades_for_walk_forward",
                "gate": {
                    "status": "blocked",
                    "reasons": ["too_few_full_history_trades_for_walk_forward"],
                    "requires_human_review": True,
                    "writes_rules_yaml": False,
                    "auto_apply": False,
                    "simulation_only": True,
                    "live_trading_enabled": settings.enable_live_trading,
                },
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            }
        candidate = {
            "score": round(
                float(metrics.get("equal_weight_cumulative_return_pct") or 0)
                + float(metrics.get("win_rate") or 0) * 10
                + float(metrics.get("expectancy_pct") or 0),
                6,
            ),
            "parameters": params,
            "train_metrics": metrics,
            "validation_metrics": metrics,
            "review_only": True,
            "simulation_only": True,
        }
        return self._signal_walk_forward_validation(
            replay=replay,
            signals=signals,
            candidates=[candidate],
        )

    def _shadow_filter_experiment_status(
        self,
        metrics: dict[str, Any],
        walk_forward: dict[str, Any],
    ) -> str:
        if walk_forward.get("status") == "passed_for_simulation_review":
            return "passed_walk_forward_review"
        if self._validation_metrics_pass(metrics):
            return "passed_metric_review_only"
        return "blocked"

    def _shadow_filter_strategy_comparison(self, items: list[dict[str, Any]]) -> dict[str, Any]:
        if not items:
            return self._empty_shadow_filter_strategy_comparison("no_filter_experiment_items")

        rows: list[dict[str, Any]] = []
        for item in items:
            metrics = item.get("metrics") or {}
            walk_forward = item.get("walk_forward") or {}
            gate = walk_forward.get("gate") or {}
            gate_reasons = [str(reason) for reason in (gate.get("reasons") or [])]
            market_context = item.get("market_context") or {}
            market_warnings = [str(warning) for warning in (market_context.get("warnings") or [])]
            trade_count = int(metrics.get("trade_count") or 0)
            win_rate = float(metrics.get("win_rate") or 0)
            average_return = float(metrics.get("average_return_pct") or 0)
            cumulative_return = float(metrics.get("equal_weight_cumulative_return_pct") or 0)
            eligible_count = int(item.get("eligible_signal_count") or 0)
            filtered_count = int(item.get("filtered_signal_count") or 0)
            input_count = int(item.get("input_signal_count") or 0)
            sample_gap = max(0, MIN_WALK_FORWARD_TRADE_COUNT * MIN_WALK_FORWARD_FOLD_COUNT - trade_count)
            sample_retention = round(filtered_count / input_count, 6) if input_count else 0.0
            execution_retention = round(trade_count / eligible_count, 6) if eligible_count else 0.0
            score = round(
                min(cumulative_return, 220.0) * 0.25
                + win_rate * 45.0
                + max(average_return, 0.0) * 4.0
                + min(trade_count, 30) * 0.8
                + (15.0 if walk_forward.get("status") == "passed_for_simulation_review" else 0.0)
                - sample_gap * 1.2
                - len(gate_reasons) * 3.0
                - len(market_warnings) * 2.0,
                6,
            )
            blockers: list[str] = []
            if item.get("status") == "blocked":
                blockers.append("full_history_metric_gate_not_passed")
            if walk_forward.get("status") != "passed_for_simulation_review":
                blockers.extend(gate_reasons or ["walk_forward_not_passed"])
            if sample_gap:
                blockers.append("needs_more_complete_window_trades")
            if trade_count < MIN_WALK_FORWARD_TRADE_COUNT:
                blockers.append("too_few_trades_for_strategy_comparison")
            if market_warnings:
                blockers.append("market_context_needs_more_review")

            if walk_forward.get("status") == "passed_for_simulation_review":
                tier = "stable_walk_forward_candidate_review_only"
                next_action = "human_review_before_any_simulation_permission_change"
            elif item.get("status") == "passed_metric_review_only":
                tier = "metric_candidate_needs_walk_forward"
                next_action = "expand_samples_and_repeat_walk_forward"
            else:
                tier = "blocked_filter_hypothesis"
                next_action = "collect_more_samples_or_drop_filter"

            rows.append(
                {
                    "experiment_id": item.get("experiment_id"),
                    "tier": tier,
                    "review_priority_score": score,
                    "sample_gap_to_walk_forward_budget": sample_gap,
                    "sample_retention": sample_retention,
                    "execution_retention": execution_retention,
                    "metrics": {
                        "trade_count": trade_count,
                        "win_rate": metrics.get("win_rate"),
                        "average_return_pct": metrics.get("average_return_pct"),
                        "equal_weight_cumulative_return_pct": metrics.get("equal_weight_cumulative_return_pct"),
                    },
                    "walk_forward_status": walk_forward.get("status"),
                    "market_context_status": market_context.get("status"),
                    "market_context": {
                        "by_market_regime": (market_context.get("by_market_regime") or [])[:4],
                        "warnings": market_warnings,
                    },
                    "promotion_blockers": sorted(set(blockers)),
                    "next_action": next_action,
                    "allowed_effect": "review_priority_only",
                    "review_only": True,
                    "simulation_only": True,
                    "live_trading_enabled": settings.enable_live_trading,
                }
            )

        rows.sort(
            key=lambda row: (
                row["tier"] != "stable_walk_forward_candidate_review_only",
                row["tier"] != "metric_candidate_needs_walk_forward",
                -float(row.get("review_priority_score") or 0),
                str(row.get("experiment_id") or ""),
            )
        )
        metric_candidates = [row for row in rows if row["tier"] == "metric_candidate_needs_walk_forward"]
        stable_candidates = [row for row in rows if row["tier"] == "stable_walk_forward_candidate_review_only"]
        next_action = (
            "human_review_stable_walk_forward_candidates"
            if stable_candidates
            else "expand_metric_candidates_across_more_symbols_and_time_windows"
            if metric_candidates
            else "collect_more_filter_experiment_samples"
        )
        top_review_priorities = rows[:5]
        return {
            "schema_version": "shadow_filter_strategy_comparison.v1",
            "status": "review_ready",
            "ranking_basis": [
                "walk_forward_status",
                "full_history_cumulative_return",
                "win_rate",
                "average_return",
                "sample_gap",
                "market_regime_context",
            ],
            "sample_budget_target": {
                "min_walk_forward_fold_count": MIN_WALK_FORWARD_FOLD_COUNT,
                "min_walk_forward_trade_count": MIN_WALK_FORWARD_TRADE_COUNT,
                "target_complete_window_trades": MIN_WALK_FORWARD_TRADE_COUNT * MIN_WALK_FORWARD_FOLD_COUNT,
            },
            "top_review_priority": top_review_priorities,
            "top_review_priorities": top_review_priorities,
            "stable_candidate_count": len(stable_candidates),
            "metric_candidate_count": len(metric_candidates),
            "next_action": next_action,
            "permission_policy": {
                "may_change_rules_yaml": False,
                "may_change_position_size": False,
                "may_enable_screen_click": False,
                "requires_human_review": True,
                "reason": "strategy_comparison_is_research_evidence_until_walk_forward_and_sim_cockpit_readback_pass",
            },
            "allowed_effect": "review_priority_only",
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _empty_shadow_filter_strategy_comparison(self, reason: str) -> dict[str, Any]:
        return {
            "schema_version": "shadow_filter_strategy_comparison.v1",
            "status": "skipped",
            "reason": reason,
            "ranking_basis": [
                "walk_forward_status",
                "full_history_cumulative_return",
                "win_rate",
                "average_return",
                "sample_gap",
                "market_regime_context",
            ],
            "sample_budget_target": {
                "min_walk_forward_fold_count": MIN_WALK_FORWARD_FOLD_COUNT,
                "min_walk_forward_trade_count": MIN_WALK_FORWARD_TRADE_COUNT,
                "target_complete_window_trades": MIN_WALK_FORWARD_TRADE_COUNT * MIN_WALK_FORWARD_FOLD_COUNT,
            },
            "top_review_priority": [],
            "top_review_priorities": [],
            "stable_candidate_count": 0,
            "metric_candidate_count": 0,
            "next_action": "collect_more_filter_experiment_samples",
            "permission_policy": {
                "may_change_rules_yaml": False,
                "may_change_position_size": False,
                "may_enable_screen_click": False,
                "requires_human_review": True,
                "reason": "no_filter_experiment_items",
            },
            "allowed_effect": "review_priority_only",
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _shadow_filter_market_context(self, trades: list[dict[str, Any]]) -> dict[str, Any]:
        if not trades:
            return self._empty_shadow_filter_market_context("no_trades_for_market_context")

        regime_cache: dict[str, dict[str, Any]] = {}
        by_market: dict[str, list[dict[str, Any]]] = defaultdict(list)
        examples: list[dict[str, Any]] = []
        for trade in trades:
            signal_date = str(trade.get("signal_date") or "")
            if signal_date not in regime_cache:
                regime_cache[signal_date] = self._phase_confidence_market_regime(signal_date)
            market = regime_cache[signal_date]
            regime = str(market.get("regime") or "insufficient_benchmark_data")
            by_market[regime].append(trade)
            if len(examples) < 5:
                examples.append(
                    {
                        "symbol": trade.get("symbol"),
                        "signal_date": signal_date,
                        "realized_pnl_pct": trade.get("realized_pnl_pct"),
                        "benchmark_symbol": market.get("benchmark_symbol"),
                        "market_regime": regime,
                        "benchmark_return_pct": market.get("return_pct"),
                        "review_only": True,
                        "simulation_only": True,
                    }
                )

        rows: list[dict[str, Any]] = []
        for regime, regime_trades in by_market.items():
            summary = self._trade_return_summary(regime_trades)
            rows.append(
                {
                    "key": regime,
                    "trade_count": summary.get("count", 0),
                    "win_rate": summary.get("win_rate", 0.0),
                    "average_return_pct": summary.get("average_return_pct", 0.0),
                    "cumulative_return_pct": summary.get("cumulative_return_pct", 0.0),
                    "loss_count": summary.get("loss_count", 0),
                    "review_only": True,
                    "simulation_only": True,
                }
            )
        rows.sort(
            key=lambda row: (
                -int(row.get("trade_count") or 0),
                -float(row.get("cumulative_return_pct") or 0),
                str(row.get("key") or ""),
            )
        )

        warnings: list[str] = []
        meaningful_rows = [row for row in rows if row.get("key") != "insufficient_benchmark_data"]
        if len(meaningful_rows) < 2:
            warnings.append("limited_market_regime_coverage")
        total_trades = len(trades)
        if total_trades >= 6 and rows:
            top_share = int(rows[0].get("trade_count") or 0) / total_trades
            if top_share >= 0.75:
                warnings.append("market_regime_concentration_high")
        for row in rows:
            if int(row.get("trade_count") or 0) < 2:
                continue
            if float(row.get("win_rate") or 0) < 0.5:
                warnings.append(f"market_{row.get('key')}_win_rate_below_50_pct")
            if float(row.get("cumulative_return_pct") or 0) < 0:
                warnings.append(f"market_{row.get('key')}_cumulative_return_negative")

        return {
            "schema_version": "shadow_filter_market_context.v1",
            "status": "robust_enough_for_review" if not warnings else "needs_more_market_context",
            "by_market_regime": rows,
            "market_context_examples": examples,
            "warnings": sorted(set(warnings)),
            "allowed_effect": "review_context_only",
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _empty_shadow_filter_market_context(self, reason: str) -> dict[str, Any]:
        return {
            "schema_version": "shadow_filter_market_context.v1",
            "status": "skipped",
            "reason": reason,
            "by_market_regime": [],
            "market_context_examples": [],
            "warnings": [],
            "allowed_effect": "review_context_only",
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _empty_shadow_context_filter_experiments(self, reason: str) -> dict[str, Any]:
        return {
            "schema_version": "shadow_context_filter_experiments.v1",
            "status": "skipped",
            "reason": reason,
            "experiment_count": 0,
            "passed_experiment_count": 0,
            "items": [],
            "strategy_comparison": self._empty_shadow_filter_strategy_comparison(reason),
            "next_action": "collect_more_filter_experiment_samples",
            "allowed_effect": "review_only_filter_hypothesis_no_rule_or_trade_change",
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _shadow_trade_context_bucket(self, trade: dict[str, Any]) -> str:
        phase = self._trade_phase_label(trade)
        tags = set(self._trade_learning_tags(trade))
        has_risk = any(
            tag.endswith("_risk")
            or tag in {"stop_loss_triggered", "filtered_loss_sample", "distribution_or_stall_risk"}
            for tag in tags
        )
        has_opportunity = self._trade_has_opportunity(list(tags))
        if phase == "distribution_or_failed_markup" or (has_risk and has_opportunity):
            return "risk_mixed"
        if phase == "missed_follow_through" or "follow_through_winner" in tags:
            return "follow_through"
        if phase == "stabilization_probe" or "stabilization_probe" in tags:
            return "stabilization"
        return "other"

    def _trade_count_rows(self, trades: list[dict[str, Any]], field: str, limit: int = 6) -> list[dict[str, Any]]:
        counts = Counter(str(trade.get(field) or "unknown") for trade in trades)
        return [
            {field: value, "count": count}
            for value, count in counts.most_common(limit)
        ]

    def _compact_trade_examples(self, trades: list[dict[str, Any]], limit: int = 6) -> list[dict[str, Any]]:
        ordered = sorted(
            trades,
            key=lambda trade: abs(float(trade.get("realized_pnl_pct") or 0)),
            reverse=True,
        )
        return [
            {
                "symbol": trade.get("symbol"),
                "pattern_id": trade.get("pattern_id"),
                "signal_date": trade.get("signal_date"),
                "entry_date": trade.get("entry_date"),
                "exit_date": trade.get("exit_date"),
                "realized_pnl_pct": trade.get("realized_pnl_pct"),
                "phase_label": self._trade_phase_label(trade),
                "learning_tags": self._trade_learning_tags(trade),
                "context_bucket": self._shadow_trade_context_bucket(trade),
                "review_only": True,
                "simulation_only": True,
            }
            for trade in ordered[:limit]
        ]

    def _empty_shadow_phase_context_split(self, reason: str) -> dict[str, Any]:
        return {
            "schema_version": "shadow_phase_context_split.v1",
            "status": "skipped",
            "reason": reason,
            "eligible_signal_count": 0,
            "trade_count": 0,
            "overall_trade_summary": self._trade_return_summary([]),
            "overall_tag_summary": self._trade_tag_summary([]),
            "passed_context_buckets": [],
            "buckets": [],
            "filter_experiments": self._empty_shadow_context_filter_experiments(reason),
            "next_action": "collect_more_phase_context_samples",
            "allowed_effect": "review_only_context_filter_hypothesis",
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _shadow_walk_forward_weak_fold_attribution(
        self,
        replay: dict[str, Any],
        signals: list[dict[str, Any]],
        walk_forward_review: dict[str, Any],
    ) -> dict[str, Any]:
        best = walk_forward_review.get("best") or {}
        params = best.get("parameters") or {}
        fold_metrics = best.get("folds") or []
        if not params or not fold_metrics:
            return {
                "schema_version": "shadow_walk_forward_weak_fold_attribution.v1",
                "status": "skipped",
                "reason": "no_walk_forward_fold_details",
                "weak_fold_count": 0,
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            }

        entry_delay = int(params.get("entry_delay_days") or 1)
        horizon = int(params.get("horizon_days") or 5)
        complete_window = self._signals_with_complete_backtest_window(
            signals,
            entry_delay_days=entry_delay,
            horizon_days=horizon,
        )
        folds = self._walk_forward_signal_folds(complete_window.get("signals") or [])
        fold_metrics_by_index = {
            int(row.get("fold_index") or 0): row
            for row in fold_metrics
            if int(row.get("fold_index") or 0) > 0
        }
        weak_folds: list[dict[str, Any]] = []
        weak_trades: list[dict[str, Any]] = []
        backtest_kwargs = {
            "horizon_days": horizon,
            "entry_delay_days": entry_delay,
            "stop_loss_pct": float(params.get("stop_loss_pct") or 0.05),
            "take_profit_pct": float(params.get("take_profit_pct") or 0.08),
            "wait_position_ratio": float(params.get("wait_position_ratio") or 0.06),
            "buy_position_ratio": float(params.get("buy_position_ratio") or 0.08),
            "confirmation_filter": str(params.get("confirmation_filter") or "none"),
            "attribution_filter": str(params.get("attribution_filter") or "none"),
        }
        for index, fold_signals in enumerate(folds, start=1):
            metrics = fold_metrics_by_index.get(index) or {}
            weak_reasons: list[str] = []
            if int(metrics.get("trade_count") or 0) < MIN_WALK_FORWARD_FOLD_TRADE_COUNT:
                weak_reasons.append("fold_trade_count_too_low")
            if float(metrics.get("win_rate") or 0) < MIN_WALK_FORWARD_MIN_FOLD_WIN_RATE:
                weak_reasons.append("fold_win_rate_below_floor")
            if float(metrics.get("equal_weight_cumulative_return_pct") or 0) < 0:
                weak_reasons.append("fold_cumulative_return_negative")
            if not weak_reasons:
                continue

            backtest = self._signal_backtest(
                replay,
                signals=fold_signals,
                include_trades=True,
                trade_limit=100,
                **backtest_kwargs,
            )
            trades = backtest.get("trades") or []
            weak_trades.extend(trades)
            weak_folds.append(
                {
                    "fold_index": index,
                    "start_signal_date": metrics.get("start_signal_date"),
                    "end_signal_date": metrics.get("end_signal_date"),
                    "signal_count": len(fold_signals),
                    "metrics": {
                        "trade_count": metrics.get("trade_count"),
                        "win_rate": metrics.get("win_rate"),
                        "average_return_pct": metrics.get("average_return_pct"),
                        "equal_weight_cumulative_return_pct": metrics.get(
                            "equal_weight_cumulative_return_pct"
                        ),
                    },
                    "weak_reasons": weak_reasons,
                    "trade_summary": self._trade_return_summary(trades),
                    "tag_summary": self._trade_tag_summary(trades),
                    "review_only": True,
                    "simulation_only": True,
                }
            )

        symbol_counts = Counter(str(trade.get("symbol") or "unknown") for trade in weak_trades)
        pattern_counts = Counter(str(trade.get("pattern_id") or "unknown") for trade in weak_trades)
        weak_trade_examples = sorted(
            weak_trades,
            key=lambda trade: float(trade.get("realized_pnl_pct") or 0),
        )[:10]
        weak_reason_counts = Counter(
            reason
            for fold in weak_folds
            for reason in (fold.get("weak_reasons") or [])
        )
        if weak_reason_counts.get("fold_trade_count_too_low"):
            next_action = "expand_reclaim_samples_across_more_time_folds"
        elif weak_reason_counts.get("fold_win_rate_below_floor"):
            next_action = "stratify_by_phase_symbol_and_market_context"
        elif weak_folds:
            next_action = "review_weak_fold_trade_examples"
        else:
            next_action = "no_weak_fold_attribution_needed"
        return {
            "schema_version": "shadow_walk_forward_weak_fold_attribution.v1",
            "status": "review_ready" if weak_folds else "skipped",
            "weak_fold_count": len(weak_folds),
            "weak_trade_count": len(weak_trades),
            "weak_reason_counts": dict(weak_reason_counts),
            "weak_folds": weak_folds[:4],
            "weak_trade_summary": self._trade_return_summary(weak_trades),
            "weak_tag_summary": self._trade_tag_summary(weak_trades),
            "top_symbols": [
                {"symbol": symbol, "count": count}
                for symbol, count in symbol_counts.most_common(8)
            ],
            "top_patterns": [
                {"pattern_id": pattern_id, "count": count}
                for pattern_id, count in pattern_counts.most_common(8)
            ],
            "weak_trade_examples": [
                {
                    "symbol": trade.get("symbol"),
                    "pattern_id": trade.get("pattern_id"),
                    "signal_date": trade.get("signal_date"),
                    "entry_date": trade.get("entry_date"),
                    "exit_date": trade.get("exit_date"),
                    "realized_pnl_pct": trade.get("realized_pnl_pct"),
                    "phase_label": self._trade_phase_label(trade),
                    "learning_tags": self._trade_learning_tags(trade),
                    "entry_gap_pct": trade.get("entry_gap_pct"),
                    "entry_close_vs_signal_pct": trade.get("entry_close_vs_signal_pct"),
                    "review_only": True,
                    "simulation_only": True,
                }
                for trade in weak_trade_examples
            ],
            "next_action": next_action,
            "allowed_effect": "review_only_phase_context_diagnosis",
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _empty_shadow_weak_fold_attribution(self, reason: str) -> dict[str, Any]:
        return {
            "schema_version": "shadow_walk_forward_weak_fold_attribution.v1",
            "status": "skipped",
            "reason": reason,
            "weak_fold_count": 0,
            "weak_trade_count": 0,
            "weak_reason_counts": {},
            "weak_folds": [],
            "weak_trade_summary": self._trade_return_summary([]),
            "weak_tag_summary": self._trade_tag_summary([]),
            "top_symbols": [],
            "top_patterns": [],
            "weak_trade_examples": [],
            "next_action": "collect_more_shadow_candidate_samples",
            "allowed_effect": "review_only_phase_context_diagnosis",
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _empty_shadow_walk_forward_review(self, reason: str) -> dict[str, Any]:
        return {
            "status": "skipped",
            "reason": reason,
            "candidate_count": 0,
            "gate": {
                "status": "blocked",
                "reasons": [reason],
                "requires_human_review": True,
                "writes_rules_yaml": False,
                "auto_apply": False,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            },
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _signal_optimization_sample(self, replay: dict[str, Any]) -> dict[str, Any]:
        primary = [
            signal
            for signal in replay.get("signals") or []
            if signal.get("action_label") in SIGNAL_BACKTEST_ACTIONS
        ]
        recent = [
            signal
            for signal in replay.get("recent_signals") or []
            if signal.get("action_label") in SIGNAL_BACKTEST_ACTIONS
        ]
        expanded = [
            signal
            for signal in replay.get("expanded_signals") or []
            if signal.get("action_label") in SIGNAL_BACKTEST_ACTIONS
        ]
        by_key: dict[tuple[str, str, str, str], dict[str, Any]] = {}
        for signal in [*primary, *recent, *expanded]:
            key = (
                str(signal.get("symbol") or ""),
                str(signal.get("signal_date") or ""),
                str(signal.get("pattern_id") or ""),
                str(signal.get("action_label") or ""),
            )
            existing = by_key.get(key)
            if existing is None or float(signal.get("score") or 0) > float(existing.get("score") or 0):
                by_key[key] = signal
        ordered = sorted(
            by_key.values(),
            key=lambda item: (
                str(item.get("signal_date") or ""),
                str(item.get("symbol") or ""),
                str(item.get("pattern_id") or ""),
            ),
        )
        deep_optimization = os.getenv("OFFHOUR_RESEARCH_DEEP_OPTIMIZATION", "").lower() in {"1", "true", "yes"}
        window_entry_delay = (
            MAX_DEEP_SIGNAL_OPTIMIZATION_ENTRY_DELAY_DAYS
            if deep_optimization
            else MAX_SIGNAL_OPTIMIZATION_ENTRY_DELAY_DAYS
        )
        window_horizon = (
            MAX_DEEP_SIGNAL_OPTIMIZATION_HORIZON_DAYS
            if deep_optimization
            else MAX_SIGNAL_OPTIMIZATION_HORIZON_DAYS
        )
        previous_series_cache = getattr(self, "_daily_bar_series_cache", None)
        if previous_series_cache is None:
            self._daily_bar_series_cache = {}
        try:
            complete_window = self._signals_with_complete_backtest_window(
                ordered,
                entry_delay_days=window_entry_delay,
                horizon_days=window_horizon,
            )
        finally:
            if previous_series_cache is None:
                self._daily_bar_series_cache = previous_series_cache
        complete_ordered = complete_window.get("signals") or []
        sample_source = complete_ordered if len(complete_ordered) >= MIN_SIGNAL_BACKTEST_TRADE_COUNT * 2 else ordered
        truncated = len(sample_source) > MAX_SIGNAL_OPTIMIZATION_SIGNAL_COUNT
        signals = sample_source[-MAX_SIGNAL_OPTIMIZATION_SIGNAL_COUNT:]
        first_date = str(signals[0].get("signal_date") or "") if signals else None
        last_date = str(signals[-1].get("signal_date") or "") if signals else None
        return {
            "signals": signals,
            "expanded_signals": sample_source,
            "summary": {
                "schema_version": "signal_optimization_sample.v1",
                "source": "signals_plus_recent_signals" if recent else "signals",
                "primary_actionable_count": len(primary),
                "recent_actionable_count": len(recent),
                "expanded_actionable_count": len(expanded),
                "deduped_actionable_count": len(ordered),
                "complete_window_actionable_count": len(complete_ordered),
                "optimized_signal_count": len(signals),
                "max_signal_count": MAX_SIGNAL_OPTIMIZATION_SIGNAL_COUNT,
                "max_expanded_signal_count": MAX_SIGNAL_OPTIMIZATION_EXPANDED_SIGNAL_COUNT,
                "complete_window": complete_window.get("summary") or {},
                "complete_window_filter": {
                    "entry_delay_days": window_entry_delay,
                    "horizon_days": window_horizon,
                    "fallback_used": sample_source is ordered,
                    "reason": "too_few_complete_window_signals" if sample_source is ordered else None,
                    "review_only": True,
                    "simulation_only": True,
                },
                "truncated_to_recent_window": truncated,
                "first_signal_date": first_date,
                "last_signal_date": last_date,
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            },
        }

    def _chronological_signal_split(
        self,
        signals: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        if len(signals) < MIN_SIGNAL_BACKTEST_TRADE_COUNT * 2:
            return signals, []
        split_index = max(MIN_SIGNAL_BACKTEST_TRADE_COUNT, int(len(signals) * 0.7))
        split_index = min(split_index, len(signals) - MIN_SIGNAL_BACKTEST_TRADE_COUNT)
        return signals[:split_index], signals[split_index:]

    def _signals_with_complete_backtest_window(
        self,
        signals: list[dict[str, Any]],
        entry_delay_days: int,
        horizon_days: int,
    ) -> dict[str, Any]:
        ordered = sorted(
            [
                signal
                for signal in signals
                if signal.get("action_label") in SIGNAL_BACKTEST_ACTIONS
            ],
            key=lambda item: (str(item.get("signal_date") or ""), str(item.get("symbol") or "")),
        )
        if getattr(self, "_daily_bar_series_cache", None) is None:
            return {
                "signals": ordered,
                "summary": {
                    "schema_version": "signal_complete_backtest_window.v1",
                    "status": "not_checked",
                    "reason": "daily_bar_series_cache_not_initialized",
                    "input_signal_count": len(ordered),
                    "eligible_signal_count": len(ordered),
                    "no_entry_bar_count": 0,
                    "incomplete_exit_window_count": 0,
                    "entry_delay_days": int(entry_delay_days),
                    "horizon_days": int(horizon_days),
                    "review_only": True,
                    "simulation_only": True,
                    "live_trading_enabled": settings.enable_live_trading,
                },
            }

        eligible: list[dict[str, Any]] = []
        no_entry_bar_count = 0
        incomplete_exit_window_count = 0
        offset = max(0, int(entry_delay_days) - 1)
        min_exit_rows = max(1, int(horizon_days))
        for signal in ordered:
            symbol = str(signal.get("symbol") or "")
            signal_date = str(signal.get("signal_date") or "")
            if not symbol or not signal_date:
                no_entry_bar_count += 1
                continue
            entry_bar = self._next_ready_bar(symbol, signal_date, offset=offset)
            if not entry_bar:
                no_entry_bar_count += 1
                continue
            if self._ready_bar_count_after(symbol, str(entry_bar.get("trade_date") or "")) < min_exit_rows:
                incomplete_exit_window_count += 1
                continue
            eligible.append(signal)

        return {
            "signals": eligible,
            "summary": {
                "schema_version": "signal_complete_backtest_window.v1",
                "status": "checked",
                "input_signal_count": len(ordered),
                "eligible_signal_count": len(eligible),
                "no_entry_bar_count": no_entry_bar_count,
                "incomplete_exit_window_count": incomplete_exit_window_count,
                "entry_delay_days": int(entry_delay_days),
                "horizon_days": int(horizon_days),
                "min_exit_rows": min_exit_rows,
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            },
        }

    def _ready_bar_count_after(self, symbol: str, trade_date: str) -> int:
        cache = getattr(self, "_signal_backtest_cache", None)
        cache_key = ("ready_bar_count_after", symbol, trade_date)
        if cache is not None and cache_key in cache:
            return int(cache[cache_key] or 0)
        series = self._ready_bars_for_symbol(symbol)
        if series is not None:
            result = sum(1 for row in series if str(row.get("trade_date") or "") > trade_date)
        else:
            row = self.store.fetch_one(
                """
                SELECT COUNT(*) AS count
                FROM daily_bar_cache
                WHERE symbol = ?
                  AND quality_status = 'ready'
                  AND trade_date > ?
                  AND trade_date != 'ERROR'
                """,
                (symbol, trade_date),
            )
            result = int(row["count"] or 0) if row else 0
        if cache is not None:
            cache[cache_key] = result
        return int(result)

    def _complete_window_budget(self, window_cache: dict[tuple[int, int], dict[str, Any]]) -> dict[str, Any]:
        summaries = [item.get("summary") or {} for item in window_cache.values()]
        eligible_counts = [int(item.get("eligible_signal_count") or 0) for item in summaries]
        incomplete_count = sum(int(item.get("incomplete_exit_window_count") or 0) for item in summaries)
        no_entry_count = sum(int(item.get("no_entry_bar_count") or 0) for item in summaries)
        return {
            "schema_version": "signal_complete_backtest_window_budget.v1",
            "entry_horizon_check_count": len(summaries),
            "min_eligible_signal_count": min(eligible_counts) if eligible_counts else 0,
            "max_eligible_signal_count": max(eligible_counts) if eligible_counts else 0,
            "total_no_entry_bar_count": no_entry_count,
            "total_incomplete_exit_window_count": incomplete_count,
            "checks": summaries,
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _signal_learning_filter_candidates(
        self,
        replay: dict[str, Any],
        train_signals: list[dict[str, Any]],
        validation_signals: list[dict[str, Any]],
        base_candidates: list[dict[str, Any]],
        experience_aligned_candidates: list[dict[str, Any]],
        all_signals: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        filters = [item for item in SIGNAL_OPTIMIZATION_ATTRIBUTION_FILTERS if item != "none"]
        pool: list[dict[str, Any]] = []
        seen: set[str] = set()
        for candidate in [*base_candidates[:8], *experience_aligned_candidates[:4]]:
            params = candidate.get("parameters") or {}
            key = _json_dumps(
                {
                    "entry_delay_days": params.get("entry_delay_days"),
                    "horizon_days": params.get("horizon_days"),
                    "stop_loss_pct": params.get("stop_loss_pct"),
                    "take_profit_pct": params.get("take_profit_pct"),
                    "confirmation_filter": params.get("confirmation_filter"),
                }
            )
            if not params or key in seen:
                continue
            seen.add(key)
            pool.append(candidate)

        accepted: list[dict[str, Any]] = []
        train_evaluation_count = 0
        validation_evaluation_count = 0
        skipped_by_train_gate = 0
        skipped_by_complete_window = 0
        window_cache: dict[tuple[int, int], dict[str, Any]] = {}
        for candidate in pool:
            params = candidate.get("parameters") or {}
            candidate_train_signals = train_signals
            candidate_validation_signals = validation_signals
            if all_signals is not None:
                entry_delay = int(params.get("entry_delay_days") or 1)
                horizon = int(params.get("horizon_days") or 5)
                window_key = (entry_delay, horizon)
                if window_key not in window_cache:
                    window_cache[window_key] = self._signals_with_complete_backtest_window(
                        all_signals,
                        entry_delay_days=entry_delay,
                        horizon_days=horizon,
                    )
                candidate_train_signals, candidate_validation_signals = self._chronological_signal_split(
                    window_cache[window_key]["signals"]
                )
            for attribution_filter in filters:
                if (
                    len(candidate_train_signals) < MIN_SIGNAL_BACKTEST_TRADE_COUNT
                    or len(candidate_validation_signals) < MIN_SIGNAL_BACKTEST_TRADE_COUNT
                ):
                    skipped_by_complete_window += 1
                    continue
                train = self._signal_backtest(
                    replay,
                    horizon_days=int(params.get("horizon_days") or 5),
                    entry_delay_days=int(params.get("entry_delay_days") or 1),
                    stop_loss_pct=float(params.get("stop_loss_pct") or 0.05),
                    take_profit_pct=float(params.get("take_profit_pct") or 0.08),
                    confirmation_filter=str(params.get("confirmation_filter") or "none"),
                    attribution_filter=attribution_filter,
                    signals=candidate_train_signals,
                    include_trades=False,
                )
                train_evaluation_count += 1
                train_metrics = train.get("metrics") or {}
                if (
                    int(train_metrics.get("trade_count") or 0) < MIN_SIGNAL_BACKTEST_TRADE_COUNT
                    or float(train_metrics.get("win_rate") or 0) < 0.4
                    or float(train_metrics.get("average_return_pct") or 0) < -1.0
                ):
                    skipped_by_train_gate += 1
                    continue

                validation = self._signal_backtest(
                    replay,
                    horizon_days=int(params.get("horizon_days") or 5),
                    entry_delay_days=int(params.get("entry_delay_days") or 1),
                    stop_loss_pct=float(params.get("stop_loss_pct") or 0.05),
                    take_profit_pct=float(params.get("take_profit_pct") or 0.08),
                    confirmation_filter=str(params.get("confirmation_filter") or "none"),
                    attribution_filter=attribution_filter,
                    signals=candidate_validation_signals,
                    include_trades=False,
                )
                validation_evaluation_count += 1
                validation_metrics = validation.get("metrics") or {}
                if int(validation_metrics.get("trade_count") or 0) < MIN_SIGNAL_BACKTEST_TRADE_COUNT:
                    continue
                score = (
                    float(validation_metrics.get("equal_weight_cumulative_return_pct") or 0)
                    + float(validation_metrics.get("win_rate") or 0) * 10
                    + float(validation_metrics.get("expectancy_pct") or 0)
                    + min(10.0, float(train_metrics.get("equal_weight_cumulative_return_pct") or 0) / 2)
                )
                accepted.append(
                    {
                        "score": round(score, 6),
                        "parameters": validation.get("parameters") or {},
                        "train_metrics": train_metrics,
                        "validation_metrics": validation_metrics,
                        "source": "signal_loss_attribution_learning_filter",
                        "base_parameters": params,
                        "review_only": True,
                        "simulation_only": True,
                    }
                )

        accepted.sort(
            key=lambda item: (
                -float(item["validation_metrics"].get("equal_weight_cumulative_return_pct") or 0),
                -float(item["validation_metrics"].get("average_return_pct") or 0),
                -float(item["validation_metrics"].get("win_rate") or 0),
                _json_dumps(item["parameters"]),
            )
        )
        return {
            "candidates": accepted,
            "top_candidates": accepted[:5],
            "budget": {
                "candidate_pool_size": len(pool),
                "filter_count": len(filters),
                "max_grid_size": len(pool) * len(filters),
                "train_evaluation_count": train_evaluation_count,
                "validation_evaluation_count": validation_evaluation_count,
                "skipped_by_train_gate": skipped_by_train_gate,
                "skipped_by_complete_window": skipped_by_complete_window,
                "complete_window": self._complete_window_budget(window_cache) if window_cache else None,
                "accepted_candidate_count": len(accepted),
                "filters": filters,
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            },
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _selected_stable_candidate(self, walk_forward: dict[str, Any]) -> dict[str, Any] | None:
        for candidate in walk_forward.get("top_candidates") or []:
            if self._candidate_passes_stable_review(candidate):
                return candidate
        best = walk_forward.get("best")
        if isinstance(best, dict) and self._candidate_passes_stable_review(best):
            return best
        return None

    def _candidate_passes_stable_review(self, candidate: dict[str, Any] | None) -> bool:
        return bool(
            isinstance(candidate, dict)
            and candidate.get("status") == "passed_for_simulation_review"
            and self._validation_metrics_pass(candidate.get("source_validation_metrics") or {})
            and candidate.get("review_only") is not False
            and candidate.get("simulation_only") is not False
        )

    def _stable_candidate_tracks(self, candidates: list[dict[str, Any]]) -> dict[str, Any]:
        tracks = {
            BROAD_MOMENTUM_TRACK: self._empty_candidate_track(
                BROAD_MOMENTUM_TRACK,
                "No broad momentum candidate passed both validation gates.",
            ),
            DATASET1_STABILIZED_TRACK: self._empty_candidate_track(
                DATASET1_STABILIZED_TRACK,
                "No Dataset1 stabilized candidate passed both validation gates.",
            ),
        }
        for candidate in candidates:
            if not self._candidate_passes_stable_review(candidate):
                continue
            track = self._candidate_track(candidate)
            if track not in tracks or tracks[track].get("status") == "passed_for_simulation_review":
                continue
            tracks[track] = self._candidate_track_payload(track, candidate)
        return {
            "schema_version": "stable_candidate_tracks.v1",
            **tracks,
            "interpretation": [
                "broad_momentum_candidate is for opportunity discovery and simulation review priority.",
                "dataset1_stabilized_candidate is for reducing buy-too-early and late-chase risk.",
                "Neither track can write rules.yaml, bypass risk gates, or trigger orders.",
            ],
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _candidate_track(self, candidate: dict[str, Any]) -> str:
        params = candidate.get("parameters") or {}
        confirmation_filter = str(params.get("confirmation_filter") or "none")
        attribution_filter = str(params.get("attribution_filter") or "none")
        if confirmation_filter == "none" and attribution_filter == "none":
            return BROAD_MOMENTUM_TRACK
        if confirmation_filter in DATASET1_EXPERIENCE_ALIGNED_FILTERS:
            return DATASET1_STABILIZED_TRACK
        return DATASET1_STABILIZED_TRACK

    def _empty_candidate_track(self, track: str, reason: str) -> dict[str, Any]:
        return {
            "track": track,
            "status": "blocked",
            "reasons": [reason],
            "candidate": None,
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _candidate_track_payload(self, track: str, candidate: dict[str, Any]) -> dict[str, Any]:
        return {
            "track": track,
            "status": "passed_for_simulation_review",
            "reasons": [],
            "candidate": {
                "status": candidate.get("status"),
                "score": candidate.get("score"),
                "parameters": candidate.get("parameters") or {},
                "source_validation_metrics": candidate.get("source_validation_metrics") or {},
                "source_train_metrics": candidate.get("source_train_metrics") or {},
                "fold_count": candidate.get("fold_count"),
                "trade_count": candidate.get("trade_count"),
                "min_fold_trade_count": candidate.get("min_fold_trade_count"),
                "weighted_win_rate": candidate.get("weighted_win_rate"),
                "weighted_average_return_pct": candidate.get("weighted_average_return_pct"),
                "total_equal_weight_cumulative_return_pct": candidate.get("total_equal_weight_cumulative_return_pct"),
                "min_fold_win_rate": candidate.get("min_fold_win_rate"),
                "min_fold_cumulative_return_pct": candidate.get("min_fold_cumulative_return_pct"),
                "review_only": True,
                "simulation_only": True,
            },
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _signal_loss_attribution(
        self,
        replay: dict[str, Any],
        signals: list[dict[str, Any]],
        candidate: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if not candidate:
            return {
                "schema_version": "signal_loss_attribution.v1",
                "status": "skipped",
                "reason": "no_selected_stable_candidate",
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            }
        params = candidate.get("parameters") or {}
        backtest = self._signal_backtest(
            replay,
            horizon_days=int(params.get("horizon_days") or 5),
            entry_delay_days=int(params.get("entry_delay_days") or 1),
            stop_loss_pct=float(params.get("stop_loss_pct") or 0.05),
            take_profit_pct=float(params.get("take_profit_pct") or 0.08),
            confirmation_filter=str(params.get("confirmation_filter") or "none"),
            attribution_filter=str(params.get("attribution_filter") or "none"),
            signals=signals,
            include_trades=True,
            trade_limit=300,
        )
        trades = backtest.get("trades") or []
        if not trades:
            return {
                "schema_version": "signal_loss_attribution.v1",
                "status": "skipped",
                "reason": "no_closed_trades_for_selected_candidate",
                "parameters": params,
                "metrics": backtest.get("metrics") or {},
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            }

        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for trade in trades:
            symbol = str(trade.get("symbol") or "")
            board = infer_board_type(normalize_a_share_code(symbol), None) if symbol else "unknown"
            groups[f"board:{board}"].append(trade)
            groups[f"pattern:{trade.get('pattern_id') or 'unknown'}"].append(trade)
            groups[f"action:{trade.get('action_label') or 'unknown'}"].append(trade)
            groups[f"phase:{self._trade_phase_label(trade)}"].append(trade)
            groups[f"reclaim:{self._trade_reclaim_bucket(trade)}"].append(trade)
            market = self._phase_confidence_market_regime(str(trade.get("signal_date") or ""))
            groups[f"market:{market.get('regime') or 'insufficient_benchmark_data'}"].append(trade)
            for tag in trade.get("signal_tags") or []:
                groups[f"tag:{tag}"].append(trade)

        rows = [
            self._signal_attribution_group_row(key, items)
            for key, items in groups.items()
            if len(items) >= 2
        ]
        rows.sort(
            key=lambda row: (
                float(row.get("average_return_pct") or 0),
                float(row.get("win_rate") or 0),
                -int(row.get("trade_count") or 0),
                str(row.get("key") or ""),
            )
        )
        best_rows = sorted(
            rows,
            key=lambda row: (
                -float(row.get("average_return_pct") or 0),
                -float(row.get("win_rate") or 0),
                -float(row.get("cumulative_return_pct") or 0),
                str(row.get("key") or ""),
            ),
        )
        losses = [
            trade
            for trade in trades
            if float(trade.get("realized_pnl_pct") or 0) <= 0
        ]
        return {
            "schema_version": "signal_loss_attribution.v1",
            "status": "completed",
            "parameters": params,
            "metrics": backtest.get("metrics") or {},
            "trade_count": len(trades),
            "loss_trade_count": len(losses),
            "worst_groups": rows[:12],
            "best_groups": best_rows[:8],
            "loss_examples": self._trade_examples(losses),
            "recommendation": self._signal_loss_recommendation(rows, best_rows),
            "allowed_effect": "review_notes_and_next_offhour_experiment_only",
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _signal_attribution_group_row(self, key: str, trades: list[dict[str, Any]]) -> dict[str, Any]:
        summary = self._trade_return_summary(trades)
        tag_summary = self._trade_tag_summary(trades)
        return {
            "key": key,
            "trade_count": summary.get("count", 0),
            "win_rate": summary.get("win_rate", 0.0),
            "average_return_pct": summary.get("average_return_pct", 0.0),
            "cumulative_return_pct": summary.get("cumulative_return_pct", 0.0),
            "loss_count": summary.get("loss_count", 0),
            "hard_risk_trade_count": tag_summary.get("hard_risk_trade_count", 0),
            "opportunity_trade_count": tag_summary.get("opportunity_trade_count", 0),
            "review_only": True,
            "simulation_only": True,
        }

    def _trade_reclaim_bucket(self, trade: dict[str, Any]) -> str:
        close_vs_signal = float(trade.get("entry_close_vs_signal_pct") or 0)
        gap_pct = float(trade.get("entry_gap_pct") or 0)
        if close_vs_signal >= 1.0 and gap_pct > -3.0:
            return "strong_reclaim"
        if close_vs_signal >= 0.0:
            return "weak_positive_reclaim"
        return "failed_reclaim"

    def _signal_loss_recommendation(
        self,
        worst_rows: list[dict[str, Any]],
        best_rows: list[dict[str, Any]],
    ) -> dict[str, Any]:
        worst_by_key = {str(row.get("key")): row for row in worst_rows}
        best_by_key = {str(row.get("key")): row for row in best_rows}
        recommendations: list[dict[str, Any]] = []

        star = worst_by_key.get("board:star")
        if star and int(star.get("trade_count") or 0) >= 3 and float(star.get("average_return_pct") or 0) <= 0:
            recommendations.append(
                {
                    "id": "avoid_star_weak_confirmation",
                    "reason": "科创板样本在当前稳态候选中收益和胜率拖后腿。",
                    "suggested_experiment": "科创板只允许 strong_reclaim 或更高确认后进入模拟 dry-run。",
                    "allowed_effect": "next_offhour_grid_only",
                }
            )

        weak = worst_by_key.get("reclaim:weak_positive_reclaim")
        strong = best_by_key.get("reclaim:strong_reclaim")
        if weak and strong and float(strong.get("win_rate") or 0) >= 0.85:
            recommendations.append(
                {
                    "id": "promote_strong_reclaim_confidence",
                    "reason": "强确认站上信号价的样本显著优于弱确认样本。",
                    "suggested_experiment": "把 strong_reclaim 作为信心加分和小额模拟复核前置条件，而不是直接交易条件。",
                    "allowed_effect": "review_priority_only",
                }
            )

        turning = worst_by_key.get("tag:turning_point")
        if turning and int(turning.get("loss_count") or 0) >= 2:
            recommendations.append(
                {
                    "id": "tighten_turning_point_wait_confirmation",
                    "reason": "turning_point/放量小阴小阳线存在较多弱确认亏损。",
                    "suggested_experiment": "WAIT_CONFIRMATION + turning_point 需要 entry_green_above_signal 或 strong_reclaim。",
                    "allowed_effect": "next_offhour_grid_only",
                }
            )

        if not recommendations:
            recommendations.append(
                {
                    "id": "collect_more_samples_before_tightening",
                    "reason": "未找到足够稳定的亏损集中项。",
                    "suggested_experiment": "继续扩大样本，不收紧当前稳态过滤器。",
                    "allowed_effect": "observe_only",
                }
            )

        return {
            "status": "review_ready",
            "items": recommendations,
            "can_change_rules_yaml": False,
            "can_change_position_size": False,
            "can_trigger_orders": False,
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _stable_candidate_tradeoff_attribution(
        self,
        replay: dict[str, Any],
        signals: list[dict[str, Any]],
        stable_candidate_tracks: dict[str, Any],
    ) -> dict[str, Any]:
        broad = ((stable_candidate_tracks.get(BROAD_MOMENTUM_TRACK) or {}).get("candidate") or {})
        stabilized = ((stable_candidate_tracks.get(DATASET1_STABILIZED_TRACK) or {}).get("candidate") or {})
        if not broad or not stabilized:
            return {
                "schema_version": "stable_candidate_tradeoff_attribution.v1",
                "status": "skipped",
                "reason": "requires_both_broad_and_dataset1_stabilized_candidates",
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            }

        broad_params = broad.get("parameters") or {}
        stabilized_params = stabilized.get("parameters") or {}
        broad_backtest = self._signal_backtest(
            replay,
            horizon_days=int(broad_params.get("horizon_days") or 5),
            entry_delay_days=int(broad_params.get("entry_delay_days") or 1),
            stop_loss_pct=float(broad_params.get("stop_loss_pct") or 0.05),
            take_profit_pct=float(broad_params.get("take_profit_pct") or 0.08),
            confirmation_filter=str(broad_params.get("confirmation_filter") or "none"),
            signals=signals,
            include_trades=True,
            trade_limit=200,
        )
        stabilized_backtest = self._signal_backtest(
            replay,
            horizon_days=int(stabilized_params.get("horizon_days") or 5),
            entry_delay_days=int(stabilized_params.get("entry_delay_days") or 1),
            stop_loss_pct=float(stabilized_params.get("stop_loss_pct") or 0.05),
            take_profit_pct=float(stabilized_params.get("take_profit_pct") or 0.08),
            confirmation_filter=str(stabilized_params.get("confirmation_filter") or "none"),
            signals=signals,
            include_trades=True,
            trade_limit=200,
        )
        broad_trades = broad_backtest.get("trades") or []
        stabilized_trades = stabilized_backtest.get("trades") or []
        broad_by_key = {self._trade_signal_key(trade): trade for trade in broad_trades}
        stabilized_by_key = {self._trade_signal_key(trade): trade for trade in stabilized_trades}
        broad_only = [trade for key, trade in broad_by_key.items() if key not in stabilized_by_key]
        stabilized_only = [trade for key, trade in stabilized_by_key.items() if key not in broad_by_key]
        shared_keys = sorted(set(broad_by_key).intersection(stabilized_by_key))
        shared_deltas = [
            float(stabilized_by_key[key].get("realized_pnl_pct") or 0)
            - float(broad_by_key[key].get("realized_pnl_pct") or 0)
            for key in shared_keys
        ]
        filtered_summary = self._trade_return_summary(broad_only)
        stabilized_only_summary = self._trade_return_summary(stabilized_only)
        shared_delta_summary = self._return_summary(shared_deltas)
        broad_only_tag_summary = self._trade_tag_summary(broad_only)
        stabilized_only_tag_summary = self._trade_tag_summary(stabilized_only)
        broad_only_supervision = self._broad_only_supervision(broad_only)
        return {
            "schema_version": "stable_candidate_tradeoff_attribution.v1",
            "status": "completed",
            "comparison_scope": self._track_comparison_scope(broad_params, stabilized_params),
            "broad_parameters": broad_params,
            "dataset1_stabilized_parameters": stabilized_params,
            "broad_metrics": broad_backtest.get("metrics") or {},
            "dataset1_stabilized_metrics": stabilized_backtest.get("metrics") or {},
            "broad_only_trade_count": len(broad_only),
            "dataset1_only_trade_count": len(stabilized_only),
            "shared_signal_count": len(shared_keys),
            "broad_only_summary": filtered_summary,
            "dataset1_only_summary": stabilized_only_summary,
            "broad_only_tag_summary": broad_only_tag_summary,
            "dataset1_only_tag_summary": stabilized_only_tag_summary,
            "broad_only_supervision": broad_only_supervision,
            "shared_signal_return_delta_summary": shared_delta_summary,
            "verdict": self._tradeoff_verdict(filtered_summary, stabilized_only_summary, shared_delta_summary),
            "broad_only_examples": self._trade_examples(broad_only),
            "dataset1_only_examples": self._trade_examples(stabilized_only),
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _trade_signal_key(self, trade: dict[str, Any]) -> str:
        return "|".join(
            [
                str(trade.get("symbol") or ""),
                str(trade.get("signal_date") or ""),
                str(trade.get("pattern_id") or ""),
                str(trade.get("action_label") or ""),
            ]
        )

    def _track_comparison_scope(self, broad_params: dict[str, Any], stabilized_params: dict[str, Any]) -> dict[str, Any]:
        deltas = {
            key: {"broad": broad_params.get(key), "dataset1_stabilized": stabilized_params.get(key)}
            for key in sorted(set(broad_params) | set(stabilized_params))
            if broad_params.get(key) != stabilized_params.get(key)
        }
        non_filter_deltas = {key: value for key, value in deltas.items() if key != "confirmation_filter"}
        return {
            "same_except_confirmation_filter": not non_filter_deltas,
            "parameter_deltas": deltas,
            "note": (
                "Pure confirmation-filter comparison."
                if not non_filter_deltas
                else "Track comparison includes confirmation and risk/exit parameter differences."
            ),
        }

    def _trade_return_summary(self, trades: list[dict[str, Any]]) -> dict[str, Any]:
        return self._return_summary([float(trade.get("realized_pnl_pct") or 0) for trade in trades])

    def _return_summary(self, returns: list[float]) -> dict[str, Any]:
        if not returns:
            return {
                "count": 0,
                "win_count": 0,
                "loss_count": 0,
                "win_rate": 0.0,
                "average_return_pct": 0.0,
                "cumulative_return_pct": 0.0,
            }
        cumulative = 1.0
        for value in returns:
            cumulative *= 1 + value / 100
        wins = [value for value in returns if value > 0]
        losses = [value for value in returns if value < 0]
        return {
            "count": len(returns),
            "win_count": len(wins),
            "loss_count": len(losses),
            "win_rate": round(len(wins) / len(returns), 6),
            "average_return_pct": round(sum(returns) / len(returns), 6),
            "cumulative_return_pct": round((cumulative - 1) * 100, 6),
            "best_return_pct": round(max(returns), 6),
            "worst_return_pct": round(min(returns), 6),
        }

    def _tradeoff_verdict(
        self,
        broad_only_summary: dict[str, Any],
        stabilized_only_summary: dict[str, Any],
        shared_delta_summary: dict[str, Any],
    ) -> dict[str, Any]:
        broad_only_count = int(broad_only_summary.get("count") or 0)
        broad_only_average = float(broad_only_summary.get("average_return_pct") or 0)
        broad_only_cumulative = float(broad_only_summary.get("cumulative_return_pct") or 0)
        shared_average_delta = float(shared_delta_summary.get("average_return_pct") or 0)
        if broad_only_count == 0 and int(stabilized_only_summary.get("count") or 0) == 0:
            label = "tracks_equivalent_on_closed_trades"
            action = "keep_both_tracks_for_monitoring"
        elif broad_only_average < 0 or broad_only_cumulative < 0:
            label = "stabilization_filter_reduced_risk"
            action = "prefer_dataset1_stabilized_candidate_for_simulated_entry_review"
        elif broad_only_average > 0 and shared_average_delta < 0:
            label = "stabilization_filter_missed_momentum"
            action = "review_filtered_winners_before_tightening_entry_filter"
        else:
            label = "mixed_tradeoff_requires_review"
            action = "keep_broad_for_discovery_and_dataset1_for_confirmation"
        return {
            "label": label,
            "next_action": action,
            "review_only": True,
            "simulation_only": True,
        }

    def _trade_examples(self, trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
        ordered = sorted(
            trades,
            key=lambda trade: abs(float(trade.get("realized_pnl_pct") or 0)),
            reverse=True,
        )
        return [
            {
                "symbol": trade.get("symbol"),
                "pattern_id": trade.get("pattern_id"),
                "action_label": trade.get("action_label"),
                "signal_date": trade.get("signal_date"),
                "entry_date": trade.get("entry_date"),
                "exit_date": trade.get("exit_date"),
                "realized_pnl_pct": trade.get("realized_pnl_pct"),
                "exit_reason": trade.get("exit_reason"),
                "phase_label": self._trade_phase_label(trade),
                "learning_tags": self._trade_learning_tags(trade),
                "entry_gap_pct": trade.get("entry_gap_pct"),
                "entry_close_vs_signal_pct": trade.get("entry_close_vs_signal_pct"),
                "secondary_confirmation": self._enhanced_watch_confirmation(trade),
                "near_reclaim_watch": self._near_reclaim_watch_confirmation(trade),
                "review_only": True,
                "simulation_only": True,
            }
            for trade in ordered[:10]
        ]

    def _trade_tag_summary(self, trades: list[dict[str, Any]]) -> dict[str, Any]:
        phase_counts: Counter[str] = Counter()
        learning_counts: Counter[str] = Counter()
        risk_count = 0
        hard_risk_count = 0
        opportunity_count = 0
        mixed_count = 0
        for trade in trades:
            phase_counts[self._trade_phase_label(trade)] += 1
            tags = self._trade_learning_tags(trade)
            learning_counts.update(tags)
            has_risk = any(tag.endswith("_risk") or tag in {"stop_loss_triggered", "filtered_loss_sample"} for tag in tags)
            has_hard_risk = self._trade_has_hard_risk(tags)
            has_opportunity = self._trade_has_opportunity(tags)
            if has_risk:
                risk_count += 1
            if has_hard_risk:
                hard_risk_count += 1
            if has_opportunity:
                opportunity_count += 1
            if has_risk and has_opportunity:
                mixed_count += 1
        return {
            "trade_count": len(trades),
            "phase_counts": dict(phase_counts),
            "learning_tag_counts": dict(learning_counts),
            "risk_trade_count": risk_count,
            "hard_risk_trade_count": hard_risk_count,
            "opportunity_trade_count": opportunity_count,
            "mixed_opportunity_risk_count": mixed_count,
            "review_only": True,
            "simulation_only": True,
        }

    def _broad_only_supervision(self, trades: list[dict[str, Any]]) -> dict[str, Any]:
        opportunity_trades: list[dict[str, Any]] = []
        confirmed_watch_trades: list[dict[str, Any]] = []
        rejected_watch_trades: list[dict[str, Any]] = []
        near_reclaim_trades: list[dict[str, Any]] = []
        hard_risk_trades: list[dict[str, Any]] = []
        mixed_trades: list[dict[str, Any]] = []
        for trade in trades:
            tags = self._trade_learning_tags(trade)
            has_opportunity = self._trade_has_opportunity(tags)
            has_hard_risk = self._trade_has_hard_risk(tags)
            if has_opportunity and not has_hard_risk:
                opportunity_trades.append(trade)
                confirmation = self._enhanced_watch_confirmation(trade)
                if confirmation["passed"]:
                    confirmed_watch_trades.append(trade)
                else:
                    rejected_watch_trades.append(trade)
                    if self._near_reclaim_watch_confirmation(trade)["passed"]:
                        near_reclaim_trades.append(trade)
            if has_hard_risk:
                hard_risk_trades.append(trade)
            if has_opportunity and has_hard_risk:
                mixed_trades.append(trade)

        opportunity_summary = self._trade_return_summary(confirmed_watch_trades)
        hard_risk_summary = self._trade_return_summary(hard_risk_trades)
        return {
            "schema_version": "broad_only_supervision.v1",
            "status": "completed" if trades else "skipped",
            "enhanced_watch_track": {
                "track": "broad_only_enhanced_watch",
                "status": "candidate" if len(confirmed_watch_trades) >= 3 else "needs_secondary_confirmation",
                "raw_opportunity_count": len(opportunity_trades),
                "sample_count": len(confirmed_watch_trades),
                "secondary_confirmation_rejected_count": len(rejected_watch_trades),
                "summary": opportunity_summary,
                "examples": self._trade_examples(confirmed_watch_trades),
                "rejected_examples": self._trade_examples(rejected_watch_trades),
                "confirmation_summary": self._enhanced_watch_confirmation_summary(opportunity_trades),
                "suggested_review_position_ratio": 0.02,
                "requires_confirmation": [
                    "reclaimed_signal_price",
                    "no_weak_open",
                    "no_hard_risk_tags",
                    "no_failed_markup_phase",
                    "portfolio_risk_gates_passed",
                    "dry_run_screen_before_any_simulated_click",
                ],
                "allowed_effect": "raise_review_priority_and_dry_run_only",
                "review_only": True,
                "simulation_only": True,
            },
            "near_reclaim_watch_track": {
                "track": "broad_only_near_reclaim_watch",
                "status": "watch_for_reclaim" if near_reclaim_trades else "no_near_reclaim_samples",
                "sample_count": len(near_reclaim_trades),
                "summary": self._trade_return_summary(near_reclaim_trades),
                "examples": self._trade_examples(near_reclaim_trades),
                "requires_next_confirmation": [
                    "future_close_or_intraday_price_reclaims_signal_price",
                    "no_new_hard_risk_tags",
                    "portfolio_risk_gates_passed",
                ],
                "allowed_effect": "watch_for_reclaim_only_not_dry_run",
                "review_only": True,
                "simulation_only": True,
            },
            "failed_markup_block": {
                "track": "broad_only_failed_markup_block",
                "status": "active" if hard_risk_trades else "no_hard_risk_samples",
                "sample_count": len(hard_risk_trades),
                "summary": hard_risk_summary,
                "examples": self._trade_examples(hard_risk_trades),
                "blocking_tags": [
                    "broad_only_risk",
                    "filtered_loss_sample",
                    "stop_loss_triggered",
                    "distribution_or_failed_markup",
                    "high_volatility_board_risk",
                ],
                "allowed_effect": "downgrade_to_observe_or_dry_run_only",
                "review_only": True,
                "simulation_only": True,
            },
            "mixed_opportunity_risk_review": {
                "sample_count": len(mixed_trades),
                "examples": self._trade_examples(mixed_trades),
                "next_action": "manual_phase_review_before_relaxing_dataset1_filter",
                "review_only": True,
                "simulation_only": True,
            },
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _enhanced_watch_confirmation_summary(self, trades: list[dict[str, Any]]) -> dict[str, Any]:
        condition_counts: Counter[str] = Counter()
        failed_reasons: Counter[str] = Counter()
        passed = 0
        for trade in trades:
            confirmation = self._enhanced_watch_confirmation(trade)
            if confirmation["passed"]:
                passed += 1
            for key, value in (confirmation.get("conditions") or {}).items():
                if value:
                    condition_counts[key] += 1
            failed_reasons.update(confirmation.get("failed_reasons") or [])
        return {
            "candidate_count": len(trades),
            "passed_count": passed,
            "failed_count": len(trades) - passed,
            "condition_pass_counts": dict(condition_counts),
            "failed_reason_counts": dict(failed_reasons),
            "review_only": True,
            "simulation_only": True,
        }

    def _near_reclaim_watch_confirmation(self, trade: dict[str, Any]) -> dict[str, Any]:
        signal_close = float(trade.get("signal_close") or 0)
        entry_open = float(trade.get("entry_open") or 0)
        entry_close = float(trade.get("entry_close") or 0)
        learning_tags = self._trade_learning_tags(trade)
        phase_label = self._trade_phase_label(trade)
        has_prices = signal_close > 0 and entry_open > 0 and entry_close > 0
        near_signal_price = has_prices and entry_close >= signal_close * 0.985
        no_deep_gap_down = has_prices and entry_open >= signal_close * 0.98
        no_hard_risk_tags = not self._trade_has_hard_risk(learning_tags)
        no_failed_markup_phase = phase_label != "distribution_or_failed_markup"
        conditions = {
            "has_entry_signal_prices": has_prices,
            "near_signal_price": near_signal_price,
            "no_deep_gap_down": no_deep_gap_down,
            "no_hard_risk_tags": no_hard_risk_tags,
            "no_failed_markup_phase": no_failed_markup_phase,
        }
        failed_reasons = [key for key, value in conditions.items() if not value]
        return {
            "passed": not failed_reasons,
            "conditions": conditions,
            "failed_reasons": failed_reasons,
            "review_only": True,
            "simulation_only": True,
        }

    def _enhanced_watch_confirmation(self, trade: dict[str, Any]) -> dict[str, Any]:
        signal_close = float(trade.get("signal_close") or 0)
        entry_open = float(trade.get("entry_open") or 0)
        entry_close = float(trade.get("entry_close") or 0)
        learning_tags = self._trade_learning_tags(trade)
        phase_label = self._trade_phase_label(trade)
        has_prices = signal_close > 0 and entry_open > 0 and entry_close > 0
        reclaimed_signal_price = has_prices and entry_close >= signal_close
        no_weak_open = has_prices and entry_open >= signal_close * 0.985 and entry_close >= entry_open * 0.995
        no_hard_risk_tags = not self._trade_has_hard_risk(learning_tags)
        no_failed_markup_phase = phase_label != "distribution_or_failed_markup"
        conditions = {
            "has_entry_signal_prices": has_prices,
            "reclaimed_signal_price": reclaimed_signal_price,
            "no_weak_open": no_weak_open,
            "no_hard_risk_tags": no_hard_risk_tags,
            "no_failed_markup_phase": no_failed_markup_phase,
        }
        failed_reasons = [key for key, value in conditions.items() if not value]
        return {
            "passed": not failed_reasons,
            "conditions": conditions,
            "failed_reasons": failed_reasons,
            "review_only": True,
            "simulation_only": True,
        }

    def _trade_has_opportunity(self, learning_tags: list[str]) -> bool:
        return any(
            tag.endswith("_opportunity") or tag in {"missed_large_winner", "follow_through_winner"}
            for tag in learning_tags
        )

    def _trade_has_hard_risk(self, learning_tags: list[str]) -> bool:
        return any(tag in {"broad_only_risk", "stop_loss_triggered", "filtered_loss_sample"} for tag in learning_tags)

    def _trade_learning_tags(self, trade: dict[str, Any]) -> list[str]:
        pnl = float(trade.get("realized_pnl_pct") or 0)
        exit_reason = str(trade.get("exit_reason") or "")
        symbol = str(trade.get("symbol") or "")
        action_label = str(trade.get("action_label") or "")
        signal_tags = set(str(tag) for tag in (trade.get("signal_tags") or []))
        matched_tags = set(str(tag) for tag in (trade.get("matched_tags") or []))
        tags = signal_tags | matched_tags
        learning: set[str] = set()

        if pnl >= 8:
            learning.update({"missed_large_winner", "broad_only_opportunity"})
        elif pnl >= 3:
            learning.update({"follow_through_winner", "broad_only_opportunity"})
        elif pnl <= -4:
            learning.update({"filtered_loss_sample", "broad_only_risk"})
        if exit_reason == "signal_stop_loss":
            learning.add("stop_loss_triggered")
        if action_label == "WAIT_CONFIRMATION" and pnl < 0:
            learning.add("weak_confirmation_risk")
        if symbol.startswith(("SH688", "SZ300", "SZ301")):
            learning.add("high_volatility_board_risk")
        if tags & {"top_risk", "distribution", "big_fall", "volume_up_price_stall", "reduce"}:
            learning.add("distribution_or_stall_risk")
        if tags & {"limit_up", "bullish_attack", "price_volume_rise", "high_amount"}:
            learning.add("strong_momentum_opportunity")
        if tags & {"sideways", "turning_point", "small_body"}:
            learning.add("stabilization_probe")
        if tags & {"down_phase", "big_yin"}:
            learning.add("weak_phase_risk")

        if not learning:
            learning.add("needs_manual_phase_review")
        return sorted(learning)

    def _trade_phase_label(self, trade: dict[str, Any]) -> str:
        pnl = float(trade.get("realized_pnl_pct") or 0)
        exit_reason = str(trade.get("exit_reason") or "")
        tags = set(str(tag) for tag in (trade.get("signal_tags") or []))
        tags |= set(str(tag) for tag in (trade.get("matched_tags") or []))
        if exit_reason == "signal_stop_loss" or pnl <= -4:
            if tags & {"top_risk", "distribution", "big_fall", "volume_up_price_stall", "reduce"}:
                return "distribution_or_failed_markup"
            return "failed_broad_momentum"
        if pnl >= 8 and tags & {"limit_up", "bullish_attack", "price_volume_rise", "high_amount"}:
            return "missed_main_rise_or_markup"
        if pnl >= 3:
            return "missed_follow_through"
        if tags & {"sideways", "turning_point", "small_body"}:
            return "stabilization_probe"
        if tags & {"top_risk", "distribution", "volume_up_price_stall"}:
            return "distribution_watch"
        return "manual_phase_review"

    def _validation_metrics_pass(self, metrics: dict[str, Any]) -> bool:
        return bool(
            float(metrics.get("win_rate") or 0) >= MIN_OPTIMIZED_VALIDATION_WIN_RATE
            and float(metrics.get("equal_weight_cumulative_return_pct") or 0)
            >= MIN_OPTIMIZED_VALIDATION_CUMULATIVE_RETURN_PCT
            and float(metrics.get("average_return_pct") or 0) > 0
            and int(metrics.get("trade_count") or 0) >= MIN_SIGNAL_BACKTEST_TRADE_COUNT
        )

    def _walk_forward_candidate_pool(
        self,
        candidates: list[dict[str, Any]],
        experience_aligned_candidates: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        by_validation_win_rate = sorted(
            candidates,
            key=lambda item: (
                -float(item["validation_metrics"].get("win_rate") or 0),
                -float(item["validation_metrics"].get("equal_weight_cumulative_return_pct") or 0),
                _json_dumps(item["parameters"]),
            ),
        )
        by_validation_trade_count = sorted(
            candidates,
            key=lambda item: (
                -int(item["validation_metrics"].get("trade_count") or 0),
                -float(item["validation_metrics"].get("average_return_pct") or 0),
                _json_dumps(item["parameters"]),
            ),
        )
        pool = (
            candidates[:10]
            + by_validation_win_rate[:8]
            + by_validation_trade_count[:8]
            + experience_aligned_candidates[:8]
        )
        unique: list[dict[str, Any]] = []
        seen: set[str] = set()
        for candidate in pool:
            key = _json_dumps(candidate.get("parameters") or {})
            if key in seen:
                continue
            seen.add(key)
            unique.append(candidate)
        return unique

    def _next_ready_bar(self, symbol: str, after_date: str, offset: int = 0) -> dict[str, Any] | None:
        cache = getattr(self, "_signal_backtest_cache", None)
        cache_key = ("next_ready_bar", symbol, after_date, int(offset))
        if cache is not None and cache_key in cache:
            cached = cache[cache_key]
            return dict(cached) if cached else None
        series = self._ready_bars_for_symbol(symbol)
        if series is not None:
            matches = [
                row
                for row in series
                if str(row.get("trade_date") or "") > after_date
            ]
            result = dict(matches[int(offset)]) if len(matches) > int(offset) else None
            if cache is not None:
                cache[cache_key] = result
            return dict(result) if result else None
        row = self.store.fetch_one(
            """
            SELECT symbol, trade_date, open, high, low, close, volume, amount
            FROM daily_bar_cache
            WHERE symbol = ?
              AND quality_status = 'ready'
              AND trade_date > ?
              AND trade_date != 'ERROR'
            ORDER BY trade_date ASC
            LIMIT 1 OFFSET ?
            """,
            (symbol, after_date, max(0, int(offset))),
        )
        result = dict(row) if row else None
        if cache is not None:
            cache[cache_key] = result
        return dict(result) if result else None

    def _signal_exit_plan(
        self,
        symbol: str,
        entry_date: str,
        entry_price: float,
        horizon_days: int,
        stop_loss_pct: float = 0.05,
        take_profit_pct: float = 0.08,
    ) -> dict[str, Any] | None:
        cache = getattr(self, "_signal_backtest_cache", None)
        cache_key = (
            "signal_exit_plan",
            symbol,
            entry_date,
            round(float(entry_price), 4),
            int(horizon_days),
            round(float(stop_loss_pct), 4),
            round(float(take_profit_pct), 4),
        )
        if cache is not None and cache_key in cache:
            cached = cache[cache_key]
            return dict(cached) if cached else None
        series = self._ready_bars_for_symbol(symbol)
        if series is not None:
            rows = [
                dict(row)
                for row in series
                if str(row.get("trade_date") or "") > entry_date
            ][: max(1, int(horizon_days))]
        else:
            rows = self.store.fetch_all(
                """
                SELECT symbol, trade_date, open, high, low, close, volume, amount
                FROM daily_bar_cache
                WHERE symbol = ?
                  AND quality_status = 'ready'
                  AND trade_date > ?
                  AND trade_date != 'ERROR'
                ORDER BY trade_date ASC
                LIMIT ?
                """,
                (symbol, entry_date, max(1, int(horizon_days))),
            )
        if not rows:
            return None
        stop_price = entry_price * (1 - float(stop_loss_pct))
        target_price = entry_price * (1 + float(take_profit_pct))
        selected = dict(rows[-1])
        exit_price = float(selected["close"])
        exit_reason = "horizon_exit"
        for row in rows:
            item = dict(row)
            if float(item["low"]) <= stop_price:
                selected = item
                exit_price = min(float(item["open"]), stop_price)
                exit_reason = "signal_stop_loss"
                break
            if float(item["high"]) >= target_price:
                selected = item
                exit_price = max(float(item["open"]), target_price)
                exit_reason = "signal_take_profit"
                break
        result = {
            "bar": selected,
            "exit_date": selected["trade_date"],
            "exit_price": exit_price,
            "exit_reason": exit_reason,
        }
        if cache is not None:
            cache[cache_key] = result
        return dict(result)

    def _execution_bar(self, bar: dict[str, Any]) -> dict[str, Any]:
        item = dict(bar)
        amount = float(item.get("amount") or 0)
        if amount <= 0:
            volume = float(item.get("volume") or 0)
            price = float(item.get("close") or item.get("open") or 0)
            if volume > 0 and price > 0:
                item["amount"] = round(volume * price, 4)
                item["amount_estimated"] = True
        return item

    def _confirmation_filter_passes(
        self,
        signal: dict[str, Any],
        entry_bar: dict[str, Any],
        previous_close: float,
        filter_id: str,
    ) -> bool:
        if filter_id in {"", "none", None}:
            return True
        signal_close = float(signal.get("close") or 0)
        entry_open = float(entry_bar.get("open") or 0)
        entry_close = float(entry_bar.get("close") or 0)
        entry_low = float(entry_bar.get("low") or 0)
        if signal_close <= 0 or entry_open <= 0 or entry_close <= 0:
            return False
        close_vs_signal = (entry_close - signal_close) / signal_close * 100
        intraday_pct = (entry_close - entry_open) / entry_open * 100
        gap_pct = (entry_open - previous_close) / previous_close * 100 if previous_close else 0.0

        if filter_id == "entry_close_above_signal":
            return close_vs_signal >= 0
        if filter_id == "entry_green_above_signal":
            return close_vs_signal >= 0 and intraday_pct >= 0
        if filter_id == "strong_reclaim":
            return close_vs_signal >= 1.0 and intraday_pct >= 0 and gap_pct > -3.0
        stabilized = close_vs_signal >= 0.5 and entry_low >= signal_close * 0.97 and intraday_pct >= -0.5
        if filter_id == "dataset1_stabilized_reclaim":
            return stabilized
        if filter_id == "dataset1_low_risk_stabilized_reclaim":
            return stabilized and not self._has_dataset1_distribution_risk(signal)
        if filter_id == "dataset1_accumulation_reclaim":
            tags = set(signal.get("tags") or [])
            accumulation_like = bool(
                "sideways" in tags
                or "turning_point" in tags
                or ("small_body" in tags and ("low_volume" in tags or "high_volume" in tags))
            )
            return stabilized and accumulation_like and not self._has_dataset1_distribution_risk(signal)
        return True

    def _signal_attribution_filter_passes(
        self,
        signal: dict[str, Any],
        entry_bar: dict[str, Any],
        previous_close: float,
        filter_id: str,
    ) -> bool:
        if filter_id in {"", "none", None}:
            return True
        symbol = str(signal.get("symbol") or "")
        board = infer_board_type(normalize_a_share_code(symbol), None) if symbol else "unknown"
        tags = {str(tag) for tag in (signal.get("tags") or [])}
        tags |= {str(tag) for tag in (signal.get("matched_tags") or [])}
        action_label = str(signal.get("action_label") or "")
        strong_reclaim = self._confirmation_filter_passes(signal, entry_bar, previous_close, "strong_reclaim")
        green_or_strong = strong_reclaim or self._confirmation_filter_passes(
            signal,
            entry_bar,
            previous_close,
            "entry_green_above_signal",
        )

        if filter_id == "star_requires_strong_reclaim":
            return board != "star" or strong_reclaim
        if filter_id == "turning_point_requires_green_or_strong":
            return not (action_label == "WAIT_CONFIRMATION" and "turning_point" in tags) or green_or_strong
        if filter_id == "star_and_turning_point_quality_gate":
            return (board != "star" or strong_reclaim) and (
                not (action_label == "WAIT_CONFIRMATION" and "turning_point" in tags) or green_or_strong
            )
        if filter_id == "block_dataset1_distribution_risk":
            return not self._has_dataset1_distribution_risk(signal)
        return True

    def _has_dataset1_distribution_risk(self, signal: dict[str, Any]) -> bool:
        tags = set(signal.get("tags") or [])
        return bool(
            tags
            & {
                "top_risk",
                "distribution",
                "big_fall",
                "volume_up_price_stall",
            }
        )

    def _signal_walk_forward_validation(
        self,
        replay: dict[str, Any],
        signals: list[dict[str, Any]],
        candidates: list[dict[str, Any]],
    ) -> dict[str, Any]:
        unique_candidates: list[dict[str, Any]] = []
        seen: set[str] = set()
        for candidate in candidates:
            params = candidate.get("parameters") or {}
            key = _json_dumps(params)
            if not params or key in seen:
                continue
            seen.add(key)
            unique_candidates.append(candidate)
            if len(unique_candidates) >= 24:
                break

        if not unique_candidates:
            return {
                "status": "skipped",
                "reason": "too_few_candidates_for_walk_forward",
                "fold_count": 0,
                "candidate_count": len(unique_candidates),
                "gate": {
                    "status": "blocked",
                    "reasons": ["too_few_candidates_for_walk_forward"],
                    "requires_human_review": True,
                    "writes_rules_yaml": False,
                    "auto_apply": False,
                    "simulation_only": True,
                    "live_trading_enabled": settings.enable_live_trading,
                },
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            }

        evaluations: list[dict[str, Any]] = []
        max_fold_count = 0
        window_cache: dict[tuple[int, int], dict[str, Any]] = {}
        for candidate in unique_candidates:
            params = candidate.get("parameters") or {}
            entry_delay = int(params.get("entry_delay_days") or 1)
            horizon = int(params.get("horizon_days") or 5)
            window_key = (entry_delay, horizon)
            if window_key not in window_cache:
                window_cache[window_key] = self._signals_with_complete_backtest_window(
                    signals,
                    entry_delay_days=entry_delay,
                    horizon_days=horizon,
                )
            window_summary = window_cache[window_key]["summary"]
            folds = self._walk_forward_signal_folds(window_cache[window_key]["signals"])
            max_fold_count = max(max_fold_count, len(folds))
            if len(folds) < MIN_WALK_FORWARD_FOLD_COUNT:
                evaluations.append(
                    {
                        "status": "blocked",
                        "score": 0.0,
                        "parameters": params,
                        "fold_count": len(folds),
                        "trade_count": 0,
                        "min_fold_trade_count": 0,
                        "weighted_win_rate": 0.0,
                        "weighted_average_return_pct": 0.0,
                        "total_equal_weight_cumulative_return_pct": 0.0,
                        "min_fold_win_rate": 0.0,
                        "min_fold_cumulative_return_pct": 0.0,
                        "source_train_metrics": candidate.get("train_metrics") or {},
                        "source_validation_metrics": candidate.get("validation_metrics") or {},
                        "gate_reasons": ["too_few_complete_window_folds_for_walk_forward"],
                        "complete_window": window_summary,
                        "folds": [],
                        "review_only": True,
                        "simulation_only": True,
                    }
                )
                continue
            fold_results: list[dict[str, Any]] = []
            total_trades = 0
            weighted_win_sum = 0.0
            weighted_return_sum = 0.0
            cumulative_factor = 1.0
            min_fold_return = None
            min_fold_win_rate = None
            min_fold_trade_count = None
            for idx, fold_signals in enumerate(folds, start=1):
                result = self._signal_backtest(
                    replay,
                    horizon_days=int(params.get("horizon_days") or 5),
                    entry_delay_days=int(params.get("entry_delay_days") or 1),
                    stop_loss_pct=float(params.get("stop_loss_pct") or 0.05),
                    take_profit_pct=float(params.get("take_profit_pct") or 0.08),
                    confirmation_filter=str(params.get("confirmation_filter") or "none"),
                    attribution_filter=str(params.get("attribution_filter") or "none"),
                    signals=fold_signals,
                    include_trades=False,
                )
                metrics = result.get("metrics") or {}
                trade_count = int(metrics.get("trade_count") or 0)
                win_rate = float(metrics.get("win_rate") or 0)
                average_return = float(metrics.get("average_return_pct") or 0)
                cumulative_return = float(metrics.get("equal_weight_cumulative_return_pct") or 0)
                total_trades += trade_count
                weighted_win_sum += win_rate * trade_count
                weighted_return_sum += average_return * trade_count
                cumulative_factor *= 1 + cumulative_return / 100
                min_fold_return = cumulative_return if min_fold_return is None else min(min_fold_return, cumulative_return)
                min_fold_win_rate = win_rate if min_fold_win_rate is None else min(min_fold_win_rate, win_rate)
                min_fold_trade_count = trade_count if min_fold_trade_count is None else min(min_fold_trade_count, trade_count)
                fold_results.append(
                    {
                        "fold_index": idx,
                        "start_signal_date": fold_signals[0].get("signal_date") if fold_signals else None,
                        "end_signal_date": fold_signals[-1].get("signal_date") if fold_signals else None,
                        "signal_count": len(fold_signals),
                        "trade_count": trade_count,
                        "win_rate": round(win_rate, 6),
                        "average_return_pct": round(average_return, 6),
                        "equal_weight_cumulative_return_pct": round(cumulative_return, 6),
                        "skipped_by_confirmation_filter": int(metrics.get("skipped_by_confirmation_filter") or 0),
                        "skipped_by_attribution_filter": int(metrics.get("skipped_by_attribution_filter") or 0),
                        "status": result.get("status"),
                    }
                )

            weighted_win_rate = weighted_win_sum / total_trades if total_trades else 0.0
            weighted_average_return = weighted_return_sum / total_trades if total_trades else 0.0
            total_cumulative_return = (cumulative_factor - 1) * 100
            gate_reasons: list[str] = []
            if total_trades < MIN_WALK_FORWARD_TRADE_COUNT:
                gate_reasons.append("walk_forward_trade_count_too_low")
            if (min_fold_trade_count or 0) < MIN_WALK_FORWARD_FOLD_TRADE_COUNT:
                gate_reasons.append("walk_forward_fold_trade_count_too_low")
            if weighted_win_rate < MIN_WALK_FORWARD_WIN_RATE:
                gate_reasons.append("walk_forward_win_rate_too_low")
            if (min_fold_win_rate or 0.0) < MIN_WALK_FORWARD_MIN_FOLD_WIN_RATE:
                gate_reasons.append("walk_forward_min_fold_win_rate_too_low")
            if total_cumulative_return < MIN_WALK_FORWARD_CUMULATIVE_RETURN_PCT:
                gate_reasons.append("walk_forward_cumulative_return_below_20_pct")
            if min_fold_return is not None and min_fold_return < MAX_WALK_FORWARD_FOLD_DRAWDOWN_PCT:
                gate_reasons.append("walk_forward_fold_loss_too_large")
            if weighted_average_return <= 0:
                gate_reasons.append("walk_forward_average_return_not_positive")

            evaluations.append(
                {
                    "status": "passed_for_simulation_review" if not gate_reasons else "blocked",
                    "score": round(total_cumulative_return + weighted_win_rate * 10 + weighted_average_return, 6),
                    "parameters": params,
                    "fold_count": len(folds),
                    "trade_count": total_trades,
                    "min_fold_trade_count": int(min_fold_trade_count or 0),
                    "weighted_win_rate": round(weighted_win_rate, 6),
                    "weighted_average_return_pct": round(weighted_average_return, 6),
                    "total_equal_weight_cumulative_return_pct": round(total_cumulative_return, 6),
                    "min_fold_win_rate": round(min_fold_win_rate or 0.0, 6),
                    "min_fold_cumulative_return_pct": round(min_fold_return or 0.0, 6),
                    "source_train_metrics": candidate.get("train_metrics") or {},
                    "source_validation_metrics": candidate.get("validation_metrics") or {},
                    "gate_reasons": gate_reasons,
                    "complete_window": window_summary,
                    "folds": fold_results,
                    "review_only": True,
                    "simulation_only": True,
                }
            )

        evaluations.sort(
            key=lambda item: (
                item["status"] != "passed_for_simulation_review",
                -float(item["total_equal_weight_cumulative_return_pct"]),
                -float(item["weighted_win_rate"]),
                _json_dumps(item["parameters"]),
            )
        )
        best = evaluations[0] if evaluations else None
        passed = bool(best and best["status"] == "passed_for_simulation_review")
        return {
            "status": "passed_for_simulation_review" if passed else "blocked",
            "fold_count": int((best or {}).get("fold_count") or max_fold_count),
            "candidate_count": len(unique_candidates),
            "best": best,
            "top_candidates": evaluations[:5],
            "stable_candidate_tracks": self._stable_candidate_tracks(evaluations),
            "complete_window": self._complete_window_budget(window_cache),
            "gate": {
                "status": "passed_for_simulation_review" if passed else "blocked",
                "reasons": [] if passed else ((best or {}).get("gate_reasons") or ["walk_forward_validation_not_passed"]),
                "min_fold_count": MIN_WALK_FORWARD_FOLD_COUNT,
                "min_trade_count": MIN_WALK_FORWARD_TRADE_COUNT,
                "min_fold_trade_count": MIN_WALK_FORWARD_FOLD_TRADE_COUNT,
                "min_weighted_win_rate": MIN_WALK_FORWARD_WIN_RATE,
                "min_fold_win_rate": MIN_WALK_FORWARD_MIN_FOLD_WIN_RATE,
                "min_cumulative_return_pct": MIN_WALK_FORWARD_CUMULATIVE_RETURN_PCT,
                "max_fold_loss_pct": MAX_WALK_FORWARD_FOLD_DRAWDOWN_PCT,
                "requires_human_review": True,
                "writes_rules_yaml": False,
                "auto_apply": False,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            },
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _walk_forward_signal_folds(self, signals: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
        ordered = sorted(signals, key=lambda item: (item["signal_date"], item["symbol"]))
        if len(ordered) < MIN_WALK_FORWARD_TRADE_COUNT:
            return []
        fold_count = min(4, max(MIN_WALK_FORWARD_FOLD_COUNT, len(ordered) // max(1, MIN_WALK_FORWARD_TRADE_COUNT)))
        fold_count = min(fold_count, len(ordered) // MIN_SIGNAL_BACKTEST_TRADE_COUNT)
        if fold_count < MIN_WALK_FORWARD_FOLD_COUNT:
            return []
        fold_size = max(MIN_SIGNAL_BACKTEST_TRADE_COUNT, len(ordered) // (fold_count + 1))
        start = max(0, len(ordered) - fold_count * fold_size)
        folds: list[list[dict[str, Any]]] = []
        for fold_index in range(fold_count):
            left = start + fold_index * fold_size
            right = left + fold_size
            fold = ordered[left:right]
            if len(fold) >= MIN_SIGNAL_BACKTEST_TRADE_COUNT:
                folds.append(fold)
        return folds

    def _previous_close(self, symbol: str, trade_date: str, fallback: float) -> float:
        cache = getattr(self, "_signal_backtest_cache", None)
        cache_key = ("previous_close", symbol, trade_date)
        if cache is not None and cache_key in cache:
            cached = cache[cache_key]
            return float(cached) if cached is not None else float(fallback)
        series = self._ready_bars_for_symbol(symbol)
        if series is not None:
            previous = [
                row
                for row in series
                if str(row.get("trade_date") or "") < trade_date
            ]
            result = float(previous[-1]["close"]) if previous and previous[-1].get("close") is not None else float(fallback)
            if cache is not None:
                cache[cache_key] = result
            return result
        row = self.store.fetch_one(
            """
            SELECT close
            FROM daily_bar_cache
            WHERE symbol = ?
              AND quality_status = 'ready'
              AND trade_date < ?
              AND trade_date != 'ERROR'
            ORDER BY trade_date DESC
            LIMIT 1
            """,
            (symbol, trade_date),
        )
        result = float(row["close"]) if row and row.get("close") is not None else float(fallback)
        if cache is not None:
            cache[cache_key] = result
        return result

    def _limit_pct(self, symbol: str) -> float:
        return limit_up_threshold(infer_board_type(normalize_a_share_code(symbol), ""))

    def _signal_backtest_metrics(
        self,
        trades: list[dict[str, Any]],
        rejected_entries: int,
        rejected_exits: int,
    ) -> dict[str, Any]:
        returns = [float(trade["realized_pnl_pct"]) for trade in trades]
        wins = [value for value in returns if value > 0]
        losses = [value for value in returns if value < 0]
        compounded = 1.0
        for value in returns:
            compounded *= 1 + value / 100
        average_win = sum(wins) / len(wins) if wins else 0.0
        average_loss = sum(losses) / len(losses) if losses else 0.0
        win_rate = len(wins) / len(returns) if returns else 0.0
        profit_loss_ratio = average_win / abs(average_loss) if average_loss else (average_win if average_win else 0.0)
        expectancy = win_rate * average_win + (1 - win_rate) * average_loss if returns else 0.0
        return {
            "trade_count": len(trades),
            "closed_trade_count": len(trades),
            "win_rate": round(win_rate, 6),
            "average_return_pct": round(sum(returns) / len(returns), 6) if returns else 0.0,
            "equal_weight_cumulative_return_pct": round((compounded - 1) * 100, 6) if returns else 0.0,
            "average_win_pct": round(average_win, 6),
            "average_loss_pct": round(average_loss, 6),
            "profit_loss_ratio": round(profit_loss_ratio, 6),
            "expectancy_pct": round(expectancy, 6),
            "rejected_entries": rejected_entries,
            "rejected_exits": rejected_exits,
        }

    def _signal_pattern_performance(self, trades: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        by_pattern: dict[str, dict[str, Any]] = {}
        for trade in trades:
            pattern_id = str(trade.get("pattern_id") or "")
            slot = by_pattern.setdefault(
                pattern_id,
                {"trade_count": 0, "wins": 0, "avg_return_pct": 0.0},
            )
            slot["trade_count"] += 1
            ret = float(trade.get("realized_pnl_pct") or 0)
            slot["wins"] += 1 if ret > 0 else 0
            slot["avg_return_pct"] += ret
        for slot in by_pattern.values():
            count = int(slot["trade_count"])
            slot["win_rate"] = round(slot["wins"] / count, 6) if count else 0.0
            slot["avg_return_pct"] = round(slot["avg_return_pct"] / count, 6) if count else 0.0
        return by_pattern

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

    def _focus_phase_diagnostics(self) -> dict[str, Any]:
        """Summarize key human-provided phase samples without fetching new data."""
        replay_service = MainForcePhaseReplayService()
        items: list[dict[str, Any]] = []
        counts: Counter[str] = Counter()
        for target in FOCUS_PHASE_TARGETS:
            item = self._focus_phase_item(replay_service, target)
            items.append(item)
            counts[str(item.get("status") or "unknown")] += 1
        if any(item.get("status") == "ready" for item in items):
            status = "completed"
        elif any(item.get("status") == "stale_replay" for item in items):
            status = "stale_replay"
        else:
            status = "needs_history"

        return {
            "schema_version": "focus_phase_diagnostics.v1",
            "status": status,
            "targets": items,
            "counts": dict(counts),
            "supervision": {
                "summary": "Use focus samples to separate accumulation, test-pull, markup, distribution, and post-distribution evidence before changing simulation priority.",
                "next_actions": [
                    "Treat Gold Mantis as a completed markup/distribution training sample unless a fresh low-risk reclaim appears.",
                    "Use Sanwei Communication to learn the successful pre-markup path and sell-into-strength discipline.",
                    "Use Lucky Film as an execution-discipline focus sample; do not average down or chase before stabilization evidence.",
                    "Refresh stale focus replays before using them as trading-time evidence.",
                ],
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            },
            "policy": {
                "uses_latest_stored_phase_replay_only": True,
                "fetches_external_history": False,
                "writes_rules_yaml": False,
                "broker_or_order_action": False,
            },
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _focus_phase_item(
        self,
        replay_service: MainForcePhaseReplayService,
        target: dict[str, Any],
    ) -> dict[str, Any]:
        symbol = str(target["symbol"])
        replays = replay_service.latest_replays(symbol=symbol, limit=1)
        cache = self._daily_bar_cache_summary(symbol)
        if not replays:
            return {
                "symbol": symbol,
                "name": target["name"],
                "role": target["role"],
                "status": "needs_history_refresh",
                "reason": "no_stored_phase_replay",
                "dataset1_anchor": target["dataset1_anchor"],
                "supervision_policy": target["supervision_policy"],
                "daily_bar_cache": cache,
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            }

        replay = replays[0]
        summary = replay.get("summary") or {}
        segments = replay.get("segments") or []
        created_at = replay.get("created_at")
        latest_phase = str(replay.get("latest_phase") or summary.get("latest_phase") or "unknown")
        stale_reason = self._focus_replay_stale_reason(summary, created_at, cache)
        status = "stale_replay" if stale_reason else "ready"

        return {
            "symbol": symbol,
            "name": target["name"],
            "role": target["role"],
            "status": status,
            "stale_reason": stale_reason,
            "latest_phase": latest_phase,
            "latest_phase_name": summary.get("latest_phase_name"),
            "phase_path": summary.get("phase_path", []),
            "segment_count": summary.get("segment_count", len(segments)),
            "bars_count": replay.get("bars_count"),
            "period_return_pct": summary.get("period_return_pct"),
            "latest_close": summary.get("latest_close"),
            "summary_end_date": summary.get("end_date"),
            "replay_created_at": created_at,
            "diagnosis": summary.get("diagnosis"),
            "dataset1_anchor": target["dataset1_anchor"],
            "supervision_policy": target["supervision_policy"],
            "current_training_use": self._focus_current_training_use(target, latest_phase),
            "recent_segments": segments[-5:],
            "daily_bar_cache": cache,
            "training_questions": summary.get("training_questions", []),
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _daily_bar_cache_summary(self, symbol: str) -> dict[str, Any]:
        row = self.store.fetch_one(
            """
            SELECT COUNT(*) AS bar_count,
                   MIN(trade_date) AS first_trade_date,
                   MAX(trade_date) AS last_trade_date
            FROM daily_bar_cache
            WHERE symbol = ?
              AND trade_date != 'ERROR'
            """,
            (symbol,),
        )
        return {
            "bar_count": int((row or {}).get("bar_count") or 0),
            "first_trade_date": (row or {}).get("first_trade_date"),
            "last_trade_date": (row or {}).get("last_trade_date"),
        }

    def _focus_replay_stale_reason(
        self,
        summary: dict[str, Any],
        created_at: str | None,
        cache: dict[str, Any],
    ) -> str | None:
        end_date = summary.get("end_date")
        cache_last = cache.get("last_trade_date")
        if cache_last and end_date and str(cache_last) > str(end_date):
            return "daily_bar_cache_newer_than_phase_replay"
        if not created_at:
            return "missing_replay_created_at"
        try:
            created = datetime.fromisoformat(str(created_at).replace("Z", "+00:00"))
        except ValueError:
            return "invalid_replay_created_at"
        if (datetime.now() - created.replace(tzinfo=None)).days > 7:
            return "phase_replay_older_than_7_days"
        return None

    def _focus_current_training_use(self, target: dict[str, Any], latest_phase: str) -> str:
        role = str(target.get("role") or "")
        if "distribution" in role or latest_phase in {"distribution", "post_distribution_watch"}:
            return "training_or_observe_only_no_new_entry_priority"
        if role == "method_success_markup_sample":
            return "learn_pre_markup_path_and_sell_discipline"
        if role == "focus_watch_execution_discipline_sample":
            return "watch_only_until_stabilization_and_manual_review"
        return "collect_more_phase_evidence"

    def _phase_similarity_performance(
        self,
        replay: dict[str, Any],
        sandbox: dict[str, Any],
    ) -> dict[str, Any]:
        evaluations = [
            item
            for item in (sandbox.get("evaluations") or [])
            if item.get("status") == "completed"
        ]
        symbols = sorted({str(item.get("symbol")) for item in evaluations if item.get("symbol")})
        matches = self._latest_phase_matches_by_symbol(symbols)
        rows: list[dict[str, Any]] = []
        groups: dict[str, dict[str, Any]] = {}
        missing_match_count = 0
        for item in evaluations:
            symbol = str(item.get("symbol") or "")
            match = matches.get(symbol)
            if not match:
                missing_match_count += 1
                continue
            summary = match.get("summary") or {}
            best = summary.get("best_match") or {}
            key = self._phase_similarity_group_key(best, summary)
            group = groups.setdefault(
                key,
                {
                    "key": key,
                    "core_symbol": best.get("core_symbol"),
                    "sample_role": best.get("sample_role"),
                    "target_latest_phase": summary.get("target_latest_phase"),
                    "target_latest_phase_name": summary.get("target_latest_phase_name"),
                    "sample_count": 0,
                    "win_count": 0,
                    "total_close_return_pct": 0.0,
                    "total_max_return_pct": 0.0,
                    "total_min_return_pct": 0.0,
                    "best_score": 0.0,
                    "examples": [],
                },
            )
            close_return = float(item.get("close_return_pct") or 0)
            max_return = float(item.get("max_return_pct") or 0)
            min_return = float(item.get("min_return_pct") or 0)
            group["sample_count"] += 1
            if item.get("outcome_label") in {"strong_follow_through", "mild_follow_through"}:
                group["win_count"] += 1
            group["total_close_return_pct"] += close_return
            group["total_max_return_pct"] += max_return
            group["total_min_return_pct"] += min_return
            group["best_score"] = max(float(group["best_score"]), float(best.get("score") or 0))
            if len(group["examples"]) < 5:
                group["examples"].append(
                    {
                        "symbol": symbol,
                        "signal_date": item.get("signal_date"),
                        "pattern_id": item.get("pattern_id"),
                        "outcome_label": item.get("outcome_label"),
                        "close_return_pct": round(close_return, 6),
                        "best_match_score": best.get("score"),
                        "target_latest_phase": summary.get("target_latest_phase"),
                        "review_only": True,
                        "simulation_only": True,
                    }
                )
            rows.append(
                {
                    "symbol": symbol,
                    "signal_date": item.get("signal_date"),
                    "pattern_id": item.get("pattern_id"),
                    "outcome_label": item.get("outcome_label"),
                    "close_return_pct": round(close_return, 6),
                    "group_key": key,
                    "best_match": {
                        "core_symbol": best.get("core_symbol"),
                        "sample_role": best.get("sample_role"),
                        "score": best.get("score"),
                        "target_latest_phase": summary.get("target_latest_phase"),
                    },
                    "review_only": True,
                    "simulation_only": True,
                }
            )

        group_rows: list[dict[str, Any]] = []
        for group in groups.values():
            count = int(group["sample_count"])
            if count <= 0:
                continue
            avg_return = float(group.pop("total_close_return_pct")) / count
            avg_max = float(group.pop("total_max_return_pct")) / count
            avg_min = float(group.pop("total_min_return_pct")) / count
            group["win_rate"] = round(float(group["win_count"]) / count, 6)
            group["average_close_return_pct"] = round(avg_return, 6)
            group["average_max_return_pct"] = round(avg_max, 6)
            group["average_min_return_pct"] = round(avg_min, 6)
            group["suggested_treatment"] = self._phase_similarity_treatment(group)
            confidence = self._phase_similarity_confidence(group)
            group["confidence_tier"] = confidence["tier"]
            group["confidence_score"] = confidence["score"]
            group["confidence_reasons"] = confidence["reasons"]
            group["downside_risk_note"] = confidence["downside_risk_note"]
            group["review_only"] = True
            group["simulation_only"] = True
            group_rows.append(group)
        group_rows.sort(
            key=lambda row: (
                row.get("suggested_treatment") not in {
                    "observe_only_distribution_risk",
                    "downgrade_to_smallest_dry_run_or_observe",
                },
                -int(row.get("sample_count") or 0),
                -float(row.get("average_close_return_pct") or 0),
            )
        )
        return {
            "schema_version": "phase_similarity_performance.v1",
            "status": "completed" if group_rows else "insufficient_phase_matches",
            "evaluated_count": len(evaluations),
            "matched_count": len(rows),
            "missing_match_count": missing_match_count,
            "by_group": group_rows,
            "items": rows[:80],
            "supervision": {
                "summary": "Compare sandbox outcomes by similarity to Sanwei success path versus Gold Mantis distribution path.",
                "recommendations": self._phase_similarity_recommendations(group_rows, missing_match_count),
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            },
            "policy": {
                "uses_existing_phase_matches_only": True,
                "fetches_external_history": False,
                "writes_rules_yaml": False,
                "broker_or_order_action": False,
            },
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _phase_confidence_walk_forward(self, phase_similarity_performance: dict[str, Any]) -> dict[str, Any]:
        groups = phase_similarity_performance.get("by_group") or []
        items = phase_similarity_performance.get("items") or []
        if not isinstance(groups, list) or not isinstance(items, list):
            return self._phase_confidence_walk_forward_skipped("invalid_phase_similarity_payload")

        group_by_key = {
            str(group.get("key")): group
            for group in groups
            if isinstance(group, dict) and group.get("key")
        }
        target_groups = [
            dict(group)
            for group in groups
            if isinstance(group, dict)
            and group.get("confidence_tier") in PHASE_CONFIDENCE_TARGET_TIERS
        ]
        if not target_groups:
            return self._phase_confidence_walk_forward_skipped("no_high_or_medium_phase_confidence_groups")

        items_by_group: dict[str, list[dict[str, Any]]] = {}
        for item in items:
            if not isinstance(item, dict):
                continue
            group_key = str(item.get("group_key") or "")
            if not group_key:
                continue
            items_by_group.setdefault(group_key, []).append(dict(item))

        evaluations = [
            self._phase_confidence_group_walk_forward(group, items_by_group.get(str(group.get("key")), []))
            for group in target_groups
        ]
        evaluations.sort(
            key=lambda item: (
                item.get("status") != "passed_for_review",
                -float(item.get("total_equal_weight_cumulative_return_pct") or 0),
                -float(item.get("weighted_win_rate") or 0),
                str(item.get("group_key") or ""),
            )
        )
        passed = [item for item in evaluations if item.get("status") == "passed_for_review"]
        blocked = [item for item in evaluations if item.get("status") != "passed_for_review"]
        robust = [
            item
            for item in evaluations
            if ((item.get("robustness") or {}).get("status") == "robust_enough_for_review")
        ]
        return {
            "schema_version": "phase_confidence_walk_forward.v1",
            "status": "passed_for_review" if passed else "blocked",
            "evaluated_group_count": len(evaluations),
            "passed_group_count": len(passed),
            "blocked_group_count": len(blocked),
            "robust_group_count": len(robust),
            "target_confidence_tiers": sorted(PHASE_CONFIDENCE_TARGET_TIERS),
            "groups": evaluations,
            "gate": {
                "status": "passed_for_review" if passed else "blocked",
                "reasons": [] if passed else ["no_phase_confidence_group_passed_walk_forward"],
                "min_sample_count": MIN_PHASE_CONFIDENCE_WF_SAMPLE_COUNT,
                "min_fold_count": MIN_PHASE_CONFIDENCE_WF_FOLD_COUNT,
                "min_fold_sample_count": MIN_PHASE_CONFIDENCE_WF_FOLD_SAMPLE_COUNT,
                "min_weighted_win_rate": MIN_PHASE_CONFIDENCE_WF_WIN_RATE,
                "min_fold_win_rate": MIN_PHASE_CONFIDENCE_WF_MIN_FOLD_WIN_RATE,
                "min_cumulative_return_pct": MIN_PHASE_CONFIDENCE_WF_CUMULATIVE_RETURN_PCT,
                "max_fold_loss_pct": MAX_PHASE_CONFIDENCE_WF_FOLD_LOSS_PCT,
                "requires_human_review": True,
                "writes_rules_yaml": False,
                "auto_apply": False,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            },
            "supervision": {
                "summary": "Validate high/medium phase-confidence groups across chronological folds before trusting review priority.",
                "next_action": (
                    "Only groups that pass this review gate can raise small dry-run review priority; "
                    "blocked groups remain observe-only or collect-more-samples."
                ),
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            },
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _phase_confidence_walk_forward_skipped(self, reason: str) -> dict[str, Any]:
        return {
            "schema_version": "phase_confidence_walk_forward.v1",
            "status": "skipped",
            "reason": reason,
            "evaluated_group_count": 0,
            "passed_group_count": 0,
            "blocked_group_count": 0,
            "groups": [],
            "gate": {
                "status": "blocked",
                "reasons": [reason],
                "requires_human_review": True,
                "writes_rules_yaml": False,
                "auto_apply": False,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            },
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _phase_confidence_group_walk_forward(
        self,
        group: dict[str, Any],
        items: list[dict[str, Any]],
    ) -> dict[str, Any]:
        ordered = sorted(
            items,
            key=lambda item: (str(item.get("signal_date") or ""), str(item.get("symbol") or "")),
        )
        folds = self._phase_confidence_folds(ordered)
        fold_results: list[dict[str, Any]] = []
        total_samples = 0
        weighted_win_sum = 0.0
        weighted_return_sum = 0.0
        cumulative_factor = 1.0
        min_fold_return = None
        min_fold_win_rate = None
        min_fold_sample_count = None

        for idx, fold in enumerate(folds, start=1):
            metrics = self._phase_confidence_return_metrics(fold)
            sample_count = int(metrics.get("sample_count") or 0)
            win_rate = float(metrics.get("win_rate") or 0)
            average_return = float(metrics.get("average_return_pct") or 0)
            cumulative_return = float(metrics.get("equal_weight_cumulative_return_pct") or 0)
            total_samples += sample_count
            weighted_win_sum += win_rate * sample_count
            weighted_return_sum += average_return * sample_count
            cumulative_factor *= 1 + cumulative_return / 100
            min_fold_return = cumulative_return if min_fold_return is None else min(min_fold_return, cumulative_return)
            min_fold_win_rate = win_rate if min_fold_win_rate is None else min(min_fold_win_rate, win_rate)
            min_fold_sample_count = (
                sample_count
                if min_fold_sample_count is None
                else min(min_fold_sample_count, sample_count)
            )
            fold_results.append(
                {
                    "fold_index": idx,
                    "start_signal_date": fold[0].get("signal_date") if fold else None,
                    "end_signal_date": fold[-1].get("signal_date") if fold else None,
                    "sample_count": sample_count,
                    "win_rate": round(win_rate, 6),
                    "average_return_pct": round(average_return, 6),
                    "equal_weight_cumulative_return_pct": round(cumulative_return, 6),
                    "review_only": True,
                    "simulation_only": True,
                }
            )

        weighted_win_rate = weighted_win_sum / total_samples if total_samples else 0.0
        weighted_average_return = weighted_return_sum / total_samples if total_samples else 0.0
        total_cumulative_return = (cumulative_factor - 1) * 100 if fold_results else 0.0
        gate_reasons: list[str] = []
        if len(ordered) < MIN_PHASE_CONFIDENCE_WF_SAMPLE_COUNT:
            gate_reasons.append("phase_confidence_sample_count_too_low")
        if len(folds) < MIN_PHASE_CONFIDENCE_WF_FOLD_COUNT:
            gate_reasons.append("phase_confidence_fold_count_too_low")
        if (min_fold_sample_count or 0) < MIN_PHASE_CONFIDENCE_WF_FOLD_SAMPLE_COUNT:
            gate_reasons.append("phase_confidence_fold_sample_count_too_low")
        if weighted_win_rate < MIN_PHASE_CONFIDENCE_WF_WIN_RATE:
            gate_reasons.append("phase_confidence_win_rate_too_low")
        if (min_fold_win_rate or 0.0) < MIN_PHASE_CONFIDENCE_WF_MIN_FOLD_WIN_RATE:
            gate_reasons.append("phase_confidence_min_fold_win_rate_too_low")
        if total_cumulative_return < MIN_PHASE_CONFIDENCE_WF_CUMULATIVE_RETURN_PCT:
            gate_reasons.append("phase_confidence_cumulative_return_below_20_pct")
        if min_fold_return is not None and min_fold_return < MAX_PHASE_CONFIDENCE_WF_FOLD_LOSS_PCT:
            gate_reasons.append("phase_confidence_fold_loss_too_large")
        if weighted_average_return <= 0:
            gate_reasons.append("phase_confidence_average_return_not_positive")

        return {
            "group_key": group.get("key"),
            "confidence_tier": group.get("confidence_tier"),
            "confidence_score": group.get("confidence_score"),
            "suggested_treatment": group.get("suggested_treatment"),
            "status": "passed_for_review" if not gate_reasons else "blocked",
            "sample_count": len(ordered),
            "fold_count": len(folds),
            "min_fold_sample_count": int(min_fold_sample_count or 0),
            "weighted_win_rate": round(weighted_win_rate, 6),
            "weighted_average_return_pct": round(weighted_average_return, 6),
            "total_equal_weight_cumulative_return_pct": round(total_cumulative_return, 6),
            "min_fold_win_rate": round(min_fold_win_rate or 0.0, 6),
            "min_fold_cumulative_return_pct": round(min_fold_return or 0.0, 6),
            "gate_reasons": gate_reasons,
            "folds": fold_results,
            "robustness": self._phase_confidence_robustness(ordered),
            "policy": {
                "review_priority_only": True,
                "writes_rules_yaml": False,
                "auto_apply": False,
                "broker_or_order_action": False,
            },
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _phase_confidence_robustness(self, items: list[dict[str, Any]]) -> dict[str, Any]:
        by_board: dict[str, list[dict[str, Any]]] = {}
        by_market: dict[str, list[dict[str, Any]]] = {}
        market_contexts: list[dict[str, Any]] = []
        for item in items:
            symbol = str(item.get("symbol") or "")
            board = infer_board_type(normalize_a_share_code(symbol), None) if symbol else "unknown"
            by_board.setdefault(board, []).append(item)
            market = self._phase_confidence_market_regime(str(item.get("signal_date") or ""))
            market_contexts.append(market)
            by_market.setdefault(str(market.get("regime") or "insufficient_benchmark_data"), []).append(item)

        board_rows = self._phase_confidence_subgroup_rows(by_board)
        market_rows = self._phase_confidence_subgroup_rows(by_market)
        warnings: list[str] = []
        warnings.extend(self._phase_confidence_subgroup_warnings("board", board_rows))
        warnings.extend(self._phase_confidence_subgroup_warnings("market_regime", market_rows))
        if len(items) < 10:
            warnings.append("small_group_sample_count_for_robustness")
        if len(board_rows) < 2:
            warnings.append("single_board_concentration")
        if len([row for row in market_rows if row.get("key") != "insufficient_benchmark_data"]) < 2:
            warnings.append("limited_market_regime_coverage")
        status = "robust_enough_for_review" if not warnings else "needs_more_context"
        return {
            "schema_version": "phase_confidence_robustness.v1",
            "status": status,
            "by_board": board_rows,
            "by_market_regime": market_rows,
            "market_context_examples": market_contexts[:5],
            "warnings": warnings,
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _phase_confidence_subgroup_rows(self, groups: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
        rows = [
            {
                "key": key,
                **self._phase_confidence_return_metrics(items),
                "review_only": True,
                "simulation_only": True,
            }
            for key, items in groups.items()
        ]
        rows.sort(
            key=lambda row: (
                -int(row.get("sample_count") or 0),
                -float(row.get("equal_weight_cumulative_return_pct") or 0),
                str(row.get("key") or ""),
            )
        )
        return rows

    def _phase_confidence_subgroup_warnings(self, prefix: str, rows: list[dict[str, Any]]) -> list[str]:
        warnings: list[str] = []
        for row in rows:
            sample_count = int(row.get("sample_count") or 0)
            if sample_count < 2:
                continue
            win_rate = float(row.get("win_rate") or 0)
            cumulative = float(row.get("equal_weight_cumulative_return_pct") or 0)
            if win_rate < 0.5:
                warnings.append(f"{prefix}_{row.get('key')}_win_rate_below_50_pct")
            if cumulative < 0:
                warnings.append(f"{prefix}_{row.get('key')}_cumulative_return_negative")
        return warnings

    def _phase_confidence_market_regime(self, signal_date: str) -> dict[str, Any]:
        if not signal_date:
            return {"regime": "insufficient_benchmark_data", "reason": "missing_signal_date"}
        for benchmark in ("SH000300", "SH000001"):
            rows = self.store.fetch_all(
                """
                SELECT trade_date, close
                FROM daily_bar_cache
                WHERE symbol = ?
                  AND quality_status = 'ready'
                  AND trade_date != 'ERROR'
                  AND trade_date <= ?
                ORDER BY trade_date DESC
                LIMIT 6
                """,
                (benchmark, signal_date),
            )
            ordered = list(reversed([dict(row) for row in rows]))
            if len(ordered) < 2:
                continue
            first = float(ordered[0].get("close") or 0)
            last = float(ordered[-1].get("close") or 0)
            if first <= 0 or last <= 0:
                continue
            return_pct = (last / first - 1) * 100
            if return_pct >= 1.0:
                regime = "benchmark_up"
            elif return_pct <= -1.0:
                regime = "benchmark_down"
            else:
                regime = "benchmark_neutral"
            return {
                "benchmark_symbol": benchmark,
                "regime": regime,
                "lookback_bar_count": len(ordered),
                "start_date": ordered[0].get("trade_date"),
                "end_date": ordered[-1].get("trade_date"),
                "return_pct": round(return_pct, 6),
            }
        return {
            "regime": "insufficient_benchmark_data",
            "reason": "no_ready_benchmark_bars_before_signal",
            "signal_date": signal_date,
        }

    def _phase_confidence_folds(self, items: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
        if len(items) < MIN_PHASE_CONFIDENCE_WF_SAMPLE_COUNT:
            return []
        fold_count = min(4, max(MIN_PHASE_CONFIDENCE_WF_FOLD_COUNT, len(items) // MIN_PHASE_CONFIDENCE_WF_FOLD_SAMPLE_COUNT))
        fold_count = min(fold_count, len(items) // MIN_PHASE_CONFIDENCE_WF_FOLD_SAMPLE_COUNT)
        if fold_count < MIN_PHASE_CONFIDENCE_WF_FOLD_COUNT:
            return []
        fold_size = max(MIN_PHASE_CONFIDENCE_WF_FOLD_SAMPLE_COUNT, len(items) // fold_count)
        start = max(0, len(items) - fold_count * fold_size)
        folds: list[list[dict[str, Any]]] = []
        for fold_index in range(fold_count):
            left = start + fold_index * fold_size
            right = left + fold_size
            fold = items[left:right]
            if len(fold) >= MIN_PHASE_CONFIDENCE_WF_FOLD_SAMPLE_COUNT:
                folds.append(fold)
        return folds

    def _phase_confidence_return_metrics(self, items: list[dict[str, Any]]) -> dict[str, Any]:
        returns = [float(item.get("close_return_pct") or 0) for item in items]
        wins = [value for value in returns if value > 0]
        compounded = 1.0
        for value in returns:
            compounded *= 1 + value / 100
        return {
            "sample_count": len(returns),
            "win_rate": round(len(wins) / len(returns), 6) if returns else 0.0,
            "average_return_pct": round(sum(returns) / len(returns), 6) if returns else 0.0,
            "equal_weight_cumulative_return_pct": round((compounded - 1) * 100, 6) if returns else 0.0,
        }

    def _latest_phase_matches_by_symbol(self, symbols: list[str]) -> dict[str, dict[str, Any]]:
        if not symbols:
            return {}
        placeholders = ",".join("?" for _ in symbols)
        rows = self.store.fetch_all(
            f"""
            SELECT id, target_symbol, target_name, target_replay_id,
                   summary_json, matches_json, created_at
            FROM main_force_phase_matches
            WHERE target_symbol IN ({placeholders})
            ORDER BY target_symbol ASC, id DESC
            """,
            tuple(symbols),
        )
        result: dict[str, dict[str, Any]] = {}
        for row in rows:
            symbol = str(row["target_symbol"])
            if symbol in result:
                continue
            result[symbol] = {
                "id": row["id"],
                "target_symbol": symbol,
                "target_name": row.get("target_name"),
                "target_replay_id": row.get("target_replay_id"),
                "summary": _json_loads(row.get("summary_json"), {}),
                "matches": _json_loads(row.get("matches_json"), []),
                "created_at": row.get("created_at"),
            }
        return result

    def _phase_similarity_group_key(self, best: dict[str, Any], summary: dict[str, Any]) -> str:
        core = str(best.get("core_symbol") or "unknown_core")
        phase = str(summary.get("target_latest_phase") or "unknown_phase")
        return f"{core}:{phase}"

    def _phase_similarity_treatment(self, group: dict[str, Any]) -> str:
        core_symbol = group.get("core_symbol")
        latest_phase = group.get("target_latest_phase")
        avg_return = float(group.get("average_close_return_pct") or 0)
        win_rate = float(group.get("win_rate") or 0)
        if core_symbol == "SZ002081" and latest_phase in {"distribution", "post_distribution_watch"}:
            return "observe_only_distribution_risk"
        if latest_phase in {"distribution", "post_distribution_watch"}:
            return "downgrade_to_smallest_dry_run_or_observe"
        if core_symbol == "SZ002115" and latest_phase == "markup" and win_rate >= 0.6 and avg_return > 0:
            return "raise_review_priority_dry_run_only"
        if latest_phase == "markup" and avg_return > 0:
            return "review_momentum_but_require_distribution_check"
        return "collect_more_samples"

    def _phase_similarity_confidence(self, group: dict[str, Any]) -> dict[str, Any]:
        sample_count = int(group.get("sample_count") or 0)
        win_rate = float(group.get("win_rate") or 0)
        avg_return = float(group.get("average_close_return_pct") or 0)
        avg_min = float(group.get("average_min_return_pct") or 0)
        best_score = float(group.get("best_score") or 0)
        treatment = str(group.get("suggested_treatment") or "collect_more_samples")
        phase = str(group.get("target_latest_phase") or "unknown")
        reasons: list[str] = []
        score = 50

        if sample_count >= 20:
            score += 15
            reasons.append("sample_count>=20")
        elif sample_count >= 10:
            score += 10
            reasons.append("sample_count>=10")
        elif sample_count >= 5:
            score += 5
            reasons.append("sample_count>=5")
        else:
            score -= 15
            reasons.append("small_sample_count<5")

        if win_rate >= 0.75:
            score += 15
            reasons.append("win_rate>=75%")
        elif win_rate >= 0.6:
            score += 8
            reasons.append("win_rate>=60%")
        else:
            score -= 12
            reasons.append("win_rate<60%")

        if avg_return >= 5:
            score += 15
            reasons.append("avg_return>=5%")
        elif avg_return >= 2:
            score += 8
            reasons.append("avg_return>=2%")
        elif avg_return > 0:
            score += 3
            reasons.append("avg_return_positive")
        else:
            score -= 15
            reasons.append("avg_return<=0")

        if avg_min >= -2:
            score += 10
            downside_note = "average intratrade downside is shallow in this group."
            reasons.append("avg_min_drawdown>=-2%")
        elif avg_min >= -5:
            downside_note = "average intratrade downside is moderate; require small dry-run sizing."
            reasons.append("avg_min_drawdown_between_-5%_and_-2%")
        else:
            score -= 15
            downside_note = "average intratrade downside is deep; downgrade confidence even if win rate is high."
            reasons.append("avg_min_drawdown<-5%")

        if best_score >= 80:
            score += 5
            reasons.append("best_similarity_score>=80")
        elif best_score < 50:
            score -= 5
            reasons.append("best_similarity_score<50")

        if treatment == "observe_only_distribution_risk":
            score = min(score, 45)
            tier = "observe_only_distribution_risk_confidence"
            reasons.append("distribution_path_caps_confidence")
        elif treatment == "downgrade_to_smallest_dry_run_or_observe":
            score = min(score, 55)
            tier = "late_cycle_low_confidence_observe_or_smallest_dry_run"
            reasons.append("late_cycle_path_caps_confidence")
        elif sample_count < 5:
            tier = "low_confidence_collect_more_samples"
        elif (
            treatment == "raise_review_priority_dry_run_only"
            and score >= 70
            and avg_min >= -3
            and phase == "markup"
        ):
            tier = "high_review_confidence_dry_run_only"
        elif score >= 55 and avg_return > 0:
            tier = "medium_review_confidence_dry_run_only"
        else:
            tier = "low_confidence_collect_more_samples"

        score = max(0, min(100, score))
        return {
            "tier": tier,
            "score": round(score, 2),
            "reasons": reasons[:8],
            "downside_risk_note": downside_note,
        }

    def _phase_similarity_recommendations(
        self,
        groups: list[dict[str, Any]],
        missing_match_count: int,
    ) -> list[str]:
        recommendations = [
            "Use phase similarity only as a review layer; it must not change allowed/quantity or live-trading permissions.",
        ]
        if missing_match_count:
            recommendations.append(
                f"{missing_match_count} sandbox outcomes lack a stored phase match; refresh phase matches before trusting stratification."
            )
        risky = [
            row
            for row in groups
            if row.get("suggested_treatment") in {
                "observe_only_distribution_risk",
                "downgrade_to_smallest_dry_run_or_observe",
            }
        ]
        if risky:
            recommendations.append(
                "Distribution-like groups exist; keep them observe-only or smallest dry-run even if raw Dataset2 returns look positive."
            )
        positive = [
            row
            for row in groups
            if row.get("suggested_treatment") == "raise_review_priority_dry_run_only"
        ]
        if positive:
            recommendations.append(
                "Sanwei-like markup groups with positive sandbox outcomes can raise review priority, still behind risk gates and dry-run evidence."
            )
        return recommendations

    def _latest_rule_family_performance_memory(self) -> dict[str, Any]:
        if settings.enable_live_trading:
            return {
                "schema_version": "offhour_rule_family_performance_memory.v1",
                "status": "blocked",
                "blocked_reasons": ["live_trading_enabled"],
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            }
        try:
            row = self.store.fetch_one(
                """
                SELECT id, payload_json, created_at
                FROM events
                WHERE event_type = 'dataset2_training_run'
                  AND payload_json LIKE '%rule_family_performance_memory%'
                ORDER BY id DESC
                LIMIT 1
                """
            )
        except (sqlite3.Error, TypeError, ValueError):
            row = None
        if not row:
            return {
                "schema_version": "offhour_rule_family_performance_memory.v1",
                "status": "empty",
                "blocked_reasons": ["missing_dataset2_training_memory"],
                "summary": {},
                "top_backtest_groups": [],
                "top_execution_groups": [],
                "recommendations": [
                    "Run Dataset2 controlled training after offhour replay so model candidates can include rule-family performance evidence."
                ],
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            }

        payload = _json_loads(row.get("payload_json"), {})
        memory = payload.get("rule_family_performance_memory") or {}
        if not isinstance(memory, dict):
            return {
                "schema_version": "offhour_rule_family_performance_memory.v1",
                "status": "empty",
                "blocked_reasons": ["invalid_dataset2_training_memory"],
                "summary": {},
                "top_backtest_groups": [],
                "top_execution_groups": [],
                "recommendations": [],
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            }
        if memory.get("review_only") is False or memory.get("simulation_only") is False:
            return {
                "schema_version": "offhour_rule_family_performance_memory.v1",
                "status": "blocked",
                "blocked_reasons": ["unsafe_rule_family_memory"],
                "source_event_id": row["id"],
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            }

        top_backtest_groups = self._compact_rule_family_groups(memory.get("top_backtest_groups"), limit=5)
        top_execution_groups = self._compact_execution_groups(memory.get("top_execution_groups"), limit=3)
        recommendations = self._rule_family_memory_recommendations(top_backtest_groups)
        return {
            "schema_version": "offhour_rule_family_performance_memory.v1",
            "source_schema_version": memory.get("schema_version"),
            "status": "ready" if top_backtest_groups or top_execution_groups else "empty",
            "source_event_id": row["id"],
            "source_created_at": row.get("created_at"),
            "summary": memory.get("summary") or {},
            "top_backtest_groups": top_backtest_groups,
            "top_execution_groups": top_execution_groups,
            "recommendations": recommendations,
            "interpretation": [
                "Rule-family memory can rank review attention for offhour scorecards.",
                "It cannot write production rules, bypass risk gates, or grant order permission.",
                "WAIT_CONFIRMATION families still require reclaim or support confirmation before dry-run review.",
            ],
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _compact_rule_family_groups(self, groups: object, limit: int) -> list[dict[str, Any]]:
        if not isinstance(groups, list):
            return []
        compacted: list[dict[str, Any]] = []
        for group in groups:
            if not isinstance(group, dict):
                continue
            compacted.append(
                {
                    "key": group.get("key"),
                    "pattern_id": group.get("pattern_id"),
                    "pattern_name": group.get("pattern_name"),
                    "category": group.get("category"),
                    "action_label": group.get("action_label"),
                    "risk_level": group.get("risk_level"),
                    "trade_count": int(group.get("trade_count") or 0),
                    "win_rate": round(float(group.get("win_rate") or 0.0), 6),
                    "average_return_pct": round(float(group.get("average_return_pct") or 0.0), 6),
                    "total_return_pct": round(float(group.get("total_return_pct") or 0.0), 6),
                    "worst_return_pct": round(float(group.get("worst_return_pct") or 0.0), 6),
                    "review_priority_score": round(float(group.get("review_priority_score") or 0.0), 6),
                    "symbols": (group.get("symbols") or [])[:8] if isinstance(group.get("symbols"), list) else [],
                    "review_only": True,
                    "simulation_only": True,
                }
            )
            if len(compacted) >= max(1, min(int(limit or 5), 20)):
                break
        return compacted

    def _compact_execution_groups(self, groups: object, limit: int) -> list[dict[str, Any]]:
        if not isinstance(groups, list):
            return []
        compacted: list[dict[str, Any]] = []
        for group in groups:
            if not isinstance(group, dict):
                continue
            compacted.append(
                {
                    "key": group.get("key"),
                    "source": group.get("source"),
                    "action": group.get("action"),
                    "status": group.get("status"),
                    "sample_count": int(group.get("sample_count") or 0),
                    "dry_run_count": int(group.get("dry_run_count") or 0),
                    "executed_count": int(group.get("executed_count") or 0),
                    "blocked_count": int(group.get("blocked_count") or 0),
                    "readback_count": int(group.get("readback_count") or 0),
                    "feasible_rate": round(float(group.get("feasible_rate") or 0.0), 6),
                    "blocked_rate": round(float(group.get("blocked_rate") or 0.0), 6),
                    "review_only": True,
                    "simulation_only": True,
                }
            )
            if len(compacted) >= max(1, min(int(limit or 3), 20)):
                break
        return compacted

    def _rule_family_memory_recommendations(self, groups: list[dict[str, Any]]) -> list[str]:
        if not groups:
            return ["Collect offhour rule-family backtest trades before using this scorecard for weighting review."]
        recommendations = []
        top = groups[0]
        recommendations.append(
            "Prioritize rule-family review for "
            f"{top.get('pattern_id')}/{top.get('pattern_name')} "
            f"with win_rate={top.get('win_rate')} and avg_return_pct={top.get('average_return_pct')}; "
            "use dry-run evidence only, not production rule changes."
        )
        wait_groups = [group for group in groups if str(group.get("action_label") or "") == "WAIT_CONFIRMATION"]
        if wait_groups:
            recommendations.append(
                "WAIT_CONFIRMATION families need reclaim, support, or close-confirmation evidence before simulated entry review."
            )
        high_risk_groups = [
            group
            for group in groups
            if "high" in str(group.get("risk_level") or "").lower()
            or float(group.get("worst_return_pct") or 0.0) <= -7.0
        ]
        if high_risk_groups:
            recommendations.append(
                "High-risk or deep-loss rule families may raise observation priority but should cap simulated dry-run size."
            )
        return recommendations

    def _rule_family_review_gate(self, memory: dict[str, Any]) -> dict[str, Any]:
        reasons: list[str] = []
        top_groups = memory.get("top_backtest_groups") or []
        if memory.get("status") != "ready":
            reasons.append("rule_family_memory_not_ready")
        if not top_groups:
            reasons.append("missing_rule_family_backtest_groups")
        else:
            top = top_groups[0]
            if int(top.get("trade_count") or 0) < 5:
                reasons.append("insufficient_rule_family_trade_count")
            if float(top.get("average_return_pct") or 0.0) <= 0:
                reasons.append("top_rule_family_average_return_not_positive")
        return {
            "schema_version": "rule_family_review_gate.v1",
            "status": "passed_for_review" if not reasons else "blocked",
            "reasons": reasons,
            "allowed_effect": "scorecard_review_priority_only",
            "requires_human_review": True,
            "writes_rules_yaml": False,
            "auto_apply": False,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _candidate_review_priority_framework(
        self,
        signal_optimization: dict[str, Any],
        rule_family_memory: dict[str, Any],
        rule_family_gate: dict[str, Any],
        reclaim_watchlist: dict[str, Any],
        reclaim_transition_study: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        def safe_float(payload: dict[str, Any], key: str) -> float:
            try:
                return float((payload or {}).get(key) or 0.0)
            except (TypeError, ValueError):
                return 0.0

        selected = signal_optimization.get("selected_stable_candidate") or {}
        selected_validation = selected.get("source_validation_metrics") or {}
        signal_gate = signal_optimization.get("gate") or {}
        stable_points = 0
        stable_reasons: list[str] = []
        if selected.get("status") == "passed_for_simulation_review" or signal_gate.get("status") == "passed_for_simulation_review":
            stable_points += 25
            stable_reasons.append("stable_candidate_passed_review_gate")
        validation_return = safe_float(selected_validation, "equal_weight_cumulative_return_pct")
        validation_win_rate = safe_float(selected_validation, "win_rate")
        walk_forward_return = safe_float(selected, "total_equal_weight_cumulative_return_pct")
        walk_forward_win_rate = safe_float(selected, "weighted_win_rate")
        if validation_return >= MIN_OPTIMIZED_VALIDATION_CUMULATIVE_RETURN_PCT:
            stable_points += 8
            stable_reasons.append("validation_return_above_20pct")
        if validation_win_rate >= MIN_OPTIMIZED_VALIDATION_WIN_RATE:
            stable_points += 4
            stable_reasons.append("validation_win_rate_above_gate")
        if walk_forward_return > 0 and walk_forward_win_rate >= 0.55:
            stable_points += 3
            stable_reasons.append("walk_forward_positive")
        stable_factor = {
            "name": "stable_candidate_parameters",
            "score_points": min(stable_points, 40),
            "status": "ready" if stable_reasons else "insufficient_evidence",
            "reasons": stable_reasons,
            "evidence": {
                "gate_status": signal_gate.get("status"),
                "selected_status": selected.get("status"),
                "validation_return_pct": round(validation_return, 6),
                "validation_win_rate": round(validation_win_rate, 6),
                "walk_forward_return_pct": round(walk_forward_return, 6),
                "walk_forward_win_rate": round(walk_forward_win_rate, 6),
                "parameters": selected.get("parameters") or {},
            },
            "review_only": True,
            "simulation_only": True,
        }

        top_groups = rule_family_memory.get("top_backtest_groups") or []
        top_family = top_groups[0] if top_groups and isinstance(top_groups[0], dict) else {}
        family_points = 0
        family_reasons: list[str] = []
        family_trade_count = safe_float(top_family, "trade_count")
        family_win_rate = safe_float(top_family, "win_rate")
        family_avg_return = safe_float(top_family, "average_return_pct")
        family_worst_return = safe_float(top_family, "worst_return_pct")
        if rule_family_gate.get("status") == "passed_for_review":
            family_points += 15
            family_reasons.append("rule_family_gate_passed")
        if family_trade_count >= 20:
            family_points += 5
            family_reasons.append("rule_family_sample_count_ready")
        if family_win_rate >= MIN_OPTIMIZED_VALIDATION_WIN_RATE:
            family_points += 5
            family_reasons.append("rule_family_win_rate_above_gate")
        if family_avg_return > 0:
            family_points += 5
            family_reasons.append("rule_family_average_return_positive")
        if family_worst_return <= -7:
            family_points = max(0, family_points - 5)
            family_reasons.append("rule_family_deep_loss_penalty")
        family_factor = {
            "name": "rule_family_performance",
            "score_points": min(family_points, 30),
            "status": "ready" if family_reasons else "insufficient_evidence",
            "reasons": family_reasons,
            "evidence": {
                "gate_status": rule_family_gate.get("status"),
                "pattern_id": top_family.get("pattern_id"),
                "pattern_name": top_family.get("pattern_name"),
                "action_label": top_family.get("action_label"),
                "trade_count": int(family_trade_count),
                "win_rate": round(family_win_rate, 6),
                "average_return_pct": round(family_avg_return, 6),
                "worst_return_pct": round(family_worst_return, 6),
            },
            "review_only": True,
            "simulation_only": True,
        }

        counts = reclaim_watchlist.get("counts") or {}
        reclaim_review_count = int(counts.get("reclaim_review") or 0)
        near_reclaim_count = int(counts.get("near_reclaim_watch") or 0)
        pending_count = int(counts.get("pending_future_data") or 0)
        failed_markup_count = int(counts.get("blocked_failed_markup_risk") or 0)
        transition_study = reclaim_transition_study or {}
        transition_by_status = transition_study.get("by_status") or {}
        transition_reclaim = transition_by_status.get("reclaim_review") or {}
        transition_near = transition_by_status.get("near_reclaim_watch") or {}
        transition_reclaim_samples = int(transition_reclaim.get("sample_count") or transition_reclaim.get("count") or 0)
        transition_reclaim_win_rate = safe_float(transition_reclaim, "win_rate")
        transition_reclaim_avg_return = safe_float(transition_reclaim, "average_return_pct")
        transition_reclaim_cumulative = safe_float(transition_reclaim, "cumulative_return_pct")
        transition_near_samples = int(transition_near.get("sample_count") or transition_near.get("count") or 0)
        transition_near_avg_return = safe_float(transition_near, "average_return_pct")
        reclaim_points = 0
        reclaim_reasons: list[str] = []
        if reclaim_review_count > 0:
            reclaim_points += 20
            reclaim_reasons.append("reclaim_review_available")
        elif near_reclaim_count > 0:
            reclaim_points += 10
            reclaim_reasons.append("near_reclaim_watch_available")
        elif pending_count > 0:
            reclaim_points += 4
            reclaim_reasons.append("waiting_for_next_ready_bar")
        if (
            transition_reclaim_samples >= 20
            and transition_reclaim_win_rate >= 0.55
            and transition_reclaim_avg_return > 0
        ):
            reclaim_points += 8
            reclaim_reasons.append("historical_reclaim_transition_positive")
        elif transition_near_samples >= 5 and transition_near_avg_return > 0:
            reclaim_points += 4
            reclaim_reasons.append("historical_near_reclaim_transition_watchable")
        if transition_reclaim_cumulative >= 20:
            reclaim_points += 4
            reclaim_reasons.append("historical_reclaim_cumulative_return_above_20pct")
        if failed_markup_count > 0:
            reclaim_points = max(0, reclaim_points - 8)
            reclaim_reasons.append("failed_markup_risk_penalty")
        reclaim_factor = {
            "name": "reclaim_confirmation_state",
            "score_points": min(reclaim_points, 20),
            "status": "ready" if reclaim_reasons else "no_recent_reclaim_context",
            "reasons": reclaim_reasons,
            "evidence": {
                "reclaim_review_count": reclaim_review_count,
                "near_reclaim_watch_count": near_reclaim_count,
                "pending_future_data_count": pending_count,
                "blocked_failed_markup_risk_count": failed_markup_count,
                "transition_study_status": transition_study.get("status"),
                "transition_reclaim_sample_count": transition_reclaim_samples,
                "transition_reclaim_win_rate": round(transition_reclaim_win_rate, 6),
                "transition_reclaim_average_return_pct": round(transition_reclaim_avg_return, 6),
                "transition_reclaim_cumulative_return_pct": round(transition_reclaim_cumulative, 6),
                "transition_near_reclaim_sample_count": transition_near_samples,
                "transition_near_reclaim_average_return_pct": round(transition_near_avg_return, 6),
            },
            "review_only": True,
            "simulation_only": True,
        }

        execution_groups = rule_family_memory.get("top_execution_groups") or []
        top_execution = execution_groups[0] if execution_groups and isinstance(execution_groups[0], dict) else {}
        execution_points = 0
        execution_reasons: list[str] = []
        execution_sample_count = safe_float(top_execution, "sample_count")
        feasible_rate = safe_float(top_execution, "feasible_rate")
        readback_count = safe_float(top_execution, "readback_count")
        if execution_sample_count > 0 and feasible_rate >= 0.8:
            execution_points += 6
            execution_reasons.append("sim_cockpit_evidence_feasible")
        if readback_count > 0:
            execution_points += 4
            execution_reasons.append("sim_cockpit_readback_seen")
        execution_factor = {
            "name": "sim_cockpit_execution_evidence",
            "score_points": min(execution_points, 10),
            "status": "ready" if execution_reasons else "insufficient_execution_evidence",
            "reasons": execution_reasons,
            "evidence": {
                "source": top_execution.get("source"),
                "action": top_execution.get("action"),
                "status": top_execution.get("status"),
                "sample_count": int(execution_sample_count),
                "feasible_rate": round(feasible_rate, 6),
                "readback_count": int(readback_count),
            },
            "review_only": True,
            "simulation_only": True,
        }

        factors = [stable_factor, family_factor, reclaim_factor, execution_factor]
        total_score = sum(int(factor.get("score_points") or 0) for factor in factors)
        if total_score >= 75:
            tier = "high_review_priority"
            next_action = "Prepare manual review and dry-run plan; still require trading-time risk gates and sim-cockpit verification."
        elif total_score >= 55:
            tier = "simulation_review_candidate"
            next_action = "Keep in simulation review queue and wait for fresh confirmation before any dry-run."
        elif total_score >= 35:
            tier = "watch_for_confirmation"
            next_action = "Watch for reclaim/support confirmation and collect more offhour or readback evidence."
        else:
            tier = "insufficient_evidence_or_observe"
            next_action = "Collect more replay, rule-family, and sim-cockpit readback evidence before raising priority."
        return {
            "schema_version": "candidate_review_priority_framework.v1",
            "status": "ready" if total_score > 0 else "empty",
            "policy": "stable_candidate_plus_rule_family_plus_reclaim_review",
            "review_priority_score": min(total_score, 100),
            "review_priority_tier": tier,
            "factors": factors,
            "ranked_review_factors": sorted(
                factors,
                key=lambda item: (-int(item.get("score_points") or 0), str(item.get("name") or "")),
            ),
            "next_action": next_action,
            "allowed_effect": "review_priority_only",
            "does_not_change": [
                "production_rules",
                "rules_yaml",
                "broker_or_order_action",
                "position_sizing",
                "risk_gates",
                "live_trading_enabled",
            ],
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _simulation_review_plan(
        self,
        replay: dict[str, Any],
        signal_optimization: dict[str, Any],
        candidate_review_priority: dict[str, Any],
    ) -> dict[str, Any]:
        """Build a review-only next-session simulation plan from learned filters."""
        shadow = signal_optimization.get("shadow_parameter_evidence") or {}
        expanded = shadow.get("expanded_history_review") or {}
        phase_context = expanded.get("phase_context_split") or {}
        filter_experiments = phase_context.get("filter_experiments") or {}
        strategy_comparison = filter_experiments.get("strategy_comparison") or {}
        priority_rows = (
            strategy_comparison.get("top_review_priorities")
            or strategy_comparison.get("top_review_priority")
            or []
        )[:SIM_REVIEW_PLAN_MAX_STRATEGY_OVERLAYS]
        experiment_items = {
            str(item.get("experiment_id") or ""): item
            for item in (filter_experiments.get("items") or [])
            if item.get("experiment_id")
        }
        selected_params = (
            signal_optimization.get("selected_stable_candidate") or {}
        ).get("parameters") or {}

        source_signals = [
            signal
            for signal in (replay.get("recent_signals") or replay.get("signals") or [])
            if signal.get("action_label") in SIGNAL_BACKTEST_ACTIONS
        ]
        latest_signal_date = max((str(signal.get("signal_date") or "") for signal in source_signals), default="")
        data_lag_days = self._calendar_lag_days(latest_signal_date)
        freshness_status = (
            "fresh_enough_for_next_session_review"
            if data_lag_days is not None and data_lag_days <= SIM_REVIEW_PLAN_DATA_FRESHNESS_MAX_DAYS
            else "stale_data_blocks_simulation_plan"
            if data_lag_days is not None
            else "missing_signal_date_blocks_simulation_plan"
        )
        data_fresh = freshness_status == "fresh_enough_for_next_session_review"

        strategy_overlays: list[dict[str, Any]] = []
        for rank, row in enumerate(priority_rows, start=1):
            experiment_id = str(row.get("experiment_id") or "")
            experiment = experiment_items.get(experiment_id) or {}
            params = experiment.get("parameters") or selected_params
            metrics = row.get("metrics") or experiment.get("metrics") or {}
            strategy_overlays.append(
                {
                    "rank": rank,
                    "experiment_id": experiment_id,
                    "tier": row.get("tier"),
                    "review_priority_score": row.get("review_priority_score"),
                    "prefilter": experiment.get("prefilter", "none"),
                    "parameters": params,
                    "metrics": {
                        "trade_count": metrics.get("trade_count"),
                        "win_rate": metrics.get("win_rate"),
                        "average_return_pct": metrics.get("average_return_pct"),
                        "equal_weight_cumulative_return_pct": metrics.get("equal_weight_cumulative_return_pct"),
                    },
                    "walk_forward_status": row.get("walk_forward_status")
                    or (experiment.get("walk_forward") or {}).get("status"),
                    "market_context_status": row.get("market_context_status")
                    or (experiment.get("market_context") or {}).get("status"),
                    "next_entry_confirmation": str(params.get("confirmation_filter") or "none"),
                    "allowed_effect": "ranking_and_dry_run_review_only",
                    "review_only": True,
                    "simulation_only": True,
                }
            )

        candidate_by_symbol: dict[str, dict[str, Any]] = {}
        ordered_signals = sorted(
            source_signals,
            key=lambda item: (
                str(item.get("signal_date") or ""),
                float(item.get("score") or 0),
                str(item.get("symbol") or ""),
            ),
            reverse=True,
        )
        for signal in ordered_signals:
            symbol = str(signal.get("symbol") or "")
            if not symbol:
                continue
            matched = self._matched_strategy_overlays(signal, strategy_overlays)
            if not matched:
                continue
            blockers: list[str] = []
            caution_flags: list[str] = []
            signal_lag_days = self._calendar_lag_days(str(signal.get("signal_date") or ""))
            if not data_fresh:
                blockers.append(freshness_status)
            if signal_lag_days is None:
                blockers.append("missing_signal_date_blocks_simulation_plan")
            elif signal_lag_days > SIM_REVIEW_PLAN_DATA_FRESHNESS_MAX_DAYS:
                blockers.append("signal_stale_for_next_session_review")
            if self._has_dataset1_distribution_risk(signal):
                blockers.append("dataset1_distribution_or_stall_risk")
            if self._is_high_volatility_board_signal(signal):
                caution_flags.append("high_volatility_board_requires_smaller_probe")
            if str(signal.get("risk_level") or "").lower() in {"high", "medium_high", "medium_to_high"}:
                caution_flags.append("dataset2_high_risk_level")

            best_overlay = matched[0]
            params = best_overlay.get("parameters") or {}
            ratio_value = (
                params.get("wait_position_ratio")
                if signal.get("action_label") == "WAIT_CONFIRMATION"
                else params.get("buy_position_ratio")
            )
            base_ratio = float(ratio_value or 0.0)
            initial_ratio = min(
                SIM_REVIEW_PLAN_MAX_INITIAL_POSITION_RATIO,
                max(0.0, base_ratio),
            )
            confirmed_ratio = min(
                SIM_REVIEW_PLAN_MAX_CONFIRMED_POSITION_RATIO,
                max(initial_ratio, float(params.get("buy_position_ratio") or initial_ratio)),
            )
            if "high_volatility_board_requires_smaller_probe" in caution_flags:
                initial_ratio = min(initial_ratio, SIM_REVIEW_PLAN_MAX_INITIAL_POSITION_RATIO / 2)
                confirmed_ratio = min(confirmed_ratio, SIM_REVIEW_PLAN_MAX_CONFIRMED_POSITION_RATIO / 2)
            evidence_quality = self._simulation_candidate_evidence_quality(
                signal=signal,
                best_overlay=best_overlay,
                blockers=blockers,
                caution_flags=caution_flags,
                signal_lag_days=signal_lag_days,
            )
            recency_bonus = (
                max(0, SIM_REVIEW_PLAN_DATA_FRESHNESS_MAX_DAYS - signal_lag_days) * 0.5
                if signal_lag_days is not None
                else 0.0
            )
            priority_score = round(
                float(best_overlay.get("review_priority_score") or 0)
                + float(signal.get("score") or 0) * 10
                + recency_bonus
                - len(caution_flags) * 3
                - len(blockers) * 20,
                6,
            )
            confidence_adjusted_priority_score = round(
                priority_score * (float(evidence_quality.get("confidence_score") or 0.0) / 100.0),
                6,
            )
            recommended_mode = "observe_only" if blockers else "dry_run_screen_candidate"
            candidate = {
                "symbol": symbol,
                "signal_date": signal.get("signal_date"),
                "pattern_id": signal.get("pattern_id"),
                "pattern_name": signal.get("pattern_name"),
                "action_label": signal.get("action_label"),
                "risk_level": signal.get("risk_level"),
                "signal_score": signal.get("score"),
                "signal_lag_days": signal_lag_days,
                "close": signal.get("close"),
                "pct_change": signal.get("pct_change"),
                "matched_strategy_ids": [item.get("experiment_id") for item in matched],
                "best_strategy": {
                    "experiment_id": best_overlay.get("experiment_id"),
                    "tier": best_overlay.get("tier"),
                    "review_priority_score": best_overlay.get("review_priority_score"),
                    "win_rate": (best_overlay.get("metrics") or {}).get("win_rate"),
                    "average_return_pct": (best_overlay.get("metrics") or {}).get("average_return_pct"),
                    "walk_forward_status": best_overlay.get("walk_forward_status"),
                    "market_context_status": best_overlay.get("market_context_status"),
                },
                "next_session_triggers": self._simulation_plan_triggers(params),
                "recommended_mode": recommended_mode,
                "priority_score": priority_score,
                "confidence_adjusted_priority_score": confidence_adjusted_priority_score,
                "evidence_quality": evidence_quality,
                "position_plan": {
                    "reference_sim_cash": SIM_REVIEW_PLAN_REFERENCE_CASH,
                    "max_initial_position_ratio": round(initial_ratio, 4),
                    "max_initial_cash": round(SIM_REVIEW_PLAN_REFERENCE_CASH * initial_ratio, 2),
                    "max_confirmed_position_ratio": round(confirmed_ratio, 4),
                    "max_confirmed_cash": round(SIM_REVIEW_PLAN_REFERENCE_CASH * confirmed_ratio, 2),
                    "staged_add_policy": "first_probe_only_then_add_after_fill_readback_and_fresh_confirmation",
                    "position_plan_effect": "simulation_review_only_no_order",
                },
                "blockers": blockers,
                "caution_flags": caution_flags,
                "tags": signal.get("tags") or [],
                "matched_tags": signal.get("matched_tags") or [],
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            }
            existing = candidate_by_symbol.get(symbol)
            if not existing or priority_score > float(existing.get("priority_score") or 0):
                candidate_by_symbol[symbol] = candidate

        candidates = sorted(
            candidate_by_symbol.values(),
            key=lambda item: (
                bool(item.get("blockers")),
                -float((item.get("evidence_quality") or {}).get("confidence_score") or 0),
                -float(item.get("confidence_adjusted_priority_score") or 0),
                -float(item.get("priority_score") or 0),
                -self._date_ordinal(str(item.get("signal_date") or "")),
                str(item.get("symbol") or ""),
            ),
        )[:SIM_REVIEW_PLAN_MAX_ITEMS]
        ready_count = sum(1 for item in candidates if item.get("recommended_mode") == "dry_run_screen_candidate")
        status = (
            "ready_for_dry_run_review"
            if ready_count and data_fresh
            else "blocked_by_data_freshness"
            if not data_fresh
            else "empty"
        )
        return {
            "schema_version": "simulation_review_plan.v1",
            "status": status,
            "source": "offhour_research_strategy_comparison",
            "data_freshness": {
                "status": freshness_status,
                "latest_signal_date": latest_signal_date,
                "calendar_lag_days": data_lag_days,
                "max_allowed_lag_days": SIM_REVIEW_PLAN_DATA_FRESHNESS_MAX_DAYS,
            },
            "strategy_overlay_count": len(strategy_overlays),
            "strategy_overlays": strategy_overlays,
            "candidate_count": len(candidates),
            "ready_dry_run_candidate_count": ready_count,
            "candidates": candidates,
            "portfolio_limits": {
                "reference_sim_cash": SIM_REVIEW_PLAN_REFERENCE_CASH,
                "max_initial_position_ratio": SIM_REVIEW_PLAN_MAX_INITIAL_POSITION_RATIO,
                "max_confirmed_position_ratio": SIM_REVIEW_PLAN_MAX_CONFIRMED_POSITION_RATIO,
                "daily_new_buy_limit": 5,
                "single_symbol_new_position_limit": 1,
            },
            "supervisor_notes": [
                "Use this plan to rank simulation candidates, not to place orders.",
                "A candidate still needs fresh trading-time risk gates, Sim-Cockpit window verification, and readback.",
                "Strong backtest evidence can raise review priority but cannot bypass Dataset1 distribution-risk discipline.",
            ],
            "permission_policy": {
                "may_change_rules_yaml": False,
                "may_change_position_size": False,
                "may_enable_screen_click": False,
                "may_submit_order": False,
                "requires_sim_cockpit_verification": True,
                "allowed_modes_before_verification": ["observe", "detect_only", "dry_run_screen"],
                "live_trading_enabled": settings.enable_live_trading,
            },
            "candidate_review_priority": {
                "score": candidate_review_priority.get("review_priority_score"),
                "tier": candidate_review_priority.get("review_priority_tier"),
                "next_action": candidate_review_priority.get("next_action"),
            },
            "allowed_effect": "review_and_dry_run_plan_only",
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _simulation_candidate_evidence_quality(
        self,
        signal: dict[str, Any],
        best_overlay: dict[str, Any],
        blockers: list[str],
        caution_flags: list[str],
        signal_lag_days: int | None,
    ) -> dict[str, Any]:
        """Score whether a candidate's evidence is strong enough for dry-run priority."""
        metrics = best_overlay.get("metrics") or {}
        trade_count = int(metrics.get("trade_count") or 0)
        win_rate = float(metrics.get("win_rate") or 0.0)
        average_return = float(metrics.get("average_return_pct") or 0.0)
        cumulative_return = float(metrics.get("equal_weight_cumulative_return_pct") or 0.0)
        confidence_score = 35.0
        reasons: list[str] = ["base_review_evidence"]
        warnings: list[str] = []

        if best_overlay.get("walk_forward_status") == "passed_for_simulation_review":
            confidence_score += 22.0
            reasons.append("walk_forward_passed")
        else:
            confidence_score -= 12.0
            warnings.append("walk_forward_not_passed")

        if best_overlay.get("market_context_status") == "robust":
            confidence_score += 12.0
            reasons.append("market_context_robust")
        elif best_overlay.get("market_context_status"):
            confidence_score -= 6.0
            warnings.append("market_context_needs_review")

        if trade_count >= MIN_WALK_FORWARD_TRADE_COUNT * MIN_WALK_FORWARD_FOLD_COUNT:
            confidence_score += 10.0
            reasons.append("trade_count_meets_walk_forward_budget")
        elif trade_count >= MIN_WALK_FORWARD_TRADE_COUNT:
            confidence_score += 4.0
            warnings.append("trade_count_below_full_walk_forward_budget")
        else:
            confidence_score -= 8.0
            warnings.append("small_sample_trade_count")

        if win_rate >= MIN_WALK_FORWARD_WIN_RATE:
            confidence_score += 8.0
            reasons.append("win_rate_meets_review_gate")
        else:
            confidence_score -= 6.0
            warnings.append("win_rate_below_review_gate")

        if cumulative_return >= MIN_WALK_FORWARD_CUMULATIVE_RETURN_PCT:
            confidence_score += 6.0
            reasons.append("cumulative_return_above_20_pct_gate")
        else:
            confidence_score -= 8.0
            warnings.append("cumulative_return_below_20_pct_gate")

        if average_return > 0:
            confidence_score += min(8.0, average_return)
            reasons.append("positive_average_return")
        else:
            confidence_score -= 8.0
            warnings.append("non_positive_average_return")

        if str(signal.get("action_label") or "") == "WAIT_CONFIRMATION":
            confidence_score -= 4.0
            warnings.append("wait_confirmation_needs_next_bar")
        if signal_lag_days is None:
            confidence_score -= 12.0
            warnings.append("missing_signal_date")
        elif signal_lag_days <= 2:
            confidence_score += 5.0
            reasons.append("signal_recent")
        elif signal_lag_days > SIM_REVIEW_PLAN_DATA_FRESHNESS_MAX_DAYS:
            confidence_score -= 15.0
            warnings.append("signal_stale")
        else:
            warnings.append("signal_aging")

        if blockers:
            confidence_score -= 30.0
            warnings.extend(f"blocker:{blocker}" for blocker in blockers)
        if caution_flags:
            confidence_score -= min(18.0, 6.0 * len(caution_flags))
            warnings.extend(f"caution:{flag}" for flag in caution_flags)

        confidence_score = round(max(0.0, min(100.0, confidence_score)), 6)
        if blockers:
            tier = "blocked_observe_only"
            next_action = "Do not enter dry-run until blockers clear."
        elif confidence_score >= 80:
            tier = "high_confidence_dry_run_review"
            next_action = "Prioritize for manual review and dry-run screen planning only."
        elif confidence_score >= 60:
            tier = "medium_confidence_dry_run_review"
            next_action = "Keep in dry-run queue; require fresh confirmation before any simulated click."
        elif confidence_score >= 40:
            tier = "low_confidence_watch_only"
            next_action = "Watch for stronger confirmation and collect more samples."
        else:
            tier = "insufficient_evidence_observe_only"
            next_action = "Observe only; do not use for tomorrow's first probe."

        return {
            "schema_version": "simulation_candidate_evidence_quality.v1",
            "confidence_score": confidence_score,
            "confidence_tier": tier,
            "reasons": sorted(set(reasons)),
            "warnings": sorted(set(warnings)),
            "metrics_used": {
                "trade_count": trade_count,
                "win_rate": metrics.get("win_rate"),
                "average_return_pct": metrics.get("average_return_pct"),
                "equal_weight_cumulative_return_pct": metrics.get("equal_weight_cumulative_return_pct"),
                "walk_forward_status": best_overlay.get("walk_forward_status"),
                "market_context_status": best_overlay.get("market_context_status"),
                "signal_lag_days": signal_lag_days,
            },
            "next_action": next_action,
            "allowed_effect": "confidence_ranking_for_review_only",
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _matched_strategy_overlays(
        self,
        signal: dict[str, Any],
        strategy_overlays: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        matched: list[dict[str, Any]] = []
        for overlay in strategy_overlays:
            prefilter = str(overlay.get("prefilter") or "none")
            if signal not in self._shadow_prefilter_signals([signal], prefilter):
                continue
            matched.append(overlay)
        return sorted(
            matched,
            key=lambda item: (
                -float(item.get("review_priority_score") or 0),
                int(item.get("rank") or 99),
                str(item.get("experiment_id") or ""),
            ),
        )

    def _simulation_plan_triggers(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        confirmation = str(params.get("confirmation_filter") or "none")
        triggers = [
            {
                "name": "fresh_risk_gates",
                "description": "Portfolio and symbol risk gates must pass during trading-time review.",
                "required": True,
            },
            {
                "name": "sim_cockpit_readback",
                "description": "Sim-Cockpit must verify simulated account window, anchors, and readback before any click mode.",
                "required": True,
            },
        ]
        if confirmation == "entry_green_above_signal":
            triggers.append(
                {
                    "name": "entry_green_above_signal",
                    "description": "Next entry bar should close at or above signal close and not be a weak red session.",
                    "required": True,
                }
            )
        elif confirmation == "strong_reclaim":
            triggers.append(
                {
                    "name": "strong_reclaim",
                    "description": "Next entry bar should reclaim signal close by at least 1%, avoid a weak gap, and close green.",
                    "required": True,
                }
            )
        elif confirmation.startswith("dataset1_"):
            triggers.append(
                {
                    "name": confirmation,
                    "description": "Dataset1 stabilization discipline must pass: no obvious distribution, no early weak entry.",
                    "required": True,
                }
            )
        else:
            triggers.append(
                {
                    "name": "manual_confirmation",
                    "description": "No strict confirmation filter is attached; require manual review before dry-run.",
                    "required": True,
                }
            )
        return triggers

    def _calendar_lag_days(self, iso_date: str) -> int | None:
        if not iso_date:
            return None
        try:
            parsed = datetime.fromisoformat(iso_date).date()
        except ValueError:
            return None
        return max(0, (datetime.now().date() - parsed).days)

    def _date_ordinal(self, iso_date: str) -> int:
        if not iso_date:
            return 0
        try:
            return datetime.fromisoformat(iso_date).date().toordinal()
        except ValueError:
            return 0

    def _write_model_candidate(
        self,
        source: dict[str, Any],
        dataset1_experience: dict[str, Any],
        replay: dict[str, Any],
        backtest: dict[str, Any],
        signal_backtest: dict[str, Any],
        signal_optimization: dict[str, Any],
        reclaim_watchlist: dict[str, Any],
        reclaim_transition_study: dict[str, Any],
        focus_phase_diagnostics: dict[str, Any],
        phase_similarity_performance: dict[str, Any],
        phase_confidence_walk_forward: dict[str, Any],
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
        recommendations = self._strategy_recommendations(
            replay=replay,
            backtest=backtest,
            signal_backtest=signal_backtest,
            ranked_patterns=ranked_patterns,
        )
        rule_family_memory = self._latest_rule_family_performance_memory()
        rule_family_gate = self._rule_family_review_gate(rule_family_memory)
        candidate_review_priority = self._candidate_review_priority_framework(
            signal_optimization=signal_optimization,
            rule_family_memory=rule_family_memory,
            rule_family_gate=rule_family_gate,
            reclaim_watchlist=reclaim_watchlist,
            reclaim_transition_study=reclaim_transition_study,
        )
        simulation_review_plan = self._simulation_review_plan(
            replay=replay,
            signal_optimization=signal_optimization,
            candidate_review_priority=candidate_review_priority,
        )
        dataset1_strategy_synthesis = dict(dataset1_experience.get("strategy_synthesis") or {})
        dataset1_strategy_synthesis.setdefault("review_only", True)
        dataset1_strategy_synthesis.setdefault("simulation_only", True)
        dataset1_strategy_synthesis.setdefault("live_trading_enabled", settings.enable_live_trading)
        payload = {
            "schema_version": "offhour_model_candidate.v1",
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "artifact_kind": "dataset2_strategy_scorecard",
            "status": "candidate_review_only",
            "source_hash": source["source_hash"],
            "dataset1_experience_constraints": {
                "status": dataset1_experience.get("status"),
                "counts": dataset1_experience.get("counts", {}),
                "anchors": dataset1_experience.get("anchors", {}),
                "constraints": dataset1_experience.get("constraints", []),
                "strategy_synthesis": dataset1_strategy_synthesis,
            },
            "signal_count": replay.get("signal_count", 0),
            "evaluated_count": sandbox.get("evaluated_count", 0),
            "top_patterns": ranked_patterns[:20],
            "strategy_recommendations": recommendations["items"],
            "rule_update_gate": recommendations["rule_update_gate"],
            "simulation_weight_gate": recommendations["simulation_weight_gate"],
            "signal_optimization": {
                "status": signal_optimization.get("status"),
                "optimization_budget": signal_optimization.get("optimization_budget"),
                "gate": signal_optimization.get("gate"),
                "best": signal_optimization.get("best"),
                "best_experience_aligned": signal_optimization.get("best_experience_aligned"),
                "selected_stable_candidate": signal_optimization.get("selected_stable_candidate"),
                "stable_candidate_tracks": signal_optimization.get("stable_candidate_tracks"),
                "track_tradeoff_attribution": signal_optimization.get("track_tradeoff_attribution"),
                "signal_loss_attribution": signal_optimization.get("signal_loss_attribution"),
                "parameter_failure_attribution": signal_optimization.get("parameter_failure_attribution"),
                "shadow_parameter_evidence": signal_optimization.get("shadow_parameter_evidence"),
                "learning_filter_candidates": signal_optimization.get("learning_filter_candidates", [])[:5],
                "walk_forward": signal_optimization.get("walk_forward"),
                "top_candidates": signal_optimization.get("top_candidates", [])[:5],
                "top_experience_aligned_candidates": signal_optimization.get("top_experience_aligned_candidates", [])[:5],
            },
            "rule_family_performance_memory": rule_family_memory,
            "rule_family_review_gate": rule_family_gate,
            "candidate_review_priority_framework": candidate_review_priority,
            "simulation_review_plan": simulation_review_plan,
            "reclaim_watchlist": reclaim_watchlist,
            "reclaim_transition_study": {
                "status": reclaim_transition_study.get("status"),
                "evaluated_count": reclaim_transition_study.get("evaluated_count"),
                "pending_count": reclaim_transition_study.get("pending_count"),
                "primary_horizon_days": reclaim_transition_study.get("primary_horizon_days"),
                "by_status": reclaim_transition_study.get("by_status", {}),
                "risk_tag_attribution": reclaim_transition_study.get("risk_tag_attribution", {}),
                "supervision": reclaim_transition_study.get("supervision", {}),
                "policy": reclaim_transition_study.get("policy", {}),
            },
            "focus_phase_diagnostics": focus_phase_diagnostics,
            "phase_similarity_performance": phase_similarity_performance,
            "phase_confidence_walk_forward": phase_confidence_walk_forward,
            "strategy_synthesis": self._combined_strategy_synthesis(
                dataset1_experience=dataset1_experience,
                signal_backtest=signal_backtest,
                signal_optimization=signal_optimization,
                reclaim_watchlist=reclaim_watchlist,
                reclaim_transition_study=reclaim_transition_study,
                focus_phase_diagnostics=focus_phase_diagnostics,
                phase_similarity_performance=phase_similarity_performance,
                phase_confidence_walk_forward=phase_confidence_walk_forward,
                rule_family_memory=rule_family_memory,
                rule_family_gate=rule_family_gate,
                candidate_review_priority=candidate_review_priority,
                simulation_review_plan=simulation_review_plan,
                sandbox=sandbox,
            ),
            "action_counts": replay.get("action_counts", {}),
            "outcome_counts": sandbox.get("outcome_counts", {}),
            "backtest_metrics": backtest.get("metrics", {}),
            "backtest_budget": backtest.get("backtest_budget", {}),
            "signal_backtest_metrics": signal_backtest.get("metrics", {}),
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
            "rule_update_gate": payload["rule_update_gate"],
            "simulation_weight_gate": payload["simulation_weight_gate"],
            "signal_optimization_gate": (payload["signal_optimization"].get("gate") or {}),
            "rule_family_review_gate": payload["rule_family_review_gate"],
            "candidate_review_priority_framework": payload["candidate_review_priority_framework"],
            "simulation_review_plan": payload["simulation_review_plan"],
            "candidate_only": True,
            "auto_loaded": False,
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _combined_strategy_synthesis(
        self,
        dataset1_experience: dict[str, Any],
        signal_backtest: dict[str, Any],
        signal_optimization: dict[str, Any],
        reclaim_watchlist: dict[str, Any],
        reclaim_transition_study: dict[str, Any],
        focus_phase_diagnostics: dict[str, Any],
        phase_similarity_performance: dict[str, Any],
        phase_confidence_walk_forward: dict[str, Any],
        rule_family_memory: dict[str, Any],
        rule_family_gate: dict[str, Any],
        candidate_review_priority: dict[str, Any],
        simulation_review_plan: dict[str, Any],
        sandbox: dict[str, Any],
    ) -> dict[str, Any]:
        best = signal_optimization.get("best") or {}
        best_experience = signal_optimization.get("best_experience_aligned") or {}
        stable_tracks = signal_optimization.get("stable_candidate_tracks") or {}
        return {
            "schema_version": "strategy_synthesis.v1",
            "external_framework_lessons": [
                {
                    "source": "vectorbt",
                    "lesson": "Use batch parameter experiments and chronological splits before trusting a signal.",
                    "mapped_to": "signal_optimization",
                },
                {
                    "source": "QSTrader",
                    "lesson": "Keep signal generation, portfolio risk, execution, and accounting separate.",
                    "mapped_to": "offhour_research -> simulation planner -> execution model",
                },
                {
                    "source": "Backtrader",
                    "lesson": "Strategy parameters must be explicit and execution assumptions must be modeled.",
                    "mapped_to": "entry delay, horizon, stop, take-profit, confirmation filter",
                },
                {
                    "source": "vn.py",
                    "lesson": "Event-driven state makes later realtime/simulation control safer than monolithic scripts.",
                    "mapped_to": "realtime events, monitoring bridge, sim-cockpit audit",
                },
                {
                    "source": "A-share price-limit research",
                    "lesson": "Limit-up or near-limit moves can contain magnet and next-day profit-taking risk; do not treat them as directly fillable buy signals.",
                    "mapped_to": "limit-status execution blocks, liquidity warnings, weak-open reduction review",
                },
                {
                    "source": "Wyckoff accumulation/distribution",
                    "lesson": "Long bases, tests, markup, and distribution should be modeled as phases before changing simulated priority.",
                    "mapped_to": "phase labels for Sanwei Communication, Gold Mantis, Lucky Film, and similar samples",
                },
            ],
            "dataset1_playbook": (dataset1_experience.get("strategy_synthesis") or {}).get("primary_playbook", []),
            "active_simulation_hypothesis": {
                "summary": "Dataset2 finds volume-price candidates; Dataset1 filters late or unstable entries; only optimized candidates enter simulation review.",
                "best_parameters": best.get("parameters", {}),
                "best_experience_aligned_parameters": best_experience.get("parameters", {}),
                "selected_stable_parameters": (
                    signal_optimization.get("selected_stable_candidate") or {}
                ).get("parameters", {}),
                "stable_candidate_tracks": stable_tracks,
                "track_tradeoff_attribution": signal_optimization.get("track_tradeoff_attribution") or {},
                "signal_loss_attribution": signal_optimization.get("signal_loss_attribution") or {},
                "parameter_failure_attribution": signal_optimization.get("parameter_failure_attribution") or {},
                "shadow_parameter_evidence": signal_optimization.get("shadow_parameter_evidence") or {},
                "learning_filter_candidates": (signal_optimization.get("learning_filter_candidates") or [])[:5],
                "reclaim_watchlist": reclaim_watchlist,
                "reclaim_transition_study": {
                    "status": reclaim_transition_study.get("status"),
                    "evaluated_count": reclaim_transition_study.get("evaluated_count"),
                    "by_status": reclaim_transition_study.get("by_status", {}),
                    "risk_tag_attribution": reclaim_transition_study.get("risk_tag_attribution", {}),
                    "supervision": reclaim_transition_study.get("supervision", {}),
                },
                "focus_phase_diagnostics": focus_phase_diagnostics,
                "phase_similarity_performance": phase_similarity_performance,
                "phase_confidence_walk_forward": phase_confidence_walk_forward,
                "rule_family_performance_memory": rule_family_memory,
                "rule_family_review_gate": rule_family_gate,
                "candidate_review_priority_framework": candidate_review_priority,
                "simulation_review_plan": simulation_review_plan,
                "walk_forward": signal_optimization.get("walk_forward", {}),
                "signal_backtest_metrics": signal_backtest.get("metrics", {}),
                "sandbox_evaluated_count": sandbox.get("evaluated_count", 0),
            },
            "dual_track_guidance": {
                "broad_momentum_candidate": "Use for opportunity discovery and simulation review priority only.",
                "dataset1_stabilized_candidate": "Use as the safer candidate family for reducing early-entry and chase risk.",
                "near_reclaim_watch": "Watch broad-only winners that pulled back near signal price; wait for reclaim before dry-run review.",
                "reclaim_transition_study": "Use next-bar confirmation outcomes to decide whether wider watch bands deserve simulation-only priority.",
                "positioning_rule": "A broad candidate may raise attention, but staged simulated entries still require Dataset1 discipline, risk gates, and readback.",
            },
            "promotion_path": [
                "off-hour replay and signal backtest",
                "chronological 70/30 optimization",
                "simulation-planner review-only weighting",
                "mock or dry-run sim-cockpit execution",
                "readback and Dataset2 sample enrichment",
            ],
            "hard_limits": {
                "writes_rules_yaml": False,
                "auto_apply": False,
                "broker_or_order_action": False,
                "requires_human_review": True,
            },
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _strategy_recommendations(
        self,
        replay: dict[str, Any],
        backtest: dict[str, Any],
        signal_backtest: dict[str, Any],
        ranked_patterns: list[dict[str, Any]],
    ) -> dict[str, Any]:
        action_by_pattern: dict[str, str] = {}
        for signal in replay.get("signals") or []:
            pattern_id = str(signal.get("pattern_id") or "")
            if pattern_id and pattern_id not in action_by_pattern:
                action_by_pattern[pattern_id] = str(signal.get("action_label") or "")

        backtest_metrics = backtest.get("metrics") or {}
        trade_count = int(backtest_metrics.get("trade_count") or 0)
        update_allowed = (
            trade_count > 0
            and backtest.get("status") == "completed"
            and float(backtest_metrics.get("total_return") or 0) > 0
            and float(backtest_metrics.get("max_drawdown") or 0) <= 0.12
        )
        gate_reasons: list[str] = []
        if backtest.get("status") != "completed":
            gate_reasons.append("backtest_not_completed")
        if trade_count <= 0:
            gate_reasons.append("backtest_has_no_executed_trades")
        if float(backtest_metrics.get("total_return") or 0) <= 0:
            gate_reasons.append("backtest_total_return_not_positive")
        if float(backtest_metrics.get("max_drawdown") or 0) > 0.12:
            gate_reasons.append("backtest_drawdown_above_review_threshold")

        signal_metrics = signal_backtest.get("metrics") or {}
        signal_trade_count = int(signal_metrics.get("trade_count") or 0)
        signal_win_rate = float(signal_metrics.get("win_rate") or 0)
        signal_avg_return = float(signal_metrics.get("average_return_pct") or 0)
        simulation_allowed = (
            signal_backtest.get("status") == "completed"
            and signal_trade_count >= MIN_SIGNAL_BACKTEST_TRADE_COUNT
            and signal_win_rate >= MIN_SIGNAL_BACKTEST_WIN_RATE
            and signal_avg_return > MIN_SIGNAL_BACKTEST_AVG_RETURN_PCT
        )
        simulation_gate_reasons: list[str] = []
        if signal_backtest.get("status") != "completed":
            simulation_gate_reasons.append("signal_backtest_not_completed")
        if signal_trade_count < MIN_SIGNAL_BACKTEST_TRADE_COUNT:
            simulation_gate_reasons.append("signal_backtest_trade_count_too_low")
        if signal_win_rate < MIN_SIGNAL_BACKTEST_WIN_RATE:
            simulation_gate_reasons.append("signal_backtest_win_rate_too_low")
        if signal_avg_return <= MIN_SIGNAL_BACKTEST_AVG_RETURN_PCT:
            simulation_gate_reasons.append("signal_backtest_average_return_not_positive")

        signal_perf = signal_backtest.get("pattern_performance") or {}
        items: list[dict[str, Any]] = []
        for pattern in ranked_patterns[:20]:
            pattern_id = str(pattern.get("pattern_id") or "")
            sample_count = int(pattern.get("sample_count") or 0)
            win_rate = float(pattern.get("win_rate") or 0)
            avg_return = float(pattern.get("avg_close_return_pct") or 0)
            action_label = action_by_pattern.get(pattern_id, "UNKNOWN")
            eligible = (
                sample_count >= MIN_PROMOTION_SAMPLE_COUNT
                and win_rate >= MIN_PROMOTION_WIN_RATE
                and avg_return >= MIN_PROMOTION_AVG_RETURN_PCT
            )
            if eligible:
                review_action = (
                    "promote_to_simulation_watch_confirmation"
                    if action_label == "WAIT_CONFIRMATION"
                    else "review_for_simulation_weight_increase"
                )
                suggested_weight_delta = min(8.0, round((win_rate - 0.5) * 10 + avg_return / 3, 2))
            else:
                review_action = "collect_more_samples_or_keep_current_weight"
                suggested_weight_delta = 0.0
            signal_item = signal_perf.get(pattern_id) or {}
            signal_confirmed = (
                int(signal_item.get("trade_count") or 0) >= MIN_SIGNAL_BACKTEST_TRADE_COUNT
                and float(signal_item.get("win_rate") or 0) >= MIN_SIGNAL_BACKTEST_WIN_RATE
                and float(signal_item.get("avg_return_pct") or 0) > MIN_SIGNAL_BACKTEST_AVG_RETURN_PCT
            )
            items.append(
                {
                    "pattern_id": pattern_id,
                    "action_label": action_label,
                    "sample_count": sample_count,
                    "win_rate": round(win_rate, 6),
                    "avg_close_return_pct": round(avg_return, 6),
                    "eligible_for_candidate_weight_increase": eligible,
                    "eligible_for_simulation_plan_weight_increase": eligible and signal_confirmed,
                    "suggested_weight_delta": suggested_weight_delta,
                    "review_action": review_action,
                    "requires_backtest_confirmation": True,
                    "signal_backtest": {
                        "trade_count": int(signal_item.get("trade_count") or 0),
                        "win_rate": round(float(signal_item.get("win_rate") or 0), 6),
                        "avg_return_pct": round(float(signal_item.get("avg_return_pct") or 0), 6),
                    },
                    "writes_rules_yaml": False,
                    "auto_apply": False,
                    "simulation_only": True,
                }
            )
        return {
            "rule_update_gate": {
                "status": "passed_for_review" if update_allowed else "blocked",
                "reasons": gate_reasons,
                "requires_human_review": True,
                "writes_rules_yaml": False,
                "auto_apply": False,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            },
            "simulation_weight_gate": {
                "status": "passed_for_simulation_review" if simulation_allowed else "blocked",
                "reasons": simulation_gate_reasons,
                "requires_human_review": True,
                "writes_rules_yaml": False,
                "auto_apply": False,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            },
            "items": items,
        }

    def _next_action(
        self,
        status: str,
        replay: dict[str, Any],
        signal_backtest: dict[str, Any],
        sandbox: dict[str, Any],
        artifact: dict[str, Any],
        coverage: dict[str, Any],
        reclaim_watchlist: dict[str, Any] | None = None,
        reclaim_transition_study: dict[str, Any] | None = None,
    ) -> str:
        if status == "blocked" and coverage.get("status") == "insufficient_history_data":
            return "Refresh daily_bar_cache for more candidate symbols, then rerun offhour research loop."
        if replay.get("signal_count", 0) == 0:
            return "Broaden Dataset2 tag mapping or collect more daily history before candidate artifact review."
        if (signal_backtest.get("metrics") or {}).get("trade_count", 0) == 0:
            return "Dataset2 replay found signals, but the signal backtest produced no closed trades; inspect execution/liquidity constraints before changing weights."
        if sandbox.get("evaluated_count", 0) < 3:
            return "Collect more future bars for replayed signals before trusting pattern performance."
        artifact_payload = artifact if isinstance(artifact, dict) else {}
        reclaim_payload = reclaim_watchlist if isinstance(reclaim_watchlist, dict) else {}
        reclaim_counts = reclaim_payload.get("counts") or {}
        if int(reclaim_counts.get("reclaim_review") or 0) > 0:
            return "Reclaim-review candidates exist; use trading-time risk gates and dry-run evidence only before any simulated cockpit action."
        if int(reclaim_counts.get("near_reclaim_watch") or 0) > 0:
            return "Near-reclaim candidates exist; watch for a fresh close or verified intraday reclaim of signal price before dry-run simulation review."
        if int(reclaim_counts.get("pending_future_data") or 0) > 0:
            return "Recent Dataset2 signals are waiting for the next ready bar; rerun after the next trading session to classify near-reclaim, reclaim-review, or failed-markup risk."
        transition_payload = reclaim_transition_study if isinstance(reclaim_transition_study, dict) else {}
        transition_supervision = transition_payload.get("supervision") or {}
        transition_recommendations = transition_supervision.get("recommendations") or []
        if transition_payload.get("status") == "completed" and transition_recommendations:
            return (
                "Use reclaim transition study as simulation-only evidence: "
                f"{transition_recommendations[0]}"
            )
        if artifact_payload.get("signal_optimization_gate", {}).get("status") == "passed_for_simulation_review":
            return "Optimized Dataset2 parameters cleared the 20% validation-return review gate; review for simulation-planner weighting only, not production rules."
        if artifact_payload.get("simulation_weight_gate", {}).get("status") == "passed_for_simulation_review":
            return "Review eligible Dataset2 pattern as a simulation-planner weight candidate; do not update production rules until the rule-engine backtest also passes."
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
            "dataset1_experience": self.experience_adapter.summary(),
            "strategy_replay": {"status": "blocked", "signal_count": 0, "signals": []},
            "backtest": {"status": "skipped"},
            "signal_backtest": {"status": "skipped", "metrics": {"trade_count": 0}},
            "signal_optimization": {"status": "skipped"},
            "reclaim_watchlist": {"status": "skipped", "items": [], "counts": {}},
            "reclaim_transition_study": {"status": "skipped", "items": [], "by_status": {}},
            "focus_phase_diagnostics": {"status": "skipped", "targets": [], "counts": {}},
            "phase_similarity_performance": {
                "status": "skipped",
                "evaluated_count": 0,
                "matched_count": 0,
                "missing_match_count": 0,
                "by_group": [],
                "items": [],
            },
            "phase_confidence_walk_forward": self._phase_confidence_walk_forward_skipped("blocked_research_run"),
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
            "signal_backtest_trade_count": ((result.get("signal_backtest") or {}).get("metrics") or {}).get("trade_count", 0),
            "signal_optimization_status": (result.get("signal_optimization") or {}).get("status"),
            "signal_optimization_gate": ((result.get("signal_optimization") or {}).get("gate") or {}).get("status"),
            "reclaim_watch_status": (result.get("reclaim_watchlist") or {}).get("status"),
            "reclaim_watch_active_count": (result.get("reclaim_watchlist") or {}).get("active_watch_count", 0),
            "reclaim_transition_status": (result.get("reclaim_transition_study") or {}).get("status"),
            "reclaim_transition_evaluated_count": (result.get("reclaim_transition_study") or {}).get("evaluated_count", 0),
            "focus_phase_status": (result.get("focus_phase_diagnostics") or {}).get("status"),
            "focus_phase_counts": (result.get("focus_phase_diagnostics") or {}).get("counts", {}),
            "phase_similarity_performance_status": (result.get("phase_similarity_performance") or {}).get("status"),
            "phase_similarity_matched_count": (result.get("phase_similarity_performance") or {}).get("matched_count", 0),
            "benchmark_history_status": (result.get("benchmark_history") or {}).get("status"),
            "phase_confidence_walk_forward_status": (result.get("phase_confidence_walk_forward") or {}).get("status"),
            "phase_confidence_walk_forward_passed_count": (result.get("phase_confidence_walk_forward") or {}).get("passed_group_count", 0),
            "dataset1_experience_status": (result.get("dataset1_experience") or {}).get("status"),
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
                    _json_dumps(
                        {
                            **(result.get("strategy_replay") or {}),
                            "dataset1_experience": result.get("dataset1_experience") or {},
                        }
                    ),
                    _json_dumps(
                        {
                            **(result.get("backtest") or {}),
                            "dataset2_signal_backtest": result.get("signal_backtest") or {},
                            "dataset2_signal_optimization": result.get("signal_optimization") or {},
                            "dataset2_reclaim_watchlist": result.get("reclaim_watchlist") or {},
                            "dataset2_reclaim_transition_study": result.get("reclaim_transition_study") or {},
                            "focus_phase_diagnostics": result.get("focus_phase_diagnostics") or {},
                            "phase_similarity_performance": result.get("phase_similarity_performance") or {},
                            "benchmark_history": result.get("benchmark_history") or {},
                            "phase_confidence_walk_forward": result.get("phase_confidence_walk_forward") or {},
                        }
                    ),
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
            "dataset1_experience": _json_loads(row.get("strategy_replay_json"), {}).get("dataset1_experience", {}),
            "backtest": _json_loads(row.get("backtest_json"), {}),
            "signal_backtest": _json_loads(row.get("backtest_json"), {}).get("dataset2_signal_backtest", {}),
            "signal_optimization": _json_loads(row.get("backtest_json"), {}).get("dataset2_signal_optimization", {}),
            "reclaim_watchlist": _json_loads(row.get("backtest_json"), {}).get("dataset2_reclaim_watchlist", {}),
            "reclaim_transition_study": _json_loads(row.get("backtest_json"), {}).get("dataset2_reclaim_transition_study", {}),
            "focus_phase_diagnostics": _json_loads(row.get("backtest_json"), {}).get("focus_phase_diagnostics", {}),
            "phase_similarity_performance": _json_loads(row.get("backtest_json"), {}).get("phase_similarity_performance", {}),
            "benchmark_history": _json_loads(row.get("backtest_json"), {}).get("benchmark_history", {}),
            "phase_confidence_walk_forward": _json_loads(row.get("backtest_json"), {}).get("phase_confidence_walk_forward", {}),
            "sandbox": _json_loads(row.get("sandbox_json"), {}),
            "model_candidate": _json_loads(row.get("artifact_json"), {}),
            "next_action": row.get("next_action"),
            "review_only": bool(row.get("review_only")),
            "simulation_only": bool(row.get("simulation_only")),
            "live_trading_enabled": bool(row.get("live_trading_enabled")),
            "created_at": row.get("created_at"),
            "completed_at": row.get("completed_at"),
        }
