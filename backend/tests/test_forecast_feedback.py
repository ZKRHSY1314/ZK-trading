from __future__ import annotations

import json

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


def _confirm_all(store):
    """Register the guard claims a scheduled run would have written.

    Labelling now writes only for canonical, guard-confirmed snapshots, so a
    fixture that means "these are real decisions" has to say so the way the
    production path does.
    """

    rows = store.fetch_all(
        "SELECT scope, data_version, decision_id, "
        "       COUNT(DISTINCT subject) AS subjects, COUNT(*) AS row_count, "
        "       COUNT(DISTINCT horizon_days) AS horizons "
        "FROM forecast_decisions GROUP BY scope, data_version, decision_id"
    )
    with store.connect() as conn:
        for row in rows:
            # A guarded stock vintage must carry the full FORECAST_HORIZONS grid
            # to be confirmed. Claiming a partial-grid snapshot would make its
            # vintage guarded-but-incomplete, i.e. invisible to every canonical
            # read - so fixtures that model legacy partial data stay unclaimed
            # and are reached with include_inferred=True instead.
            if row["scope"] == "stock" and int(row["horizons"]) < 5:
                continue
            conn.execute(
                "INSERT OR REPLACE INTO forecast_decision_days "
                "(scope, data_version, decision_id, claimed_at, candidate_count, "
                " recorded_count, run_kind) VALUES (?, ?, ?, ?, ?, ?, 'scheduled')",
                (
                    row["scope"],
                    row["data_version"],
                    row["decision_id"],
                    "2026-07-10T15:00:00+08:00",
                    int(row["subjects"]),
                    int(row["row_count"]),
                ),
            )


def _confirm(store, *, decision_id, subjects, horizons=(1, 3, 5, 10, 20), scope="stock"):
    """Register the guard claim a scheduled run would have written.

    Official metrics only consider guard-confirmed snapshots, so a fixture that
    means "this is the day's real decision" has to say so the same way the
    production path does.
    """

    with store.connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO forecast_decision_days "
            "(scope, data_version, decision_id, claimed_at, candidate_count, "
            " recorded_count, run_kind) VALUES (?, ?, ?, ?, ?, ?, 'scheduled')",
            (
                scope,
                f"fixture-vintage-{decision_id}",
                decision_id,
                "2026-07-10T15:00:00+08:00",
                len(subjects),
                len(subjects) * len(horizons),
            ),
        )


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
    data_version: str | None = None,
) -> ForecastDecision:
    # Distinct decisions come from distinct bar vintages: one snapshot per
    # vintage is now an invariant, and evaluation keeps one snapshot per
    # vintage on read. Defaulting the vintage from the decision id keeps
    # fixtures that mean "two separate decision days" reading as two.
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
        data_version=data_version or f"fixture-vintage-{decision_id}",
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

    _confirm_all(store)

    _confirm_all(store)
    result = ForecastFeedback(store).label_due("2026-07-15T16:00:00+08:00", include_inferred=True)

    assert result["status"] == "completed"
    assert result["eligible_count"] == 1
    assert result["labelled_count"] == 1
    assert result["pending_count"] == 0
    assert result["review_only"] is True
    matured = ledger.matured("2026-07-15T16:00:00+08:00", scope="stock", include_inferred=True)
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
    assert ledger.matured("2026-07-15T16:00:00+08:00", scope="sector", include_inferred=True) == []

    _confirm_all(store)

    _confirm_all(store)
    repeated = ForecastFeedback(store).label_due("2026-07-15T16:00:00+08:00", include_inferred=True)
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

    _confirm_all(store)

    _confirm_all(store)
    result = ForecastFeedback(store).label_due("2026-07-15T16:00:00+08:00", include_inferred=True)

    assert result["labelled_count"] == 1
    outcome = ForecastLedger(store).matured("2026-07-15T16:00:00+08:00", scope="stock", include_inferred=True)[0].outcome
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

    _confirm_all(store)

    _confirm_all(store)
    result = ForecastFeedback(store).label_due("2026-07-15T16:00:00+08:00", include_inferred=True)

    assert result["labelled_count"] == 0
    assert result["pending_count"] == 1
    assert result["pending"][0]["reason"] == "stock_horizon_not_matured"
    assert ForecastLedger(store).matured("2026-07-15T16:00:00+08:00", include_inferred=True) == []


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
        # A real snapshot carries the whole horizon grid; only h=5 is evaluated
        # here, but a snapshot missing horizons is by definition incomplete and
        # would never be canonical.
        for horizon in (1, 3, 5, 10, 20):
            ledger.record_forecast(
                _forecast(
                    decision_id=decision_id,
                    subject=subject,
                    horizon_days=horizon,
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
    for decision_id, subjects in (
        ("decision-a", ["SH600001", "SH600002", "SH600003"]),
        ("decision-b", ["SH600004", "SH600005", "SH600006"]),
    ):
        _confirm(store, decision_id=decision_id, subjects=subjects)

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
    # The snapshot carries the full grid so it can be canonical; only h=1 has an
    # outcome, which is what makes the sample deliberately tiny.
    for horizon in (1, 3, 5, 10, 20):
        ledger.record_forecast(_forecast(horizon_days=horizon))
    _confirm(store, decision_id="decision-a", subjects=["SH600000"])
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


def test_degraded_children_propagate_to_scope_and_top_level():
    """A container is only as trustworthy as its weakest included child."""

    from app.forecasting.feedback import _roll_up_evidence, _roll_up_status

    # degraded outranks ready, which outranks insufficient_data.
    assert _roll_up_status(["ready", "degraded", "insufficient_data"]) == "degraded"
    assert _roll_up_status(["ready", "insufficient_data"]) == "ready"
    assert _roll_up_status(["insufficient_data", "insufficient_data"]) == "insufficient_data"
    # Reporting "ready" because some other horizon qualified would hide exactly
    # the thing the caller needs to see.
    assert _roll_up_status(["degraded"]) == "degraded"

    assert _roll_up_evidence(["official", "exploratory"]) == "exploratory"
    assert _roll_up_evidence(["official", "official"]) == "official"


def test_calibration_refuses_to_propose_from_exploratory_metrics(tmp_path):
    """A proposal changes behaviour, so it may only rest on official evidence."""

    from app.forecasting import ForecastCalibrationService

    store = SQLiteStore(tmp_path / "exploratory-calibration.sqlite3")
    store.init()
    evaluation = {
        "as_of": "2026-07-20T00:00:00+08:00",
        "review_only": True,
        "by_scope": {
            "stock": {
                "horizons": [
                    {
                        "horizon_days": 5,
                        "status": "degraded",
                        "evidence_quality": "exploratory",
                        "sample_count": 40,
                        "fold_count": 4,
                        "coverage": 1.0,
                        "spearman_rank_ic": 0.4,
                    }
                ]
            }
        },
    }

    result = ForecastCalibrationService(store).persist(evaluation)

    # The snapshot is still recorded as history...
    assert result["evaluation_snapshot_count"] == 1
    # ...but it must not become a recommendation.
    assert result["proposal_count"] == 0


def test_label_due_stamps_provenance_onto_the_outcomes_it_actually_writes(tmp_path):
    """End to end: label_due itself adds provenance, and it survives reload.

    Constructing the evidence by hand only proves SQLite stores what it is
    given. This drives the real labelling path with real bars, then reads the
    rows back from disk, because once persisted an exploratory outcome is
    otherwise indistinguishable from an official one.
    """

    from app.forecasting.canonical import CANONICAL_POLICY_VERSION

    store = _store(tmp_path)
    ledger = ForecastLedger(store)

    # A guard-confirmed stock snapshot: the whole FORECAST_HORIZONS grid.
    for horizon in (1, 3, 5, 10, 20):
        ledger.record_forecast(
            _forecast(decision_id="decision-confirmed", subject="SH600000",
                      horizon_days=horizon)
        )
    with store.connect() as conn:
        conn.execute(
            "INSERT INTO forecast_decision_days "
            "(scope, data_version, decision_id, claimed_at, candidate_count, "
            " recorded_count, run_kind) VALUES "
            "('stock', 'fixture-vintage-decision-confirmed', 'decision-confirmed', "
            " '2026-07-10T15:00:00+08:00', 1, 5, 'scheduled')"
        )

    # A legacy snapshot on its own vintage with no guard record at all.
    ledger.record_forecast(
        _forecast(decision_id="decision-legacy", subject="SH600001", horizon_days=3)
    )

    for symbol in ("SH600000", "SH600001"):
        _insert_bars(
            store,
            symbol,
            [("2026-07-13", 10.0, 10.5), ("2026-07-14", 10.6, 11.0),
             ("2026-07-15", 11.1, 12.0)],
        )
    _insert_bars(
        store,
        "SH000300",
        [("2026-07-13", 4000.0, 4010.0), ("2026-07-14", 4010.0, 4020.0),
         ("2026-07-15", 4020.0, 4040.0)],
    )

    result = ForecastFeedback(store).label_due(
        "2026-07-15T16:00:00+08:00", include_inferred=True
    )

    assert result["confirmed_labelled_count"] > 0
    assert result["inferred_labelled_count"] > 0
    assert result["evidence_quality"] == "exploratory"
    assert result["canonical_policy_version"] == CANONICAL_POLICY_VERSION

    written = {
        (row["decision_id"], int(row["horizon_days"])): json.loads(row["evidence_json"] or "{}")
        for row in store.fetch_all(
            "SELECT decision_id, horizon_days, evidence_json FROM forecast_outcomes"
        )
    }
    confirmed = {
        key: value for key, value in written.items() if key[0] == "decision-confirmed"
    }
    inferred = {
        key: value for key, value in written.items() if key[0] == "decision-legacy"
    }
    assert confirmed, "the guard-confirmed snapshot produced no outcome"
    assert inferred, "the legacy snapshot produced no outcome"

    for evidence in confirmed.values():
        assert evidence["canonical_selection_kind"] == "confirmed"
        assert evidence["canonical_policy_version"] == CANONICAL_POLICY_VERSION
    for evidence in inferred.values():
        assert evidence["canonical_selection_kind"] == "inferred"
        assert evidence["canonical_policy_version"] == CANONICAL_POLICY_VERSION
