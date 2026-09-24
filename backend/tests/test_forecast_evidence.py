"""Canonical forecast evidence: small deterministic fixtures, synthetic symbols only.

Each fixture states which snapshots are real decisions the way production does
(a scheduled, finalized claim), so the tests exercise the same canonical
selector as labelling, evaluation, calibration and the scoreboard.
"""
from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path

import pytest

from app.control_plane.service import ControlPlaneService
from app.forecasting import (
    ForecastCalibrationService,
    ForecastDecision,
    ForecastFeedback,
    ForecastLedger,
    ForecastOutcome,
)
from app.forecasting.canonical import CANONICAL_POLICY_VERSION
from app.forecasting.evidence import (
    EVIDENCE_POLICY,
    ForecastEvidenceService,
    strategy_evidence_eligibility,
)
from app.storage.sqlite_store import SQLiteStore

HORIZONS = (1, 3, 5, 10, 20)


def _store(tmp_path) -> SQLiteStore:
    store = SQLiteStore(tmp_path / "evidence.sqlite3")
    store.init()
    return store


def _snapshot(store, decision_id, *, day, subjects, vintage=None, time="15:00:00",
              ranks=None, scores=None, claim="scheduled", recorded=True):
    """Record one complete snapshot (every horizon) and optionally its guard claim."""

    ledger = ForecastLedger(store)
    vintage = vintage or f"vintage-{decision_id}"
    cutoff = f"{day}T{time}+08:00"
    for index, subject in enumerate(subjects):
        for horizon in HORIZONS:
            ledger.record_forecast(ForecastDecision(
                decision_id=decision_id, scope="stock", subject=subject,
                decision_cutoff=cutoff, available_at=cutoff, horizon_days=horizon,
                rank=None if ranks is None else ranks[index],
                score=None if scores is None else scores[index],
                probability=None, model_version="synthetic", prompt_version="synthetic",
                data_version=vintage, features={}, evidence=[], reasons=["synthetic"],
                status="pending_outcome"))
    if claim is not None:
        with store.connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO forecast_decision_days (scope, data_version, decision_id, "
                "claimed_at, candidate_count, recorded_count, run_kind) VALUES ('stock', ?, ?, ?, ?, ?, ?)",
                (vintage, decision_id, cutoff, len(subjects),
                 len(subjects) * len(HORIZONS) if recorded else 0, claim))


def _outcomes(store, decision_id, horizon, returns, *, observed="2026-08-31T15:00:00+08:00"):
    ledger = ForecastLedger(store)
    for subject, value in returns.items():
        ledger.record_outcome(ForecastOutcome(
            decision_id=decision_id, scope="stock", subject=subject, horizon_days=horizon,
            observed_at=observed, continuous_return=value, benchmark_return=0.0,
            sector_return=0.0, data_version="synthetic-outcome", evidence={"source": "synthetic"}))


def _horizon(report, days, scope="stock"):
    return next(row for row in report["by_scope"][scope]["horizons"] if row["horizon_days"] == days)


SUBJECTS = ["SYN_A", "SYN_B", "SYN_C"]
AS_OF = "2026-09-01T00:00:00+08:00"


def test_snapshots_decided_on_the_same_day_are_one_independent_fold(tmp_path):
    store = _store(tmp_path)
    # Two vintages decided on 2026-08-03 with opposite rankings, one on 08-04.
    _snapshot(store, "d1-a", day="2026-08-03", subjects=SUBJECTS, ranks=[1, 2, 3])
    _snapshot(store, "d1-b", day="2026-08-03", time="15:30:00", subjects=SUBJECTS, ranks=[3, 2, 1])
    _snapshot(store, "d2", day="2026-08-04", subjects=SUBJECTS, ranks=[1, 2, 3])
    for decision_id in ("d1-a", "d1-b", "d2"):
        _outcomes(store, decision_id, 1, {"SYN_A": 0.03, "SYN_B": 0.01, "SYN_C": -0.02})

    metrics = _horizon(ForecastFeedback(store).evaluate(AS_OF, min_samples=1, min_folds=1), 1)
    assert metrics["fold_unit"] == "decision_date"
    assert metrics["canonical_snapshot_count"] == 3
    assert metrics["fold_count"] == 2
    assert metrics["repeated_snapshot_date_count"] == 1
    # Per-date mean first: 08-03 -> (1 + -1) / 2 = 0, 08-04 -> 1. Mean 0.5, not 1/3.
    assert metrics["spearman_rank_ic"] == pytest.approx(0.5)
    assert metrics["rank_ic_fold_count"] == 2
    assert [fold["decision_date"] for fold in metrics["by_decision"]] == [
        "2026-08-03", "2026-08-03", "2026-08-04"]


def test_duplicates_open_claims_and_orphans_are_excluded_and_counted(tmp_path):
    store = _store(tmp_path)
    _snapshot(store, "official", day="2026-08-03", subjects=SUBJECTS, ranks=[1, 2, 3],
              vintage="v-dup")
    # A later re-record of the same vintage: a duplicate, not a new decision.
    _snapshot(store, "rerecord", day="2026-08-03", time="15:45:00", subjects=SUBJECTS,
              ranks=[1, 2, 3], vintage="v-dup", claim=None)
    # A complete snapshot whose claim never finalized: an orphan, never canonical.
    _snapshot(store, "orphan", day="2026-08-04", subjects=SUBJECTS, ranks=[1, 2, 3],
              recorded=False)
    for decision_id in ("official", "rerecord", "orphan"):
        _outcomes(store, decision_id, 1, {"SYN_A": 0.03, "SYN_B": 0.01, "SYN_C": -0.02})

    summary = ForecastEvidenceService(store).summary(AS_OF)
    selection = summary["by_scope"]["stock"]["selection"]
    assert selection["raw_decision_id_count"] == 3
    assert selection["confirmed_snapshot_count"] == 1
    assert selection["inferred_snapshot_count"] == 0
    assert selection["non_canonical_decision_id_count"] == 2
    assert selection["claims"]["open"] == 1
    one_day = _horizon(summary, 1)
    assert one_day["canonical_snapshot_count"] == 1
    assert one_day["sample_count"] == 3  # only the official snapshot's outcomes


def test_inferred_only_evidence_is_excluded_from_official_and_never_eligible(tmp_path):
    store = _store(tmp_path)
    _snapshot(store, "legacy", day="2026-08-03", subjects=SUBJECTS, ranks=[1, 2, 3], claim=None)
    _outcomes(store, "legacy", 1, {"SYN_A": 0.03, "SYN_B": 0.01, "SYN_C": -0.02})

    official = _horizon(ForecastEvidenceService(store).summary(AS_OF), 1)
    assert official["sample_count"] == 0
    assert official["excluded_inferred_snapshot_count"] == 1
    assert "no_confirmed_snapshots" in official["insufficient_reasons"]
    assert official["strategy_evidence"]["eligible"] is False

    exploratory_summary = ForecastEvidenceService(store).summary(AS_OF, include_inferred=True)
    exploratory = _horizon(exploratory_summary, 1)
    assert exploratory["evidence_quality"] == "exploratory"
    assert exploratory["sample_count"] == 3
    assert "evidence_not_official" in exploratory["strategy_evidence"]["reasons"]
    assert exploratory_summary["strategy_evidence"]["qualified"] is False


def test_tied_predictors_and_returns_use_average_ranks_and_all_ties_are_unknown(tmp_path):
    store = _store(tmp_path)
    four = ["SYN_A", "SYN_B", "SYN_C", "SYN_D"]
    _snapshot(store, "ties", day="2026-08-03", subjects=four, scores=[3.0, 2.0, 2.0, 1.0])
    _outcomes(store, "ties", 1, {"SYN_A": 0.1, "SYN_B": 0.3, "SYN_C": -0.1, "SYN_D": -0.2})
    # Hand computation: predictor ranks [4, 2.5, 2.5, 1], return ranks [3, 4, 2, 1].
    expected = 3.0 / math.sqrt(4.5 * 5.0)
    one_day = _horizon(ForecastFeedback(store).evaluate(AS_OF, min_samples=1, min_folds=1), 1)
    assert one_day["spearman_rank_ic"] == pytest.approx(expected, abs=1e-8)

    _snapshot(store, "flat", day="2026-08-04", subjects=four, scores=[3.0, 2.0, 2.0, 1.0])
    _outcomes(store, "flat", 3, {subject: 0.05 for subject in four})
    three_day = _horizon(ForecastFeedback(store).evaluate(AS_OF, min_samples=1, min_folds=1), 3)
    # Zero variance in returns: the IC is unknown, not zero, and not averaged in.
    assert three_day["spearman_rank_ic"] is None
    assert three_day["rank_ic_fold_count"] == 0
    assert "rank_ic_unknown" in strategy_evidence_eligibility(three_day)["reasons"]


def test_partially_matured_horizons_are_pending_not_missing(tmp_path):
    store = _store(tmp_path)
    _snapshot(store, "fresh", day="2026-08-03", subjects=SUBJECTS, ranks=[1, 2, 3])
    _outcomes(store, "fresh", 1, {"SYN_A": 0.03, "SYN_B": 0.01, "SYN_C": -0.02},
              observed="2026-08-04T15:00:00+08:00")
    report = ForecastFeedback(store).evaluate("2026-08-05T09:00:00+08:00", min_samples=1, min_folds=1)
    one_day, twenty_day = _horizon(report, 1), _horizon(report, 20)
    assert (one_day["due_count"], one_day["matured_due_count"], one_day["coverage_of_due"]) == (3, 3, 1.0)
    assert twenty_day["due_count"] == 0
    assert twenty_day["pending_count"] == 3
    assert twenty_day["coverage_of_due"] is None  # nothing due is not a 0% coverage gap
    assert twenty_day["coverage"] == 0.0
    assert twenty_day["coverage_denominator"] == "all_canonical_forecasts_including_immature"
    assert "horizon_not_yet_mature" in twenty_day["insufficient_reasons"]
    assert twenty_day["maturity_basis"] == "weekday_proxy_not_exchange_calendar"


def _eligible_metrics(**overrides):
    metrics = {
        "status": "ready", "evidence_quality": "official",
        "canonical_policy_version": CANONICAL_POLICY_VERSION, "fold_unit": "decision_date",
        "fold_count": EVIDENCE_POLICY["min_independent_decision_dates"],
        "coverage_of_due": 0.9, "spearman_rank_ic": 0.08,
    }
    return {**metrics, **overrides}


@pytest.mark.parametrize("overrides,reason", [
    ({"fold_unit": None}, "independent_decision_dates_unknown"),
    ({"fold_count": 3}, "independent_decision_dates_below_20"),
    ({"coverage_of_due": None}, "no_due_forecasts"),
    ({"coverage_of_due": 0.5}, "coverage_of_due_below_0.8"),
    ({"spearman_rank_ic": None}, "rank_ic_unknown"),
    ({"spearman_rank_ic": 0.0}, "rank_ic_not_positive"),
    ({"canonical_policy_version": None}, "canonical_policy_version_not_current"),
    ({"evidence_quality": "exploratory", "status": "degraded"}, "evidence_not_official"),
])
def test_strategy_eligibility_fails_closed(overrides, reason):
    assert strategy_evidence_eligibility(_eligible_metrics())["eligible"] is True
    result = strategy_evidence_eligibility(_eligible_metrics(**overrides))
    assert result["eligible"] is False
    assert reason in result["reasons"]


def test_stored_evaluations_without_the_current_policy_are_not_current(tmp_path):
    store = _store(tmp_path)
    with store.connect() as conn:
        for evaluation_id, version, status in (("legacy-ready", None, "ready"),
                                               ("other", "canonical_snapshot.v2", "ready"),
                                               ("current", CANONICAL_POLICY_VERSION, "insufficient_data")):
            conn.execute(
                "INSERT INTO forecast_evaluations (evaluation_id, as_of, scope, horizon_days, status, "
                "sample_count, fold_count, coverage, metrics_json, canonical_policy_version, review_only) "
                "VALUES (?, '2026-09-04T00:00:00Z', 'stock', 5, ?, 0, 0, 0, '{}', ?, 1)",
                (evaluation_id, status, version))
    stored = ForecastEvidenceService(store).summary(AS_OF)["stored_evaluations"]
    qualification = {group["canonical_policy_version"]: group["qualification"] for group in stored["groups"]}
    assert qualification == {None: "legacy_unversioned", "canonical_snapshot.v2": "other_policy",
                             CANONICAL_POLICY_VERSION: "current_policy"}
    assert stored["legacy_ready_count"] == 2


def test_calibration_withholds_a_positive_statement_without_eligible_evidence():
    thin = ForecastCalibrationService._proposal(_eligible_metrics(fold_count=3, spearman_rank_ic=0.2),
                                                scope="stock")
    assert thin["action"] == "continue_monitoring"
    assert "independent_decision_dates_below_20" in thin["reason"]
    unknown_ic = ForecastCalibrationService._proposal(
        _eligible_metrics(spearman_rank_ic=None, precision_at_k=0.8), scope="stock")
    assert unknown_ic["action"] == "continue_monitoring"
    eligible = ForecastCalibrationService._proposal(_eligible_metrics(spearman_rank_ic=0.2), scope="stock")
    assert eligible["action"] == "retain_champion_validate_challenger"
    assert eligible["strategy_evidence"]["eligible"] is True
    # Nothing due yet is not a data-coverage problem; a real gap still is.
    not_due = ForecastCalibrationService._proposal(
        _eligible_metrics(coverage_of_due=None, coverage=0.0, spearman_rank_ic=None), scope="stock")
    assert not_due["action"] != "improve_data_coverage"
    gap = ForecastCalibrationService._proposal(_eligible_metrics(coverage_of_due=0.4), scope="stock")
    assert gap["action"] == "improve_data_coverage"


class _InsufficientEvidence:
    def label_due(self, *_, **__):
        return {"status": "completed", "eligible_count": 0, "labelled_count": 0, "pending_count": 0}

    def evaluate(self, *_, **__):
        return {"status": "insufficient_data", "evidence_quality": "official",
                "as_of": "2026-09-01T00:00:00Z", "review_only": True, "horizons": [], "by_scope": {}}


def test_an_evidence_shortfall_is_not_a_runtime_fault(test_db):
    service = ControlPlaneService(store=test_db, forecast_feedback_factory=_InsufficientEvidence)
    result = service._run_forecast_feedback(now=service._clock(), limit=5)
    assert result["status"] == "completed"
    assert result["evidence_status"] == "insufficient_data"
    compact = ControlPlaneService._compact_forecast_feedback(result)
    assert (compact["status"], compact["evidence_status"]) == ("completed", "insufficient_data")
    assert ControlPlaneService._normalize_status(result["status"]) == "completed"


def test_evidence_api_is_read_only_and_reports_runtime_separately(client, test_db):
    before = test_db.fetch_one("SELECT COUNT(*) AS n FROM forecast_evaluations")["n"]
    response = client.get("/api/forecast/evidence", params={"as_of": "2026-09-01T00:00:00+08:00"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "forecast_evidence.v1"
    assert payload["runtime"] == {"status": "available", "read_only": True}
    assert payload["canonical_policy_version"] == CANONICAL_POLICY_VERSION
    assert payload["live_trading_enabled"] is False
    assert set(payload["by_scope"]) == {"stock", "sector"}
    assert test_db.fetch_one("SELECT COUNT(*) AS n FROM forecast_evaluations")["n"] == before
    assert client.get("/api/forecast/evidence", params={"as_of": "2026-09-01T00:00:00"}).status_code == 422


def test_offline_report_never_writes_the_database(tmp_path):
    store = _store(tmp_path)
    _snapshot(store, "official", day="2026-08-03", subjects=SUBJECTS, ranks=[1, 2, 3])
    _outcomes(store, "official", 1, {"SYN_A": 0.03, "SYN_B": 0.01, "SYN_C": -0.02})
    before = store.db_path.read_bytes()
    script = Path(__file__).resolve().parents[1] / "scripts/forecast_evidence_report.py"
    result = subprocess.run([sys.executable, "-B", str(script), "--database", str(store.db_path),
                             "--as-of", AS_OF], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["by_scope"]["stock"]["selection"]["confirmed_snapshot_count"] == 1
    assert store.db_path.read_bytes() == before
    missing = subprocess.run([sys.executable, "-B", str(script), "--database", str(tmp_path / "absent.sqlite3")],
                             capture_output=True, text=True, timeout=60)
    assert missing.returncode == 2
    assert not (tmp_path / "absent.sqlite3").exists()
