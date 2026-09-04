from __future__ import annotations

import json
import subprocess

import pytest

from app.config import settings
from scripts import reference_data_loop


def _completed_result() -> dict[str, object]:
    return {
        "status": "completed",
        "mode": "apply",
        "sectors": {"status": "completed", "membership_records_written": 2},
        "disclosures": {"status": "completed", "facts_written": 1},
        "global_markets": {
            "status": "completed",
            "bar_records_written": 24,
            "ready_source_coverage_pct": 100.0,
        },
    }


def test_run_once_blocks_before_constructing_provider_when_live_is_enabled(monkeypatch) -> None:
    def _must_not_construct():
        raise AssertionError("service/provider constructed while live trading was enabled")

    monkeypatch.setattr(settings, "enable_live_trading", True)

    result = reference_data_loop.run_once(
        service_factory=_must_not_construct,
        board_limit=5,
        disclosure_limit=10,
        global_days=30,
        rate_limit_seconds=0,
        skip_sox=True,
    )

    assert result["status"] == "blocked"
    assert result["reason"] == "live_trading_enabled"
    assert result["writes_enabled"] is False


def test_worker_runs_first_apply_immediately_and_atomically_writes_heartbeat(
    tmp_path,
) -> None:
    heartbeat = tmp_path / "reference-data-heartbeat.json"
    calls: list[dict[str, object]] = []
    sleeps: list[float] = []

    class _Service:
        def run(self, **kwargs):
            calls.append(kwargs)
            return _completed_result()

    exit_code = reference_data_loop.main(
        [
            "--max-cycles",
            "1",
            "--interval-seconds",
            "14400",
            "--board-limit",
            "7",
            "--disclosure-limit",
            "11",
            "--global-days",
            "30",
            "--rate-limit-seconds",
            "0",
            "--skip-sox",
        ],
        service_factory=_Service,
        heartbeat_path=heartbeat,
        sleep_fn=sleeps.append,
    )

    assert exit_code == 0
    assert sleeps == []
    assert calls == [
        {
            "apply": True,
            "board_limit": 7,
            "disclosure_limit": 11,
            "rate_limit_seconds": 0.0,
            "global_days": 30,
            "include_global": True,
            "include_sox": False,
            "global_symbol_limit": None,
        }
    ]
    payload = json.loads(heartbeat.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "reference_data_heartbeat.v1"
    assert payload["cycle"] == 1
    assert payload["status"] == "completed"
    assert payload["interval_seconds"] == 14400
    assert payload["review_only"] is True
    assert payload["simulation_only"] is True
    assert payload["live_trading_enabled"] is False
    assert payload["writes_enabled"] is True
    assert payload["apply"] is True
    assert payload["summary"] == {
        "mode": "apply",
        "sector_status": "completed",
        "sector_memberships_written": 2,
        "disclosure_status": "completed",
        "disclosure_facts_written": 1,
        "global_market_status": "completed",
        "global_bars_written": 24,
        "global_ready_source_coverage_pct": 100.0,
        "reason": None,
    }
    assert not heartbeat.with_suffix(".tmp").exists()


def test_cycle_exception_is_recorded_and_does_not_abort_the_next_cycle(
    tmp_path,
    capsys,
) -> None:
    heartbeat = tmp_path / "reference-data-heartbeat.json"
    sleeps: list[float] = []

    class _FlakyService:
        calls = 0

        def run(self, **_):
            type(self).calls += 1
            if type(self).calls == 1:
                raise ConnectionError("reference source disconnected")
            return _completed_result()

    exit_code = reference_data_loop.main(
        ["--max-cycles", "2", "--interval-seconds", "1", "--skip-sox"],
        service_factory=_FlakyService,
        heartbeat_path=heartbeat,
        sleep_fn=sleeps.append,
    )

    assert exit_code == 1
    assert _FlakyService.calls == 2
    assert sleeps == [60]
    output = capsys.readouterr().out
    assert "reference source disconnected" in output
    assert '"status": "failed"' in output
    final_payload = json.loads(heartbeat.read_text(encoding="utf-8"))
    assert final_payload["cycle"] == 2
    assert final_payload["status"] == "completed"


def test_unsuccessful_reference_cycle_retries_before_regular_interval(
    tmp_path,
) -> None:
    heartbeat = tmp_path / "reference-data-heartbeat.json"
    sleeps: list[float] = []

    class _PartialThenCompleteService:
        calls = 0

        def run(self, **_):
            type(self).calls += 1
            if type(self).calls == 1:
                return {
                    **_completed_result(),
                    "status": "partial",
                    "sectors": {
                        "status": "partial",
                        "membership_records_written": 0,
                    },
                }
            return _completed_result()

    exit_code = reference_data_loop.main(
        ["--max-cycles", "2", "--interval-seconds", "14400", "--skip-sox"],
        service_factory=_PartialThenCompleteService,
        heartbeat_path=heartbeat,
        sleep_fn=sleeps.append,
    )

    assert exit_code == 1
    assert _PartialThenCompleteService.calls == 2
    assert sleeps == [900]
    final_payload = json.loads(heartbeat.read_text(encoding="utf-8"))
    assert final_payload["status"] == "completed"
    assert final_payload["next_interval_seconds"] == 14400


def test_reference_summary_keeps_section_error_evidence() -> None:
    result = _completed_result()
    result["status"] = "partial"
    result["sectors"] = {
        "status": "partial",
        "membership_records_written": 2,
        "errors": [
            {
                "source": "akshare.stock_board_industry_cons_em",
                "error": "upstream timed out",
            }
        ],
    }

    summary = reference_data_loop._result_summary(result)

    assert summary["source_errors"] == {
        "sectors": [
            {
                "source": "akshare.stock_board_industry_cons_em",
                "error": "upstream timed out",
            }
        ]
    }


def test_blocked_finite_worker_returns_nonzero_without_calling_service(
    tmp_path,
    monkeypatch,
) -> None:
    heartbeat = tmp_path / "reference-data-heartbeat.json"

    def _must_not_construct():
        raise AssertionError("blocked worker constructed service")

    monkeypatch.setattr(settings, "enable_live_trading", True)

    exit_code = reference_data_loop.main(
        ["--max-cycles", "1"],
        service_factory=_must_not_construct,
        heartbeat_path=heartbeat,
    )

    assert exit_code == 1
    payload = json.loads(heartbeat.read_text(encoding="utf-8"))
    assert payload["status"] == "blocked"
    assert payload["interval_seconds"] == 14400
    assert payload["writes_enabled"] is False
    assert payload["summary"]["reason"] == "live_trading_enabled"


def test_production_cycle_terminates_a_hung_ingest_subprocess(monkeypatch) -> None:
    def _timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], kwargs["timeout"])

    monkeypatch.setattr(reference_data_loop.subprocess, "run", _timeout)

    with pytest.raises(TimeoutError, match="exceeded 60 seconds"):
        reference_data_loop.run_once(
            service_factory=None,
            board_limit=5,
            disclosure_limit=10,
            global_days=30,
            rate_limit_seconds=0,
            skip_sox=True,
            timeout_seconds=60,
        )


def test_worker_refuses_a_second_instance_holding_the_same_lock(tmp_path) -> None:
    heartbeat = tmp_path / "reference-data-heartbeat.json"

    with reference_data_loop._worker_lock(heartbeat.with_suffix(".lock")):
        with pytest.raises(RuntimeError, match="already holds the lock"):
            reference_data_loop.main(
                ["--max-cycles", "1", "--skip-sox"],
                service_factory=lambda: None,
                heartbeat_path=heartbeat,
            )
