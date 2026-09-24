from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import pytest

from app.market_regime.service import MarketRegimeService
from app.reference_data.global_markets import GlobalMarketIngestor
from app.storage.sqlite_store import SQLiteStore


NOW = datetime(2026, 7, 12, 4, tzinfo=timezone.utc)


class _GlobalProvider:
    def __init__(self) -> None:
        self.smh_latest_delta = 0.0

    @staticmethod
    def _daily(base: float) -> pd.DataFrame:
        dates = pd.date_range("2026-07-03", periods=8, freq="D")
        closes = [base + index for index in range(8)]
        return pd.DataFrame(
            {
                "date": dates,
                "open": [value - 0.5 for value in closes],
                "high": [value + 1.0 for value in closes],
                "low": [value - 1.0 for value in closes],
                "close": closes,
                "volume": [1_000 + index for index in range(8)],
            }
        )

    def get_us_daily(self, symbol: str) -> pd.DataFrame:
        frame = self._daily(600.0 if symbol == "SMH" else 200.0)
        if symbol == "SMH":
            frame.loc[frame.index[-1], "close"] += self.smh_latest_delta
            frame.loc[frame.index[-1], "high"] += self.smh_latest_delta
        return frame

    def get_foreign_futures_daily(self, symbol: str) -> pd.DataFrame:
        bases = {"CL": 70.0, "GC": 4_000.0, "BTC": 60_000.0}
        return self._daily(bases[symbol])

    def get_sox_daily(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "\u65e5\u671f": pd.date_range("2026-07-03", periods=8, freq="D"),
                "\u6700\u65b0\u503c": [5_000.0 + index for index in range(8)],
            }
        )

    def get_crypto_spot(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "\u5e02\u573a": "Bitstamp",
                    "\u4ea4\u6613\u54c1\u79cd": "BTCUSD",
                    "\u6700\u8fd1\u62a5\u4ef7": 60_000.0,
                    "24\u5c0f\u65f6\u6700\u9ad8": 61_000.0,
                    "24\u5c0f\u65f6\u6700\u4f4e": 59_000.0,
                    "24\u5c0f\u65f6\u6210\u4ea4\u91cf": 100.0,
                    "\u66f4\u65b0\u65f6\u95f4": "2026-07-12 10:00:00",
                }
            ]
        )


def _ingestor(tmp_path, provider=None, *, clock=None):
    store = SQLiteStore(tmp_path / "global.sqlite3")
    store.init()
    return store, GlobalMarketIngestor(
        store=store,
        provider=provider or _GlobalProvider(),
        clock=clock,
    )


def test_global_dry_run_normalizes_six_bars_and_reports_source_coverage(tmp_path) -> None:
    store, ingestor = _ingestor(tmp_path)

    result = ingestor.run(apply=False, now=NOW, days=6, include_sox=True)

    assert result["status"] == "planned"
    assert result["requested_source_count"] == 6
    assert result["fetched_source_count"] == 6
    assert result["ready_source_count"] == 6
    assert result["degraded_source_count"] == 0
    assert result["source_coverage_pct"] == 100.0
    assert result["ready_source_coverage_pct"] == 100.0
    assert result["bar_records_planned"] == 36
    assert result["bar_records_new"] == 36
    assert result["bar_records_revised"] == 0
    assert result["bar_records_written"] == 0
    by_symbol = {item["symbol"]: item for item in result["sources"]}
    assert by_symbol["SMH"]["bars_selected"] == 6
    assert by_symbol["SMH"]["quality_statuses"] == ["ready"]
    assert by_symbol["SMH"]["price_adjustment"] == "qfq"
    assert by_symbol["SOX"]["bars_selected"] == 6
    assert by_symbol["BTC"]["status"] == "ready"
    assert by_symbol["BTC"]["quality_statuses"] == ["ready"]
    assert result["freshness"] == {"fresh": 6}
    assert store.fetch_one("SELECT COUNT(*) AS count FROM global_market_bars")["count"] == 0


def test_apply_appends_revisions_idempotently_and_preserves_point_in_time_values(tmp_path) -> None:
    provider = _GlobalProvider()
    store, ingestor = _ingestor(tmp_path, provider)

    first = ingestor.run(apply=True, now=NOW, days=6, include_sox=False)
    repeated = ingestor.run(apply=True, now=NOW, days=6, include_sox=False)

    assert first["bar_records_written"] == 30
    assert repeated["bar_records_new"] == 0
    assert repeated["bar_records_revised"] == 0
    assert repeated["bar_records_unchanged"] == 30
    assert repeated["bar_records_written"] == 0
    assert store.fetch_one("SELECT COUNT(*) AS count FROM global_market_bars")["count"] == 30
    assert store.fetch_one(
        "SELECT COUNT(*) AS count FROM global_market_bars WHERE quality_status = 'ready'"
    )["count"] == 30
    btc = store.fetch_one("SELECT * FROM global_market_bars WHERE symbol = 'BTC'")
    assert btc["quality_status"] == "ready"
    assert btc["asset_class"] == "crypto_future"
    assert btc["available_at"] == "2026-07-12T04:00:00Z"

    provider.smh_latest_delta = 2.0
    later = datetime(2026, 7, 12, 5, tzinfo=timezone.utc)
    changed = ingestor.run(apply=True, now=later, days=6, include_sox=False)

    assert changed["bar_records_revised"] == 1
    assert changed["bar_records_unchanged"] == 29
    assert store.fetch_one("SELECT COUNT(*) AS count FROM global_market_bars")["count"] == 31
    latest_smh = store.fetch_one(
        "SELECT close, source, available_at, quality_status FROM global_market_bars "
        "WHERE symbol = 'SMH' ORDER BY bar_time DESC, datetime(available_at) DESC LIMIT 1"
    )
    assert latest_smh["close"] == 609.0
    assert latest_smh["source"].startswith("akshare.stock_us_daily[qfq]#revision-")
    assert latest_smh["available_at"] == "2026-07-12T05:00:00Z"
    assert latest_smh["quality_status"] == "ready"
    older_smh = store.fetch_one(
        "SELECT available_at FROM global_market_bars "
        "WHERE symbol = 'SMH' AND source = 'akshare.stock_us_daily[qfq]' "
        "ORDER BY bar_time DESC LIMIT 1"
    )
    assert older_smh["available_at"] == "2026-07-12T04:00:00Z"

    old_features = MarketRegimeService(store).get_cross_market_features("2026-07-12T04:30:00Z")
    old_smh = next(item for item in old_features["features"] if item["symbol"] == "SMH")
    assert old_smh["close"] == 607.0
    assert old_smh["source"] == "akshare.stock_us_daily[qfq]"

    features = MarketRegimeService(store).get_cross_market_features("2026-07-12T06:00:00Z")
    feature_symbols = {item["symbol"] for item in features["features"]}
    assert {"SMH", "NVDA", "CL", "GC", "BTC"} <= feature_symbols
    revised_smh = next(item for item in features["features"] if item["symbol"] == "SMH")
    assert revised_smh["close"] == 609.0
    assert revised_smh["source"].startswith("akshare.stock_us_daily[qfq]#revision-")


def test_global_source_failure_is_structured_and_cannot_report_complete(tmp_path) -> None:
    class _PartialProvider(_GlobalProvider):
        def get_us_daily(self, symbol: str) -> pd.DataFrame:
            if symbol == "NVDA":
                raise ConnectionError("sina US source unavailable")
            return super().get_us_daily(symbol)

    _, ingestor = _ingestor(tmp_path, _PartialProvider())

    result = ingestor.run(
        apply=False,
        now=NOW,
        days=6,
        include_sox=False,
        symbol_limit=2,
    )

    assert result["status"] == "partial"
    assert result["source_coverage_pct"] == 50.0
    assert result["failed_source_count"] == 1
    assert result["errors"] == [
        {
            "stage": "global_market_bars",
            "symbol": "NVDA",
            "source": "akshare.stock_us_daily[qfq]",
            "error_type": "ConnectionError",
            "error": "sina US source unavailable",
        }
    ]


def test_market_regime_filters_latest_revision_quality_before_using_older_ready_row(
    tmp_path,
) -> None:
    store, ingestor = _ingestor(tmp_path)
    ingestor.run(apply=True, now=NOW, days=6, include_sox=False, symbol_limit=1)
    latest = store.fetch_one(
        "SELECT * FROM global_market_bars WHERE symbol = 'SMH' "
        "ORDER BY julianday(bar_time) DESC LIMIT 1"
    )
    with store.connect() as conn:
        conn.execute(
            """
            INSERT INTO global_market_bars(
                symbol, asset_class, bar_time, open, high, low, close,
                volume, source, available_at, quality_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                latest["symbol"],
                latest["asset_class"],
                latest["bar_time"],
                latest["open"],
                latest["high"],
                latest["low"],
                999.0,
                latest["volume"],
                "akshare.stock_us_daily[qfq]#revision-degraded",
                "2026-07-12T05:00:00Z",
                "stale",
            ),
        )

    before = MarketRegimeService(store).get_cross_market_features("2026-07-12T04:30:00Z")
    after = MarketRegimeService(store).get_cross_market_features("2026-07-12T06:00:00Z")

    assert before["features"][0]["symbol"] == "SMH"
    assert before["features"][0]["close"] == 607.0
    assert after["features"] == []
    assert after["status"] == "insufficient_data"


def test_fractional_available_at_cutoff_and_same_timestamp_revision_are_deterministic(
    tmp_path,
) -> None:
    provider = _GlobalProvider()
    store, ingestor = _ingestor(tmp_path, provider)
    first_seen = datetime(2026, 7, 12, 4, 0, 0, 900_000, tzinfo=timezone.utc)
    ingestor.run(
        apply=True,
        now=first_seen,
        days=6,
        include_sox=False,
        symbol_limit=1,
    )

    too_early = MarketRegimeService(store).get_cross_market_features(
        "2026-07-12T04:00:00.500000Z"
    )
    assert too_early["features"] == []

    provider.smh_latest_delta = 2.0
    ingestor.run(
        apply=True,
        now=first_seen,
        days=6,
        include_sox=False,
        symbol_limit=1,
    )
    provider.smh_latest_delta = 4.0
    ingestor.run(
        apply=True,
        now=first_seen,
        days=6,
        include_sox=False,
        symbol_limit=1,
    )

    visible = MarketRegimeService(store).get_cross_market_features(
        "2026-07-12T04:00:00.950000Z"
    )
    assert visible["features"][0]["close"] == 611.0
    assert visible["features"][0]["source"].startswith(
        "akshare.stock_us_daily[qfq]#revision-"
    )
    assert store.fetch_one(
        "SELECT COUNT(*) AS count FROM global_market_bars "
        "WHERE symbol = 'SMH' AND julianday(available_at) = julianday(?)",
        ("2026-07-12T04:00:00.900000Z",),
    )["count"] == 8


def test_available_at_uses_post_fetch_clock_instead_of_run_start(tmp_path) -> None:
    retrieved_at = datetime(2026, 7, 12, 4, 7, tzinfo=timezone.utc)
    store, ingestor = _ingestor(tmp_path, clock=lambda: retrieved_at)

    ingestor.run(
        apply=True,
        now=NOW,
        days=6,
        include_sox=False,
        symbol_limit=1,
    )

    row = store.fetch_one(
        "SELECT MIN(available_at) AS available_at FROM global_market_bars WHERE symbol = 'SMH'"
    )
    assert row["available_at"] == "2026-07-12T04:07:00Z"
    before_retrieval = MarketRegimeService(store).get_cross_market_features(
        "2026-07-12T04:06:59.999999Z"
    )
    assert before_retrieval["features"] == []


def test_unfinished_us_session_bar_is_provisional_and_not_a_regime_feature(tmp_path) -> None:
    class _IntradayProvider(_GlobalProvider):
        def get_us_daily(self, symbol: str) -> pd.DataFrame:
            frame = super().get_us_daily(symbol)
            frame.loc[frame.index[-1], "date"] = pd.Timestamp("2026-07-12")
            return frame

    store, ingestor = _ingestor(tmp_path, _IntradayProvider())

    result = ingestor.run(
        apply=True,
        now=NOW,
        days=6,
        include_sox=False,
        symbol_limit=1,
    )

    assert result["status"] == "partial"
    assert result["sources"][0]["status"] == "degraded_provisional"
    assert "provisional" in result["sources"][0]["quality_statuses"]
    features = MarketRegimeService(store).get_cross_market_features("2026-07-12T04:30:00Z")
    assert features["features"] == []


def test_global_days_cannot_drop_below_the_feature_minimum(tmp_path) -> None:
    _, ingestor = _ingestor(tmp_path)

    with pytest.raises(ValueError, match="at least 6"):
        ingestor.run(apply=False, now=NOW, days=5)
