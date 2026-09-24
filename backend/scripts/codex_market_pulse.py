from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import signal
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
MIN_INTERVAL_SECONDS = 900
DEFAULT_MODEL = "gpt-5.5"
DEFAULT_REASONING_EFFORT = "medium"


class CodexCaptureError(RuntimeError):
    def __init__(
        self,
        *,
        code: str,
        summary: str,
        retryable: bool,
        return_code: int | None,
        attempt_count: int,
        models_tried: list[str],
    ) -> None:
        super().__init__(summary)
        self.code = code
        self.summary = summary
        self.retryable = retryable
        self.return_code = return_code
        self.attempt_count = attempt_count
        self.models_tried = models_tried


def request_json(method: str, url: str, payload: dict[str, Any] | None = None, timeout: int = 30) -> dict:
    body = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def build_codex_command(
    output_path: Path,
    *,
    codex_command: str = "codex",
    model: str = DEFAULT_MODEL,
    reasoning_effort: str = DEFAULT_REASONING_EFFORT,
) -> list[str]:
    if model != DEFAULT_MODEL or reasoning_effort != DEFAULT_REASONING_EFFORT:
        raise ValueError("codex_market_pulse_requires_gpt_5_5_medium")
    command = [
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
    ]
    command.extend(["--model", model])
    command.extend(["--config", f'model_reasoning_effort="{reasoning_effort}"'])
    command.append(PROMPT_PATH.read_text(encoding="utf-8"))
    return command


def _classify_codex_failure(completed: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    combined = "\n".join(part for part in (completed.stderr, completed.stdout) if part).strip()
    lines = [line.strip() for line in combined.splitlines() if line.strip()]
    error_lines = [line for line in lines if line.upper().startswith("ERROR:")]
    candidate = error_lines[-1] if error_lines else ""
    lowered = candidate.lower()
    if "at capacity" in lowered:
        code, retryable, summary = "model_capacity", True, candidate[-500:]
    elif "rate limit" in lowered or "too many requests" in lowered or "429" in lowered:
        code, retryable, summary = "rate_limited", True, candidate[-500:]
    elif "temporarily unavailable" in lowered or "service unavailable" in lowered:
        code, retryable, summary = "temporarily_unavailable", True, candidate[-500:]
    elif "authentication" in lowered or "unauthorized" in lowered or "401" in lowered:
        code, retryable, summary = "authentication_failed", False, candidate[-500:]
    else:
        code, retryable = "codex_exec_failed", False
        summary = f"codex_exec_failed (exit_code={completed.returncode})"
    return {
        "code": code,
        "summary": summary,
        "retryable": retryable,
        "return_code": completed.returncode,
    }


def _run_codex_process(
    command: list[str],
    *,
    timeout_seconds: float,
) -> subprocess.CompletedProcess[str]:
    """Run one Codex capture with a bounded process-tree cleanup path."""
    process_kwargs: dict[str, Any] = {
        "cwd": str(PROJECT_ROOT),
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
        "env": {**os.environ, "PYTHONUTF8": "1"},
    }
    if os.name == "nt":
        process_kwargs["creationflags"] = getattr(
            subprocess,
            "CREATE_NEW_PROCESS_GROUP",
            0,
        )
    else:
        process_kwargs["start_new_session"] = True
    process = subprocess.Popen(command, **process_kwargs)
    try:
        stdout, stderr = process.communicate(timeout=max(1.0, float(timeout_seconds)))
    except subprocess.TimeoutExpired:
        _terminate_process_tree(process)
        try:
            process.communicate(timeout=15)
        except subprocess.TimeoutExpired:
            process.kill()
            try:
                process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                pass
        raise
    return subprocess.CompletedProcess(
        command,
        int(process.returncode if process.returncode is not None else -1),
        stdout,
        stderr,
    )


def _terminate_process_tree(process: subprocess.Popen[str]) -> None:
    """Terminate the process group created exclusively for one Codex capture."""
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            capture_output=True,
            check=False,
            timeout=15,
        )
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    if process.poll() is None:
        process.kill()


def capture_with_codex(
    *,
    timeout_seconds: int = 900,
    codex_command: str = "codex",
    model: str = DEFAULT_MODEL,
    reasoning_effort: str = DEFAULT_REASONING_EFFORT,
) -> dict[str, Any]:
    if not PROMPT_PATH.is_file() or not SCHEMA_PATH.is_file():
        raise RuntimeError("codex_market_pulse_config_missing")
    resolved = shutil.which(codex_command)
    if resolved is None:
        raise RuntimeError("codex_cli_not_found")
    handle = tempfile.NamedTemporaryFile(prefix="codex-market-pulse-", suffix=".json", delete=False)
    output_path = Path(handle.name)
    handle.close()
    attempt_models = [model]
    deadline = time.monotonic() + max(60, int(timeout_seconds))
    models_tried: list[str] = []
    try:
        for attempt_index, attempt_model in enumerate(attempt_models, start=1):
            model_label = attempt_model
            models_tried.append(model_label)
            remaining_seconds = deadline - time.monotonic()
            if remaining_seconds <= 0:
                raise CodexCaptureError(
                    code="capture_timeout",
                    summary="codex_capture_timeout_budget_exhausted",
                    retryable=False,
                    return_code=None,
                    attempt_count=attempt_index - 1,
                    models_tried=models_tried[:-1],
                )
            output_path.write_text("", encoding="utf-8")
            command = build_codex_command(
                output_path,
                codex_command=resolved,
                model=attempt_model,
                reasoning_effort=reasoning_effort,
            )
            try:
                completed = _run_codex_process(
                    command,
                    timeout_seconds=remaining_seconds,
                )
            except subprocess.TimeoutExpired as exc:
                raise CodexCaptureError(
                    code="capture_timeout",
                    summary="codex_capture_timeout",
                    retryable=False,
                    return_code=None,
                    attempt_count=attempt_index,
                    models_tried=models_tried,
                ) from exc
            if completed.returncode == 0:
                raw = output_path.read_text(encoding="utf-8").strip()
                payload = json.loads(raw)
                evidence = payload.get("evidence")
                if not isinstance(evidence, list) or not evidence:
                    raise RuntimeError("codex_evidence_empty")
                payload["_capture_metadata"] = {
                    "attempt_count": attempt_index,
                    "models_tried": models_tried,
                    "selected_model": model_label,
                    "reasoning_effort": reasoning_effort,
                }
                return payload

            failure = _classify_codex_failure(completed)
            raise CodexCaptureError(
                code=failure["code"],
                summary=failure["summary"],
                retryable=failure["retryable"],
                return_code=failure["return_code"],
                attempt_count=attempt_index,
                models_tried=models_tried,
            )
        raise RuntimeError("codex_capture_attempts_exhausted")
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


def run_once(
    api_base: str,
    *,
    timeout_seconds: int = 900,
    model: str = DEFAULT_MODEL,
    reasoning_effort: str = DEFAULT_REASONING_EFFORT,
) -> dict[str, Any]:
    health = request_json("GET", f"{api_base}/health")
    if health.get("live_trading_enabled") is not False:
        return {"status": "blocked", "reason": "live_trading_enabled", "health": health}
    capture = capture_with_codex(
        timeout_seconds=timeout_seconds,
        model=model,
        reasoning_effort=reasoning_effort,
    )
    capture_metadata = capture.get("_capture_metadata") or {}
    capture_summary = {
        "attempt_count": capture_metadata.get("attempt_count", 1),
        "models_tried": capture_metadata.get("models_tried") or [],
        "selected_model": capture_metadata.get("selected_model"),
        "reasoning_effort": capture_metadata.get("reasoning_effort") or reasoning_effort,
    }
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
            **capture_summary,
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
        **capture_summary,
        "review_only": True,
        "simulation_only": True,
        "live_trading_enabled": False,
    }


def write_heartbeat(payload: dict[str, Any]) -> None:
    HEARTBEAT_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = HEARTBEAT_PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(HEARTBEAT_PATH)


def next_interval_seconds(
    status: str,
    configured_interval_seconds: int,
    *,
    accepted_count: int | None = None,
) -> int:
    configured = max(MIN_INTERVAL_SECONDS, int(configured_interval_seconds))
    del accepted_count  # Partial cycles retry early even after useful rows were persisted.
    if status in {"failed", "blocked", "partial"}:
        return MIN_INTERVAL_SECONDS
    return configured


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture citation-backed A-share evidence with Codex.")
    parser.add_argument("--api-base", default="http://127.0.0.1:8000")
    parser.add_argument("--interval-seconds", type=int, default=14400)
    parser.add_argument("--max-cycles", type=int, default=1, help="0 runs forever")
    parser.add_argument("--timeout-seconds", type=int, default=900)
    parser.add_argument("--model", choices=(DEFAULT_MODEL,), default=DEFAULT_MODEL)
    parser.add_argument(
        "--reasoning-effort",
        choices=(DEFAULT_REASONING_EFFORT,),
        default=DEFAULT_REASONING_EFFORT,
    )
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
                "configured_model": args.model,
                "reasoning_effort": args.reasoning_effort,
                "review_only": True,
                "live_trading_enabled": False,
                "interval_seconds": max(MIN_INTERVAL_SECONDS, int(args.interval_seconds)),
                "timeout_seconds": max(60, int(args.timeout_seconds)),
                "phase": "capture",
            }
        )
        error = None
        error_code = None
        return_code = None
        try:
            result = run_once(
                args.api_base.rstrip("/"),
                timeout_seconds=args.timeout_seconds,
                model=args.model,
                reasoning_effort=args.reasoning_effort,
            )
            final_status = str(result.get("status") or "failed")
        except CodexCaptureError as exc:
            result = {
                "attempt_count": exc.attempt_count,
                "models_tried": exc.models_tried,
            }
            final_status = "failed"
            error = exc.summary
            error_code = exc.code
            return_code = exc.return_code
        except subprocess.TimeoutExpired:
            result = {}
            final_status = "failed"
            error = "codex_capture_timeout"
            error_code = "capture_timeout"
        except (
            OSError,
            RuntimeError,
            urllib.error.URLError,
            json.JSONDecodeError,
        ) as exc:
            result = {}
            final_status = "failed"
            error = str(exc)
        accepted_count = int(result.get("accepted_count") or 0)
        next_interval = next_interval_seconds(
            final_status,
            args.interval_seconds,
            accepted_count=accepted_count,
        )
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
            "accepted_count": accepted_count,
            "rejected_count": result.get("rejected_count", 0),
            "validation_errors": result.get("validation_errors") or [],
            "run_id": result.get("run_id"),
            "error": error,
            "error_code": error_code,
            "return_code": return_code,
            "attempt_count": result.get("attempt_count", 0),
            "models_tried": result.get("models_tried") or [],
            "configured_model": args.model,
            "selected_model": result.get("selected_model"),
            "reasoning_effort": result.get("reasoning_effort") or args.reasoning_effort,
            "review_only": True,
            "live_trading_enabled": False,
            "interval_seconds": max(MIN_INTERVAL_SECONDS, int(args.interval_seconds)),
            "timeout_seconds": max(60, int(args.timeout_seconds)),
            "phase": "idle" if final_status == "completed" else "retry_wait",
            "next_interval_seconds": next_interval,
        }
        write_heartbeat(heartbeat)
        print(json.dumps(heartbeat, ensure_ascii=False), flush=True)
        if args.max_cycles <= 0 or cycle < args.max_cycles:
            time.sleep(next_interval)
    return 0 if final_status not in {"failed", "blocked"} else 1


if __name__ == "__main__":
    sys.exit(main())
