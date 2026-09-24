"""M2a - offline tests. No network, no production write, synthetic fixtures only.

Blocks:
  R1  provenance + decoder: stored rows come from the captured bodies
  R2  acceptance: internal gate inventory, requiredness, input binding
  R3  transport: pacing, stop, retry classification, finite configuration
  R4  staging: path roles, honest rollups, failure-safe publication
  INT the real chain: fake transport -> decoder -> staging -> unchanged M1 gate -> acceptance

Run: python test_m2a.py
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "_m1_closure"))

import acceptance as acc          # noqa: E402
import decoder                    # noqa: E402
import pilot_runner as runner     # noqa: E402
import provenance as prov         # noqa: E402
import transport as tp            # noqa: E402
import staging_gate               # noqa: E402
from coverage_gap_generator import sessions_between  # noqa: E402

ROOT = Path(r"D:\codex-A股交易")
PROD = [ROOT / "trading_local.sqlite3", ROOT / "market_history.sqlite3"]
CALENDAR = ROOT / "backend/.venv/Lib/site-packages/akshare/file_fold/calendar.json"
REAL_MANIFEST = ROOT / "claude methods" / "_m1_closure" / "pilot_symbols.csv"
WINDOW = sessions_between("2023-09-04", "2026-09-04")

HTML = "<html>NOT MARKET DATA</html>"

CASES = []


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def pins(manifest=None):
    man = manifest or REAL_MANIFEST
    return dict(manifest_path=man, expected_manifest_sha=sha(man),
                calendar_path=CALENDAR, expected_calendar_sha=sha(CALENDAR))


def case(name):
    def deco(fn):
        CASES.append((name, fn))
        return fn
    return deco


# ------------------------------------------------------------------ fake transport

class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


class Sleeper:
    def __init__(self, clock):
        self.clock = clock
        self.waits = []

    def __call__(self, seconds):
        self.waits.append(seconds)
        self.clock.t += seconds


def fake(status=200, text="{}", location=None, raises=None, sequence=None, bodies=None):
    state = {"calls": [], "i": 0}

    def _t(url, *, timeout, allow_redirects):
        state["calls"].append({"url": url, "timeout": timeout,
                               "allow_redirects": allow_redirects})
        if raises is not None:
            raise raises
        body = (bodies or {}).get(url, text)
        if sequence is not None:
            item = sequence[min(state["i"], len(sequence) - 1)]
            state["i"] += 1
            if isinstance(item, Exception):
                raise item
            return tp.Response(status=item, text=body, url=url,
                               headers={"location": location} if location else {})
        return tp.Response(status=status, text=body, url=url,
                           headers={"location": location} if location else {})

    _t.state = state
    return _t


def paced(transport_fn, **kw):
    clock = Clock()
    sleeper = Sleeper(clock)
    t = tp.PacedTransport(transport_fn, clock=clock, sleeper=sleeper, **kw)
    t.sleeper = sleeper
    return t


def envelope(symbol, rows, basis="none", schema=decoder.SUPPORTED_SCHEMA):
    return json.dumps({"schema": schema, "symbol": symbol, "basis": basis, "rows": rows})


def price_rows(dates, with_amount=True):
    out = []
    for d in dates:
        row = {"date": d, "open": 10.0, "high": 11.0, "low": 9.0, "close": 10.5,
               "volume": 1000.0}
        if with_amount:
            row["amount"] = 1_050_000.0        # 1000 hands x 100 shares x 10.5
        out.append(row)
    return out


ROWS_HAND = price_rows(["2025-06-10"])
ROWS_SHARE = [dict(r, volume=100_000.0) for r in ROWS_HAND]


# =============================================================== R1 decoder

@case("R1 an HTML body is rejected, never decoded as market data")
def _():
    try:
        decoder.decode("<html>NOT MARKET DATA</html>", url="u",
                       expected_symbol="SZ000001", kind="stock")
    except decoder.DecodeError as exc:
        assert "markup" in str(exc)
        return
    raise AssertionError("HTML accepted")


@case("R1 malformed JSON is rejected")
def _():
    try:
        decoder.decode("{not json", url="u", expected_symbol="SZ000001", kind="stock")
    except decoder.DecodeError:
        return
    raise AssertionError("malformed JSON accepted")


@case("R1 a response for a different security is rejected")
def _():
    try:
        decoder.decode(envelope("SH600000", ROWS_HAND), url="u",
                       expected_symbol="SZ000001", kind="stock")
    except decoder.DecodeError as exc:
        assert "not the requested" in str(exc)
        return
    raise AssertionError("symbol mismatch accepted")


@case("R1 an unsupported schema is rejected")
def _():
    try:
        decoder.decode(envelope("SZ000001", ROWS_HAND, schema="something.else"),
                       url="u", expected_symbol="SZ000001", kind="stock")
    except decoder.DecodeError as exc:
        assert "unsupported schema" in str(exc)
        return
    raise AssertionError("unknown schema accepted")


@case("R1 the real Sina JS payload is KNOWN-UNSUPPORTED and fails closed")
def _():
    try:
        decoder.decode(envelope("SZ000001", ROWS_HAND, schema=decoder.SINA_KLC_JS),
                       url="u", expected_symbol="SZ000001", kind="stock")
    except decoder.DecodeError as exc:
        assert "KNOWN-UNSUPPORTED" in str(exc)
        return
    raise AssertionError("unimplemented decoder silently guessed")


@case("R1 a missing basis declaration is rejected")
def _():
    body = json.dumps({"schema": decoder.SUPPORTED_SCHEMA, "symbol": "SZ000001",
                       "rows": ROWS_HAND})
    try:
        decoder.decode(body, url="u", expected_symbol="SZ000001", kind="stock")
    except decoder.DecodeError as exc:
        assert "no adjustment basis" in str(exc)
        return
    raise AssertionError("missing basis accepted")


@case("R1 malformed dates and duplicate dates are rejected")
def _():
    for rows, hint in (([dict(ROWS_HAND[0], date="2025-13-99")], "impossible date"),
                       (ROWS_HAND + ROWS_HAND, "repeats date")):
        try:
            decoder.decode(envelope("SZ000001", rows), url="u",
                           expected_symbol="SZ000001", kind="stock")
        except decoder.DecodeError as exc:
            assert hint in str(exc), exc
            continue
        raise AssertionError("bad rows accepted: %s" % hint)


@case("R1 a stock row missing amount is rejected")
def _():
    try:
        decoder.decode(envelope("SZ000001", price_rows(["2025-06-10"], with_amount=False)),
                       url="u", expected_symbol="SZ000001", kind="stock")
    except decoder.DecodeError as exc:
        assert "missing" in str(exc)
        return
    raise AssertionError("amount-less stock row accepted")


@case("R1 the two stock responses must agree on basis and dates")
def _():
    hist = decoder.decode(envelope("SZ000001", ROWS_HAND), url="h",
                          expected_symbol="SZ000001", kind="stock")
    other = decoder.decode(envelope("SZ000001", ROWS_HAND, basis="qfq"), url="a",
                           expected_symbol="SZ000001", kind="stock")
    try:
        decoder.merge_stock_responses(hist, other)
    except decoder.DecodeError as exc:
        assert "different bases" in str(exc)
        return
    raise AssertionError("mismatched bases merged")


@case("R1 the body hash is recorded for lineage")
def _():
    d = decoder.decode(envelope("SZ000001", ROWS_HAND), url="u",
                       expected_symbol="SZ000001", kind="stock")
    assert len(d.body_sha256) == 64 and d.byte_length > 0


# =============================================================== R1 provenance

@case("R1 exact raw path plus a corroborating declared basis yields 'none'")
def _():
    urls = prov.expected_urls("SZ000001", "stock")
    p = prov.derive("SZ000001", "stock", urls, ROWS_HAND, "sina", declared_basis="none")
    assert p.adjustment_mode == prov.RAW, p


@case("R1 a right path with a payload declaring qfq is UNKNOWN, not 'none'")
def _():
    urls = prov.expected_urls("SZ000001", "stock")
    p = prov.derive("SZ000001", "stock", urls, ROWS_HAND, "sina", declared_basis="qfq")
    assert p.adjustment_mode == prov.UNKNOWN and "disagree" in p.evidence["adjustment_reason"]


@case("R1 an uncorroborated path (no payload basis) is UNKNOWN")
def _():
    urls = prov.expected_urls("SZ000001", "stock")
    p = prov.derive("SZ000001", "stock", urls, ROWS_HAND, "sina")
    assert p.adjustment_mode == prov.UNKNOWN


@case("R1 an EXTRA url yields 'unknown', never 'none'")
def _():
    urls = list(prov.expected_urls("SZ000001", "stock")) + ["https://x/qfq.js"]
    p = prov.derive("SZ000001", "stock", urls, ROWS_HAND, "sina", declared_basis="none")
    assert p.adjustment_mode == prov.UNKNOWN


@case("R1 unknown data can NEVER be relabelled 'none'")
def _():
    p = prov.derive("SZ000001", "stock", ["https://elsewhere/x"], ROWS_HAND, "sina",
                    declared_basis="none")
    try:
        p.require_basis("none")
    except prov.ProvenanceError as exc:
        assert "UNKNOWN" in str(exc)
        return
    raise AssertionError("relabelling was allowed")


@case("R1 units 'hand' and 'share' are derived, ambiguity is unknown")
def _():
    assert prov.derive_unit(ROWS_HAND)[0] == "hand"
    assert prov.derive_unit(ROWS_SHARE)[0] == "share"
    assert prov.derive_unit([dict(ROWS_HAND[0], amount=7.0)])[0] == prov.UNKNOWN
    assert prov.derive_unit([dict(ROWS_HAND[0], amount=None)])[0] == prov.UNKNOWN


@case("R1 benchmark routed distinctly: unit unknown, basis still checked")
def _():
    rows = [{k: v for k, v in ROWS_HAND[0].items() if k != "amount"}]
    p = prov.derive("SH000300", "benchmark",
                    prov.expected_urls("SH000300", "benchmark"), rows, "sina",
                    declared_basis="none")
    assert p.volume_unit == prov.UNKNOWN and p.adjustment_mode == prov.RAW


# =============================================================== R3 transport

@case("R3 pacing is applied on EVERY attempt, including both internal GETs")
def _():
    t = paced(fake())
    for url in prov.expected_urls("SZ000001", "stock"):
        t.get(url, source="sina")
    assert t.attempt_count == 2
    assert abs(t.sleeper.waits[0] - t.min_interval) < 1e-9


@case("R3 finite connect/read timeouts are passed on every attempt")
def _():
    f = fake()
    paced(f).get("https://x/1", source="sina")
    assert f.state["calls"][0]["timeout"] == (tp.CONNECT_TIMEOUT, tp.READ_TIMEOUT)


@case("R3 an INFINITE timeout is rejected by the constructor")
def _():
    for kw in ({"connect_timeout": float("inf")}, {"read_timeout": float("nan")},
               {"min_interval": float("inf")}):
        try:
            paced(fake(), **kw)
        except ValueError as exc:
            assert "finite" in str(exc)
            continue
        raise AssertionError("accepted %s" % kw)


@case("R3 a non-positive or non-integer ceiling is rejected")
def _():
    for bad in (0, -5, 2.5):
        try:
            paced(fake(), ceiling=bad)
        except ValueError:
            continue
        raise AssertionError("accepted ceiling %r" % bad)


@case("R3 redirects are not followed and are surfaced as a failure")
def _():
    f = fake(status=302, location="https://elsewhere/x")
    try:
        paced(f).get("https://x/1", source="sina")
    except tp.TransportError as exc:
        assert not exc.retryable and f.state["calls"][0]["allow_redirects"] is False
        return
    raise AssertionError("redirect followed")


@case("R3 403 and 429 stop the run immediately and are never retried")
def _():
    for status in (403, 429):
        f = fake(status=status)
        try:
            paced(f).get_with_retries("https://x/1", source="sina")
        except tp.RunAborted:
            assert len(f.state["calls"]) == 1
            continue
        raise AssertionError("%d did not abort" % status)


@case("R3 a RunAborted from the transport is STICKY and never retried")
def _():
    f = fake(raises=tp.RunAborted("vendor said stop"))
    t = paced(f)
    try:
        t.get_with_retries("https://x/1", source="sina")
    except tp.RunAborted:
        assert len(f.state["calls"]) == 1, f.state["calls"]
        return
    raise AssertionError("RunAborted was downgraded and retried")


@case("R3 a ValueError is NOT retried: it is not transient I/O")
def _():
    f = fake(raises=ValueError("bad parse"))
    try:
        paced(f).get_with_retries("https://x/1", source="sina")
    except tp.TransportError as exc:
        assert not exc.retryable and len(f.state["calls"]) == 1, f.state["calls"]
        return
    raise AssertionError("ValueError retried")


@case("R3 a genuine transient error IS retried, bounded")
def _():
    f = fake(raises=ConnectionError("reset"))
    try:
        paced(f).get_with_retries("https://x/1", source="sina", max_attempts=3)
    except tp.TransportError:
        assert len(f.state["calls"]) == 3
        return
    raise AssertionError("transient not retried")


@case("R3 the global attempt ceiling aborts the run")
def _():
    t = paced(fake(), ceiling=3)
    for i in range(3):
        t.get("https://x/%d" % i, source="sina")
    try:
        t.get("https://x/4", source="sina")
    except tp.RunAborted as exc:
        assert "ceiling" in str(exc)
        return
    raise AssertionError("ceiling not enforced")


@case("R3 hidden library retries are rejected AT CONSTRUCTION, not just by a helper")
def _():
    class Adapter:
        class R:
            total = 3
            redirect = 0
        max_retries = R()

    class Session:
        adapters = {"https://": Adapter()}

    try:
        paced(fake(), session=Session())
    except tp.RunAborted as exc:
        assert "library-level retries" in str(exc)
        return
    raise AssertionError("session with hidden retries accepted")


@case("R3 the live transport refuses to run in M2a")
def _():
    try:
        tp.LiveTransport()("https://x", timeout=(1, 1), allow_redirects=False)
    except tp.RunAborted as exc:
        assert "not armed" in str(exc)
        return
    raise AssertionError("live transport ran")


# =============================================================== R2 acceptance

def gate_text(rows, verdict_ids=None):
    lines = ["staging validation", ""]
    width = max(len(d) for _, d, _, _ in rows)
    for gid, desc, status, required in rows:
        flag = "" if required else "  (advisory)"
        lines.append("  %-10s %-*s %-14s%s" % (gid, width, desc, status, flag))
        lines.append("             detail for %s" % gid)
    failing = [g for g, _, s, r in rows if r and s not in acc.SUCCESSFUL]
    ids = failing if verdict_ids is None else verdict_ids
    lines += ["", "  summary: {}"]
    lines.append("  RESULT: FAILED - %d required gate(s) not satisfied: %s"
                 % (len(ids), ", ".join(ids)) if ids else
                 "  RESULT: SUCCEEDED - all required gates PASS/NOT_APPLICABLE")
    return "\n".join(lines), (1 if ids else 0)


def full_rows(inventory, overrides=None):
    overrides = overrides or {}
    rows = []
    for gid in inventory:
        status, required = overrides.get(gid, ("PASS", True))
        rows.append((gid, "gate %s" % gid, status, required))
    return rows


@case("R2 a run reporting only P4=PASS is REJECTED (inventory is internal)")
def _():
    text, code = gate_text([("P4", "units", "PASS", True)])
    try:
        acc.accept_research(text, code, candidate_fingerprint="fp", **pins())
    except acc.AcceptanceError as exc:
        assert "mandatory gates absent" in str(exc)
        return
    raise AssertionError("partial gate set accepted")


@case("R2 a mandatory gate marked advisory is REJECTED")
def _():
    text, code = gate_text(full_rows(acc.RESEARCH_REQUIRED,
                                     {"P4": ("UNKNOWN", False)}))
    try:
        acc.accept_research(text, code, candidate_fingerprint="fp", **pins())
    except acc.AcceptanceError as exc:
        assert "ran as advisory" in str(exc)
        return
    raise AssertionError("weakened requiredness accepted")


@case("R2 a duplicated gate is REJECTED")
def _():
    rows = full_rows(acc.RESEARCH_REQUIRED) + [("P4", "gate P4", "FAIL", True)]
    text, code = gate_text(rows, verdict_ids=["P4"])
    try:
        acc.accept_research(text, code, candidate_fingerprint="fp", **pins())
    except acc.AcceptanceError as exc:
        assert "more than once" in str(exc)
        return
    raise AssertionError("duplicate gate accepted")


@case("R2 a complete research run is accepted")
def _():
    text, code = gate_text(full_rows(acc.RESEARCH_REQUIRED))
    v = acc.accept_research(text, code, candidate_fingerprint="fp", **pins())
    assert v.accepted, v.reason


@case("R2 a reduced population is REJECTED even with the same 14 short securities")
def _():
    with tempfile.TemporaryDirectory() as d:
        man = Path(d) / "reduced.csv"
        man.write_text("symbol,stratum,list_date,delist_date\n"
                       + "".join("%s,ordinary_control,2026-01-05,\n" % s
                                 for s in acc.PINNED_SHORTFALL)
                       + "SH000300,benchmark,,\nSH000001,benchmark,,\n", encoding="utf-8")
        text, code = gate_text(full_rows(acc.RESEARCH_REQUIRED))
        try:
            acc.accept_research(text, code, candidate_fingerprint="fp", **pins(man))
        except acc.AcceptanceError as exc:
            assert "reduced population" in str(exc)
            return
    raise AssertionError("reduced population accepted")


@case("R2 a changed manifest hash is REJECTED")
def _():
    text, code = gate_text(full_rows(acc.RESEARCH_REQUIRED))
    try:
        acc.accept_research(text, code, candidate_fingerprint="fp",
                            **dict(pins(), expected_manifest_sha="deadbeef" * 8))
    except acc.AcceptanceError as exc:
        assert "does not match the pinned" in str(exc)
        return
    raise AssertionError("changed manifest accepted")


def warmup_fixture(tmp, shortfall_override=None):
    warm = acc.warmup_interval()
    pinned = dict(acc.PINNED_SHORTFALL)
    lines = ["symbol,stratum,list_date,delist_date"]
    plan, ready = {}, ["SH600000", "SZ000001"]
    for sym in ready:
        lines.append("%s,ordinary_control,2000-01-04," % sym)
        plan[sym] = list(warm)
    for sym, n in pinned.items():
        lines.append("%s,ordinary_control,%s," % (
            sym, "2026-01-05" if n == 0 else warm[len(warm) - n]))
        plan[sym] = list(warm[len(warm) - n:]) if n else []
    lines.append("SH000300,benchmark,,")
    man = tmp / "warm_manifest.csv"
    man.write_text("\n".join(lines) + "\n", encoding="utf-8")
    db = tmp / "warm_trading.sqlite3"
    conn = sqlite3.connect(db)
    conn.executescript(runner.TRADING_DDL)
    for sym, days in plan.items():
        for d in days:
            conn.execute("INSERT INTO daily_bar_cache VALUES "
                         "(?,?,10,11,9,10.5,1000,1050000,'sina','ready','none','hand')",
                         (sym, d))
    if shortfall_override:
        for sym, drop in shortfall_override.items():
            conn.execute("DELETE FROM daily_bar_cache WHERE symbol=? AND trade_date IN "
                         "(SELECT trade_date FROM daily_bar_cache WHERE symbol=? "
                         " ORDER BY trade_date DESC LIMIT ?)", (sym, sym, drop))
    conn.commit(); conn.close()
    return man, db


WARM_OK = {"V3b": ("FAIL", True)}


@case("R2 warm-up collection accepted when only the pinned depth shortfall fails")
def _():
    with tempfile.TemporaryDirectory() as d:
        man, db = warmup_fixture(Path(d))
        text, code = gate_text(full_rows(acc.WARMUP_REQUIRED, WARM_OK))
        v = acc._warmup_decision(acc.parse_gate_output(text, code), man, db, None, {})
        assert v.accepted and "NOT feature readiness" in v.reason, v.reason


@case("R2 V3b ABSENT is rejected")
def _():
    with tempfile.TemporaryDirectory() as d:
        man, db = warmup_fixture(Path(d))
        inv = tuple(g for g in acc.WARMUP_REQUIRED if g != "V3b")
        text, code = gate_text(full_rows(inv))
        v = acc._warmup_decision(acc.parse_gate_output(text, code), man, db, None, {})
        assert not v.accepted and "absent" in v.reason, v.reason


@case("R2 V3b=UNKNOWN is rejected: not a known IPO depth limitation")
def _():
    with tempfile.TemporaryDirectory() as d:
        man, db = warmup_fixture(Path(d))
        text, code = gate_text(full_rows(acc.WARMUP_REQUIRED, {"V3b": ("UNKNOWN", True)}))
        v = acc._warmup_decision(acc.parse_gate_output(text, code), man, db, None, {})
        assert not v.accepted and "UNKNOWN is missing evidence" in v.reason, v.reason


@case("R2 V3b marked advisory is rejected")
def _():
    with tempfile.TemporaryDirectory() as d:
        man, db = warmup_fixture(Path(d))
        text, code = gate_text(full_rows(acc.WARMUP_REQUIRED, {"V3b": ("FAIL", False)}),
                               verdict_ids=[])
        v = acc._warmup_decision(acc.parse_gate_output(text, code), man, db, None, {})
        assert not v.accepted and "advisory" in v.reason, v.reason


@case("R2 an integrity FAIL is rejected (exit 1 alone is insufficient)")
def _():
    with tempfile.TemporaryDirectory() as d:
        man, db = warmup_fixture(Path(d))
        text, code = gate_text(full_rows(acc.WARMUP_REQUIRED,
                                         dict(WARM_OK, W1_pricing=("FAIL", True))))
        v = acc._warmup_decision(acc.parse_gate_output(text, code), man, db, None, {})
        assert not v.accepted and "W1_pricing" in v.reason, v.reason


@case("R2 an unexpected shortfall security or wrong count is rejected")
def _():
    for override, hint in (({"SH600000": 5}, "SH600000"), ({"BJ920001": 3}, "count")):
        with tempfile.TemporaryDirectory() as d:
            man, db = warmup_fixture(Path(d), shortfall_override=override)
            text, code = gate_text(full_rows(acc.WARMUP_REQUIRED, WARM_OK))
            v = acc._warmup_decision(acc.parse_gate_output(text, code), man, db, None, {})
            assert not v.accepted, (override, v.reason)


@case("R2 the complete shortfall is 14 securities, not a 3-row sample")
def _():
    with tempfile.TemporaryDirectory() as d:
        man, db = warmup_fixture(Path(d))
        shortfall, ready = acc.compute_full_shortfall(man, db)
        assert len(shortfall) == 14 and set(shortfall) == set(acc.PINNED_SHORTFALL)


@case("R2 parse failures still fail closed")
def _():
    for text, code, hint in (("nothing here", 0, "no gate lines"),
                             (gate_text(full_rows(acc.RESEARCH_REQUIRED))[0], 1, "exit code")):
        try:
            acc.parse_gate_output(text, code)
        except acc.AcceptanceError as exc:
            assert hint in str(exc), exc
            continue
        raise AssertionError("bad parse accepted: %s" % hint)


# =============================================================== R4 staging safety

def small_manifest(tmp, stocks=("SZ000001",), marks=("SH000300",)):
    man = tmp / "m.csv"
    lines = ["symbol,stratum,list_date,delist_date"]
    lines += ["%s,ordinary_control,2000-01-04," % s for s in stocks]
    lines += ["%s,benchmark,," % m for m in marks]
    man.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return man


def make_runner(tmp, run_id="001", root=None):
    return runner.PilotRunner(small_manifest(tmp), root or (tmp / "staging"),
                              [("archive-trading", PROD[0]), ("calendar", CALENDAR)],
                              run_id=run_id)


@case("R4 plan() is the default and writes nothing")
def _():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        r = make_runner(d)
        budget = r.plan()
        assert not (d / "staging").exists()
        assert budget.http_attempts_min == 3, budget


@case("R4 trading and history resolving to the SAME file is rejected")
def _():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        same = d / "staging" / "one.sqlite3"
        try:
            runner.guard_paths(d / "staging", {"trading": same, "history": same}, [])
        except runner.StagingSafetyError as exc:
            assert "collision" in str(exc)
            return
    raise AssertionError("same destination accepted")


@case("R4 one destination equal to another's .partial is rejected")
def _():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        root = d / "staging"
        try:
            runner.guard_paths(root, {"trading": root / "a.sqlite3",
                                      "history": root / "a.sqlite3.partial"}, [])
        except runner.StagingSafetyError as exc:
            assert "collision" in str(exc)
            return
    raise AssertionError("final/partial collision accepted")


@case("R4 a destination aliasing production, or outside the root, is rejected")
def _():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        for dests, hint in (({"trading": PROD[0], "history": d / "staging" / "h.db"},
                             "protected"),
                            ({"trading": d / "outside.db", "history": d / "staging" / "h.db"},
                             "outside")):
            try:
                runner.guard_paths(d / "staging", dests, [("archive-trading", PROD[0])])
            except runner.StagingSafetyError as exc:
                assert hint in str(exc), exc
                continue
            raise AssertionError("accepted %s" % hint)


@case("R4 a staging root containing a protected input is rejected")
def _():
    try:
        runner.PilotRunner(REAL_MANIFEST, ROOT, [("archive-trading", PROD[0])],
                           run_id="x")
    except runner.StagingSafetyError as exc:
        assert "contain or alias" in str(exc)
        return
    raise AssertionError("root containing production accepted")


@case("R4 collect() refuses unless armed and paced")
def _():
    with tempfile.TemporaryDirectory() as d:
        r = make_runner(Path(d))
        for kw, hint in (({"armed": False}, "not armed"),
                         ({"armed": True, "transport": None}, "PacedTransport")):
            try:
                r.collect(kw.get("transport"), armed=kw["armed"])
            except tp.RunAborted as exc:
                assert hint in str(exc), exc
                continue
            raise AssertionError("ran with %s" % kw)


@case("R4 an existing run directory is refused, never reused")
def _():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        r = make_runner(d)
        r.run_dir.mkdir(parents=True)
        try:
            r.collect(paced(fake()), armed=True)
        except runner.StagingSafetyError as exc:
            assert "already exists" in str(exc)
            return
    raise AssertionError("run directory reused")


@case("R4 ALL jobs failing reports completed_with_failures, never completed")
def _():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        r = make_runner(d)
        out = r.collect(paced(fake(status=404)), armed=True)
        assert out["status"] == "completed_with_failures", out["status"]
        assert out["collection_complete"] is False and out["published"] is False
        assert out["jobs_ok"] == 0 and out["jobs_failed"] == 2, out


@case("R4 20 consecutive job failures stop the run")
def _():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        man = small_manifest(d, stocks=tuple("SZ%06d" % i for i in range(1, 31)))
        r = runner.PilotRunner(man, d / "staging",
                               [("calendar", CALENDAR)], run_id="stop")
        out = r.collect(paced(fake(status=404), ceiling=500), armed=True)
        assert out["status"] == "aborted" and "consecutive" in out["reason"], out
        assert len(out["outcomes"]) == runner.CONSECUTIVE_FAILURE_STOP, len(out["outcomes"])


@case("R4 publication is refused for an incomplete collection")
def _():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        r = make_runner(d)
        out = r.collect(paced(fake(status=404)), armed=True)
        pub = r.finalize(out, both_receipts(out))
        assert pub["published"] is False and "not complete" in pub["reason"], pub
        assert not (r.root / runner.POINTER).exists()


@case("R4 publication is refused when acceptance did not succeed")
def _():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        r = make_runner(d)
        bodies = good_bodies(["SZ000001"], ["SH000300"], WINDOW[:5])
        out = r.collect(paced(fake(bodies=bodies)), armed=True)
        assert out["collection_complete"], out
        pub = r.finalize(out, both_receipts(out, accepted=False))
        assert pub["published"] is False and "validation did not succeed" in pub["reason"]
        assert not (r.root / runner.POINTER).exists()


@case("R4 a failed publication of run 2 leaves run 1 intact and still pointed to")
def _():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        bodies = good_bodies(["SZ000001"], ["SH000300"], WINDOW[:5])
        r1 = make_runner(d, run_id="001")
        out1 = r1.collect(paced(fake(bodies=bodies)), armed=True)
        pub1 = r1.finalize(out1, both_receipts(out1))
        assert pub1["published"], pub1

        r2 = runner.PilotRunner(small_manifest(d), d / "staging",
                                [("calendar", CALENDAR)], run_id="002")
        out2 = r2.collect(paced(fake(status=404)), armed=True)
        pub2 = r2.finalize(out2, both_receipts(out2))
        assert pub2["published"] is False
        pointer = json.loads((r1.root / runner.POINTER).read_text(encoding="utf-8"))
        assert pointer["run_id"] == "001", pointer
        assert Path(pointer["trading"]).exists() and Path(pointer["history"]).exists()


# =============================================================== INT integrated chain

def good_bodies(stocks, marks, dates):
    bodies = {}
    for sym in stocks:
        hist, amount = prov.expected_urls(sym, "stock")
        bodies[hist] = envelope(sym, price_rows(dates))
        bodies[amount] = envelope(sym, price_rows(dates))
    for sym in marks:
        (idx,) = prov.expected_urls(sym, "benchmark")
        bodies[idx] = envelope(sym, [{k: v for k, v in r.items() if k != "amount"}
                                     for r in price_rows(dates)])
    return bodies


def build_archives(tmp):
    at, ah = tmp / "arch_t.sqlite3", tmp / "arch_h.sqlite3"
    for path, ddl in ((at, runner.TRADING_DDL), (ah, runner.HISTORY_DDL)):
        conn = sqlite3.connect(path)
        conn.executescript(ddl)
        conn.commit(); conn.close()
    return at, ah


def run_m1_gate(stag_t, stag_h, at, ah, man, baseline, extra=()):
    import contextlib
    import io as _io
    buf = _io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        code = staging_gate.main(
            ["validate", "--staging-trading", str(stag_t), "--staging-history", str(stag_h),
             "--archive-trading", str(at), "--archive-history", str(ah),
             "--pilot-manifest", str(man), "--calendar", str(CALENDAR),
             "--baseline", str(baseline), "--pricing-basis", "none",
             "--history-basis", "none", "--transformation", "identity"] + list(extra))
    return code, buf.getvalue()


@case("INT good bodies: fake transport -> decoder -> staging -> real M1 gate -> acceptance")
def _():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        man = small_manifest(d)
        at, ah = build_archives(d)
        baseline = d / "baseline.json"
        import contextlib
        import io as _io
        with contextlib.redirect_stdout(_io.StringIO()):
            staging_gate.main(["snapshot", "--archive-trading", str(at),
                               "--archive-history", str(ah), "--calendar", str(CALENDAR),
                               "--baseline-out", str(baseline)])
        r = runner.PilotRunner(man, d / "staging", [("calendar", CALENDAR)], run_id="int")
        bodies = good_bodies(["SZ000001"], ["SH000300"], WINDOW)
        out = r.collect(paced(fake(bodies=bodies), ceiling=50), armed=True)
        assert out["collection_complete"], [o.reason for o in out["outcomes"]]
        code, text = run_m1_gate(r.destinations["trading"], r.destinations["history"],
                                 at, ah, man, baseline)
        assert code == 0, text[-1500:]
        # The reduced fixture deliberately does NOT touch the public acceptance
        # boundary, which mandates the approved 50+2 population. The FULL case below
        # exercises that boundary with enforcement on and no bypasses.
        acc.enforce_inventory(acc.parse_gate_output(text, code), acc.RESEARCH_REQUIRED)
        pub = r.finalize(out, both_receipts(out))
        assert pub["published"], pub


@case("INT HTML bodies: no successful job, no publication, and the gate never sees rows")
def _():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        man = small_manifest(d)
        r = runner.PilotRunner(man, d / "staging", [("calendar", CALENDAR)], run_id="html")
        out = r.collect(paced(fake(text="<html>NOT MARKET DATA</html>")), armed=True)
        assert out["jobs_ok"] == 0, out
        assert all(o.status == "rejected" and "markup" in o.reason
                   for o in out["outcomes"]), [o.reason for o in out["outcomes"]]
        assert out["collection_complete"] is False and out["published"] is False
        conn = sqlite3.connect(r.destinations["trading"])
        n = conn.execute("SELECT COUNT(*) FROM daily_bar_cache").fetchone()[0]
        conn.close()
        assert n == 0, n
        assert r.finalize(out, both_receipts(out))["published"] is False


@case("INT a qfq-declaring payload on the raw path is rejected, not stored as 'none'")
def _():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        man = small_manifest(d)
        r = runner.PilotRunner(man, d / "staging", [("calendar", CALENDAR)], run_id="qfq")
        bodies = {}
        for sym in ("SZ000001",):
            hist, amount = prov.expected_urls(sym, "stock")
            bodies[hist] = envelope(sym, price_rows(WINDOW[:5]), basis="qfq")
            bodies[amount] = envelope(sym, price_rows(WINDOW[:5]), basis="qfq")
        (idx,) = prov.expected_urls("SH000300", "benchmark")
        bodies[idx] = envelope("SH000300", price_rows(WINDOW[:5]), basis="qfq")
        out = r.collect(paced(fake(bodies=bodies)), armed=True)
        assert out["jobs_ok"] == 0, out
        assert all("UNKNOWN" in o.reason for o in out["outcomes"]), \
            [o.reason for o in out["outcomes"]]
        conn = sqlite3.connect(r.destinations["trading"])
        n = conn.execute("SELECT COUNT(*) FROM daily_bar_cache").fetchone()[0]
        conn.close()
        assert n == 0


@case("INT provenance rows record body hash, run id and fixture mode, not live provenance")
def _():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        man = small_manifest(d)
        r = runner.PilotRunner(man, d / "staging", [("calendar", CALENDAR)], run_id="prov")
        out = r.collect(paced(fake(bodies=good_bodies(["SZ000001"], ["SH000300"],
                                                      WINDOW[:5]))), armed=True)
        assert out["collection_complete"]
        conn = sqlite3.connect(r.destinations["trading"])
        rows = conn.execute("SELECT body_sha256, run_id, run_mode, lineage "
                            "FROM ingest_provenance").fetchall()
        conn.close()
        assert rows and all(len(x[0]) == 64 for x in rows)
        assert all(x[2] == runner.FIXTURE_MODE for x in rows), rows[0]
        assert "NOT independent source corroboration" in rows[0][3]
        hc = sqlite3.connect(r.destinations["history"])
        stamps = {x[0] for x in hc.execute("SELECT DISTINCT fetched_at FROM daily_bars")}
        modes = {x[0] for x in hc.execute("SELECT run_mode FROM ingest_runs")}
        hc.close()
        assert all(runner.FIXTURE_MODE in s for s in stamps), stamps
        assert modes == {runner.FIXTURE_MODE}, modes


@case("R4 production databases are untouched by the whole suite")
def _():
    assert runner.production_fingerprint(PROD) == PROD_BEFORE


PROD_BEFORE = runner.production_fingerprint(PROD)

# =============================================== C: the seven closure counterexamples

def receipt(collection, mode, accepted=True, run_id=None, fingerprint="__use__",
            manifest_sha="m", calendar_sha="c"):
    """A directly constructed receipt, for tests whose subject is PUBLICATION.

    Tests about binding itself use the real `validate_candidate` path instead.
    """
    return runner.ValidationReceipt(
        mode=mode, run_id=run_id or collection["run_id"],
        candidate_fingerprint=(collection["candidate_fingerprint"]
                               if fingerprint == "__use__" else fingerprint),
        manifest_sha=manifest_sha, calendar_sha=calendar_sha,
        gate_exit=0 if accepted else 1, accepted=accepted,
        reason="" if accepted else "gate failed")


def both_receipts(collection, accepted=True):
    return [receipt(collection, m, accepted) for m in runner.REQUIRED_MODES]


@case("C-R1 the runner-level response-body override no longer exists")
def _():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        man = small_manifest(d)
        r = runner.PilotRunner(man, d / "staging", [("calendar", CALENDAR)], run_id="ovr")
        bodies = good_bodies(["SZ000001"], ["SH000300"], WINDOW[:5])
        try:
            r.collect(paced(fake(text=HTML)), armed=True, responses=bodies)
        except TypeError as exc:
            assert "responses" in str(exc), exc
        else:
            raise AssertionError("collect() still accepts a body override")
        out = r.collect(paced(fake(text=HTML)), armed=True)
        assert out["jobs_ok"] == 0 and out["collection_complete"] is False
        conn = sqlite3.connect(r.destinations["trading"])
        assert conn.execute("SELECT COUNT(*) FROM daily_bar_cache").fetchone()[0] == 0
        conn.close()


@case("C-R2a the public research path has no enforce bypass")
def _():
    text, code = gate_text([("P4", "units", "PASS", True)])
    try:
        acc.accept_research(text, code, enforce=False, candidate_fingerprint="fp",
                            **pins())
    except TypeError as exc:
        assert "enforce" in str(exc), exc
        return
    raise AssertionError("enforce bypass still present")


@case("C-R2b a swapped-symbol manifest with the same 50+2 counts is REJECTED")
def _():
    with tempfile.TemporaryDirectory() as d:
        man = Path(d) / "swapped.csv"
        man.write_text(REAL_MANIFEST.read_text(encoding="utf-8")
                       .replace("SH688001", "SH600998"), encoding="utf-8")
        text, code = gate_text(full_rows(acc.RESEARCH_REQUIRED))
        try:
            acc.accept_research(text, code, candidate_fingerprint="fp",
                                manifest_path=man,
                                expected_manifest_sha=sha(REAL_MANIFEST),
                                calendar_path=CALENDAR,
                                expected_calendar_sha=sha(CALENDAR))
        except acc.AcceptanceError as exc:
            assert "does not match the pinned" in str(exc)
            return
    raise AssertionError("swapped manifest accepted")


@case("C-R2c conflicting RESULT verdicts are REJECTED, not resolved by taking the last")
def _():
    text, _ = gate_text(full_rows(acc.RESEARCH_REQUIRED))
    conflicted = text.replace(
        "  RESULT: SUCCEEDED",
        "  RESULT: FAILED - 1 required gate(s) not satisfied: P4\n  RESULT: SUCCEEDED", 1)
    try:
        acc.parse_gate_output(conflicted, 0)
    except acc.AcceptanceError as exc:
        assert "conflicting verdicts" in str(exc), exc
        return
    raise AssertionError("conflicting verdicts accepted")


@case("C-R2d a mandatory binding cannot be omitted")
def _():
    text, code = gate_text(full_rows(acc.RESEARCH_REQUIRED))
    try:
        acc.accept_research(text, code, candidate_fingerprint=None, **pins())
    except acc.AcceptanceError as exc:
        assert "mandatory" in str(exc)
        return
    raise AssertionError("missing candidate binding accepted")


@case("C-R2e run A's collection cannot be published by a runner that never collected")
def _():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        man = small_manifest(d)
        bodies = good_bodies(["SZ000001"], ["SH000300"], WINDOW[:5])
        a = runner.PilotRunner(man, d / "staging", [("calendar", CALENDAR)], run_id="A")
        out = a.collect(paced(fake(bodies=bodies)), armed=True)
        assert out["collection_complete"]
        b = runner.PilotRunner(man, d / "staging", [("calendar", CALENDAR)], run_id="B")
        pub = b.finalize(out, both_receipts(out))
        assert pub["published"] is False and "belongs to run" in pub["reason"], pub
        assert not (b.root / runner.POINTER).exists()


@case("C-R2f a candidate changed after validation cannot ride that validation")
def _():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        man = small_manifest(d)
        r = runner.PilotRunner(man, d / "staging", [("calendar", CALENDAR)], run_id="mut")
        out = r.collect(paced(fake(bodies=good_bodies(["SZ000001"], ["SH000300"],
                                                      WINDOW[:5]))), armed=True)
        conn = sqlite3.connect(r.destinations["trading"])
        conn.execute("INSERT INTO daily_bar_cache VALUES "
                     "('SZ000001','2099-01-01',1,1,1,1,1,1,'x','ready','none','hand')")
        conn.commit(); conn.close()
        pub = r.finalize(out, both_receipts(out))
        assert pub["published"] is False and "changed after collection" in pub["reason"], pub


@case("C-R2g a verdict issued against another candidate is refused")
def _():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        man = small_manifest(d)
        r = runner.PilotRunner(man, d / "staging", [("calendar", CALENDAR)], run_id="bind")
        out = r.collect(paced(fake(bodies=good_bodies(["SZ000001"], ["SH000300"],
                                                      WINDOW[:5]))), armed=True)
        pub = r.finalize(out, [receipt(out, "research", fingerprint="other-candidate"),
                         receipt(out, "warmup_collection")])
        assert pub["published"] is False and "issued against candidate" in pub["reason"], pub


@case("C-R3 a transport-raised RunAborted is STICKY across a later call")
def _():
    f = fake(sequence=[tp.RunAborted("vendor said stop"), 200])
    t = paced(f)
    try:
        t.get("https://x/1", source="sina")
    except tp.RunAborted:
        pass
    assert t.aborted_reason, "abort reason was not latched"
    before = t.attempt_count
    try:
        t.get("https://x/2", source="sina")
    except tp.RunAborted:
        assert t.attempt_count == before, t.attempt_count
        assert len(f.state["calls"]) == 1, f.state["calls"]
        return
    raise AssertionError("a later call after an inner abort succeeded")


@case("C-R4a a pre-existing alias at the pointer temp is refused at construction")
def _():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        man = small_manifest(d)
        sentinel = d / "protected_sentinel.txt"
        sentinel.write_text("DO NOT OVERWRITE", encoding="utf-8")
        root = d / "staging"
        root.mkdir()
        try:
            os.link(sentinel, root / ("%s.ln.tmp" % runner.POINTER))
        except OSError:
            return                      # filesystem cannot hardlink; nothing to prove
        try:
            runner.PilotRunner(man, root, [("calendar", CALENDAR),
                                           ("synthetic-input", sentinel)], run_id="ln")
        except runner.StagingSafetyError as exc:
            assert "publication role" in str(exc), exc
            assert sentinel.read_text(encoding="utf-8") == "DO NOT OVERWRITE"
            return
    raise AssertionError("aliased pointer temp accepted")


@case("C-R4b an unowned pointer temp is refused, not followed or deleted")
def _():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        man = small_manifest(d)
        r = runner.PilotRunner(man, d / "staging", [("calendar", CALENDAR)], run_id="own")
        out = r.collect(paced(fake(bodies=good_bodies(["SZ000001"], ["SH000300"],
                                                      WINDOW[:5]))), armed=True)
        r.pointer_tmp.write_text("someone else's file", encoding="utf-8")
        pub = r.finalize(out, both_receipts(out))
        assert pub["published"] is False and "already exists" in pub["reason"], pub
        assert r.pointer_tmp.read_text(encoding="utf-8") == "someone else's file"
        assert not r.pointer.exists()


@case("C-R4c a pointer replace failure preserves the previous pointer and pair")
def _():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        man = small_manifest(d)
        bodies = good_bodies(["SZ000001"], ["SH000300"], WINDOW[:5])
        r1 = runner.PilotRunner(man, d / "staging", [("calendar", CALENDAR)], run_id="p1")
        o1 = r1.collect(paced(fake(bodies=bodies)), armed=True)
        assert r1.finalize(o1, both_receipts(o1))["published"]
        before = r1.pointer.read_bytes()

        r2 = runner.PilotRunner(man, d / "staging", [("calendar", CALENDAR)], run_id="p2")
        o2 = r2.collect(paced(fake(bodies=bodies)), armed=True)
        real_replace = os.replace

        def boom(src, dst):
            raise OSError("injected replace failure")

        os.replace = boom
        try:
            pub = r2.finalize(o2, both_receipts(o2))
        finally:
            os.replace = real_replace
        assert pub["published"] is False and "preserved" in pub["reason"], pub
        assert r1.pointer.read_bytes() == before
        assert not r2.pointer_tmp.exists(), "our own temp should have been cleaned up"
        pointer = json.loads(r1.pointer.read_text(encoding="utf-8"))
        assert pointer["run_id"] == "p1"
        assert Path(pointer["trading"]).exists() and Path(pointer["history"]).exists()


# ============================== FULL: the approved 50+2, enforcement on, no bypasses

# The former FULL case is superseded by B-FULL below, which drives the same 50+2
# population through the OFFICIAL validate_candidate path rather than calling the
# acceptance helpers directly.


# =========================== B: the two remaining acceptance-binding counterexamples

def official_setup(tmp, run_id, omit=None):
    """Build archives + baseline + a candidate through the normal collector.

    `omit` drops one (symbol, date) from BOTH response envelopes, so the candidate is
    genuinely short - not doctored after the fact.
    """
    at, ah = build_archives(tmp)
    baseline = tmp / ("baseline_%s.json" % run_id)
    import contextlib
    import io as _io
    with contextlib.redirect_stdout(_io.StringIO()):
        assert staging_gate.main(
            ["snapshot", "--archive-trading", str(at), "--archive-history", str(ah),
             "--calendar", str(CALENDAR), "--baseline-out", str(baseline)]) == 0

    r = runner.PilotRunner(REAL_MANIFEST, tmp / "staging", [("calendar", CALENDAR)],
                           run_id=run_id)
    warm = acc.warmup_interval()
    bodies = {}
    for entries, klass in ((r.stocks, "stock"), (r.benchmarks, "benchmark")):
        for entry in entries:
            days, _ = staging_gate.entry_eligibility(entry, warm + WINDOW)
            if omit and omit[0] == entry["symbol"]:
                days = [d for d in days if d != omit[1]]
            rows = price_rows(days, with_amount=(klass == "stock"))
            if klass == "benchmark":
                rows = [{k: v for k, v in row.items() if k != "amount"} for row in rows]
            for url in prov.expected_urls(entry["symbol"], klass):
                bodies[url] = envelope(entry["symbol"], rows)

    out = r.collect(paced(fake(bodies=bodies), ceiling=500), armed=True)
    return r, out, at, ah, baseline


def validate_both(r, at, ah, baseline):
    kw = dict(archive_trading=at, archive_history=ah, baseline=baseline,
              calendar_path=CALENDAR, expected_manifest_sha=sha(REAL_MANIFEST),
              expected_calendar_sha=sha(CALENDAR))
    return (r.validate_candidate("research", **kw),
            r.validate_candidate("warmup_collection", **kw))


@case("B-R2.1 a short candidate is refused by its OWN official validation")
def _():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        short_day = [s for s in WINDOW][10]
        r, out, at, ah, baseline = official_setup(d, "shortB", omit=("SH688001", short_day))
        assert out["collection_complete"] and out["jobs_ok"] == 52, out["jobs_ok"]
        research, warmup = validate_both(r, at, ah, baseline)
        assert research.accepted is False, research.reason
        assert research.gate_exit == 1, research.gate_exit
        pub = r.finalize(out, [research, warmup])
        assert pub["published"] is False and "research validation did not succeed" in pub["reason"]


@case("B-R2.1 candidate A's receipt cannot publish candidate B")
def _():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        a, out_a, at, ah, baseline = official_setup(d, "A")
        assert out_a["collection_complete"]
        research_a, warmup_a = validate_both(a, at, ah, baseline)
        assert research_a.accepted and warmup_a.accepted, (research_a.reason, warmup_a.reason)

        short_day = [s for s in WINDOW][10]
        b, out_b, _, _, _ = official_setup(d, "B", omit=("SH688001", short_day))
        assert out_b["collection_complete"]
        # A's genuine, accepted receipts handed to B's finalization.
        pub = b.finalize(out_b, [research_a, warmup_a])
        assert pub["published"] is False, pub
        assert "issued for run" in pub["reason"] or "issued against candidate" in pub["reason"], pub
        assert not (b.root / runner.POINTER).exists()


@case("B-R2.1 there is no public way to mint a receipt from raw gate text")
def _():
    # Receipts come only from validate_candidate, which measures the fingerprint itself.
    # The lower-level acceptance helpers return Verdicts, which finalize refuses.
    assert not hasattr(acc, "make_receipt")
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        man = small_manifest(d)
        r = runner.PilotRunner(man, d / "staging", [("calendar", CALENDAR)], run_id="mint")
        out = r.collect(paced(fake(bodies=good_bodies(["SZ000001"], ["SH000300"],
                                                      WINDOW[:5]))), armed=True)
        text, code = gate_text(full_rows(acc.RESEARCH_REQUIRED))
        verdict = acc.accept_research(text, code,
                                      candidate_fingerprint=out["candidate_fingerprint"],
                                      **pins())
        assert verdict.accepted
        pub = r.finalize(out, [verdict, verdict])
        assert pub["published"] is False and "ValidationReceipt" in pub["reason"], pub


@case("B-R2.2 a research receipt cannot satisfy the warm-up requirement")
def _():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        warm_day = acc.warmup_interval()[10]
        r, out, at, ah, baseline = official_setup(d, "C", omit=("SH688001", warm_day))
        assert out["collection_complete"], [o.reason for o in out["outcomes"]][:2]
        research, warmup = validate_both(r, at, ah, baseline)
        # Research is genuinely fine; warm-up integrity genuinely is not.
        assert research.accepted, research.reason
        assert warmup.accepted is False, warmup.reason
        assert "W1_pricing" in warmup.reason, warmup.reason

        pub = r.finalize(out, [research, research])
        assert pub["published"] is False, pub
        assert "two 'research' receipts" in pub["reason"], pub["reason"]

        pub = r.finalize(out, [research, warmup])
        assert pub["published"] is False and "warmup_collection" in pub["reason"], pub
        assert not (r.root / runner.POINTER).exists()


@case("B-R2.2 a single receipt is not enough to publish")
def _():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        man = small_manifest(d)
        r = runner.PilotRunner(man, d / "staging", [("calendar", CALENDAR)], run_id="one")
        out = r.collect(paced(fake(bodies=good_bodies(["SZ000001"], ["SH000300"],
                                                      WINDOW[:5]))), armed=True)
        pub = r.finalize(out, [receipt(out, "research")])
        assert pub["published"] is False and "no 'warmup_collection' receipt" in pub["reason"]


@case("B a candidate mutated during the gate run is refused by the same binding")
def _():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        r, out, at, ah, baseline = official_setup(d, "mutate")
        assert out["collection_complete"]
        real_main = staging_gate.main

        def mutate_then_run(argv):
            conn = sqlite3.connect(r.destinations["trading"])
            conn.execute("INSERT INTO daily_bar_cache VALUES "
                         "('SZ000001','2099-01-02',1,1,1,1,1,1,'x','ready','none','hand')")
            conn.commit(); conn.close()
            return real_main(argv)

        staging_gate.main = mutate_then_run
        try:
            receipt_r = r.validate_candidate(
                "research", archive_trading=at, archive_history=ah, baseline=baseline,
                calendar_path=CALENDAR, expected_manifest_sha=sha(REAL_MANIFEST),
                expected_calendar_sha=sha(CALENDAR))
        finally:
            staging_gate.main = real_main
        assert receipt_r.accepted is False, receipt_r.reason
        assert "changed while the gate was running" in receipt_r.reason, receipt_r.reason


@case("B-FULL the approved 50+2 publishes through the OFFICIAL validation path")
def _():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        r, out, at, ah, baseline = official_setup(d, "official")
        assert out["collection_complete"] and out["jobs_ok"] == 52, out["jobs_ok"]
        research, warmup = validate_both(r, at, ah, baseline)
        assert research.accepted and research.gate_exit == 0, research.reason
        assert warmup.accepted and warmup.gate_exit == 1, warmup.reason
        assert len(warmup.details["shortfall"]) == 14, warmup.details["shortfall"]
        assert set(warmup.details["shortfall"]) == set(acc.PINNED_SHORTFALL)
        pub = r.finalize(out, [research, warmup])
        assert pub["published"], pub
        pointer = json.loads(r.pointer.read_text(encoding="utf-8"))
        assert pointer["validated_modes"] == ["research", "warmup_collection"], pointer
        assert pointer["candidate_fingerprint"] == out["candidate_fingerprint"]


def main():
    failures = 0
    print("M2a offline test suite (no network, no production write)")
    for name, fn in CASES:
        try:
            fn()
            print("  [ok] %s" % name)
        except AssertionError as exc:
            failures += 1
            print("  [XX] %s\n       %s" % (name, str(exc)[:400]))
        except Exception as exc:                        # noqa: BLE001
            failures += 1
            print("  [XX] %s\n       unexpected %s: %s"
                  % (name, type(exc).__name__, str(exc)[:400]))
    print("\n  %d cases, %d unexpected" % (len(CASES), failures))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
