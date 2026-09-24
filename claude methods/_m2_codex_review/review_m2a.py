"""Independent, offline M2a review probes. Synthetic temporary writes only.

This captures observed behavior, including defects; it is not a passing acceptance
suite. No production code/data is modified and all socket connections are denied.
"""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import math
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
import transport as tp
import test_m2a as fixtures
import test_staging_gate_e2e as m1fixtures
import staging_gate

MANIFEST = M1 / "pilot_symbols.csv"
CALENDAR = ROOT / "backend/.venv/Lib/site-packages/akshare/file_fold/calendar.json"
PRODUCTION = [ROOT / "trading_local.sqlite3", ROOT / "market_history.sqlite3",
              ROOT / "market_history.sqlite3-wal"]
PROTECTED = list(M2.glob("*.py")) + list(M1.glob("*.py")) + [MANIFEST, CALENDAR]
RESULTS = []


def emit(case, **details):
    value = {"case": case, **details}
    RESULTS.append(value)
    print(json.dumps(value, ensure_ascii=False))


def metadata():
    return {str(p): (p.stat().st_size, p.stat().st_mtime_ns) for p in PRODUCTION}


def hashes():
    return {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in PROTECTED}


def gate_call(args):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        code = staging_gate.main(args)
    return code, buf.getvalue()


def parser_probes():
    text, code = fixtures.gate_text([("P4", "units", "PASS", True)])
    emit("research_missing_mandatory_gates", accepted=acc.accept_research(text, code).accepted)
    text, code = fixtures.gate_text([("P4", "units", "UNKNOWN", False)])
    emit("research_unknown_units_as_advisory", accepted=acc.accept_research(text, code).accepted)
    with tempfile.TemporaryDirectory(prefix="m2review_accept_") as tmp:
        manifest, db = fixtures.warmup_fixture(Path(tmp))
        for label, rows in (
            ("warmup_depth_gate_absent", fixtures.WARM_ROWS[:-1]),
            ("warmup_depth_gate_unknown", fixtures.WARM_ROWS[:-1] +
             [("V3b", "depth", "UNKNOWN", True)]),
            ("warmup_depth_gate_advisory", fixtures.WARM_ROWS[:-1] +
             [("V3b", "depth", "FAIL", False)]),
        ):
            text, code = fixtures.gate_text(rows)
            result = acc.accept_warmup_collection(text, code, manifest, db)
            emit(label, accepted=result.accepted, shortfall_count=len(result.details.get("shortfall", {})))


def fabricated_full_pipeline():
    with tempfile.TemporaryDirectory(prefix="m2review_pipeline_") as tmp:
        tmp = Path(tmp)
        staging = tmp / "staging"
        staging.mkdir()
        at, ah = tmp / "archive_t.sqlite3", tmp / "archive_h.sqlite3"
        m1fixtures.build_views(at, ah, {"SH600000": ["2025-06-10"]})
        baseline = tmp / "baseline.json"
        code, _ = gate_call(["snapshot", "--archive-trading", str(at), "--archive-history", str(ah),
                             "--calendar", str(CALENDAR), "--baseline-out", str(baseline)])
        assert code == 0
        dest = {"trading": staging / "t.sqlite3", "history": staging / "h.sqlite3"}
        r = runner.PilotRunner(MANIFEST, staging, dest,
                              [("archive-trading", at), ("archive-history", ah),
                               ("manifest", MANIFEST), ("calendar", CALENDAR)])
        entries = {e["symbol"]: e for e in r.stocks + r.benchmarks}

        def unrelated_rows(symbol, klass):
            # Deliberately NOT decoded from an HTTP response. All responses below
            # are non-market-data HTML, while these rows use a synthetic constant.
            days, _ = runner.entry_eligibility(entries[symbol], r.warm + r.window)
            return [dict(fixtures.ROWS_HAND[0], date=day) for day in days]

        fake = fixtures.fake(text="<html>NOT MARKET DATA</html>")
        transport = fixtures.paced(fake)
        out = r.collect(transport, armed=True, fetcher=unrelated_rows)
        with contextlib.closing(sqlite3.connect(dest["trading"])) as conn:
            n, = conn.execute("SELECT COUNT(*) FROM daily_bar_cache").fetchone()
        args = ["validate", "--staging-trading", str(dest["trading"]),
                "--staging-history", str(dest["history"]), "--archive-trading", str(at),
                "--archive-history", str(ah), "--calendar", str(CALENDAR),
                "--baseline", str(baseline), "--pilot-manifest", str(MANIFEST),
                "--history-scope", "all", "--pricing-basis", "none", "--history-basis", "none",
                "--transformation", "identity"]
        a_code, a_text = gate_call(args)
        a = acc.accept_research(a_text, a_code)
        b_code, b_text = gate_call(args + ["--warmup-consumers", "both", "--warmup-start", "2022-08-24",
                                           "--warmup-sessions", "250", "--warmup-required"])
        b = acc.accept_warmup_collection(b_text, b_code, MANIFEST, dest["trading"])
        emit("unrelated_rows_after_non_market_http_body", http_body="HTML, no bars",
             runner_status=out["status"], promoted=out["promoted"], rows_per_view=n,
             http_attempts=transport.attempt_count, research_exit=a_code,
             research_accepted=a.accepted, warmup_exit=b_code, warmup_accepted=b.accepted,
             warmup_shortfall=b.details.get("shortfall"))


def transport_probes():
    with tempfile.TemporaryDirectory(prefix="m2review_failures_") as tmp:
        tmp = Path(tmp)
        dest = {"trading": tmp / "t.sqlite3", "history": tmp / "h.sqlite3"}
        r = runner.PilotRunner(MANIFEST, tmp, dest, [("manifest", MANIFEST), ("calendar", CALENDAR)])
        t = fixtures.paced(fixtures.fake(status=404))
        out = r.collect(t, armed=True, fetcher=lambda *_: fixtures.ROWS_HAND)
        emit("consecutive_failures_do_not_stop", failed_jobs=sum(o.status == "failed" for o in out["outcomes"]),
             http_attempts=t.attempt_count, status=out["status"], promoted=out["promoted"])
    t = fixtures.paced(fixtures.fake(raises=tp.RunAborted("inner safety abort")))
    try:
        t.get_with_retries("https://offline.invalid", source="sina")
    except Exception as exc:
        emit("inner_abort_retried", exception=type(exc).__name__, attempts=t.attempt_count,
             sticky_abort=t.aborted_reason)
    t = fixtures.paced(fixtures.fake(), connect_timeout=float("inf"))
    emit("infinite_timeout_constructor_accepted", connect_timeout_is_infinite=math.isinf(t.timeout[0]))
    t = fixtures.paced(fixtures.fake(raises=ValueError("programming error")))
    try:
        t.get_with_retries("https://offline.invalid", source="sina")
    except Exception as exc:
        emit("programming_error_retried", attempts=t.attempt_count, exception=type(exc).__name__)


def staging_probes():
    with tempfile.TemporaryDirectory(prefix="m2review_collision_") as tmp:
        tmp = Path(tmp)
        same = tmp / "same.sqlite3"
        result = runner.guard_destinations(tmp, {"trading": same, "history": same}, [])
        emit("same_destination_roles_allowed", accepted=result == tmp.resolve())
        result = runner.guard_destinations(tmp, {"trading": same, "history": tmp / "same.sqlite3.partial"}, [])
        emit("destination_partial_collision_allowed", accepted=result == tmp.resolve())
    with tempfile.TemporaryDirectory(prefix="m2review_atomic_") as tmp:
        tmp = Path(tmp)
        r = fixtures.make_runner(tmp)
        trading, history = r.destinations["trading"], r.destinations["history"]
        trading.write_bytes(b"old trading candidate")
        history.write_bytes(b"old history candidate")
        old_t, old_h = trading.read_bytes(), history.read_bytes()
        real_replace = runner.os.replace

        def second_replace_fails(src, dst):
            if Path(dst) == history:
                raise OSError("injected second promotion failure")
            return real_replace(src, dst)

        with patch.object(runner.os, "replace", side_effect=second_replace_fails):
            try:
                r.collect(fixtures.paced(fixtures.fake()), armed=True,
                          fetcher=lambda *_: fixtures.ROWS_HAND)
            except OSError as exc:
                emit("second_promotion_failure_mixes_generations", exception=str(exc),
                     trading_preserved=trading.read_bytes() == old_t,
                     history_preserved=history.read_bytes() == old_h,
                     partials_remaining=[p.name for p in r.root.glob("*.partial")])


def main():
    before_meta, before_hashes = metadata(), hashes()
    with patch.object(socket.socket, "connect", side_effect=AssertionError("NETWORK DISALLOWED")), \
         patch.object(socket, "create_connection", side_effect=AssertionError("NETWORK DISALLOWED")):
        parser_probes()
        fabricated_full_pipeline()
        transport_probes()
        staging_probes()
    assert before_meta == metadata(), "production metadata changed"
    assert before_hashes == hashes(), "reviewed inputs changed"
    emit("review_safety", production_metadata_unchanged=True, reviewed_inputs_hash_unchanged=True,
         network_connections_permitted=False, note="Observed defects are NOT acceptance success.")


if __name__ == "__main__":
    main()
