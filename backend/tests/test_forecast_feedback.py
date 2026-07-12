from __future__ import annotations

import pytest

from app.forecasting import (
    ForecastDecision,
    ForecastFeedback,
    ForecastLedger,
    ForecastOutcome,
)
from app.storage.sqlite_store import SQLiteStore


def _store(tmp_path) -> SQLiteStore:
    store = SQLiteStore(tmp_path / "forecast-feedback.sqlite3")
    store.init()
    return store


def _forecast(
    *,
    decision_id: str = "decision-a",
    subject: str = "SH600000",
    horizon_days: int = 3,
    rank: int = 1,
    score: float = 90.0,
    probability: float | None = 0.8,
    scope: str = "stock",
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
        score=score,
        probability=probability,
        model_version="selection-v3",
        prompt_version="event-thesis-v1",
        data_version="fixture-decision",
        features=features or {},
        evidence=[],
        reasons=["fixture"],
        status="pending_outcome",
    )


def _insert_bars(store: SQLiteStore, symbol: str, rows: list[tuple[str, float, float]]):
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


def test_label_due_uses_next_session_open_horizon_close_and_benchmark_proxy(tmp_path):
    store = _store(tmp_path)
    ledger = ForecastLedger(store)
    ledger.record_forecast(_forecast())
    ledger.record_forecast(
        _forecast(
            decision_id="sector-decision",
            subject="semiconductors",
            scope="sector",
        )
    )
    _insert_bars(
        store,
        "SH600000",
        [
            ("2026-07-13", 10.0, 10.5),
            ("2026-07-14", 10.6, 11.0),
            ("2026-07-15", 11.1, 12.0),
        ],
    )
    _insert_bars(
        store,
        "SH000300",
        [
            ("2026-07-13", 4000.0, 4010.0),
            ("2026-07-14", 4010.0, 4020.0),
            ("2026-07-15", 4020.0, 4040.0),
        ],
    )

    result = ForecastFeedback(store).label_due("2026-07-15T16:00:00+08:00")

    assert result["status"] == "completed"
    assert result["eligible_count"] == 1
    assert result["labelled_count"] == 1
    assert result["pending_count"] == 0
    assert result["review_only"] is True
    matured = ledger.matured("2026-07-15T16:00:00+08:00", scope="stock")
    assert len(matured) == 1
    outcome = matured[0].outcome
    assert outcome.continuous_return == pytest.approx(0.2)
    assert outcome.benchmark_return == pytest.approx(0.01)
    assert outcome.sector_return == pytest.approx(outcome.benchmark_return)
    assert outcome.evidence["entry"] == {
        "trade_date": "2026-07-13",
        "price_field": "open",
        "price": 10.0,
    }
    assert outcome.evidence["exit"] == {
        "trade_date": "2026-07-15",
        "price_field": "close",
        "price": 12.0,
    }
    assert outcome.evidence["benchmark_symbol"] == "SH000300"
    assert outcome.evidence["sector_return_source"] == "benchmark_proxy"
    assert outcome.evidence["sector_return_is_proxy"] is True
    assert (
        outcome.evidence["sector_return_semantics"]
        == "benchmark_proxy_not_observed_industry_return"
    )
    assert ledger.matured("2026-07-15T16:00:00+08:00", scope="sector") == []

    repeated = ForecastFeedback(store).label_due("2026-07-15T16:00:00+08:00")
    assert repeated["eligible_count"] == 0
    assert repeated["labelled_count"] == 0


def test_label_due_uses_real_sector_benchmark_only_when_window_is_available(tmp_path):
    store = _store(tmp_path)
    ForecastLedger(store).record_forecast(
        _forecast(features={"sector_benchmark_symbol": "SH000905"})
    )
    for symbol, rows in {
        "SH600000": [
            ("2026-07-13", 10.0, 10.5),
            ("2026-07-14", 10.5, 11.0),
            ("2026-07-15", 11.0, 11.5),
        ],
        "SH000001": [
            ("2026-07-13", 3000.0, 3010.0),
            ("2026-07-14", 3010.0, 3020.0),
            ("2026-07-15", 3020.0, 3030.0),
        ],
        "SH000905": [
            ("2026-07-13", 5000.0, 5020.0),
            ("2026-07-14", 5020.0, 5050.0),
            ("2026-07-15", 5050.0, 5100.0),
        ],
    }.items():
        _insert_bars(store, symbol, rows)

    result = ForecastFeedback(store).label_due("2026-07-15T16:00:00+08:00")

    assert result["labelled_count"] == 1
    outcome = ForecastLedger(store).matured("2026-07-15T16:00:00+08:00", scope="stock")[0].outcome
    assert outcome.benchmark_return == pytest.approx(0.01)
    assert outcome.evidence["benchmark_symbol"] == "SH000001"
    assert outcome.sector_return == pytest.approx(0.02)
    assert outcome.evidence["sector_return_source"] == "industry_benchmark"
    assert outcome.evidence["sector_return_is_proxy"] is False
    assert outcome.evidence["sector_return_semantics"] == "observed_industry_benchmark_return"
    assert outcome.evidence["sector_benchmark_symbol"] == "SH000905"


def test_label_due_leaves_incomplete_horizon_pending_without_fabricated_return(tmp_path):
    store = _store(tmp_path)
    ForecastLedger(store).record_forecast(_forecast(horizon_days=5))
    _insert_bars(
        store,
        "SH600000",
        [
            ("2026-07-13", 10.0, 10.5),
            ("2026-07-14", 10.5, 11.0),
            ("2026-07-15", 11.0, 11.5),
        ],
    )

    result = ForecastFeedback(store).label_due("2026-07-15T16:00:00+08:00")

    assert result["labelled_count"] == 0
    assert result["pending_count"] == 1
    assert result["pending"][0]["reason"] == "stock_horizon_not_matured"
    assert ForecastLedger(store).matured("2026-07-15T16:00:00+08:00") == []


def test_evaluate_groups_decisions_and_reports_ranking_probability_and_coverage(tmp_path):
    store = _store(tmp_path)
    ledger = ForecastLedger(store)
    fixtures = [
        ("decision-a", "SH600001", 1, 0.9, 0.30),
        ("decision-a", "SH600002", 2, 0.6, 0.10),
        ("decision-a", "SH600003", 3, 0.2, -0.10),
        ("decision-b", "SH600004", 1, 0.8, 0.20),
        ("decision-b", "SH600005", 2, 0.4, -0.10),
        ("decision-b", "SH600006", 3, 0.1, -0.20),
    ]
    for decision_id, subject, rank, probability, realized_return in fixtures:
        ledger.record_forecast(
            _forecast(
                decision_id=decision_id,
                subject=subject,
                horizon_days=5,
                rank=rank,
                score=100.0 - rank,
                probability=probability,
                features={
                    "probability_semantics": "benchmark_outperformance",
                    "probability_horizon_days": 5,
                },
            )
        )
        ledger.record_outcome(
            ForecastOutcome(
                decision_id=decision_id,
                scope="stock",
                subject=subject,
                horizon_days=5,
                observed_at="2026-07-20T15:00:00+08:00",
                continuous_return=realized_return,
                benchmark_return=0.0,
                sector_return=0.0,
                data_version="fixture-outcome",
                evidence={"source": "fixture"},
            )
        )

    report = ForecastFeedback(store).evaluate(
        "2026-07-21T00:00:00+08:00",
        k=2,
        min_samples=6,
        min_folds=2,
    )

    five_day = next(row for row in report["horizons"] if row["horizon_days"] == 5)
    assert report["review_only"] is True
    assert five_day["status"] == "ready"
    assert five_day["sample_count"] == 6
    assert five_day["fold_count"] == 2
    assert five_day["coverage"] == pytest.approx(1.0)
    assert five_day["precision_at_k"] == pytest.approx(0.75)
    assert five_day["spearman_rank_ic"] == pytest.approx(1.0)
    assert five_day["brier_score"] == pytest.approx(0.07)
    assert five_day["probability_sample_count"] == 6
    assert five_day["target"] == "benchmark_neutral_return>0"
    assert [fold["decision_id"] for fold in five_day["by_decision"]] == [
        "decision-a",
        "decision-b",
    ]
    one_day = next(row for row in report["horizons"] if row["horizon_days"] == 1)
    assert one_day["status"] == "insufficient_data"
    assert report["horizon_days"] == [1, 3, 5, 10, 20]


def test_evaluate_reports_insufficient_when_folds_or_samples_are_too_small(tmp_path):
    store = _store(tmp_path)
    ledger = ForecastLedger(store)
    ledger.record_forecast(_forecast(horizon_days=1))
    ledger.record_outcome(
        ForecastOutcome(
            decision_id="decision-a",
            scope="stock",
            subject="SH600000",
            horizon_days=1,
            observed_at="2026-07-13T15:00:00+08:00",
            continuous_return=0.01,
            benchmark_return=0.0,
            sector_return=0.0,
            data_version="fixture-outcome",
            evidence={"source": "fixture"},
        )
    )

    report = ForecastFeedback(store).evaluate("2026-07-14T00:00:00+08:00", k=1)
    one_day = next(row for row in report["horizons"] if row["horizon_days"] == 1)

    assert one_day["status"] == "insufficient_data"
    assert one_day["sample_count"] == 1
    assert one_day["fold_count"] == 1
    assert set(one_day["insufficient_reasons"]) == {
        "sample_count_below_20",
        "fold_count_below_3",
    }
