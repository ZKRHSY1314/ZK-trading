from __future__ import annotations

from contextlib import nullcontext
import json
from pathlib import Path
import subprocess

import pytest

from app.config import settings
from app.storage.sqlite_store import SQLiteStore
from scripts import codex_decision_review as module


def _selection_fixture() -> dict:
    candidate = {
        "symbol": "SH600129",
        "name": "太极集团",
        "final_action": "WAIT_BREAKOUT_PLAN",
        "final_score": 67.43,
        "position_class": "COST_LINE_NEAR",
        "risk_flags": [],
        "hard_blocks": [],
        "rejected_by": [],
        "invalid_conditions": ["breakdown"],
        "features": {
            "price_percentile_250d": 43.5,
            "volume_ratio": 1.62,
            "above_ma5": True,
            "above_ma10": True,
            "above_ma20": True,
            "ma5_slope": 0.2,
            "ma20_slope": -0.1,
            "market_data": {"latest_trade_date": "2026-07-14"},
            "structure_signal": {
                "pre_markup_probability": 0.81,
                "distribution_probability": 0.32,
                "confidence": 1.0,
            },
        },
    }
    return {
        "as_of": "2026-07-15T14:00:00+08:00",
        "mode": "balanced",
        "summary": {
            "candidate_count": 1,
            "data_gap_count": 0,
            "strict_buy_plan_count": 0,
            "wait_pullback_plan_count": 0,
            "wait_breakout_plan_count": 1,
            "watch_only_count": 0,
            "reject_count": 0,
            "top_blocking_reasons": [],
        },
        "wait_pullback_plans": [],
        "wait_breakout_plans": [candidate],
        "watch_only_candidates": [],
        "rejected_candidates": [],
    }


def _safe_review() -> dict:
    return {
        "schema_version": "candidate_decision_review.v1",
        "as_of": "2026-07-15T14:00:00+08:00",
        "model_profile": {"model": "gpt-5.5", "reasoning_effort": "medium"},
        "market_posture": "NO_ACTION",
        "reviews": [],
        "no_order_reason": "No candidate passed the deterministic review gates.",
        "simulation_only": True,
        "live_trading_enabled": False,
    }


def _review_item(
    symbol: str = "SH600129",
    *,
    rank: int = 1,
    action: str = "WATCH_ONLY",
) -> dict:
    return {
        "rank": rank,
        "symbol": symbol,
        "action": action,
        "confidence": "low",
        "thesis": "Read-only review.",
        "confirmations": [],
        "invalidations": ["Structure fails."],
        "uncertainties": ["No calibrated probability."],
        "order_allowed": False,
    }


def _decision_input(*candidates: dict) -> dict:
    return {
        "candidates": list(candidates),
        "safety": {
            "review_only": True,
            "simulation_only": True,
            "execution_allowed": False,
            "live_trading_enabled": False,
        },
    }


def _decision_candidate(
    symbol: str = "SH600129",
    *,
    bucket: str = "wait_breakout_plans",
    hard_blocks: list[str] | None = None,
    risk_flags: list[str] | None = None,
    rejected_by: list[str] | None = None,
    phase: str | None = "observe",
) -> dict:
    return {
        "symbol": symbol,
        "selection_bucket": bucket,
        "hard_blocks": hard_blocks or [],
        "risk_flags": risk_flags or [],
        "rejected_by": rejected_by or [],
        "phase_replay": None if phase is None else {"latest_phase": phase},
    }


def test_command_is_pinned_to_read_only_gpt_5_5_medium(tmp_path) -> None:
    command = module.build_codex_command(
        tmp_path / "output.json",
        codex_command="codex",
    )

    assert command[command.index("--model") + 1] == "gpt-5.5"
    assert 'model_reasoning_effort="medium"' in command
    assert command.count("--disable") == 2
    assert "browser_use" in command
    assert "computer_use" in command
    assert "--sandbox" in command
    assert command[command.index("--sandbox") + 1] == "read-only"
    assert "--ignore-user-config" in command
    assert "--skip-git-repo-check" in command
    assert command[command.index("--cd") + 1] == str(tmp_path)
    assert command[-1] == "-"

    with pytest.raises(ValueError, match="requires_gpt_5_5_medium"):
        module.build_codex_command(tmp_path / "output.json", model="gpt-5.6-sol")


def test_review_output_rejects_symbols_outside_input_and_duplicate_symbols() -> None:
    payload = _safe_review()
    payload["reviews"] = [_review_item("SH600999")]

    with pytest.raises(ValueError, match="symbol_not_in_input"):
        module.validate_review_output(payload, _decision_input(_decision_candidate()))

    payload["reviews"] = [_review_item(), _review_item(rank=2)]
    with pytest.raises(ValueError, match="duplicate_symbol"):
        module.validate_review_output(payload, _decision_input(_decision_candidate()))


@pytest.mark.parametrize(
    "ranks",
    ([2], [1, 1], [1, 3], [2, 1]),
)
def test_review_output_requires_contiguous_ranks_in_list_order(ranks: list[int]) -> None:
    candidates = [
        _decision_candidate(f"SH{600129 + index:06d}")
        for index in range(len(ranks))
    ]
    payload = _safe_review()
    payload["reviews"] = [
        _review_item(candidate["symbol"], rank=rank)
        for candidate, rank in zip(candidates, ranks, strict=True)
    ]

    with pytest.raises(ValueError, match="rank_sequence_mismatch"):
        module.validate_review_output(payload, _decision_input(*candidates))


@pytest.mark.parametrize(
    ("action", "bucket"),
    (
        ("WAIT_BREAKOUT_REVIEW", "wait_pullback_plans"),
        ("WAIT_PULLBACK_REVIEW", "wait_breakout_plans"),
        ("WAIT_BREAKOUT_REVIEW", "watch_only_candidates"),
        ("WAIT_PULLBACK_REVIEW", "rejected_candidates"),
    ),
)
def test_wait_review_requires_matching_wait_bucket(action: str, bucket: str) -> None:
    payload = _safe_review()
    payload["reviews"] = [_review_item(action=action)]

    with pytest.raises(ValueError, match="wait_bucket_mismatch"):
        module.validate_review_output(
            payload,
            _decision_input(_decision_candidate(bucket=bucket)),
        )


@pytest.mark.parametrize(
    "candidate",
    (
        _decision_candidate(hard_blocks=["MA_BREAKDOWN"]),
        _decision_candidate(risk_flags=["HIGH_VOLATILITY"]),
        _decision_candidate(rejected_by=["risk_gate"]),
    ),
)
def test_wait_review_rejects_any_deterministic_block(candidate: dict) -> None:
    payload = _safe_review()
    payload["reviews"] = [_review_item(action="WAIT_BREAKOUT_REVIEW")]

    with pytest.raises(ValueError, match="wait_candidate_blocked"):
        module.validate_review_output(payload, _decision_input(candidate))


@pytest.mark.parametrize(
    "phase",
    ("markup", "distribution", "post_distribution_watch", "accumulation"),
)
def test_wait_review_rejects_conflicting_phase(phase: str) -> None:
    payload = _safe_review()
    payload["reviews"] = [_review_item(action="WAIT_BREAKOUT_REVIEW")]

    with pytest.raises(ValueError, match="wait_phase_rejected"):
        module.validate_review_output(
            payload,
            _decision_input(_decision_candidate(phase=phase)),
        )


def test_wait_review_accepts_clean_matching_candidate() -> None:
    payload = _safe_review()
    payload["reviews"] = [_review_item(action="WAIT_BREAKOUT_REVIEW")]

    module.validate_review_output(
        payload,
        _decision_input(_decision_candidate()),
    )


def test_decision_input_includes_latest_phase_and_marks_proxy_uncalibrated(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "review.sqlite3")
    store.init()
    with store.connect() as connection:
        connection.execute(
            """
            INSERT INTO main_force_phase_replays(
                symbol, name, lookback_years, data_source, bars_count,
                latest_phase, summary_json, segments_json, features_json
            ) VALUES (?, ?, 2, ?, 500, ?, '{}', '[]', '{}')
            """,
            ("SH600129", "太极集团", "daily_bar_cache.qfq", "post_distribution_watch"),
        )

    payload = module.build_decision_input(_selection_fixture(), store)

    assert payload["safety"]["proxy_is_calibrated_probability"] is False
    assert payload["safety"]["execution_allowed"] is False
    assert payload["candidates"][0]["phase_replay"]["latest_phase"] == "post_distribution_watch"
    assert payload["candidates"][0]["pre_markup_proxy"] == 0.81


def test_run_once_blocks_before_selection_when_live_is_not_false(monkeypatch) -> None:
    monkeypatch.setattr(
        module,
        "request_json",
        lambda *_args, **_kwargs: {"status": "ok", "live_trading_enabled": True},
    )

    result = module.run_once("http://127.0.0.1:8000")

    assert result["status"] == "blocked"
    assert result["reason"] == "live_trading_enabled"


def test_run_once_persists_simulation_only_audit(tmp_path, monkeypatch) -> None:
    database_path = tmp_path / "review.sqlite3"
    monkeypatch.setattr(settings, "database_path", database_path)

    def fake_request(url: str, **_kwargs):
        if url.endswith("/health"):
            return {"status": "ok", "live_trading_enabled": False}
        return _selection_fixture()

    monkeypatch.setattr(module, "request_json", fake_request)
    monkeypatch.setattr(module, "capture_with_codex", lambda *_args, **_kwargs: _safe_review())

    result = module.run_once("http://127.0.0.1:8000")

    assert result["status"] == "completed"
    assert result["model"] == "gpt-5.5"
    assert result["reasoning_effort"] == "medium"
    store = SQLiteStore(database_path)
    row = store.fetch_one("SELECT * FROM ai_model_audit_logs WHERE id = ?", (result["audit_id"],))
    assert row["provider"] == "codex_cli:gpt-5.5"
    assert row["operation"] == "candidate_decision_review"
    assert row["simulation_only"] == 1
    safety = json.loads(row["safety_json"])
    assert safety["execution_allowed"] is False
    assert safety["browser_enabled"] is False
    assert safety["computer_use_enabled"] is False


def test_run_once_rechecks_health_and_does_not_persist_if_live_changes(
    tmp_path,
    monkeypatch,
) -> None:
    database_path = tmp_path / "review.sqlite3"
    monkeypatch.setattr(settings, "database_path", database_path)
    health_calls = 0

    def fake_request(url: str, **_kwargs):
        nonlocal health_calls
        if url.endswith("/health"):
            health_calls += 1
            return {
                "status": "ok",
                "live_trading_enabled": health_calls > 1,
            }
        return _selection_fixture()

    monkeypatch.setattr(module, "request_json", fake_request)
    monkeypatch.setattr(module, "capture_with_codex", lambda *_args, **_kwargs: _safe_review())

    result = module.run_once("http://127.0.0.1:8000")

    assert health_calls == 2
    assert result["status"] == "blocked"
    assert result["reason"] == "live_trading_enabled_after_review"
    store = SQLiteStore(database_path)
    assert store.fetch_one("SELECT COUNT(*) AS count FROM ai_model_audit_logs")["count"] == 0


def test_capture_timeout_uses_fixed_error_without_prompt(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(module.shutil, "which", lambda _command: "codex")
    terminated: list[int] = []

    class TimedOutProcess:
        pid = 4321
        returncode = None

        def __init__(self, command, **_kwargs):
            self.command = command
            self.communicate_calls = 0

        def communicate(self, **kwargs):
            self.communicate_calls += 1
            if self.communicate_calls == 1:
                raise subprocess.TimeoutExpired(self.command, kwargs["timeout"])
            return ("", "")

    def terminate(process) -> None:
        terminated.append(process.pid)
        process.returncode = 1

    monkeypatch.setattr(module.subprocess, "Popen", TimedOutProcess)
    monkeypatch.setattr(module, "_terminate_process_tree", terminate)

    with pytest.raises(RuntimeError, match="codex_decision_review_timeout") as raised:
        module.capture_with_codex({"sensitive": "prompt"}, timeout_seconds=60)

    assert terminated == [4321]
    assert "sensitive" not in str(raised.value)


def test_capture_runs_in_an_isolated_temporary_working_directory(monkeypatch) -> None:
    monkeypatch.setattr(module.shutil, "which", lambda _command: "codex")
    observed: dict = {}

    class SuccessfulProcess:
        pid = 1234
        returncode = 0

        def __init__(self, command, **kwargs):
            observed["command"] = command
            observed["cwd"] = kwargs["cwd"]
            observed["cwd_existed"] = Path(kwargs["cwd"]).is_dir()
            output_path = Path(command[command.index("--output-last-message") + 1])
            output_path.write_text(json.dumps(_safe_review()), encoding="utf-8")

        def communicate(self, **kwargs):
            observed["prompt"] = kwargs["input"]
            return ("", "")

    monkeypatch.setattr(module.subprocess, "Popen", SuccessfulProcess)
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda *_args, **_kwargs: pytest.fail("capture must use Popen for tree cleanup"),
    )

    result = module.capture_with_codex(_decision_input(_decision_candidate()))

    command = observed["command"]
    assert result == _safe_review()
    assert observed["cwd_existed"] is True
    assert Path(observed["cwd"]) != module.PROJECT_ROOT
    assert command[command.index("--cd") + 1] == observed["cwd"]
    assert "DECISION_INPUT_JSON" in observed["prompt"]


def test_schema_and_prompt_files_exist() -> None:
    assert module.SCHEMA_PATH == Path(module.SCHEMA_PATH)
    assert module.SCHEMA_PATH.is_file()
    assert module.PROMPT_PATH.is_file()


def test_worker_lock_prevents_a_second_instance(tmp_path) -> None:
    lock_path = tmp_path / "decision-review.lock"

    with module._worker_lock(lock_path):
        with pytest.raises(RuntimeError, match="another decision-review worker"):
            with module._worker_lock(lock_path):
                pytest.fail("the second worker must never enter the critical section")
    assert lock_path.read_text(encoding="ascii") == str(module.os.getpid())


def test_failed_and_blocked_cycles_retry_after_900_seconds() -> None:
    assert module.next_interval_seconds("failed", 14_400) == 900
    assert module.next_interval_seconds("blocked", 14_400) == 900
    assert module.next_interval_seconds("completed", 14_400) == 14_400


def test_main_heartbeat_starts_ready_and_records_retry_interval(monkeypatch) -> None:
    heartbeats: list[dict] = []
    monkeypatch.setattr(
        module,
        "parse_args",
        lambda: module.argparse.Namespace(
            api_base="http://127.0.0.1:8000",
            timeout_seconds=900,
            interval_seconds=14_400,
            max_cycles=1,
            model="gpt-5.5",
            reasoning_effort="medium",
        ),
    )
    monkeypatch.setattr(module, "_worker_lock", lambda _path: nullcontext())
    monkeypatch.setattr(
        module,
        "run_once",
        lambda *_args, **_kwargs: {"status": "blocked", "reason": "live_trading_enabled"},
    )
    monkeypatch.setattr(module, "write_heartbeat", lambda payload: heartbeats.append(dict(payload)))

    exit_code = module.main()

    assert exit_code == 1
    assert heartbeats[0]["status"] == "running"
    assert heartbeats[0]["completed_at"] == heartbeats[0]["started_at"]
    assert heartbeats[-1]["status"] == "blocked"
    assert heartbeats[-1]["next_interval_seconds"] == 900
