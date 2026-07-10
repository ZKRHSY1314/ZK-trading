from __future__ import annotations

import json

import pandas as pd

from app.agent_control.learning_extraction import AgentLearningExtractionService
from app.agent_control.outcome_labeling import OutcomeLabelingService
from app.agent_control.signal_performance import SignalPerformanceService
from app.agent_control.training_feedback import TrainingFeedbackModule


def _reset(store) -> None:
    with store.connect() as conn:
        for table in [
            "agent_learning_outcomes",
            "agent_learning_samples",
            "agent_control_events",
            "agent_control_tasks",
            "automation_events",
            "automation_runs",
            "daily_bar_cache",
        ]:
            conn.execute(f"DELETE FROM {table}")


def _insert_task(store, task_type: str, result: dict) -> int:
    with store.connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO agent_control_tasks(
                task_type, status, requested_by, result_json,
                approval_status, completed_at
            ) VALUES (?, 'completed', 'pytest', ?, 'auto_approved', CURRENT_TIMESTAMP)
            """,
            (task_type, json.dumps(result, ensure_ascii=False)),
        )
        return int(cursor.lastrowid)


def _insert_sample(store, symbol: str, signal_date: str) -> int:
    with store.connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO agent_learning_samples(
                source_task_id, sample_type, symbol, features_json,
                decision_json, risk_flags_json, label, label_source
            ) VALUES (999, 'fixture', ?, ?, '{}', '[]', 'candidate', 'pytest')
            """,
            (symbol, json.dumps({"signal_date": signal_date})),
        )
        return int(cursor.lastrowid)


def _insert_bars(store, symbol: str, rows: list[tuple[str, float, float, float]]) -> None:
    with store.connect() as conn:
        for trade_date, close, high, low in rows:
            conn.execute(
                """
                INSERT INTO daily_bar_cache(
                    symbol, trade_date, open, high, low, close,
                    volume, amount, source, quality_status
                ) VALUES (?, ?, ?, ?, ?, ?, 1000, 1000000, 'fixture', 'ready')
                """,
                (symbol, trade_date, close, high, low, close),
            )


def test_full_simulation_cycle_extracts_plan_event(test_db):
    _reset(test_db)
    with test_db.connect() as conn:
        run_id = int(
            conn.execute(
                "INSERT INTO automation_runs(mode, status) VALUES ('cycle', 'completed')"
            ).lastrowid
        )
        conn.execute(
            """
            INSERT INTO automation_events(run_id, event_type, symbol, payload_json)
            VALUES (?, 'simulation_plan_created', 'SH600000', ?)
            """,
            (
                run_id,
                json.dumps(
                    {
                        "snapshot": {
                            "symbol": "SH600000",
                            "name": "fixture",
                            "trade_date": "2026-01-02",
                            "price": 10.0,
                        },
                        "decision": {
                            "score": 100.0,
                            "raw_score": 45.0,
                            "max_score": 45.0,
                            "tier": "strong",
                        },
                        "plan": {"symbol": "SH600000", "action": "observe", "allowed": True},
                        "risk_blocked": [],
                    },
                    ensure_ascii=False,
                ),
            ),
        )
    task_id = _insert_task(
        test_db,
        "full_simulation_cycle",
        {"automation": {"run_id": run_id, "summary": {"items": []}}},
    )

    result = AgentLearningExtractionService(store=test_db).extract_from_task(task_id)

    assert result["created_count"] == 1
    sample = test_db.fetch_one(
        "SELECT * FROM agent_learning_samples WHERE source_task_id = ?", (task_id,)
    )
    features = json.loads(sample["features_json"])
    assert sample["sample_type"] == "full_simulation_cycle"
    assert sample["label"] == "simulation_plan_created"
    assert features["signal_date"] == "2026-01-02"
    assert features["decision_raw_score"] == 45.0


def test_public_opinion_capture_extracts_sector_context(test_db):
    _reset(test_db)
    task_id = _insert_task(
        test_db,
        "public_opinion_capture",
        {
            "run_id": 7,
            "status": "completed",
            "source_count": 3,
            "item_count": 8,
            "sector_count": 2,
            "sector_signals": [
                {"sector": "ai_compute", "heat_score": 55, "risk_count": 0},
                {"sector": "medicine", "heat_score": 12, "risk_count": 1},
            ],
            "review_only": True,
            "simulation_only": True,
        },
    )

    result = AgentLearningExtractionService(store=test_db).extract_from_task(task_id)

    assert result["created_count"] == 1
    sample = test_db.fetch_one(
        "SELECT * FROM agent_learning_samples WHERE source_task_id = ?", (task_id,)
    )
    features = json.loads(sample["features_json"])
    assert sample["label"] == "sector_context_ready"
    assert features["top_sectors"][0]["sector"] == "ai_compute"
    assert json.loads(sample["risk_flags_json"]) == ["sector_risk:medicine"]


def test_recent_extraction_processes_oldest_unprocessed_task_first(test_db):
    _reset(test_db)
    oldest_id = _insert_task(
        test_db,
        "potential_search",
        {"items": [{"symbol": "SH600040", "signal_date": "2026-01-02"}]},
    )
    newest_id = _insert_task(
        test_db,
        "potential_search",
        {"items": [{"symbol": "SH600041", "signal_date": "2026-01-03"}]},
    )
    service = AgentLearningExtractionService(store=test_db)

    first = service.extract_from_recent(limit=1)
    second = service.extract_from_recent(limit=1)

    assert first["details"][0]["task_id"] == oldest_id
    assert second["details"][0]["task_id"] == newest_id


def test_zero_sample_task_gets_processed_marker(test_db):
    _reset(test_db)
    task_id = _insert_task(test_db, "potential_search", {"items": []})
    service = AgentLearningExtractionService(store=test_db)

    first = service.extract_from_recent(limit=1)
    second = service.extract_from_recent(limit=1)

    assert first["details"][0]["task_id"] == task_id
    assert first["total_created"] == 0
    assert second["tasks_processed"] == 0
    marker = test_db.fetch_one(
        """
        SELECT id FROM agent_control_events
        WHERE task_id = ? AND event_type = 'learning_extraction_processed'
        """,
        (task_id,),
    )
    assert marker is not None


def test_outcome_labeling_prefers_local_daily_bar_cache(test_db):
    _reset(test_db)
    sample_id = _insert_sample(test_db, "SH600001", "2026-01-02")
    _insert_bars(
        test_db,
        "SH600001",
        [
            ("2026-01-02", 10.0, 10.1, 9.9),
            ("2026-01-05", 10.4, 10.6, 10.0),
            ("2026-01-06", 10.8, 11.1, 10.3),
        ],
    )

    class NeverCalledProvider:
        calls = 0

        def get_daily_bars(self, symbol: str):
            self.calls += 1
            raise AssertionError("local cache should satisfy the horizon")

    provider = NeverCalledProvider()
    outcome = OutcomeLabelingService(store=test_db, provider=provider).label_sample(
        sample_id, horizon_days=2
    )

    assert provider.calls == 0
    assert outcome["outcome_label"] == "strong_follow_through"
    assert outcome["metrics"]["data_source"] == "daily_bar_cache"


def test_outcome_labeling_accepts_standard_akshare_chinese_columns(test_db):
    _reset(test_db)
    sample_id = _insert_sample(test_db, "SZ000002", "2026-01-02")

    class ChineseColumnProvider:
        calls = 0

        def get_daily_bars(self, symbol: str):
            self.calls += 1
            return pd.DataFrame(
                {
                    "日期": ["2026-01-02", "2026-01-05", "2026-01-06"],
                    "收盘": [10.0, 10.2, 10.3],
                    "最高": [10.1, 10.3, 10.4],
                    "最低": [9.9, 10.0, 10.1],
                }
            )

    provider = ChineseColumnProvider()
    service = OutcomeLabelingService(store=test_db, provider=provider)
    outcome = service.label_sample(sample_id, horizon_days=2)
    repeated = service.label_sample(sample_id, horizon_days=2)

    assert provider.calls == 1
    assert outcome["outcome_label"] == "mild_follow_through"
    assert repeated["id"] == outcome["id"]
    assert outcome["metrics"]["data_source"] == "akshare_fallback"


def test_training_feedback_run_marks_small_resolved_sample_set_insufficient(test_db):
    _reset(test_db)
    _insert_task(
        test_db,
        "potential_search",
        {
            "items": [
                {
                    "symbol": "SH600010",
                    "name": "fixture",
                    "signal_date": "2026-07-10",
                    "current_price": 10.0,
                    "potential_score": 25.0,
                    "lifecycle_state": "pending_review",
                }
            ]
        },
    )
    _insert_bars(
        test_db,
        "SH600010",
        [
            ("2026-07-10", 10.0, 10.1, 9.9),
            ("2026-07-13", 10.2, 10.3, 10.0),
            ("2026-07-14", 10.4, 10.5, 10.1),
        ],
    )

    result = TrainingFeedbackModule(store=test_db).run(limit=10, horizon_days=2)

    assert result["steps"]["extract_recent"]["total_created"] == 1
    assert result["resolved_market_sample_count"] == 1
    assert result["status"] == "insufficient_samples"
    assert "insufficient_resolved_market_samples" in result["blocked_reasons"]
    assert result["scoring_rules_mutated"] is False
    assert result["model_activated"] is False


def test_outcome_labeling_prioritizes_mature_pending_samples(test_db):
    _reset(test_db)
    mature_id = _insert_sample(test_db, "SH600020", "2026-01-02")
    future_id = _insert_sample(test_db, "SH600021", "2099-01-02")
    _insert_bars(
        test_db,
        "SH600020",
        [
            ("2026-01-02", 10.0, 10.1, 9.9),
            ("2026-01-05", 10.5, 10.6, 10.0),
        ],
    )
    with test_db.connect() as conn:
        conn.execute(
            """
            INSERT INTO agent_learning_outcomes(
                sample_id, symbol, horizon_days, outcome_label, risk_outcome,
                metrics_json, updated_at
            ) VALUES (?, 'SH600020', 1, 'pending_future_data', 'unknown', '{}', '2000-01-01')
            """,
            (mature_id,),
        )

    result = OutcomeLabelingService(store=test_db).label_recent(limit=1, horizon_days=1)

    assert result["outcomes"][0]["sample_id"] == mature_id
    assert result["outcomes"][0]["outcome_label"] != "pending_future_data"
    assert test_db.fetch_one(
        "SELECT id FROM agent_learning_outcomes WHERE sample_id = ?", (future_id,)
    ) is None


def test_training_feedback_counts_distinct_resolved_samples(test_db):
    _reset(test_db)
    sample_id = _insert_sample(test_db, "SH600030", "2026-01-01")
    _insert_bars(
        test_db,
        "SH600030",
        [
            (
                (pd.Timestamp("2026-01-01") + pd.Timedelta(days=index)).strftime("%Y-%m-%d"),
                10.0 + index * 0.1,
                10.2 + index * 0.1,
                9.9 + index * 0.1,
            )
            for index in range(11)
        ],
    )
    service = OutcomeLabelingService(store=test_db)
    for horizon in range(1, 11):
        service.label_sample(sample_id, horizon_days=horizon)

    snapshot = TrainingFeedbackModule(store=test_db).snapshot()

    assert snapshot["outcome_count"] == 1
    assert snapshot["all_horizon_outcome_count"] == 10
    assert snapshot["horizon_days"] == 5
    assert snapshot["resolved_market_sample_count"] == 1
    assert snapshot["status"] == "insufficient_samples"
    performance = SignalPerformanceService(store=test_db).performance_summary(horizon_days=5)
    assert performance["total_samples_with_outcomes"] == 1
    assert performance["horizon_days"] == 5
