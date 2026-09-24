"""Byte pins and clean-process execution for the frozen M3/M4 research suites.

The accepted M3/M4 modules and their standalone unittest suites are byte-pinned
(including original CRLF, see ``.gitattributes``). Two M4 tests assert that no
``app`` module is loaded in their interpreter, which the ordinary pytest host
cannot honour because ``conftest.py`` imports ``app`` for every other test.

This helper runs those tests through the suites' own documented stdlib runner
(``python -B -X utf8 tests/test_m4_*.py``) in a fresh interpreter, so the
original assertion executes unchanged in a process that genuinely never
imported ``app``. It is imported by ``conftest.py`` and the isolation tests;
it is not collected as a test module and imports nothing from ``app``.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
TESTS_DIR = BACKEND_DIR / "tests"

# SHA-256 of the accepted local frozen bytes, as recorded in
# docs/CLOUD_PUBLICATION_BASELINE_20260924.md. Changing a value here is a new
# freeze, not a fix; a semantic change needs a versioned successor instead.
FROZEN_MODULE_SHA256 = {
    "app/research/m3_labels.py": "e20eb21cdea032ced319a8f45a34cdeb03fd4d8b357ac31403306fa73b225393",
    "app/research/m3_frozen_reader.py": "288594cf0acf977c5ede3f5dec6584134a879889793c4c3542d01b1d7f7ae5af",
    "app/research/m4_execution.py": "83a28b543b9ecc5edf8080ea39fa388f8b2bb5a8724ef68b4b532041216678c7",
    "app/research/m4_portfolio.py": "2b3eec837e4c3603661371fb94e8d942f45c9bfadbf018fc5d6ebee6fadb5360",
    "app/research/m4_risk.py": "faec444ee98ed6ee8c20da217a6cb29ced53d7de2ceae1e2198b1cbc73b665f2",
}

# Frozen standalone suites and the test counts recorded at their acceptance
# (M4-01: 62, M4-02A: 42, M4-02B: 36). A different count means the suite that
# ran is not the accepted one.
FROZEN_M4_SUITES = {
    "tests/test_m4_execution.py": 62,
    "tests/test_m4_portfolio.py": 42,
    "tests/test_m4_risk.py": 36,
}

# (file name, TestCase class, method) of the tests whose assertions require an
# interpreter without ``app``. conftest.py routes exactly these items to
# ``run_frozen_tests_in_clean_process``; they are neither skipped nor deselected.
PROCESS_ISOLATED_TESTS = frozenset(
    {
        (
            "test_m4_portfolio.py",
            "TestPolicyAndIsolation",
            "test_module_is_stdlib_only_without_side_effects",
        ),
        (
            "test_m4_risk.py",
            "TestImmutabilityAndDeterminism",
            "test_module_is_stdlib_only_and_frozen_modules_are_the_pinned_bytes",
        ),
    }
)

_RAN_PATTERN = re.compile(r"^Ran (\d+) tests? in ", re.MULTILINE)
_CHILD_TIMEOUT_SECONDS = 300

# Planted before the frozen runner executes, to prove the isolation assertion
# is live: with a fake ``app`` in sys.modules the original test must fail.
_CONTAMINATED_BOOTSTRAP = (
    "import runpy, sys, types\n"
    "sys.modules['app'] = types.ModuleType('app')\n"
    "sys.argv = sys.argv[1:]\n"
    "runpy.run_path(sys.argv[0], run_name='__main__')\n"
)


def clean_child_env() -> dict[str, str]:
    """Minimal environment for a frozen-suite child: no PYTHONPATH, no project settings."""
    keep = ("PATH", "SYSTEMROOT", "WINDIR", "COMSPEC", "TEMP", "TMP", "TMPDIR", "HOME", "USERPROFILE")
    env = {key: os.environ[key] for key in keep if key in os.environ}
    env["ENABLE_LIVE_TRADING"] = "false"
    env["PYTHONUTF8"] = "1"
    return env


def run_frozen_suite(
    suite: str,
    *test_ids: str,
    contaminate_with_app: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Run a frozen suite (or named ``Class.method`` ids) with its own stdlib runner.

    ``-I`` (isolated mode) ignores PYTHON* variables and user site-packages and
    does not put the script directory on sys.path, so nothing can pre-load
    ``app``. ``-B -X utf8`` matches the suites' documented invocation.
    """
    suite_path = BACKEND_DIR / suite
    if not suite_path.is_file():
        raise FileNotFoundError(suite_path)
    if contaminate_with_app:
        command = [sys.executable, "-I", "-B", "-X", "utf8", "-c", _CONTAMINATED_BOOTSTRAP, str(suite_path), *test_ids]
    else:
        command = [sys.executable, "-I", "-B", "-X", "utf8", str(suite_path), *test_ids]
    return subprocess.run(
        command,
        cwd=str(BACKEND_DIR),
        env=clean_child_env(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=_CHILD_TIMEOUT_SECONDS,
        check=False,
    )


def ran_count(completed: subprocess.CompletedProcess[str]) -> int | None:
    """Number of tests the stdlib runner reported, or None if it never summarised."""
    match = _RAN_PATTERN.search(completed.stderr)
    return int(match.group(1)) if match else None


def unittest_succeeded(completed: subprocess.CompletedProcess[str]) -> bool:
    return completed.returncode == 0 and completed.stderr.rstrip().splitlines()[-1:] == ["OK"]


def describe(completed: subprocess.CompletedProcess[str]) -> str:
    return (
        f"command: {completed.args!r}\nexit: {completed.returncode}\n"
        f"--- stdout ---\n{completed.stdout}\n--- stderr ---\n{completed.stderr}"
    )


def run_frozen_tests_in_clean_process(suite_path: Path, class_name: str, method: str) -> None:
    """Execute one frozen test in a fresh interpreter; raise AssertionError unless it passed."""
    suite = suite_path.resolve().relative_to(BACKEND_DIR).as_posix()
    completed = run_frozen_suite(suite, f"{class_name}.{method}")
    if not unittest_succeeded(completed) or ran_count(completed) != 1:
        raise AssertionError(
            f"frozen test {suite}::{class_name}::{method} did not pass in a clean interpreter\n"
            + describe(completed)
        )
