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
    for idx, close in enumerate([10.0, 10.2, 11.9], start=1):
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

    result = BacktestEngine(config=strategy_config()).run(
        "2020-01-01",
        "2020-01-02",
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
    insert_bar(store, "SH600003", "2020-01-02", 10.1, 10.2, 10.0, 10.1, amount=1000)

    result = BacktestEngine(config=strategy_config()).run(
        "2020-01-01",
        "2020-01-02",
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
