from __future__ import annotations

import json

from app.config import settings
from app.forecasting import ForecastCalibrationService
from app.forecasting.canonical import CANONICAL_POLICY_VERSION
from app.storage.sqlite_store import SQLiteStore


def _evaluation() -> dict:
    return {
        "as_of": "2026-07-20T08:00:00Z",
        "review_only": True,
        "by_scope": {
            "stock": {
                "status": "ready",
                "horizons": [
                    {
                        "scope": "stock",
                        "horizon_days": 5,
                        "status": "ready",
                        # A real evaluation states its provenance; proposals are
                        # refused without it.
                        "evidence_quality": "official",
                        "canonical_policy_version": CANONICAL_POLICY_VERSION,
                        "sample_count": 60,
                        "fold_count": 5,
                        "coverage": 0.9,
                        "precision_at_k": 0.4,
                        "spearman_rank_ic": -0.12,
                        "brier_score": None,
                        "probability_calibration_status": "uncalibrated",
                        "review_only": True,
                    }
                ],
            },
            "sector": {
                "status": "insufficient_data",
                "horizons": [
                    {
                        "scope": "sector",
                        "horizon_days": 5,
                        "status": "insufficient_data",
                        "sample_count": 3,
                        "fold_count": 1,
                        "coverage": 0.5,
                        "directional_coverage": 0.5,
                        "precision_at_k": None,
                        "spearman_rank_ic": None,
                        "brier_score": None,
                        "review_only": True,
                    }
                ],
            },
        },
    }


def test_persist_records_deduplicated_evaluations_and_review_only_challenger(tmp_path):
    store = SQLiteStore(tmp_path / "forecast-calibration.sqlite3")
    service = ForecastCalibrationService(store)

    first = service.persist(_evaluation(), created_by="pytest")
    repeated = service.persist(_evaluation(), created_by="pytest-repeat")

    assert first["status"] == "completed"
    assert first["evaluation_snapshot_count"] == 2
    assert first["new_evaluation_snapshot_count"] == 2
    assert first["proposal_count"] == 1
    assert repeated["new_evaluation_snapshot_count"] == 0
    assert store.fetch_one("SELECT COUNT(*) AS count FROM forecast_evaluations")["count"] == 2
    proposals = store.fetch_all(
        "SELECT * FROM agent_calibration_proposals WHERE proposal_type = 'forecast_calibration'"
    )
    assert len(proposals) == 1
    assert proposals[0]["target"] == "stock:5d"
    assert proposals[0]["status"] == "pending"
    proposal = json.loads(proposals[0]["proposal_json"])
    evidence = json.loads(proposals[0]["evidence_json"])
    assert proposal["action"] == "train_challenger_reduce_review_priority"
    assert proposal["apply_automatically"] is False
    assert evidence["evaluation_id"].startswith("forecast-eval-")
    assert proposals[0]["created_by"] == "pytest-repeat"


def test_persist_refuses_to_write_when_live_trading_is_enabled(monkeypatch, tmp_path):
    store = SQLiteStore(tmp_path / "forecast-calibration-blocked.sqlite3")
    service = ForecastCalibrationService(store)
    monkeypatch.setattr(settings, "enable_live_trading", True)

    result = service.persist(_evaluation())

    assert result["status"] == "blocked"
    assert result["proposal_count"] == 0
    assert store.fetch_one("SELECT COUNT(*) AS count FROM forecast_evaluations")["count"] == 0


def test_the_canonical_policy_version_is_part_of_the_evaluation_identity(tmp_path):
    """Identical metrics under two policies must not collapse into one row.

    evaluation_id is a hash of the payload and the insert is INSERT OR IGNORE,
    so if the policy were only a column the second policy's result would be
    silently dropped and the surviving row would carry the wrong provenance.
    """

    store = SQLiteStore(tmp_path / "calibration-identity.sqlite3")
    store.init()
    evaluation = {
        "as_of": "2026-07-20T00:00:00+08:00",
        "review_only": True,
        "by_scope": {
            "stock": {
                "horizons": [
                    {
                        "horizon_days": 5,
                        "status": "ready",
                        "evidence_quality": "official",
                        "canonical_policy_version": CANONICAL_POLICY_VERSION,
                        "sample_count": 40,
                        "fold_count": 4,
                        "coverage": 1.0,
                        "precision_at_k": 0.5,
                        "spearman_rank_ic": 0.11,
                        "brier_score": 0.2,
                    }
                ]
            }
        },
    }

    first = ForecastCalibrationService(store).persist(evaluation)
    assert first["new_evaluation_snapshot_count"] == 1

    # Same numbers, different policy: a distinct record, not a silent no-op.
    # The version travels with the metrics, so that is what varies here.
    other = json.loads(json.dumps(evaluation))
    other["by_scope"]["stock"]["horizons"][0]["canonical_policy_version"] = (
        "canonical_snapshot.v99"
    )
    second = ForecastCalibrationService(store).persist(other)
    assert second["new_evaluation_snapshot_count"] == 1

    with store.connect() as conn:
        versions = sorted(
            row[0]
            for row in conn.execute(
                "SELECT canonical_policy_version FROM forecast_evaluations"
            )
        )
    # Read from the constant so a policy bump does not silently break this.
    assert versions == sorted([CANONICAL_POLICY_VERSION, "canonical_snapshot.v99"])


def _official_metrics(**overrides) -> dict:
    metrics = {
        "horizon_days": 5,
        "status": "ready",
        "evidence_quality": "official",
        "canonical_policy_version": CANONICAL_POLICY_VERSION,
        "sample_count": 40,
        "fold_count": 4,
        "coverage": 1.0,
        "spearman_rank_ic": 0.3,
    }
    metrics.update(overrides)
    return metrics


def _wrap(metrics: dict) -> dict:
    return {
        "as_of": "2026-07-20T00:00:00+08:00",
        "review_only": True,
        "by_scope": {"stock": {"horizons": [metrics]}},
    }


def test_metrics_without_provenance_cannot_produce_a_proposal(tmp_path):
    """An absent field is not a statement of quality.

    Defaulting evidence_quality to "official" let metrics that simply omitted
    the field - a caller predating provenance, or one that dropped it - become a
    recommendation to change behaviour.
    """

    store = SQLiteStore(tmp_path / "no-provenance.sqlite3")
    store.init()
    metrics = _official_metrics()
    del metrics["evidence_quality"]
    del metrics["canonical_policy_version"]

    result = ForecastCalibrationService(store).persist(_wrap(metrics))

    # Recorded as history...
    assert result["evaluation_snapshot_count"] == 1
    # ...but never promoted to a proposal.
    assert result["proposal_count"] == 0


def test_metrics_without_provenance_are_not_relabelled_as_current_policy(tmp_path):
    """Stamping the running policy onto unattributable metrics destroys the fact.

    The stored version must be what the metrics carried, so "we do not know" is
    preserved as NULL instead of being rewritten into a confident claim.
    """

    store = SQLiteStore(tmp_path / "null-provenance.sqlite3")
    store.init()
    metrics = _official_metrics()
    del metrics["canonical_policy_version"]

    ForecastCalibrationService(store).persist(_wrap(metrics))

    stored = store.fetch_all(
        "SELECT canonical_policy_version FROM forecast_evaluations"
    )
    assert [row["canonical_policy_version"] for row in stored] == [None]


def test_a_mismatched_policy_version_cannot_produce_a_proposal(tmp_path):
    """Metrics computed under another canonical policy describe another sample."""

    store = SQLiteStore(tmp_path / "mismatched-provenance.sqlite3")
    store.init()

    result = ForecastCalibrationService(store).persist(
        _wrap(_official_metrics(canonical_policy_version="canonical_snapshot.v1"))
    )

    assert result["evaluation_snapshot_count"] == 1
    assert result["proposal_count"] == 0
    # The supplied version is preserved verbatim, not overwritten.
    stored = store.fetch_all("SELECT canonical_policy_version FROM forecast_evaluations")
    assert [row["canonical_policy_version"] for row in stored] == ["canonical_snapshot.v1"]


def test_exploratory_evidence_cannot_produce_a_proposal_even_with_a_matching_version(tmp_path):
    store = SQLiteStore(tmp_path / "exploratory-provenance.sqlite3")
    store.init()

    result = ForecastCalibrationService(store).persist(
        _wrap(_official_metrics(status="degraded", evidence_quality="exploratory"))
    )

    assert result["proposal_count"] == 0


def test_fully_attributed_official_metrics_still_produce_a_proposal(tmp_path):
    """The gate must not be so strict that nothing legitimate passes."""

    store = SQLiteStore(tmp_path / "official-provenance.sqlite3")
    store.init()

    result = ForecastCalibrationService(store).persist(_wrap(_official_metrics()))

    assert result["proposal_count"] == 1
    stored = store.fetch_all("SELECT canonical_policy_version FROM forecast_evaluations")
    assert [row["canonical_policy_version"] for row in stored] == [CANONICAL_POLICY_VERSION]
