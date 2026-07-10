import importlib.util
from datetime import datetime, timezone, timedelta
from pathlib import Path


def load_poll_module():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "poll_sim_order_readback.py"
    spec = importlib.util.spec_from_file_location("poll_sim_order_readback", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_market_session_marks_weekend_closed():
    poller = load_poll_module()

    session = poller.market_session(datetime(2026, 7, 4, 11, 50, tzinfo=timezone(timedelta(hours=8))))

    assert session["status"] == "closed"
    assert session["is_open"] is False
    assert session["reason"] == "weekend_closed"


def test_market_session_marks_workday_open():
    poller = load_poll_module()

    session = poller.market_session(datetime(2026, 7, 6, 10, 0, tzinfo=timezone(timedelta(hours=8))))

    assert session["status"] == "open"
    assert session["is_open"] is True
    assert session["reason"] == "trading_window_open"


def test_pending_order_waits_when_market_closed():
    poller = load_poll_module()
    session = {"is_open": False}
    results = [
        {"readback_type": "screen_today_orders", "status": "pending_order_detected"},
        {"readback_type": "screen_today_trades", "status": "screen_table_unparsed"},
        {"readback_type": "screen_positions", "status": "screen_table_unparsed"},
    ]

    assert poller.classify_poll_status(results, session) == "pending_order_waiting_for_market_session"

