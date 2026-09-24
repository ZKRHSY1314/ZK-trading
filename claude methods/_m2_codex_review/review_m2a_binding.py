"""Offline independent review of the 73-case closure. No real collection.

Records fixed controls and two R2 binding counterexamples. Exit 0 means all stated
observations reproduced, not acceptance. All writes are disposable synthetic fixtures.
"""
from __future__ import annotations

import contextlib
import copy
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

MANIFEST, CALENDAR = fixtures.REAL_MANIFEST, fixtures.CALENDAR
PROD = [ROOT / "trading_local.sqlite3", ROOT / "market_history.sqlite3",
        ROOT / "market_history.sqlite3-wal"]
REVIEWED = list(M2.glob("*.py")) + list(M1.glob("*.py")) + [MANIFEST, CALENDAR]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def emit(name, **details):
    print(json.dumps({"case": name, **details}, ensure_ascii=False))


def pins():
    return dict(expected_manifest_sha=sha(MANIFEST), calendar_path=CALENDAR,
                expected_calendar_sha=sha(CALENDAR))


def closed_controls(tmp):
    man = fixtures.small_manifest(tmp)
    r = runner.PilotRunner(man, tmp / "controls", [("calendar", CALENDAR)], "controls")
    t = fixtures.paced(fixtures.fake(text="<html>NO BARS</html>"))
    try:
        r.collect(t, armed=True, responses={"unused": "unrelated rows"})
    except TypeError:
        assert t.attempt_count == 0 and not r.run_dir.exists()
    else:
        raise AssertionError("body override still present")
    out = r.collect(t, armed=True)
    assert not out["collection_complete"] and out["jobs_ok"] == 0
    emit("R1_closed", override_refused_before_attempt=True, html_jobs_ok=0)

    text, code = fixtures.gate_text(fixtures.full_rows(acc.RESEARCH_REQUIRED))
    try:
        acc.accept_research(text, code, manifest_path=MANIFEST, candidate_fingerprint="fp",
                            enforce=False, **pins())
    except TypeError:
        pass
    else:
        raise AssertionError("enforce bypass remains")
    for name, replacement in (("expected_manifest_sha", sha(MANIFEST)[:16]),
                              ("expected_calendar_sha", None)):
        bad = dict(pins(), **{name: replacement})
        try:
            acc.accept_research(text, code, manifest_path=MANIFEST,
                                candidate_fingerprint="fp", **bad)
        except acc.AcceptanceError:
            pass
        else:
            raise AssertionError("weak hash binding accepted")
    try:
        acc.accept_research("RESULT: FAILED - 1 required gate(s) not satisfied: P4\n" + text,
                            code, manifest_path=MANIFEST, candidate_fingerprint="fp", **pins())
    except acc.AcceptanceError:
        pass
    else:
        raise AssertionError("conflicting verdicts accepted")
    emit("R2_controls_closed", enforce_flag_removed=True, truncated_hash_refused=True,
         missing_calendar_pin_refused=True, conflicting_verdicts_refused=True)

    fake = fixtures.fake(sequence=[tp.RunAborted("original safety stop"), 200])
    transport = fixtures.paced(fake)
    for _ in range(2):
        try:
            transport.get_with_retries("https://offline.invalid", source="sina")
        except tp.RunAborted:
            pass
        else:
            raise AssertionError("request continued after abort")
    assert transport.attempt_count == len(fake.state["calls"]) == 1
    emit("R3_closed", attempts_after_two_calls=1, reason=transport.aborted_reason)

    root = tmp / "alias_control"
    root.mkdir()
    sentinel = tmp / "protected_sentinel.txt"
    sentinel.write_text("DO NOT OVERWRITE", encoding="utf-8")
    os.link(sentinel, root / "CURRENT.json.alias.tmp")
    try:
        runner.PilotRunner(man, root, [("sentinel", sentinel)], "alias")
    except runner.StagingSafetyError:
        assert sentinel.read_text(encoding="utf-8") == "DO NOT OVERWRITE"
    else:
        raise AssertionError("protected alias accepted at construction")
    emit("R4_protected_alias_closed", refused=True, disposable_sentinel_preserved=True)


def pipeline(tmp):
    at, ah = fixtures.build_archives(tmp)
    baseline = tmp / "baseline.json"
    with contextlib.redirect_stdout(io.StringIO()):
        assert staging_gate.main(["snapshot", "--archive-trading", str(at),
                                   "--archive-history", str(ah), "--calendar", str(CALENDAR),
                                   "--baseline-out", str(baseline)]) == 0
    protected = [("manifest", MANIFEST), ("calendar", CALENDAR),
                 ("archive-trading", at), ("archive-history", ah)]
    root = tmp / "candidates"
    good = runner.PilotRunner(MANIFEST, root, protected, "good")
    bodies = {}
    for entries, klass in ((good.stocks, "stock"), (good.benchmarks, "benchmark")):
        for entry in entries:
            days, _ = staging_gate.entry_eligibility(entry, good.warm + fixtures.WINDOW)
            rows = fixtures.price_rows(days, with_amount=klass == "stock")
            for url in prov.expected_urls(entry["symbol"], klass):
                bodies[url] = fixtures.envelope(entry["symbol"], rows)

    def gates(r):
        args = (r.destinations["trading"], r.destinations["history"], at, ah, MANIFEST, baseline)
        a = fixtures.run_m1_gate(*args, extra=["--history-scope", "all"])
        b = fixtures.run_m1_gate(*args, extra=["--history-scope", "all", "--warmup-consumers",
            "both", "--warmup-start", "2022-08-24", "--warmup-sessions", "250", "--warmup-required"])
        return a, b

    def verdicts(r, out, a, b):
        fp = out["candidate_fingerprint"]
        research = acc.accept_research(a[1], a[0], manifest_path=MANIFEST,
                                        candidate_fingerprint=fp, **pins())
        warmup = acc.accept_warmup_collection(b[1], b[0], MANIFEST, r.destinations["trading"],
                                              candidate_fingerprint=fp, **pins())
        return research, warmup

    def collect(run_id, data):
        r = runner.PilotRunner(MANIFEST, root, protected, run_id)
        out = r.collect(fixtures.paced(fixtures.fake(bodies=data)), armed=True)
        assert out["collection_complete"] and out["jobs_ok"] == 52
        return r, out

    gout = good.collect(fixtures.paced(fixtures.fake(bodies=bodies)), armed=True)
    ga, gb = gates(good)
    gv, gw = verdicts(good, gout, ga, gb)
    assert gv.accepted and gw.accepted and good.finalize(gout, gv, gw)["published"]
    emit("positive_control_approved_full_chain", jobs_ok=gout["jobs_ok"],
         research_exit=ga[0], warmup_exit=gb[0], shortfall=len(gw.details["shortfall"]),
         published=True)

    def omit_one(day):
        changed = dict(bodies)
        for url in prov.expected_urls("SH688001", "stock"):
            envelope = json.loads(changed[url])
            before = len(envelope["rows"])
            envelope["rows"] = [r for r in envelope["rows"] if r["date"] != day]
            assert len(envelope["rows"]) == before - 1
            changed[url] = json.dumps(envelope)
        return changed

    # B's actual M1 gates reject its missing research row. No verdict object is
    # forged: both wrong verdicts below come from the PUBLIC acceptance functions,
    # given untouched M1 text from good A and B's genuine collection fingerprint.
    bad, bout = collect("missing_research_day", omit_one(fixtures.WINDOW[20]))
    ba, bb = gates(bad)
    actual_a, actual_b = verdicts(bad, bout, ba, bb)
    assert ba[0] == 1 and not actual_a.accepted and not actual_b.accepted
    rebound_a, rebound_b = verdicts(bad, bout, ga, gb)
    pub = bad.finalize(bout, rebound_a, rebound_b)
    assert rebound_a.accepted and rebound_b.accepted and pub["published"]
    with contextlib.closing(sqlite3.connect(bad.destinations["trading"])) as conn:
        rows = conn.execute("SELECT COUNT(*) FROM daily_bar_cache").fetchone()[0]
    emit("R2_stale_gate_text_rebound_to_bad_candidate", rows_per_view=rows,
         actual_research_exit=ba[0], actual_research_accepted=actual_a.accepted,
         actual_research_failures=[g.id for g in actual_a.failing_required()],
         actual_warmup_accepted=actual_b.accepted,
         reused_report_from=gout["run_id"], candidate_run=bout["run_id"],
         public_rebound_research_accepted=rebound_a.accepted,
         public_rebound_warmup_accepted=rebound_b.accepted, published=pub["published"])

    # C has complete research data but an additional, unapproved warm-up gap.
    # Passing its REAL research verdict twice bypasses warm-up validation entirely.
    warm_bad, wout = collect("missing_warmup_day", omit_one(good.warm[20]))
    wa, wb = gates(warm_bad)
    wv, ww = verdicts(warm_bad, wout, wa, wb)
    assert wa[0] == 0 and wv.accepted and not ww.accepted
    pub = warm_bad.finalize(wout, wv, wv)
    assert pub["published"]
    emit("R2_research_verdict_substitutes_warmup", research_accepted=wv.accepted,
         actual_warmup_accepted=ww.accepted, actual_warmup_reason=ww.reason,
         same_real_research_verdict_in_both_slots=True, published=True)

    # R4 fault controls use the genuinely accepted good pair and real verdicts.
    previous = good.pointer.read_bytes()
    with patch.object(runner.os, "replace", side_effect=OSError("injected pointer replace failure")):
        pub = good.finalize(gout, gv, gw)
    assert not pub["published"] and good.pointer.read_bytes() == previous
    assert not good.pointer_tmp.exists()
    good.pointer_tmp.write_text("unowned temporary", encoding="utf-8")
    pub = good.finalize(gout, gv, gw)
    assert not pub["published"] and good.pointer_tmp.read_text(encoding="utf-8") == "unowned temporary"
    assert good.pointer.read_bytes() == previous
    emit("R4_publication_controls_closed", replace_failure_preserves_pointer=True,
         unowned_temp_preserved=True)


def main():
    meta = runner.production_fingerprint(PROD)
    hashes = {str(p): sha(p) for p in REVIEWED}
    with patch.object(socket.socket, "connect", side_effect=AssertionError("NETWORK DENIED")), \
         patch.object(socket, "create_connection", side_effect=AssertionError("NETWORK DENIED")), \
         tempfile.TemporaryDirectory(prefix="m2binding_review_") as tmp:
        closed_controls(Path(tmp))
        pipeline(Path(tmp))
    assert meta == runner.production_fingerprint(PROD), "production metadata changed"
    assert hashes == {str(p): sha(p) for p in REVIEWED}, "reviewed inputs changed"
    emit("review_safety", production_metadata_unchanged=True, reviewed_input_hashes_unchanged=True,
         network_permitted=False, temporary_fixtures_cleaned=True)


if __name__ == "__main__":
    main()
