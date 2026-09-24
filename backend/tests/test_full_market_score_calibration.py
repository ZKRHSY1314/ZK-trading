from __future__ import annotations

from datetime import date, timedelta
import math

from app.candidates.full_market_score_calibration import (
    FullMarketScoreCalibrationService,
)
from app.candidates.full_market_scan import FullMarketFeatureScanner
from app.config import settings
from app.data.market_history import MarketHistoryStore
from app.storage.sqlite_store import SQLiteStore


def _trading_dates(start: date, count: int) -> list[str]:
    dates: list[str] = []
    current = start
    while len(dates) < count:
        if current.weekday() < 5:
            dates.append(current.isoformat())
        current += timedelta(days=1)
    return dates


def _seed_rolling_history(
    history: MarketHistoryStore,
    *,
    single_universe_snapshot: bool = False,
) -> list[str]:
    history.initialize()
    dates = _trading_dates(date(2025, 10, 6), 150)
    fetched_at = "2026-07-16T09:00:00+08:00"
    symbols = ("SH600001", "SZ000002", "SH600003", "SZ000004")
    with history.connect() as connection:
        connection.executemany(
            """
            INSERT INTO instruments(symbol, name, exchange, provider, fetched_at)
            VALUES (?, ?, ?, 'fixture', ?)
            """,
            [(symbol, f"sample-{symbol}", symbol[:2], fetched_at) for symbol in symbols],
        )
        bars = []
        for offset, trade_date in enumerate(dates):
            closes = {
                "SH600001": 8.0 * (1.005**offset),
                "SZ000002": 10.0 + math.sin(offset / 2.0) * 0.7,
                "SH600003": 12.0 * (1.001**offset),
                "SZ000004": 9.0 + math.sin(offset / 8.0) * 0.08,
            }
            for symbol, close in closes.items():
                spread = 0.04 if symbol != "SZ000002" else 0.45
                bars.append(
                    (
                        symbol,
                        trade_date,
                        close,
                        close + spread,
                        close - spread,
                        close,
                        1_000.0,
                        close * 1_000.0,
                        fetched_at,
                        fetched_at,
                        f"{symbol}-{trade_date}",
                    )
                )
        connection.executemany(
            """
            INSERT INTO daily_bars(
                symbol, trade_date, adjustment_mode, open, high, low, close,
                volume, amount, provider, fetched_at, available_at, row_hash,
                quality_status
            ) VALUES (?, ?, 'qfq', ?, ?, ?, ?, ?, ?, 'fixture', ?, ?, ?, 'ready')
            """,
            bars,
        )
        snapshot_offsets = (129,) if single_universe_snapshot else range(60, 130)
        for snapshot_offset in snapshot_offsets:
            cursor = connection.execute(
                """
                INSERT INTO universe_snapshots(
                    universe_name, snapshot_date, provider, fetched_at,
                    member_count, source_hash, metadata_json
                ) VALUES ('a_share_full_market_cache', ?, 'fixture', ?, 4, ?, '{}')
                """,
                (
                    dates[snapshot_offset],
                    fetched_at,
                    f"snapshot-{snapshot_offset}",
                ),
            )
            snapshot_id = int(cursor.lastrowid)
            connection.executemany(
                "INSERT INTO universe_members(snapshot_id, symbol) VALUES (?, ?)",
                [(snapshot_id, symbol) for symbol in symbols],
            )
    return dates


def test_calibration_uses_purged_chronological_split_and_default_future_label(
    tmp_path,
) -> None:
    runtime = SQLiteStore(tmp_path / "runtime.sqlite3")
    runtime.init()
    history = MarketHistoryStore(tmp_path / "market-history.sqlite3")
    dates = _seed_rolling_history(history)

    result = FullMarketScoreCalibrationService(
        store=runtime,
        history_store=history,
    ).run(
        min_train_samples=40,
        min_validation_samples=10,
        min_bin_samples=5,
        sample_stride=2,
        persist=False,
    )

    assert result["status"] == "ready"
    assert result["label"] == {
        "horizon_trading_days": 20,
        "target": "future_max_close_return_pct",
        "threshold_pct": 8.0,
        "comparison": ">=",
    }
    assert result["split"]["policy"] == "chronological_holdout_with_horizon_purge"
    assert result["split"]["validation_start_date"] == dates[115]
    assert result["split"]["training_label_end_max"] < result["split"]["validation_start_date"]
    assert result["split"]["purged_training_sample_count"] > 0
    assert result["training"]["sample_count"] >= 40
    assert result["validation"]["sample_count"] >= 10
    ready_bins = [item for item in result["bins"] if item["status"] == "ready"]
    assert ready_bins
    assert all(item["probability"] is not None for item in ready_bins)
    assert all(
        item["confidence_interval_95"]["lower"]
        <= item["probability"]
        <= item["confidence_interval_95"]["upper"]
        for item in ready_bins
    )
    assert result["safety"]["execution_allowed"] is False
    assert result["safety"]["orders_generated"] is False


def test_persisted_calibration_maps_structure_score_with_auditable_evidence(
    tmp_path,
) -> None:
    runtime = SQLiteStore(tmp_path / "runtime.sqlite3")
    runtime.init()
    history = MarketHistoryStore(tmp_path / "market-history.sqlite3")
    _seed_rolling_history(history)
    service = FullMarketScoreCalibrationService(store=runtime, history_store=history)

    result = service.run(
        min_train_samples=40,
        min_validation_samples=10,
        min_bin_samples=5,
        sample_stride=2,
        persist=True,
    )
    ready_bin = next(item for item in result["bins"] if item["status"] == "ready")
    score = ready_bin["score_lower_inclusive"] + 0.5

    mapped = service.map_score(score)

    assert result["calibration_run_id"] > 0
    assert mapped == {
        "status": "ready",
        "calibration_run_id": result["calibration_run_id"],
        "structure_score": score,
        "score_semantics": "uncalibrated_structure_score",
        "probability": ready_bin["probability"],
        "probability_semantics": result["probability_semantics"],
        "sample_count": ready_bin["sample_count"],
        "success_count": ready_bin["success_count"],
        "confidence_interval_95": ready_bin["confidence_interval_95"],
        "label": result["label"],
        "validation": result["validation"],
        "safety": result["safety"],
    }


def test_persisting_identical_calibration_is_idempotent_and_latest_is_auditable(
    tmp_path,
) -> None:
    runtime = SQLiteStore(tmp_path / "runtime.sqlite3")
    runtime.init()
    history = MarketHistoryStore(tmp_path / "market-history.sqlite3")
    _seed_rolling_history(history)
    service = FullMarketScoreCalibrationService(store=runtime, history_store=history)
    parameters = {
        "min_train_samples": 40,
        "min_validation_samples": 10,
        "min_bin_samples": 5,
        "sample_stride": 2,
        "persist": True,
    }

    first = service.run(**parameters)
    second = service.run(**parameters)
    latest = service.latest()

    assert second["calibration_run_id"] == first["calibration_run_id"]
    assert second["persisted"] is False
    assert latest["status"] == first["status"]
    assert latest["calibration_run_id"] == first["calibration_run_id"]
    assert latest["persisted_at"]
    assert latest["safety"]["execution_allowed"] is False
    assert latest["safety"]["orders_generated"] is False
    assert runtime.fetch_one(
        "SELECT COUNT(*) AS count FROM full_market_score_calibration_runs"
    ) == {"count": 1}


def test_latest_full_market_candidates_attach_ready_calibration_without_relabeling_score(
    tmp_path,
) -> None:
    runtime = SQLiteStore(tmp_path / "runtime.sqlite3")
    runtime.init()
    history = MarketHistoryStore(tmp_path / "market-history.sqlite3")
    _seed_rolling_history(history)
    calibration = FullMarketScoreCalibrationService(
        store=runtime,
        history_store=history,
    ).run(
        min_train_samples=40,
        min_validation_samples=10,
        min_bin_samples=5,
        sample_stride=2,
        persist=True,
    )
    scanner = FullMarketFeatureScanner(store=runtime, history_store=history)
    scanner.run(limit=10, persist=True, force=True)

    latest = scanner.latest(limit=10)

    calibrated = [
        candidate
        for candidate in latest["candidates"]
        if candidate["calibration"]["status"] == "ready"
    ]
    assert calibrated
    candidate = calibrated[0]
    assert candidate["calibration"]["calibration_run_id"] == calibration["calibration_run_id"]
    assert candidate["calibration"]["structure_score"] == candidate["score"]
    assert candidate["calibration"]["probability"] is not None
    assert candidate["probability_semantics"] == "limited_historical_calibration"
    assert candidate["score_semantics"] == "uncalibrated_structure_score"


def test_insufficient_run_suppresses_probabilities_and_never_upgrades_mapping(
    tmp_path,
) -> None:
    runtime = SQLiteStore(tmp_path / "runtime.sqlite3")
    runtime.init()
    history = MarketHistoryStore(tmp_path / "market-history.sqlite3")
    _seed_rolling_history(history)
    service = FullMarketScoreCalibrationService(store=runtime, history_store=history)

    result = service.run(
        min_train_samples=10_000,
        min_validation_samples=10,
        min_bin_samples=5,
        sample_stride=2,
        persist=True,
    )
    mapped = service.map_score(75.0)

    assert result["status"] == "insufficient_data"
    assert all(item["probability"] is None for item in result["bins"])
    assert all(item["confidence_interval_95"] is None for item in result["bins"])
    assert result["validation"]["brier_score"] is None
    assert mapped["status"] == "insufficient_data"
    assert mapped["reason"] == "insufficient_calibration_samples"
    assert mapped["probability"] is None
    assert mapped["confidence_interval_95"] is None
    assert mapped["safety"]["execution_allowed"] is False
    assert mapped["safety"]["orders_generated"] is False


def test_live_trading_switch_blocks_fit_and_existing_probability_mapping(
    tmp_path,
    monkeypatch,
) -> None:
    runtime = SQLiteStore(tmp_path / "runtime.sqlite3")
    runtime.init()
    history = MarketHistoryStore(tmp_path / "market-history.sqlite3")
    _seed_rolling_history(history)
    service = FullMarketScoreCalibrationService(store=runtime, history_store=history)
    fitted = service.run(
        min_train_samples=40,
        min_validation_samples=10,
        min_bin_samples=5,
        sample_stride=2,
        persist=True,
    )
    ready_bin = next(item for item in fitted["bins"] if item["status"] == "ready")
    score = ready_bin["score_lower_inclusive"] + 0.5
    monkeypatch.setattr(settings, "enable_live_trading", True)

    blocked_fit = service.run(persist=True)
    blocked_mapping = service.map_score(score)
    blocked_latest = service.latest()

    assert blocked_fit["status"] == "blocked"
    assert blocked_mapping["status"] == "blocked"
    assert blocked_latest["status"] == "blocked"
    assert blocked_latest["reason"] == "live_trading_enabled"
    assert blocked_latest["safety"]["execution_allowed"] is False
    assert blocked_latest["safety"]["orders_generated"] is False
    assert blocked_mapping["reason"] == "live_trading_enabled"
    assert blocked_mapping["probability"] is None
    assert blocked_mapping["confidence_interval_95"] is None
    assert blocked_mapping["safety"]["live_trading_enabled"] is True
    assert blocked_mapping["safety"]["execution_allowed"] is False
    assert runtime.fetch_one(
        "SELECT COUNT(*) AS count FROM full_market_score_calibration_runs"
    ) == {"count": 1}


def test_single_current_universe_snapshot_builds_strided_historical_anchors(
    tmp_path,
) -> None:
    runtime = SQLiteStore(tmp_path / "runtime.sqlite3")
    runtime.init()
    history = MarketHistoryStore(tmp_path / "market-history.sqlite3")
    dates = _seed_rolling_history(history, single_universe_snapshot=True)

    result = FullMarketScoreCalibrationService(
        store=runtime,
        history_store=history,
    ).run(
        min_train_samples=20,
        min_validation_samples=4,
        min_bin_samples=2,
        sample_stride=5,
        persist=False,
    )

    assert result["status"] == "ready"
    assert result["sample_audit"]["universe_snapshot_date"] == dates[129]
    assert result["sample_audit"]["universe_snapshot_member_count"] == 4
    assert result["sample_audit"]["historical_universe_bias"] == (
        "current_universe_survivorship_limited"
    )
    assert result["sample_audit"]["historical_universe_membership_unbiased"] is False
    assert result["sample_audit"]["anchor_stride_trading_days"] == 5
    assert result["sample_audit"]["overlapping_label_windows"] is True
    assert result["sample_audit"]["sample_independence_assumed"] is False
    assert result["sample_audit"]["adjustment_revision_policy"] == ("latest_qfq_research_series")
    assert result["sufficiency"]["confidence_interval_method"] == (
        "wilson_score_95pct_nominal_not_cluster_adjusted"
    )
    assert result["sample_audit"]["labeled_sample_count"] > 40
    assert result["split"]["training_label_end_max"] < result["split"]["validation_start_date"]
