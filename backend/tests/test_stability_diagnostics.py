from datetime import date, timedelta
import json

from app.config import settings
from app.diagnostics.stability import V1StabilityDiagnosticsService
from app.sim_cockpit.service import SimCockpitService


def recent_date(days_ago: int = 1) -> str:
    return (date.today() - timedelta(days=days_ago)).isoformat()


def test_v1_stability_diagnostics_reports_review_only_safety(client, test_db):
    start_date = recent_date(2)
    end_date = recent_date(1)
    with test_db.connect() as conn:
        for table in [
            "daily_bar_cache",
            "potential_search_runs",
            "historical_backtest_runs",
            "offhour_research_runs",
            "sim_cockpit_window_verifications",
            "sim_cockpit_actions",
            "sim_cockpit_readbacks",
            "simulation_fills",
            "simulation_positions",
        ]:
            conn.execute(f"DELETE FROM {table}")
        conn.executemany(
            """
            INSERT INTO daily_bar_cache(
                symbol, trade_date, open, high, low, close, volume, amount, source, quality_status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'fixture', 'ready')
            """,
            [
                ("SH000300", end_date, 100, 101, 99, 100, 1000, 100000),
                ("SH000001", end_date, 100, 101, 99, 100, 1000, 100000),
                ("SH600000", end_date, 10, 11, 9, 10, 1000, 100000),
            ],
        )
        conn.execute(
            """
            INSERT INTO potential_search_runs(
                status, source, total_scanned, stored_count, scored_count, errors_json, summary_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "partial",
                "akshare.stock_zh_a_spot_em",
                0,
                0,
                2,
                json.dumps(["Remote end closed connection without response"]),
                "{}",
            ),
        )
        conn.execute(
            """
            INSERT INTO historical_backtest_runs(
                config_json, data_source, start_date, end_date, status, benchmark_symbol,
                initial_cash, final_cash, metrics_json, benchmark_json, execution_warnings_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "{}",
                "daily_bar_cache",
                start_date,
                end_date,
                "completed",
                "SH000300",
                100000,
                100000,
                json.dumps({"trade_count": 0, "rejected_by_risk_count": 3}),
                json.dumps({"status": "insufficient_benchmark_data"}),
                json.dumps(["insufficient_benchmark_data"]),
            ),
        )
        conn.execute(
            """
            INSERT INTO offhour_research_runs(
                mode, status, summary_json, next_action, review_only, simulation_only,
                live_trading_enabled
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "balanced_search_replay",
                "completed",
                json.dumps({"signal_count": 2, "signal_backtest_trade_count": 0}),
                "review data",
                1,
                1,
                0,
            ),
        )
        conn.execute(
            """
            INSERT INTO sim_cockpit_window_verifications(
                status, blocked_reasons_json, verified_by, confidence,
                simulation_mode_detected, real_trading_blocked, live_trading_enabled
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "blocked",
                json.dumps(["missing_window_or_page_text"]),
                "desktop_adapter",
                0.0,
                1,
                1,
                0,
            ),
        )

    data = client.get("/api/system/v1-stability").json()

    assert data["review_only"] is True
    assert data["simulation_only"] is True
    assert data["live_trading_enabled"] is False
    assert data["safety"]["real_order_execution_enabled"] is False
    assert data["latest_potential_search"]["degraded"] is True
    assert "external_discovery_errors" in data["latest_potential_search"]["diagnostic_reasons"]
    assert data["data_freshness"]["review_only"] is True
    assert data["data_freshness"]["daily_bar_refresh_preflight"]["preflight_writes_database"] is False
    assert data["data_freshness"]["discovery_recovery"]["preflight_writes_database"] is False
    assert "zero_completed_trades" in data["latest_backtest"]["diagnostic_reasons"]
    assert "insufficient_benchmark_data" in data["latest_backtest"]["diagnostic_reasons"]
    assert data["sim_cockpit"]["simulation_actions_allowed"] is False
    assert "sim_cockpit_not_verified" in data["attention_items"]


def test_v1_stability_flags_backtest_rerun_when_current_benchmark_cache_is_ready(client, test_db):
    start_date = recent_date(2)
    end_date = recent_date(1)
    with test_db.connect() as conn:
        for table in [
            "daily_bar_cache",
            "potential_search_runs",
            "historical_backtest_runs",
            "offhour_research_runs",
            "sim_cockpit_window_verifications",
            "sim_cockpit_actions",
            "sim_cockpit_readbacks",
            "simulation_fills",
            "simulation_positions",
        ]:
            conn.execute(f"DELETE FROM {table}")
        conn.executemany(
            """
            INSERT INTO daily_bar_cache(
                symbol, trade_date, open, high, low, close, volume, amount, source, quality_status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'fixture', 'ready')
            """,
            [
                ("SH000300", start_date, 100, 101, 99, 100, 1000, 100000),
                ("SH000300", end_date, 101, 102, 100, 101, 1000, 100000),
                ("SH600000", start_date, 10, 11, 9, 10, 1000, 100000),
                ("SH600000", end_date, 10.1, 11.1, 9.1, 10.1, 1000, 100000),
            ],
        )
        conn.execute(
            """
            INSERT INTO potential_search_runs(
                status, source, total_scanned, stored_count, scored_count, errors_json, summary_json
            )
            VALUES ('completed', 'fixture', 2, 2, 2, '[]', '{}')
            """
        )
        conn.execute(
            """
            INSERT INTO historical_backtest_runs(
                config_json, data_source, start_date, end_date, status, benchmark_symbol,
                initial_cash, final_cash, metrics_json, benchmark_json, execution_warnings_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "{}",
                "daily_bar_cache",
                start_date,
                end_date,
                "completed",
                "SH000300",
                100000,
                100000,
                json.dumps({"trade_count": 1, "rejected_by_risk_count": 0}),
                json.dumps({"status": "insufficient_benchmark_data"}),
                json.dumps(["insufficient_benchmark_data"]),
            ),
        )
        conn.execute(
            """
            INSERT INTO sim_cockpit_window_verifications(
                status, blocked_reasons_json, verified_by, confidence,
                simulation_mode_detected, real_trading_blocked, live_trading_enabled,
                raw_payload_json
            )
            VALUES (
                'verified', '[]', 'desktop_adapter', 1.0, 1, 1, 0,
                '{"source":"desktop_adapter","detection_status":"verified",' ||
                '"window":{"hwnd":1,"pid":101,"rect":{"left":0,"top":0,"width":800,"height":600}}}'
            )
            """
        )

    data = client.get("/api/system/v1-stability").json()

    assert data["latest_backtest"]["current_benchmark_coverage"]["status"] == "ready"
    assert "backtest_benchmark_rerun_required" in data["latest_backtest"]["diagnostic_reasons"]
    assert "insufficient_benchmark_data" not in data["latest_backtest"]["diagnostic_reasons"]


def test_v1_stability_includes_rule_level_risk_rejection_diagnostics(client, test_db):
    start_date = recent_date(2)
    end_date = recent_date(1)
    with test_db.connect() as conn:
        for table in [
            "daily_bar_cache",
            "potential_search_runs",
            "historical_backtest_runs",
            "offhour_research_runs",
            "sim_cockpit_window_verifications",
            "sim_cockpit_actions",
            "sim_cockpit_readbacks",
            "simulation_fills",
            "simulation_positions",
        ]:
            conn.execute(f"DELETE FROM {table}")
        conn.executemany(
            """
            INSERT INTO daily_bar_cache(
                symbol, trade_date, open, high, low, close, volume, amount, source, quality_status
            )
            VALUES (?, ?, ?, ?, ?, ?, 10000, 1000000, 'fixture', 'ready')
            """,
            [
                ("SH000300", start_date, 100, 101, 99, 100),
                ("SH000300", end_date, 101, 102, 100, 101),
                ("SH600000", start_date, 10, 10.2, 9.8, 10),
                ("SH600000", end_date, 10.1, 10.3, 9.9, 10.1),
            ],
        )
        conn.execute(
            """
            INSERT INTO potential_search_runs(
                status, source, total_scanned, stored_count, scored_count, errors_json, summary_json
            )
            VALUES ('completed', 'fixture', 1, 1, 1, '[]', '{}')
            """
        )
        conn.execute(
            """
            INSERT INTO historical_backtest_runs(
                config_json, data_source, start_date, end_date, status, benchmark_symbol,
                initial_cash, final_cash, metrics_json, benchmark_json, execution_warnings_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "{}",
                "daily_bar_cache",
                start_date,
                end_date,
                "completed",
                "SH000300",
                100000,
                100000,
                json.dumps({"trade_count": 0, "rejected_by_risk_count": 1}),
                json.dumps({"status": "ready"}),
                "[]",
            ),
        )
        conn.execute(
            """
            INSERT INTO offhour_research_runs(
                mode, status, backtest_json, summary_json, review_only, simulation_only,
                live_trading_enabled
            )
            VALUES (?, ?, ?, ?, 1, 1, 0)
            """,
            (
                "balanced_search_replay",
                "completed",
                json.dumps(
                    {
                        "symbols": ["SH600000"],
                        "start_date": start_date,
                        "end_date": end_date,
                    }
                ),
                "{}",
            ),
        )

    data = client.get("/api/system/v1-stability").json()
    risk = data["latest_backtest"]["risk_rejection_diagnostics"]

    assert risk["status"] == "ready"
    assert risk["symbol_source"].startswith("offhour_research_runs:")
    assert risk["blocked_decision_count"] == 1
    assert risk["hard_block_summary"][0]["rule_id"] == "constitution_no_high_position"
    assert risk["next_action"] == "review_hard_block_rule:constitution_no_high_position"
    assert data["strategy_safety_review"]["status"] == "accepted_conservative_no_trade_gate"
    assert data["strategy_safety_review"]["policy"]["rules_yaml_mutation_required"] is False
    assert data["accepted_attention_items"] == ["candidates_rejected_by_risk", "zero_completed_trades"]
    assert data["blocking_attention_items"] == ["sim_cockpit_not_verified"]
    assert data["release_gate"]["status"] == "externally_blocked_simulation_window"
    assert data["release_gate"]["code_data_strategy_stable"] is True
    assert data["release_gate"]["external_blockers"] == ["tonghuashun_mncg_simulation_window_not_verified"]


def test_v1_stability_accepts_conservative_no_trade_gate_when_only_strategy_attention_remains(client, test_db):
    start_date = recent_date(2)
    end_date = recent_date(1)
    with test_db.connect() as conn:
        for table in [
            "daily_bar_cache",
            "potential_search_runs",
            "historical_backtest_runs",
            "offhour_research_runs",
            "sim_cockpit_window_verifications",
            "sim_cockpit_actions",
            "sim_cockpit_readbacks",
            "simulation_fills",
            "simulation_positions",
        ]:
            conn.execute(f"DELETE FROM {table}")
        conn.executemany(
            """
            INSERT INTO daily_bar_cache(
                symbol, trade_date, open, high, low, close, volume, amount, source, quality_status
            )
            VALUES (?, ?, ?, ?, ?, ?, 10000, 1000000, 'fixture', 'ready')
            """,
            [
                ("SH000300", start_date, 100, 101, 99, 100),
                ("SH000300", end_date, 101, 102, 100, 101),
                ("SH600000", start_date, 10, 10.2, 9.8, 10),
                ("SH600000", end_date, 10.1, 10.3, 9.9, 10.1),
            ],
        )
        conn.execute(
            """
            INSERT INTO potential_search_runs(
                status, source, total_scanned, stored_count, scored_count, errors_json, summary_json
            )
            VALUES ('completed', 'fixture', 1, 1, 1, '[]', '{}')
            """
        )
        conn.execute(
            """
            INSERT INTO historical_backtest_runs(
                config_json, data_source, start_date, end_date, status, benchmark_symbol,
                initial_cash, final_cash, metrics_json, benchmark_json, execution_warnings_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "{}",
                "daily_bar_cache",
                start_date,
                end_date,
                "completed",
                "SH000300",
                100000,
                100000,
                json.dumps({"trade_count": 0, "rejected_by_risk_count": 1}),
                json.dumps({"status": "ready"}),
                "[]",
            ),
        )
        conn.execute(
            """
            INSERT INTO offhour_research_runs(
                mode, status, backtest_json, summary_json, review_only, simulation_only,
                live_trading_enabled
            )
            VALUES (?, ?, ?, ?, 1, 1, 0)
            """,
            (
                "balanced_search_replay",
                "completed",
                json.dumps(
                    {
                        "symbols": ["SH600000"],
                        "start_date": start_date,
                        "end_date": end_date,
                    }
                ),
                "{}",
            ),
        )
        conn.execute(
            """
            INSERT INTO sim_cockpit_window_verifications(
                status, blocked_reasons_json, verified_by, confidence,
                simulation_mode_detected, real_trading_blocked, live_trading_enabled,
                raw_payload_json
            )
            VALUES (
                'verified', '[]', 'desktop_adapter', 1.0, 1, 1, 0,
                '{"source":"desktop_adapter","detection_status":"verified",' ||
                '"window":{"hwnd":1,"pid":101,"rect":{"left":0,"top":0,"width":800,"height":600}}}'
            )
            """
        )

    data = client.get("/api/system/v1-stability").json()

    assert data["status"] == "ready_for_v1_review"
    assert data["attention_items"] == ["candidates_rejected_by_risk", "zero_completed_trades"]
    assert data["accepted_attention_items"] == ["candidates_rejected_by_risk", "zero_completed_trades"]
    assert data["blocking_attention_items"] == []
    assert data["strategy_safety_review"]["status"] == "accepted_conservative_no_trade_gate"
    assert data["strategy_safety_review"]["checks"]["all_blocks_explained_by_single_known_rule"] is True
    assert data["release_gate"]["status"] == "ready_for_v1_review"
    assert data["release_gate"]["ready_for_v1_review"] is True
    assert data["release_gate"]["sim_cockpit_verified"] is True
    assert data["safety"]["real_order_execution_enabled"] is False


def test_v1_stability_does_not_treat_expired_window_verification_as_ready(test_db):
    with test_db.connect() as conn:
        conn.execute("DELETE FROM sim_cockpit_window_verifications")
        conn.execute(
            """
            INSERT INTO sim_cockpit_window_verifications(
                status, blocked_reasons_json, verified_by, confidence,
                simulation_mode_detected, real_trading_blocked, live_trading_enabled,
                raw_payload_json, created_at
            )
            VALUES (
                'verified', '[]', 'desktop_adapter', 1.0, 1, 1, 0,
                '{"source":"desktop_adapter","detection_status":"verified",' ||
                '"window":{"hwnd":1,"pid":101,"rect":{"left":0,"top":0,"width":800,"height":600}}}',
                datetime('now', '-16 minutes')
            )
            """
        )

    status = V1StabilityDiagnosticsService(store=test_db)._sim_cockpit()

    assert status["status"] == "needs_verification"
    assert status["simulation_actions_allowed"] is False
    assert status["verification_freshness"]["fresh"] is False
    assert "window_verification_expired" in status["blocked_reasons"]


def test_v1_stability_matches_gateway_when_live_enabled_without_verification(test_db, monkeypatch):
    with test_db.connect() as conn:
        conn.execute("DELETE FROM sim_cockpit_window_verifications")
    monkeypatch.setattr(settings, "enable_live_trading", True)

    gateway = SimCockpitService().status()
    diagnostics = V1StabilityDiagnosticsService(store=test_db)._sim_cockpit()

    assert gateway["status"] == "blocked"
    assert gateway["simulation_actions_allowed"] is False
    assert "no_window_verification" in gateway["blocked_reasons"]
    assert "live_trading_enabled" in gateway["blocked_reasons"]
    for field in (
        "status",
        "simulation_actions_allowed",
        "blocked_reasons",
        "verification_freshness",
        "live_trading_enabled",
    ):
        assert diagnostics[field] == gateway[field]
