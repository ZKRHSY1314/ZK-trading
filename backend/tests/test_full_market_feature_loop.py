from scripts import full_market_feature_loop


def test_full_market_worker_retries_unsuccessful_cycles_early() -> None:
    assert full_market_feature_loop.next_interval_seconds("failed", 14_400) == 900
    assert full_market_feature_loop.next_interval_seconds("partial", 14_400) == 900
    assert full_market_feature_loop.next_interval_seconds("completed", 14_400) == 14_400


def test_full_market_worker_blocks_before_scan_when_live_trading_is_enabled(
    monkeypatch,
) -> None:
    calls = []

    def _request(method, url, payload=None, *, timeout=30):
        calls.append((method, url, payload, timeout))
        return {"status": "ok", "live_trading_enabled": True}

    monkeypatch.setattr(full_market_feature_loop, "request_json", _request)

    result = full_market_feature_loop.run_once(
        "http://127.0.0.1:8000",
        candidate_limit=300,
        lookback_bars=120,
        timeout_seconds=300,
    )

    assert result["status"] == "blocked"
    assert result["reason"] == "live_trading_enabled"
    assert len(calls) == 1
