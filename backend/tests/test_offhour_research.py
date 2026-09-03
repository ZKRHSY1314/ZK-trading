import json
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from app.data.daily_bar_cache import DailyBarCacheService
from app.learning.phase_replay import MainForcePhaseReplayService
from app.research import offhour
from app.research.offhour import OffhourResearchLoopService


def recent_date(days_ago: int = 1) -> str:
    return (datetime.now().date() - timedelta(days=days_ago)).isoformat()


def recent_timestamp(days_ago: int = 1) -> str:
    return (datetime.now() - timedelta(days=days_ago)).isoformat(sep=" ", timespec="seconds")


class FakePotentialSearch:
    def __init__(self, symbols=None):
        self.symbols = symbols or ["SH600000"]

    def run(self, limit=100, persist=True):
        return {
            "run_id": 7,
            "status": "completed",
            "total_scanned": len(self.symbols),
            "stored_count": len(self.symbols),
            "scored_count": len(self.symbols),
            "top_scored_symbols": self.symbols,
            "top_scored_items": [
                {"symbol": symbol, "name": f"Fixture {idx}", "potential_score": 80 - idx}
                for idx, symbol in enumerate(self.symbols)
            ],
            "errors": [],
        }


@pytest.fixture
def clean_store(test_db):
    with test_db.connect() as conn:
        for table in [
            "offhour_research_runs",
            "historical_backtest_trades",
            "historical_backtest_closed_trades",
            "historical_backtest_daily_equity",
            "historical_backtest_runs",
            "daily_bar_cache",
            "sim_cockpit_readbacks",
            "sim_cockpit_actions",
            "main_force_phase_replays",
            "main_force_phase_matches",
        ]:
            conn.execute(f"DELETE FROM {table}")
    return test_db


def write_dataset2_source(tmp_path: Path, mode="simulation_and_training_only", allow_live_order=False) -> Path:
    source_dir = (
        tmp_path
        / "\u6570\u636e\u96c62"
        / "a_share_trading_training_pack_v2"
        / "a_share_trading_training_pack_v2"
    )
    strategies_dir = source_dir / "strategies"
    strategies_dir.mkdir(parents=True)
    strategy_set = {
        "mode": mode,
        "rules": [
            {
                "pattern_id": "TEST_BIG_YANG_001",
                "name": "big yang high volume",
                "category": "fixture_volume_price",
                "timeframe": "daily",
                "conditions": {
                    "software_tags": [
                        "single_candle",
                        "big_yang",
                        "high_volume",
                        "price_volume_rise",
                    ]
                },
                "outputs": {
                    "expected_bias": "bullish",
                    "action_label": "SIM_BUY_CANDIDATE",
                    "risk_level": "medium",
                    "confidence": "medium",
                    "allow_live_order": allow_live_order,
                },
            }
        ],
    }
    risk_controls = {
        "version": "fixture",
        "action_label_map": {"SIM_BUY_CANDIDATE": "simulation only"},
    }
    (strategies_dir / "strategy_set.json").write_text(
        json.dumps(strategy_set, ensure_ascii=False),
        encoding="utf-8",
    )
    (strategies_dir / "risk_controls.json").write_text(
        json.dumps(risk_controls, ensure_ascii=False),
        encoding="utf-8",
    )
    return source_dir


def insert_bar(store, symbol, trade_date, open_, high, low, close, volume=1000, amount=1000000):
    with store.connect() as conn:
        conn.execute(
            """
            INSERT INTO daily_bar_cache(
                symbol, trade_date, open, high, low, close, volume, amount, source, quality_status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (symbol, trade_date, open_, high, low, close, volume, amount, "fixture", "ready"),
        )


def seed_signal_history(store):
    day5 = recent_date(5)
    day4 = recent_date(4)
    day3 = recent_date(3)
    day2 = recent_date(2)
    day1 = recent_date(1)
    bars = [
        (day5, 10.0, 10.1, 9.9, 10.0, 1000, 10_000_000),
        (day4, 10.0, 10.2, 9.9, 10.1, 1000, 10_100_000),
        (day3, 10.0, 11.2, 9.9, 11.0, 4000, 220_000_000),
        (day2, 11.0, 11.8, 10.8, 11.6, 2500, 180_000_000),
        (day1, 11.5, 12.0, 11.3, 11.8, 2300, 170_000_000),
    ]
    for date, open_, high, low, close, volume, amount in bars:
        insert_bar(store, "SH600000", date, open_, high, low, close, volume=volume, amount=amount)
        insert_bar(store, "SH000300", date, 100, 101, 99, 100 + len(date), volume=10000, amount=300_000_000)


def insert_phase_replay(store, symbol, name, latest_phase="post_distribution_watch"):
    summary = {
        "symbol": symbol,
        "name": name,
        "start_date": "2025-01-01",
        "end_date": recent_date(1),
        "bars_count": 240,
        "latest_phase": latest_phase,
        "latest_phase_name": "出货后观察" if latest_phase == "post_distribution_watch" else "拉升",
        "latest_close": 10.0,
        "period_return_pct": 120.0,
        "segment_count": 3,
        "phase_path": ["accumulation", "test_pull", "markup", latest_phase],
        "diagnosis": f"{name} fixture phase diagnosis",
        "training_questions": ["如何识别吸筹？", "如何避免派发后追高？"],
    }
    segments = [
        {"phase": "accumulation", "phase_name": "吸筹/整理", "start_date": "2025-01-01", "end_date": "2025-03-01", "bars": 40},
        {"phase": "test_pull", "phase_name": "试盘", "start_date": "2025-03-02", "end_date": "2025-04-01", "bars": 20},
        {"phase": "markup", "phase_name": "拉升", "start_date": "2025-04-02", "end_date": "2025-05-01", "bars": 20},
        {"phase": latest_phase, "phase_name": summary["latest_phase_name"], "start_date": "2025-05-02", "end_date": recent_date(1), "bars": 160},
    ]
    with store.connect() as conn:
        conn.execute(
            """
            INSERT INTO main_force_phase_replays(
                symbol, name, lookback_years, data_source, bars_count, latest_phase,
                summary_json, segments_json, features_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                symbol,
                name,
                3.0,
                "fixture",
                240,
                latest_phase,
                json.dumps(summary, ensure_ascii=False),
                json.dumps(segments, ensure_ascii=False),
                "{}",
                recent_timestamp(),
            ),
        )


def insert_phase_match(
    store,
    target_symbol,
    core_symbol="SZ002115",
    target_latest_phase="markup",
    sample_role="三维通信成功拉升样本",
    score=81.5,
):
    summary = {
        "target_symbol": target_symbol,
        "target_latest_phase": target_latest_phase,
        "target_latest_phase_name": "拉升" if target_latest_phase == "markup" else "出货后观察",
        "best_match": {
            "core_symbol": core_symbol,
            "sample_role": sample_role,
            "score": score,
        },
        "review_only": True,
        "simulation_only": True,
    }
    matches = [
        {
            "core_symbol": core_symbol,
            "sample_role": sample_role,
            "score": score,
            "review_only": True,
            "simulation_only": True,
        }
    ]
    with store.connect() as conn:
        conn.execute(
            """
            INSERT INTO main_force_phase_matches(
                target_symbol, target_name, target_replay_id, summary_json, matches_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                target_symbol,
                f"Fixture {target_symbol}",
                None,
                json.dumps(summary, ensure_ascii=False),
                json.dumps(matches, ensure_ascii=False),
                recent_timestamp(),
            ),
        )


def stable_candidate(confirmation_filter, validation_return=30.0, total_return=80.0):
    return {
        "status": "passed_for_simulation_review",
        "score": total_return,
        "parameters": {
            "entry_delay_days": 1,
            "horizon_days": 3,
            "stop_loss_pct": 0.04,
            "take_profit_pct": 0.08,
            "confirmation_filter": confirmation_filter,
        },
        "source_validation_metrics": {
            "trade_count": 5,
            "win_rate": 0.8,
            "average_return_pct": 3.0,
            "equal_weight_cumulative_return_pct": validation_return,
        },
        "source_train_metrics": {"trade_count": 10},
        "fold_count": 4,
        "trade_count": 20,
        "min_fold_trade_count": 4,
        "weighted_win_rate": 0.7,
        "weighted_average_return_pct": 2.5,
        "total_equal_weight_cumulative_return_pct": total_return,
        "min_fold_win_rate": 0.5,
        "min_fold_cumulative_return_pct": 5.0,
        "review_only": True,
        "simulation_only": True,
    }


def test_stable_candidate_tracks_separate_broad_and_dataset1_stabilized(clean_store, tmp_path):
    service = OffhourResearchLoopService(
        dataset2_source_dir=write_dataset2_source(tmp_path),
        artifact_dir=tmp_path / "output" / "model_candidates",
    )

    tracks = service._stable_candidate_tracks(
        [
            stable_candidate("none", validation_return=99.0, total_return=200.0),
            stable_candidate("entry_close_above_signal", validation_return=23.0, total_return=100.0),
        ]
    )

    assert tracks["schema_version"] == "stable_candidate_tracks.v1"
    broad = tracks["broad_momentum_candidate"]
    stabilized = tracks["dataset1_stabilized_candidate"]
    assert broad["status"] == "passed_for_simulation_review"
    assert broad["candidate"]["parameters"]["confirmation_filter"] == "none"
    assert stabilized["status"] == "passed_for_simulation_review"
    assert stabilized["candidate"]["parameters"]["confirmation_filter"] == "entry_close_above_signal"


def test_focus_phase_diagnostics_use_stored_replays_only(clean_store, tmp_path):
    insert_phase_replay(clean_store, "SZ002115", "三维通信")
    insert_phase_replay(clean_store, "SZ002081", "金螳螂")
    insert_phase_replay(clean_store, "SH600135", "乐凯胶片")
    service = OffhourResearchLoopService(
        dataset2_source_dir=write_dataset2_source(tmp_path),
        artifact_dir=tmp_path / "output" / "model_candidates",
    )

    diagnostics = service._focus_phase_diagnostics()

    assert diagnostics["schema_version"] == "focus_phase_diagnostics.v1"
    assert diagnostics["status"] == "completed"
    assert diagnostics["policy"]["fetches_external_history"] is False
    assert diagnostics["policy"]["writes_rules_yaml"] is False
    by_symbol = {item["symbol"]: item for item in diagnostics["targets"]}
    assert set(by_symbol) == {"SZ002115", "SZ002081", "SH600135"}
    assert by_symbol["SZ002081"]["role"] == "completed_markup_distribution_training_sample"
    assert by_symbol["SZ002081"]["current_training_use"] == "training_or_observe_only_no_new_entry_priority"
    assert by_symbol["SZ002115"]["dataset1_anchor"]
    assert by_symbol["SH600135"]["supervision_policy"] == "require_stabilization_and_execution_discipline"
    assert all(item["review_only"] and item["simulation_only"] for item in diagnostics["targets"])
    assert diagnostics["review_only"] is True
    assert diagnostics["simulation_only"] is True
    assert diagnostics["live_trading_enabled"] is False


def test_phase_similarity_performance_stratifies_sandbox_outcomes(clean_store, tmp_path):
    insert_phase_match(
        clean_store,
        "SH600000",
        core_symbol="SZ002115",
        target_latest_phase="markup",
        sample_role="三维通信成功拉升样本",
        score=88.0,
    )
    insert_phase_match(
        clean_store,
        "SZ000001",
        core_symbol="SZ002081",
        target_latest_phase="post_distribution_watch",
        sample_role="金螳螂拉升出货完成样本",
        score=82.0,
    )
    service = OffhourResearchLoopService(
        dataset2_source_dir=write_dataset2_source(tmp_path),
        artifact_dir=tmp_path / "output" / "model_candidates",
    )

    result = service._phase_similarity_performance(
        replay={"signals": []},
        sandbox={
            "evaluated_count": 3,
            "evaluations": [
                {
                    "status": "completed",
                    "symbol": "SH600000",
                    "signal_date": "2026-05-03",
                    "pattern_id": "TEST_BIG_YANG_001",
                    "outcome_label": "strong_follow_through",
                    "close_return_pct": 8.5,
                    "max_return_pct": 12.0,
                    "min_return_pct": -1.0,
                },
                {
                    "status": "completed",
                    "symbol": "SZ000001",
                    "signal_date": "2026-05-04",
                    "pattern_id": "TEST_BIG_YANG_001",
                    "outcome_label": "failed_follow_through",
                    "close_return_pct": -3.0,
                    "max_return_pct": 1.0,
                    "min_return_pct": -5.0,
                },
                {
                    "status": "completed",
                    "symbol": "SH600001",
                    "signal_date": "2026-05-05",
                    "pattern_id": "TEST_BIG_YANG_001",
                    "outcome_label": "mild_follow_through",
                    "close_return_pct": 2.0,
                    "max_return_pct": 3.0,
                    "min_return_pct": -1.0,
                },
            ],
        },
    )

    assert result["schema_version"] == "phase_similarity_performance.v1"
    assert result["status"] == "completed"
    assert result["evaluated_count"] == 3
    assert result["matched_count"] == 2
    assert result["missing_match_count"] == 1
    groups = {group["key"]: group for group in result["by_group"]}
    assert groups["SZ002115:markup"]["suggested_treatment"] == "raise_review_priority_dry_run_only"
    assert groups["SZ002115:markup"]["confidence_tier"] == "low_confidence_collect_more_samples"
    assert "small_sample_count<5" in groups["SZ002115:markup"]["confidence_reasons"]
    assert groups["SZ002081:post_distribution_watch"]["suggested_treatment"] == "observe_only_distribution_risk"
    assert groups["SZ002081:post_distribution_watch"]["confidence_tier"] == "observe_only_distribution_risk_confidence"
    assert groups["SZ002081:post_distribution_watch"]["confidence_score"] <= 45
    assert result["policy"]["fetches_external_history"] is False
    assert result["policy"]["writes_rules_yaml"] is False
    assert result["live_trading_enabled"] is False


def test_phase_similarity_confidence_tier_is_review_only_and_downside_aware(clean_store, tmp_path):
    service = OffhourResearchLoopService(
        dataset2_source_dir=write_dataset2_source(tmp_path),
        artifact_dir=tmp_path / "output" / "model_candidates",
    )

    high_confidence = service._phase_similarity_confidence(
        {
            "sample_count": 8,
            "win_rate": 0.875,
            "average_close_return_pct": 5.4,
            "average_min_return_pct": -1.2,
            "best_score": 84.0,
            "suggested_treatment": "raise_review_priority_dry_run_only",
            "target_latest_phase": "markup",
        }
    )
    assert high_confidence["tier"] == "high_review_confidence_dry_run_only"
    assert high_confidence["score"] >= 70
    assert "avg_min_drawdown>=-2%" in high_confidence["reasons"]

    deep_downside = service._phase_similarity_confidence(
        {
            "sample_count": 12,
            "win_rate": 0.75,
            "average_close_return_pct": 5.2,
            "average_min_return_pct": -8.5,
            "best_score": 82.0,
            "suggested_treatment": "raise_review_priority_dry_run_only",
            "target_latest_phase": "markup",
        }
    )
    assert deep_downside["tier"] != "high_review_confidence_dry_run_only"
    assert "deep" in deep_downside["downside_risk_note"]

    distribution = service._phase_similarity_confidence(
        {
            "sample_count": 20,
            "win_rate": 1.0,
            "average_close_return_pct": 6.0,
            "average_min_return_pct": -1.0,
            "best_score": 90.0,
            "suggested_treatment": "observe_only_distribution_risk",
            "target_latest_phase": "post_distribution_watch",
        }
    )
    assert distribution["tier"] == "observe_only_distribution_risk_confidence"
    assert distribution["score"] <= 45
    assert "distribution_path_caps_confidence" in distribution["reasons"]


def test_phase_confidence_walk_forward_validates_high_confidence_groups(clean_store, tmp_path):
    service = OffhourResearchLoopService(
        dataset2_source_dir=write_dataset2_source(tmp_path),
        artifact_dir=tmp_path / "output" / "model_candidates",
    )
    for idx, date in enumerate(
        [
            "2025-12-27",
            "2025-12-28",
            "2025-12-29",
            "2025-12-30",
            "2025-12-31",
            "2026-01-01",
            "2026-01-02",
            "2026-01-03",
            "2026-01-04",
            "2026-01-05",
            "2026-01-06",
        ]
    ):
        close = 100.0 + idx
        insert_bar(clean_store, "SH000300", date, close, close + 1, close - 1, close)
    performance = {
        "by_group": [
            {
                "key": "SZ002115:markup",
                "confidence_tier": "high_review_confidence_dry_run_only",
                "confidence_score": 92,
                "suggested_treatment": "raise_review_priority_dry_run_only",
            },
            {
                "key": "SZ002081:markup",
                "confidence_tier": "medium_review_confidence_dry_run_only",
                "confidence_score": 65,
                "suggested_treatment": "review_momentum_but_require_distribution_check",
            },
            {
                "key": "SZ002081:post_distribution_watch",
                "confidence_tier": "observe_only_distribution_risk_confidence",
                "confidence_score": 45,
                "suggested_treatment": "observe_only_distribution_risk",
            },
        ],
        "items": [
            {"group_key": "SZ002115:markup", "symbol": "SH600001", "signal_date": "2026-01-01", "close_return_pct": 4.0},
            {"group_key": "SZ002115:markup", "symbol": "SH600002", "signal_date": "2026-01-02", "close_return_pct": 5.0},
            {"group_key": "SZ002115:markup", "symbol": "SH600003", "signal_date": "2026-01-03", "close_return_pct": 3.0},
            {"group_key": "SZ002115:markup", "symbol": "SH600004", "signal_date": "2026-01-04", "close_return_pct": 6.0},
            {"group_key": "SZ002115:markup", "symbol": "SH600005", "signal_date": "2026-01-05", "close_return_pct": 4.0},
            {"group_key": "SZ002115:markup", "symbol": "SH600006", "signal_date": "2026-01-06", "close_return_pct": 5.0},
            {"group_key": "SZ002081:markup", "symbol": "SZ000001", "signal_date": "2026-01-01", "close_return_pct": 2.0},
            {"group_key": "SZ002081:markup", "symbol": "SZ000002", "signal_date": "2026-01-02", "close_return_pct": -9.0},
            {"group_key": "SZ002081:markup", "symbol": "SZ000003", "signal_date": "2026-01-03", "close_return_pct": 1.0},
            {"group_key": "SZ002081:markup", "symbol": "SZ000004", "signal_date": "2026-01-04", "close_return_pct": -2.0},
            {"group_key": "SZ002081:markup", "symbol": "SZ000005", "signal_date": "2026-01-05", "close_return_pct": 1.0},
            {"group_key": "SZ002081:markup", "symbol": "SZ000006", "signal_date": "2026-01-06", "close_return_pct": -3.0},
            {"group_key": "SZ002081:post_distribution_watch", "symbol": "SZ300001", "signal_date": "2026-01-01", "close_return_pct": 10.0},
        ],
    }

    result = service._phase_confidence_walk_forward(performance)

    assert result["schema_version"] == "phase_confidence_walk_forward.v1"
    assert result["status"] == "passed_for_review"
    assert result["evaluated_group_count"] == 2
    assert result["passed_group_count"] == 1
    groups = {group["group_key"]: group for group in result["groups"]}
    assert groups["SZ002115:markup"]["status"] == "passed_for_review"
    assert groups["SZ002115:markup"]["total_equal_weight_cumulative_return_pct"] >= 20
    assert groups["SZ002115:markup"]["robustness"]["schema_version"] == "phase_confidence_robustness.v1"
    assert groups["SZ002115:markup"]["robustness"]["by_board"][0]["key"] == "main"
    assert groups["SZ002115:markup"]["robustness"]["by_market_regime"][0]["key"] == "benchmark_up"
    assert "single_board_concentration" in groups["SZ002115:markup"]["robustness"]["warnings"]
    assert groups["SZ002081:markup"]["status"] == "blocked"
    assert "phase_confidence_cumulative_return_below_20_pct" in groups["SZ002081:markup"]["gate_reasons"]
    assert result["gate"]["writes_rules_yaml"] is False
    assert result["gate"]["auto_apply"] is False
    assert result["live_trading_enabled"] is False


def test_simulation_candidate_evidence_quality_is_downside_aware(clean_store, tmp_path):
    service = OffhourResearchLoopService(
        dataset2_source_dir=write_dataset2_source(tmp_path),
        artifact_dir=tmp_path / "output" / "model_candidates",
    )

    high_quality = service._simulation_candidate_evidence_quality(
        signal={"action_label": "SIM_BUY_CANDIDATE"},
        best_overlay={
            "walk_forward_status": "passed_for_simulation_review",
            "market_context_status": "robust",
            "metrics": {
                "trade_count": 24,
                "win_rate": 0.75,
                "average_return_pct": 4.5,
                "equal_weight_cumulative_return_pct": 80.0,
            },
        },
        blockers=[],
        caution_flags=[],
        signal_lag_days=1,
    )

    assert high_quality["schema_version"] == "simulation_candidate_evidence_quality.v1"
    assert high_quality["confidence_tier"] == "high_confidence_dry_run_review"
    assert high_quality["confidence_score"] >= 80
    assert "walk_forward_passed" in high_quality["reasons"]
    assert high_quality["review_only"] is True
    assert high_quality["simulation_only"] is True
    assert high_quality["live_trading_enabled"] is False

    blocked = service._simulation_candidate_evidence_quality(
        signal={"action_label": "WAIT_CONFIRMATION"},
        best_overlay={
            "walk_forward_status": "blocked",
            "market_context_status": "needs_review",
            "metrics": {
                "trade_count": 2,
                "win_rate": 0.5,
                "average_return_pct": -1.0,
                "equal_weight_cumulative_return_pct": 4.0,
            },
        },
        blockers=["dataset1_distribution_or_stall_risk"],
        caution_flags=["dataset2_high_risk_level"],
        signal_lag_days=9,
    )

    assert blocked["confidence_tier"] == "blocked_observe_only"
    assert blocked["confidence_score"] < high_quality["confidence_score"]
    assert "blocker:dataset1_distribution_or_stall_risk" in blocked["warnings"]
    assert blocked["allowed_effect"] == "confidence_ranking_for_review_only"


def test_simulation_review_plan_adds_evidence_quality_to_candidates(clean_store, tmp_path):
    service = OffhourResearchLoopService(
        dataset2_source_dir=write_dataset2_source(tmp_path),
        artifact_dir=tmp_path / "output" / "model_candidates",
    )

    plan = service._simulation_review_plan(
        replay={
            "recent_signals": [
                {
                    "symbol": "SH603330",
                    "signal_date": recent_date(),
                    "pattern_id": "LEGACY_VP_SINGLE_001",
                    "pattern_name": "放量大阳线",
                    "action_label": "SIM_BUY_CANDIDATE",
                    "risk_level": "medium",
                    "score": 0.82,
                    "close": 12.3,
                    "pct_change": 4.8,
                    "tags": ["markup_reclaim"],
                    "matched_tags": ["volume_price"],
                }
            ]
        },
        signal_optimization={
            "selected_stable_candidate": {
                "parameters": {
                    "confirmation_filter": "entry_green_above_signal",
                    "buy_position_ratio": 0.08,
                    "wait_position_ratio": 0.06,
                }
            },
            "shadow_parameter_evidence": {
                "expanded_history_review": {
                    "phase_context_split": {
                        "filter_experiments": {
                            "strategy_comparison": {
                                "top_review_priorities": [
                                    {
                                        "experiment_id": "base_shadow_candidate",
                                        "tier": "stable_walk_forward_candidate_review_only",
                                        "review_priority_score": 88.0,
                                        "metrics": {
                                            "trade_count": 24,
                                            "win_rate": 0.75,
                                            "average_return_pct": 4.5,
                                            "equal_weight_cumulative_return_pct": 80.0,
                                        },
                                        "walk_forward_status": "passed_for_simulation_review",
                                        "market_context_status": "robust",
                                    }
                                ]
                            },
                            "items": [
                                {
                                    "experiment_id": "base_shadow_candidate",
                                    "prefilter": "none",
                                    "parameters": {
                                        "confirmation_filter": "entry_green_above_signal",
                                        "buy_position_ratio": 0.08,
                                        "wait_position_ratio": 0.06,
                                    },
                                    "metrics": {
                                        "trade_count": 24,
                                        "win_rate": 0.75,
                                        "average_return_pct": 4.5,
                                        "equal_weight_cumulative_return_pct": 80.0,
                                    },
                                    "walk_forward": {"status": "passed_for_simulation_review"},
                                    "market_context": {"status": "robust"},
                                }
                            ],
                        }
                    }
                }
            },
        },
        candidate_review_priority={"review_priority_score": 80, "review_priority_tier": "high_review_priority"},
    )

    assert plan["schema_version"] == "simulation_review_plan.v1"
    assert plan["status"] == "ready_for_dry_run_review"
    assert plan["permission_policy"]["may_submit_order"] is False
    assert plan["permission_policy"]["may_enable_screen_click"] is False
    assert plan["candidate_count"] == 1
    candidate = plan["candidates"][0]
    assert candidate["recommended_mode"] == "dry_run_screen_candidate"
    assert candidate["evidence_quality"]["schema_version"] == "simulation_candidate_evidence_quality.v1"
    assert candidate["evidence_quality"]["confidence_tier"] == "high_confidence_dry_run_review"
    assert candidate["confidence_adjusted_priority_score"] <= candidate["priority_score"]
    assert "walk_forward_passed" in candidate["evidence_quality"]["reasons"]


def test_daily_bar_cache_refresh_benchmark_bars_saves_index_history(clean_store, monkeypatch):
    service = DailyBarCacheService(store=clean_store)
    frame = pd.DataFrame(
        [
            {"date": "2026-01-01", "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0, "volume": 1000},
            {"date": "2026-01-02", "open": 101.0, "high": 102.0, "low": 100.0, "close": 101.5, "volume": 1200},
            {"date": "2026-01-03", "open": 102.0, "high": 103.0, "low": 101.0, "close": 102.0, "volume": 1300},
        ]
    )
    monkeypatch.setattr(service, "_load_akshare_index_daily_bars", lambda symbol: frame)

    result = service.refresh_benchmark_bars(symbols=["SH000300"], days=2)

    assert result["status"] == "completed"
    assert result["ready_count"] == 1
    assert result["results"][0]["bars_saved"] == 2
    bars = service.get_bars("SH000300", limit=5)
    assert len(bars) == 2
    assert bars[0]["trade_date"] == "2026-01-03"
    assert bars[0]["source"] == "akshare.stock_zh_index_daily"


def test_daily_bar_cache_refresh_symbols_saves_explicit_stock_history(clean_store, monkeypatch):
    service = DailyBarCacheService(store=clean_store)
    raw_bars = [
        SimpleNamespace(
            trade_date=f"2026-01-0{index}",
            open=10.0 + index,
            high=10.5 + index,
            low=9.5 + index,
            close=10.2 + index,
            volume=1000 + index,
            amount=100000 + index,
        )
        for index in range(1, 4)
    ]
    monkeypatch.setattr(service.builder.provider, "get_daily_bars", lambda code: raw_bars)

    result = service.refresh_symbols(["SH603186"], days=2)

    assert result["processed"] == 1
    assert result["results"][0]["symbol"] == "SH603186"
    assert result["results"][0]["bars_saved"] == 2
    bars = service.get_bars("SH603186", limit=5)
    assert len(bars) == 2
    assert bars[0]["trade_date"] == "2026-01-03"
    assert bars[0]["source"] == "akshare.stock_zh_a_hist"
    assert bars[0]["adjustment_mode"] == "qfq"
    assert bars[0]["volume_unit"] == "hand"


def test_daily_bar_cache_uses_qfq_fallback_without_mixing_raw_prices(clean_store, monkeypatch):
    service = DailyBarCacheService(store=clean_store)

    def fail_primary(*_args, **_kwargs):
        raise RuntimeError("primary unavailable")

    fallback = pd.DataFrame(
        [
            {
                "date": "2026-01-02",
                "open": "10.0",
                "high": "10.5",
                "low": "9.8",
                "close": "10.2",
                "volume": "1234",
                "amount": None,
            }
        ]
    )
    fallback.attrs["adjustment_mode"] = "qfq"
    monkeypatch.setattr(service.builder.provider, "get_daily_bars", fail_primary)
    monkeypatch.setattr(
        service,
        "_load_tencent_qfq_daily_bars",
        lambda *_args, **_kwargs: fallback,
    )

    result = service.refresh_symbols(["SZ002842"], days=30)

    assert result["results"][0]["source"] == "tencent.fqkline.qfq"
    assert result["results"][0]["adjustment_mode"] == "qfq"
    bars = service.get_bars("SZ002842", limit=5)
    assert bars[0]["adjustment_mode"] == "qfq"
    assert bars[0]["volume_unit"] == "hand"
    assert bars[0]["amount"] is None


def test_amountless_fallback_cannot_downgrade_complete_ready_rows(clean_store, monkeypatch):
    service = DailyBarCacheService(store=clean_store)
    primary = pd.DataFrame(
        [
            {
                "date": "2026-01-02",
                "open": 10.0,
                "high": 10.5,
                "low": 9.8,
                "close": 10.2,
                "volume": 1234,
                "amount": 567890.0,
            }
        ]
    )
    monkeypatch.setattr(service.builder.provider, "get_daily_bars", lambda _code: primary)
    service.refresh_symbols(["SZ002842"], days=30)

    def fail_primary(*_args, **_kwargs):
        raise RuntimeError("primary unavailable")

    fallback = pd.DataFrame(
        [
            {
                "date": "2026-01-02",
                "open": 99.0,
                "high": 100.0,
                "low": 98.0,
                "close": 99.5,
                "volume": 9999,
                "amount": None,
            },
            {
                "date": "2026-01-03",
                "open": 10.3,
                "high": 10.7,
                "low": 10.1,
                "close": 10.6,
                "volume": 1500,
                "amount": None,
            },
        ]
    )
    fallback.attrs["adjustment_mode"] = "qfq"
    monkeypatch.setattr(service.builder.provider, "get_daily_bars", fail_primary)
    monkeypatch.setattr(
        service,
        "_load_tencent_qfq_daily_bars",
        lambda *_args, **_kwargs: fallback,
    )

    service.refresh_symbols(["SZ002842"], days=30)

    bars = {row["trade_date"]: row for row in service.get_bars("SZ002842", limit=5)}
    assert bars["2026-01-02"]["close"] == 10.2
    assert bars["2026-01-02"]["amount"] == 567890.0
    assert bars["2026-01-02"]["source"] == "akshare.stock_zh_a_hist"
    assert bars["2026-01-03"]["close"] == 10.6
    assert bars["2026-01-03"]["amount"] is None
    assert bars["2026-01-03"]["source"] == "tencent.fqkline.qfq"


def test_daily_bar_cache_drops_incomplete_current_session(clean_store, monkeypatch):
    service = DailyBarCacheService(store=clean_store)
    frame = pd.DataFrame(
        [
            {
                "date": "2026-07-14",
                "open": 10.0,
                "high": 10.5,
                "low": 9.8,
                "close": 10.2,
                "volume": 1000,
            },
            {
                "date": "2026-07-15",
                "open": 10.3,
                "high": 10.8,
                "low": 10.1,
                "close": 10.6,
                "volume": 800,
            },
        ]
    )
    monkeypatch.setattr(service.builder.provider, "get_daily_bars", lambda _code: frame)
    monkeypatch.setattr(service, "_incomplete_session_date", lambda: "2026-07-15")

    result = service.refresh_symbols(["SZ002842"], days=30)

    assert result["results"][0]["bars_saved"] == 1
    bars = service.get_bars("SZ002842", limit=5)
    assert [bar["trade_date"] for bar in bars] == ["2026-07-14"]


def test_tencent_qfq_loader_accepts_day_when_no_adjustment_exists(clean_store, monkeypatch):
    service = DailyBarCacheService(store=clean_store)
    payload = {
        "code": 0,
        "data": {
            "sh688515": {
                "day": [["2026-07-14", "10.0", "10.2", "10.5", "9.8", "1234"]]
            }
        },
    }

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps(payload).encode("utf-8")

    monkeypatch.setattr("app.data.daily_bar_cache.urlopen", lambda *_args, **_kwargs: FakeResponse())

    frame = service._load_tencent_qfq_daily_bars("688515")

    assert frame.iloc[0].to_dict() == {
        "date": "2026-07-14",
        "open": "10.0",
        "close": "10.2",
        "high": "10.5",
        "low": "9.8",
        "volume": "1234",
        "amount": None,
    }
    assert frame.attrs["adjustment_mode"] == "none"
    assert frame.attrs["source"] == "tencent.fqkline.raw"


def test_tencent_raw_is_qfq_only_when_sina_unit_factor_covers_full_horizon(
    clean_store,
    monkeypatch,
):
    service = DailyBarCacheService(store=clean_store)
    raw_payload = {
        "code": 0,
        "data": {
            "bj920011": {
                "day": [
                    ["2026-07-16", "10.0", "10.2", "10.5", "9.8", "1234"],
                    ["2026-07-17", "10.2", "10.4", "10.6", "10.1", "1500"],
                ]
            }
        },
    }
    factor_payload = {
        "total": 2,
        "data": [
            {"d": "2026-04-08", "f": "1.0000000000000000"},
            {"d": "1900-01-01", "f": "1.0000000000000000"},
        ],
    }

    class FakeResponse:
        def __init__(self, body):
            self.body = body.encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return self.body

    def fake_urlopen(request, timeout):
        assert timeout == 20
        if "finance.sina.com.cn" in request.full_url:
            return FakeResponse(f"var bj920011qfq={json.dumps(factor_payload)} /* audit */")
        return FakeResponse(json.dumps(raw_payload))

    monkeypatch.setattr("app.data.daily_bar_cache.urlopen", fake_urlopen)

    frame = service._load_tencent_qfq_daily_bars("BJ920011", days=120)

    assert frame.attrs["adjustment_mode"] == "qfq"
    assert frame.attrs["source"] == (
        "tencent.fqkline.raw+sina.qfq_factor.unit_verified"
    )
    assert frame["date"].tolist() == ["2026-07-16", "2026-07-17"]
    assert frame["close"].tolist() == ["10.2", "10.4"]


@pytest.mark.parametrize(
    "factor_payload",
    [
        {"total": 0, "data": []},
        {
            "total": 2,
            "data": [
                {"d": "2026-04-08", "f": "1.0000000000000000"},
                {"d": "1900-01-01", "f": "1.1000000000000000"},
            ],
        },
        {
            "total": 1,
            "data": [{"d": "2026-07-18", "f": "1.0000000000000000"}],
        },
    ],
    ids=("missing", "non_unit", "does_not_cover_raw_horizon"),
)
def test_tencent_raw_remains_isolated_when_sina_factor_is_not_safe(
    clean_store,
    monkeypatch,
    factor_payload,
):
    service = DailyBarCacheService(store=clean_store)
    raw_payload = {
        "code": 0,
        "data": {
            "bj920011": {
                "day": [["2026-07-17", "10.2", "10.4", "10.6", "10.1", "1500"]]
            }
        },
    }

    class FakeResponse:
        def __init__(self, body):
            self.body = body.encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return self.body

    def fake_urlopen(request, timeout):
        assert timeout == 20
        if "finance.sina.com.cn" in request.full_url:
            return FakeResponse(f"var bj920011qfq={json.dumps(factor_payload)} /* audit */")
        return FakeResponse(json.dumps(raw_payload))

    monkeypatch.setattr("app.data.daily_bar_cache.urlopen", fake_urlopen)

    frame = service._load_tencent_qfq_daily_bars("BJ920011", days=120)

    assert frame.attrs["adjustment_mode"] == "none"
    assert frame.attrs["source"] == "tencent.fqkline.raw"


def test_phase_replay_prefers_local_qfq_cache(clean_store):
    dates = pd.bdate_range(end="2026-07-14", periods=80)
    with clean_store.connect() as conn:
        conn.executemany(
            """
            INSERT INTO daily_bar_cache(
                symbol, trade_date, open, high, low, close, volume, amount,
                source, adjustment_mode, volume_unit, quality_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "SH600129",
                    trade_date.date().isoformat(),
                    10.0 + index * 0.01,
                    10.4 + index * 0.01,
                    9.8 + index * 0.01,
                    10.2 + index * 0.01,
                    1000 + index,
                    1_000_000 + index,
                    "tencent.fqkline.qfq",
                    "qfq",
                    "hand",
                    "ready",
                )
                for index, trade_date in enumerate(dates)
            ],
        )

    class RemoteMustNotRun:
        def get_daily_bars(self, *_args, **_kwargs):
            raise AssertionError("local qfq cache should be preferred")

    service = MainForcePhaseReplayService(provider=RemoteMustNotRun())

    frame, source = service._load_daily_bars("600129")

    assert source == "daily_bar_cache.qfq"
    assert len(frame) == 80
    assert frame.iloc[-1]["日期"] == "2026-07-14"


def test_offhour_ensure_benchmark_history_refreshes_when_phase_confidence_needs_it(
    clean_store,
    tmp_path,
    monkeypatch,
):
    calls = {}

    class FakeDailyBarCache:
        def refresh_benchmark_bars(self, symbols, days):
            calls["symbols"] = symbols
            calls["days"] = days
            return {"status": "completed", "ready_count": 2, "results": []}

    monkeypatch.setattr(offhour, "DailyBarCacheService", lambda: FakeDailyBarCache())
    service = OffhourResearchLoopService(
        dataset2_source_dir=write_dataset2_source(tmp_path),
        artifact_dir=tmp_path / "output" / "model_candidates",
    )

    result = service._ensure_benchmark_history(days=360, enabled=True)

    assert calls["symbols"] == offhour.BENCHMARK_HISTORY_SYMBOLS
    assert calls["days"] == offhour.MAX_INLINE_HISTORY_REFRESH_DAYS
    assert result["status"] == "partial"
    assert result["before"]["status"] == "insufficient_benchmark_data"
    assert result["refresh"]["status"] == "completed"
    assert result["live_trading_enabled"] is False


def test_offhour_ensure_benchmark_history_uses_existing_cache_without_refresh(
    clean_store,
    tmp_path,
    monkeypatch,
):
    for idx in range(offhour.MIN_BENCHMARK_READY_BARS):
        insert_bar(clean_store, "SH000300", f"2026-01-0{idx + 1}", 100 + idx, 101 + idx, 99 + idx, 100 + idx)

    class ShouldNotRefresh:
        def refresh_benchmark_bars(self, symbols, days):
            raise AssertionError("benchmark refresh should not run when cache is ready")

    monkeypatch.setattr(offhour, "DailyBarCacheService", lambda: ShouldNotRefresh())
    service = OffhourResearchLoopService(
        dataset2_source_dir=write_dataset2_source(tmp_path),
        artifact_dir=tmp_path / "output" / "model_candidates",
    )

    result = service._ensure_benchmark_history(days=120, enabled=True)

    assert result["status"] == "ready"
    assert result["refreshed"] is False
    assert result["coverage"]["ready_symbols"] == ["SH000300"]


def test_signal_loss_attribution_recommends_review_only_filters(clean_store, tmp_path, monkeypatch):
    service = OffhourResearchLoopService(
        dataset2_source_dir=write_dataset2_source(tmp_path),
        artifact_dir=tmp_path / "output" / "model_candidates",
    )
    trades = [
        {
            "symbol": "SH688622",
            "pattern_id": "LEGACY_VP_SINGLE_006",
            "action_label": "WAIT_CONFIRMATION",
            "signal_date": "2025-06-24",
            "entry_date": "2025-06-25",
            "exit_date": "2025-06-27",
            "realized_pnl_pct": -4.2,
            "exit_reason": "signal_stop_loss",
            "entry_gap_pct": 0.5,
            "entry_close_vs_signal_pct": 0.3,
            "signal_close": 82.75,
            "entry_open": 83.16,
            "entry_close": 83.02,
            "signal_tags": ["daily", "small_body", "sideways", "top_risk"],
            "matched_tags": ["small_body"],
        },
        {
            "symbol": "SH688010",
            "pattern_id": "LEGACY_VP_SINGLE_006",
            "action_label": "WAIT_CONFIRMATION",
            "signal_date": "2025-06-24",
            "entry_date": "2025-06-25",
            "exit_date": "2025-06-27",
            "realized_pnl_pct": -4.1,
            "exit_reason": "signal_stop_loss",
            "entry_gap_pct": 0.2,
            "entry_close_vs_signal_pct": 0.7,
            "signal_close": 33.73,
            "entry_open": 33.8,
            "entry_close": 33.96,
            "signal_tags": ["daily", "small_body", "sideways", "top_risk"],
            "matched_tags": ["small_body"],
        },
        {
            "symbol": "SH603439",
            "pattern_id": "LEGACY_VP_SINGLE_005",
            "action_label": "WAIT_CONFIRMATION",
            "signal_date": "2025-06-24",
            "entry_date": "2025-06-25",
            "exit_date": "2025-06-26",
            "realized_pnl_pct": -4.0,
            "exit_reason": "signal_stop_loss",
            "entry_gap_pct": 0.1,
            "entry_close_vs_signal_pct": 0.2,
            "signal_close": 11.96,
            "entry_open": 11.97,
            "entry_close": 11.98,
            "signal_tags": ["daily", "turning_point", "small_body", "volume_surge"],
            "matched_tags": ["turning_point", "small_body"],
        },
        {
            "symbol": "SH688123",
            "pattern_id": "LEGACY_VP_SINGLE_006",
            "action_label": "WAIT_CONFIRMATION",
            "signal_date": "2025-06-24",
            "entry_date": "2025-06-25",
            "exit_date": "2025-06-27",
            "realized_pnl_pct": 0.2,
            "exit_reason": "horizon_exit",
            "entry_gap_pct": 0.1,
            "entry_close_vs_signal_pct": 0.4,
            "signal_close": 20.0,
            "entry_open": 20.02,
            "entry_close": 20.08,
            "signal_tags": ["daily", "small_body", "sideways", "top_risk"],
            "matched_tags": ["small_body"],
        },
        {
            "symbol": "SH600500",
            "pattern_id": "LEGACY_VP_SINGLE_005",
            "action_label": "WAIT_CONFIRMATION",
            "signal_date": "2025-06-24",
            "entry_date": "2025-06-25",
            "exit_date": "2025-06-30",
            "realized_pnl_pct": -0.2,
            "exit_reason": "horizon_exit",
            "entry_gap_pct": -0.2,
            "entry_close_vs_signal_pct": 0.2,
            "signal_close": 3.84,
            "entry_open": 3.83,
            "entry_close": 3.85,
            "signal_tags": ["daily", "turning_point", "small_body", "volume_up_price_stall"],
            "matched_tags": ["turning_point", "small_body"],
        },
        {
            "symbol": "SH600001",
            "pattern_id": "LEGACY_VP_SINGLE_001",
            "action_label": "SIM_BUY_CANDIDATE",
            "signal_date": "2025-06-25",
            "entry_date": "2025-06-26",
            "exit_date": "2025-06-30",
            "realized_pnl_pct": 8.0,
            "exit_reason": "take_profit",
            "entry_gap_pct": 0.8,
            "entry_close_vs_signal_pct": 2.2,
            "signal_close": 10.0,
            "entry_open": 10.08,
            "entry_close": 10.22,
            "signal_tags": ["daily", "big_yang", "price_volume_rise"],
            "matched_tags": ["big_yang"],
        },
        {
            "symbol": "SZ300001",
            "pattern_id": "LEGACY_VP_SINGLE_001",
            "action_label": "SIM_BUY_CANDIDATE",
            "signal_date": "2025-06-25",
            "entry_date": "2025-06-26",
            "exit_date": "2025-06-30",
            "realized_pnl_pct": 6.0,
            "exit_reason": "horizon_exit",
            "entry_gap_pct": 0.5,
            "entry_close_vs_signal_pct": 1.5,
            "signal_close": 20.0,
            "entry_open": 20.1,
            "entry_close": 20.3,
            "signal_tags": ["daily", "bullish_attack", "price_volume_rise"],
            "matched_tags": ["bullish_attack"],
        },
    ]

    monkeypatch.setattr(
        service,
        "_signal_backtest",
        lambda *args, **kwargs: {
            "metrics": service._trade_return_summary(trades),
            "trades": trades,
        },
    )
    monkeypatch.setattr(
        service,
        "_phase_confidence_market_regime",
        lambda signal_date: {"regime": "benchmark_neutral"},
    )

    result = service._signal_loss_attribution(
        replay={"signals": []},
        signals=[],
        candidate={
            "parameters": {
                "entry_delay_days": 1,
                "horizon_days": 3,
                "stop_loss_pct": 0.04,
                "take_profit_pct": 0.08,
                "confirmation_filter": "entry_close_above_signal",
            }
        },
    )

    assert result["schema_version"] == "signal_loss_attribution.v1"
    assert result["status"] == "completed"
    recommendation_ids = {item["id"] for item in result["recommendation"]["items"]}
    assert "avoid_star_weak_confirmation" in recommendation_ids
    assert "promote_strong_reclaim_confidence" in recommendation_ids
    assert "tighten_turning_point_wait_confirmation" in recommendation_ids
    assert result["recommendation"]["can_change_rules_yaml"] is False
    assert result["recommendation"]["can_change_position_size"] is False
    assert result["recommendation"]["can_trigger_orders"] is False
    assert result["live_trading_enabled"] is False


def test_stable_candidate_tradeoff_attribution_identifies_filtered_loss(clean_store, tmp_path, monkeypatch):
    service = OffhourResearchLoopService(
        dataset2_source_dir=write_dataset2_source(tmp_path),
        artifact_dir=tmp_path / "output" / "model_candidates",
    )
    tracks = service._stable_candidate_tracks(
        [
            stable_candidate("none", validation_return=99.0, total_return=200.0),
            stable_candidate("entry_close_above_signal", validation_return=23.0, total_return=100.0),
        ]
    )

    def fake_signal_backtest(*args, **kwargs):
        confirmation_filter = kwargs["confirmation_filter"]
        common = {
            "symbol": "SH600000",
            "pattern_id": "TEST_BIG_YANG_001",
            "action_label": "SIM_BUY_CANDIDATE",
            "signal_date": "2026-05-03",
            "entry_date": "2026-05-04",
            "exit_date": "2026-05-05",
            "realized_pnl_pct": 4.0,
            "exit_reason": "take_profit",
            "signal_close": 10.0,
            "entry_open": 10.05,
            "entry_close": 10.2,
        }
        filtered_loss = {
            "symbol": "SH600001",
            "pattern_id": "TEST_BIG_YANG_001",
            "action_label": "SIM_BUY_CANDIDATE",
            "signal_date": "2026-05-04",
            "entry_date": "2026-05-05",
            "exit_date": "2026-05-06",
            "realized_pnl_pct": -6.0,
            "exit_reason": "stop_loss",
            "signal_tags": ["top_risk", "volume_up_price_stall"],
            "matched_tags": ["high_volume"],
        }
        trades = [common, filtered_loss] if confirmation_filter == "none" else [common]
        return {
            "status": "completed",
            "metrics": {
                "trade_count": len(trades),
                "win_rate": 0.5 if len(trades) == 2 else 1.0,
                "average_return_pct": -1.0 if len(trades) == 2 else 4.0,
            },
            "trades": trades,
            "review_only": True,
            "simulation_only": True,
        }

    monkeypatch.setattr(service, "_signal_backtest", fake_signal_backtest)

    attribution = service._stable_candidate_tradeoff_attribution(
        replay={"signals": []},
        signals=[],
        stable_candidate_tracks=tracks,
    )

    assert attribution["status"] == "completed"
    assert attribution["broad_only_trade_count"] == 1
    assert attribution["broad_only_summary"]["average_return_pct"] == -6.0
    assert attribution["verdict"]["label"] == "stabilization_filter_reduced_risk"
    assert attribution["broad_only_examples"][0]["symbol"] == "SH600001"
    assert attribution["broad_only_examples"][0]["phase_label"] == "distribution_or_failed_markup"
    assert "distribution_or_stall_risk" in attribution["broad_only_examples"][0]["learning_tags"]
    assert attribution["broad_only_tag_summary"]["risk_trade_count"] == 1
    assert attribution["broad_only_tag_summary"]["hard_risk_trade_count"] == 1
    assert attribution["broad_only_tag_summary"]["mixed_opportunity_risk_count"] == 0
    assert attribution["broad_only_tag_summary"]["phase_counts"]["distribution_or_failed_markup"] == 1
    assert attribution["review_only"] is True
    assert attribution["simulation_only"] is True


def test_broad_only_supervision_splits_watch_track_and_failed_markup_block(clean_store, tmp_path, monkeypatch):
    service = OffhourResearchLoopService(
        dataset2_source_dir=write_dataset2_source(tmp_path),
        artifact_dir=tmp_path / "output" / "model_candidates",
    )
    tracks = service._stable_candidate_tracks(
        [
            stable_candidate("none", validation_return=99.0, total_return=200.0),
            stable_candidate("entry_close_above_signal", validation_return=23.0, total_return=100.0),
        ]
    )

    def fake_signal_backtest(*args, **kwargs):
        confirmation_filter = kwargs["confirmation_filter"]
        common = {
            "symbol": "SH600000",
            "pattern_id": "TEST_COMMON_001",
            "action_label": "SIM_BUY_CANDIDATE",
            "signal_date": "2026-05-03",
            "entry_date": "2026-05-04",
            "exit_date": "2026-05-05",
            "realized_pnl_pct": 4.0,
            "exit_reason": "take_profit",
        }
        winners = [
            {
                "symbol": f"SH60000{idx}",
                "pattern_id": "TEST_WINNER_001",
                "action_label": "WAIT_CONFIRMATION",
                "signal_date": f"2026-05-0{idx + 4}",
                "entry_date": f"2026-05-0{idx + 5}",
                "exit_date": f"2026-05-0{idx + 6}",
                "realized_pnl_pct": pnl,
                "exit_reason": "horizon_exit",
                "signal_close": 10.0,
                "entry_open": 10.05,
                "entry_close": 10.2,
                "entry_gap_pct": 0.5,
                "entry_close_vs_signal_pct": 2.0,
                "signal_tags": ["small_body", "high_amount"],
            }
            for idx, pnl in enumerate([9.0, 5.0, 4.0], start=1)
        ]
        near_reclaim_winner = {
            "symbol": "SH600019",
            "pattern_id": "TEST_WINNER_001",
            "action_label": "WAIT_CONFIRMATION",
            "signal_date": "2026-05-09",
            "entry_date": "2026-05-10",
            "exit_date": "2026-05-11",
            "realized_pnl_pct": 6.0,
            "exit_reason": "horizon_exit",
            "signal_close": 10.0,
            "entry_open": 9.95,
            "entry_close": 9.9,
            "entry_gap_pct": -0.5,
            "entry_close_vs_signal_pct": -1.0,
            "signal_tags": ["small_body", "high_amount"],
        }
        failed_markup = {
            "symbol": "SZ301999",
            "pattern_id": "TEST_FAILED_MARKUP_001",
            "action_label": "SIM_BUY_CANDIDATE",
            "signal_date": "2026-05-09",
            "entry_date": "2026-05-10",
            "exit_date": "2026-05-11",
            "realized_pnl_pct": -6.0,
            "exit_reason": "signal_stop_loss",
            "signal_close": 10.0,
            "entry_open": 9.7,
            "entry_close": 9.5,
            "signal_tags": ["top_risk", "volume_up_price_stall"],
        }
        trades = [common, *winners, near_reclaim_winner, failed_markup] if confirmation_filter == "none" else [common]
        return {
            "status": "completed",
            "metrics": {"trade_count": len(trades), "win_rate": 0.8, "average_return_pct": 3.2},
            "trades": trades,
            "review_only": True,
            "simulation_only": True,
        }

    monkeypatch.setattr(service, "_signal_backtest", fake_signal_backtest)

    attribution = service._stable_candidate_tradeoff_attribution(
        replay={"signals": []},
        signals=[],
        stable_candidate_tracks=tracks,
    )

    supervision = attribution["broad_only_supervision"]
    assert supervision["enhanced_watch_track"]["status"] == "candidate"
    assert supervision["enhanced_watch_track"]["raw_opportunity_count"] == 4
    assert supervision["enhanced_watch_track"]["sample_count"] == 3
    assert supervision["enhanced_watch_track"]["secondary_confirmation_rejected_count"] == 1
    assert supervision["enhanced_watch_track"]["confirmation_summary"]["passed_count"] == 3
    assert supervision["enhanced_watch_track"]["suggested_review_position_ratio"] == 0.02
    assert supervision["near_reclaim_watch_track"]["status"] == "watch_for_reclaim"
    assert supervision["near_reclaim_watch_track"]["sample_count"] == 1
    assert supervision["failed_markup_block"]["status"] == "active"
    assert supervision["failed_markup_block"]["sample_count"] == 1
    assert supervision["mixed_opportunity_risk_review"]["sample_count"] == 0
    assert supervision["review_only"] is True
    assert supervision["simulation_only"] is True


def test_reclaim_watchlist_marks_near_reclaim_review_and_hard_risk(clean_store, tmp_path):
    service = OffhourResearchLoopService(
        dataset2_source_dir=write_dataset2_source(tmp_path),
        artifact_dir=tmp_path / "output" / "model_candidates",
    )
    for symbol, latest_open, latest_close, latest_volume in [
        ("SH600010", 9.95, 9.90, 900),
        ("SH600011", 10.02, 10.12, 900),
        ("SH600012", 10.00, 9.30, 6000),
    ]:
        insert_bar(clean_store, symbol, "2026-05-01", 9.8, 10.0, 9.7, 9.9, volume=1000)
        insert_bar(clean_store, symbol, "2026-05-02", 9.9, 10.2, 9.8, 10.0, volume=1100)
        insert_bar(clean_store, symbol, "2026-05-03", 10.0, 10.4, 9.9, 10.0, volume=1200)
        insert_bar(
            clean_store,
            symbol,
            "2026-05-04",
            latest_open,
            max(latest_open, latest_close, 10.1),
            min(latest_open, latest_close, 9.2),
            latest_close,
            volume=latest_volume,
        )

    replay = {
        "signals": [
            {
                "symbol": symbol,
                "signal_date": "2026-05-03",
                "close": 10.0,
                "tags": ["price_volume_rise", "high_amount"],
                "matched_tags": ["price_volume_rise"],
                "pattern_id": "TEST_BIG_YANG_001",
                "pattern_name": "fixture",
                "category": "fixture",
                "action_label": "WAIT_CONFIRMATION",
                "risk_level": "medium",
                "score": 0.8,
            }
            for symbol in ["SH600010", "SH600011", "SH600012"]
        ]
    }

    watchlist = service._reclaim_watchlist(replay)
    by_symbol = {item["symbol"]: item for item in watchlist["items"]}

    assert watchlist["schema_version"] == "reclaim_watchlist.v1"
    assert watchlist["counts"]["near_reclaim_watch"] == 1
    assert watchlist["counts"]["reclaim_review"] == 1
    assert watchlist["counts"]["blocked_failed_markup_risk"] == 1
    assert by_symbol["SH600010"]["allowed_effect"] == "watch_for_reclaim_only_not_dry_run"
    assert by_symbol["SH600011"]["allowed_effect"] == "raise_review_priority_and_dry_run_only"
    assert "big_yin" in by_symbol["SH600012"]["risk_tags"]
    assert by_symbol["SH600012"]["allowed_effect"] == "observe_only"
    assert watchlist["policy"]["broker_or_order_action"] is False
    assert watchlist["review_only"] is True
    assert watchlist["simulation_only"] is True


def test_reclaim_transition_study_scores_next_bar_statuses(clean_store, tmp_path):
    service = OffhourResearchLoopService(
        dataset2_source_dir=write_dataset2_source(tmp_path),
        artifact_dir=tmp_path / "output" / "model_candidates",
    )
    fixtures = {
        "SH600101": {
            "transition": (10.02, 10.2, 9.95, 10.12, 1000),
            "future": [10.3, 10.5, 10.7, 10.8, 11.0],
        },
        "SH600102": {
            "transition": (9.95, 10.0, 9.85, 9.9, 1200),
            "future": [10.0, 10.1, 10.2, 10.35, 10.45],
        },
        "SH600103": {
            "transition": (10.0, 10.1, 9.2, 9.3, 7000),
            "future": [9.2, 9.1, 9.0, 8.9, 8.8],
        },
    }
    for symbol, fixture in fixtures.items():
        insert_bar(clean_store, symbol, "2026-05-01", 9.8, 10.0, 9.7, 9.9, volume=1000)
        insert_bar(clean_store, symbol, "2026-05-02", 9.9, 10.2, 9.8, 10.0, volume=1100)
        insert_bar(clean_store, symbol, "2026-05-03", 10.0, 10.4, 9.9, 10.0, volume=1200)
        open_, high, low, close, volume = fixture["transition"]
        insert_bar(clean_store, symbol, "2026-05-04", open_, high, low, close, volume=volume)
        for idx, future_close in enumerate(fixture["future"], start=5):
            insert_bar(
                clean_store,
                symbol,
                f"2026-05-{idx:02d}",
                future_close - 0.03,
                future_close + 0.08,
                future_close - 0.12,
                future_close,
                volume=1000 + idx,
            )

    replay = {
        "signals": [
            {
                "symbol": symbol,
                "signal_date": "2026-05-03",
                "close": 10.0,
                "tags": ["price_volume_rise", "high_amount"],
                "matched_tags": ["price_volume_rise"],
                "pattern_id": "TEST_BIG_YANG_001",
                "pattern_name": "fixture",
                "category": "fixture",
                "action_label": "WAIT_CONFIRMATION",
                "risk_level": "medium",
                "score": 0.8,
            }
            for symbol in ["SH600101", "SH600102", "SH600103"]
        ]
    }

    study = service._reclaim_transition_study(replay)

    assert study["schema_version"] == "reclaim_transition_study.v1"
    assert study["status"] == "completed"
    assert study["evaluated_count"] == 3
    assert study["policy"]["no_future_data_in_status_classification"] is True
    assert study["policy"]["broker_or_order_action"] is False
    assert study["by_status"]["reclaim_review"]["sample_count"] == 1
    assert study["by_status"]["reclaim_review"]["average_return_pct"] > 0
    assert study["by_status"]["near_reclaim_watch"]["sample_count"] == 1
    assert study["by_status"]["near_reclaim_watch"]["suggested_review_treatment"] in {
        "collect_more_samples_before_weight_change",
        "keep_wider_watch_band_but_wait_for_reclaim",
    }
    assert study["by_status"]["blocked_failed_markup_risk"]["average_return_pct"] < 0
    assert study["by_status"]["blocked_failed_markup_risk"]["suggested_review_treatment"] == (
        "keep_blocked_until_new_signal_and_risk_tags_clear"
    )
    hard_risk_rows = {
        row["key"]: row
        for row in study["risk_tag_attribution"]["by_status_tag"]
    }
    assert hard_risk_rows["blocked_failed_markup_risk:big_yin"]["suggested_treatment"] == "observe_only_hard_risk"
    assert study["supervision"]["suggested_positioning"]["near_reclaim_position_ratio"] == 0.0
    assert study["review_only"] is True
    assert study["simulation_only"] is True


def test_candidate_priority_uses_reclaim_transition_evidence_review_only(clean_store, tmp_path):
    service = OffhourResearchLoopService(
        dataset2_source_dir=write_dataset2_source(tmp_path),
        artifact_dir=tmp_path / "output" / "model_candidates",
    )

    priority = service._candidate_review_priority_framework(
        signal_optimization={"gate": {"status": "blocked"}},
        rule_family_memory={},
        rule_family_gate={},
        reclaim_watchlist={
            "counts": {
                "pending_future_data": 3,
                "blocked_failed_markup_risk": 1,
            }
        },
        reclaim_transition_study={
            "status": "completed",
            "by_status": {
                "reclaim_review": {
                    "sample_count": 47,
                    "win_rate": 0.574468,
                    "average_return_pct": 3.124344,
                    "cumulative_return_pct": 247.174651,
                },
                "near_reclaim_watch": {
                    "sample_count": 11,
                    "average_return_pct": 2.1,
                },
            },
        },
    )

    reclaim_factor = next(
        factor for factor in priority["factors"] if factor["name"] == "reclaim_confirmation_state"
    )
    assert reclaim_factor["score_points"] == 8
    assert "historical_reclaim_transition_positive" in reclaim_factor["reasons"]
    assert "historical_reclaim_cumulative_return_above_20pct" in reclaim_factor["reasons"]
    assert "failed_markup_risk_penalty" in reclaim_factor["reasons"]
    assert reclaim_factor["evidence"]["transition_reclaim_sample_count"] == 47
    assert reclaim_factor["evidence"]["transition_reclaim_cumulative_return_pct"] == 247.174651
    assert priority["allowed_effect"] == "review_priority_only"
    assert "broker_or_order_action" in priority["does_not_change"]
    assert priority["live_trading_enabled"] is False


def test_next_action_prioritizes_recent_signals_waiting_for_future_data(clean_store, tmp_path):
    service = OffhourResearchLoopService(
        dataset2_source_dir=write_dataset2_source(tmp_path),
        artifact_dir=tmp_path / "output" / "model_candidates",
    )

    next_action = service._next_action(
        status="completed",
        replay={"signal_count": 10},
        signal_backtest={"metrics": {"trade_count": 5}},
        sandbox={"evaluated_count": 5},
        artifact={"signal_optimization_gate": {"status": "passed_for_simulation_review"}},
        coverage={"status": "ready"},
        reclaim_watchlist={"counts": {"pending_future_data": 6}},
    )

    assert "next ready bar" in next_action
    assert "near-reclaim" in next_action


def test_offhour_research_reads_dataset2_chinese_path_and_writes_candidate_artifact(
    clean_store, tmp_path, monkeypatch
):
    source_dir = write_dataset2_source(tmp_path)
    seed_signal_history(clean_store)
    insert_phase_match(clean_store, "SH600000")
    with clean_store.connect() as conn:
        conn.execute(
            """
            INSERT INTO events(event_type, payload_json)
            VALUES (?, ?)
            """,
            (
                "dataset2_training_run",
                json.dumps(
                    {
                        "rule_family_performance_memory": {
                            "schema_version": "dataset2_rule_family_performance_memory.v1",
                            "summary": {
                                "staging_group_count": 4,
                                "backtest_group_count": 2,
                                "backtest_trade_count": 18,
                                "positive_backtest_group_count": 1,
                                "execution_group_count": 1,
                            },
                            "top_backtest_groups": [
                                {
                                    "key": "LEGACY_VP_SINGLE_001|legacy_单根K线量价|SIM_BUY_CANDIDATE|medium",
                                    "pattern_id": "LEGACY_VP_SINGLE_001",
                                    "pattern_name": "放量大阳线",
                                    "category": "legacy_单根K线量价",
                                    "action_label": "SIM_BUY_CANDIDATE",
                                    "risk_level": "medium",
                                    "trade_count": 18,
                                    "win_rate": 0.666667,
                                    "average_return_pct": 3.2,
                                    "total_return_pct": 57.6,
                                    "worst_return_pct": -4.5,
                                    "review_priority_score": 57.6,
                                    "symbols": ["SZ002081", "SZ002115"],
                                    "review_only": True,
                                    "simulation_only": True,
                                },
                                {
                                    "key": "LEGACY_VP_SINGLE_006|legacy_单根K线量价|WAIT_CONFIRMATION|low_to_medium",
                                    "pattern_id": "LEGACY_VP_SINGLE_006",
                                    "pattern_name": "缩量小阴小阳线",
                                    "category": "legacy_单根K线量价",
                                    "action_label": "WAIT_CONFIRMATION",
                                    "risk_level": "low_to_medium",
                                    "trade_count": 12,
                                    "win_rate": 0.58,
                                    "average_return_pct": 2.1,
                                    "total_return_pct": 25.2,
                                    "worst_return_pct": -3.5,
                                    "review_priority_score": 25.2,
                                    "symbols": ["SH600110"],
                                    "review_only": True,
                                    "simulation_only": True,
                                },
                            ],
                            "top_execution_groups": [
                                {
                                    "key": "sim_cockpit_actions|buy|dry_run",
                                    "source": "sim_cockpit_actions",
                                    "action": "buy",
                                    "status": "dry_run",
                                    "sample_count": 2,
                                    "dry_run_count": 2,
                                    "executed_count": 0,
                                    "blocked_count": 0,
                                    "readback_count": 1,
                                    "feasible_rate": 1.0,
                                    "blocked_rate": 0.0,
                                    "review_only": True,
                                    "simulation_only": True,
                                }
                            ],
                            "review_only": True,
                            "simulation_only": True,
                            "live_trading_enabled": False,
                        },
                        "review_only": True,
                        "simulation_only": True,
                        "live_trading_enabled": False,
                    },
                    ensure_ascii=False,
                ),
            ),
        )
    monkeypatch.setattr(offhour, "OffhourPotentialSearchService", lambda: FakePotentialSearch())

    service = OffhourResearchLoopService(
        dataset2_source_dir=source_dir,
        artifact_dir=tmp_path / "output" / "model_candidates",
    )
    result = service.run(limit=10, strategy_limit=5, history_days=60, write_artifact=True)

    # The replay backtest produces no entry signal on this fixture, so the run
    # is honestly partial and says why. This test guards the Chinese dataset2
    # path handling and the candidate artifact, not the backtest outcome.
    assert result["status"] == "partial"
    assert "backtest_no_signal" in result["blocked_reasons"]
    assert result["dataset2_source"]["rule_count"] == 1
    assert result["dataset1_experience"]["status"] in {"ready", "missing"}
    assert result["dataset1_experience"]["constraints"]
    assert result["strategy_replay"]["signal_count"] >= 1
    assert result["signal_backtest"]["metrics"]["trade_count"] >= 1
    assert result["signal_backtest"]["review_only"] is True
    assert result["backtest"]["backtest_budget"]["profile"] == "balanced"
    assert result["backtest"]["backtest_budget"]["persisted_historical_backtest"] is False
    assert result["signal_optimization"]["status"] in {"skipped", "blocked", "passed_for_simulation_review"}
    assert result["reclaim_watchlist"]["schema_version"] == "reclaim_watchlist.v1"
    assert result["reclaim_transition_study"]["schema_version"] == "reclaim_transition_study.v1"
    assert result["focus_phase_diagnostics"]["schema_version"] == "focus_phase_diagnostics.v1"
    assert len(result["focus_phase_diagnostics"]["targets"]) == 3
    assert result["sandbox"]["evaluated_count"] >= 1
    assert result["model_candidate"]["artifact_written"] is True
    assert result["model_candidate"]["rule_family_review_gate"]["status"] == "passed_for_review"
    assert result["model_candidate"]["simulation_weight_gate"]["writes_rules_yaml"] is False
    assert result["model_candidate"]["simulation_weight_gate"]["auto_apply"] is False
    assert Path(result["model_candidate"]["artifact_path"]).exists()
    artifact = json.loads(Path(result["model_candidate"]["artifact_path"]).read_text(encoding="utf-8"))
    assert artifact["dataset1_experience_constraints"]["constraints"]
    constraint_ids = {
        item["constraint_id"]
        for item in artifact["dataset1_experience_constraints"]["constraints"]
    }
    assert "dataset1_low_position_limitup_quality" in constraint_ids
    assert "dataset1_dealer_cost_target" in constraint_ids
    assert artifact["dataset1_experience_constraints"]["strategy_synthesis"]["review_only"] is True
    assert artifact["strategy_synthesis"]["review_only"] is True
    assert artifact["strategy_synthesis"]["hard_limits"]["writes_rules_yaml"] is False
    assert artifact["strategy_recommendations"]
    assert artifact["rule_update_gate"]["writes_rules_yaml"] is False
    assert artifact["rule_update_gate"]["auto_apply"] is False
    assert artifact["rule_update_gate"]["status"] in {"blocked", "passed_for_review"}
    assert artifact["backtest_budget"]["profile"] == "balanced"
    assert artifact["signal_backtest_metrics"]["trade_count"] >= 1
    assert artifact["simulation_weight_gate"]["writes_rules_yaml"] is False
    assert artifact["simulation_weight_gate"]["auto_apply"] is False
    assert artifact["rule_family_review_gate"]["status"] == "passed_for_review"
    assert artifact["rule_family_review_gate"]["writes_rules_yaml"] is False
    assert artifact["rule_family_review_gate"]["auto_apply"] is False
    assert artifact["rule_family_performance_memory"]["status"] == "ready"
    assert artifact["rule_family_performance_memory"]["summary"]["backtest_trade_count"] == 18
    assert artifact["rule_family_performance_memory"]["top_backtest_groups"][0]["pattern_id"] == "LEGACY_VP_SINGLE_001"
    assert artifact["rule_family_performance_memory"]["top_backtest_groups"][0]["trade_count"] == 18
    assert artifact["rule_family_performance_memory"]["top_execution_groups"][0]["status"] == "dry_run"
    priority = artifact["candidate_review_priority_framework"]
    assert priority["schema_version"] == "candidate_review_priority_framework.v1"
    assert priority["allowed_effect"] == "review_priority_only"
    assert priority["review_only"] is True
    assert priority["simulation_only"] is True
    assert priority["live_trading_enabled"] is False
    assert "rules_yaml" in priority["does_not_change"]
    factor_names = {factor["name"] for factor in priority["factors"]}
    assert factor_names == {
        "stable_candidate_parameters",
        "rule_family_performance",
        "reclaim_confirmation_state",
        "sim_cockpit_execution_evidence",
    }
    rule_family_factor = next(
        factor for factor in priority["factors"] if factor["name"] == "rule_family_performance"
    )
    assert rule_family_factor["score_points"] >= 25
    assert rule_family_factor["evidence"]["pattern_id"] == "LEGACY_VP_SINGLE_001"
    assert rule_family_factor["evidence"]["trade_count"] == 18
    execution_factor = next(
        factor for factor in priority["factors"] if factor["name"] == "sim_cockpit_execution_evidence"
    )
    assert execution_factor["score_points"] == 10
    assert artifact["signal_optimization"]["gate"]["writes_rules_yaml"] is False
    assert artifact["signal_optimization"]["gate"]["auto_apply"] is False
    assert "stable_candidate_tracks" in artifact["signal_optimization"]
    assert "track_tradeoff_attribution" in artifact["signal_optimization"]
    assert "signal_loss_attribution" in artifact["signal_optimization"]
    assert "parameter_failure_attribution" in artifact["signal_optimization"]
    parameter_failure_attribution = artifact["signal_optimization"]["parameter_failure_attribution"]
    assert parameter_failure_attribution["schema_version"] == "signal_parameter_failure_attribution.v1"
    assert parameter_failure_attribution["review_only"] is True
    assert parameter_failure_attribution["simulation_only"] is True
    assert parameter_failure_attribution["live_trading_enabled"] is False
    assert isinstance(parameter_failure_attribution["train_gate_failures"], dict)
    assert isinstance(parameter_failure_attribution["validation_gate_failures"], dict)
    assert isinstance(parameter_failure_attribution["near_miss_train_candidates"], list)
    assert isinstance(parameter_failure_attribution["near_miss_validation_candidates"], list)
    assert "shadow_parameter_evidence" in artifact["signal_optimization"]
    shadow_parameter_evidence = artifact["signal_optimization"]["shadow_parameter_evidence"]
    assert shadow_parameter_evidence["schema_version"] == "shadow_parameter_evidence.v1"
    assert shadow_parameter_evidence["review_only"] is True
    assert shadow_parameter_evidence["simulation_only"] is True
    assert shadow_parameter_evidence["live_trading_enabled"] is False
    assert shadow_parameter_evidence["allowed_effect"] == "review_and_dataset_expansion_only"
    assert "stable_candidate_parameters" in shadow_parameter_evidence["does_not_change"]
    assert shadow_parameter_evidence["expanded_history_review"]["schema_version"] == (
        "shadow_parameter_expanded_history_review.v1"
    )
    assert shadow_parameter_evidence["expanded_history_review"]["review_only"] is True
    assert shadow_parameter_evidence["expanded_history_review"]["simulation_only"] is True
    assert "walk_forward_review" in shadow_parameter_evidence["expanded_history_review"]
    assert "weak_fold_attribution" in shadow_parameter_evidence["expanded_history_review"]
    assert shadow_parameter_evidence["expanded_history_review"]["weak_fold_attribution"]["schema_version"] == (
        "shadow_walk_forward_weak_fold_attribution.v1"
    )
    assert "phase_context_split" in shadow_parameter_evidence["expanded_history_review"]
    assert shadow_parameter_evidence["expanded_history_review"]["phase_context_split"]["schema_version"] == (
        "shadow_phase_context_split.v1"
    )
    assert shadow_parameter_evidence["expanded_history_review"]["phase_context_split"]["review_only"] is True
    assert shadow_parameter_evidence["expanded_history_review"]["phase_context_split"]["simulation_only"] is True
    phase_filter_experiments = shadow_parameter_evidence["expanded_history_review"]["phase_context_split"][
        "filter_experiments"
    ]
    assert phase_filter_experiments["schema_version"] == "shadow_context_filter_experiments.v1"
    assert phase_filter_experiments["review_only"] is True
    assert phase_filter_experiments["simulation_only"] is True
    assert phase_filter_experiments["allowed_effect"] == "review_only_filter_hypothesis_no_rule_or_trade_change"
    filter_strategy_comparison = phase_filter_experiments["strategy_comparison"]
    assert filter_strategy_comparison["schema_version"] == "shadow_filter_strategy_comparison.v1"
    assert filter_strategy_comparison["review_only"] is True
    assert filter_strategy_comparison["simulation_only"] is True
    assert filter_strategy_comparison["allowed_effect"] == "review_priority_only"
    assert "market_regime_context" in filter_strategy_comparison["ranking_basis"]
    assert filter_strategy_comparison["permission_policy"]["may_change_rules_yaml"] is False
    assert filter_strategy_comparison["permission_policy"]["may_change_position_size"] is False
    assert filter_strategy_comparison["permission_policy"]["may_enable_screen_click"] is False
    assert filter_strategy_comparison["top_review_priorities"] == filter_strategy_comparison["top_review_priority"]
    assert "next_action" in shadow_parameter_evidence["expanded_history_review"]
    assert "learning_filter_candidates" in artifact["signal_optimization"]
    assert isinstance(artifact["signal_optimization"]["learning_filter_candidates"], list)
    assert artifact["simulation_review_plan"]["schema_version"] == "simulation_review_plan.v1"
    assert artifact["simulation_review_plan"]["review_only"] is True
    assert artifact["simulation_review_plan"]["simulation_only"] is True
    assert artifact["simulation_review_plan"]["live_trading_enabled"] is False
    assert artifact["simulation_review_plan"]["allowed_effect"] == "review_and_dry_run_plan_only"
    assert artifact["simulation_review_plan"]["permission_policy"]["may_submit_order"] is False
    assert artifact["simulation_review_plan"]["permission_policy"]["may_enable_screen_click"] is False
    assert artifact["simulation_review_plan"]["portfolio_limits"]["reference_sim_cash"] == 200000.0
    assert artifact["simulation_review_plan"]["portfolio_limits"]["max_initial_position_ratio"] == 0.02
    assert artifact["simulation_review_plan"]["portfolio_limits"]["max_confirmed_position_ratio"] == 0.08
    if artifact["simulation_review_plan"]["candidates"]:
        first_plan_candidate = artifact["simulation_review_plan"]["candidates"][0]
        assert first_plan_candidate["evidence_quality"]["schema_version"] == "simulation_candidate_evidence_quality.v1"
        assert first_plan_candidate["evidence_quality"]["review_only"] is True
        assert first_plan_candidate["evidence_quality"]["simulation_only"] is True
        assert first_plan_candidate["evidence_quality"]["live_trading_enabled"] is False
        assert first_plan_candidate["confidence_adjusted_priority_score"] <= first_plan_candidate["priority_score"]
    assert artifact["reclaim_watchlist"]["schema_version"] == "reclaim_watchlist.v1"
    assert artifact["reclaim_transition_study"]["status"] in {"completed", "blocked"}
    assert artifact["focus_phase_diagnostics"]["schema_version"] == "focus_phase_diagnostics.v1"
    assert artifact["phase_similarity_performance"]["schema_version"] == "phase_similarity_performance.v1"
    assert artifact["phase_similarity_performance"]["matched_count"] >= 1
    assert artifact["phase_confidence_walk_forward"]["schema_version"] == "phase_confidence_walk_forward.v1"
    assert artifact["strategy_synthesis"]["active_simulation_hypothesis"]["reclaim_transition_study"]["status"] in {
        "completed",
        "blocked",
    }
    assert "focus_phase_diagnostics" in artifact["strategy_synthesis"]["active_simulation_hypothesis"]
    assert "phase_similarity_performance" in artifact["strategy_synthesis"]["active_simulation_hypothesis"]
    assert "phase_confidence_walk_forward" in artifact["strategy_synthesis"]["active_simulation_hypothesis"]
    assert "rule_family_performance_memory" in artifact["strategy_synthesis"]["active_simulation_hypothesis"]
    assert artifact["strategy_synthesis"]["active_simulation_hypothesis"]["rule_family_review_gate"]["status"] == "passed_for_review"
    assert artifact["strategy_synthesis"]["active_simulation_hypothesis"]["candidate_review_priority_framework"]["allowed_effect"] == "review_priority_only"
    assert "signal_loss_attribution" in artifact["strategy_synthesis"]["active_simulation_hypothesis"]
    assert "parameter_failure_attribution" in artifact["strategy_synthesis"]["active_simulation_hypothesis"]
    assert "shadow_parameter_evidence" in artifact["strategy_synthesis"]["active_simulation_hypothesis"]
    assert "learning_filter_candidates" in artifact["strategy_synthesis"]["active_simulation_hypothesis"]
    assert "simulation_review_plan" in artifact["strategy_synthesis"]["active_simulation_hypothesis"]
    assert (
        artifact["strategy_synthesis"]["active_simulation_hypothesis"]["simulation_review_plan"]["permission_policy"][
            "may_submit_order"
        ]
        is False
    )
    assert artifact["strategy_recommendations"][0]["signal_backtest"]["trade_count"] >= 1
    assert result["live_trading_enabled"] is False

    latest = service.latest_run()
    assert latest is not None
    assert latest["run_id"] == result["run_id"]
    assert latest["signal_backtest"]["metrics"]["trade_count"] >= 1
    assert latest["reclaim_watchlist"]["schema_version"] == "reclaim_watchlist.v1"
    assert latest["reclaim_transition_study"]["schema_version"] == "reclaim_transition_study.v1"
    assert latest["focus_phase_diagnostics"]["schema_version"] == "focus_phase_diagnostics.v1"
    assert latest["phase_similarity_performance"]["schema_version"] == "phase_similarity_performance.v1"
    assert latest["phase_confidence_walk_forward"]["schema_version"] == "phase_confidence_walk_forward.v1"

    candidate = service.latest_model_candidate()
    assert candidate["run_id"] == result["run_id"]
    assert candidate["artifact"]["artifact_written"] is True
    assert candidate["artifact_detail"]["status"] == "loaded"
    assert candidate["artifact_detail"]["strategy_synthesis"]["review_only"] is True
    assert candidate["artifact_detail"]["usage_policy"]["writes_rules_yaml"] is False
    assert "selected_stable_candidate" in candidate["artifact_detail"]["signal_optimization"]
    assert "signal_loss_attribution" in candidate["artifact_detail"]["signal_optimization"]
    assert "parameter_failure_attribution" in candidate["artifact_detail"]["signal_optimization"]
    assert "shadow_parameter_evidence" in candidate["artifact_detail"]["signal_optimization"]
    assert "learning_filter_candidates" in candidate["artifact_detail"]["signal_optimization"]
    assert candidate["artifact_detail"]["rule_family_review_gate"]["status"] == "passed_for_review"
    assert candidate["artifact_detail"]["rule_family_performance_memory"]["top_backtest_groups"][0]["pattern_id"] == "LEGACY_VP_SINGLE_001"
    assert candidate["artifact_detail"]["candidate_review_priority_framework"]["allowed_effect"] == "review_priority_only"
    assert candidate["artifact_detail"]["candidate_review_priority_framework"]["review_priority_score"] >= 35
    assert candidate["artifact_detail"]["simulation_review_plan"]["schema_version"] == "simulation_review_plan.v1"
    assert candidate["artifact_detail"]["simulation_review_plan"]["permission_policy"]["may_submit_order"] is False
    if candidate["artifact_detail"]["simulation_review_plan"]["candidates"]:
        assert candidate["artifact_detail"]["simulation_review_plan"]["candidates"][0]["evidence_quality"][
            "allowed_effect"
        ] == "confidence_ranking_for_review_only"
    assert candidate["artifact_detail"]["focus_phase_diagnostics"]["schema_version"] == "focus_phase_diagnostics.v1"
    assert candidate["artifact_detail"]["phase_similarity_performance"]["schema_version"] == "phase_similarity_performance.v1"
    assert candidate["artifact_detail"]["phase_confidence_walk_forward"]["schema_version"] == "phase_confidence_walk_forward.v1"


def test_offhour_research_blocks_unsafe_dataset2_strategy_source(clean_store, tmp_path, monkeypatch):
    source_dir = write_dataset2_source(tmp_path, mode="simulation_and_training_only", allow_live_order=True)
    monkeypatch.setattr(offhour, "OffhourPotentialSearchService", lambda: FakePotentialSearch())

    result = OffhourResearchLoopService(
        dataset2_source_dir=source_dir,
        artifact_dir=tmp_path / "output" / "model_candidates",
    ).run(limit=10)

    assert result["status"] == "blocked"
    assert any("unsafe strategy outputs" in reason for reason in result["blocked_reasons"])
    assert result["model_candidate"]["artifact_written"] is False


def test_offhour_research_does_not_fabricate_signals_without_daily_history(
    clean_store, tmp_path, monkeypatch
):
    source_dir = write_dataset2_source(tmp_path)
    monkeypatch.setattr(offhour, "OffhourPotentialSearchService", lambda: FakePotentialSearch(["SH600001"]))

    result = OffhourResearchLoopService(
        dataset2_source_dir=source_dir,
        artifact_dir=tmp_path / "output" / "model_candidates",
    ).run(limit=10, strategy_limit=5, history_days=60, write_artifact=True)

    assert result["status"] == "blocked"
    assert result["daily_bar_coverage"]["status"] == "insufficient_history_data"
    assert result["strategy_replay"]["signal_count"] == 0
    assert result["model_candidate"]["artifact_written"] is False


def test_offhour_history_refresh_reports_bounded_inline_budget(clean_store, tmp_path, monkeypatch):
    source_dir = write_dataset2_source(tmp_path)
    calls = {}

    class FakeDailyBarCache:
        def refresh_bars(self, limit, days):
            calls["limit"] = limit
            calls["days"] = days
            return {"status": "completed", "refreshed": 0}

    monkeypatch.setattr(offhour, "DailyBarCacheService", lambda: FakeDailyBarCache())
    service = OffhourResearchLoopService(
        dataset2_source_dir=source_dir,
        artifact_dir=tmp_path / "output" / "model_candidates",
    )

    result = service._refresh_history(limit=20, days=240, requested_limit=120, requested_days=360)

    assert calls == {"limit": 20, "days": 240}
    assert result["inline_refresh_budget"]["requested_limit"] == 120
    assert result["inline_refresh_budget"]["requested_days"] == 360
    assert result["inline_refresh_budget"]["effective_limit"] == 20
    assert result["inline_refresh_budget"]["effective_days"] == 240


def test_dataset1_confirmation_filter_requires_reclaim(clean_store, tmp_path):
    source_dir = write_dataset2_source(tmp_path)
    service = OffhourResearchLoopService(
        dataset2_source_dir=source_dir,
        artifact_dir=tmp_path / "output" / "model_candidates",
    )
    signal = {"close": 10.0}

    weak_entry = {"open": 10.1, "close": 9.95, "low": 9.9}
    reclaimed_entry = {"open": 10.0, "close": 10.2, "low": 9.8}
    strong_entry = {"open": 10.05, "close": 10.25, "low": 9.9}
    stabilized_entry = {"open": 10.1, "close": 10.06, "low": 9.75}
    broken_entry = {"open": 10.1, "close": 10.08, "low": 9.65}
    risky_signal = {"close": 10.0, "tags": ["top_risk", "volume_up_price_stall"]}
    accumulation_signal = {"close": 10.0, "tags": ["sideways", "small_body", "low_volume"]}

    assert service._confirmation_filter_passes(signal, weak_entry, 10.0, "none") is True
    assert service._confirmation_filter_passes(signal, weak_entry, 10.0, "entry_close_above_signal") is False
    assert service._confirmation_filter_passes(signal, reclaimed_entry, 10.0, "entry_close_above_signal") is True
    assert service._confirmation_filter_passes(signal, reclaimed_entry, 10.0, "entry_green_above_signal") is True
    assert service._confirmation_filter_passes(signal, strong_entry, 10.0, "strong_reclaim") is True
    assert service._confirmation_filter_passes(signal, stabilized_entry, 10.0, "dataset1_stabilized_reclaim") is True
    assert service._confirmation_filter_passes(signal, broken_entry, 10.0, "dataset1_stabilized_reclaim") is False
    assert service._confirmation_filter_passes(
        risky_signal, stabilized_entry, 10.0, "dataset1_low_risk_stabilized_reclaim"
    ) is False
    assert service._confirmation_filter_passes(
        accumulation_signal, stabilized_entry, 10.0, "dataset1_accumulation_reclaim"
    ) is True


def test_signal_attribution_filter_blocks_weak_star_and_turning_point_entries(clean_store, tmp_path):
    service = OffhourResearchLoopService(
        dataset2_source_dir=write_dataset2_source(tmp_path),
        artifact_dir=tmp_path / "output" / "model_candidates",
    )
    weak_reclaim = {"open": 10.1, "close": 10.05, "low": 9.9}
    green_reclaim = {"open": 10.0, "close": 10.05, "low": 9.9}
    strong_reclaim = {"open": 10.0, "close": 10.2, "low": 9.9}
    star_signal = {"symbol": "SH688001", "close": 10.0, "action_label": "SIM_BUY_CANDIDATE"}
    main_board_signal = {"symbol": "SH600001", "close": 10.0, "action_label": "SIM_BUY_CANDIDATE"}
    turning_signal = {
        "symbol": "SH600002",
        "close": 10.0,
        "action_label": "WAIT_CONFIRMATION",
        "tags": ["turning_point"],
    }
    risky_signal = {
        "symbol": "SH600003",
        "close": 10.0,
        "action_label": "SIM_BUY_CANDIDATE",
        "tags": ["volume_up_price_stall"],
    }

    assert service._signal_attribution_filter_passes(
        star_signal, weak_reclaim, 10.0, "star_requires_strong_reclaim"
    ) is False
    assert service._signal_attribution_filter_passes(
        star_signal, strong_reclaim, 10.0, "star_requires_strong_reclaim"
    ) is True
    assert service._signal_attribution_filter_passes(
        main_board_signal, weak_reclaim, 10.0, "star_requires_strong_reclaim"
    ) is True
    assert service._signal_attribution_filter_passes(
        turning_signal, weak_reclaim, 10.0, "turning_point_requires_green_or_strong"
    ) is False
    assert service._signal_attribution_filter_passes(
        turning_signal, green_reclaim, 10.0, "turning_point_requires_green_or_strong"
    ) is True
    assert service._signal_attribution_filter_passes(
        risky_signal, strong_reclaim, 10.0, "block_dataset1_distribution_risk"
    ) is False
    assert service._signal_attribution_filter_passes(
        main_board_signal, weak_reclaim, 10.0, "none"
    ) is True


def test_signal_learning_filter_candidates_are_bounded_and_review_only(clean_store, tmp_path, monkeypatch):
    service = OffhourResearchLoopService(
        dataset2_source_dir=write_dataset2_source(tmp_path),
        artifact_dir=tmp_path / "output" / "model_candidates",
    )
    base_candidate = {
        "parameters": {
            "entry_delay_days": 1,
            "horizon_days": 3,
            "stop_loss_pct": 0.04,
            "take_profit_pct": 0.08,
            "confirmation_filter": "entry_close_above_signal",
        },
        "validation_metrics": {
            "trade_count": 5,
            "win_rate": 0.8,
            "average_return_pct": 3.0,
            "equal_weight_cumulative_return_pct": 30.0,
        },
    }
    train_signals = [{"symbol": f"SH6000{idx}", "signal_date": f"2026-05-{idx:02d}"} for idx in range(1, 7)]
    validation_signals = [
        {"symbol": f"SH6001{idx}", "signal_date": f"2026-05-{idx + 10:02d}"} for idx in range(1, 7)
    ]
    seen_filters = []

    def fake_signal_backtest(*args, signals=None, **kwargs):
        attribution_filter = kwargs.get("attribution_filter") or "none"
        seen_filters.append(attribution_filter)
        params = {
            "entry_delay_days": kwargs.get("entry_delay_days"),
            "horizon_days": kwargs.get("horizon_days"),
            "stop_loss_pct": kwargs.get("stop_loss_pct"),
            "take_profit_pct": kwargs.get("take_profit_pct"),
            "confirmation_filter": kwargs.get("confirmation_filter"),
            "attribution_filter": attribution_filter,
        }
        return {
            "status": "completed",
            "metrics": {
                "trade_count": len(signals or []),
                "win_rate": 0.75,
                "average_return_pct": 2.5,
                "expectancy_pct": 2.0,
                "equal_weight_cumulative_return_pct": 24.0,
            },
            "parameters": params,
            "review_only": True,
            "simulation_only": True,
        }

    monkeypatch.setattr(service, "_signal_backtest", fake_signal_backtest)

    result = service._signal_learning_filter_candidates(
        replay={},
        train_signals=train_signals,
        validation_signals=validation_signals,
        base_candidates=[base_candidate],
        experience_aligned_candidates=[],
    )

    assert result["budget"]["candidate_pool_size"] == 1
    assert result["budget"]["max_grid_size"] == len(offhour.SIGNAL_OPTIMIZATION_ATTRIBUTION_FILTERS) - 1
    assert result["budget"]["accepted_candidate_count"] == len(offhour.SIGNAL_OPTIMIZATION_ATTRIBUTION_FILTERS) - 1
    assert set(seen_filters) == set(offhour.SIGNAL_OPTIMIZATION_ATTRIBUTION_FILTERS) - {"none"}
    assert all(item["review_only"] and item["simulation_only"] for item in result["candidates"])
    assert {item["parameters"]["attribution_filter"] for item in result["candidates"]} == (
        set(offhour.SIGNAL_OPTIMIZATION_ATTRIBUTION_FILTERS) - {"none"}
    )


def test_signal_optimization_sample_uses_recent_signals_and_dedupes(clean_store, tmp_path):
    service = OffhourResearchLoopService(
        dataset2_source_dir=write_dataset2_source(tmp_path),
        artifact_dir=tmp_path / "output" / "model_candidates",
    )
    visible = {
        "symbol": "SH600001",
        "signal_date": "2026-05-01",
        "pattern_id": "VISIBLE_001",
        "action_label": "SIM_BUY_CANDIDATE",
        "score": 0.6,
    }
    duplicate_higher_score = {
        **visible,
        "score": 0.9,
    }
    old_extra = {
        "symbol": "SH600002",
        "signal_date": "2026-04-30",
        "pattern_id": "RECENT_001",
        "action_label": "WAIT_CONFIRMATION",
        "score": 0.7,
    }
    ignored = {
        "symbol": "SH600003",
        "signal_date": "2026-04-29",
        "pattern_id": "RISK_001",
        "action_label": "RISK_ALERT",
        "score": 1.0,
    }

    sample = service._signal_optimization_sample(
        {
            "signals": [visible],
            "recent_signals": [duplicate_higher_score, old_extra, ignored],
        }
    )

    summary = sample["summary"]
    assert summary["source"] == "signals_plus_recent_signals"
    assert summary["primary_actionable_count"] == 1
    assert summary["recent_actionable_count"] == 2
    assert summary["deduped_actionable_count"] == 2
    assert summary["optimized_signal_count"] == 2
    assert [item["symbol"] for item in sample["signals"]] == ["SH600002", "SH600001"]
    assert sample["signals"][1]["score"] == 0.9
    assert summary["review_only"] is True
    assert summary["simulation_only"] is True


def test_signal_walk_forward_validation_requires_stable_folds(clean_store, tmp_path, monkeypatch):
    source_dir = write_dataset2_source(tmp_path)
    service = OffhourResearchLoopService(
        dataset2_source_dir=source_dir,
        artifact_dir=tmp_path / "output" / "model_candidates",
    )
    signals = [
        {
            "symbol": "SH600000",
            "signal_date": f"2026-05-{day:02d}",
            "action_label": "SIM_BUY_CANDIDATE",
        }
        for day in range(1, 19)
    ]

    def fake_signal_backtest(*args, signals=None, **kwargs):
        trade_count = len(signals or [])
        return {
            "status": "completed",
            "metrics": {
                "trade_count": trade_count,
                "win_rate": 0.666667,
                "average_return_pct": 4.0,
                "equal_weight_cumulative_return_pct": 18.0,
            },
            "parameters": {
                "entry_delay_days": kwargs.get("entry_delay_days"),
                "horizon_days": kwargs.get("horizon_days"),
                "stop_loss_pct": kwargs.get("stop_loss_pct"),
                "take_profit_pct": kwargs.get("take_profit_pct"),
                "confirmation_filter": kwargs.get("confirmation_filter"),
                "attribution_filter": kwargs.get("attribution_filter"),
            },
        }

    monkeypatch.setattr(service, "_signal_backtest", fake_signal_backtest)
    result = service._signal_walk_forward_validation(
        replay={},
        signals=signals,
        candidates=[
            {
                "parameters": {
                    "entry_delay_days": 2,
                    "horizon_days": 5,
                    "stop_loss_pct": 0.04,
                    "take_profit_pct": 0.12,
                    "confirmation_filter": "dataset1_stabilized_reclaim",
                }
            }
        ],
    )

    assert result["status"] == "passed_for_simulation_review"
    assert result["gate"]["writes_rules_yaml"] is False
    assert result["gate"]["auto_apply"] is False
    assert result["best"]["fold_count"] >= 3
    assert result["best"]["weighted_win_rate"] >= 0.58


def test_strategy_learning_packet_combines_dataset1_dataset2_and_candidates(clean_store, tmp_path, monkeypatch):
    def fake_latest_model_candidate(self):
        return {
            "run_id": 84,
            "artifact": {"artifact_written": True, "artifact_path": "ignored.json"},
            "artifact_detail": {
                "status": "loaded",
                "signal_optimization": {
                    "selected_stable_candidate": {
                        "status": "passed_for_simulation_review",
                        "parameters": {"entry_delay_days": 1, "horizon_days": 5},
                        "validation_return_pct": 203.4,
                        "validation_win_rate": 0.8,
                        "walk_forward_return_pct": 2420.6,
                        "walk_forward_win_rate": 0.82,
                    },
                    "signal_loss_attribution": {"top_loss_reason": "early_chase"},
                    "parameter_failure_attribution": {"failed_filter": "none"},
                    "learning_filter_candidates": [{"name": "avoid_late_distribution"}],
                },
                "rule_family_review_gate": {
                    "status": "passed_for_review",
                    "writes_rules_yaml": False,
                },
                "candidate_review_priority_framework": {
                    "status": "ready",
                    "review_priority_score": 88,
                    "review_priority_tier": "high_review_priority",
                    "allowed_effect": "review_priority_only",
                },
                "rule_family_performance_memory": {
                    "top_backtest_groups": [
                        {
                            "pattern_id": "LEGACY_VP_SINGLE_001",
                            "pattern_name": "放量大阳线",
                            "action_label": "SIM_BUY_CANDIDATE",
                            "risk_level": "medium",
                            "trade_count": 37,
                            "win_rate": 0.648649,
                            "average_return_pct": 3.801449,
                            "total_return_pct": 140.653628,
                            "worst_return_pct": -5.167749,
                            "review_priority_score": 76.028988,
                            "symbols": ["SH603120", "SZ002806"],
                        }
                    ]
                },
                "strategy_synthesis": {
                    "dataset1_playbook": ["separate accumulation and distribution"],
                    "dual_track_guidance": {"positioning_rule": "staged only"},
                    "active_simulation_hypothesis": {
                        "summary": "Dataset2 proposes, Dataset1 filters late entries."
                    },
                },
                "focus_phase_diagnostics": {
                    "supervision": {"next_actions": ["Use Sanwei as pre-markup sample."]}
                },
                "phase_similarity_performance": {
                    "by_group": [
                        {
                            "key": "SZ002115:post_distribution_watch",
                            "core_symbol": "SZ002115",
                            "target_latest_phase": "post_distribution_watch",
                            "sample_role": "training",
                            "confidence_tier": "late_cycle_low_confidence_observe_or_smallest_dry_run",
                            "confidence_score": 55,
                            "win_rate": 0.75,
                            "average_close_return_pct": 1.7,
                            "average_min_return_pct": -0.8,
                            "suggested_treatment": "downgrade_to_smallest_dry_run_or_observe",
                            "downside_risk_note": "shallow downside",
                        }
                    ]
                },
                "phase_confidence_walk_forward": {
                    "status": "blocked",
                    "passed_group_count": 0,
                    "reason": "no_high_or_medium_phase_confidence_groups",
                },
            },
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": False,
        }

    def fake_latest_simulation_review_plan(self, limit=8):
        return {
            "schema_version": "latest_simulation_review_plan.v1",
            "status": "ready_for_dry_run_review",
            "run_id": 84,
            "candidate_count": 1,
            "ready_dry_run_candidate_count": 1,
            "candidates": [
                {
                    "symbol": "SH603120",
                    "recommended_mode": "dry_run_screen_candidate",
                    "signal_date": "2026-06-11",
                    "pattern_id": "LEGACY_VP_SINGLE_001",
                    "action_label": "SIM_BUY_CANDIDATE",
                    "risk_level": "medium",
                    "close": 52.58,
                    "priority_score": 182.84,
                    "confidence_adjusted_priority_score": 151.76,
                    "evidence_quality": {
                        "confidence_tier": "high_confidence_dry_run_review",
                        "confidence_score": 83,
                    },
                    "position_plan": {"max_initial_cash": 4000, "max_initial_position_ratio": 0.02},
                    "best_strategy": {
                        "experiment_id": "strong_reclaim_exclude_benchmark_neutral",
                        "win_rate": 0.8,
                        "average_return_pct": 11.2,
                        "walk_forward_status": "passed_for_simulation_review",
                    },
                    "blockers": [],
                    "caution_flags": [],
                    "review_only": True,
                    "simulation_only": True,
                    "live_trading_enabled": False,
                }
            ],
            "permission_policy": {"may_submit_order": False, "may_enable_screen_click": False},
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": False,
        }

    monkeypatch.setattr(OffhourResearchLoopService, "latest_model_candidate", fake_latest_model_candidate)
    monkeypatch.setattr(
        OffhourResearchLoopService,
        "latest_simulation_review_plan",
        fake_latest_simulation_review_plan,
    )
    for date_value, close in [
        ("2026-06-12", 53.5),
        ("2026-06-15", 54.0),
        ("2026-06-16", 55.0),
        ("2026-06-17", 56.0),
        ("2026-06-18", 57.0),
    ]:
        insert_bar(clean_store, "SH603120", date_value, 52.5, close + 0.5, 52.0, close)

    packet = OffhourResearchLoopService().latest_strategy_learning_packet(limit=5)

    assert packet["schema_version"] == "offhour_strategy_learning_supervisor_packet.v1"
    assert packet["status"] == "ready"
    assert packet["learning_readiness"] == "ready_for_supervised_dry_run_learning"
    assert packet["promotion_gate"]["passed_20pct_review_gate"] is True
    assert packet["promotion_gate"]["human_confirm_readiness"]["status"] == "not_ready_for_human_confirm"
    assert "supervised_dry_run_samples" in packet["promotion_gate"]["human_confirm_readiness"][
        "missing_requirements"
    ]
    confidence = packet["confidence_calibration"]
    assert confidence["schema_version"] == "strategy_learning_confidence_calibration.v1"
    assert confidence["score"] == 75.0
    assert confidence["tier"] == "backtest_ready_simulation_needed"
    assert confidence["allowed_effect"] == "confidence_reporting_only"
    assert confidence["component_scores"]["offline_strategy_evidence"] == 35
    assert confidence["component_scores"]["simulation_execution_evidence"] == 0
    assert "supervised_dry_run_samples" in confidence["top_blockers"]
    training_plan = packet["simulation_training_plan"]
    assert training_plan["schema_version"] == "strategy_learning_simulation_training_plan.v1"
    assert training_plan["status"] == "needs_supervised_samples"
    assert training_plan["remaining_requirements"]["dry_run_samples"] == 20
    assert training_plan["remaining_requirements"]["readbacks"] == 20
    assert training_plan["candidate_queue"][0]["symbol"] == "SH603120"
    assert training_plan["candidate_queue"][0]["target_next_dry_run_samples"] == 20
    assert training_plan["candidate_queue"][0]["allowed_effect"] == "sample_collection_instruction_only"
    assert "sim_cockpit_window_verified" in training_plan["candidate_queue"][0]["requires"]
    assert "insufficient_candidate_symbol_diversity_for_target" in training_plan["warnings"]
    assert packet["simulation_training_evidence"]["dry_run_count"] == 0
    assert packet["simulation_training_targets"]["min_supervised_dry_run_samples"] == 20
    assert packet["permission_policy"]["may_submit_order"] is False
    assert packet["permission_policy"]["may_enable_screen_click"] is False
    assert packet["permission_policy"]["may_open_real_money_human_confirm"] is False
    scoring = packet["strategy_scoring_matrix"]
    assert scoring["schema_version"] == "strategy_learning_scoring_matrix.v1"
    assert scoring["status"] == "ready"
    assert scoring["top_symbol"] == "SH603120"
    assert scoring["permission_policy"]["may_change_strategy_weight_now"] is False
    assert scoring["permission_policy"]["may_submit_order"] is False
    assert scoring["permission_policy"]["may_enable_screen_click"] is False
    assert scoring["top_candidates"][0]["tier"] == "high_priority_supervised_dry_run"
    assert scoring["top_candidates"][0]["components"]["phase_score"]["score"] == 20
    assert scoring["top_candidates"][0]["components"]["risk_penalty"]["score"] == 0
    assert scoring["target_alignment"]["offline_20pct_gate_passed"] is True
    assert scoring["target_alignment"]["top_candidate_supports_20pct_goal"] is True
    assert scoring["target_alignment"]["top_candidate_strategy_win_rate"] == 0.8
    assert scoring["target_alignment"]["top_candidate_strategy_average_return_pct"] == 11.2
    assert scoring["top_candidates"][0]["outcome_evidence"]["supports_20pct_goal"] is True
    assert scoring["top_candidates"][0]["outcome_evidence"]["requires_supervised_outcome_review"] is True
    assert scoring["top_candidates"][0]["may_change_strategy_weight_now"] is False
    shadow = packet["candidate_shadow_outcome_review"]
    assert shadow["schema_version"] == "strategy_candidate_shadow_outcome_review.v1"
    assert shadow["status"] == "ready"
    assert shadow["evaluated_count"] == 1
    assert shadow["win_rate_5d"] == 1.0
    assert shadow["counts_toward_human_confirm"] is False
    assert shadow["allowed_effect"] == "historical_shadow_review_only"
    assert shadow["outcomes"][0]["counts_toward_human_confirm"] is False
    assert packet["evidence_summary"]["rule_family_top_groups"][0]["pattern_id"] == "LEGACY_VP_SINGLE_001"
    assert packet["candidates"][0]["symbol"] == "SH603120"
    assert "highest_evidence_quality_candidate" in packet["candidates"][0]["why_prioritized"]
    assert "record_execution_readback_for_dataset2" in packet["candidates"][0]["next_session_validation"]
    assert packet["candidates"][0]["training_contract"]["sample_mode"] == "detect_only_then_dry_run_screen"
    assert packet["candidates"][0]["training_contract"]["allowed_effect"] == "training_sample_collection_only"
    assert packet["review_only"] is True
    assert packet["simulation_only"] is True
    assert packet["live_trading_enabled"] is False


def test_strategy_learning_packet_evaluates_sim_cockpit_dry_run_outcomes(clean_store, tmp_path, monkeypatch):
    with clean_store.connect() as conn:
        conn.execute("DELETE FROM sim_cockpit_readbacks")
        conn.execute("DELETE FROM sim_cockpit_actions")
        for idx in range(5):
            cursor = conn.execute(
                """
                INSERT INTO sim_cockpit_actions(
                    action_type, status, symbol, price, quantity, signal_source,
                    risk_result_json, request_json, execution_json,
                    blocked_reasons_json, requested_by, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "buy",
                    "dry_run",
                    "SH603120",
                    10.0,
                    100,
                    "offhour_simulation_review_plan",
                    "{}",
                    "{}",
                    "{}",
                    "[]",
                    "pytest",
                    f"2026-06-10 09:{30 + idx:02d}:00",
                ),
            )
            action_id = int(cursor.lastrowid)
            conn.execute(
                """
                INSERT INTO sim_cockpit_readbacks(
                    action_id, readback_type, status, symbol, price, quantity,
                    payload_json, simulation_only, live_trading_enabled
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    action_id,
                    "execution_result",
                    "dry_run",
                    "SH603120",
                    10.0,
                    100,
                    "{}",
                    1,
                    0,
                ),
            )

    for date_value, close in [
        ("2026-06-11", 10.4),
        ("2026-06-12", 10.8),
        ("2026-06-15", 11.1),
        ("2026-06-16", 11.2),
        ("2026-06-17", 11.3),
    ]:
        insert_bar(clean_store, "SH603120", date_value, 10.0, close + 0.2, 9.9, close)

    def fake_latest_model_candidate(self):
        return {
            "run_id": 84,
            "artifact": {"artifact_written": True, "artifact_path": "ignored.json"},
            "artifact_detail": {
                "status": "loaded",
                "signal_optimization": {
                    "selected_stable_candidate": {
                        "status": "passed_for_simulation_review",
                        "validation_return_pct": 203.4,
                        "validation_win_rate": 0.8,
                    }
                },
                "candidate_review_priority_framework": {
                    "review_priority_tier": "high_review_priority",
                    "review_priority_score": 88,
                },
                "rule_family_performance_memory": {},
                "strategy_synthesis": {"active_simulation_hypothesis": {"summary": "fixture"}},
            },
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": False,
        }

    def fake_latest_simulation_review_plan(self, limit=8):
        return {
            "schema_version": "latest_simulation_review_plan.v1",
            "status": "ready_for_dry_run_review",
            "run_id": 84,
            "candidates": [
                {
                    "symbol": "SH603120",
                    "recommended_mode": "dry_run_screen_candidate",
                    "close": 10.0,
                    "evidence_quality": {
                        "confidence_tier": "high_confidence_dry_run_review",
                        "confidence_score": 83,
                    },
                    "position_plan": {"max_initial_cash": 4000},
                    "best_strategy": {"win_rate": 0.8, "average_return_pct": 11.2},
                    "blockers": [],
                    "caution_flags": [],
                    "review_only": True,
                    "simulation_only": True,
                    "live_trading_enabled": False,
                }
            ],
            "permission_policy": {"may_submit_order": False, "may_enable_screen_click": False},
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": False,
        }

    monkeypatch.setattr(OffhourResearchLoopService, "latest_model_candidate", fake_latest_model_candidate)
    monkeypatch.setattr(
        OffhourResearchLoopService,
        "latest_simulation_review_plan",
        fake_latest_simulation_review_plan,
    )

    service = OffhourResearchLoopService()
    assert len(service._future_daily_bars("SH603120", "2026-06-10", limit=5)) == 5

    packet = service.latest_strategy_learning_packet(limit=5)
    evidence = packet["simulation_training_evidence"]
    outcome = evidence["outcome_review"]

    assert evidence["dry_run_count"] == 5
    assert evidence["readback_count"] == 5
    assert outcome["evaluated_session_count"] == 5
    assert outcome["win_rate_5d"] == 1.0
    assert outcome["average_return_pct_5d"] == 13.0
    assert outcome["average_max_drawdown_pct"] == -1.0
    assert packet["confidence_calibration"]["component_scores"]["simulation_outcome_evidence"] == 10
    assert packet["confidence_calibration"]["tier"] == "backtest_ready_simulation_needed"
    training_plan = packet["simulation_training_plan"]
    assert training_plan["remaining_requirements"]["dry_run_samples"] == 15
    assert training_plan["remaining_requirements"]["readbacks"] == 15
    assert training_plan["remaining_requirements"]["evaluated_sessions"] == 0
    assert training_plan["candidate_queue"][0]["target_next_dry_run_samples"] == 15
    assert packet["promotion_gate"]["human_confirm_readiness"]["status"] == "not_ready_for_human_confirm"
    assert "supervised_dry_run_samples" in packet["promotion_gate"]["human_confirm_readiness"][
        "missing_requirements"
    ]


def test_offhour_research_api_smoke(client, monkeypatch):
    monkeypatch.setattr(
        OffhourResearchLoopService,
        "run",
        lambda self, **kwargs: {
            "run_id": 99,
            "status": "completed",
            "strategy_replay": {"signal_count": 1},
            "sandbox": {"evaluated_count": 1},
            "model_candidate": {"artifact_written": False, "status": "skipped"},
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": False,
        },
    )
    monkeypatch.setattr(
        OffhourResearchLoopService,
        "latest_simulation_review_plan",
        lambda self, limit=12: {
            "schema_version": "latest_simulation_review_plan.v1",
            "status": "ready_for_dry_run_review",
            "candidate_count": 1,
            "ready_dry_run_candidate_count": 1,
            "candidates": [
                {
                    "symbol": "SH603330",
                    "recommended_mode": "dry_run_screen_candidate",
                    "blockers": [],
                    "position_plan": {"max_initial_cash": 4000.0},
                    "review_only": True,
                    "simulation_only": True,
                    "live_trading_enabled": False,
                }
            ],
            "permission_policy": {
                "may_submit_order": False,
                "may_enable_screen_click": False,
            },
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": False,
        },
    )
    monkeypatch.setattr(
        OffhourResearchLoopService,
        "latest_strategy_learning_packet",
        lambda self, limit=8: {
            "schema_version": "offhour_strategy_learning_supervisor_packet.v1",
            "status": "ready",
            "learning_readiness": "ready_for_supervised_dry_run_learning",
            "candidate_count": 1,
            "candidates": [{"symbol": "SH603330", "review_only": True, "simulation_only": True}],
            "permission_policy": {
                "may_submit_order": False,
                "may_enable_screen_click": False,
                "may_write_rules_yaml": False,
            },
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": False,
        },
    )
    monkeypatch.setattr(
        OffhourResearchLoopService,
        "latest_run",
        lambda self: {
            "run_id": 99,
            "status": "completed",
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": False,
        },
    )
    monkeypatch.setattr(
        OffhourResearchLoopService,
        "get_run",
        lambda self, run_id: {
            "run_id": run_id,
            "status": "completed",
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": False,
        }
        if run_id == 99
        else None,
    )
    monkeypatch.setattr(
        OffhourResearchLoopService,
        "latest_model_candidate",
        lambda self: {
            "status": "ready_for_review",
            "artifact_written": False,
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": False,
        },
    )
    response = client.get("/api/research/offhour/capabilities")
    assert response.status_code == 200
    assert response.json()["simulation_only"] is True

    response = client.post("/api/research/offhour/run", json={"limit": 10, "strategy_limit": 5})
    assert response.status_code == 200
    assert response.json()["run_id"] == 99

    response = client.get("/api/research/offhour/runs/latest")
    assert response.status_code == 200
    assert response.json()["run_id"] == 99
    assert response.json()["review_only"] is True

    monkeypatch.setattr(OffhourResearchLoopService, "latest_run", lambda self: None)
    response = client.get("/api/research/offhour/runs/latest")
    assert response.status_code == 200
    assert response.json() == {
        "status": "empty",
        "review_only": True,
        "simulation_only": True,
        "live_trading_enabled": False,
    }

    response = client.get("/api/research/offhour/runs/99")
    assert response.status_code == 200
    assert response.json()["run_id"] == 99
    assert response.json()["simulation_only"] is True

    response = client.get("/api/research/offhour/runs/404")
    assert response.status_code == 404
    assert response.json()["detail"] == "Offhour research run not found"

    response = client.get("/api/research/offhour/model-candidates/latest")
    assert response.status_code == 200
    assert response.json()["status"] == "ready_for_review"
    assert response.json()["live_trading_enabled"] is False

    response = client.get("/api/research/offhour/simulation-review-plan/latest?limit=5")
    assert response.status_code == 200
    plan = response.json()
    assert plan["schema_version"] == "latest_simulation_review_plan.v1"
    assert plan["status"] == "ready_for_dry_run_review"
    assert plan["permission_policy"]["may_submit_order"] is False
    assert plan["permission_policy"]["may_enable_screen_click"] is False
    assert plan["candidates"][0]["recommended_mode"] == "dry_run_screen_candidate"

    response = client.get("/api/research/offhour/strategy-learning-packet/latest?limit=5")
    assert response.status_code == 200
    packet = response.json()
    assert packet["schema_version"] == "offhour_strategy_learning_supervisor_packet.v1"
    assert packet["permission_policy"]["may_submit_order"] is False
    assert packet["permission_policy"]["may_enable_screen_click"] is False
    assert packet["review_only"] is True
    assert packet["simulation_only"] is True

    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["live_trading_enabled"] is False
