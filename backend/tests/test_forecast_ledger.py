from __future__ import annotations

import pytest

from app.forecasting import (
    ForecastConflictError,
    ForecastDecision,
    ForecastLedger,
    ForecastOutcome,
)
from app.storage.sqlite_store import SQLiteStore


def _ledger(tmp_path) -> ForecastLedger:
    store = SQLiteStore(tmp_path / "forecast-ledger.sqlite3")
    store.init()
    return ForecastLedger(store)


def _forecast(**overrides) -> ForecastDecision:
    values = {
        "decision_id": "decision-20260711-0900",
        "scope": "stock",
        "subject": "SH600000",
        "decision_cutoff": "2026-07-11T09:00:00+08:00",
        "available_at": "2026-07-11T08:59:00+08:00",
        "horizon_days": 5,
        "rank": 1,
        "score": 82.5,
        "probability": 0.71,
        "model_version": "selection-v3",
        "prompt_version": "event-thesis-v1",
        "data_version": "a-share-eod-20260710",
        "features": {"relative_strength_20d": 0.18},
        "evidence": [{"source": "fixture", "available_at": "2026-07-11T08:58:00+08:00"}],
        "reasons": ["sector_tailwind", "volume_contraction"],
        "status": "pending_outcome",
    }
    values.update(overrides)
    if "evidence" not in overrides:
        values["evidence"][0]["available_at"] = values["available_at"]
    return ForecastDecision(**values)


def test_forecast_is_persisted_as_a_review_only_latest_snapshot(tmp_path):
    ledger = _ledger(tmp_path)

    recorded = ledger.record_forecast(_forecast())
    latest = ledger.latest(scope="stock")

    assert recorded.review_only is True
    assert latest == [recorded]
    assert latest[0].features == {"relative_strength_20d": 0.18}
    assert latest[0].evidence[0]["source"] == "fixture"


def test_repeated_forecast_is_idempotent_but_changed_payload_cannot_mutate_history(tmp_path):
    ledger = _ledger(tmp_path)
    forecast = _forecast()

    first = ledger.record_forecast(forecast)
    repeated = ledger.record_forecast(forecast)

    assert repeated == first
    assert ledger.latest(scope="stock") == [first]
    with pytest.raises(ForecastConflictError, match="immutable"):
        ledger.record_forecast(_forecast(score=91.0))


def test_as_of_returns_the_latest_complete_snapshot_visible_at_the_cutoff(tmp_path):
    ledger = _ledger(tmp_path)
    for forecast in [
        _forecast(
            decision_id="decision-0830",
            decision_cutoff="2026-07-11T08:30:00+08:00",
            available_at="2026-07-11T08:29:00+08:00",
            subject="SH600001",
        ),
        _forecast(
            decision_id="decision-1000",
            decision_cutoff="2026-07-11T10:00:00+08:00",
            available_at="2026-07-11T09:59:00+08:00",
            subject="SH600010",
            rank=1,
        ),
        _forecast(
            decision_id="decision-1000",
            decision_cutoff="2026-07-11T10:00:00+08:00",
            available_at="2026-07-11T09:58:00+08:00",
            subject="SZ000002",
            rank=2,
        ),
        _forecast(
            decision_id="decision-1100",
            decision_cutoff="2026-07-11T11:00:00+08:00",
            available_at="2026-07-11T10:59:00+08:00",
            subject="SH600011",
        ),
    ]:
        ledger.record_forecast(forecast)

    visible = ledger.as_of(
        "2026-07-11T10:30:00+08:00", scope="stock", horizon_days=5
    )

    assert [item.decision_id for item in visible] == ["decision-1000", "decision-1000"]
    assert [item.subject for item in visible] == ["SH600010", "SZ000002"]
    assert [item.subject for item in ledger.latest(scope="stock")] == ["SH600011"]


def test_matured_returns_store_continuous_benchmark_and_sector_neutral_outcomes(tmp_path):
    ledger = _ledger(tmp_path)
    for horizon in (1, 3, 5, 10, 20):
        ledger.record_forecast(_forecast(horizon_days=horizon))
        ledger.record_outcome(
            ForecastOutcome(
                decision_id="decision-20260711-0900",
                scope="stock",
                subject="SH600000",
                horizon_days=horizon,
                observed_at="2026-08-10T15:00:00+08:00",
                continuous_return=0.01 * horizon,
                benchmark_return=0.002 * horizon,
                sector_return=0.004 * horizon,
                data_version=f"outcome-eod-{horizon}",
                evidence={"price_source": "fixture"},
            )
        )

    matured = ledger.matured("2026-08-11T00:00:00+08:00", scope="stock")

    assert [item.outcome.horizon_days for item in matured] == [1, 3, 5, 10, 20]
    five_day = next(item.outcome for item in matured if item.outcome.horizon_days == 5)
    assert five_day.continuous_return == pytest.approx(0.05)
    assert five_day.benchmark_neutral_return == pytest.approx(0.04)
    assert five_day.sector_neutral_return == pytest.approx(0.03)
    assert five_day.status == "matured"


def test_forecast_rejects_evidence_that_was_not_available_at_decision_time():
    with pytest.raises(ValueError, match="evidence available_at"):
        _forecast(
            evidence=[
                {
                    "source": "future-news",
                    "available_at": "2026-07-11T09:01:00+08:00",
                }
            ]
        )


def test_outcome_write_is_idempotent_and_cannot_be_relabelled(tmp_path):
    ledger = _ledger(tmp_path)
    ledger.record_forecast(_forecast())
    outcome = ForecastOutcome(
        decision_id="decision-20260711-0900",
        scope="stock",
        subject="SH600000",
        horizon_days=5,
        observed_at="2026-07-18T15:00:00+08:00",
        continuous_return=0.08,
        benchmark_return=0.02,
        sector_return=0.03,
        data_version="outcome-eod-20260718",
        evidence={"price_source": "fixture"},
    )

    first = ledger.record_outcome(outcome)
    repeated = ledger.record_outcome(outcome)

    assert repeated == first
    assert ledger.matured("2026-07-18T14:59:00+08:00") == []
    assert len(ledger.matured("2026-07-18T15:00:00+08:00")) == 1
    with pytest.raises(ForecastConflictError, match="immutable"):
        ledger.record_outcome(
            ForecastOutcome(
                decision_id=outcome.decision_id,
                scope=outcome.scope,
                subject=outcome.subject,
                horizon_days=outcome.horizon_days,
                observed_at=outcome.observed_at,
                continuous_return=0.09,
                benchmark_return=outcome.benchmark_return,
                sector_return=outcome.sector_return,
                data_version=outcome.data_version,
                evidence=outcome.evidence,
            )
        )


def test_non_review_only_forecast_is_rejected():
    with pytest.raises(ValueError, match="review-only"):
        _forecast(review_only=False)
