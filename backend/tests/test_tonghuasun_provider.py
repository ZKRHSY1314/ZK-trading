from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path
from urllib.request import ProxyHandler

import pandas as pd
import pytest

from app.data.daily_bar_cache import DailyBarCacheService
from app.data.tonghuasun_provider import (
    SOURCE,
    TonghuasunConfigurationError,
    TonghuasunConnection,
    TonghuasunDataError,
    TonghuasunMarketDataProvider,
    _RejectRedirects,
    _NO_REDIRECT_OPENER,
    _trade_date,
    tonghuasun_full_code,
)
from app.storage.sqlite_store import SQLiteStore


class StubResponse:
    status = 200

    def __init__(self, value: object) -> None:
        self._buffer = BytesIO(json.dumps(value).encode("utf-8"))

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self, size: int = -1) -> bytes:
        return self._buffer.read(size)


def test_default_loopback_transport_has_no_proxy_handler() -> None:
    # urllib otherwise adds environment/system proxies automatically.
    assert not any(isinstance(handler, ProxyHandler) for handler in _NO_REDIRECT_OPENER.handlers)


@pytest.mark.parametrize("returned", ["600000.SZ", "600000.BJ", "600000.UNKNOWN", "SZ600000", "UNKNOWN600000"])
def test_response_exchange_suffix_is_not_reinferred_from_stock_digits(returned) -> None:
    def opener(request, *, timeout):
        return StubResponse({"ok": True, "data": {"items": [{
            "security": {"fullCode": returned}, "points": [],
        }]}})

    provider = TonghuasunMarketDataProvider(
        TonghuasunConnection("http://127.0.0.1:17180", "local-secret", Path(".")),
        opener=opener,
    )
    with pytest.raises(TonghuasunDataError, match="different exchange"):
        provider.get_daily_bars("600000.SH", days=1)


@pytest.mark.parametrize("url", ["http://example.com:17180", "http://192.168.1.3:17180"])
def test_explicit_connection_cannot_bypass_loopback_discovery_validation(url) -> None:
    with pytest.raises(TonghuasunConfigurationError, match="loopback"):
        TonghuasunConnection(url, "local-secret", Path("."))


def test_connection_discovery_reads_plugin_owned_secret_without_exposing_it(tmp_path) -> None:
    (tmp_path / "runtime").mkdir()
    (tmp_path / "config.json").write_text(
        json.dumps({"localAccessToken": "local-secret", "preferredPort": 17180}),
        encoding="utf-8",
    )
    (tmp_path / "runtime" / "endpoint.json").write_text(
        json.dumps(
            {
                "baseUrl": "http://127.0.0.1:17180",
                "pluginVersion": "0.2.13",
            }
        ),
        encoding="utf-8",
    )

    connection = TonghuasunConnection.discover(tmp_path)

    assert connection.base_url == "http://127.0.0.1:17180"
    assert connection.access_token == "local-secret"
    assert connection.plugin_version == "0.2.13"
    assert "local-secret" not in repr(connection)
    status = TonghuasunMarketDataProvider(connection).status()
    assert status == {
        "status": "configured",
        "source": SOURCE,
        "base_url": "http://127.0.0.1:17180",
        "plugin_version": "0.2.13",
        "market_data_only": True,
        "loopback_only": True,
    }


@pytest.mark.parametrize(
    "base_url",
    (
        "https://127.0.0.1:17180",
        "http://192.168.1.20:17180",
        "http://example.com:17180",
        "http://127.0.0.1:17180/api/v2",
    ),
)
def test_connection_discovery_rejects_non_loopback_origins(
    tmp_path,
    base_url: str,
) -> None:
    (tmp_path / "runtime").mkdir()
    (tmp_path / "config.json").write_text(
        json.dumps({"localAccessToken": "local-secret"}),
        encoding="utf-8",
    )
    (tmp_path / "runtime" / "endpoint.json").write_text(
        json.dumps({"baseUrl": base_url}),
        encoding="utf-8",
    )

    with pytest.raises(TonghuasunConfigurationError, match="loopback"):
        TonghuasunConnection.discover(tmp_path)


def test_status_endpoint_is_market_only_and_does_not_require_the_plugin(
    client,
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.delenv("TONGHUASUN_AGENT_HOME", raising=False)
    monkeypatch.delenv("TONGHUASUN_CODEX_HOME", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    response = client.get("/api/data/tonghuasun/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "not_configured"
    assert payload["market_data_only"] is True
    assert payload["loopback_only"] is True
    assert payload["live_trading_enabled"] is False
    assert "access_token" not in payload


def test_daily_candles_use_only_the_read_only_market_endpoint() -> None:
    captured = {}

    def opener(request, *, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return StubResponse(
            {
                "ok": True,
                "data": {
                    "items": [
                        {
                            "security": {"fullCode": "600000.SH"},
                            "points": [
                                {
                                    "timestampUtc": "2026-08-31T07:00:00Z",
                                    "values": {
                                        "open": 10.0,
                                        "high": 10.8,
                                        "low": 9.9,
                                        "latest": 10.6,
                                        "transaction_volume": 123_400,
                                        "transaction_amount": 1_300_000,
                                        "date_time": "20260831",
                                    },
                                }
                            ],
                        }
                    ]
                },
            }
        )

    provider = TonghuasunMarketDataProvider(
        TonghuasunConnection(
            base_url="http://127.0.0.1:17180",
            access_token="local-secret",
            product_home=Path("."),
        ),
        timeout=2.5,
        opener=opener,
    )

    frame = provider.get_daily_bars("SH600000", adjust="qfq", days=300)

    assert frame.to_dict("records") == [
        {
            "date": "2026-08-31",
            "open": 10.0,
            "high": 10.8,
            "low": 9.9,
            "close": 10.6,
            # 123_400 股 as reported by the host, normalized to 手 for the cache.
            "volume": 1_234.0,
            "amount": 1_300_000,
        }
    ]
    assert frame.attrs == {
        "source": SOURCE,
        "adjustment_mode": "qfq",
        "volume_unit": "hand",
    }
    request = captured["request"]
    assert request.full_url == "http://127.0.0.1:17180/api/v2/quotes/candle"
    assert captured["timeout"] == 2.5
    headers = {key.lower(): value for key, value in request.header_items()}
    assert headers["x-tonghuasun-codex-token"] == "local-secret"
    payload = json.loads(request.data)
    assert payload["codes"] == ["600000.SH"]
    assert payload["security"] == {
        "market": 1,
        "code": "600000",
        "fullCode": "600000.SH",
    }
    assert payload["period"] == 7
    assert payload["adjustment"] == 1
    assert payload["limit"] == 300
    assert request.method == "POST"


@pytest.mark.parametrize("days", [1, 2, 3, 5])
def test_daily_candles_bound_host_over_return_to_latest_validated_dates(days) -> None:
    captured = {}
    points = [
        {
            "values": {
                "open": 10.0,
                "high": 11.0,
                "low": 9.0,
                "latest": 10.5,
                "transaction_volume": 100,
                "transaction_amount": 1050,
                "date_time": date,
            }
        }
        for date in ("20260903", "20260901", "20260902")
    ]

    def opener(request, *, timeout):
        captured["payload"] = json.loads(request.data)
        return StubResponse(
            {"ok": True, "data": {"items": [{
                "security": {"fullCode": "600000.SH"}, "points": points,
            }]}}
        )

    provider = TonghuasunMarketDataProvider(
        TonghuasunConnection("http://127.0.0.1:17180", "local-secret", Path(".")),
        opener=opener,
    )
    frame = provider.get_daily_bars("600000.SH", days=days)

    assert captured["payload"]["limit"] == days
    assert frame["date"].tolist() == ["2026-09-01", "2026-09-02", "2026-09-03"][-days:]
    assert frame.index.tolist() == list(range(min(days, 3)))
    assert frame.attrs == {
        "source": SOURCE,
        "adjustment_mode": "qfq",
        "volume_unit": "hand",
    }

    # Even an extra old row that would be trimmed must pass validation.
    points[1]["values"]["transaction_amount"] = -1
    with pytest.raises(TonghuasunDataError, match="negative volume or amount"):
        provider.get_daily_bars("600000.SH", days=days)


def test_error_envelope_is_sanitized_and_does_not_include_token() -> None:
    provider = TonghuasunMarketDataProvider(
        TonghuasunConnection(
            base_url="http://127.0.0.1:17180",
            access_token="local-secret",
            product_home=Path("."),
        ),
        opener=lambda *_args, **_kwargs: StubResponse(
            {
                "ok": False,
                "error": {"code": "not_ready", "message": "host is not ready"},
            }
        ),
    )

    with pytest.raises(TonghuasunDataError, match="not_ready") as error:
        provider.get_daily_bars("600000")
    assert "local-secret" not in str(error.value)


def test_redirects_are_rejected_before_a_token_can_be_forwarded() -> None:
    handler = _RejectRedirects()
    assert (
        handler.redirect_request(
            object(),
            object(),
            302,
            "Found",
            {},
            "http://example.invalid/token-leak",
        )
        is None
    )


def test_trade_date_uses_shanghai_date_for_timezone_aware_values() -> None:
    assert _trade_date("2026-09-01T00:00:00+08:00") == "2026-09-01"
    assert _trade_date("2026-08-31T16:00:00Z") == "2026-09-01"


@pytest.mark.parametrize(
    ("symbol", "expected"),
    (
        ("SH600000", "600000.SH"),
        ("SZ300750", "300750.SZ"),
        ("BJ920000", "920000.BJ"),
        ("688981", "688981.SH"),
    ),
)
def test_full_code_mapping(symbol: str, expected: str) -> None:
    assert tonghuasun_full_code(symbol) == expected


def test_candle_response_for_a_different_security_is_rejected() -> None:
    provider = TonghuasunMarketDataProvider(
        TonghuasunConnection(
            base_url="http://127.0.0.1:17180",
            access_token="local-secret",
            product_home=Path("."),
        ),
        opener=lambda *_args, **_kwargs: StubResponse(
            {
                "ok": True,
                "data": {
                    "items": [
                        {
                            "security": {"fullCode": "000001.SZ"},
                            "points": [],
                        }
                    ]
                },
            }
        ),
    )

    with pytest.raises(TonghuasunDataError, match="different security"):
        provider.get_daily_bars("SH600000")


def test_candle_response_with_mismatched_adjustment_is_rejected() -> None:
    provider = TonghuasunMarketDataProvider(
        TonghuasunConnection(
            base_url="http://127.0.0.1:17180",
            access_token="local-secret",
            product_home=Path("."),
        ),
        opener=lambda *_args, **_kwargs: StubResponse(
            {"ok": True, "data": {"adjustment": 0, "items": []}}
        ),
    )

    with pytest.raises(TonghuasunDataError, match="adjustment"):
        provider.get_daily_bars("SH600000", adjust="qfq")


@pytest.mark.parametrize(
    "values",
    (
        {
            "open": 10,
            "high": 9,
            "low": 8,
            "latest": 10,
            "transaction_volume": 100,
            "transaction_amount": 1_000,
            "date_time": "20260901",
        },
        {
            "open": 10,
            "high": 11,
            "low": 9,
            "latest": float("nan"),
            "transaction_volume": 100,
            "transaction_amount": 1_000,
            "date_time": "20260901",
        },
        {
            "open": 10,
            "high": 11,
            "low": 9,
            "latest": 10,
            "transaction_volume": 100,
            "transaction_amount": -1,
            "date_time": "20260901",
        },
    ),
)
def test_invalid_candle_values_are_rejected(values: dict) -> None:
    provider = TonghuasunMarketDataProvider(
        TonghuasunConnection(
            base_url="http://127.0.0.1:17180",
            access_token="local-secret",
            product_home=Path("."),
        ),
        opener=lambda *_args, **_kwargs: StubResponse(
            {
                "ok": True,
                "data": {
                    "items": [
                        {
                            "security": {"fullCode": "600000.SH"},
                            "points": [{"values": values}],
                        }
                    ]
                },
            }
        ),
    )

    with pytest.raises(TonghuasunDataError):
        provider.get_daily_bars("SH600000")


def test_missing_transaction_amount_is_rejected_not_approximated() -> None:
    provider = TonghuasunMarketDataProvider(
        TonghuasunConnection(
            base_url="http://127.0.0.1:17180",
            access_token="local-secret",
            product_home=Path("."),
        ),
        opener=lambda *_args, **_kwargs: StubResponse(
            {
                "ok": True,
                "data": {
                    "items": [
                        {
                            "security": {"fullCode": "600000.SH"},
                            "points": [
                                {
                                    "values": {
                                        "open": 10,
                                        "high": 11,
                                        "low": 9,
                                        "latest": 10,
                                        "transaction_volume": 100,
                                        "transaction_amount": None,
                                        "date_time": "20260901",
                                    }
                                }
                            ],
                        }
                    ]
                },
            }
        ),
    )

    with pytest.raises(TonghuasunDataError, match="transaction_amount"):
        provider.get_daily_bars("SH600000")


def test_daily_bar_cache_can_prefer_tonghuasun_without_a_parallel_store(
    monkeypatch,
    tmp_path,
) -> None:
    store = SQLiteStore(tmp_path / "tonghuasun-cache.sqlite3")
    store.init()
    service = DailyBarCacheService(store=store)
    frame = pd.DataFrame(
        [
            {
                "date": "2026-08-31",
                "open": 10.0,
                "high": 10.8,
                "low": 9.9,
                "close": 10.6,
                "volume": 123_400,
                "amount": 1_300_000,
            }
        ]
    )
    frame.attrs.update(
        source=SOURCE,
        adjustment_mode="qfq",
        volume_unit="unknown",
    )
    monkeypatch.setattr(
        service.tonghuasun_provider,
        "get_daily_bars",
        lambda *_args, **_kwargs: frame,
    )
    monkeypatch.setattr(
        service,
        "_load_tencent_qfq_daily_bars",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("Tencent should not be called after local success")
        ),
    )
    monkeypatch.setattr(
        service.builder.provider,
        "get_daily_bars",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("AKShare should not be called after local success")
        ),
    )

    result = service.refresh_symbols(
        ["SH600000"],
        days=120,
        source_policy="tonghuasun_first",
    )

    item = result["results"][0]
    assert item["status"] == "success"
    assert item["source"] == SOURCE
    assert item["attempts"] == [{"source": SOURCE, "status": "success"}]
    row = store.fetch_one(
        """
        SELECT symbol, trade_date, amount, source, adjustment_mode, volume_unit,
               quality_status
        FROM daily_bar_cache
        WHERE symbol = 'SH600000'
        """
    )
    assert row == {
        "symbol": "SH600000",
        "trade_date": "2026-08-31",
        "amount": 1_300_000.0,
        "source": SOURCE,
        "adjustment_mode": "qfq",
        "volume_unit": "unknown",
        "quality_status": "ready",
    }


def test_concurrent_callers_are_serialized_and_spaced_for_the_local_host():
    """Callers keep their own concurrency; the host still sees one paced stream.

    The desktop client degrades under parallel load by answering with an empty
    candle frame instead of an error, which the cache reads as "no history" and
    charges to the next source - so the damage is silent. Measured on a
    full-market sweep, 4 unpaced workers produced usable data for 4 of 30
    symbols where a serial 1 req/s sweep produced 20 of 20.

    refresh_bars still asks for 5 workers, so the gate has to hold regardless of
    what the caller does.
    """

    import threading
    import time

    interval = 0.05
    in_flight = 0
    overlapped = False
    starts: list[float] = []
    guard = threading.Lock()

    def opener(request, timeout):
        nonlocal in_flight, overlapped
        with guard:
            in_flight += 1
            overlapped = overlapped or in_flight > 1
            starts.append(time.monotonic())
        time.sleep(interval / 2)
        with guard:
            in_flight -= 1
        return StubResponse(
            {
                "ok": True,
                "data": {
                    "adjustment": 1,
                    "candles": [
                        {
                            "security": {"fullCode": "600000.SH"},
                            "points": [
                                {
                                    "timestampUtc": "2026-08-31T07:00:00Z",
                                    "values": {
                                        "open": 10.0,
                                        "high": 10.8,
                                        "low": 9.9,
                                        "latest": 10.6,
                                        "transaction_volume": 123_400,
                                        "transaction_amount": 1_300_000,
                                        "date_time": "20260831",
                                    },
                                }
                            ],
                        }
                    ],
                },
            }
        )

    provider = TonghuasunMarketDataProvider(
        TonghuasunConnection(
            base_url="http://127.0.0.1:17180",
            access_token="local-secret",
            product_home=Path("."),
        ),
        timeout=2.5,
        min_request_interval=interval,
        opener=opener,
    )

    threads = [
        threading.Thread(target=provider.get_daily_bars, args=("SH600000",)) for _ in range(5)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(starts) == 5
    assert not overlapped, "requests reached the local host concurrently"
    starts.sort()
    gaps = [later - earlier for earlier, later in zip(starts, starts[1:])]
    # Spacing is measured from completion, so every gap clears the interval.
    assert all(gap >= interval for gap in gaps), gaps
