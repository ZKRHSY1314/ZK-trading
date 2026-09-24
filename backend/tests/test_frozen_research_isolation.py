"""CI contract for the byte-pinned M3/M4 research files and their isolation tests.

These checks never edit a frozen file. They prove that (1) the checkout carries
the accepted bytes, (2) the lint exemption for frozen style cannot outlive those
bytes, and (3) the M4 "no ``app`` in this process" assertions are executed in a
clean interpreter where they can genuinely pass or fail.
"""

from __future__ import annotations

import ast
import hashlib
import sys
import tomllib

import pytest

from frozen_research import (
    BACKEND_DIR,
    FROZEN_M4_SUITES,
    FROZEN_MODULE_SHA256,
    PROCESS_ISOLATED_TESTS,
    TESTS_DIR,
    describe,
    ran_count,
    run_frozen_suite,
    unittest_succeeded,
)

REPO_ROOT = BACKEND_DIR.parent
FROZEN_TEST_FILES = (
    "tests/test_m3_frozen_reader.py",
    "tests/test_m3_labels.py",
    "tests/test_m4_execution.py",
    "tests/test_m4_portfolio.py",
    "tests/test_m4_risk.py",
)
# Only style rules; a frozen file may not be exempted from anything else.
ALLOWED_FROZEN_LINT_EXEMPTIONS = {"E702", "E703", "E741", "F841"}


@pytest.mark.parametrize("relative_path", sorted(FROZEN_MODULE_SHA256))
def test_frozen_research_module_has_the_accepted_bytes(relative_path):
    digest = hashlib.sha256((BACKEND_DIR / relative_path).read_bytes()).hexdigest()
    assert digest == FROZEN_MODULE_SHA256[relative_path], (
        f"{relative_path} no longer has its accepted frozen bytes; a semantic change "
        "requires a versioned successor, not an edited freeze"
    )


def test_gitattributes_keeps_every_frozen_file_byte_exact():
    rules = {}
    for line in (REPO_ROOT / ".gitattributes").read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if parts and not parts[0].startswith("#"):
            rules[parts[0]] = parts[1:]
    for relative_path in [*FROZEN_MODULE_SHA256, *FROZEN_TEST_FILES]:
        attributes = rules.get(f"backend/{relative_path}")
        assert attributes is not None and "-text" in attributes, relative_path


def test_frozen_lint_exemptions_are_narrow_and_only_cover_frozen_files():
    config = tomllib.loads((BACKEND_DIR / "pyproject.toml").read_text(encoding="utf-8"))
    lint = config["tool"]["ruff"]["lint"]
    assert lint["select"] == ["E4", "E7", "E9", "F"]
    assert "ignore" not in lint and "extend-ignore" not in lint
    exemptions = lint.get("per-file-ignores", {})
    frozen_files = {*FROZEN_MODULE_SHA256, *FROZEN_TEST_FILES}
    for relative_path, codes in exemptions.items():
        assert relative_path in frozen_files, f"{relative_path} is not a frozen file"
        assert set(codes) <= ALLOWED_FROZEN_LINT_EXEMPTIONS, (relative_path, codes)
        assert all("*" not in part for part in relative_path.split("/"))


def test_every_process_isolated_target_exists_in_its_frozen_suite():
    for file_name, class_name, method in PROCESS_ISOLATED_TESTS:
        tree = ast.parse((TESTS_DIR / file_name).read_text(encoding="utf-8"))
        classes = {node.name: node for node in tree.body if isinstance(node, ast.ClassDef)}
        assert class_name in classes, (file_name, class_name)
        methods = {node.name for node in classes[class_name].body if isinstance(node, ast.FunctionDef)}
        assert method in methods, (file_name, class_name, method)
        source = ast.get_source_segment(
            (TESTS_DIR / file_name).read_text(encoding="utf-8"),
            next(node for node in classes[class_name].body if getattr(node, "name", None) == method),
        )
        assert 'name == "app" or name.startswith("app.")' in source


def test_pytest_host_imports_app_which_is_why_isolation_is_needed():
    # Documents the premise rather than assuming it: conftest.py imported app.
    assert "app" in sys.modules


@pytest.mark.parametrize("suite", sorted(FROZEN_M4_SUITES))
def test_frozen_m4_suite_passes_complete_in_a_clean_interpreter(suite):
    completed = run_frozen_suite(suite)
    assert unittest_succeeded(completed), describe(completed)
    assert ran_count(completed) == FROZEN_M4_SUITES[suite], describe(completed)


@pytest.mark.parametrize("target", sorted(PROCESS_ISOLATED_TESTS))
def test_isolation_assertion_is_live_when_app_is_preloaded(target):
    # Negative control: with a fake ``app`` planted in the child, the original
    # assertion must fail. A harness that passed here would prove nothing.
    file_name, class_name, method = target
    completed = run_frozen_suite(f"tests/{file_name}", f"{class_name}.{method}", contaminate_with_app=True)
    assert completed.returncode != 0, describe(completed)
    assert ran_count(completed) == 1, describe(completed)
    assert "AssertionError: True is not false" in completed.stderr, describe(completed)
    assert 'name == "app" or name.startswith("app.")' in completed.stderr, describe(completed)
