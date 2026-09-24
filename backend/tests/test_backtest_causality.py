"""Execution causality of the production daily-bar backtest (synthetic bars only).

Metamorphic requirement: holding every pre-open input fixed and changing only
the session's later prices - close, high, low, amount/volume - must not change
any order intent committed for that session, nor its budget. Fill adjudication
may use later prices only under an explicitly named policy.
"""
from __future__ import annotations

import pytest

from app.backtest.engine import BacktestEngine
from app.backtest.execution import BacktestExecutionModel
from app.backtest.execution_contract import (
    FILL_POLICY_PRE_OPEN,
    FILL_POLICY_RETROSPECTIVE,
    adjudication_bases,
)

HELD, ENTRY, INDEX = "SH600101", "SH600102", "SH000300"
DAYS = ["2020-01-01", "2020-01-02", "2020-01-03", "2020-01-04", "2020-01-05"]
CHECK_DAY = DAYS[3]  # HELD is already held; ENTRY is bought at this open


@pytest.fixture
def store(test_db):
    with test_db.connect() as conn:
        for table in ("daily_bar_cache", "historical_backtest_trades",
                      "historical_backtest_closed_trades", "historical_backtest_daily_equity",
                      "historical_backtest_runs", "symbol_fundamental_snapshot"):
            conn.execute(f"DELETE FROM {table}")
    return test_db


def _config():
    # One always-firing signal rule, as in test_backtest_engine.py.
    return {
        "candidate_tiers": {"strong_min_score": 20, "watch_min_score": 10},
        "rules": [{"id": "dengzhan_forced_divergence", "name": "volume", "group": "strategy",
                   "enabled": True, "weight": 100, "hard_block": False,
                   "params": {"min_volume_ratio": 1.0}}],
        "exit_rules": {"stop_loss_pct": 6.0, "partial_take_profit_pct": 15.0,
                       "partial_take_profit_ratio": 0.5, "break_ma_window": 5,
                       "require_below_limit_up_avg": False, "max_holding_days": None},
    }


def _bars(check_day_overrides=None):
    """(symbol, day) -> [open, high, low, close, volume, amount]. Large amounts so
    the budget, not the participation cap, binds."""

    bars = {}
    for index, day in enumerate(DAYS):
        bars[(INDEX, day)] = [100 + index, 101 + index, 99 + index, 100 + index, 1e6, 1e10]
        bars[(HELD, day)] = [10.0 + 0.1 * index, 10.3 + 0.1 * index, 9.9 + 0.1 * index,
                             10.1 + 0.1 * index, 1e7, 1e9]
        if index >= 1:  # ENTRY lists one day later, so it is bought one session after HELD
            bars[(ENTRY, day)] = [20.0 + 0.1 * index, 20.4 + 0.1 * index, 19.8 + 0.1 * index,
                                  20.1 + 0.1 * index, 1e7, 1e9]
    for (symbol, field), value in (check_day_overrides or {}).items():
        position = ["open", "high", "low", "close", "volume", "amount"].index(field)
        assert field != "open", "the opening print is pre-trade information for a market order"
        bars[(symbol, CHECK_DAY)][position] = value
    return bars


def _run(store, bars, *, fill_policy=FILL_POLICY_RETROSPECTIVE):
    with store.connect() as conn:
        conn.execute("DELETE FROM daily_bar_cache")
        conn.executemany(
            "INSERT INTO daily_bar_cache(symbol, trade_date, open, high, low, close, volume, amount, "
            "source, quality_status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'synthetic', 'ready')",
            [(symbol, day, *values) for (symbol, day), values in sorted(bars.items())])
    return BacktestEngine(config=_config()).run(
        DAYS[0], DAYS[-1], [HELD, ENTRY], 1_000_000, 2, 0.3,
        persist=False, fill_policy=fill_policy, include_intents=True)


def _session_intents(result, day=CHECK_DAY):
    return {intent["intent_id"]: intent for intent in result["order_intents"] if intent["session"] == day}


# Each variant moves only prices observed after the check day's open.
VARIANTS = {
    "entry_close_high_low": {(ENTRY, "close"): 25.0, (ENTRY, "high"): 25.5, (ENTRY, "low"): 19.0},
    "entry_capacity_collapses": {(ENTRY, "amount"): 1_000.0, (ENTRY, "volume"): 1.0},
    "held_rallies_through_take_profit": {(HELD, "high"): 14.0, (HELD, "close"): 13.8},
    "held_crashes_through_stop": {(HELD, "low"): 7.0, (HELD, "close"): 7.2},
    "held_close_only": {(HELD, "close"): 12.9},
    "index_close": {(INDEX, "close"): 80.0, (INDEX, "low"): 79.0},
}


@pytest.mark.parametrize("fill_policy", [FILL_POLICY_RETROSPECTIVE, FILL_POLICY_PRE_OPEN])
@pytest.mark.parametrize("variant", sorted(VARIANTS))
def test_later_session_prices_never_change_committed_intents_or_budgets(store, variant, fill_policy):
    baseline = _session_intents(_run(store, _bars(), fill_policy=fill_policy))
    varied = _session_intents(_run(store, _bars(VARIANTS[variant]), fill_policy=fill_policy))
    entry_id = f"{CHECK_DAY}:buy:{ENTRY}:market_at_open"
    assert entry_id in baseline, "fixture must commit an entry on the check day"
    assert any(intent["symbol"] == HELD for intent in baseline.values()), "HELD must carry exit orders"
    assert set(varied) == set(baseline)
    for intent_id, intent in baseline.items():
        assert varied[intent_id]["fingerprint"] == intent["fingerprint"], (variant, intent_id)
    assert varied[entry_id]["budget"] == baseline[entry_id]["budget"]
    assert varied[entry_id]["requested_quantity"] == baseline[entry_id]["requested_quantity"]


def test_open_sizing_marks_holdings_at_the_prior_close_not_the_session_close(store):
    bars = _bars()
    result = _run(store, bars)
    entry = _session_intents(result)[f"{CHECK_DAY}:buy:{ENTRY}:market_at_open"]
    held_buy = next(i for i in result["order_intents"] if i["symbol"] == HELD and i["side"] == "buy")
    quantity = held_buy["requested_quantity"]
    prior_close = bars[(HELD, DAYS[2])][3]
    session_close = bars[(HELD, CHECK_DAY)][3]
    inputs = entry["sizing_inputs"]
    assert inputs["positions_marked_at_last_close"] == pytest.approx(quantity * prior_close)
    assert inputs["positions_marked_at_last_close"] != pytest.approx(quantity * session_close)
    # Non-vacuity: the pre-fix rule (cash + holdings at the SESSION close) moves
    # with a later-only variant, which the committed budget above does not.
    moved = _bars(VARIANTS["held_close_only"])[(HELD, CHECK_DAY)][3]
    assert quantity * moved != pytest.approx(quantity * session_close)


def test_intraday_exit_proceeds_do_not_fund_the_same_open(store):
    crashed = _run(store, _bars(VARIANTS["held_crashes_through_stop"]))
    held_orders = [i for i in _session_intents(crashed).values() if i["symbol"] == HELD]
    assert any(i["order_type"] == "resting_stop" for i in held_orders)
    entry = _session_intents(crashed)[f"{CHECK_DAY}:buy:{ENTRY}:market_at_open"]
    baseline = _session_intents(_run(store, _bars()))[f"{CHECK_DAY}:buy:{ENTRY}:market_at_open"]
    assert entry["sizing_inputs"] == baseline["sizing_inputs"]
    assert crashed["metrics"]["exit_reason_counts"].get("stop_loss") == 1


def test_fill_adjudication_is_named_and_the_causal_policy_ignores_later_prices(store):
    collapsed = VARIANTS["entry_capacity_collapses"]
    retro = _run(store, _bars(collapsed), fill_policy=FILL_POLICY_RETROSPECTIVE)
    causal = _run(store, _bars(collapsed), fill_policy=FILL_POLICY_PRE_OPEN)
    causal_base = _run(store, _bars(), fill_policy=FILL_POLICY_PRE_OPEN)

    contract = retro["metrics"]["execution_contract"]
    assert contract["fill_policy"] == FILL_POLICY_RETROSPECTIVE
    assert contract["market_at_open"]["capacity_basis"] == "same_session_amount"
    assert contract["qualified_historical_execution"] is False
    assert contract["same_session_sale_proceeds_reused"] is False
    assert causal["metrics"]["execution_contract"]["market_at_open"] == {
        "fill_basis": "opening_print", "price_band_basis": "session_open",
        "capacity_basis": "prior_session_amount"}

    # Retrospective: the collapsed same-session amount rejects the entry fill...
    assert any(f"{CHECK_DAY} {ENTRY} entry blocked: liquidity" in w for w in retro["execution_warnings"])
    # ...while the pre-open policy's fill uses only the prior session and is unchanged.
    assert not any(f"{CHECK_DAY} {ENTRY} entry blocked" in w for w in causal["execution_warnings"])
    assert causal["metrics"]["entry_fill_count"] == causal_base["metrics"]["entry_fill_count"]


def test_causal_price_band_uses_the_opening_print_and_capacity_needs_a_prior_session():
    model = BacktestExecutionModel(max_participation_rate=0.005)
    opened_at_limit = {"open": 11.0, "high": 11.0, "low": 10.2, "close": 10.3, "amount": 1e9, "volume": 1e7}
    retro = model.decide("buy", 1000, 11.0, opened_at_limit, 10.0, 9.8)
    causal = model.decide("buy", 1000, 11.0, opened_at_limit, 10.0, 9.8,
                          price_band_basis="session_open", capacity_basis="prior_session_amount",
                          capacity_bar={"amount": 1e9, "volume": 1e7, "high": 10, "low": 10, "close": 10})
    # A limit-up open that later breaks: retrospective fills at the open, the
    # causal band refuses what could not be known to be fillable at the open.
    assert retro.fill_status == "full"
    assert (causal.fill_status, causal.reject_reason) == ("rejected", "open_at_limit_up")
    unproven = model.decide("buy", 1000, 10.0, {**opened_at_limit, "open": 10.0}, 10.0, 9.8,
                            price_band_basis="session_open", capacity_basis="prior_session_amount",
                            capacity_bar=None)
    assert (unproven.fill_status, unproven.reject_reason) == ("rejected", "capacity_unproven")
    assert adjudication_bases(FILL_POLICY_PRE_OPEN, "resting_stop")["price_band_basis"] == "session_range"


def test_entry_budget_covers_fees_so_a_fill_never_overdraws(store):
    result = _run(store, _bars())
    for intent in result["order_intents"]:
        if intent["side"] == "buy":
            assert intent["reserved_cash"] <= intent["budget"] + 1e-6
    assert result["metrics"]["order_intent_count"] == len(result["order_intents"])


def test_unknown_fill_policy_is_rejected(store):
    with pytest.raises(ValueError):
        BacktestEngine(config=_config()).run(DAYS[0], DAYS[-1], [HELD], 100000, 1, 0.2,
                                             persist=False, fill_policy="optimistic")
