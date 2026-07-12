from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.forecasting import ForecastDecision, ForecastFeedback, ForecastLedger, ForecastOutcome
from app.storage.sqlite_store import SQLiteStore


def _store(tmp_path) -> SQLiteStore:
    store = SQLiteStore(tmp_path / "forecast-feedback-sector.sqlite3")
    store.init()
    return store


def _forecast(
    *,
    decision_id: str = "sector-decision-a",
    subject: str = "semiconductors",
    scope: str = "sector",
    horizon_days: int = 3,
    rank: int = 1,
    probability: float | None = 0.8,
    features: dict | None = None,
) -> ForecastDecision:
    return ForecastDecision(
        decision_id=decision_id,
        scope=scope,
        subject=subject,
        decision_cutoff="2026-07-10T15:00:00+08:00",
        available_at="2026-07-10T14:59:00+08:00",
        horizon_days=horizon_days,
        rank=rank,
        score=100.0 - rank,
        probability=probability,
        model_version="sector-thesis-v1",
        prompt_version="event-thesis-v1",
        data_version="fixture-decision",
        features=features or {},
        evidence=[],
        reasons=["fixture"],
        status="pending_outcome",
    )


def _insert_memberships(store: SQLiteStore, rows: list[tuple]) -> None:
    with store.connect() as conn:
        conn.executemany(
            """
            INSERT INTO sector_membership_history(
                symbol, sector, effective_from, effective_to,
                source, available_at, confidence
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )


def _insert_bars(store: SQLiteStore, symbol: str, rows: list[tuple[str, float, float]]) -> None:
    with store.connect() as conn:
        conn.executemany(
            """
            INSERT INTO daily_bar_cache(
                symbol, trade_date, open, high, low, close, volume, amount,
                source, quality_status
            ) VALUES (?, ?, ?, ?, ?, ?, 1000, 100000, 'fixture', 'ready')
            """,
            [
                (symbol, trade_date, open_price, close_price, open_price, close_price)
                for trade_date, open_price, close_price in rows
            ],
        )


def test_sector_label_uses_only_point_in_time_members_and_equal_weight_returns(tmp_path):
    store = _store(tmp_path)
    ledger = ForecastLedger(store)
    ledger.record_forecast(_forecast())
    _insert_memberships(
        store,
        [
            (
                "SH600001",
                "semiconductors",
                "2026-01-01",
                None,
                "fixture",
                "2026-06-01T00:00:00+00:00",
                0.9,
            ),
            (
                "SZ000002",
                "semiconductors",
                "2026-02-01",
                None,
                "fixture",
                "2026-06-02T00:00:00+00:00",
                0.8,
            ),
            # Effective on decision day, but not known until after the cutoff.
            (
                "SH600003",
                "semiconductors",
                "2026-01-01",
                None,
                "fixture",
                "2026-07-10T08:00:00+00:00",
                1.0,
            ),
            # Known in advance, but not effective on the decision date.
            (
                "SH600004",
                "semiconductors",
                "2026-07-11",
                None,
                "fixture",
                "2026-07-09T00:00:00+00:00",
                1.0,
            ),
            # Historical membership already expired before the decision date.
            (
                "SH600005",
                "semiconductors",
                "2026-01-01",
                "2026-07-09",
                "fixture",
                "2026-06-01T00:00:00+00:00",
                1.0,
            ),
        ],
    )
    for symbol, closes in {
        "SH600001": (10.0, 12.0),
        "SZ000002": (20.0, 22.0),
        # These large returns must not leak into the point-in-time basket.
        "SH600003": (10.0, 20.0),
        "SH600004": (10.0, 20.0),
        "SH600005": (10.0, 20.0),
    }.items():
        _insert_bars(
            store,
            symbol,
            [
                ("2026-07-13", closes[0], closes[0]),
                ("2026-07-14", closes[0], closes[0]),
                ("2026-07-15", closes[0], closes[1]),
            ],
        )
    _insert_bars(
        store,
        "SH000300",
        [
            ("2026-07-13", 4000.0, 4005.0),
            ("2026-07-14", 4005.0, 4020.0),
            ("2026-07-15", 4020.0, 4040.0),
        ],
    )

    result = ForecastFeedback(store).label_due("2026-07-15T16:00:00+08:00")

    assert result["eligible_count"] == 0  # Legacy stock-only counter remains compatible.
    assert result["total_eligible_count"] == 1
    assert result["by_scope"]["sector"]["labelled_count"] == 1
    matured = ledger.matured("2026-07-15T16:00:00+08:00", scope="sector")
    assert len(matured) == 1
    outcome = matured[0].outcome
    assert outcome.continuous_return == pytest.approx(0.15)
    assert outcome.benchmark_return == pytest.approx(0.01)
    assert outcome.sector_return == pytest.approx(0.15)
    assert outcome.evidence["aggregation"] == "equal_weight_complete_members"
    assert outcome.evidence["benchmark_aggregation"] == "equal_weight_member_aligned_windows"
    assert outcome.evidence["membership_source"] == "sector_membership_history"
    assert outcome.evidence["eligible_member_count"] == 2
    assert outcome.evidence["complete_member_count"] == 2
    assert outcome.evidence["coverage"] == pytest.approx(1.0)
    assert outcome.evidence["benchmark_symbol"] == "SH000300"
    assert [row["symbol"] for row in outcome.evidence["members"]] == [
        "SH600001",
        "SZ000002",
    ]
    assert outcome.evidence["members"][0]["benchmark_entry"]["trade_date"] == "2026-07-13"
    assert outcome.evidence["members"][0]["benchmark_exit"]["trade_date"] == "2026-07-15"


def test_sector_label_stays_pending_until_two_members_have_complete_windows(tmp_path):
    store = _store(tmp_path)
    ledger = ForecastLedger(store)
    ledger.record_forecast(_forecast(horizon_days=3))
    _insert_memberships(
        store,
        [
            (
                "SH600001",
                "semiconductors",
                "2026-01-01",
                None,
                "fixture",
                "2026-06-01T00:00:00+00:00",
                1.0,
            ),
            (
                "SZ000002",
                "semiconductors",
                "2026-01-01",
                None,
                "fixture",
                "2026-06-01T00:00:00+00:00",
                1.0,
            ),
        ],
    )
    _insert_bars(
        store,
        "SH600001",
        [
            ("2026-07-13", 10.0, 10.1),
            ("2026-07-14", 10.1, 10.2),
            ("2026-07-15", 10.2, 10.3),
        ],
    )
    _insert_bars(
        store,
        "SZ000002",
        [
            ("2026-07-13", 20.0, 20.1),
            ("2026-07-14", 20.1, 20.2),
        ],
    )
    _insert_bars(
        store,
        "SH000300",
        [
            ("2026-07-13", 4000.0, 4005.0),
            ("2026-07-14", 4005.0, 4010.0),
            ("2026-07-15", 4010.0, 4020.0),
        ],
    )

    result = ForecastFeedback(store).label_due("2026-07-15T16:00:00+08:00")

    sector = result["by_scope"]["sector"]
    assert sector["eligible_count"] == 1
    assert sector["labelled_count"] == 0
    assert sector["pending_count"] == 1
    assert sector["pending"][0]["reason"] == "sector_complete_members_below_2"
    assert ledger.matured("2026-07-15T16:00:00+08:00", scope="sector") == []


def test_sector_label_uses_each_members_own_next_trading_sessions(tmp_path):
    store = _store(tmp_path)
    ledger = ForecastLedger(store)
    ledger.record_forecast(_forecast(horizon_days=3))
    _insert_memberships(
        store,
        [
            (
                symbol,
                "semiconductors",
                "2026-01-01",
                None,
                "fixture",
                "2026-06-01T00:00:00+00:00",
                1.0,
            )
            for symbol in ("SH600001", "SZ000002")
        ],
    )
    _insert_bars(
        store,
        "SH600001",
        [
            ("2026-07-13", 10.0, 10.1),
            ("2026-07-14", 10.1, 10.5),
            ("2026-07-15", 10.5, 11.0),
        ],
    )
    # This member did not trade on July 13, so its own three-session window
    # begins on July 14 and ends on July 16.
    _insert_bars(
        store,
        "SZ000002",
        [
            ("2026-07-14", 20.0, 21.0),
            ("2026-07-15", 21.0, 22.0),
            ("2026-07-16", 22.0, 24.0),
        ],
    )
    _insert_bars(
        store,
        "SH000300",
        [
            ("2026-07-13", 4000.0, 4005.0),
            ("2026-07-14", 4010.0, 4020.0),
            ("2026-07-15", 4020.0, 4040.0),
            ("2026-07-16", 4040.0, 4050.0),
        ],
    )

    result = ForecastFeedback(store).label_due("2026-07-16T16:00:00+08:00")

    assert result["by_scope"]["sector"]["labelled_count"] == 1
    outcome = ledger.matured("2026-07-16T16:00:00+08:00", scope="sector")[0].outcome
    assert outcome.continuous_return == pytest.approx(0.15)
    expected_benchmark = ((4040.0 / 4000.0 - 1.0) + (4050.0 / 4010.0 - 1.0)) / 2
    assert outcome.benchmark_return == pytest.approx(expected_benchmark)
    members = {row["symbol"]: row for row in outcome.evidence["members"]}
    assert members["SH600001"]["entry"]["trade_date"] == "2026-07-13"
    assert members["SH600001"]["exit"]["trade_date"] == "2026-07-15"
    assert members["SZ000002"]["entry"]["trade_date"] == "2026-07-14"
    assert members["SZ000002"]["exit"]["trade_date"] == "2026-07-16"
    assert members["SZ000002"]["benchmark_entry"]["trade_date"] == "2026-07-14"
    assert members["SZ000002"]["benchmark_exit"]["trade_date"] == "2026-07-16"


def test_sector_label_requires_five_members_and_sixty_percent_coverage(tmp_path):
    store = _store(tmp_path)
    ledger = ForecastLedger(store)
    ledger.record_forecast(_forecast(horizon_days=1))
    symbols = [f"SH6000{index:02d}" for index in range(10)]
    _insert_memberships(
        store,
        [
            (
                symbol,
                "semiconductors",
                "2026-01-01",
                None,
                "fixture",
                "2026-06-01T00:00:00+00:00",
                1.0,
            )
            for symbol in symbols
        ],
    )
    for symbol in symbols[:5]:
        _insert_bars(store, symbol, [("2026-07-13", 10.0, 10.5)])
    _insert_bars(store, "SH000300", [("2026-07-13", 4000.0, 4010.0)])

    result = ForecastFeedback(store).label_due("2026-07-13T16:00:00+08:00")

    sector = result["by_scope"]["sector"]
    assert sector["labelled_count"] == 0
    assert sector["pending_count"] == 1
    pending = sector["pending"][0]
    assert pending["reason"] == "sector_member_coverage_below_threshold"
    assert pending["eligible_member_count"] == 10
    assert pending["complete_member_count"] == 5
    assert pending["required_complete_member_count"] == 5
    assert pending["coverage"] == pytest.approx(0.5)
    assert pending["minimum_coverage"] == pytest.approx(0.6)
    assert ledger.matured("2026-07-13T16:00:00+08:00", scope="sector") == []

    _insert_bars(store, symbols[5], [("2026-07-13", 10.0, 10.5)])
    matured_result = ForecastFeedback(store).label_due("2026-07-13T16:00:00+08:00")
    assert matured_result["by_scope"]["sector"]["labelled_count"] == 1
    outcome = ledger.matured("2026-07-13T16:00:00+08:00", scope="sector")[0].outcome
    assert outcome.evidence["complete_member_count"] == 6
    assert outcome.evidence["minimum_complete_members"] == 5
    assert outcome.evidence["coverage"] == pytest.approx(0.6)
    assert outcome.evidence["minimum_coverage"] == pytest.approx(0.6)


def test_evaluate_reports_stock_and_sector_metrics_separately(tmp_path):
    store = _store(tmp_path)
    ledger = ForecastLedger(store)
    sector_fixtures = [
        ("mixed_theme", 1, 0.95, "mixed", 0.50, 0.00),
        ("semiconductors", 2, 0.8, "positive", 0.20, 0.05),
        ("oil_gas", 3, 0.7, "negative", -0.10, 0.00),
    ]
    for (
        subject,
        rank,
        probability,
        direction,
        realized_return,
        benchmark_return,
    ) in sector_fixtures:
        ledger.record_forecast(
            _forecast(
                decision_id="sector-decision-a",
                subject=subject,
                horizon_days=5,
                rank=rank,
                probability=probability,
                features={
                    "direction": direction,
                    "probability_semantics": (
                        "directional_thesis_success"
                        if direction in {"positive", "negative"}
                        else "non_directional_thesis_confidence"
                    ),
                    "probability_horizon_days": 5,
                },
            )
        )
        ledger.record_outcome(
            ForecastOutcome(
                decision_id="sector-decision-a",
                scope="sector",
                subject=subject,
                horizon_days=5,
                observed_at="2026-07-20T15:00:00+08:00",
                continuous_return=realized_return,
                benchmark_return=benchmark_return,
                sector_return=realized_return,
                data_version="fixture-sector-outcome",
                evidence={"source": "fixture"},
            )
        )
    ledger.record_forecast(
        _forecast(
            decision_id="stock-decision-a",
            subject="SH600000",
            scope="stock",
            horizon_days=5,
            probability=0.7,
        )
    )
    ledger.record_outcome(
        ForecastOutcome(
            decision_id="stock-decision-a",
            scope="stock",
            subject="SH600000",
            horizon_days=5,
            observed_at="2026-07-20T15:00:00+08:00",
            continuous_return=0.10,
            benchmark_return=0.01,
            sector_return=0.02,
            data_version="fixture-stock-outcome",
            evidence={"source": "fixture"},
        )
    )

    report = ForecastFeedback(store).evaluate(
        "2026-07-21T00:00:00+08:00",
        k=1,
        min_samples=2,
        min_folds=1,
    )

    stock_five_day = next(
        row for row in report["by_scope"]["stock"]["horizons"] if row["horizon_days"] == 5
    )
    sector_five_day = next(
        row for row in report["by_scope"]["sector"]["horizons"] if row["horizon_days"] == 5
    )
    assert report["horizons"] == report["by_scope"]["stock"]["horizons"]
    assert stock_five_day["sample_count"] == 1
    assert stock_five_day["status"] == "insufficient_data"
    assert stock_five_day["probability_sample_count"] == 0
    assert stock_five_day["uncalibrated_probability_count"] == 1
    assert stock_five_day["probability_calibration_status"] == "uncalibrated"
    assert sector_five_day["status"] == "ready"
    assert sector_five_day["forecast_count"] == 3
    assert sector_five_day["sample_count"] == 3
    assert sector_five_day["coverage"] == pytest.approx(1.0)
    assert sector_five_day["directional_sample_count"] == 2
    assert sector_five_day["directional_coverage"] == pytest.approx(1.0)
    assert sector_five_day["precision_at_k"] == pytest.approx(1.0)
    assert sector_five_day["spearman_rank_ic"] == pytest.approx(1.0)
    assert sector_five_day["brier_score"] == pytest.approx(0.065)
    assert (
        sector_five_day["target"]
        == "direction_signed_benchmark_neutral_return>0"
    )


def test_sector_backlog_does_not_consume_the_legacy_stock_label_limit(tmp_path):
    store = _store(tmp_path)
    ledger = ForecastLedger(store)
    ledger.record_forecast(
        _forecast(
            decision_id="a-sector-decision",
            subject="semiconductors",
            horizon_days=1,
        )
    )
    ledger.record_forecast(
        _forecast(
            decision_id="z-stock-decision",
            subject="SH600000",
            scope="stock",
            horizon_days=1,
        )
    )
    _insert_bars(store, "SH600000", [("2026-07-13", 10.0, 10.5)])
    _insert_bars(store, "SH000300", [("2026-07-13", 4000.0, 4010.0)])

    result = ForecastFeedback(store).label_due(
        "2026-07-13T16:00:00+08:00",
        limit=1,
    )

    assert result["eligible_count"] == 1
    assert result["labelled_count"] == 1
    assert result["by_scope"]["sector"]["eligible_count"] == 1


def test_unready_old_forecast_does_not_starve_later_mature_forecast(tmp_path):
    store = _store(tmp_path)
    ledger = ForecastLedger(store)
    ledger.record_forecast(
        _forecast(
            decision_id="a-old-unready",
            subject="SH600001",
            scope="stock",
            horizon_days=1,
        )
    )
    ledger.record_forecast(
        _forecast(
            decision_id="b-later-ready",
            subject="SH600002",
            scope="stock",
            horizon_days=1,
        )
    )
    _insert_bars(store, "SH600002", [("2026-07-13", 10.0, 10.5)])
    _insert_bars(store, "SH000300", [("2026-07-13", 4000.0, 4010.0)])

    result = ForecastFeedback(store).label_due(
        "2026-07-13T16:00:00+08:00",
        limit=1,
    )

    assert result["eligible_count"] == 1
    assert result["labelled_count"] == 1
    assert result["pending_count"] == 0
    assert result["labelled"][0]["decision_id"] == "b-later-ready"
    matured = ledger.matured("2026-07-13T16:00:00+08:00", scope="stock")
    assert [row.forecast.decision_id for row in matured] == ["b-later-ready"]


def test_label_scan_rotates_so_large_pending_backlog_cannot_starve_forever(tmp_path):
    store = _store(tmp_path)
    ledger = ForecastLedger(store)
    first_as_of = datetime.fromisoformat("2026-07-13T16:00:00+08:00")
    backlog_count = 101
    scan_limit = 100
    first_offset = (int(first_as_of.timestamp() // 300) * scan_limit) % backlog_count
    excluded_index = (first_offset - 1) % backlog_count
    ready_symbol = None
    for index in range(backlog_count):
        symbol = f"SH60{index:04d}"
        ledger.record_forecast(
            _forecast(
                decision_id=f"rotation-{index:03d}",
                subject=symbol,
                scope="stock",
                horizon_days=1,
            )
        )
        if index == excluded_index:
            ready_symbol = symbol
    assert ready_symbol is not None
    _insert_bars(store, ready_symbol, [("2026-07-13", 10.0, 10.5)])
    _insert_bars(store, "SH000300", [("2026-07-13", 4000.0, 4010.0)])

    first = ForecastFeedback(store).label_due(first_as_of, limit=1)
    second = ForecastFeedback(store).label_due(first_as_of + timedelta(minutes=5), limit=1)

    assert first["labelled_count"] == 0
    assert first["by_scope"]["stock"]["backlog_count"] == backlog_count
    assert second["labelled_count"] == 1
    assert second["labelled"][0]["subject"] == ready_symbol


def test_evaluate_is_not_ready_when_every_metric_is_unavailable(tmp_path):
    store = _store(tmp_path)
    ledger = ForecastLedger(store)
    for rank, symbol in enumerate(("SH600001", "SH600002"), start=1):
        ledger.record_forecast(
            _forecast(
                decision_id="stock-flat-decision",
                subject=symbol,
                scope="stock",
                horizon_days=1,
                rank=rank,
                probability=0.8,
            )
        )
        ledger.record_outcome(
            ForecastOutcome(
                decision_id="stock-flat-decision",
                scope="stock",
                subject=symbol,
                horizon_days=1,
                observed_at="2026-07-13T15:00:00+08:00",
                continuous_return=0.10,
                benchmark_return=0.0,
                sector_return=0.0,
                data_version="fixture-flat-outcome",
                evidence={"source": "fixture"},
            )
        )

    report = ForecastFeedback(store).evaluate(
        "2026-07-14T00:00:00+08:00",
        k=3,
        min_samples=2,
        min_folds=1,
    )

    one_day = next(row for row in report["horizons"] if row["horizon_days"] == 1)
    assert one_day["precision_at_k"] is None
    assert one_day["spearman_rank_ic"] is None
    assert one_day["brier_score"] is None
    assert one_day["status"] == "insufficient_data"
    assert "no_available_evaluation_metric" in one_day["insufficient_reasons"]
