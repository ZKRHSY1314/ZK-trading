from __future__ import annotations

import json

from app.config import settings
from app.forecasting import ForecastCalibrationService
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
