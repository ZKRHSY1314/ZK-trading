from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import time
from typing import Any, Iterator
import urllib.request

from app.config import settings
from app.storage.sqlite_store import SQLiteStore


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROMPT_PATH = PROJECT_ROOT / "backend" / "configs" / "codex_decision_review_prompt.md"
SCHEMA_PATH = PROJECT_ROOT / "backend" / "configs" / "codex_decision_review.schema.json"
HEARTBEAT_PATH = PROJECT_ROOT / "backend" / "logs" / "codex_decision_review_heartbeat.json"
LOCK_PATH = PROJECT_ROOT / "backend" / "logs" / "codex_decision_review.lock"
DEFAULT_MODEL = "gpt-5.5"
DEFAULT_REASONING_EFFORT = "medium"
MIN_INTERVAL_SECONDS = 900
MAX_REVIEW_CANDIDATES = 12


def request_json(url: str, *, timeout: int = 60) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
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
        raise ValueError("codex_decision_review_requires_gpt_5_5_medium")
    return [
        codex_command,
        "exec",
        "--ephemeral",
        "--ignore-user-config",
        "--skip-git-repo-check",
        "--sandbox",
        "read-only",
        "--disable",
        "browser_use",
        "--disable",
        "computer_use",
        "--output-schema",
        str(SCHEMA_PATH),
        "--output-last-message",
        str(output_path),
        "--cd",
        str(output_path.parent),
        "--model",
        model,
        "--config",
        f'model_reasoning_effort="{reasoning_effort}"',
        "-",
    ]


def build_decision_prompt(decision_input: dict[str, Any]) -> str:
    return (
        PROMPT_PATH.read_text(encoding="utf-8")
        + "\n\nDECISION_INPUT_JSON:\n"
        + json.dumps(decision_input, ensure_ascii=False, separators=(",", ":"))
    )


def build_decision_input(
    selection: dict[str, Any],
    store: SQLiteStore,
    *,
    max_candidates: int = MAX_REVIEW_CANDIDATES,
) -> dict[str, Any]:
    max_candidates = max(1, min(int(max_candidates), MAX_REVIEW_CANDIDATES))
    bucket_order = (
        "wait_pullback_plans",
        "wait_breakout_plans",
        "watch_only_candidates",
        "rejected_candidates",
    )
    collected: list[tuple[str, dict[str, Any]]] = []
    seen: set[str] = set()
    for bucket in bucket_order:
        rows = selection.get(bucket) or []
        ranked = sorted(rows, key=lambda row: float(row.get("final_score") or 0), reverse=True)
        for row in ranked:
            symbol = str(row.get("symbol") or "")
            if not symbol or symbol in seen:
                continue
            seen.add(symbol)
            collected.append((bucket, row))
            if len(collected) >= max_candidates:
                break
        if len(collected) >= max_candidates:
            break

    phases = _latest_phases(store, [row["symbol"] for _, row in collected])
    candidates = [
        _candidate_view(bucket, row, phases.get(str(row.get("symbol"))))
        for bucket, row in collected
    ]
    summary = selection.get("summary") or {}
    return {
        "schema_version": "candidate_decision_input.v1",
        "as_of": selection.get("as_of"),
        "selection_mode": selection.get("mode"),
        "summary": {
            key: summary.get(key)
            for key in (
                "candidate_count",
                "data_gap_count",
                "strict_buy_plan_count",
                "wait_pullback_plan_count",
                "wait_breakout_plan_count",
                "watch_only_count",
                "reject_count",
                "top_blocking_reasons",
            )
        },
        "candidates": candidates,
        "safety": {
            "review_only": True,
            "simulation_only": True,
            "execution_allowed": False,
            "live_trading_enabled": False,
            "proxy_is_calibrated_probability": False,
        },
    }


def _candidate_view(
    bucket: str,
    row: dict[str, Any],
    phase: dict[str, Any] | None,
) -> dict[str, Any]:
    features = row.get("features") or {}
    structure = features.get("structure_signal") or {}
    market_data = features.get("market_data") or {}
    return {
        "symbol": row.get("symbol"),
        "name": row.get("name"),
        "selection_bucket": bucket,
        "final_action": row.get("final_action"),
        "final_score": row.get("final_score"),
        "position_class": row.get("position_class"),
        "risk_flags": row.get("risk_flags") or [],
        "hard_blocks": row.get("hard_blocks") or [],
        "rejected_by": row.get("rejected_by") or [],
        "invalid_conditions": row.get("invalid_conditions") or [],
        "pre_markup_proxy": structure.get("pre_markup_probability"),
        "distribution_proxy": structure.get("distribution_probability"),
        "structure_confidence": structure.get("confidence"),
        "price_percentile_250d": features.get("price_percentile_250d"),
        "volume_ratio": features.get("volume_ratio"),
        "above_ma5": features.get("above_ma5"),
        "above_ma10": features.get("above_ma10"),
        "above_ma20": features.get("above_ma20"),
        "ma5_slope": features.get("ma5_slope"),
        "ma20_slope": features.get("ma20_slope"),
        "latest_trade_date": market_data.get("latest_trade_date"),
        "phase_replay": phase,
    }


def _latest_phases(store: SQLiteStore, symbols: list[str]) -> dict[str, dict[str, Any]]:
    unique = sorted(set(symbols))
    if not unique:
        return {}
    placeholders = ",".join("?" for _ in unique)
    rows = store.fetch_all(
        f"""
        WITH latest AS (
            SELECT symbol, MAX(id) AS id
            FROM main_force_phase_replays
            WHERE symbol IN ({placeholders})
            GROUP BY symbol
        )
        SELECT replay.symbol, replay.latest_phase, replay.bars_count,
               replay.data_source, replay.created_at
        FROM main_force_phase_replays AS replay
        JOIN latest ON latest.id = replay.id
        """,
        tuple(unique),
    )
    return {
        str(row["symbol"]): {
            "latest_phase": row.get("latest_phase"),
            "bars_count": row.get("bars_count"),
            "data_source": row.get("data_source"),
            "created_at": row.get("created_at"),
        }
        for row in rows
    }


def capture_with_codex(
    decision_input: dict[str, Any],
    *,
    timeout_seconds: int = 900,
    codex_command: str = "codex",
    model: str = DEFAULT_MODEL,
    reasoning_effort: str = DEFAULT_REASONING_EFFORT,
) -> dict[str, Any]:
    if not PROMPT_PATH.is_file() or not SCHEMA_PATH.is_file():
        raise RuntimeError("codex_decision_review_config_missing")
    resolved = shutil.which(codex_command)
    if resolved is None:
        raise RuntimeError("codex_cli_not_found")
    with tempfile.TemporaryDirectory(prefix="codex-decision-review-") as temporary_directory:
        isolated_workdir = Path(temporary_directory)
        output_path = isolated_workdir / "decision-review.json"
        command = build_codex_command(
            output_path,
            codex_command=resolved,
            model=model,
            reasoning_effort=reasoning_effort,
        )
        prompt = build_decision_prompt(decision_input)
        process_kwargs: dict[str, Any] = {
            "cwd": str(isolated_workdir),
            "stdin": subprocess.PIPE,
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
            stdout, stderr = process.communicate(
                input=prompt,
                timeout=max(60, int(timeout_seconds)),
            )
        except subprocess.TimeoutExpired as exc:
            _terminate_process_tree(process)
            try:
                process.communicate(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate()
            raise RuntimeError("codex_decision_review_timeout") from exc
        completed = subprocess.CompletedProcess(
            command,
            int(process.returncode or 0),
            stdout,
            stderr,
        )
        if completed.returncode != 0:
            summary = _safe_failure_summary(completed)
            raise RuntimeError(
                f"codex_decision_review_failed (exit_code={completed.returncode}): {summary}"
            )
        payload = json.loads(output_path.read_text(encoding="utf-8"))
        validate_review_output(payload, decision_input)
        return payload


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


def _safe_failure_summary(completed: subprocess.CompletedProcess[str]) -> str:
    combined = "\n".join(part for part in (completed.stderr, completed.stdout) if part)
    error_lines = [
        line.strip()
        for line in combined.splitlines()
        if line.strip().upper().startswith("ERROR:")
    ]
    return error_lines[-1][-500:] if error_lines else "no_safe_error_detail"


def validate_review_output(
    payload: dict[str, Any],
    decision_input: dict[str, Any],
) -> None:
    if payload.get("schema_version") != "candidate_decision_review.v1":
        raise ValueError("decision_review_schema_mismatch")
    if payload.get("simulation_only") is not True or payload.get("live_trading_enabled") is not False:
        raise ValueError("decision_review_safety_mismatch")
    profile = payload.get("model_profile") or {}
    if profile != {"model": DEFAULT_MODEL, "reasoning_effort": DEFAULT_REASONING_EFFORT}:
        raise ValueError("decision_review_model_profile_mismatch")
    reviews = payload.get("reviews") or []
    if any(item.get("order_allowed") is not False for item in reviews):
        raise ValueError("decision_review_order_capability_rejected")
    candidates_by_symbol = {
        str(candidate.get("symbol") or ""): candidate
        for candidate in decision_input.get("candidates") or []
        if candidate.get("symbol")
    }
    input_symbols = set(candidates_by_symbol)
    output_symbols = [str(item.get("symbol") or "") for item in reviews]
    if any(symbol not in input_symbols for symbol in output_symbols):
        raise ValueError("decision_review_symbol_not_in_input")
    if len(set(output_symbols)) != len(output_symbols):
        raise ValueError("decision_review_duplicate_symbol")
    ranks = [item.get("rank") for item in reviews]
    if ranks != list(range(1, len(reviews) + 1)):
        raise ValueError("decision_review_rank_sequence_mismatch")
    wait_buckets = {
        "WAIT_BREAKOUT_REVIEW": "wait_breakout_plans",
        "WAIT_PULLBACK_REVIEW": "wait_pullback_plans",
    }
    rejected_wait_phases = {
        "markup",
        "distribution",
        "post_distribution_watch",
        "accumulation",
    }
    for item in reviews:
        action = str(item.get("action") or "")
        expected_bucket = wait_buckets.get(action)
        if expected_bucket is None:
            continue
        candidate = candidates_by_symbol[str(item.get("symbol") or "")]
        if candidate.get("selection_bucket") != expected_bucket:
            raise ValueError("decision_review_wait_bucket_mismatch")
        if any(candidate.get(field) for field in ("hard_blocks", "risk_flags", "rejected_by")):
            raise ValueError("decision_review_wait_candidate_blocked")
        phase = (candidate.get("phase_replay") or {}).get("latest_phase")
        if str(phase or "").strip().lower() in rejected_wait_phases:
            raise ValueError("decision_review_wait_phase_rejected")


def run_once(
    api_base: str,
    *,
    timeout_seconds: int = 900,
    model: str = DEFAULT_MODEL,
    reasoning_effort: str = DEFAULT_REASONING_EFFORT,
) -> dict[str, Any]:
    api_base = api_base.rstrip("/")
    health = request_json(f"{api_base}/health", timeout=10)
    if health.get("live_trading_enabled") is not False:
        return {"status": "blocked", "reason": "live_trading_enabled", "health": health}
    selection = request_json(
        f"{api_base}/api/candidates/selection-v2/summary?mode=balanced&limit=300",
        timeout=90,
    )
    store = SQLiteStore(settings.database_path)
    store.init()
    decision_input = build_decision_input(selection, store)
    review = capture_with_codex(
        decision_input,
        timeout_seconds=timeout_seconds,
        model=model,
        reasoning_effort=reasoning_effort,
    )
    validate_review_output(review, decision_input)
    post_review_health = request_json(f"{api_base}/health", timeout=10)
    if post_review_health.get("live_trading_enabled") is not False:
        return {
            "status": "blocked",
            "reason": "live_trading_enabled_after_review",
            "health": post_review_health,
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": post_review_health.get("live_trading_enabled"),
        }
    safety = {
        "model": model,
        "reasoning_effort": reasoning_effort,
        "review_only": True,
        "simulation_only": True,
        "live_trading_enabled": False,
        "execution_allowed": False,
        "browser_enabled": False,
        "computer_use_enabled": False,
    }
    with store.connect() as connection:
        cursor = connection.execute(
            """
            INSERT INTO ai_model_audit_logs(
                provider, operation, prompt_json, response_json, safety_json, simulation_only
            ) VALUES (?, ?, ?, ?, ?, 1)
            """,
            (
                f"codex_cli:{model}",
                "candidate_decision_review",
                json.dumps(decision_input, ensure_ascii=False),
                json.dumps(review, ensure_ascii=False),
                json.dumps(safety, ensure_ascii=False),
            ),
        )
        audit_id = int(cursor.lastrowid)
    return {
        "status": "completed",
        "audit_id": audit_id,
        "candidate_count": len(decision_input["candidates"]),
        "review_count": len(review.get("reviews") or []),
        "market_posture": review.get("market_posture"),
        "no_order_reason": review.get("no_order_reason"),
        "model": model,
        "reasoning_effort": reasoning_effort,
        "review_only": True,
        "simulation_only": True,
        "live_trading_enabled": False,
    }


def write_heartbeat(payload: dict[str, Any]) -> None:
    HEARTBEAT_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = HEARTBEAT_PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(HEARTBEAT_PATH)


@contextmanager
def _worker_lock(path: Path) -> Iterator[None]:
    """Hold the same OS-backed, lifetime lock used by reference_data_loop."""
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+b")
    locked = False
    try:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            locked = True
        except OSError as exc:
            raise RuntimeError("another decision-review worker already holds the lock") from exc
        handle.seek(0)
        handle.truncate()
        handle.write(str(os.getpid()).encode("ascii"))
        handle.flush()
        yield
    finally:
        if locked:
            handle.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


def next_interval_seconds(status: str, configured_interval_seconds: int) -> int:
    configured = max(MIN_INTERVAL_SECONDS, int(configured_interval_seconds))
    if status in {"failed", "blocked"}:
        return MIN_INTERVAL_SECONDS
    return configured


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the read-only GPT candidate decision reviewer.")
    parser.add_argument("--api-base", default="http://127.0.0.1:8000")
    parser.add_argument("--timeout-seconds", type=int, default=900)
    parser.add_argument("--interval-seconds", type=int, default=14400)
    parser.add_argument("--max-cycles", type=int, default=1, help="0 runs forever")
    parser.add_argument("--model", choices=(DEFAULT_MODEL,), default=DEFAULT_MODEL)
    parser.add_argument(
        "--reasoning-effort",
        choices=(DEFAULT_REASONING_EFFORT,),
        default=DEFAULT_REASONING_EFFORT,
    )
    return parser.parse_args()


def _run_cycles(args: argparse.Namespace) -> int:
    interval = max(MIN_INTERVAL_SECONDS, int(args.interval_seconds))
    cycle = 0
    final_status = "failed"
    while args.max_cycles == 0 or cycle < args.max_cycles:
        cycle += 1
        started = datetime.now().astimezone()
        heartbeat: dict[str, Any] = {
            "schema_version": "codex_decision_review_heartbeat.v1",
            "status": "running",
            "cycle": cycle,
            "pid": os.getpid(),
            "started_at": started.isoformat(timespec="seconds"),
            "completed_at": started.isoformat(timespec="seconds"),
            "configured_model": args.model,
            "reasoning_effort": args.reasoning_effort,
            "interval_seconds": interval,
            "next_interval_seconds": interval,
            "review_only": True,
            "live_trading_enabled": False,
        }
        write_heartbeat(heartbeat)
        try:
            result = run_once(
                args.api_base,
                timeout_seconds=args.timeout_seconds,
                model=args.model,
                reasoning_effort=args.reasoning_effort,
            )
            heartbeat.update(result)
        except Exception as exc:
            heartbeat.update({"status": "failed", "error": str(exc)[:500]})
        final_status = str(heartbeat.get("status") or "failed")
        completed = datetime.now().astimezone()
        next_interval = next_interval_seconds(final_status, interval)
        heartbeat["completed_at"] = completed.isoformat(timespec="seconds")
        heartbeat["duration_seconds"] = round((completed - started).total_seconds(), 2)
        heartbeat["next_interval_seconds"] = next_interval
        write_heartbeat(heartbeat)
        print(json.dumps(heartbeat, ensure_ascii=False), flush=True)
        if args.max_cycles != 0 and cycle >= args.max_cycles:
            break
        time.sleep(next_interval)
    return 0 if final_status not in {"failed", "blocked"} else 1


def main() -> int:
    args = parse_args()
    try:
        with _worker_lock(LOCK_PATH):
            return _run_cycles(args)
    except RuntimeError as exc:
        print(json.dumps({"status": "blocked", "error": str(exc)}, ensure_ascii=False), flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
