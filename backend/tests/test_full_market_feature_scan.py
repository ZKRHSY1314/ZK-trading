from __future__ import annotations

from datetime import date, timedelta
import json

from app.candidates.full_market_scan import FullMarketFeatureScanner
from app.candidates.selection_v2 import StrategySelectionV2Service
from app.config import settings
from app.data.market_history import MarketHistoryStore
from app.storage.sqlite_store import SQLiteStore


def _seed_history(history: MarketHistoryStore) -> None:
    history.initialize()
    fetched_at = "2026-07-15T16:30:00+08:00"
    with history.connect() as connection:
        connection.executemany(
            """
            INSERT INTO instruments(symbol, name, exchange, provider, fetched_at)
            VALUES (?, ?, ?, 'fixture', ?)
            """,
            [
                ("SH600001", "紧凑样本", "SH", fetched_at),
                ("SZ000002", "波动样本", "SZ", fetched_at),
                ("BJ430001", "缺数样本", "BJ", fetched_at),
            ],
        )
        cursor = connection.execute(
            """
            INSERT INTO universe_snapshots(
                universe_name, snapshot_date, provider, fetched_at,
                member_count, source_hash, metadata_json
            )
            VALUES ('a_share_full_market_cache', '2026-07-15', 'fixture', ?, 3, 'fixture-hash', '{}')
            """,
            (fetched_at,),
        )
        snapshot_id = int(cursor.lastrowid)
        connection.executemany(
            "INSERT INTO universe_members(snapshot_id, symbol) VALUES (?, ?)",
            [(snapshot_id, "SH600001"), (snapshot_id, "SZ000002"), (snapshot_id, "BJ430001")],
        )

        start = date(2026, 5, 7)
        rows = []
        for offset in range(70):
            trade_date = (start + timedelta(days=offset)).isoformat()
            tight_close = 10.0 + offset * 0.006 + (0.03 if offset % 4 == 0 else 0.0)
            volatile_close = 10.0 + (1.7 if offset % 2 else -1.5) + offset * 0.002
            for symbol, close, spread, volume in (
                ("SH600001", tight_close, 0.08, 800.0 if offset >= 65 else 1000.0),
                ("SZ000002", volatile_close, 0.8, 1800.0 if offset % 3 else 500.0),
            ):
                rows.append(
                    (
                        symbol,
                        trade_date,
                        "qfq",
                        close - 0.01,
                        close + spread,
                        close - spread,
                        close,
                        volume,
                        "hand",
                        volume * close,
                        "fixture",
                        fetched_at,
                        fetched_at,
                        f"{symbol}-{trade_date}",
                        "ready",
                    )
                )
        connection.executemany(
            """
            INSERT INTO daily_bars(
                symbol, trade_date, adjustment_mode, open, high, low, close,
                volume, volume_unit, amount, provider, fetched_at, available_at,
                row_hash, quality_status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )


def test_full_market_scan_scores_official_qfq_universe_and_persists_evidence(
    tmp_path,
) -> None:
    runtime = SQLiteStore(tmp_path / "runtime.sqlite3")
    runtime.init()
    history = MarketHistoryStore(tmp_path / "market-history.sqlite3")
    _seed_history(history)

    result = FullMarketFeatureScanner(store=runtime, history_store=history).run(
        limit=1,
        min_bars=60,
        lookback=120,
        persist=True,
        force=True,
    )

    assert result["status"] == "completed"
    assert result["universe_count"] == 3
    assert result["qfq_ready_count"] == 2
    assert result["eligible_count"] == 2
    assert result["selected_count"] == 1
    assert result["items"][0]["symbol"] == "SH600001"
    assert result["items"][0]["features"]["range_20_pct"] < 5
    assert result["safety"] == {
        "research_only": True,
        "simulation_only": True,
        "live_trading_enabled": False,
        "execution_allowed": False,
    }

    run = runtime.fetch_one(
        """
        SELECT as_of_date, universe_count, qfq_ready_count, eligible_count,
               selected_count, live_trading_enabled
        FROM full_market_feature_runs
        """
    )
    assert run == {
        "as_of_date": "2026-07-15",
        "universe_count": 3,
        "qfq_ready_count": 2,
        "eligible_count": 2,
        "selected_count": 1,
        "live_trading_enabled": 0,
    }
    assert len(runtime.fetch_all("SELECT symbol FROM full_market_feature_state")) == 2
    assert runtime.fetch_one("SELECT COUNT(*) AS count FROM candidate_scans") == {"count": 0}
    assert runtime.fetch_one(
        "SELECT COUNT(*) AS count FROM auto_discovered_candidates"
    ) == {"count": 0}


def test_full_market_scan_reuses_unchanged_symbols_and_recomputes_only_revision(
    tmp_path,
) -> None:
    runtime = SQLiteStore(tmp_path / "runtime.sqlite3")
    runtime.init()
    history = MarketHistoryStore(tmp_path / "market-history.sqlite3")
    _seed_history(history)
    scanner = FullMarketFeatureScanner(store=runtime, history_store=history)

    first = scanner.run(limit=1, persist=True)
    second = scanner.run(limit=1, persist=True)

    assert first["incremental"] == {"computed_count": 2, "reused_count": 0}
    assert second["incremental"] == {"computed_count": 0, "reused_count": 2}

    with history.connect() as connection:
        connection.execute(
            """
            UPDATE daily_bars
            SET close = close + 0.01,
                high = high + 0.01,
                row_hash = 'revised-row',
                updated_at = '2026-07-16T10:00:00+08:00'
            WHERE symbol = 'SH600001'
              AND trade_date = (SELECT MAX(trade_date) FROM daily_bars WHERE symbol = 'SH600001')
              AND adjustment_mode = 'qfq'
            """
        )

    third = scanner.run(limit=1, persist=True)

    assert third["incremental"] == {"computed_count": 1, "reused_count": 1}
    assert runtime.fetch_one("SELECT COUNT(*) AS count FROM full_market_feature_runs") == {
        "count": 3
    }
    latest = scanner.latest(limit=1)
    assert latest["status"] == "completed"
    assert latest["run"]["incremental"] == {"computed_count": 1, "reused_count": 1}
    assert latest["candidate_count"] == 1
    assert latest["candidates"][0]["symbol"] == "SH600001"
    assert latest["candidates"][0]["features"]["bar_count"] == 70


def test_full_market_scan_api_reuses_the_lifespan_store(client, monkeypatch) -> None:
    calls: list[tuple[str, object, dict]] = []

    def _run(self, **kwargs):
        calls.append(("run", self.store, kwargs))
        return {"status": "completed", "safety": self._safety()}

    def _latest(self, **kwargs):
        calls.append(("latest", self.store, kwargs))
        return {"status": "completed", "candidate_count": 0, "candidates": []}

    monkeypatch.setattr(FullMarketFeatureScanner, "run", _run)
    monkeypatch.setattr(FullMarketFeatureScanner, "latest", _latest)

    run_response = client.post(
        "/api/candidates/full-market-scan/run",
        params={
            "candidate_limit": 123,
            "lookback_bars": 90,
            "persist": False,
            "force": True,
        },
    )
    latest_response = client.get(
        "/api/candidates/full-market-scan/latest",
        params={"limit": 12, "tier": "strong"},
    )

    assert run_response.status_code == 200
    assert latest_response.status_code == 200
    assert calls[0][0] == "run"
    assert calls[0][1] is client.app.state.runtime_store
    assert calls[0][2] == {
        "limit": 123,
        "lookback": 90,
        "persist": False,
        "force": True,
    }
    assert calls[1] == (
        "latest",
        client.app.state.runtime_store,
        {"limit": 12, "tier": "strong"},
    )


def test_selection_v2_consumes_full_market_state_without_legacy_candidate_rows(
    tmp_path,
) -> None:
    runtime = SQLiteStore(tmp_path / "runtime.sqlite3")
    runtime.init()
    history = MarketHistoryStore(tmp_path / "market-history.sqlite3")
    _seed_history(history)
    FullMarketFeatureScanner(store=runtime, history_store=history).run(limit=1, persist=True)
    with runtime.connect() as connection:
        connection.execute("DELETE FROM auto_discovered_candidates")
        connection.execute(
            """
            INSERT INTO daily_bar_cache(
                symbol, trade_date, open, high, low, close, volume, amount,
                source, adjustment_mode, volume_unit, quality_status
            )
            VALUES (
                'SH600001', '2026-07-15', 10.4, 10.5, 10.3, 10.42,
                800, 8336, 'fixture.qfq', 'qfq', 'hand', 'ready'
            )
            """
        )

    result = StrategySelectionV2Service(store=runtime).run(limit=10)
    rows = result["daily_candidate_snapshot"] + result["data_gap_candidates"]
    candidate = next(item for item in rows if item["symbol"] == "SH600001")

    assert "full_market_feature_state" in result["source"]
    assert "full_market_feature_state" in candidate["evidence_sources"]


def test_selection_v2_exposes_calibrated_probability_as_independent_evidence(
    tmp_path,
) -> None:
    runtime = SQLiteStore(tmp_path / "runtime.sqlite3")
    runtime.init()
    history = MarketHistoryStore(tmp_path / "market-history.sqlite3")
    _seed_history(history)
    FullMarketFeatureScanner(store=runtime, history_store=history).run(limit=1, persist=True)
    with runtime.connect() as connection:
        connection.execute(
            """
            INSERT INTO daily_bar_cache(
                symbol, trade_date, open, high, low, close, volume, amount,
                source, adjustment_mode, volume_unit, quality_status
            ) VALUES (
                'SH600001', '2026-07-15', 10.4, 10.5, 10.3, 10.42,
                800, 8336, 'fixture.qfq', 'qfq', 'hand', 'ready'
            )
            """
        )

    before = StrategySelectionV2Service(store=runtime).run(limit=10)
    before_candidate = next(
        item for item in before["daily_candidate_snapshot"] if item["symbol"] == "SH600001"
    )
    heuristic_probability = before_candidate["features"]["structure_signal"][
        "pre_markup_probability"
    ]

    result_json = json.dumps(
        {
            "label": {
                "horizon_trading_days": 20,
                "target": "future_max_close_return_pct",
                "threshold_pct": 8.0,
                "comparison": ">=",
            },
            "validation": {"status": "ready", "sample_count": 500},
            "safety": {
                "research_only": True,
                "simulation_only": True,
                "execution_allowed": False,
                "orders_generated": False,
            },
        },
        ensure_ascii=False,
    )
    with runtime.connect() as connection:
        cursor = connection.execute(
            """
            INSERT INTO full_market_score_calibration_runs(
                status, schema_version, score_semantics, probability_semantics,
                as_of_date, horizon_trading_days, target_return_pct,
                training_sample_count, validation_sample_count,
                mapped_validation_sample_count, result_json
            ) VALUES (
                'ready', 'full_market_score_calibration.v1',
                'uncalibrated_structure_score',
                'future_20d_max_close_return_ge_8pct',
                '2026-07-15', 20, 8.0, 1000, 500, 500, ?
            )
            """,
            (result_json,),
        )
        connection.execute(
            """
            INSERT INTO full_market_score_calibration_bins(
                calibration_run_id, bin_index, score_lower_inclusive,
                score_upper, upper_bound_inclusive, sample_count,
                success_count, probability, confidence_lower,
                confidence_upper, status
            ) VALUES (?, 0, 0, 100, 1, 1000, 420, 0.42, 0.39, 0.45, 'ready')
            """,
            (int(cursor.lastrowid),),
        )

    after = StrategySelectionV2Service(store=runtime).run(limit=10)
    candidate = next(
        item for item in after["daily_candidate_snapshot"] if item["symbol"] == "SH600001"
    )

    assert candidate["full_market_scan"]["score_semantics"] == (
        "uncalibrated_structure_score"
    )
    assert candidate["full_market_scan"]["calibrated_probability"] == 0.42
    assert candidate["full_market_scan"]["calibration"]["status"] == "ready"
    assert candidate["full_market_scan"]["calibration"]["safety"][
        "execution_allowed"
    ] is False
    assert candidate["features"]["structure_signal"]["pre_markup_probability"] == (
        heuristic_probability
    )


def test_full_market_scan_blocks_all_writes_when_live_trading_is_enabled(
    tmp_path,
    monkeypatch,
) -> None:
    runtime = SQLiteStore(tmp_path / "runtime.sqlite3")
    runtime.init()
    history = MarketHistoryStore(tmp_path / "market-history.sqlite3")
    _seed_history(history)
    monkeypatch.setattr(settings, "enable_live_trading", True)

    result = FullMarketFeatureScanner(store=runtime, history_store=history).run(
        persist=True,
    )

    assert result["status"] == "blocked"
    assert result["reason"] == "live_trading_enabled"
    assert runtime.fetch_one("SELECT COUNT(*) AS count FROM full_market_feature_runs") == {
        "count": 0
    }
    assert runtime.fetch_one("SELECT COUNT(*) AS count FROM full_market_feature_state") == {
        "count": 0
    }
