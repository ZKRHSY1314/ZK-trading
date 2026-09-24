"""Pre-work / post-work / final preservation verification for M4-03B (claude_03b).

Byte reads only (no SQLite connection): the task file hash, the four M4 freezes (execution 49, portfolio 74, risk 82,
historical-qualification 49 pins), the M4 baseline (42 immutable pins, 316 tracked files, 16 production file positions
by stat/hash), the accepted M4-03A proposal / mapping, every non-SQL input of the replay (qualification bundle, metadata
index, calendar, pilot CSV, prior development audit) and the two candidate stores (hash, size, mtime_ns, sidecar
absence).  PLAN.md and coordination_state.json are Codex-owned mutable records: their hashes are recorded, never
required to match.  Writes ONLY claude_03b/evidence/<label>_verification.json.

    backend/.venv/Scripts/python.exe -B -X utf8 "claude methods/_m4_20260912/claude_03b/verify_baseline.py" prework
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
TASK_FILE = "claude methods/M4_03B_DEVELOPMENT_REPLAY_CLAUDE_TASK_20260912.md"
TASK_SHA = "8290d8c862dfa507c97e501cdfea8df79de65af729df72c42970727456d00816"
FREEZES = {
    "execution_freeze.json": ("8a74233f21740f365b1c286d5c735dd4ead42c2ad00016ac9823e6ee5814e3f3", 49),
    "portfolio_freeze.json": ("e6fc61de18184a7cbbb3756a02fc8697e7c59f14ef836085b7a1b0c46fa3d281", 74),
    "risk_freeze.json": ("371505a47187c680bad2439abf656a5fa62bd707c5a8383dcf8c614f85186e10", 82),
    "historical_qualification_freeze.json": ("bde085d646b285e2fd2375c464fbab90fab360a3995c814eb4434702f559d3b2", 49),
}
M2_RUN = "claude methods/_m2_codex_implementation_20260910/staging_runs/ths_v2_20260910_041710_97ef9c09/run_ths_v2_20260910_041710_97ef9c09"
INPUT_PINS = {
    "claude methods/M4_03A_CODEX_ACCEPTANCE_20260912.md": "81d2f9d33e0684cb3ec3a58fc721ede94513d17e5cca1f907b03806406e64a4f",
    "claude methods/_m4_20260912/claude_03a/NEXT_READ_PROPOSAL.md": "b7c9c3346341ba38b597c36d18f80f34ed0ab532168ea45d22283555731b5203",
    "claude methods/_m4_20260912/claude_03a/proposal_mapping.py": "276cb037575f8d05a313b3266ecad46008e015d17c99ca98786c403d0c3e70de",
    "claude methods/_m4_20260912/claude_03a/qualification.json": "0902992ff4a375ee8bb9d099e6071d476883d40bc6dc544a84a355a5fed0ae1b",
    "claude methods/_m2_codex_implementation_20260910/qualification_v2_reviewed.json": "992bd79ce9d2e38d1a0a8ae2f9890cd26daebcd3d2ab664d5caab171ec3e0f37",
    "claude methods/_m3_20260910/codex/metadata_index_01/index.json": "14f1bad7d393b4e15bf73111a9d96a78c8b156784f9ccbb084d6b606d3a152e9",
    "backend/.venv/Lib/site-packages/akshare/file_fold/calendar.json": "f1f1ce33c5cceb5c530c3271fc951405cb5624d2f30becec85dc7a85fd47e656",
    "claude methods/_m1_closure/pilot_symbols.csv": "97e251ae84fc927486127a96b4966ed8fc59fac0b744b7d6f186b2b1548886fe",
    "claude methods/_m3_20260910/codex/development_input_audit_01/result.json": "dd3ac6ffde13ba0127a39163d23e3cebb148ca9a93f90d25c17cd4a22402d157",
    "backend/app/research/m4_execution.py": "83a28b543b9ecc5edf8080ea39fa388f8b2bb5a8724ef68b4b532041216678c7",
    "backend/app/research/m4_portfolio.py": "2b3eec837e4c3603661371fb94e8d942f45c9bfadbf018fc5d6ebee6fadb5360",
    "backend/app/research/m4_risk.py": "faec444ee98ed6ee8c20da217a6cb29ced53d7de2ceae1e2198b1cbc73b665f2",
}
DATABASES = {
    f"{M2_RUN}/trading.sqlite3": ("c0b26660ab903541e7e213ee312c565be73547bb3cc8c142486999717e3edeca", 38969344),
    f"{M2_RUN}/history.sqlite3": ("eda17434ab67496c33eed275b35045c140bad72802b4dcbf981ff22422c53003", 10604544),
}
MUTABLE_CODEX = ["claude methods/_m4_20260912/PLAN.md", "claude methods/_m4_20260912/coordination_state.json"]


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


def database_state(rel: str) -> dict:
    p = PROJECT / rel
    st = p.stat()
    return {"path": rel, "resolved": str(p.resolve()), "sha256": sha256(p), "bytes": st.st_size, "mtime_ns": st.st_mtime_ns,
            "sidecars_present": {s: (PROJECT / (rel + s)).exists() for s in ("-wal", "-shm", "-journal")}}


def verify(label: str) -> dict:
    problems: list[str] = []
    task_sha = sha256(PROJECT / TASK_FILE)
    if task_sha != TASK_SHA:
        problems.append(f"task_file_sha:{task_sha}")
    freezes = {}
    for name, (expected, pin_count) in FREEZES.items():
        path = M4 / name
        actual = sha256(path)
        doc = json.loads(path.read_text(encoding="utf-8"))
        pins = {}
        for rel, meta in doc["pins"].items():
            p = PROJECT / rel
            got = sha256(p) if p.is_file() else None
            size = p.stat().st_size if p.is_file() else None
            ok = got == meta["sha256"] and size == meta["bytes"]
            pins[rel] = {"expected": meta["sha256"], "actual": got, "bytes": size, "ok": ok}
            if not ok:
                problems.append(f"{name}:pin:{rel}")
        if actual != expected:
            problems.append(f"{name}:sha:{actual}")
        if len(pins) != pin_count:
            problems.append(f"{name}:pin_count:{len(pins)}")
        flags = {k: doc.get(k) for k in ("M4_complete", "review_only", "live_trading_enabled", "training_eligible", "strict_pit", "M3_complete", "verdict")}
        freezes[name] = {"path": f"claude methods/_m4_20260912/{name}", "sha256": actual, "ok": actual == expected, "policy_hash": doc.get("policy_hash"),
                         "flags": flags, "pins_total": len(pins), "pins_ok": sum(1 for v in pins.values() if v["ok"]), "pins": pins}
    inputs = {}
    for rel, expected in INPUT_PINS.items():
        p = PROJECT / rel
        got = sha256(p) if p.is_file() else None
        inputs[rel] = {"expected": expected, "actual": got, "bytes": p.stat().st_size if p.is_file() else None, "ok": got == expected}
        if got != expected:
            problems.append(f"input_pin:{rel}")
    databases = {}
    for rel, (expected, size) in DATABASES.items():
        state = database_state(rel)
        ok = state["sha256"] == expected and state["bytes"] == size and not any(state["sidecars_present"].values())
        databases[rel] = {**state, "expected": expected, "expected_bytes": size, "ok": ok, "access": "byte hash + stat only in this script"}
        if not ok:
            problems.append(f"database:{rel}")
    mutable = {rel: {"sha256": sha256(PROJECT / rel), "bytes": (PROJECT / rel).stat().st_size, "note": "Codex-owned mutable record; recorded, not required to match"} for rel in MUTABLE_CODEX}
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
        "schema": "m4.claude_03b.verification.v1", "label": label, "task_id": "M4-03B-DEVELOPMENT-REPLAY-20260912",
        "verified_at_utc": datetime.now(timezone.utc).isoformat(),
        "task_file": {"path": TASK_FILE, "sha256": task_sha, "ok": task_sha == TASK_SHA},
        "freezes": freezes, "inputs": inputs, "candidate_databases": databases, "codex_mutable_records": mutable,
        "git": {"branch": git("branch", "--show-current").strip(), "head": git("rev-parse", "HEAD").strip(),
                "status_modified": sorted(l for l in status_lines if not l.startswith("?? ")), "status_untracked_count": sum(1 for l in status_lines if l.startswith("?? ")),
                "staged": git("diff", "--cached", "--name-only").strip().splitlines()},
        "baseline": {"immutable_pins": {"count": len(imm_res), "unchanged": sum(imm_res.values()), "changed": [k for k, v in imm_res.items() if not v]},
                     "tracked_files": {"count": len(tracked), "changed_or_missing": tracked_changed},
                     "production_file_positions": {"count": len(prod_res), "unchanged": sum(1 for v in prod_res.values() if v["unchanged"]),
                                                   "changed": [k for k, v in prod_res.items() if not v["unchanged"]], "detail": prod_res,
                                                   "note": "byte hashing / stat only; no SQLite connection or SQL query"}},
        "safety": {"sqlite_connections_in_this_script": 0, "network_requests": 0, "review_only": True, "live_trading_enabled": False, "training_eligible": False, "strict_pit": False, "M4_complete": False},
        "problems": problems, "ok": not problems and not tracked_changed and all(imm_res.values()),
    }
    return result


def main(label: str) -> int:
    result = verify(label)
    out = HERE / "evidence"
    out.mkdir(exist_ok=True)
    (out / f"{label}_verification.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"label": label, "ok": result["ok"], "problems": result["problems"], "freezes": {k: f"{v['pins_ok']}/{v['pins_total']}" for k, v in result["freezes"].items()},
                      "inputs_ok": f"{sum(1 for v in result['inputs'].values() if v['ok'])}/{len(result['inputs'])}", "databases_ok": all(v["ok"] for v in result["candidate_databases"].values()),
                      "immutable_pins": result["baseline"]["immutable_pins"]["unchanged"], "tracked_changed": result["baseline"]["tracked_files"]["changed_or_missing"],
                      "production_unchanged": result["baseline"]["production_file_positions"]["unchanged"], "head": result["git"]["head"], "branch": result["git"]["branch"],
                      "modified": len(result["git"]["status_modified"]), "staged": result["git"]["staged"]}, ensure_ascii=False, indent=1))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "prework"))
