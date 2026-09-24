"""Independent acceptance checks for the 79-case M2a receipt closure.

Synthetic temporary fixtures only; no real source, production writes or deployment.
Unlike earlier defect-recording scripts, all assertions here require safe behavior.
"""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
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
import test_m2a as fx
import staging_gate
import review_m2a_binding as previous

MANIFEST, CALENDAR = fx.REAL_MANIFEST, fx.CALENDAR
PROD = [ROOT / "trading_local.sqlite3", ROOT / "market_history.sqlite3",
        ROOT / "market_history.sqlite3-wal"]
READ_ONLY = list(M2.glob("*.py")) + list(M1.glob("*.py")) + [MANIFEST, CALENDAR]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def emit(name, **details):
    print(json.dumps({"check": name, **details}, ensure_ascii=False))


def checks(tmp):
    # Reuse the previous reviewer's read-only control definitions, not its outdated
    # defect expectations. This preserves independent R1/R2/R3/R4 closure checks.
    previous.closed_controls(tmp)
    at, ah = fx.build_archives(tmp)
    baseline = tmp / "baseline.json"
    with contextlib.redirect_stdout(io.StringIO()):
        assert staging_gate.main(["snapshot", "--archive-trading", str(at),
            "--archive-history", str(ah), "--calendar", str(CALENDAR),
            "--baseline-out", str(baseline)]) == 0
    pins = dict(expected_manifest_sha=sha(MANIFEST), calendar_path=CALENDAR,
                expected_calendar_sha=sha(CALENDAR))
    validation = dict(pins, archive_trading=at, archive_history=ah, baseline=baseline)
    protected = [("manifest", MANIFEST), ("calendar", CALENDAR),
                 ("archive-trading", at), ("archive-history", ah), ("baseline", baseline)]
    root = tmp / "candidate_runs"

    def collect(run_id, omit=None):
        r = runner.PilotRunner(MANIFEST, root, protected, run_id)
        bodies = {}
        for entries, kind in ((r.stocks, "stock"), (r.benchmarks, "benchmark")):
            for entry in entries:
                days, _ = staging_gate.entry_eligibility(entry, r.warm + fx.WINDOW)
                if omit and omit[0] == entry["symbol"]:
                    assert omit[1] in days
                    days = [day for day in days if day != omit[1]]
                for url in prov.expected_urls(entry["symbol"], kind):
                    bodies[url] = fx.envelope(entry["symbol"],
                        fx.price_rows(days, with_amount=kind == "stock"))
        out = r.collect(fx.paced(fx.fake(bodies=bodies)), armed=True)
        assert out["collection_complete"] and out["jobs_ok"] == 52
        return r, out

    def validate(r):
        return [r.validate_candidate(mode, **validation) for mode in runner.REQUIRED_MODES]

    a, aout = collect("healthy_A")
    ar, aw = validate(a)
    assert ar.accepted and ar.gate_exit == 0
    assert aw.accepted and aw.gate_exit == 1
    assert aw.details["shortfall"] == acc.PINNED_SHORTFALL
    counts = {}
    for name, table in (("trading", "daily_bar_cache"), ("history", "daily_bars")):
        with contextlib.closing(sqlite3.connect(a.destinations[name])) as con:
            counts[name] = con.execute("SELECT COUNT(*) FROM " + table).fetchone()[0]
    assert counts == {"trading": 45935, "history": 45935}
    emit("healthy_full_chain", rows=counts, jobs_ok=52, research_exit=0,
         warmup_exit=1, pinned_shortfall=14)

    b, bout = collect("missing_research_B", ("SH688001", fx.WINDOW[20]))
    br, bw = validate(b)
    assert not br.accepted and br.gate_exit == 1 and not bw.accepted
    assert not b.finalize(bout, [br, bw])["published"]
    assert not b.finalize(bout, [ar, aw])["published"]
    emit("own_failure_and_wrong_run_receipts_rejected", own_research_exit=br.gate_exit,
         own_failure_published=False, A_receipts_publish_B=False)

    # Reproduce the EXACT last review failure: genuine A text plus B fingerprint.
    # The low-level helpers may parse it, but their Verdicts must not publish B.
    args = (a.destinations["trading"], a.destinations["history"], at, ah, MANIFEST, baseline)
    acode, atext = fx.run_m1_gate(*args, extra=["--history-scope", "all"])
    wcode, wtext = fx.run_m1_gate(*args, extra=["--history-scope", "all",
        "--warmup-consumers", "both", "--warmup-start", "2022-08-24",
        "--warmup-sessions", "250", "--warmup-required"])
    raw_r = acc.accept_research(atext, acode, manifest_path=MANIFEST,
                                candidate_fingerprint=bout["candidate_fingerprint"], **pins)
    raw_w = acc.accept_warmup_collection(wtext, wcode, MANIFEST, b.destinations["trading"],
                                candidate_fingerprint=bout["candidate_fingerprint"], **pins)
    assert raw_r.accepted and raw_w.accepted
    blocked = b.finalize(bout, [raw_r, raw_w])
    assert not blocked["published"] and "ValidationReceipt" in blocked["reason"]
    assert not b.pointer.exists()
    emit("R2_1_old_report_cannot_publish_new_candidate", raw_helper_verdicts_nonpublishable=True)

    c, cout = collect("missing_warmup_C", ("SH688001", a.warm[20]))
    cr, cw = validate(c)
    assert cr.accepted and not cw.accepted and "W1_pricing" in cw.reason
    for supplied in ([cr, cr], [cr], [cr, cw]):
        assert not c.finalize(cout, supplied)["published"]
    assert not c.pointer.exists()
    emit("R2_2_warmup_cannot_be_replaced", duplicate_research_refused=True,
         missing_warmup_refused=True, actual_warmup_failure_refused=True)

    # The actual M1 gate sees good data and exits 0; mutate AFTER its return but before
    # validate_candidate fingerprints again. This isolates the binding guard itself.
    d, dout = collect("mutation_D")
    dr, dw = validate(d)
    main = staging_gate.main
    def gate_then_mutate(argv):
        result = main(argv)
        assert result == 0
        with contextlib.closing(sqlite3.connect(d.destinations["trading"])) as con:
            con.execute("DELETE FROM daily_bar_cache WHERE symbol=? AND trade_date=?",
                        ("SH688001", fx.WINDOW[30]))
            con.commit()
        return result
    with patch.object(staging_gate, "main", side_effect=gate_then_mutate):
        changed = d.validate_candidate("research", **validation)
    assert changed.gate_exit == 0 and not changed.accepted
    assert "changed while the gate was running" in changed.reason
    assert not d.finalize(dout, [dr, dw])["published"]
    emit("mutation_binding", passing_gate_then_mutation_refused=True,
         previously_issued_receipts_refused_after_mutation=True)

    bad_pin = dict(validation, expected_manifest_sha="0" * 64)
    assert not a.validate_candidate("research", **bad_pin).accepted
    emit("incorrect_frozen_input_pin_rejected", accepted=False)

    published = a.finalize(aout, [ar, aw])
    assert published["published"]
    pointer = json.loads(a.pointer.read_text(encoding="utf-8"))
    assert pointer["validated_modes"] == ["research", "warmup_collection"]
    assert pointer["candidate_fingerprint"] == aout["candidate_fingerprint"]
    emit("healthy_publication", published=True, validated_modes=pointer["validated_modes"])

    old_pointer = a.pointer.read_bytes()
    with patch.object(runner.os, "replace", side_effect=OSError("synthetic replace failure")):
        assert not a.finalize(aout, [ar, aw])["published"]
    assert a.pointer.read_bytes() == old_pointer and not a.pointer_tmp.exists()
    a.pointer_tmp.write_text("unowned", encoding="utf-8")
    assert not a.finalize(aout, [ar, aw])["published"]
    assert a.pointer_tmp.read_text(encoding="utf-8") == "unowned"
    assert a.pointer.read_bytes() == old_pointer
    emit("publication_failure_controls", prior_pointer_preserved=True, unowned_temp_preserved=True)


def main():
    meta = runner.production_fingerprint(PROD)
    hashes = {str(path): sha(path) for path in READ_ONLY}
    with patch.object(socket.socket, "connect", side_effect=AssertionError("NETWORK DENIED")), \
         patch.object(socket, "create_connection", side_effect=AssertionError("NETWORK DENIED")), \
         tempfile.TemporaryDirectory(prefix="m2receipt_acceptance_") as tmp:
        checks(Path(tmp))
    assert meta == runner.production_fingerprint(PROD), "production metadata changed"
    assert hashes == {str(path): sha(path) for path in READ_ONLY}, "reviewed inputs changed"
    emit("review_safety", production_metadata_unchanged=True, reviewed_hashes_unchanged=True,
         network_connections_permitted=False, temporary_fixtures_cleaned=True)


if __name__ == "__main__":
    main()
