"""Build the claude_01_r3 artefacts for M3-01-R3: LABEL_POLICY.json, synthetic_examples.json, artifact_manifest.json.

Loads the revised pure module and the synthetic fixtures by file path (no ``app``
package, no SQLite, no network, no subprocess).  Deterministic: no wall clock, no
randomness.  Run after the test transcripts have been written so that they are pinned.
Never rerun claude_01/ or claude_01_r2/ builders: earlier deliveries stay frozen.

    D:/codex-A股交易/backend/.venv/Scripts/python.exe -B -X utf8 "claude methods/_m3_20260910/claude_01_r3/build_artifacts.py"
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from dataclasses import replace
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[2]
MODULE = PROJECT / "backend" / "app" / "research" / "m3_labels.py"
TESTS = PROJECT / "backend" / "tests" / "test_m3_labels.py"

SOURCES_READ = [
    "claude methods/M3_01_R2_CODEX_REVIEW_20260910.md",
    "claude methods/M3_01_R3_CLAUDE_TASK_20260910.md",
    "claude methods/M3_01_R2_CLAUDE_TASK_20260910.md",
    "claude methods/M3_01_CODEX_REVIEW_20260910.md",
    "claude methods/M3_01_LABEL_SPEC_CLAUDE_TASK_20260910.md",
    "claude methods/THREE_YEAR_RESEARCH_EXECUTION_GOAL.md",
    "AGENTS.md", "CODEX_CLAUDE_COLLABORATION.md",
    "claude methods/_m3_20260910/codex/R3_BENCHMARK_INTEGRATION_SUPPLEMENT.md",
    "claude methods/_m3_20260910/codex/frozen_r2_benchmark_probe.json",
    "claude methods/_m3_20260910/codex/probe_frozen_r2_benchmark.py",
    "claude methods/_m3_20260910/codex/R3_IN_PROGRESS_FEEDBACK.md",
    "claude methods/_m3_20260910/codex/test_independent_r3.py",
    "claude methods/_m3_20260910/codex/run_r3_offline_review.py",
    "claude methods/_m3_20260910/codex/r3_working_consumer_tests_01/execution.json",
    "claude methods/_m3_20260910/codex/r3_working_consumer_tests_01/stderr.txt",
    "claude methods/_m3_20260910/codex/test_independent_r2.py",
    "claude methods/_m3_20260910/codex/test_feature_oracle.py",
    "claude methods/_m3_20260910/codex/test_independent_contract.py",
    "claude methods/_m3_20260910/codex/run_offline_review.py",
    "claude methods/_m3_20260910/codex/review_02_independent_tests/execution.json",
    "claude methods/_m3_20260910/codex/review_02_independent_tests/stderr.txt",
    "claude methods/_m3_20260910/codex/review_02_input/receipt.json",
    "claude methods/_m3_20260910/codex/R2_PREVIEW_FINDINGS.md",
    "claude methods/_m3_20260910/claude_01_r2/artifact_manifest.json",
    "claude methods/_m3_20260910/claude_01_r2/LABEL_POLICY.md",
    "claude methods/_m3_20260910/claude_01/artifact_manifest.json",
    "claude methods/_m2_codex_implementation_20260910/qualification_v2_reviewed.json",
    "claude methods/_m2_codex_implementation_20260910/contract_v2.py",
    "claude methods/_m2_ths_v2_claude_review_20260910/r06_basis_unit_controls.json",
    "claude methods/_m1_closure/pilot_symbols.csv",
]
PRESERVED_ORIGINALS = {
    "claude methods/_m3_20260910/codex/review_02_input/files/backend/app/research/m3_labels.py": "fe6046476f492aca4487492e47477166f47d1cfe052167adf021c0bf238d17e7",
    "claude methods/_m3_20260910/codex/review_02_input/files/backend/tests/test_m3_labels.py": "6fd2aa983f6ab3d15d1f9b679af9dd35a149d22f6f7c52bb0db373a0dace0a7b",
    "claude methods/_m3_20260910/codex/review_01_input/files/backend/app/research/m3_labels.py": "6a0590cf2dd9b7acbc9421c818e558e24d6c2877175c8a903d47dab375a99065",
    "claude methods/_m3_20260910/codex/review_01_input/files/backend/tests/test_m3_labels.py": "efa2e21cb70b70fbd0c39e3e4908a7a24f9837bb45889858979f6a99f09f0ab2",
    "claude methods/_m3_20260910/claude_01_r2/artifact_manifest.json": "34b28360fc9842876a2c321d7316bec2b7f1e0b3935f1cfd17711ac1857d7451",
    "claude methods/_m3_20260910/claude_01/artifact_manifest.json": "428bb425661239de755dca6ac49e5128a923f8b90ebdb19e1c85d404e67a5147",
    "claude methods/_m3_20260910/codex/R3_BENCHMARK_INTEGRATION_SUPPLEMENT.md": "a66f1db5fca541b84f97e38eb2397eb6a4b0ec3db620aa7ffeecaf0417e637ff",
    "claude methods/_m3_20260910/codex/test_independent_r2.py": "656cc5c10ac40968ca707ce78efe1e7edd562d6e5793c4f4d05eb45578c196e3",
    "claude methods/_m3_20260910/codex/test_feature_oracle.py": "eb600ca23c310fbe242c7b745e0fe87279847f0393beee5af6c897263ea677da",
    "claude methods/_m3_20260910/codex/R3_IN_PROGRESS_FEEDBACK.md": "e0092b6923a0abe1f5d3e0cbf4998a61e6a5694a53daabfa80532e706d6e127c",
    "claude methods/_m3_20260910/codex/test_independent_r3.py": "403145a9520884fb9ab86053e2318f6e13f599fe7f8c4e296f9452c64a3a7e09",
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
    t = load(TESTS, "m3_labels_tests_fixtures_r3")
    m = t.m
    assert Path(m.__file__).resolve() == MODULE.resolve()
    assert m.POLICY_VERSION == "0.3.0-draft"

    dump(HERE / "LABEL_POLICY.json", m.policy_document())

    # synthetic sequence path (unchanged rules, v3 records)
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
    proofs = [m.episode_prefix_proof(ep) for ep in episodes if ep["phase"] == "accumulation"]

    # admissible positive control (fixture-only real format) and its rejections through the same counting path
    members, controls, match = t.admissible_library_fixture()
    cases = members + controls
    positive_control = m.library_counts(cases, [match], t.REAL_FORMAT_CAL)
    single_day = m.library_counts([members[-1]] + controls, [match], t.REAL_FORMAT_CAL)
    forged = dict(match, controls=[], k_min=0, control_count=3, distinct_control_symbols=3, unmatched=False)
    try:
        m.library_counts(cases, [forged], t.REAL_FORMAT_CAL)
        forged_result = "accepted (unexpected)"
    except m.LabelInputError as exc:
        forged_result = exc.code
    syn_members = [t.flat_record(t.SYN_A, end) for end in (267, 268, 269)]
    syn_controls = [t.flat_record(f"SYN00001{i}", 269, distribution_spike=True) for i in range(3)]
    syn_rep = m.attach_review(m.attach_review(syn_members[-1], t.syn_review(syn_members[-1], "syn_a", "positive")), t.syn_review(syn_members[-1], "syn_b", "positive"))
    syn_counts = m.library_counts(syn_members[:-1] + [syn_rep] + syn_controls, [m.match_controls(syn_rep, syn_controls)], t.CODEX_CAL)

    # ledger demo: disagreement preserved, explicit supersession, transplant rejected
    positive = next(o for o in series if o["cutoff"]["decision_date"] == dates[295])
    disputed = m.attach_review(m.attach_review(positive, t.syn_review(positive, "codex_synthetic_demo", "positive")),
                               t.syn_review(positive, "claude_synthetic_demo", "ambiguous", when="2026-09-11T03:00:00+00:00"))
    first = disputed["review_ledger"]["entries"][1]["entry_hash"]
    superseded = m.attach_review(disputed, t.syn_review(positive, "claude_synthetic_demo", "positive", when="2026-09-11T06:00:00+00:00",
                                                        supersedes=first, supersede_reason="synthetic demo: re-read evidence"))
    other = dict(next(o for o in series if o["cutoff"]["decision_date"] == dates[296]))
    other["review_ledger"] = superseded["review_ledger"]
    try:
        m.review_status(other)
        transplant = "accepted (unexpected)"
    except m.LabelInputError as exc:
        transplant = exc.code

    # benchmark integration demo
    base = m.generate_labels(t.request_for(t.SYN_A, rows, dates[295], benchmark_symbol=t.SYN_BENCH, benchmark_observations=bench[:296], universe_coverage_on_decision_date=t.coverage()))
    changed = m.generate_labels(t.request_for(t.SYN_A, rows, dates[295], benchmark_symbol=t.SYN_BENCH,
                                              benchmark_observations=[replace(b, volume=float(b.volume) * 37.0, amount=None) for b in bench[:296]],
                                              universe_coverage_on_decision_date=t.coverage()))
    try:
        m.generate_labels(t.request_for(t.SYN_A, rows, dates[295], benchmark_symbol=t.SYN_BENCH,
                                        benchmark_observations=[replace(b, volume_unit="share", amount_unit="CNY") for b in bench[:296]],
                                        universe_coverage_on_decision_date=t.coverage()))
        share_units = "accepted (unexpected)"
    except m.LabelInputError as exc:
        share_units = exc.code

    examples = {
        "schema": "m3.claude_01_r3.synthetic_examples.v1",
        "synthetic": True,
        "counts_toward_case_library": False,
        "note": "All stock symbols are SYN###### or fixture-only real-format codes with syn:fixture-only refs; the calendars are declared fixtures; reviewer identities are demo strings. Nothing here is a case, a review or a claim of review work; every count is a contract demonstration.",
        "policy_hash": m.POLICY_HASH, "policy_version": m.POLICY_VERSION, "producer_sha256": m.producer_sha256(),
        "episode_path": [{k: ep[k] for k in ("phase", "kind", "start", "end", "sessions", "selection_at_start", "selection_at_end", "eligibility_changes",
                                            "min_duration_established_at", "closed_reason", "status", "meets_min_sessions")} for ep in episodes],
        "episode_prefix_proofs": proofs,
        "example_records_by_phase": example_records,
        "counting": {
            "admissible_positive_control_fixture_only": {k: positive_control[k] for k in ("raw_input_records", "unique_records", "records_real", "independently_reviewed",
                                                                                        "positively_reviewed_records", "episodes_total", "episodes_duration_established",
                                                                                        "qualified_reviewed_positive_episodes", "unique_controls", "control_uses",
                                                                                        "effective_dependence_groups", "target", "qualified_episodes")},
            "single_reviewed_day_same_path": {k: single_day[k] for k in ("independently_reviewed", "episodes_duration_established", "qualified_reviewed_positive_episodes", "effective_dependence_groups")},
            "forged_match_k_min_zero_same_path": forged_result,
            "synthetic_fixture_same_path": {k: syn_counts[k] for k in ("independently_reviewed", "episodes_duration_established", "qualified_reviewed_positive_episodes", "disqualified_episodes", "effective_dependence_groups")},
        },
        "ledger_demo": {"disputed_status": disputed["review_ledger"]["status"], "after_explicit_supersession": superseded["review_ledger"]["status"],
                        "entries_preserved": len(superseded["review_ledger"]["entries"]), "transplant_onto_other_core": transplant,
                        "record_hash_unchanged": superseded["record_hash"] == positive["record_hash"]},
        "benchmark_integration": {"regime_with_retained_units": base["labels"]["regime"], "same_identity_after_changing_unused_aggregates": changed["episode_id"] == base["episode_id"],
                                  "benchmark_claiming_share_units": share_units},
        "consumed_identity_demo": {"security_context_in_core_when_unavailable": m.generate_labels(t.request_for(t.SYN_A, rows, dates[295], security=m.SecurityContext(st_status="st", evidence_refs=("syn:late",), facts_available_at="2030-01-01T00:00:00+08:00")))["security_context"]},
        "split_roles": {x: m.split_role(x) for x in ("2023-09-04", "2025-03-31", "2025-04-01", "2025-12-31", "2026-01-01", "2026-09-04")},
        "purpose_allowlist": list(m.PURPOSES),
        "seed_context": m.seed_context(),
    }
    dump(HERE / "synthetic_examples.json", examples)

    manifest = {
        "schema": "m3.claude_01_r3.artifact_manifest.v1",
        "task_id": "M3-01-R3-CONSUMER-INTEGRITY-20260910",
        "supplements_incorporated": ["claude methods/_m3_20260910/codex/R3_BENCHMARK_INTEGRATION_SUPPLEMENT.md (a66f1db5…)",
                                     "claude methods/_m3_20260910/codex/R3_IN_PROGRESS_FEEDBACK.md (e0092b69…)"],
        "status": "ready_for_review",
        "owner": "Claude (existing ZK-trading / Fable 5.1 project advice fork)",
        "accepted_by_codex": False,
        "supersedes": {"r2_manifest_sha256": "34b28360fc9842876a2c321d7316bec2b7f1e0b3935f1cfd17711ac1857d7451",
                       "r1_manifest_sha256": "428bb425661239de755dca6ac49e5128a923f8b90ebdb19e1c85d404e67a5147", **m.SUPERSEDES},
        "policy": {"namespace": m.NAMESPACE, "policy_id": m.POLICY_ID, "policy_version": m.POLICY_VERSION, "policy_hash": m.POLICY_HASH,
                   "output_schema": m.OUTPUT_SCHEMA},
        "producer_sha256": m.producer_sha256(),
        "written": {}, "sources_read": {}, "preserved_originals": {},
        "safety": {"review_only": True, "live_trading_enabled": False, "sqlite_opened": [], "network_requests": 0, "subprocesses": 0,
                   "real_corpus_rows_read": 0, "synthetic_only": True, "real_cases": 0, "real_reviews": 0, "git_mutations": 0, "py_compile_used": False},
    }
    for rel in ("backend/app/research/m3_labels.py", "backend/tests/test_m3_labels.py"):
        p = PROJECT / rel
        manifest["written"][rel] = {"sha256": sha(p), "bytes": p.stat().st_size, "supersedes_versions": ["0.2.0-draft", "0.1.0-draft"]}
    for p in sorted(HERE.rglob("*")):
        if p.is_file() and p.name != "artifact_manifest.json":
            manifest["written"][p.relative_to(PROJECT).as_posix()] = {"sha256": sha(p), "bytes": p.stat().st_size}
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
    print("positive control:", positive_control["qualified_reviewed_positive_episodes"], "qualified,", positive_control["effective_dependence_groups"], "groups,", positive_control["unique_controls"], "controls")
    print("single day:", single_day["qualified_reviewed_positive_episodes"], "forged:", forged_result, "synthetic:", syn_counts["qualified_reviewed_positive_episodes"], syn_counts["disqualified_episodes"])
    print("ledger:", disputed["review_ledger"]["status"], "->", superseded["review_ledger"]["status"], "transplant:", transplant)
    print("benchmark:", base["labels"]["regime"]["regime"], "identity stable:", changed["episode_id"] == base["episode_id"], "share units:", share_units)
    print("preserved", all(v["match"] for v in manifest["preserved_originals"].values()), "missing sources", sum(1 for v in manifest["sources_read"].values() if v.get("missing")))
    print("manifest_sha256", sha(HERE / "artifact_manifest.json"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
