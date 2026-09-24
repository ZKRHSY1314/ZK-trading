from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess

import pytest


def _load_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "codex_market_pulse.py"
    spec = importlib.util.spec_from_file_location("codex_market_pulse", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_codex_command_is_ephemeral_read_only_and_schema_bound(tmp_path):
    module = _load_module()
    command = module.build_codex_command(tmp_path / "result.json", codex_command="codex")

    assert command[:2] == ["codex", "exec"]
    assert "--ephemeral" in command
    assert command[command.index("--sandbox") + 1] == "read-only"
    assert command[command.index("--output-schema") + 1].endswith(
        "codex_market_pulse.schema.json"
    )
    assert "browser_use" in command
    assert "computer_use" in command
    assert command[command.index("--model") + 1] == "gpt-5.5"
    assert command[command.index("--config") + 1] == 'model_reasoning_effort="medium"'
    assert "--dangerously-bypass-approvals-and-sandbox" not in command


def test_codex_capture_does_not_fallback_when_gpt_5_5_is_at_capacity(monkeypatch):
    module = _load_module()
    commands = []

    def fake_run(command, **kwargs):
        commands.append(command)
        return subprocess.CompletedProcess(
            command,
            1,
            stdout="prompt body that must not become the error",
            stderr="ERROR: Selected model is at capacity. Please try a different model.",
        )

    monkeypatch.setattr(module.shutil, "which", lambda _: "codex")
    monkeypatch.setattr(module, "_run_codex_process", fake_run)

    with pytest.raises(module.CodexCaptureError) as raised:
        module.capture_with_codex(timeout_seconds=120)

    assert raised.value.code == "model_capacity"
    assert raised.value.attempt_count == 1
    assert raised.value.models_tried == ["gpt-5.5"]
    assert len(commands) == 1
    assert commands[0][commands[0].index("--model") + 1] == "gpt-5.5"


def test_codex_capture_error_is_classified_and_does_not_persist_prompt(monkeypatch):
    module = _load_module()
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(
            command,
            1,
            stdout="SENSITIVE_PROMPT " * 100,
            stderr="ERROR: Selected model is at capacity. Please try a different model.",
        )

    monkeypatch.setattr(module.shutil, "which", lambda _: "codex")
    monkeypatch.setattr(module, "_run_codex_process", fake_run)

    with pytest.raises(module.CodexCaptureError) as raised:
        module.capture_with_codex(timeout_seconds=120)

    assert raised.value.code == "model_capacity"
    assert raised.value.attempt_count == 1
    assert "SENSITIVE_PROMPT" not in str(raised.value)
    assert len(calls) == 1


def test_codex_capture_does_not_retry_non_transient_failure(monkeypatch):
    module = _load_module()
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(
            command,
            1,
            stdout="",
            stderr="ERROR: Authentication failed (401).",
        )

    monkeypatch.setattr(module.shutil, "which", lambda _: "codex")
    monkeypatch.setattr(module, "_run_codex_process", fake_run)

    with pytest.raises(module.CodexCaptureError) as raised:
        module.capture_with_codex()

    assert raised.value.code == "authentication_failed"
    assert raised.value.attempt_count == 1
    assert len(calls) == 1


def test_codex_runtime_profile_rejects_configured_default_or_coding_model(tmp_path):
    module = _load_module()

    with pytest.raises(ValueError, match="requires_gpt_5_5_medium"):
        module.build_codex_command(tmp_path / "result.json", model=None)
    with pytest.raises(ValueError, match="requires_gpt_5_5_medium"):
        module.build_codex_command(tmp_path / "result.json", model="gpt-5.6-sol")
    with pytest.raises(ValueError, match="requires_gpt_5_5_medium"):
        module.build_codex_command(tmp_path / "result.json", reasoning_effort="xhigh")


def test_worker_heartbeat_records_fixed_runtime_profile(monkeypatch):
    module = _load_module()
    heartbeats = []
    monkeypatch.setattr(module.sys, "argv", ["codex_market_pulse.py", "--max-cycles", "1"])
    monkeypatch.setattr(
        module,
        "run_once",
        lambda *args, **kwargs: {
            "status": "completed",
            "accepted_count": 1,
            "attempt_count": 1,
            "models_tried": ["gpt-5.5"],
            "selected_model": "gpt-5.5",
            "reasoning_effort": "medium",
        },
    )
    monkeypatch.setattr(module, "write_heartbeat", heartbeats.append)

    assert module.main() == 0
    assert len(heartbeats) == 2
    assert all(item["configured_model"] == "gpt-5.5" for item in heartbeats)
    assert all(item["reasoning_effort"] == "medium" for item in heartbeats)
    assert all(item["timeout_seconds"] == 900 for item in heartbeats)


def test_codex_capture_timeout_does_not_expose_command_prompt(monkeypatch):
    module = _load_module()
    terminated = []

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

    def terminate(process):
        terminated.append(process.pid)
        process.returncode = 1

    monkeypatch.setattr(module.shutil, "which", lambda _: "codex")
    monkeypatch.setattr(module.subprocess, "Popen", TimedOutProcess)
    monkeypatch.setattr(module, "_terminate_process_tree", terminate, raising=False)
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda *_args, **_kwargs: pytest.fail("capture must use Popen for tree cleanup"),
    )

    with pytest.raises(module.CodexCaptureError) as raised:
        module.capture_with_codex()

    assert terminated == [4321]
    assert raised.value.code == "capture_timeout"
    assert str(raised.value) == "codex_capture_timeout"
    assert module.PROMPT_PATH.read_text(encoding="utf-8") not in str(raised.value)


def test_unknown_codex_failure_uses_fixed_summary(monkeypatch):
    module = _load_module()

    def fake_run(command, **kwargs):
        return subprocess.CompletedProcess(
            command,
            7,
            stdout="SENSITIVE_PROMPT_OUTPUT",
            stderr="unexpected process failure without a standard marker",
        )

    monkeypatch.setattr(module.shutil, "which", lambda _: "codex")
    monkeypatch.setattr(module, "_run_codex_process", fake_run)

    with pytest.raises(module.CodexCaptureError) as raised:
        module.capture_with_codex()

    assert raised.value.code == "codex_exec_failed"
    assert str(raised.value) == "codex_exec_failed (exit_code=7)"
    assert "SENSITIVE_PROMPT_OUTPUT" not in str(raised.value)


def test_invalid_evidence_preserves_capture_attempt_metadata(monkeypatch):
    module = _load_module()
    monkeypatch.setattr(
        module,
        "request_json",
        lambda *args, **kwargs: {"status": "ok", "live_trading_enabled": False},
    )
    monkeypatch.setattr(
        module,
        "capture_with_codex",
        lambda **kwargs: {
            "evidence": [{"title": "invalid"}],
            "_capture_metadata": {
                "attempt_count": 1,
                "models_tried": ["gpt-5.5"],
                "selected_model": "gpt-5.5",
                "reasoning_effort": "medium",
            },
        },
    )

    result = module.run_once("http://127.0.0.1:8000")

    assert result["status"] == "failed"
    assert result["attempt_count"] == 1
    assert result["models_tried"] == ["gpt-5.5"]
    assert result["selected_model"] == "gpt-5.5"


def test_codex_market_pulse_health_gates_then_ingests_structured_evidence(monkeypatch):
    module = _load_module()
    calls = []
    evidence = {
        "retrieved_at": "2026-07-10T10:00:00+08:00",
        "evidence": [
            {
                "url": "https://www.csrc.gov.cn/example",
                "retrieved_at": "2026-07-10T10:00:00+08:00",
                "published_at_status": "known",
                "published_at": "2026-07-10T09:00:00+08:00",
                "title": "资本市场政策测试证据",
                "summary": "仅用于验证结构化证据传递。",
                "source_name": "中国证监会",
                "source_id": "csrc",
                "source_tier": "official",
                "category": "policy",
                "sector_hints": ["brokerage_finance"],
                "claims": ["测试声明"],
            }
        ],
    }

    def fake_request(method, url, payload=None, timeout=30):
        calls.append((method, url, payload, timeout))
        if method == "GET":
            return {"status": "ok", "live_trading_enabled": False}
        return {
            "status": "completed",
            "run_id": 17,
            "item_count": 1,
            "sector_count": 1,
            "source_stats": {"succeeded_count": 1},
            "errors": [],
        }

    monkeypatch.setattr(module, "request_json", fake_request)
    monkeypatch.setattr(module, "capture_with_codex", lambda **_: evidence)

    result = module.run_once("http://127.0.0.1:8000")

    assert result["status"] == "completed"
    assert result["captured_count"] == 1
    assert result["accepted_count"] == 1
    assert calls[0][0:2] == ("GET", "http://127.0.0.1:8000/health")
    assert calls[1][0:2] == (
        "POST",
        "http://127.0.0.1:8000/api/public-opinion/evidence/ingest",
    )
    assert calls[1][2]["evidence"] == evidence["evidence"]


def test_codex_market_pulse_output_schema_is_closed():
    module = _load_module()
    schema = json.loads(module.SCHEMA_PATH.read_text(encoding="utf-8"))

    assert schema["additionalProperties"] is False
    item = schema["properties"]["evidence"]["items"]
    assert item["additionalProperties"] is False
    assert "url" in item["required"]
    assert "published_at_status" in item["required"]
    assert item["properties"]["url"]["minLength"] == 8
    assert item["properties"]["url"]["maxLength"] == 2048
    assert item["properties"]["title"]["minLength"] == 6
    assert item["properties"]["title"]["maxLength"] == 160


def test_codex_market_pulse_retries_failed_cycles_before_regular_interval():
    module = _load_module()

    assert module.next_interval_seconds("failed", 14_400) == 900
    assert module.next_interval_seconds("blocked", 14_400) == 900
    assert module.next_interval_seconds("partial", 14_400, accepted_count=0) == 900
    assert module.next_interval_seconds("partial", 14_400, accepted_count=1) == 900
    assert module.next_interval_seconds("completed", 14_400) == 14_400


def test_codex_market_pulse_rejects_only_invalid_items_before_batch_ingest(monkeypatch):
    module = _load_module()
    submitted = []
    valid = {
        "event_id": "evt-valid",
        "cluster_id": "cluster-valid",
        "type": "policy",
        "entities": ["CSRC"],
        "geography": ["CN"],
        "status": "new",
        "direction": "neutral",
        "magnitude": 0.4,
        "url": "https://www.csrc.gov.cn/example",
        "retrieved_at": "2026-07-13T14:00:00+08:00",
        "first_seen_at": "2026-07-13T14:00:00+08:00",
        "available_at": "2026-07-13T14:00:00+08:00",
        "revision": 1,
        "evidence_urls": ["https://www.csrc.gov.cn/example"],
        "raw_hash": "a" * 64,
        "published_at_status": "known",
        "published_at": "2026-07-13T13:50:00+08:00",
        "title": "Capital market policy evidence",
        "summary": "Structured evidence used to verify batch validation.",
        "source_name": "China Securities Regulatory Commission",
        "source_id": "csrc",
        "source_tier": "official",
        "category": "policy",
        "sector_hints": ["brokerage_finance"],
        "claims": ["A policy notice was published."],
    }
    invalid = {**valid, "event_id": "evt-invalid", "retrieved_at": "not-a-datetime"}

    def fake_request(method, url, payload=None, timeout=30):
        if method == "GET":
            return {"status": "ok", "live_trading_enabled": False}
        from app.api.public_opinion_routes import CodexEvidenceItemInput

        for item in payload["evidence"]:
            CodexEvidenceItemInput.model_validate(item)
        submitted.extend(payload["evidence"])
        return {
            "status": "completed",
            "run_id": 18,
            "item_count": len(payload["evidence"]),
            "sector_count": 1,
            "source_stats": {"succeeded_count": len(payload["evidence"])},
            "errors": [],
        }

    monkeypatch.setattr(module, "request_json", fake_request)
    monkeypatch.setattr(
        module,
        "capture_with_codex",
        lambda **_: {"evidence": [valid, invalid]},
    )

    result = module.run_once("http://127.0.0.1:8000")

    assert result["status"] == "partial"
    assert result["captured_count"] == 2
    assert result["accepted_count"] == 1
    assert result["rejected_count"] == 1
    assert result["validation_errors"][0]["index"] == 1
    assert submitted == [valid]
