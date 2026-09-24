"""M3-02 bounded real development run over the exact frozen M2 candidate stores.

Read-only: the only SQLite connections are the two hash-pinned candidate files opened by
``m3_frozen_reader`` (mode=ro&immutable=1, query_only, authorizer).  Real price consumption
is bounded to trade_date <= 2025-03-31; decisions 2023-09-04 .. 2025-03-31.  Refuses to
overwrite an existing run directory.  Writes only below claude_02/runs/<run_name>/.

    D:/codex-A股交易/backend/.venv/Scripts/python.exe -B -X utf8 "claude methods/_m3_20260910/claude_02/run_real_development.py" dev_run_01
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[2]
READER = PROJECT / "backend" / "app" / "research" / "m3_frozen_reader.py"
LABELS = PROJECT / "backend" / "app" / "research" / "m3_labels.py"
FROZEN_INPUT_FILES = {
    "policy_freeze": (PROJECT / "claude methods" / "_m3_20260910" / "policy_freeze.json", "925ae86f772908babef6bc6a08a1ace58c2db7a5e71c7f97af8ad52f2c7a891f"),
    "labels_module": (LABELS, "e20eb21cdea032ced319a8f45a34cdeb03fd4d8b357ac31403306fa73b225393"),
    "labels_tests": (PROJECT / "backend" / "tests" / "test_m3_labels.py", "41eba60b21b507250f9a9a4f359fdc330232306c61b535f3d82db18ba9e45180"),
}


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    run_name = sys.argv[1] if len(sys.argv) > 1 else "dev_run_01"
    out = HERE / "runs" / run_name
    if out.exists():
        raise SystemExit(f"refusing to overwrite existing run directory: {out}")
    spec = importlib.util.spec_from_file_location("m3_frozen_reader_real_run", READER)
    r = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = r
    spec.loader.exec_module(r)
    started = datetime.now(timezone.utc).isoformat()
    pins_before = {name: {"path": str(path), "sha256": sha(path), "expected": expected, "match": sha(path) == expected}
                   for name, (path, expected) in FROZEN_INPUT_FILES.items()}
    if not all(v["match"] for v in pins_before.values()):
        raise SystemExit(f"frozen input pins do not match: {pins_before}")
    sources_before = {name: r.verify_source(spec_) for name, spec_ in r._specs(r.FROZEN_M2).items()}
    t0 = time.perf_counter()
    receipt = r.run_development(out, r.FROZEN_M2, now_utc=started)
    elapsed = time.perf_counter() - t0
    sources_after = {name: r.verify_source(spec_) for name, spec_ in r._specs(r.FROZEN_M2).items()}
    pins_after = {name: {"path": str(path), "sha256": sha(path), "expected": expected, "match": sha(path) == expected}
                  for name, (path, expected) in FROZEN_INPUT_FILES.items()}
    transcript = {
        "schema": "m3.claude_02.real_run_transcript.v1", "run_name": run_name, "started_at_utc": started,
        "finished_at_utc": datetime.now(timezone.utc).isoformat(), "elapsed_seconds": round(elapsed, 3),
        "command": f'{sys.executable} -B -X utf8 "{Path(__file__)}" {run_name}', "python": sys.version.split()[0],
        "reader_sha256": sha(READER), "status": receipt["status"], "frozen_pins_before": pins_before, "frozen_pins_after": pins_after,
        "sources_before": sources_before, "sources_after": sources_after, "sources_unchanged": sources_before == sources_after,
        "connections": receipt["read_log"]["connections"], "denied_actions": receipt["read_log"]["denied_actions"],
        "statement_count": receipt["read_log"]["statement_count"], "distinct_statements": receipt["read_log"]["distinct_statements"],
        "reconciliation_counts": receipt.get("reconciliation_counts"), "structural_problems": receipt.get("structural_problems"),
        "records_generated": receipt.get("records_generated"), "waterfall": receipt.get("waterfall"),
        "run_receipt_sha256": receipt.get("run_receipt_sha256"), "production_sqlite_connections": 0, "network_requests": 0,
    }
    data = (json.dumps(transcript, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    (out / "real_run_transcript.json").write_bytes(data)
    print(json.dumps({"status": receipt["status"], "elapsed_seconds": round(elapsed, 1), "records": receipt.get("records_generated"),
                      "sources_unchanged": sources_before == sources_after, "denied": receipt["read_log"]["denied_actions"],
                      "waterfall": {k: v for k, v in (receipt.get("waterfall") or {}).items() if not isinstance(v, dict)}}, ensure_ascii=False, indent=1))
    return 0 if receipt["status"] == "completed" else 1


if __name__ == "__main__":
    sys.exit(main())
