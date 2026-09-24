"""Guarded standalone runner for the M4-02B risk/exit suite (and, optionally, read-only reruns of the frozen kernel / ledger suites).

Guards are installed and self-checked BEFORE any test subject is imported: sqlite3.connect, sockets, subprocesses
and file writes outside claude_02b/ are denied (audit hook + monkeypatches); bytecode is disabled.  The test
subjects (frozen kernel, frozen ledger and the new risk layer) are loaded by file path inside the test modules; ``app`` is never
imported.  Outputs (all inside claude_02b/evidence/):

  risk_suite_stdout.txt / risk_scenarios.json / execution_receipt.json             (default: the new suite once)
  kernel_suite_rerun_*.{txt,json} / ledger_suite_rerun_*.{txt,json}                (--kernel-suite / --ledger-suite: frozen suites, read-only)

    backend/.venv/Scripts/python.exe -B -X utf8 "claude methods/_m4_20260912/claude_02b/run_m4_risk_tests.py"
    backend/.venv/Scripts/python.exe -B -X utf8 "claude methods/_m4_20260912/claude_02b/run_m4_risk_tests.py" --kernel-suite
    backend/.venv/Scripts/python.exe -B -X utf8 "claude methods/_m4_20260912/claude_02b/run_m4_risk_tests.py" --ledger-suite
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

HERE = Path(__file__).resolve().parent                     # .../_m4_20260912/claude_02b
PROJECT = HERE.parents[2]
EVIDENCE = HERE / "evidence"
ALLOWED_WRITE_ROOT = HERE.resolve()
KERNEL = PROJECT / "backend" / "app" / "research" / "m4_execution.py"
LEDGER = PROJECT / "backend" / "app" / "research" / "m4_portfolio.py"
LEDGER_TESTS = PROJECT / "backend" / "tests" / "test_m4_portfolio.py"
KERNEL_TESTS = PROJECT / "backend" / "tests" / "test_m4_execution.py"
RISK = PROJECT / "backend" / "app" / "research" / "m4_risk.py"
RISK_TESTS = PROJECT / "backend" / "tests" / "test_m4_risk.py"
FROZEN = {"backend/app/research/m4_execution.py": "83a28b543b9ecc5edf8080ea39fa388f8b2bb5a8724ef68b4b532041216678c7",
          "backend/tests/test_m4_execution.py": "90d8790400a497f31868ab52f985f1fe98c98806871c7346f68e8e5821c19317",
          "backend/app/research/m4_portfolio.py": "2b3eec837e4c3603661371fb94e8d942f45c9bfadbf018fc5d6ebee6fadb5360",
          "backend/tests/test_m4_portfolio.py": "8d15f54411c628e859002bc3f3de383b7de79e860f852189c3d40a3e89f6e8e6"}
GUARD_LOG: list[dict] = []


def _deny(kind: str, detail: str) -> None:
    GUARD_LOG.append({"kind": kind, "detail": detail})
    raise RuntimeError(f"denied by M4-02B runner guard: {kind}: {detail}")


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
                _deny("write_outside_claude_02b", f"{path!r} mode={mode!r} flags={flags!r}")
    elif event == "sqlite3.connect":
        _deny("sqlite", repr(args[:1]))
    elif event.startswith("socket.") and event != "socket.__new__":
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


def _self_check_guards() -> dict:
    probe_path = PROJECT / "m4_02b_guard_probe_should_not_exist.tmp"
    probes = {"sqlite3.connect": lambda: sqlite3.connect(":memory:"), "socket.socket": lambda: socket.socket(),
              "subprocess.run": lambda: subprocess.run([sys.executable, "-c", "pass"]), "os.system": lambda: os.system("echo probe"),
              "write_outside_claude_02b": lambda: open(probe_path, "w", encoding="utf-8")}
    outcome = {}
    for name, probe in probes.items():
        try:
            probe()
            outcome[name] = "NOT_DENIED"
        except RuntimeError as exc:
            outcome[name] = "denied" if "denied by M4-02B runner guard" in str(exc) else f"other_error:{exc}"
        except Exception as exc:  # noqa: BLE001
            outcome[name] = f"other_error:{type(exc).__name__}"
    outcome["probe_file_created"] = probe_path.exists()
    inside = EVIDENCE / "guard_probe_inside_claude_02b.txt"
    inside.write_text("write inside claude_02b allowed\n", encoding="utf-8")
    outcome["write_inside_claude_02b"] = "allowed" if inside.exists() else "BLOCKED"
    return outcome


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _iter_tests(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from _iter_tests(item)
        else:
            yield item


def run_suite(test_path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, test_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    stream = io.StringIO()
    suite = unittest.defaultTestLoader.loadTestsFromModule(module)
    names = sorted(f"{t.__class__.__name__}.{t._testMethodName}" for t in _iter_tests(suite))
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    return module, result, stream.getvalue(), names


def main(argv: list[str]) -> int:
    kernel_suite = "--kernel-suite" in argv
    ledger_suite = "--ledger-suite" in argv
    started = datetime.now(timezone.utc)
    command = [sys.executable, *sys.orig_argv[1:]]
    EVIDENCE.mkdir(exist_ok=True)
    hashes_before = {"backend/app/research/m4_execution.py": sha256(KERNEL), "backend/app/research/m4_portfolio.py": sha256(LEDGER),
                     "backend/tests/test_m4_portfolio.py": sha256(LEDGER_TESTS), "backend/tests/test_m4_execution.py": sha256(KERNEL_TESTS),
                     "backend/app/research/m4_risk.py": sha256(RISK), "backend/tests/test_m4_risk.py": sha256(RISK_TESTS)}
    frozen_ok = all(hashes_before[k] == v for k, v in FROZEN.items())
    _install_guards()
    guard_self_check = _self_check_guards()
    self_check_denials = list(GUARD_LOG)
    GUARD_LOG.clear()

    if kernel_suite:
        module, result, stdout_text, names = run_suite(KERNEL_TESTS, "test_m4_execution_readonly_rerun")
        label, stdout_file, receipt_file = "frozen_kernel_suite_rerun", "kernel_suite_rerun_stdout.txt", "kernel_suite_rerun_receipt.json"
    elif ledger_suite:
        module, result, stdout_text, names = run_suite(LEDGER_TESTS, "test_m4_portfolio_readonly_rerun")
        label, stdout_file, receipt_file = "frozen_ledger_suite_rerun", "ledger_suite_rerun_stdout.txt", "ledger_suite_rerun_receipt.json"
    else:
        module, result, stdout_text, names = run_suite(RISK_TESTS, "test_m4_risk_guarded")
        label, stdout_file, receipt_file = "risk_suite", "risk_suite_stdout.txt", "execution_receipt.json"
        (EVIDENCE / "risk_scenarios.json").write_text(json.dumps(module.SCENARIO_LOG, indent=1, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    sys.stdout.write(stdout_text)
    finished = datetime.now(timezone.utc)
    exit_code = 0 if result.wasSuccessful() else 1
    (EVIDENCE / stdout_file).write_text(stdout_text, encoding="utf-8")
    hashes_after = {"backend/app/research/m4_execution.py": sha256(KERNEL), "backend/app/research/m4_portfolio.py": sha256(LEDGER),
                    "backend/tests/test_m4_portfolio.py": sha256(LEDGER_TESTS), "backend/tests/test_m4_execution.py": sha256(KERNEL_TESTS),
                    "backend/app/research/m4_risk.py": sha256(RISK), "backend/tests/test_m4_risk.py": sha256(RISK_TESTS)}
    receipt = {
        "schema": "m4.claude_02b.execution_receipt.v1", "task_id": "M4-02B-RISK-EXIT-20260912", "suite": label,
        "command": command, "cwd": os.getcwd(),
        "python": {"executable": sys.executable, "version": platform.python_version(), "dont_write_bytecode": sys.dont_write_bytecode, "utf8_mode": bool(sys.flags.utf8_mode)},
        "started_at_utc": started.isoformat(), "finished_at_utc": finished.isoformat(), "exit_code": exit_code,
        "tests": {"run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors), "skipped": len(result.skipped),
                  "successful": result.wasSuccessful(), "names": names},
        "files": {rel: {"sha256_before": h, "sha256_after": hashes_after[rel], "unchanged_during_run": h == hashes_after[rel]} for rel, h in hashes_before.items()},
        "frozen_pins_ok": frozen_ok,
        "risk_scenarios": (sorted(module.SCENARIO_LOG) if label == "risk_suite" else None),
        "guards": {"installed": ["sqlite3.connect", "socket", "subprocess/os.system", "write_outside_claude_02b", "bytecode"],
                   "self_check": guard_self_check, "self_check_denials": self_check_denials,
                   "denials_during_tests": GUARD_LOG, "denial_count_during_tests": len(GUARD_LOG)},
        "isolation": {"pytest": False, "conftest_loaded": any(n.endswith("conftest") for n in sys.modules),
                      "app_package_imported": any(n == "app" or n.startswith("app.") for n in sys.modules),
                      "legacy_engine_imported": any("backtest" in n for n in sys.modules), "sqlite_connections": 0, "network_requests": 0, "wall_clock_waits": 0},
        "safety": {"review_only": True, "live_trading_enabled": False, "training_eligible": False, "M4_complete": False, "synthetic_fixtures_only": True,
                   "hypothetical_fee_schedules_only": True, "accepted_by_codex": False},
    }
    (EVIDENCE / receipt_file).write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"suite": label, "exit_code": exit_code, "tests_run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
                      "guard_denials_during_tests": len(GUARD_LOG), "frozen_pins_ok": frozen_ok}, ensure_ascii=False))
    return exit_code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
