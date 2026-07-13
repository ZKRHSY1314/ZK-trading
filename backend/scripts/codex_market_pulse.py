from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Any
import urllib.error
import urllib.request


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROMPT_PATH = PROJECT_ROOT / "backend" / "configs" / "codex_market_pulse_prompt.md"
SCHEMA_PATH = PROJECT_ROOT / "backend" / "configs" / "codex_market_pulse.schema.json"
HEARTBEAT_PATH = PROJECT_ROOT / "backend" / "logs" / "codex_market_pulse_heartbeat.json"


def request_json(method: str, url: str, payload: dict[str, Any] | None = None, timeout: int = 30) -> dict:
    body = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def build_codex_command(output_path: Path, *, codex_command: str = "codex") -> list[str]:
    return [
        codex_command,
        "exec",
        "--ephemeral",
        "--sandbox",
        "read-only",
        "--enable",
        "browser_use",
        "--disable",
        "computer_use",
        "--output-schema",
        str(SCHEMA_PATH),
        "--output-last-message",
        str(output_path),
        "--cd",
        str(PROJECT_ROOT),
        PROMPT_PATH.read_text(encoding="utf-8"),
    ]


def capture_with_codex(*, timeout_seconds: int = 900, codex_command: str = "codex") -> dict[str, Any]:
    if not PROMPT_PATH.is_file() or not SCHEMA_PATH.is_file():
        raise RuntimeError("codex_market_pulse_config_missing")
    resolved = shutil.which(codex_command)
    if resolved is None:
        raise RuntimeError("codex_cli_not_found")
    handle = tempfile.NamedTemporaryFile(prefix="codex-market-pulse-", suffix=".json", delete=False)
    output_path = Path(handle.name)
    handle.close()
    try:
        completed = subprocess.run(
            build_codex_command(output_path, codex_command=resolved),
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=max(60, int(timeout_seconds)),
            check=False,
            env={**os.environ, "PYTHONUTF8": "1"},
        )
        if completed.returncode != 0:
            error = (completed.stderr or completed.stdout or "codex_exec_failed").strip()
            raise RuntimeError(error[-2000:])
        raw = output_path.read_text(encoding="utf-8").strip()
        payload = json.loads(raw)
        evidence = payload.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            raise RuntimeError("codex_evidence_empty")
        return payload
    finally:
        output_path.unlink(missing_ok=True)


def validate_evidence_items(
    evidence: list[Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Apply the API contract per item so one malformed fact cannot reject a batch."""

    from app.api.public_opinion_routes import CodexEvidenceItemInput
    from pydantic import ValidationError

    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for index, item in enumerate(evidence):
        try:
            CodexEvidenceItemInput.model_validate(item)
        except ValidationError as exc:
            for detail in exc.errors(
                include_url=False,
                include_context=False,
                include_input=False,
            ):
                rejected.append(
                    {
                        "index": index,
                        "location": [str(part) for part in detail.get("loc") or []],
                        "type": str(detail.get("type") or "validation_error"),
                        "message": str(detail.get("msg") or "evidence rejected"),
                    }
                )
            continue
        accepted.append(dict(item))
    return accepted, rejected


def run_once(api_base: str, *, timeout_seconds: int = 900) -> dict[str, Any]:
    health = request_json("GET", f"{api_base}/health")
    if health.get("live_trading_enabled") is not False:
        return {"status": "blocked", "reason": "live_trading_enabled", "health": health}
    capture = capture_with_codex(timeout_seconds=timeout_seconds)
    captured_evidence = capture["evidence"]
    accepted_evidence, validation_errors = validate_evidence_items(captured_evidence)
    if not accepted_evidence:
        return {
            "status": "failed",
            "captured_count": len(captured_evidence),
            "submitted_count": 0,
            "accepted_count": 0,
            "rejected_count": len({error["index"] for error in validation_errors}),
            "validation_errors": validation_errors,
            "errors": validation_errors,
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": False,
        }
    result = request_json(
        "POST",
        f"{api_base}/api/public-opinion/evidence/ingest",
        {
            "evidence": accepted_evidence,
            "persist": True,
            "requested_by": "codex_market_pulse_worker",
        },
        timeout=60,
    )
    status = str(result.get("status") or "failed")
    if validation_errors and status not in {"failed", "blocked"}:
        status = "partial"
    return {
        "status": status,
        "run_id": result.get("run_id"),
        "captured_count": len(captured_evidence),
        "submitted_count": len(accepted_evidence),
        "accepted_count": result.get("item_count", 0),
        "rejected_count": len({error["index"] for error in validation_errors}),
        "validation_errors": validation_errors,
        "sector_count": result.get("sector_count", 0),
        "source_stats": result.get("source_stats") or {},
        "errors": [*validation_errors, *(result.get("errors") or [])],
        "review_only": True,
        "simulation_only": True,
        "live_trading_enabled": False,
    }


def write_heartbeat(payload: dict[str, Any]) -> None:
    HEARTBEAT_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = HEARTBEAT_PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(HEARTBEAT_PATH)


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture citation-backed A-share evidence with Codex.")
    parser.add_argument("--api-base", default="http://127.0.0.1:8000")
    parser.add_argument("--interval-seconds", type=int, default=14400)
    parser.add_argument("--max-cycles", type=int, default=1, help="0 runs forever")
    parser.add_argument("--timeout-seconds", type=int, default=900)
    args = parser.parse_args()

    cycle = 0
    final_status = "failed"
    while args.max_cycles <= 0 or cycle < args.max_cycles:
        cycle += 1
        started = datetime.now().astimezone()
        write_heartbeat(
            {
                "schema_version": "codex_market_pulse_heartbeat.v1",
                "pid": os.getpid(),
                "cycle": cycle,
                "status": "running",
                "started_at": started.isoformat(timespec="seconds"),
                "completed_at": started.isoformat(timespec="seconds"),
                "review_only": True,
                "live_trading_enabled": False,
                "interval_seconds": max(900, int(args.interval_seconds)),
            }
        )
        error = None
        try:
            result = run_once(args.api_base.rstrip("/"), timeout_seconds=args.timeout_seconds)
            final_status = str(result.get("status") or "failed")
        except (
            OSError,
            RuntimeError,
            subprocess.TimeoutExpired,
            urllib.error.URLError,
            json.JSONDecodeError,
        ) as exc:
            result = {}
            final_status = "failed"
            error = str(exc)
        heartbeat = {
            "schema_version": "codex_market_pulse_heartbeat.v1",
            "pid": os.getpid(),
            "cycle": cycle,
            "status": final_status,
            "started_at": started.isoformat(timespec="seconds"),
            "completed_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "duration_seconds": round((datetime.now().astimezone() - started).total_seconds(), 2),
            "captured_count": result.get("captured_count", 0),
            "submitted_count": result.get("submitted_count", 0),
            "accepted_count": result.get("accepted_count", 0),
            "rejected_count": result.get("rejected_count", 0),
            "validation_errors": result.get("validation_errors") or [],
            "run_id": result.get("run_id"),
            "error": error,
            "review_only": True,
            "live_trading_enabled": False,
            "interval_seconds": max(900, int(args.interval_seconds)),
        }
        write_heartbeat(heartbeat)
        print(json.dumps(heartbeat, ensure_ascii=False), flush=True)
        if args.max_cycles <= 0 or cycle < args.max_cycles:
            time.sleep(max(900, int(args.interval_seconds)))
    return 0 if final_status not in {"failed", "blocked"} else 1


if __name__ == "__main__":
    sys.exit(main())
