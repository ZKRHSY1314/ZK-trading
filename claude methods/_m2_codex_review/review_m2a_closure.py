"""Independent R1-R4 closure probes; observed defects are NOT acceptance passes.

All bars, responses, pointer publications and protected-file sentinels are synthetic
and temporary. Actual production databases are inspected by metadata only. Sockets
are blocked. The historical review_m2a.py is intentionally preserved unchanged.
"""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import socket
import sqlite3
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
M2 = ROOT / "claude methods/_m2_pilot"
M1 = ROOT / "claude methods/_m1_closure"
sys.path[:0] = [str(M2), str(M1)]
import acceptance as acc
import pilot_runner as runner
import provenance as prov
import transport as tp
import test_m2a as fixtures
import staging_gate

MANIFEST = M1 / "pilot_symbols.csv"
CALENDAR = fixtures.CALENDAR
PRODUCTION = [ROOT / "trading_local.sqlite3", ROOT / "market_history.sqlite3",
              ROOT / "market_history.sqlite3-wal"]
REVIEWED = list(M2.glob("*.py")) + list(M1.glob("*.py")) + [MANIFEST, CALENDAR]
HTML = "<html>NOT MARKET DATA</html>"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def emit(name, **data):
    print(json.dumps({"case": name, **data}, ensure_ascii=False))


def metadata():
    return runner.production_fingerprint(PRODUCTION)


def parse_probes(tmp):
    partial, code = fixtures.gate_text([("P4", "units", "PASS", True)])
    try:
        acc.accept_research(partial, code, manifest_path=MANIFEST)
    except acc.AcceptanceError:
        emit("positive_control_default_inventory", rejected=True)
    else:
        raise AssertionError("default inventory unexpectedly regressed")
    assert acc.accept_research(partial, code, enforce=False).accepted
    emit("R2_public_enforce_false_bypass", accepted=True, required_gates_present=1)

    text, code = fixtures.gate_text(fixtures.full_rows(acc.RESEARCH_REQUIRED))
    changed = tmp / "changed_manifest.csv"
    original = MANIFEST.read_text(encoding="utf-8")
    assert "SH688001" in original and "SH600998" not in original
    changed.write_text(original.replace("SH688001", "SH600998"), encoding="utf-8")
    verdict = acc.accept_research(text, code, manifest_path=changed)
    assert verdict.accepted and sha(changed) != sha(MANIFEST)
    emit("R2_same_count_substituted_manifest_without_pin", accepted=True,
         stocks=verdict.details["stocks"], benchmarks=verdict.details["benchmarks"],
         calendar_bound="calendar_sha256" in verdict.details)

    conflicting = "RESULT: FAILED - 1 required gate(s) not satisfied: P4\n" + text
    verdict = acc.accept_research(conflicting, code, manifest_path=MANIFEST,
                                  expected_manifest_sha=sha(MANIFEST),
                                  calendar_path=CALENDAR, expected_calendar_sha=sha(CALENDAR))
    assert verdict.accepted
    emit("R2_conflicting_result_lines_last_wins", accepted=True)


def transport_probes():
    fake = fixtures.fake(sequence=[tp.RunAborted("inner safety stop"), 200])
    transport = fixtures.paced(fake)
    try:
        transport.get_with_retries("https://offline.invalid", source="sina")
    except tp.RunAborted:
        pass
    else:
        raise AssertionError("first abort did not propagate")
    assert transport.attempt_count == 1
    response = transport.get_with_retries("https://offline.invalid", source="sina")
    assert response.status == 200 and transport.attempt_count == 2
    emit("R3_inner_abort_not_sticky", first_call_not_retried=True,
         next_call_status=response.status, attempts=transport.attempt_count,
         aborted_reason=transport.aborted_reason)


def full_pipeline(tmp):
    at, ah = fixtures.build_archives(tmp)
    baseline = tmp / "baseline.json"
    with contextlib.redirect_stdout(io.StringIO()):
        code = staging_gate.main(["snapshot", "--archive-trading", str(at),
                                  "--archive-history", str(ah), "--calendar", str(CALENDAR),
                                  "--baseline-out", str(baseline)])
    assert code == 0
    sentinel = tmp / "protected_synthetic_input.txt"
    sentinel.write_text("DO NOT OVERWRITE THIS SYNTHETIC INPUT", encoding="utf-8")
    protected = [("archive-trading", at), ("archive-history", ah),
                 ("manifest", MANIFEST), ("calendar", CALENDAR),
                 ("synthetic-input", sentinel)]
    root = tmp / "staging"
    # The alias exists before the runner's safety guard executes. It points only to
    # our own disposable sentinel, never any production or user-owned input.
    root.mkdir()
    os.link(sentinel, root / "CURRENT.json.tmp")
    r = runner.PilotRunner(MANIFEST, root, protected, run_id="good")
    bodies = {}
    for entries, klass in ((r.stocks, "stock"), (r.benchmarks, "benchmark")):
        for entry in entries:
            days, _ = staging_gate.entry_eligibility(entry, r.warm + fixtures.WINDOW)
            rows = fixtures.price_rows(days, with_amount=klass == "stock")
            for url in prov.expected_urls(entry["symbol"], klass):
                bodies[url] = fixtures.envelope(entry["symbol"], rows)
    pins = dict(expected_manifest_sha=sha(MANIFEST), calendar_path=CALENDAR,
                expected_calendar_sha=sha(CALENDAR))

    def evaluate(candidate):
        args = (candidate.destinations["trading"], candidate.destinations["history"],
                at, ah, MANIFEST, baseline)
        acode, atext = fixtures.run_m1_gate(*args, extra=["--history-scope", "all"])
        bcode, btext = fixtures.run_m1_gate(*args, extra=["--history-scope", "all",
            "--warmup-consumers", "both", "--warmup-start", "2022-08-24",
            "--warmup-sessions", "250", "--warmup-required"])
        a = acc.accept_research(atext, acode, manifest_path=MANIFEST, **pins)
        b = acc.accept_warmup_collection(btext, bcode, MANIFEST,
                                         candidate.destinations["trading"], **pins)
        assert a.accepted and b.accepted, (a.reason, b.reason)
        return a, b, acode, bcode

    good = r.collect(fixtures.paced(fixtures.fake(bodies=bodies)), armed=True)
    assert good["collection_complete"]
    a, b, acode, bcode = evaluate(r)
    emit("positive_control_full_52_chain", jobs_ok=good["jobs_ok"],
         research_exit=acode, warmup_exit=bcode, research_accepted=a.accepted,
         warmup_collection_accepted=b.accepted, gates_enforced=True,
         pinned_shortfall=len(b.details["shortfall"]))

    before = sentinel.read_bytes()
    published = r.publish(good, acceptance_ok=a.accepted and b.accepted)
    assert published["published"] and sentinel.read_bytes() != before
    emit("R4_pointer_temporary_alias_overwrites_protected_input", published=True,
         protected_disposable_sentinel_overwritten=True,
         alias_existed_before_constructor=True)

    another = runner.PilotRunner(MANIFEST, root, protected, run_id="not_collected")
    pub = another.publish(good, acceptance_ok=a.accepted and b.accepted)
    pointer = json.loads((root / runner.POINTER).read_text(encoding="utf-8"))
    assert pub["published"] and not Path(pointer["trading"]).exists()
    emit("R2_R4_acceptance_and_collection_replayed_across_runs", published=True,
         accepted_run=good["run_id"], pointer_run=pointer["run_id"],
         pointed_trading_exists=Path(pointer["trading"]).exists(),
         pointed_history_exists=Path(pointer["history"]).exists())

    injected = runner.PilotRunner(MANIFEST, root, protected, run_id="body_override")
    out = injected.collect(fixtures.paced(fixtures.fake(text=HTML)), armed=True,
                           responses=bodies)
    assert out["collection_complete"] and out["jobs_ok"] == 52
    a, b, acode, bcode = evaluate(injected)
    with contextlib.closing(sqlite3.connect(injected.destinations["trading"])) as conn:
        n = conn.execute("SELECT COUNT(*) FROM daily_bar_cache").fetchone()[0]
        recorded = conn.execute("SELECT url, body_sha256 FROM ingest_provenance").fetchall()
    assert n == 45935
    assert all(h == hashlib.sha256(bodies[url].encode()).hexdigest() for url, h in recorded)
    assert all(h != hashlib.sha256(HTML.encode()).hexdigest() for _, h in recorded)
    emit("R1_response_body_override_full_chain", actual_response="HTML without bars",
         replacement="caller-supplied responses map", rows_per_view=n,
         jobs_ok=out["jobs_ok"], http_attempts=out["http_attempts"],
         research_exit=acode, warmup_exit=bcode,
         research_accepted=a.accepted, warmup_collection_accepted=b.accepted,
         provenance_hashes_replacement_not_actual_response=True)


def main():
    before_meta = metadata()
    before_hashes = {str(p): sha(p) for p in REVIEWED}
    with patch.object(socket.socket, "connect", side_effect=AssertionError("NETWORK DENIED")), \
         patch.object(socket, "create_connection", side_effect=AssertionError("NETWORK DENIED")), \
         tempfile.TemporaryDirectory(prefix="m2closure_review_") as tmp:
        tmp = Path(tmp)
        parse_probes(tmp)
        transport_probes()
        full_pipeline(tmp)
    assert before_meta == metadata(), "production metadata changed"
    assert before_hashes == {str(p): sha(p) for p in REVIEWED}, "reviewed input changed"
    emit("review_safety", production_metadata_unchanged=True,
         reviewed_inputs_hash_unchanged=True, network_connections_permitted=False,
         temporary_fixtures_cleaned=True,
         note="Exit 0 means the observations reproduced, NOT that M2a passed acceptance")


if __name__ == "__main__":
    main()
