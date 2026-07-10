from __future__ import annotations

import importlib.util
import json
from pathlib import Path


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
    assert "--dangerously-bypass-approvals-and-sandbox" not in command


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
