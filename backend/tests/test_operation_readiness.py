from __future__ import annotations

from datetime import date, timedelta
import json

from app.config import settings
from app.operations.readiness import OperationReadinessService


def _reset(store) -> None:
    with store.connect() as conn:
        for table in [
            "daily_bar_cache",
            "candidate_lifecycle",
            "stock_profiles",
            "auto_discovered_candidates",
            "potential_search_items",
            "realtime_market_events",
            "candidate_scores",
            "potential_search_runs",
            "automation_events",
            "automation_runs",
            "learning_samples",
            "historical_backtest_runs",
            "historical_backtest_trades",
            "historical_backtest_closed_trades",
            "sim_cockpit_window_verifications",
            "sim_cockpit_actions",
            "sim_cockpit_readbacks",
            "simulation_fills",
            "simulation_positions",
            "public_opinion_items",
            "public_opinion_sector_signals",
            "public_opinion_runs",
        ]:
            conn.execute(f"DELETE FROM {table}")


def _seed_ready_state(store) -> None:
    today = date.today()
    with store.connect() as conn:
        for idx in range(40):
            trade_date = today - timedelta(days=39 - idx)
            close = 10 + idx * 0.05
            conn.execute(
                """
                INSERT INTO daily_bar_cache(
                    symbol, trade_date, open, high, low, close, volume, amount,
                    source, quality_status, updated_at
                )
                VALUES ('SZ301099', ?, ?, ?, ?, ?, ?, ?, 'pytest', 'ready', ?)
                """,
                (
                    trade_date.isoformat(),
                    close * 0.99,
                    close * 1.02,
                    close * 0.98,
                    close,
                    1_000_000 + idx * 1_000,
                    80_000_000,
                    f"{today.isoformat()}T15:00:00",
                ),
            )
        conn.execute(
            """
            INSERT INTO candidate_scores(
                symbol, name, total_score, discovery_score, volume_score,
                phase_score, lifecycle_score, focus_score, risk_penalty,
                rating, state, source, reasons_json, components_json, raw_json
            )
            VALUES (
                'SZ301099', 'AI芯片设备', 82, 12, 12,
                15, 12, 8, 3, 'review', 'pending_review',
                'pytest', '[]', '{}', '{"market_cap_billion": 90}'
            )
            """
        )
        conn.execute(
            """
            INSERT INTO potential_search_runs(
                status, source, total_scanned, stored_count, scored_count,
                errors_json, summary_json, completed_at
            )
            VALUES ('completed', 'pytest', 10, 1, 1, '[]', '{}', CURRENT_TIMESTAMP)
            """
        )
        cursor = conn.execute(
            """
            INSERT INTO automation_runs(mode, status, summary_json, completed_at)
            VALUES ('operation_readiness_fixture', 'completed', '{"status": "completed"}', CURRENT_TIMESTAMP)
            """
        )
        run_id = cursor.lastrowid
        conn.execute(
            """
            INSERT INTO automation_events(run_id, event_type, symbol, payload_json)
            VALUES (?, 'fixture_completed', 'SZ301099', '{}')
            """,
            (run_id,),
        )
        conn.execute(
            """
            INSERT INTO learning_samples(
                id, source_type, source_id, symbol, name, label, outcome_score,
                features_json, lessons_json, raw_json
            )
            VALUES (
                'readiness-sample-1', 'pytest', '1', 'SZ301099',
                'AI芯片设备', 'watch_success', 1.0, '{}', '[]', '{}'
            )
            """
        )
        conn.execute(
            """
            INSERT INTO historical_backtest_runs(
                config_json, data_source, start_date, end_date, status,
                benchmark_symbol, initial_cash, final_cash, metrics_json,
                benchmark_json, execution_warnings_json, completed_at
            )
            VALUES (
                '{}', 'pytest', ?, ?, 'completed', 'SH000300',
                200000, 212000, ?, '{"status": "ready"}', '[]', CURRENT_TIMESTAMP
            )
            """,
            (
                (today - timedelta(days=30)).isoformat(),
                today.isoformat(),
                json.dumps({"trade_count": 3, "average_return_pct": 6.0}),
            ),
        )
        cursor = conn.execute(
            """
            INSERT INTO public_opinion_runs(
                status, source_count, item_count, sector_count,
                summary_json, review_only, simulation_only, live_trading_enabled,
                completed_at
            )
            VALUES ('completed', 1, 2, 1, '{}', 1, 1, 0, CURRENT_TIMESTAMP)
            """
        )
        opinion_run_id = cursor.lastrowid
        conn.execute(
            """
            INSERT INTO public_opinion_sector_signals(
                run_id, sector, heat_score, item_count, positive_count,
                policy_count, market_count, risk_count, keywords_json,
                evidence_json, suggested_action
            )
            VALUES (?, 'ai_compute', 56, 2, 2, 1, 1, 0, ?, ?, 'sector_watch_review_only')
            """,
            (
                opinion_run_id,
                json.dumps(["AI", "芯片"], ensure_ascii=False),
                json.dumps([{"title": "AI芯片政策支持", "score": 20}], ensure_ascii=False),
            ),
        )


def test_operation_readiness_reports_ready_from_current_evidence(test_db):
    _reset(test_db)
    _seed_ready_state(test_db)

    report = OperationReadinessService(store=test_db).report(selection_limit=1)

    assert report["schema_version"] == "operation_readiness.v1"
    assert report["status"] == "ready_for_controlled_review_run"
    assert report["review_only"] is True
    assert report["simulation_only"] is True
    assert report["live_trading_enabled"] is False
    assert report["blocking_requirements"] == []
    assert report["attention_requirements"] == []
    assert report["requirements"]["runtime_operation"]["status"] == "ready"
    assert report["requirements"]["automation_training"]["status"] == "ready"
    assert report["requirements"]["judgment_efficiency_accuracy"]["status"] == "ready"
    assert report["requirements"]["codex_public_opinion"]["status"] == "ready"
    assert report["safety"]["allow_live_order"] is False


def test_operation_readiness_blocks_when_live_trading_enabled(test_db):
    _reset(test_db)
    _seed_ready_state(test_db)
    old_value = settings.enable_live_trading
    settings.enable_live_trading = True
    try:
        report = OperationReadinessService(store=test_db).report(selection_limit=20)
    finally:
        settings.enable_live_trading = old_value

    assert report["status"] == "blocked_live_trading_enabled"
    assert report["requirements"]["runtime_operation"]["status"] == "blocked"
    assert "live_trading_enabled" in report["requirements"]["runtime_operation"]["blockers"]
    assert report["safety"]["allow_live_order"] is False


def test_operation_readiness_accepts_degraded_discovery_when_selection_is_usable(test_db):
    _reset(test_db)
    _seed_ready_state(test_db)
    with test_db.connect() as conn:
        conn.execute(
            """
            UPDATE potential_search_runs
            SET status = 'partial',
                scored_count = 100,
                errors_json = '["discovery_failed: HTTP Error 502: Bad Gateway"]'
            """
        )

    report = OperationReadinessService(store=test_db).report(selection_limit=1)
    judgment = report["requirements"]["judgment_efficiency_accuracy"]

    assert report["status"] == "ready_for_controlled_review_run"
    assert judgment["status"] == "ready"
    assert "v1_stability_external_discovery_errors" not in judgment["warnings"]
    assert "v1_stability_status_partial" not in judgment["warnings"]
    assert judgment["evidence"]["degraded_discovery_accepted_by_selection"] is True
    assert report["safety"]["allow_live_order"] is False


def test_operation_readiness_api_smoke(client, test_db):
    _reset(test_db)
    _seed_ready_state(test_db)

    response = client.get("/api/system/operation-readiness?selection_limit=20")

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "operation_readiness.v1"
    assert payload["status"] == "ready_for_controlled_review_run"
    assert payload["requirements"]["codex_public_opinion"]["status"] == "ready"
    assert payload["safety"]["allow_live_order"] is False
