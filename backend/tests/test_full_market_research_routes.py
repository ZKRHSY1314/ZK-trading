from __future__ import annotations

from app.api import full_market_research_routes


class FakeCalibrationService:
    calls: list[dict] = []

    def __init__(self, *, store, history_store) -> None:
        self.store = store
        self.history_store = history_store

    def latest(self) -> dict:
        return {
            "status": "ready",
            "calibration_run_id": 17,
            "as_of_date": "2026-07-15",
            "safety": {
                "research_only": True,
                "simulation_only": True,
                "live_trading_enabled": False,
                "execution_allowed": False,
                "orders_generated": False,
            },
        }

    def run(self, **kwargs) -> dict:
        self.calls.append(dict(kwargs))
        return {
            "status": "ready",
            "calibration_run_id": 18,
            "as_of_date": kwargs.get("as_of_date") or "2026-07-15",
            "safety": {
                "research_only": True,
                "simulation_only": True,
                "live_trading_enabled": False,
                "execution_allowed": False,
                "orders_generated": False,
            },
        }


def test_get_latest_calibration_uses_runtime_store_and_stays_research_only(
    client,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        full_market_research_routes,
        "FullMarketScoreCalibrationService",
        FakeCalibrationService,
    )

    response = client.get("/api/candidates/full-market-calibration/latest")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["calibration_run_id"] == 17
    assert payload["safety"]["research_only"] is True
    assert payload["safety"]["execution_allowed"] is False
    assert payload["safety"]["orders_generated"] is False


def test_post_calibration_run_forces_persistence_and_accepts_only_bounded_parameters(
    client,
    monkeypatch,
) -> None:
    FakeCalibrationService.calls = []
    monkeypatch.setattr(
        full_market_research_routes,
        "FullMarketScoreCalibrationService",
        FakeCalibrationService,
    )
    request_payload = {
        "horizon_trading_days": 20,
        "target_return_pct": 8.0,
        "min_history_bars": 60,
        "lookback_bars": 120,
        "validation_fraction": 0.2,
        "score_bin_width": 10,
        "sample_stride": 10,
        "min_train_samples": 200,
        "min_validation_samples": 50,
        "min_bin_samples": 30,
        "as_of_date": "2026-07-15",
    }

    response = client.post(
        "/api/candidates/full-market-calibration/run",
        json=request_payload,
    )

    assert response.status_code == 200
    assert FakeCalibrationService.calls == [{**request_payload, "persist": True}]
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["safety"]["execution_allowed"] is False
    assert payload["safety"]["orders_generated"] is False

    assert (
        client.post(
            "/api/candidates/full-market-calibration/run",
            json={"horizon_trading_days": 0},
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/candidates/full-market-calibration/run",
            json={"persist": False},
        ).status_code
        == 422
    )
