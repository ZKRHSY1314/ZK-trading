"""Build the claude_01_r2 artefacts for M3-01-R2: LABEL_POLICY.json, synthetic_examples.json, artifact_manifest.json.

Loads the revised pure module and the synthetic fixtures by file path (no ``app``
package, no SQLite, no network, no subprocess).  Deterministic: no wall clock, no
randomness.  Run after the test transcripts have been written so that they are pinned.
Never rerun claude_01/build_artifacts.py: the first delivery stays frozen.

    D:/codex-A股交易/backend/.venv/Scripts/python.exe -B -X utf8 "claude methods/_m3_20260910/claude_01_r2/build_artifacts.py"
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
    "claude methods/M3_01_CODEX_REVIEW_20260910.md",
    "claude methods/M3_01_R2_CLAUDE_TASK_20260910.md",
    "claude methods/M3_01_LABEL_SPEC_CLAUDE_TASK_20260910.md",
    "claude methods/M2_FINAL_ACCEPTANCE_20260910.md",
    "AGENTS.md", "CODEX_CLAUDE_COLLABORATION.md",
    "claude methods/_m3_20260910/codex/test_independent_contract.py",
    "claude methods/_m3_20260910/codex/review_01_independent_tests/execution.json",
    "claude methods/_m3_20260910/codex/review_01_independent_tests/stderr.txt",
    "claude methods/_m3_20260910/codex/review_01_input/receipt.json",
    "claude methods/_m3_20260910/codex/run_offline_review.py",
    "claude methods/_m3_20260910/codex/STATIC_RISKS.md",
    "claude methods/_m3_20260910/claude_01/artifact_manifest.json",
    "claude methods/_m3_20260910/claude_01/LABEL_POLICY.md",
    "claude methods/_m2_ths_v2_claude_review_20260910/r06_basis_unit_controls.json",
    "claude methods/_m1_closure/pilot_symbols.csv",
]
PRESERVED_ORIGINALS = {
    "claude methods/_m3_20260910/codex/review_01_input/files/backend/app/research/m3_labels.py": "6a0590cf2dd9b7acbc9421c818e558e24d6c2877175c8a903d47dab375a99065",
    "claude methods/_m3_20260910/codex/review_01_input/files/backend/tests/test_m3_labels.py": "efa2e21cb70b70fbd0c39e3e4908a7a24f9837bb45889858979f6a99f09f0ab2",
    "claude methods/_m3_20260910/claude_01/artifact_manifest.json": "428bb425661239de755dca6ac49e5128a923f8b90ebdb19e1c85d404e67a5147",
}


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
    t = load(TESTS, "m3_labels_tests_fixtures_r2")
    m = t.m
    assert Path(m.__file__).resolve() == MODULE.resolve()
    assert m.POLICY_VERSION == "0.2.0-draft"

    dump(HERE / "LABEL_POLICY.json", m.policy_document())

    dates, closes, vols = t.sequence_positive_then_failed()
    rows = t.bars_from(t.SYN_A, dates, closes, vols)
    bench = t.bench_for(dates)
    req = t.request_for(t.SYN_A, rows, dates[-1], benchmark_symbol=t.SYN_BENCH, benchmark_observations=bench,
                        universe_coverage_on_decision_date=t.coverage())
    series = m.label_series(req, dates[249:])
    episodes = m.build_episodes(series, t.CAL)
    picks = {}
    for ep in episodes:
        picks.setdefault(ep["phase"], ep["start"])
    example_records = {phase: next(o for o in series if o["cutoff"]["decision_date"] == d) for phase, d in picks.items()}

    d = dates[295]
    positive = next(o for o in series if o["cutoff"]["decision_date"] == d)
    pool = []
    for k in range(6):
        sym = f"SYN00001{k}"
        _, pc, pv = t.sequence_distribution(seed=11 + k, n_rise=295)
        prows = t.bars_from(sym, dates[:296], [c * (1.0 + 0.03 * k) for c in pc], pv, upper_shadow=0.04)
        pool.append(m.generate_labels(t.request_for(sym, prows, d, benchmark_symbol=t.SYN_BENCH, benchmark_observations=bench,
                                                    universe_coverage_on_decision_date=t.coverage())))
    match = m.match_controls(positive, pool) if positive["labels"]["selection"]["label"] == "candidate" else None
    duplicates_demo = m.match_controls(positive, [pool[0]] * 5) if match else None

    r1 = t.syn_review(positive, "codex_synthetic_demo", "positive")
    r2 = t.syn_review(positive, "claude_synthetic_demo", "ambiguous", when="2026-09-11T03:00:00+00:00")
    disputed = m.attach_review(m.attach_review(positive, r1), r2)
    later = t.cutoff_for(dates[330])
    outcome = m.annotate_outcome(positive, rows, later, t.CAL)
    counts = m.library_counts([disputed] + pool, [match] if match else [], t.CAL)
    verified_pos = m.PositionState(t.SYN_A, m.POLICY_HASH, dates[295], dates[296], float(rows[296].open),
                                   evidence_ref="SYNTHETIC_ONLY:position", available_at=t.EARLY)
    hold_verified = m.generate_labels(t.request_for(t.SYN_A, rows, dates[298], position_state=verified_pos, security=t.verified_context()))
    hold_unknown = m.generate_labels(t.request_for(t.SYN_A, rows, dates[298], position_state=verified_pos))
    missing_day = m.generate_labels(t.request_for(t.SYN_A, rows[:295], d))

    examples = {
        "schema": "m3.claude_01_r2.synthetic_examples.v1",
        "synthetic": True,
        "counts_toward_case_library": False,
        "note": "All symbols are SYN######, all evidence refs SYNTHETIC_ONLY, the calendar is a declared synthetic fixture and reviewer identities are demo strings. These records demonstrate the v2 output contract; they are not cases, not reviews and never count.",
        "policy_hash": m.POLICY_HASH,
        "policy_version": m.POLICY_VERSION,
        "producer_sha256": m.producer_sha256(),
        "calendar": t.CAL.record(),
        "episode_path": [{k: ep[k] for k in ("phase", "kind", "start", "end", "sessions", "selection_at_start", "selection_at_end", "eligibility_changes",
                                            "min_duration_established_at", "closed_reason", "status", "meets_min_sessions")} for ep in episodes],
        "dependence_groups_synthetic_arithmetic_only": m.dependence_groups(episodes, include_synthetic=True),
        "example_records_by_phase": example_records,
        "matching_result": match,
        "duplicate_controls_collapse_demo": {k: duplicates_demo[k] for k in ("control_count", "identical_duplicates_collapsed", "unmatched")} if duplicates_demo else None,
        "control_reuse": m.control_reuse_counts([match]) if match else None,
        "disputed_review_ledger_demo": disputed["review_ledger"],
        "record_hash_unchanged_by_review": disputed["record_hash"] == positive["record_hash"],
        "library_counts_demo": counts,
        "position_event_verified_basis": hold_verified["labels"]["position_event"],
        "position_event_unknown_actions": hold_unknown["labels"]["position_event"],
        "missing_decision_session_record": {"current_state": missing_day["current_state"], "selection": missing_day["labels"]["selection"],
                                            "phase_reasons": missing_day["labels"]["phase"]["reasons"]},
        "later_known_outcome_demo": outcome,
        "split_roles": {x: m.split_role(x) for x in ("2023-09-04", "2025-03-31", "2025-04-01", "2025-12-31", "2026-01-01", "2026-09-04")},
        "purpose_allowlist": list(m.PURPOSES),
        "seed_context": m.seed_context(),
    }
    dump(HERE / "synthetic_examples.json", examples)

    manifest = {
        "schema": "m3.claude_01_r2.artifact_manifest.v1",
        "task_id": "M3-01-R2-CONTRACT-FIX-20260910",
        "status": "ready_for_review",
        "owner": "Claude (existing ZK-trading / Fable 5.1 project advice fork)",
        "accepted_by_codex": False,
        "supersedes": {"manifest_sha256": "428bb425661239de755dca6ac49e5128a923f8b90ebdb19e1c85d404e67a5147", **m.SUPERSEDES},
        "policy": {"namespace": m.NAMESPACE, "policy_id": m.POLICY_ID, "policy_version": m.POLICY_VERSION, "policy_hash": m.POLICY_HASH,
                   "output_schema": m.OUTPUT_SCHEMA},
        "producer_sha256": m.producer_sha256(),
        "written": {},
        "sources_read": {},
        "preserved_originals": {},
        "safety": {"review_only": True, "live_trading_enabled": False, "sqlite_opened": [], "network_requests": 0, "subprocesses": 0,
                   "real_corpus_rows_read": 0, "synthetic_only": True, "git_mutations": 0, "py_compile_used": False},
    }
    for rel in ("backend/app/research/m3_labels.py", "backend/tests/test_m3_labels.py"):
        p = PROJECT / rel
        manifest["written"][rel] = {"sha256": sha(p), "bytes": p.stat().st_size, "supersedes_first_version": True}
    for p in sorted(HERE.rglob("*")):
        if p.is_file() and p.name != "artifact_manifest.json":
            rel = p.relative_to(PROJECT).as_posix()
            manifest["written"][rel] = {"sha256": sha(p), "bytes": p.stat().st_size}
    for rel in SOURCES_READ:
        p = PROJECT / rel
        manifest["sources_read"][rel] = {"sha256": sha(p), "bytes": p.stat().st_size} if p.is_file() else {"missing": True}
    for rel, expected in PRESERVED_ORIGINALS.items():
        p = PROJECT / rel
        actual = sha(p) if p.is_file() else None
        manifest["preserved_originals"][rel] = {"sha256": actual, "expected": expected, "match": actual == expected}
    dump(HERE / "artifact_manifest.json", manifest)
    print("policy_hash", m.POLICY_HASH)
    print("producer_sha256", m.producer_sha256())
    print("episodes", [(e["phase"], e["start"], e["end"], e["selection_at_end"]) for e in episodes])
    print("match", None if match is None else (match["control_count"], match["unmatched"]))
    print("counts", {k: counts[k] for k in ("records_total", "positively_reviewed_episodes", "qualified_positives", "effective_dependence_groups")})
    print("preserved", all(v["match"] for v in manifest["preserved_originals"].values()))
    print("manifest_sha256", sha(HERE / "artifact_manifest.json"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
