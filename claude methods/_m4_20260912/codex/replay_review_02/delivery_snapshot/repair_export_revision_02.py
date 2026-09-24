"""Deterministic EXPORT-ONLY repair of the M4-03B delivery-01 run outputs (Codex review 01, P2-2) - NOT a historical replay.

Consumes the hash-verified original run folder runs/829d42809e978c04/ (pinned in superseded/delivery_01/DELIVERY_STATUS.json)
and writes a distinct revision folder runs/829d42809e978c04-rev02/.  For every branch the ONLY change is the enclosing
performance wrapper (the research record with kind == "performance"):

* raw_provenance gains the two benchmark endpoint entries (roles benchmark_start_level / benchmark_end_level: symbol,
  trade_date, raw_sha256, point_index, captured_at) taken strictly from the existing FIRST (2023-09-04) and LAST
  (2025-03-31) decision wrappers' `benchmark_level` provenance of the same branch - nothing is reconstructed; absent or
  conflicting endpoint records abort the repair;
* benchmark_endpoints (model instants per endpoint: assumed 15:00 / 16:00 of the endpoint session; raw = the capture
  instant; the engine's benchmark status / refusal reasons copied from the unmodified engine record);
* initial_cash_used = "1000000.00" (the historical run's initial cash; the performance numbers already used it, nothing
  numerical changes) and, for assumed branches, the listed-status default assumption id.

Every nested engine record and every ledger record stays byte-equivalent under canonical JSON (asserted); all other
research records are byte-equivalent (asserted); ledger_records.jsonl.gz files are copied byte-identical.  The
transformation is applied twice from identical original bytes and the two in-memory outputs must hash identically before
anything is written.  Runs under the claude_03b guard in synthetic mode: zero SQLite connections, no network, writes
only under claude_03b/.

    backend/.venv/Scripts/python.exe -B -X utf8 "claude methods/_m4_20260912/claude_03b/repair_export_revision_02.py"
"""
from __future__ import annotations

import gzip
import hashlib
import importlib.util
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[2]
sys.dont_write_bytecode = True
ORIGINAL = HERE / "runs" / "829d42809e978c04"
REVISION_ID = "829d42809e978c04-rev02"
REVISED = HERE / "runs" / REVISION_ID
STATUS_DEFAULT_ASSUMPTION = "ASSUMPTION:security_status_listed_default_no_status_evidence_declared_pool_only"
CLOSE_AVAILABILITY_ASSUMPTION = "ASSUMPTION:close_fields_observed_at_1500_available_at_close_plus_3600s"
FIRST, LAST, BENCH, INITIAL_CASH = "2023-09-04", "2025-03-31", "SH000300", "1000000.00"


def load_module(name: str, path: Path):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False, default=str)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_jsonl_gz_bytes(data: bytes) -> list[dict]:
    return [json.loads(line) for line in gzip.decompress(data).decode("utf-8").splitlines() if line]


class RepairFailure(RuntimeError):
    pass


def repair_records(records: list[dict], branch: str) -> tuple[list[dict], dict]:
    """Pure transformation: returns (new records, endpoint derivation) or raises."""
    decisions = {r["session"]: r for r in records if r["kind"] == "decision"}
    perf = [i for i, r in enumerate(records) if r["kind"] == "performance"]
    if len(perf) != 1:
        raise RepairFailure(f"{branch}: expected exactly one performance wrapper, found {len(perf)}")
    if FIRST not in decisions or LAST not in decisions:
        raise RepairFailure(f"{branch}: first/last decision wrappers missing")
    endpoints = {}
    for role, session in (("benchmark_start_level", FIRST), ("benchmark_end_level", LAST)):
        cands = [p for p in decisions[session]["raw_provenance"] if p.get("role") == "benchmark_level" and p.get("symbol") == BENCH and p.get("trade_date") == session]
        distinct = {canonical({k: v for k, v in c.items() if k != "role"}) for c in cands}
        if len(distinct) != 1:
            raise RepairFailure(f"{branch}: {role} absent or conflicting in the {session} decision wrapper ({len(cands)} candidates, {len(distinct)} distinct)")
        entry = json.loads(next(iter(distinct)))
        endpoints[role] = {**entry, "role": role}
    variant = records[perf[0]]["variant"]
    old = records[perf[0]]
    eng = old["engine_record"]
    if eng.get("schema") != "m4.risk.performance.v1" or eng.get("session") != LAST:
        raise RepairFailure(f"{branch}: unexpected performance engine record")
    model_time = {}
    for role, session in (("benchmark_start_level", FIRST), ("benchmark_end_level", LAST)):
        cap = endpoints[role]["captured_at"]
        if variant == "assumed":
            model_time[role] = {"session": session, "observed_at": f"{session}T15:00:00+08:00", "available_at": f"{session}T16:00:00+08:00", "raw_captured_at": cap}
        else:
            model_time[role] = {"session": session, "observed_at": cap, "available_at": cap, "raw_captured_at": cap}
    bench_engine = eng.get("benchmark") or {}
    new = dict(old)
    new["raw_provenance"] = list(old["raw_provenance"]) + [endpoints["benchmark_start_level"], endpoints["benchmark_end_level"]]
    new["model_time"] = {"as_of": old["model_time"]["as_of"], "mark_observed_at": f"{LAST}T15:00:00+08:00" if variant == "assumed" else "raw_capture",
                         "mark_available_at": old["model_time"]["as_of"] if variant == "assumed" else "raw_capture"}
    ids = set(old["assumption_ids"]) | ({CLOSE_AVAILABILITY_ASSUMPTION, STATUS_DEFAULT_ASSUMPTION} if variant == "assumed" else set())
    new["assumption_ids"] = sorted(ids)
    new["benchmark_endpoints"] = {"symbol": BENCH, "start_session": FIRST, "end_session": LAST, "model_time": model_time,
                                  "engine_benchmark_status": bench_engine.get("status"), "engine_benchmark_refusals": bench_engine.get("refusals", []),
                                  "note": "benchmark levels are the SH000300 closes of the two endpoint sessions consumed by the frozen risk layer's benchmark_return; raw variant keeps the 2026 capture instants and the engine's refusal reasons",
                                  "derived_from": {"start": f"decision wrapper {FIRST} raw_provenance[role=benchmark_level]", "end": f"decision wrapper {LAST} raw_provenance[role=benchmark_level]"}}
    new["initial_cash_used"] = INITIAL_CASH
    new["export_repair"] = {"revision": REVISION_ID, "review": "codex/M4_03B_REVIEW_01.md P2-2", "kind": "export_only_metadata_repair_not_a_replay"}
    new["engine_record"] = old["engine_record"]
    if canonical(new["engine_record"]) != canonical(old["engine_record"]):
        raise RepairFailure("engine record altered")
    out = list(records)
    out[perf[0]] = new
    for i, (a, b) in enumerate(zip(records, out)):
        if i != perf[0] and canonical(a) != canonical(b):
            raise RepairFailure(f"{branch}: non-performance record {i} altered")
    return out, {"endpoints": endpoints, "performance_index": perf[0], "variant": variant}


def output_hash(records, ledger_records, summary) -> str:
    body = {"records": records, "ledger_records": ledger_records, "funnel": summary["funnel"], "performance": summary["performance"], "censored": summary["censored"],
            "ledger_state_hash": summary["ledger_state_hash"], "engine_chain_hash": summary["engine_chain_hash"]}
    return sha256_text(canonical(body))


def main() -> int:
    started = datetime.now(timezone.utc).isoformat()
    guard = load_module("m4_03b_guard", HERE / "guard.py")
    guard.install()
    evidence = HERE / "evidence"
    self_check = guard.self_check(evidence)
    if REVISED.exists():
        raise SystemExit(f"revision folder exists: {REVISED}; refusing to overwrite")
    status = json.loads((HERE / "superseded" / "delivery_01" / "DELIVERY_STATUS.json").read_text(encoding="utf-8"))
    pins = status["original_run_pins"]
    verified = {}
    for rel, meta in pins.items():
        p = HERE / rel
        got = sha256_file(p)
        verified[rel] = {"expected": meta["sha256"], "actual": got, "ok": got == meta["sha256"] and p.stat().st_size == meta["bytes"]}
        if not verified[rel]["ok"]:
            raise SystemExit(f"original run file changed: {rel}")
    receipt = json.loads((ORIGINAL / "receipt.json").read_text(encoding="utf-8"))
    funnel = json.loads((ORIGINAL / "funnel.json").read_text(encoding="utf-8"))
    branches = list(receipt["branches"])
    originals = {}
    for b in branches:
        bdir = ORIGINAL / "branches" / b
        originals[b] = {"research": (bdir / "research_records.jsonl.gz").read_bytes(), "ledger": (bdir / "ledger_records.jsonl.gz").read_bytes(),
                        "summary": json.loads((bdir / "summary.json").read_text(encoding="utf-8"))}

    def transform_all() -> dict:
        out = {}
        for b in branches:
            recs = read_jsonl_gz_bytes(originals[b]["research"])
            led = read_jsonl_gz_bytes(originals[b]["ledger"])
            new, deriv = repair_records(recs, b)
            content = "".join(canonical(r) + "\n" for r in new)
            out[b] = {"records": new, "content_sha256": sha256_text(content), "content": content, "derivation": deriv, "ledger": led,
                      "revised_output_hash": output_hash(new, led, originals[b]["summary"]), "original_output_hash_recomputed": output_hash(recs, led, originals[b]["summary"])}
        return out

    pass1, pass2 = transform_all(), transform_all()
    twice = {b: {"pass_1": pass1[b]["content_sha256"], "pass_2": pass2[b]["content_sha256"], "identical": pass1[b]["content_sha256"] == pass2[b]["content_sha256"],
                 "revised_output_hash_pass_1": pass1[b]["revised_output_hash"], "revised_output_hash_pass_2": pass2[b]["revised_output_hash"]} for b in branches}
    if not all(v["identical"] and v["revised_output_hash_pass_1"] == v["revised_output_hash_pass_2"] for v in twice.values()):
        raise SystemExit("export transformation not deterministic")
    for b in branches:
        if pass1[b]["original_output_hash_recomputed"] != originals[b]["summary"]["output_hash"]:
            raise SystemExit(f"{b}: recomputed original output hash differs from the delivered summary; original bytes unexpected")
    # ---- write the revision folder once -----------------------------------------------------------------------
    REVISED.mkdir(parents=True)
    copied = {}
    for name in ("receipt.json", "sql_log.json", "reconciliation.json", "warmup_depths.json"):
        shutil.copyfile(ORIGINAL / name, REVISED / name)
        copied[name] = {"sha256": sha256_file(REVISED / name), "byte_identical_to_original": sha256_file(REVISED / name) == sha256_file(ORIGINAL / name)}
    written = {}
    revised_summaries = {}
    for b in branches:
        bdir = REVISED / "branches" / b
        bdir.mkdir(parents=True)
        with gzip.open(bdir / "research_records.jsonl.gz", "wb") as fh:
            fh.write(pass1[b]["content"].encode("utf-8"))
        shutil.copyfile(ORIGINAL / "branches" / b / "ledger_records.jsonl.gz", bdir / "ledger_records.jsonl.gz")
        s = dict(originals[b]["summary"])
        s["records"] = {"path": "research_records.jsonl.gz", "records": len(pass1[b]["records"]), "content_sha256": pass1[b]["content_sha256"], "file_sha256": sha256_file(bdir / "research_records.jsonl.gz")}
        s["output_hash_original"] = originals[b]["summary"]["output_hash"]
        s["output_hash"] = pass1[b]["revised_output_hash"]
        s["export_repair"] = {"revision": REVISION_ID, "changed_records": [pass1[b]["derivation"]["performance_index"]], "changed_record_kind": "performance wrapper metadata only",
                              "benchmark_endpoints": pass1[b]["derivation"]["endpoints"], "numerical_values_changed": False, "engine_and_ledger_records_changed": False}
        (bdir / "summary.json").write_text(json.dumps(s, indent=2, ensure_ascii=False, sort_keys=True, default=str) + "\n", encoding="utf-8")
        revised_summaries[b] = s
        for name in ("research_records.jsonl.gz", "ledger_records.jsonl.gz", "summary.json"):
            written[f"branches/{b}/{name}"] = sha256_file(bdir / name)
        if written[f"branches/{b}/ledger_records.jsonl.gz"] != sha256_file(ORIGINAL / "branches" / b / "ledger_records.jsonl.gz"):
            raise SystemExit("ledger copy not byte-identical")
    fun = dict(funnel)
    fun["determinism_original_two_historical_repeats"] = funnel["determinism"]
    fun["export_repair_revision_02"] = {"applied_twice_from_identical_original_bytes": twice, "note": "deterministic export-only repair of the performance wrapper; NOT two new historical replays"}
    (REVISED / "funnel.json").write_text(json.dumps(fun, indent=2, ensure_ascii=False, sort_keys=True, default=str) + "\n", encoding="utf-8")
    rev = {"schema": "m4.claude_03b.export_repair_receipt.v1", "revision": REVISION_ID, "kind": "export_only_metadata_repair", "not_a_historical_replay": True,
           "started_at_utc": started, "finished_at_utc": datetime.now(timezone.utc).isoformat(),
           "command": [sys.executable, "-B", "-X", "utf8", str(Path(__file__).resolve().relative_to(PROJECT).as_posix())], "transformation_code_sha256": sha256_file(Path(__file__)),
           "review": {"path": "claude methods/_m4_20260912/codex/M4_03B_REVIEW_01.md", "sha256": "a0fc04e70abf4f1bc3165e73dd99edea584dcb1d57374d515dd299f72a6f429d"},
           "original_run": {"run_id": receipt["run_id"], "run_dir": receipt["run_dir"], "input_hash": receipt["sealed_input"]["input_hash"], "model_hash": receipt["sealed_input"]["model_hash"],
                            "files_verified_against_delivery_01_pins": verified, "original_output_hashes": {b: originals[b]["summary"]["output_hash"] for b in branches}},
           "inputs": {b: {"research_records_sha256": hashlib.sha256(originals[b]["research"]).hexdigest(), "ledger_records_sha256": hashlib.sha256(originals[b]["ledger"]).hexdigest()} for b in branches},
           "outputs": {"copied_unchanged": copied, "written": written, "funnel_json_sha256": sha256_file(REVISED / "funnel.json")},
           "applied_twice": twice, "revised_output_hashes": {b: pass1[b]["revised_output_hash"] for b in branches},
           "endpoint_derivation": {b: pass1[b]["derivation"]["endpoints"] for b in branches},
           "invariants": {"engine_records_unchanged": True, "ledger_records_byte_identical": True, "non_performance_research_records_unchanged": True, "numerical_values_unchanged": True,
                          "initial_cash_used": INITIAL_CASH, "changed_per_branch": "exactly one research record (kind=performance) - enclosing metadata only"},
           "guard": {"self_check": self_check, **guard.receipt()},
           "safety": {"sqlite_connections": len(guard.CONNECTIONS), "network_requests": 0, "historical_runner_invocations": 0, "review_only": True, "live_trading_enabled": False, "training_eligible": False, "strict_pit": False, "M4_complete": False, "M5_started": False}}
    if guard.CONNECTIONS or guard.DENIAL_LOG:
        raise SystemExit("guard reported a connection or a denial during the repair")
    (REVISED / "revision_receipt.json").write_text(json.dumps(rev, indent=2, ensure_ascii=False, sort_keys=True, default=str) + "\n", encoding="utf-8")
    print(json.dumps({"revision": REVISION_ID, "applied_twice_identical": all(v["identical"] for v in twice.values()), "revised_output_hashes": rev["revised_output_hashes"],
                      "original_output_hashes": rev["original_run"]["original_output_hashes"], "connections": len(guard.CONNECTIONS), "denials": len(guard.DENIAL_LOG),
                      "endpoints": {b: {r: (e["trade_date"], e["raw_sha256"][:12], e["captured_at"]) for r, e in pass1[b]["derivation"]["endpoints"].items()} for b in branches}}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
