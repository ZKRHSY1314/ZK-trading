import pytest
from app.backtest.engine import BacktestEngine
from app.storage.sqlite_store import SQLiteStore
from app.config import settings

@pytest.fixture
def store():
    # Setup test DB or use a memory one if supported, here we just use the default test DB behavior
    s = SQLiteStore(settings.database_path)
    s.init()
    yield s

def test_backtest_engine_initialization():
    engine = BacktestEngine()
    assert engine.fee_rate > 0

def test_backtest_run_insufficient_data(store):
    engine = BacktestEngine()
    # Assuming "FAKE01" doesn't have data
    result = engine.run(
        start_date="2020-01-01",
        end_date="2020-12-31",
        symbols=["FAKE01"],
        initial_cash=100000,
        max_positions=5,
        per_symbol_cap=0.2
    )
    assert result["run_id"] > 0
    assert result["status"] == "insufficient_data"
    assert result["trades"] == 0
    assert result["metrics"]["trade_count"] == 0


def test_backtest_executes_fixture_trade(store):
    with store.connect() as conn:
        conn.execute("DELETE FROM daily_bar_cache")
        for idx, close in enumerate([100, 101, 102, 103, 104], start=1):
            conn.execute(
                """
                INSERT INTO daily_bar_cache(
                    symbol, trade_date, open, high, low, close, volume, amount, source, quality_status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "sh000001",
                    f"2020-01-0{idx}",
                    close,
                    close + 1,
                    close - 1,
                    close,
                    10000,
                    1000000,
                    "fixture",
                    "ready",
                ),
            )
        bars = [
            ("2020-01-01", 10.0, 10.2, 9.8, 10.0, 1000),
            ("2020-01-02", 10.1, 10.4, 10.0, 10.2, 2000),
            ("2020-01-03", 11.8, 12.0, 11.6, 11.9, 2200),
        ]
        for trade_date, open_, high, low, close, volume in bars:
            conn.execute(
                """
                INSERT INTO daily_bar_cache(
                    symbol, trade_date, open, high, low, close, volume, amount, source, quality_status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("SH600000", trade_date, open_, high, low, close, volume, close * volume, "fixture", "ready"),
            )

    config = {
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
    result = BacktestEngine(config=config).run(
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
