from app.diagnostics.backtest import BacktestRiskDiagnosticsService


def _insert_bar(conn, symbol: str, trade_date: str, close: float) -> None:
    conn.execute(
        """
        INSERT INTO daily_bar_cache(
            symbol, trade_date, open, high, low, close, volume, amount, source, quality_status
        )
        VALUES (?, ?, ?, ?, ?, ?, 10000, 1000000, 'fixture', 'ready')
        """,
        (symbol, trade_date, close, close + 0.2, close - 0.2, close),
    )


def test_backtest_risk_diagnostics_explains_hard_blocked_candidates(test_db):
    with test_db.connect() as conn:
        conn.execute("DELETE FROM daily_bar_cache")
        _insert_bar(conn, "SH600000", "2026-06-21", 10.0)
        _insert_bar(conn, "SH600000", "2026-06-22", 10.1)
        _insert_bar(conn, "SH600000", "2026-06-23", 10.2)

    summary = BacktestRiskDiagnosticsService(store=test_db).diagnose(
        start_date="2026-06-21",
        end_date="2026-06-23",
        symbols=["SH600000"],
        symbol_source="fixture",
    )

    assert summary["review_only"] is True
    assert summary["simulation_only"] is True
    assert summary["status"] == "ready"
    assert summary["evaluated_decision_count"] == 2
    assert summary["blocked_decision_count"] == 2
    assert summary["hard_block_summary"][0]["rule_id"] == "constitution_no_high_position"
    assert summary["hard_block_summary"][0]["count"] == 2
    assert summary["sample_rejections"][0]["failed_hard_blocks"][0]["rule_id"] == "constitution_no_high_position"
    assert summary["next_action"] == "review_hard_block_rule:constitution_no_high_position"
