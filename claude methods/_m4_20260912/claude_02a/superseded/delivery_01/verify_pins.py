"""Pre-work / post-work verification for M4-02A (claude_02a).

Verifies every pin in _m4_20260912/execution_freeze.json (frozen kernel, tests, M4-01 evidence), the task
file, the M4 baseline (42 immutable pins, 316 tracked files, 16 production file positions - byte hashing
only, no SQL), and records branch/HEAD and git status (read-only git).  Writes ONLY
claude_02a/evidence/<label>_verification.json.  Nothing else is touched.

    backend/.venv/Scripts/python.exe -B -X utf8 "claude methods/_m4_20260912/claude_02a/verify_pins.py" prework
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[2]
M4 = HERE.parent
TASK_FILE = "claude methods/M4_02A_PORTFOLIO_LEDGER_CLAUDE_TASK_20260912.md"
TASK_SHA = "ad435ec48f303a4ab8b3b33739f200b10b5eb962365ad68709dfc9101179a2e4"
FREEZE_SHA = "8a74233f21740f365b1c286d5c735dd4ead42c2ad00016ac9823e6ee5814e3f3"
KERNEL_SHA = "83a28b543b9ecc5edf8080ea39fa388f8b2bb5a8724ef68b4b532041216678c7"
KERNEL_TESTS_SHA = "90d8790400a497f31868ab52f985f1fe98c98806871c7346f68e8e5821c19317"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def norm(text: str) -> str:
    p = Path(text)
    if p.is_absolute():
        try:
            return p.resolve().relative_to(PROJECT).as_posix()
        except ValueError:
            return p.as_posix()
    return text.replace("\\", "/")


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=PROJECT, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False).stdout


def main(label: str) -> int:
    problems: list[str] = []
    freeze_path = M4 / "execution_freeze.json"
    freeze_sha = sha256(freeze_path)
    if freeze_sha != FREEZE_SHA:
        problems.append(f"freeze_sha:{freeze_sha}")
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    pins = {}
    for rel, meta in freeze["pins"].items():
        p = PROJECT / rel
        actual = sha256(p) if p.is_file() else None
        size = p.stat().st_size if p.is_file() else None
        ok = actual == meta["sha256"] and size == meta["bytes"]
        pins[rel] = {"expected": meta["sha256"], "actual": actual, "bytes": size, "ok": ok}
        if not ok:
            problems.append(f"freeze_pin:{rel}")
    task_sha = sha256(PROJECT / TASK_FILE)
    if task_sha != TASK_SHA:
        problems.append("task_file_sha")
    kernel_sha, tests_sha = sha256(PROJECT / "backend/app/research/m4_execution.py"), sha256(PROJECT / "backend/tests/test_m4_execution.py")
    if kernel_sha != KERNEL_SHA or tests_sha != KERNEL_TESTS_SHA or freeze["policy_hash"] != "9bea83482d545e6f39dd8eb70e89d674dd5d900378b596c243da8e122c273e62":
        problems.append("frozen_kernel_pins")
    baseline = M4 / "baseline"
    imm = json.loads((baseline / "immutable_pins.json").read_text(encoding="utf-8"))
    imm_res = {raw: sha256(PROJECT / norm(raw)) == expected for raw, expected in imm.items()}
    tracked = json.loads((baseline / "tracked_files_before.json").read_text(encoding="utf-8"))
    tracked_changed = [norm(k) for k, v in tracked.items() if not (PROJECT / norm(k)).is_file() or sha256(PROJECT / norm(k)) != v]
    production = json.loads((baseline / "production_files_before.json").read_text(encoding="utf-8"))
    prod_res = {}
    for raw, before in production.items():
        p = Path(raw)
        now = {"exists": p.exists()}
        if p.exists():
            st = p.stat()
            now.update({"size": st.st_size, "mtime_ns": st.st_mtime_ns, "sha256": sha256(p)})
        prod_res[norm(raw)] = {"unchanged": now["exists"] == before["exists"] and all(now.get(k) == before.get(k) for k in ("size", "mtime_ns", "sha256") if k in before), "after": now}
    status_lines = git("status", "--porcelain").splitlines()
    result = {
        "schema": "m4.claude_02a.verification.v1",
        "label": label,
        "task_id": "M4-02A-PORTFOLIO-LEDGER-20260912",
        "verified_at_utc": datetime.now(timezone.utc).isoformat(),
        "task_file": {"path": TASK_FILE, "sha256": task_sha, "ok": task_sha == TASK_SHA},
        "execution_freeze": {"path": "claude methods/_m4_20260912/execution_freeze.json", "sha256": freeze_sha, "ok": freeze_sha == FREEZE_SHA,
                             "integration_revision": freeze["integration_revision"], "policy_hash": freeze["policy_hash"],
                             "pins_total": len(pins), "pins_ok": sum(1 for v in pins.values() if v["ok"]), "pins": pins},
        "frozen_kernel": {"backend/app/research/m4_execution.py": kernel_sha, "backend/tests/test_m4_execution.py": tests_sha, "ok": kernel_sha == KERNEL_SHA and tests_sha == KERNEL_TESTS_SHA},
        "git": {"branch": git("branch", "--show-current").strip(), "head": git("rev-parse", "HEAD").strip(),
                "status_modified": sorted(l for l in status_lines if not l.startswith("?? ")), "status_untracked_count": sum(1 for l in status_lines if l.startswith("?? ")),
                "staged": git("diff", "--cached", "--name-only").strip().splitlines()},
        "baseline": {"immutable_pins": {"count": len(imm_res), "unchanged": sum(imm_res.values()), "changed": [k for k, v in imm_res.items() if not v]},
                     "tracked_files": {"count": len(tracked), "changed_or_missing": tracked_changed},
                     "production_file_positions": {"count": len(prod_res), "unchanged": sum(1 for v in prod_res.values() if v["unchanged"]),
                                                   "changed": [k for k, v in prod_res.items() if not v["unchanged"]], "detail": prod_res,
                                                   "note": "byte hashing / stat only; no SQLite connection or SQL query"}},
        "problems": problems,
        "ok": not problems and not tracked_changed and all(imm_res.values()),
    }
    out = HERE / "evidence"
    out.mkdir(exist_ok=True)
    (out / f"{label}_verification.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"label": label, "ok": result["ok"], "problems": problems, "freeze_pins_ok": f"{result['execution_freeze']['pins_ok']}/{result['execution_freeze']['pins_total']}",
                      "immutable_pins": result["baseline"]["immutable_pins"]["unchanged"], "tracked_changed": tracked_changed,
                      "production_unchanged": result["baseline"]["production_file_positions"]["unchanged"], "head": result["git"]["head"], "branch": result["git"]["branch"],
                      "modified": len(result["git"]["status_modified"]), "staged": result["git"]["staged"]}, ensure_ascii=False, indent=1))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "prework"))
