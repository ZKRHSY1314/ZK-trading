import pytest

from app.backtest.engine import BacktestEngine


@pytest.fixture
def store(test_db):
    with test_db.connect() as conn:
        for table in [
            "daily_bar_cache",
            "historical_backtest_trades",
            "historical_backtest_closed_trades",
            "historical_backtest_daily_equity",
            "historical_backtest_runs",
        ]:
            conn.execute(f"DELETE FROM {table}")
    return test_db


def insert_bar(store, symbol, trade_date, open_, high, low, close, volume=10000, amount=1000000):
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


def seed_benchmark(store):
    for idx, close in enumerate([100, 101, 102, 103, 104, 105, 106], start=1):
        insert_bar(store, "SH000300", f"2020-01-0{idx}", close, close + 1, close - 1, close)


def strategy_config():
    return {
        "candidate_tiers": {"strong_min_score": 20, "watch_min_score": 10},
        "rules": [
            {
                "id": "dengzhan_forced_divergence",
                "name": "volume",
                "group": "strategy",
                "enabled": True,
                "weight": 100,
                "hard_block": False,
                "params": {"min_volume_ratio": 1.0},
            }
        ],
    }


def test_backtest_engine_initialization(store):
    engine = BacktestEngine()
    assert engine.fee_rate > 0


def test_backtest_run_insufficient_data(store):
    result = BacktestEngine().run(
        start_date="2020-01-01",
        end_date="2020-12-31",
        symbols=["FAKE01"],
        initial_cash=100000,
        max_positions=5,
        per_symbol_cap=0.2,
    )
    assert result["run_id"] > 0
    assert result["status"] == "insufficient_data"
    assert result["trades"] == 0
    assert result["metrics"]["trade_count"] == 0


def test_backtest_executes_fixture_trade(store):
    seed_benchmark(store)
    for idx, close in enumerate([10.0, 10.2, 10.5], start=1):
        insert_bar(
            store,
            "SH600000",
            f"2020-01-0{idx}",
            close,
            close + 0.2,
            close - 0.2,
            close,
            volume=2000,
            amount=1000000,
        )

    result = BacktestEngine(config=strategy_config()).run(
        start_date="2020-01-01",
        end_date="2020-01-03",
        symbols=["SH600000"],
        initial_cash=100000,
        max_positions=1,
        per_symbol_cap=0.2,
    )

    assert result["status"] == "completed"
    assert result["metrics"]["trade_count"] >= 1
    assert result["metrics"]["exposure_ratio"] > 0


def test_backtest_closed_trade_metrics_are_realized_pnl_based(store):
    seed_benchmark(store)
    closes = [10.0, 10.1, 10.2, 10.3, 10.4, 12.2, 12.4]
    for idx, close in enumerate(closes, start=1):
        insert_bar(
            store,
            "SH600001",
            f"2020-01-0{idx}",
            close,
            close + 0.5,
            close - 0.2,
            close,
            volume=5000,
            amount=2000000,
        )

    result = BacktestEngine(config=strategy_config()).run(
        start_date="2020-01-01",
        end_date="2020-01-07",
        symbols=["SH600001"],
        initial_cash=100000,
        max_positions=1,
        per_symbol_cap=0.2,
    )

    assert result["metrics"]["closed_trade_count"] >= 1
    assert result["metrics"]["win_rate"] == 1
    assert result["metrics"]["average_win"] > 0
    assert result["metrics"]["expectancy"] > 0


def test_backtest_rejects_one_word_limit_up_buy(store):
    seed_benchmark(store)
    insert_bar(store, "SH600002", "2020-01-01", 10, 10.1, 9.9, 10, amount=1000000)
    insert_bar(store, "SH600002", "2020-01-02", 11, 11, 10.95, 11, amount=1000000)
    insert_bar(store, "SH600002", "2020-01-03", 12.1, 12.1, 12.1, 12.1, amount=1000000)

    result = BacktestEngine(config=strategy_config()).run(
        "2020-01-01",
        "2020-01-03",
        ["SH600002"],
        100000,
        1,
        0.2,
    )

    assert result["metrics"]["rejected_execution_count"] >= 1
    assert any("one_word_limit_up" in item for item in result["execution_warnings"])


def test_backtest_rejects_low_liquidity_order(store):
    seed_benchmark(store)
    insert_bar(store, "SH600003", "2020-01-01", 10, 10.1, 9.9, 10, amount=1000000)
    insert_bar(store, "SH600003", "2020-01-02", 10.1, 10.2, 10.0, 10.1, amount=1000000)
    insert_bar(store, "SH600003", "2020-01-03", 10.1, 10.2, 10.0, 10.1, amount=1000)

    result = BacktestEngine(config=strategy_config()).run(
        "2020-01-01",
        "2020-01-03",
        ["SH600003"],
        100000,
        1,
        0.2,
    )

    assert result["metrics"]["rejected_execution_count"] >= 1
    assert any("liquidity" in item for item in result["execution_warnings"])


def test_backtest_reports_benchmark_warning_when_missing(store):
    insert_bar(store, "SH600004", "2020-01-01", 10, 10.1, 9.9, 10, amount=1000000)
    insert_bar(store, "SH600004", "2020-01-02", 10.1, 10.2, 10.0, 10.1, amount=1000000)

    result = BacktestEngine(config=strategy_config()).run(
        "2020-01-01",
        "2020-01-02",
        ["SH600004"],
        100000,
        1,
        0.2,
        benchmark_symbol="SH000300",
    )

    assert result["benchmark"]["status"] == "insufficient_benchmark_data"
    assert "insufficient_benchmark_data" in result["execution_warnings"]


def test_backtest_tolerates_null_liquidity_fields_from_daily_cache(store):
    seed_benchmark(store)
    insert_bar(store, "SH600005", "2020-01-01", 10, 10.1, 9.9, 10, volume=1000, amount=1000000)
    insert_bar(store, "SH600005", "2020-01-02", 10.1, 10.4, 10.0, 10.3, volume=None, amount=None)
    insert_bar(store, "SH600005", "2020-01-03", 10.3, 10.6, 10.2, 10.5, volume=2000, amount=1000000)

    result = BacktestEngine(config=strategy_config()).run(
        "2020-01-01",
        "2020-01-03",
        ["SH600005"],
        100000,
        1,
        0.2,
    )

    assert result["status"] == "completed"
    assert result["simulation_only"] is True


def test_backtest_filters_null_price_rows_and_benchmark_closes(store):
    insert_bar(store, "SH000300", "2020-01-01", 100, 101, 99, 100)
    insert_bar(store, "SH000300", "2020-01-02", 100, 101, 99, None)
    insert_bar(store, "SH000300", "2020-01-03", 101, 102, 100, 101)
    insert_bar(store, "SH600006", "2020-01-01", 10, 10.1, 9.9, 10, amount=1000000)
    insert_bar(store, "SH600006", "2020-01-02", 10.1, None, 10.0, 10.1, amount=1000000)
    insert_bar(store, "SH600006", "2020-01-03", 10.2, 10.5, 10.1, 10.4, amount=1000000)

    result = BacktestEngine(config=strategy_config()).run(
        "2020-01-01",
        "2020-01-03",
        ["SH600006"],
        100000,
        1,
        0.2,
    )

    assert result["status"] == "completed"
    assert result["benchmark"]["status"] == "ready"


def test_backtest_executes_close_signal_on_next_trading_day_open(store):
    seed_benchmark(store)
    insert_bar(store, "SH600007", "2020-01-01", 10.0, 10.1, 9.9, 10.0, amount=1000000)
    insert_bar(store, "SH600007", "2020-01-02", 10.0, 10.2, 9.9, 10.1, amount=1000000)
    insert_bar(store, "SH600007", "2020-01-03", 10.4, 10.6, 10.3, 10.5, amount=1000000)

    result = BacktestEngine(config=strategy_config()).run(
        "2020-01-01",
        "2020-01-03",
        ["SH600007"],
        100000,
        1,
        0.2,
    )
    buy = store.fetch_one(
        """
        SELECT trade_date, price, reason
        FROM historical_backtest_trades
        WHERE run_id = ? AND symbol = 'SH600007' AND side = 'buy'
        ORDER BY id LIMIT 1
        """,
        (result["run_id"],),
    )

    assert buy is not None
    assert buy["trade_date"] == "2020-01-03"
    assert buy["reason"] == "prior_close_strong_signal"
    assert buy["price"] > 10.4


def test_backtest_entry_does_not_use_entry_day_close_regime(monkeypatch, store):
    seed_benchmark(store)
    for trade_date, close in (("2020-01-01", 10.0), ("2020-01-02", 10.1), ("2020-01-03", 10.5)):
        insert_bar(store, "SH600008", trade_date, close, close + 0.2, close - 0.2, close)

    class RegimeByDate:
        def get_latest_regime(self, trade_date):
            return {"regime": "extreme_risk" if trade_date == "2020-01-03" else "weak"}

    monkeypatch.setattr("app.backtest.engine.MarketRegimeService", RegimeByDate)
    result = BacktestEngine(config=strategy_config()).run(
        "2020-01-01", "2020-01-03", ["SH600008"], 100000, 1, 0.2
    )

    buy = store.fetch_one(
        """
        SELECT trade_date FROM historical_backtest_trades
        WHERE run_id = ? AND symbol = 'SH600008' AND side = 'buy'
        """,
        (result["run_id"],),
    )
    assert buy is not None
    assert buy["trade_date"] == "2020-01-03"


def test_backtest_defers_signal_until_symbol_next_available_bar(store):
    seed_benchmark(store)
    insert_bar(store, "SH600009", "2020-01-01", 10.0, 10.2, 9.8, 10.0)
    insert_bar(store, "SH600009", "2020-01-02", 10.0, 10.3, 9.9, 10.1)
    insert_bar(store, "SH600009", "2020-01-04", 10.4, 10.7, 10.3, 10.5)
    for day in range(1, 5):
        insert_bar(store, "SZ000009", f"2020-01-0{day}", 8.0, 8.1, 7.9, 8.0)

    result = BacktestEngine(config=strategy_config()).run(
        "2020-01-01",
        "2020-01-04",
        ["SH600009", "SZ000009"],
        100000,
        2,
        0.2,
    )
    buy = store.fetch_one(
        """
        SELECT trade_date FROM historical_backtest_trades
        WHERE run_id = ? AND symbol = 'SH600009' AND side = 'buy'
        ORDER BY id LIMIT 1
        """,
        (result["run_id"],),
    )

    assert buy is not None
    assert buy["trade_date"] == "2020-01-04"
