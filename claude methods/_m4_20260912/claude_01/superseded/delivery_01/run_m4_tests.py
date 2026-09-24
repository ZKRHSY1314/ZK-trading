"""Guarded standalone runner for backend/tests/test_m4_execution.py (M4-01, claude_01).

What it guards (audit hooks + monkeypatches installed BEFORE the test module is loaded):
  * sqlite3.connect and every ``sqlite3.connect`` audit event  -> RuntimeError (denied, counted)
  * socket creation / connect / bind / getaddrinfo / gethostbyname -> RuntimeError (denied, counted)
  * subprocess.Popen / os.system / os.posix_spawn / os.exec*      -> RuntimeError (denied, counted)
  * any file opened for writing outside claude_01/                 -> RuntimeError (denied, counted)
  * bytecode writes: sys.dont_write_bytecode = True (and the command uses -B)
The test module is loaded by file path (no ``app`` package import, no conftest, no pytest).

Writes, all inside claude_01/:
  evidence/test_stdout.txt            unittest verbose output (also echoed to the console)
  evidence/test_case_results.json     every result record produced by the tests (RESULT_LOG)
  evidence/execution_receipt.json     real command, UTC start/end, exit code, test counts, hashes, guard log

    backend/.venv/Scripts/python.exe -B -X utf8 "claude methods/_m4_20260912/claude_01/run_m4_tests.py"
"""
from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
import platform
import socket
import sqlite3
import subprocess
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True

HERE = Path(__file__).resolve().parent                     # .../_m4_20260912/claude_01
PROJECT = HERE.parents[2]                                  # D:\codex-A股交易
MODULE = PROJECT / "backend" / "app" / "research" / "m4_execution.py"
TESTS = PROJECT / "backend" / "tests" / "test_m4_execution.py"
EVIDENCE = HERE / "evidence"
ALLOWED_WRITE_ROOT = HERE.resolve()

GUARD_LOG: list[dict] = []


def _deny(kind: str, detail: str) -> None:
    GUARD_LOG.append({"kind": kind, "detail": detail, "at_utc": datetime.now(timezone.utc).isoformat()})
    raise RuntimeError(f"denied by M4-01 runner guard: {kind}: {detail}")


def _is_write_mode(mode, flags) -> bool:
    if isinstance(mode, str):
        return any(ch in mode for ch in "wax+")
    if isinstance(flags, int):
        return bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_TRUNC))
    return False


def _audit(event: str, args: tuple) -> None:
    if event == "open":
        path, mode, flags = args[0], args[1] if len(args) > 1 else None, args[2] if len(args) > 2 else None
        if _is_write_mode(mode, flags):
            try:
                target = Path(os.fsdecode(path)).resolve() if not isinstance(path, int) else None
            except Exception:  # noqa: BLE001
                target = None
            if target is None or ALLOWED_WRITE_ROOT not in (target, *target.parents):
                _deny("write_outside_claude_01", f"{path!r} mode={mode!r} flags={flags!r}")
    elif event == "sqlite3.connect":
        _deny("sqlite", repr(args[:1]))
    elif event.startswith("socket.") and event not in ("socket.__new__",):
        _deny("network", f"{event} {args[:1]!r}")
    elif event in ("subprocess.Popen", "os.system", "os.posix_spawn", "os.exec", "os.spawn", "os.fork"):
        _deny("subprocess", f"{event} {args[:1]!r}")


def _install_guards() -> None:
    sqlite3.connect = lambda *a, **k: _deny("sqlite", "sqlite3.connect monkeypatch")  # type: ignore[assignment]

    class _DeniedSocket(socket.socket):
        def __init__(self, *a, **k):
            _deny("network", "socket.socket construction")

    socket.socket = _DeniedSocket  # type: ignore[misc,assignment]
    socket.create_connection = lambda *a, **k: _deny("network", "socket.create_connection")  # type: ignore[assignment]
    subprocess.Popen = lambda *a, **k: _deny("subprocess", "subprocess.Popen monkeypatch")  # type: ignore[assignment,misc]
    subprocess.run = lambda *a, **k: _deny("subprocess", "subprocess.run monkeypatch")  # type: ignore[assignment]
    os.system = lambda *a, **k: _deny("subprocess", "os.system monkeypatch")  # type: ignore[assignment]
    sys.addaudithook(_audit)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _self_check_guards() -> dict:
    """Prove the guards deny what they claim to deny (each probe must raise RuntimeError)."""
    probe_path = PROJECT / "m4_guard_probe_should_not_exist.tmp"
    probes = {
        "sqlite3.connect": lambda: sqlite3.connect(":memory:"),
        "socket.socket": lambda: socket.socket(),
        "subprocess.run": lambda: subprocess.run([sys.executable, "-c", "pass"]),
        "os.system": lambda: os.system("echo probe"),
        "write_outside_claude_01": lambda: open(probe_path, "w", encoding="utf-8"),
    }
    outcome = {}
    for name, probe in probes.items():
        try:
            probe()
            outcome[name] = "NOT_DENIED"
        except RuntimeError as exc:
            outcome[name] = "denied" if "denied by M4-01 runner guard" in str(exc) else f"other_error:{exc}"
        except Exception as exc:  # noqa: BLE001
            outcome[name] = f"other_error:{type(exc).__name__}"
    outcome["probe_file_created"] = probe_path.exists()
    # a write inside claude_01 must still work
    inside = EVIDENCE / "guard_probe_inside_claude_01.txt"
    inside.write_text("write inside claude_01 allowed\n", encoding="utf-8")
    outcome["write_inside_claude_01"] = "allowed" if inside.exists() else "BLOCKED"
    return outcome


def main() -> int:
    started = datetime.now(timezone.utc)
    command = [sys.executable, *sys.orig_argv[1:]] if hasattr(sys, "orig_argv") else [sys.executable, *sys.argv]
    EVIDENCE.mkdir(exist_ok=True)
    module_sha_before, tests_sha_before = sha256(MODULE), sha256(TESTS)
    _install_guards()
    guard_self_check = _self_check_guards()
    self_check_denials = list(GUARD_LOG)
    GUARD_LOG.clear()

    spec = importlib.util.spec_from_file_location("test_m4_execution_guarded", TESTS)
    test_module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = test_module
    spec.loader.exec_module(test_module)

    stream = io.StringIO()
    suite = unittest.defaultTestLoader.loadTestsFromModule(test_module)
    test_names = sorted(f"{t.__class__.__name__}.{t._testMethodName}" for t in _iter_tests(suite))
    runner = unittest.TextTestRunner(stream=stream, verbosity=2)
    result = runner.run(suite)
    stdout_text = stream.getvalue()
    sys.stdout.write(stdout_text)
    finished = datetime.now(timezone.utc)
    exit_code = 0 if result.wasSuccessful() else 1

    (EVIDENCE / "test_stdout.txt").write_text(stdout_text, encoding="utf-8")
    (EVIDENCE / "test_case_results.json").write_text(
        json.dumps(test_module.RESULT_LOG, indent=1, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    kernel = test_module.m
    case_log = test_module.RESULT_LOG
    receipt = {
        "schema": "m4.claude_01.execution_receipt.v1",
        "task_id": "M4-01-EXECUTION-CONTRACT-20260912",
        "command": command,
        "cwd": os.getcwd(),
        "python": {"executable": sys.executable, "version": platform.python_version(), "flags": {"dont_write_bytecode": sys.dont_write_bytecode,
                   "utf8_mode": bool(sys.flags.utf8_mode)}},
        "started_at_utc": started.isoformat(),
        "finished_at_utc": finished.isoformat(),
        "exit_code": exit_code,
        "tests": {"run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors), "skipped": len(result.skipped),
                  "successful": result.wasSuccessful(),
                  "names": test_names},
        "recorded_cases": {"count": len(case_log), "by_status": _count_by_status(case_log)},
        "files": {"backend/app/research/m4_execution.py": {"sha256": module_sha_before, "bytes": MODULE.stat().st_size, "unchanged_during_run": sha256(MODULE) == module_sha_before},
                  "backend/tests/test_m4_execution.py": {"sha256": tests_sha_before, "bytes": TESTS.stat().st_size, "unchanged_during_run": sha256(TESTS) == tests_sha_before},
                  "claude methods/_m4_20260912/claude_01/run_m4_tests.py": {"sha256": sha256(Path(__file__)), "bytes": Path(__file__).stat().st_size}},
        "contract": {"version": kernel.CONTRACT_VERSION, "policy_hash": kernel.POLICY_HASH},
        "guards": {"installed": ["sqlite3.connect", "socket", "subprocess/os.system", "write_outside_claude_01", "bytecode"],
                   "self_check": guard_self_check, "self_check_denials": self_check_denials,
                   "denials_during_tests": GUARD_LOG, "denial_count_during_tests": len(GUARD_LOG)},
        "isolation": {"pytest": False, "conftest_loaded": "backend.tests.conftest" in sys.modules or "conftest" in sys.modules,
                      "app_package_imported": any(name == "app" or name.startswith("app.") for name in sys.modules),
                      "legacy_engine_imported": any("backtest" in name for name in sys.modules), "sqlite_connections": 0, "network_requests": 0},
        "safety": {"review_only": True, "live_trading_enabled": False, "synthetic_fixtures_only": True, "real_market_data_used": False,
                   "hypothetical_fee_schedules_only": True, "accepted_by_codex": False, "M4_complete": False},
    }
    (EVIDENCE / "execution_receipt.json").write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"exit_code": exit_code, "tests_run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
                      "guard_denials": len(GUARD_LOG), "policy_hash": kernel.POLICY_HASH}, ensure_ascii=False))
    return exit_code


def _iter_tests(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from _iter_tests(item)
        else:
            yield item


def _count_by_status(case_log: dict) -> dict:
    counts: dict[str, int] = {}
    for rec in case_log.values():
        counts[rec["status"]] = counts.get(rec["status"], 0) + 1
    return dict(sorted(counts.items()))


if __name__ == "__main__":
    sys.exit(main())
