"""Build the claude_01 artefacts for M3-01: LABEL_POLICY.json, synthetic_examples.json, artifact_manifest.json.

Loads the pure module and the synthetic fixtures by file path (no ``app`` package,
no SQLite, no network).  Deterministic: no wall clock, no randomness.  Run after the
test transcript has been written so that it can be pinned.

    D:/codex-A股交易/backend/.venv/Scripts/python.exe -B -X utf8 "claude methods/_m3_20260910/claude_01/build_artifacts.py"
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from datetime import timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[2]
MODULE = PROJECT / "backend" / "app" / "research" / "m3_labels.py"
TESTS = PROJECT / "backend" / "tests" / "test_m3_labels.py"

SOURCES_READ = [
    "claude methods/M3_01_LABEL_SPEC_CLAUDE_TASK_20260910.md",
    "claude methods/M2_FINAL_ACCEPTANCE_20260910.md",
    "claude methods/THREE_YEAR_RESEARCH_EXECUTION_GOAL.md",
    "AGENTS.md", "CODEX_CLAUDE_COLLABORATION.md", "CLAUDE.md",
    "claude methods/_m3_20260910/PLAN.md",
    "claude methods/_m3_20260910/coordination_state.json",
    "claude methods/_m3_20260910/baseline/baseline.json",
    "claude methods/_m3_20260910/codex/bootstrap.py",
    "backend/app/learning/phase_replay.py", "backend/app/learning/structure_scoring.py",
    "backend/app/learning/phase_matcher.py", "backend/app/agent_control/outcome_labeling.py",
    "backend/app/strategies/dengzhan.py", "backend/app/research/offhour.py", "backend/app/data/price_limits.py",
    "backend/app/research/__init__.py", "backend/tests/conftest.py", "backend/pyproject.toml",
    "claude methods/_m1_closure/pilot_symbols.csv",
    "claude methods/_m2_codex_implementation_20260910/staging_runs/ths_v2_20260910_041710_97ef9c09/run_ths_v2_20260910_041710_97ef9c09/contract_v2.json",
    "claude methods/_m2_ths_v2_claude_review_20260910/r02_db_schema.json",
    "claude methods/_m2_codex_implementation_20260910/contract_v2.py",
]


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def dump(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def main() -> int:
    t = load(TESTS, "m3_labels_tests_fixtures")
    m = t.m  # the module instance the fixtures were built against (same Observation class)
    assert Path(m.__file__).resolve() == MODULE.resolve()

    dump(HERE / "LABEL_POLICY.json", m.policy_document())

    # synthetic examples: positive -> markup -> failed sequence, a distribution control, one matching result
    dates, closes, vols = t.sequence_positive_then_failed()
    rows = t.bars_from(t.SYN_A, dates, closes, vols)
    bench = t.bars_from(t.SYN_BENCH, dates, [3000.0 * 1.002 ** i for i in range(len(dates))], [10_000_000] * len(dates))
    series = m.label_series(t.request_for(t.SYN_A, rows, dates[-1], benchmark_symbol=t.SYN_BENCH, benchmark_observations=bench), dates[249:])
    episodes = m.build_episodes(series)
    picks = {}
    for ep in episodes:
        picks.setdefault(ep["phase"], ep["start"])
    example_records = {phase: next(o for o in series if o["cutoff"]["decision_date"] == d) for phase, d in picks.items()}

    ddates, dcloses, dvols = t.sequence_distribution(seed=11, n_rise=295)
    drows = t.bars_from("SYN000010", dates[:296], dcloses, dvols, upper_shadow=0.04)
    dist = m.generate_labels(t.request_for("SYN000010", drows, dates[295], benchmark_symbol=t.SYN_BENCH, benchmark_observations=bench))

    positive = next((o for o in series if o["labels"]["selection"]["label"] == "candidate"), None)
    session_index = {d: i for i, d in enumerate(dates)}
    pool = []
    for k in range(6):
        sym = f"SYN00001{k}"
        offset = (k % 3) * 2
        n = 296 - offset
        _, pc, pv = t.sequence_distribution(seed=11 + k, n_rise=n - 1)
        prows = t.bars_from(sym, dates[:n], [c * (1.0 + 0.03 * k) for c in pc], pv, upper_shadow=0.04)
        pool.append(m.generate_labels(t.request_for(sym, prows, dates[n - 1], benchmark_symbol=t.SYN_BENCH, benchmark_observations=bench)))
    positive_at_295 = next((o for o in series if o["cutoff"]["decision_date"] == dates[295]), None)
    match = m.match_controls(positive_at_295, pool, session_index) if positive_at_295 and positive_at_295["labels"]["selection"]["label"] == "candidate" else None

    r1 = m.ReviewRecord("codex", "agent", "2026-09-11T02:00:00+00:00", "positive", ("syn:evidence:a",), "synthetic demonstration only")
    r2 = m.ReviewRecord("claude", "agent", "2026-09-11T03:00:00+00:00", "ambiguous", ("syn:evidence:b",), "synthetic demonstration only")
    disputed = m.attach_review(m.attach_review(positive_at_295, r1), r2) if positive_at_295 else None
    later = m.Cutoff(dates[330], (m.close_time(dates[330]) + timedelta(hours=4)).isoformat(), m.MODE_STRICT)
    outcome = m.annotate_outcome(positive_at_295, rows, later) if positive_at_295 else None

    examples = {
        "schema": "m3.claude_01.synthetic_examples.v1",
        "synthetic": True,
        "counts_toward_case_library": False,
        "note": "All symbols are SYN######. These records demonstrate the output contract; they are not cases and never count.",
        "policy_hash": m.POLICY_HASH,
        "producer_sha256": m.producer_sha256(),
        "episode_path": [{k: ep[k] for k in ("phase", "start", "end", "sessions", "selection_at_end", "open_at_last_cutoff", "meets_min_sessions")} for ep in episodes],
        "effective_counts": m.effective_decision_dates(episodes, session_index=session_index),
        "example_records_by_phase": example_records,
        "distribution_control_record": dist,
        "matching_result": match,
        "control_reuse": m.control_reuse_counts([match]) if match else None,
        "disputed_review_demo": disputed["review"] if disputed else None,
        "later_known_outcome_demo": outcome,
        "split_roles": {d: m.split_role(d) for d in ("2023-09-04", "2025-03-31", "2025-04-01", "2025-12-31", "2026-01-01", "2026-09-04")},
        "seed_context": m.seed_context(),
    }
    dump(HERE / "synthetic_examples.json", examples)

    manifest = {
        "schema": "m3.claude_01.artifact_manifest.v1",
        "task_id": "M3-01-LABEL-SPEC-20260910",
        "status": "ready_for_review",
        "owner": "Claude (existing ZK-trading / Fable 5.1 project advice fork)",
        "accepted_by_codex": False,
        "policy": {"namespace": m.NAMESPACE, "policy_id": m.POLICY_ID, "policy_version": m.POLICY_VERSION, "policy_hash": m.POLICY_HASH},
        "producer_sha256": m.producer_sha256(),
        "written": {},
        "sources_read": {},
        "safety": {"review_only": True, "live_trading_enabled": False, "sqlite_opened": [], "network_requests": 0,
                   "real_corpus_rows_read": 0, "synthetic_only": True, "git_mutations": 0},
    }
    for rel in ("backend/app/research/m3_labels.py", "backend/tests/test_m3_labels.py"):
        p = PROJECT / rel
        manifest["written"][rel] = {"sha256": sha(p), "bytes": p.stat().st_size}
    for p in sorted(HERE.iterdir()):
        if p.is_file() and p.name != "artifact_manifest.json":
            manifest["written"][f"claude methods/_m3_20260910/claude_01/{p.name}"] = {"sha256": sha(p), "bytes": p.stat().st_size}
    for rel in SOURCES_READ:
        p = PROJECT / rel
        manifest["sources_read"][rel] = {"sha256": sha(p), "bytes": p.stat().st_size} if p.is_file() else {"missing": True}
    dump(HERE / "artifact_manifest.json", manifest)
    print("policy_hash", m.POLICY_HASH)
    print("producer_sha256", m.producer_sha256())
    print("episodes", [(e["phase"], e["start"], e["end"]) for e in episodes])
    print("match", None if match is None else (match["control_count"], match["unmatched"]))
    print("manifest_sha256", sha(HERE / "artifact_manifest.json"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
