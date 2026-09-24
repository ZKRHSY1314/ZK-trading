"""Guarded standalone run of the revised synthetic suite (revision 2): zero SQLite connections, no network, writes only
claude_03b/evidence/synthetic_test_receipt_rev02.json.  Does NOT touch the historical runner or any run folder.

    backend/.venv/Scripts/python.exe -B -X utf8 "claude methods/_m4_20260912/claude_03b/run_synthetic_tests_rev02.py"
"""
from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[2]
sys.dont_write_bytecode = True


def load_module(name, path):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    started = datetime.now(timezone.utc).isoformat()
    guard = load_module("m4_03b_guard", HERE / "guard.py")
    guard.install()
    self_check = guard.self_check(HERE / "evidence")
    tests = load_module("m4_03b_test_replay_synthetic", HERE / "test_replay_synthetic.py")
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(tests))
    receipt = {"schema": "m4.claude_03b.synthetic_test_receipt.v2", "revision": "rev02", "started_at_utc": started, "finished_at_utc": datetime.now(timezone.utc).isoformat(),
               "command": [sys.executable, "-B", "-X", "utf8", str(Path(__file__).resolve().relative_to(PROJECT).as_posix())],
               "test_module_sha256": sha256(HERE / "test_replay_synthetic.py"), "replay_core_sha256": sha256(HERE / "replay_core.py"), "guard_sha256": sha256(HERE / "guard.py"),
               "tests_run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors), "skipped": len(result.skipped), "successful": result.wasSuccessful(),
               "stdout": stream.getvalue(), "scenarios": tests.SCENARIOS, "guard": {"self_check": self_check, **guard.receipt()},
               "safety": {"sqlite_connections": len(guard.CONNECTIONS), "network_requests": 0, "historical_runner_invocations": 0, "review_only": True, "live_trading_enabled": False,
                          "training_eligible": False, "strict_pit": False, "M4_complete": False, "M5_started": False}}
    (HERE / "evidence" / "synthetic_test_receipt_rev02.json").write_text(json.dumps(receipt, indent=2, ensure_ascii=False, sort_keys=True, default=str) + "\n", encoding="utf-8")
    print(json.dumps({"tests_run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors), "successful": result.wasSuccessful(),
                      "connections": len(guard.CONNECTIONS), "denials_during_tests": len(guard.DENIAL_LOG), "self_check": self_check}, ensure_ascii=False, indent=1))
    return 0 if result.wasSuccessful() and not guard.CONNECTIONS and not guard.DENIAL_LOG else 1


if __name__ == "__main__":
    sys.exit(main())
