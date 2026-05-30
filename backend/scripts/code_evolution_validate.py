from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import subprocess
import sys
import urllib.request


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = PROJECT_ROOT / "backend"
FRONTEND_DIR = PROJECT_ROOT / "frontend"
FORBIDDEN_TRACKED_MARKERS = (
    "数据集1",
    "trading_local.sqlite3",
    ".venv",
    "node_modules",
    "frontend/dist",
    "backend/logs",
    "__pycache__",
    ".pytest_cache",
    ".codegraph",
)


def run_command(name: str, command: list[str], cwd: Path, timeout: int = 300) -> dict:
    started_at = datetime.now().isoformat(timespec="seconds")
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        return {
            "name": name,
            "command": command,
            "cwd": str(cwd),
            "returncode": completed.returncode,
            "stdout_tail": (completed.stdout or "")[-4000:],
            "stderr_tail": (completed.stderr or "")[-4000:],
            "started_at": started_at,
            "completed_at": datetime.now().isoformat(timespec="seconds"),
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "name": name,
            "command": command,
            "cwd": str(cwd),
            "returncode": 124,
            "stdout_tail": (exc.stdout or "")[-4000:] if isinstance(exc.stdout, str) else "",
            "stderr_tail": (exc.stderr or "")[-4000:] if isinstance(exc.stderr, str) else "",
            "error": "timeout",
            "started_at": started_at,
            "completed_at": datetime.now().isoformat(timespec="seconds"),
        }


def post_validation(api_base: str, record_id: int, payload: dict) -> dict:
    data = json.dumps({"validation": payload}).encode("utf-8")
    request = urllib.request.Request(
        f"{api_base}/api/experience/code-evolution/{record_id}/validation",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


def run_forbidden_tracked_scan() -> dict:
    started_at = datetime.now().isoformat(timespec="seconds")
    completed = subprocess.run(
        ["git", "ls-files"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )
    tracked_files = completed.stdout.splitlines()
    matches = [
        path
        for path in tracked_files
        if any(marker in path.replace("\\", "/") for marker in FORBIDDEN_TRACKED_MARKERS)
    ]
    return {
        "name": "forbidden_tracked_file_scan",
        "command": ["git", "ls-files", "|", "python marker scan"],
        "cwd": str(PROJECT_ROOT),
        "returncode": 1 if matches or completed.returncode != 0 else 0,
        "stdout_tail": "\n".join(matches)[-4000:],
        "stderr_tail": completed.stderr[-4000:],
        "matched_count": len(matches),
        "started_at": started_at,
        "completed_at": datetime.now().isoformat(timespec="seconds"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run V3.0 code evolution validation locally.")
    parser.add_argument("--api-base", default="http://127.0.0.1:8000")
    parser.add_argument("--record-id", type=int, help="Optional code_evolution_records id to update.")
    parser.add_argument("--skip-frontend", action="store_true")
    args = parser.parse_args()

    commands = [
        ("backend_compileall", [sys.executable, "-m", "compileall", "app", "scripts", "tests"], BACKEND_DIR, 300),
        ("backend_pytest", [sys.executable, "-m", "pytest", "-q"], BACKEND_DIR, 600),
        ("backend_pip_check", [sys.executable, "-m", "pip", "check"], BACKEND_DIR, 300),
    ]
    if not args.skip_frontend:
        commands.extend(
            [
                ("frontend_vue_tsc", ["npx.cmd", "vue-tsc", "--noEmit"], FRONTEND_DIR, 300),
                ("frontend_vite_build", ["npx.cmd", "vite", "build"], FRONTEND_DIR, 300),
                ("frontend_npm_audit", ["npm.cmd", "audit", "--audit-level=moderate"], FRONTEND_DIR, 300),
            ]
        )
    commands.extend(
        [
            ("repo_diff_check", ["git", "diff", "--check"], PROJECT_ROOT, 120),
        ]
    )

    results = [run_command(name, command, cwd, timeout) for name, command, cwd, timeout in commands]
    results.append(run_forbidden_tracked_scan())

    payload = {
        "status": "validation_passed" if all(result["returncode"] == 0 for result in results) else "validation_failed",
        "passed": all(result["returncode"] == 0 for result in results),
        "commands": results,
        "review_only": True,
        "simulation_only": True,
        "live_trading_enabled": False,
        "validated_at": datetime.now().isoformat(timespec="seconds"),
    }
    if args.record_id:
        payload["api_update"] = post_validation(args.api_base, args.record_id, payload)
    print(json.dumps(payload, ensure_ascii=True, indent=2))
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
