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
            "symbol_fundamental_snapshot",
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


def strategy_config(min_volume_ratio=1.0):
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
                "params": {"min_volume_ratio": min_volume_ratio},
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
    assert result["metrics"]["entry_fill_count"] >= 1
    assert result["metrics"]["exposure_ratio"] > 0
    assert isinstance(result["metrics"]["excess_return"], float)


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
    assert result["status"] == "no_fill"
    assert result["metrics"]["entry_signal_count"] >= 1
    assert result["metrics"]["entry_fill_count"] == 0
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
    assert result["status"] == "no_fill"
    assert result["metrics"]["entry_signal_count"] >= 1
    assert result["metrics"]["entry_fill_count"] == 0
    assert any("liquidity" in item for item in result["execution_warnings"])


def test_backtest_reports_no_signal_only_when_no_strong_signal_exists(store):
    seed_benchmark(store)
    for idx, close in enumerate([10.0, 10.1, 10.2], start=1):
        insert_bar(
            store,
            "SH600099",
            f"2020-01-0{idx}",
            close,
            close + 0.2,
            close - 0.2,
            close,
            volume=1000,
            amount=1000000,
        )

    result = BacktestEngine(config=strategy_config(min_volume_ratio=2.0)).run(
        "2020-01-01", "2020-01-03", ["SH600099"], 100000, 1, 0.2, persist=False
    )

    assert result["status"] == "no_signal"
    assert result["metrics"]["entry_signal_count"] == 0
    assert result["metrics"]["entry_attempt_count"] == 0
    assert result["metrics"]["entry_fill_count"] == 0


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

    # The final valid bar creates a strong signal, but the range ends before a
    # next-session fill. That is an unfilled signal, not an absent signal.
    assert result["status"] == "no_fill"
    assert result["metrics"]["trade_count"] == 0
    assert result["metrics"]["entry_signal_count"] == 1
    assert result["metrics"]["entry_attempt_count"] == 0
    assert result["metrics"]["pending_entry_count"] == 1
    assert result["metrics"]["total_return"] is None
    assert result["metrics"]["excess_return"] is None
    assert result["benchmark"]["status"] == "ready"
    assert result["benchmark"]["excess_return"] is None


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


def dengzhan_config():
    """The shipped rule shape: the market-cap band is what went dark."""
    return {
        "candidate_tiers": {"strong_min_score": 80, "watch_min_score": 60},
        "rules": [
            {
                "id": "dengzhan_low_position_limit_up",
                "name": "低位涨停",
                "group": "strategy",
                "enabled": True,
                "weight": 100,
                "hard_block": False,
                "params": {
                    "max_price_to_high_ratio": 0.5,
                    "min_limit_up_pct": 9.9,
                    "max_pb": 6.0,
                    "min_market_cap_billion": 50,
                    "max_market_cap_billion": 200,
                },
            }
        ],
    }


def seed_low_position_limit_up(store, symbol="SH600100"):
    # A 250-day high of 100, a crash, then a +10% limit up at 44 -> ratio 0.44.
    insert_bar(store, symbol, "2020-01-01", 100, 100, 99, 100)
    insert_bar(store, symbol, "2020-01-02", 45, 45, 40, 40)
    insert_bar(store, symbol, "2020-01-03", 41, 44, 41, 44)
    insert_bar(store, symbol, "2020-01-06", 44, 45, 43, 44.5)


def test_missing_fundamentals_reports_unknown_instead_of_a_silent_rejection(store):
    seed_benchmark(store)
    seed_low_position_limit_up(store)

    result = BacktestEngine(config=dengzhan_config()).run(
        "2020-01-01", "2020-01-06", ["SH600100"], 100000, 1, 0.2, persist=False
    )

    outcomes = result["metrics"]["signal_rule_outcomes"]["dengzhan_low_position_limit_up"]
    assert outcomes.get("unknown", 0) >= 1
    assert result["metrics"]["signal_missing_inputs"]["pb"] >= 1
    assert result["metrics"]["signal_missing_inputs"]["market_cap_billion"] >= 1
    assert result["metrics"]["signal_input_coverage"] < 1.0
    assert any("fundamental_snapshots_empty" in item for item in result["execution_warnings"])
    # No fill, so return metrics are absent rather than a misleading 0.0.
    assert result["status"] == "degraded"
    assert result["metrics"]["total_return"] is None


def test_fundamental_snapshot_activates_the_market_cap_gate(store):
    from app.data.fundamentals import FundamentalsStore, FundamentalSnapshot

    seed_benchmark(store)
    seed_low_position_limit_up(store)
    FundamentalsStore(store).upsert(
        [
            FundamentalSnapshot(
                symbol="600100",
                name="fixture",
                as_of="2020-01-01",
                price=44.0,
                market_cap_billion=440.0,
                float_cap_billion=440.0,
                pb=2.0,
                total_share_billion=10.0,  # 10亿股 x 44元 = 440亿, above the band
                book_value_per_share=22.0,
                available_at="2020-01-01T06:00:00+00:00",
            )
        ]
    )

    result = BacktestEngine(config=dengzhan_config()).run(
        "2020-01-01", "2020-01-06", ["SH600100"], 100000, 1, 0.2, persist=False
    )

    outcomes = result["metrics"]["signal_rule_outcomes"]["dengzhan_low_position_limit_up"]
    # The gate now evaluates instead of failing for want of an input.
    assert outcomes.get("unknown", 0) == 0
    assert "market_cap_billion" not in result["metrics"]["signal_missing_inputs"]
    assert result["metrics"]["signal_input_coverage"] == 1.0
    reasons = result["metrics"]["signal_top_rejections"]["dengzhan_low_position_limit_up"]
    assert any("高于上限" in reason for reason in reasons)


def test_backtest_excludes_fundamental_snapshot_ingested_after_the_window(store):
    from app.data.fundamentals import FundamentalsStore, FundamentalSnapshot

    seed_benchmark(store)
    seed_low_position_limit_up(store)
    FundamentalsStore(store).upsert(
        [
            FundamentalSnapshot(
                symbol="600100",
                name="backfilled-later",
                as_of="2020-01-01",
                price=44.0,
                market_cap_billion=100.0,
                float_cap_billion=100.0,
                pb=2.0,
                total_share_billion=100.0 / 44.0,
                book_value_per_share=22.0,
                available_at="2026-09-01T00:00:00+00:00",
            )
        ]
    )

    result = BacktestEngine(config=dengzhan_config()).run(
        "2020-01-01", "2020-01-06", ["SH600100"], 100000, 1, 0.2, persist=False
    )

    outcomes = result["metrics"]["signal_rule_outcomes"]["dengzhan_low_position_limit_up"]
    assert outcomes.get("unknown", 0) >= 1
    assert result["status"] == "degraded"
    assert any(
        "fundamental_snapshots_unavailable_at_backtest_cutoff" in warning
        for warning in result["execution_warnings"]
    )


def test_projected_fundamentals_is_an_explicit_opt_in(store):
    from app.data.fundamentals import FundamentalsStore, FundamentalSnapshot

    seed_benchmark(store)
    seed_low_position_limit_up(store)
    # The only snapshot we ever have is a *current* one, dated after the window.
    FundamentalsStore(store).upsert(
        [
            FundamentalSnapshot(
                symbol="600100",
                name="fixture",
                as_of="2026-09-01",
                price=44.0,
                market_cap_billion=440.0,
                float_cap_billion=440.0,
                pb=2.0,
                total_share_billion=10.0,
                book_value_per_share=22.0,
                available_at="2026-09-01T06:00:00+00:00",
            )
        ]
    )

    strict = BacktestEngine(config=dengzhan_config()).run(
        "2020-01-01", "2020-01-06", ["SH600100"], 100000, 1, 0.2, persist=False
    )
    # Point-in-time by default: a future snapshot must not reach 2020 bars.
    assert strict["metrics"]["fundamental_point_in_time"] is True
    assert strict["metrics"]["signal_rule_outcomes"]["dengzhan_low_position_limit_up"].get("unknown", 0) >= 1
    assert any("unavailable_at_backtest_cutoff" in item for item in strict["execution_warnings"])

    projected = BacktestEngine(config=dengzhan_config()).run(
        "2020-01-01",
        "2020-01-06",
        ["SH600100"],
        100000,
        1,
        0.2,
        persist=False,
        allow_projected_fundamentals=True,
    )
    # Opted in: the gate evaluates, and the run is stamped as an approximation.
    assert projected["metrics"]["fundamental_point_in_time"] is False
    assert projected["metrics"]["signal_rule_outcomes"]["dengzhan_low_position_limit_up"].get("unknown", 0) == 0
    assert any("fundamental_projection_enabled" in item for item in projected["execution_warnings"])
    reasons = projected["metrics"]["signal_top_rejections"]["dengzhan_low_position_limit_up"]
    assert any("高于上限" in reason for reason in reasons)


def test_missing_amount_falls_back_to_a_labeled_volume_price_proxy(store):
    seed_benchmark(store)
    # Signal bar, then the fill bar carries volume but no 成交额 (the tencent
    # fqkline shape that covers 97.6% of the cache).
    insert_bar(store, "SH600200", "2020-01-01", 10, 10.1, 9.9, 10, volume=50000, amount=None)
    insert_bar(store, "SH600200", "2020-01-02", 10.1, 10.4, 10.0, 10.3, volume=80000, amount=None)
    insert_bar(store, "SH600200", "2020-01-03", 10.3, 10.6, 10.2, 10.5, volume=90000, amount=None)

    result = BacktestEngine(config=strategy_config()).run(
        "2020-01-01", "2020-01-03", ["SH600200"], 100000, 1, 0.2, persist=False
    )

    assert result["metrics"]["entry_fill_count"] >= 1
    assert result["metrics"]["liquidity_basis_counts"].get("volume_price_proxy", 0) >= 1
    assert "reported_amount" not in result["metrics"]["liquidity_basis_counts"]


def test_missing_amount_and_volume_is_still_rejected(store):
    seed_benchmark(store)
    insert_bar(store, "SH600201", "2020-01-01", 10, 10.1, 9.9, 10, volume=50000, amount=None)
    insert_bar(store, "SH600201", "2020-01-02", 10.1, 10.4, 10.0, 10.3, volume=None, amount=None)
    insert_bar(store, "SH600201", "2020-01-03", 10.3, 10.6, 10.2, 10.5, volume=None, amount=None)

    result = BacktestEngine(config=strategy_config()).run(
        "2020-01-01", "2020-01-03", ["SH600201"], 100000, 1, 0.2, persist=False
    )

    assert result["metrics"]["entry_fill_count"] == 0
    assert any("missing_liquidity_amount" in item for item in result["execution_warnings"])


def _exit_config(**overrides):
    config = strategy_config()
    exit_rules = {
        "stop_loss_pct": 6.0,
        "partial_take_profit_pct": 15.0,
        "partial_take_profit_ratio": 0.5,
        "break_ma_window": 5,
        "require_below_limit_up_avg": False,
        "max_holding_days": None,
    }
    exit_rules.update(overrides)
    config["exit_rules"] = exit_rules
    return config


def test_exit_rules_come_from_config_not_a_hardcoded_five_day_close(store):
    """A flat drift past day 5 must not be liquidated by a holding-period cap.

    The engine used to force-close at 5 days, which measured the horizon rather
    than the strategy. With max_holding_days null the position survives, and
    setting it back to 5 restores the old behaviour - so the cap is now a
    configured choice rather than something baked into the engine.
    """

    seed_benchmark(store)
    # Flat-ish drift: never 6% down, never 15% up, never below the 5-day MA.
    for idx, close in enumerate([10.0, 10.1, 10.2, 10.3, 10.4, 10.5, 10.6], start=1):
        insert_bar(
            store,
            "SH600002",
            f"2020-01-0{idx}",
            close,
            close + 0.05,
            close - 0.02,
            close,
            volume=5000,
            amount=2000000,
        )

    def run(config):
        return BacktestEngine(config=config).run(
            start_date="2020-01-01",
            end_date="2020-01-07",
            symbols=["SH600002"],
            initial_cash=100000,
            max_positions=1,
            per_symbol_cap=0.2,
        )

    held = run(_exit_config())
    assert held["metrics"]["exit_reason_counts"] == {}
    assert held["metrics"]["open_position_count"] == 1

    # The window only holds a position for a day, so assert the cap at a
    # reachable value rather than restating the old literal 5. The signal keeps
    # firing, so the position can re-enter and be capped again - what matters
    # is that the cap fires at all here and never fires above.
    capped = run(_exit_config(max_holding_days=1))
    assert capped["metrics"]["exit_reason_counts"].get("max_holding_days", 0) >= 1


def test_partial_take_profit_sells_half_and_fires_once(store):
    seed_benchmark(store)
    # Enter low, then gap far enough above cost to trip the 15% level and stay
    # there, so a repeating full take-profit would show up as several exits.
    closes = [10.0, 10.1, 10.2, 10.3, 10.4, 13.0, 13.4]
    for idx, close in enumerate(closes, start=1):
        insert_bar(
            store,
            "SH600003",
            f"2020-01-0{idx}",
            close,
            close + 0.5,
            close - 0.1,
            close,
            volume=5000,
            amount=2000000,
        )

    result = BacktestEngine(config=_exit_config()).run(
        start_date="2020-01-01",
        end_date="2020-01-07",
        symbols=["SH600003"],
        initial_cash=100000,
        max_positions=1,
        per_symbol_cap=0.2,
    )

    counts = result["metrics"]["exit_reason_counts"]
    assert counts.get("partial_take_profit") == 1
    assert "take_profit" not in counts


def test_ma_break_exit_is_labeled_when_the_limit_up_average_is_unknown(store):
    """An unconfirmed break must be distinguishable from a confirmed one.

    The spec requires close < MA *and* close < the limit-up day's average
    price. When the second input is unavailable the exit still fires, but under
    a different reason, so an approximation is never silently reported as the
    real rule.
    """

    seed_benchmark(store)
    closes = [10.0, 10.1, 10.2, 10.3, 10.4, 10.5, 9.0]
    for idx, close in enumerate(closes, start=1):
        # amount omitted -> no reported turnover -> limit-up average unavailable
        insert_bar(
            store,
            "SH600004",
            f"2020-01-0{idx}",
            close,
            close + 0.1,
            close - 0.05,
            close,
            volume=5000,
            amount=None,
        )

    result = BacktestEngine(config=_exit_config(require_below_limit_up_avg=True)).run(
        start_date="2020-01-01",
        end_date="2020-01-08",
        symbols=["SH600004"],
        initial_cash=100000,
        max_positions=1,
        per_symbol_cap=0.2,
    )

    counts = result["metrics"]["exit_reason_counts"]
    assert "take_profit" not in counts
    assert set(counts) <= {
        "stop_loss",
        "ma_break",
        "ma_break_limit_up_avg_unknown",
        "partial_take_profit",
    }


def _armed_engine_config(window):
    """The shipped two-rule shape, where S0 alone cannot reach ``strong``.

    With a single 100-weight rule an S0 scores 100 and enters at once, and the
    candidate loop then skips the symbol because it holds a position - so the
    window would never be observed. Mirroring rules.yaml (25 + 20 normalized to
    100, strong at 80) keeps S0 in ``watch`` until a divergence confirms it,
    which is the situation the ARMED window exists for.
    """

    config = dengzhan_config()
    config["candidate_tiers"] = {"strong_min_score": 80, "watch_min_score": 50}
    config["rules"][0]["weight"] = 25
    config["rules"][0]["params"]["armed_window_days"] = window
    config["rules"].append(
        {
            "id": "dengzhan_forced_divergence",
            "name": "强制分歧点",
            "group": "strategy",
            "enabled": True,
            "weight": 20,
            "hard_block": False,
            "params": {"min_volume_ratio": 1.5},
        }
    )
    return config


def test_engine_tracks_the_armed_window_across_bars(store):
    """The S0 arms on its own bar and the carry-over starts on the next one.

    The engine holds this state because rule evaluation is stateless, and the
    ordering is easy to get wrong: armed_age has to describe bars *before* the
    current one, so the arming bar itself must report 0 carried bars rather
    than arming and then immediately reading its own state back.
    """

    from app.data.fundamentals import FundamentalSnapshot, FundamentalsStore

    seed_benchmark(store)
    # Limit up at 44 on 01-03, then quiet bars that are not themselves S0.
    insert_bar(store, "SH600100", "2020-01-01", 100, 100, 99, 100)
    insert_bar(store, "SH600100", "2020-01-02", 45, 45, 40, 40)
    insert_bar(store, "SH600100", "2020-01-03", 41, 44, 41, 44)
    for day, close in (("2020-01-06", 44.2), ("2020-01-07", 44.3), ("2020-01-08", 44.4)):
        insert_bar(store, "SH600100", day, close, close + 0.2, close - 0.2, close)

    FundamentalsStore(store).upsert(
        [
            FundamentalSnapshot(
                symbol="600100",
                name="fixture",
                as_of="2020-01-01",
                price=44.0,
                market_cap_billion=88.0,  # inside the 50-200 band
                float_cap_billion=88.0,
                pb=2.0,
                total_share_billion=2.0,
                book_value_per_share=22.0,
                available_at="2020-01-01T06:00:00+00:00",
            )
        ]
    )

    def run(window):
        return BacktestEngine(config=_armed_engine_config(window)).run(
            "2020-01-01", "2020-01-08", ["SH600100"], 100000, 1, 0.2, persist=False
        )

    same_bar = run(0)
    assert same_bar["metrics"]["armed_window_days"] == 0
    assert same_bar["metrics"]["armed_window_bar_count"] == 0

    armed = run(5)
    assert armed["metrics"]["armed_window_days"] == 5
    # Three quiet bars follow the S0 and each is evaluated while armed; the S0
    # bar itself is not counted, which is the ordering this test exists for.
    assert armed["metrics"]["armed_window_bar_count"] == 3
