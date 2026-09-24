from __future__ import annotations

import json
from pathlib import Path

from scripts import full_market_calibration_loop


def _safe_ready_result(run_id: int = 7) -> dict:
    return {
        "status": "ready",
        "calibration_run_id": run_id,
        "as_of_date": "2026-07-15",
        "training": {"sample_count": 1_200},
        "validation": {"sample_count": 300, "mapped_sample_count": 280},
        "safety": {
            "research_only": True,
            "simulation_only": True,
            "live_trading_enabled": False,
            "execution_allowed": False,
            "orders_generated": False,
        },
    }


def test_run_once_blocks_before_calibration_when_remote_live_trading_is_enabled() -> None:
    calls: list[tuple] = []

    def request_fn(method, url, payload=None, *, timeout=30):
        calls.append((method, url, payload, timeout))
        return {"status": "ok", "live_trading_enabled": True}

    result = full_market_calibration_loop.run_once(
        "http://127.0.0.1:8000",
        deadline_seconds=900,
        request_fn=request_fn,
    )

    assert result["status"] == "blocked"
    assert result["reason"] == "remote_live_trading_enabled"
    assert result["safety"]["execution_allowed"] is False
    assert result["safety"]["orders_generated"] is False
    assert len(calls) == 1


def test_worker_posts_bounded_research_parameters_and_atomically_writes_heartbeat(
    tmp_path: Path,
) -> None:
    heartbeat_path = tmp_path / "full-market-calibration.json"
    calls: list[tuple] = []

    def request_fn(method, url, payload=None, *, timeout=30):
        calls.append((method, url, payload, timeout))
        if method == "GET":
            return {"status": "ok", "live_trading_enabled": False}
        return _safe_ready_result()

    exit_code = full_market_calibration_loop.main(
        [
            "--max-cycles",
            "1",
            "--heartbeat-path",
            str(heartbeat_path),
            "--interval-seconds",
            "86400",
            "--retry-seconds",
            "1800",
            "--deadline-seconds",
            "900",
        ],
        request_fn=request_fn,
    )

    assert exit_code == 0
    assert calls[0][0:3] == (
        "GET",
        "http://127.0.0.1:8000/health",
        None,
    )
    assert calls[1][0:2] == (
        "POST",
        "http://127.0.0.1:8000/api/candidates/full-market-calibration/run",
    )
    assert calls[1][2] == {
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
        "as_of_date": None,
    }
    assert calls[1][3] == 900
    heartbeat = json.loads(heartbeat_path.read_text(encoding="utf-8"))
    assert heartbeat["worker"] == "full_market_calibration"
    assert heartbeat["status"] == "completed"
    assert heartbeat["calibration_status"] == "ready"
    assert heartbeat["phase"] == "idle"
    assert heartbeat["next_interval_seconds"] == 86_400
    assert heartbeat["retry_interval_seconds"] == 1_800
    assert heartbeat["deadline_seconds"] == 900
    assert heartbeat["calibration_run_id"] == 7
    assert heartbeat["review_only"] is True
    assert heartbeat["simulation_only"] is True
    assert heartbeat["live_trading_enabled"] is False
    assert heartbeat["orders_generated"] is False
    assert not heartbeat_path.with_suffix(".json.tmp").exists()


def test_failed_cycle_retries_early_and_max_cycles_stops_the_worker(
    tmp_path: Path,
) -> None:
    heartbeat_path = tmp_path / "full-market-calibration.json"
    post_count = 0
    sleeps: list[float] = []

    def request_fn(method, url, payload=None, *, timeout=30):
        nonlocal post_count
        if method == "GET":
            return {"status": "ok", "live_trading_enabled": False}
        post_count += 1
        if post_count == 1:
            raise TimeoutError("fixture timeout")
        return _safe_ready_result(run_id=8)

    exit_code = full_market_calibration_loop.main(
        [
            "--max-cycles",
            "2",
            "--heartbeat-path",
            str(heartbeat_path),
            "--interval-seconds",
            "86400",
            "--retry-seconds",
            "1800",
        ],
        request_fn=request_fn,
        sleep_fn=sleeps.append,
    )

    assert exit_code == 0
    assert post_count == 2
    assert sleeps == [1_800]
    heartbeat = json.loads(heartbeat_path.read_text(encoding="utf-8"))
    assert heartbeat["cycle"] == 2
    assert heartbeat["status"] == "completed"
    assert heartbeat["calibration_run_id"] == 8
